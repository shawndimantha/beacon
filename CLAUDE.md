# Beacon — Claude Code Project Brief

## Context

This is a hackathon project for a Claude Code + Opus 4.6 hackathon. The main deliverable is a **3-minute demo video** showing a working prototype. The judges are the Claude Code team (Cat Wu, Boris Cherny, Lydia Hallie, Thariq, Shihipar).

### Judging Criteria
1. **Demo (30%)** — Is this a working, impressive demo? Does it hold up live? Is it genuinely cool to watch?
2. **Impact (25%)** — Real-world potential. Who benefits, how much does it matter?
3. **Opus 4.6 Use (25%)** — Creative use of Opus 4.6. Beyond basic integration. Surfacing surprising capabilities.
4. **Depth & Execution (20%)** — Engineering quality. Thoughtful refinement. Real craft.

### Problem Statement Fit
This project targets **Problem Statement Two: Break the Barriers** — taking expert knowledge locked behind medical, regulatory, scientific, and fundraising expertise and putting it in the hands of a rare disease patient's family member who desperately needs it.

It also strongly fits **Problem Statement Three: Amplify Human Judgment** — the family member remains in the loop, making strategic decisions, while the AI team handles research, outreach, and coordination at a pace no individual could achieve.

---

## Product Vision

**Beacon** is an AI team — not a chatbot — that works continuously on behalf of a rare disease patient's family. It doesn't just produce a research summary; it actively pursues treatment pathways by researching, reaching out to scientists, identifying funding, mapping regulatory paths, and coordinating all of this into an actionable, evolving plan.

### Core UX Principles
- **Agents work in the background, not on demand.** The family member doesn't have to prompt anything. The agents are always running.
- **Proactive surfacing.** Agents tap the family member on the shoulder when something important happens — a new paper, a researcher who responded, a grant deadline approaching.
- **Human-in-the-loop for consequential actions.** Sending emails, submitting applications, making public posts — all require family member approval. Research and analysis happen autonomously.
- **Progressive trust.** Over time, the family member can grant more autonomy to agents for categories of actions they've consistently approved.
- **Emotional design.** Every screen should feel warm, hopeful, and empowering. This person is going through the hardest thing in their life. The UI should feel like a steady hand on their shoulder, not a cold clinical tool.

---

## The User Journey (5 Stages)

This is the heart of the product. The user experience is a **narrative arc** — from overwhelm to empowerment. Each stage has a distinct emotional tone and visual design.

---

### Stage 1: Welcome & Intake (The Warm Hand)

**Emotional tone:** Calm, warm, human. "You're not alone anymore."

**What the user sees:**

A clean, minimal welcome page. No dashboards, no complexity. Just warmth.

**After entering the disease name**, a brief guided intake (conversational, not a form):
- Who is the patient? (your child, yourself, a family member)
- How old are they?
- When was the diagnosis?
- Where are you located? (for regulatory jurisdiction — FDA vs EMA vs other)
- Do you have a care team currently? (neurologist, geneticist, etc.)
- What matters most to you right now? (understanding the disease / finding treatment options / connecting with other families / all of the above)

**Design notes:**
- Large, readable typography. Lots of whitespace.
- Warm color palette — soft blues, warm whites, gentle amber accents. NOT clinical white or sterile.
- No jargon. Every question has a brief, kind explanation of why it's being asked.
- A small "lighthouse" or beacon icon/animation as the brand mark — a light in the dark.
- The intake should feel like talking to a compassionate, knowledgeable friend — not filling out a medical form.

---

### Stage 2: Meet Your Team (The Introduction)

**Emotional tone:** Reassuring, empowering. "Here's who's going to help you."

**Triggered:** Immediately after intake is complete.

Agent team introduced one by one:
- Scout — Your Research Scientist
- Connector — Your Medical Liaison
- Navigator — Your Regulatory Strategist
- Mobilizer — Your Fundraising Coordinator
- Strategist — Your Chief of Staff

---

### Stage 3: Agents Activating (The Launch Sequence)

**Emotional tone:** Momentum, energy, hope. "Your team is on it."

**Triggered:** Immediately after "Start the mission" is clicked. This is where the actual Claude Code sub-agents spin up.

A **live status screen** showing each agent activating and beginning their first tasks. This is the "wow" moment in the demo.

Each Claude Code sub-agent writes structured status updates to a shared JSON file as it works. The dashboard polls this file and renders updates in real time.

---

### Stage 4: Your Roadmap (The Plan Emerges)

**Emotional tone:** Clarity, direction, hope. "Here's the path forward."

**Triggered:** When the Strategist has synthesized initial findings from all agents.

A **roadmap view** showing the journey from diagnosis to treatment, with milestones, timelines, and the first concrete action items.

---

### Stage 5: Mission Control (The Dashboard)

**Emotional tone:** Empowered, in-control, active. "Your team is working. Here's what's happening."

**This is the persistent view** the family member returns to every time they open Beacon.

Key sections:
1. **Needs Your Attention** — Items requiring human approval or decision.
2. **Recent Discoveries** — Feed of significant findings from all agents.
3. **Agent Status** — What each agent is doing right now.
4. **Roadmap Progress** — Visual snapshot of mission progress.
5. **Ask your team** — Chat input routed to the right agent.

---

## Agent Architecture

### Agent 1: Scout (Research & Discovery)
Continuously builds a living knowledge base. Searches PubMed, bioRxiv, ClinicalTrials.gov, patent databases, FDA orphan drug database. Builds knowledge graph. Monitors new publications. Identifies drug repurposing opportunities. Summarizes in plain language.

### Agent 2: Connector (Outreach & Relationships)
Identifies, contacts, manages relationships with researchers, clinicians, pharma, other families. Drafts personalized outreach emails. Tracks outreach pipeline. **Requires approval** for sending emails, sharing patient info.

### Agent 3: Navigator (Regulatory & Legal Strategy)
Maps regulatory pathway from current state to clinical trial. Orphan Drug Designation, expedited pathways, IND process, entity formation, pro-bono legal resources, timeline/cost estimates.

### Agent 4: Mobilizer (Fundraising & Community)
Identifies grants (NIH, CZI, disease-specific foundations). Drafts applications. Multi-horizon fundraising strategy. Patient advocacy connections. **Requires approval** for submitting applications.

### Agent 5: Strategist (Orchestrator & Advisor)
Coordinates all agents. Master roadmap. Weekly briefings. Prioritization. Conflict resolution. Strategy adaptation.

---

## Anthropic Healthcare & Life Sciences Connectors

Beacon should leverage Anthropic's native healthcare and life sciences connectors:

**For Scout:** PubMed, bioRxiv & medRxiv, ClinicalTrials.gov, Open Targets, ChEMBL, ToolUniverse
**For Connector:** PubMed, ClinicalTrials.gov, NPI Registry
**For Navigator:** CMS Coverage Database, ICD-10 codes, ClinicalTrials.gov
**For Mobilizer:** ClinicalTrials.gov, PubMed
**For Patient:** Apple Health / Android Health Connect, HealthEx / Function

---

## Technical Architecture

### Frontend: Single React App
The entire user journey (Stages 1-5) lives in one app with state-based transitions.

### Backend: Claude Code Sub-Agent Orchestration
Each agent is a Claude Code sub-agent with specialized system prompt, web search access, and structured JSON output.

### State & Communication
Agents write to a shared JSON state file that the frontend polls.

### File Structure
```
beacon/
├── agents/           # Agent system prompts
├── orchestrator/     # run.sh, orchestrate.py, state.json
├── app/              # Single-page app — all 5 stages
├── outputs/          # Agent outputs by type
├── CLAUDE.md
└── README.md
```

### Demo Disease
**CLN3 Batten Disease** (Juvenile Neuronal Ceroid Lipofuscinosis) as test case.

---

## Demo Script (3 minutes)

- **0:00-0:15** — Stage 1: Welcome, type diagnosis, brief intake
- **0:15-0:30** — Stage 2: Meet your team, click "Start the mission"
- **0:30-1:15** — Stage 3: Live agent activation (the wow moment)
- **1:15-1:35** — Stage 4: Roadmap materializes
- **1:35-2:20** — Stage 5: Mission control, approve outreach email
- **2:20-2:45** — "Two weeks later" evolved dashboard
- **2:45-3:00** — Close: "No family should have to fight alone."

---

## Implementation Priorities

### Must-have
1. Welcome page with disease input and brief intake (Stage 1)
2. Team introduction screen (Stage 2)
3. Live agent activation with streaming status updates (Stage 3) — centerpiece
4. Basic roadmap view (Stage 4)
5. Mission Control dashboard with approval queue, discovery feed, agent status (Stage 5)
6. At least one working approval flow (outreach email review)
7. Multi-agent orchestration — all 5 agents running with real web search

### Should-have
8. Smooth animated transitions between stages
9. Real web search results powering Scout
10. Interactive roadmap with clickable milestones
11. Chat input routing questions to agents
12. "Two weeks later" state showing evolution

### Nice-to-have
13. Knowledge graph visualization
14. Outreach pipeline tracker
15. Notification/badge system
16. Sound design for status updates
