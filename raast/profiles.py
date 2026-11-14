"""Language profiles — machine-readable RTL conventions.

Single source of truth shared with the skills prose: profiles/fa.json and
profiles/ar.json drive the prose rules so text rules and documentation never
drift apart. Future languages (he, ur) plug in by adding a profile file.
"""

import json
from pathlib import Path

PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"

PROFILE_CACHE: dict = {}


def load_profile(lang: str) -> dict:
    """Load a language profile by code (fa, ar). Cached per process."""
    lang = lang.lower()
    if lang in PROFILE_CACHE:
        return PROFILE_CACHE[lang]
    path = PROFILES_DIR / f"{lang}.json"
    if not path.exists():
        raise FileNotFoundError(f"unknown language profile: {lang!r} (no {path})")
    profile = json.loads(path.read_text(encoding="utf-8"))
    PROFILE_CACHE[lang] = profile
    return profile


def available_profiles():
    return sorted(p.stem for p in PROFILES_DIR.glob("*.json"))
