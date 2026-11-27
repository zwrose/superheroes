"""#2667 — the review driver takes its vendors from the seat map, and a round whose fix audits cannot
be seated stops and says why.

Pins: one vendor source on a fresh `next` (the seat map's `liveVendors`), the halt `audits-unseatable`
after an all-unseatable audits fold (a post-fix verify gate still runs first), the one cause carried by
every record of that round, and the healthy path unchanged.
"""
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import audits  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD
RDISC = TRD.RD_DISCLOSURES
_cfg = TRD._cfg
_fix_state = TRD._fix_state
_guard_argv = TRD._guard_argv
_cli_next_json = TRD._cli_next_json
audit_checks = TRD.audit_checks


def _write_map(d, **over):
    seat_map = {"hostFamily": "anthropic"}
    seat_map.update(over)
    path = os.path.join(d, "seat-map.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(seat_map, fh)
    return path


def _targets(state):
    state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
    return state["_auditTargets"]


def _last_round(state):
    return state["rounds"][str(state["round"])]


# 1 -------------------------------------------------------------------------------------------

def test_no_vendors_flag_the_seat_map_supplies_codex(tmp_path, capsys):
    # axis: I1 — a fresh `next` with a seat map and no `--vendors` reads config.vendors off liveVendors
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2667_vendors_from_seat_map.md
    d = str(tmp_path)
    path = _write_map(d, liveVendors=["codex", "claude"])
    rc, out = _cli_next_json(d, _guard_argv(d) + ["--seat-map", path], capsys)
    assert rc == 0 and out["ok"], out
    ok, state = RD.load_state(d)
    assert ok and state is not None
    cfg = state["config"]
    assert cfg["vendors"] == ["claude", "codex"]
    assert cfg["vendorsSource"] == "seat-map"
    assert cfg["fixerVendor"] == "claude"
    state["fixBatch"] = [{"title": "bug", "severity": "Important", "consequence": "a defect stays",
                          "file": "f.py", "line": 1}]
    target = RD._audit_targets(state, state["config"], {})[0]
    assert target["auditorVendor"] == "codex"
    assert target["independence"] == "independent"


# 2 -------------------------------------------------------------------------------------------

def test_vendors_that_disagree_with_the_seat_map_refuse_naming_both_lists(tmp_path, capsys):
    # axis: I1 — a `--vendors` whose set differs from liveVendors refuses and writes nothing
    d = str(tmp_path)
    path = _write_map(d, liveVendors=["codex", "claude"])
    rc, out = _cli_next_json(d, _guard_argv(d) + ["--vendors", "claude", "--seat-map", path], capsys)
    assert rc == 1
    assert out["reason"] == "vendors-disagree-with-seat-map"
    assert out["vendors"] == ["claude"]
    assert out["seatMapLiveVendors"] == ["claude", "codex"]
    assert not os.path.exists(os.path.join(d, RD.STATE_FILE))
    ok, state = RD.load_state(d)
    assert ok and state is None


def test_vendors_with_the_same_set_in_another_order_are_accepted(tmp_path, capsys):
    # axis: I1 — agreement is by set: order and duplicates do not matter, and the source reads `cli`
    d = str(tmp_path)
    path = _write_map(d, liveVendors=["codex", "claude"])
    rc, out = _cli_next_json(
        d, _guard_argv(d) + ["--vendors", "codex,claude,codex", "--seat-map", path], capsys)
    assert rc == 0 and out["ok"], out
    ok, state = RD.load_state(d)
    assert ok and state["config"]["vendorsSource"] == "cli"
    assert set(state["config"]["vendors"]) == {"claude", "codex"}


# 3 -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("over", [{}, {"liveVendors": []}], ids=["absent", "empty"])
def test_seat_map_without_live_vendors_keeps_todays_default(tmp_path, capsys, over):
    # axis: I1 — no seat-map source (key absent, or `[]`) behaves exactly as before: the default list
    d = str(tmp_path)
    path = _write_map(d, **over)
    rc, out = _cli_next_json(d, _guard_argv(d) + ["--seat-map", path], capsys)
    assert rc == 0 and out["ok"], out
    ok, state = RD.load_state(d)
    assert ok and state["config"]["vendors"] == ["claude"]
    assert "vendorsSource" not in state["config"]


@pytest.mark.parametrize("bad", ["claude,codex", ["claude", 5], ["claude", " codex"], ["acme"]],
                         ids=["csv-string", "non-string-member", "unstripped-member", "unregistered"])
def test_malformed_live_vendors_refuse_and_write_nothing(tmp_path, capsys, bad):
    # axis: I1 — a liveVendors that is not a list of registered vendor names refuses, nothing written
    d = str(tmp_path)
    path = _write_map(d, liveVendors=bad)
    rc, out = _cli_next_json(d, _guard_argv(d) + ["--seat-map", path], capsys)
    assert rc == 1
    assert out["reason"] == "seat-map-live-vendors-invalid"
    assert out["value"] == bad
    assert not os.path.exists(os.path.join(d, RD.STATE_FILE))


# 4 -------------------------------------------------------------------------------------------

def test_an_all_unseatable_audits_fold_halts_with_the_cause():
    # axis: I2 and I3 — the fold marks every no-auditor entry and the round, and the session halts
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2667_vendors_from_seat_map.md
    state = _fix_state(_cfg(vendors=["claude"]))
    targets = _targets(state)
    ids = [t["id"] for t in targets]
    assert ids and all(t.get("auditorVendor") is None for t in targets)
    RD._fold_audits(state, state["config"], {"results": []})
    assert state["terminal"] == "halted"
    assert state["step"] == RD.P_TERMINAL
    assert state["decisions"][-1]["kind"] == RD.AUDITS_UNSEATABLE
    marked = _last_round(state)["auditsUnseatable"]
    assert marked["cause"] == RDISC.CAUSE_NO_INDEPENDENT_VENDOR
    reason = state["certification"]["reason"]
    assert reason.startswith(RD.AUDITS_UNSEATABLE + ":")
    assert marked["detail"] in reason
    assert "config.vendors" in marked["detail"] and "claude" in marked["detail"]
    assert state["decisions"][-1]["detail"] == marked["detail"]
    # axis: the emitted (verdict, decision) pair is the terminal-cause table's own key, so a drifted key fails here
    assert RD.decision_kinds.map_terminal_cause(state["terminal"], state["decisions"][-1]["kind"]) == {
        "kind": "loop", "reason": "detector"}
    entries = [a for a in _last_round(state)["audits"] if a["id"] in ids]
    assert len(entries) == len(ids)
    for entry in entries:
        assert entry["reason"] == audits.NO_AUDIT_RESULT_REASON
        assert entry["cause"] == marked
        assert entry["cause"]["vendors"] == ["claude"]
    assert "_auditsUnseatable" not in state


# 5 -------------------------------------------------------------------------------------------

def test_an_all_unseatable_audits_round_ends_the_session_through_next_and_submit(tmp_path):
    # axis: I2 — driven through `next`/`submit` (hand channel), the next `next` is the terminal and
    # no scoped finder or later round is ever emitted after the audits
    d = str(tmp_path)
    seen = []
    inner = TRD._responder(round1_findings=TRD._A_FINDING)

    def respond(phase, payload, rnd):
        seen.append((phase, rnd))
        return inner(phase, payload, rnd)

    payload = TRD._drive_cli(d, _cfg(vendors=["claude"]), respond)
    assert payload["verdict"] == "halted"
    ok, state = RD.load_state(d)
    assert ok and state["terminal"] == "halted"
    assert state["certification"]["reason"].startswith(RD.AUDITS_UNSEATABLE + ":")
    assert "config.vendors" in state["certification"]["reason"]
    assert state["decisions"][-1]["kind"] == RD.AUDITS_UNSEATABLE
    phases = [p for p, _r in seen]
    last_audits = max(i for i, p in enumerate(phases) if p == RD.P_AUDITS)
    # only the armed post-fix verify gate runs after the audits: no scoped finder, seams check, fixer
    # or later round is dispatched
    assert phases[last_audits + 1:] == [RD.P_VERIFY], phases
    assert max(r for _p, r in seen) == seen[last_audits][1]


# 6 -------------------------------------------------------------------------------------------

def test_an_armed_post_fix_verify_runs_before_the_halt():
    # axis: I2 — the verify gate armed for the round still runs first; the halt follows its pass
    state = _fix_state(_cfg(vendors=["claude"]))
    _targets(state)
    state["_verifyThen"] = RD.VERIFY_THEN_POST_AUDITS
    RD._fold_audits(state, state["config"], {"results": []})
    assert state["step"] == RD.P_VERIFY
    assert not state.get("terminal")
    assert isinstance(state.get("_auditsUnseatable"), dict)
    RD._fold_verify(state, state["config"], {"result": "pass"}, resolution=(None, None))
    assert state["terminal"] == "halted"
    assert state["decisions"][-1]["kind"] == RD.AUDITS_UNSEATABLE
    assert state["step"] == RD.P_TERMINAL


# 7 -------------------------------------------------------------------------------------------

def test_the_three_causes_each_name_the_vendor_list_they_read():
    # axis: I3 — one builder, three causes, each reading the same inputs the selection reads
    assert set(RDISC.AUDIT_UNSEATABLE_CAUSES) == {
        RDISC.CAUSE_FIXER_FAMILY_UNKNOWN, RDISC.CAUSE_RUNNER_CHANNEL_ONLY, RDISC.CAUSE_PINNED_ROSTER_EXCLUDES,
        RDISC.CAUSE_NO_INDEPENDENT_VENDOR}
    unknown = RDISC.audit_unseatable_cause({"config": {"vendors": ["claude", "codex"]}})
    assert unknown["cause"] == RDISC.CAUSE_FIXER_FAMILY_UNKNOWN and unknown["fixerFamily"] is None
    runner = RDISC.audit_unseatable_cause(
        {"config": {"vendors": ["claude", "codex"], "fixerVendor": "codex"}, "_advanceUsed": True})
    assert runner["cause"] == RDISC.CAUSE_RUNNER_CHANNEL_ONLY and runner["runnerOnly"] is True
    assert "claude" in runner["detail"]
    none = RDISC.audit_unseatable_cause(
        {"config": {"vendors": ["claude"], "fixerVendor": "claude", "vendorsSource": "cli"}})
    assert none["cause"] == RDISC.CAUSE_NO_INDEPENDENT_VENDOR
    assert none["vendorsSource"] == "cli" and none["vendors"] == ["claude"]
    assert none["vendorList"] == "config.vendors" and none["fixerFamily"] == "anthropic"
    for cause in (unknown, runner, none):
        assert cause["cause"] in RDISC.AUDIT_UNSEATABLE_CAUSES
        assert "config.vendors" in cause["detail"]
        assert "from " + cause["vendorsSource"] in cause["detail"]
        assert cause["pinnedVendors"] is None


def test_the_pinned_roster_cause_names_the_excluded_vendor_and_the_list_source():
    # axis: I3 — a live independent vendor kept out only by the pinned roster is named, with the vendor list's source
    state = {"config": {"vendors": ["claude", "codex"], "fixerVendor": "claude", "vendorsSource": "seat-map"},
             "seatMapReceipts": [{"round": "1", "map": {
                 "makerFamilies": ["anthropic"],
                 "seats": {"code-reviewer": {"vendor": "cursor", "source": "pinned"}}}}]}
    cause = RDISC.audit_unseatable_cause(state)
    assert cause["cause"] == RDISC.CAUSE_PINNED_ROSTER_EXCLUDES
    assert cause["pinnedVendors"] == ["cursor"]
    assert "codex" in cause["detail"] and "from seat-map" in cause["detail"]


def test_the_cause_builder_never_raises_on_a_malformed_state():
    # axis: I3 — a malformed state or config still yields a cause dict (fail closed, never a crash)
    for state, config in ((None, None), ({}, None), ({"config": "x"}, None), ({"rounds": 3}, [1]),
                          ({"config": {"vendors": 7, "fixerVendor": 9}}, None)):
        cause = RDISC.audit_unseatable_cause(state, config)
        assert cause["cause"] in RDISC.AUDIT_UNSEATABLE_CAUSES
        assert isinstance(cause["detail"], str) and cause["detail"]


# 8 -------------------------------------------------------------------------------------------

def test_the_missing_envelope_for_an_audit_slot_carries_the_cause(tmp_path):
    # axis: I3 — the seat-missing envelope's evidence for a no-auditor audit slot names the cause
    state = _fix_state(_cfg(vendors=["claude"]))
    cause = RDISC.audit_unseatable_cause(state)
    args = (str(tmp_path), state, 2, RD.P_AUDITS, 1, "audit:x", 1, "0" * 64, {})
    envelope = RD._unfilled_seat_missing_envelope(*args)
    assert cause["detail"] in envelope["evidence"]
    assert envelope["evidence"].startswith("no auditor outside the makers' families is available")
    panel = RD._unfilled_seat_missing_envelope(
        str(tmp_path), state, 1, RD.P_PANEL, 1, "code-reviewer", 1, "0" * 64, {})
    assert panel["evidence"] == ("the seat map leaves this seat unfilled: no candidate outside the "
                                 "makers' families")


# 9 -------------------------------------------------------------------------------------------

def test_a_healthy_session_is_unchanged():
    # axis: I4 — with an independent auditor: same target, no cause, no round key, no halt
    state = _fix_state(_cfg(vendors=["claude", "codex"]))
    targets = _targets(state)
    assert [t["auditorVendor"] for t in targets] == ["codex"]
    results = [dict({"id": t["id"], "ruling": "discharged", "reason": "fix resolves it",
                     "evidence": "tests pass", "auditorVendor": "codex", "checks": audit_checks()},
                    **TRD.audit_test_match(t))
               for t in targets]
    manifest = {t["id"]: "codex" for t in targets}
    RD._fold_audits(state, state["config"], {"results": results, "collectionManifest": manifest})
    assert state.get("terminal") != "halted"
    assert "auditsUnseatable" not in _last_round(state)
    assert "_auditsUnseatable" not in state
    assert all("cause" not in a for a in _last_round(state)["audits"])
    assert not [d for d in state["decisions"] if d["kind"] == RD.AUDITS_UNSEATABLE]


# E4 / E5 -------------------------------------------------------------------------------------

def test_a_stale_mark_never_halts_a_later_healthy_round():
    # axis: I2 — a mark left by an earlier fold is cleared at the top of every audits fold
    state = _fix_state(_cfg(vendors=["claude", "codex"]))
    state["_auditsUnseatable"] = {"cause": RDISC.CAUSE_NO_INDEPENDENT_VENDOR, "detail": "stale"}
    targets = _targets(state)
    RD._fold_audits(state, state["config"], {"results": [
        dict({"id": t["id"], "ruling": "discharged", "reason": "r", "evidence": "e",
              "auditorVendor": "codex", "checks": audit_checks()}, **TRD.audit_test_match(t))
        for t in targets], "collectionManifest": {t["id"]: "codex" for t in targets}})
    assert state.get("terminal") != "halted"
    assert "_auditsUnseatable" not in state


def test_a_mixed_round_marks_only_the_no_auditor_entries_and_does_not_halt():
    # axis: I2 — a mix of seatable and unseatable targets marks only the unseatable ones, no halt
    state = _fix_state(_cfg(vendors=["claude", "codex"]))
    targets = _targets(state)
    state["_auditTargets"] = [dict(targets[0], id="seated", auditorVendor="codex"),
                              dict(targets[0], id="unseated", auditorVendor=None)]
    RD._fold_audits(state, state["config"], {"results": []})
    by_id = {a["id"]: a for a in _last_round(state)["audits"]}
    assert "cause" in by_id["unseated"] and "cause" not in by_id["seated"]
    assert "auditsUnseatable" not in _last_round(state)
    assert state.get("terminal") != "halted"
