# Changelog — raast-vscode

All notable changes to the RAAST VS Code extension are documented here.
Format follows Keep a Changelog; versioning follows SemVer.

## [0.1.0] — initial scaffold

- Diagnostics from the installed RAAST CLI (`raast doctor --format json`) on
  scan commands, on save, and via workspace scan.
- Severity mapping P0 → Error, P1 → Warning, P2 → Information, gated by
  `raast.failOn`.
- Quick fixes for the safe tier: RTL001/RTL002/RTL004 physical → logical
  property swaps, RTL011 broken ZWNJ compound join.
- Settings: `raast.executablePath`, `raast.language`, `raast.failOn`.
- Honest error path when the CLI binary is missing.
