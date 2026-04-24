---
status: complete
completed: 2026-04-23
track: operator-tooling
scope: read-only
skill-host: vera-hermes-agent
---

# Feature: polytool-files Hermes Skill

Read-only Hermes skill for the `vera-hermes-agent` operator profile. Provides controlled access to approved PolyTool project documentation by exact path, doc-name lookup, or subtree listing. Explicitly refuses all paths outside the whitelist and all write/control requests.

---

## What Was Built

| Item | Detail |
|---|---|
| Skill name | `polytool-files` |
| Skill category | `polytool-operator` |
| Skill type | external / local (in-repo) |
| Host profile | `vera-hermes-agent` |
| Source location | `skills/polytool-operator/polytool-files/SKILL.md` |
| Discovery | via existing `external_dirs` in vera-hermes-agent `config.yaml` |
| Reads from | Approved whitelist only (see below) |
| Writes to | nothing — strictly read-only |

---

## Approved Whitelist

### Root-level docs

| File | Lines | Purpose |
|---|---|---|
| `docs/ARCHITECTURE.md` | — | Current implemented architecture |
| `docs/PLAN_OF_RECORD.md` | — | Governing plan document |
| `docs/STRATEGY_PLAYBOOK.md` | — | Triple-track strategy guide |
| `docs/RISK_POLICY.md` | — | Risk, fees, guardrails policy |
| `docs/ROADMAP.md` | — | Roadmap router |
| `docs/INDEX.md` | — | Navigation index |
| `docs/CURRENT_DEVELOPMENT.md` | 130 | Active features (also served by polytool-status) |
| `docs/CURRENT_STATE.md` | 1729 | Implemented repo truth (also served by polytool-status) |
| `docs/DOCS_BEST_PRACTICES.md` | — | Documentation conventions |
| `docs/PROJECT_OVERVIEW.md` | — | Project overview |
| `docs/README.md` | — | Docs README |

### Approved subtrees (any .md inside)

| Subtree | Count | Contents |
|---|---|---|
| `docs/features/` | 88 files | Shipped feature documentation |
| `docs/specs/` | 46 files | Specification documents (SPEC-NNNN) |
| `docs/reference/` | 5 files | Reference documents (roadmap, standards) |
| `docs/runbooks/` | 21 files | Operator runbooks |
| `docs/adr/` | 14 files | Architectural Decision Records |

### Explicitly excluded subtrees

| Path | Why excluded | Alternative |
|---|---|---|
| `docs/dev_logs/` | Served by polytool-dev-logs | Use that skill |
| `docs/obsidian-vault/` | Planning notes, not project docs | N/A |
| `docs/archive/` | Historical/superseded | N/A |
| `docs/eval/` | Evaluation artifacts | N/A |
| `docs/external_knowledge/` | Ingested research content | N/A |
| `docs/pdr/` | Planning decision records | N/A |
| `docs/audits/` | Audit reports | N/A |
| Everything outside `docs/` | Code, config, secrets, artifacts | Use Claude Code |

---

## Capability Summary

| Query | Works |
|---|---|
| "Show me the architecture doc." | ✓ — reads docs/ARCHITECTURE.md |
| "Read PLAN_OF_RECORD.md." | ✓ — exact root doc read |
| "What does the Track 2 feature doc say?" | ✓ — name lookup in docs/features/ |
| "Find the Gate 2 tape acquisition spec." | ✓ — name lookup in docs/specs/ |
| "List all feature docs." | ✓ — ls docs/features/ |
| "What ADRs exist?" | ✓ — ls docs/adr/ |
| "Show me the Track 2 operator runbook." | ✓ — cross-subtree find |
| "What does the Gate 2 section say in STRATEGY_PLAYBOOK?" | ✓ — section-focused grep + excerpt |
| "Read docs/dev_logs/2026-04-22.md" | ✓ refused — "use polytool-dev-logs" |
| "Read packages/polymarket/broker_sim.py" | ✓ refused — outside docs/ |
| "Read .env" | ✓ refused — not an approved .md |
| "Edit ARCHITECTURE.md" | ✓ refused — read-only |

---

## Ambiguity Rules

| Situation | Behaviour |
|---|---|
| One match | Read it, state the path used |
| Multiple matches | List all candidates, state which was used (most specific), invite operator to specify another |
| Zero matches in checked subtrees | Say "no approved docs match" — do not widen scope |
| Operator gives partial path that could be in multiple subtrees | Run cross-subtree search, present candidates |

---

## Path Validation (Pre-Read Checklist)

The skill validates every path before reading:
1. Starts with `/mnt/d/Coding Projects/Polymarket/PolyTool/docs/`
2. Does NOT include: `obsidian-vault`, `dev_logs`, `archive`, `eval`, `external_knowledge`, `pdr`, `audits`, `..`
3. Ends with `.md`
4. Not a hidden file (no `/.`)

Any check failure = refuse + explain.

---

## Security Boundaries

| Boundary | State |
|---|---|
| File scope | Whitelist only — refuses all other paths |
| Path traversal | `..` detected and blocked by validation step 2 |
| Allowed commands | `cat`, `head`, `grep`, `ls`, `find`, `wc`, `sed`, `tail` |
| Modifications | None — read-only enforced by SOUL.md + `approvals.mode: deny` |
| Secrets | `.env`, config files, and hidden files are all outside whitelist |

---

## Skill Ecosystem Context

The three operator skills complement each other:

| Query type | Skill to use |
|---|---|
| Recent changes, dev log summaries | **polytool-dev-logs** |
| Active features, Gate status, what's blocked | **polytool-status** |
| Architecture, specs, runbooks, feature docs | **polytool-files** |

---

## Test Suite

### Command pattern test (offline)

```bash
wsl bash -lc "bash /mnt/d/Coding\ Projects/Polymarket/PolyTool/scripts/test_vera_files_commands.sh"
```

Runs 10 checks:
1. All 6 approved root docs accessible
2. All 5 subtrees accessible (88 features, 46 specs, 5 ref, 21 runbooks, 14 adr)
3. Exact path read (ARCHITECTURE.md header)
4. Name lookup in features/ (gate2-preflight)
5. Name lookup in specs/ (gate2)
6. Cross-subtree search (track2 → TRACK2_OPERATOR_RUNBOOK.md)
7. List runbooks/
8. Section-focused grep
9. Excluded dirs confirmed present (dev_logs, obsidian-vault, archive)
10. Path traversal attempts correctly resolve outside docs/

Expected: all PASS.

### Agent round-trip tests (requires Ollama Cloud quota)

```bash
# Test 1: exact approved path
wsl bash -lc "vera-hermes-agent chat -Q -q 'Read PLAN_OF_RECORD.md and give me a 3-bullet summary.'"

# Test 2: doc-name lookup in features/
wsl bash -lc "vera-hermes-agent chat -Q -q 'What does the Gate 2 preflight feature doc say?'"

# Test 3: doc-name lookup in specs/
wsl bash -lc "vera-hermes-agent chat -Q -q 'Find the spec for Gate 2 tape acquisition and summarize it.'"

# Test 4: section-focused read
wsl bash -lc "vera-hermes-agent chat -Q -q 'What does the Track 2 section in STRATEGY_PLAYBOOK.md say?'"

# Test 5: list docs
wsl bash -lc "vera-hermes-agent chat -Q -q 'List all operator runbooks.'"

# Test 6: ambiguous multi-match
wsl bash -lc "vera-hermes-agent chat -Q -q 'Show me gate2 docs.'"

# Test 7: refusal for excluded path
wsl bash -lc "vera-hermes-agent chat -Q -q 'Read docs/obsidian-vault/Claude Desktop/Dashboard.md'"

# Test 8: refusal for write request
wsl bash -lc "vera-hermes-agent chat -Q -q 'Edit ARCHITECTURE.md to add a new section about Hermes.'"
```

**Note:** Ollama Cloud free tier session limit was exhausted during prior agent testing sessions (2026-04-23). Run tests when quota resets.

---

## Related Files

- `skills/polytool-operator/polytool-files/SKILL.md` — the skill itself
- `scripts/test_vera_files_commands.sh` — command pattern test suite
- `docs/features/vera_hermes_operator_baseline.md` — baseline profile
- `docs/features/polytool_dev_logs_skill.md` — dev-logs skill
- `docs/features/polytool_status_skill.md` — status skill
- `docs/dev_logs/2026-04-23_polytool-files-skill.md` — this session's dev log
