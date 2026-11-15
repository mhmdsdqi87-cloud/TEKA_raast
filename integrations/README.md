# Agent integrations

RAAST ships the same RTL engineering contract in the native instruction format of each major
AI coding agent. Pick your tool, copy one file, done.

| Agent | File | Where it goes | Notes |
|---|---|---|---|
| Claude Code | [`skills/`](../skills/) (6 SKILL.md playbooks) | `cp -r skills/* ~/.claude/skills/` | Full depth: per-skill references, decision tables, font catalogs. Verified end-to-end. |
| Codex CLI & agents.md-compatible tools | [`AGENTS.md`](AGENTS.md) | Repo root as `AGENTS.md` | The [agents.md](https://agents.md) convention. Covers Codex CLI, opencode, Zed and other readers. |
| GitHub Copilot | [`copilot-instructions.md`](copilot-instructions.md) | `.github/copilot-instructions.md` | Official custom-instructions location; applies to chat + inline. |
| Cursor | [`cursor-rtl.mdc`](cursor-rtl.mdc) | `.cursor/rules/rtl.mdc` | Rules file with `globs` (tsx/jsx/html/css/vue/svelte) + `alwaysApply`. |
| Any other agent | any file above | system prompt / project context | All three files are plain Markdown carrying the same contract. |

## What the rules cover

The 8 hard rules (dir/lang on `<html>`, letter-spacing ban, logical properties, ZWNJ,
bidi isolation, numerals per profile, line-height, fonts), Tailwind logical utilities and
icon-flip policy, calendar-correct dates via `Intl`, punctuation conventions per language —
and the verification step (`raast doctor`) so the agent's output is checked, not trusted.

## Honest status

- **Verified end-to-end:** Claude Code skills directory (the format this repo develops against)
  and the CLI itself (80 unit tests + 24-case benchmark).
- **Format-shipped:** Copilot / Cursor / agents.md files follow each tool's documented
  conventions but have not been runtime-tested inside every vendor's product; if one of them
  misbehaves, [open an issue](https://github.com/mhmdsdqi87-cloud/TEKA_raast/issues).

## Playwright-level browser checks

For rendered-output verification beyond static analysis, the repo also ships a Playwright
suite: [`browser/`](../browser/) — direction, overflow, line-height, tap targets at
390 / 768 / 1440 viewports.
