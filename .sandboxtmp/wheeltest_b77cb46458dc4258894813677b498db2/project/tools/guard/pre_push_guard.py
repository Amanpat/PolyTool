#!/usr/bin/env python3
"""Block pushes that include private KB/artifacts or secrets-like files."""

from __future__ import annotations

import subprocess
import sys
from typing import List

from guardlib import collect_forbidden, find_tracked_private


def _run_git(args: List[str]) -> List[str]:
    try:
        output = subprocess.check_output(["git", *args], text=True)
    except subprocess.CalledProcessError:
        return []
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines


def _get_staged_files() -> List[str]:
    return _run_git(["diff", "--cached", "--name-only", "--diff-filter=ACMR"])


def _get_pending_commit_files() -> List[str]:
    upstream = _run_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    if not upstream:
        return []
    return _run_git(["diff", "--name-only", f"{upstream[0]}..HEAD"])


def main() -> int:
    staged = _get_staged_files()
    pending = _get_pending_commit_files()
    candidates = list(dict.fromkeys(staged + pending))
    tracked_private = find_tracked_private(_run_git(["ls-files", "kb", "artifacts"]))

    if not candidates and not tracked_private:
        return 0

    violations = collect_forbidden(candidates)
    if not violations and not tracked_private:
        return 0

    print("Pre-push guard blocked the push. Forbidden files detected:", file=sys.stderr)
    for path, reason in violations:
        print(f" - {path} ({reason})", file=sys.stderr)
    if tracked_private:
        print("Tracked private files detected under kb/ or artifacts/:", file=sys.stderr)
        for path in tracked_private:
            print(f" - {path}", file=sys.stderr)
    print(
        "Move private data to kb/ or artifacts/ (gitignored), or remove from the commit.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
