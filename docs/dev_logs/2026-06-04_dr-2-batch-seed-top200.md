# DR-2 Batch-Seed Top-200 Corpus — BUILD ONLY

Date: 2026-06-04
Agent: Claude Code (Wave-2, DR-2)
Scope: BUILD + DRY-RUN only. The full live top-200 scan is an operator-initiated,
watched step AFTER this build is reviewed — it was NOT run here.

## Summary

Built the top-200 batch-seed path: a read-only leaderboard export helper + CLI
subcommand, and optional config-driven bulk pacing wired into the two aggressive
bulk loops (leaderboard page loop + wallet-scan batch loop). Reused the existing
`fetch_leaderboard()` and the existing `wallet-scan` ranked-leaderboard path — no
new fetch or PnL-ranking logic. The live dry-run is BLOCKED in this environment
(data-api.polymarket.com returns HTTP 403 — sandbox firewall); the path is instead
proven with offline/mocked tests including a full export → write → `parse_input_file`
round-trip and an end-to-end CLI-handler run with a mocked fetch.

## Files changed (uncommitted)

- `packages/polymarket/discovery/leaderboard_export.py` (NEW) — export helper
  (`export_leaderboard_addresses`, `write_input_file`, `export_to_file`). Maps
  `--top N` onto `fetch_leaderboard` page count; dedups; writes wallet-scan input.
- `packages/polymarket/discovery/bulk_pacing.py` (NEW) — `BulkPacer` (minimum-interval
  spacer, default-OFF) + `load_bulk_pacing()` (config loader, fail-safe to disabled).
- `packages/polymarket/discovery/leaderboard_fetcher.py` — added optional `pacer`
  param; paces before each page after the first. `pacer=None` ⇒ unchanged behaviour.
- `tools/cli/wallet_scan.py` — `WalletScanner(pacer=...)` paces between wallets;
  `--pace` / `--pace-delay` CLI flags (default OFF).
- `tools/cli/discovery.py` — new `export-leaderboard` subcommand + `_run_export_leaderboard`
  handler (DR-0's signal/worker-lock code left intact; targeted edits only).
- `config/discovery_scheduler.json` — new `bulk_pacing` block, `enabled: false` (OFF).
- `tests/test_dr2_batch_seed.py` (NEW) — 20 offline tests.

## Definition of Done — per-checkbox status

### [DONE] Top-200 addresses exportable to a wallet-scan input file (reusing fetch)

`discovery export-leaderboard --top 200 --out <file>` calls `export_to_file` →
`export_leaderboard_addresses` → `fetch_leaderboard` (REUSED, not reimplemented).
top=200 maps to `max_pages=4` at page_size=50. Verified by the round-trip test:
the exported file parses back through `tools.cli.wallet_scan.parse_input_file`
yielding 5 wallet-kind entries. Verified CLI-handler end-to-end with a mocked
fetch (live API 403-blocked):

```
{"requested": 5, "written": 5, "out_path": "...", "pacing_enabled": false}
RC 0
# Top-N leaderboard export for `wallet-scan --input` (DR-2 batch-seed).
0x...0001
...
0x...0005
```

### [DONE] Bulk scan path supports config-driven pacing; default conservative; scheduler cadence unaffected

`BulkPacer` is default-OFF (`enabled=false` ⇒ zero sleep, zero sleep calls). Wired
into BOTH bulk loops. Loop A and the scheduler `queue_drain` pass NO pacer, so the
gentle cadence is untouched (confirmed: 51 integrated+scheduler tests still pass).
Shipped config keeps it OFF (`test_shipped_config_bulk_pacing_is_off`). Evidence:

```
tests/test_dr2_batch_seed.py:
  test_disabled_never_sleeps ........................ PASS (0 sleep calls)
  test_no_pacer_means_no_sleep (page loop) .......... PASS
  test_enabled_paces_once_per_page_after_first ...... PASS (2 sleeps / 4 pages)
  test_no_pacer_no_sleep (batch loop) ............... PASS
  test_enabled_paces_between_wallets ................ PASS (3 sleeps / 5 wallets)
  test_shipped_config_bulk_pacing_is_off ............ PASS
```

### [BLOCKED] `wallet-scan --input <top200> --extract-dossier` dry-run produces dossiers + RIS + ranked leaderboard

BLOCKED — concrete reason: the leaderboard data API is unreachable from this
sandbox. `https://data-api.polymarket.com/v1/leaderboard` returns **HTTP 403
Forbidden** (verified by direct probe), so even the small `--top 5` export wrote
0 addresses and a live wallet scan cannot reach the local API/network either.

Mitigation (path proven offline): the export → input-file → `parse_input_file`
chain is verified by `test_export_to_file_roundtrips_through_wallet_scan_parser`,
and the dossier/RIS/leaderboard artifacts of the `wallet-scan --extract-dossier`
path are already covered by the existing, passing `tests/test_wallet_scan.py`
(46 tests) and `tests/test_ris_dossier_*` suites. No code on that path was changed
except the additive, default-off pacer.

Operator must run (on a host with network + API + ClickHouse up):

```
# 1) export the top-200 list
python -m polytool discovery export-leaderboard --top 200 --out artifacts/watchlists/top200.txt

# 2) dry-run on a small N first (5–10) to verify dossiers + RIS + leaderboard
head -n 13 artifacts/watchlists/top200.txt > artifacts/watchlists/top10.txt   # ~10 addrs (skip 3 header lines)
python -m polytool wallet-scan --input artifacts/watchlists/top10.txt --extract-dossier --pace

# 3) FULL batch-seed (operator-watched; NOT run by this packet)
python -m polytool wallet-scan --input artifacts/watchlists/top200.txt --extract-dossier --pace
```

Ranked output lands at:
`artifacts/research/wallet_scan/<YYYY-MM-DD>/<run_id>/leaderboard.json`
(+ `leaderboard.md`), sorted desc by `realized_net_pnl` — this is the artifact
the operator hands to the LLM offline.

### [DONE] Re-run / interrupted-run behavior documented (no dup/corruption)

Confirmed by reading the existing supersede + all-or-nothing ingest paths:

- **Re-run does not duplicate dossier knowledge.** `ingest_dossier_findings`
  runs `supersede_dossier_run` after ingesting the new run's findings
  (`packages/research/integration/dossier_extractor.py:612-617`), which flips
  prior active `dossier_report` docs/claims for the same normalized wallet to
  `lifecycle='superseded'` (`knowledge_store.py:489-523`). Retrieval (`rag-query`)
  excludes superseded rows, so a re-run leaves exactly one active dossier per wallet.
- **All-or-nothing per wallet.** The dossier extractor persists per-wallet
  findings in a transaction; if zero findings persist, `_make_dossier_extractor`
  raises (`wallet_scan.py:104-113`) → the wallet is recorded as a failure and is
  NOT advanced — no half-written knowledge.
- **Interrupted batch is safe.** `wallet-scan` writes artifacts per-wallet into
  `per_user_results` and only writes `leaderboard.json` at the end of the run;
  an interrupted run simply produces no final leaderboard for that run_id (no
  corruption of prior runs — each run is a fresh `<date>/<run_id>/` dir). Re-running
  re-scans all wallets; supersede keeps RIS deduped. The export file is idempotent
  (overwritten each export). On-disk prior dossier dirs are tar-gzipped on
  supersede, not duplicated (`dossier_extractor.py:729-740`).
- **Caveat (pre-existing, out of scope):** the watchlist has no no-resurrect guard
  for `review_status='rejected'` (see 2026-06-04 audit §2). Not a dup/corruption
  issue for the batch-seed corpus; flagged for the operator.

### [DONE] Tests + dev log written; ranked-export path documented

20 new tests in `tests/test_dr2_batch_seed.py`; this dev log; ranked path documented above.

## Test evidence

```
python -m pytest tests/test_wallet_scan.py tests/test_wallet_discovery.py \
  tests/test_wallet_discovery_two_tier.py tests/test_dr2_batch_seed.py -q
=> 167 passed

python -m pytest tests/test_dr2_batch_seed.py -q
=> 20 passed

python -m pytest tests/test_wallet_discovery_integrated.py tests/test_discovery_scheduler.py -q
=> 51 passed   (Loop A + scheduler cadence unaffected by the additive pacer)

python -m polytool --help                       => CLI loads clean
python -m polytool discovery --help             => export-leaderboard registered
python -m polytool discovery export-leaderboard --top 5 --out ...  => RC 0,
   "Warning: zero addresses written" (data-api HTTP 403 in this sandbox — BLOCKED dry-run)
```

No new failures. No pre-existing RIS academic-ingest failures surfaced (those
suites were not in the focused run; the broader suites run here were green).

## Codex review surface

- `tools/cli/discovery.py` `_run_export_leaderboard` — read-only fetch + write-file.
- `packages/polymarket/discovery/leaderboard_export.py` — read-only.
- `packages/polymarket/discovery/bulk_pacing.py` + the two `pace()` call sites in
  `leaderboard_fetcher.py` and `wallet_scan.py` — touch the scan/fetch loops
  (additive, default-off). Recommend `/codex:review --background` (NOT mandatory-tier:
  no execution/kill-switch/signing/order files touched).

## Operator trigger (hand-off)

```
# (a) export the top-200 list
python -m polytool discovery export-leaderboard --top 200 --out artifacts/watchlists/top200.txt

# (b) FULL batch-seed scan (operator-watched)
python -m polytool wallet-scan --input artifacts/watchlists/top200.txt --extract-dossier --pace
```
Enable steady-state pacing for the 200-wallet run via `--pace` (delay from
`config/discovery_scheduler.json` → `bulk_pacing.delay_seconds`, default 0.5s),
or `--pace --pace-delay 1.0` to override.
