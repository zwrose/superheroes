"""Tests for #2009: configure item 19 (the cloud dependency hook), the hook wiring in `set_item`,
the stamp exception, the setup text's record step.

Every fixture project is a real git repository under tmp_path (every git call pins its global and
system configuration away), and every store, home and Claude config directory is under tmp_path too.
No test reads the real home directory or the network, and the hook script is run with an
environment the test builds itself.
"""
import datetime
import json
import os
import re
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
import mode_registry  # noqa: E402
import project_config as PC  # noqa: E402
import store_core  # noqa: E402

_GIT_ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
ORIGIN = "https://github.com/acme/corner-shop.git"
SOURCE = "https://github.com/acme/superheroes.git"
COMMIT = "0123456789abcdef" * 2 + "01234567"
SUBDIR = "plugins/superheroes"
ACCOUNT = "acct-fixture-one"
ENVIRONMENT = "env-fixture-one"
ADVISOR = "1.2.3"
TODAY = datetime.date(2026, 10, 11)
CORE_FACTS = {"verifyCommand": "npm test", "stackTags": ["node"], "threatModel": "single-user",
              "patterns": "- x: a.ts:1"}
MODES = [mode_registry.GLOBAL, mode_registry.IN_REPO]
COMMANDS_SLUG = "cloudSetupCommands"
INPUTS_SLUG = "cloudSetupInputs"
HOOK_SLUG = "cloudDependencyHook"


class World:
    pass


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, env=_GIT_ENV)


def _world(tmp_path, mode):
    w = World()
    w.tmp = tmp_path
    w.repo = tmp_path / "repo"
    w.repo.mkdir()
    _git(w.repo, "init", "-q")
    _git(w.repo, "remote", "add", "origin", ORIGIN)
    w.cwd = str(w.repo)
    w.root = str(tmp_path / "store-root")
    w.home = tmp_path / "home"
    w.home.mkdir()
    w.env = {"HOME": str(w.home), "CLAUDE_CONFIG_DIR": str(tmp_path / "claude-config"),
             "PATH": os.environ.get("PATH", "")}
    remote_key = store_core.derive_identifiers(w.cwd)["remote_hash"]
    mode_registry.write_registry(w.cwd, mode, remote_key, root=w.root)
    done = core_md.write(w.cwd, dict(CORE_FACTS), "confirmed", root=w.root, now="2026-06-26")
    assert done["action"] in ("written", "reused"), done
    w.settings = w.repo / ".claude" / "settings.json"
    w.script = w.repo / hook.SCRIPT_REL.replace("/", os.sep)
    return w


def _set(w, slug, value):
    return PC.set_item(w.cwd, slug, value, root=w.root)


def _set_ok(w, slug, value):
    got = _set(w, slug, value)
    assert got["action"] in ("written", "noop"), got
    return got


def _raw(w, slug):
    return PC.get_item(w.cwd, slug, root=w.root)["raw"]


def _lock(w, name="package-lock.json", text="v1\n"):
    (w.repo / name).write_text(text)


def _compose(w, **kw):
    args = dict(now=1760000000, plugin_source=SOURCE, plugin_commit=COMMIT, plugin_subdir=SUBDIR,
                project_name="Corner Shop", root=w.root, env=w.env,
                source_dir=str(w.tmp / "opt" / "src"), plugin_dir=str(w.tmp / "opt" / "plugin"))
    args.update(kw)
    return CS.compose(w.cwd, **args)


def _stamp(w):
    return cloud_check._placed_stamp(w.cwd, w.root)


def _record(w, stamp):
    got = cloud_setup.record_check(
        w.cwd, root=w.root, account=ACCOUNT, environment=ENVIRONMENT, plugin_version=ADVISOR,
        picks_up_version=False, calibration_stamp=stamp, calibration_date="2026-10-01",
        pass_lapses="2026-12-01", checked_at="2026-10-09")
    assert got["action"] in ("written", "noop"), got


def _calibration_condition(w):
    got = cloud_ready.readiness(w.cwd, account=ACCOUNT, advisor_version=ADVISOR, today=TODAY,
                                root=w.root)
    return got["conditions"]["calibration"]


def _settings(w):
    return json.loads(w.settings.read_text())


def _ours(obj):
    return [h for g in obj.get("hooks", {}).get("SessionStart", []) for h in g["hooks"]
            if hook._is_ours(h)]


def _lose_the_repo_root_for_the_hook(monkeypatch):
    # every other reader of the root still finds it, so only the hook wiring's own lookup fails
    real_root = store_core.repo_root

    def root(cwd, **kw):
        if sys._getframe(1).f_code.co_name == "_plan_dependency_hook":
            raise store_core.RepoRootUnavailable("not a checkout")
        return real_root(cwd, **kw)

    monkeypatch.setattr(store_core, "repo_root", root)


# ---------------------------------------------------------------- the stamp


@pytest.mark.parametrize("mode", MODES)
def test_hook_off_an_input_change_moves_the_stamp_and_the_text_checks_the_inputs(tmp_path, mode):
    # axis: with the hook off, the input files' bytes are in the stamp and the text checks them
    w = _world(tmp_path, mode)
    _lock(w)
    _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    _set_ok(w, HOOK_SLUG, False)
    before = _stamp(w)
    text = _compose(w)["text"]
    assert "check_input package-lock.json" in text
    assert "setup inputs differ from the setup text" in text
    assert "--record" not in text and "dependency hook" not in text
    _lock(w, text="v2\n")
    assert _stamp(w) != before


@pytest.mark.parametrize("mode", MODES)
def test_hook_on_an_input_change_leaves_the_stamp_unchanged(tmp_path, mode):
    # axis: with the hook on, the input files stay out of the stamp
    w = _world(tmp_path, mode)
    _lock(w)
    _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    assert _set_ok(w, HOOK_SLUG, True)["dependencyHook"]["action"] == "written"
    before = _stamp(w)
    text_before = _compose(w)["text"]
    _record(w, before)
    _lock(w, text="v2\n")
    (w.repo / "uv.lock").write_text("new\n")
    assert _stamp(w) == before
    assert _compose(w)["text"] == text_before
    assert _calibration_condition(w) is True
    assert not any(k.startswith(("setup-input/", "setup-input-missing/"))
                   for k in CS.stamped_files(w.cwd, w.root))


@pytest.mark.parametrize("mode", MODES)
def test_turning_the_hook_on_or_off_changes_the_stamp(tmp_path, mode):
    w = _world(tmp_path, mode)
    _lock(w)
    _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    off = _stamp(w)
    _set_ok(w, HOOK_SLUG, True)
    on = _stamp(w)
    assert on != off
    _set_ok(w, HOOK_SLUG, False)
    assert _stamp(w) != on


@pytest.mark.parametrize("mode", MODES)
def test_the_text_leaves_the_input_check_out_and_adds_the_record_line_when_the_hook_is_on(
        tmp_path, mode):
    w = _world(tmp_path, mode)
    _lock(w)
    _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    off = _compose(w)
    assert "check_input" in off["text"] and "--record" not in off["text"]
    assert "dependencyHook" not in off["calibration"]
    _set_ok(w, HOOK_SLUG, True)
    on = _compose(w)
    assert on["action"] == "written", on
    assert "check_input" not in on["text"]
    assert "setup inputs differ" not in on["text"]
    assert "--record" in on["text"]
    assert on["calibration"]["dependencyHook"] is True
    _set_ok(w, HOOK_SLUG, False)
    back = _compose(w)
    assert "check_input" in back["text"] and "--record" not in back["text"]


def test_no_setup_commands_means_items_18_and_19_change_nothing_in_the_inside_mode(tmp_path):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _lock(w)
    unset_files = CS.stamped_files(w.cwd, w.root)
    unset_text = _compose(w, stamp_fn=lambda files: "fixed:stamp")["text"]
    _set_ok(w, INPUTS_SLUG, ["package-lock.json"])
    _set_ok(w, HOOK_SLUG, True)
    assert CS.stamped_files(w.cwd, w.root) == unset_files
    assert _compose(w, stamp_fn=lambda files: "fixed:stamp")["text"] == unset_text
    assert not w.script.exists() and not w.settings.exists()


def test_no_setup_commands_means_items_18_and_19_add_nothing_in_the_outside_mode(tmp_path):
    w = _world(tmp_path, mode_registry.GLOBAL)
    _lock(w)
    before = _stamp(w)
    _set_ok(w, INPUTS_SLUG, ["package-lock.json"])
    _set_ok(w, HOOK_SLUG, True)
    # the placed core carries the stored items, but the stamp's own view leaves them out
    assert _stamp(w) == before
    got = _compose(w)
    assert got["action"] == "written"
    assert "dependencyHook" not in got["calibration"] and "setupCommands" not in got["calibration"]
    assert "--record" not in got["text"] and "dependency hook" not in got["text"]
    assert not w.script.exists() and not w.settings.exists()


def test_item_19_is_read_only_when_commands_are_listed(tmp_path):
    w = _world(tmp_path, mode_registry.IN_REPO)
    core_md.write_project_config_item(w.cwd, HOOK_SLUG, True, root=w.root)
    assert _compose(w)["action"] == "written"
    assert CS._dependency_hook_on(w.cwd, w.root, []) is False
    assert CS._dependency_hook_on(w.cwd, w.root, ["npm ci"]) is True
    core_md.write_project_config_item(w.cwd, HOOK_SLUG, "yes", root=w.root)
    assert CS._dependency_hook_on(w.cwd, w.root, ["npm ci"]) is False


def test_the_registry_carries_item_19():
    by_number = {item["number"]: item for item in PC.ITEMS}
    assert by_number[19] == {"number": 19, "slug": "cloudDependencyHook",
                             "name": "Cloud dependency hook",
                             "home": PC.HOME_PROJECT_CONFIGURATION, "shape": "boolean",
                             "plugin_default": None}
    assert PC.CLOUD_DEPENDENCY_HOOK_SLUG == HOOK_SLUG
    assert PC.REASON_DEPENDENCY_HOOK_UNWRITABLE == "dependency-hook-unwritable"


# ---------------------------------------------------------------- configure keeps the hook files


def _desired(w):
    """What sync's desired state is for the stored items."""
    commands = _raw(w, COMMANDS_SLUG) or []
    inputs = _raw(w, INPUTS_SLUG) or []
    return commands, inputs, _raw(w, HOOK_SLUG) is True


def _assert_files_match_stored(w):
    commands, inputs, enabled = _desired(w)
    if enabled and commands:
        assert w.script.read_text() == hook.script_text(commands, inputs)
        assert len(_ours(_settings(w))) == 1
    else:
        assert not w.script.exists()
        assert not w.settings.exists() or _ours(_settings(w)) == []


@pytest.mark.parametrize("mode", MODES)
def test_configure_writes_rewrites_and_removes_the_hook_files(tmp_path, mode):
    w = _world(tmp_path, mode)
    _lock(w)
    _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    assert not w.script.exists() and not w.settings.exists()
    done = _set_ok(w, HOOK_SLUG, True)
    assert done["dependencyHook"]["action"] == "written"
    assert sorted(done["dependencyHook"]["changed"]) == sorted([hook.SCRIPT_REL, hook.SETTINGS_REL])
    _assert_files_match_stored(w)
    assert _ours(_settings(w)) == [{"type": "command", "command": hook.HOOK_COMMAND,
                                    "timeout": hook.HOOK_TIMEOUT_SECONDS}]
    first = w.script.read_text()
    _set_ok(w, COMMANDS_SLUG, ["npm ci", "make"])
    _assert_files_match_stored(w)
    assert w.script.read_text() != first
    second = w.script.read_text()
    _set_ok(w, INPUTS_SLUG, ["package-lock.json", "uv.lock"])
    _assert_files_match_stored(w)
    assert w.script.read_text() != second
    removed = _set_ok(w, HOOK_SLUG, False)
    assert removed["dependencyHook"]["action"] == "removed"
    _assert_files_match_stored(w)
    assert not w.script.exists() and not w.settings.exists()
    _set_ok(w, HOOK_SLUG, True)
    _assert_files_match_stored(w)
    assert w.script.exists()
    _set_ok(w, COMMANDS_SLUG, [])
    assert not w.script.exists() and not w.settings.exists()
    _assert_files_match_stored(w)


def test_the_first_item_17_set_with_the_hook_on_writes_a_script_that_lists_the_filled_inputs(
        tmp_path):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _lock(w)
    _set_ok(w, HOOK_SLUG, True)
    assert not w.script.exists()
    done = _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    assert done["inputsFilled"] == ["package-lock.json"]
    assert done["dependencyHook"]["action"] == "written"
    assert w.script.read_text() == hook.script_text(["npm ci"], ["package-lock.json"])
    _assert_files_match_stored(w)


def test_a_project_that_never_opted_in_never_has_its_settings_file_read(tmp_path):
    w = _world(tmp_path, mode_registry.IN_REPO)
    w.settings.parent.mkdir(parents=True, exist_ok=True)
    w.settings.write_text("{ this is not json")
    _lock(w)
    for slug, value in ((COMMANDS_SLUG, ["npm ci"]), (INPUTS_SLUG, ["uv.lock"]),
                        (HOOK_SLUG, False), (COMMANDS_SLUG, [])):
        got = _set_ok(w, slug, value)
        assert "dependencyHook" not in got
    assert w.settings.read_text() == "{ this is not json"
    assert not w.script.exists()


def test_a_script_left_behind_by_an_earlier_opt_in_is_swept_by_a_later_set(tmp_path):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    _set_ok(w, HOOK_SLUG, True)
    # the owner turned the setting off by hand-editing the core, leaving the files behind
    core_md.write_project_config_item(w.cwd, HOOK_SLUG, False, root=w.root)
    assert w.script.exists()
    done = _set_ok(w, INPUTS_SLUG, ["uv.lock"])
    assert done["dependencyHook"]["action"] == "removed"
    assert not w.script.exists() and not w.settings.exists()


def test_other_hooks_in_the_settings_file_survive_a_write_and_a_remove(tmp_path):
    w = _world(tmp_path, mode_registry.IN_REPO)
    original = {
        "permissions": {"allow": ["Bash(ls:*)"]},
        "hooks": {
            "SessionStart": [{"matcher": "startup",
                              "hooks": [{"type": "command", "command": "echo hi"}]}],
            "Stop": [{"hooks": [{"type": "command", "command": "echo bye"}]}],
        },
    }
    w.settings.parent.mkdir(parents=True, exist_ok=True)
    w.settings.write_text(json.dumps(original, indent=2) + "\n")
    _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    assert json.loads(w.settings.read_text()) == original
    _set_ok(w, HOOK_SLUG, True)
    written = _settings(w)
    assert len(_ours(written)) == 1
    assert written["permissions"] == original["permissions"]
    assert written["hooks"]["Stop"] == original["hooks"]["Stop"]
    assert written["hooks"]["SessionStart"][0] == original["hooks"]["SessionStart"][0]
    _set_ok(w, HOOK_SLUG, False)
    assert json.loads(w.settings.read_text()) == original
    assert not w.script.exists()


def test_a_refused_sync_refuses_the_set_and_stores_nothing(tmp_path):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    w.settings.parent.mkdir(parents=True, exist_ok=True)
    w.settings.write_text("{ this is not json")
    got = _set(w, HOOK_SLUG, True)
    assert got == {"action": "refused", "reason": "dependency-hook-unwritable",
                   "detail": "settings-unreadable"}
    assert _raw(w, HOOK_SLUG) is None
    assert not w.script.exists()
    assert w.settings.read_text() == "{ this is not json"


def test_an_unresolvable_repo_root_refuses_a_set_that_needs_a_sync_and_stores_nothing(
        tmp_path, monkeypatch):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    _lose_the_repo_root_for_the_hook(monkeypatch)
    got = _set(w, HOOK_SLUG, True)
    assert got == {"action": "refused", "reason": "dependency-hook-unwritable",
                   "detail": "repo-root-unavailable"}
    monkeypatch.undo()
    assert _raw(w, HOOK_SLUG) is None
    # the hook is on for a set that clears the commands, so that set needs a sync too
    _set_ok(w, HOOK_SLUG, True)
    _lose_the_repo_root_for_the_hook(monkeypatch)
    cleared = _set(w, COMMANDS_SLUG, [])
    assert cleared == {"action": "refused", "reason": "dependency-hook-unwritable",
                       "detail": "repo-root-unavailable"}
    monkeypatch.undo()
    assert _raw(w, COMMANDS_SLUG) == ["npm ci"]


def test_an_unresolvable_repo_root_refuses_nothing_for_a_project_that_never_opted_in(
        tmp_path, monkeypatch):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _lock(w)
    _lose_the_repo_root_for_the_hook(monkeypatch)
    done = _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    assert "inputsFilled" not in done and "dependencyHook" not in done
    assert "inputsFillFailed" not in done
    # turning the hook off needs no sync when it was never on
    assert "dependencyHook" not in _set_ok(w, HOOK_SLUG, False)
    monkeypatch.undo()
    assert _raw(w, COMMANDS_SLUG) == ["npm ci"]
    assert _raw(w, INPUTS_SLUG) is None
    assert _raw(w, HOOK_SLUG) is False


def test_a_failing_config_write_after_a_successful_enable_sync_rolls_the_files_back(
        tmp_path, monkeypatch):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    real = core_md.write_project_config_item

    def failing(cwd, slug, value, root=None):
        if slug == HOOK_SLUG:
            return {"action": "refused", "reason": "x"}
        return real(cwd, slug, value, root=root)

    monkeypatch.setattr(core_md, "write_project_config_item", failing)
    got = _set(w, HOOK_SLUG, True)
    assert got["action"] == "refused" and got["reason"] == "x"
    assert got["dependencyHookResynced"]["changed"]
    assert not w.script.exists() and not w.settings.exists()
    monkeypatch.undo()
    assert _raw(w, HOOK_SLUG) is None
    _assert_files_match_stored(w)


def test_a_failing_write_never_undoes_another_sets_stored_update(tmp_path, monkeypatch):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _lock(w)
    _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    _set_ok(w, HOOK_SLUG, True)
    real = core_md.write_project_config_item
    state = {"done": False}

    def interleaved(cwd, slug, value, root=None):
        if slug == INPUTS_SLUG and not state["done"]:
            state["done"] = True
            # set B lands whole (store and files) between A's sync and A's write
            assert real(cwd, COMMANDS_SLUG, ["make"], root=root)["action"] in ("written", "noop")
            assert hook.sync(w.cwd, ["make"], _raw(w, INPUTS_SLUG), True)["action"] == "written"
            return {"action": "refused", "reason": "x"}
        return real(cwd, slug, value, root=root)

    monkeypatch.setattr(core_md, "write_project_config_item", interleaved)
    got = _set(w, INPUTS_SLUG, ["uv.lock"])
    assert got["action"] == "refused" and got["reason"] == "x"
    monkeypatch.undo()
    assert _raw(w, COMMANDS_SLUG) == ["make"]
    assert w.script.read_text() == hook.script_text(["make"], _raw(w, INPUTS_SLUG))
    _assert_files_match_stored(w)


def test_a_failing_write_with_a_stored_credential_removes_the_files_and_writes_no_script(
        tmp_path, monkeypatch):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    _set_ok(w, HOOK_SLUG, True)
    secret = "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz0123456789 npm ci"
    real = core_md.write_project_config_item

    def interleaved(cwd, slug, value, root=None):
        if slug == INPUTS_SLUG:
            # a hand-edit lands past the validator, then A's own write fails
            assert real(cwd, COMMANDS_SLUG, [secret], root=root)["action"] in ("written", "noop")
            return {"action": "refused", "reason": "x"}
        return real(cwd, slug, value, root=root)

    monkeypatch.setattr(core_md, "write_project_config_item", interleaved)
    got = _set(w, INPUTS_SLUG, ["uv.lock"])
    monkeypatch.undo()
    assert got["reason"] == "x"
    assert got["dependencyHookRemovedInvalid"] == "setup-command-secret-shaped"
    assert not w.script.exists() and not w.settings.exists()


def test_a_failed_readback_after_a_held_write_keeps_the_synced_files(tmp_path, monkeypatch):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    monkeypatch.setattr(PC, "get_item", lambda *a, **k: {"action": "ok", "raw": None})
    got = _set(w, HOOK_SLUG, True)
    assert got["action"] == "refused" and got["reason"] == PC.REASON_SET_MISMATCH
    assert got["dependencyHook"]["changed"]
    assert w.script.exists() and w.settings.exists()
    monkeypatch.undo()
    assert _raw(w, HOOK_SLUG) is True
    _assert_files_match_stored(w)


def test_a_failing_fill_write_reports_inputs_fill_failed_and_the_files_match_what_is_stored(
        tmp_path, monkeypatch):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _lock(w)
    real = core_md.write_project_config_item

    def failing(cwd, slug, value, root=None):
        if slug == INPUTS_SLUG:
            return {"action": "refused", "reason": "y"}
        return real(cwd, slug, value, root=root)

    monkeypatch.setattr(core_md, "write_project_config_item", failing)
    _set_ok(w, HOOK_SLUG, True)
    done = _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    assert done["inputsFillFailed"] == "y" and "inputsFilled" not in done
    monkeypatch.undo()
    assert _raw(w, COMMANDS_SLUG) == ["npm ci"] and _raw(w, INPUTS_SLUG) is None
    assert w.script.read_text() == hook.script_text(["npm ci"], [])
    _assert_files_match_stored(w)


# ---------------------------------------------------------------- the record step


@pytest.mark.parametrize("mode", MODES)
def test_the_setup_text_records_the_hook_with_exactly_the_fingerprint_the_script_carries(
        tmp_path, mode):
    w = _world(tmp_path, mode)
    _lock(w)
    commands = ["npm ci", "make 'build all'"]
    _set_ok(w, COMMANDS_SLUG, commands)
    off = _compose(w)
    assert off["action"] == "written"
    assert "--record" not in off["text"] and "dependency hook" not in off["text"]
    assert "dependencyHook" not in off["calibration"]
    _set_ok(w, HOOK_SLUG, True)
    inputs = _raw(w, INPUTS_SLUG)
    assert inputs == ["package-lock.json"]
    fp = hook.fingerprint(commands, inputs)
    assert len(fp) == 64
    on = _compose(w)
    assert on["action"] == "written", on
    text = on["text"]
    line = "bash %s --record %s" % (hook.SCRIPT_REL, fp)
    assert text.count(line) == 1
    assert "FINGERPRINT=%s" % fp in w.script.read_text()
    assert on["calibration"]["dependencyHook"] is True
    assert CS._scan(text) is None
    for echo in ("dependency hook recorded", "dependency hook record FAILED",
                 "dependency hook not in the clone: commit and push it"):
        assert echo in text
    # the step sits inside the loop's block, after the commands and before the stamp is published
    lines = text.splitlines()
    at = next(i for i, ln in enumerate(lines) if "--record" in ln)
    assert lines.index("  done") < at < next(i for i, ln in enumerate(lines)
                                             if "setup stamp withheld" in ln)
    assert lines.index(CS.TOOL_STEPS_MARKER) > at
    # turning the hook off takes the step out again
    _set_ok(w, HOOK_SLUG, False)
    assert "--record" not in _compose(w)["text"]


def _setup_block(w, text):
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("# Run the project's own"))
    end = next(i for i, ln in enumerate(lines) if ln == "setup_rc=$?")
    body = "\n".join(lines[start:end + 1])
    count = re.search(r'"\$wrote" = (\d+)', body)
    return "\n".join(['LOG="%s"' % (w.tmp / "log.txt"), 'CLONE="repo"',
                      'wrote=%s' % (count.group(1) if count else "0"),
                      'DEST="%s"' % (w.tmp / "dest"), 'mkdir -p "$DEST"', *lines[start:end + 1],
                      'cat "$LOG"; exit "$setup_rc"'])


def _run_block(w, block):
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(w.home),
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    return subprocess.run(["bash", "-c", block], cwd=str(w.repo), env=env, capture_output=True,
                          text=True, timeout=60)


def test_the_record_step_runs_the_clones_script_and_publishes_the_stamp(tmp_path):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _lock(w)
    _set_ok(w, COMMANDS_SLUG, ["true"])
    _set_ok(w, HOOK_SLUG, True)
    block = _setup_block(w, _compose(w)["text"])
    # the clone holds the script: it is run in record mode and the result is logged
    proc = _run_block(w, block)
    assert proc.returncode == 0, proc.stderr
    assert "dependency hook recorded" in proc.stdout
    assert "record FAILED" not in proc.stdout
    assert os.path.isfile(str(w.tmp / "dest" / CS.STAMP_FILE))
    state = subprocess.run(["git", "-C", str(w.repo), "rev-parse", "--git-path", hook.HASH_NAME],
                           capture_output=True, text=True, env=_GIT_ENV).stdout.strip()
    assert os.path.isfile(os.path.join(str(w.repo), state))


def test_a_missing_hook_script_withholds_the_stamp_and_fails_the_setup(tmp_path):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _lock(w)
    _set_ok(w, COMMANDS_SLUG, ["true"])
    _set_ok(w, HOOK_SLUG, True)
    block = _setup_block(w, _compose(w)["text"])
    os.remove(w.script)
    proc = _run_block(w, block)
    assert proc.returncode != 0
    assert "dependency hook not in the clone: commit and push it" in proc.stdout
    assert "setup stamp withheld" in proc.stdout
    assert not os.path.exists(str(w.tmp / "dest" / CS.STAMP_FILE))


def _registered_settings(w):
    return json.loads(w.settings.read_text())


@pytest.mark.parametrize("variant", [
    "absent", "other-event-only", "disabled", "empty-session-start", "permission-only", "not-json",
    "matcher-resume-only", "matcher-invalid-regex", "other-script-path", "ours-inside-longer-command"])
def test_an_unregistered_hook_script_withholds_the_stamp_and_fails_the_setup(tmp_path, variant):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _lock(w)
    _set_ok(w, COMMANDS_SLUG, ["true"])
    _set_ok(w, HOOK_SLUG, True)
    block = _setup_block(w, _compose(w)["text"])
    # the script reached the clone but the settings file does not register it as a SessionStart hook
    good = _registered_settings(w)
    entry = good["hooks"]["SessionStart"]
    if variant == "absent":
        os.remove(w.settings)
    elif variant == "other-event-only":
        w.settings.write_text(json.dumps({"hooks": {"Stop": entry}}))
    elif variant == "disabled":
        w.settings.write_text(json.dumps({**good, "disableAllHooks": True}))
    elif variant == "empty-session-start":
        w.settings.write_text(json.dumps({"hooks": {"SessionStart": []}}))
    elif variant == "permission-only":
        w.settings.write_text(json.dumps({
            "hooks": {"SessionStart": []},
            "permissions": {"allow": ["Bash(bash %s)" % hook.SCRIPT_REL]}}))
    elif variant in ("matcher-resume-only", "matcher-invalid-regex"):
        matcher = "resume" if variant == "matcher-resume-only" else "start(up"
        w.settings.write_text(json.dumps({"hooks": {"SessionStart": [{**e, "matcher": matcher} for e in entry]}}))
    elif variant in ("other-script-path", "ours-inside-longer-command"):
        # axis: the registered command must be exactly ours, not another script or a longer command holding ours
        other = ('bash "$CLAUDE_PROJECT_DIR/.claude/hooks/other.sh"' if variant == "other-script-path"
                 else "echo hi && " + hook.HOOK_COMMAND)
        w.settings.write_text(json.dumps({"hooks": {"SessionStart": [
            {"hooks": [{"type": "command", "command": other}]}]}}))
    else:
        w.settings.write_text("{not json")
    proc = _run_block(w, block)
    assert proc.returncode != 0
    assert ("dependency hook not recorded: not registered as a SessionStart hook in "
            ".claude/settings.json") in proc.stdout
    assert "dependency hook record FAILED" in proc.stdout
    assert "dependency hook recorded" not in proc.stdout
    assert "setup stamp withheld" in proc.stdout
    assert not os.path.exists(str(w.tmp / "dest" / CS.STAMP_FILE))


@pytest.mark.parametrize("matcher", [None, "", "*", "startup|resume", "startup"])
def test_a_hook_group_whose_matcher_covers_startup_is_recorded(tmp_path, matcher):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _lock(w)
    _set_ok(w, COMMANDS_SLUG, ["true"])
    _set_ok(w, HOOK_SLUG, True)
    block = _setup_block(w, _compose(w)["text"])
    good = _registered_settings(w)
    if matcher is not None:
        good["hooks"]["SessionStart"] = [{**e, "matcher": matcher} for e in good["hooks"]["SessionStart"]]
    w.settings.write_text(json.dumps(good))
    proc = _run_block(w, block)
    assert proc.returncode == 0, proc.stdout
    assert "dependency hook recorded" in proc.stdout


def test_a_registered_hook_script_is_recorded_and_the_stamp_published(tmp_path):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _lock(w)
    _set_ok(w, COMMANDS_SLUG, ["true"])
    _set_ok(w, HOOK_SLUG, True)
    block = _setup_block(w, _compose(w)["text"])
    proc = _run_block(w, block)
    assert proc.returncode == 0, proc.stdout
    assert "dependency hook recorded" in proc.stdout
    assert os.path.exists(str(w.tmp / "dest" / CS.STAMP_FILE))


def test_the_record_step_failure_withholds_the_stamp_and_fails_the_setup(tmp_path):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _lock(w)
    _set_ok(w, COMMANDS_SLUG, ["true"])
    _set_ok(w, HOOK_SLUG, True)
    block = _setup_block(w, _compose(w)["text"])
    # the committed script lists different inputs from the ones the text was written for
    assert hook.sync(str(w.repo), ["true"], ["uv.lock"], True)["action"] == "written"
    proc = _run_block(w, block)
    assert proc.returncode != 0
    assert "dependency hook record FAILED" in proc.stdout
    assert not os.path.exists(str(w.tmp / "dest" / CS.STAMP_FILE))
    assert "dependency hook recorded" not in proc.stdout
    state = subprocess.run(["git", "-C", str(w.repo), "rev-parse", "--git-path", hook.HASH_NAME],
                           capture_output=True, text=True, env=_GIT_ENV).stdout.strip()
    assert not os.path.exists(os.path.join(str(w.repo), state))


def test_the_record_step_is_skipped_when_a_command_fails(tmp_path):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _lock(w)
    _set_ok(w, COMMANDS_SLUG, ["false"])
    _set_ok(w, HOOK_SLUG, True)
    proc = _run_block(w, _setup_block(w, _compose(w)["text"]))
    assert proc.returncode != 0
    assert "setup command 1 FAILED" in proc.stdout
    assert "dependency hook" not in proc.stdout


@pytest.mark.parametrize("mode", MODES)
def test_hook_on_a_changed_item_18_moves_the_stamp(tmp_path, mode):
    # axis: the input list and the hook flag stay in the stamp when the hook is on
    w = _world(tmp_path, mode)
    _lock(w)
    _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    _set_ok(w, INPUTS_SLUG, ["package-lock.json"])
    _set_ok(w, HOOK_SLUG, True)
    before = _stamp(w)
    _set_ok(w, INPUTS_SLUG, ["uv.lock"])
    assert _stamp(w) != before


@pytest.mark.parametrize("mode", MODES)
def test_enabling_the_hook_without_a_stored_item_18_moves_the_stamp(tmp_path, mode):
    w = _world(tmp_path, mode)
    # stored straight through the core writer: the set path would fill item 18 with `[]`
    stored = core_md.write_project_config_item(w.cwd, COMMANDS_SLUG, ["npm ci"], root=w.root)
    assert stored["action"] in ("written", "noop"), stored
    assert _raw(w, INPUTS_SLUG) is None
    off = _stamp(w)
    _set_ok(w, HOOK_SLUG, True)
    assert _raw(w, INPUTS_SLUG) is None
    assert _stamp(w) != off


def test_enabling_the_hook_refuses_a_stored_secret_shaped_command_and_writes_nothing(tmp_path):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    # a hand-edit of the local calibration, past the item 17 validator
    facts = core_md.read(w.cwd, w.root)
    assert facts is not None
    got = core_md.write_project_config_item(
        w.cwd, COMMANDS_SLUG, ["OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz0123456789 npm ci"],
        root=w.root)
    assert got["action"] in ("written", "noop"), got
    refused = _set(w, HOOK_SLUG, True)
    assert refused["action"] == "refused"
    assert refused["reason"] == "setup-command-secret-shaped"
    assert _raw(w, HOOK_SLUG) is None
    assert not w.script.exists()
    assert not w.settings.exists()


def test_a_refused_sync_puts_back_what_it_already_changed(tmp_path, monkeypatch):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    assert _set_ok(w, HOOK_SLUG, True)["dependencyHook"]["action"] == "written"
    script_before = w.script.read_bytes()
    settings_before = w.settings.read_bytes()
    real_remove = os.remove

    def remove(path, *a, **kw):
        if str(path) == str(w.script):
            raise PermissionError("denied")
        return real_remove(path, *a, **kw)

    monkeypatch.setattr(os, "remove", remove)
    got = _set(w, HOOK_SLUG, False)
    monkeypatch.undo()
    assert got["action"] == "refused"
    assert got["reason"] == "dependency-hook-unwritable"
    assert _raw(w, HOOK_SLUG) is True
    assert w.script.read_bytes() == script_before
    assert w.settings.read_bytes() == settings_before


def test_a_concurrent_item_17_set_landing_between_the_sync_and_the_write_leaves_files_matching_stored(
        tmp_path, monkeypatch):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    _set_ok(w, INPUTS_SLUG, ["package-lock.json"])
    _set_ok(w, HOOK_SLUG, True)
    real = core_md.write_project_config_item
    landed = []

    def racing(cwd, slug, value, root=None):
        if slug == INPUTS_SLUG and not landed:
            landed.append(True)
            assert real(cwd, COMMANDS_SLUG, ["make"], root=root)["action"] in ("written", "noop")
        return real(cwd, slug, value, root=root)

    monkeypatch.setattr(core_md, "write_project_config_item", racing)
    got = _set_ok(w, INPUTS_SLUG, ["uv.lock"])
    monkeypatch.undo()
    assert landed
    assert got["dependencyHookResynced"]["action"] in ("written", "noop")
    assert _raw(w, COMMANDS_SLUG) == ["make"] and _raw(w, INPUTS_SLUG) == ["uv.lock"]
    assert w.script.read_text() == hook.script_text(["make"], ["uv.lock"])
    _assert_files_match_stored(w)


def test_a_partial_sync_failure_recovers_to_the_stored_items_another_set_just_landed(
        tmp_path, monkeypatch):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    assert _set_ok(w, HOOK_SLUG, True)["dependencyHook"]["action"] == "written"
    real_remove = os.remove
    real_write = core_md.write_project_config_item
    landed = []

    def remove(path, *a, **kw):
        if str(path) == str(w.script):
            if not landed:
                landed.append(True)
                # another set's stored update lands while this disable is syncing
                assert real_write(w.cwd, COMMANDS_SLUG, ["make"], root=w.root)["action"] in (
                    "written", "noop")
            raise PermissionError("denied")
        return real_remove(path, *a, **kw)

    monkeypatch.setattr(os, "remove", remove)
    got = _set(w, HOOK_SLUG, False)
    monkeypatch.undo()
    assert landed
    assert got["action"] == "refused"
    assert got["reason"] == "dependency-hook-unwritable"
    assert _raw(w, COMMANDS_SLUG) == ["make"] and _raw(w, HOOK_SLUG) is True
    assert w.script.read_text() == hook.script_text(["make"], _raw(w, INPUTS_SLUG) or [])
    _assert_files_match_stored(w)


def test_a_failed_fill_write_names_every_path_the_first_sync_and_the_recovery_changed(
        tmp_path, monkeypatch):
    # axis: the result names the first sync's paths beside the recovery's when the fill write fails
    w = _world(tmp_path, mode_registry.IN_REPO)
    _lock(w)
    real = core_md.write_project_config_item

    def failing(cwd, slug, value, root=None):
        if slug == INPUTS_SLUG:
            return {"action": "refused", "reason": "y"}
        return real(cwd, slug, value, root=root)

    monkeypatch.setattr(core_md, "write_project_config_item", failing)
    _set_ok(w, HOOK_SLUG, True)
    done = _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    monkeypatch.undo()
    assert done["inputsFillFailed"] == "y"
    # the first sync wrote script and settings; the recovery rewrote only the script
    assert done["dependencyHook"]["changed"] == sorted([hook.SCRIPT_REL, hook.SETTINGS_REL])
    _assert_files_match_stored(w)


def test_a_fill_readback_mismatch_names_every_path_the_first_sync_changed(tmp_path, monkeypatch):
    # axis: a fill whose read-back mismatches keeps the first sync's paths in the result
    w = _world(tmp_path, mode_registry.IN_REPO)
    _lock(w)
    _set_ok(w, HOOK_SLUG, True)
    real_get = PC.get_item

    def get_item(cwd, slug, root=None):
        if slug == INPUTS_SLUG:
            return {"action": "ok", "raw": ["somewhere-else.lock"]}
        return real_get(cwd, slug, root=root)

    monkeypatch.setattr(PC, "get_item", get_item)
    done = _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    monkeypatch.undo()
    assert done["inputsFillFailed"] == PC.REASON_SET_MISMATCH and "inputsFilled" not in done
    assert done["dependencyHook"]["changed"] == sorted([hook.SCRIPT_REL, hook.SETTINGS_REL])
    assert _raw(w, INPUTS_SLUG) == ["package-lock.json"]
    _assert_files_match_stored(w)


def test_sync_rewrites_our_hook_out_of_a_group_whose_matcher_excludes_startup(tmp_path):
    # axis: an already-present hook counts as in place only when its group runs at startup
    w = _world(tmp_path, mode_registry.IN_REPO)
    _lock(w)
    _set_ok(w, COMMANDS_SLUG, ["true"])
    _set_ok(w, HOOK_SLUG, True)
    block = _setup_block(w, _compose(w)["text"])
    other = {"type": "command", "command": "echo hi"}
    good = _settings(w)
    good["hooks"]["SessionStart"] = [
        {"matcher": "resume", "hooks": [other, *good["hooks"]["SessionStart"][0]["hooks"]]}]
    w.settings.write_text(json.dumps(good))
    assert _run_block(w, block).returncode != 0
    synced = hook.sync(str(w.repo), ["true"], _raw(w, INPUTS_SLUG) or [], True)
    assert synced == {"action": "written", "reason": None, "changed": [hook.SETTINGS_REL]}
    groups = _settings(w)["hooks"]["SessionStart"]
    assert groups[0] == {"matcher": "resume", "hooks": [other]}
    assert len(_ours(_settings(w))) == 1
    proc = _run_block(w, block)
    assert proc.returncode == 0, proc.stdout
    assert "dependency hook recorded" in proc.stdout
    # a group that runs at startup is left as it is
    assert hook.sync(str(w.repo), ["true"], _raw(w, INPUTS_SLUG) or [], True)["action"] == "noop"


class _Killed(BaseException):
    """Stands in for the process being killed: nothing in the code under test may catch it."""


def _never_on_with_the_files_gone(w):
    commands, _inputs, enabled = _desired(w)
    if enabled and commands:
        assert w.script.exists() and w.settings.exists() and len(_ours(_settings(w))) == 1


@pytest.mark.parametrize("slug,value", [(HOOK_SLUG, False), (COMMANDS_SLUG, [])])
def test_a_kill_after_the_config_write_of_a_removal_leaves_no_on_config_with_the_files_gone(
        tmp_path, monkeypatch, slug, value):
    # axis: a set that removes the hook writes the config before the files, so a kill between them is safe
    w = _world(tmp_path, mode_registry.IN_REPO)
    _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    _set_ok(w, HOOK_SLUG, True)

    def killed(*a, **k):
        raise _Killed()

    monkeypatch.setattr(hook, "sync", killed)
    with pytest.raises(_Killed):
        _set(w, slug, value)
    monkeypatch.undo()
    assert _raw(w, slug) == value
    assert w.script.exists() and len(_ours(_settings(w))) == 1
    _never_on_with_the_files_gone(w)


@pytest.mark.parametrize("slug", [HOOK_SLUG, COMMANDS_SLUG])
def test_a_kill_at_the_file_sync_of_a_write_leaves_no_on_config_with_the_files_gone(
        tmp_path, monkeypatch, slug):
    # axis: a set that writes the hook writes the files before the config, so a kill at the file step is safe
    w = _world(tmp_path, mode_registry.IN_REPO)
    if slug == HOOK_SLUG:
        _set_ok(w, COMMANDS_SLUG, ["npm ci"])
        value = True
    else:
        _set_ok(w, HOOK_SLUG, True)
        value = ["npm ci"]

    def killed(*a, **k):
        raise _Killed()

    monkeypatch.setattr(hook, "sync", killed)
    with pytest.raises(_Killed):
        _set(w, slug, value)
    monkeypatch.undo()
    assert _raw(w, slug) != value
    _never_on_with_the_files_gone(w)


@pytest.mark.parametrize("slug", [HOOK_SLUG, COMMANDS_SLUG])
def test_a_kill_after_the_file_sync_of_a_write_leaves_no_on_config_with_the_files_gone(
        tmp_path, monkeypatch, slug):
    # axis: a set that writes the hook writes the files before the config, so a kill between them is safe
    w = _world(tmp_path, mode_registry.IN_REPO)
    if slug == HOOK_SLUG:
        _set_ok(w, COMMANDS_SLUG, ["npm ci"])
        value = True
    else:
        _set_ok(w, HOOK_SLUG, True)
        value = ["npm ci"]
    real = core_md.write_project_config_item

    def killed(cwd, key, val, root=None):
        if key == slug:
            raise _Killed()
        return real(cwd, key, val, root=root)

    monkeypatch.setattr(core_md, "write_project_config_item", killed)
    with pytest.raises(_Killed):
        _set(w, slug, value)
    monkeypatch.undo()
    assert w.script.exists() and len(_ours(_settings(w))) == 1
    assert _raw(w, slug) != value
    _never_on_with_the_files_gone(w)


@pytest.mark.parametrize("matcher", ["(?i)startup", "(?P<n>startup)", r"\Astartup\Z", "start++up", "^startup$",
                                     "(startup)", "start.*", "(?:startup|resume)"])
def test_a_python_only_matcher_is_not_a_startup_group(matcher):
    # axis: Claude evaluates matchers as JavaScript regexes; Python-only syntax is unusable
    assert hook._group_starts({"matcher": matcher}) is False


@pytest.mark.parametrize("matcher", ["startup", "startup|resume", "resume|startup", "a_b-c|startup"])
def test_a_plain_word_list_matcher_still_starts(matcher):
    assert hook._group_starts({"matcher": matcher}) is True


@pytest.mark.parametrize("password", ['"$PIP_PASS"', "'$PIP_PASS'", '"${PIP_PASS}"', "$PIP_PASS"])
def test_a_quoted_environment_reference_url_password_is_allowed(password):
    cmd = "pip install --index-url https://builder:" + password + "@packages.example/simple demo"
    assert PC._validate_command_list([cmd]) is None or "secret" not in str(PC._validate_command_list([cmd]))
    assert CS._SECRET_SHAPES  # scanner present
    assert not [n for n, p in CS._SECRET_SHAPES if n == "url credential" and p.search(cmd)]


@pytest.mark.parametrize("password", ['"hunter2"', "'hunter2'", '""'])
def test_a_quoted_literal_url_password_is_refused(password):
    cmd = "pip install --index-url https://builder:" + password + "@packages.example/simple demo"
    assert [n for n, p in CS._SECRET_SHAPES if n == "url credential" and p.search(cmd)]


def test_only_invocations_of_the_managed_script_are_ours():
    # axis: a command that merely mentions the script path is not the managed hook.
    from cloud_dependency_hook import HOOK_COMMAND, SCRIPT_REL, _is_ours
    assert _is_ours({"command": HOOK_COMMAND})
    assert _is_ours({"command": "bash " + SCRIPT_REL})
    assert not _is_ours({"command": "sha256sum " + SCRIPT_REL + ".backup"})
    assert not _is_ours({"command": "cat " + SCRIPT_REL})
    assert not _is_ours({"command": 'bash "$CLAUDE_PROJECT_DIR/' + SCRIPT_REL + '.backup"'})


def test_an_existing_non_file_input_is_refused_not_hashed_as_missing(tmp_path):
    # axis: a directory (or other non-regular input) is never recorded as a missing file
    w = _world(tmp_path, mode_registry.IN_REPO)
    (w.repo / "plugins").mkdir()
    script = w.script
    script.parent.mkdir(parents=True)
    text = hook.script_text(["true"], ["plugins"])
    script.write_text(text)
    fingerprint = re.search(r"^FINGERPRINT=(\S+)$", text, re.M).group(1).strip("'")
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(w.home),
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    proc = subprocess.run(["bash", str(script), "--record", fingerprint], cwd=str(w.repo), env=env,
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert proc.stdout.strip() == (
        "superheroes: dependency hook skipped: an input could not be read")
    state = subprocess.run(["git", "-C", str(w.repo), "rev-parse", "--git-path", hook.HASH_NAME],
                           capture_output=True, text=True, env=_GIT_ENV).stdout.strip()
    assert not os.path.exists(os.path.join(str(w.repo), state))


def test_a_registry_url_with_a_port_beside_a_scoped_package_is_not_a_url_credential(tmp_path):
    # axis: user-info matching stays inside one shell word
    w = _world(tmp_path, mode_registry.GLOBAL)
    command = "npm install --registry https://registry.example.invalid:8443 @acme/widget"
    done = _set(w, COMMANDS_SLUG, [command])
    assert done["action"] in ("written", "noop"), done
