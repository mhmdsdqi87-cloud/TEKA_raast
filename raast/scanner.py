"""File discovery honoring include/exclude glob patterns."""
from __future__ import annotations

import fnmatch
import re
from pathlib import Path

TEXT_SUFFIXES = {
    ".html", ".css", ".scss", ".sass", ".vue", ".jsx", ".tsx", ".js", ".ts",
    ".mjs", ".astro", ".md", ".mdx", ".txt", ".json", ".yml", ".yaml",
}
MAX_BYTES = 1_500_000


def glob_to_regex(pattern: str) -> re.Pattern:
    """Translate a glob (supports ** ) to a regex over posix-style relative paths."""
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
            alts = pattern[i + 1 : j].split(",")
            out += "(?:" + "|".join(re.escape(a) for a in alts) + ")"
            i = j + 1
        elif c in "[]":
            j = pattern.find("]" if c == "[" else "[", i)
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
