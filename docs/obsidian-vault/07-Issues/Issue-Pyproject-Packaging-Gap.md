---
type: issue
severity: medium
status: open
tags: [issue, packaging, status/open]
created: 2026-04-08
---

# Issue: Pyproject Packaging Gap (RIS Subpackages)

Source: audit Section 1.2 and audit note 2.

Five research subpackages are not registered in `pyproject.toml`.

---

## Affected Subpackages

| Subpackage | Status in pyproject.toml |
|------------|--------------------------|
| `packages/research/evaluation/` | NOT REGISTERED |
| `packages/research/ingestion/` | NOT REGISTERED |
| `packages/research/integration/` | NOT REGISTERED |
| `packages/research/monitoring/` | NOT REGISTERED |
| `packages/research/synthesis/` | NOT REGISTERED |

**Registered:** `packages.research`, `packages.research.hypotheses`, `packages.research.scheduling`

---

## Impact

- `pip install -e .` will not correctly register the missing subpackages as Python packages
- They work in development via `sys.path` insertion but would fail on clean installs without the project root on the path
- Anyone doing `from packages.research.evaluation import evaluator` on a fresh install without the project root on `sys.path` would get an `ImportError`

---

## Resolution

Add the five missing subpackages to `pyproject.toml`'s `packages` list:
```toml
packages = [
    ...,
    {include = "packages/research/evaluation"},
    {include = "packages/research/ingestion"},
    {include = "packages/research/integration"},
    {include = "packages/research/monitoring"},
    {include = "packages/research/synthesis"},
]
```

---

## Cross-References

- [[RIS]] — Research Intelligence System with the missing subpackages

