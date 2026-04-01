"""RIS v1 ingestion — extractor ABC and PlainTextExtractor.

Extractors convert a source (file path or raw text) into an ExtractedDocument
dataclass ready for hard-stop checking and pipeline ingestion.
"""

from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from packages.research.evaluation.types import SOURCE_FAMILIES

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ExtractedDocument:
    """Intermediate representation produced by an extractor.

    Attributes
    ----------
    title:
        Human-readable document title.
    body:
        Full document body text.
    source_url:
        Origin URL or internal reference (e.g. ``file:///abs/path``).
    source_family:
        Source-family key matching freshness_decay.json entries.
    author:
        Document author (default: "unknown").
    publish_date:
        ISO-8601 string of the publication date, or None if unknown.
    metadata:
        Arbitrary extra key/value pairs (e.g. ``content_hash``).
    """
    title: str
    body: str
    source_url: str
    source_family: str
    author: str = "unknown"
    publish_date: Optional[str] = None
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Extractor ABC
# ---------------------------------------------------------------------------

class Extractor(ABC):
    """Abstract base class for document extractors."""

    @abstractmethod
    def extract(self, source: "str | Path", **kwargs) -> ExtractedDocument:
        """Extract a document from *source*.

        Parameters
        ----------
        source:
            A file path (``str`` or ``Path``) or raw text string.
        **kwargs:
            Extractor-specific options (e.g. ``title``, ``source_type``,
            ``author``, ``publish_date``).

        Returns
        -------
        ExtractedDocument
        """
        ...


# ---------------------------------------------------------------------------
# PlainTextExtractor
# ---------------------------------------------------------------------------

_H1_RE = re.compile(r"^#\s+(.+)", re.MULTILINE)


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class PlainTextExtractor(Extractor):
    """Extract plain text and Markdown files (or raw strings).

    File mode (default)
    -------------------
    Pass a ``Path`` or a string that points to an existing file.
    - Title: first Markdown H1 (``# Title``) if present; else filename stem.
    - Body: entire file content (utf-8).
    - source_url: ``file://{absolute_path}``.

    Raw-text mode
    -------------
    Pass a string that does NOT point to an existing file.
    - ``title`` kwarg is **required**.
    - Body: the string itself.
    - source_url: ``internal://manual``.

    Common kwargs
    -------------
    source_type : str
        Source type key (default: ``"manual"``).  Mapped to ``source_family``
        via ``SOURCE_FAMILIES``; falls back to the source_type itself.
    author : str
        Document author (default: ``"unknown"``).
    publish_date : str or None
        ISO-8601 publication date (default: ``None``).
    title : str
        Required in raw-text mode; optional override in file mode.
    """

    def extract(self, source: "str | Path", **kwargs) -> ExtractedDocument:  # type: ignore[override]
        source_type: str = kwargs.get("source_type", "manual")
        author: str = kwargs.get("author", "unknown")
        publish_date: Optional[str] = kwargs.get("publish_date", None)

        # Determine source_family from source_type via mapping
        source_family: str = SOURCE_FAMILIES.get(source_type, source_type)

        # --- decide mode ---
        as_path = Path(source) if isinstance(source, str) else source
        if as_path.exists():
            # File mode
            body = as_path.read_text(encoding="utf-8")
            abs_path = str(as_path.resolve()).replace("\\", "/")
            source_url = f"file://{abs_path}"

            # Title from H1 or filename stem
            title_override = kwargs.get("title")
            if title_override:
                title = title_override
            else:
                m = _H1_RE.search(body)
                title = m.group(1).strip() if m else as_path.stem

        else:
            # Raw-text mode: source must be a non-file string
            if isinstance(source, Path):
                raise FileNotFoundError(f"No such file: {source}")
            # Check if caller meant a file path that doesn't exist
            if isinstance(source, str) and "/" in source or (isinstance(source, str) and "\\" in source):
                # Looks like a path that doesn't exist
                raise FileNotFoundError(f"No such file: {source}")

            title = kwargs.get("title")
            if not title:
                raise ValueError(
                    "PlainTextExtractor: 'title' kwarg is required in raw-text mode."
                )
            body = str(source)
            source_url = "internal://manual"

        content_hash = _sha256_hex(body)
        metadata = {"content_hash": content_hash}

        return ExtractedDocument(
            title=title,
            body=body,
            source_url=source_url,
            source_family=source_family,
            author=author,
            publish_date=publish_date,
            metadata=metadata,
        )


# ---------------------------------------------------------------------------
# MarkdownExtractor
# ---------------------------------------------------------------------------


class MarkdownExtractor(Extractor):
    """Extract Markdown files into ExtractedDocument.

    Delegates entirely to PlainTextExtractor — Markdown files are plain text
    and the H1-title extraction already works correctly there.  This class
    exists so callers can request ``get_extractor('markdown')`` and get an
    explicitly named extractor rather than the generic PlainTextExtractor.
    """

    def __init__(self) -> None:
        self._delegate = PlainTextExtractor()

    def extract(self, source: "str | Path", **kwargs) -> ExtractedDocument:  # type: ignore[override]
        return self._delegate.extract(source, **kwargs)


# ---------------------------------------------------------------------------
# Stub extractors (not-yet-implemented; raise NotImplementedError)
# ---------------------------------------------------------------------------


class StubPDFExtractor(Extractor):
    """Stub PDF extractor — raises NotImplementedError until a real library is wired.

    When a PDF extraction library is chosen (docling, marker, or pymupdf4llm),
    replace this class body with the real implementation.
    """

    def extract(self, source: "str | Path", **kwargs) -> ExtractedDocument:  # type: ignore[override]
        raise NotImplementedError(
            "PDF extraction requires an external library. "
            "Install and configure one of: docling, marker, pymupdf4llm. "
            "Replace StubPDFExtractor with a real implementation once chosen."
        )


class StubDocxExtractor(Extractor):
    """Stub DOCX extractor — raises NotImplementedError until python-docx is wired.

    When DOCX support is needed, install python-docx and replace this class body
    with a real implementation.
    """

    def extract(self, source: "str | Path", **kwargs) -> ExtractedDocument:  # type: ignore[override]
        raise NotImplementedError(
            "DOCX extraction requires python-docx. "
            "Install it (pip install python-docx) and replace StubDocxExtractor "
            "with a real implementation."
        )


# ---------------------------------------------------------------------------
# Extractor registry and factory
# ---------------------------------------------------------------------------

EXTRACTOR_REGISTRY: dict[str, type[Extractor]] = {
    "plain_text": PlainTextExtractor,
    "markdown": MarkdownExtractor,
    "pdf": StubPDFExtractor,
    "docx": StubDocxExtractor,
}


def get_extractor(name: str) -> Extractor:
    """Return an instantiated extractor for *name*.

    Parameters
    ----------
    name:
        Key in ``EXTRACTOR_REGISTRY`` (e.g. ``"plain_text"``, ``"markdown"``).

    Returns
    -------
    Extractor
        A new instance of the requested extractor class.

    Raises
    ------
    KeyError
        If *name* is not in ``EXTRACTOR_REGISTRY``.
    """
    cls = EXTRACTOR_REGISTRY[name]
    return cls()
