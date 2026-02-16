"""Beacon — Cloud backend. FastAPI + Anthropic SDK + MCP tool proxy."""

from __future__ import annotations

import asyncio
import json
import os
import traceback
from datetime import datetime
from pathlib import Path

import anthropic
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Beacon Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://beacondemo.vercel.app",
        "https://beacon-backend-production-bbf8.up.railway.app",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

AGENTS_DIR = Path(__file__).parent.parent / "agents"

MCP_SERVERS = {
    "clinical-trials": "https://mcp.deepsense.ai/clinical_trials/mcp",
    "biorxiv": "https://mcp.deepsense.ai/biorxiv/mcp",
    "chembl": "https://mcp.deepsense.ai/chembl/mcp",
    "npi-registry": "https://mcp.deepsense.ai/npi_registry/mcp",
    "cms-coverage": "https://mcp.deepsense.ai/cms_coverage/mcp",
}

MODELS = {
    "scout": "claude-opus-4-6",
    "connector": "claude-haiku-4-5-20251001",
    "navigator": "claude-opus-4-6",
    "mobilizer": "claude-haiku-4-5-20251001",
    "strategist": "claude-opus-4-6",
    "biologist": "claude-opus-4-6",
    "chemist": "claude-opus-4-6",
    "preclinician": "claude-haiku-4-5-20251001",
}

DEMO_MODELS = {
    "scout": "claude-haiku-4-5-20251001",
    "connector": "claude-haiku-4-5-20251001",
    "navigator": "claude-haiku-4-5-20251001",
    "mobilizer": "claude-haiku-4-5-20251001",
    "strategist": "claude-opus-4-6",
    "biologist": "claude-haiku-4-5-20251001",
    "chemist": "claude-opus-4-6",
    "preclinician": "claude-haiku-4-5-20251001",
}

ITERATIONS = {
    "scout": 2, "connector": 2, "navigator": 1, "mobilizer": 1,
    "strategist": 2, "biologist": 2, "chemist": 2, "preclinician": 2,
}

DEMO_ITERATIONS = {k: 1 for k in ITERATIONS}

MCP_TOOLS_PER_AGENT = {
    "scout": [
        "biorxiv__search_preprints", "biorxiv__get_preprint",
        "clinical_trials__search_trials", "clinical_trials__get_trial_details",
        "chembl__compound_search", "chembl__target_search",
        "chembl__drug_search", "chembl__get_mechanism",
    ],
    "connector": [
        "npi_registry__npi_search", "npi_registry__npi_lookup",
        "clinical_trials__search_investigators",
    ],
    "navigator": [
        "cms_coverage__search_national_coverage", "cms_coverage__search_local_coverage",
        "clinical_trials__search_by_eligibility",
    ],
    "mobilizer": [
        "clinical_trials__search_by_sponsor", "biorxiv__search_by_funder",
    ],
    "strategist": [],
    "biologist": [
        "chembl__target_search", "chembl__get_bioactivity",
        "biorxiv__search_preprints", "biorxiv__get_preprint",
    ],
    "chemist": [
        "chembl__get_bioactivity", "chembl__drug_search",
        "chembl__compound_search", "chembl__get_mechanism",
    ],
    "preclinician": [
        "chembl__get_admet", "chembl__get_bioactivity",
        "chembl__compound_search",
    ],
}

# ---------------------------------------------------------------------------
# In-memory state (replaces file I/O)
# ---------------------------------------------------------------------------

state_lock = asyncio.Lock()

app_state: dict = {
    "mission": {},
    "agents": {},
    "approvals": [],
}

shared_plan: dict = {
    "mission": {},
    "knowledge": {},
    "approvals": [],
    "log": [],
}

# All discovered MCP tool schemas, keyed by namespaced name
mcp_tool_schemas: dict = {}  # e.g. "clinical_trials__search_trials" -> {name, description, input_schema}

# ---------------------------------------------------------------------------
# MCP tool discovery & proxy
# ---------------------------------------------------------------------------

http_client = None  # httpx.AsyncClient or None


async def get_http_client() -> httpx.AsyncClient:
    global http_client
    if http_client is None or http_client.is_closed:
        http_client = httpx.AsyncClient(timeout=60.0)
    return http_client


async def mcp_jsonrpc(server_url: str, method: str, params: dict | None = None) -> dict:
    """Send a JSON-RPC 2.0 request to an MCP server."""
    client = await get_http_client()
    payload = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params:
        payload["params"] = params
    resp = await client.post(server_url, json=payload, headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    return resp.json()


async def discover_tools_from_server(server_name: str, server_url: str):
    """Discover tools from one MCP server and cache schemas."""
    try:
        # MCP Streamable HTTP: need to initialize first, then list tools
        # Try tools/list directly (some servers support stateless)
        result = await mcp_jsonrpc(server_url, "tools/list")
        tools = result.get("result", {}).get("tools", [])
        namespace = server_name.replace("-", "_")
        for tool in tools:
            namespaced = f"{namespace}__{tool['name']}"
            mcp_tool_schemas[namespaced] = {
                "name": namespaced,
                "description": tool.get("description", ""),
                "input_schema": tool.get("inputSchema", {"type": "object", "properties": {}}),
            }
        print(f"  ✓ {server_name}: {len(tools)} tools")
    except Exception as e:
        print(f"  ✗ {server_name}: {e}")


async def discover_all_tools():
    """Discover tools from all MCP servers at startup."""
    print("Discovering MCP tools...")
    tasks = [discover_tools_from_server(name, url) for name, url in MCP_SERVERS.items()]
    await asyncio.gather(*tasks)
    print(f"Total MCP tools discovered: {len(mcp_tool_schemas)}")


async def call_mcp_tool(namespaced_name: str, arguments: dict) -> str:
    """Proxy a tool call to the appropriate MCP server."""
    # Parse namespace: "clinical_trials__search_trials" -> server="clinical-trials", tool="search_trials"
    parts = namespaced_name.split("__", 1)
    if len(parts) != 2:
        return json.dumps({"error": f"Invalid tool name: {namespaced_name}"})
    namespace, tool_name = parts
    server_name = namespace.replace("_", "-")
    server_url = MCP_SERVERS.get(server_name)
    if not server_url:
        return json.dumps({"error": f"Unknown server: {server_name}"})

    try:
        result = await mcp_jsonrpc(server_url, "tools/call", {"name": tool_name, "arguments": arguments})
        content = result.get("result", {}).get("content", [])
        # Extract text from content blocks
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block["text"])
        return "\n".join(texts) if texts else json.dumps(content)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# Public API tools (no auth required)
# ---------------------------------------------------------------------------

PUBLIC_TOOL_DEFS = {
    "search_clinical_trials": {
        "name": "search_clinical_trials",
        "description": "Search ClinicalTrials.gov for clinical trials by condition, intervention, status, or sponsor. Returns structured trial data including NCT IDs, phases, status, and enrollment.",
        "input_schema": {
            "type": "object",
            "properties": {
                "condition": {"type": "string", "description": "Disease or condition (e.g. 'CLN3 Batten Disease')"},
                "intervention": {"type": "string", "description": "Drug or treatment name"},
                "status": {"type": "string", "description": "Trial status: RECRUITING, COMPLETED, ACTIVE_NOT_RECRUITING, etc."},
                "page_size": {"type": "integer", "description": "Number of results (default 10, max 50)", "default": 10},
            },
            "required": [],
        },
    },
    "get_trial_details": {
        "name": "get_trial_details",
        "description": "Get full details for a specific clinical trial by NCT ID. Returns eligibility criteria, endpoints, locations, sponsors, and study design.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nct_id": {"type": "string", "description": "NCT identifier (e.g. 'NCT03770572')"},
            },
            "required": ["nct_id"],
        },
    },
    "search_pubmed": {
        "name": "search_pubmed",
        "description": "Search PubMed for biomedical literature. Returns article titles, authors, abstracts, PMIDs, and publication dates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (e.g. 'CLN3 gene therapy')"},
                "max_results": {"type": "integer", "description": "Number of results (default 10, max 20)", "default": 10},
            },
            "required": ["query"],
        },
    },
    "search_chembl_compound": {
        "name": "search_chembl_compound",
        "description": "Search ChEMBL for compounds by name. Returns ChEMBL IDs, molecular properties, max clinical phase, and structure info.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Compound or drug name (e.g. 'miglustat', 'cysteamine')"},
            },
            "required": ["name"],
        },
    },
    "search_chembl_target": {
        "name": "search_chembl_target",
        "description": "Search ChEMBL for biological targets by name or gene symbol. Returns target ChEMBL IDs, type, organism, and associated compounds.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Target name or gene symbol (e.g. 'CLN3', 'TPP1', 'galactosylceramidase')"},
            },
            "required": ["query"],
        },
    },
    "search_chembl_bioactivity": {
        "name": "search_chembl_bioactivity",
        "description": "Get bioactivity data (IC50, EC50, Ki) for a ChEMBL target. Returns compound-target activity measurements.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target_chembl_id": {"type": "string", "description": "ChEMBL target ID (e.g. 'CHEMBL1824')"},
                "limit": {"type": "integer", "description": "Max results (default 20)", "default": 20},
            },
            "required": ["target_chembl_id"],
        },
    },
    "search_openfda_orphan": {
        "name": "search_openfda_orphan",
        "description": "Search FDA orphan drug designations by disease or drug name. Returns designation details, sponsor, approval status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Disease or drug name (e.g. 'neuronal ceroid lipofuscinosis', 'miglustat')"},
                "limit": {"type": "integer", "description": "Max results (default 10)", "default": 10},
            },
            "required": ["query"],
        },
    },
    "search_open_targets": {
        "name": "search_open_targets",
        "description": "Search Open Targets for disease-target associations. Returns association scores, evidence counts, and tractability data for drug target prioritization.",
        "input_schema": {
            "type": "object",
            "properties": {
                "disease_query": {"type": "string", "description": "Disease name to search (e.g. 'neuronal ceroid lipofuscinosis')"},
                "size": {"type": "integer", "description": "Max results (default 10)", "default": 10},
            },
            "required": ["disease_query"],
        },
    },
}


async def call_public_tool(tool_name: str, arguments: dict) -> str:
    """Call a public API tool and return results as JSON string."""
    client = await get_http_client()

    try:
        if tool_name == "search_clinical_trials":
            params = {"format": "json", "pageSize": min(arguments.get("page_size", 10), 50)}
            cond = arguments.get("condition")
            interv = arguments.get("intervention")
            status = arguments.get("status")
            query_parts = []
            if cond:
                params["query.cond"] = cond
            if interv:
                params["query.intr"] = interv
            if status:
                params["filter.overallStatus"] = status
            r = await client.get("https://clinicaltrials.gov/api/v2/studies", params=params)
            r.raise_for_status()
            studies = r.json().get("studies", [])
            results = []
            for s in studies:
                proto = s.get("protocolSection", {})
                ident = proto.get("identificationModule", {})
                status_mod = proto.get("statusModule", {})
                design = proto.get("designModule", {})
                desc = proto.get("descriptionModule", {})
                sponsor = proto.get("sponsorCollaboratorsModule", {})
                results.append({
                    "nctId": ident.get("nctId"),
                    "title": ident.get("briefTitle"),
                    "status": status_mod.get("overallStatus"),
                    "phase": (design.get("phases") or ["N/A"]),
                    "enrollment": design.get("enrollmentInfo", {}).get("count"),
                    "briefSummary": (desc.get("briefSummary") or "")[:500],
                    "sponsor": sponsor.get("leadSponsor", {}).get("name"),
                    "startDate": status_mod.get("startDateStruct", {}).get("date"),
                })
            return json.dumps({"total": len(results), "trials": results}, indent=2)

        elif tool_name == "get_trial_details":
            nct_id = arguments["nct_id"]
            r = await client.get(f"https://clinicaltrials.gov/api/v2/studies/{nct_id}", params={"format": "json"})
            r.raise_for_status()
            proto = r.json().get("protocolSection", {})
            ident = proto.get("identificationModule", {})
            status_mod = proto.get("statusModule", {})
            design = proto.get("designModule", {})
            eligibility = proto.get("eligibilityModule", {})
            outcomes = proto.get("outcomesModule", {})
            arms = proto.get("armsInterventionsModule", {})
            contacts = proto.get("contactsLocationsModule", {})
            return json.dumps({
                "nctId": ident.get("nctId"),
                "title": ident.get("officialTitle"),
                "status": status_mod.get("overallStatus"),
                "phase": design.get("phases"),
                "studyType": design.get("studyType"),
                "enrollment": design.get("enrollmentInfo", {}).get("count"),
                "eligibility": eligibility.get("eligibilityCriteria", "")[:2000],
                "minAge": eligibility.get("minimumAge"),
                "maxAge": eligibility.get("maximumAge"),
                "sex": eligibility.get("sex"),
                "primaryOutcomes": outcomes.get("primaryOutcomes", []),
                "secondaryOutcomes": (outcomes.get("secondaryOutcomes") or [])[:5],
                "interventions": arms.get("interventions", []),
                "locations": [{"facility": loc.get("facility"), "city": loc.get("city"), "state": loc.get("state"), "country": loc.get("country")} for loc in (contacts.get("locations") or [])[:10]],
            }, indent=2)

        elif tool_name == "search_pubmed":
            query = arguments["query"]
            max_results = min(arguments.get("max_results", 10), 20)
            # Step 1: search for PMIDs
            search_r = await client.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", params={
                "db": "pubmed", "term": query, "retmax": max_results, "retmode": "json", "sort": "relevance",
            })
            search_r.raise_for_status()
            ids = search_r.json().get("esearchresult", {}).get("idlist", [])
            if not ids:
                return json.dumps({"total": 0, "articles": []})
            # Step 2: fetch summaries
            summary_r = await client.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi", params={
                "db": "pubmed", "id": ",".join(ids), "retmode": "json",
            })
            summary_r.raise_for_status()
            result_data = summary_r.json().get("result", {})
            articles = []
            for pmid in ids:
                art = result_data.get(pmid, {})
                if not isinstance(art, dict):
                    continue
                authors = [a.get("name", "") for a in art.get("authors", [])[:5]]
                articles.append({
                    "pmid": pmid,
                    "title": art.get("title", ""),
                    "authors": authors,
                    "journal": art.get("fulljournalname", ""),
                    "pubDate": art.get("pubdate", ""),
                    "doi": art.get("elocationid", ""),
                })
            return json.dumps({"total": len(articles), "articles": articles}, indent=2)

        elif tool_name == "search_chembl_compound":
            name = arguments["name"]
            r = await client.get(f"https://www.ebi.ac.uk/chembl/api/data/molecule/search.json", params={"q": name, "limit": 10})
            r.raise_for_status()
            molecules = r.json().get("molecules", [])
            results = []
            for m in molecules[:10]:
                props = m.get("molecule_properties") or {}
                results.append({
                    "chembl_id": m.get("molecule_chembl_id"),
                    "name": m.get("pref_name"),
                    "max_phase": m.get("max_phase"),
                    "molecule_type": m.get("molecule_type"),
                    "mw": props.get("full_mwt"),
                    "alogp": props.get("alogp"),
                    "hba": props.get("hba"),
                    "hbd": props.get("hbd"),
                    "psa": props.get("psa"),
                    "ro5_violations": props.get("num_ro5_violations"),
                })
            return json.dumps({"total": len(results), "compounds": results}, indent=2)

        elif tool_name == "search_chembl_target":
            query = arguments["query"]
            r = await client.get(f"https://www.ebi.ac.uk/chembl/api/data/target/search.json", params={"q": query, "limit": 10})
            r.raise_for_status()
            targets = r.json().get("targets", [])
            results = []
            for t in targets[:10]:
                components = t.get("target_components", [])
                gene_symbols = []
                for comp in components:
                    for syn in comp.get("target_component_synonyms", []):
                        if syn.get("syn_type") == "GENE_SYMBOL":
                            gene_symbols.append(syn.get("component_synonym"))
                results.append({
                    "chembl_id": t.get("target_chembl_id"),
                    "name": t.get("pref_name"),
                    "type": t.get("target_type"),
                    "organism": t.get("organism"),
                    "gene_symbols": gene_symbols[:3],
                })
            return json.dumps({"total": len(results), "targets": results}, indent=2)

        elif tool_name == "search_chembl_bioactivity":
            target_id = arguments["target_chembl_id"]
            limit = min(arguments.get("limit", 20), 50)
            r = await client.get(f"https://www.ebi.ac.uk/chembl/api/data/activity.json", params={
                "target_chembl_id": target_id, "limit": limit, "pchembl_value__isnull": "false",
            })
            r.raise_for_status()
            activities = r.json().get("activities", [])
            results = []
            for a in activities:
                results.append({
                    "molecule_chembl_id": a.get("molecule_chembl_id"),
                    "molecule_name": a.get("molecule_pref_name"),
                    "activity_type": a.get("standard_type"),
                    "value": a.get("standard_value"),
                    "units": a.get("standard_units"),
                    "pchembl": a.get("pchembl_value"),
                })
            return json.dumps({"total": len(results), "activities": results}, indent=2)

        elif tool_name == "search_openfda_orphan":
            query = arguments["query"]
            limit = min(arguments.get("limit", 10), 25)
            r = await client.get("https://api.fda.gov/drug/drugsfda.json", params={
                "search": f'openfda.brand_name:"{query}"+openfda.generic_name:"{query}"',
                "limit": limit,
            })
            if r.status_code == 404:
                # Try orphan drug product list
                r2 = await client.get("https://api.fda.gov/drug/drugsfda.json", params={
                    "search": f'products.active_ingredients.name:"{query}"',
                    "limit": limit,
                })
                if r2.status_code == 200:
                    r = r2
                else:
                    return json.dumps({"total": 0, "results": [], "note": "No orphan drug designations found"})
            if r.status_code != 200:
                return json.dumps({"total": 0, "results": [], "note": f"FDA API returned {r.status_code}"})
            data = r.json()
            results = []
            for item in data.get("results", [])[:limit]:
                openfda = item.get("openfda", {})
                products = item.get("products", [])
                results.append({
                    "brand_name": openfda.get("brand_name", []),
                    "generic_name": openfda.get("generic_name", []),
                    "manufacturer": openfda.get("manufacturer_name", []),
                    "route": openfda.get("route", []),
                    "products": [{"name": p.get("brand_name"), "dosage": p.get("dosage_form"), "active_ingredients": p.get("active_ingredients", [])} for p in products[:3]],
                })
            return json.dumps({"total": len(results), "results": results}, indent=2)

        elif tool_name == "search_open_targets":
            disease_query = arguments["disease_query"]
            size = min(arguments.get("size", 10), 25)
            # Step 1: search for disease ID
            gql = {
                "query": """query ($q: String!, $size: Int!) {
                    search(queryString: $q, entityNames: ["disease"], page: {size: 1, index: 0}) {
                        hits { id name }
                    }
                }""",
                "variables": {"q": disease_query, "size": 1},
            }
            r = await client.post("https://api.platform.opentargets.org/api/v4/graphql", json=gql)
            r.raise_for_status()
            hits = r.json().get("data", {}).get("search", {}).get("hits", [])
            if not hits:
                return json.dumps({"total": 0, "associations": [], "note": "Disease not found in Open Targets"})
            disease_id = hits[0]["id"]
            disease_name = hits[0]["name"]
            # Step 2: get associated targets
            gql2 = {
                "query": """query ($diseaseId: String!, $size: Int!) {
                    disease(efoId: $diseaseId) {
                        associatedTargets(page: {size: $size, index: 0}) {
                            count
                            rows {
                                target { id approvedSymbol approvedName }
                                score
                                datatypeScores { id score }
                            }
                        }
                    }
                }""",
                "variables": {"diseaseId": disease_id, "size": size},
            }
            r2 = await client.post("https://api.platform.opentargets.org/api/v4/graphql", json=gql2)
            r2.raise_for_status()
            assoc_data = r2.json().get("data", {}).get("disease", {}).get("associatedTargets", {})
            rows = assoc_data.get("rows", [])
            results = []
            for row in rows:
                target = row.get("target", {})
                dtypes = {d["id"]: round(d["score"], 3) for d in row.get("datatypeScores", [])}
                results.append({
                    "target_id": target.get("id"),
                    "symbol": target.get("approvedSymbol"),
                    "name": target.get("approvedName"),
                    "overall_score": round(row.get("score", 0), 3),
                    "evidence_scores": dtypes,
                })
            return json.dumps({
                "disease": disease_name,
                "disease_id": disease_id,
                "total_associations": assoc_data.get("count", 0),
                "top_targets": results,
            }, indent=2)

        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

    except Exception as e:
        return json.dumps({"error": str(e), "tool": tool_name})


# Which public tools each agent gets
PUBLIC_TOOLS_PER_AGENT = {
    "scout": ["search_clinical_trials", "get_trial_details", "search_pubmed", "search_chembl_compound"],
    "connector": ["search_pubmed", "search_clinical_trials"],
    "navigator": ["search_clinical_trials", "search_openfda_orphan"],
    "mobilizer": ["search_clinical_trials", "search_pubmed"],
    "strategist": [],
    "biologist": ["search_chembl_target", "search_chembl_bioactivity", "search_open_targets", "search_pubmed"],
    "chemist": ["search_chembl_compound", "search_chembl_target", "search_chembl_bioactivity"],
    "preclinician": ["search_chembl_compound", "search_chembl_bioactivity", "search_pubmed"],
}


# ---------------------------------------------------------------------------
# Agent conversation via Anthropic SDK
# ---------------------------------------------------------------------------

def get_tools_for_agent(agent_name: str) -> list[dict]:
    """Get Anthropic-format tool definitions for an agent.

    Uses public API tools + web_search.
    """
    tools = []

    # Add public API tools
    for tool_name in PUBLIC_TOOLS_PER_AGENT.get(agent_name, []):
        if tool_name in PUBLIC_TOOL_DEFS:
            tools.append(PUBLIC_TOOL_DEFS[tool_name])

    # Also add MCP tools if discovered
    allowed = MCP_TOOLS_PER_AGENT.get(agent_name, [])
    for name in allowed:
        schema = mcp_tool_schemas.get(name)
        if schema:
            tools.append({
                "name": schema["name"],
                "description": schema["description"],
                "input_schema": schema["input_schema"],
            })

    # Add web_search only if agent has no public API tools (to avoid name conflicts)
    if agent_name != "strategist" and not tools:
        tools.append({"type": "web_search_20250305", "name": "web_search", "max_uses": 8})

    # Deduplicate by name
    seen = set()
    deduped = []
    for t in tools:
        name = t.get("name", "")
        if name not in seen:
            seen.add(name)
            deduped.append(t)
    return deduped


async def run_agent_conversation(agent_name: str, prompt: str, model: str, api_key: str | None = None) -> str:
    """Run a multi-turn conversation with an agent, handling tool_use blocks."""
    client = anthropic.AsyncAnthropic(**({"api_key": api_key} if api_key else {}))
    tools = get_tools_for_agent(agent_name)
    messages = [{"role": "user", "content": prompt}]

    # Check if using server tools (web_search) vs custom tools
    has_server_tools = any(t.get("type", "").startswith("web_search") for t in tools)
    custom_tools = [t for t in tools if not t.get("type", "").startswith("web_search")]
    server_tools = [t for t in tools if t.get("type", "").startswith("web_search")]

    tool_calls_count = 0
    max_turns = 15
    for _ in range(max_turns):
        kwargs = {"model": model, "max_tokens": 16384, "messages": messages}
        if custom_tools:
            kwargs["tools"] = custom_tools
        if server_tools:
            # Anthropic API: server-side tools go in a separate field
            kwargs.setdefault("tools", [])
            kwargs["tools"].extend(server_tools)

        if _ == 0:  # Log tools on first turn only
            tool_names = [t.get("name", "?") for t in kwargs.get("tools", [])]
            print(f"  🔧 {agent_name}: sending {len(tool_names)} tools: {tool_names}")
        response = await client.messages.create(**kwargs)

        # Check if there are tool_use blocks (custom tools only — web_search is handled server-side)
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            # Extract only actual text blocks (not web_search_tool_result or other types)
            text_blocks = [b.text for b in response.content if b.type == "text"]
            return "\n".join(text_blocks), tool_calls_count

        # Process tool calls — route to public API tools or MCP proxy
        tool_calls_count += len(tool_uses)
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for tu in tool_uses:
            if tu.name in PUBLIC_TOOL_DEFS:
                result_text = await call_public_tool(tu.name, tu.input)
            else:
                result_text = await call_mcp_tool(tu.name, tu.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": result_text[:15000],
            })
        messages.append({"role": "user", "content": tool_results})

    return "(max tool turns reached)", tool_calls_count


# ---------------------------------------------------------------------------
# State helpers (async-safe)
# ---------------------------------------------------------------------------

async def add_agent_update(agent_name: str, message: str, update_type: str = "status", completed: bool = False, mission_id: str = None):
    async with state_lock:
        if mission_id and current_mission_id != mission_id:
            return False  # Stale agent, stop writing
        agent = app_state["agents"].get(agent_name, {})
        if "updates" not in agent:
            agent["updates"] = []
        agent["updates"].append({
            "timestamp": datetime.now().isoformat(),
            "type": update_type,
            "message": message,
            "completed": completed,
        })
        app_state["agents"][agent_name] = agent
    return True


async def update_agent_status(agent_name: str, status: str, current_task: str = "", mission_id: str = None):
    async with state_lock:
        if mission_id and current_mission_id != mission_id:
            return False  # Stale agent
        if agent_name not in app_state["agents"]:
            app_state["agents"][agent_name] = {}
        app_state["agents"][agent_name]["status"] = status
        app_state["agents"][agent_name]["lastRun"] = datetime.now().isoformat()
        if current_task:
            app_state["agents"][agent_name]["current_task"] = current_task
    return True


def build_prompt(agent_name: str, plan: dict, iteration: int, num_iterations: int) -> str:
    """Build prompt with shared plan context and iteration instructions."""
    prompt_path = AGENTS_DIR / f"{agent_name}.md"
    if not prompt_path.exists():
        return f"You are the {agent_name} agent. Respond with valid JSON."
    prompt = prompt_path.read_text()

    disease = plan["mission"].get("disease", "")
    priorities = plan["mission"].get("priorities", [])
    journey_stage = plan["mission"].get("journeyStage", "just-diagnosed")
    patient = plan["mission"].get("patient", "")
    location = plan["mission"].get("location", "us")

    knowledge_context = ""
    for other_agent, knowledge in plan.get("knowledge", {}).items():
        if other_agent != agent_name and knowledge.get("updated_at"):
            knowledge_context += f"\n=== {other_agent.upper()} FINDINGS ===\n"
            knowledge_context += json.dumps(knowledge, indent=2)[:4000]
            knowledge_context += "\n"

    jurisdiction = "FDA (United States)" if location == "us" else "EMA (Europe)" if location == "eu" else "International"

    return f"""{prompt}

The disease is: {disease}
Journey stage: {journey_stage}
Patient: {patient if patient else 'not specified'}
Regulatory jurisdiction: {jurisdiction}
Focus areas: {', '.join(priorities) if priorities else 'all'}

ITERATION: {iteration} of {num_iterations - 1} (0-indexed)
{"This is your first pass. Do broad initial research." if iteration == 0 else "Build on previous findings and other agents' discoveries. Go deeper on promising leads."}

{f"=== CONTEXT FROM OTHER AGENTS ==={knowledge_context}" if knowledge_context else "No other agent data available yet (you are running in parallel)."}

Output ONLY valid JSON. No markdown fences, no explanation."""


def merge_output(agent_name: str, raw_output: str):
    """Parse agent output and merge into shared_plan + app_state. Synchronous, caller holds lock."""
    output = raw_output
    try:
        parsed = json.loads(raw_output)
        if "result" in parsed and isinstance(parsed["result"], str):
            output = parsed["result"]
    except json.JSONDecodeError:
        pass

    if "```json" in output:
        output = output.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in output:
        output = output.split("```", 1)[1].split("```", 1)[0].strip()

    # Try to extract JSON object/array
    try:
        json.loads(output)
    except (json.JSONDecodeError, ValueError):
        for start_char, end_char in [('{', '}'), ('[', ']')]:
            start_idx = output.find(start_char)
            if start_idx == -1:
                continue
            end_idx = output.rfind(end_char)
            if end_idx > start_idx:
                candidate = output[start_idx:end_idx + 1]
                try:
                    json.loads(candidate)
                    output = candidate
                    break
                except (json.JSONDecodeError, ValueError):
                    pass

    try:
        data = json.loads(output)
    except json.JSONDecodeError as e:
        print(f"  ⚠️  {agent_name}: JSON parse failed: {e}")
        print(f"  ⚠️  {agent_name}: output length={len(output)}, first 200 repr: {repr(output[:200])}")
        print(f"  ⚠️  {agent_name}: last 200 repr: {repr(output[-200:])}")
        return output

    print(f"  📦 {agent_name}: parsed JSON with keys: {list(data.keys()) if isinstance(data, dict) else 'array'}")
    now = datetime.now().isoformat()

    # Merge into shared_plan knowledge (same logic as orchestrate.py)
    if agent_name == "scout":
        shared_plan["knowledge"]["scout"] = {
            "findings": data.get("findings", []),
            "knowledge_graph": data.get("knowledgeGraph", {}),
            "handoffs": data.get("handoffs", []),
            "updated_at": now,
        }
    elif agent_name == "connector":
        shared_plan["knowledge"]["connector"] = {
            "contacts": data.get("contacts", []),
            "drafts": [c.get("email_draft", {}) for c in data.get("contacts", []) if c.get("email_draft")],
            "updated_at": now,
        }
    elif agent_name == "navigator":
        shared_plan["knowledge"]["navigator"] = {
            "pathways": data.get("regulatoryPathways", {}),
            "updated_at": now,
        }
    elif agent_name == "mobilizer":
        shared_plan["knowledge"]["mobilizer"] = {
            "grants": data.get("grantOpportunities", []),
            "fundraisingStrategy": data.get("fundraisingStrategy", {}),
            "advocacyConnections": data.get("advocacyConnections", []),
            "draftApplications": data.get("draftApplications", []),
            "experimentFundingMatches": data.get("experimentFundingMatches", {}),
            "pharmaPartnerships": data.get("pharmaPartnerships", []),
            "entityFormation": data.get("entityFormation", {}),
            "updated_at": now,
        }
    elif agent_name == "strategist":
        shared_plan["knowledge"]["strategist"] = {
            "roadmap": data.get("weeklyBriefing", {}).get("masterRoadmap", {}),
            "priorities": data.get("weeklyBriefing", {}).get("topPriorities", []),
            "questionsForFamily": data.get("weeklyBriefing", {}).get("questionsForFamily", []),
            "updated_at": now,
        }
    elif agent_name == "biologist":
        shared_plan["knowledge"]["biologist"] = {
            "targets": data.get("targets", []),
            "disease_mechanism": data.get("disease_mechanism", ""),
            "target_ranking": data.get("target_ranking", []),
            "pathway_map": data.get("pathway_map", {}),
            "handoffs": data.get("handoffs", []),
            "updated_at": now,
        }
    elif agent_name == "chemist":
        shared_plan["knowledge"]["chemist"] = {
            "screening_summary": data.get("screening_summary", {}),
            "repurposing_candidates": data.get("repurposing_candidates", []),
            "novel_candidates": data.get("novel_candidates", []),
            "candidate_ranking": data.get("candidate_ranking", []),
            "handoffs": data.get("handoffs", []),
            "updated_at": now,
        }
    elif agent_name == "preclinician":
        shared_plan["knowledge"]["preclinician"] = {
            "candidate_evaluations": data.get("candidate_evaluations", []),
            "experiment_design": data.get("experiment_design", {}),
            "cro_requirements": data.get("cro_requirements", {}),
            "updated_at": now,
        }

    # Handle approval items
    approval_items = data.get("approvalItems", [])
    if approval_items:
        shared_plan["approvals"].extend(approval_items)
        app_state.setdefault("approvals", []).extend(approval_items)

    shared_plan["log"].append({
        "agent": agent_name,
        "timestamp": now,
        "summary": f"{agent_name} completed update",
    })

    return output


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

TASK_DESCRIPTIONS = {
    "scout": "Searching medical literature and clinical trials",
    "connector": "Identifying researchers and drafting outreach",
    "navigator": "Mapping regulatory pathways",
    "mobilizer": "Finding grants and funding opportunities",
    "strategist": "Synthesizing findings and building roadmap",
    "biologist": "Analyzing disease mechanism and identifying drug targets",
    "chemist": "Screening compounds and evaluating drug candidates",
    "preclinician": "Evaluating ADMET profiles and designing experiments",
}


async def run_agent_loop(agent_name: str, demo: bool = True, mission_id: str = None, api_key: str | None = None):
    """Run all iterations of an agent."""
    await update_agent_status(agent_name, "working", TASK_DESCRIPTIONS.get(agent_name, "Working..."), mission_id=mission_id)
    alive = await add_agent_update(agent_name, f"Starting {agent_name} agent...", mission_id=mission_id)
    if alive is False:
        return  # Mission changed, abort

    models = DEMO_MODELS if demo else MODELS
    iterations = DEMO_ITERATIONS if demo else ITERATIONS
    num_iterations = iterations[agent_name]
    model = models[agent_name]

    try:
        for i in range(num_iterations):
            # Check if mission has changed
            if mission_id and current_mission_id != mission_id:
                print(f"  🛑 {agent_name} aborted — mission changed")
                return

            if agent_name == "strategist" and i > 0:
                await add_agent_update(agent_name, "Waiting for more agent data...", mission_id=mission_id)
                await asyncio.sleep(5)

            await add_agent_update(agent_name, f"Iteration {i+1}/{num_iterations}...", mission_id=mission_id)

            async with state_lock:
                if mission_id and current_mission_id != mission_id:
                    return
                prompt = build_prompt(agent_name, shared_plan, i, num_iterations)

            raw_output, tc_count = await run_agent_conversation(agent_name, prompt, model, api_key=api_key)

            # Check again after long API call
            if mission_id and current_mission_id != mission_id:
                print(f"  🛑 {agent_name} aborted after API call — mission changed")
                return

            async with state_lock:
                if mission_id and current_mission_id != mission_id:
                    return
                merge_output(agent_name, raw_output)
                agent_data = app_state["agents"].setdefault(agent_name, {})
                agent_data["tool_calls_count"] = agent_data.get("tool_calls_count", 0) + tc_count

            # Add status updates based on merged data
            async with state_lock:
                knowledge = shared_plan["knowledge"].get(agent_name, {})
            if agent_name == "scout":
                findings = knowledge.get("findings", [])
                await add_agent_update(agent_name, f"Found {len(findings)} research findings", "status", True, mission_id=mission_id)
                for f in findings[:3]:
                    await add_agent_update(agent_name, f.get("title", "Finding"), "finding", True, mission_id=mission_id)
            elif agent_name == "connector":
                contacts = knowledge.get("contacts", [])
                await add_agent_update(agent_name, f"Identified {len(contacts)} outreach targets", "status", True, mission_id=mission_id)
            elif agent_name == "navigator":
                await add_agent_update(agent_name, "Regulatory pathway mapping complete", "status", True, mission_id=mission_id)
            elif agent_name == "mobilizer":
                grants = knowledge.get("grants", [])
                await add_agent_update(agent_name, f"Found {len(grants)} grant opportunities", "status", True, mission_id=mission_id)
            elif agent_name == "strategist":
                await add_agent_update(agent_name, "Weekly briefing ready", "finding", True, mission_id=mission_id)
            elif agent_name == "biologist":
                targets = knowledge.get("targets", [])
                await add_agent_update(agent_name, f"Identified {len(targets)} therapeutic targets", "status", True, mission_id=mission_id)
            elif agent_name == "chemist":
                candidates = knowledge.get("repurposing_candidates", [])
                await add_agent_update(agent_name, f"Found {len(candidates)} repurposing candidates", "status", True, mission_id=mission_id)
            elif agent_name == "preclinician":
                evals = knowledge.get("candidate_evaluations", [])
                await add_agent_update(agent_name, f"Evaluated {len(evals)} candidates", "status", True, mission_id=mission_id)

            print(f"  ✅ {agent_name} iteration {i+1}/{num_iterations} complete")

        if mission_id and current_mission_id != mission_id:
            return
        await update_agent_status(agent_name, "complete", mission_id=mission_id)
    except Exception as e:
        traceback.print_exc()
        if mission_id and current_mission_id == mission_id:
            await update_agent_status(agent_name, "error", mission_id=mission_id)
            await add_agent_update(agent_name, f"Error: {str(e)[:100]}", "status", False, mission_id=mission_id)


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

BEACON_TOKEN = os.environ.get("BEACON_TOKEN", "beacon2026")


class LaunchRequest(BaseModel):
    disease: str = "CLN3 Batten Disease"
    priorities: list[str] = ["research", "experts", "regulatory", "funding"]
    journeyStage: str = "just-diagnosed"
    patient: str = ""
    location: str = "us"
    demo: bool = True
    api_key: str | None = None
    token: str | None = None


current_mission_id = None
current_api_key: str | None = None  # resolved API key for current mission

@app.post("/api/launch")
async def launch(req: LaunchRequest):
    """Launch all agents for a mission."""
    from fastapi.responses import JSONResponse
    global app_state, shared_plan, current_mission_id, current_api_key

    # --- BYOK / token auth ---
    resolved_key: str | None = None
    if req.token and req.token == BEACON_TOKEN:
        resolved_key = None  # use server's ANTHROPIC_API_KEY (env var)
    elif req.api_key and req.api_key.startswith("sk-ant-"):
        resolved_key = req.api_key
    else:
        return JSONResponse(status_code=403, content={"error": "Provide a valid token or Anthropic API key to launch agents."})

    current_api_key = resolved_key

    import uuid
    mission_id = str(uuid.uuid4())[:8]
    current_mission_id = mission_id

    async with state_lock:
        # Reset state
        mission = {
            "disease": req.disease,
            "priorities": req.priorities,
            "journeyStage": req.journeyStage,
            "patient": req.patient,
            "location": req.location,
            "stage": "launch",
            "created_at": datetime.now().isoformat(),
            "mission_id": mission_id,
        }
        app_state = {
            "mission": mission,
            "agents": {name: {"status": "pending", "updates": []} for name in MODELS},
            "approvals": [],
        }
        shared_plan = {
            "mission": mission,
            "knowledge": {},
            "approvals": [],
            "log": [{"agent": "orchestrator", "timestamp": datetime.now().isoformat(),
                      "summary": f"Mission initialized for {req.disease}"}],
        }

    agent_names = ["scout", "connector", "navigator", "mobilizer",
                    "strategist", "biologist", "chemist", "preclinician"]

    async def run_synthesis():
        """Extended context synthesis: concatenate all agent outputs and produce unified briefing."""
        if current_mission_id != mission_id:
            return
        async with state_lock:
            app_state["synthesis"] = {"status": "running", "result": None}
            all_knowledge = json.dumps(shared_plan.get("knowledge", {}), indent=1, default=str)
            disease = shared_plan.get("mission", {}).get("disease", "the condition")

        token_estimate = len(all_knowledge) // 4  # rough char-to-token ratio
        print(f"  🧠 Synthesis pass: ~{token_estimate:,} tokens from 8 agents")

        client = anthropic.AsyncAnthropic(**({"api_key": resolved_key} if resolved_key else {}))
        try:
            response = await client.messages.create(
                model="claude-opus-4-6",
                max_tokens=4096,
                messages=[{"role": "user", "content": f"""You are the Chief Strategist for a rare disease family support team.
Below is the complete output from 8 specialist AI agents who have been researching {disease}.
Synthesize ALL findings into a clear, actionable 1-page family briefing with these sections:
1. **Key Discovery** — The single most important finding
2. **Treatment Pathways** — Ranked options with status
3. **Immediate Actions** — 3-5 things the family should do this week
4. **Research Landscape** — Brief overview of active trials and research groups
5. **Funding & Regulatory** — Grant opportunities and pathway status

Write for a non-expert family member. Be warm, clear, and action-oriented.

=== AGENT OUTPUTS ({token_estimate:,} tokens) ===
{all_knowledge[:200000]}"""}],
            )
            synthesis_text = "\n".join(b.text for b in response.content if b.type == "text")
            async with state_lock:
                app_state["synthesis"] = {
                    "status": "complete",
                    "result": synthesis_text,
                    "token_count": token_estimate,
                }
            print(f"  ✅ Synthesis complete")
        except Exception as e:
            traceback.print_exc()
            async with state_lock:
                app_state["synthesis"] = {"status": "error", "result": str(e)[:200]}

    async def pre_generate_summaries():
        """Pre-generate lab summary and researcher briefing after agents complete."""
        try:
            from starlette.testclient import TestClient
        except ImportError:
            pass
        # Just call the endpoint functions directly
        await lab_summary()
        await researcher_briefing()
        print("  ✅ Lab summaries pre-generated")

    async def run_all():
        await asyncio.gather(*[run_agent_loop(name, demo=req.demo, mission_id=mission_id, api_key=resolved_key) for name in agent_names])
        if current_mission_id != mission_id:
            return  # Mission changed, skip synthesis
        # Run synthesis and pre-generate summaries in parallel
        await asyncio.gather(run_synthesis(), pre_generate_summaries())
        if current_mission_id == mission_id:
            async with state_lock:
                app_state["mission"]["stage"] = "roadmap"

    asyncio.create_task(run_all())
    return {"status": "launched", "agents": agent_names}


@app.get("/api/state")
async def get_state():
    async with state_lock:
        return app_state


@app.get("/api/plan")
async def get_plan():
    async with state_lock:
        return shared_plan


lab_summary_cache = {"mission_id": None, "result": None, "status": "idle"}

@app.get("/api/lab-summary")
async def lab_summary():
    """Generate a family-friendly summary of the Drug Discovery Lab findings."""
    global lab_summary_cache

    # Return cached if same mission
    if lab_summary_cache["mission_id"] == current_mission_id and lab_summary_cache["result"]:
        return lab_summary_cache

    # Check if lab agents have data
    async with state_lock:
        knowledge = shared_plan.get("knowledge", {})
        disease = shared_plan.get("mission", {}).get("disease", "the condition")

    bio = knowledge.get("biologist", {})
    chem = knowledge.get("chemist", {})
    prec = knowledge.get("preclinician", {})

    if not bio.get("targets") and not chem.get("repurposing_candidates"):
        return {"status": "waiting", "result": None, "mission_id": current_mission_id}

    lab_summary_cache = {"mission_id": current_mission_id, "result": None, "status": "generating"}

    lab_data = json.dumps({"biologist": bio, "chemist": chem, "preclinician": prec}, indent=1, default=str)[:50000]

    client = anthropic.AsyncAnthropic(**({"api_key": current_api_key} if current_api_key else {}))
    try:
        response = await client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1500,
            messages=[{"role": "user", "content": f"""You are writing for a family member (non-scientist) whose child has {disease}.

Below is technical data from our Drug Discovery Lab agents (biologist, chemist, preclinician) about potential treatments.

Write a warm, clear 3-4 paragraph summary that:
1. Explains what our lab team found in plain language (what targets were identified, what drugs look promising)
2. Highlights the most actionable finding (the best drug candidate and why)
3. Lists 2-3 concrete next steps the family could take
4. Notes any safety considerations in reassuring language

Keep it under 300 words. No jargon. No markdown headers. Write as if you're a kind doctor explaining results to a worried parent.

=== LAB DATA ===
{lab_data}"""}],
        )
        result = "\n".join(b.text for b in response.content if b.type == "text")
        lab_summary_cache = {"mission_id": current_mission_id, "result": result, "status": "complete"}
    except Exception as e:
        traceback.print_exc()
        lab_summary_cache = {"mission_id": current_mission_id, "result": f"Summary unavailable: {str(e)[:100]}", "status": "error"}

    return lab_summary_cache


researcher_briefing_cache = {"mission_id": None, "result": None, "status": "idle"}

@app.get("/api/researcher-briefing")
async def researcher_briefing():
    """Generate a technical briefing a family can forward to a researcher identified by Connector."""
    global researcher_briefing_cache

    if researcher_briefing_cache["mission_id"] == current_mission_id and researcher_briefing_cache["result"]:
        return researcher_briefing_cache

    async with state_lock:
        knowledge = shared_plan.get("knowledge", {})
        disease = shared_plan.get("mission", {}).get("disease", "the condition")

    bio = knowledge.get("biologist", {})
    chem = knowledge.get("chemist", {})
    prec = knowledge.get("preclinician", {})
    scout = knowledge.get("scout", {})
    connector = knowledge.get("connector", {})

    if not bio.get("targets") and not scout.get("findings"):
        return {"status": "waiting", "result": None, "mission_id": current_mission_id}

    researcher_briefing_cache = {"mission_id": current_mission_id, "result": None, "status": "generating"}

    all_data = json.dumps({"scout": scout, "biologist": bio, "chemist": chem, "preclinician": prec, "connector": connector}, indent=1, default=str)[:60000]

    client = anthropic.AsyncAnthropic(**({"api_key": current_api_key} if current_api_key else {}))
    try:
        response = await client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2000,
            messages=[{"role": "user", "content": f"""Write a professional research briefing document about {disease} that a patient's family can forward to a researcher or specialist they've been connected with.

The briefing should:
1. Open with a concise clinical summary of the patient's condition ({disease})
2. Summarize the computational drug discovery analysis performed (targets identified, compounds screened, top candidates)
3. Present the top 2-3 drug repurposing candidates with their mechanisms, evidence, and safety profiles
4. Include relevant clinical trial matches
5. End with specific questions the family would like the researcher's input on

Write in professional scientific language appropriate for a PhD/MD researcher. Include data points (pChEMBL values, IC50s, gene names) where available. Format with clear sections.

Start with: "RESEARCH BRIEFING: {disease} — Computational Drug Discovery Analysis"

=== AGENT DATA ===
{all_data}"""}],
        )
        result = "\n".join(b.text for b in response.content if b.type == "text")
        researcher_briefing_cache = {"mission_id": current_mission_id, "result": result, "status": "complete"}
    except Exception as e:
        traceback.print_exc()
        researcher_briefing_cache = {"mission_id": current_mission_id, "result": f"Briefing unavailable: {str(e)[:100]}", "status": "error"}

    return researcher_briefing_cache


@app.get("/api/health")
async def health():
    return {"status": "ok", "tools": len(mcp_tool_schemas)}


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    await discover_all_tools()
