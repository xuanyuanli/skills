#!/usr/bin/env python3
"""Collect commits for a weekly report.

The default window starts at the most recent Saturday 00:00 local time and
ends now. When the script runs on a Saturday it looks back seven days, so the
report covers the week that just ended instead of producing an empty report.

Examples:
    python collect.py
    python collect.py --json
    python collect.py --author all --branch master
    python collect.py --since 2026-10-24 --no-stats
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

FIELD = "\x1f"
RECORD = "\x1e"
CONVENTIONAL = {
    "feat",
    "fix",
    "refactor",
    "perf",
    "test",
    "docs",
    "chore",
    "style",
    "build",
    "ci",
    "revert",
}
SUBJECT_RE = re.compile(r"^([A-Za-z]+)(?:\(([^)]*)\))?!?:\s*(.+)$")
STAT_RE = re.compile(
    r"(\d+) files? changed"
    r"(?:, (\d+) insertions?\(\+\))?"
    r"(?:, (\d+) deletions?\(-\))?"
)


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise SystemExit(f"error: git {' '.join(args)} failed\n{result.stderr.strip()}")
    return result.stdout


def try_git(repo: Path, *args: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip() if result.returncode == 0 else None


def compute_window(now: datetime) -> tuple[datetime, datetime]:
    """Return (start, end). Saturday is the first day of the week."""
    if now.weekday() == 5:  # Saturday: report the week that just ended
        days = 7
    else:
        days = (now.weekday() - 5) % 7
    start = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, now


def parse_subject(subject: str) -> tuple[str, str, str]:
    match = SUBJECT_RE.match(subject)
    if match and match.group(1).lower() in CONVENTIONAL:
        return match.group(1).lower(), match.group(2) or "", match.group(3).strip()
    return "other", "", subject.strip()


def commit_stats(repo: Path, commit: str) -> tuple[int, int, int]:
    output = git(repo, "show", "--no-renames", "--shortstat", "--format=", commit)
    match = STAT_RE.search(output)
    if not match:
        return 0, 0, 0
    return int(match.group(1)), int(match.group(2) or 0), int(match.group(3) or 0)


def collect(
    repo: Path,
    branch: str | None,
    author: str | None,
    since: datetime,
    until: datetime,
    with_stats: bool,
) -> dict:
    fmt = FIELD.join(["%H", "%ad", "%an", "%ae", "%s", "%b"]) + RECORD
    args = [
        "log",
        "--no-merges",
        f"--since={since.strftime('%Y-%m-%d %H:%M:%S')}",
        f"--until={until.strftime('%Y-%m-%d %H:%M:%S')}",
        "--date=iso-strict",
        f"--pretty=format:{fmt}",
    ]
    if author:
        args.append(f"--author={author}")
    if branch:
        args.append(branch)

    raw = git(repo, *args)
    commits = []
    for record in raw.split(RECORD):
        record = record.strip("\n")
        if not record:
            continue
        parts = record.split(FIELD)
        if len(parts) < 6:
            continue
        commit_hash, date_text, name, email, subject, body = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
        kind, scope, title = parse_subject(subject)
        try:
            when = datetime.fromisoformat(date_text)
        except ValueError:
            when = since
        files = insertions = deletions = 0
        if with_stats:
            files, insertions, deletions = commit_stats(repo, commit_hash)
        commits.append(
            {
                "hash": commit_hash,
                "short": commit_hash[:9],
                "date": when.strftime("%Y-%m-%d %H:%M"),
                "author": name,
                "email": email,
                "subject": subject,
                "type": kind,
                "scope": scope,
                "title": title,
                "body": body.strip(),
                "files": files,
                "insertions": insertions,
                "deletions": deletions,
            }
        )

    types: dict[str, int] = {}
    for commit in commits:
        types[commit["type"]] = types.get(commit["type"], 0) + 1

    totals = {
        "commits": len(commits),
        "files": sum(c["files"] for c in commits),
        "insertions": sum(c["insertions"] for c in commits),
        "deletions": sum(c["deletions"] for c in commits),
    }

    return {
        "repo": str(repo),
        "branch": branch or "HEAD",
        "author": author or "all",
        "window": {
            "since": since.isoformat(timespec="seconds"),
            "until": until.isoformat(timespec="seconds"),
            "label": f"{since:%m-%d} ~ {until:%m-%d}",
            "days": (until.date() - since.date()).days + 1,
        },
        "totals": totals,
        "types": dict(sorted(types.items(), key=lambda item: (-item[1], item[0]))),
        "commits": commits,
    }


def main() -> int:
    # Git emits UTF-8; the Windows console default (cp936) would mangle it.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Collect commits for a weekly report.")
    parser.add_argument("--repo", default=".", help="repository path (default: current directory)")
    parser.add_argument("--branch", help="branch or revision (default: current branch)")
    parser.add_argument(
        "--author",
        help="author filter; 'all' disables it (default: git config user.email)",
    )
    parser.add_argument("--since", help="window start, e.g. 2026-10-24 or '2026-10-24 09:00'")
    parser.add_argument("--json", action="store_true", help="print JSON")
    parser.add_argument("--no-stats", action="store_true", help="skip per-commit line counts (faster)")
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    top = try_git(repo, "rev-parse", "--show-toplevel")
    if not top:
        print(f"error: not a git repository: {repo}", file=sys.stderr)
        return 2
    repo = Path(top)

    since: datetime
    if args.since:
        try:
            since = datetime.fromisoformat(args.since)
            if len(args.since.strip()) <= 10:
                since = since.replace(hour=0, minute=0, second=0)
        except ValueError:
            print(f"error: invalid --since {args.since!r}", file=sys.stderr)
            return 2
    else:
        since, _ = compute_window(datetime.now())
    until = datetime.now()

    branch = args.branch
    if not branch:
        current = try_git(repo, "rev-parse", "--abbrev-ref", "HEAD")
        branch = None if current in (None, "HEAD") else current
    elif not try_git(repo, "rev-parse", "--verify", branch):
        print(f"error: unknown branch or revision: {branch}", file=sys.stderr)
        return 2

    author = args.author
    if author is None:
        email = try_git(repo, "config", "user.email")
        author = email or None
        if author is None:
            print("warning: git user.email is unset; collecting all authors", file=sys.stderr)
    elif author.lower() == "all":
        author = None

    data = collect(repo, branch, author, since, until, not args.no_stats)

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    window = data["window"]
    print(f"repo    {data['repo']}")
    print(f"branch  {data['branch']}    author={data['author']}")
    print(f"window  {window['since']} -> {window['until']}  ({window['days']} days)")
    totals = data["totals"]
    print(
        f"totals  {totals['commits']} commits, {totals['files']} files, "
        f"+{totals['insertions']}/-{totals['deletions']}"
    )
    print("types   " + ", ".join(f"{name}={count}" for name, count in data["types"].items()))
    print()
    for commit in data["commits"]:
        print(f"{commit['date']}  {commit['short']}  [{commit['type']:<8}] {commit['title']}")
    if not data["commits"]:
        print("(no commits in this window)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
