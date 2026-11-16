#!/usr/bin/env python3
"""Compatibility matrix generator for RAAST.

Runs the real RAAST engine (the `doctor` CLI) against every fixture project
listed in fixtures/compat/manifest.json and generates docs/compatibility-matrix.md
from the actual run results. Nothing in the generated table is hand-written:
each detected rule id comes from parsing the doctor JSON output of a real run.

Usage:
    python3 tools/compat/run_matrix.py                  # run fixtures, write the doc
    python3 tools/compat/run_matrix.py --check          # exit 1 if the committed doc is stale
    python3 tools/compat/run_matrix.py --output PATH    # write elsewhere
    python3 tools/compat/run_matrix.py --format json    # print raw matrix JSON, write nothing

Exit codes:
    0  all fixtures passed (and, under --check, the doc is fresh)
    1  at least one fixture FAILED, or the committed doc is stale under --check
    2  usage error (missing/invalid manifest, unknown language, missing fixture dir)

Determinism: the output contains the engine version and counts but NO
timestamps, so `--check` is stable across runs with identical inputs.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "fixtures" / "compat" / "manifest.json"
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "compatibility-matrix.md"
VALID_LANGUAGES = {"fa", "ar", "he", "es"}
REQUIRED_KEYS = {"name", "path", "language", "expect_rules", "notes"}


class UsageError(Exception):
    """Raised for manifest/invocation problems; maps to exit code 2."""


def engine_version() -> str:
    """Read the version from the raast package itself (same source the CLI prints)."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from raast import __version__

    return __version__


def load_manifest() -> list[dict]:
    if not MANIFEST_PATH.exists():
        raise UsageError(f"manifest not found: {MANIFEST_PATH}")
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise UsageError(f"manifest is not valid JSON: {e}") from e
    if not isinstance(data, list) or not data:
        raise UsageError("manifest must be a non-empty JSON array")
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise UsageError(f"manifest entry #{i} must be an object")
        missing = REQUIRED_KEYS - set(entry)
        if missing:
            raise UsageError(f"manifest entry #{i} ({entry.get('name', '?')}) missing key(s): {sorted(missing)}")
        if entry["language"] not in VALID_LANGUAGES:
            raise UsageError(
                f"manifest entry {entry['name']}: language {entry['language']!r} "
                f"not in {sorted(VALID_LANGUAGES)}"
            )
        if not all(isinstance(r, str) and r.startswith("RTL") for r in entry["expect_rules"]):
            raise UsageError(f"manifest entry {entry['name']}: expect_rules must be RTL ids")
        if "|" in entry["notes"]:
            raise UsageError(f"manifest entry {entry['name']}: notes must not contain '|'")
    return data


def run_engine(fixture_dir: Path, language: str) -> tuple[list[dict] | None, str | None]:
    """Run `doctor <fixture> --language <lang> --format json` via subprocess.

    Returns (findings, None) or (None, error_message). The CLI exits 0 when no
    finding is at/above fail_on and 1 when findings exist — both are normal
    outcomes and the JSON is parsed either way. Exit code 2 means the CLI
    itself failed (bad config/profile) and is surfaced as an error.
    """
    cmd = [
        sys.executable, "-m", "raast.cli", "doctor", str(fixture_dir),
        "--language", language, "--format", "json",
    ]
    try:
        proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return None, "doctor timed out after 60s"
    if proc.returncode not in (0, 1):
        detail = (proc.stderr.strip() or proc.stdout.strip())[:300]
        return None, f"doctor exited {proc.returncode}: {detail}"
    stdout = proc.stdout
    brace = stdout.find("{")  # tolerate any leading non-JSON noise
    if brace < 0:
        return None, "doctor produced no JSON object on stdout"
    try:
        payload = json.loads(stdout[brace:])
    except json.JSONDecodeError as e:
        return None, f"doctor JSON unparsable: {e}"
    findings = payload.get("findings")
    if not isinstance(findings, list):
        return None, "doctor JSON has no findings list"
    return findings, None


def fixture_files(fixture_dir: Path) -> list[str]:
    """Sorted relative paths of the files actually scanned in the fixture."""
    return sorted(p.relative_to(fixture_dir).as_posix() for p in fixture_dir.rglob("*") if p.is_file())


def build_matrix(entries: list[dict]) -> dict:
    """Execute every fixture run and assemble the raw matrix data structure."""
    version = engine_version()
    fixtures: list[dict] = []
    for entry in entries:
        name = entry["name"]
        fixture_dir = (REPO_ROOT / entry["path"]).resolve()
        expect = sorted(set(entry["expect_rules"]))
        record: dict = {
            "name": name,
            "path": entry["path"],
            "language": entry["language"],
            "files": fixture_files(fixture_dir) if fixture_dir.is_dir() else [],
            "expect_rules": expect,
            "notes": entry["notes"],
        }
        if not fixture_dir.is_dir():
            record.update({"verdict": "FAIL", "error": f"fixture directory missing: {entry['path']}",
                           "detected_rules": [], "detected_counts": {}, "missing_rules": expect,
                           "extra_rules": [], "severity_counts": {}})
        else:
            findings, error = run_engine(fixture_dir, entry["language"])
            if error is not None:
                record.update({"verdict": "FAIL", "error": error, "detected_rules": [],
                               "detected_counts": {}, "missing_rules": expect,
                               "extra_rules": [], "severity_counts": {}})
            else:
                detected: dict[str, int] = {}
                severities = {"P0": 0, "P1": 0, "P2": 0}
                for f in findings:
                    detected[f["rule"]] = detected.get(f["rule"], 0) + 1
                    severities[f["severity"]] = severities.get(f["severity"], 0) + 1
                detected_sorted = sorted(detected)
                missing = [r for r in expect if r not in detected]
                extras = [r for r in detected_sorted if r not in expect]
                record.update({
                    "verdict": "PASS" if not missing else "FAIL",
                    "detected_rules": detected_sorted,
                    "detected_counts": {r: detected[r] for r in detected_sorted},
                    "missing_rules": missing,
                    "extra_rules": extras,
                    "severity_counts": severities,
                })
        fixtures.append(record)

    passed = sum(1 for f in fixtures if f["verdict"] == "PASS")
    return {
        "engine_version": version,
        "command": "python3 -m raast.cli doctor <fixture> --language <lang> --format json",
        "fixtures_passing": passed,
        "fixtures_total": len(fixtures),
        "fixtures": fixtures,
    }


def _rules_cell(rec: dict) -> str:
    """Render the 'Rules exercised (expect → detected)' table cell."""
    expect = ", ".join(rec["expect_rules"]) if rec["expect_rules"] else "(none)"
    if rec.get("error"):
        return f"{expect} → engine error: {rec['error']}"
    detected = ", ".join(f"{r}({rec['detected_counts'][r]})" for r in rec["detected_rules"]) or "(none)"
    cell = f"{expect} → {detected}"
    if rec["missing_rules"]:
        cell += f" — MISSING: {', '.join(rec['missing_rules'])}"
    return cell


def render_markdown(matrix: dict) -> str:
    """Deterministic markdown rendering: version + counts only, no timestamps."""
    lines: list[str] = []
    lines.append("# Compatibility Matrix")
    lines.append("")
    lines.append(
        "Generated from real runs of the engine against fixture projects — "
        "regenerate with `tools/compat/run_matrix.py`; do not edit by hand."
    )
    lines.append("")
    lines.append(f"- Engine: RAAST `{matrix['engine_version']}` (`raast.__version__`)")
    lines.append(f"- Command per fixture: `{matrix['command']}`")
    lines.append(
        f"- Summary: **{matrix['fixtures_passing']}/{matrix['fixtures_total']} fixtures passing** "
        "(PASS = every expected rule fired; extra detections are allowed and listed)"
    )
    lines.append("")
    lines.append("| Framework stack | Files | Language | Rules exercised (expect → detected) | Verdict | Notes |")
    lines.append("|---|---|---|---|---|---|")
    for rec in matrix["fixtures"]:
        files = ", ".join(f"`{f}`" for f in rec["files"]) or "(none)"
        lines.append(
            f"| {rec['name']} | {files} | {rec['language']} "
            f"| {_rules_cell(rec)} | {rec['verdict']} | {rec['notes']} |"
        )
    lines.append("")
    lines.append("## What this matrix proves / does not prove")
    lines.append("")
    lines.append("Proves:")
    lines.append("")
    lines.append(
        "- The engine's rules fire on these frameworks' *source files* as written: every "
        "detected rule id above was emitted by an actual `doctor` run against the fixture "
        "directory, with the fixture's language profile."
    )
    lines.append(
        "- The evidence gate behaves as documented: CSS/Tailwind rules only fire in files that "
        "themselves contain RTL-script text, so fixtures embed realistic Persian/Arabic strings "
        "to arm them — and the correct logical-property blocks stay silent."
    )
    lines.append(
        "- CSS-in-JS style objects are first-class: camelCase declarations (marginLeft, "
        "textAlign) are normalized to kebab-case before matching and fire the same rules, "
        "with camelCase logical-property fixes. Vendor-cased names normalize with a leading "
        "hyphen. The react-jsx fixture carries both spellings."
    )
    lines.append(
        "- The verdicts are reproducible: `run_matrix.py --check` re-runs every fixture and "
        "compares this file byte-for-byte."
    )
    lines.append("")
    lines.append("Does not prove:")
    lines.append("")
    lines.append(
        "- Rendering correctness in a browser. Static lexical matching cannot see computed "
        "styles, cascade order or runtime layout — use the RAAST runtime inspect / browser "
        "suite (`browser/`) for behavioral verification."
    )
    lines.append(
        "- Framework-internal behavior: Tailwind JIT class generation, CSS Modules hashing, "
        "Vue SFC compilation and Next.js runtime styling are not modeled; the scanner reads "
        "source text only."
    )
    lines.append(
        "- That camelCase coverage is total: property names are normalized before matching, "
        "but shorthand and vendor-prefixed forms beyond the known prefixes (Webkit, Moz, ms, "
        "O, Khtml) are not specially modeled. The react-jsx fixture documents the supported "
        "spellings."
    )
    lines.append("")
    lines.append("## Commands actually executed")
    lines.append("")
    lines.append("```text")
    for rec in matrix["fixtures"]:
        lines.append(
            f"python3 -m raast.cli doctor {rec['path']} --language {rec['language']} --format json"
        )
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_matrix.py",
        description="Run the RAAST engine against compat fixtures and generate docs/compatibility-matrix.md.",
    )
    parser.add_argument("--check", action="store_true",
                        help="regenerate into a temp file and compare with the committed doc; exit 1 if stale")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT),
                        help=f"output path (default: {DEFAULT_OUTPUT.relative_to(REPO_ROOT)})")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown",
                        help="json prints the raw matrix JSON and writes nothing")
    args = parser.parse_args(argv)

    if args.check and args.format == "json":
        print("error: --check and --format json are mutually exclusive", file=sys.stderr)
        return 2

    try:
        entries = load_manifest()
    except UsageError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    matrix = build_matrix(entries)

    if args.format == "json":
        print(json.dumps(matrix, ensure_ascii=False, indent=2))
    elif args.check:
        out = Path(args.output)
        if not out.is_absolute():
            out = REPO_ROOT / out
        if not out.exists():
            print(f"stale: {out} does not exist — run: python3 tools/compat/run_matrix.py", file=sys.stderr)
            return 1
        fresh = render_markdown(matrix)
        current = out.read_text(encoding="utf-8")
        if current != fresh:
            for i, (a, b) in enumerate(zip(current.splitlines(), fresh.splitlines()), 1):
                if a != b:
                    print(f"stale: {out} differs from a fresh run at line {i}:", file=sys.stderr)
                    print(f"  committed: {a[:120]}", file=sys.stderr)
                    print(f"  fresh:     {b[:120]}", file=sys.stderr)
                    break
            else:
                print(f"stale: {out} differs from a fresh run (length {len(current.splitlines())} "
                      f"vs {len(fresh.splitlines())} lines)", file=sys.stderr)
            print("regenerate with: python3 tools/compat/run_matrix.py", file=sys.stderr)
            return 1
        print(f"ok: {out} is fresh ({matrix['fixtures_passing']}/{matrix['fixtures_total']} fixtures passing)")
    else:
        out = Path(args.output)
        if not out.is_absolute():
            out = REPO_ROOT / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_markdown(matrix), encoding="utf-8")
        print(f"wrote {out} — {matrix['fixtures_passing']}/{matrix['fixtures_total']} fixtures passing "
              f"(engine {matrix['engine_version']})")
        for rec in matrix["fixtures"]:
            if rec["verdict"] == "FAIL":
                why = rec.get("error") or f"missing rules: {', '.join(rec['missing_rules'])}"
                print(f"  FAIL {rec['name']}: {why}", file=sys.stderr)

    return 0 if matrix["fixtures_passing"] == matrix["fixtures_total"] else 1


if __name__ == "__main__":
    sys.exit(main())
