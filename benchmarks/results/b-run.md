# RAAST Benchmark Report — condition `B-raast`

- Candidate: `/home/z/raast-publish/benchmarks/ai/b`
- Evaluated at: 2026-11-16T15:48:04+00:00
- Result: **20/24 passed, 4 failed, 0 skipped**

| Category | Passed | Failed | Skipped |
|---|---|---|---|
| accessibility | 3 | 0 | 0 |
| arabic_typography | 3 | 0 | 0 |
| bidi | 1 | 3 | 0 |
| component_correctness | 2 | 0 | 0 |
| persian_typography | 3 | 1 | 0 |
| jalali_dates | 2 | 0 | 0 |
| rtl_layout | 4 | 0 | 0 |
| responsive | 2 | 0 | 0 |

## Case detail

| Case | Status | Failed checks |
|---|---|---|
| `a11y-001` | pass | — |
| `a11y-002` | pass | — |
| `a11y-003` | pass | — |
| `ar-typo-001` | pass | — |
| `ar-typo-002` | pass | — |
| `ar-typo-003` | pass | — |
| `bidi-001` | fail | bidi_isolation |
| `bidi-002` | fail | bidi_isolation |
| `bidi-003` | pass | — |
| `bidi-004` | fail | bidi_isolation |
| `comp-001` | pass | — |
| `comp-002` | pass | — |
| `fa-typo-001` | pass | — |
| `fa-typo-002` | pass | — |
| `fa-typo-003` | fail | persian_punctuation |
| `fa-typo-004` | pass | — |
| `jalali-001` | pass | — |
| `jalali-002` | pass | — |
| `layout-001` | pass | — |
| `layout-002` | pass | — |
| `layout-003` | pass | — |
| `layout-004` | pass | — |
| `resp-001` | pass | — |
| `resp-002` | pass | — |

## Known limitations

- Static validators inspect markup and text; they cannot certify visual rendering.
- Condition A/B results require running agents externally; this report only reflects the files given to it.
- Font availability and OS rendering differ across machines; browser suite adds computed-style checks but not pixel truth.

