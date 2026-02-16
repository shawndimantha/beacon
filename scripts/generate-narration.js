#!/usr/bin/env node
// Generate narration MP3s from Cartesia TTS API
// Usage: CARTESIA_API_KEY=sk_car_... node scripts/generate-narration.js

const https = require('https');
const fs = require('fs');
const path = require('path');

const API_KEY = process.env.CARTESIA_API_KEY;
if (!API_KEY) {
  console.error('Missing CARTESIA_API_KEY env var');
  process.exit(1);
}

const VOICE_ID = 'e8e5fffb-252c-436d-b842-8879b84445b6';
const OUTPUT_DIR = path.join(__dirname, '..', 'app', 'audio');

const NARRATIONS = [
  {
    key: 'welcome',
    text: "Every year, 300 million people worldwide are affected by rare diseases. Most have no approved treatment. When a family gets this diagnosis, they're on their own — navigating science, regulation, and funding with no expertise. Beacon changes that. Let me walk you through the architecture first. Beacon is a multi-agent system built almost entirely with Claude Code. A FastAPI backend on Railway orchestrates eight specialized Opus 4.6 sub-agents, each with its own system prompt and tool access. The agents communicate through a shared state file — structured JSON that the React frontend polls every two seconds from a Vercel deployment. The agents use Anthropic's healthcare MCP connectors — ClinicalTrials.gov, ChEMBL, bioRxiv, the NPI Registry, and the CMS Coverage database — so every data point is sourced from real medical infrastructure, not hallucinated.",
  },
  {
    key: 'intake',
    text: "The journey starts with a simple intake — disease name, patient context, location. Behind the scenes, this seeds every agent's system prompt with structured context, so Opus 4.6 can reason about jurisdiction-specific regulatory paths and personalized research strategies from the first query.",
  },
  {
    key: 'agents_activating',
    text: "When the family clicks Launch, the orchestrator spins up all eight agents in parallel via asyncio. Three of them — Scout, Navigator, and Strategist — run on Opus 4.6 for deep scientific reasoning. The others use Haiku for speed. Each agent runs a multi-turn conversation loop with up to 15 tool calls per iteration. You can see the tool call counts updating live on each agent's status card — that's Opus 4.6's agentic search capability in action, leading all benchmarks on BrowseComp and DeepSearchQA.",
  },
  {
    key: 'progress',
    text: "What you're watching is live agent output streaming into the UI. Each progress bar, each status update, each achievement — those are real structured outputs from Opus 4.6 sub-agents writing to shared state. The orchestrator coordinates task dependencies so agents can hand off findings to each other. Notice the Opus 4.6 Multidisciplinary Reasoning panel — Opus 4.6 scored two-x better than its predecessor on computational biology, structural biology, and organic chemistry. Our Biologist, Chemist, and Preclinician agents chain these capabilities together: targets to compounds to safety profiles.",
  },
  {
    key: 'insights',
    text: "These insights are the cross-agent synthesis. When all eight agents complete, we trigger an extended context synthesis pass — concatenating every agent's full output into a single Opus 4.6 call. With the one-million-token context window and 76% eight-needle retrieval accuracy, Opus 4.6 produces a unified family briefing that no single agent could create alone. This is the research-to-action chain that sets Beacon apart.",
  },
  {
    key: 'approvals',
    text: "Human-in-the-loop for consequential actions. The agent drafts an outreach email to a researcher it identified through PubMed and verified through the NPI Registry. The family reviews and approves. Progressive trust — the AI proposes, the human decides.",
  },
  {
    key: 'lab_overview',
    text: "The Drug Discovery Lab uses ChEMBL MCP connectors for real compound screening and ADMET evaluation. When agents complete, this tab populates with live targets, candidates, and safety profiles for the specific disease entered. The 3D protein structures come from AlphaFold.",
  },
  {
    key: 'community_network',
    text: "Community features — patient matching, data commons, and clinical trial planning — are coming soon. The current view shows our design direction.",
  },
  {
    key: 'closing',
    text: "To recap the Opus 4.6 showcase — multidisciplinary scientific reasoning across biology, chemistry, and pharmacology. Agentic tool use with live MCP connectors to real medical databases. Extended context synthesis across one million tokens from eight parallel agents. And all of it orchestrated by Claude Code. Beacon is a team of AI agents that never stops working. No family should have to fight alone.",
  },
];

async function generateClip(narration) {
  const outPath = path.join(OUTPUT_DIR, `${narration.key}.mp3`);
  if (fs.existsSync(outPath)) {
    console.log(`  [skip] ${narration.key}.mp3 already exists`);
    return;
  }

  const body = JSON.stringify({
    model_id: 'sonic-2',
    transcript: narration.text,
    voice: { mode: 'id', id: VOICE_ID },
    output_format: { container: 'mp3', encoding: 'mp3', sample_rate: 44100 },
  });

  return new Promise((resolve, reject) => {
    const req = https.request(
      {
        hostname: 'api.cartesia.ai',
        path: '/tts/bytes',
        method: 'POST',
        headers: {
          'Cartesia-Version': '2024-06-10',
          'X-API-Key': API_KEY,
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(body),
        },
      },
      (res) => {
        if (res.statusCode !== 200) {
          let data = '';
          res.on('data', (c) => (data += c));
          res.on('end', () => {
            console.error(`  [error] ${narration.key}: HTTP ${res.statusCode} — ${data}`);
            reject(new Error(`HTTP ${res.statusCode}`));
          });
          return;
        }
        const chunks = [];
        res.on('data', (c) => chunks.push(c));
        res.on('end', () => {
          fs.writeFileSync(outPath, Buffer.concat(chunks));
          console.log(`  [ok] ${narration.key}.mp3 (${(Buffer.concat(chunks).length / 1024).toFixed(0)} KB)`);
          resolve();
        });
      }
    );
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

(async () => {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  console.log(`Generating ${NARRATIONS.length} narration clips...`);
  for (const n of NARRATIONS) {
    await generateClip(n);
  }
  console.log('Done!');
})();
