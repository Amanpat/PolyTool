# Dev Log: session-pack target-regime false coverage fix

**Date:** 2026-03-10
**Branch:** simtrader
**Files changed:** 2 (source + test)

---

## Problem

Running `make-session-pack` with:

```
--target-regime politics
--source-manifest artifacts/gates/gate2_tape_manifest.json
```

against a ranked-scan that contained only UNKNOWN-regime markets
(`gta-vi-released-before-june-2026`, `will-jesus-christ-return-before-gta-vi-665`)
printed:

```
Coverage  : session advances missing regime coverage -> ['gta-vi-released-before-june-2026', ...]
```

That is a false positive.  Neither slug has political content signal.

---

## Root cause

`_build_watchlist_rows` calls `derive_tape_regime(..., operator_regime=regime, ...)`
where `regime` is the **session-level** `--regime` argument (e.g. `"politics"`).

`derive_tape_regime` selection logic:

1. If derived regime (from content) is a named regime → use it.
2. If derived is `"other"` (no content signal) and operator is a named regime → use operator.
3. Otherwise → `"unknown"`.

GTA VI slugs have no political keywords, so `derived = "other"`.  The operator
fallback then promotes them to `final_regime = "politics"` (from the session
`--regime`).

`_build_coverage_intent` then sees `final_regime = "politics"` intersecting
`named_missing = ["politics", ...]` and sets `advances_coverage = True`.

The session regime is a **session-level hint**, not a per-market label.
Markets that the scanner already classified as `unknown` should not inherit it
as a coverage credit.

---

## Fix

**`tools/cli/make_session_pack.py` — `_build_watchlist_rows`**

Before calling `derive_tape_regime`, check the target's pre-scan `_regime`
key (set by `_load_ranked_json` from the ranked-scan artifact):

```python
pre_regime = target.metadata.get("_regime")
effective_operator_regime = "unknown" if pre_regime == "unknown" else regime
integrity = derive_tape_regime(
    snapshot,
    operator_regime=effective_operator_regime,
    reference_time=created_dt,
)
```

When `_regime = "unknown"`:
- `effective_operator_regime = "unknown"` → op_named = False
- `derived = "other"` → derived_named = False
- Result: `final_regime = "unknown"`, `regime_source = "fallback_unknown"`

`_build_coverage_intent` then sees:
- `selected_regimes = {"unknown"}`
- `named_missing` never includes `"unknown"` (filtered out by design)
- Intersection is empty → `advances_coverage = False`
- `coverage_warning` is set (either from `target_regime_warning` or the
  generic "None of the selected slugs target missing regimes" notice)

The operator sees a clear warning instead of a false success message.

---

## Behaviour change

| Scenario | Before | After |
|----------|--------|-------|
| UNKNOWN markets + `--target-regime politics` | `advances_coverage=True`, "session advances missing regime coverage" printed | `advances_coverage=False`, NOTICE warning printed |
| Named-regime markets (politics/sports/new_market) | Unchanged | Unchanged |
| Markets without `_regime` key (manual `--slugs`) | Unchanged | Unchanged |

---

## Tests added

**`tests/test_gate2_session_pack.py`** (+3 tests):

- `test_unknown_regime_target_does_not_advance_named_coverage` — unit: two
  UNKNOWN targets + `--regime politics` + missing politics → `advances_coverage=False`,
  all `final_regime="unknown"`.
- `test_cli_unknown_regime_candidates_with_target_regime_warns_not_advances` —
  CLI integration: ranked-json with two UNKNOWN slugs, `--target-regime politics`,
  `--source-manifest` → no "advances missing regime coverage" in stdout, NOTICE
  visible, `advances_coverage=False`.
- `test_named_regime_target_still_advances_coverage` — guard: politics market
  with category metadata still sets `advances_coverage=True` (regression guard
  for the normal path).

74 tests total in file, all passing.
