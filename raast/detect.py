"""Framework / project detection.

Evidence-based: a framework is only claimed when its marker appears where it
should (e.g. a dependency inside package.json, not merely a file name).
"""
from __future__ import annotations

import json
import re
from pathlib import Path


def _load_package_json(root: Path) -> dict | None:
    pj = root / "package.json"
    if pj.exists():
        try:
            return json.loads(pj.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _deps(pj: dict | None) -> set[str]:
    if not pj:
        return set()
    return set(pj.get("dependencies", {})) | set(pj.get("devDependencies", {}))


def detect(root: Path) -> dict:
    """Detect frameworks in *root*. Returns evidence-backed findings."""
    deps = _deps(_load_package_json(root))
    frameworks: dict[str, bool] = {}
    evidence: dict[str, list[str]] = {}

    def claim(name: str, evidence_list: list[str]) -> None:
        frameworks[name] = True
        evidence[name] = evidence_list

    # JS frameworks: require package.json dependency (not a lone file).
    if "next" in deps:
        claim("next", ["package.json: dependencies.next"])
    if "react" in deps:
        claim("react", ["package.json: dependencies.react"])
    if "vite" in deps:
        claim("vite", ["package.json: dependencies.vite"])
    if "vue" in deps:
        claim("vue", ["package.json: dependencies.vue"])
    if "svelte" in deps:
        claim("svelte", ["package.json: dependencies.svelte"])
    if "astro" in deps:
        claim("astro", ["package.json: dependencies.astro"])

    # Tailwind: dependency OR config file present together with css usage.
    tw_markers = []
    if "tailwindcss" in deps:
        tw_markers.append("package.json: dependencies.tailwindcss")
    for cfg in ("tailwind.config.js", "tailwind.config.ts", "tailwind.config.mjs", "tailwind.config.cjs"):
        if (root / cfg).exists():
            tw_markers.append(cfg)
    if (root / "src").exists() and list(root.glob("src/**/*.css")) and tw_markers:
        tw_markers.append("css files present under src/")
    if tw_markers:
        claim("tailwindcss", tw_markers)

    # Plain HTML/CSS project (no package.json OR html files present).
    html_files = list(root.glob("*.html")) + list(root.glob("src/**/*.html")) + list(root.glob("public/**/*.html"))
    css_files = list(root.glob("*.css")) + list(root.glob("src/**/*.css")) + list(root.glob("public/**/*.css"))
    if html_files:
        claim("html", [f"{len(html_files)} .html file(s)"])
    if css_files:
        claim("css", [f"{len(css_files)} .css file(s)"])

    # CSS frameworks (only via dependency evidence).
    if "bootstrap" in deps:
        claim("bootstrap", ["package.json: dependencies.bootstrap"])
    if "sass" in deps or "node-sass" in deps:
        claim("sass", ["package.json: sass dependency"])

    return {
        "root": str(root),
        "frameworks": {k: v for k, v in frameworks.items() if v},
        "evidence": evidence,
        "has_package_json": (root / "package.json").exists(),
    }
