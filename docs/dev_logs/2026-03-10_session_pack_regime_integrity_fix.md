# Dev Log: Session Pack Regime Integrity Fix

Date: 2026-03-10

## Problem

`make-session-pack` was letting the session-level `--regime` leak into factual
market classification during targeted selection and watchlist row generation.
That created two bad outcomes:

- `--target-regime politics` could keep UNKNOWN/off-target candidates and still
  make the pack look politically targeted.
- `--target-regime new_market` could treat unknown/null age as a new-market hit
  just because the operator passed `--regime new_market`.

The resulting `session_plan.json` could therefore record factual-looking regime
fields that were really just operator input, and `coverage_intent` could be
misleading or null under targeted runs.

## Fix

The patch is intentionally narrow and only touches session-pack logic.

- Targeted filtering now probes factual regime only.
- Session watchlist rows now keep factual regime separate from the session
  operating regime.
- Ranked-scan `_regime` advisory data is preserved as factual regime when
  present.
- Unknown age does not self-promote a market into `new_market`.
- When `--target-regime` is used, `coverage_intent.advances_coverage` is always
  explicit (`true` or `false`), never `null`.
- If no factual target matches exist, the command emits an explicit
  non-advancing pack with a hard warning instead of pretending coverage
  progress.

## Files

- `tools/cli/make_session_pack.py`
- `tests/test_gate2_session_pack.py`

## Regression Coverage

Added/updated tests for:

- politics target with only UNKNOWN/off-target candidates
- new_market target with unknown age
- operator regime cannot rewrite factual regime
- targeted packs without manifest context still emit explicit non-advancing
  coverage intent
- valid factual targeted packs still advance coverage when manifest context says
  the regime is missing

## Verification

Automated:

```powershell
pytest -q tests/test_gate2_session_pack.py
```

Manual:

```powershell
python -m polytool make-session-pack `
  --ranked-json artifacts/watchlists/gate2_ranked_latest.json `
  --regime politics `
  --target-regime politics `
  --top 3 `
  --duration 600 `
  --poll-interval 30
```

Expected after the fix:

- no UNKNOWN/off-target market is rewritten to factual `politics`
- `coverage_intent.advances_coverage` is explicit
- off-target targeted runs emit a hard warning and stay non-advancing
