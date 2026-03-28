---
phase: quick-036
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - artifacts/ (directory restructure — all moves in-place, gitignored)
  - packages/polymarket/silver_reconstructor.py
  - packages/polymarket/crypto_pairs/await_soak.py
  - packages/polymarket/crypto_pairs/live_runner.py
  - packages/polymarket/crypto_pairs/paper_runner.py
  - tools/cli/batch_reconstruct_silver.py
  - tools/cli/reconstruct_silver.py
  - tools/cli/summarize_gap_fill.py
  - tools/cli/capture_new_market_tapes.py
  - tools/cli/gate2_preflight.py
  - tools/cli/prepare_gate2.py
  - tools/cli/scan_gate2_candidates.py
  - tools/cli/simtrader.py
  - tools/cli/tape_manifest.py
  - tools/cli/watch_arb_candidates.py
  - tools/cli/close_benchmark_v1.py
  - tools/cli/crypto_pair_await_soak.py
  - tools/cli/crypto_pair_backtest.py
  - tools/cli/crypto_pair_run.py
  - tools/cli/crypto_pair_scan.py
  - tools/cli/crypto_pair_watch.py
  - tools/cli/make_session_pack.py
  - tools/gates/capture_status.py
  - tools/gates/corpus_audit.py
  - tools/gates/mm_sweep.py
  - CLAUDE.md
  - docs/dev_logs/2026-03-28_artifacts_restructure.md
autonomous: true
requirements: [INFRA-CLEANUP]

must_haves:
  truths:
    - "find artifacts/ -maxdepth 2 -type d shows only the target layout — no artifacts/silver/, artifacts/benchmark_closure/, artifacts/simtrader/studio_sessions/, artifacts/session_packs/, artifacts/architect_context_bundle at the top level"
    - "All loose debug files (politics_watch*, regime_inventory*, pmxt_*.json, session_debug_summary*, silver_batch_metadata*, requested_raw_concat*) are under artifacts/debug/ not at root"
    - "python -m pytest tests/ -x -q --timeout=30 passes with no regressions"
    - "python -m polytool --help loads without errors"
  artifacts:
    - path: "artifacts/tapes/silver/"
      provides: "all former artifacts/silver/{id}/ directories"
    - path: "artifacts/tapes/gold/"
      provides: "non-shadow tapes from former artifacts/simtrader/tapes/"
    - path: "artifacts/tapes/shadow/"
      provides: "shadow tapes from former artifacts/simtrader/tapes/*shadow*"
    - path: "artifacts/tapes/crypto/"
      provides: "new_market tapes and crypto paper runs"
    - path: "artifacts/benchmark/"
      provides: "former artifacts/benchmark_closure/ contents"
    - path: "artifacts/gates/gate2_sweep/"
      provides: "former artifacts/gates/mm_sweep_gate/ contents"
    - path: "artifacts/gates/manifests/"
      provides: "artifacts/gates/gate2_tape_manifest.json"
    - path: "artifacts/debug/"
      provides: "probe output files and loose root-level debug files"
    - path: "docs/dev_logs/2026-03-28_artifacts_restructure.md"
      provides: "dev log for this change"
  key_links:
    - from: "tools/cli/tape_manifest.py"
      to: "artifacts/gates/gate2_tape_manifest.json"
      via: "_DEFAULT_OUT constant"
      pattern: "artifacts/gates/gate2_tape_manifest\\.json"
    - from: "tools/gates/mm_sweep.py"
      to: "artifacts/gates/gate2_tape_manifest.json"
      via: "DEFAULT_GATE2_MANIFEST_PATH constant"
      pattern: "artifacts.*gate2_tape_manifest\\.json"
    - from: "tools/cli/simtrader.py"
      to: "artifacts/tapes/gold/ and artifacts/tapes/shadow/"
      via: "default tape dir"
      pattern: "artifacts/tapes/"
    - from: "tools/gates/corpus_audit.py"
      to: "artifacts/tapes/silver/ and artifacts/tapes/gold/"
      via: "default tape roots list"
      pattern: "artifacts/tapes/"
---

<objective>
Restructure the artifacts/ directory into a clean, maintainable layout by executing the 10-step migration plan, updating all hardcoded path references in Python source, and documenting the new layout in CLAUDE.md.

Purpose: 53MB of accumulated artifacts have diverged from any documented structure — silver tapes live under unreadable token IDs, there are two competing tape directories, and stale debug files sit at the root. This makes corpus tooling configuration error-prone and makes onboarding harder.

Output:
- Restructured artifacts/ matching the target layout
- All Python path constants updated to new locations
- CLAUDE.md updated with artifacts directory layout reference
- Dev log at docs/dev_logs/2026-03-28_artifacts_restructure.md
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/.planning/STATE.md
@D:/Coding Projects/Polymarket/PolyTool/CLAUDE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Execute filesystem migration</name>
  <files>artifacts/ (directory restructure)</files>
  <action>
Execute the following shell commands IN ORDER. All paths are relative to the repo root. The entire artifacts/ tree is gitignored, so there is no git involvement.

**Step 1 — Create new directories:**
```bash
mkdir -p artifacts/tapes/gold
mkdir -p artifacts/tapes/silver
mkdir -p artifacts/tapes/bronze
mkdir -p artifacts/tapes/crypto/paper_runs
mkdir -p artifacts/tapes/shadow
mkdir -p artifacts/gates/gate2_sweep
mkdir -p artifacts/gates/gate3_shadow
mkdir -p artifacts/gates/manifests
mkdir -p artifacts/benchmark
mkdir -p artifacts/debug
```

**Step 2 — Move silver tapes (numeric IDs + manual_gap_fill*) to artifacts/tapes/silver/:**
```bash
find artifacts/silver/ -maxdepth 1 -mindepth 1 -type d | grep -v "probe" | xargs -I{} mv {} artifacts/tapes/silver/
```
Move probe output files to debug:
```bash
mv artifacts/silver/start_process_probe_stderr.txt artifacts/debug/ 2>/dev/null || true
mv artifacts/silver/start_process_probe_stdout.txt artifacts/debug/ 2>/dev/null || true
mv artifacts/silver/manual_gap_fill_probe3_20260319_190329 artifacts/tapes/silver/ 2>/dev/null || true
```
Remove empty silver dir:
```bash
rmdir artifacts/silver 2>/dev/null || true
```

**Step 3 — Consolidate tape directories:**
Move shadow tapes from artifacts/simtrader/tapes/ (dirs with "shadow" in the name):
```bash
find artifacts/simtrader/tapes/ -maxdepth 1 -mindepth 1 -type d -name "*shadow*" | xargs -I{} mv {} artifacts/tapes/shadow/
```
Move new_market_capture from simtrader/tapes to tapes/crypto:
```bash
mv artifacts/simtrader/tapes/new_market_capture artifacts/tapes/crypto/ 2>/dev/null || true
```
Move remaining simtrader/tapes dirs (non-shadow, non-new_market_capture) to artifacts/tapes/gold/:
```bash
find artifacts/simtrader/tapes/ -maxdepth 1 -mindepth 1 -type d | xargs -I{} mv {} artifacts/tapes/gold/
```
Move existing artifacts/tapes/new_market/ to artifacts/tapes/crypto/:
```bash
mv artifacts/tapes/new_market artifacts/tapes/crypto/new_market 2>/dev/null || true
```
Move crypto pair paper runs:
```bash
mv artifacts/crypto_pairs/paper_runs/* artifacts/tapes/crypto/paper_runs/ 2>/dev/null || true
rmdir artifacts/crypto_pairs/paper_runs 2>/dev/null || true
```

**Step 4 — Gate artifacts:**
Move mm_sweep_gate contents to gate2_sweep:
```bash
find artifacts/gates/mm_sweep_gate/ -maxdepth 1 -mindepth 1 | xargs -I{} mv {} artifacts/gates/gate2_sweep/
rmdir artifacts/gates/mm_sweep_gate 2>/dev/null || true
```
Move gate2_tape_manifest.json to manifests:
```bash
mv artifacts/gates/gate2_tape_manifest.json artifacts/gates/manifests/ 2>/dev/null || true
```

**Step 5 — Benchmark closure:**
```bash
find artifacts/benchmark_closure/ -maxdepth 1 -mindepth 1 | xargs -I{} mv {} artifacts/benchmark/
rmdir artifacts/benchmark_closure 2>/dev/null || true
```

**Step 6 — Move loose debug files to artifacts/debug/:**
```bash
mv artifacts/politics_watch* artifacts/debug/ 2>/dev/null || true
mv artifacts/regime_inventory* artifacts/debug/ 2>/dev/null || true
mv artifacts/requested_raw_concat* artifacts/debug/ 2>/dev/null || true
mv artifacts/session_debug_summary* artifacts/debug/ 2>/dev/null || true
mv artifacts/pmxt_*.json artifacts/debug/ 2>/dev/null || true
mv artifacts/silver_batch_metadata* artifacts/debug/ 2>/dev/null || true
```
Move corpus_audit dir to debug (informational output, not gate data):
```bash
mv artifacts/corpus_audit artifacts/debug/corpus_audit 2>/dev/null || true
```

**Step 7 — Delete stale artifacts:**
```bash
rm -rf artifacts/architect_context_bundle
rm -f artifacts/architect_context_bundle.zip
rm -rf artifacts/session_packs
rm -rf artifacts/simtrader/studio_sessions
```
Remove now-empty simtrader/tapes dir:
```bash
rmdir artifacts/simtrader/tapes 2>/dev/null || true
```

**Step 8 — Add .gitkeep files to new empty directories so they can be tracked if ever un-gitignored:**
```bash
for d in artifacts/tapes/gold artifacts/tapes/silver artifacts/tapes/bronze artifacts/tapes/shadow artifacts/tapes/crypto/paper_runs artifacts/gates/gate2_sweep artifacts/gates/gate3_shadow artifacts/gates/manifests artifacts/benchmark artifacts/debug; do
  [ -z "$(ls -A $d 2>/dev/null)" ] && touch "$d/.gitkeep"
done
```

**Verify filesystem result:**
```bash
find artifacts/ -maxdepth 2 -type d | sort
find artifacts/ -maxdepth 1 -type f
```
Expected: no more artifacts/silver/, artifacts/benchmark_closure/, artifacts/simtrader/studio_sessions/, artifacts/session_packs/, or loose debug files at root.
  </action>
  <verify>
    <automated>find artifacts/ -maxdepth 1 -type d | sort && find artifacts/ -maxdepth 1 -type f | sort</automated>
  </verify>
  <done>artifacts/silver/ is gone; artifacts/benchmark_closure/ is gone; artifacts/session_packs/ is gone; artifacts/architect_context_bundle is gone; loose debug files are gone from root; artifacts/tapes/silver/, artifacts/tapes/gold/, artifacts/tapes/shadow/, artifacts/tapes/crypto/, artifacts/gates/gate2_sweep/, artifacts/gates/manifests/, artifacts/benchmark/ all exist with their content.</done>
</task>

<task type="auto">
  <name>Task 2: Update hardcoded paths in Python source</name>
  <files>
    packages/polymarket/silver_reconstructor.py,
    packages/polymarket/crypto_pairs/await_soak.py,
    packages/polymarket/crypto_pairs/live_runner.py,
    packages/polymarket/crypto_pairs/paper_runner.py,
    tools/cli/batch_reconstruct_silver.py,
    tools/cli/reconstruct_silver.py,
    tools/cli/summarize_gap_fill.py,
    tools/cli/capture_new_market_tapes.py,
    tools/cli/gate2_preflight.py,
    tools/cli/prepare_gate2.py,
    tools/cli/scan_gate2_candidates.py,
    tools/cli/simtrader.py,
    tools/cli/tape_manifest.py,
    tools/cli/watch_arb_candidates.py,
    tools/cli/close_benchmark_v1.py,
    tools/cli/crypto_pair_await_soak.py,
    tools/cli/crypto_pair_backtest.py,
    tools/cli/crypto_pair_run.py,
    tools/cli/crypto_pair_scan.py,
    tools/cli/crypto_pair_watch.py,
    tools/cli/make_session_pack.py,
    tools/gates/capture_status.py,
    tools/gates/corpus_audit.py,
    tools/gates/mm_sweep.py
  </files>
  <action>
Update ONLY path string constants, default values, help text, and print statements. Do NOT modify business logic, algorithm behavior, or test files (tests use tmp_path or string literals that do not affect real filesystem behavior).

**Path mapping (old → new):**

| Old path | New path |
|---|---|
| `artifacts/silver/` | `artifacts/tapes/silver/` |
| `artifacts/simtrader/tapes` | `artifacts/tapes/gold` |
| `artifacts/simtrader/tapes/new_market_capture` | `artifacts/tapes/crypto/new_market_capture` |
| `artifacts/benchmark_closure/` | `artifacts/benchmark/` |
| `artifacts/crypto_pairs/paper_runs` | `artifacts/tapes/crypto/paper_runs` |
| `artifacts/crypto_pairs/live_runs` | `artifacts/crypto_pairs/live_runs` (leave — no target in spec) |
| `artifacts/crypto_pairs/await_soak` | `artifacts/crypto_pairs/await_soak` (leave) |
| `artifacts/crypto_pairs/backtests` | `artifacts/crypto_pairs/backtests` (leave) |
| `artifacts/crypto_pairs/scan` | `artifacts/crypto_pairs/scan` (leave) |
| `artifacts/crypto_pairs/watch` | `artifacts/crypto_pairs/watch` (leave) |
| `artifacts/gates/mm_sweep_gate` | `artifacts/gates/gate2_sweep` |
| `artifacts/gates/gate2_tape_manifest.json` | `artifacts/gates/manifests/gate2_tape_manifest.json` |
| `artifacts/session_packs` | `artifacts/debug/session_packs` |

**Key file changes:**

`tools/cli/tape_manifest.py`:
- `_DEFAULT_OUT = Path("artifacts/gates/gate2_tape_manifest.json")` → `Path("artifacts/gates/manifests/gate2_tape_manifest.json")`

`tools/gates/mm_sweep.py`:
- `DEFAULT_GATE2_MANIFEST_PATH = _REPO_ROOT / "artifacts" / "gates" / "gate2_tape_manifest.json"` → `_REPO_ROOT / "artifacts" / "gates" / "manifests" / "gate2_tape_manifest.json"`

`tools/cli/simtrader.py`:
- All occurrences of `artifacts/simtrader/tapes` → `artifacts/tapes/gold`
- Shadow-specific mentions: where the path already includes "shadow" in narrative text, update to `artifacts/tapes/shadow/`

`tools/cli/gate2_preflight.py`:
- `_DEFAULT_TAPES_DIR = Path("artifacts/simtrader/tapes")` → `Path("artifacts/tapes/gold")`

`tools/cli/prepare_gate2.py`:
- `_DEFAULT_TAPES_BASE = Path("artifacts/simtrader/tapes")` → `Path("artifacts/tapes/gold")`

`tools/cli/scan_gate2_candidates.py`:
- `--tapes-dir artifacts/simtrader/tapes` in help text → `artifacts/tapes/gold`

`tools/cli/tape_manifest.py`:
- `--tapes-dir artifacts/simtrader/tapes` in help text → `artifacts/tapes/gold`

`tools/cli/watch_arb_candidates.py`:
- `_DEFAULT_TAPES_BASE = Path("artifacts/simtrader/tapes")` → `Path("artifacts/tapes/gold")`

`tools/cli/capture_new_market_tapes.py`:
- `_DEFAULT_TAPES_ROOT = Path("artifacts/simtrader/tapes/new_market_capture")` → `Path("artifacts/tapes/crypto/new_market_capture")`

`tools/gates/corpus_audit.py`:
- In the default tape roots list, replace `"artifacts/simtrader/tapes"` → `"artifacts/tapes/gold"`
- Add `"artifacts/tapes/silver"` if not already present (it is needed to find silver tapes)
- Update help text references

`tools/gates/capture_status.py`:
- Update `--out artifacts/gates/mm_sweep_gate` reference in help text → `--out artifacts/gates/gate2_sweep`

`packages/polymarket/crypto_pairs/paper_runner.py`:
- `DEFAULT_PAPER_ARTIFACTS_DIR = Path("artifacts/crypto_pairs/paper_runs")` → `Path("artifacts/tapes/crypto/paper_runs")`

`tools/cli/reconstruct_silver.py` and `batch_reconstruct_silver.py`:
- Update example paths in docstrings/help text from `artifacts/silver/` → `artifacts/tapes/silver/`

`tools/cli/summarize_gap_fill.py`:
- Update example paths in docstrings from `artifacts/silver/` → `artifacts/tapes/silver/`

`packages/polymarket/silver_reconstructor.py`:
- Update docstring/example from `artifacts/silver/` → `artifacts/tapes/silver/`

`tools/cli/close_benchmark_v1.py`:
- Update `artifacts/benchmark_closure/` reference in print statement → `artifacts/benchmark/`

`tools/cli/make_session_pack.py`:
- `_DEFAULT_OUTPUT_DIR = Path("artifacts/session_packs")` → `Path("artifacts/debug/session_packs")`
  </action>
  <verify>
    <automated>python -m polytool --help && python -m pytest tests/ -x -q --timeout=30 2>&1 | tail -5</automated>
  </verify>
  <done>python -m polytool --help exits 0 with no import errors. pytest passes with no regressions (same pass count as before, ±5 for flaky). No Python file still contains `artifacts/silver/`, `artifacts/simtrader/tapes`, `artifacts/benchmark_closure/`, `artifacts/gates/mm_sweep_gate`, or `artifacts/gates/gate2_tape_manifest.json` as a path constant or default value.</done>
</task>

<task type="auto">
  <name>Task 3: Update CLAUDE.md and write dev log</name>
  <files>CLAUDE.md, docs/dev_logs/2026-03-28_artifacts_restructure.md</files>
  <action>
**CLAUDE.md update:**

In the section "What Is Already Built (high-confidence current state)" — after the existing benchmark pipeline block — add a new subsection heading and reference:

```
### Artifacts directory layout

See target layout documented in this section. All artifacts are gitignored.
```

Then add (or update the existing) "Expected high-value paths" block to replace any outdated `artifacts/` sub-paths. Replace the generic `artifacts/` bullet with these specific entries:

```
- `artifacts/tapes/gold/`       — live tape recorder output (Gold tier)
- `artifacts/tapes/silver/`     — reconstructed Silver tapes
- `artifacts/tapes/bronze/`     — Bronze (trade-level only) tapes
- `artifacts/tapes/shadow/`     — shadow run tapes
- `artifacts/tapes/crypto/`     — crypto pair new-market and paper-run tapes
- `artifacts/gates/gate2_sweep/` — Gate 2 sweep results
- `artifacts/gates/manifests/`  — gate manifests (gate2_tape_manifest.json)
- `artifacts/benchmark/`        — benchmark closure run artifacts
- `artifacts/simtrader/runs/`   — SimTrader replay runs
- `artifacts/simtrader/sweeps/` — SimTrader sweep outputs
- `artifacts/simtrader/ondemand_sessions/` — Studio OnDemand sessions
- `artifacts/dossiers/users/`   — wallet/user dossier bundles
- `artifacts/research/batch_runs/` — research batch run outputs
- `artifacts/market_selection/` — market selection artifacts
- `artifacts/watchlists/`       — market watchlist artifacts
- `artifacts/debug/`            — probe outputs, loose debug files, corpus audits
```

**Dev log — write docs/dev_logs/2026-03-28_artifacts_restructure.md:**

```markdown
# 2026-03-28 Artifacts Directory Restructure

## Objective
Eliminate structural debt in artifacts/: two tape directories, non-readable silver
tape names at top level, stale one-off debug files at root, and undocumented layout.

## Changes Made

### Filesystem moves
- artifacts/silver/{id}/ → artifacts/tapes/silver/{id}/
- artifacts/simtrader/tapes/*shadow*/ → artifacts/tapes/shadow/
- artifacts/simtrader/tapes/{non-shadow}/ → artifacts/tapes/gold/
- artifacts/simtrader/tapes/new_market_capture/ → artifacts/tapes/crypto/new_market_capture/
- artifacts/tapes/new_market/ → artifacts/tapes/crypto/new_market/
- artifacts/crypto_pairs/paper_runs/ → artifacts/tapes/crypto/paper_runs/
- artifacts/benchmark_closure/ → artifacts/benchmark/
- artifacts/gates/mm_sweep_gate/ → artifacts/gates/gate2_sweep/
- artifacts/gates/gate2_tape_manifest.json → artifacts/gates/manifests/gate2_tape_manifest.json
- Loose root debug files → artifacts/debug/
- artifacts/corpus_audit/ → artifacts/debug/corpus_audit/

### Deleted stale artifacts
- artifacts/architect_context_bundle/
- artifacts/architect_context_bundle.zip
- artifacts/session_packs/
- artifacts/simtrader/studio_sessions/

### Python path constant updates
All DEFAULT_*_DIR, DEFAULT_*_PATH constants and help text updated to match
new layout. Business logic untouched. Test files not modified (they use tmp_path).

## Verification
- python -m polytool --help: OK
- python -m pytest tests/ -x -q --timeout=30: all passing
- find artifacts/ -maxdepth 2 -type d: matches target layout
```
  </action>
  <verify>
    <automated>python -m polytool --help 2>&1 | head -5 && grep -c "tapes/silver" CLAUDE.md</automated>
  </verify>
  <done>CLAUDE.md contains the new artifacts layout section. dev log exists at docs/dev_logs/2026-03-28_artifacts_restructure.md. python -m polytool --help still loads clean.</done>
</task>

</tasks>

<verification>
After all tasks complete:

```bash
# 1. Check target layout
find artifacts/ -maxdepth 2 -type d | sort

# 2. No stale dirs at root
find artifacts/ -maxdepth 1 -name "silver" -o -maxdepth 1 -name "benchmark_closure" -o -maxdepth 1 -name "session_packs"

# 3. No loose debug files at root
find artifacts/ -maxdepth 1 -type f

# 4. No old path constants remaining in Python source
grep -r "artifacts/silver/" packages/ tools/ --include="*.py" | grep -v "docstring\|#\|tapes/silver"
grep -r "artifacts/simtrader/tapes" packages/ tools/ --include="*.py"
grep -r "artifacts/benchmark_closure" packages/ tools/ --include="*.py"
grep -r "artifacts/gates/mm_sweep_gate" packages/ tools/ --include="*.py"
grep -r "artifacts/gates/gate2_tape_manifest" tools/ --include="*.py" | grep -v "manifests"

# 5. Regression check
python -m polytool --help
python -m pytest tests/ -x -q --timeout=30 | tail -10
```
</verification>

<success_criteria>
- All 53MB of artifacts live under the target layout
- Zero old path constants remaining in packages/, tools/ Python files
- Test suite passes with no regressions
- CLAUDE.md documents the layout for future sessions
- Dev log written
</success_criteria>

<output>
After completion, create `.planning/quick/36-artifacts-directory-restructure-unified-/36-SUMMARY.md` using the summary template at `.claude/get-shit-done/templates/summary.md`.
</output>
