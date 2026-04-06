---
phase: quick-260405-jyv
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - Dockerfile
  - docs/CURRENT_STATE.md
  - docs/dev_logs/2026-04-05_root_image_final_slimming.md
autonomous: true
requirements: []
must_haves:
  truths:
    - "Root Dockerfile installs only extras needed by ris-scheduler and polytool CLI runtime roles"
    - "dev, rag, and studio extras are NOT installed in the root image"
    - "CURRENT_STATE.md no longer claims Dockerfile.bot is orphaned"
    - "polytool --help still works (no import breakage)"
    - "docker compose config still validates"
  artifacts:
    - path: "Dockerfile"
      provides: "Narrowed extras for root image runtime"
      contains: "pip install"
    - path: "docs/CURRENT_STATE.md"
      provides: "Corrected Docker infrastructure documentation"
    - path: "docs/dev_logs/2026-04-05_root_image_final_slimming.md"
      provides: "Dev log documenting the change and rationale"
  key_links:
    - from: "Dockerfile"
      to: "docker-compose.yml"
      via: "polytool and ris-scheduler services build from root Dockerfile"
      pattern: "dockerfile: Dockerfile"
---

<objective>
Slim the root Docker image by narrowing extras from `.[all,ris]` to only what
ris-scheduler and polytool CLI actually need at runtime. Fix stale Docker
documentation in CURRENT_STATE.md.

Purpose: The root image currently installs ~500MB+ of unnecessary packages
(sentence-transformers, chromadb, fastapi, uvicorn, pytest) that no root-image
consumer uses. Prior work (quick-260405-jle) already split pair-bot to its own
lean image; this pass narrows the root image for its actual roles.

Output: Updated Dockerfile, corrected CURRENT_STATE.md, dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@Dockerfile
@Dockerfile.bot
@docker-compose.yml
@pyproject.toml
@docs/CURRENT_STATE.md
@docs/dev_logs/2026-04-05_docker_image_slimming.md

Key findings from audit:

Root image consumers (docker-compose.yml):
1. `polytool` service (profile: cli) — general-purpose CLI container
2. `ris-scheduler` service — runs `research-scheduler start`

Current extras: `.[all,ris]`
- `[all]` = rag, mcp, simtrader, studio, dev, historical, historical-import, live
- `[ris]` = apscheduler

Extras analysis:
- `dev` (pytest, pytest-cov) — REMOVE: no tests in runtime images
- `rag` (sentence-transformers ~300MB+, chromadb ~150MB+) — REMOVE: all imports
  are lazy/guarded inside function bodies. No CLI tool or scheduler job imports
  them at module level. Scheduler jobs all use --no-eval. Grep confirms zero
  top-level chromadb/sentence_transformers imports in polytool/ or tools/.
- `studio` (fastapi, uvicorn) — REMOVE: API service builds from its own
  `services/api/Dockerfile`. No root image consumer needs fastapi/uvicorn.
- `ris` (apscheduler) — KEEP: ris-scheduler needs it
- `mcp` (mcp SDK) — KEEP: lightweight, could be used by ad-hoc CLI
- `simtrader` (websocket-client) — KEEP: lightweight, CLI replay/shadow commands
- `historical` (duckdb) — KEEP: CLI historical queries
- `historical-import` (pyarrow) — KEEP: CLI historical import
- `live` (py-clob-client) — KEEP: CLI live execution commands

Target extras: `.[ris,mcp,simtrader,historical,historical-import,live]`
Estimated savings: ~500MB+ (sentence-transformers + chromadb + fastapi + uvicorn + pytest)

Stale CURRENT_STATE.md statements to fix:
- Lines 60-64: "Dockerfile.bot identified as orphaned" — WRONG. quick-260405-jle
  already pointed pair-bot-paper and pair-bot-live to Dockerfile.bot. This bullet
  describes the state BEFORE the slimming pass but was not updated afterward.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Narrow root Dockerfile extras and fix stale CURRENT_STATE docs</name>
  <files>Dockerfile, docs/CURRENT_STATE.md</files>
  <action>
1. In `Dockerfile`, change BOTH pip install lines (the cached dep install AND the
   --no-deps reinstall) from:
   ```
   pip install ".[all,ris]"
   ```
   to:
   ```
   pip install ".[ris,mcp,simtrader,historical,historical-import,live]"
   ```
   Update the comment above the first pip install line to explain what each extra
   provides and why rag/studio/dev are excluded:
   ```
   # [ris]              = apscheduler (scheduler runtime)
   # [mcp]              = mcp SDK (MCP server)
   # [simtrader]        = websocket-client (replay/shadow)
   # [historical]       = duckdb (historical queries)
   # [historical-import]= pyarrow (historical import)
   # [live]             = py-clob-client (live execution)
   # Excluded: [rag] (sentence-transformers/chromadb ~450MB, all imports lazy),
   #           [studio] (fastapi/uvicorn, API has own Dockerfile),
   #           [dev] (pytest, not for runtime images)
   ```

2. In `docs/CURRENT_STATE.md`, replace the stale orphan bullet (lines 60-64):
   ```
   - **Dockerfile.bot identified as orphaned (quick-260405-j2t, 2026-04-05)**: No
     compose service references `Dockerfile.bot`. It uses Python 3.12 (inconsistent
     with 3.11 elsewhere) and installs `[live,simtrader]` extras (pair-bot services
     use root Dockerfile with `[all,ris]`). Status documented; file not deleted.
     Cleanup commands documented in dev log.
   ```
   with an updated bullet that reflects the current truth:
   ```
   - **Dockerfile.bot adopted for pair-bot (quick-260405-jle, 2026-04-05)**:
     `pair-bot-paper` and `pair-bot-live` compose services now build from
     `Dockerfile.bot` (python:3.11-slim, `[live,simtrader]` only, multi-stage).
     Root `Dockerfile` narrowed to `[ris,mcp,simtrader,historical,historical-import,live]`
     (quick-260405-jyv) — drops `[rag]` (~450MB sentence-transformers/chromadb, all
     imports lazy), `[studio]` (API has own Dockerfile), and `[dev]` (pytest not for
     runtime). See dev logs `2026-04-05_docker_image_slimming.md` and
     `2026-04-05_root_image_final_slimming.md`.
   ```

3. Do NOT touch pyproject.toml, Dockerfile.bot, or docker-compose.yml.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m polytool --help && rtk docker compose config --quiet 2>/dev/null; echo "exit: $?"</automated>
  </verify>
  <done>
  - Dockerfile pip install lines use narrowed extras (no rag, studio, dev)
  - Dockerfile comments explain what each extra provides and why three are excluded
  - CURRENT_STATE.md orphan bullet replaced with accurate current-state bullet
  - python -m polytool --help passes (no import breakage)
  - docker compose config validates (compose topology unchanged)
  </done>
</task>

<task type="auto">
  <name>Task 2: Write dev log</name>
  <files>docs/dev_logs/2026-04-05_root_image_final_slimming.md</files>
  <action>
Create `docs/dev_logs/2026-04-05_root_image_final_slimming.md` with:

- Task ID: quick-260405-jyv
- Branch: feat/ws-clob-feed
- Summary: narrowed root image extras, fixed stale CURRENT_STATE docs
- Before/After table:
  | Attribute | Before | After |
  | Extras | `.[all,ris]` | `.[ris,mcp,simtrader,historical,historical-import,live]` |
  | Dropped | — | rag (~450MB), studio (~15MB), dev (~10MB) |
  | Estimated savings | — | ~475MB+ |
- Audit methodology: grep confirmed zero top-level chromadb/sentence_transformers
  imports in polytool/ and tools/; all RAG imports are lazy (inside function bodies);
  scheduler jobs use --no-eval; API service has own Dockerfile (no studio needed);
  pytest not for runtime images
- CURRENT_STATE.md fix: replaced stale "Dockerfile.bot orphaned" bullet with
  accurate description of adopted state + root image narrowing
- Files changed table
- Verification results (polytool --help, compose config)
- Codex review tier: Skip (Dockerfile + docs only)
  </action>
  <verify>
    <automated>test -f "D:/Coding Projects/Polymarket/PolyTool/docs/dev_logs/2026-04-05_root_image_final_slimming.md" && echo "PASS" || echo "FAIL"</automated>
  </verify>
  <done>Dev log exists with complete before/after analysis, audit methodology, and verification results</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

No new trust boundaries introduced. This is a dependency-narrowing change to
an existing Dockerfile. No new network exposure, no new code paths.

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-01 | Denial of Service | Dockerfile | accept | Removing extras reduces attack surface (fewer packages = fewer CVE vectors). Net positive. |
</threat_model>

<verification>
1. `python -m polytool --help` — CLI still loads without import errors
2. `docker compose config --quiet` — compose YAML still validates
3. Grep Dockerfile for `rag\|studio\|dev\|all` — none of these should appear in pip install lines
4. Read CURRENT_STATE.md — no "orphaned" claim about Dockerfile.bot
</verification>

<success_criteria>
- Root Dockerfile installs `.[ris,mcp,simtrader,historical,historical-import,live]` (not `.[all,ris]`)
- ~475MB+ of unnecessary packages (sentence-transformers, chromadb, fastapi, uvicorn, pytest) excluded from root image
- CURRENT_STATE.md accurately describes Dockerfile.bot as adopted (not orphaned)
- No Python import breakage
- No compose topology changes
- Dev log written
</success_criteria>

<output>
After completion, create `.planning/quick/260405-jyv-root-image-final-slimming-narrow-extras-/260405-jyv-SUMMARY.md`
</output>
