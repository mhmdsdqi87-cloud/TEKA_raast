# Troubleshooting

## CLI

**`raast: command not found`** — run `pip install -e .` inside the repo, or invoke `python3 -m raast.cli`.

**`config error: ... invalid config`** — your `raast.config.json` has an unknown key, rule id, severity, or rule option. The exact offending entry is listed in the error; the schema is documented in docs/cli-reference.md.

**Doctor finds too little on a mixed-language project** — CSS/Tailwind rules only fire in files containing Arabic-script evidence (false-positive guard). Widen deliberately:
```json
{ "rules": { "RTL001": { "force": true }, "RTL004": { "force": true } } }
```

**Doctor flags `left: 50%` centering patterns** — that is the intended RTL003 review-only finding: centering is direction-neutral, and the engine cannot know your intent. P2, not auto-fixed, not failing CI at the default threshold.

**`fix --apply` — where are my originals?** — `.raast-backup/<relative-path>`. The backup folder is excluded from scans. Delete it when satisfied.

**Broken ZWNJ joined where I didn't want it** — the safe table (skills/rtl-typography/references/normalization.md) only joins known affix patterns against code-fence/URL/inline-code protection. If a join is wrong, restore from backup and wrap the region in `<!-- keep --> … <!-- /keep -->`, then report the case in an issue.

## Skills

**Skill not triggering in Claude Code** — check `~/.claude/skills/<name>/SKILL.md` exists with YAML frontmatter (`name` + `description`). Only one level of nesting is used by this repo.

**Skill applies Persian rules to Arabic content** — the skills ask the agent to confirm fa vs ar first; if it guessed wrong, say "use the Arabic profile" — `profiles/ar.json` conventions (Arabic-Indic digits, no ZWNJ affix joining) are documented in rtl-typography §8.

## Browser suite

**Playwright "Executable doesn't exist"** — the npm package version must match the installed browser revision. This repo pins `playwright@1.57.0` (chromium-1200). Run `npx playwright install chromium` after install.

**File targets** — use absolute `file://` URLs: `--target file:///abs/path/page.html`.

**Tap-target failures on links inside a `<nav>`** — give links `padding` (≥40px box height) or an `::after` stretched hit area; see demo/index.html for the pattern.

## GitHub Action

**Annotations not appearing** — the doctor must run with `--format github` (the action does this). Check the workflow step did not override it.

**Action exits 1 on P2s** — set `fail-on: off` or the severity you intend; default in the action is `P0`.
