# 2026-04-22 RIS WP1 Context Fetch

## Scope

Read-only repo inspection for RIS Phase 2A WP1-A through WP1-E.

Allowed write surface for this task: `docs/dev_logs/` only.

No application code, config, workflow, infra, or repo-state changes were made.

## Repo State Note

Unrelated local modifications were already present at session start:

```text
 M docs/obsidian-vault/.obsidian/workspace.json
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
```

They do not overlap this task and were not modified.

## Files And Commands Inspected

### Core evaluation surfaces

- `packages/research/evaluation/scoring.py`
- `packages/research/evaluation/config.py`
- `packages/research/evaluation/evaluator.py`
- `packages/research/evaluation/providers.py`
- `packages/research/evaluation/artifacts.py`
- `packages/research/evaluation/replay.py`
- `packages/research/evaluation/types.py`
- `packages/research/metrics.py`

### Ingestion / seed surfaces

- `packages/research/ingestion/seed.py`
- `packages/research/ingestion/pipeline.py`
- `packages/research/ingestion/fetchers.py`
- `tools/cli/research_seed.py`
- `tools/cli/research_stats.py`
- `tools/cli/research_acquire.py`
- `tools/cli/research_eval.py`
- `tools/cli/research_ingest.py`
- `polytool/__main__.py`

### Config / seed corpus / roadmap sources

- `config/seed_manifest.json`
- `config/seed_manifest_external_knowledge.json`
- `config/ris_eval_config.json`
- `config/freshness_decay.json`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/CURRENT_STATE.md`
- `docs/reference/RAGfiles/RIS_04_KNOWLEDGE_STORE.md`
- `docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md`
- `docs/reference/RAGfiles/RIS_07_INTEGRATION.md`
- `docs/obsidian-vault/Claude Desktop/09-Decisions/RIS_OPERATIONAL_READINESS_ROADMAP.md`
- `docs/obsidian-vault/Claude Desktop/09-Decisions/RIS_OPERATIONAL_READINESS_ROADMAP_v1.1.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Unified Open Source Integration Sprint.md`
- `docs/obsidian-vault/Claude Desktop/10-Session-Notes/2026-04-22 RIS Roadmap v1.1 Review.md`
- `docs/external_knowledge/*.md`

## Commands Run

### Multi-agent awareness / baseline

Command:

```powershell
git log --oneline -5
```

Output:

```text
a610f18 Hermes Agent containerization
05389a8 docs(quick-260422-ll0): PMXT Deliverable C close-out artifacts
0efd895 fix(ris): remove retriever over-fetch truncation for text_query path; Deliverable C gap1 fix
2d926c6 feat(ris): strip YAML frontmatter in heuristic claim extractor (v2)
5962d46 docs(simtrader): PMXT Deliverable B docs close-out
```

Command:

```powershell
python -m polytool --help
```

Relevant exact output:

```text
  research-eval             Evaluate a document through the RIS quality gate
  research-seed             Seed the RIS knowledge store from a manifest
  research-acquire          Acquire a source from URL and ingest into knowledge store
  research-stats            Operator metrics snapshot and local-first export for RIS pipeline
```

### CLI surface verification

Command:

```powershell
python -m polytool research-seed --help
```

Relevant exact output:

```text
usage: research-seed [-h] [--manifest PATH] [--db PATH] [--no-eval]
                     [--dry-run] [--reseed] [--json]
```

Command:

```powershell
python -m polytool research-stats --help
```

Relevant exact output:

```text
usage: research-stats [-h] SUBCOMMAND ...

positional arguments:
  SUBCOMMAND
    summary
    export
```

Command:

```powershell
python -m polytool research-acquire --help
```

Relevant exact output:

```text
usage: research-acquire [-h] [--url URL | --search QUERY] [--max-results N]
                        [--source-family FAMILY] ...
```

Command:

```powershell
python -m polytool research-eval
```

Exact output:

```text
research-eval: RIS document evaluation CLI

Subcommands:
  eval
  replay
  list-providers
```

### Current live RIS state

Command:

```powershell
python -m polytool research-stats summary --json
```

Exact output:

```json
{
  "generated_at": "2026-04-22T22:23:21+00:00",
  "total_docs": 48,
  "total_claims": 146,
  "docs_by_family": {
    "academic": 16,
    "blog": 16,
    "book": 1,
    "external_knowledge": 7,
    "github": 5,
    "manual": 3
  },
  "gate_distribution": {},
  "ingestion_by_family": {},
  "precheck_decisions": {
    "GO": 0,
    "CAUTION": 1,
    "STOP": 0
  },
  "reports_by_type": {
    "weekly_digest": 1
  },
  "total_reports": 1,
  "acquisition_new": 5,
  "acquisition_cached": 43,
  "acquisition_errors": 6,
  "provider_route_distribution": {},
  "provider_failure_counts": {},
  "review_queue": {
    "queue_depth": 1,
    "by_status": {
      "pending": 1
    },
    "by_gate": {
      "REVIEW": 1
    }
  },
  "disposition_distribution": {
    "ACCEPT": 0,
    "REVIEW": 0,
    "REJECT": 0,
    "BLOCKED": 0
  },
  "routing_summary": {
    "escalation_count": 0,
    "fallback_count": 0,
    "direct_count": 0,
    "total_routed": 0
  }
}
```

### Seed-manifest dry runs

Command:

```powershell
python -m polytool research-seed --dry-run --json
```

Relevant exact output:

```json
{
  "total": 11,
  "ingested": 0,
  "skipped": 0,
  "failed": 0,
  "dry_run": true,
  "reseed": false
}
```

Command:

```powershell
python -m polytool research-seed --manifest config/seed_manifest_external_knowledge.json --dry-run --json
```

Relevant exact output:

```json
{
  "total": 7,
  "ingested": 0,
  "skipped": 0,
  "failed": 0,
  "dry_run": true,
  "reseed": false
}
```

## Current State Summary

### High-level

- `docs/CURRENT_DEVELOPMENT.md` says the repo is currently on `WP1 Foundation Fixes` and points to the Obsidian roadmap as the authoritative Phase 2A plan.
- `research-seed` and `research-stats` are both actually wired in `polytool/__main__.py` and visible in `python -m polytool --help`.
- The default KnowledgeStore currently has `external_knowledge: 7` and `book_foundational: 0`.
- That means WP1-E-style external seeding has already happened in the live default store, but WP1-D foundational seed has not.

### Phase R0 seed sources live today

Current executable Phase R0 seed source is:

- `config/seed_manifest.json`

It resolves to 11 entries:

- `docs/reference/RAGfiles/RIS_OVERVIEW.md`
- `docs/reference/RAGfiles/RIS_01_INGESTION_ACADEMIC.md`
- `docs/reference/RAGfiles/RIS_02_INGESTION_SOCIAL.md`
- `docs/reference/RAGfiles/RIS_03_EVALUATION_GATE.md`
- `docs/reference/RAGfiles/RIS_04_KNOWLEDGE_STORE.md`
- `docs/reference/RAGfiles/RIS_05_SYNTHESIS_ENGINE.md`
- `docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md`
- `docs/reference/RAGfiles/RIS_07_INTEGRATION.md`
- `docs/archive/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md`
- `docs/archive/reference/POLYTOOL_MASTER_ROADMAP_v5.md`
- `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md`

Important mismatch:

- older RIS RAG docs still describe manual Phase R0 seeding of ~17 docs via `llm-save` / direct Chroma API / pseudo-command `polytool research seed-foundations`
- current repo truth is the 11-entry `research-seed` manifest above

### WP1-E seed docs live today

The repo already contains the distilled external docs as standalone markdown files:

- `docs/external_knowledge/polymarket_fee_structure_april2026.md`
- `docs/external_knowledge/pmxt_sdk_operational_gotchas.md`
- `docs/external_knowledge/sports_strategy_catalogue.md`
- `docs/external_knowledge/cross_platform_price_divergence_empirics.md`
- `docs/external_knowledge/simtrader_known_limitations.md`

Two additional companion docs also exist:

- `docs/external_knowledge/kalshi_fee_structure_april2026.md`
- `docs/external_knowledge/cross_platform_market_matching.md`

The external corpus is already formalized in:

- `config/seed_manifest_external_knowledge.json`

## Implementation Map

### WP1-A — scoring weights

| Surface | Exists | What it does now | Match vs roadmap | Likely change needed |
|---|---|---|---|---|
| `packages/research/evaluation/scoring.py` | Yes | Computes composite via config-backed weights and embeds old formula in prompt text: `0.30 / 0.25 / 0.25 / 0.20`. | No. Roadmap wants credibility-weighted `0.30 / 0.20 / 0.20 / 0.30`. | Edit `_compute_composite()` fallback constants and prompt text. |
| `packages/research/evaluation/config.py` | Yes | Default weights still `novelty=0.25`, `actionability=0.25`, `credibility=0.20`. | No. Runtime weights come from config loader, so roadmap file target is incomplete. | Edit defaults here too, not just `scoring.py`. |
| `config/ris_eval_config.json` | Yes | Persisted scoring weights still old values. | No. Even if `scoring.py` changes, this file still drives current runtime defaults. | Update JSON weights to new contract. |
| `docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - RIS Evaluation Scoring Policy.md` | Yes | Decision doc says composite is relevance 0.30, credibility 0.30, novelty 0.20, actionability 0.20. | Yes. | Use as the target contract. |

Conclusion:

- WP1-A is not a `scoring.py`-only change in current repo truth.
- Real edit set is at least `scoring.py + config.py + config/ris_eval_config.json`.

### WP1-B — per-dimension floors

| Surface | Exists | What it does now | Match vs roadmap | Likely change needed |
|---|---|---|---|---|
| `packages/research/evaluation/config.py` | Yes | Floors only `relevance=2`, `credibility=2`. | No. Roadmap wants novelty/actionability floor=2 added. | Add `novelty` and `actionability` to `_DEFAULT_FLOORS`, env handling as needed. |
| `config/ris_eval_config.json` | Yes | `scoring.floors` still only lists relevance and credibility. | No. | Add novelty/actionability floors here too. |
| `packages/research/evaluation/types.py` | Yes | Gate logic iterates over `cfg.floors.items()`. | Mostly yes. Engine already supports more floors if config changes. | Probably no logic change required; config expansion likely sufficient. |
| `packages/research/evaluation/scoring.py` | Yes | Prompt text says only relevance + credibility floors are required. | No. | Update prompt text so model sees the new floor contract. |

Conclusion:

- WP1-B is primarily config contract work; gate code already generalizes to extra floor keys.

### WP1-C — provider_event mismatch

| Surface | Exists | What it does now | Match vs roadmap | Likely change needed |
|---|---|---|---|---|
| `packages/research/metrics.py` | Yes | Reads `artifact.get("provider_events") or []`. | Matches roadmap expectation. | None if contract becomes plural list. |
| `packages/research/evaluation/artifacts.py` | Yes | `EvalArtifact` schema stores singular `provider_event`, not list. | No. | Decide whether artifact contract moves to `provider_events` list while preserving backward compatibility. |
| `packages/research/evaluation/evaluator.py` | Yes | Persists singular `provider_event=...` into artifacts. | No. | Not one-line in practice; artifact write path must change. |
| `packages/research/evaluation/replay.py` | Yes | Reads singular `provider_event`. | No if artifact contract changes. | Update replay loader/diff logic to plural contract or dual-read both forms. |
| `tools/cli/research_eval.py` | Yes | CLI JSON output and replay code read singular `provider_event`. | No if artifact contract changes. | Update eval/replay surfaces or support both names. |
| tests | Yes | Mixed expectations: some tests expect singular `provider_event`, others plural `provider_events`. | No. | Test contract reconciliation required. |

Conclusion:

- Current roadmap callout "one-line fix" is stale for current repo state.
- Real edit radius is at least `artifacts.py`, `evaluator.py`, `replay.py`, `research_eval.py`, tests, and maybe dual-read logic in `metrics.py` for old artifacts.

### WP1-D — run Phase R0 seed

| Surface | Exists | What it does now | Match vs roadmap | Likely change needed |
|---|---|---|---|---|
| `tools/cli/research_seed.py` | Yes | Manifest-driven seed CLI with `--manifest`, `--db`, `--no-eval`, `--dry-run`, `--reseed`, `--json`. Wired in CLI. | Mostly yes. | Operationally usable now. |
| `packages/research/ingestion/seed.py` | Yes | Loads manifest and runs batch seed into KnowledgeStore. | Yes. | No WP1 code change required to run it. |
| `config/seed_manifest.json` | Yes | 11-entry foundational manifest. | Partially. Roadmap still talks about Phase R0 more generally / older docs mention ~17 manual docs. | This is the actual current source of truth for runnable R0 seed. |
| `tools/cli/research_stats.py` | Yes | `summary` and `export` only; wired in CLI. | Yes for verification use. | Use `summary --json` for family counts. |

Important operational mismatch:

- `research-seed --help` says `--no-eval` is the default for seed.
- `tools/cli/research_seed.py` actually sets `skip_eval = args.no_eval`.
- Therefore plain `python -m polytool research-seed` does **not** skip eval by default in current code.

Current live state:

- default DB shows `book_foundational` absent
- dry-run of default manifest resolves 11 docs cleanly

Conclusion:

- WP1-D is still pending in the live default store.
- Safest current operator command is `python -m polytool research-seed --no-eval --json`, not the roadmap’s plain `research-seed`.

### WP1-E — seed open-source integration findings

| Surface | Exists | What it does now | Match vs roadmap | Likely change needed |
|---|---|---|---|---|
| `docs/external_knowledge/*.md` | Yes | Standalone markdown seed docs already exist for all five roadmap targets, plus two extras. | Exceeds roadmap. | No doc creation required unless regeneration is desired. |
| `config/seed_manifest_external_knowledge.json` | Yes | Formal 7-entry manifest for external knowledge seed corpus. | More mature than roadmap. | Current best reseed path. |
| `tools/cli/research_acquire.py` | Yes | URL/search acquisition only; source-family choices are `academic/github/blog/news/book/reddit/youtube`; provider choices `manual/ollama`. | No. Roadmap says use local `<path>` with `--source-family practitioner`. Current CLI does not support that. | Do not use as-written roadmap command. |
| `tools/cli/research_ingest.py` | Yes | Supports `--file PATH` and `--text`; viable for manual one-by-one local file ingest. | More realistic than roadmap acquire path. | Use for individual local docs if not using manifest seeding. |

Current live state:

- default DB already contains 7 `external_knowledge` docs:
  - Polymarket Fee Structure (April 2026)
  - Kalshi Fee Structure (April 2026)
  - pmxt SDK Operational Gotchas
  - Sports Strategy Catalogue
  - Cross-Platform Price Divergence Empirics
  - SimTrader Known Limitations (Verified)
  - Cross-Platform Market Matching

Conclusion:

- WP1-E appears already completed in current repo/store state, and beyond the roadmap’s 5-doc minimum.
- If re-seeding is required, current repo truth says use `research-seed --manifest config/seed_manifest_external_knowledge.json --no-eval` or `research-ingest --file ...`, not `research-acquire --url <path> --source-family practitioner`.

## Command Surface Check

### `research-seed` wired?

Yes.

Evidence:

- `polytool/__main__.py` defines `research_seed_main = _command_entrypoint("tools.cli.research_seed")`
- `_COMMAND_HANDLER_NAMES["research-seed"] = "research_seed_main"`
- `python -m polytool --help` lists `research-seed`
- `python -m polytool research-seed --help` returns argparse help successfully

### `research-stats` wired?

Yes.

Evidence:

- `polytool/__main__.py` defines `research_stats_main = _command_entrypoint("tools.cli.research_stats")`
- `_COMMAND_HANDLER_NAMES["research-stats"] = "research_stats_main"`
- `python -m polytool --help` lists `research-stats`
- `python -m polytool research-stats --help` returns argparse help successfully

### Actual shipped subcommands

- `research-stats` currently ships only `summary` and `export`
- older docs still mention `docs` / `claims` subcommands, but those are not present in current CLI

## WP1-E Source Mapping

### Immediate current source files

If the next session wants the actual five WP1-E docs to seed or reseed, the current file locations are:

- `docs/external_knowledge/polymarket_fee_structure_april2026.md`
- `docs/external_knowledge/pmxt_sdk_operational_gotchas.md`
- `docs/external_knowledge/sports_strategy_catalogue.md`
- `docs/external_knowledge/cross_platform_price_divergence_empirics.md`
- `docs/external_knowledge/simtrader_known_limitations.md`

### Most likely upstream repo / vault sources

- `Polymarket Fee Structure (April 2026)`
  - current file: `docs/external_knowledge/polymarket_fee_structure_april2026.md`
  - upstream notes: `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Unified Open Source Integration Sprint.md`
  - likely companion packet: `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Fee Model Maker-Taker + Kalshi.md`

- `pmxt SDK Operational Gotchas`
  - current file: `docs/external_knowledge/pmxt_sdk_operational_gotchas.md`
  - upstream notes: `docs/obsidian-vault/Claude Desktop/08-Research/09-Hermes-PMXT-Deep-Dive.md`
  - cited external source in notes: hermes-pmxt `LEARNINGS.md`

- `Sports Strategy Catalogue`
  - current file: `docs/external_knowledge/sports_strategy_catalogue.md`
  - upstream notes: `docs/dev_logs/2026-04-21_deliverable-b_reference-extract.md`
  - packet context: `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Unified Open Source Integration Sprint.md`

- `Cross-Platform Price Divergence Empirics`
  - current file: `docs/external_knowledge/cross_platform_price_divergence_empirics.md`
  - upstream notes: `docs/obsidian-vault/Claude Desktop/12-Ideas/Idea - Cross-Platform Price Divergence as RIS Signal.md`
  - cited external source in notes: AhaSignals March 2026 tracker (still secondary / caution-heavy)

- `SimTrader Known Limitations (Verified)`
  - current file: `docs/external_knowledge/simtrader_known_limitations.md`
  - upstream evidence: local SimTrader code inspection plus external comparison notes
  - likely upstream note bucket: `docs/obsidian-vault/Claude Desktop/08-Research/07-Backtesting-Repo-Deep-Dive.md`

## Mismatches Vs Roadmap

1. WP1-A is not a `scoring.py`-only fix anymore. Current runtime weights also live in `packages/research/evaluation/config.py` and `config/ris_eval_config.json`.

2. WP1-C is not a one-line rename in current repo truth. The singular/plural artifact contract touches evaluator, artifact schema, replay, CLI output, metrics, and tests.

3. WP1-D roadmap says `python -m polytool research-seed`. Current CLI help implies no-eval default, but current code does not actually skip eval unless `--no-eval` is passed.

4. WP1-D verification target is not yet satisfied in the live default store. `research-stats summary --json` shows `external_knowledge: 7` but no `book_foundational`.

5. WP1-E roadmap command is stale. Current `research-acquire` does not accept local file paths or `practitioner` as a source family.

6. WP1-E content is already present in current repo state as `docs/external_knowledge/*.md` and already ingested into the default store.

7. Phase R0 public/reference docs still describe older manual or pseudo-command seeding flows; current executable repo truth is manifest-driven `research-seed`.

## Blockers / Unknowns

1. `research-seed` default behavior mismatch:
   - help text suggests seed defaults to no-eval
   - actual code does not
   - next code session should decide whether to fix code/defaults before running WP1-D or simply use `--no-eval`

2. `provider_event` contract ambiguity:
   - roadmap expects plural `provider_events`
   - phase 5 artifact schema and CLI replay still use singular `provider_event`
   - next code session must choose whether to:
     - migrate fully to plural list and keep backward-compat reads, or
     - dual-write singular + plural temporarily

3. external-knowledge seeding already happened:
   - roadmap still lists WP1-E as pending 5-doc ingest
   - current default DB already has 7 external docs
   - next session should explicitly decide whether WP1-E is:
     - already done
     - done but needs verification only
     - done but should be re-seeded from manifest for reproducibility

4. stale operator docs around `research-stats`:
   - some docs mention `docs` / `claims` subcommands
   - current shipped CLI only has `summary` / `export`
   - not a WP1 blocker, but easy source of confusion during verification

5. Phase R0 corpus scope drift:
   - roadmap/reference prose still mentions ~17 foundational docs
   - current runnable manifest is 11 docs
   - next session should treat the 11-entry manifest as executable truth unless directed otherwise

## Recommended First Implementation Order

1. WP1-C decision first, before editing code:
   - choose the artifact contract (`provider_events` list with backward-compatible reads is the roadmap-aligned option)
   - because this affects evaluator, replay, CLI output, metrics, and tests

2. WP1-A and WP1-B together:
   - update `packages/research/evaluation/config.py`
   - update `config/ris_eval_config.json`
   - update `packages/research/evaluation/scoring.py` prompt/composite text
   - this is one coherent scoring-contract pass

3. WP1-D next:
   - either fix `research-seed` default no-eval behavior or run with explicit `--no-eval`
   - verify with `python -m polytool research-stats summary --json`
   - success criterion in current store: `docs_by_family.book_foundational >= 11`

4. WP1-E after that, but only if explicitly needed:
   - current likely action is verification or reseed, not doc creation
   - use `config/seed_manifest_external_knowledge.json` or `research-ingest --file`, not `research-acquire --url <path> --source-family practitioner`

5. Only after the above, decide whether any doc-surface truth sync is required:
   - `CURRENT_DEVELOPMENT`
   - roadmap note
   - operator docs / runbooks

## Recommended Next Session Starting Point

If the next session is an implementation session, the cleanest first move is:

1. reconcile WP1-C artifact contract
2. land WP1-A + WP1-B in one scoring-config pass
3. run `python -m polytool research-seed --no-eval --json`
4. verify `book_foundational` count with `python -m polytool research-stats summary --json`
5. treat WP1-E as verification/reseed only unless directed otherwise

