# Codex Review - Docker Storage Optimization

Date: 2026-05-04
Reviewer: Codex
Scope: Review Docker storage optimization changes for Docker bloat risk, runtime data safety, and RIS service compatibility.

## Verdict

PASS WITH FIXES

The Docker storage changes reduce bloat risk without deleting runtime data and the Compose configuration still renders successfully. L1 Marker validation may resume from a storage/config standpoint, but the current working tree is not a clean Docker-only change set because it also contains unrelated parser benchmark edits and Obsidian vault updates.

## Commands Run

```text
git status --short
 M .dockerignore
 M Dockerfile.ris
 M docs/obsidian-vault/.obsidian/workspace.json
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_09-Decisions_Decision_-_Academic_Pipeline_Hosting_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Pre-fetch_SVM_Topic_Filter_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
 M "docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md"
 M tools/cli/research_parser_benchmark.py
?? docs/dev_logs/2026-05-03_codex-rereview-ris-marker-production-rollout.md
?? docs/dev_logs/2026-05-03_ris-marker-gpu-failure-diagnosis.md
?? docs/dev_logs/2026-05-04_docker-storage-optimization.md
?? docs/runbooks/docker_storage.md
```

```text
git log --oneline -5
3348aef fix(ris): L1 Marker rollout - Codex FAIL resolution (adapter rejection, scheduler split, cache mount)
94a074c feat(ris): L1 Marker production rollout - default parser, GPU Docker, explicit failure semantics
f5bf5af L3.1 Complete
ac3aebc feat(ris): L3.1 prefetch review queue + label store + hold-review mode
a923e6a Academic Pipeline Improvements L0 - L2
```

```text
python -m polytool --help
exit 0; CLI loaded and listed RIS, SimTrader, crypto pair, RAG, and utility commands.
```

```text
git diff --name-status
M       .dockerignore
M       Dockerfile.ris
M       docs/obsidian-vault/.obsidian/workspace.json
M       docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
M       docs/obsidian-vault/.smart-env/multi/Claude_Desktop_09-Decisions_Decision_-_Academic_Pipeline_Hosting_md.ajson
M       docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Pre-fetch_SVM_Topic_Filter_md.ajson
M       docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
M       docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md
M       tools/cli/research_parser_benchmark.py
```

```text
docker compose config
exit 0; full rendered output intentionally not copied because Compose expands local .env / env_file values into the config output.
```

```text
docker compose --profile ris-gpu config --services
clickhouse
api
grafana
migrate
ris-scheduler
ris-scheduler-gpu
```

```text
docker compose --profile ris-gpu config --profiles
cli
pair-bot
ris-gpu
ris-n8n
```

```text
docker compose --profile ris-gpu config --volumes
clickhouse_data
grafana_data
```

```text
git diff --check
exit 0; line-ending warnings only, no whitespace errors reported.
Warnings referenced Dockerfile.ris, Obsidian vault files, and tools/cli/research_parser_benchmark.py as LF-to-CRLF-on-next-touch paths.
```

```text
docker system df -v
Images: 0
Containers: 0
Local Volumes: 0
Build cache: 0B
```

Auxiliary inspection:

```text
Root large runtime directories measured:
artifacts: 8761 files, 11642528679 bytes
kb: 153 files, 1199779237 bytes
docker_data: 1 file, 0 bytes

These are excluded by .dockerignore.
```

## Findings

Blocking: none for Docker storage safety or RIS Compose validity.

Non-blocking:

1. The current working tree includes `tools/cli/research_parser_benchmark.py` changes. Those are parser diagnostics, not Docker storage optimization. They should be committed separately or explicitly tied to the prior Marker failure-diagnosis packet before the Docker storage change is declared clean.
2. The current working tree also includes Obsidian vault changes unrelated to Docker storage. They do not affect Docker or RIS services, but they should not be bundled with the storage optimization unless intentionally included.
3. `.dockerignore` covers the actual large runtime directories present in this repo (`artifacts/`, `kb/`, `docker_data/`, `.venv`, Python/test caches). It does not add generic future-proof model/local-DB patterns such as `.cache/`, `.huggingface/`, `.cache/datalab/`, `*.duckdb`, `*.sqlite`, or `*.db`. Current Marker model weights are mounted from `${USERPROFILE}/.cache/datalab`, outside the repo build context, so this is not blocking.

Positive checks:

1. `artifacts/` covers benchmark outputs and is excluded from build context.
2. `kb/` and `docker_data/` are excluded, preventing local knowledge stores and Docker runtime data from entering images.
3. `Dockerfile.ris` keeps dependency installation before source copy and uses BuildKit pip cache mounts, so dependency layers stay reusable and pip cache stays outside the image layer.
4. `Dockerfile.ris` does not download Marker model weights during build.
5. `docker-compose.yml` keeps `ris-scheduler-gpu` behind the `ris-gpu` profile.
6. The Marker cache is bind-mounted from host `${USERPROFILE}/.cache/datalab` to `/home/polytool/.cache/datalab`, outside the image.
7. `docs/runbooks/docker_storage.md` lists `docker system prune -f` only in safe cleanup and flags `docker system prune --volumes -f` as unsafe/operator-confirmation only.
8. No runtime data deletion commands were run.

## L1 Marker Validation

L1 Marker validation may resume from a Docker storage/config standpoint.

Do not treat this as Marker benchmark validation. I did not run the Marker benchmark, did not build the GPU image, and did not download model weights. The next validation should follow `docs/runbooks/docker_storage.md` Section 9 after the unrelated working-tree changes are split or acknowledged.

## Codex Review Summary

Tier: Recommended infrastructure/docs review.
Issues found: no blocking Docker storage or RIS service issue; one non-blocking scope hygiene issue from unrelated parser and Obsidian changes.
Issues addressed: none; review only.
