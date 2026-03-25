# SPEC-0014: Gate 2 Eligible Tape Acquisition

**Status:** Accepted
**Created:** 2026-03-08
**Authors:** PolyTool Contributors

---

## 1. Purpose and non-goals

### Purpose

Define the canonical workflow for discovering, watching, capturing, and
labeling binary market tapes that are **Gate 2 eligible** — tapes that
contain at least one tick with simultaneous depth and complement edge
sufficient for `binary_complement_arb` to attempt an entry.

This spec operationalizes SPEC-0013 Packet 1 ("Eligible Tape Acquisition")
without weakening Gate 2 pass criteria or inventing parallel workflows
alongside the existing scan/watch/prepare path.

### Non-goals

- Does **not** define Gate 2 sweep pass criteria (remain in `close_sweep_gate.py`)
- Does **not** implement Opportunity Radar (deferred; see `docs/ROADMAP.md`)
- Does **not** change strategy entry logic, preset sizing, or fee models
- Does **not** claim Gate 2 is passed
- Does **not** apply to `market_maker_v0` (the Phase 1 live strategy)
- Does **not** cover Gate 3 shadow session execution

---

## 2. Canonical Gate 2 blocker

Gate 2 requires a tape with `executable_ticks > 0`:

- **`executable_ticks`**: the count of ticks where BOTH of the following
  hold simultaneously:
  1. `depth_ok`: YES best-ask size ≥ `max_size` AND NO best-ask size ≥ `max_size`
  2. `edge_ok`: `yes_ask + no_ask < 1 - buffer`
- The `sane` preset uses `max_size=50`, `buffer=0.01` (threshold 0.99)
- If `executable_ticks == 0`, the tape is **ineligible** — the sweep will
  produce 0/24 profitable scenarios (as confirmed by the `bitboy-convicted`
  failure: `profitable_scenarios=0`, dominant rejection: `insufficient_depth`)

**Eligibility is never softened.** A tape labeled eligible must have
`executable_ticks > 0` verified by `check_binary_arb_tape_eligibility`.
"Could be tradable" is not enough.

---

## 3. Candidate discovery flow

```
Step 1 — Discover candidates
  python -m polytool scan-gate2-candidates --all --top 20

Step 2 — Watch and auto-record (near-edge trigger)
  python -m polytool watch-arb-candidates \
    --markets <slug1,slug2,...> \
    --regime <politics|sports|new_market|unknown> \
    --duration 600 \
    --poll-interval 30

  OR: full orchestrated scan → record → check:
  python -m polytool prepare-gate2 \
    --top 3 --duration 300 \
    --regime <politics|sports|new_market|unknown>

Step 3 — Check tape corpus eligibility
  python -m polytool tape-manifest

Step 4 — If eligible tape found: close Gate 2
  python tools/gates/close_sweep_gate.py
```

### Discovery tools

| Tool | Purpose |
|------|---------|
| `scan-gate2-candidates` | Ranks live markets by depth and complement edge; identifies top candidates |
| `watch-arb-candidates` | Polls candidates; auto-starts tape recording on near-edge trigger |
| `prepare-gate2` | One-shot orchestrator: scan → record → eligibility check |
| `tape-manifest` | Audits existing tape corpus; emits `gate2_tape_manifest.json` |

### Regime labeling during capture

Both `watch-arb-candidates` and `prepare-gate2` accept `--regime` flag:

```bash
python -m polytool watch-arb-candidates \
  --markets presidential-election-2026 \
  --regime politics

python -m polytool prepare-gate2 \
  --top 3 --regime sports
```

The regime label is written to tape metadata (`watch_meta.json` or
`prep_meta.json`) and is read by `tape-manifest` to compute corpus coverage.

When available at capture time, the recording tool also writes an additive
`market_snapshot` block into the same artifact. This snapshot preserves the
best available local market metadata used later for regime/new-market
derivation, such as `question`, `category`, `tags`, `event_slug`,
`created_at`, `age_hours`, and `captured_at`.

---

## 4. Mixed-regime corpus policy

Gate 2+ validation must cover **at least three market regimes** per
SPEC-0012 §4:

| Regime | Label | Examples |
|--------|-------|---------|
| Politics | `politics` | Elections, policy referenda, geopolitical outcomes |
| Sports | `sports` | NFL, NBA, NHL, soccer event-resolution markets |
| New markets | `new_market` | Markets < 48 hours old |

**Corpus requirement**: at least one eligible tape per regime before Gate 3
shadow validation begins.

`tape-manifest` tracks coverage in `corpus_summary.by_regime`. The
`mixed_regime_eligible` field is `true` only when eligible tapes span
≥ 2 distinct named regimes (not counting `unknown`).

**Operator must explicitly label each tape** with `--regime` during
capture. Unlabeled tapes default to `unknown` and do not satisfy the
mixed-regime requirement even if eligible.

---

## 5. Tape eligibility signals and manifest schema

### Eligibility invariant

```
eligible = true   iff   ticks_with_depth_and_edge > 0
eligible = false  always if   ticks_with_depth_and_edge == 0
```

This invariant is enforced in `tools/cli/tape_manifest.py`:
```python
eligible = result.eligible and executable_ticks > 0
```

### Evidence stats per tape

From `check_binary_arb_tape_eligibility`:

| Field | Meaning |
|-------|---------|
| `events_scanned` | Total events read from tape |
| `ticks_with_both_bbo` | Ticks where both YES and NO had a best ask |
| `ticks_with_depth_ok` | Ticks where both sizes ≥ max_size |
| `ticks_with_edge_ok` | Ticks where sum_ask < threshold |
| `ticks_with_depth_and_edge` | Ticks where BOTH conditions hold (= executable_ticks) |
| `min_sum_ask_seen` | Best complement observed (lower = closer to threshold) |
| `min_yes_ask_size_seen` | Smallest YES best-ask size across tape |
| `min_no_ask_size_seen` | Smallest NO best-ask size across tape |
| `required_depth` | max_size parameter used |
| `required_edge_threshold` | 1 - buffer |

### Manifest schema (`gate2_tape_manifest_v1`)

```json
{
  "schema_version": "gate2_tape_manifest_v1",
  "generated_at": "<ISO-8601>",
  "strategy": "binary_complement_arb",
  "eligibility_params": {
    "max_size": 50.0,
    "buffer": 0.01,
    "threshold": 0.99
  },
  "corpus_summary": {
    "total_tapes": 13,
    "eligible_count": 0,
    "ineligible_count": 13,
    "by_regime": {
      "politics": {"total": 0, "eligible": 0},
      "sports": {"total": 7, "eligible": 0},
      "new_market": {"total": 0, "eligible": 0},
      "unknown": {"total": 6, "eligible": 0}
    },
    "mixed_regime_eligible": false,
    "gate2_eligible_tapes": [],
    "corpus_note": "BLOCKED: No eligible tapes. ..."
  },
  "tapes": [
    {
      "tape_dir": "artifacts/simtrader/tapes/...",
      "slug": "market-slug",
      "regime": "sports",
      "recorded_by": "watch-arb-candidates",
      "eligible": false,
      "executable_ticks": 0,
      "reject_reason": "insufficient depth: ...",
      "evidence": { ... }
    }
  ]
}
```

Written to `artifacts/gates/gate2_tape_manifest.json` by default.

### Ineligible tape always has reject_reason

Every ineligible tape entry must include a non-empty `reject_reason`
explaining why. Categories:
- `"insufficient depth: ..."` — sizes too small
- `"no positive edge: ..."` — sum_ask never < threshold
- `"depth and edge never overlap on the same tick"` — partial signal
- `"could not determine YES/NO asset IDs from tape metadata"` — metadata gap
- `"no events.jsonl found in tape directory"` — tape recording failed

---

## 6. Operator workflow

### Step-by-step: capture an eligible tape

```bash
# 1. Identify top candidates by depth + edge
python -m polytool scan-gate2-candidates --all --top 20

# 2a. Watch candidates (auto-records when near-edge trigger fires)
python -m polytool watch-arb-candidates \
  --markets <slug1,slug2> \
  --regime sports \
  --duration 600 \
  --poll-interval 30

# 2b. OR: one-shot orchestrated run on top candidates
python -m polytool prepare-gate2 \
  --top 3 --duration 300 --regime sports

# 3. Check corpus state (runs eligibility check on all tapes)
python -m polytool tape-manifest

# 4. If eligible_count > 0: close Gate 2
python tools/gates/close_sweep_gate.py

# 5. Verify gate status
python tools/gates/gate_status.py
```

### Labeling a tape with regime after the fact

If tapes were recorded without `--regime`, update `watch_meta.json` or
`prep_meta.json` manually:

```json
{
  "market_slug": "...",
  "yes_asset_id": "...",
  "no_asset_id": "...",
  "regime": "sports"
}
```

Do not invent missing `market_snapshot` values after the fact. Leave absent
fields absent if the capture artifact did not record them.

Then re-run `python -m polytool tape-manifest` to refresh the manifest.

### What to do when no eligible tapes exist

1. Run `scan-gate2-candidates --all --top 20` to check current market state.
2. Review `corpus_summary.by_regime` for the dominant failure mode.
3. If all tapes fail on depth: target higher-liquidity markets.
4. If all tapes fail on edge: wait for a dislocation event or target markets
   known to dislocate (e.g., near-live sports events, major election nights).
5. Do NOT weaken `max_size` or `buffer` to force a tape to pass.
6. Do NOT label an ineligible tape as eligible.

---

## 7. Failure modes

| Failure | Symptom | Action |
|---------|---------|--------|
| All tapes fail on depth | `ticks_with_depth_ok == 0`, `min_yes/no_ask_size` << 50 | Target more liquid markets; increase `--min-depth` in watcher to filter candidates earlier |
| All tapes fail on edge | `ticks_with_edge_ok == 0`, `min_sum_ask` ≥ 0.99 | Wait for market dislocation event; try markets with historically wider spreads |
| Depth and edge never overlap | `ticks_with_depth_ok > 0` AND `ticks_with_edge_ok > 0` but `ticks_with_depth_and_edge == 0` | Capture longer tapes; dislocation may be brief (try `--duration 600+`) |
| Tape has no asset IDs | `reject_reason`: "could not determine YES/NO asset IDs" | Ensure `--regime` and asset IDs are set in `watch_meta.json` or `prep_meta.json` |
| All tapes are `unknown` regime | `mixed_regime_eligible: false` | Re-run captures with explicit `--regime` flag |
| Watch loop fires no trigger | No new tapes created | Markets don't dislocate; try during catalyst events (game start, vote close) |

---

## 8. Acceptance criteria and evidence artifacts

### Acceptance criteria for this spec

1. `python -m polytool tape-manifest` runs against any tapes directory
   without error and produces `gate2_tape_manifest.json`.
2. All ineligible tapes in the manifest have a non-empty `reject_reason`.
3. `eligible=true` appears in the manifest ONLY when `executable_ticks > 0`.
4. `--regime` flag on `watch-arb-candidates` writes the regime label to
   `watch_meta.json`.
5. `--regime` flag on `prepare-gate2` writes the regime label to
   `prep_meta.json`.
6. Capture artifacts persist an additive `market_snapshot` block with the best
   available capture-time market metadata when those fields are available.
7. `tape-manifest` prefers artifact-local `market_snapshot` metadata when
   deriving regime/new-market context, while preserving legacy fallback
   behavior for older tapes without snapshots.
8. `corpus_summary.mixed_regime_eligible` is `true` only when eligible
   tapes span ≥ 2 distinct named regimes (not `unknown`).
9. Tests in `tests/test_gate2_eligible_tape_acquisition.py` all pass.

### Gate 2 evidence artifact

Gate 2 passes when `close_sweep_gate.py` writes:
```
artifacts/gates/sweep_gate/gate_passed.json
```
with `profitable_fraction >= 0.70`.

This requires an eligible tape. `tape-manifest` surfaces which tape(s) to
use. The manifest itself is not a gate artifact — it is an operator
visibility tool.

### Pre-Gate-2 evidence audit

Before running `close_sweep_gate.py`, operator verifies:
- `gate2_tape_manifest.json` exists and was generated recently
- `eligible_count >= 1`
- The eligible tape's `evidence.ticks_with_depth_and_edge > 0`
- The tape's `regime` is labeled (not `unknown` if possible)
- The tape was not captured during an anomalous event that would not repeat

---

## References

- `docs/specs/SPEC-0012-phase1-tracka-live-bot-program.md` — Phase 1 program, mixed-regime requirement
- `docs/specs/SPEC-0013-phase1-tracka-gap-matrix.md` — Gap matrix, Packet 1 definition
- `docs/runbooks/GATE2_ELIGIBLE_TAPE_ACQUISITION.md` — Operator runbook
- `tools/cli/tape_manifest.py` — Manifest generator
- `tools/cli/scan_gate2_candidates.py` — Candidate scanner
- `tools/cli/watch_arb_candidates.py` — Dislocation watcher + auto-recorder
- `tools/cli/prepare_gate2.py` — Orchestration glue
- `packages/polymarket/simtrader/sweeps/eligibility.py` — Eligibility check
- `tools/gates/close_sweep_gate.py` — Gate 2 sweep script
