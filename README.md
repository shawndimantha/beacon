# 🔆 Beacon

**An AI team that works around the clock for rare disease families.**

Beacon isn't a chatbot — it's a team of AI agents that continuously research treatments, connect with scientists, navigate regulatory pathways, identify funding, and coordinate everything into an actionable plan. Built almost entirely with Claude Code and Opus 4.6.

**Live demo:** [beacondemo.vercel.app](https://beacondemo.vercel.app)

## The Problem

When a family receives a rare disease diagnosis, they face an impossible task: understanding complex science, finding the right researchers, navigating FDA pathways, securing funding — all while dealing with the emotional weight of the situation. This expertise is locked behind years of specialized knowledge that no single person can acquire fast enough.

## What Beacon Does

Beacon assembles a team of AI agents, each specialized in a critical domain:

| Agent | Role | What They Do |
|-------|------|-------------|
| 🔬 **Scout** | Research Scientist | Searches PubMed, bioRxiv, ClinicalTrials.gov. Identifies promising therapies and drug repurposing opportunities. Extracts and synthesizes case reports. |
| 🤝 **Connector** | Medical Liaison | Finds researchers and clinicians, verifies credentials via NPI Registry, drafts personalized outreach. |
| 🧭 **Navigator** | Regulatory Strategist | Maps FDA pathways — orphan drug designation, expedited review, IND filing. Queries CMS Coverage database. |
| 💰 **Mobilizer** | Fundraising Coordinator | Identifies NIH grants, foundation funding, and community fundraising strategies. |
| 🎯 **Strategist** | Chief of Staff | Synthesizes all findings into a roadmap. Prioritizes actions. Coordinates cross-agent handoffs. |
| 🧬 **Biologist** | Drug Discovery | Identifies protein targets and disease mechanisms. Searches ChEMBL for bioactive compounds. |
| ⚗️ **Chemist** | Compound Screening | Retrieves IC50/EC50 values, evaluates binding affinity, screens compound libraries via ChEMBL. |
| 🧪 **Preclinician** | Safety & ADMET | Evaluates pharmacokinetic properties, safety profiles, and clinical precedent for candidate compounds. |
| 💡 **Guide** | Contextual Narrator | Demo mode: narrates the hackathon presentation. Product mode: contextual tips based on current view. |

## User Journey

1. **Welcome** — Enter the diagnosis. Brief intake to understand the family's situation.
2. **Meet Your Team** — See the agents and what each will do.
3. **Launch** — Watch agents activate in real time with live status updates.
4. **Roadmap** — A phased plan from diagnosis to clinical trial, with this week's priorities.
5. **Mission Control** — Ongoing dashboard with approval queue, discovery feed, agent status, drug discovery lab, and community network.

## Demo Mode

Append `?demo=true` to the URL to run a scripted simulation that demonstrates the full flow without running actual agents. The Guide agent narrates the experience with auto-playing voiceover and subtitles.

## Tech Stack

- **Frontend:** Single-page React app (CDN-loaded, no build step)
- **Agents:** 9 Claude Code sub-agents, each with a specialized system prompt (Opus 4.6)
- **Orchestration:** Python orchestrator that launches and coordinates agents in parallel
- **MCP Connectors:** bioRxiv, ClinicalTrials.gov, ChEMBL, CMS Coverage, NPI Registry
- **Narration:** Cartesia TTS (Sonic 2) for Guide agent voiceover
- **State:** Shared JSON files polled by the frontend in real time
- **Deployment:** Vercel (static)

## Running Locally

```bash
# Serve the app
cd app && python3 -m http.server 3333

# Open in browser
open http://localhost:3333

# For demo mode
open http://localhost:3333?demo=true

# To run actual agents (requires Claude Code CLI)
cd orchestrator && ./run.sh "CLN3 Batten Disease"

# To regenerate narration audio
CARTESIA_API_KEY=... node scripts/generate-narration.js
```

## Project Structure

```
beacon/
├── agents/           # Agent system prompts (9 agents)
│   ├── scout.md
│   ├── connector.md
│   ├── navigator.md
│   ├── mobilizer.md
│   ├── strategist.md
│   ├── biologist.md
│   ├── chemist.md
│   ├── preclinician.md
│   └── guide.md
├── app/              # Single-page app (all 5 stages)
│   ├── index.html
│   ├── audio/        # Generated narration MP3s
│   └── data/         # Agent output files (polled by frontend)
├── orchestrator/     # run.sh, orchestrate.py, state.json
├── scripts/          # Narration generation script
├── outputs/          # Agent outputs by type
├── prototypes/       # UI prototypes
├── CLAUDE.md
├── LICENSE
└── README.md
```

## Built With

- [Claude Opus 4.6](https://anthropic.com) — Powers all 9 agents
- [Claude Code](https://claude.com/claude-code) — Agent orchestration, sub-agent management, and primary development tool
- Anthropic Healthcare & Life Sciences MCP connectors (bioRxiv, ClinicalTrials.gov, ChEMBL, CMS Coverage, NPI Registry)
- [Cartesia Sonic 2](https://cartesia.ai) — TTS for Guide agent narration

## The Demo Disease

**CLN3 Batten Disease** (Juvenile Neuronal Ceroid Lipofuscinosis) — a devastating rare pediatric neurodegenerative disease affecting ~1 in 100,000 children. There is currently no approved treatment. Beacon demonstrates what's possible when AI works tirelessly on behalf of these families.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

*No family should have to fight alone.*
