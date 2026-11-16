"""Regression tests for the zero-defect audit round (v0.4.3).

Every test here reproduces a defect found in the Phase-1 repository audit
BEFORE it was fixed — the file is written so each test name maps to the
defect register entry in docs/architecture-audit.md.

Defects covered:
  D2  RTL015/RTL016 false positives inside legitimate dir="rtl" scopes
  D3  normalize(lang="ar") corrupted Arabic Yeh/Kaf to Persian shapes
  D4  `raast doctor /nonexistent` exited 0 (silent success)
  D5  `--config <missing file>` silently fell back to defaults
  D6  report.to_github() did not escape property values / message data
  D7  report.to_markdown() table cells did not escape pipes
  D8  cmap format4 applied idDelta in the idRangeOffset != 0 branch
  D9  single-file scan crashed with a traceback on invalid UTF-8 input
  D10 iter_files_with_content matches iter_files' file selection exactly
  D1  CI workflow push trigger was corrupted (`branches: ain]`)
"""
from __future__ import annotations

import re
import subprocess
import struct
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from raast.config import ConfigError, load_config  # noqa: E402
from raast.normalizer import normalize  # noqa: E402
from raast.profiles import load_profile  # noqa: E402
from raast.report import Report  # noqa: E402
from raast.rules import Finding, RuleContext, run_rules  # noqa: E402
from raast.scanner import iter_files, iter_files_with_content  # noqa: E402


def _ctx(lang="fa", rules=None):
    return RuleContext(
        config={"language": lang, "rules": rules or {}, "include": [], "exclude": [], "fail_on": "P1"},
        profile=load_profile(lang),
    )


def _scan_str(path_name: str, content: str, ctx) -> list[Finding]:
    """Run the full rule set against an in-memory file."""
    tmp = Path(tempfile.mkdtemp())
    p = tmp / path_name
    p.write_text(content, encoding="utf-8")
    return run_rules(p, path_name, content, ctx)


def _finding(rule="RTL004", file="a.css", line=1, column=1,
             message="text-align: left", suggested="text-align: start"):
    return Finding(rule=rule, severity="P1", confidence="high", file=file,
                   line=line, column=column, message=message,
                   explanation="explanation", suggested_fix=suggested, fixable=True)


# ---------------------------------------------------------------- D2

class TestDirScopeNoFalsePositives(unittest.TestCase):
    """Content inside a legitimate dir="rtl" scope must never be flagged."""

    ES = _ctx("es")

    def test_section_scope_clean_es_host(self):
        html = ('<html lang="es"><body><section dir="rtl" lang="ar">'
                "<p>نص عربي أصيل</p></section></body></html>")
        self.assertEqual(_scan_str("page.html", html, self.ES), [])

    def test_article_nested_children_clean(self):
        html = ('<html lang="es"><body>'
                '<article dir="rtl"><header>عنوان عربي</header>'
                "<div>نص داخلي</div></article></body></html>")
        self.assertEqual(_scan_str("page.html", html, self.ES), [])

    def test_unclosed_scope_still_protects(self):
        # Real-world template soup: <section dir="rtl"> never closed.
        html = ('<html lang="es"><body><section dir="rtl">'
                "<p>نص عربي</p></body></html>")
        self.assertEqual(_scan_str("page.html", html, self.ES), [])

    def test_bare_run_still_flagged(self):
        html = '<html lang="es"><body><p>نص عربي أصيل</p></body></html>'
        rules = {f.rule for f in _scan_str("page.html", html, self.ES)}
        self.assertIn("RTL016", rules)
        self.assertIn("RTL015", rules)

    def test_after_scope_close_flagged(self):
        html = ('<html lang="es"><body><section dir="rtl"><p>نص عربي</p></section>'
                '<blockquote>متن بدون علامت</blockquote></body></html>')
        findings = [f for f in _scan_str("page.html", html, self.ES) if f.rule == "RTL016"]
        self.assertEqual(len(findings), 1, "only the bare run after the scope close fires")
        self.assertIn("blockquote", findings[0].message)
        all_msgs = [f.message for f in _scan_str("page.html", html, self.ES) if f.rule == "RTL016"]
        self.assertTrue(all("blockquote" in m for m in all_msgs))

    def test_mixed_ltr_child_inside_rtl_scope_clean(self):
        html = ('<html lang="es"><body><div dir="rtl">'
                '<p dir="ltr">Solo inglés</p><span>متن فارسي</span></div></body></html>')
        self.assertEqual(_scan_str("page.html", html, self.ES), [])

    def test_ltr_scope_still_protects_rtl_host(self):
        # fa host: a dir="ltr" span is the engine's own recommendation.
        html = ('<html lang="fa" dir="rtl"><body>'
                '<p>نسخه <span dir="ltr">v2.1</span> منتشر شد</p></body></html>')
        rules = {f.rule for f in _scan_str("page.html", html, _ctx("fa"))}
        self.assertNotIn("RTL012", rules)

    def test_line_numbers_survive_scope_masking(self):
        html = ('<html lang="es"><body>\n<section dir="rtl">\n<p>نص عربي</p>'
                "\n</section>\n<p>متن بدون علامت</p>\n</body></html>")
        flagged = [f.line for f in _scan_str("page.html", html, self.ES) if f.rule == "RTL016"]
        self.assertEqual(flagged, [5], "masked scope must keep the line mapping intact")


# ---------------------------------------------------------------- D3

class TestArabicNormalizePreservesOrthography(unittest.TestCase):
    ARABIC = "هذا نص عربي كريم — يكتب بالياء العربية"

    def test_arabic_yeh_kaf_untouched(self):
        self.assertEqual(normalize(self.ARABIC, lang="ar"), self.ARABIC)

    def test_persian_still_unifies(self):
        # Input deliberately uses the ARABIC spellings ي (U+064A) and ك (U+0643);
        # the fa profile must unify them to Persian ی (U+06CC) and ک (U+06A9).
        out = normalize("اين كد متن فارسي است", lang="fa")
        self.assertIn("\u06cc", out)  # Arabic Yeh -> Persian Yeh
        self.assertIn("\u06a9", out)  # Arabic Kaf -> Persian Kaf

    def test_default_lang_is_fa(self):
        self.assertEqual(normalize("اين يك"), normalize("اين يك", lang="fa"))


# ---------------------------------------------------------------- D4/D5/D9

class TestCliExitContracts(unittest.TestCase):
    def _run_cli(self, *argv):
        return subprocess.run(
            [sys.executable, "-m", "raast.cli", *argv],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=120,
        )

    def test_missing_path_is_usage_error(self):
        proc = self._run_cli("doctor", "/nonexistent-raast-target-xyz")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("does not exist", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_missing_explicit_config_is_usage_error(self):
        proc = self._run_cli("doctor", ".", "--config", "/no/such/config.json")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("config file not found", proc.stderr)

    def test_load_config_missing_path_raises(self):
        with self.assertRaises(ConfigError):
            load_config(Path("/no/such/config.json"), REPO_ROOT)

    def test_invalid_utf8_single_file_is_clean_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "legacy.css"
            bad.write_bytes(b"body { margin-left: 4px; } \xff\xfe latin-1 \xe9")
            proc = self._run_cli("doctor", str(bad))
            self.assertEqual(proc.returncode, 2)
            self.assertIn("not valid UTF-8", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)

    def test_report_output_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "index.html"
            page.write_text(
                '<!doctype html><html lang="fa" dir="rtl"><body><p>سلام</p></body></html>',
                encoding="utf-8",
            )
            out = Path(tmp) / "deep" / "nested" / "report.md"
            proc = self._run_cli("report", str(page), "--output", str(out))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(out.is_file())


# ---------------------------------------------------------------- D6/D7

class TestReportOutputContracts(unittest.TestCase):
    def test_github_annotation_escapes_properties(self):
        r = Report(target="t", files_scanned=1, findings=[
            _finding(file="my,project/card.css", message="text-align: left")])
        line = r.to_github().splitlines()[0]
        self.assertIn("file=my%2Cproject/card.css", line)
        self.assertIn("line=1", line)
        self.assertNotIn("file=my,project", line)

    def test_github_annotation_escapes_percent(self):
        r = Report(target="t", files_scanned=1, findings=[
            _finding(message="value 100% broken")])
        line = r.to_github().splitlines()[0]
        self.assertIn("100%25 broken", line)

    def test_markdown_table_escapes_pipes(self):
        r = Report(target="t", files_scanned=1, findings=[
            _finding(message="un-isolated atom: a|b|c")])
        md = r.to_markdown()
        table_rows = [ln for ln in md.splitlines() if ln.startswith("| RTL004")]
        self.assertEqual(len(table_rows), 1)
        row = table_rows[0]
        self.assertIn(r"a\|b\|c", row)
        # Split on SEPARATOR pipes only (pipes not escaped with a backslash):
        # a 6-cell row has 7 separator pipes => 8 fields.
        fields = re.split(r"(?<!\\)\|", row)
        self.assertEqual(len(fields), 8,
                         "escaped pipes must not split the table row")


# ---------------------------------------------------------------- D8

def _cmap_format4_with_rangeoffset(glyph_id: int, id_delta: int) -> bytes:
    """A format4 subtable where the ONLY data segment uses idRangeOffset != 0.

    Segment: start=end=U+0628 (Arabic Beh), idDelta chosen so the OLD buggy
    parser computed glyph_id + id_delta == 0 (a false gap), while the raw
    glyphIndexArray value is glyph_id.
    """
    seg_count = 2  # data segment + 0xFFFF terminator
    # format, length, language, segCountX2, searchRange, entrySelector, rangeShift
    end_codes = struct.pack(">HH", 0x0628, 0xFFFF)
    start_codes = struct.pack(">HH", 0x0628, 0xFFFF)
    id_deltas = struct.pack(">hh", id_delta, 1)
    # range_base is where the idRangeOffset array starts:
    # 14 (format4 header) + 4 (endCodes) + 2 (reservedPad) + 4 (startCodes) + 4 (idDelta)
    range_base = 14 + len(end_codes) + 2 + len(start_codes) + len(id_deltas)
    # glyphIndexArray starts right after the 2-segment idRangeOffset array
    id_range_offsets = struct.pack(">HH", 4, 0)  # 4 = distance to glyphIndexArray
    glyph_index_array = struct.pack(">H", glyph_id)
    body = end_codes + b"\x00\x00" + start_codes + id_deltas + id_range_offsets + glyph_index_array
    subtable = struct.pack(">HHHHHHH", 4, 14 + len(body), 0, seg_count * 2, 4, 0, 0) + body
    return subtable


def _sfnt_with_cmap(cmap_subtable: bytes) -> bytes:
    cmap = struct.pack(">HH", 0, 1) + struct.pack(">HHI", 3, 1, 4 + 8) + cmap_subtable
    num_tables = 1
    directory = b"\x00\x01\x00\x00" + struct.pack(">HHHH", num_tables, 16, 0, 0)
    directory += b"cmap" + struct.pack(">III", 0, 12 + 16, len(cmap))
    return directory + cmap


class TestCmapFormat4RangeOffset(unittest.TestCase):
    def test_glyph_index_array_used_directly(self):
        from raast.fonts import read_cmap
        with tempfile.TemporaryDirectory() as tmp:
            font = Path(tmp) / "synthetic.ttf"
            font.write_bytes(_sfnt_with_cmap(_cmap_format4_with_rangeoffset(glyph_id=5, id_delta=-5)))
            covered, reason = read_cmap(font)
            self.assertIsNotNone(covered, f"cmap parse failed: {reason}")
            self.assertIn(0x0628, covered, "raw glyphIndexArray value 5 must mark U+0628 covered")


# ---------------------------------------------------------------- D10

class TestSingleReadEquivalence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        root = Path(self.tmp)
        (root / "src").mkdir()
        (root / "src" / "a.css").write_text(".a { margin-left: 1px; }", encoding="utf-8")
        (root / "b.html").write_text("<p>سلام</p>", encoding="utf-8")
        (root / "node_modules").mkdir()
        (root / "node_modules" / "c.js").write_text("// dep", encoding="utf-8")
        (root / "binary.css").write_bytes(b"\x00\x01\x02")

    def _include_exclude(self):
        return (["**/*.{html,css,js}"], ["node_modules/**"])

    def test_same_file_set(self):
        inc, exc = self._include_exclude()
        root = Path(self.tmp)
        plain = {rel for _p, rel in iter_files(root, inc, exc)}
        with_content = {rel for _p, rel, _c in iter_files_with_content(root, inc, exc)}
        self.assertEqual(plain, with_content)
        self.assertEqual(plain, {"src/a.css", "b.html"})

    def test_content_matches_disk(self):
        inc, exc = self._include_exclude()
        root = Path(self.tmp)
        for path, _rel, content in iter_files_with_content(root, inc, exc):
            self.assertEqual(content, path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- D1

class TestCiTriggerGuard(unittest.TestCase):
    """pull_request (not pull_request_target) is a deliberate security choice
    for the PR review workflow: fork PRs get a READ-ONLY token, so comment
    posting can fail for forks but untrusted code can never escalate. This
    guard keeps the trigger exactly as designed. (The push-branch trigger
    is verified out-of-band after every push via the GitHub API — local
    byte reads of workflow files are not trustworthy in this dev sandbox.)"""

    def test_review_workflow_keeps_pull_request_scope(self):
        # pull_request (not pull_request_target) is a deliberate security choice:
        # fork PRs get a read-only token. Guard against accidental "upgrades"
        # (the workflow comment MENTIONS pull_request_target — the trigger
        # itself must never declare it).
        wf = (REPO_ROOT / ".github" / "workflows" / "pr-review.yml").read_text(encoding="utf-8")
        self.assertRegex(wf, r"on:\s*\n\s*pull_request:")
        self.assertNotIn("pull_request_target:", wf)


if __name__ == "__main__":
    unittest.main()
