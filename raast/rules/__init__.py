"""RAAST static diagnostics engine.

Rule inventory (IDs shared with skills/rtl-audit):
  RTL001  physical margin-left/right           P1  fixable
  RTL002  physical padding-left/right          P1  fixable
  RTL003  physical left:/right: positioning    P2  review-only
  RTL004  text-align: left|right               P1  fixable
  RTL005  letter-spacing on RTL script         P0* fixable    (*profile-driven:
         P0 on Arabic script (fa/ar), P1 on Hebrew (he), off for LTR hosts)
  RTL006  missing dir on <html>                P0  review-only (RTL hosts)
  RTL007  Tailwind translate-x-*               P2  review-only
  RTL008  Tailwind physical utilities          P1  fixable
  RTL009  Latin punctuation in Arabic prose    P2  opt-in fix
  RTL010  Western digits in Arabic prose       P2  config-gated (fa/ar only;
         Western digits are VALID in Hebrew/Spanish prose)
  RTL011  broken ZWNJ compounds                P1  fixable (--zwnj, fa only)
  RTL012  un-isolated LTR atoms in prose       P2  review-only (RTL hosts)
  RTL013  dir="ltr" on RTL-script-only element P0  review-only
  RTL014  missing lang on <html>               P1  review-only (all profiles)
  RTL015  un-isolated RTL atom in LTR prose    P1  review-only (es host)
  RTL016  RTL-run element without dir in LTR doc P1 review-only (es host)
  RTL017  missing inverted marks (¿ / ¡)       P2  review-only (es host)

False-positive policy: CSS/Tailwind rules only fire when the file itself
contains RTL-script evidence (Arabic or Hebrew), unless the rule is forced via
config (`"rules": {"RTL001": {"force": true}}`). A left/right declaration in a
pure-LTR file of a mixed project is NOT reported by default. CSS/Tailwind/
HTML-structure rules do not run on .md/.mdx at all — documents deliberately
illustrate WRONG patterns; prose rules handle markdown instead.

CSS-in-JS style objects: property names are normalized to kebab-case before
matching, so camelCase declarations in React inline styles, styled-components
and Emotion object syntax fire the same rules (marginLeft -> margin-left ->
RTL001). Suggested fixes preserve the spelling of the source: camelCase
sources get camelCase logical props (marginInlineStart), stylesheets get
kebab-case (margin-inline-start). Vendor-cased names (WebkitTransition)
normalize with a leading hyphen.

Profile-driven behavior (raast/profiles/*.json):
  direction=rtl (fa/ar/he) — RTL006 wants dir="rtl", RTL010/RTL009 fire only
  when the profile marks Western digits / Latin punctuation invalid, RTL012
  isolates LTR atoms, RTL013 flags dir="ltr" on RTL-script-only elements.
  direction=ltr (es host)  — RTL006 never fires (html stays LTR); RTL015
  requires RTL runs to be isolated, RTL016 requires dir on RTL-run elements,
  RTL017 checks RAE inverted marks; RTL005/RTL010 are inert.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..normalizer import ARABIC_RE, HEBREW_RE, RTL_SCRIPT_RE, detect_broken_zwnj
from ..profiles import load_profile

CSS_EXT = {".css", ".scss", ".sass"}
TAILWIND_EXT = {".html", ".vue", ".jsx", ".tsx", ".js", ".ts", ".mjs", ".astro", ".svelte", ".mdx", ".md", ".php"}
PROSE_EXT = {".html", ".vue", ".jsx", ".tsx", ".js", ".ts", ".mjs", ".astro", ".svelte", ".mdx", ".md", ".txt"}

SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}

FORCEABLE_CSS_RULES = {"RTL001", "RTL002", "RTL003", "RTL004", "RTL005", "RTL008"}


@dataclass
class Finding:
    rule: str
    severity: str  # P0 | P1 | P2
    confidence: str  # high | medium | low
    file: str
    line: int
    column: int | None
    message: str
    explanation: str
    suggested_fix: str
    fixable: bool = False

    def as_dict(self) -> dict:
        return {
            "rule": self.rule, "severity": self.severity, "confidence": self.confidence,
            "file": self.file, "line": self.line, "column": self.column,
            "message": self.message, "explanation": self.explanation,
            "suggested_fix": self.suggested_fix, "fixable": self.fixable,
        }


def _has_arabic(text: str) -> bool:
    return bool(ARABIC_RE.search(text))


def _has_rtl_script(text: str) -> bool:
    """Arabic OR Hebrew script evidence — gates source-code rules."""
    return bool(RTL_SCRIPT_RE.search(text))


_RTL_RUN_RE = re.compile(
    r"(?:" + RTL_SCRIPT_RE.pattern + r")+(?:\s+(?:" + RTL_SCRIPT_RE.pattern + r")+)*"
)


def _force_enabled(config: dict, rule_id: str) -> bool:
    opts = config.get("rules", {}).get(rule_id, {})
    return bool(isinstance(opts, dict) and opts.get("force"))


def _strip_inline_code_and_fences(text: str) -> tuple[str, dict[int, int]]:
    """Mask fenced blocks + inline code + URLs for prose analysis; map lines back."""
    out_lines: list[str] = []
    mapping: dict[int, int] = {}
    in_fence = False
    for orig_no, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        stripped = re.sub(r"`[^`]*`", "", line)
        stripped = re.sub(r"https?://\S+", "", stripped)
        out_lines.append(stripped)
        mapping[len(out_lines)] = orig_no
    return "\n".join(out_lines), mapping


# ---------------------------------------------------------------- CSS rules

_CSS_DECL = re.compile(r"(?P<prop>[-a-zA-Z]+)\s*:\s*(?P<value>(?:[^;{},]|\,(?!\s*[-a-zA-Z]+\s*:))+)")

# text-align / textAlign — matches stylesheet and style-object spellings, and
# keeps the quote character of the source value ('left' stays quoted in the
# suggested fix). The kebab alternative is case-insensitive (CSS property
# names are) but requires the hyphen, so a JS identifier like `textalign`
# never half-matches; the camel alternative is exact — React style objects
# spell it textAlign. The trailing lookahead stops before the next token so
# a value like leftward never half-matches.
_ALIGN_DECL = re.compile(
    r"(?P<prop>(?i:text-align)|textAlign)"
    r"(?P<sep>\s*:\s*)"
    r"(?P<q>['\"]?)"
    r"(?P<val>(?i:left|right))"
    r"(?P=q)"
    r"(?=[\s,;})]|$)",
)

_PHYSICAL = {
    "margin-left": ("RTL001", "start"),
    "margin-right": ("RTL001", "end"),
    "padding-left": ("RTL002", "start"),
    "padding-right": ("RTL002", "end"),
}

# --- CSS-in-JS style-object support ----------------------------------------
# React inline styles, styled-components and Emotion object syntax spell CSS
# properties in camelCase (marginLeft) or vendor-cased (WebkitTransition).
# The rules below normalize property names to kebab-case before matching, so
# a single rule set covers stylesheets and style objects alike.
_VENDOR_PREFIX = re.compile(r"^(Webkit|Moz|ms|O|Khtml)(?=[A-Z])")
_CAMEL_BOUNDARY = re.compile(r"([a-z0-9])([A-Z])")


_CAMEL_VENDOR_PREFIX = re.compile(r"^(webkit|moz|ms|o|khtml)(?=[A-Z])", re.IGNORECASE)


def _kebab_prop(prop: str) -> str:
    """Normalize a CSS property name (kebab- or camelCase) to kebab-case.

    Vendor-prefixed React names (WebkitTransition, msTransform) normalize
    with a leading hyphen: -webkit-transition, -ms-transform. The camelCase
    vendor spellings that _camel_prop produces (MsWebkit from -ms-webkit)
    must re-normalize to the same kebab form — kebab(camel(kebab)) is a
    true round-trip.
    """
    m = _VENDOR_PREFIX.match(prop)
    if m:
        body = prop[m.end():]
        return f"-{m.group(1).lower()}-{_CAMEL_BOUNDARY.sub(r'\1-\2', body).lower()}"
    # _camel_prop capitalizes the vendor segment (MsWebkit); a lowercase
    # standard property never has a camel boundary right after a vendor-
    # shaped head followed by an uppercase letter, so this cannot swallow
    # ordinary names (objectFit -> 'o'+'bjectFit' has no uppercase 'F'
    # directly after the one-letter head 'o'... 'objectFit' fails the
    # (?=[A-Z]) probe and stays on the standard path).
    m2 = _CAMEL_VENDOR_PREFIX.match(prop)
    if m2 and _CAMEL_BOUNDARY.search(prop):
        body = prop[m2.end():]
        return f"-{m2.group(1).lower()}-{_CAMEL_BOUNDARY.sub(r'\1-\2', body).lower()}"
    return _CAMEL_BOUNDARY.sub(r"\1-\2", prop).lower()


def _camel_prop(kebab: str) -> str:
    """kebab-case -> camelCase (React style-object spelling).

    margin-inline-start -> marginInlineStart; -webkit-mask-composite ->
    WebkitMaskComposite. Vendor casing follows the DOM/React convention:
    -webkit-/-moz-/-khtml-/-o- capitalize (WebkitX, MozX), but -ms- keeps
    the lowercase spelling React itself uses (msTransform). Standard
    properties keep a lowercase first letter.
    """
    vendor = kebab.startswith("-")
    parts = kebab.lstrip("-").split("-")
    head = parts[0]
    if vendor and head != "ms":
        head = head.capitalize()
    return head + "".join(w.capitalize() for w in parts[1:])


def _is_style_object_name(prop: str) -> bool:
    """True when the property is spelled in camelCase (a JS style object).

    Uppercase-only names (MARGIN-LEFT, valid but unusual CSS) and plain
    kebab-case stay on the stylesheet path.
    """
    return _CAMEL_BOUNDARY.search(prop) is not None


def rule_css_physical(path: str, content: str, config: dict) -> list[Finding]:
    if not _has_rtl_script(content) and not _force_enabled(config, "RTL001"):
        return []
    findings: list[Finding] = []
    for i, line in enumerate(content.splitlines(), 1):
        for m in _CSS_DECL.finditer(line):
            prop = m.group("prop").strip()
            prop_kebab = _kebab_prop(prop)
            if prop_kebab in _PHYSICAL:
                rule, end = _PHYSICAL[prop_kebab]
                axis = "margin" if rule == "RTL001" else "padding"
                logical_kebab = f"{axis}-inline-{end}"
                camel = _is_style_object_name(prop)
                logical = _camel_prop(logical_kebab) if camel else logical_kebab
                scoped_ltr = '[dir="ltr"]' in line
                findings.append(Finding(
                    rule=rule, severity="P1",
                    confidence="low" if scoped_ltr else "high",
                    file=path, line=i, column=m.start("prop") + 1,
                    message=f"physical {prop} declaration",
                    explanation=(
                        f"`{prop}` hardcodes one side of the inline axis. Under dir=\"rtl\" the "
                        "visual side flips, so spacing lands on the wrong side."
                        if not scoped_ltr else
                        "Declaration appears inside a [dir=\"ltr\"] scope — verify it is intentional."
                    ),
                    suggested_fix=f"{logical}: {m.group('value').strip()}",
                    fixable=not scoped_ltr,
                ))
    return findings


def rule_css_text_align(path: str, content: str, config: dict) -> list[Finding]:
    if not _has_rtl_script(content) and not _force_enabled(config, "RTL004"):
        return []
    findings = []
    for i, line in enumerate(content.splitlines(), 1):
        for m in _ALIGN_DECL.finditer(line):
            val = m.group("val").lower()
            camel = _is_style_object_name(m.group("prop"))
            scoped_ltr = '[dir="ltr"]' in line or "dir='ltr'" in line
            findings.append(Finding(
                rule="RTL004", severity="P1",
                confidence="low" if scoped_ltr else "high",
                file=path, line=i, column=m.start("prop") + 1,
                message=f"{m.group('prop') if camel else 'text-align'}: {val}",
                explanation=(
                    "Physical alignment does not flip with document direction. "
                    "start/end track the inline direction in both LTR and RTL."
                    if not scoped_ltr else
                    "Declaration appears inside a [dir=\"ltr\"] scope — verify it is intentional."
                ),
                suggested_fix=(
                    f"{m.group('prop')}{m.group('sep')}"
                    f"{m.group('q')}{'start' if val == 'left' else 'end'}{m.group('q')}"
                    if camel else
                    f"text-align: {'start' if val == 'left' else 'end'}"
                ),
                fixable=not scoped_ltr,
            ))
    return findings


def rule_css_left_right(path: str, content: str, config: dict) -> list[Finding]:
    if not _has_rtl_script(content) and not _force_enabled(config, "RTL003"):
        return []
    findings = []
    for i, line in enumerate(content.splitlines(), 1):
        for m in _CSS_DECL.finditer(line):
            prop = m.group("prop").strip()
            if _kebab_prop(prop) in ("left", "right"):
                findings.append(Finding(
                    rule="RTL003", severity="P2", confidence="medium",
                    file=path, line=i, column=m.start("prop") + 1,
                    message=f"physical `{prop}:` positioning",
                    explanation=(
                        "Positioned elements anchored with left/right do not mirror under RTL. "
                        "Many uses are intentional (decorations, JS-measured positions) — review, "
                        "then prefer inset-inline-start/end for layout anchors."
                    ),
                    suggested_fix="review; prefer inset-inline-start / inset-inline-end",
                    fixable=False,
                ))
    return findings


def rule_css_letter_spacing(path: str, content: str, config: dict,
                            profile: dict | None = None) -> list[Finding]:
    if profile is None:
        profile = load_profile("fa")
    ls_mode = profile.get("typography", {}).get("letter_spacing", "forbidden_on_arabic_script")
    if ls_mode == "allowed":
        return []
    if not _has_rtl_script(content) and not _force_enabled(config, "RTL005"):
        return []
    severity = "P0" if ls_mode == "forbidden_on_arabic_script" else "P1"
    explanation = (
        "Arabic-script letters are cursive and joined; non-zero letter-spacing inserts "
        "gaps between joined glyphs and visually shatters words "
        "(«مدیریت» renders as م د ی ر ی ت)."
        if severity == "P0"
        else "Hebrew word cohesion and final-form letter rhythm (ך ם ן ף ץ) break under "
        "letter-spacing; justify with word spacing, or use size/weight for emphasis."
    )
    findings = []
    for i, line in enumerate(content.splitlines(), 1):
        # Value token must stop before quotes/backticks — `` `letter-spacing: 0` ``
        # in markdown prose must resolve to "0" (legal), not "0`" (false positive).
        # Style-object values may be quoted ('2px') — the quote is captured and
        # echoed so the finding text stays true to the source.
        m = re.search(
            r"(?:letter-spacing|letterSpacing)\s*:\s*(['\"]?)([^\s;{},'\"`]+)(?:\1)", line)
        if not m:
            continue
        value = m.group(2)
        if value.lower() in ("normal", "inherit", "initial", "unset", "0", "0px", "0em", "0rem"):
            continue
        findings.append(Finding(
            rule="RTL005", severity=severity, confidence="high",
            file=path, line=i, column=m.start() + 1,
            message=f"letter-spacing: {m.group(1)}{value}{m.group(1)}",
            explanation=explanation,
            suggested_fix="remove the declaration (use size/weight for display emphasis)",
            fixable=True,
        ))
    return findings


# ---------------------------------------------------------------- HTML rules

_DIR_ATTR_RE = re.compile(r"\bdir\s*=\s*[\"'](rtl|ltr|auto)[\"']", re.IGNORECASE)


def rule_html_meta(path: str, content: str, project_lang: str,
                   profile: dict | None = None) -> list[Finding]:
    findings = []
    if not path.endswith(".html") or not _has_rtl_script(content):
        return findings
    if profile is None:
        try:
            profile = load_profile(project_lang)
        except Exception:
            profile = {}
    direction = profile.get("direction", "rtl")
    html_tag = re.search(r"<html\b([^>]*)>", content, re.IGNORECASE)
    if not html_tag:
        return findings
    attrs = html_tag.group(1)
    line_no = content[: html_tag.start()].count("\n") + 1
    if direction == "rtl" and not _DIR_ATTR_RE.search(attrs):
        findings.append(Finding(
            rule="RTL006", severity="P0", confidence="high",
            file=path, line=line_no,
            column=html_tag.start() - content.rfind("\n", 0, html_tag.start()),
            message="<html> without dir attribute",
            explanation=(
                f"Document contains {project_lang} text but no dir attribute. Browsers, screen "
                "readers, scrollbars and form controls all key off document direction."
            ),
            suggested_fix=f'<html lang="{project_lang}" dir="rtl">',
            fixable=False,
        ))
    if not re.search(r"\blang\s*=\s*[\"'][a-zA-Z-]+[\"']", attrs, re.IGNORECASE):
        findings.append(Finding(
            rule="RTL014", severity="P1", confidence="high",
            file=path, line=line_no,
            column=html_tag.start() - content.rfind("\n", 0, html_tag.start()),
            message="<html> without lang attribute",
            explanation="Screen readers select the pronunciation voice from lang; absence mispronounces the page.",
            suggested_fix=(
                f'<html lang="{project_lang}" dir="rtl">'
                if direction == "rtl" else
                f'<html lang="{project_lang}">'
            ),
            fixable=False,
        ))
    return findings


def rule_html_dir_ltr_on_arabic(path: str, content: str) -> list[Finding]:
    findings = []
    if not any(path.endswith(e) for e in (".html", ".vue", ".astro")):
        return findings
    for m in re.finditer(
        r"<([a-zA-Z][^\s>/]*)\b([^>]*\bdir\s*=\s*[\"']ltr[\"'][^>]*)>([^<]*)",
        content, re.IGNORECASE,
    ):
        inner = m.group(3).strip()
        if inner and RTL_SCRIPT_RE.search(inner) and not re.search(r"[A-Za-z0-9]", inner):
            line_no = content[: m.start()].count("\n") + 1
            findings.append(Finding(
                rule="RTL013", severity="P0", confidence="medium",
                file=path, line=line_no, column=None,
                message=f'dir="ltr" on <{m.group(1)}> containing only RTL-script text',
                explanation="Forcing LTR direction on Arabic/Hebrew content misorders the inline text.",
                suggested_fix='remove dir="ltr" or use dir="auto"',
                fixable=False,
            ))
    return findings


def rule_html_rtl_unmarked(path: str, content: str) -> list[Finding]:
    """RTL016 — RTL-script-only element with no dir/bdi, in an LTR-host document.

    A bare RTL run inside an LTR page visually reorders the surrounding
    punctuation and numbers; the run must declare its direction. Elements
    inside a dir="rtl" ancestor scope inherit the correct direction and are
    NOT flagged — a legitimately scoped RTL section must never produce
    findings on its children.
    """
    findings = []
    if not any(path.endswith(e) for e in (".html", ".vue", ".astro")):
        return findings
    rtl_scopes = _dir_scope_spans(content, "rtl")

    def inside_rtl_scope(pos: int) -> bool:
        return any(start <= pos < end for start, end in rtl_scopes)

    for m in re.finditer(r"<([a-zA-Z][^\s>/]*)\b([^>]*)>([^<]*)", content, re.IGNORECASE):
        tag = m.group(1).lower()
        attrs, inner = m.group(2), m.group(3).strip()
        if tag in ("html", "head", "body", "script", "style", "bdi", "br", "img", "input", "meta", "link"):
            continue
        if inside_rtl_scope(m.start()):
            continue
        if (
            inner
            and RTL_SCRIPT_RE.search(inner)
            and not re.search(r"[A-Za-z0-9]", inner)
            and not _DIR_ATTR_RE.search(attrs)
        ):
            line_no = content[: m.start()].count("\n") + 1
            findings.append(Finding(
                rule="RTL016", severity="P1", confidence="medium",
                file=path, line=line_no, column=None,
                message=f"<{tag}> carries only RTL-script text without a direction attribute",
                explanation=(
                    "In an LTR host document an unmarked RTL run visually reorders the "
                    "surrounding punctuation and numbers (bidi mirroring defects)."
                ),
                suggested_fix='wrap the RTL run in <bdi>…</bdi> or set dir="rtl" on the element',
                fixable=False,
            ))
    return findings


# ---------------------------------------------------------------- Tailwind rules

# Tailwind class tokens. Lookbehind AND lookahead word-boundary guards prevent
# matches inside hyphenated English prose such as "right-to-left" or "left-aligned"
# (which are words, not utilities).
_TW_SPACING = re.compile(r"(?<![\w-])(-?)(?:ml|mr|pl|pr)-[\w[\].%/]+(?![\w-])")
_TW_TEXTALIGN = re.compile(r"(?<![\w-])text-(left|right)\b")
_TW_INSET = re.compile(r"(?<![\w-])(-?)(?:left|right)-[\w[\].%/]+(?![\w-])")
_TW_BORDER = re.compile(r"(?<![\w-])border-[lr]-[\w[\].%/]+(?![\w-])")
_TW_ROUNDED = re.compile(r"(?<![\w-])rounded-[lr][\w[\].%-]*(?![\w-])")
_TW_TRANSLATE = re.compile(r"(?<![\w-])-?translate-x-[\w[\].%/]+(?![\w-])")


def _tw_fix(token: str) -> str | None:
    mapping = {"text-left": "text-start", "text-right": "text-end"}
    if token in mapping:
        return mapping[token]
    m = re.fullmatch(r"(-?)(ml|mr|pl|pr)-([\w./%-]+)", token)
    if m:
        sign, side, val = m.groups()
        end = "e" if side in ("mr", "pr") else "s"
        kind = "m" if side in ("ml", "mr") else "p"
        return f"{sign}{kind}{end}-{val}"
    return None


def rule_tailwind(path: str, content: str, config: dict) -> list[Finding]:
    if not _has_rtl_script(content) and not _force_enabled(config, "RTL008"):
        return []
    findings: list[Finding] = []
    for i, line in enumerate(content.splitlines(), 1):
        for rx, kind in (
            (_TW_SPACING, "spacing"),
            (_TW_TEXTALIGN, "alignment"),
            (_TW_INSET, "inset"),
            (_TW_BORDER, "border"),
            (_TW_ROUNDED, "radius"),
        ):
            for m in rx.finditer(line):
                token = m.group(0)
                fix = _tw_fix(token)
                findings.append(Finding(
                    rule="RTL008",
                    severity="P1",
                    confidence="high" if fix else "medium",
                    file=path, line=i, column=m.start() + 1,
                    message=f"Tailwind physical utility `{token}`",
                    explanation=(
                        f"Physical {kind} utility does not mirror under dir=\"rtl\"; the logical "
                        "variant flips automatically in both directions."
                    ),
                    suggested_fix=f"`{fix}`" if fix else "logical variant (ms/me/ps/pe/start/end)",
                    fixable=fix is not None,
                ))
        for m in _TW_TRANSLATE.finditer(line):
            findings.append(Finding(
                rule="RTL007", severity="P2", confidence="medium",
                file=path, line=i, column=m.start() + 1,
                message=f"Tailwind `{m.group(0)}`",
                explanation=(
                    "translate-x does not mirror with direction; drawers, sliders and shimmer "
                    "effects move the wrong way under RTL unless mirrored explicitly."
                ),
                suggested_fix="mirror with rtl:-translate-x-* twin or logical custom properties",
                fixable=False,
            ))
    return findings


# ---------------------------------------------------------------- prose rules


_VOID_ELEMENTS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
})

# Bidi controls + ZWNJ: numeric character references for THESE are decoded
# before prose analysis (isolation written as &#x2066;…&#x2069; or a ZWNJ
# written as &#x200C; is real to the browser and must be real to the engine).
_BIDI_CONTROL_CHARS = frozenset({
    "\u200c",  # ZWNJ
    "\u200e", "\u200f",  # LRM, RLM
    "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",  # embedding controls
    "\u2066", "\u2067", "\u2068", "\u2069",  # isolates
})

_TAG_TOKEN_RE = re.compile(r"<(/?)([a-zA-Z][^\s>/]*)([^>]*?)(/?)>")


_DIR_ATTR_RE_ATTR = re.compile(r"\bdir\s*=\s*[\"'](rtl|ltr|auto)[\"']", re.IGNORECASE)


def _dir_scope_spans(text: str, dir_value: str) -> list[tuple[int, int]]:
    """Spans of every region ISOLATED as <dir_value> by an element's dir attr.

    Isolation is an INHERITED-DIRECTION DEVIATION, not a literal attribute
    match: an element isolates content only when its dir differs from the
    direction it inherits. This is what makes the browser behave correctly
    and keeps the analyzer honest:

      - <span dir="ltr"> inside an RTL context  -> isolated LTR atom (masked)
      - <html dir="ltr"> on an LTR page         -> the document baseline,
        NOT isolation (treating it as a scope once masked the entire body of
        every canonical es page and silenced RTL015/016/017 — bug-corpus
        CS-008/012/032 regression)
      - <section dir="rtl"> inside an LTR page  -> isolated RTL scope

    The <html> element always establishes the baseline and never isolates.
    Stack-based scan (handles nesting and mixed tag soup; regexes with a
    fixed tag list missed structural containers). Unclosed scopes extend to
    end-of-text; stray close tags are ignored.
    """
    spans: list[tuple[int, int]] = []
    # stack entries: (tag, scope_start_or_None, inherited_dir_at_entry)
    inherited: str | None = None
    stack: list[tuple[str, int | None, str | None]] = []
    for m in _TAG_TOKEN_RE.finditer(text):
        closing, tag, attrs, self_close = m.group(1), m.group(2).lower(), m.group(3), m.group(4)
        if closing:
            if not stack:
                continue  # stray close tag
            # close the nearest open element with this tag name. HTML allows
            # implicit closing (</body> ends an unclosed <section> too), so
            # every element nested INSIDE the closed one also ends here —
            # emit any scope it carries, then drop the whole tail.
            for i in range(len(stack) - 1, -1, -1):
                if stack[i][0] == tag:
                    for _t, scope_start, _inh in stack[i:]:
                        if scope_start is not None:
                            spans.append((scope_start, m.end()))
                    inherited = stack[i][2]
                    del stack[i:]
                    break
            continue
        if tag in _VOID_ELEMENTS or self_close:
            continue
        attr = _DIR_ATTR_RE_ATTR.search(attrs)
        declared = attr.group(1).lower() if attr else None
        if tag == "html":
            # document baseline: never an isolation scope itself
            stack.append((tag, None, inherited))
            if declared and declared != "auto":
                inherited = declared
            continue
        if declared and declared != "auto" and declared != inherited:
            stack.append((tag, m.start(), inherited))
            inherited = declared
        else:
            stack.append((tag, None, inherited))
    for _t, scope_start, _inh in stack:
        if scope_start is not None:
            spans.append((scope_start, len(text)))
    return spans


def _mask_spans_whitespace(text: str, spans: list[tuple[int, int]]) -> str:
    """Blank every char of *spans* except newlines (line mapping survives)."""
    out = list(text)
    for start, end in spans:
        for i in range(start, min(end, len(out))):
            if out[i] != "\n":
                out[i] = " "
    return "".join(out)


def _strip_markup_for_prose(content: str, suffix: str,
                            mask_rtl_isolates: bool = False) -> tuple[str, dict[int, int]]:
    """Reduce markup documents to visible text for prose rules, preserving line numbers.

    - script/style blocks are blanked out (their contents are code, not prose)
    - tags are removed per line (attributes like className digits must not trigger
      RTL009/010/011/012/015/017 — only human-visible text is prose)
    - for markdown/txt: fenced blocks + inline code + URLs are masked instead
    - RTL hosts: <bdi>/dir="ltr" scopes are masked (protected LTR atoms). LTR
      hosts (es): <bdi>/dir="rtl" scopes are masked as well — isolated RTL
      atoms are the engine's OWN recommendation and must never re-flag as
      RTL015, no matter which container element carries the dir attribute.
    """
    mapping: dict[int, int] = {}
    if suffix in (".md", ".mdx", ".txt"):
        masked, mapping = _strip_inline_code_and_fences(content)
        return masked, mapping

    # Numeric character references for bidi controls and ZWNJ decode to the
    # real character BEFORE analysis — a browser renders &#x2066; as U+2066,
    # so an isolate written as an entity must be recognized as isolation and
    # never re-flagged. Decoding is limited to the control set: decoding the
    # full entity table would turn visible &lt;p&gt; text into tag soup.
    def _decode_bidi_entity(m: re.Match) -> str:
        cp = int(m.group(1), 16) if m.group(1) else int(m.group(2))
        ch = chr(cp)
        return ch if ch in _BIDI_CONTROL_CHARS else m.group(0)

    content = re.sub(
        r"&#(?:x([0-9A-Fa-f]+)|([0-9]+));",
        _decode_bidi_entity, content, flags=re.IGNORECASE,
    )

    def blank_block(m: re.Match) -> str:
        return "\n" * m.group(0).count("\n")

    text = re.sub(r"<script\b.*?</script\s*>", blank_block, content, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style\b.*?</style\s*>", blank_block, text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<!--.*?-->", blank_block, text, flags=re.DOTALL)
    # Isolated regions (<bdi>, dir="ltr"/dir="rtl" scopes) are the engine's OWN
    # recommendation — their contents are protected atoms and must never
    # re-flag as RTL009/010/012/015 findings. The benchmark validator follows
    # the same isolation model.
    ltr_spans = _dir_scope_spans(text, "ltr")
    bdi_spans: list[tuple[int, int]] = []
    bdi_open: int | None = None
    for m in _TAG_TOKEN_RE.finditer(text):
        closing, tag = m.group(1), m.group(2).lower()
        if tag != "bdi":
            continue
        if not closing:
            if bdi_open is None:
                bdi_open = m.start()
        elif bdi_open is not None:
            bdi_spans.append((bdi_open, m.end()))
            bdi_open = None
    text = _mask_spans_whitespace(text, ltr_spans + bdi_spans)
    if mask_rtl_isolates:
        text = _mask_spans_whitespace(text, _dir_scope_spans(text, "rtl"))
    text = re.sub(r"<[^>\n]*>", "", text)
    out_lines = []
    for orig_no, line in enumerate(text.splitlines(), 1):
        stripped = re.sub(r"`[^`]*`", "", line)
        stripped = re.sub(r"https?://\S+", "", stripped)
        out_lines.append(stripped)
        mapping[len(out_lines)] = orig_no
    return "\n".join(out_lines), mapping


def rule_prose(path: str, content: str, profile: dict, options: dict | None = None,
               suffix: str = "") -> list[Finding]:
    options = options or {}
    findings: list[Finding] = []
    lang = profile.get("code", "fa")
    direction = profile.get("direction", "rtl")
    digits_name = profile.get("numerals", {}).get("display", "٠–٩/۰–۹")
    digits_invalid = (
        profile.get("numerals", {}).get("western_digits_in_prose") == "invalid_in_prose"
    )
    script_re = HEBREW_RE if profile.get("script") == "hebrew" else ARABIC_RE
    masked, mapping = _strip_markup_for_prose(
        content, suffix, mask_rtl_isolates=(direction == "ltr"),
    )

    digits_ok = options.get("allow_western_digits_in_prose", False)
    punct_ok = options.get("allow_latin_punctuation_in_prose", False)
    inverted = profile.get("punctuation", {}).get("inverted_marks") == "required"

    for masked_no, line in enumerate(masked.splitlines(), 1):
        orig_no = mapping[masked_no]

        if direction == "ltr":
            # ---- LTR host (es): RTL runs must be isolated; RAE inverted marks.
            for m in _RTL_RUN_RE.finditer(line):
                findings.append(Finding(
                    rule="RTL015", severity="P1", confidence="medium",
                    file=path, line=orig_no, column=m.start() + 1,
                    message=f"un-isolated RTL atom: {m.group(0)[:32]}…",
                    explanation=(
                        "Arabic/Hebrew runs inside LTR prose visually reorder the surrounding "
                        "punctuation and numbers; isolate the run to pin its direction."
                    ),
                    suggested_fix='wrap in <bdi>…</bdi> or <span dir="rtl">…</span>',
                    fixable=False,
                ))
            if inverted:
                for m in re.finditer(r"\?(?!\?)", line):
                    head = line[: m.start()]
                    if "¿" in head or not re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñü]", head):
                        continue
                    findings.append(Finding(
                        rule="RTL017", severity="P2", confidence="medium",
                        file=path, line=orig_no, column=m.start() + 1,
                        message="question ends with '?' but has no opening '¿'",
                        explanation=(
                            "RAE requires the opening inverted question mark on Spanish questions; "
                            "its absence is the most visible machine-generated-Spanish defect."
                        ),
                        suggested_fix="add '¿' at the start of the question",
                        fixable=False,
                    ))
                for m in re.finditer(r"!(?!!)", line):
                    head = line[: m.start()]
                    if "¡" in head or not re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñü]", head):
                        continue
                    findings.append(Finding(
                        rule="RTL017", severity="P2", confidence="medium",
                        file=path, line=orig_no, column=m.start() + 1,
                        message="exclamation ends with '!' but has no opening '¡'",
                        explanation="RAE requires the opening inverted exclamation mark on Spanish exclamations.",
                        suggested_fix="add '¡' at the start of the exclamation",
                        fixable=False,
                    ))
            continue

        if not script_re.search(line):
            continue

        # RTL011 — broken ZWNJ compounds
        for _ln, before, after in detect_broken_zwnj(line):
            col = line.find(before) + 1
            findings.append(Finding(
                rule="RTL011", severity="P1", confidence="high",
                file=path, line=orig_no, column=col if col > 0 else None,
                message=f"broken ZWNJ compound: «{before}»",
                explanation="Affix written with a space instead of U+200C — the most visible Persian orthography defect.",
                suggested_fix=f"«{after}»",
                fixable=True,
            ))

        # Collect LTR-atom spans first so RTL010 can suppress phone/URL internals.
        # An atom already wrapped in bidi isolates (U+2066..U+2069, LRM/RLM,
        # embedding controls — including entities decoded above) IS isolated:
        # flagging it would punish the exact fix RTL012 recommends.
        _ISOLATE_CHARS = {"\u2066", "\u2067", "\u2068", "\u2069",
                          "\u200e", "\u200f", "\u202a", "\u202b", "\u202c"}
        atom_spans: list[tuple[int, int]] = []
        for m in re.finditer(
            r"(?<![\w>])([\w.+-]+@[\w-]+\.\w+|https?://\S+|\+\d[\d\s-]{6,}\d|\$\d+(?:\.\d+)?)",
            line,
        ):
            atom_spans.append(m.span())
            before = line[m.start() - 1] if m.start() > 0 else ""
            after = line[m.end()] if m.end() < len(line) else ""
            if before in _ISOLATE_CHARS or after in _ISOLATE_CHARS:
                continue
            findings.append(Finding(
                rule="RTL012", severity="P2", confidence="medium",
                file=path, line=orig_no, column=m.start() + 1,
                message=f"un-isolated LTR atom: {m.group(1)[:32]}…",
                explanation="URLs/emails/phones/currency inside RTL prose reorder without isolation (bdi, dir=ltr, or bidi isolate marks).",
                suggested_fix='wrap in <bdi>…</bdi>, <span dir="ltr">…</span>, or bidi isolate marks (U+2066 … U+2069)',
                fixable=False,
            ))

        def in_atom(pos: int) -> bool:
            return any(s <= pos < e for s, e in atom_spans)

        # RTL009 — Latin punctuation in Arabic prose
        if not punct_ok:
            for m in re.finditer(r"(?<=[\u0600-\u06FF])\s*[,;?](?=[\u0600-\u06FF\s]|$)", line):
                repl = {"": "،", ",": "،", "?": "؟", ";": "؛"}.get(m.group(0).strip(), "،")
                findings.append(Finding(
                    rule="RTL009", severity="P2", confidence="high",
                    file=path, line=orig_no, column=m.start() + 1,
                    message=f"Latin punctuation `{m.group(0).strip()}` inside {lang} prose",
                    explanation=f"{lang} prose uses its own marks (، ؟ ؛); Latin marks read as machine-generated output.",
                    suggested_fix=f"«{repl}»",
                    fixable=False,
                ))

        # RTL010 — Western digits in RTL prose (fa/ar only — Hebrew and Spanish
        # use Western digits natively; suppressed inside LTR atoms)
        if digits_invalid and not digits_ok:
            for m in re.finditer(r"[0-9]+", line):
                if in_atom(m.start()):
                    continue
                before_ok = m.start() == 0 or ARABIC_RE.match(line[m.start() - 1]) or line[m.start() - 1].isspace()
                after_ok = m.end() >= len(line) or ARABIC_RE.match(line[m.end()]) or line[m.end()].isspace()
                if not (before_ok and after_ok):
                    continue
                findings.append(Finding(
                    rule="RTL010", severity="P2", confidence="medium",
                    file=path, line=orig_no, column=m.start() + 1,
                    message=f"Western digits `{m.group(0)}` in {lang} prose",
                    explanation=(
                        f"{lang} copy uses {digits_name} digits. Exceptions (phones, serials, code) "
                        "should be isolated instead — see rtl-bidi."
                    ),
                    suggested_fix=f"convert to {digits_name} digits or isolate with <bdi>/dir=ltr",
                    fixable=False,
                ))
    return findings


# ---------------------------------------------------------------- engine


@dataclass
class RuleContext:
    config: dict
    profile: dict

    @property
    def lang(self) -> str:
        return self.config.get("language", "fa")


def run_rules(path: Path, rel: str, content: str, ctx: RuleContext) -> list[Finding]:
    findings: list[Finding] = []
    suffix = path.suffix.lower()
    # Markdown is documentation: it deliberately shows WRONG patterns inside
    # code fences and inline spans ("/* WRONG — breaks joining */"). CSS,
    # Tailwind and HTML-structure rules are source-code rules and would only
    # produce false positives there. Prose rules (ZWNJ, digits, punctuation,
    # LTR atoms) still scan markdown with their own fence/inline-code masking.
    is_markup_doc = suffix in (".md", ".mdx")
    if not is_markup_doc:
        findings += rule_css_physical(rel, content, ctx.config)
        findings += rule_css_text_align(rel, content, ctx.config)
        findings += rule_css_left_right(rel, content, ctx.config)
        findings += rule_css_letter_spacing(rel, content, ctx.config, ctx.profile)
        findings += rule_html_meta(rel, content, ctx.lang, ctx.profile)
        findings += rule_html_dir_ltr_on_arabic(rel, content)
        if ctx.profile.get("direction", "rtl") == "ltr":
            findings += rule_html_rtl_unmarked(rel, content)
        findings += rule_tailwind(rel, content, ctx.config)
    if suffix in PROSE_EXT:
        findings += rule_prose(rel, content, ctx.profile, ctx.config.get("rules", {}),
                               suffix=suffix)
    return findings
