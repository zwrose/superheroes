"""A passing break-it test that missed its path gets one more test (C1-L7, #2211, WO-C).

A finding whose break-it test passed on the unfixed code, and that the verifier judged as not reaching the
finding's path (`pathReached: false`), is never graded or closed on that test alone: it is held, one fresh run of
the test reviewer writes one more test for it, the driver runs that test, and the verifier grades the finding on
all the evidence. A REFUTED verdict closes it as wrong; any other verdict keeps it, graded. No finding gets a
third test and none is lost on the way.

Groups: T the hold's truth table (`apply_verdicts`) · FR-15 a passing test that reached the path refutes the
finding · FR-16 a passing test that missed it is held, sent to the second-test seat, run, and graded again ·
FR-17 the second pass never holds again · F3 pass 2 stages its ids afresh · F4 the kept-check reads the second
test as the finding's latest · U the unseatable seat · M a missing, absent or malformed result · S the strict
verdicts schema · C the census of every site that names the phase.

Edges: 1 `pathReached` missing, null or non-bool is never held · 2 a passed run with no run record, or an outcome
other than exactly `passed`, is never held · 3 an unseatable seat emits no order, the held findings go to pass 2
marked `secondTest`, disclosed · 4 a missing seat result is the adapter's refuse-fold · 5 a result with no match, a
malformed block or a duplicate id sends that finding to pass 2 with no new test, recorded · 6 a second test the
runner records `not-run` is still appended and the finding goes to pass 2 · 7 a finding held in pass 2 is kept
`plausible`, never re-held or dropped, recorded · 8 a park while held closes nothing · 9 pass-1 drops and grades are
written in pass 1 and are not rewritten in pass 2.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/c1l7_wo_c_second_test.md
"""
import glob
import json
import os
import shlex
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import break_it  # noqa: E402
import decision_kinds  # noqa: E402
import engine_result_channel as ERC  # noqa: E402
import model_registry  # noqa: E402
import payload_contracts as PC  # noqa: E402
import receipt_disclosures  # noqa: E402
import review_record  # noqa: E402
import review_record_session as rs  # noqa: E402
import round_adapters as RA  # noqa: E402
import round_orders as RO  # noqa: E402
import round_phases as RP  # noqa: E402
import session_contract as SC  # noqa: E402
import test_break_it_loop as TBL  # noqa: E402
import test_round_driver as TRD  # noqa: E402
import test_synthesis_seat_1858 as S1858  # noqa: E402
import test_verification as TV  # noqa: E402
import verification as V  # noqa: E402
from session_checkout import enter_checkout  # noqa: E402

RD = TRD.RD
FIRST_PATH = "tests/test_first_try.py"
SECOND_PATH = "tests/test_second_try.py"
_FIRST = TBL._block(FIRST_PATH, "print('first try')\n")
_SECOND = TBL._block(SECOND_PATH, "print('second try')\n")
_CONSEQUENCE = "a reviewer-found defect stays in the change"
_NOTE = "the first test never calls the retry path"
_REACHED_REASON = "the test ran the retry path and the guard held"
_SECOND_REASON = "the second test reached the path and the guard held"
_DIFF = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
         "@@ -1 +1,4 @@\n-old\n+new\n+more\n+most\n+last\n")
_HELD = {"title": "retry applies the write twice", "severity": "Important", "file": "f.py", "line": 2,
         "consequence": _CONSEQUENCE, "suggestion": _FIRST}
_PLAIN = {"title": "plain defect", "severity": "Important", "file": "f.py", "line": 3,
          "consequence": _CONSEQUENCE}
_CONFIRMED = {"verdict": "CONFIRMED", "reason": "reproduced", "evidence": "ran: 1 failed"}
_PLAUSIBLE = {"verdict": "PLAUSIBLE", "reason": "could not run it"}
_MISSED = {"verdict": "PLAUSIBLE", "reason": _NOTE, "pathReached": False}
_REACHED = {"verdict": "REFUTED", "reason": _REACHED_REASON, "pathReached": True}
_SECOND_REFUTED = {"verdict": "REFUTED", "reason": _SECOND_REASON}
_KEPT_SUFFIX = " (kept as a judgment call; no further test)"
PASSED = {"outcome": "passed"}


# ---- T: the hold's truth table --------------------------------------------------------------------------------

def _apply(verdict, **finding_kw):
    findings = TV._stage([TV._f("a.py", "bug", "Important", **finding_kw)])
    return V.apply_verdicts(findings, [dict(verdict, id="v0")])


@pytest.mark.parametrize("verdict", [
    pytest.param({"verdict": "REFUTED", "reason": "the test ran the path"}, id="refuted"),
    pytest.param({"verdict": "PLAUSIBLE", "reason": "the test never reached it"}, id="plausible"),
])
def test_t_a_passed_run_that_missed_its_path_is_held_whatever_the_verdict(verdict):
    # bites on: the hold condition never holding (G1)
    out = _apply(dict(verdict, pathReached=False), breakItRun=PASSED)
    assert out["findings"] == [] and out["drops"] == []
    assert out["held"] == [{"id": "v0", "file": "a.py", "title": "bug", "note": verdict["reason"]}]


def test_t_a_held_finding_is_graded_nowhere_and_its_note_defaults():
    out = _apply({"verdict": "PLAUSIBLE", "reason": "   ", "pathReached": False}, breakItRun=PASSED)
    assert out["held"][0]["note"] == "no reason given"
    assert out["findings"] == [] and out["drops"] == [] and out["downgrades"] == []
    assert out["unverified"] == [] and out["notExecuted"] == []


def test_t_a_passed_run_that_reached_its_path_is_a_wrong_drop():
    out = _apply(dict(_REACHED), breakItRun=PASSED)
    assert out["held"] == [] and out["findings"] == []
    assert out["drops"][0]["grade"] == {"verdict": "wrong", "reason": _REACHED_REASON}


@pytest.mark.parametrize("path_reached", [
    pytest.param(None, id="null"), pytest.param("false", id="string"), pytest.param(0, id="zero"),
    pytest.param([], id="list"),
])
def test_t_a_path_reached_that_is_not_exactly_false_never_holds(path_reached):
    # edge 1
    out = _apply({"verdict": "PLAUSIBLE", "reason": "r", "pathReached": path_reached}, breakItRun=PASSED)
    assert out["held"] == [] and len(out["findings"]) == 1


def test_t_a_missing_path_reached_never_holds():
    out = _apply({"verdict": "REFUTED", "reason": "the guard holds"}, breakItRun=PASSED)
    assert out["held"] == [] and len(out["drops"]) == 1


@pytest.mark.parametrize("run", [
    pytest.param({"outcome": "failed"}, id="failed"),
    pytest.param({"outcome": "not-run"}, id="not-run"),
    pytest.param({"outcome": "passed "}, id="outcome-spelled-otherwise"),
    pytest.param({"outcome": True}, id="outcome-not-a-string"),
    pytest.param({}, id="no-outcome"),
    pytest.param("passed", id="record-is-a-string"),
    pytest.param(None, id="record-is-null"),
])
def test_t_a_run_record_that_is_not_exactly_passed_never_holds(run):
    # edge 2
    out = _apply(dict(_MISSED), breakItRun=run)
    assert out["held"] == [] and len(out["findings"]) == 1


def test_t_a_finding_with_no_run_record_never_holds():
    out = _apply(dict(_MISSED))
    assert out["held"] == [] and len(out["findings"]) == 1


def test_t_an_honored_confirmed_with_evidence_is_not_held():
    out = _apply(dict(_CONFIRMED, pathReached=False), breakItRun=PASSED)
    assert out["held"] == []
    assert out["findings"][0]["grade"] == {"verdict": "confirmed", "reason": "reproduced"}


def test_t_a_confirmed_without_evidence_is_not_honored_so_it_is_held():
    out = _apply({"verdict": "CONFIRMED", "reason": "looks real", "pathReached": False}, breakItRun=PASSED)
    assert len(out["held"]) == 1 and out["findings"] == []


def test_t_a_second_test_finding_is_never_held_and_is_kept_with_the_judgment_call_suffix():
    # bites on: the secondTest exclusion from holding (G2)
    out = _apply(dict(_MISSED), breakItRun=PASSED, secondTest=True)
    assert out["held"] == [] and out["drops"] == []
    kept = out["findings"][0]
    assert kept["verdict"] == "PLAUSIBLE"
    assert kept["grade"] == {"verdict": "plausible", "reason": _NOTE + _KEPT_SUFFIX}


def test_t_a_second_test_finding_ignores_path_reached_when_it_is_refuted():
    out = _apply(dict(_MISSED, verdict="REFUTED"), breakItRun=PASSED, secondTest=True)
    assert out["held"] == []
    assert out["drops"][0]["grade"] == {"verdict": "wrong", "reason": _NOTE}


def test_t_a_second_test_finding_without_path_reached_false_gets_no_suffix():
    out = _apply({"verdict": "PLAUSIBLE", "reason": "r", "pathReached": True}, breakItRun=PASSED, secondTest=True)
    assert out["findings"][0]["grade"] == {"verdict": "plausible", "reason": "r"}


# ---- the driven round -----------------------------------------------------------------------------------------

class Round:
    """A driven review session in a real checkout. The test role raises ``_HELD`` (its attached test is `_FIRST`)
    and the code reviewer raises each of ``plain``; the verifier answers each title from ``first`` (pass 1) or
    ``second`` (a finding marked `secondTest`), CONFIRMED when a title is in neither. ``second_result`` builds the
    second-test seat's findings from the step payload."""

    def __init__(self, tmp_path, first=None, second=None, plain=(), second_result=None, seat_map=None, **cfg_kw):
        self.dir = str(tmp_path)
        self.checkout = os.path.join(self.dir, "checkout")
        head = enter_checkout(self.checkout)
        TRD._seed_repo_root_if_missing(self.dir, self.checkout)
        cfg = S1858._cfg(**cfg_kw)
        cfg.pop("repoRoot")  # the driven session runs in a real checkout
        if seat_map is not None:
            cfg["seatMap"] = seat_map
        self.cfg = TRD._cfg(diff=_DIFF, headSha=head, breakItInterpreter=shlex.quote(sys.executable), **cfg)
        self.first = {_HELD["title"]: _MISSED} if first is None else first
        self.second = second or {}
        self.plain = list(plain)
        self.second_result = second_result or self._default_result
        self.seen, self.verifier_payloads = [], []
        self.started = False

    @staticmethod
    def _default_result(payload):
        return [{"id": e["id"], "title": e["title"], "file": e["file"], "line": e["line"],
                 "severity": e["severity"], "consequence": e["consequence"], "suggestion": _SECOND}
                for e in payload["findings"]]

    def state(self):
        ok, state = RD.load_state(self.dir)
        assert ok, state
        return state

    def respond(self, phase, payload, rnd):
        self.seen.append(phase)
        if phase == RD.P_PANEL:
            seats = {d: {"findings": []} for d in RD.DIMENSIONS}
            if rnd == 1:
                seats["test-role"] = {"findings": [dict(_HELD)]}
                seats["code-reviewer"] = {"findings": [dict(f) for f in self.plain]}
            return {"seats": seats}
        if phase == RD.P_VERIFIERS:
            self.verifier_payloads.append(payload)
            verdicts = []
            for cluster in payload.get("clusters", []):
                for finding, fid in zip(cluster["findings"], cluster["ids"]):
                    table = self.second if finding.get("secondTest") is True else self.first
                    verdicts.append(dict(table.get(finding["title"], _CONFIRMED), id=fid))
            return {"verdicts": verdicts,
                    "verifierVendor": RD._nonpanel_selection(self.state(), self.dir, phase)[0]}
        if phase == RD.P_SECOND_TEST:
            return self.second_artifact(self.second_result(payload))
        return TRD._responder()(phase, payload, rnd)

    def second_artifact(self, findings):
        art = {"findings": findings}
        vendor = RD._nonpanel_selection(self.state(), self.dir, RD.P_SECOND_TEST)[0]
        if vendor is not None:
            art["reviewerVendor"] = vendor
        return art

    def drive(self, stop=None):
        """Drive next/submit until the pending step is ``stop`` (returned unsubmitted) or the terminal."""
        for _ in range(80):
            n = RD.cmd_next(self.dir, None if self.started else self.cfg)
            self.started = True
            assert n["ok"], n
            if n["action"] == RD.P_TERMINAL or n.get("phase") == stop:
                return n
            art = TRD._claim_reviewer(self.dir, n["phase"], self.respond(n["phase"], n["payload"], n["round"]))
            s = RD.cmd_submit(self.dir, n["phase"], n["attempt"], n["expectedStateHash"], art)
            assert s["ok"], s
        raise AssertionError("no terminal or %s within 80 steps; saw %s" % (stop, self.seen))

    def submit(self, n, findings):
        s = RD.cmd_submit(self.dir, n["phase"], n["attempt"], n["expectedStateHash"],
                          self.second_artifact(findings))
        assert s["ok"], s
        return s

    def to_second_test(self):
        n = self.drive(stop=RD.P_SECOND_TEST)
        assert n.get("phase") == RD.P_SECOND_TEST, (n.get("action"), self.seen)
        return n

    def row(self, title=_HELD["title"], state=None):
        rows = [e for e in (state or self.state())[SC.DISPOSITION_LEDGER_KEY] if e.get("title") == title]
        assert len(rows) == 1, rows
        return rows[0]


def _key(finding=_HELD):
    return SC.finding_identity_key(finding)


# ---- FR-15 ----------------------------------------------------------------------------------------------------

def test_fr15_a_passing_test_that_reached_the_path_closes_the_finding_wrong(tmp_path):
    r = Round(tmp_path, first={_HELD["title"]: _REACHED})
    r.drive()
    state = r.state()
    assert RD.P_SECOND_TEST not in r.seen and RD.P_FIXER not in r.seen, r.seen
    row = r.row(state=state)
    assert row["disposition"] == "refuted"
    assert row["grade"] == {"verdict": "wrong", "reason": _REACHED_REASON}
    # in no fix batch: nothing the round kept was a survivor
    assert _HELD["title"] not in {f.get("title") for f in state["findings"]}
    assert [p["held"] for p in state["rounds"]["1"]["verifyPasses"]] == [0]
    (run,) = state["rounds"]["1"]["breakItRuns"]
    assert run["outcome"] == "passed"
    # the session record reads it shown-wrong, on the verifier's grade
    assert rs._decide(row, {_key(): row}, {})[:2] == ("shown-wrong", _REACHED_REASON)


# ---- FR-16 ----------------------------------------------------------------------------------------------------

def test_fr16_a_passing_test_that_missed_its_path_is_held_and_offered_to_the_second_test_seat(tmp_path):
    # bites on: the hold condition never holding (G1)
    r = Round(tmp_path)
    n = r.to_second_test()
    state = r.state()
    assert state["step"] == RD.P_SECOND_TEST and n["action"] == RD.P_SECOND_TEST
    (entry,) = n["payload"]["findings"]
    assert (entry["title"], entry["file"], entry["line"]) == (_HELD["title"], "f.py", 2)
    assert entry["severity"] == "Important" and entry["consequence"] == _CONSEQUENCE
    assert entry["suggestion"] == _FIRST and entry["verifierNote"] == _NOTE
    assert V.is_staged_id(entry["id"])
    (first_run,) = entry["breakItRuns"]
    assert first_run["test"] == FIRST_PATH and first_run["status"] == "ran" and first_run["exitCode"] == 0
    assert isinstance(first_run["output"], str)
    # held, not graded or closed: the ledger row is open and ungraded
    row = r.row(state=state)
    assert "disposition" not in row and "grade" not in row
    assert [f["title"] for f in state["_toVerify"]] == [_HELD["title"]]
    second = state["rounds"]["1"]["secondTest"]
    assert second["held"] == [{"findingKey": _key(), "note": _NOTE}]
    assert [p["held"] for p in state["rounds"]["1"]["verifyPasses"]] == [1]
    assert any(d["kind"] == "second-test-held" for d in state["decisions"])


def test_fr16_the_rendered_order_carries_the_assignment_and_the_grammar(tmp_path):
    r = Round(tmp_path)
    r.to_second_test()
    (order,) = glob.glob(os.path.join(r.dir, "round-1", "orders", RD.P_SECOND_TEST, "*.md"))
    with open(order, encoding="utf-8") as fh:
        text = fh.read()
    assert "Write one new test that reaches the finding's path." in text
    assert "This is the finding's last test" in text
    assert "- The break-it block (" in text and break_it.BLOCK_TEMPLATE in text
    assert "Return only the items you were given, each once, by its staged `id`." in text
    held_path = [line for line in text.splitlines() if "Held items" in line or "second-test-held" in line]
    assert held_path
    (sidecar,) = glob.glob(os.path.join(r.dir, "round-1", "**", RD.ORDER_SIDECAR_HELD_FILE), recursive=True)
    with open(sidecar, encoding="utf-8") as fh:
        held = json.load(fh)["findings"]
    assert [h["title"] for h in held] == [_HELD["title"]] and held[0]["verifierNote"] == _NOTE


def test_fr16_a_new_test_is_run_and_appended_to_the_finding_and_the_round_history(tmp_path):
    # bites on: the round-history append of the second run (G4)
    r = Round(tmp_path)
    n = r.to_second_test()
    r.submit(n, r.second_result(n["payload"]))
    state = r.state()
    runs = state["rounds"]["1"]["breakItRuns"]
    assert [(x["path"], x["outcome"], x["findingKey"]) for x in runs] == [
        (FIRST_PATH, "passed", _key()), (SECOND_PATH, "passed", _key())]
    staged = state["_toVerify"][0]
    assert [x["test"] for x in staged[break_it.RUNS_FIELD]] == [FIRST_PATH, SECOND_PATH]
    assert staged[break_it.RUN_FIELD]["path"] == SECOND_PATH and staged["suggestion"] == _SECOND
    assert staged["secondTest"] is True
    assert [x["test"] for x in r.row(state=state)[break_it.RUNS_FIELD]] == [FIRST_PATH, SECOND_PATH]
    second = state["rounds"]["1"]["secondTest"]
    assert second["ran"] == [{"findingKey": _key(), "outcome": "passed"}]
    assert second["noTest"] == [] and second["unmatched"] == []


def test_fr16_the_next_step_is_the_verifiers_over_only_that_finding(tmp_path):
    r = Round(tmp_path, plain=[_PLAIN], first={_HELD["title"]: _MISSED, _PLAIN["title"]: _PLAUSIBLE})
    n = r.to_second_test()
    # pass 1 kept the plain finding aside: the second test seat sees only the held one
    assert [e["title"] for e in n["payload"]["findings"]] == [_HELD["title"]]
    r.submit(n, r.second_result(n["payload"]))
    nxt = RD.cmd_next(r.dir, None)
    assert nxt["ok"] and nxt["phase"] == RD.P_VERIFIERS
    findings = [f for c in nxt["payload"]["clusters"] for f in c["findings"]]
    assert [f["title"] for f in findings] == [_HELD["title"]]
    assert findings[0]["secondTest"] is True and findings[0]["id"] == "v0"


# ---- FR-17 ----------------------------------------------------------------------------------------------------

def test_fr17_a_refuted_verdict_in_pass_two_closes_the_finding_wrong(tmp_path):
    r = Round(tmp_path, second={_HELD["title"]: _SECOND_REFUTED})
    r.drive()
    state = r.state()
    assert r.seen.count(RD.P_SECOND_TEST) == 1 and r.seen.count(RD.P_VERIFIERS) == 2, r.seen
    row = r.row(state=state)
    assert row["disposition"] == "refuted" and row["grade"] == {"verdict": "wrong", "reason": _SECOND_REASON}
    assert state["terminal"] and RD.P_FIXER not in r.seen
    assert [p["held"] for p in state["rounds"]["1"]["verifyPasses"]] == [1, 0]


def test_fr17_a_kept_finding_never_gets_a_third_test(tmp_path):
    # bites on: the secondTest exclusion from holding (G2)
    r = Round(tmp_path, second={_HELD["title"]: _MISSED})
    n = r.drive(stop=RD.P_SYNTHESIS)
    state = r.state()
    assert n["phase"] == RD.P_SYNTHESIS and r.seen.count(RD.P_SECOND_TEST) == 1, r.seen
    (kept,) = n["payload"]["findings"]
    assert kept["title"] == _HELD["title"] and kept["verdict"] == "PLAUSIBLE"
    assert kept["grade"] == {"verdict": "plausible", "reason": _NOTE + _KEPT_SUFFIX}
    assert [p["held"] for p in state["rounds"]["1"]["verifyPasses"]] == [1, 0]
    assert not any(d["kind"] == "second-test-held-again" for d in state["decisions"])
    assert r.row(state=state)["grade"]["reason"] == _NOTE + _KEPT_SUFFIX
    r.drive()
    assert r.seen.count(RD.P_SECOND_TEST) == 1, r.seen


def test_fr17_a_finding_held_in_pass_two_is_kept_plausible_and_never_dropped():
    # edge 7: every finding in pass 2 carries `secondTest`, so nothing is held; one that is anyway is kept
    cfg = {"leg": "code", "vendors": ["claude", "codex"], "diff": "d", "fixerVendor": "codex",
           "seatMap": {"hostFamily": "anthropic"}}
    state = RD.new_state(cfg)
    # staged as the panel fold leaves it: the run record is stamped by the break-it run, which compile keeps
    RD._stage_findings(state, [dict(_HELD, breakItRun=PASSED)])
    state["_secondTestPass"] = True
    state["_secondTestCarry"] = []
    RD._fold_verifiers(state, state["config"], {"verdicts": [dict(_MISSED, id="v0")]})
    (kept,) = state["_verified"]
    assert kept["verdict"] == "PLAUSIBLE"
    assert kept["grade"] == {"verdict": "plausible", "reason": RD.SECOND_TEST_HELD_AGAIN_REASON}
    assert any(d["kind"] == "second-test-held-again" for d in state["decisions"])
    assert "_secondTestPass" not in state and "_secondTestHeld" not in state
    assert state["step"] != RD.P_SECOND_TEST
    row = state[SC.DISPOSITION_LEDGER_KEY][0]
    assert "disposition" not in row and row["grade"]["verdict"] == "plausible"


# ---- F3, edge 9 -----------------------------------------------------------------------------------------------

def test_f3_pass_two_stages_its_ids_afresh_so_a_grouping_covering_both_findings_is_accepted(tmp_path):
    # bites on: the fresh re-staging of pass 2's `_verified` (G3)
    r = Round(tmp_path, plain=[_PLAIN], first={_HELD["title"]: _MISSED, _PLAIN["title"]: _PLAUSIBLE},
              second={_HELD["title"]: _MISSED})
    n = r.drive(stop=RD.P_SYNTHESIS)
    state = r.state()
    findings = n["payload"]["findings"]
    ids = [f["id"] for f in findings]
    assert sorted(f["title"] for f in findings) == sorted([_HELD["title"], _PLAIN["title"]])
    assert len(ids) == len(set(ids)) == 2, ids
    assert [f["id"] for f in state["_verified"]] == ids
    grouping = [{"group_id": "g0", "member_ids": list(ids)}]
    assert V._valid_grouping(state["_verified"], grouping) is not None
    s = RD.cmd_submit(r.dir, n["phase"], n["attempt"], n["expectedStateHash"], {"grouping": grouping})
    assert s["ok"], s
    after = r.state()
    assert after["step"] != RD.P_SYNTHESIS
    assert {f["title"] for f in after["findings"]} == {_HELD["title"], _PLAIN["title"]}


def test_edge9_pass_one_drops_and_grades_are_written_once_and_not_rewritten_in_pass_two(tmp_path):
    third = dict(_PLAIN, title="refuted defect", line=1)
    r = Round(tmp_path, plain=[_PLAIN, third],
              first={_HELD["title"]: _MISSED, _PLAIN["title"]: _PLAUSIBLE,
                     third["title"]: {"verdict": "REFUTED", "reason": "already guarded"}},
              second={_HELD["title"]: _SECOND_REFUTED})
    r.to_second_test()
    mid = r.state()
    kept_grade = r.row(_PLAIN["title"], mid)["grade"]
    refuted = r.row(third["title"], mid)
    assert kept_grade == {"verdict": "plausible", "reason": "could not run it"}
    assert refuted["disposition"] == "refuted" and refuted["grade"]["verdict"] == "wrong"
    r.drive()
    state = r.state()
    assert r.row(_PLAIN["title"], state)["grade"] == kept_grade
    assert r.row(third["title"], state)["grade"] == refuted["grade"]
    assert r.row(state=state)["grade"] == {"verdict": "wrong", "reason": _SECOND_REASON}
    # the round's verify record keeps pass 1's drop beside pass 2's
    assert [d["reason"] for d in state["rounds"]["1"]["verify"]["drops"]] == ["already guarded", _SECOND_REASON]


# ---- F4 -------------------------------------------------------------------------------------------------------

def test_f4_the_kept_check_reads_the_second_test_as_the_findings_latest(tmp_path, monkeypatch):
    # bites on: the round-history append of the second run (G4)
    r = Round(tmp_path)
    n = r.to_second_test()
    r.submit(n, r.second_result(n["payload"]))
    state = r.state()
    RD._record_disposition(state, _key(), "fixed", 1)
    checked = []

    def check_kept(repo_root, base, head, run, **kwargs):
        checked.append(run)
        return {"outcome": break_it.KEPT, "path": run.get("path"), "reason": None, "run": run}

    monkeypatch.setattr(break_it, "check_kept", check_kept)
    assert RD._break_it_kept_step(state, state["config"]) is False
    assert [run["path"] for run in checked] == [SECOND_PATH]


# ---- U: the unseatable seat -----------------------------------------------------------------------------------

def _verifier_only_seat_map():
    """Claude is barred as a maker, and codex is proven live only on its verifier cell: the verifiers can be
    seated, the second-test seat (a reviewer-deep cell) cannot."""
    seat_map = S1858._seat_map("anthropic", ("anthropic",), ("codex",))
    cell = model_registry.matrix_config("verifier", "codex")
    seat_map["nonPanelLiveCells"] = [["codex", cell[0], cell[1]]]
    return seat_map


def test_u_an_unseatable_second_test_seat_emits_no_order_and_the_held_finding_is_graded_in_pass_two(tmp_path):
    # bites on: the unseatable branch (G5)
    r = Round(tmp_path, second={_HELD["title"]: _SECOND_REFUTED}, fixer="cursor",
              seat_map=_verifier_only_seat_map())
    r.drive()
    state = r.state()
    assert RD._nonpanel_unseatable(state, r.dir, RD.P_SECOND_TEST) is True
    assert RD._nonpanel_unseatable(state, r.dir, RD.P_VERIFIERS) is False
    assert RD.P_SECOND_TEST not in r.seen and r.seen.count(RD.P_VERIFIERS) == 2, r.seen
    assert not glob.glob(os.path.join(r.dir, "round-1", "orders", RD.P_SECOND_TEST, "*"))
    rec = state["rounds"]["1"]
    assert rec["secondTestUnseatable"] == [{"makerFamilies": ["anthropic"], "fixerVendor": "cursor",
                                            "held": [_key()]}]
    assert [d["kind"] for d in state["decisions"] if d["kind"].startswith("second-test")] == [
        "second-test-held", "second-test-unseatable"]
    # no new test: pass 2 judges the finding on the test it has, marked `secondTest`
    (pass_two,) = [f for c in r.verifier_payloads[1]["clusters"] for f in c["findings"]]
    assert pass_two["secondTest"] is True and pass_two["suggestion"] == _FIRST
    assert [x["test"] for x in pass_two[break_it.RUNS_FIELD]] == [FIRST_PATH]
    assert len(rec["breakItRuns"]) == 1
    row = r.row(state=state)
    assert row["disposition"] == "refuted" and row["grade"]["verdict"] == "wrong"
    # the receipt discloses it
    degraded = RD.build_receipt(state)["degraded"]
    assert any(line.startswith("second-test-unseatable (round 1)") for line in degraded), degraded


def test_u_a_seatable_second_test_seat_discloses_nothing(tmp_path):
    r = Round(tmp_path, second={_HELD["title"]: _SECOND_REFUTED})
    r.drive()
    state = r.state()
    assert RD.P_SECOND_TEST in r.seen
    assert "secondTestUnseatable" not in state["rounds"]["1"]
    assert not any("second-test-unseatable" in line for line in RD.build_receipt(state)["degraded"])


# ---- M: a result that supplies no test ------------------------------------------------------------------------

def _round_two_after(tmp_path, results):
    """A session submitted the second-test results ``results`` (a function of the payload); returns the state
    and the round."""
    r = Round(tmp_path, second_result=results)
    n = r.to_second_test()
    r.submit(n, r.second_result(n["payload"]))
    return r.state(), r


def test_m_a_held_finding_with_no_matching_result_goes_to_pass_two_with_no_test_and_the_other_id_unmatched(tmp_path):
    state, r = _round_two_after(tmp_path, lambda payload: [
        {"id": "v99", "title": "stranger", "file": "f.py", "line": 1, "severity": "Important",
         "consequence": _CONSEQUENCE, "suggestion": _SECOND}])
    second = state["rounds"]["1"]["secondTest"]
    assert second["noTest"] == [{"findingKey": _key(), "reason": "no-result"}]
    assert second["unmatched"] == ["v99"] and second["ran"] == []
    assert [f["title"] for f in state["_toVerify"]] == [_HELD["title"]]  # nothing was taken from the stranger
    staged = state["_toVerify"][0]
    assert staged["secondTest"] is True and staged["suggestion"] == _FIRST
    assert len(state["rounds"]["1"]["breakItRuns"]) == 1
    assert state["step"] == RD.P_VERIFIERS and state["_secondTestPass"] is True


def test_m_a_result_with_no_block_goes_to_pass_two_with_no_test(tmp_path):
    state, r = _round_two_after(tmp_path, lambda payload: [
        dict(e, suggestion="I could not write a test that reaches it") for e in Round._default_result(payload)])
    assert state["rounds"]["1"]["secondTest"]["noTest"] == [{"findingKey": _key(), "reason": "no-block"}]
    assert state["_toVerify"][0]["suggestion"] == _FIRST and len(state["rounds"]["1"]["breakItRuns"]) == 1


def test_m_a_duplicate_id_gives_no_new_test(tmp_path):
    state, r = _round_two_after(tmp_path, lambda payload: Round._default_result(payload) * 2)
    assert state["rounds"]["1"]["secondTest"]["noTest"] == [{"findingKey": _key(), "reason": "duplicate-id"}]
    assert state["_toVerify"][0]["suggestion"] == _FIRST and len(state["rounds"]["1"]["breakItRuns"]) == 1


def test_m_a_result_never_overwrites_the_finding_beyond_its_test(tmp_path):
    state, r = _round_two_after(tmp_path, lambda payload: [
        dict(e, title="renamed", file="elsewhere.py", line=1, severity="Nit", consequence="nothing")
        for e in Round._default_result(payload)])
    staged = state["_toVerify"][0]
    assert (staged["title"], staged["file"], staged["line"], staged["severity"]) == (
        _HELD["title"], "f.py", 2, "Important")
    assert staged["suggestion"] == _SECOND


def test_m_a_second_test_the_runner_cannot_run_is_still_appended_and_the_finding_goes_to_pass_two(tmp_path):
    # edge 6: a `run` the loop refuses (a shell chain) is a block, so it is run and recorded not-run
    chained = "break-it-test v1\npath: %s\nrun: true && true\n---\nx\n" % SECOND_PATH
    state, r = _round_two_after(tmp_path, lambda payload: [
        dict(e, suggestion=chained) for e in Round._default_result(payload)])
    runs = state["rounds"]["1"]["breakItRuns"]
    assert [(x["path"], x["outcome"]) for x in runs] == [(FIRST_PATH, "passed"), (SECOND_PATH, "not-run")]
    assert state["rounds"]["1"]["secondTest"]["ran"] == [{"findingKey": _key(), "outcome": "not-run"}]
    staged = state["_toVerify"][0]
    assert staged["secondTest"] is True and state["step"] == RD.P_VERIFIERS


def test_m_a_missing_second_test_seat_result_is_the_adapters_refuse_fold():
    # edge 4
    assert RA.missing_policy(RP.P_SECOND_TEST) == RA.MISSING_REFUSE_FOLD
    assert RA.missing_policy(RP.P_SECOND_TEST) == RA.missing_policy(RP.P_GAPSWEEP)
    assert RA._SINGLE_SEAT[RP.P_SECOND_TEST] == RA.SEAT_SECOND_TEST == "second-test"


def test_m_a_park_while_held_closes_nothing(tmp_path):
    # edge 8
    r = Round(tmp_path)
    r.to_second_test()
    state = r.state()
    assert "disposition" not in r.row(state=state)
    RD._park_cannot_certify(state, "parked while a finding was held")
    assert state["terminal"] == "cannot-certify"
    # the terminal settles every open finding as still open, never as fixed or refuted, and grades none
    row = r.row(state=state)
    assert row.get("disposition") not in ("fixed", "refuted") and "grade" not in row
    assert [f["title"] for f in state["_toVerify"]] == [_HELD["title"]]


# ---- S: the strict verdicts schema ----------------------------------------------------------------------------

def test_s_the_strict_verdicts_schema_lists_path_reached_required_and_nullable():
    items = ERC._branch_payload_schema("verdicts")["items"]
    assert items["additionalProperties"] is False
    assert "pathReached" in items["required"]
    assert items["properties"]["pathReached"]["type"] == ["boolean", "null"]
    assert sorted(items["required"]) == sorted(items["properties"])


def test_s_the_verdict_contract_accepts_a_boolean_path_reached_and_refuses_any_other():
    seat = "verifier:f.py:0"
    base = {"verdicts": [{"id": "v0", "verdict": "PLAUSIBLE", "reason": "r"}]}
    assert PC.payload_fault(RP.P_VERIFIERS, base, seat) is None
    for ok in (True, False):
        assert PC.payload_fault(RP.P_VERIFIERS, {"verdicts": [dict(base["verdicts"][0], pathReached=ok)]}, seat) is None
    for bad in ("false", 0, [], {}):
        fault = PC.payload_fault(RP.P_VERIFIERS, {"verdicts": [dict(base["verdicts"][0], pathReached=bad)]}, seat)
        assert fault is not None, bad


def test_s_the_second_test_contract_is_the_gap_sweeps():
    assert PC.payload_fault(RP.P_SECOND_TEST, {"findings": []}, RA.SEAT_SECOND_TEST) is None
    assert PC.payload_fault(RP.P_SECOND_TEST, {}, RA.SEAT_SECOND_TEST) is not None
    assert PC.payload_fault(RP.P_SECOND_TEST, {"findings": [], "reviewerVendor": "claude"},
                            RA.SEAT_SECOND_TEST) is None
    assert RA.payload_contract(RP.P_SECOND_TEST) == RA.payload_contract(RP.P_GAPSWEEP)


# ---- C: the census --------------------------------------------------------------------------------------------

def test_c_the_new_phase_is_named_at_every_site_that_names_gap_sweep():
    phase = RP.P_SECOND_TEST
    assert phase == "dispatch-second-test"
    assert phase in RP.ALL_PHASES and phase in RO.ORDER_PHASES
    assert phase in PC.ADAPTER_PHASES and phase in RA.ADAPTER_PHASES
    assert SC.RUN_KIND_BY_PHASE[phase] == SC.RUN_KIND_BY_PHASE[RP.P_GAPSWEEP]
    assert phase in RD._NONPANEL_REVIEWER_PHASES
    assert RD._NONPANEL_PHASE_ROLE[phase] == RD._NONPANEL_PHASE_ROLE[RP.P_GAPSWEEP] == "reviewer-deep"
    assert RA._SINGLE_SEAT[phase] == "second-test"
    assert phase in PC._PAYLOAD_CHECKERS
    with open(os.path.join(_HERE, "fixtures", "orders", "clause_manifest.json"), encoding="utf-8") as fh:
        assert json.load(fh)[phase]
    assert os.path.isfile(RO.order_template_path(phase))


def test_c_every_decision_kind_the_fold_writes_is_registered():
    state = RD.new_state(TRD._cfg())
    for kind in ("second-test-held", "second-test-held-again", "second-test-unseatable"):
        assert kind in decision_kinds.DECISION_KINDS
        RD._decision(state, kind, "registered")  # an unregistered kind raises
    assert [d["kind"] for d in state["decisions"]] == [
        "second-test-held", "second-test-held-again", "second-test-unseatable"]


def test_c_the_unseatable_degradation_is_a_carried_channel_the_verifier_fold_records():
    assert receipt_disclosures.CARRIED_DISCLOSURE_CHANNELS["secondTestUnseatable"] is receipt_disclosures.dict_list
    assert "secondTestUnseatable" in RD.VERIFIER_FOLD_DISCLOSURE_CHANNELS
    # `secondTest` stays in the round state: the review record and the decisions carry it
    assert "secondTest" not in receipt_disclosures.CARRIED_DISCLOSURE_CHANNELS


def test_c_the_reviewer_header_names_the_second_test_seat():
    assert review_record._STEM_ROLE["second-test "] == "second test"
    assert "second test" in review_record._ROLE_ORDER
    assert review_record._ROLE_ORDER.index("second test") > review_record._ROLE_ORDER.index("gap sweep")


def test_c_the_second_test_seat_is_a_pre_fix_seat_but_not_a_raw_finder():
    assert RP.P_SECOND_TEST in rs._PRE_FIX_PHASES
    assert RP.P_SECOND_TEST not in rs._RAW_PHASES
