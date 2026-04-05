# Dev Log: Root Dockerfile Build Fix — Close-Out Verification

**Date:** 2026-04-05
**Task:** quick-260405-kpg
**Branch:** feat/ws-clob-feed

---

## Context

This is a verification-only task. No code changes were made.

Prior task quick-260405-kh2 fixed the root Dockerfile layer-order bug: the
stub-creation `RUN` layer was missing, causing setuptools to abort with
`package directory './polytool/reports' does not exist` during the deps-only pip
install phase. The fix (committed 4d6b5e5, 103ac8a) inserted a stub `RUN` layer
between `COPY pyproject.toml` and the deps install, creating `README.md` and all
24 declared package directories as stubs.

quick-260405-kh2 verified ris-scheduler in isolation. This task verifies the full
default compose stack (both buildable services: `api` + `ris-scheduler`) builds
cleanly after that fix.

---

## Commands Run

### Step 1: Validate compose YAML

```
rtk docker compose config --quiet
```

**Output:**

```
[rtk] /!\ No hook installed — run `rtk init -g` for automatic token savings
EXIT: 0
```

Result: PASS — compose YAML is valid.

---

### Step 2: Full default-compose build

```
docker compose build
```

**Output (abbreviated — key stages):**

```
#2  [api internal] load build definition from Dockerfile  DONE
#3  [ris-scheduler internal] load build definition from Dockerfile  DONE

#13 [api stage-0 3/8] WORKDIR /app  CACHED
#14 [api stage-0 2/8] RUN ... apt-get install curl  CACHED
#15 [api stage-0 4/8] COPY services/api/requirements.txt  CACHED
#17 [api stage-0 5/8] RUN pip install -r requirements.txt  CACHED
#18 [api stage-0 6/8] COPY packages  CACHED
#16 [api stage-0 7/8] COPY services/api  CACHED
#19 [api stage-0 8/8] WORKDIR /app/services/api  CACHED
#20 [api] exporting to image  DONE
 polytool-api  Built

#28 [ris-scheduler builder  5/11] RUN echo "# PolyTool" > README.md && mkdir -p ...  CACHED
#24 [ris-scheduler builder  6/11] RUN pip install ... "[ris,mcp,simtrader,historical,historical-import,live]"  CACHED
#30 [ris-scheduler builder  7/11] COPY polytool/  CACHED
#39 [ris-scheduler builder  8/11] COPY packages/  CACHED
#35 [ris-scheduler builder  9/11] COPY tools/  CACHED
#26 [ris-scheduler builder 10/11] COPY services/  CACHED
#33 [ris-scheduler builder 11/11] RUN pip install --no-deps "[...]"  CACHED
#32 [ris-scheduler stage-1  5/11] COPY site-packages  CACHED
#21 [ris-scheduler stage-1  6/11] COPY /usr/local/bin  CACHED
#22 [ris-scheduler stage-1  7/11] COPY polytool/  CACHED
#36 [ris-scheduler stage-1  8/11] COPY packages/  CACHED
#37 [ris-scheduler stage-1  9/11] COPY tools/  CACHED
#31 [ris-scheduler stage-1 10/11] COPY services/  CACHED
#40 [ris-scheduler stage-1 11/11] RUN chown -R polytool:polytool /app  CACHED
#41 [ris-scheduler] exporting to image  DONE
 polytool-ris-scheduler  Built
BUILD EXIT: 0
```

Result: PASS — both `api` and `ris-scheduler` built successfully (all layers CACHED
from prior builds — no layer-order errors).

---

### Step 3: CLI smoke test inside ris-scheduler container

```
docker compose run --rm --no-deps ris-scheduler python -m polytool --help
```

**Output (abbreviated):**

```
PolyTool - Polymarket analysis toolchain

Usage: polytool <command> [options]
       python -m polytool <command> [options]

--- Research Loop (Track B) ---
  wallet-scan       Batch-scan many wallets/handles -> ranked leaderboard
  alpha-distill     Distill wallet-scan data -> ranked edge candidates (no LLM)
  ...
  research-scheduler  Manage the RIS background ingestion scheduler
  ...
  simtrader         Record/replay/shadow/live trading - run 'simtrader --help'
  market-scan       Rank active Polymarket markets by reward/spread/fill quality
  ...

HELP EXIT: 0
```

Result: PASS — CLI loads without import errors.

---

## Result

**ALL 3 STEPS: PASS**

| Step | Command | Exit Code |
|------|---------|-----------|
| 1 | docker compose config --quiet | 0 |
| 2 | docker compose build | 0 |
| 3 | docker compose run --rm --no-deps ris-scheduler python -m polytool --help | 0 |

---

## Files Changed

None — this is a verification-only task.

---

## Codex Review

Tier: skip (verification + documentation only; no execution, risk, or order-placement logic)
