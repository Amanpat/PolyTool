# Dev Log — RIS Phase 2: Calibration Hardening and Corpus Metadata Hygiene

**Date:** 2026-04-02
**Plan:** quick-260402-ivi
**Branch:** feat/ws-clob-feed (worktree: agent-a82e9400)

---

## Objective

Two improvements in one plan:

1. Fix inaccurate `source_type` classifications in `config/seed_manifest.json` (all 11 entries
   were originally classified as `source_type: "book"`, which was wrong for internal reference
   docs and roadmaps). Extend `SeedEntry` with optional `evidence_tier` and `notes` fields.

2. Add `research-calibration` CLI surface and `packages/research/synthesis/calibration.py`
   module for inspecting precheck ledger health over time windows, with aggregate metrics and
   per-domain drift reporting.

---

## Files Changed

| File | Rationale |
|------|-----------|
| `config/seed_manifest.json` | Bumped to v2; reclassified 11 entries with accurate `source_type`, `evidence_tier`, and `notes`. |
| `packages/research/ingestion/seed.py` | Extended `SeedEntry` dataclass with optional `evidence_tier` and `notes` fields; updated `load_seed_manifest()` to parse them. |
| `packages/research/evaluation/types.py` | Added `"reference_doc"` and `"roadmap"` to `SOURCE_FAMILIES`; added `"book_foundational"` to `SOURCE_FAMILY_GUIDANCE` to satisfy invariant (deviation fix). |
| `packages/research/synthesis/calibration.py` | New module: `CalibrationSummary`, `FamilyDriftReport`, `compute_calibration_summary()`, `compute_family_drift()`, `format_calibration_report()`. |
| `tools/cli/research_calibration.py` | New CLI entrypoint for `research-calibration summary` subcommand with `--window`, `--ledger`, `--manifest`, `--json` flags. |
| `polytool/__main__.py` | Registered `research_calibration_main` and added `research-calibration` to command handler dict and help text. |
| `tests/test_ris_calibration.py` | 31 tests covering calibration module, CLI, manifest hygiene, and backward compatibility. |
| `docs/features/FEATURE-ris-calibration-and-metadata.md` | Feature documentation for both improvements. |

---

## Seed Metadata Corrections

### Before / After for All 11 Entries

| Path | Old `source_type` | New `source_type` | `evidence_tier` Added |
|------|-------------------|--------------------|-----------------------|
| `docs/reference/RAGfiles/RIS_OVERVIEW.md` | `book` | `reference_doc` | `tier_1_internal` |
| `docs/reference/RAGfiles/RIS_01_INGESTION_ACADEMIC.md` | `book` | `reference_doc` | `tier_1_internal` |
| `docs/reference/RAGfiles/RIS_02_INGESTION_SOCIAL.md` | `book` | `reference_doc` | `tier_1_internal` |
| `docs/reference/RAGfiles/RIS_03_EVALUATION_GATE.md` | `book` | `reference_doc` | `tier_1_internal` |
| `docs/reference/RAGfiles/RIS_04_KNOWLEDGE_STORE.md` | `book` | `reference_doc` | `tier_1_internal` |
| `docs/reference/RAGfiles/RIS_05_SYNTHESIS_ENGINE.md` | `book` | `reference_doc` | `tier_1_internal` |
| `docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md` | `book` | `reference_doc` | `tier_1_internal` |
| `docs/reference/RAGfiles/RIS_07_INTEGRATION.md` | `book` | `reference_doc` | `tier_1_internal` |
| `docs/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md` | `book` | `roadmap` | `tier_2_superseded` |
| `docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md` | `book` | `roadmap` | `tier_1_internal` |
| `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md` | `book` | `roadmap` | `tier_1_internal` |

All entries retain `source_family: "book_foundational"` — this is correct because these are
timeless foundational documents with `null` half-life in `config/freshness_decay.json`.

---

## Calibration Metrics Exposed

`compute_calibration_summary(events)` computes the following over a time window:

| Metric | Definition |
|--------|------------|
| `total_prechecks` | Count of `precheck_run` events in the window |
| `recommendation_distribution` | `{GO: N, CAUTION: N, STOP: N}` counts from `precheck_run.recommendation` |
| `override_count` | Count of `override` events in the window |
| `override_rate` | `override_count / total_prechecks`; 0.0 if no prechecks |
| `outcome_count` | Count of `outcome` events in the window |
| `outcome_distribution` | `{successful: N, failed: N, partial: N, not_tried: N}` counts from `outcome.outcome_label` |
| `stale_warning_count` | Count of `precheck_run` events with `stale_warning=True` |
| `avg_evidence_count` | Mean of `len(supporting_evidence) + len(contradicting_evidence)` per precheck |

`compute_family_drift(events)` adds per-domain analysis:

| Metric | Definition |
|--------|------------|
| `family_counts` | Per-domain `{recommendation: count}` dict, domain assigned via keyword heuristic on `idea` text |
| `overrepresented_in_stop` | Domains where `STOP count / domain_total > 0.5` |
| `total_prechecks` | Total precheck_run events analyzed |

---

## Commands Run and Output

### Targeted test run (post-RED, pre-GREEN)

All 31 tests in RED phase confirmed failing (as expected — module not yet created).

### Targeted test run (post-GREEN)

```
rtk python -m pytest tests/test_ris_calibration.py -v --tb=short
```

Result: **31 passed, 0 failed**

### Smoke test — CLI

```
python -m polytool research-calibration summary --window all --json
```

Output (empty ledger, as expected):
```json
{
  "window_start": "all",
  "window_end": "all",
  "total_prechecks": 0,
  "recommendation_distribution": {},
  "override_count": 0,
  "override_rate": 0.0,
  "outcome_distribution": {},
  "outcome_count": 0,
  "stale_warning_count": 0,
  "avg_evidence_count": 0.0,
  "family_drift": {
    "family_counts": {},
    "overrepresented_in_stop": [],
    "total_prechecks": 0
  }
}
```

### Full regression

```
rtk python -m pytest tests/ -x -q --tb=short
```

Result: **3039 passed, 4 failed** (pre-existing failures; no regressions introduced)

Pre-existing failures (all artifact-dependent, not caused by this work):
- `test_coverage_report.py::test_pending_no_sells_realized_is_zero` — requires local dossier artifact
- `test_llm_research_packets.py` (3 tests) — require local `@DrPufferfish` dossier files

---

## Deviation: book_foundational guidance (Rule 2)

Adding `"reference_doc"` and `"roadmap"` to `SOURCE_FAMILIES` caused `book_foundational` to
appear as a mapped value without a corresponding entry in `SOURCE_FAMILY_GUIDANCE`. The existing
test `test_all_families_have_guidance` checks this invariant. Fixed by adding the
`book_foundational` guidance entry to `types.py`. Committed as separate fix commit `0a234d7`.

---

## Codex Review

Tier: Skip (docs, config, tests, CLI formatting — no mandatory files changed).
No Codex review required per policy.

---

## Open Questions for Phase 3

1. **Semantic source-family attribution**: Precheck ledger events currently don't carry
   `source_family`. The keyword heuristic in `compute_family_drift()` is best-effort.
   Phase 3 should add `source_family` to `precheck_run` events for precise attribution.

2. **ML-based evidence weighting**: Current `avg_evidence_count` treats all evidence equally.
   Future versions should weight by relevance score or embedding similarity.

3. **Automated threshold tuning**: The GO/CAUTION/STOP thresholds are static.
   A feedback loop from `outcome` events back to threshold adjustment would improve calibration.

4. **Dashboard visualization**: Grafana panel for calibration metrics (override_rate, stale_warning_count,
   recommendation distribution over time) would give ongoing operational visibility.

5. **Ledger pruning policy**: As the ledger grows, there's no purge/archive mechanism.
   Phase 3 should define retention policy (rolling window vs. full history).
