---
title: RIS Mirror Sync Survey 2026-05-23
type: work_packet
status: active
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: reviewed
target_agent: claude-code
acceptance_criteria:
  - sync-ris-mirror.py deployed and running successfully
  - ris-mirror/ populated with current KS and Chroma data across all four partitions
  - Windows Scheduled Tasks registered (VaultSync-RisMirror every 5 min, VaultSync-RepoDocs every 15 min)
  - manifest.json updated with content hashes and last_sync timestamp
  - validate-vault-frontmatter.py passes (ris-mirror/ already in SKIP_DIRS)
---

# RIS Mirror Sync Survey

**Date:** 2026-05-23  
**Purpose:** Pre-build survey of Chroma and KnowledgeStore setup to inform sync-ris-mirror.py design.

---

## Chroma Setup

**Client type:** `chromadb.PersistentClient` — local disk-backed, no host/port/auth.  
**Persist directory:** `kb/rag/index` (relative to repo root)  
**Wrapper class:** None — all call sites use raw `chromadb.PersistentClient` directly.  
**Reference:** `packages/polymarket/rag/index.py`, `packages/polymarket/rag/query.py`

### Collections

| Collection | Count | Role |
|---|---|---|
| `polytool_rag` | 24,502 chunks | Repo-doc and KB embeddings; used for semantic search |
| `academic_papers` | 25 docs | Ingested academic PDFs from RIS harvester pipeline |

**Key finding:** The task spec assumed 4 named Chroma partitions (`user_data`, `external_knowledge`, `research`, `signals`). Actual setup has 2 flat collections. The partition names are vault-level logical groupings — not Chroma collection names.

### Metadata schema (polytool_rag)

Fields observed on `polytool_rag` chunks: `file_path`, `doc_id`, `chunk_index`, `is_private`, `doc_type`, `created_at`, `user_slug`.

### Metadata schema (academic_papers)

Fields observed on `academic_papers` docs: `title`, `url`/`source_url`, `file_path` (where available). Schema varies per harvester.

---

## KnowledgeStore Setup

**Type:** SQLite, accessed via `packages/polymarket/rag/knowledge_store.py`  
**Path:** `kb/rag/knowledge/knowledge.sqlite3`  
**Default constant:** `KnowledgeStore.DEFAULT_KNOWLEDGE_DB_PATH` = `Path("kb") / "rag" / "knowledge" / "knowledge.sqlite3"`

### Table row counts (as of survey)

| Table | Rows | Notes |
|---|---|---|
| `source_documents` | 131 | Ingested papers and URLs |
| `derived_claims` | 1,598 | Extracted claims linked to source_documents |
| `pending_review` | 1 | Items awaiting operator review |
| `claim_evidence` | (linked) | Evidence for derived_claims |
| `claim_relations` | (linked) | Cross-claim relationships |

---

## Partition Mapping Design

Since Chroma has no named partitions, the four vault partition names map to actual data sources as follows:

| Vault partition | Data source |
|---|---|
| `external_knowledge` | KS `source_documents` (131 docs) + Chroma `academic_papers` (25 docs) |
| `research` | KS `derived_claims` grouped by `source_document_id` (~131 files, one per source) |
| `signals` | KS `pending_review` (1 item currently) |
| `user_data` | Chroma `polytool_rag` summary only — no per-chunk files (24,502 chunks is impractical to enumerate) |

**user_data rationale:** `polytool_rag` chunks are derived from repo documents already present in `repo-docs/`. Creating 24,502 individual vault files would be unusable. Instead, `user_data/` gets a single `polytool-rag-summary.md` with collection stats and sample paths, plus a CLI usage note.

---

## Task 3 Status

`ris-mirror` is **already present** in `SKIP_DIRS` in `validate-vault-frontmatter.py` (line 41). No change needed.

---

## Open Questions / Risks

- **`academic_papers` Chroma schema**: Not all fields are consistent across docs. Sync script must be defensive (handle missing metadata keys gracefully).
- **`pending_review` table schema**: Varies from the assumed schema. Script uses `SELECT *` fallback.
- **`body_text` availability**: Some `source_documents` may have empty `body_text` if the Marker pipeline didn't complete. Script truncates at 2,000 chars and shows placeholder for empty bodies.
- **Content drift**: KS `derived_claims` will grow over time. The 5-minute sync interval ensures the `research/` partition stays current.
- **Log rotation**: Status log at `.sync-logs/ris-mirror-status.json` keeps last 50 run entries.

---

## Connections

- [[claude-memory/work-packets/2026-05-23-vault-redesign-execution-report]]
- [[claude-memory/spec/vault-redesign-spec]]
