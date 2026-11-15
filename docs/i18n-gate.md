# Language Quality Gate (`raast-i18n`)

RAAST started as an RTL page auditor: the static engine in `raast.rules`
(namespace RTL001-017) scans rendered pages for physical CSS, missing `dir`,
broken ZWNJ and bidi problems. The Language Quality Gate extends the same
P0/P1/P2 discipline one step upstream, to the locale files that feed those
pages. It compares every target locale against a source locale and reports
translation-quality findings with its own rule namespace **LQG001-009**.

Zero dependencies (stdlib only, Python 3.11+). Runs as a module:

```
python3 -m raast.i18n scan --locales <dir> [options]
```

(A `raast-i18n` console script wiring is planned alongside `raast = raast.cli:main`.)

## What it checks and why

Locale files fail silently: a missing key renders empty text or throws at
runtime depending on the i18n library; a placeholder mismatch crashes
`str.format`/printf or leaks raw braces into the UI; untranslated strings ship
source-language copy straight to production; and Arabic Yeh/Kaf pasted from an
Arabic keyboard into a Persian string is a classic copy-paste bug that breaks
Persian search and spellchecking while looking almost right. All of these are
invisible in code review and expensive to catch in QA — so the gate catches
them before they ship.

## Checks

| Rule | Sev | Fires when | Example |
|---|---|---|---|
| LQG001 | P1 | A key exists in the source locale but is absent from a target. | `checkout.total` present in `en`, absent in `fa` |
| LQG002 | P1 | A target value is `""` or whitespace-only. | `"status.error": ""` |
| LQG003 | P1 | The placeholder set of the target differs from the source (missing or extra). | source `{name} {count}` vs target `{name}` |
| LQG004 | P2 | Target value is exactly identical to the source value and looks like translatable prose (at least 4 Latin letters). | `"settings.language": "Language"` in `fa` |
| LQG005 | P2 | `len(target) > 2.5 x len(source)`, or the source is longer than 20 chars and `len(target) < 0.4 x len(source)`. | 115-char translation of `"New"` |
| LQG006 | P2 | Arabic-script prose (targets `fa`/`ar`, or any value that is majority Arabic-script; `he`/`es` exempt) contains Latin sentence punctuation `, ? ! ;` or bare Western digits `0-9`. | `"5 ? فقط"` in Persian |
| LQG007 | P2 | An RTL-majority value contains a run of 3+ Latin characters with no bidi isolation (no U+2066-U+2069, no LRM/RLM U+200E/U+200F around the run, no `<bdi>` markup). | `"تماس با Support 24/7 ما"` |
| LQG008 | P1 | A Persian (`fa`) value contains Arabic YEH U+064A or Arabic KAF U+0643; Persian requires U+06CC and U+06A9. | `"ذخیره كنيد"` with Arabic `ك` |
| LQG009 | P2 | A Hebrew (`he`) value contains niqqud U+0591-U+05C7. **Opt-in:** only reported with `--hebrew-diacritics`. | `"בְּחִירָה"` in production copy |

Rule IDs are stable and shared with this document, the module docstring and
the fixture corpus in `tests/fixtures/locales/` — a fixture plants exactly one
instance of LQG001-LQG008 so every rule is reproducible.

## Usage

Scan a Next.js-style `locales/` directory (works with `locales/en.json` or
`locales/en/common.json` layouts):

```
python3 -m raast.i18n scan --locales locales/ --source en
```

JSON output for CI or dashboards:

```
python3 -m raast.i18n scan --locales locales/ --format json > i18n-report.json
```

Exit-code gating — the gate exits 1 when the number of P0+P1 findings exceeds
`--max-errors` (default 0). P2 findings never gate:

```
python3 -m raast.i18n scan --locales locales/ --max-errors 0
# CI step: any missing key, empty value, placeholder mismatch or Arabic-Yeh bug fails the build
```

Full option set:

```
python3 -m raast.i18n scan --locales DIR
    [--source en]                  # source locale code (default: en)
    [--targets fa,ar,he,es]        # default: every discovered locale except the source
    [--format text|json|markdown]  # default: text
    [--max-errors N]               # exit 1 when P0+P1 findings exceed N (default: 0)
    [--hebrew-diacritics]          # opt-in: also flag niqqud in Hebrew strings (LQG009)
```

Exit codes: `0` clean (or only P2 findings within the threshold), `1` too many
P0+P1 findings, `2` usage error — bad directory, missing source locale, or a
locale file that is unreadable/invalid JSON (the offending filename is part of
the error message).

### Locale discovery

- `*.json` directly in the directory: locale code = file stem (`en.json` -> `en`).
- One level of subdirectories containing `*.json`: locale code = the
  subdirectory name (`en/common.json` -> `en`); all JSON files inside merge in
  sorted-filename order, later files win per key. Deeper nesting is ignored.
- If both `DIR/en.json` and `DIR/en/*.json` exist, the subdirectory wins on
  conflicting keys.
- Hidden entries (leading `.`) are skipped; non-JSON files are ignored.

### Parsing rules

- UTF-8 with BOM tolerated; duplicate object keys resolve last-wins (stdlib
  `json.loads` behavior, relied upon and documented rather than hidden).
- Nested objects flatten to dot-path keys (`nav.home`).
- **Arrays are treated as a single leaf value whose items are joined with
  `" | "`** — kept deliberately simple, so `["Docs", "Blog"]` compares as the
  string `"Docs | Blog"`. Item-level array comparison is not attempted.
- Keys present only in a target (dead keys) are ignored — LQG001 is
  source-to-target only.

### Placeholder syntaxes

| Syntax | Extracted token | Notes |
|---|---|---|
| `{name}`, `{0}` | `{name}`, `{0}` | Python `str.format` / generic named+indexed |
| `{{name}}` | `{{name}}` | Handlebars-style interpolation. Caveat: inside Python `str.format` `{{...}}` is an escaped literal brace — the gate compares tokens as written, so `{name}` and `{{name}}` are distinct |
| `%s`, `%d` | `%s`, `%d` | printf-style |
| `%1$s`, `%2$d` | `%1$s`, `%2$d` | positional printf; tokens are compared as written, so `%s` and `%1$s` count as different tokens |

The comparison is **set equality**: order and multiplicity are ignored
(`{a} {a}` vs `{a}` passes; counting duplicates is roadmap work).

### Language profiles

`fa`/`ar` conventions (digit shapes, punctuation) are read from
`raast.profiles.load_profile` — the same profiles that drive the RTL engine —
so the gate and the prose rules cannot drift apart. If a profile is missing or
unreadable (`ProfileError`), the gate falls back to built-in defaults (fa/ar
are treated as Arabic-script RTL with invalid Western digits in prose; unknown
locale codes are gated by per-value Arabic-script majority instead), so the
module also runs standalone without profile data.

## Output formats

- `text` — one line per finding, grouped by locale, then a summary line.
- `json` — machine-readable: `{"locales", "source", "keys_checked",
  "findings", "summary", "warnings"}`; each finding is
  `{rule, severity, confidence, locale, key, message, explanation, suggested_fix}`.
  `keys_checked` counts every (source key, target locale) comparison.
- `markdown` — one `Rule | Key | Sev | Issue | Fix` table per locale plus a
  summary; includes a note that these locale-file checks complement the
  page-level RTL015-017 host checks (locale files here, rendered pages there).

## Worked example

The fixture corpus `tests/fixtures/locales/` is a deliberate error corpus
(see its README): `fa.json` plants exactly one instance of LQG001-LQG008 and
keeps several correct keys; `es.json` is complete and clean except one planted
LQG004. Scanning it produces, verbatim:

```
$ python3 -m raast.i18n scan --locales tests/fixtures/locales --source en --format text
raast-i18n scan — tests/fixtures/locales (source: en, targets: es, fa)
== es ==
LQG004 P2 [es] settings.language — value is identical to the en source: "Language"
== fa ==
LQG005 P2 [fa] badge.new — translation length 115 is 38.3x the source length 3
LQG003 P1 [fa] checkout.greeting — placeholder mismatch — missing in fa: {count}
LQG001 P1 [fa] checkout.total — key missing in fa (present in en)
LQG006 P2 [fa] price — Western digit(s) 5 and Latin punctuation (?) in Persian prose
LQG008 P1 [fa] save — Arabic letter(s) ك (U+0643) and ي (U+064A) in Persian text — Persian uses ی (U+06CC) and ک (U+06A9)
LQG004 P2 [fa] settings.language — value is identical to the en source: "Language"
LQG002 P1 [fa] status.error — value is empty or whitespace-only
LQG007 P2 [fa] support — un-isolated Latin run(s) in RTL text: Support
2 locale(s), 50 keys checked, 9 findings (P0:0 P1:4 P2:5)
```

The same scan exits `1` (4 P1 findings > `--max-errors 0`). A directory
containing only `en.json` + `es.json` exits `0` — the single LQG004 is P2 and
P2 never gates. `--hebrew-diacritics` only changes output for `he` targets:
with a Hebrew file containing niqqud the gate reports LQG009; without the flag
it stays silent.

## Limitations (honest)

- **JSON only.** `.po`, `.arb`, `.xliff` and YAML locale formats are not
  parsed yet — roadmap.
- **Length heuristics are P2 for a reason.** Legitimately long translations
  (German compounds, legal copy) will trigger LQG005; that is a review nudge,
  never a CI gate. The 2.5x / 40% thresholds are not linguistically justified,
  only empirically useful.
- **String-level only.** The gate validates keys, placeholders, script and
  length — not grammar, terminology, tone, or whether the translation is
  actually *good*. Human review remains necessary (`raast audit` lists it).
- **Placeholder sets, not counts.** Duplicate placeholders are compared as
  sets; `{a} {a}` vs `{a}` passes.
- **`{{name}}` ambiguity.** Treated as a placeholder token as written; in
  Python `str.format` semantics it would be an escaped brace.
- **Isolation detection is adjacency-based.** A Latin run is considered
  isolated only when U+2066-U+2069 / U+200E / U+200F sits immediately next to
  it, or the run is inside `<bdi>...</bdi>`. An isolate elsewhere in the same
  string does not excuse an unmarked run.
- **Bare Western numbers only in LQG006.** Digit tokens that mix with Latin
  letters or code-like separators (`24/7`, `1.2.3`, `v2`, `SAR99`) are treated
  as LTR atoms and left to the page-level RTL010 engine.
- **Dead keys are ignored.** Keys present only in a target locale are not
  reported (roadmap).
- Dot-colliding keys (`"a.b"` vs `{"a": {"b": ...}}`) are ambiguous after
  flattening; last write wins.

## Relation to the RTL engine

LQG findings cover locale *files*. They complement — not replace — the
page-level host checks RTL015-017 (un-isolated RTL atoms, unmarked RTL runs
and missing inverted marks in LTR pages), which scan rendered pages. A clean
locale scan does not guarantee a correct rendered page; run both.
