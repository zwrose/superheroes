# plugins/superheroes/lib/tests/test_cache_markers.py
"""Stale `.in_use` marker sweep — fail-closed edges E1–E11."""
import os
import time

import cache_markers as cm


def _in_use(root):
    return os.path.join(str(root), ".in_use")


def _mk_marker(root, name, mtime=None):
    d = _in_use(root)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, name)
    with open(path, "w") as fh:
        fh.write("")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def _old_mtime(now=None):
    now = now if now is not None else time.time()
    return now - 7200


# E1 — .in_use does not exist
def test_e1_no_in_use_dir_returns_zero(tmp_path):
    assert cm.sweep_stale(str(tmp_path)) == 0


# E2 — .in_use is a file
def test_e2_in_use_is_file_returns_zero(tmp_path):
    path = _in_use(tmp_path)
    with open(path, "w") as fh:
        fh.write("not a dir")
    assert cm.sweep_stale(str(tmp_path)) == 0


# E3 — .in_use is a symlink (dead marker in target must survive)
def test_e3_in_use_symlink_skips_sweep_dead_marker_survives(tmp_path, monkeypatch):
    real = tmp_path / "real_in_use"
    real.mkdir()
    marker = real / "99999"
    marker.write_text("")
    old = _old_mtime()
    os.utime(marker, (old, old))

    symlink = _in_use(tmp_path)
    os.symlink(str(real), symlink)

    def kill(pid, sig):
        raise ProcessLookupError()

    monkeypatch.setattr(os, "kill", kill)

    assert cm.sweep_stale(str(tmp_path)) == 0
    assert marker.is_file()


# E4 — non-numeric filename
def test_e4_non_numeric_filename_survives(tmp_path, monkeypatch):
    path = _mk_marker(tmp_path, ".hidden", mtime=_old_mtime())

    def kill(pid, sig):
        raise ProcessLookupError()

    monkeypatch.setattr(os, "kill", kill)

    assert cm.sweep_stale(str(tmp_path)) == 0
    assert os.path.isfile(path)


def test_e4_leading_plus_filename_survives(tmp_path, monkeypatch):
    path = _mk_marker(tmp_path, "+123", mtime=_old_mtime())

    def kill(pid, sig):
        raise ProcessLookupError()

    monkeypatch.setattr(os, "kill", kill)

    assert cm.sweep_stale(str(tmp_path)) == 0
    assert os.path.isfile(path)


def test_e4_pid_zero_skipped(tmp_path, monkeypatch):
    path = _mk_marker(tmp_path, "0", mtime=_old_mtime())

    def kill(pid, sig):
        raise ProcessLookupError()

    monkeypatch.setattr(os, "kill", kill)

    assert cm.sweep_stale(str(tmp_path)) == 0
    assert os.path.isfile(path)


# E5 — marker is a directory
def test_e5_marker_subdirectory_skipped(tmp_path, monkeypatch):
    d = _in_use(tmp_path)
    os.makedirs(os.path.join(d, "12345"), exist_ok=True)

    def kill(pid, sig):
        raise ProcessLookupError()

    monkeypatch.setattr(os, "kill", kill)

    assert cm.sweep_stale(str(tmp_path)) == 0
    assert os.path.isdir(os.path.join(d, "12345"))


# E6 — PermissionError from os.kill
def test_e6_permission_error_keeps_marker(tmp_path, monkeypatch):
    path = _mk_marker(tmp_path, str(os.getpid()), mtime=_old_mtime())

    def kill(pid, sig):
        raise PermissionError()

    monkeypatch.setattr(os, "kill", kill)

    assert cm.sweep_stale(str(tmp_path)) == 0
    assert os.path.isfile(path)


# E7 — grace period
def test_e7_fresh_mtime_dead_pid_survives(tmp_path, monkeypatch):
    path = _mk_marker(tmp_path, "424242", mtime=time.time())

    def kill(pid, sig):
        raise ProcessLookupError()

    monkeypatch.setattr(os, "kill", kill)

    assert cm.sweep_stale(str(tmp_path)) == 0
    assert os.path.isfile(path)


# E8 — inode change before unlink
def test_e8_inode_change_before_unlink_keeps_marker(tmp_path, monkeypatch):
    path = _mk_marker(tmp_path, "424243", mtime=_old_mtime())
    real_stat = os.stat
    stat_calls = {}

    def stat(name, *args, **kwargs):
        if kwargs.get("dir_fd") is None:
            return real_stat(name, *args, **kwargs)
        st = real_stat(name, *args, **kwargs)
        n = stat_calls.get(name, 0) + 1
        stat_calls[name] = n
        if n >= 2:
            class FakeStat:
                st_ino = st.st_ino + 1
                st_dev = st.st_dev
                st_mode = st.st_mode
                st_mtime = st.st_mtime

            return FakeStat()
        return st

    def kill(pid, sig):
        raise ProcessLookupError()

    monkeypatch.setattr(os, "stat", stat)
    monkeypatch.setattr(os, "kill", kill)

    assert cm.sweep_stale(str(tmp_path)) == 0
    assert os.path.isfile(path)


# E9 — unlink raises
def test_e9_unlink_error_continues_sweep(tmp_path, monkeypatch):
    _mk_marker(tmp_path, "424244", mtime=_old_mtime())
    _mk_marker(tmp_path, "424245", mtime=_old_mtime())
    path_keep = os.path.join(_in_use(tmp_path), "424244")
    path_remove = os.path.join(_in_use(tmp_path), "424245")

    def kill(pid, sig):
        raise ProcessLookupError()

    real_unlink = os.unlink

    def unlink(name, *args, **kwargs):
        if name == "424244":
            raise OSError("simulated race")
        return real_unlink(name, *args, **kwargs)

    monkeypatch.setattr(os, "kill", kill)
    monkeypatch.setattr(os, "unlink", unlink)

    removed = cm.sweep_stale(str(tmp_path))
    assert removed == 1
    assert os.path.isfile(path_keep)
    assert not os.path.isfile(path_remove)


# E10 — platform lacks dir_fd (simulated)
def test_e10_no_dir_fd_support_returns_zero(tmp_path, monkeypatch):
    path = _mk_marker(tmp_path, "424246", mtime=_old_mtime())

    monkeypatch.setattr(os, "supports_dir_fd", set())

    assert cm.sweep_stale(str(tmp_path)) == 0
    assert os.path.isfile(path)


# E11 — unexpected exception swallowed
def test_e11_unexpected_exception_returns_zero(tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(os.path, "exists", boom)
    assert cm.sweep_stale(str(tmp_path)) == 0


# Required behaviors
def test_live_pid_old_mtime_survives(tmp_path):
    path = _mk_marker(tmp_path, str(os.getpid()), mtime=_old_mtime())
    assert cm.sweep_stale(str(tmp_path)) == 0
    assert os.path.isfile(path)


def test_dead_pid_old_mtime_removed(tmp_path, monkeypatch):
    path = _mk_marker(tmp_path, "888888", mtime=_old_mtime())

    def kill(pid, sig):
        raise ProcessLookupError()

    monkeypatch.setattr(os, "kill", kill)

    assert cm.sweep_stale(str(tmp_path)) == 1
    assert not os.path.isfile(path)


def test_nonexistent_plugin_root_returns_zero(tmp_path):
    missing = os.path.join(str(tmp_path), "no_such_plugin")
    assert cm.sweep_stale(missing) == 0
