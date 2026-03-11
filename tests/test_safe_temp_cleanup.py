from __future__ import annotations

from pathlib import Path

import pytest

from tests import _safe_cleanup as cleanup


def test_safe_rmtree_refuses_path_outside_allowed_root(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()

    with pytest.raises(RuntimeError, match="Refusing to delete"):
        cleanup.safe_rmtree(outside, allowed_roots=(allowed,))

    assert outside.exists()


def test_safe_rmtree_skips_mount_or_junction(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    target = allowed / "junction_like"
    target.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(cleanup, "_is_mount_or_junction", lambda _p: True)

    removed = cleanup.safe_rmtree(target, allowed_roots=(allowed,))

    assert removed is False
    assert target.exists()


def test_safe_rmtree_chmods_and_retries_permission_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    allowed = tmp_path / "allowed"
    target = allowed / "to_delete"
    target.mkdir(parents=True, exist_ok=True)
    locked_file = target / "locked.txt"
    locked_file.write_text("locked", encoding="utf-8")

    state = {"chmod_called": False, "retry_calls": 0}

    def fake_chmod(path, mode) -> None:
        state["chmod_called"] = True

    def retry_delete(path: str) -> None:
        state["retry_calls"] += 1
        if not state["chmod_called"]:
            raise PermissionError("locked")
        Path(path).unlink()

    def fake_rmtree(path, ignore_errors=False, onerror=None, onexc=None, dir_fd=None) -> None:
        callback = onexc
        if callback is None:
            assert onerror is not None

            def _wrapped(func, failing_path, exc):
                onerror(func, failing_path, (type(exc), exc, None))

            callback = _wrapped
        callback(retry_delete, str(locked_file), PermissionError("locked"))
        Path(path).rmdir()

    monkeypatch.setattr(cleanup.os, "chmod", fake_chmod)
    monkeypatch.setattr(cleanup.shutil, "rmtree", fake_rmtree)

    removed = cleanup.safe_rmtree(target, allowed_roots=(allowed,))

    assert removed is True
    assert state["chmod_called"] is True
    assert state["retry_calls"] == 1
    assert not target.exists()
