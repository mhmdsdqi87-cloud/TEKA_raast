"""RAAST command-line interface.

Zero-dependency (stdlib). Entry point: `raast` console script or
`python3 -m raast.cli`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .benchmark import benchmark_markdown, run_benchmark
from .config import ConfigError, load_config
from .detect import detect
from .fixer import BACKUP_DIRNAME, fix_file, journal_load, revert_all, tier_for
from .profiles import ProfileError, available_profiles, load_profile
from .report import Report
from .rules import Finding, RuleContext, run_rules, SEVERITY_ORDER
from .scanner import iter_files

LANGUAGES = ["fa", "ar", "he", "es"]


def _build_context(root: Path, config_path: Path | None, language: str | None = None) -> tuple[RuleContext, str | None]:
    config, source = load_config(config_path, root)
    if language:
        config["language"] = language
    profile = load_profile(config["language"])
    return RuleContext(config=config, profile=profile), source


def _scan(root: Path, ctx: RuleContext) -> tuple[list[tuple[Path, str, str, list[Finding]]], int]:
    """Return [(path, rel, content, findings)], file_count. Accepts a dir or a single file."""
    results = []
    count = 0
    if root.is_file():
        candidates = [(root, root.name)]
    else:
        candidates = list(iter_files(root, ctx.config["include"], ctx.config["exclude"]))
    for path, rel in candidates:
        count += 1
        content = path.read_text(encoding="utf-8")
        findings = run_rules(path, rel, content, ctx)
        if findings:
            results.append((path, rel, content, findings))
    return results, count


def _collect_report(root: Path, ctx: RuleContext, config_source: str | None, with_frameworks: bool) -> Report:
    groups, count = _scan(root, ctx)
    findings = [f for (_p, _r, _c, fs) in groups for f in fs]
    report = Report(target=str(root), files_scanned=count, findings=findings, config_source=config_source)
    if with_frameworks:
        report.frameworks = detect(root)["frameworks"]
    return report, groups


# ---------------------------------------------------------------- commands


def cmd_init(args) -> int:
    root = Path(args.path).resolve()
    cfg_path = root / "raast.config.json"
    if cfg_path.exists() and not args.force:
        print(f"raast.config.json already exists at {cfg_path} (use --force to overwrite)")
        return 1
    det = detect(root)
    cfg = {
        "language": args.language,
        "include": ["**/*.{html,css,scss,sass,vue,jsx,tsx,js,ts,mjs,astro,svelte,md,mdx,txt}"],
        "exclude": ["node_modules/**", "dist/**", "build/**", ".next/**", "vendor/**", ".raast-backup/**", "**/*.min.css"],
        "severity_overrides": {},
        "rules": {},
        "fail_on": "P1",
    }
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {cfg_path}")
    print(f"detected frameworks: {', '.join(sorted(det['frameworks'])) or 'none'}")
    print("edit `language`, `exclude` and rule options as needed")
    return 0


def cmd_profiles(args) -> int:
    print("available language profiles:")
    for code in available_profiles():
        try:
            p = load_profile(code)
            direction = p.get("direction", "?")
            print(f"  {code:<4} {p.get('name_native', ''):<10} {p.get('name', ''):<12} ({direction})")
        except ProfileError as e:
            print(f"  {code:<4} UNREADABLE: {e}")
            return 2
    return 0


def cmd_detect(args) -> int:
    det = detect(Path(args.path).resolve())
    print(json.dumps(det, indent=2))
    return 0


def _fmt_report(report: Report, fmt: str) -> str:
    if fmt == "json":
        return report.to_json()
    if fmt == "markdown":
        return report.to_markdown()
    if fmt == "github":
        return report.to_github()
    return report.to_text()


def cmd_doctor(args) -> int:
    root = Path(args.path).resolve()
    try:
        ctx, source = _build_context(root, Path(args.config) if args.config else None,
                                     language=getattr(args, "language", None))
    except (ConfigError, ProfileError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    report, _ = _collect_report(root, ctx, source, with_frameworks=True)
    print(_fmt_report(report, args.format))
    fail_on = args.fail_on or ctx.config["fail_on"]
    return 1 if report.should_fail(fail_on) else 0


def cmd_audit(args) -> int:
    """doctor + manual checklist appendix (markdown)."""
    args.format = "markdown"
    code = cmd_doctor(args)
    print(
        """
## Manual checks (not automatable — human review required)

- [ ] Visual contrast >= 4.5:1 for body text in BOTH themes
- [ ] Reading rhythm: line-height >= 1.8 for Persian body copy
- [ ] Translation quality: no machine-translation tone, no lorem ipsum
- [ ] Directional icons match flow (next points left under RTL)
- [ ] Fonts actually render Persian glyphs on target OS (not fallback tofu)
- [ ] prefers-reduced-motion honored for entrance animations
"""
    )
    return code


def cmd_fix(args) -> int:
    root = Path(args.path).resolve()
    try:
        ctx, source = _build_context(root, Path(args.config) if args.config else None)
    except (ConfigError, ProfileError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    groups, _count = _scan(root, ctx)
    changed_files = 0
    total_fixes = 0
    total_findings = sum(len(fs) for (_p, _r, _c, fs) in groups)
    tiers_total: dict[str, int] = {"safe": 0, "suggested": 0}
    addressed_rules: set[str] = set()
    backups = []
    dry_run = not args.apply
    tier = getattr(args, "tier", "safe")
    for path, rel, content, findings in groups:
        result = fix_file(
            path, rel, findings,
            zwnj=args.zwnj or args.zwnj_punct or args.zwnj_digits,
            lang=ctx.config["language"],
            zwnj_digits=args.zwnj_digits,
            zwnj_punct=args.zwnj_punct,
            tier=tier,
        )
        for t, n in result.tiers.items():
            tiers_total[t] = tiers_total.get(t, 0) + n
        addressed_rules.update(result.rules_applied)
        if not result.changed:
            continue
        changed_files += 1
        total_fixes += result.fix_count
        if args.diff or dry_run:
            print(result.diff)
            print()
        if not dry_run:
            from .fixer import apply_fix

            backup = apply_fix(path, rel, result, root=root)
            backups.append(backup)
            print(f"fixed {rel} ({result.fix_count} change(s)) — backup: {backup}")
    print(f"\n{'DRY RUN — ' if dry_run else ''}{total_fixes} fix(es) across {changed_files} file(s)")
    if total_fixes:
        manual_count = sum(
            1 for (_p, _r, _c, fs) in groups for f in fs if tier_for(f.rule) == "manual"
        )
        print(
            f"tier breakdown: safe={tiers_total.get('safe', 0)} "
            f"suggested={tiers_total.get('suggested', 0)} "
            f"manual(review-only)={manual_count}"
        )
    if total_findings:
        skipped = sum(1 for (_p, _r, _c, fs) in groups for f in fs if f.rule not in addressed_rules)
        if skipped:
            print(
                f"{skipped} finding(s) not auto-applied (manual review or opt-in gates) — "
                "use 'raast fix --tier all --zwnj ...' to include suggested fixes"
            )
    if dry_run and changed_files:
        print("re-run with --apply to write changes (backups land in .raast-backup/)")
    return 0


def _backup_files_present(root: Path) -> bool:
    backup_root = root / BACKUP_DIRNAME
    if not backup_root.is_dir():
        return False
    return any(p.is_file() and p.name != "journal.json" for p in backup_root.rglob("*"))


def cmd_revert(args) -> int:
    """Undo applied fixes by restoring the backups recorded in the journal."""
    root = Path(args.path).resolve()
    journal = journal_load(root)
    if not journal:
        if _backup_files_present(root):
            print(
                f"cannot revert: {root / BACKUP_DIRNAME} contains backup copies but no usable "
                f"journal ({BACKUP_DIRNAME}/journal.json is missing, empty or corrupt)"
            )
            print(
                "the journal is the only source of truth for which backup belongs to which "
                "file, so nothing can be restored safely; nothing was changed"
            )
            return 1
        print(f"nothing to revert: no journal and no backups under {root / BACKUP_DIRNAME}")
        return 0
    print(f"revert plan — {len(journal)} journal entr(y/ies) under {root / BACKUP_DIRNAME}:")
    for entry in journal:
        print(f"  restore {entry.get('file')}  <-  {entry.get('backup')}")
    if not args.yes:
        if sys.stdin.isatty():
            try:
                answer = input("apply revert? [y/N] ")
            except EOFError:
                answer = ""
            if answer.strip().lower() not in ("y", "yes"):
                print("aborted — nothing was changed")
                return 0
        else:
            print("re-run with --yes to apply")
            return 0
    restored_count, restored = revert_all(root)
    for rel in restored:
        print(f"restored {rel}")
    print(f"{restored_count} file(s) restored; journal cleared")
    return 0


def cmd_report(args) -> int:
    root = Path(args.path).resolve()
    try:
        ctx, source = _build_context(root, Path(args.config) if args.config else None)
    except (ConfigError, ProfileError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    report, _ = _collect_report(root, ctx, source, with_frameworks=True)
    out = Path(args.output)
    out.write_text(report.to_markdown(), encoding="utf-8")
    print(f"wrote {out} — {report.summary_line()}")
    return 0


def cmd_benchmark(args) -> int:
    cases_dir = Path(args.cases).resolve()
    candidate = Path(args.candidate).resolve()
    condition = args.condition
    report = run_benchmark(cases_dir, candidate, condition)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.output_prefix:
        prefix = Path(args.output_prefix)
        prefix.parent.mkdir(parents=True, exist_ok=True)
        prefix.with_suffix(".json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        prefix.with_suffix(".md").write_text(benchmark_markdown(report) + "\n", encoding="utf-8")
        print(f"wrote {prefix}.json and {prefix}.md")
    s = report["summary"]
    print(
        f"condition={condition} candidate={candidate}\n"
        f"passed {s['passed']}/{s['total']}, failed {s['failed']}, skipped {s['skipped']}"
    )
    for cat, c in sorted(s["categories"].items()):
        print(f"  {cat:<28} {c['passed']}/{c['total']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="raast",
        description="RAAST — RTL engineering diagnostics (Persian, Arabic, Hebrew + Spanish LTR host).",
    )
    p.add_argument("--version", action="version", version=f"raast {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("profiles", help="list available language profiles")
    sp.set_defaults(func=cmd_profiles)

    sp = sub.add_parser("init", help="write a raast.config.json with detected defaults")
    sp.add_argument("path", nargs="?", default=".")
    sp.add_argument("--language", default="fa", choices=LANGUAGES)
    sp.add_argument("--force", action="store_true")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("detect", help="detect frameworks (evidence-based)")
    sp.add_argument("path", nargs="?", default=".")
    sp.set_defaults(func=cmd_detect)

    sp = sub.add_parser("doctor", help="static RTL diagnostics")
    sp.add_argument("path", nargs="?", default=".")
    sp.add_argument("--format", choices=["text", "json", "markdown", "github"], default="text")
    sp.add_argument("--fail-on", choices=["P0", "P1", "P2"], default=None)
    sp.add_argument("--language", choices=LANGUAGES, default=None,
                    help="override config language profile")
    sp.add_argument("--config", default=None)
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("audit", help="doctor (markdown) + manual review checklist")
    sp.add_argument("path", nargs="?", default=".")
    sp.add_argument("--fail-on", choices=["P0", "P1", "P2"], default=None)
    sp.add_argument("--language", choices=LANGUAGES, default=None,
                    help="override config language profile")
    sp.add_argument("--config", default=None)
    sp.set_defaults(func=cmd_audit)

    sp = sub.add_parser("fix", help="apply safe fixes (dry-run by default)")
    sp.add_argument("path", nargs="?", default=".")
    sp.add_argument("--apply", action="store_true", help="write changes (backups in .raast-backup/)")
    sp.add_argument("--diff", action="store_true", help="show diffs even when applying")
    sp.add_argument("--tier", choices=["safe", "all"], default="safe",
                    help="fix tier policy: 'safe' applies only safe-tier fixes; "
                         "'all' also includes suggested-tier fixes, which stay gated by "
                         "--zwnj/--zwnj-digits/--zwnj-punct. Manual-tier findings are "
                         "never auto-applied (review-only). Default: safe")
    sp.add_argument("--zwnj", action="store_true", help="also apply safe ZWNJ joins")
    sp.add_argument("--zwnj-digits", action="store_true", help="also convert digits (fa only; needs --tier all)")
    sp.add_argument("--zwnj-punct", action="store_true", help="also convert Latin punctuation in prose (needs --tier all)")
    sp.add_argument("--config", default=None)
    sp.set_defaults(func=cmd_fix)

    sp = sub.add_parser("revert", help="restore backups recorded in the fix journal")
    sp.add_argument("path", nargs="?", default=".")
    sp.add_argument("--yes", action="store_true", help="apply without confirmation prompt")
    sp.set_defaults(func=cmd_revert)

    sp = sub.add_parser("report", help="write a markdown diagnostics report")
    sp.add_argument("path", nargs="?", default=".")
    sp.add_argument("--output", default="raast-report.md")
    sp.add_argument("--config", default=None)
    sp.set_defaults(func=cmd_report)

    sp = sub.add_parser("benchmark", help="validate an artifact set against benchmark cases")
    sp.add_argument("--cases", default="benchmarks/cases")
    sp.add_argument("--candidate", required=True)
    sp.add_argument("--condition", default="C-reference", help="A-baseline | B-raast | C-reference")
    sp.add_argument("--json", action="store_true", help="print raw JSON report")
    sp.add_argument("--output-prefix", default=None, help="write <prefix>.json and <prefix>.md")
    sp.set_defaults(func=cmd_benchmark)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
