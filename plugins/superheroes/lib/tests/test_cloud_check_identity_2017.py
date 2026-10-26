"""Tests for the cloud check's git identity part (#2017): the cloud session must resolve a configured
author and committer identity, a guessed one never counts, the report line carries neither a name
nor an email, and the owner's own name and email fill in the fix line only in judge's message.

The identity test (`launch_doctrine.git_identity`) runs against a real `git init` repository under tmp_path, with the home, the
global config and the system config pinned away from this machine's. The judgment tests use the
fixture projects of test_cloud_check and an identity written into the report object. No test starts
a cloud session, runs the reviewer tool or touches the network.
"""
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_check as CC  # noqa: E402
import cloud_setup_text  # noqa: E402
import launch_doctrine as LD  # noqa: E402
import mode_registry  # noqa: E402
from test_cloud_check import (ACCOUNT, NONCE, VERSION, _cloud_report, _confirm, _first,  # noqa: E402
                              _judge, _pair)

FIRST = ("**The check failed on one part.** The cloud session has no git identity to commit with, "
         "so a build there would stop at its first commit.")
UNREPORTED = "**The check failed on one part.** The cloud session did not report its git identity."
FIX = ("set GIT_AUTHOR_NAME and GIT_COMMITTER_NAME to your name, and GIT_AUTHOR_EMAIL and "
       "GIT_COMMITTER_EMAIL to your email, in the environment's variables")
BOTH = {"author": True, "committer": True}
NEITHER = {"author": False, "committer": False}
EMAIL = "owner@example.invalid"


# --- fixtures ------------------------------------------------------------------------------

@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A real git repository whose git sees no configuration but its own and no identity variable."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for var in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL",
                "EMAIL"):
        monkeypatch.delenv(var, raising=False)
    path = tmp_path / "identity-repo"
    subprocess.run(["git", "init", "-q", str(path)], check=True, capture_output=True, text=True)
    return str(path)


def _local_config(path, name="Owner", email=EMAIL):
    for key, value in (("user.name", name), ("user.email", email)):
        subprocess.run(["git", "-C", path, "config", "--local", key, value], check=True,
                       capture_output=True, text=True)


def _with_identity(cloud, identity):
    obj = _cloud_report(cloud)
    obj[CC.IDENTITY_FIELD] = identity
    return obj


def _failed_on_identity(result):
    assert result["action"] == "failed", result
    assert result["failedParts"] == ["identity"], result
    assert result["results"]["identityPresent"] is False
    assert result["recordWritten"] is False
    assert _first(result) == FIRST, result["message"]


def _failed_on_unreported_identity(result):
    assert result["action"] == "failed", result
    assert result["failedParts"] == ["identity"], result
    assert result["results"]["identityPresent"] is False
    assert result["recordWritten"] is False
    assert _first(result) == UNREPORTED, result["message"]
    assert "GIT_AUTHOR_NAME" not in result["message"]


# --- launch_doctrine.git_identity: against a real repository -------------------------------

def test_git_identity_is_author_only_with_only_the_author_variables(repo, monkeypatch):
    monkeypatch.setenv("GIT_AUTHOR_NAME", "A")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "a@example.invalid")
    # axis: the author variables give the author identity and leave the committer one false
    assert LD.git_identity(repo) == {"author": True, "committer": False}


def test_git_identity_is_false_when_the_directory_is_missing(repo, tmp_path):
    # axis: a directory that does not exist gives two false flags and no raise
    assert LD.git_identity(str(tmp_path / "no-such-directory")) == NEITHER


# --- report --------------------------------------------------------------------------------

def test_report_carries_the_identity_from_identity_fn(tmp_path):
    seen = []

    def identity_fn(cwd):
        seen.append(cwd)
        return {"author": True, "committer": False}

    obj = CC.report(env={}, cwd=str(tmp_path), root=str(tmp_path / "no-store"), nonce=NONCE,
                    confirm_fn=_confirm(), identity_fn=identity_fn)
    # axis: the report carries exactly what identity_fn returned for the report's own cwd
    assert obj[CC.IDENTITY_FIELD] == {"author": True, "committer": False}
    assert seen == [str(tmp_path)]


def test_report_carries_both_false_when_identity_fn_raises(tmp_path):
    def raising(cwd):
        raise RuntimeError("no git")

    obj = CC.report(env={}, cwd=str(tmp_path), root=str(tmp_path / "no-store"), nonce=NONCE,
                    confirm_fn=_confirm(), identity_fn=raising)
    # axis: an identity_fn that raises shows both flags false, never a raise out of report
    assert obj[CC.IDENTITY_FIELD] == NEITHER


def test_report_line_never_carries_the_name_or_the_email(repo, tmp_path):
    _local_config(repo)
    obj = CC.report(env={}, cwd=repo, root=str(tmp_path / "no-store"), nonce=NONCE,
                    confirm_fn=_confirm())
    assert obj[CC.IDENTITY_FIELD] == BOTH
    line = CC.report_line(obj)
    # axis: the report line carries the two flags and never the resolved name or email
    assert EMAIL not in line and "Owner" not in line


# --- judge ---------------------------------------------------------------------------------

def test_judge_passes_with_a_configured_author_and_committer(tmp_path):
    local, cloud = _pair(tmp_path)
    result = _judge(local, _with_identity(cloud, BOTH))
    # axis: both flags true with every other part agreeing is a pass
    assert result["action"] == "passed" and result["failedParts"] == []
    assert result["results"]["identityPresent"] is True


def test_judge_fails_on_identity_when_the_report_has_none(tmp_path):
    local, cloud = _pair(tmp_path)
    obj = _cloud_report(cloud)
    del obj[CC.IDENTITY_FIELD]
    # axis: a report without an identity key does not show a configured identity, so the check
    # fails, but the identity was never reported and the message does not claim there is none
    _failed_on_unreported_identity(_judge(local, obj))


def test_judge_fails_on_identity_when_it_is_null(tmp_path):
    local, cloud = _pair(tmp_path)
    # axis: a null identity is not a configured identity, so the check fails, but the identity was
    # never reported and the message does not claim there is none
    _failed_on_unreported_identity(_judge(local, _with_identity(cloud, None)))


def test_judge_fails_on_identity_when_it_is_not_a_dict(tmp_path):
    local, cloud = _pair(tmp_path)
    for bad in (["author", "committer"], "author committer", True, 1):
        # axis: only a dict with both flags true counts; a truthy non-dict never does, and as a
        # non-dict it was never reported, so the message does not claim there is no identity
        _failed_on_unreported_identity(_judge(local, _with_identity(cloud, bad)))


def test_judge_fails_on_identity_without_a_committer(tmp_path):
    local, cloud = _pair(tmp_path)
    for committer in (False, "true", 1, None, "missing"):
        identity = {"author": True}
        if committer != "missing":
            identity["committer"] = committer
        # axis: the committer identity must be exactly true
        _failed_on_identity(_judge(local, _with_identity(cloud, identity)))


def test_judge_fails_on_identity_without_an_author(tmp_path):
    local, cloud = _pair(tmp_path)
    for author in (False, "true", 1, None, "missing"):
        identity = {"committer": True}
        if author != "missing":
            identity["author"] = author
        # axis: the author identity must be exactly true
        _failed_on_identity(_judge(local, _with_identity(cloud, identity)))


def test_judge_identity_message_ends_with_the_fix(repo, tmp_path):
    local, cloud = _pair(tmp_path)
    result = _judge(local, _with_identity(cloud, NEITHER))
    # axis: the message ends with the fix line, "your name" and "your email" where this machine
    # resolves no identity
    assert result["message"].endswith("To fix it, " + FIX + " and say \"check again\".")


def test_judge_reads_an_older_cloud_report_with_no_identity_and_fails_it(tmp_path):
    local, cloud = _pair(tmp_path)
    obj = _cloud_report(cloud, pluginVersion="0.0.1")
    del obj[CC.IDENTITY_FIELD]
    result = _judge(local, obj)
    # axis: an older cloud report with no identity key fails on identity beside its other part
    assert result["action"] == "failed", result
    assert result["failedParts"] == ["version", "identity"]


def test_the_fallback_line_does_not_pass_on_identity(tmp_path):
    local, _cloud = _pair(tmp_path)
    result = _judge(local, CC._fallback_line(NONCE))
    # axis: the line a session that cannot run `report` gives never passes the identity part
    assert result["action"] != "passed"
    assert result["results"]["identityPresent"] is False


# --- an unreported identity is not a missing one -------------------------------------------------

def _unreported(cloud, **changes):
    obj = _cloud_report(cloud, **changes)
    del obj[CC.IDENTITY_FIELD]
    return obj


def test_the_fallback_line_never_says_there_is_no_identity(tmp_path):
    local, _cloud = _pair(tmp_path)
    result = _judge(local, CC._fallback_line(NONCE))
    # axis: a session that reported no identity is never told it has none, nor given the variables fix
    assert "identity" in result["failedParts"]
    assert "has no git identity" not in result["message"]
    assert "GIT_AUTHOR_NAME" not in result["message"]


def test_an_older_report_without_identity_never_says_there_is_no_identity(tmp_path):
    local, cloud = _pair(tmp_path)
    result = _judge(local, _unreported(cloud, pluginVersion="0.0.1"))
    # axis: the count follows the sentences listed, so an unreported identity beside another part
    # adds neither a sentence, a fix nor a part to the count
    assert result["failedParts"] == ["version", "identity"]
    assert result["message"].split("\n\n")[0] == (
        "**The check failed on one part.** The cloud's plugin is 0.0.1 and mine is %s." % VERSION)
    assert "GIT_AUTHOR_NAME" not in result["message"]


def test_an_unreported_identity_alone_says_it_was_not_reported(tmp_path):
    local, cloud = _pair(tmp_path)
    result = _judge(local, _unreported(cloud))
    # axis: an unreported identity that is the only failed part is named as unreported, with the
    # setup-text fix
    assert result["failedParts"] == ["identity"]
    assert result["message"] == (
        "**The check failed on one part.** The cloud session did not report its git identity.\n\n"
        "Cloud builds are paused for this account until the check passes. They resume by "
        "themselves once the check passes. To fix it, paste the new setup text into the "
        "environment and say \"check again\".")


def test_an_unreported_identity_spawns_no_local_identity_read(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(CC, "_local_identity", lambda cwd: calls.append(cwd))
    local, cloud = _pair(tmp_path)
    result = _judge(local, _unreported(cloud))
    # axis: an identity the session never reported spawns no git process on the owner's machine
    assert result["failedParts"] == ["identity"]
    assert calls == []


# --- the fix line carries the owner's own name and email, only in the message ----------------

def _files_under(*directories):
    for directory in directories:
        for base, _dirs, names in os.walk(directory):
            for name in names:
                yield os.path.join(base, name)


def test_judge_message_names_the_local_identity_in_the_fix(repo, tmp_path):
    local, cloud = _pair(tmp_path)
    _local_config(local.cwd)
    result = _judge(local, _with_identity(cloud, NEITHER))
    # axis: the fix line names the name and email this machine resolves, set off in backticks
    _failed_on_identity(result)
    assert "set GIT_AUTHOR_NAME and GIT_COMMITTER_NAME to `Owner`" in result["message"]
    assert "GIT_COMMITTER_EMAIL to `owner@example.invalid`, in the environment's variables" \
        in result["message"]


def test_judge_message_says_your_name_and_your_email_with_no_local_identity(repo, tmp_path):
    local, cloud = _pair(tmp_path)
    result = _judge(local, _with_identity(cloud, NEITHER))
    # axis: with no identity on this machine the fix line asks for the owner's own name and email
    _failed_on_identity(result)
    assert "to your name" in result["message"] and "to your email" in result["message"]


def test_the_owner_email_is_stored_in_no_file(repo, tmp_path):
    local, cloud = _pair(tmp_path)
    _local_config(local.cwd)
    result = _judge(local, _with_identity(cloud, NEITHER))
    assert EMAIL in result["message"]
    marker = CC.read_failed_check(local.cwd, ACCOUNT, local.root)
    assert marker is not None and "identity" in marker["failedParts"]
    store = mode_registry.project_store_dir(local.cwd, local.root)
    files = list(_files_under(store, local.root))
    assert any(path.endswith(CC.FAILED_CHECK_SUFFIX) for path in files)
    # axis: not stored: the email appears in no file of the store or of the root, marker included
    for path in files:
        with open(path, "rb") as fh:
            assert EMAIL.encode() not in fh.read(), path


def test_the_setup_text_writes_no_git_config_step(tmp_path):
    local, _cloud = _pair(tmp_path)
    got = cloud_setup_text.compose(
        local.cwd, now=1760097600.0, stamp_fn=lambda files: "2026-10-10:" + "0" * 12,
        plugin_source="https://github.com/acme/superheroes.git",
        plugin_commit="0123456789abcdef" * 2 + "01234567", plugin_subdir="plugins/superheroes",
        project_name="Corner Shop", root=local.root, env=local.env,
        source_dir=str(tmp_path / "opt" / "src"), plugin_dir=str(tmp_path / "opt" / "plugin"))
    assert got["action"] == "written", got
    # axis: no step: the setup text carries no `git config` line, so the identity is never written
    assert "git config" not in got["text"]


def test_cloud_check_holds_no_identity_implementation_of_its_own(repo, monkeypatch, tmp_path):
    # axis: one implementation: cloud_check has no identity test of its own and report calls the
    # doctrine's
    assert not hasattr(CC, "_git_identity")
    monkeypatch.setattr(LD, "git_identity", lambda cwd: {"author": True, "committer": False})
    obj = CC.report(env={}, cwd=repo, root=str(tmp_path / "no-store"), nonce=NONCE,
                    confirm_fn=_confirm())
    assert obj[CC.IDENTITY_FIELD] == {"author": True, "committer": False}


def test_report_with_no_identity_fn_carries_the_doctrines_value(repo, tmp_path):
    _local_config(repo)
    obj = CC.report(env={}, cwd=repo, root=str(tmp_path / "no-store"), nonce=NONCE,
                    confirm_fn=_confirm())
    # axis: the flags in the report are the ones launch_doctrine.git_identity gives for that cwd
    assert obj[CC.IDENTITY_FIELD] == LD.git_identity(repo) == BOTH


# --- _local_identity: fail-closed edges ---------------------------------------------------------

class _Ran:
    def __init__(self, returncode, stdout):
        self.returncode, self.stdout = returncode, stdout


def test_local_identity_reads_the_name_and_email(repo):
    _local_config(repo)
    # axis: the ident line parses to the name and the email, and nothing else
    assert CC._local_identity(repo) == ("Owner", EMAIL)


def test_local_identity_is_none_when_git_var_fails(repo):
    # axis: E1: git var exiting non-zero (no identity set) gives None
    assert CC._local_identity(repo) is None


def test_local_identity_is_none_for_unparseable_output(repo, monkeypatch):
    for out in ("", "garbage", "Owner <> 1 +0000", "<owner@example.invalid> 1 +0000",
                "Owner <owner@example.invalid> x +0000"):
        monkeypatch.setattr(CC.subprocess, "run", lambda *a, _out=out, **k: _Ran(0, _out))
        # axis: E2: output that is not `name <email> stamp zone` with both parts gives None
        assert CC._local_identity(repo) is None, out


def test_local_identity_is_none_when_the_directory_is_missing(repo, tmp_path):
    # axis: E3: a missing directory gives None and no raise
    assert CC._local_identity(str(tmp_path / "no-such-directory")) is None


def test_local_identity_is_not_called_when_the_identity_part_did_not_fail(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(CC, "_local_identity", lambda cwd: calls.append(cwd))
    local, cloud = _pair(tmp_path)
    result = _judge(local, _with_identity(cloud, BOTH))
    # axis: E4: a passing identity part spawns no git on the owner's machine
    assert result["action"] == "passed"
    assert calls == []


def test_a_name_and_email_with_braces_do_not_break_the_fix_line(repo, tmp_path):
    local, cloud = _pair(tmp_path)
    _local_config(local.cwd, name="A{b}", email="a{b}@example.invalid")
    result = _judge(local, _with_identity(cloud, NEITHER))
    # axis: E5: braces in the name or email are values, never format fields
    _failed_on_identity(result)
    assert "to `A{b}`" in result["message"] and "to `a{b}@example.invalid`" in result["message"]
