# Changelog

All notable changes. Format based on Keep a Changelog; versioning: SemVer.

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
