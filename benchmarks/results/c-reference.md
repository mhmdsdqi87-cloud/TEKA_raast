# RAAST Benchmark Report — condition `C-reference`

- Candidate: `/home/z/my-project/raast/benchmarks/reference`
- Evaluated at: 2026-11-14T21:30:49+00:00
- Result: **24/24 passed, 0 failed, 0 skipped**

| Category | Passed | Failed | Skipped |
|---|---|---|---|
| accessibility | 3 | 0 | 0 |
| arabic_typography | 3 | 0 | 0 |
| bidi | 4 | 0 | 0 |
| component_correctness | 2 | 0 | 0 |
| persian_typography | 4 | 0 | 0 |
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
| `bidi-001` | pass | — |
| `bidi-002` | pass | — |
| `bidi-003` | pass | — |
| `bidi-004` | pass | — |
| `comp-001` | pass | — |
| `comp-002` | pass | — |
| `fa-typo-001` | pass | — |
| `fa-typo-002` | pass | — |
| `fa-typo-003` | pass | — |
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

