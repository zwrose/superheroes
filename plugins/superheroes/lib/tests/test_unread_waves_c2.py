"""Nothing a slice reviewer left unread goes unreviewed.

On a sliced round 1, every part of the change that a slice seat was given and did not list as read becomes a new slice
with the same seats any slice gets, in the same round, before the seams check and the verifiers. The waves are bounded,
whatever is still unread at the bound is recorded and shown, and the record's unread share is always filled on a sliced
change. Each seat is held to its own read list: a test seat that read nothing leaves its slice unread however much the
code seat of that slice read.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/c2_wo4b_unread_waves.md
"""
import copy
import hashlib
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import countable_lines as cl  # noqa: E402
import review_record as rr  # noqa: E402
import review_record_session as rs  # noqa: E402
import round_driver as RD  # noqa: E402
import round_phases as RP  # noqa: E402
from test_review_record_session import Fake, Session, extras, put_envelope  # noqa: E402
from test_sliced_panel_c2 import (  # noqa: E402,F401  (`_pin_git` is an autouse fixture)
    BAR, OTHER, PAYMENTS, RISK_AREAS, _added, _git, _pin_git, _placeholders, _read, _repo, _risk_diff, _session_dir,
    _slice_ids, _state, _three_thousand,
)

NOTHING = "nothing"
CONSEQUENCE = "a reviewer-found defect stays in the change"
FIRST = "pkg/f0.py"


def _finding(title, file=FIRST, line=5):
    return {"title": title, "severity": "Important", "consequence": CONSEQUENCE, "file": file, "line": line}


def _slice(state, slice_id):
    return next(s for s in state["slicePlan"]["slices"] if s["id"] == slice_id)


def _wave(state, reads=None, findings=None, omit=()):
    """Fold one panel wave over the state's current roster and return the seats submitted. A slice seat reads its whole slice
    unless ``reads`` is ``NOTHING`` (every slice seat reads nothing) or names a list for that seat. ``findings`` maps a seat to
    its findings; ``omit`` names seats left out of the submit."""
    roster = RP.panel_roster(state, state["config"])
    seats = {}
    for key in roster:
        if key in omit:
            continue
        payload = {"findings": list((findings or {}).get(key, []))}
        if RP.is_slice_seat(key):
            if reads == NOTHING:
                payload["readParts"] = []
            elif isinstance(reads, dict) and key in reads:
                payload["readParts"] = copy.deepcopy(reads[key])
            else:
                payload["readParts"] = copy.deepcopy(_slice(state, key.partition(":")[2])["parts"])
        seats[key] = payload
    RD._fold(state, state["config"], RD.P_PANEL, {"seats": seats})
    return seats


def _titles(state):
    return sorted(f["title"] for f in state.get("_toVerify") or [])


# --- the waves -----------------------------------------------------------------------------------------------------

def test_when_every_slice_seat_reads_its_whole_slice_there_is_no_second_wave_and_the_seams_check_follows(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    _wave(state)
    assert state["step"] == RD.P_SEAMS
    assert state["unreadShare"] == {"unreadLines": 0, "countableLines": state["slicePlan"]["countable"], "parts": []}
    assert "_sliceWave" not in state and "_sliceWaveRoster" not in state
    assert _slice_ids(state) == ["s1", "s2", "s3"]
    assert "unread-after-waves" not in [d["kind"] for d in state["decisions"]]


def test_a_test_seat_that_read_nothing_opens_a_second_wave_over_its_slice_though_its_code_seat_read_everything(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    sdir = _session_dir(tmp_path)
    _wave(state, reads={"test-role:s2": []})
    assert state["step"] == RD.P_PANEL and state["_sliceWave"] == 2
    assert not state.get("_toVerify") and "unreadShare" not in state
    roster = RP.panel_roster(state, state["config"])
    assert "code-reviewer:w2u1" in roster and "test-role:w2u1" in roster
    assert not [k for k in roster if k.endswith(":s1") or k.endswith(":s2") or k.endswith(":s3")]
    assert "architecture-reviewer" not in roster
    new = _slice(state, "w2u1")
    assert new["parts"] == _slice(state, "s2")["parts"] and "diff" not in new and new["wave"] == 2
    payload = RD._advance(state, state["config"])["payload"]
    assert payload["dimensions"] == roster
    assert [s["id"] for s in payload["slices"]] == ["w2u1"]
    ph = _placeholders(state, sdir, "test-role:w2u1")
    assert {s["file"] for s in cl.parse_sections(_read(ph["DIFF_PATH"]))} == {"pkg/f1.py"}
    assert ph["SLICE_SCOPE_LINE"].startswith("Your slice: w2u1. Review only these parts of the change")
    _wave(state)
    assert state["step"] == RD.P_SEAMS and state["unreadShare"]["parts"] == []


def test_an_unread_part_that_touches_a_risk_area_gets_a_security_seat_and_one_premortem_seat_over_the_whole_change(tmp_path):
    state = _state(_repo(tmp_path, RISK_AREAS), _risk_diff())
    sdir = _session_dir(tmp_path)
    touching = next(s for s in state["slicePlan"]["slices"] if any(p["file"] == PAYMENTS for p in s["parts"]))
    sid = touching["id"]
    _wave(state, reads={"%s:%s" % (lens, sid): [] for lens in RP.SLICED_LENSES})
    assert state["step"] == RD.P_PANEL
    assert RP.panel_roster(state, state["config"]) == [
        "code-reviewer:w2u1", "test-role:w2u1", "security-reviewer:w2u1", "premortem-reviewer:w2"]
    assert _slice(state, "w2u1")["security"] is True
    assert RP.seat_lens("premortem-reviewer:w2") == "premortem-reviewer"
    ph = _placeholders(state, sdir, "premortem-reviewer:w2")
    assert ph["DIFF_PATH"] == os.path.join(sdir, "round-1", "diff.txt")
    assert _read(ph["DIFF_PATH"]) == _risk_diff()
    assert ph["SLICE_SCOPE_LINE"].startswith("Read the whole change. Make sure your read list covers these parts too: ")
    assert PAYMENTS in ph["SLICE_SCOPE_LINE"] and OTHER not in ph["SLICE_SCOPE_LINE"]
    sec = _placeholders(state, sdir, "security-reviewer:w2u1")
    assert PAYMENTS in sec["SLICE_SCOPE_LINE"] and sec["SLICE_SCOPE_LINE"].startswith("Your slice: w2u1.")
    _wave(state)
    assert state["step"] == RD.P_SEAMS


def test_an_unread_part_with_a_clear_risk_gets_no_security_seat_and_no_premortem_wave_seat(tmp_path):
    state = _state(_repo(tmp_path, RISK_AREAS), _risk_diff())
    clear = next(s for s in state["slicePlan"]["slices"] if s["security"] is False)
    sid = clear["id"]
    _wave(state, reads={"code-reviewer:" + sid: [], "test-role:" + sid: []})
    assert state["step"] == RD.P_PANEL
    assert RP.panel_roster(state, state["config"]) == ["code-reviewer:w2u1", "test-role:w2u1"]
    assert _slice(state, "w2u1")["security"] is False
    assert PAYMENTS not in {p["file"] for p in _slice(state, "w2u1")["parts"]}


def test_the_waves_stop_at_the_bound_and_what_is_still_unread_is_recorded_with_every_waves_findings_staged_once(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    _wave(state, reads={"test-role:s1": []}, findings={"code-reviewer:s1": [_finding("wave one bug")]})
    assert state["step"] == RD.P_PANEL and state["_sliceWave"] == 2
    _wave(state, reads=NOTHING, findings={"code-reviewer:w2u1": [_finding("wave two bug", line=6)]})
    assert state["step"] == RD.P_PANEL and state["_sliceWave"] == RD.UNREAD_WAVE_BOUND == 3
    assert RP.panel_roster(state, state["config"])[0] == "code-reviewer:w3u1"
    _wave(state, reads=NOTHING, findings={"code-reviewer:w3u1": [_finding("wave three bug", line=7)]})
    assert state["step"] == RD.P_SEAMS
    assert "_sliceWave" not in state and "_sliceCarry" not in state
    assert [i for i in _slice_ids(state) if i.startswith("w4")] == []
    share = state["unreadShare"]
    assert share["unreadLines"] > 0 and share["unreadLines"] <= share["countableLines"]
    assert [p["file"] for p in share["parts"]] == [FIRST]
    decisions = [d for d in state["decisions"] if d["kind"] == "unread-after-waves"]
    assert len(decisions) == 1 and "%d countable line(s) in 1 file(s)" % share["unreadLines"] in decisions[0]["detail"]
    RD._fold(state, state["config"], RD.P_SEAMS, {"findings": []})
    assert _titles(state) == ["wave one bug", "wave three bug", "wave two bug"]
    assert len(state["_toVerify"]) == 3


def test_unread_parts_no_slice_ever_showed_are_recorded_and_shown_not_dropped(tmp_path):
    state = _state(_repo(tmp_path), _added("pkg/one.py", 3))
    state["slicePlan"] = {"sliced": True, "countable": 3, "bar": BAR, "slices": [
        {"id": "s1", "weight": 3, "parts": [{"file": "pkg/one.py", "lines": [[1, 3]]}], "security": False}]}
    _wave(state, reads=NOTHING)
    assert state["step"] == RD.P_SEAMS and "_sliceWave" not in state
    assert state["unreadShare"] == {"unreadLines": 3, "countableLines": 3,
                                    "parts": [{"file": "pkg/one.py", "lines": [[1, 3]]}]}
    assert [d["kind"] for d in state["decisions"]].count("unread-after-waves") == 1


# --- what a copy, a lock file and the plan never owe -----------------------------------------------------------------

def test_a_proven_copy_is_named_by_no_slice_no_wave_seat_order_and_no_unread_part(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    (root / "README.md").write_bytes(b"readme\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    base = _git(root, "rev-parse", "HEAD").strip()
    copy_path = "src/vendored/copy.py"
    copy_bytes = b"".join(b"copied %d\n" % i for i in range(1, 401))
    for rel, data in ((copy_path, copy_bytes),
                      ("src/a.py", b"".join(b"a %d\n" % i for i in range(700))),
                      ("src/b.py", b"".join(b"b %d\n" % i for i in range(700)))):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "head")
    proof = {"schema": "copy-proof/1", "copies": [
        {"file": copy_path, "source": "vendor/orig.py", "sha256": hashlib.sha256(copy_bytes).hexdigest()}]}
    state = _state(root, _git(root, "diff", base + "...HEAD"), copyProof=proof)
    assert state["slicePlan"]["sliced"] is True
    sdir = _session_dir(tmp_path)
    waves = 0
    while state["step"] == RD.P_PANEL:
        waves += 1
        for key in RP.panel_roster(state, state["config"]):
            if RP.is_slice_seat(key) or key.startswith("premortem-reviewer:"):
                ph = _placeholders(state, sdir, key)
                assert copy_path not in ph["SLICE_SCOPE_LINE"] and copy_path not in _read(ph["DIFF_PATH"])
        _wave(state, reads=NOTHING)
    assert waves == RD.UNREAD_WAVE_BOUND
    for sl in state["slicePlan"]["slices"]:
        assert copy_path not in {p["file"] for p in sl["parts"]}
    share = state["unreadShare"]
    assert share["parts"] and copy_path not in {p["file"] for p in share["parts"]}


def test_a_lock_file_whose_seat_read_nothing_never_pushes_the_unread_lines_above_the_countable_lines(tmp_path):
    state = _state(_repo(tmp_path), _added("src/big.py", BAR + 200) + _added("package-lock.json", 3000))
    assert state["slicePlan"]["sliced"] is True
    _wave(state, reads=NOTHING)
    while state["step"] == RD.P_PANEL:
        _wave(state, reads=NOTHING)
    share = state["unreadShare"]
    assert "package-lock.json" in {p["file"] for p in share["parts"]}
    assert share["unreadLines"] <= share["countableLines"]
    assert share["unreadLines"] == BAR + 200


# --- the round's record ----------------------------------------------------------------------------------------------

def test_a_later_waves_fold_adds_to_the_first_waves_seat_status_coverage_and_review_record(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    first = _wave(state, reads={"test-role:s2": []})
    first_keys = set(first)
    status = dict(state["rounds"]["1"]["seatStatus"])
    assert set(status) == first_keys and set(status.values()) == {"run"}
    second = _wave(state)
    second_keys = set(second)
    rec = state["rounds"]["1"]
    assert set(rec["seatStatus"]) == first_keys | second_keys and not first_keys & second_keys
    assert all(rec["seatStatus"][k] == "run" for k in rec["seatStatus"])
    assert rec["lensCoverage"] == {"ran": len(first_keys) + len(second_keys),
                                   "expected": len(first_keys) + len(second_keys), "floor": False}
    assert state["fullPanelRan"] is True and state["_incompletePanel"] is False
    (record,) = [r for r in state["_records"] if r["round"] == 1]
    assert set(record["dimensions"]) == first_keys | second_keys


def test_full_panel_ran_is_true_only_when_every_waves_seats_ran(tmp_path):
    early = _state(_repo(tmp_path), _three_thousand())
    _wave(early, reads={"test-role:s2": []}, omit=("code-reviewer:s3",))
    assert early["fullPanelRan"] is False
    _wave(early)
    assert early["fullPanelRan"] is False and early["_incompletePanel"] is True
    assert early["rounds"]["1"]["seatStatus"]["code-reviewer:s3"] == "missing"
    assert early["rounds"]["1"]["lensCoverage"]["floor"] is True
    sub = tmp_path / "b"
    sub.mkdir()
    late = _state(_repo(sub), _three_thousand())
    _wave(late, reads={"test-role:s2": []})
    assert late["fullPanelRan"] is True
    _wave(late, omit=("test-role:w2u1",))
    assert late["fullPanelRan"] is False
    assert late["rounds"]["1"]["seatStatus"]["test-role:w2u1"] == "missing"
    assert late["rounds"]["1"]["seatStatus"]["code-reviewer:s1"] == "run"


def test_the_account_built_from_a_two_wave_session_carries_the_unread_share_and_every_seats_own_read_list(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    first = _wave(state, reads={"test-role:s2": []})
    second = _wave(state)
    assert state["unreadShare"]["parts"] == []
    session = Session(tmp_path, rounds=state["rounds"], unreadShare=state["unreadShare"])
    for attempt, seats in ((0, first), (1, second)):
        for key in seats:
            session.seat(key, attempt=attempt)
    path = session.save()
    for attempt, seats in ((0, first), (1, second)):
        for key, payload in seats.items():
            put_envelope(path, key, {"vendor": "codex", "model": "m", "payload": payload}, attempt=attempt)
    account = rs.account_from_session(path, extras(), Fake().readers())
    assert account["unreadShare"] == state["unreadShare"]
    rows = {r["name"]: r for r in account["reviewers"]}
    assert len(account["reviewers"]) == len(first) + len(second) == len(rows)
    for key, payload in {**first, **second}.items():
        row = rows["%s (round 1)" % key]
        if RP.is_slice_seat(key):
            assert row["readParts"] == payload["readParts"], key
    assert rows["test-role:s2 (round 1)"]["readParts"] == []
    assert rows["code-reviewer:s2 (round 1)"]["readParts"] == _slice(state, "s2")["parts"]
    assert rows["test-role:w2u1 (round 1)"]["readParts"] == _slice(state, "s2")["parts"]
    built = rr.build_record(account, Fake().readers())
    assert built is not None


# --- what stays as it was ------------------------------------------------------------------------------------------

def test_round_two_of_a_sliced_session_never_opens_an_unread_wave(tmp_path):
    state = _state(_repo(tmp_path), _three_thousand())
    _wave(state)
    RD._fold(state, state["config"], RD.P_SEAMS, {"findings": []})
    share = copy.deepcopy(state["unreadShare"])
    slices = copy.deepcopy(state["slicePlan"]["slices"])
    state["round"] = 2
    state["step"] = RD.P_PANEL
    dims = RP.panel_roster(state, state["config"])
    assert dims == RP.panel_dimensions(state["config"])
    RD._fold(state, state["config"], RD.P_PANEL, {"seats": {d: {"findings": [], "readParts": []} for d in dims}})
    assert state["step"] == RD.P_VERIFIERS and "_sliceWave" not in state
    assert state["slicePlan"]["slices"] == slices and state["unreadShare"] == share


def test_an_unsliced_session_has_no_unread_share_and_goes_straight_to_the_verifiers(tmp_path):
    state = _state(_repo(tmp_path), _added("pkg/one.py", 3))
    roster = RP.panel_roster(state, state["config"])
    RD._fold(state, state["config"], RD.P_PANEL, {"seats": {d: {"findings": [], "readParts": []} for d in roster}})
    assert state["step"] == RD.P_VERIFIERS
    assert "unreadShare" not in state and "_sliceWave" not in state and "_sliceWaves" not in state


@pytest.mark.parametrize("key,slice_seat", [
    ("code-reviewer:s1", True), ("test-role:w2u3", True), ("security-reviewer:w3u1", True),
    ("premortem-reviewer:w2", False), ("premortem-reviewer", False), ("architecture-reviewer", False)])
def test_only_a_lens_colon_slice_key_is_a_slice_seat(key, slice_seat):
    assert RP.is_slice_seat(key) is slice_seat
