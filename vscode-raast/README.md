# RAAST — RTL Doctor (VS Code extension)

This extension runs the installed RAAST CLI on the files you edit and shows the
findings in the Problems panel and in the editor, with quick fixes for the
rules the engine marks as safe to rewrite.

The extension is a thin client: all detection happens in the `raast` Python
CLI. Nothing is re-implemented in JavaScript, so rule behavior (including the
RTL-script evidence gate) is identical to the command line.

## What you see

Findings appear as diagnostics with the rule id, severity, message and the
suggested fix. The Problems panel renders them like this:

```
RTL001  P1  Warning  physical margin-left declaration — fix: margin-inline-start: 16px
    styles.css · line 13

RTL004  P1  Warning  text-align: left — fix: text-align: start
    index.html · line 18
```

Severity mapping: P0 → Error, P1 → Warning, P2 → Information. The `raast.failOn`
setting hides findings below the chosen tier (default P1, so P2 is hidden
until you raise it).

## Commands

| Command | Behavior |
|---|---|
| `RAAST: Scan Current File` | Runs `raast doctor <file> --language <lang> --format json` and populates diagnostics for the active editor. |
| `RAAST: Scan Workspace` | Runs the CLI once per scannable file (`html, css, scss, sass, vue, js, mjs, cjs, jsx, ts, tsx`), sequentially, with a progress indicator. |

Saving a file whose language matches the supported set re-scans it
automatically.

## Quick fixes

Offered only for the safe tier, matching what `raast fix` will rewrite:

- RTL001: `margin-left`/`margin-right` → `margin-inline-start`/`margin-inline-end`
- RTL002: `padding-left`/`padding-right` → `padding-inline-start`/`padding-inline-end`
- RTL004: `text-align: left|right` → `text-align: start|end`
- RTL011: broken ZWNJ compound replaced with the joined form suggested by the engine

Everything else is review-only; no quick fix is offered. Title:
"RAAST: replace with logical property" (ZWNJ: "RAAST: join broken ZWNJ compound").

## Configuration

| Setting | Default | Meaning |
|---|---|---|
| `raast.executablePath` | `raast` | CLI executable; change it if `raast` is not on PATH. |
| `raast.language` | `fa` | Language profile passed to `--language` (`fa`, `ar`, `he`, `es`). |
| `raast.failOn` | `P1` | Minimum severity surfaced as diagnostics. |

## Install prerequisites

1. Python 3.11+ and the CLI: `pip install raast` (or `pip install -e .` from
   the repository root). Check with `raast --version` or `python3 -m raast.cli --version`.
2. VS Code 1.85+.
3. Node.js is only needed to *build* the extension (see below), not to run it.

If the CLI cannot be found the extension shows: "RAAST CLI not found. Install
it with: pip install raast (Python 3.11+) — or set raast.executablePath."

## Build / package (developers)

The extension declares **no runtime dependencies** and ships as a single
`extension.js` plus `package.json`.

```sh
cd vscode-raast
npm i -g @vscode/vsce   # once, for the packager
vsce package            # produces raast-vscode-0.1.0.vsix
code --install-extension raast-vscode-0.1.0.vsix
```

`@types/vscode` is a devDependency used only for type checking; `vsce package`
runs `node --check extension.js` first. There is no bundler and no install
step for runtime code.

## Honest limitations

- **JSON contract:** the extension parses the `doctor --format json` output of
  the installed CLI. If the installed CLI version does not match the output
  shape this extension expects (a `findings` array with the documented
  fields), scanning reports "could not parse doctor output" instead of
  guessing. The repository ships both pieces in lockstep; mixing versions can
  degrade behavior.
- **Quick fixes are limited to the safe tier** (RTL001/RTL002/RTL004/RTL011)
  and to the flagged line; multi-declaration lines and non-kebab-case
  declarations may need manual edits.
- **camelCase style objects** (`marginLeft: 8` in JSX) are not detected by the
  engine itself (kebab-case only — see `docs/compatibility-matrix.md`, the
  react-jsx row). The quick fix can still rewrite camelCase on a flagged line,
  but nothing flags it in the first place.
- **Workspace scan is sequential** — one CLI process at a time. On large
  repositories this takes seconds to minutes; it is deliberately not parallel
  to keep output predictable.
- **Static only:** diagnostics reflect the engine's lexical rules. Rendering
  correctness needs the runtime/browser tooling, not this extension.
