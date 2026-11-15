"""RAAST Auto-Fix 2.0 tests (raast.fixer) — tiers, journal, revert.

Covers the three-tier fix classification (safe / suggested / manual), the
append-only fix journal (.raast-backup/journal.json), and revert_all, which
must restore EXACTLY the bytes that were there before the fix — the undo
path has to be as trustworthy as the fix path.

Run: python3 -m unittest discover -s tests -p test_autofix.py -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from raast.fixer import (  # noqa: E402
    BACKUP_DIRNAME,
    FIX_TIERS,
    JOURNAL_FILENAME,
    apply_fix,
    fix_file,
    journal_append,
    journal_load,
    revert_all,
    tier_for,
)
from raast.rules import Finding  # noqa: E402

ZWNJ = "\u200c"


def _finding(rule: str, line: int, message: str, fix: str,
             confidence: str = "high", fixable: bool = True) -> Finding:
    return Finding(
        rule=rule, severity="P1", confidence=confidence, file="page.html", line=line,
        column=None, message=message, explanation="test", suggested_fix=fix,
        fixable=fixable,
    )


CSS = """.card {
  margin-left: 4px;
  padding-right: 8px;
  text-align: left;
  letter-spacing: 0.05em;
}
"""


class TestTierClassification(unittest.TestCase):
    def test_every_static_rule_has_exactly_one_tier(self):
        # RTL001..RTL017 — the complete static namespace must be classified
        expected = {f"RTL{n:03d}" for n in range(1, 18)}
        self.assertEqual(set(FIX_TIERS.keys()), expected)

    def test_tier_values_are_valid(self):
        for rule, tier in FIX_TIERS.items():
            self.assertIn(tier, ("safe", "suggested", "manual"), f"{rule}: bad tier {tier}")

    def test_safe_tier_is_mechanical_subset(self):
        safe = {r for r, t in FIX_TIERS.items() if t == "safe"}
        self.assertEqual(safe, {"RTL001", "RTL002", "RTL004", "RTL005", "RTL008", "RTL011"})

    def test_unknown_rule_falls_back_to_manual(self):
        self.assertEqual(tier_for("RTL999"), "manual")
        self.assertEqual(tier_for("RT001"), "manual")
        self.assertEqual(tier_for(""), "manual")


class TestFixFile(unittest.TestCase):
    def test_safe_tier_rewrites_physical_declarations_on_flagged_lines(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "page.html"
            path.write_text(CSS, encoding="utf-8")
            findings = [
                _finding("RTL001", 2, "physical margin-left declaration", "margin-inline-start: 4px"),
                _finding("RTL002", 3, "physical padding-right declaration", "padding-inline-end: 8px"),
                _finding("RTL004", 4, "text-align: left", "text-align: start"),
                _finding("RTL005", 5, "letter-spacing on Arabic script", "remove letter-spacing"),
            ]
            result = fix_file(path, "page.html", findings, tier="safe")
            self.assertTrue(result.changed)
            out = result.content
            self.assertIn("margin-inline-start: 4px", out)
            self.assertIn("padding-inline-end: 8px", out)
            self.assertIn("text-align: start", out)
            self.assertNotIn("letter-spacing", out)
            self.assertEqual(result.fix_count, 4)
            self.assertEqual(set(result.rules_applied), {"RTL001", "RTL002", "RTL004", "RTL005"})
            self.assertEqual(result.tiers.get("safe"), 4)
            self.assertNotIn("suggested", result.tiers)
            self.assertNotIn("manual", result.tiers)
            # diff is a unified diff naming the file with before/after labels
            self.assertIn("--- page.html (before)", result.diff)
            self.assertIn("+++ page.html (after)", result.diff)
            self.assertIn("-  margin-left: 4px;", result.diff)
            self.assertIn("+  margin-inline-start: 4px;", result.diff)

    def test_low_confidence_or_unfixable_findings_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "page.html"
            path.write_text(CSS, encoding="utf-8")
            findings = [_finding("RTL001", 2, "physical margin-left declaration",
                                 "margin-inline-start: 4px", confidence="low"),
                        _finding("RTL001", 3, "physical margin-left declaration",
                                 "margin-inline-start: 4px", fixable=False)]
            result = fix_file(path, "page.html", findings, tier="safe")
            self.assertFalse(result.changed)
            self.assertEqual(result.fix_count, 0)

    def test_out_of_range_line_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "page.html"
            path.write_text(CSS, encoding="utf-8")
            findings = [_finding("RTL001", 99, "physical margin-left declaration",
                                 "margin-inline-start: 4px")]
            result = fix_file(path, "page.html", findings, tier="safe")
            self.assertFalse(result.changed)

    def test_manual_tier_never_applied(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "page.html"
            path.write_text(CSS, encoding="utf-8")
            # RTL003 is manual: even a well-formed finding must not change bytes
            findings = [_finding("RTL003", 2, "physical `left:` positioning",
                                 "review; prefer inset-inline-start", fixable=False)]
            result = fix_file(path, "page.html", findings, tier="safe")
            self.assertFalse(result.changed)
            self.assertEqual(result.fix_count, 0)

    def test_unrelated_lines_untouched(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "page.html"
            path.write_text(CSS, encoding="utf-8")
            # finding points at line 2, the margin-left line; line 4's
            # text-align: left has NO finding -> must survive untouched
            findings = [_finding("RTL001", 2, "physical margin-left declaration",
                                 "margin-inline-start: 4px")]
            result = fix_file(path, "page.html", findings, tier="safe")
            self.assertIn("text-align: left", result.content)
            self.assertEqual(result.fix_count, 1)


class TestSuggestedTierGating(unittest.TestCase):
    def test_suggested_blocked_under_safe_policy(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "page.html"
            path.write_text("قیمت 5 دلار\n", encoding="utf-8")
            result = fix_file(path, "page.html", [], zwnj=True, lang="fa",
                              zwnj_digits=True, tier="safe")
            self.assertEqual(result.content, "قیمت 5 دلار\n")  # digits untouched
            self.assertNotIn("RTL010", result.rules_applied)

    def test_suggested_applies_under_all_policy_with_flag(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "page.html"
            path.write_text("قیمت 5 دلار\n", encoding="utf-8")
            result = fix_file(path, "page.html", [], zwnj=True, lang="fa",
                              zwnj_digits=True, tier="all")
            self.assertIn("قیمت ۵ دلار", result.content)
            self.assertIn("RTL010", result.rules_applied)
            self.assertGreater(result.tiers.get("suggested", 0), 0)

    def test_ltr_digit_atoms_survive_digit_fix(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "page.html"
            path.write_text("قیمت $5 و شماره ‎+982100000000\n", encoding="utf-8")
            result = fix_file(path, "page.html", [], zwnj=True, lang="fa",
                              zwnj_digits=True, tier="all")
            self.assertIn("$5", result.content)            # amount survives
            self.assertIn("+982100000000", result.content)  # phone survives

    def test_digit_fix_is_fa_only(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "page.html"
            path.write_text("كتاب 5\n", encoding="utf-8")
            result = fix_file(path, "page.html", [], zwnj=True, lang="ar",
                              zwnj_digits=True, tier="all")
            self.assertIn("5", result.content)  # Arabic-Indic set is already correct in ar


class TestJournal(unittest.TestCase):
    def test_append_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.assertEqual(journal_load(root), [])  # missing -> tolerant []
            journal_append(root, {"file": "a.html", "backup": "a.html", "rules": ["RTL001"]})
            journal_append(root, {"file": "b.html", "backup": "b.html", "rules": []})
            entries = journal_load(root)
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0]["file"], "a.html")
            self.assertEqual(entries[1]["file"], "b.html")

    def test_corrupt_journal_is_tolerated_as_empty(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            jp = root / BACKUP_DIRNAME / JOURNAL_FILENAME
            jp.parent.mkdir(parents=True)
            jp.write_text("{not valid json", encoding="utf-8")
            self.assertEqual(journal_load(root), [])

    def test_non_list_journal_is_tolerated_as_empty(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            jp = root / BACKUP_DIRNAME / JOURNAL_FILENAME
            jp.parent.mkdir(parents=True)
            jp.write_text('{"file": "a.html"}', encoding="utf-8")
            self.assertEqual(journal_load(root), [])

    def test_non_dict_entries_filtered(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            jp = root / BACKUP_DIRNAME / JOURNAL_FILENAME
            jp.parent.mkdir(parents=True)
            jp.write_text('["junk", {"file": "a.html", "backup": "a.html"}]', encoding="utf-8")
            entries = journal_load(root)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["file"], "a.html")


class TestApplyAndRevert(unittest.TestCase):
    def test_apply_backs_up_then_revert_restores_exact_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "page.html"
            original = CSS
            path.write_text(original, encoding="utf-8")
            findings = [_finding("RTL001", 2, "physical margin-left declaration",
                                 "margin-inline-start: 4px")]
            result = fix_file(path, "page.html", findings, tier="safe")
            backup = apply_fix(path, "page.html", result, root=root)
            self.assertTrue(Path(backup).is_file())
            self.assertNotEqual(path.read_text(encoding="utf-8"), original)
            self.assertIn("margin-inline-start", path.read_text(encoding="utf-8"))
            # journal has exactly one entry describing the change
            entries = journal_load(root)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["file"], "page.html")
            self.assertEqual(entries[0]["rules"], ["RTL001"])
            # revert: exact byte restoration, cleanup, journal cleared
            restored_count, restored = revert_all(root)
            self.assertEqual((restored_count, restored), (1, ["page.html"]))
            self.assertEqual(path.read_text(encoding="utf-8"), original,
                             "revert must restore EXACT bytes")
            self.assertFalse(Path(backup).is_file(), "backup removed after restore")
            self.assertEqual(journal_load(root), [], "journal cleared after revert")
            self.assertFalse((root / BACKUP_DIRNAME / "page.html").exists())

    def test_revert_multiple_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            originals = {}
            for name, content in (("a.html", CSS), ("b.html", "می رود\n")):
                p = root / name
                p.write_text(content, encoding="utf-8")
                originals[name] = content
            findings_a = [_finding("RTL001", 2, "physical margin-left declaration",
                                   "margin-inline-start: 4px")]
            res_a = fix_file(root / "a.html", "a.html", findings_a, tier="safe")
            apply_fix(root / "a.html", "a.html", res_a, root=root)
            res_b = fix_file(root / "b.html", "b.html", [], zwnj=True, lang="fa", tier="safe")
            apply_fix(root / "b.html", "b.html", res_b, root=root)
            restored_count, restored = revert_all(root)
            self.assertEqual(restored_count, 2)
            self.assertEqual(sorted(restored), ["a.html", "b.html"])
            for name, content in originals.items():
                self.assertEqual((root / name).read_text(encoding="utf-8"), content)

    def test_revert_preserves_subdirectory_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            deep = root / "src" / "components"
            deep.mkdir(parents=True)
            original = CSS
            (deep / "card.css").write_text(original, encoding="utf-8")
            findings = [_finding("RTL001", 2, "physical margin-left declaration",
                                 "margin-inline-start: 4px")]
            result = fix_file(deep / "card.css", "src/components/card.css",
                              findings, tier="safe")
            backup = apply_fix(deep / "card.css", "src/components/card.css",
                               result, root=root)
            self.assertEqual(Path(backup).name, "card.css")
            restored_count, restored = revert_all(root)
            self.assertEqual((restored_count, restored), (1, ["src/components/card.css"]))
            self.assertEqual((deep / "card.css").read_text(encoding="utf-8"), original)
            # empty backup subdirectories are cleaned up
            self.assertFalse((root / BACKUP_DIRNAME / "src").exists())

    def test_revert_without_journal_restores_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.assertEqual(revert_all(root), (0, []))

    def test_revert_refuses_backups_without_journal_entry(self):
        # safety policy: backups WITHOUT a journal mapping are never restored
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "page.html"
            path.write_text("current\n", encoding="utf-8")
            bak = root / BACKUP_DIRNAME / "page.html"
            bak.parent.mkdir(parents=True)
            bak.write_text("old original\n", encoding="utf-8")
            restored_count, restored = revert_all(root)
            self.assertEqual((restored_count, restored), (0, []))
            self.assertEqual(path.read_text(encoding="utf-8"), "current\n")

    def test_revert_skips_path_escape_entries(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            victim = Path(td).parent / "outside-target.txt"
            victim.write_text("victim\n", encoding="utf-8")
            jp = root / BACKUP_DIRNAME / JOURNAL_FILENAME
            jp.parent.mkdir(parents=True)
            jp.write_text(json.dumps([
                {"file": "../outside-target.txt", "backup": "outside-target.txt"},
                {"file": "/etc/passwd", "backup": "passwd"},
            ]), encoding="utf-8")
            (root / BACKUP_DIRNAME / "outside-target.txt").write_text("evil\n", encoding="utf-8")
            (root / BACKUP_DIRNAME / "passwd").write_text("evil\n", encoding="utf-8")
            restored_count, restored = revert_all(root)
            self.assertEqual((restored_count, restored), (0, []))
            self.assertEqual(victim.read_text(encoding="utf-8"), "victim\n")
            # journal is consumed by the run (cleared when the backup dir
            # exists) even though nothing was restored — pin that behavior
            self.assertEqual(journal_load(root), [])
            victim.unlink()

    def test_revert_skips_missing_backup_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            journal_append(root, {"file": "gone.html", "backup": "gone.html"})
            restored_count, restored = revert_all(root)
            self.assertEqual((restored_count, restored), (0, []))


class TestCliRevertRoundtrip(unittest.TestCase):
    """End to end: raast fix --apply then raast revert --yes."""

    def test_apply_then_revert_via_cli(self):
        import subprocess
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            target = td_path / "page.html"
            broken = (REPO_ROOT / "tests" / "fixtures" / "broken_page.html").read_text(encoding="utf-8")
            target.write_text(broken, encoding="utf-8")
            # apply fixes
            proc = subprocess.run(
                [sys.executable, "-m", "raast.cli", "fix", str(td_path), "--zwnj", "--apply"],
                capture_output=True, text=True, cwd=REPO_ROOT,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            fixed = target.read_text(encoding="utf-8")
            self.assertNotEqual(fixed, broken)
            self.assertTrue((td_path / ".raast-backup" / "journal.json").is_file())
            # revert
            proc2 = subprocess.run(
                [sys.executable, "-m", "raast.cli", "revert", str(td_path), "--yes"],
                capture_output=True, text=True, cwd=REPO_ROOT,
            )
            self.assertEqual(proc2.returncode, 0, proc2.stderr)
            self.assertIn("restored", proc2.stdout)
            self.assertEqual(target.read_text(encoding="utf-8"), broken,
                             "CLI revert must restore the exact original bytes")
            self.assertEqual(json.loads(
                (td_path / ".raast-backup" / "journal.json").read_text(encoding="utf-8")), [])

    def test_revert_without_journal_and_without_backups(self):
        import subprocess
        with tempfile.TemporaryDirectory() as td:
            proc = subprocess.run(
                [sys.executable, "-m", "raast.cli", "revert", td, "--yes"],
                capture_output=True, text=True, cwd=REPO_ROOT,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertIn("nothing to revert", proc.stdout)


if __name__ == "__main__":
    unittest.main()
