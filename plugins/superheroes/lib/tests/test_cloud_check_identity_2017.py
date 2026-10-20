"""Tests for the cloud check's git identity part (#2017): the cloud session must resolve a configured
author and committer identity, a guessed one never counts, and the report line carries neither a
name nor an email.

The identity helper runs against a real `git init` repository under tmp_path, with the home, the
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
from test_cloud_check import NONCE, _cloud_report, _confirm, _first, _judge, _pair  # noqa: E402

FIRST = ("**The check failed on one part.** The cloud session has no git identity to commit with, "
         "so a build there would stop at its first commit.")
FIX = ("set GIT_AUTHOR_NAME, GIT_AUTHOR_EMAIL, GIT_COMMITTER_NAME and GIT_COMMITTER_EMAIL to your "
       "name and email in the environment's variables")
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


# --- _git_identity: against a real repository ----------------------------------------------

def test_git_identity_is_false_when_nothing_is_set(repo):
    assert CC._git_identity(repo) == NEITHER


def test_git_identity_refuses_a_guess_from_EMAIL(repo, monkeypatch):
    monkeypatch.setenv("EMAIL", "guess@example.invalid")
    # axis: an identity git guesses (from $EMAIL, the host name or the passwd entry) never counts
    assert CC._git_identity(repo) == NEITHER


def test_git_identity_is_true_for_a_repository_config(repo):
    _local_config(repo)
    assert CC._git_identity(repo) == BOTH


def test_git_identity_is_true_for_the_four_variables(repo, monkeypatch):
    for var, value in (("GIT_AUTHOR_NAME", "A"), ("GIT_AUTHOR_EMAIL", "a@example.invalid"),
                       ("GIT_COMMITTER_NAME", "C"), ("GIT_COMMITTER_EMAIL", "c@example.invalid")):
        monkeypatch.setenv(var, value)
    assert CC._git_identity(repo) == BOTH


def test_git_identity_is_author_only_with_only_the_author_variables(repo, monkeypatch):
    monkeypatch.setenv("GIT_AUTHOR_NAME", "A")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "a@example.invalid")
    assert CC._git_identity(repo) == {"author": True, "committer": False}


def test_git_identity_is_false_when_the_directory_is_missing(repo, tmp_path):
    assert CC._git_identity(str(tmp_path / "no-such-directory")) == NEITHER


# --- report --------------------------------------------------------------------------------

def test_report_carries_the_identity_from_identity_fn(tmp_path):
    seen = []

    def identity_fn(cwd):
        seen.append(cwd)
        return {"author": True, "committer": False}

    obj = CC.report(env={}, cwd=str(tmp_path), root=str(tmp_path / "no-store"), nonce=NONCE,
                    confirm_fn=_confirm(), identity_fn=identity_fn)
    assert obj[CC.IDENTITY_FIELD] == {"author": True, "committer": False}
    assert seen == [str(tmp_path)]


def test_report_carries_both_false_when_identity_fn_raises(tmp_path):
    def raising(cwd):
        raise RuntimeError("no git")

    obj = CC.report(env={}, cwd=str(tmp_path), root=str(tmp_path / "no-store"), nonce=NONCE,
                    confirm_fn=_confirm(), identity_fn=raising)
    assert obj[CC.IDENTITY_FIELD] == NEITHER


def test_report_line_never_carries_the_name_or_the_email(repo, tmp_path):
    _local_config(repo)
    obj = CC.report(env={}, cwd=repo, root=str(tmp_path / "no-store"), nonce=NONCE,
                    confirm_fn=_confirm())
    assert obj[CC.IDENTITY_FIELD] == BOTH
    line = CC.report_line(obj)
    assert EMAIL not in line and "Owner" not in line


# --- judge ---------------------------------------------------------------------------------

def test_judge_passes_with_a_configured_author_and_committer(tmp_path):
    local, cloud = _pair(tmp_path)
    result = _judge(local, _with_identity(cloud, BOTH))
    assert result["action"] == "passed" and result["failedParts"] == []
    assert result["results"]["identityPresent"] is True


def test_judge_fails_on_identity_when_the_report_has_none(tmp_path):
    local, cloud = _pair(tmp_path)
    obj = _cloud_report(cloud)
    del obj[CC.IDENTITY_FIELD]
    # axis: a report without an identity key does not show a configured identity
    _failed_on_identity(_judge(local, obj))


def test_judge_fails_on_identity_when_it_is_null(tmp_path):
    local, cloud = _pair(tmp_path)
    _failed_on_identity(_judge(local, _with_identity(cloud, None)))


def test_judge_fails_on_identity_when_it_is_not_a_dict(tmp_path):
    local, cloud = _pair(tmp_path)
    for bad in (["author", "committer"], "author committer", True, 1):
        _failed_on_identity(_judge(local, _with_identity(cloud, bad)))


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


def test_judge_identity_message_ends_with_the_fix(tmp_path):
    local, cloud = _pair(tmp_path)
    result = _judge(local, _with_identity(cloud, NEITHER))
    assert result["message"].endswith("To fix it, " + FIX + " and say \"check again\".")


def test_judge_reads_an_older_cloud_report_with_no_identity_and_fails_it(tmp_path):
    local, cloud = _pair(tmp_path)
    obj = _cloud_report(cloud, pluginVersion="0.0.1")
    del obj[CC.IDENTITY_FIELD]
    result = _judge(local, obj)
    assert result["action"] == "failed", result
    assert result["failedParts"] == ["version", "identity"]


def test_the_fallback_line_does_not_pass_on_identity(tmp_path):
    local, _cloud = _pair(tmp_path)
    result = _judge(local, CC._fallback_line(NONCE))
    assert result["action"] != "passed"
    assert result["results"]["identityPresent"] is False
