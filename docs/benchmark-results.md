# Benchmark Results

## Condition C — reference self-validation (published, reproducible)

Executed: 2026-11-14 · Python 3.12 · Linux · runner: `raast benchmark`

```
condition=C-reference candidate=benchmarks/reference
passed 24/24, failed 0, skipped 0
  accessibility                3/3
  arabic_typography            3/3
  bidi                         4/4
  component_correctness        2/2
  jalali_dates                 2/2
  persian_typography           4/4
  responsive                   2/2
  rtl_layout                   4/4
```

Artifacts: `benchmarks/results/c-reference.json` and `benchmarks/results/c-reference.md`.

**What this proves:** the validators accept genuinely correct implementations (they are not vacuously failing), and the reference implementations satisfy every published rule. It is a meta-test of the benchmark itself, included in CI (`.github/workflows/raast.yml`).

## Conditions A/B — agent comparisons

**Not published at v0.1 — deliberately.**

An honest A/B claim requires controlled runs of a named agent with pinned prompts and versions. This repository does not fabricate numbers. The methodology (docs/benchmark-methodology.md) gives you the exact procedure:

1. Run your agent on the 24 `task` prompts without skills → collect output dir → `--condition A-baseline`
2. Repeat with RAAST skills installed → `--condition B-raast`
3. Publish both JSON reports with their environment blocks

If you run this and publish the two JSON artifacts, open a PR adding them under `benchmarks/results/` — include agent name, version, and prompts.

## Browser validation (development environment, real runs)

Real Chromium runs executed during development against the shipped demo and the project showcase fixture:

| Target | 390px | 768px | 1440px | Notes |
|---|---|---|---|---|
| `demo/index.html` | 9/9 | 9/9 | 9/9 | after tap-target fixes found by the suite itself |
| showcase fixture (localhost) | 9/9 | 9/9 | 9/9 | 1 manual-review note per viewport (bidi isolation inventory) |

Raw artifacts: `browser/results/demo.json`, `browser/results/showcase.json`, screenshots under `browser/results/screenshots/`.

These runs verified the suite catches real bugs: it found sub-40px tap targets in both pages before they were fixed. That finding→fix→green loop is the intended workflow.
