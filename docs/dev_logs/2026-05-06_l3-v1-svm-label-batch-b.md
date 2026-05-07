# L3 v1 SVM Label Expansion — Director Review Packet B

**Date:** 2026-05-06  
**Author:** Claude Code (read-only pass)  
**Scope:** Create `artifacts/research/svm_filter_label_expansion/label_batch_B.md` with label recommendations for candidates 50–98. No labels applied, no code changed.

---

## Commands Run and Outputs

### 1. Baseline counts

```
python -m polytool research-prefetch-review counts --json
```

```json
{
  "total_queued": 159,
  "pending_unlabeled": 98,
  "labeled_total": 61,
  "labeled_allow": 30,
  "labeled_reject": 31
}
```

### 2. Baseline label SHA

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath 'artifacts\research\svm_filter_labels\labels.jsonl'
```

```
Hash: 3940D2FFB1F9F62C2BF65B5A01C33CE3F9BDF7623532916B68F1C5276E6000A2
```

### 3. Export pending candidates

```
python -m polytool research-prefetch-review list --json | python -c "
import json,sys
data=json.load(sys.stdin)
sorted_data=sorted(data, key=lambda x: x.get('candidate_id',''))
# 98 pending total, Batch B = indices 49-97
"
```

Confirmed: 98 pending unlabeled candidates exported.

### 4. Sort rule verification

First three sorted IDs (ascending `candidate_id` lex):
- `000c6e786a9e56ec` — Price Formation in Field Prediction Markets...
- `01d5c7aee0852d13` — Price Interpretability of Prediction Markets...
- `04ca156ccf290410` — Market Microstructure During Financial Crisis...

Last three:
- `ef09d5eec381c46b` — Dynamic Grid Trading Strategy...
- `ef7352351d0deae6` — A comprehensive survey on deep active learning in medical image analysis
- `fb12002203e77b3c` — Reinforcement Learning for Trade Execution with Market and Limit Orders

### 5. Batch range

**Batch A:** sorted positions 1–49 (indices 0–48)  
**Batch B:** sorted positions 50–98 (indices 49–97)  
49 candidates total in Batch B.

### 6. Post-check counts (after batch file creation — no labels applied)

```
python -m polytool research-prefetch-review counts --json
```

```json
{
  "total_queued": 159,
  "pending_unlabeled": 98,
  "labeled_total": 61,
  "labeled_allow": 30,
  "labeled_reject": 31
}
```

### 7. Post-check label SHA

```
Hash: 3940D2FFB1F9F62C2BF65B5A01C33CE3F9BDF7623532916B68F1C5276E6000A2
```

SHA matches baseline. Labels unchanged. ✓

---

## Batch Range and Split Rule

- **Total pending:** 98
- **Batch B range:** candidates 50–98 (sorted by `candidate_id` ascending)
- **Batch B count:** 49 candidates

The split rule is deterministic: `sorted(pending, key=lambda x: x['candidate_id'])`. Batch A covers indices 0–48, Batch B covers indices 49–97. This is reproducible from any fresh `list --json` call as long as the pending set is unchanged.

---

## Recommendation Summary

| Label | Count | High-confidence | Medium-confidence |
|---|---|---|---|
| allow | 23 | 15 | 8 |
| reject | 25 | 17 | 8 |
| leave pending | 1 | 0 | 1 (low) |
| **Total** | **49** | **32** | **16** |

### High-confidence ALLOW (15)

Papers with strong direct relevance to prediction markets, LOB, market making, or execution:
- #53 FaRM: Fair Reward Mechanism for Information Aggregation (prediction market)
- #55 Beating the market with a bad predictive model (Kelly criterion, market maker)
- #56 Deterministic LOB Simulator with Hawkes-Driven Order Flow (SimTrader)
- #57 Endogenous Formation of Limit Order Books (LOB theory)
- #58 Trade arrival dynamics and quote imbalance in LOB (microstructure)
- #65 LOB Dynamics in Matching Markets: Microstructure, Spread, Execution
- #67 Information Aggregation in Exponential Family Markets (prediction market)
- #73 Market Making under Weakly Consistent LOB Model (market maker)
- #75 Universal scaling and nonlinearity of aggregate price impact
- #78 TradeFM: Generative Foundation Model for Trade-flow and Microstructure
- #82 Model-based gym environments for LOB trading (backtesting)
- #86 Asynchronous Deep Double Duelling Q-Learning for LOB execution (RL)
- #87 Hidden Order in Trades Predicts Price Moves (informed trading)
- #93 A Prediction Market for Toxic Assets Prices
- #98 Reinforcement Learning for Trade Execution with Market and Limit Orders

### High-confidence REJECT (17)

Medical imaging (9): #50, #60, #63, #71, #74, #85, #89, #94, #97  
Other unrelated domains (8): #52 (healthcare ML), #59 (bioinformatics), #64 (astrophysics), #66 (medical survey), #76 (RL robotics), #80 (agricultural policy), #83 (few-shot ML), #84 (fake news), #90 (remote sensing)

### Medium-confidence recommendations

**Allow (8):** Papers adjacent to PolyTool's core concerns — price discovery in futures (#51), intra-day equity price prediction (#54), sports betting ML (#62), agent-based price formation (#68), dark pools and price discovery (#81), backtesting candle charts (#88), liquidity risk and market depth (#95), grid trading strategy (#96).

**Reject (8):** Generic ML papers with no market context — ML learning curves survey (#61), official statistics ML (#69), physics-inspired ML interpretability (#70), unsupervised representation learning (#72), evidence accumulation ML theory (#77), active learning data streams (#79), Fourier neural networks (#91).

### Leave pending (1)

**#92** "Stock Market Price Prediction using Neural Prophet with Deep Neural Network" — Borderline financial ML. Stock-specific, not prediction-market or LOB specific. Score 0.5 (no matched terms). Recommend Director reads abstract before forcing a label.

---

## Label Gap Analysis

Current: 61 total (30 allow / 31 reject). Gate: ≥150.  
If Director applies all Batch B recommendations (48 labels): 
- allow: 30 + 23 = 53  
- reject: 31 + 25 = 56  
- total: 61 + 48 = 109  
- remaining gap: 150 − 109 = **41 more labels needed**

Batch A (candidates 1–49) provides additional pool to close the gap.

---

## Label SHA Before / After

| Checkpoint | SHA256 |
|---|---|
| Before (baseline) | `3940D2FFB1F9F62C2BF65B5A01C33CE3F9BDF7623532916B68F1C5276E6000A2` |
| After (post batch file creation) | `3940D2FFB1F9F62C2BF65B5A01C33CE3F9BDF7623532916B68F1C5276E6000A2` |

No change. ✓

---

## Open Questions

1. **#92 (Stock Market Price Prediction):** Director to judge allow vs. reject after reading abstract.
2. **Medium-confidence allows (#51, 54, 62, 68, 81, 88, 95, 96):** Director should review these 8 if there's any concern about allow boundary scope.
3. **Do Batch A recommendations need a matching packet?** This session only covers Batch B (50–98). Batch A (1–49) recommendations either already exist in a prior packet or need a separate Packet A session.
4. **After reaching ≥150 labels:** Director must explicitly approve before enforce mode can be activated. Model-selection decision (SPECTER2 vs bge-large-en-v1.5) also still open.

---

## Code / Artifact Changes

- **Created:** `artifacts/research/svm_filter_label_expansion/label_batch_B.md`
- **Created:** `docs/dev_logs/2026-05-06_l3-v1-svm-label-batch-b.md` (this file)
- **Not touched:** `artifacts/research/svm_filter_labels/labels.jsonl`
- **Not touched:** `artifacts/research/prefetch_review_queue/review_queue.jsonl`
- **Not touched:** any code, tests, model artifacts, or training state
