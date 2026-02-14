#!/usr/bin/env python3
"""Beacon — Multi-agent orchestrator. Runs all 5 agents and populates dashboard."""

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
DASHBOARD_DATA = ROOT / "dashboard" / "data"

def load_state():
    with open(STATE_FILE) as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
    # Mirror to dashboard
    with open(DASHBOARD_DATA / "state.json", "w") as f:
        json.dump(state, f, indent=2)

def update_agent_status(agent_name, status):
    state = load_state()
    state["agents"][agent_name]["status"] = status
    state["agents"][agent_name]["lastRun"] = datetime.now().isoformat()
    save_state(state)

async def run_agent(agent_name, prompt_file, output_file, extra_context=""):
    """Run a single agent via claude CLI."""
    print(f"  🚀 {agent_name.capitalize()} starting...")
    update_agent_status(agent_name, "running")

    prompt = prompt_file.read_text()
    state = load_state()
    disease = state["disease"]
    patient_name = state["patient"]["name"]

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
            "--output-format", "json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        output = stdout.decode().strip()
        # Write raw output
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(output)

        # Copy to dashboard
        dashboard_file = DASHBOARD_DATA / output_file.name
        dashboard_file.write_text(output)

        update_agent_status(agent_name, "complete")
        print(f"  ✅ {agent_name.capitalize()} complete → {output_file.name}")

        # Extract approval items and add to state
        try:
            data = json.loads(output)
            approval_items = data.get("approvalItems", [])
            if approval_items:
                state = load_state()
                state["approvalQueue"].extend(approval_items)
                save_state(state)
                print(f"     📋 {len(approval_items)} items added to approval queue")
        except json.JSONDecodeError:
            print(f"  ⚠️  {agent_name} output was not valid JSON")

    except Exception as e:
        update_agent_status(agent_name, "error")
        print(f"  ❌ {agent_name.capitalize()} failed: {e}")

async def main():
    print(f"\n🌟 Beacon — Multi-Agent Orchestrator")
    state = load_state()
    print(f"   Disease: {state['disease']}")
    print(f"   Patient: {state['patient']['name']}\n")

    # Phase 1: Scout (others depend on its output)
    print("Phase 1: Research & Discovery")
    scout_output = OUTPUTS_DIR / "reports" / "scout-report.json"
    await run_agent(
        "scout",
        AGENTS_DIR / "scout.md",
        scout_output,
    )

    # Read scout output for context
    scout_context = ""
    if scout_output.exists():
        scout_context = f"Scout's research findings:\n{scout_output.read_text()[:8000]}"

    # Phase 2: Connector, Navigator, Mobilizer in parallel
    print("\nPhase 2: Outreach, Regulatory, Fundraising (parallel)")
    await asyncio.gather(
        run_agent(
            "connector",
            AGENTS_DIR / "connector.md",
            OUTPUTS_DIR / "reports" / "connector-report.json",
            extra_context=scout_context,
        ),
        run_agent(
            "navigator",
            AGENTS_DIR / "navigator.md",
            OUTPUTS_DIR / "reports" / "navigator-report.json",
            extra_context=scout_context,
        ),
        run_agent(
            "mobilizer",
            AGENTS_DIR / "mobilizer.md",
            OUTPUTS_DIR / "reports" / "mobilizer-report.json",
            extra_context=scout_context,
        ),
    )

    # Phase 3: Strategist (reads all outputs)
    print("\nPhase 3: Strategy & Synthesis")
    all_context_parts = []
    for name in ["scout", "connector", "navigator", "mobilizer"]:
        report = OUTPUTS_DIR / "reports" / f"{name}-report.json"
        if report.exists():
            all_context_parts.append(f"=== {name.upper()} REPORT ===\n{report.read_text()[:6000]}")

    strategist_context = "\n\n".join(all_context_parts)
    briefing_file = OUTPUTS_DIR / "briefings" / f"briefing-{datetime.now().strftime('%Y%m%d')}.json"
    await run_agent(
        "strategist",
        AGENTS_DIR / "strategist.md",
        briefing_file,
        extra_context=strategist_context,
    )
    # Also copy as latest briefing for dashboard
    if briefing_file.exists():
        (DASHBOARD_DATA / "strategist-briefing.json").write_text(briefing_file.read_text())

    # Final state copy
    save_state(load_state())

    print(f"\n🎯 Orchestration complete!")
    print(f"   Outputs: {OUTPUTS_DIR}")
    print(f"   Dashboard data: {DASHBOARD_DATA}")
    print(f"   Open dashboard/index.html in a browser to view results.")

if __name__ == "__main__":
    asyncio.run(main())
