"""Font glyph-coverage audit for RTL scripts.

Mechanical pre-check: does each font file shipped in a project actually
contain the glyphs a language profile needs? This catches the classic
broken-RTL launch — a Latin-only display font applied to Persian headings,
or a fallback stack that silently drops Persian digits — before it reaches
a browser.

What is checked (deterministic, from the font's cmap table):
  - letter coverage for the profile's script (incl. Persian پ چ ژ گ ی ک)
  - digit coverage (Persian ۰-۹ / Arabic-Indic ٠-٩ per profile)
  - punctuation (، ؛ ؟ « » …)
  - format controls (ZWNJ for fa — missing ZWNJ glyphs break compound words)

What is deliberately NOT checked (and must stay honest in the docs):
  - aesthetic quality of the glyphs (kerning, joining context, baseline
    rhythm) — that needs a native human eye, see docs/review-program.md
  - hinting/rendering differences across browsers

Formats: TTF/OTF are parsed with a built-in sfnt/cmap reader (formats 0, 4
and 12 — the ones found in real web fonts). WOFF v1 is unpacked with zlib
and parsed the same way. WOFF2 needs brotli; it is checked with fontTools
when that package is installed and reported as "unsupported" otherwise —
never silently ignored.

CLI: `raast fonts <path> --language fa [--format json]`
Exit codes: 0 = every scanned font covers the required glyphs,
1 = at least one glyph gap, 2 = usage error.
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path

FONT_SUFFIXES = {".ttf", ".otf", ".woff", ".woff2"}


# ----------------------------------------------------------- requirements

def _cp_range(first: int, last: int) -> set[int]:
    return set(range(first, last + 1))


_ARABIC_BASE = _cp_range(0x0621, 0x064A)  # hamza .. yeh barree base
_FA_EXTRA = {0x0622, 0x067E, 0x0686, 0x0698, 0x06AF, 0x06A9, 0x06CC, 0x0629}
_COMMON_PUNCT = {0x060C, 0x061B, 0x061F, 0x00AB, 0x00BB, 0x2026}  # ، ؛ ؟ « » …

# Grouped requirements per profile code. "letters"/"digits"/"punctuation"
# gaps fail the audit; "optional" groups are reported but never gate.
REQUIRED_CODEPOINTS: dict[str, dict[str, set[int]]] = {
    "fa": {
        "letters": _ARABIC_BASE | _FA_EXTRA,
        "digits": _cp_range(0x06F0, 0x06F9),  # ۰-۹
        "punctuation": _COMMON_PUNCT,
        "format_controls": {0x200C},  # ZWNJ
    },
    "ar": {
        "letters": _ARABIC_BASE,
        "digits": _cp_range(0x0660, 0x0669),  # ٠-٩
        "punctuation": _COMMON_PUNCT,
    },
    "he": {
        "letters": _cp_range(0x05D0, 0x05EA),
        "punctuation": {0x05BE, 0x05F3, 0x05F4, 0x00AB, 0x00BB},  # maqaf geresh gershayim « »
        "optional": {
            "niqqud": _cp_range(0x05B0, 0x05C7),
        },
    },
    "es": {
        "letters": _cp_range(0x0041, 0x005A) | _cp_range(0x0061, 0x007A)
        | {0x00C1, 0x00C9, 0x00CD, 0x00D3, 0x00DA, 0x00D1, 0x00DC,
           0x00E1, 0x00E9, 0x00ED, 0x00F3, 0x00FA, 0x00F1, 0x00FC},
        "digits": _cp_range(0x0030, 0x0039),
        "punctuation": {0x00BF, 0x00A1, 0x00AB, 0x00BB, 0x2026},  # ¿ ¡ « » …
    },
}


def _char_label(cps: set[int], limit: int = 12) -> str:
    chars = sorted(cps)[:limit]
    out = " ".join(f"U+{c:04X}({chr(c)})" for c in chars)
    if len(cps) > limit:
        out += f" … (+{len(cps) - limit} more)"
    return out


# ----------------------------------------------------------- cmap parsing

@dataclass
class CmapResult:
    covered: set[int] = field(default_factory=set)
    formats_seen: list[int] = field(default_factory=list)


def _parse_format0(data: bytes, offset: int, res: CmapResult) -> None:
    table = data[offset + 6: offset + 6 + 256]
    for code, glyph in enumerate(table):
        if glyph:
            res.covered.add(code)


def _parse_format4(data: bytes, offset: int, res: CmapResult) -> None:
    seg_count_x2 = struct.unpack_from(">H", data, offset + 6)[0]
    seg_count = seg_count_x2 // 2
    end_base = offset + 14
    start_base = end_base + seg_count_x2 + 2  # + reservedPad
    delta_base = start_base + seg_count_x2
    range_base = delta_base + seg_count_x2
    for seg in range(seg_count):
        end_code = struct.unpack_from(">H", data, end_base + seg * 2)[0]
        start_code = struct.unpack_from(">H", data, start_base + seg * 2)[0]
        if start_code == 0xFFFF:
            continue
        id_delta = struct.unpack_from(">h", data, delta_base + seg * 2)[0]
        id_range_offset = struct.unpack_from(">H", data, range_base + seg * 2)[0]
        for code in range(start_code, min(end_code, 0xFFFE) + 1):
            if id_range_offset == 0:
                glyph = (code + id_delta) & 0xFFFF
            else:
                # Per the sfnt spec the glyphIndexArray value is used DIRECTLY
                # (no idDelta) when idRangeOffset != 0 — applying the delta
                # here could wrap a real glyph index to 0 and report a false
                # glyph gap.
                glyph_index_addr = range_base + seg * 2 + id_range_offset + (code - start_code) * 2
                if glyph_index_addr + 2 > len(data):
                    continue
                glyph = struct.unpack_from(">H", data, glyph_index_addr)[0]
            if glyph:
                res.covered.add(code)


def _parse_format12(data: bytes, offset: int, res: CmapResult) -> None:
    n_groups = struct.unpack_from(">I", data, offset + 12)[0]
    base = offset + 16
    for g in range(n_groups):
        start, end, start_glyph = struct.unpack_from(">III", data, base + g * 12)
        for code in range(start, min(end, start + 0x10FFFF) + 1):
            if start_glyph + (code - start):
                res.covered.add(code)


def _parse_sfnt_cmap(data: bytes, res: CmapResult) -> bool:
    """Read the cmap subtables of a plain sfnt (TTF/OTF) buffer."""
    if len(data) < 12:
        return False
    num_tables = struct.unpack_from(">H", data, 4)[0]
    cmap_off = cmap_len = None
    for i in range(num_tables):
        rec = 12 + i * 16
        if rec + 16 > len(data):
            return False
        tag = data[rec:rec + 4]
        off, length = struct.unpack_from(">II", data, rec + 8)
        if tag == b"cmap":
            cmap_off, cmap_len = off, length
    if cmap_off is None or cmap_off + cmap_len > len(data):
        return False
    cmap = data[cmap_off:cmap_off + cmap_len]
    if len(cmap) < 4:
        return False
    num_sub = struct.unpack_from(">H", cmap, 2)[0]
    candidates: list[tuple[int, int]] = []  # (priority, subtable offset)
    for i in range(num_sub):
        rec = 4 + i * 8
        if rec + 8 > len(cmap):
            break
        platform, encoding, sub_off = struct.unpack_from(">HHI", cmap, rec)
        if platform == 3 and encoding == 10:
            candidates.append((0, sub_off))
        elif platform == 0:
            candidates.append((1, sub_off))
        elif platform == 3 and encoding == 1:
            candidates.append((2, sub_off))
        elif platform == 3 and encoding == 0:
            candidates.append((3, sub_off))
    for _, sub_off in sorted(candidates):
        if sub_off + 2 > len(cmap):
            continue
        fmt = struct.unpack_from(">H", cmap, sub_off)[0]
        res.formats_seen.append(fmt)
        try:
            if fmt == 4:
                _parse_format4(cmap, sub_off, res)
            elif fmt == 12:
                _parse_format12(cmap, sub_off, res)
            elif fmt == 0:
                _parse_format0(cmap, sub_off, res)
        except (struct.error, IndexError):
            continue  # tolerant: try the next candidate subtable
    return bool(res.covered)


def _woff_to_sfnt(raw: bytes) -> bytes | None:
    """Unpack a WOFF v1 container (zlib per-table) into sfnt bytes."""
    if len(raw) < 44 or raw[:4] != b"wOFF":
        return None
    flavor = raw[4:8]
    num_tables = struct.unpack_from(">H", raw, 12)[0]
    tables: list[tuple[bytes, bytes]] = []
    for i in range(num_tables):
        rec = 44 + i * 20
        if rec + 20 > len(raw):
            return None
        tag, off, comp_len, orig_len, _checksum = struct.unpack_from(">4sIIII", raw, rec)
        chunk = raw[off:off + comp_len]
        if comp_len < orig_len:
            try:
                chunk = zlib.decompress(chunk)
            except zlib.error:
                return None
        if len(chunk) != orig_len:
            return None
        tables.append((tag, chunk))
    sfnt = bytearray()
    sfnt += flavor
    sfnt += struct.pack(">HHHH", num_tables, 0, 0, 0)
    offset = 12 + 16 * len(tables)
    dir_part = bytearray()
    body = bytearray()
    for tag, chunk in tables:
        dir_part += tag + struct.pack(">III", 0, offset + len(body), len(chunk))
        body += chunk
        pad = (-len(chunk)) % 4
        body += b"\0" * pad
    sfnt += dir_part + body
    return bytes(sfnt)


def read_cmap(path: Path) -> tuple[CmapResult | None, str | None]:
    """Return (covered codepoints, None) or (None, reason).

    reason != None means the font could not be parsed; the audit reports it
    as unsupported/unreadable instead of pretending it passed.
    """
    try:
        raw = path.read_bytes()
    except OSError as e:
        return None, f"unreadable: {e}"
    if not raw:
        return None, "empty file"
    fonttools_error = None
    if raw[:4] == b"wOF2":
        font = _try_fonttools(path)
        if font is not None:
            return font
        return None, (
            "WOFF2 requires fontTools (pip install fontTools) — install it or "
            "audit a TTF/OTF/WOFF build of the same font"
        )
    res = CmapResult()
    sfnt = raw
    if raw[:4] == b"wOFF":
        sfnt = _woff_to_sfnt(raw)
        if sfnt is None:
            return None, "malformed WOFF container"
    if not _parse_sfnt_cmap(sfnt, res):
        # Built-in reader failed; fontTools may still understand the file.
        font = _try_fonttools(path)
        if font is not None:
            return font
        return None, "built-in cmap reader found no usable subtable"
    return res.covered, None


def _try_fonttools(path: Path) -> tuple[CmapResult, None] | tuple[None, str] | None:
    """Best-effort fontTools fallback. Returns None when fontTools is absent."""
    try:
        from fontTools.ttLib import TTFont  # type: ignore
    except ImportError:
        return None
    try:
        tt = TTFont(str(path), fontNumber=0, lazy=True)
        res = CmapResult()
        for table in tt["cmap"].tables:
            res.formats_seen.append(table.format)
            for code in table.cmap.keys():
                res.covered.add(code)
        return res.covered, None
    except Exception as e:  # fontTools raises a zoo of exceptions on bad files
        return None, f"fontTools could not parse: {e}"


# ------------------------------------------------------------- the audit

@dataclass
class FontAudit:
    file: str
    format: str
    status: str  # ok | gaps | unsupported | unreadable
    groups: dict[str, dict] = field(default_factory=dict)
    optional: dict[str, dict] = field(default_factory=dict)
    message: str | None = None

    def exit_worthy(self) -> bool:
        return self.status == "gaps"


def audit_font(path: Path, lang: str) -> FontAudit:
    req = REQUIRED_CODEPOINTS.get(lang)
    rel = path.name
    if req is None:
        return FontAudit(file=rel, format="?", status="unreadable",
                         message=f"unknown language {lang!r}")
    covered, reason = read_cmap(path)
    if covered is None:
        status = "unsupported" if "requires fontTools" in (reason or "") else "unreadable"
        suffix = path.suffix.lower().lstrip(".")
        return FontAudit(file=rel, format=suffix, status=status, message=reason)
    groups: dict[str, dict] = {}
    optional: dict[str, dict] = {}
    for group, cps in req.items():
        if group == "optional":
            for sub, sub_cps in cps.items():
                missing = sub_cps - covered
                optional[sub] = {
                    "covered": len(sub_cps) - len(missing),
                    "total": len(sub_cps),
                    "missing_chars": _char_label(missing) if missing else "",
                }
            continue
        missing = cps - covered
        groups[group] = {
            "covered": len(cps) - len(missing),
            "total": len(cps),
            "missing_chars": _char_label(missing) if missing else "",
        }
    has_gap = any(g["missing_chars"] for g in groups.values())
    fmt = path.suffix.lower().lstrip(".")
    return FontAudit(
        file=rel, format=fmt, status="gaps" if has_gap else "ok",
        groups=groups, optional=optional,
    )


def find_font_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*")
                  if p.is_file() and p.suffix.lower() in FONT_SUFFIXES
                  and ".raast-backup" not in p.parts)


def audit_project(root: Path, lang: str) -> dict:
    fonts = find_font_files(root)
    audits = [audit_font(p, lang) for p in fonts]
    return {
        "language": lang,
        "root": str(root),
        "fonts_scanned": len(audits),
        "fonts": [
            {
                "file": a.file, "format": a.format, "status": a.status,
                "groups": a.groups, "optional": a.optional,
                "message": a.message,
            }
            for a in audits
        ],
        "gaps": sum(1 for a in audits if a.exit_worthy()),
        "warnings": sum(1 for a in audits if a.status in ("unsupported", "unreadable")),
    }


# ------------------------------------------------------------- rendering

def audit_markdown(report: dict) -> str:
    lang = report["language"]
    lines = [
        f"# Font glyph-coverage audit — `{lang}`",
        "",
        f"Scanned **{report['fonts_scanned']}** font file(s) under `{report['root']}`; "
        f"{report['gaps']} with glyph gaps, {report['warnings']} warning(s).",
        "",
        "Mechanical check only: cmap coverage for the profile's required "
        "letters, digits, punctuation and format controls (ZWNJ for fa). "
        "Aesthetic quality still needs a native human eye — "
        "see docs/review-program.md.",
        "",
    ]
    for f in report["fonts"]:
        lines.append(f"## `{f['file']}` — {f['status']}")
        if f.get("message"):
            lines.append(f"- {f['message']}")
        for group, info in f.get("groups", {}).items():
            pct = round(100 * info["covered"] / info["total"]) if info["total"] else 100
            line = f"- {group}: {info['covered']}/{info['total']} ({pct}%)"
            if info["missing_chars"]:
                line += f" — missing: {info['missing_chars']}"
            lines.append(line)
        for sub, info in f.get("optional", {}).items():
            lines.append(f"- optional {sub}: {info['covered']}/{info['total']}")
        lines.append("")
    if not report["fonts"]:
        lines.append("No font files found — nothing to audit.")
    return "\n".join(lines)

