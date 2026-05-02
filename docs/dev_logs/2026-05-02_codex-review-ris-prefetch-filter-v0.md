# Codex Review: RIS L3 Pre-fetch Filter v0

**Date:** 2026-05-02
**Reviewer:** Codex
**Verdict:** FAIL
**Safety state:** Safe for benchmark/dry-run simulation only. Not enforce-ready.

---

## Scope Reviewed

Reviewed Prompt A implementation and Prompt B packet/docs activation state:

- `git diff`
- `packages/research/relevance_filter/__init__.py`
- `packages/research/relevance_filter/scorer.py`
- `config/research_relevance_filter_v1.json`
- `tools/cli/research_eval_benchmark.py`
- `tools/cli/research_acquire.py`
- `tests/test_ris_relevance_filter.py`
- `tests/test_ris_eval_benchmark.py`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Pre-fetch SVM Topic Filter.md`
- `docs/obsidian-vault/Claude Desktop/Current-Focus.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/runbooks/research_eval_benchmark.md`
- `docs/INDEX.md`
- `docs/dev_logs/2026-05-01_ris-prefetch-filter-packet-activation.md`
- `docs/dev_logs/2026-05-02_ris-prefetch-filter-coldstart.md`

Prompt A code is in commit `14a15a8 feat(ris): L3 cold-start lexical relevance filter with corpus simulation`.
Prompt B working diff is documentation/Obsidian state only.

---

## Commands Run

### Session-state checks

`git status --short`

```text
 M docs/CURRENT_DEVELOPMENT.md
 M docs/obsidian-vault/.obsidian/workspace.json
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_08-Research_11-Scientific-RAG-Target-Architecture_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Marker_Structural_Parser_Integration_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Pre-fetch_SVM_Topic_Filter_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Scientific_RAG_Evaluation_Benchmark_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
 M "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Pre-fetch SVM Topic Filter.md"
 M "docs/obsidian-vault/Claude Desktop/Current-Focus.md"
 M docs/runbooks/research_eval_benchmark.md
?? docs/dev_logs/2026-05-01_ris-prefetch-filter-packet-activation.md
?? docs/dev_logs/2026-05-02_ris-eval-benchmark-golden-qa-finalized.md
?? docs/dev_logs/2026-05-02_ris-eval-benchmark-v0-closeout.md
?? docs/features/FEATURE-ris-scientific-eval-benchmark-v0.md
?? tests/fixtures/research_eval_benchmark/golden_qa_v0.json
```

`git log --oneline -5`

```text
14a15a8 feat(ris): L3 cold-start lexical relevance filter with corpus simulation
7df7b9f feat(ris): scoped lexical refresh for L5 benchmark corpus
0646a68 feat(ris): L5 QA review pack - 35 verified candidate QA pairs for baseline
a15d560 fix(ris): Harden L5 eval benchmark v0 - apply all Codex fixes and run first draft
a8b8664 feat(ris): Scientific RAG Evaluation Benchmark v0 core infrastructure
```

`python -m polytool --help`

```text
Exit code 0. CLI loaded. research-eval-benchmark and research-acquire commands are present.
```

### Requested review commands

`python -m pytest tests/test_ris_relevance_filter.py tests/test_ris_eval_benchmark.py`

```text
collected 102 items
102 passed in 1.02s
```

`python -m polytool research-eval-benchmark --corpus v0 --simulate-prefetch-filter`

```text
PREFETCH FILTER SIMULATION REPORT
Filter config version : v1
Allow threshold       : 0.55
Review threshold      : 0.35
Corpus entries        : 23
Docs loaded from DB   : 23

Baseline off-topic count/rate: 7 / 23, 30.43%
Filter decisions: ALLOW 20, REVIEW 0, REJECT 3
Scenario A (reject excluded, review included): 20.0% [20 docs]
Scenario B (reject+review excluded): 20.0% [20 docs]
Target <10% off_topic (scenario B): NO (20.0%)
```

`python -m polytool research-eval-benchmark --corpus v0 --golden-set v0 --simulate-prefetch-filter`

```text
Filter decisions: ALLOW 20, REVIEW 0, REJECT 3
Scenario A (reject excluded, review included): 20.0% [20 docs]
Scenario B (reject+review excluded): 20.0% [20 docs]
QA paper source_ids tracked : 10
QA papers in REJECT         : 0
QA papers in REVIEW         : 0
Target <10% off_topic (scenario B): NO (20.0%)
```

`python -m polytool research-acquire --help`

```text
Exit code 0. Help lists --url, --search, --max-results, --source-family, --cache-dir, --review-dir, --db, --no-eval, --dry-run, --json, --provider, --priority-tier, --extract-claims, --run-log.
No relevance filter, relevance dry-run/audit, filter config, or --enforce-relevance-filter option is present.
```

Dependency check:

`Select-String -Path pyproject.toml,requirements*.txt -Pattern "specter|s2fos|scikit|sklearn|sentence-transformers|torch|transformers"`

```text
pyproject.toml:33:    "sentence-transformers>=2.2.0",
requirements-rag.txt:1:sentence-transformers
requirements-rag.txt:2:torch
```

No Prompt A/Preset L3 dependency-file changes were found. Existing `sentence-transformers`/`torch` entries are pre-existing RAG dependencies, not new L3 filter dependencies.

### Diagnostic command

Computed the off-topic rows that remain in the allow-only scenario:

```text
{'off_topic_count': 4, 'total': 20, 'off_topic_rate_pct': 20.0}
82267d0774e149cc26ae32da513668f86644665aa481f96719ff3346254a3509 | On a Class of Diverse Market Models
9495ffda89417b8ef55a85c0a4f5f1233b4c68cea77536d3e466549a08ddc599 | The Inelastic Market Hypothesis: A Microstructural Interpretation
6e911b4fbe2c041440a6eab4d7ef9de74c2d5b150440c835f2a37f6a8952c1b5 | How Market Ecology Explains Market Malfunction
4f5c91b1fe0abb14cdf5c2dbeba186ce0973bc3f9202b3b2dd7adfacabc13108 | Uncovering the Internal Structure of the Indian Financial Market: Cross-correlation behavior in the NSE
```

---

## Findings

### Blocking

1. **L3 impact gate fails on the real replay.**

   The packet requires simulated post-filter `off_topic_rate < 10%`. The actual command returns Scenario A = `20.0%` and Scenario B = `20.0%`. The earlier dev log and INDEX entry claim a title-only Scenario B projection of `6.25%`, but the DB-backed replay with abstracts does not reproduce it.

   Why: only the three clear negatives are rejected. Four remaining off-topic/ambiguous rows are still allowed because broad weak positives such as `financial market`, `arbitrage`, `microstructure`, and `liquidity` push scores above the current `allow_threshold=0.55`.

   Exact fix:
   - Tune `config/research_relevance_filter_v1.json` so a single generic finance term cannot produce `ALLOW`.
   - A minimal calibration to test is `allow_threshold=0.80` while keeping `review_threshold=0.35`; in a diagnostic run this produced `ALLOW=17`, `REVIEW=3`, `REJECT=3`, Scenario B `5.88%`, and QA `REJECT=0`.
   - Re-run `python -m polytool research-eval-benchmark --corpus v0 --golden-set v0 --simulate-prefetch-filter`.
   - Do not claim the packet passes until the DB-backed command, not the title-only estimate, prints `Target <10% off_topic (scenario B): YES`.

2. **`research-acquire` is not wired to the filter.**

   The implementation creates a scorer and benchmark simulation, but `tools/cli/research_acquire.py` has no relevance-filter flag, config option, dry-run/audit output, enforce flag, or decision logging path. The help output confirms there is no `--enforce-relevance-filter` or equivalent.

   Exact fix:
   - Add explicit acquisition options, with enforcement off by default:
     - `--relevance-filter-dry-run` or `--relevance-filter-audit`
     - `--enforce-relevance-filter`
     - `--relevance-filter-config PATH`
   - For academic search results, score candidate `title + abstract` before PDF/body fetch or ingest.
   - In default/non-enforce mode, log the decision and continue ingestion.
   - In enforce mode, only block according to the documented policy. Until the review-vs-reject policy is settled, block `reject` only and route `review` to audit/review rather than silently dropping it.
   - Add `research-acquire --help` coverage proving enforcement remains opt-in.

3. **Auditability is incomplete for reject/review decisions.**

   `FilterDecision` contains `score`, `raw_score`, `reason_codes`, and `matched_terms`, but it does not carry the applied `allow_threshold` or `review_threshold`. The benchmark per-paper result omits `raw_score`, `matched_terms`, and thresholds, and the human report truncates reason codes to the first three terms. There is no persistent acquisition decision log.

   Exact fix:
   - Extend `FilterDecision` or the serialized audit record to include `allow_threshold`, `review_threshold`, and `config_version`.
   - In `tools/cli/research_eval_benchmark.py`, store/print full `reason_codes`, `matched_terms`, `raw_score`, `allow_threshold`, and `review_threshold` for every `REVIEW` and `REJECT` row at minimum.
   - Add a JSONL audit writer for acquisition decisions with fields:
     `source_id`, `source_url`, `title`, `decision`, `score`, `raw_score`, `allow_threshold`, `review_threshold`, `reason_codes`, `matched_terms`, `config_version`, `timestamp`, `enforced`.
   - Add offline tests that assert these fields exist on rejected/reviewed candidates.

### Major

4. **Tests do not cover the new replay/CLI path.**

   `tests/test_ris_relevance_filter.py` covers scoring, thresholds, determinism, and title-based false-negative protection. `tests/test_ris_eval_benchmark.py` has CLI tests, but no test mentions `--simulate-prefetch-filter`, `_run_simulate_prefetch_filter`, `--filter-config`, or the target `<10%` reporting path.

   Exact fix:
   - Add offline tests in `tests/test_ris_eval_benchmark.py` for:
     - `main([... "--simulate-prefetch-filter" ...])` exits 0 with a temp corpus/DB.
     - Missing `--filter-config` exits 1.
     - The simulation report includes thresholds, reason codes, matched terms, and remaining off-topic rows when target is not met.
     - A calibrated fixture produces `Target <10% ... YES`.

5. **Docs overclaim activation/verification state.**

   `docs/dev_logs/2026-05-02_ris-prefetch-filter-coldstart.md` says Scenario B reaches `<10%` based on a title-only estimate, and `docs/INDEX.md` repeats "projected scenario-B off_topic_rate 6.25%". The actual requested replay returns `20.0%` and `NO`.

   Exact fix:
   - Update both docs to distinguish "title-only estimate" from "DB-backed replay".
   - Replace the `6.25%` pass claim with the verified current result: Scenario A `20.0%`, Scenario B `20.0%`, target `NO`.
   - Add the four allowed off-topic rows listed above as the reason the impact gate fails.

6. **Current feature state still says Prompt A is pending.**

   `docs/CURRENT_DEVELOPMENT.md` Feature 3 says "packet refined and handed to Prompt A for implementation" and "Current step: Implement ... in research-acquire", while Prompt A has already landed a partial implementation. `Current-Focus.md` frontmatter still says `updated: 2026-05-01` while it records L5 as shipped on 2026-05-02.

   Exact fix:
   - Update Feature 3 status to "partial implementation under review; benchmark scorer exists; acquisition integration and audit logging incomplete".
   - Keep the feature Active, not Recently Completed.
   - Bump `last_updated` / `updated` to 2026-05-02.
   - Leave DoD boxes unchecked for research-acquire integration, simulated `<10%`, decision log, label store, health counter, feature doc, and CURRENT_STATE update.

### Non-blocking

7. **Generated Obsidian smart-env files include unrelated cache churn.**

   The working diff includes `.smart-env` cache updates for Marker and Scientific RAG notes. No behavior files for Marker, PaperQA2, harvesters, parser, n8n, or trading were changed, so this is not a code-scope violation. It is still noisy for review.

   Exact fix:
   - Before committing Prompt B docs, either confirm these generated cache files are intentionally tracked or leave them out of the commit if they are incidental editor cache churn.

8. **The cold-start dev log says Codex review was skipped because no execution-path code changed.**

   Prompt A changed `tools/cli/research_eval_benchmark.py` and added executable scorer code, so "Skip - no execution-path code changed" is inaccurate.

   Exact fix:
   - Amend the dev log to say Codex review was pending, then reference this review log.

---

## Checklist Results

| Check | Result | Notes |
|---|---|---|
| Scope: no Marker/PaperQA2/harvester/parser/n8n/trading behavior changes | PASS | Only RIS benchmark/filter code changed; Obsidian cache churn is docs/editor state only. |
| Safety: enforcement off by default | PASS | No enforcement exists yet; safe by absence, but incomplete. |
| Live acquisition integration explicit dry-run/enforce | FAIL | `research-acquire` has no filter integration or flags. |
| Determinism | PASS | Scorer is deterministic exact substring matching over ordered config terms. |
| Golden false-negative protection | PASS | DB-backed replay with golden QA: `REJECT=0`, `REVIEW=0`. |
| Benchmark impact | FAIL | DB-backed replay: Scenario B `20.0%`, target `<10%` is `NO`. |
| Auditability | FAIL | Missing thresholds/matched terms in CLI records; no persistent acquisition log. |
| Heavy ML dependencies | PASS | No new SPECTER2/S2FOS/sklearn/SVM dependency introduced. |
| Docs packet state | PARTIAL | Packet no longer stale stub and correctly says v0 is not SVM, but docs overclaim impact and Prompt A completion state. |
| Tests | PARTIAL | 102 targeted tests pass; no offline tests cover simulation CLI/replay output. |
| Current-Focus/CURRENT_DEVELOPMENT conventions | PARTIAL | Active slot is valid, but status/date/DoD are stale after partial implementation. |

---

## Recommended Fix Order

1. Calibrate `config/research_relevance_filter_v1.json` so the DB-backed replay hits `<10%` without QA rejects.
2. Add simulation CLI tests for replay, config failure, audit fields, and target reporting.
3. Wire `research-acquire` with explicit audit/dry-run and enforce flags; keep enforcement off by default.
4. Add persistent audit JSONL for acquisition filter decisions.
5. Update docs/INDEX/CURRENT_DEVELOPMENT/Current-Focus to reflect "partial implementation, not shipped".
6. Re-run:
   - `python -m pytest tests/test_ris_relevance_filter.py tests/test_ris_eval_benchmark.py`
   - `python -m polytool research-eval-benchmark --corpus v0 --golden-set v0 --simulate-prefetch-filter`
   - `python -m polytool research-acquire --help`

---

## Final Assessment

The scorer itself is deterministic, lightweight, and does not add heavy ML dependencies. It also avoids rejecting the reviewed golden QA papers at current thresholds. However, v0 is not ready to ship or enforce: the actual replay misses the `<10%` gate, acquisition is not wired, reject/review audit data is incomplete, and docs currently overclaim the benchmark result.

Use it only as a benchmark simulation artifact until the blocking fixes above are complete.
