---
title: Marker Canonical Parse Queue V0
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-05_marker-canonical-parse-queue-v0.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Marker Canonical Academic Parse Queue v0

Date: 2026-05-05
Scope: Async Marker parse queue — enqueue, warm-model worker, RAG-readiness gate.
Status: IMPLEMENTED — offline tests pass; live Docker validation deferred.

---

## Context

Single-paper control surface validated 2026-05-05 (`parse_seconds=85.95s`). Root cause:
model cold-load dominates (~80s) per invocation. Operator decision: Marker is the only
canonical parser for final academic RAG embeddings. pdfplumber must not be a normal
production fallback. The queue solves cold-load by keeping models warm across papers.

Prior session: `docs/dev_logs/2026-05-05_marker-single-paper-control-surface-validation.md`

---

## Files Changed

| File | Change |
|------|--------|
| `packages/research/ingestion/marker_queue.py` | New — core queue logic |
| `tools/cli/research_marker_queue.py` | New — CLI entrypoint |
| `polytool/__main__.py` | Register `research-marker-queue` command + usage line |
| `tests/test_ris_marker_queue.py` | New — 43 offline tests |
| `docs/dev_logs/2026-05-05_marker-canonical-parse-queue-v0.md` | This file |

---

## Queue Schema

### queue.jsonl (mutable, rewritten on status changes)

```json
{
  "candidate_id": "arxiv:2604.24366",
  "source_url": "https://arxiv.org/abs/2604.24366",
  "arxiv_id": "2604.24366",
  "title": "",
  "status": "pending",
  "attempts": 0,
  "created_at": "2026-05-05T12:00:00.000000+00:00",
  "updated_at": "2026-05-05T12:00:00.000000+00:00"
}
```

Status flow: `pending` → `processing` → `done` | `pending` (retry) | `failed` (terminal)

### results.jsonl (append-only, one record per process attempt)

```json
{
  "candidate_id": "arxiv:2604.24366",
  "source_url": "https://arxiv.org/abs/2604.24366",
  "arxiv_id": "2604.24366",
  "title": "The Anatomy of a Decentralized Prediction Market",
  "body_source": "marker",
  "body_length": 56923,
  "parse_seconds": 6.2,
  "failure_reason": null,
  "rejected": false,
  "exit_code": 0,
  "marker_ready": true,
  "total_seconds": 6.4,
  "processed_at": "2026-05-05T12:05:00.000000+00:00",
  "attempt": 1,
  "queue_status": "done"
}
```

---

## Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `MAX_ATTEMPTS` | 3 | Failures before item becomes terminal (`failed`) |
| `MIN_MARKER_BODY_LENGTH` | 5000 chars | Minimum body for `marker_ready=True` |

---

## CLI Commands

```powershell
# Enqueue one paper
python -m polytool research-marker-queue enqueue --url 2604.24366
python -m polytool research-marker-queue enqueue --url https://arxiv.org/abs/2604.24366
python -m polytool research-marker-queue enqueue --url 2604.24366 --force   # re-enqueue failed

# List queue
python -m polytool research-marker-queue list
python -m polytool research-marker-queue list --status pending
python -m polytool research-marker-queue list --json

# Process items (warm-model worker — run inside GPU Docker container)
python -m polytool research-marker-queue process --max-items 10 --marker-timeout 900
python -m polytool research-marker-queue process --json

# Count by status
python -m polytool research-marker-queue counts
python -m polytool research-marker-queue counts --json
```

---

## RAG-Ready Rule (canonical)

```python
def is_marker_ready(body_source: str, body_length: int) -> bool:
    return body_source == "marker" and body_length >= MIN_MARKER_BODY_LENGTH  # 5000 chars
```

| body_source | marker_ready |
|-------------|-------------|
| `marker` + length ≥ 5000 | **True** |
| `marker` + length < 5000 | False |
| `marker_failed` | False |
| `pdfplumber_fallback` | False |
| `pdf` | False |
| `abstract_fallback` | False |
| `error` | False |

The `marker_ready` field in results.jsonl is the authoritative RAG-readiness flag.
Embedding/indexing code should gate on `marker_ready=true` for Marker queue results.

---

## Worker Warm-Model Design

The `process` command processes items sequentially within one invocation of the CLI.
By running inside the `ris-scheduler-gpu` Docker container (or any container with
Marker models volume-mounted), the first paper incurs the ~80s cold-load. Subsequent
papers run at ~6s/paper (GPU inference only).

Recommended operator workflow:
```powershell
# Start long-running GPU container (models load once)
docker compose --profile ris-gpu run --rm ris-scheduler-gpu `
  python -m polytool research-marker-queue process --max-items 50 --marker-timeout 900
```

Or pipe a batch of URLs:
```powershell
# From host, enqueue papers first
python -m polytool research-marker-queue enqueue --url 2604.24366
python -m polytool research-marker-queue enqueue --url 2401.00001
# Then process inside GPU container
docker compose --profile ris-gpu run --rm ris-scheduler-gpu `
  python -m polytool research-marker-queue process --max-items 10
```

---

## Tests Run

```
python -m pytest tests/test_ris_marker_queue.py -v --tb=short
```

Expected: all 43 tests pass (offline, no Docker, no Marker install).

Additional regression checks (from CLAUDE.md smoke test):
```
python -m polytool --help
python -m polytool research-marker-queue --help
```

---

## Remaining Live Validation Steps (Docker/GPU required)

1. **Model warm-load test**: process 2 papers sequentially; confirm second paper
   completes in ~6s (vs ~86s cold-load first paper).
2. **Timeout kill test**: process a math-heavy paper with `--marker-timeout 60`;
   confirm process-boundary kill fires and `queue_status=pending` (retryable).
3. **Full batch test**: enqueue 5 papers, process all; confirm results.jsonl has
   5 records, all with `marker_ready=true`.
4. **Integration gate**: RAG embedding pipeline reads `marker_ready` flag;
   only `marker_ready=true` records are indexed.

---

## Codex Review

Tier: Skip — no execution layer, kill switch, or live trading code touched.

---

## Open Questions / Blockers

- **No RAG integration hook yet**: `marker_ready` is documented but embedding code
  does not yet read results.jsonl. Integration point: the chunker/embedder should
  check `marker_ready=true` before indexing. This is out of scope for this packet.
- **No file locking**: queue.jsonl is rewritten on every status update. Safe for
  single-worker use; concurrent writes would corrupt. v0 design is single-worker only.
- **`_MARKER_DISABLED` global persists across queue items**: if Marker times out on
  item N, items N+1..MAX_ATTEMPTS will immediately fail with `marker_disabled` rather
  than retrying after a restart. The worker must be restarted (new process) after a
  timeout to clear this flag. Document in operator runbook.
