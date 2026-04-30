# 2026-04-29 — Scientific RAG Vault Reconciliation

## Objective

Reconcile vault work-packet docs and target-architecture doc with actual repo state after Layer 0 (PDF fix) and Layer 1 (Marker scaffold) shipped on 2026-04-27. Ensure all status fields, metadata labels, and cross-references are truthful. Remove stale `marker_llm_boost` references. Create the missing evaluation benchmark stub.

---

## Mismatches Found

| Location | Mismatch | Severity |
|---|---|---|
| `Work-Packet - Academic Pipeline PDF Download Fix.md` | `status: ready` — should be `shipped` (shipped 2026-04-27) | High |
| `Work-Packet - Marker Structural Parser Integration.md` | `status: stub` — scaffold fully implemented across Prompts A–D; `marker_llm_boost` in scope guards | High |
| `11-Scientific-RAG-Target-Architecture.md` | Layer 0 "specced, ready to ship" — should be "shipped"; Layer 1 "future packet" — should be "scaffold implemented, production deferred"; `marker_llm_boost` in Layer 1 body; cross-refs said "ready" and "stub" | High |
| `Decision - Scientific RAG Architecture Adoption.md` | Cross-ref: "immediate fix (layer 1)" — should be "layer 0"; "eval gate scoring (still authoritative for layer 1's evaluator)" — ambiguous; missing evaluation benchmark cross-ref | Medium |
| `packages/research/ingestion/fetchers.py` | Docstring listed `"marker_llm_boost"` as a valid `body_source` value — that value was removed in Prompt C and never exists in the codebase | Medium |
| `12-Ideas/` directory | `Work-Packet - Scientific RAG Evaluation Benchmark.md` missing — decision doc says five stubs must exist; only four were present | Medium |

---

## Files Changed

| File | Change |
|---|---|
| `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Academic Pipeline PDF Download Fix.md` | `status: ready` → `status: shipped`, added `shipped-date: 2026-04-27`, replaced scope callout with shipped evidence block (dev logs, Docker smoke, test count) |
| `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md` | `status: stub` → `status: implemented-experimental-scaffold`; replaced stub callout with warning noting default=pdfplumber, CPU timeout, deferred rollout; removed `marker_llm_boost`; added canonical feature doc pointer; added deferred items table |
| `docs/obsidian-vault/Claude Desktop/08-Research/11-Scientific-RAG-Target-Architecture.md` | Intro updated to reflect shipped/scaffold state; Layer 0 status "specced, ready to ship" → "shipped 2026-04-27"; Layer 1 "future packet" → "scaffold implemented, production deferred"; removed `marker_llm_boost`, added accurate `marker_llm_requested`/`marker_llm_applied` language; build-order table updated; cross-refs updated; evaluation benchmark cross-ref added |
| `docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Scientific RAG Architecture Adoption.md` | Impact section updated to note evaluation benchmark stub was missing and created in this pass; cross-ref "immediate fix (layer 1)" → "(layer 0 — shipped 2026-04-27)"; "layer 1's evaluator" → "the evaluation gate"; added Layer 1 and evaluation benchmark cross-refs |
| `packages/research/ingestion/fetchers.py` | `_fetch_pdf_body` docstring: removed `"marker_llm_boost" — Marker with LLM flag enabled`; replaced with `"marker" — Marker success (opt-in: RIS_PDF_PARSER=auto\|marker)` and corrected `pdfplumber_fallback` description |
| `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Scientific RAG Evaluation Benchmark.md` | **Created** — stub packet; purpose: measure corpus quality and retrieval readiness before Layer 2; no implementation; gates Layer 2 commitment |
| `docs/INDEX.md` | Added reconciliation dev log row at top of Recent Dev Logs table |
| `docs/dev_logs/2026-04-29_scientific-rag-vault-reconciliation.md` | This file |

---

## Status Changes Made

| Artifact | Before | After |
|---|---|---|
| Layer 0 work packet status | `ready` | `shipped` |
| Layer 1 work packet status | `stub` | `implemented-experimental-scaffold` |
| Architecture Layer 0 description | "specced, ready to ship" | "shipped 2026-04-27" |
| Architecture Layer 1 description | "future packet" | "scaffold implemented, production deferred" |
| Architecture build-order table | "ships first, immediate fix" | "SHIPPED 2026-04-27" |
| Decision doc Layer 0 cross-ref label | "immediate fix (layer 1)" | "immediate fix (layer 0 — shipped)" |
| Decision doc eval gate cross-ref | "layer 1's evaluator" | "the evaluation gate" |

---

## Evaluation Benchmark Packet

**Decision:** Created the stub (`Work-Packet - Scientific RAG Evaluation Benchmark.md`).

Rationale: The decision doc explicitly stated five stubs must exist. The evaluation benchmark was the only missing one. The stub documents purpose (measure retrieval before Layer 2 commitment), scope guards, and open questions. No implementation yet. The existing 31-query P@5 baseline from RIS Phase 2A is noted as a starting point.

---

## Commands Run

```bash
# Verify marker_llm_boost no longer appears outside historical dev logs
rtk grep "marker_llm_boost" --type py
rtk grep "marker_llm_boost" --type md
```

Expected: no matches in `.py` files; matches only in historical dev logs (`2026-04-27_ris-marker-timeout-llm-truthfulness.md` and similar) which preserve history intentionally.

```bash
rtk git diff --check
rtk git status --short
```

---

## Remaining Docs Debt

1. **Re-ingest cleanup not tracked**: Existing ChromaDB academic data is abstract-only (pre-Layer 0). A follow-up task should re-ingest known arXiv URLs through the fixed pipeline. No work packet exists for this yet.
2. **Marker production rollout gate**: No work packet captures the GPU-host availability check and throughput validation needed before Marker becomes the default parser. Currently noted as deferred in the scaffold feature doc — sufficient for now.
3. **Layer 1 vault packet is now a hybrid** (stub-turned-scaffold-implemented). It documents what was built but does not have the full acceptance-criteria structure of an active packet. This is acceptable until the production rollout work packet is created.
4. **`docs/obsidian-vault/` is excluded from public docs goals** (per ADR-0014) — these vault reconciliation changes do not affect public doc count targets.
