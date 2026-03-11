# Report -> SimTrader Payload Example (2026-03-06)

## Purpose

This note turns
`docs/dev_logs/2026-03-06_report_to_sim_handoff.md`
into one small concrete handoff contract for triggering SimTrader Gate 2 prep.

It is intentionally narrow:

- one normalized payload
- one market candidate
- no dossier redesign
- no automation-plan expansion

## Contract

One payload represents one candidate market to hand to a Gate 2 prep consumer.

### Minimum required field

| Field | Type | Why it is required |
|---|---|---|
| `market_slug` | string | Canonical market key. A `prepare-gate2` style consumer can resolve the market and paired token IDs from this slug internally. |

### Optional but helpful fields

| Field | Type | Why it helps |
|---|---|---|
| `schema_version` | string | Optional version marker for future tooling compatibility. |
| `market_title` | string | Human verification before recording or prep. |
| `source_type` | string | Provenance marker such as `dossier`, `bundle`, or `report`. |
| `source_path` | string | Exact artifact path used to produce the handoff. |
| `source_run_id` | string | Stable provenance across follow-on steps. |
| `source_generated_at_utc` | string | Freshness / staleness check for the source artifact. |
| `observed_at_utc` | string | Timestamp of the specific evidence row or mention, if available. |
| `source_user_slug` | string | User-level provenance. |
| `source_wallet` | string | Wallet-level provenance when the source came from a dossier/export. |
| `priority_rank` | integer | Ordering hint when multiple markets are surfaced. |
| `priority_reason` | string | Short explanation for why the market was surfaced. |
| `confidence_label` | string | Lightweight confidence hint such as `high`, `medium`, or `low`. |
| `yes_token_id` | string | Optional enrichment. Include when already known. |
| `no_token_id` | string | Optional enrichment. Include when already known. |

## Important rule

`market_slug` is required.

`yes_token_id` and `no_token_id` may be omitted when the SimTrader prep
consumer resolves them internally from `market_slug`.

If the payload is meant to drive direct `simtrader record` execution without a
slug-resolution step, both token IDs must be present.

## Concrete JSON example

```json
{
  "schema_version": "report_to_sim_payload_v1",
  "market_slug": "will-there-be-between-10-and-13-us-strikes-on-somalia-in-february-2026",
  "market_title": "Will there be between 10 and 13 US strikes on Somalia in February 2026?",
  "source_type": "dossier",
  "source_path": "artifacts/dossiers/users/anoin123/.../dossier.json",
  "source_run_id": "a5a3e49c-8b79-4b46-acdf-147010f7161d",
  "source_generated_at_utc": "2026-02-20T22:37:57Z",
  "observed_at_utc": "2026-02-20T02:24:48Z",
  "source_user_slug": "anoin123",
  "source_wallet": "0x96489abcb9f583d6835c8ef95ffc923d05a86825",
  "priority_rank": 1,
  "priority_reason": "top_by_total_pnl_net",
  "confidence_label": "medium"
}
```

This example is sufficient for Gate 2 prep as long as the receiving consumer
resolves YES/NO token IDs from `market_slug` before any direct tape capture.
