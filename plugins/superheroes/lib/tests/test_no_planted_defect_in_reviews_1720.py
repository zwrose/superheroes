#!/usr/bin/env python3
"""#1720 — no review dispatch hands a reviewer a planted defect, and no old probe file is read."""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
_PLUGIN = os.path.dirname(_LIB)
_REPO = os.path.dirname(os.path.dirname(_PLUGIN))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from session_checkout import seed_session_meta  # noqa: E402

import round_driver as RD  # noqa: E402
import round_records  # noqa: E402

from test_engine_dispatch import (  # noqa: E402
    ED, FakeRunner, _VALID_FINDINGS_STDOUT, _codex_seat, _fake_build_view, _repo, _valid_prompt,
)
from test_panel_diff_at_head_1419 import (  # noqa: E402
    _commit_file, _init_two_commit_repo,
)
from test_round_driver import (  # noqa: E402
    _cfg, _drive_to_phase, _responder,
)

_A_FINDING = [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]
_FORBIDDEN_TEXT = ("verify_submission", "planted", "canary")
_RETIRED_RECORD_KEYS = frozenset((
    "canaryUnverified", "canaryFailed", "canaryOutcomeFailed", "canaryPlantUndetected",
    "canaryVerified", "controlProbe", "canaryResult",
))
_REVIEWER_FACING = (RD.P_PANEL, RD.P_VERIFIERS, RD.P_SCOPED)
_OLD_PROBE_RESULT = {
    "engine": "codex", "outcome": "ok", "engaged": True, "detectedPlant": True,
    "evidence": {}, "detail": "left by an older version",
}


def _all_keys(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield key
            yield from _all_keys(value)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            yield from _all_keys(item)


def _plant_old_probe_file(session_dir):
    probe_dir = os.path.join(
        round_records.round_dir(session_dir, 1), "landing", "dispatch-panel", "_canary")
    os.makedirs(probe_dir, exist_ok=True)
    path = os.path.join(probe_dir, "codex.a1.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(_OLD_PROBE_RESULT, fh)
    return path


def _drive_full_lane_review(base, leave_old_probe_file):
    """Drive one fixture full-lane review to its terminal.

    Returns (terminal next, reviewer-facing payloads seen, session dir, planted path or None)."""
    base.mkdir()
    repo, base_sha, diff_commit1 = _init_two_commit_repo(base)
    session = str(base / "session")
    seed_session_meta(session, repo)
    cfg = _cfg(verifyCommand="pytest -q", diff=diff_commit1, repoRoot=repo, baseRef=base_sha)
    seen = []

    def respond(phase, payload, rnd):
        if phase == RD.P_FIXER and rnd == 1:
            _commit_file(repo, "f.py", "fixed head\n", "fixer commit")
            return {"fixes": [{"file": "f.py"}], "changedSubjects": ["Code"]}
        return _responder(round1_findings=_A_FINDING)(phase, payload, rnd)

    n = _drive_to_phase(session, cfg, respond, RD.P_PANEL)
    planted = _plant_old_probe_file(session) if leave_old_probe_file else None
    for _ in range(80):
        if n["action"] == RD.P_TERMINAL:
            return n, seen, session, planted
        if n["phase"] in _REVIEWER_FACING:
            seen.append((n["phase"], n["payload"]))
        s = RD.cmd_submit(session, n["phase"], n["attempt"], n["expectedStateHash"],
                          respond(n["phase"], n["payload"], n["round"]))
        assert s["ok"], s
        n = RD.cmd_next(session)
        assert n["ok"], n
    raise AssertionError("driver did not reach a terminal within 80 steps")


def test_full_lane_fixture_review_hands_no_reviewer_a_planted_defect(tmp_path):
    terminal, seen, session, planted = _drive_full_lane_review(tmp_path / "with", True)
    control_terminal, _control_seen, _control_session, _ = _drive_full_lane_review(
        tmp_path / "without", False)

    # the fixture really exercised the reviewer-facing phases
    phases = {phase for phase, _payload in seen}
    assert RD.P_PANEL in phases and RD.P_VERIFIERS in phases, phases

    # (i) no reviewer-facing payload carries a planted defect
    for phase, payload in seen:
        text = json.dumps(payload)
        for needle in _FORBIDDEN_TEXT:
            assert needle not in text, (phase, needle)

    # (ii) no order or prompt file the driver wrote carries one either
    planted_real = os.path.realpath(planted)
    walked = 0
    for root, _dirs, files in os.walk(session):
        for name in files:
            path = os.path.join(root, name)
            if os.path.realpath(path) == planted_real or not os.path.isfile(path):
                continue
            with open(path, "rb") as fh:
                text = fh.read().decode("utf-8", errors="replace")
            walked += 1
            for needle in _FORBIDDEN_TEXT:
                assert needle not in text, (path, needle)
    assert walked > 0
    with open(planted, encoding="utf-8") as fh:
        assert json.load(fh) == _OLD_PROBE_RESULT

    # (iii) the round records and the terminal receipt carry no retired probe key
    ok, state = RD.load_state(session)
    assert ok and state
    with open(os.path.join(session, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    assert state["rounds"] and receipt
    for label, doc in (("rounds", state["rounds"]), ("state", state),
                       ("receipt", receipt), ("terminal", terminal["payload"])):
        assert not (set(_all_keys(doc)) & _RETIRED_RECORD_KEYS), label

    # (iv) the old probe file changes nothing about how the review ends
    assert terminal["payload"]["verdict"]
    assert terminal["payload"]["verdict"] == control_terminal["payload"]["verdict"]


def test_single_reviewer_fixture_review_hands_the_reviewer_no_planted_defect(tmp_path):
    repo_root = _repo(tmp_path)
    build_view = _fake_build_view(tmp_path)
    base_body = "Review this code.\n"
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    result = ED.dispatch_review(
        seat=_codex_seat(),
        prompt_path=_valid_prompt(tmp_path, base_body), repo_root=repo_root, run_engine=fake,
        build_view=build_view,
    )
    assert len(fake.calls) == 1
    text = fake.calls[0]["prompt_bytes"].decode("utf-8")
    assert base_body in text
    for needle in ("verify_submission", "fails open on any error", "planted"):
        assert needle not in text, needle
    assert not ({"canaryResult", "controlProbe", "detectedPlant"} & set(_all_keys(result)))


def test_no_shipped_python_names_the_retired_control():
    retired = ("seat_canary", "canary_outcome")
    this_file = os.path.realpath(__file__)
    roots = (
        os.path.join(_PLUGIN, "lib"),
        os.path.join(_PLUGIN, "eval"),
        os.path.join(_REPO, ".github", "scripts"),
    )
    scanned = 0
    for top in roots:
        assert os.path.isdir(top), top
        for root, _dirs, files in os.walk(top):
            for name in files:
                path = os.path.join(root, name)
                if not name.endswith(".py") or os.path.realpath(path) == this_file:
                    continue
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
                scanned += 1
                for needle in retired:
                    assert needle not in text, (path, needle)
    assert scanned > 0
    for name in ("seat_canary.py", "canary_outcome.py"):
        assert not os.path.exists(os.path.join(_PLUGIN, "lib", name)), name
