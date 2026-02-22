# Feature: Scan Full-By-Default + Full/Lite Profiles

PolyTool scan now behaves as a one-command workflow: when you run `scan` without any stage flags, it automatically runs the full research pipeline so the standard trust artifacts and reports are emitted in one pass.

## Defaulting Rules

- If no stage flags are passed, scan enables the full stage profile.
- If any stage flags are passed explicitly, scan does not auto-enable additional stages.
- `--full` forces the full stage profile, even if explicit stage flags are also present.
- `--lite` forces a minimal fast stage profile and does not enable extra ingestion stages.

## Stage Profiles

Full profile:
- `--ingest-markets`
- `--ingest-activity`
- `--ingest-positions`
- `--compute-pnl`
- `--compute-opportunities`
- `--snapshot-books`
- `--enrich-resolutions`
- `--warm-clv-cache`
- `--compute-clv`

Lite profile:
- `--ingest-positions`
- `--compute-pnl`
- `--enrich-resolutions`
- `--compute-clv`

## Precedence

1. `--full` (highest)
2. `--lite`
3. Explicit stage flags
4. No stage flags => full default

## Examples

Full by default (no stage flags):

```bash
python -m polytool scan --user "@example"
```

Respect explicit stage selection:

```bash
python -m polytool scan --user "@example" --ingest-positions
```

Force full even with explicit stage flags:

```bash
python -m polytool scan --user "@example" --ingest-positions --full
```

Force lite:

```bash
python -m polytool scan --user "@example" --lite
```
