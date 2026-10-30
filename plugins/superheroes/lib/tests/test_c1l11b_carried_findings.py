"""C1-L11b (UFR-1): a finding carried over from an abandoned session with no outcome is settled fixed when later commits
show it fixed, and otherwise sent back to the reviewers.

Pins, each at the place the rule is enforced:

U1  at fresh state every earlier-record finding with no outcome is seeded into the session's ledger under its stored key,
    once, before any audit runs, on both the `changed` and the `full` path; a finding that has an outcome is not carried;
U2  round 1 audits the carried findings first, against the change since the last reviewed commit, and a discharged one is
    settled `fixed` under its stored key;
U3  a carried finding the audit did not discharge, or could not target, goes to the verifier under its stored key, never
    to the fix queue (a false one ends shown-wrong with no fix applied);
U4  no carried findings: today's returning round, step for step;
U5  the record account relists each carried finding once, under its stored key, with its outcome.

Drives the real round driver through the CLI functions (`cmd_next`, `cmd_submit`) on a real throwaway git repository,
the way test_c1l11b_returning_session.py does.

Bite-proof record: c1l11b_wo_d2_carried_findings
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

import review_record as RR  # noqa: E402
import review_record_session as RS  # noqa: E402
import session_contract as SC  # noqa: E402
import test_c1l10_later_rounds as TLR  # noqa: E402
import test_c1l11b_returning_session as TS  # noqa: E402
import test_returning_review_c1l11 as TR  # noqa: E402
import test_review_record_session as TRRS  # noqa: E402
import test_round_driver as TRD  # noqa: E402
from test_c1l11b_returning_session import _isolated_git  # noqa: E402,F401  (autouse: no global git config)

RD = TRD.RD
VENDORS = TS.VENDORS
SHARED = "src/shared.py"  # 30 lines on main; the first leg edits lines 3 and 27, so the pull request has two hunks in it


def _shared(**edits):
    """src/shared.py with its lines 3 and 27 edited as the first leg left them, and ``edits`` ({line: text}) on top."""
    lines = TR.numbered("shared", 30).splitlines(keepends=True)
    lines[2], lines[26] = "edited_a = 1\n", "edited_b = 1\n"
    for line, text in edits.items():
        lines[int(line) - 1] = text
    return "".join(lines)


FIRST = {SHARED: _shared()}


def _change(**edits):
    def change(repo):
        repo.write(SHARED, _shared(**edits))
        repo.commit("later commit")
    return change


FIXES_LINE_27 = _change(**{"27": "edited_b = 2\n"})  # the later commit that fixes the finding at line 27
TOUCHES_NEAR_27 = _change(**{"28": "edited_c = 2\n"})  # a later commit near line 27 that does not fix it


def _finding(line, title="the edited value is wrong", file=SHARED, **over):
    """A finding of the earlier record with no outcome, carrying the key the record stored for it."""
    row = {"id": "F-%s" % title.split()[0], "title": title, "severity": "Important", "file": file, "line": line,
           "consequence": TRD._CONSEQUENCE}
    row.update(over)
    row[SC.FINDING_KEY_FIELD] = RR._key(row)
    return row


def _session(tmp_path, monkeypatch, findings, change=FIXES_LINE_27, record=None, **kwargs):
    s = TS.Session(tmp_path, monkeypatch, first=kwargs.pop("first", FIRST), change=change, **kwargs)
    s.write_earlier(dict(s.record, findings=findings, **(record or {})))
    s.cfg["headSha"] = s.head
    return s


ABANDONED = {"abandoned": {"reason": "the loop was closed before it ended"}}  # reads `full`, and still names lastReviewed


def _respond(**kwargs):
    return TRD._responder(vendors=VENDORS, **kwargs)


def _run(s, respond, stop_at=None, limit=40):
    """next/submit until the terminal or the first ``stop_at`` phase; returns that `next` answer and every (action, round)."""
    seen = []
    for step in range(limit):
        n = s.next(first=step == 0)
        seen.append((n["action"], n["round"]))
        if n["action"] == RD.P_TERMINAL or n["phase"] == stop_at:
            return n, seen
        art = respond(n["phase"], n["payload"], n["round"])
        if n["phase"] == RD.P_PANEL:  # the panel answers for the lenses this session's seat map configured, no others
            art = dict(art, seats={dim: {"findings": []} for dim in s.state()["config"]["dimensions"]})
        if n["phase"] == RD.P_VERIFIERS:  # the verdicts count only when they claim the vendor the driver seated
            vendor = RD._nonpanel_selection(s.state(), s.dir, RD.P_VERIFIERS)[0]
            art = dict(art, verifierVendor=vendor) if vendor else art
        art = TRD._claim_reviewer(s.dir, n["phase"], art)
        sub = RD.cmd_submit(s.dir, n["phase"], n["attempt"], n["expectedStateHash"], art)
        assert sub["ok"], sub
    raise AssertionError("no stop in %d steps: %s" % (limit, seen))


def _row(state, key):
    [row] = [r for r in state.get(SC.DISPOSITION_LEDGER_KEY) or [] if SC.finding_identity_key(r) == key]
    return row


def _carried(state):
    return state["rounds"]["1"]["carried"]


def _account_findings(s, state):
    """The record account's findings for the finished session, each with an outcome: the whole account the writer builds,
    for a returning session that ran no panel as for one that did."""
    return TLR._every_finding_has_an_outcome(s.dir, state)["findings"]


def _outcomes(findings, key):
    return [f["outcome"] for f in findings if f["findingKey"] == key]


# --- T1 (UFR-1 acceptance): a carried finding with no outcome and a later fix is settled fixed ---------------------------

@pytest.mark.parametrize("record,read,order", [
    (None, "changed", [(RD.P_AUDITS, 1), (RD.P_SCOPED, 1)]),
    (ABANDONED, "full", [(RD.P_AUDITS, 1), (RD.P_PANEL, 1)]),
], ids=["changed", "full"])
def test_t1_a_carried_finding_a_later_commit_fixed_is_settled_fixed_and_the_record_reads_reviewed(tmp_path, monkeypatch, record, read, order):
    finding = _finding(27)
    s = _session(tmp_path, monkeypatch, [finding], record=record)
    first = s.next()
    state = s.state()
    assert first["action"] == RD.P_AUDITS and first["round"] == 1, first
    returning = state["config"]["returning"]
    assert returning["read"] == read
    if read == "changed":
        assert returning["lastReviewed"] == s.reviewed and _carried(state)["auditBase"] == s.reviewed
    else:
        # C1-L11a's rule: an abandoned earlier record reads full and names no lastReviewed; the carried record names the base the audit read
        assert returning["lastReviewed"] is None and _carried(state)["auditBase"] == s.reviewed
    key = finding[SC.FINDING_KEY_FIELD]
    # seeded under the stored key before the audit ran: a raised sequence and no disposition yet
    seeded = _row(state, key)
    assert seeded.get("raisedSeq") and seeded.get("raisedRound") == 1 and "disposition" not in seeded, seeded
    assert [t["id"] for t in first["payload"]["targets"]] == [key]
    assert first["payload"]["targets"][0]["fixHunks"], "the audit is given the hunk of the change over the finding's line"
    if read == "full":
        # the abandoned session's audit reads only the later fix (auditBase...head), never the original pull request's changes
        delta = first["payload"]["targets"][0]["fixerDelta"]
        assert "-+edited_b = 1" in delta and "++edited_b = 2" in delta, delta
        assert not any("edited_a" in line for line in delta), delta
    n, seen = _run(s, _respond(audit="discharged"))
    assert n["action"] == RD.P_TERMINAL and n["payload"]["verdict"] == "converged", seen
    assert seen[:len(order)] == order and (RD.P_PANEL in [a for a, _ in seen]) == (read == "full"), seen
    assert RD.P_APPLY_FIXES not in [a for a, _ in seen]
    state = s.state()
    row = _row(state, key)
    assert row["disposition"] == "fixed" and row["dispositionRound"] == 1 and row["dispositionSeq"] > row["raisedSeq"], row
    assert _carried(state) == {"keys": [key], "auditBase": s.reviewed, "discharged": [key], "sentBack": []}
    # the record account relists it once, under its stored key, as fixed; no undecided row is left
    findings = _account_findings(s, state)
    assert _outcomes(findings, key) == ["fixed"] and RR._finding_lines(findings) == []
    fake = TRRS.Fake(head=s.head)
    out = RS.write_from_session(s.dir, TRRS.put_extras(tmp_path, TRRS.extras(ci="green")), s.repo.root, fake.readers())
    assert out["ok"], out
    record_written = RR.read(7, readers=fake.readers())
    stored = [f for f in record_written["findings"] if f["findingKey"] == key]
    assert [f["outcome"] for f in stored] == ["fixed"]
    missing = record_written["whatIsMissing"]
    assert not [line for line in missing if "finding" in line], missing
    if read == "full":
        # The record still reads not-reviewed, for one reason that is the fixture's: a session driven by hand submit journals
        # no seat and holds no engine record, so each panel seat reads "did not run". Those four lines are all that is missing.
        assert sorted(missing) == sorted("%s (round 1) did not run" % dim for dim in state["config"]["dimensions"]), missing
        assert record_written["status"] == RR.NOT_REVIEWED
    else:
        # No panel ran, so none was planned: no seat reads "did not run", and the audit and the scoped finder at the
        # session head read the record as reviewed.
        assert not [line for line in missing if "did not run" in line], missing
        assert record_written["status"] == RR.REVIEWED, missing


def test_t1_the_carried_finding_is_undecided_until_the_audit_settles_it(tmp_path, monkeypatch):
    # the control: before the audit folds, the record writer reads the seeded row as undecided (a raised sequence, no newer
    # disposition), so a record written then would list it as still open
    finding = _finding(27)
    key = finding[SC.FINDING_KEY_FIELD]
    s = _session(tmp_path, monkeypatch, [finding])
    s.next()
    state = s.state()
    assert RS.row_decision(_row(state, key), RS.decision_inputs(state))[0] is None
    n, _seen = _run(s, _respond(audit="discharged"))
    state = s.state()
    assert RS.row_decision(_row(state, key), RS.decision_inputs(state))[0] == "fixed"


# --- T2: no fix; the audit does not discharge it; the verifier confirms it -----------------------------------------------

@pytest.mark.parametrize("record,after", [(None, RD.P_SCOPED), (ABANDONED, RD.P_PANEL)], ids=["changed", "full"])
def test_t2_a_carried_finding_the_audit_does_not_discharge_goes_to_the_verifier_and_stays_open_when_confirmed(tmp_path, monkeypatch, record, after):
    finding = _finding(27, tradeoff=False)  # a row with no `tradeoff` key is held for the owner (I3 below), not fixed
    key = finding[SC.FINDING_KEY_FIELD]
    s = _session(tmp_path, monkeypatch, [finding], change=TOUCHES_NEAR_27, record=record)
    n, seen = _run(s, _respond(audit="not-discharged"), stop_at=RD.P_VERIFIERS)
    assert n["action"] == RD.P_VERIFIERS and seen[:2] == [(RD.P_AUDITS, 1), (after, 1)], seen
    state = s.state()
    # staged for the verifier under its stored key; not on the fix queue, not fixed
    assert [SC.finding_identity_key(f) for f in state["_toVerify"]] == [key]
    assert not state.get("_fixBatch") and state["_auditOutcome"]["notDischarged"] == []
    assert "disposition" not in _row(state, key) or _row(state, key)["disposition"] != "fixed"
    assert _carried(state) == {"keys": [key], "auditBase": s.reviewed, "discharged": [], "sentBack": [key]}
    n, seen = _run(s, _respond(audit="not-discharged", verdict="CONFIRMED"), stop_at=RD.P_APPLY_FIXES)
    assert n["action"] == RD.P_APPLY_FIXES, seen
    assert [SC.finding_identity_key(f) for f in n["payload"]["batch"]] == [key]
    assert _row(s.state(), key).get("disposition") != "fixed"


def test_t2_an_abandoned_record_whose_final_commit_is_not_a_sha_audits_nothing_and_sends_the_carried_finding_to_the_verifier(tmp_path, monkeypatch):
    finding = _finding(27, tradeoff=False)
    key = finding[SC.FINDING_KEY_FIELD]
    s = _session(tmp_path, monkeypatch, [finding], record=dict(ABANDONED, finalCommit={"sha": "not-a-sha"}))
    first = s.next()
    state = s.state()
    assert first["action"] == RD.P_PANEL and "returningAuditBase" not in state["config"], first
    assert state["config"]["returning"]["lastReviewed"] is None and "returningBaselineDiff" not in state["config"]
    assert _carried(state) == {"keys": [key], "auditBase": None, "discharged": [], "sentBack": [key]}
    n, seen = _run(s, _respond(), stop_at=RD.P_VERIFIERS)
    assert RD.P_AUDITS not in [a for a, _ in seen], seen
    state = s.state()
    assert [SC.finding_identity_key(f) for f in state["_toVerify"]] == [key]
    assert _row(state, key).get("disposition") != "fixed"


# --- I3 (round-2 audit): a row from a record written before `tradeoff` was persisted is never fixed autonomously ------------

def _confirmed_run(tmp_path, monkeypatch, finding):
    s = _session(tmp_path, monkeypatch, [finding], change=TOUCHES_NEAR_27)
    n, seen = _run(s, _respond(audit="not-discharged"), stop_at=RD.P_VERIFIERS)
    assert n["action"] == RD.P_VERIFIERS, seen
    return s, _run(s, _respond(audit="not-discharged", verdict="CONFIRMED"), stop_at=RD.P_APPLY_FIXES)


def test_i3_a_carried_important_row_with_no_tradeoff_key_the_verifier_confirms_is_held_for_the_owner(tmp_path, monkeypatch):
    finding = _finding(27)
    assert "tradeoff" not in finding
    key = finding[SC.FINDING_KEY_FIELD]
    s, (n, seen) = _confirmed_run(tmp_path, monkeypatch, finding)
    assert RD.P_APPLY_FIXES not in [a for a, _ in seen], seen
    state = s.state()
    assert key in state["ownerChoiceHeld"], state.get("ownerChoiceHeld")
    assert key not in [SC.finding_identity_key(f) for f in state.get("fixBatch") or []]
    assert _row(state, key).get("disposition") != "fixed"


def test_i3_a_carried_important_row_whose_tradeoff_key_is_false_still_reaches_the_fixer(tmp_path, monkeypatch):
    finding = _finding(27, tradeoff=False)
    key = finding[SC.FINDING_KEY_FIELD]
    s, (n, seen) = _confirmed_run(tmp_path, monkeypatch, finding)
    assert n["action"] == RD.P_APPLY_FIXES, seen
    assert [SC.finding_identity_key(f) for f in n["payload"]["batch"]] == [key]
    assert key not in (s.state().get("ownerChoiceHeld") or [])


# --- T3 (F3): a false carried finding is shown wrong and no fix is ordered for it ----------------------------------------

@pytest.mark.parametrize("record,change", [(None, TOUCHES_NEAR_27), (ABANDONED, FIXES_LINE_27)], ids=["changed", "full"])
def test_t3_a_false_carried_finding_the_verifier_refutes_ends_shown_wrong_with_no_fix_ordered(tmp_path, monkeypatch, record, change):
    finding = _finding(27, title="the edited value is not wrong at all")
    key = finding[SC.FINDING_KEY_FIELD]
    s = _session(tmp_path, monkeypatch, [finding], change=change, record=record)
    # an audit that discharges nothing: whatever it says, a finding it did not discharge only reaches the verifier
    n, seen = _run(s, _respond(audit="not-discharged", verdict="REFUTED"))
    assert n["action"] == RD.P_TERMINAL and n["payload"]["verdict"] == "converged", seen
    assert RD.P_APPLY_FIXES not in [a for a, _ in seen], seen
    state = s.state()
    row = _row(state, key)
    assert row["disposition"] == "refuted" and row["grade"]["verdict"] == "wrong", row
    assert _outcomes(_account_findings(s, state), key) == ["shown-wrong"]


# --- T4: the fail-closed edges --------------------------------------------------------------------------------------------

def test_t4_e1_a_carried_finding_with_no_file_or_line_is_sent_back_never_fixed(tmp_path, monkeypatch):
    finding = {"id": "F-none", "title": "somewhere in the module", "severity": "Important", "consequence": TRD._CONSEQUENCE,
               SC.FINDING_KEY_FIELD: "rr1:" + "1" * 32}
    key = finding[SC.FINDING_KEY_FIELD]
    s = _session(tmp_path, monkeypatch, [finding])
    first = s.next()
    assert first["action"] == RD.P_SCOPED, first  # nothing to audit: the scoped finder is next
    assert _carried(s.state()) == {"keys": [key], "auditBase": s.reviewed, "discharged": [], "sentBack": [key]}
    n, _seen = _run(s, _respond(audit="discharged"), stop_at=RD.P_VERIFIERS)
    state = s.state()
    assert [SC.finding_identity_key(f) for f in state["_toVerify"]] == [key]
    assert _row(state, key).get("disposition") != "fixed"


def test_t4_e2_an_audit_that_returns_nothing_for_a_carried_target_sends_it_back_never_fixed(tmp_path, monkeypatch):
    finding = _finding(27)
    key = finding[SC.FINDING_KEY_FIELD]
    s = _session(tmp_path, monkeypatch, [finding])
    respond = _respond(audit="discharged")

    def silent_auditor(phase, payload, rnd):
        art = respond(phase, payload, rnd)
        return dict(art, results=[]) if phase == RD.P_AUDITS else art

    n, seen = _run(s, silent_auditor, stop_at=RD.P_VERIFIERS)
    assert n["action"] == RD.P_VERIFIERS, seen
    state = s.state()
    assert [SC.finding_identity_key(f) for f in state["_toVerify"]] == [key]
    assert _row(state, key).get("disposition") != "fixed" and _carried(state)["sentBack"] == [key]
    assert state["_auditOutcome"]["discharged"] == []


def test_t4_e3_a_record_finding_that_has_an_outcome_is_not_carried(tmp_path, monkeypatch):
    decided = _finding(3, title="already decided", outcome="fixed", reason="fixed and audited in round 2")
    open_one = _finding(27)
    s = _session(tmp_path, monkeypatch, [decided, open_one])
    s.next()
    state = s.state()
    assert [c[SC.FINDING_KEY_FIELD] for c in state["config"]["returningCarried"]] == [open_one[SC.FINDING_KEY_FIELD]]
    keys = [SC.finding_identity_key(r) for r in state.get(SC.DISPOSITION_LEDGER_KEY) or []]
    assert keys == [open_one[SC.FINDING_KEY_FIELD]], keys
    assert _carried(state)["keys"] == [open_one[SC.FINDING_KEY_FIELD]]


def test_t4_e4_two_carried_findings_with_one_key_are_one_ledger_row(tmp_path, monkeypatch):
    finding = _finding(27)
    twin = dict(finding, id="F-twin")
    s = _session(tmp_path, monkeypatch, [finding, twin])
    first = s.next()
    state = s.state()
    key = finding[SC.FINDING_KEY_FIELD]
    assert [SC.finding_identity_key(r) for r in state[SC.DISPOSITION_LEDGER_KEY]] == [key]
    assert _carried(state)["keys"] == [key] and [t["id"] for t in first["payload"]["targets"]] == [key]
    n, _seen = _run(s, _respond(audit="discharged"))
    assert _outcomes(_account_findings(s, s.state()), key) == ["fixed"]


def test_t4_e5_a_carried_finding_on_a_proven_copy_is_not_audited_and_is_sent_back(tmp_path, monkeypatch):
    finding = _finding(1, title="the vendored blob is wrong", file="vendor/blob.bin")
    key = finding[SC.FINDING_KEY_FIELD]
    s = _session(tmp_path, monkeypatch, [finding], first=TS._first_leg(), change=TS._vendor_a_binary_copy_and_edit,
                 cfg={"copyProof": TS._blob_proof()})
    first = s.next()
    assert first["action"] == RD.P_SCOPED, first  # no audit target: the proven copy is in no seat's input
    assert _carried(s.state()) == {"keys": [key], "auditBase": s.reviewed, "discharged": [], "sentBack": [key]}
    n, _seen = _run(s, _respond(), stop_at=RD.P_VERIFIERS)
    state = s.state()
    assert [SC.finding_identity_key(f) for f in state["_toVerify"]] == [key]
    assert _row(state, key).get("disposition") != "fixed"


def test_t4_a_carried_finding_outside_the_change_since_the_last_reviewed_commit_is_sent_back_not_audited(tmp_path, monkeypatch):
    far = _finding(3, title="the first edit is wrong")  # the later commit touches only the hunk around line 27
    near = _finding(27)
    s = _session(tmp_path, monkeypatch, [far, near])
    first = s.next()
    assert [t["id"] for t in first["payload"]["targets"]] == [near[SC.FINDING_KEY_FIELD]], first
    assert _carried(s.state())["sentBack"] == [far[SC.FINDING_KEY_FIELD]]
    n, _seen = _run(s, _respond(audit="discharged"), stop_at=RD.P_VERIFIERS)
    state = s.state()
    assert [SC.finding_identity_key(f) for f in state["_toVerify"]] == [far[SC.FINDING_KEY_FIELD]]
    assert _row(state, near[SC.FINDING_KEY_FIELD])["disposition"] == "fixed"
    assert _row(state, far[SC.FINDING_KEY_FIELD]).get("disposition") != "fixed"


def test_t4_a_returning_decision_with_no_last_reviewed_commit_sends_the_carried_finding_to_the_panels_verifier(tmp_path, monkeypatch):
    finding = _finding(27)
    key = finding[SC.FINDING_KEY_FIELD]
    s = _session(tmp_path, monkeypatch, [finding])
    monkeypatch.setattr(RD, "_returning_decide", lambda *a, **k: None)  # a decider that gave no usable answer: full, no commit
    first = s.next()
    assert first["action"] == RD.P_PANEL and s.state()["config"]["returning"]["lastReviewed"] is None, first
    n, seen = _run(s, _respond(), stop_at=RD.P_VERIFIERS)
    state = s.state()
    assert [SC.finding_identity_key(f) for f in state["_toVerify"]] == [key], seen
    assert RD.P_AUDITS not in [a for a, _ in seen] and _carried(state) == {"keys": [key], "auditBase": None, "discharged": [], "sentBack": [key]}


def test_t4_a_caller_cannot_supply_carried_findings_itself(tmp_path, monkeypatch):
    s = _session(tmp_path, monkeypatch, [], cfg={"returningCarried": [_finding(27)]})
    s.next()
    state = s.state()
    assert "returningCarried" not in state["config"] and not state.get(SC.DISPOSITION_LEDGER_KEY)


# --- T5: no carried findings, today's returning round ---------------------------------------------------------------------

def _plain_run(tmp_path, monkeypatch, name, findings):
    s = TS.Session(tmp_path / name, monkeypatch, first=TS._first_leg(), change=TS._append("src/app.py", TR.numbered("fix", 40)))
    s.write_earlier(dict(s.record, findings=findings))
    n, seen = _run(s, _respond())
    assert n["action"] == RD.P_TERMINAL and n["payload"]["verdict"] == "converged"
    return s.state(), seen


def test_t5_no_carried_findings_runs_the_returning_round_exactly_as_it_did(tmp_path, monkeypatch):
    plain_state, plain = _plain_run(tmp_path, monkeypatch, "plain", [])
    decided_state, decided = _plain_run(tmp_path, monkeypatch, "decided",
                                        [_finding(3, title="decided", outcome="shown-wrong", reason="not a defect")])
    assert plain == decided and plain[0] == (RD.P_SCOPED, 1) and plain[-1] == (RD.P_TERMINAL, 1), plain
    assert RD.P_PANEL not in [a for a, _ in plain] and RD.P_AUDITS not in [a for a, _ in plain]
    for state in (plain_state, decided_state):
        assert "carried" not in state["rounds"]["1"] and "returningCarried" not in state["config"]
        assert not state.get(SC.DISPOSITION_LEDGER_KEY) and "_carriedToVerify" not in state and "_auditFirst" not in state


# --- E1 (panel-free record): a returning session that read nothing holds nothing a reviewer ran ------------------------------

def test_e1_a_changed_session_with_an_empty_surface_completed_by_hand_writes_no_record(tmp_path, monkeypatch):
    def catch_up(repo):  # main moves and is merged: the change since the last reviewed commit has nothing to read
        repo.moved = repo.main_commit("docs/other.md", "other\n")
        repo.merge_main()

    s = TS.Session(tmp_path, monkeypatch, change=catch_up, base_after=lambda repo: repo.moved)
    answer = s.next()
    assert answer["action"] == RD.P_TERMINAL and answer["payload"]["verdict"] == "converged", answer
    state = s.state()
    assert state["rounds"]["1"]["scopedFinder"] == "skipped-empty-surface", state["rounds"]["1"]
    fake = TRRS.Fake(head=s.head)
    out = RS.write_from_session(s.dir, TRRS.put_extras(tmp_path, TRRS.extras(ci="green")), s.repo.root, fake.readers())
    # nothing ran, so there is no reviewer row to list: the writer refuses, and posts nothing
    assert out["ok"] is False and out["reason"] == RS.UNSUPPORTED, out
    assert fake.writes == [] and fake.comments == [], (fake.writes, fake.comments)


# --- C (finding C): `_with_carried` merges a fresh report into the carried finding it matches ---------------------------------

BREAK_IT_BLOCK = "break-it-test v1\npath: tests/test_x.py\nrun: python tests/test_x.py\n---\nassert True\n"


def _compiled(held, **over):
    """A fresh report of the finding ``held`` carries: the same place and title, no stored key."""
    row = {key: held[key] for key in ("id", "title", "file", "line")}
    row.update(severity="Important", consequence=TRD._CONSEQUENCE)
    row.update(over)
    assert RD.repeat_marks.opaque_key(row) == held[SC.FINDING_KEY_FIELD]
    return row


def test_c1_a_held_minor_code_quality_finding_merges_with_a_fresh_important_real_report_under_the_held_key():
    held = _finding(27, severity="Minor", consequenceKind="code-quality")
    fresh = _compiled(held, consequenceKind="real")
    state = {"_carriedToVerify": [held]}
    [row] = RD._with_carried(state, [fresh])
    assert row["severity"] == "Important" and row["consequenceKind"] == "real", row
    assert row[SC.FINDING_KEY_FIELD] == held[SC.FINDING_KEY_FIELD]
    assert "_carriedToVerify" not in state


def test_c2_a_held_important_finding_merges_with_a_fresh_minor_report_and_stays_important():
    held = _finding(27)
    fresh = _compiled(held, severity="Minor")
    [row] = RD._with_carried({"_carriedToVerify": [held]}, [fresh])
    assert row["severity"] == "Important" and row[SC.FINDING_KEY_FIELD] == held[SC.FINDING_KEY_FIELD], row


def test_c3_a_fresh_report_under_another_key_is_kept_beside_the_held_finding():
    held = _finding(27)
    other = {"id": "F-other", "title": "another defect", "severity": "Important", "file": SHARED, "line": 3,
             "consequence": TRD._CONSEQUENCE}
    assert RD.repeat_marks.opaque_key(other) != held[SC.FINDING_KEY_FIELD]
    rows = RD._with_carried({"_carriedToVerify": [held]}, [other])
    assert sorted(r["title"] for r in rows) == sorted([held["title"], other["title"]]), rows
    assert [r for r in rows if r["title"] == held["title"]] == [held]


def test_c4_a_fresh_report_that_carries_a_break_it_test_keeps_it_when_merged_into_the_held_finding():
    held = _finding(27, severity="Minor", consequenceKind="code-quality")
    run = {"outcome": "failed", "reason": None, "exitCode": 1, "output": "", "path": "tests/test_x.py", "head": "h"}
    fresh = _compiled(held, consequenceKind="real", suggestion=BREAK_IT_BLOCK)
    fresh[RD.break_it.RUN_FIELD] = run
    assert RD.break_it.carries_test(fresh)
    [row] = RD._with_carried({"_carriedToVerify": [held]}, [fresh])
    assert row["suggestion"] == BREAK_IT_BLOCK and row[RD.break_it.RUN_FIELD] == run, row
    assert row["severity"] == "Important" and row[SC.FINDING_KEY_FIELD] == held[SC.FINDING_KEY_FIELD], row


def test_c5_a_break_it_run_bound_to_the_fresh_key_is_rebound_to_the_carried_key_on_merge():
    held = _finding(27)
    fresh = _compiled(held, suggestion=BREAK_IT_BLOCK)
    fresh_key = RD._finding_identity_key(fresh)
    assert fresh_key != held[SC.FINDING_KEY_FIELD]
    state = {"round": 1, "rounds": {"1": {"breakItRuns": [{"findingKey": fresh_key, "outcome": "failed"},
                                                          {"findingKey": "other", "outcome": "failed"}]}},
             "_carriedToVerify": [held]}
    [row] = RD._with_carried(state, [fresh])
    assert row[SC.FINDING_KEY_FIELD] == held[SC.FINDING_KEY_FIELD]
    assert [r["findingKey"] for r in state["rounds"]["1"]["breakItRuns"]] == [held[SC.FINDING_KEY_FIELD], "other"]


def test_c6_a_carried_finding_whose_record_shows_a_lost_break_it_test_is_never_audited_but_sent_back(tmp_path, monkeypatch):
    run = {"test": "tests/test_x.py", "commit": "h", "status": "ran", "exitCode": 1, "output": "", "reason": None, "changedWhy": None}
    finding = _finding(27, tradeoff=False, breakItRuns=[run])
    key = finding[SC.FINDING_KEY_FIELD]
    assert RD._carried_test_unrecoverable(finding) and not RD._carried_test_unrecoverable(_finding(27))
    s = _session(tmp_path, monkeypatch, [finding])
    first = s.next()
    assert first["action"] == RD.P_SCOPED, first  # no audit target: a later source-only fix cannot discharge a lost test
    assert _carried(s.state()) == {"keys": [key], "auditBase": s.reviewed, "discharged": [], "sentBack": [key]}
