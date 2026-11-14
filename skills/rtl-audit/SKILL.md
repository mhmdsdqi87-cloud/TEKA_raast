---
name: rtl-audit
description: Review an existing page or component for RTL/Persian/Arabic bugs and produce a prioritized fix report. Use when the user asks to check, review, fix, or audit an RTL page, or when RTL output looks broken. Covers the 20-point checklist: dir attribute, letter-spacing, logical utilities, icon flips, bidi scrambles, fonts, digits, ZWNJ.
---

# RTL Audit — find the bugs a Persian user sees in 5 seconds

Run top-down. Output: severity-ordered report with exact line fixes. Severity: P0 = broken meaning/reading, P1 = visibly wrong, P2 = polish.

## P0 — reading is broken

1. **Missing `dir="rtl"`** on `<html>` (or on the subtree). Everything else is moot until set. Symptom: page reads left-to-right, punctuation floats at the wrong end.
2. **`letter-spacing` on Arabic-script text** — words visually shatter («م د ی ر ی ت»). Search CSS for `letter-spacing` and scope it to Latin-only classes.
3. **Font without Persian glyphs** for fa content — tofu, wrong ی/ک forms, or silent fallback font mid-paragraph. Check computed font on a Persian string in DevTools.
4. **Space instead of ZWNJ** in `«می شود»، «خانه ها»، «خوب تر»` patterns. Fix: `rtl-typography/scripts/fix-zwnj.py --apply`.
5. **Un-isolated LTR atoms** — phone `+98…` renders as `98+`, `$99` becomes `99$`, URLs break across lines wrongly. Wrap in `<bdi>`/`dir="ltr"`.

## P1 — visibly wrong

6. **Physical over logical**: any `text-left/right`, `ml-/mr-`, `pl-/pr-`, `left-/right-`, `border-l/r`, `rounded-l/r` on layout that should mirror → convert to logical utilities.
7. **Un-flipped directional icons**: next/arrow icons still pointing right on an RTL page (chevrons in breadcrumbs, carousels, list rows, "read more" links).
8. **Wrongly flipped non-directional icons**: clock, lock, search, check mirrored by an over-eager global `[dir=rtl] svg { transform: scaleX(-1) }` — remove that global rule; flip per-icon.
9. **Transforms not mirrored**: `translate-x` sliders/sheets moving the wrong way, carousel (embla/swiper) scrolling backwards (set `direction: rtl` in the lib), skeleton shimmer sliding wrong.
10. **Latin digits in Persian prose**: "5 ستاره", "2026" → «۵»، «۱۴۰۵». Exception: phone/serial/code blocks stay Western.
11. **Latin punctuation in Persian copy**: `, ? ! " "` → «، ؟ ! «»». One space after ، no space before.
12. **Form inputs fighting the user**: Persian name field forcing LTR caret, email field flipping text right. Name/message → `dir="auto"`; email/phone → `dir="ltr"`.
13. **Code blocks/commands in RTL flow**: `npm install …` mirrored → force `dir="ltr" text-align:left` on `pre/code` globally.
14. **Numbers/prices hand-rolled**: JS string concatenation producing «۱۰۰٬۰۰۰ تومان» wrongly or Arabic-Indic digits on a Persian page — route all numbers through `toLocaleString('fa-IR')`.

## P2 — polish

15. **Cramped line-height**: body < 1.8 for Persian looks suffocated → 1.8–2.0.
16. **Justified rivers**: `text-align: justify` without kashida → switch to `text-align: start`.
17. **Truncation edge cases**: `text-overflow: ellipsis` clipping the start of Persian words oddly; ensure min-width on flex children (`min-w-0`).
18. **Scrollbar side confusion**: mixed `dir` containers each getting own scrollbar; unify `dir` at document level.
19. **Mixed-script headings with baseline clash**: Persian font + Latin font inline → use one font family that covers Latin, or `<bdi>` with matched size.
20. **Missing `lang`**: `lang="fa"` absent → a11y readers pronounce Persian with wrong voice.

## Report format

Each finding carries: issue identifier (`RTL0xx` for machine-checkable rules from the `raast` CLI, `MANUAL-xx` for human-only checks), severity, affected component, reproduction steps, expected vs actual behavior, and remediation.

```md
## RTL Audit — <page>
- [RTL005/P0] letter-spacing .05em on .hero-title (styles.css:42) → remove; joining breaks
- [RTL011/P0] "می شود" ×3 in copy (hero.tsx) → run `raast fix --zwnj` or fix-zwnj.py --apply
- [RTL007/P1] next chevron points right (nav.tsx:88) → rtl:rotate-180 or ChevronLeft
- [RTL001/P1] margin-left on .card (theme.css:120) → margin-inline-start
- [MANUAL-02/P2] body line-height 1.5 → 1.9 for Persian
Summary: 2 P0, 2 P1, 1 P2 — page is not shippable until P0s are fixed.
```

Machine-checkable rules (`RTL001`–`RTL014`) are automated by the `raast` CLI — run `raast doctor <path>` for the same findings with exact file:line locations, then reserve human judgment for contrast, rhythm, and translation quality that static analysis cannot see.

When fixing, prefer the logical utilities from `rtl-components` so the component works in both directions.
