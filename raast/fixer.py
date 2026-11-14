"""Safe auto-fix engine.

Fixes ONLY the transformations classified as safe in
skills/rtl-typography/references/normalization.md, and only for findings
flagged fixable with high confidence. Default mode is dry-run with a unified
diff; --apply writes backups to .raast-backup/ before changing anything.
"""
from __future__ import annotations

import difflib
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from .normalizer import normalize
from .rules import Finding, _tw_fix

BACKUP_DIRNAME = ".raast-backup"


@dataclass
class FixResult:
    file: str
    changed: bool
    content: str
    diff: str
    fix_count: int
    backup_path: str | None = None


def _apply_css_fixes(content: str, findings: list[Finding]) -> tuple[str, int]:
    """Line-level declarative fixes for RTL001/002/004/005 and RTL011 prose joins.

    Targets the SPECIFIC declaration per finding (lines can hold several
    declarations — e.g. `.card { margin-left: 4px; text-align: left; }`).
    """
    lines = content.splitlines(keepends=True)
    applied = 0
    for f in findings:
        if not f.fixable or f.confidence != "high":
            continue
        if not (1 <= f.line <= len(lines)):
            continue
        line = lines[f.line - 1]
        new_line = line

        if f.rule in ("RTL001", "RTL002"):
            m = re.search(r"(margin|padding)-(left|right)(\s*:\s*)([^;{}]+)", line)
            if m:
                axis, side, sep, value = m.groups()
                logical = f"{axis}-inline-{'end' if side == 'right' else 'start'}"
                new_line = line[: m.start()] + f"{logical}{sep}{value.rstrip()}" + line[m.end():]

        elif f.rule == "RTL004":
            m = re.search(r"text-align(\s*:\s*)(left|right)\b", line, re.IGNORECASE)
            if m:
                repl = "start" if m.group(2).lower() == "left" else "end"
                new_line = line[: m.start()] + f"text-align{m.group(1)}{repl}" + line[m.end():]

        elif f.rule == "RTL005":
            m = re.search(r"\s*letter-spacing\s*:\s*[^;{}]+;?", line)
            if m:
                new_line = line[: m.start()] + line[m.end():]
                if new_line.strip() == "":
                    new_line = ""

        elif f.rule == "RTL011":
            before = f.message.split("«", 1)[1].split("»", 1)[0]
            after = f.suggested_fix.split("«", 1)[1].split("»", 1)[0]
            if before in line:
                new_line = line.replace(before, after)

        if new_line != line:
            lines[f.line - 1] = new_line
            applied += 1
    return "".join(lines), applied


def _apply_tw_fixes(content: str, findings: list[Finding]) -> tuple[str, int]:
    """Tailwind class renames (RTL008) — token-boundary-safe replacements."""
    applied = 0
    result = content
    seen: set[tuple[int, str, str]] = set()
    for f in sorted(findings, key=lambda x: x.line):
        if not (f.fixable and f.confidence == "high" and f.rule == "RTL008"):
            continue
        token = f.message.split("`")[1] if "`" in f.message else None
        if not token:
            continue
        fixed = _tw_fix(token)
        if not fixed:
            continue
        line_idx = f.line - 1
        lines = result.splitlines(keepends=True)
        if not (0 <= line_idx < len(lines)):
            continue
        line = lines[line_idx]
        key = (f.line, token, fixed)
        if key in seen:
            continue
        seen.add(key)
        pattern = re.compile(r"(?<![\w-])" + re.escape(token) + r"(?![\w-])")
        new_line = pattern.sub(fixed, line, count=1)
        if new_line != line:
            lines[line_idx] = new_line
            result = "".join(lines)
            applied += 1
    return result, applied


def _apply_zwnj(content: str, lang: str, digits: bool, punct: bool) -> tuple[str, int]:
    fixed = normalize(content, lang=lang, digits=digits, punct=punct)
    changed_chars = sum(1 for a, b in zip(content.splitlines(), fixed.splitlines()) if a != b)
    return fixed, changed_chars


def fix_file(
    path: Path,
    rel: str,
    findings: list[Finding],
    zwnj: bool = False,
    lang: str = "fa",
    zwnj_digits: bool = False,
    zwnj_punct: bool = False,
) -> FixResult:
    content = path.read_text(encoding="utf-8")
    original = content
    total = 0

    content, n = _apply_css_fixes(content, findings)
    total += n
    content, n = _apply_tw_fixes(content, findings)
    total += n
    if zwnj:
        content, n = _apply_zwnj(content, lang, zwnj_digits, zwnj_punct)
        total += n

    diff = ""
    if content != original:
        diff = "\n".join(
            difflib.unified_diff(
                original.splitlines(), content.splitlines(),
                fromfile=f"{rel} (before)", tofile=f"{rel} (after)", lineterm="",
            )
        )
    return FixResult(file=rel, changed=content != original, content=content,
                     diff=diff, fix_count=total)


def apply_fix(path: Path, rel: str, result: FixResult, root: Path | None = None) -> str:
    """Write the fixed content with a backup. Returns backup path."""
    backup_root = (root or path.parent) / BACKUP_DIRNAME
    backup_file = backup_root / rel
    backup_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_file)
    path.write_text(result.content, encoding="utf-8")
    return str(backup_file)
