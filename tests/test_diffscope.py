"""RAAST diff-scope tests (raast.diffscope) — "only new issues" policy.

The PR reviewer's credibility rests on this module: it must map a unified
diff to changed-line ranges of the NEW file exactly, and every documented
edge case (deleted files, binary files, renames, omitted hunk counts,
"no newline" markers, metadata-looking hunk bodies) must behave as the
docstring claims. These tests pin that contract.

Ranges always come from hunk headers (`@@ -a,b +c,d @@`):
  - `git diff -U0`  -> one tight range per changed line group
  - `diff -u` / -U3 -> one span covering the whole hunk (context included)

Run: python3 -m unittest discover -s tests -p test_diffscope.py -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from raast.diffscope import (  # noqa: E402
    file_changed_ranges,
    filter_findings,
    finding_in_ranges,
    parse_unified_diff,
)
from raast.rules import Finding  # noqa: E402


def _finding(file: str, line: int) -> Finding:
    return Finding(
        rule="RTL001", severity="P1", confidence="high", file=file, line=line,
        column=None, message="margin-left", explanation="physical margin",
        suggested_fix="margin-inline-start", fixable=True,
    )


GIT_DIFF_U0 = """diff --git a/src/card.css b/src/card.css
index 1111111..2222222 100644
--- a/src/card.css
+++ b/src/card.css
@@ -2 +2 @@
+.card { margin-left: 4px; }
@@ -4 +4 @@
+.btn { padding-right: 8px; }
"""


class TestBasicParsing(unittest.TestCase):
    def test_u0_added_lines_map_to_tight_ranges(self):
        ranges = parse_unified_diff(GIT_DIFF_U0)
        self.assertEqual(ranges, {"src/card.css": [(2, 2), (4, 4)]})

    def test_u3_context_hunk_is_one_span(self):
        diff = """--- a/a.css
+++ b/a.css
@@ -10,3 +10,3 @@
 old one
-old two
+new two
+new three
 old four
"""
        ranges = parse_unified_diff(diff)
        self.assertEqual(ranges, {"a.css": [(10, 12)]})

    def test_wrapper_functions_agree(self):
        self.assertEqual(file_changed_ranges(GIT_DIFF_U0), parse_unified_diff(GIT_DIFF_U0))

    def test_empty_diff(self):
        self.assertEqual(parse_unified_diff(""), {})

    def test_diff_without_hunks(self):
        self.assertEqual(parse_unified_diff("diff --git a/x b/x\n"), {})


class TestFileHeaderEdgeCases(unittest.TestCase):
    def test_deleted_file_produces_no_ranges(self):
        diff = """diff --git a/gone.css b/gone.css
deleted file mode 100644
--- a/gone.css
+++ /dev/null
@@ -1,2 +0,0 @@
-line one
-line two
"""
        self.assertEqual(parse_unified_diff(diff), {})

    def test_created_file_full_range(self):
        diff = """diff --git a/new.css b/new.css
new file mode 100644
--- /dev/null
+++ b/new.css
@@ -0,0 +1,3 @@
+a
+b
+c
"""
        self.assertEqual(parse_unified_diff(diff), {"new.css": [(1, 3)]})

    def test_binary_file_no_ranges(self):
        diff = """diff --git a/logo.png b/logo.png
Binary files a/logo.png and b/logo.png differ
"""
        self.assertEqual(parse_unified_diff(diff), {})

    def test_git_binary_patch_no_ranges(self):
        diff = """diff --git a/logo.png b/logo.png
GIT binary patch
literal 10
"""
        self.assertEqual(parse_unified_diff(diff), {})

    def test_rename_attaches_to_new_path(self):
        diff = """diff --git a/old.css b/renamed.css
similarity index 90%
rename from old.css
rename to renamed.css
--- a/old.css
+++ b/renamed.css
@@ -5 +5,2 @@
-new
+new and fixed
 context
"""
        ranges = parse_unified_diff(diff)
        self.assertEqual(ranges, {"renamed.css": [(5, 6)]})

    def test_gnu_diff_minus_u_with_timestamp(self):
        diff = """--- a/page.css\t2024-01-01 10:00:00
+++ b/page.css\t2024-01-02 10:00:00
@@ -3 +3 @@
-bad
+good
"""
        self.assertEqual(parse_unified_diff(diff), {"page.css": [(3, 3)]})

    def test_quoted_path_unquoted(self):
        # git quotes the whole path spec (including the b/ prefix) for
        # special-character paths: `+++ "b/weird name.css"`
        diff = 'diff --git "a/weird name.css" "b/weird name.css"\n' \
               '+++ "b/weird name.css"\n' \
               "@@ -1 +1 @@\n+x\n"
        self.assertEqual(parse_unified_diff(diff), {"weird name.css": [(1, 1)]})

    def test_side_a_of_header_ignored(self):
        # `--- a/deleted.css` must not create an entry; only the +++ side counts
        diff = """--- a/deleted.css
+++ b/live.css
@@ -1 +1 @@
-old
+new
"""
        self.assertEqual(parse_unified_diff(diff), {"live.css": [(1, 1)]})


class TestHunkHeaderEdgeCases(unittest.TestCase):
    def test_omitted_counts_mean_one_line(self):
        diff = """+++ b/x.css
@@ -3 +3 @@
-old
+new
"""
        self.assertEqual(parse_unified_diff(diff), {"x.css": [(3, 3)]})

    def test_zero_new_count_is_empty_range_skipped(self):
        # pure deletion: @@ -1,2 +0,0 @@ -> nothing to report on the new side
        diff = """+++ b/x.css
@@ -1,2 +0,0 @@
-gone one
-gone two
"""
        self.assertEqual(parse_unified_diff(diff), {})

    def test_hunk_header_with_trailing_section_text(self):
        diff = """+++ b/x.css
@@ -7,3 +7,3 @@ def helper():
-old
+new
 context
"""
        self.assertEqual(parse_unified_diff(diff), {"x.css": [(7, 9)]})

    def test_multiple_hunks_multiple_ranges(self):
        diff = """+++ b/x.css
@@ -1 +1 @@
-a
+1
@@ -50 +50 @@
-b
+2
@@ -100,2 +100,2 @@
-c
+3
+d
"""
        self.assertEqual(parse_unified_diff(diff), {"x.css": [(1, 1), (50, 50), (100, 101)]})

    def test_no_newline_marker_inside_hunk(self):
        diff = """+++ b/x.css
@@ -1 +1 @@
-old text
\\ No newline at end of file
+new text
\\ No newline at end of file
"""
        self.assertEqual(parse_unified_diff(diff), {"x.css": [(1, 1)]})

    def test_hunk_body_line_that_looks_like_metadata(self):
        # A removed line whose content is "++ foo" renders as "-++ foo" in the
        # body and an added one as "++ foo"; the counts from the hunk header
        # must consume both before metadata parsing resumes, so the second
        # hunk header is still recognized.
        diff = """+++ b/x.css
@@ -1,1 +1,1 @@
-++ foo
++ bar
@@ -9 +9 @@
-b
+n
"""
        self.assertEqual(parse_unified_diff(diff), {"x.css": [(1, 1), (9, 9)]})

    def test_hunk_body_removed_line_starting_with_plus(self):
        # "-+" prefix: a REMOVED line whose content itself starts with '+'
        diff = """+++ b/x.css
@@ -1,1 +1,1 @@
-+ added-then-removed
+kept
"""
        self.assertEqual(parse_unified_diff(diff), {"x.css": [(1, 1)]})

    def test_multiple_files_in_one_diff(self):
        diff = """diff --git a/a.css b/a.css
--- a/a.css
+++ b/a.css
@@ -1 +1 @@
-x
+one
diff --git a/b.html b/b.html
--- a/b.html
+++ b/b.html
@@ -2,2 +2,2 @@
-y
+two
+three
"""
        self.assertEqual(parse_unified_diff(diff),
                         {"a.css": [(1, 1)], "b.html": [(2, 3)]})

    def test_context_lines_do_not_create_ranges(self):
        # -U3 style: only the header span counts; context neighbor lines
        # (5 and 7 here) must not appear as changed ranges.
        diff = """+++ b/x.css
@@ -1 +1 @@
-plain old
+plain new
@@ -5,3 +6,3 @@
 c1
-changed
+fixed
 c2
"""
        ranges = parse_unified_diff(diff)
        self.assertEqual(ranges, {"x.css": [(1, 1), (6, 8)]})
        self.assertFalse(finding_in_ranges("x.css", 5, ranges))
        self.assertFalse(finding_in_ranges("x.css", 9, ranges))
        self.assertTrue(finding_in_ranges("x.css", 6, ranges))
        self.assertTrue(finding_in_ranges("x.css", 8, ranges))


class TestFindingMatching(unittest.TestCase):
    RANGES = {"src/card.css": [(2, 2), (4, 4)], "page.html": [(10, 12)]}

    def test_line_inside_range(self):
        self.assertTrue(finding_in_ranges("src/card.css", 2, self.RANGES))
        self.assertTrue(finding_in_ranges("src/card.css", 4, self.RANGES))

    def test_line_outside_range(self):
        self.assertFalse(finding_in_ranges("src/card.css", 1, self.RANGES))
        self.assertFalse(finding_in_ranges("src/card.css", 3, self.RANGES))
        self.assertFalse(finding_in_ranges("src/card.css", 5, self.RANGES))

    def test_span_boundaries_inclusive(self):
        self.assertTrue(finding_in_ranges("page.html", 10, self.RANGES))
        self.assertTrue(finding_in_ranges("page.html", 12, self.RANGES))
        self.assertFalse(finding_in_ranges("page.html", 13, self.RANGES))

    def test_unknown_file(self):
        self.assertFalse(finding_in_ranges("other.css", 2, self.RANGES))

    def test_zero_and_negative_lines_never_match(self):
        self.assertFalse(finding_in_ranges("src/card.css", 0, self.RANGES))
        self.assertFalse(finding_in_ranges("src/card.css", -1, self.RANGES))

    def test_tolerant_suffix_match_finding_relative(self):
        # scanner path is file-relative, diff path is repo-relative
        self.assertTrue(finding_in_ranges("card.css", 2, self.RANGES))

    def test_tolerant_suffix_match_diff_relative(self):
        # finding carries a deeper path than the diff (e.g. subrepo scan)
        self.assertTrue(finding_in_ranges("app/src/card.css", 2, self.RANGES))

    def test_suffix_match_requires_component_boundary(self):
        # "cardx.css" does NOT end with "card.css" at a component boundary
        self.assertFalse(finding_in_ranges("src/cardx.css", 2,
                                           {"card.css": [(2, 2)]}))

    def test_filter_findings_keeps_only_in_range(self):
        findings = [
            _finding("src/card.css", 2),   # changed   -> keep
            _finding("src/card.css", 1),   # unchanged -> drop
            _finding("page.html", 11),     # changed   -> keep
            _finding("page.html", 99),     # unchanged -> drop
            _finding("other.css", 2),      # untouched file -> drop
        ]
        kept = filter_findings(findings, self.RANGES)
        self.assertEqual([(f.file, f.line) for f in kept],
                         [("src/card.css", 2), ("page.html", 11)])

    def test_filter_findings_empty_ranges_keeps_nothing(self):
        self.assertEqual(filter_findings([_finding("a.css", 1)], {}), [])

    def test_normalize_paths(self):
        ranges = {"src/card.css": [(2, 2)]}
        self.assertTrue(finding_in_ranges("./src/card.css", 2, ranges))
        self.assertTrue(finding_in_ranges("src\\card.css", 2, ranges))


if __name__ == "__main__":
    unittest.main()
