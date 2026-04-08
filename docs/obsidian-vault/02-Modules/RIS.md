---
type: module
status: done
tags: [module, status/done, ris]
lines: 7000+
test-coverage: partial
created: 2026-04-08
---

# Research Intelligence System (RIS)

Source: audit Section 1.2 — `packages/research/` (6 subpackages).

RIS is the persistent knowledge base for research findings, academic papers, and operator-discovered insights. Before implementing a new strategy or feature, run `research-precheck` to surface known contradictions or blockers.

**Packaging gap:** `evaluation`, `ingestion`, `integration`, `monitoring`, and `synthesis` subpackages are NOT registered in `pyproject.toml`. They work via `sys.path` insertion but would not install correctly as a proper Python package. See [[Issue-Pyproject-Packaging-Gap]].

---

## Subpackage Inventory

### evaluation/

| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `evaluator.py` | 256 | Research item quality evaluator | WORKING |
| `providers.py` | 221 | LLM evaluation provider abstraction | WORKING |
| `models.py` | ~80 | Evaluation result dataclasses | WORKING |
| `cache.py` | ~120 | Evaluation result cache | WORKING |
| `config.py` | ~60 | Evaluation configuration | WORKING |
| `batch.py` | ~150 | Batch evaluation runner | WORKING |
| `prompts.py` | ~100 | LLM evaluation prompts | WORKING |

### hypotheses/

| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `registry.py` | 409 | Research hypothesis registry (SQLite-backed) | WORKING |

Note: There is also a JSON-backed hypothesis registry at `packages/polymarket/hypotheses/`. See [[Issue-Duplicate-Hypothesis-Registry]].

### ingestion/

| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `fetchers.py` | 859 | Content fetchers (web, ArXiv, Reddit, YouTube, etc.) | WORKING |
| `claim_extractor.py` | 661 | Claim extraction from research text | WORKING |
| `adapters.py` | 624 | Source adapters (academic, GitHub, blog, news, etc.) | WORKING |
| `extractors.py` | 536 | Document text extractors (PDF, HTML, etc.) | WORKING |
| `pipeline.py` | 347 | Full ingestion pipeline orchestration | WORKING |
| `seed.py` | 428 | Seed data and bootstrap content | WORKING |
| `deduplication.py` | ~200 | Near-duplicate detection | WORKING |
| `validators.py` | ~150 | Input validation for ingested content | WORKING |
| `models.py` | ~120 | Ingestion dataclasses | WORKING |
| `store.py` | ~180 | Ingestion result persistence | WORKING |

### integration/

| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `dossier_extractor.py` | 551 | Extract research findings from wallet dossiers | WORKING |
| `bridge.py` | ~200 | Research bridge — links findings to strategies | WORKING |
| `models.py` | ~80 | Integration dataclasses | WORKING |

### monitoring/

| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `health_checks.py` | 255 | RIS pipeline health checks | WORKING |
| `metrics.py` | ~150 | Pipeline metrics collection | WORKING |
| `alerts.py` | ~100 | Health alert triggers | WORKING |

### scheduling/

| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `scheduler.py` | 398 | APScheduler-based RIS job scheduler | WORKING |

### synthesis/

| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `report.py` | 686 | Research report generation | WORKING |
| `calibration.py` | 540 | Finding calibration and confidence scoring | WORKING |
| `precheck.py` | 438 | Pre-build precheck (STOP/CAUTION/GO verdicts) | WORKING |
| `report_ledger.py` | 430 | Report ledger — tracks generated reports | WORKING |
| `synthesizer.py` | ~300 | Multi-source finding synthesis | WORKING |
| `conflict_detector.py` | ~200 | Detects contradictions across findings | WORKING |
| `summary_builder.py` | ~180 | Summary text builder | WORKING |
| `formatter.py` | ~120 | Output formatting | WORKING |
| `models.py` | ~100 | Synthesis dataclasses | WORKING |

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `research-precheck` | Pre-build STOP/CAUTION/GO verdict |
| `research-ingest` | Ingest text/file research into RIS |
| `research-acquire` | Acquire URL-based research |
| `research-report` | Generate research synthesis report |
| `research-health` | RIS pipeline health snapshot |
| `research-stats` | RIS pipeline metrics |
| `research-scheduler` | APScheduler management |
| `research-bridge` | Link research findings to strategies |

---

## Dev Agent Pre-Build Workflow

Before starting any feature or strategy implementation:

1. `python -m polytool research-precheck run --idea "description" --no-ledger`
2. Interpret: STOP = do not proceed; CAUTION = proceed with awareness; GO = no blockers
3. For deeper context: `python -m polytool rag-query --question "topic" --hybrid --knowledge-store default`

---

## Cross-References

- [[RAG]] — ChromaDB + SQLite FTS5 retrieval layer
- [[LLM-Policy]] — Evaluation uses Tier 1 free LLM providers
- [[Issue-Pyproject-Packaging-Gap]] — 5 subpackages missing from pyproject.toml
- [[Issue-Duplicate-Hypothesis-Registry]] — JSON-backed vs SQLite-backed registry

