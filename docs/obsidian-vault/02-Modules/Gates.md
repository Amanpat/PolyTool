---
type: module
status: partial
tags: [module, status/partial, gates]
lines: 4674
test-coverage: partial
created: 2026-04-08
---

# Gates

Source: audit Section 1.5 — `tools/gates/` (11 files, 4674 total lines).

Gate management scripts for the market-maker validation ladder.

---

## Gate Definitions

| Gate | Description | Threshold | Current Status |
|------|-------------|-----------|----------------|
| Gate 1 — Replay Pass | Positive net PnL across broad tape set | Positive net PnL | PASSED |
| Gate 2 — Scenario Sweep | Parameter sweep on benchmark set | >= 70% tapes positive net PnL after fees | FAILED (7/50 = 14%) |
| Gate 3 — Shadow Run | Shadow PnL within 25% of replay prediction | 25% deviation ceiling | BLOCKED (Gate 2 not passed) |
| Gate 4 — Dry-Run Pass | 72-hour zero-error paper live run | Zero errors over 72h | PASSED |

**Root cause of Gate 2 failure:** Silver tapes produce zero fills for politics/sports categories. Crypto bucket positive (7/10) but blocked on new crypto markets.

---

## Script Inventory

| File | Purpose | Status |
|------|---------|--------|
| `close_replay_gate.py` | Close Gate 1 (replay pass) | WORKING |
| `close_sweep_gate.py` | Close Gate 2 (scenario sweep pass) | WORKING |
| `close_mm_gate.py` | Close market-maker gate | WORKING |
| `run_dry_run_gate.py` | Gate: dry-run pass | WORKING |
| `gate_status.py` | Display current gate status | WORKING |
| `benchmark_closure_orchestrator.py` | Full benchmark closure orchestration | WORKING |
| `corpus_audit.py` | Corpus quality audit | WORKING |
| `manifest_curator.py` | Tape manifest curation | WORKING |
| `silver_gap_fill_executor.py` | Execute Silver gap-fill plan | WORKING |
| `sweep_reporter.py` | Sweep result reporter | WORKING |
| `validate_manifest.py` | Validate tape manifest schema | WORKING |

---

## Benchmark Policy

- **benchmark_v1 CLOSED** 2026-03-21 — 50 tapes, DO NOT MODIFY
- WAIT_FOR_CRYPTO policy active (ADR: `docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md`)
- Escalation deadline for benchmark_v2 consideration: 2026-04-12

Gate 2 is currently NOT_RUN (not FAILED) — the corpus has only 10/50 qualifying tapes (crypto bucket blocked).

---

## Gate Script Usage

```bash
python tools/gates/close_sweep_gate.py  # Gate 2 sweep
python tools/gates/gate_status.py       # Current gate status
python tools/gates/validate_manifest.py # Validate manifest schema
```

---

## Cross-References

- [[Track-1B-Market-Maker]] — Gate status and validation path
- [[SimTrader]] — Replay runner used by Gate 1 and Gate 2
- [[Tape-Tiers]] — Silver tapes consumed by Gate 2 sweep
- [[Notifications]] — Gate scripts fire Discord alerts via notify_gate_result

