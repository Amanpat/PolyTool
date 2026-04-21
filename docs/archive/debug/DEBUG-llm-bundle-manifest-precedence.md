# Debug Note: llm-bundle dossier manifest precedence

## Context

`polytool llm-bundle` must read dossier metadata from either:

- `run_manifest.json` (new canonical filename)
- `manifest.json` (legacy filename)

## Decision

Manifest resolution is explicit and deterministic:

1. Check `<run_root>/run_manifest.json` first.
2. Fall back to `<run_root>/manifest.json`.
3. If neither exists, raise a `FileNotFoundError` that lists both expected full paths and suggests running `export-dossier` or `scan`.

When multiple dossier runs exist, run selection remains deterministic through the existing manifest sort key (timestamp, then path).
