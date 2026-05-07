# L3 v1 SVM — Director Review Packet: Label Batch A

**Date:** 2026-05-06  
**Author:** Claude Code (read-only analysis session — no labels applied, no code changes)  
**Scope:** Prepare batch A of label recommendations for Director review.

---

## Objective

Create a read-only Director review packet (`artifacts/research/svm_filter_label_expansion/label_batch_A.md`) covering candidates 1–49 of the 98 pending unlabeled queue entries sorted by `candidate_id` ascending. No labels were applied during this session.

---

## Commands Run + Outputs

### Step 1: Baseline

```
git status --short
```
Working tree dirty from prior L3 SVM implementation work (pre-existing). No new code changes in this session.

```
python -m polytool research-prefetch-review counts --json
```
```json
{
  "total_queued": 159,
  "pending_unlabeled": 98,
  "labeled_total": 61,
  "labeled_allow": 30,
  "labeled_reject": 31,
  "pending_review_count": 159,
  "label_count": 61,
  "allowed_label_count": 30,
  "rejected_label_count": 31
}
```

```
Get-FileHash -Algorithm SHA256 -LiteralPath 'artifacts\research\svm_filter_labels\labels.jsonl'
```
`3940D2FFB1F9F62C2BF65B5A01C33CE3F9BDF7623532916B68F1C5276E6000A2`

This SHA matches the prior verification hash from the Codex verify dev log (`2026-05-06_codex-verify-l3-v1-svm-workpacket-blockers.md`).

### Step 2: CLI Discovery

```
python -m polytool research-prefetch-review --help
python -m polytool research-prefetch-review list --help
python -m polytool research-prefetch-review label --help
```

Confirmed: `list` subcommand exports pending unlabeled candidates as JSON (read-only, no side effects). `label CANDIDATE_ID LABEL` applies a label. `counts` shows queue and label store state.

### Step 3: Export + Sort Pending Candidates

```
python -m polytool research-prefetch-review list --json > pending_candidates.json
```
98 candidates exported. Sorted by `candidate_id` (SHA256 hex string, lexicographic ascending). Verified via PowerShell sort — first entry `000c6e786a9e56ec...` (Price Formation in Prediction Markets), last entry `fb12002203e77b3c...` (RL for Trade Execution).

### Step 4: Batch Extraction + Classification

Candidates 1–49 of the sorted list were manually classified against the allow/reject criteria:

- **ALLOW:** prediction markets, market microstructure, LOB dynamics, order books, backtesting, information aggregation in markets, arbitrage, queue/fill/latency, financial ML directly relevant to RIS/PolyTool, cryptocurrency price discovery, binary option markets.
- **REJECT:** medical imaging, astrophysics, generic ML surveys, sports performance analytics (non-market), educational AI, general deep learning theory, biology ML, differential privacy for generic ML.
- **LEAVE PENDING:** content too ambiguous or sparse to classify confidently.

### Step 5: Post-Check (labels and counts unchanged)

```
python -m polytool research-prefetch-review counts --json
```
Identical output to baseline — counts unchanged.

```
Get-FileHash -Algorithm SHA256 -LiteralPath 'artifacts\research\svm_filter_labels\labels.jsonl'
```
`3940D2FFB1F9F62C2BF65B5A01C33CE3F9BDF7623532916B68F1C5276E6000A2`

SHA unchanged — confirms no labels were applied during this session.

---

## Batch Range and Split Rule

- **Range:** candidates 1–49 (inclusive) of 98 pending, sorted by `candidate_id` ascending.
- **Split rule:** lexicographic sort of `candidate_id` SHA256 hex string — deterministic across runs; no RNG involved.
- **Batch A artifact:** `artifacts/research/svm_filter_label_expansion/label_batch_A.md`
- **Batch B:** candidates 50–98 — to be prepared after Director applies batch A.

---

## Recommendation Summary

| Recommendation | Count |
|---|---|
| ALLOW | 21 |
| REJECT | 26 |
| LEAVE PENDING | 2 |
| **Total** | **49** |

**ALLOW examples (high confidence):**
- Prediction market price formation and information aggregation papers
- Algorithmic trading in microstructural LOB models
- Market making with decreasing utility for information (combinatorial prediction markets)
- Sparse order book simulation for intraday markets
- MARL in realistic LOB simulation
- Price discovery in cryptocurrency markets (relevant to Track 2)
- Dynamics of binary option markets (directly analogous to Polymarket binary outcomes)
- Early detection of latent microstructure regimes in LOBs

**REJECT examples (high confidence):**
- Medical imaging DL surveys (multiple — lexical scorer queued these via sports/radiology queries)
- Sports performance ML (cyclist fitness, volleyball outcome, etc.)
- Generic deep learning theory and generic AutoML papers
- Astrophysics ML papers (gravitational waves, brown dwarf surveys)
- Generic ML evaluation and meta-learning papers

**Notable medium-confidence REJECT:**
- Candidate #33 (China money market liquidity shocks): lexical scorer gave `allow` (0.881) on "financial market" + "liquidity" keywords, but content is macro banking research unrelated to prediction markets or LOBs. Recommended reject — good SVM training signal for lexical false positives.

**LEAVE PENDING:**
- Candidate #21: Repetitive Dilemma Games paper — title/abstract mismatch, confusing preliminary report.
- Candidate #26: Binary classification model monitoring — too generic to classify confidently.

---

## Label SHA Before / After

| Point | SHA256 |
|---|---|
| Before | `3940D2FFB1F9F62C2BF65B5A01C33CE3F9BDF7623532916B68F1C5276E6000A2` |
| After (this session) | `3940D2FFB1F9F62C2BF65B5A01C33CE3F9BDF7623532916B68F1C5276E6000A2` |

SHA unchanged — no labels applied in this session. ✓

---

## Counts Before / After

| Metric | Before | After |
|---|---|---|
| total_queued | 159 | 159 |
| pending_unlabeled | 98 | 98 |
| labeled_total | 61 | 61 |
| labeled_allow | 30 | 30 |
| labeled_reject | 31 | 31 |

Counts unchanged — no labels applied in this session. ✓

---

## Files Touched

| File | Action |
|---|---|
| `artifacts/research/svm_filter_label_expansion/label_batch_A.md` | CREATED (new) |
| `docs/dev_logs/2026-05-06_l3-v1-svm-label-batch-a.md` | CREATED (this file) |
| `artifacts/research/svm_filter_labels/labels.jsonl` | READ ONLY (not modified) |
| `artifacts/research/prefetch_review_queue/review_queue.jsonl` | READ ONLY via CLI (not modified) |
| All implementation code and tests | NOT TOUCHED |

---

## Open Questions

1. **Director batch A review:** 21 allow + 26 reject recommendations are ready for Director to apply. After applying all 47, labeled_total reaches 108 — still 42 short of the 150 enforce gate.
2. **Batch B:** After batch A is applied, prepare batch B (candidates 50–98) using the same split rule.
3. **Model selection:** `BAAI/bge-large-en-v1.5` vs SPECTER2 path — decision still pending. Does not block label collection but needed before training with the enriched corpus.
4. **Candidate #33 (China money market):** Lexical false positive flagged — useful for SVM to learn lexical score is not authoritative. Director should confirm reject/allow.
5. **Candidate #26 (binary classification monitoring):** Director should decide after reviewing abstract if performance estimation for calibrated classifiers is in-scope for PolyTool RIS.

---

## Codex Review Summary

Tier: artifact creation only. No implementation code reviewed or modified.  
Issues found: none.  
Issues addressed: N/A.
