"""C1-L11e (issue #2277): a stacked layer catches up at handback, not by restarting its review.

If the layer below a stacked PR moves before or during the upper layer's review session, the session reads the
upper layer's change against the one commit of the lower layer it pinned at start; before the upper layer hands back
it catches up to the lower layer's current head, re-runs its checks there, and is reviewed for only what that
catch-up changed in its own lines. A move of the lower layer never restarts the review session.

Pins, each at the place the rule is enforced:

R1  `next`, `submit` and `advance` of a started stacked session read no remote head and refuse nothing because the
    lower layer moved; the session keeps the base commit it pinned (the old `stack-lower-*` refusals are gone);
R2  `vet_slot handback --pr --repo` refuses a ready marking of a stacked PR whose head is behind its lower branch
    (`stack-not-caught-up`) or whose lower layer cannot be read (`stack-lower-unreadable`, five fail-closed edges);
    the same catch-up, once merged, converges in round 1 with nothing read and its record reads reviewed, green on
    the caught-up head, with no finding;
R3  a catch-up that changed none of the layer's own lines reads nothing new, and a finding still open from the
    earlier review is re-checked against the caught-up head.

Bite-proof record: c1l11e_wo_a_catch_up
"""
import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import review_record_session as RS  # noqa: E402
import test_c1l11b_returning_session as TS  # noqa: E402
import test_c1l11d_carried_review as TC  # noqa: E402
import test_c1l11d_fold_returning as TF  # noqa: E402
import test_review_record_session as TRRS  # noqa: E402
import test_round_driver as TRD  # noqa: E402
import test_vet_slot as TV  # noqa: E402
import vet_slot as VS  # noqa: E402
from test_c1l11b_returning_session import _isolated_git  # noqa: E402,F401  (autouse: no global git config)

RD = TRD.RD  # the driver module these sessions run on is test_round_driver's own load of it
G = RD.review_base_guard
_PR_URL = "https://github.com/acme/widget/pull/7"


@pytest.fixture(autouse=True)
def _hermetic_git(monkeypatch):
    for key, val in (("AUTHOR", "t"), ("COMMITTER", "t")):
        monkeypatch.setenv("GIT_%s_NAME" % key, val)
        monkeypatch.setenv("GIT_%s_EMAIL" % key, "t@t")
    # The PR-mode fork check compares the PR url to the origin url; a local bare repo has no host.
    monkeypatch.setattr(RD.review_base_guard, "origin_repo", lambda *a, **k: "github.com/acme/widget")


@pytest.fixture(autouse=True)
def _gh_on_path(monkeypatch):
    monkeypatch.setattr(VS.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)


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
        """The session dir with the meta.json review-code Setup wrote before this change: `stackLower` is still in it."""
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


# --- R1 (DoD row 1): the lower layer moves during the session; the session is not restarted ------------------------

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


def _stack_refusals(sd):
    return [e for e in RD.read_journal(sd)
            if e.get("outcome") == "refused-base-guard" and str(e.get("reason")).startswith("stack-")]


def _pins(sd):
    """The base commit the session holds: the state's stored pin and meta.json's."""
    ok, state = RD.load_state(sd)
    assert ok and isinstance(state, dict), state
    with open(os.path.join(sd, "meta.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    return state["config"]["baseRef"], meta["baseRef"]


def _no_stack_reason(out):
    return out is None or not str(out.get("reason")).startswith("stack-")


def test_cli_next_after_the_lower_layer_moves_runs_on_the_pinned_commit(stack, capsys):
    # axis: next on a started stacked session reads no remote head and refuses nothing for a moved lower layer — see bite-proof record c1l11e_wo_a_catch_up
    sd = _started(stack, capsys)
    assert _pins(sd) == (stack.pin, stack.pin)
    moved = stack.push_lower()
    assert moved != stack.pin
    rc, out = _run(["next", "--session-dir", sd, "--repo-root", stack.repo], capsys)
    assert rc == 0 and _no_stack_reason(out), out
    assert _stack_refusals(sd) == []
    assert _pins(sd) == (stack.pin, stack.pin)  # the session ran on the pinned commit: no restart


def test_cli_submit_after_the_lower_layer_moves_is_not_refused_for_it(stack, capsys, tmp_path):
    # axis: submit on a started stacked session reads no remote head and refuses nothing for a moved lower layer
    sd = _started(stack, capsys)
    stack.push_lower()
    artifact = str(tmp_path / "artifact.json")
    with open(artifact, "w", encoding="utf-8") as fh:
        json.dump({"findings": []}, fh)
    _rc, out = _run(["submit", "--session-dir", sd, "--phase", "dispatch-panel", "--attempt", "1",
                     "--artifact", artifact], capsys)
    assert _no_stack_reason(out), out
    assert _stack_refusals(sd) == []
    assert _pins(sd) == (stack.pin, stack.pin)


def test_cli_advance_after_the_lower_layer_moves_is_not_refused_for_it(stack, capsys):
    # axis: advance on a started stacked session reads no remote head and refuses nothing for a moved lower layer
    sd = _started(stack, capsys)
    stack.push_lower()
    _rc, out = _run(["advance", "--session-dir", sd], capsys)
    assert _no_stack_reason(out), out
    assert _stack_refusals(sd) == []
    assert _pins(sd) == (stack.pin, stack.pin)


def test_cli_next_never_reads_the_lower_branch_on_origin(stack, capsys, tmp_path):
    # axis: an unreachable origin does not stop a started stacked session — the lower branch's remote head is not read
    sd = _started(stack, capsys)
    _git(stack.repo, "remote", "set-url", "origin", str(tmp_path / "gone.git"))
    rc, out = _run(["next", "--session-dir", sd, "--repo-root", stack.repo], capsys)
    assert rc == 0 and _no_stack_reason(out), out
    assert _stack_refusals(sd) == []


def test_fresh_next_on_a_layer_that_lacks_the_lower_head_creates_state_normally(stack, capsys):
    # axis: a fresh next pins the base it was given; a layer that does not yet hold the lower layer's new head is not refused
    new_head = stack.push_lower()
    _git(stack.repo, "fetch", "-q", "origin", "lower")
    sd = stack.session(pin=new_head)
    rc, out = _run(["next", "--session-dir", sd, "--repo-root", stack.repo,
                    "--diff-path", stack.round_diff(sd, pin=new_head)], capsys)
    assert rc == 0 and _no_stack_reason(out), out
    assert os.path.isfile(os.path.join(sd, RD.STATE_FILE))
    assert _stack_refusals(sd) == []
    assert _pins(sd) == (new_head, new_head)


def test_the_stack_lower_refusals_and_their_names_are_gone():
    # axis: the removed guard does not come back under another route (driver helper, guard function, reason constants)
    assert not hasattr(RD, "_refuse_stack_lower")
    for name in ("check_stack_lower", "_ls_remote_head", "_branch_name_ok", "REASON_STACK_LOWER_UNREADABLE",
                 "REASON_STACK_LOWER_MOVED", "REASON_STACK_LOWER_AHEAD"):
        assert not hasattr(G, name), name


# --- R2 (DoD row 2): the handback check --------------------------------------------------------------------------------

REPO = "o/r"
PR = 7
LOWER = "claude/issue-2273-workhorse-xvcoga"
HEAD = "5d3e97c07a92d74a015dd498ae7834ffc374f6f1"
PULL = ("gh", "api", "repos/o/r/pulls/7")
COMPARE = ["gh", "api", "repos/o/r/compare/%s...%s" % (LOWER, HEAD)]


def _payload(base_ref=LOWER, default="main", sha=HEAD, body=TV.BODY):
    return {"number": PR, "body": body, "base": {"ref": base_ref, "repo": {"default_branch": default}},
            "head": {"sha": sha}}


def _compare(behind=0, **over):
    row = {"status": "behind" if behind else "identical", "ahead_by": 0, "behind_by": behind, **over}
    return lambda argv: SimpleNamespace(returncode=0, stdout=json.dumps(row), stderr="")


class FakeGh:
    """Serves the PR read, and the compare read through ``compare`` (None: the read must never be made)."""

    def __init__(self, payload, compare=None):
        self.payload, self.compare, self.calls = payload, compare, []

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        assert kwargs.get("timeout") == VS.GH_TIMEOUT
        if tuple(argv) == PULL:
            return SimpleNamespace(returncode=0, stdout=json.dumps(self.payload), stderr="")
        if argv[:2] == ["gh", "api"] and "/compare/" in argv[2]:
            if self.compare is None:
                raise AssertionError("a compare read was made for a PR that is not stacked: %r" % (argv,))
            return self.compare(argv)
        raise AssertionError("unexpected argv %r" % (argv,))


def _handback(payload, compare=None):
    fake = FakeGh(payload, compare)
    return VS.run_verb("handback", PR, REPO, run=fake), fake


def test_a_head_behind_its_lower_branch_refuses_stack_not_caught_up():
    # axis: behind_by > 0 refuses stack-not-caught-up, naming the head, the count, the lower branch and the catch-up step — see bite-proof record c1l11e_wo_a_catch_up
    result, fake = _handback(_payload(), _compare(2))
    assert result["ok"] is False and result["reason"] == "stack-not-caught-up" == VS.REASON_STACK_NOT_CAUGHT_UP
    detail = result["detail"]
    assert HEAD[:12] in detail and HEAD[:13] not in detail and "2 commit" in detail and LOWER in detail
    assert "--no-ff" in detail and "push" in detail and "calibrated verify" in detail
    assert "returning review-code session" in detail and "native-stacks.md" in detail and "handback again" in detail
    assert fake.calls == [list(PULL), COMPARE]


def test_a_head_that_holds_its_lower_branch_passes():
    # axis: behind_by 0 is caught up; the handback body check then runs and passes
    result, fake = _handback(_payload(), _compare(0))
    assert result == {"ok": True, "verb": "handback", "followups": ["FU1", "FU2"]}
    assert fake.calls == [list(PULL), COMPARE]


def test_a_head_ahead_of_its_lower_branch_is_caught_up():
    # axis: only behind_by decides; a layer that is ahead of its lower branch (the usual case) passes
    result, _fake = _handback(_payload(), _compare(0, status="ahead", ahead_by=3))
    assert result["ok"] is True


def test_a_pr_on_the_default_branch_is_not_stacked_and_makes_no_compare_read():
    # axis: base.ref == default_branch is not a stacked PR: no refusal and no further gh call
    result, fake = _handback(_payload(base_ref="main", default="main"), compare=None)
    assert result["ok"] is True
    assert fake.calls == [list(PULL)]


def test_the_catch_up_check_runs_before_the_body_check():
    # axis: a stacked PR behind its lower branch is refused for that, whatever its body says
    result, _fake = _handback(_payload(body="no markers here\n"), _compare(1))
    assert result["reason"] == "stack-not-caught-up"


def test_a_caught_up_stacked_pr_still_gets_the_body_check():
    # axis: the handback body check still runs after the catch-up check passes
    result, _fake = _handback(_payload(body=TV.HYPHEN_BODIES[0]), _compare(0))
    assert result["ok"] is False and result["reason"] == "markers-invalid"


def test_the_lower_branch_is_quoted_into_the_compare_path_but_slashes_stay():
    # axis: a branch name is percent-quoted into the compare path, with its slashes kept
    seen = []

    def compare(argv):
        seen.append(list(argv))
        return _compare(0)(argv)

    result, _fake = _handback(_payload(base_ref="feat/a b#1"), compare)
    assert result["ok"] is True
    assert seen == [["gh", "api", "repos/o/r/compare/feat/a%20b%231..." + HEAD]]


def test_cli_handback_on_a_pr_exits_one_when_the_head_is_behind(capsys):
    # axis: the CLI handback --pr --repo runs the catch-up check and exits 1 on a refusal
    assert VS.main(["handback", "--pr", str(PR), "--repo", REPO], run=FakeGh(_payload(), _compare(2))) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False and out["reason"] == "stack-not-caught-up"
    assert VS.main(["handback", "--pr", str(PR), "--repo", REPO], run=FakeGh(_payload(), _compare(0))) == 0
    assert json.loads(capsys.readouterr().out)["verb"] == "handback"


def test_cli_handback_body_file_runs_no_catch_up_check(capsys, tmp_path):
    # axis: handback --body-file is unchanged: it reads no PR and makes no gh call
    path = tmp_path / "body.md"
    path.write_text(TV.BODY, encoding="utf-8")

    def no_gh(argv, **kwargs):
        raise AssertionError("gh was called for --body-file: %r" % (argv,))

    assert VS.main(["handback", "--body-file", str(path)], run=no_gh) == 0
    assert json.loads(capsys.readouterr().out)["verb"] == "handback"


def _drop(*keys):
    def mutate(payload):
        node = payload
        for key in keys[:-1]:
            node = node[key]
        del node[keys[-1]]
    return mutate


def _set(value, *keys):
    def mutate(payload):
        node = payload
        for key in keys[:-1]:
            node = node[key]
        node[keys[-1]] = value
    return mutate


# e1: base, base.repo or head missing or not a dict
E1 = [("no-base", _drop("base")), ("base-null", _set(None, "base")), ("base-a-list", _set([], "base")),
      ("no-base-repo", _drop("base", "repo")), ("base-repo-a-string", _set("o/r", "base", "repo")),
      ("no-head", _drop("head")), ("head-null", _set(None, "head")), ("head-a-string", _set(HEAD, "head"))]
# e2: base.ref or default_branch not a non-empty string
E2 = [("no-base-ref", _drop("base", "ref")), ("base-ref-empty", _set("", "base", "ref")),
      ("base-ref-blank", _set("  ", "base", "ref")), ("base-ref-int", _set(5, "base", "ref")),
      ("no-default-branch", _drop("base", "repo", "default_branch")),
      ("default-branch-empty", _set("", "base", "repo", "default_branch")),
      ("default-branch-null", _set(None, "base", "repo", "default_branch")),
      ("default-branch-int", _set(7, "base", "repo", "default_branch"))]
# e3: head.sha not 40 hex characters
E3 = [("no-sha", _drop("head", "sha")), ("sha-null", _set(None, "head", "sha")), ("sha-int", _set(5, "head", "sha")),
      ("sha-short", _set(HEAD[:39], "head", "sha")), ("sha-long", _set(HEAD + "a", "head", "sha")),
      ("sha-not-hex", _set("g" * 40, "head", "sha")), ("sha-abbrev", _set(HEAD[:12], "head", "sha"))]


def _unreadable(payload, compare=None):
    result, fake = _handback(payload, compare)
    assert result["ok"] is False and result["reason"] == "stack-lower-unreadable" == VS.REASON_STACK_LOWER_UNREADABLE, result
    return result, fake


@pytest.mark.parametrize("name,mutate", E1, ids=[n for n, _ in E1])
def test_e1_a_payload_without_base_base_repo_or_head_objects_refuses_unreadable(name, mutate):
    # axis: e1 — base, base.repo or head missing or not a dict refuses stack-lower-unreadable, with no compare read — see bite-proof record c1l11e_wo_a_catch_up
    payload = _payload()
    mutate(payload)
    _result, fake = _unreadable(payload)
    assert fake.calls == [list(PULL)]


@pytest.mark.parametrize("name,mutate", E2, ids=[n for n, _ in E2])
def test_e2_a_base_ref_or_default_branch_that_is_not_a_non_empty_string_refuses_unreadable(name, mutate):
    # axis: e2 — base.ref or default_branch not a non-empty string refuses stack-lower-unreadable, with no compare read — see bite-proof record c1l11e_wo_a_catch_up
    payload = _payload()
    mutate(payload)
    _result, fake = _unreadable(payload)
    assert fake.calls == [list(PULL)]


@pytest.mark.parametrize("name,mutate", E3, ids=[n for n, _ in E3])
def test_e3_a_head_sha_that_is_not_forty_hex_characters_refuses_unreadable(name, mutate):
    # axis: e3 — head.sha not 40 hex characters refuses stack-lower-unreadable, with no compare read — see bite-proof record c1l11e_wo_a_catch_up
    payload = _payload()
    mutate(payload)
    _result, fake = _unreadable(payload)
    assert fake.calls == [list(PULL)]


def _raising(exc):
    def compare(argv):
        raise exc
    return compare


def _out(stdout, returncode=0, stderr=""):
    return lambda argv: SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


E4 = [("exit-nonzero", _out("", 1, "boom: HTTP 404"), "boom: HTTP 404"),
      ("timeout", _raising(subprocess.TimeoutExpired(["gh"], 1)), "timed out"),
      ("oserror", _raising(OSError("gh vanished")), "gh vanished"),
      ("bad-json", _out("{not json"), "bad JSON"),
      ("json-list", _out("[]"), "not an object"),
      ("json-null", _out("null"), "not an object"),
      ("json-number", _out("3"), "not an object")]


@pytest.mark.parametrize("name,compare,detail", E4, ids=[n for n, _c, _d in E4])
def test_e4_a_compare_read_that_fails_or_is_not_an_object_refuses_unreadable(name, compare, detail):
    # axis: e4 — the compare gh call fails, times out, raises OSError, or prints JSON that is bad or not an object: refuses stack-lower-unreadable with the original detail — see bite-proof record c1l11e_wo_a_catch_up
    result, fake = _unreadable(_payload(), compare)
    assert detail in result["detail"], result
    assert fake.calls == [list(PULL), COMPARE]


E5 = [("missing", None), ("null", None), ("string", "2"), ("float", 2.0), ("bool-true", True), ("bool-false", False),
      ("negative", -1), ("list", [2])]


@pytest.mark.parametrize("name,behind", E5, ids=[n for n, _ in E5])
def test_e5_a_behind_by_that_is_not_a_count_refuses_unreadable(name, behind):
    # axis: e5 — behind_by missing, not an int, a bool, or negative refuses stack-lower-unreadable, never a pass — see bite-proof record c1l11e_wo_a_catch_up
    row = {"status": "identical", "ahead_by": 0}
    if name != "missing":
        row["behind_by"] = behind
    _unreadable(_payload(), _out(json.dumps(row)))


# --- R2b (DoD row 2, after the catch-up): a lower layer that changed a file the layer also changes ------------------

SHARED = TF.SHARED


def _caught_up_session(tmp_path, monkeypatch):
    """A PR that edited line 26 of a shared file, reviewed once; the lower layer then rewrote that file far from the
    PR's hunk, and the PR merged it in (a catch-up). The session's base is the moved lower layer."""
    def catch_up(repo):
        repo.moved = repo.main_commit(SHARED, TF._far_base_text())
        repo.merge_main()

    s = TS.Session(tmp_path, monkeypatch, first={SHARED: TF._shared_with_pr_edit()}, change=catch_up,
                   base_after=lambda repo: repo.moved)
    s.cfg["headSha"] = s.head  # the session reviews the PR's head: the account's final commit
    return s


def _converged(s):
    answer = s.next()
    assert answer["action"] == RD.P_TERMINAL and answer["payload"]["verdict"] == "converged", answer
    return s.state()


def test_a_catch_up_over_a_file_the_layer_also_changes_converges_in_round_one_with_nothing_read(tmp_path, monkeypatch):
    # axis: the returning round's surface holds only the files the decider named as changed; a catch-up's index line is not content — see bite-proof record c1l11e_wo_a_catch_up
    s = _caught_up_session(tmp_path, monkeypatch)
    state = _converged(s)
    assert state["config"]["returning"]["read"] == "changed" and state["config"]["returning"]["changedFiles"] == []
    assert state["rounds"]["1"]["scopedFinder"] == "skipped-empty-surface"
    assert state["rounds"]["1"]["roundKind"] == RD.RETURNING_KIND and state["round"] == 1
    assert state["findings"] == []
    assert [r for r in RS._journal(s.dir) if r.get("outcome") == "recorded"] == []  # no reviewer ran


def test_the_record_of_that_catch_up_reads_reviewed_green_on_the_caught_up_head_with_no_finding(tmp_path, monkeypatch):
    # axis: the record written from the empty catch-up round reads reviewed, its final commit and CI line are the caught-up head's, and it holds no finding
    s = _caught_up_session(tmp_path, monkeypatch)
    _converged(s)
    fake = TRRS.Fake(head=s.head)
    TC._post_earlier(fake, s)
    out = TC._send(tmp_path, s, fake)
    assert out["ok"] is True and out["status"] == "reviewed", out
    rec = TC._latest(fake)
    assert rec["status"] == "reviewed" and rec["finalCommit"]["sha"] == s.head != s.reviewed
    assert rec["ci"]["state"] == "green" and rec["ci"]["sha"] == s.head, rec["ci"]
    assert rec["checked"][0] == "CI on %s: green" % s.head[:7], rec["checked"]
    assert rec["findings"] == [] and rec["leftForOwner"] == []


# A file whose own change is the same in both diffs and whose `index` line differs: what a catch-up leaves of a file the layer also changes.
_REVIEWED = "diff --git a/f.py b/f.py\nindex 1111111..2222222 100644\n--- a/f.py\n+++ b/f.py\n@@ -1,3 +1,3 @@\n x\n-y\n+z\n w\n"
_CAUGHT_UP = _REVIEWED.replace("1111111..2222222", "3333333..4444444")


def test_the_fix_delta_surface_keeps_out_every_file_outside_only():
    # axis: only=set skips every file not in it (no surface entry, no text); only=None is today's compare of raw sections — see bite-proof record c1l11e_wo_a_catch_up
    state = RD.new_state(TRD._cfg())
    surface, text = RD._fix_delta_surface(state, _REVIEWED, _CAUGHT_UP)
    assert list(surface) == ["f.py"] and "index" in text, (surface, text)  # the premise of the fix: the raw compare reads the index pair
    assert RD._fix_delta_surface(state, _REVIEWED, _CAUGHT_UP, only=None) == (surface, text)
    assert RD._fix_delta_surface(state, _REVIEWED, _CAUGHT_UP, only={"f.py"}) == (surface, text)
    assert RD._fix_delta_surface(state, _REVIEWED, _CAUGHT_UP, only=set()) == ({}, "")
    assert RD._fix_delta_surface(state, _REVIEWED, _CAUGHT_UP, only={"other.py"}) == ({}, "")


@pytest.mark.parametrize("changed,keeps", [
    ([], False), (["other.py"], False), (["f.py"], True),
    (None, True), ("f.py", True), (["f.py", 3], True), ([3], True),
], ids=["none-changed", "another-file", "this-file", "absent", "a-string", "a-non-string-member", "only-non-string"])
def test_a_returning_surface_is_filtered_by_the_deciders_changed_files_only_when_it_is_a_list_of_strings(monkeypatch, changed, keeps):
    # axis: _returning_surface passes only=set(changedFiles) when the decider's list is all strings, and no filter otherwise — see bite-proof record c1l11e_wo_a_catch_up
    monkeypatch.setattr(RD, "_returning_diffs", lambda state, cfg: (_REVIEWED, _CAUGHT_UP))
    returning = {"read": "changed"} if changed is None else {"read": "changed", "changedFiles": changed}
    (surface, text), why = RD._returning_surface(RD.new_state(TRD._cfg()), {"returning": returning})
    assert why is None
    assert (list(surface) == ["f.py"]) is keeps and ("index" in text) is keeps, (surface, text)


# --- R3 (DoD row 3): a catch-up that changed none of the layer's lines reads nothing new; open findings are re-checked ---

LEFT = dict(TC.OPEN, outcome="left-for-owner", reason="waits for the owner")


def _open_earlier(tmp_path, monkeypatch):
    """The caught-up session, over an earlier record that holds one finding still open (left for the owner)."""
    s = _caught_up_session(tmp_path, monkeypatch)
    fake = TRRS.Fake(head=s.head)
    earlier = TC._post_earlier(fake, s, findings=[LEFT])
    [held] = earlier["findings"]
    assert held["outcome"] == "left-for-owner" and held["findingKey"]
    s.write_earlier(dict(TC._latest(fake)))
    state = _converged(s)
    assert state["rounds"]["1"]["scopedFinder"] == "skipped-empty-surface" and state["findings"] == []
    return s, fake, held["findingKey"]


def _check(s, key, **over):
    return {"key": key, "settled": "fixed", "commit": s.reviewed, "checkedHead": s.head,
            "evidence": "ran the test on the caught-up head; it passes", **over}


def test_an_empty_catch_up_round_carries_the_open_finding_and_the_record_still_reads_the_earlier_review(tmp_path, monkeypatch):
    # axis: a catch-up that changed none of the layer's lines reads nothing new; the record carries the earlier reviewers and keeps the open finding open
    s, fake, key = _open_earlier(tmp_path, monkeypatch)
    out = TC._send(tmp_path, s, fake)
    assert out["ok"] is True, out
    rec = TC._latest(fake)
    assert rec["finalCommit"]["sha"] == s.head
    assert rec["reviewers"] and all(v["carried"] == {"commit": s.reviewed} for v in rec["reviewers"]), rec["reviewers"]
    [held] = rec["findings"]
    assert held["findingKey"] == key and held["outcome"] == "left-for-owner" and rec["carriedRechecks"] == []


def test_a_still_open_finding_is_rechecked_against_the_caught_up_head(tmp_path, monkeypatch):
    # axis: a carried check made at the caught-up head moves a fixed finding to fixed and names that head — see bite-proof record c1l11e_wo_a_catch_up
    s, fake, key = _open_earlier(tmp_path, monkeypatch)
    out = TC._send(tmp_path, s, fake, carriedChecks=[_check(s, key)])
    assert out["ok"] is True, out
    rec = TC._latest(fake)
    [held] = rec["findings"]
    assert held["outcome"] == "fixed" and rec["leftForOwner"] == []
    assert "checked against the final commit %s" % s.head[:7] in held["reason"], held["reason"]
    [row] = rec["carriedRechecks"]
    assert row["result"] == "fixed" and row["checkedHead"] == s.head == rec["finalCommit"]["sha"], row


@pytest.mark.parametrize("settled", ["applies", "unsettled"])
def test_a_recheck_at_the_caught_up_head_that_still_finds_it_keeps_it_for_the_owner(tmp_path, monkeypatch, settled):
    # axis: a check at the caught-up head that finds the finding still there keeps it left for the owner, with that head named
    s, fake, key = _open_earlier(tmp_path, monkeypatch)
    out = TC._send(tmp_path, s, fake, carriedChecks=[_check(s, key, settled=settled, commit=None, evidence="still reads past the end")])
    assert out["ok"] is True, out
    rec = TC._latest(fake)
    [held] = rec["findings"]
    assert held["outcome"] == "left-for-owner" and rec["leftForOwner"] == [held["id"]]
    assert "a check against the final commit" in held["reason"] and "still reads past the end" in held["reason"]
    [row] = rec["carriedRechecks"]
    assert row["result"] == "kept" and row["checkedHead"] == s.head, row


def test_a_recheck_made_before_the_catch_up_does_not_count_for_the_caught_up_head(tmp_path, monkeypatch):
    # axis: a check counts only for the commit the record names as final; one made at the pre-catch-up commit keeps the finding
    s, fake, key = _open_earlier(tmp_path, monkeypatch)
    out = TC._send(tmp_path, s, fake, carriedChecks=[_check(s, key, checkedHead=s.reviewed)])
    assert out["ok"] is True, out
    rec = TC._latest(fake)
    [held] = rec["findings"]
    assert held["outcome"] == "left-for-owner"
    assert "checked on %s, not the final commit %s" % (s.reviewed[:7], s.head[:7]) in held["reason"], held["reason"]
