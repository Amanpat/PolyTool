---
phase: quick-260402-rmz
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/research/evaluation/artifacts.py
  - packages/research/evaluation/providers.py
  - packages/research/evaluation/scoring.py
  - packages/research/evaluation/evaluator.py
  - packages/research/evaluation/replay.py
  - tools/cli/research_eval.py
  - tests/test_ris_phase5_provider_enablement.py
  - docs/dev_logs/2026-04-02_ris_phase5_provider_enablement.md
  - docs/features/FEATURE-ris-v1-data-foundation.md
  - docs/CURRENT_STATE.md
autonomous: true
requirements: []

must_haves:
  truths:
    - "Local providers (manual, ollama) remain the default and work without any env vars or flags"
    - "Cloud providers require explicit opt-in via RIS_ENABLE_CLOUD_PROVIDERS=1 env var -- no silent fallback"
    - "Every provider-backed scoring event records replay-grade metadata: provider_name, model_id, prompt_template_id, generation_params, source_chunk_refs, timestamp, output_hash"
    - "A replay/compare workflow can rerun scoring on the same document with a different provider/template and emit a structured diff artifact"
    - "CLI --provider flag makes provider choice obvious; research-eval replay subcommand supports replay/compare"
    - "All new code is tested deterministically with no network calls"
  artifacts:
    - path: "packages/research/evaluation/artifacts.py"
      provides: "EvalArtifact with replay metadata fields, ProviderEvent dataclass, persist/load helpers"
      min_lines: 100
    - path: "packages/research/evaluation/providers.py"
      provides: "Cloud provider guard via RIS_ENABLE_CLOUD_PROVIDERS env var, provider metadata capture"
      min_lines: 140
    - path: "packages/research/evaluation/replay.py"
      provides: "replay_eval(), compare_eval_events(), ReplayDiff dataclass, persist_replay_diff()"
      min_lines: 80
    - path: "tools/cli/research_eval.py"
      provides: "research-eval with --provider flag (guarded), replay subcommand"
      exports: ["main"]
    - path: "tests/test_ris_phase5_provider_enablement.py"
      provides: "Deterministic offline tests for cloud guard, replay metadata, replay/compare workflow, CLI"
      min_lines: 150
  key_links:
    - from: "packages/research/evaluation/evaluator.py"
      to: "packages/research/evaluation/artifacts.py"
      via: "Passes ProviderEvent metadata into EvalArtifact on every scoring path"
      pattern: "ProviderEvent|provider_event"
    - from: "packages/research/evaluation/providers.py"
      to: "RIS_ENABLE_CLOUD_PROVIDERS env var"
      via: "os.environ check in get_provider() for any non-local provider name"
      pattern: "RIS_ENABLE_CLOUD_PROVIDERS"
    - from: "packages/research/evaluation/replay.py"
      to: "packages/research/evaluation/evaluator.py"
      via: "Calls evaluate() on same doc with different provider to produce diff"
      pattern: "DocumentEvaluator|evaluate_document"
    - from: "tools/cli/research_eval.py"
      to: "packages/research/evaluation/replay.py"
      via: "replay subcommand imports replay_eval and compare_eval_events"
      pattern: "replay_eval|compare_eval_events"
---

<objective>
Build controlled provider enablement with replay-grade auditability for the RIS evaluation gate.

Purpose: Enable future cloud LLM providers (Gemini, DeepSeek, etc.) with explicit operator
opt-in while ensuring every evaluation event carries enough metadata to replay the exact
same call later with a different provider or prompt template. This is the foundation for
A/B comparing providers and auditing evaluation drift over time.

Output:
- Cloud provider guard (env var gated, no silent fallback)
- Replay-grade metadata on every eval artifact (provider, model, prompt template, params, output hash)
- Replay/compare workflow with structured diff artifacts
- CLI surface for provider selection and replay
- Deterministic test suite
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@packages/research/evaluation/types.py
@packages/research/evaluation/providers.py
@packages/research/evaluation/artifacts.py
@packages/research/evaluation/scoring.py
@packages/research/evaluation/evaluator.py
@tools/cli/research_eval.py

<interfaces>
<!-- Key types and contracts the executor needs. Extracted from codebase. -->

From packages/research/evaluation/types.py:
```python
@dataclass
class EvalDocument:
    doc_id: str
    title: str
    author: str
    source_type: str
    source_url: str
    source_publish_date: Optional[str]
    body: str
    metadata: dict = field(default_factory=dict)

@dataclass
class ScoringResult:
    relevance: int; novelty: int; actionability: int; credibility: int
    total: int; epistemic_type: str; summary: str; key_findings: list; eval_model: str
    @property gate -> str  # ACCEPT|REVIEW|REJECT

@dataclass
class GateDecision:
    gate: str; scores: Optional[ScoringResult]; hard_stop: Optional[HardStopResult]
    doc_id: str; timestamp: str
```

From packages/research/evaluation/artifacts.py:
```python
@dataclass
class EvalArtifact:
    doc_id: str; timestamp: str; gate: str
    hard_stop_result: Optional[dict]; near_duplicate_result: Optional[dict]
    family_features: dict; scores: Optional[dict]
    source_family: str; source_type: str

def persist_eval_artifact(artifact: EvalArtifact, artifacts_dir: Path) -> None
def load_eval_artifacts(artifacts_dir: Path) -> list[dict]
```

From packages/research/evaluation/providers.py:
```python
class EvalProvider(ABC):
    @property name -> str
    def score(doc: EvalDocument, prompt: str) -> str

class ManualProvider(EvalProvider): ...
class OllamaProvider(EvalProvider): ...
def get_provider(name: str = "manual", **kwargs) -> EvalProvider
```

From packages/research/evaluation/scoring.py:
```python
def build_scoring_prompt(doc: EvalDocument) -> str
def parse_scoring_response(raw_json: str, model_name: str) -> ScoringResult
def score_document(doc: EvalDocument, provider: EvalProvider) -> ScoringResult
```

From packages/research/evaluation/evaluator.py:
```python
class DocumentEvaluator:
    def __init__(self, provider, artifacts_dir, existing_hashes, existing_shingles)
    def evaluate(self, doc: EvalDocument) -> GateDecision

def evaluate_document(doc, provider_name="manual", artifacts_dir=None, **kwargs) -> GateDecision
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add replay metadata to EvalArtifact and ProviderEvent dataclass</name>
  <files>packages/research/evaluation/artifacts.py</files>
  <action>
Extend the existing artifacts module with replay-grade metadata support:

1. Add a new `ProviderEvent` dataclass that captures everything needed to replay an eval call:
   - `provider_name: str` (e.g., "manual", "ollama", "gemini")
   - `model_id: str` (e.g., "manual_placeholder", "qwen3:30b", "gemini-2.5-flash")
   - `prompt_template_id: str` (e.g., "scoring_v1" -- the only template today)
   - `prompt_template_version: str` (sha256 of the prompt text, first 12 chars, for drift detection)
   - `generation_params: dict` (e.g., `{"format": "json", "stream": false}` for Ollama; empty dict for manual)
   - `source_chunk_refs: list[str]` (list of doc_id + chunk references that went into the prompt; for now just `[doc_id]`)
   - `timestamp: str` (ISO-8601 UTC)
   - `output_hash: str` (sha256 of the raw provider output string, first 16 chars)
   - `raw_output: Optional[str]` (the raw output itself, optional, None by default to keep artifact size small)

2. Add new Optional fields to `EvalArtifact`:
   - `provider_event: Optional[dict] = None` (serialized ProviderEvent)
   - `event_id: Optional[str] = None` (unique ID for this eval event, sha256 of doc_id + timestamp + provider_name, first 16 chars)

   These fields MUST be Optional with default None so that existing artifacts without them
   load correctly (backward compatible). Use `field(default=None)` in the dataclass.

3. Add a helper function `generate_event_id(doc_id: str, timestamp: str, provider_name: str) -> str`
   that computes sha256(f"{doc_id}\0{timestamp}\0{provider_name}").hexdigest()[:16].

4. Add a helper function `compute_output_hash(raw_output: str) -> str`
   that computes sha256(raw_output.encode("utf-8")).hexdigest()[:16].

5. The existing `persist_eval_artifact` and `load_eval_artifacts` functions need NO changes --
   they use `dataclasses.asdict` and `json.loads` which will handle the new Optional fields
   automatically. Verify this is true by checking the persist/load round-trip in tests.

Do NOT change the _ARTIFACT_FILENAME constant or the file format. The new fields simply
appear as additional keys in each JSONL row when present, or are absent/null for older rows.
  </action>
  <verify>
    <automated>python -c "from packages.research.evaluation.artifacts import EvalArtifact, ProviderEvent, generate_event_id, compute_output_hash; a = EvalArtifact(doc_id='test', timestamp='t', gate='ACCEPT', hard_stop_result=None, near_duplicate_result=None, family_features={}, scores=None, source_family='manual', source_type='manual'); print('OK: EvalArtifact has defaults'); pe = ProviderEvent(provider_name='manual', model_id='m', prompt_template_id='scoring_v1', prompt_template_version='abc', generation_params={}, source_chunk_refs=[], timestamp='t', output_hash='h'); print('OK: ProviderEvent created'); print('event_id:', generate_event_id('doc1', 't', 'manual')); print('output_hash:', compute_output_hash('hello'))"</automated>
  </verify>
  <done>
  - ProviderEvent dataclass exists and is importable
  - EvalArtifact has optional provider_event and event_id fields, defaults to None
  - generate_event_id and compute_output_hash helpers exist
  - Existing code that creates EvalArtifact without the new fields still works (backward compat)
  </done>
</task>

<task type="auto">
  <name>Task 2: Add cloud provider guard and metadata capture to providers.py and scoring.py</name>
  <files>packages/research/evaluation/providers.py, packages/research/evaluation/scoring.py</files>
  <action>
Two changes across two files:

**providers.py changes:**

1. Add `import os` and `import hashlib` at the top.

2. Define a module-level constant:
   ```python
   _LOCAL_PROVIDERS = frozenset({"manual", "ollama"})
   _CLOUD_GUARD_ENV_VAR = "RIS_ENABLE_CLOUD_PROVIDERS"
   ```

3. Add a `ProviderMetadata` helper (not a full class, just a dict-returning function):
   ```python
   def get_provider_metadata(provider: EvalProvider) -> dict:
       """Return metadata dict for a provider instance.
       Keys: provider_name, model_id, generation_params."""
       meta = {"provider_name": provider.name, "model_id": "", "generation_params": {}}
       if isinstance(provider, ManualProvider):
           meta["model_id"] = "manual_placeholder"
       elif isinstance(provider, OllamaProvider):
           meta["model_id"] = provider._model
           meta["generation_params"] = {"format": "json", "stream": False}
       return meta
   ```

4. Modify `get_provider()` to enforce the cloud guard:
   - If `name` is in `_LOCAL_PROVIDERS`, proceed as before (no guard).
   - If `name` is NOT in `_LOCAL_PROVIDERS` (i.e., any cloud provider name like "gemini", "deepseek"):
     - Check `os.environ.get(_CLOUD_GUARD_ENV_VAR, "") == "1"`
     - If not set, raise `PermissionError(f"Cloud provider '{name}' requires {_CLOUD_GUARD_ENV_VAR}=1. Set this env var to explicitly opt in.")`
     - If set, for now still raise `ValueError` with the "not implemented yet" message, since
       no cloud providers are actually implemented. The guard is the important part -- it
       establishes the pattern that future cloud provider implementations will follow.
   - Keep the existing ValueError for truly unknown providers but change the flow:
     ```python
     if name in _LOCAL_PROVIDERS:
         # existing manual/ollama logic
     else:
         # Cloud guard check
         if os.environ.get(_CLOUD_GUARD_ENV_VAR, "") != "1":
             raise PermissionError(...)
         # Future: instantiate cloud provider here
         raise ValueError(f"Cloud provider '{name}' recognized but not yet implemented. ...")
     ```

**scoring.py changes:**

1. Add a module-level constant for the prompt template ID:
   ```python
   SCORING_PROMPT_TEMPLATE_ID = "scoring_v1"
   ```

2. Modify `score_document()` to return BOTH the ScoringResult AND the raw output + prompt hash.
   Instead of changing the return type (which would break callers), add a module-level function:
   ```python
   def score_document_with_metadata(doc: EvalDocument, provider: "EvalProvider") -> tuple:
       """Score a document and return (ScoringResult, raw_output, prompt_hash).

       prompt_hash is sha256(prompt_text)[:12] for prompt template versioning.
       raw_output is the raw string returned by the provider.
       """
       prompt = build_scoring_prompt(doc)
       prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
       raw_output = provider.score(doc, prompt)
       result = parse_scoring_response(raw_output, provider.name)
       return result, raw_output, prompt_hash
   ```
   Add `import hashlib` at the top.

3. Do NOT modify the existing `score_document()` function -- it remains for backward
   compatibility. The evaluator will switch to `score_document_with_metadata()`.
  </action>
  <verify>
    <automated>python -c "from packages.research.evaluation.providers import get_provider, get_provider_metadata, _CLOUD_GUARD_ENV_VAR, _LOCAL_PROVIDERS; p = get_provider('manual'); meta = get_provider_metadata(p); assert meta['provider_name'] == 'manual'; assert meta['model_id'] == 'manual_placeholder'; print('OK: local provider works'); import os; os.environ.pop('RIS_ENABLE_CLOUD_PROVIDERS', None); try: get_provider('gemini'); assert False, 'should have raised'; except PermissionError as e: print(f'OK: cloud guard blocked: {e}'); from packages.research.evaluation.scoring import SCORING_PROMPT_TEMPLATE_ID, score_document_with_metadata; print(f'OK: template ID = {SCORING_PROMPT_TEMPLATE_ID}')"</automated>
  </verify>
  <done>
  - get_provider("manual") and get_provider("ollama") work as before with no env var
  - get_provider("gemini") raises PermissionError when RIS_ENABLE_CLOUD_PROVIDERS is not set
  - get_provider_metadata() returns provider_name, model_id, generation_params
  - SCORING_PROMPT_TEMPLATE_ID = "scoring_v1" is importable from scoring.py
  - score_document_with_metadata() returns (ScoringResult, raw_output, prompt_hash) tuple
  </done>
</task>

<task type="auto">
  <name>Task 3: Wire replay metadata into the evaluator pipeline</name>
  <files>packages/research/evaluation/evaluator.py</files>
  <action>
Modify DocumentEvaluator.evaluate() to record replay metadata on every scoring event:

1. Add imports at the top of the function (lazy, inside evaluate):
   ```python
   from packages.research.evaluation.artifacts import ProviderEvent, generate_event_id, compute_output_hash
   from packages.research.evaluation.scoring import score_document_with_metadata, SCORING_PROMPT_TEMPLATE_ID
   from packages.research.evaluation.providers import get_provider_metadata
   ```

2. In Step 4 (score with provider), replace:
   ```python
   scores = score_document(doc, self._provider)
   ```
   with:
   ```python
   scores, raw_output, prompt_hash = score_document_with_metadata(doc, self._provider)
   ```

3. After scoring, build a ProviderEvent:
   ```python
   provider_meta = get_provider_metadata(self._provider)
   event_id = generate_event_id(doc.doc_id, now, provider_meta["provider_name"])
   provider_event = ProviderEvent(
       provider_name=provider_meta["provider_name"],
       model_id=provider_meta["model_id"],
       prompt_template_id=SCORING_PROMPT_TEMPLATE_ID,
       prompt_template_version=prompt_hash,
       generation_params=provider_meta["generation_params"],
       source_chunk_refs=[doc.doc_id],
       timestamp=now,
       output_hash=compute_output_hash(raw_output),
       raw_output=None,  # keep artifacts lightweight by default
   )
   ```

4. In Step 5 (persist artifact), pass the new fields to EvalArtifact:
   ```python
   artifact = EvalArtifact(
       # ... existing fields unchanged ...
       provider_event=dataclasses.asdict(provider_event),
       event_id=event_id,
   )
   ```

5. Also update the hard-stop and dedup early-return paths (Steps 1 and 2) that create
   EvalArtifact: pass `provider_event=None, event_id=None` explicitly. These paths
   skip scoring so there is no provider event to record. Since the fields have defaults,
   this is technically optional, but being explicit is clearer.

6. Remove the now-unused `from packages.research.evaluation.scoring import score_document`
   import if it was the only caller. Check: scoring.py's `score_document` is still used
   by the convenience function `evaluate_document` indirectly. Actually, evaluate_document
   calls DocumentEvaluator.evaluate() which now uses score_document_with_metadata. So
   score_document is no longer called from evaluator.py. Leave the import in scoring.py
   (it is a public API), but remove it from evaluator.py's imports if it was imported there.
   Check: evaluator.py imports `score_document` from scoring -- remove that specific import
   since we now use `score_document_with_metadata` instead (imported lazily inside evaluate()).

7. Do NOT change the GateDecision return value or the evaluate_document convenience function
   signature. The provider_event metadata lives in the persisted artifact only, not in the
   returned GateDecision. This keeps the API surface unchanged.
  </action>
  <verify>
    <automated>python -c "
from pathlib import Path
import tempfile, json
from packages.research.evaluation.types import EvalDocument
from packages.research.evaluation.evaluator import evaluate_document
from packages.research.evaluation.artifacts import load_eval_artifacts

with tempfile.TemporaryDirectory() as td:
    doc = EvalDocument(doc_id='test1', title='T', author='A', source_type='manual', source_url='', source_publish_date=None, body='Test body text for evaluation.', metadata={})
    result = evaluate_document(doc, provider_name='manual', artifacts_dir=Path(td))
    assert result.gate == 'ACCEPT', f'unexpected gate: {result.gate}'
    arts = load_eval_artifacts(Path(td))
    assert len(arts) == 1
    art = arts[0]
    assert art.get('provider_event') is not None, 'missing provider_event'
    pe = art['provider_event']
    assert pe['provider_name'] == 'manual'
    assert pe['prompt_template_id'] == 'scoring_v1'
    assert pe['output_hash'] is not None and len(pe['output_hash']) == 16
    assert art.get('event_id') is not None and len(art['event_id']) == 16
    print(f'OK: artifact has provider_event with provider={pe[\"provider_name\"]}, template={pe[\"prompt_template_id\"]}, hash={pe[\"output_hash\"]}')
    print(f'OK: event_id={art[\"event_id\"]}')
"</automated>
  </verify>
  <done>
  - evaluate_document() with artifacts_dir persists EvalArtifact with provider_event and event_id fields
  - provider_event contains provider_name, model_id, prompt_template_id, prompt_template_version, generation_params, source_chunk_refs, timestamp, output_hash
  - Hard-stop and dedup paths persist artifacts with provider_event=None, event_id=None
  - Existing evaluate() return type (GateDecision) is unchanged
  - evaluate_document convenience function still works identically from the caller's perspective
  </done>
</task>

<task type="auto">
  <name>Task 4: Create replay.py -- replay/compare workflow with diff artifact</name>
  <files>packages/research/evaluation/replay.py</files>
  <action>
Create a new module `packages/research/evaluation/replay.py` that provides the replay/compare workflow:

1. Define a `ReplayDiff` dataclass:
   ```python
   @dataclass
   class ReplayDiff:
       original_event_id: str
       replay_timestamp: str
       original_output: Optional[dict]   # original scores dict
       replay_output: Optional[dict]     # replay scores dict
       diff_fields: dict                 # {field: {"original": val, "replay": val}} for changed fields
       provider_original: str
       provider_replay: str
       prompt_template_original: str
       prompt_template_replay: str
       original_gate: str
       replay_gate: str
       gate_changed: bool
   ```

2. Define `replay_eval(doc: EvalDocument, provider_name: str = "manual", artifacts_dir: Optional[Path] = None, **kwargs) -> tuple[GateDecision, Optional[dict]]`:
   - Creates a provider via get_provider(provider_name, **kwargs)
   - Creates a DocumentEvaluator with that provider and artifacts_dir
   - Calls evaluate(doc)
   - Loads the last artifact from artifacts_dir (if set) to get the provider_event
   - Returns (decision, provider_event_dict or None)

3. Define `compare_eval_events(original_artifact: dict, replay_artifact: dict) -> ReplayDiff`:
   - Takes two artifact dicts (as loaded by load_eval_artifacts).
   - Extracts scores dicts from both.
   - Computes diff_fields: for each scoring dimension (relevance, novelty, actionability, credibility, total), if values differ, add to diff_fields.
   - Extracts provider_event info from both (with safe fallbacks for old artifacts without provider_event).
   - Returns a ReplayDiff.

4. Define `persist_replay_diff(diff: ReplayDiff, artifacts_dir: Path) -> Path`:
   - Writes the diff as a JSON file to `{artifacts_dir}/replay_diffs/replay_{original_event_id}_{replay_timestamp_slug}.json`
   - Creates the replay_diffs/ subdirectory if needed.
   - Returns the path to the written file.

5. Define `load_replay_diffs(artifacts_dir: Path) -> list[dict]`:
   - Loads all JSON files from `{artifacts_dir}/replay_diffs/`.
   - Returns list of dicts, sorted by replay_timestamp.

6. Define `find_artifact_by_event_id(event_id: str, artifacts_dir: Path) -> Optional[dict]`:
   - Loads all artifacts, scans for matching event_id.
   - Returns the matching artifact dict or None.

Keep all imports lazy where possible to avoid circular imports. The module depends on:
- artifacts.py (load_eval_artifacts, EvalArtifact)
- evaluator.py (DocumentEvaluator, evaluate_document)
- providers.py (get_provider)
- types.py (EvalDocument, GateDecision)
  </action>
  <verify>
    <automated>python -c "
from packages.research.evaluation.replay import ReplayDiff, compare_eval_events, persist_replay_diff, find_artifact_by_event_id
# Test compare_eval_events with two mock artifacts
a1 = {'doc_id': 'x', 'event_id': 'evt1', 'gate': 'ACCEPT', 'scores': {'relevance': 3, 'novelty': 3, 'actionability': 3, 'credibility': 3, 'total': 12}, 'provider_event': {'provider_name': 'manual', 'prompt_template_id': 'scoring_v1'}}
a2 = {'doc_id': 'x', 'event_id': 'evt2', 'gate': 'REVIEW', 'scores': {'relevance': 2, 'novelty': 3, 'actionability': 2, 'credibility': 3, 'total': 10}, 'provider_event': {'provider_name': 'ollama', 'prompt_template_id': 'scoring_v1'}}
diff = compare_eval_events(a1, a2)
assert diff.gate_changed == True
assert 'relevance' in diff.diff_fields
assert diff.provider_original == 'manual'
assert diff.provider_replay == 'ollama'
print(f'OK: diff has {len(diff.diff_fields)} changed fields, gate_changed={diff.gate_changed}')
print(f'OK: providers: {diff.provider_original} -> {diff.provider_replay}')
"</automated>
  </verify>
  <done>
  - replay.py module exists with ReplayDiff dataclass, replay_eval(), compare_eval_events(), persist_replay_diff(), load_replay_diffs(), find_artifact_by_event_id()
  - compare_eval_events correctly identifies which scoring fields changed between two artifacts
  - persist_replay_diff writes structured JSON to replay_diffs/ subdirectory
  - find_artifact_by_event_id scans JSONL for matching event_id
  </done>
</task>

<task type="auto">
  <name>Task 5: Extend research-eval CLI with cloud guard UX and replay subcommand</name>
  <files>tools/cli/research_eval.py</files>
  <action>
Restructure research_eval.py to support subcommands while maintaining backward compatibility:

1. **Backward compat**: If argv[0] is not a known subcommand and --file or --title is present,
   treat as the "eval" subcommand (existing callers keep working). Pattern: same approach used
   by research_precheck.py's main() function.

2. **Subcommand: eval (default)** -- the current behavior, with enhancements:
   - The `--provider` flag already exists with `choices=["manual", "ollama"]`.
   - Change choices to be open-ended (remove choices restriction) so that cloud provider names
     can be passed. The guard in `get_provider()` will handle permission checking.
   - Add `--enable-cloud` flag as a CLI-level convenience that sets
     `os.environ["RIS_ENABLE_CLOUD_PROVIDERS"] = "1"` before calling get_provider.
     This is in addition to the env var approach -- operators can use either.
   - When `--provider` is not manual or ollama and `--enable-cloud` is not set and
     `RIS_ENABLE_CLOUD_PROVIDERS` is not in env, print a clear error message explaining
     the guard mechanism and exit 1. Do this check BEFORE calling evaluate_document to
     give a better UX than a raw PermissionError traceback.
   - When `--json` output includes provider_event from the artifact (if artifacts_dir set),
     add it to the JSON output.

3. **Subcommand: replay**
   ```
   research-eval replay --event-id <id> --artifacts-dir <path> [--provider <name>] [--enable-cloud] [--json]
   ```
   - `--event-id` (required): the event_id from a prior eval artifact.
   - `--artifacts-dir` (required): where to find the original artifact and write replay output.
   - `--provider` (optional, default: same as original): provider to use for replay.
   - `--enable-cloud`: same cloud guard convenience flag.
   - `--json`: output the ReplayDiff as JSON.
   
   Workflow:
   1. Load the original artifact by event_id from artifacts_dir.
   2. Reconstruct the EvalDocument from the artifact (doc_id, source_type, source_family from artifact; body NOT stored in artifact, so require --file or --body for replay).
   3. Actually: require `--file` or `--body` + `--title` for replay too, since the artifact
      does not store the document body. This is intentional -- artifacts are lightweight.
   4. Run replay_eval() with the specified (or original) provider.
   5. Call compare_eval_events() between original and replay artifacts.
   6. Call persist_replay_diff() to save the diff.
   7. Print the diff (formatted text or --json).

   Text output format:
   ```
   Replay: evt1 -> evt2
   Original: manual (scoring_v1) -> ACCEPT (12/20)
   Replay:   ollama (scoring_v1) -> REVIEW (10/20)
   Gate changed: yes
   Diff:
     relevance: 3 -> 2
     actionability: 3 -> 2
   Diff saved: artifacts/replay_diffs/replay_evt1_20260402T...json
   ```

4. Keep `_KNOWN_SUBCOMMANDS = frozenset({"eval", "replay"})` for the backward compat check.
  </action>
  <verify>
    <automated>python -c "
import sys; sys.argv = ['test']
from tools.cli.research_eval import main
# Test that basic eval still works (backward compat)
rc = main(['--title', 'Test', '--body', 'Test body text', '--source-type', 'manual', '--provider', 'manual'])
assert rc == 0, f'expected 0, got {rc}'
print('OK: backward compat eval works')
# Test cloud guard error message
rc = main(['eval', '--title', 'Test', '--body', 'Test body text', '--provider', 'gemini'])
assert rc != 0, 'expected non-zero for unguarded cloud provider'
print('OK: cloud guard blocks gemini without opt-in')
# Test replay with no args shows help
rc = main(['replay'])
assert rc != 0, 'expected non-zero for replay with no args'
print('OK: replay subcommand registered')
"</automated>
  </verify>
  <done>
  - research-eval with --title/--body/--file works as before (backward compat)
  - research-eval eval --provider gemini fails with clear guard message when cloud not enabled
  - research-eval replay --event-id --artifacts-dir --file works for replay/compare
  - --enable-cloud flag sets env var for cloud provider opt-in
  - --json output includes provider_event metadata when artifacts_dir is set
  </done>
</task>

<task type="auto">
  <name>Task 6: Write deterministic test suite and dev log</name>
  <files>tests/test_ris_phase5_provider_enablement.py, docs/dev_logs/2026-04-02_ris_phase5_provider_enablement.md</files>
  <action>
Create `tests/test_ris_phase5_provider_enablement.py` with the following test cases.
All tests MUST be deterministic, offline, no network calls. Use `tmp_path` fixture for
artifacts_dir. Use `monkeypatch` for env var manipulation.

**Cloud provider guard tests (4 tests):**
- `test_local_providers_no_guard_needed`: get_provider("manual") and get_provider("ollama") work
  without RIS_ENABLE_CLOUD_PROVIDERS. (OllamaProvider just instantiates, does not connect.)
- `test_cloud_provider_blocked_without_env_var`: get_provider("gemini") raises PermissionError
  when RIS_ENABLE_CLOUD_PROVIDERS is not set.
- `test_cloud_provider_env_var_set_but_not_implemented`: With RIS_ENABLE_CLOUD_PROVIDERS=1,
  get_provider("gemini") raises ValueError (not implemented yet), NOT PermissionError.
- `test_cloud_guard_env_var_name_is_correct`: Assert _CLOUD_GUARD_ENV_VAR == "RIS_ENABLE_CLOUD_PROVIDERS".

**Provider metadata tests (2 tests):**
- `test_manual_provider_metadata`: get_provider_metadata(ManualProvider()) returns correct dict.
- `test_ollama_provider_metadata`: get_provider_metadata(OllamaProvider()) returns model_id and generation_params.

**Replay metadata in artifacts tests (3 tests):**
- `test_eval_artifact_has_provider_event`: Run evaluate_document with artifacts_dir, load artifact,
  verify provider_event fields are present and correct for ManualProvider.
- `test_eval_artifact_event_id_is_deterministic`: Same doc + same timestamp + same provider =
  same event_id. (Mock _utcnow in evaluator to control timestamp.)
- `test_eval_artifact_backward_compat`: Create an EvalArtifact WITHOUT provider_event and event_id
  (old-style), persist it, load it, verify it loads correctly with those fields as None/missing.

**Replay/compare workflow tests (4 tests):**
- `test_compare_eval_events_detects_diffs`: Two artifacts with different scores produce a
  ReplayDiff with correct diff_fields and gate_changed.
- `test_compare_eval_events_no_diff`: Two identical artifacts produce empty diff_fields and
  gate_changed=False.
- `test_persist_and_load_replay_diff`: persist_replay_diff writes JSON, load_replay_diffs
  reads it back correctly.
- `test_find_artifact_by_event_id`: Persist two artifacts with different event_ids, find each
  by event_id, verify correct one is returned.

**CLI tests (3 tests):**
- `test_cli_eval_backward_compat`: main(["--title", "T", "--body", "B"]) returns 0.
- `test_cli_cloud_guard_blocks`: main(["eval", "--title", "T", "--body", "B", "--provider", "gemini"])
  returns non-zero without cloud env var.
- `test_cli_replay_no_args_fails`: main(["replay"]) returns non-zero.

**Scoring template ID test (1 test):**
- `test_scoring_prompt_template_id`: Assert SCORING_PROMPT_TEMPLATE_ID == "scoring_v1".

Total: ~17 tests.

Also create a dev log at `docs/dev_logs/2026-04-02_ris_phase5_provider_enablement.md`:
- Title: RIS Phase 5: Controlled Provider Enablement with Replay-Grade Auditability
- What was built: cloud guard, replay metadata, replay/compare workflow, CLI extensions
- Design decisions: env var guard pattern, ProviderEvent fields, prompt template versioning via hash
- Files changed: list all modified files
- Test results: reference the test file and count
- Next steps: implement actual cloud providers (gemini, deepseek), add raw_output capture flag, build provider A/B dashboard
  </action>
  <verify>
    <automated>python -m pytest tests/test_ris_phase5_provider_enablement.py -v --tb=short -x</automated>
  </verify>
  <done>
  - tests/test_ris_phase5_provider_enablement.py exists with ~17 tests, all passing
  - No network calls in any test (verify by running with --timeout=5 per test)
  - Dev log exists at docs/dev_logs/2026-04-02_ris_phase5_provider_enablement.md
  - All existing tests still pass: python -m pytest tests/ -x -q --tb=short shows no regressions
  </done>
</task>

</tasks>

<verification>
After all tasks are complete, run these checks:

1. **Import smoke test:**
   ```bash
   python -c "from packages.research.evaluation.artifacts import ProviderEvent, generate_event_id, compute_output_hash; from packages.research.evaluation.providers import get_provider, get_provider_metadata, _CLOUD_GUARD_ENV_VAR; from packages.research.evaluation.replay import ReplayDiff, replay_eval, compare_eval_events, persist_replay_diff; from packages.research.evaluation.scoring import SCORING_PROMPT_TEMPLATE_ID, score_document_with_metadata; print('All imports OK')"
   ```

2. **Cloud guard works:**
   ```bash
   python -c "from packages.research.evaluation.providers import get_provider; get_provider('manual'); print('manual OK'); get_provider('ollama'); print('ollama OK')"
   python -c "from packages.research.evaluation.providers import get_provider; get_provider('gemini')" 2>&1 | grep -i "PermissionError"
   ```

3. **Replay metadata in artifacts:**
   ```bash
   python -c "
   import tempfile, json
   from pathlib import Path
   from packages.research.evaluation.types import EvalDocument
   from packages.research.evaluation.evaluator import evaluate_document
   from packages.research.evaluation.artifacts import load_eval_artifacts
   with tempfile.TemporaryDirectory() as td:
       doc = EvalDocument(doc_id='v', title='T', author='A', source_type='manual', source_url='', source_publish_date=None, body='Body text')
       evaluate_document(doc, artifacts_dir=Path(td))
       arts = load_eval_artifacts(Path(td))
       pe = arts[0].get('provider_event', {})
       assert pe.get('provider_name') == 'manual'
       assert pe.get('prompt_template_id') == 'scoring_v1'
       print('Replay metadata verified')
   "
   ```

4. **Phase 5 tests pass:**
   ```bash
   python -m pytest tests/test_ris_phase5_provider_enablement.py -v --tb=short
   ```

5. **No regressions:**
   ```bash
   python -m pytest tests/ -x -q --tb=short
   ```

6. **CLI still loads:**
   ```bash
   python -m polytool --help
   ```
</verification>

<success_criteria>
- Cloud providers are gated behind RIS_ENABLE_CLOUD_PROVIDERS=1; local providers work unchanged
- Every scoring event with artifacts_dir persists replay-grade metadata (provider_event + event_id)
- replay.py provides compare_eval_events() producing structured diffs
- CLI research-eval supports eval subcommand (backward compat) and replay subcommand
- ~17 deterministic tests pass with no network calls
- All existing tests continue to pass (no regressions)
- Dev log documents the work
</success_criteria>

<output>
After completion, create `.planning/quick/260402-rmz-ris-phase-5-controlled-provider-enableme/260402-rmz-SUMMARY.md`
</output>
