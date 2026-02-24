"""Config loader with UTF-8 BOM support.

PowerShell 5.1 writes UTF-8 BOM by default when using Out-File.  Plain
``json.loads(path.read_text(encoding="utf-8"))`` rejects such files with a
JSONDecodeError.  All config loading goes through this module so the fix is
applied globally.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union


class ConfigLoadError(ValueError):
    """Raised when config loading or parsing fails."""


def load_json_from_path(path: Union[str, Path]) -> dict:
    """Load a JSON file, accepting UTF-8 BOM (as produced by PowerShell 5.1).

    Args:
        path: Path to the JSON file.

    Returns:
        Parsed JSON object as a dict.

    Raises:
        ConfigLoadError: If the file is not found or contains invalid JSON.
    """
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise ConfigLoadError(f"config file not found: {p}") from exc

    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigLoadError(f"config file is not valid JSON ({p}): {exc}") from exc

    if not isinstance(result, dict):
        raise ConfigLoadError(
            f"config file must contain a JSON object, got {type(result).__name__}: {p}"
        )
    return result


def load_json_from_string(raw: str) -> dict:
    """Parse a JSON string into a dict.

    Strips a leading UTF-8 BOM character (U+FEFF) if present so that strings
    produced by PowerShell 5.1 ``ConvertTo-Json | Out-String`` pipelines parse
    correctly.

    Args:
        raw: JSON string, optionally BOM-prefixed.

    Returns:
        Parsed JSON object as a dict.

    Raises:
        ConfigLoadError: If the string is not valid JSON or not an object.
    """
    if raw.startswith("\ufeff"):
        raw = raw[1:]
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigLoadError(f"config string is not valid JSON: {exc}") from exc

    if not isinstance(result, dict):
        raise ConfigLoadError(
            f"config string must be a JSON object, got {type(result).__name__}"
        )
    return result


def load_strategy_config(
    *,
    config_path: Union[str, Path, None] = None,
    config_json: Union[str, None] = None,
) -> dict:
    """Load strategy config from a file path, a JSON string, or return {}.

    Exactly one of ``config_path`` and ``config_json`` may be provided.

    Args:
        config_path: Path to a JSON config file (accepts UTF-8 BOM).
        config_json: Raw JSON string.

    Returns:
        Config dict, or {} if neither argument is provided.

    Raises:
        ConfigLoadError: If both arguments are provided, or if loading fails.
    """
    if config_path is not None and config_json is not None:
        raise ConfigLoadError(
            "Provide only one of config_path or config_json, not both."
        )

    if config_path is not None:
        return load_json_from_path(config_path)

    if config_json is not None:
        return load_json_from_string(config_json)

    return {}
