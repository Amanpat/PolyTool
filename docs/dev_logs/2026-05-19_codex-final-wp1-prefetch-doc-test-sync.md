# Codex Final WP-1 Prefetch Doc/Test Sync

**Date:** 2026-05-19
**Track:** RIS L1 Marker queue
**Type:** Narrow cleanup / verification

---

## Files Changed

| File | Why |
|------|-----|
| `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` | Replaced the two stale `prefetch --status` examples with the actual `status-report` command. |
| `tests/test_ris_marker_queue.py` | Removed the avoidable xfail now that the runbook/CLI mismatch is corrected. |
| `docs/dev_logs/2026-05-19_codex-final-wp1-prefetch-doc-test-sync.md` | Required handoff log for this work unit. |

No implementation code, benchmark baselines, 29-paper artifacts, Docker/GPU validation, or non-academic RIS pipeline code were changed.

---

## Commands Run

### Session state

```powershell
git status --short
```

Output showed unrelated local Obsidian changes, plus in-scope pre-existing `tests/test_ris_marker_queue.py` edits and an untracked prior Codex dev log:

```text
 M docs/obsidian-vault/.obsidian/graph.json
 M docs/obsidian-vault/.obsidian/workspace.json
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_11-Prompt-Archive_2026-04-21_Architect_Custom_Instructions_v2_md.ajson
 M "docs/obsidian-vault/Claude Desktop/11-Prompt-Archive/2026-04-21 Architect Custom Instructions v2.md"
 M tests/test_ris_marker_queue.py
?? docs/dev_logs/2026-05-19_codex-tests-academic-prefetch-separation-wp1.md
?? docs/obsidian-vault/.smart-env/multi/Claude_Desktop_11-Prompt-Archive_2026-04-22_Architect_Custom_Instructions_v3_md.ajson
?? "docs/obsidian-vault/Claude Desktop/11-Prompt-Archive/2026-04-22 Architect Custom Instructions v3.md"
```

```powershell
git log --oneline -5
```

```text
50775d1 feat(ris): WP-1 academic PDF prefetch separation
1fb000d Academic Pipeline Improvements/Testing
de72208 docs(ris): academic pipeline scaled validation - Batch 1 execution record
03c9546 academic pipeline complete
dbcf2ec feat(ris): L4 Multi-source Academic Harvesters - Feature 3 closed
```

```powershell
python -m polytool --help
```

Result: exit 0; top-level CLI loaded and listed `research-marker-queue`.

### Runbook / CLI contract checks

```powershell
rg -n "prefetch --status|--status|status-report" docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md tests/test_ris_marker_queue.py
```

Initial output confirmed stale runbook examples at lines 341 and 439 using `--status`, plus valid `status-report` references.

```powershell
python -m polytool research-marker-queue prefetch --help
```

```text
usage: polytool research-marker-queue prefetch [-h] [--max-items N]
                                               [--delay-seconds SECONDS]
                                               [--json]

options:
  -h, --help            show this help message and exit
  --max-items N         Max pending items to prefetch (default: all pending)
  --delay-seconds SECONDS
                        Seconds to sleep between successive PDF downloads
                        (default: 10.0). Keep >= 5s to avoid arXiv rate limits
                        under sustained load.
  --json                Output result as JSON
```

```powershell
python -m polytool research-marker-queue status-report --help
```

```text
usage: polytool research-marker-queue status-report [-h] [--json]

options:
  -h, --help  show this help message and exit
  --json      Output report as JSON
```

Post-edit check:

```powershell
rg -n "prefetch --status|--status|status-report" docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md tests/test_ris_marker_queue.py
```

Result: no `prefetch --status` references remain. Remaining `--status` hits are valid `research-marker-queue list --status ...` examples and the regression test's forbidden-string assertions.

```powershell
rg -n "xfail" tests/test_ris_marker_queue.py
```

Result: no output. The avoidable xfail was removed.

### Focused WP-1 tests

```powershell
pytest tests/test_ris_marker_queue.py -q
```

```text
collected 145 items
144 passed, 1 skipped in 2.80s
```

### Adjacent queue/fetcher subset

```powershell
pytest tests/test_ris_marker_queue.py tests/test_ris_fetchers.py tests/test_ris_marker_ipc_worker.py tests/test_ris_claim_extraction.py -q
```

```text
collected 299 items / 3 deselected / 296 selected
295 passed, 1 skipped, 3 deselected, 2 warnings in 70.85s (0:01:10)
```

Warnings were existing Pydantic deprecation warnings from `marker` / `surya`.

### Full-suite stop-at-first-failure smoke

```powershell
python -m pytest tests/ -x -q --tb=short
```

```text
collected 5145 items / 3 deselected / 5142 selected
FAILED tests/test_ris_phase4_source_acquisition.py::TestEndToEnd::test_ingest_external_arxiv_fixture
AssertionError: Rejected: academic_marker_gate: body_source='abstract' with body_length=0 is not Marker-quality; only Marker-parsed bodies (>= 5000 chars) are indexed as canonical academic corpus
1 failed, 3298 passed, 1 skipped, 3 deselected, 21 warnings in 206.07s (0:03:26)
```

The unrelated full-suite RIS gate mismatch still exists and was not fixed here.

---

## Decisions

- The actual CLI contract is `research-marker-queue status-report`; `prefetch` has no `--status` flag.
- Updated only stale runbook examples; valid `list --status` examples were left unchanged.
- Removed the xfail because the mismatch is now resolved and should be protected by a normal regression test.
- Did not touch implementation code because the documented command exists and help exits 0.

---

## Remaining Mismatches / Blockers

- Unrelated full-suite failure remains: `tests/test_ris_phase4_source_acquisition.py::TestEndToEnd::test_ingest_external_arxiv_fixture` expects abstract-only arXiv fixture ingestion to pass, but the current academic gate rejects non-Marker academic bodies.
- No WP-1 doc/CLI mismatch remains in `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`.

---

## Codex Review Summary

Tier: skip. Only docs/tests/dev log changed; no execution, risk, rate limiter, order placement, or live-trading paths touched.
