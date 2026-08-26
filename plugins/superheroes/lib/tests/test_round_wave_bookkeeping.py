"""#1107 WO-B: fix-batch stall bookkeeping and per-round verifier-wave attempt allocation."""
import ast
import importlib.util
import json
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")
RR = _load("round_records")
FI = _load("finding_identity")


def _cfg(**over):
    base = {"leg": "code", "vendors": ["claude", "codex"], "diff": "d", "fixerVendor": "claude"}
    base.update(over)
    return base


def _finding(file="f.py", line=1, title="bug", severity="Important", **extra):
    f = {"file": file, "line": line, "title": title, "severity": severity}
    f.update(extra)
    return f


def test_stall_self_recovery_does_not_reemit_discharged_fix_batch():
    # axis: stall self-recovery must not seed _fixBatch from the prior round's discharged fixBatch
    ident = FI.finding_identity(_finding(title="stale"))
    discharged = {"id": "%s@L1" % ident, "identity": ident, "file": "f.py", "line": 1,
                  "title": "stale", "severity": "Important"}
    state = RD.new_state(_cfg())
    state["fixBatch"] = [dict(discharged)]
    state["_auditTargets"] = [discharged]
    state["_auditOutcome"] = {"notDischarged": [], "discharged": [discharged["id"]]}
    state["selfRecovered"] = False
    breaker = {"reason": "audit-stall", "detail": "x", "stalledIdentities": [ident]}
    RD._handle_stall(state, state["config"], breaker)
    assert state.get("step") != RD.P_FIXER
    assert state.get("_fixBatch") != state["fixBatch"]


def test_stall_self_recovery_parks_when_open_set_unresolvable():
    # axis: legacy persisted session with audit history and an unreadable outcome must park
    state = RD.new_state(_cfg())
    state["fixBatch"] = []
    state["auditRounds"] = [{"round": 1, "outcomes": [
        {"identity": "lib/a.py::x", "ruling": "not-discharged"}]}]
    state["selfRecovered"] = False
    breaker = {"reason": "audit-stall", "detail": "x", "stalledIdentities": ["lib/a.py::x"]}
    RD._handle_stall(state, state["config"], breaker)
    assert state["terminal"] == "cannot-certify"
    assert state["step"] == RD.P_TERMINAL
    assert any(d.get("kind") == "cannot-certify" for d in state.get("decisions") or [])


def test_stall_self_recovery_routes_open_important_not_converged():
    # axis: discharged stalled targets with an open Important still not-discharged must fix, not certify
    ident = FI.finding_identity(_finding(title="open-important"))
    open_target = {"id": "%s@L1" % ident, "identity": ident, "file": "f.py", "line": 1,
                   "title": "open-important", "severity": "Important"}
    state = RD.new_state(_cfg())
    state["_auditTargets"] = [open_target]
    state["_auditOutcome"] = {"notDischarged": [open_target["id"]], "discharged": []}
    state["selfRecovered"] = False
    other_ident = FI.finding_identity(_finding(title="stalled-other"))
    breaker = {"reason": "audit-stall", "detail": "x", "stalledIdentities": [other_ident]}
    RD._handle_stall(state, state["config"], breaker)
    assert state.get("step") == RD.P_FIXER
    assert state.get("terminal") != "converged"
    assert state.get("_fixBatch")


def test_second_verifier_wave_in_same_round_gets_fresh_attempt(tmp_path):
    # axis: a second wave after an accepted wave gets a fresh attempt
    d = str(tmp_path)
    state = RD.new_state(_cfg())
    state["round"] = 2
    state["step"] = RD.P_VERIFIERS
    state["_toVerify"] = [_finding(title="new-issue")]
    state["lastAccepted"] = {"phase": RD.P_SCOPED, "round": 2, "attempt": 0, "artifactHash": "x"}
    RD.save_state(d, state)
    RD._journal_append(d, {"cmd": "submit", "phase": RD.P_VERIFIERS, "round": 2, "attempt": 0,
                           "outcome": "accepted"})
    seat = "verifier:f.py:0"
    skey = RR.storage_key(seat)
    spath = RR.store_path(d, 2, RD.P_VERIFIERS, skey, 0)
    os.makedirs(os.path.dirname(spath), exist_ok=True)
    with open(spath, "w", encoding="utf-8") as fh:
        json.dump({"seat": seat, "attempt": 0, "round": 2, "phase": RD.P_VERIFIERS,
                   "payloadSha256": "deadbeef"}, fh)
    n = RD.cmd_next(d)
    assert n["ok"], n
    assert n["phase"] == RD.P_VERIFIERS
    assert n["attempt"] == 1


def test_reemit_of_an_unaccepted_wave_reuses_its_attempt(tmp_path):
    # axis: a landing is not an acceptance, so a re-emit must reuse the attempt its seats landed under
    d = str(tmp_path)
    state = RD.new_state(_cfg())
    state["round"] = 2
    state["step"] = RD.P_VERIFIERS
    state["_toVerify"] = [_finding(title="new-issue")]
    state["lastAccepted"] = {"phase": RD.P_SCOPED, "round": 2, "attempt": 0, "artifactHash": "x"}
    RD.save_state(d, state)
    RD._journal_append(d, {"cmd": "next", "phase": RD.P_VERIFIERS, "round": 2, "attempt": 0,
                           "outcome": "emitted"})
    seat = "verifier:f.py:0"
    skey = RR.storage_key(seat)
    spath = RR.store_path(d, 2, RD.P_VERIFIERS, skey, 0)
    os.makedirs(os.path.dirname(spath), exist_ok=True)
    with open(spath, "w", encoding="utf-8") as fh:
        json.dump({"seat": seat, "attempt": 0, "round": 2, "phase": RD.P_VERIFIERS,
                   "payloadSha256": "deadbeef"}, fh)
    n = RD.cmd_next(d)
    assert n["ok"], n
    assert n["phase"] == RD.P_VERIFIERS
    assert n["attempt"] == 0


def test_next_reemit_preserves_pending_attempt(tmp_path):
    # axis: idempotent pending re-emit must return the same attempt without recomputing allocation
    d = str(tmp_path)
    n1 = RD.cmd_next(d, _cfg())
    assert n1["ok"], n1
    n2 = RD.cmd_next(d)
    assert n2["ok"], n2
    assert n1["attempt"] == n2["attempt"]
    assert n1["phase"] == n2["phase"]
    assert n1["expectedStateHash"] == n2["expectedStateHash"]


def test_stall_malformed_not_discharged_member_parks_not_raises():
    # axis: malformed notDischarged member must park via unresolvable tri-state, never raise
    state = RD.new_state(_cfg())
    state["_auditOutcome"] = {"notDischarged": [{}]}
    state["auditRounds"] = [{"round": 1, "outcomes": [
        {"identity": "lib/a.py::x", "ruling": "not-discharged"}]}]
    state["selfRecovered"] = False
    breaker = {"reason": "audit-stall", "detail": "x", "stalledIdentities": ["lib/a.py::x"]}
    RD._handle_stall(state, state["config"], breaker)
    assert state.get("terminal")
    assert state["step"] == RD.P_TERMINAL


def test_not_discharged_to_open_id_set_single_constructor():
    # Invariant: every conversion of _auditOutcome.notDischarged into an open-id set happens at
    # one validated construction boundary — no raw set(notDischarged) elsewhere in round_driver.
    path = os.path.join(_LIB, "round_driver.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)

    def _expr_references_not_discharged(expr):
        for sub in ast.walk(expr):
            if isinstance(sub, ast.Attribute) and sub.attr == "notDischarged":
                return True
            if isinstance(sub, ast.Call):
                func = sub.func
                if isinstance(func, ast.Attribute) and func.attr == "get":
                    for arg in sub.args:
                        if isinstance(arg, ast.Constant) and arg.value == "notDischarged":
                            return True
                    for kw in sub.keywords:
                        if kw.arg in (None, "key") and isinstance(kw.value, ast.Constant):
                            if kw.value.value == "notDischarged":
                                return True
        return False

    converters = []

    class _Visitor(ast.NodeVisitor):
        def __init__(self):
            self._current_func = None
            self._nd_names = set()

        def visit_FunctionDef(self, node):
            prev_func = self._current_func
            prev_names = self._nd_names
            self._current_func = node.name
            self._nd_names = set()
            if node.name == "_open_audit_ids_from_not_discharged" and node.args.args:
                self._nd_names.add(node.args.args[0].arg)
            self.generic_visit(node)
            self._current_func = prev_func
            self._nd_names = prev_names

        def visit_Assign(self, node):
            if _expr_references_not_discharged(node.value):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self._nd_names.add(target.id)
            self.generic_visit(node)

        def visit_Call(self, node):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "set" and node.args:
                arg = node.args[0]
                derived = _expr_references_not_discharged(arg)
                if isinstance(arg, ast.Name) and arg.id in self._nd_names:
                    derived = True
                if derived:
                    converters.append(self._current_func)
            self.generic_visit(node)

    _Visitor().visit(tree)
    assert converters == ["_open_audit_ids_from_not_discharged"]


@pytest.mark.parametrize("bad_member", [{}, 0, None])
def test_stall_not_discharged_bad_member_type_parks(bad_member):
    # axis: any non-str notDischarged member routes unresolvable → park, never raises
    state = RD.new_state(_cfg())
    state["_auditOutcome"] = {"notDischarged": [bad_member]}
    state["auditRounds"] = [{"round": 1, "outcomes": [
        {"identity": "lib/a.py::x", "ruling": "not-discharged"}]}]
    state["selfRecovered"] = False
    breaker = {"reason": "audit-stall", "detail": "x", "stalledIdentities": ["lib/a.py::x"]}
    RD._handle_stall(state, state["config"], breaker)
    assert state.get("terminal")
    assert state["step"] == RD.P_TERMINAL
