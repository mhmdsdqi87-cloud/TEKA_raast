# RTL Engineering Rules for AI Coding Agents

Copy this file as `AGENTS.md` at your repository root (or merge it into your existing one).
It is read by Codex CLI, OpenAI-compatible agents and most tools that follow the
[agents.md](https://agents.md) convention. Cursor/Copilot users: use the dedicated files in
this folder instead.

Scope: every page, component or template that renders Persian (fa), Arabic (ar) or Hebrew (he)
text — full pages, embedded fragments, or LTR host pages that display RTL content (e.g. a
Spanish page showing Arabic names).

## Non-negotiables (break these and the page is broken, not just ugly)

1. **`<html lang="…" dir="rtl">` on RTL pages.** Never `dir="ltr"` on a page whose content is
   RTL script. On LTR host pages (Spanish, English) the root stays LTR and each RTL region
   declares `dir="rtl"`.
2. **No `letter-spacing` on Arabic-script text.** Arabic letters are joined; spacing breaks the
   cursive connections and words become unreadable («مدیریت» renders as م د ی ر ی ت).
   Exception: Hebrew tolerates small tracking, but it is still discouraged — nikud clipping.
3. **Logical CSS properties, not physical.** `margin-inline-start`, `padding-inline-end`,
   `inset-inline-start`, `text-align: start`. Physical `left/right/margin-left/padding-left`
   point at the wrong edge in RTL.
4. **ZWNJ (U+200C) in Persian compounds.** `می‌شود`, `خانه‌ها`, `بهتر‌ترین` use half-space;
   a full space breaks the word. Never insert ZWNJ in Arabic or Hebrew — they don't use it.
5. **Isolate every mixed-direction run.** URLs, emails, `$99`, phone numbers, foreign names
   inside RTL prose: wrap in `<bdi>` or give the container `dir="auto"`. `$99` becomes `99$`
   otherwise.
6. **Numerals follow the profile.** fa: ۰-۹ · ar: ٠-٩ · he: 0-9 (Western digits are correct in
   Hebrew) · es host: 0-9. Never convert digits inside code, URLs or APIs.
7. **Line-height ≥ 1.5** for Arabic-script body text (1.6 recommended; Hebrew needs vertical
   room for nikud). Compact 1.2–1.4 clipping is a defect.
8. **Fonts must carry the script's glyphs.** fa: Vazirmatn, Sahel, IRANSansX · ar: Noto Naskh
   Arabic, Cairo, Tajawal · he: Heebo, Assistant, Rubik. A Latin-only stack shows tofu or
   falls back inconsistently.

## Tailwind specifics

- `ms-` / `me-` / `ps-` / `pe-` / `text-start` / `text-end` instead of `ml-` / `mr-` / `pl-` /
  `pr-` / `text-left` / `text-right`.
- `rtl:` and `ltr:` variants for directional motion: `translate-x-4 rtl:-translate-x-4`.
- Flip direction-aware icons (arrows, chevrons, indent, reply, exit): use
  `rtl:-scale-x-100` or directional variants. Do NOT flip: logos, media controls, clocks,
  avatars, checkmarks.

## Dates and formatting

- Never hand-roll calendar math. fa: `new Intl.DateTimeFormat('fa-IR')` gives Jalali + Persian
  digits. he: `new Intl.DateTimeFormat('he-IL-u-ca-hebrew')`. Store ISO-8601 in UTC, format at
  render time, format on the server for SSR to avoid hydration mismatches.

## Punctuation

- fa: ، ؟ ؛ «» · ar: ، ؟ ؛ «» · he: `,` `?` `;` (Latin marks are correct in modern Hebrew) plus
  gershayim ״ / geresh ׳ / maqaf ־ conventions · es host: «» and RAE inverted marks ¿ ¡ are
  required — a question without ¿ is a defect.

## Verify, don't assume

Run the audit before shipping any RTL change:

```bash
pip install raast
raast doctor ./your-project --language fa   # or ar / he / es
```

17 static rules, exit-code severity gate, GitHub Action available
(`mhmdsdqi87-cloud/TEKA_raast/action@main`). Rule IDs `RTL001`–`RTL017`; findings carry
severity (P0 = shipping broken, P1 = wrong but readable, P2 = review) and confidence.

Full reference: [RAAST skills](https://github.com/mhmdsdqi87-cloud/TEKA_raast/tree/main/skills)
— six focused Markdown playbooks (typography, landing pages, components, bidi, Jalali dates,
audit checklist).
