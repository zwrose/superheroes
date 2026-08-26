"""Pytest plugin: block writes to shipped (non-test) Python source.

Three layers:
  1. ``sys.addaudithook`` — fail the offending test at write time.
  2. Per-test ``lstat`` residue detection against a session baseline.
  3. Session-end ``git status --porcelain`` ground truth (controller only).

Residual (stated, not attributed to an individual test by layer 2): a same-size
rewrite whose ``mtime_ns`` was restored is caught at session end only. No layer
can promise anything about a ``SIGKILL`` landing mid-write.

Residual (stated): CPython's ``open`` audit event carries ``(path, mode, flags)``
and no ``dir_fd``, so a ``dir_fd``-relative ``os.open`` for writing cannot be
anchored from the event alone and stays resolved against the process cwd. The
replace-ish events (``os.remove``, ``os.rename``/``os.replace``) do carry their
anchors and are resolved against them. Layers 2 and 3 remain the backstop for
anything layer 1 declines to match.
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


_REQUIRED_ROOT_FILES = ("pytest.ini", "conftest.py", "source_guard.py")


def _missing_wiring_file_message(name):
    return "%s is missing at the repository root" % name


def _all_missing_wiring_messages():
    return [_missing_wiring_file_message(name) for name in _REQUIRED_ROOT_FILES]


def missing_wiring_files(root):
    """Return the sorted subset of required root files that are missing under ``root``.

    Checks only that ``pytest.ini``, ``conftest.py``, and ``source_guard.py`` exist
    as regular files at the repository root. File presence does not imply the guard
    loads; see the behavioural wiring tests in ``test_source_guard`` for effective
    wiring.
    """
    # bite-axis: presence only — the three required root files must exist as regular
    # files; presence is not effective wiring.
    missing = []
    if not os.path.isdir(root):
        missing.extend(_all_missing_wiring_messages())
        return sorted(missing)

    root = os.path.realpath(root)

    pytest_ini_path = os.path.join(root, "pytest.ini")
    if not os.path.isfile(pytest_ini_path):
        missing.append(_missing_wiring_file_message("pytest.ini"))

    conftest_path = os.path.join(root, "conftest.py")
    if not os.path.isfile(conftest_path):
        missing.append(_missing_wiring_file_message("conftest.py"))

    source_guard_path = os.path.join(root, "source_guard.py")
    if not os.path.isfile(source_guard_path):
        missing.append(_missing_wiring_file_message("source_guard.py"))

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


def _is_real_dir_fd(dir_fd):
    """True when ``dir_fd`` is an actual descriptor rather than the "no dir_fd" sentinel.

    Measured against CPython's audit events: the sentinel is reported as a negative
    int (``-1`` observed on macOS/3.9), and ``AT_FDCWD`` is negative on every platform
    that defines it, so the sign test needs no platform constant. A real descriptor is
    always non-negative.
    """
    # bite-axis: sign — a non-negative int is a real descriptor to anchor on; a
    # negative int, a non-int, or a bool is the cwd-anchored sentinel.
    if isinstance(dir_fd, bool) or not isinstance(dir_fd, int):
        return False
    return dir_fd >= 0


def _write_targets(event, args):
    """Pair every path argument of a replace-ish audit event with its own dir_fd anchor.

    Signatures measured from CPython's audit events: ``os.remove(path, dir_fd)``,
    ``os.rename(src, dst, src_dir_fd, dst_dir_fd)`` — which ``os.replace`` raises too,
    rather than a distinct ``os.replace`` event — and ``os.truncate(path_or_fd, length)``,
    which carries no dir_fd. Short arg tuples are tolerated so a signature change
    degrades to cwd anchoring rather than raising IndexError inside the audit hook.
    """
    # bite-axis: pairing — each path travels with the dir_fd that anchors THAT path,
    # so a rename's src and dst can never borrow each other's anchor.
    def arg(index):
        return args[index] if len(args) > index else None

    if event == "os.remove":
        return ((arg(0), arg(1)),)
    if event in ("os.rename", "os.replace"):
        return ((arg(0), arg(2)), (arg(1), arg(3)))
    if event == "os.truncate":
        return ((arg(0), None),)
    return ()


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

    def _relative_hits_watched(self, path, dir_fd):
        """Match a dir_fd-relative path by the identity of the directory it acts in.

        Compares ``(st_dev, st_ino)`` of the directory the operation actually targets
        against the parent directory of every watched file sharing the basename. It
        never consults the process cwd, so a tmp-tree ``conftest.py`` unlinked during
        pytest's tmpdir GC cannot borrow the repo root's identity — while a genuine
        ``dir_fd``-relative delete of the repo's own ``conftest.py`` still matches.
        """
        # bite-axis: directory identity — a basename match counts only when the
        # anchored directory IS the watched file's parent, not merely same-named.
        head, tail = os.path.split(path)
        try:
            anchor = os.stat(head or os.curdir, dir_fd=dir_fd)
        except (OSError, ValueError, TypeError, NotImplementedError):
            return False
        anchor_key = (anchor.st_dev, anchor.st_ino)
        for watched in self.watched:
            if os.path.basename(watched) != tail:
                continue
            try:
                parent = os.stat(os.path.dirname(watched))
            except OSError:
                continue
            if (parent.st_dev, parent.st_ino) == anchor_key:
                return True
        return False

    def _path_hits_watched(self, path, dir_fd=None):
        # bite-axis: anchor selection — a relative path is resolved against the
        # operation's own dir_fd; cwd resolution applies only when the operation
        # is genuinely cwd-anchored (absolute path, or no real descriptor).
        if not isinstance(path, (str, bytes)):
            return False
        if isinstance(path, bytes):
            path = path.decode("utf-8", "replace")
        if _is_real_dir_fd(dir_fd) and not os.path.isabs(path):
            return self._relative_hits_watched(path, dir_fd)
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

        for target, dir_fd in _write_targets(event, args):
            if self._path_hits_watched(target, dir_fd):
                node = self.current_test_nodeid or "<unknown test>"
                raise ShippedSourceWrite(
                    "%s on shipped source %r blocked — see %s"
                    % (event, target, node)
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
