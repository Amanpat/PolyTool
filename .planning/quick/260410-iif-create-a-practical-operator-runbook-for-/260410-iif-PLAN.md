---
phase: quick-260410-iif
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md
  - docs/features/wallet-discovery-v1.md
  - docs/README.md
  - docs/dev_logs/2026-04-10_wallet_discovery_v1_operator_runbook.md
autonomous: true
requirements: []

must_haves:
  truths:
    - "An operator can run the full Wallet Discovery v1 path end-to-end using only the runbook"
    - "The runbook contains copy-paste command examples for every step"
    - "The runbook clearly distinguishes what v1 does from what it does NOT do"
    - "The feature doc links to the runbook"
  artifacts:
    - path: "docs/runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md"
      provides: "Complete operator runbook for Wallet Discovery v1"
      min_lines: 120
    - path: "docs/dev_logs/2026-04-10_wallet_discovery_v1_operator_runbook.md"
      provides: "Mandatory dev log for this work"
      min_lines: 20
  key_links:
    - from: "docs/features/wallet-discovery-v1.md"
      to: "docs/runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md"
      via: "markdown link in Related Docs or new Runbook section"
      pattern: "WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK"
    - from: "docs/README.md"
      to: "docs/runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md"
      via: "entry in Workflows section"
      pattern: "WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK"
---

<objective>
Write a concise, copy-paste-ready operator runbook for the shipped Wallet Discovery v1
feature. An operator should be able to follow this single document to run the entire v1
path: leaderboard discovery (Loop A), quick scan with MVF fingerprint, and human review
gate interpretation.

Purpose: The feature code (Packets A + B) shipped on 2026-04-09/10 and is integrated,
but there is no operator-facing "how to use it" document. This runbook closes that gap.

Output: One runbook in docs/runbooks/, cross-linked from the feature doc and docs README,
plus a mandatory dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@docs/specs/SPEC-wallet-discovery-v1.md
@docs/features/wallet-discovery-v1.md
@docs/runbooks/RIS_N8N_OPERATOR_SOP.md (format reference)
@docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md (format reference)
@docs/README.md
@tools/cli/discovery.py (CLI flags for run-loop-a)
@tools/cli/scan.py (--quick flag, output paths)
@packages/polymarket/discovery/__init__.py (public API)
@infra/clickhouse/initdb/27_wallet_discovery.sql (DDL for the 3 tables)
@docs/dev_logs/2026-04-10_wallet_discovery_v1_integration.md (integration context)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Write the Wallet Discovery v1 Operator Runbook</name>
  <files>docs/runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md</files>
  <action>
Create `docs/runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md` following the format
conventions of existing runbooks (RIS_N8N_OPERATOR_SOP.md, CORPUS_GOLD_CAPTURE_RUNBOOK.md):
compact, numbered sections, copy-paste command blocks, expected output annotations.

The runbook MUST contain these sections in this order:

**0. Purpose** (3-4 sentences max)
- What Wallet Discovery v1 is: Loop A leaderboard fetch, churn detection, MVF fingerprint,
  human review gate. One-line statement of the end-to-end path.

**1. Prerequisites**
- Docker running (`docker compose ps`)
- ClickHouse accessible (`curl "http://localhost:8123/?query=SELECT%201"`)
- `CLICKHOUSE_PASSWORD` env var set (with the `export` command from `.env`)
- CLI loads (`python -m polytool --help`)
- The 3 discovery tables exist (query: `SELECT name FROM system.tables WHERE database='polytool' AND name IN ('watchlist','leaderboard_snapshots','scan_queue')`)
- If tables missing: `docker compose restart clickhouse` or manually run
  `infra/clickhouse/initdb/27_wallet_discovery.sql`

**2. Loop A: Leaderboard Discovery**
- Purpose: one-sentence
- Dry-run (safe, no ClickHouse writes):
  ```
  python -m polytool discovery run-loop-a --dry-run
  ```
- Live run:
  ```
  python -m polytool discovery run-loop-a
  ```
- Expected output: show the `--- Loop A Result ---` block with field labels
  (fetch_run_id, snapshot_ts, rows_fetched, new_wallets, dropped_wallets,
  rising_wallets, rows_enqueued, dry_run)
- Customization flags: `--order-by PNL|VOL`, `--time-period DAY|WEEK|MONTH|ALL`,
  `--category OVERALL|POLITICS|SPORTS|CRYPTO`, `--max-pages N`
- How to verify rows landed in ClickHouse:
  ```
  curl "http://localhost:8123/" --data "SELECT count() FROM polytool.leaderboard_snapshots"
  curl "http://localhost:8123/" --data "SELECT count() FROM polytool.scan_queue WHERE queue_state='pending'"
  ```

**3. Quick Scan with MVF**
- Purpose: scan a wallet with zero LLM calls, producing MVF fingerprint + detectors + PnL
- Command:
  ```
  python -m polytool scan <WALLET_ADDRESS> --quick
  ```
  (Replace `<WALLET_ADDRESS>` with a real 0x-prefixed address.)
- What --quick does vs normal scan: --quick = --lite stages + MVF fingerprint, zero cloud
  LLM calls guaranteed.
- Expected artifacts: `dossier.json` in the artifact output directory, containing an `"mvf"`
  block with the 11 MVF dimensions.
- How to confirm MVF was appended:
  ```
  python -c "import json, pathlib, sys; d=json.loads(pathlib.Path(sys.argv[1]).read_text()); print(json.dumps(d.get('mvf',{}), indent=2))" path/to/dossier.json
  ```
  (Or simply: open dossier.json, search for `"mvf"` key.)
- List the 11 MVF dimensions by name so the operator knows what to expect:
  win_rate, avg_hold_duration_hours, median_entry_price, market_concentration,
  category_entropy, avg_position_size_usdc, trade_frequency_per_day,
  late_entry_rate, dca_score, resolution_coverage_rate, maker_taker_ratio.
- Note: `late_entry_rate` may be null (Gap E — requires market_open_ts/close_timestamp
  in dossier export schema). `maker_taker_ratio` may be null if maker/taker data unavailable.

**4. Human Review Gate**
- The lifecycle path is: discovered -> queued -> scanned -> reviewed -> promoted.
- `scanned -> promoted` is an INVALID transition. The operator MUST review before promoting.
- v1 has NO auto-promotion code path. The operator reviews scan output (MVF + detectors + PnL)
  and manually decides.
- Currently there is no CLI command for lifecycle state transitions — the operator inspects
  the scan output and records decisions. State transitions are application-enforced.
- What to look for when reviewing: MVF dimensions (win_rate, hold duration, DCA score,
  trade frequency), PnL data, detector outputs.

**5. ClickHouse Tables Reference**
- Compact table showing the 3 tables, their engine, their purpose, and a one-line query
  to inspect each:
  | Table | Engine | Purpose | Quick Query |
  |-------|--------|---------|-------------|
  | `watchlist` | ReplacingMergeTree | Wallet lifecycle state | `SELECT * FROM polytool.watchlist LIMIT 5` |
  | `leaderboard_snapshots` | MergeTree | Raw leaderboard facts | `SELECT count() FROM polytool.leaderboard_snapshots` |
  | `scan_queue` | ReplacingMergeTree | Discovery work queue | `SELECT * FROM polytool.scan_queue WHERE queue_state='pending' LIMIT 5` |

**6. What v1 Does NOT Cover**
- Bullet list extracted directly from the spec non-goals: Loop B, Loop C, Loop D,
  insider scoring, exemplar selection, cloud LLM wallet analysis, auto-promotion,
  n8n discovery integration, Docker services for Loop B/D, copy-trading, SimTrader
  closed-loop testing.
- One-sentence note: see `docs/specs/SPEC-wallet-discovery-v1.md` for blockers per
  deferred capability.

**7. Troubleshooting**
Table format matching RIS_N8N_OPERATOR_SOP.md "Common Mistakes" section:
| Symptom | Cause | Fix |
|---------|-------|-----|
| `Error: CLICKHOUSE_PASSWORD is required` | Env var not set | `export CLICKHOUSE_PASSWORD=$(grep CLICKHOUSE_PASSWORD .env \| cut -d= -f2)` |
| Tables not found (empty query result in prereq) | DDL not applied | `docker compose restart clickhouse` or run `27_wallet_discovery.sql` manually |
| Loop A returns 0 rows_fetched | Polymarket API unreachable or rate-limited | Check internet; retry after 60s |
| scan_queue shows 0 pending after Loop A | No new wallets vs. previous snapshot (all seen before) | Normal — means the leaderboard is stable. Try `--time-period WEEK` or `--category CRYPTO` for different coverage |
| `--quick` scan produces no MVF block in dossier.json | Wallet has 0 resolved positions | MVF requires at least 1 position with trade data |
| `late_entry_rate` is null in MVF | Gap E: market timestamps not in dossier schema | Expected in v1 — not a bug |
| `ImportError: discovery` | Package not installed or path issue | Run from project root; verify `python -m polytool --help` works |

**8. Related Docs**
Table format:
| Doc | Purpose |
|-----|---------|
| `docs/specs/SPEC-wallet-discovery-v1.md` | Frozen v1 contract (table DDL, lifecycle state machine, acceptance tests) |
| `docs/features/wallet-discovery-v1.md` | Feature doc with implementation status |
| `infra/clickhouse/initdb/27_wallet_discovery.sql` | ClickHouse DDL for the 3 tables |
| `docs/dev_logs/2026-04-10_wallet_discovery_v1_integration.md` | Integration dev log |

Style notes:
- Keep the doc under 250 lines. Operator docs should be scannable, not exhaustive.
- Use `Last verified: 2026-04-10` in the header.
- No LLM-dependent steps anywhere in the runbook.
- All commands must be copy-pasteable as-is (except wallet address placeholders).
  </action>
  <verify>
    <automated>python -c "p=__import__('pathlib').Path('docs/runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md'); assert p.exists(); t=p.read_text(); assert len(t.splitlines())>=120, f'Too short: {len(t.splitlines())} lines'; assert '--quick' in t; assert 'run-loop-a' in t; assert '--dry-run' in t; assert 'mvf' in t.lower(); assert 'CLICKHOUSE_PASSWORD' in t; assert 'NOT' in t or 'Does NOT' in t; print('PASS: runbook exists with all required sections')"</automated>
  </verify>
  <done>
    Runbook exists at docs/runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md with all 8 sections.
    Contains copy-paste commands for dry-run Loop A, live Loop A, quick scan, MVF verification,
    and ClickHouse table checks. Troubleshooting table covers the 7 listed symptoms.
  </done>
</task>

<task type="auto">
  <name>Task 2: Cross-link runbook from feature doc, docs README, and write dev log</name>
  <files>docs/features/wallet-discovery-v1.md, docs/README.md, docs/dev_logs/2026-04-10_wallet_discovery_v1_operator_runbook.md</files>
  <action>
**A) Update docs/features/wallet-discovery-v1.md:**
Add a "Runbook" section (or "Operator Guide" section) after the "CLI Surface" section
and before "Human Review Gate". Content:

```markdown
---

## Operator Runbook

[Wallet Discovery v1 Operator Runbook](../runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md) —
step-by-step guide covering prerequisites, Loop A discovery, quick scan with MVF,
human review gate, and troubleshooting.
```

**B) Update docs/README.md:**
In the "Workflows" section, add an entry after the "Runbook: Scan-first manual workflow"
line:

```markdown
- [Wallet Discovery v1 Operator Runbook](runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md) - Loop A leaderboard discovery, quick scan with MVF, human review gate
```

**C) Create docs/dev_logs/2026-04-10_wallet_discovery_v1_operator_runbook.md:**
Mandatory dev log. Content:
- Date: 2026-04-10
- Task: quick-260410-iif
- Type: Docs-only
- What was done: Created operator runbook for Wallet Discovery v1, cross-linked from
  feature doc and docs README.
- Files changed: list the 3 files (runbook, feature doc, README).
- Files NOT changed: no code, tests, infra, or migrations.
- Codex review: Skip (docs-only).
  </action>
  <verify>
    <automated>python -c "
ft = __import__('pathlib').Path('docs/features/wallet-discovery-v1.md').read_text()
assert 'WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK' in ft, 'Feature doc missing runbook link'
rt = __import__('pathlib').Path('docs/README.md').read_text()
assert 'WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK' in rt, 'README missing runbook link'
dl = __import__('pathlib').Path('docs/dev_logs/2026-04-10_wallet_discovery_v1_operator_runbook.md')
assert dl.exists(), 'Dev log missing'
print('PASS: all cross-links and dev log present')
"</automated>
  </verify>
  <done>
    Feature doc has a Runbook section linking to the runbook.
    docs/README.md Workflows section lists the runbook.
    Dev log exists at docs/dev_logs/2026-04-10_wallet_discovery_v1_operator_runbook.md.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

No trust boundaries applicable — this is a docs-only plan with no code changes,
no API endpoints, no credential handling, and no data flow modifications.

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| (none) | N/A | docs-only | accept | No code or infra changes; no attack surface |
</threat_model>

<verification>
1. Runbook file exists at `docs/runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md`
2. Runbook contains all 8 required sections (Purpose through Related Docs)
3. All commands in the runbook are syntactically correct and copy-pasteable
4. Feature doc links to runbook
5. docs/README.md Workflows section links to runbook
6. Dev log exists
7. No code, test, infra, or migration files were modified
</verification>

<success_criteria>
An operator can open the runbook and follow it end-to-end to:
  (a) verify prerequisites (ClickHouse tables exist, env vars set),
  (b) run a dry-run Loop A discovery,
  (c) run a live Loop A discovery,
  (d) run a quick scan with MVF on a discovered wallet,
  (e) confirm MVF was appended to dossier.json,
  (f) understand the human review gate,
  (g) troubleshoot common failures,
all without referencing any other document.
</success_criteria>

<output>
After completion, create `.planning/quick/260410-iif-create-a-practical-operator-runbook-for-/260410-iif-SUMMARY.md`
</output>
