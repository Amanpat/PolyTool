# Marker IPC Live-Validation — Preflight Queue Setup

**Date:** 2026-05-07
**Type:** Preflight only — no live Docker run, no warm-process
**Track:** RIS — L1 Marker IPC Warm-Worker (Feature 3)
**L1 Status:** BLOCKED — preflight items 1, 2, 3 still pending before live run
**warm-process run:** NOT RUN — explicitly excluded from this session scope

---

## Objective

Complete the preflight queue setup steps from the corrected rerun plan
(`2026-05-07_marker-ipc-live-validation-rerun-plan.md`, Codex PASS).
Specifically: verify CLI syntax, select 3 candidate papers with evidence,
create isolated validation queue, enqueue candidates, and verify counts.

---

## Preflight Checklist Status

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | arXiv API cooldown cleared | **FAIL** | API still timing out as of this session. `Invoke-WebRequest` to `export.arxiv.org/api/query?id_list=2604.24366` returned timeout after 25s. Do not run warm-process until API responds with `<entry>` XML. |
| 2 | Papers 2-3 selected and verified by operator | **PARTIAL** | Papers selected with local cache evidence (see Candidate Selection below). Operator visual PDF verification still required before live run. |
| 3 | Docker image rebuilt with Dockerfile.ris fix | **NOT RUN** | Out of scope for this session. Must be run before warm-process. |
| 4 | Fresh validation queue created with 3 verified papers | **PASS** | `artifacts/research/marker_validation_queue` created; 3 papers enqueued with `--url`. All exit 0. |
| 5 | Validation queue counts verified | **PASS** | `{"pending": 3, "processing": 0, "done": 0, "failed": 0, "total": 3}` |

**Live validation remains BLOCKED.** Items 1, 2, and 3 must be checked with evidence before running warm-process.

---

## CLI Syntax Verification

All three help commands executed successfully (exit 0):

```
python -m polytool research-marker-queue --help
python -m polytool research-marker-queue enqueue --help
python -m polytool research-marker-queue counts --help
python -m polytool research-marker-queue list --help
```

**Confirmed correct enqueue syntax:**
```
python -m polytool research-marker-queue [--queue-dir PATH] enqueue --url URL_OR_ID [--title TITLE] [--force] [--json]
```

`--url` is REQUIRED. `--queue-dir PATH` is the isolation flag. `--title` is optional (API-resolved during warm-process).

---

## Candidate Paper Selection

### Paper 1 — Anchor (mandatory)

| Field | Value |
|-------|-------|
| arXiv ID | `2604.24366` |
| Title | The Anatomy of a Decentralized Prediction Market: Microstructure Evidence from the Polymarket Order Book |
| Evidence | **Proven in 2026-05-05 single-paper validation**: cold OCR = 85.9s, body_length = 56,923 chars, body_source = "marker", exit_code = 0. 15 pages, economics prose, minimal figures, no heavy math. |
| Local evidence | `artifacts/research/acquisition_reviews/filter_decisions.jsonl`: decision=allow, score=1.0. Main queue results.jsonl: title confirmed from prior runs. |
| Rate-limit risk | LOW — enqueue is API-free. Metadata call during warm-process is the only risk point. |
| Operator action | None for enqueue. Verify title in queue list output. ✅ Already done. |

---

### Paper 2 — Selected

| Field | Value |
|-------|-------|
| arXiv ID | `1910.08858` |
| Title | Beating the House: Identifying Inefficiencies in Sports Betting Markets |
| Body length (cached) | 58,604 chars (via PDF extraction) ≈ ~15 pages |
| Body source (cached) | `pdf` — paper previously fetched, PDF accessible |
| Filter decision | `allow` (score=0.880797, reason_codes: `["strong_positive:betting market"]`) |
| Abstract summary | Empirical analysis of sports betting market inefficiencies across NFL, NBA, NCAAF, NCAAB, WNBA. Non-parametric win probability model. US sports betting market context. |
| Why expected simple/prose-heavy | Empirical finance/econ paper: sports market analysis, regression/statistics methodology, NOT an ML architecture paper. Body length ≈ 15 pages (same as anchor). No mathematical physics or dense equation blocks expected. Category likely q-fin.TR or econ.EM. |
| Local evidence | `raw_source_cache/academic/1b7ea11f48bcad8e.json`: title confirmed, abstract confirmed, body_length=58,604, body_source=pdf (accessible). `filter_decisions.jsonl`: decision=allow. |
| Rate-limit risk | LOW — enqueue is API-free. |
| Operator action required | **Visual PDF verification still required before warm-process.** Confirm: (a) <20 pages in PDF viewer, (b) fewer than 3 full-figure pages, (c) no dense math blocks. |

---

### Paper 3 — Selected

| Field | Value |
|-------|-------|
| arXiv ID | `2109.07581` |
| Title | The Impact of COVID-19 on Sports Betting Markets |
| Body length (cached) | 41,926 chars (via PDF extraction) ≈ ~11 pages |
| Body source (cached) | `pdf` — paper previously fetched, PDF accessible |
| Filter decision | `allow` (score=0.880797, reason_codes: `["strong_positive:betting market"]`) |
| Abstract summary | Empirical event study of COVID-19 impact on NBA and other sports betting markets. Identifies betting market inefficiency during pandemic. Simple moneyline odds analysis, profit margin calculations. |
| Why expected simple/prose-heavy | Short empirical economics paper (~11 pages). Event study methodology — basic statistical analysis, odds tables, no ML or heavy math. Body length well under anchor paper. Category likely q-fin.TR, econ.EM, or econ.GN. |
| Local evidence | `raw_source_cache/academic/9cb0749d56b09f9d.json`: title confirmed, abstract confirmed, body_length=41,926, body_source=pdf (accessible). `filter_decisions.jsonl`: decision=allow. |
| Rate-limit risk | LOW — enqueue is API-free. |
| Operator action required | **Visual PDF verification still required before warm-process.** Confirm: (a) <20 pages in PDF viewer, (b) fewer than 3 full-figure pages, (c) no dense math blocks. |

### Excluded Papers

| arXiv ID | Reason |
|----------|--------|
| `2412.14173` | Per rerun plan: 2 attempts consumed, 1 remaining. Too risky — any cooldown failure = permanent fail. |
| `2204.05149` | Unverified: title unknown, could be long ML paper. No local cache evidence. |
| `2310.06825` "Mistral 7B" | Used in Runs 1-2; OCR timeout at 900s (55+ text blocks, extreme complexity). NEVER use again. |
| `2005.11401` "RAG paper" | Hit HTTP 429 in Run 2. Complex ML paper. |

---

## Commands Run and Outputs

### arXiv API Rate-Limit Check

```powershell
Invoke-WebRequest -Uri "http://export.arxiv.org/api/query?id_list=2604.24366&max_results=1" -TimeoutSec 25
```

**Output:** `RESULT: REQUEST FAILED — The operation has timed out.`

**Verdict:** API still rate-limited. Preflight item 1 FAILS. Wait additional time before live run.

### Enqueue Commands (all exit 0)

```bash
# Paper 1 — anchor
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/marker_validation_queue \
  enqueue --url 2604.24366 \
  --title "The Anatomy of a Decentralized Prediction Market" \
  --json
# Output: {"candidate_id": "arxiv:2604.24366", "status": "pending", "action": "added"}

# Paper 2
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/marker_validation_queue \
  enqueue --url 1910.08858 \
  --title "Beating the House: Identifying Inefficiencies in Sports Betting Markets" \
  --json
# Output: {"candidate_id": "arxiv:1910.08858", "status": "pending", "action": "added"}

# Paper 3
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/marker_validation_queue \
  enqueue --url 2109.07581 \
  --title "The Impact of COVID-19 on Sports Betting Markets" \
  --json
# Output: {"candidate_id": "arxiv:2109.07581", "status": "pending", "action": "added"}
```

### Counts Verification

```bash
python -m polytool research-marker-queue --queue-dir artifacts/research/marker_validation_queue counts --json
```

**Output:**
```json
{
  "pending": 3,
  "processing": 0,
  "done": 0,
  "failed": 0,
  "total": 3
}
```

Expected: `pending=3, failed=0, total=3` — **MATCH.**

### List Verification

```bash
python -m polytool research-marker-queue --queue-dir artifacts/research/marker_validation_queue list --status all
```

**Output:**
```
  candidate_id                 status       att   title
  -------------------------------------------------------------------------------------------
  arxiv:2604.24366             pending      0     The Anatomy of a Decentralized Predictio
  arxiv:1910.08858             pending      0     Beating the House: Identifying Inefficie
  arxiv:2109.07581             pending      0     The Impact of COVID-19 on Sports Betting

Total: 3 item(s)
```

All 3 papers: status=pending, attempts=0, correct candidate_ids.

### Main Queue Unchanged (verification)

```bash
python -m polytool research-marker-queue counts --json
```

**Output:** `{"pending": 2, "processing": 0, "done": 0, "failed": 1, "total": 3}`

Same as before this session. Main queue not contaminated.

---

## Isolated Queue Path

```
artifacts/research/marker_validation_queue/
  queue.jsonl    — 3 pending entries
  results.jsonl  — does not exist yet (created on first warm-process result)
```

**NOT the main queue:** `artifacts/research/marker_parse_queue/` (unchanged, `failed=1, pending=2, total=3`)

---

## Exact Next Live-Validation Command

**DO NOT RUN until all 5 preflight items are checked with evidence.**
Items 1, 2, 3 are still incomplete as of this session.

```powershell
# Prerequisites must be complete:
# [x] 1. arXiv API responds with <entry> XML (check with curl before running)
# [ ] 2. Operator has visually verified both PDFs (1910.08858 and 2109.07581)
# [ ] 3. Docker image rebuilt: docker compose --profile ris-gpu build ris-scheduler-gpu

# Pre-flight check (run this first):
curl -s "http://export.arxiv.org/api/query?id_list=2604.24366&max_results=1" | Select-String "entry"
# Expected: line containing <entry> — if empty or timeout, STOP and wait longer

# Then run warm-process:
New-Item -ItemType Directory -Force -Path artifacts/research/marker_ipc_validation | Out-Null

$logFile = "artifacts/research/marker_ipc_validation/warm_process_rerun_$(Get-Date -Format yyyyMMdd_HHmm).log"

docker compose --profile ris-gpu run --rm --no-deps ris-scheduler-gpu `
  python -m polytool research-marker-queue `
    --queue-dir artifacts/research/marker_validation_queue `
    warm-process `
    --max-items 3 `
    --marker-timeout 900 `
    --json `
  2>&1 | Tee-Object -FilePath $logFile

Write-Host "Log written to: $logFile"
```

**STOP immediately if Paper 1 (2604.24366) returns `failure_reason` containing "429" or "Timeout fetching". The rate limit has not cleared.**

---

## Pass/Fail Summary

| Check | Result |
|-------|--------|
| CLI syntax confirmed (enqueue `--url`, counts, list) | **PASS** |
| 3 candidate papers selected with local evidence | **PASS** |
| Papers 2-3 NOT risky/excluded papers | **PASS** — 2412.14173 excluded, 2204.05149 not used |
| Isolated queue created fresh (was MISSING before session) | **PASS** |
| All 3 papers enqueued with correct `--url` syntax, all exit 0 | **PASS** |
| Counts: pending=3, failed=0, total=3 | **PASS** |
| List: all 3 pending, attempts=0 | **PASS** |
| Main queue untouched | **PASS** |
| warm-process NOT run | **PASS — not run** |
| arXiv API cooldown cleared | **FAIL — still timing out** |
| Operator visual paper verification done | **PENDING — human step required** |
| Docker image rebuilt | **NOT RUN — deferred to live-run session** |

**Candidate/queue preflight: PASS for items 4+5. Items 1, 2, 3 remain for next session.**

---

## What Remains Before Live Run

1. **Wait for arXiv API cooldown.** Verify with:
   ```powershell
   Invoke-WebRequest -Uri "http://export.arxiv.org/api/query?id_list=2604.24366&max_results=1" -TimeoutSec 20
   ```
   Proceed only when status is 200 and content contains `<entry>`.

2. **Operator visual verification of papers 2 and 3:**
   - Open `https://arxiv.org/pdf/1910.08858` and confirm: <20 pages, <3 full-figure pages, no dense math
   - Open `https://arxiv.org/pdf/2109.07581` and confirm: <20 pages, <3 full-figure pages, no dense math

3. **Rebuild Docker image:**
   ```powershell
   docker compose --profile ris-gpu build ris-scheduler-gpu
   ```
   Expected: exits 0, no "package directory does not exist" error.

4. **Run live warm-process** (exact command in section above).

---

## warm-process Not Run Confirmation

`warm-process` was NOT invoked in this session. No Docker commands were run.
No live Marker parsing occurred. The main queue was not modified.
Only `enqueue`, `counts`, and `list` subcommands were used, all against the isolated queue.

---

## Codex Review Summary

Tier: skip (docs/artifacts only). No code, tests, Docker, main queue, SVM, or trading files changed.
Issues found: none. Issues addressed: none. Only artifact created is this dev log.
