"""Adversarial fixture pins — every finding on fixtures/adversarial/* is
hand-verified and pinned here. These files exist to catch accidental engine
behavior changes on nasty real-world-shaped inputs (scope nesting, malformed
markup, bidi control soup, CSS-in-JS spellings, Tailwind edge tokens).

Pin semantics:
  - each fixture's EXPECTED (rule, line) multiset is asserted exactly
  - a fixture documented as "clean" must scan to zero findings
Any diff against these pins must be a deliberate, documented decision.

Standalone style/utility files (a2, a5) carry no RTL-script text by design:
the evidence gate keeps them silent in a real project scan, so their pins
run with the rule `force` flags to exercise the CSS-in-JS and Tailwind paths
themselves.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from raast.config import DEFAULT_CONFIG  # noqa: E402
from raast.profiles import load_profile  # noqa: E402
from raast.rules import RuleContext, run_rules  # noqa: E402

ADVERSARIAL = REPO_ROOT / "fixtures" / "adversarial"


def _ctx(lang="fa", forced_rules=()):
    rules = {rid: {"force": True} for rid in forced_rules}
    return RuleContext(config={**DEFAULT_CONFIG, "language": lang, "rules": rules},
                       profile=load_profile(lang))


def _scan(name: str, lang: str, forced=()):
    p = ADVERSARIAL / name
    findings = run_rules(p, name, p.read_text(encoding="utf-8"), _ctx(lang, forced))
    return sorted((f.rule, f.line) for f in findings)


class TestAdversarialPins(unittest.TestCase):

    def test_a1_rtl_scope_nesting(self):
        # es host: every child inside <section dir="rtl"> is protected;
        # only the bare footer run fires (RTL015; RTL016 doesn't — the
        # footer paragraph also carries Latin words).
        self.assertEqual(_scan("a1-rtl-scope-nesting.html", "es"), [("RTL015", 14)])

    def test_a2_style_object_mix(self):
        # forced CSS rules: camelCase + vendor spellings + quoted values all
        # detected; the logical/zero-value safe block stays silent.
        self.assertEqual(_scan("a2-style-object-mix.js", "fa",
                               forced=("RTL001", "RTL002", "RTL004", "RTL005")),
                         [("RTL001", 6), ("RTL001", 7),
                          ("RTL002", 8), ("RTL002", 9), ("RTL002", 16),
                          ("RTL004", 10), ("RTL004", 16),
                          ("RTL005", 11)])

    def test_a3_bidi_soup_is_clean(self):
        # fa host: ZWNJ compounds correct, Persian digits correct, atoms
        # isolated via <bdi>, dir=ltr spans, AND entity-written isolates
        # (U+2066…U+2069 as &#x2066;…&#x2069;) — nothing may fire.
        self.assertEqual(_scan("a3-bidi-soup.html", "fa"), [])

    def test_a4_malformed_markup(self):
        # ar host: unclosed tags and multi-line attributes must not crash or
        # overfire; the physical margin and missing dir are real findings.
        self.assertEqual(_scan("a4-malformed-markup.html", "ar"),
                         [("RTL001", 11), ("RTL006", 5)])

    def test_a5_tailwind_torture(self):
        # forced: physical utilities on every line that carries them,
        # logical twins and word-like non-utilities (right-to-left) silent,
        # translate-x reported as RTL007 review-only (3 tokens on line 9).
        self.assertEqual(_scan("a5-tailwind-torture.js", "fa",
                               forced=("RTL008", "RTL007")),
                         [("RTL007", 9), ("RTL007", 9), ("RTL007", 9),
                          ("RTL008", 4), ("RTL008", 4), ("RTL008", 4),
                          ("RTL008", 4), ("RTL008", 4),
                          ("RTL008", 5), ("RTL008", 5),
                          ("RTL008", 6), ("RTL008", 6),
                          ("RTL008", 7), ("RTL008", 7),
                          ("RTL008", 8), ("RTL008", 8),
                          ("RTL008", 10),
                          ("RTL008", 11), ("RTL008", 11), ("RTL008", 11),
                          ("RTL008", 11)])

    def test_a6_he_es_host_mix(self):
        # es host: Hebrew inside dir=rtl section silent; the exposed Hebrew
        # paragraph fires RTL015+RTL016; the missing ¿ fires RTL017.
        self.assertEqual(_scan("a6-he-es-host-mix.html", "es"),
                         [("RTL015", 10), ("RTL016", 10), ("RTL017", 12)])

    def test_a7_canonical_es_page(self):
        # <html lang="es" dir="ltr"> is the document baseline, NOT an
        # isolation scope — the whole body must remain analyzable. The bare
        # Hebrew paragraph fires RTL015+RTL016; the dir=rtl section and the
        # redundant dir="ltr" containers stay silent.
        self.assertEqual(_scan("a7-canonical-es-page.html", "es"),
                         [("RTL015", 15), ("RTL016", 15)])

    def test_a5_wordlike_tokens_not_flagged(self):
        # The lookbehind/lookahead guards must keep prose hyphenations like
        # right-to-left out of RTL008 even under force.
        p = ADVERSARIAL / "a5-tailwind-torture.js"
        findings = run_rules(p, "a5-tailwind-torture.js",
                             p.read_text(encoding="utf-8"),
                             _ctx("fa", forced_rules=("RTL008",)))
        msgs = [f.message for f in findings]
        self.assertFalse(any("right-to-left" in m for m in msgs),
                         "prose hyphenation must never match as a utility")


if __name__ == "__main__":
    unittest.main()
