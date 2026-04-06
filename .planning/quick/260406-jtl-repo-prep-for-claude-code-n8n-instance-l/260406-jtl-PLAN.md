---
phase: quick-260406-jtl
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .mcp.json
  - .env.example
  - infra/n8n/README.md
  - docs/RIS_OPERATOR_GUIDE.md
  - docs/dev_logs/2026-04-06_n8n_instance_mcp_repo_prep.md
autonomous: true
requirements: []
must_haves:
  truths:
    - ".mcp.json contains an n8n-instance-mcp server entry with HTTP transport pointing to ${N8N_BASE_URL}/mcp-server/http"
    - ".env.example contains N8N_BASE_URL and N8N_MCP_TOKEN placeholders with safe defaults"
    - "infra/n8n/README.md exists with workflow layout and MCP pointer"
    - "RIS_OPERATOR_GUIDE.md MCP section includes exact manual steps for enabling instance-level MCP"
    - "No real secrets committed in any file"
    - "Enterprise-only prerequisite is clearly documented everywhere the MCP config appears"
  artifacts:
    - path: ".mcp.json"
      provides: "Project-scoped MCP config with n8n HTTP server entry"
      contains: "n8n-instance-mcp"
    - path: ".env.example"
      provides: "Safe env template with N8N_BASE_URL and N8N_MCP_TOKEN placeholders"
      contains: "N8N_BASE_URL"
    - path: "infra/n8n/README.md"
      provides: "n8n infrastructure README with workflow layout and MCP pointer"
    - path: "docs/dev_logs/2026-04-06_n8n_instance_mcp_repo_prep.md"
      provides: "Dev log documenting this prep work"
  key_links:
    - from: ".mcp.json"
      to: ".env.example"
      via: "env var expansion: N8N_BASE_URL, N8N_MCP_TOKEN"
      pattern: "N8N_BASE_URL|N8N_MCP_TOKEN"
    - from: "docs/RIS_OPERATOR_GUIDE.md"
      to: ".mcp.json"
      via: "operator instructions reference the config file"
---

<objective>
Prepare the PolyTool repo for Claude Code to connect to n8n via instance-level MCP
(HTTP transport). This is repo-side prep only: config files, env templates, and
operator docs. No runtime changes, no secrets, no n8n UI steps.

Purpose: When n8n Enterprise licensing is available (or when the community edition
adds MCP backend support), Claude Code can immediately connect by filling in two
env vars. Until then, the config is inert but correctly structured.

Output: Updated .mcp.json, .env.example, new infra/n8n/README.md, updated
RIS_OPERATOR_GUIDE.md MCP section, dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.mcp.json (existing — has code-review-graph server, must be preserved)
@.env.example (existing — already has N8N_MCP_BEARER_TOKEN; needs N8N_BASE_URL + N8N_MCP_TOKEN additions)
@docker-compose.yml (reference — n8n service config, port 5678, N8N_MCP_BEARER_TOKEN env var)
@docs/RIS_OPERATOR_GUIDE.md (existing — "Claude Code MCP connection" section needs instance-level MCP steps)
@docs/dev_logs/2026-04-06_n8n_2x_instance_mcp_upgrade.md (prior work — documents Enterprise-only finding)
@infra/n8n/Dockerfile (reference — n8n 2.14.2 base image)

<interfaces>
<!-- Existing .mcp.json structure (must be preserved and extended): -->
```json
{
  "mcpServers": {
    "code-review-graph": {
      "command": "code-review-graph",
      "args": ["serve"]
    }
  }
}
```

<!-- Claude Code .mcp.json HTTP server schema (from Claude Code docs): -->
<!-- HTTP/SSE transport uses "url" + optional "headers" instead of "command"/"args" -->
```json
{
  "mcpServers": {
    "server-name": {
      "url": "http://host:port/path",
      "headers": {
        "Authorization": "Bearer ${ENV_VAR_NAME}"
      }
    }
  }
}
```

<!-- Existing .env.example n8n section (lines 124-138): -->
<!-- N8N_PORT=5678 -->
<!-- N8N_MCP_BEARER_TOKEN=replace_with_mcp_bearer_token (compose-side, separate from Claude Code side) -->
<!-- MCP_PORT=8001 -->
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add n8n instance-level MCP to .mcp.json and .env.example</name>
  <files>.mcp.json, .env.example</files>
  <action>
1. Read the existing `.mcp.json` and ADD a new server entry alongside the existing
   `code-review-graph` entry. Do NOT remove the existing entry. The new entry:

   ```json
   "n8n-instance-mcp": {
     "url": "${N8N_BASE_URL}/mcp-server/http",
     "headers": {
       "Authorization": "Bearer ${N8N_MCP_TOKEN}"
     }
   }
   ```

   The `url` and `headers` fields use Claude Code's env-var expansion syntax
   (`${VAR_NAME}`). No hardcoded URLs or tokens.

2. Read `.env.example` and add two new env vars in the n8n section (after the existing
   `N8N_MCP_BEARER_TOKEN` line). Add a comment block explaining the distinction:

   ```
   # Claude Code -> n8n instance-level MCP connection (project .mcp.json)
   # These are used by Claude Code when opening from repo root.
   # N8N_MCP_BEARER_TOKEN (above) is for compose-side n8n container config.
   # N8N_MCP_TOKEN (below) is for Claude Code's .mcp.json env-var expansion.
   # They MAY hold the same token value, but are consumed by different systems.
   # IMPORTANT: Instance-level MCP requires n8n Enterprise edition (community
   # edition 2.14.2 does not expose the /mcp-server/http backend).
   N8N_BASE_URL=http://localhost:5678
   N8N_MCP_TOKEN=<replace-with-access-token-from-n8n-settings-ui>
   ```

   Ensure the `.env` file itself is gitignored (it already is). The `.env.example`
   is safe to commit because it contains only placeholders.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -c "import json; d=json.load(open('.mcp.json')); assert 'n8n-instance-mcp' in d['mcpServers']; assert 'code-review-graph' in d['mcpServers']; assert '${N8N_BASE_URL}' in d['mcpServers']['n8n-instance-mcp']['url']; print('OK')" && grep -q "N8N_BASE_URL=http://localhost:5678" .env.example && grep -q "N8N_MCP_TOKEN=" .env.example && echo "env OK"</automated>
  </verify>
  <done>
    - .mcp.json has both code-review-graph (unchanged) and n8n-instance-mcp (new) entries
    - n8n-instance-mcp uses url with ${N8N_BASE_URL} and Authorization header with ${N8N_MCP_TOKEN}
    - .env.example has N8N_BASE_URL and N8N_MCP_TOKEN placeholders with explanatory comments
    - No real secrets in either file
  </done>
</task>

<task type="auto">
  <name>Task 2: Create infra/n8n/README.md and update RIS_OPERATOR_GUIDE.md MCP section</name>
  <files>infra/n8n/README.md, docs/RIS_OPERATOR_GUIDE.md</files>
  <action>
1. Create `infra/n8n/README.md` with:
   - Brief purpose statement (custom n8n image for PolyTool RIS pilot)
   - Image details: base n8n 2.14.2 + docker-cli static binary
   - Workflow JSON layout section listing `infra/n8n/workflows/` and all 11 workflow files
   - Note that live workflow grouping/activation happens inside the n8n Project UI
   - A "Claude Code MCP" subsection with:
     - Pointer to `.mcp.json` at repo root for the n8n-instance-mcp server config
     - Pointer to `docs/RIS_OPERATOR_GUIDE.md` for full manual setup steps
     - One-line note: "Instance-level MCP requires n8n Enterprise edition"
   - Link to ADR: `docs/adr/0013-ris-n8n-pilot-scoped.md`

2. Update `docs/RIS_OPERATOR_GUIDE.md` — find the existing "Claude Code MCP connection"
   section (starts around line 598). The section currently has two subsections:
   "polytool MCP server (stdio)" and "n8n 2.x built-in MCP server (HTTP -- Enterprise only)".

   Add a NEW subsection AFTER the existing "n8n 2.x built-in MCP server" subsection:

   ```markdown
   #### Instance-level MCP setup (when Enterprise is available)

   When n8n Enterprise licensing is available, follow these manual steps to enable
   Claude Code's n8n MCP connection:

   1. **Enable instance-level MCP in n8n UI:**
      Settings -> Instance-level MCP -> toggle ON

   2. **Generate or copy the Access Token** from the same settings page.

   3. **Enable MCP access per workflow:**
      Open each workflow you want Claude Code to access -> Settings -> toggle
      "Allow MCP access" ON. Only enabled workflows are visible via MCP.

   4. **Set env vars in your local `.env`** (not `.env.example`):
      ```
      N8N_BASE_URL=http://localhost:5678
      N8N_MCP_TOKEN=<paste-access-token-from-step-2>
      ```

   5. **Restart or reopen Claude Code** from the repo root so it picks up the
      updated `.mcp.json` and env vars. Claude Code reads `.mcp.json` on startup.

   6. **Verify** by asking Claude Code to list available MCP tools. The n8n
      workflows with MCP access enabled should appear as callable tools.

   **Project MCP config:** `.mcp.json` at repo root contains the
   `n8n-instance-mcp` server entry. It uses `${N8N_BASE_URL}` and
   `${N8N_MCP_TOKEN}` env-var expansion -- no secrets are committed.

   **Note:** `N8N_MCP_BEARER_TOKEN` (in docker-compose.yml / .env.example) is the
   compose-side env var that n8n reads at container startup. `N8N_MCP_TOKEN` (in
   .env, consumed by .mcp.json) is the Claude Code side. They may hold the same
   token value but are consumed by different systems.
   ```

   Also update the "Last verified" date at the top of the file to 2026-04-06 if
   not already set (it may already be from the prior quick task).

   Do NOT modify any other sections of RIS_OPERATOR_GUIDE.md.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && test -f infra/n8n/README.md && echo "README exists" && grep -q "Instance-level MCP" docs/RIS_OPERATOR_GUIDE.md && echo "Guide updated" && grep -q ".mcp.json" infra/n8n/README.md && echo "README references mcp config"</automated>
  </verify>
  <done>
    - infra/n8n/README.md exists with image details, workflow layout, and MCP pointer
    - RIS_OPERATOR_GUIDE.md has new "Instance-level MCP setup (when Enterprise is available)" subsection
    - Setup steps are numbered 1-6: enable in UI, copy token, enable per-workflow, set env vars, restart Claude Code, verify
    - Enterprise prerequisite is clearly stated
    - Distinction between N8N_MCP_BEARER_TOKEN (compose) and N8N_MCP_TOKEN (Claude Code) is documented
  </done>
</task>

<task type="auto">
  <name>Task 3: Write dev log</name>
  <files>docs/dev_logs/2026-04-06_n8n_instance_mcp_repo_prep.md</files>
  <action>
Create `docs/dev_logs/2026-04-06_n8n_instance_mcp_repo_prep.md` with:

- **Date:** 2026-04-06
- **Quick task:** quick-260406-jtl
- **Summary:** Repo-side prep for Claude Code to connect to n8n via instance-level MCP.
  Added n8n-instance-mcp entry to project .mcp.json (HTTP transport, env-var expansion
  for URL and bearer token). Added N8N_BASE_URL and N8N_MCP_TOKEN to .env.example.
  Created infra/n8n/README.md with workflow layout and MCP pointer. Updated
  RIS_OPERATOR_GUIDE.md with 6-step manual setup procedure for when Enterprise is available.
- **Files Changed** table listing all 5 files and what changed in each.
- **Enterprise prerequisite** section: Restate that n8n community edition 2.14.2 does
  not expose the /mcp-server/http backend (per probing in quick-260406-ido dev log).
  This prep is forward-looking: when Enterprise is available or community adds MCP
  backend support, the repo config is ready.
- **Env var distinction** section explaining N8N_MCP_BEARER_TOKEN (compose) vs
  N8N_MCP_TOKEN (Claude Code .mcp.json).
- **Remaining manual steps** section: (1) acquire Enterprise license or wait for
  community MCP support, (2) enable instance-level MCP in n8n UI, (3) generate token,
  (4) enable per-workflow MCP access, (5) set N8N_BASE_URL and N8N_MCP_TOKEN in .env,
  (6) restart Claude Code.
- **Codex Review:** Tier: Skip (config + docs only, no strategy/execution/risk code).
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && test -f docs/dev_logs/2026-04-06_n8n_instance_mcp_repo_prep.md && grep -q "quick-260406-jtl" docs/dev_logs/2026-04-06_n8n_instance_mcp_repo_prep.md && echo "Dev log OK"</automated>
  </verify>
  <done>
    - Dev log exists at docs/dev_logs/2026-04-06_n8n_instance_mcp_repo_prep.md
    - Contains summary, files changed, Enterprise prerequisite, env var distinction, remaining manual steps
    - Codex review tier documented as Skip
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| .mcp.json env-var expansion | Claude Code reads env vars from .env at startup; .mcp.json must not contain real tokens |
| .env.example in git | Template file is committed; must contain only placeholders, never real secrets |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-jtl-01 | Information Disclosure | .mcp.json | mitigate | Use ${ENV_VAR} expansion only; no hardcoded URLs with real tokens; verify .env is gitignored (already is) |
| T-jtl-02 | Information Disclosure | .env.example | mitigate | Use placeholder values only ("replace-with-..."); real .env is gitignored |
| T-jtl-03 | Spoofing | MCP bearer token | accept | Token management is n8n's responsibility; repo only stores placeholder; operator must use strong token |
</threat_model>

<verification>
1. `.mcp.json` is valid JSON with both `code-review-graph` and `n8n-instance-mcp` entries
2. No real tokens or URLs with credentials in any committed file
3. `.env.example` has N8N_BASE_URL and N8N_MCP_TOKEN with placeholder values
4. `infra/n8n/README.md` exists and references workflow layout + MCP config
5. `docs/RIS_OPERATOR_GUIDE.md` has the new "Instance-level MCP setup" subsection
6. Dev log written with all required sections
</verification>

<success_criteria>
- Claude Code, when opened from repo root with N8N_BASE_URL and N8N_MCP_TOKEN set in .env, would attempt to connect to the n8n MCP endpoint (connection will fail until Enterprise is available, but the config is correct)
- An operator reading the RIS_OPERATOR_GUIDE.md can follow the 6 numbered steps to activate the MCP connection when Enterprise becomes available
- No secrets committed; no runtime behavior changes; existing .mcp.json code-review-graph entry preserved
</success_criteria>

<output>
After completion, create `.planning/quick/260406-jtl-repo-prep-for-claude-code-n8n-instance-l/260406-jtl-SUMMARY.md`
</output>
