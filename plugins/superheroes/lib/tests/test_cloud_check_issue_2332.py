"""#2332 gap 1: a cloud check is never started unless its result is readable by construction.

`start` needs a positive issue number and confirms that issue resolves before anything is spawned.
"""
import json
import subprocess

import pytest

import cloud_check as CC
import stack_check
from test_cloud_check import ENV_ID, NONCE, Spawner, _build


class Reader:
    """A fake issue reader: records every call and answers with a canned value or raises."""

    def __init__(self, answer=True, raises=None):
        self.answer = answer
        self.raises = raises
        self.calls = []

    def __call__(self, root, number):
        self.calls.append((root, number))
        if self.raises is not None:
            raise self.raises
        return self.answer


def _go(local, spawner, reader, **kw):
    args = dict(environment=ENV_ID, env=local.env, spawn_fn=spawner, nonce=NONCE,
                issue_reader=reader)
    args.update(kw)
    return CC.start(local.cwd, **args)


def test_start_without_an_issue_is_refused_before_anything_is_read_or_spawned(tmp_path):
    local = _build(tmp_path)
    spawner, reader = Spawner(), Reader()
    result = _go(local, spawner, reader)
    assert result["action"] == "refused" and result["reason"] == "check-issue-required"
    assert result["message"] == (
        "A check needs an issue to post its result on, because this seat cannot read the check "
        "session's own log. Name an issue in this repository with --issue, and the check posts "
        "its one result line there.")
    assert spawner.calls == [] and reader.calls == []


@pytest.mark.parametrize("bad", [0, -1, "abc", True])
def test_start_with_a_malformed_issue_is_still_invalid(tmp_path, bad):
    local = _build(tmp_path)
    spawner, reader = Spawner(), Reader()
    assert _go(local, spawner, reader, issue=bad)["reason"] == "check-issue-invalid"
    assert spawner.calls == [] and reader.calls == []


def test_an_issue_that_does_not_resolve_spawns_nothing(tmp_path):
    local = _build(tmp_path)
    spawner, reader = Spawner(), Reader(answer=False)
    result = _go(local, spawner, reader, issue=1745)
    assert result["action"] == "refused" and result["reason"] == "check-issue-unreadable"
    assert result["message"] == (
        "I could not read issue #1745 in this repository, so the check could not post its "
        "result there. Name an issue that exists here.")
    assert len(reader.calls) == 1 and reader.calls[0][1] == 1745
    assert spawner.calls == []


def test_only_true_passes_the_reader_check(tmp_path):
    local = _build(tmp_path)
    spawner = Spawner()
    result = _go(local, spawner, Reader(answer="yes"), issue=1745)
    assert result["reason"] == "check-issue-unreadable" and spawner.calls == []


def test_a_reader_that_raises_is_an_unreadable_issue(tmp_path):
    local = _build(tmp_path)
    spawner = Spawner()
    result = _go(local, spawner, Reader(raises=RuntimeError("boom")), issue=1745)
    assert result["reason"] == "check-issue-unreadable" and spawner.calls == []


def test_a_readable_issue_starts_the_check_and_the_message_names_it(tmp_path):
    local = _build(tmp_path)
    spawner, reader = Spawner(), Reader()
    result = _go(local, spawner, reader, issue=1745)
    assert result["action"] == "started" and result["issue"] == 1745
    assert "issue #1745" in result["message"]
    assert result["message"] == ("The check session is running. It posts its result line on "
                                 "issue #1745; I'll read it there in about a minute.")
    assert len(spawner.calls) == 1 and len(reader.calls) == 1


def test_the_issue_is_read_before_the_model_is_resolved(tmp_path, monkeypatch):
    local = _build(tmp_path)

    def boom(*a, **k):
        raise AssertionError("the model was resolved before the issue was read")

    monkeypatch.setattr(CC.model_registry, "resolve_dispatch", boom)
    spawner = Spawner()
    result = _go(local, spawner, Reader(answer=False), issue=1745)
    assert result["reason"] == "check-issue-unreadable" and spawner.calls == []


class _Done:
    def __init__(self, returncode, stdout):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = ""


def _patch_gh(monkeypatch, *, slug=("owner/repo", None), done=None, raises=None):
    ran = []
    monkeypatch.setattr(stack_check, "resolve_repo_slug", lambda root, **k: slug)

    def run(argv, **kw):
        ran.append(argv)
        if raises is not None:
            raise raises
        return done

    monkeypatch.setattr(CC.subprocess, "run", run)
    return ran


def test_the_default_reader_is_false_when_the_slug_cannot_be_resolved(monkeypatch):
    ran = _patch_gh(monkeypatch, slug=(None, {"reason": "stack-unreadable"}),
                    done=_Done(0, json.dumps({"number": 1745})))
    assert CC._issue_resolves("/repo", 1745) is False and ran == []


def test_the_default_reader_is_false_on_a_non_zero_exit(monkeypatch):
    _patch_gh(monkeypatch, done=_Done(1, ""))
    assert CC._issue_resolves("/repo", 1745) is False


def test_the_default_reader_is_false_on_unparsable_json(monkeypatch):
    _patch_gh(monkeypatch, done=_Done(0, "not json"))
    assert CC._issue_resolves("/repo", 1745) is False


def test_the_default_reader_is_false_for_another_issue_number(monkeypatch):
    _patch_gh(monkeypatch, done=_Done(0, json.dumps({"number": 7})))
    assert CC._issue_resolves("/repo", 1745) is False


def test_the_default_reader_is_true_for_the_named_issue(monkeypatch):
    ran = _patch_gh(monkeypatch, done=_Done(0, json.dumps({"number": 1745})))
    assert CC._issue_resolves("/repo", 1745) is True
    assert ran == [["gh", "api", "repos/owner/repo/issues/1745"]]


def test_the_default_reader_is_false_when_running_gh_raises(monkeypatch):
    _patch_gh(monkeypatch, raises=subprocess.TimeoutExpired("gh", 60))
    assert CC._issue_resolves("/repo", 1745) is False


def test_the_command_line_start_without_an_issue_exits_one(tmp_path, capsys):
    local = _build(tmp_path)
    spawner = Spawner()
    code = CC.main(["start", "--environment", ENV_ID, "--cwd", local.cwd], spawn_fn=spawner)
    printed = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert code == 1 and printed["reason"] == "check-issue-required"
    assert spawner.calls == []
