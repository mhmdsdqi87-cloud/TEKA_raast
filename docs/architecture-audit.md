# Architecture Audit — RAAST v1 (pre-ecosystem baseline)

Audit date: 2026-11-14 · Auditor: automated audit pass + manual review · Repo state: 11 content files, ~1,520 lines, no git history yet.

## 1. What existed (v1)

| Component | State | Notes |
|---|---|---|
| 6 Skills (`skills/*/SKILL.md`) | Working content | All validated against the Agent Skills frontmatter constraints (see §3) |
| `skills/rtl-typography/fonts.md` | Working | 13 fonts, CDN snippets, pairing recipes |
| `skills/rtl-typography/scripts/fix-zwnj.py` | Working, untested | Dry-run default, code-block/URL protection verified on sample input |
| `demo/index.html` | Working | Persian RTL landing (fictional product «سیمرغ»), ۴۵ ZWNJ verified, no letter-spacing declarations, no physical text-align |
| `assets/` | Working | Banner (1280×640), demo + showcase screenshots, banner.html source |
| `README.md` | Bilingual (EN+FA) | Referenced repo name `raast`; needed rename handling for `TEKA_raast` |
| `LICENSE` | MIT | — |

## 2. Gaps identified (drove this roadmap)

1. **No executable layer** — knowledge existed as prose; nothing could *inspect* a project, so quality depended entirely on the agent obeying prose.
2. **No tests at all** — the ZWNJ normalizer had zero test coverage despite handling Unicode edge cases (the riskiest code in the repo).
3. **No verification loop** — nothing could prove a page is RTL-correct (statically or in a browser), so "fixed" claims were unverifiable.
4. **No benchmark** — no way to measure whether Skills actually improve agent output. Any claim would have been fabricated.
5. **No CI / community files** — no CONTRIBUTING, SECURITY, CHANGELOG, issue templates; not prepared for contributors.
6. **Docstring bug** in `fix-zwnj.py`: usage example `python3 draft-output.md > fixed.md --apply` is invalid shell (flag after redirect target); `--apply` belongs before the redirect. No file-exclusion flag despite claiming one.
7. **Duplication risk**: ZWNJ rules appear in `rtl-typography` §5 and again in `rtl-audit` P0 items; the normalizer logic would be duplicated a second time inside the CLI. Resolution: `rtl-audit` references typography for rules (kept, cross-reference is intentional); the CLI owns the engine, the skill script stays standalone for no-CLI users — documented as two entry points to one spec (`skills/rtl-typography/references/normalization.md`).
8. **README claimed "100+ rules"** — marketing-sounding, unverifiable at the time. Replaced by rule IDs that can be counted in the CLI.
9. **Language scope drift risk**: v1 mixed Persian and Arabic coverage in single files; ecosystem needs per-language profiles so adding Hebrew/Urdu does not mean editing prose everywhere.

## 3. Skills spec compliance (verified programmatically)

Checked on 2026-11-14 against the Agent Skills frontmatter constraints:

| Skill | frontmatter | name format (≤64, `[a-z0-9-]`) | description length (≤1024) | bundled files |
|---|---|---|---|---|
| rtl-typography | OK | 14 chars, valid | 355 | fonts.md, scripts/fix-zwnj.py |
| rtl-landing | OK | 11, valid | 334 | — |
| rtl-components | OK | 14, valid | 324 | — |
| rtl-bidi | OK | 8, valid | 366 | — |
| jalali-dates | OK | 12, valid | 334 | — |
| rtl-audit | OK | 9, valid | 333 | — |

ZWNJ inventory in skill prose: rtl-typography 26, rtl-bidi 4, rtl-landing 1, jalali-dates 1, others 0 (skills with 0 only show *broken* patterns deliberately, as wrong-vs-right examples).

## 4. Target architecture (three pillars, one engine)

```
            ┌────────────────────────────────────────────┐
            │            skills/  (intelligence)         │
            │  SKILL.md files teach agents the rules     │
            └───────────────┬────────────────────────────┘
                            │ same rule set, executed
            ┌───────────────▼────────────────────────────┐
            │        raast CLI  (diagnostics engine)     │
            │  detect → rules → report / safe-fix        │
            │  raast/profiles/fa.json · raast/profiles/ar.json       │
            └───────┬────────────────────┬───────────────┘
                    │                    │
     ┌──────────────▼─────┐    ┌─────────▼──────────────┐
     │ benchmarks/        │    │ browser/ (Playwright)  │
     │ cases + validators │    │ overflow, dir, icons   │
     │ A/B/C evaluation   │    │ 390/768/1440 viewports │
     └────────────────────┘    └────────────────────────┘
                    │
        ┌───────────▼────────────┐
        │ action/ (GitHub Action)│  CI integration, exit code
        └────────────────────────┘  by severity threshold
```

- **Skills** stay pure Markdown + one standalone script (usable with no CLI installed).
- **CLI** (`raast` Python package, stdlib-only) is the single diagnostic engine; Skills' audit checklist mirrors its rule IDs.
- **Benchmarks** evaluate *outputs* (HTML) against validators; the runner cannot invent results — it only validates real candidate files.
- **Browser suite** runs real Chromium checks; it explicitly separates automated failures from "needs human review".

## 5. Decisions & assumptions

- **Python 3.11+, stdlib-only CLI** — zero runtime dependencies is a feature for a linter that runs in CI everywhere; no pip risk, no supply-chain surface. Tests use `unittest` (stdlib) for the same reason.
- **Node/Playwright for browser tests** — Playwright is the de-facto standard for direction/computed-style assertions; installed and verified at 1.57.0 in the development sandbox.
- **Repo name**: canonical GitHub repo is `TEKA_raast`; all clone URLs, install commands and badges use that name. Package/import name stays `raast` (lowercase, PyPI-legal, shell-friendly).
- **Persian kept inside skills/docs where it is content** (it *is* the subject matter); all top-level README/docs are international English per project positioning.
- No custom Jalali conversion algorithm was introduced — `jalali-dates` continues to mandate `Intl`/vetted libraries (algorithm correctness would need independent test vectors we cannot yet certify).

## 6. Zero-defect round defect register (v0.4.3)

Every entry below was REPRODUCED with a minimal case before fixing, then
pinned with regression tests. D1 is recorded as a lesson about tooling, not
a code defect.

| ID | Severity | Component | Defect | Status |
|----|----------|-----------|--------|--------|
| D2 | high (FP) | raast/rules | RTL015/RTL016 fired on content inside legitimate `dir="rtl"` scopes; mask used a fixed element list that missed structural containers | fixed — stack-based inherited-direction scope model + 8 regression tests |
| D3 | high (corruption) | raast/normalizer | `normalize(lang="ar")` rewrote Arabic Yeh/Kaf to Persian shapes, corrupting Arabic orthography | fixed — unification gated to `fa` |
| D4 | medium (CLI contract) | raast/cli | missing scan target exited 0 ("0 files scanned") | fixed — exit 2 across doctor/audit/fix/report |
| D5 | medium (CLI contract) | raast/config | explicit `--config` pointing to a missing file silently used defaults | fixed — clean ConfigError |
| D6 | medium | raast/report | `to_github()` emitted unescaped property values / message data | fixed — same escaping contract as review |
| D7 | low | raast/report | `to_markdown()` table cells did not escape pipes | fixed |
| D8 | low | raast/fonts | cmap format4 applied `idDelta` in the `idRangeOffset != 0` branch (spec violation; false glyph gaps possible) | fixed — spec-correct direct glyphIndexArray read, synthetic-font regression test |
| D9 | medium (crash) | raast/cli | single-file scan crashed with a traceback on invalid UTF-8 | fixed — clean exit-2 naming the file |
| D10 | perf | raast/scanner + cli | every file was read twice (validation pass + scan pass) | fixed — `iter_files_with_content` single-read path; baseline recorded |
| D11 | low | raast/rules | kebab/camel vendor-prefix round-trip divergence (`-ms-webkit` -> `MsWebkit` -> `ms-webkit`); `-ms-*` camelCase casing violated the React `ms` lowercase convention | fixed — true round-trip invariant + correct `ms` casing (found by fuzzing) |
| D12 | critical (hang) | raast/scanner | `glob_to_regex` infinite loop on unclosed `{` / `[` — a corrupted config pattern froze the CLI forever | fixed — unbalanced delimiters become literals (found by fuzzing) |
| D13 | medium (crash) | raast/config | `validate_config` raised TypeError on unhashable `fail_on`/severity values instead of ConfigError | fixed — type-guarded validation (found by fuzzing) |
| D14 | medium (FP) | raast/rules | RTL012 flagged atoms already wrapped in bidi isolates; isolation written as `&#x2066;…&#x2069;` was invisible (entities never decoded) | fixed — bidi-control/ZWNJ entity decoding + isolate-awareness |
| D15 | high (FN regression, caught pre-push) | raast/rules | an intermediate scope-mask version treated `<html dir="ltr">` as an isolation scope, masking the entire body of canonical es pages and silencing RTL015/016/017 | fixed — inherited-direction model where `<html>` states the baseline; caught by bug corpus CS-008/012/032, pinned by fixture a7 |
| D1 | — | CI workflow | SUSPECTED corrupted push trigger (`branches: ain]`) — investigation proved a phantom: byte-level comparison + API blob-sha verification showed the remote always carried `branches: [main]`; the "corruption" existed only in the dev sandbox's rendered tool output | no code change needed; verification method documented (sha comparison, never rendered strings) |

Known limitations that remain (honest, documented, not defects):
- Lexical prose scanning cannot resolve ambiguous Persian words (e.g. «می»
  as wine vs. prefix) — the verb-stem gate keeps such cases silent, which is
  the conservative choice; native-review program covers the rest.
- CSS-in-JS shorthand/vendor forms beyond the known prefixes are not modeled
  (documented on the compatibility matrix).
- Fixture-level compatibility verification is not production-framework
  verification; the matrix wording keeps that distinction explicit.
