"use strict";

/**
 * RAAST — RTL Doctor (VS Code extension scaffold).
 *
 * Shells out to the installed RAAST CLI (`raast doctor <file> --language <lang>
 * --format json`) and maps the JSON findings onto editor diagnostics. Quick
 * fixes are offered only for the safe-tier rules; everything else stays
 * review-only.
 *
 * Honest contract with the CLI:
 * - `doctor` exits 0 when no finding is at/above fail_on and 1 when findings
 *   exist. Both are normal: stdout still carries the JSON either way.
 * - Exit code 2 or unparseable stdout means the CLI did not behave as this
 *   extension expects (wrong version, broken install); we surface that
 *   instead of guessing.
 *
 * No runtime dependencies: uses only `vscode`, `child_process` and `path`.
 */
const vscode = require("vscode");
const { execFile } = require("child_process");
const path = require("path");

const DIAGNOSTIC_SOURCE = "RAAST";

/** Engine severity rank (P0 is most severe). */
const SEVERITY_RANK = { P0: 0, P1: 1, P2: 2 };
const VSCODE_SEVERITY = {
  P0: vscode.DiagnosticSeverity.Error,
  P1: vscode.DiagnosticSeverity.Warning,
  P2: vscode.DiagnosticSeverity.Information,
};

/** Language ids the extension activates on (mirrors contributes.languages). */
const LANGUAGE_IDS = [
  "html",
  "css",
  "scss",
  "javascript",
  "typescript",
  "javascriptreact", // .jsx
  "typescriptreact", // .tsx
  "vue",
];

/** Include glob for the workspace scan (exclude list mirrors `raast init`). */
const SCAN_GLOB = "**/*.{html,htm,css,scss,sass,vue,js,mjs,cjs,jsx,ts,tsx}";
const SCAN_EXCLUDE = "{**/node_modules/**,**/dist/**,**/build/**,**/.next/**,**/vendor/**}";

/** Rules for which the extension offers an automatic quick fix. */
const SAFE_RULES = new Set(["RTL001", "RTL002", "RTL004", "RTL011"]);

/**
 * Physical -> logical declaration swaps, applied to the diagnostic's line.
 * Kebab-case covers CSS/template literals; camelCase covers JSX style
 * objects (the engine itself does not detect camelCase — see the matrix —
 * so camelCase swaps only apply when a diagnostic already exists on that
 * line from another source).
 */
const LOGICAL_SWAPS = [
  [/\bmargin-left\b/g, "margin-inline-start"],
  [/\bmargin-right\b/g, "margin-inline-end"],
  [/\bpadding-left\b/g, "padding-inline-start"],
  [/\bpadding-right\b/g, "padding-inline-end"],
  [/text-align\s*:\s*left\b/gi, "text-align: start"],
  [/text-align\s*:\s*right\b/gi, "text-align: end"],
  [/\bmarginLeft\b/g, "marginInlineStart"],
  [/\bmarginRight\b/g, "marginInlineEnd"],
  [/\bpaddingLeft\b/g, "paddingInlineStart"],
  [/\bpaddingRight\b/g, "paddingInlineEnd"],
];

/**
 * Run `raast doctor` on one absolute path. Resolves with raw stdout even
 * when the process exits 1 (findings present); rejects only for a missing
 * binary or a shape-breaking CLI failure.
 */
function runDoctor(absPath) {
  const config = vscode.workspace.getConfiguration("raast");
  const executable = config.get("executablePath", "raast") || "raast";
  const language = config.get("language", "fa") || "fa";
  const args = ["doctor", absPath, "--language", language, "--format", "json"];
  const folder = vscode.workspace.getWorkspaceFolder(vscode.Uri.file(absPath));
  const cwd = folder ? folder.uri.fsPath : path.dirname(absPath);
  return new Promise((resolve, reject) => {
    execFile(executable, args, { cwd, maxBuffer: 10 * 1024 * 1024 }, (error, stdout, stderr) => {
      if (error && error.code === "ENOENT") {
        reject({ kind: "missing-binary", executable });
        return;
      }
      // error with code 1 = findings exist (expected); any other error still
      // carries stdout we can try to parse before giving up.
      resolve({ stdout: String(stdout || ""), stderr: String(stderr || ""), error });
    });
  });
}

/** Extract the findings array from CLI stdout, tolerating non-JSON noise. */
function parseFindings(stdout) {
  const brace = stdout.indexOf("{");
  if (brace < 0) return null;
  try {
    const payload = JSON.parse(stdout.slice(brace));
    return Array.isArray(payload.findings) ? payload.findings : null;
  } catch (_) {
    return null;
  }
}

/** Map a finding's 1-based line/column to a Range (whole line as fallback). */
function findingRange(document, finding) {
  const line = Math.max(0, (finding.line || 1) - 1);
  if (line >= document.lineCount) {
    const last = document.lineAt(document.lineCount - 1);
    return new vscode.Range(last.range.start, last.range.end);
  }
  const textLine = document.lineAt(line);
  if (typeof finding.column === "number" && finding.column > 0) {
    const col = Math.min(finding.column - 1, textLine.text.length);
    return new vscode.Range(line, col, line, textLine.text.length);
  }
  return new vscode.Range(line, 0, line, textLine.text.length);
}

/** Convert a CLI finding into a VS Code diagnostic (rule id kept as code). */
function toDiagnostic(document, finding) {
  const severity = VSCODE_SEVERITY[finding.severity] || vscode.DiagnosticSeverity.Information;
  const diagnostic = new vscode.Diagnostic(
    findingRange(document, finding),
    `[${finding.rule} ${finding.severity}] ${finding.message} — fix: ${finding.suggested_fix}`,
    severity
  );
  diagnostic.source = DIAGNOSTIC_SOURCE;
  diagnostic.code = finding.rule;
  diagnostic.raast = finding; // kept for the quick-fix provider
  return diagnostic;
}

/** Scan one document: run the CLI, filter by failOn, replace its diagnostics. */
async function scanDocument(document, collection) {
  const config = vscode.workspace.getConfiguration("raast");
  const failOn = config.get("failOn", "P1");
  collection.delete(document.uri);
  let run;
  try {
    run = await runDoctor(document.uri.fsPath);
  } catch (err) {
    if (err && err.kind === "missing-binary") {
      vscode.window.showInformationMessage(
        "RAAST CLI not found. Install it with: pip install raast (Python 3.11+) — or set raast.executablePath."
      );
      return;
    }
    throw err;
  }
  const findings = parseFindings(run.stdout);
  if (findings === null) {
    const detail = run.error && run.error.code !== 1 ? ` (exit ${run.error && run.error.code})` : "";
    vscode.window.showWarningMessage(
      `RAAST: could not parse doctor output for ${document.uri.fsPath}${detail}. ` +
        "The installed CLI version may not match the output shape this extension expects."
    );
    return;
  }
  const diagnostics = findings
    .filter((f) => SEVERITY_RANK[f.severity] <= SEVERITY_RANK[failOn])
    .map((f) => toDiagnostic(document, f));
  collection.set(document.uri, diagnostics);
}

/** Scan a file that may not be open: open it read-only, then scan. */
async function scanUri(uri, collection) {
  const document = await vscode.workspace.openTextDocument(uri);
  if (LANGUAGE_IDS.includes(document.languageId)) {
    await scanDocument(document, collection);
  }
}

/** RAAST: Scan Workspace — sequential per-file doctor runs with progress. */
async function scanWorkspace(collection) {
  const files = await vscode.workspace.findFiles(SCAN_GLOB, SCAN_EXCLUDE);
  if (files.length === 0) {
    vscode.window.showInformationMessage("RAAST: no scannable files in this workspace.");
    return;
  }
  await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Window, title: "RAAST: scanning workspace" },
    async (progress) => {
      // Sequential on purpose: one CLI process at a time keeps output
      // predictable and avoids spawning hundreds of Python interpreters.
      for (let i = 0; i < files.length; i++) {
        progress.report({ message: `${i + 1}/${files.length}`, increment: 100 / files.length });
        try {
          await scanUri(files[i], collection);
        } catch (err) {
          if (err && err.kind === "missing-binary") {
            vscode.window.showInformationMessage(
              "RAAST CLI not found. Install it with: pip install raast (Python 3.11+) — or set raast.executablePath."
            );
            return;
          }
          // Skip unreadable files; keep scanning the rest.
        }
      }
    }
  );
  vscode.window.showInformationMessage(`RAAST: workspace scan finished (${files.length} file(s)).`);
}

/**
 * Quick-fix provider for the SAFE set. RTL001/002/004 rewrite the physical
 * declaration into its logical twin on the flagged line; RTL011 replaces the
 * broken ZWNJ compound with the engine's suggested join.
 */
function provideQuickFixes(document, diagnostic) {
  const finding = diagnostic.raast;
  if (!finding || !SAFE_RULES.has(finding.rule)) return [];
  const line = diagnostic.range.start.line;
  const lineRange = document.lineAt(line).range;
  const text = document.lineAt(line).text;
  let replacement = null;
  let title = "RAAST: replace with logical property";

  if (finding.rule === "RTL011") {
    // suggested_fix looks like «correct-form»; the message carries the
    // broken compound as «broken-form» — swap the first occurrence.
    const before = /«([^»]+)»/.exec(finding.message || "");
    const after = /«([^»]+)»/.exec(finding.suggested_fix || "");
    if (!before || !after || !text.includes(before[1])) return [];
    replacement = text.replace(before[1], after[1]);
    title = "RAAST: join broken ZWNJ compound";
  } else {
    replacement = text;
    for (const [pattern, logical] of LOGICAL_SWAPS) replacement = replacement.replace(pattern, logical);
    if (replacement === text) return []; // nothing swappable on this line
  }

  const action = new vscode.CodeAction(title, vscode.CodeActionKind.QuickFix);
  const edit = new vscode.WorkspaceEdit();
  edit.replace(document.uri, lineRange, replacement);
  action.edit = edit;
  action.diagnostics = [diagnostic];
  action.isPreferred = true;
  return [action];
}

function activate(context) {
  const collection = vscode.languages.createDiagnosticCollection("raast");
  context.subscriptions.push(collection);

  context.subscriptions.push(
    vscode.commands.registerCommand("raast.scanFile", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor || editor.document.uri.scheme !== "file") {
        vscode.window.showInformationMessage("RAAST: open a file first.");
        return;
      }
      await scanDocument(editor.document, collection);
    }),
    vscode.commands.registerCommand("raast.scanWorkspace", () => scanWorkspace(collection)),
    vscode.languages.registerCodeActionsProvider(
      LANGUAGE_IDS.map((language) => ({ language })),
      { provideCodeActions: (document, _range, context_) => context_.diagnostics.flatMap((d) => provideQuickFixes(document, d)) },
      { providedCodeActionKinds: [vscode.CodeActionKind.QuickFix] }
    ),
    vscode.workspace.onDidSaveTextDocument((document) => {
      // Auto-scan saved files when the language matches; silent on anything else.
      if (document.uri.scheme === "file" && LANGUAGE_IDS.includes(document.languageId)) {
        scanDocument(document, collection).catch(() => undefined);
      }
    }),
    vscode.workspace.onDidCloseTextDocument((document) => collection.delete(document.uri))
  );
}

function deactivate() {
  // Nothing to flush: diagnostics die with their collection.
}

module.exports = { activate, deactivate };
