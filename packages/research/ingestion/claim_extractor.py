"""RIS Phase 4: Heuristic claim extraction pipeline.

Extracts structured DERIVED_CLAIM records from already-ingested source documents,
creates chunk-level CLAIM_EVIDENCE links, and builds lightweight typed relations
(SUPPORTS, CONTRADICTS) between claims sharing key terms.

Design constraints:
- No LLM calls. Entirely heuristic / regex-based.
- No network calls. All reads from KnowledgeStore + local file paths.
- Deterministic: same doc + same extractor version = same claim IDs (INSERT OR IGNORE).
- Offline safe: all tests use KnowledgeStore(":memory:") and tmp_path fixtures.

Public API:
- ``extract_claims_from_document(store, doc_id) -> list[str]``
- ``build_intra_doc_relations(store, claim_ids) -> int``
- ``extract_and_link(store, doc_id) -> dict``
- ``HeuristicClaimExtractor`` (class wrapper for registry consistency)
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from packages.polymarket.rag.knowledge_store import KnowledgeStore

from packages.polymarket.rag.chunker import chunk_text

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_log = logging.getLogger(__name__)

EXTRACTOR_ID = "heuristic_v1"

# Trust tier -> confidence mapping
_TIER_CONFIDENCE: dict[str | None, float] = {
    "PEER_REVIEWED": 0.85,
    "PRACTITIONER": 0.70,
    "COMMUNITY": 0.55,
}

_DEFAULT_CONFIDENCE = 0.70

# Minimum sentence length to be considered assertive
_MIN_SENTENCE_LENGTH = 30

# Maximum assertive sentences extracted per chunk
_MAX_SENTENCES_PER_CHUNK = 5

# Minimum shared key terms to create a relation between two claims
_MIN_SHARED_TERMS_FOR_RELATION = 3

# Stopwords to filter when extracting key terms
_STOPWORDS: frozenset[str] = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "has", "have", "had", "do", "does", "did", "will", "would",
    "could", "should", "can", "may", "might", "shall",
    "to", "of", "in", "for", "on", "at", "by", "with", "from",
    "and", "or", "but", "if", "then", "that", "this", "it", "its",
    "they", "them", "their", "we", "our", "you", "your",
    "he", "she", "him", "her", "also", "just", "more", "most",
    "all", "some", "any", "each", "into", "about", "which", "who",
    "when", "where", "while", "than", "so", "as", "up", "out",
    "what", "how", "why", "not", "no", "nor", "yet", "both",
})

# Negation qualifiers — case-insensitive word/phrase matching
_NEGATION_PATTERNS: tuple[str, ...] = (
    r"\bnot\b",
    r"\bno\b",
    r"\bnever\b",
    r"\bcannot\b",
    r"\bunlikely\b",
    r"\bincorrect\b",
    r"\bfalse\b",
    r"\bfail\b",
    r"\breject\b",
    r"\bdon't\b",
    r"\bdoesn't\b",
    r"\bwon't\b",
    r"\bshouldn't\b",
    r"\bdoesnt\b",
    r"\bwont\b",
    r"\bshouldnt\b",
    r"\bdont\b",
    r"\bcan't\b",
    r"\bcant\b",
)

# Lines that should be skipped in sentence extraction
_SKIP_LINE_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p) for p in [
        r"^\s*[#|>`~]",           # headings, blockquotes, code fences, tildes
        r"^\s*[-*]\s*$",          # empty list markers
        r"^\s*```",               # code fence markers
        r"^\s*\|",                # table rows
        r"^\s*[-=]{3,}\s*$",      # horizontal rules
        r"https?://\S+",          # pure URL lines
        r"^\s*\d+\.\s*$",         # numbered list markers only
    ]
)

# Heading detection pattern (for section heading extraction)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

# Claim type classification patterns
_EMPIRICAL_RE = re.compile(r"\d+%|\d+\.\d+|\b\d{3,}\b")
_NORMATIVE_RE = re.compile(r"\bshould\b|\bmust\b|\brecommend\b|\bbest practice\b", re.IGNORECASE)
_STRUCTURAL_RE = re.compile(
    r"\barchitecture\b|\bsystem\b|\bdesign\b|\bstructure\b|\blayer\b", re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Helper functions (public for testability)
# ---------------------------------------------------------------------------

def _confidence_for_tier(trust_tier: str | None) -> float:
    """Map a trust_tier string to a confidence float.

    PEER_REVIEWED -> 0.85
    PRACTITIONER  -> 0.70
    COMMUNITY     -> 0.55
    default       -> 0.70
    """
    return _TIER_CONFIDENCE.get(trust_tier, _DEFAULT_CONFIDENCE)


def _classify_claim_type(sentence: str) -> str:
    """Classify a sentence as empirical, normative, or structural.

    Checks patterns in priority order:
    1. empirical  — contains numbers/percentages (strong signal for data claims)
    2. normative  — contains should/must/recommend/best practice
    3. structural — contains architecture/system/design/structure/layer
    4. default    -> "empirical"
    """
    if _EMPIRICAL_RE.search(sentence):
        return "empirical"
    if _NORMATIVE_RE.search(sentence):
        return "normative"
    if _STRUCTURAL_RE.search(sentence):
        return "structural"
    return "empirical"


def _has_negation(sentence: str) -> bool:
    """Return True if sentence contains any negation qualifier.

    Checks for: not, no, never, cannot, unlikely, incorrect, false,
    fail, reject, don't, doesn't, won't, shouldn't (case-insensitive).
    """
    s_lower = sentence.lower()
    for pattern in _NEGATION_PATTERNS:
        if re.search(pattern, s_lower):
            return True
    return False


def _extract_key_terms(sentence: str) -> set[str]:
    """Extract non-stopword content terms from a sentence.

    Lowercases, splits on whitespace/punctuation, filters stopwords,
    returns terms with len >= 3.
    """
    words = re.split(r"[\s,.\-;:!?()\[\]\"']+", sentence.lower())
    return {w for w in words if w and len(w) >= 3 and w not in _STOPWORDS}


def _is_skip_line(line: str) -> bool:
    """Return True if the line should be skipped during sentence extraction."""
    for pattern in _SKIP_LINE_PATTERNS:
        if pattern.search(line):
            return True
    return False


def _extract_assertive_sentences(text: str) -> list[str]:
    """Extract up to 5 assertive sentences from a chunk of text.

    The chunker (chunk_text) joins words with spaces, so the chunk text is a
    single long string that may contain inline Markdown artifacts like
    ``## Heading`` or ``| col |`` that appeared as separate lines in the source.

    Filters out:
    - Markdown heading tokens (``#`` at the start of a token group)
    - Table-row-looking fragments starting with ``|``
    - Code-fence markers (` ``` `)
    - Blockquote markers (``>``)
    - Very short fragments (< 30 chars)
    - All-caps tokens
    - Code-looking phrases (def /class /import /return )

    Splits on sentence boundaries (period/exclamation/question mark followed
    by whitespace or end-of-string).
    Returns up to MAX_SENTENCES_PER_CHUNK assertive sentences.
    """
    # First, clean out heading tokens that got merged into the chunk.
    # The chunker joins all words with spaces, so "#" or "##" appear inline.
    # Strategy: remove "# Word Word" tokens up to the next capital-start word
    # that begins a real sentence. We match "# ..." up to next sentence start.
    # Step 1: Remove heading sequences like "# Research Document" or "## Market Analysis"
    # These appear as "#{1,6} WORD [WORD]* " in the chunk.
    # We match the hash chars + following TITLE CASE words (Title or ALL) until
    # we hit a lowercase-continuation word that starts the actual sentence.
    cleaned = re.sub(r"#{1,6}\s+(?:[A-Z][A-Za-z]* ?)+", " ", text)
    # Remove table-row fragments: "| word | word |" etc.
    cleaned = re.sub(r"\|[^|]+\|", " ", cleaned)
    # Remove isolated pipe chars left after table cleanup
    cleaned = re.sub(r"\|\s*", " ", cleaned)
    # Remove code fence markers
    cleaned = re.sub(r"```\S*", " ", cleaned)
    # Remove blockquote markers at word boundaries
    cleaned = re.sub(r"\s>\s", " ", cleaned)
    # Normalize whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Split into sentence candidates
    # Split at period/exclamation/question followed by whitespace or end
    raw_sentences = re.split(r"(?<=[.!?])(?:\s+|$)", cleaned)

    candidates: list[str] = []
    for sent in raw_sentences:
        sent = sent.strip()
        if len(sent) < _MIN_SENTENCE_LENGTH:
            continue
        # Skip all-caps sentences (likely headers or acronym blocks)
        if sent.isupper():
            continue
        # Skip code-looking sentences
        if re.search(r"\b(def |class |import |from |return )", sent):
            continue
        # Skip if starts with a markdown heading token
        if sent.startswith("#"):
            continue
        # Skip if starts with table marker
        if sent.startswith("|"):
            continue
        candidates.append(sent)

    return candidates[:_MAX_SENTENCES_PER_CHUNK]


def _find_section_heading(body: str, start_word: int) -> str:
    """Find the nearest preceding section heading for a chunk starting at start_word.

    Scans the body text for heading lines, maps them to word positions,
    and returns the last heading before start_word.
    """
    words = body.split()
    word_count = 0
    last_heading = ""

    for line in body.splitlines():
        line_words = line.split()
        heading_match = _HEADING_RE.match(line.strip())
        if heading_match:
            if word_count <= start_word:
                last_heading = heading_match.group(2).strip()
        word_count += len(line_words)
        if word_count > start_word and last_heading:
            break

    return last_heading


def _get_document_body(store: "KnowledgeStore", doc: dict) -> str | None:
    """Retrieve the body text for a source document.

    Strategy:
    1. Check metadata_json for a 'body' key (some tests may inject this).
    2. Try to read from source_url if it's a file:// path.
    3. Return None if neither works.
    """
    # Strategy 1: body in metadata_json
    metadata_json = doc.get("metadata_json")
    if metadata_json:
        try:
            meta = json.loads(metadata_json)
            if "body" in meta and meta["body"]:
                return str(meta["body"])
        except (json.JSONDecodeError, TypeError):
            pass

    # Strategy 2: file:// source_url
    source_url = doc.get("source_url", "")
    if source_url and source_url.startswith("file://"):
        file_path_str = source_url[len("file://"):]
        # Handle both posix and windows paths
        try:
            file_path = Path(file_path_str)
            if file_path.exists():
                return file_path.read_text(encoding="utf-8")
        except (OSError, ValueError):
            pass

    return None


def _get_scope_from_metadata(doc: dict) -> str | None:
    """Extract scope from document metadata_json tags field."""
    metadata_json = doc.get("metadata_json")
    if not metadata_json:
        return None
    try:
        meta = json.loads(metadata_json)
        tags = meta.get("tags")
        if tags:
            # Return first tag as scope, or all tags as comma-separated
            return str(tags)
    except (json.JSONDecodeError, TypeError):
        pass
    return None


# ---------------------------------------------------------------------------
# Internal: deterministic timestamp for idempotent IDs
# ---------------------------------------------------------------------------

def _deterministic_created_at(doc_id: str, sentence: str, chunk_id: int) -> str:
    """Generate a deterministic ISO-8601 timestamp string for claim ID derivation.

    The KnowledgeStore uses _sha256_id("claim", claim_text, actor, created_at)
    to generate claim IDs. By providing a deterministic created_at (derived from
    the content itself), we ensure that re-running extraction on the same doc
    produces identical claim IDs, making extraction idempotent.

    The value is formatted as a valid ISO-8601 string (year 2000-01-01 + offset)
    to satisfy any downstream date parsing, but the actual value is derived from
    content hash to be unique per sentence.
    """
    seed = hashlib.sha256(
        f"{doc_id}\0{sentence}\0{chunk_id}\0{EXTRACTOR_ID}".encode()
    ).hexdigest()[:8]
    # Format as valid ISO-8601 using a fixed epoch with hex offset as microseconds
    # This is deterministic and parseable, just not a real timestamp
    offset_micros = int(seed, 16) % 1_000_000
    return f"2000-01-01T00:00:00.{offset_micros:06d}+00:00"


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

def extract_claims_from_document(
    store: "KnowledgeStore",
    doc_id: str,
) -> list[str]:
    """Extract structured DERIVED_CLAIM records from an ingested source document.

    For each chunk of the document body:
    - Extracts assertive sentences via _extract_assertive_sentences.
    - Creates a derived_claims record for each sentence.
    - Creates a claim_evidence record linking the claim to the chunk excerpt.

    Parameters
    ----------
    store:
        A KnowledgeStore instance (may be in-memory for tests).
    doc_id:
        The source document ID to extract claims from.

    Returns
    -------
    list[str]
        List of claim IDs created (or already existing on re-run).
        Returns empty list if doc not found or body is empty.
    """
    # Load source document
    doc = store.get_source_document(doc_id)
    if doc is None:
        return []

    # Get body text
    body = _get_document_body(store, doc)
    if not body or not body.strip():
        return []

    # Determine trust tier and confidence
    trust_tier = doc.get("confidence_tier") or "PRACTITIONER"
    confidence = _confidence_for_tier(trust_tier)

    # Determine scope from metadata
    scope = _get_scope_from_metadata(doc)

    # Chunk the body
    chunks = chunk_text(body)
    if not chunks:
        return []

    claim_ids: list[str] = []

    for chunk in chunks:
        # Find section heading for this chunk
        section_heading = _find_section_heading(body, chunk.start_word)

        # Extract assertive sentences
        sentences = _extract_assertive_sentences(chunk.text)
        if not sentences:
            continue

        for sentence in sentences:
            # Classify claim type
            claim_type = _classify_claim_type(sentence)

            # Build notes JSON
            notes_dict = {
                "extractor_id": EXTRACTOR_ID,
                "chunk_id": chunk.chunk_id,
                "document_id": doc_id,
                "section_heading": section_heading,
            }

            # Build location JSON for evidence
            location_dict = {
                "chunk_id": chunk.chunk_id,
                "start_word": chunk.start_word,
                "end_word": chunk.end_word,
                "document_id": doc_id,
                "section_heading": section_heading,
            }

            # Build deterministic created_at so re-running produces the same claim ID
            det_created_at = _deterministic_created_at(doc_id, sentence, chunk.chunk_id)

            # Store claim
            claim_id = store.add_claim(
                claim_text=sentence,
                claim_type=claim_type,
                confidence=confidence,
                trust_tier=trust_tier,
                validation_status="UNTESTED",
                lifecycle="active",
                actor=EXTRACTOR_ID,
                created_at=det_created_at,
                source_document_id=doc_id,
                scope=scope,
                tags=None,
                notes=json.dumps(notes_dict),
            )

            # Store evidence link — only insert if this claim was just created (INSERT OR IGNORE
            # on claims means the claim row already exists on second run; we check evidence too).
            existing_evidence = store._conn.execute(
                "SELECT 1 FROM claim_evidence WHERE claim_id = ? AND source_document_id = ?",
                (claim_id, doc_id),
            ).fetchone()
            if existing_evidence is None:
                store.add_evidence(
                    claim_id=claim_id,
                    source_document_id=doc_id,
                    excerpt=chunk.text[:500],
                    location=json.dumps(location_dict),
                )

            claim_ids.append(claim_id)

    return claim_ids


# ---------------------------------------------------------------------------
# Relation builder
# ---------------------------------------------------------------------------

def build_intra_doc_relations(
    store: "KnowledgeStore",
    claim_ids: list[str],
) -> int:
    """Build SUPPORTS / CONTRADICTS relations between claims in the same document.

    For each pair (i, j) where i < j:
    - Loads both claims.
    - Extracts key terms from both.
    - If shared_terms >= MIN_SHARED_TERMS_FOR_RELATION:
      - If one claim has negation and the other does not -> CONTRADICTS
      - Else -> SUPPORTS
    - Calls store.add_relation().

    Parameters
    ----------
    store:
        A KnowledgeStore instance.
    claim_ids:
        List of claim IDs to compare pairwise.

    Returns
    -------
    int
        Count of relations created.
    """
    if len(claim_ids) < 2:
        return 0

    # Pre-load all claims to avoid N+1
    claims: dict[str, dict] = {}
    for cid in claim_ids:
        claim = store.get_claim(cid)
        if claim:
            claims[cid] = claim

    relation_count = 0

    for i in range(len(claim_ids)):
        for j in range(i + 1, len(claim_ids)):
            cid_i = claim_ids[i]
            cid_j = claim_ids[j]

            claim_i = claims.get(cid_i)
            claim_j = claims.get(cid_j)

            if claim_i is None or claim_j is None:
                continue

            text_i = claim_i.get("claim_text", "")
            text_j = claim_j.get("claim_text", "")

            terms_i = _extract_key_terms(text_i)
            terms_j = _extract_key_terms(text_j)

            shared_terms = terms_i & terms_j
            if len(shared_terms) < _MIN_SHARED_TERMS_FOR_RELATION:
                continue

            # Determine relation type based on negation
            neg_i = _has_negation(text_i)
            neg_j = _has_negation(text_j)

            if neg_i != neg_j:
                # One has negation, the other does not -> CONTRADICTS
                relation_type = "CONTRADICTS"
            else:
                relation_type = "SUPPORTS"

            try:
                store.add_relation(cid_i, cid_j, relation_type)
                relation_count += 1
            except sqlite3.IntegrityError:
                _log.debug(
                    "Constraint violation for relation %s->%s (%s), skipping",
                    cid_i, cid_j, relation_type,
                )

    return relation_count


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------

def extract_and_link(
    store: "KnowledgeStore",
    doc_id: str,
) -> dict:
    """Extract claims from a document and build intra-document relations.

    Convenience wrapper that calls extract_claims_from_document and
    build_intra_doc_relations in sequence.

    Parameters
    ----------
    store:
        A KnowledgeStore instance.
    doc_id:
        The source document ID to process.

    Returns
    -------
    dict
        Summary dict with keys:
        - doc_id: str
        - claims_extracted: int
        - relations_created: int
        - claim_ids: list[str]
    """
    claim_ids = extract_claims_from_document(store, doc_id)
    relation_count = build_intra_doc_relations(store, claim_ids) if claim_ids else 0

    return {
        "doc_id": doc_id,
        "claims_extracted": len(claim_ids),
        "relations_created": relation_count,
        "claim_ids": claim_ids,
    }


# ---------------------------------------------------------------------------
# HeuristicClaimExtractor class (for registry consistency)
# ---------------------------------------------------------------------------

class HeuristicClaimExtractor:
    """Class wrapper around the heuristic claim extraction functions.

    Provides a consistent interface with other extractor classes in the
    research ingestion pipeline.
    """

    EXTRACTOR_ID: str = EXTRACTOR_ID

    def extract_claims(
        self,
        store: "KnowledgeStore",
        doc_id: str,
    ) -> list[str]:
        """Extract claims from an ingested document.

        Parameters
        ----------
        store:
            A KnowledgeStore instance.
        doc_id:
            Source document ID to extract from.

        Returns
        -------
        list[str]
            List of claim IDs created.
        """
        return extract_claims_from_document(store, doc_id)

    def link(
        self,
        store: "KnowledgeStore",
        claim_ids: list[str],
    ) -> int:
        """Build intra-document relations for a list of claim IDs.

        Parameters
        ----------
        store:
            A KnowledgeStore instance.
        claim_ids:
            List of claim IDs to build relations for.

        Returns
        -------
        int
            Number of relations created.
        """
        return build_intra_doc_relations(store, claim_ids)

    def extract_and_link(
        self,
        store: "KnowledgeStore",
        doc_id: str,
    ) -> dict:
        """Extract claims and build relations in one pass.

        Returns
        -------
        dict
            Same as extract_and_link() function.
        """
        return extract_and_link(store, doc_id)
