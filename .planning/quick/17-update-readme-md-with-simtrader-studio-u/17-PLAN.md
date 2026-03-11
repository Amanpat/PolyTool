---
phase: quick-17
plan: 17
type: execute
wave: 1
depends_on: []
files_modified:
  - README.md
autonomous: true

must_haves:
  truths:
    - "README.md has a top-level 'SimTrader Studio (UI) — User Guide' section"
    - "Section covers launch instructions for both local and Docker"
    - "Three 'Start here' workflows are documented with click-by-click steps"
    - "Tab reference table covers all 8 tabs (Dashboard, Sessions, Cockpit, Workspaces, Tapes, Reports, OnDemand, Settings)"
    - "Troubleshooting addresses '0 trades is normal', no-tape state, WS stalls"
    - "Links to README_SIMTRADER.md, FEATURE-simtrader-studio.md, TODO_SIMTRADER_STUDIO.md are present"
  artifacts:
    - path: "README.md"
      provides: "SimTrader Studio user guide section"
      contains: "SimTrader Studio (UI)"
  key_links:
    - from: "README.md"
      to: "docs/README_SIMTRADER.md"
      via: "markdown link"
    - from: "README.md"
      to: "docs/features/FEATURE-simtrader-studio.md"
      via: "markdown link"
    - from: "README.md"
      to: "docs/TODO_SIMTRADER_STUDIO.md"
      via: "markdown link"
---

<objective>
Add a concise, practical "SimTrader Studio (UI) — User Guide" section to README.md.

Purpose: First-time users need launch instructions, orientation to the tab layout, and three
canonical workflows without hunting through multiple docs. The section replaces the current
stub ("Studio UI" block) with a full guide that links out to deeper references.

Output: Updated README.md with Studio user guide section.
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@README.md
@docs/README_SIMTRADER.md
@docs/features/FEATURE-simtrader-studio.md
@docs/TODO_SIMTRADER_STUDIO.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Replace Studio UI stub with full user guide section in README.md</name>
  <files>README.md</files>
  <action>
Replace the existing "## Studio UI" section (lines 32–56 in README.md, from "## Studio UI" through the closing "---") with a new "## SimTrader Studio (UI) — User Guide" section. The new section must include exactly these subsections, kept short and practical (no walls of text):

**Launch**

Local dev:
```bash
pip install polytool[studio]
python -m polytool simtrader studio --open
# Opens http://localhost:8765
```

Docker (binds all interfaces):
```bash
docker compose up --build polytool
# Opens http://localhost:8765
```

Inside a Docker container omit `--open` (no local browser to open).

**Tabs at a glance**

A two-column table or tight bullet list covering the 8 tabs in their nav order:

| Tab | What it does |
|-----|--------------|
| Dashboard | Command launcher + recent session summary |
| Sessions | List of all running and completed sessions with status |
| Cockpit | Workspace grid: attach sessions, OnDemand replays, or static artifacts to panels |
| Workspaces | (alias/entry point for workspace management if applicable) |
| Tapes | Browse recorded WS tapes |
| Reports | Browse and open HTML run/sweep/batch reports |
| OnDemand | Create and control interactive tape replay sessions |
| Settings | Export/import workspace layout JSON; clear saved workspaces |

Note: The actual nav order from the HTML is Dashboard → Sessions → Cockpit → Workspaces → Tapes → Reports → OnDemand → Settings. Use that exact order.

**Start here: three workflows**

Workflow A — Live practice (Shadow → Viewer → Rewind):
1. Go to Dashboard, click **Shadow** (or fill in market slug + duration) to start a live simulation session.
2. Switch to the Sessions tab — the new session appears. Click it to open the Simulation Viewer (equity curve, orders, fills, Reasons tab).
3. When the shadow run ends, go to the OnDemand tab, select the tape that was recorded, and replay it interactively to scrub/seek with different strategy configs.

Workflow B — OnDemand prop trading (replay and iterate):
1. Go to the OnDemand tab; select a tape from the list.
2. Click **Start** to create a replay session. Use seek/scrub controls to advance through events.
3. Adjust strategy config (inline JSON or preset) and restart from any position.
4. Artifacts (run_manifest.json, summary.json, ledger.jsonl) are written to `artifacts/simtrader/` on finish.

Workflow C — Visual bot playback (interpret a simulation run):
1. Go to Cockpit, open a workspace, and attach it to an existing Session or Artifact.
2. The workspace shows the equity curve chart, orders table, fills table, and the Reasons tab.
3. The Reasons tab lists rejection counters — `no_bbo`, `edge_below_threshold`, `fee_kills_edge`, etc. — explaining why a no-trade run produced no fills.

**Troubleshooting**

Keep this as a tight bullet list:
- **"0 trades" is normal** — check the Reasons tab for the dominant rejection counter (e.g. `edge_below_threshold` means the strategy threshold is stricter than the market spread).
- **No tapes available** — run a shadow session first: Dashboard → Shadow; tapes are written to `artifacts/simtrader/tapes/` by default.
- **WS stall** — the shadow run exits early. Pick a more active market or increase `--max-ws-stalls-seconds` in the shadow config form.
- **Studio won't start** — ensure `pip install polytool[studio]` was run. Port conflicts: pass `--port 9000` or another free port.

**Further reading**

| Resource | Purpose |
|----------|---------|
| [docs/README_SIMTRADER.md](docs/README_SIMTRADER.md) | Full CLI operator guide: quickrun, shadow, sweeps, batch, artifact layout |
| [docs/features/FEATURE-simtrader-studio.md](docs/features/FEATURE-simtrader-studio.md) | Studio architecture, API endpoints, workspace types, monitor cards |
| [docs/TODO_SIMTRADER_STUDIO.md](docs/TODO_SIMTRADER_STUDIO.md) | Planned features: Live button, Rewind button, auto-attach, playback speed |

Close the section with a `---` horizontal rule to match surrounding README style.

Do NOT mention "polyttool" (legacy name). Do NOT add animations or dark-mode notes. Keep each subsection to 10 lines or fewer where possible.
  </action>
  <verify>
    1. `grep -n "SimTrader Studio (UI)" README.md` returns a match at the expected heading.
    2. `grep -n "docs/README_SIMTRADER.md" README.md` returns a match (link present).
    3. `grep -n "docs/features/FEATURE-simtrader-studio.md" README.md` returns a match.
    4. `grep -n "docs/TODO_SIMTRADER_STUDIO.md" README.md` returns a match.
    5. `grep -n "0 trades" README.md` returns a match (troubleshooting present).
    6. The old stub heading "## Studio UI" is gone (replaced).
    7. Read README.md and confirm no `polyttool` references were introduced.
  </verify>
  <done>
    README.md contains a single "SimTrader Studio (UI) — User Guide" section with: launch
    instructions (local + Docker), an 8-tab reference table, three numbered workflows (A/B/C),
    a troubleshooting bullet list, and a further-reading table linking to the three specified docs.
    The previous "## Studio UI" stub is removed.
  </done>
</task>

</tasks>

<verification>
After writing:
- README renders cleanly (no broken markdown: unclosed code fences, mismatched table columns).
- All three doc links are relative paths pointing to existing files.
- Section fits the README's existing style (H2 headings, fenced code blocks, tables, `---` separators).
</verification>

<success_criteria>
- README.md has exactly one "SimTrader Studio (UI)" section (no duplicate headings).
- Launch instructions cover both `python -m polytool simtrader studio --open` and `docker compose up --build polytool`.
- Workflows A, B, C are present with numbered steps.
- Tab table lists all 8 tabs.
- Troubleshooting covers: 0-trades, no-tapes, WS-stall, studio-won't-start.
- Three doc links present and correct.
- No legacy "polyttool" name introduced.
</success_criteria>

<output>
After completion, create `.planning/quick/17-update-readme-md-with-simtrader-studio-u/17-SUMMARY.md` using the summary template.
</output>
