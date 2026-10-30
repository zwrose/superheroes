"""Vet 735's items (#2279, WO-D): an owner's audited out-of-scope ruling exempts a carried lost-test finding from the
lost-test park, and a not-discharged audit keeps the new issues it raised.

D1: `_break_it_kept_step` reads the audited owner exemption before it parks a carried finding whose break-it test the
earlier record lost. D2: `apply_audit_results` keeps `newIssues` for a result whose own ruling is `not-discharged` on
every arm that returns for it, and the abandoned-session recovery (`_audit_candidates`) reads them from a stored one."""
import os
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import audits  # noqa: E402
import review_record_session as RS  # noqa: E402
import round_phases  # noqa: E402
import test_c1l10_audit_checks as AC  # noqa: E402
import test_c1l11b_carried_findings as TC  # noqa: E402
import test_round_driver as TRD  # noqa: E402
from test_review_record_session import CODEX, Fake, extras, put_envelope  # noqa: E402
from test_review_record_session import Session as SessionFixture  # noqa: E402

RD = TRD.RD
PROV = {"ruledBy": "zach", "ruledAt": "2026-10-20T12:00:00Z"}
REASON = "belongs to the billing rewrite"
_RUN = {"test": "tests/test_x.py", "commit": "h", "status": "ran", "exitCode": 1, "output": "", "reason": None,
        "changedWhy": None}


# ---- D1: the owner exemption before the carried lost-test park -------------------------------

def _lost_row(line=27, title="the edited value is wrong", disposition="fixed"):
    """A carried ledger row marked as having lost its break-it test, with the given disposition."""
    earlier = {"findings": [dict(TC._finding(line, title=title, tradeoff=False, breakItRuns=[_RUN]), outcome=None)]}
    [row] = RD._carried_findings(earlier)
    assert row[RD.CARRIED_TEST_LOST_FIELD] is True
    return dict(row, disposition=disposition)


def _state(*rows):
    """A session whose ledger has a recognized owner (a legacy ledger reads only its fixed rows, which would hide the
    out-of-scope ones from the lost-test leg)."""
    return {"round": 2, "rounds": {"1": {}, "2": {}}, RD.session_contract.DISPOSITION_LEDGER_KEY: list(rows),
            RD.session_contract.DISPOSITION_LEDGER_OWNER_FIELD: RD.session_contract.DISPOSITION_LEDGER_OWNER_VALUE,
            "config": {}}


def _rule(state, row, ruling="out-of-scope", provenance=PROV, source=None):
    """Append a `rule`-verb row to the rulings log the way `_cmd_rule_locked` writes it."""
    key = RD._finding_identity_key(row)
    entry = {"seq": RD._next_ruling_seq(state), "round": state["round"], "id": key, "findingKey": key,
             "ruling": ruling, "reason": REASON, "by": "test"}
    if provenance is not None:
        entry["provenance"] = provenance
    RD._writable_rulings_log(state).append(entry)


def _audit(state, row, ruling="discharged"):
    RD._record_round_append(state, "audits", {"id": RD._finding_identity_key(row), "ruling": ruling})


@pytest.fixture
def parked(monkeypatch):
    seen = []
    monkeypatch.setattr(RD, "_park_cannot_certify", lambda state, detail: seen.append(detail))
    return seen


@pytest.mark.parametrize("disposition", ["fixed", "out-of-scope"])
def test_a_a_carried_lost_test_finding_the_owner_ruled_out_of_scope_and_the_audit_cleared_certifies(parked, disposition):
    row = _lost_row(disposition=disposition)
    state = _state(row)
    _rule(state, row)
    _audit(state, row)
    assert RD._break_it_kept_step(state, {}) is False
    assert parked == []


def test_a_an_exempt_carried_lost_test_finding_gets_its_ruled_out_of_scope_row_and_the_record_reports_the_ruling(parked):
    row = _lost_row()
    state = _state(row)
    key = RD._finding_identity_key(row)
    _rule(state, row)
    _audit(state, row)
    assert RD._break_it_kept_step(state, {}) is False
    kept = [r for rec in state["rounds"].values() for r in rec.get("breakItKept") or []]
    assert [(r["findingKey"], r["outcome"], r["ruledBy"], r["ruledAt"]) for r in kept] == [
        (key, "ruled-out-of-scope", PROV["ruledBy"], PROV["ruledAt"])]
    by_key, rulings, exempt = RS.decision_inputs(state)
    assert key in exempt
    outcome, reason, _rep = RS._decide(by_key[key], by_key, rulings, exempt)
    assert "fixed and audited" not in (reason or ""), (outcome, reason)


@pytest.mark.parametrize("case", ["unattributed", "half-attributed", "no-audit", "not-discharged-audit",
                                  "no-ruling", "guidance-ruling"])
def test_b_a_lost_test_finding_without_the_whole_exemption_still_parks(parked, case):
    row = _lost_row()
    state = _state(row)
    if case == "unattributed":
        _rule(state, row, provenance=None)
    elif case == "half-attributed":
        _rule(state, row, provenance={"ruledBy": "zach"})
    elif case == "guidance-ruling":
        _rule(state, row, ruling="guidance")
    elif case != "no-ruling":
        _rule(state, row)
    if case in ("unattributed", "half-attributed", "no-ruling", "guidance-ruling"):
        _audit(state, row)
    if case == "not-discharged-audit":
        _audit(state, row, "not-discharged")
    assert RD._break_it_kept_step(state, {}) is True
    assert len(parked) == 1 and "was lost" in parked[0] and RD._finding_identity_key(row) in parked[0], parked


def test_b_a_gate_skip_is_not_a_rule_verb_ruling_and_a_lost_test_finding_it_covers_still_parks(parked):
    row = _lost_row()
    state = _state(row)
    key = RD._finding_identity_key(row)
    state["rounds"]["2"]["judgmentDispositions"] = [
        {"findingKey": key, "disposition": "skip", "reason": REASON, "rulingSeq": 1, **PROV}]
    _audit(state, row)
    assert RD._live_ruling_by_key(state)[key]["source"] == "gate"
    assert RD._break_it_kept_step(state, {}) is True
    assert len(parked) == 1 and "was lost" in parked[0], parked


def test_c_two_lost_test_findings_one_exempt_and_one_not_park_naming_the_one_that_is_not(parked):
    exempt = _lost_row(27, title="the edited value is wrong")
    owed = _lost_row(3, title="the first value is wrong")
    assert RD._finding_identity_key(exempt) != RD._finding_identity_key(owed)
    for rows in ((exempt, owed), (owed, exempt)):
        del parked[:]
        state = _state(*rows)
        _rule(state, exempt)
        _audit(state, exempt)
        assert RD._break_it_kept_step(state, {}) is True
        assert len(parked) == 1 and RD._finding_identity_key(owed) in parked[0], parked
        assert RD._finding_identity_key(exempt) not in parked[0], parked


# ---- D2: a not-discharged audit keeps its newIssues ------------------------------------------

NEW_ISSUE = {"title": "the fix breaks the caller", "severity": "Important", "file": "src/b.py", "line": 9,
             "consequence": "caller crashes", "consequenceKind": "real"}
WEAKENED = {"answer": "weakened", "why": "the assertion no longer checks the charge"}


def _target(match=None, **extra):
    """An audit target seated on the independent auditor `codex`, with a break-it test when `match` is given."""
    target = {"id": "t0", "title": "T", "file": "f.py", "line": 1, "auditorVendor": "codex",
              "independence": "independent"}
    if match is not None:
        target["breakIt"] = {"path": AC.TEST_PATH, "reviewerTest": AC.ROLE_TEST, "committedTest": AC.FIXED_TEST,
                             "changedWhy": AC.WHY, "match": match}
    return dict(target, **extra)


def _raised(ruling="not-discharged", issues=None, **extra):
    """An audit result of the given ruling that also reports new issues (the default is one Important one)."""
    return AC._result(ruling=ruling, newIssues=[dict(NEW_ISSUE)] if issues is None else issues, **extra)


def _fold(results, target=None, manifest=True, **kw):
    """`apply_audit_results` over one target; `manifest` is the dispatch manifest (True: the auditor it names)."""
    target = target if target is not None else _target()
    if manifest is True:
        manifest = {"t0": "codex"}
    return audits.apply_audit_results([target], results, collection_manifest=manifest, **kw)


def _titles(outcome):
    return [i["title"] for i in outcome["newIssues"]]


def test_d_a_not_discharged_audit_carrying_a_new_issue_stages_it_for_the_verifier():
    outcome = _fold([_raised()])
    assert outcome["notDischarged"] == ["t0"] and outcome["discharged"] == []
    assert AC._only(outcome)["ruling"] == "not-discharged" and AC._only(outcome)["reason"] == "the fix resolves it"
    assert [(i["title"], i["originAuditId"]) for i in outcome["newIssues"]] == [(NEW_ISSUE["title"], "t0")]
    # the same result on a target the driver recorded no auditor for (provenance not enforced) keeps it too
    bare = _fold([_raised()], {"id": "t0", "title": "T", "file": "f.py", "line": 1}, manifest=None)
    assert _titles(bare) == [NEW_ISSUE["title"]]


def test_d_the_driver_fold_stages_the_not_discharged_audits_new_issue_in_the_state():
    cfg = {"repoRoot": "/nonexistent-review-project", "fixerVendor": "claude", "vendors": ["claude", "codex"]}
    state = RD.new_state(cfg)
    state["_verifyThen"] = RD.VERIFY_THEN_POST_AUDITS
    state["_auditTargets"] = [_target()]
    RD._fold_audits(state, cfg, {"results": [_raised()], "collectionManifest": {"t0": "codex"}})
    assert [i["title"] for i in state["_newIssues"]] == [NEW_ISSUE["title"]]


@pytest.mark.parametrize("path", ["missing", "changed-unexplained", "weakened"])
def test_e_a_not_discharged_audit_on_a_blocked_test_path_keeps_its_new_issue(path):
    if path == "weakened":
        outcome = _fold([_raised(testMatch=WEAKENED)], _target("changed-explained"))
    else:
        outcome = _fold([_raised()], _target(path))
    assert outcome["notDischarged"] == ["t0"] and outcome["testMismatch"] == ["t0"]
    assert AC._only(outcome)["testMatch"]["blocking"] is True and AC._only(outcome)["ruling"] == "not-discharged"
    assert _titles(outcome) == [NEW_ISSUE["title"]]


@pytest.mark.parametrize("manifest", [None, {}, {"t0": "claude"}, {"other": "codex"}],
                         ids=["no-manifest", "no-entry", "wrong-vendor", "other-id"])
@pytest.mark.parametrize("ruling", ["not-discharged", "discharged-but-new-issue"])
def test_f_a_result_the_manifest_does_not_authenticate_has_its_new_issue_dropped(ruling, manifest):
    outcome = _fold([_raised(ruling)], manifest=manifest)
    assert outcome["notDischarged"] == ["t0"] and outcome["newIssues"] == []


@pytest.mark.parametrize("path", ["missing", "weakened"])
def test_f_an_unauthenticated_not_discharged_result_on_a_blocked_test_path_drops_its_new_issue(path):
    if path == "weakened":
        outcome = _fold([_raised(testMatch=WEAKENED)], _target("changed-explained"), manifest={})
    else:
        outcome = _fold([_raised()], _target(path), manifest={})
    assert outcome["testMismatch"] == ["t0"] and outcome["newIssues"] == []


@pytest.mark.parametrize("checks", [None, "yes"], ids=["no-checks", "not-a-dict"])
def test_f_a_not_discharged_result_audit_checks_refuse_drops_its_new_issue(checks):
    outcome = _fold([_raised(checks=checks)])
    assert outcome["malformed"] == ["t0"] and outcome["newIssues"] == []


@pytest.mark.parametrize("issues,kept", [("not a list", 0), (["text", 3, None], 0), ([{"title": "ok"}, "text"], 1),
                                         ([], 0)], ids=["not-a-list", "non-dict-rows", "mixed-rows", "empty"])
def test_f_malformed_new_issues_on_a_not_discharged_result_drop_what_the_discharged_arm_drops(issues, kept):
    outcome = _fold([_raised(issues=issues)])
    assert len(outcome["newIssues"]) == kept
    assert len(_fold([_raised("discharged-but-new-issue", issues=issues)])["newIssues"]) == kept


def test_f_a_new_issue_is_tagged_with_the_audit_that_raised_it_whatever_it_claims():
    outcome = _fold([_raised(issues=[{"title": "x", "originAuditId": "forged"}])])
    assert outcome["newIssues"][0]["originAuditId"] == "t0"


# ---- D2: the abandoned-session recovery -------------------------------------------------------

def _audit_session(tmp_path, result):
    """An abandoned session with one stored fix-audit result and no folded finding."""
    s = SessionFixture(tmp_path, terminal=None).seat("auditor", phase=round_phases.P_AUDITS, rnd=1)
    session = s.save()
    put_envelope(session, "auditor", {"vendor": "codex", "model": CODEX, "payload": result},
                 phase=round_phases.P_AUDITS, rnd=1)
    return session


@pytest.mark.parametrize("ruling", ["not-discharged", "discharged-but-new-issue"])
def test_g_a_stored_audit_result_with_a_new_issue_abandoned_before_the_fold_shows_it_open(tmp_path, ruling):
    session = _audit_session(tmp_path, {"id": "t0", "ruling": ruling, "reason": "r", "newIssues": [dict(NEW_ISSUE)]})
    account = RS.account_from_session(session, extras(), Fake().readers(), abandoned="owner stopped the loop")
    rows = [f for f in account["findings"] if f["title"] == NEW_ISSUE["title"]]
    assert len(rows) == 1, account["findings"]
    assert rows[0]["outcome"] is None and rows[0]["reason"] == RS.UNFOLDED_OPEN and rows[0]["reviewer"] == "auditor"


@pytest.mark.parametrize("payload", [{"ruling": "discharged", "newIssues": [dict(NEW_ISSUE)]},
                                     {"ruling": "not-discharged", "newIssues": "text"},
                                     {"ruling": "not-discharged", "newIssues": ["text", None]},
                                     {"ruling": "not-discharged"}, "text", None], ids=str)
def test_g_a_stored_result_that_is_not_a_not_discharged_or_new_issue_claim_adds_no_candidate(payload):
    assert RS._audit_candidates(payload) == []
