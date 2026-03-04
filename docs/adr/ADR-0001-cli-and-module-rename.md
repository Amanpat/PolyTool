# ADR-0001: CLI and Module Rename (polyttool → polytool)

**Date**: 2026-02-05
**Status**: Completed (shim removed 2026-03-03)
**Deciders**: PolyTool maintainers

## Context

The original CLI and module name `polyttool` (double 't') contained a typo. This caused
confusion and made the tool name harder to remember and type. The canonical name is
`polytool` to match the repository name and common expectations.

## Decision

1. **Renamed the primary package** from `polyttool/` to `polytool/`.
2. **Created a new console script entrypoint** named `polytool` as the canonical CLI.
3. ~~**Keep `polyttool` as a deprecation shim**~~ — shim has been removed.
4. **Removed the shim**: `polyttool/` directory deleted, `polyttool` console script removed from `pyproject.toml`.

## Consequences

### Positive
- Clean, typo-free package name
- Easier to remember and type
- Matches repository name (`PolyTool`)

### Negative
- Temporary maintenance of two packages during transition
- Users of existing scripts needed to update their commands

### Migration Path (completed 2026-03-03)

1. ~~**Immediate**: Both `polytool` and `polyttool` worked identically.~~
2. ~~**Warning period**: `polyttool` printed deprecation warning.~~
3. **Done**: `polyttool` shim removed. Use `python -m polytool` or `polytool`.

## References

- `polytool/__init__.py`: Canonical package
- `pyproject.toml`: Console script definitions
