# Font glyph-coverage audit

The mechanical half of font correctness for RTL scripts: does each font
file a project ships actually contain the glyphs the language needs?
`raast fonts` answers that deterministically, from the font's `cmap` table,
with zero runtime rendering involved.

```bash
raast fonts ./public/fonts --language fa          # text report
raast fonts . --language fa --format json         # machine-readable
echo $?   # 0 = covered, 1 = at least one glyph gap, 2 = usage error
```

## What is checked

Per language profile, per font file (`ttf`, `otf`, `woff` parsed natively;
`woff2` via [fontTools](https://pypi.org/project/fonttools/) when installed):

| Group | fa | ar | he | es |
|---|---|---|---|---|
| letters | Arabic base + پ چ ژ گ ک ی آ | Arabic base | U+05D0–U+05EA | Latin + á é í ó ú ñ ü |
| digits | ۰–۹ (U+06F0–06F9) | ٠–٩ (U+0660–0669) | — (Western, shared) | 0–9 |
| punctuation | ، ؛ ؟ « » … | ، ؛ ؟ « » … | maqaf, geresh, gershayim, « » | ¿ ¡ « » … |
| format controls | ZWNJ (U+200C) | — | — | — |

A missing ZWNJ glyph is the silent killer of Persian prose: the character
is present in the text but renders as nothing (or worse, as .notdef), so
compounds like «می‌شود» break apart. That is why it is a first-class group,
not an afterthought.

Hebrew niqqud (U+05B0–U+05C7) is reported as an **optional** group — many
production Hebrew fonts deliberately drop niqqud; the audit surfaces the
fact without failing the run.

## What is deliberately NOT checked

- **Aesthetic quality.** Whether a font *looks* right — joining context,
  kerning, baseline rhythm, display-vs-body balance — needs a native human
  eye. See [review-program.md](review-program.md); the review program's
  artifact list includes the font catalogs for exactly this reason.
- **Hinting and browser rendering differences.** The same cmap can render
  differently across rasterizers; the runtime inspector (`raast-inspect`)
  and the browser suite remain the behavioral source of truth.
- **Fallback chains.** The audit checks each font file in isolation; whether
  your CSS `font-family` stack orders an RTL-capable font before the generic
  fallback is a code review question the doctor's font-related rules and
  skills cover.

## Output

Text (markdown) or `--format json` with a stable schema:

```json
{
  "language": "fa",
  "fonts_scanned": 1,
  "fonts": [
    {
      "file": "Vazirmatn-Bold.ttf",
      "format": "ttf",
      "status": "ok",
      "groups": { "letters": {"covered": 48, "total": 48, "missing_chars": ""} },
      "optional": {},
      "message": null
    }
  ],
  "gaps": 0,
  "warnings": 0
}
```

Statuses: `ok` (all required groups covered) · `gaps` (missing glyphs —
exit 1) · `unsupported` (e.g. WOFF2 without fontTools — warning) ·
`unreadable` (corrupt/unparseable — warning). Warnings never fail CI; a
font you cannot parse is a packaging problem to fix, not a proven glyph gap.

## CI usage

```yaml
- name: Font glyph coverage (fa)
  run: raast fonts ./assets/fonts --language fa
```
