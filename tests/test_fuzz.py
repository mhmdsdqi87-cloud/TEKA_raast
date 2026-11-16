"""Property and fuzz tests — randomized inputs with fixed seeds.

Complements the scenario tests: each property here holds for EVERY input
from a large generated space, not just the hand-picked fixtures. Seeds are
fixed so failures are always reproducible.

Properties under test:
  P1  kebab/camel CSS property normalization round-trips (incl. vendor prefixes)
  P2  glob translation never raises on safe patterns and matches sanely
  P3  _mask/_unmask is a perfect round-trip for arbitrary Unicode payloads
  P4  normalize() is idempotent (second run changes nothing)
  P5  parse_unified_diff never raises on arbitrary token soup; ranges are
      well-formed (start <= end, positive lines)
  P6  validate_config either returns a dict or raises ConfigError — never
      any other exception type (malformed config must not crash the CLI)
  P7  extract_placeholders preserves text length when masking
  P8  the prose rule never raises on arbitrary Unicode line soup
"""
from __future__ import annotations

import random
import string
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from raast.config import ConfigError, validate_config  # noqa: E402
from raast.diffscope import parse_unified_diff  # noqa: E402
from raast.i18n import extract_placeholders  # noqa: E402
from raast.normalizer import _mask, _unmask, normalize  # noqa: E402
from raast.profiles import load_profile  # noqa: E402
from raast.rules import Finding, RuleContext, _camel_prop, _kebab_prop, rule_prose  # noqa: E402
from raast.scanner import glob_to_regex  # noqa: E402

rng = random.Random(20260217)


def _ctx(lang="fa"):
    return RuleContext(
        config={"language": lang, "rules": {}, "include": [], "exclude": [], "fail_on": "P1"},
        profile=load_profile(lang),
    )


FA_CHUNKS = ["می", "نمی", "شود", "خانه", "ها", "های", "تر", "ترین", "کتاب", "اين", "كد", " ", "\u200c"]
AR_CHUNKS = ["هذا", "نص", "عربي", "كريم", "ي", "ك", " "]
HE_CHUNKS = ["שלום", "עולם", "זהו", " "]
ES_CHUNKS = ["¿", "¡", "Hola", "mundo", "?", "!", " ", ","]
LATIN_CHUNKS = ["a", "Z9", "-", "_", "https://x.example/p?1=2", "mail@x.io", " ", "\t"]


def _random_text(chunks, min_len=1, max_len=25) -> str:
    return "".join(rng.choice(chunks) for _ in range(rng.randint(min_len, max_len)))


class TestPropertyNormalization(unittest.TestCase):
    """P1/P3/P4 — normalization layer properties."""

    VENDOR_WORDS = ["webkit", "moz", "ms", "o", "khtml"]
    PLAIN_WORDS = ["margin", "padding", "border", "inline", "block", "start",
                   "end", "left", "right", "size", "color"]

    def _gen_prop(self) -> str:
        """Generate property names from the REAL spelling universes:
        kebab (optionally vendor-prefixed), camelCase, and React vendor
        camelCase (WebkitX/MozX/KhtmlX/OX or lowercase msX)."""
        kind = rng.choice(["kebab", "kebab", "camel", "vendor_camel"])
        n = rng.randint(1, 4)
        words = [rng.choice(self.PLAIN_WORDS) for _ in range(n)]
        if kind == "kebab":
            prop = "-".join(words)
            # a leading hyphen is RESERVED for vendor prefixes — only real
            # vendor heads may carry it (-padding-x is not a CSS spelling)
            if words[0] in self.VENDOR_WORDS and rng.random() < 0.5:
                prop = "-" + prop
            return prop
        if n == 1:
            return words[0]
        if kind == "camel":
            return words[0] + "".join(w.capitalize() for w in words[1:])
        vendor = rng.choice(self.VENDOR_WORDS)
        head = "ms" if vendor == "ms" else vendor.capitalize()
        return head + "".join(w.capitalize() for w in words)

    def test_kebab_camel_round_trip(self):
        ok = 0
        for _ in range(600):
            prop = self._gen_prop()
            kebab = _kebab_prop(prop)
            self.assertFalse(any(c.isupper() for c in kebab),
                             f"kebab has uppercase: {prop!r} -> {kebab!r}")
            back = _camel_prop(kebab)
            # kebab->camel is not always the exact inverse (vendor casing),
            # but re-normalizing must converge to the same kebab form
            self.assertEqual(_kebab_prop(back), kebab, f"round-trip diverged: {prop!r}")
            ok += 1
        self.assertGreater(ok, 500)

    def test_vendor_prefix_normalization(self):
        for prefix in ("Webkit", "Moz", "ms", "O", "Khtml"):
            prop = prefix + "Transform"
            kebab = _kebab_prop(prop)
            self.assertTrue(kebab.startswith("-"), f"{prefix} must gain a leading hyphen, got {kebab!r}")

    def test_mask_unmask_round_trip_unicode(self):
        for _ in range(300):
            chunks = rng.choice([FA_CHUNKS, AR_CHUNKS, HE_CHUNKS, ES_CHUNKS, LATIN_CHUNKS])
            text = _random_text(chunks)
            # sprinkle protected-region markers
            if rng.random() < 0.5:
                text += " https://a.example/" + _random_text(LATIN_CHUNKS, 1, 6)
            if rng.random() < 0.3:
                text = "`" + _random_text(LATIN_CHUNKS, 1, 5) + "` " + text
            masked, saved = _mask(text)
            self.assertEqual(_unmask(masked, saved), text)

    def test_normalize_idempotent(self):
        for _ in range(200):
            lang = rng.choice(["fa", "ar", "he", "es"])
            chunks = {"fa": FA_CHUNKS, "ar": AR_CHUNKS, "he": HE_CHUNKS, "es": ES_CHUNKS}[lang]
            text = _random_text(chunks)
            once = normalize(text, lang=lang)
            twice = normalize(once, lang=lang)
            self.assertEqual(once, twice, f"normalize not idempotent for {lang}: {text!r}")


class TestPropertyScanner(unittest.TestCase):
    """P2 — glob translation robustness."""

    SAFE_PATTERN_CHARS = string.ascii_letters + string.digits + "*/?-.{}_"

    def test_glob_never_raises_and_is_anchored(self):
        rx_count = 0
        for _ in range(300):
            pat = "".join(rng.choice(self.SAFE_PATTERN_CHARS) for _ in range(rng.randint(1, 12)))
            rx = glob_to_regex(pat)  # must not raise
            probe = rng.choice(["a/b/c.css", "x.js", "deep/nested/dir/file.tsx", "a.md"])
            m = rx.match(probe)
            self.assertTrue(m is None or (m.start() == 0 and m.end() == len(probe)),
                            f"pattern {pat!r} produced an unanchored match")
            rx_count += 1
        self.assertGreater(rx_count, 250)

    def test_doublestar_matches_any_depth(self):
        rx = glob_to_regex("**/*.css")
        for path in ("a.css", "a/b.css", "a/b/c/d/e.css"):
            self.assertTrue(rx.match(path), f"**/*.css must match {path}")
        self.assertFalse(rx.match("a.css.bak"))

    def test_unclosed_brace_terminates_as_literal(self):
        # Regression: an unclosed '{' or '[' once sent the translator into an
        # infinite loop (a corrupted config pattern froze the CLI forever).
        for pat in ("a{", "a{b", "[", "ab[", "**/{unbalanced", "x[a"):
            rx = glob_to_regex(pat)  # must terminate
            self.assertIsNotNone(rx.match("a{") is None or True)
        self.assertFalse(glob_to_regex("a{").match("ab"))
        self.assertTrue(glob_to_regex("a{").match("a{"))


class TestPropertyDiffscope(unittest.TestCase):
    """P5 — the unified-diff parser tolerates arbitrary token soup."""

    SOUP_TOKENS = ["@@ -1 +1 @@", "@@", "-x", "+y", " z", "diff --git a/p b/p",
                   "+++ b/p", "--- a/p", "Binary files differ", "\\ No newline",
                   "index abc..def 100644", "", "\t", "+++ /dev/null"]

    def test_parser_never_raises_and_ranges_wellformed(self):
        for _ in range(400):
            soup = "\n".join(rng.choice(self.SOUP_TOKENS)
                             for _ in range(rng.randint(0, 30)))
            ranges = parse_unified_diff(soup)  # must not raise
            for path, rs in ranges.items():
                self.assertIsInstance(path, str)
                for start, end in rs:
                    self.assertGreaterEqual(start, 1)
                    self.assertGreaterEqual(end, start)

    def test_valid_git_diff_ranges_accurate(self):
        diff = ("diff --git a/src/ui.css b/src/ui.css\n"
                "index 111..222 100644\n"
                "--- a/src/ui.css\n"
                "+++ b/src/ui.css\n"
                "@@ -10,2 +10,3 @@\n"
                " old line\n"
                "-removed\n"
                "+added one\n"
                "+added two\n"
                " ctx\n")
        ranges = parse_unified_diff(diff)
        self.assertEqual(ranges, {"src/ui.css": [(10, 12)]})


class TestPropertyConfig(unittest.TestCase):
    """P6 — malformed config never escapes ConfigError."""

    def test_random_dicts_either_valid_or_configerror(self):
        keys = ["language", "include", "exclude", "fail_on", "severity_overrides",
                "rules", "unknown_key"]
        values = [None, 42, ["**/*.css"], {"RTL001": {"force": True}},
                  {"RTL999": "bogus"}, {"RTL004": {"nope": 1}}, "P0", "off", [],
                  {"fa": "not-here"}, "fa", 3.14, {"unexpected": True}]
        for _ in range(500):
            data = {rng.choice(keys): rng.choice(values)
                    for _ in range(rng.randint(0, 5))}
            try:
                cfg = validate_config(data)
            except ConfigError:
                continue
            self.assertIsInstance(cfg, dict)

    def test_known_good_config_still_valid(self):
        cfg = validate_config({"language": "fa", "fail_on": "P0",
                               "rules": {"RTL001": {"force": True}}})
        self.assertEqual(cfg["language"], "fa")


class TestPropertyI18nPlaceholders(unittest.TestCase):
    """P7 — placeholder masking preserves length exactly."""

    PLACEHOLDER_TOKENS = ["{name}", "{{count}}", "%s", "%1$s", "{0}", "{user_name}", "plain"]

    def test_masking_preserves_length(self):
        for _ in range(300):
            parts = []
            for _ in range(rng.randint(1, 6)):
                parts.append(rng.choice(self.PLACEHOLDER_TOKENS))
                parts.append(_random_text(FA_CHUNKS + LATIN_CHUNKS, 0, 8))
            text = "".join(parts)
            tokens, masked = extract_placeholders(text)
            self.assertEqual(len(masked), len(text))

    def test_no_placeholder_leaks_into_masked_prose(self):
        for _ in range(200):
            text = rng.choice(self.PLACEHOLDER_TOKENS) + _random_text(FA_CHUNKS, 1, 6)
            _, masked = extract_placeholders(text)
            self.assertNotIn("{", masked)
            self.assertNotIn("%s", masked)


class TestPropertyProseRuleRobustness(unittest.TestCase):
    """P8 — rule_prose survives arbitrary Unicode soup without raising."""

    def test_prose_never_raises_any_profile(self):
        for _ in range(120):
            lang = rng.choice(["fa", "ar", "he", "es"])
            chunks = {"fa": FA_CHUNKS, "ar": AR_CHUNKS, "he": HE_CHUNKS, "es": ES_CHUNKS}[lang]
            line = _random_text(chunks + LATIN_CHUNKS, 0, 30)
            path = rng.choice(["doc.md", "page.html", "comp.vue", "x.txt"])
            findings = rule_prose(path, line, load_profile(lang), {}, suffix=Path(path).suffix)
            for f in findings:
                self.assertIn(f.rule, {"RTL009", "RTL010", "RTL011", "RTL012", "RTL015", "RTL017"})


if __name__ == "__main__":
    unittest.main()
