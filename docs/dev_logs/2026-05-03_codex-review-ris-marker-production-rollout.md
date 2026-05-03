# Codex Review - RIS Marker Production Rollout

Date: 2026-05-03
Reviewer: Codex
Scope: Review L1 Marker production rollout after Claude Prompt A.

## Verdict

FAIL

The implementation makes `LiveAcademicFetcher` default to Marker and includes
`marker-pdf` in the `[ris]` extra, but it does not safely make Marker the
production default end to end.

Prompt B should not proceed to live GPU validation yet. Fix the blocking
scheduler split and `marker_failed` ingestion semantics first, then run the
GPU validation.

## Commands Run

### Startup / repo state

`git status --short`

Result: exit 0. Pre-existing dirty files were present before this review:

```text
 M docs/obsidian-vault/.obsidian/workspace.json
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_09-Decisions_Decision_-_Academic_Pipeline_Hosting_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
 M docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md
 M docs/obsidian-vault/Claude Desktop/Current-Focus.md
?? docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md
```

`git log --oneline -5`

```text
94a074c feat(ris): L1 Marker production rollout - default parser, GPU Docker, explicit failure semantics
f5bf5af L3.1 Complete
ac3aebc feat(ris): L3.1 prefetch review queue + label store + hold-review mode
a923e6a Academic Pipeline Improvements L0 - L2
1520e18 fix(ris): L3 pre-fetch filter v0 - Codex FAIL resolution (v1.1)
```

`python -m polytool --help`

Result: exit 0. CLI loaded and listed `research-acquire`,
`research-parser-benchmark`, `research-scheduler`, and other RIS commands.

### Required checks

`python -m pytest tests/test_ris_academic_pdf.py tests/test_ris_research_acquire_cli.py`

```text
collected 69 items
69 passed in 1.15s
```

`python -m polytool research-acquire --help`

Result: exit 0. Help printed successfully and included `--url`, `--search`,
`--source-family`, `--prefetch-filter-mode`, and related options.

`docker compose config`

Result: exit 0. Compose rendered successfully. Full output is intentionally
not copied here because it expands `.env` values, including secrets/tokens.
Important non-secret observation: default `docker compose config` does not
include the profile-gated `ris-scheduler-gpu` service.

Additional profile check:

`docker compose --profile ris-gpu config --services`

```text
clickhouse
api
grafana
migrate
ris-scheduler
ris-scheduler-gpu
```

`docker compose --profile ris-gpu config | Select-String ...`

Relevant non-secret lines confirmed:

```text
ris-scheduler-gpu
capabilities:
  - gpu
driver: nvidia
RIS_PDF_PARSER: marker
source: C:\Users\patel/.cache/datalab
target: /root/.cache/datalab
```

`git diff --check`

Result: exit 0. Output was line-ending warnings only for pre-existing Obsidian
working-tree files.

### Targeted review probes

`python -c "... AcademicAdapter marker_failed probe ..."`

```text
marker_failed
99
This abstract is long enough t
```

This proves `AcademicAdapter` still turns empty `body_text` into the abstract
even when `body_source="marker_failed"`.

`git ls-files | Select-String -Pattern "\.(pt|pth|safetensors|onnx|ckpt)$|(^|/)(datalab|models?|weights?)(/|$)|\.bin$"`

Result: exit 0, no matches.

`git ls-files -o --exclude-standard | Select-String -Pattern "\.(pt|pth|safetensors|onnx|ckpt)$|(^|/)(datalab|models?|weights?)(/|$)|\.bin$"`

Result: exit 0, no matches.

## Findings

### Blocking

1. `marker_failed` is not an end-to-end rejection.

`packages/research/ingestion/fetchers.py` now returns `body_text=""` with
`body_source="marker_failed"`, but `packages/research/ingestion/adapters.py`
lines 130-137 still implement "prefer body_text, fall back to abstract".
That means an academic Marker failure can become an abstract-only
`ExtractedDocument` before hard stops and storage. Any abstract longer than
50 characters can pass the hard-stop length check, so acquisition review may
record a normal ingest instead of the Marker failure.

This violates the rollout requirement: "Marker failures are visible and
recoverable, not silently abstract-only."

2. The CPU `ris-scheduler` still schedules academic ingest with
`RIS_PDF_PARSER=pdfplumber`.

`docker-compose.yml` lines 132-142 start the default `ris-scheduler` with
`RIS_PDF_PARSER=pdfplumber` and the normal `research-scheduler start`
command. `packages/research/scheduling/scheduler.py` lines 54-59 register
`academic_ingest`, and lines 373-395 add every job in `JOB_REGISTRY` to every
scheduler instance. There is no job filter or split.

The hosting decision says academic ingest moves to the dev-machine GPU while
reddit/blog/youtube/github remain on the CPU host. The compose implementation
does not enforce that split. In default Compose, academic ingest still exists
on the CPU service and uses pdfplumber. With the `ris-gpu` profile enabled,
both services are present and both run the same all-jobs scheduler.

This violates "Marker is the default academic parser" and the accepted
scheduler split.

3. The model cache mount targets `/root/.cache/datalab`, but the GPU image
runs as `polytool`.

`Dockerfile.ris` creates and switches to `USER polytool` at line 121.
`docker-compose.yml` line 182 mounts the host cache at `/root/.cache/datalab`.
Marker's normal `~/.cache/datalab` path for the running user will resolve to
the `polytool` home, not `/root`. Prompt B would not actually validate the
intended host cache reuse unless the cache path is corrected or the cache env
is explicitly set.

This violates the model-cache volume requirement.

### Non-blocking / Medium

1. Stale pdfplumber assumptions remain in comments and docs.

Examples:
- `packages/research/ingestion/fetchers.py` lines 161-165 still describe
  pdfplumber as the default/auto fallback behavior for `_fetch_pdf_body`.
- `tests/test_ris_academic_pdf.py` line 779 says the busy Marker path returns
  `pdfplumber_fallback`, but the assertion now expects `marker_failed`.
- `docs/features/ris-marker-structural-parser-scaffold.md` still says the
  disabled timeout path falls back to pdfplumber, even though production Marker
  mode now returns `marker_failed`.

These do not create runtime behavior by themselves, but they directly conflict
with the "no stale pdfplumber assumptions" requirement.

2. Tests cover fetcher-level default/failure semantics, but not production
ingest semantics.

The 69 targeted tests pass, including `TestMarkerProductionDefault`, but they
do not test that `marker_failed` is rejected by `AcademicAdapter`,
`IngestPipeline`, `research-acquire`, or the acquisition review JSONL. They
also do not test that the scheduler split prevents academic jobs from running
on the CPU pdfplumber service.

## Checks Against Requested Criteria

1. Marker dependency in normal RIS production path: PASS.
`pyproject.toml` puts `marker-pdf>=1.0` in `[ris]`.

2. Docker/Compose GPU passthrough and model cache on correct service: FAIL.
GPU reservation exists on `ris-scheduler-gpu`, but the cache target is wrong
for the runtime user and the profile-gated service is not included by default
`docker compose config`.

3. Marker is the default academic parser: FAIL.
Fetcher default is Marker, but the default CPU scheduler still runs academic
jobs with `RIS_PDF_PARSER=pdfplumber`.

4. pdfplumber not silently used as production-equivalent fallback: FAIL.
The CPU scheduler still uses pdfplumber for academic jobs.

5. Marker failures visible/recoverable, not abstract-only: FAIL.
Fetcher behavior is explicit, but adapter/pipeline behavior can still turn
`marker_failed` into an abstract-only ingest.

6. No `marker_llm_boost` label returns: PASS.
Runtime metadata uses `body_source="marker"` with
`marker_llm_requested=True` / `marker_llm_applied=False` when requested.
Occurrences found were comments/tests/docs, not returned labels.

7. No model weights/caches/artifacts committed: PASS.
Tracked and untracked scans found no model-weight/cache matches.

8. No PaperQA2/SVM/multi-source/n8n/trading scope creep: PASS.
No new rollout code for those areas was found in the Prompt A diff. Existing
n8n and relevance-filter content predates this rollout.

9. Tests cover default parser and failure semantics: FAIL.
They cover fetcher semantics, not end-to-end rejection/acquisition-review
semantics or scheduler production routing.

## Prompt B Readiness

Prompt B should not proceed to live GPU validation yet.

Minimum fix set before Prompt B:

1. Make `marker_failed` an explicit ingest rejection before adapter fallback
can reintroduce the abstract, and add a CLI/acquisition-review test for it.
2. Implement the scheduler split so the CPU service cannot run
`academic_ingest`, and the GPU service does not duplicate all CPU jobs.
3. Mount the datalab cache at the runtime user's actual cache path or set the
cache environment explicitly.
4. Clean stale pdfplumber comments/docs that now contradict production mode.

