# 2026-05-05 - L3.2 Allow-Label Candidate Discovery

## Summary

Ran metadata-only L3.2 allow-label discovery with the three operator-specified
small arXiv searches. No labels were applied. No PDFs were downloaded. Marker was
not run. No ingestion, indexing, or SVM training was run.

Outcome: 2 pending candidates are available after discovery. At least 6 strong
allow candidates are not available from this run.

## Files Changed

- `docs/dev_logs/2026-05-05_l3-2_allow-label-candidate-discovery.md` - records
  commands, queue counts, pending candidates, and operator label recommendations.

No code was edited.

## Current Counts

Source of truth: `python -m polytool research-prefetch-review counts` after the
metadata-only discovery run.

| Counter | Value |
|---|---:|
| Total queued | 56 |
| Labeled in queue | 54 |
| Allow labels | 24 |
| Reject labels | 30 |
| Pending unlabeled | 2 |

SVM trigger remains blocked: need 6 more allow labels and 0 more reject labels.

## Pending Candidates

| Candidate ID | Score | Recommended label | Title | URL |
|---|---:|---|---|---|
| `33b0fb900395` | 0.9975 | allow | Unravelling the Probabilistic Forest: Arbitrage in Prediction Markets | https://arxiv.org/abs/2508.03474 |
| `cd5bc6b5dc9a` | 0.8808 | reject | Impact of arbitrage between leveraged ETF and futures on market liquidity during market crash | https://arxiv.org/abs/2603.05862 |

Recommendation rationale:

- `33b0fb900395`: strong allow candidate. It is directly about prediction
  markets and arbitrage.
- `cd5bc6b5dc9a`: not a strong allow candidate for this label batch. It is about
  leveraged ETFs/futures and market liquidity, not Polymarket, prediction
  markets, decentralized prediction markets, AMMs, or betting markets.

## Operator Label Commands

Likely allow candidates only:

```powershell
python -m polytool research-prefetch-review label 33b0fb900395 allow
```

No command is recommended for `cd5bc6b5dc9a` as a likely allow candidate.

## Commands Run

### Session-start checks

Command:

```powershell
git status --short
```

Output:

```text
 M docs/CURRENT_DEVELOPMENT.md
 M docs/INDEX.md
 M docs/obsidian-vault/.obsidian/workspace.json
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Marker_Canonical_Academic_Parse_Queue_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
 M "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md"
 M "docs/obsidian-vault/Claude Desktop/Current-Focus.md"
 M packages/research/relevance_filter/queue_store.py
 M polytool/__main__.py
?? docs/dev_logs/2026-05-05_codex-rereview-marker-canonical-parse-queue-v0.md
?? docs/dev_logs/2026-05-05_codex-review-l3-2-prefetch-label-discovery.md
?? docs/dev_logs/2026-05-05_codex-verify-l3-2-label-state.md
?? docs/dev_logs/2026-05-05_l3-2-prefetch-label-discovery-activation.md
?? docs/dev_logs/2026-05-05_l3-2-prefetch-label-discovery-impl.md
?? docs/dev_logs/2026-05-05_marker-canonical-parse-queue-v0-closeout.md
?? docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Prefetch_Label_Discovery_Mode_md.ajson
?? "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md"
?? tests/test_ris_prefetch_discovery.py
?? tools/cli/research_prefetch_discover.py
```

Command:

```powershell
git log --oneline -5
```

Output:

```text
be8b4f2 fix(ris): resolve Codex FAIL blockers - Marker queue v0
7b81a7a Marker Parser added
a4fdcac docs(ris): close out Marker control surface validation - L1 still blocked
e01efd4 feat(ris): Marker single-paper validation control surface
38a13c2 docs(ris): short-paper Marker smoke validation - systematic timeout diagnosis
```

Command:

```powershell
python -m polytool --help
```

Result: exit 0. CLI loaded successfully and listed both L3.2 commands:

```text
research-prefetch-review  List/label L3 hold-review queue items; export label counts for SVM
research-prefetch-discover  L3.2 metadata-only arXiv discovery: score + enqueue for labels (no PDF)
```

### Metadata-only discovery

Command:

```powershell
python -m polytool research-prefetch-discover --search "Polymarket prediction market arbitrage liquidity" --max-results 5 --include-allow --decision-filter all
```

Output:

```text
arXiv metadata discovery: 'Polymarket prediction market arbitrage liquidity'
  source_family    : academic
  discovered       : 5
  filter decisions : allow=4  review=1  reject=0
  queued         : 2  (filter: allow, reject, review)
  skipped dup      : 3  (use --force to re-queue)

Queued:
  33b0fb900395  [allow ]  score=0.9975  Unravelling the Probabilistic Forest: Arbitrage in Prediction Markets
             https://arxiv.org/abs/2508.03474
  cd5bc6b5dc9a  [allow ]  score=0.8808  Impact of arbitrage between leveraged ETF and futures on market liquidity during market crash
             https://arxiv.org/abs/2603.05862

Label store  : 54 total  allow=24  reject=30
SVM trigger (>=30 each) : need 6 more allow, 0 more reject
```

Command:

```powershell
python -m polytool research-prefetch-discover --search "automated market maker liquidity provision decentralized exchange" --max-results 5 --include-allow --decision-filter all
```

Output:

```text
arXiv metadata discovery: 'automated market maker liquidity provision decentralized exchange'
  source_family    : academic
  discovered       : 5
  filter decisions : allow=5  review=0  reject=0
  queued         : 0  (filter: allow, reject, review)
  skipped dup      : 5  (use --force to re-queue)

Label store  : 54 total  allow=24  reject=30
SVM trigger (>=30 each) : need 6 more allow, 0 more reject
```

Command:

```powershell
python -m polytool research-prefetch-discover --search "prediction market information aggregation market making betting markets" --max-results 5 --include-allow --decision-filter all
```

Output:

```text
arXiv metadata discovery: 'prediction market information aggregation market making betting markets'
  source_family    : academic
  discovered       : 5
  filter decisions : allow=3  review=2  reject=0
  queued         : 0  (filter: allow, reject, review)
  skipped dup      : 5  (use --force to re-queue)

Label store  : 54 total  allow=24  reject=30
SVM trigger (>=30 each) : need 6 more allow, 0 more reject
```

### Review queue

Command:

```powershell
python -m polytool research-prefetch-review list
```

Output:

```text
Prefetch review queue - 2 unlabeled pending item(s)  (56 total queued)

  33b0fb900395  score=0.9975  [2026-05-05]  Unravelling the Probabilistic Forest: Arbitrage in Prediction Markets
           https://arxiv.org/abs/2508.03474
  cd5bc6b5dc9a  score=0.8808  [2026-05-05]  Impact of arbitrage between leveraged ETF and futures on market liquidity during market crash
           https://arxiv.org/abs/2603.05862

Use 'research-prefetch-review label <CANDIDATE_ID> allow|reject' to label an item.
```

Command:

```powershell
python -m polytool research-prefetch-review counts
```

Output:

```text
Prefetch review queue : 56 total queued  |  2 pending unlabeled
Labels (in queue)     : 54 labeled  |  24 allow  |  30 reject
SVM trigger (>=30 each) : need 6 more allow, 0 more reject
```

## Decisions

- Did not label any paper.
- Did not run PDF download, Marker, ingestion, indexing, or SVM training.
- Treated duplicate discovery hits as already queued/labeled and did not force
  re-queue them.
- Recommended only the prediction-market arbitrage paper as a likely allow.

## Open Questions / Blockers

- L3.2 still needs 6 additional allow labels to reach the SVM trigger.
- This small-query batch produced only 1 strong allow recommendation, so another
  metadata-only discovery batch is needed before the operator can close the allow
  shortfall.

## Codex Review Summary

No code review was requested or performed. This was a metadata-only discovery and
dev-log packet.
