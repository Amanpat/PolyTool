# Codex Verify: Marker IPC Live-Validation Final Preflight

Date: 2026-05-08
Type: read-only verification review
Scope: verify whether the second live Docker validation may run next
Verdict: PASS, conditional on using Docker context `default`

## Decision

PASS. The second live Docker validation may run next if the operator uses
`docker --context default ...` or switches Docker to the `default` context first.

The final preflight completion log is substantively correct: the rebuilt GPU image
exists, `research-marker-queue warm-process --help` works inside the rebuilt
container, CUDA is visible inside that container, the isolated validation queue
still has exactly 3 pending papers and no results file, arXiv precheck returns
entries for all 3 IDs, and papers 2-3 are reasonable simple validation candidates.

Important caveat: raw `docker info` still targets the active `desktop-linux` context
and fails with Docker API permission denied. This does not block the second live
validation as long as the validation command is run with `--context default`.

No `warm-process` parse job or live Marker parsing was run during this review.
Only this dev log was created.

## Preflight Checklist

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Docker daemon is healthy | PASS WITH CONTEXT NOTE | `docker --context default info` exit 0; raw `docker info` fails on active `desktop-linux` with permission denied. |
| 2 | Docker container/image exposes `research-marker-queue warm-process` | PASS | `docker --context default run --rm polytool-ris-scheduler-gpu:latest python -m polytool research-marker-queue warm-process --help` exit 0. |
| 3 | GPU visibility check passed inside container | PASS | `CUDA available: True`, `devices: 1`, `NVIDIA GeForce RTX 2070 SUPER`. |
| 4 | Isolated validation queue has exactly 3 pending, 0 done, 0 failed | PASS | `pending=3`, `processing=0`, `done=0`, `failed=0`, `total=3`; no `results.jsonl`. |
| 5 | No `warm-process` or live Marker parsing was run during preflight | PASS | Only `warm-process --help` was run; queue mtime remains 2026-05-07 16:04:02; no results file. |
| 6 | arXiv cooldown/precheck passed | PASS | All 3 IDs returned HTTP 200 and `<entry>` from export.arxiv.org. |
| 7 | Papers 2-3 accepted as reasonable simple candidates | PASS | Local cache confirms prose-heavy betting-market PDFs; paper 2 has 8,979 words and low equation/theorem refs; paper 3 has 6,231 words and 0 equation/theorem refs. |
| 8 | No code/tests/SVM/trading/L2/L4 changes occurred during this review | PASS WITH DIRTY-TREE NOTE | This review created only this dev log. The pre-existing worktree already contains Marker IPC code/test changes and one SVM-named Obsidian metadata file; no trading, L2, or L4 paths are in the tracked diff. |
| 9 | L1 remains blocked pending live validation | PASS | Current development and work packet still gate L1 on live Docker/GPU validation. This preflight only clears permission to run the next validation. |

## Docker and Container Evidence

### Raw `docker info`

Exit code: 1

```text
Client:
 Version:    29.0.1
 Context:    desktop-linux
 Debug Mode: false

Server:
permission denied while trying to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine
```

Assessment: not the usable context for this validation. Use `--context default`.

### `docker --context default info`

Exit code: 0

```text
Client:
 Version:    29.0.1
 Context:    default
 Debug Mode: false

Server:
 Containers: 5
  Running: 2
  Paused: 0
  Stopped: 3
 Images: 7
 Server Version: 29.0.1
 Storage Driver: overlayfs
 Runtimes: io.containerd.runc.v2 nvidia runc
 Kernel Version: 6.6.87.2-microsoft-standard-WSL2
 Operating System: Docker Desktop
 OSType: linux
 Architecture: x86_64
 Name: docker-desktop
```

### `docker ps`

Exit code: 0

```text
CONTAINER ID   IMAGE                    COMMAND                  CREATED      STATUS         PORTS     NAMES
7096c85085a0   polytool-ris-scheduler   "python -m polytool ..." 3 days ago   Up 8 minutes             polytool-ris-scheduler
```

### `docker context ls`

Exit code: 0

```text
NAME              DESCRIPTION                               DOCKER ENDPOINT                             ERROR
default           Current DOCKER_HOST based configuration   npipe:////./pipe/docker_engine
desktop-linux *   Docker Desktop                            npipe:////./pipe/dockerDesktopLinuxEngine
```

### `docker --context default ps --format "table {{.Names}}`t{{.Status}}`t{{.Image}}"`

Exit code: 0

```text
NAMES                    STATUS         IMAGE
polytool-ris-scheduler   Up 9 minutes   polytool-ris-scheduler
```

### `docker --context default image inspect polytool-ris-scheduler-gpu:latest --format "{{.Id}} {{.Created}}"`

Exit code: 0

```text
sha256:c28202a3ebfafb2f5a0f1371f54c4060f44f832173c3b84eda465c6cc696aae0 2026-05-07T18:28:14.116868182Z
```

### Container `warm-process --help`

Command:

```powershell
docker --context default run --rm polytool-ris-scheduler-gpu:latest python -m polytool research-marker-queue warm-process --help
```

Exit code: 0

```text
usage: polytool research-marker-queue warm-process [-h] [--max-items N]
                                                   [--marker-timeout SECONDS]
                                                   [--json]

options:
  -h, --help            show this help message and exit
  --max-items N         Maximum number of pending items to process (default:
                        1)
  --marker-timeout SECONDS
                        Marker extraction timeout in seconds (default: 900)
  --json                Output results as JSON
```

### In-container GPU visibility

Command:

```powershell
docker --context default run --rm --gpus all polytool-ris-scheduler-gpu:latest python -c "import torch; print('CUDA available:', torch.cuda.is_available(), '| devices:', torch.cuda.device_count()); [print('  GPU', i, ':', torch.cuda.get_device_name(i)) for i in range(torch.cuda.device_count())]"
```

Exit code: 0

```text
CUDA available: True | devices: 1
  GPU 0 : NVIDIA GeForce RTX 2070 SUPER
```

## Queue Evidence

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

Command:

```powershell
Test-Path -LiteralPath 'artifacts/research/marker_validation_queue/results.jsonl'
```

Exit code: 0

```text
False
```

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

## arXiv Precheck

Command:

```powershell
$ids = @('2604.24366','1910.08858','2109.07581'); foreach ($id in $ids) { $url = "https://export.arxiv.org/api/query?id_list=$id&max_results=1"; try { $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 30; $hasEntry = $r.Content -match '<entry>'; Write-Output "$id status=$($r.StatusCode) entry=$hasEntry" } catch { Write-Output "$id ERROR $($_.Exception.Message)" } }
```

Exit code: 0

```text
2604.24366 status=200 entry=True
1910.08858 status=200 entry=True
2109.07581 status=200 entry=True
```

## Candidate Verification Status

| Paper | Status | Evidence |
|---|---|---|
| `2604.24366` | PASS anchor candidate | Present in validation queue as pending, attempts 0. Prior single-paper Marker validation anchor. |
| `1910.08858` | PASS simple/prose-heavy candidate | `body_source=pdf`, `body_length=58604`, `page_count=46`, `word_count=8979`, low equation/theorem refs, filter decision `allow`, score `0.880797`. |
| `2109.07581` | PASS simple/prose-heavy candidate | `body_source=pdf`, `body_length=41926`, `page_count=23`, `word_count=6231`, 0 equation/theorem refs, filter decision `allow`, score `0.880797`. |

Candidate cache commands:

```text
1910.08858:
title             : Beating the House: Identifying Inefficiencies in Sports Betting Markets
body_source       : pdf
body_length       : 58604
page_count        : 46
word_count        : 8979
eq_theorem_refs   : 2
figure_table_refs : 50

2109.07581:
title             : The Impact of COVID-19 on Sports Betting Markets
body_source       : pdf
body_length       : 41926
page_count        : 23
word_count        : 6231
eq_theorem_refs   : 0
figure_table_refs : 35
```

Filter-decision evidence:

```jsonl
{"timestamp": "2026-05-03T00:34:51.124936+00:00", "source_id": "1b7ea11f48bcad8e", "source_url": "https://arxiv.org/abs/1910.08858", "title": "Beating the House: Identifying Inefficiencies in Sports Betting Markets", "decision": "allow", "score": 0.880797, "raw_score": 2.0, "allow_threshold": 0.8, "review_threshold": 0.35, "reason_codes": ["strong_positive:betting market"], "matched_terms": {"strong_positive": ["betting market"], "positive": [], "strong_negative": [], "negative": []}, "config_version": "v1.1", "input_fields_used": ["title", "abstract"], "enforced": true}
{"timestamp": "2026-05-03T00:34:51.199413+00:00", "source_id": "9cb0749d56b09f9d", "source_url": "https://arxiv.org/abs/2109.07581", "title": "The Impact of COVID-19 on Sports Betting Markets", "decision": "allow", "score": 0.880797, "raw_score": 2.0, "allow_threshold": 0.8, "review_threshold": 0.35, "reason_codes": ["strong_positive:betting market"], "matched_terms": {"strong_positive": ["betting market"], "positive": [], "strong_negative": [], "negative": []}, "config_version": "v1.1", "input_fields_used": ["title", "abstract"], "enforced": true}
```

## Git Scope Evidence

### Initial session checks

`git log --oneline -5`:

```text
4b57400 SVM scoring complete
e482a6d L3 handoff
be8b4f2 fix(ris): resolve Codex FAIL blockers - Marker queue v0
7b81a7a Marker Parser added
a4fdcac docs(ris): close out Marker control surface validation - L1 still blocked
```

`python -m polytool --help`: exit code 0. CLI loaded successfully and includes
`research-marker-queue     Enqueue/process arXiv papers through Marker; track RAG-ready status`.

### `git status --short` before this dev log

Exit code: 0

```text
 M Dockerfile.ris
 M docs/INDEX.md
 M docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md
 M docs/obsidian-vault/.obsidian/workspace.json
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_09-Decisions_Decision_-_Academic_Pipeline_Hosting_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_L3_v1_SVM_Topic_Filter_Training_md.ajson
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
?? docs/dev_logs/2026-05-08_codex-verify-marker-ipc-live-validation-preflight.md
?? docs/dev_logs/2026-05-08_marker-ipc-live-validation-preflight-completion.md
?? docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Marker_Docker_IPC_Warm-Worker_v1_md.ajson
?? "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"
?? packages/research/ingestion/marker_ipc_worker.py
?? tests/test_ris_marker_ipc_worker.py
```

### `git diff --stat` before this dev log

Exit code: 0

```text
 Dockerfile.ris                                     |   1 +
 docs/INDEX.md                                      |   2 +-
 ...026-05-03_academic-pipeline-hosting-decision.md |  15 +-
 .../.smart-env/event_logs/event_logs.ajson         |  97 +++------
 ...s_Decision_-_Academic_Pipeline_Hosting_md.ajson |   5 +-
 ...cket_-_L3_v1_SVM_Topic_Filter_Training_md.ajson | 208 ++++++++++--------
 .../multi/Claude_Desktop_Current-Focus_md.ajson    |  31 +--
 .../Decision - Academic Pipeline Hosting.md        |   2 +-
 .../obsidian-vault/Claude Desktop/Current-Focus.md |   4 +-
 packages/research/ingestion/fetchers.py            |  66 ++++++
 packages/research/ingestion/marker_queue.py        |  98 +++++++++
 tests/test_ris_marker_queue.py                     | 236 +++++++++++++++++++++
 tools/cli/research_marker_queue.py                 | 114 ++++++++++
 13 files changed, 700 insertions(+), 179 deletions(-)
```

Assessment: the tree is not clean. Those changes pre-existed this final review.
This review did not modify code, tests, artifacts, SVM product code, trading, L2,
or L4 paths. The only file created by this review is this dev log.

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`
- `docs/dev_logs/2026-05-08_codex-verify-marker-ipc-live-validation-preflight.md`
- `docs/dev_logs/2026-05-08_marker-ipc-live-validation-preflight-completion.md`
- `artifacts/research/marker_validation_queue/queue.jsonl`
- `tools/cli/research_marker_queue.py`
- `docker-compose.yml`
- `Dockerfile.ris`
- `artifacts/research/raw_source_cache/academic/1b7ea11f48bcad8e.json`
- `artifacts/research/raw_source_cache/academic/9cb0749d56b09f9d.json`
- `artifacts/research/acquisition_reviews/filter_decisions.jsonl`

## Live Validation May Run Next

Yes. Use the `default` Docker context explicitly:

```powershell
docker --context default run --rm --gpus all `
  -v "${PWD}/artifacts:/app/artifacts" `
  polytool-ris-scheduler-gpu:latest `
  python -m polytool research-marker-queue `
  --queue-dir artifacts/research/marker_validation_queue `
  warm-process --max-items 1 --json
```

Do not run the command without either `--context default` or `docker context use default`,
because the active `desktop-linux` context still fails `docker info`.

## Blockers / Fixes

No blocker remains for the second live Docker validation if using `--context default`.

Recommended hygiene before or after validation:

- Switch Docker context to `default` if the operator wants raw `docker info` to pass.
- Keep the validation queue isolated and run only one item first, as shown above.
- After live validation, inspect queue counts and `results.jsonl` before processing papers 2-3.

## Codex Review Summary

Tier: skip/read-only preflight validation. No code review was required for this
task. No code, tests, Dockerfile, SVM product code, trading, L2, L4, or queue
artifact changes were made by Codex. Only this dev log was created.
