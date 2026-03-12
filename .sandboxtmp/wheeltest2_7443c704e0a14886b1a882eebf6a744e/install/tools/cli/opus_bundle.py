#!/usr/bin/env python3
"""Deprecated Opus bundle wrapper."""

from __future__ import annotations

import os
import sys
from typing import Optional

if __package__ is None or __package__ == "":
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from tools.cli import llm_bundle


def main(argv: Optional[list[str]] = None) -> int:
    print("Warning: 'opus-bundle' is deprecated; use 'llm-bundle' instead.", file=sys.stderr)
    return llm_bundle.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
