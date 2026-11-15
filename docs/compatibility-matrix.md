# Compatibility Matrix

Generated from real runs of the engine against fixture projects — regenerate with `tools/compat/run_matrix.py`; do not edit by hand.

- Engine: RAAST `0.4.0` (`raast.__version__`)
- Command per fixture: `python3 -m raast.cli doctor <fixture> --language <lang> --format json`
- Summary: **8/8 fixtures passing** (PASS = every expected rule fired; extra detections are allowed and listed)

| Framework stack | Files | Language | Rules exercised (expect → detected) | Verdict | Notes |
|---|---|---|---|---|---|
| vanilla-css | `index.html`, `styles.css` | fa | RTL001, RTL004 → RTL001(1), RTL004(1) | PASS | Plain CSS is the classic defect source: physical margin plus physical alignment scanned lexically; the correct block with logical properties stays silent. The Persian content string in the stylesheet arms the evidence gate. |
| css-modules | `Card.jsx`, `Card.module.css` | ar | RTL002 → RTL002(1) | PASS | Module CSS scanned like plain CSS; class-name hashing and bundler mapping are not modeled. Arabic copy arms the gate; the logical padding twin stays silent. |
| tailwind | `page.html` | fa | RTL007, RTL008 → RTL007(1), RTL008(3) | PASS | Physical utilities detected lexically from class attributes; JIT output not required. Logical twins (ms/text-start) stay silent; translate is reported review-only. |
| bootstrap | `page.html` | fa | RTL001 → RTL001(1) | PASS | Bootstrap 5.3 rtl: build is fine — the logical margin utility ms-2 stays silent; inline physical styles remain the residual defect source and are caught lexically. |
| react-jsx | `Button.tsx` | fa | RTL001 → RTL001(1) | PASS | Kebab-case declarations inside CSS-in-JS template literals are scanned like stylesheets. Honest gap: camelCase style objects (marginLeft: 8) are NOT matched by the current engine — kebab-case property names only; a dedicated JSX style-object rule is future work. |
| next-jsx | `page.tsx` | fa | RTL004 → RTL004(1) | PASS | styled-jsx style blocks scanned like plain CSS; runtime styling and CSS resolution are not evaluated. dir on the wrapper is honored implicitly by the correct twin staying silent. |
| vue | `Alert.vue` | fa | RTL002 → RTL002(1) | PASS | SFC style blocks scanned; template directives and compiler output are not parsed. The logical padding twin stays silent. |
| es-host | `page.html` | es | RTL015, RTL016 → RTL015(2), RTL016(1) | PASS | LTR host profile: the direction rules flip — RTL runs inside Spanish prose must be isolated (RTL015) and RTL-only elements need dir (RTL016). The bdi-isolated paragraph stays silent, which is the engine's own recommendation pattern. |

## What this matrix proves / does not prove

Proves:

- The engine's rules fire on these frameworks' *source files* as written: every detected rule id above was emitted by an actual `doctor` run against the fixture directory, with the fixture's language profile.
- The evidence gate behaves as documented: CSS/Tailwind rules only fire in files that themselves contain RTL-script text, so fixtures embed realistic Persian/Arabic strings to arm them — and the correct logical-property blocks stay silent.
- The verdicts are reproducible: `run_matrix.py --check` re-runs every fixture and compares this file byte-for-byte.

Does not prove:

- Rendering correctness in a browser. Static lexical matching cannot see computed styles, cascade order or runtime layout — use the RAAST runtime inspect / browser suite (`browser/`) for behavioral verification.
- Framework-internal behavior: Tailwind JIT class generation, CSS Modules hashing, Vue SFC compilation and Next.js runtime styling are not modeled; the scanner reads source text only.
- That the camelCase style-object gap is closed: `marginLeft: 8` in JSX is not detected (kebab-case only). The react-jsx row documents this honestly.

## Commands actually executed

```text
python3 -m raast.cli doctor fixtures/compat/vanilla-css --language fa --format json
python3 -m raast.cli doctor fixtures/compat/css-modules --language ar --format json
python3 -m raast.cli doctor fixtures/compat/tailwind --language fa --format json
python3 -m raast.cli doctor fixtures/compat/bootstrap --language fa --format json
python3 -m raast.cli doctor fixtures/compat/react-jsx --language fa --format json
python3 -m raast.cli doctor fixtures/compat/next-jsx --language fa --format json
python3 -m raast.cli doctor fixtures/compat/vue --language fa --format json
python3 -m raast.cli doctor fixtures/compat/es-host --language es --format json
```
