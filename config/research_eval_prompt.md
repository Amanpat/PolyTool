# PolyTool Research Evaluation Rubric

**Version:** RIS v1  
**Updated:** 2026-04-01  
**Purpose:** Scoring rubric for the RIS evaluation gate. This file is loaded by the evaluator and can be refined via calibration sessions.

---

## Domain Context

PolyTool is a Polymarket-first research, simulation, and execution system. We are building three strategy tracks:

1. **Market Maker** (Track A) — Avellaneda-Stoikov style quoting with inventory control on Polymarket binary markets
2. **Crypto Pair Bot** (Track 2 / Phase 1A) — Directional momentum entries on BTC/ETH/SOL 5m/15m binary markets
3. **Sports Directional Model** (Track 3) — Probability model using freely available sports data

We need research on:
- Prediction market microstructure (order flow, adverse selection, spread dynamics)
- Market making strategy theory and parameters
- Quantitative trading edge identification
- Crypto pair dynamics and reference feed analysis
- Sports probability modeling and calibration
- Behavioral patterns of profitable prediction market participants

---

## Scoring Rubric

### Scale: 1-5 per dimension (total /20)

### Dimension 1: Relevance

How directly does this content relate to prediction market trading, market making, or PolyTool's strategy tracks?

| Score | Description |
|-------|-------------|
| 5 | Directly about Polymarket, prediction market microstructure, or a strategy type we are building |
| 4 | About general market making, quantitative trading, or prediction markets on other platforms |
| 3 | Adjacent topic (DeFi trading, options MM, sports analytics) with transferable insights |
| 2 | Tangentially related (general ML, general finance, broad crypto) |
| 1 | Not relevant to our domain |

### Dimension 2: Novelty

Does this add information not already in the knowledge base?

| Score | Description |
|-------|-------------|
| 5 | Entirely new strategy concept, data source, or empirical finding |
| 4 | New angle on a known concept, or significant new data |
| 3 | Moderate new information, some overlap with existing knowledge |
| 2 | Mostly redundant, adds minor detail |
| 1 | Already covered comprehensively in the knowledge base |

### Dimension 3: Actionability

Can this directly inform a trading decision, strategy parameter, or development choice?

| Score | Description |
|-------|-------------|
| 5 | Contains specific parameters, thresholds, or implementations directly testable |
| 4 | Contains a testable hypothesis or clear strategic recommendation |
| 3 | Useful context that informs strategy design indirectly |
| 2 | Interesting background but no clear path to action |
| 1 | Pure theory with no practical application |

### Dimension 4: Credibility

How trustworthy is this source?

| Score | Description |
|-------|-------------|
| 5 | Peer-reviewed paper, published dataset with methodology, verified on-chain analysis |
| 4 | Experienced practitioner with evidence, well-reasoned post with data |
| 3 | Community member with some evidence, anecdotal but plausible |
| 2 | Unverified claim, single data point, promotional content |
| 1 | Known unreliable, contradicted by data, spam |

### Thresholds

| Band | Score Range | Gate | Action |
|------|-------------|------|--------|
| GREEN | >= 12/20 | ACCEPT | Auto-ingest into knowledge base |
| YELLOW | 8-11/20 | REVIEW | Escalate for re-evaluation or human review |
| RED | < 8/20 | REJECT | Reject; log to rejected_log.jsonl |

---

## Source Family Guidance

Apply the appropriate guidance based on source_type:

- **academic** (arxiv, ssrn, book): Academic/peer-reviewed source. Credibility floor is 3 unless methodology is clearly flawed. Weight empirical findings heavily.
- **forum_social** (reddit, twitter, youtube): Community source. Credibility ceiling is 3 unless the author provides verifiable data or on-chain evidence. Look past conversational filler for core insight.
- **github**: Open-source practitioner source. Credibility 3-4 if repo has evidence of real usage. Score actionability high if code is directly adaptable.
- **blog**: Blog/essay source. Credibility depends on author track record and evidence quality. Score novelty relative to existing knowledge base.
- **news**: News article. Credibility depends on outlet reputation. Actionability is usually low unless it contains market-moving data.
- **dossier_report**: Internal analysis report. High relevance by default. Score novelty based on whether findings are already captured.
- **manual**: Manually submitted content. Apply standard rubric without source-type bias.

---

## Epistemic Type Tagging

Tag each document with exactly one epistemic type (stored as metadata, does not affect score):

- `EMPIRICAL` — contains verifiable data or measured results
- `THEORETICAL` — contains a model or framework without empirical validation
- `ANECDOTAL` — personal experience or observation
- `SPECULATIVE` — prediction or hypothesis without evidence

---

## Example Evaluations

### Example 1: ACCEPT (academic, empirical)

**Document:** "Avellaneda-Stoikov Market Making Model: Implementation and Parameter Study"  
**Source type:** arxiv  
**Expected scores:** relevance=5, novelty=4, actionability=5, credibility=5, total=19

**Rationale:**
- Relevance=5: Directly describes the exact market making model we are implementing
- Novelty=4: Core model is known, but parameter study adds new calibration data
- Actionability=5: Contains specific parameter ranges directly usable in our MarketMakerV1
- Credibility=5: Peer-reviewed, published methodology with reproducible results

**Gate: ACCEPT**

---

### Example 2: REJECT (spam/promotional)

**Document:** "TRADE POLYMARKET NOW — 10X RETURNS GUARANTEED with my exclusive signals"  
**Source type:** manual  
**Expected scores:** relevance=2, novelty=1, actionability=1, credibility=1, total=5

**Rationale:**
- Relevance=2: Mentions Polymarket but contains no analytical content
- Novelty=1: No novel information whatsoever
- Actionability=1: Promotional content with no actionable insight
- Credibility=1: No evidence, promotional, likely spam

**Gate: REJECT**

---

### Example 3: REVIEW (borderline, forum post with data)

**Document:** Reddit post by gabagool22 with on-chain trade analysis showing directional momentum pattern  
**Source type:** reddit  
**Expected scores:** relevance=4, novelty=3, actionability=3, credibility=3, total=13 → ACCEPT

**Rationale:**
- Relevance=4: About Polymarket crypto markets, directly relevant to Track 2
- Novelty=3: Describes a pattern we have partially explored, adds supporting evidence
- Actionability=3: Useful signal but requires our own validation before deploying
- Credibility=3: On-chain data provided, but single wallet, anecdotal

**Gate: ACCEPT (13/20)**

---

## Calibration Notes

*(Empty in RIS v1 — to be populated after initial calibration sessions)*

Calibration workflow:
1. Seed with 20 manually scored documents
2. Run pipeline, review all accepts and rejects
3. Adjust thresholds based on observed accept/reject rates (target: 50-70% accept)
4. Lock thresholds, write calibration notes here

---

## Expected JSON Output Format

```json
{
  "relevance": {"score": 4, "rationale": "One-sentence rationale"},
  "novelty": {"score": 3, "rationale": "One-sentence rationale"},
  "actionability": {"score": 4, "rationale": "One-sentence rationale"},
  "credibility": {"score": 5, "rationale": "One-sentence rationale"},
  "total": 16,
  "epistemic_type": "EMPIRICAL",
  "summary": "2-3 sentence summary of the document's key contribution.",
  "key_findings": [
    "Finding 1: specific actionable insight",
    "Finding 2: supporting empirical evidence"
  ],
  "eval_model": "provider_name"
}
```

**Instructions to evaluator:**
- Output JSON only — no markdown, no explanation, no preamble
- Score substance not grammar; typos do not reduce credibility
- For social media: look past conversational filler for core insight
- For academic papers: abstract alone is sufficient for scoring unless borderline
- Evaluate novelty relative to what PolyTool already knows, not absolute novelty
