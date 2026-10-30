"""A verify gate that fails once runs once more, and the round record holds both runs.

The driver cannot tell from a project's verify command which code a failure sits in, so the re-run
fires on ANY first `fail` at a gate. A failure the round's own change caused fails the re-run too and
halts as before. The second result decides: a `pass` at the same head goes on exactly as a first-time
pass does; anything else halts exactly as it does for a first-time result; a re-run at another head
halts. Both runs land in the round as one `rerunChecks` entry.

The fail-closed edges are numbered as the work order numbers them; each is its own test. The fold
tests drive `_fold_verify` the way the neighbouring verify tests do; the end-to-end test drives the
real `run-verify` verb and `advance` over a throwaway git repository.
"""
import os
import stat
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import test_round_driver_advance as TA  # noqa: E402
from test_round_driver_advance import adapters  # noqa: E402,F401  (a fixture)

import review_record  # noqa: E402
import review_record_session  # noqa: E402

RD = TA.RD
RR = TA.RR
COMMAND = "make test"
H1 = "1" * 40
H2 = "2" * 40
FAIL_REASON = "verify gate failed"


# =============================================================================================
# helpers
# =============================================================================================

def _state(**cfg_over):
    """A round-1 state parked on the verify gate that follows the audits, with a scoped surface so a
    passing gate visibly goes on (to the scoped finder)."""
    cfg_over.setdefault("verifyCommand", COMMAND)
    state = RD.new_state(TA._cfg(**cfg_over))
    state["round"] = 1
    state["rounds"] = {"1": {}}
    state["step"] = RD.P_VERIFY
    state["_verifyThen"] = RD.VERIFY_THEN_POST_AUDITS
    state["_newSurface"] = {"f.py": [1]}
    state["_fixDeltaDiff"] = "diff --git a/f.py b/f.py\n"
    return state


def _fold(state, artifact, fold_head=H1):
    resolution = (fold_head, None) if fold_head else (None, "fix-fold head: repo root unresolvable")
    RD._fold_verify(state, state["config"], artifact, resolution=resolution)
    return state


def _artifact(result, exit_code="default", head=H1, after=None, output_path=None):
    art = {"result": result}
    art["exitCode"] = (0 if result == "pass" else 1) if exit_code == "default" else exit_code
    if head is not None:
        art["headSha"] = head
    if after is not None:
        art["headShaAfter"] = after
    if output_path is not None:
        art["outputPath"] = output_path
    return art


def _log(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def _entries(state):
    return state["rounds"]["1"].get("rerunChecks") or []


def _runs(state):
    (entry,) = _entries(state)
    assert entry["check"] == "verify"
    return entry["runs"]


def _kinds(state):
    return [d["kind"] for d in state["decisions"]]


def _halted_with(state, reason, kind):
    assert state["terminal"] == "halted"
    assert state["step"] == RD.P_TERMINAL
    assert state["certification"] == {"shape": None, "reason": reason}
    assert _kinds(state)[-1] == kind


# =============================================================================================
# the edges, through the fold
# =============================================================================================

def test_edge1_a_first_fail_then_a_pass_at_the_same_head_goes_on_and_records_both_runs(tmp_path):
    first_log = _log(tmp_path, "first.log", "FAILED test_flaky\n")
    second_log = _log(tmp_path, "second.log", "all passed\n")
    state = _state()

    _fold(state, _artifact("fail", output_path=first_log))
    # the first fail does not halt: the same gate is pending again, its continuation untouched
    assert not state.get("terminal")
    assert state["step"] == RD.P_VERIFY
    assert state["_verifyThen"] == RD.VERIFY_THEN_POST_AUDITS
    assert state["_verifyRerun"]["head"] == H1 and state["_verifyRerun"]["headSource"] == "run"
    assert _kinds(state) == ["verify-rerun"]
    assert H1 in state["decisions"][0]["detail"]
    assert _entries(state) == []

    _fold(state, _artifact("pass", output_path=second_log))
    # the pass goes on exactly as a first-time pass does
    assert not state.get("terminal")
    assert state["step"] == RD.P_SCOPED
    assert "_verifyThen" not in state
    assert state["rounds"]["1"]["verifyResult"] == "pass"
    assert state["rounds"]["1"]["verifyVia"] == {"via": "local", "command": COMMAND}
    first, second = _runs(state)
    assert first == {"status": "ran", "exitCode": 1, "output": "FAILED test_flaky\n", "reason": None,
                     "head": H1, "headSource": "run"}
    assert second == {"status": "ran", "exitCode": 0, "output": "all passed\n", "reason": None,
                      "head": H1, "headSource": "run"}


def test_edge2_a_first_fail_then_a_fail_halts_as_a_fail_does_today_with_both_runs(tmp_path):
    state = _state()
    _fold(state, _artifact("fail", output_path=_log(tmp_path, "a.log", "boom 1\n")))
    _fold(state, _artifact("fail", output_path=_log(tmp_path, "b.log", "boom 2\n")))

    _halted_with(state, FAIL_REASON, "verify-fail")
    first, second = _runs(state)
    assert (first["status"], first["exitCode"], first["output"]) == ("ran", 1, "boom 1\n")
    assert (second["status"], second["exitCode"], second["output"]) == ("ran", 1, "boom 2\n")
    assert _kinds(state).count("verify-rerun") == 1
    assert state["rounds"]["1"]["verifyResult"] == "fail"


@pytest.mark.parametrize("second,reason,kind,status,exit_code", [
    ("timeout", "verify gate did not pass (result 'timeout') — halt, certification withheld",
     "verify-unresolved", "timed-out", None),
    ("none", "verify gate reported 'none' but a verify command is configured ('make test') — the "
             "gate did not run; halt, certification withheld",
     "verify-skip-but-configured", "ran", 0),
])
def test_edge3_a_first_fail_then_a_timeout_or_skip_halts_as_that_result_does_today(
        tmp_path, second, reason, kind, status, exit_code):
    state = _state()
    _fold(state, _artifact("fail"))
    _fold(state, _artifact(second, exit_code=exit_code, output_path=_log(tmp_path, "c.log", "late\n")))

    _halted_with(state, reason, kind)
    first_run, second_run = _runs(state)
    assert first_run["status"] == "ran" and first_run["exitCode"] == 1
    assert second_run["status"] == status and second_run["exitCode"] == exit_code
    if second == "timeout":
        assert second_run["reason"] == "timeout" and second_run["output"] == "late\n"


def test_edge4_a_re_run_at_another_head_halts_with_both_runs_recorded():
    state = _state()
    _fold(state, _artifact("fail", head=H1), fold_head=H1)
    _fold(state, _artifact("pass", head=H2), fold_head=H2)

    _halted_with(
        state,
        "verify re-run ran at a different head (%s then %s) — halt, certification withheld" % (H1, H2),
        "verify-rerun-head-moved")
    first, second = _runs(state)
    assert (first["head"], second["head"]) == (H1, H2)


def test_a_passing_re_run_on_changed_working_tree_contents_halts():
    state = _state()
    first = _artifact("fail")
    first["treeSha"] = "a" * 64
    second = _artifact("pass")
    second["treeSha"] = "b" * 64
    _fold(state, first)
    _fold(state, second)

    _halted_with(
        state, "verify re-run ran on changed working-tree contents — halt, certification withheld",
        "verify-rerun-tree-changed")


def test_a_passing_re_run_whose_tree_changed_while_it_ran_halts():
    state = _state()
    first = _artifact("fail")
    first["treeSha"] = "a" * 64
    second = _artifact("pass")
    second["treeSha"] = "a" * 64
    second["treeShaAfter"] = "b" * 64
    _fold(state, first)
    _fold(state, second)

    assert state["terminal"] == "halted"
    assert _kinds(state)[-1] == "verify-rerun-tree-changed"


def test_a_passing_re_run_on_the_same_working_tree_contents_goes_on():
    state = _state()
    first = _artifact("fail")
    first["treeSha"] = "a" * 64
    second = _artifact("pass")
    second["treeSha"] = "a" * 64
    _fold(state, first)
    _fold(state, second)

    assert not state.get("terminal")


def test_edge4_a_re_run_that_straddled_a_head_change_halts():
    state = _state()
    _fold(state, _artifact("fail", head=H1))
    _fold(state, _artifact("pass", head=H1, after=H2))

    _halted_with(
        state,
        "verify re-run ran at a different head (%s then %s) — halt, certification withheld" % (H1, H2),
        "verify-rerun-head-moved")
    assert len(_runs(state)) == 2


def test_edge4_a_re_run_that_straddled_a_head_change_records_where_it_ended():
    # axis: a re-run whose own head moved records where it ended — see bite-proof record c1l9b_wod_head_after
    state = _state()
    _fold(state, _artifact("fail", head=H1))
    _fold(state, _artifact("pass", head=H1, after=H2))

    _halted_with(
        state,
        "verify re-run ran at a different head (%s then %s) — halt, certification withheld" % (H1, H2),
        "verify-rerun-head-moved")
    first, second = _runs(state)
    assert second["head"] == H1 and second["headAfter"] == H2
    assert "headAfter" not in first


def test_edge5_a_first_run_whose_own_head_moved_gets_no_re_run_and_halts():
    state = _state()
    _fold(state, _artifact("fail", head=H1, after=H2))

    _halted_with(state, FAIL_REASON, "verify-fail")
    assert "_verifyRerun" not in state
    assert _entries(state) == []
    assert "verify-rerun" not in _kinds(state)


def test_edge6_a_first_time_pass_is_untouched_and_records_no_re_run():
    state = _state()
    _fold(state, _artifact("pass"))

    assert not state.get("terminal")
    assert state["step"] == RD.P_SCOPED
    assert "_verifyRerun" not in state
    assert _entries(state) == []
    assert _kinds(state) == []


def test_edge6_a_first_time_timeout_is_untouched_and_records_no_re_run():
    state = _state()
    _fold(state, _artifact("timeout", exit_code=None))

    _halted_with(state, "verify gate did not pass (result 'timeout') — halt, certification withheld",
                 "verify-unresolved")
    assert "_verifyRerun" not in state
    assert _entries(state) == []


@pytest.mark.parametrize("result", ["none", "skipped", "unverified", "bogus", None])
def test_edge6_a_first_time_skip_or_unknown_result_is_untouched(result):
    state = _state(verifyCommand="none")
    _fold(state, {"result": result})

    assert "_verifyRerun" not in state
    assert _entries(state) == []
    assert "verify-rerun" not in _kinds(state)


def test_edge6_a_ci_exact_head_claim_never_starts_a_re_run():
    state = _state()
    art = _artifact("fail", head=None)
    art["via"] = "ci-exact-head"
    _fold(state, art)

    _halted_with(state, FAIL_REASON, "verify-fail")
    assert "_verifyRerun" not in state and _entries(state) == []


def test_edge7_a_fail_while_a_re_run_is_pending_never_starts_a_third_run():
    state = _state()
    _fold(state, _artifact("fail"))
    assert "_verifyRerun" in state
    _fold(state, _artifact("fail"))

    _halted_with(state, FAIL_REASON, "verify-fail")
    assert "_verifyRerun" not in state
    assert _kinds(state).count("verify-rerun") == 1
    assert len(_entries(state)) == 1


@pytest.mark.parametrize("second", [
    _artifact("pass"), _artifact("fail"), _artifact("timeout", exit_code=None),
    {"result": "none"}, {"result": "bogus"}, {}, _artifact("pass", head=H2),
])
def test_edge8_the_pending_re_run_never_survives_the_second_fold(second):
    state = _state()
    _fold(state, _artifact("fail"))
    assert "_verifyRerun" in state
    _fold(state, second)

    assert "_verifyRerun" not in state
    assert len(_entries(state)) == 1


def test_edge9_an_unreadable_output_path_records_empty_output_and_does_not_crash(tmp_path):
    state = _state()
    _fold(state, _artifact("fail", output_path=str(tmp_path / "missing.log")))
    _fold(state, _artifact("pass", output_path=str(tmp_path)))  # a directory: unreadable too

    assert not state.get("terminal")
    first, second = _runs(state)
    assert first["output"] == "" and second["output"] == ""
    assert (first["exitCode"], second["exitCode"]) == (1, 0)


def test_edge9_a_long_output_keeps_its_last_four_thousand_characters(tmp_path):
    tail = "z" * 4000
    state = _state()
    _fold(state, _artifact("fail", output_path=_log(tmp_path, "long.log", "head-of-log\n" + "y" * 9000 + tail)))
    _fold(state, _artifact("pass"))

    first, _second = _runs(state)
    assert first["output"] == tail


def test_edge10_two_runs_with_no_known_head_do_not_halt_on_the_head_rule():
    state = _state()
    _fold(state, _artifact("fail", head=None), fold_head=None)
    assert state["_verifyRerun"]["head"] is None and state["_verifyRerun"]["headSource"] == "unknown"
    _fold(state, _artifact("pass", head=None), fold_head=None)

    assert not state.get("terminal")
    assert state["step"] == RD.P_SCOPED
    first, second = _runs(state)
    assert (first["headSource"], second["headSource"]) == ("unknown", "unknown")
    assert first["head"] is None and second["head"] is None


def test_edge10_an_unknown_head_on_one_side_does_not_halt_and_the_second_result_decides():
    state = _state()
    _fold(state, _artifact("fail", head=None), fold_head=None)
    _fold(state, _artifact("fail", head=H2), fold_head=H2)

    _halted_with(state, FAIL_REASON, "verify-fail")
    first, second = _runs(state)
    assert (first["headSource"], second["headSource"]) == ("unknown", "run")


def test_edge10_a_passing_re_run_at_a_head_after_an_unknown_first_head_does_not_halt():
    state = _state()
    _fold(state, _artifact("fail", head=None), fold_head=None)
    _fold(state, _artifact("pass", head=H2), fold_head=H2)

    assert not state.get("terminal")
    assert state["step"] == RD.P_SCOPED
    assert "verify-rerun-head-moved" not in _kinds(state)


def test_edge10_a_passing_re_run_with_no_head_after_a_known_first_head_does_not_halt():
    state = _state()
    _fold(state, _artifact("fail", head=H1), fold_head=H1)
    _fold(state, _artifact("pass", head=None), fold_head=None)

    assert not state.get("terminal")
    assert state["step"] == RD.P_SCOPED
    assert "verify-rerun-head-moved" not in _kinds(state)


def test_a_run_without_its_own_head_takes_the_head_resolved_at_the_fold():
    state = _state()
    _fold(state, _artifact("fail", head=None), fold_head=H1)
    assert state["_verifyRerun"]["headSource"] == "fold"
    _fold(state, _artifact("pass", head=None), fold_head=H1)

    assert not state.get("terminal")
    first, second = _runs(state)
    assert (first["head"], first["headSource"]) == (H1, "fold")
    assert (second["head"], second["headSource"]) == (H1, "fold")


def test_a_run_with_no_exit_code_records_not_started_with_the_result_token():
    state = _state()
    _fold(state, {"result": "fail"})
    _fold(state, {"result": "pass"})

    first, second = _runs(state)
    assert first["status"] == "not-started" and first["exitCode"] is None
    assert first["reason"] == "fail" and first["output"] == ""
    assert second["status"] == "not-started" and second["reason"] == "pass"


# =============================================================================================
# the record the driver writes is one the review record accepts
# =============================================================================================

def test_the_driver_entry_passes_the_review_record_round_validation(tmp_path):
    timed_out = _state()
    _fold(timed_out, _artifact("fail", output_path=_log(tmp_path, "a.log", "boom\n")))
    _fold(timed_out, _artifact("timeout", exit_code=None, output_path=_log(tmp_path, "b.log", "slow\n")))
    passed = _state()
    _fold(passed, _artifact("fail"))
    _fold(passed, _artifact("pass"))

    for folded in (timed_out, passed):
        (entry,) = _entries(folded)
        assert "round" not in entry
        assert review_record._rerun_fault(dict(entry, round=1)) is None
        # through the exporter, which names the containing round on each entry
        exported = review_record_session._rerun_checks(folded["rounds"])
        assert exported == [dict(entry, round=1)]
        assert review_record._rerun_fault(exported[0]) is None


# =============================================================================================
# end to end: the real verb, a real command, advance
# =============================================================================================

_GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "LC_ALL": "C"}


def _git(repo, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(_GIT_ENV)
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
         "-c", "commit.gpgsign=false", "-C", str(repo), *args],
        capture_output=True, text=True, check=True, env=env, timeout=60).stdout.strip()


def test_the_real_verb_re_runs_a_flaky_gate_and_the_round_goes_on(tmp_path, adapters):
    repo = tmp_path / "flaky-repo"
    repo.mkdir()
    counter = tmp_path / "counter"
    script = repo / "flaky.sh"
    script.write_text(
        "#!/bin/bash\n"
        "n=$(cat \"$1\" 2>/dev/null || echo 0)\n"
        "echo $((n + 1)) > \"$1\"\n"
        "echo \"run $((n + 1))\"\n"
        "[ \"$n\" -ge 1 ]\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "flaky")
    head = _git(repo, "rev-parse", "HEAD")

    d = TA._session(tmp_path)
    TA._at_run_verify(tmp_path, d)
    state = TA._state(d)
    state["config"]["verifyCommand"] = "./flaky.sh %s" % counter
    state["config"]["repoRoot"] = str(repo)
    RD.save_state(d, state)

    # the first run fails; advance folds it without halting and hands out the same gate again
    first = RD.cmd_run_verify(d)
    assert first["ok"] is True and first["result"] == "fail" and first["attempt"] == 0, first
    out = TA._advance(d, tmp_path)
    assert out["ok"] is True, out
    mid = TA._state(d)
    assert not mid.get("terminal")
    assert "_verifyRerun" in mid
    pend = TA._pending(d)
    assert (pend["phase"], pend["attempt"]) == (RD.P_VERIFY, 1)

    # the re-run lands at a fresh slot, passes, and the round goes on
    second = RD.cmd_run_verify(d)
    assert second["ok"] is True and second["result"] == "pass" and second["attempt"] == 1, second
    assert second["landingPath"] != first["landingPath"]
    out = TA._advance(d, tmp_path)
    assert out["ok"] is True, out
    end = TA._state(d)
    assert "_verifyRerun" not in end
    assert end["terminal"] != "halted"
    assert "verify-fail" not in [dec["kind"] for dec in end["decisions"]]
    assert end["rounds"]["1"]["verifyResult"] == "pass"
    first_run, second_run = end["rounds"]["1"]["rerunChecks"][0]["runs"]
    assert (first_run["status"], first_run["exitCode"]) == ("ran", 1)
    assert (second_run["status"], second_run["exitCode"]) == ("ran", 0)
    assert first_run["output"] == "run 1\n" and second_run["output"] == "run 2\n"
    assert first_run["head"] == head == second_run["head"]
    assert (first_run["headSource"], second_run["headSource"]) == ("run", "run")
    assert len(end["rounds"]["1"]["rerunChecks"]) == 1


def test_the_real_verb_records_a_head_that_moves_while_the_re_run_executes_and_advance_halts(
        tmp_path, adapters):
    repo = tmp_path / "moving-repo"
    repo.mkdir()
    (repo / "f.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "first")
    h1 = _git(repo, "rev-parse", "HEAD")

    d = TA._session(tmp_path)
    TA._at_run_verify(tmp_path, d)
    state = TA._state(d)
    state["config"]["verifyCommand"] = COMMAND
    state["config"]["repoRoot"] = str(repo)
    RD.save_state(d, state)

    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        if len(calls) == 1:
            return subprocess.CompletedProcess(argv, 1, b"fail\n", None)
        _git(repo, "commit", "-q", "--allow-empty", "-m", "moved during the verify run")
        return subprocess.CompletedProcess(argv, 0, b"pass\n", None)

    first = RD.cmd_run_verify(d, run=fake_run)
    assert first["ok"] is True and first["result"] == "fail", first
    out = TA._advance(d, tmp_path)
    assert out["ok"] is True, out
    assert not TA._state(d).get("terminal")

    second = RD.cmd_run_verify(d, run=fake_run)
    assert second["ok"] is True and second["result"] == "pass" and second["attempt"] == 1, second
    h2 = _git(repo, "rev-parse", "HEAD")
    assert h2 != h1
    landed, err = RR.read_json(second["landingPath"])
    assert err is None, err
    assert landed["headSha"] == h1 and landed["headShaAfter"] == h2

    out = TA._advance(d, tmp_path)
    assert out["ok"] is True, out
    end = TA._state(d)
    assert end["terminal"] == "halted"
    assert end["decisions"][-1]["kind"] == "verify-rerun-head-moved"
