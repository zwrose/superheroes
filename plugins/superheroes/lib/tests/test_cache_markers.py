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
    fixed_now = 2_000_000.0
    path = _mk_marker(tmp_path, "424242", mtime=fixed_now - 100)

    def kill(pid, sig):
        raise ProcessLookupError()

    monkeypatch.setattr(os, "kill", kill)

    assert cm.sweep_stale(str(tmp_path), now=fixed_now, grace_seconds=3600) == 0
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
    fixed_now = 3_000_000.0
    path = _mk_marker(tmp_path, "888888", mtime=fixed_now - 7200)

    def kill(pid, sig):
        raise ProcessLookupError()

    monkeypatch.setattr(os, "kill", kill)

    assert cm.sweep_stale(str(tmp_path), now=fixed_now) == 1
    assert not os.path.isfile(path)


def test_nonexistent_plugin_root_returns_zero(tmp_path):
    missing = os.path.join(str(tmp_path), "no_such_plugin")
    assert cm.sweep_stale(missing) == 0


def test_tmp_hash_marker_dead_pid_old_mtime_removed(tmp_path, monkeypatch):
    fixed_now = 4_000_000.0
    name = "20469.tmp.a2cb91d1"
    path = _mk_marker(tmp_path, name, mtime=fixed_now - 7200)

    def kill(pid, sig):
        raise ProcessLookupError()

    monkeypatch.setattr(os, "kill", kill)

    assert cm.sweep_stale(str(tmp_path), now=fixed_now) == 1
    assert not os.path.isfile(path)


def test_tmp_hash_marker_live_pid_survives(tmp_path):
    fixed_now = 4_000_001.0
    name = "%d.tmp.701e7d38" % os.getpid()
    path = _mk_marker(tmp_path, name, mtime=fixed_now - 7200)
    assert cm.sweep_stale(str(tmp_path), now=fixed_now) == 0
    assert os.path.isfile(path)


def test_tmp_hash_marker_fresh_mtime_survives(tmp_path, monkeypatch):
    fixed_now = 4_000_002.0
    name = "99999.tmp.deadbeef"
    path = _mk_marker(tmp_path, name, mtime=fixed_now - 10)

    def kill(pid, sig):
        raise ProcessLookupError()

    monkeypatch.setattr(os, "kill", kill)

    assert cm.sweep_stale(str(tmp_path), now=fixed_now, grace_seconds=3600) == 0
    assert os.path.isfile(path)


def test_tmp_hash_invalid_names_never_touched(tmp_path, monkeypatch):
    fixed_now = 4_000_003.0
    path_bad_lead = _mk_marker(tmp_path, "12ab.tmp.x", mtime=fixed_now - 7200)
    path_no_pid = _mk_marker(tmp_path, ".tmp.abc", mtime=fixed_now - 7200)

    def kill(pid, sig):
        raise ProcessLookupError()

    monkeypatch.setattr(os, "kill", kill)

    assert cm.sweep_stale(str(tmp_path), now=fixed_now) == 0
    assert os.path.isfile(path_bad_lead)
    assert os.path.isfile(path_no_pid)


def test_superheroes_no_cache_sweep_opt_out(tmp_path, monkeypatch):
    _mk_marker(tmp_path, "424299", mtime=_old_mtime())

    def kill(pid, sig):
        raise ProcessLookupError()

    monkeypatch.setattr(os, "kill", kill)
    monkeypatch.setenv("SUPERHEROES_NO_CACHE_SWEEP", "1")

    assert cm.sweep_stale(str(tmp_path)) == 0
    assert os.path.isfile(os.path.join(_in_use(tmp_path), "424299"))


def test_session_start_hook_invokes_sweep_stale(monkeypatch):
    import importlib.util
    import io
    import json
    import sys

    plugin = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    hook_path = os.path.join(plugin, "hooks", "session_start.py")
    spec = importlib.util.spec_from_file_location("session_start_hook", hook_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    calls = []

    def spy_sweep(plugin_root, now=None, grace_seconds=3600):
        calls.append((plugin_root, now, grace_seconds))
        return 0

    import cache_markers

    monkeypatch.setattr(cache_markers, "sweep_stale", spy_sweep)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(json.dumps({"source": "startup", "cwd": "/tmp"})),
    )

    assert mod.main() == 0
    assert len(calls) == 1
    assert calls[0][0] == mod._PLUGIN_ROOT


def test_session_start_stderr_when_sweep_removes_markers(monkeypatch, capsys):
    import importlib.util
    import io
    import json
    import sys

    plugin = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    hook_path = os.path.join(plugin, "hooks", "session_start.py")
    spec = importlib.util.spec_from_file_location("session_start_hook_breadcrumb", hook_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    import cache_markers

    monkeypatch.setattr(cache_markers, "sweep_stale", lambda *_a, **_k: 2)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(json.dumps({"source": "resume", "cwd": "/tmp"})),
    )

    assert mod.main() == 0
    assert capsys.readouterr().err == "superheroes: swept 2 stale .in_use marker(s)\n"


# ---------------------------------------------------------------- scan_stale_siblings (rider 3)
def _sibling_install(tmp_path, running="0.21.2", extra_versions=()):
    parent = tmp_path / "plugin-cache"
    parent.mkdir()
    run_dir = parent / running
    run_dir.mkdir()
    for ver in extra_versions:
        (parent / ver).mkdir()
    return str(run_dir), parent


def _dead_kill(monkeypatch):
    def kill(pid, sig):
        raise ProcessLookupError()

    monkeypatch.setattr(os, "kill", kill)


def test_scan_stale_siblings_reports_dead_pid_in_older_dir(tmp_path, monkeypatch):
    fixed_now = 5_000_000.0
    plugin_root, _parent = _sibling_install(tmp_path, extra_versions=("0.10.0", "0.21.1"))
    _mk_marker(_parent / "0.10.0", "888001", mtime=fixed_now - 7200)
    _mk_marker(_parent / "0.21.1", "888002", mtime=fixed_now - 7200)
    _dead_kill(monkeypatch)

    result = cm.scan_stale_siblings(plugin_root, now=fixed_now)
    assert result == {"dirs": ["0.10.0", "0.21.1"], "markers": 2}


def test_scan_stale_siblings_skips_live_pid_in_older_dir(tmp_path):
    fixed_now = 5_000_001.0
    plugin_root, parent = _sibling_install(tmp_path, extra_versions=("0.10.0",))
    _mk_marker(parent / "0.10.0", str(os.getpid()), mtime=fixed_now - 7200)

    result = cm.scan_stale_siblings(plugin_root, now=fixed_now)
    assert result == {"dirs": [], "markers": 0}


def test_scan_stale_siblings_skips_fresh_mtime_dead_pid(tmp_path, monkeypatch):
    fixed_now = 5_000_002.0
    plugin_root, parent = _sibling_install(tmp_path, extra_versions=("0.21.1",))
    _mk_marker(parent / "0.21.1", "888003", mtime=fixed_now - 100)
    _dead_kill(monkeypatch)

    result = cm.scan_stale_siblings(plugin_root, now=fixed_now, grace_seconds=3600)
    assert result == {"dirs": [], "markers": 0}


def test_scan_stale_siblings_skips_malformed_and_zero_pid(tmp_path, monkeypatch):
    fixed_now = 5_000_003.0
    plugin_root, parent = _sibling_install(tmp_path, extra_versions=("0.10.0",))
    _mk_marker(parent / "0.10.0", "+123", mtime=fixed_now - 7200)
    _mk_marker(parent / "0.10.0", "0", mtime=fixed_now - 7200)
    _dead_kill(monkeypatch)

    result = cm.scan_stale_siblings(plugin_root, now=fixed_now)
    assert result == {"dirs": [], "markers": 0}


def test_scan_stale_siblings_excludes_running_version_dir(tmp_path, monkeypatch):
    fixed_now = 5_000_004.0
    plugin_root, parent = _sibling_install(tmp_path, extra_versions=("0.10.0",))
    _mk_marker(parent / "0.21.2", "888004", mtime=fixed_now - 7200)
    _dead_kill(monkeypatch)

    result = cm.scan_stale_siblings(plugin_root, now=fixed_now)
    assert result == {"dirs": [], "markers": 0}


def test_scan_stale_siblings_opt_out_no_filesystem(tmp_path, monkeypatch):
    fixed_now = 5_000_005.0
    plugin_root, parent = _sibling_install(tmp_path, extra_versions=("0.10.0",))
    _mk_marker(parent / "0.10.0", "888005", mtime=fixed_now - 7200)
    _dead_kill(monkeypatch)
    monkeypatch.setenv("SUPERHEROES_NO_CACHE_SWEEP", "1")

    listdir_calls = []

    real_listdir = os.listdir

    def tracking_listdir(path):
        listdir_calls.append(path)
        return real_listdir(path)

    monkeypatch.setattr(os, "listdir", tracking_listdir)

    assert cm.scan_stale_siblings(plugin_root, now=fixed_now) == {"dirs": [], "markers": 0}
    assert listdir_calls == []


def test_scan_stale_siblings_read_only_preserves_all_markers(tmp_path, monkeypatch):
    fixed_now = 5_000_006.0
    plugin_root, parent = _sibling_install(tmp_path, extra_versions=("0.10.0", "0.21.1"))
    paths = [
        _mk_marker(parent / "0.10.0", "888006", mtime=fixed_now - 7200),
        _mk_marker(parent / "0.21.1", "888007", mtime=fixed_now - 7200),
    ]
    _dead_kill(monkeypatch)

    result = cm.scan_stale_siblings(plugin_root, now=fixed_now)
    assert result["markers"] == 2

    for p in paths:
        assert os.path.isfile(p)
    assert (parent / "0.10.0").is_dir()
    assert (parent / "0.21.1").is_dir()
    assert _in_use(parent / "0.10.0") and os.path.isdir(_in_use(parent / "0.10.0"))


def test_scan_stale_siblings_clean_layout(tmp_path, monkeypatch):
    plugin_root, parent = _sibling_install(tmp_path, extra_versions=("0.10.0",))
    _dead_kill(monkeypatch)
    assert cm.scan_stale_siblings(plugin_root) == {"dirs": [], "markers": 0}

