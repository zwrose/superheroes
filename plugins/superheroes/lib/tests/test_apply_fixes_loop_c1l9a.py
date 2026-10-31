"""A whole review, round 1 to a converged terminal, where the build session applies the fix itself.

Round 1's panel raises one finding that carries an attached break-it test; the verifiers confirm it; synthesis
follows; the driver sets `apply-fixes`; the session makes a real commit holding the fix and the test and reports
it bound to the finding; the verify gate runs; round 2's audit discharges the fix; the review converges.

H is the hand path: `next` / `submit`.
D is the durable-record path: the report lands as a bare payload and `advance` folds it.
"""
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _path in (_HERE, _LIB):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import test_apply_fixes_c1l9a as H  # noqa: E402

RD = H.RD
TRD = H.TRD


@pytest.fixture(autouse=True)
def _pinned_git(monkeypatch, tmp_path):
    for name in ("home", "xdg-config"):
        (tmp_path / name).mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _no_order_dir(session):
    for phase in (RD.P_APPLY_FIXES, "dispatch-fixer"):
        assert not os.path.exists(os.path.join(session, "round-1", "orders", phase)), phase


def test_h_a_full_loop_by_hand_applies_the_fix_in_the_build_session(tmp_path):
    fx = H.Fixture(tmp_path)
    session = str(fx.session)
    n = fx.reach()
    key = fx.keys()[0]
    assert os.path.dirname(n["payload"]["landingPath"]) == RD.round_records.landing_dir(
        session, 1, RD.P_APPLY_FIXES)
    sha = fx.commit_fix()
    out = fx.submit(H._bound(key, sha))
    assert out["ok"] is True and out["foldLanded"] is True, out
    payload = TRD._drive_cli(session, None, fx.respond)
    assert payload["verdict"] == "converged", payload
    ok, state = RD.load_state(session)
    assert ok
    _no_order_dir(session)
    assert state["rounds"]["1"]["fix"]["commits"] == [{"finding": key, "commit": sha}]
    assert state["rounds"]["1"]["fixReportedKeys"] == [key]
    # the commit is the session's own: it carries the fix and the test together
    assert sorted(H.git(fx.repo, "show", "--name-only", "--format=", sha).splitlines()) == [
        H.CHARGE_PATH, H.TEST_PATH]
    accepted = [e for e in RD.read_journal(session)
                if e.get("phase") == RD.P_APPLY_FIXES and e.get("outcome") == "accepted"]
    assert len(accepted) == 1
    (kept,) = [r for rec in state["rounds"].values() for r in rec.get("breakItKept") or []]
    assert kept["outcome"] == H.break_it.KEPT


def test_d_the_durable_record_path_folds_a_bare_landing_through_advance(tmp_path):
    fx = H.Fixture(tmp_path)
    session = str(fx.session)
    n = fx.reach()
    key = fx.keys()[0]
    # the steps before this one were folded by hand, which latches `advance` off; the fixture lifts the latch
    # so that this one step takes the durable-record path
    state = fx.state()
    state.pop("_submitUsed", None)
    RD.save_state(session, state)
    n = RD.cmd_next(session)
    landing = n["payload"]["landingPath"]
    fx.commit_fix()
    sha = H.git(fx.repo, "rev-parse", "HEAD")

    # a landing that names no commit for the test-carrying finding is refused, and the step stays pending
    with open(landing, "w") as fh:
        json.dump({"fixes": ["fixed it"]}, fh)
    refused = RD.cmd_advance(session)
    assert refused["ok"] is False and refused["reason"] == "fold-refused", refused
    assert refused["detail"] == "%s:%s:no-binding" % (H.NO_TEST, key)
    assert RD.cmd_next(session)["attempt"] == n["attempt"]

    with open(landing, "w") as fh:
        json.dump({"fixes": [{"finding": key, "commit": sha}]}, fh)
    out = RD.cmd_advance(session)
    assert out["ok"] is True and out["folded"] == {"phase": RD.P_APPLY_FIXES, "round": 1,
                                                    "attempt": n["attempt"]}, out
    ok, after = RD.load_state(session)
    assert ok and after["rounds"]["1"]["fix"]["commits"] == [{"finding": key, "commit": sha}]
    _no_order_dir(session)
    record, err = RD.round_records.read_json(RD.round_records.store_path(
        session, 1, RD.P_APPLY_FIXES, RD.round_records.storage_key("apply-fixes"), n["attempt"]))
    assert err is None and record["provenance"] == RD.round_records.PROVENANCE_ORCHESTRATOR_FULFILLED
    assert record["payload"] == {"fixes": [{"finding": key, "commit": sha}]}
