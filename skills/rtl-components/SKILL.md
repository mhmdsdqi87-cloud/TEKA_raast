---
name: rtl-components
description: RTL-correct component patterns with Tailwind logical utilities. Use when building forms, cards, navigation, tables, modals, pagination, breadcrumbs, or any UI component for Persian/Arabic RTL pages, or when fixing mirrored layout bugs. Covers ms/me/ps/pe utilities, icon flipping, sidebar placement, and shadcn/ui RTL notes.
---

# RTL Component Patterns (Tailwind + shadcn/ui)

Logical, direction-agnostic components. After `dir="rtl"`, flex/grid mirror automatically — the bugs live in the leftovers listed here.

## 1. Utility translation table (memorize this)

| LTR habit | Logical (use always) |
|---|---|
| `ml-` / `mr-` | `ms-` / `me-` |
| `pl-` / `pr-` | `ps-` / `pe-` |
| `left-0` / `right-0` | `start-0` / `end-0` |
| `text-left` / `text-right` | `text-start` / `text-end` |
| `border-l-` / `border-r-` | `border-s-` / `border-e-` |
| `rounded-l-` / `rounded-r-` | `rounded-s-` / `rounded-e-` |
| `ml-auto` (push to far side) | `ms-auto` |

These exist in Tailwind v3.3+ and v4. Using them means the component works in BOTH directions for free.

## 2. Directional icons — the flip list

Flip ONLY truly directional icons. Never flip semantic-stable ones.

Flip (`rtl:-scale-x-100` or pre-flipped SVG, or `rtl:rotate-180` for arrows):
- chevrons/arrows for next/prev, back buttons, breadcrumb separators
- indent/outdent, reply (share arrow), forward, redo
- timeline markers, "expand side panel" icons

Do NOT flip:
- clock, lock, search, settings, check, heart, star, upload/download, wifi, bell

```html
<!-- next arrow in RTL points left -->
<svg class="rtl:rotate-180">…</svg>
```

For shadcn/ui + lucide: `<ChevronLeft className="rtl:rotate-180" />` is wrong twice — instead just use the correct glyph for the direction you serve. For an RTL-only product: next = `ChevronLeft`, back = `ChevronRight`.

## 3. Forms

- Labels sit at inline-start above the input (standard).
- Text inputs: `dir="auto"` for name/message; `dir="ltr"` + `text-end` for phone, email, national ID, price inputs (content is LTR but placement stays right).
- Input group addons: currency «تومان» after the number → visually left side; use logical padding on both sides, never hard-code `pr`.
- Validation icons: place with `end-0` not `right-0`.
- Error text: Persian, with «؛» and correct ZWNJ: «ایمیل معتبر نیست»، «رمز عبور باید ۸ نویسه یا بیشتر باشد».

## 4. Navigation & chrome

- Sidebar: `start-0` (renders right in RTL). Icon-only collapsed variant keeps tooltips flipping (`side="start"` in Radix tooltips).
- Breadcrumbs: separator = `ChevronLeft` (RTL "forward-down" direction), last item current.
- Pagination: page numbers ascend toward the LEFT: ۱ ۲ ۳ ۴ with next = ChevronLeft. `Prev` is on the right side visually.
- Tabs: order flows right → left; active underline via `border-b` is fine.
- Table: column order auto-mirrors; align numeric cells `text-end` and let Persian-digit numbers keep their own LTR runs.

## 5. Overlays

- Dialogs/Sheets: `Sheet side="start"` = right-side drawer in RTL pages.
- Dropdown/Popover: Radix uses `side`/`align` — `align="start"` follows inline-start (right). Default collision works fine with RTL.
- Toasts: position `bottom-start` (visually bottom-right for RTL) so they don't fight CTAs at inline-end.
- Tooltips on truncated Persian text: Radix measures fine; ensure `max-w` is set — Persian ellipsis works normally.

## 6. Cards & content blocks

- Accent bar on the inline-start edge: `border-s-2 border-s-emerald-500` (renders on the right).
- Meta rows (author · date · read-time): separator dot with `ms-2 me-2` or flex `gap-2`.
- Cards with actions: primary action inline-end? No — in RTL reading, primary CTA conventionally sits at inline-END (left) in card footers, mirroring LTR conventions.

## 7. Motion & transforms

`dir` does NOT mirror transforms. Audit every:

- `translate-x-*` (sliders, off-canvas, marquee) → needs an explicit RTL twin
- `rotate-45` decorative → usually fine
- Carousel swipe: embla/swiper — set `direction: rtl` option or they scroll backwards
- Progress bars: fill anchored at `start-0`, grows toward the left; percentages as ۷۰٪
- Skeleton shimmer: keyframe `translate-x` must mirror or shimmer slides the wrong way

### Direction-aware animation patterns

```css
/* Off-canvas drawer: enters from inline-start, exits to inline-start.
   One declaration pair serves both directions. */
.drawer { transform: translateX(calc(var(--dir-sign, -1) * 100%)); }
[dir="rtl"] .drawer { --dir-sign: 1; }
.drawer.open { transform: translateX(0); }

/* Bounce / emphasis icons: flip the whole animation, not the element mid-flight */
[dir="rtl"] .cta-arrow { animation: nudge-rtl 1.2s infinite; }
@keyframes nudge-rtl { 50% { transform: translateX(-4px); } }

/* Number counters and progress fill: animate the logical inline size, not left */
@keyframes fill { from { inline-size: 0 } }
```

- CSS logical `inset-inline-start` + custom property sign switch beats duplicating whole keyframes per direction.
- `prefers-reduced-motion: reduce` → disable nudges/marquees, keep opacity fades.

## 8. shadcn/ui RTL notes (v4 tokens, New York style)

- Most primitives are RTL-clean when the app sets `dir="rtl"` on `<html>`.
- Known touch-ups: `DropdownMenuContent align="start"` keeps menus anchored under the trigger's right edge; `Select` chevron should be `ChevronDown` (direction-free, no change); `InputOTP`, `CommandDialog`, and `ResizablePanel` need manual review.
- Set font tokens once: put Vazirmatn in `--font-sans` (globals.css) so every shadcn component inherits it.

## 9. Audit hook

Ship components through the `rtl-audit` checklist — especially icon flips, transforms, and `left/right` classes.
