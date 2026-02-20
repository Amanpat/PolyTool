# Feature: CLV preflight and actionable reason codes

## Summary
CLV misses are now classified into actionable categories instead of collapsing into `OFFLINE`.
When `--compute-clv` is enabled, scan now runs a single CLV preflight check and writes `clv_preflight.json` to the run directory.

This makes failed runs diagnosable without reading stack traces.

## Reason codes

| Reason code | Meaning | Typical next step |
| --- | --- | --- |
| `OFFLINE` | Online CLV fetch explicitly disabled (`--clv-offline`) | Re-run without `--clv-offline` if live fetch is desired |
| `AUTH_MISSING` | Missing/invalid auth for `/prices-history` | Configure CLOB auth headers/keys |
| `CONNECTIVITY` | Network path failure (DNS, refused, no route) | Check outbound network + DNS + host reachability |
| `HTTP_ERROR` | Non-2xx HTTP response (except 429/auth cases) | Inspect response status/body and service health |
| `RATE_LIMITED` | HTTP 429 from CLOB | Back off and retry at lower request rate |
| `TIMEOUT` | Request timeout | Increase timeout and verify network latency |
| `EMPTY_HISTORY` | Request succeeded but no history points returned | Widen window or warm cache earlier |
| `OUTSIDE_WINDOW` | Points exist but none valid in closing selector window | Increase closing window where appropriate |

## Common 400 cause
`/prices-history` can return HTTP 400 when query params do not match the API contract:
- use `market` (not `token_id`)
- `startTs/endTs` and `interval` are mutually exclusive
- `fidelity` must be numeric minutes (for example `1`, `5`, `60`), not `"high"`/`"medium"`/`"low"`

## Artifacts
- `clv_preflight.json`
  - `endpoint_used`
  - `auth_present` (boolean only)
  - `error_class`
  - `recommended_next_action`
  - `preflight_ok`
- `run_manifest.json`
  - `diagnostics.clv_preflight`

## How to verify
1. Run:
   - `python -m tools.cli.scan --user "@<user>" --compute-clv`
2. Open run artifacts and confirm:
   - `clv_preflight.json` exists
   - `error_class` is specific (`AUTH_MISSING`, `CONNECTIVITY`, etc.) in bad environments
3. Open coverage/audit reports and confirm:
   - `clv_missing_reason` values reflect the same specific reason codes.
