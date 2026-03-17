"""Contract validation and freeze-lock helpers for benchmark tape manifests."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from tools.cli.benchmark_manifest import (
    BENCHMARK_VERSION,
    BUCKET_ORDER,
    MANIFEST_SCHEMA_VERSION,
    QUOTAS,
    discover_candidates_from_paths,
    select_manifest,
)

LOCK_SCHEMA_VERSION = "benchmark_tape_lock_v1"


class BenchmarkManifestValidationError(ValueError):
    """Raised when a benchmark manifest breaks the contract."""

    def __init__(self, manifest_path: Path, issues: list[str]) -> None:
        self.manifest_path = manifest_path
        self.issues = list(issues)
        super().__init__(self._build_message())

    def _build_message(self) -> str:
        joined = "; ".join(self.issues)
        return f"benchmark manifest invalid: {self.manifest_path} ({joined})"


@dataclass(frozen=True)
class BenchmarkManifestValidationResult:
    manifest_path: str
    resolved_manifest_path: Path
    manifest_entries: list[str]
    resolved_tape_paths: list[Path]
    bucket_counts: dict[str, int]
    manifest_sha256: str
    tape_fingerprints: dict[str, str]

    def build_lock_payload(self) -> dict[str, Any]:
        return {
            "schema_version": LOCK_SCHEMA_VERSION,
            "benchmark_version": BENCHMARK_VERSION,
            "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
            "generated_at": _utcnow(),
            "manifest_path": self.manifest_path,
            "manifest_sha256": self.manifest_sha256,
            "tape_count": len(self.manifest_entries),
            "bucket_counts": dict(self.bucket_counts),
            "tape_paths": list(self.manifest_entries),
            "tape_fingerprints": dict(self.tape_fingerprints),
        }


def validate_benchmark_manifest(
    manifest_path: Path,
    *,
    lock_path: Optional[Path] = None,
) -> BenchmarkManifestValidationResult:
    payload = _read_json(manifest_path, label="manifest file")
    return validate_benchmark_manifest_payload(
        payload,
        manifest_path=manifest_path,
        lock_path=lock_path,
    )


def validate_benchmark_manifest_payload(
    payload: Any,
    *,
    manifest_path: Path,
    lock_path: Optional[Path] = None,
) -> BenchmarkManifestValidationResult:
    issues: list[str] = []
    resolved_manifest_path = _resolve_manifest_path(manifest_path)
    display_manifest_path = _normalize_path(resolved_manifest_path)

    if not isinstance(payload, list):
        raise BenchmarkManifestValidationError(
            manifest_path=resolved_manifest_path,
            issues=["manifest root must be a JSON array of tape paths"],
        )

    resolved_tapes: list[Path] = []
    canonical_entries: list[str] = []
    seen_by_resolved: dict[str, int] = {}

    for idx, raw_entry in enumerate(payload):
        if not isinstance(raw_entry, str):
            issues.append(f"entry {idx} must be a string path")
            continue

        raw_text = raw_entry.strip()
        if not raw_text:
            issues.append(f"entry {idx} must be a non-empty string path")
            continue

        resolved_tape = _resolve_manifest_path(Path(raw_text))
        canonical_entry = _normalize_path(resolved_tape)
        if raw_entry != canonical_entry:
            issues.append(
                f"entry {idx} must use canonical path '{canonical_entry}' (got '{raw_entry}')"
            )

        resolved_key = str(resolved_tape.resolve(strict=False))
        first_idx = seen_by_resolved.get(resolved_key)
        if first_idx is not None:
            issues.append(
                f"duplicate tape path at entry {idx}: {canonical_entry} "
                f"(already used at entry {first_idx})"
            )
        else:
            seen_by_resolved[resolved_key] = idx

        canonical_entries.append(canonical_entry)
        resolved_tapes.append(resolved_tape)

    expected_count = sum(QUOTAS.values())
    if len(payload) != expected_count:
        issues.append(
            f"manifest must contain exactly {expected_count} tape paths; found {len(payload)}"
        )

    missing_entries: list[str] = []
    existing_unique_paths: list[Path] = []
    existing_seen: set[str] = set()
    for idx, tape_path in enumerate(resolved_tapes):
        canonical_entry = canonical_entries[idx]
        if not tape_path.is_file():
            missing_entries.append(canonical_entry)
            issues.append(f"missing tape file at entry {idx}: {canonical_entry}")
            continue
        resolved_key = str(tape_path.resolve(strict=False))
        if resolved_key in existing_seen:
            continue
        existing_seen.add(resolved_key)
        existing_unique_paths.append(tape_path)

    candidates, skipped = discover_candidates_from_paths(existing_unique_paths)
    for skipped_tape in skipped:
        issues.append(f"{skipped_tape.tape_path}: {skipped_tape.reason}")

    for candidate in candidates:
        if not candidate.candidate_buckets:
            issues.append(
                f"tape is not eligible for any roadmap bucket: {candidate.tape_path}"
            )

    selection = select_manifest(candidates)
    if not selection.success:
        shortages = ", ".join(
            f"{bucket}={selection.shortages[bucket]}"
            for bucket in BUCKET_ORDER
            if selection.shortages[bucket] > 0
        )
        issues.append(f"required bucket counts not satisfied: {shortages}")

    if (
        not missing_entries
        and len(canonical_entries) == expected_count
        and selection.success
        and canonical_entries != selection.selected_paths
    ):
        issues.append(
            "manifest order does not match canonical benchmark_v1 bucket order"
        )

    if issues:
        raise BenchmarkManifestValidationError(
            manifest_path=resolved_manifest_path,
            issues=issues,
        )

    manifest_sha256 = _sha256_text(_canonical_manifest_json(canonical_entries))
    tape_fingerprints = {
        candidate.tape_path: _sha256_file(path)
        for candidate, path in zip(
            sorted(candidates, key=lambda item: item.tape_path),
            sorted(existing_unique_paths, key=lambda item: _normalize_path(item)),
            strict=True,
        )
    }
    bucket_counts = {
        bucket: len(selection.assignments[bucket])
        for bucket in BUCKET_ORDER
    }

    result = BenchmarkManifestValidationResult(
        manifest_path=display_manifest_path,
        resolved_manifest_path=resolved_manifest_path,
        manifest_entries=list(canonical_entries),
        resolved_tape_paths=list(resolved_tapes),
        bucket_counts=bucket_counts,
        manifest_sha256=manifest_sha256,
        tape_fingerprints=tape_fingerprints,
    )

    if lock_path is not None and lock_path.exists():
        lock_issues = _validate_lock_payload(
            result=result,
            lock_payload=_read_json(lock_path, label="lock file"),
            lock_path=lock_path,
        )
        if lock_issues:
            raise BenchmarkManifestValidationError(
                manifest_path=resolved_manifest_path,
                issues=lock_issues,
            )

    return result


def write_benchmark_manifest_lock(
    lock_path: Path,
    result: BenchmarkManifestValidationResult,
) -> None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        json.dumps(result.build_lock_payload(), indent=2) + "\n",
        encoding="utf-8",
    )


def default_lock_path_for_manifest(manifest_path: Path) -> Path:
    name = manifest_path.name
    if name.endswith(".tape_manifest"):
        return manifest_path.with_name(name.replace(".tape_manifest", ".lock.json"))
    if manifest_path.suffix:
        return manifest_path.with_suffix(".lock.json")
    return manifest_path.with_name(f"{manifest_path.name}.lock.json")


def _validate_lock_payload(
    *,
    result: BenchmarkManifestValidationResult,
    lock_payload: Any,
    lock_path: Path,
) -> list[str]:
    display_lock_path = _normalize_path(_resolve_manifest_path(lock_path))
    if not isinstance(lock_payload, dict):
        return [f"lock file is not a JSON object: {display_lock_path}"]

    issues: list[str] = []

    if lock_payload.get("schema_version") != LOCK_SCHEMA_VERSION:
        issues.append(
            f"lock schema_version must be {LOCK_SCHEMA_VERSION!r}: {display_lock_path}"
        )
    if lock_payload.get("benchmark_version") != BENCHMARK_VERSION:
        issues.append(
            f"lock benchmark_version must be {BENCHMARK_VERSION!r}: {display_lock_path}"
        )
    if lock_payload.get("manifest_schema_version") != MANIFEST_SCHEMA_VERSION:
        issues.append(
            "lock manifest_schema_version does not match benchmark manifest contract"
        )
    if lock_payload.get("manifest_path") != result.manifest_path:
        issues.append(
            "lock manifest_path does not match the manifest being validated"
        )
    if lock_payload.get("manifest_sha256") != result.manifest_sha256:
        issues.append("fingerprint drift: manifest content changed since lock creation")

    locked_tape_count = lock_payload.get("tape_count")
    if locked_tape_count != len(result.manifest_entries):
        issues.append(
            "fingerprint drift: lock tape_count does not match current manifest"
        )
    if lock_payload.get("bucket_counts") != result.bucket_counts:
        issues.append(
            "fingerprint drift: lock bucket_counts do not match current manifest"
        )
    if lock_payload.get("tape_paths") != result.manifest_entries:
        issues.append("fingerprint drift: lock tape_paths do not match current manifest")

    locked_fingerprints = lock_payload.get("tape_fingerprints")
    if not isinstance(locked_fingerprints, dict):
        issues.append("lock file missing tape_fingerprints object")
        return issues

    changed_paths = [
        path
        for path, digest in result.tape_fingerprints.items()
        if locked_fingerprints.get(path) != digest
    ]
    removed_paths = [
        path for path in locked_fingerprints if path not in result.tape_fingerprints
    ]
    added_paths = [
        path for path in result.tape_fingerprints if path not in locked_fingerprints
    ]

    if changed_paths:
        issues.append(
            "fingerprint drift: tape file contents changed for "
            + ", ".join(changed_paths)
        )
    if removed_paths:
        issues.append(
            "fingerprint drift: lock references tapes missing from current manifest: "
            + ", ".join(removed_paths)
        )
    if added_paths:
        issues.append(
            "fingerprint drift: current manifest has tapes absent from lock: "
            + ", ".join(added_paths)
        )

    return issues


def _resolve_manifest_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return (_repo_root() / path).resolve(strict=False)


def _normalize_path(path: Path) -> str:
    resolved = path.resolve(strict=False)
    repo_root = _repo_root().resolve(strict=False)
    try:
        return resolved.relative_to(repo_root).as_posix()
    except ValueError:
        return str(resolved)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _canonical_manifest_json(entries: list[str]) -> str:
    return json.dumps(entries, sort_keys=False, separators=(",", ":"), ensure_ascii=True)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_json(path: Path, *, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise BenchmarkManifestValidationError(
            manifest_path=_resolve_manifest_path(path),
            issues=[f"could not read {label}: {exc}"],
        ) from exc
    except json.JSONDecodeError as exc:
        raise BenchmarkManifestValidationError(
            manifest_path=_resolve_manifest_path(path),
            issues=[f"{label} is not valid JSON: {exc}"],
        ) from exc
