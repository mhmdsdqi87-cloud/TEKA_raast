# Implementation Roadmap

Status legend: **done** (implemented + verified) · **partial** (implemented, gaps documented) · **planned** (designed, not built).

## Phase A — Audit — done
- Full repository audit → [architecture-audit.md](architecture-audit.md)
- Skills spec validation (programmatic) → done, all 6 pass
- Compatibility matrix → [compatibility.md](compatibility.md)

## Phase B — Skills engineering — done
- `rtl-typography`: normalization reference added (`references/normalization.md`); copy/paste & selection guidance; ambiguous-transformation warnings defined
- `rtl-landing`: semantic HTML + a11y + theme guidance expanded
- `rtl-components`: direction-aware animation section added
- `rtl-bidi`: product identifiers / serials / UGC table expanded
- `jalali-dates`: conversion-vs-formatting distinction sharpened; no custom algorithm (by design)
- `rtl-audit`: findings now reference CLI rule IDs (`RTL0xx`) — one shared vocabulary
- ZWNJ normalizer: engine moved to CLI (`raast/normalizer.py`); skill script kept as standalone entry point; **unit tests added** (Unicode edge cases, code-block protection, exclusions)

## Phase C/D — CLI — done
- `raast` CLI (stdlib only): `doctor`, `fix`, `report`, `detect`, `init`, `benchmark`, `--version`
- 14 static rules with IDs `RTL001`–`RTL014`, confidence levels, P0/P1/P2 severities
- `raast.config.json` with schema validation; include/exclude, severity overrides, language profile
- Outputs: human, JSON, Markdown, GitHub Actions annotations
- Safe autofix: dry-run default, unified diff preview, explicit `--apply`
- Verified: unit tests + dogfood run on this repo's own files (see below)

## Phase E — Benchmark — done (infrastructure) / results: reference-only
- 24 cases across 8 categories, JSON-defined, each with validator + severity
- Reference implementations for 6 representative cases
- Runner validates real candidate files; condition C (reference) executed and reported
- **No A/B agent-run results are published** — methodology requires running agents in your environment; see [benchmark-methodology.md](benchmark-methodology.md)

## Phase F — Browser testing — done
- Playwright suite: direction, overflow at 390/768/1440, icon orientation, form/label wiring, `lang`/`alt` presence, mixed-direction isolation
- Clear separation: automated failures vs. manual-review findings vs. not-automatable checks
- Verified against `demo/index.html` and the project showcase fixture

## Phase G — GitHub Action — done
- `action/action.yml` composite action (checkout → setup-python → `raast doctor --fail-on`)
- Example workflow `.github/workflows/raast.yml`; self-check workflow for this repo

## Phase H — Multi-agent ecosystem — partial
- Claude Code verified (see compatibility.md); plugin/API flows planned
- Adaptation guides for other agents planned (roadmap v0.3)

## Phase I — VS Code extension — planned (by design)
- Design documented in roadmap §v0.4; deliberately not scaffolded before the diagnostics engine accumulates real-world usage. The engine (Python) would be consumed via the CLI as language server exec — no logic duplication planned.

## Phase J — Language profiles — done for fa/ar
- `profiles/fa.json`, `profiles/ar.json`: digits, separators, punctuation, affixes, fonts, date locale
- Contributor path for native reviewers documented in CONTRIBUTING.md

## Phase K — Docs & release prep — done
- README (international English), CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, CHANGELOG, release checklist
- docs/: getting-started, installation, cli-reference, benchmark-methodology, benchmark-results, troubleshooting
- Issue/PR templates; no fabricated community artifacts (no fake issues/stars/contributors — the repo starts at zero and says so)

## Post-release (planned)
- **v0.2**: plugin manifest + marketplace flow; benchmark condition A/B example runs with a named agent, published as methodology demo
- **v0.3**: agent adaptation guides (Cursor/Copilot/Windsurf), `raast report --serve` static HTML viewer
- **v0.4**: VS Code extension using the CLI engine
- **v0.5**: Hebrew/Urdu profiles after native-speaker review; additional benchmark categories (email clients, PDF generation)
