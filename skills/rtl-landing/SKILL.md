---
name: rtl-landing
description: Build complete Persian or Arabic RTL landing pages end-to-end. Use when the user asks for a landing page, marketing site, or product page in Persian/Farsi/Arabic, or says لندینگ فارسی، صفحه محصول، سایت فارسی. Covers section-by-section structure, copywriting with correct ZWNJ, pricing in Toman, and the anti-slop design rules for RTL.
---

# RTL Landing Pages (Persian / Arabic)

End-to-end recipe for a marketing/landing page in Persian or Arabic. Typography rules come from `rtl-typography` (font choice, ZWNJ, digits, punctuation) — apply them everywhere below without repeating them.

## 0. Before writing any code

1. **Language check**: fa or ar? (different digits, different font lists)
2. **Audience line**: Persian products price in تومان with Persian digits; Arabic in ر.س/د.إ or USD.
3. Confirm brand name rendering: if the brand is Latin (e.g. "Raast"), decide whether it stays Latin in RTL copy (usually yes, wrap in `<bdi>` where inline).

## 1. Skeleton

```html
<!doctype html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>... | برند</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@100..900&display=swap" rel="stylesheet">
</head>
```

Meta description in the same language as the page, with correct ZWNJ.

## 2. Section order (conversion-tested for Persian markets)

1. **Nav**: brand at inline-start (right side visually), links, CTA at inline-end (left). Sticky, blurred.
2. **Hero**: badge pill, H1 in display font, subline, two CTAs, trust line («مورد اعتماد بیش از X تیم»).
3. **Social proof / logos** (optional but strong in this market).
4. **Features**: six cards, three-column desktop grid, icons in tinted squares.
5. **How it works**: three numbered steps — numbers as Persian digits ۱ ۲ ۳ in circles.
6. **Pricing**: two plans, one highlighted «پیشنهاد ما». Prices: «۲۴۹٬۰۰۰ تومان در ماه». Annual note: «پرداخت سالانه ۲۰٪ تخفیف دارد.»
7. **Testimonial**: one strong quote with guillemets «...», Persian name + role.
8. **FAQ**: native `<details>/<summary>`, 4–6 questions, chevron rotates when open.
9. **Final CTA band** + **Footer**: «© ۱۴۰۵ برند» (Jalali year, not 2026!).

## 3. Copy rules (Persian)

- Write like a Persian marketer, not a translation engine. Short sentences. No passiveMachine tone.
- ZWNJ everywhere it belongs — see `rtl-typography` §5. If editing existing text, run `rtl-typography/scripts/fix-zwnj.py`.
- Numbers in copy: Persian digits. Trust lines: «۱٬۲۰۰+» is written «بیش از ۱٬۲۰۰» to avoid bidi plus-sign placement issues.
- Verbs of address: «تیم‌تان», «شما» — keep consistent formality (positive formal, not stiff).
- CTA verbs: «شروع کنید»، «شروع رایگان»، «دمو را ببینید»، «بیشتر بدانید».
- Never leave lorem ipsum in a Persian deliverable.

## 4. Layout mechanics (RTL)

- The visual flow mirrors: what English sites put on the left goes to the right.
- "Forward/next" arrows point **left** (chevron-left), "back" points right.
- Progress, steps, timelines run right → left.
- Test with the DevTools responsive mode at 360px, 768px, 1440px.

## 5. Anti-slop rules for RTL marketing pages

The generic AI look is doubly obvious in Persian. Forbid:

- Purple/blue gradient heroes, glassmorphism overload, random floating blobs
- letter-spacing on Persian headings (breaks joining — see rtl-typography §3)
- Centered-everything monotony: vary alignment, use asymmetric feature grids
- Emoji as feature icons — use inline SVG strokes
- Latin digits inside Persian sentences («۵», not "5")
- One-line English mixed into Persian headings ("فارسی با Power")

Do instead:

- One display font + one body font (see fonts.md pairing recipes)
- Warm neutrals or deep charcoal with ONE accent color used sparingly
- Real Persian microcopy everywhere (empty states, buttons, form hints)
- Generous line-height (1.9) — Persian reads bigger and calmer

## 6. Tailwind quick-start

```html
<body class="bg-[#0B0D0C] text-[#E7EAE8] antialiased">
  <section class="max-w-6xl mx-auto px-6 py-24 text-start">
    <h1 class="font-display text-5xl leading-[1.3] font-bold">...</h1>
  </section>
</body>
```

Tailwind handles `dir="rtl"` natively: flex/grid auto-flip. Only re-check: `translate-x`, `rotate`, absolute `left/right` (use `start-0`/`end-0`), and directional icons (`rtl:rotate-180` or pre-flipped SVGs).

## 7. Semantics, accessibility & themes

A landing page is read by users, bots, and screen readers. Non-negotiables:

- **Landmarks**: `header` / `nav` / `main` / `section` (with `aria-labelledby`) / `footer` — in that nesting. No `<div>` soup.
- **One `<h1>`**; section titles `<h2>`; visual size via CSS, not heading level.
- **Images**: meaningful `alt` in the page language («داشبورد گزارش فروش سیمرغ»), empty `alt=""` for decoration.
- **Icon-only buttons** (e.g. mobile menu): `aria-label` in Persian; visible focus ring (`:focus-visible`), ≥44px touch targets.
- **Forms**: `<label>` wired with `for`/`id`; errors as text linked via `aria-describedby`; never color-only.
- **Color**: body text ≥ 4.5:1 contrast on both themes; the accent color may not be the only signal.
- **Dark/light**: author tokens once (`--bg`, `--surface`, `--text`, `--accent`) and derive both themes from them; respect `prefers-color-scheme` as default, manual toggle as override; verify shadows/borders in dark (pure black shadows vanish).
- **Motion**: honor `prefers-reduced-motion` for any entrance animation.
- **Performance**: preload only the body font; `width`/`height` on images; hero is LCP — keep it markup-first (no JS-gated text).

## 8. Final QA

Run the `rtl-audit` checklist on the finished page before delivery.
