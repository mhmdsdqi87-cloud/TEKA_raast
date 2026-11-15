"""Safe auto-fix engine.

Fixes ONLY the transformations classified as safe in
skills/rtl-typography/references/normalization.md, and only for findings
flagged fixable with high confidence. Default mode is dry-run with a unified
diff; --apply writes backups to .raast-backup/ before changing anything.

Auto-Fix 2.0 adds a three-tier classification (safe / suggested / manual),
an append-only fix journal (.raast-backup/journal.json) and `revert_all`,
which restores exactly the files recorded in that journal.
"""
from __future__ import annotations

import difflib
import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .normalizer import ARABIC_RE, _mask, _unmask, normalize
from .rules import Finding, _tw_fix

BACKUP_DIRNAME = ".raast-backup"
JOURNAL_FILENAME = "journal.json"

# Three-tier fix classification. Every rule id maps to exactly one tier:
#   safe     — mechanical, reversible rewrites (applied by `raast fix`)
#   suggested — correct but opinionated; applied only under `--tier all`
#              AND their existing opt-in flags (--zwnj-digits / --zwnj-punct)
#   manual   — never auto-applied; reported for human review only
FIX_TIERS: dict[str, str] = {
    "RTL001": "safe",      # margin-left/right -> margin-inline-start/end
    "RTL002": "safe",      # padding-left/right -> padding-inline-start/end
    "RTL004": "safe",      # text-align left/right -> start/end
    "RTL005": "safe",      # remove letter-spacing on Arabic script
    "RTL008": "safe",      # Tailwind ml/mr/pl/pr/text-left -> logical utilities
    "RTL011": "safe",      # broken ZWNJ compound joins (--zwnj)
    "RTL009": "suggested",  # Latin punctuation -> Arabic marks (--zwnj-punct)
    "RTL010": "suggested",  # Western digits -> Persian digits (--zwnj-digits)
    "RTL003": "manual",    # physical left:/right: positioning — semantics vary
    "RTL006": "manual",    # missing dir on <html> — template-owned
    "RTL007": "manual",    # Tailwind translate-x — animation intent unknown
    "RTL012": "manual",    # un-isolated LTR atom — markup choice (bdi vs span)
    "RTL013": "manual",    # dir="ltr" on RTL content — may be deliberate
    "RTL014": "manual",    # missing lang — i18n decision
    "RTL015": "manual",    # un-isolated RTL atom in LTR host — markup choice
    "RTL016": "manual",    # RTL element without dir in LTR doc — markup choice
    "RTL017": "manual",    # missing inverted marks — copy-editing decision
}


def tier_for(rule: str) -> str:
    """Return the fix tier for a rule id; unknown ids fall back to "manual"."""
    return FIX_TIERS.get(rule, "manual")


@dataclass
class FixResult:
    file: str
    changed: bool
    content: str
    diff: str
    fix_count: int
    backup_path: str | None = None
    rules_applied: list[str] = field(default_factory=list)
    tiers: dict[str, int] = field(default_factory=dict)


def _apply_css_fixes(content: str, findings: list[Finding]) -> tuple[str, int, list[str]]:
    """Line-level declarative fixes for RTL001/002/004/005 and RTL011 prose joins.

    Targets the SPECIFIC declaration per finding (lines can hold several
    declarations — e.g. `.card { margin-left: 4px; text-align: left; }`).
    Returns (content, applied_count, applied_rule_ids).
    """
    lines = content.splitlines(keepends=True)
    applied = 0
    applied_rules: list[str] = []
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
            applied_rules.append(f.rule)
    return "".join(lines), applied, applied_rules


def _apply_tw_fixes(content: str, findings: list[Finding]) -> tuple[str, int, list[str]]:
    """Tailwind class renames (RTL008) — token-boundary-safe replacements.

    Returns (content, applied_count, applied_rule_ids).
    """
    applied = 0
    applied_rules: list[str] = []
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
            applied_rules.append(f.rule)
    return result, applied, applied_rules


def _apply_zwnj(content: str, lang: str, digits: bool, punct: bool) -> tuple[str, int]:
    fixed = normalize(content, lang=lang, digits=digits, punct=punct)
    changed_chars = sum(1 for a, b in zip(content.splitlines(), fixed.splitlines()) if a != b)
    return fixed, changed_chars


# RTL010 suggested transform: Western digits -> Persian digits (fa profile).
# Arabic-Indic digits are unified to the Persian set in the same pass.
_DIGIT_TABLE = str.maketrans({
    **{ord(w): f for w, f in zip("0123456789", "۰۱۲۳۴۵۶۷۸۹")},
    **{ord(a): p for a, p in zip("٠١٢٣٤٥٦٧٨٩", "۰۱۲۳۴۵۶۷۸۹")},
})
# LTR digit atoms whose digits must survive: phone numbers and $ amounts
# (URLs and emails are masked by the normalizer's _mask; tags are skipped per line).
_ATOM_NUM_RE = re.compile(r"(?<![\w>])(\+\d[\d\s-]{6,}\d|\$\d+(?:\.\d+)?)")
_TAG_RE = re.compile(r"<[^>\n]*>")


def _apply_fa_digits(content: str) -> tuple[str, int]:
    """RTL010 suggested transform (fa): Western digits -> Persian digits on
    Arabic-script lines. Arabic-Indic digits are unified to the Persian set.

    Digits inside protected regions survive: URLs, emails, inline code,
    keep-spans (via the normalizer's masking), HTML tags/attributes, and LTR
    digit atoms (phone numbers, $ amounts) — the same atom model the RTL010
    rule uses when it suppresses findings.
    """
    masked, saved = _mask(content)
    out_lines = []
    changed = 0
    for line in masked.split("\n"):
        new_line = line
        if ARABIC_RE.search(line) and re.search(r"[0-9٠-٩]", line):
            protected = (
                [(m.start(), m.end()) for m in _TAG_RE.finditer(line)]
                + [(m.start(), m.end()) for m in _ATOM_NUM_RE.finditer(line)]
            )
            if not protected:
                new_line = line.translate(_DIGIT_TABLE)
            else:
                protected.sort()
                pieces: list[str] = []
                pos = 0
                for s, e in protected:
                    if s < pos:
                        continue  # overlapping protection — leave as-is
                    pieces.append(line[pos:s].translate(_DIGIT_TABLE))
                    pieces.append(line[s:e])
                    pos = e
                pieces.append(line[pos:].translate(_DIGIT_TABLE))
                new_line = "".join(pieces)
        if new_line != line:
            changed += 1
        out_lines.append(new_line)
    return _unmask("\n".join(out_lines), saved), changed


def fix_file(
    path: Path,
    rel: str,
    findings: list[Finding],
    zwnj: bool = False,
    lang: str = "fa",
    zwnj_digits: bool = False,
    zwnj_punct: bool = False,
    tier: str = "safe",
) -> FixResult:
    """Build a fix for one file under the requested tier policy.

    Tier policy:
      "safe" — only safe-tier fixes apply (mechanical, reversible rewrites).
      "all"  — safe-tier fixes PLUS suggested-tier transforms, which stay
               gated by their opt-in flags (zwnj_digits / zwnj_punct).
    Manual-tier findings are NEVER applied here; they remain findings for
    the caller to surface as manual review items.
    """
    content = path.read_text(encoding="utf-8")
    original = content
    total = 0
    tiers: dict[str, int] = {}
    rules_hit: set[str] = set()

    def _count_tier(rule: str) -> None:
        t = tier_for(rule)
        tiers[t] = tiers.get(t, 0) + 1
        rules_hit.add(rule)

    content, n, hit = _apply_css_fixes(content, findings)
    total += n
    for rule in hit:
        _count_tier(rule)
    content, n, hit = _apply_tw_fixes(content, findings)
    total += n
    for rule in hit:
        _count_tier(rule)

    if zwnj:
        # Stage 1 — safe-tier text normalization only: ZWNJ compound joins and
        # Arabic yeh/kaf unification (RTL011 territory). Digits and punctuation
        # are suggested-tier and deferred to stage 2 under the "all" policy.
        content, n = _apply_zwnj(content, lang, digits=False, punct=False)
        total += n
        if n:
            if "RTL011" not in rules_hit:
                _count_tier("RTL011")

        # Stage 2 — suggested tier: only under the "all" policy, and still
        # behind their existing opt-in flags.
        if tier == "all" and (zwnj_digits or zwnj_punct):
            if zwnj_digits:
                # RTL010 territory: Western digits -> Persian digits on
                # Arabic-script lines (fa profile only — Arabic-Indic digits
                # are already correct in ar, and he/es use Western digits).
                if lang == "fa":
                    content, n2 = _apply_fa_digits(content)
                    if n2:
                        total += n2
                        tiers["suggested"] = tiers.get("suggested", 0) + n2
                        rules_hit.add("RTL010")
            if zwnj_punct:
                # RTL009 territory: Latin punctuation -> Arabic marks after
                # Arabic characters (PUNCT_SUBS no-op elsewhere).
                stage2 = normalize(content, lang=lang, digits=False, punct=True)
                n3 = sum(1 for a, b in zip(content.splitlines(), stage2.splitlines()) if a != b)
                if n3:
                    content = stage2
                    total += n3
                    tiers["suggested"] = tiers.get("suggested", 0) + n3
                    rules_hit.add("RTL009")

    diff = ""
    if content != original:
        diff = "\n".join(
            difflib.unified_diff(
                original.splitlines(), content.splitlines(),
                fromfile=f"{rel} (before)", tofile=f"{rel} (after)", lineterm="",
            )
        )
    return FixResult(file=rel, changed=content != original, content=content,
                     diff=diff, fix_count=total,
                     rules_applied=sorted(rules_hit), tiers=tiers)


def apply_fix(path: Path, rel: str, result: FixResult, root: Path | None = None) -> str:
    """Write the fixed content with a backup, then record the change in the
    fix journal (.raast-backup/journal.json). Returns backup path."""
    backup_root = (root or path.parent) / BACKUP_DIRNAME
    backup_file = backup_root / rel
    backup_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_file)
    path.write_text(result.content, encoding="utf-8")
    journal_append(root or path.parent, {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "file": rel,
        "backup": str(backup_file.relative_to(backup_root)),
        "rules": list(result.rules_applied),
        "fix_count": result.fix_count,
    })
    return str(backup_file)


# ---------------------------------------------------------------- journal


def _journal_path(root: Path) -> Path:
    return Path(root) / BACKUP_DIRNAME / JOURNAL_FILENAME


def journal_load(root: Path) -> list[dict]:
    """Load the fix journal for *root*. Tolerant: missing or corrupt journal
    returns [] — an unreadable journal must never crash a fix or revert run."""
    try:
        data = json.loads(_journal_path(root).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [entry for entry in data if isinstance(entry, dict)]


def journal_append(root: Path, entry: dict) -> None:
    """Append one entry to the fix journal, creating it if needed."""
    entries = journal_load(root)
    entries.append(entry)
    jp = _journal_path(root)
    jp.parent.mkdir(parents=True, exist_ok=True)
    jp.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def revert_all(root: Path, backup_dirname: str = BACKUP_DIRNAME) -> tuple[int, list[str]]:
    """Restore every backup recorded in the journal for *root*.

    Safety policy: the journal is the ONLY source of truth for the mapping
    between a backup copy and the file it replaced. Without a usable journal,
    nothing is restored (returns (0, [])). Restoration writes only to paths
    inside *root* and reads/deletes only inside root/<backup_dirname>.
    Restored backups are removed and the journal is cleared.

    Returns (restored_count, restored_repo-relative_paths).
    """
    root = Path(root)
    root_resolved = root.resolve()
    backup_root = root / backup_dirname
    journal = journal_load(root)
    if not journal:
        return 0, []

    restored: list[str] = []
    for entry in journal:
        rel = entry.get("file")
        bak = entry.get("backup")
        if not isinstance(rel, str) or not isinstance(bak, str) or not rel or not bak:
            continue
        rel_path = Path(rel)
        if rel_path.is_absolute() or ".." in rel_path.parts:
            continue
        target = root / rel_path
        try:
            target.resolve().relative_to(root_resolved)
        except (ValueError, OSError):
            continue  # would escape the root — refuse
        src = backup_root / bak
        try:
            src.resolve().relative_to((backup_root).resolve())
        except (ValueError, OSError):
            continue
        if not src.is_file():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        src.unlink()
        parent = src.parent
        while parent != backup_root and parent.is_dir():
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
        restored.append(rel)

    if backup_root.is_dir():
        (backup_root / JOURNAL_FILENAME).write_text("[]\n", encoding="utf-8")
    return len(restored), restored

