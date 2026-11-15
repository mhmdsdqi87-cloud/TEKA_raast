"""Diff scoping — map a unified diff to changed line ranges per file.

Policy: "only new issues".

RAAST's PR reviewer deliberately reports only findings that land on lines
this pull request actually changed. Pre-existing problems on untouched
lines are NOT reported. This keeps the review comment small (a 3-file PR
in a 50k-line legacy repo does not turn into a wall of old debt), avoids
shaming code the author never touched, and makes RAAST adoptable in
existing codebases where a repo-wide gate would fail on day one. Teams
that want full-repo coverage run `raast scan` separately; the PR gate
stays scoped to the diff.

Parsing targets `git diff -U0` output (zero context), but ordinary
`diff -u` output and diffs with context lines are handled as well.

Handled edge cases:
- only the b/ (new-file) side of `+++ b/path` is used; `--- a/path` is ignored
- `+++ /dev/null` (deleted file) produces no ranges
- hunk headers `@@ -a,b +c,d @@` with counts omitted (`@@ -3 +3 @@`) —
  a missing count means 1; a count of 0 means an empty range (skipped)
- binary files (`Binary files a/x and b/x differ`, `GIT binary patch`)
- renames and copies (ranges attach to the NEW path from `+++ b/new`)
- `\\ No newline at end of file` markers inside hunk bodies
- hunk body lines that themselves look like metadata (e.g. a removed line
  containing `++ foo` renders as `+++ foo`) — bodies are consumed using the
  counts from the hunk header before metadata parsing resumes
"""
from __future__ import annotations

import re

from .rules import Finding

# @@ -old_start[,old_count] +new_start[,new_count] @@ (optional trailing section text)
_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _unquote(path: str) -> str:
    """Strip surrounding quotes git uses for paths with special characters."""
    if len(path) >= 2 and path[0] == '"' and path[-1] == '"':
        body = path[1:-1]
        body = body.replace('\\"', '"').replace("\\\\", "\\")
        body = body.replace("\\t", "\t").replace("\\n", "\n")
        return body
    return path


def parse_unified_diff(diff_text: str) -> dict[str, list[tuple[int, int]]]:
    """Parse a unified diff and return changed line ranges in the NEW file.

    Returns a dict mapping repo-relative file paths to a list of inclusive
    (start, end) line ranges covering every added or modified line. Ranges
    come from the hunk headers: the new-file side spans
    new_start .. new_start + new_count - 1. Deleted files (b/ == /dev/null)
    and binary files produce no entry.
    """
    ranges: dict[str, list[tuple[int, int]]] = {}
    current: str | None = None
    # Lines left to consume in the current hunk body, per side.
    old_remaining = 0
    new_remaining = 0

    for raw_line in diff_text.splitlines():
        line = raw_line.rstrip("\r")

        # Inside a hunk body: consume exactly old_count + new_count body
        # lines (and any "\ No newline..." markers) before trusting
        # anything that looks like metadata again.
        if old_remaining or new_remaining:
            if line.startswith("\\"):  # "\ No newline at end of file"
                continue
            if line.startswith("+") and new_remaining > 0:
                new_remaining -= 1
                continue
            if line.startswith("-") and old_remaining > 0:
                old_remaining -= 1
                continue
            if line.startswith(" ") or line == "":
                old_remaining = max(0, old_remaining - 1)
                new_remaining = max(0, new_remaining - 1)
                continue
            # Malformed hunk: resynchronize and re-parse this line as
            # metadata (falls through to the header handling below).
            old_remaining = 0
            new_remaining = 0

        if line.startswith("diff --git "):
            current = None
            continue
        if line.startswith("Binary files ") or line.startswith("GIT binary patch"):
            current = None
            continue
        if line.startswith("+++ "):
            # "+++ b/path" (git) or "+++ path\t<timestamp>" (GNU diff -u)
            raw = line[4:].split("\t")[0].strip()
            raw = _unquote(raw)
            if raw == "/dev/null":
                current = None  # deleted file: nothing to report
            else:
                current = raw[2:] if raw.startswith("b/") else raw
                ranges.setdefault(current, [])
            continue

        m = _HUNK_RE.match(line)
        if m and current is not None:
            old_count = int(m.group(2)) if m.group(2) is not None else 1
            new_start = int(m.group(3))
            new_count = int(m.group(4)) if m.group(4) is not None else 1
            if new_count > 0:
                ranges[current].append((new_start, new_start + new_count - 1))
            old_remaining = old_count
            new_remaining = new_count

    return {path: rs for path, rs in ranges.items() if rs}


def file_changed_ranges(diff_text: str) -> dict[str, list[tuple[int, int]]]:
    """Thin wrapper around parse_unified_diff (kept for call-site clarity)."""
    return parse_unified_diff(diff_text)


def _normalize(path: str) -> str:
    """Posix-normalize a relative path for comparison."""
    p = path.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p.strip("/")


def _ends_with_component(long_path: str, short_path: str) -> bool:
    """True if long_path ends with short_path at a path-component boundary."""
    return long_path == short_path or long_path.endswith("/" + short_path)


def finding_in_ranges(finding_file: str, finding_line: int,
                      ranges: dict[str, list[tuple[int, int]]]) -> bool:
    """True if the finding's line falls inside a changed range of its file.

    Matching is by exact relative path first. Tolerant fallback: git diff
    paths are repository-relative while findings carry scanner-relative
    paths, so a match is also accepted when either path ends with the other
    at a component boundary (``src/card.css`` matches ``card.css``).
    """
    if finding_line is None or finding_line <= 0:
        return False
    key = _normalize(finding_file)
    file_ranges = ranges.get(key)
    if file_ranges is None:
        for path, rs in ranges.items():
            if _ends_with_component(key, path) or _ends_with_component(path, key):
                file_ranges = rs
                break
    if not file_ranges:
        return False
    return any(start <= finding_line <= end for start, end in file_ranges)


def filter_findings(findings: list[Finding],
                    ranges: dict[str, list[tuple[int, int]]]) -> list[Finding]:
    """Keep only findings whose file+line land inside the changed ranges."""
    return [f for f in findings if finding_in_ranges(f.file, f.line, ranges)]
