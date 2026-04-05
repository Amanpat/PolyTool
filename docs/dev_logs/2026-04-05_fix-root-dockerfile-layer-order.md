# Dev Log: Fix Root Dockerfile Layer Order

**Date:** 2026-04-05
**Task:** quick-260405-kh2
**Branch:** feat/ws-clob-feed
**Commits:** 4d6b5e5, 103ac8a

---

## Root Cause

The Dockerfile used a two-phase pip install pattern to cache dependencies
separately from source. Phase 1 (`pip install ".[extras]"`) ran before any
`COPY polytool/` or `COPY packages/` lines, and before `README.md` entered the
build context (`.dockerignore` excludes it by default).

setuptools requires two things to process the package metadata:
1. `README.md` — declared as `readme = "README.md"` in `pyproject.toml`
2. All package directories listed in `[tool.setuptools] packages = [...]`

With neither available, the build aborted with:

```
warning: /app/README.md not found
error: package directory './polytool/reports' does not exist
```

(and similar for 20+ other package directories declared in `pyproject.toml`)

---

## Fix

Added a stub-creation `RUN` layer in the builder stage, inserted **after**
`COPY pyproject.toml ./` and **before** the deps-only pip install.

The stub layer:
1. Creates `README.md` inline (`echo "# PolyTool" > README.md`)
2. Uses `mkdir -p` to create every package directory declared in `[tool.setuptools] packages`
3. Uses `find ... -type d -exec touch {}/__init__.py \;` to create stub `__init__.py` files

The real `COPY polytool/ packages/ tools/ services/` layer that follows overwrites
all stubs with actual source. The subsequent `--no-deps` reinstall then corrects
entry points and metadata to reflect the real source tree.

**Initial attempt:** Only stubbed `polytool/__init__.py`. Build still failed on
`./polytool/reports` (second package in the declaration list). Required expanding
to cover all 24 declared package directories.

**Final stub covers:**
- `polytool/`, `polytool/reports/`
- `packages/polymarket/` and all 12 sub-packages (rag, hypotheses, notifications,
  market_selection, historical_import, simtrader + 8 simtrader sub-packages, crypto_pairs)
- `packages/research/hypotheses/`, `packages/research/scheduling/`
- `tools/cli/`, `tools/guard/`

---

## Build Layer Ordering After Fix

```
1. apt-get install gcc libffi-dev
2. COPY pyproject.toml ./
3. RUN (stub layer) — creates README.md + all __init__.py stubs   ← NEW
4. RUN pip install --upgrade pip && pip install ".[extras]"       (deps cached here)
5. COPY polytool/ packages/ tools/ services/                      (real source)
6. RUN pip install --no-deps ".[extras]"                          (fixes entry points)
```

BuildKit dep-cache is preserved: the deps layer is invalidated only when
`pyproject.toml` changes. Source-only changes skip straight to step 5.

---

## Verification

**docker compose build ris-scheduler output (abbreviated):**

```
#15 [builder  5/11] RUN echo "# PolyTool" > README.md ...
#15 DONE 0.2s

#16 [builder  6/11] RUN --mount=type=cache... pip install --upgrade pip && pip install "[...]"
...
#16 Successfully installed ... polytool-0.1.0 ...
#16 DONE 78.5s

#17-#20 COPY polytool/ packages/ tools/ services/  DONE

#21 [builder 11/11] RUN pip install --no-deps "[...]"
...
#21 Successfully installed polytool-0.1.0
#21 DONE 5.0s

polytool-ris-scheduler  Built
BUILD EXIT: 0
```

**python -m polytool --help:** Exit 0, CLI loads without import errors.

---

## Files Changed

- `Dockerfile` — stub `RUN` layer added between `COPY pyproject.toml` and deps install;
  all other layers unchanged

---

## Codex Review

Tier: skip (Dockerfile only — no execution, risk, or order-placement logic)
