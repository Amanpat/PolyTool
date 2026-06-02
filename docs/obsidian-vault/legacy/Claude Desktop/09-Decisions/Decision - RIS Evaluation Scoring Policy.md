---
tags: [decision]
date: 2026-04-09
status: accepted
---
# Decision — RIS Evaluation Scoring Policy

## Context
Two scoring approaches were proposed: weighted composite (/5.0) and simple sum (/20). The architect flagged that using both without a canonical gate creates ambiguity about what "passes."

## Decision
Weighted composite + per-dimension floor is the canonical gate. Simple sum is a diagnostic column only.

**Gate logic:**
- Composite = (relevance × 0.30) + (credibility × 0.30) + (novelty × 0.20) + (actionability × 0.20)
- Pass if: composite ≥ 3.0 AND no single dimension < 2
- Score zones: GREEN (≥3.5 / composite ≥12 sum) auto-accept, YELLOW (2.5-3.5 / sum 8-12) escalate, RED (<2.5 / sum <8) reject

**Fail-closed contract:** No provider path can silently pass a document without a valid scored artifact. Score absence is distinct from low score.

**Budget control:** Global 1,500/day Gemini cap with per-source ceilings (Academic 20%, Reddit 25%, Blog 15%, YouTube 5%, GitHub 5%, Escalation 15%, Manual reserve 15%).

## Alternatives Considered
- Simple sum as gate: allows high-credibility/low-relevance docs to sneak through
- No per-dimension floor: same problem — a 5/5/5/1 document shouldn't pass
- No budget control: one noisy source (Reddit) could starve the rest

See [[02-Modules/RIS]], [[Decision - RIS Evaluation Gate Model Swappability]]
