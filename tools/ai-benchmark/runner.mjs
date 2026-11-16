// RAAST AI benchmark runner — the exact script used for the published
// A/B run (benchmarks/results/a-run.*, b-run.*). See README.md next to
// this file for the reproduction contract.
//
// For every artifact file targeted by the benchmark cases it makes TWO
// model calls with IDENTICAL user prompts; the only difference is the
// RTL expertise appendix (tools/ai-benchmark/skill-digest.md) present in
// condition B. The runner writes files, it never scores them — scoring is
// `raast benchmark`'s job, so this script cannot influence the outcome.
//
// Environment: node >= 18, `z-ai-web-dev-sdk` installed (the environment
// the published run executed in; see README for the environment block).
//
// Usage:
//   node runner.mjs --repo /path/to/TEKA_raast --out /path/to/benchmarks/ai
import ZAI from 'z-ai-web-dev-sdk';
import { readdirSync, readFileSync, writeFileSync, mkdirSync } from 'fs';
import { createHash } from 'crypto';
import { join, basename } from 'path';

const args = process.argv.slice(2);
const argOf = (name, fallback) => {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : fallback;
};
const REPO = argOf('--repo', process.cwd());
const OUT = argOf('--out', join(REPO, 'benchmarks', 'ai'));

const SYSTEM = 'You are a senior front-end engineer. Produce one complete, production-quality single-file HTML page that fulfills every requirement listed. Output ONLY the raw HTML file content — no explanations, no markdown fences.';

// Group cases by artifact file, merge their tasks (one page must satisfy
// every case that validates it — mirrors how benchmarks/reference is built).
const casesDir = join(REPO, 'benchmarks', 'cases');
const byFile = new Map();
for (const f of readdirSync(casesDir).sort()) {
  if (!f.endsWith('.json')) continue;
  const c = JSON.parse(readFileSync(join(casesDir, f), 'utf-8'));
  const file = basename(c.files.replace(/\*\*\//g, ''));
  if (!byFile.has(file)) byFile.set(file, []);
  byFile.get(file).push(c);
}

const digestPath = join(REPO, 'tools', 'ai-benchmark', 'skill-digest.md');
const digestRaw = readFileSync(digestPath, 'utf-8');
const digestBody = digestRaw.slice(digestRaw.indexOf('---') + 3).trim();
const digestHash = createHash('sha256').update(digestBody, 'utf-8').digest('hex').slice(0, 16);

function stripFences(text) {
  const m = text.match(/```(?:html)?\s*\n([\s\S]*?)```/);
  const body = m ? m[1] : text;
  return body.trim() + '\n';
}

const zai = await ZAI.create();
const manifest = { digest_sha256_16: digestHash, started_at: new Date().toISOString(), runs: [] };

for (const [file, cases] of byFile) {
  const tasks = cases.map((c, i) => `${i + 1}) ${c.task}`).join('\n');
  const user = `Requirements (all of them apply to one page):\n${tasks}\n\nWrite the complete HTML file now.`;
  for (const cond of ['a', 'b']) {
    const sys = cond === 'b'
      ? SYSTEM + '\n\n--- RTL expertise brief (follow it) ---\n' + digestBody
      : SYSTEM;
    const started = new Date().toISOString();
    try {
      const completion = await zai.chat.completions.create({
        messages: [
          { role: 'assistant', content: sys },
          { role: 'user', content: user },
        ],
        thinking: { type: 'disabled' },
      });
      const content = completion.choices?.[0]?.message?.content ?? '';
      const model = completion.model || 'unknown';
      const dir = join(OUT, cond);
      mkdirSync(dir, { recursive: true });
      writeFileSync(join(dir, file), stripFences(content));
      manifest.runs.push({ file, condition: cond, model, started, finished: new Date().toISOString(), bytes: content.length });
      console.log(`ok ${cond}/${file} model=${model} bytes=${content.length}`);
    } catch (e) {
      manifest.runs.push({ file, condition: cond, started, error: e.message });
      console.error(`FAIL ${cond}/${file}: ${e.message}`);
    }
    await new Promise((r) => setTimeout(r, 300));
  }
}

writeFileSync(join(OUT, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
console.log(`done: ${manifest.runs.length} calls, digest=${digestHash}`);
