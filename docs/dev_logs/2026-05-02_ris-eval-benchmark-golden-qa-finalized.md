# RIS Eval Benchmark — Golden QA v0 Finalized

**Date:** 2026-05-02  
**Work packet:** L5 bulk-accept review pass — finalize golden_qa_v0.json  
**Author:** operator + Claude Code  

---

## Summary

The 35-pair DRAFT QA set was reviewed, four weak substrings were fixed, and the
final reviewed file was saved as `tests/fixtures/research_eval_benchmark/golden_qa_v0.json`
with `review_status="reviewed"`. Dry-run passed. No baseline was created.

---

## Final QA Pair Count

**35 pairs** — all 35 candidates accepted. No pairs removed.

---

## Rows Edited

Four substrings were replaced. All fixes were verified against
`artifacts/research/raw_source_cache/academic/` body text before writing.

### qa_012 — PDF newline artifact removed

- **Paper:** Black-Scholes for Prediction Markets (aea8351605f4b28c.json)
- **Issue:** Substring `"unifying\nstochastic kernel that options gained from Black"` contained
  a literal `\n` from PDF line-wrap extraction, which would fail exact string matching in any
  retrieval system that normalizes whitespace.
- **Fix:** `"stochastic kernel that options gained from Black"` — starts clean at the beginning
  of the next line, captures the same core concept (the BS-analogy stochastic kernel),
  no newline at start.

### qa_014 — Theorem name replaced with what the theorem proves

- **Paper:** LOB Dynamics in Matching Markets (a3447cebd3b7b513.json)
- **Issue:** Substring `"Threshold Impossibility Theorem"` only verifies the theorem name, which
  appears verbatim in the question itself. A RAG system that returns the question text would pass
  trivially, making this a low-signal test.
- **Fix:** `"cannot close spreads derived from ordinal categorization"` — the core claim the
  theorem proves. Extracted from body: "whichprovesthatlinearcompensation\ncannot close spreads
  derived from ordinal categorization without inducing a regime switch."

### qa_023 — Second bias added

- **Paper:** Interpretable Hypothesis-Driven Trading (f1bfec43f961cf0b.json)
- **Issue:** Substring `"lookahead bias"` only verifies one of the two biases the question asks
  about. A retrieval result mentioning only lookahead bias would pass despite not answering the
  question fully.
- **Fix:** `"overfitting and lookahead bias"` — present in abstract: "designed to mitigate
  overfitting and lookahead bias." Now requires the answer to name both.

### qa_029 — Vague phrase replaced with specific finding

- **Paper:** HF Market Microstructure Noise (3dc8e37cb374e169.json)
- **Issue:** Substring `"more liquid stocks"` is the subject of the question, not the finding.
  Any document mentioning liquid stocks in any context would pass.
- **Fix:** `"have lower noise and noise-to-signal ratio"` — found in a cleaner passage (second
  occurrence in abstract section): "More liq-\nuid stocks have lower noise and noise-to-signal
  ratio." The substring starts after the line break, is clean, and directly states the finding.

---

## Substring Verification Result

All 35 final substrings verified by Python `in` search against the corresponding
`artifacts/research/raw_source_cache/academic/*.json` `payload.body_text`:

```
Verification: 35/35 passed, 0 failed
```

Mapping used:
- b1982ae... → 47eae7fb28cdfde1.json (SoK DePMs)
- 8cebfdb... → aea8351605f4b28c.json (Black Scholes PM)
- e357875... → a3447cebd3b7b513.json (LOB Dynamics)
- 68acefe... → 6f8dfef0413ada61.json (Semi Markov)
- 64d01f0... → f1bfec43f961cf0b.json (Hypothesis Trading)
- 89b902e... → bb81ac9c4c8915a4.json (TradeFM)
- 0c8b3c3... → 3dc8e37cb374e169.json (HF Noise)
- 6e911b4... → 7eee677a3c03ad3f.json (Market Ecology)
- af8935f... → 0ed992a9de186e51.json (Systemic Risk Hawkes)
- 40fd58b... → e6f3c05aba30bfb0.json (FX WM Fix)

---

## Dry-Run Output

```
Corpus loaded: config/research_eval_benchmark_v0_corpus.draft.json
  version=v0, entries=23, review_status=draft
Golden QA loaded: tests/fixtures/research_eval_benchmark/golden_qa_v0.json
  version=v0, pairs=35, review_status=reviewed
Dry-run complete. Inputs are valid.
```

---

## Baseline Status

`artifacts/research/eval_benchmark/baseline_v0.json` — **NOT created**. `--save-baseline`
was not passed. The dry-run flag was used as required.

---

## Next Steps

1. Run `python -m polytool rag-refresh` to populate the lexical index with academic chunks
   (currently empty — known Rule C failure from draft runs).
2. Re-run benchmark without `--dry-run` to get real P@5 values.
3. Once P@5 is non-zero, run `--save-baseline` to lock the baseline.
4. Investigate Rule A (off-topic 30.43%) and Rule D (equation parseable heuristic) failures
   from prior draft runs before declaring the benchmark healthy.

---

## Codex Review

Tier: Skip (fixture JSON + dev log; no execution-path code changed).
