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
from .fixer import fix_file
from .profiles import load_profile
from .report import Report
from .rules import Finding, RuleContext, run_rules, SEVERITY_ORDER
from .scanner import iter_files


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
        "include": ["**/*.{html,css,scss,sass,vue,jsx,tsx,js,ts,mjs,astro,md,mdx,txt}"],
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
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
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
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2
    groups, _count = _scan(root, ctx)
    changed_files = 0
    total_fixes = 0
    backups = []
    dry_run = not args.apply
    for path, rel, content, findings in groups:
        result = fix_file(
            path, rel, findings,
            zwnj=args.zwnj or args.zwnj_punct or args.zwnj_digits,
            lang=ctx.config["language"],
            zwnj_digits=args.zwnj_digits,
            zwnj_punct=args.zwnj_punct,
        )
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
    if dry_run and changed_files:
        print("re-run with --apply to write changes (backups land in .raast-backup/)")
    return 0


def cmd_report(args) -> int:
    root = Path(args.path).resolve()
    try:
        ctx, source = _build_context(root, Path(args.config) if args.config else None)
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
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
        description="RAAST — RTL engineering diagnostics (Persian/Arabic first).",
    )
    p.add_argument("--version", action="version", version=f"raast {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("init", help="write a raast.config.json with detected defaults")
    sp.add_argument("path", nargs="?", default=".")
    sp.add_argument("--language", default="fa", choices=["fa", "ar"])
    sp.add_argument("--force", action="store_true")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("detect", help="detect frameworks (evidence-based)")
    sp.add_argument("path", nargs="?", default=".")
    sp.set_defaults(func=cmd_detect)

    sp = sub.add_parser("doctor", help="static RTL diagnostics")
    sp.add_argument("path", nargs="?", default=".")
    sp.add_argument("--format", choices=["text", "json", "markdown", "github"], default="text")
    sp.add_argument("--fail-on", choices=["P0", "P1", "P2"], default=None)
    sp.add_argument("--language", choices=["fa", "ar"], default=None,
                    help="override config language profile")
    sp.add_argument("--config", default=None)
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("audit", help="doctor (markdown) + manual review checklist")
    sp.add_argument("path", nargs="?", default=".")
    sp.add_argument("--fail-on", choices=["P0", "P1", "P2"], default=None)
    sp.add_argument("--language", choices=["fa", "ar"], default=None,
                    help="override config language profile")
    sp.add_argument("--config", default=None)
    sp.set_defaults(func=cmd_audit)

    sp = sub.add_parser("fix", help="apply safe fixes (dry-run by default)")
    sp.add_argument("path", nargs="?", default=".")
    sp.add_argument("--apply", action="store_true", help="write changes (backups in .raast-backup/)")
    sp.add_argument("--diff", action="store_true", help="show diffs even when applying")
    sp.add_argument("--zwnj", action="store_true", help="also apply safe ZWNJ joins")
    sp.add_argument("--zwnj-digits", action="store_true", help="also convert digits (fa only)")
    sp.add_argument("--zwnj-punct", action="store_true", help="also convert Latin punctuation in prose")
    sp.add_argument("--config", default=None)
    sp.set_defaults(func=cmd_fix)

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
