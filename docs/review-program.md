# Native-language review program

RAAST splits RTL correctness into two halves. The engine automates one half completely; the other half cannot be automated and belongs to native speakers. This document is the working manual for that second half: what is already verified mechanically, what needs native eyes, the per-language checklists, the process, and the honest current status.

Joining instructions and credit policy live in [CONTRIBUTING.md](../CONTRIBUTING.md#native-language-review-program); this page carries the detail reviewers actually need.

## Automation vs. native judgment

### What the engine already verifies mechanically

| Layer | What it checks | Where |
|---|---|---|
| Static CSS/HTML | physical `margin/padding/left/right`, `text-align`, missing `dir`/`lang`, Tailwind physical utilities, `translate-x` twins | `RTL001–RTL014` (`raast doctor`) |
| Typography | `letter-spacing` on Arabic script (P0), ZWNJ compound *shape* (`«می رود»`), un-isolated LTR atoms | `RTL005`, `RTL011`, `RTL012` |
| Host-language flip (es) | un-isolated RTL runs, RTL elements without `dir`, missing RAE inverted marks ¿ ¡ | `RTL015–RTL017` |
| Locale files | missing keys, empty values, placeholder sets, untranslated strings, length anomalies, Western digits / Latin punctuation in Arabic-script prose, un-isolated Latin runs, Arabic Yeh/Kaf in Persian strings, opt-in niqqud | `LQG001–LQG009` (`raast-i18n`) |
| Rendered geometry | mirror asymmetry, overflow, clipped text, unflipped icons, mixed-direction text in a real browser | `RT001–RT006` (`raast-inspect`) |
| Evidence | 32 machine-verified corpus specimens, 24 benchmark cases, generated compatibility matrix | `tools/corpus/verify.py`, `raast benchmark` |

### What needs native eyes

- **Which compound, not just whether it is shaped right.** The engine knows `می‌` is a prefix and `ها` a suffix; it cannot tell whether a *specific* sentence should use the compound form at all, or whether a possessive suffix (`کتابم`) must stay attached without ZWNJ.
- **Idiomatic phrasing.** Grammatical Persian is not natural Persian; example copy that a Persian speaker would never write teaches agents the wrong register even when every rule passes.
- **Cultural correctness.** Calendar context, month/weekday names, currency conventions, tone of honorifics — profile fields can be *declared* wrong; only a native reviewer can confirm they are right.
- **Convention fairness.** Claims like "Western digits invalid in fa prose" or "niqqud flagged only opt-in" are decisions, not facts; a native reviewer confirms or challenges them.
- **Font and tooling recommendations.** The [font catalog](../skills/rtl-typography/fonts.md) lists curated families; native judgment on real-world rendering quality is the strongest evidence available.

## Honest starting point

Much of the bundled Persian/Arabic/Hebrew example copy in `corpus/samples/` and `skills/` was written by non-native contributors. It is machine-verified against the profiles (corpus 32/32, fixed pages scan clean), but it has **not** been native-reviewed. That gap is exactly why this program exists — no completed native reviews have been published yet.

## Per-language checklists

### Persian (fa)

**Files to review**

- `corpus/samples/*/broken.html` + `fixed.html` — all 32 specimens carry Persian prose; typography (CS-009–012), bidi (CS-005–008) and forms (CS-017–020) are the prose-heaviest
- `skills/rtl-typography/SKILL.md`, `skills/rtl-landing/SKILL.md`, `skills/jalali-dates/SKILL.md` — example snippets
- `skills/rtl-typography/fonts.md` — Persian section (Vazirmatn, Estedad, Lalezar, …)
- `raast/profiles/fa.json` — digits, punctuation, ZWNJ affix lists, dates, Toman placement
- `benchmarks/cases/fa-typo-001…004.json`, `jalali-001/002.json` — task wording
- `docs/i18n-gate.md` worked examples and `tests/fixtures/locales/fa.json` — the locale-corpus Persian strings

**Questions a fa reviewer answers**

1. Do ZWNJ joins in `corpus/*/fixed.html` specimens follow می‌ + verb and noun + ‌ها conventions correctly? Are half-space compounds like می‌شود، کتاب‌ها used consistently?
2. Are possessive suffixes (`کتابم`, `کتابش`) left attached — no ZWNJ — per the profile's `possessive_suffixes_no_zwnj`?
3. Is every Persian string free of Arabic Yeh ي (U+064A) and Kaf ك (U+0643)? Persian requires ی (U+06CC) and ک (U+06A9).
4. Are digits ۰–۹, decimal/thousands separators ٫ ٬, percent placement (۱۲٪, no space), ، ؟ ؛ punctuation and «» quotes consistent with `raast/profiles/fa.json`?
5. Do Jalali month/weekday names, Toman amounts and `fa-IR` `Intl` guidance in the examples read naturally and correctly?
6. Is the typography guidance (body line-height ≥ 1.8, letter-spacing forbidden) what a Persian typographer would recommend?

### Arabic (ar)

**Files to review**

- `corpus/samples/*/broken.html` + `fixed.html` — bidi and typography specimens carry Arabic-script prose
- `skills/rtl-typography/SKILL.md` (Arabic sections), `skills/rtl-bidi/SKILL.md` — example snippets
- `skills/rtl-typography/fonts.md` — Arabic section (IBM Plex Sans Arabic, Cairo, Tajawal, Almarai, Noto Naskh Arabic)
- `raast/profiles/ar.json` — digits, punctuation, the "ZWNJ rare in Arabic" stance, currency isolation
- `benchmarks/cases/ar-typo-001…003.json` — task wording
- `docs/i18n-gate.md` LQG006/LQG007 examples — Arabic-script conventions in locale values

**Questions an ar reviewer answers**

1. Are Arabic-script examples in standard Modern Standard Arabic web conventions — with no Persian letters (پ چ ژ گ) leaking in as typos, mirroring the profile's `persian_yeh_is/kaf_is: invalid_in_ar`?
2. Are Arabic-Indic digits ٠–٩ and ، ؟ ؛ punctuation used correctly? Is `western_digits_in_prose: invalid_in_prose` fair, given the profile's own note that some regional conventions use Western digits — or is the P2 gate too strict?
3. Does "ZWNJ rare in Arabic — do NOT apply Persian affix joining rules to Arabic content" hold everywhere in shipped examples and fixer behavior descriptions?
4. Are currency examples (SAR/EGP treated as project-specific, codes isolated as LTR atoms) realistic for Arabic e-commerce copy?
5. Is the recommended font set a sensible MSA-first web list, and is the body line-height (≥ 1.6) adequate for Naskh rendering?

### Hebrew (he)

**Files to review**

- `corpus/samples/*/broken.html` + `fixed.html` — prose-bearing specimens
- `skills/rtl-typography/SKILL.md` — Hebrew-relevant guidance (final-form letters, justification)
- `raast/profiles/he.json` — Western-digit validity, gershayim/geresh/maqaf, nikud note, letter-spacing downgrade
- `benchmarks/cases/*.json` — any task wording that Hebrew-hosted projects would imitate
- `docs/i18n-gate.md` LQG009 (opt-in niqqud) — the example `בְּחִירָה` and the flag rationale

**Questions a he reviewer answers**

1. Are Hebrew example strings natural modern Hebrew — no transliterated placeholders, no Arabic-script contamination?
2. Niqqud handling: is the opt-in stance (LQG009 reports niqqud only with `--hebrew-diacritics`) the right default for production copy, and is the wording of the finding appropriate?
3. Are gershayim ״ (inside acronyms, e.g. רא״ם), geresh ׳ (abbreviations, foreign phonetics) and maqaf ־ vs plain hyphen-minus handled correctly in examples and profile notes?
4. Is "Western digits valid in prose, Latin punctuation valid, letter-spacing discouraged at P1 (not P0)" the right severity for Hebrew, given that letters are separate and not cursive?
5. Does the nikud-aware line-height note (body ≥ 1.5 so vowel points do not clip) match real rendering behavior?

### Spanish (es)

**Files to review**

- `fixtures/compat/` Spanish LTR host fixture and its row in `docs/compatibility-matrix.md` — the es engine-flip example
- `raast/profiles/es.json` — inverted marks, comillas, digit separators, € placement, bidi isolation notes
- `skills/rtl-typography/SKILL.md`, `skills/rtl-bidi/SKILL.md` — RTL-fragment isolation recipes an es-hosted project would copy
- `corpus/samples/` — any specimen usable as an LTR-host example
- `docs/cli-reference.md` / `docs/troubleshooting.md` — es-specific prose (RTL015–RTL017 descriptions)

**Questions an es reviewer answers**

1. Do Spanish prose examples follow RAE conventions: opening ¿ ¡ on questions/exclamations, «comillas angulares» preference in prose, 25 € with non-breaking space, dd/mm/yyyy dates?
2. Are RTL-fragment isolation examples realistic — Arabic/Hebrew names and quotes inside Spanish prose wrapped in `<bdi>` or `dir="rtl"` — matching the profile's claim that bare RTL runs are the #1 bidi defect in es pages?
3. Is "never suggest `dir="rtl"` on `<html>` in an es host" consistently reflected in every example and rule description?
4. Is the es-ES vs LatAm digit-separator guidance ("pick per project locale and stay consistent") sound and clearly worded?
5. Does the font list (Inter, Source Sans 3, Lato, Open Sans, Noto Sans) hold up for Spanish with ¿ ¡ « » coverage?

## Process

1. **Claim** — open a GitHub issue with the Native review issue template (`language`, `focus_areas`, `artifacts`, agreements).
2. **Scope confirmation** — a maintainer confirms the language + artifact scope on the issue; large scopes are split into rounds.
3. **Review** — you read the confirmed artifacts and record findings as concrete file/line notes on the issue (or a draft gist linked from it). There is no time commitment beyond what you claim.
4. **PR** — you open normal PRs from your own GitHub account, one artifact group per PR, fixing prose/conventions/profile fields directly. Engine and test changes that a finding motivates follow the normal contribution flow.
5. **Maintainer merge** — standard CI gates apply to every review PR (unit tests, corpus 32/32, matrix freshness); merging is a maintainer action.
6. **Credit** — after merge, you are credited in CONTRIBUTORS.md and in the release notes of the version that lands the review.

## Status

| Language | Status | Reviewed artifacts |
|---|---|---|
| Persian (`fa`) | awaiting first review | — |
| Arabic (`ar`) | awaiting first review | — |
| Hebrew (`he`) | awaiting first review | — |
| Spanish (`es`) | awaiting first review | — |

This table is updated only when a review PR actually lands — never pre-filled, never projected.

## What this program is not

- **Not a substitute for automated CI.** The rule engine, corpus verification, i18n gate and browser suite keep running exactly as before. Native review complements the machines; it does not replace them, and a reviewer's approval never waives a failing gate.
- **No paid engagements.** Review is volunteer contribution under the project's Code of Conduct, credited per the policy above. Nothing here implies compensation, contracting, or a hiring pipeline.
- **No fabricated endorsements.** The status table is the single source of truth. We do not quote reviews that have not landed as merged PRs, and we do not publish reviewer names before the reviewer's own PR authorship does.
- **Not a translation service.** Reviewers validate existing artifacts; the program does not produce product translations or locale files for third parties.
