#!/usr/bin/env python3
"""Lint Obsidian reading notes against the conventions in SKILL.md.

Examples:
    python lint_notes.py note.md
    python lint_notes.py "读书笔记" --json
    python lint_notes.py "读书笔记" --fix
    python lint_notes.py "读书笔记" --candidates
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

SKIP_DIRS = {".git", ".obsidian", ".trash", "node_modules", "assets", ".venv"}
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*\S)\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
H1_BOLD_RE = re.compile(r"^#\s+\*\*.+\*\*\s*$")
NBSP_RE = re.compile(r"&nbsp;|&#160;|&#xa0;", re.IGNORECASE)
GLOBAL_ATTACHMENT_RE = re.compile(r"\]\((?:\./)?(attachments|images)/")
PUNCT = "《》「」『』:：·—–-_.,，。!！?？()（）[]【】 "


@dataclass
class Issue:
    line: int
    severity: str  # error | warning | info
    code: str
    message: str


@dataclass
class FileReport:
    path: Path
    lines: int
    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")


def normalize(text: str) -> str:
    return "".join(ch for ch in text.strip().lower() if ch not in PUNCT)


def read_text(path: Path) -> tuple[str, str | None]:
    try:
        return path.read_text(encoding="utf-8-sig"), None
    except UnicodeDecodeError:
        return path.read_text(encoding="gbk", errors="replace"), "not utf-8, decoded as gbk"


def scan(text: str, path: Path, max_lines: int) -> FileReport:
    lines = text.splitlines()
    report = FileReport(path=path, lines=len(lines))
    fence: str | None = None
    fence_start = 0
    seen_headings: dict[str, int] = {}
    previous_level = 0

    if lines and lines[0].strip() == "---":
        for idx in range(1, min(len(lines), 100)):
            if lines[idx].strip() in {"---", "..."}:
                report.issues.append(
                    Issue(1, "error", "frontmatter", "file starts with YAML frontmatter; use --- only as a separator")
                )
                break

    for number, raw in enumerate(lines, start=1):
        fence_match = FENCE_RE.match(raw)
        if fence_match:
            marker = fence_match.group(1)
            if fence is None:
                fence, fence_start = marker, number
            elif marker == fence:
                fence = None
            continue
        if fence is not None:
            continue

        if H1_BOLD_RE.match(raw):
            report.issues.append(
                Issue(number, "error", "h1-bold", "heading uses # and ** together; use plain # levels")
            )

        heading = HEADING_RE.match(raw)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()
            if level == 1:
                if normalize(title) == normalize(path.stem):
                    report.issues.append(
                        Issue(number, "error", "duplicate-h1", "H1 repeats the filename; drop the heading")
                    )
                else:
                    report.issues.append(
                        Issue(number, "warning", "unexpected-h1", f"unexpected H1: {title!r}; filename is the title")
                    )
            if previous_level and level > previous_level + 1:
                report.issues.append(
                    Issue(number, "warning", "heading-jump", f"heading jumps from h{previous_level} to h{level}")
                )
            previous_level = level

            key = f"{level}:{title}"
            if key in seen_headings:
                report.issues.append(
                    Issue(number, "warning", "duplicate-heading", f"duplicate h{level} heading {title!r} (first at line {seen_headings[key]})")
                )
            else:
                seen_headings[key] = number

        if NBSP_RE.search(raw):
            report.issues.append(Issue(number, "warning", "nbsp", "contains &nbsp; or numeric equivalent"))

        if raw.rstrip() != raw:
            report.issues.append(Issue(number, "warning", "trailing-space", "trailing whitespace"))

        if raw.startswith("\t") or "\t" in raw[: len(raw) - len(raw.lstrip())]:
            report.issues.append(Issue(number, "warning", "tab", "leading tab; use 2 spaces for list nesting"))

        if GLOBAL_ATTACHMENT_RE.search(raw):
            report.issues.append(
                Issue(number, "warning", "global-attachments", "global attachments/ or images/ path; use assets/<note>/")
            )

    if fence is not None:
        report.issues.append(Issue(fence_start, "error", "unclosed-fence", "code fence is never closed"))

    if len(lines) < max_lines:
        report.issues.append(
            Issue(0, "info", "merge-candidate", f"{len(lines)} lines (< {max_lines}); candidate for merging")
        )
    return report


def fix_text(text: str, path: Path) -> tuple[str, int]:
    """Apply only safe fixes. Returns (new_text, number_of_changes)."""
    lines = text.splitlines()
    out: list[str] = []
    changes = 0
    fence: str | None = None

    for raw in lines:
        fence_match = FENCE_RE.match(raw)
        if fence_match:
            marker = fence_match.group(1)
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            out.append(raw)
            continue

        if fence is not None:
            out.append(raw)
            continue

        # A heading identical to the filename duplicates the page title.
        heading = HEADING_RE.match(raw)
        if heading and len(heading.group(1)) == 1 and normalize(heading.group(2)) == normalize(path.stem):
            changes += 1
            continue

        new_line = NBSP_RE.sub(" ", raw).rstrip()
        if new_line != raw:
            changes += 1
        out.append(new_line)

    fixed = "\n".join(out)
    fixed = re.sub(r"\n{4,}", "\n\n\n", fixed)
    if not fixed.endswith("\n"):
        fixed += "\n"
    return fixed, changes


def iter_notes(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    notes = []
    for path in sorted(target.rglob("*.md")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        notes.append(path)
    return notes


def display(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint Obsidian reading notes.")
    parser.add_argument("paths", nargs="+", type=Path, help="file or directory")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--fix", action="store_true", help="apply safe fixes")
    parser.add_argument("--candidates", action="store_true", help="only list merge candidates")
    parser.add_argument("--max-lines", type=int, default=500, help="merge candidate threshold (default 500)")
    args = parser.parse_args()

    targets: list[Path] = []
    missing = []
    for raw in args.paths:
        path = raw.expanduser()
        if not path.exists():
            missing.append(str(path))
        else:
            targets.append(path)
    if missing:
        for path in missing:
            print(f"error: not found: {path}", file=sys.stderr)
        return 2

    notes: list[Path] = []
    for target in targets:
        notes.extend(iter_notes(target))
    notes = sorted(set(notes))
    if not notes:
        print("error: no Markdown files found", file=sys.stderr)
        return 2

    reports: list[FileReport] = []
    fixed_files = 0
    for note in notes:
        text, encoding_note = read_text(note)
        changed = 0
        if args.fix:
            new_text, changed = fix_text(text, note)
            if changed:
                note.write_text(new_text, encoding="utf-8", newline="\n")
                text = new_text
                fixed_files += 1
        report = scan(text, note, args.max_lines)
        if encoding_note:
            report.issues.append(Issue(1, "warning", "encoding", encoding_note))
        if changed:
            report.issues.append(Issue(0, "info", "fixed", f"applied {changed} safe fixes"))
        reports.append(report)

    if args.candidates:
        rows = [
            (r, next((i for i in r.issues if i.code == "merge-candidate"), None))
            for r in reports
        ]
        rows = [(r, i) for r, i in rows if i is not None]
        if args.json:
            print(json.dumps([{"path": display(r.path), "lines": r.lines} for r, _ in rows], ensure_ascii=False, indent=2))
        else:
            for r, i in rows:
                print(f"{display(r.path)}  {i.message}")
            print(f"\n{len(rows)} merge candidate(s) — report only, do not merge without approval")
        return 0

    errors = sum(r.errors for r in reports)
    warnings = sum(1 for r in reports for i in r.issues if i.severity == "warning")
    infos = sum(1 for r in reports for i in r.issues if i.severity == "info")

    if args.json:
        payload = {
            "files": [
                {
                    "path": display(r.path),
                    "lines": r.lines,
                    "issues": [
                        {"line": i.line, "severity": i.severity, "code": i.code, "message": i.message}
                        for i in r.issues
                        if not (i.code == "merge-candidate" and args.candidates)
                    ],
                }
                for r in reports
            ],
            "summary": {
                "files": len(reports),
                "errors": errors,
                "warnings": warnings,
                "infos": infos,
                "fixed_files": fixed_files,
            },
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for report in reports:
            visible = [
                i
                for i in report.issues
                if i.code != "merge-candidate" or args.candidates
            ]
            if not visible:
                continue
            print(display(report.path))
            for issue in visible:
                prefix = f"  line {issue.line}: " if issue.line else "  "
                print(f"{prefix}[{issue.severity}] {issue.message}")
            print()
        print(f"{len(reports)} file(s), {errors} error(s), {warnings} warning(s)")
        if args.fix:
            print(f"safe fixes applied to {fixed_files} file(s)")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
