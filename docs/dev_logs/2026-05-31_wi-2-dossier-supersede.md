# 2026-05-31 — WI-2: Dossier Supersede + Schema

**Sprint:** Wallet-Ingestion v1 (work packet WI-2)
**Status:** COMPLETE. Code committed (`ef82b10`) + hardening. Live DB migration applied (see Addendum — it auto-applied before the human go; landed clean; operator chose "accept + harden").

## Objective

On a material rescan of a wallet, retire the prior dossier's findings instead of
accumulating them. Add lifecycle fields to `source_documents`, supersede the prior
wallet dossier docs + their claims on a successful new run, register `dossier_report`
in the freshness config, keep the prior interpretive report on disk as
`previous-results.md`, and compress (not delete) the prior raw scan.

## Design implemented (per operator-settled decisions)

- **Wallet-level supersede, gated on new-run success** (NOT wallet+section). When a
  new dossier run's docs for a wallet are successfully ingested, ALL prior active
  `dossier_report` source docs for that wallet (excluding the just-ingested run) are
  superseded and their claims cascade-superseded. Robust to missing/extra sections
  (the reason wallet+section was rejected: conditional candidates/memo sections would
  orphan prior docs).
- **Stable `document_type` persisted** from the existing constants — never parsed from
  the human title.
- **Wallet normalization = lowercase**, applied on BOTH write (persisted into
  `metadata_json.wallet`) and the supersede-match query (`lower(json_extract(...))`).
- **Single transaction, new-first, supersede-after-success**: new run's docs+claims are
  inserted FIRST, THEN the prior active set is superseded, all inside one
  `deferred_transaction()` (one BEGIN/COMMIT). A mid-ingest failure rolls back the whole
  block → wallet keeps its OLD active set intact (never zero, never two active sets).
- **Cascade by FK**: `derived_claims.source_document_id REFERENCES source_documents(id)`.

## Files modified / created

- `packages/polymarket/rag/knowledge_store.py`
  - `source_documents` CREATE TABLE gains `lifecycle TEXT NOT NULL DEFAULT 'active'`,
    `superseded_by TEXT`, `superseded_at TEXT`.
  - `_upgrade_source_document_lifecycle()` — idempotent `PRAGMA table_info` → `ALTER ADD COLUMN`
    for missing columns only; called from `_ensure_schema()`. No-op on fresh DBs and on an
    already-migrated DB.
  - `_defer_commit_depth` + `_commit()` + `deferred_transaction()` context manager —
    suppresses intra-method commits so a caller can wrap many writes atomically. Switched
    `add_source_document`, `add_claim`, `add_evidence`, `add_relation` from `self._conn.commit()`
    to `self._commit()`.
  - `list_source_documents(include_superseded=False, include_archived=False)` — lifecycle-
    excluding retrieval mirroring `query_claims`'s opt-in flags. `get_source_document(id)` left
    lifecycle-agnostic (by-id provenance lookup).
  - `supersede_dossier_run(wallet, keep_doc_ids, ...)` — wallet-level supersede sweep + claim
    cascade; pure mutation, enrolls in the caller's transaction.
- `packages/research/integration/dossier_extractor.py`
  - `_normalize_wallet()` helper.
  - `ingest_dossier_findings()` rewritten: group findings by normalized wallet → one
    `deferred_transaction()` per wallet → ingest new docs (identical-content skip preserved) →
    patch `metadata_json` with normalized `wallet`/`document_type`/`run_id`/`dossier_path`/`user_slug`
    (PlainTextExtractor otherwise stores only `content_hash`) → `extract_and_link` when requested →
    `supersede_dossier_run(keep=new_doc_ids)` → commit. Exactly ONE supersede sweep per wallet per run.
  - `_retain_prior_runs()` — success-gated retention: copies prior `memo.md` → new run
    `previous-results.md`; gzips each prior raw run dir to `<dir>.tar.gz` then removes the
    original dir (archive retains it; no hard delete). Prior run dirs located from the superseded
    docs' own `metadata_json.dossier_path` (no "most recent" guess needed). Best-effort, non-fatal.
- `config/freshness_decay.json` — added `"dossier_report": 4`.
- `docs/scripts/sync-ris-mirror.py` — `_ks_rows()` now excludes
  `lifecycle IN ('superseded','archived')` for `source_documents` and `derived_claims`
  (defensive `PRAGMA table_info` column check). Mirror does NOT route through `query_claims`,
  so the filter was added at its own read path.
- `tests/test_ris_dossier_supersede.py` — new (10 tests).

## Retention seam choice

Retention fires inside `ingest_dossier_findings._retain_prior_runs`, **after the wallet's
transaction commits AND `supersede_dossier_run` returns a non-empty `superseded_doc_ids`**.
This ties retention to the exact same success gate as supersede (one place that knows both the
new run dir and the prior runs). The post-scan worker seam (`wallet_scan._make_dossier_extractor`)
was rejected because it does not know which prior docs were superseded; locating the prior run dir
there would require a separate "most recent prior run" lookup. Reading `dossier_path` straight off
the retired source-doc rows is more reliable.

## Mirror-consistency finding

The RIS Obsidian mirror (`docs/scripts/sync-ris-mirror.py`) syncs dossier rows through the
generic `source_documents`/`derived_claims` path via `_ks_rows()` (raw `SELECT *`). It does NOT
call `KnowledgeStore.query_claims`, so it would NOT have inherited the lifecycle exclusion.
Fix: `_ks_rows` now filters `lifecycle NOT IN ('superseded','archived')` for those two tables
(guarded by a `PRAGMA table_info` check so it is safe against pre-migration DBs). Verified by
`TestMirrorExclusion::test_mirror_ks_rows_excludes_superseded`.

## Freshness-consumption finding (LIVE knob, not dead)

`query_claims` calls `compute_freshness_modifier(source_family=sd.source_family, published_at=sd.published_at)`.
Dossier source docs are stored with `source_family='dossier_report'` and `published_at` set to the
dossier `generated_at[:10]` date. So `query_claims` DOES read and apply the new `dossier_report: 4`
half-life to dossier claims. The `4` is therefore a **live knob**, not cosmetic. Rationale for 4 <
sibling `wallet_analysis: 6`: supersede already keeps rescanned wallets current, so decay only
governs stale un-rescanned dossiers, which should lose weight faster.

## Transaction shape (confirmed)

`deferred_transaction()` is reference-counted; only the outermost exit commits or rolls back.
Inside `ingest_dossier_findings`, per wallet: BEGIN (implicit via deferred depth) → insert new
docs + claims (new-first) → `supersede_dossier_run` (excludes `new_doc_ids`) → COMMIT on clean
exit; ROLLBACK on any exception (then all that wallet's findings reported rejected). Confirmed by
`test_transaction_atomicity_rollback`.

## Wallet normalization (confirmed)

Lowercase, applied at write (`meta["wallet"] = _normalize_wallet(...)` before adapt, persisted into
`metadata_json`) and at match (`lower(COALESCE(json_extract(metadata_json,'$.wallet'),''))`).
Confirmed by `test_wallet_normalization_match`.

## Tests

`python -m pytest tests/test_ris_dossier_supersede.py tests/test_ris_dossier_extractor.py tests/test_knowledge_store.py tests/test_wallet_scan_dossier_integration.py`
→ **94 passed, 0 failed**.

Broader RIS/ingestion regression
(`-k "knowledge or dossier or ingest or freshness or claim or pipeline or rag or pending_review or research"`)
→ **971 passed, 3 failed**. The 3 failures are in `test_ris_phase4_source_acquisition.py`
(academic_marker_gate rejections) and are **PRE-EXISTING** — they fail identically on the clean
tree at `c249ff5` (verified via `git stash`), and are unrelated to WI-2 (academic adapter / Marker
gate, not dossier/lifecycle).

`python -m polytool --help` → loads OK.

## Live migration — EXACT statements the orchestrator will run

Applied automatically by `KnowledgeStore.__init__` → `_ensure_schema` →
`_upgrade_source_document_lifecycle` on first open of the live DB after this code lands. The
orchestrator should run these (or simply open a `KnowledgeStore` once with writers quiesced):

```sql
ALTER TABLE source_documents ADD COLUMN lifecycle TEXT NOT NULL DEFAULT 'active';
ALTER TABLE source_documents ADD COLUMN superseded_by TEXT;
ALTER TABLE source_documents ADD COLUMN superseded_at TEXT;
```

All existing ~151 rows backfill to `lifecycle='active'` via the DEFAULT. Idempotent: each ALTER
is skipped if the column already exists (`PRAGMA table_info`).

## Live-migration risks / open items

- WAL mode is on; the ALTERs are fast metadata-only operations but must run with writers quiesced
  (no concurrent dossier ingest) to avoid lock contention.
- This packet did NOT apply the ALTER to `kb/rag/knowledge/knowledge.sqlite3`. All tests used
  `:memory:` or temp-file DBs.
- Retention archives prior run dirs as `<dir>.tar.gz`. If a future loader walks
  `artifacts/dossiers/.../` for `dossier.json`, the gzipped dirs are no longer discovered (by
  design — the active run is the current one). No code in this packet reads archived dirs.

## Codex review

`knowledge_store.py` and `dossier_extractor.py` are research-side, NOT in the mandatory
adversarial-review denylist → **Recommended tier**, not run in this session (not blocking).

## Addendum — Migration-Gate Incident + Hardening (orchestrator, 2026-05-31)

The migration was gated behind an explicit human second-go (apply with writers quiesced after a
pre-backup). It instead **auto-applied to the live `kb/rag/knowledge/knowledge.sqlite3` before that
go**: `KnowledgeStore.__init__` defaults `db_path` to the live file and `_ensure_schema` runs the
lifecycle upgrade on every open, so a bare `KnowledgeStore()` opened during an ad-hoc run fired the
three ALTERs above.

**Impact (read-only verified):** purely additive — all three columns present; 151 source_documents +
4893 derived_claims, **100% `lifecycle='active'`, 0 superseded**; counts unchanged from post-WI-1-smoke;
no data loss; DB gitignored. Post-hoc backup: `kb/rag/knowledge/knowledge.sqlite3.pre-wi2.2026-05-31.bak`
(sha `e15c8397…`).

**Operator decision:** "Accept, but harden first."

**Hardening — first attempt (REVERTED, commit `e1709aa` → reverted in `f8bae6e`):** added a guard that
raised if the live `DEFAULT_KNOWLEDGE_DB_PATH` was opened under `PYTEST_CURRENT_TEST`. **This was wrong:**
(1) `tests/conftest.py :: pytest_configure` already `chdir`s the whole session into an isolated temp
workspace, and `DEFAULT_KNOWLEDGE_DB_PATH` is a *relative* path — so under pytest it resolves into the
workspace, never the real repo DB. The guard fired on the already-safe workspace path. (2) It raised on
~12 RIS CLI tests (marker-queue `index-done`, monitoring run-log, acquire) that legitimately open the
default-path store (safe via the chdir). It also did NOT address the true incident vector — the live DB
was migrated by an ad-hoc `python -m polytool` run in the *real* CWD (not pytest), which the guard cannot
catch.

**Hardening — corrected (commit `f8bae6e`):** `_backup_before_schema_migration()` takes a one-time WAL-safe
backup (`<db>.premigration.bak`) before the lifecycle ALTER mutates a **populated on-disk** DB — the actual
ad-hoc-run vector. No-op for `:memory:` and fresh/empty DBs; never clobbers an existing backup. 4 backup
tests replace the 4 reverted guard tests. The 11 RIS tests pass again; only 3 genuinely pre-existing
`test_ris_phase4_source_acquisition` academic failures remain (unrelated). Auto-upgrade-on-open stays the
production behavior (correct); the safeguard just guarantees a recoverable copy first.

## Connections

- Work packet: `docs/obsidian-vault/claude-memory/work-packets/work-packet-wi-2-dossier-supersede.md`
- Audit: `docs/obsidian-vault/claude-memory/session-notes/2026-05-29-wallet-ingestion-audit-results.md`
