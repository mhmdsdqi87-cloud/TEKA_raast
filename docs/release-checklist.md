# Release checklist (vX.Y.Z)

1. [ ] `python3 -m unittest discover -s tests` green
2. [ ] `raast benchmark --cases benchmarks/cases --candidate benchmarks/reference --condition C-reference` 24/24
3. [ ] `raast doctor . --fail-on P0` clean on this repository
4. [ ] Browser suite green on demo + one live URL (3 viewports)
5. [ ] `raast --version` bumped in `raast/__init__.py` and `pyproject.toml`
6. [ ] CHANGELOG.md updated with date
7. [ ] docs/implementation-roadmap.md statuses reviewed (no stale "done")
8. [ ] Skill frontmatter re-validated (name/description constraints)
9. [ ] No secrets, no generated artifacts (node_modules, .raast-backup, results of private runs) committed
10. [ ] Git tag `vX.Y.Z` on main after merge — tags only, no force-push, no history rewrite
