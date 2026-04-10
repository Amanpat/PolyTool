# 2026-04-10 — Wallet Discovery v1 Truth Sync and Release Checklist

**Task**: quick-260410-ii8
**Status**: COMPLETE

## Objective

Truth-sync authoritative docs so Wallet Discovery v1 is no longer described as
"pending" and create (or enhance) a release-readiness runbook for use in research
workflows. Done when repo docs no longer say Wallet Discovery v1 is "implementation
pending" and there is a concise go/no-go checklist for using v1 in research.

---

## What Was Changed

### 1. `docs/CURRENT_STATE.md`
- Section heading changed from `Wallet Discovery v1 (Spec Frozen, 2026-04-09)`
  to `Wallet Discovery v1 (Shipped, 2026-04-10)`.
- Body updated: removed "contract is frozen as a docs-only spec" and
  "Implementation is pending." Replaced with implemented/integrated/hardened
  language including commit references (83832e1, 724a23c), test counts
  (118 discovery-area tests, 3908 full suite).
- Added `**Runbook**: docs/runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md` link.
- Kept deferred scope paragraph (B/C/D, insider scoring, auto-promotion, n8n)
  and spec/feature doc links unchanged.

### 2. `docs/ROADMAP.md`
- Section heading changed from `### Wallet Discovery v1 [SPEC FROZEN]` to
  `### Wallet Discovery v1 [SHIPPED]`.
- All 4 checklist items changed from `- [ ]` to `- [x]`:
  - Loop A: leaderboard fetcher + churn detection + scan queue
  - ClickHouse tables: watchlist, leaderboard_snapshots, scan_queue
  - Unified `polytool scan <address>` with `--quick` (no-LLM guarantee)
  - MVF computation (11-dim, Python math only)
- Added shipped date and test counts after the checklist.
- Kept Spec link, Acceptance line, and Deferred block unchanged.

### 3. `docs/INDEX.md`
- Features table: Wallet Discovery v1 row description changed from
  "Spec frozen: ..." to "Shipped: ...".
- Workflows table: added new row for
  `WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md` as the go/no-go runbook.

### 4. `docs/runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md`
- **Pre-existing file** — discovered during execution. Already a comprehensive
  operator runbook created during the acceptance hardening pass.
- Enhanced (not replaced) with 4 new sections:
  - **What Is Shipped** — explicit shipped scope summary with test count
  - **CLI Entrypoints** — quick-reference command block for Loop A and scan
  - **No-LLM Guarantee** — dedicated section with enforcement detail (AT-06)
  - **Known Non-Blocking Issues** — pre-existing RIS cloud-provider test failures
    and `late_entry_rate` null gap documented as non-blocking
  - **Go/No-Go Checklist** — 7-step operator checklist before research use
  - Renamed Section 6 from "What v1 Does NOT Cover" to
    "What Is Explicitly Not Shipped" for search/grep consistency.

---

## What Was NOT Changed

| Item | Reason |
|------|--------|
| `docs/specs/SPEC-wallet-discovery-v1.md` | Frozen spec — point-in-time contract snapshot, not a living status doc. Still says "Implementation is pending" in its own Status section; this is correct for a frozen spec. The feature doc is the live status source. |
| `docs/features/wallet-discovery-v1.md` | Already accurate from integration and hardening passes. |
| `docs/PLAN_OF_RECORD.md` | No policy changes needed. |
| All code, tests, migrations, workflows | Docs-only task — zero code changes. |

---

## Verification

### Command and output:
```bash
grep -rn "implementation.*pending|Implementation is pending|SPEC FROZEN" \
  docs/CURRENT_STATE.md docs/ROADMAP.md docs/INDEX.md
# Exit 1 — no matches found (desired outcome)
```

Run during execution — confirmed exit code 1 (zero stale matches).

### Runbook section count:
```bash
grep -c "Go/No-Go|What Is Shipped|What Is Explicitly Not|Prerequisites|CLI Entrypoints|No-LLM Guarantee|Human Review Gate|Known Non-Blocking" \
  docs/runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md
# Result: 8 (required >= 8)
```

### ROADMAP checked items:
```bash
grep -A 8 "Wallet Discovery v1" docs/ROADMAP.md | grep -c "\[x\]"
# Result: 4
```

### INDEX.md runbook row:
```bash
grep "WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK" docs/INDEX.md
# Returns: one matching line
```

---

## Decisions Made

1. **Used existing runbook rather than creating duplicate.** The acceptance hardening
   pass had already created `WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md`. Creating a
   second `WALLET_DISCOVERY_V1_RUNBOOK.md` would be file bloat. Enhanced the existing
   file instead; updated INDEX.md to point to the correct path.

2. **Frozen spec not updated.** `SPEC-wallet-discovery-v1.md` still contains
   "Implementation is pending" in its own Status block. This is intentional — specs are
   point-in-time contracts, not living status trackers. The feature doc at
   `docs/features/wallet-discovery-v1.md` is the authoritative living status source.

---

## Remaining Gaps

None — all targeted docs are now consistent with the shipped state. The frozen spec's
internal Status section remains "pending" by design (it is a historical artifact of the
spec being written before implementation).

---

## Codex Review

Skip — docs-only task, no execution layer touched.
