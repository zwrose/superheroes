"""Tests for #2021: cloud readiness checks the dependency hook on the commit the build starts from.

Every fixture project is a real git repository under tmp_path (every git call pins its global and
system configuration away and passes its identity inline), and every store, home and Claude config
directory is under tmp_path too. No test reads the real home directory or the network.
"""
import datetime
import functools
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

import cloud_check  # noqa: E402
import cloud_dependency_hook as hook  # noqa: E402
import cloud_ready  # noqa: E402
import cloud_setup  # noqa: E402
import cloud_setup_text as CS  # noqa: E402
import core_md  # noqa: E402
import launch_place  # noqa: E402
import launch_report  # noqa: E402
import mode_registry  # noqa: E402
import project_config as PC  # noqa: E402
import store_core  # noqa: E402

# inherited GIT_* routing (GIT_INDEX_FILE, GIT_DIR, GIT_WORK_TREE...) would send a fixture's git call to
# the caller's repository, so none of it is kept; the two pins are the only GIT_* the fixtures get
_GIT_ENV = {**{k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
ORIGIN = "https://github.com/acme/corner-shop.git"
ACCOUNT = "acct-fixture-one"
ENVIRONMENT = "env-fixture-one"
ADVISOR = "1.2.3"
TODAY = datetime.date(2026, 10, 11)
CORE_FACTS = {"verifyCommand": "npm test", "stackTags": ["node"], "threatModel": "single-user",
              "patterns": "- x: a.ts:1"}
COMMANDS = ["npm ci"]
INPUTS = ["package-lock.json"]
COMMANDS_SLUG = "cloudSetupCommands"
HOOK_SLUG = "cloudDependencyHook"
OTHERS = ("setup", "passPresent", "passLive", "version", "calibration", "platform")


class World:
    pass


def _git(cwd, *args):
    done = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, env=_GIT_ENV,
                          check=True)
    return done.stdout.decode("utf-8").strip()


def _commit(cwd, message="c", stage=True):
    if stage:
        _git(cwd, "add", "-A")
    _git(cwd, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c",
         "commit.gpgsign=false", "commit", "-q", "--allow-empty", "-m", message)
    return _git(cwd, "rev-parse", "HEAD")


def _world(tmp_path):
    w = World()
    w.tmp = tmp_path
    w.repo = tmp_path / "repo"
    w.repo.mkdir(parents=True)
    _git(w.repo, "init", "-q")
    _git(w.repo, "remote", "add", "origin", ORIGIN)
    w.cwd = str(w.repo)
    w.root = str(tmp_path / "store-root")
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    (home / ".claude.json").write_text(json.dumps({"oauthAccount": {"accountUuid": ACCOUNT}}))
    w.env = {"HOME": str(home)}
    remote_key = store_core.derive_identifiers(w.cwd)["remote_hash"]
    mode_registry.write_registry(w.cwd, mode_registry.GLOBAL, remote_key, root=w.root)
    done = core_md.write(w.cwd, dict(CORE_FACTS), "confirmed", root=w.root, now="2026-06-26")
    assert done["action"] in ("written", "reused"), done
    w.settings = w.repo / ".claude" / "settings.json"
    w.script = w.repo / hook.SCRIPT_REL.replace("/", os.sep)
    return w


def _set_ok(w, slug, value):
    got = PC.set_item(w.cwd, slug, value, root=w.root)
    assert got["action"] in ("written", "noop"), got
    return got


def _lock(w, text="v1\n"):
    (w.repo / "package-lock.json").write_text(text)


def _record(w, **over):
    values = dict(
        root=w.root, account=ACCOUNT, environment=ENVIRONMENT, plugin_version=ADVISOR,
        picks_up_version=False, calibration_stamp=cloud_check._placed_stamp(w.cwd, w.root),
        calibration_date="2026-10-01", pass_lapses="2099-01-01", checked_at="2026-10-09")
    values.update(over)
    got = cloud_setup.record_check(w.cwd, **values)
    assert got["action"] in ("written", "noop"), got


def _ready(w, **kw):
    args = dict(account=ACCOUNT, advisor_version=ADVISOR, today=TODAY, root=w.root)
    args.update(kw)
    return cloud_ready.readiness(w.cwd, **args)


def _hooked(tmp_path):
    """A project with the hook on whose first commit lacks it and second carries it. The setup is
    recorded against the final calibration. Returns (world, commit without the hook, commit with it)."""
    w = _world(tmp_path)
    _lock(w)
    _set_ok(w, COMMANDS_SLUG, list(COMMANDS))
    bare = _commit(w.cwd, "bare")
    assert _set_ok(w, HOOK_SLUG, True)["dependencyHook"]["action"] == "written"
    with_hook = _commit(w.cwd, "hook")
    _record(w)
    return w, bare, with_hook


def _drop_hook_files(w):
    _git(w.repo, "rm", "-q", hook.SCRIPT_REL, hook.SETTINGS_REL)
    return _commit(w.cwd, "drop")


# ---------------------------------------------------------------- fixture git isolation


_ROUTING_PROBE = """
import sys
sys.path.insert(0, %(here)r)
import test_cloud_branch_hook_2021 as T


def test_fixture_commits_stay_in_the_fixture_repository(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    T._git(repo, "init", "-q")
    (repo / "f.txt").write_text("x\\n")
    T._commit(repo, "c")
"""


def test_inherited_git_index_routing_never_reaches_the_fixture_commands(tmp_path):
    here = tmp_path / "probe"
    here.mkdir()
    (here / "test_probe.py").write_text(_ROUTING_PROBE % {"here": _HERE})
    sentinel = tmp_path / "sentinel-index"
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_INDEX_FILE=str(sentinel), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
               PYTHONDONTWRITEBYTECODE="1")
    ran = subprocess.run(
        [sys.executable, "-m", "pytest", str(here / "test_probe.py"), "-q", "-p", "no:cacheprovider",
         "--rootdir", str(here)],
        capture_output=True, env=env, cwd=str(here))
    assert ran.returncode == 0, ran.stdout.decode("utf-8") + ran.stderr.decode("utf-8")
    assert b"1 passed" in ran.stdout
    assert not sentinel.exists()


# ---------------------------------------------------------------- DoD row 1


def test_dod1_hook_on_and_head_lacks_the_hook_is_not_ready_for_that_reason_alone(tmp_path):
    w, bare, with_hook = _hooked(tmp_path)
    assert _ready(w)["ready"] is True
    _drop_hook_files(w)
    got = _ready(w)
    assert got["ready"] is False and got["reason"] == "dependency-hook"
    assert got["conditions"]["dependencyHook"] is False
    assert all(got["conditions"][name] is True for name in OTHERS)
    # the saved setting still says the hook is on; only the commit is read
    assert PC.get_item(w.cwd, HOOK_SLUG, root=w.root)["raw"] is True


def test_dod1_a_passed_commit_is_the_one_read(tmp_path):
    w, bare, with_hook = _hooked(tmp_path)
    assert _ready(w, commit=with_hook)["ready"] is True
    got = _ready(w, commit=bare)
    assert got["reason"] == "dependency-hook" and got["conditions"]["dependencyHook"] is False
    assert _ready(w, commit="no-such-commit")["conditions"]["dependencyHook"] is False


def _account_route(w, premise, word="cloud", **kw):
    kw.setdefault("needs_fn", lambda *a, **k: [])
    return launch_place.route(w.cwd, premise, word, root=w.root, env=w.env, **kw)


def _record_for_routing(w):
    # route uses the real plugin version and today's date, so the record names them
    _record(w, plugin_version=CS._plugin_version())


def test_dod1_routing_a_base_commit_without_the_hook_runs_locally_with_the_new_words(tmp_path):
    w, bare, with_hook = _hooked(tmp_path)
    _record_for_routing(w)
    assert _account_route(w, {"baseCommit": with_hook})["place"] == "cloud"
    call = _account_route(w, {"baseCommit": bare})
    assert call["place"] == "local" and call["reason"] == "dependency-hook"
    assert launch_place.reason_text(call) == (
        "The dependency hook on the branch this build starts from failed its check "
        "(`script-missing`): it has no dependency hook script, so the cloud could build it "
        "with out-of-date dependencies.")
    assert launch_place.fix_text(call) == (
        "To fix it, set configure's item 17, 18 or 19 again (any set rewrites the hook files), "
        "then commit and push the settings file and the hook script on the branch builds start "
        "from. Then launch again.")
    assert "at the regular file itself, with no link in between" in (
        launch_place.REASONS["dependency-hook"]["fix"])
    assert launch_place.REASONS["dependency-hook"]["short"] == (
        "Bring the dependency hook and any adopted setup-file change onto the starting branch, "
        "and list setup files as regular files, to fix it.")
    assert "regular files" in launch_place.REASONS["dependency-hook"]["short"]
    assert launch_place.REASONS["dependency-hook"]["wasnt"] == (
        "the branch it starts from doesn't carry the dependency hook, or a setup file it adopts "
        "can't be shown unchanged.")


def test_route_reads_the_startup_commit_not_the_checkout_head(tmp_path):
    w, bare, with_hook = _hooked(tmp_path)
    _record_for_routing(w)
    # HEAD carries the hook, the startup commit does not
    assert _git(w.repo, "rev-parse", "HEAD") == with_hook
    call = _account_route(w, {"baseCommit": bare})
    assert call["place"] == "local" and call["reason"] == "dependency-hook"
    # HEAD lacks the hook, the startup commit carries it
    _drop_hook_files(w)
    assert _account_route(w, {"baseCommit": with_hook})["place"] == "cloud"
    call = _account_route(w, {})
    assert call["place"] == "local" and call["reason"] == "dependency-hook"


def test_route_with_an_injected_readiness_calls_it_as_before(tmp_path):
    w, bare, with_hook = _hooked(tmp_path)
    seen = []

    def fake(cwd, reported=None, root=None, env=None):
        seen.append((cwd, reported, root, env))
        return {"ready": True, "reason": None, "setting": True, "environment": "e"}

    call = _account_route(w, {"baseCommit": bare, "adoptsHead": with_hook}, readiness_fn=fake)
    assert call["place"] == "cloud" and len(seen) == 1


# ---------------------------------------------------------------- adoption


def test_adoption_changing_a_listed_input_is_not_ready(tmp_path):
    w, bare, with_hook = _hooked(tmp_path)
    _lock(w, "v2\n")
    adopted = _commit(w.cwd, "lock changed")
    got = _ready(w, commit=with_hook, adopted=adopted)
    assert got["reason"] == "dependency-hook" and got["conditions"]["dependencyHook"] is False
    assert hook.branch_gap(w.cwd, with_hook, COMMANDS, INPUTS, adopted) == "adopted-inputs-differ"


def test_adoption_with_identical_inputs_is_ready(tmp_path):
    w, bare, with_hook = _hooked(tmp_path)
    (w.repo / "other.txt").write_text("x\n")
    adopted = _commit(w.cwd, "other file")
    assert _ready(w, commit=with_hook, adopted=adopted)["ready"] is True


def test_adoption_where_only_the_adopted_head_carries_the_hook_is_not_ready(tmp_path):
    w, bare, with_hook = _hooked(tmp_path)
    got = _ready(w, commit=bare, adopted=with_hook)
    assert got["reason"] == "dependency-hook" and got["conditions"]["dependencyHook"] is False


def test_routing_passes_the_adopted_head(tmp_path):
    w, bare, with_hook = _hooked(tmp_path)
    _record_for_routing(w)
    _lock(w, "v2\n")
    adopted = _commit(w.cwd, "lock changed")
    call = _account_route(w, {"baseCommit": with_hook, "adoptsHead": adopted})
    assert call["place"] == "local" and call["reason"] == "dependency-hook"
    assert _account_route(w, {"baseCommit": with_hook, "adoptsHead": with_hook})["place"] == "cloud"


def test_routing_an_adopted_dependency_change_tells_the_owner_about_the_adoption(tmp_path):
    w, bare, with_hook = _hooked(tmp_path)
    _record_for_routing(w)
    _lock(w, "v2\n")
    adopted = _commit(w.cwd, "lock changed")
    call = _account_route(w, {"baseCommit": with_hook, "adoptsHead": adopted})
    assert call["place"] == "local" and call["reason"] == "dependency-hook"
    reason = launch_place.reason_text(call)
    assert "adopts" in reason and "setup file" in reason
    fix = launch_place.fix_text(call)
    assert "adopts" in fix and "dependency file" in fix


# ---------------------------------------------------------------- DoD row 2


def test_dod2_an_input_change_after_the_hook_is_committed_asks_for_no_repaste(tmp_path):
    w, bare, with_hook = _hooked(tmp_path)
    before = _ready(w)
    assert before["conditions"]["dependencyHook"] is True and before["ready"] is True
    _lock(w, "v2\n")
    _commit(w.cwd, "lock changed")
    after = _ready(w)
    assert after["conditions"]["calibration"] is True
    assert after["conditions"]["dependencyHook"] is True and after["ready"] is True


# ---------------------------------------------------------------- hook off


def test_hook_off_reads_no_git_even_in_a_checkout_with_no_commits(tmp_path):
    w = _world(tmp_path)
    _set_ok(w, COMMANDS_SLUG, list(COMMANDS))
    _set_ok(w, HOOK_SLUG, False)
    # HEAD does not exist yet, so a git read would be unreadable
    assert hook.branch_gap(w.cwd, "HEAD", COMMANDS, INPUTS) == "commit-unreadable"
    assert CS.branch_hook_gap(w.cwd, w.root) is None
    assert CS.branch_hook_gap(w.cwd, w.root, "no-such-commit", "also-none") is None


def test_hook_off_never_calls_git(tmp_path, monkeypatch):
    w = _world(tmp_path)
    _set_ok(w, COMMANDS_SLUG, list(COMMANDS))
    _set_ok(w, HOOK_SLUG, False)

    def boom(*a, **k):
        raise AssertionError("git was read")

    monkeypatch.setattr(hook, "_git_out", boom)
    assert CS.branch_hook_gap(w.cwd, w.root) is None


def test_hook_off_in_a_directory_that_is_not_a_repository_reads_no_git(tmp_path):
    w = _world(tmp_path)
    _set_ok(w, COMMANDS_SLUG, list(COMMANDS))
    _set_ok(w, HOOK_SLUG, False)
    shutil.rmtree(w.repo / ".git")
    assert not (w.repo / ".git").exists()
    assert CS.branch_hook_gap(w.cwd, w.root) is None
    assert hook.branch_gap(w.cwd, "HEAD", COMMANDS, INPUTS) == "commit-unreadable"


def test_no_stored_commands_is_not_a_hook_on_project(tmp_path):
    w = _world(tmp_path)
    assert CS.branch_hook_gap(w.cwd, w.root) is None


def test_hook_off_readiness_is_unchanged_and_ready(tmp_path):
    w = _world(tmp_path)
    _lock(w)
    _set_ok(w, COMMANDS_SLUG, list(COMMANDS))
    _commit(w.cwd, "bare")
    _record(w)
    got = _ready(w)
    assert got["ready"] is True and got["conditions"]["dependencyHook"] is True


# ---------------------------------------------------------------- order (F2)


def test_the_hook_gap_is_named_before_a_calibration_mismatch(tmp_path):
    w, bare, with_hook = _hooked(tmp_path)
    _drop_hook_files(w)
    got = _ready(w, stamp_fn=lambda cwd, root: "other-stamp")
    assert got["conditions"]["dependencyHook"] is False and got["conditions"]["calibration"] is False
    assert got["reason"] == "dependency-hook"
    assert cloud_ready.CONDITION_ORDER.index("dependencyHook") < cloud_ready.CONDITION_ORDER.index(
        "calibration")
    readiness_fn = functools.partial(
        cloud_ready.readiness, account=ACCOUNT, advisor_version=ADVISOR, today=TODAY,
        stamp_fn=lambda cwd, root: "other-stamp")
    call = _account_route(w, {}, readiness_fn=readiness_fn)
    assert call["reason"] == "dependency-hook"
    fix = launch_place.fix_text(call)
    assert "paste" not in fix.lower() and "setup text" not in fix.lower()


# ---------------------------------------------------------------- the fail-closed edges


def _edge_repo(tmp_path, *, script="good", settings="good", name="edge"):
    """A repository with one commit whose hook files are as asked. Returns (repo, commit)."""
    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init", "-q")
    registered = {"hooks": {"SessionStart": [{"hooks": [
        {"type": "command", "command": hook.HOOK_COMMAND, "timeout": 600}]}]}}
    (repo / ".claude" / "hooks").mkdir(parents=True)
    (repo / "package-lock.json").write_text("v1\n")
    if script == "good":
        (repo / hook.SCRIPT_REL).write_text(hook.script_text(COMMANDS, INPUTS))
        os.chmod(repo / hook.SCRIPT_REL, 0o755)
    elif script == "other-commands":
        (repo / hook.SCRIPT_REL).write_text(hook.script_text(["pip install ."], INPUTS))
    elif script == "symlink":
        # a symlink entry whose blob holds exactly the script's bytes, so only its mode refuses it
        oid = subprocess.run(
            ["git", "-C", str(repo), "hash-object", "-w", "--stdin"], capture_output=True,
            env=_GIT_ENV, check=True, input=hook.script_text(COMMANDS, INPUTS).encode("utf-8")
        ).stdout.decode().strip()
        _git(repo, "update-index", "--add", "--cacheinfo", "120000,%s,%s" % (oid, hook.SCRIPT_REL))
    elif script == "directory":
        (repo / hook.SCRIPT_REL).mkdir()
        (repo / hook.SCRIPT_REL / "inner").write_text("x")
    if settings == "good":
        (repo / hook.SETTINGS_REL).write_text(json.dumps(registered))
    elif isinstance(settings, dict):
        (repo / hook.SETTINGS_REL).write_text(json.dumps(settings))
    elif isinstance(settings, str) and settings != "absent":
        (repo / hook.SETTINGS_REL).write_text(settings)
    if script == "symlink":
        # `add -A` would drop the index-only symlink entry, so the other files are staged by name
        _git(repo, "add", "package-lock.json", hook.SETTINGS_REL)
    return str(repo), _commit(repo, "edge", stage=script != "symlink")


def _hook_entry(**over):
    entry = {"type": "command", "command": hook.HOOK_COMMAND, "timeout": 600}
    entry.update(over)
    return entry


def _gap(repo, commit, **kw):
    return hook.branch_gap(repo, commit, kw.pop("commands", COMMANDS), kw.pop("inputs", INPUTS),
                           **kw)


def test_a_commit_carrying_the_hook_has_no_gap(tmp_path):
    repo, commit = _edge_repo(tmp_path)
    assert _gap(repo, commit) is None
    assert _gap(repo, "HEAD") is None


def test_edge1_a_commit_that_does_not_resolve_is_unreadable(tmp_path):
    repo, commit = _edge_repo(tmp_path)
    assert _gap(repo, "0123456789abcdef0123456789abcdef01234567") == "commit-unreadable"
    assert _gap(repo, "no-such-ref") == "commit-unreadable"
    assert _gap(repo, "--help") == "commit-unreadable"
    assert _gap(repo, "") == "commit-unreadable"
    assert _gap(str(tmp_path / "nowhere"), "HEAD") == "commit-unreadable"


def test_edge2_an_adopted_head_that_does_not_resolve_is_unreadable(tmp_path):
    repo, commit = _edge_repo(tmp_path)
    assert _gap(repo, commit, adopted="no-such-ref") == "commit-unreadable"


def test_edge3_a_missing_script(tmp_path):
    repo, commit = _edge_repo(tmp_path, script="absent")
    assert _gap(repo, commit) == "script-missing"


@pytest.mark.parametrize("kind", ["symlink", "directory"])
def test_edge4_a_script_that_is_not_a_regular_file_differs(tmp_path, kind):
    repo, commit = _edge_repo(tmp_path, script=kind)
    assert _gap(repo, commit) == "script-differs"


def test_edge5_a_script_written_for_other_commands_differs(tmp_path):
    repo, commit = _edge_repo(tmp_path, script="other-commands")
    assert _gap(repo, commit) == "script-differs"
    good, good_commit = _edge_repo(tmp_path, name="good")
    assert _gap(good, good_commit, commands=["something else"]) == "script-differs"
    assert _gap(good, good_commit, inputs=["uv.lock"]) == "script-differs"


def test_edge6_missing_settings(tmp_path):
    repo, commit = _edge_repo(tmp_path, settings="absent")
    assert _gap(repo, commit) == "settings-not-registered"


@pytest.mark.parametrize("body", ["{not json", "[]", '"text"', "null", "\xff\xfe"])
def test_edge7_settings_that_are_not_a_json_object(tmp_path, body):
    repo, commit = _edge_repo(tmp_path, settings=body)
    assert _gap(repo, commit) == "settings-not-registered"


def test_edge8_disable_all_hooks_refuses(tmp_path):
    settings = {"disableAllHooks": True, "hooks": {"SessionStart": [{"hooks": [_hook_entry()]}]}}
    repo, commit = _edge_repo(tmp_path, settings=settings)
    assert _gap(repo, commit) == "settings-not-registered"


def test_edge9_a_group_that_does_not_cover_startup_refuses(tmp_path):
    settings = {"hooks": {"SessionStart": [{"matcher": "resume", "hooks": [_hook_entry()]}]}}
    repo, commit = _edge_repo(tmp_path, settings=settings)
    assert _gap(repo, commit) == "settings-not-registered"
    covering = {"hooks": {"SessionStart": [{"matcher": "startup|resume", "hooks": [_hook_entry()]}]}}
    repo, commit = _edge_repo(tmp_path, settings=covering, name="covering")
    assert _gap(repo, commit) is None


def test_edge10_a_hook_entry_of_another_type_or_command_refuses(tmp_path):
    for n, entry in enumerate([_hook_entry(type="prompt"), _hook_entry(command="bash other.sh")]):
        settings = {"hooks": {"SessionStart": [{"hooks": [entry]}]}}
        repo, commit = _edge_repo(tmp_path, settings=settings, name="e%d" % n)
        assert _gap(repo, commit) == "settings-not-registered"


def test_edge11_adopted_inputs_that_differ(tmp_path):
    repo, commit = _edge_repo(tmp_path)
    assert _gap(repo, commit, adopted=commit) is None
    # bytes differ
    (tmp_path / "edge" / "package-lock.json").write_text("v2\n")
    changed = _commit(repo, "changed")
    assert _gap(repo, commit, adopted=changed) == "adopted-inputs-differ"
    # present at the adopted head only
    _git(repo, "rm", "-q", "package-lock.json")
    removed = _commit(repo, "removed")
    assert _gap(repo, removed, adopted=changed) == "adopted-inputs-differ"
    assert _gap(repo, changed, adopted=removed) == "adopted-inputs-differ"
    # absent at both is the same
    assert _gap(repo, removed, adopted=removed) is None


def test_edge11_an_input_that_is_a_directory_at_one_head_differs(tmp_path):
    repo, commit = _edge_repo(tmp_path)
    _git(repo, "rm", "-q", "package-lock.json")
    (tmp_path / "edge" / "package-lock.json").mkdir()
    (tmp_path / "edge" / "package-lock.json" / "f").write_text("x")
    swapped = _commit(repo, "swapped")
    assert _gap(repo, commit, adopted=swapped) == "adopted-input-not-a-file"


def _hooked_with_dot_slash_input(tmp_path):
    """A hooked project whose stored item 18 is one entry: the lockfile named with a leading dot-slash
    segment. Returns (world, the commit carrying the hook files for that list)."""
    w = _world(tmp_path)
    _lock(w)
    _set_ok(w, COMMANDS_SLUG, list(COMMANDS))
    _set_ok(w, "cloudSetupInputs", ["./" + INPUTS[0]])
    assert _set_ok(w, HOOK_SLUG, True)["dependencyHook"]["action"] == "written"
    start = _commit(w.cwd, "hook")
    _record(w)
    return w, start


def test_adoption_changing_a_dot_slash_listed_input_differs(tmp_path):
    w, start = _hooked_with_dot_slash_input(tmp_path)
    _lock(w, "v2\n")
    adopted = _commit(w.cwd, "lock changed")
    assert CS.branch_hook_gap(w.cwd, w.root, start, adopted) == "adopted-inputs-differ"


def test_adoption_leaving_a_dot_slash_listed_input_unchanged_has_no_gap(tmp_path):
    w, start = _hooked_with_dot_slash_input(tmp_path)
    (w.repo / "other.txt").write_text("x\n")
    adopted = _commit(w.cwd, "other file")
    assert CS.branch_hook_gap(w.cwd, w.root, start, adopted) is None


NESTED_INPUT = "deps/requirements.txt"


def _hooked_with_nested_input(tmp_path, linked):
    """A hooked project whose stored item 18 is one nested entry (directory `deps`, file
    `requirements.txt` inside it). With `linked`, `deps` is a committed symlink to the real directory
    `real-deps` that holds the file. Returns (world, the commit carrying the hook files)."""
    w = _world(tmp_path)
    holder = w.repo / ("real-deps" if linked else "deps")
    holder.mkdir()
    (holder / "requirements.txt").write_text("v1\n")
    if linked:
        (w.repo / "deps").symlink_to("real-deps")
    _set_ok(w, COMMANDS_SLUG, list(COMMANDS))
    _set_ok(w, "cloudSetupInputs", [NESTED_INPUT])
    assert _set_ok(w, HOOK_SLUG, True)["dependencyHook"]["action"] == "written"
    start = _commit(w.cwd, "hook")
    _record(w)
    return w, start


def test_adoption_changing_a_file_behind_a_symlinked_input_directory_differs(tmp_path):
    w, start = _hooked_with_nested_input(tmp_path, linked=True)
    (w.repo / "real-deps" / "requirements.txt").write_text("v2\n")
    adopted = _commit(w.cwd, "target file changed")
    assert CS.branch_hook_gap(w.cwd, w.root, start, adopted) == "adopted-input-not-a-file"


def test_adoption_leaving_a_symlinked_input_directory_unchanged_still_cannot_be_compared(tmp_path):
    w, start = _hooked_with_nested_input(tmp_path, linked=True)
    (w.repo / "other.txt").write_text("x\n")
    adopted = _commit(w.cwd, "other file")
    assert CS.branch_hook_gap(w.cwd, w.root, start, adopted) == "adopted-input-not-a-file"


def test_adoption_of_a_nested_input_in_a_real_directory_is_read_by_its_blob(tmp_path):
    w, start = _hooked_with_nested_input(tmp_path, linked=False)
    (w.repo / "other.txt").write_text("x\n")
    unchanged = _commit(w.cwd, "other file")
    assert CS.branch_hook_gap(w.cwd, w.root, start, unchanged) is None
    (w.repo / "deps" / "requirements.txt").write_text("v2\n")
    changed = _commit(w.cwd, "nested file changed")
    assert CS.branch_hook_gap(w.cwd, w.root, start, changed) == "adopted-inputs-differ"


def test_edge11_a_symlink_input_with_an_unchanged_target_is_not_a_file(tmp_path):
    repo, _ = _edge_repo(tmp_path)
    root = tmp_path / "edge"
    (root / "dependency-lock.json").write_text("v1\n")
    (root / "package-lock.json").unlink()
    (root / "package-lock.json").symlink_to("dependency-lock.json")
    linked = _commit(repo, "input is a symlink")
    (root / "other.txt").write_text("x\n")
    adopted = _commit(repo, "other file")
    assert _gap(repo, linked, adopted=adopted) == "adopted-input-not-a-file"


def test_edge12_a_reader_that_raises_reads_as_not_ready(tmp_path, monkeypatch):
    w, bare, with_hook = _hooked(tmp_path)
    assert _ready(w)["ready"] is True
    real_root = store_core.repo_root

    def root(cwd, **kw):
        if sys._getframe(1).f_code.co_name == "branch_hook_gap":
            raise store_core.RepoRootUnavailable("not a checkout")
        return real_root(cwd, **kw)

    monkeypatch.setattr(store_core, "repo_root", root)
    with pytest.raises(store_core.RepoRootUnavailable):
        CS.branch_hook_gap(w.cwd, w.root)
    got = _ready(w)
    assert got["conditions"]["dependencyHook"] is False and got["reason"] == "dependency-hook"


def test_edge12_unreadable_calibration_reads_as_not_ready(tmp_path, monkeypatch):
    w, bare, with_hook = _hooked(tmp_path)

    def refused(cwd, root):
        raise CS._Refused("setup-commands-unreadable", "unreadable")

    monkeypatch.setattr(CS, "_dependency_hook_on", lambda cwd, root, commands: refused(cwd, root))
    got = _ready(w)
    assert got["conditions"]["dependencyHook"] is False and got["ready"] is False


# ---------------------------------------------------------------- parity census


def _record_snippet():
    lines = hook.script_text(COMMANDS, INPUTS).splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.endswith("<<'PY' 2>/dev/null")) + 1
    end = lines.index("PY", start)
    return "\n".join(lines[start:end]) + "\n"


def _startup(matcher=None, **over):
    group = {"hooks": [_hook_entry()]}
    if matcher is not None:
        group["matcher"] = matcher
    group.update(over)
    return {"hooks": {"SessionStart": [group]}}


CORPUS = [
    json.dumps(_startup()),
    json.dumps(_startup("")),
    json.dumps(_startup("*")),
    json.dumps(_startup("startup")),
    json.dumps(_startup("startup|resume")),
    json.dumps(_startup("resume")),
    json.dumps(_startup("start.*")),
    json.dumps(_startup("start++up")),
    json.dumps(_startup(5)),
    json.dumps({**_startup(), "disableAllHooks": True}),
    json.dumps({**_startup(), "disableAllHooks": False}),
    json.dumps({**_startup(), "disableAllHooks": "yes"}),
    json.dumps({"hooks": {"SessionStart": [{"hooks": [_hook_entry(type="prompt")]}]}}),
    json.dumps({"hooks": {"SessionStart": [{"hooks": [_hook_entry(command="bash x.sh")]}]}}),
    json.dumps({"hooks": {"SessionStart": ["text", {"hooks": [_hook_entry()]}]}}),
    json.dumps({"hooks": {"SessionStart": [{"hooks": None}]}}),
    json.dumps({"hooks": {"SessionStart": [{}]}}),
    json.dumps({"hooks": {"SessionStart": [{"hooks": ["x", _hook_entry()]}]}}),
    json.dumps({"hooks": {"SessionStart": {"hooks": [_hook_entry()]}}}),
    json.dumps({"hooks": None}),
    json.dumps({"hooks": []}),
    json.dumps({}),
    json.dumps([]),
    "not json",
]


@pytest.mark.parametrize("index", range(len(CORPUS)))
def test_the_registration_rule_agrees_with_the_record_mode_snippet(tmp_path, index):
    text = CORPUS[index]
    path = tmp_path / "settings.json"
    path.write_text(text)
    ran = subprocess.run([sys.executable, "-", str(path), hook.HOOK_COMMAND],
                         input=_record_snippet().encode("utf-8"), capture_output=True)
    assert ran.returncode in (0, 1), ran.stderr
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    assert hook._registers(data) is (ran.returncode == 0), text


def test_the_census_has_both_outcomes():
    assert len(CORPUS) >= 10
    outcomes = set()
    for text in CORPUS:
        try:
            outcomes.add(hook._registers(json.loads(text)))
        except ValueError:
            outcomes.add(False)
    assert outcomes == {True, False}


# ---------------------------------------------------------------- the launch report


def _hook_candidate(base, adopts):
    return {"reason": "dependency-hook", "by": "word", "cloudVersion": None,
            "advisorVersion": None, "reported": None, "failedCheck": None,
            "observedOn": "2026-10-10", "baseCommit": base, "adoptsHead": adopts}


# the checkout's own readiness reads fixed in every case below; only the launch's own check decides
_NOW_READS_FIXED = {"conditions": {"dependencyHook": True}, "setting": True, "ready": False}


def test_the_still_line_rereads_the_dependency_hook_reason(tmp_path):
    assert "dependency-hook" in launch_report._REREAD_REASONS
    w, bare, with_hook = _hooked(tmp_path)
    (w.repo / "other.txt").write_text("x\n")
    same_inputs = _commit(w.cwd, "other file")
    _lock(w, "v2\n")
    changed = _commit(w.cwd, "lock changed")
    _git(w.repo, "checkout", "-q", "--detach", same_inputs)
    # the checkout's HEAD carries the hook and the lock file as `with_hook` has it
    assert _git(w.repo, "rev-parse", "HEAD") == same_inputs
    assert CS.branch_hook_gap(w.cwd, w.root) is None

    def fixed(base, adopts):
        return launch_report._fixed(_hook_candidate(base, adopts), _NOW_READS_FIXED, w.cwd, w.root)

    # (a) the launch's base lacked the hook and the hook has since been committed on HEAD: fixed,
    # with no adopted head and with an adopted head whose listed inputs match HEAD
    assert fixed(bare, None) is True
    assert fixed(bare, with_hook) is True
    # (b) the adopted head changed a listed input relative to HEAD: the fallback stands even though
    # HEAD carries the hook
    assert fixed(bare, changed) is False
    assert fixed(with_hook, changed) is False
    # (c) HEAD without the hook is not fixed, adopted or not
    _git(w.repo, "checkout", "-q", "--detach", bare)
    assert fixed(with_hook, None) is False
    assert fixed(with_hook, bare) is False


def test_the_fallback_candidate_carries_the_reserved_records_base_and_adopted_commits():
    def records(premise):
        return [{"event": "reserved", "launchId": "a", "premise": premise},
                {"event": "started", "launchId": "a"}]

    launches = {"a": {"started": True, "place": "local", "reservedIndex": 0, "startedTs": 1760000000}}
    call = {"place": "local", "pointedAtCloud": True, "reason": "dependency-hook", "by": "word"}
    got = launch_report._fallbacks(
        records({"placeCall": call, "baseCommit": "b" * 40, "adoptsHead": "c" * 40}), launches)
    assert [(c["baseCommit"], c["adoptsHead"]) for c in got] == [("b" * 40, "c" * 40)]
    for premise in ({"placeCall": call}, {"placeCall": call, "baseCommit": "", "adoptsHead": 7}):
        got = launch_report._fallbacks(records(premise), launches)
        assert [(c["baseCommit"], c["adoptsHead"]) for c in got] == [(None, None)]


def test_the_interface_gains_the_new_condition_and_reason():
    assert cloud_ready.REASON_FOR["dependencyHook"] == "dependency-hook"
    assert "dependency-hook" in launch_place.NOT_READY_CODES
    assert "dependency-hook" in launch_place.REASON_CODES
