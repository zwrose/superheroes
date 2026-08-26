"""#915: per-location audit target ids, line-less stall identity, and fail-closed duplicates."""
import importlib.util
import inspect
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
AU = _load("audits")
CB = _load("circuit_breaker")
FI = _load("finding_identity")
RR = _load("round_records")


def _cfg(**over):
    base = {"leg": "code", "vendors": ["claude", "codex"], "diff": "d", "fixerVendor": "codex"}
    base.update(over)
    return base


def _finding(file="f.py", line=1, title="bug", severity="Important", **extra):
    f = {"file": file, "line": line, "title": title, "severity": severity}
    f.update(extra)
    return f


# --- D1: judgment ids byte-identical ------------------------------------------

def test_judgment_row_ids_occurrence_suffix_same_location():
    # axis: repeated same-location judgment findings must get #1, #2, … suffixes
    f = _finding(line=5, title="dup")
    loc = RD._location_id(f)
    findings = [f, dict(f), dict(f)]
    assert RD._judgment_row_ids(findings) == [loc, "%s#1" % loc, "%s#2" % loc]


# --- D2: unique ids + identity ------------------------------------------------

def test_audit_targets_distinct_ids_same_title_different_lines():
    # axis: same line-less identity at different lines must get distinct per-location ids
    state = RD.new_state(_cfg())
    state["fixBatch"] = [_finding(line=2, title="unchecked input"),
                         _finding(line=3, title="unchecked input")]
    targets = RD._audit_targets(state, state["config"], {})
    assert len(targets) == 2
    assert targets[0]["id"] != targets[1]["id"]
    assert targets[0]["identity"] == targets[1]["identity"]
    assert targets[0]["id"] == "%s@L2" % targets[0]["identity"]
    assert targets[1]["id"] == "%s@L3" % targets[1]["identity"]


def test_audit_targets_occurrence_suffix_same_location():
    # axis: repeated same-location findings must get #1, #2, … suffixes (not all #1)
    state = RD.new_state(_cfg())
    state["fixBatch"] = [_finding(line=5, title="dup"), _finding(line=5, title="dup"),
                         _finding(line=5, title="dup")]
    targets = RD._audit_targets(state, state["config"], {})
    loc = RD._location_id(_finding(line=5, title="dup"))
    ids = [t["id"] for t in targets]
    assert ids == [loc, "%s#1" % loc, "%s#2" % loc]
    assert len(set(ids)) == 3


def test_location_id_stable_when_line_missing():
    # axis: missing line must still yield a stable @LNone location id
    f = {"file": "a.py", "title": "x"}
    assert RD._location_id(f) == "%s@LNone" % FI.finding_identity(f)


# --- D3: outcomes carry line-less identity ------------------------------------

def test_fold_audits_outcomes_identity_is_line_less():
    # axis: folded audit outcomes must carry line-less identity for stall alias matching
    state = RD.new_state(_cfg())
    state["fixBatch"] = [_finding(line=7, title="leak")]
    state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
    tgt = state["_auditTargets"][0]
    RD._fold_audits(state, state["config"], {"results": [
        {"id": tgt["id"], "ruling": "not-discharged", "reason": "still broken"}]})
    outcome = state["auditRounds"][-1]["outcomes"][0]
    assert outcome["identity"] == tgt["identity"]
    assert outcome["identity"] == FI.finding_identity(tgt)
    assert "@L" not in outcome["identity"]


def test_fold_audits_outcome_identity_classkey_free():
    """Without classKey on the target, stall identity must still be line-less."""
    # axis: classKey absence must not block line-less identity on folded outcomes
    state = RD.new_state(_cfg())
    loc_id = "%s@L9" % FI.finding_identity(_finding(line=9, title="plain"))
    ident = FI.finding_identity(_finding(line=9, title="plain"))
    state["_auditTargets"] = [{"id": loc_id, "identity": ident, "file": "f.py", "line": 9,
                               "title": "plain", "severity": "Important", "independence": "n/a"}]
    RD._fold_audits(state, state["config"], {"results": [
        {"id": loc_id, "ruling": "not-discharged", "reason": "nope"}]})
    outcome = state["auditRounds"][-1]["outcomes"][0]
    assert outcome["identity"] == ident
    assert "classKey" not in outcome or outcome.get("classKey") is None


# --- D4: duplicate target id fail-closed --------------------------------------

def test_apply_audit_results_duplicate_target_ids_fail_closed():
    # axis: colliding per-location ids must fail-closed for every duplicate, not collapse to one
    collided = "f.py::bug@L1"
    targets = [{"id": collided, "file": "f.py", "line": 1, "title": "bug"},
               {"id": collided, "file": "f.py", "line": 2, "title": "bug"}]
    results = [{"id": collided, "ruling": "discharged", "reason": "ok"}]
    out = AU.apply_audit_results(targets, results)
    assert out["ambiguous"] == [collided]
    assert out["discharged"] == []
    assert out["notDischarged"] == [collided, collided]
    assert len(out["audits"]) == 2
    assert {a["identity"] for a in out["audits"]} == {FI.finding_identity(t) for t in targets}
    assert {a["line"] for a in out["audits"]} == {1, 2}
    assert all(a["ruling"] == "not-discharged" for a in out["audits"])


def test_apply_audit_results_threads_explicit_identity():
    # axis: authoritative identity field must pass through unchanged, not be recomputed
    explicit = "custom::identity"
    t = {"id": "v0", "identity": explicit, "file": "f.py", "line": 3,
         "title": "t", "severity": "Important"}
    out = AU.apply_audit_results([t], [])
    assert out["audits"][0]["identity"] == explicit
    assert out["audits"][0]["identity"] != FI.finding_identity(t)


def test_apply_audit_results_derives_identity_when_absent():
    # axis: absent identity must fall back to finding_identity derivation
    t = {"id": "v0", "file": "f.py", "line": 3, "title": "t", "severity": "Important"}
    out = AU.apply_audit_results([t], [])
    assert out["audits"][0]["identity"] == FI.finding_identity(t)


def test_apply_audit_results_line_none_when_absent():
    # axis: missing line on target must yield None on audit entry, never KeyError
    t = {"id": "v0", "file": "f.py", "title": "t", "severity": "Important"}
    out = AU.apply_audit_results([t], [])
    assert out["audits"][0]["line"] is None


# --- D5.1: critical severity lookup via target id ------------------------------

def test_not_discharged_critical_reaches_surfaced_since_last_panel():
    # axis: Critical severity lookup must key on per-location target id, not line-less identity
    state = RD.new_state(_cfg(maxRounds=20))
    f = _finding(severity="Critical", line=1)
    state["fixBatch"] = [f]
    state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
    tid = state["_auditTargets"][0]["id"]
    state["_auditOutcome"] = {"notDischarged": [tid], "discharged": []}
    state["auditRounds"] = [{"round": 2, "outcomes": []}]
    state["findings"] = []
    state["confirmations"] = 0
    state["surfacedSinceLastPanel"] = []
    RD._settle_delta(state, state["config"])
    assert "Critical" in state.get("surfacedSinceLastPanel", [])


def test_not_discharged_important_does_not_surface_critical():
    # axis: non-Critical not-discharged must not be misclassified as Critical
    state = RD.new_state(_cfg(maxRounds=20))
    f = _finding(severity="Important", line=1)
    state["fixBatch"] = [f]
    state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
    tid = state["_auditTargets"][0]["id"]
    state["confirmations"] = 0
    state["surfacedSinceLastPanel"] = []
    state["round"] = 3
    state["findings"] = []
    state["fullPanelRan"] = False
    state["auditRounds"] = [{"round": 2, "outcomes": [
        {"identity": FI.finding_identity(f), "ruling": "discharged"}]}]
    state["_auditOutcome"] = {"notDischarged": [tid], "discharged": []}
    RD._settle_delta(state, state["config"])
    assert "Critical" not in state.get("surfacedSinceLastPanel", [])
    state["_auditOutcome"] = {"notDischarged": [], "discharged": [tid]}
    state["findings"] = []
    state.pop("_fixBatch", None)
    state["step"] = None
    state["terminal"] = None
    state["_changedSubjects"] = []
    state["_changedSubjectsSincePanel"] = []
    RD._settle_delta(state, state["config"])
    assert not any(d["kind"] == "confirmation-rearm" for d in state["decisions"])


def test_critical_not_discharged_rearms_confirmation():
    # axis: discharged-then-not-discharged Critical must re-arm confirmation via per-location id
    state = RD.new_state(_cfg(maxRounds=20))
    f = _finding(severity="Critical", line=1)
    state["fixBatch"] = [f]
    state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
    tid = state["_auditTargets"][0]["id"]
    state["confirmations"] = 0
    state["surfacedSinceLastPanel"] = []
    state["round"] = 3
    state["findings"] = []
    state["fullPanelRan"] = False
    state["auditRounds"] = [{"round": 2, "outcomes": [
        {"identity": FI.finding_identity(f), "ruling": "discharged"}]}]
    state["_auditOutcome"] = {"notDischarged": [tid], "discharged": []}
    RD._settle_delta(state, state["config"])
    assert "Critical" in state["surfacedSinceLastPanel"]
    state["_auditOutcome"] = {"notDischarged": [], "discharged": [tid]}
    state["findings"] = []
    state.pop("_fixBatch", None)
    state["step"] = None
    state["terminal"] = None
    RD._settle_delta(state, state["config"])
    assert state["step"] == RD.P_PANEL
    assert any(d["kind"] == "confirmation-rearm" for d in state["decisions"])


# --- D5.2/D5.3: alias-based stall selection -----------------------------------

def test_handle_stall_unions_stalled_alias_with_not_discharged_targets():
    # axis (AMENDED #1165, was PR #924 / issue #915 "stall self-recovery must match stalled alias,
    # not every target in the batch", len(batch) == 1): stalled alias PLUS not-discharged audit
    # targets; never new blocking findings.
    # What #915 protected: self-recovery must not re-dispatch every member of the prior fix batch —
    # in particular not a target the audit already DISCHARGED. The widening preserves that intent
    # because it admits only targets the audit itself left not-discharged; discharged siblings stay
    # excluded (pinned by test_handle_stall_excludes_discharged_sibling_same_identity).
    class_key = "Security::CWE-401::orig"
    stalled_target = {
        "id": "f.py::old title@L1", "identity": "f.py::old title",
        "file": "f.py", "line": 1, "title": "new title", "severity": "Important",
        "classKey": class_key, "dimension": "Security", "taxonomy": "CWE-401",
    }
    other = {
        "id": "g.py::other@L2", "identity": "g.py::other",
        "file": "g.py", "line": 2, "title": "other", "severity": "Important",
        "classKey": "Code::misc::other", "dimension": "Code", "taxonomy": "misc",
    }
    state = RD.new_state(_cfg())
    state["_auditTargets"] = [stalled_target, other]
    state["fixBatch"] = [dict(stalled_target), dict(other)]
    state["_auditOutcome"] = {"notDischarged": [stalled_target["id"], other["id"]],
                              "discharged": []}
    breaker = {"reason": "audit-stall", "detail": "x",
               "stalledIdentities": [class_key]}
    RD._handle_stall(state, state["config"], breaker)
    batch = state.get("_fixBatch") or []
    assert len(batch) == 2
    assert {b["id"] for b in batch} == {stalled_target["id"], other["id"]}


def test_handle_stall_unions_exclude_new_blocking_findings():
    # axis: stall self-recovery union admits stalled and not-discharged audit targets only
    class_key = "Security::CWE-401::orig"
    stalled_target = {
        "id": "f.py::old title@L1", "identity": "f.py::old title",
        "file": "f.py", "line": 1, "title": "new title", "severity": "Important",
        "classKey": class_key, "dimension": "Security", "taxonomy": "CWE-401",
    }
    other = {
        "id": "g.py::other@L2", "identity": "g.py::other",
        "file": "g.py", "line": 2, "title": "other", "severity": "Important",
        "classKey": "Code::misc::other", "dimension": "Code", "taxonomy": "misc",
    }
    new_blocker = _finding(file="h.py", line=9, title="fresh blocker", severity="Critical")
    state = RD.new_state(_cfg())
    state["_auditTargets"] = [stalled_target, other]
    state["fixBatch"] = [dict(stalled_target), dict(other)]
    state["_auditOutcome"] = {"notDischarged": [stalled_target["id"], other["id"]],
                              "discharged": []}
    state["findings"] = [dict(new_blocker)]
    breaker = {"reason": "audit-stall", "detail": "x",
               "stalledIdentities": [class_key]}
    RD._handle_stall(state, state["config"], breaker)
    batch = state.get("_fixBatch") or []
    assert len(batch) == 2
    assert {b["id"] for b in batch} == {stalled_target["id"], other["id"]}
    batch_files = {b.get("file") for b in batch}
    assert new_blocker["file"] not in batch_files


def test_stall_batch_never_drops_a_second_open_target_regression_1165():
    # axis: before #1165 a second open not-discharged target was dropped (batch was ['a@L1'] only)
    target_a = {
        "id": "a.py::first@L1", "identity": "a.py::first",
        "file": "a.py", "line": 1, "title": "first", "severity": "Important",
        "classKey": "Code::a::first", "dimension": "Code", "taxonomy": "a",
    }
    target_b = {
        "id": "b.py::second@L2", "identity": "b.py::second",
        "file": "b.py", "line": 2, "title": "second", "severity": "Important",
        "classKey": "Code::b::second", "dimension": "Code", "taxonomy": "b",
    }
    state = RD.new_state(_cfg())
    state["_auditTargets"] = [target_a, target_b]
    state["fixBatch"] = [dict(target_a), dict(target_b)]
    state["_auditOutcome"] = {"notDischarged": [target_a["id"], target_b["id"]],
                              "discharged": []}
    breaker = {"reason": "audit-stall", "detail": "x",
               "stalledIdentities": [target_a["classKey"]]}
    RD._handle_stall(state, state["config"], breaker)
    assert state["step"] == RD.P_FIXER
    batch = state.get("_fixBatch") or []
    assert {b["id"] for b in batch} == {target_a["id"], target_b["id"]}


def test_handle_stall_malformed_not_discharged_parks_with_stalled_target():
    # axis: present-but-unreadable open set must fail closed, never dispatch a partial batch
    stalled_target = {
        "id": "f.py::old title@L1", "identity": "f.py::old title",
        "file": "f.py", "line": 1, "title": "new title", "severity": "Important",
        "classKey": "Security::CWE-401::orig", "dimension": "Security", "taxonomy": "CWE-401",
    }
    ident = FI.finding_identity(stalled_target)
    state = RD.new_state(_cfg())
    state["_auditTargets"] = [stalled_target]
    state["fixBatch"] = [dict(stalled_target)]
    state["_auditOutcome"] = {"notDischarged": [{}]}
    breaker = {"reason": "audit-stall", "detail": "x",
               "stalledIdentities": [ident]}
    RD._handle_stall(state, state["config"], breaker)
    assert state["step"] == RD.P_TERMINAL
    assert state["terminal"] == "cannot-certify"


def test_handle_stall_uncomposable_open_id_refuses():
    # axis: an open target that cannot be composed into the batch must refuse, never partial dispatch
    class_key = "Security::CWE-401::orig"
    stalled_target = {
        "id": "f.py::old title@L1", "identity": "f.py::old title",
        "file": "f.py", "line": 1, "title": "new title", "severity": "Important",
        "classKey": class_key, "dimension": "Security", "taxonomy": "CWE-401",
    }
    phantom_id = "z.py::missing@L99"
    state = RD.new_state(_cfg())
    state["_auditTargets"] = [stalled_target]
    state["fixBatch"] = [dict(stalled_target)]
    state["_auditOutcome"] = {"notDischarged": [stalled_target["id"], phantom_id]}
    breaker = {"reason": "audit-stall", "detail": "x",
               "stalledIdentities": [class_key]}
    RD._handle_stall(state, state["config"], breaker)
    assert state["step"] == RD.P_TERMINAL
    assert state["terminal"] == "cannot-certify"


def test_stalled_critical_uses_alias_not_line_less_identity():
    # axis: stalled Critical cap lookup must match classKey alias, not retitled line-less identity
    class_key = "Security::CWE-401::crit"
    target = {
        "id": "f.py::retitled@L1", "identity": "f.py::retitled",
        "file": "f.py", "line": 1, "title": "retitled", "severity": "Critical",
        "classKey": class_key, "dimension": "Security", "taxonomy": "CWE-401",
    }
    state = RD.new_state(_cfg())
    state["_auditTargets"] = [target]
    state["fixBatch"] = [dict(target)]
    state["_auditOutcome"] = {"notDischarged": [target["id"]], "discharged": []}
    breaker = {"stalledIdentities": [class_key]}
    crit = RD._stalled_critical(state, state["config"], breaker)
    assert crit == [target]


def test_handle_stall_excludes_discharged_sibling_same_identity():
    # axis: stall self-recovery must not re-open a discharged sibling sharing line-less identity
    ident = FI.finding_identity(_finding(file="lib/a.py", title="unchecked input", line=10))
    open_tgt = {"id": "lib/a.py::unchecked input@L10", "identity": ident,
                "file": "lib/a.py", "line": 10, "title": "unchecked input",
                "severity": "Important"}
    closed_tgt = {"id": "lib/a.py::unchecked input@L400", "identity": ident,
                  "file": "lib/a.py", "line": 400, "title": "unchecked input",
                  "severity": "Important"}
    state = RD.new_state(_cfg())
    state["_auditTargets"] = [closed_tgt, open_tgt]
    state["fixBatch"] = [dict(closed_tgt), dict(open_tgt)]
    state["_auditOutcome"] = {"notDischarged": [open_tgt["id"]],
                              "discharged": [closed_tgt["id"]]}
    breaker = {"reason": "audit-stall", "detail": "x", "stalledIdentities": [ident]}
    RD._handle_stall(state, state["config"], breaker)
    batch = state.get("_fixBatch") or []
    assert len(batch) == 1
    assert batch[0]["id"] == open_tgt["id"]


def test_stalled_critical_excludes_discharged_sibling_same_identity():
    # axis: stalled Critical cap must not count a discharged Critical sibling at another line
    ident = FI.finding_identity(_finding(file="lib/a.py", title="unchecked input", line=10,
                                         severity="Critical"))
    open_tgt = {"id": "lib/a.py::unchecked input@L10", "identity": ident,
                "file": "lib/a.py", "line": 10, "title": "unchecked input",
                "severity": "Critical"}
    closed_tgt = {"id": "lib/a.py::unchecked input@L400", "identity": ident,
                  "file": "lib/a.py", "line": 400, "title": "unchecked input",
                  "severity": "Critical"}
    state = RD.new_state(_cfg())
    state["_auditTargets"] = [closed_tgt, open_tgt]
    state["fixBatch"] = [dict(closed_tgt), dict(open_tgt)]
    state["_auditOutcome"] = {"notDischarged": [open_tgt["id"]],
                              "discharged": [closed_tgt["id"]]}
    breaker = {"stalledIdentities": [ident]}
    crit = RD._stalled_critical(state, state["config"], breaker)
    assert crit == [open_tgt]


def test_stalled_critical_important_open_critical_discharged_returns_empty():
    # axis: discharged Critical sibling must not be reported as open Critical at the cap
    ident = FI.finding_identity(_finding(file="lib/a.py", title="unchecked input", line=10))
    open_tgt = {"id": "lib/a.py::unchecked input@L10", "identity": ident,
                "file": "lib/a.py", "line": 10, "title": "unchecked input",
                "severity": "Important"}
    closed_tgt = {"id": "lib/a.py::unchecked input@L400", "identity": ident,
                  "file": "lib/a.py", "line": 400, "title": "unchecked input",
                  "severity": "Critical"}
    state = RD.new_state(_cfg())
    state["_auditTargets"] = [closed_tgt, open_tgt]
    state["fixBatch"] = [dict(closed_tgt), dict(open_tgt)]
    state["_auditOutcome"] = {"notDischarged": [open_tgt["id"]],
                              "discharged": [closed_tgt["id"]]}
    breaker = {"stalledIdentities": [ident]}
    crit = RD._stalled_critical(state, state["config"], breaker)
    assert crit == []


def test_stalled_callers_share_helper_no_duplicate_alias_loops():
    # axis: stall selection must live in one helper — no independent alias loops in callers;
    # module-wide census (not per-caller inspect)
    import ast
    import inspect
    rd_path = os.path.join(_LIB, "round_driver.py")
    with open(rd_path, encoding="utf-8") as fh:
        source = fh.read()
    tree = ast.parse(source, filename=rd_path)
    lines = source.splitlines(True)
    alias_fns = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        # Slice starts at `def`; decorator lines above lineno are excluded.
        if node.end_lineno is None:
            fn_src = ""
        else:
            fn_src = "".join(lines[node.lineno - 1:node.end_lineno])
        if "audit_target_aliases" in fn_src:
            alias_fns.append(node.name)
    assert alias_fns == ["_stalled_open_targets"], (
        "audit_target_aliases must appear only in _stalled_open_targets, found: %s" % alias_fns)
    compose_src = inspect.getsource(RD._compose_stall_fix_batch)
    assert "_stalled_open_targets" in compose_src
    stall_src = inspect.getsource(RD._handle_stall)
    # the stall-MENU half still selects through the shared helper; the RECOVERY half's
    # delegation is pinned separately in test_stall_decomposition.py.
    assert "_stalled_open_targets" in stall_src
    crit_src = inspect.getsource(RD._stalled_critical)
    assert "_stalled_open_targets" in crit_src


def test_handle_stall_legacy_no_audit_outcome_uses_alias_only():
    # axis: legacy session without _auditOutcome must still select stalled alias (not empty batch)
    ident = FI.finding_identity(_finding(title="stale", line=1))
    target = {"id": "f.py::stale@L1", "identity": ident,
              "file": "f.py", "line": 1, "title": "stale", "severity": "Important"}
    state = RD.new_state(_cfg())
    state["_auditTargets"] = [target]
    state["fixBatch"] = [dict(target)]
    breaker = {"reason": "audit-stall", "detail": "x", "stalledIdentities": [ident]}
    RD._handle_stall(state, state["config"], breaker)
    batch = state.get("_fixBatch") or []
    assert len(batch) == 1
    assert batch[0]["id"] == target["id"]


def test_audit_target_ids_disjoint_from_roster_occurrence_suffix():
    # axis: #n occurrence mint for repeated locations must not collide with roster slot suffixes
    state = RD.new_state(_cfg())
    state["fixBatch"] = [_finding(line=5, title="dup"), _finding(line=5, title="dup")]
    targets = RD._audit_targets(state, state["config"], {})
    ids = [t["id"] for t in targets]
    assert len(set(ids)) == len(ids)
    roster = [t["id"] for t in targets]
    assert RR.roster_slots(roster) == [(ids[0], 0), (ids[1], 0)]


# --- D6: settle_delta dedupe both directions ----------------------------------

def test_settle_delta_different_line_does_not_drop_unresolved_target():
    # axis: settle_delta must retain unresolved target when new blocker differs only by line
    ident = FI.finding_identity(_finding(title="shared", line=1))
    nd_target = {"id": "%s@L1" % ident, "identity": ident, "file": "f.py", "line": 1,
                 "title": "shared", "severity": "Important"}
    new_blocker = _finding(title="shared", line=9, severity="Important")
    state = RD.new_state(_cfg(maxRounds=20))
    state["_auditTargets"] = [nd_target]
    state["_auditOutcome"] = {"notDischarged": [nd_target["id"]], "discharged": []}
    state["auditRounds"] = [{"round": 2, "outcomes": []}]
    state["findings"] = [dict(new_blocker)]
    RD._settle_delta(state, state["config"])
    batch = state.get("_fixBatch") or []
    ids = {b.get("id") for b in batch if isinstance(b, dict)}
    assert nd_target["id"] in ids or any(
        b.get("identity") == ident and b.get("line") == 1 for b in batch)


def test_settle_delta_same_location_does_not_double_add():
    # axis: settle_delta must not double-add when new blocker shares location with unresolved target
    ident = FI.finding_identity(_finding(title="same", line=4))
    nd_target = {"id": "%s@L4" % ident, "identity": ident, "file": "f.py", "line": 4,
                 "title": "same", "severity": "Important"}
    same_blocker = _finding(title="same", line=4, severity="Important")
    state = RD.new_state(_cfg(maxRounds=20))
    state["_auditTargets"] = [nd_target]
    state["_auditOutcome"] = {"notDischarged": [nd_target["id"]], "discharged": []}
    state["auditRounds"] = [{"round": 2, "outcomes": []}]
    state["findings"] = [dict(same_blocker)]
    RD._settle_delta(state, state["config"])
    batch = state.get("_fixBatch") or []
    keys = [(b.get("identity") or FI.finding_identity(b), b.get("line"))
            for b in batch if isinstance(b, dict)]
    assert keys.count((ident, 4)) == 1


def test_union_open_blockers_dedupe_rule_single_home():
    # axis: per-location dedupe rule has exactly one home in round_driver
    rd_path = os.path.join(_LIB, "round_driver.py")
    with open(rd_path, encoding="utf-8") as fh:
        source = fh.read()
    assert source.count('f.get("identity") or finding_identity(f)') == 1
    assert "_union_open_blockers" in source
    settle_src = inspect.getsource(RD._settle_delta)
    compose_src = inspect.getsource(RD._compose_stall_fix_batch)
    assert "_union_open_blockers" in settle_src
    assert "_union_open_blockers" in compose_src
    helper_src = inspect.getsource(RD._union_open_blockers)
    assert 'f.get("identity") or finding_identity(f)' in helper_src


# --- circuit_breaker audit_target_aliases -------------------------------------

def test_audit_target_aliases_agrees_with_outcome_aliases_for_identity_bearing_records():
    # axis: identity-bearing records must agree — id-only asymmetry is tested separately
    cases = [
        ({"id": "f.py::t@L1", "identity": "f.py::t", "title": "t",
          "classKey": "k", "dimension": "Security", "taxonomy": "CWE-1"},
         {"identity": "f.py::t", "title": "t",
          "classKey": "k", "dimension": "Security", "taxonomy": "CWE-1",
          "ruling": "not-discharged"}),
        ({"file": "lib/a.py", "title": "unchecked input", "severity": "Critical"},
         {"file": "lib/a.py", "title": "unchecked input", "ruling": "not-discharged"}),
        ({"severity": "Important"},
         {"ruling": "not-discharged"}),
        ("not-a-dict", "also-not-a-dict"),
    ]
    for target, outcome in cases:
        assert CB.audit_target_aliases(target) == CB._audit_outcome_aliases(outcome)


def test_audit_target_aliases_diverges_for_id_only_record():
    # axis: id-only records diverge — targets match more; outcomes mark malformed
    record = {"id": "f.py::t@L1"}
    assert CB.audit_target_aliases(record) == {"f.py::t@L1"}
    assert CB._audit_outcome_aliases(record) == set()


def test_stalled_critical_legacy_raw_finding_matches_line_less_identity():
    # axis: legacy leg, plain raw finding → selected by line-less identity
    raw = {"file": "lib/a.py", "line": 10, "title": "unchecked input", "severity": "Critical"}
    ident = FI.finding_identity(raw)
    state = RD.new_state(_cfg())
    state["fixBatch"] = [dict(raw)]
    breaker = {"stalledIdentities": [ident]}
    crit = RD._stalled_critical(state, state["config"], breaker)
    assert crit == [raw]


def test_stalled_critical_legacy_classed_finding_matches_line_less_identity():
    # axis: legacy leg, classed raw finding → selected by line-less identity
    raw = {"file": "lib/a.py", "line": 10, "title": "unchecked input", "severity": "Critical",
           "classKey": "code::bug"}
    ident = FI.finding_identity(raw)
    state = RD.new_state(_cfg())
    state["fixBatch"] = [dict(raw)]
    breaker = {"stalledIdentities": [ident]}
    crit = RD._stalled_critical(state, state["config"], breaker)
    assert crit == [raw]


def test_handle_stall_legacy_raw_critical_selects_stalled_finding():
    # axis: legacy _handle_stall must select stalled raw Critical, not fall back to full batch
    raw = {"file": "lib/a.py", "line": 10, "title": "unchecked input", "severity": "Critical"}
    ident = FI.finding_identity(raw)
    state = RD.new_state(_cfg())
    state["fixBatch"] = [dict(raw)]
    breaker = {"reason": "audit-stall", "detail": "x", "stalledIdentities": [ident]}
    RD._handle_stall(state, state["config"], breaker)
    batch = state.get("_fixBatch") or []
    assert len(batch) == 1
    assert batch[0] == raw


def test_stalled_open_targets_legacy_empty_fix_batch_returns_empty():
    # axis: legacy leg with empty fixBatch yields no stalled targets
    ident = FI.finding_identity(_finding(file="lib/a.py", title="unchecked input"))
    state = RD.new_state(_cfg())
    state["fixBatch"] = []
    breaker = {"stalledIdentities": [ident]}
    assert RD._stalled_open_targets(state, breaker) == []


def test_handle_stall_legacy_empty_fix_batch_parks_unresolvable_open_set():
    # axis: legacy persisted session with audit history and an unreadable outcome parks — no prior-batch fallback
    state = RD.new_state(_cfg())
    state["fixBatch"] = []
    state["auditRounds"] = [{"round": 1, "outcomes": [
        {"identity": "lib/a.py::x", "ruling": "not-discharged"}]}]
    breaker = {"reason": "audit-stall", "detail": "x", "stalledIdentities": ["lib/a.py::x"]}
    RD._handle_stall(state, state["config"], breaker)
    assert state["terminal"] == "cannot-certify"
    assert state["step"] == RD.P_TERMINAL
    assert any(d["kind"] == "cannot-certify" for d in state["decisions"])
    detail = next(d["detail"] for d in state["decisions"] if d["kind"] == "cannot-certify")
    assert "open audit target set unresolvable" in detail
