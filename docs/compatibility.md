# Compatibility

Honest status of where RAAST works. "Verified" means actually executed in the stated environment during development; "Planned" means designed for but not yet exercised — do not treat planned rows as working.

## Skills hosting environments

| Environment | Status | Install | Notes |
|---|---|---|---|
| Claude Code (skills directory) | **Verified** | `cp -r skills/* ~/.claude/skills/` | Format used throughout development: folder per skill with `SKILL.md` (YAML `name` + `description`). Frontmatter of all six skills validated against the published constraints (name `≤64` chars `[a-z0-9-]`, description `≤1024` chars) — see [architecture-audit.md §3](architecture-audit.md). |
| Claude Code (plugin marketplace) | Planned | — | Requires a `.claude-plugin/plugin.json` manifest and marketplace testing; tracked in the roadmap. |
| Claude API (Skill upload) | Planned | — | The Agent Skills spec is the same; API upload flow not yet exercised end-to-end. |
| Generic agent / any LLM chat | Verified (manual) | Paste `SKILL.md` content into system prompt or project context | Skills are plain Markdown; any agent that ingests instructions can use them. Marked "manual" because we cannot enumerate every environment. |
| Codex CLI / agents.md tools | Format shipped | Copy [`integrations/AGENTS.md`](../integrations/AGENTS.md) → repo root `AGENTS.md` | Follows the [agents.md](https://agents.md) convention. Not runtime-tested inside every vendor product — report mismatches as issues. |
| GitHub Copilot | Format shipped | Copy [`integrations/copilot-instructions.md`](../integrations/copilot-instructions.md) → `.github/copilot-instructions.md` | Official custom-instructions location. Same honest-status caveat. |
| Cursor | Format shipped | Copy [`integrations/cursor-rtl.mdc`](../integrations/cursor-rtl.mdc) → `.cursor/rules/rtl.mdc` | Rules file with `globs` + `alwaysApply` per Cursor's documented format. Same honest-status caveat. |
| Browser (no install) | **Verified** | [RAAST Playground](https://mhmdsdqi87-cloud.github.io/TEKA_raast/) | Client-side port of all 17 rules in `playground/index.html`; rule IDs and profile gating mirror the CLI. Served from the `gh-pages` branch. |

## CLI

| Requirement | Status |
|---|---|
| Python 3.11+ | Verified on 3.12.x (development) |
| Runtime dependencies | None (stdlib only) |
| OS | Verified on Linux (Debian 13). Windows/macOS expected but unverified. |
| Installation | `pip install -e .` from repo root (editable), or run `python3 -m raast.cli` directly |

## Browser test suite

| Requirement | Status |
|---|---|
| Node 18+ / Bun | Verified: Bun 1.3.x with Playwright 1.57.0 |
| Chromium | Verified: installed via `playwright install chromium` in the development sandbox |
| Target | Any URL or local file; fixtures included under `browser/fixtures/` |

## GitHub Action

| Requirement | Status |
|---|---|
| `actions/checkout@v4`, `actions/setup-python@v5` | Pinned in example workflow |
| Composite action at `action/` | Provided; runs CLI in `--format github` annotation mode |
| Browser tests inside Action | Optional, disabled by default (requires `npx playwright install --with-deps chromium`) |

## Language profiles

| Language | Status | Profile |
|---|---|---|
| Persian (fa) | Verified — rules and normalizer wired to profile | `raast/profiles/fa.json` |
| Arabic (ar) | Verified — profile loaded, prose rules use it | `raast/profiles/ar.json` |
| Hebrew (he) | Planned | profile schema supports it; content needs a native-speaker reviewer |
| Urdu (ur) | Planned | same |

## Known non-goals

- RAAST does not ship fonts or claim font licenses beyond pointing to their upstream open licenses.
- The benchmark does not run AI agents itself; it validates HTML artifacts. Condition A/B runs (with/without Skills) happen in *your* agent environment using the methodology in [benchmark-methodology.md](benchmark-methodology.md).
