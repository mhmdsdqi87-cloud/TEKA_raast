<!-- Describe the change; one section per deliverable. Remove what does not apply. -->

## What and why

<!-- What does this PR change, and which defect or gap does it address? Link the issue with "Fixes #...". -->

## Test evidence

```
<!-- paste REAL output of the commands you ran -->
$ python3 -m unittest discover -s tests
...

$ raast doctor <fixture> --format json
...
```

- [ ] `python3 -m unittest discover -s tests` passes
- [ ] New/changed rules: reproduction added (a corpus specimen with `broken.html` + `fixed.html`, or a unit fixture) and `python3 tools/corpus/verify.py` passes
- [ ] Engine changes: `python3 tools/compat/run_matrix.py --check` still passes (regenerate with `python3 tools/compat/run_matrix.py` if the matrix legitimately changed)
- [ ] Suggested-fix strings updated for any rule whose fix text changed
- [ ] Docs updated (docs/cli-reference.md / the relevant docs page)
- [ ] No new runtime dependencies (the CLI core stays stdlib-only)
- [ ] Benchmark results not hand-edited

## False-positive check

<!-- Static rules are evidence-gated: they must stay silent on RTL-free files. Did you verify the rule does not fire on clean input? -->

## Severity and tier

<!-- New finding: severity (P0/P1/P2) and auto-fix tier (safe / suggested / manual) — see docs/auto-fix.md for the tier policy. -->
