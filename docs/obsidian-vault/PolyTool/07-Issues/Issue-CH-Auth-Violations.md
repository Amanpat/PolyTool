---
type: issue
severity: high
status: open
tags: [issue, clickhouse, auth, status/open]
created: 2026-04-08
---

# Issue: ClickHouse Authentication Violations

Source: audit Section 7.2.

Four CLI files use a hardcoded password fallback, violating the CLAUDE.md ClickHouse authentication rule.

---

## CLAUDE.md Rule

> "Never use a hardcoded fallback like `polytool_admin`. Never silently default to empty string."
> "All CLI entrypoints that touch ClickHouse MUST read credentials from the `CLICKHOUSE_PASSWORD` environment variable with fail-fast behavior: `if not ch_password: sys.exit(1)`."

This rule exists because three separate auth-propagation bugs were shipped and debugged between 2026-03-18 and 2026-03-19.

---

## Correct Pattern (fail-fast)

```python
ch_password = os.environ.get("CLICKHOUSE_PASSWORD")
if not ch_password:
    sys.exit(1)
```

Files using correct pattern: `fetch_price_2min.py`, `close_benchmark_v1.py`, `batch_reconstruct_silver.py`

---

## Incorrect Pattern (silent fallback — violation)

```python
ch_password = os.environ.get("CLICKHOUSE_PASSWORD", "polytool_admin")
```

**Files with violations:**

| File | Impact |
|------|--------|
| `tools/cli/examine.py` | DEAD command, but still violates pattern |
| `tools/cli/export_dossier.py` | Active command |
| `tools/cli/export_clickhouse.py` | Active command |
| `tools/cli/reconstruct_silver.py` | Active command |

---

## Resolution

Replace all occurrences of the incorrect pattern with the fail-fast pattern. The fix is mechanical — copy from `fetch_price_2min.py` or `close_benchmark_v1.py`.

---

## Cross-References

- [[Database-Rules]] — ClickHouse/DuckDB one-sentence rule and auth requirement
- [[CLI-Reference]] — Affected CLI commands

