## What & why

<!-- one paragraph -->

## Test evidence

```
<!-- paste REAL output of the commands you ran -->
$ python3 -m unittest discover -s tests
...
$ raast doctor <fixture> --format json
...
```

## Checklist
- [ ] `python3 -m unittest discover -s tests` green
- [ ] New rule/validator includes a false-positive test
- [ ] Docs updated (cli-reference / methodology / skill files)
- [ ] No new runtime dependencies (CLI stays stdlib-only)
- [ ] Benchmark results not hand-edited
