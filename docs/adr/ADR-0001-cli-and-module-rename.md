# ADR-0001: CLI and Module Rename (polyttool -> polytool)

**Date**: 2026-02-05
**Status**: Accepted
**Deciders**: PolyTool maintainers

## Context

The original CLI and module name `polyttool` contains a typo (double 't'). This causes
confusion and makes the tool name harder to remember and type. The canonical name should
be `polytool` to match the repository name and common expectations.

## Decision

1. **Rename the primary package** from `polyttool/` to `polytool/`.
2. **Create a new console script entrypoint** named `polytool` as the canonical CLI.
3. **Keep `polyttool` as a deprecation shim** that:
   - Forwards all commands to `polytool`
   - Prints a deprecation warning once per invocation
   - Supports both `python -m polyttool` and `polyttool` console script
4. **Remove the shim** in version 0.2.0 or the first stable release, whichever comes first.

## Consequences

### Positive
- Clean, typo-free package name
- Easier to remember and type
- Matches repository name (`PolyTool`)

### Negative
- Temporary maintenance of two packages during transition
- Users of existing scripts need to update their commands

### Migration Path

1. **Immediate**: Both `polytool` and `polyttool` work identically.
2. **Warning period**: `polyttool` prints deprecation warning (current state).
3. **v0.2.0 or stable release**: `polyttool` package is removed.

Users should update their scripts to use:
```bash
# Instead of:
python -m polyttool <command>

# Use:
python -m polytool <command>
# or
polytool <command>
```

## Removal Timeline

The `polyttool` backward-compatibility shim will be removed when **either**:
- Version 0.2.0 is released, OR
- The first stable release (1.0.0) is published

Whichever comes first. At that point:
1. The `polyttool/` directory will be deleted
2. The `polyttool` console script entrypoint will be removed from `pyproject.toml`
3. All documentation will reference only `polytool`

## References

- `polytool/__init__.py`: Canonical package
- `polyttool/__init__.py`: Deprecation shim
- `pyproject.toml`: Console script definitions
