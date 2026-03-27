---
phase: quick-031
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/polymarket/simtrader/market_picker.py
  - packages/polymarket/simtrader/target_resolver.py
  - tools/cli/simtrader.py
  - tests/test_target_resolver.py
  - docs/dev_logs/2026-03-27_phase1b_market_target_resolution.md
autonomous: true
requirements: []

must_haves:
  truths:
    - "`simtrader shadow --market <polymarket.com/market/SLUG>` resolves to the correct binary market"
    - "`simtrader shadow --market <polymarket.com/event/SLUG>` fetches child markets and either auto-resolves or prints a ranked shortlist"
    - "`simtrader shadow --market <event-slug>` that fails direct market lookup falls back to event child lookup"
    - "Rejected child markets print exact skip reasons (not binary, not accepting orders, no token IDs)"
    - "Old error 'no markets returned for slug' is replaced by a diagnostic message that names the input form and suggests the fallback tried"
  artifacts:
    - path: "packages/polymarket/simtrader/target_resolver.py"
      provides: "TargetResolver class with resolve_target() returning ResolvedMarket or ChildMarketChoice"
      exports: ["TargetResolver", "ChildMarketChoice", "TargetResolverError"]
    - path: "tests/test_target_resolver.py"
      provides: "Offline tests for all resolution paths"
      contains: "def test_"
    - path: "docs/dev_logs/2026-03-27_phase1b_market_target_resolution.md"
      provides: "Dev log with accepted input forms, commands run, test results"
  key_links:
    - from: "tools/cli/simtrader.py _shadow()"
      to: "packages/polymarket/simtrader/target_resolver.py TargetResolver.resolve_target()"
      via: "replace picker.resolve_slug(args.market) with resolver.resolve_target(args.market)"
      pattern: "resolve_target"
---

<objective>
Add a target-resolution layer to `simtrader shadow` so operators can paste any real Polymarket URL or slug and get either a ready-to-use binary market or a ranked shortlist of child markets with exact skip reasons.

Purpose: Phase 1B Gold corpus capture is blocked on live shadow sessions. Operators hit "no markets returned" because they paste event URLs from the homepage instead of direct market slugs. This makes the capture loop fragile.

Output: `TargetResolver` module, updated `_shadow()` handler, 15+ offline tests, dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/CLAUDE.md
@D:/Coding Projects/Polymarket/PolyTool/docs/CURRENT_STATE.md

# Key interfaces the executor needs

## packages/polymarket/simtrader/market_picker.py
```python
class MarketPickerError(ValueError): ...

@dataclass
class ResolvedMarket:
    slug: str
    yes_token_id: str
    no_token_id: str
    yes_label: str
    no_label: str
    question: str
    mapping_tier: str = "explicit"
    probe_results: Optional[dict] = field(default=None, repr=False)

class MarketPicker:
    def __init__(self, gamma_client, clob_client) -> None: ...
    def resolve_slug(self, slug: str) -> ResolvedMarket: ...
    # raises MarketPickerError("no markets returned for slug: {slug!r}")
    # raises MarketPickerError if not binary or YES/NO ambiguous
```

## packages/polymarket/gamma.py — GammaClient
```python
class Market:
    market_slug: str
    question: str
    outcomes: list[str]
    clob_token_ids: list[str]
    active: bool
    enable_order_book: Optional[bool]
    accepting_orders: Optional[bool]
    end_date_iso: Optional[datetime]
    liquidity: float
    volume: float
    event_slug: str          # primary event slug (single)
    event_slugs: list[str]   # all event slugs

class GammaClient:
    def fetch_markets_filtered(
        self,
        condition_ids=None,
        clob_token_ids=None,
        slugs=None,
        closed=None,
        limit=100,
    ) -> list[Market]: ...

    def _fetch_events(
        self,
        *,
        event_ids: list[str],
        event_slugs: list[str],
        limit: int = 200,
    ) -> list[dict]: ...
    # raw event dicts; each may have "markets": [...] list of raw market dicts
    # OR the operator must call fetch_markets_filtered with event_slug param
```

## tools/cli/simtrader.py — _shadow() entry point (lines ~2185-2212)
```python
def _shadow(args: argparse.Namespace) -> int:
    picker = MarketPicker(GammaClient(), ClobClient())
    try:
        resolved = picker.resolve_slug(args.market)  # <-- REPLACE THIS
        yes_val = picker.validate_book(resolved.yes_token_id, allow_empty=False)
        no_val = picker.validate_book(resolved.no_token_id, allow_empty=False)
    except MarketPickerError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    # ... rest uses resolved.slug, resolved.yes_token_id, resolved.no_token_id
```

## Polymarket URL patterns
- Market URL:  https://polymarket.com/market/will-btc-hit-100k-by-dec-2025
- Event URL:   https://polymarket.com/event/btc-price-december-2025
- Direct slugs have no URL prefix
- Both /market/ and /event/ path prefixes must be stripped to get the slug
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Build TargetResolver module</name>
  <files>packages/polymarket/simtrader/target_resolver.py, tests/test_target_resolver.py</files>
  <behavior>
    - test_parse_market_url: "https://polymarket.com/market/my-slug" -> slug "my-slug"
    - test_parse_event_url: "https://polymarket.com/event/my-event" -> event slug "my-event"
    - test_parse_bare_slug: "my-slug" with no URL prefix -> treated as direct market slug
    - test_resolve_direct_market_slug: gamma returns 1 matching binary market -> ResolvedMarket
    - test_resolve_market_url: strips /market/ prefix, resolves same as direct slug
    - test_resolve_event_url_single_child: strips /event/ prefix, fetches children, exactly one binary usable market -> auto-resolves to ResolvedMarket
    - test_resolve_event_url_multi_child: multiple usable children -> raises ChildMarketChoice with ranked list and each has question+slug
    - test_resolve_event_slug_fallback: direct slug fails (no markets returned), retried as event slug -> resolves child
    - test_reject_non_binary_child: child market with 3+ outcomes -> skip reason "not_binary (3 outcomes)"
    - test_reject_no_token_ids_child: child with empty clob_token_ids -> skip reason "no_token_ids"
    - test_reject_not_accepting_orders: accepting_orders=False -> skip reason "not_accepting_orders"
    - test_reject_closed_child: active=False -> skip reason "closed"
    - test_ranked_shortlist_order: usable children ranked by liquidity desc (then volume desc as tiebreak)
    - test_market_url_wrong_path: "https://polymarket.com/faq/something" -> TargetResolverError with helpful message
  </behavior>
  <action>
Create `packages/polymarket/simtrader/target_resolver.py` with:

**Data classes:**
- `ChildMarketChoice(Exception)` — raised when multiple plausible binary children exist; contains `candidates: list[dict]` (each with keys: rank, slug, question, liquidity, volume) and `skipped: list[dict]` (each with keys: slug, question, reason)
- `TargetResolverError(ValueError)` — raised when resolution fails completely; message must be operator-useful (name the input form, say what was tried, why it failed)

**`_parse_target(raw: str) -> tuple[str, str]`** — returns `(slug, hint)` where hint is `"market"`, `"event"`, or `"unknown"`. Logic:
- If raw starts with `http://` or `https://`: parse the path
  - path starts with `/market/` -> return (path segment after /market/, "market")
  - path starts with `/event/` -> return (path segment after /event/, "event")
  - other polymarket.com path -> raise TargetResolverError explaining only /market/ and /event/ paths are supported
  - non-polymarket.com URL -> raise TargetResolverError
- Otherwise: strip whitespace, return (raw, "unknown")

**`_fetch_event_child_markets(gamma_client, event_slug: str) -> list[Market]`** — fetches markets whose event_slug matches. Use `gamma_client.fetch_markets_filtered(slugs=None, closed=False)` with a `event_slug` param attempt first; if that returns empty, fall back to scanning markets via `gamma_client.fetch_markets_page(limit=100)` and filtering by `market.event_slug == event_slug or event_slug in market.event_slugs`. NOTE: check if GammaClient's `fetch_markets_filtered` accepts an `event_slug` kwarg by checking the actual source — if not, use the page scan approach only. Do NOT invent API params that don't exist.

**`_rank_children(markets: list[Market]) -> tuple[list[Market], list[dict]]`** — returns `(usable, skipped)`:
- Usable: binary (exactly 2 clob_token_ids and 2 outcomes), active=True, accepting_orders is not False, enable_order_book is not False
- Skip reasons (in check order): "closed" if not active, "not_accepting_orders" if accepting_orders==False, "orderbook_disabled" if enable_order_book==False, "not_binary (N outcomes)" if outcome count != 2 or token count != 2, "no_token_ids" if clob_token_ids is empty
- Sort usable by liquidity desc, volume desc

**`class TargetResolver`:**
```python
def __init__(self, gamma_client, clob_client) -> None
def resolve_target(self, raw: str) -> ResolvedMarket
```
`resolve_target` logic:
1. Call `_parse_target(raw)` -> `(slug, hint)`
2. If hint == "market" OR hint == "unknown": try `picker.resolve_slug(slug)`. On success return it. On MarketPickerError where message contains "no markets returned" AND hint == "unknown": fall through to step 3. On MarketPickerError for other reasons (not binary, ambiguous YES/NO): re-raise as TargetResolverError with explanation.
3. If hint == "event" OR fell through from step 2: call `_fetch_event_child_markets(gamma_client, slug)`. If empty list: raise TargetResolverError("event slug {slug!r} returned no child markets. Check the slug is correct and the event is active."). Call `_rank_children(children)` -> (usable, skipped). If len(usable)==0: raise TargetResolverError listing all skip reasons. If len(usable)==1: call `picker.resolve_slug(usable[0].market_slug)` and return. If len(usable)>1: raise ChildMarketChoice with ranked candidates list and skipped list.

Wire up `MarketPicker` internally: `self._picker = MarketPicker(gamma_client, clob_client)`.

Tests go in `tests/test_target_resolver.py`. Mock `GammaClient` and `ClobClient` — all tests must be fully offline (no network). Use `unittest.mock.patch` or pass stub objects directly to `TargetResolver.__init__`. Test the 14 behaviors listed in `<behavior>` above.

For `_fetch_event_child_markets`: first check whether `GammaClient.fetch_markets_filtered` accepts an `event_slug` kwarg by reading the actual method signature in `packages/polymarket/gamma.py`. If not present, use the page scan approach. Do not add new params to GammaClient.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/test_target_resolver.py -v --tb=short -q 2>&1 | tail -20</automated>
  </verify>
  <done>All test_target_resolver.py tests pass. TargetResolver, ChildMarketChoice, TargetResolverError are importable from the module. No network calls in tests.</done>
</task>

<task type="auto">
  <name>Task 2: Wire TargetResolver into shadow CLI and write dev log</name>
  <files>tools/cli/simtrader.py, docs/dev_logs/2026-03-27_phase1b_market_target_resolution.md</files>
  <action>
**In `tools/cli/simtrader.py`, update `_shadow()` (around line 2185):**

1. Add import at top of `_shadow()`:
   ```python
   from packages.polymarket.simtrader.target_resolver import (
       TargetResolver,
       TargetResolverError,
       ChildMarketChoice,
   )
   ```

2. Replace the current resolution block:
   ```python
   # OLD:
   try:
       resolved = picker.resolve_slug(args.market)
       yes_val = picker.validate_book(resolved.yes_token_id, allow_empty=False)
       no_val = picker.validate_book(resolved.no_token_id, allow_empty=False)
   except MarketPickerError as exc:
       print(f"Error: {exc}", file=sys.stderr)
       return 1
   ```
   With:
   ```python
   resolver = TargetResolver(GammaClient(), ClobClient())
   try:
       resolved = resolver.resolve_target(args.market)
   except ChildMarketChoice as choice:
       print(
           f"Error: {args.market!r} is an event with multiple tradable markets. "
           f"Rerun with one of these --market slugs:",
           file=sys.stderr,
       )
       for c in choice.candidates:
           print(f"  [{c['rank']}] {c['slug']}  -- {c['question']}  "
                 f"(liquidity={c['liquidity']:.0f}, volume={c['volume']:.0f})", file=sys.stderr)
       if choice.skipped:
           print("Skipped (not usable):", file=sys.stderr)
           for s in choice.skipped:
               print(f"  {s['slug']}: {s['reason']}", file=sys.stderr)
       return 1
   except TargetResolverError as exc:
       print(f"Error: {exc}", file=sys.stderr)
       return 1
   # MarketPickerError is no longer expected here but keep as safety net
   except MarketPickerError as exc:
       print(f"Error: {exc}", file=sys.stderr)
       return 1

   yes_val = picker.validate_book(resolved.yes_token_id, allow_empty=False)
   no_val = picker.validate_book(resolved.no_token_id, allow_empty=False)
   ```
   Note: `picker` is still constructed above (line ~2204) — keep it, as it is used for `validate_book`.

3. Update the `--market` argparse help text (around line 3969):
   ```python
   help=(
       "Polymarket market slug, market URL, event slug, or event URL.  "
       "Examples: 'will-x-happen-2026', "
       "'https://polymarket.com/market/will-x-happen-2026', "
       "'https://polymarket.com/event/some-event-name'.  "
       "Event inputs list child market options when multiple are available."
   ),
   ```

**Dev log** — create `docs/dev_logs/2026-03-27_phase1b_market_target_resolution.md` with:
- Summary: what changed and why (Phase 1B Gold capture context)
- Accepted `--market` input forms (4 forms with examples)
- New module: `packages/polymarket/simtrader/target_resolver.py` — TargetResolver, ChildMarketChoice, TargetResolverError
- Modified: `tools/cli/simtrader.py` — _shadow() now uses TargetResolver; --market help updated
- Resolution logic flow (direct -> event fallback -> ranked shortlist)
- Ranking criteria (liquidity desc, volume desc; skip reasons listed)
- Test results: exact counts from `python -m pytest tests/test_target_resolver.py`
- Full regression: exact counts from `python -m pytest tests/ -q`
- Open questions: whether Gamma /events endpoint exposes child market slugs reliably; whether event_slug filter param exists on /markets
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m polytool simtrader shadow --help 2>&1 | grep -A3 "\-\-market" && python -m pytest tests/ -q --tb=short 2>&1 | tail -5</automated>
  </verify>
  <done>
    - `simtrader shadow --help` shows updated --market help text with URL example
    - Full regression suite passes (no new failures vs baseline)
    - Dev log exists at docs/dev_logs/2026-03-27_phase1b_market_target_resolution.md
    - `from packages.polymarket.simtrader.target_resolver import TargetResolver` succeeds
  </done>
</task>

</tasks>

<verification>
Run final checks:
```bash
cd "D:/Coding Projects/Polymarket/PolyTool"
python -m polytool simtrader shadow --help
python -m pytest tests/test_target_resolver.py -v --tb=short
python -m pytest tests/ -q --tb=short 2>&1 | tail -10
```

Expected: --help shows updated market arg description; test_target_resolver.py all pass; full suite passes with no new failures.
</verification>

<success_criteria>
- TargetResolver.resolve_target() accepts all 4 input forms: direct slug, market URL, event slug, event URL
- Event URLs with a single usable binary child auto-resolve without operator intervention
- Event URLs with multiple usable binary children print a ranked shortlist (slug, question, liquidity, volume) and exact skip reasons for rejected children
- The old "no markets returned for slug" error is replaced by diagnostic output naming what was tried
- 14+ offline tests pass in test_target_resolver.py covering all resolution paths and rejection cases
- Full regression suite passes
- Dev log documents the change
</success_criteria>

<output>
After completion, create `.planning/quick/31-harden-phase-1b-market-targeting-accept-/31-SUMMARY.md` following the summary template.
</output>
