#!/usr/bin/env python3
"""Block pushes that include private KB/artifacts or secrets-like files."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

ALLOWED_KB_FILES = {"kb/readme.md", "kb/.gitkeep"}
SECRET_HINTS = ("secret", "secrets", "key", "token")
DATA_EXTENSIONS = {
    ".env",
    ".txt",
    ".json",
    ".jsonl",
    ".ndjson",
    ".csv",
    ".tsv",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".log",
    ".pem",
    ".key",
    ".pfx",
    ".p12",
    ".crt",
    ".der",
}


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


def _normalize(path: str) -> str:
    return Path(path).as_posix().lstrip("./")


def _is_secrets_like(path: str) -> bool:
    lower_name = Path(path).name.lower()
    if not any(hint in lower_name for hint in SECRET_HINTS):
        return False
    return Path(lower_name).suffix in DATA_EXTENSIONS


def _is_forbidden(path: str) -> Tuple[bool, str]:
    normalized = _normalize(path)
    lower = normalized.lower()

    if lower in ALLOWED_KB_FILES:
        return False, ""
    if lower.startswith("kb/"):
        return True, "private kb path"
    if lower.startswith("artifacts/"):
        return True, "artifacts path"

    name = Path(lower).name
    if name == ".env" or name.startswith(".env."):
        return True, "env file"
    if name.endswith(".env") and name != ".env":
        return True, "env file"

    if name.startswith("response_") and name.endswith(".json"):
        return True, "response json export"

    if Path(name).suffix in {".log", ".tmp"}:
        return True, "log/tmp output"

    if "/exports/" in f"/{lower}":
        if Path(name).suffix in DATA_EXTENSIONS:
            return True, "raw export"

    if _is_secrets_like(normalized):
        return True, "secrets-like filename"

    return False, ""


def _collect_forbidden(paths: Iterable[str]) -> List[Tuple[str, str]]:
    forbidden: List[Tuple[str, str]] = []
    for path in paths:
        blocked, reason = _is_forbidden(path)
        if blocked:
            forbidden.append((path, reason))
    return forbidden


def main() -> int:
    staged = _get_staged_files()
    pending = _get_pending_commit_files()
    candidates = list(dict.fromkeys(staged + pending))

    if not candidates:
        return 0

    violations = _collect_forbidden(candidates)
    if not violations:
        return 0

    print("Pre-push guard blocked the push. Forbidden files detected:", file=sys.stderr)
    for path, reason in violations:
        print(f" - {path} ({reason})", file=sys.stderr)
    print(
        "Move private data to kb/ or artifacts/ (gitignored), or remove from the commit.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
