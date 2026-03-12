"""Kill switch primitive for the live execution layer.

A FileBasedKillSwitch trips when a file exists and contains truthy text
("1", "true", "yes", case-insensitive).  An absent or empty file is not
tripped.  This lets an operator trip the switch with a simple shell command:

    echo 1 > artifacts/kill_switch.txt

and clear it by removing the file or writing a falsy value.
"""

from __future__ import annotations

from pathlib import Path


class KillSwitch:
    """Abstract interface for kill-switch implementations."""

    def is_tripped(self) -> bool:  # pragma: no cover
        raise NotImplementedError

    def check_or_raise(self) -> None:  # pragma: no cover
        raise NotImplementedError


_TRUTHY = {"1", "true", "yes", "on"}


class FileBasedKillSwitch(KillSwitch):
    """Kill switch backed by a plain text file on disk.

    Args:
        path: Path to the kill-switch sentinel file.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def is_tripped(self) -> bool:
        """Return True iff the file exists and contains a truthy value."""
        if not self.path.exists():
            return False
        try:
            content = self.path.read_text(encoding="utf-8").strip().lower()
        except OSError:
            return False
        return content in _TRUTHY

    def check_or_raise(self) -> None:
        """Raise RuntimeError if the kill switch is active."""
        if self.is_tripped():
            raise RuntimeError(f"Kill switch is active: {self.path}")
