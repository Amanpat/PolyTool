---
title: Fix Research Query Natural Language Normalization
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-09_fix-research-query-natural-language-normalization.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Fix: research-query natural-language question normalization

**Date:** 2026-05-09  
**Scope:** packages/research/synthesis/academic_query.py, tests/test_research_query.py

---

## Root cause

`query_knowledge_store_for_rrf` performs verbatim case-insensitive **substring** matching:

```python
query_lower in c.get("claim_text", "").lower()
```

A claim like *"Prediction markets aggregate information efficiently."* contains the substring
`"prediction markets"` but not `"what are prediction markets"`. So:

- `research-query --question "prediction markets"` → hit → citation returned.
- `research-query --question "what are prediction markets"` → no hit → fallback warning.

The retrieval layer has no semantic understanding — it never sees embeddings at this path
(the ChromaDB vector path is deferred to L2.1). The mismatch was purely syntactic.

---

## Fix: query normalization in `_build_sub_queries`

Added two new pieces to `academic_query.py`:

### `_QUESTION_PREAMBLES` (module-level constant)

A tuple of common leading question phrases to strip:

```python
("what is ", "what are ", "how does ", "how do ", "why is ", "explain ", "define ", ...)
```

Covers 18 patterns. Case-insensitive prefix match. First match wins.

### `_normalize_question(question: str) -> str`

Strips the first matching preamble and trims trailing `?.,!`. Returns the original
string unchanged when no preamble matches or the result would be empty.

```python
_normalize_question("what are prediction markets")  # → "prediction markets"
_normalize_question("explain sports betting markets")  # → "sports betting markets"
_normalize_question("prediction markets")  # → "prediction markets" (unchanged)
_normalize_question("what is")  # → "what is" (empty core — no change)
```

### `_build_sub_queries` injection

The normalized core phrase is inserted as a `"normalized"` angle **between** the primary
query and any `plan_queries` angles, so it gets high retrieval priority:

```
primary:    "what are prediction markets"
normalized: "prediction markets"
angle_0:    "evidence for what are prediction markets"
...
```

Deduplication via `seen` set prevents any angle from appearing twice. When the question
has no preamble, `core == question` and no extra angle is added.

---

## Files changed

| File | Change |
|---|---|
| `packages/research/synthesis/academic_query.py` | Added `_QUESTION_PREAMBLES`, `_normalize_question()`, updated `_build_sub_queries()` |
| `tests/test_research_query.py` | 19 new tests across two new test classes |

---

## Tests run + results

```
tests/test_research_query.py        54 passed  (was 35 before this fix)
tests/test_ris_marker_queue.py     ~170 passed, 1 skipped
tests/test_ris_claim_extraction.py  ~33 passed
```

Total: **54 passed, 0 failed** in test_research_query.py.

New test classes added:
- `TestAcademicQueryHelpers` — 9 new tests for `_normalize_question` and `_build_sub_queries` behavior
- `TestNaturalLanguageRetrieval` — 7 end-to-end tests with in-memory KS

---

## Before/after behavior

**Before:**
```
research-query --question "prediction markets"       → citation (had_fallback=false)
research-query --question "what are prediction markets" → no citation (had_fallback=true, no-match warning)
```

**After:**
```
research-query --question "prediction markets"          → citation (had_fallback=false)
research-query --question "what are prediction markets" → citation (had_fallback=false)
research-query --question "explain prediction markets"  → citation (had_fallback=false)
research-query --question "quantum chromodynamics xyz"  → no citation (had_fallback=true, no-match warning)
```

The `question` field in JSON output always contains the **original** question. The
normalized form only appears in `query_angles`.

---

## Remaining retrieval limitations

1. **No stemming or lemmatization.** "predicting markets" would not hit "prediction markets."
   Requires FTS5 or semantic retrieval to close.
2. **Substring only.** Synonyms ("futures", "betting exchange") will not match "prediction
   markets" claims without synonym expansion.
3. **ChromaDB vector path deferred (L2.1).** Vector search would handle all of the above
   cases naturally. The normalization fix is a conservative stopgap that avoids any new
   dependency.
4. **plan_queries angles use the original question.** Angle templates like "evidence for
   what are prediction markets" inherit the original phrasing. A future improvement could
   also normalize the topic passed to plan_queries.

---

## Codex review

Skip — docs + test file only significant changes; academic_query.py change is pure
retrieval plumbing with no execution path, no ClickHouse writes, no live trading code.
