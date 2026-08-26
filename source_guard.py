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


class ShippedSourceWrite(RuntimeError):
    """Raised when a watched shipped-source path is opened for writing."""


def missing_wiring_files(root):
    """Return the sorted subset of required root files that are missing under ``root``.

    Checks only that ``pytest.ini``, ``conftest.py``, and ``source_guard.py`` exist
    as regular files at the repository root. File presence does not imply the guard
    loads; see the behavioural wiring tests in ``test_source_guard`` for effective
    wiring.
    """
    missing = []
    if not os.path.isdir(root):
        missing.extend(
            [
                "pytest.ini is missing at the repository root",
                "conftest.py is missing at the repository root",
                "source_guard.py is missing at the repository root",
            ]
        )
        return sorted(missing)

    root = os.path.realpath(root)

    pytest_ini_path = os.path.join(root, "pytest.ini")
    if not os.path.isfile(pytest_ini_path):
        missing.append("pytest.ini is missing at the repository root")

    conftest_path = os.path.join(root, "conftest.py")
    if not os.path.isfile(conftest_path):
        missing.append("conftest.py is missing at the repository root")

    source_guard_path = os.path.join(root, "source_guard.py")
    if not os.path.isfile(source_guard_path):
        missing.append("source_guard.py is missing at the repository root")

    return sorted(missing)


def watched_paths(repo_root):
    """Absolute realpaths of every tracked non-test .py file. Authoritative: git ls-files."""
    proc = subprocess.run(
        ["git", "ls-files", "-z", "--full-name", "*.py"],
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


def _git_dirty_paths(repo_root):
    proc = subprocess.run(
        ["git", "-c", "core.quotepath=false", "status", "--porcelain", "-z"],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "source_guard: git status failed (exit %d): %s"
            % (proc.returncode, proc.stderr.decode("utf-8", "replace"))
        )
    dirty = set()
    entries = proc.stdout.split(b"\0")
    i = 0
    while i < len(entries):
        entry = entries[i]
        if not entry:
            i += 1
            continue
        if len(entry) < 3:
            i += 1
            continue
        status = entry[:2]
        if status[0] == ord("R") or status[1] == ord("R"):
            i += 1
            if i >= len(entries) or not entries[i]:
                break
            path = entries[i].decode("utf-8", "replace")
            i += 1
        else:
            path = entry[3:].decode("utf-8", "replace")
            i += 1
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


def _resolve_repo_root(config):
    candidate = os.environ.get(REPO_ROOT_ENV)
    if candidate is None:
        candidate = str(config.rootpath)
    proc = subprocess.run(
        ["git", "-C", candidate, "rev-parse", "--show-toplevel"],
        capture_output=True,
        check=False,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "source_guard: git rev-parse --show-toplevel failed (exit %d): %s"
            % (proc.returncode, proc.stderr)
        )
    return os.path.realpath(proc.stdout.strip())


class GuardState:
    def __init__(self, addaudithook):
        self._addaudithook = addaudithook
        self.repo_root = None
        self.watched = frozenset()
        self.baseline_signatures = {}
        self.baseline_hashes = {}
        self.current_signatures = {}
        self.session_start_dirty = frozenset()
        self.current_test_nodeid = None
        self.audit_hook_installed = False
        self.configured = False

    def configure(self, config):
        if self.configured:
            return False
        self.repo_root = _resolve_repo_root(config)

        workerinput = getattr(config, "workerinput", None)
        if workerinput is None:
            paths = watched_paths(self.repo_root)
            self.watched = frozenset(paths)
            baseline = _capture_baseline(paths)
            self.baseline_signatures = dict(baseline["signatures"])
            self.baseline_hashes = dict(baseline["hashes"])
            self.current_signatures = dict(baseline["signatures"])
            self.session_start_dirty = frozenset(_git_dirty_paths(self.repo_root))
        else:
            baseline = workerinput["source_guard_baseline"]
            paths = workerinput["source_guard_watched"]
            self.watched = frozenset(paths)
            self.baseline_signatures = dict(baseline["signatures"])
            self.baseline_hashes = dict(baseline["hashes"])
            self.current_signatures = dict(baseline["signatures"])

        self.install_audit_hook()
        self.configured = True
        return True

    def install_audit_hook(self):
        if self.audit_hook_installed:
            return
        self._addaudithook(self.audit)
        self.audit_hook_installed = True

    def _path_hits_watched(self, path):
        if not isinstance(path, (str, bytes)):
            return False
        if isinstance(path, bytes):
            path = path.decode("utf-8", "replace")
        real = os.path.realpath(path)
        return real in self.watched

    def audit(self, event, args):
        """Raise ShippedSourceWrite when a watched path is opened for writing or replaced."""
        if event == "open":
            path, mode, flags = args
            if not _is_write_open(mode, flags):
                return
            if self._path_hits_watched(path):
                node = self.current_test_nodeid or "<unknown test>"
                raise ShippedSourceWrite(
                    "write to shipped source %r blocked — see %s"
                    % (path, node)
                )
            return

        if event in ("os.rename", "os.replace", "os.remove", "os.truncate"):
            for arg in args:
                if self._path_hits_watched(arg):
                    node = self.current_test_nodeid or "<unknown test>"
                    raise ShippedSourceWrite(
                        "%s on shipped source %r blocked — see %s"
                        % (event, arg, node)
                    )

    def check_residue(self, test_nodeid):
        changed = []
        for path in self.watched:
            if path not in self.baseline_hashes:
                continue
            try:
                current_sig = _lstat_signature(path)
            except OSError as exc:
                pytest.fail(
                    "source_guard: cannot lstat watched file %r after %s: %s"
                    % (path, test_nodeid, exc)
                )
            baseline_sig = self.baseline_signatures.get(path)
            cached_sig = self.current_signatures.get(path, baseline_sig)
            if current_sig == cached_sig:
                continue
            current_hash = _file_hash(path)
            baseline_hash = self.baseline_hashes[path]
            if current_hash == baseline_hash:
                self.current_signatures[path] = current_sig
                continue
            changed.append(path)
            self.current_signatures[path] = current_sig
            self.baseline_hashes[path] = current_hash
        if changed:
            pytest.fail(
                "source_guard: shipped source mutated by %s: %s"
                % (test_nodeid, ", ".join(sorted(changed)))
            )

    def export_to(self, node):
        node.workerinput["source_guard_baseline"] = {
            "signatures": dict(self.baseline_signatures),
            "hashes": dict(self.baseline_hashes),
        }
        node.workerinput["source_guard_watched"] = sorted(self.watched)

    def session_finish(self, session):
        self.configured = False
        if getattr(session.config, "workerinput", None) is not None:
            return
        end_dirty = _git_dirty_paths(self.repo_root)
        new_dirty = end_dirty - self.session_start_dirty
        watched_dirty = new_dirty & set(self.watched)
        if watched_dirty:
            if session.exitstatus == 0:
                session.exitstatus = 1
            paths = ", ".join(sorted(watched_dirty))
            session.config._source_guard_session_failure = (
                "source_guard: session left shipped source dirty: %s" % paths
            )
            tw = session.config.pluginmanager.getplugin("terminalreporter")
            if tw is not None:
                tw.write_line(session.config._source_guard_session_failure, red=True)


_LIVE = GuardState(sys.addaudithook)


def pytest_configure(config):
    return _LIVE.configure(config)


@pytest.hookimpl(optionalhook=True)
def pytest_configure_node(node):
    return _LIVE.export_to(node)


@pytest.fixture(autouse=True, scope="function")
def _source_guard_test_context(request):
    _LIVE.current_test_nodeid = request.node.nodeid
    yield
    _LIVE.current_test_nodeid = None
    _LIVE.check_residue(request.node.nodeid)


def pytest_sessionfinish(session, exitstatus):
    return _LIVE.session_finish(session)
