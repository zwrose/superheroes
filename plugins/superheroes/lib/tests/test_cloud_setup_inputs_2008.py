"""Tests for configure item 18 (the files the cloud setup depends on): the registry entry, the
fill from the repository root's lockfiles, the input files in the setup stamp, and `detect_inputs`.

Every fixture project is a real git repository under tmp_path (every git call pins its global and
system configuration away), and every store, home and Claude config directory is under tmp_path too.
No test reads the real home directory or the network.
"""
import datetime
import io
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_check  # noqa: E402
import cloud_ready  # noqa: E402
import cloud_setup  # noqa: E402
import cloud_setup_text as CS  # noqa: E402
import core_md  # noqa: E402
import mode_registry  # noqa: E402
import project_config as PC  # noqa: E402
import store_core  # noqa: E402

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


class World:
    pass


def _git(cwd, *args):
    # Built per call from the current (fixture-sanitized) environment, never a collection-time
    # snapshot: an inherited GIT_DIR would otherwise override `git -C`.
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, env=env)


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


# ---------------------------------------------------------------- the stamp


@pytest.mark.parametrize("mode", MODES)
def test_an_input_change_moves_the_stamp_and_the_cloud_check_reports_it_stale(tmp_path, mode):
    # axis: the input files' bytes are in the stamp
    w = _world(tmp_path, mode)
    _lock(w)
    done = _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    assert done["inputsFilled"] == ["package-lock.json"]
    before = _compose(w)["calibration"]["stamp"]
    assert before == _stamp(w)
    _record(w, before)
    assert _calibration_condition(w) is True
    _lock(w, text="v2\n")
    after = _compose(w)["calibration"]["stamp"]
    assert after == _stamp(w) and after != before
    assert _calibration_condition(w) is False
    _lock(w, text="v1\n")
    assert _compose(w)["calibration"]["stamp"] == before
    assert _stamp(w) == before and _calibration_condition(w) is True


@pytest.mark.parametrize("mode", MODES)
def test_deleting_an_input_moves_the_stamp_and_compose_still_writes(tmp_path, mode):
    w = _world(tmp_path, mode)
    _lock(w)
    _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    before = _stamp(w)
    os.remove(w.repo / "package-lock.json")
    assert _stamp(w) != before
    files = CS.stamped_files(w.cwd, w.root)
    assert files["setup-input-missing/package-lock.json"] == b""
    assert "setup-input/package-lock.json" not in files
    assert _compose(w)["action"] == "written"


@pytest.mark.parametrize("mode", MODES)
def test_an_input_that_is_a_directory_refuses_setup_inputs_unreadable(tmp_path, mode):
    w = _world(tmp_path, mode)
    _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    _set_ok(w, INPUTS_SLUG, ["vendor"])
    (w.repo / "vendor").mkdir()
    got = _compose(w)
    assert got["action"] == "refused" and got["reason"] == "setup-inputs-unreadable", got
    assert "text" not in got


@pytest.mark.parametrize("mode", MODES)
def test_a_stored_input_list_that_is_malformed_refuses_setup_inputs_malformed(tmp_path, mode):
    w = _world(tmp_path, mode)
    core_md.write_project_config_item(w.cwd, COMMANDS_SLUG, ["npm ci"], root=w.root)
    core_md.write_project_config_item(w.cwd, INPUTS_SLUG, ["/etc/passwd"], root=w.root)
    got = _compose(w)
    assert got["action"] == "refused" and got["reason"] == "setup-inputs-malformed", got


@pytest.mark.parametrize("mode", MODES)
def test_inputs_not_stored_at_all_stay_out_of_the_stamp(tmp_path, mode):
    w = _world(tmp_path, mode)
    _lock(w)
    core_md.write_project_config_item(w.cwd, COMMANDS_SLUG, ["npm ci"], root=w.root)
    before = _stamp(w)
    _lock(w, text="v2\n")
    assert _stamp(w) == before
    assert not any(k.startswith("setup-input") for k in CS.stamped_files(w.cwd, w.root))


def test_no_setup_commands_means_item_18_changes_nothing_in_the_inside_mode(tmp_path):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _lock(w)
    unset_files = CS.stamped_files(w.cwd, w.root)
    unset_text = _compose(w, stamp_fn=lambda files: "fixed:stamp")["text"]
    _set_ok(w, INPUTS_SLUG, ["package-lock.json"])
    assert CS.stamped_files(w.cwd, w.root) == unset_files
    assert _compose(w, stamp_fn=lambda files: "fixed:stamp")["text"] == unset_text


def test_no_setup_commands_means_item_18_adds_nothing_in_the_outside_mode(tmp_path):
    w = _world(tmp_path, mode_registry.GLOBAL)
    _lock(w)
    before = _stamp(w)
    assert before in _compose(w)["text"]
    _record(w, before)
    # the placed core carries the stored items, so only the stamp's own view is compared
    _set_ok(w, INPUTS_SLUG, ["package-lock.json"])
    assert _stamp(w) == before
    # the placed core carries the stored item, but the stamp the text publishes is unchanged
    got = _compose(w)
    assert before in got["text"] and got["calibration"]["stamp"] == before
    assert _calibration_condition(w) is True
    assert got["action"] == "written"
    assert "setupCommands" not in got["calibration"]


def test_a_malformed_item_18_is_not_read_without_setup_commands(tmp_path):
    w = _world(tmp_path, mode_registry.IN_REPO)
    core_md.write_project_config_item(w.cwd, INPUTS_SLUG, ["/etc/passwd"], root=w.root)
    assert _compose(w)["action"] == "written"


# ---------------------------------------------------------------- item 18


@pytest.mark.parametrize("mode", MODES)
def test_item_17_fills_item_18_from_root_lockfiles_and_a_later_set_keeps_an_edited_list(
        tmp_path, mode):
    w = _world(tmp_path, mode)
    _lock(w)
    _lock(w, "requirements.txt", "flask\n")
    _lock(w, "notes.txt", "not a lockfile\n")
    done = _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    assert done["inputsFilled"] == ["package-lock.json", "requirements.txt"]
    assert _raw(w, INPUTS_SLUG) == ["package-lock.json", "requirements.txt"]
    _set_ok(w, INPUTS_SLUG, ["package-lock.json"])
    later = _set_ok(w, COMMANDS_SLUG, ["npm ci", "make"])
    assert "inputsFilled" not in later
    assert _raw(w, INPUTS_SLUG) == ["package-lock.json"]
    # a list stored as empty is stored, so it is not filled either
    _set_ok(w, INPUTS_SLUG, [])
    assert "inputsFilled" not in _set_ok(w, COMMANDS_SLUG, ["make"])
    assert _raw(w, INPUTS_SLUG) == []


def test_an_empty_item_17_fills_nothing(tmp_path):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _lock(w)
    assert "inputsFilled" not in _set_ok(w, COMMANDS_SLUG, [])
    assert _raw(w, INPUTS_SLUG) is None


def test_a_non_empty_item_17_with_no_lockfiles_stores_an_empty_item_18(tmp_path):
    w = _world(tmp_path, mode_registry.IN_REPO)
    done = _set_ok(w, COMMANDS_SLUG, ["make"])
    assert done["inputsFilled"] == []
    assert _raw(w, INPUTS_SLUG) == []


def _lose_the_repo_root_for_the_fill(monkeypatch):
    # every other reader of the root still finds it, so only the fill's own lookup fails
    real_root = store_core.repo_root

    def root(cwd, **kw):
        if sys._getframe(1).f_code.co_name == "_fill_setup_inputs":
            raise store_core.RepoRootUnavailable("not a checkout")
        return real_root(cwd, **kw)

    monkeypatch.setattr(store_core, "repo_root", root)


def test_an_unresolvable_repo_root_skips_the_fill_and_item_17_stays_stored(tmp_path, monkeypatch):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _lock(w)
    _lose_the_repo_root_for_the_fill(monkeypatch)
    done = _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    assert "inputsFilled" not in done
    assert done["inputsFillFailed"] == "repo-root-unavailable"
    monkeypatch.undo()
    assert _raw(w, COMMANDS_SLUG) == ["npm ci"]
    assert _raw(w, INPUTS_SLUG) is None


def test_an_unreadable_root_is_a_failed_scan_not_an_empty_fill(tmp_path, monkeypatch):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _lock(w)
    real_scandir = os.scandir

    def scandir(path):
        if str(path) == str(w.repo):
            raise PermissionError(13, "Permission denied")
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", scandir)
    with pytest.raises(OSError):
        CS.detect_inputs(str(w.repo))
    done = _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    assert "inputsFilled" not in done
    assert "Permission denied" in done["inputsFillFailed"], done
    monkeypatch.undo()
    assert _raw(w, COMMANDS_SLUG) == ["npm ci"]
    assert _raw(w, INPUTS_SLUG) is None
    again = _set_ok(w, COMMANDS_SLUG, ["npm ci", "npm test"])
    assert again["inputsFilled"] == ["package-lock.json"]


def test_a_failed_fill_reports_inputs_fill_failed_and_item_17_stays_stored(tmp_path, monkeypatch):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _lock(w)
    real_write = core_md.write_project_config_item
    refusal = dict(action="refused", reason="write-failed")

    def write(cwd, slug, value, **kw):
        return refusal if slug == INPUTS_SLUG else real_write(cwd, slug, value, **kw)

    monkeypatch.setattr(core_md, "write_project_config_item", write)
    done = _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    assert done["inputsFillFailed"] == "write-failed", done
    assert "inputsFilled" not in done
    monkeypatch.undo()
    assert _raw(w, COMMANDS_SLUG) == ["npm ci"]
    assert _raw(w, INPUTS_SLUG) is None


@pytest.mark.parametrize("value,reason", [
    (["/abs"], "setup-input-unsafe-path"),
    (["../x"], "setup-input-unsafe-path"),
    (["a/../x"], "setup-input-unsafe-path"),
    (["has space"], "setup-input-unsafe-path"),
    ([7], "setup-input-unsafe-path"),
    ("package-lock.json", "malformed-value"),
    (None, "malformed-value"),
])
def test_item_18_refuses_an_unsafe_entry_or_a_non_list_and_stores_nothing(tmp_path, value, reason):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _set_ok(w, INPUTS_SLUG, ["keep.lock"])
    assert _set(w, INPUTS_SLUG, value) == dict(action="refused", reason=reason)
    assert _raw(w, INPUTS_SLUG) == ["keep.lock"]


def test_item_18_takes_a_list_and_an_empty_list(tmp_path):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _set_ok(w, INPUTS_SLUG, ["a/b.lock", "c.lock"])
    assert _raw(w, INPUTS_SLUG) == ["a/b.lock", "c.lock"]
    _set_ok(w, INPUTS_SLUG, [])
    assert _raw(w, INPUTS_SLUG) == []


def test_the_registry_carries_item_18():
    by_number = {item["number"]: item for item in PC.ITEMS}
    assert by_number[18] == dict(number=18, slug="cloudSetupInputs", name="Cloud setup inputs",
                                 home=PC.HOME_PROJECT_CONFIGURATION, shape="inputPathList",
                                 plugin_default=None)
    assert PC.CLOUD_SETUP_INPUTS_SLUG == INPUTS_SLUG
    assert PC.REASON_SETUP_INPUT_UNSAFE_PATH == "setup-input-unsafe-path"


def test_a_detected_name_item_18_would_refuse_is_left_out_of_the_list(tmp_path):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _lock(w)
    _lock(w, "requirements dev.txt", "flask\n")
    done = _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    assert done["inputsFilled"] == ["package-lock.json"], done
    assert "inputsFillFailed" not in done
    assert _raw(w, COMMANDS_SLUG) == ["npm ci"]
    assert _raw(w, INPUTS_SLUG) == ["package-lock.json"]


def test_a_fill_whose_read_back_does_not_match_reports_set_read_mismatch(tmp_path, monkeypatch):
    # axis: a write that claims success without storing the list is reported, not trusted
    w = _world(tmp_path, mode_registry.IN_REPO)
    _lock(w)
    real_write = core_md.write_project_config_item

    def write(cwd, slug, value, **kw):
        if slug == INPUTS_SLUG:
            return dict(action="written")
        return real_write(cwd, slug, value, **kw)

    monkeypatch.setattr(core_md, "write_project_config_item", write)
    done = _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    assert done["inputsFillFailed"] == "set-read-mismatch" == PC.REASON_SET_MISMATCH, done
    assert "inputsFilled" not in done
    monkeypatch.undo()
    assert _raw(w, COMMANDS_SLUG) == ["npm ci"]
    assert _raw(w, INPUTS_SLUG) is None


def test_a_configured_directory_that_is_not_a_git_checkout_gets_no_fill(tmp_path, monkeypatch):
    # axis: the fill scans only a git checkout, so a plain configured directory is reported, not scanned
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "package-lock.json").write_text("v1\n")
    cwd, root = str(plain), str(tmp_path / "store-root")
    assert store_core.repo_root(cwd) == os.path.realpath(cwd)
    assert mode_registry.write_registry(cwd, mode_registry.IN_REPO, None, root=root) is not None
    done = core_md.write(cwd, dict(CORE_FACTS), "confirmed", root=root, now="2026-06-26")
    assert done["action"] in ("written", "reused"), done
    got = PC.set_item(cwd, COMMANDS_SLUG, ["npm ci"], root=root)
    assert got["action"] in ("written", "noop"), got
    assert got["inputsFillFailed"] == "not-a-git-checkout", got
    assert "inputsFilled" not in got
    assert PC.get_item(cwd, COMMANDS_SLUG, root=root)["raw"] == ["npm ci"]
    assert PC.get_item(cwd, INPUTS_SLUG, root=root)["raw"] is None


@pytest.mark.parametrize("mode", MODES)
def test_the_cli_sets_item_18_from_stdin_and_the_setup_stamp_moves(tmp_path, monkeypatch, capsys,
                                                                    mode):
    # axis: item 18 through its public entry point stores the list and the stamp carries it
    w = _world(tmp_path, mode)
    _set_ok(w, COMMANDS_SLUG, ["npm ci"])
    assert _raw(w, INPUTS_SLUG) == []
    before = _stamp(w)
    _lock(w)
    monkeypatch.setattr("sys.stdin", io.StringIO('["package-lock.json"]'))
    rc = PC.main(["set", "--item", INPUTS_SLUG, "--cwd", w.cwd, "--root", w.root])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["action"] == "written"
    assert _raw(w, INPUTS_SLUG) == ["package-lock.json"]
    after = _stamp(w)
    assert after != before and after == _compose(w)["calibration"]["stamp"]


# ---------------------------------------------------------------- the script checks its inputs


def _run_setup(w, text, lock_text):
    """Runs the text in a stub clone (`work`, with a .git directory) holding the lockfile
    `lock_text` (no lockfile when it is None), every tool stubbed; returns the setup log, the work directory, the stamp path and the completed process."""
    stub = w.tmp / "stubs"
    stub.mkdir()
    for name in ("git", "npm", "apt-get", "uv"):
        (stub / name).write_text("#!/bin/bash\nexit 0\n")
        (stub / name).chmod(0o755)
    work = w.tmp / "work"
    (work / ".git").mkdir(parents=True)
    if lock_text is not None:
        (work / "package-lock.json").write_text(lock_text)
    env = {"HOME": str(w.home), "PATH": "%s:/usr/bin:/bin" % stub}
    proc = subprocess.run(["bash", "-c", text], env=env, capture_output=True, text=True, timeout=60,
                          cwd=str(work))
    log = (w.home / "superheroes-cloud-setup.log").read_text()
    stamp = os.path.join(mode_registry.project_store_dir(
        w.cwd, str(w.home / ".claude" / "superheroes")), CS.STAMP_FILE)
    return log, work, stamp, proc


def test_the_script_runs_nothing_and_withholds_the_stamp_when_an_input_differs(tmp_path):
    w = _world(tmp_path, mode_registry.IN_REPO)
    _lock(w, text="v2\n")
    _set_ok(w, COMMANDS_SLUG, ['echo ran >> "$PWD/ran.txt"'])
    text = _compose(w)["text"]
    log, work, stamp, proc = _run_setup(w, text, "v1\n")
    assert "setup input package-lock.json differs from the setup text" in log
    assert "setup stamp withheld" in log and "setup command 1 ok" not in log
    assert not os.path.exists(stamp) and not (work / "ran.txt").exists()
    assert proc.returncode != 0, (proc.returncode, proc.stdout, proc.stderr)


def test_the_script_publishes_the_stamp_when_the_inputs_match(tmp_path):
    # axis: the published stamp is the one that carries the input contents, not just any stamp
    w = _world(tmp_path, mode_registry.IN_REPO)
    _lock(w, text="v2\n")
    _set_ok(w, COMMANDS_SLUG, ['echo ran >> "$PWD/ran.txt"'])
    composed = _compose(w)
    log, work, stamp, proc = _run_setup(w, composed["text"], "v2\n")
    assert proc.returncode == 0, (proc.returncode, proc.stdout, proc.stderr)
    assert "differs" not in log and "setup command 1 ok" in log
    assert os.path.exists(stamp) and (work / "ran.txt").exists()
    # the script writes the stamp followed by one newline (`printf '%s\n'`)
    published = open(stamp).read()
    assert published == composed["calibration"]["stamp"] + "\n"
    published = published[:-1]
    assert published == _stamp(w)
    _lock(w, text="v3\n")
    changed = _compose(w)["calibration"]["stamp"]
    assert changed != published and changed == _stamp(w)


def test_the_script_flags_an_input_missing_in_the_clone_that_was_present_at_compose(tmp_path):
    # axis: an input present when the text was composed and absent in the clone is caught
    w = _world(tmp_path, mode_registry.IN_REPO)
    _lock(w, text="v1\n")
    _set_ok(w, COMMANDS_SLUG, ['echo ran >> "$PWD/ran.txt"'])
    assert _raw(w, INPUTS_SLUG) == ["package-lock.json"]
    log, work, stamp, proc = _run_setup(w, _compose(w)["text"], None)
    assert proc.returncode != 0, (proc.returncode, proc.stdout, proc.stderr)
    assert not (work / "package-lock.json").exists()
    assert "setup input package-lock.json differs from the setup text" in log
    assert "found missing" in log and "expected missing" not in log
    assert "setup stamp withheld" in log and "setup command 1 ok" not in log
    assert not os.path.exists(stamp) and not (work / "ran.txt").exists()


def test_the_script_flags_an_input_present_in_the_clone_that_was_missing_at_compose(tmp_path):
    # axis: an input missing when the text was composed and present in the clone is caught
    w = _world(tmp_path, mode_registry.IN_REPO)
    _set_ok(w, COMMANDS_SLUG, ["true"])
    _set_ok(w, INPUTS_SLUG, ["package-lock.json"])
    log, _, stamp, proc = _run_setup(w, _compose(w)["text"], "now present\n")
    assert proc.returncode != 0, (proc.returncode, proc.stdout, proc.stderr)
    assert "setup input package-lock.json differs" in log and "expected missing" in log
    assert not os.path.exists(stamp)


# ---------------------------------------------------------------- detect_inputs


def test_detect_inputs_picks_root_level_lockfiles_sorted(tmp_path):
    for name in ("yarn.lock", "package-lock.json", "requirements-dev.txt", "requirements.txt",
                 "README.md", "notes.txt", "Cargo.lock"):
        (tmp_path / name).write_text("x")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "package-lock.json").write_text("x")
    (tmp_path / "go.sum").mkdir()
    assert CS.detect_inputs(str(tmp_path)) == [
        "Cargo.lock", "package-lock.json", "requirements-dev.txt", "requirements.txt", "yarn.lock"]


def test_detect_inputs_missing_root_is_empty(tmp_path):
    assert CS.detect_inputs(str(tmp_path / "nope")) == []
    (tmp_path / "afile").write_text("x")
    assert CS.detect_inputs(str(tmp_path / "afile")) == []


# ---------------------------------------------------------------- git environment isolation


def test_git_helper_ignores_git_dir_inherited_at_import(tmp_path, monkeypatch):
    other = tmp_path / "other"
    other.mkdir()
    subprocess.run(["git", "-C", str(other), "init", "-q"], check=True, capture_output=True)
    before = (other / ".git" / "config").read_text()
    import importlib.util
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    spec = importlib.util.spec_from_file_location("_inputs_2008_fresh", __file__)
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)  # a fresh import snapshots the inherited GIT_DIR, as collection can
    monkeypatch.delenv("GIT_DIR")  # the autouse fixture's isolation, applied after collection
    work = tmp_path / "work"
    work.mkdir()
    w = fresh._world(work, mode_registry.GLOBAL)
    assert (w.repo / ".git").is_dir()
    assert (other / ".git" / "config").read_text() == before
