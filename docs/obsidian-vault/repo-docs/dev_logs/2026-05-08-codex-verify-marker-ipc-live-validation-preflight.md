---
title: Codex Verify Marker Ipc Live Validation Preflight
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-08_codex-verify-marker-ipc-live-validation-preflight.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Codex Verify: Marker IPC Live-Validation Preflight

Date: 2026-05-08
Type: read-only verification review
Scope: verify whether the second live Docker validation may run next
Verdict: FAIL

## Decision

FAIL. The second live Docker validation may NOT run next.

The isolated validation queue is present and contains exactly 3 pending
validation candidates. However, the preflight is not complete because:

1. The Docker daemon is still unresponsive in this review; `docker ps` timed out
   after 124 seconds.
2. `warm-process --help` has not been verified inside the validation container
   after the rebuild.
3. The in-container GPU visibility check remains deferred/blockered.
4. The queue preflight log still records arXiv API cooldown failure.
5. Papers 2-3 have good local evidence as simple/prose-heavy candidates, but
   operator visual PDF verification is still pending in the queue preflight log.

L1 remains blocked pending live validation. No `warm-process` or live Marker
parse was run during this review.

## Preflight Checklist

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Candidate set has exactly 3 validation papers | PASS | Queue counts: `pending=3`, `total=3`; list shows `2604.24366`, `1910.08858`, `2109.07581`. |
| 2 | Papers 2-3 are reasonable simple/prose-heavy candidates, or live validation remains blocked | PARTIAL/BLOCKED | Local cache evidence supports both papers, but operator visual PDF verification remains pending; live validation stays blocked. |
| 3 | Isolated queue exists under `artifacts/research/marker_validation_queue` | PASS | Directory exists with `queue.jsonl`; no `results.jsonl`. |
| 4 | Queue counts/list show exactly 3 pending validation candidates | PASS | `counts --json` returned `pending: 3`, `processing: 0`, `done: 0`, `failed: 0`, `total: 3`; list shows all attempts 0. |
| 5 | Enqueue commands used required `--url` | PASS | Queue preflight log shows all three enqueue calls with `--url`; CLI source has `required=True`; queue file has normalized arXiv source URLs. |
| 6 | Docker image/container rebuilt or verified to include current code | PARTIAL | Docker preflight log records successful image rebuild and tag timestamp `2026-05-07 14:28:14`; container verification remains blocked. |
| 7 | `warm-process` help works inside validation container | FAIL | Docker preflight deferred this; current `docker ps` timed out, so in-container help could not be verified. |
| 8 | GPU visibility checked or clear blocker documented | BLOCKED | Docker preflight documents daemon blocker; current `docker ps` timeout confirms Docker remains blocked. Host-level GPU evidence exists from prior run, but current in-container check is not complete. |
| 9 | No `warm-process` or live Marker parsing was run during preflight | PASS | Queue preflight and Docker preflight both state no warm-process/no live Marker parsing; validation queue has no `results.jsonl`. |
| 10 | No code/tests/SVM/trading/L2/L4 changes occurred | PASS WITH NOTE | Preflight logs state no code/test/SVM/trading/L2/L4 changes during preflight. Current working tree does contain earlier Marker IPC code/test/Docker changes from the implementation work, so this is not a clean-tree claim. This review changed only this dev log. |
| 11 | L1 remains blocked pending live validation | PASS | Work packet, current development doc, queue preflight, and Docker preflight all preserve L1 blocked status. |

## Candidate Table

| Paper | arXiv ID | Title | Evidence | Review result |
|---|---|---|---|---|
| 1 | `2604.24366` | The Anatomy of a Decentralized Prediction Market | Anchor from prior single-paper Marker validation; preflight queue entry is pending with attempts 0. | PASS as mandatory anchor. |
| 2 | `1910.08858` | Beating the House: Identifying Inefficiencies in Sports Betting Markets | Local cache: `body_source=pdf`, `body_length=58604`; filter decision `allow`, score `0.880797`, reason `strong_positive:betting market`. | Reasonable simple/prose-heavy candidate, but visual PDF verification remains pending. |
| 3 | `2109.07581` | The Impact of COVID-19 on Sports Betting Markets | Local cache: `body_source=pdf`, `body_length=41926`; filter decision `allow`, score `0.880797`, reason `strong_positive:betting market`. | Reasonable simple/prose-heavy candidate, but visual PDF verification remains pending. |

## Docker / Container Evidence

Docker image rebuild evidence exists in
`docs/dev_logs/2026-05-07_marker-ipc-live-validation-docker-preflight.md`:

- `docker compose --profile ris-gpu build ris-scheduler-gpu`
- Result: build exit 0.
- Image tag updated to `polytool-ris-scheduler-gpu:latest`.
- Post-build image timestamp recorded as `2026-05-07 14:28:14 -0400 EDT`.

That is not enough to run the second live validation because the same preflight
log deferred the two required in-container checks:

- `research-marker-queue warm-process --help`
- GPU visibility check

This review attempted only `docker ps` as a safe daemon probe. It timed out after
124 seconds, confirming the Docker blocker remains current.

## Queue Evidence

Isolated validation queue:

```text
artifacts/research/marker_validation_queue/
  queue.jsonl
```

No results file exists:

```text
artifacts/research/marker_validation_queue/results.jsonl = False
```

That is consistent with no live validation run against the isolated queue.

## Commands Run

### `git status --short`

Exit code: 0

```text
 M Dockerfile.ris
 M docs/INDEX.md
 M docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
 M "docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md"
 M "docs/obsidian-vault/Claude Desktop/Current-Focus.md"
 M packages/research/ingestion/fetchers.py
 M packages/research/ingestion/marker_queue.py
 M tests/test_ris_marker_queue.py
 M tools/cli/research_marker_queue.py
?? docs/dev_logs/2026-05-07_claude-review-marker-docker-ipc-live-validation.md
?? docs/dev_logs/2026-05-07_claude-review-marker-docker-ipc-worker-integration.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-live-validation.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-v1-activation-clean.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-v1-activation-fixed.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-v1-activation.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-worker-implementation.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-worker-integration-fixed.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-ipc-live-validation-fixes.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-ipc-live-validation-rerun-plan-fixed.md
?? docs/dev_logs/2026-05-07_fix-marker-docker-ipc-warm-worker-v1-activation.md
?? docs/dev_logs/2026-05-07_fix-marker-docker-ipc-worker-integration.md
?? docs/dev_logs/2026-05-07_fix-marker-historical-l1-unblocked-claims.md
?? docs/dev_logs/2026-05-07_fix-marker-ipc-live-validation-blockers.md
?? docs/dev_logs/2026-05-07_fix-marker-ipc-live-validation-rerun-plan.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-live-validation.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-activation.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-context-map.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-worker-core.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-worker-queue-cli-integration.md
?? docs/dev_logs/2026-05-07_marker-ipc-live-validation-docker-preflight.md
?? docs/dev_logs/2026-05-07_marker-ipc-live-validation-preflight-queue.md
?? docs/dev_logs/2026-05-07_marker-ipc-live-validation-rerun-plan.md
?? "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"
?? packages/research/ingestion/marker_ipc_worker.py
?? tests/test_ris_marker_ipc_worker.py
```

### `git diff --stat`

Exit code: 0

```text
 Dockerfile.ris                                     |   1 +
 docs/INDEX.md                                      |   2 +-
 ...026-05-03_academic-pipeline-hosting-decision.md |  15 +-
 .../.smart-env/event_logs/event_logs.ajson         |  12 +-
 .../multi/Claude_Desktop_Current-Focus_md.ajson    |   6 +
 .../Decision - Academic Pipeline Hosting.md        |   2 +-
 .../obsidian-vault/Claude Desktop/Current-Focus.md |   4 +-
 packages/research/ingestion/fetchers.py            |  66 ++++++
 packages/research/ingestion/marker_queue.py        |  98 +++++++++
 tests/test_ris_marker_queue.py                     | 236 +++++++++++++++++++++
 tools/cli/research_marker_queue.py                 | 114 ++++++++++
 11 files changed, 548 insertions(+), 8 deletions(-)
warning: in the working copy of 'Dockerfile.ris', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson', LF will be replaced by CRLF the next time Git touches it
```

### `git log --oneline -5`

Exit code: 0

```text
4b57400 SVM scoring complete
e482a6d L3 handoff
be8b4f2 fix(ris): resolve Codex FAIL blockers - Marker queue v0
7b81a7a Marker Parser added
a4fdcac docs(ris): close out Marker control surface validation - L1 still blocked
```

### `python -m polytool --help`

Exit code: 0. CLI loaded successfully. Relevant output included
`research-marker-queue     Enqueue/process arXiv papers through Marker; track RAG-ready status`.

### Queue counts

Command:

```powershell
python -m polytool research-marker-queue --queue-dir artifacts/research/marker_validation_queue counts --json
```

Exit code: 0

```json
{
  "pending": 3,
  "processing": 0,
  "done": 0,
  "failed": 0,
  "total": 3
}
```

### Queue list

Command:

```powershell
python -m polytool research-marker-queue --queue-dir artifacts/research/marker_validation_queue list --status all
```

Exit code: 0

```text
  candidate_id                 status       att   title
  -------------------------------------------------------------------------------------------
  arxiv:2604.24366             pending      0     The Anatomy of a Decentralized Predictio
  arxiv:1910.08858             pending      0     Beating the House: Identifying Inefficie
  arxiv:2109.07581             pending      0     The Impact of COVID-19 on Sports Betting

Total: 3 item(s)
```

### Queue files

Command:

```powershell
Get-ChildItem -Force -LiteralPath 'artifacts/research/marker_validation_queue' | Select-Object Name,Length,LastWriteTime | Format-Table -AutoSize | Out-String -Width 200
```

Exit code: 0

```text
Name        Length LastWriteTime
----        ------ -------------
queue.jsonl    911 5/7/2026 4:04:02 PM
```

### Queue JSONL

Command:

```powershell
Get-Content -Raw -LiteralPath 'artifacts/research/marker_validation_queue/queue.jsonl'
```

Exit code: 0

```jsonl
{"candidate_id":"arxiv:2604.24366","source_url":"https://arxiv.org/abs/2604.24366","arxiv_id":"2604.24366","title":"The Anatomy of a Decentralized Prediction Market","status":"pending","attempts":0,"created_at":"2026-05-07T20:03:55.263213+00:00","updated_at":"2026-05-07T20:03:55.263213+00:00"}
{"candidate_id":"arxiv:1910.08858","source_url":"https://arxiv.org/abs/1910.08858","arxiv_id":"1910.08858","title":"Beating the House: Identifying Inefficiencies in Sports Betting Markets","status":"pending","attempts":0,"created_at":"2026-05-07T20:04:01.605463+00:00","updated_at":"2026-05-07T20:04:01.605463+00:00"}
{"candidate_id":"arxiv:2109.07581","source_url":"https://arxiv.org/abs/2109.07581","arxiv_id":"2109.07581","title":"The Impact of COVID-19 on Sports Betting Markets","status":"pending","attempts":0,"created_at":"2026-05-07T20:04:02.524462+00:00","updated_at":"2026-05-07T20:04:02.524462+00:00"}
```

### Validation results file check

Command:

```powershell
Test-Path -LiteralPath 'artifacts/research/marker_validation_queue/results.jsonl'
```

Exit code: 0

```text
False
```

### Docker daemon check

Command:

```powershell
docker ps --format "table {{.Names}}`t{{.Status}}`t{{.Image}}"
```

Exit code: 124

```text
command timed out after 124014 milliseconds
```

### Candidate cache checks

Command:

```powershell
$j = Get-Content -Raw -LiteralPath 'artifacts/research/raw_source_cache/academic/1b7ea11f48bcad8e.json' | ConvertFrom-Json; $j.payload | Select-Object title,body_source,body_length,source_url | Format-List | Out-String -Width 200
```

Exit code: 0

```text
title       : Beating the House: Identifying Inefficiencies in Sports Betting Markets
body_source : pdf
body_length : 58604
source_url  :
```

Command:

```powershell
$j = Get-Content -Raw -LiteralPath 'artifacts/research/raw_source_cache/academic/9cb0749d56b09f9d.json' | ConvertFrom-Json; $j.payload | Select-Object title,body_source,body_length,source_url | Format-List | Out-String -Width 200
```

Exit code: 0

```text
title       : The Impact of COVID-19 on Sports Betting Markets
body_source : pdf
body_length : 41926
source_url  :
```

Command:

```powershell
Select-String -LiteralPath 'artifacts/research/acquisition_reviews/filter_decisions.jsonl' -Pattern '1910.08858','2109.07581','2604.24366' | ForEach-Object { $_.Line }
```

Exit code: 0. Relevant lines:

```jsonl
{"timestamp": "2026-05-03T00:34:51.124936+00:00", "source_id": "1b7ea11f48bcad8e", "source_url": "https://arxiv.org/abs/1910.08858", "title": "Beating the House: Identifying Inefficiencies in Sports Betting Markets", "decision": "allow", "score": 0.880797, "raw_score": 2.0, "allow_threshold": 0.8, "review_threshold": 0.35, "reason_codes": ["strong_positive:betting market"], "matched_terms": {"strong_positive": ["betting market"], "positive": [], "strong_negative": [], "negative": []}, "config_version": "v1.1", "input_fields_used": ["title", "abstract"], "enforced": true}
{"timestamp": "2026-05-03T00:34:51.199413+00:00", "source_id": "9cb0749d56b09f9d", "source_url": "https://arxiv.org/abs/2109.07581", "title": "The Impact of COVID-19 on Sports Betting Markets", "decision": "allow", "score": 0.880797, "raw_score": 2.0, "allow_threshold": 0.8, "review_threshold": 0.35, "reason_codes": ["strong_positive:betting market"], "matched_terms": {"strong_positive": ["betting market"], "positive": [], "strong_negative": [], "negative": []}, "config_version": "v1.1", "input_fields_used": ["title", "abstract"], "enforced": true}
```

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`
- `docs/dev_logs/2026-05-07_codex-verify-marker-ipc-live-validation-rerun-plan-fixed.md`
- `docs/dev_logs/2026-05-07_marker-ipc-live-validation-preflight-queue.md`
- `docs/dev_logs/2026-05-07_marker-ipc-live-validation-docker-preflight.md`
- `tools/cli/research_marker_queue.py`
- `packages/research/ingestion/marker_queue.py`
- `Dockerfile.ris`
- `docker-compose.yml`
- `artifacts/research/marker_validation_queue/queue.jsonl`
- `artifacts/research/raw_source_cache/academic/1b7ea11f48bcad8e.json`
- `artifacts/research/raw_source_cache/academic/9cb0749d56b09f9d.json`
- `artifacts/research/acquisition_reviews/filter_decisions.jsonl`

## Blockers / Required Fixes Before Second Live Docker Validation

1. Restart Docker Desktop / daemon and confirm `docker ps` returns promptly.
2. Run in-container help check:
   `docker compose --profile ris-gpu run --rm --no-deps ris-scheduler-gpu python -m polytool research-marker-queue warm-process --help`
3. Run in-container GPU visibility check without Marker parsing.
4. Re-check arXiv API cooldown; proceed only if the anchor query returns an
   `<entry>`.
5. Complete operator visual PDF verification for `1910.08858` and `2109.07581`
   or explicitly accept local-cache-only candidate evidence.
6. Only after the above pass, run the second live Docker validation command.

## Codex Review Summary

Tier: skip/read-only validation review. No code, tests, Docker build, queue
mutation, SVM, trading, L2, or L4 changes were made by Codex in this review.
Only this dev log was created.

