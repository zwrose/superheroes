"""Tests for source_guard pytest plugin and bite_support helper."""
import os
import stat
import subprocess
import sys
import types

import pytest

import source_guard as sg
from bite_support import patched_module

_REPO_ROOT = os.path.realpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
)


@pytest.fixture
def isolated_watched():
    saved = set(sg._WATCHED_PATHS)
    sg._WATCHED_PATHS.clear()
    yield sg._WATCHED_PATHS
    sg._WATCHED_PATHS.clear()
    sg._WATCHED_PATHS.update(saved)


# --- Group 1: unit behaviour -------------------------------------------------


def test_watched_paths_excludes_tests_and_nonempty():
    paths = sg.watched_paths(_REPO_ROOT)
    assert paths
    assert all("/tests/" not in p for p in paths)
    assert all(not p.endswith("/tests") for p in paths)


def test_watched_paths_empty_git_raises(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    with pytest.raises(RuntimeError, match="no tracked"):
        sg.watched_paths(str(tmp_path))


def test_watched_paths_failed_git_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(
        sg.subprocess,
        "run",
        lambda *a, **k: types.SimpleNamespace(returncode=1, stdout=b"", stderr=b"fail"),
    )
    with pytest.raises(RuntimeError, match="git ls-files failed"):
        sg.watched_paths(str(tmp_path))


def test_audit_hook_allows_read_of_watched(tmp_path, isolated_watched):
    path = tmp_path / "watched.py"
    path.write_text("x\n")
    real = os.path.realpath(str(path))
    isolated_watched.add(real)
    sg.audit_hook("open", (real, "r", 0))


def test_audit_hook_blocks_open_write_watched(tmp_path, isolated_watched):
    path = tmp_path / "watched.py"
    path.write_text("x\n")
    real = os.path.realpath(str(path))
    isolated_watched.add(real)
    with pytest.raises(sg.ShippedSourceWrite):
        sg.audit_hook("open", (real, "w", 0))


def test_audit_hook_blocks_os_open_write_watched(tmp_path, isolated_watched):
    path = tmp_path / "watched.py"
    path.write_text("x\n")
    real = os.path.realpath(str(path))
    isolated_watched.add(real)
    with pytest.raises(sg.ShippedSourceWrite):
        sg.audit_hook(
            "open",
            (real, None, os.O_WRONLY | os.O_CREAT),
        )


def test_audit_hook_blocks_rename_replace_remove_truncate(tmp_path, isolated_watched):
    path = tmp_path / "watched.py"
    path.write_text("x\n")
    real = os.path.realpath(str(path))
    other = os.path.realpath(str(tmp_path / "other.py"))
    isolated_watched.add(real)
    for event, args in (
        ("os.rename", (other, real)),
        ("os.replace", (other, real)),
        ("os.remove", (real,)),
        ("os.truncate", (real, 0)),
    ):
        with pytest.raises(sg.ShippedSourceWrite):
            sg.audit_hook(event, args)


def test_audit_hook_allows_write_unwatched(tmp_path, isolated_watched):
    path = tmp_path / "free.py"
    path.write_text("x\n")
    real = os.path.realpath(str(path))
    sg.audit_hook("open", (real, "w", 0))


def test_lstat_signature_differs_on_chmod(tmp_path):
    path = tmp_path / "f.py"
    path.write_text("same\n")
    base = sg._lstat_signature(str(path))
    os.chmod(path, base[0] ^ stat.S_IWUSR)
    try:
        assert sg._lstat_signature(str(path)) != base
    finally:
        os.chmod(path, base[0])


def test_lstat_signature_differs_on_exec_bit(tmp_path):
    path = tmp_path / "f.py"
    path.write_text("#!/usr/bin/env python3\n")
    base = sg._lstat_signature(str(path))
    os.chmod(path, base[0] | stat.S_IXUSR)
    try:
        assert sg._lstat_signature(str(path)) != base
    finally:
        os.chmod(path, base[0])


def test_lstat_signature_differs_on_symlink_replacement(tmp_path):
    path = tmp_path / "f.py"
    path.write_text("payload\n")
    base = sg._lstat_signature(str(path))
    target = tmp_path / "target.py"
    target.write_text("payload\n")
    os.remove(path)
    os.symlink(str(target), str(path))
    assert sg._lstat_signature(str(path)) != base


def test_patched_module_absent_old_raises():
    import handback_gate as hg

    with pytest.raises(AssertionError, match="not found"):
        patched_module(hg, ("THIS STRING DOES NOT EXIST", "x"))


def test_patched_module_duplicate_old_raises(tmp_path):
    mod_path = tmp_path / "dummy.py"
    mod_path.write_text("MARKER\nMARKER\n")
    mod = types.ModuleType("dummy")
    mod.__file__ = str(mod_path)
    with pytest.raises(AssertionError, match="occurs"):
        patched_module(mod, ("MARKER\n", "Y\n"))


def test_patched_module_two_edits_in_order():
    import handback_gate as hg

    old1 = '    if _LEGACY_BASE_SHA.match(sidecar.get("baseRef") or ""):'
    old2 = "        if cmd_base != sidecar_base:"
    with open(hg.__file__, encoding="utf-8") as fh:
        disk_before = fh.read()
    mod = patched_module(
        hg,
        [
            (old1, "    if False and _LEGACY_BASE_SHA.match(sidecar.get(\"baseRef\") or \"\"):"),
            (old2, "        if False and cmd_base != sidecar_base:"),
        ],
    )
    with open(hg.__file__, encoding="utf-8") as fh:
        disk_after = fh.read()
    assert disk_after == disk_before
    assert mod is not hg
    assert hasattr(mod, "validate_handback")


def test_patched_module_leaves_original_and_sys_modules(tmp_path):
    import handback_gate as hg

    before_id = id(hg)
    before_name = hg.__name__
    assert "handback_gate__patched" not in sys.modules
    mod = patched_module(
        hg,
        ('if not os.path.isfile(sidecar_path):', 'if False and not os.path.isfile(sidecar_path):'),
    )
    assert id(hg) == before_id
    assert hg.__name__ == before_name
    assert "handback_gate__patched" not in sys.modules
    assert mod is not hg


# --- Group 2: bite-proofs (in-memory via patched_module) -----------------------


def _bite_red_green(label, neutralize_edits, red_fn, green_fn):
    """Run red (neutralized) then green (real) for one guarded element."""
    mod = patched_module(sg, neutralize_edits, name="source_guard__patched_%s" % label)
    assert red_fn(mod) is False, "%s: neutralized copy must not fire (red half)" % label
    assert green_fn(sg) is True, "%s: real module must fire (green half)" % label


def test_bite_audit_hook_write_mode_detection(tmp_path, isolated_watched):
    path = tmp_path / "w.py"
    path.write_text("z\n")
    real = os.path.realpath(str(path))
    isolated_watched.add(real)

    def fires(mod):
        mod._WATCHED_PATHS.add(real)
        try:
            mod.audit_hook("open", (real, "w", 0))
            return False
        except mod.ShippedSourceWrite:
            return True

    _bite_red_green(
        "write_mode",
        (
            '        return any(ch in mode for ch in "wax+")',
            "        return False",
        ),
        lambda m: fires(m),
        lambda m: fires(m),
    )


def test_bite_audit_hook_rename_branch(tmp_path, isolated_watched):
    path = tmp_path / "w.py"
    path.write_text("z\n")
    real = os.path.realpath(str(path))
    other = os.path.realpath(str(tmp_path / "o.py"))
    isolated_watched.add(real)

    def fires(mod):
        mod._WATCHED_PATHS.add(real)
        try:
            mod.audit_hook("os.rename", (other, real))
            return False
        except mod.ShippedSourceWrite:
            return True

    _bite_red_green(
        "rename_branch",
        (
            '    if event in ("os.rename", "os.replace", "os.remove", "os.truncate"):',
            '    if False and event in ("os.rename", "os.replace", "os.remove", "os.truncate"):',
        ),
        lambda m: fires(m),
        lambda m: fires(m),
    )


def test_bite_watched_set_membership(tmp_path, isolated_watched):
    path = tmp_path / "w.py"
    path.write_text("z\n")
    real = os.path.realpath(str(path))
    isolated_watched.add(real)

    def fires(mod):
        mod._WATCHED_PATHS.add(real)
        try:
            mod.audit_hook("open", (real, "w", 0))
            return False
        except mod.ShippedSourceWrite:
            return True

    _bite_red_green(
        "watched_membership",
        (
            "    return real in _WATCHED_PATHS",
            "    return False",
        ),
        lambda m: fires(m),
        lambda m: fires(m),
    )


def test_bite_watched_paths_tests_exclusion(tmp_path):
    tests_py = tmp_path / "pkg" / "tests" / "t.py"
    tests_py.parent.mkdir(parents=True)
    tests_py.write_text("x = 1\n")
    lib_py = tmp_path / "pkg" / "lib.py"
    lib_py.write_text("y = 2\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e.com", "-c", "user.name=T", "commit", "-q", "-m", "init"],
        cwd=tmp_path,
        check=True,
    )

    def excludes_tests(mod):
        paths = mod.watched_paths(str(tmp_path))
        return str(tests_py.resolve()) not in paths

    _bite_red_green(
        "tests_exclusion",
        (
            '        if "/tests/" in rel_str or rel_str.startswith("tests/"):\n'
            "            continue",
            "        if False:\n"
            "            continue",
        ),
        lambda m: excludes_tests(m),
        lambda m: excludes_tests(m),
    )


def test_bite_empty_manifest_raises(tmp_path):
    tests_py = tmp_path / "pkg" / "tests" / "t.py"
    tests_py.parent.mkdir(parents=True)
    tests_py.write_text("x = 1\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e.com", "-c", "user.name=T", "commit", "-q", "-m", "init"],
        cwd=tmp_path,
        check=True,
    )

    def raises_empty(mod):
        try:
            mod.watched_paths(str(tmp_path))
            return False
        except RuntimeError:
            return True

    _bite_red_green(
        "empty_manifest",
        (
            "    if not paths:\n"
            '        raise RuntimeError("source_guard: watched set is empty after excluding tests/")',
            "    if not paths:\n"
            "        pass",
        ),
        lambda m: raises_empty(m),
        lambda m: raises_empty(m),
    )


def test_bite_patched_module_count_zero():
    import handback_gate as hg
    import bite_support as bs

    def raises_absent(mod):
        try:
            mod.patched_module(hg, ("ABSENT_TARGET_XYZ", "y"))
            return False
        except AssertionError:
            return True

    mod = patched_module(
        bs,
        [
            (
                "        if count == 0:\n"
                '            raise AssertionError("neutralization target not found: %r" % (old,))',
                "        if False and count == 0:\n"
                '            raise AssertionError("neutralization target not found: %r" % (old,))',
            ),
            (
                "        if count != 1:",
                "        if count > 1:",
            ),
        ],
        name="bite_support__patched_zero",
    )
    assert raises_absent(mod) is False
    assert raises_absent(bs) is True


def test_bite_patched_module_count_two(tmp_path):
    import bite_support as bs

    mod_path = tmp_path / "dummy.py"
    mod_path.write_text("# DUPLINE\n# DUPLINE\n")
    mod = types.ModuleType("dummy")
    mod.__file__ = str(mod_path)

    def raises_dup(bs_mod):
        try:
            bs_mod.patched_module(mod, ("# DUPLINE\n", "# ONCE\n"))
            return False
        except AssertionError as exc:
            return "occurs" in str(exc)

    patched = patched_module(
        bs,
        (
            "        if count != 1:",
            "        if False and count != 1:",
        ),
        name="bite_support__patched_two",
    )
    assert raises_dup(patched) is False
    assert raises_dup(bs) is True


# --- Group 3: wiring proof (subprocess, real plugin) -------------------------


def _build_micro_suite(root, load_via_pytest_plugins=True):
    shipped = root / "lib" / "shipped.py"
    shipped.parent.mkdir(parents=True)
    shipped.write_text("VALUE = 1\n")
    (root / "pytest.ini").write_text("[pytest]\n")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e.com", "-c", "user.name=T", "commit", "-q", "-m", "init"],
        cwd=root,
        check=True,
    )
    conftest_lines = []
    if load_via_pytest_plugins:
        conftest_lines.append("pytest_plugins = ('source_guard',)\n")
    conftest_lines.extend(
        [
            "import pytest\n\n",
            "@pytest.fixture\n",
            "def shipped_path():\n",
            "    import pathlib\n",
            "    return pathlib.Path(__file__).resolve().parent / 'lib' / 'shipped.py'\n",
        ]
    )
    (root / "conftest.py").write_text("".join(conftest_lines))
    (root / "test_violator.py").write_text(
        "def test_rewrite_shipped(shipped_path):\n"
        "    path = str(shipped_path)\n"
        "    with open(path, encoding='utf-8') as fh:\n"
        "        orig = fh.read()\n"
        "    try:\n"
        "        with open(path, 'w', encoding='utf-8') as fh:\n"
        "            fh.write(orig.replace('1', '2'))\n"
        "    finally:\n"
        "        with open(path, 'w', encoding='utf-8') as fh:\n"
        "            fh.write(orig)\n"
    )
    subprocess.run(["git", "add", "conftest.py", "test_violator.py"], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e.com", "-c", "user.name=T", "commit", "-q", "-m", "tests"],
        cwd=root,
        check=True,
    )


def _run_micro_pytest(root, xdist_workers=None, explicit_plugin=True, cwd=None, test_file=None):
    env = os.environ.copy()
    env["PYTHONPATH"] = _REPO_ROOT
    env[sg.REPO_ROOT_ENV] = str(root)
    target = test_file or (root / "test_violator.py")
    run_cwd = cwd or root
    if cwd is None and explicit_plugin:
        run_cwd = _REPO_ROOT
    rel_target = str(target)
    if os.path.commonpath([os.path.realpath(run_cwd), os.path.realpath(target)]) == os.path.realpath(run_cwd):
        rel_target = os.path.relpath(target, run_cwd)
    cmd = [
        sys.executable,
        "-B",
        "-m",
        "pytest",
        rel_target,
        "-q",
    ]
    if explicit_plugin:
        cmd.extend(["-p", "source_guard"])
    if xdist_workers is not None:
        cmd.extend(["-n", str(xdist_workers)])
    return subprocess.run(
        cmd,
        cwd=run_cwd,
        env=env,
        capture_output=True,
        text=True,
    )


def _assert_wiring_failure(proc, root):
    combined = proc.stdout + proc.stderr
    assert proc.returncode != 0, "micro-suite must fail on shipped rewrite:\n%s" % combined
    assert "ShippedSourceWrite" in combined
    assert "test_rewrite_shipped" in combined
    assert "source_guard" in combined
    diff = subprocess.run(
        ["git", "diff", "--", "lib/shipped.py"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert diff.stdout == "", "fake shipped file must be byte-clean after run"
    with open(root / "lib" / "shipped.py", encoding="utf-8") as fh:
        assert fh.read() == "VALUE = 1\n"


def test_wiring_proof_serial_subprocess(tmp_path):
    root = tmp_path / "micro_serial"
    root.mkdir()
    _build_micro_suite(root)
    proc = _run_micro_pytest(root)
    _assert_wiring_failure(proc, root)


def test_guard_loads_without_explicit_plugin_flag(tmp_path):
    root = tmp_path / "micro_implicit"
    root.mkdir()
    _build_micro_suite(root, load_via_pytest_plugins=True)
    proc = _run_micro_pytest(root, explicit_plugin=False)
    _assert_wiring_failure(proc, root)


def _build_nested_fake_repo(root):
    (root / "pytest.ini").write_text("[pytest]\n")
    (root / "conftest.py").write_text("pytest_plugins = ('source_guard',)\n")
    test_dir = root / "plugins" / "superheroes" / "lib" / "tests"
    test_dir.mkdir(parents=True)
    shipped = root / "lib" / "shipped.py"
    shipped.parent.mkdir()
    shipped.write_text("VALUE = 1\n")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e.com", "-c", "user.name=T", "commit", "-q", "-m", "init"],
        cwd=root,
        check=True,
    )
    (test_dir / "conftest.py").write_text(
        "import pytest\n\n"
        "@pytest.fixture\n"
        "def shipped_path():\n"
        "    import pathlib\n"
        "    return pathlib.Path(__file__).resolve().parent.parent.parent.parent.parent / 'lib' / 'shipped.py'\n"
    )
    (test_dir / "test_violator.py").write_text(
        "def test_rewrite_shipped(shipped_path):\n"
        "    path = str(shipped_path)\n"
        "    with open(path, encoding='utf-8') as fh:\n"
        "        orig = fh.read()\n"
        "    try:\n"
        "        with open(path, 'w', encoding='utf-8') as fh:\n"
        "            fh.write(orig.replace('1', '2'))\n"
        "    finally:\n"
        "        with open(path, 'w', encoding='utf-8') as fh:\n"
        "            fh.write(orig)\n"
    )
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e.com", "-c", "user.name=T", "commit", "-q", "-m", "tests"],
        cwd=root,
        check=True,
    )
    return test_dir


def test_guard_loads_from_nested_test_directory(tmp_path):
    root = tmp_path / "nested_fake"
    root.mkdir()
    test_dir = _build_nested_fake_repo(root)
    env = os.environ.copy()
    env["PYTHONPATH"] = _REPO_ROOT
    env[sg.REPO_ROOT_ENV] = str(root)
    proc = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "test_violator.py", "-q"],
        cwd=test_dir,
        env=env,
        capture_output=True,
        text=True,
    )
    _assert_wiring_failure(proc, root)


def test_resolve_repo_root_from_subdirectory(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    sub = repo / "nested"
    sub.mkdir(parents=True)
    lib = repo / "lib"
    lib.mkdir()
    (lib / "mod.py").write_text("x = 1\n")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e.com", "-c", "user.name=T", "commit", "-q", "-m", "init"],
        cwd=repo,
        check=True,
    )
    monkeypatch.delenv(sg.REPO_ROOT_ENV, raising=False)
    config = types.SimpleNamespace(rootpath=str(sub))
    resolved = sg._resolve_repo_root(config)
    assert resolved == os.path.realpath(str(repo))


def _build_layer2_micro_suite(root):
    _build_micro_suite(root)
    (root / "test_unrestored.py").write_text(
        "import subprocess, sys\n\n"
        "def test_child_mutates_unrestored(shipped_path):\n"
        "    path = str(shipped_path)\n"
        "    subprocess.run(\n"
        "        [sys.executable, '-c', 'open(%r, \"w\").write(\"CORRUPTED\")' % path],\n"
        "        check=True,\n"
        "    )\n"
    )
    subprocess.run(["git", "add", "test_unrestored.py"], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e.com", "-c", "user.name=T", "commit", "-q", "-m", "layer2"],
        cwd=root,
        check=True,
    )


def test_layer2_subprocess_unrestored(tmp_path):
    root = tmp_path / "micro_layer2"
    root.mkdir()
    _build_layer2_micro_suite(root)
    proc = _run_micro_pytest(root, test_file=root / "test_unrestored.py")
    combined = proc.stdout + proc.stderr
    assert proc.returncode != 0, combined
    assert "source_guard: shipped source mutated by" in combined
    assert "test_child_mutates_unrestored" in combined
    assert "shipped.py" in combined
    (root / "lib" / "shipped.py").write_text("VALUE = 1\n")


def _build_layer3_micro_suite(root):
    _build_micro_suite(root)
    (root / "test_chmod.py").write_text(
        "import subprocess, sys\n\n"
        "def test_child_chmods_shipped(shipped_path):\n"
        "    path = str(shipped_path)\n"
        "    subprocess.run(\n"
        "        [sys.executable, '-c',\n"
        "         'import os, stat; p=%r; m=os.stat(p).st_mode; "
        "os.chmod(p, m | stat.S_IXUSR)' % path],\n"
        "        check=True,\n"
        "    )\n"
    )
    subprocess.run(["git", "add", "test_chmod.py"], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e.com", "-c", "user.name=T", "commit", "-q", "-m", "layer3"],
        cwd=root,
        check=True,
    )


def test_layer3_session_end_reports_dirty(tmp_path):
    root = tmp_path / "micro_layer3"
    root.mkdir()
    _build_layer3_micro_suite(root)
    proc = _run_micro_pytest(root, test_file=root / "test_chmod.py")
    combined = proc.stdout + proc.stderr
    assert proc.returncode != 0, combined
    assert "source_guard: session left shipped source dirty:" in combined
    assert "shipped.py" in combined
    st = os.stat(root / "lib" / "shipped.py")
    os.chmod(root / "lib" / "shipped.py", st.st_mode & ~stat.S_IXUSR)


def test_wiring_proof_xdist_subprocess(tmp_path):
    pytest.importorskip("xdist")
    root = tmp_path / "micro_xdist"
    root.mkdir()
    _build_micro_suite(root)
    proc = _run_micro_pytest(root, xdist_workers=2)
    if "unrecognized arguments: -n" in proc.stderr:
        pytest.skip("pytest-xdist unavailable in subprocess environment")
    _assert_wiring_failure(proc, root)


def test_plugin_loads_with_xdist_disabled():
    target = os.path.join(
        _REPO_ROOT,
        "plugins",
        "superheroes",
        "lib",
        "tests",
        "test_pilot_malformed_input.py",
    )
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            target,
            "--collect-only",
            "-q",
            "-p",
            "no:xdist",
            "-p",
            "no:randomly",
            "-p",
            "no:cacheprovider",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONHASHSEED": "0"},
    )
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 0, combined
    assert "INTERNALERROR" not in combined
    assert "PluginValidationError" not in combined


def test_pytest_configure_installs_audit_hook_once(monkeypatch):
    saved = sg._AUDIT_HOOK_INSTALLED
    sg._AUDIT_HOOK_INSTALLED = False
    calls = []

    def counting_addaudithook(hook):
        calls.append(hook)

    monkeypatch.setattr(sg.sys, "addaudithook", counting_addaudithook)
    baseline = {"signatures": {}, "hashes": {}}
    config = types.SimpleNamespace(
        rootpath=_REPO_ROOT,
        workerinput={
            "source_guard_baseline": baseline,
            "source_guard_watched": [],
        },
        _source_guard_baseline=None,
    )
    try:
        sg.pytest_configure(config)
        assert sg._AUDIT_HOOK_INSTALLED is True
        assert len(calls) == 1
        sg.pytest_configure(config)
        assert len(calls) == 1
    finally:
        sg._AUDIT_HOOK_INSTALLED = saved
