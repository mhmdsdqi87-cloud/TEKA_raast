# CLI Reference — `raast`

Zero-dependency Python CLI (3.11+). Install: `pip install -e .` from the repo root, or run as a module: `python3 -m raast.cli`.

Global: `raast --version`

## raast profiles

```
raast profiles
```

Lists the language profiles that ship with the installed CLI — native name, English name, direction (`rtl`/`ltr`). The first command to run when a profile question comes up; profiles are package data, so this works from any wheel install without a repo checkout.

## raast init

```
raast init [path] [--language fa|ar|he|es] [--force]
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
             [--fail-on P0|P1|P2] [--language fa|ar|he|es] [--config <file>]
```

Static diagnostics. `path` may be a directory or a single file.

- `--format github` emits `::error`/`::warning` annotations for Actions.
- `--fail-on P0` exits 1 when P0 findings exist (default comes from config `fail_on`).
- `--language` overrides the profile from config (`fa`, `ar`, `he`, `es`).
- Exit codes: 0 clean, 1 findings >= threshold, 2 config/profile error.

Language behavior is profile-driven: `fa`/`ar` enforce their own digits and punctuation in prose, `he` keeps Western digits and Latin punctuation valid while flagging discouraged letter-spacing at P1, and `es` (LTR host) flips the engine — RTL runs inside Spanish prose must be isolated (RTL015), RTL-run elements need `dir` (RTL016), and RAE inverted marks ¿ ¡ are checked (RTL017).

## raast audit

```
raast audit [path]
```

`doctor --format markdown` plus the manual-review checklist (contrast, rhythm, translation quality, icon direction) that static analysis cannot automate.

## raast fix

```
raast fix [path] [--apply] [--diff] [--tier safe|all] [--zwnj] [--zwnj-digits] [--zwnj-punct] [--config <file>]
```

Auto-fix with a three-tier safety policy (full policy: docs/auto-fix.md):

- **safe tier** (default, `--tier safe`) — mechanical, reversible transformations applied automatically:
  - physical declarations → logical (`margin-left` → `margin-inline-start`, `text-align: left` → `start`)
  - removal of non-zero `letter-spacing` on Arabic-script files
  - Tailwind class renames (`ml-4` → `ms-4`, `text-left` → `text-start`)
  - `--zwnj`: safe U+200C joins per the normalization decision table
- **suggested tier** (included only with `--tier all`, still opt-in per flag) — context-sensitive conversions: `--zwnj-digits` / `--zwnj-punct` (language-gated, fa only; disabled for ar automatically)
- **manual tier** — never auto-applied. Positioning semantics, `dir` placement, icon intent, i18n decisions need human judgment; these findings are listed as review items instead.

Dry-run is the default and prints unified diffs. `--apply` writes backups to `.raast-backup/` (excluded from future scans) and records a machine-readable journal (`.raast-backup/journal.json`: timestamp, file, rules applied, fix count). A tier breakdown is printed with every run.

## raast revert

```
raast revert [path] [--yes]
```

Restores every file recorded in the fix journal to its pre-fix content (byte-identical), removes the consumed backups and clears the journal. Without `--yes` it prints the plan first (interactive confirmation only in a TTY). If backups exist without a usable journal, revert refuses honestly rather than guessing.

## raast report

```
raast report [path] --output raast-report.md
```

Writes the markdown report artifact.

## raast fonts

```
raast fonts <path> [--language fa] [--format text|json]
```

Font glyph-coverage audit: parses the cmap table of every font file found
under `<path>` (`.ttf`/`.otf`/`.woff` natively; `.woff2` via fontTools when
installed) and checks it against the required letters, digits, punctuation
and format controls of the language profile. Exit `1` when any font has a
real glyph gap; unreadable/unsupported formats are warnings, not failures.
Methodology and honest limits: docs/font-audit.md.

## raast benchmark

```
raast benchmark --candidate <dir> [--cases <dir>] [--condition C-reference] [--json] [--output-prefix <path>]
```

Validates HTML artifacts against the 24-case suite. The runner only reports what actually passes — it cannot fabricate results. Condition semantics in docs/benchmark-methodology.md.

## raast-review — diff-scoped PR review

```
raast-review --base origin/main [--path .] [--config <file>]
             [--fail-on P0|P1|P2|off] [--comment-out FILE] [--format markdown|github]
```

Scans ONLY the lines changed between the merge base and HEAD (rules RTL001–RTL017), so legacy issues outside the diff never appear. `--format github` emits Actions annotations; `--comment-out` writes a marker-based markdown comment body that the bundled workflow (`.github/workflows/pr-review.yml`) posts/updates idempotently on the PR. Exit codes: 0 clean, 1 findings ≥ threshold, 2 engine error. Full anatomy and limitations: docs/pr-review.md.

## raast-i18n — language quality gate

```
raast-i18n scan --locales <dir> [--source en] [--targets fa,ar,he,es]
                [--format text|json|markdown] [--max-errors N] [--hebrew-diacritics]
```

Scans locale JSON files for translation-quality defects (rules LQG001–LQG009): missing keys, empty values, placeholder mismatches, untranslated strings, length anomalies, Western digits / Latin punctuation in Arabic-script prose, un-isolated Latin runs in RTL values, Arabic Yeh/Kaf in Persian strings, opt-in niqqud. `--max-errors N` gates the exit code on P0+P1 counts. Full check table: docs/i18n-gate.md.

## raast-inspect — runtime (browser) inspection

```
raast-inspect inspect (--url URL | --file FILE) --out DIR
                  [--viewport WxH ...] [--wait MS] [--max-elements N] [--skip-mirror]
```

Requires the optional dependency group: `pip install 'raast[runtime]' && playwright install chromium`. Renders the page in headless Chromium, collects per-element geometry, then flips the document direction and measures again. Reports rendered-only defects (rules RT001–RT006): horizontal overflow, page-level overflow, clipped text, asymmetric mirroring, unflipped directional icons, un-isolated mixed-direction text — each with a selector, severity, suggested fix and before/after screenshots in `--out` (report.json, report.md, PNGs). Complements `raast doctor`; it does not replace static analysis. Details: docs/runtime-inspector.md.

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

Validation is strict: unknown keys, bad rule ids, bad severities, unknown rule options and unknown languages raise an error (exit code 2, with the list of available languages). `"force": true` scans a rule even in files without RTL-script evidence (off by default to keep false positives near zero).
