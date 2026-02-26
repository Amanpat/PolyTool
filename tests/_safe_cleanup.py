from __future__ import annotations

import inspect
import os
import shutil
import stat
from pathlib import Path
from typing import Iterable


def _is_mount_or_junction(path: Path) -> bool:
    try:
        if path.is_mount():
            return True
    except OSError:
        pass
    isjunction = getattr(os.path, "isjunction", None)
    if isjunction is None:
        return False
    try:
        return bool(isjunction(os.fspath(path)))
    except OSError:
        return False


def _is_within_allowed_roots(target: Path, allowed_roots: Iterable[Path]) -> bool:
    resolved_target = target.resolve(strict=False)
    for root in allowed_roots:
        resolved_root = Path(root).resolve(strict=False)
        if resolved_target == resolved_root or resolved_target.is_relative_to(resolved_root):
            return True
    return False


def safe_rmtree(
    target: str | Path,
    *,
    allowed_roots: Iterable[Path],
    ignore_errors: bool = False,
) -> bool:
    """
    Safely remove a test temp directory.

    Returns True when removal completed (or target did not exist), False when removal
    was intentionally skipped (for example mount/junction or ignored error).
    """
    target_path = Path(target)
    resolved_target = target_path.resolve(strict=False)
    if not _is_within_allowed_roots(resolved_target, allowed_roots):
        if ignore_errors:
            return False
        raise RuntimeError(f"Refusing to delete non-test-temp path: {resolved_target}")

    if not target_path.exists():
        return True
    if _is_mount_or_junction(target_path):
        return False

    def _onexc(func, path, exc: BaseException) -> None:
        if isinstance(exc, FileNotFoundError):
            return
        failing_path = Path(path)
        if _is_mount_or_junction(failing_path):
            return
        if isinstance(exc, PermissionError):
            try:
                os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
            except OSError:
                pass
            try:
                func(path)
                return
            except FileNotFoundError:
                return
            except PermissionError as retry_exc:
                if ignore_errors:
                    return
                raise retry_exc
        if ignore_errors:
            return
        raise exc

    rmtree_params = inspect.signature(shutil.rmtree).parameters
    if "onexc" in rmtree_params:
        shutil.rmtree(target_path, ignore_errors=False, onexc=_onexc)
        return True

    def _onerror(func, path, exc_info) -> None:
        _onexc(func, path, exc_info[1])

    shutil.rmtree(target_path, ignore_errors=False, onerror=_onerror)
    return True
