# Dev Log: RIS Final Truth-Drift Cleanup

**Date:** 2026-04-03
**Plan:** quick-260403-n2w
**Type:** Documentation-only (truth alignment, zero code changes)

---

## Objective

Close the final RIS truth-alignment gaps so that CURRENT_STATE.md, feature docs,
and wallet-scan docs no longer contain stale deferred claims for shipped behavior.
Three plans shipped after the initial RIS v1 closure section was written
(quick-260403-lim, quick-260403-lir, quick-260403-lix) creating truth drift.

---

## Stale Claims Corrected

### CURRENT_STATE.md

| Line area | Stale claim | Correction |
|-----------|-------------|------------|
| v2 Deferred list | "Auto-trigger dossier extraction after wallet-scan (hook not wired)" | REMOVED — shipped in quick-260403-lim via --extract-dossier |
| v2 Deferred list | "MCP rag-query -> KnowledgeStore routing" | REMOVED — shipped in quick-260403-lir with ks_active flag |
| v1 Complete list | Missing wallet-scan hook + bridge CLI + MCP routing entries | ADDED both entries |
| Test count | 3660 | Updated to 3689 |
| Missing section | No entry for quick-260403-lir | ADDED full section before RIS v1 COMPLETE |
| RIS_07 deferred bullets | Auto-trigger "remains v2 deferred" | Updated to "also shipped (quick-260403-lim)" |
| RIS_07 deferred bullets | "MCP auto-routing for rag-query" bare deferred | Updated to "v1 shipped" with ks_active detail |
| R5 Deferred inline note | Inline "Wired via --extract-dossier flag" note | Cleaned to standard "Shipped via --extract-dossier flag" format |
| Still deferred (lim section) | "RAG query integration (Chroma/FTS5 not yet connected to KnowledgeStore)" | Clarified: KS hybrid routing shipped; direct Chroma embed still pending |

### FEATURE-ris-dev-agent-integration-v1.md

| Line area | Stale claim | Correction |
|-----------|-------------|------------|
| v2 Deferred, dossier bullet | Fully deferred: "Requires LLM extraction prompt and integration with wallet-scan / alpha-distill" | Updated: v1 shipped (jy8 + lim); only LLM extraction and alpha-distill integration remain v2 |
| v2 Deferred, auto-discovery bullet | "Requires Section 1 as prerequisite" (implied Section 1 still deferred) | Updated: Section 1 prerequisite now shipped; full auto-loop remains v2 |
| v2 Deferred, SimTrader bridge bullet | Fully deferred | Updated: bridge CLI shipped in quick-260403-lir; auto-loop v2 |
| v2 Deferred, MCP bullet | "not yet wired to KS" | Updated: v1 shipped via quick-260403-lir with ks_active flag |

### FEATURE-ris-v1-data-foundation.md

| Line area | Stale claim | Correction |
|-----------|-------------|------------|
| Status line (line 4) | "Complete (data-plane only; not yet wired into Chroma query path)" | Updated: "Complete (data-plane + query spine wired via quick-260402-ivb, MCP routing via quick-260403-lir)" |
| Deliberate Simplifications | "No Chroma integration yet. ...That wiring is deferred to a future plan." | Updated: wiring shipped in quick-260402-ivb (query spine) and quick-260403-lir (MCP KS routing) |
| Phase R5 Deferred | "Auto-trigger not yet wired. Run manually after each scan session." | Updated: "Shipped via --extract-dossier flag on wallet-scan (quick-260403-lim)" |

### wallet-scan-v0.md

| Line area | Stale claim | Correction |
|-----------|-------------|------------|
| Dossier Extraction section | `--base-dir` flag name in example | Changed to `--dossier-base` (matches actual CLI output from `research-dossier-extract --help`) |

---

## Commands Run (Smoke Tests)

### 1. `python -m polytool wallet-scan --help`
```
usage: __main__.py [-h] --input INPUT [--profile {lite,full}] [--out OUT]
                   [--run-id RUN_ID] [--max-entries MAX_ENTRIES]
                   [--continue-on-error | --no-continue-on-error]
                   [--extract-dossier]
                   [--extract-dossier-db EXTRACT_DOSSIER_DB]
```
Confirms: `--extract-dossier` and `--extract-dossier-db` both present. PASS.

### 2. `python -m polytool research-dossier-extract --help`
```
usage: research-dossier-extract [-h] (--dossier-dir DIR | --batch)
                                [--dossier-base DIR] [--db-path PATH]
                                [--extract-claims] [--dry-run]
```
Confirms: flag is `--dossier-base` (not `--base-dir`). PASS.

### 3. `python -m polytool research-register-hypothesis --help`
```
usage: research-bridge register-hypothesis [-h]
                                           [--candidate-json PATH | --candidate-json-string STR]
                                           [--registry-path PATH]
```
Confirms: command exists and loads. PASS.

### 4. `python -m polytool research-record-outcome --help`
```
usage: research-bridge record-outcome [-h] --hypothesis-id ID
                                      [--claim-ids ID1,ID2,...]
                                      [--claim-id ID] --outcome
                                      {confirmed,contradicted,inconclusive}
                                      --reason REASON [--knowledge-store PATH]
```
Confirms: command exists and loads. PASS.

### 5. `python -m polytool --help`
Top-level CLI loads. All RIS commands listed including `research-register-hypothesis`
and `research-record-outcome`. PASS.

---

## Final RIS v1 State

### Shipped (v1 complete)

All RIS subsystems are shipped. The full v1 surface includes:
- R0: Knowledge store foundation (SQLite + Chroma, BGE-M3 embeddings)
- R1: Academic ingestion (ArXiv, BookAdapter, manual URL, --extract-claims)
- R2: Social ingestion (Reddit, YouTube, clean_transcript)
- R3: Synthesis engine (deterministic ReportSynthesizer, EnhancedPrecheck, ResearchBrief)
- R4: Infrastructure (scheduler 8-job, health checks 6-condition, stats/metrics export, report catalog save/list/search/digest)
- R5: Dossier pipeline + wallet-scan --extract-dossier auto-trigger hook
- Dev agent integration (CLAUDE.md RIS section, operator recipes A-E)
- SimTrader bridge (research-register-hypothesis, research-record-outcome CLIs)
- Bridge CLI + MCP KnowledgeStore hybrid routing (ks_active flag in response)

### Genuinely v2 Deferred

- Auto-discovery -> knowledge loop (requires candidate scanner integration)
- SimTrader auto-promotion loop (bridge shipped; auto-loop not wired)
- LLM-based synthesis (DeepSeek V3 prose generation)
- n8n migration from APScheduler
- ClickHouse ingestion_log table + Grafana panels
- ChatGPT architect / Google Drive connector
- Weekly digest automation
- SSRN ingestion, Twitter/X ingestion
- LLM-assisted dossier memo extraction (authority conflict)

---

## Codex Review

**Tier:** Docs-only changes. Skip tier. No adversarial review required.
