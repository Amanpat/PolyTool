# Feature: Audit Coverage CLI

## What this does

When you run a Polymarket scan on your laptop, the tool writes several analysis
files to disk.  The `audit-coverage` command reads those files and produces a
short sanity-check report — without needing ClickHouse, a network connection,
or any other running service.  You can run it anywhere, any time, as long as
you have the scan artifacts folder.

The report has three parts: a **Quick Stats** summary (how many positions were
found, how well they are categorised, any fee or metadata gaps), a **Red Flags**
section that highlights the most common coverage problems automatically, and a
**Samples** section that shows a small, reproducible slice of positions so you
can eyeball the data quality directly.

---

## How to use it

Run the latest scan for a user, then audit it:

```bash
python -m polytool scan --user "@example"
python -m polytool audit-coverage --user "@example" --sample 25
```

The command prints the path to the report file and exits 0.

### Flags

| Flag          | Default | Purpose                                              |
|---------------|---------|------------------------------------------------------|
| `--sample N`  | 25      | How many positions to show in the Samples section.   |
| `--seed INT`  | 1337    | Seed for deterministic sampling (reproducible).      |
| `--run-id ID` | latest  | Audit a specific past run instead of the latest one. |
| `--output P`  | auto    | Write the report to a custom path.                   |
| `--format`    | `md`    | `md` for Markdown, `json` for machine-readable JSON. |

### Example: audit a specific older run

```bash
python -m polytool audit-coverage --user "@example" --run-id abc12345
```

---

## Where the report is saved

By default the report is written into the same folder as the scan artifacts:

```
artifacts/dossiers/users/<slug>/<wallet>/<YYYY-MM-DD>/<run_id>/audit_coverage_report.md
```

Use `--output <path>` to redirect it anywhere you like.

---

## Technical notes

- Reads: `run_manifest.json`, `dossier.json`,
  `coverage_reconciliation_report.json`, `segment_analysis.json`.
- All inputs are optional; missing files produce graceful "not found" notes.
- Sampling is deterministic: same `--seed` on the same artifacts always yields
  the same positions.  Resolved positions (WIN/LOSS/PROFIT_EXIT/LOSS_EXIT) are
  sampled before pending/unknown ones.
- See `docs/specs/SPEC-0007-audit-coverage-cli.md` for the full specification.
