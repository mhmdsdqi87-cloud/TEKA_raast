---
name: jalali-dates
description: Persian (Solar Hijri / Jalali) calendar dates, relative time, and Persian number formatting in JavaScript. Use when a Persian interface needs dates, timestamps, countdowns, or formatted numbers — or the user mentions تاریخ شمسی، تقویم فارسی، Jalali. Covers Intl fa-IR one-liners, date-fns-jalali, month names, and storage conventions.
---

# Jalali dates & Persian formatting

## 0. Conversion vs formatting — know the difference

Two distinct problems, two distinct solutions:

1. **Localized display formatting** of the *same instant*: 2026-11-14T10:00Z shown as «۲۳ آبان ۱۴۰۵». Pure presentation; `Intl` handles it — calendar mapping, month names, digits, all locale-driven. **This is what 95% of UIs need.**
2. **Calendar conversion** producing calendar-arithmetic values (jy/jm/jd tuples, month lengths, leap checks): needed for date *inputs*, recurrence, and analytics buckets. Requires a vetted library (`jalaali-js`, `date-fns-jalali`) — **never** a hand-rolled algorithm, because the Jalali leap-year rule (33-year cycles with documented exceptions) fails naive implementations on specific years.

Rule: reach for (1) by default; reach for (2) only when the user picks/manipulates dates, and then the library owns all arithmetic.

## 1. The zero-dependency default: Intl

Modern browsers and Node 14+ (full-icu) natively produce Jalali dates for `fa-IR`:

```js
const d = new Date('2026-11-14T10:00:00Z');

new Intl.DateTimeFormat('fa-IR').format(d)
// «۱۴۰۵/۸/۲۳»

new Intl.DateTimeFormat('fa-IR', { dateStyle: 'long' }).format(d)
// «۲۳ آبان ۱۴۰۵»

new Intl.DateTimeFormat('fa-IR', { dateStyle: 'full' }).format(d)
// «شنبه ۲۳ آبان ۱۴۰۵»

new Intl.DateTimeFormat('fa-IR', { dateStyle: 'long', timeStyle: 'short' }).format(d)
// «۲۳ آبان ۱۴۰۵ در ساعت ۱۰:۰۰» (time style varies by platform — check visually)
```

Notes:
- Output digits are Persian by default. No manual conversion.
- `new Intl.DateTimeFormat('fa-IR-u-ca-persian')` forces the Persian calendar even where `fa-IR` defaults differ (rare platform edge cases).
- For Arabic UIs with Gregorian: `new Intl.DateTimeFormat('ar')`.

## 2. Formatting recipes

| Need | Code |
|---|---|
| Numeric short | `fa-IR` default → ۱۴۰۵/۸/۲۳ |
| Long prose | `dateStyle: 'long'` → ۲۳ آبان ۱۴۰۵ |
| Day+month only | `{ day: 'numeric', month: 'long' }` → ۲۳ آبان |
| Weekday | `{ weekday: 'long' }` → شنبه |
| Clock | `new Intl.DateTimeFormat('fa-IR', { hour: '2-digit', minute: '2-digit' })` |
| Relative | `new Intl.RelativeTimeFormat('fa').format(-3, 'day')` → «۳ روز پیش» |
| Percent | `new Intl.NumberFormat('fa-IR', { style: 'percent' })` → ۱۲٪ |
| Money (Toman) | `(125000).toLocaleString('fa-IR') + ' تومان'` → ۱۲۵٬۰۰۰ تومان |

## 3. Reference tables

Month names (1→12): فروردین، اردیبهشت، خرداد، تیر، مرداد، شهریور، مهر، آبان، آذر، دی، بهمن، اسفند

Weekdays (sat-first in Iran): شنبه، یکشنبه، دوشنبه، سه‌شنبه، چهارشنبه، پنجشنبه، جمعه

Facts to respect:
- Weekend in Iran = Friday (جمعه). Business weeks start Saturday.
- Leap-year rule differs from Gregorian (33-year cycle approximations exist) — never hand-roll conversion.
- Jalali year = Gregorian year + 621/622 (birthday of the difference moves at Nowruz ~March 20/21).
- Nowruz = ۱ فروردین (≈ `21 March`, Gregorian). Persian sites commonly show «سال نو مبارک» around it.

## 4. Libraries (when Intl isn't enough)

| Library | Use |
|---|---|
| `date-fns-jalali` | date-fns API with Jalali calendar — best DX for React apps |
| `jalaali-js` | bare conversion functions (toJalaali/toGregorian) — tiny, core algorithm |
| `react-multi-date-picker` | the standard Jalali datepicker component |
| `moment-jalaali` | legacy only; prefer date-fns-jalali |

```js
import { toJalaali } from 'jalaali-js';
toJalaali(2026, 11, 14) // { jy: 1405, jm: 8, jd: 23 }
```

## 5. Storage & architecture conventions

- **Store UTC timestamps** (`timestamptz` / ISO). Jalali is a presentation concern.
- Convert at the rendering boundary, using the user's timezone.
- Never store Jalali strings as the source of truth.
- Persian datepickers: value in ISO, display Jalali.
- Range pickers for reports: guard month lengths — اسفند has 29/30 days (`31` in leap years); مهر/اردیبهشت/خرداد always 30; months 1–6 have `31` days.

## 6. Server vs client rendering

`Intl` results depend on ICU — identical on modern Node/browsers, but to avoid hydration mismatches in SSR:
- Render dates client-side (`useEffect`/mounted state), or
- Pre-format on the server with the SAME ICU and pass the string down, or
- `<time suppressHydrationWarning dateTime={iso}>` wrapper.

Always emit `<time datetime="2026-11-14">۲۳ آبان ۱۴۰۵</time>` — machines get ISO, humans get Jalali.
