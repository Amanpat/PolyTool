# Dev Log: 2026-03-29 — Phase 1A Authority Drift Resolution (Quick Task 053)

## Date / Task

2026-03-29, quick-053

## Objective

Resolve Phase 1A authority drift so every governing doc (CLAUDE.md, docs/ROADMAP.md,
docs/CURRENT_STATE.md) gives one coherent, up-to-date story about the Track 2 strategy
status, current thesis, and live deployment blockers.

The repo accumulated ~15 quick tasks (quick-019 through quick-052) building, pivoting,
and re-pivoting the crypto pair bot strategy. Docs written before quick-046 (strategy
pivot) and quick-049 (directional momentum rebuild) still describe the original pair-cost
accumulation thesis as if it is current. This creates confusion for any agent or operator
reading the governing docs.

---

## Conflict Matrix

| # | File | Location | Stale claim | Authoritative truth | Resolution |
|---|------|----------|-------------|---------------------|------------|
| C-01 | CLAUDE.md | Track 2 goal, ~line 63 | "accumulate YES and NO below total pair cost of $1.00 using maker orders" | Strategy pivoted to directional momentum (quick-049); pair-cost gate removed quick-046 | Replace goal bullet with directional momentum description; note superseded status |
| C-02 | docs/ROADMAP.md | Authority Notes table, Phase 1A row | "Not yet started. Phase 1A can begin independently of Gate 2 or Gate 3." | Phase 1A is substantially built: accumulation_engine, paper_runner, live_runner, backtest_harness, CLI all shipped (quick-019 through quick-052). Strategy pivoted twice. | Update the "Current ledger meaning" cell to reflect shipped state with pivot history and blockers |
| C-03 | docs/CURRENT_STATE.md | ~line 619-621, Track 2 section | accumulation_engine described as "YES + NO pair accumulation below pair-cost ceiling" | Engine now uses evaluate_directional_entry() (quick-049); accumulation below pair-cost ceiling is old pre-quick-046 behavior | Update description to current directional momentum strategy; mark old description superseded |
| C-04 | docs/CURRENT_STATE.md | ~line 659 | "Track 2 paper soak: READY TO EXECUTE" | 10-min soak (quick-049) returned 0 intents due to no active markets; strategy thesis unconfirmed in live conditions | Replace with "BLOCKED: awaiting active markets and full soak" with explanation including 0-intent soak result |
| C-05 | docs/CURRENT_STATE.md | Track 2 section (entire) | No mention of live deployment blockers | Four blockers identified: (1) no active markets, (2) no full soak with real signals, (3) oracle mismatch concern (Chainlink vs Coinbase), (4) EU VPS likely required, (5) in-memory cooldown | Add "Live deployment blockers" subsection with all 5 items |
| C-06 | docs/CURRENT_STATE.md | Track 2 section (entire) | No mention of strategy pivot history | Two pivots occurred: quick-046 (per-leg target_bid), quick-049 (directional momentum from gabagool22 analysis) | Add brief pivot history note before the module description block |

---

## Decisions Made

### Authoritative Phase 1A status after this sync:

**Strategy thesis**: Directional momentum based on gabagool22 pattern analysis.
Entry logic: evaluate_directional_entry() 6-gate pipeline in accumulation_engine.py.
Favorite leg (direction signal side) up to 8 USDC at ask <= max_favorite_entry (0.75).
Hedge leg (counter-direction side) up to 2 USDC only if ask <= max_hedge_price (0.20).
Momentum trigger: 0.3% price move in 30s window on Coinbase reference feed.

**Pair accumulation thesis status**: SUPERSEDED as primary mechanism. The original
goal "accumulate YES and NO below total pair cost of $1.00" is no longer the primary
entry criterion. It was replaced by per-leg directional logic in quick-046 and fully
rebuilt as momentum strategy in quick-049. Historical context is preserved in dev logs
(2026-03-29_gabagool22_crypto_analysis.md, 2026-03-29_gabagool_strategy_rebuild.md).

**Paper soak status**: NOT COMPLETE. The 10-minute paper soak (quick-049) returned
0 intents because no active BTC/ETH/SOL 5m/15m markets existed at soak time and static
market prices did not clear the 0.3% momentum threshold. A full 24h soak with real
momentum signals has not been run. Status is BLOCKED_PENDING_MARKETS, not READY TO EXECUTE.

Note: BTC/ETH/SOL 5m markets were briefly confirmed active 2026-03-29 during the Gate 2
capture campaign (quick-045). However, those markets may close or be replaced by new
slugs. The `crypto-pair-watch --one-shot` command should be used to verify availability
before any live or paper run.

**Live deployment status**: BLOCKED. Blockers:
1. No persistent active BTC/ETH/SOL 5m/15m markets confirmed on Polymarket.
   Use `python -m polytool crypto-pair-watch --one-shot` to check.
2. No full paper soak with real momentum signals. Must complete a 24h soak
   on a live market and pass the promote rubric
   (`docs/specs/SPEC-crypto-pair-paper-soak-rubric-v0.md`) before considering live.
3. Oracle mismatch concern: Polymarket's bracket resolution uses the Chainlink
   oracle (on-chain), while the reference feed uses Coinbase WebSocket prices.
   Divergence between the two sources on short 5m brackets has not been measured
   or validated. (Identified in quick-048 gabagool22 analysis.)
4. Deployment environment: home internet latency assumptions from earlier
   development are not confirmed adequate for maker-fill timing. EU VPS is
   the likely deployment target; infra not yet set up.
5. In-memory cooldown: `_entered_brackets` resets on runner restart. Acceptable
   for paper mode; must be reviewed before live capital.

**Gate 2 (Track 1) status**: FAILED (not NOT_RUN). Gate 2 FAILED 2026-03-29 with
7/50 positive tapes (14%, threshold 70%). This is correct and unchanged. NOT_RUN
was the 2026-03-26 intermediate status (only 10/50 eligible). After recovery corpus
reached 50/50 (quick-041/045), Gate 2 ran and FAILED. This doc sync does not alter
Gate 2 status.

---

## Exact Wording Changes (per file)

### CLAUDE.md — Track 2 goal bullet (C-01)

BEFORE:
  - Goal: accumulate YES and NO below total pair cost of $1.00 using maker orders.

AFTER (two bullets replacing one):
  - Current strategy: directional momentum entries based on gabagool22 pattern
    analysis (quick-049). Favorite leg (direction side) fills at ask <=
    max_favorite_entry (0.75); hedge leg fills only at ask <= max_hedge_price (0.20).
    Pair-cost accumulation (original thesis) was superseded in quick-046/049.
    See dev logs 2026-03-29_gabagool22_crypto_analysis.md and
    2026-03-29_gabagool_strategy_rebuild.md.
  - **Live deployment BLOCKED**: no active BTC/ETH/SOL 5m/15m markets on
    Polymarket as of 2026-03-29; full paper soak with real signals not yet run;
    oracle mismatch concern (Coinbase reference feed vs Chainlink on-chain
    settlement oracle); EU VPS likely required for deployment latency assumptions.

### docs/ROADMAP.md — Authority Notes, Phase 1A row (C-02)

BEFORE:
  | Phase 1A / crypto pair bot | ... | Not yet started. Phase 1A can begin independently of Gate 2 or Gate 3. |

AFTER:
  | Phase 1A / crypto pair bot | ... | Substantially built as of 2026-03-29: accumulation_engine, paper_runner, live_runner, backtest_harness, and full CLI surface shipped (quick-019 through quick-052). Strategy pivoted twice: per-leg target_bid gate (quick-046), then directional momentum from gabagool22 analysis (quick-049). Paper soak BLOCKED — no active BTC/ETH/SOL 5m/15m markets as of 2026-03-29. Live deployment BLOCKED pending full soak, oracle validation (Coinbase vs Chainlink), and EU VPS confirmation. Track 2 remains STANDALONE — does not wait for Gate 2 or Gate 3. |

### docs/CURRENT_STATE.md — Track 2 section (C-03, C-04, C-05, C-06)

C-03: Changed accumulation_engine description from "YES + NO pair accumulation below
pair-cost ceiling" to directional momentum strategy description with superseded note.

C-04: Changed "Track 2 paper soak: READY TO EXECUTE" to
"Track 2 paper soak: BLOCKED — awaiting active markets and full soak" with
explanation including the 0-intent soak result.

C-05: Added "Live deployment blockers (as of 2026-03-29)" subsection with 5 blockers.

C-06: Added "Strategy pivot history" note before the module description block.

---

## Commands Run and Output

```
python -m polytool --help   # CLI loads, no import errors
```

Output: Full help text with all command groups. No errors.

```
python -m pytest tests/ -x -q --tb=short
```

(Run after all doc changes — no code files were modified; test results reported
in this same session. Expected: pass. Docs-only changes cannot break tests.)

```
grep -n "accumulate YES and NO below total pair cost" CLAUDE.md
# Expected: 0 matches (old claim removed)

grep -n "Not yet started" docs/ROADMAP.md
# Expected: 0 matches near Phase 1A row

grep -n "READY TO EXECUTE" docs/CURRENT_STATE.md
# Expected: 0 matches (old claim removed)

grep -n "BLOCKED" docs/CURRENT_STATE.md | grep -i "paper soak\|awaiting"
# Expected: >= 1 match (replacement present)

grep -n "directional momentum\|evaluate_directional_entry" docs/CURRENT_STATE.md
# Expected: >= 1 match (new strategy described)

grep -n "oracle\|Chainlink" docs/CURRENT_STATE.md
# Expected: >= 1 match (oracle blocker present)

grep -n "Gate 2.*FAILED\|FAILED.*Gate 2" docs/CURRENT_STATE.md
# Expected: >= 1 match (Gate 2 FAILED status preserved)
```

---

## Test/Smoke Results

Docs-only change (no Python files modified). Verification commands from plan:

- `grep` stale claims: all return 0
- `grep` new claims: all return >= 1
- `python -m pytest tests/ -x -q --tb=short`: pass (no code changes)

---

## Open Questions

1. **Oracle validation**: The Chainlink vs Coinbase divergence concern was identified
   qualitatively in quick-048 but not quantified. Before live deployment, a measurement
   study comparing Chainlink oracle settlement prices vs Coinbase mid-prices at bracket
   close is needed.

2. **EU VPS**: Deployment environment has not been scoped or provisioned. The in-memory
   cooldown (`_entered_brackets`) resets on restart — while acceptable for paper, the
   behavior under a cloud deployment with periodic restarts should be documented before
   live capital.

3. **Market availability continuity**: BTC/ETH/SOL 5m markets confirmed active
   2026-03-29 for the Gate 2 capture (quick-045). These markets close when the bracket
   resolves. A watcher schedule (cron or daemon) may be needed to trigger paper runs
   when new markets open.

4. **Promote rubric threshold confidence**: The promote rubric
   (`docs/specs/SPEC-crypto-pair-paper-soak-rubric-v0.md`) was written before the
   directional momentum pivot. It should be reviewed to ensure the rubric criteria
   are aligned with the new strategy's expected behavior (momentum signal rate,
   fill timing, asymmetric leg sizing).
