---
name: rtl-bidi
description: Handle mixed Persian/Arabic with English text, numbers, phone numbers, emails, URLs, code, and currency inside RTL interfaces. Use when text contains both scripts, when output looks scrambled with wrong number/order placement, or for inputs, prices, and code blocks on RTL pages. Covers the bidi algorithm, bdi elements, unicode-bidi CSS, and common scrambling bugs.
---

# Bidi: Mixed Persian/English content

The Unicode BiDi algorithm reorders mixed-direction text automatically — sometimes wrongly. This skill teaches when to intervene and exactly how.

## 1. The mental model

- Base direction comes from `dir` on the nearest ancestor (page: RTL).
- Runs of strong-LTR content (Latin letters) embed and flow LTR inside.
- **Neutral characters** (punctuation, digits-adjacent signs like + - / $ %) take the direction of their surroundings — this is where scrambling happens.

## 2. The intervention toolbox

| Tool | When | Example |
|---|---|---|
| `<bdi>` element | Inline foreign atom inside Persian text, direction unknown | «فایل <bdi>report_final.pdf</bdi> را ببینید» |
| `<span dir="ltr">` | Known-LTR atom you also want left-aligned internally | `<span dir="ltr">+98 912 345 6789</span>` |
| `dir="auto"` | User-generated or unpredictable content | chat bubbles, comments, file names |
| CSS `unicode-bidi: plaintext` | Same as `dir="auto"` but for styled spans | `.user-content { unicode-bidi: plaintext; }` |
| `isolate` (default for bdi) | Prevent the atom from reordering neighbors | default behavior of `<bdi>` |

## 3. Canonical cases

### Phone numbers
`+98 912` in Persian text often renders the `+` on the wrong side.
```html
تلفن پشتیبانی: <span dir="ltr">+98 21 9100 2000</span>
```

### Prices in foreign currency
`$99` floating in RTL text becomes `99$`:
```html
اشتراک جهانی: <span dir="ltr">$99/mo</span> — اشتراک داخلی: ۹۹٬۰۰۰ تومان
```

### Emails, URLs, handles
```html
به <bdi>support@example.com</bdi> ایمیل بزنید.
مستندات: <bdi>https://docs.example.co/fa</bdi>
```

### Latin brand names mid-sentence
Usually fine as plain text, but after a Persian suffix it breaks:
«نسخه‌ی جدید Node.js» — «Node.js» is safe; «های Node.js» needs `<bdi>` around the Latin run if a suffix attaches: `<bdi>Node.js</bdi>های` is wrong — rephrase to «افزونه‌های Node.js».

### Code & commands — always LTR blocks
```html
<pre dir="ltr" style="text-align: left;">npm install raast</pre>
```
Inline commands in Persian prose: `<code dir="ltr">npx create-next-app</code>`.

### Lists of mixed items
Item markers (۱ ۲ ۳) live in the RTL flow; long LTR items inside stay isolated per item — put `<bdi>` on any item starting with Latin/digits.

### Product identifiers, serials & technical IDs
The highest-scramble category — mixed letters, digits and dashes:

```html
شماره سریال: <bdi dir="ltr">SN-9F42-KM18</bdi>
کد پیگیری: <bdi dir="ltr">TRK-IR-14050823-0042</bdi>
شناسه محصول: <bdi dir="ltr">SKU 88451-B</bdi>
```

Rules:
- Identifiers must stay **byte-exact** when copied — isolation only changes rendering, never the string.
- Trailing dash/digit runs inside an RTL sentence will reorder without `<bdi>` (e.g. `88451-B` → `B-88451`).
- Database lookups built in JS: keep the logical string; do not "pre-flip" for display.
- Fixed-width mono font + `dir="ltr"` + `text-align: start` for ID columns in tables.

### User-generated content (chat, comments, filenames)
- Container: `dir="auto"` + CSS `unicode-bidi: plaintext` — each message orients by its first strong character.
- A Persian user pasting English text, or vice versa, must read correctly without code switching `dir` manually.
- Never enforce page direction onto UGC with `dir="rtl"` + `text-align: start` alone; the first-strong-char rule is the point of `plaintext`.
- Filenames/downloads: render in `<bdi>` so extensions (`.pdf`, `.zip`) don't detach.

## 4. Form inputs

- `dir="auto"`: the input adopts the first strong character's direction — right for name/message fields.
- Explicit `dir="ltr"`: email, phone, username, card number, URL, price (with `text-align: end` so the caret starts right for RTL users... actually keep `text-align: start` on the ltr input for caret sanity; test).

## 5. Debugging scrambled output — the checklist

1. Is the atom wrapped/isolated? (bdi / span dir=ltr)
2. Are neutral chars (`+ - / . , ( )`) adjacent to a direction boundary? Add isolation or a RLM (`\u200F`)/LRM (`\u200E`) mark.
3. Trailing punctuation of an LTR atom jumping to the wrong end → include the trailing space inside the isolation.
4. String built in JS? Bidi is a rendering concern — don't reorder in code, fix the DOM/CSS.
5. Invisible char dump: paste into a bidi inspector or `JSON.stringify()` the text to see U+200E/F placement.

## 6. RLM/LRM — the scalpel

`&rlm;` (U+200F) / `&lrm;` (U+200E) force neutral characters to one side when isolation is impossible (e.g. plain-text emails, CSV cells):

```
متن فارسی‎ +98‎  -> keep the + attached to the number
```

Use sparingly — visible mojibake in some fonts; prefer structural isolation on the web.

## 7. Titles, meta, and single-line contexts

- `<title>` with mixed scripts: browsers render bidi in tabs reasonably, but lead with the page language: «raast — مهارت‌های RTL» vs «مهارت‌های RTL — raast»: put the strong script of the page language first.
- `aria-label` strings follow the same rules; screen readers handle unicode bidi marks, so keep them.
- JSON/API payloads: store logical order always; never pre-reverse anything for display.
