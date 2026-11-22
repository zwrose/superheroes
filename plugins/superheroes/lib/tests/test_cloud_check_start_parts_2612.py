"""Tests for the cloud check's start part (#2612): the cloud session's start hook records which
plugin copy each start part it opened came from, the report carries that as `startParts`, and the
judgment fails the check when any such part has other bytes than this machine's copy of it.

The invariant, pinned at `cloud_check._start_match` and through `judge`: a cloud check passes only
when every start part the start hook actually opened has the same bytes as this machine's copy, and
a comparison that cannot be made fails the check, except a report from an older session with no
`startParts` key, which is judged as before and says its start parts were not read back.

The judgment tests use the fixture projects of test_cloud_check. The recorder tests drive the hook's
audit function directly over temp plugin copies; one test runs the real hook in a subprocess
through a symlink. No test starts a cloud session or touches the network.
"""
import hashlib
import importlib.util
import json
import os
import shlex
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
for _path in (_HERE, _LIB):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import cloud_check as CC  # noqa: E402
import cloud_pass  # noqa: E402
import cloud_setup  # noqa: E402
import cloud_setup_text  # noqa: E402
from test_cloud_check import (ACCOUNT, COMMIT, ENV_ID, NONCE, PAUSED_STANDING, VERSION,  # noqa: E402
                              _cloud_report, _confirm, _judge, _pair)

PLUGIN = cloud_setup_text._plugin_root()
HOOK_PATH = os.path.join(PLUGIN, "hooks", "session_start.py")
HOOK_PART = "hooks/session_start.py"
SHORT = COMMIT[:12]
FIX = "paste the new setup text into the environment"
NOT_READ_BACK = ("The start parts were not read back: the cloud session's plugin is older than "
                 "the one that reports them, so its start code was not checked.")
BULLET = "- Its start hook ran the same start code as mine.\n"
UNREAD_SENTENCE = ("The cloud session did not report which plugin copy its start hook ran, so I "
                   "could not check its start code.")
MINE_UNREADABLE_SENTENCE = ("I could not read my own plugin's start code, so I could not compare "
                            "the cloud's start hook with it.")
SESSION = "session-2612"


# --- fixtures ------------------------------------------------------------------------------

def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _mine():
    """{part: bytes} of this machine's start parts, the bytes the judgment compares against."""
    return cloud_setup_text.start_read_parts()


def _copy(part, version=VERSION, commit=COMMIT, data=None):
    """One reported copy of `part`: this machine's bytes unless `data` says otherwise."""
    return {"version": version, "commit": commit,
            "sha256": _sha(_mine()[part] if data is None else data)}


def _start_value(**changed):
    """A `startParts` value in which every start part came from a copy with this machine's bytes;
    `changed` maps a part, named by its path with `/` and `.` written `__` and `_dot_` (so
    `lib__core_md_dot_py` is `lib/core_md.py`), to the list of copies it is given instead."""
    value = {part: [_copy(part)] for part in cloud_setup_text.START_HOOK_READS}
    for key, copies in changed.items():
        part = key.replace("__", "/").replace("_dot_", ".")
        assert part in value, part
        value[part] = copies
    return value


def _first_paragraph(message):
    return message.split("\n\n")[0]


def _load_hook(name="session_start_2612"):
    spec = importlib.util.spec_from_file_location(name, HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def hook():
    return _load_hook()


def _older(cloud, **over):
    """A report from an older session: no `startParts` key at all."""
    obj = _cloud_report(cloud, **over)
    del obj["startParts"]
    return obj


def _marker_parts(local):
    return CC.read_failed_check(local.cwd, ACCOUNT, local.root)["failedParts"]


# --- _start_match: the one chokepoint -------------------------------------------------------

def test_start_match_passes_when_every_part_has_my_bytes():
    assert CC._start_match({"startParts": _start_value()}) == (True, None, [])


def test_start_match_without_the_key_is_not_read_back():
    # axis: an older session's report has no key; it is neither a match nor a failure
    assert CC._start_match({}) == (None, "not-read-back", [])


@pytest.mark.parametrize("value", [
    None, [], "x", 7, {"lib/core_md.py": "not a list"}, {"lib/core_md.py": []},
    {"lib/core_md.py": [None]}, {"lib/core_md.py": [{"version": "1", "commit": None}]},
    {"lib/core_md.py": [{"version": 1, "commit": None, "sha256": "a"}]},
    {"lib/core_md.py": [{"version": "1", "commit": 5, "sha256": "a"}]},
    {"lib/core_md.py": [{"version": "1", "commit": None, "sha256": 5}]},
    {5: [{"version": "1", "commit": None, "sha256": "a"}]},
], ids=repr)
def test_start_match_a_null_or_malformed_value_is_unread(value):
    # axis: a value that is not {part: non-empty list of {version, commit, sha256}} is unread
    assert CC._start_match({"startParts": value}) == (False, "unread", [])


def test_start_match_a_malformed_copy_beside_good_ones_is_still_unread():
    value = _start_value()
    value["lib/core_md.py"] = []
    assert CC._start_match({"startParts": value}) == (False, "unread", [])


def test_start_match_a_record_without_the_hooks_own_part_is_unread():
    value = _start_value()
    del value[HOOK_PART]
    # axis: no hook part means no proof which hook ran, so the record is unread
    assert CC._start_match({"startParts": value}) == (False, "unread", [])
    assert CC._start_match({"startParts": {}}) == (False, "unread", [])


def test_start_match_my_own_parts_unreadable_is_mine_unreadable(monkeypatch):
    value = _start_value()
    real = cloud_setup_text.start_read_parts

    def boom(root=None):
        if root is None:
            raise OSError("unreadable")
        return real(root)

    monkeypatch.setattr(cloud_setup_text, "start_read_parts", boom)
    # axis: parts that cannot be read here cannot be compared, so the check fails
    assert CC._start_match({"startParts": value}) == (False, "mine-unreadable", [])


def test_start_match_a_copy_with_no_sha_differs():
    bad = {"version": VERSION, "commit": COMMIT, "sha256": None}
    got = CC._start_match({"startParts": _start_value(lib__core_md_dot_py=[bad])})
    # axis: a part that could not be read in its copy (None) is a difference, never a match
    assert got == (False, "older", [("lib/core_md.py", bad)])


def test_start_match_lists_every_differing_copy_of_every_part_in_order():
    old = _copy("lib/core_md.py", version="0.1.0", data=b"old")
    older = _copy("lib/core_md.py", version="0.0.9", data=b"older")
    also = _copy("lib/cloud_pass.py", version="0.1.0", data=b"old")
    got = CC._start_match({"startParts": _start_value(
        lib__core_md_dot_py=[old, _copy("lib/core_md.py"), older], lib__cloud_pass_dot_py=[also])})
    assert got == (False, "older", [("lib/cloud_pass.py", also), ("lib/core_md.py", old),
                                    ("lib/core_md.py", older)])


def test_start_match_ignores_a_part_the_expected_set_does_not_list():
    value = _start_value()
    value["lib/not_a_start_part.py"] = [{"version": "0.0.1", "commit": None, "sha256": "0" * 64}]
    assert CC._start_match({"startParts": value}) == (True, None, [])


# --- judge ----------------------------------------------------------------------------------

def test_a_one_part_from_an_older_copy_fails_and_names_it_and_the_marker_records_start(tmp_path):
    local, cloud = _pair(tmp_path)
    old = _copy("lib/core_md.py", version="0.40.0", data=b"# an older core_md\n")
    result = _judge(local, _cloud_report(cloud, startParts=_start_value(lib__core_md_dot_py=[old])))
    assert result["action"] == "failed" and "start" in result["failedParts"]
    assert result["failedParts"] == ["start"] and result["recordWritten"] is False
    assert result["results"]["startPartsMatch"] is False
    assert result["message"] == (
        "**The check failed on one part.** The cloud session's start hook ran start code that "
        "differs from mine: `lib/core_md.py` from plugin 0.40.0 at commit %s, and mine is %s.\n\n"
        % (SHORT, VERSION) + PAUSED_STANDING + " To fix it, " + FIX + " and say \"check again\".")
    assert "start" in _marker_parts(local)
    assert cloud_setup.read(local.cwd, ACCOUNT, local.root)["state"] == "none"


def test_every_part_with_my_bytes_and_version_passes_and_says_so(tmp_path):
    local, cloud = _pair(tmp_path)
    result = _judge(local, _cloud_report(cloud, startParts=_start_value()))
    assert result["action"] == "passed" and result["failedParts"] == []
    assert result["results"]["startPartsMatch"] is True
    assert BULLET in result["message"] and NOT_READ_BACK not in result["message"]
    # the bullet follows the calibration bullet
    assert ("- Its calibration matches this machine's.\n" + BULLET
            + "- The reviewer answered.\n") in result["message"]
    assert list(result["results"])[:6] == [
        "versionMatches", "pinMatches", "dependencyHookMatches", "calibrationMatches",
        "startPartsMatch", "reviewerAnswered"]


def test_an_older_version_with_identical_bytes_passes(tmp_path):
    local, cloud = _pair(tmp_path)
    same = {part: [_copy(part, version="0.1.0", commit=None)]
            for part in cloud_setup_text.START_HOOK_READS}
    result = _judge(local, _cloud_report(cloud, startParts=same))
    # axis: the comparison is of bytes; an older release whose start code did not change is no failure
    assert result["action"] == "passed" and result["results"]["startPartsMatch"] is True


def test_a_stale_covenant_fails_naming_it(tmp_path):
    local, cloud = _pair(tmp_path)
    stale = _copy("rubric/covenant.md", version="0.30.0", commit=None, data=b"an older covenant\n")
    result = _judge(local, _cloud_report(
        cloud, startParts=_start_value(rubric__covenant_dot_md=[stale])))
    # axis: a start part that is no module (the covenant text) is compared like the modules
    assert result["failedParts"] == ["start"]
    assert ("`rubric/covenant.md` from plugin 0.30.0 at an unknown commit, and mine is %s." % VERSION
            in result["message"])


def test_two_differing_items_are_joined_and_unknowns_are_said(tmp_path):
    local, cloud = _pair(tmp_path)
    one = _copy("lib/core_md.py", version=None, commit=COMMIT, data=b"x")
    two = _copy("lib/store.py", version="0.2.0", commit=None, data=b"y")
    result = _judge(local, _cloud_report(
        cloud, startParts=_start_value(lib__core_md_dot_py=[one], lib__store_dot_py=[two])))
    assert _first_paragraph(result["message"]) == (
        "**The check failed on one part.** The cloud session's start hook ran start code that "
        "differs from mine: `lib/core_md.py` from plugin an unknown version at commit %s and "
        "`lib/store.py` from plugin 0.2.0 at an unknown commit, and mine is %s." % (SHORT, VERSION))


def test_a_report_with_no_start_parts_key_passes_as_before_and_says_not_read_back(tmp_path):
    local, cloud = _pair(tmp_path)
    result = _judge(local, _older(cloud))
    # edge 1: no key leads to the result as today, startPartsMatch None, and the paragraph
    assert result["action"] == "passed" and result["failedParts"] == []
    assert result["results"]["startPartsMatch"] is None
    assert result["message"] == (
        "**The check passed.**\n\n"
        "- The cloud's plugin is %s, the same as mine.\n"
        "- Its calibration matches this machine's.\n"
        "- The reviewer answered.\n"
        "- It has a git identity to commit with.\n\n" % VERSION + NOT_READ_BACK + "\n\n"
        "Cloud builds are ready for demo and still switched off. Say \"turn cloud builds on\" "
        "when you want them.")


def test_a_failing_report_with_no_start_parts_key_fails_as_before_and_says_not_read_back(tmp_path):
    local, cloud = _pair(tmp_path)
    result = _judge(local, _older(cloud, pluginVersion="0.0.1"))
    assert result["action"] == "failed" and result["failedParts"] == ["version"]
    assert result["results"]["startPartsMatch"] is None
    assert "start" not in _marker_parts(local)
    assert result["message"].endswith("\n\n" + NOT_READ_BACK)
    assert _first_paragraph(result["message"]) == (
        "**The check failed on one part.** The cloud's plugin is 0.0.1 and mine is %s." % VERSION)


def test_a_null_start_parts_fails_on_start_as_unread(tmp_path):
    local, cloud = _pair(tmp_path)
    result = _judge(local, _cloud_report(cloud, startParts=None))
    assert result["failedParts"] == ["start"] and result["results"]["startPartsMatch"] is False
    assert result["message"] == (
        "**The check failed on one part.** " + UNREAD_SENTENCE + "\n\n" + PAUSED_STANDING
        + " To fix it, " + FIX + " and say \"check again\".")
    assert "start" in _marker_parts(local)


@pytest.mark.parametrize("value", [{"lib/core_md.py": "x"}, {"lib/core_md.py": []}, "x", [1]],
                         ids=repr)
def test_a_malformed_start_parts_fails_on_start_as_unread(tmp_path, value):
    local, cloud = _pair(tmp_path)
    result = _judge(local, _cloud_report(cloud, startParts=value))
    assert result["failedParts"] == ["start"]
    assert UNREAD_SENTENCE in result["message"] and NOT_READ_BACK not in result["message"]


def test_a_record_without_the_hooks_part_fails_on_start_as_unread(tmp_path):
    local, cloud = _pair(tmp_path)
    value = _start_value()
    del value[HOOK_PART]
    result = _judge(local, _cloud_report(cloud, startParts=value))
    assert result["failedParts"] == ["start"] and UNREAD_SENTENCE in result["message"]


def test_my_own_parts_unreadable_fails_on_start_with_its_own_sentence_and_fix(tmp_path,
                                                                           monkeypatch):
    local, cloud = _pair(tmp_path)
    obj = _cloud_report(cloud, startParts=_start_value())
    real = cloud_setup_text.start_read_parts

    def boom(root=None):
        if root is None:
            raise OSError("unreadable")
        return real(root)

    monkeypatch.setattr(cloud_setup_text, "start_read_parts", boom)
    result = _judge(local, obj)
    assert result["failedParts"] == ["start"]
    assert result["message"] == (
        "**The check failed on one part.** " + MINE_UNREADABLE_SENTENCE + "\n\n" + PAUSED_STANDING
        + " To fix it, tell me so I can look at this machine's plugin copy and say \"check "
        "again\".")


def test_a_copy_with_no_sha_fails_on_start_as_older(tmp_path):
    local, cloud = _pair(tmp_path)
    bad = {"version": "0.5.0", "commit": None, "sha256": None}
    result = _judge(local, _cloud_report(cloud, startParts=_start_value(lib__store_dot_py=[bad])))
    assert result["failedParts"] == ["start"]
    assert ("`lib/store.py` from plugin 0.5.0 at an unknown commit" in result["message"])


def test_judge_and_judge_parts_both_route_through_start_match(tmp_path, monkeypatch):
    local, cloud = _pair(tmp_path)
    seen = []
    forced = (False, "older", [("lib/store.py", {"version": "0.1.0", "commit": None,
                                                  "sha256": "0" * 64})])

    def fake(obj):
        seen.append(obj)
        return forced

    monkeypatch.setattr(CC, "_start_match", fake)
    result = _judge(local, _cloud_report(cloud, startParts=_start_value()))
    # axis: the judgment reads the verdict from the one function, even where the report would pass
    assert seen and result["failedParts"] == ["start"] and "`lib/store.py`" in result["message"]
    assert result["results"]["startPartsMatch"] is False


def test_an_unread_result_carries_the_start_key_as_none(tmp_path):
    local, _cloud = _pair(tmp_path)
    result = _judge(local, "no report here")
    assert result["action"] == "unread" and "startPartsMatch" in result["results"]
    assert result["results"]["startPartsMatch"] is None
    assert list(result["results"])[3:5] == ["calibrationMatches", "startPartsMatch"]


def test_the_start_part_is_in_the_marker_wording_table():
    names = [row[0] for row in CC._PARTS]
    assert names[names.index("calibration") + 1] == "start"
    assert list(cloud_setup.PAUSED_PARTS)[4:6] == ["calibration", "start"]
    assert cloud_setup.PAUSED_PARTS["start"] == (
        "the plugin copy the cloud session started from", cloud_setup.FIX_PASTE_SETUP)
    assert "the plugin copy the cloud session started from" in cloud_setup.paused_failure(["start"])


def test_start_parts_is_not_a_required_report_field():
    # axis: an older report, which has no such field, must stay readable
    assert "startParts" not in CC.REPORT_FIELDS


# --- report: the record the session's start hook left ---------------------------------------

def _record(copy, session=SESSION, parts=None, **over):
    record = {"schema": cloud_pass.START_COPY_SCHEMA, "session": session, "roots": [str(copy)],
              "parts": {"lib/x.py": [0]} if parts is None else parts}
    record.update(over)
    return record


def _env(record, session=SESSION):
    env = {cloud_pass.START_COPY_ENV: record if isinstance(record, str) else json.dumps(record)}
    if session is not None:
        env["CLAUDE_CODE_SESSION_ID"] = session
    return env


class _Git:
    def __init__(self, returncode=0, stdout=COMMIT + "\n"):
        self.returncode, self.stdout = returncode, stdout


def test_report_gives_each_recorded_part_its_copys_version_commit_and_sha(tmp_path, monkeypatch):
    copy = tmp_path / "copy"
    (copy / "lib").mkdir(parents=True)
    (copy / "version.txt").write_text("9.9.9\nsecond line\n")
    (copy / "lib" / "x.py").write_bytes(b"abc")
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        return _Git()

    monkeypatch.setattr(CC.subprocess, "run", run)
    got = CC._start_parts(_env(_record(copy, parts={"lib/x.py": [0], "lib/missing.py": [0]})))
    assert got == {
        "lib/x.py": [{"version": "9.9.9", "commit": COMMIT, "sha256": _sha(b"abc")}],
        "lib/missing.py": [{"version": "9.9.9", "commit": COMMIT, "sha256": None}]}
    assert calls and calls[0] == ["git", "-C", str(copy), "rev-parse", "--verify", "HEAD"]


def test_report_has_no_commit_when_git_does_not_answer_and_no_version_without_the_file(
        tmp_path, monkeypatch):
    copy = tmp_path / "copy"
    copy.mkdir()
    (copy / "x.py").write_bytes(b"abc")
    for fake in (lambda argv, **kw: _Git(128, ""), lambda argv, **kw: _Git(0, "not-hex\n"),
                 lambda argv, **kw: (_ for _ in ()).throw(FileNotFoundError("git"))):
        monkeypatch.setattr(CC.subprocess, "run", fake)
        got = CC._start_parts(_env(_record(copy, parts={"x.py": [0]})))
        assert got == {"x.py": [{"version": None, "commit": None, "sha256": _sha(b"abc")}]}


def test_report_carries_the_start_parts_of_the_sessions_own_record(tmp_path):
    local, cloud = _pair(tmp_path)
    env = dict(_env(_record(PLUGIN, parts={HOOK_PART: [0]})), **{cloud_pass.ENVIRONMENT_ENV: ENV_ID})
    obj = CC.report(env=env, cwd=cloud.cwd, root=cloud.root, nonce=NONCE, confirm_fn=_confirm(),
                    identity_fn=lambda cwd: {"author": True, "committer": True})
    assert list(obj["startParts"]) == [HOOK_PART]
    copy = obj["startParts"][HOOK_PART][0]
    assert copy["version"] == VERSION and copy["sha256"] == _sha(_mine()[HOOK_PART])


def test_a_record_of_another_session_or_with_none_to_match_gives_none(tmp_path):
    base = _record(tmp_path)
    # the positive case, so the refusals below are not vacuous
    assert CC._start_parts(_env(base)) is not None
    # edge 7: a record whose session differs from CLAUDE_CODE_SESSION_ID, or with that unset
    assert CC._start_parts(_env(base, session="another-session")) is None
    assert CC._start_parts(_env(base, session=None)) is None
    assert CC._start_parts(_env(base, session="")) is None
    assert CC._start_parts(_env(dict(base, session=""), session="")) is None
    assert CC._start_parts({"CLAUDE_CODE_SESSION_ID": SESSION}) is None
    assert CC._start_parts({}) is None


@pytest.mark.parametrize("change", [
    {"schema": "start-copy/2"}, {"schema": None}, {"session": 5}, {"roots": []},
    {"roots": ["/a"] * 9}, {"roots": ["relative/path"]}, {"roots": [5]}, {"roots": "/abs"},
    {"parts": []}, {"parts": {"../x.py": [0]}}, {"parts": {"lib/../x.py": [0]}},
    {"parts": {"/abs.py": [0]}}, {"parts": {"hooks/hooks.json#SessionStart": [0]}},
    {"parts": {"": [0]}}, {"parts": {"lib/x.py": []}}, {"parts": {"lib/x.py": 0}},
    {"parts": {"lib/x.py": [True]}}, {"parts": {"lib/x.py": [1]}}, {"parts": {"lib/x.py": [-1]}},
    {"parts": {"lib/x.py": ["0"]}}, {"parts": {"lib/x.py": [0.0]}},
    {"parts": {"p%d.py" % n: [0] for n in range(501)}},
])
def test_a_record_that_is_not_whole_gives_none(tmp_path, change):
    assert CC._start_parts(_env(_record(tmp_path))) is not None
    assert CC._start_parts(_env(_record(tmp_path, **change))) is None


def test_a_record_of_500_parts_and_8_roots_is_still_read(tmp_path):
    parts = {"p%d.py" % n: [n % 8] for n in range(500)}
    got = CC._start_parts(_env(dict(_record(tmp_path, parts=parts), roots=[str(tmp_path)] * 8)))
    assert got is not None and len(got) == 500


@pytest.mark.parametrize("raw", ["", "not json", "[]", "null", "7", '{"schema": '], ids=repr)
def test_a_record_that_is_not_a_json_object_gives_none_through_report(tmp_path, raw):
    local, cloud = _pair(tmp_path)
    env = dict(_env(raw), **{cloud_pass.ENVIRONMENT_ENV: ENV_ID})
    obj = CC.report(env=env, cwd=cloud.cwd, root=cloud.root, nonce=NONCE, confirm_fn=_confirm(),
                    identity_fn=lambda cwd: {"author": True, "committer": True})
    assert "startParts" in obj and obj["startParts"] is None


# --- the recorder in the hook ---------------------------------------------------------------

def _plugin_copy(base, name, version, files):
    root = base / name
    for rel, data in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (root / "version.txt").write_text(version + "\n")
    return str(root)


def _open(audit, path):
    audit("open", (path, "r", 0))


def test_a_mid_swap_attributes_each_part_to_the_copy_it_was_opened_from(tmp_path, hook):
    mine = _mine()
    copy_a = _plugin_copy(tmp_path, "a", "0.1.0", {
        "lib/host_model.py": mine["lib/host_model.py"], "lib/cloud_pass.py": b"# older\n",
        HOOK_PART: mine[HOOK_PART]})
    copy_b = _plugin_copy(tmp_path, "b", "0.2.0", {
        "lib/host_model.py": b"# never opened from b\n", "lib/cloud_pass.py": mine["lib/cloud_pass.py"],
        HOOK_PART: mine[HOOK_PART]})
    link = str(tmp_path / "plugin-link")
    os.symlink(copy_a, link)
    audit, state = hook._start_recorder(link)

    _open(audit, link + "/lib/host_model.py")
    os.unlink(link)
    os.symlink(copy_b, link)
    _open(audit, link + "/lib/cloud_pass.py")

    real_a, real_b = os.path.realpath(copy_a), os.path.realpath(copy_b)
    assert state["roots"] == [real_a, real_b]
    assert state["parts"] == {"lib/host_model.py": {0}, "lib/cloud_pass.py": {1}}
    state["parts"][HOOK_PART] = {1}
    record = {"schema": cloud_pass.START_COPY_SCHEMA, "session": SESSION, "roots": state["roots"],
              "parts": {part: sorted(idx) for part, idx in state["parts"].items()}}
    started = CC._start_parts(_env(record))
    assert started["lib/host_model.py"][0]["version"] == "0.1.0"
    assert started["lib/cloud_pass.py"][0]["version"] == "0.2.0"

    local, cloud = _pair(tmp_path / "world")
    # A's unopened part (cloud_pass) and B's unopened part (host_model) differ, and neither fails
    result = _judge(local, _cloud_report(cloud, startParts=started))
    assert result["action"] == "passed" and result["results"]["startPartsMatch"] is True

    # contrast: the same two opens both from A would have loaded A's older cloud_pass
    os.unlink(link)
    os.symlink(copy_a, link)
    audit2, state2 = hook._start_recorder(link)
    _open(audit2, link + "/lib/host_model.py")
    _open(audit2, link + "/lib/cloud_pass.py")
    state2["parts"][HOOK_PART] = {0}
    record2 = dict(record, roots=state2["roots"],
                   parts={part: sorted(idx) for part, idx in state2["parts"].items()})
    failed = _judge(local, _cloud_report(cloud, startParts=CC._start_parts(_env(record2))))
    assert failed["failedParts"] == ["start"]
    assert "`lib/cloud_pass.py` from plugin 0.1.0" in failed["message"]


def test_the_recorder_maps_bytecode_to_its_source_and_skips_directories_and_outsiders(
        tmp_path, hook):
    copy = _plugin_copy(tmp_path, "a", "0.1.0", {"lib/x.py": b"x", "lib/sub/y.py": b"y"})
    link = str(tmp_path / "link")
    os.symlink(copy, link)
    audit, state = hook._start_recorder(link)
    _open(audit, link + "/lib/__pycache__/x.cpython-312.pyc")
    _open(audit, link + "/lib/__pycache__/x.cpython-312.opt-1.pyc")
    _open(audit, link + "/lib")                      # a directory
    _open(audit, link + "/lib/sub")                  # a directory
    _open(audit, str(tmp_path / "elsewhere.py"))     # outside the plugin
    _open(audit, link + "/../elsewhere.py")          # outside through ..
    _open(audit, link)                               # the plugin folder itself
    assert state["parts"] == {"lib/x.py": {0}}
    assert state["roots"] == [os.path.realpath(copy)]


def test_the_recorder_takes_a_real_path_under_a_known_folder_and_credits_that_folder(tmp_path, hook):
    copy_a = _plugin_copy(tmp_path, "a", "0.1.0", {"lib/x.py": b"x", "lib/y.py": b"y"})
    copy_b = _plugin_copy(tmp_path, "b", "0.2.0", {"lib/x.py": b"x", "lib/y.py": b"y"})
    link = str(tmp_path / "link")
    os.symlink(copy_a, link)
    audit, state = hook._start_recorder(link)
    _open(audit, link + "/lib/x.py")
    os.unlink(link)
    os.symlink(copy_b, link)
    # a file opened by the real path of the folder the link pointed to earlier is that folder's
    _open(audit, os.path.join(os.path.realpath(copy_a), "lib", "y.py"))
    # one opened by the new folder's real path is credited to the folder it is under
    _open(audit, os.path.join(os.path.realpath(copy_b), "lib", "z.py"))
    assert state["roots"] == [os.path.realpath(copy_a), os.path.realpath(copy_b)]
    assert state["parts"] == {"lib/x.py": {0}, "lib/y.py": {0}, "lib/z.py": {1}}


def test_the_audit_function_never_raises(tmp_path, hook):
    copy = _plugin_copy(tmp_path, "a", "0.1.0", {"lib/x.py": b"x"})
    link = str(tmp_path / "link")
    os.symlink(copy, link)
    audit, state = hook._start_recorder(link)

    class Odd:
        def __fspath__(self):
            raise RuntimeError("no path")

    class Bad:
        def __fspath__(self):
            return 7

    # edge 8: a bytes path is read, an int descriptor is ignored, and nothing raises
    audit("open", (link.encode() + b"/lib/x.py", "r", 0))
    assert state["parts"] == {"lib/x.py": {0}}
    before = json.dumps(state, default=sorted)
    for args in ((3, "r", 0), (), None, (None,), ("\x00bad", "r", 0), (Odd(),), (Bad(),), ([],),
                 (b"\xff\xfe/lib/x.py", "r", 0), ("", "r", 0)):
        audit("open", args)
    audit("exec", (link + "/lib/y.py",))
    audit("open", 5)
    audit(None, None)
    assert json.dumps(state, default=sorted) == before
    # a vanished link: the folder cannot be resolved, and the call still returns
    os.unlink(link)
    audit("open", (link + "/lib/y.py", "r", 0))
    gone, gone_state = hook._start_recorder(str(tmp_path / "never-existed"))
    gone("open", (str(tmp_path / "never-existed" / "lib" / "z.py"), "r", 0))
    gone("open", (str(tmp_path / "elsewhere"), "r", 0))


def test_a_stopped_recorder_notes_nothing(tmp_path, hook):
    copy = _plugin_copy(tmp_path, "a", "0.1.0", {"lib/x.py": b"x"})
    audit, state = hook._start_recorder(copy)
    state["stopped"] = True
    _open(audit, copy + "/lib/x.py")
    assert state["parts"] == {} and state["roots"] == []


def test_the_hook_installs_nothing_when_imported(hook):
    # an audit hook cannot be removed, so only the script run as `__main__` in a cloud session installs one
    assert hook._RECORDER is None and hook._START_ROOT is None and hook._OWN_CODE is None
    assert hook._LINK_ROOT == hook._PLUGIN_ROOT


def test_the_same_bytes_compare_equal_whatever_the_file_name_and_one_character_does_not():
    source = b"import os\nx = 1\n"
    one = compile(source, "/one/hooks/session_start.py", "exec", dont_inherit=True)
    two = compile(source, "/two/other_name.py", "exec", dont_inherit=True)
    assert one == two
    assert one != compile(b"import os\nx = 2\n", "/one/hooks/session_start.py", "exec",
                          dont_inherit=True)


def test_own_copy_matches_compares_the_running_code_with_the_file(tmp_path, hook):
    root = tmp_path / "start-root"
    (root / "hooks").mkdir(parents=True)
    path = root / "hooks" / "session_start.py"
    code = compile(b"x = 1\n", "somewhere/else.py", "exec", dont_inherit=True)
    path.write_bytes(b"x = 1\n")
    assert hook._own_copy_matches(code, str(root)) is True
    path.write_bytes(b"x = 2\n")
    assert hook._own_copy_matches(code, str(root)) is False
    path.write_bytes(b"x = (\n")                      # does not compile
    assert hook._own_copy_matches(code, str(root)) is False
    assert hook._own_copy_matches(code, str(tmp_path / "no-such-root")) is False
    assert hook._own_copy_matches(None, str(root)) is False


def _state(roots, parts):
    return {"roots": list(roots), "parts": {k: set(v) for k, v in parts.items()}, "stopped": False}


def _exported(env_file):
    lines = [ln for ln in env_file.read_text().splitlines()
             if ln.startswith("export %s=" % cloud_pass.START_COPY_ENV)]
    assert len(lines) == 1, lines
    return json.loads(shlex.split(lines[0])[1].split("=", 1)[1])


def test_the_hooks_own_part_follows_the_comparison_alone(tmp_path, monkeypatch, hook):
    env_file = tmp_path / "env"
    env_file.write_text("")
    monkeypatch.setenv("CLAUDE_ENV_FILE", str(env_file))
    start = tmp_path / "start-root"
    (start / "hooks").mkdir(parents=True)
    (start / "hooks" / "session_start.py").write_bytes(b"x = 2\n")
    running = compile(b"x = 1\n", "hooks/session_start.py", "exec", dont_inherit=True)
    other = str(tmp_path / "other")
    # a hook part already noted by an earlier open is dropped when the running code differs
    state = _state([other], {HOOK_PART: [0], "lib/host_model.py": [0]})
    monkeypatch.setattr(hook, "_RECORDER", state)
    monkeypatch.setattr(hook, "_OWN_CODE", running)
    monkeypatch.setattr(hook, "_START_ROOT", str(start))
    hook._write_start_copy(SESSION)
    # edge 9: the hook's own code differing from the file at its start root leaves no hook part
    record = _exported(env_file)
    assert HOOK_PART not in record["parts"] and record["parts"] == {"lib/host_model.py": [0]}
    assert record["session"] == SESSION and record["schema"] == cloud_pass.START_COPY_SCHEMA
    assert state["stopped"] is True

    # the same, with the file equal to the running code: the part is the start root's index
    env_file.write_text("")
    (start / "hooks" / "session_start.py").write_bytes(b"x = 1\n")
    state = _state([other], {"lib/host_model.py": [0]})
    monkeypatch.setattr(hook, "_RECORDER", state)
    hook._write_start_copy(SESSION)
    record = _exported(env_file)
    assert record["roots"] == [other, str(start)]
    assert record["parts"] == {"lib/host_model.py": [0], HOOK_PART: [1]}


def test_the_record_is_not_written_without_a_recorder_an_env_file_or_a_session_id(
        tmp_path, monkeypatch, hook):
    env_file = tmp_path / "env"
    env_file.write_text("")
    running = compile(b"x = 1\n", "f.py", "exec", dont_inherit=True)
    monkeypatch.setattr(hook, "_OWN_CODE", running)
    monkeypatch.setattr(hook, "_START_ROOT", str(tmp_path))
    state = _state([], {})
    monkeypatch.setenv("CLAUDE_ENV_FILE", str(env_file))
    monkeypatch.setattr(hook, "_RECORDER", None)
    hook._write_start_copy(SESSION)
    monkeypatch.setattr(hook, "_RECORDER", state)
    for bad in (None, "", 5, ["s"]):
        hook._write_start_copy(bad)
    monkeypatch.delenv("CLAUDE_ENV_FILE")
    hook._write_start_copy(SESSION)
    assert env_file.read_text() == "" and state["stopped"] is False
    # an env file that cannot be opened is no raise either
    monkeypatch.setenv("CLAUDE_ENV_FILE", str(tmp_path / "no-dir" / "env"))
    hook._write_start_copy(SESSION)


# --- the real hook, in a subprocess ---------------------------------------------------------

def _run_hook(tmp_path, remote):
    """Run the real hook through a symlink to this plugin; (env file, completed process, link)."""
    home = tmp_path / "home"
    codex = tmp_path / "codex"
    repo = tmp_path / "repo"
    for path in (home, codex, repo):
        path.mkdir()
    base = {"PATH": os.environ.get("PATH", ""), "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True, env=base)
    env_file = tmp_path / "claude-env"
    env_file.write_text("")
    env = dict(base, HOME=str(home), CODEX_HOME=str(codex), CLAUDE_CONFIG_DIR=str(home / "cfg"),
               CLAUDE_ENV_FILE=str(env_file), PYTHONDONTWRITEBYTECODE="1")
    if remote:
        env["CLAUDE_CODE_REMOTE"] = "true"
    link = tmp_path / "plugin-link"
    os.symlink(PLUGIN, str(link))
    payload = {"source": "startup", "cwd": str(repo), "session_id": SESSION,
               "transcript_path": str(tmp_path / "transcript.jsonl")}
    done = subprocess.run([sys.executable, "-B", str(link / "hooks" / "session_start.py")],
                          input=json.dumps(payload), cwd=str(repo), env=env, capture_output=True,
                          text=True, timeout=120)
    return env_file, done, link


def test_the_real_hook_records_its_start_parts_and_the_check_reads_them_back(tmp_path):
    env_file, done, _link = _run_hook(tmp_path, remote=True)
    assert done.returncode == 0, done.stderr
    record = _exported(env_file)
    assert record["roots"] == [os.path.realpath(PLUGIN)]
    assert record["session"] == SESSION and record["schema"] == cloud_pass.START_COPY_SCHEMA
    assert HOOK_PART in record["parts"] and "lib/host_model.py" in record["parts"]
    assert set(record["parts"]) <= set(cloud_setup_text.START_HOOK_READS)
    assert all(idx == [0] for idx in record["parts"].values())

    started = CC._start_parts(_env(record))
    assert started is not None and HOOK_PART in started
    assert CC._start_match({"startParts": started}) == (True, None, [])
    local, cloud = _pair(tmp_path / "world")
    result = _judge(local, _cloud_report(cloud, startParts=started))
    assert result["results"]["startPartsMatch"] is True and result["action"] == "passed"


def test_a_local_run_writes_no_start_copy_export(tmp_path):
    env_file, done, _link = _run_hook(tmp_path, remote=False)
    assert done.returncode == 0, done.stderr
    assert cloud_pass.START_COPY_ENV not in env_file.read_text()
    assert "SUPERHEROES_HOST_MODEL" in env_file.read_text()
