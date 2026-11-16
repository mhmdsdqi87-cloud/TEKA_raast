#!/usr/bin/env python3
"""RAAST performance baseline harness.

Generates a deterministic synthetic repository, scans it with the real
engine, and records wall time, throughput and peak memory to a JSON
baseline. Run it before and after a performance-sensitive change:

    python3 tools/perf_baseline.py --files 600 --out /tmp/baseline-before.json
    # ... change ...
    python3 tools/perf_baseline.py --files 600 --out /tmp/baseline-after.json

The baseline is REPRODUCIBLE: the synthetic tree is generated from a fixed
seed (same file count always produces the same bytes), so numbers from two
runs on the same machine are directly comparable. Absolute numbers vary with
hardware — never compare baselines across machines; compare before/after on
the SAME machine and report both numbers together with the hardware note the
tool prints.

Honesty rules:
  - the harness never fabricates numbers; it measures the real CLI scan
  - a single run has noise; use --repeat N and report the median
  - memory is measured via resource.getrusage (ru_maxrss, kB on Linux)
"""
from __future__ import annotations

import argparse
import json
import platform
import random
import statistics
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from raast import __version__  # noqa: E402
from raast.cli import _build_context, _scan  # noqa: E402

rng = random.Random(20260217)

FA_WORDS = ["پروژه", "می‌شود", "خانه", "کتاب", "بزرگ‌ترین", "داده", "کاربر"]
LATIN_WORDS = ["container", "button", "grid", "value", "state", "layout"]


def _component(idx: int) -> str:
    """One synthetic React-ish component (TSX) with RTL content."""
    fa = " ".join(rng.choice(FA_WORDS) for _ in range(rng.randint(8, 24)))
    en = " ".join(rng.choice(LATIN_WORDS) for _ in range(rng.randint(2, 6)))
    physical = rng.random() < 0.4
    style = ("  marginLeft: '8px',\n" if physical else "  marginInlineStart: '8px',\n")
    cls = (f'className="ml-2 {en}"' if physical else f'className="ms-2 {en}"')
    return (
        f"import React from 'react';\n\n"
        f"export function Card{idx}() {{\n"
        f"  const styles = {{\n"
        f"{style}"
        f"    textAlign: '{'left' if physical else 'start'}',\n"
        f"  }};\n"
        f'  return <div className="card {cls}" style={{styles}}>\n'
        f"    <p>{fa}</p>\n"
        f"    <span dir=\"ltr\">{en}</span>\n"
        f"  </div>;\n"
        f"}}\n"
    )


def _stylesheet(idx: int) -> str:
    fa = " ".join(rng.choice(FA_WORDS) for _ in range(rng.randint(3, 10)))
    physical = rng.random() < 0.5
    margin = "margin-left: 4px;" if physical else "margin-inline-start: 4px;"
    align = "text-align: left;" if physical else "text-align: start;"
    return f".card-{idx} {{\n  {margin}\n  {align}\n  /* {fa} */\n}}\n\n"


def build_synthetic_repo(root: Path, n_components: int) -> int:
    """Deterministic synthetic project. Returns the number of files written."""
    count = 0
    for i in range(n_components):
        d = root / "src" / "components" / f"mod{i // 25}"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"Card{i}.tsx").write_text(_component(i), encoding="utf-8")
        count += 1
        if i % 3 == 0:
            cd = root / "src" / "styles"
            cd.mkdir(parents=True, exist_ok=True)
            (cd / f"card{i}.css").write_text(_stylesheet(i), encoding="utf-8")
            count += 1
    (root / "index.html").write_text(
        '<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "</head><body><main>سلام دنیا</main></body></html>",
        encoding="utf-8",
    )
    return count + 1


def run_once(n_components: int) -> dict:
    import resource

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "proj"
        root.mkdir()
        files = build_synthetic_repo(root, n_components)
        t0 = time.perf_counter()
        ctx, _ = _build_context(root, None, language="fa")
        _results, scanned = _scan(root, ctx)
        elapsed = time.perf_counter() - t0
        peak_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "files_written": files,
        "files_scanned": scanned,
        "wall_seconds": round(elapsed, 4),
        "files_per_second": round(scanned / elapsed, 1) if elapsed else None,
        "peak_rss_kb": peak_kb,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="RAAST performance baseline harness")
    ap.add_argument("--files", type=int, default=600, metavar="N",
                    help="number of synthetic components (default 600)")
    ap.add_argument("--repeat", type=int, default=3, metavar="N",
                    help="repeat the scan N times and report the median (default 3)")
    ap.add_argument("--out", default=None, help="write the JSON baseline here")
    args = ap.parse_args(argv)

    runs = []
    for i in range(max(1, args.repeat)):
        runs.append(run_once(args.files))
        r = runs[-1]
        print(f"run {i + 1}/{args.repeat}: {r['files_scanned']} files, "
              f"{r['wall_seconds']}s, {r['files_per_second']} files/s, "
              f"peak {r['peak_rss_kb']} kB")

    med_wall = statistics.median(r["wall_seconds"] for r in runs)
    med_fps = statistics.median(r["files_per_second"] for r in runs)
    baseline = {
        "tool": "raast-perf-baseline",
        "raast_version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "config": {"files": args.files, "repeat": args.repeat, "seed": rng.__getstate__()[0] if hasattr(rng, "__getstate__") else 20260217},
        "runs": runs,
        "median": {
            "wall_seconds": round(med_wall, 4),
            "files_per_second": round(med_fps, 1),
        },
        "notes": [
            "Same machine before/after comparisons only; absolute numbers are hardware-dependent.",
            "Synthetic tree is deterministic for a given --files value (fixed seed).",
            "Throughput counts scanner-visible text files, not total repo files.",
        ],
    }
    text = json.dumps(baseline, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"baseline written: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
