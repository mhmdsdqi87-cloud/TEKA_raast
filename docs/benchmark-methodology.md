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

- This repository publishes **condition C results only** (reference self-validation: the validators must accept the reference implementations — a meta-test that the validators are not just always-fail).
- No A/B agent runs are published by this repo at v0.1. Claims like "skills improve output by X%" require controlled A/B runs with a named agent, version, and prompts — the methodology below enables you to produce them reproducibly.
- Do not compare models on a tiny, uncontrolled sample. 24 cases is a smoke benchmark, not a leaderboard.

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
