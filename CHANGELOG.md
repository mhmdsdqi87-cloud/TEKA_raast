# Changelog

All notable changes. Format based on Keep a Changelog; versioning: SemVer.

## [0.1.1] — 2026-11-14

CI-green release: the repository's own GitHub Action now passes on every push.

### Fixed
- **GitHub Action install path**: the composite action ran `pip install <action_path>/../..` which resolved to the *parent* of the action repository — install failed with `exit code 1` before the doctor ever ran. Now `<action_path>/..` (the repo root).
- **CLI/action flag mismatch**: the action passed `--language` to `doctor`, which did not accept it. `doctor` and `audit` now support `--language {fa,ar}` as a config override.
- **RTL005 false positive**: `` `letter-spacing: 0` `` inside inline code resolved to the token `` 0` `` (trailing backtick) and was flagged P0. Value tokens now stop at quotes/backticks.
- **RTL008 prose false positives**: hyphenated English words ("right-to-left", "left-aligned") matched as Tailwind utilities. Trailing word-boundary lookaheads added.
- **RTL004 scoped-LTR awareness**: `text-align: left` inside a `[dir="ltr"]` scope is now reported at low confidence / non-fixable ("verify intentional"), consistent with RTL001/RTL002.
- **RTL012/009/010 isolation awareness**: contents of `<bdi>` and `dir="ltr"` regions are masked before prose analysis — already-isolated LTR atoms no longer re-flag. Matches the benchmark validator's isolation model.
- **Markdown scanning policy**: CSS/Tailwind/HTML-structure rules no longer run on `.md`/`.mdx` (documents deliberately illustrate wrong patterns); prose rules still scan markdown.
- **Demo**: pricing badge centered with `inset-inline`/`margin-inline: auto` instead of physical `left: 50%` + `translateX(-50%)`.
- **CI hygiene**: `actions/checkout@v5`, `actions/setup-python@v6` (Node 24 — removes deprecation warnings); runners pinned to `ubuntu-24.04` for reproducibility.

### Added
- Root `raast.config.json` for self-scanning: benchmark fixtures, browser suite, test fixtures and generated assets are excluded from the doctor gate (intentionally-broken or non-source content).

### Verification (all run locally before push)
- `python3 -m unittest discover -s tests` → 51/51 OK
- `python3 -m raast.cli benchmark --cases benchmarks/cases --candidate benchmarks/reference --condition C-reference` → 24/24 passed
- `python3 -m raast.cli doctor . --language fa --fail-on P0 --format github` → **0 findings**, exit 0

## [0.1.0] — 2026-11-14

First public release of the RAAST ecosystem (three pillars, one rule set).

### Added
- **Skills** (6): rtl-typography (with fonts.md + normalization reference + standalone fix-zwnj.py), rtl-landing, rtl-components, rtl-bidi, jalali-dates, rtl-audit — frontmatter validated against Agent Skills constraints.
- **CLI** (`raast`, stdlib-only Python): `init`, `detect`, `doctor`, `audit`, `fix`, `report`, `benchmark` with 14 static rules (RTL001–RTL014), severity/confidence model, text/JSON/Markdown/GitHub-annotation output, strict config validation, safe dry-run-first autofix with `.raast-backup/` recoverability.
- **Benchmarks**: 24 cases across 8 categories, 17 validators, 7 reference implementations; condition C self-validation passes 24/24 in CI.
- **Browser suite** (Playwright 1.57): direction/overflow/tap-targets/alt/labels/line-height checks at 390/768/1440 with screenshots; verified green on demo + showcase after finding and fixing real tap-target bugs.
- **GitHub Action** (composite, no secrets) + example workflow with self-test job.
- **Profiles**: `fa.json`, `ar.json` — machine-readable conventions shared by rules and skills.
- **Docs**: getting-started, installation, cli-reference, benchmark methodology + results, troubleshooting, architecture audit, compatibility, roadmap.
- **Community**: CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, templates, release checklist.

### Known limitations
- No A/B agent-run benchmark results published (methodology provided; nothing fabricated).
- VS Code extension designed but intentionally not built (roadmap v0.4).
- Arabic profile awaiting native-speaker review (roadmap v0.5).
