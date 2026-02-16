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

## User Journey

1. **Welcome** — Enter the diagnosis. Brief intake to understand the family's situation.
2. **Meet Your Team** — See the agents and what each will do.
3. **Launch** — Watch agents activate in real time with live status updates.
4. **Roadmap** — A phased plan from diagnosis to clinical trial, with this week's priorities.
5. **Mission Control** — Ongoing dashboard with approval queue, discovery feed, agent status, drug discovery lab, and community network.

## URL Modes

| URL | Mode | Description |
|-----|------|-------------|
| `beacondemo.vercel.app` | **Live** | Full experience — enters disease, launches Opus 4.6 agents on Railway backend |
| `beacondemo.vercel.app?demo` | **Demo** | Scripted CLN3 Batten Disease simulation with Guide agent narration. No backend needed. |
| `beacondemo.vercel.app?cheap` | **Cheap** | Like live mode but uses Haiku models (~10x cheaper). Good for testing. |
| `beacondemo.vercel.app?disease=Myositis` | **Reconnect** | Skips onboarding, polls existing backend data for the given disease. Zero cost. |

## Tech Stack

- **Frontend:** Single-page React app (CDN-loaded, no build step), deployed on Vercel
- **Backend:** FastAPI server using Anthropic API directly (Opus 4.6 for live, Haiku for cheap/demo), deployed on Railway
- **Agents:** 8 specialized AI agents, each with a domain-specific system prompt
- **MCP Connectors:** ClinicalTrials.gov, ChEMBL, bioRxiv, CMS Coverage, NPI Registry
- **State:** Backend JSON state polled by frontend in real time
- **Deployment:** Vercel (frontend) + Railway (backend)

## Running Locally

```bash
# Frontend
cd app && python3 -m http.server 3333
open http://localhost:3333

# Backend (requires ANTHROPIC_API_KEY)
cd backend && pip install -r requirements.txt
ANTHROPIC_API_KEY=sk-... uvicorn main:app --port 8000

# Demo mode (no backend needed)
open http://localhost:3333?demo

```

## Deploying to Production

### Frontend → Vercel

```bash
cd app
vercel --prod
```

This deploys the `app/` folder as a static site. No build step required.

### Backend → Railway

1. Create a new Railway project and link the `backend/` directory.
2. Set the environment variable `ANTHROPIC_API_KEY` in Railway's dashboard.
3. Railway auto-detects the `Dockerfile` in `backend/` and deploys.
4. Update the backend URL in `app/index.html` (search for `RAILWAY_BACKEND`) to point to your Railway deployment URL.

## Project Structure

```
beacon/
├── agents/           # Agent system prompts (8 agents)
│   ├── scout.md
│   ├── connector.md
│   ├── navigator.md
│   ├── mobilizer.md
│   ├── strategist.md
│   ├── biologist.md
│   ├── chemist.md
│   └── preclinician.md
├── backend/          # FastAPI server (main.py, Dockerfile, requirements.txt)
├── app/              # Single-page app (all 5 stages)
│   ├── index.html
│   ├── audio/        # Generated narration MP3s
│   └── data/         # Agent output files (polled by frontend)
├── orchestrator/     # run.sh, orchestrate.py, state.json
├── scripts/          # Narration generation
├── outputs/          # Agent outputs by type
├── prototypes/       # UI prototypes
├── CLAUDE.md
├── LICENSE
└── README.md
```

## Built With

- [Claude Opus 4.6](https://anthropic.com) — Powers all 8 agents
- [Claude Code](https://claude.com/claude-code) — Agent orchestration, sub-agent management, and primary development tool
- Anthropic Healthcare & Life Sciences MCP connectors (bioRxiv, ClinicalTrials.gov, ChEMBL, CMS Coverage, NPI Registry)

## The Demo Disease

**CLN3 Batten Disease** (Juvenile Neuronal Ceroid Lipofuscinosis) — a devastating rare pediatric neurodegenerative disease affecting ~1 in 100,000 children. There is currently no approved treatment. Beacon demonstrates what's possible when AI works tirelessly on behalf of these families.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

*No family should have to fight alone.*
