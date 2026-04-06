# RIS Implementation Audit Report

Date: 2026-04-04
Auditor: Claude Code (claude-sonnet-4-6)
Scope: RIS v1 — all layers, CLI, and infrastructure

---

## Executive Summary

RIS v1 is substantially implemented. The ingestion pipeline, evaluation gate (with
ManualProvider), knowledge store, synthesis layer, precheck, and all 14 CLI commands
exist as real working code — not stubs. Live CLI tests confirm the system is operational:
5 source documents stored, health checks returning real metrics, precheck returning
labelled results.

**Maturity by layer:**

| Layer | Maturity | Notes |
|-------|----------|-------|
| Layer 1: Ingestion | 85% | ArXiv, Reddit, YouTube, GitHub, Blog/News all functional; Twitter/X and SSRN absent |
| Layer 2: Evaluation Gate | 90% | All pipeline wired; ManualProvider works offline; cloud LLMs are v2 stubs |
| Layer 3: Knowledge Store | 80% | Full SQLite schema; contradiction tracking wired; Chroma is the RAG index only |
| Layer 4: Synthesis | 75% | Precheck, query planner, HyDE, report synthesizer all deterministic; LLM synthesis v2 |
| Infrastructure | 70% | Scheduler, health, run log all operational; Discord not wired; some health checks deferred |

**What works today (offline, no LLM required):**
- Document ingestion from files, text, URLs (ArXiv, GitHub, blog, news, Reddit, YouTube)
- Hard-stop evaluation gate + near-dedup check
- KnowledgeStore SQLite persistence (source_documents, derived_claims, claim_relations)
- Hybrid RAG query (semantic Chroma + FTS5 lexical + RRF fusion + optional reranking)
- Precheck (GO/CAUTION/STOP) with deterministic evidence scoring
- Research-report generation (deterministic, no LLM)
- APScheduler background ingestion jobs
- Health checks and run log metrics
- Hypothesis bridge and dossier extractor

**What requires a running LLM:**
- LLM-scored evaluation (without --no-eval flag, ManualProvider gives hardcoded scores)
- LLM-mode query planner (deterministic fallback exists)
- LLM-mode HyDE expansion (deterministic fallback exists)
- Cloud providers (Gemini, DeepSeek, OpenAI, Anthropic): explicitly "v2 deliverable", raise ValueError even with guard env var

**What is absent / planned:**
- Twitter/X source adapter or fetcher
- SSRN-specific adapter (AcademicAdapter only covers arXiv)
- Discord alert sink (generic WebhookSink exists; existing discord.py not wired)
- model_unavailable and rejection_audit_disagreement health checks (GREEN stubs)
- Grafana panels for RIS metrics
- ClickHouse tables for RIS data
- LLM-based report synthesis (DeepSeek V3, documented as v2)
- past_failures population in precheck (v2 via research partition query)
- Auto-promotion / Discord approval flow in hypothesis bridge

---

## Methodology

Read-only codebase inspection across all source files listed in the plan context.
No code was modified. Files inspected include:

**Layer 1 (11 files):** adapters.py, fetchers.py, pipeline.py, extractors.py,
claim_extractor.py, seed.py, normalize.py, source_cache.py, acquisition_review.py,
benchmark.py, retriever.py

**Layer 2 (9 files):** evaluator.py, scoring.py, providers.py, dedup.py, hard_stops.py,
feature_extraction.py, artifacts.py, replay.py, types.py

**Layer 3 (9 files):** knowledge_store.py, index.py, metadata.py, freshness.py,
lexical.py, chunker.py, embedder.py, query.py, reranker.py

**Layer 4 (7 files):** query_planner.py, hyde.py, retrieval.py, report.py, precheck.py,
precheck_ledger.py, calibration.py, report_ledger.py

**Infrastructure (7 files):** scheduler.py, health_checks.py, run_log.py, alert_sink.py,
metrics.py, hypothesis_bridge.py, validation_feedback.py, dossier_extractor.py

**CLI (14 files):** research_ingest.py, research_acquire.py, research_precheck.py,
research_health.py, research_stats.py, research_report.py, research_scheduler.py,
research_eval.py, research_seed.py, research_bridge.py, research_calibration.py,
research_dossier_extract.py, research_extract_claims.py, research_benchmark.py

Live verification: `python -m polytool research-health` and
`python -m polytool research-stats summary` both executed successfully.

---

## Layer 1: Ingestion

### Source Adapters (adapters.py)

ADAPTER_REGISTRY maps family name to adapter class. All registered adapters are
concrete implementations that call fetchers and return RawSourceDoc objects.

- **ArXiv:** [IMPLEMENTED] — AcademicAdapter calls ArXivFetcher; fetches Atom XML; returns title, abstract, authors, published_date. Resolves DOIs and arXiv IDs via normalize.py.
- **SSRN:** [PARTIAL] — No SSRN-specific adapter. AcademicAdapter handles "academic" family but its fetcher only calls ArXiv Atom API. SSRN URLs will not be fetched.
- **Reddit:** [IMPLEMENTED] — RedditAdapter registered; requires `praw` optional dep. Falls back gracefully if praw absent. Fetches top posts from subreddits.
- **Twitter/X:** [PLANNED] — No adapter. No fetcher. Not scheduled. Comment in scheduler.py explicitly notes Twitter excluded.
- **YouTube:** [IMPLEMENTED] — YouTubeAdapter registered; requires `yt-dlp` optional dep. Extracts VTT transcripts or description fallback.
- **Blog/RSS:** [IMPLEMENTED] — BlogAdapter registered; fetches via regex HTML parser (stdlib only, no BeautifulSoup). News domains auto-detected via known-domain set.
- **GitHub:** [IMPLEMENTED] — GitHubAdapter registered; uses GitHub REST API; GITHUB_TOKEN env var optional; falls back to unauthenticated for public repos.
- **Book/PDF:** [PARTIAL] — BookAdapter registered; fetch logic uses pdfplumber (optional) or python-docx (optional). Body extracted from local file or URL download. Dependency-gated.
- **Manual URL:** [IMPLEMENTED] — Handled via `research-acquire` CLI which routes to the appropriate adapter based on --source-family flag.
- **Dossier:** [IMPLEMENTED] — DossierAdapter registered; parses dossier artifact bundles (dossier.json, memo.md, hypothesis_candidates.json).

### Live Fetchers (fetchers.py)

All fetchers use stdlib urllib (no requests dependency). Injectable _http_fn/_subprocess_fn
for offline test isolation.

- ArXivFetcher: Fully implemented. Atom XML parsing; handles pagination; normalizes author list.
- GitHubFetcher: Fully implemented. REST API; README extraction; stars/forks metadata.
- BlogFetcher: Functional via regex HTML. No BeautifulSoup. Extracts title (h1/h2/title) and body (p tags). Quality varies for JS-heavy pages.
- NewsFetcher: Same as BlogFetcher with news domain routing.
- RedditFetcher: Functional when praw installed. Returns post title + selftext.
- YouTubeFetcher: Functional when yt-dlp installed. Transcript preferred, description fallback.
- No Twitter/X fetcher exists.

### Pipeline (pipeline.py)

[IMPLEMENTED] — IngestPipeline.ingest() and ingest_external() both exist and work.

End-to-end flow: ExtractText → HardStops → (optional) Evaluator → Chunk → Store → (optional) ClaimExtract.

IngestResult dataclass carries doc_id, chunk_count, gate_decision, rejected, reject_reason. Pipeline exits early on hard-stop rejection (gate=HARD_STOP). Evaluator is optional and skipped when --no-eval is passed.

### Text Extractors (extractors.py)

[IMPLEMENTED] — ExtractorRegistry with handlers for: .md/.txt (raw UTF-8), .pdf (pdfplumber optional), .docx (python-docx optional), and a fallback for plain text. Encoding detection with chardet (optional). Returns ExtractedText with title, body, metadata.

### Claim Extractor (claim_extractor.py)

[IMPLEMENTED — deterministic, no LLM] — EXTRACTOR_ID = "heuristic_v1". Pure regex/heuristic pipeline:
1. Split body into candidate sentences (period/exclamation/question split with min 20 chars)
2. Score by hedging-language patterns (confidence: 0.5–0.9)
3. Store DERIVED_CLAIM records in knowledge_store.derived_claims table
4. Build SUPPORTS/CONTRADICTS relations via shared key-term overlap

No LLM calls. All deterministic. Result: structured claims with confidence scores and source_document_id foreign keys.

---

## Layer 2: Evaluation Gate

### Binary Pre-Gate (hard_stops.py)

[IMPLEMENTED] — 4 hard-stop checks applied before any scoring:

1. `empty_body` — body is None or stripped empty string
2. `too_short` — body length < 50 characters
3. `encoding_garbage` — > 80% non-ASCII characters
4. `spam_malformed` — uppercase ratio > 60% or same URL repeated 4+ times

All checks return HardStopResult(triggered, reason_code). Pipeline checks these before calling the evaluator. Hard-stop rejections are final (no score produced).

### 4-Dimension Scoring (scoring.py)

[IMPLEMENTED — LLM-dependent for real scores] — 4 dimensions: relevance, novelty, actionability, credibility. Each scored 1–5. Total >= 12 → ACCEPT. Source-family credibility guidance baked into prompt.

SCORING_PROMPT_TEMPLATE_ID = "scoring_v1" for drift detection.

With ManualProvider (default): all dims = 3, total = 12, gate = ACCEPT. Every document passes.
With OllamaProvider: real LLM scores. Other providers: not implemented.

### Deduplication (dedup.py)

[IMPLEMENTED] — Two checks:

1. SHA256 exact-content hash (prevents identical reingestion)
2. Jaccard shingle near-dedup with default threshold **0.85**

**Spec discrepancy:** Feature docs reference 0.92 threshold. Code uses 0.85.
Operator should treat 0.85 as the operative value.

`check_near_duplicate(doc, existing_hashes, existing_shingles, threshold=0.85)` — returns DedupResult(is_duplicate, reason, similarity_score).

### Multi-Model Routing (providers.py)

[PARTIAL] — Registered providers:

- `manual`: ManualProvider — hardcoded placeholder scores. Works fully offline. Default.
- `ollama`: OllamaProvider — local Ollama via urllib; default model `qwen3:30b`. Works if Ollama running.
- `gemini`: raises ValueError — "Gemini provider is a RIS v2 deliverable"
- `deepseek`: raises ValueError — "DeepSeek provider is a RIS v2 deliverable"
- `openai`: raises ValueError — "OpenAI provider is a RIS v2 deliverable"
- `anthropic`: raises ValueError — "Anthropic provider is a RIS v2 deliverable"

`get_provider_metadata()` exists for replay-grade audit captures. Eval replay infrastructure exists in replay.py.

### Feature Extraction (feature_extraction.py)

[IMPLEMENTED] — Deterministic features extracted before LLM scoring:

- word_count, sentence_count, avg_sentence_length
- hedge_density (probability language detection)
- numeric_density (quantitative evidence)
- citation_density (reference patterns)
- polymarket_relevance (keyword overlap with prediction market domain)
- recency_signal (year mentions, "2024"/"2025" patterns)

All features are deterministic and offline. Stored in evaluation artifacts.

---

## Layer 3: Knowledge Store

### Architecture Note

**The KnowledgeStore is NOT Chroma.** The `packages/polymarket/rag/` directory contains
two separate systems:

- `knowledge_store.py`: SQLite-backed store for source_documents and derived_claims
- `index.py`: Chroma-backed semantic index for vector search

Both are used. KnowledgeStore.store_document() writes to SQLite and then calls
ChromaIndex.add() to populate the vector index. They share document IDs.

### Chroma Collection (index.py)

[IMPLEMENTED] — Collection name: `polytool_brain`. Default embedding model: all-MiniLM-L6-v2
(SentenceTransformers). 384-dimensional embeddings. Privacy-scoped metadata filtering
applied at query time. Chroma operates in persistent local mode (no server required).

### Metadata Schema (metadata.py)

[IMPLEMENTED] — Full field set defined:

- doc_id (SHA256-based deterministic), source_type, source_url, title, author
- published_at, ingested_at, trust_tier, privacy_scope
- chunk_index, chunk_count, token_count
- eval_score, eval_gate, eval_provider, eval_model
- freshness_modifier (float, computed at query time)

Privacy scoping: metadata.privacy_scope filters are applied at both Chroma query layer
and FTS5 lexical layer.

### DERIVED_CLAIM Objects (knowledge_store.py)

[IMPLEMENTED] — SQLite tables:

- `source_documents`: full document metadata + body text
- `derived_claims`: claim_id, source_document_id, claim_text, confidence, trust_tier, extractor_id
- `claim_evidence`: many-to-many claim-to-document provenance
- `claim_relations`: typed relations (SUPPORTS, CONTRADICTS, SUPERSEDES, EXTENDS)

### Contradiction Tracking

[IMPLEMENTED] — `find_contradictions()` method on KnowledgeStore queries
claim_relations WHERE relation_type = 'CONTRADICTS'. Returns list of dicts with
claim_text, contradicts_claim_text, and source IDs. Wired into precheck.py's
`find_contradictions()` call.

### Freshness Decay (freshness.py)

[IMPLEMENTED] — Exponential decay modifier loaded from `config/freshness_decay.json`.
Per-source-family half-life values. `compute_freshness_modifier(family, published_at)`
returns float 0–1. Applied at query time to downweight stale evidence. LRU-cached config
load. Pure function (no I/O except config read).

---

## Layer 4: Synthesis

### Query Planner (query_planner.py)

[IMPLEMENTED] — Two modes:

1. **Deterministic:** 5 angle prefixes ("evidence for", "risks of", "alternatives to",
   "recent developments in", "key assumptions behind") crossed with the topic. Always works.
2. **LLM mode:** Sends JSON prompt; falls back to deterministic on parse failure.

`QueryPlan` dataclass includes `was_fallback` flag to signal which mode ran.
Single-hop only in v1. Multi-hop query planning is v2.

### HyDE (hyde.py)

[IMPLEMENTED] — Two modes:

1. **Deterministic template:** Generic 3-sentence hypothetical passage incorporating query text. Offline, always works.
2. **LLM mode:** Calls provider; falls back to template on error.

`HydeResult` dataclass with was_fallback flag.

### RAG Retrieval (retrieval.py)

[IMPLEMENTED] — Full hybrid retrieval pipeline:
- Semantic search via ChromaIndex
- Lexical search via FTS5 (SQLite)
- RRF fusion (k=60 per paper standard)
- Optional cross-encoder reranking (--hybrid --rerank)
- Privacy-scoped filtering at both layers

`query_knowledge_store_enriched()` returns claims with freshness notes,
contradiction flags, contradiction_summary, and provenance_docs.

### Report Synthesizer (report.py)

[IMPLEMENTED — deterministic only] — ReportSynthesizer class produces:
- `ResearchBrief`: topic summary, key findings, contradictions, actionability, knowledge gaps, cited sources
- `EnhancedPrecheck`: supporting/contradicting evidence lists with full citations

All synthesis is deterministic. No LLM calls. Comment in source: "LLM-based synthesis (DeepSeek V3) is a v2 feature."

### Precheck (precheck.py)

[IMPLEMENTED] — `run_precheck()` returns `PrecheckResult` with:
- `recommendation`: GO / CAUTION / STOP
- `reason_code`: STRONG_SUPPORT / MIXED_EVIDENCE / FUNDAMENTAL_BLOCKER
- `precheck_id`: 12-char SHA256
- `evidence_gap`, `review_horizon` (7d/30d/"")
- `stale_warning`: True only when ALL documents are stale

Logic:
- ManualProvider path always returns CAUTION (hardcoded placeholder)
- OllamaProvider: real reasoning
- Contradiction check via KnowledgeStore.find_contradictions()
- Staleness check via freshness decay

Lifecycle fields (was_overridden, outcome_label, promoted_to_hypothesis) are NOT
populated by run_precheck() — populated only by ledger hydration.

### Override Artifacts (precheck_ledger.py)

[IMPLEMENTED] — SQLite ledger at `kb/rag/knowledge/precheck_ledger.sqlite3`.
Tracks precheck history with override audit trail. `list_overrides()` and
`inspect_ledger()` exposed via `research-precheck inspect` CLI. Full provenance
for operator override decisions.

---

## Infrastructure

### APScheduler (scheduler.py)

[IMPLEMENTED] — JOB_REGISTRY with 8 defined jobs:

| Job | Schedule | Family |
|-----|----------|--------|
| academic_ingest | Every 12 hours | academic |
| reddit_polymarket | Every 6 hours | reddit |
| reddit_others | Daily | reddit |
| blog_ingest | Every 4 hours | blog |
| youtube_ingest | Weekly (Mon) | youtube |
| github_ingest | Weekly (Wed) | github |
| freshness_refresh | Weekly (Sun) | (meta) |
| weekly_digest | Weekly (Sun) | (meta) |

Twitter/X explicitly excluded with comment. APScheduler CronTrigger used. Each job
calls `run_job()` which logs to run_log.jsonl. `start_research_scheduler()` fires
all registered jobs.

### CLI Commands

All 14 research CLI commands exist in tools/cli/. All expose `main(argv) -> int`.

| Command | Status | Notes |
|---------|--------|-------|
| research-ingest | IMPLEMENTED | file, text, --from-adapter paths; --extract-claims opt-in |
| research-acquire | IMPLEMENTED | --url --source-family; routes to adapters |
| research-precheck | IMPLEMENTED | run, inspect subcommands; GO/CAUTION/STOP |
| research-health | IMPLEMENTED | Returns real health check results |
| research-stats | IMPLEMENTED | summary, docs, claims subcommands |
| research-report | IMPLEMENTED | Deterministic report from knowledge store |
| research-scheduler | IMPLEMENTED | start, status, run-job subcommands |
| research-eval | IMPLEMENTED | Standalone evaluation of a document |
| research-seed | IMPLEMENTED | Seeds starter documents into knowledge store |
| research-bridge | IMPLEMENTED | Registers hypotheses to SimTrader registry |
| research-calibration | IMPLEMENTED | Calibration records for evaluation drift |
| research-dossier-extract | IMPLEMENTED | Extracts findings from wallet dossiers |
| research-extract-claims | IMPLEMENTED | Runs claim extraction on stored documents |
| research-benchmark | IMPLEMENTED | Benchmarks ingestion throughput |

Verified live: `research-health` and `research-stats summary` both returned real data.

### Grafana Panels

[PLANNED] — No Grafana dashboards for RIS metrics exist in `infra/grafana/dashboards/`.
No reference to RIS-specific panels found in any dashboard JSON. RIS metrics are visible
only via CLI (`research-health`, `research-stats`).

### ClickHouse Tables

[PLANNED] — No ClickHouse tables for RIS data. KnowledgeStore uses SQLite exclusively.
Run log is JSONL file. Health data is in-memory or JSONL. No CH schema migrations
for RIS in `infra/clickhouse/initdb/`.

### Discord Alerts (alert_sink.py)

[PARTIAL] — `AlertSink` protocol, `LogSink` (default, logs to Python logger), and
`WebhookSink` (generic HTTP webhook) exist. LogSink is the default and requires no
configuration.

**Key gap:** The existing `packages/polymarket/notifications/discord.py` module (with
`notify_gate_result`, `notify_session_start`, etc.) is **not wired** to the research
alert sink. Research alerts go to LogSink by default. To get Discord alerts, operator
must configure `WebhookSink` manually with Discord webhook URL; the research system
does NOT automatically use the discord.py integration already in the repo.

---

## Cross-Cutting Concerns

### Offline-First Compliance

RIS v1 is largely offline-first. The following components require no network access
when not explicitly using LLM providers:

- All hard-stop checks
- ManualProvider evaluation (hardcoded, no network)
- KnowledgeStore SQLite read/write
- Chroma vector index (local persistent mode)
- FTS5 lexical index
- Freshness decay computation
- Precheck (with ManualProvider fallback)
- Report synthesis (deterministic)
- Health checks and run log

Network-dependent operations (opt-in or configured):
- ArXiv fetcher (HTTP to arxiv.org)
- GitHub fetcher (HTTP to api.github.com)
- Blog/News fetcher (HTTP to target URL)
- Reddit fetcher (praw API)
- YouTube fetcher (yt-dlp subprocess)
- OllamaProvider (HTTP to localhost:11434)
- WebhookSink (HTTP to webhook URL)

### Test Coverage

Test files matching research, ris, rag, or knowledge patterns were collected.
Command: `python -m pytest tests/ -k "research or ris or rag or precheck or knowledge" --collect-only -q`

Results: **206 tests collected** across the RIS and RAG test suite.
Key test files: test_research_pipeline.py, test_research_evaluation.py, test_rag_knowledge_store.py,
test_research_precheck.py, test_research_synthesis.py, test_research_scheduling.py.

---

## Gap Summary Table

| Component | Status | Notes |
|-----------|--------|-------|
| ArXiv adapter + fetcher | IMPLEMENTED | urllib, Atom XML, no deps |
| SSRN adapter | PARTIAL | No fetcher; falls back to generic academic |
| Reddit adapter + fetcher | IMPLEMENTED | Requires praw optional dep |
| Twitter/X adapter | PLANNED | No code exists |
| YouTube adapter + fetcher | IMPLEMENTED | Requires yt-dlp optional dep |
| Blog/News adapter + fetcher | IMPLEMENTED | Regex HTML, stdlib only |
| GitHub adapter + fetcher | IMPLEMENTED | REST API, GITHUB_TOKEN optional |
| Book/PDF adapter | PARTIAL | Requires pdfplumber / python-docx |
| Dossier adapter | IMPLEMENTED | Parses dossier.json artifacts |
| Ingest pipeline | IMPLEMENTED | Full extract/eval/chunk/store flow |
| Text extractors | IMPLEMENTED | .md, .txt, .pdf (opt), .docx (opt) |
| Claim extractor | IMPLEMENTED | Heuristic v1, deterministic, no LLM |
| Metadata normalization | IMPLEMENTED | URL canonicalization, canonical IDs |
| Hard-stop gate | IMPLEMENTED | 4 checks wired |
| 4-dimension scoring | IMPLEMENTED | ManualProvider default; OllamaProvider opt-in |
| Deduplication | IMPLEMENTED | SHA256 + Jaccard; threshold 0.85 (not 0.92) |
| ManualProvider | IMPLEMENTED | Hardcoded placeholder, offline |
| OllamaProvider | IMPLEMENTED | Local Ollama, requires Ollama running |
| Cloud LLM providers | PLANNED | Gemini/DeepSeek/OpenAI/Anthropic raise ValueError |
| Feature extraction | IMPLEMENTED | Deterministic pre-LLM features |
| Eval replay | IMPLEMENTED | Replay artifacts and metadata capture |
| KnowledgeStore (SQLite) | IMPLEMENTED | 4-table schema, fully functional |
| Chroma index | IMPLEMENTED | local persistent, all-MiniLM-L6-v2 |
| FTS5 lexical index | IMPLEMENTED | SQLite FTS5, privacy-scoped |
| Derived claims table | IMPLEMENTED | claim_text, confidence, extractor_id |
| Contradiction tracking | IMPLEMENTED | CONTRADICTS relations queryable |
| Freshness decay | IMPLEMENTED | Per-family half-lives from config JSON |
| Metadata schema | IMPLEMENTED | Full field set including trust_tier |
| Query planner | IMPLEMENTED | Deterministic 5-angle; LLM fallback |
| HyDE | IMPLEMENTED | Template deterministic; LLM fallback |
| RAG retrieval (hybrid) | IMPLEMENTED | Semantic + FTS5 + RRF + optional rerank |
| Report synthesizer | IMPLEMENTED | Deterministic; LLM synthesis is v2 |
| Precheck (GO/CAUTION/STOP) | IMPLEMENTED | Wired, labelled results |
| Precheck ledger | IMPLEMENTED | Override audit trail in SQLite |
| APScheduler | IMPLEMENTED | 8 jobs registered |
| Health checks | PARTIAL | 2 of 6 checks are GREEN stubs |
| Run log | IMPLEMENTED | JSONL file, append_run() |
| Alert sink | PARTIAL | LogSink default; discord.py NOT wired |
| Hypothesis bridge | IMPLEMENTED | brief_to_candidate, register_hypothesis |
| Dossier extractor | IMPLEMENTED | batch_extract_dossiers, ingest_dossier_findings |
| Validation feedback | IMPLEMENTED | outcome_label, promoted_to_hypothesis |
| Calibration | IMPLEMENTED | EvalCalibrationRecord, drift detection |
| Grafana panels | PLANNED | No RIS dashboards exist |
| ClickHouse tables | PLANNED | No RIS schema in CH |
| Discord alerts integration | PARTIAL | WebhookSink not wired to discord.py |
| Twitter/X source | PLANNED | No adapter, fetcher, or schedule |
| Cloud LLM eval providers | PLANNED | All raise ValueError, v2 deliverable |
| LLM-based report synthesis | PLANNED | DeepSeek V3, v2 deliverable |
| Multi-hop query planner | PLANNED | v2 |
| past_failures in precheck | PLANNED | v2 via research partition query |
