"""RAAST PR review — diff-scoped review engine for pull requests.

Runs the static rule engine over the files changed in a pull request,
keeps only findings that land on lines changed by the PR (see
raast.diffscope), and emits either GitHub workflow annotations or a
markdown PR comment suitable for idempotent posting (one comment per PR,
updated in place via the ``<!-- raast-review -->`` marker).

Usage:
    python3 -m raast.review --base origin/main [--path .] [--config PATH]
        [--fail-on P0|P1|P2|off] [--comment-out FILE]
        [--format markdown|github]

Exit codes:
    0  no findings at/above --fail-on on changed lines
    1  findings at/above the threshold on changed lines
    2  usage or engine error (bad ref, not a git repo, invalid config, ...)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path, PurePosixPath

from .config import ConfigError, load_config
from .diffscope import file_changed_ranges, filter_findings
from .profiles import ProfileError, load_profile
from .rules import Finding, RuleContext, SEVERITY_ORDER, run_rules

# Extensions the rule engine can meaningfully inspect (case-insensitive).
REVIEWED_EXTENSIONS = {
    ".html", ".css", ".scss", ".sass", ".vue", ".jsx", ".tsx", ".js", ".ts",
    ".mjs", ".astro", ".md", ".mdx", ".txt",
}

COMMENT_MARKER = "<!-- raast-review -->"

SEVERITIES = ("P0", "P1", "P2")


def _run_git(workdir: Path, *args: str) -> str:
    """Run a git command in workdir and return stdout. Raises on failure."""
    # core.quotepath=off keeps non-ASCII (e.g. RTL script) file names raw
    # instead of C-quoted, so paths match the scanner's rel paths.
    try:
        proc = subprocess.run(
            ["git", "-c", "core.quotepath=off", *args],
            cwd=str(workdir), check=True, capture_output=True, text=True,
        )
    except FileNotFoundError:
        raise RuntimeError("git executable not found on PATH (or --path does not exist)")
    return proc.stdout


def _build_context(root: Path, config_path: Path | None) -> tuple[RuleContext, str | None]:
    """Build a RuleContext from the repo's raast.config.json (auto-discovered)."""
    config, source = load_config(config_path, root)
    profile = load_profile(config["language"])
    return RuleContext(config=config, profile=profile), source


def _is_reviewed(rel: str) -> bool:
    return PurePosixPath(rel).suffix.lower() in REVIEWED_EXTENSIONS


def _changed_files_and_ranges(root: Path, merge_base: str) -> tuple[list[str], dict[str, list[tuple[int, int]]]]:
    """List changed files (merge-base..HEAD) and parse their changed ranges."""
    names_raw = _run_git(root, "diff", "-U0", "--name-only", merge_base, "HEAD")
    files = [ln.strip() for ln in names_raw.splitlines() if ln.strip()]
    files = [f for f in files if _is_reviewed(f)]
    ranges: dict[str, list[tuple[int, int]]] = {}
    for rel in files:
        diff_text = _run_git(root, "diff", "-U0", merge_base, "HEAD", "--", rel)
        ranges.update(file_changed_ranges(diff_text))
    return files, ranges


def _scan_changed(root: Path, ctx: RuleContext, files: list[str]) -> tuple[list[Finding], int]:
    """Run rules over changed files present in the working tree.

    Returns (findings, scanned_count). Files deleted by the PR are skipped.
    """
    findings: list[Finding] = []
    scanned = 0
    for rel in files:
        path = root / rel
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            print(f"raast-review: skipping unreadable file {rel}: {e}", file=sys.stderr)
            continue
        scanned += 1
        findings.extend(run_rules(path, rel, content, ctx))
    return findings, scanned


def _sort_findings(findings: list[Finding]) -> list[Finding]:
    """Deterministic order: P0 first, then P1, then P2; then file/line/rule."""
    return sorted(
        findings,
        key=lambda f: (SEVERITY_ORDER.get(f.severity, len(SEVERITIES)), f.file, f.line, f.rule),
    )


def _escape_property(value: str) -> str:
    """Escape a GitHub workflow-command property value."""
    return (value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
                 .replace(":", "%3A").replace(",", "%2C"))


def _build_github(findings: list[Finding]) -> str:
    """GitHub workflow-command annotations, one line per finding."""
    lines = []
    for f in _sort_findings(findings):
        cmd = "error" if f.severity in ("P0", "P1") else "warning"
        title = f"{f.rule} ({f.severity})"
        lines.append(
            f"::{cmd} file={_escape_property(f.file)},line={f.line},"
            f"title={_escape_property(title)}::{f.message}"
        )
    return "\n".join(lines)


def _build_comment_markdown(scanned: int, range_count: int, findings: list[Finding]) -> str:
    """Markdown PR comment body (marker first so posting can update in place)."""
    ordered = _sort_findings(findings)
    lines: list[str] = [
        COMMENT_MARKER,
        "## RAAST RTL Review",
        "",
        f"Scanned {scanned} changed file(s), {range_count} changed line range(s). "
        "Reporting only findings on lines changed in this PR.",
    ]
    for sev in SEVERITIES:
        for f in (x for x in ordered if x.severity == sev):
            lines += [
                "",
                f"### {f.severity} — {f.rule} · `{f.file}` · line {f.line}",
                "",
                f"**Issue:** {f.message}",
            ]
            if f.suggested_fix:
                lines += ["", f"**Suggested fix:** {f.suggested_fix}"]
    lines += [
        "",
        "### Summary",
        "",
        "| Severity | Count |",
        "|---|---|",
    ]
    for sev in SEVERITIES:
        lines.append(f"| {sev} | {sum(1 for x in ordered if x.severity == sev)} |")
    blocking = any(x.severity in ("P0", "P1") for x in ordered)
    lines += [
        "",
        "**Status:** Review required." if blocking
        else "**Status:** Passed — no RTL issues on changed lines.",
        "",
        "<sub>Comment is updated in place on every push. "
        "Rule reference: docs/cli-reference.md</sub>",
    ]
    return "\n".join(lines) + "\n"


def _at_or_above(severity: str, threshold: str) -> bool:
    """P0 is most severe; a finding is at/above the threshold when its rank
    is numerically lower or equal (P0=0 < P1=1 < P2=2)."""
    return SEVERITY_ORDER.get(severity, len(SEVERITIES)) <= SEVERITY_ORDER[threshold]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="raast-review",
        description="Diff-scoped RAAST review for pull requests: reports only "
                    "findings on lines changed relative to a base ref.",
    )
    parser.add_argument("--base", required=True,
                        help="git ref to diff against (e.g. origin/main)")
    parser.add_argument("--path", default=".",
                        help="path inside the repository to review (default: .)")
    parser.add_argument("--config", default=None,
                        help="explicit raast.config.json path (auto-discovered from the repo root by default)")
    parser.add_argument("--fail-on", default="P1", choices=["P0", "P1", "P2", "off"],
                        help="severity threshold for exit code 1 (default: P1)")
    parser.add_argument("--comment-out", default=None,
                        help="write the markdown PR comment to this file")
    parser.add_argument("--format", default="markdown", choices=["markdown", "github"],
                        help="stdout report format (default: markdown)")
    args = parser.parse_args(argv)

    workdir = Path(args.path).expanduser().resolve()

    # 1. Repo root (from --path, which may be a subdirectory of the repo).
    try:
        root = Path(_run_git(workdir, "rev-parse", "--show-toplevel").strip())
    except subprocess.CalledProcessError:
        print(f"raast-review: error: {workdir} is not inside a git repository "
              f"(git rev-parse --show-toplevel failed)", file=sys.stderr)
        return 2
    except RuntimeError as e:
        print(f"raast-review: error: {e}", file=sys.stderr)
        return 2

    config_path = Path(args.config).expanduser() if args.config else None
    try:
        # 2. Merge base, changed files, changed line ranges.
        merge_base = _run_git(root, "merge-base", args.base, "HEAD").strip()
        files, ranges = _changed_files_and_ranges(root, merge_base)
        # 3. Rule engine context from the repo's raast.config.json.
        ctx, _source = _build_context(root, config_path)
        findings, scanned = _scan_changed(root, ctx, files)
    except subprocess.CalledProcessError as e:
        detail = (e.stderr or "").strip()
        print(f"raast-review: error: git command failed: {e.cmd}", file=sys.stderr)
        if detail:
            print(detail, file=sys.stderr)
        return 2
    except (RuntimeError, ConfigError, ProfileError) as e:
        print(f"raast-review: error: {e}", file=sys.stderr)
        return 2

    # 4. Keep only findings on changed lines.
    scoped = filter_findings(findings, ranges)
    range_count = sum(len(rs) for rs in ranges.values())

    # 5. Build outputs (stdout report + optional comment file, always markdown).
    comment = _build_comment_markdown(scanned, range_count, scoped)
    if args.format == "github":
        report = _build_github(scoped)
        if report:
            print(report)
    else:
        print(comment, end="")

    if args.comment_out:
        try:
            out_path = Path(args.comment_out).expanduser()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(comment, encoding="utf-8")
        except OSError as e:
            print(f"raast-review: error: cannot write comment file "
                  f"{args.comment_out}: {e}", file=sys.stderr)
            return 2

    print(f"raast-review: {scanned} file(s) scanned, {range_count} changed line "
          f"range(s), {len(scoped)} finding(s) on changed lines", file=sys.stderr)

    # 6. Exit code from the --fail-on threshold (P0 most severe).
    if args.fail_on == "off":
        return 0
    blocked = any(_at_or_above(f.severity, args.fail_on) for f in scoped)
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
