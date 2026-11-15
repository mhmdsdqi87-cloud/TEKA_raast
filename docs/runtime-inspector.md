# Runtime Inspector — rendered RTL checks (`raast.runtime`)

## What it is and why

`raast doctor` (static rules RTL001-RTL017) reads source text. It can flag physical CSS declarations, but it cannot observe what a browser does with them: rendered geometry, real scroll overflow, how elements move when the document direction flips, or where the bidi algorithm places fragments. Those behaviors only exist at runtime.

The runtime inspector loads the target page in headless Chromium (Playwright), collects per-element geometry and computed styles in the page's natural direction (pass 1), then flips `document.documentElement`'s `dir` attribute and measures again (pass 2). Comparing the page against its own mirror detects bug classes a source scan cannot see: elements that fail to reach their mirrored position, rendered horizontal overflow, visually clipped text, and directional icons that never flip.

## Install

```
pip install 'raast[runtime]' && playwright install chromium
```

Plain `pip install playwright` also works (the extra is only a dependency alias; the engine imports `playwright` lazily and exits with code 2 and an install hint when it is missing).

## Usage

```
python3 -m raast.runtime inspect --url URL | --file PATH --out REPORT_DIR
    [--viewport WxH]  (repeatable; default: 375x667 and 1280x800)
    [--wait MS]       (settle time after load, default 400)
    [--max-elements N] (cap collected elements per pass, default 1500)
    [--skip-mirror]   (skip the direction-flip comparison pass)
```

- Exactly one of `--url` (http/https) or `--file` (loaded as a `file://` URI) is required; `--out` is required.
- Each viewport gets its own browser context, both passes, and its own screenshots.
- `--wait` adds settle time after `load` — raise it for SPAs that render late. A page that never reaches `load` within 30s is inspected in its current state (a note is printed to stderr, the run continues).
- Exit codes: `0` no P0/P1 findings (P2-only runs pass), `1` findings at P1+ (CI gate), `2` engine/usage error (missing playwright, bad arguments, browser failure).
- Wire it as a console script with `raast-inspect = raast.runtime:main` if you prefer `raast-inspect inspect ...`.

### Worked example

A deliberately broken RTL page (`lang="fa" dir="rtl"`): a `margin-left: 40px` + `position: relative; left: 30px` block, a fixed-width 500px block, a mixed Persian/English sentence with no isolation, an `overflow-x: hidden` box with nowrap text, and an unflipped `.arrow-icon` span:

```
$ python3 -m raast.runtime inspect --file /tmp/rt-demo/broken.html --out /tmp/rt-demo/out --viewport 375x667
runtime inspection: file:///tmp/rt-demo/broken.html
viewports: 375x667
issues: 0 P0, 3 P1, 4 P2 (total 7)
report: /tmp/rt-demo/out/report.md (+ report.json, screenshots)
$ echo $?
1
```

Fired rules on that page: RT001 twice (a full-width block pushed past the right edge by physical offsets, and the 500px block overflowing left), RT002 (documentElement scrollWidth 516px vs clientWidth 375px), RT003 (375px of nowrap text inside a 200px hidden-overflow box), RT004 (the physical-offset block stays at x=78px where the mirrored position is -22px), RT005 (the `.arrow-icon` span in an RTL document with no flip mechanism), RT006 (the mixed Persian/English paragraph).

The same page with logical properties (`margin-inline-start`, `padding-inline`), bdi-wrapped mixed text, no fixed widths, and a `rtl:rotate-180`-classed icon produces `issues: 0 P0, 0 P1, 0 P2 (total 0)` and exit code 0.

## Rules

| Rule | Severity | Confidence | Detects | Suggested fix |
|---|---|---|---|---|
| RT001 | P1 | high | An element renders outside the horizontal viewport bounds (rect right > viewport width + 1px, or rect left < -1px) | Replace physical offsets with logical properties (margin-inline, padding-inline, inset-inline) and ensure no fixed pixel widths on containers |
| RT002 | P1 | high | Page-level horizontal overflow: documentElement scrollWidth > clientWidth + 1px | Same guidance as RT001 |
| RT003 | P2 | medium | Clipped text: element has direct text, scrollWidth > clientWidth + 2px, and computed overflow-x is hidden/clip | Text is clipped; add logical padding or allow wrapping |
| RT004 | P2 | medium | Asymmetric mirroring: after the dir flip the element is more than 8px away from its mirrored x position (`viewport - x - width`) | Replace physical left/right/margin/padding with logical properties (inset-inline, margin-inline, padding-inline) |
| RT005 | P2 | low | Directional icon (tag/class/aria-label/alt matching arrow, chevron, back, next, prev, forward) in an RTL document with no flip mechanism (scaleX(-1)-style computed transform, or an `rtl:` / `rotate-180` class) | Apply transform: scaleX(-1) or a direction-aware utility, or swap the glyph for RTL |
| RT006 | P2 | medium | Un-isolated mixed-direction text: direct text contains both Arabic-script and Latin characters and the element has no bidi isolation | Wrap the foreign-direction fragment in `<bdi>` or set `dir="auto"` on the container |

Mirror comparison (RT004) skips elements it cannot judge fairly: `position: fixed`, non-`none` transforms, media elements (svg, canvas, img, iframe, video), and elements whose computed direction differs from the document direction in pass 1. Elements whose selector path disappears between passes are skipped, not misreported.

## Output artifacts

All artifacts land in `--out` (created if needed):

- `report.json` — machine-readable: `target`, `engine: "runtime"`, `viewports`, `generated_at` (ISO UTC), `summary` (`p0/p1/p2/total`), `issues` (each with rule, severity, confidence, viewport, selector, tag, classes, text preview, rect, message, explanation, suggested_fix), and `screenshots`.
- `report.md` — human-readable report: target, per-viewport severity table, issues grouped by severity with selector, rect, message and suggested fix, image references to the screenshots, and a limitations note.
- `screenshot-natural.png` / `screenshot-mirrored.png` — full-page screenshots of both passes. With more than one viewport the files are suffixed per viewport (e.g. `screenshot-natural-1280x800.png`) and `report.json`'s `screenshots` object carries a `per_viewport` map.

## Limitations

- Needs a real browser. The engine is only as good as the environment it renders in: no Chromium, no findings (exit 2).
- SPA apps render after JavaScript runs; a page that is still empty at `load` produces false-clean results. Raise `--wait` (and consider running against a built/preview server rather than a dev server with loading spinners).
- Selector paths are best-effort `nth-of-type` chains. If JavaScript mutates the DOM between passes, paths can shift; such elements are then simply skipped from the mirror comparison rather than misreported. RT001/RT002/RT003/RT005/RT006 are unaffected because they run entirely within pass 1.
- Icon-flip detection (RT005) is a heuristic on names and classes. It can produce review signals for elements that merely mention "next"/"back" in a label, and it cannot verify a class-only flip utility actually applies (confidence is deliberately low).
- RT006 isolation check: Chromium reports `unicode-bidi: isolate` for any block that merely inherits `dir` from an ancestor, so computed `isolate` only counts as isolation when the element carries its own `dir` attribute; `<bdi>` tags and author-CSS `unicode-bidi: plaintext`/`isolate-overlay` always count.
- Findings complement `raast doctor`, not replace it: static analysis catches problems in source the runtime never renders (conditional branches, other routes), and runtime inspection catches geometry source reading cannot. Use both.
