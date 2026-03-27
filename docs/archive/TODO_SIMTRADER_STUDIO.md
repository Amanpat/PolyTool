# TODO: SimTrader Studio — Upcoming Features

Tracked items for the next Studio development pass. All underlying primitives (monitor endpoint, OnDemand sessions, workspace persistence) are in place; these items complete the Live practice + Rewind workflow and improve iteration speed.

---

## 1. "▶ Live" button in workspace toolbar

Add a **Live** button to each workspace card that launches a shadow run directly inside that workspace. The card should transition from idle → active session without the user leaving the UI or typing a CLI command.

Acceptance:
- Clicking Live opens a config mini-form (market slug, duration, strategy preset).
- On confirm, POSTs to `/api/run` with `shadow` command and attaches the resulting session ID to the workspace.
- Workspace card switches to monitor view automatically.

---

## 2. "⏪ Rewind" button to open tape in OnDemand

When a shadow session ends and a tape has been recorded, surface a **Rewind** button in the workspace card. One click opens the tape in a new OnDemand workspace pre-attached to the same market context (slug, YES/NO asset IDs from tape `meta.json`).

Acceptance:
- Button appears only when `run_manifest.json` shows `mode="shadow"` and a `tape_dir` is set.
- New OnDemand workspace is inserted into the grid next to the originating session workspace.
- Tape is pre-selected and strategy config is pre-populated from the shadow session's config.

---

## 3. Auto-attach shadow tape to OnDemand workspace on session completion

As a background enhancement to item 2: when the Studio detects a session transitioning to `completed` via the monitor poll, automatically create an OnDemand workspace and attach the tape without requiring a button click. This enables a fully hands-off live → replay transition.

Acceptance:
- Controlled by a Studio setting (default: off) so users who prefer manual control are unaffected.
- Works even if the browser tab was backgrounded during the shadow run.
- OnDemand workspace is added at the end of the workspace list, not displacing existing cards.

---

## 4. Playback speed control in OnDemand scrubber

Add **1× / 2× / 4× / max** speed selector buttons to the OnDemand workspace. Currently replays run at a fixed rate; variable speed lets users quickly scan a long tape or slow down around an interesting event cluster.

Acceptance:
- Speed buttons are visible in the OnDemand card header alongside seek controls.
- Changing speed takes effect immediately on the next event batch (no restart required).
- "max" runs as fast as the backend can drain the tape (useful for quick equity-curve previews).
