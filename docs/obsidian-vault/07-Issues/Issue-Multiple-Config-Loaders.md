---
type: issue
severity: low
status: open
tags: [issue, config, status/open]
created: 2026-04-08
---

# Issue: Multiple Config Loading Patterns

Source: audit Section 7.4.

At least three config loading patterns exist in the codebase.

---

## Current State

| Pattern | Files | Notes |
|---------|-------|-------|
| `simtrader/config_loader.py` | SimTrader CLI tools | Canonical — has BOM fix, UTF-8-sig, ConfigLoadError |
| `json.load(open(path))` direct | Various gate scripts | No BOM handling, no error context |
| `python-dotenv` `.env` loading | `polytool/__main__.py` | Only at entrypoint level |

---

## Risk

The canonical `config_loader.py` has a BOM fix (UTF-8-sig) that was added specifically because Windows-edited JSON files break on open. Gate scripts that use `json.load(open(path))` directly will silently break on BOM-prefixed files.

---

## Resolution

Prefer `config_loader.py` (via `load_json_from_path`) for all JSON config loading. The BOM fix matters on Windows.

---

## Cross-References

- [[SimTrader]] — `config_loader.py` is in `simtrader/`
- [[Gates]] — Gate scripts use the incorrect pattern

