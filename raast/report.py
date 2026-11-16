"""Report renderers: human text, JSON, Markdown, GitHub Actions annotations."""
from __future__ import annotations

import json as _json
from dataclasses import dataclass, field

from .rules import Finding, SEVERITY_ORDER

_COLORS = {"P0": "\033[91m", "P1": "\033[93m", "P2": "\033[96m"}
_RESET = "\033[0m"
_BOLD = "\033[1m"


def _escape_property(value: str) -> str:
    """Escape a GitHub workflow-command property value (file paths, columns).
    Same contract as raast.review — commas/colons in a path would otherwise
    split the property list and silently misroute the annotation."""
    return (value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
                 .replace(":", "%3A").replace(",", "%2C"))


def _escape_data(value: str) -> str:
    """Escape a GitHub workflow-command MESSAGE (data) section."""
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _md_cell(text: str) -> str:
    """Make a finding message safe inside a Markdown table cell.
    Finding messages embed matched source text, which may contain pipes
    that would otherwise split the table."""
    return text.replace("|", "\\|").replace("\r\n", " ").replace("\n", " ")


@dataclass
class Report:
    target: str
    files_scanned: int
    findings: list[Finding] = field(default_factory=list)
    config_source: str | None = None
    frameworks: dict | None = None

    @property
    def counts(self) -> dict:
        c = {"P0": 0, "P1": 0, "P2": 0}
        for f in self.findings:
            c[f.severity] += 1
        return c

    def summary_line(self) -> str:
        c = self.counts
        return f"{len(self.findings)} finding(s): {c['P0']} P0, {c['P1']} P1, {c['P2']} P2"

    def should_fail(self, fail_on: str) -> bool:
        if fail_on == "off":
            return False
        return any(SEVERITY_ORDER[f.severity] <= SEVERITY_ORDER[fail_on] for f in self.findings)

    def to_json(self) -> str:
        return _json.dumps(
            {
                "tool": "raast",
                "target": self.target,
                "files_scanned": self.files_scanned,
                "config_source": self.config_source,
                "frameworks": self.frameworks,
                "summary": self.counts,
                "findings": [f.as_dict() for f in self.findings],
            },
            ensure_ascii=False,
            indent=2,
        )

    def to_markdown(self) -> str:
        lines = [
            "# RAAST Diagnostics Report",
            "",
            f"- Target: `{self.target}`",
            f"- Files scanned: {self.files_scanned}",
            f"- Config: `{self.config_source or 'defaults'}`",
            f"- Summary: **{self.summary_line()}**",
            "",
        ]
        if not self.findings:
            lines += ["No findings. This is not a guarantee of correctness — run the browser suite too.", ""]
            return "\n".join(lines)
        lines += [
            "| Rule | Sev | Conf | Location | Issue | Suggested fix |",
            "|---|---|---|---|---|---|",
        ]
        for f in sorted(self.findings, key=lambda x: (SEVERITY_ORDER[x.severity], x.file, x.line)):
            loc = f"{f.file}:{f.line}" + (f":{f.column}" if f.column else "")
            lines.append(
                f"| {f.rule} | {f.severity} | {f.confidence} | `{_md_cell(loc)}` "
                f"| {_md_cell(f.message)} | {_md_cell(f.suggested_fix)} |"
            )
        lines += [
            "",
            "Review each finding against the rule explanation before auto-fixing; "
            "`raast fix` only rewrites high-confidence, safe transformations.",
            "",
        ]
        return "\n".join(lines)

    def to_text(self, color: bool = True) -> str:
        out = [
            f"{_BOLD}RAAST doctor{_RESET} — target: {self.target}",
            f"files scanned: {self.files_scanned}   config: {self.config_source or 'defaults'}",
        ]
        if self.frameworks:
            fw = ", ".join(sorted(self.frameworks)) or "none detected"
            out.append(f"frameworks: {fw}")
        out.append("")
        if not self.findings:
            out.append("No findings. Static analysis is not a guarantee — run browser tests too.")
            return "\n".join(out)
        for f in sorted(self.findings, key=lambda x: (SEVERITY_ORDER[x.severity], x.file, x.line)):
            loc = f"{f.file}:{f.line}" + (f":{f.column}" if f.column else "")
            mark = "FIXABLE" if f.fixable else "review"
            head = f"[{f.severity}] {f.rule} {loc} {f.message} ({f.confidence}, {mark})"
            if color:
                head = f"{_COLORS[f.severity]}{head}{_RESET}"
            out.append(head)
            out.append(f"    {f.explanation}")
            out.append(f"    fix: {f.suggested_fix}")
        out.append("")
        out.append(f"Summary: {self.summary_line()}")
        return "\n".join(out)

    def to_github(self) -> str:
        lines = []
        for f in self.findings:
            cmd = "error" if f.severity == "P0" else "warning"
            meta = f"file={_escape_property(f.file)},line={f.line}"
            if f.column:
                meta += f",col={f.column}"
            msg = _escape_data(f"{f.rule}: {f.message} — {f.suggested_fix}")
            lines.append(f"::{cmd} {meta}::{msg}")
        lines.append(f"RAAST summary: {self.summary_line()}")
        return "\n".join(lines)
