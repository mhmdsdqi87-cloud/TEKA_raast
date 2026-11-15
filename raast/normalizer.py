"""Safe Persian/Arabic text normalization engine.

Implements the decision table in skills/rtl-typography/references/normalization.md:
only "Always safe" transformations are applied by default; language-gated
transforms require an explicit language profile; "Never automatic" cases are
reported but never rewritten.

Protected regions: fenced code blocks, inline code, URLs, emails, and
<!-- keep --> ... <!-- /keep --> spans.
"""
from __future__ import annotations

import re

ZWNJ = "\u200c"

# ---------------------------------------------------------------- wordlists
# Conservative verb stems for the prefix-join rule. Extend via profile
# `extra_verb_stems` when a language requires it.
DEFAULT_VERB_STEMS = [
    "شود", "شده", "شوند", "باشد", "باشند", "بود", "هست", "هستند",
    "رود", "رفت", "رفته", "روند", "رویم", "روم", "برود",
    "آید", "آمد", "آمده", "آیند",
    "دهد", "داد", "داده", "دهند", "دهم", "دهید",
    "برد", "برند", "ببر", "بریم",
    "گیرد", "گرفت", "گرفته", "گیرند", "گیریم",
    "کند", "کرد", "کرده", "کنند", "کنیم", "کن", "کنید",
    "خواهد", "خواهم", "خواهیم", "خواهند", "خواست",
    "تواند", "توانست", "توانم", "می‌تواند",
    "آورد", "آورده", "آورند",
    "گفت", "گوید", "گفته", "گویند",
    "بیند", "دید", "دیده",
    "یابد", "یافت", "یافته",
    "رسد", "رسید", "رسیده",
    "داند", "دانست", "دانند",
    "پردازد", "پرداخت", "پرداخته",
    "سازد", "ساخت", "ساخته", "سازند",
    "نویسد", "نوشت", "نوشته",
    "خواند", "خوانده",
    "دارد", "داشت", "دارند", "دانم", "دانی", "دانید",
    "افزاید", "افزود", "افزوده",
    "بماند", "ماند", "مانده",
    "گردد", "گردید", "گردیده",
    "می‌شود", "می‌کند", "می‌دهد",
]

AR_YEH_KAF = str.maketrans({"ي": "ی", "ك": "ک", "ھ": "ه"})
AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "۰۱۲۳۴۵۶۷۸۹")

ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")
HEBREW_RE = re.compile(r"[\u0590-\u05FF]")
# Evidence of RTL-script text in a file — Arabic OR Hebrew. Gates the CSS /
# Tailwind / HTML rules so mixed projects never false-positive on pure LTR files.
RTL_SCRIPT_RE = re.compile(r"[\u0590-\u05FF\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")
CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`]*`")
URL_EMAIL_RE = re.compile(r"(https?://\S+|[\w.+-]+@[\w-]+\.[\w.]+)")
KEEP_RE = re.compile(r"<!--\s*keep\s*-->.*?<!--\s*/keep\s*-->", re.DOTALL)

PUNCT_SUBS = [
    (re.compile(r"(?<=[\u0600-\u06FF])\s*,\s*(?=[\u0600-\u06FF\s])"), "، "),
    (re.compile(r"(?<=[\u0600-\u06FF])\s*\?(?=\s|$)"), "؟"),
    (re.compile(r"(?<=[\u0600-\u06FF])\s*;(?=\s|$)"), "؛"),
]


def _build_prefix_re(stems: list[str]) -> re.Pattern:
    return re.compile(r"(?<![\u0600-\u06FF])(می|نمی|بی|هم|باز|نا|فرا)\s+(" + "|".join(stems) + r")(?![\u0600-\u06FF])")


def _mask(text: str) -> tuple[str, list[str]]:
    saved: list[str] = []

    def stash(m: re.Match) -> str:
        saved.append(m.group(0))
        return f"\x00{len(saved) - 1}\x00"

    masked = KEEP_RE.sub(stash, text)
    masked = CODE_FENCE_RE.sub(stash, masked)
    masked = INLINE_CODE_RE.sub(stash, masked)
    masked = URL_EMAIL_RE.sub(stash, masked)
    return masked, saved


def _unmask(text: str, saved: list[str]) -> str:
    for i, chunk in enumerate(saved):
        text = text.replace(f"\x00{i}\x00", chunk)
    return text


def detect_broken_zwnj(text: str) -> list[tuple[int, str, str]]:
    """Return [(line_no, before, after)] for broken ZWNJ patterns (report-only view)."""
    masked, _ = _mask(text)
    prefix_re = _build_prefix_re(DEFAULT_VERB_STEMS)
    findings = []
    for lineno, line in enumerate(masked.splitlines(), 1):
        for m in prefix_re.finditer(line):
            findings.append((lineno, m.group(0), m.group(1) + ZWNJ + m.group(2)))
        for m in re.finditer(r"([\u0600-\u06FF]{2,})[ ]+(ها|های)(?=[\s،؛؟!.]|$)", line):
            findings.append((lineno, m.group(0), m.group(1) + ZWNJ + m.group(2)))
        for m in re.finditer(r"([\u0600-\u06FF]{2,})[ ]+(تر|ترین)(?=[\s،؛؟!.]|$)", line):
            findings.append((lineno, m.group(0), m.group(1) + ZWNJ + m.group(2)))
    return findings


def normalize(
    text: str,
    lang: str = "fa",
    digits: bool = False,
    punct: bool = False,
    extra_stems: list[str] | None = None,
) -> str:
    """Normalize *text*. digits/punct are language-gated opt-ins (see decision table)."""
    if lang == "ar":
        # Language-gated: Arabic-Indic digits are CORRECT in Arabic content.
        digits = False
    stems = DEFAULT_VERB_STEMS + list(extra_stems or [])
    prefix_re = _build_prefix_re(stems)

    masked, saved = _mask(text)
    masked = prefix_re.sub(lambda m: m.group(1) + ZWNJ + m.group(2), masked)
    masked = re.sub(
        r"([\u0600-\u06FF]{2,})[ ]+(ها|های)(?=[\s،؛؟!.]|$)",
        lambda m: m.group(1) + ZWNJ + m.group(2),
        masked,
    )
    masked = re.sub(
        r"([\u0600-\u06FF]{2,})[ ]+(تر|ترین)(?=[\s،؛؟!.]|$)",
        lambda m: m.group(1) + ZWNJ + m.group(2),
        masked,
    )
    masked = masked.translate(AR_YEH_KAF)

    if digits and lang == "fa":
        def fix_line(line: str) -> str:
            if ARABIC_RE.search(line):
                return line.translate(AR_DIGITS)
            return line

        masked = "\n".join(fix_line(line) for line in masked.split("\n"))

    if punct:
        for rx, repl in PUNCT_SUBS:
            masked = rx.sub(repl, masked)

    return _unmask(masked, saved)
