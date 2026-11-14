---
name: rtl-typography
description: Core typography rules for Persian (Farsi) and Arabic web interfaces. Use when building or styling any UI containing Persian/Arabic/Farsi text, or when the user mentions فارسی، عربی، RTL، نیم‌فاصله، فونت فارسی. Covers font selection, ZWNJ (نیم‌فاصله), Persian numerals, punctuation, line-height, and forbidden patterns like letter-spacing on Arabic script.
---

# RTL Typography: Persian & Arabic done right

This skill encodes the typography layer for right-to-left interfaces. Follow it whenever text on the page is Persian or Arabic. For full-page builds see `rtl-landing`, for component patterns see `rtl-components`.

## 1. Document setup — always first

```html
<html lang="fa" dir="rtl">
```

- Set `lang` AND `dir` together. `lang="fa"` for Persian, `lang="ar"` for Arabic.
- Never simulate RTL with `text-align: right` on an LTR document. Browsers, screen readers, form controls, and scrollbars all key off `dir`.
- Every alignment must use logical values: `text-align: start`, not `left`.

## 2. Fonts

Use a font designed for the language. A font that lacks Persian glyphs renders broken/tofu shapes or substitutes silently.

Reliable choices (details + CDN snippets in [fonts.md](fonts.md)):

| Use case | Persian | Arabic |
|---|---|---|
| Body/UI (default) | Vazirmatn | IBM Plex Sans Arabic |
| Display/headlines | Lalezar, Estedad | Cairo, Changa |
| Editorial/serif feel | Markazi Text, Parastoo | Noto Naskh Arabic |
| Familiar/system feel | Sahel, Shabnam | Tajawal, Almarai |

Stack pattern — always name a fallback, and let one font cover Latin:

```css
font-family: 'Vazirmatn', Tahoma, sans-serif;
```

Load only `woff2`, use `font-display: swap`, subset weights you use (400, 500, 700 is usually enough).

## 3. NEVER use letter-spacing on Arabic script

This is the single most common AI-generated RTL bug.

Arabic-script letters are **cursive and joined**. `letter-spacing` inserts gaps between joined glyphs, visually shattering words: «مدیریت» becomes م د ی ر ی ت.

```css
/* WRONG — breaks joining */
.hero-title { letter-spacing: 0.05em; }

/* RIGHT — if you need wider display text, use size/weight instead */
.hero-title { font-weight: 800; font-size: 3rem; }
```

Rule: `letter-spacing: 0` or unset for any Arabic-script text. Tracking tricks (uppercase, wide tracking) don't apply anyway — Arabic script has no case.

## 4. Line-height and rhythm

Arabic-script line boxes are taller than Latin (ascenders/descenders + diacritics). Latin defaults look cramped.

- Persian body text: `line-height: 1.8`–`2.0` (1.9 is a safe default)
- Arabic body text: `line-height: 1.6`–`1.8`
- Headings: `1.3`–`1.4`
- Persian text runs ~10–15% wider than English for the same content — budget wider buttons, more paragraph width, don't over-truncate.

Justification: prefer start-aligned (ragged) text. Browser justification without kashida support creates ugly rivers between words.

## 5. ZWNJ — نیم‌فاصله (U+200C)

Persian compounds and affixes are written with a Zero-Width Non-Joiner between parts. Missing ZWNJ is the most visible spelling defect in generated Persian copy.

### Correct usage table

| Wrong (space or joined) | Correct (with U+200C) |
|---|---|
| می رود | می‌رود |
| نمی شود | نمی‌شود |
| می خواهم | می‌خواهم |
| خانه ها | خانه‌ها |
| کتاب های | کتاب‌های |
| بهترین ها | بهترین‌ها |
| خوب تر | خوب‌تر |
| برنامه نویسی | برنامه‌نویسی |
| راه اندازی | راه‌اندازی |
| ورود به سیستم می پردازد | ورود به سیستم می‌پردازد |

Rules of thumb:
- Prefixes `می`, `نمی`, `بی`, `هم`, `نا`, `باز` + verb/adjective → ZWNJ: می‌گوید، نمی‌دانست، بی‌نقص، هم‌گام
- Suffixes `ها`, `های`, `تر`, `ترین` after a word → ZWNJ: پرنده‌ها، کتاب‌های، بزرگ‌تر، بزرگ‌ترین
- Compound nouns from the Academy wordlist → ZWNJ: راه‌اندازی، برنامه‌نویسی، نرم‌افزار، ذخیره‌سازی
- Possessive suffixes `ام/ات/اش` are written joined: کتابم، خانه‌ات — do NOT insert ZWNJ there.

When generating Persian copy, write ZWNJ natively (not a space). To sanitize existing text, use the bundled script:

```bash
python3 scripts/fix-zwnj.py draft.md            # dry-run diff
python3 draft-output.md > fixed.md --apply ...  # see --help
```

The script joins common broken patterns (`می رود`, `خانه ها`, `خوب تر`), converts Arabic `ي ك` to Persian `ی ک`, and never touches code blocks or URLs.

## 6. Numerals

| Language | Digits | Unicode range |
|---|---|---|
| Persian | ۰۱۲۳۴۵۶۷۸۹ | U+06F0–U+06F9 |
| Arabic | ٠١٢٣٤٥٦٧٨٩ | U+0660–U+0669 |
| Latin (embedded contexts) | 0123456789 | U+0030–U+0039 |

- Copy written in Persian uses Persian digits: «۵ دلیل»، «۲۴ ساعت».
- Prices: `۱۲۵٬۰۰۰ تومان` — thousands separator is U+066C (٬), decimal is U+066B (٫).
- Percent after the number, no space: `۱۲٪` (Arabic percent sign U+066A).
- Never hand-format these: use JS locale APIs.

```js
(125000).toLocaleString('fa-IR')   // "۱۲۵٬۰۰۰"
(12.5).toLocaleString('fa-IR')     // "۱۲٫۵"
new Intl.NumberFormat('fa-IR', { style: 'percent' }).format(0.12)  // "۱۲٪"
```

Keep Western digits only inside inherently-LTR atoms: phone numbers, URLs, code, prices in foreign currency.

## 7. Punctuation — Persian marks in Persian text

| Purpose | Persian/Arabic | Don't use |
|---|---|---|
| Comma | ، (U+060C) | , |
| Question mark | ؟ (U+061F) | ? |
| Semicolon | ؛ (U+061B) | ; |
| Quotation | «متن» | "متن" |
| Decimal / thousands | ٫ ٬ | . , |
| Percent | ٪ (U+066A) | % |

Ellipsis is `…`, not three dots. No space before ، ؟ ؛ ; one space after.

## 8. Persian vs Arabic — decide first

They are different languages with different conventions. Confirm which one before styling:

- Digits: fa → ۱۲۳ (U+06F0), ar → ١٢٣ (U+0660)
- Letters: Persian ی/ک vs Arabic ي/ك — a Persian font must include Persian forms
- Punctuation overlap but tone/idiom differ
- A Persian-only font on an Arabic page shows wrong letter forms for ک/ی and vice versa

The machine-readable conventions (digit ranges, separators, punctuation, affix lists) live in `profiles/fa.json` and `profiles/ar.json` — the same files the `raast` CLI consumes, so prose rules and automated checks never drift apart.

## 9. Copy, paste, selection & rendering

Arabic-script text breaks in copy/paste and selection more often than Latin. Rules:

- **Selection rendering**: set `::selection` with sufficient contrast (Arabic-script glyph clusters extend below the line; a thin highlight band visually slices them). Padding on `::selection` helps.
- **Copy/paste integrity**: never insert ZWNJ programmatically into areas users may paste into plain-text fields; on paste *into* the page, keep the pasted text byte-exact (no auto-"cleanup" of U+200C, U+200E/F, U+061C Arabic letter mark). Removing invisible chars silently corrupts Persian search and spelling.
- **`user-select: all`** on quotes/citations so guillemets stay attached.
- **Copy-to-clipboard components** (price, tracking number) must copy the logical string, not the visually reordered one — test with a RTL page + LTR clipboard viewer.
- **Font rendering flags**: prefer `text-rendering: optimizeLegibility`; do NOT use `font-synthesis` weights on Arabic display faces (fake bold breaks naskh rhythm) — load real weights.
- **Warnings on ambiguous transformations**: normalizing Arabic-Indic digits (٠١٢) to Persian (۰۱۲) is safe in fa content, destructive in ar content. Any automated conversion must be language-gated — see `references/normalization.md` for the decision table.

## 10. Mixed-script basics (details in rtl-bidi skill)

- Phone/email/URL/code inside Persian text: wrap in `<bdi>` or a `dir="ltr"` span.
- Code blocks: always `dir="ltr"` + `text-align: left`, even on RTL pages.
- User-generated inputs: `dir="auto"` so each input adapts to its own content.

## 11. Pre-flight checklist

- [ ] `<html lang="fa|ar" dir="rtl">` set
- [ ] Font covers the language; fallback named
- [ ] `letter-spacing` absent on Arabic-script text
- [ ] Body line-height ≥ 1.8 (Persian)
- [ ] All affixes use real U+200C, not spaces
- [ ] Persian digits + ٬ ٫ ٪ ٬ in copy; Latin digits only in LTR atoms
- [ ] Persian punctuation ، ؟ ؛ «» in copy
- [ ] Alignments use `start`/`end`, never `left`/`right`
