# SPEC: Hypothesis Registry v0

## Scope

This spec defines an offline-only hypothesis registry plus `experiment-init`
and `experiment-run` experiment skeleton commands for Track B research
workflows. No network calls. No LLM calls.

## Registry Format

Registry path: `artifacts/research/hypothesis_registry/registry.jsonl`

The registry is append-only JSONL. Each line is a full-snapshot event for one
`hypothesis_id`.

Required state fields:

- `schema_version`: `"hypothesis_registry_v0"`
- `hypothesis_id`: stable ID derived deterministically from candidate content
- `title`: human-readable hypothesis title
- `created_at`: first registration timestamp in UTC ISO 8601
- `status`: one of `proposed | testing | validated | rejected | parked`
- `source`: object with candidate provenance
- `assumptions`: array of strings
- `metrics_plan`: object describing what to measure next
- `stop_conditions`: array of strings
- `notes`: array of strings

`source` fields:

- `candidate_file`: source candidate JSON path
- `rank`: candidate rank selected from the file
- `source_candidate_id`: candidate-local identifier when present
- `candidate_schema_version`: source file schema version when present

Event metadata fields:

- `event_type`: `registered` or `status_change`
- `event_at`: event timestamp in UTC ISO 8601
- `status_reason`: optional human-readable reason for the latest status change

## ID Generation

`hypothesis_id` is derived from stable candidate identity fields, hashed
deterministically. Preferred identity inputs are:

1. `dimension` + `key` inferred from `evidence_refs[]`
2. `segment_key`
3. `candidate_id` with any `__rankNNN` suffix removed
4. fallback stable text fields if the stronger identifiers are absent

Output format:

- `hyp_<16 hex chars>`

The rank suffix must not affect the ID.

## Event Model

This v0 chooses full-snapshot events rather than delta-only events.

Implications:

- Every append writes the latest full materialized state for that hypothesis.
- Historical status changes remain auditable because older snapshots stay in the
  JSONL file.
- `get_latest()` materializes state by replaying matching lines in order and
  returning the latest merged snapshot.

## Experiment Init and Run

`experiment-init` writes `experiment.json` in the requested output directory.
Use it when the operator wants to choose the experiment directory name
explicitly.

`experiment-run` is a thin wrapper over the same artifact writer. It treats
`--outdir` as an experiment-attempt root, generates a new child directory, and
then writes the same `experiment.json` payload there.

Generated attempt IDs:

- Format: `exp-YYYYMMDDTHHMMSSZ`
- Collision handling: append `-NN` when the timestamp directory already exists
- Recommended root: `artifacts/research/experiments/<hypothesis_id>/`

Required fields:

- `schema_version`: `"experiment_init_v0"`
- `experiment_id`: derived from output directory name for `experiment-init`, or
  from the generated attempt directory name for `experiment-run`
- `hypothesis_id`
- `created_at`
- `registry_snapshot`: title, status, created_at, and source pointer block
- `inputs`: candidate file, candidate rank, source candidate ID
- `planned_execution`: placeholder block with `tape_path`, `sweep_config`, and
  `notes`
- `metrics_plan`
- `stop_conditions`
- `notes`

Current naming alignment rule:

- `experiment-run` is the preferred lifecycle name for creating a new attempt
- `experiment-init` remains available for explicit/manual directory selection
- Both commands write the same v0 schema today
