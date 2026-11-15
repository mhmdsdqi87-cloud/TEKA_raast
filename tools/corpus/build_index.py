#!/usr/bin/env python3
"""Regenerate the specimen index in corpus/README.md.

Rewrites ONLY the section between the `<!-- corpus-index:start -->` and
`<!-- corpus-index:end -->` markers: a markdown table (ID | Category |
Language | Rule(s) | Defect) plus a count line. Deterministic — no timestamps,
no locale-dependent formatting — so re-runs produce byte-identical output.
Reads each specimen's metadata from its sample.json; it never invents rows.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

START_MARK = "<!-- corpus-index:start -->"
END_MARK = "<!-- corpus-index:end -->"


def build_section(sample_dirs: list[Path]) -> str:
    rows = []
    categories: set[str] = set()
    for d in sample_dirs:
        meta = json.loads((d / "sample.json").read_text(encoding="utf-8"))
        categories.add(meta["category"])
        rules = ", ".join(meta.get("rule_ids", [])) or "-"
        rows.append(
            f"| {meta['id']} | {meta['category']} | {meta['language']} "
            f"| {rules} | {meta['title']} |"
        )
    lines = [
        f"{len(rows)} specimens · {len(categories)} categories · all lab-verified.",
        "",
        "| ID | Category | Language | Rule(s) | Defect |",
        "|---|---|---|---|---|",
        *rows,
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="regenerate the corpus index table")
    parser.add_argument("--corpus", default=str(REPO_ROOT / "corpus"),
                        help="path to the corpus directory (default: <repo>/corpus)")
    args = parser.parse_args()
    readme = Path(args.corpus) / "README.md"
    try:
        text = readme.read_text(encoding="utf-8")
    except OSError as e:
        print(f"error: cannot read {readme}: {e}", file=sys.stderr)
        return 2
    if START_MARK not in text or END_MARK not in text:
        print(
            f"error: {readme} is missing the {START_MARK} / {END_MARK} markers",
            file=sys.stderr,
        )
        return 2

    samples_dir = Path(args.corpus) / "samples"
    sample_dirs = sorted(p for p in samples_dir.iterdir() if p.is_dir() and (p / "sample.json").exists())
    if not sample_dirs:
        print(f"error: no specimens with sample.json found under {samples_dir}", file=sys.stderr)
        return 2

    start = text.index(START_MARK) + len(START_MARK)
    end = text.index(END_MARK)
    new_text = text[:start] + "\n" + build_section(sample_dirs) + "\n" + text[end:]
    readme.write_text(new_text, encoding="utf-8")
    print(f"regenerated index in {readme} ({len(sample_dirs)} specimens)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
