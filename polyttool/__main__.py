"""Backward-compatibility shim for polyttool -> polytool migration.

DEPRECATION WARNING: This module is deprecated and will be removed.
Use 'python -m polytool' or the 'polytool' CLI instead.

This shim exists only for backward compatibility during the transition period.
See docs/adr/ADR-0001-cli-and-module-rename.md for details.
"""

from __future__ import annotations

import sys
import warnings

_DEPRECATION_SHOWN = False


def _show_deprecation_warning() -> None:
    """Show deprecation warning once per invocation."""
    global _DEPRECATION_SHOWN
    if not _DEPRECATION_SHOWN:
        warnings.warn(
            "'polyttool' is deprecated. Use 'polytool' instead. "
            "This shim will be removed in v0.2.0 or after the first stable release. "
            "See docs/adr/ADR-0001-cli-and-module-rename.md for migration details.",
            DeprecationWarning,
            stacklevel=3,
        )
        print(
            "DEPRECATION WARNING: 'python -m polyttool' is deprecated. "
            "Use 'python -m polytool' instead.",
            file=sys.stderr,
        )
        _DEPRECATION_SHOWN = True


def main() -> int:
    """Forward to polytool main with deprecation warning."""
    _show_deprecation_warning()
    from polytool.__main__ import main as polytool_main
    return polytool_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
