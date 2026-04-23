---
date: 2026-04-22
work_packet: WP1-C
phase: RIS Phase 2A
slug: ris_wp1c_provider_events_contract
---

# WP1-C: provider_events contract reconciliation

## Objective

Reconcile the split `provider_event` (singular dict) vs `provider_events` (plural list) contract across the RIS evaluation artifact system so that:

- All new writes emit `provider_events: [...]` (list)
- Legacy artifacts with `provider_event: {...}` (singular) still read correctly
- Replay, CLI, and metrics behavior stays valid

## Root cause

`metrics.py` was already written expecting a plural `provider_events` list (forward-looking), while all evaluator write paths and most read paths used `provider_event` (singular dict). Old artifacts on disk use the singular key. This meant metrics silently returned zero failure counts for all existing artifacts.

## Files changed

| File | Change |
|---|---|
| `packages/research/evaluation/artifacts.py` | `EvalArtifact.provider_event` renamed to `provider_events: Optional[List[dict]]`; `normalize_provider_events()` helper added |
| `packages/research/evaluation/evaluator.py` | Three write sites updated to emit `provider_events=[...]` (list); hard-stop, dedup, and scoring paths all updated |
| `packages/research/evaluation/replay.py` | `replay_eval()` and `compare_eval_events()` both use `normalize_provider_events()` for reads |
| `tools/cli/research_eval.py` | `_cmd_eval()` outputs `provider_events` key (plural); dead `provider_event` read in `_cmd_replay()` removed |
| `packages/research/metrics.py` | Uses `normalize_provider_events()` instead of bare `.get("provider_events")` |
| `tests/test_ris_phase5_provider_enablement.py` | 20 existing tests updated to plural contract; 5 new backward-compat tests added |

## normalize_provider_events contract

```python
def normalize_provider_events(artifact: dict) -> List[dict]:
    # New format: provider_events is a list
    events = artifact.get("provider_events")
    if events is not None and isinstance(events, list):
        return events
    # Legacy format: provider_event is a singular dict — wrap in list
    singular = artifact.get("provider_event")
    if singular and isinstance(singular, dict):
        return [singular]
    return []
```

This ensures all read paths handle both old and new artifacts transparently.

## Test results

```
tests/test_ris_phase5_provider_enablement.py  25 passed (0.25s)
Full suite (excluding pre-existing WP2 failures): 2332 passed, 1 failed, 3 deselected
```

The 1 full-suite failure (`test_each_claim_has_required_fields`) is pre-existing from commit `2d926c6` (heuristic extractor v2 bump changed actor name). Not caused by WP1-C.

The 8 failures in `test_ris_phase2_cloud_provider_routing.py` are also pre-existing WP2 work not yet implemented.

## New backward-compat tests

- `test_normalize_provider_events_new_artifact` — new-format list returned as-is
- `test_normalize_provider_events_legacy_artifact` — singular dict wrapped in list
- `test_normalize_provider_events_empty` — empty dict / None returns `[]`
- `test_replay_eval_returns_list_for_new_artifact` — `replay_eval()` second element is a list
- `test_compare_eval_events_reads_legacy_provider_event` — `compare_eval_events()` extracts metadata from legacy singular-dict artifacts

## Codex review

Tier: Skip (evaluation plumbing, no execution path). No review required per CLAUDE.md policy.

## Open questions / next steps

- WP1-A: scoring weights and per-dimension floor fixes still pending
- WP1-D: R0 seed (11+ docs) and WP1-E: 5 open-source docs seeded still pending
- WP2 (cloud provider routing) will need to update `test_ris_phase2_cloud_provider_routing.py` line 254 from `provider_event` to `provider_events[0]` when that work lands
