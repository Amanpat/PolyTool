#!/usr/bin/env python3
"""Shared guard logic for pre-commit/pre-push hooks."""

from __future__ import annotations

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


def normalize_path(path: str) -> str:
    normalized = Path(path).as_posix()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.lstrip("/")


def is_secrets_like(path: str) -> bool:
    lower_name = Path(path).name.lower()
    if not any(hint in lower_name for hint in SECRET_HINTS):
        return False
    return Path(lower_name).suffix in DATA_EXTENSIONS


def is_forbidden(path: str) -> Tuple[bool, str]:
    normalized = normalize_path(path)
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

    if is_secrets_like(normalized):
        return True, "secrets-like filename"

    return False, ""


def collect_forbidden(paths: Iterable[str]) -> List[Tuple[str, str]]:
    forbidden: List[Tuple[str, str]] = []
    for path in paths:
        blocked, reason = is_forbidden(path)
        if blocked:
            forbidden.append((path, reason))
    return forbidden


def find_tracked_private(paths: Iterable[str]) -> List[str]:
    tracked: List[str] = []
    for path in paths:
        normalized = normalize_path(path)
        lower = normalized.lower()
        if lower in ALLOWED_KB_FILES:
            continue
        if lower.startswith("kb/") or lower.startswith("artifacts/"):
            tracked.append(normalized)
    return tracked
