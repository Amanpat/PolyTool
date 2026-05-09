# Dev Log — Fix: Marker Last Timing Gate References (Codex Final Blockers)

**Date:** 2026-05-08
**Type:** Docs-only
**Track:** RIS — Feature 3 closeout prerequisite
**Codex trigger:** `docs/dev_logs/2026-05-08_codex-verify-marker-final-throughput-claims.md` FAIL

---

## Summary

Addressed the two mandatory Codex FAIL blockers preventing Feature 3 closeout
verification from proceeding. Also updated three locations in the 2026-05-03 dev
log whose stale notes still cited ≤10s/paper as an active blocker condition.

No code, tests, Docker, artifacts, queues, SVM labels/models, trading files, L2,
L4, or feature closeout documents were touched. Feature 3 is NOT moved to
Recently Completed — closeout verification must still run.

---

## Codex Blockers Addressed

### Blocker 1 — `Work-Packet - Marker Single-Paper Validation Control Surface.md`

Codex flagged four locations presenting the ≤10s/paper gate as the active
current blocker on L1 production rollout:

| Location | Old text | Fix |
|----------|----------|-----|
| Frontmatter `unblocks` (line 14) | "still blocked on ≤10s/paper gate" | Strikethrough + "gate rejected/superseded 2026-05-08; revised functional gate PASS — see Feature 3" |
| SUCCESS callout (line 21) | "`parse_seconds=85.95s` exceeds the ≤10s/paper production gate" | Added gate-update paragraph after Evidence line |
| Code block annotation (line 29) | "FAILS ≤10s/paper gate" | Covered by gate-update paragraph added after the callout |
| Verdict summary (line 149) | "L1 production verdict: BLOCKED — … ≤10s/paper production gate" | Renamed to "as-measured (2026-05-05)" + inline supersession note |

The callout itself (lines 21, 29) correctly records the 2026-05-05 validation
measurement. The added gate-update paragraph at line 37 makes the supersession
explicit adjacent to those measurements so no reader is left with the false
impression that ≤10s/paper is still the active requirement.

### Blocker 2 — `Work-Packet - Marker Canonical Academic Parse Queue.md` line 181

Reference Materials item 1 said "papers 2+ expected ≤10s warm" with no
adjacent supersession note.

Fixed: added strikethrough + "timing gate rejected as unrealistic 2026-05-08;
measured warm times: 69.73s paper 2, 48.31s paper 3 — see Feature 3" inline.

---

## Additional Fixes — `docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md`

Codex listed this file as "Consider" (not a mandatory blocker), but it was
in scope and had three references to ≤10s/paper that, while inside STALE
callouts, did not yet have an explicit revised-gate note. Added:

| Line | Context | Fix |
|------|---------|-----|
| 17 | Summary STALE inline note | Added "(historical gate — ≤10s/paper rejected as unrealistic 2026-05-08; revised functional gate accepted — see Feature 3)" |
| 93–94 | Blockquote STALE callout | Same note appended to the <=10s/paper sentence |
| 114 | Setup task item 5 | Added "*(Historical: ≤10s/paper gate rejected as unrealistic 2026-05-08; revised functional gate accepted — see Feature 3.)*" |

---

## Remaining Timing References — Safety Audit

Ran `git grep -n "<=10 s\|<=10s\|≤10s\|10s/paper\|10 seconds\|5-10\|5–10\|~5-10" docs`
(excluding `.ajson`/`.smart-env` caches).

Every remaining match is one of:

**Explicitly superseded/rejected in place:**
- `docs/CURRENT_DEVELOPMENT.md:85` — "Original ≤10s/paper timing gate rejected as unrealistic"
- `docs/CURRENT_DEVELOPMENT.md:118` — "gate later revised 2026-05-08"
- `docs/CURRENT_STATE.md:1783` — "Original ≤10s/paper timing gate rejected as unrealistic"
- `docs/INDEX.md:155–161, 182` — historical log entries; all fix/superseded/blocked labels
- `docs/features/ris-marker-structural-parser-scaffold.md:7, 14, 89` — "rejected as unrealistic", "superseded 2026-05-08", "rejected as unrealistic"
- `docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md:19, 102` — "rejected as unrealistic", "SUPERSEDED 2026-05-08"
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md:43, 56, 96, 126` — all have rejected/superseded/historical notes
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md:152` — "rejected as unrealistic"
- `docs/obsidian-vault/Claude Desktop/Current-Focus.md:57` — "later rejected/revised 2026-05-08"
- `docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md:17, 93–94, 114` — now all have explicit rejected/historical notes (fixed this session)
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md:50, 61, 102, 181` — all have rejected/revised/strikethrough notes (line 181 fixed this session)
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Single-Paper Validation Control Surface.md:14, 37, 151` — frontmatter strikethrough + gate-update paragraph + revised verdict (all fixed this session)

**Historical dev logs (recording what was believed on that date):**
- `docs/dev_logs/2026-05-05_marker-single-paper-control-surface-validation.md:85, 118` — explains the ≤10s gate and why it failed; is the primary evidence source
- `docs/dev_logs/2026-05-05_marker-canonical-parse-queue-packet.md:11, 24, 52, 98` — design intent recorded 2026-05-05
- `docs/dev_logs/2026-05-05_marker-canonical-parse-queue-v0-closeout.md:54, 66, 115` — v0 closeout state at 2026-05-05
- `docs/dev_logs/2026-05-05_context-ris-gpu-scheduler-marker-validation.md:240` — safety audit noting 10s assumption needed revision
- `docs/dev_logs/2026-05-05_obsidian-vault-ris-state-sync.md:55` — state sync snapshot
- `docs/dev_logs/2026-05-05_l3-2-prefetch-label-discovery-activation.md:78` — records expectation at packet-creation time
- `docs/dev_logs/2026-05-05_marker-production-rollout-reconciliation.md:90` — reconciliation log
- `docs/dev_logs/2026-04-27_ris-marker-timeout-concurrency-fix.md:106` — "5–10+ min" Marker thread runtime
- `docs/dev_logs/2026-04-27_ris-marker-timeout-llm-truthfulness.md:33` — same thread runtime context

**Unrelated usage (not Marker PDF parse timing):**
- `docs/archive/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md:1262`, `v5.md:1344` — "every 10 seconds" API polling
- `docs/dev_logs/2026-03-10_marketmaker_v1_calibration_plumbing.md:42` — "1 trade per 10 seconds" kappa calibration
- `docs/dev_logs/2026-04-06_n8n_2x_instance_mcp_upgrade.md:167` — "10 seconds ago" docker container uptime
- `docs/dev_logs/2026-04-15_wallet_discovery_loop_b_pof.md:43, 129` — "5-10 minutes" Alchemy setup time
- `docs/dev_logs/2026-04-15_wallet_discovery_loop_d_pof.md:68` — "subscribe/unsubscribe at runtime" timing
- `docs/dev_logs/2026-04-23_ris_wp4*.md` — "5–10 RIS pipelines / 5–10-workflow" n8n workflow count
- `docs/dev_logs/2026-05-05_ris-marker-docker-static-permission-fix.md:169` — "5-10× longer per box" box processing time
- `docs/obsidian-vault/Claude Desktop/08-Research/02-Metrics-Engine-MVF.md:59` — "5-10 trades" around resolution
- `docs/obsidian-vault/Claude Desktop/08-Research/11-Scientific-RAG-Target-Architecture.md:52` — "5-10 candidate papers" in search
- `docs/obsidian-vault/Claude Desktop/11-Prompt-Archive/...` — archived prompt, CLOB websocket ping interval
- `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md:1472` — "every 10 seconds" KPI cards
- `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md:120` — "5–10 minutes" tape capture
- `docs/runbooks/research_eval_benchmark.md:179` — "under 10 seconds" for indexing 23 corpus papers

---

## Scoped Dirty-Path Evidence

### Before (baseline from Codex review log)

```
M	Dockerfile.ris
M	packages/research/ingestion/fetchers.py
M	packages/research/ingestion/marker_queue.py
M	tests/test_ris_marker_queue.py
M	tools/cli/research_marker_queue.py
```

### After (confirmed this session)

```
M	Dockerfile.ris
M	packages/research/ingestion/fetchers.py
M	packages/research/ingestion/marker_queue.py
M	tests/test_ris_marker_queue.py
M	tools/cli/research_marker_queue.py
```

Identical. No implementation, test, Docker, artifact, SVM, or trading files changed.

---

## Commands Run

```
git diff --name-status -- packages tools tests polytool config infra docker-compose.yml Dockerfile.ris artifacts
# → same 5 files as baseline; unchanged

git grep -n "<=10 s|<=10s|≤10s|10s/paper|10 seconds|5-10|5–10|~5-10" docs
# → all remaining matches verified safe (see audit above)

git diff --stat -- docs
# → docs-only changes confirmed
```

---

## Files Changed and Why

| File | Change | Reason |
|------|--------|--------|
| `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Single-Paper Validation Control Surface.md` | Frontmatter unblocks item: strikethrough + superseded note. Callout: added gate-update paragraph. Verdict line: "as-measured 2026-05-05" + supersession note. | Codex mandatory blocker 1 |
| `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md` | Reference Materials item 1: strikethrough ≤10s + measured warm times + Feature 3 pointer | Codex mandatory blocker 2 |
| `docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md` | Three locations (summary stale note, blockquote stale callout, setup task 5): explicit "historical gate — rejected 2026-05-08" notes added | Codex "Consider" item; in scope; stale notes cited old gate as active blocker |

---

## Whether Codex Closeout Verification May Rerun

Yes. Both mandatory Codex FAIL blockers are resolved. The 2026-05-03 dev log
stale-note references are also addressed. All remaining ≤10s/paper / 5-10s
timing mentions are explicitly historical, rejected, or superseded in place.

Feature 3 closeout verification may now proceed.

**Feature 3 is NOT moved to Recently Completed** — that step requires closeout
verification to pass first.
