---
title: Vault Log
type: log
status: active
source_zone: claude_memory
last_updated: 2026-05-29
lifecycle: reviewed
---

# Vault Log

## [2026-05-29] close | Academic RIS Developer/Operator Demo-Ready v1 — FORMALLY CLOSED
Academic RIS v1 formally closed as of 2026-05-28. Batch A/B complete: queue done=20, failed=0, sidecar_count=20. Chroma: 917 chunks / 21 papers / 0 orphans. 7 semantic probes PASS. Final Codex review: PASS. **NOT production-ready.** Caveats: weather lexical false positive (non-blocking), Docker Chroma gap (Windows host fallback), JIT cache persistence unresolved, Batch C/D deferred to post-v1 hardening (Tier-3 approval required). Next Academic RIS work: Docker `jit-cache-check` only. Vault sync updated work-packet-academic-pipeline-scaled-validation-corpus (status→complete, L2.1 stale line qualified) and work-packet-paperqa2-rag-control-flow (ChromaDB-deferred language qualified, L2.1 completion noted).
Feature doc: `docs/features/FEATURE-ris-academic-demo-ready-v1.md` | Closeout: `docs/dev_logs/2026-05-28_academic-ris-demo-ready-v1-closeout.md`

## [2026-05-28] ops | scaled_validation_queue_v2 reset — validation-ready, PARTIAL
Reset `scaled_validation_queue_v2` to clean state without full GPU parse. 5 done sidecars indexed (227 chunks, 1106 claims). 1 stuck item + 5 failed items reset to pending. 24/24 pending PDFs prefetched. Chroma embedding of 4 new papers blocked (sentence-transformers absent in GPU container; NTFS colon blocks Windows host). JIT cache persistence unproven. Tier-3 risk papers identified and tagged. 4-batch validation plan produced.
Dev log: `docs/dev_logs/2026-05-28_academic-scaled-validation-queue-reset-readiness.md`

## [2026-05-25] fix | sync-ris-mirror.py: chunk consolidation, short filenames, structured signals
Three quality fixes to `docs/scripts/sync-ris-mirror.py` after first-sync review. Fix 1: 25 per-chunk files from one academic paper collapsed to 1 consolidated file (grouped by `ks_doc_id`, chunks joined with `---` separators). Fix 2: filenames shortened to `<family>-<id[:8]>-<slug>.md`; wikilink display aliases in `_index.md` now show document titles. Fix 3: signals `pending_review` rows rendered as structured fields + scores table — raw Python dict dropped. Added `--clean` flag. Before: 176 files. After: 161 files (25 → 1 for the arXiv paper). Validators: 0 unresolved wikilinks, 1014 pass, 0 fail.
Doc: [[claude-memory/work-packets/2026-05-25-mirror-quality-fixes]]

## [2026-05-25] infra | RIS mirror sync built; Task Scheduler ready to register
Built `docs/scripts/sync-ris-mirror.py` (full sync of KnowledgeStore + Chroma → `ris-mirror/`). First run: 176 new files across 4 partitions (`external_knowledge`, `research`, `signals`, `user_data`). Wrote `docs/scripts/setup-vault-sync-schedule.ps1` for idempotent Windows Scheduled Task registration (VaultSync-RisMirror every 5 min, VaultSync-RepoDocs every 15 min) — operator must run manually. Added `.sync-logs/` to `docs/obsidian-vault/.gitignore`. Frontmatter validator: 1014 pass, 0 fail.
Doc: [[claude-memory/work-packets/2026-05-23-ris-mirror-survey]]

## [2026-05-25] fix | sync-repo-docs.py: is_diverged one-sided comparison
Fixed `is_diverged()` to use a one-sided source-field check instead of full dict equality. Previous logic flagged 60 content files as perpetually DIVERGED because `make_vault_fm()` injects `title` and `type` into the mirror even when absent from the source, causing `src_cmp != mirror_cmp` on every re-run. Fix: compare only fields present in source; mirror may carry auto-generated extras without triggering divergence. Re-run: 0 new, 0 diverged, 852 unchanged.
Doc: [[claude-memory/work-packets/2026-05-23-repo-docs-sync-survey]]

## [2026-05-25] fix | sync-repo-docs.py: full-path index links
Fixed `write_dir_index()` to emit fully-qualified wikilinks (`[[repo-docs/subfolder/stem|stem]]`) instead of bare stems, resolving 3 ambiguous-wikilink findings from the previous sync. Index files regenerated.
Doc: [[claude-memory/work-packets/2026-05-23-repo-docs-sync-survey]]

## [2026-05-25] sync | repo-docs/ full resync — 787 new, 64 updated, 1 orphaned
Ran `docs/scripts/sync-repo-docs.py` to bring repo-docs/ fully in sync with docs/: created 787 new mirror files (features/, dev_logs/, runbooks/, reference/, external_knowledge/ directories all added for the first time), updated 64 diverged files (previous sync had appended `## Connections` sections not present in source), and flagged 1 orphan (`adrs/adr-benchmark-versioning-and-crypto-unavailability.md` — source is in specs/, not adr/). Frontmatter validator: 1012 pass / 0 fail. Wikilink scanner: 0 unresolved, 3 ambiguous (see survey for details); auto-fix deferred.
Doc: [[claude-memory/work-packets/2026-05-23-repo-docs-sync-survey]]

## [2026-05-23] complete | Vault work DONE — feature development unblocked
Fixed two post-move wikilinks: `[[PolyTool/00-Index/Dashboard|...]]` → `[[legacy/PolyTool/00-Index/Dashboard|...]]` in decision-two-zone-vault-architecture.md (was ambiguous); `[[Claude Desktop/09-Decisions/Decision - Roadmap v6.0 Slim Master Restructure]]` → `[[legacy/Claude Desktop/...]]` in research-roadmap-v6-master-draft.md (was unresolved). Both routed to legacy/ paths to match the established pattern. Vault structural work is officially complete — all six contradictions resolved, all validators clean, legacy zones isolated, operating rules in place across vault root and repo root. Forward path: feature development.
Doc: [[legacy/_index]]



[2026-05-23] isolate | Legacy zones moved to legacy/ and excluded from active vault
Moved Claude Desktop/, PolyTool/, 10-Session-Notes/ into legacy/ parent folder. Added legacy/ to .obsidian/app.json userIgnoreFilters so Obsidian's search, graph, and quick-switcher ignore them. Files remain on disk and accessible via obsidian MCP tools for future per-file migration into claude-memory/. Templates/ left in place — active Templater source. Vault structural work complete — feature development unblocked.
Doc: [[legacy/_index]]

## [2026-05-23] complete | Vault structural migration declared COMPLETE
Vault structural migration officially complete. 5 cleanup phases executed, 4 independent Codex audits completed, all 6 contradictions (C-001 through C-006) RESOLVED, final validators clean (220/220 frontmatter pass, 0 unresolved wikilinks across 1184 links / 215 files). Final state: STRUCTURAL MIGRATION COMPLETE.
Doc: [[claude-memory/work-packets/2026-05-23-vault-redesign-execution-report]]

## [2026-05-23] close | C-004 — research file content placed
Placed full research packet body (~14K words across PROMPT A–E + cross-cutting notes + synthesis decisions) directly into the vault via Claude Desktop obsidian MCP tools after Claude Code's Phase 5 closeout left the placeholder pending (research file lives in Claude Desktop's artifact store, inaccessible from local repo). Frontmatter updated: status: draft → active, lifecycle: draft → reviewed. C-004 RESOLVED.
Doc: [[claude-memory/research/2026-05-23-research-llm-obsidian-vault-design]]



> [!info] Format
> Append-only chronological log. Newest entries at top.
> Format: `## [YYYY-MM-DD] <operation> | <title>` + 1-2 sentences + wikilink.

## [2026-05-23] fix | Add [[README]] to vault-root short-name examples in CLAUDE.md and AGENTS.md
Added `[[README]]` to the example link list in the Linking Rules Summary of vault-root `CLAUDE.md` and `AGENTS.md`, matching the spec table exactly. Closes the caveat noted in the Codex Phase 4 audit.
Doc: [[claude-memory/work-packets/2026-05-23-vault-redesign-execution-report]]

## [2026-05-23] phase4 | Wikilink triage complete + spec amended for vault-root short-name exception
Triaged all 18 unresolved wikilinks from the Phase 3 scanner run: 9 legacy-zone links wrapped in `<!-- LEGACY: [[...]] -->` comments across 5 files; 2 vault-redesign-spec frontmatter links converted to plain text with explanatory annotations; scanner fixed to skip HTML comments (0 unresolved on final run). Added Vault-Root Short-Name Exception rule to `vault-redesign-spec-v1.md` (and vault mirror), `CLAUDE.md`, and `AGENTS.md` explicitly permitting `[[index]]`, `[[log]]`, `[[CLAUDE]]`, `[[AGENTS]]`, `[[README]]` short links from any zone.
Doc: [[claude-memory/work-packets/2026-05-23-wikilink-triage-phase4]]

## [2026-05-23] phase3-t6 | Smart Connections plugins deleted
Removed `.obsidian/plugins/smart-connections/` and `.obsidian/plugins/smart-connections-visualizer/` from vault. `community-plugins.json` confirmed clean — neither plugin referenced. 9 intentional plugins remain.
Doc: [[claude-memory/work-packets/2026-05-23-vault-redesign-execution-report]]

## [2026-05-23] phase3-t5 | Connections sections added to 64 repo-docs Tier 1/2 files
Batch-added `## Connections` (with `[[repo-docs/_index|Repo Docs Index]]` and `[[index|Vault Home]]`) to all spec, adr, decision, and reference files in repo-docs/ that were missing it. All 64 patched; zero Tier 1/2 repo-docs files remain without Connections.
Doc: [[claude-memory/work-packets/2026-05-23-vault-redesign-execution-report]]

## [2026-05-23] phase3-t4 | repo-docs frontmatter fixes — 69 failures resolved
Fixed 65 files with `lifecycle: active` → `lifecycle: reviewed`, added `mirror_of:` to 4 `_index.md` files, removed duplicate `source_zone` from vault-redesign-spec-v1.md. Validation should now return 0 failures for repo-docs zone.
Doc: [[claude-memory/work-packets/2026-05-23-vault-redesign-execution-report]]

## [2026-05-23] phase3-t3 | C-005 architectural fix — 12 re-pointed, 30 archived
Replaced blanket `superseded_by: repo-docs/_index` with per-file resolution: 12 stale concept/reference files updated to named repo-docs paths with reciprocal callouts; 30 with no counterpart archived to `claude-memory/archive/research-stale/`. Decision log written with full per-file rationale.
Doc: [[claude-memory/work-packets/2026-05-23-c005-resolution]]

## [2026-05-23] phase3-t2 | C-002 bidirectional pointer completed
Added `supersedes: claude-memory/decisions/decision-ris-n8n-pilot-scope` to frontmatter of `repo-docs/adrs/adr-0013-ris-n8n-pilot-scoped.md`. Completes the Zone A reverse pointer that was PARTIAL after Phase 2. C-002 is now fully RESOLVED.
Doc: [[claude-memory/work-packets/2026-05-23-vault-redesign-execution-report]]

## [2026-05-23] phase3-t1 | Wikilink ambiguity: 73 → 0 ambiguous
Patched `docs/scripts/fix-wikilinks.py` with alias-skip, vault-root-exemption, inline-code-stripping, and template fix. Re-ran: 0 ambiguous, 18 unresolved (all are legitimate legacy-zone references for operator resolution). Manually aliased bare `[[AGENTS]]` links in archive/AGENT.md and bare dashboard link in decision-two-zone-vault-architecture.md.
Doc: [[claude-memory/work-packets/2026-05-23-broken-wikilinks-manual-review]]

## [2026-05-23] task6 | Plugin state audit — cleanup required work packet
Scanned `.obsidian/plugins/` and `community-plugins.json`. Found Linter and MetaEdit installed but not enabled; Smart Connections Visualizer enabled despite spec exclusion; Claudian (realclaudian) present and unreviewed. Wrote operator action checklist with confirmation status for all spec-required plugins.
Doc: [[claude-memory/work-packets/2026-05-23-plugin-cleanup-required]]

## [2026-05-23] task5 | Templater folder templates — 7 templates created and configured
Created skeleton templates for all claude-memory/ subfolders (decisions, research, session-notes, prompts, ideas, work-packets, spec) with valid frontmatter for each type. Updated `.obsidian/plugins/templater-obsidian/data.json` with 7 folder→template mappings.
Doc: [[Templates/decisions-template]]

## [2026-05-23] task4 | Validation script expanded to cover repo-docs/ (Zone A)
Added Zone A schema validation (source_zone=repo, mirror_of set, lifecycle=reviewed) to `docs/scripts/validate-vault-frontmatter.py`. Re-ran script: 215 checked, 146 pass, 69 fail. 68 failures are lifecycle: active in repo-docs/ — root cause is sync script writing wrong value; unfixable from vault side. Documented as open item.
Doc: [[claude-memory/work-packets/2026-05-23-vault-redesign-execution-report]]

## [2026-05-23] task3 | Added Connections sections to 81 Tier 1/2 docs in claude-memory/
Batch-added `## Connections` to every spec, adr, decision, research, concept, entity, mirror, and reference doc in claude-memory/ that was missing it. Zero Tier 1/2 docs remain without Connections. Emitted full list to work packet.
Doc: [[claude-memory/work-packets/2026-05-23-connections-added]]

## [2026-05-23] task2 | Contradiction resolutions C-002 through C-006 completed
Added bidirectional supersedes/superseded_by frontmatter: C-003 (v1.1 supersedes path corrected), C-005 (42 stale concept/reference files → status: superseded + superseded_by pointer), C-006 (AGENTS.md now has supersedes: pointer). C-002 remains PARTIAL (Zone A read-only). C-004 remains OPEN (operator action).
Doc: [[claude-memory/work-packets/2026-05-23-vault-redesign-execution-report]]

## [2026-05-23] task1 | 557 broken wikilinks auto-fixed; 73 queued for manual review
Wrote and ran `docs/scripts/fix-wikilinks.py`. Scanned claude-memory/ and vault root; resolved 557 unambiguous broken links across 108 files using legacy zone remaps and slug normalization. Wrote manual-review work packet for 73 ambiguous or unresolvable links.
Doc: [[claude-memory/work-packets/2026-05-23-broken-wikilinks-manual-review]]

## [2026-05-23] cleanup | Vault redesign post-session cleanup
Ran `validate-vault-frontmatter.py`; fixed 14 `lifecycle: active` → `reviewed` violations, added `adr_number`/`decision` to adr-0001, patched 16 work_packet files missing `target_agent`/`acceptance_criteria`. Final result: 143 pass, 0 fail. Updated execution report with C-006 RESOLVED and 3 new Open Items (5–7).
Doc: [[claude-memory/work-packets/2026-05-23-frontmatter-validation-report]]

## [2026-05-23] supersede | AGENT.md → AGENTS.md
AGENT.md (two-zone entry point, dated 2026-04-22) was superseded by AGENTS.md (three-zone operating rules, dated 2026-05-23). AGENT.md moved to archive with status: superseded frontmatter and warning callout. Contradiction C-006 RESOLVED.
Doc: [[claude-memory/archive/AGENT]]

## [2026-05-23] create | Vault redesign specification
Initial spec for three-zone vault structure with frontmatter schema, RIS mirror sync architecture, and migration playbook. Tier 1 document.
Doc: [[claude-memory/spec/vault-redesign-spec]]

## [2026-05-23] phase-6 | Vault redesign — validation and completion report
Spot-checked frontmatter compliance on sample files (all 7 required fields present). Verified ris-mirror/ is gitignored and structured (folders + manifest.json only). Updated index.md with all Tier 1 docs. Wrote completion report.
Doc: [[claude-memory/work-packets/2026-05-23-vault-redesign-execution-report]]

## [2026-05-23] phase-5 | Archive obsolete Dataview-powered index files
Copied 9 Dataview-dependent index files to claude-memory/archive/ with status: archived. Originals remain in place in PolyTool/ and Claude Desktop/ zones per no-deletion rule.
Doc: [[claude-memory/archive/_index]]

## [2026-05-23] phase-5 | Final wikilink remediation and tooling hardening
Resolved all 4 Codex Phase 4 audit findings: wrapped 1 aliased legacy link in LEGACY comment; applied C-004 treatment to broken wikilinks in vault-redesign-spec-v1.md and its repo-docs/ mirror; expanded fix-wikilinks.py to scan repo-docs/ zone and resolve aliased-link targets; added Vault-Root Short-Name Exception to resolver (0 unresolved, 0 ambiguous across 215 files); corrected Phase 4 triage packet arithmetic to account for all 18 original detections; added Vault Operations pointer section to repo-root claude.md and AGENTS.md.
Doc: [[claude-memory/work-packets/2026-05-23-vault-redesign-execution-report]]

## [2026-05-23] phase-4 | Migrate Tier 1/2 docs to claude-memory/
Migrated ~115 files from old Zone A/B folders into claude-memory/ subfolders with valid frontmatter. Resolved 4 contradictions: C-001 (two-zone → ADR-0001), C-002 (n8n pilot scope → repo ADR-0013), C-003 (RIS roadmap v1 → v1.1), C-004 (missing research → placeholder stub). Created decision _index, research _index, session-notes _index, prompts _index, ideas _index, work-packets _index.
Doc: [[claude-memory/decisions/adr-0001-three-zone-vault-architecture]]

## [2026-05-23] phase-3 | Copy repo docs to repo-docs/ zone
Mirrored docs/specs/, docs/adr/, docs/features/, docs/dev_logs/ into repo-docs/ with read-only zone markers. Created index files for each subfolder.
Doc: [[repo-docs/_index]]

## [2026-05-23] phase-2 | Copy vault spec to claude-memory/spec/
Placed vault-redesign-spec-v1.md at claude-memory/spec/vault-redesign-spec.md with mirror_of: pointer. This is the grounding Tier 1 document for the vault.
Doc: [[claude-memory/spec/vault-redesign-spec]]

## [2026-05-23] phase-1 | Scaffold vault structure
Created all zone folders (repo-docs/, claude-memory/, ris-mirror/) with subfolders. Created root files (index.md, log.md, CLAUDE.md, AGENTS.md, README.md, .gitignore). Created _index.md in every folder. Created ris-mirror/manifest.json stub.
Doc: [[claude-memory/work-packets/2026-05-23-vault-redesign-execution-report]]

## Connections

- [[index]]

## 2026-05-28 — Batch A Preflight

- Ran staged cached validation preflight for scaled_validation_queue_v2
- Resolved Chroma embedding gap: all 5 done papers now embedded (check-chroma-links: 9 papers, 359 chunks, 0 orphans)
- Documented indexed.jsonl duplicate disposition (19 entries, 5 unique, harmless)
- Fixed stale runbook corpus-status section (pre-reset counts replaced with post-reset state)
- Updated CURRENT_STATE.md: Chroma gap RESOLVED, indexed.jsonl duplicate note, staged plan reference
- JIT cache persistence remains UNPROVEN — requires inside-Docker before/after check
- Batch A ready: 5 small papers (2507.01990, 2510.05533, 2605.00864, 2507.08921, 2601.18815), 3600s timeout
- Dev log: docs/dev_logs/2026-05-28_academic-batch-a-preflight.md

## [2026-05-31] wallet-ingestion-v1 | WI-1 Queue Consumer + Arg-Seam Fix COMPLETE
Shipped the keystone packet: `ScanWorker` drains `scan_queue` (lease→scan→dossier→RIS ingest→watchlist `scanned`→complete), fixed the `--wallet`/`--user` arg seam, RMT latest-state collapse on load (`FINAL`), and `discovery run-worker` CLI. 142 tests pass; live end-to-end smoke PASS against running API+ClickHouse. maker/taker confirmed absent from Data API → deferred. WI-1 DoD fully ticked.
Packet: [[claude-memory/work-packets/work-packet-wi-1-queue-consumer]] — Dev log: docs/dev_logs/2026-05-31_wi-1-queue-consumer.md

## [2026-05-31] wallet-ingestion-v1 | WI-2 Dossier Supersede + Schema COMPLETE
Wallet-level supersede-on-new-run for dossier docs+claims (sections are conditional, so not (wallet,section)); lifecycle columns on `source_documents` with idempotent upgrade; `dossier_report: 4` freshness (confirmed live knob); success-gated disk retention; RIS mirror now excludes superseded. Commit `ef82b10` + hardening. Migration-gate incident: the live ALTER auto-applied via a bare `KnowledgeStore()` (landed clean, additive, backup saved); operator chose accept+harden. Hardening corrected mid-sprint: the first pytest-refusal guard was misconceived (pytest already chdir-isolates) and reverted; replaced with `_backup_before_schema_migration()` (one-time `.premigration.bak` before mutating a populated on-disk DB).
Packet: [[claude-memory/work-packets/work-packet-wi-2-dossier-supersede]] — Dev log: docs/dev_logs/2026-05-31_wi-2-dossier-supersede.md

## [2026-06-01] wallet-ingestion-v1 | WI-3 Scheduler + WI-6 MVF Fix COMPLETE (parallel batch)
WI-3: discovery/rescan scheduler reusing the RIS APScheduler `JOB_REGISTRY` pattern (discovery_loop_a / watchlist_rescan / single-tick queue_drain), tier-aware skip-if-recent with forward-compatible `resolve_tier` (no watchlist DDL — WI-4 owns that), config-driven cadences, `discovery-scheduler` compose service. WI-6: reconciled the 3 silently-degraded MVF dims to compute on real scan fields (incl. `late_entry_rate` via existing `start_date_iso`), dimension count corrected to 11, maker_taker_ratio null/documented. 249 passed across all sprint-affected suites.
Packets: [[claude-memory/work-packets/work-packet-wi-3-discovery-scheduler]], [[claude-memory/work-packets/work-packet-wi-6-mvf-input-fix]] — Dev logs: docs/dev_logs/2026-06-01_wi-3-discovery-scheduler.md, docs/dev_logs/2026-06-01_wi-6-mvf-input-fix.md
