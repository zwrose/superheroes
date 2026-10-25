"""#2072 (layer 3 of #2053): CI on the exact head is a sanctioned stand-in for a local verify the
environment cannot run.

A `run-verify` payload may carry `via: "ci-exact-head"` with the CI run it rests on. The SHAPE is
checked by `round_phases.verify_result_fault` (one home, so hand submit, bare-payload advance and the
payload contract all get it); the RUN is checked at the one submit chokepoint, `round_driver.cmd_submit`,
against the run fetched through `round_driver._fetch_ci_run` — monkeypatched here, so no test reaches
the network. Every refusal names exactly one token, is journalled, and leaves `state.json` untouched.
"""
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import test_round_driver_advance as TA  # noqa: E402
from test_round_driver_advance import adapters  # noqa: E402,F401  (a fixture)
from test_review_record_session import Fake, Session, extras  # noqa: E402

import payload_contracts  # noqa: E402
import receipt_disclosures  # noqa: E402
import review_record_session as rs  # noqa: E402
import round_phases  # noqa: E402

RD = TA.RD
RR = TA.RR
SHA = "b" * 40
OTHER_SHA = "c" * 40
RUN_ID = "39773254322"


def _ci(**over):
    ci = {"workflow": "CI", "runId": RUN_ID, "headSha": SHA, "conclusion": "success"}
    ci.update(over)
    return {k: v for k, v in ci.items() if v is not _MISSING}


_MISSING = object()


def _payload(**over):
    payload = {"result": "pass", "via": "ci-exact-head", "ci": _ci(),
               "reason": "the verify command needs a database this environment lacks"}
    payload.update(over)
    return {k: v for k, v in payload.items() if v is not _MISSING}


def _run(head=SHA, **over):
    run = {"id": int(RUN_ID), "name": "CI", "head_sha": head, "status": "completed",
           "conclusion": "success"}
    run.update(over)
    return {k: v for k, v in run.items() if v is not _MISSING}


# =============================================================================================
# the shape — pure, one home
# =============================================================================================

def _shape(payload):
    return round_phases.verify_result_fault(payload)


def _is_shape_fault(payload):
    fault = _shape(payload)
    return isinstance(fault, str) and fault.startswith("ci-verify-shape:")


def test_a_well_formed_ci_exact_head_payload_has_no_shape_fault():
    assert _shape(_payload()) is None


def test_run_id_may_be_an_integer_or_a_digit_string_and_head_sha_may_be_64_hex():
    assert _shape(_payload(ci=_ci(runId=39773254322))) is None
    assert _shape(_payload(ci=_ci(runId="7"))) is None
    assert _shape(_payload(ci=_ci(headSha="f" * 64))) is None
    assert _shape(_payload(ci=_ci(headSha="A" * 40))) is None


@pytest.mark.parametrize("payload", [{"result": "pass"}, {"result": "pass", "via": "local"},
                                     {"result": "fail", "via": "local", "command": "make test"}],
                         ids=["no-via", "via-local", "via-local-fail"])
def test_a_local_verify_has_no_shape_fault(payload):
    assert _shape(payload) is None


@pytest.mark.parametrize("via", ["remote", "CI-EXACT-HEAD", "", 1, None, ["ci-exact-head"], True],
                         ids=["unknown", "wrong-case", "empty", "int", "none", "list", "bool"])
def test_edge1_an_unknown_or_non_string_via_is_a_shape_fault(via):
    assert _is_shape_fault(_payload(via=via))


@pytest.mark.parametrize("result", ["fail", "skipped", "timeout", "none", "unverified"])
def test_edge2_ci_exact_head_stands_in_only_for_a_pass(result):
    assert _is_shape_fault(_payload(result=result))


def test_edge3_ci_missing_or_not_an_object_is_a_shape_fault():
    assert _is_shape_fault(_payload(ci=_MISSING))
    for bad in ("CI", ["CI"], None, 5):
        assert _is_shape_fault(_payload(ci=bad)), bad


@pytest.mark.parametrize("field", ["workflow", "conclusion"])
@pytest.mark.parametrize("bad", [_MISSING, "", "  ", None, 5, ["x"]], ids=[
    "missing", "empty", "blank", "none", "int", "list"])
def test_edge3_each_string_ci_field_must_be_a_non_empty_string(field, bad):
    assert _is_shape_fault(_payload(ci=_ci(**{field: bad})))


@pytest.mark.parametrize("bad", [_MISSING, 0, -3, "0", "-3", "abc", "12a", "", " 12", 1.5, None, True,
                                 "١٢٣", ["1"]],
                         ids=["missing", "zero", "negative", "zero-str", "negative-str", "alpha",
                              "mixed", "empty", "padded", "float", "none", "bool", "unicode-digits",
                              "list"])
def test_edge3_run_id_must_be_a_positive_integer_or_digit_string(bad):
    assert _is_shape_fault(_payload(ci=_ci(runId=bad)))


@pytest.mark.parametrize("bad", [_MISSING, "", "abc1234", "b" * 7, "b" * 39, "b" * 41, "b" * 63,
                                 "g" * 40, "b" * 39 + "z", None, 5, ["b" * 40]],
                         ids=["missing", "empty", "short-abbrev", "seven", "thirtynine", "fortyone",
                              "sixtythree", "non-hex", "non-hex-tail", "none", "int", "list"])
def test_edge3_head_sha_must_be_40_or_64_hex(bad):
    assert _is_shape_fault(_payload(ci=_ci(headSha=bad)))


@pytest.mark.parametrize("bad", [_MISSING, "", "   ", None, 5, ["why"]],
                         ids=["missing", "empty", "blank", "none", "int", "list"])
def test_edge4_reason_must_be_a_non_empty_string(bad):
    assert _is_shape_fault(_payload(reason=bad))


@pytest.mark.parametrize("payload", [
    {"result": "pass", "ci": _ci()},
    {"result": "pass", "reason": "why"},
    {"result": "pass", "ci": _ci(), "reason": "why"},
    {"result": "pass", "via": "local", "ci": _ci()},
    {"result": "pass", "via": "local", "reason": "why"},
], ids=["ci-only", "reason-only", "both", "local-with-ci", "local-with-reason"])
def test_edge5_no_evidence_rides_a_local_verify(payload):
    assert _is_shape_fault(payload)


def test_a_bad_result_token_keeps_its_own_fault_not_the_ci_one():
    fault = _shape(_payload(result="banana"))
    assert fault and not fault.startswith("ci-verify-shape:")


def test_the_payload_contract_accepts_the_new_fields_and_delegates_shape():
    contract = payload_contracts._PAYLOAD_CONTRACTS[RD.P_VERIFY]
    assert {"via", "ci", "reason"} <= set(contract["optional"])
    assert (contract["types"]["via"], contract["types"]["ci"], contract["types"]["reason"]) == (
        "string", "object", "string")
    assert payload_contracts._verify_payload_fault(_payload(), "verify") is None
    fault = payload_contracts._verify_payload_fault(_payload(ci=_ci(headSha="abc")), "verify")
    assert fault and fault.startswith("ci-verify-shape:")
    assert payload_contracts._verify_payload_fault(_payload(ci="CI"), "verify")


# =============================================================================================
# the three paths to the chokepoint
# =============================================================================================

class _Fetch(object):
    """The `_fetch_ci_run` seam: returns what the test set, counts its calls, never touches gh."""

    def __init__(self):
        self.calls = []
        self.result = (_run(), None)
        self.raises = None

    def __call__(self, repo_root, run_id):
        self.calls.append((repo_root, run_id))
        if self.raises is not None:
            raise self.raises
        return self.result


@pytest.fixture
def fetch(monkeypatch):
    seam = _Fetch()
    monkeypatch.setattr(RD, "_fetch_ci_run", seam)
    import review_record
    monkeypatch.setattr(review_record, "_ci_workflow", lambda repo_root: ("declared", "CI"))
    return seam


@pytest.fixture
def real_verify_assembly(adapters):  # noqa: F811
    """The durable-seat path assembles through the REAL `_assemble_verify`: the stand-in adapter only
    routes to it, so what the seat's payload carries is decided by production code."""
    real = TA._load("round_adapters")
    stub_assemble = adapters.assemble

    def assemble(phase, envelopes, state, config, dispatch_manifest=None, session_dir=None,
                 orders_manifest=None):
        if phase != RD.P_VERIFY:
            return stub_assemble(phase, envelopes, state, config, dispatch_manifest, session_dir,
                                 orders_manifest)
        for env in envelopes or []:
            if isinstance(env, dict) and env.get("schema") != RR.SEAT_MISSING_SCHEMA:
                return real._assemble_verify(["verify"], {("verify", 0): env}, {}), None
        return None, "missing-verify"

    adapters.assemble = assemble
    return adapters


PATHS = ["hand", "bare", "seat"]


class _World(object):
    """One session parked at `run-verify`, driven to the fold by `path`."""

    def __init__(self, tmp_path, path):
        self.path, self.tmp_path = path, tmp_path
        self.d = TA._session(tmp_path)
        TA._at_run_verify(tmp_path, self.d)
        state = TA._state(self.d)
        if path == "hand":
            state.pop("_advanceUsed", None)
            RD.save_state(self.d, state)
        self.head = RD._verified_head_at_fold(self.d, TA._state(self.d))[0]
        assert self.head and len(self.head) == 40
        self.landed = False

    def state_bytes(self):
        with open(os.path.join(self.d, RD.STATE_FILE), "rb") as fh:
            return fh.read()

    def submit(self, payload):
        if self.path == "hand":
            pend = TA._pending(self.d)
            return RD.cmd_submit(self.d, pend["phase"], pend["attempt"],
                                 RD.state_hash(TA._state(self.d)), payload)
        if self.path == "bare":
            TA._write_verify_payload(self.d, payload)
        elif not self.landed:
            TA._land_and_record(self.d, "verify", payload=payload)
            self.landed = True
        return TA._advance(self.d, self.tmp_path)

    def submit_local(self, command="make test"):
        """A local verify that passed: a hand submit on the hand path; on the advance paths the
        driver's own `run-verify` verb runs the command and lands the result (#2133)."""
        if self.path == "hand":
            return self.submit({"result": "pass", "command": command, "exit": 0})
        TA._land_verify_via_verb(self.d, command=command, as_record=self.path == "seat")
        self.landed = self.path == "seat"
        return TA._advance(self.d, self.tmp_path)

    def folded(self, out):
        return out.get("ok") is True and TA._state(self.d)["rounds"]["1"].get("verifyResult") == "pass"

    def via(self):
        return TA._state(self.d)["rounds"]["1"].get("verifyVia")


@pytest.fixture(params=PATHS)
def world(request, tmp_path, real_verify_assembly, fetch):
    w = _World(tmp_path, request.param)
    fetch.result = (_run(head=w.head), None)
    w.good = _payload(ci=_ci(headSha=w.head))
    return w


def _token(out):
    """The refusal token: `cmd_submit` answers it as `reason`; `advance` wraps every refused fold as
    `fold-refused` and carries the submit's reason in `detail`."""
    return out["detail"] if out["reason"] == "fold-refused" else out["reason"]


def test_an_accepted_ci_exact_head_payload_folds_pass_and_records_which_verify(world, fetch):
    out = world.submit(world.good)
    assert world.folded(out), out
    assert world.via() == {"via": "ci-exact-head", "workflow": "CI", "runId": RUN_ID,
                           "headSha": world.head, "conclusion": "success",
                           "reason": world.good["reason"]}
    assert len(fetch.calls) == 1 and fetch.calls[0][1] == RUN_ID
    assert os.path.realpath(fetch.calls[0][0]) == fetch.calls[0][0]


def test_an_integer_run_id_folds_and_is_recorded_as_a_string(world):
    out = world.submit(_payload(ci=_ci(headSha=world.head, runId=int(RUN_ID))))
    assert world.folded(out), out
    assert world.via()["runId"] == RUN_ID


def test_a_sha_mismatch_twin_is_refused_on_every_path(world, fetch):
    fetch.result = (_run(head=OTHER_SHA), None)
    out = world.submit(_payload(ci=_ci(headSha=OTHER_SHA)))
    assert out["ok"] is False and _token(out) == "ci-verify-sha-mismatch", out
    assert TA._state(world.d)["rounds"]["1"].get("verifyResult") is None
    assert TA._pending(world.d)["phase"] == RD.P_VERIFY


def test_a_local_verify_never_calls_the_fetch_seam_and_records_it_local(world, fetch):
    out = world.submit_local("make test")
    assert world.folded(out), out
    assert fetch.calls == []
    assert world.via() == {"via": "local", "command": "make test"}


def test_a_local_verify_without_a_command_records_the_configured_one(tmp_path, adapters, fetch):
    d = TA._session(tmp_path, verifyCommand="make verify")
    TA._at_run_verify(tmp_path, d)
    state = TA._state(d)
    state.pop("_advanceUsed", None)
    RD.save_state(d, state)
    pend = TA._pending(d)
    out = RD.cmd_submit(d, pend["phase"], pend["attempt"], RD.state_hash(TA._state(d)),
                        {"result": "pass"})
    assert out.get("ok") is True, out
    assert TA._state(d)["rounds"]["1"]["verifyVia"] == {"via": "local", "command": "make verify"}
    assert fetch.calls == []


# --- the refusals, all on the hand path (the three-path twin above covers the wiring) ----------

def _hand(tmp_path, fetch, adapters):  # noqa: F811
    w = _World(tmp_path, "hand")
    fetch.result = (_run(head=w.head), None)
    w.good = _payload(ci=_ci(headSha=w.head))
    return w


def _refused(w, payload, token):
    """The whole refusal contract: one named token, journalled, state byte-identical, pending alive,
    and a corrected resubmit (the same payload against a matching run) folds."""
    before = w.state_bytes()
    out = w.submit(payload)
    assert out["ok"] is False and out["reason"] == token, out
    assert "detail" in out and out["detail"]
    assert w.state_bytes() == before, "a refused submit mutated loop-state"
    assert TA._pending(w.d)["phase"] == RD.P_VERIFY
    assert not TA._state(w.d).get("terminal")
    assert TA._journal(w.d)[-1].get("outcome") == token
    return out


def test_edge6_a_failed_fetch_is_unreadable(tmp_path, adapters, fetch):
    w = _hand(tmp_path, fetch, adapters)
    fetch.result = (None, "gh api exited 1")
    out = _refused(w, w.good, "ci-verify-run-unreadable")
    assert "gh api exited 1" in out["detail"]


def test_edge6_a_raising_fetch_is_unreadable(tmp_path, adapters, fetch):
    w = _hand(tmp_path, fetch, adapters)
    fetch.raises = RuntimeError("timed out")
    _refused(w, w.good, "ci-verify-run-unreadable")


@pytest.mark.parametrize("missing", ["id", "name", "head_sha", "status", "conclusion"])
def test_edge6_a_run_lacking_any_required_field_is_unreadable(tmp_path, adapters, fetch, missing):
    w = _hand(tmp_path, fetch, adapters)
    fetch.result = (_run(head=w.head, **{missing: _MISSING}), None)
    _refused(w, w.good, "ci-verify-run-unreadable")


def test_edge6_a_non_dict_run_is_unreadable(tmp_path, adapters, fetch):
    w = _hand(tmp_path, fetch, adapters)
    fetch.result = (["not", "a", "run"], None)
    _refused(w, w.good, "ci-verify-run-unreadable")


def test_edge7_a_head_resolution_error_is_unreadable_and_never_compared(tmp_path, adapters, fetch,
                                                                         monkeypatch):
    w = _hand(tmp_path, fetch, adapters)
    monkeypatch.setattr(RD, "_verified_head_at_fold", lambda session_dir, state: (None, "no head"))
    # the fetched run claims the very `None`-ish head a careless compare would accept
    fetch.result = (_run(head=None), None)
    out = _refused(w, _payload(ci=_ci(headSha=w.head)), "ci-verify-run-unreadable")
    assert "no head" in out["detail"]
    assert fetch.calls == []


def test_edge7_an_unresolvable_repo_root_is_unreadable(tmp_path, adapters, fetch, monkeypatch):
    w = _hand(tmp_path, fetch, adapters)
    monkeypatch.setattr(RD, "_resolve_repo_root", lambda session_dir, state: None)
    _refused(w, w.good, "ci-verify-run-unreadable")
    assert fetch.calls == []


def test_edge8_fetched_head_differs_from_the_verified_head_though_the_claim_matches_it(
        tmp_path, adapters, fetch):
    w = _hand(tmp_path, fetch, adapters)
    fetch.result = (_run(head=OTHER_SHA), None)
    out = _refused(w, _payload(ci=_ci(headSha=OTHER_SHA)), "ci-verify-sha-mismatch")
    assert w.head in out["detail"]


def test_edge8_claimed_head_differs_from_the_fetched_head(tmp_path, adapters, fetch):
    w = _hand(tmp_path, fetch, adapters)
    # the run IS on the verified head; the claim names another commit
    _refused(w, _payload(ci=_ci(headSha=OTHER_SHA)), "ci-verify-sha-mismatch")


def test_edge8_an_uppercase_claim_of_the_verified_head_is_accepted(tmp_path, adapters, fetch):
    w = _hand(tmp_path, fetch, adapters)
    out = w.submit(_payload(ci=_ci(headSha=w.head.upper())))
    assert out["ok"] is True, out


def test_edge8_an_uppercase_claim_of_a_different_commit_is_still_refused(tmp_path, adapters, fetch):
    w = _hand(tmp_path, fetch, adapters)
    _refused(w, _payload(ci=_ci(headSha=OTHER_SHA.upper())), "ci-verify-sha-mismatch")


def test_edge8_fetched_id_differs_from_the_claimed_run_id(tmp_path, adapters, fetch):
    w = _hand(tmp_path, fetch, adapters)
    fetch.result = (_run(head=w.head, id=int(RUN_ID) + 1), None)
    _refused(w, w.good, "ci-verify-sha-mismatch")


def test_edge8_an_integer_claimed_run_id_matches_the_integer_fetched_id(tmp_path, adapters, fetch):
    w = _hand(tmp_path, fetch, adapters)
    out = w.submit(_payload(ci=_ci(headSha=w.head, runId=int(RUN_ID))))
    assert w.folded(out), out


def test_edge9_fetched_workflow_differs_from_the_claimed_workflow(tmp_path, adapters, fetch):
    w = _hand(tmp_path, fetch, adapters)
    fetch.result = (_run(head=w.head, name="pr-title"), None)
    _refused(w, w.good, "ci-verify-workflow-mismatch")


@pytest.mark.parametrize("kind", ["absent", "unreadable"])
def test_an_undeclared_ci_workflow_is_refused_before_the_fetch(tmp_path, adapters, fetch, monkeypatch, kind):
    import review_record
    w = _hand(tmp_path, fetch, adapters)
    monkeypatch.setattr(review_record, "_ci_workflow", lambda repo_root: (kind, None))
    _refused(w, w.good, "ci-verify-workflow-unconfigured")
    assert fetch.calls == []


def test_a_claimed_workflow_other_than_the_declared_one_is_refused(tmp_path, adapters, fetch):
    w = _hand(tmp_path, fetch, adapters)
    fetch.result = (_run(head=w.head, name="pr-title"), None)
    _refused(w, _payload(ci=_ci(headSha=w.head, workflow="pr-title")), "ci-verify-workflow-mismatch")


def test_a_claimed_workflow_other_than_the_declared_one_is_refused_before_the_fetch(
        tmp_path, adapters, fetch):
    w = _hand(tmp_path, fetch, adapters)
    # the fetch would return the declared `CI` run, so the fetched-run checks cannot tell the claim
    # is wrong by token alone; only the claim check ahead of the fetch keeps the fetch from happening
    _refused(w, _payload(ci=_ci(headSha=w.head, workflow="pr-title")), "ci-verify-workflow-mismatch")
    assert fetch.calls == []


def test_edge10_a_run_still_in_progress_is_a_conclusion_mismatch(tmp_path, adapters, fetch):
    w = _hand(tmp_path, fetch, adapters)
    # conclusion agrees with the claim, so only the status check can refuse it
    fetch.result = (_run(head=w.head, status="in_progress"), None)
    _refused(w, w.good, "ci-verify-conclusion-mismatch")


def test_edge10_a_claimed_conclusion_the_run_does_not_have_is_refused(tmp_path, adapters, fetch):
    w = _hand(tmp_path, fetch, adapters)
    # the run succeeded; only the claim differs, so only the claim-vs-run check can refuse it
    _refused(w, _payload(ci=_ci(headSha=w.head, conclusion="neutral")), "ci-verify-conclusion-mismatch")


def test_edge10_a_failed_run_claimed_as_failure_is_still_not_a_stand_in(tmp_path, adapters, fetch):
    w = _hand(tmp_path, fetch, adapters)
    fetch.result = (_run(head=w.head, conclusion="failure"), None)
    out = _refused(w, _payload(ci=_ci(headSha=w.head, conclusion="failure")),
                   "ci-verify-conclusion-mismatch")
    assert "not success" in out["detail"]


def test_edge10_a_claimed_success_the_run_failed_is_refused(tmp_path, adapters, fetch):
    w = _hand(tmp_path, fetch, adapters)
    fetch.result = (_run(head=w.head, conclusion="failure"), None)
    _refused(w, w.good, "ci-verify-conclusion-mismatch")


def test_the_checks_run_in_order_the_first_failing_one_names_the_refusal(tmp_path, adapters, fetch):
    w = _hand(tmp_path, fetch, adapters)
    # sha, workflow and conclusion all disagree: the sha refusal wins
    fetch.result = (_run(head=OTHER_SHA, name="pr-title", conclusion="failure", status="queued"), None)
    _refused(w, w.good, "ci-verify-sha-mismatch")
    # workflow and conclusion both disagree: the workflow refusal wins
    fetch.result = (_run(head=w.head, name="pr-title", conclusion="failure"), None)
    _refused(w, w.good, "ci-verify-workflow-mismatch")
    # unreadable beats everything
    fetch.result = (_run(head=OTHER_SHA, name=_MISSING), None)
    _refused(w, w.good, "ci-verify-run-unreadable")


@pytest.mark.parametrize("path", PATHS)
def test_edge11_a_refusal_leaves_state_alone_and_a_corrected_resubmit_folds(
        tmp_path, real_verify_assembly, fetch, path):
    w = _World(tmp_path, path)
    good = _payload(ci=_ci(headSha=w.head))
    fetch.result = (_run(head=OTHER_SHA), None)
    before = w.state_bytes()
    out = w.submit(good)
    assert out["ok"] is False and _token(out) == "ci-verify-sha-mismatch", out
    assert w.state_bytes() == before
    # `advance` journals its own `refused` row after the submit's
    assert "ci-verify-sha-mismatch" in [e.get("outcome") for e in TA._journal(w.d)]
    fetch.result = (_run(head=w.head), None)
    out = w.submit(good)
    assert w.folded(out), out
    assert w.via()["via"] == "ci-exact-head"


@pytest.mark.parametrize("path", PATHS)
def test_a_shape_fault_is_refused_on_every_path_before_any_fetch(
        tmp_path, real_verify_assembly, fetch, path):
    w = _World(tmp_path, path)
    out = w.submit(_payload(ci=_ci(headSha="abc")))
    assert out["ok"] is False and _token(out).startswith("ci-verify-shape:"), out
    assert fetch.calls == []
    assert TA._pending(w.d)["phase"] == RD.P_VERIFY


def test_edge12_a_local_verify_never_calls_the_seam_even_when_it_would_raise(tmp_path, adapters, fetch):
    w = _hand(tmp_path, fetch, adapters)
    fetch.raises = AssertionError("a local verify must not fetch")
    out = w.submit({"result": "pass"})
    assert w.folded(out), out
    assert fetch.calls == []


# =============================================================================================
# the fetch seam itself
# =============================================================================================

class _Done(object):
    def __init__(self, returncode=0, stdout=b"", stderr=b""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def _stub_run(monkeypatch, result):
    seen = {}

    def run(argv, **kw):
        seen["argv"], seen["kw"] = argv, kw
        if isinstance(result, Exception):
            raise result
        return result
    monkeypatch.setattr(RD.subprocess, "run", run)
    return seen


def test_the_fetch_seam_runs_gh_api_with_an_argv_list_and_a_timeout(monkeypatch):
    seen = _stub_run(monkeypatch, _Done(stdout=json.dumps(_run()).encode()))
    run, err = RD._fetch_ci_run("/repo", RUN_ID)
    assert err is None and run["id"] == int(RUN_ID)
    assert seen["argv"] == ["gh", "api", "repos/{owner}/{repo}/actions/runs/%s" % RUN_ID]
    assert seen["kw"]["cwd"] == "/repo" and seen["kw"]["timeout"] == 60
    assert seen["kw"]["capture_output"] is True and not seen["kw"].get("shell")
    assert seen["kw"].get("stdin") is RD.subprocess.DEVNULL


@pytest.mark.parametrize("result", [
    _Done(returncode=1, stderr=b"HTTP 404"), _Done(stdout=b"<html>"), _Done(stdout=b"[1]"),
    OSError("no gh"), __import__("subprocess").TimeoutExpired("gh", 60)],
    ids=["nonzero", "non-json", "non-object", "oserror", "timeout"])
def test_the_fetch_seam_reports_every_failure_as_a_reason(monkeypatch, result):
    _stub_run(monkeypatch, result)
    run, err = RD._fetch_ci_run("/repo", RUN_ID)
    assert run is None and isinstance(err, str) and err


# =============================================================================================
# the record, the receipt line and the review record
# =============================================================================================

CI_VIA = {"via": "ci-exact-head", "workflow": "CI", "runId": RUN_ID, "headSha": SHA,
          "conclusion": "success", "reason": "no database here"}


def test_verify_via_is_a_carried_channel_with_one_census_home():
    assert RD.VERIFY_FOLD_DISCLOSURE_CHANNELS == ("verifyVia",)
    shape_ok = receipt_disclosures.CARRIED_DISCLOSURE_CHANNELS["verifyVia"]
    assert shape_ok(CI_VIA) and shape_ok({"via": "local", "command": "make test"})
    assert not shape_ok([CI_VIA]) and not shape_ok("ci-exact-head") and not shape_ok({"x": 1})
    assert receipt_disclosures.declared_disclosures({"verifyVia": CI_VIA}) == {"verifyVia": CI_VIA}


def _degraded(via):
    state = {"config": {}, "rounds": {"2": {"verifyVia": via}}}
    prose, _ = receipt_disclosures.build_degraded_prose(state, receipt_disclosures.RECEIPT_FORM_CERTIFIED)
    return [line for line in prose if line.startswith("verify-via-ci")]


def test_the_receipt_names_a_ci_verify_round_and_says_nothing_of_a_local_one():
    assert _degraded(CI_VIA) == [
        "verify-via-ci (round 2): CI workflow CI run %s on %s (success) stood in for the local "
        "verify command: no database here" % (RUN_ID, SHA[:7])]
    assert _degraded({"via": "local", "command": "make test"}) == []


def test_the_review_record_names_the_verify_used(tmp_path):
    s = Session(tmp_path, rounds={"1": {"verifyVia": {"via": "local", "command": "make test"}},
                                  "2": {"verifyVia": CI_VIA}, "3": {}})
    s.seat("code-reviewer")
    account = rs.account_from_session(s.save(), extras(checked=["ran the suite"]),
                                       Fake().readers())
    assert [c for c in account["checked"] if c.startswith("Verify in round")] == [
        "Verify in round 2: CI workflow CI run %s on %s passed, in place of the local verify "
        "command (no database here)" % (RUN_ID, SHA[:7])]
    assert "ran the suite" in account["checked"]
