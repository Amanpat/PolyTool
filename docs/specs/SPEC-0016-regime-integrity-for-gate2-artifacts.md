# SPEC-0016: Regime Integrity for Gate 2 Artifacts

**Status:** Accepted
**Created:** 2026-03-08
**Authors:** PolyTool Contributors

---

## 1. Purpose and non-goals

### Purpose

Define the canonical contract for regime provenance in Gate 2 tape acquisition
artifacts so that mixed-regime corpus coverage cannot drift from
operator-entered labels that are never cross-checked against available market
metadata.

Prior to this spec, the only regime signal in `gate2_tape_manifest.json` was
the operator-entered `--regime` flag at capture time.  There was no machine
check against the market slug or metadata, no explicit record of how a regime
was determined, and no way to detect when an operator label contradicted what
the market metadata implied.

### Non-goals

- Does **not** change Gate 2 pass criteria (profitable_fraction >= 0.70)
- Does **not** change strategy entry logic or preset sizing
- Does **not** touch Discord notification code
- Does **not** touch FastAPI, n8n, Grafana, or deploy scripts
- Does **not** weakly trust freeform operator labels without provenance

---

## 2. Problem: label drift

Gate 2 requires diverse regime coverage before Gate 3 shadow validation can
begin.  The mixed-regime requirement depends entirely on operator discipline:
if every tape is captured with `--regime sports` regardless of what the market
actually is, the coverage summary will show false saturation.

Symptoms of drift:
- `corpus_summary.by_regime.sports.eligible = 3` but all three are actually
  US-politics markets labeled sports by mistake.
- `mixed_regime_eligible: false` because the operator forgot `--regime` on two
  political tapes that ended up as `unknown`.
- `mixed_regime_eligible: true` from two eligible tapes in regimes that were
  typed wrong.

---

## 3. Canonical regime integrity contract

### Fields added per tape record

Every tape entry in `gate2_tape_manifest.json` (schema v2) carries:

| Field | Type | Meaning |
|-------|------|---------|
| `derived_regime` | string | Regime from `classify_market_regime()` on available metadata; `"other"` when signal is weak |
| `operator_regime` | string | Raw regime label from tape metadata (`watch_meta.json` / `prep_meta.json`); `"unknown"` if absent |
| `final_regime` | string | Authoritative regime for corpus counting (see selection logic below) |
| `regime_source` | string | `"derived"` \| `"operator"` \| `"fallback_unknown"` |
| `regime_mismatch` | bool | True when derived and operator are BOTH named regimes and they disagree |

The existing `regime` field is retained for backward compatibility and equals
`final_regime` for all new records.

### Artifact-local snapshot precedence

If `watch_meta.json` or `prep_meta.json` contains a `market_snapshot` block,
the manifest generator derives regime/new-market context from that snapshot
first. Legacy top-level metadata and `meta.json` remain fallback sources for
older tapes that do not carry a snapshot.

### Selection logic for `final_regime`

```
if derived_regime in {politics, sports, new_market}:
    final_regime = derived_regime
    regime_source = "derived"
elif operator_regime in {politics, sports, new_market}:
    final_regime = operator_regime
    regime_source = "operator"
else:
    final_regime = "unknown"
    regime_source = "fallback_unknown"
```

Derived regime wins when the classifier has a clear signal (politics/sports/new_market).
Operator regime is used as a fallback when the classifier has no signal (slug/metadata
too generic).  If both are weak, `final_regime = "unknown"`.

### Mismatch rule

```
regime_mismatch = (
    derived in {politics, sports, new_market}
    AND operator in {politics, sports, new_market}
    AND derived != operator
)
```

No mismatch is declared when either side is `"other"` or `"unknown"` — there
is not enough signal to call it a contradiction.

---

## 4. Mixed-regime coverage

`corpus_summary.mixed_regime_eligible` is now computed via
`regime_policy.coverage_from_classified_regimes()` (shared helper) rather than
ad hoc label counting.  This ensures the coverage definition cannot diverge
between the classification logic and the manifest generator.

`corpus_summary.regime_coverage` is added to the manifest:

```json
"regime_coverage": {
    "satisfies_policy": false,
    "covered_regimes": ["sports"],
    "missing_regimes": ["politics", "new_market"],
    "regime_counts": {"politics": 0, "sports": 1, "new_market": 0}
}
```

Coverage is computed from eligible tapes' `final_regime` values only.
`"unknown"` tapes do not count toward any required regime.

---

## 5. Legacy artifact backward compatibility

Tapes recorded before this spec have no `market_snapshot`, `derived_regime`,
or `final_regime` in their metadata files. The manifest generator handles
these conservatively:

1. `operator_regime` = whatever the `regime` field says in the existing
   watch_meta.json / prep_meta.json (may be `"unknown"`)
2. `derived_regime` = result of `classify_market_regime()` on the slug alone
   (often `"other"` for ambiguous slugs)
3. `final_regime` follows the selection logic above
4. `regime` = `final_regime` (so the output column is still correct)

No manual migration is needed.  Re-running `tape-manifest` on existing tapes
will upgrade their manifest entries automatically.

---

## 6. Acceptance criteria

1. `gate2_tape_manifest.json` schema version is `gate2_tape_manifest_v2`.
2. Every tape entry contains `derived_regime`, `operator_regime`, `final_regime`,
   `regime_source`, `regime_mismatch`.
3. `final_regime == regime` for all new records.
4. `regime_mismatch` is True only when both derived and operator are named
   regimes and they disagree.
5. `corpus_summary.regime_coverage` is present and uses
   `coverage_from_classified_regimes()` logic.
6. When a capture artifact contains `market_snapshot`, regime/new-market
   derivation prefers that artifact-local snapshot over `meta.json`.
7. `mixed_regime_eligible` computation is identical under both the old and new
   implementations for any corpus where all tapes have operator labels.
8. Legacy tape records (no new fields) serialize with `regime` = operator label.
9. All tests in `tests/test_regime_policy.py` and
   `tests/test_gate2_eligible_tape_acquisition.py` pass.

---

## 7. Operator guidance

### When to trust `derived_regime`

The classifier uses slug, title, question, tags, and category fields.  For
markets with clear regime keywords in the slug (e.g., `senate`, `nba`, `nhl`,
`election`), the derived regime is reliable.  For generic slugs (e.g.,
`will-btc-close-above-100k`), derived will be `"other"` and the operator label
is used.

### When to investigate `regime_mismatch: true`

A `regime_mismatch` record is not automatically wrong — the classifier can
mis-classify obscure markets.  However, it warrants operator review:

1. Check the tape slug and market metadata.
2. If the classifier is right and the operator label is wrong, update
   `watch_meta.json` or `prep_meta.json` with the correct label and re-run
   `tape-manifest`.
3. If the operator label is correct and the slug is ambiguous, the mismatch
   flag is informational only.  The `final_regime = derived_regime` (derived
   wins) but the operator can override by making the metadata richer (add
   `question` or `tags` fields to the meta file).

### Conservative fallback

- Do not guess a regime when both derived and operator are weak.
  `regime_source = "fallback_unknown"` is the honest answer.
- Do not trust `regime_mismatch: false` alone as evidence the regime is correct.
  It means "no contradiction detected", not "definitely correct".

---

## References

- `packages/polymarket/market_selection/regime_policy.py` — classifier + `derive_tape_regime` + `coverage_from_classified_regimes`
- `tools/cli/tape_manifest.py` — manifest generator with regime integrity
- `docs/specs/SPEC-0014-gate2-eligible-tape-acquisition.md` — tape acquisition spec
- `docs/specs/SPEC-0012-phase1-tracka-live-bot-program.md` — mixed-regime requirement
- `tests/test_regime_policy.py` — classifier + integrity tests
- `tests/test_gate2_eligible_tape_acquisition.py` — manifest + integrity tests
