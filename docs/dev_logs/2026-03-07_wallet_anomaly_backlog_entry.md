# Dev Log: Wallet Anomaly Alerts — Backlog Entry

**Date:** 2026-03-07
**Branch:** simtrader
**Author:** Claude Code

---

## What Was Done

Added a deferred backlog entry for wallet anomaly alerts / flow discrepancy
alerts to `docs/TODO.md` under the **Future Feature** section.

---

## File Updated

**`docs/TODO.md`** — New section inserted under `## Future Feature`:

```
### Wallet Anomaly Alerts / Flow Discrepancy Alerts [DEFERRED — Track B Research]

Not part of the arb watcher. Not in current scope.

Deferred until the current usability + workflow streamlining pass is complete.

Intended future scope:
- Detect unusually large bets relative to a wallet's own history
- Detect unusually large bets relative to market-level or user-bucket baselines
- Abnormal conviction alerts: extreme YES/NO skew, one-sided position building
- Treat this as suspicious flow detection, not proven insider detection

Future integration points:
- May feed market selection / watchlists as a signal lane
- May surface in research alerts or LLM bundle context
- Should live under a separate Track B signal pipeline, not inside the arb watcher
```

---

## Why This Is Deferred

The current project focus is streamlining the existing toolchain:
- End-to-end usability
- UI clarity and command clarity
- One-command RAG workflows
- Better documentation
- Cleaner user-facing experience

Wallet anomaly detection is a valid future signal lane but adds implementation
complexity that is out of scope for this pass. It requires:

1. A baseline model per wallet (history aggregation)
2. A baseline model per market / user bucket (statistical outlier detection)
3. A signal pipeline separate from the existing arb watcher
4. A policy for surfacing flags without making automated trading decisions

None of these are needed to complete the current usability milestone.

---

## Constraints Respected

- No anomaly detection code was written
- Current roadmap priorities were not changed
- Entry is clearly marked as deferred Track B research work
- Entry explicitly calls out it is NOT part of the arb watcher
