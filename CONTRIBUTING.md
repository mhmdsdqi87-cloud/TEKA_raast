# Contributing

Thanks for your interest in RAAST. This project optimizes for **correctness over volume** — we would rather have one verified rule than five plausible ones.

## Development setup

```bash
git clone https://github.com/mhmdsdqi87-cloud/TEKA_raast.git
cd TEKA_raast
pip install -e .
python3 -m unittest discover -s tests -v     # must be green before any PR
python3 tools/corpus/verify.py               # 32/32 specimens must PASS
python3 tools/compat/run_matrix.py --check   # generated docs must be fresh
# optional, for the runtime inspector:
pip install 'raast[runtime]' && playwright install chromium
```

## Repository layout

```
raast/         CLI engine (Python, stdlib only)    tests/      unit + e2e (stdlib unittest)
skills/        six agent skills (SKILL.md)         benchmarks/ cases + validators + reference
browser/       Playwright suite (Node)             raast/profiles/ fa / ar / he / es JSON
corpus/        32 verified RTL bug specimens       fixtures/compat/  framework fixtures
vscode-raast/  VS Code extension scaffold          tools/      corpus + matrix tooling
action/        GitHub Action (composite)           docs/       all documentation
demo/          demo artifact produced by the skills
```

## Ground rules

1. **No new runtime dependencies in the CLI** — stdlib only. The browser suite may add devDependencies, pinned.
2. **Every rule ships with tests** — including a false-positive case (the rule must NOT fire on legitimate patterns).
3. **Every falsifiable claim needs an artifact** — benchmark numbers come from `raast benchmark` output; never edit results files by hand.
4. **Normalization changes** must follow `skills/rtl-typography/references/normalization.md` — additions need the ambiguity analysis filled in.
5. **Unicode discipline**: tests must include real Persian/Arabic strings (ZWNJ, digits, punctuation) — no transliterated placeholders.

## Adding a language profile (native speakers especially welcome)

1. Copy `raast/profiles/fa.json` → `raast/profiles/he.json` (or ur) and fill every field; do not guess — mark fields you are unsure about with `"$review": true`.
2. Add prose rules wiring in `raast/rules` behind the profile (no hard-coded language checks).
3. Add at least 3 benchmark cases using the new profile.
4. Open the PR titled `profiles: add <lang>` — a maintainer will pair with you on review.

## Adding a corpus specimen

The corpus ([corpus/](corpus/README.md)) is the project's evidence base. To add a specimen:

1. Copy an existing sample dir under `corpus/samples/CS-<NNN>-<category>/` and edit `broken.html` (one defect), `fixed.html` (the corrected twin) and `sample.json` (claim exactly the rule IDs that should fire).
2. Run `python3 tools/corpus/verify.py` — your specimen FAILS until the claimed rules actually fire on `broken.html` and `fixed.html` scans clean. Never adjust `rule_ids` to match a bad specimen; fix the specimen.
3. Run `python3 tools/corpus/evidence.py --only CS-<NNN>` to render before/after screenshots (requires playwright).
4. Run `python3 tools/corpus/build_index.py` to refresh the index table.
5. Specimens reproduced from real websites must cite the source URL and license in `sample.json.source`; unverified reproductions stay labeled `lab-verified`.

## Pull requests

- One logical change per PR; include: what/why, test evidence (paste real command output), docs updates.
- CI must pass: unit tests, benchmark self-validation (condition C), corpus verification, compatibility-matrix freshness, i18n-gate detection check, and the repo's own doctor scan (P0-free).
- Descriptions in English; Persian is welcome in comments where it clarifies content.

## Reporting bugs

Use the bug template. For RTL rendering questions include: OS, browser, font stack, and a minimal HTML snippet.

## Native-language review program

RAAST automates the mechanical half of RTL correctness — the rule engine, the corpus verifier, the benchmark and the i18n gate check what a machine can check: physical CSS, missing `dir`, ZWNJ compound *shape*, digit and punctuation classes, placeholder sets. What no engine can judge is whether the language itself reads right: idiomatic phrasing, cultural correctness, and typographic nuance in examples and corpus text. That judgment belongs to native speakers, which is why this program exists.

Honest starting point: much of the bundled Persian/Arabic/Hebrew example copy in `corpus/samples/` and `skills/` was written by non-native contributors. It is machine-verified against the profiles, but it has not been native-reviewed — and that gap is exactly what this program closes. (Adding a *new* language profile, e.g. Urdu, is a separate track — see "Adding a language profile" above; this program reviews the existing fa/ar/he/es artifacts.)

### Languages and scope

| Language | Review scope |
|---|---|
| Persian (`fa`) | ZWNJ compound correctness (می‌ + verb, noun + ‌ها) in corpus and docs |
| Arabic (`ar`) | Arabic-script examples and digit/punctuation conventions |
| Hebrew (`he`) | Hebrew examples and niqqud handling |
| Spanish (`es`) | Spanish prose conventions and RTL-fragment isolation examples |

### What reviewers review

- `corpus/samples/*/broken.html` + `fixed.html` — the specimen prose
- `skills/*/SKILL.md` — the example snippets agents will imitate
- `skills/rtl-typography/fonts.md` — the Persian/Arabic font-catalog entries
- `raast/profiles/<lang>.json` — the convention declarations (digits, punctuation, affixes, fonts, dates)
- `benchmarks/cases/*.json` — task wording and expected behavior
- docs examples (`docs/*.md` sample copy)

Concrete questions per language and the full process: [docs/review-program.md](docs/review-program.md).

### How to join

1. Open a GitHub issue using the **Native review** issue template: state your language, your focus areas, and the artifacts you intend to review.
2. A maintainer confirms the scope on the issue.
3. You open normal PRs from your own account — same ground rules as any other contribution (tests still green, corpus still 32/32).

### Credit policy

Reviewers are credited in CONTRIBUTORS.md (the file is created with the first credit) and in the release notes of the version that lands their review. Review PRs are authored by the reviewer's own GitHub account — credit follows authorship, merged PR by merged PR.

### Status

Status: the program is open as of v0.4.2. No completed native reviews have been published yet — every language is awaiting its first reviewer. Review claims are tracked via the Native review issue template.
