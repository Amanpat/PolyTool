# Codex Re-review: RIS L3 Pre-fetch Filter v0

**Date:** 2026-05-02  
**Reviewer:** Codex  
**Verdict:** PASS WITH FIXES  
**Enforcement state:** Safe for dry-run/audit. Reject-only enforce has safe skip semantics for the current QA guard, but is not full gate-closure enforce-ready until the Scenario A vs Scenario B policy is documented and enforce-mode failure handling is tightened.

---

## Scope Reviewed

- `git diff`
- `docs/dev_logs/*prefetch*filter*`
- `packages/research/relevance_filter/*`
- `config/research_relevance_filter_v1.json`
- `tools/cli/research_eval_benchmark.py`
- `tools/cli/research_acquire.py`
- `tests/test_ris_relevance_filter.py`
- `tests/test_ris_eval_benchmark.py`
- `docs/runbooks/research_eval_benchmark.md`

Recent fix commit inspected:

```text
1520e18 fix(ris): L3 pre-fetch filter v0 - Codex FAIL resolution (v1.1)
```

---

## Commands Run

### Session checks

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
?? docs/dev_logs/2026-05-02_codex-review-ris-prefetch-filter-v0.md
?? docs/dev_logs/2026-05-02_ris-eval-benchmark-golden-qa-finalized.md
?? docs/dev_logs/2026-05-02_ris-eval-benchmark-v0-closeout.md
?? docs/features/FEATURE-ris-scientific-eval-benchmark-v0.md
?? tests/fixtures/research_eval_benchmark/golden_qa_v0.json
```

`git log --oneline -5`

```text
1520e18 fix(ris): L3 pre-fetch filter v0 - Codex FAIL resolution (v1.1)
14a15a8 feat(ris): L3 cold-start lexical relevance filter with corpus simulation
7df7b9f feat(ris): scoped lexical refresh for L5 benchmark corpus
0646a68 feat(ris): L5 QA review pack - 35 verified candidate QA pairs for baseline
a15d560 fix(ris): Harden L5 eval benchmark v0 - apply all Codex fixes and run first draft
```

`python -m polytool --help`

```text
Exit code 0. CLI loaded; research-eval-benchmark and research-acquire are present.
```

`rg --files packages/research/relevance_filter`

```text
Access is denied
```

Fallback used:

`Get-ChildItem -Path packages\research\relevance_filter -Recurse -File`

```text
packages/research/relevance_filter/scorer.py
packages/research/relevance_filter/__init__.py
```

### Diff inspection

`git diff --stat`

```text
 docs/CURRENT_DEVELOPMENT.md                        |  28 ++++-
 docs/obsidian-vault/.obsidian/workspace.json       |  10 +-
 .../.smart-env/event_logs/event_logs.ajson         |  68 ++++++++---
 ..._11-Scientific-RAG-Target-Architecture_md.ajson |   5 +-
 ...-_Marker_Structural_Parser_Integration_md.ajson |  97 +--------------
 ...rk-Packet_-_Pre-fetch_SVM_Topic_Filter_md.ajson |  77 +++++++++++-
 ..._-_Scientific_RAG_Evaluation_Benchmark_md.ajson |  55 +--------
 .../multi/Claude_Desktop_Current-Focus_md.ajson    |  25 +++-
 .../Work-Packet - Pre-fetch SVM Topic Filter.md    | 136 ++++++++++++++++-----
 .../obsidian-vault/Claude Desktop/Current-Focus.md |  15 +--
 docs/runbooks/research_eval_benchmark.md           |  25 +++-
 11 files changed, 313 insertions(+), 228 deletions(-)
```

`git show --stat --oneline HEAD`

```text
1520e18 fix(ris): L3 pre-fetch filter v0 - Codex FAIL resolution (v1.1)
 config/research_relevance_filter_v1.json           |   4 +-
 docs/INDEX.md                                      |   3 +-
 .../2026-05-02_ris-prefetch-filter-coldstart.md    |  20 ++-
 .../2026-05-02_ris-prefetch-filter-v0-fix.md       | 182 +++++++++++++++++++++
 packages/research/relevance_filter/scorer.py       |  14 ++
 tests/test_ris_eval_benchmark.py                   | 135 +++++++++++++++
 tests/test_ris_relevance_filter.py                 |  83 ++++++++++
 tools/cli/research_acquire.py                      | 135 +++++++++++++++
 tools/cli/research_eval_benchmark.py               |  24 ++-
 9 files changed, 588 insertions(+), 12 deletions(-)
```

### Requested runs

`python -m pytest tests/test_ris_relevance_filter.py tests/test_ris_eval_benchmark.py`

```text
collected 113 items
113 passed in 1.07s
```

`python -m polytool research-eval-benchmark --corpus v0 --golden-set v0 --simulate-prefetch-filter`

```text
Filter config version : v1.1
Allow threshold       : 0.8
Review threshold      : 0.35
Corpus entries        : 23
Docs loaded from DB   : 23

Baseline off-topic count/rate: 7 / 23, 30.43%
Filter decisions: ALLOW 17, REVIEW 3, REJECT 3
Scenario A (reject excluded, review included): 20.0% [20 docs]
Scenario B (reject+review excluded): 5.88% [17 docs]

QA paper source_ids tracked : 10
QA papers in REJECT         : 0
QA papers in REVIEW         : 1

Target <10% off_topic (scenario B): YES (5.88%)
```

The detailed report also printed per-review/reject `score`, `raw_score`, thresholds, full `reason_codes`, and `matched_terms`.

`python -m polytool research-acquire --help`

```text
--prefetch-filter-mode {off,dry-run,enforce}
                        Relevance pre-fetch filter mode (default: off). dry-
                        run: score and log but always ingest. enforce: skip
                        REJECT candidates; REVIEW candidates are ingested with
                        audit flag.
--prefetch-filter-config PATH
                        Path to relevance filter config JSON (default: auto-
                        discover config/research_relevance_filter_v1.json).
```

Dependency/scope search:

`Select-String -Path pyproject.toml,requirements*.txt -Pattern "specter|s2fos|scikit|sklearn|svm|sentence-transformers|torch|transformers|paperqa|marker|n8n" -CaseSensitive:$false`

```text
pyproject.toml:33:    "sentence-transformers>=2.2.0",
pyproject.toml:63:ris-marker = [
pyproject.toml:64:    "marker-pdf>=1.0",
pyproject.toml:116:markers = [
requirements-rag.txt:1:sentence-transformers
requirements-rag.txt:2:torch
```

No new heavy ML dependency was added by the L3 filter fix. The hits are pre-existing RAG/Marker dependencies, not new SVM/SPECTER2 scope in this fix.

---

## Check Results

| Check | Result | Notes |
|---|---|---|
| DB-backed simulation post-filter off_topic_rate <10% | PASS WITH CAVEAT | Scenario B is 5.88% and prints target YES. Scenario A, which matches reject-only enforcement, remains 20.0%. |
| Golden-QA false negatives are 0 | PASS | DB replay shows QA papers in REJECT = 0. One QA paper is REVIEW, not REJECT. |
| `research-acquire` has off/dry-run/enforce flags, default off | PASS | `--prefetch-filter-mode {off,dry-run,enforce}`, default `off`. |
| Dry-run does not skip; enforce skips only reject decisions | PASS | Help and code match: dry-run logs and continues; enforce skips only `decision == "reject"`. |
| Audit output includes thresholds, score, raw_score, matched terms, reason codes, input fields, config version | PASS | `FilterDecision` carries these fields; acquisition audit JSONL writes them. Benchmark detail prints all except per-row `input_fields_used`, with config version in the report header. |
| Docs no longer overclaim title-only projection | PASS WITH FIXES | Cold-start log and INDEX distinguish title-only estimate from v1.1 DB-backed fix. CURRENT_DEVELOPMENT/work-packet still use stale flag/default wording. |
| No heavy ML deps or SVM/SPECTER2 added | PASS | No dependency-file changes in fix commit. |
| No Marker/PaperQA2/multi-source/n8n/trading scope creep | PASS | No behavior/code files in those areas changed by the fix commit. Obsidian metadata contains unrelated cache churn only. |
| Tests offline and deterministic | PASS WITH FIXES | Tests run offline and pass. New simulation tests mostly assert exit codes; output/content assertions should be strengthened before treating them as regression guards. |

---

## Findings

### Blocking

No original Codex FAIL blocker remains unresolved in the narrow sense:

1. The DB-backed simulation now prints `Target <10% off_topic (scenario B): YES (5.88%)`.
2. Golden QA false negatives are zero under reject-only enforcement.
3. `research-acquire` exposes explicit `off|dry-run|enforce` filter modes with default `off`.
4. Acquisition audit records include score, raw score, thresholds, reason codes, matched terms, input fields, config version, source fields, and enforced status.

### Fix Before Full Enforcement

1. **Scenario B target is not the same as current enforce behavior.**

   `research_eval_benchmark.py` reports target success from Scenario B, which excludes both REVIEW and REJECT papers. `research_acquire.py` enforce mode skips only REJECT and ingests REVIEW. With current DB data, reject-only enforcement corresponds to Scenario A, which remains `20.0%`, not `<10%`.

   This is acceptable for a conservative safety posture, but docs/operator language must not claim reject-only enforcement achieves the `<10%` gate. The clearest wording is: "v1.1 meets the allow-only simulation target; current enforce mode is reject-only and removes only the three clear negatives."

2. **Enforce mode currently fails open on scoring/config errors.**

   `_score_candidate_for_filter()` catches all exceptions, prints a warning, returns `None`, and the acquisition flow proceeds. That behavior is reasonable for `dry-run`/`off`, but explicit `--prefetch-filter-mode enforce` should probably return a nonzero error if the filter cannot score the candidate. Otherwise an invalid config silently disables enforcement.

3. **Docs have stale flag/default wording.**

   `docs/CURRENT_DEVELOPMENT.md` and the Obsidian work packet still mention default dry-run/audit and `--enforce-relevance-filter`. Actual CLI behavior is default `off` with `--prefetch-filter-mode enforce`. This is not the old title-only overclaim, but it should be corrected before operator handoff.

4. **Simulation CLI tests are too shallow.**

   The new tests are offline and deterministic, but the simulation tests mostly assert exit codes. Add captured-output assertions for `Target <10%`, reject/review counts, thresholds, raw score, matched terms, and reason codes so future changes cannot regress the reporting contract unnoticed.

---

## Enforcement Readiness

**Dry-run/audit:** Safe now.

**Reject-only enforce:** Mechanically safe for the current golden-QA guard because DB replay shows zero QA papers in REJECT and the code skips only REJECT. I would treat it as an experimental conservative enforcement mode, not as full gate-closure enforcement.

**Full enforce-ready verdict:** Not yet. The `<10%` success is Scenario B (ALLOW-only), while actual enforce mode is Scenario A (REJECT-only) at `20.0%`. Tighten docs/policy and make enforce fail closed on filter scoring/config errors before calling this fully enforce-ready.

---

## Decisions

- Did not implement fixes; this was a re-review request.
- Did not enable enforcement by default.
- Recorded verdict as PASS WITH FIXES because the original FAIL blockers are materially resolved, but enforcement-readiness language and fail-open behavior still need a small follow-up.

---

## Open Questions

1. Should v0 acceptance define `<10%` against Scenario B (allow-only simulation) or against the actual reject-only enforcement path?
2. Should `--prefetch-filter-mode enforce` fail closed when config/scoring fails?
3. Should REVIEW papers be routed to an operator queue in enforce mode instead of being ingested normally?
