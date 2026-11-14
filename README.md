<div align="center">
  <img src="assets/banner.svg" alt="RAAST — RTL engineering for AI-powered development" width="100%">
</div>

<div align="center">

**Build RTL right. Everywhere.**

Open-source RTL engineering for AI-powered development — Persian & Arabic first.

[![Skills](https://img.shields.io/badge/agent_skills-6-34D399)](#pillar-1--raast-skills) [![CLI rules](https://img.shields.io/badge/doctor_rules-14-34D399)](#pillar-2--raast-doctor-cli) [![Benchmark](https://img.shields.io/badge/benchmark-24_cases-34D399)](#pillar-3--raast-benchmark) [![Tests](https://img.shields.io/badge/unit_tests-51_passing-34D399)](#test-evidence) [![License](https://img.shields.io/badge/license-MIT-9AA3A0)](LICENSE)

`rtl` · `persian` · `farsi` · `arabic` · `bidi` · `typography` · `i18n` · `l10n` · `claude-code` · `claude-skills` · `ai-agents` · `developer-tools` · `linting` · `accessibility` · `right-to-left` · `hebrew` · `urdu` · `localization` · `nextjs` · `tailwind`

</div>

---

AI coding agents build beautiful interfaces — and then you open them in Persian or Arabic:

- `letter-spacing` **shatters joined Arabic-script letters**: «مدیریت» renders as م د ی ر ی ت
- Missing **ZWNJ** (`نیم‌فاصله`, U+200C): `«می شود»، «خانه ها»، «خوب تر»`
- Western digits inside Persian copy: "5 ستاره" instead of «۵ ستاره»
- `text-align: left`, physical `margin-left/right`, icons pointing the wrong way
- `$99` scrambling to `99$`, URLs reordering inside RTL sentences
- Fonts without Persian glyph coverage, cramped 1.5 line-height on Arabic script

LLMs *know* some of this — but knowledge without an executable contract does not ship. **RAAST turns RTL correctness into three artifacts that work together: skills that teach the agent, a CLI that verifies the result, and a benchmark that measures the difference.**

<div align="center">
  <img src="assets/terminal-demo.gif" alt="raast doctor finding and fixing real RTL bugs" width="760">
</div>

> Real CLI output. The broken page is in [`tests/fixtures/`](tests/fixtures/) — reproduce it yourself in 10 seconds.

## The three pillars

### Pillar 1 — RAAST Skills (the intelligence layer)

Six focused skills, plain Markdown, zero config — validated against the [Agent Skills](https://github.com/anthropics/skills) frontmatter constraints:

| Skill | Teaches the agent |
|---|---|
| [`rtl-typography`](skills/rtl-typography/SKILL.md) | Font selection (Persian/Arabic catalog), ZWNJ rules with corrected examples, numerals & separators, punctuation, line-height, the letter-spacing ban, copy/paste & selection integrity, and the [normalization decision table](skills/rtl-typography/references/normalization.md) |
| [`rtl-landing`](skills/rtl-landing/SKILL.md) | Full Persian/Arabic landing pages: section order, Toman pricing, semantic HTML, dark/light theming, Jalali copyright year |
| [`rtl-components`](skills/rtl-components/SKILL.md) | Tailwind logical utilities, the icon-flip list, forms/tables/overlays, direction-aware animations, shadcn/ui RTL notes |
| [`rtl-bidi`](skills/rtl-bidi/SKILL.md) | Mixed-direction content: phones, emails, URLs, `$99`, serials/SKUs, code blocks, UGC — with `bdi`/`dir=auto`/`unicode-bidi` recipes |
| [`jalali-dates`](skills/jalali-dates/SKILL.md) | `Intl` fa-IR one-liners, conversion-vs-formatting distinction, relative time, storage conventions, SSR hydration |
| [`rtl-audit`](skills/rtl-audit/SKILL.md) | 20-point review checklist, P0/P1/P2 severities, findings mapped to CLI rule IDs |

Languages: **fa** and **ar** profiles today; **he** and **ur** are designed-in via [`profiles/`](profiles/) and need native-speaker reviewers (see [CONTRIBUTING.md](CONTRIBUTING.md)).

### Pillar 2 — RAAST Doctor CLI (the engineering layer)

```bash
pip install -e .        # Python 3.11+, zero dependencies
raast doctor ./your-project
```

14 static rules (`RTL001`–`RTL014`) with severity + confidence, evidence-gated so mixed projects stay quiet (a `left:` in a pure-LTR file is *not* flagged):

| Rule | Detects | Sev |
|---|---|---|
| `RTL001/002` | physical `margin/padding-left/right` | P1 |
| `RTL003` | physical `left:/right:` positioning | P2 review |
| `RTL004` | `text-align: left/right` | P1 |
| `RTL005` | non-zero `letter-spacing` on Arabic script | **P0** |
| `RTL006/014` | missing `dir` / `lang` on `<html>` | P0 / P1 |
| `RTL007` | `translate-x` without an RTL twin | P2 review |
| `RTL008` | Tailwind physical utilities (`ml-`, `text-left`, …) | P1 |
| `RTL009/010` | Latin punctuation / Western digits in Arabic prose | P2 |
| `RTL011` | broken ZWNJ compounds (`«می رود»`) | P1 |
| `RTL012` | un-isolated LTR atoms (URL/phone/$) in RTL prose | P2 review |
| `RTL013` | `dir="ltr"` on Arabic-only content | P0 |

```bash
raast doctor . --format github      # Actions annotations
raast doctor . --fail-on P0         # severity gate, exit code
raast fix . --zwnj                  # dry-run diffs first
raast fix . --zwnj --apply          # backups land in .raast-backup/
raast audit .                       # + human-only manual checklist
```

Safe fixes only. Ambiguous code is never rewritten — the [normalization decision table](skills/rtl-typography/references/normalization.md) defines exactly what may transform, per language.

### Pillar 3 — RAAST Benchmark (the evaluation layer)

24 machine-validated cases across 8 categories with 17 validators. The runner **only reports what actually passes** — it cannot fabricate numbers.

- **Condition C (reference)** — human-verified implementations, validated in CI: **24/24** ([results](docs/benchmark-results.md))
- **Conditions A/B (with vs. without skills)** — methodology published, numbers *deliberately not fabricated*; run it on your agent per [docs/benchmark-methodology.md](docs/benchmark-methodology.md)

## Real browser testing

A Playwright suite (Node, Chromium) that runs against any page at **390 / 768 / 1440** viewports:

```bash
cd browser && npm install
node tests/rtl.spec.mjs --target https://your-page.example --label prod
```

Direction, horizontal overflow, computed line-height, tap-target sizes, alt/label wiring, keyboard focus — plus screenshots for human review. It separates **automated failures** from **manual-review signals** from **checks that are not automatable** (glyph fidelity, bidi shaping — no fake claims). During development this suite found real sub-40px tap targets in our own pages; the finding→fix→green loop is the workflow.

## GitHub Action

```yaml
- uses: mhmdsdqi87-cloud/TEKA_raast/action@main
  with:
    language: fa
    fail-on: P0
```

No secrets required. Annotations appear on the PR; the gate is your severity choice. Full example: [`.github/workflows/raast.yml`](.github/workflows/raast.yml).

## Install & quick start

```bash
git clone https://github.com/mhmdsdqi87-cloud/TEKA_raast.git
cp -r TEKA_raast/skills/* ~/.claude/skills/     # skills for Claude Code
cd TEKA_raast && pip install -e .               # the CLI (optional)
raast doctor benchmarks/reference --fail-on P0  # sanity check → exit 0
```

Anything that ingests Markdown can use the skills; verified environments and honest status of everything else: [docs/compatibility.md](docs/compatibility.md).

## Test evidence

```
$ python3 -m unittest discover -s tests
Ran 51 tests in 0.3s — OK

$ raast benchmark --cases benchmarks/cases --candidate benchmarks/reference --condition C-reference
passed 24/24, failed 0, skipped 0

$ raast doctor demo --fail-on P0
Summary: 1 finding(s): 0 P0, 0 P1, 1 P2      # exit 0
```

The unit suite covers Unicode edge cases: ZWNJ joins and their *non*-joins (possessive suffixes stay attached), Arabic-Indic digits blocked from conversion in `ar`, code-fence protection, config schema validation, scanner globs, and end-to-end CLI runs including the backup/restore path.

## Documentation

| | |
|---|---|
| [Getting started](docs/getting-started.md) | [Installation](docs/installation.md) |
| [CLI reference](docs/cli-reference.md) | [Troubleshooting](docs/troubleshooting.md) |
| [Benchmark methodology](docs/benchmark-methodology.md) | [Benchmark results](docs/benchmark-results.md) |
| [Architecture audit](docs/architecture-audit.md) | [Compatibility](docs/compatibility.md) |
| [Roadmap](docs/implementation-roadmap.md) | [Release checklist](docs/release-checklist.md) |

## What RAAST is not

- **Not a Persian-only prompt pack** — machine-readable profiles separate language conventions from rules.
- **Not a star-maximization project** — no fabricated metrics; A/B claims require controlled runs you can reproduce.
- **Not a visual-perfect scanner** — static analysis plus browser checks approximate truth; screenshots accompany every claim.

## Roadmap

- **v0.2** — Claude Code plugin manifest + marketplace flow; a published, reproducible A/B benchmark demo
- **v0.3** — agent adaptation guides (Cursor rules, Copilot instructions); HTML report viewer
- **v0.4** — VS Code extension reusing the CLI engine (design in roadmap)
- **v0.5** — Hebrew / Urdu profiles after native-speaker review; email-client and PDF categories

## Contributing

PRs welcome — rules with false-positive tests, benchmark cases, and **language profiles from native speakers** are the highest-value contributions. Read [CONTRIBUTING.md](CONTRIBUTING.md); releases follow [docs/release-checklist.md](docs/release-checklist.md). This project follows its [Code of Conduct](CODE_OF_CONDUCT.md); security issues go to [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) — referenced fonts carry their own open licenses (OFL or equivalent).

<div align="center">
  <sub>raast (راست) — "right / straight / correct" in Persian. Built because Persian and Arabic users deserve interfaces that read like a native designer made them.</sub>
</div>
