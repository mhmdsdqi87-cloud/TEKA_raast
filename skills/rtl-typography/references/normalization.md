# Normalization decision table

What automated tooling may and may not transform in Arabic-script text. The CLI (`raast fix`) implements exactly this table; `scripts/fix-zwnj.py` is the standalone Skills entry point to the same spec.

## Always safe (default transformations)

| Transformation | Example | Why safe |
|---|---|---|
| Join `می/نمی/بی/هم/باز/نا/فرا` + known verb stem with U+200C | «می رود» → «می‌رود» | Space between prefix and verb is never correct in modern Persian orthography |
| Join plural `ها/های` to a preceding Arabic-script word | «خانه ها» → «خانه‌ها» | «ها» is never a standalone word in prose |
| Join `تر/ترین` after an Arabic-script word | «خوب تر» → «خوب‌تر» | Attached comparative, per Academy orthography |
| Arabic Yeh/Kaf → Persian | ي→ی، ك→ک | In **fa** content these are always legacy-keyboard artifacts |
| Arabic Tatweel (U+0640) removal in UI copy | «مـدیـریـت» → «مدیریت» | Kashida stretching is a print-era decoration; in web UI it breaks search. **Warn first** — legit in decorative logos |

## Language-gated (apply only when content language matches)

| Transformation | fa | ar | Why |
|---|---|---|---|
| Arabic-Indic ٠١٢٣٤٥٦٧٨٩ → Persian ۰۱۲۳۴۵۶۷۸۹ | allowed | **forbidden** | ٠… are *correct* digits in Arabic content |
| Latin `, ? ;` → ، ؟ ؛ in prose lines | allowed (prose only) | allowed (prose only) | Prose heuristic: line must contain Arabic-script letters; code/URLs excluded |
| Percent `٪` placement normalization | after digits, no space | same | Both scripts agree; safe |

## Never automatic (require human review)

| Case | Why |
|---|---|
| Joined «میکند» → «می‌کند» (missing ZWNJ *without* a space) | Splitting a joined word requires lexicon; risk of false splits. Engine reports, does not fix. |
| ZWNJ removal anywhere | Removing U+200C can change meaning (literary texts rely on it) |
| Possessive suffix separation | «کتابم» must stay joined; a naive rule joining «ام/ات/اش» with ZWNJ would corrupt it |
| RLM/LRM (U+200E/F) removal | These may be load-bearing bidi marks; removal reorders text |
| Quote style conversion («…» ↔ "…") in mixed EN/fa files | Language of each string is not locally determinable |

## Protected regions (never modified)

1. Fenced code blocks (``` ... ```)
2. Inline code (` ... `)
3. URLs, emails
4. HTML attributes / tags (in HTML mode, only text nodes are normalized)
5. Regions between `<!-- keep -->` and `<!-- /keep -->`

## Ambiguity reporting contract

Every tool implementing this table must, in report output, attach to each change:
- the rule applied (identifier),
- before → after with visible marker for U+200C (e.g. `⸍`),
- a `confidence: high|medium` field,
- a skip reason for anything under "Never automatic" that matched but was not applied.
