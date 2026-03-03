---
phase: 16-studio-workspace-grid-real-time-monitor-
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/polymarket/simtrader/studio/static/index.html
  - packages/polymarket/simtrader/studio/app.py
autonomous: true

must_haves:
  truths:
    - "Session card shows status, last-log-time, event rate, reconnects/stalls, decision/order/fill counts, net PnL, with Open Report and Kill buttons"
    - "Artifact card shows strategy name, net PnL, dominant rejection reason, and an Open in Viewer link"
    - "OnDemand card shows current timestamp, cash, equity, and open order count"
    - "All three cards update within 3 seconds of actual state changes without UI lag when multiple workspaces are open"
  artifacts:
    - path: "packages/polymarket/simtrader/studio/static/index.html"
      provides: "Enhanced renderWorkspaceSessionCard, renderWorkspaceArtifactCard, renderWorkspaceOnDemandCard + monitor metrics cache"
    - path: "packages/polymarket/simtrader/studio/app.py"
      provides: "GET /api/sessions/{id}/monitor — thin endpoint returning run_metrics + summary fields"
  key_links:
    - from: "refreshWorkspaceMonitorMetrics()"
      to: "/api/sessions/{id}/monitor"
      via: "apiJson fetch in refresh loop"
      pattern: "api/sessions.*monitor"
    - from: "renderWorkspaceSessionCard(ws)"
      to: "state.wsMonitorCache"
      via: "Map lookup by session_id"
      pattern: "wsMonitorCache\\.get"
---

<objective>
Upgrade the three workspace source cards (Running Session, OnDemand, Simulation Viewer) to show
actionable real-time monitor metrics. Sessions show live stats + action buttons. Artifact cards
show a summary with a viewer link. OnDemand cards surface cursor position and portfolio state.

Purpose: Let a user run 2 shadows and 1 replay simultaneously and watch all three in grid view with meaningful at-a-glance status — without switching tabs.
Output: Enhanced three-panel source grid with throttled 1 s monitor refresh, thin backend metrics endpoint.
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/quick/16-studio-workspace-grid-real-time-monitor-/16-PLAN.md
@packages/polymarket/simtrader/studio/static/index.html
@packages/polymarket/simtrader/studio/app.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add GET /api/sessions/{id}/monitor backend endpoint</name>
  <files>packages/polymarket/simtrader/studio/app.py</files>
  <action>
Add a new lightweight GET endpoint at `/api/sessions/{session_id}/monitor` in `app.py`, placed
after the existing `/api/sessions/{session_id}/log` route (around line 995).

The endpoint must:
1. Call `_get_tracked_session(session_id)` to get the decorated session snapshot.
2. Read `run_manifest.json` from `session["artifact_dir"]` if the dir exists (use
   `_read_json_file`). Extract `run_metrics` dict from it (keys: `events_received`,
   `ws_reconnects`, `ws_timeouts`). If no artifact_dir or file missing, `run_metrics = {}`.
3. Read `summary.json` from the same dir. Extract `net_profit` and `strategy`. If missing,
   both are `None`.
4. Derive `decisions_count` from `run_manifest.get("decisions_count")`, falling back to
   `summary.get("decisions_count")`, then `None`.
5. Derive `orders_count` and `fills_count` the same way (run_manifest first, then summary).
6. Return:
   ```json
   {
     "session_id": "...",
     "status": "...",
     "started_at": "...",
     "subcommand": "...",
     "report_url": "...",
     "artifact_dir": "...",
     "run_metrics": { "events_received": N, "ws_reconnects": N, "ws_timeouts": N },
     "net_profit": "...",
     "strategy": "...",
     "decisions_count": N,
     "orders_count": N,
     "fills_count": N
   }
   ```

Do NOT load equity_curve, orders, fills, or decisions rows — this is a lightweight stats call.
</action>
  <verify>
Start studio locally and run:
```
curl http://localhost:2701/api/sessions/SOME_ID/monitor
```
Returns JSON with the fields above. If no session exists, returns 404. If session has no artifact_dir yet, run_metrics/net_profit/strategy all present as null/empty without error.
</verify>
  <done>Endpoint exists, returns correct shape for running sessions and for sessions with no artifact_dir yet.</done>
</task>

<task type="auto">
  <name>Task 2: Frontend monitor cache + refreshWorkspaceMonitorMetrics + enhanced session/artifact/ondemand cards</name>
  <files>packages/polymarket/simtrader/studio/static/index.html</files>
  <action>
Make the following changes to index.html. All changes are in the `<script>` block.

**A. Add `wsMonitorCache` to the state object (around line 584):**
Add after `workspaceArtifactLoading`:
```js
wsMonitorCache: new Map(),   // session_id -> monitor payload
wsMonitorFetching: new Set(), // session_ids being fetched
```

**B. Add `refreshWorkspaceMonitorMetrics()` function** (place after `refreshWorkspaceSessionLogs`, around line 2693):
```js
async function refreshWorkspaceMonitorMetrics() {
  // Collect unique attached session IDs across all workspaces
  const needed = new Set();
  for (const ws of state.workspaces) {
    if (ws.attachedSessionId) needed.add(ws.attachedSessionId);
  }
  const toFetch = [...needed].filter((id) => !state.wsMonitorFetching.has(id));
  if (!toFetch.length) return;
  await Promise.all(toFetch.map(async (sessionId) => {
    state.wsMonitorFetching.add(sessionId);
    try {
      const data = await apiJson("/api/sessions/" + encodeURIComponent(sessionId) + "/monitor");
      state.wsMonitorCache.set(sessionId, data);
    } catch (_) {
      // keep stale data; don't evict on transient failure
    } finally {
      state.wsMonitorFetching.delete(sessionId);
    }
  }));
}
```

**C. Replace `refreshWorkspaceSessionLogs` call in the boot() poll loop** (around line 3341):
Change:
```js
await Promise.all([refreshSessions(), refreshArtifacts(), refreshOnDemandSessions()]);
await refreshWorkspaceSessionLogs();
```
To:
```js
await Promise.all([refreshSessions(), refreshArtifacts(), refreshOnDemandSessions()]);
await Promise.all([refreshWorkspaceSessionLogs(), refreshWorkspaceMonitorMetrics()]);
```

Also add a separate 1-second interval only for monitor metrics refresh (does not re-render full
panel; just updates cache and re-renders workspace panel):
```js
setInterval(async () => {
  try {
    await refreshWorkspaceMonitorMetrics();
    renderWorkspacePanel();
  } catch (_) {}
}, 1000);
```
Add this just after the existing 3-second interval in `boot()`.

**D. Replace `renderWorkspaceSessionCard(ws)` entirely** (around line 2808-2828):

```js
function renderWorkspaceSessionCard(ws) {
  if (!ws.attachedSessionId) {
    return "<div class='workspace-source-card'><h3>Running Session</h3><div class='empty'>No session attached.</div></div>";
  }
  const row = state.sessionById.get(ws.attachedSessionId);
  if (!row) {
    return "<div class='workspace-source-card'><h3>Running Session</h3><div class='empty'>Session no longer available.</div></div>";
  }
  const mon = state.wsMonitorCache.get(ws.attachedSessionId) || {};
  const rm = mon.run_metrics || {};
  const eventsReceived = rm.events_received != null ? String(rm.events_received) : "-";
  const reconnects = rm.ws_reconnects != null ? String(rm.ws_reconnects) : "-";
  const wsTimeouts = rm.ws_timeouts != null ? String(rm.ws_timeouts) : "-";
  const netProfit = mon.net_profit != null ? String(mon.net_profit) : "-";
  const decisionsCount = mon.decisions_count != null ? String(mon.decisions_count) : "-";
  const ordersCount = mon.orders_count != null ? String(mon.orders_count) : "-";
  const fillsCount = mon.fills_count != null ? String(mon.fills_count) : "-";
  const lastLogLine = (ws.sessionLogText || "").split("\n").filter(Boolean).slice(-1)[0] || "";
  const lastLogShort = lastLogLine.length > 60 ? lastLogLine.slice(0, 60) + "…" : lastLogLine;
  const isActive = ["running", "starting", "terminating"].includes(String(row.status));
  const reportUrl = row.report_url || mon.report_url || "";
  const openReportBtn = reportUrl
    ? "<button class='btn small' onclick=\"openReport('" + escAttr(reportUrl) + "')\">Open Report</button>"
    : "<button class='btn small ghost' disabled>No Report</button>";
  const killBtn = isActive
    ? "<button class='btn small danger' onclick=\"killSession('" + escAttr(ws.attachedSessionId) + "')\">Kill</button>"
    : "";
  return "<div class='workspace-source-card'>"
    + "<h3>Running Session</h3>"
    + "<div class='kv'>"
    + "<div class='k'>status</div><div class='v'><span class='status " + escHtml(row.status || "") + "'>" + escHtml(row.status || "unknown") + "</span></div>"
    + "<div class='k'>kind</div><div class='v'>" + escHtml(row.subcommand || row.kind || "-") + "</div>"
    + "<div class='k'>started</div><div class='v'>" + escHtml(fmtDate(row.started_at)) + "</div>"
    + "<div class='k'>events</div><div class='v'>" + escHtml(eventsReceived) + "</div>"
    + "<div class='k'>reconnects</div><div class='v'>" + escHtml(reconnects) + "</div>"
    + "<div class='k'>stalls</div><div class='v'>" + escHtml(wsTimeouts) + "</div>"
    + "<div class='k'>decisions</div><div class='v'>" + escHtml(decisionsCount) + "</div>"
    + "<div class='k'>orders</div><div class='v'>" + escHtml(ordersCount) + "</div>"
    + "<div class='k'>fills</div><div class='v'>" + escHtml(fillsCount) + "</div>"
    + "<div class='k'>net PnL</div><div class='v'>" + escHtml(netProfit) + "</div>"
    + "<div class='k'>last log</div><div class='v mono muted'>" + escHtml(lastLogShort || "—") + "</div>"
    + "</div>"
    + "<div class='row' style='margin-top:8px;gap:6px;'>"
    + openReportBtn + " " + killBtn
    + "</div>"
    + "</div>";
}
```

**E. Replace `renderWorkspaceArtifactCard(ws)` entirely** (around line 2854-2879):

Keep the existing loading/error states. Update the "loaded" branch to:
```js
// after "const artifact = payload.artifact || {}; const summary = payload.summary || {};"
const rejectionReasons = payload.rejection_reasons || [];
const dominantReason = rejectionReasons.length > 0
  ? String(rejectionReasons[0].reason || "-")
  : "-";
const dominantCount = rejectionReasons.length > 0
  ? String(rejectionReasons[0].count || "")
  : "";
const netProfit = summary.net_profit != null ? String(summary.net_profit) : "-";
const strategy = summary.strategy || (payload.run_manifest || {}).strategy || "-";
const parsed = parseSimulationArtifactKey(ws.attachedArtifactKey);
const viewerUrl = parsed
  ? ("/simulation/" + encodeURIComponent(parsed.artifactType) + "/" + encodeURIComponent(parsed.artifactId))
  : null;
const openViewerBtn = viewerUrl
  ? "<a href='" + escAttr(viewerUrl) + "' class='btn small' target='_blank'>Open Viewer</a>"
  : "";
return "<div class='workspace-source-card'>"
  + "<h3>Simulation Viewer</h3>"
  + "<div class='kv'>"
  + "<div class='k'>artifact</div><div class='v'>" + escHtml(String(artifact.display_name || ws.attachedArtifactKey)) + "</div>"
  + "<div class='k'>strategy</div><div class='v'>" + escHtml(strategy) + "</div>"
  + "<div class='k'>net PnL</div><div class='v'>" + escHtml(netProfit) + "</div>"
  + "<div class='k'>top reject</div><div class='v'>" + escHtml(dominantReason) + (dominantCount ? " (" + escHtml(dominantCount) + ")" : "") + "</div>"
  + "<div class='k'>orders</div><div class='v'>" + escHtml(String((payload.orders || []).length)) + "</div>"
  + "<div class='k'>fills</div><div class='v'>" + escHtml(String((payload.fills || []).length)) + "</div>"
  + "</div>"
  + (openViewerBtn ? "<div style='margin-top:8px;'>" + openViewerBtn + "</div>" : "")
  + "</div>";
```

NOTE: The viewer URL path `/simulation/...` may not be a real route. If a direct viewer URL does
not exist, use a link that opens the simulation tab. Check the existing `openReport` pattern or
use a javascript call: replace the `<a href>` with:
```js
const openViewerBtn = "<button class='btn small' onclick=\"openSimulationArtifact('" + escAttr(ws.attachedArtifactKey) + "')\">Open Viewer</button>";
```
where `openSimulationArtifact(key)` sets `state.simulation.selectedArtifactKey = key` then
calls `activateTab("simulation")` then `loadSimulationSelected()`. Add this helper function.

**F. Replace `renderWorkspaceOnDemandCard(ws)` entirely** (around line 2830-2852):

```js
function renderWorkspaceOnDemandCard(ws) {
  if (!ws.attachedOnDemandId) {
    return "<div class='workspace-source-card'><h3>OnDemand</h3><div class='empty'>No OnDemand session attached.</div></div>";
  }
  const row = state.ondemandById.get(ws.attachedOnDemandId);
  if (!row || !row.state) {
    return "<div class='workspace-source-card'><h3>OnDemand</h3><div class='empty'>OnDemand session no longer available.</div></div>";
  }
  const st = row.state || {};
  const snapshot = st.portfolio_snapshot || {};
  const cursor = st.cursor != null ? String(st.cursor) : "0";
  const total = st.total_events != null ? String(st.total_events) : "?";
  const pct = (st.total_events && st.cursor != null)
    ? " (" + Math.round(100 * st.cursor / st.total_events) + "%)"
    : "";
  const tsRecv = st.ts_recv != null ? String(st.ts_recv) : "-";
  const openOrders = (st.open_orders || []).length;
  const equity = snapshot.final_equity != null ? String(snapshot.final_equity) : "-";
  const cash = snapshot.final_cash != null ? String(snapshot.final_cash) : (snapshot.cash != null ? String(snapshot.cash) : "-");
  const netProfit = snapshot.net_profit != null ? String(snapshot.net_profit) : "-";
  return "<div class='workspace-source-card'>"
    + "<h3>OnDemand</h3>"
    + "<div class='kv'>"
    + "<div class='k'>cursor</div><div class='v'>" + escHtml(cursor + " / " + total + pct) + "</div>"
    + "<div class='k'>timestamp</div><div class='v mono'>" + escHtml(tsRecv) + "</div>"
    + "<div class='k'>open orders</div><div class='v'>" + escHtml(String(openOrders)) + "</div>"
    + "<div class='k'>cash</div><div class='v'>" + escHtml(cash) + "</div>"
    + "<div class='k'>equity</div><div class='v'>" + escHtml(equity) + "</div>"
    + "<div class='k'>net PnL</div><div class='v'>" + escHtml(netProfit) + "</div>"
    + "</div>"
    + "</div>";
}
```

**Throttle note:** The 1-second monitor refresh already throttles the heavy work. The
`renderWorkspacePanel()` it calls re-renders all cards from cached data only (no I/O), so even
with 2-3 workspaces open, DOM updates are minimal string concatenations at 1 Hz.
</action>
  <verify>
1. Open Studio at http://localhost:2701, navigate to Workspaces tab.
2. Open 2 market workspaces and start shadow sessions on each.
3. Open 1 tape workspace, attach a finished run artifact.
4. In grid layout: each workspace shows 3 monitor cards.
5. Running Session cards show status=running, events count incrementing, reconnects, stalls, decisions/orders/fills counts, net PnL (may be - until run completes), and a Kill button. No Open Report button visible until report exists.
6. Simulation Viewer card shows strategy name, net PnL, top rejection reason with count, and an "Open Viewer" button that switches to simulation tab and loads the artifact.
7. OnDemand card shows cursor position and portfolio fields.
8. No UI lag or blank frames observed while all sessions are active.
</verify>
  <done>
- All three monitor cards show their specified fields for each workspace panel.
- Kill button present and functional on running session cards.
- Open Viewer button navigates to simulation tab with artifact pre-selected.
- Monitor data updates at ~1 s cadence without causing visible jank.
- No JS console errors in normal operation.
</done>
</task>

</tasks>

<verification>
After both tasks complete:
- `curl http://localhost:2701/api/sessions/{id}/monitor` returns the lightweight stats shape.
- Workspace grid with 3 workspaces (2 shadow + 1 replay artifact) displays all monitor data.
- Kill buttons trigger POST /api/sessions/{id}/kill and refresh the session status.
- Artifact "Open Viewer" button activates simulation tab with the correct artifact selected.
</verification>

<success_criteria>
Run 2 shadow sessions and 1 replay in workspace grid simultaneously. All three source cards in
each workspace show live or static metrics without blank states. No tab switching required to
check session health. UI remains responsive throughout.
</success_criteria>

<output>
After completion, create `.planning/quick/16-studio-workspace-grid-real-time-monitor-/16-SUMMARY.md`
</output>
