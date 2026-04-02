---
phase: quick-260402-ivi
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - config/seed_manifest.json
  - packages/research/ingestion/seed.py
  - packages/research/evaluation/types.py
  - packages/research/synthesis/calibration.py
  - packages/research/synthesis/precheck_ledger.py
  - tools/cli/research_calibration.py
  - polytool/__main__.py
  - tests/test_ris_calibration.py
  - tests/test_ris_seed.py
  - docs/features/FEATURE-ris-calibration-and-metadata.md
  - docs/dev_logs/2026-04-02_ris_phase2_calibration_and_metadata_hardening.md
autonomous: true
requirements: []
must_haves:
  truths:
    - "Seed manifest classifies each entry with an accurate source_family that matches freshness_decay.json families"
    - "Manifest entries have optional evidence_tier and notes fields for metadata hygiene"
    - "Operator can run a CLI command to get calibration health summary over a time window"
    - "Calibration summary shows usage rate, override rate, outcome distribution, and per-source-family counts"
    - "Family-drift reporting identifies overrepresented source families in STOP/REVIEW decisions"
  artifacts:
    - path: "config/seed_manifest.json"
      provides: "Reclassified corpus metadata with evidence_tier and notes"
    - path: "packages/research/synthesis/calibration.py"
      provides: "Calibration analytics helpers over precheck ledger"
      exports: ["compute_calibration_summary", "compute_family_drift"]
    - path: "tools/cli/research_calibration.py"
      provides: "research-calibration CLI entrypoint"
    - path: "tests/test_ris_calibration.py"
      provides: "Deterministic tests for calibration and manifest parsing"
  key_links:
    - from: "packages/research/synthesis/calibration.py"
      to: "packages/research/synthesis/precheck_ledger.py"
      via: "list_prechecks_by_window() and list_prechecks()"
      pattern: "list_prechecks"
    - from: "tools/cli/research_calibration.py"
      to: "packages/research/synthesis/calibration.py"
      via: "compute_calibration_summary import"
      pattern: "compute_calibration_summary"
---

<objective>
Complete RIS Phase 2 calibration hardening and corpus metadata hygiene.

Purpose: The seeded corpus currently has all 11 entries classified as
`source_family: "book_foundational"` and `source_type: "book"` which is
inaccurate -- the RIS RAGfiles are internal architecture reference docs and the
roadmaps are strategy/planning docs. Additionally, no tooling exists for operators
to inspect calibration health (usage rate, override rate, outcome distribution,
family drift) over the precheck ledger. This plan corrects the metadata, extends
the manifest schema, builds calibration analytics helpers, and adds a CLI surface.

Output: Corrected seed_manifest.json, new calibration.py module, research-calibration
CLI, deterministic tests, feature doc, dev log.
</objective>

<execution_context>
@.claude/get-shit-done/workflows/execute-plan.md
@.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@config/seed_manifest.json
@config/freshness_decay.json
@packages/research/evaluation/types.py
@packages/research/ingestion/seed.py
@packages/research/synthesis/precheck.py
@packages/research/synthesis/precheck_ledger.py
@tests/test_ris_seed.py
@docs/dev_logs/2026-04-01_ris_phase2_seed_and_extractor_benchmark.md

<interfaces>
<!-- Key types and contracts the executor needs. -->

From packages/research/synthesis/precheck_ledger.py:
```python
LEDGER_SCHEMA_VERSION = "precheck_ledger_v2"
DEFAULT_LEDGER_PATH = Path("artifacts/research/prechecks/precheck_ledger.jsonl")

def list_prechecks(ledger_path: Path | None = None) -> list[dict]: ...
def list_prechecks_by_window(start_iso: str, end_iso: str, ledger_path: Path | None = None) -> list[dict]: ...
def get_precheck_history(precheck_id: str, ledger_path: Path | None = None) -> list[dict]: ...
def append_precheck(result: "PrecheckResult", ledger_path: Path | None = None) -> None: ...
def append_override(precheck_id: str, override_reason: str, ledger_path: Path | None = None) -> None: ...
def append_outcome(precheck_id: str, outcome_label: str, outcome_date: str | None = None, ledger_path: Path | None = None) -> None: ...
```

Ledger event shapes:
- precheck_run: {schema_version, event_type: "precheck_run", recommendation, idea, supporting_evidence, contradicting_evidence, risk_factors, stale_warning, timestamp, provider_used, precheck_id, reason_code, evidence_gap, review_horizon, written_at}
- override: {schema_version, event_type: "override", precheck_id, was_overridden: true, override_reason, written_at}
- outcome: {schema_version, event_type: "outcome", precheck_id, outcome_label, outcome_date, written_at}

From packages/research/ingestion/seed.py:
```python
@dataclass
class SeedEntry:
    path: str
    title: str
    source_type: str
    source_family: str
    author: str = "unknown"
    publish_date: Optional[str] = None
    tags: list = field(default_factory=list)

@dataclass
class SeedManifest:
    version: str
    description: str
    entries: list[SeedEntry]

def load_seed_manifest(manifest_path: "str | Path") -> SeedManifest: ...
```

From packages/research/evaluation/types.py:
```python
SOURCE_FAMILIES: dict[str, str] = {
    "arxiv": "academic", "ssrn": "academic", "book": "academic",
    "reddit": "forum_social", "twitter": "forum_social", "youtube": "forum_social",
    "github": "github", "blog": "blog", "news": "news",
    "dossier": "dossier_report", "manual": "manual",
}
```

From config/freshness_decay.json families:
academic_foundational, book_foundational, academic_empirical, preprint, github,
blog, reddit, twitter, youtube, wallet_analysis, news
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Seed manifest metadata hygiene and schema extension</name>
  <files>config/seed_manifest.json, packages/research/ingestion/seed.py, packages/research/evaluation/types.py</files>
  <action>
1. Reclassify config/seed_manifest.json entries with accurate metadata:

   - RIS RAGfiles (RIS_OVERVIEW through RIS_07): These are internal architecture
     reference docs, NOT books. Set source_type="reference_doc", source_family=
     "book_foundational" (correct -- they ARE timeless foundational docs per
     freshness_decay.json where book_foundational has null half-life). Add
     evidence_tier="tier_1_internal" and notes describing the content.

   - POLYTOOL_MASTER_ROADMAP_v4.2.md: Superseded roadmap. Set source_type=
     "roadmap", source_family="book_foundational", evidence_tier="tier_2_superseded",
     notes="Superseded by v5; retained for historical context".

   - POLYTOOL_MASTER_ROADMAP_v5.md: Active roadmap predecessor. Set source_type=
     "roadmap", source_family="book_foundational", evidence_tier="tier_1_internal",
     notes="Predecessor to v5.1; contains Phase 0-4 planning".

   - POLYTOOL_MASTER_ROADMAP_v5_1.md: Current governing roadmap. Set source_type=
     "roadmap", source_family="book_foundational", evidence_tier="tier_1_internal",
     notes="Current governing roadmap document".

2. Bump manifest version from "1" to "2" and update description to reflect
   the reclassification.

3. Extend SeedEntry dataclass in seed.py to accept optional fields:
   - evidence_tier: Optional[str] = None
   - notes: Optional[str] = None

   Update load_seed_manifest() to parse these new optional fields from JSON
   using .get() with None defaults. This is backward compatible -- v1 manifests
   without these fields will parse fine.

4. Add "reference_doc" and "roadmap" to SOURCE_FAMILIES in types.py:
   - "reference_doc" -> "book_foundational"
   - "roadmap" -> "book_foundational"

   This ensures new source_type values map correctly through the pipeline's
   family resolution logic.

5. Do NOT change run_seed() behavior -- the SQL override mechanism for
   source_family already handles the authoritative manifest value correctly.
  </action>
  <verify>
    <automated>cd D:/Coding\ Projects/Polymarket/PolyTool && python -c "from packages.research.ingestion.seed import load_seed_manifest; m = load_seed_manifest('config/seed_manifest.json'); assert m.version == '2'; assert all(e.source_type in ('reference_doc', 'roadmap') for e in m.entries); assert any(e.evidence_tier for e in m.entries); print(f'OK: {len(m.entries)} entries, version={m.version}')"</automated>
  </verify>
  <done>
    All 11 seed manifest entries have accurate source_type (reference_doc or roadmap),
    optional evidence_tier and notes fields populated, SeedEntry dataclass extended,
    SOURCE_FAMILIES mapping updated, manifest version bumped to "2".
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Calibration analytics module, family-drift reporting, and CLI</name>
  <files>packages/research/synthesis/calibration.py, tools/cli/research_calibration.py, polytool/__main__.py, tests/test_ris_calibration.py</files>
  <behavior>
    - compute_calibration_summary(events) with empty list returns zero counts
    - compute_calibration_summary(events) with mixed precheck_run/override/outcome events returns correct usage_count, override_count, override_rate, outcome_distribution dict, recommendation_distribution dict
    - compute_calibration_summary filters to precheck_run events for recommendation counts, override events for override counts, outcome events for outcome distribution
    - compute_family_drift(events, seed_manifest) returns per-source-family breakdown of recommendation counts
    - compute_family_drift with no matching events returns empty dict
    - compute_family_drift correctly associates precheck events with source families using the idea text or metadata
    - CLI research-calibration --window 7d reads ledger and prints JSON summary
    - CLI research-calibration --json flag outputs machine-readable JSON
    - Manifest hygiene: load_seed_manifest v2 with evidence_tier/notes parses correctly
    - Manifest hygiene: load_seed_manifest v1 (no evidence_tier/notes) backward compat
  </behavior>
  <action>
1. Create packages/research/synthesis/calibration.py with:

   a) CalibrationSummary dataclass:
      - window_start: str (ISO)
      - window_end: str (ISO)
      - total_prechecks: int
      - recommendation_distribution: dict[str, int]  (GO/CAUTION/STOP counts)
      - override_count: int
      - override_rate: float  (override_count / total_prechecks or 0.0)
      - outcome_distribution: dict[str, int]  (successful/failed/partial/not_tried counts)
      - outcome_count: int
      - stale_warning_count: int
      - avg_evidence_count: float  (avg len of supporting+contradicting per precheck)

   b) compute_calibration_summary(events: list[dict]) -> CalibrationSummary:
      Partition events by event_type. Count prechecks (event_type="precheck_run"),
      overrides (event_type="override"), outcomes (event_type="outcome"). Compute
      distributions and rates. Use .get() with defaults for all fields (backward
      compat with v0/v1 ledger entries).

   c) FamilyDriftReport dataclass:
      - family_counts: dict[str, dict[str, int]]  (family -> {GO: n, CAUTION: n, STOP: n})
      - overrepresented_in_stop: list[str]  (families with > 50% STOP rate)
      - total_prechecks: int

   d) compute_family_drift(events: list[dict], manifest: SeedManifest | None = None) -> FamilyDriftReport:
      Since precheck_run events do not currently carry source_family, this function
      inspects the "idea" field text for domain keywords (e.g., "market maker",
      "crypto", "sports") to approximate domain assignment. If a manifest is
      provided, it checks whether the idea text overlaps with any manifest entry
      titles/tags for family association. This is a best-effort heuristic --
      future versions can add source_family to precheck events directly.

      For the overrepresented_in_stop field: any family where STOP count exceeds
      50% of that family's total events.

   e) format_calibration_report(summary: CalibrationSummary, drift: FamilyDriftReport | None = None) -> str:
      Human-readable multi-line text report.

2. Create tools/cli/research_calibration.py with main(argv) -> int:
   - Subcommand: research-calibration summary
     Flags: --window DURATION (e.g., "7d", "30d", "all"; default "30d"),
            --ledger PATH (default: DEFAULT_LEDGER_PATH),
            --manifest PATH (optional, for family drift),
            --json (output JSON instead of text report)
   - Reads ledger via list_prechecks_by_window() (or list_prechecks() for "all")
   - Calls compute_calibration_summary() and optionally compute_family_drift()
   - Prints formatted report or JSON

3. Register "research-calibration" in polytool/__main__.py using the same
   pattern as existing research-* commands.

4. Write tests/test_ris_calibration.py (TDD: write tests FIRST, then implement):
   - Test compute_calibration_summary with empty events -> zero counts
   - Test compute_calibration_summary with 3 precheck_run events (GO, CAUTION, STOP)
   - Test compute_calibration_summary with override events -> correct override_rate
   - Test compute_calibration_summary with outcome events -> correct distribution
   - Test compute_calibration_summary with mixed v0/v1/v2 events (backward compat)
   - Test compute_family_drift with keyword-based domain assignment
   - Test compute_family_drift overrepresented_in_stop detection
   - Test format_calibration_report produces non-empty string
   - Test CLI argument parsing (--window, --json, --manifest)
   - Test CLI with fixture ledger file produces output (no network)
   - Test load_seed_manifest v2 with evidence_tier/notes
   - Test load_seed_manifest v1 backward compat (no evidence_tier/notes)

   All tests must be offline/deterministic. Use tmp_path fixtures for ledger files.
   Create fixture JSONL data inline in tests (no external fixture files needed).
  </action>
  <verify>
    <automated>cd D:/Coding\ Projects/Polymarket/PolyTool && rtk python -m pytest tests/test_ris_calibration.py tests/test_ris_seed.py -x -v --tb=short</automated>
  </verify>
  <done>
    Calibration analytics module exists with compute_calibration_summary() and
    compute_family_drift(). CLI research-calibration registered and working.
    All new tests pass. Existing seed tests still pass.
  </done>
</task>

<task type="auto">
  <name>Task 3: Feature doc, dev log, and smoke test</name>
  <files>docs/features/FEATURE-ris-calibration-and-metadata.md, docs/dev_logs/2026-04-02_ris_phase2_calibration_and_metadata_hardening.md</files>
  <action>
1. Create docs/features/FEATURE-ris-calibration-and-metadata.md documenting:
   - Seed manifest v2 schema (new fields: evidence_tier, notes)
   - Source-family reclassification rationale
   - Calibration summary: what metrics it exposes, how to interpret them
   - Family drift: what it detects, what "overrepresented in STOP" means
   - CLI usage: research-calibration summary --window 30d [--json] [--manifest PATH]
   - Intentionally deferred: ML-based weighting, semantic source-family assignment,
     automated threshold tuning, dashboard visualization

2. Create docs/dev_logs/2026-04-02_ris_phase2_calibration_and_metadata_hardening.md with:
   - Objective
   - Files changed and why (list each file with 1-line rationale)
   - Seed metadata corrections made (before/after for each reclassified entry)
   - Calibration metrics exposed (list each metric with definition)
   - Commands run + output (targeted tests, smoke test, full regression)
   - Test results (exact counts)
   - Open questions for Phase 3

3. Run full regression suite and record exact counts in dev log:
   python -m pytest tests/ -x -q --tb=short

4. Run smoke test of the CLI:
   python -m polytool research-calibration summary --window all --json

   (This will produce a zero-count summary if no ledger exists, which is the
   expected behavior -- confirms the CLI wiring works.)

5. Verify python -m polytool --help still loads cleanly.
  </action>
  <verify>
    <automated>cd D:/Coding\ Projects/Polymarket/PolyTool && python -m polytool --help && rtk python -m pytest tests/ -x -q --tb=short</automated>
  </verify>
  <done>
    Feature doc and dev log written. Full regression passes with no regressions.
    CLI --help loads. Smoke test of research-calibration CLI produces output.
    Dev log has exact test counts, file change list, and open questions.
  </done>
</task>

</tasks>

<verification>
1. config/seed_manifest.json has version "2" with reclassified entries
2. All 11 entries have source_type in {reference_doc, roadmap}
3. At least 9 entries have non-null evidence_tier
4. SeedEntry accepts evidence_tier and notes without breaking v1 manifests
5. compute_calibration_summary returns correct distributions from fixture data
6. compute_family_drift identifies overrepresented families
7. research-calibration CLI registered and produces output
8. All new tests pass, all existing tests pass
9. No network calls in any test
</verification>

<success_criteria>
- Seed manifest accurately classifies all entries by source_family and evidence_tier
- Calibration analytics module computes usage rate, override rate, outcome distribution, and family drift
- Operator can run `python -m polytool research-calibration summary --window 30d` and get actionable output
- Full test suite passes with zero regressions
- Feature doc and dev log exist with shipped behavior documented
</success_criteria>

<output>
After completion, create `.planning/quick/260402-ivi-ris-phase-2-calibration-hardening-and-co/260402-ivi-SUMMARY.md`
</output>
