---
title: "Backlog — Remove PlainTextExtractor content-sniffing (/→path) heuristic"
type: work_packet
status: draft
source_zone: claude_memory
last_updated: 2026-06-01
lifecycle: draft
tags: [work-packet, backlog, ris, ingestion, tech-debt]
target_agent: claude-code
acceptance_criteria:
  - See Definition of Done
---
# Backlog — Remove PlainTextExtractor content-sniffing (`/`→path) heuristic

**Status: BACKLOG (deferred).** Surfaced during the Wallet-Ingestion v1 live two-pass validation
(2026-06-01). Tracked here for later; NOT for the current sprint.

## Problem
`PlainTextExtractor.extract` (`packages/research/ingestion/extractors.py`) decides file-mode vs
raw-text-mode by sniffing the string: if a raw-text `source` contains `/` or `\\`, it assumes a
missing file path and raises `FileNotFoundError`. This is fragile — any raw body containing a slash
(dates, percentages, URLs, prose, dossier memos) is mis-classified. It silently broke dossier ingest
until the WI validation fix added an explicit `raw_text=True` bypass (commit `ae4947d`).

## Interim state (already shipped)
- `extract` accepts `raw_text: bool` (default False). When True, both the file probe and the
  content-sniffing guard are skipped. The dossier ingest passes `raw_text=True`.
- The heuristic remains in place for all callers that do NOT pass `raw_text` — so this debt is
  contained, not active for the dossier path.

## Scope (when picked up)
1. **Full caller audit:** enumerate every `IngestPipeline.ingest` / `*.extract` caller and classify
   each as file-path vs raw-text intent (grep `extract(`, `pipeline.ingest(`, `get_extractor`).
2. Replace the content-sniffing heuristic with an **explicit** mode contract: callers pass a real
   path OR raw text + an explicit flag — never inferred from string content.
3. Migrate every caller to the explicit contract; add `raw_text=True` (or a path) at each site.
4. Remove the `/`/`\\` sniffing branch.
5. Regression tests per caller family (academic, manual, dossier, marker).

## Definition of Done
- [ ] No code path infers file-vs-raw from the presence of `/`/`\\` in the string.
- [ ] Every extractor/ingest caller passes an explicit mode; tests cover each family.
- [ ] Dossier `raw_text=True` bypass folded into the unified contract.

## Cross-References
- Dev log: `docs/dev_logs/2026-06-01_wi-validation-fix.md`
- [[claude-memory/work-packets/work-packet-wi-2-dossier-supersede]]

## Connections
- [[claude-memory/work-packets/_index]]
- [[index|Vault Home]]
