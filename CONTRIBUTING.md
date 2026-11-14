# Contributing

Thanks for your interest in RAAST. This project optimizes for **correctness over volume** — we would rather have one verified rule than five plausible ones.

## Development setup

```bash
git clone https://github.com/mhmdsdqi87-cloud/TEKA_raast.git
cd TEKA_raast
pip install -e .
python3 -m unittest discover -s tests -v     # must be green before any PR
cd browser && npm install && npx playwright install chromium
```

## Repository layout

```
raast/        CLI engine (Python, stdlib only)   tests/      unit + e2e (stdlib unittest)
skills/       six agent skills (SKILL.md)        benchmarks/ cases + validators + reference
browser/      Playwright suite (Node)            profiles/   fa.json / ar.json
action/       GitHub Action (composite)          docs/       all documentation
demo/         demo artifact produced by the skills
```

## Ground rules

1. **No new runtime dependencies in the CLI** — stdlib only. The browser suite may add devDependencies, pinned.
2. **Every rule ships with tests** — including a false-positive case (the rule must NOT fire on legitimate patterns).
3. **Every falsifiable claim needs an artifact** — benchmark numbers come from `raast benchmark` output; never edit results files by hand.
4. **Normalization changes** must follow `skills/rtl-typography/references/normalization.md` — additions need the ambiguity analysis filled in.
5. **Unicode discipline**: tests must include real Persian/Arabic strings (ZWNJ, digits, punctuation) — no transliterated placeholders.

## Adding a language profile (native speakers especially welcome)

1. Copy `profiles/fa.json` → `profiles/he.json` (or ur) and fill every field; do not guess — mark fields you are unsure about with `"$review": true`.
2. Add prose rules wiring in `raast/rules` behind the profile (no hard-coded language checks).
3. Add at least 3 benchmark cases using the new profile.
4. Open the PR titled `profiles: add <lang>` — a maintainer will pair with you on review.

## Pull requests

- One logical change per PR; include: what/why, test evidence (paste real command output), docs updates.
- CI must pass: unit tests, benchmark self-validation (condition C), and the repo's own doctor scan (P0-free).
- Descriptions in English; Persian is welcome in comments where it clarifies content.

## Reporting bugs

Use the bug template. For RTL rendering questions include: OS, browser, font stack, and a minimal HTML snippet.
