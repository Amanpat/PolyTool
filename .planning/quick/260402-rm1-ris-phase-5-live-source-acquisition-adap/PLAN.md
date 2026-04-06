---
quick_id: 260402-rm1
title: "RIS Phase 5: Live Source Acquisition Adapters and Review Artifacts"
type: execute
tasks: 4
autonomous: true
files_modified:
  - packages/research/ingestion/fetchers.py
  - packages/research/ingestion/acquisition_review.py
  - tools/cli/research_acquire.py
  - polytool/__main__.py
  - tests/test_ris_fetchers.py
  - tests/test_ris_acquisition_review.py
  - tests/test_ris_research_acquire_cli.py
  - tests/conftest.py
  - docs/dev_logs/2026-04-02_ris_phase5_live_acquisition.md
  - docs/features/FEATURE-ris-phase5-live-acquisition.md
---

<objective>
Add live HTTP fetch capability to the RIS ingestion pipeline so sources can be
acquired directly from URLs, plus an acquisition review artifact (JSONL audit
log) and a `research-acquire` CLI command.

Purpose: Phase 4 adapters only accept pre-loaded dicts. Phase 5 closes the gap
between "I have a URL" and "it is in the knowledge store" by adding fetchers
that produce the exact raw_source dicts the existing adapters expect.

Output:
- `packages/research/ingestion/fetchers.py` — three live fetchers
- `packages/research/ingestion/acquisition_review.py` — JSONL review writer
- `tools/cli/research_acquire.py` — CLI entrypoint
- Registration in `polytool/__main__.py`
- Comprehensive offline tests + `@pytest.mark.live` smoke guards
- Dev log + feature doc
</objective>

<context>
@packages/research/ingestion/adapters.py
@packages/research/ingestion/source_cache.py
@packages/research/ingestion/normalize.py
@packages/research/ingestion/pipeline.py
@tools/cli/research_ingest.py
@polytool/__main__.py

<interfaces>
<!-- Key types and contracts the executor needs from existing code. -->

From packages/research/ingestion/adapters.py:
```python
class SourceAdapter(ABC):
    def adapt(self, raw_source: dict, cache: Optional[RawSourceCache] = None) -> ExtractedDocument: ...

ADAPTER_REGISTRY: dict[str, type[SourceAdapter]]  # keys: academic, github, blog, news
def get_adapter(family: str) -> SourceAdapter
```

From packages/research/ingestion/source_cache.py:
```python
def make_source_id(canonical_url: str) -> str  # SHA-256[:16]
class RawSourceCache:
    def __init__(self, cache_dir: str | Path) -> None
    def cache_raw(self, source_id: str, payload: dict, source_family: str) -> Path
    def has_raw(self, source_id: str, source_family: str) -> bool
    def get_raw(self, source_id: str, source_family: str) -> Optional[dict]
```

From packages/research/ingestion/normalize.py:
```python
def canonicalize_url(url: str) -> str
def extract_canonical_ids(text: str, url: str) -> dict
def normalize_metadata(raw: dict, source_family: str) -> NormalizedMetadata
```

From packages/research/ingestion/extractors.py:
```python
@dataclass
class ExtractedDocument:
    title: str
    body: str
    source_url: str
    source_family: str
    author: str = "unknown"
    publish_date: Optional[str] = None
    metadata: dict = field(default_factory=dict)
```

From polytool/__main__.py (registration pattern):
```python
research_ingest_main = _command_entrypoint("tools.cli.research_ingest")
# In _COMMAND_HANDLER_NAMES dict:
"research-ingest": "research_ingest_main",
# In print_usage():
print("  research-ingest           Ingest a document into the RIS knowledge store")
```

Raw source dict contracts (from existing fixtures):
- Academic: {url, title, abstract, authors: list[str], published_date, body_text}
- GitHub:   {repo_url, readme_text, description, stars, forks, license, last_commit_date}
- Blog:     {url, title, body_text, author, published_date, publisher}
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Live fetchers module + acquisition review writer</name>
  <files>
    packages/research/ingestion/fetchers.py
    packages/research/ingestion/acquisition_review.py
    tests/test_ris_fetchers.py
    tests/test_ris_acquisition_review.py
  </files>
  <behavior>
    Fetchers (all tested with injectable _http_fn, NO real network):
    - LiveAcademicFetcher.fetch("https://arxiv.org/abs/2301.12345") -> dict with keys {url, title, abstract, authors, published_date} parsed from arXiv API XML
    - LiveAcademicFetcher.fetch("https://arxiv.org/pdf/2301.12345") normalizes URL to abs form before fetching
    - LiveAcademicFetcher.fetch("invalid-url") raises FetchError with descriptive message
    - LiveAcademicFetcher.fetch(...) raises FetchError on HTTP timeout or non-200 status
    - LiveGitHubFetcher.fetch("https://github.com/polymarket/py-clob-client") -> dict with keys {repo_url, readme_text, description, stars, forks, license, last_commit_date}
    - LiveGitHubFetcher uses GITHUB_TOKEN env var for Authorization header when present; omits it when absent
    - LiveGitHubFetcher.fetch("bad-url") raises FetchError
    - LiveBlogFetcher.fetch("https://blog.example.com/article") -> dict with keys {url, title, body_text, author, published_date, publisher}
    - LiveBlogFetcher extracts title from HTML <title> tag and strips HTML tags from body
    - LiveBlogFetcher detects author/date from <meta> tags (og:article:author, article:published_time)
    - All fetcher outputs pass directly into their corresponding adapter without error

    AcquisitionReview:
    - AcquisitionReviewWriter(review_dir).write_review(record) appends a single JSON line to acquisition_review.jsonl
    - Multiple writes append (don't overwrite)
    - AcquisitionReviewWriter.read_reviews() returns list of all review dicts
    - Review record schema: {acquired_at, source_url, source_family, source_id, canonical_ids, cached_path, normalized_title, dedup_status, error}
    - dedup_status is "new" if source_id not already cached, "cached" if it was
  </behavior>
  <action>
    Create `packages/research/ingestion/fetchers.py`:

    1. Define `class FetchError(Exception)` at module level.

    2. Define a module-level `_default_urlopen(url: str, timeout: int, headers: dict) -> bytes` helper
       that uses `urllib.request.Request` + `urllib.request.urlopen` (stdlib only, no requests/httpx).
       Returns the response body as bytes. Raises `FetchError` on `HTTPError`, `URLError`, or timeout.

    3. `class LiveAcademicFetcher`:
       - `__init__(self, timeout: int = 15, _http_fn=None)` — stores timeout; `_http_fn` defaults
         to `_default_urlopen` for real use, injectable for tests.
       - `fetch(self, url: str) -> dict`:
         - Parse arXiv ID from URL using `_ARXIV_URL_ID_RE` from normalize.py (import it).
           Also handle bare IDs like "2301.12345" by regex match.
           If URL contains `/pdf/`, normalize to `/abs/` first.
         - Call arXiv API: `http://export.arxiv.org/api/query?id_list={arxiv_id}&max_results=1`
           via `self._http_fn(api_url, self._timeout, {})`.
         - Parse Atom XML response with `xml.etree.ElementTree.fromstring()`.
           Namespace: `{"atom": "http://www.w3.org/2005/Atom"}`.
           Extract: `atom:entry/atom:title` -> title (strip whitespace),
           `atom:entry/atom:summary` -> abstract (strip whitespace),
           `atom:entry/atom:author/atom:name` -> authors (list of strings),
           `atom:entry/atom:published` -> published_date (first 10 chars for YYYY-MM-DD).
         - If no `<entry>` found, raise `FetchError("arXiv returned no results for {arxiv_id}")`.
         - Return dict: `{url: canonical_abs_url, title, abstract, authors, published_date}`.

    4. `class LiveGitHubFetcher`:
       - `__init__(self, token: Optional[str] = None, timeout: int = 15, _http_fn=None)`.
         Token defaults to `os.environ.get("GITHUB_TOKEN")` if not passed.
       - `fetch(self, url: str) -> dict`:
         - Parse owner/repo from URL using `_GITHUB_REPO_RE` from normalize.py.
           Raise `FetchError` if URL doesn't match.
         - Call `https://api.github.com/repos/{owner}/{repo}` with headers
           `{"Accept": "application/vnd.github.v3+json"}` (+ `Authorization: token {token}` if token set).
         - Parse JSON. Extract: description, stargazers_count, forks_count,
           license.spdx_id (or license.name, or None), pushed_at[:10].
         - Call `https://api.github.com/repos/{owner}/{repo}/readme` with same headers.
           Parse JSON; base64-decode `content` field to get readme_text.
           If readme fetch fails (404), set readme_text to "".
         - Return dict: `{repo_url: canonical_url, readme_text, description, stars, forks, license, last_commit_date}`.

    5. `class LiveBlogFetcher`:
       - `__init__(self, timeout: int = 15, _http_fn=None)`.
       - `fetch(self, url: str) -> dict`:
         - GET the URL via `self._http_fn(url, self._timeout, {})`.
         - Decode response as UTF-8 (with fallback to latin-1).
         - Extract `<title>...</title>` via regex `<title[^>]*>([^<]+)</title>` (case-insensitive).
         - Extract author from `<meta name="author" content="...">` or
           `<meta property="og:article:author" content="...">` or
           `<meta property="article:author" content="...">`.
         - Extract published_date from `<meta property="article:published_time" content="...">` or
           `<meta property="og:article:published_time" content="...">`; take first 10 chars.
         - Extract publisher from `<meta property="og:site_name" content="...">`.
         - Strip ALL HTML tags from body: `re.sub(r'<[^>]+>', ' ', html)`, collapse whitespace.
           Truncate body_text to first 50000 chars (prevent unbounded memory).
         - Return dict: `{url, title, body_text, author, published_date, publisher}`.
           Use None (not empty string) for any field that wasn't extracted.

    6. `FETCHER_REGISTRY: dict[str, type] = {"academic": LiveAcademicFetcher, "github": LiveGitHubFetcher, "blog": LiveBlogFetcher, "news": LiveBlogFetcher}`
       and `def get_fetcher(family: str, **kwargs)` factory.

    Create `packages/research/ingestion/acquisition_review.py`:

    1. `@dataclass class AcquisitionRecord`:
       Fields: `acquired_at: str, source_url: str, source_family: str, source_id: str,
       canonical_ids: dict, cached_path: str, normalized_title: str,
       dedup_status: str, error: Optional[str]`.

    2. `class AcquisitionReviewWriter`:
       - `__init__(self, review_dir: str | Path)` — stores Path, does NOT create dir yet.
       - `_review_path` property -> `self._root / "acquisition_review.jsonl"`.
       - `write_review(self, record: AcquisitionRecord) -> Path`:
         Creates parent dirs, opens file in append mode ("a"), writes
         `json.dumps(dataclasses.asdict(record)) + "\n"`. Returns path.
       - `read_reviews(self) -> list[dict]`:
         Reads all lines from the JSONL file, parses each as JSON, returns list.
         Returns empty list if file doesn't exist.

    Write tests FIRST (RED), then implement (GREEN):

    `tests/test_ris_fetchers.py`:
    - Test `LiveAcademicFetcher.fetch` with a canned arXiv API XML response injected via `_http_fn`.
      Verify all returned dict keys. Verify arXiv ID extraction from abs URL, pdf URL, and bare ID.
      Verify FetchError on missing entry element. Verify FetchError on HTTP error.
    - Test `LiveGitHubFetcher.fetch` with canned JSON responses for repo metadata and readme.
      Verify token header propagation. Verify fallback when readme 404s.
      Verify FetchError on invalid URL pattern.
    - Test `LiveBlogFetcher.fetch` with canned HTML. Verify title extraction, body strip,
      meta tag extraction (author, date, publisher). Verify body truncation at 50000 chars.
    - Test that each fetcher's output dict can be passed into its corresponding adapter
      (AcademicAdapter, GithubAdapter, BlogNewsAdapter) without error.
    - Test `get_fetcher("academic")` returns LiveAcademicFetcher instance.
    - Test `get_fetcher("news")` returns LiveBlogFetcher instance.

    `tests/test_ris_acquisition_review.py`:
    - Test `AcquisitionReviewWriter.write_review` creates file and appends JSON line.
    - Test multiple writes produce multiple lines.
    - Test `read_reviews` returns list of dicts.
    - Test `read_reviews` on missing file returns empty list.
    - Test record schema matches expected keys.
  </action>
  <verify>
    <automated>rtk python -m pytest tests/test_ris_fetchers.py tests/test_ris_acquisition_review.py -x -v --tb=short</automated>
  </verify>
  <done>
    All three fetcher classes produce raw_source dicts that pass directly into their
    corresponding Phase 4 adapters. AcquisitionReviewWriter appends valid JSONL records.
    Every test runs offline (no network). FetchError raised on bad input/HTTP errors.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: research-acquire CLI + __main__.py registration</name>
  <files>
    tools/cli/research_acquire.py
    polytool/__main__.py
    tests/test_ris_research_acquire_cli.py
  </files>
  <behavior>
    - `research-acquire --url https://arxiv.org/abs/2301.12345 --source-family academic --no-eval --json`
      fetches, adapts, caches, writes review record, prints JSON to stdout with keys:
      {source_url, source_id, source_family, normalized_title, dedup_status, cached_path, doc_id, chunk_count, rejected, reject_reason}
    - `research-acquire --url ... --source-family academic --dry-run` fetches and normalizes
      but does NOT cache, does NOT write review, does NOT ingest to knowledge store; prints summary
    - `research-acquire` with no args prints help and returns 1
    - `research-acquire --url ... --source-family INVALID` returns error exit code 1
    - `research-acquire --url ... --source-family academic --cache-dir /custom/path` uses custom cache dir
    - `research-acquire --url ... --source-family academic --review-dir /custom/path` uses custom review dir
    - `python -m polytool research-acquire --help` works (command registered in __main__.py)
  </behavior>
  <action>
    Create `tools/cli/research_acquire.py` with `main(argv: list[str]) -> int`.

    Follow the exact pattern of `tools/cli/research_ingest.py`:

    1. `argparse.ArgumentParser(prog="research-acquire")` with args:
       - `--url URL` (required positional-style, but use --url for consistency)
       - `--source-family FAMILY` (required, choices=["academic", "github", "blog", "news"])
       - `--cache-dir PATH` (default: "artifacts/research/raw_source_cache")
       - `--review-dir PATH` (default: "artifacts/research/acquisition_reviews")
       - `--db PATH` (default: None, same as research_ingest)
       - `--no-eval` (skip eval gate)
       - `--dry-run` (fetch + normalize only, no cache/ingest/review)
       - `--json` (JSON output to stdout)
       - `--provider NAME` (default: "manual", choices=["manual", "ollama"])

    2. Validation: require both --url and --source-family. If missing, print error, return 1.

    3. Execution flow:
       a. Import `get_fetcher` from `packages.research.ingestion.fetchers`.
       b. `fetcher = get_fetcher(args.source_family)` — fetch raw_source dict.
          Wrap in try/except FetchError -> print error, return 2.
       c. Import `normalize_metadata`, `make_source_id`, `canonicalize_url` from normalize/source_cache.
       d. Compute `canonical_url`, `source_id`, `canonical_ids`, `normalized_title` from the raw_source.
       e. Check dedup: `RawSourceCache(cache_dir).has_raw(source_id, family)` -> dedup_status "cached"|"new".
       f. If `--dry-run`: print summary (or JSON), return 0. Do NOT cache, write review, or ingest.
       g. If not dry-run:
          - Cache via `RawSourceCache(cache_dir).cache_raw(source_id, raw_source, family)` -> cached_path.
          - Build `IngestPipeline` (same pattern as research_ingest.py) and call
            `pipeline.ingest_external(raw_source, family, cache=cache)` -> IngestResult.
          - Write acquisition review via `AcquisitionReviewWriter(review_dir).write_review(record)`.
            Build `AcquisitionRecord` with all fields. Set error=None on success.
       h. Output: if --json, print JSON dict to stdout. Otherwise print human-readable one-liner.
       i. Return 0 on success, 2 on fetch error, 2 on unexpected exception.

    4. Register in `polytool/__main__.py`:
       - Add `research_acquire_main = _command_entrypoint("tools.cli.research_acquire")`
         after the `research_extract_claims_main` line.
       - Add `"research-acquire": "research_acquire_main"` to `_COMMAND_HANDLER_NAMES`.
       - Add help line in `print_usage()` under the RIS section:
         `print("  research-acquire          Acquire a source from URL and ingest into knowledge store")`

    Write tests FIRST (RED) then implement (GREEN):

    `tests/test_ris_research_acquire_cli.py`:
    - Test `main([])` returns 1 (no args).
    - Test `main(["--url", "https://arxiv.org/abs/2301.12345", "--source-family", "academic", "--dry-run", "--json", "--no-eval"])`
      returns 0 and stdout contains JSON with expected keys. Use monkeypatch to
      inject a fake `_http_fn` on the fetcher (patch `packages.research.ingestion.fetchers._default_urlopen`
      to return canned arXiv XML bytes).
    - Test `--dry-run` does NOT create any files in cache_dir or review_dir (use tmp_path).
    - Test full (non-dry-run) flow with `--cache-dir` and `--review-dir` pointed at tmp_path:
      verify cache file exists, review JSONL file exists with one line.
    - Test invalid `--source-family` fails argument parsing.
    - Test missing `--url` returns 1.
  </action>
  <verify>
    <automated>rtk python -m pytest tests/test_ris_research_acquire_cli.py -x -v --tb=short</automated>
  </verify>
  <done>
    `python -m polytool research-acquire --help` prints usage.
    `research-acquire --url <arxiv_url> --source-family academic --dry-run --json --no-eval`
    returns 0 with JSON output. Full flow caches raw payload, ingests to knowledge store,
    and writes acquisition review JSONL. All tests offline.
  </done>
</task>

<task type="auto">
  <name>Task 3: pytest.mark.live registration + live smoke test stubs</name>
  <files>
    tests/conftest.py
    tests/test_ris_fetchers.py
  </files>
  <action>
    1. In `tests/conftest.py`, inside the existing `pytest_configure` function, add
       marker registration BEFORE the basetemp logic (near the top of the function body):

       ```python
       config.addinivalue_line("markers", "live: marks tests that require real network access (deselect with '-m \"not live\"')")
       ```

    2. In `tests/test_ris_fetchers.py`, add a section at the bottom with `@pytest.mark.live`
       smoke tests. These use REAL fetchers (no _http_fn injection) against real endpoints.
       Each test should have a 20-second timeout via `@pytest.mark.timeout(20)` if
       pytest-timeout is available, otherwise just rely on the fetcher's built-in timeout.

       ```python
       @pytest.mark.live
       class TestLiveSmoke:
           def test_arxiv_live(self):
               """Smoke: fetch a known arXiv paper."""
               fetcher = LiveAcademicFetcher(timeout=15)
               result = fetcher.fetch("https://arxiv.org/abs/2301.12345")
               assert "title" in result
               assert "abstract" in result
               assert isinstance(result["authors"], list)

           def test_github_live(self):
               """Smoke: fetch a known public GitHub repo."""
               fetcher = LiveGitHubFetcher(timeout=15)
               result = fetcher.fetch("https://github.com/polymarket/py-clob-client")
               assert "repo_url" in result
               assert "readme_text" in result
               assert result["stars"] >= 0

           def test_blog_live(self):
               """Smoke: fetch a known blog page."""
               fetcher = LiveBlogFetcher(timeout=15)
               result = fetcher.fetch("https://blog.polymarket.com")
               assert "title" in result
               assert "body_text" in result
       ```

    3. Verify that `pytest tests/test_ris_fetchers.py -m "not live" -v` runs ONLY the
       offline tests (skips the live class). Verify that
       `pytest tests/test_ris_fetchers.py -m live -v` selects ONLY the live tests.
  </action>
  <verify>
    <automated>rtk python -m pytest tests/test_ris_fetchers.py -m "not live" -x -v --tb=short</automated>
  </verify>
  <done>
    `pytest.mark.live` registered without warnings. Default `pytest tests/` does not
    run live tests. `pytest -m live` selects only live smoke tests. No marker warnings
    in pytest output.
  </done>
</task>

<task type="auto">
  <name>Task 4: Dev log + feature doc + full regression</name>
  <files>
    docs/dev_logs/2026-04-02_ris_phase5_live_acquisition.md
    docs/features/FEATURE-ris-phase5-live-acquisition.md
  </files>
  <action>
    1. Create `docs/dev_logs/2026-04-02_ris_phase5_live_acquisition.md`:
       - Title: "RIS Phase 5 -- Live Source Acquisition Adapters"
       - Date: 2026-04-02
       - Branch: feat/ws-clob-feed
       - Summary: what was built (three fetchers, review writer, CLI, tests)
       - Files created/modified (list all)
       - Test results: paste exact counts from the final regression run
       - Architecture notes:
         - stdlib-only HTTP (urllib.request), no new dependencies
         - Injectable _http_fn for fully offline test isolation
         - Fetcher output dicts match existing adapter contracts exactly
         - Acquisition review is append-only JSONL for audit trail
       - Open questions / next steps:
         - Phase 6: auto-acquire from watchlist/market-scan outputs
         - Retry/backoff logic for rate-limited APIs (arXiv, GitHub)
         - Possible Scrapling integration for blog fetcher (better extraction)

    2. Create `docs/features/FEATURE-ris-phase5-live-acquisition.md`:
       - Feature name: Live Source Acquisition
       - Status: Shipped
       - CLI: `python -m polytool research-acquire --url URL --source-family FAMILY [--dry-run] [--json] [--no-eval]`
       - Supported families: academic (arXiv), github, blog, news
       - Artifacts: `artifacts/research/raw_source_cache/{family}/{source_id}.json`,
         `artifacts/research/acquisition_reviews/acquisition_review.jsonl`
       - Operator notes:
         - Set GITHUB_TOKEN env var for GitHub rate limit (5000/hr vs 60/hr unauth)
         - arXiv API has ~3s courtesy delay; do not hammer
         - Use --dry-run to preview without caching/ingesting
         - Review JSONL for audit of all acquisitions
       - Dependencies on Phase 4: adapters.py, source_cache.py, normalize.py, pipeline.py

    3. Run FULL regression suite:
       ```bash
       rtk python -m pytest tests/ -x -q --tb=short -m "not live"
       ```
       Report exact pass/fail/skip counts in the dev log.

    4. Run smoke test to verify CLI loads:
       ```bash
       python -m polytool research-acquire --help
       python -m polytool --help
       ```
       Verify "research-acquire" appears in the help output.
  </action>
  <verify>
    <automated>rtk python -m pytest tests/ -x -q --tb=short -m "not live"</automated>
  </verify>
  <done>
    Dev log exists at expected path with accurate test counts. Feature doc exists.
    Full regression passes with zero regressions. `python -m polytool research-acquire --help`
    prints usage. `python -m polytool --help` lists research-acquire.
  </done>
</task>

</tasks>

<verification>
1. All three fetcher classes instantiate and fetch returns correct dict schema (offline tests)
2. Each fetcher output passes into its corresponding Phase 4 adapter without error
3. AcquisitionReviewWriter creates valid JSONL, supports append, read_reviews round-trips
4. CLI: `research-acquire --dry-run --json --no-eval` returns 0 with valid JSON (offline)
5. CLI: full flow creates cache file + review JSONL + ingests to knowledge store (offline)
6. `pytest.mark.live` registered; default test runs exclude live tests
7. `python -m polytool research-acquire --help` works
8. `python -m polytool --help` shows research-acquire in RIS section
9. Full regression: zero test failures on existing tests
</verification>

<success_criteria>
- `python -m polytool research-acquire --url https://arxiv.org/abs/2301.12345 --source-family academic --dry-run --json --no-eval` succeeds (with live network)
- All new tests pass offline: `pytest tests/test_ris_fetchers.py tests/test_ris_acquisition_review.py tests/test_ris_research_acquire_cli.py -v -m "not live"`
- Full regression passes: `pytest tests/ -x -q --tb=short -m "not live"` -- zero failures
- No new dependencies added to pyproject.toml (stdlib only)
- Dev log and feature doc committed
</success_criteria>
