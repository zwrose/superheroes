"""Tests for cloud_plugin_pin (#2035): the plugin pin hook module.

Every fixture project is a real git repository under tmp_path, and the generated script is run with
bash against it. The plugin's source is a local git repository reached through the pin's https URL
by a `url.<base>.insteadOf` rewrite carried in the script's environment, so no test touches the
network, the real home directory or the real /opt/superheroes. Fixture git configuration is pinned
(GIT_CONFIG_GLOBAL, GIT_CONFIG_NOSYSTEM) so nothing on the machine leaks in.
"""
import json
import os
import shutil
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_dependency_hook as dep  # noqa: E402
import cloud_pass  # noqa: E402
import cloud_plugin_pin as pin_mod  # noqa: E402
import cloud_setup_text  # noqa: E402

URL = "https://example.invalid/plug.git"
SUBDIR = "plugins/superheroes"
PIN = {"source": URL, "commit": "a" * 40, "subdir": SUBDIR, "version": "1.2.3"}
CANON = pin_mod.pin_text(PIN)
SCRIPT_PATH = ".claude/hooks/superheroes-plugin-pin.sh"
PIN_PATH = ".claude/superheroes-plugin-pin"
SETTINGS_PATH = ".claude/settings.json"
OLD_SCRIPT = os.path.join(_HERE, "fixtures", "plugin_pin_hook_before_2178.sh")


def _env(remote=None):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": os.devnull,
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    if remote is not None:
        env["CLAUDE_CODE_REMOTE"] = remote
    return env


def _git(cwd, *args):
    done = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                          cwd=str(cwd), env=_env(), capture_output=True, text=True, check=True)
    return done.stdout.strip()


def _write(root, rel, data):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))


def _commit_all(root):
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "x")
    return _git(root, "rev-parse", "HEAD")


def _repo(path, files):
    path.mkdir(parents=True)
    _git(path, "init", "-q")
    for rel, data in {"README": b"x\n", **files}.items():
        _write(path, rel, data)
    _commit_all(path)
    return path


def _snapshot(root):
    out = {}
    for base, _dirs, names in os.walk(str(root)):
        for name in names:
            path = os.path.join(base, name)
            out[os.path.relpath(path, str(root))] = open(path, "rb").read()
    return out


def _good(tmp_path):
    """The three files `sync` writes for PIN: relative path -> bytes."""
    root = tmp_path / "good"
    root.mkdir()
    assert pin_mod.sync(str(root), PIN)["action"] == "written"
    return {rel: (root / rel).read_bytes() for rel in (SCRIPT_PATH, PIN_PATH, SETTINGS_PATH)}


def _bad(good, **changes):
    files = dict(good)
    for rel, data in changes.items():
        rel = {"script": SCRIPT_PATH, "pin": PIN_PATH, "settings": SETTINGS_PATH}[rel]
        if data is None:
            del files[rel]
        else:
            files[rel] = data
    return files


# ---- literals ----

def test_the_external_contract_literals_are_pinned():
    assert pin_mod.SCRIPT_REL == ".claude/hooks/superheroes-plugin-pin.sh"
    assert pin_mod.PIN_REL == ".claude/superheroes-plugin-pin"
    assert pin_mod.HOOK_COMMAND == 'bash "$CLAUDE_PROJECT_DIR/.claude/hooks/superheroes-plugin-pin.sh"'
    assert pin_mod.SETTINGS_REL == ".claude/settings.json"
    assert pin_mod.PIN_KEYS == ("source", "commit", "subdir", "version")


# ---- parse_pin / pin_text ----

def _text(**overrides):
    values = {**PIN, **overrides}
    return "# c\n" + "".join("%s=%s\n" % (k, values[k]) for k in pin_mod.PIN_KEYS if values[k] is not None)


def test_parse_pin_accepts_the_canonical_text_and_round_trips():
    assert pin_mod.parse_pin(CANON) == PIN
    assert pin_mod.pin_text(pin_mod.parse_pin(CANON)) == CANON
    assert CANON.startswith("# The superheroes plugin the cloud sessions of this project install.")
    assert pin_mod.parse_pin("\n# note\n" + CANON.split("\n", 1)[1] + "\n") == PIN


@pytest.mark.parametrize("key", pin_mod.PIN_KEYS)
def test_parse_pin_rejects_a_missing_key(key):
    assert pin_mod.parse_pin(_text(**{key: None})) is None


def test_parse_pin_rejects_a_duplicate_key():
    assert pin_mod.parse_pin(CANON + "version=1.2.4\n") is None


def test_parse_pin_rejects_an_unknown_key():
    assert pin_mod.parse_pin(CANON + "extra=1\n") is None


@pytest.mark.parametrize("field,value", [
    ("source", "http://example.invalid/p.git"), ("source", "https://exa mple.invalid/p.git"),
    ("commit", "abc123"), ("commit", "A" * 40),
    ("subdir", "/abs/path"), ("subdir", "../up"), ("subdir", "a/../b"),
    ("version", "1.2"), ("version", "1.2.3-rc1")])
def test_parse_pin_rejects_an_invalid_value(field, value):
    assert pin_mod.parse_pin(_text(**{field: value})) is None


def test_parse_pin_rejects_a_line_that_is_not_key_value():
    assert pin_mod.parse_pin(CANON + "stray\n") is None


def test_pin_text_raises_on_an_invalid_pin():
    with pytest.raises(ValueError):
        pin_mod.pin_text({**PIN, "commit": "short"})


def test_script_text_rejects_directories_that_are_not_plain_absolute_paths():
    with pytest.raises(ValueError):
        pin_mod.script_text(plugin_dir="relative/dir")
    with pytest.raises(ValueError):
        pin_mod.script_text(source_dir="/a b/c")


# ---- sync ----

def test_sync_writes_the_three_files_with_their_modes_and_is_then_a_noop(tmp_path):
    result = pin_mod.sync(str(tmp_path), PIN)
    assert result == {"action": "written", "reason": None,
                      "changed": sorted([PIN_PATH, SCRIPT_PATH, SETTINGS_PATH])}
    assert (tmp_path / SCRIPT_PATH).read_text() == pin_mod.script_text()
    assert (tmp_path / PIN_PATH).read_text() == pin_mod.pin_text(PIN)
    assert os.stat(str(tmp_path / SCRIPT_PATH)).st_mode & 0o777 == 0o755
    assert os.stat(str(tmp_path / PIN_PATH)).st_mode & 0o777 == 0o644
    assert os.stat(str(tmp_path / SETTINGS_PATH)).st_mode & 0o777 == 0o644
    settings = json.loads((tmp_path / SETTINGS_PATH).read_text())
    assert settings == {"hooks": {"SessionStart": [{"hooks": [
        {"type": "command", "command": pin_mod.HOOK_COMMAND, "timeout": 300}]}]}}
    assert pin_mod.sync(str(tmp_path), PIN) == {"action": "noop", "reason": None, "changed": []}


def test_sync_rewrites_a_changed_pin_and_a_damaged_settings_entry(tmp_path):
    pin_mod.sync(str(tmp_path), PIN)
    newer = {**PIN, "commit": "b" * 40, "version": "1.3.0"}
    assert pin_mod.sync(str(tmp_path), newer)["changed"] == [PIN_PATH]
    settings = json.loads((tmp_path / SETTINGS_PATH).read_text())
    settings["hooks"]["SessionStart"][0]["hooks"][0]["timeout"] = 5
    settings["hooks"]["SessionStart"].append({"matcher": "resume", "hooks": [
        {"type": "command", "command": pin_mod.HOOK_COMMAND}]})
    _write(tmp_path, SETTINGS_PATH, json.dumps(settings))
    assert pin_mod.sync(str(tmp_path), newer)["changed"] == [SETTINGS_PATH]
    again = json.loads((tmp_path / SETTINGS_PATH).read_text())
    assert [h for g in again["hooks"]["SessionStart"] for h in g["hooks"]] == [
        {"type": "command", "command": pin_mod.HOOK_COMMAND, "timeout": 300}]


def test_sync_repairs_a_registration_whose_only_damage_is_a_resume_matcher(tmp_path):
    pin_mod.sync(str(tmp_path), PIN)
    settings = json.loads((tmp_path / SETTINGS_PATH).read_text())
    groups = settings["hooks"]["SessionStart"]
    assert len(groups) == 1
    groups[0]["matcher"] = "resume"
    _write(tmp_path, SETTINGS_PATH, json.dumps(settings))
    assert pin_mod.sync(str(tmp_path), PIN) == {
        "action": "written", "reason": None, "changed": [SETTINGS_PATH]}
    assert pin_mod.in_tree(str(tmp_path)) == {"state": "valid", "reason": None, "pin": PIN}


def test_the_pin_hook_and_the_dependency_hook_share_the_settings_file(tmp_path):
    root = str(tmp_path)
    assert dep.sync(root, ["echo one"], ["uv.lock"], True)["action"] == "written"
    with_dep = (tmp_path / SETTINGS_PATH).read_bytes()
    dep_script = (tmp_path / dep.SCRIPT_REL).read_bytes()
    assert pin_mod.sync(root, PIN)["action"] == "written"
    commands = [h["command"] for g in json.loads((tmp_path / SETTINGS_PATH).read_text())
                ["hooks"]["SessionStart"] for h in g["hooks"]]
    assert commands == [dep.HOOK_COMMAND, pin_mod.HOOK_COMMAND]
    removed = pin_mod.sync(root, None)
    assert removed["action"] == "removed"
    assert removed["changed"] == sorted([PIN_PATH, SCRIPT_PATH, SETTINGS_PATH])
    assert (tmp_path / SETTINGS_PATH).read_bytes() == with_dep
    assert (tmp_path / dep.SCRIPT_REL).read_bytes() == dep_script
    assert dep.sync(root, ["echo one"], ["uv.lock"], True)["action"] == "noop"


def test_remove_deletes_the_settings_file_only_when_it_becomes_empty(tmp_path):
    pin_mod.sync(str(tmp_path), PIN)
    assert pin_mod.sync(str(tmp_path), None)["action"] == "removed"
    assert _snapshot(tmp_path) == {}
    assert pin_mod.sync(str(tmp_path), None) == {"action": "noop", "reason": None, "changed": []}
    _write(tmp_path, SETTINGS_PATH, json.dumps({"model": "m"}))
    pin_mod.sync(str(tmp_path), PIN)
    pin_mod.sync(str(tmp_path), None)
    assert json.loads((tmp_path / SETTINGS_PATH).read_text()) == {"model": "m"}


@pytest.mark.parametrize("pin,settings,reason", [
    ({"source": "x"}, None, "invalid-pin"),
    (PIN, "not json", "settings-unreadable"),
    (PIN, json.dumps({"disableAllHooks": True}), "settings-hooks-disabled"),
    (PIN, json.dumps({"env": {"X_API_KEY": "abc123def456"}}), "secret-shaped")])
def test_sync_refuses_and_leaves_every_file_byte_identical(tmp_path, pin, settings, reason):
    if settings is not None:
        _write(tmp_path, SETTINGS_PATH, settings)
    before = _snapshot(tmp_path)
    assert pin_mod.sync(str(tmp_path), pin) == {"action": "refused", "reason": reason, "changed": []}
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("generator", ["script_text", "pin_text"])
def test_sync_refuses_a_secret_shape_in_the_script_or_pin_text(tmp_path, monkeypatch, generator):
    real = getattr(pin_mod, generator)
    token = "npm_" + "a" * 36
    monkeypatch.setattr(pin_mod, generator, lambda *a, **kw: real(*a, **kw) + "# " + token + "\n")
    assert pin_mod.sync(str(tmp_path), PIN) == {
        "action": "refused", "reason": "secret-shaped", "changed": []}
    assert _snapshot(tmp_path) == {}


def test_sync_refuses_when_the_hook_files_cannot_be_written(tmp_path):
    _write(tmp_path, ".claude/hooks", b"a file where the folder belongs")
    assert pin_mod.sync(str(tmp_path), PIN) == {
        "action": "refused", "reason": "hook-files-unwritable", "changed": []}


def test_removal_refuses_unreadable_settings_and_removes_nothing(tmp_path):
    pin_mod.sync(str(tmp_path), PIN)
    _write(tmp_path, SETTINGS_PATH, "not json")
    before = _snapshot(tmp_path)
    assert pin_mod.sync(str(tmp_path), None)["reason"] == "settings-unreadable"
    assert _snapshot(tmp_path) == before


# ---- at_commit / in_tree ----

def _state(result):
    return (result["state"], result["reason"])


def test_at_commit_absent_when_nothing_of_ours_is_committed(tmp_path):
    root = _repo(tmp_path / "p", {})
    assert at(root) == {"state": "absent", "reason": None, "pin": None}


def at(root, commit="HEAD"):
    return pin_mod.at_commit(str(root), commit)


def test_at_commit_valid_for_the_files_sync_writes(tmp_path):
    root = _repo(tmp_path / "p", _good(tmp_path))
    assert at(root) == {"state": "valid", "reason": None, "pin": PIN}


def test_at_commit_describes_the_commit_not_the_working_tree(tmp_path):
    root = _repo(tmp_path / "p", _good(tmp_path))
    sha = _git(root, "rev-parse", "HEAD")
    (root / PIN_PATH).unlink()
    assert pin_mod.at_commit(str(root), sha) == {"state": "valid", "reason": None, "pin": PIN}
    assert pin_mod.in_tree(str(root)) == {"state": "broken", "reason": "pin-missing", "pin": None}


def test_at_commit_valid_when_the_registration_is_untidy_but_still_runs(tmp_path):
    entry = {"type": "command", "command": pin_mod.HOOK_COMMAND, "timeout": 7}
    settings = {"hooks": {"SessionStart": [{"hooks": [entry]}, {"hooks": [entry]}]}}
    root = _repo(tmp_path / "p", _bad(_good(tmp_path), settings=json.dumps(settings).encode()))
    assert _state(at(root)) == ("valid", None)


@pytest.mark.parametrize("name,changes,reason", [
    ("script-missing", {"script": None}, "script-missing"),
    ("script-differs", {"script": b"#!/bin/bash\nexit 0\n"}, "script-differs"),
    ("settings-not-registered", {"settings": b"{}"}, "settings-not-registered"),
    ("settings-missing", {"settings": None}, "settings-not-registered"),
    ("pin-missing", {"pin": None}, "pin-missing"),
    ("pin-invalid", {"pin": b"commit=short\n"}, "pin-invalid")])
def test_at_commit_is_broken_with_the_first_reason_that_holds(tmp_path, name, changes, reason):
    root = _repo(tmp_path / "p", _bad(_good(tmp_path), **changes))
    assert _state(at(root)) == ("broken", reason)


def test_at_commit_script_without_the_pin_or_settings_is_broken_not_absent(tmp_path):
    good = _good(tmp_path)
    root = _repo(tmp_path / "p", {SCRIPT_PATH: good[SCRIPT_PATH]})
    assert _state(at(root)) == ("broken", "settings-not-registered")


def test_at_commit_our_object_under_disable_all_hooks_is_broken_not_absent(tmp_path):
    settings = {"disableAllHooks": True, "hooks": {"SessionStart": [{"hooks": [
        {"type": "command", "command": pin_mod.HOOK_COMMAND}]}]}}
    root = _repo(tmp_path / "p", {SETTINGS_PATH: json.dumps(settings)})
    assert _state(at(root)) == ("broken", "script-missing")


def test_at_commit_a_symlinked_script_is_broken(tmp_path):
    good = _good(tmp_path)
    root = _repo(tmp_path / "p", _bad(good, script=None))
    link = root / SCRIPT_PATH
    link.parent.mkdir(parents=True, exist_ok=True)
    os.symlink("elsewhere.sh", str(link))
    _commit_all(root)
    assert _state(at(root)) == ("broken", "script-differs")


def test_at_commit_unreadable_commit_with_an_empty_working_tree_is_absent(tmp_path):
    root = _repo(tmp_path / "p", {})
    assert at(root, "d" * 40) == {"state": "absent", "reason": None, "pin": None}


def test_at_commit_unreadable_commit_with_a_pin_in_the_working_tree_is_broken(tmp_path):
    root = _repo(tmp_path / "p", {})
    _write(root, PIN_PATH, CANON)
    assert at(root, "d" * 40) == {"state": "broken", "reason": "commit-unreadable", "pin": None}
    assert at(root, "-bad-option") == {"state": "broken", "reason": "commit-unreadable", "pin": None}


def test_in_tree_reads_the_working_tree(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    assert pin_mod.in_tree(str(root))["state"] == "absent"
    pin_mod.sync(str(root), PIN)
    assert pin_mod.in_tree(str(root)) == {"state": "valid", "reason": None, "pin": PIN}
    (root / PIN_PATH).unlink()
    os.symlink("elsewhere", str(root / PIN_PATH))
    assert _state(pin_mod.in_tree(str(root))) == ("broken", "pin-invalid")
    (root / PIN_PATH).unlink()
    assert _state(pin_mod.in_tree(str(root))) == ("broken", "pin-missing")


# ---- the script ----

def _plug(tmp_path):
    src = _repo(tmp_path / "plugsrc", {SUBDIR + "/version.txt": "0.0.1\n"})
    _git(src, "config", "uploadpack.allowAnySHA1InWant", "true")
    sha_a = _git(src, "rev-parse", "HEAD")
    _write(src, SUBDIR + "/version.txt", "9.9.9\n")
    return src, sha_a, _commit_all(src)


class _Scene:
    pass


def _scene(tmp_path, installed="a", pin_version="9.9.9", pin_body=None):
    sc = _Scene()
    sc.root = tmp_path
    sc.src, sc.sha_a, sc.sha_b = _plug(tmp_path)
    old = tmp_path / "old"
    _git(tmp_path, "clone", "-q", str(sc.src), str(old))
    _git(old, "checkout", "-q", "--detach", {"a": sc.sha_a, "b": sc.sha_b}[installed])
    sc.link = tmp_path / "plugin"
    os.symlink(str(old / SUBDIR), str(sc.link))
    sc.project = tmp_path / "project"
    sc.project.mkdir()
    _git(sc.project, "init", "-q")
    sc.script = sc.project / SCRIPT_PATH
    _write(sc.project, SCRIPT_PATH, pin_mod.script_text(
        plugin_dir=str(sc.link), source_dir=str(tmp_path / "src")))
    pin = {**PIN, "commit": sc.sha_b, "version": pin_version}
    _write(sc.project, PIN_PATH, pin_mod.pin_text(pin) if pin_body is None else pin_body)
    sc.shared = tmp_path / ("src-" + sc.sha_b)  # the one destination the script before #2178 used
    return sc


def _script_env(sc, remote="true", source=None, bin_dir=None):
    env = _env(remote)
    env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_VALUE_0=URL,
               GIT_CONFIG_KEY_0="url.file://%s.insteadOf" % (source or sc.src))
    if bin_dir is not None:
        env["PATH"] = str(bin_dir) + os.pathsep + env["PATH"]
    return env


def _run_script(sc, remote="true", source=None, bin_dir=None):
    return subprocess.run(["bash", str(sc.script)], env=_script_env(sc, remote, source, bin_dir),
                          capture_output=True, text=True, timeout=120)


def _fetched(sc):
    """The plugin trees the script fetched: every src-<pinned sha>.* directory."""
    return sorted(n for n in os.listdir(str(sc.root)) if n.startswith("src-%s." % sc.sha_b))


def _fake_bin(tmp_path, scripts):
    """A directory of stand-in commands, put first on the script's PATH."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in scripts.items():
        _write(bin_dir, name, "#!/bin/bash\n" + body)
        os.chmod(str(bin_dir / name), 0o755)
    return bin_dir


def _linked(sc):
    return os.path.realpath(str(sc.link))


def _leftovers(sc):
    return [n for n in os.listdir(str(sc.root)) if ".tmp." in n or ".pin-tmp." in n]


def test_the_script_installs_a_different_commit(tmp_path):
    sc = _scene(tmp_path)
    done = _run_script(sc)
    assert done.returncode == 0, done.stderr
    assert done.stdout == "superheroes: plugin 9.9.9 installed at the pinned commit %s.\n" % sc.sha_b[:12]
    [fetched] = _fetched(sc)
    assert _linked(sc) == os.path.realpath(str(tmp_path / fetched / SUBDIR))
    assert (sc.link / "version.txt").read_text().strip() == "9.9.9"
    assert _git(sc.link, "rev-parse", "HEAD") == sc.sha_b
    assert _leftovers(sc) == []


def test_the_script_at_the_pinned_commit_fetches_nothing_and_says_nothing(tmp_path):
    sc = _scene(tmp_path, installed="b")
    before = _linked(sc)
    done = _run_script(sc, source=tmp_path / "does-not-exist")
    assert (done.returncode, done.stdout) == (0, "")
    assert _linked(sc) == before
    assert _fetched(sc) == []


def test_the_script_at_the_pinned_commit_with_another_version_fetches_again(tmp_path):
    sc = _scene(tmp_path, installed="b")
    (sc.link / "version.txt").write_text("6.6.6\n")  # a modified installed copy at the pinned commit
    done = _run_script(sc)
    assert done.returncode == 0, done.stderr
    assert done.stdout == "superheroes: plugin 9.9.9 installed at the pinned commit %s.\n" % sc.sha_b[:12]
    [fetched] = _fetched(sc)
    assert _linked(sc) == os.path.realpath(str(tmp_path / fetched / SUBDIR))
    assert (sc.link / "version.txt").read_text() == "9.9.9\n"


def test_the_script_fetch_failure_leaves_the_link_and_says_so(tmp_path):
    sc = _scene(tmp_path)
    before = _linked(sc)
    done = _run_script(sc, source=tmp_path / "does-not-exist")
    assert done.returncode == 0
    assert done.stdout == ("superheroes: plugin pin not applied: the pinned commit could not be "
                           "fetched; this session runs the plugin already installed (%s).\n" % sc.sha_a)
    assert _linked(sc) == before
    assert _leftovers(sc) == [] and _fetched(sc) == []


def test_the_script_does_not_link_a_tree_whose_version_disagrees_with_the_pin(tmp_path):
    sc = _scene(tmp_path, pin_version="8.8.8")
    before = _linked(sc)
    done = _run_script(sc)
    assert done.returncode == 0
    assert "plugin pin not applied: the fetched plugin is version 9.9.9, not the pinned 8.8.8" in done.stdout
    assert _linked(sc) == before
    assert _fetched(sc) == []


def test_the_script_does_not_link_a_fetched_tree_at_another_commit(tmp_path):
    sc = _scene(tmp_path)
    before = _linked(sc)
    git = shutil.which("git")
    bin_dir = _fake_bin(tmp_path, {"git": (
        '%s "$@" || exit\n'
        'if [ "$1 $2" = "checkout -q" ]; then\n'
        '  %s -c user.name=t -c user.email=t@t commit -q --allow-empty -m elsewhere\n'
        'fi\n' % (git, git))})
    done = _run_script(sc, bin_dir=bin_dir)
    assert done.returncode == 0
    assert "plugin pin not applied: the fetched plugin is not at the pinned commit;" in done.stdout
    assert _linked(sc) == before
    assert _fetched(sc) == []


def test_the_script_never_deletes_a_tree_another_session_is_publishing(tmp_path):
    # Another session's tree at the destination the script before #2178 shared, caught before its
    # version file landed: that script removed it and published its own in its place.
    sc = _scene(tmp_path)
    _write(sc.shared, "another-session", "x\n")
    done = _run_script(sc)
    assert done.returncode == 0, done.stderr
    assert (sc.shared / "another-session").read_text() == "x\n"
    assert not (sc.shared / SUBDIR).exists()
    [fetched] = _fetched(sc)
    assert _linked(sc) == os.path.realpath(str(tmp_path / fetched / SUBDIR))


def test_two_sessions_installing_at_once_each_fetch_their_own_tree(tmp_path):
    sc = _scene(tmp_path)
    runs = [subprocess.Popen(["bash", str(sc.script)], env=_script_env(sc), stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True) for _ in range(2)]
    outs = [run.communicate(timeout=120) for run in runs]
    assert [run.returncode for run in runs] == [0, 0], outs
    assert len(_fetched(sc)) == 2
    assert (sc.link / "version.txt").read_text() == "9.9.9\n"
    assert _leftovers(sc) == []


def _rename_onto(mv):
    """Shell text that renames "$2" onto the link "$3" itself with the host's own mv, whichever of the
    two no-follow forms the host accepts (GNU -T, BSD -h)."""
    return '%s -Tf "$2" "$3" 2>/dev/null || %s -fh "$2" "$3"; exit ;;\n' % (mv, mv)


def _bsd_mv_and_ln(tmp_path, sc):
    """mv and ln as a BSD system has them: mv knows -h and no -T; ln -f unlinks the old link before
    creating the new one, and here the creation fails, as an interruption between the two would."""
    mv, ln = shutil.which("mv"), shutil.which("ln")
    return _fake_bin(tmp_path, {
        "mv": ('case "$1" in\n'
               '  --version|-Tf) echo "mv: illegal option" >&2; exit 64 ;;\n'
               '  -fh) ' + _rename_onto(mv) +
               'esac\n'
               'exec %s "$@"\n' % mv),
        "ln": ('if [ "${@: -1}" = %s ]; then rm -f "${@: -1}"; exit 1; fi\n'
               'exec %s "$@"\n' % (str(sc.link), ln)),
    })


def test_the_script_never_leaves_the_session_without_a_link_on_a_bsd_system(tmp_path):
    sc = _scene(tmp_path)
    done = _run_script(sc, bin_dir=_bsd_mv_and_ln(tmp_path, sc))
    assert done.returncode == 0, done.stderr
    assert os.path.lexists(str(sc.link)), "the session was left with no plugin link"
    assert done.stdout == "superheroes: plugin 9.9.9 installed at the pinned commit %s.\n" % sc.sha_b[:12]
    [fetched] = _fetched(sc)
    assert _linked(sc) == os.path.realpath(str(tmp_path / fetched / SUBDIR))
    assert _leftovers(sc) == []


def test_the_script_renames_with_a_gnu_compatible_mv_that_is_not_gnu(tmp_path):
    # uutils coreutils: takes -T, rejects -h, and does not call itself GNU coreutils
    sc = _scene(tmp_path)
    mv = shutil.which("mv")
    bin_dir = _fake_bin(tmp_path, {"mv": (
        'case "$1" in\n'
        '  --version) echo "mv (uutils coreutils) 0.2.2" ; exit 0 ;;\n'
        '  -fh) echo "error: unexpected argument \'-h\' found" >&2; exit 1 ;;\n'
        '  -Tf) ' + _rename_onto(mv) +
        'esac\n'
        'exec %s "$@"\n' % mv)})
    done = _run_script(sc, bin_dir=bin_dir)
    assert done.returncode == 0, done.stderr
    assert done.stdout == "superheroes: plugin 9.9.9 installed at the pinned commit %s.\n" % sc.sha_b[:12]
    [fetched] = _fetched(sc)
    assert _linked(sc) == os.path.realpath(str(tmp_path / fetched / SUBDIR))
    assert _leftovers(sc) == []


def test_the_script_keeps_the_old_link_when_mv_cannot_rename_onto_it(tmp_path):
    sc = _scene(tmp_path)
    before = _linked(sc)
    bin_dir = _fake_bin(tmp_path, {"mv": 'echo "mv: illegal option" >&2; exit 64\n'})
    done = _run_script(sc, bin_dir=bin_dir)
    assert done.returncode == 0
    assert done.stdout.startswith("superheroes: plugin pin not applied: the plugin link could not be "
                                  "replaced;")
    assert _linked(sc) == before
    assert _leftovers(sc) == [] and _fetched(sc) == []


def test_the_script_bounds_the_checkout_as_well_as_the_fetch(tmp_path):
    sc = _scene(tmp_path)
    calls = tmp_path / "timeout-calls"
    bin_dir = _fake_bin(tmp_path, {"timeout": 'echo "$*" >> %s\nshift\nexec "$@"\n' % calls})
    done = _run_script(sc, bin_dir=bin_dir)
    assert done.returncode == 0, done.stderr
    bounded = [line.split()[:3] for line in calls.read_text().splitlines()]
    assert ["120", "git", "fetch"] in bounded and ["120", "git", "checkout"] in bounded


def test_the_script_comments_claim_only_what_it_does():
    text = pin_mod.script_text()
    for overstated in ("never to the session", "It never fails the session"):
        assert overstated not in text
    assert "is reported by the session itself" in text


def test_the_script_leaves_the_link_for_a_malformed_pin(tmp_path):
    sc = _scene(tmp_path, pin_body=_text(commit="xyz"))
    before = _linked(sc)
    done = _run_script(sc)
    assert done.returncode == 0
    assert done.stdout == ("superheroes: plugin pin not applied: the pin commit is not a full "
                           "lowercase sha; this session runs the plugin already installed (%s).\n"
                           % sc.sha_a)
    assert _linked(sc) == before
    assert _fetched(sc) == []


@pytest.mark.parametrize("body,why", [
    (CANON + "version=1.2.4\n", "the pin file repeats version"),
    (CANON + "extra=1\n", "the pin file has an unknown key"),
    (_text(subdir=None), "the pin file has no subdir"),
    (CANON + "stray\n", "the pin file has a line that is not key=value"),
    (_text(subdir="a/../b"), "the pin subdir is not a plain relative path")])
def test_the_script_reads_the_pin_as_strictly_as_parse_pin(tmp_path, body, why):
    sc = _scene(tmp_path, pin_body=body)
    assert pin_mod.parse_pin(body) is None
    done = _run_script(sc)
    assert done.returncode == 0
    assert done.stdout.startswith("superheroes: plugin pin not applied: %s;" % why)


def test_the_script_does_nothing_outside_a_cloud_session(tmp_path):
    sc = _scene(tmp_path)
    before = _linked(sc)
    for remote in (None, "false"):
        done = _run_script(sc, remote=remote)
        assert (done.returncode, done.stdout, done.stderr) == (0, "", "")
    assert _linked(sc) == before
    assert _fetched(sc) == []


def test_the_script_without_a_pin_file_says_so(tmp_path):
    sc = _scene(tmp_path)
    (sc.project / PIN_PATH).unlink()
    done = _run_script(sc)
    assert done.returncode == 0
    assert done.stdout.startswith("superheroes: plugin pin not applied: the pin file is missing;")


# ---- census, CLI ----

def test_nothing_sync_writes_carries_a_secret_shape(tmp_path):
    pin_mod.sync(str(tmp_path), PIN)
    texts = [pin_mod.script_text(), pin_mod.pin_text(PIN), (tmp_path / SETTINGS_PATH).read_text()]
    for text in texts:
        assert cloud_setup_text._scan(text) is None
        assert cloud_pass.PASS_ENV not in text


def test_status_reads_a_repository_written_by_the_script_before_2178_as_needing_a_rewrite(
        tmp_path, capsys):
    root = _repo(tmp_path / "p", {})
    assert pin_mod.sync(str(root), PIN)["action"] == "written"
    with open(OLD_SCRIPT, "rb") as old:
        _write(root, SCRIPT_PATH, old.read())
    _commit_all(root)
    assert _state(pin_mod.at_commit(str(root), "HEAD")) == ("broken", "script-differs")
    assert pin_mod.main(["status", "--cwd", str(root)]) == 0
    assert json.loads(capsys.readouterr().out)["reason"] == "script-differs"
    assert pin_mod.sync(str(root), PIN)["changed"] == [SCRIPT_PATH]


def test_the_cli_status_remove_and_write(tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path / "p", {})
    monkeypatch.setattr(pin_mod, "installed_pin", lambda cwd, env=None: (PIN, None))
    assert pin_mod.main(["write", "--cwd", str(root)]) == 0
    written = json.loads(capsys.readouterr().out)
    assert written["action"] == "written" and written["pin"] == PIN and written["detail"] is None
    assert "commit and push" in written["message"].lower()
    _commit_all(root)
    assert pin_mod.main(["status", "--cwd", str(root)]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "valid"
    assert pin_mod.main(["remove", "--cwd", str(root)]) == 0
    assert json.loads(capsys.readouterr().out)["action"] == "removed"
    refusal = {"action": "refused", "reason": "plugin-source-unknown", "detail": "d"}
    monkeypatch.setattr(pin_mod, "installed_pin", lambda cwd, env=None: (None, refusal))
    assert pin_mod.main(["write", "--cwd", str(root)]) == 1
    assert json.loads(capsys.readouterr().out) == {**refusal, "changed": []}
