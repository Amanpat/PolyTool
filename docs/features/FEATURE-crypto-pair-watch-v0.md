# Feature: Crypto Pair Market Availability Watcher v0

## Purpose

The crypto pair market availability watcher gives the Track 2 operator a
lightweight, artifact-producing command to check whether eligible BTC/ETH/SOL
5m/15m binary markets exist on Polymarket right now, and to optionally poll
until they appear. This closes the operational gap between `crypto-pair-scan`
(which requires live markets) and the current state where Polymarket has zero
active crypto pair markets.

## When to Use

Run `crypto-pair-watch` when:
- You suspect markets may be offline and want a quick eligibility status.
- You want to leave a watch loop running and be notified when markets rotate in.
- You want a dated artifact proving market availability was checked.

Run `crypto-pair-scan` only after `crypto-pair-watch` reports `eligible_now: yes`.

## CLI Usage

### One-shot check (default)

```bash
python -m polytool crypto-pair-watch
```

Example output when no markets exist:

```
[crypto-pair-watch] eligible_now : no
[crypto-pair-watch] total_eligible: 0
[crypto-pair-watch] by_symbol     : BTC=0 ETH=0 SOL=0
[crypto-pair-watch] by_duration   : 5m=0 15m=0
[crypto-pair-watch] checked_at    : 2026-03-25T22:00:00+00:00
[crypto-pair-watch] next_action   : Markets unavailable. Re-run later or use --watch --timeout 3600
[crypto-pair-watch] Bundle written: artifacts/crypto_pairs/watch/2026-03-25/<run_id>
```

One-shot mode always exits 0 (informational; not an error if markets are offline).

### Watch mode — poll until markets appear

```bash
python -m polytool crypto-pair-watch --watch --timeout 3600 --poll-interval 60
```

- Polls every 60 seconds for up to 1 hour.
- Exits 0 when eligible markets are found; prints eligible slugs and next-action.
- Exits 1 when the timeout elapses with no eligible markets found.

### Symbol and duration hints (reserved, v0)

```bash
python -m polytool crypto-pair-watch --symbol BTC --duration 5
```

The `--symbol` and `--duration` flags are accepted in v0 but do not filter the
underlying Gamma API query. All eligible markets (BTC, ETH, SOL / 5m, 15m) are
always returned. Per-symbol/duration filtering will be wired in a future release.

### Custom artifact directory

```bash
python -m polytool crypto-pair-watch --output /tmp/my-watch-artifacts
```

## Eligibility Rules

A market is eligible when all of the following are true:

1. `active=True` on the Gamma market record.
2. `accepting_orders` is not explicitly `False` (`True` or `None` are both OK).
3. Exactly 2 CLOB token IDs (binary market).
4. Symbol detected in question or slug: BTC/Bitcoin, ETH/Ethereum/Ether,
   SOL/Solana (case-insensitive, keyword match).
5. Duration detected in question or slug: 5m/5min/5 minute or 15m/15min/15 minute
   (keyword match).

Classification is delegated entirely to `discover_crypto_pair_markets` in
`packages/polymarket/crypto_pairs/market_discovery.py`. This module does NOT
fork the classifier.

## Artifact Schema

All artifacts are written to:
```
artifacts/crypto_pairs/watch/<YYYY-MM-DD>/<run_id>/
```

### watch_manifest.json

```json
{
  "artifact_dir": "artifacts/crypto_pairs/watch/2026-03-25/abc123def456",
  "generated_at": "2026-03-25T22:00:00+00:00",
  "mode": "one_shot",
  "run_id": "abc123def456",
  "summary_ref": "artifacts/crypto_pairs/watch/2026-03-25/abc123def456/availability_summary.json"
}
```

Fields:
- `run_id`: 12-char hex UUID fragment, unique per invocation.
- `generated_at`: ISO 8601 UTC timestamp of run start.
- `mode`: `"one_shot"` or `"watch"`.
- `summary_ref`: Absolute path to the availability_summary.json artifact.
- `artifact_dir`: Directory containing all artifacts for this run.

### availability_summary.json

```json
{
  "by_duration": {"15m": 0, "5m": 0},
  "by_symbol": {"BTC": 0, "ETH": 0, "SOL": 0},
  "checked_at": "2026-03-25T22:00:00+00:00",
  "eligible_now": false,
  "first_eligible_slugs": [],
  "rejection_reason": "No active BTC/ETH/SOL 5m/15m binary pair markets found",
  "total_eligible": 0
}
```

Fields:
- `eligible_now`: `true` when `total_eligible > 0`.
- `total_eligible`: Count of all eligible markets discovered.
- `by_symbol`: Per-symbol eligible count.
- `by_duration`: Per-duration eligible count.
- `first_eligible_slugs`: Up to 5 eligible market slugs (empty when none).
- `rejection_reason`: Human-readable explanation when `eligible_now=false`, else `null`.
- `checked_at`: ISO 8601 UTC timestamp of the availability check.

### availability_summary.md

Human-readable Markdown report with the same data, formatted as a table plus
next-action guidance and an assumptions section.

## Next-Action Guidance

| Condition | next_action |
|-----------|-------------|
| `eligible_now=true` | Run: `python -m polytool crypto-pair-scan` (then `crypto-pair-run` when ready) |
| `eligible_now=false` | Markets unavailable. Re-run later or use `--watch --timeout 3600` |

## Exit Codes

| Mode | Condition | Exit code |
|------|-----------|-----------|
| one-shot | Always | 0 |
| watch | Eligible markets found | 0 |
| watch | Timeout with no markets | 1 |
| any | Unexpected exception | 1 |

## Core Modules

| File | Role |
|------|------|
| `packages/polymarket/crypto_pairs/market_watch.py` | Core evaluator: `AvailabilitySummary`, `run_availability_check`, `run_watch_loop` |
| `tools/cli/crypto_pair_watch.py` | CLI entrypoint: argument parsing, printing, artifact writes |
| `tests/test_crypto_pair_watch.py` | 20+ offline tests, no network calls |

## Limitations (v0)

- `--symbol` and `--duration` flags do not filter the Gamma API query; they are
  reserved for future wiring. The underlying discovery always returns all
  eligible markets.
- Watch mode uses wall-clock time (monotonic); if the process is suspended or
  the system clock drifts, the timeout may not be perfectly accurate.
- There is no notification mechanism (no Discord hook) in v0; the operator must
  observe the process output or check artifacts manually.
- first_eligible_slugs is capped at 5; run `crypto-pair-scan` for the full list.
