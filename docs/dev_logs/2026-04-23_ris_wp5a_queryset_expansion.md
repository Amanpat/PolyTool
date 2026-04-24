---
date: 2026-04-23
slug: ris_wp5a_queryset_expansion
type: data
scope: docs/eval only
feature: RIS Phase 2A — WP5-A Retrieval Benchmark Query Expansion
---

# RIS WP5-A — Retrieval Benchmark Query Set Expansion

## Objective

Expand `docs/eval/ris_retrieval_benchmark.jsonl` from 9 queries (3 classes) to 30+ queries
covering all five roadmap-specified classes: `factual`, `conceptual`, `cross-document`,
`paraphrase`, `negative-control`.

No code, config, infra, or workflow changes. Data-only work packet.

---

## File Changed

**`docs/eval/ris_retrieval_benchmark.jsonl`**

Previous state: 9 entries, classes `factual`×3, `analytical`×3, `exploratory`×3.  
New state: 31 entries across all 5 roadmap classes.

---

## What Changed and Why

### Class taxonomy migration

The prior 9 queries used `analytical` and `exploratory` — neither appears in the roadmap's
five-class specification. Since no baseline has been frozen yet (WP5-D not done), re-labeling
before baseline lock is the correct move. Waiting would bake in non-canonical class names.

| Old class | Disposition | New class |
|---|---|---|
| `factual` × 3 | Kept as-is | `factual` × 3 |
| `analytical` × 3 | Re-labeled | `conceptual` × 3 |
| `exploratory` × 2 | Re-labeled | `conceptual` × 2 |
| `exploratory` × 1 ("What approaches exist for market selection scoring?") | Re-labeled | `factual` × 1 |

Labels were updated to match (`mm-inventory-risk-analytical` → `mm-inventory-risk-conceptual`, etc.).
No query text was altered.

### Queries removed

None. All 9 original queries were preserved (with class/label corrections).

### New queries added: 22

| Class | New count | Total |
|---|---|---|
| `factual` | +2 (gate2 threshold, default scheduler) | 6 |
| `conceptual` | +2 (logit-space rationale, RIS eval gate) | 7 |
| `cross-document` | +6 | 6 |
| `paraphrase` | +6 | 6 |
| `negative-control` | +6 | 6 |
| **TOTAL** | **+22** | **31** |

---

## Final Query Count and Per-Class Distribution

| Class | Count |
|---|---|
| `factual` | 6 |
| `conceptual` | 7 |
| `cross-document` | 6 |
| `paraphrase` | 6 |
| `negative-control` | 6 |
| **TOTAL** | **31** |

All five roadmap classes present. 30+ threshold met.

---

## Query Design Notes

### factual
Direct lookup of specific project facts: ClickHouse schema, fee model, tape tier definitions,
7-factor market scorer, Gate 2 pass threshold (70%), APScheduler default. All grounded in
CLAUDE.md and ARCHITECTURE.md content that should be in the knowledge store.

### conceptual
Abstracted understanding: how inventory risk works, tape tier tradeoffs, gate/capital
interaction, prediction market strategies, how research informs trading, why logit space
for bounded markets, how the RIS eval gate classifies documents. These require synthesizing
rather than recalling a single fact.

### cross-document
Each query explicitly requires combining 2+ separate docs:
- Crypto pair bot + benchmark validation pipeline
- Gate 2 failure + WAIT_FOR_CRYPTO ADR
- Fee model + Gate 2 threshold (combined viability test)
- Market selection engine + shadow runner
- RIS knowledge store + research-precheck workflow
- Tape tier quality (Silver/no L2 book) + Gate 2 fill diagnosis

### paraphrase
Semantically equivalent rewording of one existing query per entry:
- fee-model-factual → fee-model-paraphrase (charges framing)
- clickhouse-schema-factual → clickhouse-streaming-paraphrase (write-target framing)
- mm-inventory-risk-conceptual → mm-position-management-paraphrase (adverse-condition framing)
- tape-tiers-factual → tape-tier-distinction-paraphrase (distinguishing characteristics framing)
- gate-capital-interaction-conceptual → live-capital-requirements-paraphrase (strategy-centric framing)
- market-selection-factual → market-ranking-paraphrase (prioritization framing)

### negative-control
Clearly out-of-scope topics that a well-calibrated retriever should not return strong matches for.
All 6 are plausible research questions in general but have no relevant content in the
PolyTool/RIS knowledge store (which covers prediction markets, trading strategy, and related research):
- Crypto exchange regulatory filings
- TCP/IP three-way handshake
- NLP sentiment classification architectures
- European GDPR regulation
- Bitcoin proof-of-work consensus
- Clinical drug trial statistics

These test that the retriever does not hallucinate relevance for genuinely OOS queries.

---

## Commands Run and Validation Results

```
python -m polytool --help
```
**Result:** Exit 0. CLI loads cleanly. No import errors.

```python
python -c "
import json, collections
lines = [l for l in open('docs/eval/ris_retrieval_benchmark.jsonl', encoding='utf-8') if l.strip()]
parsed = [json.loads(l) for l in lines]
print(f'JSONL parses cleanly: {len(parsed)} entries')
counts = collections.Counter(e['query_class'] for e in parsed)
for cls, n in sorted(counts.items()):
    print(f'  {cls}: {n}')
print(f'  TOTAL: {sum(counts.values())}')
classes = set(counts.keys())
required = {'factual', 'conceptual', 'cross-document', 'paraphrase', 'negative-control'}
print(f'Required classes present: {required <= classes}')
print(f'30+ threshold met: {sum(counts.values()) >= 30}')
"
```

**Result:**
```
JSONL parses cleanly: 31 entries
  conceptual: 7
  cross-document: 6
  factual: 6
  negative-control: 6
  paraphrase: 6
  TOTAL: 31
Required classes present: True
30+ threshold met: True
```

All acceptance criteria met.

---

## WP5-A Acceptance Checklist

- [x] `docs/eval/ris_retrieval_benchmark.jsonl` has 30+ queries (31 total)
- [x] All five roadmap classes present: `factual`, `conceptual`, `cross-document`, `paraphrase`, `negative-control`
- [x] Query text is realistic and grounded in RIS/PolyTool corpus themes
- [x] Class labels are explicit and consistent across all 31 entries
- [x] Negative-controls are clearly out-of-scope
- [x] No existing good queries removed (9 originals preserved with class corrections)
- [x] Schema preserved exactly (query, query_class, filters, expect, label)
- [x] JSONL parses cleanly (0 parse errors)
- [x] CLI still loads (smoke test passed)
- [x] `docs/eval/sample_queries.jsonl` not touched
- [x] No code changes, no config changes, no infra changes

---

## Recommendation: What Goes Next

**WP5-B (Precision@5) should go next, before WP5-D (baseline save).**

Rationale:
- WP5-D requires a baseline to be meaningful. That baseline should include P@5, not just Recall@k and MRR@k. Running WP5-D before WP5-B locks in an incomplete metric set.
- WP5-C (segmented per-class reporting) is already done — the eval harness already propagates `query_class` through `EvalReport.per_class_modes`. No action needed.
- The correct order is: **WP5-A** (done) → **WP5-B** (add P@5) → **WP5-D** (save baseline with full metrics).

WP5-B implementation targets per the context fetch log (`2026-04-23_ris_wp5_context_fetch.md`):
- `packages/polymarket/rag/eval.py`: add `precision_at_5` to `ModeAggregate`, `_eval_single`, `_build_aggregate`, `write_report`
- `tools/cli/rag_eval.py`: add Precision@5 column to `_print_mode_table`
- `tests/test_rag_eval.py`: add tests following `_FakeEmbedder`/`_EvalIndexHelper` pattern

---

## Codex Review Note

No application code was changed. Codex review not applicable.
