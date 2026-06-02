---
title: "Wikilink Triage — Phase 4 Vault Redesign Cleanup"
type: work_packet
status: active
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: verified
phase5_amended: 2026-05-23
tags: [work-packet, vault, wikilinks, triage, phase4]
target_agent: human
acceptance_criteria:
  - All 18 originally unresolved links triaged
  - fix-wikilinks.py reports 0 unresolved after HTML comment stripping wired in
  - Source files updated in place (LEGACY comments or frontmatter plain text)
  - Script updated to skip fenced blocks, inline code, and HTML comments
---

# Wikilink Triage — Phase 4 Vault Redesign Cleanup

> **Status: COMPLETE — 2026-05-23**
> fix-wikilinks.py run after all edits: **0 unresolved, 0 ambiguous, 960 OK**.

## Context

Phase 4 of the vault redesign cleanup found 18 unresolved wikilinks when `docs/scripts/fix-wikilinks.py` was first run. These links pointed to legacy zones or files that no longer exist in the current vault structure. This packet records every triage decision.

---

## Scanner Fixes Applied

`docs/scripts/fix-wikilinks.py` had three gaps that caused false positives and incorrect auto-fixes:

| Gap | Fix |
|-----|-----|
| Fenced code blocks (` ``` `) were not stripped before scanning | Added `FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)` applied first |
| HTML comments (`<!-- ... -->`) were not stripped | Added `HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)` applied third |
| Multi-line wikilinks in table cells broke table rendering in generated report | Added `.replace("\n", " ")` in table generation |

Without the HTML comment fix, every `<!-- LEGACY: [[...]] -->` comment was itself scanned and re-reported as unresolved, creating a feedback loop.

---

## Triage Decisions

### Group 1 — Hermes Agent Platform Evaluation (3 links)

**Original link:** `[[12-Ideas/Idea - Hermes Agent Platform Evaluation]]`

**Files:**
- `claude-memory/decisions/decision-agent-parallelism-ris-phase2.md`
- `claude-memory/research/reference-hermes-agent-integration-guide.md`
- `claude-memory/research/ris-operational-readiness-roadmap-v1.md`

**Decision:** LEGACY comment. The source file exists at `Claude Desktop/12-Ideas/Idea - Hermes Agent Platform Evaluation.md` (legacy zone, not migrated). The link is informational context only — no navigation value until the file is migrated.

**Applied:** `<!-- LEGACY: [[12-Ideas/Idea - Hermes Agent Platform Evaluation]] -->` inline.

---

### Group 2 — RIS Phase 2 Gap Closure Roadmap (1 link)

**Original link:** `[[07-RIS-Phase2-Gap-Closure-Roadmap (2026-04-10 version)]]`

**File:** `claude-memory/research/ris-operational-readiness-roadmap-v1.md`

**Decision:** LEGACY comment. No file with this name exists in any current vault zone. The link refers to a historical iteration document. Cross-reference value is low (the content it pointed to predates the current roadmap structure).

**Applied:** `<!-- LEGACY: [[07-RIS-Phase2-Gap-Closure-Roadmap (2026-04-10 version)]] -->` inline.

---

### Group 3 — Architecture note (3 links)

**Original link:** `[[01-Architecture]]`

**File:** `claude-memory/research/research-roadmap-v6-master-draft.md`

**Decision:** LEGACY comment. `01-Architecture` was a legacy zone prefix. No direct file with this name exists in claude-memory. The roadmap draft uses it as a placeholder for the architecture section that was to be written as a separate doc. The comment preserves the intent without polluting the scanner.

**Applied:** `<!-- LEGACY: [[01-Architecture]] -->` in all three table rows and inline paragraph references.

---

### Group 4 — LLM Chunking Prompt Archive (1 link)

**Original link:** `[[11-Prompt-Archive/2026-04-08 GLM5 - LLM Chunking]]`

**File:** `claude-memory/session-notes/2026-04-09-wallet-discovery-pipeline-design.md`

**Decision:** LEGACY comment. The prompt archive file exists at `Claude Desktop/11-Prompt-Archive/2026-04-08 GLM5 - LLM Chunking.md` (legacy zone). Not migrated. The session note references it as additional reading context, not a required navigation target.

**Applied:** `<!-- LEGACY: [[11-Prompt-Archive/2026-04-08 GLM5 - LLM Chunking]] -->` inline.

---

### Group 5 — Vault Redesign Spec dangling links (3 links)

> **Phase 5 correction:** original packet header said "2 links" but 3 detections existed — 2 frontmatter + 1 body. All 3 were fixed in Phase 4; this entry corrects the count. This was one of the 2 detections unaccounted for in the original 18-link claim.

**Original links:**
- `[[2026-05-23-session-research-captured-vault-redesign]]` (frontmatter `references:` field)
- `[[claude-memory/decisions/2026-05-23-chroma-vs-obsidian-rag]]` (frontmatter `related:` field)
- `[[2026-05-23-session-research-captured-vault-redesign]]` (body `## Connections` section, line ~798)

**File:** `claude-memory/spec/vault-redesign-spec.md`

**Decision:** Convert frontmatter wikilinks to plain text (YAML list items cannot be HTML-commented). Replace body wikilink with OPERATOR HTML comment. Annotate all with parenthetical explanations.

**Applied:**
- `references:` value → `"2026-05-23-session-research-captured-vault-redesign (C-004: file not yet exported from Claude Desktop)"`
- `related:` value → `"claude-memory/decisions/2026-05-23-chroma-vs-obsidian-rag (missing: decision doc not yet created)"`
- Body `Connections` section: `<!-- OPERATOR: C-004 open — session note not yet exported from Claude Desktop -->` comment replacing the wikilink

---

### Group 6 — Vault Redesign Spec fenced code block links (2 links)

> **Phase 5 correction:** original packet identified line 344 by content but did not individually name line 387. The second link (`[[ris-mirror/<partition>/<related_chroma_id_slug>]]`) is identified here. This was the second of the 2 detections unaccounted for in the original 18-link claim.

**Original links:**
- Line 344 of `claude-memory/spec/vault-redesign-spec.md`: `[[claude-memory/decisions/2026-05-23-chroma-vs-obsidian-rag]]` — example in `### Connections Section` fenced block
- Line 387 of `claude-memory/spec/vault-redesign-spec.md` (original numbering): `[[ris-mirror/<partition>/<related_chroma_id_slug>]]` — RIS mirror example template placeholder in a fenced block

Both are **example syntax illustrations** inside fenced ` ``` ` blocks, not real navigation targets.

**Decision:** No source file edit needed. Fixed by adding `FENCED_CODE_RE` stripping to the scanner. The links are valid examples in code blocks and should remain as-is.

**Applied:** Scanner fix only.

---

### Group 7 — Marker Structural Parser Integration (multi-line, 4 original link detections)

**Original link:** Multi-line wikilink `[[Work-Packet - Marker\nStructural Parser Integration]]` in a table cell in `claude-memory/work-packets/work-packet-marker-single-paper-validation.md`.

**Decision:** Two-part fix:
1. Collapse multi-line wikilink to single line in source file.
2. Wrap in LEGACY comment because the target (`Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md`) is in a legacy zone, not migrated.

**Applied:** `<!-- LEGACY: [[Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration]] -->` (scanner auto-expanded the stem match to the full legacy path on first run; accepted).

---

## Final Scanner State

```
File catalog: 957 keys (909 unique, 48 ambiguous keys)
Files to scan: 144

=== Results ===
  OK (already correct):   960
  Auto-fixed:             0
  Ambiguous (manual):     0
  Unresolved (manual):    0
  Files changed:          0
```

---

## Connections

- [[claude-memory/work-packets/2026-05-23-vault-redesign-execution-report]]
- [[claude-memory/work-packets/_index]]
- [[index|Vault Home]]
