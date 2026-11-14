"""`break-it-change` at a fix step: the build session may change a reviewer's break-it test through the verb both
while the verifiers' orders are out and at an `apply-fixes` step that is not restore-only; either way the changed
test is the one every copy of the finding carries, the one the step's test binding checks and the one the audit
compares against.

G1 at a fix step the verb, given a stored id or a finding key, changes every row that holds the finding and its ledger
   entry, records the run, and drops the pending fix step so `next` re-emits it at a fresh attempt from the changed rows.
G2 a fix report that commits the changed test folds, and the audit reads the committed test as `changed-explained`.
G3 a restore-only step, a pending correction, an id two rows share, a finding outside the current slice and a row with
   no test are each refused with the state file untouched.
G4 the PR-body snapshot the step took survives the re-emission, so a body edit made before the change still counts.
G5 any other step still refuses `break-it-change-not-at-verifiers`.
"""
import copy
import hashlib
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _path in (_HERE, _LIB):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import break_it  # noqa: E402
import pr_body_stage as PBS  # noqa: E402
import test_break_it_attached_2210 as A  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD
SC = RD.session_contract

WHY = A.WHY
WHY_AGAIN = "the second draft still asserted too much"
NOT_AT_VERIFIERS = "break-it-change-not-at-verifiers"
UNKNOWN = "break-it-change-finding-unknown"
NO_TEST = "break-it-change-no-test"
BODY = "## Summary\nAdds the retry budget.\n"
EDITED_BODY = "## Summary\nAdds the retry budget to the charge client.\n"


@pytest.fixture(autouse=True)
def _pinned_git(monkeypatch, tmp_path):
    """The fixture repo's commits read no user or system git config (autouse fixtures do not carry across an
    import, so it is pinned here)."""
    for name in ("home", "xdg-config"):
        (tmp_path / name).mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


@pytest.fixture
def fx(tmp_path):
    return A.Fixture(tmp_path)


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _respond(fx_):
    return A._respond(A._seats(test_role=[A._attached()]), A._apply_fixes(fx_))


def _at_fix_step(fx_, target=None):
    """Drive a real session to the pending fix step (or ``target``); returns that `next`."""
    return TRD._drive_to_phase(str(fx_.session), fx_.config, _respond(fx_), target or RD.P_APPLY_FIXES)


def _state(session):
    ok, state = RD.load_state(session)
    assert ok
    return state


def _edit_state(session, edit):
    state = _state(session)
    edit(state)
    RD.save_state(session, state)


def _change(tmp_path, session, ref, content, why=WHY):
    return RD.cmd_break_it_change(session, ref, A._content_file(tmp_path, content), why)


def _holders(state, key):
    """Every row that holds the finding `key`'s test: the rows outside the ledger and its ledger entry."""
    rows = RD._reviewer_test_rows(state, key)
    ledger = [row for row in state[SC.DISPOSITION_LEDGER_KEY] if RD._finding_identity_key(row) == key]
    assert len(rows) >= 2 and len(ledger) == 1, (len(rows), len(ledger))
    return rows + ledger


# ---- G1 -----------------------------------------------------------------------------------------------------

def test_g1_at_a_fix_step_the_verb_changes_every_copy_and_the_step_is_re_emitted_from_them(fx, tmp_path):
    session = str(fx.session)
    old = _at_fix_step(fx)
    state = _state(session)
    (row,) = state["_fixBatch"]
    key, stored_id = RD._finding_identity_key(row), row["id"]
    assert isinstance(stored_id, str) and stored_id
    assert state["pending"]["phase"] == RD.P_APPLY_FIXES and state["pending"]["attempt"] == old["attempt"]
    runs_before = len(state["rounds"]["1"]["breakItRuns"])
    heads = (state["_fixStepHead"], state["_fixAttemptStartHead"])
    original = break_it.carried_block(row)[0]["content"]
    assert original == A._TEST_FAILING

    out = _change(tmp_path, session, stored_id, A._TEST_PASSING)
    assert out["ok"] is True and out["finding"] == stored_id
    assert out["run"]["sha256"] == _sha(A._TEST_PASSING)
    state = _state(session)
    want = A._block(A.ATTACHED_TEST, A._TEST_PASSING)
    for holder in _holders(state, key):
        assert holder["suggestion"] == want
        assert holder[break_it.RUN_FIELD] == out["run"]
        assert holder[RD.REVIEWER_TEST_FIELD] == original
        assert [r["changedWhy"] for r in holder[break_it.RUNS_FIELD]] == [None, WHY]
    runs = state["rounds"]["1"]["breakItRuns"]
    assert len(runs) == runs_before + 1
    assert (runs[-1]["changedWhy"], runs[-1]["findingKey"]) == (WHY, key)
    assert state["pending"] is None
    assert (state["_fixStepHead"], state["_fixAttemptStartHead"]) == heads
    journal = RD.read_journal(session)[-1]
    assert (journal["cmd"], journal["outcome"], journal["phase"], journal["supersededAttempt"]) == (
        "break-it-change", "changed", RD.P_APPLY_FIXES, old["attempt"])

    fresh = RD.cmd_next(session)
    assert fresh["ok"] and fresh["action"] == RD.P_APPLY_FIXES and fresh["attempt"] > old["attempt"]
    (carried,) = fresh["payload"]["batch"]
    assert carried["suggestion"] == want
    assert [r["changedWhy"] for r in carried[break_it.RUNS_FIELD]] == [None, WHY]
    assert fresh["payload"]["startHead"] == heads[0]

    # by the finding key, and a later change keeps the test role's first version
    again = _change(tmp_path, session, key, A._TEST_PASSING + "# again\n", WHY_AGAIN)
    assert again["ok"] is True and again["finding"] == stored_id
    state = _state(session)
    for holder in _holders(state, key):
        assert holder[RD.REVIEWER_TEST_FIELD] == original
        assert [r["changedWhy"] for r in holder[break_it.RUNS_FIELD]] == [None, WHY, WHY_AGAIN]
        assert break_it.carried_block(holder)[0]["content"] == A._TEST_PASSING + "# again\n"


def test_g1_a_positional_verifier_id_is_not_a_name_at_a_fix_step(fx, tmp_path):
    session = str(fx.session)
    _at_fix_step(fx)
    _edit_state(session, lambda s: s["_fixBatch"][0].update(id="v7"))
    A._assert_refused(session, UNKNOWN, "v0", A._content_file(tmp_path, A._TEST_PASSING), WHY)
    assert _change(tmp_path, session, "v7", A._TEST_PASSING)["finding"] == "v7"


@pytest.mark.parametrize("ref", ["v9", "not-a-finding-key", ""])
def test_g1_a_value_the_resolver_does_not_map_is_refused(fx, tmp_path, ref):
    _at_fix_step(fx)
    A._assert_refused(str(fx.session), UNKNOWN, ref, A._content_file(tmp_path, A._TEST_PASSING), WHY)


# ---- G2 -----------------------------------------------------------------------------------------------------

def test_g2_the_changed_test_is_the_one_the_fix_commits_and_the_audit_compares_against(fx, tmp_path):
    session = str(fx.session)
    respond = _respond(fx)
    _at_fix_step(fx)
    row = _state(session)["_fixBatch"][0]
    assert _change(tmp_path, session, row["id"], A._TEST_PASSING)["ok"] is True
    matches = []

    def watching(phase, payload, rnd):
        if phase == RD.P_AUDITS:
            matches.extend(t["breakIt"]["match"] for t in payload["targets"] if t.get("breakIt"))
        return respond(phase, payload, rnd)

    payload = TRD._drive_cli(session, fx.config, watching)
    state = _state(session)
    assert matches == ["changed-explained"]
    assert A._git(fx.repo, "show", "HEAD:" + A.ATTACHED_TEST) == A._TEST_PASSING.strip()
    (kept,) = [r for rec in state["rounds"].values() for r in rec.get("breakItKept") or []]
    assert (kept["findingKey"], kept["path"], kept["outcome"]) == (
        RD._finding_identity_key(row), A.ATTACHED_TEST, break_it.KEPT)
    kinds = [d["kind"] for d in state["decisions"]]
    assert "cannot-certify" not in kinds
    assert not any(RD.FIX_WITHOUT_TEST in str(d.get("detail")) for d in state["decisions"])
    assert payload["verdict"] == "converged", payload


# ---- G3 -----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("edit", [
    lambda s: s.update({RD.TEST_RESTORE_FIELD: {"restores": []}}),
    lambda s: s.update({RD.TEST_CORRECTION_PENDING_FIELD: {"findingKeys": []}}),
    lambda s: s.update({RD.TEST_CORRECTION_PENDING_FIELD: {"findingKeys": []}, "step": RD.P_SECOND_TEST}),
], ids=["restore-only step", "correction pending at the fix step", "correction step"])
def test_g3_a_restore_only_step_or_a_pending_correction_is_refused_with_the_state_untouched(fx, tmp_path, edit):
    session = str(fx.session)
    _at_fix_step(fx)
    row = _state(session)["_fixBatch"][0]
    _edit_state(session, edit)
    A._assert_refused(session, NOT_AT_VERIFIERS, row["id"], A._content_file(tmp_path, A._TEST_PASSING), WHY)


def _with_second_row(state):
    """The fix batch gains a second finding that shares the first one's stored id."""
    other = copy.deepcopy(state["_fixBatch"][0])
    other[SC.FINDING_KEY_FIELD] = "src/payments/other.py::another-finding@L9"
    other["title"] = "Another finding"
    state["_fixBatch"].append(other)
    return other


def test_g3_an_id_two_rows_share_is_refused_and_either_finding_key_is_accepted(fx, tmp_path):
    session = str(fx.session)
    _at_fix_step(fx)
    _edit_state(session, _with_second_row)
    first, second = _state(session)["_fixBatch"]
    assert first["id"] == second["id"]
    A._assert_refused(session, UNKNOWN, first["id"], A._content_file(tmp_path, A._TEST_PASSING), WHY)
    for index, row in enumerate((first, second)):
        out = _change(tmp_path, session, RD._finding_identity_key(row), A._TEST_PASSING + "# %d\n" % index)
        assert out["ok"] is True and out["finding"] == row["id"]
        landed = _state(session)["_fixBatch"][index]
        assert break_it.carried_block(landed)[0]["content"] == A._TEST_PASSING + "# %d\n" % index


@pytest.mark.parametrize("by", ["id", "key"])
def test_g3_a_finding_outside_the_current_slice_is_refused(fx, tmp_path, by):
    session = str(fx.session)
    _at_fix_step(fx)
    state = _state(session)
    (row,) = state["_fixBatch"]
    ref = row["id"] if by == "id" else RD._finding_identity_key(row)

    def move_to_a_later_slice(s):
        later = s["_fixBatch"][0]
        s["_fixQueue"] = [later]
        s["_fixBatch"] = [dict(copy.deepcopy(later), id="v5", title="A different finding",
                               **{SC.FINDING_KEY_FIELD: "src/payments/other.py::a-different-finding@L3"})]

    _edit_state(session, move_to_a_later_slice)
    A._assert_refused(session, UNKNOWN, ref, A._content_file(tmp_path, A._TEST_PASSING), WHY)


def test_g3_a_fix_batch_row_with_no_test_is_refused(fx, tmp_path):
    session = str(fx.session)
    _at_fix_step(fx)
    row = _state(session)["_fixBatch"][0]

    def drop_the_test(s):
        s["_fixBatch"][0]["suggestion"] = "no test rides on this finding"
        s["_fixBatch"][0].pop(break_it.RUN_FIELD, None)

    _edit_state(session, drop_the_test)
    A._assert_refused(session, NO_TEST, row["id"], A._content_file(tmp_path, A._TEST_PASSING), WHY)


# ---- G4 -----------------------------------------------------------------------------------------------------

def test_g4_the_pr_body_snapshot_survives_the_re_emission_and_the_fold_credits_the_body_edit(fx, tmp_path):
    session = str(fx.session)
    (fx.session / "pr.json").write_text(json.dumps({"number": 7, "body": BODY}))
    old = _at_fix_step(fx)
    staged = PBS.paths(session)["staged"]
    assert _state(session)["_prBodyAtStep"] == _sha(BODY)
    with open(staged, "w", encoding="utf-8") as fh:
        fh.write(EDITED_BODY)
    row = _state(session)["_fixBatch"][0]
    assert _change(tmp_path, session, row["id"], A._TEST_PASSING)["ok"] is True
    fresh = RD.cmd_next(session)
    assert fresh["ok"] and fresh["action"] == RD.P_APPLY_FIXES and fresh["attempt"] > old["attempt"]
    assert _state(session)["_prBodyAtStep"] == _sha(BODY)
    with open(staged, encoding="utf-8") as fh:
        assert fh.read() == EDITED_BODY
    artifact = A._apply_fixes(fx)(fresh["payload"])
    folded = RD.cmd_submit(session, fresh["phase"], fresh["attempt"], fresh["expectedStateHash"],
                           TRD._claim_reviewer(session, fresh["phase"], artifact))
    assert folded["ok"], folded
    assert _state(session)["rounds"]["1"]["prBodyFix"] == {"before": _sha(BODY), "after": _sha(EDITED_BODY)}


# ---- G5 -----------------------------------------------------------------------------------------------------

def test_g5_a_step_that_is_neither_the_verifiers_nor_a_fix_step_is_still_refused(fx, tmp_path):
    session = str(fx.session)
    _at_fix_step(fx, RD.P_AUDITS)
    assert _state(session)["step"] == RD.P_AUDITS
    A._assert_refused(session, NOT_AT_VERIFIERS, "v0", A._content_file(tmp_path, A._TEST_PASSING), WHY)
