---
title: RIS Mirror Quality Fixes 2026-05-25
type: work_packet
status: active
source_zone: claude_memory
last_updated: 2026-05-25
lifecycle: reviewed
target_agent: claude-code
acceptance_criteria:
  - Chunk consolidation: all chunks from one ks_doc_id grouped into a single vault file
  - Filenames follow <family>-<id[:8]>-<slug>.md scheme across all partitions
  - Wikilink display aliases in _index.md use document titles not filenames
  - Signals pending_review renders structured fields + scores table, no raw dict
  - --clean flag wipes stale .md files before rebuild
  - validate-vault-frontmatter.py passes (0 fail)
  - fix-wikilinks.py --dry-run: 0 unresolved, 0 ambiguous
---

# RIS Mirror Quality Fixes 2026-05-25

**Date:** 2026-05-25
**Script modified:** `docs/scripts/sync-ris-mirror.py`
**Trigger:** Review of initial sync output (2026-05-25) revealed three structural problems.

---

## Problems Fixed

### Fix 1 — Chunk Consolidation (DONE)

**Problem:** The `academic_papers` Chroma collection stores one paper as 25 individual chunks, each with its own Chroma ID. The sync script emitted one vault file per chunk → 25 files for one paper.

**Root cause:** No grouping logic; every `get()` result became its own file.

**Fix:** Group chunks by `ks_doc_id` metadata field. Sort by `chunk_index` ascending. Concatenate bodies with `\n\n---\n\n`. Write ONE file per `ks_doc_id`. Frontmatter carries `chunk_count:` and `ks_doc_id:`.

**Result:** 25 files → 1 file for the arXiv microstructure paper.

---

### Fix 2 — Short Filenames + Title Aliases (DONE)

**Problem:** Filenames used full 64-char hash IDs, making them unreadable in the file tree and breaking tab display in Obsidian.

**Fix:** Filenames now follow `<family>-<id[:8]>-<title-slug>.md`:
- KS source docs: `src-0f5a6f6c-simtrader-known-limitations-verified.md`
- KS-backed acad chunks: `acad-a1921b9a-the-anatomy-of-a-decentralized-prediction-market-microstruct.md`
- Research claims: `claims-a1921b9a-the-anatomy-of-a-decentralized-prediction-market.md`
- Signals: `pending-review-manual-66196347.md`

Wikilinks in `_index.md` now use the `|Title` alias syntax so Obsidian graph and link text shows the real document title:
```
[[ris-mirror/external_knowledge/acad-a1921b9a-the-anatomy-of-a-decentralized-prediction-market-microstruct|The Anatomy of a Decentralized Prediction Market: Microstructure Evidence from the Polymarket Order Book]]
```

---

### Fix 3 — Structured Signals Rendering (DONE)

**Problem:** `pending_review` table has no `content` column. The previous sync code fell back to `str(dict(row))`, dumping a raw Python dict literal as the body.

**Fix:** Added `_parse_pending_review_content()` helper that tries `ast.literal_eval` then `json.loads` on the row. Also parses the nested `gate_snapshot_json` string to extract scores and body preview. Renders:
- Title, Review type, Gate, Weighted score (+ simple sum)
- Source URL, Created timestamp, Status
- Body Preview section (from `source_document.body_preview`)
- Scores table: Relevance / Credibility / Novelty / Actionability

---

### --clean Flag (DONE)

Wipes all `.md` files in each partition dir (except `_index.md`) before rebuild. Also purges stale keys from `manifest.json` for that partition. Prevents ghost files from old naming schemes persisting alongside new ones.

Usage: `python docs/scripts/sync-ris-mirror.py --clean`

---

## Before/After

| Metric | Before | After |
|---|---|---|
| Total ris-mirror .md files | 176 | 161 |
| external_knowledge files | ~155 | 137 |
| acad chunk files → consolidated | 25 | 5 (5 distinct papers) |
| Filename style | `chroma-acad-<64char>-<slug>.md` | `acad-<8char>-<slug>.md` |
| Wikilink display | filename stem | document title |
| Signals body | raw Python dict | structured fields + scores table |

---

## Validation Results

```
python docs/scripts/fix-wikilinks.py --dry-run
  OK (already correct):   1816
  Auto-fixed:             22
  Ambiguous (manual):     0
  Unresolved (manual):    0

python docs/scripts/validate-vault-frontmatter.py
  Validation: 1014 checked, 1014 pass, 0 fail, 302 skipped (legacy)
```

---

## Bases View Decision

Obsidian Bases (released Aug 2025) — syntax not unambiguous enough for safe inline query blocks without risk of vault parse errors. Skipped. The `_index.md` files with title-aliased wikilinks provide adequate navigation. Revisit when Bases syntax is well-documented.

---

## Connections

- [[claude-memory/work-packets/2026-05-23-ris-mirror-survey]]
- [[log]]
