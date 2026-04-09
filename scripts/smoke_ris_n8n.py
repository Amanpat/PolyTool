#!/usr/bin/env python3
"""
smoke_ris_n8n.py -- Non-destructive repo-side validation for RIS n8n pilot assets.

Purpose:
    Validates that all infra/n8n/workflows/*.json files are internally consistent,
    CLI entrypoints respond correctly, and the docker compose profile renders cleanly.
    Does NOT start containers, POST to webhooks, or modify any files.

Usage:
    python scripts/smoke_ris_n8n.py

Exit codes:
    0  All checks PASS or SKIP (no FAILs)
    1  One or more checks FAIL

Sections:
    1. Workflow JSON validation (parse, fields, command correctness)
    2. CLI entrypoint --help verification
    3. Docker Compose profile render check (SKIPs gracefully if Docker unavailable)
    4. Summary table + curl examples for operator reference
"""

import glob
import json
import os
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
WORKFLOW_DIR = REPO_ROOT / "infra" / "n8n" / "workflows"
ORPHAN_DIR = REPO_ROOT / "workflows" / "n8n"

KNOWN_POLYTOOL_SUBCOMMANDS = {
    "research-health",
    "research-acquire",
    "research-scheduler",
    "research-report",
    "research-stats",
}

EXPECTED_CONTAINER = "polytool-ris-scheduler"

CLI_ENTRYPOINTS = [
    "research-health",
    "research-stats",
    "research-scheduler",
    "research-acquire",
    "research-report",
]


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

class CheckResult:
    def __init__(self, name: str, status: str, detail: str = ""):
        self.name = name
        self.status = status  # PASS, FAIL, SKIP
        self.detail = detail

    def __repr__(self) -> str:
        return f"CheckResult({self.name}, {self.status})"


results: list[CheckResult] = []


def check(name: str, status: str, detail: str = "") -> CheckResult:
    r = CheckResult(name, status, detail)
    results.append(r)
    return r


# ---------------------------------------------------------------------------
# Section 1: Workflow JSON validation
# ---------------------------------------------------------------------------

def validate_workflows() -> None:
    print("\n[1] Workflow JSON validation")
    print(f"    Directory: {WORKFLOW_DIR}")

    workflow_files = sorted(WORKFLOW_DIR.glob("*.json"))
    if not workflow_files:
        check("workflow-files-exist", "FAIL", f"No *.json files found in {WORKFLOW_DIR}")
        return

    check("workflow-files-exist", "PASS", f"{len(workflow_files)} workflow file(s) found")

    for wf_path in workflow_files:
        fname = wf_path.name

        # Parse JSON
        try:
            with wf_path.open(encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as exc:
            check(f"json-parse:{fname}", "FAIL", str(exc))
            continue
        check(f"json-parse:{fname}", "PASS")

        # Has name field
        if not data.get("name"):
            check(f"has-name:{fname}", "FAIL", "Missing or empty 'name' field")
        else:
            check(f"has-name:{fname}", "PASS", data["name"])

        # Has nodes array
        if not isinstance(data.get("nodes"), list):
            check(f"has-nodes:{fname}", "FAIL", "Missing or non-list 'nodes' field")
            continue
        check(f"has-nodes:{fname}", "PASS", f"{len(data['nodes'])} node(s)")

        # Validate executeCommand nodes
        for node in data["nodes"]:
            if node.get("type") != "n8n-nodes-base.executeCommand":
                continue
            cmd = node.get("parameters", {}).get("command", "")
            node_name = node.get("name", "<unnamed>")

            # No leading =
            if cmd.startswith("="):
                check(
                    f"no-leading-equals:{fname}:{node_name}",
                    "FAIL",
                    f"command starts with '=': {cmd[:80]}",
                )
            else:
                check(f"no-leading-equals:{fname}:{node_name}", "PASS")

            # References correct container
            if EXPECTED_CONTAINER not in cmd:
                check(
                    f"correct-container:{fname}:{node_name}",
                    "FAIL",
                    f"Expected '{EXPECTED_CONTAINER}' in command, got: {cmd[:80]}",
                )
            else:
                check(f"correct-container:{fname}:{node_name}", "PASS")

            # Extract polytool subcommand and verify it's in known-good set
            # Command pattern: docker exec <container> python -m polytool <subcommand> [args...]
            parts = cmd.split()
            try:
                pm_idx = parts.index("-m")
                # parts[pm_idx+1] should be "polytool", parts[pm_idx+2] is subcommand
                if pm_idx + 2 < len(parts):
                    subcommand = parts[pm_idx + 2]
                    if subcommand in KNOWN_POLYTOOL_SUBCOMMANDS:
                        check(
                            f"known-subcommand:{fname}:{node_name}",
                            "PASS",
                            subcommand,
                        )
                    else:
                        check(
                            f"known-subcommand:{fname}:{node_name}",
                            "FAIL",
                            f"Unknown subcommand '{subcommand}' not in {KNOWN_POLYTOOL_SUBCOMMANDS}",
                        )
                else:
                    check(
                        f"known-subcommand:{fname}:{node_name}",
                        "FAIL",
                        "Could not extract subcommand from command string",
                    )
            except ValueError:
                # '-m' not in parts -- might be a non-polytool exec; skip subcommand check
                check(
                    f"known-subcommand:{fname}:{node_name}",
                    "SKIP",
                    "No '-m polytool' pattern found; skipping subcommand check",
                )

    # No JSON files should remain in the old workflows/n8n/ location
    orphan_jsons = list(ORPHAN_DIR.glob("*.json")) if ORPHAN_DIR.exists() else []
    if orphan_jsons:
        check(
            "orphan-json-removed",
            "FAIL",
            f"{len(orphan_jsons)} JSON file(s) still in {ORPHAN_DIR}",
        )
    else:
        check("orphan-json-removed", "PASS", "No workflow JSON in workflows/n8n/")


# ---------------------------------------------------------------------------
# Section 2: CLI entrypoints --help check
# ---------------------------------------------------------------------------

def validate_cli_entrypoints() -> None:
    print("\n[2] CLI entrypoint --help verification")

    for subcommand in CLI_ENTRYPOINTS:
        label = f"cli-help:{subcommand}"
        try:
            r = subprocess.run(
                [sys.executable, "-m", "polytool", subcommand, "--help"],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
                timeout=30,
            )
            if r.returncode == 0:
                check(label, "PASS", f"exit 0")
            else:
                check(label, "FAIL", f"exit {r.returncode}: {r.stderr[:120]}")
        except FileNotFoundError:
            check(label, "FAIL", "python not found")
        except subprocess.TimeoutExpired:
            check(label, "FAIL", "timed out after 30s")
        except Exception as exc:
            check(label, "FAIL", str(exc))


# ---------------------------------------------------------------------------
# Section 3: Docker Compose profile render
# ---------------------------------------------------------------------------

def validate_compose_profile() -> None:
    print("\n[3] Docker Compose profile render check")

    # Check if docker is available
    try:
        r_version = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r_version.returncode != 0:
            check(
                "compose-profile-render",
                "SKIP",
                "docker not available (returncode != 0)",
            )
            return
    except (FileNotFoundError, subprocess.TimeoutExpired):
        check(
            "compose-profile-render",
            "SKIP",
            "docker command not found or timed out",
        )
        return

    # Run docker compose config
    try:
        r = subprocess.run(
            ["docker", "compose", "--profile", "ris-n8n", "config", "--quiet"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=30,
        )
        if r.returncode == 0:
            check("compose-profile-render", "PASS", "docker compose --profile ris-n8n config --quiet exit 0")
        else:
            check(
                "compose-profile-render",
                "FAIL",
                f"exit {r.returncode}: {r.stderr[:200]}",
            )
    except subprocess.TimeoutExpired:
        check("compose-profile-render", "FAIL", "docker compose timed out after 30s")
    except Exception as exc:
        check("compose-profile-render", "FAIL", str(exc))


# ---------------------------------------------------------------------------
# Section 4: Summary table + curl examples
# ---------------------------------------------------------------------------

CURL_EXAMPLES = """
Curl examples (informational -- requires n8n running and workflow activated):

  # Health check manual trigger (GET to n8n webhook):
  # First get the webhook URL from the n8n UI for ris_health_check workflow, then:
  curl -X GET http://localhost:5678/webhook/<health-check-webhook-id>

  # Manual acquire trigger (POST to webhook):
  # Get webhook URL from n8n UI for RIS Manual Acquire workflow, then:
  curl -X POST http://localhost:5678/webhook/<acquire-webhook-id> \\
    -H "Content-Type: application/json" \\
    -d '{"url": "https://arxiv.org/abs/2301.00001", "source_family": "academic"}'

  # Valid source_family values: academic, github, blog, news, book, reddit, youtube

NOTE: Webhook URLs contain n8n-generated auth tokens. Treat them as secrets.
Do not log or share the full webhook URL in plain text.
"""


def print_summary() -> None:
    print("\n" + "=" * 70)
    print("SMOKE TEST SUMMARY")
    print("=" * 70)

    # Column widths
    col_status = 6
    col_name = 55

    # Header
    print(f"  {'STATUS':<{col_status}}  {'CHECK':<{col_name}}")
    print(f"  {'-'*col_status}  {'-'*col_name}")

    pass_count = fail_count = skip_count = 0
    for r in results:
        if r.status == "PASS":
            pass_count += 1
            status_str = "PASS"
        elif r.status == "FAIL":
            fail_count += 1
            status_str = "FAIL"
        else:
            skip_count += 1
            status_str = "SKIP"

        name_str = r.name[:col_name]
        print(f"  {status_str:<{col_status}}  {name_str}")
        if r.detail and r.status in ("FAIL", "SKIP"):
            # Print detail indented on next line for failures/skips
            detail_str = r.detail[:80]
            print(f"  {'':<{col_status}}    -> {detail_str}")

    print(f"\n  Total: {pass_count} PASS, {fail_count} FAIL, {skip_count} SKIP")
    print("=" * 70)

    if fail_count == 0:
        print("\nRESULT: ALL CHECKS PASSED (or SKIP)")
    else:
        print(f"\nRESULT: {fail_count} CHECK(S) FAILED")

    print(CURL_EXAMPLES)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("RIS n8n Pilot -- Smoke Test")
    print(f"Repo root: {REPO_ROOT}")

    validate_workflows()
    validate_cli_entrypoints()
    validate_compose_profile()
    print_summary()

    fail_count = sum(1 for r in results if r.status == "FAIL")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
