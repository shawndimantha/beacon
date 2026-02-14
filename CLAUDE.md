# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Context

Hackathon project for Claude Code + Opus 4.6 hackathon. Main deliverable: **3-minute demo video** of a working prototype. Judges: Claude Code team (Cat Wu, Boris Cherny, Lydia Hallie, Thariq, Shihipar).

### Judging Criteria
1. **Demo (30%)** — Working, impressive, holds up live, genuinely cool
2. **Impact (25%)** — Real-world potential. Who benefits, how much does it matter
3. **Opus 4.6 Use (25%)** — Creative use beyond basic integration. Surfacing surprising capabilities
4. **Depth & Execution (20%)** — Engineering quality, thoughtful refinement, real craft

### Problem Statement Fit
- **Problem Statement Two: Break the Barriers** — unlocking expert knowledge (medical, regulatory, scientific, fundraising) for rare disease families
- **Problem Statement Three: Amplify Human Judgment** — family stays in the loop making strategic decisions while AI handles research, outreach, coordination

## Product Vision

**Beacon** is an AI team (not a chatbot) that works continuously on behalf of a rare disease patient's family. It actively pursues treatment pathways — researching, reaching out to scientists, identifying funding, mapping regulatory paths, coordinating into an actionable, evolving plan.

Family sees a **mission control dashboard** where agents report progress, surface discoveries, and request approval for consequential actions.

### Core UX Principles
- **Agents work in the background, not on demand.** Always running, no prompting needed.
- **Proactive surfacing.** Agents notify when something important happens — new paper, researcher response, grant deadline.
- **Human-in-the-loop for consequential actions.** Emails, applications, public posts require approval. Research/analysis is autonomous.
- **Progressive trust.** Family can grant more autonomy over time for consistently approved action categories.

## Agent Architecture

```
Strategist (main orchestrator)
├── Scout (research & discovery)
├── Connector (outreach & relationships)
├── Navigator (regulatory & legal strategy)
└── Mobilizer (fundraising & community)
```

### Agent 1: Scout (Research & Discovery)
Continuously builds a living knowledge base. Searches PubMed, bioRxiv, ClinicalTrials.gov, patent databases, FDA orphan drug database. Builds knowledge graph (disease mechanism → targets → approaches → research groups → compounds). Monitors new publications, identifies drug repurposing opportunities, tracks competitive/collaborative landscape. Summarizes in plain language with technical depth on demand.

### Agent 2: Connector (Outreach & Relationships)
Identifies, contacts, manages relationships with researchers, clinicians, pharma, other families. Builds target lists from Scout's research, drafts personalized outreach emails demonstrating scientific understanding. Tracks pipeline: drafted → sent (pending approval) → awaiting response → responded → active. Connects with patient advocacy orgs, patient registries, specialized clinicians.

**Requires approval:** Sending outreach emails, sharing patient medical info, making introductions.

### Agent 3: Navigator (Regulatory & Legal Strategy)
Maps regulatory pathway from current state to clinical trial. Determines Orphan Drug Designation eligibility, maps expedited pathways (Breakthrough Therapy, Fast Track, Accelerated Approval, RMAT). Outlines IND process, researches entity formation options (501(c)(3), PBC, LLC), identifies pro-bono legal resources, estimates timelines/costs per phase.

### Agent 4: Mobilizer (Fundraising & Community)
Identifies grant opportunities (NIH/NCATS/NINDS, PCORI, DoD CDMRP, CZI Rare As One, disease-specific foundations). Drafts applications, builds multi-horizon fundraising strategy, connects with patient advocacy orgs, helps build patient registries.

**Requires approval:** Submitting grant applications, publishing campaigns, committing to partnerships.

### Agent 5: Strategist (Orchestrator & Advisor)
Coordinates all agents, maintains master roadmap (diagnosis → research → preclinical → IND → clinical trial), prioritizes across agents, resolves conflicts, generates weekly briefings, adapts strategy to new information, surfaces critical path items.

## Technical Architecture

### File Structure
```
beacon/
├── agents/
│   ├── strategist.md          # Strategist system prompt
│   ├── scout.md               # Scout system prompt
│   ├── connector.md           # Connector system prompt
│   ├── navigator.md           # Navigator system prompt
│   └── mobilizer.md           # Mobilizer system prompt
├── orchestrator/
│   ├── run.sh                 # Main entry point
│   ├── orchestrate.py         # Coordination logic: runs agents, collects outputs, updates state
│   └── state.json             # Shared state file agents read/write
├── dashboard/
│   ├── index.html             # React dashboard
│   └── data/                  # Agent output JSONs the dashboard reads
├── outputs/
│   ├── briefings/             # Strategist weekly briefings
│   ├── emails/                # Connector draft emails for approval
│   ├── grants/                # Mobilizer draft applications
│   └── reports/               # Scout research reports
├── CLAUDE.md
└── README.md
```

### Key Technical Decisions
- **Use Opus 4.6 for all agent reasoning** — judging criterion; every agent uses Opus, not just orchestrator
- **Sub-agents in Claude Code** are the core architecture. Use `claude --dangerously-skip-permissions` or programmatic sub-agent API for parallel execution
- **Web search is critical for Scout** — real research, not mocked data. PubMed, ClinicalTrials.gov, etc.
- **Structured JSON output** from each agent feeds the dashboard. Clear schemas per agent.
- **Dashboard should feel alive** — polling JSON files, showing updates appearing, status changes, progress indicators
- **Emotional design** — warm, hopeful, empowering; not clinical or overwhelming

### Demo Disease
**CLN3 Batten Disease** (Juvenile Neuronal Ceroid Lipofuscinosis) — ~1 in 100,000 births, progressive neurodegeneration in children, active research community, no approved treatment, rich literature, real grant opportunities and advocacy orgs.

## Demo Script (3 minutes)

- **0:00–0:20** — The Problem: child diagnosed with CLN3 Batten Disease, no treatment, parent alone. Show Google/ChatGPT producing passive text walls.
- **0:20–0:50** — Meet Your Team: 5 AI agents working 24/7. Claude Code terminal spinning up agents in parallel, dashboard comes alive.
- **0:50–1:40** — Agents at Work: dashboard populates in real time. Scout finds TRPML1 paper, Connector identifies top researchers + drafts emails, Navigator maps FDA orphan drug pathway, Mobilizer finds CZI grant + drafts LOI, Strategist synthesizes weekly plan. Key visual: months of work in minutes.
- **1:40–2:20** — Human in the Loop: family reviews/approves Connector's email (adds personal note), asks Strategist follow-up on dual-track strategy, approves CZI LOI.
- **2:20–2:50** — Two Weeks Later: Dr. Chen responded, CZI LOI submitted, 2 more papers found, 3 families identified, Orphan Drug app drafted, roadmap updated.
- **2:50–3:00** — Close: "No family should fight a rare disease alone. Beacon gives every family a world-class team."

## Implementation Priorities

### Must-have (Core demo)
1. Multi-agent orchestration — all 5 agents running, producing structured outputs
2. Dashboard displaying agent outputs in real time (or near-real-time with file watching)
3. At least 2 agents producing genuinely impressive outputs (Scout research + Connector outreach)
4. Approval flow for at least one consequential action (reviewing/approving outreach email)
5. Strategist weekly briefing synthesizing all outputs

### Should-have
6. Visual knowledge graph / disease landscape map
7. Real web search powering Scout (not mocked)
8. Before/after comparison: Google/ChatGPT vs Beacon dashboard
9. Interactive drill-down into any agent's domain

### Nice-to-have
10. Notification system / sidebar widget
11. Progressive autonomy visualization
12. Multiple disease support
13. Timeline/Gantt for regulatory pathway
