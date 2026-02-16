#!/usr/bin/env python3
"""Beacon — Multi-agent orchestrator. Parallel execution with shared memory and MCP tools."""

import asyncio
import fcntl
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "orchestrator" / "state.json"
SHARED_PLAN_FILE = ROOT / "orchestrator" / "shared_plan.json"
MCP_CONFIG = ROOT / "orchestrator" / "mcp_config.json"
AGENTS_DIR = ROOT / "agents"
OUTPUTS_DIR = ROOT / "outputs"
APP_DATA = ROOT / "app" / "data"

DEMO_MODE = "--demo" in sys.argv or os.environ.get("BEACON_DEMO") == "1"

# Model assignment: Opus for complex reasoning, Haiku for structured extraction
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

# Iterations per agent
ITERATIONS = {
    "scout": 2,
    "connector": 2,
    "navigator": 1,
    "mobilizer": 1,
    "strategist": 2,
    "biologist": 2,
    "chemist": 2,
    "preclinician": 2,
}

DEMO_ITERATIONS = {
    "scout": 1, "connector": 1, "navigator": 1, "mobilizer": 1, "strategist": 1,
    "biologist": 1, "chemist": 2, "preclinician": 2,
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

# MCP tools each agent should use (included in prompt instructions)
MCP_TOOLS = {
    "scout": [
        "biorxiv.search_preprints", "biorxiv.get_preprint",
        "clinical-trials.search_trials", "clinical-trials.get_trial_details",
        "chembl.compound_search", "chembl.target_search",
        "chembl.drug_search", "chembl.get_mechanism",
    ],
    "connector": [
        "npi-registry.npi_search", "npi-registry.npi_lookup",
        "clinical-trials.search_investigators",
    ],
    "navigator": [
        "cms-coverage.search_national_coverage", "cms-coverage.search_local_coverage",
        "clinical-trials.search_by_eligibility",
    ],
    "mobilizer": [
        "clinical-trials.search_by_sponsor", "biorxiv.search_by_funder",
    ],
    "strategist": [],
    "biologist": [
        "chembl.target_search", "chembl.get_bioactivity",
        "biorxiv.search_preprints", "biorxiv.get_preprint",
    ],
    "chemist": [
        "chembl.get_bioactivity", "chembl.drug_search",
        "chembl.compound_search", "chembl.get_mechanism",
    ],
    "preclinician": [
        "chembl.get_admet", "chembl.get_bioactivity",
        "chembl.compound_search",
    ],
}


def load_state():
    with open(STATE_FILE) as f:
        return json.load(f)


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
    APP_DATA.mkdir(parents=True, exist_ok=True)
    with open(APP_DATA / "state.json", "w") as f:
        json.dump(state, f, indent=2)


def load_shared_plan():
    """Load shared plan with file locking."""
    with open(SHARED_PLAN_FILE) as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        data = json.load(f)
        fcntl.flock(f, fcntl.LOCK_UN)
    return data


def save_shared_plan(plan):
    """Save shared plan with exclusive file locking."""
    with open(SHARED_PLAN_FILE, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        json.dump(plan, f, indent=2)
        fcntl.flock(f, fcntl.LOCK_UN)
    # Also copy to app/data for frontend
    APP_DATA.mkdir(parents=True, exist_ok=True)
    with open(APP_DATA / "shared_plan.json", "w") as f:
        json.dump(plan, f, indent=2)


def add_agent_update(agent_name, message, update_type="status", completed=False):
    """Add a streaming status update for an agent."""
    state = load_state()
    agent = state["agents"][agent_name]
    if "updates" not in agent:
        agent["updates"] = []
    agent["updates"].append({
        "timestamp": datetime.now().isoformat(),
        "type": update_type,
        "message": message,
        "completed": completed,
    })
    save_state(state)


def update_agent_status(agent_name, status, current_task=""):
    state = load_state()
    state["agents"][agent_name]["status"] = status
    state["agents"][agent_name]["lastRun"] = datetime.now().isoformat()
    if current_task:
        state["agents"][agent_name]["current_task"] = current_task
    save_state(state)


def merge_output(agent_name, raw_output):
    """Parse agent output and merge into shared plan + state.json."""
    # Strip markdown fences
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

    # If still not valid JSON, try to extract the first JSON object/array from the text
    try:
        json.loads(output)
    except (json.JSONDecodeError, ValueError):
        # Find the first { or [ and extract the matching JSON block
        for start_char, end_char in [('{', '}'), ('[', ']')]:
            start_idx = output.find(start_char)
            if start_idx == -1:
                continue
            # Walk from the end to find the last matching bracket
            end_idx = output.rfind(end_char)
            if end_idx > start_idx:
                candidate = output[start_idx:end_idx + 1]
                try:
                    json.loads(candidate)
                    output = candidate
                    break
                except (json.JSONDecodeError, ValueError):
                    pass

    # Save raw output file
    output_dir = OUTPUTS_DIR / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{agent_name}-report.json"
    output_file.write_text(output)
    APP_DATA.mkdir(parents=True, exist_ok=True)
    (APP_DATA / output_file.name).write_text(output)

    # Parse and merge into shared plan
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        # Fallback: the agent may have written its own JSON file directly
        agent_file = OUTPUTS_DIR / agent_name / f"{agent_name}-report.json"
        fallback_loaded = False
        if agent_file.exists():
            try:
                data = json.loads(agent_file.read_text())
                fallback_loaded = True
                print(f"  📂 {agent_name} output recovered from agent-written file")
                # Also update the reports copy with the proper JSON
                output = agent_file.read_text()
                output_file.write_text(output)
                (APP_DATA / output_file.name).write_text(output)
            except (json.JSONDecodeError, ValueError):
                pass
        if not fallback_loaded:
            print(f"  ⚠️  {agent_name} output was not valid JSON")
            add_agent_update(agent_name, "Processing complete (raw output)", "status", True)
            return output

    plan = load_shared_plan()
    now = datetime.now().isoformat()

    if agent_name == "scout":
        plan["knowledge"]["scout"] = {
            "findings": data.get("findings", []),
            "knowledge_graph": data.get("knowledgeGraph", {}),
            "handoffs": data.get("handoffs", []),
            "updated_at": now,
        }
        findings = data.get("findings", [])
        add_agent_update(agent_name, f"Found {len(findings)} research findings", "status", True)
        for f in findings[:3]:
            add_agent_update(agent_name, f.get("title", "Finding"), "finding", True)
        kg = data.get("knowledgeGraph", {})
        if kg:
            targets = len(kg.get("targets", []))
            compounds = len(kg.get("compounds", []))
            add_agent_update(agent_name, f"Knowledge graph: {targets} targets, {compounds} compounds", "status", True)

    elif agent_name == "connector":
        plan["knowledge"]["connector"] = {
            "contacts": data.get("contacts", []),
            "drafts": [c.get("email_draft", {}) for c in data.get("contacts", []) if c.get("email_draft")],
            "updated_at": now,
        }
        contacts = data.get("contacts", [])
        add_agent_update(agent_name, f"Identified {len(contacts)} outreach targets", "status", True)
        for c in contacts[:3]:
            add_agent_update(agent_name, f"Drafted email to {c.get('name', 'researcher')}", "finding", True)

    elif agent_name == "navigator":
        plan["knowledge"]["navigator"] = {
            "pathways": data.get("regulatoryPathways", {}),
            "updated_at": now,
        }
        pathways = data.get("regulatoryPathways", {})
        if pathways.get("orphanDrugDesignation", {}).get("eligible"):
            add_agent_update(agent_name, "✓ Qualifies for Orphan Drug Designation", "finding", True)
        for ep in pathways.get("expeditedPathways", [])[:2]:
            add_agent_update(agent_name, f"{ep['name']}: {ep.get('eligible', 'assessing')}", "status", True)
        add_agent_update(agent_name, "Regulatory pathway mapping complete", "status", True)

    elif agent_name == "mobilizer":
        plan["knowledge"]["mobilizer"] = {
            "grants": data.get("grantOpportunities", []),
            "fundraisingStrategy": data.get("fundraisingStrategy", {}),
            "advocacyConnections": data.get("advocacyConnections", []),
            "draftApplications": data.get("draftApplications", []),
            "experimentFundingMatches": data.get("experimentFundingMatches", {}),
            "pharmaPartnerships": data.get("pharmaPartnerships", []),
            "entityFormation": data.get("entityFormation", {}),
            "updated_at": now,
        }
        grants = data.get("grantOpportunities", [])
        add_agent_update(agent_name, f"Found {len(grants)} grant opportunities", "status", True)
        for g in grants[:2]:
            add_agent_update(agent_name, f"{g.get('name', 'Grant')}: {g.get('amount', 'TBD')}", "finding", True)
        pharma = data.get("pharmaPartnerships", [])
        if pharma:
            add_agent_update(agent_name, f"Identified {len(pharma)} pharma partnership opportunities", "finding", True)
        entity = data.get("entityFormation", {})
        if entity.get("recommended"):
            add_agent_update(agent_name, f"Entity formation: {entity['recommended']} recommended", "finding", True)

    elif agent_name == "strategist":
        plan["knowledge"]["strategist"] = {
            "roadmap": data.get("weeklyBriefing", {}).get("masterRoadmap", {}),
            "priorities": data.get("weeklyBriefing", {}).get("topPriorities", []),
            "questionsForFamily": data.get("weeklyBriefing", {}).get("questionsForFamily", []),
            "updated_at": now,
        }
        briefing = data.get("weeklyBriefing", {})
        priorities = briefing.get("topPriorities", [])
        add_agent_update(agent_name, f"Identified {len(priorities)} top priorities", "status", True)
        add_agent_update(agent_name, "Weekly briefing ready", "finding", True)
        # Save strategist briefing separately
        briefing_file = OUTPUTS_DIR / "briefings" / f"briefing-{datetime.now().strftime('%Y%m%d')}.json"
        briefing_file.parent.mkdir(parents=True, exist_ok=True)
        briefing_file.write_text(output)
        (APP_DATA / "strategist-briefing.json").write_text(output)

    elif agent_name == "biologist":
        plan["knowledge"]["biologist"] = {
            "targets": data.get("targets", []),
            "disease_mechanism": data.get("disease_mechanism", ""),
            "target_ranking": data.get("target_ranking", []),
            "pathway_map": data.get("pathway_map", {}),
            "handoffs": data.get("handoffs", []),
            "updated_at": now,
        }
        targets = data.get("targets", [])
        add_agent_update(agent_name, f"Identified {len(targets)} therapeutic targets", "status", True)
        for t in targets[:3]:
            add_agent_update(agent_name, f"Target: {t.get('name', '')} (druggability: {t.get('druggability_score', 'N/A')})", "finding", True)

    elif agent_name == "chemist":
        plan["knowledge"]["chemist"] = {
            "screening_summary": data.get("screening_summary", {}),
            "repurposing_candidates": data.get("repurposing_candidates", []),
            "novel_candidates": data.get("novel_candidates", []),
            "candidate_ranking": data.get("candidate_ranking", []),
            "handoffs": data.get("handoffs", []),
            "updated_at": now,
        }
        candidates = data.get("repurposing_candidates", [])
        summary = data.get("screening_summary", {})
        add_agent_update(agent_name, f"Screened {summary.get('total_compounds_found', 0)} compounds, {len(candidates)} repurposing candidates", "status", True)
        for c in candidates[:3]:
            phase = "FDA-approved" if c.get("fda_approved") else f"Phase {c.get('max_phase', '?')}"
            add_agent_update(agent_name, f"{c.get('name', 'Compound')}: {phase}, pChEMBL {c.get('pchembl_value', 'N/A')}", "finding", True)

    elif agent_name == "preclinician":
        plan["knowledge"]["preclinician"] = {
            "candidate_evaluations": data.get("candidate_evaluations", []),
            "experiment_design": data.get("experiment_design", {}),
            "cro_requirements": data.get("cro_requirements", {}),
            "updated_at": now,
        }
        evals = data.get("candidate_evaluations", [])
        add_agent_update(agent_name, f"Evaluated {len(evals)} candidates across ADMET parameters", "status", True)
        for e in evals[:3]:
            add_agent_update(agent_name, f"{e.get('name', 'Candidate')}: {e.get('overall_rating', 'N/A')} — {e.get('recommendation', '')}", "finding", True)
        tiers = data.get("experiment_design", {}).get("tiers", [])
        if tiers:
            add_agent_update(agent_name, f"Designed {len(tiers)} experiment tiers", "finding", True)

    # Handle approval items
    approval_items = data.get("approvalItems", [])
    if approval_items:
        plan["approvals"].extend(approval_items)
        state = load_state()
        approvals = state.get("approvals", state.get("approvalQueue", []))
        approvals.extend(approval_items)
        if "approvals" in state:
            state["approvals"] = approvals
        else:
            state["approvalQueue"] = approvals
        save_state(state)
        print(f"     📋 {len(approval_items)} items added to approval queue")

    # Log the update
    plan["log"].append({
        "agent": agent_name,
        "timestamp": now,
        "summary": f"{agent_name} completed update",
    })

    save_shared_plan(plan)
    return output


def build_prompt(agent_name, shared_plan, iteration):
    """Build prompt with shared plan context and iteration instructions."""
    prompt = (AGENTS_DIR / f"{agent_name}.md").read_text()
    disease = shared_plan["mission"]["disease"]
    priorities = shared_plan["mission"].get("priorities", [])
    journey_stage = shared_plan["mission"].get("journeyStage", "just-diagnosed")
    patient = shared_plan["mission"].get("patient", "")
    location = shared_plan["mission"].get("location", "us")

    # Shared plan context (other agents' findings)
    knowledge_context = ""
    for other_agent, knowledge in shared_plan["knowledge"].items():
        if other_agent != agent_name and knowledge.get("updated_at"):
            knowledge_context += f"\n=== {other_agent.upper()} FINDINGS ===\n"
            knowledge_context += json.dumps(knowledge, indent=2)[:4000]
            knowledge_context += "\n"

    jurisdiction = "FDA (United States)" if location == "us" else "EMA (Europe)" if location == "eu" else "International"

    full_prompt = f"""{prompt}

The disease is: {disease}
Journey stage: {journey_stage}
Patient: {patient if patient else 'not specified'}
Regulatory jurisdiction: {jurisdiction}
Focus areas: {', '.join(priorities) if priorities else 'all'}

ITERATION: {iteration} of {ITERATIONS[agent_name] - 1} (0-indexed)
{"This is your first pass. Do broad initial research." if iteration == 0 else "Build on previous findings and other agents' discoveries. Go deeper on promising leads."}

{f"=== CONTEXT FROM OTHER AGENTS ==={knowledge_context}" if knowledge_context else "No other agent data available yet (you are running in parallel)."}

Output ONLY valid JSON. No markdown fences, no explanation."""

    if agent_name == "preclinician":
        chemist_data = shared_plan["knowledge"].get("chemist", {})
        candidates = chemist_data.get("repurposing_candidates", []) + chemist_data.get("novel_candidates", [])
        if not candidates:
            full_prompt += """

NOTE: The chemist has not identified drug candidates yet. Instead of ADMET evaluation, focus on:
1. Map existing clinical trials for this disease (use clinical-trials tools)
2. Evaluate any existing approved/off-label treatments
3. Design a clinical baseline assessment for the patient
4. Identify what biomarkers and tests should be established now
Output your findings in the standard JSON format with candidate_evaluations (for any existing treatments you find) and experiment_design (for baseline assessments)."""

    return full_prompt


async def run_agent_iteration(agent_name, iteration):
    """Run a single iteration of an agent via claude CLI with MCP tools."""
    model = (DEMO_MODELS if DEMO_MODE else MODELS)[agent_name]
    shared_plan = load_shared_plan()
    prompt = build_prompt(agent_name, shared_plan, iteration)

    iter_label = f"[iter {iteration}]"
    print(f"  🚀 {agent_name.capitalize()} {iter_label} starting (model: {model})...")

    cmd = [
        "claude", "-p", prompt,
        "--model", model,
        "--mcp-config", str(MCP_CONFIG),
        "--dangerously-skip-permissions",
        "--output-format", "text",
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    raw_output = stdout.decode().strip()

    if proc.returncode != 0:
        err = stderr.decode().strip()[:200]
        raise RuntimeError(f"claude CLI failed (rc={proc.returncode}): {err}")

    return raw_output


async def run_agent_loop(agent_name):
    """Run all iterations of an agent."""
    task_descriptions = {
        "scout": "Searching medical literature and clinical trials",
        "connector": "Identifying researchers and drafting outreach",
        "navigator": "Mapping regulatory pathways",
        "mobilizer": "Finding grants and funding opportunities",
        "strategist": "Synthesizing findings and building roadmap",
        "biologist": "Analyzing disease mechanism and identifying drug targets",
        "chemist": "Screening compounds and evaluating drug candidates",
        "preclinician": "Evaluating ADMET profiles and designing experiments",
    }
    update_agent_status(agent_name, "working", task_descriptions.get(agent_name, "Working..."))
    add_agent_update(agent_name, f"Starting {agent_name} agent...")

    num_iterations = (DEMO_ITERATIONS if DEMO_MODE else ITERATIONS)[agent_name]
    try:
        for i in range(num_iterations):
            # Dependency waits: biologist → chemist → preclinician
            if agent_name == "chemist" and i > 0:
                add_agent_update(agent_name, "Waiting for biologist data...")
                for _ in range(12):  # up to 60s
                    plan = load_shared_plan()
                    if plan["knowledge"].get("biologist", {}).get("updated_at"):
                        break
                    await asyncio.sleep(5)

            if agent_name == "preclinician" and i > 0:
                add_agent_update(agent_name, "Waiting for chemist data...")
                for _ in range(12):  # up to 60s
                    plan = load_shared_plan()
                    if plan["knowledge"].get("chemist", {}).get("updated_at"):
                        break
                    await asyncio.sleep(5)

            # Strategist waits on later iterations to let data accumulate
            if agent_name == "strategist" and i > 0:
                add_agent_update(agent_name, "Waiting for more agent data...")
                await asyncio.sleep(5)

            add_agent_update(agent_name, f"Iteration {i+1}/{num_iterations}...")
            raw_output = await run_agent_iteration(agent_name, i)
            merge_output(agent_name, raw_output)
            print(f"  ✅ {agent_name.capitalize()} iteration {i+1}/{num_iterations} complete")

        update_agent_status(agent_name, "complete")
        print(f"  ✅ {agent_name.capitalize()} fully complete")

    except Exception as e:
        update_agent_status(agent_name, "error")
        add_agent_update(agent_name, f"Error: {str(e)[:100]}", "status", False)
        print(f"  ❌ {agent_name.capitalize()} failed: {e}")


def init_shared_plan(mission_data):
    """Initialize shared plan with mission data."""
    plan = load_shared_plan()
    plan["mission"]["disease"] = mission_data.get("disease", "")
    plan["mission"]["priorities"] = mission_data.get("priorities", [])
    plan["mission"]["journeyStage"] = mission_data.get("journeyStage", "just-diagnosed")
    plan["mission"]["patient"] = mission_data.get("patient", "")
    plan["mission"]["location"] = mission_data.get("location", "us")
    plan["log"] = [{
        "agent": "orchestrator",
        "timestamp": datetime.now().isoformat(),
        "summary": f"Mission initialized for {mission_data.get('disease', 'unknown')}",
    }]
    save_shared_plan(plan)


async def main():
    state = load_state()
    mission_data = state.get("mission", {})
    disease = mission_data.get("disease", state.get("disease", ""))
    mission_data["disease"] = disease
    priorities = mission_data.get("priorities", state.get("priorities", []))
    mission_data["priorities"] = priorities

    print(f"\n🌟 Beacon — Parallel Multi-Agent Orchestrator")
    print(f"   Disease: {disease}")
    print(f"   Journey stage: {mission_data.get('journeyStage', 'just-diagnosed')}")
    print(f"   Mode: {'DEMO (fast)' if DEMO_MODE else 'FULL (multi-iteration)'}")
    print(f"   Models: {'Mixed (Opus for Strategist/Chemist, Haiku for others)' if DEMO_MODE else 'Opus (Scout, Navigator, Strategist, Biologist, Chemist) / Haiku (Connector, Mobilizer, Preclinician)'}")
    print(f"   MCP Tools: clinical-trials, biorxiv, chembl, npi-registry, cms-coverage\n")

    APP_DATA.mkdir(parents=True, exist_ok=True)

    # Initialize shared plan
    init_shared_plan(mission_data)

    # Update mission stage
    if "mission" in state:
        state["mission"]["stage"] = "launch"
        save_state(state)

    # Launch ALL agents in parallel
    print("Launching all 8 agents in parallel...")
    await asyncio.gather(
        run_agent_loop("scout"),
        run_agent_loop("connector"),
        run_agent_loop("navigator"),
        run_agent_loop("mobilizer"),
        run_agent_loop("strategist"),
        run_agent_loop("biologist"),
        run_agent_loop("chemist"),
        run_agent_loop("preclinician"),
    )

    # Update mission stage to roadmap
    state = load_state()
    if "mission" in state:
        state["mission"]["stage"] = "roadmap"
    save_state(state)

    print(f"\n🎯 Orchestration complete!")
    print(f"   Outputs: {OUTPUTS_DIR}")
    print(f"   Shared plan: {SHARED_PLAN_FILE}")
    print(f"   App data: {APP_DATA}")
    print(f"   Serve app/ directory and open in browser to view results.")


if __name__ == "__main__":
    asyncio.run(main())
