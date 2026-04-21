#!/usr/bin/env python3
"""Import the canonical RIS n8n workflow set via the n8n REST API.

This helper is cross-platform and matches the shape of the committed
workflow JSON files under ``infra/n8n/workflows``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib import error, parse, request

ROOT_DIR = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT_DIR / "infra" / "n8n" / "workflows"
WORKFLOW_IDS_PATH = WORKFLOW_DIR / "workflow_ids.env"
ENV_PATH = ROOT_DIR / ".env"
CANONICAL_WORKFLOWS = [
    ("UNIFIED_DEV_ID", "ris-unified-dev.json"),
    ("HEALTH_WEBHOOK_ID", "ris-health-webhook.json"),
]
WORKFLOW_STRING_PLACEHOLDERS = {
    "__RIS_OPERATOR_WEBHOOK_URL__": "DISCORD_WEBHOOK_URL",
}


def read_dotenv_value(key: str) -> str | None:
    if not ENV_PATH.exists():
        return None
    for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        lhs, rhs = line.split("=", 1)
        if lhs.strip() == key:
            return rhs.strip().strip('"').strip("'")
    return None


def read_config_value(key: str) -> tuple[str | None, str | None]:
    env_value = os.environ.get(key)
    if env_value:
        return env_value, "environment"

    dotenv_value = read_dotenv_value(key)
    if dotenv_value:
        return dotenv_value, ".env"

    return None, None


def escape_js_single_quoted_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def workflow_string_replacements() -> tuple[dict[str, str], dict[str, str]]:
    replacements: dict[str, str] = {}
    sources: dict[str, str] = {}

    for placeholder, env_key in WORKFLOW_STRING_PLACEHOLDERS.items():
        raw_value, source = read_config_value(env_key)
        replacements[placeholder] = escape_js_single_quoted_string(raw_value or "")
        sources[env_key] = source or "missing"

    return replacements, sources


def apply_string_replacements(payload: Any, replacements: dict[str, str]) -> Any:
    if isinstance(payload, str):
        updated = payload
        for placeholder, value in replacements.items():
            updated = updated.replace(placeholder, value)
        return updated
    if isinstance(payload, list):
        return [apply_string_replacements(item, replacements) for item in payload]
    if isinstance(payload, dict):
        return {
            key: apply_string_replacements(value, replacements)
            for key, value in payload.items()
        }
    return payload


def read_workflow_ids() -> dict[str, str]:
    if not WORKFLOW_IDS_PATH.exists():
        return {}
    ids: dict[str, str] = {}
    for raw_line in WORKFLOW_IDS_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        lhs, rhs = line.split("=", 1)
        ids[lhs.strip()] = rhs.strip()
    return ids


def write_workflow_ids(ids: dict[str, str]) -> None:
    lines = [
        "# RIS n8n Workflow IDs",
        "# Updated by infra/n8n/import_workflows.py",
        "# Canonical import file: infra/n8n/workflows/ris-unified-dev.json",
        "",
    ]
    for key, value in sorted(ids.items()):
        lines.append(f"{key}={value}")
    WORKFLOW_IDS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def request_json(
    method: str,
    base_url: str,
    api_key: str,
    endpoint: str,
    *,
    payload: dict[str, Any] | None = None,
) -> Any:
    url = f"{base_url.rstrip('/')}{endpoint}"
    headers = {
        "X-N8N-API-KEY": api_key,
        "Accept": "application/json",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req) as response:
            content = response.read().decode("utf-8")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {endpoint} failed: HTTP {exc.code} {body}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"{method} {endpoint} failed: {exc.reason}") from exc

    if not content:
        return None
    return json.loads(content)


def get_existing_workflow_id(
    base_url: str,
    api_key: str,
    workflow_name: str,
    known_id: str | None,
) -> str | None:
    if known_id:
        try:
            workflow = request_json(
                "GET",
                base_url,
                api_key,
                f"/api/v1/workflows/{parse.quote(known_id)}",
            )
        except RuntimeError as exc:
            if "HTTP 404" not in str(exc):
                raise
        else:
            if workflow.get("name") == workflow_name:
                return str(workflow["id"])

    data = request_json("GET", base_url, api_key, "/api/v1/workflows")
    for workflow in data.get("data", []):
        if workflow.get("name") == workflow_name:
            return str(workflow["id"])
    return None


def import_workflow(
    base_url: str,
    api_key: str,
    id_key: str,
    filename: str,
    activate: bool,
    replacements: dict[str, str],
) -> tuple[str, str]:
    workflow_path = WORKFLOW_DIR / filename
    if not workflow_path.exists():
        raise FileNotFoundError(f"Workflow file not found: {workflow_path}")

    workflow_payload = json.loads(workflow_path.read_text(encoding="utf-8"))
    workflow_payload = apply_string_replacements(workflow_payload, replacements)
    workflow_name = workflow_payload["name"]
    workflow_ids = read_workflow_ids()
    existing_id = get_existing_workflow_id(
        base_url,
        api_key,
        workflow_name,
        workflow_ids.get(id_key),
    )

    if existing_id:
        response = request_json(
            "PUT",
            base_url,
            api_key,
            f"/api/v1/workflows/{parse.quote(existing_id)}",
            payload=workflow_payload,
        )
        workflow_id = str(response["id"])
        action = "updated"
    else:
        response = request_json(
            "POST",
            base_url,
            api_key,
            "/api/v1/workflows",
            payload=workflow_payload,
        )
        workflow_id = str(response["id"])
        action = "created"

    workflow_ids[id_key] = workflow_id
    write_workflow_ids(workflow_ids)

    current = request_json(
        "GET",
        base_url,
        api_key,
        f"/api/v1/workflows/{parse.quote(workflow_id)}",
    )
    if activate and not current.get("active", False):
        request_json(
            "POST",
            base_url,
            api_key,
            f"/api/v1/workflows/{parse.quote(workflow_id)}/activate",
        )
        action = f"{action} + activated"
    elif activate:
        action = f"{action} + already-active"

    return workflow_id, action


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("N8N_BASE_URL") or read_dotenv_value("N8N_BASE_URL") or "http://localhost:5678",
        help="Base URL for the n8n instance.",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("N8N_API_KEY") or read_dotenv_value("N8N_API_KEY"),
        help="n8n API key. Defaults to N8N_API_KEY from the environment or .env.",
    )
    parser.add_argument(
        "--no-activate",
        action="store_true",
        help="Import/update workflows without activating them.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.api_key:
        print("ERROR: N8N_API_KEY was not provided and was not found in .env.", file=sys.stderr)
        return 1

    try:
        replacements, replacement_sources = workflow_string_replacements()
        print(f"Importing canonical workflows into {args.base_url} ...")
        for env_key, source in replacement_sources.items():
            status = "configured" if source != "missing" else "missing"
            print(f"  {env_key}: {status} ({source})")
        for id_key, filename in CANONICAL_WORKFLOWS:
            workflow_id, action = import_workflow(
                args.base_url,
                args.api_key,
                id_key,
                filename,
                activate=not args.no_activate,
                replacements=replacements,
            )
            print(f"  {filename}: {workflow_id} ({action})")
    except Exception as exc:  # pragma: no cover - CLI path
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("Import complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
