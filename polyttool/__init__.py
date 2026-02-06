"""Backward-compatibility shim for polyttool -> polytool migration.

DEPRECATION WARNING: This package is deprecated. Use 'polytool' instead.
This shim will be removed in v0.2.0 or after the first stable release.
"""

import warnings

warnings.warn(
    "The 'polyttool' package is deprecated. Use 'polytool' instead. "
    "This shim will be removed in v0.2.0.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export from polytool for backward compatibility
from polytool import __version__

__all__ = ["__version__"]
