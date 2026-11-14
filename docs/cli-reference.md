# CLI Reference — `raast`

Zero-dependency Python CLI (3.11+). Install: `pip install -e .` from the repo root, or run as a module: `python3 -m raast.cli`.

Global: `raast --version`

## raast init

```
raast init [path] [--language fa|ar] [--force]
```

Writes `raast.config.json` with detected defaults. Refuses to overwrite without `--force`.

## raast detect

```
raast detect [path]
```

Evidence-based framework detection (JSON). Claims a framework only on real evidence: dependencies inside `package.json`, tailwind config + CSS presence, or HTML/CSS file counts. Never assumes from a single decoy file.

## raast doctor

```
raast doctor [path] [--format text|json|markdown|github]
             [--fail-on P0|P1|P2] [--config <file>]
```

Static diagnostics. `path` may be a directory or a single file.

- `--format github` emits `::error`/`::warning` annotations for Actions.
- `--fail-on P0` exits 1 when P0 findings exist (default comes from config `fail_on`).
- Exit codes: 0 clean, 1 findings >= threshold, 2 config error.

## raast audit

```
raast audit [path]
```

`doctor --format markdown` plus the manual-review checklist (contrast, rhythm, translation quality, icon direction) that static analysis cannot automate.

## raast fix

```
raast fix [path] [--apply] [--diff] [--zwnj] [--zwnj-digits] [--zwnj-punct] [--config <file>]
```

Safe fixes only — high-confidence, reversible transformations:

- physical declarations → logical (`margin-left` → `margin-inline-start`, `text-align: left` → `start`)
- removal of non-zero `letter-spacing` on Arabic-script files (P0)
- Tailwind class renames (`ml-4` → `ms-4`, `text-left` → `text-start`)
- `--zwnj`: safe U+200C joins per the normalization decision table
- `--zwnj-digits` / `--zwnj-punct`: language-gated extras (fa only; disabled for ar automatically)

Dry-run is the default and prints unified diffs. `--apply` writes backups to `.raast-backup/` (excluded from future scans). Ambiguous code is never rewritten.

## raast report

```
raast report [path] --output raast-report.md
```

Writes the markdown report artifact.

## raast benchmark

```
raast benchmark --candidate <dir> [--cases <dir>] [--condition C-reference] [--json] [--output-prefix <path>]
```

Validates HTML artifacts against the 24-case suite. The runner only reports what actually passes — it cannot fabricate results. Condition semantics in docs/benchmark-methodology.md.

## Configuration — raast.config.json

```json
{
  "language": "fa",
  "include": ["**/*.{html,css,tsx,md}"],
  "exclude": ["node_modules/**", "dist/**", ".raast-backup/**"],
  "severity_overrides": { "RTL003": "P2" },
  "rules": {
    "RTL001": { "force": true },
    "RTL010": { "allow_western_digits_in_prose": false }
  },
  "fail_on": "P1"
}
```

Validation is strict: unknown keys, bad rule ids, bad severities and unknown rule options raise a `ConfigError` (exit code 2). `"force": true` scans a rule even in files without Arabic-script evidence (off by default to keep false positives near zero).
