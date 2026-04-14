# Gate 2 Next-Step Packet

**Date:** 2026-04-14
**Task:** quick-260414-rez
**Status:** COMPLETE

---

## Verdict: RESUME_CRYPTO_CAPTURE

### Evidence

1. **crypto-pair-watch output (2026-04-14T23:48:36+00:00):**

   ```
   [crypto-pair-watch] eligible_now : yes
   [crypto-pair-watch] total_eligible: 12
   [crypto-pair-watch] by_symbol     : BTC=4 ETH=4 SOL=4
   [crypto-pair-watch] by_duration   : 5m=12 15m=0
   [crypto-pair-watch] checked_at    : 2026-04-14T23:48:36+00:00
   [crypto-pair-watch] next_action   : Run: python -m polytool crypto-pair-scan (then crypto-pair-run when ready)
   [crypto-pair-watch] Bundle written: artifacts\crypto_pairs\watch\2026-04-14\0b25c0fcce4d
   ```

   12 active 5m markets confirmed: BTC=4, ETH=4, SOL=4. All are 5m duration.

2. **Current corpus status:**
   - Recovery corpus: 40/50 qualifying tapes (crypto = 0/10 blocked since 2026-03-29)
   - Gate 2 last run: FAILED (7/50 = 14%) on 2026-03-29 against 50-tape corpus
   - Root cause: Silver tapes produce zero fills (no L2 book data);
     crypto 5m Gold tapes were 7/10 positive (strongest bucket)
   - See: docs/dev_logs/2026-04-14_gate2_fill_diagnosis.md

3. **ADR escalation deadline status:**
   - Deadline: 2026-04-12 (14 calendar days from 2026-03-29)
   - Today: 2026-04-14 (2 days past deadline)
   - ADR: docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md
   - **Outcome:** Deadline passed but crypto markets are now active. WAIT_FOR_CRYPTO
     policy remains appropriate per ADR escalation criterion #1: markets have returned,
     so the time threshold condition is not fully satisfied (markets ARE available).
     No benchmark_v2 decision is required at this time.

---

## Execution Packet: Resume Crypto Gold Capture

Crypto 5m markets are active (12 markets: BTC=4, ETH=4, SOL=4). Resume the Gold
capture campaign to fill the crypto=10 bucket shortage.

### Prerequisites

Confirm before capture:
- Docker running: `docker compose ps`
- ClickHouse accessible: `curl "http://localhost:8123/?query=SELECT%201"`
- CLICKHOUSE_PASSWORD set: `echo $CLICKHOUSE_PASSWORD`
- CLI loads: `python -m polytool --help`

### Step 1 — Check active market slugs

```bash
python -m polytool crypto-pair-watch
```

This returns the current list of active 5m BTC/ETH/SOL pair market slugs.
As of 2026-04-14: 12 active markets (BTC=4, ETH=4, SOL=4).

To get the actual slugs for use in capture commands:

```bash
python -m polytool crypto-pair-scan
```

### Step 2 — Capture Gold tapes

For each active crypto 5m market slug (from crypto-pair-scan output), run a shadow
session to capture a Gold tape. Target 12-15 sessions total to ensure 10+ qualify.

```bash
# Capture one tape per active market (repeat for 12-15 sessions total)
python -m polytool simtrader shadow \
    --market <SLUG> \
    --strategy market_maker_v1 \
    --duration 600 \
    --record-tape \
    --tape-dir "artifacts/tapes/gold/crypto_<SLUG>_$(date -u +%Y%m%dT%H%M%SZ)"
```

Replace `<SLUG>` with each slug from crypto-pair-scan. Distribute across BTC, ETH, and
SOL slugs for diversity.

### Step 3 — Batch qualification check

After each capture batch (5+ tapes), check which qualify:

```bash
python tools/gates/qualify_gold_batch.py \
    --tape-dirs artifacts/tapes/gold/crypto_*
```

This reports which new tapes qualify for the crypto bucket and how many more are needed.

### Step 4 — Full corpus audit (when batch looks good)

When qualify_gold_batch.py shows >= 10 qualifying crypto tapes:

```bash
python tools/gates/corpus_audit.py \
    --tape-roots artifacts/tapes/gold \
    --tape-roots artifacts/tapes/silver \
    --tape-roots artifacts/tapes/shadow \
    --out-dir artifacts/corpus_audit \
    --manifest-out config/recovery_corpus_v1.tape_manifest
```

### Stopping Condition

When corpus_audit.py exits 0 (50/50 qualifying tapes including crypto=10), run Gate 2:

```bash
python tools/gates/run_recovery_corpus_sweep.py \
    --manifest config/recovery_corpus_v1.tape_manifest \
    --out artifacts/gates/mm_sweep_gate \
    --threshold 0.70
```

Or equivalently (if close_mm_sweep_gate.py is available):

```bash
python tools/gates/close_mm_sweep_gate.py \
    --benchmark-manifest config/recovery_corpus_v1.tape_manifest \
    --out artifacts/gates/gate2_sweep
```

Gate 2 passes when >= 70% of tapes show positive net PnL after fees and
realistic-retail assumptions.

### Capture target summary

| Bucket | Status | Target |
|--------|--------|--------|
| politics | COMPLETE (10/10) | No action needed |
| sports | COMPLETE (15/15) | No action needed |
| near_resolution | COMPLETE (10/10) | No action needed |
| new_market | COMPLETE (5/5) | No action needed |
| crypto | INCOMPLETE (0/10) | **Capture 12-15 sessions from active 5m markets** |

### ADR Deadline Note

The ADR escalation deadline (2026-04-12) has passed, but crypto markets are now active
(12 markets confirmed on 2026-04-14). Per ADR-benchmark-versioning-and-crypto-unavailability.md
escalation criterion #1, the time threshold condition requires markets to remain absent AND
no pending return announcement. Since markets have returned, WAIT_FOR_CRYPTO policy remains
valid. Capture should proceed immediately.

If markets go offline again before 10 crypto tapes are captured, re-evaluate benchmark_v2
at that point per the ADR escalation criteria.

---

## Open Questions

1. Should CURRENT_STATE.md Gate 2 section be updated to reflect the current
   verdict and date? (Answer: yes, Task 2 handles this.)

## Files Changed

| File | Action |
|------|--------|
| docs/dev_logs/2026-04-14_gate2_next_step_packet.md | Created -- this file |

## Codex Review

Tier: Skip (docs-only, no execution paths).
