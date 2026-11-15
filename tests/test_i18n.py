"""RAAST Language Quality Gate tests (raast.i18n, rule namespace LQG001-009).

Full rule coverage plus the supporting machinery: locale flattening,
placeholder extraction with masking, discovery layouts (flat + subdirs),
renderers, and CLI exit codes (0 clean / 1 gate / 2 usage).

Run: python3 -m unittest discover -s tests -p test_i18n.py -v
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from raast import i18n  # noqa: E402
from raast.i18n import (  # noqa: E402
    I18nFinding,
    ScanResult,
    discover_locales,
    extract_placeholders,
    flatten,
    main,
    render_json,
    render_markdown,
    render_text,
    scan_locales,
)

ZWNJ = "\u200c"
NIQQUD = "\u05b0"  # sheva — inside the U+0591-U+05C7 range
ARABIC_YEH = "\u064a"
ARABIC_KAF = "\u0643"


def _rules(findings: list[I18nFinding]) -> set[str]:
    return {f.rule for f in findings}


def _one(findings: list[I18nFinding], rule: str) -> I18nFinding:
    matches = [f for f in findings if f.rule == rule]
    assert matches, f"expected a {rule} finding, got {[f.rule for f in findings]}"
    return matches[0]


class TestFlatten(unittest.TestCase):
    def test_nested_objects_to_dot_paths(self):
        self.assertEqual(flatten({"a": {"b": {"c": "x"}}}), {"a.b.c": "x"})

    def test_scalar_top_level(self):
        self.assertEqual(flatten({"k": "v"}), {"k": "v"})

    def test_null_becomes_empty_string(self):
        self.assertEqual(flatten({"k": None}), {"k": ""})

    def test_arrays_collapse_to_joined_leaf(self):
        self.assertEqual(flatten({"list": ["a", "b"]}), {"list": "a | b"})

    def test_array_of_objects_json_encoded(self):
        self.assertEqual(flatten({"list": [{"x": 1}]}), {"list": '{"x":1}'})

    def test_numbers_and_bools_compact_json(self):
        self.assertEqual(flatten({"n": 5, "b": True}), {"n": "5", "b": "true"})


class TestPlaceholderExtraction(unittest.TestCase):
    def test_named_brace(self):
        tokens, masked = extract_placeholders("Hello {name}!")
        self.assertEqual(tokens, ["{name}"])
        self.assertNotIn("{", masked)
        self.assertNotIn("}", masked)
        self.assertEqual(len(masked), len("Hello {name}!"))  # length preserved

    def test_positional_brace(self):
        self.assertEqual(extract_placeholders("{0} item")[0], ["{0}"])

    def test_handlebars_double_brace(self):
        tokens, _ = extract_placeholders("Hi {{name}}")
        self.assertEqual(tokens, ["{{name}}"])

    def test_double_brace_takes_priority_over_inner_single(self):
        tokens, _ = extract_placeholders("Hi {{name}}")
        self.assertEqual(tokens, ["{{name}}"])
        self.assertNotIn("{name}", tokens)

    def test_printf_styles(self):
        tokens, _ = extract_placeholders("%s items, %d total, %1$s first")
        self.assertEqual(tokens, ["%s", "%d", "%1$s"])

    def test_mixed_syntax(self):
        # tokens are collected per pattern pass (handlebars, brace, printf),
        # not by position — pin that contract explicitly
        tokens, _ = extract_placeholders("{user} has {{count}} %s")
        self.assertEqual(tokens, ["{{count}}", "{user}", "%s"])
        self.assertEqual(sorted(tokens), ["%s", "{user}", "{{count}}"])

    def test_no_placeholders(self):
        tokens, masked = extract_placeholders("plain text")
        self.assertEqual(tokens, [])
        self.assertEqual(masked, "plain text")


class TestScanRules(unittest.TestCase):
    """scan_locales over in-memory locale maps — one rule per test.

    The helper mirrors keys across source and target automatically: when
    no explicit `en` map is given, the source gets the FIRST target's keys
    with distinct placeholder-English values, so only the planted issue
    under test can fire.
    """

    def _scan(self, targets=("fa",), en=None, **locales) -> ScanResult:
        if en is None:
            first = locales.get(targets[0], {}) if targets else {}
            en = {k: f"Source text {k}" for k in first}
        data = {"en": en, **locales}
        return scan_locales(data, "en", list(targets))

    def test_lqg001_missing_key(self):
        result = self._scan(fa={"other": "مقدار"}, en={"greeting": "Hello"})
        f = _one(result.findings, "LQG001")
        self.assertEqual(f.severity, "P1")
        self.assertEqual(f.locale, "fa")
        self.assertEqual(f.key, "greeting")
        self.assertIn("missing in fa", f.message)
        self.assertIn("Add the key to fa", f.suggested_fix)

    def test_lqg002_empty_value(self):
        for value in ("", "   "):
            result = self._scan(fa={"greeting": value})
            f = _one(result.findings, "LQG002")
            self.assertEqual(f.severity, "P1")
            self.assertIn("empty", f.message)

    def test_lqg003_missing_and_extra_placeholders(self):
        result = self._scan(en={"greet": "Hi {name}, you have {count} messages"},
                            fa={"greet": "سلام {name}"})
        f = _one(result.findings, "LQG003")
        self.assertEqual(f.severity, "P1")
        self.assertIn("missing in fa: {count}", f.message)
        result2 = self._scan(en={"greet": "Hi"},
                             fa={"greet": "سلام {extra}"})
        self.assertIn("unexpected in fa: {extra}", _one(result2.findings, "LQG003").message)

    def test_lqg003_placeholder_order_and_multiplicity_ignored(self):
        # same token set in a different order / repeated -> NO finding
        result = self._scan(en={"greet": "{a} and {b}"},
                            fa={"greet": "{b} و {a}"})
        self.assertEqual(_rules(result.findings), set())

    def test_lqg004_untranslated_prose(self):
        result = self._scan(fa={"settings.language": "Language"},
                            en={"settings.language": "Language"})
        f = _one(result.findings, "LQG004")
        self.assertEqual(f.severity, "P2")
        self.assertIn("identical to the en source", f.message)

    def test_lqg004_url_identical_is_legitimate(self):
        url = "https://example.test/help"
        result = self._scan(fa={"docs.link": url}, en={"docs.link": url})
        self.assertEqual(_rules(result.findings), set())

    def test_lqg004_tech_atom_identical_is_legitimate(self):
        atom = "api/v2/users"
        result = self._scan(fa={"api.path": atom}, en={"api.path": atom})
        self.assertEqual(_rules(result.findings), set())

    def test_lqg004_short_or_number_only_identical_is_legitimate(self):
        result = self._scan(fa={"count": "42", "sym": "OK"},
                            en={"count": "42", "sym": "OK"})
        # identical short/numeric values must NOT be flagged as untranslated
        # (LQG004); other rules may still comment on the value itself
        self.assertNotIn("LQG004", _rules(result.findings))

    def test_lqg005_too_long_translation(self):
        result = self._scan(en={"btn": "New"},
                            fa={"btn": "دکمه " * 40})
        f = _one(result.findings, "LQG005")
        self.assertEqual(f.severity, "P2")
        self.assertIn("x the source length", f.message)

    def test_lqg005_too_short_translation(self):
        result = self._scan(en={"desc": "This is a long description field for testing"},
                            fa={"desc": "ک"})
        self.assertIn("LQG005", _rules(result.findings))

    def test_lqg005_reasonable_translation_no_finding(self):
        result = self._scan(en={"desc": "This is a long description field for testing"},
                            fa={"desc": "این یک توضیح نسبتا طولانی برای آزمایش است"})
        self.assertEqual(_rules(result.findings), set())

    def test_lqg006_western_digits_and_latin_punctuation_in_fa_prose(self):
        result = self._scan(fa={"msg": "خطا 5 رخ داد, دوباره تلاش کنید?"})
        f = _one(result.findings, "LQG006")
        self.assertEqual(f.severity, "P2")
        self.assertIn("Western digit(s) 5", f.message)
        self.assertIn("Latin punctuation", f.message)

    def test_lqg006_arabic_punctuation_clean(self):
        result = self._scan(fa={"msg": "خطا رخ داد، دوباره تلاش کنید؟"})
        self.assertEqual(_rules(result.findings), set())

    def test_lqg006_he_es_exempt(self):
        he = self._scan(he={"msg": "Error 5 happened, retry?"}, targets=("he",))
        es = self._scan(es={"msg": "Error 5 happened, retry?"}, targets=("es",))
        for r in (he, es):
            self.assertNotIn("LQG006", _rules(r.findings))

    def test_lqg006_placeholders_and_urls_masked(self):
        result = self._scan(
            en={"msg": "{count} found at https://example.test/x?a=1,b=2 now"},
            fa={"msg": "{count} مورد در https://example.test/x?a=1,b=2 یافت شد"})
        self.assertEqual(_rules(result.findings), set())

    def test_lqg006_number_comma_masked(self):
        # the comma inside 1,500 is masked (no "Latin punctuation" finding),
        # but the surrounding Western digit runs are still reported — Persian
        # prose must use Persian digits regardless
        result = self._scan(fa={"msg": "قیمت 1,500 تومان است"},
                            en={"msg": "Price is 1500 tomans"})
        lqg = [f for f in result.findings if f.rule == "LQG006"]
        self.assertEqual(len(lqg), 1)
        self.assertIn("Western digit(s) 1 500", lqg[0].message)
        self.assertNotIn("Latin punctuation", lqg[0].message)

    def test_lqg007_unisolated_latin_run_in_rtl_value(self):
        result = self._scan(fa={"cta": "تماس با Support برای راهنما"})
        f = _one(result.findings, "LQG007")
        self.assertEqual(f.severity, "P2")
        self.assertIn("Support", f.message)

    def test_lqg007_isolated_run_clean(self):
        isolated = "تماس با \u2066Support\u2069 برای راهنما"
        self.assertNotIn("LQG007",
                         _rules(self._scan(fa={"cta": isolated}).findings))
        bdi = "تماس با <bdi>Support</bdi> برای راهنما"
        self.assertNotIn("LQG007",
                         _rules(self._scan(fa={"cta": bdi}).findings))

    def test_lqg007_short_latin_runs_ignored(self):
        result = self._scan(fa={"cta": "نسخه v2 آماده است"})
        self.assertNotIn("LQG007", _rules(result.findings))

    def test_lqg008_arabic_yeh_kaf_in_persian(self):
        result = self._scan(fa={"save": f"ذخیره {ARABIC_KAF}نيد"})
        f = _one(result.findings, "LQG008")
        self.assertEqual(f.severity, "P1")
        self.assertIn("U+0643", f.message)
        self.assertIn("Persian uses", f.message)

    def test_lqg008_arabic_yeh(self):
        result = self._scan(fa={"verb": f"{ARABIC_YEH}د"})
        self.assertIn("U+064A", _one(result.findings, "LQG008").message)

    def test_lqg008_ar_target_not_flagged(self):
        result = self._scan(ar={"save": f"حفظ {ARABIC_KAF}نده"}, targets=("ar",))
        self.assertEqual(_rules(result.findings), set())

    def test_lqg009_niqqud_opt_in(self):
        he_locales = {"en": {"hi": "Hi"}, "he": {"hi": f"ש{NIQQUD}לום"}}
        without = scan_locales(he_locales, "en", ["he"], hebrew_diacritics=False)
        self.assertEqual(_rules(without.findings), set())
        with_ = scan_locales(he_locales, "en", ["he"], hebrew_diacritics=True)
        f = _one(with_.findings, "LQG009")
        self.assertEqual(f.severity, "P2")
        self.assertIn("niqqud", f.message)

    def test_keys_checked_counts_every_comparison(self):
        result = scan_locales({"en": {"a": "1", "b": "2", "c": "3"},
                               "fa": {"a": "۱"}, "ar": {}}, "en", ["fa", "ar"])
        self.assertEqual(result.keys_checked, 6)
        self.assertEqual(result.source_keys, 3)

    def test_severity_summary_counts(self):
        result = self._scan(fa={}, en={"greeting": "Hello"})
        counts = result.counts
        self.assertEqual(counts["P1"], 1)  # LQG001
        self.assertEqual(counts["P0"], 0)
        self.assertEqual(counts["P2"], 0)


class TestDiscovery(unittest.TestCase):
    def test_flat_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "en.json").write_text('{"a": "1"}', encoding="utf-8")
            (root / "fa.json").write_text('{"a": "۱"}', encoding="utf-8")
            (root / "notes.txt").write_text("ignored", encoding="utf-8")
            locales = discover_locales(root)
            self.assertEqual(sorted(locales), ["en", "fa"])
            self.assertEqual(locales["fa"]["a"], "۱")

    def test_subdirectory_layout_merged_in_filename_order(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "fa"
            root.mkdir()
            (root / "a-common.json").write_text('{"x": "1"}', encoding="utf-8")
            (root / "b-page.json").write_text('{"x": "2", "y": "3"}', encoding="utf-8")
            locales = discover_locales(root.parent)
            self.assertEqual(locales["fa"], {"x": "2", "y": "3"})  # later file wins

    def test_hidden_entries_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".hidden.json").write_text('{"a": "1"}', encoding="utf-8")
            (root / "en.json").write_text('{"a": "1"}', encoding="utf-8")
            self.assertEqual(sorted(discover_locales(root)), ["en"])

    def test_subdirectory_wins_over_flat_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "fa.json").write_text('{"a": "flat"}', encoding="utf-8")
            sub = root / "fa"
            sub.mkdir()
            (sub / "main.json").write_text('{"a": "subdir"}', encoding="utf-8")
            self.assertEqual(discover_locales(root)["fa"]["a"], "subdir")

    def test_bom_tolerated(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "en.json").write_bytes(b'\xef\xbb\xbf{"a": "1"}')
            self.assertEqual(discover_locales(root)["en"]["a"], "1")


class TestRenderers(unittest.TestCase):
    def _result(self) -> ScanResult:
        result = scan_locales({"en": {"hi": "Hello"}, "fa": {}}, "en", ["fa"])
        result.warnings = ["target locale 'de' not found"]
        return result

    def test_text_renderer(self):
        text = render_text(self._result(), Path("/tmp/locales"))
        self.assertIn("== fa ==", text)
        self.assertIn("LQG001 P1 [fa] hi", text)
        self.assertIn("1 locale(s), 1 keys checked, 1 findings", text)
        self.assertIn("(P0:0 P1:1 P2:0)", text)

    def test_json_renderer_shape(self):
        data = json.loads(render_json(self._result()))
        self.assertEqual(data["tool"], "raast-i18n")
        self.assertEqual(data["source"], "en")
        self.assertEqual(data["locales"], ["fa"])
        self.assertEqual(data["summary"]["findings"], 1)
        self.assertEqual(data["summary"]["by_severity"]["P1"], 1)
        self.assertEqual(data["findings"][0]["rule"], "LQG001")
        self.assertIn("target locale 'de' not found", data["warnings"][0])

    def test_markdown_renderer_shape(self):
        md = render_markdown(self._result(), Path("/tmp/locales"))
        self.assertIn("# RAAST Language Quality Gate", md)
        self.assertIn("| Rule | Key | Sev | Issue | Fix |", md)
        self.assertIn("| LQG001 | `hi` | P1 |", md)
        self.assertIn("> warning: target locale 'de' not found", md)
        self.assertIn("they complement the page-level host checks", md)

    def test_finding_as_dict(self):
        f = _one(self._result().findings, "LQG001")
        d = f.as_dict()
        for key in ("rule", "severity", "confidence", "locale", "key",
                    "message", "explanation", "suggested_fix"):
            self.assertIn(key, d)


class TestCli(unittest.TestCase):
    def _write_locales(self, root: Path, en: dict, fa: dict):
        root.mkdir(parents=True)
        (root / "en.json").write_text(json.dumps(en, ensure_ascii=False), encoding="utf-8")
        (root / "fa.json").write_text(json.dumps(fa, ensure_ascii=False), encoding="utf-8")

    def test_clean_scan_exits_0(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "locales"
            self._write_locales(root,
                                {"hi": "Hello", "n": "5 items"},
                                {"hi": "سلام", "n": "۵ مورد"})
            code, out, err = self._run(["scan", "--locales", str(root)])
            self.assertEqual(code, 0, err)
            self.assertIn("no findings", out)

    def test_gate_exits_1_when_p1_exceeds_max_errors(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "locales"
            self._write_locales(root, {"hi": "Hello"}, {})  # LQG001
            code, _out, _err = self._run(["scan", "--locales", str(root), "--max-errors", "0"])
            self.assertEqual(code, 1)
            # a laxer max-errors lets the same scan pass the gate
            code2, _out2, _err2 = self._run(["scan", "--locales", str(root), "--max-errors", "5"])
            self.assertEqual(code2, 0)

    def test_usage_error_bad_directory(self):
        code, _out, err = self._run(["scan", "--locales", "/no/such/dir"])
        self.assertEqual(code, 2)
        self.assertIn("not a directory", err)

    def test_usage_error_missing_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "locales"
            self._write_locales(root, {"hi": "Hello"}, {"hi": "سلام"})
            code, _out, err = self._run(["scan", "--locales", str(root), "--source", "de"])
            self.assertEqual(code, 2)
            self.assertIn("not found", err)

    def test_usage_error_invalid_json_names_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "locales"
            root.mkdir()
            (root / "en.json").write_text("{broken", encoding="utf-8")
            code, _out, err = self._run(["scan", "--locales", str(root)])
            self.assertEqual(code, 2)
            self.assertIn("en.json", err)
            self.assertIn("invalid JSON", err)

    def test_usage_error_non_object_json(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "locales"
            root.mkdir()
            (root / "en.json").write_text('[1, 2]', encoding="utf-8")
            code, _out, err = self._run(["scan", "--locales", str(root)])
            self.assertEqual(code, 2)
            self.assertIn("must be an object", err)

    def test_unknown_target_warns_not_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "locales"
            self._write_locales(root, {"hi": "Hello"}, {"hi": "سلام"})
            code, out, err = self._run(["scan", "--locales", str(root),
                                        "--targets", "de"])
            self.assertEqual(code, 2)  # no valid target left -> usage error
            code2, _out2, err2 = self._run(["scan", "--locales", str(root),
                                            "--targets", "fa,de"])
            self.assertEqual(code2, 0)
            self.assertIn("warning: target locale 'de' not found", err2)

    def test_json_format_machine_readable(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "locales"
            self._write_locales(root, {"hi": "Hello"}, {})
            code, out, _err = self._run(["scan", "--locales", str(root), "--format", "json"])
            self.assertEqual(code, 1)
            data = json.loads(out)
            self.assertEqual(data["findings"][0]["rule"], "LQG001")

    def test_repo_fixture_fires_all_planted_rules(self):
        # the CI fixture corpus must keep exercising LQG001-LQG008
        fixture = REPO_ROOT / "tests" / "fixtures" / "locales"
        code, out, _err = self._run(["scan", "--locales", str(fixture), "--format", "json"])
        data = json.loads(out)
        rules = {f["rule"] for f in data["findings"]}
        self.assertLessEqual({"LQG001", "LQG002", "LQG003", "LQG004", "LQG005",
                              "LQG006", "LQG007", "LQG008"}, rules)

    def _run(self, args: list[str]) -> tuple[int, str, str]:
        proc = subprocess.run(
            [sys.executable, "-m", "raast.i18n", *args],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        return proc.returncode, proc.stdout, proc.stderr


class TestMainDispatch(unittest.TestCase):
    def test_main_returns_usage_error_code(self):
        self.assertEqual(main(["scan", "--locales", "/no/such/dir"]), 2)

    def test_main_rejects_missing_subcommand(self):
        with self.assertRaises(SystemExit):
            main([])


if __name__ == "__main__":
    unittest.main()
