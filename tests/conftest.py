from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path

import pytest


_ISOLATED_ENV_VARS = (
    "POLYTOOL_KB_ROOT",
    "POLYTOOL_ARTIFACTS_ROOT",
    "POLYTOOL_CACHE_DIR",
    "TMPDIR",
    "TEMP",
    "TMP",
)

_PREVIOUS_CWD: Path | None = None
_PREVIOUS_ENV: dict[str, str | None] = {}
_WORKSPACE_ROOT: Path | None = None
_ORIGINAL_TEMPORARY_DIRECTORY = None


def pytest_configure(config: pytest.Config) -> None:
    """Guard pytest tmpdir cleanup against Windows ACL edge cases."""
    import _pytest.tmpdir as pytest_tmpdir

    repo_root = Path(__file__).resolve().parent.parent
    basetemp_root = repo_root / ".tmp" / "pytest-basetemp"
    basetemp_root.mkdir(parents=True, exist_ok=True)
    if not config.option.basetemp:
        config.option.basetemp = str(basetemp_root / uuid.uuid4().hex)

    original_cleanup = pytest_tmpdir.cleanup_dead_symlinks
    original_getbasetemp = pytest_tmpdir.TempPathFactory.getbasetemp

    def _safe_getbasetemp(self):
        if self._basetemp is not None:
            return self._basetemp
        if self._given_basetemp is not None:
            basetemp = self._given_basetemp
            if basetemp.exists():
                shutil.rmtree(basetemp, ignore_errors=True)
            # Avoid 0o700 ACL issues in restricted Windows environments.
            basetemp.mkdir(mode=0o777, parents=True, exist_ok=True)
            self._basetemp = basetemp.resolve()
            self._trace("new basetemp", self._basetemp)
            return self._basetemp
        return original_getbasetemp(self)

    def _safe_cleanup_dead_symlinks(root: Path) -> None:
        try:
            original_cleanup(root)
        except PermissionError:
            # Some Windows/sandbox ACL combinations make basetemp unreadable
            # during session shutdown even when test execution succeeded.
            return

    def _safe_mktemp(self, basename: str, numbered: bool = True):
        basename = self._ensure_relative_to_basetemp(basename)
        if not numbered:
            path = self.getbasetemp().joinpath(basename)
            path.mkdir(mode=0o777)
            return path
        path = pytest_tmpdir.make_numbered_dir(
            root=self.getbasetemp(),
            prefix=basename,
            mode=0o777,
        )
        self._trace("mktemp", path)
        return path

    pytest_tmpdir.TempPathFactory.getbasetemp = _safe_getbasetemp
    pytest_tmpdir.TempPathFactory.mktemp = _safe_mktemp
    pytest_tmpdir.cleanup_dead_symlinks = _safe_cleanup_dead_symlinks

    # Global test workspace + env isolation (applies to unittest-style tests too).
    global _PREVIOUS_CWD, _PREVIOUS_ENV, _WORKSPACE_ROOT, _ORIGINAL_TEMPORARY_DIRECTORY
    repo_root = Path(__file__).resolve().parent.parent
    workspaces_root = repo_root / ".tmp" / "test-workspaces"
    workspace_root = workspaces_root / uuid.uuid4().hex
    kb_root = workspace_root / "kb"
    artifacts_root = workspace_root / "artifacts"
    cache_root = workspace_root / "cache"
    for path in (workspaces_root, kb_root, artifacts_root, cache_root):
        path.mkdir(parents=True, exist_ok=True)

    _PREVIOUS_CWD = Path.cwd()
    _PREVIOUS_ENV = {key: os.environ.get(key) for key in _ISOLATED_ENV_VARS}
    _WORKSPACE_ROOT = workspace_root

    os.environ["POLYTOOL_KB_ROOT"] = str(kb_root)
    os.environ["POLYTOOL_ARTIFACTS_ROOT"] = str(artifacts_root)
    os.environ["POLYTOOL_CACHE_DIR"] = str(cache_root)
    os.environ["TMPDIR"] = str(cache_root)
    os.environ["TEMP"] = str(cache_root)
    os.environ["TMP"] = str(cache_root)
    tempfile.tempdir = str(cache_root)

    _ORIGINAL_TEMPORARY_DIRECTORY = tempfile.TemporaryDirectory

    class _SafeTemporaryDirectory:
        def __init__(
            self,
            suffix: str | None = None,
            prefix: str | None = None,
            dir: str | os.PathLike[str] | None = None,
            ignore_cleanup_errors: bool = False,
        ) -> None:
            base_dir = Path(dir) if dir is not None else cache_root
            base_dir.mkdir(parents=True, exist_ok=True)
            token = uuid.uuid4().hex
            name = f"{prefix or 'tmp'}{token}{suffix or ''}"
            path = base_dir / name
            path.mkdir(mode=0o777, parents=True, exist_ok=False)
            self.name = str(path)
            self._ignore_cleanup_errors = ignore_cleanup_errors
            self._closed = False

        def __enter__(self) -> str:
            return self.name

        def __exit__(self, exc_type, exc, tb) -> None:
            self.cleanup()

        def cleanup(self) -> None:
            if self._closed:
                return
            self._closed = True
            try:
                shutil.rmtree(self.name, ignore_errors=False)
            except Exception:
                if not self._ignore_cleanup_errors:
                    raise

    tempfile.TemporaryDirectory = _SafeTemporaryDirectory  # type: ignore[assignment]
    os.chdir(workspace_root)


def pytest_unconfigure(config: pytest.Config) -> None:
    global _PREVIOUS_CWD, _PREVIOUS_ENV, _WORKSPACE_ROOT, _ORIGINAL_TEMPORARY_DIRECTORY
    if _PREVIOUS_CWD is not None:
        os.chdir(_PREVIOUS_CWD)
    for key, value in _PREVIOUS_ENV.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    tempfile.tempdir = None
    if _ORIGINAL_TEMPORARY_DIRECTORY is not None:
        tempfile.TemporaryDirectory = _ORIGINAL_TEMPORARY_DIRECTORY  # type: ignore[assignment]
    if _WORKSPACE_ROOT is not None:
        shutil.rmtree(_WORKSPACE_ROOT, ignore_errors=True)
