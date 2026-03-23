# Dev Log: Hypothesis Validation Loop v0 - Packet 1 Packaging Fix

**Date:** 2026-03-11
**Branch:** phase-1
**Track:** Track B - Research Loop

---

## Summary

Closed the remaining Packet 1 blocker for final acceptance: hypothesis schema loading is package-local at runtime, and the acceptance smoke now proves the schema ships in the built package.

`packages/polymarket/hypotheses/validator.py` already loads `hypothesis_schema_v1.json` with `importlib.resources`, so runtime validation no longer depends on `docs/specs/`. The remaining acceptance gap was the smoke test: it only staged source files plus a `pyproject.toml` assertion, which did not prove the built distribution actually carried the schema resource.

Packet 1 now has a stronger guard that builds the wheel from a temp project copy, extracts the installed contents, and validates a minimal hypothesis document from that extracted install root while running outside the source checkout.

---

## Canonical Schema Copy

Canonical runtime copy:
- `packages/polymarket/hypotheses/hypothesis_schema_v1.json`

Documentation mirror retained:
- `docs/specs/hypothesis_schema_v1.json`

Runtime code depends only on the package-local copy. The docs copy remains a human-facing mirror and must be kept in sync.

---

## Implementation

### Runtime/package loading

No runtime code change was needed in this pass:
- `validator.py` already loads the schema via `importlib.resources.files(...).joinpath(...).read_text(...)`
- `pyproject.toml` already declares the schema as package data for `packages.polymarket.hypotheses`
- `llm-save` artifact behavior remains unchanged

### `tests/test_hypothesis_validator.py`

Replaced the weaker staged-source smoke with an installed-package smoke that:
- copies the project into a temp build root,
- builds a wheel with `setuptools.build_meta.build_wheel(...)`,
- asserts the wheel contains `packages/polymarket/hypotheses/hypothesis_schema_v1.json`,
- extracts the wheel into an install root,
- runs a subprocess from outside the checkout with `PYTHONPATH` pointing at that extracted install root,
- imports `packages.polymarket.hypotheses.validator` and validates a minimal hypothesis document.

This fails if the schema resource is absent from the packaged build, which is the actual Packet 1 blocker.

---

## Scope Notes

Did NOT touch:
- Track A
- Gate 2
- Packet 2 work
- `llm-save` artifact layout or persistence behavior

---

## Files Changed

- `tests/test_hypothesis_validator.py`
- `docs/dev_logs/2026-03-11_hypothesis_validation_loop_v0_packet1_packaging_fix.md`

---

## Commands Run

```bash
pytest -q tests/test_hypothesis_validator.py
pytest -q tests/test_hypothesis_validator.py tests/test_llm_save.py tests/test_hypotheses_cli.py tests/test_polytool_main_module_smoke.py
```

---

## Test Results

Requested acceptance command:

```bash
pytest -q tests/test_hypothesis_validator.py tests/test_llm_save.py tests/test_hypotheses_cli.py tests/test_polytool_main_module_smoke.py
```

Result:
- 83 passed
- `tests/test_hypothesis_validator.py`: 60 passed
- `tests/test_llm_save.py`: 9 passed
- `tests/test_hypotheses_cli.py`: 7 passed
- `tests/test_polytool_main_module_smoke.py`: 7 passed

---

## Acceptance Status

Packet 1 is ready for final acceptance on the requested scope.