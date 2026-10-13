"""Tests for a successor launch that adopts a pushed branch: the premise key, the prompt line on
both prompts, the cloud builder's reading of the line, and its intake on that branch.

Nothing here touches the network. The intake tests build throwaway repositories with a bare remote
under tmp_path; the failure-edge tests record git calls with a fake `run`.
"""
import json
import os
import subprocess

import pytest

import cloud_builder as cb
import cloud_pass
from test_cloud_builder import ENV_ID, SHA, VERSION, FakeRun, _git, _launch, _session
from test_launcher import L, _init_repo, _valid_premise

BRANCH = "feature/adopted-1"
HEAD = "b" * 40


@pytest.fixture(autouse=True)
def _no_user_git_config(tmp_path, monkeypatch):
    """The throwaway repositories commit without the user's global git config (a signing setup
    would otherwise reach for a signer the test has no business calling)."""
    empty = tmp_path / "empty-gitconfig"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))


def _cloud_prompt(premise):
    composed = L.compose_launch(
        ".", 1747, premise, model="opus", place="cloud", cloud_environment=ENV_ID,
        session_name="issue-1747-probe")
    assert composed["ok"] is True, composed
    return composed["prompt"]


def _local_prompt(repo, premise):
    composed = L.compose_launch(repo, 656, premise)
    assert composed["ok"] is True, composed
    return composed["prompt"]


# ---------------------------------------------------------------- compose


def test_cloud_prompt_names_the_branch_right_after_the_base_commit():
    prompt = _cloud_prompt({"baseCommit": SHA, "adoptsBranch": BRANCH, "adoptsHead": HEAD})
    assert "Base commit: %s\nAdopts branch: %s at %s\n\n" % (SHA, BRANCH, HEAD) in prompt


def test_local_prompt_names_branch_and_base_between_the_issue_and_the_rulings(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo, adoptsBranch=BRANCH, adoptsHead=HEAD)
    prompt = _local_prompt(repo, premise)
    head = "%s\n\nIssue: #656\n\nAdopts branch: %s at %s\nBase commit: %s\n\n" % (
        L._WORKHORSE_CMD, BRANCH, HEAD, premise["baseCommit"])
    assert prompt.startswith(head)
    assert prompt[len(head):].strip() != ""


def test_prompts_without_the_key_are_byte_identical_to_the_prior_prompts(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo)
    assert "adoptsBranch" not in premise
    local = _local_prompt(repo, premise)
    assert local == "%s\n\nIssue: #656\n\n%s" % (
        L._WORKHORSE_CMD, L.compose_launch(repo, 656, premise)["doctrine"]["rulingsBlock"])
    assert "Adopts branch" not in local
    cloud = _cloud_prompt({"baseCommit": SHA})
    assert "Adopts branch" not in cloud
    assert "Base commit: %s\n\n" % SHA in cloud
    # the same premise with the key adds exactly the one cloud line and nothing else
    adopted = _cloud_prompt({"baseCommit": SHA, "adoptsBranch": BRANCH, "adoptsHead": HEAD})
    assert adopted.replace("\nAdopts branch: %s at %s" % (BRANCH, HEAD), "", 1) == cloud


def test_compose_refuses_a_malformed_branch_and_composes_nothing(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    result = L.compose_launch(repo, 656, _valid_premise(repo, adoptsBranch="a..b", adoptsHead=HEAD))
    assert result["ok"] is False
    assert result["reason"] == "premise-adopts-branch-invalid"
    assert "prompt" not in result


# ---------------------------------------------------------------- validate_premise


def test_validate_premise_accepts_a_valid_branch_and_stamps_it_untouched(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    result = L.validate_premise(_valid_premise(repo, adoptsBranch=BRANCH, adoptsHead=HEAD), repo)
    assert result["ok"] is True, result
    assert result["premise"]["adoptsBranch"] == BRANCH
    assert result["premise"]["adoptsHead"] == HEAD


@pytest.mark.parametrize("bad", [
    "-x", "a..b", "a//b", "a/", "a.lock", "a.", "", "a" * 201, " a", "a b", "a\n", None, 7, True,
    ["a"], {"a": 1},
])
def test_validate_premise_refuses_a_malformed_branch(tmp_path, bad):
    repo = _init_repo(tmp_path / "repo")
    result = L.validate_premise(_valid_premise(repo, adoptsBranch=bad, adoptsHead=HEAD), repo)
    assert result["ok"] is False
    assert result["reason"] == "premise-adopts-branch-invalid"


@pytest.mark.parametrize("good", ["a", "a" * 200, "feature/x-1.2_3", "0abc", "a.lockx"])
def test_validate_premise_accepts_the_edges_of_the_shape(tmp_path, good):
    repo = _init_repo(tmp_path / "repo")
    assert L.validate_premise(_valid_premise(repo, adoptsBranch=good, adoptsHead=HEAD), repo)["ok"] is True


@pytest.mark.parametrize("bad", [
    "b" * 39, "b" * 41, "B" * 40, "g" * 40, HEAD + "\n", "", None, 7, True, [HEAD],
])
def test_validate_premise_refuses_a_malformed_head(tmp_path, bad):
    repo = _init_repo(tmp_path / "repo")
    result = L.validate_premise(_valid_premise(repo, adoptsBranch=BRANCH, adoptsHead=bad), repo)
    assert result["ok"] is False and result["reason"] == "premise-adopts-head-invalid"


def test_validate_premise_refuses_a_branch_without_a_head_and_a_head_without_a_branch(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    for extra in ({"adoptsBranch": BRANCH}, {"adoptsHead": HEAD}):
        result = L.validate_premise(_valid_premise(repo, **extra), repo)
        assert result["ok"] is False and result["reason"] == "premise-adopts-head-invalid"
        composed = L.compose_launch(repo, 656, _valid_premise(repo, **extra))
        assert composed["ok"] is False and composed["reason"] == "premise-adopts-head-invalid"


def test_validate_premise_without_the_key_is_unchanged(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    result = L.validate_premise(_valid_premise(repo), repo)
    assert result["ok"] is True
    assert "adoptsBranch" not in result["premise"]


# ---------------------------------------------------------------- parse_launch


def _adopt_launch(*values, head=HEAD):
    return _launch(extra="".join(
        "Adopts branch: %s\n" % (v if " at " in v else "%s at %s" % (v, head)) for v in values))


def test_parse_launch_adopt_line_absent_is_none_and_not_invalid():
    parsed = cb.parse_launch(_launch())
    assert parsed["adoptsBranch"] is None
    assert "adoptsBranchInvalid" not in parsed


def test_parse_launch_reads_the_adopted_branch():
    parsed = cb.parse_launch(_adopt_launch(BRANCH))
    assert parsed["adoptsBranch"] == BRANCH and parsed["adoptsHead"] == HEAD
    assert "adoptsBranchInvalid" not in parsed


def test_parse_launch_the_same_value_stated_twice_is_that_value():
    parsed = cb.parse_launch(_adopt_launch(BRANCH, BRANCH))
    assert parsed["adoptsBranch"] == BRANCH
    assert "adoptsBranchInvalid" not in parsed


@pytest.mark.parametrize("bad", ["-x", "a..b", "a//b", "a/", "a.lock", "a b", "a" * 201])
def test_parse_launch_a_malformed_branch_is_invalid(bad):
    parsed = cb.parse_launch(_adopt_launch(bad))
    assert parsed["adoptsBranch"] is None
    assert parsed["adoptsBranchInvalid"] is True


@pytest.mark.parametrize("text", [
    "Adopts branch:", "Adopts branch: ", "Adopts branch:x",
    "Adopts branch: %s" % BRANCH,
    "Adopts branch: %s at %s" % (BRANCH, "b" * 39),
    "Adopts branch: %s at %s" % (BRANCH, "B" * 40),
    "Adopts branch: %s at %s extra" % (BRANCH, HEAD),
    "Adopts branch: %s %s" % (BRANCH, HEAD),
])
def test_parse_launch_a_present_but_empty_or_unspaced_line_is_invalid(text):
    parsed = cb.parse_launch(_launch(extra=text + "\n"))
    assert parsed["adoptsBranchInvalid"] is True


def test_parse_launch_two_different_values_are_invalid():
    parsed = cb.parse_launch(_adopt_launch(BRANCH, "feature/other"))
    assert parsed["adoptsBranch"] is None
    assert parsed["adoptsBranchInvalid"] is True


def test_the_launchers_adopt_prompt_parses_back():
    parsed = cb.parse_launch(
        _cloud_prompt({"baseCommit": SHA, "adoptsBranch": BRANCH, "adoptsHead": HEAD}))
    assert parsed["adoptsBranch"] == BRANCH and parsed["baseCommit"] == SHA
    assert parsed["adoptsHead"] == HEAD
    assert "adoptsBranchInvalid" not in parsed


# ---------------------------------------------------------------- intake, real git


def _commit(work, name):
    (work / name).write_text(name, encoding="utf-8")
    _git(work, "add", name)
    _git(work, "-c", "user.name=t", "-c", "user.email=t@example.invalid",
         "-c", "commit.gpgsign=false", "commit", "-m", name)
    return _git(work, "rev-parse", "HEAD")


def _world(tmp_path):
    """A work repo with `main` and a pushed `BRANCH` (one commit past main), a bare remote, and
    a fresh clone. Returns (work, origin, clone, main_sha, tip_sha)."""
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-b", "main")
    main_sha = _commit(work, "one")
    origin = tmp_path / "origin.git"
    _git(tmp_path, "clone", "--bare", str(work), str(origin))
    _git(work, "remote", "add", "origin", str(origin))
    _git(work, "checkout", "-b", BRANCH)
    tip = _commit(work, "two")
    _git(work, "push", "origin", BRANCH)
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "file://%s" % origin, str(clone))
    return work, origin, clone, main_sha, tip


def _real_intake(clone, base, head, *values):
    env = dict(os.environ)
    env[cloud_pass.ENVIRONMENT_ENV] = ENV_ID
    return cb.intake(str(clone), _launch(base=base, extra="".join(
        "Adopts branch: %s at %s\n" % (v, head) for v in values)), env=env,
        running_version=VERSION)


def _env_intake(clone, base):
    env = dict(os.environ)
    env[cloud_pass.ENVIRONMENT_ENV] = ENV_ID
    return cb.intake(str(clone), _launch(base=base), env=env, running_version=VERSION)


def _head_is_detached(clone):
    return subprocess.run(["git", "-C", str(clone), "symbolic-ref", "-q", "HEAD"],
                          capture_output=True).returncode != 0


def test_intake_starts_on_the_adopted_branch_at_its_pushed_head(tmp_path):
    _, _, clone, main_sha, tip = _world(tmp_path)
    result = _real_intake(clone, main_sha, tip, BRANCH)
    assert result == {"ok": True, "outcome": None, "reason": None, "startedFrom": tip,
                      "branch": BRANCH, "pluginVersion": VERSION,
                      "comment": cb.INTAKE_ADOPT_TEXT.format(v=VERSION, sha=tip, branch=BRANCH)}
    assert _git(clone, "symbolic-ref", "--short", "HEAD") == BRANCH
    assert _git(clone, "rev-parse", "HEAD") == tip
    assert _git(clone, "rev-parse", "--abbrev-ref", "%s@{upstream}" % BRANCH) == "origin/" + BRANCH


def test_intake_refuses_a_branch_that_moved_past_the_base(tmp_path):
    work, _, clone, main_sha, tip = _world(tmp_path)
    _commit(work, "three")
    _git(work, "push", "origin", BRANCH)
    before = _git(clone, "rev-parse", "HEAD")
    result = _real_intake(clone, main_sha, tip, BRANCH)
    assert result["ok"] is False and result["reason"] == "adopted-branch-moved"
    assert result["startedFrom"] is None
    assert "adopted-branch-moved" in result["comment"]
    assert _git(clone, "rev-parse", "HEAD") == before
    assert _git(clone, "symbolic-ref", "--short", "HEAD") == "main"


def test_intake_continues_a_stack_layer_whose_base_is_the_layer_below(tmp_path):
    """The base commit is the layer below's head; the adopted head is a different, descendant sha."""
    work, _, clone, main_sha, tip = _world(tmp_path)
    assert tip != main_sha
    result = _real_intake(clone, main_sha, tip, BRANCH)
    assert result["ok"] is True and result["startedFrom"] == tip and result["branch"] == BRANCH
    assert _git(clone, "rev-parse", "HEAD") == tip


def test_intake_refuses_an_adopted_head_that_is_not_a_descendant_of_the_base(tmp_path):
    work, _, clone, main_sha, tip = _world(tmp_path)
    _git(work, "checkout", "-b", "side", main_sha)
    side = _commit(work, "side")
    _git(work, "push", "origin", "side")
    # the base is the branch tip; the adopted branch is `side`, which does not contain it
    result = _real_intake(clone, tip, side, "side")
    assert result["ok"] is False and result["reason"] == "adopted-head-not-on-base"
    assert _git(clone, "symbolic-ref", "--short", "HEAD") == "main"


def test_intake_adopts_in_a_single_branch_shallow_clone(tmp_path):
    work, origin, _, main_sha, tip = _world(tmp_path)
    clone = tmp_path / "single"
    _git(tmp_path, "clone", "--depth", "1", "--single-branch", "--branch", "main",
         "file://%s" % origin, str(clone))
    assert _git(clone, "config", "--get-all", "remote.origin.fetch") == (
        "+refs/heads/main:refs/remotes/origin/main")
    result = _real_intake(clone, main_sha, tip, BRANCH)
    assert result["ok"] is True, result
    assert _git(clone, "rev-parse", "HEAD") == tip
    assert _git(clone, "rev-parse", "--abbrev-ref", "%s@{upstream}" % BRANCH) == "origin/" + BRANCH


def test_intake_refuses_a_branch_absent_from_the_remote(tmp_path):
    _, _, clone, main_sha, tip = _world(tmp_path)
    result = _real_intake(clone, main_sha, tip, "feature/gone")
    assert result["ok"] is False and result["reason"] == "adopted-branch-unfetchable"
    assert _git(clone, "symbolic-ref", "--short", "HEAD") == "main"


def test_intake_without_the_line_checks_out_detached_as_before(tmp_path):
    _, _, clone, main_sha, _ = _world(tmp_path)
    result = _env_intake(clone, main_sha)
    assert result == {"ok": True, "outcome": None, "reason": None, "startedFrom": main_sha,
                      "branch": None, "pluginVersion": VERSION,
                      "comment": cb.INTAKE_TEXT.format(v=VERSION, sha=main_sha)}
    assert _head_is_detached(clone)
    assert _git(clone, "rev-parse", "HEAD") == main_sha


def test_intake_with_a_malformed_line_refuses_and_checks_nothing_out(tmp_path):
    _, _, clone, main_sha, tip = _world(tmp_path)
    result = _real_intake(clone, main_sha, tip, "a..b")
    assert result["ok"] is False and result["reason"] == "adopts-branch-invalid"
    assert _git(clone, "symbolic-ref", "--short", "HEAD") == "main"


def test_intake_with_two_different_lines_refuses_and_checks_nothing_out(tmp_path):
    _, _, clone, main_sha, tip = _world(tmp_path)
    result = _real_intake(clone, main_sha, tip, BRANCH, "feature/other")
    assert result["ok"] is False and result["reason"] == "adopts-branch-invalid"
    assert _git(clone, "symbolic-ref", "--short", "HEAD") == "main"


# ---------------------------------------------------------------- intake, recorded git


def _adopt_keys():
    tracking = "refs/remotes/origin/%s" % BRANCH
    return {"map": "remote set-branches --add origin %s" % BRANCH,
            "ancestor": "merge-base --is-ancestor %s %s" % (SHA, HEAD),
            "fetch": "fetch origin +refs/heads/%s:%s" % (BRANCH, tracking),
            "verify": "rev-parse --verify %s" % tracking,
            "checkout": "checkout -B %s %s" % (BRANCH, HEAD),
            "upstream": "branch --set-upstream-to=origin/%s %s" % (BRANCH, BRANCH)}


def _recorded(answers=None, launch=None, version=VERSION, env=None):
    keys = _adopt_keys()
    base = {keys["verify"]: (0, HEAD + "\n")}
    base.update(answers or {})
    run = FakeRun(base)
    result = cb.intake("/repo", launch if launch is not None else _adopt_launch(BRANCH),
                       env=_session() if env is None else env, run=run, running_version=version)
    return run, result


def test_recorded_adopt_runs_the_base_checks_then_the_branch_steps_and_no_detach():
    run, result = _recorded()
    assert result["ok"] is True and result["branch"] == BRANCH
    keys = _adopt_keys()
    tails = [" ".join(a[3:]) for a in run.git_calls]
    assert tails[-8:] == [
        "fetch origin %s" % SHA, "cat-file -e %s^{commit}" % SHA, keys["map"], keys["fetch"],
        keys["verify"], keys["ancestor"], keys["checkout"], keys["upstream"]]
    assert not any("--detach" in t for t in tails)


@pytest.mark.parametrize("step,reason", [
    ("checkout", "base-checkout-failed"),
    ("upstream", "adopted-branch-upstream-failed"),
    ("fetch", "adopted-branch-unfetchable"),
    ("map", "adopted-branch-unfetchable"),
    ("ancestor", "adopted-head-not-on-base"),
])
def test_recorded_adopt_step_failures_are_refusals(step, reason):
    _, result = _recorded({_adopt_keys()[step]: (1, "")})
    assert result["ok"] is False and result["reason"] == reason
    assert result["startedFrom"] is None and "branch" not in result


def test_recorded_a_tip_other_than_the_adopted_head_is_a_moved_refusal():
    _, result = _recorded({_adopt_keys()["verify"]: (0, SHA + "\n")})
    assert result["reason"] == "adopted-branch-moved"


def test_recorded_unreadable_remote_tip_is_a_moved_refusal():
    _, result = _recorded({_adopt_keys()["verify"]: (1, "")})
    assert result["reason"] == "adopted-branch-moved"


def test_recorded_a_malformed_line_runs_no_checkout_step():
    run, result = _recorded(launch=_adopt_launch("a..b"))
    assert result["reason"] == "adopts-branch-invalid"
    tails = [" ".join(a[3:]) for a in run.git_calls]
    assert not any(t.startswith(("checkout", "branch")) for t in tails)


def test_recorded_the_version_and_environment_checks_still_run_first():
    run, result = _recorded(version="9.8.6")
    assert result["reason"] == "plugin-version-mismatch"
    assert run.git_calls == []
    run, result = _recorded(env={cloud_pass.ENVIRONMENT_ENV: "env_99ZZZ"})
    assert result["reason"] == "cloud-environment-mismatch"
    assert run.git_calls == []


def test_recorded_a_malformed_line_does_not_bypass_the_version_check():
    run, result = _recorded(launch=_adopt_launch("a..b"), version="9.8.6")
    assert result["reason"] == "plugin-version-mismatch"
    assert run.git_calls == []


# ---------------------------------------------------------------- handover


def test_handover_text_is_the_contract_text():
    assert cb.HANDOVER_HEADER == "Builder handover (cloud build)."
    assert cb.handover_text(SHA) == (
        "Builder handover (cloud build).\n\n"
        "I pushed my work and stopped working on this issue. My pushed head is " + SHA + ".")


@pytest.mark.parametrize("bad", ["a" * 39, "a" * 41, "A" * 40, "g" * 40, SHA + "\n", "", None, 7])
def test_handover_text_refuses_a_sha_that_is_not_40_lowercase_hex(bad):
    assert cb.handover_text(bad) is None


def test_handover_cli_both_ways(capsys):
    assert cb.main(["handover", "--head", SHA]) == 0
    assert json.loads(capsys.readouterr().out) == {"ok": True, "comment": cb.handover_text(SHA)}
    assert cb.main(["handover", "--head", "nope"]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "reason": "head-invalid"}
