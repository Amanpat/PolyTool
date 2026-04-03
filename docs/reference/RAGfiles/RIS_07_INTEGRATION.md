# RIS_07 — Integration with Master Roadmap
**System:** PolyTool Research Intelligence System  
**Covers:** Dossier pipeline upgrade, SimTrader bridge, auto-discovery loop, LLM complement

---

## Purpose

The RIS is not a standalone system — it connects to every other part of PolyTool. This
document specifies how the research system integrates with existing and planned components
from the master roadmap v5.1.

---

## Integration Map

```
                    ┌─────────────────────┐
                    │    RIS Knowledge     │
                    │    Store (Chroma)    │
                    └──────┬──────────────┘
                           │
         ┌─────────────────┼─────────────────────────┐
         │                 │                           │
         ▼                 ▼                           ▼
┌────────────────┐ ┌──────────────┐ ┌──────────────────────────┐
│ Wallet Scanner │ │  SimTrader   │ │    Dev Agent Sessions    │
│ (existing)     │ │  (existing)  │ │ (Claude Code, ChatGPT)   │
│                │ │              │ │                          │
│ Dossiers write │ │ Hypothesis   │ │ Query knowledge base     │
│ to user_data   │ │ testing uses │ │ before building features │
│                │ │ research     │ │                          │
│ Key findings → │ │ findings as  │ │ precheck command before  │
│ external_      │ │ hypothesis   │ │ coding begins            │
│ knowledge      │ │ candidates   │ │                          │
└────────────────┘ └──────────────┘ └──────────────────────────┘
```

---

## 1. Dossier Pipeline Upgrade

### Current State

The wallet scanning pipeline produces dossiers that go to the `user_data` partition:

```
scan user → ClickHouse ingest → dossier → LLM bundle → user_data partition
```

The dossiers contain raw trade data, strategy detectors, PnL computation, CLV analysis.
They're useful for analyzing individual wallets but their KEY FINDINGS are locked inside
individual user dossiers and not queryable as general knowledge.

### Upgraded Flow

Add an extraction step that pulls key findings from dossiers and writes them to
`external_knowledge` as reusable knowledge:

```
scan user → ClickHouse ingest → dossier → LLM bundle → user_data partition
                                              │
                                              ▼
                                    LLM extract key findings
                                              │
                                              ▼
                                    Write to external_knowledge
                                    (source_type: wallet_analysis)
                                    (confidence_tier: PRACTITIONER)
```

**What gets extracted:**
- Strategy classification (what the wallet is actually doing, not what it claims)
- Entry/exit patterns (price levels, timing, market types)
- Performance metrics (win rate, CLV, pair costs if applicable)
- Market preferences (which categories, which market characteristics)
- Risk management patterns (position sizes relative to account, holding duration)

**Implementation:**

```python
# packages/research/integration/dossier_extractor.py

def extract_dossier_findings(dossier_path: str, llm) -> list[dict]:
    """Extract key findings from a wallet dossier for external_knowledge."""
    dossier_text = Path(dossier_path).read_text()
    
    prompt = f"""You are analyzing a wallet dossier from a Polymarket trader.
Extract 3-5 key findings that would be useful for strategy development.

For each finding, provide:
- A clear, specific statement of what this wallet does
- The evidence from the dossier supporting this
- Which strategy track this is relevant to (market_maker, crypto_pairs, sports_model)

Focus on BEHAVIOR, not identity. We care about WHAT they do, not WHO they are.

Dossier:
{dossier_text}

Findings (JSON array):"""
    
    response = llm.generate(prompt, response_format="json")
    findings = json.loads(response)
    
    documents = []
    for finding in findings:
        doc = {
            "text": finding["statement"] + "\n\nEvidence: " + finding["evidence"],
            "title": f"Wallet Analysis Finding: {finding['statement'][:80]}",
            "source_type": "wallet_analysis",
            "confidence_tier": "PRACTITIONER",
            "freshness_tier": "CURRENT",
            "related_strategy_tracks": finding.get("relevant_tracks", []),
        }
        documents.append(doc)
    
    return documents
```

**When this runs:**
- After every `wallet-scan` completion
- After batch runs (`alpha-distill`)
- Can also be run retroactively on existing dossiers in `artifacts/dossiers/users/`

**Phase R0 example:** The gabagool22 findings currently exist only in chat history
and memory. Phase R0 manually seeds these into `external_knowledge`. The upgraded
pipeline automates this for all future wallet scans.

---

## 2. Auto-Discovery → Knowledge Loop

### Current State (Master Roadmap Phase 2)

The Candidate Scanner discovers profitable wallets:
```
9 signals → score wallets → top candidates → wallet-scan → dossiers
```

### Upgraded Flow with RIS

```
Candidate Scanner discovers wallet
    → wallet-scan generates dossier
    → dossier_extractor pulls key findings
    → findings written to external_knowledge
    → research briefs now cite wallet behavior alongside academic research
    → Over time: growing library of "what profitable wallets actually do"
```

**The compounding effect:** The earlier auto-discovery starts, the richer the historical
dataset. A wallet scanned today with 30 days of history → scanned again in 6 months
with 210 days of history → the dossier now contains seasonal patterns, market regime
behavior, and long-term strategy evolution that a single scan would miss.

**Wallet watchlist integration:** The roadmap's Phase 2 Wallet Watchlist (top 20-50
wallets monitored every 15 min) feeds into this loop. New positions from watched wallets
→ Discord alert (existing) + dossier update → findings extracted → knowledge base grows.

---

## 3. SimTrader Bridge (Phase R5 / v2)

### Hypothesis Generation from Research

When the synthesis engine identifies an actionable finding with HIGH confidence, it can
automatically generate a hypothesis candidate for the existing hypothesis registry:

```
Research brief identifies finding:
  "Jon-Becker data shows Entertainment markets have 4.79pp maker-taker gap.
   No existing strategy targets Entertainment category specifically."
    │
    ▼
Generate hypothesis candidate:
  {
    "name": "entertainment_market_maker_v1",
    "source": "research_brief_2026-04-15",
    "strategy_type": "market_maker",
    "market_category": "entertainment",
    "hypothesis": "Market making on Entertainment markets with category-specific
                   parameters will yield higher returns than the current
                   category-agnostic approach due to the 4.79pp maker edge.",
    "evidence_doc_ids": ["ext_2026_jb_finding_2", "ext_2026_arxiv_2510.15205"],
    "suggested_parameters": {
      "category_weight": "entertainment",
      "expected_edge_pp": 4.79,
      "min_volume_24h": 500,
    }
  }
    │
    ▼
Register in hypothesis registry
    │
    ▼
SimTrader Level 1 auto-test (20+ tape replay)
    │
    ▼
Results written to research partition (with validation_gate_pass)
```

**Human gate:** The hypothesis is auto-generated and auto-tested, but promoting it to
live capital still requires human approval (Discord button). This matches the master
roadmap's Human-in-the-Loop Policy.

### Feedback Loop (Phase 6)

When a strategy is validated and deployed:
- KEEP (perf_ratio ≥0.75) → cited `external_knowledge` docs marked `CONSISTENT_WITH_RESULTS`
- AUTO_DISABLE (perf_ratio <0.40) → cited docs marked `CONTRADICTED`

This creates empirical credibility scores on the knowledge base itself. Over time, the
research system learns which sources produce strategies that actually work.

---

## 4. Dev Agent Integration

### How dev agents (Claude Code, ChatGPT, Codex) use the RIS

**Direct query via MCP (existing):**
The `polytool:polymarket_rag_query` MCP tool already connects to the Chroma knowledge
base. Once `external_knowledge` is populated, dev agents can query research material
directly without any code changes.

Example: Claude Code working on the market maker spread calculation can query:
```
"What does Avellaneda-Stoikov say about optimal spread width under inventory risk?"
```
And receive the seeded academic paper summary with specific formula references.

**Precheck before coding:**
Before starting any feature development session, the operator runs:
```bash
python -m polytool research-precheck run --idea "Implement momentum signal for crypto pair bot" --no-ledger
```
The precheck report is pasted into the dev agent session as context, ensuring the agent
knows what existing research says about the approach.

**CLAUDE.md integration:**
Add to `CLAUDE.md`:
```
## Research Intelligence System
Before implementing a new strategy or feature, check existing research:
- Run: python -m polytool research-precheck run --idea "description" --no-ledger
- Query: python -m polytool rag-query --question "relevant topic" --hybrid --knowledge-store default
- If the precheck returns STOP, do not proceed without discussing with the operator.
```

### How the ChatGPT architect uses the RIS

**[v2 deferred — requires manual Google Drive sync setup]**

The ChatGPT architect (Google Drive connector) can access research reports saved to
`artifacts/research/reports/`. When generating specs and prompts for dev agents, the
architect references relevant research briefs to ground the specifications in empirical
evidence rather than assumptions.

---

## 5. LLM Fast-Research Complement

### Problem

The RIS runs 24/7 but processes documents slowly (evaluate each one, embed, store). When
a developer needs an answer RIGHT NOW during a coding session, the RIS may not have the
information yet.

### Solution: Complementary fast-research via LLMs

| System | Speed | Persistence | Coverage | Use Case |
|--------|-------|-------------|----------|----------|
| RIS (built system) | Slow (hours) | Permanent | Comprehensive | Background knowledge accumulation |
| GLM-5 Turbo | Fast (seconds) | Session-only | Web search | On-demand deep dives during dev sessions |
| Gemini Flash | Fast (seconds) | Session-only | Web search | Quick fact-checking during dev sessions |
| ChatGPT | Fast (seconds) | Project-scoped | Training + web | Architecture decisions, spec generation |

### Bridge: Fast research → RIS

When an LLM fast-research session produces valuable findings:

1. Operator identifies the finding as worth preserving
2. `python -m polytool research-acquire --url "source_url" --source-family blog --no-eval` captures the source permanently
3. Or manually writes a summary: `python -m polytool research-ingest --text "..." --title "..." --source-type manual --no-eval`
4. The finding goes through the evaluation gate and enters `external_knowledge`
5. Now it's permanently queryable by all future sessions

Over time, the RIS absorbs the best findings from ad-hoc research sessions, building
institutional memory that outlasts any single chat conversation.

### Does the LLM replace the RIS?

No. They serve different purposes:

- **LLMs are ephemeral.** Chat context disappears. Training knowledge has a cutoff.
  Answers aren't verified against your specific domain knowledge.
- **The RIS is persistent and domain-specific.** It contains verified, scored, and
  structured knowledge specifically about prediction market trading. It builds
  compounding institutional memory. It knows what has already been tried and failed.
- **LLMs can't do prechecks.** An LLM doesn't know that gabagool22's wallet behavior
  contradicts pair accumulation unless that finding is in its context. The RIS does —
  it's in the knowledge base, queryable permanently.

The RIS is the long-term memory. LLMs are the fast-thinking short-term processor.
They complement each other.

---

## 6. Master Roadmap Integration Summary

### What RIS Replaces

| Roadmap Item | RIS Replacement |
|-------------|----------------|
| Phase 1B: "Seed Jon-Becker findings into RAG" | Phase R0 — done as RIS foundation |
| Phase 2: "LLM-Assisted Research Scraper" | Phase R1 + R2 — more comprehensive |
| Phase 2: "Domain Specialization Layer" | Informed by R3 reports per category |
| Phase 3: "Unified Chroma collection (external_knowledge)" | Phase R0-R2 populates this |

### What RIS Accelerates

| Roadmap Item | How RIS Helps |
|-------------|---------------|
| Phase 4: Autoresearch hypothesis generation | R5 bridge generates hypothesis candidates from research findings |
| Phase 1A/B/C: Strategy development | Precheck command prevents wasted development cycles |
| Phase 2: Wallet analysis | Dossier findings flow into queryable knowledge base |
| Phase 6: Feedback loop | validation_status updates create empirical credibility |

### What RIS Does NOT Replace

- Wallet scanning pipeline (user_data partition — unchanged)
- SimTrader engine and tape library (separate system)
- Live bot execution and risk management (separate system)
- Signals pipeline (real-time news → market reaction measurement — Phase 3)
- The `research` partition write-gate (requires validation_gate_pass — Phase 4+)

---

## 7. Development Dependencies

### RIS has NO blocking dependencies on other systems

The RIS can be built and deployed independently of:
- Phase 1A (crypto pair bot)
- Phase 1B (market maker)
- Phase 1C (sports model)
- SimTrader
- VPS setup
- Live trading accounts

This is by design — the research system is a knowledge tool, not a trading tool.
It runs on the dev machine, doesn't need Polymarket connectivity, and doesn't
require ClickHouse or Docker (Chroma is a pip install).

### Other systems depend on RIS (softly)

- Dev agent sessions benefit from populated `external_knowledge`
- Autoresearch hypothesis generation (Phase 4) needs research findings
- Market selection engine (Phase 1B) benefits from Jon-Becker category data

These are soft dependencies — the other systems work without RIS, they just work
better with it.

---

*End of RIS_07 — Integration with Master Roadmap*
