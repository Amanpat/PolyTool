---
title: "pmxt SDK Operational Gotchas"
freshness_tier: CURRENT
confidence_tier: PRACTITIONER
validation_status: UNTESTED
source_family: external_knowledge
source_quality_caution: >
  Practitioner guidance derived from LEARNINGS.md and contributor notes in the
  hermes-pmxt repo snapshot. Attribute claims to that source, not to official
  pmxt documentation. Behavior may differ across pmxt versions.
---

# pmxt SDK Operational Gotchas

## Overview

This document captures empirical pitfalls from pmxt SDK usage in PolyTool's research
pipeline. It is a distilled practitioner note, not an official SDK specification.
All behaviors below were observed in the hermes-pmxt repo and associated LEARNINGS.md
at a specific point in time.

## API Reliability Issues

**`fetch_market(market_id=...)` is unreliable.** This method was reported as broken or
inconsistently returning results. Do not rely on it for production market lookup.

**Slug-based lookups may time out or return empty results.** Keyword-based search
(`search_markets(keyword=...)`) was the more reliable lookup path in the cited notes.
Prefer keyword search over slug resolution when robustness matters.

## Order Creation Requirements

Order creation requires both `market_id` and `outcome_id`. Outcome identifiers are long
opaque strings — they cannot be inferred from market slugs or outcome names. Retrieve
them programmatically from the market metadata before constructing any order payload.

## Price Scale Normalization

pmxt normalizes prices to the 0–1 scale across all connected exchanges, even when
a venue (e.g., Kalshi) natively uses a cents-based scale. Code that reads pmxt
prices should not apply additional normalization unless targeting the raw venue API.

## Sidecar Process Behavior

The pmxt sidecar runs as a persistent local process:
- **Default port**: 3847
- **Auto-start**: launches on first call from any Python process
- **Singleton behavior**: shared across Python processes on the same machine
- **State files**: lock files and log files under `~/.pmxt/`

If the sidecar crashes or locks, clear `~/.pmxt/` state and restart. Multiple
concurrent scripts hitting the sidecar simultaneously may produce race conditions
on lock acquisition.

## Practical Market Matching Baseline

The practical baseline for matching markets across platforms is Jaccard word similarity
with a 40% threshold. This catches most obvious matches but has a known failure mode:
shared keywords across unrelated events produce false positives. See
`cross_platform_market_matching.md` for a fuller treatment.

## Arbitrage Caution

The empirical finding from the cited notes: **true arbitrage is rare.** Observed price
gaps are frequently noise, matching errors, or structural differences rather than
exploitable dislocations. Do not treat any gap detected by a pmxt scan as a confirmed
arb opportunity without structural validation.

## Replacement for Some Use Cases

For other-wallet analytics (profile lookups, trade history), direct Polymarket REST
profile endpoints can sometimes replace pmxt entirely, reducing sidecar dependency.
Evaluate the tradeoff for each use case before defaulting to the sidecar path.
