"""RAAST test suite — stdlib unittest, no external dependencies.

Run: python3 -m unittest discover -s tests -v   (from repo root)
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from raast.config import ConfigError, validate_config, load_config  # noqa: E402
from raast.detect import detect  # noqa: E402
from raast.normalizer import normalize, detect_broken_zwnj  # noqa: E402
from raast.rules import (  # noqa: E402
    Finding, RuleContext, run_rules, rule_css_physical, rule_css_text_align,
    rule_css_letter_spacing, rule_tailwind, rule_html_meta, rule_prose,
)
from raast.profiles import load_profile, available_profiles  # noqa: E402
from raast.benchmark import run_case  # noqa: E402
from raast.scanner import glob_to_regex  # noqa: E402

ZWNJ = "\u200c"
CTX_FA = RuleContext(config={"language": "fa", "rules": {}, "include": [], "exclude": [], "fail_on": "P1"},
                     profile=load_profile("fa"))
CTX_AR = RuleContext(config={"language": "ar", "rules": {}, "include": [], "exclude": [], "fail_on": "P1"},
                     profile=load_profile("ar"))


def _ctx(lang="fa", rules=None):
    return RuleContext(config={"language": lang, "rules": rules or {}, "include": [], "exclude": [], "fail_on": "P1"},
                       profile=load_profile(lang))


class TestNormalizer(unittest.TestCase):
    def test_prefix_join(self):
        self.assertEqual(normalize("می رود"), f"می{ZWNJ}رود")
        self.assertEqual(normalize("نمی دانم"), f"نمی{ZWNJ}دانم")

    def test_plural_join(self):
        self.assertEqual(normalize("خانه ها را ببینید"), f"خانه{ZWNJ}ها را ببینید")
        self.assertEqual(normalize("کتاب های"), f"کتاب{ZWNJ}های")

    def test_comparative_join(self):
        self.assertEqual(normalize("خوب تر است"), f"خوب{ZWNJ}تر است")
        self.assertEqual(normalize("بزرگ ترین"), f"بزرگ{ZWNJ}ترین")

    def test_possessive_never_joined(self):
        # کتابم must remain byte-identical (no false ZWNJ insertion)
        self.assertEqual(normalize("کتابم"), "کتابم")

    def test_arabic_yeh_kaf(self):
        self.assertEqual(normalize("ي ك"), "ی ک")

    def test_code_fence_protected(self):
        text = "می رود\n```bash\nnpm run mi rood\n```"
        out = normalize(text)
        self.assertIn(f"می{ZWNJ}رود", out)
        self.assertIn("npm run mi rood", out)

    def test_url_email_protected(self):
        text = "آدرس https://mi-rood.example/ها است و mail@example.com می رود"
        out = normalize(text)
        self.assertIn("https://mi-rood.example/ها", out)
        self.assertIn("mail@example.com", out)

    def test_keep_region_protected(self):
        text = "می رود <!-- keep -->می رود<!-- /keep -->"
        out = normalize(text)
        self.assertIn(f"می{ZWNJ}رود <!-- keep -->می رود<!-- /keep -->", out)

    def test_digits_fa(self):
        # --digits converts Arabic-Indic ٠-٩ to Persian ۰-۹ in fa prose (per decision table)
        self.assertEqual(normalize("قیمت ٩٩٠٠٠", lang="fa", digits=True), f"قیمت ۹۹۰۰۰")
        # Western digits are NOT auto-converted (RTL010 reports them instead)
        self.assertEqual(normalize("قیمت 99000", lang="fa", digits=True), "قیمت 99000")

    def test_digits_blocked_for_ar(self):
        # Arabic-Indic digits are CORRECT in Arabic — must not be converted.
        self.assertEqual(normalize("٩٩٠٠٠", lang="ar", digits=True), "٩٩٠٠٠")

    def test_punct(self):
        # Latin punctuation adjacent to Persian letters converts per PUNCT_SUBS;
        # Persian text must use ، ؟ ؛ (U+060C / U+061F / U+061B)
        self.assertEqual(normalize("سلام , دنیا", punct=True), "سلام، دنیا")
        self.assertEqual(normalize("آیا این درست است ?", punct=True), "آیا این درست است؟")
        self.assertEqual(normalize("یعنی این ; پایان", punct=True), "یعنی این؛ پایان")
        # Latin punctuation next to Latin words must stay untouched
        self.assertEqual(normalize("wait, what? ok; done", punct=True), "wait, what? ok; done")

    def test_detect_broken_zwnj_lines(self):
        hits = detect_broken_zwnj("می رود و خانه ها")
        self.assertGreaterEqual(len(hits), 2)

    def test_joined_form_not_autosplit(self):
        # "میکند" (joined, missing ZWNJ) must NOT be rewritten — review-only per decision table
        out = normalize("میکند")
        self.assertEqual(out, "میکند")


class TestRules(unittest.TestCase):
    def test_css_physical_margin_padding(self):
        css = ".a { margin-left: 10px; }\n.b { padding-right: 4px; }\n"
        force = {"rules": {"RTL001": {"force": True}, "RTL002": {"force": True}}}
        f = rule_css_physical("a.css", css, force)
        ids = {x.rule for x in f}
        self.assertEqual(ids, {"RTL001", "RTL002"})

    def test_css_physical_gated_on_arabic(self):
        css = ".a { margin-left: 10px; }\n"  # no Arabic evidence
        f = rule_css_physical("a.css", css, CTX_FA.config)
        self.assertEqual(f, [])

    def test_css_physical_force(self):
        css = ".a { margin-left: 10px; }\n"
        f = rule_css_physical("a.css", css, {"rules": {"RTL001": {"force": True}}})
        self.assertEqual(len(f), 1)

    def test_text_align(self):
        f = rule_css_text_align("a.css", ".c { text-align: left; }", {"rules": {"RTL004": {"force": True}}})
        self.assertEqual(f[0].suggested_fix, "text-align: start")

    def test_letter_spacing_p0(self):
        f = rule_css_letter_spacing("a.css", ".t { letter-spacing: .05em; }", {"rules": {"RTL005": {"force": True}}})
        self.assertEqual(f[0].rule, "RTL005")
        self.assertEqual(f[0].severity, "P0")

    def test_letter_spacing_zero_ok(self):
        f = rule_css_letter_spacing("a.css", ".t { letter-spacing: 0; }", {"rules": {"RTL005": {"force": True}}})
        self.assertEqual(f, [])

    def test_tailwind_spacing_fix(self):
        html = '<div class="ml-4 mr-2 pl-1 text-left">فارسی</div>'
        f = [x for x in rule_tailwind("a.tsx", html, CTX_FA.config) if x.fixable]
        fixes = {x.message.split("`")[1]: x.suggested_fix for x in f}
        self.assertEqual(fixes["ml-4"], "`ms-4`")
        self.assertEqual(fixes["mr-2"], "`me-2`")
        self.assertEqual(fixes["pl-1"], "`ps-1`")
        self.assertEqual(fixes["text-left"], "`text-start`")

    def test_tailwind_translate_x(self):
        html = '<div class="translate-x-full">فارسی</div>'
        f = rule_tailwind("a.tsx", html, CTX_FA.config)
        self.assertTrue(any(x.rule == "RTL007" for x in f))

    def test_html_missing_dir(self):
        html = '<html lang="fa"><body><p>فارسی</p></body></html>'
        f = rule_html_meta("a.html", html, "fa")
        rules = {x.rule for x in f}
        self.assertIn("RTL006", rules)
        self.assertNotIn("RTL014", rules)  # lang present

    def test_html_missing_lang(self):
        html = '<html dir="rtl"><body><p>فارسی</p></body></html>'
        f = rule_html_meta("a.html", html, "fa")
        self.assertIn("RTL014", {x.rule for x in f})

    def test_ltr_on_arabic(self):
        html = '<span dir="ltr">سلام دوست من</span>'
        f = run_rules(Path("a.html"), "a.html", html, CTX_FA)
        self.assertTrue(any(x.rule == "RTL013" for x in f))

    def test_ltr_on_phone_ok(self):
        # phone inside dir=ltr is CORRECT — must not trigger RTL013
        html = '<span dir="ltr">+98 21 9100 2000</span>'
        f = run_rules(Path("a.html"), "a.html", html, CTX_FA)
        self.assertFalse(any(x.rule == "RTL013" for x in f))

    def test_prose_broken_zwnj_and_latin_punct(self):
        text = "این می رود , سریع !"
        f = rule_prose("a.md", text, load_profile("fa"))
        rules = {x.rule for x in f}
        self.assertIn("RTL011", rules)
        self.assertIn("RTL009", rules)

    def test_prose_western_digits(self):
        f = rule_prose("a.md", "قیمت 99000 تومان است", load_profile("fa"))
        self.assertIn("RTL010", {x.rule for x in f})

    def test_prose_phone_isolated_ok(self):
        # digits inside the +98... atom are suppressed by RTL012 containment
        f = rule_prose("a.md", "تماس +98 912 345 6789 برای پشتیبانی", load_profile("fa"))
        rtl010 = [x for x in f if x.rule == "RTL010"]
        self.assertEqual(rtl010, [])

    def test_prose_code_fence_ignored(self):
        text = "```\nمی رود , 99000\n```\nپاک"
        f = rule_prose("a.md", text, load_profile("fa"), suffix=".md")
        self.assertEqual([x for x in f if x.rule in ("RTL011", "RTL010", "RTL009")], [])

    def test_prose_style_block_ignored(self):
        # CSS/JS inside markup must not trigger prose rules (false-positive guard)
        text = "<style>.x { gap: 24px; margin-left: 1px; }</style><p>متن پاک</p>"
        f = rule_prose("a.html", text, load_profile("fa"), suffix=".html")
        self.assertEqual([x for x in f if x.rule in ("RTL009", "RTL010", "RTL011")], [])

    def test_prose_jsx_attributes_ignored(self):
        # Tailwind classes in JSX attributes are not prose
        text = '<button className="px-5 py-2.5 font-bold">شروع رایگان</button>'
        f = rule_prose("a.tsx", text, load_profile("fa"), suffix=".tsx")
        self.assertEqual([x for x in f if x.rule == "RTL010"], [])

    def test_english_file_quiet(self):
        html = '<div class="ml-4 text-left">Hello world</div>'
        f = rule_tailwind("a.tsx", html, CTX_FA.config)
        self.assertEqual(f, [])


class TestConfig(unittest.TestCase):
    def test_valid(self):
        cfg = validate_config({"language": "ar", "fail_on": "P0"})
        self.assertEqual(cfg["language"], "ar")

    def test_unknown_key(self):
        with self.assertRaises(ConfigError):
            validate_config({"languages": "fa"})

    def test_bad_language(self):
        with self.assertRaises(ConfigError):
            validate_config({"language": "de"})

    def test_bad_severity(self):
        with self.assertRaises(ConfigError):
            validate_config({"severity_overrides": {"RTL003": "P3"}})

    def test_bad_rule_option(self):
        with self.assertRaises(ConfigError):
            validate_config({"rules": {"RTL003": {"not_an_option": 1}}})

    def test_force_ok(self):
        cfg = validate_config({"rules": {"RTL001": {"force": True}}})
        self.assertTrue(cfg["rules"]["RTL001"]["force"])

    def test_load_missing_returns_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            cfg, source = load_config(None, Path(td))
            self.assertIsNone(source)
            self.assertEqual(cfg["fail_on"], "P1")


class TestDetect(unittest.TestCase):
    def test_next_tailwind(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            (tdp / "package.json").write_text(json.dumps(
                {"dependencies": {"next": "16.1.1", "react": "19", "tailwindcss": "4"}}))
            (tdp / "tailwind.config.ts").write_text("export default {}")
            det = detect(tdp)
            self.assertTrue(det["frameworks"].get("next"))
            self.assertTrue(det["frameworks"].get("react"))
            self.assertTrue(det["frameworks"].get("tailwindcss"))

    def test_no_assumption_from_lone_file(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            (tdp / "next.config.js").write_text("// decoy without package.json")
            det = detect(tdp)
            self.assertFalse(det["frameworks"].get("next", False))

    def test_html_project(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            (tdp / "index.html").write_text("<html></html>")
            det = detect(tdp)
            self.assertTrue(det["frameworks"].get("html"))


class TestScanner(unittest.TestCase):
    def test_glob_patterns(self):
        r = glob_to_regex("**/*.{html,css}")
        self.assertTrue(r.match("a/b.html"))
        self.assertTrue(r.match("x.css"))
        self.assertFalse(r.match("a/b.tsx"))

    def test_double_star(self):
        r = glob_to_regex("node_modules/**")
        self.assertTrue(r.match("node_modules/pkg/index.js"))
        self.assertFalse(r.match("src/index.js"))


class TestBenchmarkValidators(unittest.TestCase):
    GOOD = Path(REPO_ROOT / "tests/fixtures/correct_page.html").read_text(encoding="utf-8")
    BAD = Path(REPO_ROOT / "tests/fixtures/broken_page.html").read_text(encoding="utf-8")

    def _case(self, validations, files="*.html"):
        return {
            "id": "test-case", "category": "test", "title": "t", "severity": "P0",
            "files": files, "validation": validations,
        }

    def test_good_page_passes(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "p.html").write_text(self.GOOD, encoding="utf-8")
            res = run_case(self._case([
                {"type": "html_lang_dir", "lang": "fa", "dir": "rtl"},
                {"type": "no_letter_spacing"},
                {"type": "zwnj_min_count", "min": 2},
                {"type": "persian_digits_in_prose"},
                {"type": "persian_punctuation"},
                {"type": "no_physical_margin"},
                {"type": "viewport_meta"},
                {"type": "img_alt"},
                {"type": "icon_button_labels"},
                {"type": "code_dir_ltr"},
                {"type": "bidi_isolation"},
            ]), Path(td))
            self.assertEqual(res["status"], "pass", msg=str(res["checks"]))

    def test_bad_page_fails(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "p.html").write_text(self.BAD, encoding="utf-8")
            res = run_case(self._case([
                {"type": "html_lang_dir", "lang": "fa", "dir": "rtl"},
                {"type": "no_letter_spacing"},
                {"type": "no_physical_margin"},
            ]), Path(td))
            self.assertEqual(res["status"], "fail")
            failed = {c["type"] for c in res["checks"] if c["status"] == "fail"}
            self.assertLessEqual({"html_lang_dir", "no_letter_spacing", "no_physical_margin"}, failed)

    def test_missing_candidate_skips(self):
        with tempfile.TemporaryDirectory() as td:
            res = run_case(self._case([{"type": "viewport_meta"}], files="**/*.html"), Path(td))
            self.assertEqual(res["status"], "skipped")


class TestPackaging(unittest.TestCase):
    """Profiles must ship INSIDE the package — the wheel a user installs has no
    repo-root profiles/ dir. Regression guard for 'profile not found'."""

    def test_profiles_live_inside_package(self):
        import raast.profiles as profiles_mod
        pkg_dir = Path(profiles_mod.__file__).resolve().parent
        self.assertEqual(profiles_mod.PROFILES_DIR, pkg_dir / "profiles")

    def test_profile_files_exist_in_package(self):
        for lang in ("fa", "ar"):
            p = Path(load_profile.__globals__["PROFILES_DIR"]) / f"{lang}.json"
            self.assertTrue(p.exists(), f"{lang}.json missing from package data: {p}")

    def test_profiles_parse_and_are_complete(self):
        for lang in ("fa", "ar"):
            profile = load_profile(lang)
            self.assertIsInstance(profile, dict)
            numerals = profile.get("numerals")
            self.assertTrue(numerals and numerals.get("display"), f"{lang}: numerals missing")
            punct = profile.get("punctuation")
            self.assertTrue(punct and punct.get("comma") and punct.get("question"),
                            f"{lang}: punctuation missing")
            self.assertEqual(profile.get("direction"), "rtl")

    def test_available_profiles(self):
        self.assertEqual(available_profiles(), ["ar", "fa"])


class TestEndToEndCLI(unittest.TestCase):
    def test_doctor_json_on_fixture(self):
        import subprocess
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            (td_path / "broken.html").write_text(
                Path(REPO_ROOT / "tests/fixtures/broken_page.html").read_text(encoding="utf-8"),
                encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "-m", "raast.cli", "doctor", str(td_path), "--format", "json"],
                capture_output=True, text=True, cwd=REPO_ROOT,
            )
            data = json.loads(proc.stdout)
            rules = {f["rule"] for f in data["findings"]}
            # fixture HAS lang="fa" (so no RTL014) but lacks dir → RTL006
            expected = {"RTL006", "RTL001", "RTL002", "RTL004", "RTL005", "RTL003",
                        "RTL011", "RTL009", "RTL010"}
            self.assertLessEqual(expected, rules)

    def test_doctor_fail_on_p0_exit_code(self):
        import subprocess
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            (td_path / "broken.html").write_text(
                Path(REPO_ROOT / "tests/fixtures/broken_page.html").read_text(encoding="utf-8"),
                encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "-m", "raast.cli", "doctor", str(td_path), "--fail-on", "P0"],
                capture_output=True, text=True, cwd=REPO_ROOT,
            )
            self.assertEqual(proc.returncode, 1)

    def test_fix_dry_run_does_not_write(self):
        import subprocess
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            target = td_path / "page.html"
            target.write_text(
                Path(REPO_ROOT / "tests/fixtures/broken_page.html").read_text(encoding="utf-8"),
                encoding="utf-8")
            before = target.read_text(encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "-m", "raast.cli", "fix", str(td_path), "--zwnj"],
                capture_output=True, text=True, cwd=REPO_ROOT,
            )
            self.assertIn("DRY RUN", proc.stdout)
            self.assertEqual(target.read_text(encoding="utf-8"), before)

    def test_fix_apply_rewrites_and_backs_up(self):
        import subprocess
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            target = td_path / "page.html"
            target.write_text(
                Path(REPO_ROOT / "tests/fixtures/broken_page.html").read_text(encoding="utf-8"),
                encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "-m", "raast.cli", "fix", str(td_path), "--zwnj", "--apply"],
                capture_output=True, text=True, cwd=REPO_ROOT,
            )
            after = target.read_text(encoding="utf-8")
            self.assertIn(f"می{ZWNJ}کند", after)          # RTL011 fixed via --zwnj
            self.assertIn("margin-inline-start", after)   # RTL001 fixed
            self.assertIn("text-align: start", after)     # RTL004 fixed
            self.assertNotIn("letter-spacing: 0.05em", after)  # RTL005 removed
            self.assertTrue((td_path / ".raast-backup" / "page.html").exists())
            # re-scan: P0s must be gone
            proc2 = subprocess.run(
                [sys.executable, "-m", "raast.cli", "doctor", str(td_path), "--format", "json"],
                capture_output=True, text=True, cwd=REPO_ROOT,
            )
            data = json.loads(proc2.stdout)
            # RTL006 (missing dir) is deliberately review-only — it must remain
            self.assertEqual(data["summary"]["P0"], 1)
            remaining_p0 = {f["rule"] for f in data["findings"] if f["severity"] == "P0"}
            self.assertEqual(remaining_p0, {"RTL006"})


if __name__ == "__main__":
    unittest.main()
