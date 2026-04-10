---
phase: 260410-gop
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tests/test_wallet_discovery_integrated.py
  - docs/features/wallet-discovery-v1.md
autonomous: true
requirements: [AT-01, AT-02, AT-03, AT-04, AT-05, AT-06, AT-07]
must_haves:
  truths:
    - "Full Loop A path (fetch -> snapshot -> churn -> queue) works end-to-end with in-memory stubs"
    - "Re-running Loop A with identical input is idempotent (no duplicate queue entries)"
    - "scan --quick dossier.json contains stable mvf key with 11 dimensions and metadata"
    - "scan --quick makes zero HTTP calls to any cloud LLM endpoint"
    - "Null maker_taker_ratio handled gracefully in integrated dossier output"
    - "Lifecycle state machine rejects scanned->promoted (human review gate enforced)"
  artifacts:
    - path: "tests/test_wallet_discovery_integrated.py"
      provides: "Integrated acceptance tests covering full v1 path"
      min_lines: 200
  key_links:
    - from: "packages/polymarket/discovery/leaderboard_fetcher.py"
      to: "packages/polymarket/discovery/churn_detector.py"
      via: "to_snapshot_rows output feeds detect_churn input"
      pattern: "detect_churn.*current_snapshot_rows"
    - from: "packages/polymarket/discovery/churn_detector.py"
      to: "packages/polymarket/discovery/scan_queue.py"
      via: "ChurnResult.new_wallets feeds ScanQueueManager.enqueue"
      pattern: "enqueue.*wallet.*loop_a"
    - from: "tools/cli/scan.py"
      to: "packages/polymarket/discovery/mvf.py"
      via: "compute_mvf called on --quick path with positions list"
      pattern: "compute_mvf.*positions.*proxy_wallet"
---

<objective>
Harden Wallet Discovery v1 with integrated acceptance tests that validate the
frozen v1 contract end-to-end on deterministic fixtures. No new product scope.

Purpose: Prove the full v1 path works as a cohesive system, not just at the
unit level. Existing tests (test_wallet_discovery.py, test_mvf.py,
test_scan_quick_mode.py) cover individual AT-01..AT-07 contracts per component.
This plan adds integration-level tests that thread the entire flow together:
leaderboard fetch -> snapshot -> churn -> queue -> scan --quick -> MVF output.

Output: tests/test_wallet_discovery_integrated.py with all integrated acceptance
tests passing. Feature doc updated if any wording is inaccurate vs shipped behavior.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@docs/specs/SPEC-wallet-discovery-v1.md
@docs/features/wallet-discovery-v1.md
@packages/polymarket/discovery/__init__.py
@packages/polymarket/discovery/models.py
@packages/polymarket/discovery/leaderboard_fetcher.py
@packages/polymarket/discovery/churn_detector.py
@packages/polymarket/discovery/scan_queue.py
@packages/polymarket/discovery/loop_a.py
@packages/polymarket/discovery/mvf.py
@tools/cli/scan.py
@tests/test_wallet_discovery.py
@tests/test_mvf.py
@tests/test_scan_quick_mode.py

<interfaces>
<!-- Key types and contracts the executor needs. Extracted from codebase. -->

From packages/polymarket/discovery/__init__.py:
```python
from packages.polymarket.discovery.models import (
    LifecycleState, ReviewStatus, QueueState,
    InvalidTransitionError, validate_transition,
    WatchlistRow, LeaderboardSnapshotRow, ScanQueueRow,
)
from packages.polymarket.discovery.mvf import compute_mvf, MvfResult, mvf_to_dict
```

From packages/polymarket/discovery/leaderboard_fetcher.py:
```python
def fetch_leaderboard(
    order_by="PNL", time_period="DAY", category="OVERALL",
    max_pages=5, page_size=50, http_client=None,
) -> list[dict]: ...

def to_snapshot_rows(
    raw_entries, fetch_run_id, snapshot_ts, order_by, time_period, category,
    prior_wallets=None,
) -> list[LeaderboardSnapshotRow]: ...
```

From packages/polymarket/discovery/churn_detector.py:
```python
@dataclass
class ChurnResult:
    new_wallets: list[str]
    dropped_wallets: list[str]
    persisting_wallets: list[str]
    rising_wallets: list[tuple[str, int, int]]

def detect_churn(current_rows, prior_rows) -> ChurnResult: ...
```

From packages/polymarket/discovery/scan_queue.py:
```python
class ScanQueueManager:
    def enqueue(self, wallet_address, source, priority=3, source_ref="") -> ScanQueueRow: ...
    def lease(self, dedup_key, lease_owner, lease_duration_seconds=300) -> Optional[ScanQueueRow]: ...
    def complete(self, dedup_key) -> Optional[ScanQueueRow]: ...
    def fail(self, dedup_key, error_msg) -> Optional[ScanQueueRow]: ...
    def get_pending(self, limit=10) -> list[ScanQueueRow]: ...
    def requeue_expired_leases(self) -> int: ...
```

From packages/polymarket/discovery/loop_a.py:
```python
@dataclass
class LoopAResult:
    fetch_run_id: str
    snapshot_ts: datetime
    rows_fetched: int
    churn: ChurnResult
    rows_enqueued: int
    dry_run: bool

def run_loop_a(
    order_by="PNL", time_period="DAY", category="OVERALL", max_pages=5,
    ch_host="localhost", ch_port=8123, ch_user="polytool_admin", ch_password="",
    dry_run=False, http_client=None,
    fetch_run_id=None, snapshot_ts=None,
) -> LoopAResult: ...
```

From packages/polymarket/discovery/mvf.py:
```python
@dataclass
class MvfResult:
    dimensions: Dict[str, Optional[float]]
    metadata: Dict[str, Any]

def compute_mvf(positions: list[dict], wallet_address: str) -> MvfResult: ...
def mvf_to_dict(result: MvfResult) -> Dict[str, Any]: ...
```

From tools/cli/scan.py (relevant functions):
```python
def build_parser() -> argparse.ArgumentParser: ...
def build_config(args: argparse.Namespace) -> Dict[str, Any]: ...
def apply_scan_defaults(args, argv) -> argparse.Namespace: ...
def run_scan(config, argv, started_at) -> None: ...
LITE_PIPELINE_STAGE_SET: frozenset
FULL_PIPELINE_STAGE_SET: frozenset
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create integrated acceptance test suite for full v1 path</name>
  <files>tests/test_wallet_discovery_integrated.py</files>
  <action>
Create a new test file `tests/test_wallet_discovery_integrated.py` with the following
integrated acceptance tests. All tests must be fully deterministic (no network, no
ClickHouse, no clock dependency). Use injected timestamps, UUIDs, in-memory
ScanQueueManager, and mocked http_client fixtures.

**Shared fixtures** (module-level):
- A 3-page leaderboard fixture (150 entries) with distinct `proxy_wallet` and `rank`
  fields, built by a `_build_leaderboard_pages()` helper (reuse the pattern from
  test_wallet_discovery.py `_build_page` but produce 3 pages of 50).
- A pinned `snapshot_ts = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)` and
  `fetch_run_id = "integrated-run-001"`.
- A 12-position dossier fixture (same as test_scan_quick_mode.py `_POSITIONS_FIXTURE`)
  including WIN, LOSS, PROFIT_EXIT, LOSS_EXIT, PENDING outcomes with NO maker/taker
  fields (to test graceful null handling).

**Test class 1: TestIntegratedLoopAPath** — End-to-end Loop A flow:
1. `test_fetch_to_churn_to_queue_full_flow`: Using mocked http_client returning 3
   leaderboard pages (150 entries), call `fetch_leaderboard()`, then
   `to_snapshot_rows()` with no prior wallets (first run), then `detect_churn()`
   comparing current vs empty prior. Assert: (a) 150 entries fetched, (b) all 150
   flagged as new_wallets in churn result, (c) feeding all new_wallets into a fresh
   `ScanQueueManager.enqueue()` produces 150 pending items, (d) each queue item has
   `source="loop_a"` and `queue_state=QueueState.pending`.

2. `test_churn_detects_new_and_dropped_in_second_run`: Build a T-1 snapshot of 150
   wallets. Build a T snapshot where 5 wallets are replaced by 5 new ones (wallets
   146-150 replaced by wallets 151-155). Run `detect_churn()`. Assert: (a) exactly 5
   new_wallets, (b) exactly 5 dropped_wallets, (c) exactly 145 persisting_wallets.

3. `test_queue_idempotency_on_rerun`: Enqueue 10 wallets. Re-enqueue the same 10
   wallets. Assert: `get_pending()` returns exactly 10 items (not 20). Confirm each
   `dedup_key` appears exactly once.

4. `test_snapshot_idempotency_same_input`: Call `to_snapshot_rows()` twice with identical
   `(raw_entries, fetch_run_id, snapshot_ts, order_by, time_period, category, prior_wallets)`.
   Assert: both calls produce byte-identical lists (same length, same field values on
   each row including `is_new` flags).

**Test class 2: TestIntegratedScanQuickMvf** — Scan --quick -> MVF integration:
5. `test_quick_scan_dossier_mvf_shape`: Run `scan.run_scan()` with `config["quick"]=True`
   and mocked `post_json` (same pattern as test_scan_quick_mode.py). After completion,
   load `dossier.json` from the run_root. Assert: (a) `"mvf"` key present, (b)
   `dossier["mvf"]["dimensions"]` has exactly 11 keys, (c) all dimension keys match
   the spec names (win_rate, avg_hold_duration_hours, median_entry_price,
   market_concentration, category_entropy, avg_position_size_usdc,
   trade_frequency_per_day, late_entry_rate, dca_score, resolution_coverage_rate,
   maker_taker_ratio), (d) `dossier["mvf"]["metadata"]["input_trade_count"]` equals the
   fixture length, (e) `dossier["mvf"]["metadata"]["wallet_address"]` is set.

6. `test_quick_scan_null_maker_taker_graceful`: Same scan setup as above but fixture has
   NO maker/taker fields. Assert: `dossier["mvf"]["dimensions"]["maker_taker_ratio"]`
   is None (JSON null). Assert `"maker_taker_data_unavailable"` is in
   `dossier["mvf"]["metadata"]["data_notes"]`.

7. `test_quick_scan_no_llm_calls_request_intercept`: Run `scan.run_scan()` with
   `config["quick"]=True` and a request-intercepting `post_json` mock that logs all
   outbound URLs. Assert: zero URLs contain any LLM provider domain string
   ("gemini", "deepseek", "openai", "anthropic", "googleapis",
   "generativelanguage", "api.openai", "api.anthropic"). This is a request-level
   interception, not code-path inspection.

8. `test_quick_scan_no_mvf_without_quick_flag`: Run `scan.run_scan()` with
   `config["quick"]=False`. Assert `"mvf"` key is NOT in dossier.json.

**Test class 3: TestIntegratedLifecycleGate** — Human review gate enforcement:
9. `test_full_lifecycle_happy_path`: Walk a wallet through
   discovered -> queued -> scanned -> reviewed -> promoted, calling
   `validate_transition()` at each step. The reviewed -> promoted step must pass
   `review_status=ReviewStatus.approved`. Assert: no exception raised.

10. `test_scanned_to_promoted_blocked_without_review`: Attempt
    `validate_transition(scanned, promoted)`. Assert: `InvalidTransitionError` raised
    with message containing "scanned" and "promoted".

11. `test_reviewed_to_promoted_blocked_without_approval`: Attempt
    `validate_transition(reviewed, promoted, review_status=ReviewStatus.pending)`.
    Assert: `InvalidTransitionError` raised with message containing "approved".

**Test class 4: TestIntegratedLoopAOrchestrator** — run_loop_a() as black box:
12. `test_loop_a_dry_run_full_integration`: Call `run_loop_a(dry_run=True)` with a
    mocked http_client returning 2 pages of 50 entries. Inject `fetch_run_id` and
    `snapshot_ts`. Assert: (a) result.rows_fetched == 100, (b) result.churn.new_wallets
    has 100 entries (first run, no prior), (c) result.dry_run is True, (d)
    result.rows_enqueued == 0 (dry_run skips writes).

Use `monkeypatch` and `tmp_path` pytest fixtures. Use `os.chdir` with try/finally for
scan tests (same pattern as test_scan_quick_mode.py). Import from
`packages.polymarket.discovery.*` and `tools.cli.scan` directly.

Do NOT: add any test that requires network, ClickHouse, clock, or randomness.
Do NOT: test Loop B, C, D, insider scoring, or LLM paths.
Do NOT: add any production code changes unless a test exposes a real contract mismatch
(in which case fix the minimal code and document the fix in the test docstring).
  </action>
  <verify>
    <automated>python -m pytest tests/test_wallet_discovery_integrated.py -v --tb=short -x</automated>
  </verify>
  <done>
All 12 integrated acceptance tests pass deterministically. The full v1 path
(leaderboard fetch -> snapshot -> churn -> queue -> scan --quick -> MVF) is proven
end-to-end on deterministic fixtures. No external service dependencies.
  </done>
</task>

<task type="auto">
  <name>Task 2: Verify existing tests still pass and update feature doc if needed</name>
  <files>docs/features/wallet-discovery-v1.md</files>
  <action>
1. Run the full existing test suite for the discovery area:
   `python -m pytest tests/test_wallet_discovery.py tests/test_mvf.py tests/test_scan_quick_mode.py tests/test_wallet_discovery_integrated.py -v --tb=short`
   All tests must pass with zero failures.

2. Read the current `docs/features/wallet-discovery-v1.md` and verify every
   statement matches shipped behavior. Specifically check:
   - The "Implementation" section references correct commit hashes and test counts.
   - The "What v1 Covers" section accurately describes the 4 capabilities.
   - The "Human Review Gate" section accurately describes the lifecycle enforcement.
   - The "CLI Surface" section shows correct command syntax.

3. If any wording is inaccurate vs actual shipped behavior, make the minimal
   correction. Examples of corrections that ARE in scope:
   - Test count update (if integration adds to the total touched-area count).
   - Adding a line about integrated acceptance tests under the Implementation section.
   Do NOT add new feature scope, Loop B/C/D references, or LLM path descriptions.

4. Run the project-wide smoke test to confirm no regressions:
   `python -m polytool --help`
   `python -m pytest tests/ -x -q --tb=short` (stop at first failure, report counts)
  </action>
  <verify>
    <automated>python -m pytest tests/test_wallet_discovery.py tests/test_mvf.py tests/test_scan_quick_mode.py tests/test_wallet_discovery_integrated.py -v --tb=short</automated>
  </verify>
  <done>
All discovery-area tests pass (existing + new integrated). Feature doc is accurate
vs shipped behavior. Project-wide smoke test shows no regressions. Exact test count
reported.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Leaderboard API -> fetch_leaderboard | Untrusted external HTTP data enters the pipeline |
| scan CLI -> dossier.json | File I/O writes user-facing artifacts |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-gop-01 | S (Spoofing) | Leaderboard API mock | accept | Tests use deterministic fixtures; no real API in scope |
| T-gop-02 | T (Tampering) | dossier.json write | accept | Test-only scope; production write path already validated in AT-06/AT-07 |
| T-gop-03 | I (Information Disclosure) | Test fixtures | accept | Fixtures use synthetic data only; no real wallet addresses |
| T-gop-04 | E (Elevation of Privilege) | Lifecycle gate bypass | mitigate | Test 10/11 explicitly verify scanned->promoted and reviewed->promoted-without-approval are rejected by validate_transition() |
</threat_model>

<verification>
1. `python -m pytest tests/test_wallet_discovery_integrated.py -v --tb=short -x` — all 12 tests pass
2. `python -m pytest tests/test_wallet_discovery.py tests/test_mvf.py tests/test_scan_quick_mode.py -v --tb=short` — existing 106+ tests still pass
3. `python -m polytool --help` — CLI loads without import errors
4. `python -m pytest tests/ -x -q --tb=short` — full suite, no regressions
</verification>

<success_criteria>
- 12 new integrated acceptance tests pass deterministically in tests/test_wallet_discovery_integrated.py
- Full v1 path proven: leaderboard fetch -> snapshot rows -> churn detection -> queue insert -> scan --quick -> MVF output
- Re-run idempotency verified for snapshots and queue
- No-LLM guarantee verified via request interception on --quick scans
- Null maker_taker_ratio handled gracefully in integrated output
- Human review gate (scanned->promoted rejection) proven in integrated context
- All existing tests continue to pass (zero regressions)
- Feature doc accurate vs shipped behavior
</success_criteria>

<output>
After completion, create `.planning/quick/260410-gop-harden-wallet-discovery-v1-with-integrat/260410-gop-SUMMARY.md`
</output>
