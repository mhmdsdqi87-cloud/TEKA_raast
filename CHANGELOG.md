# Changelog

All notable changes. Format based on Keep a Changelog; versioning: SemVer.

## [0.4.0] — 2026-11-15

The verification release: RAAST now observes real browser behavior (Runtime Inspector), reviews pull requests line-by-line (PR Reviewer), repairs code under an explicit three-tier safety policy (Auto-Fix 2.0), backs its claims with a machine-verified bug corpus, extends quality checks from RTL pages to translation files (Language Quality Gate), and documents framework compatibility from real runs instead of manual claims.

### Added
- **RAAST Runtime Inspector** ([`raast/runtime.py`](raast/runtime.py), [docs/runtime-inspector.md](docs/runtime-inspector.md)) — Playwright renders your page at the chosen viewports, collects per-element geometry, then flips the document direction and measures again: asymmetric mirroring, horizontal overflow, clipped text, unflipped directional icons and un-isolated mixed-direction text are reported with a stable selector, screenshot evidence and a suggested fix (rules `RT001`–`RT006`). Ships as the optional dependency group `runtime`: `pip install 'raast[runtime]' && playwright install chromium`.
- **RAAST PR Reviewer** ([`raast/review.py`](raast/review.py) + [`.github/workflows/pr-review.yml`](.github/workflows/pr-review.yml), [docs/pr-review.md](docs/pr-review.md)) — diff-scoped review: only lines changed in the PR are scanned (`git merge-base` diff + `-U0` range parsing in `raast/diffscope.py`), findings are posted as ONE idempotent comment (marker-based update, never comment spam) with severity, file · line, issue and suggested fix, and an optional severity gate for merge blocking.
- **Auto-Fix 2.0** ([`raast/fixer.py`](raast/fixer.py), [docs/auto-fix.md](docs/auto-fix.md)) — every rule is classified into three tiers: **safe** (mechanical, always applied), **suggested** (context-sensitive, stays opt-in behind the existing language gates), **manual** (never auto-applied). `raast fix --tier all|safe`; every apply records a machine-readable fix journal (`.raast-backup/journal.json`) and `raast revert --yes` restores byte-identical originals from that journal.
- **RAAST Bug Corpus** ([`corpus/`](corpus/README.md), tooling in [`tools/corpus/`](tools/corpus/)) — 32 reproducible RTL defect specimens across 8 categories (css-direction, bidi, typography, components, forms, tables, icons, responsive), each with `broken.html`, `fixed.html`, machine-verified rule hits (`tools/corpus/verify.py` — 32/32 PASS, fixed pages must scan clean) and Chromium-rendered before/after screenshots (`tools/corpus/evidence.py`, 64 images). Every specimen is labeled `lab-verified`; the corpus policy separates lab reproductions from real-world reports and ships none of the latter yet.
- **Language Quality Gate** ([`raast/i18n.py`](raast/i18n.py), [docs/i18n-gate.md](docs/i18n-gate.md)) — scans locale files for missing keys, empty values, placeholder mismatches (`{name}`, `{{name}}`, `%s`, `%1$s`), untranslated strings, length anomalies, Western digits / Latin punctuation in Arabic-script prose, un-isolated Latin runs in RTL values, Arabic Yeh/Kaf in Persian text, and opt-in Hebrew niqqud (rules `LQG001`–`LQG009`). CI gate via `--max-errors`.
- **Compatibility Matrix** ([`fixtures/compat/`](fixtures/compat/manifest.json), [`tools/compat/run_matrix.py`](tools/compat/run_matrix.py), [docs/compatibility-matrix.md](docs/compatibility-matrix.md)) — 8 framework fixtures (vanilla CSS, CSS Modules, Tailwind, Bootstrap, React JSX, Next styled-jsx, Vue SFC, Spanish LTR host) scanned by the real engine; the matrix doc is generated, deterministic, and CI-checked for staleness (`run_matrix.py --check`).
- **VS Code extension scaffold** ([`vscode-raast/`](vscode-raast/README.md)) — runs the installed CLI on save and publishes findings as Problems-panel diagnostics (P0 → Error, P1 → Warning, P2 → Information) with quick fixes for safe-tier rules; build/publish instructions included.
- **New console scripts**: `raast-inspect`, `raast-review`, `raast-i18n`. The core `raast` CLI is unchanged and still zero-dependency.

### Changed
- CI self-test job now also validates the corpus (rule-hit verification), the compatibility matrix freshness, and i18n-gate detection on the planted-error locale fixtures.
- `raast.__version__` reconciled with `pyproject.toml` (0.4.0 everywhere).

### Verification (all run locally before push)
- `python3 -m unittest discover -s tests` → 80/80 OK
- `python3 tools/corpus/verify.py` → 32/32 specimens PASS, every fixed page scans clean
- `python3 tools/compat/run_matrix.py --check` → fresh, 8/8 fixtures passing (engine 0.4.0)
- i18n gate on fixture corpora → all 8 planted error classes detected (9 findings), clean locales exit 0
- Wheel installed into a clean venv outside the repo → all four console scripts respond; `raast-inspect` without playwright prints the exact install hint and exits 2
- Runtime Inspector rendered real corpus pages in headless Chromium: broken specimens fire RT rules with report.json + report.md + per-pass screenshots; a logical-property clean page exits 0

## [0.3.0] — 2026-11-15

Distribution release: RAAST becomes auditable without an install (browser playground on GitHub Pages) and speaks the native instruction language of every major AI coding agent.

### Added
- **RAAST Playground** ([`playground/index.html`](playground/index.html), live on GitHub Pages) — paste HTML/CSS, pick a profile (fa / ar / he / es), get findings instantly. Client-side port of **all 17 CLI rules** (`RTL001`–`RTL017`) with the same IDs, severities and profile-driven gating: `RTL005` is P0 for fa/ar and P1-discouraged for he and inert for es; `RTL006` never fires on the es LTR host; `RTL010/RTL009` are suppressed for he/es; `RTL015–017` exist only on the es host. `pre`/`code`/`script`/`style` protected like the CLI. Zero dependencies, zero network calls, nothing uploaded. Exports: Markdown copy, JSON download, prefilled GitHub-issue link.
- **Agent integration files** ([`integrations/`](integrations/README.md)) — the same RTL contract in each tool's native format: `AGENTS.md` (Codex CLI / agents.md convention), `copilot-instructions.md` (`.github/copilot-instructions.md`), `cursor-rtl.mdc` (`.cursor/rules/rtl.mdc`, globs + alwaysApply), plus a per-tool matrix with honest verification status.
- **README**: CI + Release + Playground badges, playground callout, "Works with your agent" table, star-history chart.

### Changed
- Roadmap re-sequenced: plugin manifest / HTML report viewer / VS Code extension move to v0.4; the browser-audit deliverable shipped early as the Playground (client-side port, CLI remains the CI-grade engine).

## [0.2.0] — 2026-11-15

International release: RAAST now covers the three major RTL scripts and becomes a bidirectional tool with its first LTR host profile.

### Added
- **Hebrew profile (`he`)** — third RTL language: Western digits are VALID in prose (RTL010 suppressed), Latin punctuation valid (RTL009 suppressed), ZWNJ never applies, gershayim ״ / geresh ׳ / maqaf ־ conventions documented, nikud-aware line-height (≥ 1.5), font catalog (Heebo, Assistant, Rubik, David Libre, Frank Ruhl Libre, …), Hebrew-calendar `Intl` tag `he-IL-u-ca-hebrew`, ₪ placement. `RTL005` letter-spacing on Hebrew is **P1 discouraged** (not P0 forbidden — Hebrew letters are separate, not cursive) with a Hebrew-specific explanation.
- **Spanish profile (`es`) — first LTR host**: the rule engine inverts. `RTL015` flags un-isolated Arabic/Hebrew runs inside Spanish prose (the #1 bidi defect in es pages serving RTL content), `RTL016` flags RTL-run elements without `dir` in LTR documents, `RTL017` checks RAE inverted marks (¿ ¡). `RTL006` never suggests `dir="rtl"` on `<html>` for LTR hosts; `<bdi>`/`dir="rtl"` regions are masked before prose analysis so the engine's own recommendations never re-flag.
- **New CLI command `raast profiles`** — lists installed language profiles with native names and direction; the debug surface for "which languages does my wheel carry?".
- **RTL script evidence is now Arabic OR Hebrew** — CSS/Tailwind/HTML rules gate on `RTL_SCRIPT_RE` (U+0590–05FF included), so a Hebrew project gets the same physical-property checks as fa/ar. `RTL013` extended accordingly.
- **Profile-driven rule switching**: severity and applicability read from profile JSON (`numerals.western_digits_in_prose`, `punctuation.inverted_marks`, `typography.letter_spacing`) — adding a language no longer requires touching rule code.

### Fixed (packaging hardening)
- **`py.typed` was declared in `package-data` but did not exist** — the type-checker promise was broken and some setuptools versions fail/warn on missing package-data files. File added and regression-tested.
- **Profile loading is now zip-safe** — anchors on `importlib.resources` first with a filesystem fallback, so installs into zipapps/PyInstaller-style bundles resolve profiles too.
- **"Profile not found" is now graceful**: `ProfileError` (a `ValueError`) lists the available profiles instead of a raw `FileNotFoundError` traceback; `doctor`/`fix`/`report` exit 2 with an actionable message.

### Verification (all run locally before push)
- `python3 -m unittest discover -s tests` → 80/80 OK (25 new tests: Hebrew prose/CSS/Tailwind/HTML-meta, Spanish RTL015/016/017 + LTR-host invariants, packaging py.typed + 4-profile completeness, `raast profiles` e2e)
- `python3 -m build` → wheel + sdist; both installed into clean venvs; `raast doctor --language fa|ar|he|es` all exit 0 from outside the repo; `py.typed` + 4 profile JSONs verified inside the installed wheel
- `raast benchmark --cases benchmarks/cases --candidate benchmarks/reference --condition C-reference` → 24/24 passed (no regression)
- `raast doctor . --fail-on P0` → 0 findings, exit 0
- CI `packaging-smoke` job extended: verifies all four profiles load from the installed wheel and he/es probes exit 0

## [0.1.2] — 2026-11-15

Packaging-integrity release: the artifact a user installs now works everywhere, not just inside the source repo.

### Fixed
- **Profiles missing from wheel/sdist (P0)**: `profiles/` lived outside the `raast` package and `PROFILES_DIR` pointed at `<site-packages>/profiles/`. Any real `pip install` (wheel or sdist) crashed every command with `FileNotFoundError: unknown language profile: 'fa'`. CI never caught it because `pip install -e .` (editable) reads straight from the repo, and the action ran `python3 -m raast.cli` from inside the raast source checkout — CWD shadowing imported the source tree instead of the installed package. Profiles now ship as package data (`raast/profiles/`), declared in `[tool.setuptools.package-data]` + `MANIFEST.in`; `PROFILES_DIR` resolves via `__file__` inside the package.
- **Composite action ran the shadowed CLI**: `python3 -m raast.cli` replaced with the installed `raast` console script — always exercises the exact artifact users get, never CWD shadowing.

### Added
- **CI `packaging-smoke` job**: builds sdist + wheel, installs each into a *clean venv outside the repo*, runs `raast doctor` from `/tmp` — fails if profiles are not found. Prevents the class of bug that editable-install CI cannot see.
- **Release workflow**: on `v*` tags — builds wheel+sdist, smoke-tests the wheel in a clean venv, attaches artifacts to the GitHub Release (`pip install raast` from Releases works from v0.1.2).
- **`tests/test_raast.py::TestPackaging`**: profiles live inside the package, parse cleanly, expose digits/punctuation for fa and ar.
- Real assertions for punctuation normalization (previously a tautology comparing `normalize()` to itself).

### Verification (all run locally before push)
- `python3 -m unittest discover -s tests` → 55/55 OK
- `python3 -m build` → wheel + sdist; both installed into clean venvs; `raast doctor <dir outside repo>` exits 0 with profiles found
- `python3 -m raast.cli benchmark --cases benchmarks/cases --candidate benchmarks/reference --condition C-reference` → 24/24 passed
- `python3 -m raast.cli doctor . --fail-on P0 --format github` → 0 findings, exit 0

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
- **Packaging**: SPDX license expression (`license = "MIT"` + `license-files`, `setuptools>=77`) — removes pip build-backend deprecation warnings (PEP 639).

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
