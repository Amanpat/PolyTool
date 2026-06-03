---
title: Wi 4 Two Tier Watchlist
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-06-01_wi-4-two-tier-watchlist.md
last_synced: '2026-06-03T02:26:56Z'
lifecycle: reviewed
generator: repo-sync
---

# 2026-06-01 — WI-4 Two-Tier Watchlist + Promotion Criteria + CLI Review

**Packet:** WI-4 (Wallet-Ingestion v1 sprint). Scope: make the watchlist
two-tiered (system-owned `candidate` + operator-owned `locked`), add a
deterministic promotion-criteria / evidence-summary module (the WP-5 contract),
and add a `discovery review` dev/ops CLI that routes through the enforced human
gate. **No git commit, no live-CH DDL apply** (orchestrator handles both).

## Design fork resolutions

### Fork #1 — `source` column collision (RESOLVED: did NOT add a conflicting `source`)

The watchlist DDL already has `source String` meaning discovery **ORIGIN**
(`loop_a` / `manual` / `loop_d`). The packet's scope item 1 literally said add
`source` (auto|manual), which would clobber that meaning. I did **not** add a
conflicting `source`. Instead I added two new columns:

- `tier Enum8('candidate'=1, 'locked'=2) DEFAULT 'candidate'`
- `locked UInt8 DEFAULT 0`

Auto-vs-manual **OWNERSHIP** is derived from `locked=1` (and/or
`source='manual'`), not from a new `source` value. `source` keeps its ORIGIN
meaning untouched. `WatchlistRow` gained `tier="candidate"` and `locked=0`
fields **with defaults at the end of the dataclass** so the two existing
positional constructors (`loop_a.py`, `scan_worker.py`) stay valid.

### Fork #2 — match WI-3 `resolve_tier` contract (RESOLVED: names + values aligned)

WI-3's `resolve_tier(row)` (packages/research/scheduling/discovery_scheduler.py
lines ~155-202) reads, in order:

```python
locked_val = row.get("locked")
if locked_val in (1, "1", True, "true", "True"):
    return TIER_LOCKED            # "locked"
tier_val = row.get("tier")
if isinstance(tier_val, str) and tier_val.strip().lower() in (
    TIER_LOCKED, TIER_CANDIDATE, TIER_DISCOVERED, TIER_REST):
    return tier_val.strip().lower()
```

My columns use the **exact** names `tier` / `locked` and the **exact** values
`candidate` / `locked` that this resolver expects, so the scheduler starts
honoring real tiers with zero rework. Verified by
`TestResolveTierAlignment` in the new test file (a `build_candidate_row` dict
resolves to `candidate`; flipping `locked=1` resolves to `locked`).

## Exact ALTER statements for live CH (orchestrator applies — NOT run here)

```sql
ALTER TABLE polytool.watchlist
    ADD COLUMN IF NOT EXISTS tier Enum8('candidate' = 1, 'locked' = 2) DEFAULT 'candidate' AFTER source;
ALTER TABLE polytool.watchlist
    ADD COLUMN IF NOT EXISTS locked UInt8 DEFAULT 0 AFTER tier;
```

Idempotent (`IF NOT EXISTS`); existing rows default to `tier='candidate'`,
`locked=0`. Both the `CREATE TABLE` (fresh DBs) and these `ALTER`s live in
`infra/clickhouse/initdb/27_wallet_discovery.sql`.

## Evidence-summary module (the WP-5 contract)

Module: `packages/polymarket/discovery/evidence_summary.py`

```python
@dataclass(frozen=True)
class Evidence:
    wallet_address: str = ""
    realized_net_pnl: Optional[float] = None
    win_rate: Optional[float] = None
    trades: Optional[int] = None
    clv_coverage_rate: Optional[float] = None
    churn_triggered: bool = False
    @classmethod
    def from_dict(cls, data: dict) -> "Evidence": ...

def summarize_evidence(evidence: "Evidence | dict") -> str: ...
def is_candidate(evidence: "Evidence | dict", thresholds: Optional[dict] = None) -> bool: ...
def is_promotion_eligible(evidence: "Evidence | dict", thresholds: Optional[dict] = None) -> bool: ...
def load_promotion_config(config_path: Optional[Path] = None) -> dict: ...
```

`summarize_evidence` is the WP-5 contract: pure, deterministic (no clock, no
RNG, no I/O), stable field order. Example output:

```
+$24.0k PnL, 64% win / 180 trades, CLV 72%, churn-triggered
```

Missing dimensions are omitted (never fabricated); empty evidence returns
`"no evidence available"`. WP-5 should `from packages.polymarket.discovery.evidence_summary
import Evidence, summarize_evidence, is_promotion_eligible` and render the
candidate card from the returned string.

## Candidate thresholds + config path

Config: `config/watchlist_promotion.json` (operator-tunable, defensive-loaded;
defaults mirrored in code so behavior is identical with/without the file).

- `candidate_thresholds` (OR semantics — clear ANY one gate to enter candidate
  tier): `min_positions=20` (floor on metric gates), `min_realized_net_pnl=5000`,
  `min_win_rate=0.58`, `min_clv_coverage_rate=0.50`, `churn_qualifies=true`
  (churn-triggered alone qualifies).
- `promotion_eligibility` (AND semantics — advisory surfacing only, never
  advances state): `min_positions=50`, `min_realized_net_pnl=10000`,
  `min_win_rate=0.60`.

## Candidate auto-population

Module: `packages/polymarket/discovery/candidate_population.py`

- `build_candidate_row(evidence, ...)` → a CANDIDATE-tier `WatchlistRow`
  (`tier='candidate'`, `locked=0`, `lifecycle_state='scanned'`,
  `review_status='pending'`) carrying the evidence reason string.
- `plan_candidate_writes(evidences, snapshot, ...)` → keeps only wallets passing
  `is_candidate`, builds rows, then DROPS any whose wallet is locked in the
  current snapshot. Pure (no I/O).
- `populate_candidates(..., write_rows=callable)` → injects the write callable
  so it stays ClickHouse-free / offline-testable.

The WI-1 scan-worker advancer (`make_clickhouse_watchlist_advancer`) now writes
`tier='candidate'` rows and is guarded (see below).

## Locked immutability — how it is enforced

Single enforcement point in `candidate_population.py`:

- `is_locked_row(row)` — locked iff `locked` truthy OR `tier == 'locked'`.
- `locked_wallets(snapshot)` → set of locked wallet addresses.
- `filter_locked(rows, locked_set)` → drops locked-wallet rows before any write.
- `guard_not_locked(wallet, locked_set)` → raises `LockedImmutabilityError`.

Wired into every automated path:
- **Candidate population**: `plan_candidate_writes` filters locked wallets out.
- **Scan-worker advance**: `make_clickhouse_watchlist_advancer` first calls
  `read_watchlist_lock_state(wallet)` (new read helper) and SKIPS the write if
  the row is locked.
- **`discovery review` CLI**: refuses (exit 1, nothing written) if the target
  row is locked.

**Proof (acceptance gate 2):**
`TestLockedImmutability::test_locked_entry_byte_identical_after_full_cycle`
runs two full plan cycles (discovery + rescan) against a locked row with strong
evidence that WOULD overwrite it; both cycles produce zero writable rows and the
snapshot dict is asserted byte-identical (`snapshot[0] == locked_row`).

## Gate preservation — no auto-promote (acceptance gate 1)

- Auto-population only ever writes `lifecycle_state='scanned'`,
  `review_status='pending'` — fully inside the human gate. Asserted by
  `TestGateEnforcement::test_candidate_population_never_sets_approved`.
- The new `discovery review` CLI and its pure planner
  (`packages/polymarket/discovery/review.py :: plan_review`) route EVERY change
  through `validate_transition`. `--approve` sets `review_status='approved'` and
  advances `scanned->reviewed` (validated); promotion `reviewed->promoted` only
  happens with explicit `--promote` and is validated WITH
  `review_status='approved'` (the gate). `--deny` sets `rejected`, no advance.
- `TestGateEnforcement::test_no_auto_promote_from_discovered` and
  `TestReviewCLI::test_review_promote_from_discovered_refused_by_gate` prove the
  gate refuses an illegal jump (exit 1, nothing written).
- No code path sets `review_status='approved'` automatically.

## CLI

`python -m polytool discovery review --approve|--deny <wallet> [--promote]
[--dry-run] [--json]` — verified `discovery --help` lists `review`.

## Files created / modified

Created:
- `packages/polymarket/discovery/evidence_summary.py`
- `packages/polymarket/discovery/candidate_population.py`
- `packages/polymarket/discovery/review.py`
- `config/watchlist_promotion.json`
- `tests/test_wallet_discovery_two_tier.py`

Modified:
- `infra/clickhouse/initdb/27_wallet_discovery.sql` — CREATE adds `tier`/`locked`; idempotent ALTERs.
- `packages/polymarket/discovery/models.py` — `WatchlistRow.tier` / `.locked` (defaulted).
- `packages/polymarket/discovery/clickhouse_writer.py` — write tier/locked; `read_watchlist_lock_state`, `read_watchlist_row`.
- `packages/polymarket/discovery/scan_worker.py` — advancer writes candidate tier + locked guard.
- `tools/cli/discovery.py` — `review` subcommand + `_run_review`.

## Test results

- New: `tests/test_wallet_discovery_two_tier.py` — **38 passed**.
- Existing discovery suites: `test_wallet_discovery.py` + `test_wallet_discovery_integrated.py`
  + `test_discovery_scheduler.py` — **105 passed, 0 failed**.
- Full suite: **5342 passed, 1 skipped, 15 failed**. All 15 failures are in
  `tests/test_ris_*` (RIS marker-queue / acquire / monitoring CLI smoke tests),
  unrelated to WI-4. Confirmed PRE-EXISTING: stashing the discovery changes and
  rerunning `test_ris_marker_queue.py::...::test_index_done_json_output` still
  fails identically (`assert 1 == 0`). My changes touch only `discovery/`,
  `tools/cli/discovery.py`, the DDL, config, and the new test — none imported by
  the RIS CLI paths.

## Codex review tier

`models.py` and the watchlist are research-side (not execution/kill-switch/
signing). Per CLAUDE.md Codex policy this is **Recommended** (not Mandatory).
Recommend `/codex:review --background` on the new discovery modules.

## Open risks

- `read_watchlist_lock_state` / `read_watchlist_row` issue one extra CH read per
  scanned wallet on the worker advance path; negligible at current volumes.
- The DDL ALTERs are reported here and written into initdb but NOT applied to
  live CH (per packet, orchestrator applies deliberately after WI-2 migration-gate
  incident).
