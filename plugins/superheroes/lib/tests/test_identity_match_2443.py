"""Issue 2443: the review loop matches a superseded slot and a stalled finding by their FULL identity.

Part 1 — `round_driver._attest_roster` labels a pending-phase slot `superseded` only for a
driver-journal row marked superseded that names that same slot: phase, round, attempt, seat and
occurrence. A row from another phase, round, attempt or twin slot never labels it, so a missing seat
is never hidden behind a superseded row of the same seat elsewhere.

Part 3 — `circuit_breaker.check_audit_breaker` counts DISTINCT stalled findings (by the audit
target's `id`) in its `detail`, never the union of every alias a finding carries.

Each part has a test that fails on the base code and passes after, its healthy sibling, and one test
per fail-closed edge. Bite-proof record: `bite_proofs/i2443_identity_match.md`.
"""
import importlib.util
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
from fake_adapters import FakeAdapters  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")
RR = _load("round_records")
import circuit_breaker as CB  # noqa: E402

DIFF = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
        "@@ -1 +1,2 @@\n-old\n+new\n+more\n")
_CONSEQUENCE = "a reviewer-found defect stays in the change"
SEAT_MAP = {"seats": {dim: {"vendor": "claude", "model": "sonnet-5.5", "engine": "claude"}
                      for dim in RD.DIMENSIONS}}
STALL_PREFIX = "%d finding(s) failed audit in two consecutive rounds: %s"


# =============================================================================================
# Part 1 — session helpers (modelled on test_round_driver_advance.py)
# =============================================================================================

@pytest.fixture
def adapters(monkeypatch):
    fake = FakeAdapters()
    monkeypatch.setitem(sys.modules, "round_adapters", fake)
    return fake


def _cfg(**over):
    base = {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF, "fixerVendor": "claude",
            "seatMap": SEAT_MAP}
    base.update(over)
    return base


def _session(tmp_path, name="s"):
    d = str(tmp_path / name)
    os.makedirs(d, exist_ok=True)
    out = RD.cmd_next(d, _cfg())
    assert out["ok"], out
    return d


def _state(session_dir):
    ok, state = RD.load_state(session_dir)
    assert ok, state
    return state


def _pending(session_dir):
    return _state(session_dir)["pending"]


def _session_id(session_dir):
    with open(os.path.join(session_dir, RR.META_FILE), encoding="utf-8") as fh:
        return json.load(fh)["sessionId"]


def _anchor_hashes(session_dir, rnd, phase, attempt, seat, occurrence=0):
    anchor = RD._orders_anchor(_state(session_dir), session_dir, rnd, phase, attempt)
    if anchor is None:
        return RR.NOT_EMITTED, RR.NOT_EMITTED
    skey = RR.storage_key(seat, occurrence)
    return anchor["manifestSha256"], (anchor.get("orders") or {}).get(skey, RR.NOT_EMITTED)


def _execution_evidence():
    return {
        "source": "runner", "runnerNonce": "nonce-1", "recordDigest": "digest-1",
        "resultKind": "findings", "resultDigest": RR.payload_sha256([]),
        "observation": {"tokens": None, "toolCalls": None, "stdoutBytes": 0, "wallSeconds": 0.0,
                        "source": "none", "read": "unknown", "telemetry": "none"},
    }


def _payload(seat, tag=None):
    payload = {"findings": [], "confidence": "high", "seat": seat,
               "verificationReceipt": {"ran": True}}
    if tag is not None:
        payload["findings"] = [tag]
    return payload


def _land(session_dir, seat, payload=None, occurrence=0):
    """Write a seat's envelope into the LANDING area (what the host does)."""
    pend = _pending(session_dir)
    payload = _payload(seat) if payload is None else payload
    manifest_sha, order_sha = _anchor_hashes(session_dir, pend["round"], pend["phase"],
                                             pend["attempt"], seat, occurrence=occurrence)
    schema = RR.seat_result_schema_for_state_version(_state(session_dir).get("schemaVersion"))
    if schema is None:
        schema = RR.SEAT_RESULT_SCHEMA
    env = {
        "schema": schema, "session": _session_id(session_dir), "round": pend["round"],
        "phase": pend["phase"], "seat": seat, "attempt": pend["attempt"], "vendor": "claude",
        "model": "sonnet-5.5", "dispatchRef": manifest_sha, "orderSha256": order_sha,
        "manifestSha256": manifest_sha, "recordedAt": "2026-08-07T00:00:00",
        "payloadSha256": RR.payload_sha256(payload), "payload": payload,
    }
    if schema == RR.SEAT_RESULT_SCHEMA_V2:
        evidence = _execution_evidence()
        env["executionEvidence"] = evidence
        env["provenance"] = RR.PROVENANCE_HAND_LANDED
        env["envelopeSha256"] = RR.envelope_sha256(payload, evidence)
    if occurrence:
        env["occurrence"] = occurrence
    path = RR.landing_path(session_dir, pend["round"], pend["phase"],
                           RR.storage_key(seat, occurrence), pend["attempt"])
    RR.atomic_write_json(path, env)
    return path, env


def _land_and_record(session_dir, seat, payload=None, occurrence=0):
    _land(session_dir, seat, payload=payload, occurrence=occurrence)
    out = RD.cmd_record_result(session_dir, seat, occurrence=occurrence)
    assert out["ok"], out
    return out


_ABSENT = object()
SEAT = "code-reviewer"
OTHER_SEAT = "test-role"


def _journal_row(session_dir, **over):
    """One driver-journal row marked superseded that names (by default) the pending slot of `SEAT`.
    `_attest_roster` reads only `superseded` and the slot-identity keys; a key set to `_ABSENT` is
    left out of the row. The default row names the pending phase, round and attempt, occurrence 0."""
    pend = _pending(session_dir)
    fields = {"phase": pend["phase"], "round": pend["round"], "attempt": pend["attempt"],
              "seat": SEAT, "occurrence": 0, "superseded": True}
    fields.update(over)
    fields = {k: v for k, v in fields.items() if v is not _ABSENT}
    RD._journal_event(session_dir, "record-result", "noted", **fields)


def _roster(session_dir):
    return RD._attest_roster(session_dir, _state(session_dir))


def _recorded_session(tmp_path, adapters, name="s", seats=(SEAT,)):
    d = _session(tmp_path, name)
    for seat in seats:
        _land_and_record(d, seat)
    return d


def _twin_session(tmp_path, adapters, name="twin"):
    """A pending panel whose roster names `SEAT` twice: two slots, `SEAT` and `SEAT#1`, both recorded."""
    adapters.rosters[RD.P_PANEL] = [SEAT, SEAT]
    d = _session(tmp_path, name)
    _land_and_record(d, SEAT, payload=_payload(SEAT, "zero"), occurrence=0)
    _land_and_record(d, SEAT, payload=_payload(SEAT, "one"), occurrence=1)
    return d


# =============================================================================================
# Part 1 — `_attest_roster` matches a superseded row by its whole slot
# =============================================================================================

def test_fixture_pending_phase_is_round_one_attempt_zero(tmp_path, adapters):
    """The edge tests below name round 2 / attempt 1 / bool 1 against this pending phase."""
    d = _recorded_session(tmp_path, adapters)
    pend = _pending(d)
    assert pend["phase"] == RD.P_PANEL and pend["round"] == 1 and pend["attempt"] == 0
    assert _roster(d)[SEAT] == "recorded"


def test_edge1_a_superseded_row_of_another_round_does_not_label_the_slot(tmp_path, adapters):
    d = _recorded_session(tmp_path, adapters)
    _journal_row(d, round=_pending(d)["round"] + 1)
    assert _roster(d)[SEAT] == "recorded"


def test_edge2_a_superseded_row_of_another_phase_does_not_label_the_slot(tmp_path, adapters):
    d = _recorded_session(tmp_path, adapters)
    assert RD.P_AUDITS != _pending(d)["phase"]
    _journal_row(d, phase=RD.P_AUDITS)
    assert _roster(d)[SEAT] == "recorded"


def test_edge3_a_superseded_row_of_another_attempt_does_not_label_the_slot(tmp_path, adapters):
    d = _recorded_session(tmp_path, adapters)
    _journal_row(d, attempt=_pending(d)["attempt"] + 1)
    assert _roster(d)[SEAT] == "recorded"


@pytest.mark.parametrize("row_occurrence, expected", [
    (1, {SEAT: "recorded", SEAT + "#1": "superseded"}),
    (0, {SEAT: "superseded", SEAT + "#1": "recorded"}),
])
def test_edge4_only_the_named_occurrence_of_a_twin_slot_reads_superseded(
        tmp_path, adapters, row_occurrence, expected):
    d = _twin_session(tmp_path, adapters, name="twin%d" % row_occurrence)
    _journal_row(d, occurrence=row_occurrence)
    assert _roster(d) == expected


@pytest.mark.parametrize("occurrence_value", [_ABSENT, None, "1", 1.0, True],
                         ids=["absent", "none", "string", "float", "bool"])
def test_edge5_a_row_whose_occurrence_is_absent_or_not_an_int_reads_as_occurrence_zero(
        tmp_path, adapters, occurrence_value):
    d = _twin_session(tmp_path, adapters)
    _journal_row(d, occurrence=occurrence_value)
    assert _roster(d) == {SEAT: "superseded", SEAT + "#1": "recorded"}


def test_edge6_a_really_superseded_slot_still_reads_superseded_through_the_real_supersede(
        tmp_path, adapters):
    """Healthy sibling, real path: the journal row `record-result --supersede` writes names the slot."""
    d = _session(tmp_path)
    first = _land_and_record(d, SEAT)
    assert _roster(d)[SEAT] == "recorded"
    _land(d, SEAT, payload=_payload(SEAT, "replaced"))
    out = RD.cmd_record_result(d, SEAT, supersede=True, expect_sha256=first["casToken"])
    assert out["ok"] is True and out["superseded"] is True
    assert _roster(d)[SEAT] == "superseded"


def test_edge6_a_row_with_all_five_fields_of_the_slot_reads_superseded(tmp_path, adapters):
    """Healthy sibling: the full identity, written by hand, labels exactly its slot — and the other
    seats of the roster stay as they were."""
    d = _recorded_session(tmp_path, adapters, seats=(SEAT, OTHER_SEAT))
    _journal_row(d)
    roster = _roster(d)
    assert roster[SEAT] == "superseded"
    assert roster[OTHER_SEAT] == "recorded"
    assert roster["security-reviewer"] == "absent"


def test_edge7_a_missing_seat_is_not_hidden_by_a_superseded_row_of_another_round(
        tmp_path, adapters):
    d = _session(tmp_path)
    assert RD.cmd_record_missing(d, SEAT, 0, "timeout")["ok"] is True
    assert _roster(d)[SEAT] == "missing"
    _journal_row(d, round=_pending(d)["round"] + 1)
    assert _roster(d)[SEAT] == "missing"


def test_edge7_a_missing_seat_with_its_own_superseded_row_keeps_the_precedence(tmp_path, adapters):
    """Healthy sibling: precedence absent > superseded > missing > recorded is unchanged."""
    d = _session(tmp_path)
    assert RD.cmd_record_missing(d, SEAT, 0, "timeout")["ok"] is True
    _journal_row(d)
    assert _roster(d)[SEAT] == "superseded"


@pytest.mark.parametrize("superseded_value", [False, None, 0, _ABSENT],
                         ids=["false", "none", "zero", "absent"])
def test_edge8_a_row_whose_superseded_is_false_or_absent_never_counts(
        tmp_path, adapters, superseded_value):
    d = _recorded_session(tmp_path, adapters)
    _journal_row(d, superseded=superseded_value)
    assert _roster(d)[SEAT] == "recorded"


def test_edge9_a_bool_round_does_not_match_round_one(tmp_path, adapters):
    d = _recorded_session(tmp_path, adapters)
    assert _pending(d)["round"] == 1
    _journal_row(d, round=True)
    assert _roster(d)[SEAT] == "recorded"


def test_edge9_a_bool_attempt_does_not_match_attempt_zero(tmp_path, adapters):
    d = _recorded_session(tmp_path, adapters)
    assert _pending(d)["attempt"] == 0
    _journal_row(d, attempt=False)
    assert _roster(d)[SEAT] == "recorded"


def test_a_superseded_row_of_one_seat_never_labels_another_seat(tmp_path, adapters):
    d = _recorded_session(tmp_path, adapters, seats=(SEAT, OTHER_SEAT))
    _journal_row(d, seat=OTHER_SEAT)
    roster = _roster(d)
    assert roster[OTHER_SEAT] == "superseded"
    assert roster[SEAT] == "recorded"


# =============================================================================================
# Part 3 — `check_audit_breaker` counts distinct stalled findings
# =============================================================================================

def a_round(num, outcomes):
    return {"round": num, "outcomes": outcomes}


def nd(identity, **extra):
    d = {"identity": identity, "ruling": "not-discharged"}
    d.update(extra)
    return d


def dis(identity, **extra):
    d = {"identity": identity, "ruling": "discharged"}
    d.update(extra)
    return d


def _classed(identity, tid, **extra):
    """A not-discharged outcome that carries class-key aliases (classKey, dimension, taxonomy)."""
    return nd(identity, id=tid, title="leaks", classKey="Security::CWE-401::leaks",
              dimension="Security", taxonomy="CWE-401", **extra)


def test_p3_edge1_one_finding_with_class_key_aliases_counts_once():
    outcome = _classed("f.py::leaks", "f.py@L1")
    rounds = [a_round(1, [dict(outcome)]), a_round(2, [dict(outcome)])]
    # the precondition that makes this discriminating: the finding carries several aliases
    assert len(CB._audit_outcome_aliases(outcome)) >= 2
    res = CB.check_audit_breaker(rounds)
    assert res["halt"] is True and res["reason"] == "audit-stall"
    assert res["detail"] == STALL_PREFIX % (1, "f.py@L1")


def test_p3_edge2_two_distinct_stalled_findings_count_two():
    rounds = [a_round(1, [nd("f.py::a", id="f.py@L1"), nd("g.py::b", id="g.py@L2")]),
              a_round(2, [nd("f.py::a", id="f.py@L1"), nd("g.py::b", id="g.py@L2")])]
    res = CB.check_audit_breaker(rounds)
    assert res["halt"] is True
    assert res["detail"] == STALL_PREFIX % (2, "f.py@L1; g.py@L2")


def test_p3_edge3_two_findings_at_different_lines_sharing_a_lineless_identity_count_two():
    rounds = [a_round(1, [nd("x", id="x@L2"), nd("x", id="x@L3")]),
              a_round(2, [nd("x", id="x@L2"), nd("x", id="x@L3")])]
    res = CB.check_audit_breaker(rounds)
    assert res["halt"] is True
    assert res["detail"] == STALL_PREFIX % (2, "x@L2; x@L3")


def test_p3_edge4_one_id_recorded_twice_in_the_latest_round_counts_once():
    rounds = [a_round(1, [nd("f.py::a", id="T1")]),
              a_round(2, [nd("f.py::a", id="T1"), nd("f.py::a", id="T1")])]
    res = CB.check_audit_breaker(rounds)
    assert res["halt"] is True
    assert res["detail"] == STALL_PREFIX % (1, "T1")


def test_p3_edge5_two_idless_outcomes_sharing_an_identity_count_two_and_are_named_twice():
    rounds = [a_round(1, [nd("x"), nd("x")]), a_round(2, [nd("x"), nd("x")])]
    res = CB.check_audit_breaker(rounds)
    assert res["halt"] is True
    assert res["detail"] == STALL_PREFIX % (2, "x; x")


def test_p3_edge5_an_empty_or_nonstring_id_is_no_usable_id():
    rounds = [a_round(1, [nd("x", id=""), nd("x", id=None), nd("x", id=7)]),
              a_round(2, [nd("x", id=""), nd("x", id=None), nd("x", id=7)])]
    res = CB.check_audit_breaker(rounds)
    assert res["detail"] == STALL_PREFIX % (3, "x; x; x")


def test_p3_edge6_two_malformed_outcomes_in_both_rounds_count_two():
    bad = [{"ruling": "not-discharged"}, "not-a-dict"]
    res = CB.check_audit_breaker([a_round(1, list(bad)), a_round(2, list(bad))])
    assert res["halt"] is True and res["reason"] == "audit-stall"
    assert res["detail"] == STALL_PREFIX % (2, "%s; %s" % (CB._MALFORMED_OUTCOME,
                                                          CB._MALFORMED_OUTCOME))


def test_p3_edge6_a_malformed_round_counts_one_and_names_its_marker():
    res = CB.check_audit_breaker(["junk", "junk"])
    assert res["halt"] is True
    assert res["detail"] == STALL_PREFIX % (1, CB._MALFORMED_ROUND)


def test_p3_edge7_halt_reason_and_stalled_identities_are_the_alias_union():
    outcome = _classed("f.py::leaks", "f.py@L1")
    res = CB.check_audit_breaker([a_round(1, [dict(outcome)]), a_round(2, [dict(outcome)])])
    assert res["halt"] is True and res["reason"] == "audit-stall"
    assert res["stalledIdentities"] == sorted(CB._audit_outcome_aliases(outcome))
    assert len(res["stalledIdentities"]) >= 2


def test_p3_edge7_a_discharged_or_unshared_finding_does_not_stall():
    """Healthy sibling: no shared alias, or a discharge in between, is still no stall."""
    res = CB.check_audit_breaker([a_round(1, [nd("a", id="A")]), a_round(2, [nd("b", id="B")])])
    assert res == {"halt": False, "reason": None, "detail": "progressing", "stalledIdentities": []}
    res = CB.check_audit_breaker([a_round(1, [nd("a", id="A")]), a_round(2, [dis("a", id="A")])])
    assert res["halt"] is False and res["stalledIdentities"] == []


def test_p3_the_alias_helpers_never_read_id():
    assert CB._audit_outcome_aliases(nd("x", id="x@L2")) == {"x"}
    assert CB._audit_outcome_aliases(nd("x", id="other")) == {"x"}


def test_p3_the_helper_classifies_per_outcome_and_the_alias_view_agrees():
    round_rec = a_round(1, [nd("a", id="A"), dis("b", id="B"), nd("c"), {"ruling": "bad"}])
    rows = CB._round_not_discharged_findings(round_rec)
    assert [(name, aliases) for _key, name, aliases in rows] == [
        ("A", {"a"}), ("c", {"c"}), (CB._MALFORMED_OUTCOME, {CB._MALFORMED_OUTCOME})]
    assert CB._round_not_discharged(round_rec) == [aliases for _k, _n, aliases in rows]


# --- the outcome carries its id (edge 8) ---------------------------------------------------------

def audit_checks(**answers):
    return {name: {"answer": answers.get(name, "yes"), "why": "checked: %s" % name}
            for name in ("right", "brokeNothing", "testWouldFail")}


def _fold_one_not_discharged_round(state):
    """Fold one not-discharged audit of the state's single fix-batch target; return (target, round)."""
    state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
    tgt = state["_auditTargets"][0]
    RD._fold_audits(state, state["config"], {"results": [
        {"id": tgt["id"], "ruling": "not-discharged", "reason": "still broken",
         "checks": audit_checks(right="no")}]})
    return tgt, state["auditRounds"][-1]


def _batch_state():
    state = RD.new_state({"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF,
                         "fixerVendor": "claude"})
    state["fixBatch"] = [{"title": "leaks memory", "severity": "Important",
                          "consequence": _CONSEQUENCE, "file": "f.py", "line": 1,
                          "dimension": "Security", "taxonomy": "CWE-401",
                          "classKey": "Security::CWE-401::orig"}]
    return state


def test_p3_edge8_a_folded_audit_outcome_carries_its_targets_id():
    tgt, round1 = _fold_one_not_discharged_round(_batch_state())
    assert tgt["id"] and tgt["id"] != tgt["identity"]
    assert round1["outcomes"][0]["id"] == tgt["id"]
    # additive: the keys the alias match reads are all still there
    for key in ("identity", "ruling", "title", "classKey", "dimension", "taxonomy"):
        assert key in round1["outcomes"][0]


def test_p3_edge8_a_stall_through_the_fold_names_the_finding_by_its_target_id():
    tgt, round1 = _fold_one_not_discharged_round(_batch_state())
    round2 = {"round": round1["round"] + 1, "outcomes": [dict(round1["outcomes"][0])]}
    res = CB.check_audit_breaker([round1, round2])
    assert res["halt"] is True and res["reason"] == "audit-stall"
    assert res["detail"] == STALL_PREFIX % (1, tgt["id"])
    assert len(res["stalledIdentities"]) >= 2
