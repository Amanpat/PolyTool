---
title: Fix Marker Structural Parser Frontmatter Timing Gate
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-08_fix-marker-structural-parser-frontmatter-timing-gate.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Fix: Marker Structural Parser Integration — Frontmatter/Top-Status Timing Gate

Date: 2026-05-08
Type: docs-only fix
Scope: Marker Docker IPC Warm-Worker v1 — final Codex closeout blocker

---

## Codex Blocker Addressed

Codex review `docs/dev_logs/2026-05-08_codex-verify-marker-last-timing-gate-references.md`
returned FAIL. The two previously flagged files were confirmed fixed, but
`docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser
Integration.md` still presented the old `≤10s/paper` production gate in
active-looking frontmatter and top-status language at lines 5, 31, and 34.
The old gate was rejected/superseded on 2026-05-08 (Director decision). The
current blocker is Feature 3 closeout, not the queue shipping (queue has shipped).

---

## Scoped Implementation Baseline (Before/After)

`git diff --name-status -- packages tools tests polytool config infra docker-compose.yml Dockerfile.ris artifacts`

Both before and after this docs fix:

```text
M	Dockerfile.ris
M	packages/research/ingestion/fetchers.py
M	packages/research/ingestion/marker_queue.py
M	tests/test_ris_marker_queue.py
M	tools/cli/research_marker_queue.py
```

No implementation, test, Docker, artifact, SVM, or trading files were touched
by this docs fix.

---

## Exact Lines/Sections Changed

File: `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md`

### Change 1 — Frontmatter `blocked-reason` and `updated` (lines 5–6)

**Old:**
```
blocked-reason: "Operator chose Option A 2026-05-05: async parse queue. L1 production
rollout cannot ship as synchronous default (parse_seconds=85.95s >> ≤10s/paper gate;
cold-start dominates). Blocked pending [[Work-Packet - Marker Canonical Academic Parse
Queue]] shipping. pdfplumber is legacy/debug only. Final embeddings must be Marker-only."
updated: 2026-05-05
```

**New:**
```
blocked-reason: "CURRENT BLOCKER (2026-05-08): Feature 3 closeout — Marker Docker IPC
Warm-Worker v1 pending Codex closeout verification. HISTORICAL (2026-05-05, gate rejected
2026-05-08): old ≤10s/paper timing gate was rejected as unrealistic; async parse queue has
shipped. pdfplumber is legacy/debug only. Final embeddings must be Marker-only."
updated: 2026-05-08
```

Why: frontmatter `blocked-reason` was the primary source of the active-looking gate
language. It also said "Blocked pending queue shipping" which is stale — queue shipped.

### Change 2 — DANGER callout header (line 23)

**Old:**
```
> [!DANGER] Status: BLOCKED — Awaiting Async Queue Implementation (updated 2026-05-05)
```

**New:**
```
> [!DANGER] Status: BLOCKED — Pending Feature 3 Closeout (updated 2026-05-08; queue shipped)
```

Why: callout header still said "Awaiting Async Queue Implementation" and was dated
2026-05-05. Queue has shipped; current blocker is Feature 3 closeout.

### Change 3 — Line 31: strike "fails ≤10s/paper production gate"

**Old:**
```
> - `parse_seconds=85.95s` ❌ — **fails ≤10s/paper production gate by ~8.6×**
```

**New:**
```
> - `parse_seconds=85.95s` ❌ — ~~**fails ≤10s/paper production gate by ~8.6×**~~
>   **(historical — ≤10s/paper gate rejected/superseded 2026-05-08; see revised gate below)**
```

Why: this was the top of the DANGER callout — the most visible active-looking gate
language in the file. Codex FAIL explicitly cited this line.

### Change 4 — Lines 34–35: mark `~5–10s/paper` historical

**Old:**
```
> **Root cause:** RTX 2070 Super cold-load time dominates per-paper budget. The ~5–10s/paper
> estimate in the architecture survey was from a warm-model benchmark not replicated here.
```

**New:**
```
> **Root cause (historical — superseded 2026-05-08):** RTX 2070 Super cold-load time
> dominates per-paper budget. The ~~`~5–10s/paper`
> estimate in the architecture survey was from a warm-model benchmark not replicated here~~
> — survey estimate rejected as unrealistic; measured warm-worker timings: 45.55s, 69.73s, 48.31s.
```

Why: Codex FAIL cited line 34 (`~5–10s/paper` survey estimate) as still reading as
current state in the top status block.

### Change 5 — Line 46: replace stale "resumes when queue ships"

**Old:**
```
> **This packet resumes when [[Work-Packet - Marker Canonical Academic Parse Queue]] ships.**
```

**New:**
```
> ~~**This packet resumes when [[Work-Packet - Marker Canonical Academic Parse Queue]] ships.**~~
> **Queue shipped. Current blocker: Feature 3 closeout — Marker Docker IPC Warm-Worker v1
> pending Codex closeout verification.**
```

Why: queue has shipped; this line was the third source of stale "blocked pending queue"
language adjacent to the timing gate text.

---

## Remaining Timing References — Safety Assessment

All references in the work packet with timing patterns (lines 43, 56, 96, 126) were
already safe before this fix. They are confirmed safe:

- **Line 43**: `revised gate 2026-05-08; original "≤10s/paper" per-paper target **rejected as unrealistic**` — already had explicit rejected label.
- **Line 56**: `~~Marker on this hardware is ~5-10s/paper...~~ **Historical note, superseded 2026-05-08:**` — already struck through with superseded label.
- **Line 96**: `~~On the production host...≤10 seconds.~~ **Superseded (Director 2026-05-08):**` — already struck through with superseded label.
- **Line 126**: `~~Does acceptance gate 2 ("≤10s warm")...~~ **Resolved:** acceptance gate 2 revised (Director 2026-05-08)` — already struck through with resolved label.

Other docs with timing matches confirmed safe (all have explicit rejected/superseded/historical labels):
- `docs/CURRENT_DEVELOPMENT.md:85,118` — "rejected as unrealistic" / "gate later revised 2026-05-08"
- `docs/CURRENT_STATE.md:1783` — "rejected as unrealistic (Director 2026-05-08)"
- `docs/features/ris-marker-structural-parser-scaffold.md:7,14,23,89` — "rejected as unrealistic" / "superseded 2026-05-08"
- `docs/obsidian-vault/.../Decision - Academic Pipeline Hosting.md:19,102` — "rejected as unrealistic" / "SUPERSEDED 2026-05-08"
- `docs/obsidian-vault/.../Work-Packet - Marker Canonical Academic Parse Queue.md:50,61,102,181` — "rejected as unrealistic (Director 2026-05-08)"
- `docs/obsidian-vault/.../Work-Packet - Marker Single-Paper Validation Control Surface.md:14,21,29,37,151` — adjacent gate-update at line 37 explicitly supersedes
- `docs/obsidian-vault/Claude Desktop/Current-Focus.md:4,42,53,54,57,81` — historical session entries; line 57 explicitly records later revision
- `docs/obsidian-vault/.../Work-Packet - Prefetch Label Discovery Mode.md:152` — "rejected as unrealistic"

Historical dev logs (2026-05-05_* and 2026-05-03_*) preserve measurement records — these
are frozen historical artifacts, not current-state claims, and are not treated as blockers.

---

## Commands Run + Outputs

### 1. Implementation scope baseline
```
git diff --name-status -- packages tools tests polytool config infra docker-compose.yml Dockerfile.ris artifacts
```
Output (before and after, identical):
```
M	Dockerfile.ris
M	packages/research/ingestion/fetchers.py
M	packages/research/ingestion/marker_queue.py
M	tests/test_ris_marker_queue.py
M	tools/cli/research_marker_queue.py
```

### 2. Timing gate grep
```
git grep -n "<=10 s\|<=10s\|≤10s\|10s/paper\|10 seconds\|5-10\|5–10\|~5-10" docs
```
All remaining matches in the work packet (lines 5, 31, 34, 43, 56, 96, 126) are now
explicitly marked historical/superseded/rejected. No active-looking gate language remains
in the frontmatter or top-status block.

### 3. Work packet diff stat
```
git diff --stat -- "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md"
```
Output:
```
 ...acket - Marker Structural Parser Integration.md | 22 +++++++++++-----------
 1 file changed, 11 insertions(+), 11 deletions(-)
```

---

## Timings Preserved

Actual measured timings are preserved and not hidden:
- Paper 1: 45.55s (cold start)
- Paper 2: 69.73s
- Paper 3: 48.31s

No claim that ≤10s/paper was achieved. No claim that full academic RAG pipeline is
complete. Feature 3 NOT moved to Recently Completed.

---

## Whether Codex Closeout Verification May Rerun

Yes. This fix resolves the final blocker identified in
`docs/dev_logs/2026-05-08_codex-verify-marker-last-timing-gate-references.md`.
Codex closeout verification for Feature 3 may now rerun.

---

## Codex Review Summary

Tier: docs-only timing-gate fix.
Issues found: 5 locations in Work-Packet - Marker Structural Parser Integration.md
with active-looking ≤10s/paper gate language (frontmatter blocked-reason, callout
header, line 31, lines 34–35, line 46).
Issues addressed: all 5. Implementation scope unchanged.
