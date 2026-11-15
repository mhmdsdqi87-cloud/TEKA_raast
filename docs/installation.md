# Installation

## Skills (Claude Code)

```bash
git clone https://github.com/mhmdsdqi87-cloud/TEKA_raast.git
cp -r TEKA_raast/skills/* ~/.claude/skills/
```

Verify: start Claude Code and ask "what skills are installed?" — the six `rtl-*` / `jalali-dates` skills should appear. Frontmatter is validated against the Agent Skills constraints (docs/architecture-audit.md §3).

## CLI

Requirements: Python 3.11+ (stdlib only, no dependencies).

```bash
# editable install (recommended for contributors)
git clone https://github.com/mhmdsdqi87-cloud/TEKA_raast.git
cd TEKA_raast
pip install -e .

# or run without installing
python3 -m raast.cli doctor <path>
```

Sanity check:

```bash
raast --version          # raast 0.1.0
raast doctor benchmarks/reference --fail-on P0   # exit 0 expected
```

## Browser suite

Requirements: Node 18+ (or Bun), Playwright 1.57+, Chromium.

```bash
cd browser
npm install                       # or: bun install
npx playwright install chromium   # skip if already installed
node tests/rtl.spec.mjs --target file://../demo/index.html --label demo
```

## GitHub Action

No secrets required. In your repository's workflow:

```yaml
- uses: mhmdsdqi87-cloud/TEKA_raast/action@main
  with:
    language: fa
    fail-on: P0
```

See .github/workflows/raast.yml for a complete example including the self-test job.

## Troubleshooting quick hits

| Symptom | Fix |
|---|---|
| `pip install -e .` fails on Python < 3.11 | Upgrade Python; the CLI uses `tomllib`-era stdlib features |
| Playwright launch error "Executable doesn't exist" | `npx playwright install chromium` — keep the npm package version close to the installed browser revision (1.57.x ↔ chromium-1200) |
| Config error: unknown top-level key | docs/cli-reference.md lists the exact schema |
| Too few findings on a mixed project | CSS/Tailwind rules need Arabic-script evidence per file; use `rules: {"RTL001": {"force": true}}` to widen |
