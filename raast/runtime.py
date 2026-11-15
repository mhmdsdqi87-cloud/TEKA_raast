"""RAAST runtime inspector — rendered-layout RTL checks in a real browser.

Static analysis (``raast doctor``, rules RTL001-RTL017) reads source text. It
can flag physical CSS declarations, but it cannot observe what a browser does
with them: rendered geometry, real scroll overflow, how elements move when the
document direction flips, or where the bidi algorithm places fragments. Those
behaviors only exist at runtime. This engine loads the target page in headless
Chromium (Playwright), collects per-element geometry and computed styles in the
natural direction, then flips the document direction and measures again —
comparing the page against its own mirror surfaces bug classes static analysis
cannot see (mirrored-position deviation, rendered overflow, clipped text, unflipped
directional icons).

Runtime rule inventory (separate namespace from the RTL0xx static rules):
  RT001  horizontal element overflow             P1  high
  RT002  page-level horizontal overflow          P1  high
  RT003  clipped text (overflow-x hidden/clip)   P2  medium
  RT004  asymmetric mirroring on dir flip        P2  medium
  RT005  directional icon not flipped in RTL     P2  low
  RT006  un-isolated mixed-direction text        P2  medium

Artifacts written to --out: report.json, report.md, full-page screenshots.
Exit codes: 0 no P0/P1 findings, 1 findings at P1+ (CI gate), 2 engine/usage
error. Run: python3 -m raast.runtime inspect --url URL | --file PATH --out DIR
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ENGINE = "runtime"
PROG = "raast-inspect"
DEFAULT_VIEWPORTS = ["375x667", "1280x800"]
_VIEWPORT_RE = re.compile(r"^(\d{1,5})x(\d{1,5})$")
_OPPOSITE = {"rtl": "ltr", "ltr": "rtl"}
_SKIP_MIRROR_TAGS = {"svg", "canvas", "img", "iframe", "video"}
_OVERFLOW_CLIP = {"hidden", "clip"}
_MIRROR_TOLERANCE_PX = 8.0
_LOAD_TIMEOUT_MS = 30_000
_MIRROR_SETTLE_MS = 120

_FIX_RT001 = ("Replace physical offsets with logical properties (margin-inline, padding-inline, "
              "inset-inline) and ensure no fixed pixel widths on containers.")
_FIX_RT002 = _FIX_RT001
_FIX_RT003 = "Text is clipped; add logical padding or allow wrapping."
_FIX_RT004 = ("Positioning does not mirror under direction change; replace physical "
              "left/right/margin/padding with logical properties (inset-inline, margin-inline, "
              "padding-inline).")
_FIX_RT005 = ("Directional icon should follow reading direction: apply transform: scaleX(-1) or a "
              "direction-aware utility, or swap the glyph for RTL.")
_FIX_RT006 = ("Wrap the foreign-direction fragment in <bdi> or set dir=\"auto\" on the container so "
              "the browser's bidi algorithm cannot reorder it.")

# Single-string collection script handed to page.evaluate (defensive on every
# property access; returns plain JSON-serializable data only).
_COLLECT_JS = r"""
(arg) => {
  const MAX = (arg && arg.maxElements) > 0 ? arg.maxElements : 1500;
  const DIR_ICON_RE = /arrow|chevron|back|next|prev|forward/i;
  const RTL_CHARS = /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\u0590-\u05FF]/;
  const LATIN = /[A-Za-z]/;

  function safe(fn, fallback) {
    try { const v = fn(); return (v === undefined || v === null) ? fallback : v; }
    catch (err) { return fallback; }
  }
  function collapse(s) { return String(s || "").replace(/\s+/g, " ").trim(); }

  function selectorPath(el) {
    const parts = [];
    let node = el;
    for (let depth = 0; node && node.nodeType === 1 && depth < 30; depth++) {
      const tag = safe(() => node.tagName.toLowerCase(), "unknown");
      const parent = safe(() => node.parentElement, null);
      if (!parent) { parts.unshift(tag); break; }
      let part = tag;
      if (tag !== "html" && tag !== "body") {
        const siblings = safe(() => Array.prototype.filter.call(
          parent.children, (c) => safe(() => c.tagName.toLowerCase(), "") === tag), []);
        let idx = 1;
        for (let i = 0; i < siblings.length; i++) { if (siblings[i] === node) { idx = i + 1; break; } }
        part = tag + ":nth-of-type(" + idx + ")";
      }
      parts.unshift(part);
      node = parent;
    }
    return safe(() => parts.join(" > "), "");
  }

  function describe(el) {
    const rect = safe(() => el.getBoundingClientRect(), null);
    if (!rect) return null;
    const w = safe(() => rect.width, 0);
    const h = safe(() => rect.height, 0);
    if (!(w > 0) || !(h > 0)) return null;  // zero-size elements are invisible; skip
    const cs = safe(() => getComputedStyle(el), null) || {};
    const tag = safe(() => el.tagName.toLowerCase(), "unknown");
    const attr = (name) => safe(() => el.getAttribute(name) || "", "");
    const cls = collapse(attr("class"));
    const fullText = collapse(safe(() => el.textContent, ""));
    let hasDirectText = false;
    safe(() => { Array.prototype.forEach.call(el.childNodes, (n) => {
      if (n.nodeType === 3 && String(n.nodeValue || "").trim()) hasDirectText = true;
    }); return null; }, null);
    const iconHay = tag + " " + cls + " " + attr("aria-label") + " " + attr("alt");
    const unicodeBidi = String(safe(() => cs.unicodeBidi, "normal") || "normal");
    // Chromium quirk: a block that merely inherits dir from an ancestor computes
    // unicode-bidi: isolate without owning a dir attribute, so computed "isolate"
    // only counts as isolation with the element's own dir attribute;
    // plaintext / isolate-overlay are author-CSS-only values and always count.
    const ownDir = attr("dir");
    const iso = (tag === "bdi" || ownDir !== "" ||
                 unicodeBidi === "plaintext" || unicodeBidi === "isolate-overlay");
    return {
      path: selectorPath(el), tag: tag, cls: cls.slice(0, 80),
      x: safe(() => rect.x, 0), y: safe(() => rect.y, 0), w: w, h: h,
      text: fullText.slice(0, 60),
      dir: String(safe(() => cs.direction, "ltr") || "ltr"),
      pos: String(safe(() => cs.position, "static") || "static"),
      transform: String(safe(() => cs.transform, "none") || "none"),
      sw: safe(() => el.scrollWidth, 0), cw: safe(() => el.clientWidth, 0),
      sh: safe(() => el.scrollHeight, 0), ch: safe(() => el.clientHeight, 0),
      ox: String(safe(() => cs.overflowX, "visible") || "visible"),
      hasText: hasDirectText,
      icon: safe(() => DIR_ICON_RE.test(iconHay), false),
      iso: iso, mixed: safe(() => RTL_CHARS.test(fullText) && LATIN.test(fullText), false),
    };
  }

  const root = safe(() => document.documentElement, null);
  const docDirAttr = safe(() => (root && root.getAttribute("dir")) || null, null);
  const docDir = docDirAttr || String(safe(() => (root && getComputedStyle(root).direction) || "ltr", "ltr"));
  const body = safe(() => document.body, null);
  const all = body ? safe(() => Array.prototype.slice.call(body.querySelectorAll("*")), []) : [];
  const elements = [];
  for (let i = 0; i < all.length && elements.length < MAX; i++) {
    const rec = safe(() => describe(all[i]), null);
    if (rec) elements.push(rec);
  }
  return {
    doc: {
      dir: docDir, dirAttr: docDirAttr,
      lang: safe(() => (root && root.getAttribute("lang")) || "", ""),
      scrollWidth: safe(() => (root && root.scrollWidth) || 0, 0),
      clientWidth: safe(() => (root && root.clientWidth) || 0, 0),
      scrollHeight: safe(() => (root && root.scrollHeight) || 0, 0),
      clientHeight: safe(() => (root && root.clientHeight) || 0, 0),
    },
    elements: elements,
  };
}
"""

_FLIP_DIR_JS = "(dir) => { document.documentElement.setAttribute('dir', dir); }"


def _counts(issues: list[dict]) -> dict:
    c = {"P0": 0, "P1": 0, "P2": 0}
    for i in issues:
        c[i["severity"]] += 1
    return c


def _issue(rule: str, severity: str, confidence: str, viewport: str, el: dict,
           message: str, explanation: str, fix: str) -> dict:
    return {  # `el` is a collected element record (or a pseudo record for RT002)
        "rule": rule, "severity": severity, "confidence": confidence, "viewport": viewport,
        "selector": el.get("path", ""), "tag": el.get("tag", ""), "classes": el.get("cls", ""),
        "text": el.get("text", ""),
        "rect": {"x": round(float(el.get("x", 0.0)), 1), "y": round(float(el.get("y", 0.0)), 1),
                 "width": round(float(el.get("w", 0.0)), 1),
                 "height": round(float(el.get("h", 0.0)), 1)},
        "message": message, "explanation": explanation, "suggested_fix": fix,
    }


def _icon_has_flip(el: dict) -> bool:
    return ("matrix(-1" in el.get("transform", "none")
            or "rtl:" in el.get("cls", "") or "rotate-180" in el.get("cls", ""))


def _check_pass1(els: list[dict], doc: dict, vw: int, vh: int, viewport: str) -> list[dict]:
    """PASS 1 checks: RT001 element overflow, RT002 page overflow, RT003 clipped text,
    RT005 unflipped directional icons in an RTL document, RT006 un-isolated mixed text."""
    issues: list[dict] = []
    for el in els:
        x, w = float(el["x"]), float(el["w"])
        right = x + w
        if right > vw + 1 or x < -1:
            edge = (f"right edge {right:.0f}px vs viewport {vw}px" if right > vw + 1
                    else f"left edge {x:.0f}px vs viewport origin")
            issues.append(_issue(
                "RT001", "P1", "high", viewport, el,
                message=f"element renders outside the horizontal viewport bounds ({edge})",
                explanation=f"Rendered rect spans x {x:.0f}..{right:.0f} at viewport {vw}x{vh}; rendered overflow only exists in a real browser.",
                fix=_FIX_RT001))
        if el["hasText"] and el["sw"] > el["cw"] + 2 and el["ox"] in _OVERFLOW_CLIP:
            issues.append(_issue(
                "RT003", "P2", "medium", viewport, el,
                message=(f"text is clipped: content {el['sw']}px inside {el['cw']}px box "
                         f"with overflow-x: {el['ox']}"),
                explanation=f"Element has direct text, scrollWidth {el['sw']}px vs clientWidth {el['cw']}px, computed overflow-x '{el['ox']}' — excess text is visually cut off.",
                fix=_FIX_RT003))
        if doc["dir"] == "rtl" and el["icon"] and not _icon_has_flip(el):
            issues.append(_issue(
                "RT005", "P2", "low", viewport, el,
                message="directional icon does not appear to flip in an RTL document",
                explanation=("Element matches directional-icon heuristics (arrow|chevron|back|next|prev|forward "
                             "on tag/class/aria-label/alt) but shows no scaleX(-1) transform or "
                             "rtl:/rotate-180 class — likely a review signal."),
                fix=_FIX_RT005))
        if el["hasText"] and el["mixed"] and not el["iso"]:
            issues.append(_issue(
                "RT006", "P2", "medium", viewport, el,
                message="mixed-direction text without bidi isolation",
                explanation=("Direct text mixes Arabic-script and Latin characters without bdi/dir=auto/"
                             "unicode-bidi isolation; the bidi algorithm may reorder fragments at render time."),
                fix=_FIX_RT006))
    sw, cw = int(doc["scrollWidth"]), int(doc["clientWidth"])
    if sw > cw + 1:
        pseudo = {"path": "html", "tag": "html", "cls": "", "text": "",
                  "x": 0, "y": 0, "w": sw, "h": doc["scrollHeight"]}
        issues.append(_issue(
            "RT002", "P1", "high", viewport, pseudo,
            message=f"page scrolls horizontally: documentElement scrollWidth {sw}px > clientWidth {cw}px",
            explanation=(f"Document is {sw}px wide inside a {cw}px viewport ({vw}x{vh}) — users must scroll "
                         "horizontally, which breaks RTL reading flow."),
            fix=_FIX_RT002))
    return issues


def _check_mirror(first: list[dict], second: list[dict], doc_dir: str, vw: int,
                  viewport: str) -> list[dict]:
    """PASS 2 comparison: RT004 — elements that fail to reach their mirrored position."""
    issues: list[dict] = []
    mirrored = {el["path"]: el for el in second}
    for el in first:
        el2 = mirrored.get(el["path"])
        if el2 is None:
            continue  # DOM mutated between passes; skip rather than misreport
        if (el["pos"] == "fixed" or el["transform"] != "none"
                or el["tag"] in _SKIP_MIRROR_TAGS or el["dir"] != doc_dir):
            continue
        x1, w1, x2 = float(el["x"]), float(el["w"]), float(el2["x"])
        expected = vw - x1 - w1
        if abs(x2 - expected) > _MIRROR_TOLERANCE_PX:
            issues.append(_issue(
                "RT004", "P2", "medium", viewport, el,
                message=(f"element did not mirror under direction change: x {x1:.0f}px -> "
                         f"{x2:.0f}px, expected {expected:.0f}px"),
                explanation=(f"After flipping document dir to '{_OPPOSITE.get(doc_dir, 'rtl')}' the element "
                             f"should sit at x ~= {expected:.0f}px (mirror of {x1:.0f}px, width {w1:.0f}px, "
                             f"tolerance {_MIRROR_TOLERANCE_PX:.0f}px) but renders at x ~= {x2:.0f}px — "
                             "physical offsets survived the flip."),
                fix=_FIX_RT004))
    return issues


def _shot_name(kind: str, label: str, multi: bool) -> str:
    return f"screenshot-{kind}-{label}.png" if multi else f"screenshot-{kind}.png"


def _screenshots_payload(shots: dict[str, dict[str, str | None]], labels: list[str]) -> dict:
    last = shots.get(labels[-1], {})
    payload: dict = {"natural": last.get("natural"), "mirrored": last.get("mirrored")}
    if len(labels) > 1:
        payload["per_viewport"] = shots
    return payload


def _run(target: str, viewports: list[tuple[int, int, str]], wait_ms: int, max_elements: int,
         skip_mirror: bool, out_dir: Path) -> tuple[list[dict], dict[str, dict[str, str | None]], int]:
    """Render the target per viewport, run both passes, return (issues, shots, exit_code)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright is required for runtime inspection: "
              "pip install 'raast[runtime]' && playwright install chromium", file=sys.stderr)
        return [], {}, 2
    out_dir.mkdir(parents=True, exist_ok=True)
    issues: list[dict] = []
    shots: dict[str, dict[str, str | None]] = {}
    multi = len(viewports) > 1
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                for vw, vh, label in viewports:
                    context = browser.new_context(viewport={"width": vw, "height": vh})
                    page = context.new_page()
                    try:
                        page.goto(target, wait_until="load", timeout=_LOAD_TIMEOUT_MS)
                    except Exception:
                        print(f"note: [{label}] page did not reach 'load' within {_LOAD_TIMEOUT_MS}ms; inspecting current state", file=sys.stderr)
                    page.wait_for_timeout(wait_ms)
                    natural = out_dir / _shot_name("natural", label, multi)
                    page.screenshot(path=str(natural), full_page=True)
                    shots[label] = {"natural": natural.name, "mirrored": None}
                    first = page.evaluate(_COLLECT_JS, {"maxElements": max_elements})
                    vp_issues = _check_pass1(first["elements"], first["doc"], vw, vh, label)
                    if not skip_mirror:
                        doc_dir = first["doc"]["dir"]
                        page.evaluate(_FLIP_DIR_JS, _OPPOSITE.get(doc_dir, "rtl"))
                        page.wait_for_timeout(_MIRROR_SETTLE_MS)
                        flipped = out_dir / _shot_name("mirrored", label, multi)
                        page.screenshot(path=str(flipped), full_page=True)
                        shots[label]["mirrored"] = flipped.name
                        second = page.evaluate(_COLLECT_JS, {"maxElements": max_elements})
                        vp_issues += _check_mirror(first["elements"], second["elements"],
                                                   doc_dir, vw, label)
                    issues.extend(vp_issues)
                    context.close()
            finally:
                browser.close()
    except Exception as exc:  # engine failure is an error class, not a finding
        print(f"error: runtime inspection failed: {exc}", file=sys.stderr)
        return [], {}, 2
    return issues, shots, 0


def _markdown(target: str, labels: list[str], issues: list[dict],
              shots: dict[str, dict[str, str | None]]) -> str:
    counts = _counts(issues)
    per_vp = {label: {"P0": 0, "P1": 0, "P2": 0} for label in labels}
    for i in issues:
        per_vp[i["viewport"]][i["severity"]] += 1
    lines = [
        "# RAAST Runtime Inspection Report", "",
        f"- Target: `{target}`",
        "- Engine: runtime (headless Chromium via Playwright)",
        f"- Viewports: {', '.join(labels)}",
        f"- Summary: **{len(issues)} issue(s): {counts['P0']} P0, {counts['P1']} P1, "
        f"{counts['P2']} P2**", "",
        "| Viewport | P0 | P1 | P2 |", "|---|---|---|---|",
    ]
    for label in labels:
        c = per_vp[label]
        lines.append(f"| {label} | {c['P0']} | {c['P1']} | {c['P2']} |")
    lines.append("")
    if not issues:
        lines += ["No runtime findings for the collected elements. This is not a guarantee of "
                  "correctness — see the limitations note below.", ""]
    for sev in ("P0", "P1", "P2"):
        group = [i for i in issues if i["severity"] == sev]
        if not group:
            continue
        lines += [f"## {sev}", ""]
        for i in group:
            block = [
                f"### {i['rule']} — {i['viewport']} ({i['confidence']} confidence)", "",
                f"- Selector: `{i['selector']}`",
                f"- Tag: `{i['tag']}`" + (f", classes: `{i['classes']}`" if i["classes"] else ""),
            ]
            if i["text"]:
                block.append(f"- Text: `{i['text']}`")
            r = i["rect"]
            block.append(f"- Rect: x={r['x']}, y={r['y']}, width={r['width']}, height={r['height']} (px, viewport {i['viewport']})")
            lines += block + ["", i["message"], "", f"_{i['explanation']}_", "", f"Fix: {i['suggested_fix']}", ""]
    lines += ["## Evidence", ""]
    for label in labels:
        s = shots.get(label, {})
        lines.append(f"Viewport {label}:")
        if s.get("natural"):
            lines.append(f"![natural direction — {label}]({s['natural']})")
        if s.get("mirrored"):
            lines.append(f"![mirrored direction — {label}]({s['mirrored']})")
        lines.append("")
    lines += [
        "---", "",
        "Limitations: element selectors are best-effort nth-child paths and can shift when "
        "JavaScript mutates the DOM between passes (such elements are skipped, not misreported). "
        "Runtime findings complement, not replace, `raast doctor` static results.", "",
    ]
    return "\n".join(lines)


def _write_reports(out_dir: Path, target: str, labels: list[str], issues: list[dict],
                   shots: dict[str, dict[str, str | None]]) -> None:
    counts = _counts(issues)
    payload = {
        "target": target,
        "engine": ENGINE,
        "viewports": labels,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")
                        .replace("+00:00", "Z"),
        "summary": {"p0": counts["P0"], "p1": counts["P1"], "p2": counts["P2"],
                    "total": len(issues)},
        "issues": issues,
        "screenshots": _screenshots_payload(shots, labels),
    }
    (out_dir / "report.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "report.md").write_text(_markdown(target, labels, issues, shots), encoding="utf-8")


def cmd_inspect(args) -> int:
    viewports: list[tuple[int, int, str]] = []
    for value in (args.viewport or list(DEFAULT_VIEWPORTS)):
        m = _VIEWPORT_RE.match(value.strip().lower())
        if not m or int(m.group(1)) < 1 or int(m.group(2)) < 1:
            print(f"error: invalid viewport '{value}' (expected WxH, e.g. 375x667)", file=sys.stderr)
            return 2
        w, h = int(m.group(1)), int(m.group(2))
        viewports.append((w, h, f"{w}x{h}"))
    if args.wait < 0 or args.max_elements < 1:
        print("error: --wait must be >= 0 and --max-elements must be >= 1", file=sys.stderr)
        return 2
    if args.url:
        if not args.url.lower().startswith(("http://", "https://")):
            print("error: --url must be an http(s) URL (use --file for local paths)", file=sys.stderr)
            return 2
        target = args.url
    else:
        path = Path(args.file)
        if not path.is_file():
            print(f"error: file not found: {args.file}", file=sys.stderr)
            return 2
        target = path.resolve().as_uri()
    out_dir = Path(args.out)
    labels = [v[2] for v in viewports]
    issues, shots, code = _run(target, viewports, args.wait, args.max_elements,
                               args.skip_mirror, out_dir)
    if code != 0:
        return code
    _write_reports(out_dir, target, labels, issues, shots)
    counts = _counts(issues)
    print(f"runtime inspection: {target}")
    print(f"viewports: {', '.join(labels)}")
    print(f"issues: {counts['P0']} P0, {counts['P1']} P1, {counts['P2']} P2 (total {len(issues)})")
    print(f"report: {out_dir / 'report.md'} (+ report.json, screenshots)")
    return 1 if counts["P0"] or counts["P1"] else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=PROG,
        description="RAAST runtime inspector — rendered RTL layout checks in a real browser "
                    "(headless Chromium via Playwright).",
    )
    sub = p.add_subparsers(dest="command", required=True)
    sp = sub.add_parser("inspect", help="render a URL or local HTML file and detect "
                                        "rendered RTL layout bugs")
    src = sp.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", help="http(s) URL to inspect")
    src.add_argument("--file", help="local HTML file to inspect (loaded as a file:// URL)")
    sp.add_argument("--out", required=True,
                    help="directory for report.json, report.md and screenshots")
    sp.add_argument("--viewport", action="append", metavar="WxH", default=None,
                    help="viewport size, repeatable (default: 375x667 and 1280x800)")
    sp.add_argument("--wait", type=int, default=400, metavar="MS",
                    help="settle time after load in ms (default: 400)")
    sp.add_argument("--max-elements", type=int, default=1500, metavar="N",
                    help="cap on collected elements per pass (default: 1500)")
    sp.add_argument("--skip-mirror", action="store_true",
                    help="skip the direction-flip comparison pass")
    sp.set_defaults(func=cmd_inspect)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
