# Codex Review - L2.1 One-Paper Acceptance Repair

**Date:** 2026-05-25
**Reviewer:** Codex
**Verdict:** PASS WITH CONCERNS

## Objective

Review L2.1 Deliverable B recovery after commit hygiene and the one-paper
acceptance repair. Acceptance target: default `academic_papers` Chroma collection
contains `arxiv:2510.05533`; live/default `research-query` smokes pass honestly;
unrelated vault files are separated or documented; L2.1 is either complete or
blocked with exact reasons.

## Git Hygiene Verdict

Commit hygiene is improved but the working tree is not clean.

- `HEAD` is `7fc6bf2 fix(ris): L2.1 Deliverable B - offline-safe semantic fallback, resolves Codex BLOCK`.
- `git show --stat --name-status HEAD` shows exactly 3 files:
  - `docs/dev_logs/2026-05-25_l2-1-semantic-fallback-offline-safe-fix.md`
  - `packages/research/synthesis/academic_query.py`
  - `tests/test_research_query.py`
- The prior mixed vault commit was documented in `docs/dev_logs/2026-05-25_repo-hygiene-after-4788871.md`; unrelated vault files are now unstaged/untracked and separated from `HEAD`.
- Current non-vault working tree still includes unstaged L2.1/A repair files plus unrelated root-doc edits:
  - `AGENTS.md`
  - `claude.md`
  - `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`
  - `packages/research/ingestion/marker_queue.py`
  - `packages/research/synthesis/academic_query.py`
  - `tests/test_ris_marker_queue.py`
  - `tools/cli/research_marker_queue.py`
  - `tools/cli/research_query.py`
- Current vault working tree still has large unrelated Obsidian churn under `docs/obsidian-vault/` and must remain out of any L2.1 commit.

Hygiene conclusion: functionally reviewable, but not commit/worktree-clean as-is.

## Commands Run

```text
$ git status --short
Result: dirty tree. Relevant L2.1 files plus large unrelated docs/obsidian-vault/
churn; no files staged.

$ git log --oneline -5
7fc6bf2 fix(ris): L2.1 Deliverable B - offline-safe semantic fallback, resolves Codex BLOCK
15ef471 docs(ris): repo hygiene before L2.1 Deliverable A - closeout log
3348e79 feat(ris): L2.1 Deliverable C - display-only snippet sanitation
310e184 feat(ris): WP-2 Marker queue speed observability and review-concern fixes
76db8a1 docs(ris): WP-1 cached PDF E2E closeout - PASS

$ python -m polytool --help
Result: exit 0; CLI loads and lists research-query and research-marker-queue.

$ python -m pytest tests/test_research_query.py -q --tb=short
95 passed in 4.66s

$ python -m pytest tests/test_ris_marker_queue.py -q --tb=short
204 passed, 1 skipped in 6.28s

$ python -m polytool research-marker-queue check-chroma-links --json
{
  "collection": "academic_papers",
  "chroma_path": "kb\\rag\\index",
  "total_chunks": 162,
  "unique_papers": 5,
  "valid_ks_doc_id": 162,
  "missing_ks_doc_id": 0,
  "ks_doc_id_not_in_ks": 0,
  "not_in_ks_doc_ids": []
}
```

Chroma membership probe:

```json
{
  "count": 162,
  "arxiv_ids": [
    "1106.5040",
    "1609.03471",
    "1810.04383",
    "2510.05533",
    "2604.24366"
  ],
  "has_2510_05533": true
}
```

## Chroma Link Result

PASS.

`academic_papers` is present in `kb/rag/index`, has 162 chunks across 5 unique
papers, all chunks have `ks_doc_id`, and all linked KnowledgeStore documents
exist. The collection includes `arxiv:2510.05533`.

## Acceptance Query Results

| Query | had_fallback | retrieval_mode | Citation | Score | Result |
|---|---:|---|---|---:|---|
| `LLM` | false | semantic | `arxiv:2510.05533` | 0.339719 | PASS |
| `language model financial prediction` | false | semantic | `arxiv:2510.05533` | 0.657555 | PASS |
| `what does this paper say about hallucination` | false | semantic | `arxiv:2510.05533` | 0.196530 | PASS |
| `weather forecast` | true | lexical | none | n/a | PASS |

The unrelated control query remains an honest rejection: no citations,
`had_fallback=true`, and a no-match warning.

## Retrieval Metadata

PASS.

The default CLI JSON now exposes:

- `retrieval_mode`
- `semantic_unavailable_reason`

Positive acceptance queries returned `retrieval_mode="semantic"` with
`semantic_unavailable_reason=null`. The unrelated query returned
`retrieval_mode="lexical"`, `had_fallback=true`, and no citations.

## Snippet Sanitation Result

PASS WITH CONCERNS.

The checked acceptance snippets no longer contain the explicit blocked Marker
artifact patterns from the spec:

- no `<sup>`
- no `<br>`
- no `####`
- no `(#page-N-M)`
- no raw `<span ...>` tags in semantic snippets after the one-paper repair

Concern: semantic body chunks still expose Markdown/angle-link text from the
paper body, for example arXiv URL references rendered as Markdown-style links
or `<https://...>` autolinks. That is not one of the current AT-5 blocked
patterns, but it remains operator-facing snippet noise and should be considered
if snippet quality is tightened beyond the current spec.

## Decisions

- No feature implementation code was changed by this review.
- No GPU parsing, 3-paper sample, 29-paper validation, SVM enforce, benchmark,
  or marker parser/queue edits were run by this review.
- I did not stage or revert unrelated vault/root-doc changes.

## Verdict

PASS WITH CONCERNS.

Functional one-paper L2.1 acceptance now passes honestly against the default
local state. The prior one-paper blockers are resolved:

1. `academic_papers` contains `arxiv:2510.05533`.
2. Chroma linkage is clean.
3. The three positive acceptance queries return `2510.05533`.
4. `weather forecast` is rejected.
5. Retrieval mode metadata is present.
6. The specified Marker snippet artifacts are absent.

Remaining concerns:

1. The working tree is still not scope-clean because unrelated vault churn and
   root-doc edits remain dirty.
2. The acceptance repair is currently in unstaged working-tree changes, not a
   clean acceptance-repair commit.
3. Snippets are sanitized for the specified Marker artifacts, but still contain
   some Markdown/URL noise from raw paper body chunks.

## L2.1 Status

L2.1 one-paper functional acceptance is complete.

Closeout is not commit-ready until the L2.1 repair changes are isolated from the
unrelated vault/root-doc changes and committed or otherwise explicitly left as a
documented dirty tree.

## Is 3-Paper Category Sample Safe Next?

Technically yes after this one-paper functional pass, but operationally not from
the current dirty tree. Safe next step is to isolate/commit the L2.1 acceptance
repair and keep `docs/obsidian-vault/`, `AGENTS.md`, and `claude.md` out of that
commit unless the Director explicitly includes them. After that hygiene step, a
3-paper category sample is safe to schedule.
