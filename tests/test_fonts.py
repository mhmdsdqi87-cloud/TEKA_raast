"""RAAST font glyph-coverage audit tests (raast.fonts).

The audit must prove real coverage from real cmap tables — so these tests
build synthetic TTF/WOFF binaries in-memory (a valid sfnt with a cmap
format 4 subtable) and run the actual parser against them. No external
fontTools dependency is required: the built-in reader handles formats
0/4/12 and WOFF v1 via zlib.

Run: python3 -m unittest discover -s tests -p test_fonts.py -v
"""
from __future__ import annotations

import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from raast.fonts import (  # noqa: E402
    REQUIRED_CODEPOINTS, CmapResult, _parse_sfnt_cmap, audit_font,
    audit_project, read_cmap,
)


# ------------------------------------------------------------ TTF builder

def _cmap_format4(ranges: list[tuple[int, int]]) -> bytes:
    """Build a cmap format 4 subtable from inclusive codepoint ranges."""
    segs = ranges + [(0xFFFF, 0xFFFF)]
    seg_count = len(segs)
    end_codes = b"".join(struct.pack(">H", end) for _, end in segs)
    start_codes = b"".join(struct.pack(">H", start) for start, _ in segs)
    # idDelta = 0 everywhere; every mapped codepoint "has" a glyph (id 0 is
    # technically .notdef, but coverage audits only need cmap presence).
    id_deltas = b"\x00\x01" * seg_count  # delta = 1 -> glyph = code + 1 (non-zero)
    id_range_offsets = b"\x00\x00" * seg_count
    length = 14 + len(end_codes) + 2 + len(start_codes) + len(id_deltas) + len(id_range_offsets)
    header = struct.pack(
        ">HHHHHHH", 4, length, 0, seg_count * 2, 0, 0, seg_count * 2 - seg_count * 2
    )
    return header + end_codes + b"\x00\x00" + start_codes + id_deltas + id_range_offsets


def _sfnt_with_cmap(cmap_subtable: bytes) -> bytes:
    """Wrap a cmap subtable into a minimal one-table sfnt (TTF)."""
    cmap = struct.pack(">HH", 0, 1) + struct.pack(">HHI", 3, 1, 4 + 8) + cmap_subtable
    tables = [(b"cmap", cmap)]
    num_tables = len(tables)
    header_len = 12 + 16 * num_tables
    body = b""
    directory = b""
    offset = header_len
    for tag, data in tables:
        directory += tag + struct.pack(">III", 0, offset, len(data))
        body += data
        offset += len(data) + (-len(data)) % 4
    head = b"\x00\x01\x00\x00" + struct.pack(">HHHH", num_tables, 0, 0, 0)
    return head + directory + body


def _woff_wrap(sfnt: bytes) -> bytes:
    """Wrap sfnt bytes into a WOFF v1 container (stored or zlib table)."""
    num_tables = struct.unpack_from(">H", sfnt, 4)[0]
    flavor = sfnt[0:4]
    raw_table = sfnt[12 + 16 * num_tables:]
    comp = zlib.compress(raw_table)
    # WOFF rule: zlib only when it actually shrinks; otherwise store raw.
    if len(comp) < len(raw_table):
        table_data, comp_len = comp, len(comp)
    else:
        table_data, comp_len = raw_table, len(raw_table)
    orig_len = len(raw_table)
    header = (b"wOFF" + flavor
              + struct.pack(">I", 44 + 20 * num_tables + len(table_data))
              + struct.pack(">H", num_tables)
              + struct.pack(">H", 0)
              + struct.pack(">I", 12 + 16 * num_tables)   # totalSfntSize
              + struct.pack(">HH", 1, 0)                  # version
              + struct.pack(">IIIII", 0, 0, 0, 0, 0))     # meta/priv blocks
    entry = b"cmap" + struct.pack(
        ">IIII", 44 + 20, comp_len, orig_len, 0
    )
    return header + entry + table_data


PERSIAN_RANGES = [(0x0621, 0x064A), (0x067E, 0x067E), (0x0686, 0x0686),
                  (0x0698, 0x0698), (0x06AF, 0x06AF), (0x06A9, 0x06A9),
                  (0x06CC, 0x06CC), (0x06F0, 0x06F9), (0x200C, 0x200C),
                  (0x060C, 0x061F), (0x00AB, 0x00BB), (0x2026, 0x2026)]


class TestParser(unittest.TestCase):
    def test_format4_covers_built_ranges(self):
        sfnt = _sfnt_with_cmap(_cmap_format4(PERSIAN_RANGES))
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "font.ttf"
            p.write_bytes(sfnt)
            res, err = read_cmap(p)
        self.assertIsNone(err)
        self.assertIn(0x0627, res)              # ا
        self.assertIn(0x067E, res)              # پ
        self.assertIn(0x06F0, res)              # ۰
        self.assertIn(0x200C, res)              # ZWNJ
        self.assertNotIn(0x05D0, res)           # no Hebrew

    def test_persian_font_passes_fa_audit(self):
        sfnt = _sfnt_with_cmap(_cmap_format4(PERSIAN_RANGES))
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "Vazirmatn.ttf"
            p.write_bytes(sfnt)
            audit = audit_font(p, "fa")
        self.assertEqual(audit.status, "ok")
        self.assertEqual(audit.format, "ttf")
        for group, info in audit.groups.items():
            self.assertEqual(info["missing_chars"], "", f"{group} should be fully covered")

    def test_latin_only_font_fails_fa_audit(self):
        sfnt = _sfnt_with_cmap(_cmap_format4([(0x0041, 0x005A)]))
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "latin-display.ttf"
            p.write_bytes(sfnt)
            audit = audit_font(p, "fa")
        self.assertEqual(audit.status, "gaps")
        self.assertIn("U+0627", audit.groups["letters"]["missing_chars"])
        self.assertIn("U+200C", audit.groups["format_controls"]["missing_chars"])
        self.assertTrue(audit.exit_worthy())

    def test_missing_persian_digits_only(self):
        # Arabic base letters without the Extended (Persian) digit row.
        ranges = [(0x0621, 0x064A), (0x067E, 0x067E), (0x0686, 0x0686),
                  (0x0698, 0x0698), (0x06AF, 0x06AF), (0x06A9, 0x06A9),
                  (0x06CC, 0x06CC), (0x200C, 0x200C), (0x060C, 0x061F)]
        sfnt = _sfnt_with_cmap(_cmap_format4(ranges))
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "no-digits.ttf"
            p.write_bytes(sfnt)
            audit = audit_font(p, "fa")
        self.assertEqual(audit.status, "gaps")
        self.assertEqual(audit.groups["letters"]["missing_chars"], "")
        self.assertIn("U+06F0", audit.groups["digits"]["missing_chars"])

    def test_woff_container_is_unpacked(self):
        sfnt = _sfnt_with_cmap(_cmap_format4(PERSIAN_RANGES))
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "font.woff"
            p.write_bytes(_woff_wrap(sfnt))
            res, err = read_cmap(p)
            self.assertIsNone(err)
            self.assertIn(0x067E, res)
            audit = audit_font(p, "fa")
            self.assertEqual(audit.status, "ok")

    def test_woff2_without_fonttools_reports_unsupported(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "font.woff2"
            p.write_bytes(b"wOF2" + b"\x00" * 100)
            audit = audit_font(p, "fa")
            # fontTools may be installed in the dev environment; both outcomes
            # are acceptable, but the status must never be "ok" for garbage.
            self.assertIn(audit.status, ("unsupported", "unreadable"))
            self.assertFalse(audit.exit_worthy())

    def test_garbage_file_is_unreadable_not_gaps(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "broken.ttf"
            p.write_bytes(b"not a font at all")
            audit = audit_font(p, "fa")
            self.assertEqual(audit.status, "unreadable")
            self.assertFalse(audit.exit_worthy())

    def test_empty_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "empty.ttf"
            p.write_bytes(b"")
            audit = audit_font(p, "fa")
            self.assertEqual(audit.status, "unreadable")

    def test_direct_parse_helper(self):
        res = CmapResult()
        self.assertTrue(_parse_sfnt_cmap(_sfnt_with_cmap(_cmap_format4([(0x0621, 0x0623)])), res))
        self.assertEqual(res.covered, {0x0621, 0x0622, 0x0623})


class TestProjectAudit(unittest.TestCase):
    def test_audit_project_counts_and_skips_backups(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "fonts").mkdir()
            (root / "fonts" / "good.ttf").write_bytes(
                _sfnt_with_cmap(_cmap_format4(PERSIAN_RANGES)))
            (root / "fonts" / "latin.ttf").write_bytes(
                _sfnt_with_cmap(_cmap_format4([(0x0041, 0x005A)])))
            backup = root / ".raast-backup"
            backup.mkdir()
            (backup / "ignored.ttf").write_bytes(b"junk")
            report = audit_project(root, "fa")
        self.assertEqual(report["fonts_scanned"], 2)
        self.assertEqual(report["gaps"], 1)
        self.assertEqual(report["warnings"], 0)

    def test_no_fonts_is_clean(self):
        with tempfile.TemporaryDirectory() as td:
            report = audit_project(Path(td), "fa")
        self.assertEqual(report["fonts_scanned"], 0)
        self.assertEqual(report["gaps"], 0)

    def test_requirement_sets_are_sane(self):
        fa = REQUIRED_CODEPOINTS["fa"]
        self.assertIn(0x200C, fa["format_controls"])
        self.assertIn(0x067E, fa["letters"])   # پ
        self.assertIn(0x06AF, fa["letters"])   # گ
        self.assertIn(0x06F0, fa["digits"])    # ۰
        he = REQUIRED_CODEPOINTS["he"]
        self.assertIn(0x05D0, he["letters"])   # א
        self.assertIn(0x05F4, he["punctuation"])  # gershayim
        es = REQUIRED_CODEPOINTS["es"]
        self.assertIn(0x00BF, es["punctuation"])  # ¿
        self.assertIn(0x00F1, es["letters"])      # ñ


if __name__ == "__main__":
    unittest.main()
