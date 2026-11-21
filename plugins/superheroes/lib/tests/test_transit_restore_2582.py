"""A break-it test whose text carries a transit redaction placeholder never becomes a restore demand.

The invariant: a break-it test whose text carries a transit placeholder (the stamp `break_it.TRANSIT_FIELD`, or the
`[REDACTED...]` family in the block's path, run or content, or in an extra text the caller passes) is recorded not run,
reason `transit-redacted`, at every step of the review loop that reads the test's bytes (intake, the audit fold, the
correction fold, the final kept check), and is never turned into a demand for those bytes nor handed to a runner. A
clean test behaves exactly as before.

Every placeholder is built from pieces at run time: a whole placeholder written to disk is replaced by the cloud redactor.
No credential-like value is used here.

R1  the field replay: an unstamped test whose saved text holds the placeholder takes no restore;
R1b the placeholder only in the saved reviewer test; R1c only in the committed copy;
R2  a stamped source finding: the stamp survives into the audit target and the fold takes no restore;
R3  the clean pin: a clean weakened test is restored as before;
R4  two mismatched targets, one damaged: the restore step carries only the clean one;
R5  every target damaged: the audit goes on as with no mismatch;
R6  the bounded pass: a damaged target is filtered before `_bounded_mismatch`;
R7  intake: `break_it.intercept` never runs an unstamped damaged test, and stamps it;
R8  the correction fold: an unstamped damaged correction is no correction, `transit-redacted`;
R9  the final kept check answers `unresolved`, `transit-redacted`, and never calls the runner;
R10 the predicate itself.

Bite-proof record: wo_a_2582_transit_restore
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

import break_it  # noqa: E402
import decision_kinds  # noqa: E402
import test_bounded_pass_b2_2554 as BP  # noqa: E402
import test_break_it_body_2053 as BB  # noqa: E402
import test_c1l10_audit_checks as C1  # noqa: E402
import test_c1l10b_test_restore as TR  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD

PLACEHOLDER = "[" + "REDACTED]"
TOKEN_LINE = "    token = " + PLACEHOLDER + "\n"
TEST_PATH = C1.TEST_PATH
ROLE_TEST = C1.ROLE_TEST
FIXED_TEST = C1.FIXED_TEST
WHY = C1.WHY
DAMAGED_ROLE = ROLE_TEST + TOKEN_LINE
KIND = "break-it-restore-transit-redacted"


@pytest.fixture(autouse=True)
def _pinned_git_config(monkeypatch, tmp_path):
    for name in ("home", "xdg-config"):
        (tmp_path / name).mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    BB._git(root, "init", "-q")
    BB._write(root, "README.md", "fixture\n")
    BB._write(root, "mod.py", "def value():\n    return 2\n")
    BB._commit(root, "base")
    return root


def _swap_finding(w, finding):
    """Put ``finding`` (same key) in the world's batch and rebuild its audit targets."""
    assert RD._finding_key_of(finding) == w.key
    w.finding = finding
    w.state["fixBatch"] = [finding]
    w.state["findings"] = [copy.deepcopy(finding)]
    w.state["_auditTargets"] = RD._audit_targets(w.state, w.cfg, {})


def _entry(key, path=TEST_PATH):
    return {"findingKey": key, "path": path, "step": "restore", "outcome": "not-run",
            "reason": "transit-redacted"}


def _assert_no_restore(w, path=TEST_PATH):
    """The audit listed the mismatch, took no restore, recorded the test not run and went on."""
    rec = w.state["rounds"]["2"]
    assert rec["testMismatch"] == [w.key]
    assert RD.TEST_RESTORE_FIELD not in w.state
    assert w.state["step"] == RD.P_VERIFY
    step = w.step()
    assert step["action"] != RD.P_APPLY_FIXES and "restoreOnly" not in json.dumps(step)
    assert rec["breakItTransitRedacted"] == [_entry(w.key, path)]
    kinds = TR._decisions(w.state)
    assert KIND in kinds and "break-it-test-restored" not in kinds
    assert w.state["_auditOutcome"]["notDischarged"] == [w.key]


# --- R1: the field replay (DoD 1) ----------------------------------------------------------------------------------

def test_r1_an_unstamped_test_whose_saved_text_holds_the_placeholder_takes_no_restore(tmp_path):
    # axis: G1 — the audit fold's damaged split — see bite-proof record wo_a_2582_transit_restore
    w = TR.World(tmp_path, committed=None)
    finding = C1._finding(content=DAMAGED_ROLE, reviewer_test=DAMAGED_ROLE, changed_why=WHY)
    assert break_it.TRANSIT_FIELD not in finding
    _swap_finding(w, finding)
    w.audit()
    _assert_no_restore(w)
    detail = [d["detail"] for d in w.state["decisions"] if d["kind"] == KIND]
    assert len(detail) == 1 and w.key in detail[0] and "recorded not run" in detail[0]


def test_r1b_the_placeholder_only_in_the_saved_reviewer_test_takes_no_restore(tmp_path):
    # axis: G2 — the predicate reads the audit facts' reviewerTest — see bite-proof record wo_a_2582_transit_restore
    w = TR.World(tmp_path)
    finding = C1._finding(content=FIXED_TEST, reviewer_test=DAMAGED_ROLE, changed_why=WHY)
    _swap_finding(w, finding)
    target = w.state["_auditTargets"][0]
    assert not break_it.test_transit_damaged(target) and target["breakIt"]["reviewerTest"] == DAMAGED_ROLE
    w.audit()
    _assert_no_restore(w)


def test_r1c_the_placeholder_only_in_the_committed_copy_takes_no_restore(tmp_path):
    # axis: G2 — the predicate reads the audit facts' committedTest — see bite-proof record wo_a_2582_transit_restore
    w = TR.World(tmp_path, committed=FIXED_TEST + TOKEN_LINE)
    target = w.state["_auditTargets"][0]
    assert not break_it.test_transit_damaged(target)
    assert target["breakIt"]["reviewerTest"] == ROLE_TEST and PLACEHOLDER in target["breakIt"]["committedTest"]
    w.audit()
    _assert_no_restore(w)


# --- R2: the stamp survives into the audit target (B2) -------------------------------------------------------------

def test_r2_a_stamped_source_finding_carries_its_stamp_into_the_target_and_takes_no_restore(tmp_path):
    # axis: G3 — the target carries TRANSIT_FIELD — see bite-proof record wo_a_2582_transit_restore
    w = TR.World(tmp_path)
    finding = C1._finding(content=FIXED_TEST, reviewer_test=ROLE_TEST, changed_why=WHY)
    finding[break_it.TRANSIT_FIELD] = True
    assert not break_it.test_transit_damaged(dict(finding, **{break_it.TRANSIT_FIELD: False}))
    _swap_finding(w, finding)
    target = w.state["_auditTargets"][0]
    assert target[break_it.TRANSIT_FIELD] is True
    facts = target["breakIt"]
    assert not any(break_it.transit_redacted(facts.get(k)) for k in ("path", "reviewerTest", "committedTest"))
    w.audit()
    _assert_no_restore(w)


# --- R3: the clean pin (DoD 2) -------------------------------------------------------------------------------------

def test_r3_a_clean_weakened_test_is_still_restored_with_the_reviewers_bytes(tmp_path):
    w = TR.World(tmp_path)
    assert not break_it.test_transit_damaged(w.state["_auditTargets"][0], *[
        w.state["_auditTargets"][0]["breakIt"][k] for k in ("path", "reviewerTest", "committedTest")])
    w.audit()
    assert w.state["rounds"]["2"]["testMismatch"] == [w.key]
    step = w.step()
    assert step["action"] == RD.P_APPLY_FIXES and step["payload"]["restoreOnly"] is True
    assert step["payload"]["restores"] == [{"findingKey": w.key, "path": TEST_PATH, "content": ROLE_TEST,
                                            "sha256": TR._sha(ROLE_TEST)}]
    w.restore()
    assert w.committed() == ROLE_TEST
    assert "breakItTransitRedacted" not in w.state["rounds"]["2"]
    assert KIND not in TR._decisions(w.state) and "break-it-test-restored" in TR._decisions(w.state)


# --- R4: one damaged target and one clean one ----------------------------------------------------------------------

def test_r4_the_restore_step_carries_only_the_clean_target_and_the_damaged_one_is_recorded(tmp_path):
    w = TR.World(tmp_path)
    second = copy.deepcopy(w.finding)
    second["title"] = "Another retry bug"
    second["suggestion"] = C1._block_text(FIXED_TEST).replace(TEST_PATH, "tests/test_other.py")
    second[RD.REVIEWER_TEST_FIELD] = ROLE_TEST
    damaged = copy.deepcopy(w.finding)
    damaged[RD.REVIEWER_TEST_FIELD] = DAMAGED_ROLE
    w.write("tests/test_other.py", FIXED_TEST)
    head = TR._commit(w.root, "second test")
    w.state["rounds"]["1"]["fixFoldHead"] = head
    w.state["fixBatch"] = [damaged, second]
    w.state["_auditTargets"] = RD._audit_targets(w.state, w.cfg, {})
    second_key = RD._finding_key_of(second)
    assert second_key != w.key
    w.audit()
    step = w.step()
    assert step["payload"]["restoreOnly"] is True
    assert [r["path"] for r in step["payload"]["restores"]] == ["tests/test_other.py"]
    assert [r["findingKey"] for r in step["payload"]["restores"]] == [second_key]
    assert w.state["rounds"]["2"]["breakItTransitRedacted"] == [_entry(w.key)]
    detail = [d["detail"] for d in w.state["decisions"] if d["kind"] == KIND]
    assert len(detail) == 1 and w.key in detail[0] and second_key not in detail[0]
    w.write("tests/test_other.py", ROLE_TEST)
    TR._commit(w.root, "restore the clean one")
    w.fold(RD.P_APPLY_FIXES, {"fixes": []})
    step = w.step()
    assert step["action"] == RD.P_SECOND_TEST and len(step["payload"]["findings"]) == 1


# --- R5: every target damaged, the other continuation ------------------------------------------------------------

def _continuation_spy(monkeypatch):
    calls = []
    real = RD._after_audits

    def spy(state, config, session_dir=None):
        calls.append(state["step"])
        return real(state, config, session_dir=session_dir)

    monkeypatch.setattr(RD, "_after_audits", spy)
    return calls


def test_r5_with_every_target_damaged_and_no_post_audits_verify_the_audit_goes_on_as_with_no_mismatch(
        tmp_path, monkeypatch):
    calls = _continuation_spy(monkeypatch)
    # the control: an identical clean world whose audit lists no mismatch and leaves the finding open the same way
    clean = TR.World(tmp_path / "clean", committed=ROLE_TEST)
    clean.state["fixBatch"] = [C1._finding()]
    clean.state["_auditTargets"] = RD._audit_targets(clean.state, clean.cfg, {})
    clean.state.pop("_verifyThen")
    artifact = clean.audit_artifact()
    for result in artifact["results"]:
        result.update(ruling="not-discharged", reason="still broken", checks=TRD.audit_checks(right="no"))
    clean.fold(RD.P_AUDITS, artifact)
    assert "testMismatch" not in clean.state["rounds"]["2"] and len(calls) == 1
    assert clean.state["_auditOutcome"]["notDischarged"] == [clean.key]
    expected_step = clean.state["step"]
    calls.clear()

    w = TR.World(tmp_path / "damaged", committed=None)
    _swap_finding(w, C1._finding(content=DAMAGED_ROLE, reviewer_test=DAMAGED_ROLE, changed_why=WHY))
    w.state.pop("_verifyThen")
    w.audit()
    assert w.state["rounds"]["2"]["testMismatch"] == [w.key]
    assert w.state["rounds"]["2"]["breakItTransitRedacted"] == [_entry(w.key)]
    assert RD.TEST_RESTORE_FIELD not in w.state and len(calls) == 1
    # an open finding's ordinary continuation is the next fix step; what it must not be is the restore-only one
    assert w.state["step"] == expected_step
    assert "restoreOnly" not in json.dumps(w.step())


# --- R6: the bounded pass -----------------------------------------------------------------------------------------

def test_r6_a_damaged_target_is_filtered_before_the_bounded_mismatch_in_b1(tmp_path):
    # axis: G1 — the damaged split runs before `_bounded_mismatch` — see bite-proof record wo_a_2582_transit_restore
    w = BP._bounded_world(tmp_path, "audit", BP.CAP + 1)
    w.state["_auditTargets"][0]["breakIt"]["reviewerTest"] = DAMAGED_ROLE
    w.audit()
    state = w.state
    rec = state["rounds"][str(BP.CAP + 1)]
    assert rec["testMismatch"] == [w.key] and rec["breakItTransitRedacted"] == [_entry(w.key)]
    assert "restores" not in state["boundedPass"] and RD._bounded_restore_payload(state) == []
    assert RD.TEST_RESTORE_FIELD not in state and state["step"] == RD.P_APPLY_FIXES
    step = w.step()
    assert step["action"] == RD.P_APPLY_FIXES and "restoreOnly" not in step["payload"]
    assert state["_auditOutcome"]["notDischarged"] == [w.key]
    assert KIND in TR._decisions(state)


def test_r6_a_damaged_only_mismatch_in_the_final_audit_does_not_hand_back_bounded_pass_open(tmp_path):
    # axis: G1 — the damaged split runs before `_bounded_mismatch` — see bite-proof record wo_a_2582_transit_restore
    w = BP._bounded_world(tmp_path, "final-audit", BP.CAP + 2)
    w.state["_auditTargets"][0]["breakIt"]["reviewerTest"] = DAMAGED_ROLE
    w.audit()
    state = w.state
    kinds = TR._decisions(state)
    assert "bounded-pass-open" not in kinds and KIND in kinds and "break-it-test-mismatch" in kinds
    assert state["rounds"][str(BP.CAP + 2)]["breakItTransitRedacted"] == [_entry(w.key)]
    assert RD.TEST_RESTORE_FIELD not in state


# --- R7: intake ---------------------------------------------------------------------------------------------------

def _spy_runner(calls, outcome="passed"):
    def runner(repo_root, head, block, **kwargs):
        calls.append(block["path"])
        return break_it._record(head, block, outcome, exit_code=0 if outcome == "passed" else 1)
    return runner


def test_r7_intercept_never_runs_an_unstamped_test_whose_block_holds_the_placeholder_and_stamps_it():
    # axis: G4 — intercept reads the block's text, not the stamp alone — see bite-proof record wo_a_2582_transit_restore
    finding = C1._finding(content=DAMAGED_ROLE)
    assert break_it.TRANSIT_FIELD not in finding
    calls = []
    kept, runs, exempt, stamped = break_it.intercept([finding], "/nowhere", "H", runner=_spy_runner(calls))
    assert calls == []
    record = kept[0][break_it.RUN_FIELD]
    assert record["outcome"] == break_it.OUTCOME_NOT_RUN and record["reason"] == "transit-redacted"
    assert runs[0]["outcome"] == break_it.OUTCOME_NOT_RUN and runs[0]["reason"] == "transit-redacted"
    assert kept[0][break_it.TRANSIT_FIELD] is True
    assert break_it.TRANSIT_FIELD not in finding, "the seat's own finding is not mutated"


def test_r7_a_clean_finding_still_calls_the_runner_once_and_carries_no_stamp():
    finding = C1._finding(content=ROLE_TEST)
    calls = []
    kept, runs, exempt, stamped = break_it.intercept([finding], "/nowhere", "H", runner=_spy_runner(calls))
    assert calls == [TEST_PATH]
    assert kept[0][break_it.RUN_FIELD]["outcome"] == break_it.OUTCOME_PASSED
    assert break_it.TRANSIT_FIELD not in kept[0]


def test_r7b_a_scrub_flagged_finding_with_a_placeholder_in_its_header_stays_suggestion_redacted():
    # axis: G7 — the scrub flag is consulted before the text read, so the adapter's own header placeholder is not transit damage — see bite-proof record wo_a_2582_transit_restore
    finding = _finding_with(run=C1.RUN + " --key " + PLACEHOLDER)
    finding[break_it.REDACTED_FIELD] = True
    assert break_it.TRANSIT_FIELD not in finding
    assert break_it.test_transit_damaged(finding) is True, "the header placeholder is real, so only the flag keeps it off the transit path"
    calls = []
    kept, runs, exempt, stamped = break_it.intercept([finding], "/nowhere", "H", runner=_spy_runner(calls))
    assert calls == []
    record = kept[0][break_it.RUN_FIELD]
    assert record["outcome"] == break_it.OUTCOME_NOT_RUN and record["reason"] == "suggestion-redacted"
    assert runs[0]["outcome"] == break_it.OUTCOME_NOT_RUN and runs[0]["reason"] == "suggestion-redacted"
    assert break_it.TRANSIT_FIELD not in kept[0], "the copy is not stamped transit-redacted"
    assert break_it.TRANSIT_FIELD not in finding


def test_r7b_both_flags_set_keeps_transit_redacted_and_a_content_placeholder_with_the_scrub_flag_does_not_run():
    both = _finding_with(run=C1.RUN + " --key " + PLACEHOLDER)
    both[break_it.REDACTED_FIELD] = True
    both[break_it.TRANSIT_FIELD] = True
    in_content = _finding_with(content=DAMAGED_ROLE)
    in_content[break_it.REDACTED_FIELD] = True
    calls = []
    kept, runs, exempt, stamped = break_it.intercept([both, in_content], "/nowhere", "H", runner=_spy_runner(calls))
    assert calls == []
    assert kept[0][break_it.RUN_FIELD]["reason"] == "transit-redacted" and kept[0][break_it.TRANSIT_FIELD] is True
    assert kept[1][break_it.RUN_FIELD]["reason"] == "suggestion-redacted"
    assert break_it.TRANSIT_FIELD not in kept[1]


# --- R8: the correction fold --------------------------------------------------------------------------------------

def test_r8_an_unstamped_correction_whose_block_holds_the_placeholder_is_no_correction(tmp_path):
    # axis: G5 — the correction fold's predicate — see bite-proof record wo_a_2582_transit_restore
    w = TR.World(tmp_path)
    w.audit()
    w.restore()
    assert w.state["step"] == RD.P_SECOND_TEST
    result = {"id": w.key, "suggestion": C1._block_text(ROLE_TEST + "    other = 1\n" + TOKEN_LINE)}
    assert break_it.TRANSIT_FIELD not in result
    w.fold(RD.P_SECOND_TEST, {"findings": [result]})
    assert w.state["rounds"]["2"]["testCorrection"] == [
        {"findingKey": w.key, "outcome": "none", "reason": "transit-redacted"}]
    assert w.state["step"] == RD.P_VERIFY and w.state["step"] != RD.P_APPLY_FIXES
    assert RD.TEST_RESTORE_FIELD not in w.state and w.committed() == ROLE_TEST


# --- R9: the final kept check -------------------------------------------------------------------------------------

def _got(result):
    return result["outcome"], result["reason"]


UNRESOLVED = (break_it.KEPT_UNRESOLVED, "transit-redacted")


def test_r9a_a_record_whose_content_holds_the_placeholder_is_unresolved_and_never_run(repo):
    # axis: G6 — the kept check's guard — see bite-proof record wo_a_2582_transit_restore
    damaged = BB.ORIG + "\n# note " + PLACEHOLDER + "\n"
    base, head = BB._stage(repo, {BB.OWN: damaged})
    calls = []
    result = BB._check(repo, base, head, BB._record(content=damaged), BB._stub(calls))
    assert _got(result) == UNRESOLVED and result["run"] is None and calls == []


def test_r9a_a_clean_copy_found_for_a_record_whose_content_holds_the_placeholder_is_never_run(repo):
    # axis: G6 — the body search's guard — see bite-proof record wo_a_2582_transit_restore
    damaged = BB.ORIG + "\n# note " + PLACEHOLDER + "\n"
    host = BB._host(body=BB.BODY.replace("test_x", "test_x_moved"))
    base, head = BB._stage(repo, {"tests/test_weekly.py": host})
    calls = []
    result = BB._check(repo, base, head, BB._record(content=damaged), BB._stub(calls))
    assert _got(result) == UNRESOLVED and result["run"] is None and calls == []


def test_r9b_a_clean_record_whose_committed_blob_holds_the_placeholder_is_unresolved_and_never_run(repo):
    # axis: G6 — the kept check's guard reads the committed blob — see bite-proof record wo_a_2582_transit_restore
    committed = "assert True\n# note " + PLACEHOLDER + "\n"
    base, head = BB._stage(repo, {BB.OWN: committed})
    record = {"path": BB.OWN, "command": BB._cmd(), "sha256": BB._sha(committed)}
    assert not break_it.transit_redacted(record.get("content"))
    calls = []
    result = BB._check(repo, base, head, record, BB._stub(calls))
    assert _got(result) == UNRESOLVED and result["run"] is None and calls == []


def test_r9c_a_relocated_copy_whose_file_holds_the_placeholder_is_unresolved_and_never_run(repo):
    # axis: G6 — the body search's guard reads the located copy's file — see bite-proof record wo_a_2582_transit_restore
    host = BB._host(body=BB.BODY.replace("test_x", "test_x_moved"), after="\n\n# note " + PLACEHOLDER + "\n")
    base, head = BB._stage(repo, {"tests/test_weekly.py": host})
    calls = []
    result = BB._check(repo, base, head, BB._record(), BB._stub(calls))
    assert _got(result) == UNRESOLVED and result["run"] is None and calls == []


def test_r9d_a_clean_record_and_clean_files_still_reach_the_runner(repo):
    calls = []
    base, head = BB._stage(repo, {BB.OWN: "assert True\n"})
    record = {"path": BB.OWN, "command": BB._cmd(), "sha256": BB._sha("assert True\n")}
    result = BB._check(repo, base, head, record, BB._stub(calls))
    assert _got(result) == (break_it.KEPT, None) and len(calls) == 1
    # a relocated clean copy is run as before
    calls.clear()
    moved = BB._host(body=BB.BODY.replace("test_x", "test_x_moved"))
    base2, head2 = BB._stage(repo, {"tests/test_weekly.py": moved})
    result = BB._check(repo, base2, head2, BB._record(), BB._stub(calls))
    assert _got(result) == (break_it.KEPT, "body-match") and len(calls) == 1


def _finding_with(**block):
    fields = {"path": TEST_PATH, "run": C1.RUN}
    content = block.pop("content", ROLE_TEST)
    fields.update(block)
    return {"title": "t", "file": TEST_PATH, "line": 1, "taxonomy": break_it.TAXONOMY,
            "suggestion": RD._break_it_block_text(fields, content)}


# --- R11: the same-anchor merge carry -----------------------------------------------------------------------------

def test_r11_a_same_anchor_merge_an_ordinary_finding_wins_carries_the_transit_stamp():
    # axis: G8 — the transit stamp rides the carried test through a same-anchor merge — see bite-proof record wo_a_2582_transit_restore
    run = {"outcome": break_it.OUTCOME_NOT_RUN, "reason": "transit-redacted"}
    carrier = {"file": "f.py", "line": 1, "title": "t", "severity": "Nit", "taxonomy": break_it.TAXONOMY,
               "suggestion": "carried", break_it.RUN_FIELD: run, break_it.TRANSIT_FIELD: True}
    plain = {"file": "f.py", "line": 1, "title": "t", "severity": "Critical"}
    for existing, incoming in ((carrier, plain), (plain, carrier)):
        merged = RD._merge_same_finding(existing, incoming)
        assert merged["severity"] == "Critical"
        assert merged[break_it.RUN_FIELD] == run
        assert merged[break_it.TRANSIT_FIELD] is True


def test_r11_a_carrier_with_no_stamp_leaves_the_merged_finding_unstamped():
    run = {"outcome": break_it.OUTCOME_PASSED}
    carrier = {"file": "f.py", "line": 1, "title": "t", "severity": "Nit", "taxonomy": break_it.TAXONOMY,
               "suggestion": "carried", break_it.RUN_FIELD: run}
    plain = {"file": "f.py", "line": 1, "title": "t", "severity": "Critical"}
    for existing, incoming in ((carrier, plain), (plain, carrier)):
        merged = RD._merge_same_finding(existing, incoming)
        assert merged["severity"] == "Critical"
        assert merged[break_it.RUN_FIELD] == run
        assert break_it.TRANSIT_FIELD not in merged


# --- R10: the predicate -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("finding", [
    pytest.param({break_it.TRANSIT_FIELD: True}, id="stamp"),
    pytest.param(_finding_with(path="tests/test_" + PLACEHOLDER + ".py"), id="path"),
    pytest.param(_finding_with(run=C1.RUN + " --key " + PLACEHOLDER), id="run"),
    pytest.param(_finding_with(content=DAMAGED_ROLE), id="content"),
    pytest.param(_finding_with(content=ROLE_TEST + "    x = '[" + "REDACTED:key]'\n"), id="content-with-a-label"),
])
def test_r10_the_predicate_is_true_for_the_stamp_and_for_each_text_of_the_block(finding):
    assert break_it.test_transit_damaged(finding) is True


@pytest.mark.parametrize("extra", [
    pytest.param(("clean", PLACEHOLDER), id="second"),
    pytest.param((PLACEHOLDER,), id="only"),
])
def test_r10_the_predicate_is_true_for_an_extra_text(extra):
    assert break_it.test_transit_damaged(_finding_with(), *extra) is True
    assert break_it.test_transit_damaged(None, *extra) is True


def test_r10_the_predicate_is_false_for_a_clean_finding_a_non_dict_and_the_bare_word():
    assert break_it.test_transit_damaged(_finding_with()) is False
    assert break_it.test_transit_damaged(_finding_with(), "clean", None, 5) is False
    assert break_it.test_transit_damaged({break_it.TRANSIT_FIELD: False}) is False
    for not_a_dict in (None, "x", 5, ["a"]):
        assert break_it.test_transit_damaged(not_a_dict) is False
    bare = _finding_with(content=ROLE_TEST + "    note = 'REDACTED'\n")
    assert break_it.test_transit_damaged(bare) is False
    assert break_it.test_transit_damaged(bare, "REDACTED", "[REDACTED") is False


def test_the_new_decision_kind_is_registered():
    assert KIND in decision_kinds.DECISION_KINDS
