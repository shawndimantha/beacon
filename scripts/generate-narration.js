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
    text: "Every year, 300 million people worldwide are affected by rare diseases. Most have no approved treatment. When a family gets this diagnosis, they're on their own — navigating science, regulation, and funding with no expertise. Beacon changes that. Built almost entirely with Claude Code and Opus 4.6, Beacon is a team of AI agents that works continuously on a family's behalf.",
  },
  {
    key: 'intake',
    text: "The journey starts with a simple intake — disease name, patient context, location. Behind the scenes, this seeds every agent's system prompt with structured context, so Opus 4.6 can reason about jurisdiction-specific regulatory paths and personalized research strategies from the first query.",
  },
  {
    key: 'agents_activating',
    text: "When the family clicks Launch, Beacon's orchestrator spins up eight Claude Code sub-agents in parallel — each powered by Opus 4.6 with a specialized system prompt. Scout searches bioRxiv, PubMed, and ClinicalTrials.gov through Anthropic's healthcare MCP connectors. Navigator queries the CMS Coverage database and maps FDA orphan drug pathways. Connector cross-references the NPI Registry to verify physician credentials. Each agent writes structured JSON that the dashboard polls in real time.",
  },
  {
    key: 'progress',
    text: "What you're watching is live agent output streaming into the UI. Each progress bar, each status update, each achievement — those are real structured outputs from Opus 4.6 sub-agents writing to shared state files. The orchestrator coordinates task dependencies so agents can hand off findings to each other.",
  },
  {
    key: 'insights',
    text: "These insights are the cross-agent synthesis — Scout found a clinical trial, Navigator checked the regulatory precedent, Mobilizer identified matching grant funding. This research-to-action chain is what sets Beacon apart. Other tools stop at search results. Beacon executes the full pipeline.",
  },
  {
    key: 'approvals',
    text: "Human-in-the-loop for consequential actions. The agent drafts an outreach email to a researcher it identified through PubMed and verified through the NPI Registry. The family reviews and approves. Progressive trust — the AI proposes, the human decides.",
  },
  {
    key: 'lab_overview',
    text: "The Drug Discovery Lab pushes Opus 4.6 further. Three specialized agents — Biologist, Chemist, Preclinician — use the ChEMBL MCP connector to search bioactive compounds, retrieve IC50 values, and evaluate ADMET properties. This is real drug discovery reasoning, not keyword search.",
  },
  {
    key: 'lab_candidates',
    text: "The candidate pipeline ranks compounds by predicted efficacy, safety profile, and clinical precedent — all extracted from ChEMBL's curated database of bioactive molecules. Each agent's reasoning chain is fully traceable.",
  },
  {
    key: 'community_network',
    text: "Beacon's Connector agent builds a family network — matching by geography, disease variant, and treatment stage. Every connection requires family approval. Privacy by design.",
  },
  {
    key: 'community_data',
    text: "When families opt in to share outcomes, Beacon's agents analyze the pooled data — identifying treatment patterns, adverse events, and response rates. For ultra-rare diseases, this community evidence may be the only data that exists.",
  },
  {
    key: 'closing',
    text: "Beacon is a team of AI agents that never stops working — researching, connecting, strategizing, funding — all orchestrated by Claude Code and powered by Opus 4.6. No family should have to fight alone.",
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
