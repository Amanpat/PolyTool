# Feature: RIS Calibration Analytics and Corpus Metadata Hygiene

**Phase:** RIS Phase 2
**Status:** Shipped (2026-04-02)
**Plan:** quick-260402-ivi

---

## Overview

Two improvements shipped in this plan:

1. **Seed manifest v2** — reclassified all 11 corpus entries with accurate `source_type`,
   `evidence_tier`, and `notes` fields. The original manifest incorrectly classified all
   internal reference docs as `source_type: "book"`.

2. **Calibration analytics** — new `research-calibration` CLI surface and
   `packages/research/synthesis/calibration.py` module for inspecting precheck ledger
   health over time windows.

---

## Seed Manifest v2 Schema

### New Optional Fields

```json
{
  "path": "docs/reference/RAGfiles/RIS_OVERVIEW.md",
  "title": "RIS Overview",
  "source_type": "reference_doc",
  "source_family": "book_foundational",
  "author": "PolyTool Team",
  "publish_date": "2026-03-01T00:00:00+00:00",
  "tags": ["ris", "architecture", "overview"],
  "evidence_tier": "tier_1_internal",
  "notes": "Internal architecture reference doc for the Research Intelligence System."
}
```

| Field           | Type            | Description                                              |
|-----------------|-----------------|----------------------------------------------------------|
| `evidence_tier` | `str \| null`   | Provenance tier. Values: `tier_1_internal`, `tier_2_superseded`. Null if not set. |
| `notes`         | `str \| null`   | Human-readable notes about reclassification rationale or usage guidance. Null if not set. |

Both fields are optional. v1 manifests without these fields parse without error
(`.get()` with `None` defaults in `load_seed_manifest()`).

### Source-Family Reclassification Rationale

The original v1 manifest classified all 11 entries as `source_type: "book"`, which was
inaccurate. The v2 reclassification:

| Entry type          | Old `source_type` | New `source_type` | `source_family` (unchanged) | `evidence_tier`    |
|---------------------|-------------------|--------------------|------------------------------|--------------------|
| RIS RAGfiles (×8)   | `book`            | `reference_doc`    | `book_foundational`          | `tier_1_internal`  |
| Superseded roadmap  | `book`            | `roadmap`          | `book_foundational`          | `tier_2_superseded`|
| Active roadmaps (×2)| `book`            | `roadmap`          | `book_foundational`          | `tier_1_internal`  |

`source_family: "book_foundational"` is retained for all entries — these are timeless
foundational docs with null half-life in `freshness_decay.json`.

### SOURCE_FAMILIES Update

`packages/research/evaluation/types.py` now maps the new source types:

```python
SOURCE_FAMILIES = {
    ...
    "reference_doc": "book_foundational",
    "roadmap": "book_foundational",
}
```

`SOURCE_FAMILY_GUIDANCE` also now includes a `book_foundational` guidance entry
to satisfy the invariant that all `SOURCE_FAMILIES` values have corresponding guidance.

---

## Calibration Summary

### What It Measures

`compute_calibration_summary(events)` computes:

| Metric                        | Description                                                         |
|-------------------------------|---------------------------------------------------------------------|
| `total_prechecks`             | Count of `precheck_run` events in the window                       |
| `recommendation_distribution` | `{GO: N, CAUTION: N, STOP: N}` counts                             |
| `override_count`              | Count of `override` events                                         |
| `override_rate`               | `override_count / total_prechecks` (0.0 if no prechecks)          |
| `outcome_distribution`        | `{successful: N, failed: N, partial: N, not_tried: N}` counts     |
| `outcome_count`               | Count of `outcome` events                                          |
| `stale_warning_count`         | Count of prechecks with `stale_warning=True`                       |
| `avg_evidence_count`          | Mean of `len(supporting) + len(contradicting)` per precheck        |

### How to Interpret

- **High override_rate (>30%)**: Precheck recommendations diverge from operator judgment.
  Either the knowledge base is missing key context, or the synthesis engine thresholds
  need tuning.
- **High stale_warning_count**: Many prechecks were completed with stale evidence.
  Indicates the corpus needs refresh cycles.
- **STOP-heavy recommendation_distribution**: Normal for a conservative posture.
  Cross-reference with outcome_distribution to see if STOP recommendations were warranted.
- **Low avg_evidence_count**: Prechecks are being run with sparse evidence.
  Improve corpus coverage for the relevant domains.

---

## Family Drift Reporting

### What It Detects

`compute_family_drift(events)` uses keyword-based heuristics on the `idea` field
to assign domain labels and compute per-domain recommendation breakdowns.

```python
# Domain keyword mapping (first match wins):
market_maker  ← "market maker", "quoting", "avellaneda"
crypto        ← "crypto", "bitcoin", "btc", "eth", "solana"
sports        ← "sports", "football", "nba", "nfl"
ris           ← "ris", "precheck", "knowledge store"
polymarket    ← "polymarket", "clob", "prediction market"
wallet        ← "wallet", "dossier", "alpha"
news          ← "news", "election", "geopolitical"
general       ← (fallback)
```

### What "Overrepresented in STOP" Means

A domain is flagged when its `STOP count > 50%` of all prechecks in that domain.
This signals that the knowledge base may be biased against a particular research area —
either because the corpus lacks supporting evidence, or because the threshold calibration
is too conservative for that domain.

**Operator action**: Review the overrepresented domain's precheck history with
`research-precheck --history` to determine whether the STOP recommendations were
warranted.

---

## CLI Usage

### Basic Usage

```bash
# 30-day window (default) — human-readable report
python -m polytool research-calibration summary

# Custom window
python -m polytool research-calibration summary --window 7d
python -m polytool research-calibration summary --window all

# Machine-readable JSON
python -m polytool research-calibration summary --window all --json

# Custom ledger path
python -m polytool research-calibration summary --ledger /path/to/ledger.jsonl

# With seed manifest for domain attribution
python -m polytool research-calibration summary --manifest config/seed_manifest.json --json
```

### Window Formats

| Format   | Meaning                     |
|----------|-----------------------------|
| `all`    | No time filter (all events) |
| `7d`     | Last 7 days                 |
| `30d`    | Last 30 days (default)      |
| `90d`    | Last 90 days                |
| `24h`    | Last 24 hours               |

### Example JSON Output

```json
{
  "window_start": "all",
  "window_end": "all",
  "total_prechecks": 12,
  "recommendation_distribution": {"GO": 7, "CAUTION": 3, "STOP": 2},
  "override_count": 1,
  "override_rate": 0.083,
  "outcome_distribution": {"successful": 3, "not_tried": 4},
  "outcome_count": 7,
  "stale_warning_count": 2,
  "avg_evidence_count": 3.5,
  "family_drift": {
    "family_counts": {
      "market_maker": {"GO": 4, "CAUTION": 2},
      "crypto": {"STOP": 2, "GO": 1}
    },
    "overrepresented_in_stop": ["crypto"],
    "total_prechecks": 12
  }
}
```

---

## Intentionally Deferred

The following improvements are out of scope for this plan:

- **ML-based evidence weighting**: Using embeddings to weight supporting vs contradicting
  evidence quality, not just count.
- **Semantic source-family assignment**: Adding `source_family` directly to `precheck_run`
  events for precise (non-heuristic) family drift attribution.
- **Automated threshold tuning**: Adjusting GO/CAUTION/STOP thresholds based on outcome
  feedback loops.
- **Dashboard visualization**: Grafana panel for calibration metrics over time.
- **Export to CSV**: Bulk export of calibration data for external analysis.
