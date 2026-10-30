"""C7 L1 (WO-4): every finding the review took in has one outcome when the loop reaches a terminal.

Drives the real round driver: `run_loop` with scripted seams for the loop-shaped cases, and a staged
state plus the real `rule` verb and the `_set_terminal` chokepoint for the ruling cases.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/wo4_c7_settle.md
"""
import ast
import copy
import json
import os
import re
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import canon  # noqa: E402
import definition_doc  # noqa: E402
import finding_outcomes as FO  # noqa: E402
import round_orders  # noqa: E402
import session_contract as SC  # noqa: E402
import test_risk_areas as TRA  # noqa: E402
import test_round_driver as TRD  # noqa: E402
import verification  # noqa: E402

RD = TRD.RD  # run_loop runs on test_round_driver's own load of the module

CANON_ID = "2026-01-02-abcd1234-1"
OTHER_ID = "2026-01-02-abcd1234-2"
CANON_TEXT = canon.entry_line(CANON_ID, "2026-01-02", "standing", "a ruling",
                              "owner's words: \"go\"", "issue thread")
RESIDUAL_TEXT = "Ratified residuals:\n- keep the  legacy retry loop for now\n"
SOURCES = {"canonText": CANON_TEXT, "residualText": RESIDUAL_TEXT, "residualSource": "base"}
REAL_CONSEQUENCE = "users lose their saved work"
QUALITY_CONSEQUENCE = "the name is harder to read"


def _finding(title, line=1, severity="Minor", kind="code-quality", consequence=None):
    if consequence is None:
        consequence = QUALITY_CONSEQUENCE if kind == "code-quality" else REAL_CONSEQUENCE
    return {"file": "f.py", "line": line, "title": title, "severity": severity,
            "consequence": consequence, "consequenceKind": kind}


def _run_once(findings, cfg=None, **seam_kw):
    """run_loop with `findings` reported once by the first reviewer call; returns (result, state)."""
    box = {"done": False}

    def reviewer(dim, tier, rnd, ctx):
        if rnd == 1 and not box["done"]:
            box["done"] = True
            return [dict(f) for f in findings]
        return []

    return TRD._run_loop_capturing_state(TRD._seams(reviewer=reviewer, **seam_kw),
                                         cfg or TRD._cfg_cert())


def _ledger(state):
    return {SC.finding_identity_key(e): e for e in state.get(SC.DISPOSITION_LEDGER_KEY) or []}


def _row(state, title, line=1):
    return _ledger(state)["f.py::%s@L%d" % (title.lower(), line)]


@pytest.fixture
def sources_calls(monkeypatch):
    """Patch the decision-sources seam; the list records each call."""
    calls = []

    def fake(state):
        calls.append(True)
        return copy.deepcopy(SOURCES)

    monkeypatch.setattr(RD, "_decision_sources", fake)
    return calls


def _staged_state(findings, cfg=None):
    state = RD.new_state(cfg or TRD._cfg())
    compiled, _ = RD.mechanical_compile([dict(f) for f in findings], None)
    RD._stage_findings(state, compiled)
    RD._set_findings(state, state["_toVerify"])
    return state


# --- T1: code quality only is craft, wherever it sits ------------------------------------------

@pytest.mark.parametrize("risk_area", [False, True], ids=["no-risk-area", "risk-area-covers-file"])
def test_t1_code_quality_minor_left_at_convergence_is_craft(risk_area, tmp_path, sources_calls, monkeypatch):
    cfg = TRD._cfg_cert()
    if risk_area:
        area = dict(TRA.PAYMENTS, name="The reviewed file", covers=["f.py"])
        repo, store = TRA._repo(tmp_path, [area])
        # The loop's readers pass no store root, so the fixture's store must be the default one.
        monkeypatch.setenv("WORKHORSE_STORE_ROOT", store)
        cfg = TRD._cfg_cert(repoRoot=repo)  # the loop runs on the repo whose risk area covers f.py
    result, state = _run_once([_finding("Naming")], cfg)
    if risk_area:
        read = TRA.R.touched(state["config"]["repoRoot"], ["f.py"])  # as the loop's own readers see it
        assert read["riskAreas"] == "set"
        assert [hit["area"]["name"] for hit in read["touched"]] == ["The reviewed file"]
        assert read["touched"][0]["matched"] == ["f.py"]
    else:
        assert "repoRoot" not in state["config"]
    assert state["terminal"] == "converged"
    row = _row(state, "Naming")
    assert row["disposition"] == "craft"
    assert row["settledReason"].startswith("code quality only")
    assert sources_calls == []  # no ruling cites a decision, so no source is read


# --- T2: an open real finding at the round cap goes to the owner -------------------------------

def _capped_seams():
    counter = {"n": 0}

    def fix_step(batch, rnd, payload):
        counter["n"] += 1
        return {"fixes": [], "headDiff": TRD._headf(counter["n"]), "changedSubjects": ["Code"]}

    def plausible(clusters, rnd):
        return [{"id": i, "verdict": "PLAUSIBLE", "reason": "checked"}
                for c in (clusters or []) for i in (c.get("ids") or [])]

    def reviewer(dim, tier, rnd, ctx):
        if rnd == 1 and dim == "code-reviewer":
            return {"findings": [_finding("Bug", severity="Important", kind="real")]}
        return []

    return TRD._seams(
        reviewer=reviewer, verifier=plausible, fix_step=fix_step,
        auditor=lambda targets, rnd: [{"id": t["id"], "ruling": "not-discharged", "reason": "broken"}
                                      for t in (targets or [])])


def test_t2_real_important_open_at_the_round_cap_is_left_for_owner(sources_calls):
    result, state = TRD._run_loop_capturing_state(_capped_seams(), TRD._cfg_cert(maxRounds=1))
    assert state["terminal"] == "handed-back"
    row = _row(state, "Bug")
    assert row["disposition"] == "left-for-owner"
    assert "round cap" in row["settledReason"]
    assert sources_calls == []


def test_a_fixer_that_fixes_one_of_two_leaves_the_other_open(sources_calls):
    """A fixer's `fixes` names files, never findings: the skipped finding is not credited `fixed`."""
    counter = {"n": 0}

    def fix_step(batch, rnd, payload):
        counter["n"] += 1
        return {"fixes": [{"file": "f.py", "summary": "fixed the first"}],
                "headDiff": TRD.HEAD, "changedSubjects": ["Code"]}

    def reviewer(dim, tier, rnd, ctx):
        if rnd == 1 and dim == "code-reviewer":
            return {"findings": [_finding("First bug", 1, "Important", "real"),
                                 _finding("Second bug", 2, "Important", "real")]}
        return []

    def auditor(targets, rnd):
        rulings = []
        for t in targets or []:
            if t["id"] == "f.py::first bug@L1":
                rulings.append({"id": t["id"], "ruling": "discharged", "reason": "fix resolves it",
                                "evidence": "tests pass", "auditorVendor": t.get("auditorVendor"),
                                "checks": TRD.audit_checks()})
            else:
                rulings.append({"id": t["id"], "ruling": "not-discharged", "reason": "still broken",
                                "checks": TRD.audit_checks(right="no")})
        return rulings

    # the fix changed a file, so the scoped finder runs; the proven non-panel cells let it seat on the
    # vendor outside the fixer's family instead of parking the review
    result, state = TRD._run_loop_capturing_state(
        TRD._seams(reviewer=reviewer, fix_step=fix_step, auditor=auditor),
        TRD._cfg_cert(maxRounds=2, seatMap=TRD._nonpanel_cell_proof(["claude", "codex"])))
    assert state["terminal"]
    assert counter["n"] >= 1
    _assert_all_settled(state)
    assert _row(state, "First bug", 1)["disposition"] == "fixed"
    ledger = _ledger(state)
    assert "f.py::second bug@L2" in ledger, (
        {k: (r.get("disposition"), r.get("settledReason"), r.get(SC.MERGED_INTO_FIELD))
         for k, r in ledger.items()}, state["rounds"])
    second = _row(state, "Second bug", 2)
    assert second["disposition"] != "fixed", (second, state["rounds"])
    assert second["disposition"] == "left-for-owner", second
    assert "round cap" in second["settledReason"]
    assert state["terminal"] == "handed-back"


# --- T3 / T10: rulings that cite a decision ---------------------------------------------------

def _provenance():
    return {"ruledBy": "owner", "ruledAt": "2026-08-26T00:00:00Z", "records": ["rulings.json"]}


def _follow_up():
    return {"item": "backlog item", "revisitTrigger": "next milestone", "classClosure": "owner backlog"}


def _write_rulings(path, entries):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"_provenance": _provenance(), "rulings": entries}, fh)
    return str(path)


def _ruling(key, decided_by="absent"):
    entry = {"id": key, "ruling": "out-of-scope", "reason": "belongs to the next milestone",
             "followUp": _follow_up()}
    if decided_by != "absent":
        entry["decidedBy"] = decided_by
    return entry


def _rule_session(tmp_path, findings):
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir)
    state = _staged_state(findings)
    RD.save_state(session_dir, state)
    keys = [RD._finding_identity_key(f) for f in state["findings"]]
    return session_dir, keys


def _state_bytes(session_dir):
    with open(os.path.join(session_dir, SC.STATE_FILE), "rb") as fh:
        return fh.read()


def test_t3_out_of_scope_ruling_settles_by_the_decision_it_cites(tmp_path, monkeypatch, sources_calls):
    findings = [_finding("Canon call", 1, "Important", "real"),
                _finding("Residual call", 2, "Important", "real"),
                _finding("Unknown call", 1, "Important", "real")]
    session_dir, (k_canon, k_resid, k_unknown) = _rule_session(tmp_path, findings)
    path = _write_rulings(tmp_path / "rulings.json", [
        _ruling(k_canon, {"kind": "canon", "ref": CANON_ID}),
        _ruling(k_resid, {"kind": "residual", "ref": "keep the legacy retry loop"}),
        _ruling(k_unknown, {"kind": "canon", "ref": OTHER_ID}),
    ])
    out = RD.cmd_rule(session_dir, path, "owner")
    assert out.get("ok"), out
    ok, state = RD.load_state(session_dir)
    assert ok and state.get("terminal") is None
    assert _ledger(state)[k_canon]["disposition"] == "out-of-scope"  # rule itself never settles
    RD._set_terminal(state, "converged")
    ledger = _ledger(state)
    assert ledger[k_canon]["disposition"] == "ruling"
    assert ledger[k_canon]["decidedBy"] == {"kind": "canon", "ref": CANON_ID}
    assert CANON_ID in ledger[k_canon]["settledReason"]
    assert ledger[k_resid]["disposition"] == "ruling"
    assert ledger[k_resid]["decidedBy"]["kind"] == "residual"
    assert "keep the legacy retry loop" in ledger[k_resid]["settledReason"]
    assert ledger[k_unknown]["disposition"] == "left-for-owner"
    assert "not on record" in ledger[k_unknown]["settledReason"]
    assert ledger[k_unknown]["settledReason"].startswith("out of scope: belongs to the next milestone; ")
    assert ledger[k_unknown]["decidedBy"] == {"kind": "canon", "ref": OTHER_ID}  # kept for the writer's re-check
    assert sources_calls == [True]  # read once, for the whole terminal


def test_t3_unreadable_sources_leave_the_decision_off_the_record(tmp_path, monkeypatch):
    def boom(state):
        raise RuntimeError("canon store unreachable")

    monkeypatch.setattr(RD, "_decision_sources", boom)
    session_dir, (key,) = _rule_session(tmp_path, [_finding("Canon call", 1, "Important", "real")])
    path = _write_rulings(tmp_path / "rulings.json", [_ruling(key, {"kind": "canon", "ref": CANON_ID})])
    assert RD.cmd_rule(session_dir, path, "owner").get("ok")
    ok, state = RD.load_state(session_dir)
    RD._set_terminal(state, "halted")  # a raising seam never propagates
    row = _ledger(state)[key]
    assert row["disposition"] == "left-for-owner"
    assert "no Canon text was available" in row["settledReason"]


def test_t3_out_of_scope_without_a_decision_goes_to_owner_or_craft(sources_calls):
    state = _staged_state([_finding("Deferred", 1, "Minor", "real"),
                           _finding("Tidy", 2, "Minor", "code-quality")])
    for title, line in (("Deferred", 1), ("Tidy", 2)):
        RD._record_disposition(state, "f.py::%s@L%d" % (title.lower(), line), "out-of-scope", 1,
                               outOfScopeReason="later")
    RD._set_terminal(state, "converged")
    deferred, tidy = _row(state, "Deferred", 1), _row(state, "Tidy", 2)
    assert deferred["disposition"] == "left-for-owner"
    assert deferred["settledReason"].startswith("out of scope: later; ")
    assert tidy["disposition"] == "craft"
    assert tidy["settledReason"].startswith("code quality only")
    assert sources_calls == []


# --- T4: severity never keeps a finding from the owner ----------------------------------------

def test_t4_nit_with_a_real_consequence_is_left_for_owner(sources_calls):
    result, state = _run_once([_finding("Docs lie", 1, "Nit", "real")])
    assert state["terminal"] == "converged"
    row = _row(state, "Docs lie")
    assert row["disposition"] == "left-for-owner"
    assert "converged" in row["settledReason"]


# --- T5 / T6: every finding has one outcome ----------------------------------------------------

def _assert_all_settled(state):
    ledger = _ledger(state)
    assert ledger
    for key, row in ledger.items():
        if row.get("summaryEntry") or row.get(SC.MERGED_INTO_FIELD):
            continue
        assert row.get("disposition") in SC.DISPOSITIONS, (key, row)
        assert row["disposition"] != "out-of-scope", (key, row)
        assert row[SC.DISPOSITION_SEQ_FIELD] > row[SC.RAISED_SEQ_FIELD], (key, row)


def test_t5_a_loop_run_to_its_terminal_leaves_no_finding_undecided(sources_calls):
    result, state = _run_once([
        _finding("Null deref", 1, "Important", "real"),
        _finding("Naming", 2, "Minor", "code-quality"),
        _finding("Docs lie", 2, "Nit", "real"),
        _finding("Null deref", 1, "Important", "real"),  # the same place and title twice
    ])
    assert state["terminal"]
    _assert_all_settled(state)
    dispositions = {k: r["disposition"] for k, r in _ledger(state).items()}
    assert dispositions["f.py::naming@L2"] == "craft"
    assert dispositions["f.py::docs lie@L2"] == "left-for-owner"


OUTCOME_BEARING = ("fixed", "refuted", "craft", "left-for-owner", "ruling")
LOWERED_BECAUSE = "only a cosmetic effect once the cache is warm"


def _lowering_verdicts(findings):
    verdicts = []
    for f in findings:
        verdict = {"id": f["id"], "verdict": "CONFIRMED", "evidence": "ran", "reason": "ran"}
        if f["title"] == "Slow path":
            verdict.update(severity="Minor", reason=LOWERED_BECAUSE)
        verdicts.append(verdict)
    return verdicts


def _assert_counts_match(taken_in, state):
    ledger = _ledger(state)
    outcome_bearing = {k for k, r in ledger.items() if r.get("disposition") in OUTCOME_BEARING}
    merged = {k for k, r in ledger.items() if r.get(SC.MERGED_INTO_FIELD)}
    assert not (outcome_bearing & merged)
    assert taken_in == outcome_bearing | merged
    assert len(taken_in) == len(outcome_bearing) + len(merged)
    return merged


def _assert_lowered_once(verified):
    changed = [f for f in verified if f.get("severityChange")]
    assert [f["title"] for f in changed] == ["Slow path"]
    assert changed[0]["severity"] == "Minor"
    assert changed[0]["severityChange"] == {"from": "Important", "to": "Minor", "reason": LOWERED_BECAUSE}


def test_t6_a_loop_run_counts_every_finding_taken_in_and_records_a_lowered_severity(
        monkeypatch, sources_calls):
    taken_in = set()
    real_compile = RD.mechanical_compile

    def spy(*args, **kwargs):
        compiled, drops = real_compile(*args, **kwargs)
        taken_in.update(RD._finding_identity_key(f) for f in compiled if not f.get("summaryEntry"))
        return compiled, drops

    monkeypatch.setattr(RD, "mechanical_compile", spy)
    verified = []
    real_apply = verification.apply_verdicts

    def apply_spy(findings, verdicts):
        applied = real_apply(findings, verdicts)
        verified.extend(applied["findings"])
        return applied

    monkeypatch.setattr(verification, "apply_verdicts", apply_spy)

    def verifier(clusters, rnd):
        return {"verdicts": _lowering_verdicts([f for c in clusters or [] for f in c["findings"]]),
                "vendor": "codex"}

    result, state = _run_once([
        _finding("Root cause", 1, "Important", "real"),
        _finding("Slow path", 1, "Important", "real"),
        _finding("Naming", 2, "Minor", "code-quality"),
        _finding("Docs lie", 2, "Nit", "real"),
    ], verifier=verifier, vendors=["claude", "codex"])  # a seat map proves the verifier cell, so verdicts count
    assert state["terminal"]
    assert len(taken_in) == 4
    _assert_counts_match(taken_in, state)
    _assert_lowered_once(verified)


def test_t6_a_synthesis_merge_counts_as_merged_not_as_an_outcome(sources_calls):
    state = _staged_state([_finding("Root cause", 1, "Important", "real"),
                           _finding("Same root cause", 2, "Important", "real"),
                           _finding("Slow path", 1, "Important", "real")])
    taken_in = {RD._finding_identity_key(f) for f in state["_toVerify"]}
    assert len(taken_in) == 3
    staged = verification.stage_ids(state["_toVerify"])
    applied = verification.apply_verdicts(staged, _lowering_verdicts(staged))
    state["_verified"] = applied["findings"]
    ids = [f["id"] for f in staged if f["title"] in ("Root cause", "Same root cause")]
    alone = [f["id"] for f in staged if f["title"] == "Slow path"]  # a grouping must cover every finding
    RD._fold_synthesis(state, state["config"], {"grouping": [
        {"group_id": "g", "member_ids": ids}, {"group_id": "h", "member_ids": alone}]})
    RD._set_terminal(state, "converged")
    merged = _assert_counts_match(taken_in, state)
    assert len(merged) == 1
    _assert_lowered_once(state["_verified"])


def test_t6_severity_change_defaults_its_reason_and_ignores_a_raise():
    findings = [{"id": "a", "severity": "Important", "title": "a", "file": "f.py", "line": 1},
                {"id": "b", "severity": "Minor", "title": "b", "file": "f.py", "line": 2},
                {"id": "c", "severity": "Important", "title": "c", "file": "f.py", "line": 3}]
    verdicts = [{"id": "a", "verdict": "PLAUSIBLE", "severity": "Nit"},
                {"id": "b", "verdict": "PLAUSIBLE", "severity": "Critical", "reason": "worse"},
                {"id": "c", "verdict": "PLAUSIBLE", "severity": "Important", "reason": "same"}]
    kept = {f["id"]: f for f in verification.apply_verdicts(findings, verdicts)["findings"]}
    assert kept["a"]["severityChange"] == {"from": "Important", "to": "Nit", "reason": "no reason given"}
    assert "severityChange" not in kept["b"]
    assert "severityChange" not in kept["c"]


# --- T7: one chokepoint -----------------------------------------------------------------------

def test_t7_one_writer_of_the_terminal_and_it_is_set_terminal():
    path = os.path.join(_LIB, "round_driver.py")
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    tree = ast.parse(source)
    writers = []
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(func):
            targets = node.targets if isinstance(node, ast.Assign) else (
                [node.target] if isinstance(node, (ast.AugAssign, ast.AnnAssign)) else [])
            for t in targets:
                if (isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name)
                        and t.value.id == "state" and isinstance(t.slice, ast.Constant)
                        and t.slice.value == "terminal"):
                    writers.append((func.name, node.lineno))
    assert {name for name, _ in writers} == {"_set_terminal"}, writers
    assert len({line for _, line in writers}) == 1, writers
    lines = [ln for ln in source.splitlines() if re.search(r'state\["terminal"\] = ', ln)]
    assert len(lines) == 1, lines


# --- T8: the Nit cap collapses only code-quality Nits -----------------------------------------

def test_t8_nit_cap_collapses_only_code_quality_nits_into_craft(sources_calls):
    findings = ([_finding("Quality %d" % i, i, "Nit", "code-quality") for i in range(1, 7)]
                + [_finding("Real one", 7, "Nit", "real"), _finding("Real two", 8, "Nit", "real")])
    compiled, drops = RD.mechanical_compile(findings, None)
    titles = [f["title"] for f in compiled if not f.get("summaryEntry")]
    assert "Real one" in titles and "Real two" in titles
    assert "Quality 6" not in titles
    summary = [f for f in compiled if f.get("summaryEntry")]
    assert len(summary) == 1
    assert summary[0]["title"].startswith("+ 1 more Nits")
    assert [m["title"] for m in summary[0]["members"]] == ["Quality 6"]
    state = RD.new_state(TRD._cfg())
    RD._stage_findings(state, compiled)
    row = _ledger(state)["f.py::quality 6@L6"]
    assert row["disposition"] == "craft"
    assert row["settledReason"] == "over the readout cap; code quality only: " + QUALITY_CONSEQUENCE
    assert row[SC.DISPOSITION_SEQ_FIELD] > row[SC.RAISED_SEQ_FIELD]


def test_t8_a_summary_row_without_members_is_ignored(sources_calls):
    summary = {"title": "+ 2 more Nits — see findings-*.json for details", "severity": "Nit",
               "file": None, "line": None, "summaryEntry": True}
    state = RD.new_state(TRD._cfg())
    RD._stage_findings(state, [summary, dict(_finding("Docs lie", 1, "Nit", "real"))])
    RD._set_terminal(state, "converged")
    ledger = _ledger(state)
    assert ledger["f.py::docs lie@L1"]["disposition"] == "left-for-owner"
    assert [k for k, r in ledger.items() if r.get("summaryEntry")]
    assert all("disposition" not in r for r in ledger.values() if r.get("summaryEntry"))


def test_t8_a_collapsed_duplicate_never_downgrades_a_held_real_consequence_nit():
    real = _finding("Dup", 1, "Nit", "real")
    members = [_finding("Quality %d" % i, i + 2, "Nit") for i in range(5)] + [_finding("Dup", 1, "Nit")]
    summary = {"summaryEntry": True, "members": members, "file": None, "line": None}
    state = RD.new_state(TRD._cfg())
    RD._stage_findings(state, [real])
    RD._stage_findings(state, [summary])
    RD._set_terminal(state, "converged")
    assert _ledger(state)["f.py::dup@L1"]["disposition"] == "left-for-owner"


# --- T9: findings at the same place and title are merged and the merge is recorded ------------

def test_t9_same_place_duplicates_merge_and_record_the_merge():
    first = _finding("Off by one", 1, "Important", "real")
    second = dict(first, severity="Minor")
    compiled, drops = RD.mechanical_compile([first, second], None)
    assert len(compiled) == 1
    assert [d for d in drops if d["reason"] == "merged with a finding at the same place and title"] == [
        {"file": "f.py", "line": 1, "title": "Off by one",
         "reason": "merged with a finding at the same place and title"}]
    assert compiled[0]["severity"] == "Important"


# --- T10: the `decidedBy` shape of a ruling ----------------------------------------------------

@pytest.mark.parametrize("decided_by", [
    None, "canon", ["canon", "x"], {}, {"kind": "canon"}, {"kind": "canon", "ref": "  "},
    {"kind": "canon", "ref": 5}, {"kind": "residual", "ref": ""}, {"kind": "other", "ref": "x"},
    {"kind": "canon", "ref": "x", "extra": 1}, {"kind": "sheet-answer", "ref": "card-1"},
    {"kind": "sheet-answer", "ref": None}, {"kind": "sheet-answer", "ref": 5},
    {"kind": "sheet-answer", "ref": True},
    {"kind": "sheet-answer", "ref": {"pr": "7", "card": "c1"}},
    {"kind": "sheet-answer", "ref": {"pr": True, "card": "c1"}},
    {"kind": "sheet-answer", "ref": {"pr": 7, "card": " "}},
    {"kind": "sheet-answer", "ref": {"pr": 7}},
    {"kind": "sheet-answer", "ref": {"pr": 7, "card": "c1", "x": 1}},
])
def test_t10_a_malformed_decided_by_is_refused_and_state_is_unchanged(tmp_path, decided_by):
    session_dir, (key,) = _rule_session(tmp_path, [_finding("Canon call", 1, "Important", "real")])
    before = _state_bytes(session_dir)
    path = _write_rulings(tmp_path / "rulings.json", [_ruling(key, decided_by)])
    out = RD.cmd_rule(session_dir, path, "owner")
    assert out.get("ok") is False and out.get("reason") == "ruling-decided-by-malformed", out
    assert RD.RULING_DECIDED_BY_MALFORMED == "ruling-decided-by-malformed"
    assert _state_bytes(session_dir) == before


@pytest.mark.parametrize("decided_by", [
    {"kind": "canon", "ref": CANON_ID},
    {"kind": "residual", "ref": "keep the legacy retry loop"},
    {"kind": "sheet-answer", "ref": {"pr": 7, "card": "c1"}},
])
def test_t10_a_valid_decided_by_is_stored_on_the_rulings_log_row(tmp_path, decided_by):
    session_dir, (key,) = _rule_session(tmp_path, [_finding("Canon call", 1, "Important", "real")])
    path = _write_rulings(tmp_path / "rulings.json", [_ruling(key, decided_by)])
    out = RD.cmd_rule(session_dir, path, "owner")
    assert out.get("ok"), out
    ok, state = RD.load_state(session_dir)
    assert state["rulingsLog"][-1]["decidedBy"] == decided_by
    assert _ledger(state)[key]["disposition"] == "out-of-scope"  # `rule` writes no settled disposition


# --- T11 / T12 / E-edges: pending issues, idempotence, faults ----------------------------------

def test_t11_a_terminal_with_pending_new_issues_settles_them_and_records_the_drop(sources_calls):
    state = _staged_state([_finding("Known", 1, "Important", "real")])
    good = _finding("Late find", 2, "Important", "real")
    no_consequence = {"file": "f.py", "line": 1, "title": "Vague worry", "severity": "Important"}
    state["_newIssues"] = [good, no_consequence]
    to_verify = [RD._finding_identity_key(f) for f in state["_toVerify"]]
    RD._set_terminal(state, "halted")
    row = _row(state, "Late find", 2)
    assert row["disposition"] == "left-for-owner"
    assert "(halted)" in row["settledReason"]
    assert "f.py::vague worry@L1" not in _ledger(state)
    drops = state["rounds"]["1"]["compileDrops"]
    assert [d["reason"] for d in drops if d["title"] == "Vague worry"] == [RD.COMPILE_DROP_NO_CONSEQUENCE]
    assert [RD._finding_identity_key(f) for f in state["_toVerify"]] == to_verify  # `_toVerify` is untouched


def test_t12_settling_twice_changes_nothing(tmp_path, sources_calls):
    state = _staged_state([_finding("Real", 1, "Important", "real"),
                           _finding("Tidy", 2, "Minor", "code-quality")])
    nits = [_finding("Nit %d" % i, 3 + i, "Nit", "code-quality") for i in range(RD._NIT_CAP + 2)]
    state["reviewedDiff"] = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
                             "@@ -1 +1,12 @@\n-old\n" + "+new\n" * 12)  # every pending Nit sits in scope
    state["_newIssues"] = ([{"file": "f.py", "line": 1, "title": "Vague worry", "severity": "Important"},
                            _finding("Late find", 2, "Minor", "real")] + nits)
    RD._record_disposition(state, "f.py::real@L1", "out-of-scope", 1, outOfScopeReason="later")
    RD._set_terminal(state, "converged")
    collapsed = ["f.py::nit %d@L%d" % (i, 3 + i) for i in range(RD._NIT_CAP, RD._NIT_CAP + 2)]
    collapsed_rows = {k: copy.deepcopy(_ledger(state)[k]) for k in collapsed}
    assert [r["disposition"] for r in collapsed_rows.values()] == ["craft", "craft"]  # the cap really collapsed two
    first = json.dumps(state, sort_keys=True)
    first_keys = sorted(_ledger(state))
    RD._settle_open_findings(state)
    RD._settle_open_findings(state, cap=True)
    assert json.dumps(state, sort_keys=True) == first
    assert sorted(_ledger(state)) == first_keys
    assert {k: _ledger(state)[k] for k in collapsed} == collapsed_rows


def test_stale_fixed_disposition_is_settled_as_open(sources_calls):
    state = _staged_state([_finding("Raised again", 1, "Important", "real")])
    key = "f.py::raised again@L1"
    RD._record_disposition(state, key, "fixed", 1, dispositionReceipt="r")
    compiled, _ = RD.mechanical_compile([_finding("Raised again", 1, "Important", "real")], None)
    RD._stage_findings(state, compiled)  # re-raised in the same round: the fixed family stays, now stale
    row = _ledger(state)[key]
    assert row["disposition"] == "fixed" and SC.DISPOSITION_SEQ_FIELD not in row  # nothing newer than the raise
    RD._set_terminal(state, "stalled")
    row = _ledger(state)[key]
    assert row["disposition"] == "left-for-owner"
    assert row["settledReason"] == "still open when the review loop ended (stalled)"
    assert "dispositionReceipt" not in row


def test_fixed_refuted_and_merged_findings_keep_what_they_have(sources_calls):
    state = _staged_state([_finding("Fixed one", 1, "Important", "real"),
                           _finding("Refuted one", 2, "Important", "real"),
                           _finding("Merged one", 1, "Important", "real")])
    RD._record_disposition(state, "f.py::fixed one@L1", "fixed", 1, dispositionReceipt="r")
    RD._record_disposition(state, "f.py::refuted one@L2", "refuted", 1, refutedReason="not reachable")
    RD._record_merged_into(state, "f.py::merged one@L1", "f.py::fixed one@L1")
    before = copy.deepcopy(_ledger(state))
    RD._set_terminal(state, "converged")
    assert _ledger(state) == before


def test_an_unreadable_ledger_settles_nothing_and_records_why(monkeypatch):
    state = _staged_state([_finding("Real", 1, "Important", "real")])
    ledger_before = copy.deepcopy(state[SC.DISPOSITION_LEDGER_KEY])
    decisions_before = copy.deepcopy(state.get("decisions"))
    fault = SC.DispositionLedgerReadFault(token="disposition-ledger-malformed",
                                          detail="dispositionLedger must be a list")
    monkeypatch.setattr(RD, "_disposition_ledger_by_key", lambda s: ({}, fault))
    RD._set_terminal(state, "halted")  # never crashes the terminal
    assert state["terminal"] == "halted"
    assert state[SC.DISPOSITION_LEDGER_KEY] == ledger_before
    assert state["settleSkipped"]["token"] == "disposition-ledger-malformed"
    assert "dispositionLedger must be a list" in state["settleSkipped"]["detail"]
    assert state["decisions"] == decisions_before  # a skipped settle is not a decision


def test_a_cap_stop_states_the_round_cap_whatever_the_verdict(sources_calls):
    state = _staged_state([_finding("Real", 1, "Important", "real")])
    RD._hand_back(state, "round-cap", "cap", cap=True)
    assert state["terminal"] == "handed-back"
    assert _row(state, "Real")["settledReason"] == "still open when the loop reached its round cap"


def test_a_staged_newer_report_settles_over_the_older_live_copy():
    state = RD.new_state({"repoRoot": "/nonexistent-review-project"})
    f = {"file": "f.py", "line": 1, "title": "Bug", "severity": "Minor",
         "consequence": "harder to read", "consequenceKind": "code-quality"}
    RD._stage_findings(state, [f])
    RD._set_findings(state, state["_toVerify"])
    state["round"] = 2
    RD._stage_findings(state, [dict(f, consequence="lost work", consequenceKind="real")])
    RD._seed_findings_before_record_park(state)
    RD._park_cannot_certify(state, "record write failed")
    row = state[SC.DISPOSITION_LEDGER_KEY][0]
    assert row["disposition"] == "left-for-owner"
    assert row["consequenceKind"] == "real"
    import review_record_session as RRS
    exported = RRS._findings(state)[0]
    assert "lost work" in exported["consequence"]
    assert exported["outcome"] == "left-for-owner"


def test_a_merged_real_consequence_is_not_settled_as_craft():
    state = RD.new_state({"repoRoot": "/nonexistent-review-project"})
    f = {"file": "f.py", "line": 1, "title": "Bug", "severity": "Minor",
         "consequence": "lost work", "consequenceKind": "real"}
    RD._stage_findings(state, [f])
    RD._set_findings(state, state["_toVerify"])
    older = state["findings"][0]
    newer = dict(f, consequence="harder to read", consequenceKind="code-quality",
                 **{SC.RAISED_SEQ_FIELD: (older.get(SC.RAISED_SEQ_FIELD) or 0) + 1})
    merged = RD._merge_same_finding(older, newer)
    assert merged["consequenceKind"] == "real"
    assert merged[SC.RAISED_SEQ_FIELD] == newer[SC.RAISED_SEQ_FIELD]
    # Through settlement: the staged code-quality report must not turn the real finding into craft.
    state = RD.new_state({"repoRoot": "/nonexistent-review-project"})
    RD._stage_findings(state, [f])
    RD._set_findings(state, state["_toVerify"])
    state["round"] = 2
    RD._stage_findings(state, [dict(f, consequence="harder to read", consequenceKind="code-quality")])
    RD._seed_findings_before_record_park(state)
    RD._park_cannot_certify(state, "record write failed")
    assert state[SC.DISPOSITION_LEDGER_KEY][0]["disposition"] == "left-for-owner"
    import review_record_session as RRS
    exported = RRS._findings(state)[0]
    assert exported["outcome"] == "left-for-owner"
    assert exported["consequence"].startswith("lost work")


def test_a_later_code_quality_reraise_keeps_the_held_real_consequence():
    state = RD.new_state({"repoRoot": "/nonexistent-review-project"})
    f = {"file": "f.py", "line": 1, "title": "Bug", "severity": "Minor",
         "consequence": "lost work", "consequenceKind": "real"}
    RD._stage_findings(state, [f])
    RD._set_findings(state, state["_toVerify"])
    state["round"] = 2
    RD._stage_findings(state, [dict(f, severity="Important", consequence="harder to read",
                                    consequenceKind="code-quality")])
    RD._seed_findings_before_record_park(state)
    RD._park_cannot_certify(state, "record write failed")
    row = state[SC.DISPOSITION_LEDGER_KEY][0]
    assert row["consequenceKind"] == "real"
    assert row["disposition"] == "left-for-owner"
    assert "lost work" in row["consequence"]
    import review_record_session as RRS
    assert RRS._findings(state)[0]["outcome"] == "left-for-owner"


# --- the driver reads its decision sources from the one home the record writer uses -------------

def _canon_project(tmp_path, monkeypatch):
    """A throwaway git repo holding a Canon file; the Canon lookup and the residual read are pinned to
    it, so a read that names no repository root would find them anyway (the ambient project's)."""
    root = str(tmp_path / "project")
    subprocess.run(["git", "init", "-q", "-b", "main", root], check=True)
    path = os.path.join(root, "docs", "superheroes", "canon.md")
    os.makedirs(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(canon.HEADER + CANON_TEXT + "\n")
    loc = {"path": path, "home": "repo", "gitRoot": root, "exists": True, "defaultRef": None}
    monkeypatch.setattr(definition_doc, "resolve_canon", lambda root: dict(loc))
    seen = []

    def residuals(repo_root, base_ref):
        seen.append((repo_root, base_ref))
        return RESIDUAL_TEXT, "Residuals below are read from the review base commit (base-pinned).", None

    monkeypatch.setattr(round_orders, "resolve_order_residuals", residuals)
    return root, seen


def test_the_drivers_decision_sources_are_the_record_writers(tmp_path, monkeypatch):
    # axis: the driver's sources are `finding_outcomes.decision_sources` for the session's repo root and base
    root, seen = _canon_project(tmp_path, monkeypatch)
    state = RD.new_state(TRD._cfg(repoRoot=root, baseRef="base-oid"))
    sources = RD._decision_sources(state)
    assert sources == FO.decision_sources(root, "base-oid")
    assert CANON_ID in sources["canonText"]
    assert (sources["residualText"], sources["residualSource"]) == (RESIDUAL_TEXT, "base")
    assert seen == [(root, "base-oid"), (root, "base-oid")]


def test_a_session_with_no_repo_root_has_no_decision_sources(tmp_path, monkeypatch):
    # axis: no repository named reads nothing, so a cited decision is not on record (never the ambient project's)
    _canon_project(tmp_path, monkeypatch)
    state = RD.new_state(TRD._cfg())
    assert "repoRoot" not in state["config"]
    assert RD._decision_sources(state) == {}
    assert RD._decision_sources({"config": {"repoRoot": "  ", "baseRef": "base-oid"}}) == {}
