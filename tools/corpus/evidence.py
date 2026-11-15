#!/usr/bin/env python3
"""Render before/after screenshots for every corpus specimen.

For each specimen (or only the one named with --only CS-xxx): launches
headless Chromium at the viewport declared in sample.json, opens broken.html
and fixed.html via file:// URLs, waits 300 ms for layout, and takes full-page
screenshots to evidence/before.png and evidence/after.png. Idempotent —
re-runs overwrite the existing screenshots.

Requires playwright + chromium. If the import fails the script explains how
to install them and exits 2.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_viewport(spec: str) -> tuple[int, int]:
    try:
        width, height = spec.lower().split("x", 1)
        return int(width), int(height)
    except (ValueError, AttributeError):
        raise SystemExit(f"error: bad viewport {spec!r} in sample.json (expected WIDTHxHEIGHT)")


def main() -> int:
    parser = argparse.ArgumentParser(description="render corpus before/after screenshots")
    parser.add_argument("--corpus", default=str(REPO_ROOT / "corpus"),
                        help="path to the corpus directory (default: <repo>/corpus)")
    parser.add_argument("--only", default=None, metavar="CS-xxx",
                        help="render a single specimen by id")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "playwright is not installed — run: pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        return 2

    samples_dir = Path(args.corpus) / "samples"
    dirs = sorted(p for p in samples_dir.iterdir() if p.is_dir() and (p / "sample.json").exists())
    if args.only:
        dirs = [d for d in dirs if json.loads((d / "sample.json").read_text(encoding="utf-8")).get("id") == args.only]
        if not dirs:
            print(f"error: no specimen with id {args.only}", file=sys.stderr)
            return 2

    count = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        for d in dirs:
            meta = json.loads((d / "sample.json").read_text(encoding="utf-8"))
            width, height = parse_viewport(meta.get("viewport", "1280x800"))
            evidence_dir = d / "evidence"
            evidence_dir.mkdir(parents=True, exist_ok=True)
            page = browser.new_page(viewport={"width": width, "height": height})
            try:
                for src, out in (
                    (d / "broken.html", evidence_dir / "before.png"),
                    (d / "fixed.html", evidence_dir / "after.png"),
                ):
                    page.goto(src.as_uri())
                    page.wait_for_timeout(300)
                    page.screenshot(path=str(out), full_page=True)
                    count += 1
            finally:
                page.close()
            print(f"rendered {meta['id']} ({meta['viewport']})")
        browser.close()
    print(f"done: {count} screenshot(s) across {len(dirs)} specimen(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
