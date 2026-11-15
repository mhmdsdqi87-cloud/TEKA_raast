# RTL Engineering Rules (GitHub Copilot instructions)

Copy this file to `.github/copilot-instructions.md` in your repository. GitHub Copilot picks it
up automatically for chat and inline suggestions. Codex CLI users: use `AGENTS.md` in this
folder; Cursor users: use `cursor-rtl.mdc`.

## When building or editing UI that renders Persian (fa), Arabic (ar) or Hebrew (he)

1. Root element: `<html lang="fa" dir="rtl">` on RTL pages. Never `dir="ltr"` there. On LTR
   host pages keep the root LTR and mark each RTL region `dir="rtl"`.
2. Use logical CSS properties only: `margin-inline-start/end`, `padding-inline-start/end`,
   `inset-inline-start/end`, `text-align: start/end`. Do not generate `margin-left`,
   `padding-right`, `text-align: left`, `left:`, `right:` in RTL contexts.
3. Never emit `letter-spacing` for Arabic-script text (breaks cursive joining). For Hebrew it
   is discouraged, not forbidden.
4. Persian half-space (ZWNJ, U+200C): `می‌شود`, `خانه‌ها`, `بیشتر‌ین`. Never place ZWNJ in
   Arabic or Hebrew text.
5. Wrap URLs, emails, `$prices`, phone numbers and Latin brand names inside RTL prose in
   `<bdi>` or containers with `dir="auto"`.
6. Numerals: fa ۰-۹, ar ٠-٩, he 0-9, es 0-9. Do not convert digits inside code samples, URLs
   or API payloads.
7. Tailwind: `ms-/me-/ps-/pe-/text-start/text-end`, `rtl:` variants for motion; flip
   direction-aware icons with `rtl:-scale-x-100` (arrows, chevrons, indent, reply, exit) —
   never flip logos, media controls, clocks or avatars.
8. Body line-height at least 1.5 for Arabic script (1.6 recommended); Hebrew needs room for
   nikud marks.
9. Fonts: fa — Vazirmatn / Sahel / IRANSansX; ar — Noto Naskh Arabic / Cairo / Tajawal;
   he — Heebo / Assistant / Rubik. Latin-only stacks are a defect.
10. Dates: `Intl.DateTimeFormat('fa-IR')` for Jalali (fa), `Intl.DateTimeFormat('he-IL-u-ca-hebrew')`
    for the Hebrew calendar. Store ISO-8601 UTC; format server-side for SSR consistency.
11. Spanish host pages: RAE inverted marks ¿ ¡ are mandatory; wrap embedded RTL runs in
    `<bdi>`; keep `<html>` LTR.
12. Punctuation: fa/ar use ، ؟ ؛ «» — never Latin `,` `?` `;` next to Arabic-script letters.
    Modern Hebrew uses Latin `,` `?` `;` plus gershayim ״ / geresh ׳ / maqaf ־ conventions.

## Before finishing any RTL task

Verify with the audit CLI (17 rules, severity-gated):

```bash
pip install raast && raast doctor . --language fa
```

or wire the GitHub Action: `uses: mhmdsdqi87-cloud/TEKA_raast/action@main`.

Deep references: the six RAAST skills in
[mhmdsdqi87-cloud/TEKA_raast](https://github.com/mhmdsdqi87-cloud/TEKA_raast/tree/main/skills)
(typography, landing pages, components, bidi, Jalali dates, 20-point audit).
