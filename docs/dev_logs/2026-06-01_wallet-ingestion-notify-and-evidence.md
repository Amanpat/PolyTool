# 2026-06-01 — Wallet-ingestion notifications + display-time evidence

**Work packet:** post-v1 follow-up to WI-5. Vera two-way Discord approval is
descoped; operator workflow is now **notifications via the existing outbound
webhook, approvals via the CLI gate** (`discovery review --approve/--deny`).

## Problem

1. **Generic evidence at display.** Pending candidates surfaced by
   `discovery review --list-pending` showed the stored `reason` column. When the
   WI-1 worker advancer ([scan_worker.py](../../packages/polymarket/discovery/scan_worker.py))
   wrote the row, that reason is the generic
   `"scan-worker drained scan_queue and produced a dossier"` — not real evidence.
   (The WI-4 candidate-population path stores the real `summarize_evidence`
   string, so behaviour was inconsistent across paths.)
2. **No outbound notification** fired when a candidate entered
   `review_status='pending'`.

## Change (one cohesive packet)

New module **`packages/polymarket/discovery/pending_notify.py`** — kept separate
from the pure WI-5 `approval_request.py` because it touches the Discord
transport (which `approval_request` deliberately does not).

### A) Real evidence at display time

- `compute_row_evidence(row, *, metrics_reader=None)` recomputes
  `summarize_evidence` from the wallet's **fresh scan metrics** rather than
  trusting the stored `reason`. This normalises both advance paths (worker vs.
  candidate-population).
- `default_metrics_reader` locates the scan `run_root` from the row's
  `last_scan_run_id` under `artifacts/dossiers/users/**/<run_id>` and reads
  `wallet_scan._extract_user_metrics`. Best-effort; never raises.
- Fallback chain: computed evidence → stored `reason` → `"no evidence available"`.
- Wired into `discovery review --list-pending` ([discovery.py](../../tools/cli/discovery.py)).
  The metrics reader is module-global so it stays test-injectable; with no
  locatable scan data it falls back to the stored reason (so the existing WI-5
  `--list-pending` tests stay green unchanged).

### B) Notify on a candidate entering pending review

- `format_pending_notification(addr, evidence)` builds a deterministic, **ASCII-only**
  (Windows-safe) message containing the **full** wallet address, the evidence
  body, and the exact CLI commands:
  ```
  python3 -m polytool discovery review --approve <full_addr>
  python3 -m polytool discovery review --deny <full_addr>
  ```
- `notify_pending_candidate(...)` posts via an injectable `post` callable
  (default = `notifications.discord.post_message`, lazily imported). **Dedup**
  reuses the WI-5 `approvals_notified.json` state file (`load_notified` /
  `mark_notified`): an already-notified wallet is skipped; a wallet is recorded
  as notified **only on successful delivery**, so a failed webhook is retried
  next pass rather than silently lost. The post **never raises** — a poster that
  returns `False` or throws is caught and reported via the `ok` flag.
- `notify_pending_candidates(rows, ...)` is the batch driver (compute evidence +
  deduped notify per row); returns `{considered, posted, deduped, failed}`.
- Wired into the worker CLI `_run_worker` as a **post-drain pass**: after the
  flush it reads pending candidates and notifies un-notified ones. This single
  hook covers candidates **regardless of which code path advanced the row**.
  Gated by a new `--no-notify` flag; the entire pass is wrapped non-fatally so a
  webhook/read failure never fails the worker.

## Guards honoured

- Did not touch kill switch / EIP-712 / order execution / risk manager / live
  bot (none are in the wallet-ingestion path).
- `DISCORD_WEBHOOK_URL` is never read/printed/logged/hardcoded here; the webhook
  value lives only in `post_message`. Unset URL → `post_message` no-ops
  (returns `False`) → wallet not marked, no error.
- Notification path is fully try/except-wrapped (mirrors the existing gate-script
  hooks); webhook failure cannot block or fail the pipeline.

## Tests

New: **`tests/test_wallet_ingestion_notify.py`** — 21 tests, fully offline
(injected metrics reader + post callable; tmp_path dedup file):

1. `--list-pending` shows computed `summarize_evidence` for a **worker-advanced**
   row (generic reason → real evidence); plus fallback-to-stored-reason case.
2. Entering pending posts **exactly one** webhook message containing addr +
   real evidence + both CLI lines (and NOT the generic reason).
3. A second pass does **not** re-notify (dedup; one message across two passes).
4. Notify **never raises** when `post` returns `False` or throws; failed
   delivery is not marked notified (retried).

Plus `format_pending_notification` (content / ASCII / full-address) and
`compute_row_evidence` (fallback / reader-exception safety) unit tests.

### Results

```
tests/test_wallet_ingestion_notify.py ...................... 21 passed
WI-5 + watchlist + discovery suites .......................... 190 passed
python -m polytool --help .................................... OK
python -m polytool discovery {review,run-worker} --help ...... OK
```

Full `pytest tests/` regression: see session output (no regressions introduced
by this packet).

## Codex review

Tier: **skip** per the project Codex Review Policy — this packet touches only
the wallet-ingestion display/notification path (no execution/, kill_switch,
risk_manager, rate_limiter, pair_engine, reference_feed, py_clob_client/EIP-712,
or bid/ask extraction files).

## Open questions / deferred

- Notification currently fires from the **worker drain** only. Wiring the same
  `notify_pending_candidates` pass into the discovery **scheduler** (so scheduled
  rescans also notify) is deliberately **out of scope** (scheduler work).
- Retention-cap work explicitly **not started** this session.
- `default_metrics_reader` globs the dossier tree by `run_id`; if dossier layout
  changes, that resolver needs updating (it degrades to the stored reason, never
  errors).
