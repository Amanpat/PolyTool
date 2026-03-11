---
phase: 10-quickrun-list-candidates-and-exclude-mar
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tools/cli/simtrader.py
  - tests/test_simtrader_quickrun.py
  - docs/README_SIMTRADER.md
autonomous: true

must_haves:
  truths:
    - "quickrun --dry-run --list-candidates N prints the top N passing candidates with slug, question, and depth stats"
    - "quickrun --exclude-market SLUG (repeatable) skips excluded slugs during auto-pick"
    - "excluded slugs are persisted in quickrun_context under 'excluded_slugs'"
    - "all existing 20 quickrun tests still pass"
  artifacts:
    - path: "tools/cli/simtrader.py"
      provides: "--list-candidates and --exclude-market arg definitions + handler logic"
      contains: "list_candidates"
    - path: "tests/test_simtrader_quickrun.py"
      provides: "offline tests for both new flags"
      contains: "list_candidates"
    - path: "docs/README_SIMTRADER.md"
      provides: "user-facing docs for new flags"
      contains: "exclude-market"
  key_links:
    - from: "tools/cli/simtrader.py _quickrun()"
      to: "MarketPicker.auto_pick_many()"
      via: "list_candidates path calls auto_pick_many(n=list_candidates) instead of auto_pick(n=1)"
    - from: "tools/cli/simtrader.py _quickrun()"
      to: "args.exclude_markets list"
      via: "passed as exclude_slugs= to auto_pick / auto_pick_many"
---

<objective>
Add two UX improvements to `quickrun`: `--list-candidates N` shows the top N passing candidates (useful with `--dry-run` so users can see what the auto-picker found before committing to one), and `--exclude-market SLUG` (repeatable) lets users skip slugs that keep getting selected because they dominate the liquidity ranking.

Purpose: Breaks the "always same market" loop by giving visibility into the candidate pool and a one-flag escape hatch.
Output: Updated CLI handler, argparse definitions, offline tests, README section.
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@tools/cli/simtrader.py
@packages/polymarket/simtrader/market_picker.py
@tests/test_simtrader_quickrun.py
@docs/README_SIMTRADER.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add --list-candidates and --exclude-market to quickrun CLI</name>
  <files>tools/cli/simtrader.py</files>
  <action>
**Argparse additions** (in `_build_argparser()` quickrun section, after `--max-candidates`):

```python
qr.add_argument(
    "--list-candidates",
    type=int,
    default=0,
    metavar="N",
    dest="list_candidates",
    help=(
        "Print the top N candidates that pass validation, then exit.  "
        "Best combined with --dry-run.  0 = disabled (default)."
    ),
)
qr.add_argument(
    "--exclude-market",
    action="append",
    default=[],
    metavar="SLUG",
    dest="exclude_markets",
    help=(
        "Skip this slug during auto-pick (repeatable).  "
        "e.g. --exclude-market will-x-happen --exclude-market will-y-happen"
    ),
)
```

**Handler changes in `_quickrun()`** — two distinct paths:

*Path A — list-candidates mode* (`args.list_candidates > 0`):
- Must only be reachable when `not args.market` (if `--market` is provided alongside `--list-candidates`, print a warning to stderr that `--list-candidates` is ignored when `--market` is explicit and fall through to normal flow).
- Call `picker.auto_pick_many(n=args.list_candidates, max_candidates=args.max_candidates, allow_empty_book=args.allow_empty_book, min_depth_size=min_depth_size, top_n_levels=top_n_levels, exclude_slugs=set(args.exclude_markets))`.
- For each candidate in the returned list, validate both YES and NO books to get depth_total, then print:
  ```
  [candidate 1] slug     : <slug>
  [candidate 1] question : <question>
  [candidate 1] YES bid  : <best_bid>  ask: <best_ask>  depth: <depth_total or "n/a">
  [candidate 1] NO  bid  : <best_bid>  ask: <best_ask>  depth: <depth_total or "n/a">
  ```
  If `yes_val.depth_total` is None (because `min_depth_size` was 0), show "n/a" for depth.
- After printing all candidates, print `Listed N candidates.` and return 0.
- If `auto_pick_many` returns an empty list, print `No valid candidates found in first {max_candidates} examined.` to stderr and return 1.

*Path B — exclude-market only* (no `--list-candidates`, but `--exclude-market` given):
- Pass `exclude_slugs=set(args.exclude_markets)` to the existing `picker.auto_pick(...)` call (it already accepts `collect_skips` but does NOT accept `exclude_slugs` directly — `auto_pick` delegates to `auto_pick_many` which does accept `exclude_slugs`). Update the `auto_pick` call in `_quickrun` to pass `exclude_slugs=set(args.exclude_markets)` (check `auto_pick` signature — it currently does NOT expose `exclude_slugs`; add the parameter forwarding: update `auto_pick()` in `market_picker.py` to accept and forward `exclude_slugs` to `auto_pick_many`).

**quickrun_context persistence**: in the `quickrun_context` dict (built after dry_run check), add:
```python
"excluded_slugs": args.exclude_markets,
"list_candidates": args.list_candidates,
```

**market_picker.py change**: Add `exclude_slugs: Optional[set] = None` parameter to `auto_pick()` and forward it to `auto_pick_many(exclude_slugs=exclude_slugs)`. This is a one-line addition (the parameter already exists on `auto_pick_many`).
  </action>
  <verify>
    ```bash
    python -m pytest tests/test_simtrader_quickrun.py -v --tb=short -q 2>&1 | tail -5
    ```
    All 20 existing tests must still pass (no regressions).
  </verify>
  <done>
    `--list-candidates` and `--exclude-market` arguments exist in the quickrun argparser.
    `_quickrun()` routes to list-candidates print path when `args.list_candidates > 0` and no explicit `--market`.
    `auto_pick()` forwards `exclude_slugs` to `auto_pick_many()`.
    `quickrun_context` includes `excluded_slugs` and `list_candidates` keys.
    All 20 existing tests pass.
  </done>
</task>

<task type="auto">
  <name>Task 2: Offline tests for list-candidates and exclude-market</name>
  <files>tests/test_simtrader_quickrun.py</files>
  <action>
Append a new test class `TestListCandidates` and extend `TestExcludeMarket` (or add it) after the existing test classes. Keep the existing helper functions (`_make_market`, `_make_book`, `YES_TOKEN`, `NO_TOKEN`, `SLUG`) in scope — do not duplicate them.

**Test structure pattern** (follows existing tests — mock `GammaClient`, `ClobClient`, `TapeRecorder`, `run_strategy` via `patch`):

```python
class TestListCandidates:
    """Tests for --list-candidates flag."""

    def _run_quickrun(self, extra_args, gamma_markets, book_map=None):
        """Helper: patch externals, invoke _quickrun, capture stdout/stderr."""
        # Use standard pattern from existing tests:
        # patch GammaClient().fetch_markets_page and fetch_markets_filtered,
        # patch ClobClient().fetch_book,
        # patch TapeRecorder and run_strategy so they never run.
        ...

    def test_list_candidates_prints_n_candidates(self, capsys):
        """--list-candidates 2 prints exactly 2 passing candidates."""
        # Arrange: gamma returns 3 markets; books all valid.
        # Act: quickrun --dry-run --list-candidates 2
        # Assert: stdout contains both slugs; "Listed 2 candidates." printed.

    def test_list_candidates_exits_zero(self, capsys):
        """--list-candidates exits 0 when candidates found."""
        # quickrun --list-candidates 1 → returns 0.

    def test_list_candidates_exits_one_when_empty(self, capsys):
        """--list-candidates exits 1 when no candidates pass validation."""
        # All books invalid → auto_pick_many returns [] → exits 1.

    def test_list_candidates_ignored_with_explicit_market(self, capsys):
        """--list-candidates is silently ignored when --market is explicit."""
        # --market SLUG --list-candidates 3 → proceeds with normal flow (no candidate list printed).


class TestExcludeMarket:
    """Tests for --exclude-market flag."""

    def test_exclude_single_slug_skipped(self, capsys):
        """--exclude-market SLUG causes auto-pick to skip that slug."""
        # gamma returns [SLUG, "other-slug"]; books valid for both.
        # --exclude-market SLUG → resolved market is "other-slug".

    def test_exclude_multiple_slugs(self, capsys):
        """--exclude-market repeatable: both slugs are skipped."""
        # gamma returns [SLUG, "other-slug", "third-slug"]; all books valid.
        # --exclude-market SLUG --exclude-market other-slug → resolved = "third-slug".

    def test_exclude_persisted_in_quickrun_context(self, tmp_path, capsys):
        """excluded_slugs appear in quickrun_context written to run_manifest."""
        # Full run (not dry-run); verify manifest contains excluded_slugs.
```

Each test must be fully offline (no network). Use `patch("packages.polymarket.gamma.GammaClient")` and `patch("packages.polymarket.clob.ClobClient")` consistently with the existing test pattern. Verify test count increases from 20 to at least 27 (7 new tests).
  </action>
  <verify>
    ```bash
    python -m pytest tests/test_simtrader_quickrun.py -v --tb=short 2>&1 | tail -15
    ```
    All tests pass; count is >= 27.
  </verify>
  <done>
    7+ new tests covering list-candidates (3 tests) and exclude-market (3+ tests) all pass.
    No existing tests broken.
    `pytest tests/test_simtrader_quickrun.py` exits 0.
  </done>
</task>

<task type="auto">
  <name>Task 3: Document new flags in README_SIMTRADER.md</name>
  <files>docs/README_SIMTRADER.md</files>
  <action>
**Location 1 — "All quickrun flags" table** (around line 357-374): Add two rows after `--max-candidates`:

```
| `--list-candidates N` | 0 | Print top N passing candidates and exit (combine with `--dry-run`). 0 = disabled |
| `--exclude-market SLUG` | – | Skip this slug during auto-pick; repeatable |
```

**Location 2 — Add a new subsection** after the existing `--dry-run` tip at the end of the auto-pick/dry-run area (before or after "All quickrun flags", wherever it reads naturally — around the Golden Run checklist section). Insert:

```markdown
### Browsing candidates and excluding over-represented markets

If `quickrun --dry-run` always picks the same market (because it dominates the liquidity ranking),
use `--list-candidates N` to see the top N passing candidates, then exclude the unwanted one:

```bash
# See the top 5 passing candidates without committing to any
python -m polytool simtrader quickrun --dry-run --list-candidates 5

# Skip a specific market on the next run
python -m polytool simtrader quickrun --exclude-market will-always-selected-2026 --dry-run

# Exclude multiple slugs and list what remains
python -m polytool simtrader quickrun \
  --dry-run \
  --list-candidates 3 \
  --exclude-market will-always-selected-2026 \
  --exclude-market will-second-most-popular-2026
```

`--exclude-market` is also persisted to `quickrun_context` in the run manifest for auditability.
```

Keep the existing section structure intact; only insert, do not rewrite existing paragraphs.
  </action>
  <verify>
    ```bash
    python -m pytest tests/test_simtrader_quickrun.py -v -q --tb=short 2>&1 | tail -5
    ```
    (Docs are prose — verify by reading the updated file to confirm both the table rows and new subsection are present and the markdown renders correctly with no broken fences.)
  </verify>
  <done>
    `docs/README_SIMTRADER.md` contains `--list-candidates` and `--exclude-market` in the flags table and a new subsection with usage examples.
    File parses as valid markdown (no unclosed fences, no duplicate section headers).
  </done>
</task>

</tasks>

<verification>
```bash
python -m pytest tests/test_simtrader_quickrun.py -v --tb=short
```
All tests pass. Count >= 27 (was 20).

Spot-check flag presence:
```bash
python -m polytool simtrader quickrun --help | grep -E "list-candidates|exclude-market"
```
Both flags appear in help output.
</verification>

<success_criteria>
- `quickrun --dry-run --list-candidates N` prints N candidate blocks (slug / question / book stats) and exits 0.
- `quickrun --exclude-market SLUG` (repeatable) causes those slugs to be skipped by auto_pick.
- `quickrun_context` in manifests includes `excluded_slugs` list and `list_candidates` int.
- `auto_pick()` in `market_picker.py` accepts and forwards `exclude_slugs`.
- README flags table and new subsection present.
- All 27+ tests pass (`pytest tests/test_simtrader_quickrun.py`).
</success_criteria>

<output>
After completion, create `.planning/quick/10-quickrun-list-candidates-and-exclude-mar/10-SUMMARY.md`
</output>
