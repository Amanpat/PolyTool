# RIS + n8n Operator SOP Cheat Sheet

**Date:** 2026-04-09
**Scope:** Docs-only. No code, workflow JSON, Docker files, or tests were modified.

## What Was Created

- `docs/runbooks/RIS_N8N_OPERATOR_SOP.md` — New compact one-page operator SOP cheat sheet for the RIS+n8n pilot.

## What Was Updated (Cross-Reference Links)

Four existing docs received minimal cross-reference additions — one line or bullet each, no rewrites:

1. `docs/RIS_OPERATOR_GUIDE.md` — Added `> Quick reference:` callout at the top of the "n8n RIS Pilot (Opt-In)" section (after the scope boundary note).
2. `infra/n8n/README.md` — Added bullet to the "Related Docs" section.
3. `docs/README.md` — Added entry in the "Workflows" section after the "RIS n8n operator path" line.
4. `docs/runbooks/RIS_N8N_SMOKE_TEST.md` — Added bullet in the "Related Documentation" section.

## Source Material

The cheat sheet was distilled from:

- `docs/RIS_OPERATOR_GUIDE.md` lines 596–845 ("n8n RIS Pilot" section) — primary source of truth for all n8n commands.
- `infra/n8n/README.md` — n8n image details, workflow layout, import command.
- `docs/runbooks/RIS_N8N_SMOKE_TEST.md` — manual follow-up steps, troubleshooting patterns.

## Design Decisions

- Cheat sheet is command-driven and under 120 lines (115 lines). No prose paragraphs.
- Does not duplicate instructions from source docs — references them via the Related Docs table.
- Scoped-pilot boundary (ADR 0013) is stated in the header and the Common Mistakes section.
- Discord alert troubleshooting included because the connection between RIS LogSink and the polytool Discord module is a frequent point of confusion.
- The APScheduler / n8n double-scheduling risk is noted in both Startup and Common Mistakes (the two places operators are most likely to encounter it).

## Codex Review

Tier: Skip (docs-only, no execution code).
