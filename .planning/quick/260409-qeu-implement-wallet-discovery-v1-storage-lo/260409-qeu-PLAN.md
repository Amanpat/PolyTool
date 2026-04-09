---
phase: quick-260409-qeu
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - infra/clickhouse/initdb/27_wallet_discovery.sql
  - packages/polymarket/discovery/__init__.py
  - packages/polymarket/discovery/models.py
  - packages/polymarket/discovery/clickhouse_writer.py
  - packages/polymarket/discovery/leaderboard_fetcher.py
  - packages/polymarket/discovery/churn_detector.py
  - packages/polymarket/discovery/scan_queue.py
  - packages/polymarket/discovery/loop_a.py
  - tools/cli/discovery.py
  - polytool/__main__.py
  - tests/test_wallet_discovery.py
  - docs/dev_logs/2026-04-09_wallet_discovery_v1_impl_a.md
autonomous: true
requirements: []
must_haves:
  truths:
    - "Three ClickHouse tables (watchlist, leaderboard_snapshots, scan_queue) have DDL matching the frozen SPEC exactly"
    - "Leaderboard fetcher paginates through the Polymarket data API and returns typed row objects"
    - "Churn detector compares two snapshot sets and correctly identifies new, dropped, and persisting wallets"
    - "Scan queue manager enforces one-open-item-per-dedup-key and supports lease/expiry semantics"
    - "Lifecycle state machine rejects invalid transitions (discovered->promoted, scanned->promoted, etc.)"
    - "One-shot Loop A CLI command wires fetch -> churn -> enqueue into a single invocation"
    - "All deterministic tests pass with no network calls"
  artifacts:
    - path: "infra/clickhouse/initdb/27_wallet_discovery.sql"
      provides: "DDL for watchlist, leaderboard_snapshots, scan_queue tables"
      contains: "CREATE TABLE IF NOT EXISTS polytool.watchlist"
    - path: "packages/polymarket/discovery/models.py"
      provides: "Dataclasses, enums, lifecycle state machine, typed row models"
    - path: "packages/polymarket/discovery/leaderboard_fetcher.py"
      provides: "Paginated leaderboard fetch with raw payload preservation"
    - path: "packages/polymarket/discovery/churn_detector.py"
      provides: "Snapshot diff: new wallets, dropped wallets, is_new flagging"
    - path: "packages/polymarket/discovery/scan_queue.py"
      provides: "Queue insert with dedup, lease, expiry, re-queue logic"
    - path: "packages/polymarket/discovery/loop_a.py"
      provides: "One-shot Loop A orchestrator: fetch -> churn -> enqueue"
    - path: "tools/cli/discovery.py"
      provides: "CLI entrypoint: python -m polytool discovery run-loop-a"
    - path: "tests/test_wallet_discovery.py"
      provides: "Deterministic tests for AT-01 through AT-05"
  key_links:
    - from: "tools/cli/discovery.py"
      to: "packages/polymarket/discovery/loop_a.py"
      via: "CLI calls run_loop_a()"
      pattern: "run_loop_a"
    - from: "packages/polymarket/discovery/loop_a.py"
      to: "packages/polymarket/discovery/leaderboard_fetcher.py"
      via: "fetch_leaderboard() call"
      pattern: "fetch_leaderboard"
    - from: "packages/polymarket/discovery/loop_a.py"
      to: "packages/polymarket/discovery/churn_detector.py"
      via: "detect_churn() call"
      pattern: "detect_churn"
    - from: "packages/polymarket/discovery/loop_a.py"
      to: "packages/polymarket/discovery/scan_queue.py"
      via: "enqueue_wallets() call"
      pattern: "enqueue_wallets"
---

<objective>
Implement the Wallet Discovery v1 storage layer (ClickHouse DDL) and Loop A discovery
plumbing (leaderboard fetcher, churn detector, scan queue manager, one-shot CLI command).

Purpose: Deliver the infrastructure for automated wallet discovery from the Polymarket
leaderboard API, per the frozen SPEC-wallet-discovery-v1.md contract. This is the
foundational plumbing that later phases (scan --quick, MVF, Loop B/C/D) depend on.

Output: Three ClickHouse table DDLs, a `packages/polymarket/discovery/` module with
typed models + lifecycle state machine + leaderboard fetcher + churn detector + scan
queue manager + Loop A orchestrator, a `discovery` CLI command group, and comprehensive
deterministic tests covering AT-01 through AT-05 from the spec.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@docs/specs/SPEC-wallet-discovery-v1.md (frozen contract — the authority for all table schemas, state machine, and acceptance tests)
@docs/features/wallet-discovery-v1.md
@docs/ARCHITECTURE.md (ClickHouse = live writes; DuckDB = historical reads)
@CLAUDE.md (ClickHouse auth rule: CLICKHOUSE_PASSWORD env var, fail-fast, never hardcode)

<interfaces>
<!-- Existing repo patterns the executor must follow -->

From infra/clickhouse/initdb/ (naming convention):
- Files numbered sequentially: 01_init.sql, 02_tables.sql, ... 26_crypto_pair_events.sql
- Next file: 27_wallet_discovery.sql
- All tables in `polytool.` database schema
- Pattern: CREATE TABLE IF NOT EXISTS polytool.<name> (...) ENGINE = ...;
- Grafana read-only grants: GRANT SELECT ON polytool.<table> TO grafana_ro;

From packages/polymarket/silver_tape_metadata.py (ClickHouse HTTP write pattern):
```python
def write_to_clickhouse(row, *, host="localhost", port=8123, user="polytool_admin", password=""):
    # Uses urllib.request, Basic auth, JSONEachRow format
    query = "INSERT INTO polytool.<table> FORMAT JSONEachRow"
    url = f"http://{host}:{port}/?query={urllib.parse.quote(query)}"
    # POST with JSON body
```

From packages/polymarket/http_client.py:
```python
class HttpClient:
    def __init__(self, base_url, timeout=20.0, max_retries=5, backoff_factor=1.0, ...):
```

From polytool/__main__.py (CLI registration pattern):
```python
# 1. Add entrypoint alias at module level:
discovery_main = _command_entrypoint("tools.cli.discovery")

# 2. Add to _COMMAND_HANDLER_NAMES dict:
"discovery": "discovery_main",

# 3. Add help text in print_usage()
```

From tools/cli/ (CLI module pattern):
```python
def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(...)
    # subparsers for subcommands
    args = parser.parse_args(argv)
    # dispatch to handler
    return 0
```

Leaderboard API (from spec):
```
GET https://data-api.polymarket.com/v1/leaderboard
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: ClickHouse DDL + discovery models + lifecycle state machine</name>
  <files>
    infra/clickhouse/initdb/27_wallet_discovery.sql
    packages/polymarket/discovery/__init__.py
    packages/polymarket/discovery/models.py
    packages/polymarket/discovery/clickhouse_writer.py
  </files>
  <behavior>
    - Test: LifecycleState enum has exactly 8 values matching spec (discovered, queued, scanned, reviewed, promoted, watched, stale, retired)
    - Test: ReviewStatus enum has exactly 3 values (pending, approved, rejected)
    - Test: QueueState enum has exactly 5 values (pending, leased, done, failed, dropped)
    - Test: VALID_TRANSITIONS dict allows discovered->queued, queued->scanned, scanned->reviewed, reviewed->promoted (when review_status=approved), reviewed->retired, any->retired
    - Test: validate_transition("discovered", "promoted") raises InvalidTransitionError
    - Test: validate_transition("scanned", "promoted") raises InvalidTransitionError
    - Test: validate_transition("discovered", "discovered") raises InvalidTransitionError (discovered is entry-only)
    - Test: validate_transition("reviewed", "promoted") requires review_status="approved"
    - Test: WatchlistRow, LeaderboardSnapshotRow, ScanQueueRow dataclasses have all fields matching spec DDL
    - Test: dedup_key property produces "{source}:{wallet_address}" format
  </behavior>
  <action>
1. Create `infra/clickhouse/initdb/27_wallet_discovery.sql` with the exact DDL from the
   frozen spec for all three tables (`watchlist`, `leaderboard_snapshots`, `scan_queue`).
   Copy DDL verbatim from SPEC-wallet-discovery-v1.md. Add `GRANT SELECT ... TO grafana_ro`
   for each table, matching the convention in 25_tape_metadata.sql and 26_crypto_pair_events.sql.
   Prefix all tables with `polytool.` database schema.

2. Create `packages/polymarket/discovery/__init__.py` with standard exports.

3. Create `packages/polymarket/discovery/models.py` with:
   - `LifecycleState` enum (str, Enum) with 8 values matching spec Enum8 definitions
   - `ReviewStatus` enum (str, Enum) with 3 values
   - `QueueState` enum (str, Enum) with 5 values
   - `VALID_TRANSITIONS: dict[LifecycleState, set[LifecycleState]]` — encoding the exact
     allowed transitions from the spec state machine diagram. `reviewed -> promoted`
     additionally requires `review_status == "approved"` (enforced by validate_transition).
   - `InvalidTransitionError(ValueError)` exception
   - `validate_transition(current: LifecycleState, target: LifecycleState, review_status: ReviewStatus | None = None) -> None`
     raises InvalidTransitionError on invalid transitions with descriptive message.
   - `WatchlistRow` dataclass matching watchlist DDL columns
   - `LeaderboardSnapshotRow` dataclass matching leaderboard_snapshots DDL columns
   - `ScanQueueRow` dataclass matching scan_queue DDL columns, with `dedup_key` property
     returning `f"{self.source}:{self.wallet_address}"`

4. Create `packages/polymarket/discovery/clickhouse_writer.py` with:
   - `write_watchlist_rows(rows, *, host, port, user, password)` using urllib HTTP
     interface pattern from silver_tape_metadata.py (not clickhouse_connect). JSONEachRow
     format. Returns bool (True on success). Never raises.
   - `write_leaderboard_snapshot_rows(rows, *, host, port, user, password)` same pattern.
   - `write_scan_queue_rows(rows, *, host, port, user, password)` same pattern.
   - `read_latest_snapshot(order_by, time_period, category, *, host, port, user, password)`
     queries leaderboard_snapshots for the most recent snapshot_ts at the given key.
     Returns list of LeaderboardSnapshotRow. Uses HTTP GET with query param.
   - ClickHouse auth: password parameter required, no hardcoded default. Follow the
     CLAUDE.md rule: `if not password: raise ValueError("CLICKHOUSE_PASSWORD required")`.

All ClickHouse I/O is in clickhouse_writer.py. The models, lifecycle logic, and fetcher
are pure Python with no ClickHouse dependency, enabling deterministic testing.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/test_wallet_discovery.py -x -q --tb=short -k "lifecycle or model or transition or dedup_key"</automated>
  </verify>
  <done>
    - 27_wallet_discovery.sql exists with exact spec DDL for 3 tables + grafana_ro grants
    - models.py has LifecycleState (8), ReviewStatus (3), QueueState (5) enums
    - validate_transition rejects all spec-listed invalid transitions and allows valid ones
    - WatchlistRow, LeaderboardSnapshotRow, ScanQueueRow dataclasses match spec columns
    - clickhouse_writer.py has write/read functions using HTTP interface pattern
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Leaderboard fetcher + churn detector + scan queue manager + Loop A orchestrator + CLI wiring</name>
  <files>
    packages/polymarket/discovery/leaderboard_fetcher.py
    packages/polymarket/discovery/churn_detector.py
    packages/polymarket/discovery/scan_queue.py
    packages/polymarket/discovery/loop_a.py
    tools/cli/discovery.py
    polytool/__main__.py
  </files>
  <behavior>
    - Test AT-01: Mock leaderboard API returning 3 pages of 50 entries -> 150 entries returned, ordered rank 1-150, no duplicates, all have non-empty proxy_wallet
    - Test AT-02: Given snapshot T-1 [A,B,C] and T [B,C,D] at same key -> D is is_new=1, A is detected as dropped
    - Test AT-02b: Given snapshot T-1 [A(rank=5),B(rank=10)] and T [A(rank=2),B(rank=10)] -> A detected as rank improvement
    - Test AT-04 dedup: Two inserts with same dedup_key -> ScanQueueManager only yields one pending row
    - Test AT-04 lease: Leased item not returned by pending query while within TTL; after expiry, available for re-lease
    - Test AT-05: validate_transition("discovered", "promoted") raises InvalidTransitionError (already covered in Task 1 but exercised end-to-end here)
    - Test: Loop A orchestrator calls fetch -> churn -> enqueue in correct order (mock all I/O)
    - Test: Leaderboard fetcher stops pagination when empty page or max_pages reached
    - Test: Churn detector handles first-ever snapshot (no prior) by flagging all wallets as is_new=1
  </behavior>
  <action>
1. Create `packages/polymarket/discovery/leaderboard_fetcher.py`:
   - `fetch_leaderboard(order_by="PNL", time_period="DAY", category="OVERALL", max_pages=5, page_size=50, http_client=None) -> list[dict]`
   - Uses `packages/polymarket/http_client.HttpClient` (or accepts one as injection for
     testing). Base URL: `https://data-api.polymarket.com`.
   - Paginates: requests `/v1/leaderboard?order_by={order_by}&time_period={time_period}&limit={page_size}&offset={n*page_size}`
     (verify actual query params from the API — the spec says `GET .../v1/leaderboard`).
     Stop when: response is empty list, or max_pages reached.
   - Returns list of raw dicts preserving full API payload.
   - `to_snapshot_rows(raw_entries, fetch_run_id, snapshot_ts, order_by, time_period, category, prior_wallets=None) -> list[LeaderboardSnapshotRow]`
     converts raw dicts to typed rows, setting `is_new=1` if proxy_wallet not in prior_wallets set.

2. Create `packages/polymarket/discovery/churn_detector.py`:
   - `ChurnResult` dataclass: `new_wallets: list[str]`, `dropped_wallets: list[str]`, `persisting_wallets: list[str]`, `rising_wallets: list[tuple[str, int, int]]` (wallet, old_rank, new_rank where new < old)
   - `detect_churn(current_rows: list[LeaderboardSnapshotRow], prior_rows: list[LeaderboardSnapshotRow]) -> ChurnResult`
   - If prior_rows is empty (first-ever snapshot), all current wallets are new.
   - New = in current but not prior (by proxy_wallet). Dropped = in prior but not current.
   - Rising = in both, current rank < prior rank (lower rank number = better).

3. Create `packages/polymarket/discovery/scan_queue.py`:
   - `ScanQueueManager` class with in-memory state for testability, plus ClickHouse
     persistence methods:
   - `enqueue(wallet_address, source, priority=3, source_ref="") -> ScanQueueRow`
     Creates row with dedup_key=f"{source}:{wallet_address}", queue_state="pending".
     If a pending/leased item already exists for this dedup_key, returns existing (idempotent).
   - `lease(dedup_key, lease_owner, lease_duration_seconds=300) -> ScanQueueRow | None`
     Sets queue_state="leased", leased_at=now, lease_expires_at=now+duration.
   - `complete(dedup_key) -> ScanQueueRow | None` sets queue_state="done".
   - `fail(dedup_key, error_msg) -> ScanQueueRow | None` sets queue_state="failed",
     last_error=error_msg, increments attempt_count.
   - `get_pending(limit=10) -> list[ScanQueueRow]` returns pending items where
     available_at <= now, ordered by priority ASC then created_at ASC.
   - `requeue_expired_leases() -> int` finds leased items past lease_expires_at, resets
     to pending with incremented attempt_count. Returns count re-queued.
   - The manager operates on in-memory dicts for unit testing. A `flush_to_clickhouse()`
     method persists via clickhouse_writer. A `load_from_clickhouse()` hydrates from CH.

4. Create `packages/polymarket/discovery/loop_a.py`:
   - `run_loop_a(order_by="PNL", time_period="DAY", category="OVERALL", max_pages=5, ch_host="localhost", ch_port=8123, ch_user="polytool_admin", ch_password="", dry_run=False, http_client=None) -> LoopAResult`
   - `LoopAResult` dataclass: fetch_run_id, snapshot_ts, rows_fetched, churn (ChurnResult), rows_enqueued, dry_run
   - Orchestration: generate UUID fetch_run_id and snapshot_ts -> fetch leaderboard ->
     read prior snapshot from CH (or empty if first run or dry_run) -> detect churn ->
     build snapshot rows with is_new flags -> write snapshots to CH (unless dry_run) ->
     enqueue new wallets to scan_queue (unless dry_run) -> update watchlist with
     discovered state for new wallets (unless dry_run) -> return result.
   - Handles CH password via parameter. Fail-fast if not dry_run and password is empty.

5. Create `tools/cli/discovery.py`:
   - `main(argv) -> int` with argparse.
   - Subcommand: `run-loop-a` with flags: `--order-by` (default PNL), `--time-period`
     (default DAY), `--category` (default OVERALL), `--max-pages` (default 5),
     `--dry-run`, `--clickhouse-host`, `--clickhouse-port`, `--clickhouse-user`,
     `--clickhouse-password`.
   - Password falls back to `os.environ.get("CLICKHOUSE_PASSWORD")`. Fail-fast if empty
     and not dry-run.
   - Prints summary: rows fetched, new wallets, dropped wallets, rows enqueued.

6. Register in `polytool/__main__.py`:
   - Add `discovery_main = _command_entrypoint("tools.cli.discovery")` near the other entrypoints.
   - Add `"discovery": "discovery_main"` to `_COMMAND_HANDLER_NAMES`.
   - Add help text line in `print_usage()` under a new "--- Wallet Discovery ---" section.

7. Write ALL tests in `tests/test_wallet_discovery.py`:
   - AT-01 (leaderboard pagination): Build a mock HTTP handler returning 3 pages of 50
     entries. Call `fetch_leaderboard(max_pages=3, http_client=mock)`. Assert 150 entries,
     ordered rank 1-150, all have non-empty proxy_wallet. No real HTTP calls.
   - AT-02 (churn detection): Fixture snapshots T-1=[A,B,C] and T=[B,C,D]. Call
     detect_churn. Assert D is new, A is dropped, B and C are persisting.
   - AT-02b (rising detection): A improves from rank 5 to rank 2. Assert A in rising_wallets.
   - AT-02c (first-ever snapshot): No prior rows. All current wallets flagged as new.
   - AT-03 (snapshot idempotency): This is a ClickHouse-level MergeTree property, not
     testable without CH. Instead test that to_snapshot_rows produces identical output for
     identical input (determinism).
   - AT-04 dedup: Create ScanQueueManager in-memory. Enqueue 0xABC twice with same
     dedup_key. Assert only one pending item exists.
   - AT-04 lease: Enqueue, lease with 300s TTL. Assert not in get_pending(). Manually set
     lease_expires_at to past. Call requeue_expired_leases(). Assert item back in
     get_pending().
   - AT-05 (invalid lifecycle): Import validate_transition. Assert
     validate_transition("discovered", "promoted") raises InvalidTransitionError. Assert
     validate_transition("scanned", "promoted") raises InvalidTransitionError. Assert
     validate_transition("discovered", "discovered") raises InvalidTransitionError.
   - Loop A orchestrator test: Mock fetch_leaderboard, read_latest_snapshot (returns empty),
     and all CH writes. Call run_loop_a(dry_run=True). Assert churn result has all wallets
     as new. Assert result.rows_fetched > 0.
   - Pagination stop test: Mock returns empty page on page 2. Assert fetcher stops early
     with only page 1 results.

All tests are fully deterministic: no network, no ClickHouse, no clock dependency (inject
timestamps where needed), no randomness (inject UUIDs where needed).
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/test_wallet_discovery.py -x -v --tb=short</automated>
  </verify>
  <done>
    - AT-01 through AT-05 pass deterministically
    - Leaderboard fetcher paginates correctly and stops on empty page or max_pages
    - Churn detector identifies new, dropped, persisting, and rising wallets
    - ScanQueueManager enforces dedup and lease/expiry semantics in-memory
    - Loop A orchestrator wires fetch -> churn -> enqueue
    - CLI registered: `python -m polytool discovery run-loop-a --help` prints usage
    - `python -m polytool --help` lists `discovery` command
  </done>
</task>

<task type="auto">
  <name>Task 3: Regression check + dev log</name>
  <files>
    docs/dev_logs/2026-04-09_wallet_discovery_v1_impl_a.md
  </files>
  <action>
1. Run `python -m polytool --help` and confirm `discovery` appears in output.
2. Run `python -m polytool discovery run-loop-a --help` and confirm it prints usage.
3. Run `python -m pytest tests/test_wallet_discovery.py -v --tb=short` and record
   exact pass/fail counts.
4. Run `python -m pytest tests/ -x -q --tb=short` (full repo regression) and record
   counts. If any pre-existing failures, note them but do not fix unrelated tests.
5. Create `docs/dev_logs/2026-04-09_wallet_discovery_v1_impl_a.md` with:
   - Summary of what was built
   - Files created/modified (with brief rationale for each)
   - Commands run and output
   - Test results (targeted + regression)
   - Decisions made (e.g., why HTTP interface over clickhouse_connect, why in-memory
     queue manager for testability, etc.)
   - Open questions for next prompt (MVF implementation, scan --quick, etc.)
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m polytool --help | grep -q discovery && echo "PASS: discovery in help" || echo "FAIL: discovery missing"</automated>
  </verify>
  <done>
    - `python -m polytool --help` lists `discovery`
    - `python -m polytool discovery run-loop-a --help` works
    - All test_wallet_discovery.py tests pass
    - No regressions in existing tests
    - Dev log created at docs/dev_logs/2026-04-09_wallet_discovery_v1_impl_a.md
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Polymarket leaderboard API -> PolyTool | Untrusted external data: wallet addresses, usernames, PnL/volume numbers could be malformed |
| PolyTool -> ClickHouse HTTP | ClickHouse credentials cross process boundary via Basic auth over localhost HTTP |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-qeu-01 | Spoofing | leaderboard_fetcher | accept | Read-only fetch from public API; no auth token exposed. Data is informational, not used for execution. |
| T-qeu-02 | Tampering | leaderboard_snapshots | mitigate | Append-only MergeTree; no UPDATE/DELETE exposed. Raw payload preserved for audit. |
| T-qeu-03 | Information Disclosure | clickhouse_writer | mitigate | ClickHouse password read from env var only, never hardcoded. Basic auth over localhost only (no remote). |
| T-qeu-04 | Denial of Service | leaderboard_fetcher | mitigate | max_pages cap prevents unbounded pagination. HttpClient has timeout + retry limits. |
| T-qeu-05 | Elevation of Privilege | watchlist lifecycle | mitigate | validate_transition() rejects invalid state transitions at application layer. Human review gate enforced: scanned->promoted is rejected. |
</threat_model>

<verification>
1. `python -m pytest tests/test_wallet_discovery.py -v --tb=short` — all discovery tests pass
2. `python -m pytest tests/ -x -q --tb=short` — no regressions in existing tests
3. `python -m polytool --help` — shows `discovery` command
4. `python -m polytool discovery run-loop-a --help` — prints usage without error
5. `cat infra/clickhouse/initdb/27_wallet_discovery.sql` — contains all 3 table DDLs
</verification>

<success_criteria>
- Three ClickHouse table DDLs (watchlist, leaderboard_snapshots, scan_queue) match the frozen SPEC exactly
- Lifecycle state machine with validate_transition() rejects all spec-listed invalid transitions
- Leaderboard fetcher handles pagination, empty pages, and max_pages limit
- Churn detector identifies new, dropped, persisting, and rising wallets correctly
- Scan queue manager enforces dedup-by-key and lease/expiry semantics
- Loop A orchestrator chains fetch -> churn -> enqueue in one-shot
- CLI command `python -m polytool discovery run-loop-a` registered and functional
- All deterministic tests pass (AT-01 through AT-05 from spec, plus additional edge cases)
- No regressions in existing test suite
- Dev log created
</success_criteria>

<output>
After completion, create `.planning/quick/260409-qeu-implement-wallet-discovery-v1-storage-lo/260409-qeu-SUMMARY.md`
</output>
