"""The round driver makes each round's landing folders before it hands back an order (#1913).

Whenever the driver hands a caller a pending step whose phase is a seat dispatch or `run-verify`,
`round-<N>/landing/<phase>/` already exists — and so does the parent of the verify gate's advertised
`landingPath` — so no host seat and no hand-run command writes into a missing directory.

Bite-proof: neutralize the phase branch of `RD._ensure_landing_folders` (E-B1) and the fresh-dispatch,
re-emit and standalone run-verify tests go red; neutralize its `landingPath` branch (E-B2) and the
audits verify-gate test goes red.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import test_round_driver_advance as TRA  # noqa: E402
from session_checkout import enter_checkout  # noqa: E402

RD = TRA.RD
RR = TRA.RR


def _landing_dir(d, rnd, phase):
    return RR.landing_dir(d, rnd, phase)


def _audits_pending(verify_path, verify_round=1):
    return {"action": RD.P_AUDITS, "round": 1, "phase": RD.P_AUDITS, "attempt": 0,
            "payload": {"verify": {"round": verify_round, "attempt": 0, "landingPath": verify_path}}}


def test_a_fresh_dispatch_step_has_its_landing_folder(tmp_path):
    d = TRA._session(tmp_path)
    p = TRA._pending(d)
    assert p["phase"].startswith("dispatch-")
    assert os.path.isdir(_landing_dir(d, p["round"], p["phase"]))


def test_a_re_emitted_step_recreates_its_landing_folder(tmp_path):
    d = TRA._session(tmp_path)
    p = TRA._pending(d)
    folder = _landing_dir(d, p["round"], p["phase"])
    os.rmdir(folder)
    assert not os.path.exists(folder)
    out = RD.cmd_next(d)
    assert out["ok"], out
    assert (out["round"], out["phase"]) == (p["round"], p["phase"])
    assert os.path.isdir(folder)


def test_a_standalone_run_verify_step_has_its_landing_folder(tmp_path):
    d = TRA._session(tmp_path)
    enter_checkout(os.path.join(os.path.dirname(d), "checkout"))
    state = TRA._state(d)
    state["step"] = RD.P_VERIFY
    state["pending"] = None
    RD.save_state(d, state)
    rnd = state["round"]
    assert not os.path.exists(_landing_dir(d, rnd, RD.P_VERIFY))
    out = RD.cmd_next(d)
    assert out["ok"], out
    assert out["phase"] == RD.P_VERIFY and out["round"] == rnd
    assert os.path.isdir(_landing_dir(d, rnd, RD.P_VERIFY))
    assert not os.path.exists(os.path.join(d, "round-%d" % rnd, "landing", RD.P_AUDITS))


def test_the_audits_verify_gate_landing_folder_exists(tmp_path):
    d = TRA._session(tmp_path)
    path = RR.bare_payload_path(d, 1, RD.P_VERIFY, RR.storage_key("verify"), 0)
    assert not os.path.exists(os.path.dirname(path))
    out = RD._next_response(d, TRA._state(d), _audits_pending(path), "next")
    assert out["ok"], out
    assert os.path.isdir(os.path.dirname(path))


def test_a_terminal_step_makes_no_landing_folder(tmp_path):
    d = TRA._session(tmp_path)
    pending = {"action": "terminal", "round": 1, "phase": "terminal", "attempt": 0, "payload": {}}
    out = RD._next_response(d, TRA._state(d), pending, "next")
    assert out["ok"], out
    assert not os.path.exists(_landing_dir(d, 1, "terminal"))


def test_a_non_int_round_makes_no_landing_folder_and_raises_nothing(tmp_path):
    d = TRA._session(tmp_path)
    for rnd in (None, True, "1"):
        pending = {"action": "dispatch-x", "round": rnd, "phase": "dispatch-x", "attempt": 0, "payload": {}}
        assert RD._next_response(d, TRA._state(d), pending, "next")["ok"]
    assert not os.path.exists(_landing_dir(d, 1, "dispatch-x"))


def test_a_foreign_verify_landing_path_is_not_created(tmp_path):
    d = TRA._session(tmp_path)
    foreign = str(tmp_path / "elsewhere" / "verify.a0.payload.json")
    out = RD._next_response(d, TRA._state(d), _audits_pending(foreign), "next")
    assert out["ok"], out
    assert not os.path.exists(os.path.dirname(foreign))
