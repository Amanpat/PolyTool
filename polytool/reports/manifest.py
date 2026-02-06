"""Run Manifest builder.

Produces a JSON manifest capturing run provenance: timing, command,
user context, output paths, config hash, and version information.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import polytool

MANIFEST_VERSION = "1.0.0"


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _duration_seconds(started: str, finished: str) -> float:
    """Compute seconds between two ISO timestamps."""
    try:
        fmt = "%Y-%m-%dT%H:%M:%S%z"
        t0 = datetime.fromisoformat(started)
        t1 = datetime.fromisoformat(finished)
        return round((t1 - t0).total_seconds(), 3)
    except (ValueError, TypeError):
        return 0.0


def _git_commit() -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def stable_config_hash(config: Dict[str, Any]) -> str:
    """SHA-256 of deterministically-serialised config dict.

    Secrets (keys containing 'password', 'secret', 'token', 'key')
    are redacted before hashing.
    """
    redacted = _redact_secrets(config)
    canonical = json.dumps(redacted, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _redact_secrets(obj: Any) -> Any:
    secret_keys = {"password", "secret", "token", "key", "api_key"}
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if any(s in k.lower() for s in secret_keys):
                out[k] = "<REDACTED>"
            else:
                out[k] = _redact_secrets(v)
        return out
    if isinstance(obj, list):
        return [_redact_secrets(item) for item in obj]
    return obj


def build_run_manifest(
    run_id: str,
    started_at: str,
    command_name: str,
    argv: List[str],
    user_input: str,
    user_slug: str,
    wallets: List[str],
    output_paths: Dict[str, str],
    effective_config: Optional[Dict[str, Any]] = None,
    finished_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a Run Manifest dict.

    Parameters
    ----------
    run_id : str
        Unique run identifier.
    started_at : str
        ISO-8601 timestamp when the run started.
    command_name : str
        CLI command name (e.g. "examine").
    argv : list[str]
        Safe CLI arguments (secrets should already be stripped).
    user_input : str
        Original --user value.
    user_slug : str
        Canonical slug.
    wallets : list[str]
        Wallet addresses involved.
    output_paths : dict
        Mapping of path labels to filesystem paths.
    effective_config : dict | None
        Config dict to hash (secrets auto-redacted).
    finished_at : str | None
        ISO-8601 timestamp when the run finished.  If ``None``,
        ``_now_utc()`` is used.
    """
    fin = finished_at or _now_utc()
    duration = _duration_seconds(started_at, fin)

    config_hash = ""
    if effective_config:
        config_hash = stable_config_hash(effective_config)

    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": fin,
        "duration_seconds": duration,
        "command_name": command_name,
        "argv": argv,
        "user_input": user_input,
        "user_slug": user_slug,
        "wallets": wallets,
        "output_paths": output_paths,
        "effective_config_hash_sha256": config_hash,
        "polytool_version": polytool.__version__,
        "git_commit": _git_commit(),
    }
    return manifest


def write_run_manifest(
    manifest: Dict[str, Any],
    output_dir: Path,
) -> str:
    """Write ``run_manifest.json`` to *output_dir* and return the path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "run_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)
