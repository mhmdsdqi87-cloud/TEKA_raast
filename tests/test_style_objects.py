"""RAAST CSS-in-JS style-object tests — camelCase normalization layer.

Style objects (React inline styles, styled-components / Emotion object
syntax) spell properties in camelCase. The engine normalizes property names
to kebab-case before matching, so one rule set covers stylesheets and style
objects. These tests pin the normalization, the detection, the silent
logical twins, the value-boundary behavior inside JS objects, and the
camelCase auto-fix path.

Run: python3 -m unittest discover -s tests -p test_style_objects.py -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from raast.fixer import fix_file  # noqa: E402
from raast.rules import (  # noqa: E402
    RuleContext, _camel_prop, _kebab_prop, rule_css_left_right,
    rule_css_letter_spacing, rule_css_physical, rule_css_text_align, run_rules,
)
from raast.profiles import load_profile  # noqa: E402

# Persian copy arms the evidence gate (CSS rules only fire in files that
# themselves contain RTL-script text).
FA = "افزودن به سبد"

CFG = {"language": "fa", "rules": {}, "include": [], "exclude": [], "fail_on": "P1"}


def _ctx(lang: str = "fa") -> RuleContext:
    return RuleContext(config=dict(CFG, language=lang), profile=load_profile(lang))


class TestPropertyNormalization(unittest.TestCase):
    def test_camel_to_kebab(self):
        self.assertEqual(_kebab_prop("marginLeft"), "margin-left")
        self.assertEqual(_kebab_prop("paddingRight"), "padding-right")
        self.assertEqual(_kebab_prop("textAlign"), "text-align")
        self.assertEqual(_kebab_prop("letterSpacing"), "letter-spacing")

    def test_kebab_passthrough(self):
        self.assertEqual(_kebab_prop("margin-left"), "margin-left")
        self.assertEqual(_kebab_prop("text-align"), "text-align")

    def test_vendor_prefixes_gain_leading_hyphen(self):
        self.assertEqual(_kebab_prop("WebkitTransition"), "-webkit-transition")
        self.assertEqual(_kebab_prop("msTransform"), "-ms-transform")
        self.assertEqual(_kebab_prop("MozAppearance"), "-moz-appearance")
        self.assertEqual(_kebab_prop("OTransition"), "-o-transition")

    def test_lowercase_o_is_not_a_vendor_prefix(self):
        # "Open" is not -pen-anything: the O-prefix requires an uppercase
        # letter right after it.
        self.assertEqual(_kebab_prop("Open"), "open")

    def test_camel_prop(self):
        self.assertEqual(_camel_prop("margin-inline-start"), "marginInlineStart")
        self.assertEqual(_camel_prop("padding-inline-end"), "paddingInlineEnd")
        self.assertEqual(_camel_prop("-webkit-mask-composite"), "WebkitMaskComposite")

    def test_kebab_to_camel_roundtrip(self):
        for name in ("marginLeft", "paddingRight", "WebkitMaskSize"):
            self.assertEqual(_camel_prop(_kebab_prop(name)), name)


class TestDetection(unittest.TestCase):
    def test_camel_margin_left_fires_rtl001(self):
        src = f"const s = {{ marginLeft: 8 }}; // {FA}"
        findings = rule_css_physical("a.tsx", src, CFG)
        self.assertEqual([f.rule for f in findings], ["RTL001"])
        self.assertEqual(findings[0].suggested_fix, "marginInlineStart: 8")

    def test_camel_padding_right_fires_rtl002(self):
        src = f"const box = {{ paddingRight: '1rem' }}; // {FA}"
        findings = rule_css_physical("a.tsx", src, CFG)
        self.assertEqual([f.rule for f in findings], ["RTL002"])
        self.assertEqual(findings[0].suggested_fix, "paddingInlineEnd: '1rem'")

    def test_kebab_css_regression(self):
        src = f".card {{ margin-left: 4px; }} /* {FA} */"
        findings = rule_css_physical("a.css", src, CFG)
        self.assertEqual([f.rule for f in findings], ["RTL001"])
        self.assertEqual(findings[0].suggested_fix, "margin-inline-start: 4px")

    def test_logical_twins_stay_silent(self):
        src = (
            f"const ok1 = {{ marginInlineStart: 8, marginInlineEnd: 8 }}; // {FA}\n"
            f"const ok2 = {{ paddingInlineStart: 4, paddingInlineEnd: 4 }};\n"
        )
        self.assertEqual(rule_css_physical("a.tsx", src, CFG), [])

    def test_camel_text_align_quoted(self):
        src = f"const s = {{ textAlign: 'left' }}; // {FA}"
        findings = rule_css_text_align("a.tsx", src, CFG)
        self.assertEqual([f.rule for f in findings], ["RTL004"])
        self.assertEqual(findings[0].message, "textAlign: left")
        self.assertEqual(findings[0].suggested_fix, "textAlign: 'start'")

    def test_camel_text_align_double_quoted(self):
        src = f'const s = {{ textAlign: "right" }}; // {FA}'
        findings = rule_css_text_align("a.tsx", src, CFG)
        self.assertEqual(findings[0].suggested_fix, 'textAlign: "end"')

    def test_kebab_text_align_regression(self):
        src = f".card {{ text-align: left; }} /* {FA} */"
        findings = rule_css_text_align("a.css", src, CFG)
        self.assertEqual(findings[0].message, "text-align: left")
        self.assertEqual(findings[0].suggested_fix, "text-align: start")

    def test_text_align_start_stays_silent(self):
        src = f"const s = {{ textAlign: 'start', textalign: 'left' }}; // {FA}"
        findings = rule_css_text_align("a.tsx", src, CFG)
        self.assertEqual(findings, [])

    def test_align_value_word_boundary(self):
        # "leftward" is not a left value.
        src = f"const s = {{ textAlign: 'leftward' }}; // {FA}"
        self.assertEqual(rule_css_text_align("a.tsx", src, CFG), [])

    def test_letter_spacing_camel(self):
        src = f"const s = {{ letterSpacing: '2px' }}; // {FA}"
        findings = rule_css_letter_spacing("a.tsx", src, CFG)
        self.assertEqual([f.rule for f in findings], ["RTL005"])

    def test_letter_spacing_zero_stays_silent(self):
        src = f"const s = {{ letterSpacing: 0 }}; // {FA}"
        self.assertEqual(rule_css_letter_spacing("a.tsx", src, CFG), [])

    def test_left_in_style_object_is_review_only(self):
        src = f"const pos = {{ left: 20 }}; // {FA}"
        findings = rule_css_left_right("a.tsx", src, CFG)
        self.assertEqual([f.rule for f in findings], ["RTL003"])
        self.assertFalse(findings[0].fixable)


class TestValueBoundaries(unittest.TestCase):
    def test_js_object_comma_does_not_swallow_next_property(self):
        src = f"const s = {{ marginLeft: 8, color: 'red' }}; // {FA}"
        findings = rule_css_physical("a.tsx", src, CFG)
        self.assertEqual(findings[0].suggested_fix, "marginInlineStart: 8")

    def test_css_function_comma_preserved(self):
        src = f".card {{ margin-left: min(10px, 2vw); }} /* {FA} */"
        findings = rule_css_physical("a.css", src, CFG)
        self.assertEqual(findings[0].suggested_fix, "margin-inline-start: min(10px, 2vw)")

    def test_font_family_comma_preserved_on_non_physical_prop(self):
        # Non-physical declarations never produce findings; this only checks
        # the declaration regex does not crash on multi-value CSS.
        src = f".card {{ font-family: Vazirmatn, sans-serif; }} /* {FA} */"
        self.assertEqual(rule_css_physical("a.css", src, CFG), [])


class TestAutoFix(unittest.TestCase):
    def _fix(self, content: str, suffix: str = ".tsx") -> str:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / f"sample{suffix}"
            p.write_text(content, encoding="utf-8")
            from raast.rules import run_rules as _rr
            findings = _rr(p, p.name, content, _ctx())
            result = fix_file(p, p.name, findings, tier="safe")
            return result.content

    def test_fixer_converts_camel_margin_to_camel_logical(self):
        out = self._fix(f"const s = {{ marginLeft: 8 }}; // {FA}\n")
        self.assertIn("marginInlineStart: 8", out)
        self.assertNotIn("marginLeft", out)

    def test_fixer_keeps_quotes_for_camel_text_align(self):
        out = self._fix(f"const s = {{ textAlign: 'left' }}; // {FA}\n")
        self.assertIn("textAlign: 'start'", out)

    def test_fixer_kebab_css_regression(self):
        out = self._fix(f".card {{ margin-left: 4px; text-align: left; }} /* {FA} */\n", ".css")
        self.assertIn("margin-inline-start: 4px", out)
        self.assertIn("text-align: start", out)

    def test_fixer_removes_camel_letter_spacing(self):
        out = self._fix(f"const s = {{ letterSpacing: '2px', color: 'red' }}; // {FA}\n")
        self.assertNotIn("letterSpacing", out)
        self.assertIn("color: 'red'", out)


class TestSvelteScanning(unittest.TestCase):
    def test_svelte_files_are_scanned_by_run_rules(self):
        src = (
            "<main class=\"panel\">سبد خرید شما</main>\n"
            "<style>\n"
            "  .panel { padding-right: 16px; }\n"
            "  .panel-ok { padding-inline-end: 16px; }\n"
            "</style>\n"
        )
        findings = run_rules(Path("App.svelte"), "App.svelte", src, _ctx())
        self.assertEqual([f.rule for f in findings], ["RTL002"])
        self.assertEqual(findings[0].file, "App.svelte")

    def test_svelte_logical_twin_stays_silent(self):
        src = "<p>سبد خالی</p>\n<style>.ok { padding-inline-end: 16px; }</style>\n"
        self.assertEqual(run_rules(Path("App.svelte"), "App.svelte", src, _ctx()), [])


if __name__ == "__main__":
    unittest.main()
