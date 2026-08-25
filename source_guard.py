"""Pytest plugin: block writes to shipped (non-test) Python source.

Three layers:
  1. ``sys.addaudithook`` — fail the offending test at write time.
  2. Per-test ``lstat`` residue detection against a session baseline.
  3. Session-end ``git status --porcelain`` ground truth (controller only).

Residual (stated, not attributed to an individual test by layer 2): a same-size
rewrite whose ``mtime_ns`` was restored is caught at session end only. No layer
can promise anything about a ``SIGKILL`` landing mid-write.
"""
from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import sys

import pytest

# Injection seam for subprocess wiring proofs (defaults to repo root).
REPO_ROOT_ENV = "SUPERHEROES_SOURCE_GUARD_ROOT"

# Module-level mutable watched set — tests may replace without reinstalling hooks.
_WATCHED_PATHS = set()

_BASELINE_SIGNATURES = {}
_BASELINE_HASHES = {}
_CURRENT_SIGNATURES = {}

_SESSION_START_DIRTY = set()
_REPO_ROOT = None
_CURRENT_TEST_NODEID = None


class ShippedSourceWrite(RuntimeError):
    """Raised when a watched shipped-source path is opened for writing."""


def watched_paths(repo_root):
    """Absolute realpaths of every tracked non-test .py file. Authoritative: git ls-files."""
    proc = subprocess.run(
        ["git", "ls-files", "-z", "*.py"],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "source_guard: git ls-files failed (exit %d): %s"
            % (proc.returncode, proc.stderr.decode("utf-8", "replace"))
        )
    raw = proc.stdout
    if not raw:
        raise RuntimeError("source_guard: git ls-files returned no tracked .py files")
    paths = []
    for rel in raw.split(b"\0"):
        if not rel:
            continue
        rel_str = rel.decode("utf-8", "replace")
        if "/tests/" in rel_str or rel_str.startswith("tests/"):
            continue
        paths.append(os.path.realpath(os.path.join(repo_root, rel_str)))
    if not paths:
        raise RuntimeError("source_guard: watched set is empty after excluding tests/")
    return frozenset(paths)


def _lstat_signature(path):
    st = os.lstat(path)
    return (st.st_mode, stat.S_IFMT(st.st_mode), st.st_size, st.st_mtime_ns)


def _file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _capture_baseline(paths):
    sigs = {}
    hashes = {}
    for path in paths:
        sigs[path] = _lstat_signature(path)
        hashes[path] = _file_hash(path)
    return {"signatures": sigs, "hashes": hashes}


def _apply_baseline(baseline):
    global _BASELINE_SIGNATURES, _BASELINE_HASHES, _CURRENT_SIGNATURES
    _BASELINE_SIGNATURES = dict(baseline["signatures"])
    _BASELINE_HASHES = dict(baseline["hashes"])
    _CURRENT_SIGNATURES = dict(baseline["signatures"])


def _git_dirty_paths(repo_root):
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_root,
        capture_output=True,
        check=False,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "source_guard: git status failed (exit %d): %s"
            % (proc.returncode, proc.stderr)
        )
    dirty = set()
    for line in proc.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        dirty.add(os.path.realpath(os.path.join(repo_root, path)))
    return dirty


def _is_write_open(mode, flags):
    if mode is None:
        write_flags = (
            os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_TRUNC | os.O_CREAT
        )
        return bool(flags & write_flags)
    if isinstance(mode, str):
        return any(ch in mode for ch in "wax+")
    return False


def _path_hits_watched(path):
    if not isinstance(path, (str, bytes)):
        return False
    if isinstance(path, bytes):
        path = path.decode("utf-8", "replace")
    real = os.path.realpath(path)
    return real in _WATCHED_PATHS


def audit_hook(event, args):
    """Raise ShippedSourceWrite when a watched path is opened for writing or replaced."""
    if event == "open":
        path, mode, flags = args
        if not _is_write_open(mode, flags):
            return
        if _path_hits_watched(path):
            node = _CURRENT_TEST_NODEID or "<unknown test>"
            raise ShippedSourceWrite(
                "write to shipped source %r blocked — see %s"
                % (path, node)
            )
        return

    if event in ("os.rename", "os.replace", "os.remove", "os.truncate"):
        for arg in args:
            if _path_hits_watched(arg):
                node = _CURRENT_TEST_NODEID or "<unknown test>"
                raise ShippedSourceWrite(
                    "%s on shipped source %r blocked — see %s"
                    % (event, arg, node)
                )


def _resolve_repo_root(config):
    env = os.environ.get(REPO_ROOT_ENV)
    if env:
        return os.path.realpath(env)
    return os.path.realpath(str(config.rootpath))


def pytest_addoption(parser):
    parser.addini(
        "source_guard_loaded",
        "Marker that source_guard plugin registered",
        default="yes",
    )


def pytest_configure(config):
    global _REPO_ROOT, _SESSION_START_DIRTY
    config._source_guard_active = True
    _REPO_ROOT = _resolve_repo_root(config)

    workerinput = getattr(config, "workerinput", None)
    if workerinput is None:
        paths = watched_paths(_REPO_ROOT)
        _WATCHED_PATHS.clear()
        _WATCHED_PATHS.update(paths)
        baseline = _capture_baseline(paths)
        config._source_guard_baseline = baseline
        _apply_baseline(baseline)
        _SESSION_START_DIRTY = _git_dirty_paths(_REPO_ROOT)
    else:
        baseline = workerinput["source_guard_baseline"]
        paths = workerinput["source_guard_watched"]
        _WATCHED_PATHS.clear()
        _WATCHED_PATHS.update(paths)
        _apply_baseline(baseline)

    if not getattr(config, "_source_guard_hook_installed", False):
        sys.addaudithook(audit_hook)
        config._source_guard_hook_installed = True


def pytest_configure_node(node):
    baseline = node.config._source_guard_baseline
    node.workerinput["source_guard_baseline"] = baseline
    node.workerinput["source_guard_watched"] = list(_WATCHED_PATHS)


@pytest.fixture(autouse=True, scope="function")
def _source_guard_test_context(request):
    global _CURRENT_TEST_NODEID
    _CURRENT_TEST_NODEID = request.node.nodeid
    yield
    _CURRENT_TEST_NODEID = None
    _check_residue(request.node.nodeid)


def _check_residue(test_nodeid):
    changed = []
    for path in _WATCHED_PATHS:
        if path not in _BASELINE_HASHES:
            continue
        try:
            current_sig = _lstat_signature(path)
        except OSError as exc:
            pytest.fail(
                "source_guard: cannot lstat watched file %r after %s: %s"
                % (path, test_nodeid, exc)
            )
        baseline_sig = _BASELINE_SIGNATURES.get(path)
        cached_sig = _CURRENT_SIGNATURES.get(path, baseline_sig)
        if current_sig == cached_sig:
            continue
        current_hash = _file_hash(path)
        baseline_hash = _BASELINE_HASHES[path]
        if current_hash == baseline_hash:
            _CURRENT_SIGNATURES[path] = current_sig
            continue
        changed.append(path)
    if changed:
        pytest.fail(
            "source_guard: shipped source mutated by %s: %s"
            % (test_nodeid, ", ".join(sorted(changed)))
        )


def pytest_sessionfinish(session, exitstatus):
    if getattr(session.config, "workerinput", None) is not None:
        return
    end_dirty = _git_dirty_paths(_REPO_ROOT)
    new_dirty = end_dirty - _SESSION_START_DIRTY
    if new_dirty:
        session.exitstatus = 1
        paths = ", ".join(sorted(new_dirty))
        session.config._source_guard_session_failure = (
            "source_guard: session left shipped source dirty: %s" % paths
        )
        tw = session.config.pluginmanager.getplugin("terminalreporter")
        if tw is not None:
            tw.write_line(session.config._source_guard_session_failure, red=True)
