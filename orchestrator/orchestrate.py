#!/usr/bin/env python3
"""Beacon — Multi-agent orchestrator. Runs all 5 agents and populates the app."""

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "orchestrator" / "state.json"
AGENTS_DIR = ROOT / "agents"
OUTPUTS_DIR = ROOT / "outputs"
APP_DATA = ROOT / "app" / "data"

def load_state():
    with open(STATE_FILE) as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
    APP_DATA.mkdir(parents=True, exist_ok=True)
    with open(APP_DATA / "state.json", "w") as f:
        json.dump(state, f, indent=2)

def add_agent_update(agent_name, message, update_type="status", completed=False):
    """Add a streaming status update for an agent (visible in launch sequence)."""
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

async def run_agent(agent_name, prompt_file, output_file, extra_context=""):
    """Run a single agent via claude CLI."""
    print(f"  🚀 {agent_name.capitalize()} starting...")

    # Set initial status with task description
    task_descriptions = {
        "scout": "Searching medical literature and clinical trials",
        "connector": "Identifying researchers and drafting outreach",
        "navigator": "Mapping regulatory pathways",
        "mobilizer": "Finding grants and funding opportunities",
        "strategist": "Synthesizing findings and building roadmap",
    }
    update_agent_status(agent_name, "working", task_descriptions.get(agent_name, "Working..."))
    add_agent_update(agent_name, f"Starting {agent_name} agent...")

    prompt = prompt_file.read_text()
    state = load_state()
    disease = state["mission"]["disease"] if "mission" in state else state.get("disease", "")
    patient = state["mission"]["patient"] if "mission" in state else state.get("patient", {})
    patient_name = patient.get("name", "the patient")

    full_prompt = f"""{prompt}

The disease is: {disease}
The patient's name is: {patient_name}

{extra_context}

Output ONLY valid JSON. No markdown fences, no explanation."""

    try:
        proc = await asyncio.create_subprocess_exec(
            "claude", "-p", full_prompt,
            "--model", "claude-opus-4-6",
            "--dangerously-skip-permissions",
            "--output-format", "text",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        raw_output = stdout.decode().strip()

        # Try to extract JSON from the output
        # Handle: raw JSON, ```json fences, or {"result":"..."} envelope
        output = raw_output
        try:
            parsed = json.loads(raw_output)
            # Check if it's a Claude CLI envelope
            if "result" in parsed and isinstance(parsed["result"], str):
                output = parsed["result"]
                # The result itself might contain JSON
                try:
                    json.loads(output)
                except json.JSONDecodeError:
                    pass  # It's text, not JSON - we'll handle below
        except json.JSONDecodeError:
            pass

        # Strip markdown fences if present
        if "```json" in output:
            output = output.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in output:
            output = output.split("```", 1)[1].split("```", 1)[0].strip()

        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(output)

        # Copy to app data
        APP_DATA.mkdir(parents=True, exist_ok=True)
        (APP_DATA / output_file.name).write_text(output)

        # Parse output and generate status updates
        try:
            data = json.loads(output)

            # Generate meaningful status updates from the output
            if agent_name == "scout":
                findings = data.get("findings", [])
                add_agent_update(agent_name, f"Found {len(findings)} research findings", "status", True)
                for f in findings[:3]:
                    add_agent_update(agent_name, f["title"], "finding", True)
                if data.get("knowledgeGraph"):
                    kg = data["knowledgeGraph"]
                    targets = len(kg.get("targets", []))
                    compounds = len(kg.get("compounds", []))
                    add_agent_update(agent_name, f"Knowledge graph: {targets} targets, {compounds} compounds mapped", "status", True)

            elif agent_name == "connector":
                contacts = data.get("contacts", [])
                add_agent_update(agent_name, f"Identified {len(contacts)} outreach targets", "status", True)
                for c in contacts[:3]:
                    add_agent_update(agent_name, f"Drafted email to {c.get('name', 'researcher')}", "finding", True)

            elif agent_name == "navigator":
                pathways = data.get("regulatoryPathways", {})
                if pathways.get("orphanDrugDesignation", {}).get("eligible"):
                    add_agent_update(agent_name, "✓ Qualifies for Orphan Drug Designation", "finding", True)
                expedited = pathways.get("expeditedPathways", [])
                for ep in expedited[:2]:
                    add_agent_update(agent_name, f"{ep['name']}: {ep.get('eligible', 'assessing')}", "status", True)
                add_agent_update(agent_name, "Regulatory pathway mapping complete", "status", True)

            elif agent_name == "mobilizer":
                grants = data.get("grantOpportunities", [])
                add_agent_update(agent_name, f"Found {len(grants)} grant opportunities", "status", True)
                for g in grants[:2]:
                    add_agent_update(agent_name, f"{g.get('name', 'Grant')}: {g.get('amount', 'TBD')}", "finding", True)

            elif agent_name == "strategist":
                briefing = data.get("weeklyBriefing", {})
                priorities = briefing.get("topPriorities", [])
                add_agent_update(agent_name, f"Identified {len(priorities)} top priorities", "status", True)
                add_agent_update(agent_name, "Weekly briefing ready", "finding", True)

            # Add approval items to state
            approval_items = data.get("approvalItems", [])
            if approval_items:
                state = load_state()
                approvals = state.get("approvals", state.get("approvalQueue", []))
                approvals.extend(approval_items)
                if "approvals" in state:
                    state["approvals"] = approvals
                else:
                    state["approvalQueue"] = approvals
                save_state(state)
                print(f"     📋 {len(approval_items)} items added to approval queue")

        except json.JSONDecodeError:
            print(f"  ⚠️  {agent_name} output was not valid JSON")
            add_agent_update(agent_name, "Processing complete (raw output)", "status", True)

        update_agent_status(agent_name, "complete")
        print(f"  ✅ {agent_name.capitalize()} complete → {output_file.name}")

    except Exception as e:
        update_agent_status(agent_name, "error")
        add_agent_update(agent_name, f"Error: {str(e)[:100]}", "status", False)
        print(f"  ❌ {agent_name.capitalize()} failed: {e}")

async def main():
    state = load_state()
    disease = state["mission"]["disease"] if "mission" in state else state.get("disease", "")
    patient = state["mission"]["patient"] if "mission" in state else state.get("patient", {})

    print(f"\n🌟 Beacon — Multi-Agent Orchestrator")
    print(f"   Disease: {disease}")
    print(f"   Patient: {patient.get('name', 'Unknown')}\n")

    # Ensure app/data exists
    APP_DATA.mkdir(parents=True, exist_ok=True)

    # Update mission stage
    if "mission" in state:
        state["mission"]["stage"] = "launch"
        save_state(state)

    # Phase 1: Scout (others depend on its output)
    print("Phase 1: Research & Discovery")
    add_agent_update("scout", "Searching PubMed for disease literature...")
    add_agent_update("scout", "Scanning ClinicalTrials.gov...")
    add_agent_update("scout", "Checking bioRxiv for preprints...")

    scout_output = OUTPUTS_DIR / "reports" / "scout-report.json"
    await run_agent("scout", AGENTS_DIR / "scout.md", scout_output)

    # Read scout output for context
    scout_context = ""
    if scout_output.exists():
        scout_context = f"Scout's research findings:\n{scout_output.read_text()[:8000]}"

    # Phase 2: Connector, Navigator, Mobilizer in parallel
    print("\nPhase 2: Outreach, Regulatory, Fundraising (parallel)")
    add_agent_update("connector", "Reading Scout's research findings...")
    add_agent_update("connector", "Identifying top researchers...")
    add_agent_update("navigator", "Checking orphan drug eligibility...")
    add_agent_update("navigator", "Analyzing FDA expedited pathways...")
    add_agent_update("mobilizer", "Scanning active grant opportunities...")
    add_agent_update("mobilizer", "Identifying patient communities...")

    await asyncio.gather(
        run_agent("connector", AGENTS_DIR / "connector.md",
                  OUTPUTS_DIR / "reports" / "connector-report.json", scout_context),
        run_agent("navigator", AGENTS_DIR / "navigator.md",
                  OUTPUTS_DIR / "reports" / "navigator-report.json", scout_context),
        run_agent("mobilizer", AGENTS_DIR / "mobilizer.md",
                  OUTPUTS_DIR / "reports" / "mobilizer-report.json", scout_context),
    )

    # Phase 3: Strategist (reads all outputs)
    print("\nPhase 3: Strategy & Synthesis")
    add_agent_update("strategist", "Reading all agent reports...")
    add_agent_update("strategist", "Building your roadmap...")

    all_context_parts = []
    for name in ["scout", "connector", "navigator", "mobilizer"]:
        report = OUTPUTS_DIR / "reports" / f"{name}-report.json"
        if report.exists():
            all_context_parts.append(f"=== {name.upper()} REPORT ===\n{report.read_text()[:6000]}")

    strategist_context = "\n\n".join(all_context_parts)
    briefing_file = OUTPUTS_DIR / "briefings" / f"briefing-{datetime.now().strftime('%Y%m%d')}.json"
    await run_agent("strategist", AGENTS_DIR / "strategist.md", briefing_file, strategist_context)

    if briefing_file.exists():
        (APP_DATA / "strategist-briefing.json").write_text(briefing_file.read_text())

    # Update mission stage to roadmap
    state = load_state()
    if "mission" in state:
        state["mission"]["stage"] = "roadmap"
    save_state(state)

    print(f"\n🎯 Orchestration complete!")
    print(f"   Outputs: {OUTPUTS_DIR}")
    print(f"   App data: {APP_DATA}")
    print(f"   Serve app/ directory and open in browser to view results.")

if __name__ == "__main__":
    asyncio.run(main())
