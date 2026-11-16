# Benchmark Methodology

## What the benchmark measures

How correctly an *artifact* (HTML page built by a human or an AI agent) implements RTL engineering rules — not how large a model is, and not subjective aesthetics. Every case is a machine-checkable property with a deterministic validator.

## The three conditions

| Condition | Meaning | How it is produced |
|---|---|---|
| **A — baseline** | Agent output WITHOUT RAAST skills | Run the case `task` prompt in your agent environment with skills absent; collect the produced files into a directory |
| **B — raast** | Agent output WITH RAAST skills | Same, with skills installed |
| **C — reference** | Human-verified expected behavior | `benchmarks/reference/` in this repo, validated in CI |

The runner validates whatever directory you point it at. It **cannot** invent results; it only executes validators over real files and reports statuses. Any A/B numbers you see elsewhere must come with the environment info block the runner emits.

## Honest claims policy

- Reference self-validation (condition C) runs in CI: the validators must accept the reference implementations — a meta-test that they are not just always-fail.
- A/B claims require controlled runs with a named agent, pinned prompts, and a published digest — as of v0.4.2 the repo publishes one such run (baseline 14/24 → with-skills 20/24, `glm-4-plus`, 2026-11-16) produced by [`tools/ai-benchmark/`](../tools/ai-benchmark/) and scored by the unmodified runner; raw artifacts and the call manifest are committed for offline re-verification.
- Do not compare models on a tiny, uncontrolled sample. 24 cases (7 artifacts × 2 conditions) is evidence of direction, not a leaderboard; re-running generation is nondeterministic, re-running scoring is not.

## Reproducing a run

```bash
# C — reference self-validation (CI runs this)
raast benchmark --cases benchmarks/cases --candidate benchmarks/reference --condition C-reference

# A/B — your agent experiment
raast benchmark --cases benchmarks/cases --candidate ./my-agent-output --condition A-baseline --output-prefix benchmarks/results/a-run
raast benchmark --cases benchmarks/cases --candidate ./my-agent-output-raast --condition B-raast --output-prefix benchmarks/results/b-run
```

Each run writes `<prefix>.json` (raw) and `<prefix>.md` (report) with: totals, per-category scores, environment (Python/platform/timestamp), and a limitations block.

## Case anatomy

```json
{
  "id": "fa-typo-001",
  "category": "persian_typography",
  "task": "Build a Persian hero section with a bold display headline.",
  "files": "**/persian_typography.html",
  "severity": "P0",
  "expected_behavior": "...",
  "validation": [ { "type": "no_letter_spacing" } ]
}
```

Validator inventory (15): `html_lang_dir`, `no_letter_spacing`, `zwnj_min_count`, `persian_digits_in_prose`, `arabic_digits_in_prose`, `persian_punctuation`, `no_physical_margin`, `logical_tailwind`, `logical_text_align`, `bidi_isolation`, `code_dir_ltr`, `viewport_meta`, `img_alt`, `icon_button_labels`, `intl_jalali`, `no_ltr_next_arrow`, `responsive_signals`.

Categories (8): persian_typography, arabic_typography, bidi, rtl_layout, responsive, accessibility, jalali_dates, component_correctness.

## Known limitations (published with every report)

1. Static validators inspect markup and visible text; they cannot certify rendered pixels.
2. Validator heuristics (e.g. prose digit detection) can miss exotic structures; they are tuned to minimize false positives, so some true positives are deliberately not caught.
3. Condition A/B comparisons are only meaningful when prompts, temperature, and context are held fixed — the runner does not control these; you must.
4. Font availability and OS shaping affect browser checks; the browser suite attaches screenshots for human review instead of claiming pixel truth.
