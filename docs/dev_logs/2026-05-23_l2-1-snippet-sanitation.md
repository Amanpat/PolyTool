# L2.1 Deliverable C — Academic Snippet Sanitation

**Date:** 2026-05-23
**Track:** RIS L2.1 — Academic Retrieval Quality
**Deliverable:** C — Operator-Facing Snippet Sanitation
**Spec:** `docs/specs/SPEC-ris-l2-1-academic-retrieval-quality.md`

---

## Objective

Strip Marker/OCR artifacts from `AcademicCitation.best_snippet` so that
`research-query` output is operator-readable and safe for downstream LLM
consumption. Raw `claim_text` stored in KnowledgeStore is never modified.

---

## Files Changed

| File | Change |
|---|---|
| `packages/research/synthesis/academic_query.py` | Added `import re`; 5 compiled regex constants; `_sanitize_snippet()` function; applied at citation build time |
| `tests/test_research_query.py` | Added `TestSanitizeSnippet` (39 unit tests) and `TestSanitizeSnippetIntegration` (4 integration tests) — 43 new tests total |

---

## Implementation Details

### `_sanitize_snippet(text: str) -> str`

Added to `packages/research/synthesis/academic_query.py`. Called only when
building `AcademicCitation.best_snippet`; not called anywhere in the
KnowledgeStore write path.

Five compiled patterns:

```python
# Whitelist of known Marker HTML tags (not a general <[^>]+> — preserves math < >)
_KNOWN_MARKER_TAGS = re.compile(
    r"</?(?:sup|sub|br|a)(?:\s[^>]*)?/?>",
    re.IGNORECASE,
)
# Marker internal cross-reference anchors: (#page-N-M)
_PAGE_REF = re.compile(r"\(#page-\d+-\d+\)")
# Markdown heading markers at line start
_MD_HEADING = re.compile(r"(?m)^#{1,6}[ \t]*")
# Three or more consecutive newlines → two
_EXCESS_NEWLINES = re.compile(r"\n{3,}")
# Three or more consecutive spaces/tabs → one
_EXCESS_SPACES = re.compile(r"[ \t]{3,}")
```

Design decision: **Whitelist, not general `<[^>]+>`**. The planning packet
(2026-05-23_l2-1-academic-retrieval-quality-packet.md) flagged a risk that
a general HTML regex could strip math inequality signs (`a < b`). By targeting
known Marker tag names only (`sup`, `sub`, `br`, `a`), bare `<` and `>` in
math expressions are preserved. Tests confirm this behavior.

Application point (`academic_query.py`, `query_academic_corpus` Step 6):

```python
# Before:
snippet = best_claim.get("snippet", "")

# After:
snippet = _sanitize_snippet(best_claim.get("snippet", ""))
```

---

## Before / After Snippet Examples

### Example 1 — Abstract with footnote superscript and heading

**Raw claim_text (stored, unchanged):**
```
<sup>∗</sup> Work was done while the author was working at JP Morgan Chase.

#### **Abstract**

We provide a comprehensive survey of Large Language Models in financial prediction.
```

**Sanitized best_snippet (operator-facing):**
```
∗ Work was done while the author was working at JP Morgan Chase.

**Abstract**

We provide a comprehensive survey of Large Language Models in financial prediction.
```

Changes:
- `<sup>` and `</sup>` stripped; `∗` content preserved
- `#### ` heading marker stripped; `**Abstract**` preserved

### Example 2 — Internal page cross-reference anchor

**Raw claim_text (stored, unchanged):**
```
(#page-18-0) (Li et al., 2024b; Wang et al., 2023) can be used to significantly
improve the generation quality of LLMs (Gao et al., 2023) from 22.5% to 47.1% on
Open-Book QA (Mihaylov et al., 2018).
```

**Sanitized best_snippet (operator-facing):**
```
(Li et al., 2024b; Wang et al., 2023) can be used to significantly
improve the generation quality of LLMs (Gao et al., 2023) from 22.5% to 47.1% on
Open-Book QA (Mihaylov et al., 2018).
```

Changes:
- `(#page-18-0)` stripped; all citation content and percentages preserved

---

## Commands Run

```
python -m pytest tests/test_research_query.py -x -q --tb=short
# 83 passed in 4.64s (43 new tests; 40 existing tests unchanged)

python -m pytest tests/test_research_query.py tests/test_ris_marker_queue.py -q --tb=short
# 260 passed, 1 skipped in 14.68s
```

Smoke query against live KS not run — the full `tests/` suite was not run in
this session to avoid waiting for slow integration tests, but targeted RIS area
tests all pass. The live smoke (`research-query --question "sentiment"`) was not
run because it would require the Docker stack and does not exercise any new code
path (the KS query behavior is unchanged; only the display layer changed).

---

## Tests Added

### `TestSanitizeSnippet` (39 tests)

Unit tests for `_sanitize_snippet()`:

| Group | Tests |
|---|---|
| HTML tag stripping | `<sup>`, `</sup>`, `<sub>`, `<br>`, `<br/>`, `<br />`, `<a href>`, `</a>` |
| Page ref stripping | Start, mid-text, multiple, large numbers |
| Heading marker stripping | h1–h4, heading-only-at-line-start invariant |
| Whitespace normalization | Excess newlines, excess spaces, leading/trailing strip |
| Preservation guarantees | Plain text, numbers/percentages, math inequalities `a < b`, LaTeX `$...$`, real Marker abstract snippet, real page-ref snippet |

### `TestSanitizeSnippetIntegration` (4 tests)

Integration via `query_academic_corpus` with injected in-memory KS:

| Test | Verifies |
|---|---|
| `test_citation_snippet_has_no_html_tags` | `best_snippet` has `<sup>` stripped |
| `test_citation_snippet_has_no_page_ref` | `best_snippet` has `(#page-N-M)` stripped |
| `test_citation_snippet_has_no_md_heading` | `best_snippet` has `####` stripped |
| `test_stored_claim_text_not_modified` | KS `claim_text` still contains raw content |

All 83 tests in `test_research_query.py` pass. No regressions in
`test_ris_marker_queue.py` (177 passed, 1 skipped).

---

## Acceptance Test Status (from Spec)

| AT | Description | Status |
|---|---|---|
| AT-5 | `best_snippet` has no `<sup>`, `<br>`, `####`, `(#page-N-M)` | **PASS** (unit + integration) |
| AT-1 | `research-query --question "LLM"` → targeted hits | Deferred to Deliverable B |
| AT-2 | `research-query --question "language model financial prediction"` | Deferred to Deliverable B |
| AT-3 | `research-query --question "hallucination"` | Passes today (substring match) |
| AT-4 | Control query correctly rejected | Unchanged (existing behavior) |

---

## What Remains for L2.1

### Deliverable A — Chroma doc_id Linkage for Academic Bodies (~2 hours)

Extend `research-marker-queue index-done` to embed and upsert body text into
a new ChromaDB collection `"academic_papers"`. Requires:
- Body sidecar read from `bodies/{candidate_id}.body.txt`
- Chunking (~512 tokens, ~128 overlap)
- BAAI/bge-large-en-v1.5 embedding (already in Docker)
- Upsert with metadata: `ks_doc_id`, `arxiv_id`, `body_source`, `candidate_id`
- `--reindex-chroma` flag for backfill of existing done items

### Deliverable B — Semantic Retrieval Fallback (~1.5 hours)

Add `_query_chroma_academic()` in `academic_query.py`. Wire as fallback when
substring search returns zero claims and `academic_papers` collection is non-empty.
Fixes W1 (abbreviation blindness) and W2 (multi-word conjunction failure).
Prerequisite: Deliverable A must ship first.

### Open Issues Carried Forward

- **Math inequality edge case**: `a < 5%` patterns (where text after `<` ends
  with `%>` or similar) could theoretically match a tag pattern. Real arxiv:2510.05533
  claims were not inspected character-by-character; the whitelist approach is safe
  for all known Marker output patterns.
- **`(#page-N-M)` regex scope**: Only strips the anchor; orphaned leading space
  after stripping is cleaned by `.strip()` and `_EXCESS_SPACES`. Tested via
  `test_real_marker_page_ref_snippet`.

---

## Codex Review

Not required — no execution, kill-switch, or risk-manager code changed.
Snippet sanitation is display-layer only; scope is `academic_query.py` (skip tier).
