"""Tests for cloud_builder (#1747 C6-WO-A): the cloud builder's machine-side steps.

No test touches the network, the real home directory or the reviewer tool. The git calls are
recorded by a fake `run` except in the one real-git test, which builds throwaway repositories
under tmp_path and never leaves them.
"""
import base64
import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_builder as cb  # noqa: E402
import cloud_pass  # noqa: E402
import launcher  # noqa: E402

VERSION = "9.8.7"
OTHER_VERSION = "9.8.6"
ENV_ID = "env_01ABCdef"
OTHER_ENV_ID = "env_99ZZZ"
SHA = "a" * 40
MAIN_REF = "refs/remotes/origin/main"
NOW = 1_800_000_000


def _launch(version=VERSION, environment=ENV_ID, base=SHA, extra=""):
    lines = []
    if version is not None:
        lines.append("Advisor plugin version: %s" % version)
    if environment is not None:
        lines.append("Cloud environment: %s" % environment)
    if base is not None:
        lines.append("Base commit: %s" % base)
    return "Build issue 1747.\n\n" + "\n".join(lines) + "\n" + extra


def _session(**extra):
    env = {cloud_pass.ENVIRONMENT_ENV: ENV_ID}
    env.update(extra)
    return env


class FakeRun:
    """Records every call; `answers` maps the argv tail after `git -C D` (or the gh argv) to an
    exit code and stdout, a raised exception, or a callable of the argv."""

    def __init__(self, answers=None, shallow=("false",)):
        self.calls = []
        self.answers = answers or {}
        self.shallow = list(shallow)

    def __call__(self, argv, **kwargs):
        self.calls.append((list(argv), kwargs))
        key = " ".join(argv[3:]) if argv[:2] == ["git", "-C"] else " ".join(argv)
        answer = self.answers.get(key)
        if key.endswith("--is-shallow-repository") and answer is None:
            value = self.shallow.pop(0) if len(self.shallow) > 1 else self.shallow[0]
            answer = (0, value + "\n")
        if answer is None:
            answer = (0, "")
        if isinstance(answer, BaseException):
            raise answer
        code, out = answer
        return SimpleNamespace(returncode=code, stdout=out, stderr="")

    @property
    def argvs(self):
        return [argv for argv, _ in self.calls]

    @property
    def git_calls(self):
        return [argv for argv in self.argvs if argv[:1] == ["git"]]


def _sha_key(sub):
    return {"fetch": "fetch origin %s" % SHA, "cat": "cat-file -e %s^{commit}" % SHA,
            "checkout": "checkout --detach %s" % SHA}[sub]


SHALLOW_KEY = "rev-parse --is-shallow-repository"
UNSHALLOW_KEY = "fetch --unshallow origin"
MAIN_FETCH_KEY = "fetch origin +refs/heads/main:%s" % MAIN_REF
VERIFY_KEY = "rev-parse --verify --quiet %s" % MAIN_REF


def _intake(run, launch=None, env=None, version=VERSION):
    return cb.intake("/repo", launch if launch is not None else _launch(),
                     env=_session() if env is None else env, run=run, running_version=version)


def _assert_refusal(result, reason):
    assert result["ok"] is False
    assert result["outcome"] == "refusal"
    assert result["reason"] == reason
    assert result["startedFrom"] is None
    assert result["comment"].startswith("Builder refusal (cloud build).\n\n")


# ---------------------------------------------------------------- parse_launch


def test_parse_launch_reads_the_three_lines():
    text = "  Advisor plugin version: 1.2.3  \nnoise\n\tCloud environment: env_abc123\r\n" \
           "Base commit: %s\n" % SHA
    assert cb.parse_launch(text) == {"advisorVersion": "1.2.3", "environment": "env_abc123",
                                     "baseCommit": SHA, "adoptsBranch": None, "adoptsHead": None}


def test_parse_launch_missing_lines_are_none():
    assert cb.parse_launch("nothing here") == {"advisorVersion": None, "environment": None,
                                               "baseCommit": None, "adoptsBranch": None, "adoptsHead": None}
    assert cb.parse_launch(None)["baseCommit"] is None


@pytest.mark.parametrize("environment", ["env_", "env-abc", "ENV_abc", "env_ab cd", "env_ab-cd",
                                         "xenv_abc"])
def test_parse_launch_malformed_environment_is_none(environment):
    assert cb.parse_launch(_launch(environment=environment))["environment"] is None


@pytest.mark.parametrize("base", ["a" * 39, "a" * 41, "A" * 40, "g" * 40, "HEAD", "a" * 40 + "x"])
def test_parse_launch_malformed_base_is_none(base):
    assert cb.parse_launch(_launch(base=base))["baseCommit"] is None


def test_parse_launch_conflicting_repeats_read_as_missing():
    text = _launch() + "Base commit: %s\n" % ("b" * 40)
    assert cb.parse_launch(text)["baseCommit"] is None


# ---------------------------------------------------------------- intake: E1-E6, zero git calls


def test_e1_version_missing_on_the_launch_side():
    run = FakeRun()
    result = _intake(run, launch=_launch(version=None))
    _assert_refusal(result, "plugin-version-mismatch")
    assert run.calls == []
    assert VERSION in result["comment"] and "an unreadable version" in result["comment"]


@pytest.mark.parametrize("running", [None, "", "   ", 3])
def test_e1_version_missing_on_the_running_side(running, monkeypatch):
    monkeypatch.setattr(launcher, "plugin_version", lambda: None)
    run = FakeRun()
    result = _intake(run, version=running)
    _assert_refusal(result, "plugin-version-mismatch")
    assert run.calls == []
    assert VERSION in result["comment"] and "an unreadable version" in result["comment"]


def test_e1_default_running_version_comes_from_the_launcher(monkeypatch):
    monkeypatch.setattr(launcher, "plugin_version", lambda: VERSION)
    run = FakeRun()
    result = cb.intake("/repo", _launch(), env=_session(), run=run)
    assert result["ok"] is True and result["pluginVersion"] == VERSION


def test_e2_version_unequal():
    run = FakeRun()
    result = _intake(run, launch=_launch(version=OTHER_VERSION))
    _assert_refusal(result, "plugin-version-mismatch")
    assert run.git_calls == [] and run.calls == []
    assert VERSION in result["comment"] and OTHER_VERSION in result["comment"]


@pytest.mark.parametrize("env", [{}, {cloud_pass.ENVIRONMENT_ENV: ""},
                                 {cloud_pass.ENVIRONMENT_ENV: "   "}])
def test_e3_environment_variable_missing_or_blank(env):
    run = FakeRun()
    result = _intake(run, env=env)
    _assert_refusal(result, "cloud-environment-mismatch")
    assert run.calls == []
    assert ENV_ID in result["comment"] and "no environment" in result["comment"]


@pytest.mark.parametrize("environment", [None, "env_", "not-an-env"])
def test_e4_environment_line_missing_or_malformed(environment):
    run = FakeRun()
    result = _intake(run, launch=_launch(environment=environment))
    _assert_refusal(result, "cloud-environment-mismatch")
    assert run.calls == []
    assert "no environment" in result["comment"]


def test_e5_environment_unequal():
    run = FakeRun()
    result = _intake(run, launch=_launch(environment=OTHER_ENV_ID))
    _assert_refusal(result, "cloud-environment-mismatch")
    assert run.calls == []
    assert ENV_ID in result["comment"] and OTHER_ENV_ID in result["comment"]


def test_e5_environment_variable_is_stripped_before_comparing():
    run = FakeRun()
    assert _intake(run, env=_session(**{cloud_pass.ENVIRONMENT_ENV: " %s\n" % ENV_ID}))["ok"]


def test_e5_a_malformed_environment_variable_is_never_printed():
    run = FakeRun()
    result = _intake(run, env={cloud_pass.ENVIRONMENT_ENV: "hunter2-not-an-id"})
    _assert_refusal(result, "cloud-environment-mismatch")
    assert run.calls == []
    assert "hunter2" not in result["comment"] and ENV_ID in result["comment"]


@pytest.mark.parametrize("base", [None, "abc123", "g" * 40, "a" * 41])
def test_e6_base_line_missing_or_not_40_hex(base):
    run = FakeRun()
    result = _intake(run, launch=_launch(base=base))
    _assert_refusal(result, "base-commit-missing")
    assert run.calls == []


# ---------------------------------------------------------------- ensure_history: E7-E10, E15


def _history(run, **kw):
    return cb.ensure_history("/repo", env={"GIT_DIR": "x", "KEEP": "1"}, run=run, **kw)


@pytest.mark.parametrize("answer", [(0, "maybe\n"), (0, ""), (0, "True"), (128, "true\n"),
                                    OSError("no git"),
                                    subprocess.TimeoutExpired("git", 1)])
def test_e7_shallow_answer_unreadable(answer):
    run = FakeRun({SHALLOW_KEY: answer})
    assert _history(run) == {"ok": False, "reason": "shallow-state-unreadable", "fetched": []}
    assert [a[3:] for a in run.git_calls] == [["rev-parse", "--is-shallow-repository"]]


def test_e8_unshallow_fails():
    run = FakeRun({UNSHALLOW_KEY: (1, "")}, shallow=("true",))
    result = _history(run)
    assert result["ok"] is False and result["reason"] == "unshallow-failed"
    assert not any(a[3:5] == ["fetch", "origin"] and a[5].startswith("+") for a in run.git_calls)


def test_e8_unshallow_raises():
    run = FakeRun({UNSHALLOW_KEY: OSError("gone")}, shallow=("true",))
    assert _history(run)["reason"] == "unshallow-failed"


def test_e9_main_fetch_fails():
    run = FakeRun({MAIN_FETCH_KEY: (1, "")}, shallow=("true", "false"))
    result = _history(run)
    assert result["ok"] is False and result["reason"] == "main-fetch-failed"
    assert result["fetched"] == ["unshallow"]


def test_e9_main_fetch_raises():
    run = FakeRun({MAIN_FETCH_KEY: subprocess.TimeoutExpired("git", 1)})
    assert _history(run)["reason"] == "main-fetch-failed"


def test_e10_history_still_incomplete_when_still_shallow():
    run = FakeRun(shallow=("true",))
    result = _history(run)
    assert result["ok"] is False and result["reason"] == "history-still-incomplete"


def test_e10_history_still_incomplete_when_origin_main_is_missing():
    run = FakeRun({VERIFY_KEY: (1, "")})
    assert _history(run)["reason"] == "history-still-incomplete"


def test_ensure_history_full_clone_runs_only_the_main_fetch_and_is_idempotent():
    run = FakeRun()
    for _ in range(2):
        assert _history(run) == {"ok": True, "reason": None, "fetched": ["origin/main"]}
    assert not any(UNSHALLOW_KEY == " ".join(a[3:]) for a in run.git_calls)


def test_ensure_history_shallow_clone_unshallows_then_fetches_the_main_branch():
    run = FakeRun(shallow=("true", "false"))
    result = _history(run, main_branch="trunk")
    assert result == {"ok": True, "reason": None, "fetched": ["unshallow", "origin/trunk"]}
    tails = [" ".join(a[3:]) for a in run.git_calls]
    assert tails[1:3] == [UNSHALLOW_KEY,
                          "fetch origin +refs/heads/trunk:refs/remotes/origin/trunk"]


def test_ensure_history_strips_only_git_variables_from_the_env():
    run = FakeRun()
    cb.ensure_history("/repo", env={"GIT_DIR": "x", "GIT_SSH_COMMAND": "y", "KEEP": "1",
                                    "gitlike": "2"}, run=run)
    assert run.calls
    for _, kwargs in run.calls:
        assert kwargs["env"] == {"KEEP": "1", "gitlike": "2"}


def test_ensure_history_budget_caps_every_git_timeout_and_a_spent_budget_runs_nothing():
    run = FakeRun(shallow=("true", "false"))
    assert _history(run, budget=30)["ok"] is True
    assert all(kwargs["timeout"] <= 30 for _, kwargs in run.calls)
    spent = FakeRun()
    result = _history(spent, budget=0)
    assert result["ok"] is False and spent.calls == []


# ---------------------------------------------------------------- intake: step 4 onward


def test_intake_maps_a_not_ok_history_to_history_unfetchable():
    run = FakeRun({MAIN_FETCH_KEY: (1, "")})
    result = _intake(run)
    _assert_refusal(result, "history-unfetchable")
    assert not any("checkout" in a for a in run.argvs)


def test_e11_base_fetch_fails():
    run = FakeRun({_sha_key("fetch"): (1, "")})
    result = _intake(run)
    _assert_refusal(result, "base-commit-unfetchable")
    assert not any("checkout" in a for a in run.argvs)


def test_e11_base_missing_after_the_fetch():
    run = FakeRun({_sha_key("cat"): (1, "")})
    result = _intake(run)
    _assert_refusal(result, "base-commit-unfetchable")
    assert not any("checkout" in a for a in run.argvs)


def test_e12_base_checkout_fails():
    run = FakeRun({_sha_key("checkout"): (1, "")})
    _assert_refusal(_intake(run), "base-checkout-failed")


@pytest.mark.parametrize("which,reason", [("fetch", "base-commit-unfetchable"),
                                          ("cat", "base-commit-unfetchable"),
                                          ("checkout", "base-checkout-failed")])
def test_e15_a_raising_run_in_the_base_steps_returns_the_steps_token(which, reason):
    run = FakeRun({_sha_key(which): OSError("gone")})
    _assert_refusal(_intake(run), reason)


def test_intake_success_runs_the_checks_in_order_and_returns_the_board_text():
    run = FakeRun()
    result = _intake(run)
    assert result == {"ok": True, "outcome": None, "reason": None, "startedFrom": SHA,
                      "comment": cb.INTAKE_TEXT.format(v=VERSION, sha=SHA),
                      "pluginVersion": VERSION, "branch": None}
    tails = [" ".join(a[3:]) for a in run.git_calls]
    assert tails == [SHALLOW_KEY, MAIN_FETCH_KEY, VERIFY_KEY, SHALLOW_KEY, _sha_key("fetch"),
                     _sha_key("cat"), _sha_key("checkout")]


# ---------------------------------------------------------------- the DoD row


def test_dod_version_mismatch_is_a_refusal_naming_both_versions_with_no_git_call():
    run = FakeRun()
    result = _intake(run, launch=_launch(version=OTHER_VERSION))
    assert result["outcome"] == "refusal" and result["outcome"] != "park"
    assert run.git_calls == []
    assert result["comment"] == (
        "Builder refusal (cloud build).\n\n"
        "This cloud session runs plugin %s; the launch named plugin %s. I built nothing. This "
        "lane ends as a refusal, and the advisor relaunches the build on the owner's machine."
        % (VERSION, OTHER_VERSION))


def test_dod_the_composed_refusal_posts_as_exactly_one_issue_comment(tmp_path):
    refusal = _intake(FakeRun(), launch=_launch(version=OTHER_VERSION))
    body = tmp_path / "body.md"
    body.write_text(refusal["comment"], encoding="utf-8")
    run = FakeRun({"gh api -X POST repos/o/r/issues/1747/comments -F body=@%s" % body:
                   (0, json.dumps({"html_url": "https://github.com/o/r/issues/1747#c1"}))})
    result = cb.post_comment("o/r", 1747, str(body), run=run, env={})
    assert result == {"ok": True, "reason": None, "url": "https://github.com/o/r/issues/1747#c1"}
    assert run.argvs == [["gh", "api", "-X", "POST", "repos/o/r/issues/1747/comments", "-F",
                          "body=@%s" % body]]


# ---------------------------------------------------------------- refusal texts


def test_refusal_text_other_reasons_and_no_secret_words():
    run = FakeRun({_sha_key("checkout"): (1, "")})
    result = _intake(run, env=_session(SUPERHEROES_REVIEWER_PASS="pass-secret",
                                       OTHER="other-secret"))
    assert result["comment"] == (
        "Builder refusal (cloud build).\n\n"
        "I could not start from the launch's base commit (base-checkout-failed). I built "
        "nothing. This lane ends as a refusal.")
    mismatch = _intake(FakeRun(), launch=_launch(environment=OTHER_ENV_ID),
                       env=_session(SUPERHEROES_REVIEWER_PASS="pass-secret"))
    assert mismatch["comment"] == (
        "Builder refusal (cloud build).\n\n"
        "This cloud session's environment variable names %s; the launch named %s. I built "
        "nothing. This lane ends as a refusal." % (ENV_ID, OTHER_ENV_ID))
    for text in (result["comment"], mismatch["comment"]):
        assert "pass-secret" not in text and "other-secret" not in text
        assert "reviewer pass" not in text.lower() and "token" not in text.lower()


# ---------------------------------------------------------------- real git, no network


def _git(cwd, *args, env=None):
    pinned = ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")
    clean = {k: v for k, v in (env or os.environ).items()
             if not k.startswith("GIT_") or k in pinned}
    done = subprocess.run(["git", "-C", str(cwd)] + list(args), capture_output=True, text=True,
                          env=clean)
    assert done.returncode == 0, (args, done.stderr)
    return done.stdout.strip()


def _commit(work, name):
    (work / name).write_text(name, encoding="utf-8")
    _git(work, "add", name)
    _git(work, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-m", name)


def test_real_git_unshallows_and_intake_checks_out_the_second_commit(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-b", "main")
    for name in ("one", "two", "three"):
        _commit(work, name)
    second = _git(work, "rev-parse", "HEAD~1")
    origin = tmp_path / "origin.git"
    _git(tmp_path, "clone", "--bare", str(work), str(origin))
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "--depth", "1", "file://%s" % origin, str(clone))
    _git(clone, "update-ref", "-d", MAIN_REF)
    assert _git(clone, "rev-parse", "--is-shallow-repository") == "true"
    assert subprocess.run(["git", "-C", str(clone), "rev-parse", "--verify", "--quiet", MAIN_REF],
                          capture_output=True).returncode != 0

    env = dict(os.environ)
    result = cb.ensure_history(str(clone), env=env)
    assert result["ok"] is True and result["reason"] is None
    assert _git(clone, "rev-parse", "--is-shallow-repository") == "false"
    assert _git(clone, "rev-parse", MAIN_REF) == _git(origin, "rev-parse", "refs/heads/main")

    env[cloud_pass.ENVIRONMENT_ENV] = ENV_ID
    taken = cb.intake(str(clone), _launch(base=second), env=env, running_version=VERSION)
    assert taken["ok"] is True and taken["startedFrom"] == second
    assert _git(clone, "rev-parse", "HEAD") == second
    assert subprocess.run(["git", "-C", str(clone), "symbolic-ref", "-q", "HEAD"],
                          capture_output=True).returncode != 0


# ---------------------------------------------------------------- github_channel


def test_github_channel_truth_table():
    ok = {"tool": "gh auth", "ok": True, "exit": 0, "detail": ""}
    bad = {"tool": "gh auth", "ok": False, "exit": 1, "detail": "no"}
    assert cb.github_channel(ok, "not-tried") == {"ok": True, "channel": "gh"}
    assert cb.github_channel(bad, "ok") == {"ok": True, "channel": "tools"}
    refused = {"ok": False, "channel": None, "reason": "no-github-channel"}
    assert cb.github_channel(bad, "failed") == refused
    assert cb.github_channel(bad, "not-tried") == refused
    assert cb.github_channel({}, "failed") == refused
    assert cb.github_channel(None, "not-tried") == refused
    assert cb.github_channel({"ok": "true"}, "failed") == refused


def test_a_rest_read_probe_is_not_proof_of_write():
    rest = {"tool": "gh auth", "ok": True, "exit": 0, "detail": "", "channel": "rest"}
    assert cb.github_channel(rest, "ok") == {"ok": True, "channel": "tools"}
    assert cb.github_channel(rest, "not-tried") == {
        "ok": False, "channel": None, "reason": "no-github-channel"}


def test_the_launchers_cloud_prompt_passes_intake(tmp_path):
    composed = launcher.compose_launch(
        ".", 1747, {"baseCommit": SHA}, model="opus", place="cloud",
        cloud_environment=ENV_ID, session_name="issue-1747-probe")
    assert composed["ok"] is True, composed
    parsed = cb.parse_launch(composed["prompt"])
    assert parsed == {"advisorVersion": composed["pluginVersion"],
                      "environment": ENV_ID, "baseCommit": SHA, "adoptsBranch": None, "adoptsHead": None}


@pytest.mark.parametrize("content", ["{not json", "[1, 2]", "\"ok\"", None])
def test_e14_malformed_probe_file_reads_as_not_ok(tmp_path, capsys, content):
    path = tmp_path / "probe.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    code = cb.main(["github-channel", "--gh-probe-file", str(path), "--tools-write", "failed"])
    assert json.loads(capsys.readouterr().out) == {"ok": False, "channel": None,
                                                    "reason": "no-github-channel"}
    assert code == 1
    code = cb.main(["github-channel", "--gh-probe-file", str(path), "--tools-write", "ok"])
    assert json.loads(capsys.readouterr().out) == {"ok": True, "channel": "tools"}
    assert code == 0


def test_github_channel_cli_reads_a_good_probe(tmp_path, capsys):
    path = tmp_path / "probe.json"
    path.write_text(json.dumps({"tool": "gh auth", "ok": True, "exit": 0, "detail": ""}))
    assert cb.main(["github-channel", "--gh-probe-file", str(path),
                    "--tools-write", "not-tried"]) == 0
    assert json.loads(capsys.readouterr().out) == {"ok": True, "channel": "gh"}


# ---------------------------------------------------------------- pr_json / repo_json / post_comment

PULLS_ENDPOINT = "gh api repos/o/r/pulls?head=o:build/1747-x&state=open"


def _pull(body="the body", number=7):
    return {"number": number, "title": "A title", "user": {"login": "zach", "id": 1},
            "head": {"ref": "build/1747-x", "sha": "b" * 40}, "base": {"ref": "main"},
            "html_url": "https://github.com/o/r/pull/%d" % number, "body": body, "state": "open"}


def _pr(stdout, code=0):
    run = FakeRun({PULLS_ENDPOINT: (code, stdout)})
    return cb.pr_json("o/r", "build/1747-x", run=run, env={}), run


def test_pr_json_one_pull_maps_to_gh_pr_view_field_names():
    result, run = _pr(json.dumps([_pull()]))
    assert result == {"ok": True, "pr": {
        "number": 7, "title": "A title", "author": {"login": "zach"},
        "headRefName": "build/1747-x", "headRefOid": "b" * 40, "baseRefName": "main",
        "url": "https://github.com/o/r/pull/7", "body": "the body"}}
    assert run.argvs == [["gh", "api", "repos/o/r/pulls?head=o:build/1747-x&state=open"]]


def test_pr_json_null_body_becomes_empty():
    assert _pr(json.dumps([_pull(body=None)]))[0]["pr"]["body"] == ""


def test_pr_json_zero_and_many():
    assert _pr("[]")[0] == {"ok": False, "reason": "pr-not-found"}
    assert _pr(json.dumps([_pull(), _pull(number=8)]))[0] == {"ok": False,
                                                                "reason": "pr-ambiguous"}


@pytest.mark.parametrize("stdout,code", [("garbage", 0), ("", 0), ("{\"message\": \"x\"}", 0),
                                         ("[1]", 0), ("[{\"number\": \"7\"}]", 0),
                                         (json.dumps([_pull()]), 1)])
def test_e13_pr_json_non_zero_or_unparseable(stdout, code):
    assert _pr(stdout, code)[0] == {"ok": False, "reason": "github-read-failed"}


def test_e13_repo_json_and_post_comment_failures():
    run = FakeRun({"gh api repos/o/r --jq .full_name": (1, "")})
    assert cb.repo_json("o/r", run=run, env={}) == {"ok": False, "reason": "github-read-failed"}
    run = FakeRun({"gh api -X POST repos/o/r/issues/5/comments -F body=@/b": (1, "")})
    assert cb.post_comment("o/r", 5, "/b", run=run, env={}) == {
        "ok": False, "reason": "github-write-failed", "url": None}
    assert len(run.calls) == 1


def test_repo_json_returns_the_stripped_name():
    run = FakeRun({"gh api repos/o/r --jq .full_name": (0, "Owner/Repo\n")})
    assert cb.repo_json("o/r", run=run, env={}) == {"ok": True, "nameWithOwner": "Owner/Repo"}


def test_post_comment_with_unparseable_success_output_has_no_url():
    run = FakeRun({"gh api -X POST repos/o/r/issues/5/comments -F body=@/b": (0, "ok")})
    assert cb.post_comment("o/r", 5, "/b", run=run, env={}) == {"ok": True, "reason": None,
                                                                  "url": None}


@pytest.mark.parametrize("raised", [OSError("no gh"), subprocess.TimeoutExpired("gh", 1)])
def test_e15_a_raising_run_in_the_github_functions_returns_the_failure_token(raised):
    run = FakeRun({PULLS_ENDPOINT: raised, "gh api repos/o/r --jq .full_name": raised,
                   "gh api -X POST repos/o/r/issues/5/comments -F body=@/b": raised})
    assert cb.pr_json("o/r", "build/1747-x", run=run, env={})["reason"] == "github-read-failed"
    assert cb.repo_json("o/r", run=run, env={})["reason"] == "github-read-failed"
    assert cb.post_comment("o/r", 5, "/b", run=run, env={})["reason"] == "github-write-failed"


def test_e15_a_raising_run_in_intake_and_history_never_raises():
    run = FakeRun({SHALLOW_KEY: OSError("no git")})
    _assert_refusal(_intake(run), "history-unfetchable")


def test_github_functions_refuse_a_malformed_repo_without_running_gh():
    run = FakeRun()
    assert cb.pr_json("not a repo", "b", run=run, env={})["reason"] == "github-read-failed"
    assert cb.repo_json("../x", run=run, env={})["reason"] == "github-read-failed"
    assert cb.post_comment("o/r", "5; rm", "/b", run=run, env={})["reason"] == "github-write-failed"
    assert run.calls == []


def test_pr_json_cli_writes_out_only_when_ok(tmp_path, capsys, monkeypatch):
    out = tmp_path / "pr.json"
    answers = {"gh api repos/o/r/pulls?head=o:b&state=open": (0, json.dumps([_pull()]))}
    fake = FakeRun(answers)
    monkeypatch.setattr(cb.subprocess, "run", fake)
    argv = ["pr-json", "--repo", "o/r", "--branch", "b", "--out", str(out)]
    assert cb.main(argv) == 0
    assert json.loads(out.read_text())["number"] == 7
    assert json.loads(capsys.readouterr().out)["ok"] is True
    out.unlink()
    answers["gh api repos/o/r/pulls?head=o:b&state=open"] = (0, "[]")
    assert cb.main(argv) == 1
    assert not out.exists()
    assert json.loads(capsys.readouterr().out)["reason"] == "pr-not-found"


# ---------------------------------------------------------------- board texts


def test_board_texts_are_byte_exact():
    taken = _intake(FakeRun())["comment"]
    assert taken.split("\n")[0] == (
        "Builder intake (cloud build). Plugin 9.8.7. Commits from this build carry the cloud's "
        "own author name; the PR will be under the owner's name.")
    assert taken.split("\n")[1:] == ["", "Started from %s, the base commit the launch named." % SHA]
    note = cb.note_text("  Which branch?\n")["comment"]
    assert note == ("Builder note for the advisor (cloud build).\n\nWhich branch?\n\n"
                    "I'm waiting for your answer.")
    assert cb.review_lapsed_text() == {"comment": (
        "Parked: the review did not run.\n\n"
        "The reviewer pass lapsed during this build, so no independent review happened. The "
        "work is pushed and this PR is not ready. It needs a fresh pass, then a review.")}


def test_note_and_review_lapsed_cli(tmp_path, capsys):
    question = tmp_path / "q.txt"
    question.write_text("Which branch?\n", encoding="utf-8")
    assert cb.main(["note", "--question-file", str(question)]) == 0
    assert json.loads(capsys.readouterr().out) == cb.note_text("Which branch?")
    assert cb.main(["note", "--question-file", str(tmp_path / "missing")]) == 1
    capsys.readouterr()
    assert cb.main(["review-lapsed"]) == 0
    assert json.loads(capsys.readouterr().out) == cb.review_lapsed_text()


# ---------------------------------------------------------------- pass_state


def _b64u(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _jwt(exp):
    return ".".join([_b64u(b'{"alg":"none"}'), _b64u(json.dumps({"exp": exp}).encode()),
                     _b64u(b"sig")])


def test_pass_state_adds_the_cloud_flag(tmp_path):
    auth = tmp_path / ".codex" / "auth.json"
    auth.parent.mkdir()
    auth.write_text(json.dumps({"tokens": {"access_token": _jwt(NOW + 86400)}}))
    env = {"HOME": str(tmp_path)}
    assert cb.pass_state(env=env, now=NOW) == {"state": "valid", "passLapses": "2027-01-16",
                                               "cloud": False}
    env[cloud_pass.CLOUD_ENV] = "true"
    assert cb.pass_state(env=env, now=NOW)["cloud"] is True
    assert cb.pass_state(env={"HOME": str(tmp_path / "none")}, now=NOW) == {
        "state": "absent", "passLapses": None, "cloud": False}


def test_pass_state_cli(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    assert cb.main(["pass-state"]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "absent"


# ---------------------------------------------------------------- a detective launch: the intake note follows the charter

DETECTIVE_CMD = "/superheroes:detective"
ADOPT_BRANCH = "feature/adopted-1"
ADOPT_HEAD = "b" * 40
DETECTIVE_BUDGET = "until 18:00 local, no more than 3 hours of builder time"


def _detective_launch(**kwargs):
    return DETECTIVE_CMD + "\n\n" + _launch(**kwargs)


def _composed_detective_prompt():
    composed = launcher.compose_launch(
        ".", 1747, {"baseCommit": SHA, "charter": "detective", "budget": DETECTIVE_BUDGET},
        model="opus", place="cloud", cloud_environment=ENV_ID, session_name="issue-1747-probe")
    assert composed["ok"] is True, composed
    return composed


# E1 non-strings, E2 empty text, E3 leading blank lines, E4 spaces around the command, E5 the command not on the first non-blank line
@pytest.mark.parametrize("text, charter", [
    (DETECTIVE_CMD + "\n\nIssue: #1747\n", "detective"),
    ("\n\n \n" + DETECTIVE_CMD + "\nIssue: #1747\n", "detective"),
    (" " + DETECTIVE_CMD + " \t \nIssue: #1747\n", "detective"),
    ("/superheroes:workhorse\n\nIssue: #1747\n", "workhorse"),
    ("Issue: #1747\n" + DETECTIVE_CMD + "\n", "workhorse"),
    ("Issue: #1747, see " + DETECTIVE_CMD + " for the lane\n", "workhorse"),
    (DETECTIVE_CMD + " extra\n", "workhorse"),
    ("", "workhorse"),
    (" \t \n\n", "workhorse"),
    (None, "workhorse"),
    (7, "workhorse"),
    (b"/superheroes:detective", "workhorse"),
    ([DETECTIVE_CMD], "workhorse"),
])
def test_launch_charter_reads_the_first_non_blank_line(text, charter):
    assert cb.launch_charter(text) == charter


def test_launch_charter_reads_the_launchers_composed_prompts():
    assert cb.launch_charter(_composed_detective_prompt()["prompt"]) == "detective"
    workhorse = launcher.compose_launch(
        ".", 1747, {"baseCommit": SHA}, model="opus", place="cloud",
        cloud_environment=ENV_ID, session_name="issue-1747-probe")
    assert workhorse["ok"] is True, workhorse
    assert cb.launch_charter(workhorse["prompt"]) == "workhorse"


def test_a_detective_intake_succeeds_with_the_detective_note_and_the_same_git_calls():
    run = FakeRun()
    result = _intake(run, launch=_detective_launch())
    assert result == {"ok": True, "outcome": None, "reason": None, "startedFrom": SHA,
                      "comment": cb.DETECTIVE_INTAKE_TEXT.format(v=VERSION, sha=SHA),
                      "pluginVersion": VERSION, "branch": None}
    tails = [" ".join(a[3:]) for a in run.git_calls]
    assert tails == [SHALLOW_KEY, MAIN_FETCH_KEY, VERIFY_KEY, SHALLOW_KEY, _sha_key("fetch"),
                     _sha_key("cat"), _sha_key("checkout")]


def test_a_workhorse_launch_keeps_the_builders_note_byte_for_byte():
    # axis: only a launch whose first non-blank line is the detective command gets the detective note
    text = _launch()
    assert cb.launch_charter(text) == "workhorse"
    assert _intake(FakeRun(), launch=text)["comment"] == (
        "Builder intake (cloud build). Plugin %s. Commits from this build carry the cloud's own "
        "author name; the PR will be under the owner's name.\n\n"
        "Started from %s, the base commit the launch named." % (VERSION, SHA))
    later = _launch() + DETECTIVE_CMD + "\n"
    assert _intake(FakeRun(), launch=later)["comment"] == cb.INTAKE_TEXT.format(v=VERSION, sha=SHA)


def test_a_detective_version_mismatch_refuses_with_the_builders_refusal_and_no_git_call():
    run = FakeRun()
    result = _intake(run, launch=_detective_launch(version=OTHER_VERSION))
    _assert_refusal(result, "plugin-version-mismatch")
    assert run.git_calls == []
    assert result["comment"] == cb._refusal_comment(
        "plugin-version-mismatch", running=VERSION, launched=OTHER_VERSION)


@pytest.mark.parametrize("which,reason", [("fetch", "base-commit-unfetchable"),
                                          ("checkout", "base-checkout-failed")])
def test_a_detective_refusal_after_the_checks_is_the_builders_refusal(which, reason):
    # E6: the refusal tokens and wording do not depend on the launch's charter
    detective = _intake(FakeRun({_sha_key(which): (1, "")}), launch=_detective_launch())
    builder = _intake(FakeRun({_sha_key(which): (1, "")}))
    _assert_refusal(detective, reason)
    assert detective == builder


def test_a_detective_adopt_intake_returns_the_detective_adopt_note():
    tracking = "refs/remotes/origin/%s" % ADOPT_BRANCH
    run = FakeRun({"rev-parse --verify %s" % tracking: (0, ADOPT_HEAD + "\n")})
    launch = _detective_launch(extra="Adopts branch: %s at %s\n" % (ADOPT_BRANCH, ADOPT_HEAD))
    result = _intake(run, launch=launch)
    assert result == {"ok": True, "outcome": None, "reason": None, "startedFrom": ADOPT_HEAD,
                      "branch": ADOPT_BRANCH, "pluginVersion": VERSION,
                      "comment": cb.DETECTIVE_INTAKE_ADOPT_TEXT.format(
                          v=VERSION, sha=ADOPT_HEAD, branch=ADOPT_BRANCH)}
    assert [" ".join(a[3:]) for a in run.git_calls][-3:] == [
        "merge-base --is-ancestor %s %s" % (SHA, ADOPT_HEAD),
        "checkout -B %s %s" % (ADOPT_BRANCH, ADOPT_HEAD),
        "branch --set-upstream-to=origin/%s %s" % (ADOPT_BRANCH, ADOPT_BRANCH)]
    # the same launch under the builder's first line keeps the builder's adopt note
    builder = _intake(FakeRun({"rev-parse --verify %s" % tracking: (0, ADOPT_HEAD + "\n")}),
                      launch=launch.replace(DETECTIVE_CMD, "/superheroes:workhorse", 1))
    assert builder["comment"] == cb.INTAKE_ADOPT_TEXT.format(
        v=VERSION, sha=ADOPT_HEAD, branch=ADOPT_BRANCH)


def test_e9_the_detective_intake_notes_open_with_no_header_the_wave_watch_reads():
    headers = list(cb.TERMINAL_HEADERS.values()) + [
        cb.NOTE_HEADER, cb.PROGRESS_HEADER, cb.REFUSAL_HEADER, cb.HANDOVER_HEADER]
    for text in (cb.DETECTIVE_INTAKE_TEXT, cb.DETECTIVE_INTAKE_ADOPT_TEXT):
        body = text.format(v=VERSION, sha=SHA, branch=ADOPT_BRANCH)
        assert not any(body.startswith(header) for header in headers)
        assert cb.terminal_kind(body) is None
        assert cb.parse_progress(body) is None


def test_the_launchers_detective_cloud_prompt_passes_intake():
    composed = _composed_detective_prompt()
    parsed = cb.parse_launch(composed["prompt"])
    assert parsed == {"advisorVersion": composed["pluginVersion"],
                      "environment": ENV_ID, "baseCommit": SHA, "adoptsBranch": None, "adoptsHead": None}
    assert cb.launch_charter(composed["prompt"]) == "detective"
