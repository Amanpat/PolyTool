---
title: Claude Review Marker Docker Ipc Live Validation
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-07_claude-review-marker-docker-ipc-live-validation.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Read-Only Review: Marker Docker IPC Warm-Worker Live Validation Evidence

**Date:** 2026-05-07
**Reviewer:** Claude Code (read-only pass)
**Overall verdict: FAIL — Live validation evidence is insufficient; Codex code review may proceed but L1 production is not unblocked.**

---

## Files and Artifacts Reviewed

- `docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-live-validation.md` (primary validation dev log)
- `docs/dev_logs/2026-05-07_claude-review-marker-docker-ipc-worker-integration.md` (integration code review)
- `docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-v1-activation.md` (Codex activation verify — FAIL)
- `docs/dev_logs/2026-05-07_fix-marker-docker-ipc-warm-worker-v1-activation.md` (fix log for activation blockers)
- `docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-activation.md` (Feature 3 activation)
- `artifacts/research/marker_ipc_validation/warm_process_20260507.log` (run 1 — stale extractors, TypeError)
- `artifacts/research/marker_ipc_validation/warm_process_20260507_run2.log` (run 2 — fixed extractors, 900s timeout)
- `artifacts/research/marker_ipc_validation/warm_process_20260507_run3.log` (run 3 — LoRA paper, aborted)
- `artifacts/research/marker_ipc_validation/warm_process_20260507_run4.log` (run 4 — arXiv API blocked)
- `artifacts/research/marker_parse_queue/results.jsonl` (queue results from final run)
- `docs/CURRENT_DEVELOPMENT.md` (active feature state)
- `docs/obsidian-vault/Claude Desktop/Current-Focus.md` (navigation doc)

---

## Commands Run

```powershell
rtk git status --short
rtk git diff --stat
rtk git log --oneline -8
python -m pytest tests/test_ris_marker_ipc_worker.py tests/test_ris_marker_queue.py -q --tb=no
python -m polytool research-marker-queue counts --json
docker ps
cat artifacts/research/marker_parse_queue/results.jsonl
cat artifacts/research/marker_ipc_validation/warm_process_20260507.log
cat artifacts/research/marker_ipc_validation/warm_process_20260507_run2.log
cat artifacts/research/marker_ipc_validation/warm_process_20260507_run3.log
cat artifacts/research/marker_ipc_validation/warm_process_20260507_run4.log
Select-String -Path docs/CURRENT_DEVELOPMENT.md -Pattern "L1|Feature 3|IPC|warm"
Select-String -Path "docs/obsidian-vault/Claude Desktop/Current-Focus.md" -Pattern "L1.*unblock"
rtk git diff HEAD -- "docs/obsidian-vault/Claude Desktop/Current-Focus.md" docs/INDEX.md
```

---

## Gate-by-Gate Findings

### Gate 1 — At least 3 papers processed in one warm-worker session

**FAIL.**

Zero papers completed parsing in any single run:
- Run 1: stale `extractors.py` caused `TypeError` on first paper; subsequent attempts returned `worker_not_running`.
- Run 2: fixed extractors; Mistral 7B (55 pages) timed out at 900s after 47/55 pages; subsequent papers returned `worker_not_running` or HTTP 429.
- Run 3: LoRA paper (139 chunks including appendix) aborted manually at 14 minutes (~43/139 chunks done) because projected total OCR exceeded 900s.
- Run 4: all 3 papers failed at arXiv metadata API stage (timeout/429) before PDFs were downloaded.

No per-paper timing table can be produced because no paper successfully completed.

### Gate 2 — Paper 1 timing identified separately from papers 2+

**NOT TESTED.** Gate 1 not passed; no paper reached completion.

Cold-load was observed: run 1 shows model load took ~52s before the `TypeError` hit. Run 2 shows GPU OCR progress bars completing layout/OCR detection phases (~6s total) before the 900s OCR timeout for text recognition. This confirms the cold-start path works, but no warm-path (paper 2+) data exists.

### Gate 3 — Papers 2+ each have parse_seconds <= 10s

**NOT TESTED.** Paper 1 never completed.

### Gate 4 — Each result shows `ipc_warm_worker_used=true`

**PASS (partial).**

- Run 1 records (from log): all 3 attempt records have `"ipc_warm_worker_used": true`.
- Run 2 records (from log): all 5 attempt records have `"ipc_warm_worker_used": true`.
- Run 4 records (from `results.jsonl`): per-paper records do NOT contain the `ipc_warm_worker_used` key. However, the run-level JSON response does include `"ipc_warm_worker_used": true`. The field is absent from individual paper records because the arXiv API failure occurred before any IPC parse was attempted — the IPC worker was started but never invoked for these papers. This is consistent with the implementation contract (the field on paper records reflects whether the IPC path was actually used for that paper's parse).

Verdict: the IPC routing is correct and the flag is correctly scoped to parse-path usage. The absence in run 4 paper records is not a bug.

### Gate 5 — No pdfplumber fallback in any result

**PASS.**

Every `body_source` across all runs is either `"marker_failed"` (IPC parse error/timeout) or `"error"` (fetch failure). No `"pdfplumber"`, `"pdfplumber_fallback"`, or `"pdf"` appears in any result record.

### Gate 6 — Worker shutdown / orphan process check performed

**PASS.**

The live validation dev log records:
```
docker exec ris-gpu-validation bash -c "ls /proc | grep '^[0-9]' | wc -l"
# Output: 6
```
Only 6 processes (sleep 7200 + bash exec + thread-self + variants). No Marker, Surya, or Python OCR subprocesses. Container stopped and removed at session end.

One warning observed in run 2 output:
```
resource_tracker: There appear to be 1 leaked semaphore objects to clean up at shutdown
```
This indicates a semaphore resource leak in the IPC worker's multiprocessing teardown. Not a zombie process but a non-fatal cleanup gap. Should be investigated before production use.

### Gate 7 — Queue state / result semantics intact

**PASS.**

State transitions (`pending → processing → pending` on retry, `pending → failed` on max retries) are correct. Retry counting increments correctly (attempt 1, 2, 3). `results.jsonl` appends on every attempt. `counts --json` returns `{"pending": 2, "processing": 0, "done": 0, "failed": 1, "total": 3}` — consistent with the final state of the queue after run 4.

### Gate 8 — No implementation files changed during validation

**PASS.**

Current `git status --short` matches the baseline recorded at validation session start:
```
M packages/research/ingestion/fetchers.py
M packages/research/ingestion/marker_queue.py
M tests/test_ris_marker_queue.py
M tools/cli/research_marker_queue.py
?? packages/research/ingestion/marker_ipc_worker.py
?? tests/test_ris_marker_ipc_worker.py
```
No implementation, test, config, infra, artifact, or trading files were modified during the validation session. All 119 tests pass, 1 skipped — identical to session start.

### Gate 9 — L1 is not marked unblocked in docs

**PASS (with one stale doc caveat).**

- `docs/CURRENT_DEVELOPMENT.md`: correctly states "L1 Marker Production Rollout remains PAUSED — blocked on Docker IPC warm-worker v1" and "Blocked on Docker IPC warm-worker (v1)" in the Paused/Deferred table.
- `docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-live-validation.md`: concludes "L1 production is NOT unblocked."
- `docs/obsidian-vault/Claude Desktop/Current-Focus.md` (lines 20 and 56): still contains stale "L1 Marker production rollout is now unblocked" language from 2026-05-03 (before the IPC warm-worker requirement was discovered). The fix log (`2026-05-07_fix-marker-docker-ipc-warm-worker-v1-activation.md`) documents fixes to these lines, but those changes were never committed — `Current-Focus.md` at HEAD retains the stale content. This is a documentation gap, not a code issue, and does not represent an actual claim that live validation has passed.

Net verdict: no authoritative doc claims live validation succeeded. The stale Current-Focus.md language predates the IPC requirement discovery (2026-05-05) and is a known unfixed item from the Codex activation verify FAIL.

---

## Additional Structural Finding: Feature 3 Activation Not in Committed State

The activation dev log (`2026-05-07_marker-docker-ipc-warm-worker-v1-activation.md`) claims Feature 3 was added to `CURRENT_DEVELOPMENT.md` (active count → 3). However, `CURRENT_DEVELOPMENT.md` at HEAD still shows "Active count is now 2 (Features 1 and 2) — one Feature 3 slot is available." The activation changes were described in the dev log but were never committed. The Feature 3 active slot was claimed in an untracked doc but not in the committed state of the repo.

This is a latent inconsistency between the untracked dev logs and the committed repo state. The live validation FAIL means it is not a correctness blocker (Feature 3 is not done), but it should be resolved before closeout.

---

## Per-Run Evidence Artifact Paths

| Run | Artifact | Key observation |
|-----|----------|-----------------|
| Run 1 | `artifacts/research/marker_ipc_validation/warm_process_20260507.log` | `TypeError` from stale `extractors.py`; `ipc_warm_worker_used: true` on all 3 attempt records |
| Run 2 | `artifacts/research/marker_ipc_validation/warm_process_20260507_run2.log` | GPU OCR confirmed; 47/55 pages before 900s timeout; leaked semaphore warning |
| Run 3 | `artifacts/research/marker_ipc_validation/warm_process_20260507_run3.log` | LoRA 139-chunk paper; aborted at 43 chunks (~10min); projected 20+ min total |
| Run 4 | `artifacts/research/marker_ipc_validation/warm_process_20260507_run4.log` + `results.jsonl` | All 3 papers blocked by arXiv API timeout/429; no PDFs fetched |

---

## Codex Code Review Readiness

**May proceed.** The Claude integration review (`2026-05-07_claude-review-marker-docker-ipc-worker-integration.md`) gave PASS on all 8 implementation checks: IPC routing, no `_MARKER_DISABLED` set, no pdfplumber fallback, Windows thread path unchanged, worker lifecycle, test coverage (119 pass / 1 skip), and scope (only expected 4 modified + 2 new files). The code is real, tested offline, and structurally correct.

Codex code review is not blocked by the live validation failure — those are independent assessments. The live validation failure establishes that IPC warm throughput on real GPU hardware has not been demonstrated, which blocks L1 production sign-off. Codex review can audit the code quality independently.

Suggested Codex scope (from integration review):
- `packages/research/ingestion/fetchers.py` — IPC dispatch routing, no fallback
- `packages/research/ingestion/marker_queue.py` — worker lifecycle, `finally` shutdown, flag propagation
- `tools/cli/research_marker_queue.py` — `warm-process` subcommand, L1 gate reminder
- `tests/test_ris_marker_queue.py` — new IPC test classes

---

## Remaining Blockers Before L1 Acceptance Gates Can Be Retested

| # | Blocker | Required Fix |
|---|---------|-------------|
| 1 | arXiv metadata API rate limiting | Wait ≥1 hour after last API call, OR add local-PDF queue mode (code change) |
| 2 | Complex papers exceed 900s timeout | Use only simple text-heavy papers (<20 pages, minimal figures/equations): economics, policy, social science. Avoid ML papers with figures/equations. |
| 3 | Worker not restarted after timeout | `_marker_ipc_worker_extract()` in `fetchers.py` must call `self._ipc_worker.restart()` after detecting a `marker_timeout` result before returning. Code change required. |
| 4 | Leaked semaphore on shutdown | Investigate `resource_tracker: 1 leaked semaphore` warning in IPC worker teardown. Non-blocking for re-validation but should be fixed for production. |
| 5 | Dockerfile.ris rebuild fails | Add `mkdir -p packages/research/relevance_filter` to builder stub step; rebuild image. Workaround: `docker cp` each changed file per session. |
| 6 | Current-Focus.md stale L1 language | Commit the fix described in `fix-marker-docker-ipc-warm-worker-v1-activation.md` (lines 20 and 56). |
| 7 | CURRENT_DEVELOPMENT.md Feature 3 slot | Commit Feature 3 as Active in CURRENT_DEVELOPMENT.md or explicitly document decision not to (if activation is deferred). |

---

## Overall Verdict

**FAIL.**

The live Docker/GPU validation session confirmed the IPC warm-worker routing, GPU model loading, and queue state machine work correctly. However, zero papers completed parsing in any single run due to: arXiv API rate limiting, complex paper OCR exceeding the 900s timeout, and a worker-restart-after-timeout gap that cascades remaining papers to immediate failure once paper 1 times out.

The acceptance gates that require ≥3 papers in one session and papers 2+ at ≤10s/paper were not testable. L1 production remains blocked.

Codex code review of the implementation may proceed independently. L1 sign-off requires a successful re-validation once the three root causes above are resolved.

---

## Codex Review Summary

Tier: Skip. This review session is read-only — no implementation, tests, queue state, artifacts, SVM, L2/L4, or trading files were modified. This dev log is the only file written.
