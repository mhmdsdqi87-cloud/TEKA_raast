# Font catalog: Persian & Arabic web fonts

Curated, battle-tested fonts. Every entry ships woff2 and is free (OFL or equivalent). Prefer loading via CDN during prototyping; self-host in production.

Load pattern:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@100..900&display=swap" rel="stylesheet">
```

Self-host fallback (jsDelivr, rastikerdar family):

```html
<link href="https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css" rel="stylesheet">
```

(Verify tag names against the repository's releases when you use jsDelivr.)

---

## Persian fonts

### Vazirmatn — the default choice
- Variable 100–900, includes matching Latin glyphs (one font covers mixed text)
- Clean neo-grotesque feel, excellent at UI sizes
- Google Fonts: `family=Vazirmatn:wght@100..900`
- Use for: body, UI, dashboards, forms. The safe default; start here.

### Estedad — modern display
- Variable, geometric, great for headlines and marketing pages
- Also has aFD (FD variant) with alternate glyph flavor
- Use for: hero headings on landing pages, paired with Vazirmatn body

### Lalezar — poster/display voice
- Single weight 400, chunky, distinctive Persian poster character
- Google Fonts: `family=Lalezar`
- Use for: brand wordmarks, big hero lines, section titles. Not for body.

### Markazi Text — editorial
- Low-contrast serif-ish text face, warm print feel
- Use for: long-form articles, blog bodies, quotes

### Sahel / Shabnam / Samim — rastikerdar classics
- Widely recognized, comfortable reading faces (fixed-width variants available)
- Use when a familiar, slightly softer feel than Vazirmatn is wanted
- jsDelivr pattern: `gh/rastikerdar/shabnam-font@v5.0.1/dist/font-face.css`

### Parastoo — literary
- Inspired by traditional Persian book typography
- Use for: poetry, literature, cultural content

---

## Arabic fonts

### IBM Plex Sans Arabic — the default choice
- 7 weights, superb UI clarity, pairs with IBM Plex Sans (Latin)
- Google Fonts: `family=IBM+Plex+Sans+Arabic:wght@100;200;300;400;500;600;700`

### Cairo — friendly sans
- Variable, rounded terminals, works for both display and body
- Google Fonts: `family=Cairo:wght@200..1000`

### Tajawal — geometric UI
- Light and clean, strong at small sizes
- Google Fonts: `family=Tajawal:wght@200;300;400;500;700;800;900`

### Almarai — minimal
- Four weights, no-frills, great for dense UIs
- Google Fonts: `family=Almarai:wght@300;400;700;800`

### Noto Naskh Arabic — editorial serif feel
- Traditional naskh flavor for body text and print-like layouts
- Google Fonts: `family=Noto+Naskh+Arabic:wght@400..700`

### Changa — display
- Condensed display voice for headlines
- Google Fonts: `family=Changa:wght@200..800`

---

## Pairing recipes

| Product type | Display | Body | Latin-adjacent |
|---|---|---|---|
| SaaS landing (fa) | Estedad 800 | Vazirmatn 400 | (Vazirmatn covers Latin) |
| Marketing poster (fa) | Lalezar | Vazirmatn | — |
| Blog/editorial (fa) | Lalezar | Markazi Text | JetBrains Mono for code |
| Dashboard (fa) | Vazirmatn 700 | Vazirmatn 400 | Geist Mono for numbers? no — keep Vazirmatn |
| Arabic fintech UI | IBM Plex Sans Arabic 600 | IBM Plex Sans Arabic 400 | IBM Plex Mono |
| Arabic media | Cairo 800 | Tajawal 400 | — |

## Rules when applying fonts

1. One Arabic-script family for body + one optional display face. More than two looks chaotic.
2. Let the Persian font's own Latin cover embedded Latin words — mixing Vazirmatn + Inter inside a paragraph causes baseline clashes. Use a separate Latin font only in dedicated Latin blocks.
3. `font-feature-settings`: some fonts expose digit stylistic sets (check each font's README). Prefer explicit `toLocaleString('fa-IR')` conversion over font features — it is deterministic.
4. Preload the body font only (`<link rel="preload" as="font" type="font/woff2" crossorigin>`), never the display face.
5. Test the exact glyph set you need: Persian text must show ی ک گ چ پ ژ correctly; Arabic text must show ي ك ة correctly.
