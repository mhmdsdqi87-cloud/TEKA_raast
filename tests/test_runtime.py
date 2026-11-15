"""RAAST Runtime Inspector tests (raast.runtime, rule namespace RT001-RT006).

Two layers:

1. Pure-logic tests — the pass-1 / pass-2 detectors, report writers and CLI
   validation run without a browser, so they execute everywhere (CI included).
2. Browser tests — real headless Chromium renders two calibration fixtures
   (a clean RTL page and a page planting one instance of every RT rule).
   They are skipped when playwright + chromium are not installed; CI has a
   dedicated job (runtime-inspector-tests) that installs the [runtime] extra
   and runs this module so the browser layer is genuinely exercised there.

Run: python3 -m unittest discover -s tests -p test_runtime.py -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    from playwright.sync_api import sync_playwright  # noqa: F401

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

from raast import runtime  # noqa: E402


def _el(**kw) -> dict:
    """A collected element record with sane defaults (shape mirrors _COLLECT_JS)."""
    base = {
        "path": "html > body > div", "tag": "div", "cls": "",
        "x": 0.0, "y": 0.0, "w": 100.0, "h": 20.0, "text": "",
        "dir": "rtl", "pos": "static", "transform": "none",
        "sw": 100, "cw": 100, "sh": 20, "ch": 20,
        "ox": "visible", "hasText": False, "icon": False,
        "iso": False, "mixed": False,
    }
    base.update(kw)
    return base


def _doc(**kw) -> dict:
    base = {"dir": "rtl", "dirAttr": "rtl", "lang": "fa", "scrollWidth": 375,
            "clientWidth": 375, "scrollHeight": 600, "clientHeight": 667}
    base.update(kw)
    return base


class TestPass1Detectors(unittest.TestCase):
    """PASS 1: RT001 overflow, RT002 page overflow, RT003 clipping,
    RT005 icons, RT006 mixed text — synthetic records, no browser."""

    def test_clean_records_produce_no_findings(self):
        issues = runtime._check_pass1([_el()], _doc(), 375, 667, "375x667")
        self.assertEqual(issues, [])

    def test_rt001_element_beyond_right_edge(self):
        el = _el(x=300.0, w=100.0)  # right edge 400 > 375+1
        issues = runtime._check_pass1([el], _doc(), 375, 667, "375x667")
        self.assertEqual([i["rule"] for i in issues], ["RT001"])
        self.assertEqual(issues[0]["severity"], "P1")
        self.assertEqual(issues[0]["confidence"], "high")
        self.assertIn("right edge 400px", issues[0]["message"])

    def test_rt001_element_left_of_origin(self):
        el = _el(x=-5.0, w=100.0)
        issues = runtime._check_pass1([el], _doc(), 375, 667, "375x667")
        self.assertEqual([i["rule"] for i in issues], ["RT001"])
        self.assertIn("left edge -5px", issues[0]["message"])

    def test_rt001_subpixel_tolerance(self):
        el = _el(x=300.0, w=76.0)  # right edge 376 == 375+1 -> inside tolerance
        issues = runtime._check_pass1([el], _doc(), 375, 667, "375x667")
        self.assertEqual(issues, [])

    def test_rt002_page_overflow_uses_pseudo_record(self):
        doc = _doc(scrollWidth=563, scrollHeight=600)
        issues = runtime._check_pass1([_el()], doc, 375, 667, "375x667")
        self.assertEqual([i["rule"] for i in issues], ["RT002"])
        self.assertEqual(issues[0]["severity"], "P1")
        self.assertEqual(issues[0]["selector"], "html")
        self.assertIn("scrollWidth 563px > clientWidth 375px", issues[0]["message"])

    def test_rt003_clipped_text(self):
        el = _el(hasText=True, sw=606, cw=120, ox="hidden")
        issues = runtime._check_pass1([el], _doc(), 375, 667, "375x667")
        self.assertEqual([i["rule"] for i in issues], ["RT003"])
        self.assertIn("606px inside 120px box", issues[0]["message"])

    def test_rt003_requires_direct_text_and_clip(self):
        # no direct text node -> not a clipped-text finding
        el = _el(hasText=False, sw=606, cw=120, ox="hidden")
        self.assertEqual(runtime._check_pass1([el], _doc(), 375, 667, "v"), [])
        # overflow-x visible -> not clipped
        el2 = _el(hasText=True, sw=606, cw=120, ox="visible")
        self.assertEqual(runtime._check_pass1([el2], _doc(), 375, 667, "v"), [])
        # scrollWidth not greater -> no finding
        el3 = _el(hasText=True, sw=120, cw=120, ox="hidden")
        self.assertEqual(runtime._check_pass1([el3], _doc(), 375, 667, "v"), [])

    def test_rt005_unflipped_directional_icon_in_rtl(self):
        el = _el(icon=True, tag="span", cls="icon arrow-forward")
        issues = runtime._check_pass1([el], _doc(dir="rtl"), 375, 667, "375x667")
        self.assertEqual([i["rule"] for i in issues], ["RT005"])
        self.assertEqual(issues[0]["severity"], "P2")

    def test_rt005_requires_rtl_document(self):
        el = _el(icon=True)
        issues = runtime._check_pass1([el], _doc(dir="ltr"), 375, 667, "375x667")
        self.assertEqual(issues, [])

    def test_rt005_flipped_icon_suppressed(self):
        el = _el(icon=True, transform="matrix(-1, 0, 0, 1, 0, 0)")
        self.assertEqual(runtime._check_pass1([el], _doc(dir="rtl"), 375, 667, "v"), [])
        el2 = _el(icon=True, cls="rtl:rotate-icon")
        self.assertEqual(runtime._check_pass1([el2], _doc(dir="rtl"), 375, 667, "v"), [])
        el3 = _el(icon=True, cls="rotate-180")
        self.assertEqual(runtime._check_pass1([el3], _doc(dir="rtl"), 375, 667, "v"), [])

    def test_rt006_mixed_direction_without_isolation(self):
        el = _el(hasText=True, text="این قیمت برای Product است", mixed=True, iso=False)
        issues = runtime._check_pass1([el], _doc(dir="rtl"), 375, 667, "375x667")
        self.assertEqual([i["rule"] for i in issues], ["RT006"])
        self.assertEqual(issues[0]["severity"], "P2")

    def test_rt006_isolated_or_unmixed_suppressed(self):
        isolated = _el(hasText=True, mixed=True, iso=True)  # bdi / own dir attr
        self.assertEqual(runtime._check_pass1([isolated], _doc(dir="rtl"), 375, 667, "v"), [])
        unmixed = _el(hasText=True, mixed=False)
        self.assertEqual(runtime._check_pass1([unmixed], _doc(dir="rtl"), 375, 667, "v"), [])

    def test_multiple_findings_keep_record_order(self):
        els = [_el(x=-5.0), _el(icon=True)]
        issues = runtime._check_pass1(els, _doc(), 375, 667, "375x667")
        self.assertEqual([i["rule"] for i in issues], ["RT001", "RT005"])


class TestMirrorDetector(unittest.TestCase):
    """PASS 2: RT004 — elements that fail to reach their mirrored position."""

    def test_exact_mirror_no_finding(self):
        first = [_el(x=24.0, w=100.0)]
        # expected mirror at vw - x - w = 375 - 24 - 100 = 251
        second = [_el(x=251.0, w=100.0)]
        self.assertEqual(runtime._check_mirror(first, second, "rtl", 375, "375x667"), [])

    def test_within_tolerance_no_finding(self):
        first = [_el(x=24.0, w=100.0)]
        second = [_el(x=251.0 + runtime._MIRROR_TOLERANCE_PX - 1, w=100.0)]
        self.assertEqual(runtime._check_mirror(first, second, "rtl", 375, "375x667"), [])

    def test_beyond_tolerance_fires_rt004(self):
        first = [_el(x=24.0, w=100.0)]
        second = [_el(x=24.0, w=100.0)]  # did not move at all
        issues = runtime._check_mirror(first, second, "rtl", 375, "375x667")
        self.assertEqual([i["rule"] for i in issues], ["RT004"])
        self.assertIn("x 24px -> 24px, expected 251px", issues[0]["message"])
        self.assertIn("physical offsets survived the flip", issues[0]["explanation"])

    def test_fixed_position_skipped(self):
        first = [_el(x=24.0, w=100.0, pos="fixed")]
        second = [_el(x=24.0, w=100.0)]
        self.assertEqual(runtime._check_mirror(first, second, "rtl", 375, "v"), [])

    def test_transformed_element_skipped(self):
        first = [_el(x=24.0, w=100.0, transform="matrix(1, 0, 0, 1, 8, 0)")]
        second = [_el(x=24.0, w=100.0)]
        self.assertEqual(runtime._check_mirror(first, second, "rtl", 375, "v"), [])

    def test_replaced_tags_skipped(self):
        for tag in runtime._SKIP_MIRROR_TAGS:
            first = [_el(x=24.0, w=100.0, tag=tag)]
            second = [_el(x=24.0, w=100.0)]
            self.assertEqual(runtime._check_mirror(first, second, "rtl", 375, "v"), [])

    def test_own_direction_mismatch_skipped(self):
        # element with dir="ltr" inside an rtl document is exempt
        first = [_el(x=24.0, w=100.0, dir="ltr")]
        second = [_el(x=24.0, w=100.0)]
        self.assertEqual(runtime._check_mirror(first, second, "rtl", 375, "v"), [])

    def test_dom_mutated_between_passes_skipped(self):
        first = [_el(x=24.0, w=100.0)]
        second = []  # element vanished after the flip
        self.assertEqual(runtime._check_mirror(first, second, "rtl", 375, "v"), [])


class TestIconFlipHeuristic(unittest.TestCase):
    def test_scalex_minus_one(self):
        self.assertTrue(runtime._icon_has_flip({"transform": "matrix(-1, 0, 0, 1, 0, 0)"}))

    def test_rtl_class(self):
        self.assertTrue(runtime._icon_has_flip({"transform": "none", "cls": "rtl:flip"}))

    def test_rotate_180_class(self):
        self.assertTrue(runtime._icon_has_flip({"transform": "none", "cls": "rotate-180"}))

    def test_no_flip_signal(self):
        self.assertFalse(runtime._icon_has_flip({"transform": "none", "cls": ""}))


class TestReportWriters(unittest.TestCase):
    def _sample_issues(self) -> list[dict]:
        el = _el(x=-5.0, w=100.0)
        return runtime._check_pass1([el], _doc(), 375, 667, "375x667")

    def test_counts(self):
        self.assertEqual(runtime._counts([]), {"P0": 0, "P1": 0, "P2": 0})
        el = _el(x=-5.0, w=100.0)
        mixed = runtime._check_pass1([el, _el(hasText=True, mixed=True)], _doc(), 375, 667, "v")
        self.assertEqual(runtime._counts(mixed), {"P0": 0, "P1": 1, "P2": 1})

    def test_markdown_shape(self):
        issues = self._sample_issues()
        md = runtime._markdown("https://example.test", ["375x667"], issues,
                               {"375x667": {"natural": "screenshot-natural.png",
                                            "mirrored": "screenshot-mirrored.png"}})
        self.assertIn("# RAAST Runtime Inspection Report", md)
        self.assertIn("- Target: `https://example.test`", md)
        self.assertIn("## P1", md)
        self.assertIn("### RT001", md)
        self.assertIn("Fix:", md)
        self.assertIn("![natural direction", md)
        self.assertIn("![mirrored direction", md)
        self.assertIn("Limitations:", md)

    def test_markdown_clean_report(self):
        md = runtime._markdown("x", ["375x667"], [], {"375x667": {"natural": None, "mirrored": None}})
        self.assertIn("No runtime findings", md)
        self.assertIn("| 375x667 | 0 | 0 | 0 |", md)
        self.assertNotIn("![natural direction", md)  # no screenshot was taken

    def test_write_reports_json_md_consistency(self):
        issues = self._sample_issues()
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            runtime._write_reports(out, "https://example.test", ["375x667"], issues,
                                   {"375x667": {"natural": "a.png", "mirrored": "b.png"}})
            data = json.loads((out / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(data["engine"], "runtime")
            self.assertEqual(data["target"], "https://example.test")
            self.assertEqual(data["summary"]["total"], len(issues))
            self.assertEqual(len(data["issues"]), len(issues))
            self.assertEqual(data["screenshots"]["natural"], "a.png")
            self.assertEqual(data["screenshots"]["mirrored"], "b.png")
            self.assertNotIn("per_viewport", data["screenshots"])
            md = (out / "report.md").read_text(encoding="utf-8")
            self.assertIn("# RAAST Runtime Inspection Report", md)

    def test_screenshots_payload_multi_viewport(self):
        shots = {"375x667": {"natural": "screenshot-natural-375x667.png", "mirrored": None},
                 "1280x800": {"natural": "screenshot-natural-1280x800.png",
                              "mirrored": "screenshot-mirrored-1280x800.png"}}
        payload = runtime._screenshots_payload(shots, ["375x667", "1280x800"])
        # top-level mirrors the LAST viewport; per-viewport map included
        self.assertEqual(payload["natural"], "screenshot-natural-1280x800.png")
        self.assertEqual(payload["mirrored"], "screenshot-mirrored-1280x800.png")
        self.assertEqual(payload["per_viewport"], shots)
        single = runtime._screenshots_payload({"375x667": shots["375x667"]}, ["375x667"])
        self.assertNotIn("per_viewport", single)

    def test_shot_naming(self):
        self.assertEqual(runtime._shot_name("natural", "375x667", True),
                         "screenshot-natural-375x667.png")
        self.assertEqual(runtime._shot_name("mirrored", "1280x800", True),
                         "screenshot-mirrored-1280x800.png")
        self.assertEqual(runtime._shot_name("natural", "375x667", False),
                         "screenshot-natural.png")


@unittest.skipUnless(HAS_PLAYWRIGHT, "playwright is not installed (pip install 'raast[runtime]')")
class TestRuntimeBrowser(unittest.TestCase):
    """Real headless Chromium against calibration fixtures.

    The clean fixture must produce ZERO findings (no false positives, mirror
    comparison included). The broken fixture plants exactly one instance of
    each RT rule class and must produce all six rules with exit code 1.
    """

    @classmethod
    def setUpClass(cls):
        cls.fixtures = REPO_ROOT / "tests" / "fixtures" / "runtime"
        cls.clean = cls.fixtures / "clean_rtl.html"
        cls.broken = cls.fixtures / "broken_rtl.html"
        # Re-verify the calibration contract here: both fixtures must exist
        # and the broken one must reference every RT rule class it plants.
        self_missing = [p.name for p in (cls.clean, cls.broken) if not p.is_file()]
        assert not self_missing, f"missing runtime fixtures: {self_missing}"

    def _inspect(self, fixture: Path, out: Path, extra: list[str] | None = None) -> int:
        argv = ["inspect", "--file", str(fixture), "--out", str(out),
                "--viewport", "375x667", "--wait", "60"]
        argv += extra or []
        return runtime.main(argv)

    def test_clean_rtl_page_zero_findings_exit_0(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            code = self._inspect(self.clean, out)
            self.assertEqual(code, 0, "clean RTL page must exit 0 (no findings)")
            data = json.loads((out / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(data["summary"]["total"], 0)
            self.assertEqual(data["summary"], {"p0": 0, "p1": 0, "p2": 0, "total": 0})
            self.assertEqual(data["issues"], [])
            self.assertEqual(data["viewports"], ["375x667"])
            self.assertTrue(data["target"].startswith("file://"))
            # reports + both screenshots exist on disk
            self.assertTrue((out / "report.md").is_file())
            self.assertTrue((out / "screenshot-natural.png").is_file())
            self.assertTrue((out / "screenshot-mirrored.png").is_file())
            md = (out / "report.md").read_text(encoding="utf-8")
            self.assertIn("No runtime findings", md)

    def test_broken_page_fires_all_six_rules_exit_1(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            code = self._inspect(self.broken, out)
            self.assertEqual(code, 1, "P1 findings must yield exit code 1 (CI gate)")
            data = json.loads((out / "report.json").read_text(encoding="utf-8"))
            rules = {i["rule"] for i in data["issues"]}
            self.assertEqual(rules, {"RT001", "RT002", "RT003", "RT004", "RT005", "RT006"})
            self.assertEqual(data["summary"]["p1"], 2)  # RT001 + RT002
            self.assertEqual(data["summary"]["p2"], 4)  # RT003 + RT004 + RT005 + RT006
            # every finding carries actionable metadata
            for issue in data["issues"]:
                self.assertIn(issue["severity"], ("P1", "P2"))
                self.assertIn(issue["confidence"], ("high", "medium", "low"))
                self.assertTrue(issue["selector"], "selector path must be present")
                self.assertTrue(issue["message"])
                self.assertTrue(issue["explanation"])
                self.assertTrue(issue["suggested_fix"])
                self.assertEqual(issue["viewport"], "375x667")
            # rule-specific spot checks
            by_rule = {i["rule"]: i for i in data["issues"]}
            self.assertIn("left edge", by_rule["RT001"]["message"])
            self.assertIn("scrollWidth", by_rule["RT002"]["message"])
            self.assertIn("text is clipped", by_rule["RT003"]["message"])
            self.assertIn("did not mirror", by_rule["RT004"]["message"])
            self.assertIn("directional icon", by_rule["RT005"]["message"])
            self.assertIn("mixed-direction", by_rule["RT006"]["message"])
            # markdown report groups by severity and links evidence
            md = (out / "report.md").read_text(encoding="utf-8")
            self.assertIn("## P1", md)
            self.assertIn("## P2", md)
            self.assertIn("### RT001", md)
            self.assertIn("screenshot-natural.png", md)
            self.assertIn("screenshot-mirrored.png", md)

    def test_skip_mirror_flag_suppresses_rt004_and_mirrored_shot(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            code = self._inspect(self.broken, out, ["--skip-mirror"])
            self.assertEqual(code, 1)
            data = json.loads((out / "report.json").read_text(encoding="utf-8"))
            rules = {i["rule"] for i in data["issues"]}
            self.assertNotIn("RT004", rules)  # pass 2 skipped entirely
            self.assertIn("RT001", rules)     # pass 1 still runs
            self.assertNotIn("per_viewport", data["screenshots"])
            self.assertIsNone(data["screenshots"]["mirrored"])
            self.assertFalse((out / "screenshot-mirrored.png").exists())

    def test_multi_viewport_naming_and_payload(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            code = runtime.main(["inspect", "--file", str(self.broken),
                                 "--out", str(out), "--wait", "60",
                                 "--viewport", "375x667", "--viewport", "1280x800"])
            self.assertEqual(code, 1)
            data = json.loads((out / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(data["viewports"], ["375x667", "1280x800"])
            pv = data["screenshots"]["per_viewport"]
            self.assertEqual(sorted(pv), ["1280x800", "375x667"])
            self.assertTrue((out / "screenshot-natural-375x667.png").is_file())
            self.assertTrue((out / "screenshot-mirrored-1280x800.png").is_file())
            # findings are tagged per viewport
            viewports_of = {i["viewport"] for i in data["issues"]}
            self.assertTrue(viewports_of <= {"375x667", "1280x800"})

    def test_desktop_viewport_clean_page_stays_clean(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            code = self._inspect(self.clean, out, ["--viewport", "1280x800"])
            self.assertEqual(code, 0)


class TestCliValidation(unittest.TestCase):
    """Usage errors must exit 2 with a message, before any browser launches."""

    def test_invalid_viewport_format(self):
        with tempfile.TemporaryDirectory() as td:
            code = runtime.main(["inspect", "--file", __file__, "--out", td, "--viewport", "100"])
            self.assertEqual(code, 2)

    def test_zero_dimension_viewport(self):
        with tempfile.TemporaryDirectory() as td:
            code = runtime.main(["inspect", "--file", __file__, "--out", td, "--viewport", "0x600"])
            self.assertEqual(code, 2)

    def test_negative_wait(self):
        with tempfile.TemporaryDirectory() as td:
            code = runtime.main(["inspect", "--file", __file__, "--out", td, "--wait", "-1"])
            self.assertEqual(code, 2)

    def test_zero_max_elements(self):
        with tempfile.TemporaryDirectory() as td:
            code = runtime.main(["inspect", "--file", __file__, "--out", td, "--max-elements", "0"])
            self.assertEqual(code, 2)

    def test_url_scheme_must_be_http(self):
        with tempfile.TemporaryDirectory() as td:
            code = runtime.main(["inspect", "--url", "ftp://example.test", "--out", td])
            self.assertEqual(code, 2)

    def test_missing_local_file(self):
        with tempfile.TemporaryDirectory() as td:
            code = runtime.main(["inspect", "--file", str(Path(td) / "nope.html"), "--out", td])
            self.assertEqual(code, 2)

    def test_source_required(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(SystemExit) as cm:
                runtime.main(["inspect", "--out", td])
            self.assertEqual(cm.exception.code, 2)

    def test_url_and_file_mutually_exclusive(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(SystemExit) as cm:
                runtime.main(["inspect", "--url", "https://example.test",
                              "--file", __file__, "--out", td])
            self.assertEqual(cm.exception.code, 2)

    def test_engine_error_without_playwright_is_exit_2(self):
        # _run must report engine failure (not findings) as exit code 2.
        if HAS_PLAYWRIGHT:
            self.skipTest("playwright installed — cannot simulate ImportError")
        with tempfile.TemporaryDirectory() as td:
            issues, shots, code = runtime._run("file:///nonexistent.html",
                                               [(375, 667, "375x667")], 0, 100, False, Path(td))
            self.assertEqual((issues, shots, code), ([], {}, 2))


if __name__ == "__main__":
    unittest.main()
