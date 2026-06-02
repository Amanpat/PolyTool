---
type: architecture
tags: [architecture, tapes, status/done]
created: 2026-04-08
---

# Tape Tiers

Source: roadmap "Tape Library Tiers" + CLAUDE.md tape tier definitions + audit Section 1.

Every tape-driven result must preserve tier metadata. Do not treat Bronze or coarse price-only data as equivalent to Gold.

---

## Tier Definitions

| Tier | Source | Granularity | Use Case | Available |
|------|--------|-------------|----------|-----------|
| **Gold** | Live Tape Recorder | Tick-level, ms | Microstructure, A-S calibration, Gate 3 | Accumulates from now |
| **Silver** | pmxt + Jon-Becker + polymarket-apis reconstruction | ~2 min effective | Strategy PnL, Gate 2, autoresearch | After bulk import |
| **Bronze** | Jon-Becker raw trades only | Trade-level, no book | Category analysis, κ MLE | After download |

### Gold

- Highest-fidelity source
- Live tape recorder output from Polymarket WebSocket stream
- Tick-level millisecond resolution
- Required for Gate 3 shadow validation
- Required for Avellaneda-Stoikov calibration
- Code: `packages/polymarket/simtrader/tape/recorder.py` (300 lines)

### Silver

- Reconstructed from three free data sources: pmxt archive + Jon-Becker dataset + polymarket-apis 2-min price bars
- Good for Gate 2 parameter sweep and autoresearch benchmarks
- Tagged `source='reconstructed'`, `reconstruction_confidence='medium'`
- Code: `packages/polymarket/silver_reconstructor.py` (877 lines)

### Bronze

- Jon-Becker raw trades only (trade-level, no orderbook state)
- Lower fidelity — no book reconstruction possible
- Useful for category analysis and κ MLE calibration
- NOT suitable for full SimTrader replay (no book events to drive fills)

---

## Artifacts Directory Layout

All tapes live under `artifacts/tapes/` organized by tier. Never create tape directories elsewhere. (From CLAUDE.md)

```
artifacts/tapes/
  gold/          # Live tape recorder output (highest fidelity)
  silver/        # Reconstructed from pmxt + Jon-Becker + polymarket-apis
  bronze/        # Jon-Becker raw trade tapes
  crypto/        # Crypto pair bot recordings
  shadow/        # Shadow mode run tapes
```

Other artifacts:
```
artifacts/gates/
  gate2_sweep/   # MM parameter sweep results
  gate3_shadow/  # Shadow validation
  manifests/     # Tape manifests
artifacts/simtrader/
  runs/          # Replay runs
  sweeps/        # Parameter sweeps
  ondemand_sessions/
```

---

## Benchmark Tape Set (benchmark_v1)

- **FINALIZED 2026-03-21 — DO NOT MODIFY**
- 50 tapes across 5 buckets: politics=10, sports=15, crypto=10, near_resolution=10, new_market=5
- Files: `config/benchmark_v1.tape_manifest`, `config/benchmark_v1.lock.json`, `config/benchmark_v1.audit.json`
- All autoresearch experiments and Gate 2 sweeps reference this fixed manifest
- Recovery corpus: `config/recovery_corpus_v1.tape_manifest` (50 tapes, all qualifying paths)

---

## Tape Integrity Audit (2026-03-29)

- 314 tapes scanned: gold=8, silver=118, shadow=181, crypto_new=7
- Verdict: **SAFE_TO_USE** — zero YES/NO token-ID mapping bugs, zero structural corruption
- Artifact: `artifacts/debug/tape_integrity_audit_report.md`

---

## Cross-References

- [[SimTrader]] — Uses tapes for replay, shadow, and sweep runs
- [[Database-Rules]] — ClickHouse stores tape metadata, DuckDB reads Parquet
- [[Risk-Framework]] — Gate 2 requires Silver tapes, Gate 3 requires Gold tapes
- [[Data-Stack]] — Five free layers that produce tapes
