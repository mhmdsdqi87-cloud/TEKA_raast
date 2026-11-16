# AI benchmark — controlled with/without-skills run

Answers one question with real data: **does the RAAST skill set measurably
improve an LLM's RTL output?** The published run is fully reproducible;
nothing here is hand-scored.

## Design

- **Artifact generation** — the runner (`runner.mjs`) groups the 24
  benchmark cases by their 7 artifact files (several cases validate the
  same page, so one page must satisfy all of them — the same contract as
  `benchmarks/reference/`). For each artifact file it makes two model
  calls with **identical user prompts**. Condition **A** gets a bare
  system prompt; condition **B** gets the same prompt plus
  [`skill-digest.md`](skill-digest.md) — a condensed digest of the six
  RAAST skills. `thinking` disabled, default temperature, no other
  settings touched.
- **Scoring** — the runner only writes files. Scoring is
  `raast benchmark`'s job and runs afterwards, unmodified:

  ```bash
  raast benchmark --cases benchmarks/cases --candidate benchmarks/ai/a \
      --condition A-baseline --output-prefix benchmarks/results/a-run
  raast benchmark --cases benchmarks/cases --candidate benchmarks/ai/b \
      --condition B-raast --output-prefix benchmarks/results/b-run
  ```

- **Published run** — `benchmarks/results/a-run.*` and `b-run.*`, with the
  generated artifacts under `benchmarks/ai/{a,b}/` and the call manifest
  (`model`, per-call timestamps, digest hash) in `benchmarks/ai/manifest.json`.

## Reproducing

```bash
pip install raast                                   # or: pip install -e .
node tools/ai-benchmark/runner.mjs --repo . --out benchmarks/ai
# (requires z-ai-web-dev-sdk in the node environment — the SDK the
# published run used; see the environment block in docs/benchmark-results.md)
raast benchmark --cases benchmarks/cases --candidate benchmarks/ai/a \
    --condition A-baseline --output-prefix benchmarks/results/a-run
raast benchmark --cases benchmarks/cases --candidate benchmarks/ai/b \
    --condition B-raast --output-prefix benchmarks/results/b-run
```

## Honest-claims rules

- One published run is one named model, one date, one digest hash — recorded
  in the results docs. Small samples: 7 artifacts × 2 conditions; treat the
  delta as evidence of direction, not a leaderboard.
- The digest changes only when the skills change; the manifest pins its
  hash (`digest_sha256_16`).
- Model outputs are nondeterministic; re-running may shift individual
  cases. The raw artifacts are committed so every published number can be
  re-verified offline with `raast benchmark` alone.
