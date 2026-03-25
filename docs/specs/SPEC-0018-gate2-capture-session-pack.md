# SPEC-0018: Gate 2 Capture Session Pack

**Status:** Accepted
**Created:** 2026-03-10
**Authors:** PolyTool Contributors

---

## 1. Purpose and non-goals

### Purpose

Define the canonical artifact format and CLI contract for a **Gate 2 capture
session pack** — a pair of files that record one operator-driven capture
session's intent before it starts, making sessions repeatable, bounded, and
evidence-rich.

The existing scan → watch → tape-manifest workflow is correct. This spec adds
one small artifact step between scan output and watch invocation: the operator
selects exact slugs, labels a regime, and commits those choices to a
timestamped session pack before the watch session starts.

The pack can be built from:
- explicit `--slugs`
- an existing `--watchlist-file`
- or both merged together

### Non-goals

- Does **not** change Gate 2 pass criteria (profitable_fraction >= 0.70)
- Does **not** change strategy entry logic, preset sizing, or buffer
- Does **not** change `scan-gate2-candidates`, `watch-arb-candidates`,
  `tape-manifest`, or `gate2-preflight` behavior
- Does **not** add autonomous market selection or live execution
- Does **not** apply to Gate 3, Stage 0, Stage 1, or any VPS/cloud workflow
- Does **not** require a live network connection (all offline)

---

## 2. Problem: slug selection is undocumented

Between `scan-gate2-candidates` output and the `watch-arb-candidates`
invocation, the operator mentally selects a subset of ranked slugs. This
selection step is invisible:

- Which slugs were chosen and why?
- What was the corpus state at the time of selection?
- When did the session start?
- What happened after?

Without a session artifact, repeated capture attempts accumulate tapes with no
record of the original intent, making it hard to review sessions and correlate
tape outcomes with candidate quality.

---

## 3. Session pack format

A session pack is a timestamped subdirectory written to
`artifacts/session_packs/<session_id>/` containing two files:

### `session_watchlist.txt`

One exact market slug per line. No truncation. No header.

Compatible with `watch-arb-candidates --watchlist-file` and
`scan-gate2-candidates --watchlist-out` format.

```
will-the-oklahoma-city-thunder-win-the-series
will-the-celtics-win-the-nba-championship
```

### `session_plan.json`

Full structured artifact documenting session intent.

#### Schema (`gate2_session_pack_v1`)

```json
{
  "schema_version": "gate2_session_pack_v1",
  "session_id": "20260310T143000Z",
  "created_at": "2026-03-10T14:30:00Z",
  "regime": "sports",
  "chosen_slugs": ["slug1", "slug2"],
  "slug_count": 2,
  "watchlist_path": "artifacts/session_packs/20260310T143000Z/session_watchlist.txt",
  "plan_path": "artifacts/session_packs/20260310T143000Z/session_plan.json",
  "watch_config": {
    "duration_seconds": 600.0,
    "poll_interval_seconds": 30.0,
    "near_edge_threshold": 1.0,
    "min_depth": 50.0
  },
  "watch_command": "python -m polytool watch-arb-candidates ...",
  "watchlist": [
    {
      "market_slug": "slug1",
      "session_priority": 1,
      "selection_source": "watchlist-file:artifacts/watchlists/gate2_top20.txt",
      "selected_at_utc": "2026-03-10T14:30:00Z",
      "operator_regime": "sports",
      "derived_regime": "sports",
      "final_regime": "sports",
      "regime_source": "derived",
      "regime_mismatch": false,
      "age_hours": 12.0,
      "is_new_market": true,
      "market_snapshot": {
        "market_slug": "slug1",
        "question": "Will the Toronto Maple Leafs win the 2026 NHL Stanley Cup?",
        "category": "Sports"
      }
    }
  ],
  "corpus_context": {
    "eligible_count": 0,
    "covered_regimes": ["sports"],
    "missing_regimes": ["politics", "new_market"],
    "corpus_note": "BLOCKED: No eligible tapes. ...",
    "manifest_source": "artifacts/gates/gate2_tape_manifest.json",
    "manifest_generated_at": "2026-03-10T12:00:00Z"
  },
  "post_session_notes": "",
  "post_session_template": "## Post-Session Note — 20260310T143000Z\n..."
}
```

#### Field definitions

| Field | Meaning |
|-------|---------|
| `schema_version` | Always `gate2_session_pack_v1` |
| `session_id` | Compact UTC timestamp: `YYYYMMDDTHHMMSSZ` |
| `created_at` | Full ISO-8601 timestamp of pack creation |
| `regime` | Operator-chosen regime label for this session |
| `chosen_slugs` | Exact, deduplicated, ordered slug list |
| `slug_count` | Length of `chosen_slugs` |
| `watchlist_path` | Absolute or relative path to the watchlist file |
| `plan_path` | Absolute or relative path to `session_plan.json` |
| `watch_config` | Planned watcher parameters recorded with the pack |
| `watch_command` | Paste-ready `watch-arb-candidates` command using the JSON plan |
| `watchlist` | Watcher-compatible array of per-slug selection records |
| `corpus_context.eligible_count` | Eligible tape count at pack creation time (null if no manifest) |
| `corpus_context.covered_regimes` | Named regimes with eligible tapes at pack creation time |
| `corpus_context.missing_regimes` | Named regimes still lacking eligible tapes |
| `corpus_context.corpus_note` | Human-readable corpus assessment from tape-manifest |
| `corpus_context.manifest_source` | Path to the manifest JSON used; null if none |
| `corpus_context.manifest_generated_at` | Manifest generation timestamp; null if none |
| `post_session_notes` | Operator fills this in after the session (starts empty) |
| `post_session_template` | Paste-ready note template pre-filled with session context |

#### `watchlist` row contract

Each row preserves `market_slug` plus any upstream metadata already present in
the source watchlist file. The pack also adds deterministic planning context:

- `session_priority`
- `selection_source`
- `selected_at_utc`
- `operator_regime`
- `derived_regime`
- `final_regime`
- `regime_source`
- `regime_mismatch`
- `age_hours`
- `is_new_market`
- `market_snapshot`

This makes the plan readable by `watch-arb-candidates --watchlist-file`
because the top-level `watchlist` array is preserved.

#### `corpus_context` when no manifest is provided

```json
{
  "eligible_count": null,
  "covered_regimes": [],
  "missing_regimes": [],
  "corpus_note": "No manifest provided — run 'python -m polytool tape-manifest' ...",
  "manifest_source": null,
  "manifest_generated_at": null
}
```

---

## 4. Session ID format

```
YYYYMMDDTHHMMSSZ
```

Example: `20260310T143000Z` = 2026-03-10 14:30:00 UTC.

- Always UTC
- Compact but sortable lexicographically
- Used as the session pack subdirectory name

---

## 5. CLI contract

### Command

```bash
python -m polytool make-session-pack \
    [--ranked-json <path>] \
    [--slugs <slug1> [slug2 ...]] \
    [--watchlist-file <path>] \
    [--top <N>] \
    --regime <politics|sports|new_market|unknown> \
    [--source-manifest <path>] \
    [--out-dir <dir>] \
    [--duration <seconds>] \
    [--poll-interval <seconds>] \
    [--near-edge <threshold>] \
    [--min-depth <shares>]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--ranked-json` | No | Path to a `gate2_ranked_scan_v1` artifact from `scan-gate2-candidates --ranked-json-out`. Slugs are taken in rank order; rank/advisory context (gate2_status, rank_score, explanation) is preserved in the session plan's watchlist rows. Merged with `--slugs`/`--watchlist-file`; ranked-json entries appear first. |
| `--slugs` | No | Market slugs. Accepts repeated values or comma-separated. Deduplicated, order-preserved. |
| `--watchlist-file` | No | Existing report-style JSON or newline-delimited slug file. Merged with `--slugs`. |
| `--top` | No | Keeps the first N merged selections. |
| `--regime` | Yes | Regime label for the session: `politics`, `sports`, `new_market`, `unknown`. |
| `--source-manifest` | No | Path to `gate2_tape_manifest.json` for corpus context enrichment. Optional. |
| `--out-dir` | No | Base directory for output (default: `artifacts/session_packs/`). |
| `--duration` | No | Planned watcher duration recorded in the plan. |
| `--poll-interval` | No | Planned watcher poll interval recorded in the plan. |
| `--near-edge` | No | Planned watcher near-edge threshold recorded in the plan. |
| `--min-depth` | No | Planned watcher minimum depth recorded in the plan. |
| `-v`, `--verbose` | No | Debug logging. |

At least one of `--ranked-json`, `--slugs`, or `--watchlist-file` must be supplied.

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Session pack created successfully |
| 1 | Argument error (missing slugs, invalid regime, missing manifest path) |

### Stdout

Human-readable summary:
- Session ID, regime, slug list
- Watchlist and plan file paths
- Corpus state (if manifest provided)
- Paste-ready `watch-arb-candidates` invocation using `session_plan.json`

---

## 6. Operator workflow

```bash
# Step 1: Scan live candidates; emit ranked JSON and/or exact-slug watchlist
python -m polytool scan-gate2-candidates --all --top 20 --explain \
    --ranked-json-out artifacts/watchlists/gate2_top20_ranked.json \
    --watchlist-out   artifacts/watchlists/gate2_top20.txt

# Step 2a: Create session pack directly from ranked JSON (carries advisory context)
python -m polytool make-session-pack \
    --ranked-json artifacts/watchlists/gate2_top20_ranked.json \
    --top 3 \
    --regime sports \
    --source-manifest artifacts/gates/gate2_tape_manifest.json \
    --duration 600 \
    --poll-interval 30

# Step 2b (manual alternative): select slugs explicitly and create pack
python -m polytool make-session-pack \
    --watchlist-file artifacts/watchlists/gate2_top20.txt \
    --top 3 \
    --regime sports \
    --source-manifest artifacts/gates/gate2_tape_manifest.json \
    --duration 600 \
    --poll-interval 30

# Step 3: Start the watch session using the generated plan
python -m polytool watch-arb-candidates \
    --watchlist-file artifacts/session_packs/<session_id>/session_plan.json \
    --regime sports \
    --duration 600 \
    --poll-interval 30 \
    --near-edge 1.0 \
    --min-depth 50

# Step 4: After the session, check tape corpus
python -m polytool tape-manifest

# Step 5: Fill in the post-session template in session_plan.json
#   -> What happened, tape outcome, next action

# Step 6: If eligible tape found, run preflight and close Gate 2
python -m polytool gate2-preflight
python tools/gates/close_sweep_gate.py
```

---

## 7. Post-session template

The `post_session_template` field contains a Markdown note template
pre-populated with session context. After each session, the operator fills in:

- Market conditions observed (liquidity, spread behavior, edge proximity)
- Trigger outcome (fired / did not fire; tape path if fired)
- Tape outcome (`tape-manifest` result: eligible? executable_ticks? reject_reason?)
- Regime assessment (label correct? update `watch_meta.json` if not)
- Next action (proceed to sweep, retry with different slugs, etc.)

The completed note is saved in `post_session_notes` or alongside the session
pack as external documentation. This ensures each capture session is an
explicit, reviewable evidence step.

---

## 8. Constraints and invariants

1. **Exact slugs**: `chosen_slugs` and `session_watchlist.txt` always contain
   full, untruncated slugs. The operator never copies from a truncated table.

2. **Deduplication**: duplicate slugs in `--slugs` are silently removed while
   preserving first-seen order.

3. **Corpus context is read-only**: the pack reads the manifest at creation
   time. It does NOT write to or modify the manifest.

4. **No gate criteria changes**: Gate 2 pass criteria (profitable_fraction >= 0.70,
   max_size=50, buffer=0.01) are not affected by session packs.

5. **No watch behavior changes**: `watch-arb-candidates` is invoked as-is;
   the session pack only standardizes the slug-selection artifact.

6. **Watcher-compatible JSON**: `session_plan.json` preserves a top-level
   `watchlist` array readable by `watch-arb-candidates --watchlist-file`.

7. **Offline only**: `make-session-pack` makes no network calls.

8. **Non-destructive**: running `make-session-pack` multiple times creates
   separate timestamped subdirectories; nothing is overwritten.

---

## 9. Acceptance criteria

1. `python -m polytool make-session-pack --slugs slug1,slug2 --regime sports`
   creates `artifacts/session_packs/<session_id>/session_watchlist.txt` and
   `artifacts/session_packs/<session_id>/session_plan.json`.

2. `session_watchlist.txt` contains one exact slug per line and is loadable
   by `watch-arb-candidates --watchlist-file` without error.

3. `session_plan.json` carries schema_version, session_id, created_at, regime,
   chosen_slugs, slug_count, watchlist_path, plan_path, watch_config,
   watch_command, watchlist, corpus_context, post_session_notes,
   post_session_template.

4. `session_id` format is `YYYYMMDDTHHMMSSZ`.

5. Duplicate slugs in `--slugs` are deduplicated; order is preserved.

6. When `--source-manifest` is provided, `corpus_context.eligible_count`,
   `covered_regimes`, `missing_regimes`, and `corpus_note` are populated from
   the manifest.

7. When `--source-manifest` is omitted, `corpus_context.eligible_count` is
   `null` and `manifest_source` is `null`.

8. `session_plan.json` is loadable by `watch-arb-candidates --watchlist-file`
   because it preserves the top-level `watchlist` array contract.

9. `post_session_template` is non-empty and contains the session ID, regime,
   and slug list.

10. Empty `--slugs`/`--watchlist-file` selection (after parsing) returns exit code 1.

11. Invalid regime returns exit code 1.

12. `--source-manifest` pointing to a missing file returns exit code 1.

13. All tests in `tests/test_gate2_session_pack.py` pass.

---

## References

- `tools/cli/make_session_pack.py` — Implementation
- `tests/test_gate2_session_pack.py` — Acceptance tests
- `docs/runbooks/GATE2_ELIGIBLE_TAPE_ACQUISITION.md` — Operator runbook (updated)
- `docs/specs/SPEC-0014-gate2-eligible-tape-acquisition.md` — Tape acquisition spec
- `docs/specs/SPEC-0017-phase1-gate2-candidate-ranking.md` — Ranking spec
- `tools/cli/scan_gate2_candidates.py` — Candidate scanner (upstream)
- `tools/cli/watch_arb_candidates.py` — Watcher (downstream consumer of watchlist)
- `tools/cli/gate2_preflight.py` — Preflight check (downstream)
