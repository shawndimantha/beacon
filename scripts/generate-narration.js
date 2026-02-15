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
    text: "Welcome to Beacon. When your child is diagnosed with a rare disease, the world gets very quiet. Beacon changes that. Let's get started.",
  },
  {
    key: 'intake',
    text: "Tell us a little about your situation. This helps your team know exactly where to focus — no detail is shared without your permission.",
  },
  {
    key: 'agents_activating',
    text: "Meet your team — eight AI agents, each with a specialty, all working for you right now. Scout is searching the latest research. Connector is finding families and clinicians. Navigator is mapping the regulatory path. Watch them work.",
  },
  {
    key: 'progress',
    text: "As your agents make discoveries, you'll see progress here. Each breakthrough — a new clinical trial, a promising compound, a connected family — appears in real time. This isn't a static report. Your team never stops.",
  },
  {
    key: 'insights',
    text: "These are your key insights — the most important findings your agents have surfaced. You can dig deeper into any of them, or save them for later. Everything is written in plain language, not medical jargon.",
  },
  {
    key: 'approvals',
    text: "Some actions need your approval — like sending an email to a researcher, or submitting a grant application. Your team drafts it. You decide. You're always in control.",
  },
  {
    key: 'lab_overview',
    text: "This is your Drug Discovery Lab. Your Biologist agent has identified protein targets linked to the disease. Your Chemist is screening hundreds of compounds. And your Preclinician is evaluating which ones are safe enough to test.",
  },
  {
    key: 'lab_candidates',
    text: "Here's your candidate pipeline — compounds ranked by potential, with safety profiles and clinical precedent. Your team can even help you design experiments and find contract research labs.",
  },
  {
    key: 'community_network',
    text: "You're not the only family fighting this. Beacon's Connector agent has found twelve other CLN3 families — matched by geography, treatment stage, and willingness to share. Every introduction goes through you first.",
  },
  {
    key: 'community_data',
    text: "When families share outcomes, patterns emerge. Your agents analyze this community data to identify what's working. And when enough evidence builds, they map the path from shared data to a formal clinical trial — regulatory steps, funding sources, everything.",
  },
  {
    key: 'closing',
    text: "No family should have to fight alone. Beacon is your team — researching, connecting, strategizing, and never stopping. This is just the beginning.",
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
