"""RAAST PR review tests (raast.review) — diff-scoped review gate.

Integration layer: a real temp git repository with a base branch (old debt)
and a feature branch (new debt + new clean lines) proves the core promise —
"report only findings on lines this PR changed, never pre-existing debt".
Unit layer: comment/annotation builders, severity ordering, exit-code
thresholds, and the extension filter.

Run: python3 -m unittest discover -s tests -p test_review.py -v
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from raast.review import (  # noqa: E402
    COMMENT_MARKER,
    REVIEWED_EXTENSIONS,
    _at_or_above,
    _build_comment_markdown,
    _build_github,
    _escape_property,
    _is_reviewed,
    _sort_findings,
    main,
)
from raast.rules import Finding  # noqa: E402

BASE_CSS = """/* کارت اصلی */
.card {
  margin-left: 4px;
  color: #333;
}
"""


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-c", "user.name=raast-test",
                           "-c", "user.email=raast-test@example.test",
                           "-c", "commit.gpgsign=false", *args],
                          cwd=str(repo), check=True, capture_output=True, text=True)
    return proc.stdout.strip()


def _finding(rule="RTL001", severity="P1", file="src/a.css", line=2) -> Finding:
    return Finding(
        rule=rule, severity=severity, confidence="high", file=file, line=line,
        column=None, message="margin-left: 4px", explanation="physical margin",
        suggested_fix="margin-inline-start: 4px", fixable=True,
    )


class _GitRepoCase(unittest.TestCase):
    """Base: one committed physical margin (PRE-EXISTING debt on line 3,
    file carries a Persian comment so the RTL-script gate is satisfied).
    Feature branch: appends a NEW physical margin (line 8) to the same file
    and adds a brand-new file with another finding."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "proj"
        self.repo.mkdir()
        _git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "src").mkdir()
        (self.repo / "src" / "card.css").write_text(BASE_CSS, encoding="utf-8")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-q", "-m", "base")
        # feature branch: append a new violation AFTER the untouched debt
        _git(self.repo, "checkout", "-q", "-b", "feature")
        css = self.repo / "src" / "card.css"
        css.write_text(BASE_CSS + "\n.btn {\n  margin-right: 8px;\n}\n", encoding="utf-8")
        (self.repo / "src" / "new.html").write_text(
            '<!doctype html><html lang="fa"><body><p>سلام</p></body></html>',
            encoding="utf-8")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-q", "-m", "feature work")

    def tearDown(self):
        self._tmp.cleanup()

    def _review(self, *extra: str) -> tuple[int, str, str]:
        proc = subprocess.run(
            [sys.executable, "-m", "raast.review", "--base", "main",
             "--path", str(self.repo), *extra],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        return proc.returncode, proc.stdout, proc.stderr

    def _comment_out(self, td: Path) -> Path:
        return td / "comment.md"


class TestChangedLinesOnly(_GitRepoCase):
    """THE core promise: new debt reported, pre-existing debt silent."""

    def test_only_new_lines_reported_github_format(self):
        with tempfile.TemporaryDirectory() as td:
            comment = self._comment_out(Path(td))
            code, out, err = self._review("--format", "github",
                                          "--comment-out", str(comment))
            self.assertEqual(code, 1, "findings on changed lines -> exit 1")
            # card.css line 8 (new margin-right) is reported...
            self.assertIn("file=src/card.css,line=8", out)
            # ...but line 3 (pre-existing margin-left, untouched) is NOT
            self.assertNotIn("file=src/card.css,line=3", out)
            # new.html line 1 (missing dir) is reported — it is a new file
            self.assertIn("file=src/new.html", out)

    def test_pre_existing_debt_absent_from_comment(self):
        with tempfile.TemporaryDirectory() as td:
            comment = self._comment_out(Path(td))
            code, _out, _err = self._review("--comment-out", str(comment))
            self.assertEqual(code, 1)
            body = comment.read_text(encoding="utf-8")
            self.assertIn(COMMENT_MARKER, body)
            self.assertIn("line 8", body)
            # the pre-existing margin-left finding (line 3) stays silent
            self.assertNotIn("margin-left", body)
            self.assertNotIn("**Status:** Passed", body)
            self.assertIn("**Status:** Review required.", body)

    def test_range_count_and_scanned_files_in_comment(self):
        with tempfile.TemporaryDirectory() as td:
            comment = self._comment_out(Path(td))
            self._review("--comment-out", str(comment))
            body = comment.read_text(encoding="utf-8")
            # 2 changed files scanned (card.css + new.html)
            self.assertIn("Scanned 2 changed file(s)", body)
            self.assertIn("Reporting only findings on lines changed in this PR.", body)

    def test_clean_branch_passes_even_with_repo_debt(self):
        # a PR off MAIN that changes nothing problematic must pass, despite
        # the pre-existing margin-left debt on main (adoptability on day one)
        _git(self.repo, "checkout", "-q", "-b", "clean-pr", "main")
        (self.repo / "src" / "clean.css").write_text(
            ".ok { color: inherit; }\n", encoding="utf-8")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-q", "-m", "clean work")
        with tempfile.TemporaryDirectory() as td:
            comment = self._comment_out(Path(td))
            code, _out, _err = self._review("--comment-out", str(comment),
                                            "--fail-on", "P1")
            self.assertEqual(code, 0)
            body = comment.read_text(encoding="utf-8")
            self.assertIn("**Status:** Passed", body)
            # the untouched margin-left debt stays silent
            self.assertNotIn("margin-left: 4px", body)


class TestExitCodeThresholds(_GitRepoCase):
    def test_fail_on_p0_blocks_on_p0_finding(self):
        # new.html is a new file with lang=fa but no dir -> RTL006 (P0) on
        # line 1; the P0 gate must block even though P1s are also present
        with tempfile.TemporaryDirectory() as td:
            code, _out, _err = self._review("--fail-on", "P0",
                                            "--comment-out", str(self._comment_out(Path(td))))
            self.assertEqual(code, 1)

    def test_fail_on_p0_passes_when_only_p1_p2_changed(self):
        # a branch whose only finding is the P1 margin-right must pass a P0 gate
        _git(self.repo, "checkout", "-q", "-b", "p1-only", "main")
        css = self.repo / "src" / "card.css"
        css.write_text(BASE_CSS + "\n.btn {\n  margin-right: 8px;\n}\n", encoding="utf-8")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-q", "-m", "p1 only")
        with tempfile.TemporaryDirectory() as td:
            code, _out, _err = self._review("--fail-on", "P0",
                                            "--comment-out", str(self._comment_out(Path(td))))
            self.assertEqual(code, 0)

    def test_fail_on_off_always_zero(self):
        with tempfile.TemporaryDirectory() as td:
            code, _out, _err = self._review("--fail-on", "off",
                                            "--comment-out", str(self._comment_out(Path(td))))
            self.assertEqual(code, 0)

    def test_fail_on_p2_blocks_on_any_finding(self):
        with tempfile.TemporaryDirectory() as td:
            code, _out, _err = self._review("--fail-on", "P2",
                                            "--comment-out", str(self._comment_out(Path(td))))
            self.assertEqual(code, 1)


class TestUsageErrors(_GitRepoCase):
    def test_bad_base_ref_is_exit_2(self):
        proc = subprocess.run(
            [sys.executable, "-m", "raast.review", "--base", "no-such-ref",
             "--path", str(self.repo)],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("git command failed", proc.stderr)

    def test_not_a_git_repo_is_exit_2(self):
        with tempfile.TemporaryDirectory() as td:
            plain = Path(td) / "plain"
            plain.mkdir()
            proc = subprocess.run(
                [sys.executable, "-m", "raast.review", "--base", "main",
                 "--path", str(plain)],
                capture_output=True, text=True, cwd=str(REPO_ROOT),
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("not inside a git repository", proc.stderr)


class TestCommentBuilder(unittest.TestCase):
    def test_marker_first_line(self):
        body = _build_comment_markdown(1, 1, [_finding()])
        self.assertTrue(body.startswith(COMMENT_MARKER + "\n"))

    def test_grouped_by_severity_with_counts(self):
        findings = [_finding("RTL001", "P1"), _finding("RTL003", "P0"),
                    _finding("RTL005", "P2"), _finding("RTL008", "P2")]
        body = _build_comment_markdown(4, 4, findings)
        # P0 block appears before P1 before P2
        self.assertLess(body.index("### P0"), body.index("### P1"))
        self.assertLess(body.index("### P1"), body.index("### P2"))
        self.assertIn("| P0 | 1 |", body)
        self.assertIn("| P1 | 1 |", body)
        self.assertIn("| P2 | 2 |", body)
        self.assertIn("**Status:** Review required.", body)

    def test_clean_comment_has_passed_status(self):
        body = _build_comment_markdown(1, 1, [])
        self.assertIn("**Status:** Passed — no RTL issues on changed lines.", body)
        self.assertIn("| P0 | 0 |", body)
        self.assertIn("| P1 | 0 |", body)
        self.assertIn("| P2 | 0 |", body)

    def test_suggested_fix_line_present(self):
        body = _build_comment_markdown(1, 1, [_finding()])
        self.assertIn("**Issue:** margin-left: 4px", body)
        self.assertIn("**Suggested fix:** margin-inline-start: 4px", body)
        self.assertIn("`src/a.css` · line 2", body)


class TestGithubAnnotations(unittest.TestCase):
    def test_p0_p1_are_errors_p2_warnings(self):
        out = _build_github([_finding("RTL003", "P0"),
                             _finding("RTL001", "P1"),
                             _finding("RTL005", "P2")])
        lines = out.splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("::error "))
        self.assertTrue(lines[1].startswith("::error "))
        self.assertTrue(lines[2].startswith("::warning "))
        self.assertIn("file=src/a.css,line=2", lines[1])
        self.assertIn("title=RTL003 (P0)", lines[0])

    def test_deterministic_order(self):
        findings = [_finding("RTL005", "P2", "b.css", 1),
                    _finding("RTL001", "P1", "a.css", 3),
                    _finding("RTL001", "P1", "a.css", 1)]
        out = _build_github(findings)
        pos_p1_a1 = out.index("line=1")
        pos_p1_a3 = out.index("line=3")
        pos_p2 = out.index("::warning")
        self.assertLess(pos_p1_a1, pos_p1_a3)
        self.assertLess(pos_p1_a3, pos_p2)

    def test_empty_findings_empty_output(self):
        self.assertEqual(_build_github([]), "")

    def test_property_escaping(self):
        self.assertEqual(_escape_property("a:b,c%d\ne"), "a%3Ab%2Cc%25d%0Ae")


class TestSeverityHelpers(unittest.TestCase):
    def test_at_or_above_ordering(self):
        # "at or above the threshold" = at least AS SEVERE as the gate:
        # a P1 finding does NOT trip a P0 gate, but a P0 finding trips a P1 gate
        self.assertTrue(_at_or_above("P0", "P0"))
        self.assertFalse(_at_or_above("P1", "P0"))
        self.assertFalse(_at_or_above("P2", "P0"))
        self.assertTrue(_at_or_above("P0", "P1"))
        self.assertTrue(_at_or_above("P1", "P1"))
        self.assertFalse(_at_or_above("P2", "P1"))
        self.assertTrue(_at_or_above("P2", "P2"))

    def test_sort_findings_deterministic(self):
        findings = [_finding("RTL005", "P2", "b.css", 1),
                    _finding("RTL001", "P1", "a.css", 9),
                    _finding("RTL003", "P0", "c.css", 1)]
        ordered = _sort_findings(findings)
        self.assertEqual([f.severity for f in ordered], ["P0", "P1", "P2"])


class TestExtensionFilter(unittest.TestCase):
    def test_reviewed_extensions(self):
        for ext in (".html", ".css", ".vue", ".tsx", ".md"):
            self.assertTrue(_is_reviewed(f"src/file{ext}"))
            self.assertTrue(_is_reviewed(f"src/file{ext.upper()}"))

    def test_non_reviewed_extensions_skipped(self):
        for name in ("logo.png", "data.json", "main.py", "lock", "archive.zip"):
            self.assertFalse(_is_reviewed(name))


if __name__ == "__main__":
    unittest.main()
