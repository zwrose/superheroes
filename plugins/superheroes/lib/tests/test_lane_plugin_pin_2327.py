"""Tests for the lane pin (#2327): every local lane `compose_launch` composes starts its child on the
advisor's own plugin root and names that root's version in its prompt, and a lane whose running
plugin version differs from the version its launch prompt names is refused naming both versions.

Nothing here touches the network. The roots and manifests are built under tmp_path.
"""
import json
import os
import signal

import pytest

import engine_adapter
import launch_lines
from test_cloud_builder import ENV_ID, SHA
# The two autouse fixtures imported here isolate the ledger and the seat config for launch_build.
from test_launcher import (  # noqa: F401
    L, _all_checks, _autouse_isolated_ledger_root, _autouse_seat_config_matches_spawn,
    _init_repo, _make_spawn_fn, _valid_premise)

VERSION_LABEL = launch_lines.VERSION
BRANCH = "feature/adopted-1"
HEAD = "b" * 40
BUDGET = "until 18:00 local, no more than 3 hours of builder time"


@pytest.fixture(autouse=True)
def _no_user_git_config(tmp_path, monkeypatch):
    empty = tmp_path / "empty-gitconfig"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))


def _fake_root(tmp_path, version, name="rootA"):
    root = tmp_path / name
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "superheroes", "version": version}), encoding="utf-8")
    return str(root)


def _pin_root(monkeypatch, root):
    monkeypatch.setattr(L, "plugin_root", lambda: root)


def _version_lines(prompt):
    return [line for line in prompt.splitlines() if line.startswith(VERSION_LABEL)]


def _assert_pinned(composed, root, version):
    # axis: a composed local lane carries the pin on all three faces — argv, prompt and result
    assert composed["ok"] is True, composed
    argv = composed["argv"]
    assert "--plugin-dir" in argv
    assert argv[argv.index("--plugin-dir") + 1] == root
    assert argv[-2:] == ["--plugin-dir", root]
    assert _version_lines(composed["prompt"]) == ["%s %s" % (VERSION_LABEL, version)]
    assert composed["pluginVersion"] == version
    assert composed["pluginRoot"] == root


# ---------------------------------------------------------------- the DoD row: root A against version B


def test_a_local_workhorse_lane_starts_on_root_a_and_a_lane_running_version_b_is_refused(
        tmp_path, monkeypatch):
    # axis: the local argv pins --plugin-dir, the local prompt names the version, and a mismatch is refused naming both
    root_a = _fake_root(tmp_path, "9.1.0")
    _pin_root(monkeypatch, root_a)
    repo = _init_repo(tmp_path / "repo")
    composed = L.compose_launch(repo, 656, _valid_premise(repo))
    _assert_pinned(composed, root_a, "9.1.0")
    assert "Advisor plugin version: 9.1.0" in composed["prompt"].splitlines()
    refused = L.lane_version_check(composed["prompt"], running_version="9.2.0")
    assert refused["ok"] is False
    assert refused["pinned"] is True
    assert refused["reason"] == "lane-plugin-version-mismatch"
    assert "9.2.0" in refused["comment"] and "9.1.0" in refused["comment"]
    assert refused["running"] == "9.2.0" and refused["launched"] == "9.1.0"
    admitted = L.lane_version_check(composed["prompt"], running_version="9.1.0")
    assert admitted["ok"] is True and admitted["pinned"] is True
    assert admitted["reason"] is None and admitted["comment"] is None


def test_the_prompt_places_the_version_line_directly_after_the_issue_line(tmp_path, monkeypatch):
    # axis: a local prompt names the advisor's plugin version on its own line right after the issue line
    _pin_root(monkeypatch, _fake_root(tmp_path, "9.1.0"))
    repo = _init_repo(tmp_path / "repo")
    composed = L.compose_launch(repo, 656, _valid_premise(repo))
    rulings = composed["doctrine"]["rulingsBlock"]
    assert composed["prompt"] == "%s\n\nIssue: #656\n\nAdvisor plugin version: 9.1.0\n\n%s" % (
        L._WORKHORSE_CMD, rulings)


def test_a_local_adopt_lane_carries_the_same_pin(tmp_path, monkeypatch):
    # axis: an adopt lane's local prompt carries the version line between the issue line and the adopted branch
    root_a = _fake_root(tmp_path, "9.1.0")
    _pin_root(monkeypatch, root_a)
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo, adoptsBranch=BRANCH, adoptsHead=HEAD)
    composed = L.compose_launch(repo, 656, premise)
    _assert_pinned(composed, root_a, "9.1.0")
    head = "%s\n\nIssue: #656\n\nAdvisor plugin version: 9.1.0\nAdopts branch: %s at %s\nBase commit: %s\n\n" % (
        L._WORKHORSE_CMD, BRANCH, HEAD, premise["baseCommit"])
    assert composed["prompt"].startswith(head)
    assert L.lane_version_check(composed["prompt"], running_version="9.2.0")["ok"] is False
    assert L.lane_version_check(composed["prompt"], running_version="9.1.0")["ok"] is True


def test_a_local_detective_lane_carries_the_same_pin(tmp_path, monkeypatch):
    # axis: a detective lane's local prompt carries the version line after its issue and budget lines
    root_a = _fake_root(tmp_path, "9.1.0")
    _pin_root(monkeypatch, root_a)
    repo = _init_repo(tmp_path / "repo")
    composed = L.compose_launch(
        repo, 656, _valid_premise(repo, charter="detective", budget=BUDGET))
    _assert_pinned(composed, root_a, "9.1.0")
    assert composed["prompt"].startswith(
        "/superheroes:detective\n\nIssue: #656\nBudget: %s\n\nAdvisor plugin version: 9.1.0\n\n" % BUDGET)
    assert L.lane_version_check(composed["prompt"], running_version="9.2.0")["ok"] is False
    assert L.lane_version_check(composed["prompt"], running_version="9.1.0")["ok"] is True


def test_place_local_is_pinned_like_place_none(tmp_path, monkeypatch):
    # axis: the explicit local place is composed the same as the omitted place
    root_a = _fake_root(tmp_path, "9.1.0")
    _pin_root(monkeypatch, root_a)
    repo = _init_repo(tmp_path / "repo")
    composed = L.compose_launch(repo, 656, _valid_premise(repo), place=L.PLACE_LOCAL)
    _assert_pinned(composed, root_a, "9.1.0")


def test_the_real_root_is_the_directory_that_holds_the_running_launcher():
    # axis: plugin_root is the plugin root that holds the running launcher.py's lib directory
    root = L.plugin_root()
    assert os.path.isabs(root)
    assert os.path.isfile(os.path.join(root, "lib", "launcher.py"))
    manifest = os.path.join(root, ".claude-plugin", "plugin.json")
    with open(manifest, encoding="utf-8") as fh:
        assert L.plugin_version() == json.load(fh)["version"]


# ---------------------------------------------------------------- cloud is unchanged


def test_a_cloud_compose_has_no_plugin_dir_and_exactly_one_version_line(monkeypatch):
    # axis: a cloud prompt keeps its single version line and a cloud argv carries no --plugin-dir
    monkeypatch.setattr(L, "plugin_version", lambda: "9.1.0")
    composed = L.compose_launch(
        ".", 1747, {"baseCommit": SHA}, model="opus", place="cloud",
        cloud_environment=ENV_ID, session_name="issue-1747-probe")
    assert composed["ok"] is True, composed
    assert "--plugin-dir" not in composed["argv"]
    assert _version_lines(composed["prompt"]) == ["Advisor plugin version: 9.1.0"]
    assert composed["prompt"].count("Advisor plugin version:") == 1
    assert composed["pluginVersion"] == "9.1.0"
    assert composed["pluginRoot"] == L.plugin_root()
    rulings = composed["doctrine"]["rulingsBlock"]
    assert composed["prompt"] == "%s\n\nIssue: #1747\n\n%s\n%s\n%s\n%s\n\n%s\n\n%s" % (
        L._WORKHORSE_CMD, "Place: cloud session", "Advisor plugin version: 9.1.0",
        "Cloud environment: %s" % ENV_ID, "Base commit: %s" % SHA,
        composed["doctrine"]["cloudLaunchLine"], rulings)


# ---------------------------------------------------------------- unreadable root version (E1)


@pytest.mark.parametrize("manifest", [
    None,
    "not json {",
    json.dumps({"name": "superheroes"}),
    json.dumps({"version": "   "}),
    json.dumps({"version": 7}),
    json.dumps(["9.1.0"]),
])
def test_an_unreadable_root_version_refuses_a_local_compose(tmp_path, monkeypatch, manifest):
    # axis: a missing, unparseable or blank manifest version refuses a local compose, as it does a cloud one
    root = tmp_path / "bad-root"
    (root / ".claude-plugin").mkdir(parents=True)
    if manifest is not None:
        (root / ".claude-plugin" / "plugin.json").write_text(manifest, encoding="utf-8")
    _pin_root(monkeypatch, str(root))
    repo = _init_repo(tmp_path / "repo")
    result = L.compose_launch(repo, 656, _valid_premise(repo))
    assert result["ok"] is False
    assert result["reason"] == "compose-plugin-version-unreadable"


def test_an_unreadable_root_version_refuses_a_cloud_compose_as_before(monkeypatch):
    # axis: the cloud refusal for an unreadable plugin version is kept
    monkeypatch.setattr(L, "plugin_version", lambda: None)
    result = L.compose_launch(
        ".", 1747, {"baseCommit": SHA}, model="opus", place="cloud",
        cloud_environment=ENV_ID, session_name="issue-1747-probe")
    assert result["ok"] is False and result["reason"] == "compose-plugin-version-unreadable"


# ---------------------------------------------------------------- lane_version_check


def test_a_launch_with_no_version_line_is_admitted_unpinned():
    # axis: a hand-typed or pre-pin launch with no version line is admitted, unpinned
    got = L.lane_version_check("/superheroes:workhorse\n\nIssue: #1\n", running_version="9.2.0")
    assert got == {
        "ok": True, "pinned": False, "reason": None, "running": "9.2.0",
        "launched": None, "comment": None,
    }


@pytest.mark.parametrize("text", [None, 7, b"Advisor plugin version: 9.1.0", ["Advisor plugin version: 9.1.0"]])
def test_a_launch_text_that_is_not_a_string_reads_as_no_line(text):
    # axis: a non-string launch text never raises and reads as no version line
    got = L.lane_version_check(text, running_version="9.2.0")
    assert got["ok"] is True and got["pinned"] is False and got["launched"] is None


def test_two_disagreeing_version_lines_are_refused_with_no_launched_version():
    # axis: duplicate version lines with different values are a mismatch whose launched version is unreadable
    text = "Advisor plugin version: 9.1.0\n  Advisor plugin version: 9.2.0  \n"
    got = L.lane_version_check(text, running_version="9.2.0")
    assert got["ok"] is False and got["pinned"] is True
    assert got["reason"] == "lane-plugin-version-mismatch"
    assert got["launched"] is None and got["running"] == "9.2.0"
    assert got["comment"] == L.LANE_VERSION_REFUSAL_TEXT.format(
        running="9.2.0", launched="an unreadable version")


@pytest.mark.parametrize("text", [
    "Advisor plugin version:",
    "Advisor plugin version:   ",
    "Advisor plugin version:9.1.0",
    "Advisor plugin version  9.1.0",
    "Advisor plugin version 9.1.0",
    "Advisor plugin version: 9.1.0\nAdvisor plugin version:",
])
@pytest.mark.parametrize("running", ["9.1.0", "9.2.0", None])
def test_a_damaged_version_header_is_refused_never_admitted_unpinned(text, running):
    # axis: a line that starts with the version label but is not a well-formed header pins the lane with an unreadable launched version
    got = L.lane_version_check("/superheroes:workhorse\n\nIssue: #1\n\n" + text + "\n", running_version=running)
    assert got["ok"] is False and got["pinned"] is True
    assert got["reason"] == "lane-plugin-version-mismatch"
    assert got["launched"] is None
    assert got["comment"] == L.LANE_VERSION_REFUSAL_TEXT.format(
        running=running or "an unreadable version", launched="an unreadable version")


def test_two_agreeing_version_lines_are_admitted_when_the_running_version_matches():
    # axis: duplicate version lines that agree name one version
    text = "Advisor plugin version: 9.1.0\nAdvisor plugin version: 9.1.0\n"
    got = L.lane_version_check(text, running_version="9.1.0")
    assert got["ok"] is True and got["launched"] == "9.1.0"


@pytest.mark.parametrize("running", [None, "", "   ", 9, ["9.1.0"]])
def test_an_unreadable_running_version_is_refused_naming_an_unreadable_version(running):
    # axis: an explicit None, blank or non-string running version is unreadable and refused
    got = L.lane_version_check("Advisor plugin version: 9.1.0", running_version=running)
    assert got["ok"] is False and got["pinned"] is True
    assert got["reason"] == "lane-plugin-version-mismatch"
    assert got["running"] is None and got["launched"] == "9.1.0"
    assert "an unreadable version" in got["comment"] and "9.1.0" in got["comment"]
    assert got["comment"] == L.LANE_VERSION_REFUSAL_TEXT.format(
        running="an unreadable version", launched="9.1.0")


def test_an_omitted_running_version_is_read_from_the_plugin_manifest(monkeypatch):
    # axis: an omitted running version is the running plugin's own version, not an unreadable one
    monkeypatch.setattr(L, "plugin_version", lambda: "9.1.0")
    assert L.lane_version_check("Advisor plugin version: 9.1.0")["ok"] is True
    assert L.lane_version_check("Advisor plugin version: 9.2.0")["ok"] is False
    monkeypatch.setattr(L, "plugin_version", lambda: None)
    got = L.lane_version_check("Advisor plugin version: 9.1.0")
    assert got["ok"] is False and got["running"] is None


def test_the_refusal_text_is_the_contract_text():
    # axis: the refusal text constant is the shared contract text, verbatim
    assert L.LANE_VERSION_REFUSAL_TEXT == (
        "This lane runs plugin {running}; its launch named plugin {launched}. I built nothing. "
        "The advisor relaunches the lane once its seat and this machine agree on the version.")


# ---------------------------------------------------------------- the CLI verb


def _launch_file(tmp_path, version):
    path = tmp_path / "launch.txt"
    path.write_text("/superheroes:workhorse\n\nIssue: #1\n\nAdvisor plugin version: %s\n\nrest\n" % version,
                    encoding="utf-8")
    return str(path)


def test_the_lane_version_verb_exits_1_on_a_mismatch_and_0_on_a_match(tmp_path, monkeypatch, capsys):
    # axis: the lane-version verb exits non-zero exactly when the running version differs from the named one
    monkeypatch.setattr(L, "plugin_version", lambda: "9.2.0")
    assert L.main(["lane-version", "--launch-file", _launch_file(tmp_path, "9.1.0")]) == 1
    printed = json.loads(capsys.readouterr().out)
    assert printed["ok"] is False and printed["reason"] == "lane-plugin-version-mismatch"
    assert "9.2.0" in printed["comment"] and "9.1.0" in printed["comment"]
    assert L.main(["lane-version", "--launch-file", _launch_file(tmp_path, "9.2.0")]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["ok"] is True and printed["pinned"] is True


def test_the_lane_version_verb_refuses_a_missing_launch_file(tmp_path, capsys):
    # axis: an unreadable launch file is a refusal with its own reason, never a crash
    assert L.main(["lane-version", "--launch-file", str(tmp_path / "absent.txt")]) == 1
    printed = json.loads(capsys.readouterr().out)
    assert printed == {
        "ok": False, "pinned": False, "reason": "lane-version-launch-file-unreadable",
        "running": None, "launched": None, "comment": L.LANE_VERSION_UNREADABLE_TEXT,
    }


def test_the_lane_version_verb_refuses_a_launch_file_that_is_not_utf8(tmp_path, capsys):
    # axis: a launch file that is not UTF-8 is unreadable, not a traceback
    path = tmp_path / "binary.txt"
    path.write_bytes(b"\xff\xfe\x00bad")
    assert L.main(["lane-version", "--launch-file", str(path)]) == 1
    printed = json.loads(capsys.readouterr().out)
    assert printed["reason"] == "lane-version-launch-file-unreadable"
    assert printed["comment"] == L.LANE_VERSION_UNREADABLE_TEXT


def test_the_unreadable_text_is_the_contract_text():
    # axis: the unreadable-launch-file stop comment is the shared contract text, verbatim
    assert L.LANE_VERSION_UNREADABLE_TEXT == (
        "This lane could not read its launch prompt file, so it could not check its plugin version. "
        "I built nothing. The advisor relaunches the lane.")


# ---------------------------------------------------------------- the spawn argv


def test_launch_build_spawns_the_child_with_the_plugin_dir_pin(tmp_path, monkeypatch):
    # axis: the argv handed to the spawn ends with --plugin-dir <plugin_root()> and its -p prompt names the version
    repo = _init_repo(tmp_path / "repo")
    log_dir = str(tmp_path / "logs")
    seen = {"argv": None, "pid": None}

    def capture_spawn(argv, repo_root, out_fh, err_fh, child_env):
        seen["argv"] = list(argv)
        proc = _make_spawn_fn("sleep")(argv, repo_root, out_fh, err_fh, child_env)
        seen["pid"] = proc.pid
        return proc

    try:
        result = L.launch_build(
            repo, 656, _valid_premise(repo), _all_checks(), log_dir,
            spawn_fn=capture_spawn, settle_seconds=0.1)
    finally:
        if seen["pid"] is not None:
            try:
                os.kill(seen["pid"], signal.SIGKILL)
            except ProcessLookupError:
                pass
    assert seen["argv"] is not None, result
    argv = seen["argv"]
    assert argv[-2:] == ["--plugin-dir", L.plugin_root()]
    prompt = argv[argv.index("-p") + 1]
    assert "Advisor plugin version: " + L.plugin_version() in prompt.splitlines()


# ---------------------------------------------------------------- the argv builder


def _builder(**kwargs):
    return engine_adapter.claude_builder_argv(
        "sonnet", "11111111-1111-4111-8111-111111111111", "do the work", **kwargs)


def test_claude_builder_argv_appends_the_plugin_dir_at_the_end():
    # axis: a non-empty plugin_dir is appended as the last two argv elements and the prompt stays the -p value
    plain = _builder()
    assert plain["reason"] is None
    pinned = _builder(plugin_dir="/abs/root")
    assert pinned["reason"] is None
    assert pinned["argv"][-2:] == ["--plugin-dir", "/abs/root"]
    assert pinned["argv"][:-2] == plain["argv"]
    assert pinned["argv"][pinned["argv"].index("-p") + 1] == "do the work"


@pytest.mark.parametrize("plugin_dir", [None, "", 7, ["/abs/root"], b"/abs/root"])
def test_claude_builder_argv_appends_nothing_for_any_other_plugin_dir(plugin_dir):
    # axis: a plugin_dir that is not a non-empty string leaves the argv unchanged
    assert _builder(plugin_dir=plugin_dir)["argv"] == _builder()["argv"]
    assert "--plugin-dir" not in _builder(plugin_dir=plugin_dir)["argv"]
