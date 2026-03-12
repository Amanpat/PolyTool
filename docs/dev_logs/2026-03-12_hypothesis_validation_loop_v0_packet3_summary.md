# Dev Log: Hypothesis Validation Loop v0 - Packet 3

**Date:** 2026-03-12
**Branch:** phase-1
**Track:** Track B - Research Loop

---

## Summary

Implemented Packet 3 of the Track B Hypothesis Validation Loop milestone.

This packet adds a deterministic `hypothesis-summary` review surface for saved
`hypothesis.json` artifacts. The new command emits a compact JSON-first payload
with ordered summary bullets plus a structured `primary_hypothesis` block so an
operator or downstream automation can quickly read the key claim, confidence,
core evidence, limitations, and next step without reparsing the full artifact.

Packet 1 validation behavior, Packet 2 diff behavior, `llm-save` persistence,
Track A / Gate 2 work, strategy-codify work, n8n work, and FastAPI wrapper work
were left unchanged.

---

## What Was Built

### `packages/polymarket/hypotheses/summary.py` (new)

Added a dedicated summary extraction module for saved hypothesis artifacts.

Core behavior:
- `load_hypothesis_summary_artifact(path)` loads a saved JSON artifact and rejects non-object roots.
- `extract_hypothesis_summary(document, *, hypothesis_path=...)` returns a deterministic JSON summary payload.
- Output is structured around:
  - `metadata` (user_slug, run_id, model, created_at_utc, optional dossier/wallet/window metadata)
  - `overall_assessment`
  - `primary_hypothesis` (stable key, claim, confidence, next feature, execution recommendation, primary evidence)
  - `summary_bullets[]` with stable bullet keys and source-field paths
  - `summary` counts (`bullet_count`, `hypothesis_count`, `observation_count`, `primary_hypothesis_key`, `available_sections`, `structured_fields_used`)

Determinism rules:
- primary hypothesis is selected by a stable key order (`H1`, `H2`, ... then other ids, then claims, then anonymous entries)
- duplicate hypothesis ids or claims receive deterministic suffixes (`#1`, `#2`, ...)
- trade UID order is normalized in the machine-readable `primary_evidence` block
- bullet order is fixed: identity -> overall_assessment -> executive_summary -> core_edge_claim -> confidence -> primary_evidence -> risks_limitations -> next_step
- missing content is omitted rather than invented

### `tools/cli/hypotheses.py` (modified)

Added `hypothesis-summary` to the existing hypothesis CLI surface.

- New command:
  - `python -m polytool hypothesis-summary --hypothesis-path PATH`
- Behavior:
  - reads one saved `hypothesis.json`
  - prints a structured JSON summary to stdout
  - exits 0 on success, 1 on missing file / invalid JSON / invalid root type

### `polytool/__main__.py` (modified)

Registered `hypothesis-summary` in the top-level module dispatcher and help output.

- Added to `_COMMAND_HANDLER_NAMES`
- Added to `_FULL_ARGV_COMMANDS`
- Listed under the Track B Research Loop help surface

### Tests

#### `tests/test_hypothesis_summary.py` (new)

Focused module coverage for Packet 3 behavior:
- expected contract for a populated artifact
- deterministic output when hypothesis order changes
- omission of optional bullets when content is absent
- non-object root rejection when loading a saved artifact

#### `tests/test_hypotheses_cli.py` (modified)

Extended CLI coverage for the new command:
- top-level help now asserts `hypothesis-summary` is listed
- CLI summary smoke verifies payload shape and bullet ordering
- missing-file and invalid-JSON error paths exit 1

#### `tests/test_polytool_main_module_smoke.py` (modified)

Extended subprocess help coverage:
- top-level `python -m polytool --help` includes `hypothesis-summary`
- `python -m polytool hypothesis-summary --help` prints the expected arguments

---

## Files Changed

| File | Change |
|------|--------|
| `packages/polymarket/hypotheses/summary.py` | New deterministic hypothesis summary module |
| `tools/cli/hypotheses.py` | Added `hypothesis-summary` handler and subparser |
| `polytool/__main__.py` | Registered `hypothesis-summary` and updated help text |
| `tests/test_hypothesis_summary.py` | New focused unit tests for Packet 3 |
| `tests/test_hypotheses_cli.py` | Added CLI coverage for `hypothesis-summary` |
| `tests/test_polytool_main_module_smoke.py` | Added help-surface smoke coverage for `hypothesis-summary` |
| `docs/dev_logs/2026-03-12_hypothesis_validation_loop_v0_packet3_summary.md` | Packet 3 implementation log |

---

## Commands Run

```bash
pytest -q tests/test_hypothesis_summary.py tests/test_hypotheses_cli.py tests/test_polytool_main_module_smoke.py
python -m polytool hypothesis-summary --help
python -m polytool hypothesis-summary --hypothesis-path kb/users/testuser/llm_reports/2026-03-11/claude-sonnet-4-6_smoke001/hypothesis.json
```

---

## Summary Artifact Contract

`python -m polytool hypothesis-summary --hypothesis-path PATH` returns:

```json
{
  "schema_version": "hypothesis_summary_v0",
  "source": {
    "hypothesis_path": "..."
  },
  "metadata": {
    "user_slug": "...",
    "run_id": "...",
    "model": "...",
    "created_at_utc": "...",
    "proxy_wallet": null,
    "dossier_export_id": null,
    "window_days": null
  },
  "overall_assessment": "mixed",
  "primary_hypothesis": {
    "key": "id:H1",
    "id": "H1",
    "claim": "...",
    "confidence": "medium",
    "evidence_count": 1,
    "next_feature_needed": "...",
    "execution_recommendation": "...",
    "primary_evidence": {
      "text": "...",
      "file_path": "...",
      "path": "evidence[0].text",
      "trade_uid_count": 2,
      "trade_uids": ["t1", "t2"],
      "metrics": {}
    }
  },
  "summary": {
    "available_sections": ["metadata", "executive_summary", "hypotheses"],
    "bullet_count": 2,
    "hypothesis_count": 0,
    "observation_count": 0,
    "primary_hypothesis_key": null,
    "structured_fields_used": ["metadata.user_slug", "executive_summary.bullets[0]"]
  },
  "summary_bullets": [
    {
      "key": "identity",
      "text": "Identity: ...",
      "source_fields": ["metadata.user_slug", "metadata.run_id", "metadata.model"]
    }
  ]
}
```

Bullet keys are fixed and emitted only when backing content exists:
- `identity`
- `overall_assessment`
- `executive_summary`
- `core_edge_claim`
- `confidence`
- `primary_evidence`
- `risks_limitations`
- `next_step`

---

## Scope Constraints

**Did NOT touch:**
- Packet 1 validator or `llm-save` validation behavior
- Packet 2 diff behavior
- Track A / Gate 2 / strategy-codify / n8n / FastAPI wrapper work
- hypothesis schema contract
- live execution or automation wiring
