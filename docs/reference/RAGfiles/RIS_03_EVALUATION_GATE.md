# RIS_03 — Evaluation Gate
**System:** PolyTool Research Intelligence System  
**Covers:** LLM scoring, multi-model panel, calibration workflow, rejection review

---

## Purpose

The evaluation gate decides which documents enter the knowledge base. Every document from
every source passes through this single gate. It is the quality control layer that prevents
the RAG from filling with noise, outdated content, or irrelevant material.

---

## Architecture

```
Document (from normalizer)
    │
    ▼
┌──────────────────────────────┐
│  STEP 1: Deduplication       │
│  Embedding similarity check  │
│  >0.92 = skip (log as dupe)  │
└──────────────┬───────────────┘
               │ unique document
               ▼
┌──────────────────────────────┐
│  STEP 2: Binary Pre-Gate     │
│  "Is this about prediction   │
│   markets, trading, market   │
│   making, or quant strategy?"│
│  Gemini Flash (1 token: Y/N) │
└──────────────┬───────────────┘
               │ YES
               ▼
┌──────────────────────────────┐
│  STEP 3: Dimensional Scoring │
│  Gemini Flash primary        │
│  4 dimensions × 1-5 scale    │
│  Total: /20                  │
└──────────────┬───────────────┘
               │
    ┌──────────┼──────────┐
    ▼          ▼          ▼
 GREEN      YELLOW       RED
 ≥12/20     8-12/20     <8/20
 Auto-      Escalate     Reject
 ingest     to DeepSeek  + log
            V3 or human
```

---

## Scoring Rubric

### Scale: 1-5 per dimension (total /20)

Research (Report 2) confirms that LLMs can reliably distinguish 1-5 ordinal levels but
struggle with 0-25 granularity. The 1-5 scale maps to clear, describable quality levels
that an LLM can consistently apply.

### Dimension 1: Relevance (1-5)

How directly does this content relate to prediction market trading, market making, or
PolyTool's strategy tracks?

| Score | Description |
|-------|------------|
| 5 | Directly about Polymarket, prediction market microstructure, or a strategy type we're building |
| 4 | About general market making, quantitative trading, or prediction markets on other platforms |
| 3 | Adjacent topic (DeFi trading, options MM, sports analytics) with transferable insights |
| 2 | Tangentially related (general ML, general finance, broad crypto) |
| 1 | Not relevant to our domain |

### Dimension 2: Novelty (1-5)

Does this add information not already in the knowledge base?

| Score | Description |
|-------|------------|
| 5 | Entirely new strategy concept, data source, or empirical finding |
| 4 | New angle on a known concept, or significant new data |
| 3 | Moderate new information, some overlap with existing knowledge |
| 2 | Mostly redundant, adds minor detail |
| 1 | Already covered comprehensively in the knowledge base |

### Dimension 3: Actionability (1-5)

Can this directly inform a trading decision, strategy parameter, or development choice?

| Score | Description |
|-------|------------|
| 5 | Contains specific parameters, thresholds, or implementations directly testable |
| 4 | Contains a testable hypothesis or clear strategic recommendation |
| 3 | Useful context that informs strategy design indirectly |
| 2 | Interesting background but no clear path to action |
| 1 | Pure theory with no practical application |

### Dimension 4: Credibility (1-5)

How trustworthy is this source?

| Score | Description |
|-------|------------|
| 5 | Peer-reviewed paper, published dataset with methodology, verified on-chain analysis |
| 4 | Experienced practitioner with evidence, well-reasoned post with data |
| 3 | Community member with some evidence, anecdotal but plausible |
| 2 | Unverified claim, single data point, promotional content |
| 1 | Known unreliable, contradicted by data, spam |

### Thresholds

| Band | Score Range | Action |
|------|------------|--------|
| GREEN | ≥12/20 | Auto-ingest into `external_knowledge` |
| YELLOW | 8-12/20 | Escalate to DeepSeek V3 for re-evaluation. If DeepSeek scores ≥12, ingest. Otherwise, queue for human review. |
| RED | <8/20 | Reject. Log to `artifacts/research/rejected_log.jsonl` with scores and rationale. |

### Epistemic Clarity (bonus signal, not a scored dimension)

Inspired by the Clarity Gate project (Research Report 2): the evaluator prompt asks
the LLM to tag each document with epistemic markers:
- `EMPIRICAL` — contains verifiable data or measured results
- `THEORETICAL` — contains a model or framework without empirical validation
- `ANECDOTAL` — personal experience or observation
- `SPECULATIVE` — prediction or hypothesis without evidence

This tag is stored as metadata (`epistemic_type`) but does NOT affect the score. It helps
downstream consumers (report synthesizer, human reviewers) interpret the content correctly.

---

## Evaluation Prompt

The prompt document lives at `config/research_eval_prompt.md` and is the operator's
primary tool for improving system quality. It contains:

1. The rubric (copied from above)
2. Domain context (what PolyTool is, what we're building)
3. 5+ example evaluations (2 accepts, 2 rejects, 1 borderline)
4. Accumulated calibration notes from human review sessions
5. Special instructions for different source types

**Key prompt instructions:**
- "Evaluate substance, not grammar. Typos and informal language do not reduce scores."
- "Score against what's ALREADY in the knowledge base for novelty assessment." (The prompt
  includes a summary of current knowledge base contents, updated weekly.)
- "For social media posts: look past conversational filler for the core insight."
- "For academic papers: the abstract alone is often sufficient for scoring; full text
  evaluation is for borderline cases."

**Prompt structure for the LLM:**
```
You are a research evaluator for a prediction market trading system called PolyTool.

Your task: evaluate whether this document should be added to our knowledge base.

DOMAIN CONTEXT:
[Brief description of PolyTool, current strategy tracks, known findings]

CURRENT KNOWLEDGE BASE SUMMARY:
[Auto-generated weekly summary of what's already indexed — prevents redundant ingestion]

RUBRIC:
[The 4 dimensions with descriptions]

DOCUMENT TO EVALUATE:
Source type: {source_type}
Title: {title}
Author: {author}
Date: {source_publish_date}
Text: {text}

EXAMPLES OF CORRECT EVALUATIONS:
[5+ examples with rationale]

INSTRUCTIONS:
1. First: is this about prediction markets, trading, market making, or quantitative
   strategies? If NO, output: {"gate": "REJECT", "reason": "not_relevant"}
2. If YES: score each dimension 1-5 with a one-sentence rationale.
3. Tag epistemic type: EMPIRICAL | THEORETICAL | ANECDOTAL | SPECULATIVE
4. Write a 2-3 sentence summary of the document's key contribution.
5. List 1-3 key findings as bullet points.
6. Identify related strategy tracks: market_maker | crypto_pairs | sports_model | general

Output JSON:
{
  "gate": "ACCEPT" | "REVIEW" | "REJECT",
  "relevance": {"score": 1-5, "rationale": "..."},
  "novelty": {"score": 1-5, "rationale": "..."},
  "actionability": {"score": 1-5, "rationale": "..."},
  "credibility": {"score": 1-5, "rationale": "..."},
  "total": 4-20,
  "epistemic_type": "EMPIRICAL" | "THEORETICAL" | "ANECDOTAL" | "SPECULATIVE",
  "summary": "2-3 sentences",
  "key_findings": ["finding 1", "finding 2"],
  "related_tracks": ["market_maker", "sports_model"]
}
```

---

## Multi-Model Strategy

### v1: Two-tier evaluation

```
All documents → Gemini Flash (fast, 1500 free/day)
                    │
                    ├── GREEN (≥12) → auto-ingest
                    ├── RED (<8) → auto-reject + log
                    └── YELLOW (8-12) → DeepSeek V3 (re-evaluate)
                                           │
                                           ├── ≥12 → ingest
                                           └── <12 → human review queue
```

**Why Gemini Flash first:** Speed and free quota. Most documents (70-80%) will be clearly
accept or reject. Only borderline cases need the stronger model.

**Why DeepSeek V3 for escalation:** Better reasoning, especially on complex academic papers
where Gemini might miss nuance. DeepSeek V3 is free via API but slower.

**Ollama fallback:** When both cloud APIs are unavailable or rate-limited, fall back to
Ollama (Qwen3-30B or Llama-3-8B). Lower quality but keeps the pipeline running.

### v2: Multi-model jury (future)

For high-stakes documents (e.g., papers claiming to have found a new profitable strategy),
run a panel of 2-3 models and aggregate:
- Average scores across models
- If models disagree by >3 points on any dimension, flag for human review
- Randomize presentation order to mitigate position bias

Research (Report 2) shows 8-15% reliability gains from jury approaches. Worth implementing
once the v1 pipeline is stable and we understand common failure modes.

### v2+: Autoresearch-informed evaluation (future)

The Karpathy autoresearch pattern applied to the evaluation prompt itself:
- Define a gold set of 100+ human-scored documents
- Run the evaluator against the gold set, measure agreement
- LLM agent proposes modifications to the evaluation prompt
- Run modified prompt against gold set → if agreement improves, keep
- Overnight loop iterates on the prompt automatically

This is the Adaptive ML / RL connection: the evaluation prompt is being optimized via
a keep/revert loop against a human-labeled benchmark, analogous to how autoresearch
optimizes strategy configs against benchmark tapes.

---

## Calibration Workflow

### Phase 1: Initial calibration (first 2 weeks)

```
Day 1-3:   Seed gold set with 20 manually scored documents (diverse sources)
Day 4-7:   Run pipeline, manually review ALL documents (accept and reject)
Day 7:     Adjust thresholds based on observed accept/reject rates
Day 8-14:  Review only YELLOW zone documents + random 10% sample
Day 14:    Lock thresholds, write calibration notes to eval prompt
```

**Target metrics after calibration:**
- Accept rate: 50-70% (if higher, threshold may be too low)
- Accept rate: <30% (if lower, sources may be too noisy or threshold too high)
- Human agreement with LLM on gold set: >80%

### Phase 2: Ongoing calibration (post-initial)

- Weekly: review 10 random YELLOW zone documents, verify decisions
- Monthly: re-score full gold set, check for drift
- On threshold change: re-run gold set to verify improvement
- Add new examples to eval prompt when common failure modes are identified

### Active learning loop

```
New document → LLM scores → Decision made → [Random sample or YELLOW zone]
                                                      │
                                              Human reviews decision
                                                      │
                                              If LLM was wrong:
                                              ├── Add to gold set
                                              ├── Add as example in eval prompt
                                              └── Check if threshold needs adjustment
```

---

## Rejection Review System

Rejected documents are NOT in the RAG but ARE logged for periodic review.

**Storage:** `artifacts/research/rejected_log.jsonl`

```json
{
  "doc_id": "ext_2026-03-30_reddit_abc123",
  "timestamp": "2026-03-30T14:22:00Z",
  "source_type": "reddit",
  "title": "My strategy for polymarket crypto markets",
  "scores": {"relevance": 3, "novelty": 1, "actionability": 2, "credibility": 1},
  "total": 7,
  "reason": "Low novelty and credibility. Content is a basic description of buying YES when price drops, without data or specific parameters.",
  "eval_model": "gemini-flash"
}
```

**Weekly rejection audit (automated):**
- Cron job samples 10 random rejections from the past week
- DeepSeek V3 re-evaluates each: "Was this rejection correct?"
- If DeepSeek disagrees on 3+ documents, flag for human review
- Results logged to `artifacts/research/rejection_audits/`

**Manual promotion:**
```bash
# Review rejected documents
polytool research review-rejected --days 7

# Promote a wrongly rejected document
polytool research promote-rejected --doc-id ext_2026-03-30_reddit_abc123
```

---

## Deduplication

Before evaluation, check if the document is a near-duplicate of something already indexed.

**Method:** Compute embedding of the new document's text (first 512 tokens), compare
against all existing embeddings in `external_knowledge` partition using cosine similarity.

**Threshold:** >0.92 similarity = duplicate. Skip evaluation, log as duplicate.

**Why 0.92:** Empirically, documents above this threshold are either identical content
from different sources (same Reddit post shared on two subreddits) or trivially
rephrased versions. Below 0.92, documents are distinct enough to warrant separate
evaluation.

**Implementation:** Uses the same BGE-M3 embedding model as the main knowledge store.
The comparison is a single Chroma query with `include=["embeddings"]` — fast even at
scale.

---

## Implementation

```python
# packages/research/evaluation/evaluator.py

import json
from typing import Literal

class DocumentEvaluator:
    """Multi-model evaluation gate for incoming documents."""
    
    def __init__(self, config_path: str = "config/research_eval_prompt.md"):
        self.prompt_template = Path(config_path).read_text()
        self.gemini = GeminiFlashClient()   # primary
        self.deepseek = DeepSeekV3Client()  # escalation
        self.ollama = OllamaClient()        # fallback
    
    def evaluate(self, document: dict) -> dict:
        """Evaluate a document through the gate.
        
        Returns dict with gate decision, scores, summary, and metadata.
        """
        # Step 1: Deduplication (handled by caller)
        
        # Step 2 + 3: Score with primary model
        result = self._score_with_model(document, model="gemini")
        
        if result is None:
            # Gemini unavailable, try DeepSeek
            result = self._score_with_model(document, model="deepseek")
        
        if result is None:
            # Both cloud APIs down, fallback to Ollama
            result = self._score_with_model(document, model="ollama")
        
        if result is None:
            # All models unavailable
            return {"gate": "REVIEW", "reason": "all_models_unavailable"}
        
        # Step 4: Escalation for borderline cases
        total = result.get("total", 0)
        if 8 <= total <= 12 and result.get("eval_model") == "gemini-flash":
            escalation = self._score_with_model(document, model="deepseek")
            if escalation and escalation["total"] >= 12:
                result = escalation
                result["escalated"] = True
        
        # Step 5: Set gate decision
        if total >= 12:
            result["gate"] = "ACCEPT"
        elif total >= 8:
            result["gate"] = "REVIEW"
        else:
            result["gate"] = "REJECT"
        
        return result
    
    def _score_with_model(self, document: dict, model: str) -> dict | None:
        """Score a document with a specific model."""
        prompt = self._build_prompt(document)
        
        try:
            if model == "gemini":
                raw = self.gemini.generate(prompt, response_format="json")
                model_name = "gemini-flash"
            elif model == "deepseek":
                raw = self.deepseek.generate(prompt, response_format="json")
                model_name = "deepseek-v3"
            else:
                raw = self.ollama.generate(prompt, response_format="json")
                model_name = "ollama-local"
            
            result = json.loads(raw)
            result["eval_model"] = model_name
            result["total"] = sum([
                result.get("relevance", {}).get("score", 0),
                result.get("novelty", {}).get("score", 0),
                result.get("actionability", {}).get("score", 0),
                result.get("credibility", {}).get("score", 0),
            ])
            return result
        except Exception:
            return None
```

---

## Metrics

| Metric | Target | Alert If |
|--------|--------|----------|
| Accept rate | 50-70% | <30% or >90% |
| Human-LLM agreement (gold set) | >80% | <70% |
| Escalation rate (YELLOW zone) | 15-25% | >40% (too many borderlines) |
| Deduplication hit rate | <10% | >30% (source overlap too high) |
| Avg evaluation latency | <5s (Gemini) | >15s consistently |
| Rejection audit disagreement | <20% | >30% (evaluator drift) |

---

*End of RIS_03 — Evaluation Gate*
