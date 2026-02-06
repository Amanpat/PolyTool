# Hypothesis Standard

This document defines the standardized prompt template, output requirements, and
quality rubric for LLM-assisted dossier examination reports.

---

## Standardized Prompt Template

Use this prompt verbatim (or via the auto-generated `prompt.txt` from `examine`).
Replace placeholders with actual values.

```text
You are an LLM assistant analyzing a Polymarket trader's activity.

INSTRUCTIONS:
1. Every factual claim MUST include a citation using [file_path: ...] format.
2. Do NOT invent details or use outside knowledge.
3. If a claim is not supported by evidence, say so explicitly.
4. Reference specific trades using [trade_uid: <uid>] format.

REQUIRED OUTPUTS:

1. hypothesis.md - Markdown report with:
   - Executive summary (3-6 bullets)
   - Key observations with citations
   - Hypotheses table: claim, evidence, confidence, falsification method
   - Limitations section (what the evidence does NOT show)
   - Missing data for backtest section

2. hypothesis.json - JSON matching docs/specs/hypothesis_schema_v1.json with:
   - schema_version: "hypothesis_v1"
   - metadata: { user_slug, run_id, created_at_utc, model }
   - executive_summary: { bullets: [...] }
   - hypotheses: [ { claim, evidence[], confidence, falsification } ]
   - observations: [ { statement, evidence[] } ]
   - limitations: [...]
   - missing_data_for_backtest: [...]

EVIDENCE FILES (pasted in this order):
1. memo.md - Human-readable research memo
2. dossier.json - Structured data (key sections)
3. manifest.json - Export metadata
4. RAG excerpts with [file_path: ...] headers

CITATION FORMAT:
[file_path: kb/users/<slug>/notes/2026-02-03.md]
[trade_uid: abc123def456...]

User: {user_handle}
Window: {window_days} days
Dossier path: {dossier_path}
Bundle path: {bundle_path}
```

---

## Output Requirements

### Both Artifacts Are Required

Every examination run MUST produce:

1. **hypothesis.md** - Human-readable Markdown report.
2. **hypothesis.json** - Machine-readable structured data conforming to
   `docs/specs/hypothesis_schema_v1.json`.

If the LLM fails to produce the JSON, the operator must manually construct it
from the Markdown report before running `llm-save`.

### Citation Rules

- Every factual claim must cite at least one source using `[file_path: ...]`.
- Trade-specific claims must reference trade UIDs using `[trade_uid: ...]`.
- If a claim cannot be supported by the provided evidence, the report must
  explicitly state: "Not supported by provided evidence."
- Do not cite files that were not provided in the bundle.

### Evidence Minimums

- Each hypothesis must include at least **3 supporting trade_uids**.
- Each hypothesis must include a **falsification method** that describes a
  concrete, actionable test that could disprove the claim.
- The `confidence` field must be one of: `high`, `medium`, `low`.

### missing_data_for_backtest (Required Field)

The `missing_data_for_backtest` array in hypothesis.json must list every data
gap that would need to be filled before the hypothesis could be backtested.
Common entries:

- "Historical orderbook depth at trade time"
- "Pre-trade information context (news, odds movements)"
- "Exact fee rates at time of each trade"
- "Event start times for timing analysis"
- "Settlement prices for UNKNOWN_RESOLUTION positions"
- "Position snapshots between ingestion windows"

If the list is empty, the hypothesis is considered `backtest_ready`. In practice,
no hypotheses will be backtest_ready until Roadmap 3 data gaps are closed.

---

## Quality Rubric

### What Good Looks Like

A high-quality hypothesis report:

| Criterion | Good | Bad |
|-----------|------|-----|
| **Executive summary** | 3-6 bullets that capture the key finding; a reader skipping everything else gets the point | Vague generalities like "the trader is active" |
| **Specificity** | "Win rate on sports markets entered below 0.30 is 72% (N=18)" | "The trader seems to do well on cheap markets" |
| **Citations** | Every number traces to a file_path or trade_uid | Numbers appear without sources |
| **Falsification** | "If win rate drops below 50% on the next 20 sub-0.30 entries, reject H1" | "Could be wrong" |
| **Confidence calibration** | `high` only when N>=20, edge>10%, multiple segments confirm | `high` on 3 trades |
| **Limitations** | Explicit list of what the evidence cannot show | Implied or missing |
| **Missing data** | Specific data items needed: "historical orderbook at trade time" | Empty list or generic "more data" |

### Confidence Level Guidelines

| Level | When to Use |
|-------|------------|
| **high** | N >= 20 resolved positions; edge > 10% over implied; consistent across 2+ segmentation axes; falsification test has clear threshold |
| **medium** | N >= 10; edge > 5%; at least 1 segmentation axis tested; falsification is possible but data-limited |
| **low** | N < 10 or edge < 5%; pattern observed but could be noise; significant data gaps exist |

### Anti-Patterns to Avoid

- **Cherry-picking**: Selecting only trades that support the hypothesis while
  ignoring contradictory evidence. The report must address both.
- **Survivorship bias**: Only analyzing resolved markets. PENDING positions
  must be noted separately.
- **Category confusion**: Claiming a "sports expert" pattern when only 5 of 50
  trades are sports markets.
- **Over-precision**: Reporting 4 decimal places on a 10-trade sample.
- **Causal claims**: "The trader knew X" when the data only shows timing
  correlation. Always use "consistent with" rather than "because of."

---

## Saving the Report

After the LLM produces hypothesis.md and hypothesis.json:

```powershell
python -m polytool llm-save --user "@handle" --model "model-name" --report-path "path/to/hypothesis.md" --prompt-path "path/to/prompt.txt" --input "path/to/bundle.md" --tags "exam,report"
```

This writes to `kb/users/<slug>/llm_reports/<date>/<model>_<run_id>/` and
creates an LLM_note summary in `kb/users/<slug>/notes/LLM_notes/`.

Then rebuild the RAG index so the report is searchable:

```powershell
python -m polytool rag-index --roots "kb,artifacts" --rebuild
```

---

## Schema Reference

The full JSON schema is at `docs/specs/hypothesis_schema_v1.json`. Key
structural elements:

```
hypothesis_v1
├── metadata
│   ├── user_slug (required)
│   ├── run_id (required)
│   ├── created_at_utc (required)
│   ├── model (required)
│   ├── proxy_wallet
│   ├── dossier_export_id
│   └── window_days
├── executive_summary
│   ├── bullets[] (required, 1-10)
│   └── overall_assessment (enum)
├── hypotheses[] (required)
│   ├── id (H1, H2, ...)
│   ├── claim (required)
│   ├── evidence[] (required, min 1)
│   │   ├── text (required)
│   │   ├── file_path
│   │   ├── trade_uids[]
│   │   └── metrics{}
│   ├── confidence (required: high/medium/low)
│   ├── falsification (required)
│   ├── next_feature_needed
│   └── tags[]
├── observations[]
│   ├── statement (required)
│   └── evidence[] (required)
├── limitations[]
├── missing_data_for_backtest[]
└── next_features_needed[]
```
