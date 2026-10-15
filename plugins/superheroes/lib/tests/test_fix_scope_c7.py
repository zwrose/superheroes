"""C7 L2c (WO2): a fix touches only what its finding needs.

Part A: an out-of-scope finding is offered to a fixer in at most one round while it stays out of scope.
Part B: a fix that changes behaviour its finding does not name is not credited `fixed` without a
ruling that allows it.

Drives the real round driver: `run_loop` with scripted seams for the loop-shaped cases, a staged state
for the fix-batch writer, and the audit fold, the `rule` verb, the native-result transport and the
strict-mode schema directly for the rest.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/wo2_c7_fix_scope.md
"""
import copy
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import audits as AU  # noqa: E402
import engine_adapter as EA  # noqa: E402
import engine_dispatch as ED  # noqa: E402
import engine_result_channel as ERC  # noqa: E402
import payload_contracts as PC  # noqa: E402
import session_contract as SC  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD  # run_loop runs on test_round_driver's own load of the module

UNNAMED = "it also stops retrying on a timeout"
UNNAMED_REASON_PREFIX = "the fix changes behaviour its finding does not name"


def _follow_up():
    return {"item": "backlog item", "revisitTrigger": "next milestone", "classClosure": "owner backlog"}


def _provenance():
    return {"ruledBy": "owner", "ruledAt": "2026-08-26T00:00:00Z", "records": ["rulings.json"]}


def _finding(title, line=1, severity="Important", kind="real", **extra):
    out = {"file": "f.py", "line": line, "title": title, "severity": severity,
           "consequence": "users lose their saved work", "consequenceKind": kind}
    out.update(extra)
    return out


def _key(title, line=1):
    return "f.py::%s@L%d" % (title.lower(), line)


def _ledger(state):
    return {SC.finding_identity_key(e): e for e in state.get(SC.DISPOSITION_LEDGER_KEY) or []}


def _decisions(state, kind):
    return [d for d in state.get("decisions") or [] if d.get("kind") == kind]


def _staged_state(findings, round_no=1):
    state = RD.new_state(TRD._cfg())
    compiled, _ = RD.mechanical_compile([dict(f) for f in findings], None)
    RD._stage_findings(state, compiled)
    RD._set_findings(state, state["_toVerify"])
    state["round"] = round_no
    return state


def _decide(state, key, ruling, round_no, **extra):
    """Append a decision to `rulingsLog` the way the `rule` verb writes it."""
    state["rulingSeqCounter"] = state.get("rulingSeqCounter", 0) + 1
    row = {"seq": state["rulingSeqCounter"], "round": round_no, "phase": "dispatch-fixer",
           "attempt": None, "id": key, "findingKey": key, "ruling": ruling, "reason": "owner call",
           "by": "owner"}
    if ruling == "out-of-scope":
        row["followUp"] = _follow_up()
    if ruling == "guidance":
        row["guidance"] = "keep the retry behaviour"
    row.update(extra)
    state.setdefault("rulingsLog", []).append(row)
    return row["seq"]


def _offer(state, round_no, **kw):
    """Offer the state's findings to the fix-batch writer in `round_no`; returns (status, keys)."""
    state["round"] = round_no
    state.pop("_fixBatch", None)
    status = RD._queue_fix_batch(state, state["config"], [dict(f) for f in state["findings"]], **kw)
    return status, [RD._fix_batch_row_key(r) for r in state.get("_fixBatch") or []]


@pytest.fixture
def empty_batch_calls(monkeypatch):
    """Record each time the empty-batch resolver runs (it needs a whole loop behind it to run)."""
    calls = []
    monkeypatch.setattr(RD, "_resolve_empty_fix_batch_convergence",
                        lambda state, config: calls.append(state["round"]))
    return calls


@pytest.fixture
def captured_state(monkeypatch):
    """The state `run_loop` builds, so a scripted seam can record a decision into it."""
    box = {}
    real = RD.new_state

    def capture(*args, **kwargs):
        box["state"] = real(*args, **kwargs)
        return box["state"]

    monkeypatch.setattr(RD, "new_state", capture)
    monkeypatch.setattr(RD, "_decision_sources", lambda state: {})
    return box


# --- Part A: out of scope, offered once ---------------------------------------------------------

def test_t4_edge1_critical_out_of_scope_offered_in_round_two_is_not_in_round_three(empty_batch_calls):
    state = _staged_state([_finding("Gate bypass", severity="Critical")])
    key = _key("Gate bypass")
    _decide(state, key, "out-of-scope", 1)
    RD._record_disposition(state, key, "out-of-scope", 1, outOfScopeReason="owner deferred it",
                           followUp=_follow_up())

    status, keys = _offer(state, 2)
    assert (status, keys) == ("queued", [key])
    assert state["outOfScopeFixerRounds"] == {key: {"episode": 1, "rounds": [2]}}
    # the same round asked again (a ruling re-slices the batch) is not a second offer
    status, keys = _offer(state, 2, reset_accumulator=False)
    assert (status, keys) == ("queued", [key])

    status, keys = _offer(state, 3)
    assert status == "excluded" and keys == []
    row = _ledger(state)[key]
    assert row["disposition"] == "out-of-scope"
    assert "round 2" in row["outOfScopeReason"]
    assert row["followUp"] == _follow_up()
    spent = _decisions(state, "out-of-scope-fix-spent")
    assert len(spent) == 1 and "round 2" in spent[0]["detail"]
    assert state["outOfScopeFixerRounds"][key]["rounds"] == [2]


def test_t4_edge2_a_later_guidance_decision_returns_the_finding_to_the_batch(empty_batch_calls):
    state = _staged_state([_finding("Gate bypass", severity="Critical")])
    key = _key("Gate bypass")
    _decide(state, key, "out-of-scope", 1)
    assert _offer(state, 2) == ("queued", [key])
    assert _offer(state, 3)[0] == "excluded"

    _decide(state, key, "guidance", 3)
    assert _offer(state, 4) == ("queued", [key])  # the episode ended
    assert _offer(state, 5) == ("queued", [key])

    seq = _decide(state, key, "out-of-scope", 5)  # a new episode starts afresh
    assert _offer(state, 6) == ("queued", [key])
    assert state["outOfScopeFixerRounds"][key] == {"episode": seq, "rounds": [6]}
    status, keys = _offer(state, 7)
    assert status == "excluded" and keys == []
    assert "round 6" in _ledger(state)[key]["outOfScopeReason"]


def test_t4_edge2_an_unsequenced_gate_skip_is_one_episode_per_its_round(empty_batch_calls):
    state = _staged_state([_finding("Gate bypass", severity="Critical")])
    key = _key("Gate bypass")
    state["rounds"]["1"] = {"judgmentDispositions": [
        {"id": key, "file": "f.py", "line": 1, "title": "Gate bypass", "disposition": "skip",
         "reason": "owner accepted it"}]}
    assert _offer(state, 2) == ("queued", [key])
    assert state["outOfScopeFixerRounds"][key]["episode"] == "round:1"
    assert _offer(state, 3)[0] == "excluded"


def test_t4_edge3_a_batch_emptied_only_by_the_rule_settles_through_the_empty_batch_path(
        empty_batch_calls):
    state = _staged_state([_finding("Gate bypass", severity="Critical")])
    key = _key("Gate bypass")
    _decide(state, key, "out-of-scope", 1)
    assert _offer(state, 2)[0] == "queued"
    state["rounds"]["3"] = {"fixBatchExcludedByDischarge": 4}

    status, _keys = _offer(state, 3)
    assert status == "excluded"
    assert empty_batch_calls == [3]
    assert state["rounds"]["3"]["fixBatchExcludedByDischarge"] == 4  # unchanged
    own = [d for d in _decisions(state, "fix-batch-excluded") if "once-per-episode" in d["detail"]]
    assert len(own) == 1


def test_t4_edge3_a_batch_emptied_by_discharge_is_still_counted(empty_batch_calls):
    state = _staged_state([_finding("Done already")])
    RD._record_disposition(state, _key("Done already"), "fixed", 1)
    status, _keys = _offer(state, 2)
    assert status == "excluded"
    assert empty_batch_calls == [2]
    assert state["rounds"]["2"]["fixBatchExcludedByDischarge"] == 1
    assert _decisions(state, "out-of-scope-fix-spent") == []


def test_t1_a_critical_out_of_scope_finding_is_offered_to_a_fixer_once(captured_state):
    # axis: the fix batch of a later round in the same out-of-scope episode leaves the finding out
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo2_c7_fix_scope.md
    key = _key("Gate bypass")
    offers = []

    def reviewer(dim, tier, rnd, ctx):
        if rnd == 1 and dim == "code-reviewer":
            return {"findings": [_finding("Gate bypass", severity="Critical")]}
        return []

    def verifier(clusters, rnd):
        # the owner defers the finding before the first fix batch is planned
        if not captured_state["state"].get("rulingsLog"):
            _decide(captured_state["state"], key, "out-of-scope", rnd)
        return {"verdicts": [{"id": i, "verdict": "CONFIRMED", "evidence": "ran", "reason": "ran"}
                             for c in (clusters or []) for i in (c.get("ids") or [])],
                "vendor": "codex"}

    def fix_step(batch, rnd, payload):
        offers.append((rnd, [RD._fix_batch_row_key(r) for r in batch]))
        return {"fixes": [], "headDiff": TRD._headf(len(offers)), "changedSubjects": ["Code"]}

    def auditor(targets, rnd):
        return [{"id": t["id"], "ruling": "not-discharged", "reason": "still open"}
                for t in (targets or [])]

    seams = TRD._seams(reviewer=reviewer, verifier=verifier, fix_step=fix_step, auditor=auditor,
                       io={"stall_menu": lambda payload: "hold"})
    _result, state = TRD._run_loop_capturing_state(seams, TRD._cfg_cert())
    assert state["terminal"]
    assert offers == [(1, [key])]  # offered once; the next round's batch left it out
    assert state["outOfScopeFixerRounds"][key] == {"episode": 1, "rounds": [1]}
    assert len(_decisions(state, "out-of-scope-fix-spent")) == 1
    row = _ledger(state)[key]
    assert "round 1" in (row.get("outOfScopeReason") or "") + (row.get("settledReason") or "")
    assert "fixBatchExcludedByDischarge" not in state["rounds"]["2"]
    assert any("once-per-episode" in d["detail"] for d in _decisions(state, "fix-batch-excluded"))


def test_t2_an_out_of_scope_low_severity_real_finding_ends_as_a_leftover(captured_state):
    key = _key("Cache lies", 2)

    def reviewer(dim, tier, rnd, ctx):
        if rnd == 1 and dim == "code-reviewer":
            return {"findings": [_finding("Cache lies", 2, severity="Minor", kind="real")]}
        return []

    def verifier(clusters, rnd):
        state = captured_state["state"]
        if not state.get("rulingsLog"):
            _decide(state, key, "out-of-scope", rnd)
            RD._record_disposition(state, key, "out-of-scope", rnd, outOfScopeReason="owner deferred it",
                                   followUp=_follow_up())
        return {"verdicts": [{"id": i, "verdict": "CONFIRMED", "evidence": "ran", "reason": "ran"}
                             for c in (clusters or []) for i in (c.get("ids") or [])],
                "vendor": "codex"}

    seams = TRD._seams(reviewer=reviewer, verifier=verifier)
    _result, state = TRD._run_loop_capturing_state(seams, TRD._cfg_cert())
    assert state["terminal"] == "converged"
    row = _ledger(state)[key]
    assert row["disposition"] == "left-for-owner"
    assert "out of scope" in row["settledReason"]
    assert _decisions(state, "out-of-scope-fix-spent") == []


# --- Part B: the audit fold ---------------------------------------------------------------------

def _fold(result, allowed=(), target=None, **kw):
    target = target or {"id": "a", "file": "f.py", "line": 1, "title": "t", "severity": "Important"}
    body = {"id": "a", "ruling": "discharged", "reason": "the fix resolves it"}
    body.update(result)
    return AU.apply_audit_results([target], [body], change_allowed_ids=allowed, **kw)


def test_t4_edge4_an_unnamed_change_without_an_allowing_ruling_is_not_discharged():
    out = _fold({"unnamedChange": UNNAMED})
    assert out["discharged"] == [] and out["notDischarged"] == ["a"]
    assert out["unnamedChange"] == ["a"]
    assert out["audits"][0]["ruling"] == "not-discharged"
    assert out["audits"][0]["reason"] == "%s: %s" % (UNNAMED_REASON_PREFIX, UNNAMED)


def test_t4_edge4_an_allowing_ruling_keeps_the_discharge_and_records_the_change():
    out = _fold({"unnamedChange": "  %s " % UNNAMED}, allowed=["a"])
    assert out["discharged"] == ["a"] and out["unnamedChange"] == []
    assert out["audits"][0]["ruling"] == "discharged"
    assert out["audits"][0]["allowedChange"] == UNNAMED


def test_t4_edge4_a_target_not_in_the_allowed_ids_is_refused_even_when_another_is_allowed():
    out = _fold({"unnamedChange": UNNAMED}, allowed=["b"])
    assert out["discharged"] == [] and out["unnamedChange"] == ["a"]


def test_t4_edge4_new_issues_of_a_refused_clearing_result_still_route():
    out = _fold({"ruling": "discharged-but-new-issue", "unnamedChange": UNNAMED,
                 "newIssues": [{"file": "g.py", "line": 3, "title": "fresh", "severity": "Minor"}]})
    assert out["discharged"] == [] and out["unnamedChange"] == ["a"]
    assert [n["title"] for n in out["newIssues"]] == ["fresh"]
    assert out["newIssues"][0]["originAuditId"] == "a"


@pytest.mark.parametrize("value", [None, "", "   \n"], ids=["null", "empty", "blank"])
def test_t4_edge5_a_blank_or_null_unnamed_change_has_no_effect(value):
    out = _fold({"unnamedChange": value})
    assert out["discharged"] == ["a"] and out["unnamedChange"] == []
    assert "allowedChange" not in out["audits"][0]


@pytest.mark.parametrize("value", [7, True, ["x"]], ids=["number", "bool", "list"])
def test_t4_edge5_a_non_string_unnamed_change_is_malformed(value):
    out = _fold({"unnamedChange": value}, allowed=["a"])
    assert out["discharged"] == [] and out["notDischarged"] == ["a"]
    assert out["malformed"] == ["a"] and out["unnamedChange"] == []


def test_t4_edge5_a_reasonless_clearing_result_stays_malformed_not_unnamed_change():
    out = _fold({"reason": "", "unnamedChange": UNNAMED})
    assert out["malformed"] == ["a"] and out["unnamedChange"] == []


def test_t4_edge6_an_unauthenticated_clearing_result_stays_unauthenticated():
    target = {"id": "a", "file": "f.py", "line": 1, "title": "t", "severity": "Important"}
    out = _fold({"unnamedChange": UNNAMED}, target=target,
                expected_auditors={"a": "codex"}, collection_manifest={})
    assert out["unauthenticated"] == ["a"] and out["unnamedChange"] == []
    assert out["audits"][0]["unauthenticatedCause"] == AU.UNAUTHENTICATED_MANIFEST_ENTRY_MISSING
    assert out["notDischarged"] == ["a"]


# --- Part B: the loop ---------------------------------------------------------------------------

def _unnamed_change_loop(captured_state, *, allow):
    key = _key("Null deref")
    offers, seen_targets, history = [], [], {}

    def reviewer(dim, tier, rnd, ctx):
        if rnd == 1 and dim == "code-reviewer":
            return {"findings": [_finding("Null deref", body="the value can be missing",
                                          suggestion="check it first")]}
        return []

    def fix_step(batch, rnd, payload):
        state = captured_state["state"]
        offers.append((rnd, [RD._fix_batch_row_key(r) for r in batch]))
        if len(offers) == 1 and allow:
            _decide(state, key, "guidance", rnd, allowsChange=True)
        if len(offers) == 2:
            history.update(RD._finding_history(state))
        return {"fixes": [], "headDiff": TRD._headf(len(offers)), "changedSubjects": ["Code"]}

    def auditor(targets, rnd):
        seen_targets.append(copy.deepcopy(targets))
        out = []
        for t in targets or []:
            result = {"id": t["id"], "ruling": "discharged", "reason": "fix resolves it",
                      "evidence": "tests pass", "auditorVendor": t.get("auditorVendor")}
            if rnd == 2:
                result["unnamedChange"] = UNNAMED
            out.append(result)
        return out

    seams = TRD._seams(reviewer=reviewer, fix_step=fix_step, auditor=auditor,
                       io={"stall_menu": lambda payload: "hold"})
    _result, state = TRD._run_loop_capturing_state(seams, TRD._cfg_cert())
    return key, state, offers, seen_targets, history


def test_t3_a_fix_with_an_unnamed_change_is_not_fixed_and_returns_with_the_auditors_reason(
        captured_state):
    # axis: refusal — a clearing audit that names an unnamed change is not credited without a ruling
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo2_c7_fix_scope.md
    key, state, offers, seen_targets, history = _unnamed_change_loop(captured_state, allow=False)
    assert state["terminal"] == "converged"
    audit = state["rounds"]["2"]["audits"][0]
    assert audit["ruling"] == "not-discharged"
    assert audit["reason"] == "%s: %s" % (UNNAMED_REASON_PREFIX, UNNAMED)
    assert state["rounds"]["2"]["auditUnnamedChange"] == [key]
    assert len(_decisions(state, "audit-unnamed-change")) == 1
    # the finding went back to the next fixer, who is shown the auditor's reason
    assert offers == [(1, [key]), (2, [key])]
    assert history[key]["priorAudit"]["reason"].startswith(UNNAMED_REASON_PREFIX)
    # credited only when a later audit named nothing unexpected
    row = _ledger(state)[key]
    assert row["disposition"] == "fixed" and row["dispositionRound"] == 3


def test_t3_a_guidance_ruling_that_allows_the_change_keeps_the_fix_credited(captured_state):
    # axis: allowance — only a guidance ruling with allowsChange true lets the unnamed change stand
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo2_c7_fix_scope.md
    key, state, offers, seen_targets, _history = _unnamed_change_loop(captured_state, allow=True)
    assert state["terminal"] == "converged"
    audit = state["rounds"]["2"]["audits"][0]
    assert audit["ruling"] == "discharged" and audit["allowedChange"] == UNNAMED
    assert "auditUnnamedChange" not in state["rounds"]["2"]
    assert offers == [(1, [key])]
    row = _ledger(state)[key]
    assert row["disposition"] == "fixed" and row["dispositionRound"] == 2


def test_t3_the_auditor_is_given_the_finding_text_and_the_fix_hunks(captured_state):
    _key_, _state, _offers, seen_targets, _history = _unnamed_change_loop(captured_state, allow=False)
    target = seen_targets[0][0]
    assert target["body"] == "the value can be missing"
    assert target["suggestion"] == "check it first"
    assert target["consequence"] == "users lose their saved work"
    assert len(target["fixHunks"]) == 1 and target["fixHunks"][0]["text"].startswith("@@ -1 +1,3 @@")


# --- Part B: what the auditor is given ----------------------------------------------------------

def _hunk(start, end):
    return {"start": start, "end": end, "text": "@@ +%d,%d @@" % (start, end - start + 1)}


def test_t5_audit_targets_carry_the_finding_text_and_only_the_hunks_over_their_line():
    state = RD.new_state(TRD._cfg(fixerVendor="claude"))
    state["fixBatch"] = [
        dict(_finding("Near the top", 2), body="b1", suggestion="s1"),
        dict(_finding("Far down", 80)),
        _finding("Other file", 2, file="g.py"),
        {"file": "f.py", "line": "x", "title": "No line", "severity": "Minor"},
    ]
    hunks = {"f.py": [_hunk(1, 4), _hunk(78, 90), _hunk(200, 210)], "g.py": [_hunk(500, 510)]}
    top, far, other, no_line = RD._audit_targets(state, state["config"], hunks)
    assert top["fixHunks"] == [_hunk(1, 4)]
    assert (top["body"], top["suggestion"], top["consequence"]) == (
        "b1", "s1", "users lose their saved work")
    assert far["fixHunks"] == [_hunk(78, 90)]
    assert "body" not in far and "suggestion" not in far
    assert other["fixHunks"] == []
    assert no_line["fixHunks"] == [] and "consequence" not in no_line


def test_t5_the_order_sidecar_carries_the_hunks(tmp_path):
    state = RD.new_state(TRD._cfg(fixerVendor="claude"))
    state["fixBatch"] = [dict(_finding("Near the top", 2), body="b1")]
    targets = RD._audit_targets(state, state["config"], {"f.py": [_hunk(1, 4)]})
    writes = RD._order_sidecar_writes(str(tmp_path), 2, RD.P_AUDITS, [targets[0]["id"]],
                                      {"targets": targets})
    assert len(writes) == 1
    doc = json.loads(writes[0][1].decode("utf-8"))
    assert doc["fixHunks"] == [_hunk(1, 4)] and doc["body"] == "b1"


def test_t5_the_audit_order_asks_for_unnamed_change():
    # the template's prose never names a contract field (test_round_orders); the driver renders the
    # contract block, so the field name is asserted on the rendered order, the instruction on the template
    with open(os.path.join(_LIB, os.pardir, "rubric", "orders", "dispatch-audits.md"),
              encoding="utf-8") as fh:
        text = " ".join(fh.read().split())
    assert "say so in plain words" in text and "behaviour the finding does not name" in text
    assert "`fixHunks`" in text
    with open(os.path.join(_HERE, "fixtures", "orders", "golden", "dispatch-audits.txt"),
              encoding="utf-8") as fh:
        rendered = fh.read()
    assert "Optional keys: " in rendered
    optional = [line for line in rendered.splitlines() if line.startswith("Optional keys: ")][0]
    assert "unnamedChange" in optional.split(": ", 1)[1].split(", ")
    assert "unnamedChange type: string" in rendered


# --- Part B: the ruling field -------------------------------------------------------------------

def _ruling_doc(entry):
    return {"_provenance": _provenance(), "rulings": [entry]}


def _guidance_entry(**extra):
    entry = {"id": "k", "ruling": "guidance", "reason": "owner call", "guidance": "keep retries"}
    entry.update(extra)
    return entry


def _oos_entry(**extra):
    entry = {"id": "k", "ruling": "out-of-scope", "reason": "later", "followUp": _follow_up()}
    entry.update(extra)
    return entry


@pytest.mark.parametrize("value", ["true", 1, None, "yes", [True]],
                         ids=["string-true", "int", "null", "string-yes", "list"])
def test_t4_edge7_allows_change_that_is_not_a_boolean_is_ruling_file_shape(value):
    parsed, _prov, reason = RD._validate_ruling_entries(
        _ruling_doc(_guidance_entry(allowsChange=value)))
    assert parsed is None and reason == RD.RULING_FILE_SHAPE


@pytest.mark.parametrize("value", [True, False], ids=["true", "false"])
def test_t4_edge7_allows_change_on_an_out_of_scope_entry_is_ruling_file_shape(value):
    parsed, _prov, reason = RD._validate_ruling_entries(_ruling_doc(_oos_entry(allowsChange=value)))
    assert parsed is None and reason == RD.RULING_FILE_SHAPE


@pytest.mark.parametrize("value", [True, False], ids=["true", "false"])
def test_t4_a_boolean_allows_change_on_guidance_is_accepted(value):
    parsed, _prov, reason = RD._validate_ruling_entries(
        _ruling_doc(_guidance_entry(allowsChange=value)))
    assert reason is None and parsed[0]["allowsChange"] is value


def test_t4_a_guidance_entry_without_allows_change_carries_none():
    parsed, _prov, reason = RD._validate_ruling_entries(_ruling_doc(_guidance_entry()))
    assert reason is None and "allowsChange" not in parsed[0]


def test_t4_the_rule_verb_copies_allows_change_onto_the_log_row(tmp_path):
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir)
    state = _staged_state([_finding("Null deref")])
    RD.save_state(session_dir, state)
    key = _key("Null deref")
    path = str(tmp_path / "rulings.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(_ruling_doc(_guidance_entry(id=key, allowsChange=True)), fh)
    assert RD.cmd_rule(session_dir, path, "owner").get("ok")
    ok, saved = RD.load_state(session_dir)
    assert ok
    assert saved["rulingsLog"][-1]["allowsChange"] is True
    assert RD._live_ruling_by_key(saved)[key]["allowsChange"] is True


def test_t4_the_rule_verb_refuses_a_string_allows_change_and_records_nothing(tmp_path):
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir)
    state = _staged_state([_finding("Null deref")])
    RD.save_state(session_dir, state)
    path = str(tmp_path / "rulings.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(_ruling_doc(_guidance_entry(id=_key("Null deref"), allowsChange="true")), fh)
    out = RD.cmd_rule(session_dir, path, "owner")
    assert not out.get("ok") and RD.RULING_FILE_SHAPE in json.dumps(out)
    ok, saved = RD.load_state(session_dir)
    assert ok and not saved.get("rulingsLog")


# --- Transport ----------------------------------------------------------------------------------

def _native_ruling_branch(**over):
    contract, reason = PC.payload_contract(PC.P_AUDITS)
    assert reason is None
    branch = {"resultKind": "ruling", "findings": None, "verdicts": None, "grouping": None,
              "investigated": ["f.py"], "id": "audit-seat",
              "ruling": contract["enums"]["ruling"][0], "reason": "grounds"}
    for opt in contract.get("optional") or ():
        branch[opt] = None
    branch.update(over)
    return branch


def _ruling_schema():
    return ERC.declared_schema("codex", ERC.RUN_KIND_REVIEW, expected_result_kind="ruling")


def test_t4_edge8_the_audit_contract_declares_unnamed_change_as_an_optional_string():
    contract, reason = PC.payload_contract(PC.P_AUDITS)
    assert reason is None
    assert "unnamedChange" in contract["optional"]
    assert contract["types"]["unnamedChange"] == "string"


def test_t4_edge8_a_native_audit_branch_with_a_null_unnamed_change_normalizes_and_parses():
    # axis: transport — a null optional audit member is read as absent, never a forfeit
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo2_c7_fix_scope.md
    branch = _native_ruling_branch()
    assert branch["unnamedChange"] is None
    ok, why = ERC.validate(_ruling_schema(), {"result": branch})
    assert ok, why
    normalized = ED._normalize_native_review_branch_for_parser(branch)
    assert "unnamedChange" not in normalized
    parsed = EA._REVIEW_CONTRACT_PARSERS["ruling"](normalized, None)
    assert parsed["ok"] is True
    assert "unnamedChange" not in parsed["ruling"]


def test_t4_edge8_a_string_unnamed_change_arrives_in_the_scrubbed_ruling_record():
    # axis: transport — the scrubber carries every optional audit member the contract declares
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo2_c7_fix_scope.md
    branch = _native_ruling_branch(unnamedChange=UNNAMED)
    ok, why = ERC.validate(_ruling_schema(), {"result": branch})
    assert ok, why
    normalized = ED._normalize_native_review_branch_for_parser(branch)
    assert normalized["unnamedChange"] == UNNAMED
    parsed = EA._REVIEW_CONTRACT_PARSERS["ruling"](normalized, None)
    assert parsed["ok"] is True
    assert parsed["ruling"]["unnamedChange"] == UNNAMED


def _objects_with_property(node, name, found):
    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict) and name in props:
            found.append(node)
        for value in node.values():
            _objects_with_property(value, name, found)
    elif isinstance(node, list):
        for value in node:
            _objects_with_property(value, name, found)
    return found


def test_t4_edge8_the_strict_schema_lists_unnamed_change_as_a_required_nullable_member():
    schema = _ruling_schema()
    ERC.assert_strict_mode_valid(schema)
    holders = _objects_with_property(schema, "unnamedChange", [])
    assert holders
    for holder in holders:
        assert "unnamedChange" in holder["required"]
        types = holder["properties"]["unnamedChange"]["type"]
        assert "string" in types and "null" in types
    for schema_ in (ERC.declared_schema("codex", ERC.RUN_KIND_REVIEW),
                    ERC.declared_schema("codex", ERC.RUN_KIND_REVIEW, expected_result_kind="findings")):
        ERC.assert_strict_mode_valid(schema_)


# --- Review round 1 regressions ------------------------------------------------------------------

def test_a_finding_raised_to_critical_after_its_out_of_scope_ruling_is_never_spent(
        empty_batch_calls):
    state = _staged_state([_finding("Gate bypass", severity="Important")])
    key = _key("Gate bypass")
    _decide(state, key, "out-of-scope", 1)
    RD._record_disposition(state, key, "out-of-scope", 1, outOfScopeReason="owner deferred it",
                           followUp=_follow_up())
    state["findings"][0]["severity"] = "Critical"  # re-raised as a blocker under the same key
    for rnd in (2, 3, 4):
        assert _offer(state, rnd) == ("queued", [key])
    assert empty_batch_calls == []
    assert _decisions(state, "out-of-scope-fix-spent") == []


def test_a_spent_episode_survives_a_lineage_root_change(empty_batch_calls):
    state = _staged_state([_finding("Gate bypass", severity="Critical")])
    key = _key("Gate bypass")
    _decide(state, key, "out-of-scope", 1)
    RD._record_disposition(state, key, "out-of-scope", 1, outOfScopeReason="owner deferred it",
                           followUp=_follow_up())
    assert _offer(state, 2) == ("queued", [key])
    # synthesis later merges the finding into another; the offer was logged under the old root
    state["findingLineage"] = {key: _key("Other finding", 9)}
    status, keys = _offer(state, 3)
    assert status == "excluded" and keys == []
    assert len(_decisions(state, "out-of-scope-fix-spent")) == 1


def test_audit_targets_carry_the_reviewed_hunks_beside_the_fix_hunks():
    state = RD.new_state(TRD._cfg(fixerVendor="claude"))
    state["fixBatch"] = [_finding("Near the top", 2), _finding("Far down", 80)]
    head = {"f.py": [_hunk(1, 4), _hunk(78, 90)]}
    reviewed = {"f.py": [_hunk(1, 3), _hunk(200, 210)]}
    top, far = RD._audit_targets(state, state["config"], head, reviewed_hunks_map=reviewed)
    assert top["reviewedHunks"] == [_hunk(1, 3)]
    assert far["reviewedHunks"] == []
    assert RD._audit_targets(state, state["config"], head)[0]["reviewedHunks"] == []


def test_the_audit_order_names_the_reviewed_hunks():
    text = open(os.path.join(os.path.dirname(__file__), "..", "..", "rubric", "orders",
                             "dispatch-audits.md")).read()
    assert "reviewedHunks" in text


@pytest.mark.parametrize("value", [[], 5, {"a": 1}, True])
def test_the_submit_guard_refuses_a_non_string_unnamed_change(value):
    targets = [{"id": "a"}]
    ok = {"results": [{"id": "a", "ruling": "discharged", "reason": "fixed"}]}
    assert RD.audit_results_fault(ok, targets) is None
    ok["results"][0]["unnamedChange"] = "it also stops retrying"
    assert RD.audit_results_fault(ok, targets) is None
    ok["results"][0]["unnamedChange"] = None
    assert RD.audit_results_fault(ok, targets) is None
    ok["results"][0]["unnamedChange"] = value
    fault = RD.audit_results_fault(ok, targets)
    assert fault and "unnamedChange" in fault
