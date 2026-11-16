# Compatibility Matrix

Generated from real runs of the engine against fixture projects — regenerate with `tools/compat/run_matrix.py`; do not edit by hand.

- Engine: RAAST `0.4.3` (`raast.__version__`)
- Command per fixture: `python3 -m raast.cli doctor <fixture> --language <lang> --format json`
- Summary: **14/14 fixtures passing** (PASS = every expected rule fired; extra detections are allowed and listed)

| Framework stack | Files | Language | Rules exercised (expect → detected) | Verdict | Notes |
|---|---|---|---|---|---|
| vanilla-css | `index.html`, `styles.css` | fa | RTL001, RTL004 → RTL001(1), RTL004(1) | PASS | Plain CSS is the classic defect source: physical margin plus physical alignment scanned lexically; the correct block with logical properties stays silent. The Persian content string in the stylesheet arms the evidence gate. |
| css-modules | `Card.jsx`, `Card.module.css` | ar | RTL002 → RTL002(1) | PASS | Module CSS scanned like plain CSS; class-name hashing and bundler mapping are not modeled. Arabic copy arms the gate; the logical padding twin stays silent. |
| tailwind | `page.html` | fa | RTL007, RTL008 → RTL007(1), RTL008(3) | PASS | Physical utilities detected lexically from class attributes; JIT output not required. Logical twins (ms/text-start) stay silent; translate is reported review-only. |
| bootstrap | `page.html` | fa | RTL001 → RTL001(1) | PASS | Bootstrap 5.3 rtl: build is fine — the logical margin utility ms-2 stays silent; inline physical styles remain the residual defect source and are caught lexically. |
| react-jsx | `Button.tsx` | fa | RTL001 → RTL001(2) | PASS | Kebab-case declarations inside CSS-in-JS template literals are scanned like stylesheets. The camelCase style object (marginLeft: 8) fires the same rule: property names are normalized to kebab-case before matching, and the suggested fix stays camelCase (marginInlineStart). The logical inline-object twin stays silent. |
| next-jsx | `page.tsx` | fa | RTL004 → RTL004(1) | PASS | styled-jsx style blocks scanned like plain CSS; runtime styling and CSS resolution are not evaluated. dir on the wrapper is honored implicitly by the correct twin staying silent. |
| vue | `Alert.vue` | fa | RTL002 → RTL002(1) | PASS | SFC style blocks scanned; template directives and compiler output are not parsed. The logical padding twin stays silent. |
| es-host | `page.html` | es | RTL015, RTL016 → RTL015(2), RTL016(1) | PASS | LTR host profile: the direction rules flip — RTL runs inside Spanish prose must be isolated (RTL015) and RTL-only elements need dir (RTL016). The bdi-isolated paragraph stays silent, which is the engine's own recommendation pattern. |
| astro | `astro.config.mjs`, `package.json`, `src/pages/index.astro` | fa | RTL001 → RTL001(1) | PASS | Astro page scanned as source text: frontmatter, template markup and the component style block are all read lexically in one pass. The physical margin declaration in the style block fires RTL001; the margin-inline-start twin stays silent. Compilation, islands and style scoping are not modeled. |
| svelte | `package.json`, `src/App.svelte`, `src/app.css`, `src/main.js` | fa | RTL002 → RTL002(2) | PASS | The SFC and the global stylesheet pair are both scanned: v0.4.2 added .svelte to the scanner's extension set, so the App.svelte style block fires RTL002 alongside the defect in src/app.css and both logical twins stay silent. Svelte compilation and component scoping are not modeled. |
| remix | `app/routes/_index.tsx`, `package.json` | fa | RTL004 → RTL004(1) | PASS | Route module scanned as source text; the inline critical-CSS template literal is read lexically like a stylesheet, so the physical alignment fires RTL004. Loaders, the compiler and runtime styling are not modeled; the text-align start twin stays silent. |
| nuxt | `app.vue`, `nuxt.config.ts`, `package.json` | fa | RTL001 → RTL001(1) | PASS | Nuxt 3 root component app.vue scanned like the plain vue fixture: the SFC style block is read lexically while auto-imports and SSR output are not parsed. The physical margin declaration fires RTL001; the margin-inline-end twin stays silent. |
| vite | `index.html`, `package.json`, `src/main.js`, `src/style.css` | fa | RTL004 → RTL004(1) | PASS | Vanilla Vite trio: document, entry module and stylesheet are scanned as separate files, and the CSS evidence gate is per-file, so style.css carries its own Persian generated label. The physical alignment in the stylesheet fires RTL004; the text-align end twin stays silent and the clean document keeps proper root meta so no structure rules fire. |
| angular | `package.json`, `src/app/app.component.css`, `src/app/app.component.html`, `src/app/app.component.ts` | fa | RTL001 → RTL001(1) | PASS | Angular trio scanned as three plain files: component class, external template and component stylesheet. templateUrl wiring and ViewEncapsulation rewriting are not modeled. The physical margin declaration in app.component.css fires RTL001; the margin-inline-start twin stays silent. |

## What this matrix proves / does not prove

Proves:

- The engine's rules fire on these frameworks' *source files* as written: every detected rule id above was emitted by an actual `doctor` run against the fixture directory, with the fixture's language profile.
- The evidence gate behaves as documented: CSS/Tailwind rules only fire in files that themselves contain RTL-script text, so fixtures embed realistic Persian/Arabic strings to arm them — and the correct logical-property blocks stay silent.
- CSS-in-JS style objects are first-class: camelCase declarations (marginLeft, textAlign) are normalized to kebab-case before matching and fire the same rules, with camelCase logical-property fixes. Vendor-cased names normalize with a leading hyphen. The react-jsx fixture carries both spellings.
- The verdicts are reproducible: `run_matrix.py --check` re-runs every fixture and compares this file byte-for-byte.

Does not prove:

- Rendering correctness in a browser. Static lexical matching cannot see computed styles, cascade order or runtime layout — use the RAAST runtime inspect / browser suite (`browser/`) for behavioral verification.
- Framework-internal behavior: Tailwind JIT class generation, CSS Modules hashing, Vue SFC compilation and Next.js runtime styling are not modeled; the scanner reads source text only.
- That camelCase coverage is total: property names are normalized before matching, but shorthand and vendor-prefixed forms beyond the known prefixes (Webkit, Moz, ms, O, Khtml) are not specially modeled. The react-jsx fixture documents the supported spellings.

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
python3 -m raast.cli doctor fixtures/compat/astro --language fa --format json
python3 -m raast.cli doctor fixtures/compat/svelte --language fa --format json
python3 -m raast.cli doctor fixtures/compat/remix --language fa --format json
python3 -m raast.cli doctor fixtures/compat/nuxt --language fa --format json
python3 -m raast.cli doctor fixtures/compat/vite --language fa --format json
python3 -m raast.cli doctor fixtures/compat/angular --language fa --format json
```
