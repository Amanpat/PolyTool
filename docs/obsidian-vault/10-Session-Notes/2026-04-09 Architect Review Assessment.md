---
tags: [session-note]
date: 2026-04-09
status: complete
topics: [wallet-discovery, architect-review, roadmap-revision]
---
# Architect Review of Wallet Discovery Roadmap — Assessment & Response

## What Happened
Architect (ChatGPT) reviewed the 06-Wallet-Discovery-Roadmap.md and returned a critical review identifying 10 issues plus 5 direct questions. This note captures our assessment of the review and the decisions made in response.

## Architect's Points — Our Assessment

### Agreed (architect correct, roadmap needs fixing):

1. **Scope too wide.** Roadmap presents a full Phase 2 subsystem as an immediate build order while Phase 1 revenue gates aren't closed. Should be treated as a design doc with a narrow v1 slice.

2. **LLM policy conflict.** PLAN_OF_RECORD authorizes Gemini/DeepSeek for RIS evaluation scoring only. Using them for wallet hypothesis generation (Loop C) contradicts the current doc authority. Needs explicit doc reconciliation before implementation.

3. **Insider scoring math is wrong.** Single `binom_test(wins, total, p0)` with averaged p0 is mathematically incorrect when each trade has a different baseline probability. Needs per-bucket calibration test or permutation/bootstrap design.

4. **Alchemy assumptions unverified.** Dynamic topic filter updates, market-level wallet attribution via eth_getLogs, and indexed field mapping are treated as facts but are actually assumptions. Must be Phase 0 proof-of-feasibility checks.

5. **Pass criteria too weak.** "Detect one volume spike in 24h" is exploratory KPI, not engineering acceptance. Need deterministic replay fixtures and synthetic test data.

6. **Watchlist promotion too loose.** LLM novelty flag as auto-promotion criterion violates project's evidence-first standards. Should be a review signal with human gate.

7. **Missing state/lifecycle contracts.** No explicit wallet lifecycle states, no idempotency rules, no dedup contracts. Will cause duplicate processing and alert spam.

8. **Cost estimate too precise.** 1.38M CU/month is a rough planning estimate, not a verified cost. Should be downgraded until Phase 0 probes confirm actual consumption.

### Partially agreed:

9. **Database boundary concern.** Valid concern but our roadmap keeps live writes in ClickHouse and historical reads in DuckDB. No violation planned. Architect is right to flag it as something to watch.

10. **Build order should be thinner slices.** Agree with the sequence: Loop A → scan queue → watchlist → Loop B POC → Loop D POC → Loop C. This matches "simple path first" better.

## Answers to Architect's 5 Questions

| # | Question | Answer | Rationale |
|---|----------|--------|-----------|
| 1 | Immediate build or design package? | **Design package with narrow v1 build** | Phase 1 gates aren't closed; this is Phase 2 work |
| 2 | Loop C hypotheses exploratory or strategy-feeding? | **Exploratory only** | Goes to `user_data` partition, NOT `research`. Must earn promotion through existing gate system if later validated via SimTrader |
| 3 | Cloud LLMs for this now? | **Reconcile docs first** | Update PLAN_OF_RECORD to authorize cloud LLMs for wallet hypothesis generation (same tier-1 policy as RIS), OR start with Ollama-only for v1 |
| 4 | Loop D attribution strength? | **Best-effort candidates** | "Candidate wallets associated with anomalous activity" not "causative wallets." Correlation, not causation |
| 5 | Watchlist promotion human gate? | **Yes for v1** | Quantitative scores surface candidates, human reviews and approves. LLM novelty is a signal, not a trigger |

## V1 Build Scope (Narrowed)

Only these items are in the immediate build:
1. **Loop A** — leaderboard fetcher + churn detection + scan queue
2. **Watchlist table** — ClickHouse schema with lifecycle states
3. **Unified scan command** — consolidate existing CLI flags
4. **MVF computation** — add 7 missing metrics (Python math only, no LLM)

Everything else stays as documented intent with explicit blockers listed.

## Blockers for Phases Beyond V1

- [ ] LLM policy reconciliation (PLAN_OF_RECORD update)
- [ ] Alchemy proof-of-feasibility (topic filtering, dynamic resubscribe, wallet attribution)
- [ ] Insider scoring math correction (heterogeneous probability test design)
- [ ] Schema contracts with lifecycle states and idempotency rules
- [ ] Deterministic acceptance test fixtures

## Cross-References
- [[08-Research/06-Wallet-Discovery-Roadmap]] — original roadmap (to be revised)
- [[09-Decisions/Decision - Two-Feed Architecture]]
- [[09-Decisions/Decision - Watchlist ClickHouse Storage]]
