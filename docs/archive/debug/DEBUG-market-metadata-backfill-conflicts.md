# Debug: Market Metadata Backfill Conflicts

## What is a metadata conflict?

A metadata conflict occurs when two positions in the same dossier share the same
identifier (`token_id`, `resolved_token_id`, or `condition_id`) but carry
**different** values for at least one of `market_slug`, `question`, or
`outcome_name`.

PolyTool resolves conflicts deterministically by keeping the **first** entry
encountered.  The conflict is counted and (up to 5 examples) surfaced in the
coverage report so you can investigate.

---

## How to spot conflicts

**JSON report** — check `market_metadata_coverage`:

```json
"market_metadata_coverage": {
    "metadata_conflicts_count": 3,
    "metadata_conflict_sample": [
        {
            "identifier": "0xabc...",
            "first": {
                "market_slug": "slug-a",
                "question": "Who wins?",
                "outcome_name": "Team A"
            },
            "second": {
                "market_slug": "slug-b",
                "question": "Who wins?",
                "outcome_name": "Team A"
            }
        }
    ]
}
```

**Markdown report** — look for a blockquote warning in the
"Market Metadata Coverage" section:

```
> **Warning:** 3 metadata map collision(s) detected (same token/condition ID
> found with different values — first entry kept). See `metadata_conflict_sample`
> in JSON report for details.
```

---

## Common causes

| Cause | What to look for |
|-------|-----------------|
| Duplicate rows in export | Same `token_id` appears twice with different `market_slug` |
| Re-tokenised markets | Polymarket issued a new token for an existing market; both old and new rows are present |
| Proxy-wallet merge | Two wallets traded in the same market and their dossiers were merged |
| Data quality issue upstream | The export endpoint returned inconsistent metadata for the same token |

---

## How to investigate

1. **Identify the conflicting identifier** from `metadata_conflict_sample[].identifier`.

2. **Find all rows** in the raw dossier JSON that share that identifier:

   ```python
   identifier = "0xabc..."
   conflicting = [p for p in positions if p.get("token_id") == identifier]
   for row in conflicting:
       print(row.get("market_slug"), row.get("question"), row.get("outcome_name"))
   ```

3. **Check the first vs second values** in the sample.  If `market_slug` differs,
   the two rows are likely from different markets sharing a token (very unusual).
   If only `outcome_name` differs, this may be a normalisation discrepancy
   (e.g. `"Yes"` vs `"YES"`).

4. **Decide if the conflict matters** for your analysis:

   - If only whitespace/case differs — safe to ignore; both map to the same market.
   - If `market_slug` differs — investigate the raw export; this is a data anomaly.

5. **Re-run with `--debug-export`** to get additional hydration diagnostics:

   ```powershell
   python -m polytool scan --user "@example" --debug-export
   ```

---

## Conflict resolution policy

PolyTool always keeps the **first** mapping encountered for any given identifier
and never overwrites it.  This is intentional:

- **Deterministic** — same input always produces same output.
- **Conservative** — the first occurrence is typically the canonical record.
- **Auditable** — the conflict count and sample are preserved in the report
  so you can see exactly what was discarded.

If you need to override this behaviour, pre-process your dossier to deduplicate
positions before running `scan`.

---

## condition_id conflicts and outcome_name

Because `condition_id` identifies a **market** (not a specific outcome token),
backfill via `condition_id` never populates `outcome_name` even when the mapping
carries one.  This means:

- A conflict on a `condition_id`-mapped position will not affect `outcome_name`.
- `first` and `second` in the conflict sample may show `outcome_name` values —
  these are the raw map entries, but neither value would have been applied.

See [SPEC-0005](../specs/SPEC-0005-market-metadata-backfill.md) for the full
identifier priority and restriction rules.
