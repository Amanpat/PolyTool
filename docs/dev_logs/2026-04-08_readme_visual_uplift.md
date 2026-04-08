# README Visual Uplift

**Date:** 2026-04-08
**Scope:** docs-only (README.md + Obsidian vault companion)

## What Changed

- Added 3 Mermaid diagrams to `README.md`:
  - **System Map** (after intro, before "What Is Shipped Today")
  - **First-Time Operator Path** (after Configuration, before Quick Workflows)
  - **Infrastructure Map** (after Operator Surfaces table, before Project Structure)
- Created `docs/obsidian-vault/01-Architecture/Visual-Maps.md` as the
  single-source companion for maintaining all 3 diagrams.

## Why

The README had no visual orientation. Three targeted diagrams give new
operators a quick mental model without bloating the text.

## Files Touched

- `README.md` -- 3 additive Mermaid insertions
- `docs/obsidian-vault/01-Architecture/Visual-Maps.md` -- new companion doc
- `docs/dev_logs/2026-04-08_readme_visual_uplift.md` -- this log

## Verification

- `grep -c '```mermaid' README.md` returns `3`
- No code, config, or test files modified
