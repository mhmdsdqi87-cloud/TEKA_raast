"""RAAST Language Quality Gate (raast-i18n).

Translation-quality scans for locale files. RAAST's static engine
(raast.rules, namespace RTL001-017) audits rendered pages; this gate audits
the locale JSON that feeds them, with its own rule namespace LQG001-009:

  LQG001  missing key (source key absent in target)               P1  high
  LQG002  empty value ("" or whitespace-only)                     P1  high
  LQG003  placeholder mismatch ({name} {0} {{name}} %s %d %1$s)   P1  high
  LQG004  untranslated value (identical to source, prose-like)    P2  medium
  LQG005  length anomaly (>2.5x source, or <40% when source > 20) P2  medium
  LQG006  Latin sentence punctuation / Western digits in
          Arabic-script prose (fa/ar and Arabic-majority values;
          he/es exempt)                                           P2  medium
  LQG007  un-isolated Latin run (3+ chars) in RTL-majority value  P2  medium
  LQG008  Arabic Yeh/Kaf inside Persian strings                   P1  high
  LQG009  Hebrew niqqud in production copy (--hebrew-diacritics)  P2  low

Usage:
  python3 -m raast.i18n scan --locales DIR [--source en]
      [--targets fa,ar,he,es] [--format text|json|markdown]
      [--max-errors N] [--hebrew-diacritics]

Design notes (full contract in docs/i18n-gate.md):
- Stdlib only. Locale JSON is read as UTF-8 (BOM tolerated); duplicate object
  keys resolve last-wins — stdlib json.loads behavior, relied upon here.
- Nested objects flatten to dot-path keys ("nav.home"). Arrays collapse into
  a single leaf value joined with " | " so array-valued keys still compare.
- Placeholders are extracted as written ({name}, {{name}}, %1$s, ...) and the
  source/target token SETS must be equal (order and multiplicity ignored).
  Placeholder spans are masked out before script/punctuation/run analysis:
  they are template syntax, substituted before display.
- Language conventions come from raast.profiles.load_profile (fa/ar/he/es).
  ProfileError (or a missing profile) falls back to built-in defaults, so the
  module also works without profile data.
- Exit codes: 0 clean; 1 when P0+P1 findings exceed --max-errors (P2 never
  gates); 2 usage error (bad directory, missing source locale, unreadable or
  invalid JSON — the offending filename is part of the error message).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

try:
    from .profiles import ProfileError, load_profile
except ImportError:  # module copied outside the package — built-in defaults only
    class ProfileError(ValueError):
        """Raised when language profile data cannot be loaded."""


    def load_profile(lang: str) -> dict:
        raise ProfileError(f"language profiles unavailable (standalone module): {lang!r}")


# ---------------------------------------------------------------- rule table

RULES: dict[str, dict[str, str]] = {
    "LQG001": {"severity": "P1", "confidence": "high", "title": "missing key"},
    "LQG002": {"severity": "P1", "confidence": "high", "title": "empty value"},
    "LQG003": {"severity": "P1", "confidence": "high", "title": "placeholder mismatch"},
    "LQG004": {"severity": "P2", "confidence": "medium", "title": "untranslated value"},
    "LQG005": {"severity": "P2", "confidence": "medium", "title": "length anomaly"},
    "LQG006": {"severity": "P2", "confidence": "medium",
               "title": "Latin punctuation / Western digits in Arabic-script prose"},
    "LQG007": {"severity": "P2", "confidence": "medium", "title": "un-isolated LTR atom in RTL value"},
    "LQG008": {"severity": "P1", "confidence": "high", "title": "Arabic Yeh/Kaf in Persian string"},
    "LQG009": {"severity": "P2", "confidence": "low", "title": "Hebrew niqqud (opt-in)"},
}

_EXPLANATIONS: dict[str, str] = {
    "LQG001": "A key present in the source locale but absent from a target renders empty text "
              "or raises at runtime, depending on the i18n library in use.",
    "LQG002": "An empty or whitespace-only value renders as blank UI copy; it usually means a "
              "translation was stubbed and never filled in.",
    "LQG003": "Formatters substitute placeholders by name or index; a set mismatch crashes "
              "str.format/printf or leaks raw braces into the UI.",
    "LQG004": "A target value identical to the source usually means the translation step was "
              "skipped and source-language copy ships to the target locale.",
    "LQG005": "A large length divergence between source and target signals truncation, padded "
              "filler text, or a missing segment; it is a heuristic, not proof.",
    "LQG006": "Persian and Arabic prose use \u060c \u061f \u061b and Arabic-Indic digits; Latin "
              "sentence punctuation and Western digits scramble bidi ordering and break reading flow.",
    "LQG007": "The Unicode bidi algorithm can reorder a bare Latin run inside RTL text; "
              "isolation marks (or markup) pin the run's visual position.",
    "LQG008": "Arabic Yeh/Kaf render with the wrong dots in Persian text and break Persian "
              "search and spellchecking; Persian uses \u06cc (U+06CC) and \u06a9 (U+06A9).",
    "LQG009": "Niqqud marks are teaching-text diacritics; production Hebrew UI copy normally "
              "ships without them.",
}

# ----------------------------------------------------------------- patterns

_BRACE_BRACE_RE = re.compile(r"\{\{\s*([A-Za-z0-9_.]+)\s*\}\}")   # {{name}} (Handlebars-style)
_BRACE_RE = re.compile(r"\{([A-Za-z0-9_]+)\}")                    # {name} / {0}
_PRINTF_RE = re.compile(r"%(?:\d+\$)?[sd]")                       # %s %d %1$s %2$d

_URL_RE = re.compile(r"https?://\S+")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+")
_NUM_COMMA_RE = re.compile(r"(?<=\d),(?=\d)")                     # 1,000 — comma inside a number
_ATOM_RE = re.compile(r"[0-9A-Za-z][0-9A-Za-z./+:@_-]*")          # code-like tokens (24/7, v2, 1.2.3)
_LATIN_RUN_RE = re.compile(r"[A-Za-z]{3,}")
_BDI_SPAN_RE = re.compile(r"<bdi>.*?</bdi>", re.IGNORECASE | re.DOTALL)
_NIQQUD_RE = re.compile(r"[\u0591-\u05C7]")

_ARABIC_YEH_KAF = ("\u064A", "\u0643")                            # Arabic YEH, Arabic KAF
_ISOLATES = frozenset({"\u2066", "\u2067", "\u2068", "\u2069", "\u200E", "\u200F"})

_ARABIC_CHAR_RE = re.compile("[\u0600-\u06ff\u0750-\u077f\ufb50-\ufdff\ufe70-\ufeff]")
_HEBREW_CHAR_RE = re.compile("[\u0590-\u05ff]")
_LATIN_CHAR_RE = re.compile(r"[A-Za-z]")

_URL_START_RE = re.compile(r"^https?://")
# Technical-looking atom: word/path/email/slug chars with NO space. Only
# skipped for LQG004 when it also carries a digit or a ./@- separator — a
# plain alphabetic word ("Language") is translatable prose, not an atom.
_TOKENISH_RE = re.compile(r"^[\w./@-]+$")
_TECH_HINT_RE = re.compile(r"[\d./@-]")

_LQG006_EXEMPT = frozenset({"he", "es"})


# ------------------------------------------------------------------- model


@dataclass
class I18nFinding:
    """One locale-quality finding (mirrors raast.rules.Finding for locale data)."""

    rule: str
    severity: str  # P0 | P1 | P2
    locale: str
    key: str
    message: str
    explanation: str
    suggested_fix: str
    confidence: str = "high"  # high | medium | low

    def as_dict(self) -> dict:
        return {
            "rule": self.rule, "severity": self.severity, "confidence": self.confidence,
            "locale": self.locale, "key": self.key, "message": self.message,
            "explanation": self.explanation, "suggested_fix": self.suggested_fix,
        }


@dataclass
class ScanResult:
    source: str
    source_keys: int
    locales: list[str]
    keys_checked: int
    findings: list[I18nFinding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        counts = {"P0": 0, "P1": 0, "P2": 0}
        for f in self.findings:
            counts[f.severity] += 1
        return counts


class _UsageError(Exception):
    """CLI usage/data error — reported as `error: ...` with exit code 2."""


def _finding(rule: str, locale: str, key: str, message: str, suggested_fix: str) -> I18nFinding:
    meta = RULES[rule]
    return I18nFinding(
        rule=rule, severity=meta["severity"], confidence=meta["confidence"],
        locale=locale, key=key, message=message,
        explanation=_EXPLANATIONS[rule], suggested_fix=suggested_fix,
    )


# ------------------------------------------------------------ flattening


def _leaf(value: object) -> str:
    """Scalar leaf: strings as-is, null as empty, everything else compact JSON."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def flatten(obj: object, prefix: str = "") -> dict[str, str]:
    """Flatten a parsed locale object to dot-path keys.

    Nested objects become "a.b.c" keys. Arrays collapse into ONE leaf value
    whose items are joined with " | " (nested structures inside arrays are
    compact-JSON encoded). Dot-colliding keys ("a.b" vs {"a": {"b": ...}})
    are inherently ambiguous; last write wins.
    """
    flat: dict[str, str] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            flat.update(flatten(v, key))
    elif isinstance(obj, list):
        flat[prefix] = " | ".join(_leaf(item) for item in obj)
    else:
        flat[prefix] = _leaf(obj)
    return flat


# ---------------------------------------------------------- discovery/load


def _load_json_object(path: Path) -> dict:
    """Parse a locale file as UTF-8 (BOM tolerated). Duplicate keys: last wins."""
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise _UsageError(f"{path}: unreadable ({exc})") from exc
    except UnicodeDecodeError as exc:
        raise _UsageError(f"{path}: not valid UTF-8 ({exc})") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _UsageError(f"{path}: invalid JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise _UsageError(f"{path}: top-level JSON must be an object")
    return data


def _load_flat(path: Path) -> dict[str, str]:
    return flatten(_load_json_object(path))


def discover_locales(root: Path) -> dict[str, dict[str, str]]:
    """Map locale code -> flattened key/value view for a locales directory.

    - *.json directly in root: locale code = file stem.
    - One level of subdirectories that contain *.json: locale code = the
      subdirectory name; all its JSON files merge in sorted-filename order
      (later files win per key). Deeper nesting is ignored.
    - If both DIR/<code>.json and DIR/<code>/*.json exist, the subdirectory
      wins on conflicting keys.
    - Hidden entries (leading ".") are skipped.
    """
    top: dict[str, dict[str, str]] = {}
    subdir: dict[str, dict[str, str]] = {}
    entries = sorted(root.iterdir(), key=lambda p: p.name)  # OSError -> caller maps to usage error
    for entry in entries:
        if entry.name.startswith("."):
            continue
        if entry.is_file() and entry.suffix.lower() == ".json":
            top.setdefault(entry.stem, {}).update(_load_flat(entry))
        elif entry.is_dir():
            inner = sorted(
                (p for p in entry.iterdir()
                 if p.is_file() and p.suffix.lower() == ".json" and not p.name.startswith(".")),
                key=lambda p: p.name,
            )
            if inner:
                merged: dict[str, str] = {}
                for p in inner:
                    merged.update(_load_flat(p))
                subdir[entry.name] = merged
    for code, merged in subdir.items():  # subdirectory wins on key conflicts
        top.setdefault(code, {}).update(merged)
    return top


# ------------------------------------------------------------- placeholders


def extract_placeholders(text: str) -> tuple[list[str], str]:
    """Return (tokens, masked_text) for every supported placeholder syntax.

    Supported: {name} and {0}; {{name}} (Handlebars-style; note that inside
    Python str.format this would be an escaped literal brace — see docs);
    printf %s / %d and positional %1$s / %2$d. Tokens are recorded as written,
    so {name} and {{name}} are distinct tokens. Masked text keeps the original
    length with placeholder spans blanked, so downstream character-level scans
    never see template syntax as prose.
    """
    tokens: list[str] = []
    spans: list[tuple[int, int]] = []

    def take(match: re.Match[str], token: str) -> None:
        start, end = match.span()
        if any(start < pe and end > ps for ps, pe in spans):
            return  # overlaps an already-consumed span (e.g. "{name}" inside "{{name}}")
        tokens.append(token)
        spans.append((start, end))

    for m in _BRACE_BRACE_RE.finditer(text):
        take(m, "{{" + m.group(1) + "}}")
    for m in _BRACE_RE.finditer(text):
        take(m, "{" + m.group(1) + "}")
    for m in _PRINTF_RE.finditer(text):
        take(m, m.group(0))

    masked = list(text)
    for start, end in spans:
        for i in range(start, end):
            masked[i] = " "
    return tokens, "".join(masked)


def _mask_spans(text: str, pattern: re.Pattern[str]) -> str:
    out = list(text)
    for m in pattern.finditer(text):
        for i in range(*m.span()):
            out[i] = " "
    return "".join(out)


# ----------------------------------------------------------- script helpers


def _script_counts(value: str) -> tuple[int, int, int]:
    return (
        len(_ARABIC_CHAR_RE.findall(value)),
        len(_HEBREW_CHAR_RE.findall(value)),
        len(_LATIN_CHAR_RE.findall(value)),
    )


def _arabic_majority(value: str) -> bool:
    arabic, hebrew, latin = _script_counts(value)
    return arabic > 0 and arabic * 2 > arabic + hebrew + latin


def _rtl_majority(value: str) -> bool:
    arabic, hebrew, latin = _script_counts(value)
    return (arabic + hebrew) > 0 and (arabic + hebrew) * 2 > arabic + hebrew + latin


def _prose_gate(locale: str, value: str) -> bool:
    """LQG006 applies to fa/ar targets and Arabic-majority values; he/es exempt."""
    if locale in _LQG006_EXEMPT:
        return False
    if locale in {"fa", "ar"}:
        return True
    try:
        if load_profile(locale).get("script") == "arabic":
            return True
    except ProfileError:
        pass
    return _arabic_majority(value)


def _script_policy(locale: str) -> dict[str, str]:
    """Punctuation/digit conventions: profile data first, built-in defaults second."""
    name: str | None = None
    display: str | None = None
    try:
        profile = load_profile(locale)
        name = profile.get("name")
        display = profile.get("numerals", {}).get("display")
    except ProfileError:
        pass
    fallback_names = {"fa": "Persian", "ar": "Arabic"}
    fallback_digits = {
        "fa": "Persian/Arabic-Indic digits (\u06f0-\u06f9)",
        "ar": "Arabic-Indic digits (\u0660-\u0669)",
    }
    return {
        "name": name or fallback_names.get(locale, "Arabic-script"),
        "digits_label": (
            f"{name} digits ({display})" if name and display
            else fallback_digits.get(locale, "Arabic-Indic digits (\u0660-\u0669)")
        ),
    }


# ------------------------------------------------------------------ checks


def _check_placeholders(source_value: str, target_value: str, locale: str, key: str) -> list[I18nFinding]:
    source_tokens, _ = extract_placeholders(source_value)
    target_tokens, _ = extract_placeholders(target_value)
    missing = sorted(set(source_tokens) - set(target_tokens))
    extra = sorted(set(target_tokens) - set(source_tokens))
    if not missing and not extra:
        return []
    parts = []
    if missing:
        parts.append(f"missing in {locale}: {', '.join(missing)}")
    if extra:
        parts.append(f"unexpected in {locale}: {', '.join(extra)}")
    return [_finding("LQG003", locale, key,
                     "placeholder mismatch — " + "; ".join(parts),
                     "Use the same placeholders as the source string.")]


def _check_untranslated(source_value: str, target_value: str, source: str,
                        locale: str, key: str) -> list[I18nFinding]:
    if target_value != source_value:
        return []
    if target_value == "" or _URL_START_RE.match(target_value):
        return []  # URLs are legitimately identical across locales
    if _TOKENISH_RE.match(target_value) and _TECH_HINT_RE.search(target_value):
        return []  # path/email/slug/version atom — not translatable prose
    latin = len(_LATIN_CHAR_RE.findall(target_value))
    if latin < 4:
        return []  # numbers, short tokens, symbols
    shown = target_value[:60] + ("…" if len(target_value) > 60 else "")
    return [_finding("LQG004", locale, key,
                     f'value is identical to the {source} source: "{shown}"',
                     "Translate the string or mark it intentionally identical.")]


def _check_length(source_value: str, target_value: str, locale: str, key: str) -> list[I18nFinding]:
    if not target_value.strip() or len(source_value) == 0:
        return []  # empties are LQG002's job; nothing to compare against
    too_long = len(target_value) > 2.5 * len(source_value)
    too_short = len(source_value) > 20 and len(target_value) < 0.4 * len(source_value)
    if not (too_long or too_short):
        return []
    if too_long:
        ratio = len(target_value) / len(source_value)
        message = f"translation length {len(target_value)} is {ratio:.1f}x the source length {len(source_value)}"
    else:
        message = (f"translation length {len(target_value)} is below 40% of the "
                   f"source length {len(source_value)}")
    return [_finding("LQG005", locale, key, message,
                     "Verify the translation is complete — length differs strongly "
                     "from the source (UI truncation risk).")]


def _check_prose(locale: str, value: str, key: str) -> list[I18nFinding]:
    """LQG006 — Latin sentence punctuation / Western digits in Arabic-script prose."""
    if not _prose_gate(locale, value):
        return []
    masked = extract_placeholders(value)[1]
    masked = _mask_spans(masked, _URL_RE)
    masked = _mask_spans(masked, _EMAIL_RE)
    masked = _mask_spans(masked, _NUM_COMMA_RE)
    punct = sorted({ch for ch in masked if ch in ",?!;"})
    digits: list[str] = []
    for m in _ATOM_RE.finditer(masked):
        run = m.group(0)
        # Bare Western numbers ("5", "2024") are flagged. Tokens that mix
        # digits with Latin letters or code-like separators ("24/7", "1.2.3",
        # "v2", "SAR99") are LTR atoms — the page-level RTL010 engine owns them.
        if run.isdigit() and run not in digits:
            digits.append(run)
    if not punct and not digits:
        return []
    policy = _script_policy(locale)
    parts = []
    if digits:
        parts.append(f"Western digit(s) {' '.join(digits)}")
    if punct:
        parts.append(f"Latin punctuation ({' '.join(punct)})")
    message = f"{' and '.join(parts)} in {policy['name']} prose"
    fix = (f"Use {policy['digits_label']} and \u060c \u061f \u061b punctuation "
           f"per profile {locale}.")
    return [_finding("LQG006", locale, key, message, fix)]


def _check_ltr_runs(locale: str, value: str, key: str) -> list[I18nFinding]:
    """LQG007 — Latin runs of 3+ chars inside RTL-majority values without isolation."""
    if not _rtl_majority(value):
        return []
    masked = extract_placeholders(value)[1]
    masked = _mask_spans(masked, _BDI_SPAN_RE)  # <bdi>...</bdi> counts as isolation
    runs: list[str] = []
    for m in _LATIN_RUN_RE.finditer(masked):
        before = masked[m.start() - 1] if m.start() > 0 else ""
        after = masked[m.end()] if m.end() < len(masked) else ""
        if before in _ISOLATES or after in _ISOLATES:
            continue  # U+2066-U+2069 isolates, or LRM/RLM marks around the run
        if m.group(0) not in runs:
            runs.append(m.group(0))
    if not runs:
        return []
    return [_finding("LQG007", locale, key,
                     f"un-isolated Latin run(s) in RTL text: {', '.join(runs)}",
                     "Add bidi isolation marks (U+2066 ... U+2069) around the Latin run "
                     "so ordering cannot scramble.")]


def _check_yeh_kaf(locale: str, value: str, key: str) -> list[I18nFinding]:
    """LQG008 — Arabic Yeh/Kaf inside Persian strings (Persian uses U+06CC/U+06A9)."""
    if locale != "fa" or not _arabic_majority(value):
        return []
    found = sorted({ch for ch in value if ch in _ARABIC_YEH_KAF})
    if not found:
        return []
    listed = " and ".join(f"{ch} (U+{ord(ch):04X})" for ch in found)
    return [_finding("LQG008", locale, key,
                     f"Arabic letter(s) {listed} in Persian text — Persian uses "
                     f"\u06cc (U+06CC) and \u06a9 (U+06A9)",
                     "Replace Arabic \u064a/\u0643 with Persian \u06cc/\u06a9.")]


def _check_niqqud(locale: str, value: str, key: str, enabled: bool) -> list[I18nFinding]:
    """LQG009 — Hebrew niqqud; only reported with --hebrew-diacritics."""
    if not enabled or locale != "he":
        return []
    if not _NIQQUD_RE.search(value):
        return []
    return [_finding("LQG009", locale, key,
                     "niqqud diacritics (U+0591-U+05C7) present in Hebrew string",
                     "Remove niqqud for production UI copy unless intentionally teaching text.")]


# -------------------------------------------------------------------- scan


def scan_locales(locales: dict[str, dict[str, str]], source: str, targets: Sequence[str],
                 hebrew_diacritics: bool = False) -> ScanResult:
    """Compare every target locale against the source, key by key.

    Iteration order is deterministic: targets in the given order, keys sorted.
    keys_checked counts every (source key, target locale) comparison.
    """
    source_map = locales[source]
    findings: list[I18nFinding] = []
    for locale in targets:
        target_map = locales[locale]
        for key in sorted(source_map):
            source_value = source_map[key]
            if key not in target_map:
                findings.append(_finding("LQG001", locale, key,
                                         f"key missing in {locale} (present in {source})",
                                         f"Add the key to {locale}."))
                continue
            target_value = target_map[key]
            if not target_value.strip():
                findings.append(_finding("LQG002", locale, key,
                                         "value is empty or whitespace-only",
                                         "Provide a non-empty translation."))
                continue
            findings += _check_placeholders(source_value, target_value, locale, key)
            findings += _check_untranslated(source_value, target_value, source, locale, key)
            findings += _check_length(source_value, target_value, locale, key)
            findings += _check_prose(locale, target_value, key)
            findings += _check_ltr_runs(locale, target_value, key)
            findings += _check_yeh_kaf(locale, target_value, key)
            findings += _check_niqqud(locale, target_value, key, hebrew_diacritics)
    return ScanResult(
        source=source,
        source_keys=len(source_map),
        locales=list(targets),
        keys_checked=len(source_map) * len(targets),
        findings=findings,
    )


# ---------------------------------------------------------------- renderers


def render_text(result: ScanResult, root: Path) -> str:
    lines = [f"raast-i18n scan — {root} "
             f"(source: {result.source}, targets: {', '.join(result.locales) or 'none'})"]
    for locale in result.locales:
        lines.append(f"== {locale} ==")
        locale_findings = [f for f in result.findings if f.locale == locale]
        if not locale_findings:
            lines.append("  no findings")
        for f in locale_findings:
            lines.append(f"{f.rule} {f.severity} [{f.locale}] {f.key} — {f.message}")
    counts = result.counts
    lines.append(
        f"{len(result.locales)} locale(s), {result.keys_checked} keys checked, "
        f"{len(result.findings)} findings (P0:{counts['P0']} P1:{counts['P1']} P2:{counts['P2']})"
    )
    return "\n".join(lines)


def render_json(result: ScanResult) -> str:
    counts = result.counts
    payload = {
        "tool": "raast-i18n",
        "source": result.source,
        "locales": result.locales,
        "keys_checked": result.keys_checked,
        "findings": [f.as_dict() for f in result.findings],
        "summary": {
            "locales": len(result.locales),
            "source_keys": result.source_keys,
            "keys_checked": result.keys_checked,
            "findings": len(result.findings),
            "by_severity": counts,
        },
        "warnings": result.warnings,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _md_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\r\n", " ").replace("\n", " ")


def render_markdown(result: ScanResult, root: Path) -> str:
    counts = result.counts
    targets = ", ".join(f"`{l}`" for l in result.locales) or "none"
    lines = [
        "# RAAST Language Quality Gate — locale scan",
        "",
        f"- Locales directory: `{root}`",
        f"- Source locale: `{result.source}` — targets: {targets}",
        f"- Keys checked: {result.keys_checked} "
        f"({result.source_keys} source keys x {len(result.locales)} target locale(s))",
        f"- Summary: **{len(result.findings)} finding(s) — "
        f"P0: {counts['P0']}, P1: {counts['P1']}, P2: {counts['P2']}**",
        "",
    ]
    for w in result.warnings:
        lines.append(f"> warning: {w}")
    if result.warnings:
        lines.append("")
    for locale in result.locales:
        lines += [f"## {locale}", ""]
        locale_findings = [f for f in result.findings if f.locale == locale]
        if not locale_findings:
            lines += ["No findings for this locale.", ""]
            continue
        lines += ["| Rule | Key | Sev | Issue | Fix |", "|---|---|---|---|---|"]
        for f in locale_findings:
            lines.append(
                f"| {f.rule} | `{_md_cell(f.key)}` | {f.severity} "
                f"| {_md_cell(f.message)} | {_md_cell(f.suggested_fix)} |"
            )
        lines.append("")
    lines += [
        "> LQG findings cover locale files; they complement the page-level host checks "
        "RTL015-017 (un-isolated RTL atoms, unmarked RTL runs, inverted marks in LTR pages), "
        "which audit rendered pages rather than translation sources.",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------- CLI


def cmd_scan(args) -> int:
    root = Path(args.locales)
    if not root.is_dir():
        raise _UsageError(f"--locales {args.locales!r} is not a directory")
    try:
        locales = discover_locales(root)
    except OSError as exc:
        raise _UsageError(f"{root}: unreadable ({exc})") from exc
    if not locales:
        raise _UsageError(f"no locale JSON files found in {root}")
    source = args.source
    if source not in locales:
        found = ", ".join(sorted(locales))
        raise _UsageError(f"source locale {source!r} not found in {root} (found: {found})")

    warnings: list[str] = []
    if args.targets:
        requested = [t.strip() for t in args.targets.split(",") if t.strip()]
        targets: list[str] = []
        for t in requested:
            if t not in locales:
                warnings.append(f"target locale {t!r} not found in {root} — skipped")
            elif t == source:
                warnings.append(f"requested target {t!r} is the source locale — skipped")
            else:
                targets.append(t)
        if not targets:
            found = ", ".join(sorted(locales))
            raise _UsageError(f"none of the requested --targets were found in {root} (found: {found})")
    else:
        targets = sorted(code for code in locales if code != source)
        if not targets:
            raise _UsageError(f"only the source locale {source!r} was found in {root} — nothing to compare")

    result = scan_locales(locales, source, targets, hebrew_diacritics=args.hebrew_diacritics)
    result.warnings = warnings
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)

    if args.format == "json":
        print(render_json(result))
    elif args.format == "markdown":
        print(render_markdown(result, root))
    else:
        print(render_text(result, root))

    gated = result.counts["P0"] + result.counts["P1"]
    return 1 if gated > args.max_errors else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="raast-i18n",
        description="RAAST Language Quality Gate — translation-quality scans for locale "
                    "files (rule namespace LQG001-009).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("scan", help="scan a locale directory against a source locale")
    sp.add_argument("--locales", required=True,
                    help="directory holding <code>.json files or <code>/*.json subdirectories")
    sp.add_argument("--source", default="en", help="source locale code (default: en)")
    sp.add_argument("--targets", default=None,
                    help="comma-separated target locale codes "
                         "(default: every discovered locale except the source)")
    sp.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    sp.add_argument("--max-errors", type=int, default=0, metavar="N",
                    help="exit 1 when P0+P1 findings exceed N (default: 0); P2 never gates")
    sp.add_argument("--hebrew-diacritics", action="store_true",
                    help="also flag niqqud in Hebrew strings (LQG009)")
    sp.set_defaults(func=cmd_scan)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except _UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
