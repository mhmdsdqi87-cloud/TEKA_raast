"""Configuration loading and schema validation for raast.config.json."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .profiles import available_profiles

DEFAULT_CONFIG: dict = {
    "language": "fa",
    "include": ["**/*.{html,css,scss,sass,vue,jsx,tsx,js,ts,mjs,astro,svelte,md,mdx,txt}"],
    "exclude": [
        "node_modules/**",
        "dist/**",
        "build/**",
        ".next/**",
        "vendor/**",
        ".raast-backup/**",
        "**/*.min.css",
        "**/package-lock.json",
    ],
    "severity_overrides": {},
    "rules": {},
    "fail_on": "P1",
}

VALID_SEVERITIES = {"P0", "P1", "P2"}
VALID_FAIL_ON = {"P0", "P1", "P2", "off"}

KNOWN_KEYS = set(DEFAULT_CONFIG.keys())

# Rule ids that accept per-rule option config (validated strictly).
_RULE_OPTION_KEYS = {
    "RTL001": {"force"},
    "RTL002": {"force"},
    "RTL003": {"force"},
    "RTL004": {"force"},
    "RTL005": {"force"},
    "RTL008": {"force"},
    "RTL009": {"allow_latin_punctuation_in_prose"},
    "RTL010": {"allow_western_digits_in_prose"},
}


class ConfigError(ValueError):
    """Raised when a configuration file is invalid."""


def validate_config(data: dict, source: str = "<memory>") -> dict:
    """Validate a config dict; returns normalized config. Raises ConfigError."""
    errors: list[str] = []

    unknown = set(data.keys()) - KNOWN_KEYS
    if unknown:
        errors.append(f"unknown top-level key(s): {', '.join(sorted(str(k) for k in unknown))}")

    lang = data.get("language", DEFAULT_CONFIG["language"])
    if not isinstance(lang, str) or lang.lower() not in available_profiles():
        errors.append(
            f"language must be one of {available_profiles()}, got {lang!r}"
        )

    for key in ("include", "exclude"):
        val = data.get(key, DEFAULT_CONFIG[key])
        if not isinstance(val, list) or not all(isinstance(p, str) for p in val):
            errors.append(f"{key} must be a list of glob strings")

    fail_on = data.get("fail_on", DEFAULT_CONFIG["fail_on"])
    if not isinstance(fail_on, str) or fail_on not in VALID_FAIL_ON:
        errors.append(f"fail_on must be one of {sorted(VALID_FAIL_ON)}, got {fail_on!r}")

    overrides = data.get("severity_overrides", {})
    if not isinstance(overrides, dict):
        errors.append("severity_overrides must be an object of {ruleId: severity}")
    else:
        for rule_id, sev in overrides.items():
            if not isinstance(rule_id, str) or not re.fullmatch(r"RTL\d{3}", rule_id):
                errors.append(f"severity_overrides: invalid rule id {rule_id!r}")
            elif not isinstance(sev, str) or sev not in VALID_SEVERITIES:
                errors.append(
                    f"severity_overrides[{rule_id}]: severity must be one of "
                    f"{sorted(VALID_SEVERITIES)}, got {sev!r}"
                )

    rules = data.get("rules", {})
    if not isinstance(rules, dict):
        errors.append("rules must be an object of {ruleId: options}")
    else:
        for rule_id, opts in rules.items():
            if not isinstance(rule_id, str) or not re.fullmatch(r"RTL\d{3}", rule_id):
                errors.append(f"rules: invalid rule id {rule_id!r}")
            elif not isinstance(opts, dict):
                errors.append(f"rules[{rule_id}]: options must be an object")
            elif rule_id in _RULE_OPTION_KEYS:
                unknown_opts = set(opts) - _RULE_OPTION_KEYS[rule_id]
                if unknown_opts:
                    errors.append(
                        f"rules[{rule_id}]: unknown option(s) {sorted(str(o) for o in unknown_opts)}; "
                        f"known: {sorted(_RULE_OPTION_KEYS[rule_id])}"
                    )
            else:
                errors.append(f"rules[{rule_id}]: rule does not accept options")

    if errors:
        raise ConfigError(f"{source}: invalid config\n  - " + "\n  - ".join(errors))

    # Normalize
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(data)
    cfg["language"] = cfg["language"].lower()
    return cfg


def load_config(path: Path | None, root: Path) -> tuple[dict, str | None]:
    """Load raast.config.json from *path* or search *root*. Returns (config, source).

    An EXPLICITLY given path that does not exist is a usage error (ConfigError) —
    silently falling back to defaults would make a typo'd --config invisible.
    """
    candidates = []
    if path is not None:
        if not path.exists():
            raise ConfigError(f"config file not found: {path}")
        candidates.append(path)
    else:
        candidates.append(root / "raast.config.json")
    for c in candidates:
        if c.exists():
            try:
                data = json.loads(c.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                raise ConfigError(f"{c}: not valid JSON: {e}") from e
            return validate_config(data, str(c)), str(c)
    return dict(DEFAULT_CONFIG), None
