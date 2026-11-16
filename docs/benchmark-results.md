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

## Conditions A/B — controlled with/without-skills run (published, reproducible)

First controlled A/B run, executed 2026-11-16 with the runner and digest in
[`tools/ai-benchmark/`](../tools/ai-benchmark/) (see that README for the
exact reproduction contract):

| Item | Value |
|---|---|
| Model | `glm-4-plus` (z-ai-web-dev-sdk, `thinking: disabled`, default temperature) |
| Calls | 14 — 7 artifact files × 2 conditions, identical user prompts |
| Condition B delta | identical prompt + `tools/ai-benchmark/skill-digest.md` (`digest_sha256_16: 5b8469cec25a38e3`) |
| Scoring | unmodified `raast benchmark` (`--condition A-baseline` / `B-raast`) |

| Condition | Passed | Failed | Notable per-category |
|---|---|---|---|
| **A — baseline (no skills)** | **14/24** | 10 | jalali 0/2 · a11y 1/3 · components 1/2 · rtl_layout 3/4 |
| **B — with RAAST skills** | **20/24** | 4 | jalali 2/2 · a11y 3/3 · components 2/2 · rtl_layout 4/4 |

**Delta: +6 cases.** The skill digest flipped exactly these: `lang`/`dir`
on `<html>` (a11y-003, layout-001), `aria-label` on icon buttons (a11y-002,
comp-002), and Intl-based Jalali dates (`fa-IR-u-ca-persian`) instead of
hardcoded conversion (jalali-001, jalali-002).

**Still failing in BOTH conditions (the honest part):** `bidi-001/002/004`
(un-isolated LTR atoms in generated prose) and `fa-typo-003` (Latin
punctuation in Persian prose). Both conditions were scored with the same
validators; the digest's bidi guidance did not translate into isolation in
generated markup — that is the highest-value skill-improvement target this
run surfaced, and we publish it as such rather than around it.

Raw evidence, all committed:

- Artifacts: `benchmarks/ai/a/*.html`, `benchmarks/ai/b/*.html`
- Call manifest: `benchmarks/ai/manifest.json` (model, per-call timestamps, byte counts, digest hash)
- Reports: `benchmarks/results/a-run.json|.md`, `benchmarks/results/b-run.json|.md`

Any number above can be re-verified offline: `raast benchmark --cases
benchmarks/cases --candidate benchmarks/ai/a --condition A-baseline`
against the committed artifacts. Re-running the *generation* is
nondeterministic (model output); re-running the *scoring* is not.

**Small-sample caveat:** 7 artifacts × 2 conditions is evidence of
direction, not a leaderboard. If you reproduce the run with another
agent/model, open a PR with both JSON reports + environment block and the
results table gains a row.

## Historical note

**Not published at v0.1 — deliberately.** Versions ≤ 0.4.1 refused to
publish A/B numbers because no controlled run had been executed; the
methodology doc shipped first (docs/benchmark-methodology.md), the
controlled run second (this section, v0.4.2).

## Browser validation (development environment, real runs)

Real Chromium runs executed during development against the shipped demo and the project showcase fixture:

| Target | 390px | 768px | 1440px | Notes |
|---|---|---|---|---|
| `demo/index.html` | 9/9 | 9/9 | 9/9 | after tap-target fixes found by the suite itself |
| showcase fixture (localhost) | 9/9 | 9/9 | 9/9 | 1 manual-review note per viewport (bidi isolation inventory) |

Raw artifacts: `browser/results/demo.json`, `browser/results/showcase.json`, screenshots under `browser/results/screenshots/`.

These runs verified the suite catches real bugs: it found sub-40px tap targets in both pages before they were fixed. That finding→fix→green loop is the intended workflow.
