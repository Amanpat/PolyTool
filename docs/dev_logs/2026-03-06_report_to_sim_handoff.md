# Report -> SimTrader Handoff (2026-03-06)

## Scope

This note checks whether current dossier / bundle / report outputs can feed the
SimTrader prep flow cleanly for:

1. candidate market selection
2. tape capture
3. Gate 2 preparation

This is an interface-contract check only. It does not change report logic,
scanner logic, recorder logic, or strategy logic.

## Artifacts inspected

Real artifact paths inspected from the repo:

- `artifacts/dossiers/users/anoin123/0x96489abcb9f583d6835c8ef95ffc923d05a86825/2026-02-20/a5a3e49c-8b79-4b46-acdf-147010f7161d/dossier.json`
- `artifacts/dossiers/users/anoin123/0x96489abcb9f583d6835c8ef95ffc923d05a86825/2026-02-20/a5a3e49c-8b79-4b46-acdf-147010f7161d/run_manifest.json`
- `artifacts/dossiers/users/anoin123/0x96489abcb9f583d6835c8ef95ffc923d05a86825/2026-02-20/a5a3e49c-8b79-4b46-acdf-147010f7161d/segment_analysis.json`
- `artifacts/dossiers/users/anoin123/0x96489abcb9f583d6835c8ef95ffc923d05a86825/2026-02-20/a5a3e49c-8b79-4b46-acdf-147010f7161d/memo.md`
- `kb/users/drpufferfish/llm_bundles/2026-03-05/890dc539/bundle.md`
- `kb/users/drpufferfish/llm_bundles/2026-03-05/890dc539/bundle_manifest.json`
- `kb/users/drpufferfish/reports/2026-03-05/890dc539_report.md`

Docs / code read for consumer expectations:

- `docs/dev_logs/2026-03-06_gate2_market_scanner.md`
- `docs/dev_logs/2026-03-06_gate2_tape_capture_playbook.md`
- `docs/dev_logs/2026-03-06_gate2_prep_orchestrator.md`
- `docs/specs/LLM_BUNDLE_CONTRACT.md`
- `docs/dev_logs/2026-03-05_llm_bundle_report_stub.md`
- `tools/cli/scan_gate2_candidates.py`
- `tools/cli/prepare_gate2.py`
- `tools/cli/simtrader.py`
- `packages/polymarket/simtrader/tape/recorder.py`

## What the SimTrader side actually expects

### Candidate market selection

The SimTrader prep flow ultimately selects markets by `slug`.

- `scan_gate2_candidates.CandidateResult` is keyed by `slug`
- `prepare_gate2.prepare_candidates()` consumes `candidate.slug`
- `simtrader quickrun --market <slug>` resolves the market from slug

Minimum machine need here: a market-level identifier that can be resolved by
`MarketPicker`. In practice that is `market_slug`.

### Tape capture

The current direct recorder flow is token-ID based:

```text
python -m polytool simtrader record --asset-id <YES> --asset-id <NO>
```

So direct recording needs both:

- `yes_token_id`
- `no_token_id`

However, the current operator playbook resolves those IDs from `market_slug`
first via:

```text
python -m polytool simtrader quickrun --dry-run --market <slug>
```

Conclusion: token IDs are not required for slug-driven prep, but they are
required if the handoff is expected to drive `simtrader record` directly.

### Gate 2 preparation

`prepare-gate2` can work from slug-only candidates because it resolves YES/NO
token IDs internally before recording. It also writes `prep_meta.json` with:

- `market_slug`
- `yes_asset_id`
- `no_asset_id`

Conclusion: the true minimum for Gate 2 prep is `market_slug`, but provenance
and freshness fields are needed so the operator knows what the candidate came
from and how stale it is.

## Fields found in current artifacts

### Dossier (`dossier.json`)

The inspected dossier is the only currently produced artifact that already has
usable structured market rows.

Present in inspected position rows:

- `market_slug`
- `question` (usable as market title)
- `outcome_name`
- `resolved_token_id`
- `entry_ts`
- `exit_ts`
- `close_ts`
- `resolution_outcome`
- `trade_count`
- `total_cost`
- `realized_pnl_net`

Present in dossier header:

- `export_id`
- `generated_at`
- `user_input`
- `proxy_wallet`
- `window_start`
- `window_end`

Observed counts in the inspected dossier run:

- `market_slug`: present on 50/50 positions
- `question`: present on 50/50 positions
- `resolved_token_id`: present on 50/50 positions
- `entry_ts`: present on 50/50 positions
- `close_ts`: present on 45/50 positions
- `category`: present on 0/50 positions in this specific run

Important limitation:

- the dossier has only the traded outcome token (`resolved_token_id`)
- it does not carry the paired market-level YES and NO token IDs
- it does not carry a direct market URL
- it does not carry `condition_id` in the inspected exported positions

### Run manifest (`run_manifest.json`)

Useful structured provenance exists here:

- `run_id`
- `user_slug`
- `started_at`
- `finished_at`
- `output_paths.dossier_json`
- `output_paths.dossier_path`
- `output_paths.coverage_reconciliation_report_json`
- `output_paths.segment_analysis_json`

This is good for source/run provenance but does not solve the token-ID gap.

### Segment analysis (`segment_analysis.json`)

This is the only inspected structured artifact already close to a market-level
ranking list.

Present:

- `segment_analysis.by_market_slug.top_by_total_pnl_net[]`
- `segment_analysis.by_market_slug.top_by_count[]`

Sample row shape:

- `market_slug`
- `count`
- `total_pnl_net`
- `win_rate`

This is useful for optional `priority_rank`, but it still lacks:

- `market_title`
- paired `yes_token_id` / `no_token_id`
- direct market URL

### Bundle (`bundle.md` + `bundle_manifest.json`)

Bundle artifacts are useful for provenance, not as the clean handoff object.

Present:

- `bundle_manifest.json.created_at_utc`
- `bundle_manifest.json.run_id`
- `bundle_manifest.json.user_slug`
- `bundle_manifest.json.dossier_path`
- `bundle.md` header with user / run / dossier path

Missing as structured fields:

- market-level candidate rows
- explicit per-market rank
- paired YES/NO token IDs
- market URLs

`bundle.md` embeds the dossier content, but only as Markdown text. That means a
consumer must re-parse human-facing content instead of reading a clean market
record.

### Report stub (`*_report.md`)

The report stub is not a machine handoff.

Present:

- `user_slug`
- `bundle_id`
- `generated_at`
- path to `bundle.md`
- path to `memo_filled.md`

Missing:

- market slug list
- market title list
- rank / priority
- token IDs
- market URLs
- structured per-market provenance

Current report output is therefore human-facing only.

## Minimum handoff contract

The smallest clean handoff is a normalized market-candidate record extracted
from existing structured artifacts, not a redesign of the report system.

### Required fields

| Field | Why it is required |
|---|---|
| `market_slug` | Canonical key for `quickrun --market` and `prepare-gate2` |
| `market_title` | Human verification; use dossier `question` |
| `source_type` | Distinguish `dossier`, `bundle`, or `report` origin |
| `source_path` | Trace back to the exact artifact used |
| `source_run_id` | Stable provenance across follow-on steps |
| `source_generated_at_utc` | Freshness / staleness check |
| `source_user_slug` | User provenance |

### Conditionally required fields

| Field | When it becomes required |
|---|---|
| `yes_token_id` | Required for direct `simtrader record` without a slug-resolution step |
| `no_token_id` | Required for direct `simtrader record` without a slug-resolution step |

### Optional but helpful fields

| Field | Why it helps |
|---|---|
| `priority_rank` | Lets reports suggest an order when multiple markets are mentioned |
| `priority_reason` | Explains why the market was surfaced |
| `source_wallet` | Extra provenance when the source is a dossier/export |
| `evidence_ts_utc` | Entry / mention timestamp if the candidate came from a specific position |
| `evidence_trade_uids` | Traceability back to concrete evidence rows |
| `market_url` | Operator convenience for manual inspection |
| `resolved_token_id` | Useful evidence, but not enough for recorder flow by itself |

### One important rule

`resolved_token_id` is not a substitute for `yes_token_id` + `no_token_id`.

It identifies the trader's resolved outcome token in the dossier. The recorder
and eligibility flow for binary complement markets needs the pair of market
tokens, not just the one side the user traded.

## Smallest clean format

This is the recommended minimal normalized shape:

```json
{
  "schema_version": "report_to_sim_handoff_v1",
  "candidates": [
    {
      "market_slug": "will-there-be-between-10-and-13-us-strikes-on-somalia-in-february-2026",
      "market_title": "Will there be between 10 and 13 US strikes on Somalia in February 2026?",
      "source_type": "dossier",
      "source_path": "artifacts/dossiers/users/anoin123/.../dossier.json",
      "source_run_id": "a5a3e49c-8b79-4b46-acdf-147010f7161d",
      "source_generated_at_utc": "2026-02-20T22:37:57Z",
      "source_user_slug": "anoin123",
      "source_wallet": "0x96489abcb9f583d6835c8ef95ffc923d05a86825",
      "priority_rank": 1,
      "priority_reason": "segment_analysis.by_market_slug.top_by_total_pnl_net",
      "yes_token_id": null,
      "no_token_id": null,
      "evidence_ts_utc": "2026-02-20T02:24:48Z"
    }
  ]
}
```

This is intentionally small:

- market identity
- provenance
- optional ranking
- optional direct recorder fields

Nothing here changes report scoring or report generation logic.

## Current gaps / mismatches

| Area | Current state | Gap |
|---|---|---|
| Market identifier | `market_slug` exists in dossier positions | Good |
| Market title | `question` exists in dossier positions | Good |
| Recorder token IDs | only `resolved_token_id` exists in dossier | Missing paired `yes_token_id` / `no_token_id` |
| Provenance | strong in dossier header and run manifest | Good |
| Freshness timestamp | available in dossier header / manifest | Good |
| Priority / rank | only indirectly available via `segment_analysis.by_market_slug` order | Needs normalization into explicit `priority_rank` if reports are to suggest order |
| Direct market URL | not present in inspected artifacts | Missing optional convenience field |
| Report output | report stub is Markdown only | Not sufficient as a direct machine handoff |
| Bundle output | provenance exists, but market rows are embedded Markdown | Not sufficient as a clean handoff object |

## Sufficiency verdict

Plainly:

- `dossier.json` is the right raw structured source for a report-to-SimTrader handoff.
- current `bundle.md` and `*_report.md` outputs are not sufficient as the handoff object.
- current artifacts are not clean end-to-end for direct tape capture because paired
  `yes_token_id` / `no_token_id` are missing.
- current artifacts are close enough for `prepare-gate2` only if a small
  normalization step extracts market-level rows and the consumer resolves token
  IDs from `market_slug`.

So the answer is:

- **Already sufficient without normalization?** No.
- **Need a full redesign?** No.
- **Smallest fix in contract terms:** normalize existing dossier market rows into
  a tiny market-candidate record, and treat YES/NO token IDs as optional
  enrichment unless the handoff must call `simtrader record` directly.

## Recommendation

Use the dossier run as the source of truth and define the handoff at the
market-candidate level, not at the free-form report level.

Recommended extraction path:

1. Start from `dossier.json.positions.positions[]`
2. Deduplicate by `market_slug`
3. Map `question` -> `market_title`
4. Carry provenance from `dossier.header` and `run_manifest.json`
5. Optionally attach `priority_rank` from `segment_analysis.by_market_slug`
6. Optionally attach `yes_token_id` / `no_token_id`; otherwise require the next
   step to resolve them from slug before direct recording

That is the minimum clean handoff contract.
