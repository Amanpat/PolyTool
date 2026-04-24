---
name: polytool-files
description: Read approved PolyTool project docs by path or name. Read-only. Whitelisted paths only.
version: 1.0.0
category: polytool-operator
metadata:
  hermes:
    tags: [polytool, files, read-only, operator, docs, architecture]
---

# polytool-files

## Purpose

Reads approved PolyTool project documentation by exact path, doc name, or folder. Complements the narrower skills:
- Use **polytool-dev-logs** for `docs/dev_logs/` entries.
- Use **polytool-status** for `CURRENT_DEVELOPMENT.md` / `CURRENT_STATE.md` status queries.
- Use **polytool-files** for everything else in the approved whitelist: architecture, plan of record, feature docs, specs, runbooks, ADRs.

**Repo root (WSL):** `/mnt/d/Coding Projects/Polymarket/PolyTool`

---

## Approved Whitelist

### Root-level docs (exact paths)

```
docs/ARCHITECTURE.md
docs/PLAN_OF_RECORD.md
docs/STRATEGY_PLAYBOOK.md
docs/RISK_POLICY.md
docs/ROADMAP.md
docs/INDEX.md
docs/CURRENT_DEVELOPMENT.md
docs/CURRENT_STATE.md
docs/DOCS_BEST_PRACTICES.md
docs/PROJECT_OVERVIEW.md
docs/README.md
```

### Approved subtrees (any .md inside)

```
docs/features/
docs/specs/
docs/reference/
docs/runbooks/
docs/adr/
```

### Not in scope for this skill

```
docs/dev_logs/          → use polytool-dev-logs
docs/obsidian-vault/    → planning notes, not project docs
docs/archive/           → historical, superseded docs
docs/eval/              → evaluation artifacts
docs/external_knowledge/→ ingested research content
docs/pdr/               → planning decision records
docs/audits/            → audit reports
```

**Anything outside `docs/` is always refused** — no code, no config, no .env, no artifacts, no hidden files.

---

## When to Use

- "Show me the architecture doc."
- "Read PLAN_OF_RECORD.md."
- "What does the Track 2 feature doc say?"
- "Find the spec for Gate 2 tape acquisition."
- "List all feature docs."
- "What does the STRATEGY_PLAYBOOK say about Track 1?"
- "Show me the runbook for Track 2."
- "What ADRs exist?"

---

## Hard Boundaries

**ONLY read from the approved whitelist above.**

**NEVER:**
- Read any path outside `docs/`
- Read from excluded subdirectories (dev_logs, obsidian-vault, archive, eval, external_knowledge, pdr, audits)
- Modify any file
- Execute `python -m polytool` or any live command
- Print API keys, credentials, or secrets
- Use shell commands beyond: `cat`, `head`, `grep`, `ls`, `find`, `wc`, `sed`, `tail`

If the operator asks for an out-of-scope path, **refuse and explain** which skill handles it (if any).

---

## Procedure

### Path validation (run before every read)

Before reading any file, verify ALL of:
1. Path starts with `/mnt/d/Coding Projects/Polymarket/PolyTool/docs/`
2. Path does NOT include: `obsidian-vault`, `dev_logs`, `archive`, `eval`, `external_knowledge`, `pdr`, `audits`, `..`
3. Path ends with `.md`
4. File is not a hidden file (no `/.`)

If any check fails: do not read. Explain the refusal.

### Query: Exact path read

```bash
cat "/mnt/d/Coding Projects/Polymarket/PolyTool/docs/ARCHITECTURE.md"
```

### Query: Doc-name lookup in a subtree

Search by name fragment within an approved subtree:
```bash
ls "/mnt/d/Coding Projects/Polymarket/PolyTool/docs/features/" | grep -i "KEYWORD"
```

```bash
ls "/mnt/d/Coding Projects/Polymarket/PolyTool/docs/specs/" | grep -i "KEYWORD"
```

If one match: read it. If multiple matches: list them and ask operator which one.

### Query: Cross-subtree name search

```bash
REPO="/mnt/d/Coding Projects/Polymarket/PolyTool"
find "$REPO/docs/features" "$REPO/docs/specs" "$REPO/docs/reference" "$REPO/docs/runbooks" "$REPO/docs/adr" -name "*.md" | grep -i "KEYWORD" | sed "s|$REPO/||"
```

### Query: List all docs in a subtree

```bash
ls "/mnt/d/Coding Projects/Polymarket/PolyTool/docs/features/" | head -30
ls "/mnt/d/Coding Projects/Polymarket/PolyTool/docs/specs/"
ls "/mnt/d/Coding Projects/Polymarket/PolyTool/docs/runbooks/"
ls "/mnt/d/Coding Projects/Polymarket/PolyTool/docs/adr/"
```

### Query: Section-focused read

Find the heading line, then read from there:
```bash
grep -n "## HEADING" "/mnt/d/Coding Projects/Polymarket/PolyTool/docs/FILENAME.md"
# Note the line number N, then:
sed -n 'N,/^## /p' "/mnt/d/Coding Projects/Polymarket/PolyTool/docs/FILENAME.md" | head -60
```

Or simpler:
```bash
grep -A 40 "^## HEADING" "/mnt/d/Coding Projects/Polymarket/PolyTool/docs/FILENAME.md" | head -40
```

---

## Ambiguity Handling

**Multiple matches:** List all candidates with their paths. State which one was used (most specific match, or most recently modified). Example:

```
Found 3 docs matching "gate2":
1. docs/features/FEATURE-gate2-preflight.md
2. docs/features/FEATURE-gate2-eligible-tape-acquisition.md
3. docs/specs/SPEC-0014-gate2-eligible-tape-acquisition.md

Using (1) — most specific match for "gate2 preflight". Reply "2" or "3" to read a different one.
```

**Ambiguous name with no clear winner:** List candidates and ask operator to specify. Do not guess.

**Zero matches:** Say "No approved docs match 'KEYWORD' in the checked subtrees." Do not widen scope to find it elsewhere.

---

## Output Format

**Concise summary** (default for long docs): 4-8 bullets covering purpose, key decisions, current status.

**Full read**: return entire file content if operator asks or file is short (< 100 lines).

**Section excerpt**: return the named section verbatim with surrounding context.

Always prefix the response with the file path used: `[docs/features/FEATURE-foo.md]`

---

## Guardrails Checklist

Before any command:
- [ ] Path passes all 4 validation checks above
- [ ] Command is read-only (cat / head / grep / ls / find / sed / tail / wc)
- [ ] Output does not contain API keys, passwords, or secrets

If any check fails: refuse and explain.

---

## Out-of-Scope Refusals

**"Read packages/polymarket/simtrader/broker_sim.py"**
→ "polytool-files only reads approved docs under docs/. Use Claude Code for code inspection."

**"Read docs/dev_logs/2026-04-23_ris_wp4d.md"**
→ "Dev logs are served by polytool-dev-logs, not this skill."

**"Read docs/obsidian-vault/Claude Desktop/..."**
→ "obsidian-vault is excluded. Those are planning notes, not project docs."

**"Read .env"**
→ "Only approved .md files inside docs/ are readable. Environment files are never accessible."

**"Edit ARCHITECTURE.md to add a section"**
→ "This instance is read-only. I cannot modify files."

**"Read config/benchmark_v1.lock.json"**
→ "Only approved docs under docs/ are readable. config/ is excluded."
