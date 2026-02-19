# Feature: README Roadmap 4 Runbook

## What this does

The project now has a root `README.md` that serves as the practical working
guide for Roadmap 4.  Before this change there was no top-level README, so a
new contributor (or your future self on a different machine) had no single
place to learn what commands to run, where outputs land, or how to handle
common Windows-specific issues.

The README is intentionally command-first: copy-paste the four numbered steps
and you go from a cold Docker install to a full coverage audit and LLM bundle
in under ten minutes.

---

## What changed

### Created: `README.md` (root)

Five sections written from the Roadmap 4 working runbook:

1. **Quickstart (Local)** — step-by-step commands:
   - `docker compose up -d` + `curl` ping on port 8123
   - Canonical scan command with `--ingest-positions`, `--compute-pnl`,
     `--enrich-resolutions`, `--debug-export`
   - `audit-coverage` command (with `--seed` example and `--format json`)
   - `llm-bundle` with a note that it works without RAG

2. **Outputs / Where files go** — explains the run-root path format
   (`artifacts/dossiers/users/<slug>/<wallet>/<YYYY-MM-DD>/<run_id>/`) and
   lists every trust artifact with a one-line description.

3. **Configuration** — `polytool.yaml` examples for `segment_config` entry
   price tiers and `fee_config.profit_fee_rate`.

4. **Troubleshooting (Windows)** — `localhost` vs `127.0.0.1` (IPv6 resolution
   issue on Windows), port map (8123/9000/8000/3000), and `positions_total = 0`
   triage checklist.

5. **Repository layout** and **Infrastructure commands** reference sections.

### Created: `docs/features/FEATURE-readme-roadmap4-runbook.md`

This file.
