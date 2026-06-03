---
title: Doc Sync Hermes Retirement Discord System
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-06-02_doc-sync-hermes-retirement-discord-system.md
last_synced: '2026-06-03T02:28:25Z'
lifecycle: reviewed
generator: repo-sync
---

# Dev Log — Doc sync: Hermes retirement + the Discord notification/bot system

**Date:** 2026-06-02
**Slug:** doc-sync-hermes-retirement-discord-system
**Type:** Docs only (no code, no denylist paths, no Codex)

## Objective

Bring the repo docs and the vault `repo-docs/` mirror (stale since 2026-05-25)
in line with three shipped changes: the Hermes retirement, the WP-1/WP-2 Discord
embed-card notifications, and the new Vera discord.py bot. Disambiguate "Vera"
(the new bot) from the retired `vera-hermes-agent` everywhere.

## What was done

1. **Confirmed Hermes retirement marks intact** (from `3dbf1cd`): all 4
   `docs/features/` docs (`vera_hermes_operator_baseline`, `polytool_status_skill`,
   `polytool_files_skill`, `polytool_dev_logs_skill`) carry `status: retired`; 4
   INDEX rows marked RETIRED; CURRENT_STATE/CURRENT_DEVELOPMENT retirement notes
   present.

2. **Updated `docs/features/FEATURE-discord-alerting-tracka.md`** to the current
   system: a "notifier vs. bot" preamble (webhook = always-on notifier;
   copy-block = bot-independent fallback; buttons = the separate Vera bot); the
   new `post_message(text="", *, embeds=None, webhook_url=None)` signature; and a
   new "Wallet pending-review notifications (WP-1 + WP-2)" section covering the
   richer evidence fields (open/resolved, discovery source, category), the embed
   card + digest + copy-block, dedup, and the non-fatal contract.

3. **Created `docs/features/FEATURE-vera-discord-bot.md`** (new canonical doc):
   purpose; the split (webhook notifies, bot handles interaction); Phase A
   (skeleton, `/ping`, `Dockerfile.vera` + `polytool-vera-bot`
   `restart: unless-stopped`, least-privilege intents) SHIPPED; Phase B
   (`/pending` + approve/deny buttons, thin trigger over `discovery review`,
   author-guard on list+click, idempotency, button-disable-after-action, public
   cards) with the ACTUAL final state from its dev log (Codex 10/10 PASS,
   live-verified); security boundaries; deployment. **Explicitly states it is NOT
   the retired `vera-hermes-agent`.**

4. **Updated `CURRENT_STATE.md` / `CURRENT_DEVELOPMENT.md`** operator surface: a
   new "Operator Discord Surface" section (CURRENT_STATE) and architect note
   (CURRENT_DEVELOPMENT) — Hermes retired; notifications via webhook embed cards;
   interactive approve/deny via the Vera bot. Updated the retirement section's
   "planned → SHIPPED" replacement pointer. Added an INDEX row for the canonical
   Vera bot doc.

5. **Regenerated the vault `repo-docs/` mirror** via the repo-sync process:
   `python docs/scripts/sync-repo-docs.py` (one-way `docs/` → `repo-docs/`,
   PyYAML 6.0.2). Result: 52 new, 10 diverged, 0 orphaned, 843 unchanged.
   Verified the vault now shows: the 4 Hermes mirrors `status: retired`, the
   updated `feature-discord-alerting-tracka.md` (embed-card/copy-block content),
   and the new `feature-vera-discord-bot.md` (with the not-vera-hermes-agent
   disambiguation). The mirror is generated/one-way; source `docs/` is authoritative.

## Notes / flags

- **WP-1/WP-2 source is uncommitted (other agents' in-flight work).** The code
  (`evidence_summary.py`, `pending_notify.py`, `notifications/discord.py`,
  `wallet_scan.py` + tests) and the two WP dev logs
  (`2026-06-02_pending_review_fields_wp1.md`,
  `_embed_card_wp2.md`) are present in the working tree but NOT committed. The
  docs (and the Vera bot's Phase B) describe this working-tree reality. This
  packet left that code/those logs untouched (docs-only). The mirror regeneration
  did create mirrors of those untracked dev logs (it mirrors working-tree docs);
  surfaced here for the reviewer. **Recommend committing the WP-1/WP-2 work
  separately** so the committed tree matches the docs and the shipped bot.

## Guards honored

Docs only — no code or denylist changes; no Codex (per policy). Commit separate
from the WP code and the operator's untracked vault decision doc; tree left for
review.
