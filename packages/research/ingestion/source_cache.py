"""RIS Phase 4 — raw-source cache.

Provides disk-backed preservation of original payloads with metadata.
Raw payloads are stored before any processing or transformation, ensuring
the original scraped or fetched content is always recoverable.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def make_source_id(canonical_url: str) -> str:
    """Compute a deterministic 16-char source ID from a canonical URL.

    Parameters
    ----------
    canonical_url:
        The canonical URL of the source (after normalization).

    Returns
    -------
    str
        First 16 hex characters of SHA-256 of the UTF-8-encoded URL.
    """
    return hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()[:16]


def _utcnow_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class RawSourceCache:
    """Disk-backed cache storing original source payloads with metadata.

    Storage layout:
        {cache_dir}/{source_family}/{source_id}.json

    Each cached file is a JSON envelope:
        {
            "source_id": str,
            "source_family": str,
            "cached_at": "<UTC ISO-8601>",
            "payload": <original dict>
        }

    Parameters
    ----------
    cache_dir:
        Root directory for the cache. Created automatically if it does not
        exist.
    """

    def __init__(self, cache_dir: "str | Path") -> None:
        self._root = Path(cache_dir)

    def _path(self, source_id: str, source_family: str) -> Path:
        return self._root / source_family / f"{source_id}.json"

    def cache_raw(self, source_id: str, payload: dict, source_family: str) -> Path:
        """Write *payload* to disk under *source_family/source_id.json*.

        Parameters
        ----------
        source_id:
            Deterministic identifier for this source (e.g. from make_source_id).
        payload:
            The original raw dict produced by a scraper or fixture loader.
        source_family:
            Source-family key (e.g. "academic", "github", "blog").

        Returns
        -------
        Path
            The path where the envelope was written.
        """
        path = self._path(source_id, source_family)
        path.parent.mkdir(parents=True, exist_ok=True)
        envelope = {
            "source_id": source_id,
            "source_family": source_family,
            "cached_at": _utcnow_iso(),
            "payload": payload,
        }
        path.write_text(
            json.dumps(envelope, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def get_raw(self, source_id: str, source_family: str) -> Optional[dict]:
        """Read the cached envelope for *source_id* / *source_family*.

        Returns
        -------
        dict or None
            The full envelope dict (including ``payload`` key), or None if
            the entry does not exist.
        """
        path = self._path(source_id, source_family)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def has_raw(self, source_id: str, source_family: str) -> bool:
        """Return True if *source_id* / *source_family* is cached."""
        return self._path(source_id, source_family).exists()
