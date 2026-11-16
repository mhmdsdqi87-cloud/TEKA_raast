# RTL engineering brief (condition B — "with skills")

This file is the exact expertise appendix injected into the model for
condition B of the AI benchmark (see README.md in this directory). It is a
faithful condensed digest of the six RAAST skills; it carries no
model-specific instructions and changes only when the skills change.
Condition A runs the identical prompt without this appendix.

---

Apply these RTL / right-to-left engineering rules to the page you build:

1. Document setup — `<html lang="fa" dir="rtl">` for Persian (`ar`/`he`
   analogous: `lang="ar" dir="rtl"`, `lang="he" dir="rtl"`). Never emit
   `dir="ltr"` on an element whose content is only RTL-script.

2. Layout — use logical CSS properties everywhere on the inline axis:
   `margin-inline-start/end`, `padding-inline-start/end`,
   `inset-inline-start/end`, `text-align: start/end`. Never hardcode
   `margin-left/right`, `padding-left/right`, physical `left:/right:`
   positioning for layout anchors, or `text-align: left/right`.

3. Tailwind (if used) — `ms-*`, `me-*`, `ps-*`, `pe-*`, `start-*`, `end-*`,
   `text-start`, `text-end`. Avoid `ml-*`/`mr-*`/`pl-*`/`pr-*`/`text-left`/
   `text-right`. `translate-x-*` needs an explicit `rtl:` twin or it breaks
   mirroring.

4. Persian typography — join compound words with ZWNJ (U+200C): «می‌شود»,
   «کتاب‌ها», «می‌توانند». Use Persian digits ۰–۹ in prose and Persian
   punctuation ، ؛ ؟ and guillemets « ». Never apply `letter-spacing` to
   Arabic-script text — joined glyphs shatter («مدیریت» becomes
   م د ی ر ی ت); emphasize with weight/size instead.

5. Arabic typography — Arabic-Indic digits ٠–٩ in prose, Arabic punctuation
   ، ؛ ؟. Same letter-spacing ban.

6. Bidi isolation — wrap LTR atoms inside RTL prose (URLs, phone numbers,
   `$` amounts, file names, Latin code) in `<bdi>` or `dir="ltr"` spans so
   punctuation and numbers do not jump sides. Code blocks are
   `dir="ltr"` with `text-align: left`.

7. Dates — for Persian dates use
   `new Intl.DateTimeFormat("fa-IR-u-ca-persian", ...)`; never hardcode a
   manual Gregorian→Jalali conversion table.

8. Components — directional arrows must mirror: in RTL, "next" points
   left. Icon-only buttons need `aria-label`.

9. Page quality — `<meta name="viewport" ...>`, `alt` text on every
   `<img>`, responsive behavior via media queries / `clamp()` / grid or
   flex wrapping.

10. Fonts — declare an RTL-script-capable family (e.g. `Vazirmatn`,
    `Estedad` for Persian) before any generic fallback in `font-family`.
