"""RAAST Benchmark — validation of real HTML artifacts against case criteria.

The runner NEVER fabricates results: it validates candidate files supplied to
it (a reference implementation, an agent output directory, a repo snapshot)
and reports exactly what passed. Methodology lives in
docs/benchmark-methodology.md.
"""
from __future__ import annotations

import json
import platform
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from .normalizer import ARABIC_RE
from . import __version__

VALIDATOR_NAMES = {
    "html_lang_dir",
    "no_letter_spacing",
    "zwnj_min_count",
    "persian_digits_in_prose",
    "arabic_digits_in_prose",
    "persian_punctuation",
    "no_physical_margin",
    "logical_tailwind",
    "bidi_isolation",
    "code_dir_ltr",
    "viewport_meta",
    "img_alt",
    "icon_button_labels",
    "intl_jalali",
    "no_ltr_next_arrow",
    "logical_text_align",
    "responsive_signals",
}


# ---------------------------------------------------------------- helpers

def _strip_code_blocks(html: str) -> str:
    html = re.sub(r"<(script|style|pre|code)\b.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    return html


def _visible_text(html: str) -> str:
    """Approximate visible text: drop head/script/style, strip tags, keep line structure."""
    text = re.sub(r"<head\b.*?</head>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = _strip_code_blocks(text)
    text = re.sub(r"<[^>]*>", "", text)
    return text


def _visible_lines(html: str) -> list[str]:
    return _visible_text(html).splitlines()


# ---------------------------------------------------------------- validators
# Each validator returns (passed: bool, detail: str)


def _v_html_lang_dir(html: str, spec: dict) -> tuple[bool, str]:
    m = re.search(r"<html\b([^>]*)>", html, re.IGNORECASE)
    if not m:
        return False, "no <html> tag found"
    attrs = m.group(1)
    want_lang = spec.get("lang")
    want_dir = spec.get("dir")
    problems = []
    if want_lang and not re.search(rf"lang\s*=\s*[\"']{want_lang}[\"']", attrs, re.IGNORECASE):
        problems.append(f"missing lang={want_lang}")
    if want_dir and not re.search(rf"dir\s*=\s*[\"']{want_dir}[\"']", attrs, re.IGNORECASE):
        problems.append(f"missing dir={want_dir}")
    return (not problems), ("; ".join(problems) or "ok")


def _v_no_letter_spacing(html: str, spec: dict) -> tuple[bool, str]:
    for m in re.finditer(r"letter-spacing\s*:\s*([^\s;\"']+)", html):
        if m.group(1).lower() not in ("normal", "inherit", "initial", "unset", "0", "0px", "0em", "0rem"):
            return False, f"letter-spacing: {m.group(1)}"
    for m in re.finditer(r"letterSpacing\s*:\s*[\"']?([^\s\"';]+)", html):
        if m.group(1).lower() not in ("normal", "inherit", "initial", "unset", "0", "0px", "0em", "0rem"):
            return False, f"letterSpacing: {m.group(1)}"
    return True, "ok"


def _v_zwnj_min_count(html: str, spec: dict) -> tuple[bool, str]:
    visible = _visible_text(html)
    count = visible.count("\u200c")
    minimum = int(spec.get("min", 1))
    if count < minimum:
        return False, f"visible ZWNJ count {count} < required {minimum}"
    return True, f"{count} ZWNJ found"


def _prose_digit_violations(lines: list[str]) -> list[str]:
    bad = []
    for line in lines:
        if not ARABIC_RE.search(line):
            continue
        for m in re.finditer(r"[0-9]+", line):
            before = line[m.start() - 1] if m.start() else ""
            after = line[m.end()] if m.end() < len(line) else ""
            if (not before or ARABIC_RE.match(before) or before.isspace()) and (
                not after or ARABIC_RE.match(after) or after.isspace()
            ):
                bad.append(f"{m.group(0)} in «…{line[max(0,m.start()-12):m.end()+12].strip()}…»")
    return bad


def _v_persian_digits_in_prose(html: str, spec: dict) -> tuple[bool, str]:
    """Western digits in non-isolated Arabic-script text nodes are violations.
    Digits inside <bdi>/dir=ltr atoms (phones, serials) are correct."""
    bad = []
    for text, isolated in _walk_visible_nodes(html):
        if isolated:
            continue
        for line in text.splitlines():
            if not ARABIC_RE.search(line):
                continue
            for m in re.finditer(r"[0-9]+", line):
                before = line[m.start() - 1] if m.start() else ""
                after = line[m.end()] if m.end() < len(line) else ""
                if (not before or ARABIC_RE.match(before) or before.isspace()) and (
                    not after or ARABIC_RE.match(after) or after.isspace()
                ):
                    bad.append(f"{m.group(0)} in «…{line[max(0,m.start()-12):m.end()+12].strip()}…»")
    return (not bad), ("; ".join(bad[:3]) or "ok")


def _v_arabic_digits_in_prose(html: str, spec: dict) -> tuple[bool, str]:
    """Arabic content must use Arabic-Indic digits (٠١٢); Persian ۰۱۲ is wrong here."""
    bad = []
    for line in _visible_lines(html):
        if not ARABIC_RE.search(line):
            continue
        if re.search(r"[\u06F0-\u06F9]", line):
            bad.append("Persian digits (۰-۹) found in Arabic content")
    return (not bad), ("; ".join(bad[:3]) or "ok")


def _v_persian_punctuation(html: str, spec: dict) -> tuple[bool, str]:
    bad = []
    for line in _visible_lines(html):
        if not ARABIC_RE.search(line):
            continue
        for m in re.finditer(r"(?<=[\u0600-\u06FF])\s*[,;?](?=[\u0600-\u06FF\s]|$)", line):
            bad.append(f"Latin `{m.group(0).strip()}` after Arabic word")
    return (not bad), ("; ".join(bad[:3]) or "ok")


def _v_no_physical_margin(html: str, spec: dict) -> tuple[bool, str]:
    bad = []
    for m in re.finditer(r"(margin|padding)-(left|right)\s*:", html):
        bad.append(f"{m.group(0)}")
    return (not bad), ("; ".join(bad[:3]) or "ok")


def _v_logical_tailwind(html: str, spec: dict) -> tuple[bool, str]:
    bad = []
    for m in re.finditer(r"""(?<![\w-])(?:ml|mr|pl|pr)-[\w[\].%/]+|text-(?:left|right)\b""", html):
        bad.append(f"`{m.group(0)}`")
    return (not bad), ("; ".join(sorted(set(bad))[:3]) or "ok")


def _walk_visible_nodes(html: str) -> list[tuple[str, bool]]:
    """Walk text nodes via HTMLParser; returns [(text, isolated)] skipping script/style/pre/code."""
    from html.parser import HTMLParser

    class NodeWalker(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.nodes: list[tuple[str, bool]] = []
            self.iso_stack: list[bool] = []
            self.skip_depth = 0

        def handle_starttag(self, tag, attrs):
            a = {k.lower(): (v or "") for k, v in attrs}
            if tag in ("script", "style", "pre", "code"):
                self.skip_depth += 1
                return
            self.iso_stack.append(tag == "bdi" or a.get("dir", "").lower() == "ltr")

        def handle_endtag(self, tag):
            if tag in ("script", "style", "pre", "code"):
                self.skip_depth = max(0, self.skip_depth - 1)
                return
            if self.iso_stack:
                self.iso_stack.pop()

        def handle_data(self, data):
            if self.skip_depth:
                return
            self.nodes.append((data, bool(self.iso_stack) and any(self.iso_stack)))

    w = NodeWalker()
    w.feed(html)
    w.close()
    return w.nodes


def _v_bidi_isolation(html: str, spec: dict) -> tuple[bool, str]:
    """URLs/emails/phones/$ in Arabic-script TEXT NODES must be isolated.

    Uses stdlib HTMLParser to walk real text nodes with an isolation stack,
    so href attributes (a legitimate place for URLs) never false-positive.
    """
    bad = []
    for text, isolated in _walk_visible_nodes(html):
        if isolated:
            continue
        for m in re.finditer(
            r"(?<![\w>])([\w.+-]+@[\w-]+\.\w+|https?://\S+|\+\d[\d\s-]{6,}\d|\$\d+(?:\.\d+)?)",
            text,
        ):
            bad.append(m.group(1)[:40])
    return (not bad), ("; ".join(bad[:3]) or "ok")


def _v_code_dir_ltr(html: str, spec: dict) -> tuple[bool, str]:
    bad = []
    for m in re.finditer(r"<(pre|code)\b([^>]*)>", html, re.IGNORECASE):
        attrs = m.group(2)
        if "dir" not in attrs.lower():
            tag = m.group(1)
            end = html.find(f"</{tag}", m.end())
            inner = html[m.end() : end if end != -1 else len(html)]
            if re.search(r"[A-Za-z]\s+\w+|\w+\s+[-|>&]", re.sub(r"<[^>]*>", "", inner)):
                bad.append(f"<{tag}> without dir=\"ltr\"")
    return (not bad), ("; ".join(sorted(set(bad))[:3]) or "ok")


def _v_viewport_meta(html: str, spec: dict) -> tuple[bool, str]:
    ok = re.search(r'<meta[^>]+name\s*=\s*["\']viewport["\']', html, re.IGNORECASE) is not None
    return ok, ("ok" if ok else "missing <meta name=viewport>")


def _v_img_alt(html: str, spec: dict) -> tuple[bool, str]:
    bad = []
    for m in re.finditer(r"<img\b([^>]*)>", html, re.IGNORECASE):
        if not re.search(r"\balt\s*=", m.group(1), re.IGNORECASE):
            bad.append("img without alt")
    return (not bad), ("; ".join(sorted(set(bad))[:3]) or "ok")


def _v_icon_button_labels(html: str, spec: dict) -> tuple[bool, str]:
    bad = []
    for m in re.finditer(r"<button\b([^>]*)>(.*?)</button>", html, re.DOTALL | re.IGNORECASE):
        attrs, inner = m.groups()
        text = re.sub(r"<[^>]*>", "", inner).strip()
        if not text and not re.search(r"aria-label|title\s*=", attrs, re.IGNORECASE):
            bad.append("icon-only <button> without accessible name")
    return (not bad), ("; ".join(sorted(set(bad))[:3]) or "ok")


def _v_intl_jalali(html: str, spec: dict) -> tuple[bool, str]:
    ok = bool(
        re.search(r"Intl\.DateTimeFormat\s*\(\s*['\"]fa-IR", html)
        or re.search(r"fa-IR-u-ca-persian", html)
        or re.search(r"(from\s+['\"][^'\"]*(date-fns-jalali|jalaali-js)|require\(['\"](moment-jalaali)", html)
    )
    return ok, ("ok" if ok else "no Intl fa-IR / Jalali library usage found")


def _v_no_ltr_next_arrow(html: str, spec: dict) -> tuple[bool, str]:
    """A next/forward affordance must not use a right-pointing arrow near RTL nav words."""
    bad = []
    text = _strip_code_blocks(html)
    for word in spec.get("words", ["بعدی", "ادامه", "مرحله بعد"]):
        for m in re.finditer(re.escape(word), text):
            window = text[max(0, m.start() - 120) : m.end() + 120]
            if re.search(r"(ArrowRight|ChevronRight|\u2190?right arrow)", window) or re.search(
                r"[\u2192]", window
            ):
                bad.append(f"`{word}` near right-pointing arrow")
    return (not bad), ("; ".join(sorted(set(bad))[:3]) or "ok")


def _v_logical_text_align(html: str, spec: dict) -> tuple[bool, str]:
    bad = []
    for m in re.finditer(r"text-align\s*:\s*(left|right)\b", html, re.IGNORECASE):
        bad.append(f"text-align: {m.group(1)}")
    return (not bad), ("; ".join(bad[:3]) or "ok")


def _v_responsive_signals(html: str, spec: dict) -> tuple[bool, str]:
    """Evidence of responsive intent: viewport meta + (media queries or responsive classes)."""
    has_viewport = _v_viewport_meta(html, spec)[0]
    has_media = "@media" in html
    has_resp_classes = re.search(r"(?:sm|md|lg|xl):[\w\[\]]", html) is not None
    if has_viewport and (has_media or has_resp_classes):
        return True, "viewport + responsive signals found"
    if not has_viewport:
        return False, "missing viewport meta"
    return False, "no @media queries or responsive breakpoint classes (sm:/md:)"


_VALIDATORS = {
    "html_lang_dir": _v_html_lang_dir,
    "no_letter_spacing": _v_no_letter_spacing,
    "zwnj_min_count": _v_zwnj_min_count,
    "persian_digits_in_prose": _v_persian_digits_in_prose,
    "arabic_digits_in_prose": _v_arabic_digits_in_prose,
    "persian_punctuation": _v_persian_punctuation,
    "no_physical_margin": _v_no_physical_margin,
    "logical_tailwind": _v_logical_tailwind,
    "bidi_isolation": _v_bidi_isolation,
    "code_dir_ltr": _v_code_dir_ltr,
    "viewport_meta": _v_viewport_meta,
    "img_alt": _v_img_alt,
    "icon_button_labels": _v_icon_button_labels,
    "intl_jalali": _v_intl_jalali,
    "no_ltr_next_arrow": _v_no_ltr_next_arrow,
    "logical_text_align": _v_logical_text_align,
    "responsive_signals": _v_responsive_signals,
}


# ---------------------------------------------------------------- runner

def load_cases(cases_dir: Path) -> list[dict]:
    cases = []
    for p in sorted(cases_dir.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        data["_source"] = p.name
        cases.append(data)
    return cases


def run_case(case: dict, candidate_root: Path) -> dict:
    pattern = case.get("files", "**/*.html")
    matches = [p for p in sorted(candidate_root.glob(pattern)) if p.is_file()]
    if not matches:
        return {
            "id": case["id"], "category": case["category"],
            "status": "skipped", "reason": f"no file matching {pattern} in candidate",
            "checks": [],
        }
    target = matches[0]
    html = target.read_text(encoding="utf-8")
    checks = []
    passed_all = True
    for v in case.get("validation", []):
        vtype = v.get("type")
        fn = _VALIDATORS.get(vtype)
        if fn is None:
            checks.append({"type": vtype, "status": "error", "detail": "unknown validator"})
            passed_all = False
            continue
        try:
            ok, detail = fn(html, v)
        except Exception as e:  # validator crash = explicit failure, never a fake pass
            ok, detail = False, f"validator exception: {e!r}"
        checks.append({"type": vtype, "status": "pass" if ok else "fail", "detail": detail})
        passed_all = passed_all and ok
    return {
        "id": case["id"],
        "category": case["category"],
        "title": case.get("title", ""),
        "severity": case.get("severity", "P2"),
        "file": str(target),
        "status": "pass" if passed_all else "fail",
        "checks": checks,
    }


def run_benchmark(cases_dir: Path, candidate_root: Path, condition: str) -> dict:
    cases = load_cases(cases_dir)
    results = [run_case(c, candidate_root) for c in cases]
    by_cat: dict[str, dict[str, int]] = {}
    status_key = {"pass": "passed", "fail": "failed", "skipped": "skipped"}
    for r in results:
        cat = by_cat.setdefault(r["category"], {"total": 0, "passed": 0, "failed": 0, "skipped": 0})
        cat["total"] += 1
        cat[status_key[r["status"]]] += 1
    summary = {
        "total": len(results),
        "passed": sum(1 for r in results if r["status"] == "pass"),
        "failed": sum(1 for r in results if r["status"] == "fail"),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "categories": by_cat,
    }
    return {
        "tool": "raast-benchmark",
        "tool_version": __version__,
        "condition": condition,
        "candidate": str(candidate_root),
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "summary": summary,
        "cases": results,
        "limitations": [
            "Static validators inspect markup and text; they cannot certify visual rendering.",
            "Condition A/B results require running agents externally; this report only reflects the files given to it.",
            "Font availability and OS rendering differ across machines; browser suite adds computed-style checks but not pixel truth.",
        ],
    }


def benchmark_markdown(report: dict) -> str:
    s = report["summary"]
    lines = [
        f"# RAAST Benchmark Report — condition `{report['condition']}`",
        "",
        f"- Candidate: `{report['candidate']}`",
        f"- Evaluated at: {report['environment']['evaluated_at']}",
        f"- Result: **{s['passed']}/{s['total']} passed, {s['failed']} failed, {s['skipped']} skipped**",
        "",
        "| Category | Passed | Failed | Skipped |",
        "|---|---|---|---|",
    ]
    for cat, c in s["categories"].items():
        lines.append(f"| {cat} | {c['passed']} | {c['failed']} | {c['skipped']} |")
    lines += ["", "## Case detail", "", "| Case | Status | Failed checks |", "|---|---|---|"]
    for r in report["cases"]:
        failed = "; ".join(c["type"] for c in r["checks"] if c["status"] == "fail") or "—"
        lines.append(f"| `{r['id']}` | {r['status']} | {failed} |")
    lines += ["", "## Known limitations", ""]
    for lim in report["limitations"]:
        lines.append(f"- {lim}")
    lines.append("")
    return "\n".join(lines)
