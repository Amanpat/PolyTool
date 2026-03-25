# Feature: Gate 2 Capture Session Pack

**Spec:** `docs/specs/SPEC-0018-gate2-capture-session-pack.md`
**Status:** Implemented
**Date:** 2026-03-10

---

## Summary

Adds a `make-session-pack` CLI command that bridges the gap between
`scan-gate2-candidates` output and `watch-arb-candidates` invocation.

Before this feature, the operator's slug selection step was invisible: which
slugs were chosen, what the corpus state was at selection time, and what
happened during the session were all undocumented.

Now the operator runs one additional command before each watch session. It can
take explicit slugs or an existing watchlist file, commits that selection to a
timestamped artifact, and produces:
- an exact slug watchlist file
- a watcher-compatible JSON plan with per-slug context

---

## What changed

### New file

**`tools/cli/make_session_pack.py`** — `make-session-pack` CLI

- `make_session_pack(chosen_slugs, regime, *, source_manifest_path, out_dir, now)` — core function
- `_read_corpus_context(manifest_path)` — reads eligible_count and coverage from tape manifest
- `_build_post_session_template(session_id, regime, slugs, ...)` — paste-ready note template
- `_session_id_from_dt(dt)` — `YYYYMMDDTHHMMSSZ` session ID
- `_parse_slugs_arg(slugs_arg)` — comma-or-space separated slug parsing
- `print_session_pack_summary(plan)` — stdout summary + paste-ready watch command
- `build_parser()` + `main(argv)` — CLI entrypoint

Produces two files per session in `artifacts/session_packs/<session_id>/`:
- `session_watchlist.txt` — exact slugs, one per line
- `session_plan.json` — full context artifact (schema `gate2_session_pack_v1`)

`session_plan.json` now includes:
- `watch_config`
- `watch_command`
- a top-level watcher-compatible `watchlist` array
- per-slug regime / new-market context when derivable from source metadata

### Updated files

- `polytool/__main__.py` — added `make-session-pack` route and usage line
- `docs/runbooks/GATE2_ELIGIBLE_TAPE_ACQUISITION.md` — Phase 1.5 added
- `docs/INDEX.md` — feature and spec entries added

### New test file

**`tests/test_gate2_session_pack.py`** — 38 tests, all passing

---

## Operator workflow

```bash
# 1. Scan live candidates (existing step)
python -m polytool scan-gate2-candidates --all --top 20 --explain

# 2. NEW: Commit ranked selection to a session pack
python -m polytool make-session-pack \
    --watchlist-file artifacts/watchlists/gate2_top20.txt \
    --top 3 \
    --regime sports \
    --source-manifest artifacts/gates/gate2_tape_manifest.json \
    --duration 600 \
    --poll-interval 30

# Output shows:
#   Session pack created: 20260310T143000Z
#     Regime : sports
#     Slugs  : 2
#       - will-the-okc-thunder-win
#       - will-the-celtics-win
#     Watchlist : artifacts/session_packs/20260310T143000Z/session_watchlist.txt
#     Plan      : artifacts/session_packs/20260310T143000Z/session_plan.json
#     Corpus    : eligible=0  covered=['sports']  missing=['politics', 'new_market']
#
#   Start the watch session with:
#     python -m polytool watch-arb-candidates \
#         --watchlist-file artifacts/session_packs/20260310T143000Z/session_plan.json \
#         --regime sports --duration 600 --poll-interval 30 --near-edge 1.0 --min-depth 50

# 3. Copy and run the printed watch command (existing step)
python -m polytool watch-arb-candidates \
    --watchlist-file artifacts/session_packs/20260310T143000Z/session_plan.json \
    --regime sports \
    --duration 600 \
    --poll-interval 30 \
    --near-edge 1.0 \
    --min-depth 50

# 4. After session, check corpus (existing step)
python -m polytool tape-manifest

# 5. Fill in post_session_template in session_plan.json
```

---

## Key design decisions

### Exact slugs — never truncated

`session_watchlist.txt` contains full, untruncated slugs. The operator never
needs to copy from a truncated table column. This is the same guarantee as
`scan-gate2-candidates --watchlist-out`.

### Plan JSON stays watcher-compatible

`session_plan.json` preserves a top-level `watchlist` array so it can be passed
directly to `watch-arb-candidates --watchlist-file`. This keeps the workflow
inside the existing watch path while carrying richer planning metadata forward.

### Corpus context is read-only snapshot

The session pack reads `gate2_tape_manifest.json` at creation time to capture
the corpus state the operator saw when they made their selection. It does not
write to or modify the manifest.

### Offline — no network calls

`make-session-pack` requires no live API access. Corpus context comes from the
locally-generated manifest.

### Non-destructive — timestamped subdirectories

Each invocation creates a new `<session_id>/` subdirectory. Multiple sessions
accumulate without collision.

### Backwards-compatible

No existing CLI behavior changes. `scan-gate2-candidates`, `watch-arb-candidates`,
`tape-manifest`, and `gate2-preflight` are unmodified.

---

## Session plan JSON schema

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
      "final_regime": "sports",
      "is_new_market": false
    }
  ],
  "corpus_context": {
    "eligible_count": 0,
    "covered_regimes": ["sports"],
    "missing_regimes": ["politics", "new_market"],
    "corpus_note": "BLOCKED: ...",
    "manifest_source": "artifacts/gates/gate2_tape_manifest.json",
    "manifest_generated_at": "2026-03-10T12:00:00Z"
  },
  "post_session_notes": "",
  "post_session_template": "## Post-Session Note — 20260310T143000Z\n..."
}
```

---

## Operator checklist

- [ ] Run `scan-gate2-candidates --all --top 20 --explain --ranked-json-out <path>` to identify candidates and emit ranked JSON
- [ ] Run `make-session-pack --ranked-json <path> --top <N> --regime <regime>` to commit selection with advisory context preserved
- [ ] Copy the printed watch command and run `watch-arb-candidates`
- [ ] After session: run `tape-manifest` to check corpus
- [ ] Fill in the `post_session_template` in `session_plan.json`
- [ ] Run `gate2-preflight` to check sweep readiness

---

---

## Coverage-aware session planning (2026-03-10)

`make-session-pack` can now read the tape manifest at pack creation time and
guide the operator toward missing regimes.

### New CLI flags

| Flag | Description |
|------|-------------|
| `--prefer-missing-regimes` | Reorder candidates so missing-regime targets appear first (before `--top` is applied). Requires `--source-manifest`. |
| `--target-regime REGIME` | Filter candidates to those matching `REGIME` before `--top`. Advisory: if no candidates match, all are included with a warning. |

### New `coverage_intent` field in `session_plan.json`

```json
"coverage_intent": {
  "prefer_missing": false,
  "target_regime": null,
  "missing_regimes_at_creation": ["politics", "new_market"],
  "advances_coverage": false,
  "coverage_warning": "NOTICE: None of the selected slugs target missing regimes ..."
}
```

| Field | Meaning |
|-------|---------|
| `prefer_missing` | Whether `--prefer-missing-regimes` was applied |
| `target_regime` | Value of `--target-regime` if set, else `null` |
| `missing_regimes_at_creation` | Named missing regimes from the manifest at pack creation |
| `advances_coverage` | `true` if any selected slug targets a missing regime; `false` if not; `null` if no manifest |
| `coverage_warning` | Advisory notice when selection doesn't advance coverage; `null` when clean |

### Design decisions

- Coverage guidance is **advisory only** — Gate 2 pass criteria are unchanged.
- `--prefer-missing-regimes` and `--target-regime` apply before `--top` so
  the preference actually affects which candidates are selected, not just
  their order within a fixed set.
- When `--target-regime` finds no matching candidates, all candidates are
  included (not rejected) and a warning is printed to stderr.
- Regime classification uses the fast path from ranked-JSON `regime` field
  when available; falls back to `derive_tape_regime` snapshot derivation.
- `coverage_intent` is always present in the plan (with null `advances_coverage`
  when no manifest was provided).

---

## Deferred

- Expiry field on session packs (auto-expiring watchlists) — deferred; use
  `watch-arb-candidates --duration` to bound sessions instead.
- Multi-session corpus view (aggregate post-session notes across sessions) — deferred.
