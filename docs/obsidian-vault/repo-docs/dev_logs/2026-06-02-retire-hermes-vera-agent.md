---
title: Retire Hermes Vera Agent
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-06-02_retire-hermes-vera-agent.md
last_synced: '2026-06-03T02:26:56Z'
lifecycle: reviewed
generator: repo-sync
---

# Dev Log — Retire vera-hermes-agent (Hermes)

**Date:** 2026-06-02
**Slug:** retire-hermes-vera-agent
**Type:** Cleanup / retirement (docs + config + WSL ops; no execution-critical code)
**Decision record:** `docs/obsidian-vault/claude-memory/decisions/decision-retire-hermes-build-vera-bot.md`

## Objective

Retire the `vera-hermes-agent` (Hermes) operator agent. Hermes was a read-only,
natural-language Q&A agent over repo docs (3 skills: polytool-status / dev-logs /
files) on a flaky free model. It is isolated — no trading, no jobs, nothing
operational depends on it — so removal is low-risk. A purpose-built discord.py bot
reusing the name "Vera" (with real approve/deny buttons) replaces it later.

**Guard honored:** the webhook notification path
(`packages/polymarket/discovery/pending_notify.py` + `notifications/discord.py`)
was NOT touched. Approval denylist (trading / kill_switch / execution /
risk_manager / secrets / config) untouched. No Codex review (docs/config cleanup).

## What was done

### 1. systemd user service (WSL2)

`hermes-gateway.service` was found **active / enabled / running** (serving the
`vera-hermes-agent` profile). Actions:

- `systemctl --user stop hermes-gateway.service` → stopped.
- `systemctl --user disable hermes-gateway.service` → removed `default.target.wants` symlink.
- `rm ~/.config/systemd/user/hermes-gateway.service` + `daemon-reload` → unit file gone (full retire).
- `systemctl --user reset-failed hermes-gateway.service` → cleared the not-found stub.
- Confirmed: no hermes units in `list-units --all`, no hermes entries in `list-unit-files`.

### 2. Hermes profile

- Two profiles existed: `default` (stopped) and `vera-hermes-agent` (running, sticky default).
- `hermes profile use default` → moved sticky default off vera.
- `hermes profile delete -y vera-hermes-agent` → removed profile dir
  `/home/patel/.hermes/profiles/vera-hermes-agent/` (config, API keys, memories,
  sessions, 76 skills, cron) and the alias binary `/home/patel/.local/bin/vera-hermes-agent`.
- Confirmed: `hermes profile list` now shows only `default`; profiles dir empty.

### 3. Repo wiring removed (`git rm`)

- `skills/polytool-operator/` — `polytool-status/`, `polytool-dev-logs/`, `polytool-files/` (3 SKILL.md).
- `scripts/vera_hermes_healthcheck.sh`
- `scripts/test_vera_status_commands.sh`, `scripts/test_vera_dev_logs_commands.sh`, `scripts/test_vera_files_commands.sh`
- `scripts/start_vera_discord_gateway.sh` — **packet addition.** Not in the packet's
  explicit list, but it is dead Hermes-only wiring (`hermes -p vera-hermes-agent gateway run`
  via tmux) for the now-deleted profile. Flagged and removed.

**`external_dirs` config entry:** the operator skills were registered to Hermes via
`external_dirs` in the *profile's* `config.yaml` (in the WSL profile dir), not in any
repo config. That config was deleted with the profile in step 2. Grep confirmed no
repo `*.json/*.yaml/*.yml/*.toml` carries an `external_dirs` Hermes/skill entry.

### 4. Docs marked RETIRED (history preserved, not deleted)

- `docs/features/vera_hermes_operator_baseline.md`, `polytool_status_skill.md`,
  `polytool_files_skill.md`, `polytool_dev_logs_skill.md` — frontmatter
  `status: complete → retired`, added `retired: 2026-06-02`, plus a one-line RETIRED note.
- `docs/INDEX.md` — the 4 feature rows marked **RETIRED 2026-06-02** (links kept).
- `docs/CURRENT_STATE.md` — new "Hermes Operator Agent — RETIRED (2026-06-02)" section.
- `docs/CURRENT_DEVELOPMENT.md` — voided the stale "Hermes enters at WP7" note and
  added a RETIRED note to "Notes for the Architect" (do not reintroduce Hermes).

### 5. Operational reference scan (scope 5)

Grepped the repo (`*.py/json/yaml/yml/toml/cfg/ini/service`) for `hermes` / `vera-hermes`:

- **Nothing operational imports or calls Hermes / the vera-hermes binary.** Confirmed.
- `config/seed_manifest_external_knowledge.json` (lines 38, 86) — matches `hermes-pmxt`,
  an unrelated **pmxt-SDK knowledge-source attribution**, NOT the Hermes agent. Left untouched.
- `packages/polymarket/discovery/pending_notify.py:32` — a comment in the **guarded
  webhook path** explaining that webhooks (and the old Hermes gateway) can't receive
  component interactions and buttons are deferred. Point is still accurate; left
  untouched per guard.
- `docs/obsidian-vault/.obsidian/workspace.json` — Obsidian open-tab state. Cosmetic.

## Verification

- WSL: service absent from `list-units`/`list-unit-files`; profile dir empty;
  `hermes profile list` shows only `default`; alias binary gone.
- Repo: `git status` shows the 8 deletions + doc edits; no operational code changed.
- Python smoke (`python -m polytool --help`) not affected — no Python touched, but
  see note below.

## Notes / open items

- The new discord.py "Vera" bot (Phases A/B in the decision doc) is **not** built here —
  this packet only retires Hermes. Webhook + `discovery review` CLI gate remain the
  current approve/deny affordance until the bot ships.
- Tree left for review; committed separately per packet instruction.
