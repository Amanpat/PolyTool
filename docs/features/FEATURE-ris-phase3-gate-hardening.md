# RIS Phase 3 — Evaluation Gate Hardening

**Plan:** quick-260402-m6t
**Date:** 2026-04-02
**Branch:** feat/ws-clob-feed (worktree-agent-afba9780)
**Status:** Shipped

---

## Overview

Phase 3 adds deterministic structure to the RIS evaluation gate. Before this
change, the gate was: hard_stops -> LLM scoring. After Phase 3 it is:

```
hard_stops -> near_duplicate_check -> feature_extraction -> LLM_scoring -> artifact_persistence
```

The LLM is still the primary quality signal. Phase 3 adds local-first guardrails
and observability on top — without replacing or weakening LLM scoring.

Key additions:
1. Per-family deterministic feature extraction (local regex/text, no network)
2. Content-hash + shingle near-duplicate detection (exact + Jaccard)
3. Structured eval artifact persistence (JSONL per eval run)
4. Enhanced calibration summaries with family-level and hard-stop breakdowns
5. SOURCE_FAMILY_OFFSETS hook for future data-driven family score tuning

---

## Structured Feature Extraction

**Module:** `packages/research/evaluation/feature_extraction.py`
**Entry point:** `extract_features(doc: EvalDocument) -> FamilyFeatures`

All extraction is pure text/regex. No network calls. No LLM dependency.

### Features by Family

| Family | Key Features |
|--------|-------------|
| `academic` | `has_doi`, `has_arxiv_id`, `has_ssrn_id`, `methodology_cues` (count), `has_known_author`, `has_publish_date` |
| `github` | `stars` (from metadata), `forks` (from metadata), `has_readme_mention`, `has_license_mention`, `commit_recency` |
| `blog` | `has_byline`, `has_date`, `heading_count`, `paragraph_count`, `has_blockquote` |
| `news` | same as blog |
| `forum_social` | `has_screenshot`, `has_data_mention`, `reply_count` (from metadata), `specificity_markers` (percent/dollar patterns) |
| `manual` / default | `body_length`, `word_count`, `has_url` |

Source families not explicitly listed fall through to the `manual` extractor.

### FamilyFeatures Dataclass

```python
@dataclass
class FamilyFeatures:
    family: str                    # e.g. "academic", "github"
    features: dict[str, Any]       # feature name -> value (bool, int, None)
    confidence_signals: list[str]  # human-readable positive signals
```

---

## Near-Duplicate Detection

**Module:** `packages/research/evaluation/dedup.py`

Two-pass algorithm (in order):

1. **Exact duplicate:** SHA256 of normalized body (lowercase + whitespace-collapsed).
   Match against `existing_hashes: set[str]`.

2. **Near-duplicate:** 5-gram word shingles + Jaccard similarity.
   Match against `existing_shingles: list[tuple[doc_id, frozenset]]`.
   Default threshold: **0.85**.

```python
@dataclass
class NearDuplicateResult:
    is_duplicate: bool
    duplicate_type: Optional[str]   # "exact" | "near" | None
    matched_doc_id: Optional[str]
    similarity: float
```

Near-duplicates are rejected **before LLM scoring** — they never consume API tokens.

Empty/None body returns `is_duplicate=False` without error.

---

## Scoring Artifact Persistence

**Module:** `packages/research/evaluation/artifacts.py`
**File:** `{artifacts_dir}/eval_artifacts.jsonl` (one JSON line per eval)

```python
@dataclass
class EvalArtifact:
    doc_id: str
    timestamp: str              # ISO-8601 UTC
    gate: str                   # ACCEPT | REVIEW | REJECT
    hard_stop_result: Optional[dict]
    near_duplicate_result: Optional[dict]
    family_features: dict
    scores: Optional[dict]
    source_family: str
    source_type: str
```

Persistence is opt-in: `DocumentEvaluator(artifacts_dir=Path(...))`.
Without `artifacts_dir`, behavior is identical to Phase 2 (backward compatible).

CLI flag: `python -m polytool research-eval --artifacts-dir /path/to/dir --json`
When `--json` and `--artifacts-dir` are both set, the output includes `features`
and `near_duplicate` fields alongside existing gate/scores fields.

---

## Enhanced Calibration Analytics

**Module:** `packages/research/synthesis/calibration.py`

New function: `compute_eval_artifact_summary(artifacts: list[dict]) -> dict`

Output fields:

| Field | Description |
|-------|-------------|
| `total_evals` | Total artifact count |
| `gate_distribution` | ACCEPT/REVIEW/REJECT counts |
| `hard_stop_distribution` | Count per stop_type (empty_body, too_short, etc.) |
| `family_gate_distribution` | Per-family ACCEPT/REVIEW/REJECT counts |
| `dedup_stats` | exact_duplicates, near_duplicates, unique counts |
| `avg_features_by_family` | Per-family numeric feature averages |

Updated function: `format_calibration_report(summary, drift=None, eval_artifacts_summary=None)`

When `eval_artifacts_summary` is provided, the report gains two new sections:
- **Hard-Stop Causes** — ranked table of stop_type counts
- **Family Gate Distribution** — per-family accept/reject breakdown with ACCEPT %

---

## Family-Specific Offset Hook

**Location:** `packages/research/evaluation/types.py`

```python
# SOURCE_FAMILY_OFFSETS is the designated extension point for data-driven
# per-family score adjustments. It is intentionally empty until calibration
# artifacts accumulate enough signal to justify non-zero offsets.
SOURCE_FAMILY_OFFSETS: dict[str, dict[str, int]] = {}
```

This is the **future config hook** for applying per-family credibility adjustments
before returning a gate decision. It is deliberately empty in Phase 3.

**When to populate:** After `eval_artifacts.jsonl` accumulates >= 50 entries across
>= 3 source families, run a calibration analysis to derive initial offsets. Until
then, the LLM rubric and SOURCE_FAMILY_GUIDANCE strings carry all family-specific
signal.

---

## What Is Deferred

The following are explicitly deferred from Phase 3:

- **ML-based scoring models:** No training, no weights. Feature extraction feeds
  future ML work but is not wired to any model yet.
- **Config-driven family weighting from data:** SOURCE_FAMILY_OFFSETS exists as a
  hook but is empty. Offset derivation requires >= 50 labeled artifacts.
- **Dashboard visualization:** No Grafana dashboards for artifact analytics.
  The JSONL artifact file is queryable with DuckDB when needed.
- **Shingle parameter tuning:** The 5-gram shingle size and 0.85 Jaccard threshold
  are defaults, not calibrated. They should be revisited once false-positive/negative
  data is available from production artifact logs.
