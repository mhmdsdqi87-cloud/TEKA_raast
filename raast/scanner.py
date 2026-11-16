"""File discovery honoring include/exclude glob patterns."""
from __future__ import annotations

import fnmatch
import re
from pathlib import Path

TEXT_SUFFIXES = {
    ".html", ".css", ".scss", ".sass", ".vue", ".jsx", ".tsx", ".js", ".ts",
    ".mjs", ".astro", ".svelte", ".md", ".mdx", ".txt", ".json", ".yml", ".yaml",
}
MAX_BYTES = 1_500_000


def glob_to_regex(pattern: str) -> re.Pattern:
    """Translate a glob (supports ** ) to a regex over posix-style relative paths.

    Robust against malformed patterns: an unclosed ``{`` or ``[`` is treated
    as a literal character instead of hanging the translator in an infinite
    loop (a corrupted include/exclude pattern must never freeze the CLI).
    """
    i = 0
    out = ""
    pattern = pattern.replace("\\", "/")
    while i < len(pattern):
        c = pattern[i]
        if c == "*":
            if pattern[i : i + 3] == "**/":
                out += "(?:[^/]+/)*"
                i += 3
                continue
            if pattern[i : i + 2] == "**":
                out += ".*"
                i += 2
                continue
            out += "[^/]*"
            i += 1
        elif c == "?":
            out += "[^/]"
            i += 1
        elif c == "{":
            j = pattern.find("}", i)
            if j == -1:  # unclosed brace: literal character, keep scanning
                out += re.escape(c)
                i += 1
                continue
            alts = pattern[i + 1 : j].split(",")
            out += "(?:" + "|".join(re.escape(a) for a in alts) + ")"
            i = j + 1
        elif c in "[]":
            j = pattern.find("]" if c == "[" else "[", i)
            if j == -1:  # unclosed class: literal character, keep scanning
                out += re.escape(c)
                i += 1
                continue
            out += pattern[i : j + 1]
            i = j + 1
        else:
            out += re.escape(c)
            i += 1
    return re.compile("^" + out + "$")


def is_text_file(path: Path) -> bool:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return False
    try:
        if path.stat().st_size > MAX_BYTES:
            return False
        raw = path.read_bytes()
        if b"\x00" in raw:
            return False
        raw.decode("utf-8")
        return True
    except (OSError, UnicodeDecodeError):
        return False


def read_text_checked(path: Path) -> tuple[bool, str | None]:
    """Validate + decode in ONE read (is_text_file reads, then cli re-reads —
    halving file I/O matters on large repositories).

    Returns (True, text) when the file is a scannable UTF-8 text file,
    (False, None) otherwise (wrong suffix, too large, binary, bad encoding).
    """
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return False, None
    try:
        if path.stat().st_size > MAX_BYTES:
            return False, None
        raw = path.read_bytes()
        if b"\x00" in raw:
            return False, None
        return True, raw.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return False, None


def iter_files(root: Path, include: list[str], exclude: list[str]):
    inc_res = [glob_to_regex(p) for p in (include or ["**/*"])]
    exc_res = [glob_to_regex(p) for p in (exclude or [])]
    for path in sorted(root.rglob("*")):
        if not path.is_file() or not is_text_file(path):
            continue
        rel = path.relative_to(root).as_posix()
        if any(r.match(rel) for r in exc_res):
            continue
        if not any(r.match(rel) for r in inc_res):
            continue
        yield path, rel


def iter_files_with_content(root: Path, include: list[str], exclude: list[str]):
    """Yield (path, rel, content) — single-read variant used by the CLI scan
    loop. Files rejected by read_text_checked are skipped exactly like
    iter_files."""
    inc_res = [glob_to_regex(p) for p in (include or ["**/*"])]
    exc_res = [glob_to_regex(p) for p in (exclude or [])]
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if any(r.match(rel) for r in exc_res):
            continue
        if not any(r.match(rel) for r in inc_res):
            continue
        ok, content = read_text_checked(path)
        if not ok:
            continue
        yield path, rel, content
