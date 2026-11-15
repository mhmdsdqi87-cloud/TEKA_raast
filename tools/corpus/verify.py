#!/usr/bin/env python3
"""Machine-verify the RAAST bug corpus.

For every specimen (corpus/samples/CS-*):
  1. scans broken.html with the real CLI (`python3 -m raast.cli doctor ... --format json`)
     under the language declared in sample.json and compares the fired rule-id set
     against sample.json.rule_ids — PASS requires every claimed id to fire;
  2. checks the observed finding count against sample.json.expected_findings;
  3. scans fixed.html under the same language and requires ZERO P0/P1 findings —
     a fixed specimen must be clean.

Prints a PASS/FAIL table and exits 1 if any specimen fails. Extra findings on
broken.html (rule ids fired but not claimed) are allowed but reported.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VALID_RULES = {f"RTL{n:03d}" for n in range(1, 18)}


def scan(path: Path, language: str) -> list[dict]:
    """Run the real CLI doctor on one file; return its findings list."""
    proc = subprocess.run(
        [sys.executable, "-m", "raast.cli", "doctor", str(path),
         "--language", language, "--format", "json"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    if proc.returncode not in (0, 1):
        raise RuntimeError(
            f"doctor failed on {path} (exit {proc.returncode}): {proc.stderr.strip()}"
        )
    data = json.loads(proc.stdout)
    return data.get("findings", [])


def verify_sample(sample_dir: Path) -> dict:
    meta = json.loads((sample_dir / "sample.json").read_text(encoding="utf-8"))
    language = meta["language"]
    claimed: list[str] = meta.get("rule_ids", [])
    expected = meta.get("expected_findings")

    broken_findings = scan(sample_dir / "broken.html", language)
    fired = [f["rule"] for f in broken_findings]
    fired_set = set(fired)

    problems: list[str] = []
    unknown = [r for r in claimed if r not in VALID_RULES]
    if unknown:
        problems.append(f"invalid rule id(s) in rule_ids: {', '.join(unknown)}")
    missing = [r for r in claimed if r not in fired_set]
    if missing:
        problems.append(f"claimed rule(s) did NOT fire: {', '.join(missing)}")
    if expected is not None and len(broken_findings) != expected:
        problems.append(
            f"expected_findings={expected} but doctor reported {len(broken_findings)}"
        )

    fixed_findings = scan(sample_dir / "fixed.html", language)
    fixed_p0p1 = [f for f in fixed_findings if f["severity"] in ("P0", "P1")]
    if fixed_p0p1:
        problems.append(
            "fixed.html is NOT clean: "
            + "; ".join(f"{f['rule']} ({f['severity']}) line {f['line']}" for f in fixed_p0p1)
        )

    extras = sorted(fired_set - set(claimed))
    return {
        "id": meta["id"],
        "category": meta["category"],
        "language": language,
        "claimed": claimed,
        "fired_count": len(broken_findings),
        "fired": fired,
        "extras": extras,
        "fixed_findings": len(fixed_findings),
        "problems": problems,
        "ok": not problems,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="verify RAAST bug corpus specimens")
    parser.add_argument("--corpus", default=str(REPO_ROOT / "corpus"),
                        help="path to the corpus directory (default: <repo>/corpus)")
    args = parser.parse_args()
    corpus = Path(args.corpus)
    samples_dir = corpus / "samples"
    sample_dirs = sorted(p for p in samples_dir.iterdir() if p.is_dir())
    if not sample_dirs:
        print(f"error: no specimens found under {samples_dir}", file=sys.stderr)
        return 2

    results = []
    for d in sample_dirs:
        try:
            results.append(verify_sample(d))
        except Exception as e:  # noqa: BLE001 — report and continue
            results.append({
                "id": d.name, "category": "?", "language": "?",
                "claimed": [], "fired_count": 0, "fired": [], "extras": [],
                "fixed_findings": 0,
                "problems": [f"verification error: {e}"], "ok": False,
            })

    width = max(len(r["id"]) for r in results) + len("-") + 20
    print(f"{'specimen':<{width}} {'lang':<5} {'claimed':<22} {'fired':>5} {'fixed':>5}  result")
    print("-" * (width + 55))
    for r in results:
        claimed = ",".join(r["claimed"]) or "-"
        name = r["id"]
        status = "PASS" if r["ok"] else "FAIL"
        print(f"{name:<{width}} {r['language']:<5} {claimed:<22} "
              f"{r['fired_count']:>5} {r['fixed_findings']:>5}  {status}")
        if r["extras"]:
            print(f"{'':<{width}} note: extra rule(s) fired but unclaimed: {', '.join(r['extras'])}")
        for problem in r["problems"]:
            print(f"{'':<{width}} -> {problem}")

    passed = sum(1 for r in results if r["ok"])
    failed = len(results) - passed
    print("-" * (width + 55))
    print(f"{passed}/{len(results)} specimens PASS, {failed} FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
