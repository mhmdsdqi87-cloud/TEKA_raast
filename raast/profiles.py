"""Language profiles — machine-readable RTL conventions.

Single source of truth shared with the skills prose: raast/profiles/*.json
drive the prose rules so text rules and documentation never drift apart.
Languages: fa (Persian), ar (Arabic), he (Hebrew) — all RTL — plus es
(Spanish), the first LTR host profile for pages embedding RTL content.

Profiles ship INSIDE the raast package (declared as package-data in
pyproject.toml) so that `pip install raast` works everywhere — repo source,
wheel, sdist, editable, and zipapp installs all resolve the same path.
Loading anchors on importlib.resources first (zip-safe) with a filesystem
fallback; failures raise ProfileError listing what IS available instead of a
raw FileNotFoundError, so first-time users get an actionable message.
"""

import json
from importlib import resources
from pathlib import Path

_FALLBACK_DIR = Path(__file__).resolve().parent / "profiles"

PROFILE_CACHE: dict = {}


class ProfileError(ValueError):
    """Raised when a language profile is missing or unreadable."""


def _profile_resource(lang: str):
    """Return a readable Traversable/Path for <lang>.json, or None."""
    try:
        anchor = resources.files("raast") / "profiles" / f"{lang}.json"
        if anchor.is_file():
            return anchor
    except Exception:
        pass
    path = _FALLBACK_DIR / f"{lang}.json"
    return path if path.is_file() else None


def load_profile(lang: str) -> dict:
    """Load a language profile by code (fa, ar, he, es). Cached per process."""
    lang = lang.lower()
    if lang in PROFILE_CACHE:
        return PROFILE_CACHE[lang]
    res = _profile_resource(lang)
    if res is None:
        raise ProfileError(
            f"unknown language profile: {lang!r} — available: {', '.join(available_profiles())}"
        )
    try:
        profile = json.loads(res.read_text(encoding="utf-8"))
    except Exception as e:  # unreadable/corrupt profile — never a raw traceback
        raise ProfileError(f"profile {lang!r} is unreadable: {e}") from e
    PROFILE_CACHE[lang] = profile
    return profile


def available_profiles() -> list[str]:
    """Sorted language codes that ship with the installed package."""
    try:
        anchor = resources.files("raast") / "profiles"
        names = sorted(
            p.name[:-5] for p in anchor.iterdir()
            if p.name.endswith(".json") and not p.name.startswith(".")
        )
        if names:
            return names
    except Exception:
        pass
    return sorted(
        p.stem for p in _FALLBACK_DIR.glob("*.json") if not p.name.startswith(".")
    )
