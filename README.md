# 🔆 Beacon

**An AI team that works around the clock for rare disease families.**

Beacon isn't a chatbot — it's a team of five AI agents that continuously research treatments, connect with scientists, navigate regulatory pathways, identify funding, and coordinate everything into an actionable plan. Families dealing with a rare disease diagnosis shouldn't have to become experts in everything overnight. Beacon does that work for them.

## The Problem

When a family receives a rare disease diagnosis, they face an impossible task: understanding complex science, finding the right researchers, navigating FDA pathways, securing funding — all while dealing with the emotional weight of the situation. This expertise is locked behind years of specialized knowledge that no single person can acquire fast enough.

## What Beacon Does

Beacon assembles a team of AI agents, each specialized in a critical domain:

| Agent | Role | What They Do |
|-------|------|-------------|
| 🔬 **Scout** | Research Scientist | Searches PubMed, bioRxiv, ClinicalTrials.gov. Identifies promising therapies and drug repurposing opportunities. |
| 🤝 **Connector** | Medical Liaison | Finds and drafts outreach to leading researchers and clinicians. Manages the relationship pipeline. |
| 🧭 **Navigator** | Regulatory Strategist | Maps FDA pathways — orphan drug designation, expedited review, IND filing. Estimates timelines and costs. |
| 💰 **Mobilizer** | Fundraising Coordinator | Identifies NIH grants, foundation funding, and community fundraising strategies. |
| 🎯 **Strategist** | Chief of Staff | Synthesizes all findings into a roadmap. Prioritizes actions. Keeps the family informed. |

## User Journey

1. **Welcome** — Enter the diagnosis. Brief intake to understand the family's situation.
2. **Meet Your Team** — See the five agents and what each will do.
3. **Launch** — Watch agents activate in real time. Compact progress view with email notification opt-in.
4. **Roadmap** — A phased plan from diagnosis to clinical trial, with this week's priorities.
5. **Mission Control** — Ongoing dashboard with approval queue, discovery feed, and agent status.

## Demo Mode

Append `?demo=true` to the URL to run a scripted simulation (~20 seconds) that demonstrates the full flow without running actual agents. Ideal for presentations and the hackathon video.

## Tech Stack

- **Frontend:** Single-page React app (CDN-loaded, no build step)
- **Agents:** Claude Code sub-agents with specialized system prompts
- **Orchestration:** Python orchestrator that launches and coordinates agents
- **Data:** MCP connectors for PubMed, bioRxiv, ClinicalTrials.gov, ChEMBL, CMS Coverage, NPI Registry
- **State:** Shared JSON files polled by the frontend

## Running Locally

```bash
# Serve the app
cd app && python3 -m http.server 8000

# Open in browser
open http://localhost:8000

# For demo mode
open http://localhost:8000?demo=true

# To run actual agents (requires Claude Code CLI)
cd orchestrator && ./run.sh "CLN3 Batten Disease"
```

## Project Structure

```
beacon/
├── agents/           # Agent system prompts
├── orchestrator/     # run.sh, orchestrate.py, state.json
├── app/              # Single-page app (all 5 stages)
│   └── data/         # Agent output files (polled by frontend)
├── outputs/          # Agent outputs by type
└── README.md
```

## Built With

- [Claude Opus 4.6](https://anthropic.com) — Powers all five agents
- [Claude Code](https://claude.com/claude-code) — Agent orchestration and sub-agent management
- Anthropic Healthcare & Life Sciences MCP connectors

## The Demo Disease

**CLN3 Batten Disease** (Juvenile Neuronal Ceroid Lipofuscinosis) — a devastating rare pediatric neurodegenerative disease affecting ~1 in 100,000 children. There is currently no approved treatment. Beacon demonstrates what's possible when AI works tirelessly on behalf of these families.

---

*No family should have to fight alone.*
