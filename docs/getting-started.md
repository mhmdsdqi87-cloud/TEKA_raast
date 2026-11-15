# Getting Started

RAAST has three pillars that work together:

1. **Skills** — copy Markdown skills into your agent so it *writes* RTL correctly.
2. **Doctor CLI** — scan any project for RTL engineering bugs.
3. **Browser suite + Benchmark** — prove the result on real pages.

## 1. Install the Skills (Claude Code)

```bash
git clone https://github.com/mhmdsdqi87-cloud/TEKA_raast.git
cp -r TEKA_raast/skills/* ~/.claude/skills/
```

No config, no API keys. The agent picks each skill up when you work on Persian/Arabic/RTL interfaces.

Prompts that trigger them:

```
Build a Persian landing page for a coffee shop
Audit this page for RTL bugs
Convert this dashboard's dates to Jalali
```

## 2. Run the Doctor CLI

Requires Python 3.11+ (no dependencies):

```bash
cd TEKA_raast
pip install -e .          # installs the `raast` command
raast doctor /path/to/your-project
```

Typical output:

```
[P0] RTL005 styles.css:42:17 letter-spacing: .05em
    Arabic-script letters are cursive and joined; non-zero letter-spacing
    shatters words («مدیریت» renders as م د ی ر ی ت).
    fix: remove the declaration (use size/weight for display emphasis)
```

Severity gate for CI:

```bash
raast doctor . --fail-on P0 && echo shippable
```

Safe auto-fix (dry-run by default):

```bash
raast fix . --zwnj          # preview diffs
raast fix . --zwnj --apply  # write changes, backups in .raast-backup/
```

## 3. Browser validation (optional)

```bash
cd browser
npm install
npx playwright install chromium
node tests/rtl.spec.mjs --target https://your-site.example --label prod
```

Checks direction, overflow, tap targets, alt/labels, line-height at 390/768/1440 and drops screenshots into `browser/results/screenshots/`.

## 4. Benchmark your agent's output (optional)

```bash
raast benchmark --cases benchmarks/cases --candidate <output-dir> --condition A-baseline
```

See docs/benchmark-methodology.md for conditions A/B/C.

## Next steps

- docs/installation.md — full install matrix
- docs/cli-reference.md — every command and flag
- docs/troubleshooting.md — common issues
