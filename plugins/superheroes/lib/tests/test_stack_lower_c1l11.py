"""C1-L11 (WO-C): a stacked layer is reviewed on its lower layer's current head.

On every `next`, `submit` and `advance` of a stacked session (before anything folds or emits) the lower
branch's remote head equals the session's pinned base commit, and that commit is in HEAD's history;
otherwise the call refuses and changes nothing but a journal line.

Real throwaway repos: a bare "origin", a clone with a `lower` branch and an `upper` branch on it, and a
`meta.json` written as the review-code Setup writes it. The during-the-session cases drive the driver's
CLI (`RD.main`) the way `test_prior_comments_mode.py` does.

Bite-proof record: c1l11_wo_c_stack_lower
"""
import json
import os
import re
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
_PLUGIN = os.path.dirname(_LIB)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import review_base_guard as G  # noqa: E402
import round_driver as RD  # noqa: E402

_SKILL = os.path.join(_PLUGIN, "skills", "review-code", "SKILL.md")
_NATIVE_STACKS = os.path.join(_PLUGIN, "rubric", "native-stacks.md")
_WORKHORSE = os.path.join(_PLUGIN, "skills", "workhorse", "SKILL.md")
_PR_URL = "https://github.com/acme/widget/pull/7"


@pytest.fixture(autouse=True)
def _hermetic_git(monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for key, val in (("AUTHOR", "t"), ("COMMITTER", "t")):
        monkeypatch.setenv("GIT_%s_NAME" % key, val)
        monkeypatch.setenv("GIT_%s_EMAIL" % key, "t@t")
    # The PR-mode fork check compares the PR url to the origin url; a local bare repo has no host.
    monkeypatch.setattr(RD.review_base_guard, "origin_repo", lambda *a, **k: "github.com/acme/widget")


def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


def _commit(cwd, name, text="x\n"):
    with open(os.path.join(str(cwd), name), "w", encoding="utf-8") as fh:
        fh.write(text)
    _git(cwd, "add", name)
    _git(cwd, "commit", "-q", "-m", "add " + name)
    return _git(cwd, "rev-parse", "HEAD")


class Stack:
    """origin (bare) + work (clone on `upper`, which is built on `lower`)."""

    def __init__(self, tmp_path):
        self.tmp = tmp_path
        self.origin = str(tmp_path / "origin.git")
        self.repo = str(tmp_path / "work")
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", self.origin], check=True)
        subprocess.run(["git", "init", "-q", "-b", "main", self.repo], check=True)
        _git(self.repo, "remote", "add", "origin", self.origin)
        _commit(self.repo, "base.txt")
        _git(self.repo, "push", "-q", "origin", "main")
        _git(self.repo, "checkout", "-q", "-b", "lower")
        self.pin = _commit(self.repo, "lower1.txt")
        _git(self.repo, "push", "-q", "origin", "lower")
        _git(self.repo, "checkout", "-q", "-b", "upper")
        _commit(self.repo, "upper1.txt")

    def push_lower(self):
        """Another clone pushes a new commit to `lower` on origin; returns the new head."""
        other = str(self.tmp / "other")
        if not os.path.isdir(other):
            subprocess.run(["git", "clone", "-q", self.origin, other], check=True)
        _git(other, "checkout", "-q", "lower")
        sha = _commit(other, "lower-%d.txt" % len(os.listdir(other)))
        _git(other, "push", "-q", "origin", "lower")
        return sha

    def session(self, pin=None, **meta_over):
        sd = str(self.tmp / "session")
        os.makedirs(sd, exist_ok=True)
        meta = {"mode": "pr", "baseBranch": "lower", "baseRef": pin or self.pin,
                "baseFetch": "fetched", "repoRoot": os.path.realpath(self.repo), "stackLower": True}
        meta.update(meta_over)
        meta = {k: v for k, v in meta.items() if v is not None}
        with open(os.path.join(sd, "meta.json"), "w", encoding="utf-8") as fh:
            json.dump(meta, fh)
        with open(os.path.join(sd, "pr.json"), "w", encoding="utf-8") as fh:
            json.dump({"url": _PR_URL}, fh)
        return sd

    def round_diff(self, sd, pin=None):
        path = os.path.join(sd, "round-1", "diff.txt")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(_git(self.repo, "diff", "%s...HEAD" % (pin or self.pin)) + "\n")
        return path


@pytest.fixture
def stack(tmp_path):
    return Stack(tmp_path)


def _no_call(*_a, **_k):
    raise AssertionError("a git read was made for a session that is not stacked")


# --- the lower layer is current ------------------------------------------------------------------

def test_current_lower_is_ok(stack):
    # axis: a layer holding the lower layer's current head passes
    res = G.check_stack_lower(stack.session(), stack.repo)
    assert res["ok"] is True and res["stacked"] is True
    assert res["baseRef"] == stack.pin


@pytest.mark.parametrize("meta_over", [{"stackLower": None}, {"stackLower": False}])
def test_not_stacked_session_makes_no_git_call(stack, meta_over):
    # axis: stackLower absent or false means no check, and no read of the remote
    sd = stack.session(**meta_over)
    res = G.check_stack_lower(sd, stack.repo, run=_no_call, ls_remote=_no_call)
    assert res == {"ok": True, "stacked": False}


# --- before the session --------------------------------------------------------------------------

def test_moved_lower_before_the_session_refuses_moved(stack):
    # axis: remote head != pin refuses stack-lower-moved and names both shas
    new_head = stack.push_lower()
    res = G.check_stack_lower(stack.session(), stack.repo)
    assert res["ok"] is False and res["reason"] == "stack-lower-moved" == G.REASON_STACK_LOWER_MOVED
    assert new_head in res["detail"] and stack.pin in res["detail"]
    assert "--no-ff" in res["detail"] and "abandoned" in res["detail"]


def test_pin_the_layer_does_not_contain_refuses_ahead_until_merged(stack):
    # axis: pin == remote head but not in HEAD's history refuses stack-lower-ahead; a --no-ff merge clears it
    new_head = stack.push_lower()
    _git(stack.repo, "fetch", "-q", "origin", "lower")
    sd = stack.session(pin=new_head)
    res = G.check_stack_lower(sd, stack.repo)
    assert res["ok"] is False and res["reason"] == "stack-lower-ahead" == G.REASON_STACK_LOWER_AHEAD
    assert "current head" in res["detail"]
    _git(stack.repo, "merge", "-q", "--no-ff", "-m", "bring current", new_head)
    res = G.check_stack_lower(sd, stack.repo)
    assert res["ok"] is True and res["stacked"] is True


# --- the remote head cannot be read --------------------------------------------------------------

def test_unreadable_remote_refuses_even_with_a_stale_pin_that_is_an_ancestor(stack):
    # axis: an unreadable remote head refuses; a cached pin in HEAD's history is not a substitute
    sd = stack.session()
    assert _git(stack.repo, "merge-base", "--is-ancestor", stack.pin, "HEAD") == ""
    for answer in (None, "", "abc123", "z" * 40):
        res = G.check_stack_lower(sd, stack.repo, ls_remote=lambda _r, _b, a=answer: a)
        assert res["ok"] is False and res["reason"] == "stack-lower-unreadable" == G.REASON_STACK_LOWER_UNREADABLE
        assert "origin" in res["detail"] and "same command again" in res["detail"]


def test_origin_pointing_at_a_missing_path_refuses_unreadable(stack, tmp_path):
    # axis: a real ls-remote failure (origin unreachable) refuses stack-lower-unreadable
    sd = stack.session()
    _git(stack.repo, "remote", "set-url", "origin", str(tmp_path / "gone.git"))
    res = G.check_stack_lower(sd, stack.repo)
    assert res["ok"] is False and res["reason"] == "stack-lower-unreadable"


def test_missing_lower_branch_on_origin_refuses_unreadable(stack):
    # axis: no such branch on the remote is unreadable, not a pass
    sd = stack.session(baseBranch="no-such-branch")
    res = G.check_stack_lower(sd, stack.repo)
    assert res["ok"] is False and res["reason"] == "stack-lower-unreadable"


@pytest.mark.parametrize("bad", ["", "bad..name", "has space", "-x", 7])
def test_invalid_lower_branch_name_refuses_unreadable(stack, bad):
    # axis: meta.baseBranch must pass `git check-ref-format --branch`
    sd = stack.session(baseBranch=bad)
    res = G.check_stack_lower(sd, stack.repo, ls_remote=lambda _r, _b: stack.pin)
    assert res["ok"] is False and res["reason"] == "stack-lower-unreadable"


def test_unreadable_meta_and_non_boolean_flag_refuse_unreadable(stack, tmp_path):
    # axis: a meta read that fails, or a stackLower that is neither true nor false, fails closed
    empty = str(tmp_path / "no-meta")
    os.makedirs(empty)
    res = G.check_stack_lower(empty, stack.repo)
    assert res["ok"] is False and res["reason"] == "stack-lower-unreadable"
    res = G.check_stack_lower(stack.session(stackLower="true"), stack.repo)
    assert res["ok"] is False and res["reason"] == "stack-lower-unreadable"


def test_refusal_order_is_unreadable_then_moved_then_ahead(stack):
    # axis: the three refusals fire in the order the invariant states
    sd = stack.session()
    other = "f" * 40
    assert G.check_stack_lower(sd, stack.repo, ls_remote=lambda _r, _b: None)["reason"] == "stack-lower-unreadable"
    assert G.check_stack_lower(sd, stack.repo, ls_remote=lambda _r, _b: other)["reason"] == "stack-lower-moved"
    _git(stack.repo, "checkout", "-q", "-b", "elsewhere", "main")  # HEAD without the pin
    assert G.check_stack_lower(sd, stack.repo, ls_remote=lambda _r, _b: stack.pin)["reason"] == "stack-lower-ahead"


# --- during the session, through the driver's CLI ------------------------------------------------

def _run(argv, capsys):
    rc = RD.main(argv)
    out = capsys.readouterr().out.strip()
    return rc, (json.loads(out.splitlines()[-1]) if out else None)


def _started(stack, capsys):
    sd = stack.session()
    rc, _ = _run(["next", "--session-dir", sd, "--repo-root", stack.repo,
                  "--diff-path", stack.round_diff(sd)], capsys)
    assert rc == 0
    assert os.path.isfile(os.path.join(sd, RD.STATE_FILE))
    return sd


def _refusals(sd, reason):
    return [e for e in RD.read_journal(sd)
            if e.get("outcome") == "refused-base-guard" and e.get("reason") == reason]


def _read(path):
    with open(path, "rb") as fh:
        return fh.read()


def test_cli_session_on_a_current_lower_is_not_refused(stack, capsys):
    # axis: the guard does not refuse a session whose lower layer has not moved
    sd = _started(stack, capsys)
    rc, _ = _run(["next", "--session-dir", sd, "--repo-root", stack.repo], capsys)
    assert rc == 0
    assert _refusals(sd, "stack-lower-moved") == []


def test_cli_next_refuses_when_lower_moves_during_the_session(stack, capsys):
    # axis: next on a started session refuses stack-lower-moved and changes nothing but the journal
    sd = _started(stack, capsys)
    state_path = os.path.join(sd, RD.STATE_FILE)
    before = _read(state_path)
    stack.push_lower()
    rc, out = _run(["next", "--session-dir", sd, "--repo-root", stack.repo], capsys)
    assert rc == 1 and out["ok"] is False and out["reason"] == "stack-lower-moved"
    assert _read(state_path) == before
    assert len(_refusals(sd, "stack-lower-moved")) == 1


def test_cli_submit_refuses_when_lower_moves_during_the_session(stack, capsys, tmp_path):
    # axis: submit on a started session refuses stack-lower-moved before it reads the artifact or folds
    sd = _started(stack, capsys)
    state_path = os.path.join(sd, RD.STATE_FILE)
    before = _read(state_path)
    stack.push_lower()
    artifact = str(tmp_path / "artifact.json")
    with open(artifact, "w", encoding="utf-8") as fh:
        json.dump({"findings": []}, fh)
    rc, out = _run(["submit", "--session-dir", sd, "--phase", "dispatch-panel", "--attempt", "1",
                    "--artifact", artifact], capsys)
    assert rc == 1 and out["ok"] is False and out["reason"] == "stack-lower-moved"
    assert _read(state_path) == before
    assert len(_refusals(sd, "stack-lower-moved")) == 1


def test_cli_advance_refuses_when_lower_moves_during_the_session(stack, capsys):
    # axis: advance on a started session refuses stack-lower-moved and folds nothing
    sd = _started(stack, capsys)
    state_path = os.path.join(sd, RD.STATE_FILE)
    before = _read(state_path)
    stack.push_lower()
    rc, out = _run(["advance", "--session-dir", sd], capsys)
    assert rc == 1 and out["ok"] is False and out["reason"] == "stack-lower-moved"
    assert _read(state_path) == before
    assert len(_refusals(sd, "stack-lower-moved")) == 1


def test_cli_unreadable_remote_refuses_next_with_a_stale_pin(stack, capsys, tmp_path):
    # axis: an unreachable origin refuses the CLI call even when the cached pin is in HEAD's history
    sd = _started(stack, capsys)
    state_path = os.path.join(sd, RD.STATE_FILE)
    before = _read(state_path)
    _git(stack.repo, "remote", "set-url", "origin", str(tmp_path / "gone.git"))
    rc, out = _run(["next", "--session-dir", sd, "--repo-root", stack.repo], capsys)
    assert rc == 1 and out["reason"] == "stack-lower-unreadable"
    assert _read(state_path) == before


def test_fresh_next_on_a_layer_that_lacks_the_lower_head_creates_no_state(stack, capsys):
    # axis: before the session, next refuses stack-lower-ahead and no state file is written
    new_head = stack.push_lower()
    _git(stack.repo, "fetch", "-q", "origin", "lower")
    sd = stack.session(pin=new_head)
    rc, out = _run(["next", "--session-dir", sd, "--repo-root", stack.repo,
                    "--diff-path", stack.round_diff(sd, pin=stack.pin)], capsys)
    assert rc == 1 and out["reason"] == "stack-lower-ahead"
    assert not os.path.exists(os.path.join(sd, RD.STATE_FILE))
    assert len(_refusals(sd, "stack-lower-ahead")) == 1


# --- the Setup shell computes stackLower ---------------------------------------------------------

def _setup_line(prefix):
    with open(_SKILL, encoding="utf-8") as fh:
        lines = [ln for ln in fh.read().splitlines() if ln.startswith(prefix)]
    assert len(lines) == 1, prefix
    return lines[0]


def _stack_lower_from_setup(repo, base_branch):
    script = "\n".join([_setup_line("DEFAULT_BRANCH="), _setup_line("if [ -n \"$DEFAULT_BRANCH\""),
                        'printf %s "$STACK_LOWER"'])
    return subprocess.run(["bash", "-c", script], cwd=repo, env=dict(os.environ, BASE_BRANCH=base_branch),
                          check=True, capture_output=True, text=True).stdout


def test_setup_marks_a_non_default_base_stacked_and_the_default_not(stack):
    # axis: STACK_LOWER is false for the default branch and true for any other base
    assert _stack_lower_from_setup(stack.repo, "main") == "false"
    assert _stack_lower_from_setup(stack.repo, "lower") == "true"


def test_setup_fails_closed_when_the_default_branch_cannot_be_read(stack, tmp_path):
    # axis: an unreadable default branch is treated as stacked
    _git(stack.repo, "remote", "set-url", "origin", str(tmp_path / "gone.git"))
    assert _stack_lower_from_setup(stack.repo, "main") == "true"


# --- prose ---------------------------------------------------------------------------------------

def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_native_stacks_states_the_stop_and_new_session_rule():
    text = _text(_NATIVE_STACKS)
    assert "while its review loop is open" not in text
    assert "stack-lower-moved" in text
    assert "The tax it removes" in text


def test_workhorse_section_12_names_the_lower_layers_current_head():
    text = _text(_WORKHORSE)
    start = text.index("**The scoped pass writes a review record.**")
    end = text.index("**Keep the PR body correct as you go.**", start)
    para = text[start:end]
    assert "lower layer's current head" in para
    assert "abandoned" in para


def test_review_code_meta_block_records_stack_lower():
    text = _text(_SKILL)
    assert 'stackLower:$stackLower' in text
    assert '--argjson stackLower "$STACK_LOWER"' in text
    assert "stack-lower-moved" in text and "stack-lower-ahead" in text and "stack-lower-unreadable" in text


def test_round_driver_reference_lists_the_three_refusals():
    text = _text(os.path.join(_PLUGIN, "skills", "review-code", "reference", "round-driver.md"))
    for token in (G.REASON_STACK_LOWER_UNREADABLE, G.REASON_STACK_LOWER_MOVED, G.REASON_STACK_LOWER_AHEAD):
        assert re.search(r"^\| `%s` \|" % re.escape(token), text, re.M), token
