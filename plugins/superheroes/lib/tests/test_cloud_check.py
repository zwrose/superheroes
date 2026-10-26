"""Tests for cloud_check: the setup sitting's messages, the cloud-side report and its judgment.

Every fixture project is a real git repository under tmp_path, with its store, home and Claude
config directory under tmp_path too. The reviewer, the record writer and the setting writer are
fakes wherever a test needs to see or force a call; the real record writer and reader run against
the fixture store wherever a test asserts that a record was or was not written. No test starts a
cloud session, runs the reviewer tool or touches the network.
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_check as CC  # noqa: E402
import cloud_pass  # noqa: E402
import cloud_plugin_pin  # noqa: E402
import cloud_setup  # noqa: E402
import cloud_setup_text  # noqa: E402
import core_md  # noqa: E402
import engine_adapter  # noqa: E402
import mode_registry  # noqa: E402
import model_registry  # noqa: E402
import project_config  # noqa: E402
from test_cloud_setup_text import _put, _world  # noqa: E402

VERSION = open(os.path.join(cloud_setup_text._plugin_root(), "version.txt")).read().strip()
ENV_ID = "env_01ABCdef"
OTHER_ENV_ID = "env_09ZYXwvu"
NONCE = "abcd1234efgh"
ACCOUNT = "acct-fixture-one"
NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc).timestamp()
LATER = NOW + 60  # a judgment that starts after a marker stamped NOW may clear it
TODAY = "2026-10-10"
FAR = "2099-12-31"
SOURCE = "https://github.com/acme/superheroes.git"
COMMIT = "0123456789abcdef" * 2 + "01234567"
SUBDIR = "plugins/superheroes"
FACTS = {"verifyCommand": "npm test", "stackTags": ["node"], "threatModel": "single-user",
         "patterns": "- x: a.ts:1"}
FIRST_UNREAD = "**The check did not report back.** I could not read a result from the check session."
OTHER_STAMP = "sha256:" + "0" * 64


# --- fixtures ------------------------------------------------------------------------------

def _build(base, mode=mode_registry.GLOBAL, patterns=FACTS["patterns"]):
    """A project with a core file, and for a global project two more calibration files and the
    stamp file the setup text would have written."""
    base.mkdir(parents=True, exist_ok=True)
    w = _world(base, mode)
    core_md.write(w.cwd, dict(FACTS, patterns=patterns), "confirmed", root=w.root, now="2026-10-01")
    if mode == mode_registry.GLOBAL:
        _put(w, "config/review-crew.md", b"# Crew\nsecond\n")
        _put(w, "doc-policy.json", b'{"docs": "x"}\n')
    w.stamp = cloud_setup.calibration_stamp(cloud_setup_text.stamped_files(w.cwd, w.root))
    if w.stamp != "none":
        _put(w, cloud_setup_text.STAMP_FILE, (w.stamp + "\n").encode())
    return w


def _mirror(base, local, mode, patterns):
    """The cloud machine of `local`: the placed files carry the same bytes, as the setup text
    writes them; a repository's own calibration is its own checkout's, written here as given."""
    base.mkdir(parents=True, exist_ok=True)
    w = _world(base, mode)
    core_md.write(w.cwd, dict(FACTS, patterns=patterns), "confirmed", root=w.root, now="2026-10-01")
    if mode == mode_registry.GLOBAL:
        for rel, data in cloud_setup_text.calibration_files(local.cwd, local.root).items():
            _put(w, rel, data)
        _put(w, cloud_setup_text.STAMP_FILE, (local.stamp + "\n").encode())
    w.stamp = local.stamp
    return w


def _pair(tmp_path, mode=mode_registry.GLOBAL, cloud_patterns=FACTS["patterns"]):
    local = _build(tmp_path / "local", mode)
    return local, _mirror(tmp_path / "cloud", local, mode, cloud_patterns)


def _confirm(answered=True, lapses=FAR, reason=None):
    return lambda env: {"schema": cloud_pass.CONFIRMATION_SCHEMA, "reviewerAnswered": answered,
                        "passLapses": lapses, "reason": reason}


def _cloud_report(cloud, **over):
    obj = CC.report(env={cloud_pass.ENVIRONMENT_ENV: ENV_ID}, cwd=cloud.cwd, root=cloud.root,
                    nonce=NONCE, confirm_fn=_confirm(),
                    identity_fn=lambda cwd: {"author": True, "committer": True})
    obj.update(over)
    return obj


def _judge(local, obj, **kw):
    text = CC.report_line(obj) if isinstance(obj, dict) else obj
    args = dict(environment=ENV_ID, nonce=NONCE, account=ACCOUNT, root=local.root, env=local.env,
                now=NOW, project_name="demo")
    args.update(kw)
    return CC.judge(local.cwd, text, **args)


def _record_state(w):
    return cloud_setup.read(w.cwd, ACCOUNT, w.root)["state"]


def _setting(w):
    return cloud_setup.read(w.cwd, ACCOUNT, w.root)["setting"]


def _turn_on(w):
    written = core_md.write_project_config_item(
        w.cwd, project_config.CLOUD_BUILDS_SLUG, True, root=w.root)
    assert written == {"action": "written"} and _setting(w) is True


def _first(result):
    return result["message"].split("\n\n")[0]


def _failed_on(result, parts, first_paragraph):
    assert result["action"] == "failed", result
    assert result["failedParts"] == parts, result
    assert result["recordWritten"] is False
    assert _first(result) == first_paragraph, result["message"]


def _ok_report(cloud):
    return _cloud_report(cloud)


@pytest.fixture
def composing(monkeypatch):
    """The setup text writer with the plugin's source given, so no plugin record file is needed."""
    real = cloud_setup_text.compose

    def compose(cwd, **kw):
        return real(cwd, plugin_source=SOURCE, plugin_commit=COMMIT, plugin_subdir=SUBDIR, **kw)

    monkeypatch.setattr(cloud_setup_text, "compose", compose)
    return real


# --- setup_message -------------------------------------------------------------------------

def _setup_message_literal(header):
    return (
        "**Setting up cloud builds for demo.** You do these by hand, once. It takes about ten "
        "minutes.\n\n"
        "1. Make a cloud environment for this project on claude.ai, then run /remote-env in Claude "
        "Code on this computer and pick it. I read which one you picked, so there's no id to copy, "
        "and every build names this environment itself. Once this account's first check passes, I "
        "keep the environment, so later checks need no pick unless you move this account to another "
        "one.\n"
        "2. Paste the setup text into it. I've written it below.\n"
        "3. Sign in once to the reviewer on your machine, with a sign-in kept apart from your main "
        "one. The pass is made from it. You only do this the first time on this machine, and I'll "
        "walk you through it.\n"
        "4. Paste the reviewer pass into the environment. Run the pass command on your machine and "
        "it puts the pass on your clipboard.\n\n"
        "**Two things to know before you start.**\n\n"
        "The reviewer pass will sit in that environment's settings, and any session started in "
        "that environment can read it. It is a separate sign-in from your main one, it cannot "
        "renew itself, and it stops working after 10 days; the exact date isn't known yet.\n\n"
        "Cloud builders do not get your personal instructions or permission rules. They follow "
        "this project's rules and the plugin's rules, and nothing else.\n\n"
        "Tell me when they're done and I'll run a short check.\n\n"
        "**Setup text** " + header + "\n\n"
        "A block to copy and paste. It holds no secret. The pass never goes in here. If this "
        "project needs its own setup commands in the cloud, such as installing its dependencies, "
        "list them in configure (item 17, cloud setup commands) and write new setup text: a step "
        "added by hand under the line that reads \"# The project's own tool steps, if any, go "
        "below this line.\" is lost the next time setup text is pasted."
        " A credential never goes in a listed command: put it in the cloud environment's variables "
        "and reference it as $NAME. The setup text's secret scan catches obvious pastes and is not "
        "a guarantee."
    )


def _message(tmp_path):
    w = _build(tmp_path)
    return w, CC.setup_message(w.cwd, project_name="demo", root=w.root, env=w.env, now=NOW)


def test_setup_message_is_the_approved_words(tmp_path, composing):
    w, result = _message(tmp_path)
    assert result["action"] == "written"
    header = "demo · plugin %s · calibration from 10 Oct" % VERSION
    assert result["header"] == header
    assert result["message"] == _setup_message_literal(header)


def test_setup_message_lists_four_hand_steps_in_order(tmp_path, composing):
    _w, result = _message(tmp_path)
    lines = [l for l in result["message"].splitlines() if l[:3] in ("1. ", "2. ", "3. ", "4. ")]
    assert [l[:3] for l in lines] == ["1. ", "2. ", "3. ", "4. "]
    assert "environment" in lines[0] and "setup text" in lines[1]
    assert "sign in" in lines[2].lower() and "reviewer pass" in lines[3]


def test_setup_message_never_asks_to_change_the_default_environment(tmp_path, composing):
    _w, result = _message(tmp_path)
    # the owner picks the environment with /remote-env; the message never speaks of a default
    assert "default" not in result["message"].lower()


def test_setup_message_carries_the_five_pass_facts_and_the_personal_rules_line(tmp_path, composing):
    _w, result = _message(tmp_path)
    message = result["message"]
    for fact in ("will sit in that environment's settings",
                 "any session started in that environment can read it",
                 "It is a separate sign-in from your main one",
                 "it cannot renew itself",
                 "it stops working after %d days; the exact date isn't known yet"
                 % CC.PASS_LIFETIME_DAYS):
        assert fact in message
    assert CC.PASS_LIFETIME_DAYS == 10
    assert ("Cloud builders do not get your personal instructions or permission rules. They "
            "follow this project's rules and the plugin's rules, and nothing else.") in message


def test_setup_message_returns_composes_text_unchanged(tmp_path, composing):
    w, result = _message(tmp_path)
    expected = composing(w.cwd, now=NOW, project_name="demo", root=w.root, env=w.env,
                         plugin_source=SOURCE, plugin_commit=COMMIT, plugin_subdir=SUBDIR)
    assert result["setupText"] == expected["text"]
    assert result["setupText"] not in result["message"]
    assert result["signedIn"] is False


def test_setup_message_passes_a_compose_refusal_through(tmp_path, monkeypatch):
    w = _build(tmp_path)
    refusal = {"action": "refused", "reason": "calibration-missing", "detail": "No calibration."}
    monkeypatch.setattr(cloud_setup_text, "compose", lambda cwd, **kw: dict(refusal))
    result = CC.setup_message(w.cwd, project_name="demo", root=w.root, env=w.env, now=NOW)
    assert result["action"] == "refused" and result["reason"] == "calibration-missing"
    assert result["message"] == "No calibration."
    assert "setupText" not in result and "text" not in result


# --- sign_in -------------------------------------------------------------------------------

def _home_env(tmp_path, **extra):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return home, dict({"HOME": str(home)}, **extra)


def _auth(directory):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "auth.json").write_text("{}")
    return directory / "auth.json"


def test_sign_in_walk_when_no_separate_sign_in(tmp_path):
    home, env = _home_env(tmp_path)
    result = CC.sign_in(env)
    assert result["action"] == "checked" and result["signedIn"] is False
    # bites on: any change to the walk text, including the mkdir -p lead on the command line
    assert result["message"] == (
        "The reviewer needs its own sign-in on this machine, kept apart from your main one. Run "
        "this in a terminal and finish the sign-in in your browser:\n\n"
        "    mkdir -p %(h)s/.codex-cloud && CODEX_HOME=%(h)s/.codex-cloud codex login\n\n"
        "Tell me when it's done and I'll check it." % {"h": home})


def test_sign_in_command_creates_a_missing_home_before_signing_in(tmp_path):
    import shlex
    missing = tmp_path / "not-created-yet"
    home, env = _home_env(tmp_path, **{cloud_pass.SEPARATE_HOME_ENV: str(missing)})
    command = CC.sign_in(env)["message"].split("\n\n")[1].strip()
    quoted = shlex.quote(str(missing))
    # bites on: the command losing its `mkdir -p <home> &&` lead, so codex meets a missing home
    assert not missing.exists()
    assert command == "mkdir -p %s && %s=%s codex login" % (quoted, cloud_pass._CODEX_HOME_ENV, quoted)


def test_sign_in_message_names_the_quoted_home_twice_and_makes_it_once(tmp_path):
    import shlex
    tricky = tmp_path / "rev$UNSET_X home"
    home, env = _home_env(tmp_path, **{cloud_pass.SEPARATE_HOME_ENV: str(tricky)})
    message = CC.sign_in(env)["message"]
    # bites on: the home appearing a different number of times, or mkdir -p repeated or dropped
    assert message.count(shlex.quote(str(tricky))) == 2 and message.count("mkdir -p") == 1


def test_sign_in_in_place(tmp_path):
    home, env = _home_env(tmp_path)
    _auth(home / ".codex-cloud")
    assert CC.sign_in(env) == {"action": "checked", "signedIn": True,
                               "message": "The separate reviewer sign-in is in place."}


def test_sign_in_refuses_the_main_sign_in_as_the_separate_one(tmp_path):
    home, env = _home_env(tmp_path)
    main = _auth(home / ".codex")
    # axis: the main sign-in file never counts as the separate one
    same = dict(env, **{cloud_pass.SEPARATE_HOME_ENV: str(home / ".codex")})
    assert CC.sign_in(same)["signedIn"] is False
    # axis: no login command ever targets the main sign-in's home
    refusal = CC.sign_in(same)["message"]
    assert "codex login" not in refusal and cloud_pass.SEPARATE_HOME_ENV in refusal
    linked = home / "linked"
    linked.mkdir()
    os.symlink(main, linked / "auth.json")
    through_link = dict(env, **{cloud_pass.SEPARATE_HOME_ENV: str(linked)})
    assert CC.sign_in(through_link)["signedIn"] is False
    assert CC.sign_in(dict(env, **{cloud_pass.SEPARATE_HOME_ENV: str(home / "elsewhere")})
                      )["signedIn"] is False


def test_sign_in_command_quotes_the_home_literally(tmp_path):
    # axis: the printed sign-in command carries the home literally (run.stdout) and creates it (is_dir) — see bite-proof record c8a_wo1.md
    import shlex
    import subprocess
    tricky = tmp_path / "rev$UNSET_X home"
    home, env = _home_env(tmp_path, **{cloud_pass.SEPARATE_HOME_ENV: str(tricky)})
    command = CC.sign_in(env)["message"].split("\n\n")[1].strip()
    run = subprocess.run(["/bin/sh", "-c", "codex() { printf '%s' \"$CODEX_HOME\"; }\n" + command],
                         capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"})
    assert run.stdout == str(tricky)
    # bites on: either occurrence of the home being quoted differently from the other
    quoted = shlex.quote(str(tricky))
    assert command == "mkdir -p %s && CODEX_HOME=%s codex login" % (quoted, quoted)
    assert tricky.is_dir()


def test_setup_message_names_the_sign_ins_real_expiry_when_readable(tmp_path, composing):
    # axis: the setup message names the expiry read from the sign-in's own token, never a guessed one — see bite-proof record c8a_wo1.md
    import base64
    w = _build(tmp_path)
    exp = int(datetime(2026, 10, 12, tzinfo=timezone.utc).timestamp())
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode().rstrip("=")
    signin = tmp_path / "sep"
    signin.mkdir()
    (signin / "auth.json").write_text(json.dumps({"tokens": {
        "access_token": "h.%s.s" % payload, "id_token": "i"}}))
    env = dict(w.env, **{cloud_pass.SEPARATE_HOME_ENV: str(signin)})
    message = CC.setup_message(w.cwd, project_name="demo", root=w.root, env=env, now=NOW)["message"]
    assert "it stops working on 2026-10-12." in message
    assert "10 days" not in message and "unknown" not in message


# --- setup_text ----------------------------------------------------------------------------

def test_setup_text_returns_new_text_from_the_writer(tmp_path, composing):
    w = _build(tmp_path)
    expected = composing(w.cwd, now=NOW, project_name="demo", root=w.root, env=w.env,
                         plugin_source=SOURCE, plugin_commit=COMMIT, plugin_subdir=SUBDIR)
    result = CC.setup_text(w.cwd, project_name="demo", root=w.root, env=w.env, now=NOW)
    assert result == {
        "action": "written", "setupText": expected["text"], "header": expected["header"],
        "message": "**Setup text** %s\n\nPaste this over the whole setup-script field of the "
                   "cloud environment. It holds no secret. The pass never goes in here."
                   % expected["header"]}


def test_setup_text_passes_a_compose_refusal_through(tmp_path, monkeypatch):
    w = _build(tmp_path)
    monkeypatch.setattr(cloud_setup_text, "compose", lambda cwd, **kw: {
        "action": "refused", "reason": "stamp-unavailable", "detail": "No stamp."})
    result = CC.setup_text(w.cwd, root=w.root)
    assert (result["action"], result["reason"], result["message"]) == (
        "refused", "stamp-unavailable", "No stamp.")


# --- report --------------------------------------------------------------------------------

def test_report_line_round_trips_through_judge(tmp_path):
    local, cloud = _pair(tmp_path)
    obj = _cloud_report(cloud)
    assert obj["schema"] == CC.REPORT_SCHEMA and obj["nonce"] == NONCE
    assert obj["environment"] == ENV_ID and obj["pluginVersion"] == VERSION
    assert obj["placedStamp"] == obj["stampFile"] == local.stamp
    line = CC.report_line(obj)
    assert line.startswith("SUPERHEROES-CLOUD-CHECK {") and "\n" not in line
    carried = dict(obj, digest=CC.report_digest(obj))
    assert line == "SUPERHEROES-CLOUD-CHECK " + json.dumps(carried, sort_keys=True,
                                                         separators=(",", ":"))
    result = _judge(local, line)
    assert result["action"] == "passed" and result["failedParts"] == []
    assert result["results"] == {"versionMatches": True, "pinMatches": None,
                                 "dependencyHookMatches": True, "calibrationMatches": True,
                                 "reviewerAnswered": True, "environmentMatches": True,
                                 "identityPresent": True}
    assert result["recordWritten"] is True and result["settingSwitchedOff"] is False
    state = cloud_setup.read(local.cwd, ACCOUNT, local.root)
    assert state["ready"] is True
    record = state["record"]
    assert record["schema"] == cloud_setup.SCHEMA
    assert record["account"] == ACCOUNT
    assert record["environment"] == ENV_ID
    assert record["pluginVersion"] == VERSION
    assert record["picksUpVersion"] is False
    assert record["calibrationStamp"] == local.stamp
    assert record["calibrationDate"] == TODAY
    assert record["passLapses"] == FAR
    assert record["checkedAt"] == TODAY


def test_report_never_raises_in_an_empty_session(tmp_path, monkeypatch):
    monkeypatch.setattr(cloud_setup_text, "_plugin_root", lambda: str(tmp_path / "no-plugin"))

    def raising(env):
        raise RuntimeError("no reviewer")

    nowhere = str(tmp_path / "nowhere")
    obj = CC.report(env={}, cwd=nowhere, root=str(tmp_path / "no-store"), nonce="short",
                    confirm_fn=raising)
    # a session with no store and no calibration directory has nothing placed and nothing carried
    assert obj == {
        "schema": CC.REPORT_SCHEMA, "nonce": None, "environment": None,
        "pluginVersion": None, "pluginCommit": None, "placedStamp": "none", "stampFile": None,
        "repoStamp": "none", "confirmation": {"schema": cloud_pass.CONFIRMATION_SCHEMA, "reviewerAnswered": False,
                         "passLapses": None, "reason": "confirm-raised"},
        "identity": {"author": False, "committer": False}}
    line = CC.report_line(obj)
    assert line.startswith("SUPERHEROES-CLOUD-CHECK ") and "\n" not in line
    assert json.loads(line.split(" ", 1)[1]) == dict(obj, digest=CC.report_digest(obj))
    real = CC.report(env={}, cwd=nowhere, root=str(tmp_path / "no-store"))
    assert real["confirmation"]["reviewerAnswered"] is False and real["environment"] is None


def test_report_takes_only_well_formed_nonce_and_environment(tmp_path):
    w = _build(tmp_path)
    for bad_nonce in ("short", "x" * 65, "has space1234", "cafécafécafé", 12345678, None):
        assert CC.report(env={}, cwd=w.cwd, root=w.root, nonce=bad_nonce,
                         confirm_fn=_confirm())["nonce"] is None
    for bad_env in ("env_", "env-01", "env_01 x", "env_01\n", "", None):
        got = CC.report(env={cloud_pass.ENVIRONMENT_ENV: bad_env}, cwd=w.cwd, root=w.root,
                        confirm_fn=_confirm())
        assert got["environment"] is None
    assert CC.report(env={}, cwd=w.cwd, root=w.root, nonce="a" * 64,
                     confirm_fn=_confirm())["nonce"] == "a" * 64


# --- judge: one test per fail-closed edge --------------------------------------------------

def test_judge_edge1_a_report_with_another_nonce_is_unread(tmp_path):
    local, cloud = _pair(tmp_path)
    other = CC.report(env={cloud_pass.ENVIRONMENT_ENV: ENV_ID}, cwd=cloud.cwd, root=cloud.root,
                      nonce="zzzzzzzz9999", confirm_fn=_confirm())
    # axis: a report answers only the check that was started with its nonce
    result = _judge(local, other)
    assert result["action"] == "unread" and result["failedParts"] == ["unread"]
    assert result["recordWritten"] is False and _first(result) == FIRST_UNREAD
    assert set(result["results"].values()) == {None}
    assert _record_state(local) == "none"
    # an object whose own nonce was changed after the report was made is unread too
    forged = dict(_ok_report(cloud), nonce="zzzzzzzz9999")
    assert _judge(local, forged)["action"] == "unread"
    assert _record_state(local) == "none"


def test_judge_edge2_two_different_lines_with_the_nonce_are_unread(tmp_path):
    local, cloud = _pair(tmp_path)
    one = CC.report_line(_ok_report(cloud))
    two = CC.report_line(_cloud_report(cloud, pluginVersion="9.9.9"))
    result = _judge(local, "first\n%s\nthen\n%s\n" % (one, two))
    assert result["action"] == "unread" and result["failedParts"] == ["unread"]
    assert _first(result) == FIRST_UNREAD
    assert _record_state(local) == "none"
    # the same line twice is one report
    assert _judge(local, "%s\n%s\n" % (one, one), now=LATER)["action"] == "passed"


def test_judge_edge3_a_wrong_or_missing_environment_fails_on_environment(tmp_path):
    local, cloud = _pair(tmp_path)
    for bad in (None, OTHER_ENV_ID):
        # axis: the check must have run in the environment whose id the owner gave
        result = _judge(local, _cloud_report(cloud, environment=bad))
        _failed_on(result, ["environment"], "**The check failed on one part.** The check ran in a "
                   "different environment from the one you picked with /remote-env, or that "
                   "environment has no pass block in it yet.")
        assert result["results"]["environmentMatches"] is False
        assert _record_state(local) == "none"


def test_judge_edge4_a_different_or_missing_cloud_version_fails_on_version(tmp_path):
    local, cloud = _pair(tmp_path)
    for bad in ("0.0.1", None, 42):
        # axis: the cloud's plugin must be the version this machine runs
        result = _judge(local, _cloud_report(cloud, pluginVersion=bad))
        assert result["action"] == "failed" and result["failedParts"] == ["version"]
        assert result["results"]["versionMatches"] is False and result["recordWritten"] is False
        assert _first(result).startswith("**The check failed on one part.** The cloud's plugin is ")
        assert _record_state(local) == "none"


def test_judge_edge5_a_different_placed_stamp_fails_on_calibration(tmp_path):
    local, cloud = _pair(tmp_path)
    result = _judge(local, _cloud_report(cloud, placedStamp=OTHER_STAMP))
    _failed_on(result, ["calibration"], "**The check failed on one part.** The cloud's calibration "
               "doesn't match this machine's.")
    assert _record_state(local) == "none"


def test_judge_edge5_a_different_stamp_file_fails_on_calibration(tmp_path):
    local, cloud = _pair(tmp_path)
    result = _judge(local, _cloud_report(cloud, stampFile=OTHER_STAMP))
    _failed_on(result, ["calibration"], "**The check failed on one part.** The cloud's calibration "
               "doesn't match this machine's.")
    assert _record_state(local) == "none"


def test_judge_edge5_a_missing_stamp_file_fails_when_files_were_placed(tmp_path):
    local, cloud = _pair(tmp_path)
    assert local.stamp.startswith("sha256:")
    result = _judge(local, _cloud_report(cloud, stampFile=None))
    _failed_on(result, ["calibration"], "**The check failed on one part.** The cloud's calibration "
               "doesn't match this machine's.")
    assert _record_state(local) == "none"


def test_judge_edge5_a_stamp_file_fails_when_nothing_was_placed(tmp_path):
    local, cloud = _pair(tmp_path, mode_registry.IN_REPO)
    assert local.stamp == "none"
    result = _judge(local, _cloud_report(cloud, stampFile=local.stamp))
    _failed_on(result, ["calibration"], "**The check failed on one part.** The cloud's calibration "
               "doesn't match this machine's.")
    assert _record_state(local) == "none"


def test_judge_edge5_a_different_repository_stamp_fails_on_calibration(tmp_path):
    local, cloud = _pair(tmp_path, mode_registry.IN_REPO)
    result = _judge(local, _cloud_report(cloud, repoStamp=OTHER_STAMP))
    _failed_on(result, ["calibration"], "**The check failed on one part.** The cloud's calibration "
               "doesn't match this machine's.")
    assert _record_state(local) == "none"


def test_judge_edge5_a_local_stamp_that_cannot_be_computed_fails_on_calibration(
        tmp_path, monkeypatch):
    local, cloud = _pair(tmp_path)
    obj = _cloud_report(cloud)

    def broken(cwd, root=None):
        raise OSError("unreadable")

    monkeypatch.setattr(cloud_setup_text, "stamped_files", broken)
    result = _judge(local, obj)
    _failed_on(result, ["calibration"], "**The check failed on one part.** The cloud's calibration "
               "doesn't match this machine's.")
    assert _record_state(local) == "none"
    monkeypatch.undo()
    monkeypatch.setattr(CC, "repo_calibration_stamp", broken)
    _failed_on(_judge(local, obj), ["calibration"], "**The check failed on one part.** The cloud's "
               "calibration doesn't match this machine's.")
    assert _record_state(local) == "none"


def test_judge_edge6_a_reviewer_that_did_not_answer_or_a_lapsed_pass_fails_on_reviewer(tmp_path):
    local, cloud = _pair(tmp_path)
    first = "**The check failed on one part.** The reviewer did not answer, so the pass is " \
            "missing or was pasted wrong."
    cases = [
        {"reviewerAnswered": False, "passLapses": FAR},
        {"reviewerAnswered": True, "passLapses": None},
        {"reviewerAnswered": True, "passLapses": "soon"},
        {"reviewerAnswered": True, "passLapses": "2026-13-45"},
        {"reviewerAnswered": True, "passLapses": "2026-10-09"},
        {"reviewerAnswered": True, "passLapses": 20261231},
        {"reviewerAnswered": True},
    ]
    for case in cases:
        confirmation = {"schema": cloud_pass.CONFIRMATION_SCHEMA, "reason": None}
        confirmation.update(case)
        # axis: the pass is accepted only when the reviewer answered and the pass has not lapsed
        result = _judge(local, _cloud_report(cloud, confirmation=confirmation))
        _failed_on(result, ["reviewer"], first)
        assert result["results"]["reviewerAnswered"] is False, case
        assert _record_state(local) == "none", case
    for truthy in ("true", 1, "yes", None):
        confirmation = {"schema": cloud_pass.CONFIRMATION_SCHEMA, "reviewerAnswered": truthy,
                        "passLapses": FAR, "reason": None}
        result = _judge(local, _cloud_report(cloud, confirmation=confirmation))
        assert result["action"] == "unread" and result["failedParts"] == ["unread"], truthy
        assert _record_state(local) == "none"


def test_judge_a_pass_that_lapses_today_still_passes(tmp_path):
    local, cloud = _pair(tmp_path)
    confirmation = _confirm(lapses=TODAY)(None)
    assert _judge(local, _cloud_report(cloud, confirmation=confirmation))["action"] == "passed"
    assert _record_state(local) == "ready"


def test_judge_edge7_an_unreadable_account_fails_on_record(tmp_path):
    local, cloud = _pair(tmp_path)
    calls = []
    result = _judge(local, _ok_report(cloud), account=None,
                    record_fn=lambda *a, **k: calls.append(k) or {"action": "written"})
    _failed_on(result, ["record"], "**The check failed on one part.** The check passed, but I "
               "could not finish saving the result on this machine.")
    assert calls == [] and _record_state(local) == "none"


def test_judge_resolves_the_launching_account_itself_when_none_is_given(tmp_path):
    # axis: a judgment given no account reads the launching account itself and records against it — see bite-proof record c8a_wo1.md
    local, cloud = _pair(tmp_path)
    config = local.env["CLAUDE_CONFIG_DIR"]
    os.makedirs(config, exist_ok=True)
    with open(os.path.join(config, ".claude.json"), "w", encoding="utf-8") as fh:
        json.dump({"oauthAccount": {"accountUuid": ACCOUNT}}, fh)
    result = CC.judge(local.cwd, CC.report_line(_ok_report(cloud)), environment=ENV_ID,
                      nonce=NONCE, root=local.root, env=local.env, now=NOW, project_name="demo")
    assert result["action"] == "passed"
    assert _record_state(local) == "ready"


def test_judge_edge8_a_refused_or_raising_record_write_fails_on_record(tmp_path):
    local, cloud = _pair(tmp_path)

    def raising(*a, **k):
        raise OSError("disk")

    for fake in (lambda *a, **k: {"action": "refused", "reason": "store-locked"},
                 lambda *a, **k: None, raising):
        # axis: a record write that did not report written is never reported as a pass
        result = _judge(local, _ok_report(cloud), record_fn=fake)
        _failed_on(result, ["record"], "**The check failed on one part.** The check passed, but I "
                   "could not finish saving the result on this machine.")
        assert _record_state(local) == "none"
    assert _judge(local, _ok_report(cloud), now=LATER)["action"] == "passed"


def test_judge_a_repeat_passing_check_is_a_pass_and_keeps_an_on_setting(tmp_path):
    local, cloud = _pair(tmp_path)
    _turn_on(local)
    assert _judge(local, _ok_report(cloud))["action"] == "passed"
    # the same day, the same report: the real writer answers noop, which is still a pass
    again = _judge(local, _ok_report(cloud))
    assert again["action"] == "passed" and again["recordWritten"] is True
    assert _setting(local) is True and _record_state(local) == "ready"


def test_judge_edge8_the_record_write_gets_the_fields_of_the_report(tmp_path):
    local, cloud = _pair(tmp_path)
    seen = []
    result = _judge(local, _ok_report(cloud),
                    record_fn=lambda cwd, **kw: seen.append((cwd, kw)) or {"action": "written"})
    assert result["action"] == "passed"
    assert seen == [(local.cwd, {
        "account": ACCOUNT, "environment": ENV_ID, "plugin_version": VERSION,
        "picks_up_version": False, "calibration_stamp": local.stamp, "calibration_date": TODAY,
        "pass_lapses": FAR, "checked_at": TODAY, "root": local.root})]


def test_judge_edge9_a_failure_switches_an_on_setting_off(tmp_path):
    local, cloud = _pair(tmp_path)
    _turn_on(local)
    # axis: a failed check leaves cloud builds off
    result = _judge(local, _cloud_report(cloud, confirmation=_confirm(answered=False)(None)))
    assert result["action"] == "failed" and result["failedParts"] == ["reviewer"]
    assert result["settingSwitchedOff"] is True and result["recordWritten"] is False
    assert _setting(local) is False and _record_state(local) == "none"
    assert result["message"] == (
        "**The check failed on one part.** The reviewer did not answer, so the pass is missing or "
        "was pasted wrong.\n\nCloud builds stay off. They were on for this project, so I've "
        "switched them off. To fix it, paste a fresh pass into the environment and say \"check "
        "again\".")


def test_judge_edge9_the_switch_off_goes_through_the_settings_write_path(tmp_path):
    local, cloud = _pair(tmp_path)
    _turn_on(local)
    calls = []
    result = _judge(local, _cloud_report(cloud, pluginVersion="0.0.1"),
                    set_fn=lambda *a, **k: calls.append((a, k)) or {"action": "written"})
    assert result["settingSwitchedOff"] is True and result["failedParts"] == ["version"]
    assert calls == [((local.cwd, project_config.CLOUD_BUILDS_SLUG, False),
                      {"root": local.root, "project_name": "demo"})]


def test_judge_edge9_a_refused_or_raising_switch_off_adds_the_setting_part(tmp_path):
    local, cloud = _pair(tmp_path)
    _turn_on(local)

    def raising(*a, **k):
        raise OSError("locked")

    for fake in (lambda *a, **k: {"action": "refused", "reason": "profile-absent"}, raising,
                 lambda *a, **k: None):
        result = _judge(local, _cloud_report(cloud, pluginVersion="0.0.1"), set_fn=fake)
        assert result["action"] == "failed" and result["failedParts"] == ["version", "setting"]
        assert result["settingSwitchedOff"] is False and result["recordWritten"] is False
        assert _setting(local) is True
        assert result["message"].split("\n\n")[0].startswith("**The check failed on 2 parts.**")
        assert "I could not switch cloud builds off." in _first(result)
        # axis: a failed switch-off is never answered with the builds being off
        assert "Cloud builds are still on." in result["message"]
        assert "Cloud builds stay off" not in result["message"]
        assert "switched them off" not in result["message"]
        assert result["message"].endswith("paste the new setup text into the environment, then "
                                          "switch them off in configure and say \"check again\".")


def test_judge_edge9_an_unread_report_with_a_refused_or_raising_switch_off_says_so(tmp_path):
    # axis: an unread report whose switch-off did not happen says the builds are still on — see bite-proof record c8a_wo1.md
    local, cloud = _pair(tmp_path)
    _turn_on(local)

    def raising(*a, **k):
        raise OSError("locked")

    for fake in (lambda *a, **k: {"action": "refused", "reason": "profile-absent"},
                 lambda *a, **k: {"action": "deferred", "reason": "lock-contended"}, raising,
                 lambda *a, **k: None):
        result = _judge(local, "no report here", set_fn=fake)
        assert result["action"] == "unread" and result["failedParts"] == ["unread", "setting"]
        assert result["settingSwitchedOff"] is False and _setting(local) is True
        assert result["message"] == (
            "**The check did not report back.** I could not read a result from the check "
            "session.\n\nCloud builds are still on: I could not switch them off. Switch them off "
            "in configure, then say \"check again\" and I'll run it once more.")
        assert "stay off" not in result["message"]


def test_judge_a_report_altered_after_it_was_made_is_unread(tmp_path):
    local, cloud = _pair(tmp_path)
    failing = _cloud_report(cloud, confirmation=_confirm(answered=False)(None))
    line = CC.report_line(failing)
    altered = line.replace('"reviewerAnswered":false', '"reviewerAnswered":true')
    assert altered != line
    # axis: a copy that changed the reviewer's answer is not read, so no setup record is written
    result = _judge(local, altered)
    assert result["action"] == "unread" and _record_state(local) == "none"
    for old, new in ((VERSION, "9.9.9"), (FAR, "2999-01-01")):
        good = CC.report_line(_ok_report(cloud))
        assert old in good
        assert _judge(local, good.replace(old, new))["action"] == "unread"
    # a line with its digest removed is not read either
    stripped = json.loads(CC.report_line(_ok_report(cloud)).split(" ", 1)[1])
    del stripped["digest"]
    assert _judge(local, "SUPERHEROES-CLOUD-CHECK " + json.dumps(stripped))["action"] == "unread"
    assert _record_state(local) == "none"


def test_judge_edge9_a_failure_with_the_setting_off_does_not_touch_it(tmp_path):
    local, cloud = _pair(tmp_path)
    calls = []
    result = _judge(local, _cloud_report(cloud, pluginVersion="0.0.1"),
                    set_fn=lambda *a, **k: calls.append(a) or {"action": "written"})
    assert calls == [] and result["settingSwitchedOff"] is False
    assert "switched them off" not in result["message"]


def test_judge_edge10_a_passed_check_never_changes_the_setting(tmp_path):
    for turn_on in (False, True):
        local, cloud = _pair(tmp_path / ("on" if turn_on else "off"))
        if turn_on:
            _turn_on(local)
        calls = []
        result = _judge(local, _ok_report(cloud),
                        set_fn=lambda *a, **k: calls.append(a) or {"action": "written"})
        assert result["action"] == "passed" and result["settingSwitchedOff"] is False
        assert calls == [] and _setting(local) is turn_on


def test_judge_edge11_a_malformed_environment_is_unread_and_still_switches_off(tmp_path):
    local, cloud = _pair(tmp_path)
    for bad in ("env-01ABCdef", "", None, "env_", "env_01 ABC", "env_01ABCdef\n", 7):
        result = _judge(local, _ok_report(cloud), environment=bad)
        assert result["action"] == "unread" and result["failedParts"] == ["unread"], bad
        assert _first(result) == FIRST_UNREAD and _record_state(local) == "none"
    for bad in ("short", "has space 123", "x" * 65, None, 12345678):
        result = _judge(local, _ok_report(cloud), nonce=bad)
        assert result["action"] == "unread" and _record_state(local) == "none", bad
    _turn_on(local)
    result = _judge(local, _ok_report(cloud), environment="env-01ABCdef")
    assert result["action"] == "unread" and result["settingSwitchedOff"] is True
    assert _setting(local) is False and _record_state(local) == "none"
    assert result["message"] == (
        "**The check did not report back.** I could not read a result from the check session.\n\n"
        "Cloud builds stay off. They were on for this project, so I've switched them off. Say "
        "\"check again\" and I'll run it once more.")


def test_judge_reads_nothing_from_a_non_report(tmp_path):
    local, cloud = _pair(tmp_path)
    good = _ok_report(cloud)
    wrong_schema = dict(good, schema="cloud-check-report/2")
    gone = {k: v for k, v in good.items() if k != "stampFile"}
    for text in ("", "nothing here", "SUPERHEROES-CLOUD-CHECK", "SUPERHEROES-CLOUD-CHECK {broken",
                 "SUPERHEROES-CLOUD-CHECK  " + json.dumps(good), "SUPERHEROES-CLOUD-CHECK [1]",
                 "xSUPERHEROES-CLOUD-CHECK " + json.dumps(good), wrong_schema, gone, None, 5):
        assert _judge(local, text)["action"] == "unread", text
        assert _record_state(local) == "none"


# --- judge: calibration of the repository and of the stamp file ---------------------------

def test_judge_in_repository_project_fails_when_a_core_layer_differs(tmp_path):
    local, cloud = _pair(tmp_path, mode_registry.IN_REPO, cloud_patterns="- other: b.ts:2")
    obj = _cloud_report(cloud)
    assert obj["placedStamp"] == local.stamp == "none" and obj["stampFile"] is None
    assert obj["repoStamp"] != CC.repo_calibration_stamp(local.cwd)
    # axis: the calibration the repository carries must match this machine's
    result = _judge(local, obj)
    _failed_on(result, ["calibration"], "**The check failed on one part.** The cloud's calibration "
               "doesn't match this machine's.")
    assert _record_state(local) == "none"
    same_local, same_cloud = _pair(tmp_path / "again", mode_registry.IN_REPO)
    assert _judge(same_local, _cloud_report(same_cloud))["action"] == "passed"


def test_judge_accepts_an_absent_stamp_file_only_when_nothing_was_placed(tmp_path):
    local, cloud = _pair(tmp_path / "in", mode_registry.IN_REPO)
    # axis: the stamp file is absent exactly when nothing was placed
    absent = _cloud_report(cloud)
    assert absent["stampFile"] is None
    wrongly_there = _judge(local, _cloud_report(cloud, stampFile=OTHER_STAMP))
    assert wrongly_there["failedParts"] == ["calibration"]
    assert _record_state(local) == "none"
    assert _judge(local, absent, now=LATER)["action"] == "passed"
    placed_local, placed_cloud = _pair(tmp_path / "out")
    missing = _judge(placed_local, _cloud_report(placed_cloud, stampFile=None))
    assert missing["failedParts"] == ["calibration"]
    assert _record_state(placed_local) == "none"


def test_repo_calibration_stamp_covers_every_layer_file_and_ignores_the_setting(tmp_path):
    w = _build(tmp_path, mode_registry.IN_REPO)
    directory = os.path.join(w.cwd, os.path.dirname(core_md.in_repo_core_rel_path()))
    before = CC.repo_calibration_stamp(w.cwd)
    _turn_on(w)
    assert CC.repo_calibration_stamp(w.cwd) == before
    with open(os.path.join(directory, "extra.md"), "w") as fh:
        fh.write("extra\n")
    assert CC.repo_calibration_stamp(w.cwd) not in (before, "none")
    bare = tmp_path / "bare"
    bare.mkdir()
    bare_world = _world(bare, mode_registry.IN_REPO)
    assert CC.repo_calibration_stamp(bare_world.cwd) == "none"


def test_repo_calibration_stamp_ignores_a_ds_store(tmp_path):
    w = _build(tmp_path, mode_registry.IN_REPO)
    directory = os.path.join(w.cwd, os.path.dirname(core_md.in_repo_core_rel_path()))
    before = CC.repo_calibration_stamp(w.cwd)
    with open(os.path.join(directory, ".DS_Store"), "wb") as fh:
        fh.write(b"\x00junk")
    assert CC.repo_calibration_stamp(w.cwd) == before


def test_repo_calibration_stamp_ignores_a_guardian_sweep_output(tmp_path):
    w = _build(tmp_path, mode_registry.IN_REPO)
    directory = os.path.join(w.cwd, os.path.dirname(core_md.in_repo_core_rel_path()))
    before = CC.repo_calibration_stamp(w.cwd)
    sweep = os.path.join(directory, "guardian")
    os.makedirs(sweep)
    for name, body in (("report.md", "# sweep\n"), ("latest.json", "{}"), ("vitals.jsonl", "{}\n"),
                       ("ledger.md", "ledger\n")):
        with open(os.path.join(sweep, name), "w") as fh:
            fh.write(body)
    with open(os.path.join(directory, "core.md.lock"), "w") as fh:
        fh.write("1")
    # detector: a Guardian sweep output (or lock file) that changes the fingerprint goes red here
    assert CC.repo_calibration_stamp(w.cwd) == before


def test_judge_ignores_the_echoed_launch_prompt_beside_the_real_report(tmp_path):
    local, cloud = _pair(tmp_path)
    prompt = CC._check_prompt(NONCE, None)
    real = CC.report_line(_ok_report(cloud))
    assert _judge(local, prompt + "\n" + real + "\n")["action"] == "passed"
    # a lone fallback line (the session could not run report) still reads, and fails
    assert _judge(local, prompt)["action"] != "passed"
    # genuinely conflicting results beside the echoed prompt stay unread
    other = CC.report_line(_cloud_report(cloud, pluginVersion="9.9.9"))
    assert _judge(local, "%s\n%s\n%s\n" % (prompt, real, other))["action"] == "unread"


# --- judge: finding the line, and the approved words ---------------------------------------

def test_judge_finds_the_line_inside_a_comment_body(tmp_path):
    shapes = [
        "Here is the result of the check:\n\n```\n{line}\n```\n\nThanks!\n",
        "Log noise\n> {line}\nmore noise\n",
        "  `{line}`  \n",
        "text before\n{line}\ntext after\n",
    ]
    for index, shape in enumerate(shapes):
        local, cloud = _pair(tmp_path / ("c%d" % index))
        result = _judge(local, shape.format(line=CC.report_line(_ok_report(cloud))))
        assert result["action"] == "passed", (shape, result)


def test_judge_reviewer_failure_message_is_the_approved_words(tmp_path):
    local, cloud = _pair(tmp_path)
    result = _judge(local, _cloud_report(cloud, confirmation=_confirm(answered=False)(None)))
    assert result["message"] == (
        "**The check failed on one part.** The reviewer did not answer, so the pass is missing or "
        "was pasted wrong.\n\nCloud builds stay off. To fix it, paste a fresh pass into the "
        "environment and say \"check again\".")


def test_judge_passed_message_is_the_approved_words(tmp_path):
    local, cloud = _pair(tmp_path)
    result = _judge(local, _ok_report(cloud))
    assert result["message"] == (
        "**The check passed.**\n\n"
        "- The cloud's plugin is %s, the same as mine.\n"
        "- Its calibration matches this machine's.\n"
        "- The reviewer answered.\n"
        "- It has a git identity to commit with.\n\n"
        "Cloud builds are ready for demo and still switched off. Say \"turn cloud builds on\" "
        "when you want them." % VERSION)


def test_judge_passed_message_when_already_on(tmp_path):
    local, cloud = _pair(tmp_path)
    _turn_on(local)
    result = _judge(local, _ok_report(cloud))
    assert result["action"] == "passed"
    assert result["message"] == (
        "**The check passed.**\n\n"
        "- The cloud's plugin is %s, the same as mine.\n"
        "- Its calibration matches this machine's.\n"
        "- The reviewer answered.\n"
        "- It has a git identity to commit with.\n\n"
        "Cloud builds are ready for demo, and they're already on." % VERSION)


def test_judge_version_mismatch_names_both_versions_and_its_fix(tmp_path):
    local, cloud = _pair(tmp_path)
    result = _judge(local, _cloud_report(cloud, pluginVersion="0.0.1"))
    assert result["message"] == (
        "**The check failed on one part.** The cloud's plugin is 0.0.1 and mine is %s.\n\n"
        "Cloud builds stay off. To fix it, paste the new setup text into the environment and say "
        "\"check again\"." % VERSION)
    missing = _judge(local, _cloud_report(cloud, pluginVersion=None))
    assert _first(missing) == ("**The check failed on one part.** The cloud's plugin is not "
                               "installed and mine is %s." % VERSION)


def test_judge_calibration_mismatch_names_its_fix(tmp_path):
    local, cloud = _pair(tmp_path)
    result = _judge(local, _cloud_report(cloud, placedStamp=OTHER_STAMP))
    assert result["message"] == (
        "**The check failed on one part.** The cloud's calibration doesn't match this machine's."
        "\n\nCloud builds stay off. To fix it, paste the new setup text into the environment and "
        "say \"check again\".")


def test_judge_two_failed_parts_joins_fixes_once(tmp_path):
    local, cloud = _pair(tmp_path)
    same_fix = _judge(local, _cloud_report(cloud, pluginVersion="0.0.1", placedStamp=OTHER_STAMP))
    assert same_fix["failedParts"] == ["version", "calibration"]
    assert same_fix["message"] == (
        "**The check failed on 2 parts.** The cloud's plugin is 0.0.1 and mine is %s. The cloud's "
        "calibration doesn't match this machine's.\n\nCloud builds stay off. To fix it, paste the "
        "new setup text into the environment and say \"check again\"." % VERSION)
    different = _judge(local, _cloud_report(
        cloud, environment=None, confirmation=_confirm(answered=False)(None)))
    assert different["failedParts"] == ["environment", "reviewer"]
    assert different["message"].endswith(
        "To fix it, run /remote-env in Claude Code and pick this project's environment again, then "
        "run the pass command and paste the block into that environment, then paste a fresh pass "
        "into the environment and say \"check again\".")
    assert _record_state(local) == "none"


def test_judge_unread_message(tmp_path):
    local, _cloud = _pair(tmp_path)
    result = _judge(local, "no report here")
    assert result["action"] == "unread" and result["settingSwitchedOff"] is False
    assert result["message"] == (
        "**The check did not report back.** I could not read a result from the check session.\n\n"
        "Cloud builds stay off. Say \"check again\" and I'll run it once more.")


# --- the failed-check marker ---------------------------------------------------------------

FAILED_AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
DAMAGED = {"schema": CC.FAILED_CHECK_SCHEMA, "failedAt": None, "failedParts": [],
           "environment": None, "damaged": True}


def _marker_path(w):
    return CC.failed_check_path(w.cwd, ACCOUNT, w.root)


def _record_bytes(w):
    with open(cloud_setup.record_path(w.cwd, ACCOUNT, w.root), "rb") as fh:
        return fh.read()


def _marker_files(w):
    return [os.path.join(top, name) for top, _dirs, names in os.walk(w.root) for name in names
            if name.endswith(CC.FAILED_CHECK_SUFFIX)]


def test_failed_check_path_sits_beside_the_record(tmp_path):
    w = _build(tmp_path)
    record = cloud_setup.record_path(w.cwd, ACCOUNT, w.root)
    assert CC.failed_check_path(w.cwd, ACCOUNT, w.root) == record[:-len(".json")] + \
        ".failed-check.json"
    assert record.endswith(".json") and not record.endswith(".failed-check.json")


def test_a_failed_check_writes_the_marker_and_leaves_the_record_alone(tmp_path):
    local, cloud = _pair(tmp_path)
    assert _judge(local, _ok_report(cloud))["action"] == "passed"
    before = _record_bytes(local)
    assert CC.read_failed_check(local.cwd, ACCOUNT, local.root) is None
    result = _judge(local, _cloud_report(cloud, pluginVersion="0.0.1"))
    assert result["action"] == "failed" and result["failedParts"] == ["version"]
    # detector: a failed check that left no marker, or whose marker lacks a field, goes red here
    assert result["markerWritten"] is True
    marker = CC.read_failed_check(local.cwd, ACCOUNT, local.root)
    assert set(marker) == {"schema", "account", "environment", "failedAt", "failedParts"}
    assert marker["schema"] == CC.FAILED_CHECK_SCHEMA and marker["account"] == ACCOUNT
    assert marker["environment"] == ENV_ID and marker["failedParts"] == ["version"]
    assert FAILED_AT_RE.match(marker["failedAt"]) and marker["failedAt"] == "2026-10-10T12:00:00Z"
    with open(_marker_path(local), encoding="utf-8") as fh:
        assert fh.read() == json.dumps(marker, sort_keys=True, indent=2) + "\n"
    # detector: a failed judgment that wrote, changed or removed the setup record goes red here
    assert _record_bytes(local) == before


def test_an_unread_report_writes_the_marker(tmp_path):
    local, _cloud = _pair(tmp_path)
    result = _judge(local, "no report here")
    assert result["action"] == "unread" and result["failedParts"] == ["unread"]
    # detector: an unread judgment that left no marker goes red here
    assert result["markerWritten"] is True
    marker = CC.read_failed_check(local.cwd, ACCOUNT, local.root)
    assert marker["failedParts"][:1] == ["unread"] and marker["environment"] == ENV_ID
    assert FAILED_AT_RE.match(marker["failedAt"])
    assert _record_state(local) == "none"


def test_a_marker_lists_the_setting_part_after_a_switch_off_that_failed(tmp_path):
    local, cloud = _pair(tmp_path)
    _turn_on(local)
    result = _judge(local, _cloud_report(cloud, pluginVersion="0.0.1"),
                    set_fn=lambda *a, **k: {"action": "refused", "reason": "profile-absent"})
    assert result["failedParts"] == ["version", "setting"]
    # detector: a marker written before the switch-off settled its parts goes red here
    assert CC.read_failed_check(local.cwd, ACCOUNT, local.root)["failedParts"] == [
        "version", "setting"]


def test_the_marker_exists_when_the_switch_off_is_attempted(tmp_path):
    local, cloud = _pair(tmp_path)
    _turn_on(local)
    seen = []

    def set_fn(*a, **k):
        seen.append(CC.read_failed_check(local.cwd, ACCOUNT, local.root))
        return {"action": "written"}

    result = _judge(local, _cloud_report(cloud, pluginVersion="0.0.1"), set_fn=set_fn)
    # detector: a switch-off attempted before the marker is on disk goes red here
    assert len(seen) == 1 and seen[0]["failedParts"] == ["version"]
    assert result["markerWritten"] is True and result["failedParts"] == ["version"]
    seen.clear()
    unread = _judge(local, "no report here", set_fn=set_fn)
    assert len(seen) == 1 and seen[0]["failedParts"] == ["unread"]
    assert unread["markerWritten"] is True


def test_a_failed_switch_off_rewrites_the_marker_and_a_failed_rewrite_keeps_the_first(
        tmp_path, monkeypatch):
    local, cloud = _pair(tmp_path)
    _turn_on(local)
    refuse = lambda *a, **k: {"action": "refused", "reason": "profile-absent"}  # noqa: E731
    real_replace = os.replace
    writes = []

    def replace(src, dst, *a, **k):
        if str(dst).endswith(CC.FAILED_CHECK_SUFFIX):
            writes.append(1)
            if len(writes) > 1:
                raise OSError("disk")
        return real_replace(src, dst, *a, **k)

    monkeypatch.setattr(os, "replace", replace)
    result = _judge(local, _cloud_report(cloud, pluginVersion="0.0.1"), set_fn=refuse)
    # detector: markerWritten true while the disk marker lacks the final parts goes red here
    assert result["failedParts"] == ["version", "setting"] and result["markerWritten"] is False
    assert CC.read_failed_check(local.cwd, ACCOUNT, local.root)["failedParts"] == ["version"]


def test_a_passing_check_removes_the_marker_and_writes_the_record(tmp_path):
    local, cloud = _pair(tmp_path)
    assert _judge(local, _cloud_report(cloud, pluginVersion="0.0.1"))["action"] == "failed"
    assert os.path.exists(_marker_path(local))
    result = _judge(local, _ok_report(cloud), now=LATER)
    assert result["action"] == "passed" and result["markerWritten"] is False
    # detector: a pass that leaves the earlier failure's marker behind goes red here
    assert not os.path.exists(_marker_path(local))
    assert CC.read_failed_check(local.cwd, ACCOUNT, local.root) is None
    assert _record_state(local) == "ready"


def test_every_judge_result_carries_the_marker_key(tmp_path):
    local, cloud = _pair(tmp_path)
    for result in (_judge(local, "no report here"),
                   _judge(local, _cloud_report(cloud, pluginVersion="0.0.1")),
                   _judge(local, _ok_report(cloud))):
        assert isinstance(result["markerWritten"], bool), result


@pytest.mark.parametrize("how", ["unlink", "lock"])
def test_a_marker_that_cannot_be_removed_fails_the_check_after_the_record_write(tmp_path, monkeypatch, how):
    local, cloud = _pair(tmp_path)
    assert _judge(local, _cloud_report(cloud, pluginVersion="0.0.1"))["action"] == "failed"
    calls = []
    if how == "unlink":
        real_unlink = os.unlink

        def unlink(path, *a, **k):
            if str(path).endswith(CC.FAILED_CHECK_SUFFIX):
                raise OSError("busy")
            return real_unlink(path, *a, **k)

        monkeypatch.setattr(os, "unlink", unlink)
    else:
        import contextlib

        @contextlib.contextmanager
        def held(cwd, root=None):
            yield False

        monkeypatch.setattr(mode_registry, "config_lock", held)
    result = _judge(local, _ok_report(cloud),
                    record_fn=lambda *a, **k: calls.append(k) or {"action": "written"})
    # detector: a pass reported as passed, or one that loses the marker, when it could not be removed goes red
    assert result["action"] == "failed" and "record" in result["failedParts"]
    assert len(calls) == 1 and result["recordWritten"] is True
    assert os.path.exists(_marker_path(local))


def _record_write_that_raises(*a, **k):
    raise OSError("disk")


@pytest.mark.parametrize("record_fn", [
    _record_write_that_raises,
    lambda *a, **k: {"action": "refused"},
    lambda *a, **k: None,
], ids=["raises", "refused", "none"])
def test_a_record_write_that_fails_leaves_an_existing_marker_in_place(
        tmp_path, monkeypatch, record_fn):
    # axis: the marker is cleared only after a record write that reported written — see bite-proof record c8a_wo1.md
    local, cloud = _pair(tmp_path)
    assert _judge(local, _cloud_report(cloud, pluginVersion="0.0.1"))["action"] == "failed"
    before = open(_marker_path(local)).read()
    seen = []
    removals = []
    real_remove = CC._remove_failed_check

    def spying_remove(*a, **k):
        removals.append(a)
        return real_remove(*a, **k)

    monkeypatch.setattr(CC, "_remove_failed_check", spying_remove)

    def recording(*a, **k):
        # detector: a marker cleared before the record writer is called goes red here
        seen.append(os.path.exists(_marker_path(local)) and open(_marker_path(local)).read() == before)
        return record_fn(*a, **k)

    result = _judge(local, _ok_report(cloud), now=LATER, record_fn=recording)
    # detector: a failed record write that clears the failure marker goes red here
    assert seen == [True]
    assert result["action"] == "failed" and "record" in result["failedParts"]
    assert removals == []
    assert os.path.exists(_marker_path(local)) and before


def _plant_marker(local, failed_at):
    os.makedirs(os.path.dirname(_marker_path(local)), exist_ok=True)
    with open(_marker_path(local), "w") as fh:
        json.dump({"schema": CC.FAILED_CHECK_SCHEMA, "account": ACCOUNT, "environment": ENV_ID,
                   "failedAt": failed_at, "failedParts": ["version"]}, fh)


def test_a_marker_stamped_after_the_judgment_start_is_kept_and_fails_on_record(tmp_path):
    local, cloud = _pair(tmp_path)
    _plant_marker(local, "2026-10-10T12:00:30Z")
    result = _judge(local, _ok_report(cloud))
    # detector: removing a marker written by an overlapping failed judgment goes red here
    assert result["action"] == "failed" and "record" in result["failedParts"]
    assert result["recordWritten"] is True
    assert os.path.exists(_marker_path(local))


def test_a_marker_stamped_before_the_judgment_start_is_removed_on_a_pass(tmp_path):
    local, cloud = _pair(tmp_path)
    _plant_marker(local, "2026-10-10T11:59:59Z")
    result = _judge(local, _ok_report(cloud))
    # detector: keeping an older marker (a stuck failure) goes red here
    assert result["action"] == "passed"
    assert not os.path.exists(_marker_path(local))


def test_a_damaged_marker_is_removed_on_a_pass(tmp_path):
    local, cloud = _pair(tmp_path)
    os.makedirs(os.path.dirname(_marker_path(local)), exist_ok=True)
    with open(_marker_path(local), "w") as fh:
        fh.write("{not json")
    result = _judge(local, _ok_report(cloud))
    # detector: a damaged marker that survives a pass goes red here
    assert result["action"] == "passed"
    assert not os.path.exists(_marker_path(local))


def test_a_record_that_is_written_before_the_marker_is_cleared(tmp_path):
    local, cloud = _pair(tmp_path)
    assert _judge(local, _cloud_report(cloud, pluginVersion="0.0.1"))["action"] == "failed"
    seen = []
    result = _judge(local, _ok_report(cloud), now=LATER, record_fn=lambda *a, **k: seen.append(
        os.path.exists(_marker_path(local))) or {"action": "written"})
    # detector: clearing the marker before the record write goes red here
    assert seen == [True] and result["action"] == "passed"
    assert not os.path.exists(_marker_path(local))


def test_a_marker_write_that_fails_changes_nothing_else(tmp_path, monkeypatch):
    results = {}
    for label, break_write in (("base", False), ("fault", True)):
        local, cloud = _pair(tmp_path / label)
        _turn_on(local)
        if break_write:
            real_replace = os.replace

            def replace(src, dst, *a, **k):
                if str(dst).endswith(CC.FAILED_CHECK_SUFFIX):
                    raise OSError("disk")
                return real_replace(src, dst, *a, **k)

            monkeypatch.setattr(os, "replace", replace)
        results[label] = _judge(local, _cloud_report(cloud, pluginVersion="0.0.1"))
        results[label + "-setting"] = _setting(local)
        monkeypatch.undo()
        results[label + "-marker"] = os.path.exists(_marker_path(local))
    base, fault = results["base"], results["fault"]
    assert base["markerWritten"] is True and results["base-marker"] is True
    # detector: a marker write that fails but is reported written goes red here
    assert fault["markerWritten"] is False and results["fault-marker"] is False
    assert dict(fault, markerWritten=True) == base
    assert fault["settingSwitchedOff"] is True
    assert results["fault-setting"] is False and results["base-setting"] is False


def test_an_unresolved_account_writes_no_marker(tmp_path):
    local, cloud = _pair(tmp_path)
    for text in (_cloud_report(cloud, pluginVersion="0.0.1"), "no report here"):
        result = _judge(local, text, account=None)
        # detector: a marker written for an account that could not be resolved goes red here
        assert result["action"] in ("failed", "unread") and result["markerWritten"] is False
    assert _marker_files(local) == []


def test_read_failed_check_reads_the_damaged_shape(tmp_path):
    w = _build(tmp_path)
    path = _marker_path(w)
    assert CC.read_failed_check(w.cwd, ACCOUNT, w.root) is None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for body in ("not json", json.dumps({"schema": "cloud-check-failed/2", "failedParts": ["x"]}),
                 json.dumps([CC.FAILED_CHECK_SCHEMA]), ""):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
        # detector: a marker that exists but does not read as ours must not come back as absent
        assert CC.read_failed_check(w.cwd, ACCOUNT, w.root) == DAMAGED, body
    os.unlink(path)
    os.mkdir(path)
    assert CC.read_failed_check(w.cwd, ACCOUNT, w.root) == DAMAGED
    os.rmdir(path)
    good = {"schema": CC.FAILED_CHECK_SCHEMA, "account": ACCOUNT, "environment": ENV_ID,
            "failedAt": "2026-10-10T12:00:00Z", "failedParts": ["version"]}
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(good))
    assert CC.read_failed_check(w.cwd, ACCOUNT, w.root) == good


def test_no_owner_facing_string_sends_the_owner_to_an_environment_page_for_an_id():
    strings = [value for value in vars(CC).values() if isinstance(value, str)]
    for _name, sentence, fix in CC._PARTS:
        strings += [sentence, fix]
    assert CC._SETUP_MESSAGE in strings and CC._ENVIRONMENT_NEEDED in strings
    for text in strings:
        # detector: any owner-facing string that tells the owner to copy or check an id goes red here
        for phrase in ("environment" + "'s page", "copy its" + " id", "whose id" + " you gave"):
            assert phrase not in text, (phrase, text)
    for text in (CC._SETUP_MESSAGE, CC._ENVIRONMENT_NEEDED, dict((n, s) for n, s, _ in CC._PARTS)[
            "environment"]):
        assert "/remote-env" in text


# --- the command line ----------------------------------------------------------------------

def _cli_env(monkeypatch, tmp_path):
    monkeypatch.setenv(cloud_pass.ENVIRONMENT_ENV, ENV_ID)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv(cloud_pass.SEPARATE_HOME_ENV, raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setattr(cloud_pass, "confirm", _confirm())


def test_cli_report_prints_one_marked_line(tmp_path, monkeypatch, capsys):
    _cloud = _build(tmp_path)
    _cli_env(monkeypatch, tmp_path)
    code = CC.main(["report", "--cwd", _cloud.cwd, "--root", _cloud.root, "--nonce", NONCE])
    out = capsys.readouterr().out
    assert code == 0 and out.endswith("\n") and out.count("\n") == 1
    assert out.startswith("SUPERHEROES-CLOUD-CHECK {")
    obj = json.loads(out.split(" ", 1)[1])
    assert obj["nonce"] == NONCE and obj["environment"] == ENV_ID and obj["pluginVersion"] == VERSION
    assert obj["digest"] == CC.report_digest(obj)
    assert out == CC.report_line(obj) + "\n"
    # a session with nothing at all still prints its line and exits 0
    monkeypatch.delenv(cloud_pass.ENVIRONMENT_ENV)
    code = CC.main(["report", "--cwd", str(tmp_path / "nowhere"), "--root", str(tmp_path / "none")])
    out = capsys.readouterr().out
    assert code == 0 and json.loads(out.split(" ", 1)[1])["environment"] is None


def test_cli_judge_exit_codes(tmp_path, monkeypatch, capsys):
    local, cloud = _pair(tmp_path)
    _cli_env(monkeypatch, tmp_path)
    CC.main(["report", "--cwd", cloud.cwd, "--root", cloud.root, "--nonce", NONCE])
    line = capsys.readouterr().out
    base = ["judge", "--cwd", local.cwd, "--root", local.root, "--environment", ENV_ID,
            "--account", ACCOUNT, "--project-name", "demo"]
    wrong = CC.main(base + ["--nonce", "zzzzzzzz9999", "--line", line])
    assert wrong == 1 and json.loads(capsys.readouterr().out)["action"] == "unread"
    assert _record_state(local) == "none"
    missing = CC.main(base + ["--nonce", NONCE, "--line-file", str(tmp_path / "absent.txt")])
    assert missing == 1 and json.loads(capsys.readouterr().out)["action"] == "unread"
    shipped = json.loads(line.split(" ", 1)[1])
    shipped.pop("digest")
    bad_version = CC.report_line(dict(shipped, pluginVersion="0.0.1"))
    clock = [NOW]
    # pins the CLI's wall clock: same-second stamps would keep the failed marker and fail the pass
    monkeypatch.setattr(CC.time, "time", lambda: clock[0])
    failed = CC.main(base + ["--nonce", NONCE, "--line", bad_version])
    assert failed == 1 and json.loads(capsys.readouterr().out)["action"] == "failed"
    assert _record_state(local) == "none"
    clock[0] = LATER
    path = tmp_path / "comment.txt"
    path.write_text("Result:\n```\n%s```\n" % line)
    passed = CC.main(base + ["--nonce", NONCE, "--line-file", str(path)])
    printed = json.loads(capsys.readouterr().out)
    assert passed == 0 and printed["action"] == "passed" and _record_state(local) == "ready"


def test_cli_other_verbs_exit_codes(tmp_path, monkeypatch, capsys, composing):
    w = _build(tmp_path)
    _cli_env(monkeypatch, tmp_path)
    assert CC.main(["sign-in"]) == 0
    assert json.loads(capsys.readouterr().out)["signedIn"] is False
    assert CC.main(["setup-message", "--cwd", w.cwd, "--root", w.root,
                    "--project-name", "demo"]) == 0
    assert json.loads(capsys.readouterr().out)["action"] == "written"
    assert CC.main(["setup-text", "--cwd", w.cwd, "--root", w.root]) == 0
    assert json.loads(capsys.readouterr().out)["action"] == "written"
    monkeypatch.setattr(cloud_setup_text, "compose", lambda cwd, **kw: {
        "action": "refused", "reason": "calibration-missing", "detail": "No calibration."})
    assert CC.main(["setup-message", "--cwd", w.cwd, "--root", w.root]) == 1
    assert json.loads(capsys.readouterr().out)["action"] == "refused"
    assert CC.main(["setup-text", "--cwd", w.cwd, "--root", w.root]) == 1
    assert json.loads(capsys.readouterr().out)["action"] == "refused"


# --- start ---------------------------------------------------------------------------------

def _receipt(name):
    return ("Created cloud session: %s\n"
            "View: https://claude.ai/code/session_01ABCdef?from=cli\n"
            "Resume with: claude --teleport session_01ABCdef\n" % name)


class Spawner:
    """A fake spawn function: records every call and answers with canned output."""

    def __init__(self, output=None, raises=None, timed_out=False):
        self.calls = []
        self.output = output
        self.raises = raises
        self.timed_out = timed_out

    def __call__(self, argv, cwd, log_path, child_env, timeout):
        self.calls.append({"argv": list(argv), "cwd": cwd, "log_path": log_path,
                           "env": child_env, "timeout": timeout})
        if self.raises is not None:
            raise self.raises
        name = argv[argv.index("-n") + 1]
        output = _receipt(name) if self.output is None else self.output
        return {"pid": 1, "rc": 0, "timedOut": self.timed_out, "output": output}


def _start(local, spawner, **kw):
    args = dict(environment=ENV_ID, env=local.env, spawn_fn=spawner, nonce=NONCE)
    args.update(kw)
    return CC.start(local.cwd, **args)


def _prompt(spawner):
    argv = spawner.calls[0]["argv"]
    return argv[argv.index("--cloud") + 1]


def test_start_scrubs_inherited_git_variables_from_the_child_and_the_root(tmp_path):
    local, _ = _pair(tmp_path)
    spawner = Spawner()
    env = dict(local.env, GIT_WORK_TREE="/tmp", GIT_DIR="/tmp/nope")
    assert _start(local, spawner, env=env)["action"] == "started"
    call = spawner.calls[0]
    # detector: a start that hands inherited GIT_* variables to the child or the root lookup goes red
    assert "GIT_WORK_TREE" not in call["env"] and "GIT_DIR" not in call["env"]
    assert os.path.realpath(call["cwd"]) == os.path.realpath(local.cwd)


def test_start_pins_the_cells_effort_over_an_inherited_effort_variable(tmp_path):
    # axis: the check session's environment carries the cell's effort, since an inherited variable outranks the flag — see bite-proof record c8a_wo1.md
    local, _ = _pair(tmp_path)
    spawner = Spawner()
    env = dict(local.env, CLAUDE_CODE_EFFORT_LEVEL="low", CLAUDE_EFFORT="low")
    assert _start(local, spawner, env=env)["action"] == "started"
    cell = model_registry.resolve_dispatch("mechanical", "claude", None)
    child_env = spawner.calls[0]["env"]
    assert child_env["CLAUDE_CODE_EFFORT_LEVEL"] == cell["effort"] != "low"
    assert "CLAUDE_EFFORT" not in child_env


def test_start_with_no_resolved_effort_leaves_the_environment_untouched(tmp_path, monkeypatch):
    # The registry's mechanical claude cell carries an effort today, so the cell is stubbed here.
    local, _ = _pair(tmp_path)
    real = model_registry.resolve_dispatch
    monkeypatch.setattr(model_registry, "resolve_dispatch",
                        lambda *a, **k: dict(real(*a, **k), effort=None))
    spawner = Spawner()
    env = dict(local.env, CLAUDE_CODE_EFFORT_LEVEL="low", CLAUDE_EFFORT="low")
    assert _start(local, spawner, env=env)["action"] == "started"
    child_env = spawner.calls[0]["env"]
    assert child_env["CLAUDE_CODE_EFFORT_LEVEL"] == "low" and child_env["CLAUDE_EFFORT"] == "low"
    assert "--effort" not in spawner.calls[0]["argv"]


def test_start_names_the_environment_in_the_launch(tmp_path):
    local = _build(tmp_path)
    spawner = Spawner()
    result = _start(local, spawner)
    assert result["action"] == "started" and len(spawner.calls) == 1
    argv = spawner.calls[0]["argv"]
    cell = model_registry.resolve_dispatch("mechanical", "claude", None)
    assert argv == engine_adapter.claude_cloud_builder_argv(
        cell["dispatch_token"], cell["effort"], _prompt(spawner), ENV_ID,
        "cloud-check-" + NONCE[:8], permission_mode=None, disallowed_tools=None)["argv"]
    assert "--permission-mode" not in argv
    assert "--disallowedTools" not in argv
    settings = json.loads(argv[argv.index("--settings") + 1])
    assert settings == {"remote": {"defaultEnvironmentId": ENV_ID}}
    assert result["environment"] == ENV_ID and OTHER_ENV_ID not in " ".join(argv)


@pytest.mark.parametrize("bad", [None, "", "env_", "env-01ABC", "env_01 ABC", "xenv_01ABC",
                                 "env_01ABC\n", 42, ["env_01ABC"], b"env_01ABC"])
def test_start_refuses_without_an_environment_id(tmp_path, bad):
    local = _build(tmp_path)
    spawner = Spawner()
    result = _start(local, spawner, environment=bad)
    assert result["action"] == "refused" and result["reason"] == "check-environment-invalid"
    assert result["message"] == (
        "I need to know which cloud environment to check. Run /remote-env in Claude Code on this "
        "computer and pick this project's environment, then tell me, and I'll read which one you "
        "picked.")
    assert spawner.calls == []


def test_start_refuses_a_bad_issue_or_nonce_before_spawning(tmp_path):
    local = _build(tmp_path)
    spawner = Spawner()
    for bad in (0, -3, "0", "12a", "", True, 1.5, "#12"):
        assert _start(local, spawner, issue=bad)["reason"] == "check-issue-invalid"
    for bad in ("short", "has space1234", "x" * 65, 12345678, ""):
        assert _start(local, spawner, nonce=bad)["reason"] == "check-nonce-invalid"
    assert spawner.calls == []


def test_start_refuses_when_the_model_cannot_be_resolved_or_the_argv_is_refused(
        tmp_path, monkeypatch):
    local = _build(tmp_path)
    spawner = Spawner()
    with monkeypatch.context() as patch:
        patch.setattr(model_registry, "resolve_dispatch",
                      lambda *a: {"ok": False, "detail": "no seat"})
        assert _start(local, spawner)["reason"] == "check-model-unresolved"
    monkeypatch.setattr(engine_adapter, "claude_cloud_builder_argv",
                        lambda *a, **k: {"argv": [], "reason": "cloud-session-name-invalid"})
    result = _start(local, spawner)
    assert result["action"] == "refused" and result["reason"] == "check-launch-refused"
    assert result["detail"] == "cloud-session-name-invalid"
    assert spawner.calls == []


def test_start_reports_a_launch_that_could_not_run(tmp_path):
    local = _build(tmp_path)
    spawner = Spawner(raises=OSError("no terminal"))
    result = _start(local, spawner)
    assert result["action"] == "refused" and result["reason"] == "check-session-not-started"
    assert result["message"] == ("The check session did not start: the cloud launch command could "
                                 "not be run.")
    assert len(spawner.calls) == 1


@pytest.mark.parametrize("output,timed_out", [
    ("", False),
    (_receipt("cloud-check-zzzzzzzz"), False),
    ("Starting...\n", True),
])
def test_start_never_reports_started_without_a_receipt(tmp_path, output, timed_out):
    local = _build(tmp_path)
    spawner = Spawner(output=output, timed_out=timed_out)
    result = _start(local, spawner)
    assert result["action"] == "refused" and result["reason"] == "check-session-unconfirmed"
    assert result["sessionName"] == "cloud-check-abcd1234"
    assert result["message"] == (
        "I could not confirm that the check session started. Look for a session named "
        "cloud-check-abcd1234 in your session list; say \"check again\" and I'll start a new "
        "one.")
    assert len(spawner.calls) == 1


def test_start_reports_started_when_a_timed_out_launch_printed_its_receipt(tmp_path):
    local = _build(tmp_path)
    spawner = Spawner(output="\x1b[2K" + _receipt("cloud-check-abcd1234"), timed_out=True)
    result = _start(local, spawner, issue="1745")
    assert result == {"action": "started", "reason": None, "environment": ENV_ID, "nonce": NONCE,
                      "sessionName": "cloud-check-abcd1234", "sessionId": "session_01ABCdef",
                      "sessionUrl": "https://claude.ai/code/session_01ABCdef", "issue": 1745,
                      "message": "The check session is running. I'll read its result in about a "
                                 "minute."}


def test_start_spawns_in_the_repository_root_with_a_copy_of_the_environment(tmp_path):
    local = _build(tmp_path)
    sub = os.path.join(local.cwd, "nested")
    os.makedirs(sub)
    env = dict(local.env, SOME_VALUE="kept")
    spawner = Spawner()
    _start(local, spawner, env=env, timeout=7)
    call = spawner.calls[0]
    assert os.path.realpath(call["cwd"]) == os.path.realpath(local.cwd)
    import launcher
    expected = dict(env)
    launcher.pin_effort(expected, model_registry.resolve_dispatch("mechanical", "claude", None)["effort"])
    assert call["env"] == expected and call["env"] is not env and call["timeout"] == 7
    assert os.path.isdir(os.path.dirname(call["log_path"]))
    spawner2 = Spawner()
    CC.start(sub, environment=ENV_ID, env=env, spawn_fn=spawner2, nonce=NONCE)
    assert os.path.realpath(spawner2.calls[0]["cwd"]) == os.path.realpath(local.cwd)


def test_start_makes_a_fresh_nonce_when_none_is_given(tmp_path):
    local = _build(tmp_path)
    one = _start(local, Spawner(), nonce=None)
    two = _start(local, Spawner(), nonce=None)
    assert re.fullmatch(r"[0-9a-f]{16}", one["nonce"]) and one["nonce"] != two["nonce"]
    assert one["sessionName"] == "cloud-check-" + one["nonce"][:8]


def _expected_prompt(issue=None):
    fallback_object = (
        {"schema": CC.REPORT_SCHEMA, "nonce": NONCE, "environment": None,
         "pluginVersion": None, "pluginCommit": None, "placedStamp": None, "stampFile": None,
         "repoStamp": None, "confirmation": {"schema": cloud_pass.CONFIRMATION_SCHEMA, "reviewerAnswered": False,
                          "passLapses": None, "reason": "plugin-missing"},
         "identity": None})
    fallback = CC.report_line(fallback_object)
    text = ("This is a short setup check. Edit nothing, commit nothing, push nothing, and invoke "
            "no skill.\n\n"
            "Run exactly this one command from the repository's root:\n\n"
            "python3 -B %s/lib/cloud_check.py report --nonce %s\n\n"
            "It prints one line that starts with SUPERHEROES-CLOUD-CHECK. If the command cannot "
            "run because that file does not exist, use this line instead, exactly as written:\n\n"
            "%s\n\n"
            "Give that one line, alone and unchanged, as your final message."
            % (cloud_pass.CLOUD_PLUGIN_DIR, NONCE, fallback))
    if issue is not None:
        text += ("\n\nAlso post that one line, alone inside a fenced code block, as one comment on "
                 "issue #%d of this repository." % issue)
    return text


def test_start_prompt_carries_the_nonce_the_report_command_and_the_fallback_line(tmp_path):
    local = _build(tmp_path)
    spawner = Spawner()
    _start(local, spawner)
    assert _prompt(spawner) == _expected_prompt()
    assert "/opt/superheroes/plugin/lib/cloud_check.py report --nonce " + NONCE in _prompt(spawner)


def test_start_prompt_never_carries_the_pass_or_an_environment_variable(tmp_path):
    local = _build(tmp_path)
    secret = "sk-secret-value-9f8e7d"
    spawner = Spawner()
    _start(local, spawner, env=dict(local.env, REVIEWER_PASS=secret, OTHER=secret + "2"))
    prompt = _prompt(spawner)
    assert secret not in prompt and secret not in " ".join(spawner.calls[0]["argv"])
    assert local.env["HOME"] not in prompt and local.root not in prompt


def test_start_fallback_line_judges_as_failed_not_passed(tmp_path):
    local = _build(tmp_path)
    spawner = Spawner()
    _start(local, spawner)
    line = [l for l in _prompt(spawner).splitlines() if l.startswith(CC.MARKER + " {")]
    assert len(line) == 1
    result = _judge(local, line[0])
    assert result["action"] == "failed" and "reviewer" in result["failedParts"]
    assert "environment" in result["failedParts"] and result["recordWritten"] is False
    assert _record_state(local) == "none"


def test_start_posts_to_an_issue_only_when_one_is_named(tmp_path):
    local = _build(tmp_path)
    without, with_issue = Spawner(), Spawner()
    _start(local, without)
    _start(local, with_issue, issue=1745)
    assert "issue #" not in _prompt(without) and _prompt(without) == _expected_prompt()
    assert _prompt(with_issue) == _expected_prompt(1745)
    assert _prompt(with_issue).endswith("as one comment on issue #1745 of this repository.")
    assert _prompt(with_issue).startswith(_prompt(without))


def test_setup_sitting_names_the_id_and_never_the_default(tmp_path, composing):
    local, cloud = _pair(tmp_path)
    # 1. the instructions send the owner to /remote-env and never ask for an id or a default change
    message = CC.setup_message(local.cwd, project_name="demo", root=local.root, env=local.env,
                               now=NOW)["message"]
    assert ("1. Make a cloud environment for this project on claude.ai, then run /remote-env in "
            "Claude Code on this computer and pick it. I read which one you picked, so there's no "
            "id to copy, and every build names this environment itself.") in message
    assert "default" not in message.lower()
    # 2. a machine with no separate sign-in is walked through one, then finds it in place
    (tmp_path / "owner").mkdir()
    home, env = _home_env(tmp_path / "owner")
    walk = CC.sign_in(env)
    assert walk["signedIn"] is False and "codex login" in walk["message"]
    _auth(home / ".codex-cloud")
    assert CC.sign_in(env) == {"action": "checked", "signedIn": True,
                               "message": "The separate reviewer sign-in is in place."}
    # 3. no id, no launch
    spawner = Spawner()
    assert _start(local, spawner, environment=None)["action"] == "refused"
    assert spawner.calls == []
    # 4. the launch names the id the owner gave
    started = _start(local, spawner, nonce=None)
    assert started["action"] == "started" and len(spawner.calls) == 1
    argv = spawner.calls[0]["argv"]
    assert json.loads(argv[argv.index("--settings") + 1]) == {
        "remote": {"defaultEnvironmentId": ENV_ID}}
    # 5. the cloud machine reports under the same nonce, and the judgment passes
    obj = CC.report(env={cloud_pass.ENVIRONMENT_ENV: ENV_ID}, cwd=cloud.cwd, root=cloud.root,
                    nonce=started["nonce"], confirm_fn=_confirm())
    judged = _judge(local, obj, nonce=started["nonce"])
    assert judged["action"] == "passed" and judged["recordWritten"] is True
    record = cloud_setup.read(local.cwd, ACCOUNT, local.root)["record"]
    assert record["environment"] == ENV_ID


def test_cli_start_exit_codes(tmp_path, capsys):
    local = _build(tmp_path)
    spawner = Spawner()
    code = CC.main(["start", "--cwd", local.cwd, "--environment", ENV_ID, "--issue", "1745"],
                   spawn_fn=spawner)
    printed = json.loads(capsys.readouterr().out)
    assert code == 0 and printed["action"] == "started" and printed["issue"] == 1745
    assert printed["environment"] == ENV_ID and len(spawner.calls) == 1
    refused_spawner = Spawner()
    code = CC.main(["start", "--cwd", local.cwd], spawn_fn=refused_spawner)
    printed = json.loads(capsys.readouterr().out)
    assert code == 1 and printed["reason"] == "check-environment-invalid"
    assert refused_spawner.calls == []
    code = CC.main(["start", "--cwd", local.cwd, "--environment", ENV_ID],
                   spawn_fn=Spawner(output=""))
    assert code == 1 and json.loads(capsys.readouterr().out)["reason"] == "check-session-unconfirmed"


def test_find_report_accepts_a_respaced_copy_of_the_same_report():
    obj = dict.fromkeys(CC.REPORT_FIELDS)
    obj.update(schema=CC.REPORT_SCHEMA, nonce="abcdefgh", pluginVersion="0.42.0",
               confirmation={"schema": cloud_pass.CONFIRMATION_SCHEMA, "reviewerAnswered": True,
                             "passLapses": "2099-12-31"})
    line = CC.report_line(obj)
    respaced = CC.MARKER + " " + json.dumps(json.loads(line.split(" ", 1)[1]))
    # bites on: raw-body comparison treating a respaced copy as a conflicting report (None)
    assert CC._find_report(line + "\n" + respaced, "abcdefgh") is not None


# --- the plugin pin hook: the report's commit and the judgment of a pin project ----------------

PIN = {"source": SOURCE, "commit": COMMIT, "subdir": SUBDIR, "version": VERSION}
OTHER_COMMIT = "b" * 40
PIN_FILE = os.path.join(".claude", "superheroes-plugin-pin")


def _git_env():
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": os.devnull,
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def _plugin_repo(path):
    """A directory that is a git repository with one commit; returns that commit."""
    path.mkdir()
    (path / "version.txt").write_text("1.2.3\n")
    for args in (["init", "-q"], ["add", "-A"],
                 ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "x"]):
        subprocess.run(["git", *args], cwd=str(path), env=_git_env(), capture_output=True, check=True)
    done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(path), env=_git_env(),
                          capture_output=True, text=True, check=True)
    return done.stdout.strip()


def _pin_pair(tmp_path, pin=PIN):
    """A pair whose local project commits the pin hook; its stamp covers the pin's two entries."""
    local = _build(tmp_path / "local")
    assert cloud_plugin_pin.sync(local.cwd, pin)["action"] == "written"
    local.stamp = cloud_setup.calibration_stamp(
        cloud_setup_text.stamped_files(local.cwd, local.root))
    _put(local, cloud_setup_text.STAMP_FILE, (local.stamp + "\n").encode())
    cloud = _mirror(tmp_path / "cloud", local, mode_registry.GLOBAL, FACTS["patterns"])
    # the cloud session works in a clone of the repository, which carries the committed hook files
    assert cloud_plugin_pin.sync(cloud.cwd, pin)["action"] == "written"
    return local, cloud


def _break_local_pin(local):
    with open(os.path.join(local.cwd, PIN_FILE), "w") as fh:
        fh.write("not a pin\n")
    assert cloud_plugin_pin.in_tree(local.cwd)["state"] == "broken"


def test_report_carries_the_commit_of_the_plugin_it_runs(tmp_path, monkeypatch):
    commit = _plugin_repo(tmp_path / "plugin-repo")
    monkeypatch.setattr(cloud_setup_text, "_plugin_root", lambda: str(tmp_path / "plugin-repo"))
    got = CC.report(env={}, cwd=str(tmp_path), root=str(tmp_path / "no-store"))
    assert got["pluginCommit"] == commit and re.fullmatch(r"[0-9a-f]{40}", commit)
    (tmp_path / "plain").mkdir()
    monkeypatch.setattr(cloud_setup_text, "_plugin_root", lambda: str(tmp_path / "plain"))
    assert CC.report(env={}, cwd=str(tmp_path), root=str(tmp_path / "no-store"))["pluginCommit"] is None


def test_judge_passes_a_pin_project_when_the_commit_and_version_match(tmp_path):
    local, cloud = _pin_pair(tmp_path)
    result = _judge(local, _cloud_report(cloud, pluginCommit=COMMIT))
    assert result["action"] == "passed" and result["failedParts"] == []
    assert result["results"] == {"versionMatches": True, "pinMatches": True,
                                 "dependencyHookMatches": True, "calibrationMatches": True,
                                 "reviewerAnswered": True, "environmentMatches": True,
                                 "identityPresent": True}
    assert result["recordWritten"] is True
    assert cloud_setup.read(local.cwd, ACCOUNT, local.root)["state"] == "ready"


def test_judge_fails_the_pin_part_when_the_cloud_runs_another_commit(tmp_path):
    local, cloud = _pin_pair(tmp_path)
    result = _judge(local, _cloud_report(cloud, pluginCommit=OTHER_COMMIT))
    # axis: the cloud's reported commit must equal the pin's commit
    assert result["action"] == "failed" and result["failedParts"] == ["pin"]
    assert result["results"]["pinMatches"] is False and result["recordWritten"] is False
    assert _first(result) == (
        "**The check failed on one part.** The cloud runs plugin %s at commit %s; this project's "
        "pin names %s at %s, and mine is %s." % (
            VERSION, OTHER_COMMIT[:12], VERSION, COMMIT[:12], VERSION))
    assert "run cloud_plugin_pin.py write on this machine" in result["message"]


def test_judge_fails_the_pin_part_when_the_commit_cannot_be_read(tmp_path):
    local, cloud = _pin_pair(tmp_path)
    for commit in (None, "not-a-commit", COMMIT.upper(), COMMIT[:12]):
        result = _judge(local, _cloud_report(cloud, pluginCommit=commit))
        assert result["failedParts"] == ["pin"] and result["results"]["pinMatches"] is False
    no_field = _cloud_report(cloud)
    del no_field["pluginCommit"]
    assert _judge(local, no_field)["failedParts"] == ["pin"]


def test_judge_fails_the_pin_part_when_the_pin_names_another_version(tmp_path):
    local, cloud = _pin_pair(tmp_path, dict(PIN, version="0.0.1"))
    result = _judge(local, _cloud_report(cloud, pluginCommit=COMMIT))
    assert result["failedParts"] == ["pin"] and result["results"]["pinMatches"] is False
    assert "this project's pin names 0.0.1 at %s, and mine is %s." % (COMMIT[:12], VERSION) in (
        result["message"])


def test_judge_fails_the_pin_part_for_a_broken_hook(tmp_path):
    local, cloud = _pin_pair(tmp_path)
    _break_local_pin(local)
    result = _judge(local, _cloud_report(cloud, pluginCommit=COMMIT))
    assert "pin" in result["failedParts"] and result["results"]["pinMatches"] is False
    assert result["action"] == "failed" and result["recordWritten"] is False
    assert "This project's plugin pin hook is broken (" in result["message"]


def test_judge_a_pin_project_does_not_fail_on_the_reported_version_alone(tmp_path):
    local, cloud = _pin_pair(tmp_path)
    result = _judge(local, _cloud_report(cloud, pluginVersion="0.0.1", pluginCommit=COMMIT))
    assert result["action"] == "passed" and result["results"]["versionMatches"] is False


def test_judge_without_the_hook_judges_the_version_and_ignores_the_commit(tmp_path):
    local, cloud = _pair(tmp_path)
    assert cloud_plugin_pin.in_tree(local.cwd)["state"] == "absent"
    for commit in (None, OTHER_COMMIT):
        result = _judge(local, _cloud_report(cloud, pluginCommit=commit))
        assert result["action"] == "passed" and result["results"]["pinMatches"] is None
    bad = _judge(local, _cloud_report(cloud, pluginVersion="0.0.1", pluginCommit=COMMIT))
    assert bad["failedParts"] == ["version"] and bad["results"]["pinMatches"] is None
    assert _first(bad) == ("**The check failed on one part.** The cloud's plugin is 0.0.1 and "
                           "mine is %s." % VERSION)


def test_the_fallback_line_still_judges_as_failed_for_a_pin_project_and_one_without(tmp_path):
    for name, local in (("pin", _pin_pair(tmp_path / "pin")[0]), ("plain", _build(tmp_path / "plain"))):
        result = _judge(local, CC._fallback_line(NONCE))
        assert result["action"] == "failed", name
        assert "reviewer" in result["failedParts"] and result["recordWritten"] is False
        assert ("pin" in result["failedParts"]) is (name == "pin")
