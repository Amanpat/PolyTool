# Dev Log: RIS SimTrader Bridge v1 (RIS_07 Section 3 practical implementation)

**Date:** 2026-04-03
**Plan:** quick-260403-jyg
**Commit:** edccc70

---

## Objective

Close the gap between RIS research outputs and the hypothesis registry /
SimTrader validation workflow. ResearchBrief and EnhancedPrecheck objects were
dead-end dataclasses before this -- rich evidence, but no path forward.

Goal: smallest real, honest bridge. No fake auto-loop. No LLM calls.

---

## Files Changed

| File | Change |
|------|--------|
| `packages/polymarket/rag/knowledge_store.py` | Added `update_claim_validation_status()` method + `VALID_VALIDATION_STATUSES` constant |
| `packages/research/integration/__init__.py` | New module -- public re-exports for the bridge |
| `packages/research/integration/hypothesis_bridge.py` | New -- `brief_to_candidate()`, `precheck_to_candidate()`, `register_research_hypothesis()` |
| `packages/research/integration/validation_feedback.py` | New -- `record_validation_outcome()` with outcome->status mapping |
| `tests/test_ris_simtrader_bridge.py` | New -- 37 offline deterministic tests |

---

## Design Decisions

### 1. Why not reuse `stable_hypothesis_id()` from registry.py?

`stable_hypothesis_id()` expects dimension_key / segment_key / candidate_id
structures from the alpha_distill pipeline. Research candidates have a `name`
field (topic slug) as their identity anchor. Reusing that function would require
papering over a mismatch. Instead, the bridge computes:

```python
sha256({"kind": "research_candidate", "name": candidate["name"]})[:16]
```

This produces a stable `hyp_<hex>` ID scoped to the research origin without
coupling to the alpha_distill data shape.

### 2. Validation statuses align with RIS_07 Section 3 language

- `CONSISTENT_WITH_RESULTS` = "KEEP" signal from Gate 2 (evidence supported)
- `CONTRADICTED` = "AUTO_DISABLE candidate" signal (evidence refuted)
- `INCONCLUSIVE` = safe middle ground (mixed or insufficient replay data)
- `UNTESTED` = default for never-validated claims (unchanged from schema default)

### 3. record_validation_outcome is operator-triggered, not automatic

The function does not watch run_manifest.json, does not poll SimTrader output,
does not fire on Gate 2 events. The operator (or a future orchestrator at R5/v2)
calls it after reviewing replay results. This is honest about what v1 ships.

### 4. evidence_doc_ids flow through the full chain

brief -> candidate["evidence_doc_ids"] -> registry event["source"]["evidence_doc_ids"]

This preserves the research provenance chain so future queries can trace a
hypothesis back to specific source documents in the KnowledgeStore.

---

## Commands Run + Results

### Bridge tests (RED -> GREEN TDD cycle)

```
python -m pytest tests/test_ris_simtrader_bridge.py -x --tb=short -q
# RED: ERRORS collecting test (ModuleNotFoundError: No module named 'packages.research.integration')
```

After implementation:

```
python -m pytest tests/test_ris_simtrader_bridge.py -v --tb=short
# 37 passed in 0.44s
```

### Import smoke test

```
python -c "from packages.research.integration import brief_to_candidate, precheck_to_candidate, register_research_hypothesis, record_validation_outcome; print('bridge imports OK')"
# bridge imports OK
```

### CLI smoke test

```
python -m polytool --help
# No import errors; full command list displayed
```

### Full regression suite

```
python -m pytest tests/ -q --tb=line
# 6 failed, 3644 passed, 3 deselected, 25 warnings
```

The 6 failures are in `tests/test_ris_dossier_extractor.py`. These are caused
by a parallel agent (plan 260403-jy8) that modified `packages/research/integration/__init__.py`
on disk to import a `dossier_extractor` module that has not been created yet.
These failures are NOT caused by the SimTrader bridge work -- my 37 tests pass
in isolation and the import smoke test passes. Per CLAUDE.md multi-agent
awareness rules, I am not reverting the parallel agent's changes.

---

## What is truly shipped now (v1 practical bridge)

- `KnowledgeStore.update_claim_validation_status()` -- SQLite row update with validation
- `brief_to_candidate()` -- deterministic conversion of ResearchBrief to candidate dict
- `precheck_to_candidate()` -- deterministic conversion of EnhancedPrecheck to candidate dict
- `register_research_hypothesis()` -- JSONL append with research_bridge provenance
- `record_validation_outcome()` -- maps confirmed/contradicted/inconclusive to SQLite status updates
- 37 offline tests exercising all functions end-to-end

---

## What remains deferred (R5 / v2 autonomous orchestration)

These items are explicitly NOT in v1:

1. **Auto-test orchestration loop** -- no automated "register -> run SimTrader -> record feedback" cycle. Operator/future orchestrator must call functions manually.
2. **Auto-hypothesis promotion** -- no automatic status change from "proposed" to "testing" on Gate 2 pass.
3. **Discord approval integration** -- no approval-flow hooks in the feedback loop.
4. **Scheduled re-validation** -- no cron job re-evaluating claim statuses against new tape data.
5. **LLM-enhanced hypothesis generation** -- DeepSeek V3 synthesis is a v2 feature (deferred per PLAN_OF_RECORD no-external-LLM policy).
6. **Dossier pipeline** -- `extract_dossier_findings()`, `batch_extract_dossiers()`, `ingest_dossier_findings()` are a separate plan (260403-jy8).

---

## Codex Review

Tier: Skip (no execution layer, no order placement, no risk logic).
Files changed are synthesis bridge utilities and SQLite update -- no mandatory review required per CLAUDE.md Codex Review Policy.
