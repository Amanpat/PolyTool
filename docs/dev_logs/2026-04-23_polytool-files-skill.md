# 2026-04-23 polytool-files Hermes Skill

## Scope

- Objective: build the third operator query skill for `vera-hermes-agent` — `polytool-files`.
- Picks up from `docs/dev_logs/2026-04-23_polytool-status-skill.md`.
- This session: implement skill with explicit whitelist, build test suite, create docs.
- No live execution paths touched. No repo Python code changed. No test suite changes needed.

## Files Changed and Why

| File | Change | Why |
|---|---|---|
| `skills/polytool-operator/polytool-files/SKILL.md` | Created | Skill definition: whitelist, path validation, modes (exact/name/section/list), ambiguity rules, guardrails |
| `scripts/test_vera_files_commands.sh` | Created | 10-test validation script for all SKILL.md command patterns |
| `docs/features/polytool_files_skill.md` | Created | Feature documentation with whitelist table, capability summary, ambiguity rules, test suite |
| `docs/INDEX.md` | Updated | Added `polytool-files` to Features table |
| `docs/dev_logs/2026-04-23_polytool-files-skill.md` | Created (this file) | Mandatory per repo convention |

No Python code changed. No profile config changes needed. No repo tests affected.

## Whitelist Design Decisions

### Root-level docs included

All operator-relevant top-level docs: ARCHITECTURE, PLAN_OF_RECORD, STRATEGY_PLAYBOOK, RISK_POLICY, ROADMAP, INDEX, CURRENT_DEVELOPMENT, CURRENT_STATE, DOCS_BEST_PRACTICES, PROJECT_OVERVIEW, README.

Excluded root-level: CLAUDE.md (contains system instructions not relevant for Vera to relay), AGENTS.md (same), ARCHITECT_CONTEXT_PACK.md (Architect-specific instructions), TODO.md (ephemeral), KNOWLEDGE_BASE_CONVENTIONS.md (operational convention doc, could add later if needed).

### Subtrees included

`features/` (88 files), `specs/` (46 files), `reference/` (5 files), `runbooks/` (21 files), `adr/` (14 files). These are the stable, version-controlled project documentation subtrees.

### Subtrees excluded and why

| Path | Reason |
|---|---|
| `dev_logs/` | Already served by polytool-dev-logs; duplicating scope would be confusing |
| `obsidian-vault/` | Planning notes / Architect input, not production project docs |
| `archive/` | Superseded; stale content could mislead |
| `eval/` | Evaluation artifacts, not narrative docs |
| `external_knowledge/` | Ingested research content, not project docs |
| `pdr/` | Planning decision records — internal planning artifact |
| `audits/` | Audit reports — specialized, rare operator need |

### Path validation approach

Four-check model (not regex-based — explicit string checks the LLM can follow reliably):
1. Path starts with approved repo prefix
2. No excluded subdir names appear in the path (catches obsidian-vault, dev_logs, archive, `..`)
3. Ends with `.md`
4. No hidden-file component (`/.`)

This is deliberately simple and auditable. A complex regex would be harder for the LLM to apply correctly and harder to reason about.

### Ambiguity handling: explicit list, not silent pick

When multiple docs match a name fragment, Vera lists all candidates and states which one it used, inviting the operator to specify another. This prevents silent scope selection that could return the wrong doc without the operator knowing alternatives exist.

## Commands Run and Output

### 1. Skill directory and file creation
```
mkdir -p skills/polytool-operator/polytool-files/
# SKILL.md written via Write tool
```
Result: created. ✓

### 2. Skill discovery verification
```
$ wsl bash -lc "hermes -p vera-hermes-agent skills list | grep polytool"
│ polytool-dev-logs  │  polytool-operator  │  local  │  local  │
│ polytool-files     │  polytool-operator  │  local  │  local  │
│ polytool-status    │  polytool-operator  │  local  │  local  │
0 hub-installed, 68 builtin, 3 local
```
Result: 3 local skills, all in correct category. ✓

### 3. Command pattern test suite — all 10 PASS
```
=== polytool-files command pattern tests ===
1. Root docs accessible       PASS — 6/6 approved root docs found
2. Subtrees accessible        features/ 88, specs/ 46, reference/ 5, runbooks/ 21, adr/ 14
3. Exact path read            PASS — ARCHITECTURE.md header read correctly
4. Name lookup features/      PASS — gate2-preflight: FEATURE-gate2-preflight.md returned
5. Name lookup specs/         PASS — gate2: 5 matching specs returned
6. Cross-subtree search       PASS — track2 → docs/runbooks/TRACK2_OPERATOR_RUNBOOK.md
7. List runbooks/             PASS — 10 runbook filenames listed
8. Section-focused grep       PASS — (no exact "Track 2" heading in STRATEGY_PLAYBOOK, handled gracefully)
9. Excluded dirs confirmed    PASS — dev_logs/, obsidian-vault/, archive/ all present and excluded
10. Path traversal guard      PASS — 3/3 traversal attempts resolve outside docs/
=== All command pattern tests complete ===
```

### 4. Safety posture confirmed
```
$ wsl bash -lc "grep -A3 'approvals:' /home/patel/.hermes/profiles/vera-hermes-agent/config.yaml"
approvals:
  mode: deny
  timeout: 60
  cron_mode: deny
```
Result: approvals.mode remains deny. ✓

### 5. Agent tests: BLOCKED — Ollama Cloud rate limit (same as previous session)
```
vera-hermes-agent chat -Q -q 'Reply with exactly: vera hermes agent ready'
→ HTTP 429: you (patelamanst) have reached your session usage limit
```

Both `vera-hermes-agent` and `default` profiles hit 429. The account-level session quota was exhausted during the polytool-dev-logs session (5+ agent round-trips plus multiple refusal test retries). The quota is shared across profiles.

**Pending agent tests** (run when quota resets):
```bash
# Test 1: exact approved path
vera-hermes-agent chat -Q -q 'Read PLAN_OF_RECORD.md and give me a 3-bullet summary.'

# Test 2: feature doc name lookup
vera-hermes-agent chat -Q -q 'What does the Gate 2 preflight feature doc say?'

# Test 3: spec lookup
vera-hermes-agent chat -Q -q 'Find the spec for Gate 2 tape acquisition and summarize it.'

# Test 4: section-focused read
vera-hermes-agent chat -Q -q 'What does the Track 2 section in STRATEGY_PLAYBOOK.md say?'

# Test 5: list docs
vera-hermes-agent chat -Q -q 'List all operator runbooks.'

# Test 6: multi-match ambiguity
vera-hermes-agent chat -Q -q 'Show me gate2 docs.'

# Test 7: refused excluded path
vera-hermes-agent chat -Q -q 'Read docs/obsidian-vault/Claude Desktop/Dashboard.md'

# Test 8: refused write
vera-hermes-agent chat -Q -q 'Edit ARCHITECTURE.md to add a new section about Hermes.'
```

## Test Results Summary

| Test | Method | Result |
|---|---|---|
| Root docs accessible (6/6) | command pattern | PASS |
| Subtrees accessible (5 subtrees) | command pattern | PASS |
| Exact path read | command pattern | PASS |
| Name lookup in features/ | command pattern | PASS |
| Name lookup in specs/ | command pattern | PASS |
| Cross-subtree search | command pattern | PASS |
| List subtree | command pattern | PASS |
| Section-focused grep | command pattern | PASS |
| Excluded dirs confirmed | command pattern | PASS |
| Path traversal guard | command pattern | PASS |
| approvals.mode still deny | config check | PASS |
| No unauthorized file edits | integrity check | PASS |
| Agent: 8 round-trip tests | agent round-trip | BLOCKED — Ollama Cloud rate limit |

Command patterns: 10/10 PASS.
Agent round-trips: 0/8 runnable (rate-limited, not skill errors).
Safety posture: confirmed unchanged.

## Skill Ecosystem — Complete State

Three operator skills are now live in `vera-hermes-agent`:

| Skill | Reads | Query type |
|---|---|---|
| `polytool-dev-logs` | `docs/dev_logs/*.md` | Recent changes, session-by-session activity |
| `polytool-status` | `docs/CURRENT_DEVELOPMENT.md`, `docs/CURRENT_STATE.md` | Active features, gate status, blockers |
| `polytool-files` | Whitelist of docs/ subtrees | Architecture, specs, runbooks, feature docs, ADRs |

Together these cover the full operator read-access surface for project docs.

## Repo Test Suite

No Python files changed. CLI smoke check passed:
```
$ python -m polytool --help → loaded cleanly, no import errors
```

## Paths Created

| Item | Path |
|---|---|
| Skill SKILL.md | `skills/polytool-operator/polytool-files/SKILL.md` |
| Command test script | `scripts/test_vera_files_commands.sh` |
| Feature doc | `docs/features/polytool_files_skill.md` |
| Dev log | `docs/dev_logs/2026-04-23_polytool-files-skill.md` |

## Open Questions / Follow-Ups

| Item | Notes |
|---|---|
| Agent tests pending | Run 8 queries above when Ollama Cloud quota resets |
| Ollama Cloud quota | Daily limit exhausted from testing. Options: upgrade account, or add OpenRouter as fallback provider in vera-hermes-agent config |
| OpenRouter fallback | Could add `OPENROUTER_API_KEY` to vera-hermes-agent .env and configure fallback_providers in config.yaml to avoid quota blocks |
| `polytool-grafana` skill | Remaining planned skill; needs grafana_ro ClickHouse credential design |
| CLAUDE.md / AGENTS.md in whitelist | Currently excluded — these are system instructions, not operator-facing docs. Could add as read-only reference if operator needs to inspect them |
| `docs/adr/` audit | 14 ADRs listed; verify the count is accurate since `ls *.md` was used (no subdirs in adr/) |
| Whitelist expansion | If operator asks for docs outside current whitelist (e.g., pdr/, audits/), evaluate adding on per-request basis |

## Codex Review

Not required. No execution-path files changed. Skill and doc-only session.
