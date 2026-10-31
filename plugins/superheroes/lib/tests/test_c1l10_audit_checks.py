"""C1-L10: the fix auditor answers three checks per fix, and checks the committed break-it test against the test role's.

Pins, each at the place the rule is enforced:

K1  `audits.audit_checks_fault` is the one judge of the shape: the payload contract's `audit-checks` predicate, the
    submit guard (`round_driver.audit_results_fault`) and the fold (`audits.apply_audit_results`) all call it;
K2  the fold honours a clearing ruling only on three `yes` answers, and fails closed on a result without them;
K3  the strict-mode schema and the engine parser carry `checks` and `testMatch` through to the fold;
K4  `breakIt.match` on an audit target is `same`, `changed-explained`, `changed-unexplained` or `missing`, read from
    git at the audited head;
K5  `missing` and `changed-unexplained` block the fix whatever the result says, and a `weakened` answer on a
    `changed-explained` test blocks it too, listed in `testMismatch`;
K6  the first `break-it-change` of a finding keeps the test role's version as `reviewerTest`; a second never
    replaces it.

Bite-proof record: c1l10_wo2_audit_checks
"""
import copy
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import audits  # noqa: E402
import break_it  # noqa: E402
import decision_kinds  # noqa: E402
import engine_adapter  # noqa: E402
import engine_result_channel as ERC  # noqa: E402
import payload_contracts  # noqa: E402
import round_driver as RD  # noqa: E402
import test_round_driver as TRD  # noqa: E402

# The throwaway fixture repo's commits carry an inline identity; nothing is signed.
_ID = ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]
TEST_PATH = "tests/test_charge.py"
RUN = "python tests/test_charge.py"
ROLE_TEST = "def test_charge():\n    assert charge(2) == 2\n"
FIXED_TEST = "def test_charge():\n    import charge_mod\n    assert charge(2) == 2\n"
WEAKER_TEST = "def test_charge():\n    assert True\n"
WHY = "the first draft was missing an import"


@pytest.fixture(autouse=True)
def _pinned_git_config(monkeypatch, tmp_path):
    for name in ("home", "xdg-config"):
        (tmp_path / name).mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _git(repo, *args):
    done = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def _repo_with(tmp_path, committed):
    """A scratch repository whose HEAD commits `TEST_PATH` as `committed` (nothing when None); returns (root, head)."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "README.md").write_text("fixture\n")
    if committed is not None:
        (root / TEST_PATH).parent.mkdir(parents=True, exist_ok=True)
        (root / TEST_PATH).write_text(committed)
    _git(root, "add", "-A")
    _git(root, *_ID, "commit", "-q", "-m", "fix")
    return root, _git(root, "rev-parse", "HEAD")


def _block_text(content):
    return RD._break_it_block_text({"path": TEST_PATH, "run": RUN}, content)


def _finding(content=ROLE_TEST, reviewer_test=None, changed_why=None):
    """A finding carrying the break-it block `content`, with the run list of a test the build session changed
    (`changed_why`) when given."""
    finding = {"title": "Retry charges twice", "file": TEST_PATH, "line": 1, "severity": "Important",
               "taxonomy": break_it.TAXONOMY, "suggestion": _block_text(content)}
    if reviewer_test is not None:
        finding[RD.REVIEWER_TEST_FIELD] = reviewer_test
    if changed_why is not None:
        finding[break_it.RUNS_FIELD] = [{"test": TEST_PATH, "changedWhy": None},
                                        {"test": TEST_PATH, "changedWhy": changed_why}]
    return finding


def _facts(tmp_path, committed, finding, head=True):
    root, sha = _repo_with(tmp_path, committed)
    return RD._break_it_target_facts({}, {"repoRoot": str(root)}, finding, sha if head else None)


# --- K1: the one judge of the shape -----------------------------------------------------------------------------

def _checks(**answers):
    return TRD.audit_checks(**answers)


def _result(checks=True, ruling="discharged", **extra):
    out = {"id": "t0", "ruling": ruling, "reason": "the fix resolves it"}
    if checks is True:
        out["checks"] = _checks()
    elif checks is not None:
        out["checks"] = checks
    out.update(extra)
    return out


def _without(name):
    checks = _checks()
    del checks[name]
    return checks


def _with(name, **entry):
    checks = _checks()
    checks[name] = dict(checks[name], **entry)
    return checks


@pytest.mark.parametrize("checks", [
    pytest.param(None, id="absent"),
    pytest.param("yes", id="not-a-dict"),
    pytest.param([_checks()], id="a-list"),
    pytest.param(_without("right"), id="right-missing"),
    pytest.param(_without("brokeNothing"), id="brokeNothing-missing"),
    pytest.param(_without("testWouldFail"), id="testWouldFail-missing"),
    pytest.param(_with("right", answer="maybe"), id="answer-outside-yes-no"),
    pytest.param(_with("right", answer=True), id="answer-a-boolean"),
    pytest.param(_with("brokeNothing", answer="YES"), id="answer-wrong-case"),
    pytest.param(_with("testWouldFail", why="   "), id="why-blank"),
    pytest.param(_with("testWouldFail", why=None), id="why-absent"),
    pytest.param(_with("right", why=7), id="why-not-a-string"),
    pytest.param(dict(_checks(), right="yes"), id="entry-not-an-object"),
])
def test_k1_audit_checks_fault_names_every_malformed_checks(checks):
    # axis: E1 — every way `checks` fails to answer the three checks is a fault
    fault = audits.audit_checks_fault(_result(checks=checks))
    assert isinstance(fault, str) and "checks" in fault, fault


def test_k1_audit_checks_fault_is_none_for_three_answers_of_either_kind():
    assert audits.audit_checks_fault(_result()) is None
    assert audits.audit_checks_fault(_result(checks=_checks(right="no", brokeNothing="no"))) is None
    assert audits.audit_checks_fault("not a result") is not None


def test_k1_a_changed_explained_target_owes_a_usable_test_match_and_no_other_target_does():
    changed = {"breakIt": {"match": "changed-explained"}}
    for owed in (None, "weakened", {"answer": "matches"}, {"answer": "fine", "why": "x"},
                 {"answer": "matches", "why": " "}):
        fault = audits.audit_checks_fault(_result(testMatch=owed), changed)
        assert fault is not None and "testMatch" in fault, (owed, fault)
    good = {"answer": "matches", "why": "only added the import"}
    assert audits.audit_checks_fault(_result(testMatch=good), changed) is None
    # E5: where the committed test is the test role's own, a `testMatch` is ignored, whatever it holds
    for match in ("same", "missing", "changed-unexplained"):
        assert audits.audit_checks_fault(_result(testMatch="junk"), {"breakIt": {"match": match}}) is None
    assert audits.audit_checks_fault(_result(testMatch="junk"), {"title": "no test here"}) is None
    assert audits.audit_checks_fault(_result(testMatch="junk")) is None


def test_k1_the_payload_contract_predicate_calls_the_same_judge():
    contract, _ = payload_contracts.payload_contract(payload_contracts.P_AUDITS)
    assert "checks" in contract["required"] and "testMatch" in contract["optional"]
    assert "audit-checks" in [p["name"] for p in contract["predicates"]]
    assert payload_contracts.payload_fault(payload_contracts.P_AUDITS, _result(), "t0") is None
    missing = payload_contracts.payload_fault(payload_contracts.P_AUDITS, _result(checks=None), "t0")
    assert missing is not None and "checks" in missing
    shaped = payload_contracts.payload_fault(
        payload_contracts.P_AUDITS, _result(checks=_with("right", answer="maybe")), "t0")
    assert shaped == "audit result refused: %s" % audits.audit_checks_fault(
        _result(checks=_with("right", answer="maybe"))), shaped


def test_k1_the_submit_guard_refuses_a_result_missing_a_check_and_keeps_the_step_pending():
    # axis: E1 at submit — the refusal names the check; a resubmit with the check is accepted
    targets = [{"id": "t0"}]
    for checks in (None, _without("testWouldFail"), _with("right", answer="perhaps")):
        fault = RD.audit_results_fault({"results": [_result(checks=checks)]}, targets)
        assert fault is not None and "results[0]" in fault and "checks" in fault, fault
    assert RD.audit_results_fault({"results": [_result()]}, targets) is None
    # a not-discharged ruling owes the answers too
    assert RD.audit_results_fault({"results": [_result(ruling="not-discharged", checks=None)]}, targets)
    assert RD.audit_results_fault({"results": [_result(ruling="not-discharged", checks=_checks(right="no"))]},
                                  targets) is None


def test_k1_the_submit_guard_judges_the_test_match_against_the_target_the_result_answers():
    targets = [{"id": "t0", "breakIt": {"match": "changed-explained"}}, {"id": "t1"}]
    fault = RD.audit_results_fault({"results": [_result()]}, targets)
    assert fault is not None and "testMatch" in fault, fault
    ok = _result(testMatch={"answer": "matches", "why": "an import only"})
    assert RD.audit_results_fault({"results": [ok, dict(_result(), id="t1")]}, targets) is None


# --- K2: the fold ------------------------------------------------------------------------------------------------

def _fold(results, targets=None, **kw):
    targets = targets if targets is not None else [{"id": "t0", "title": "T", "file": "f.py", "line": 1}]
    return audits.apply_audit_results(targets, results, **kw)


def _only(outcome):
    (entry,) = outcome["audits"]
    return entry


def test_k2_three_yes_answers_discharge():
    outcome = _fold([_result()])
    assert outcome["discharged"] == ["t0"] and outcome["notDischarged"] == []
    assert outcome["malformed"] == [] and outcome["testMismatch"] == []
    assert _only(outcome)["ruling"] == "discharged" and "testMatch" not in _only(outcome)


@pytest.mark.parametrize("failing", list(audits.CHECK_NAMES))
@pytest.mark.parametrize("ruling", ["discharged", "discharged-but-new-issue"])
def test_k2_one_no_on_a_clearing_ruling_is_not_discharged_naming_the_check(failing, ruling):
    extra = {"newIssues": [{"title": "leak", "file": "f.py", "line": 2}]} if ruling != "discharged" else {}
    outcome = _fold([_result(ruling=ruling, checks=_checks(**{failing: "no"}), **extra)])
    entry = _only(outcome)
    assert outcome["notDischarged"] == ["t0"] and outcome["discharged"] == []
    assert entry["ruling"] == "not-discharged"
    assert entry["reason"] == "audit check failed: %s: checked: %s" % (failing, failing)
    assert outcome["malformed"] == []


def test_k2_a_not_discharged_ruling_may_carry_any_answers():
    outcome = _fold([_result(ruling="not-discharged", checks=_checks(right="no", brokeNothing="no"),
                             reason="still broken")])
    assert outcome["notDischarged"] == ["t0"] and outcome["malformed"] == []
    assert _only(outcome)["reason"] == "still broken"


@pytest.mark.parametrize("ruling", ["discharged", "discharged-but-new-issue", "not-discharged"])
@pytest.mark.parametrize("checks", [None, _without("brokeNothing"), _with("right", answer="maybe"),
                                    _with("testWouldFail", why="")])
def test_k2_a_result_missing_a_check_is_malformed_not_discharged_whatever_its_ruling(ruling, checks):
    # axis: E1 at the fold — the fold fails closed with the shared judge's reason
    extra = {"newIssues": [{"title": "leak"}]} if ruling == "discharged-but-new-issue" else {}
    result = _result(ruling=ruling, checks=checks, **extra)
    outcome = _fold([result])
    assert outcome["malformed"] == ["t0"] and outcome["notDischarged"] == ["t0"]
    assert outcome["discharged"] == []
    assert _only(outcome)["ruling"] == "not-discharged"
    assert _only(outcome)["reason"] == "audit refused: %s" % audits.audit_checks_fault(result)


# --- K3: the engine channel --------------------------------------------------------------------------------------

def test_k3_the_strict_ruling_schema_is_closed_and_valid():
    schema = ERC._review_root_schema("ruling")
    ERC.assert_strict_mode_valid(schema)
    # the ruling branch lists the contract's fields beside `resultKind`, each required in strict mode
    ruling = schema["properties"]["result"]
    assert ruling["properties"]["resultKind"]["enum"] == ["ruling"]
    assert "checks" in ruling["required"] and "testMatch" in ruling["required"]
    checks = ruling["properties"]["checks"]
    assert checks["type"] == "object" and checks["additionalProperties"] is False
    assert sorted(checks["required"]) == sorted(audits.CHECK_NAMES)
    for name in audits.CHECK_NAMES:
        entry = checks["properties"][name]
        assert entry["additionalProperties"] is False and entry["required"] == ["answer", "why"]
        assert entry["properties"]["answer"]["enum"] == ["yes", "no"]
        assert entry["properties"]["why"] == {"type": "string"}
    match = ruling["properties"]["testMatch"]
    assert match["type"] == ["object", "null"] and match["additionalProperties"] is False
    assert match["properties"]["answer"]["enum"] == ["matches", "weakened"]
    # no unclosed `object` anywhere in the ruling's schema
    for node in _walk(ruling["properties"]["checks"]) + _walk(match):
        if node.get("type") == "object" or (isinstance(node.get("type"), list) and "object" in node["type"]):
            assert node.get("additionalProperties") is False and node.get("properties"), node


def _walk(node):
    out = [node]
    for child in list((node.get("properties") or {}).values()) + ([node["items"]] if "items" in node else []):
        out.extend(_walk(child))
    return out


def test_k3_a_ruling_with_checks_and_test_match_survives_the_parser():
    # axis: E2 — `checks` is a required contract field, not an optional one; the scrub must still carry it
    obj = {"id": "t0", "ruling": "discharged", "reason": "the fix resolves it",
           "checks": _checks(testWouldFail="no"),
           "testMatch": {"answer": "weakened", "why": "the assertion was dropped"}}
    parsed = engine_adapter._parse_review_ruling_object(copy.deepcopy(obj), None)
    assert parsed["ok"] is True and parsed["resultKind"] == "ruling", parsed
    assert parsed["ruling"]["checks"] == obj["checks"]
    assert parsed["ruling"]["testMatch"] == obj["testMatch"]
    assert audits.audit_checks_fault(parsed["ruling"]) is None


def test_k3_a_ruling_without_checks_is_unreadable_at_the_parser():
    obj = {"id": "t0", "ruling": "discharged", "reason": "the fix resolves it"}
    assert engine_adapter._parse_review_ruling_object(obj, None) == {"ok": False, "reason": "unreadable"}


# --- K4: breakIt.match, one per value, on a temp git repo --------------------------------------------------------

def test_k4_same_when_the_committed_test_is_the_test_roles(tmp_path):
    facts = _facts(tmp_path, ROLE_TEST, _finding())
    assert facts == {"path": TEST_PATH, "reviewerTest": ROLE_TEST, "committedTest": ROLE_TEST,
                     "changedWhy": None, "match": "same"}


def test_k4_changed_explained_when_the_committed_test_is_the_build_sessions_explained_change(tmp_path):
    finding = _finding(content=FIXED_TEST, reviewer_test=ROLE_TEST, changed_why=WHY)
    facts = _facts(tmp_path, FIXED_TEST, finding)
    assert facts == {"path": TEST_PATH, "reviewerTest": ROLE_TEST, "committedTest": FIXED_TEST,
                     "changedWhy": WHY, "match": "changed-explained"}


def test_k4_changed_unexplained_when_the_change_carries_no_reason(tmp_path):
    finding = _finding(content=FIXED_TEST, reviewer_test=ROLE_TEST)
    facts = _facts(tmp_path, FIXED_TEST, finding)
    assert facts["match"] == "changed-unexplained" and facts["changedWhy"] is None


def test_k4_changed_unexplained_when_the_commit_is_not_the_change_the_session_explained(tmp_path):
    # the reason was given for FIXED_TEST, but the fixer committed something else
    finding = _finding(content=FIXED_TEST, reviewer_test=ROLE_TEST, changed_why=WHY)
    facts = _facts(tmp_path, WEAKER_TEST, finding)
    assert facts["match"] == "changed-unexplained" and facts["committedTest"] == WEAKER_TEST


def test_k4_a_recorded_change_with_no_kept_original_never_reads_same(tmp_path):
    # axis: a recorded change with no kept original reads changed-unexplained, never same, even when the commit equals the rewritten text
    finding = _finding(content=WEAKER_TEST, changed_why=WHY)
    root, sha = _repo_with(tmp_path, WEAKER_TEST)
    facts = RD._break_it_target_facts({}, {"repoRoot": str(root)}, finding, sha)
    assert facts["reviewerTest"] is None
    assert facts["match"] == "changed-unexplained"


def test_k4_changed_unexplained_when_a_fixer_edits_a_test_nobody_changed(tmp_path):
    facts = _facts(tmp_path, WEAKER_TEST, _finding())
    assert facts["match"] == "changed-unexplained"


def test_k4_missing_when_the_test_is_not_committed_at_the_head(tmp_path):
    facts = _facts(tmp_path, None, _finding())
    assert facts["match"] == "missing" and facts["committedTest"] is None


def test_k4_missing_when_git_cannot_be_read(tmp_path):
    # axis: E3 — no head, no repo root, a non-repository root: each fails closed
    root, sha = _repo_with(tmp_path, ROLE_TEST)
    finding = _finding()
    assert RD._break_it_target_facts({}, {"repoRoot": str(root)}, finding, None)["match"] == "missing"
    assert RD._break_it_target_facts({}, {}, finding, sha)["match"] == "missing"
    elsewhere = tmp_path / "not-a-repo"
    elsewhere.mkdir()
    assert RD._break_it_target_facts({}, {"repoRoot": str(elsewhere)}, finding, sha)["match"] == "missing"
    assert RD._break_it_target_facts({}, {"repoRoot": str(root)}, finding, "0" * 40)["match"] == "missing"


def test_k4_the_target_row_carries_breakIt_read_at_the_fix_fold_head(tmp_path):
    # the recorded fix commit holds the weakened test; HEAD then moves on to a commit restoring the role's test
    root, sha = _repo_with(tmp_path, WEAKER_TEST)
    (root / TEST_PATH).write_text(ROLE_TEST)
    _git(root, "add", "-A")
    _git(root, *_ID, "commit", "-q", "-m", "restore")
    assert _git(root, "rev-parse", "HEAD") != sha
    cfg = {"repoRoot": str(root), "fixerVendor": "claude", "vendors": ["claude", "codex"]}
    state = RD.new_state(cfg)
    state["round"] = 2
    state["rounds"] = {"1": {"fixFoldHead": sha}}
    state["fixBatch"] = [_finding()]
    (target,) = RD._audit_targets(state, cfg, {})
    assert target["breakIt"]["path"] == TEST_PATH
    assert target["breakIt"]["committedTest"] == WEAKER_TEST
    assert target["breakIt"]["match"] == "changed-unexplained"
    assert RD._audit_head(state, cfg) == sha
    # a finding that carries no test has no `breakIt`
    state["fixBatch"] = [{"title": "plain", "file": "f.py", "line": 1, "severity": "Important"}]
    (plain,) = RD._audit_targets(state, cfg, {})
    assert "breakIt" not in plain


# --- K5: the blocking test match ---------------------------------------------------------------------------------

def _target(match, **extra):
    return {"id": "t0", "title": "T", "file": "f.py", "line": 1,
            "breakIt": dict({"path": TEST_PATH, "reviewerTest": ROLE_TEST, "committedTest": FIXED_TEST,
                             "changedWhy": WHY, "match": match}, **extra)}


@pytest.mark.parametrize("match", ["missing", "changed-unexplained"])
@pytest.mark.parametrize("ruling", ["discharged", "discharged-but-new-issue", "not-discharged"])
def test_k5_a_missing_or_unexplained_test_blocks_whatever_the_result_says(match, ruling):
    # axis: the match test — a clean `discharged` with three `yes` answers still folds not-discharged
    extra = {"newIssues": [{"title": "leak"}]} if ruling == "discharged-but-new-issue" else {}
    outcome = _fold([_result(ruling=ruling, **extra)], [_target(match)])
    entry = _only(outcome)
    assert outcome["discharged"] == [] and outcome["notDischarged"] == ["t0"]
    assert outcome["testMismatch"] == ["t0"] and outcome["malformed"] == []
    assert entry["ruling"] == "not-discharged"
    assert entry["reason"] == ("break-it test %s: the committed test at %s is not the test role's version "
                               "(or the build session's explained change of it)" % (match, TEST_PATH))
    assert entry["testMatch"] == {"match": match, "answer": None, "blocking": True}


@pytest.mark.parametrize("match", ["missing", "changed-unexplained", "changed-explained"])
def test_k5_a_test_mismatch_keeps_the_new_issues_the_result_reported(match):
    # axis: the veto of the parent's discharge never drops the auditor's separate findings
    given = {"newIssues": [{"title": "leak", "file": "f.py", "line": 2}]}
    if match == "changed-explained":
        given["testMatch"] = {"answer": "weakened", "why": "the assertion no longer checks the charge"}
    outcome = _fold([_result(ruling="discharged-but-new-issue", **given)], [_target(match)])
    assert outcome["notDischarged"] == ["t0"] and outcome["testMismatch"] == ["t0"]
    assert [i["title"] for i in outcome["newIssues"]] == ["leak"]


def test_k5_a_blocked_test_is_blocked_even_when_the_result_omits_its_checks():
    outcome = _fold([_result(checks=None)], [_target("missing")])
    assert outcome["testMismatch"] == ["t0"] and outcome["malformed"] == []


def test_k5_a_weakened_explained_change_blocks_and_a_matching_one_discharges():
    weakened = _result(testMatch={"answer": "weakened", "why": "the assertion no longer checks the charge"})
    outcome = _fold([weakened], [_target("changed-explained")])
    entry = _only(outcome)
    assert outcome["discharged"] == [] and outcome["notDischarged"] == ["t0"]
    assert outcome["testMismatch"] == ["t0"] and outcome["malformed"] == []
    assert entry["ruling"] == "not-discharged"
    assert entry["reason"] == "break-it test weakened: the assertion no longer checks the charge"
    assert entry["testMatch"] == {"match": "changed-explained", "answer": "weakened", "blocking": True}

    matches = _result(testMatch={"answer": "matches", "why": "only the import was added"})
    outcome = _fold([matches], [_target("changed-explained")])
    assert outcome["discharged"] == ["t0"] and outcome["testMismatch"] == []
    assert _only(outcome)["testMatch"] == {"match": "changed-explained", "answer": "matches", "blocking": False}


def test_k5_a_changed_explained_target_with_no_usable_test_match_is_malformed():
    for given in ({}, {"testMatch": {"answer": "matches"}}, {"testMatch": "matches"}):
        outcome = _fold([_result(**given)], [_target("changed-explained")])
        assert outcome["malformed"] == ["t0"] and outcome["notDischarged"] == ["t0"], given
        assert outcome["testMismatch"] == []
        assert _only(outcome)["reason"].startswith("audit refused: `testMatch`"), _only(outcome)


def test_k5_a_test_match_is_ignored_where_the_committed_test_is_the_test_roles():
    # axis: E5 — `weakened` on a `same` target never blocks
    given = _result(testMatch={"answer": "weakened", "why": "an answer the target did not owe"})
    outcome = _fold([given], [_target("same")])
    assert outcome["discharged"] == ["t0"] and outcome["testMismatch"] == []
    assert _only(outcome)["testMatch"] == {"match": "same", "answer": None, "blocking": False}


def test_k5_an_unreadable_match_reads_as_missing():
    target = _target("same")
    target["breakIt"]["match"] = "something-else"
    outcome = _fold([_result()], [target])
    assert outcome["testMismatch"] == ["t0"] and outcome["discharged"] == []


def test_k5_the_driver_fold_records_the_mismatch_and_decides_it():
    cfg = {"repoRoot": "/nonexistent-review-project", "fixerVendor": "claude", "vendors": ["claude", "codex"]}
    state = RD.new_state(cfg)
    state["_verifyThen"] = RD.VERIFY_THEN_POST_AUDITS
    # a target seated on an auditor: a result for a target with none is ignored as silence
    state["_auditTargets"] = [dict(_target("changed-unexplained"), auditorVendor="codex",
                                   independence="independent")]
    RD._fold_audits(state, cfg, {"results": [_result()], "collectionManifest": {"t0": "codex"}})
    assert state["rounds"][str(state["round"])]["testMismatch"] == ["t0"]
    assert state["_auditOutcome"]["testMismatch"] == ["t0"]
    assert [d["kind"] for d in state["decisions"] if d["kind"] == "break-it-test-mismatch"] == [
        "break-it-test-mismatch"]
    assert "break-it-test-mismatch" in decision_kinds.DECISION_KINDS

# --- K6: the test role's version is kept ---------------------------------------------------------------------------

def _record(outcome="failed"):
    return {"path": TEST_PATH, "run": RUN, "outcome": outcome, "exitCode": 1, "head": "a" * 40, "output": ""}


def test_k6_the_first_change_keeps_the_test_roles_version_and_a_second_never_replaces_it():
    # axis: E4 — the second `break-it-change` rewrites the suggestion again and leaves `reviewerTest` alone
    copy_ = _finding()
    RD._rewrite_break_it_copy(copy_, _block_text(FIXED_TEST), _record(), WHY)
    assert copy_[RD.REVIEWER_TEST_FIELD] == ROLE_TEST
    assert break_it.carried_block(copy_)[0]["content"] == FIXED_TEST
    RD._rewrite_break_it_copy(copy_, _block_text(WEAKER_TEST), _record(), "a second correction")
    assert copy_[RD.REVIEWER_TEST_FIELD] == ROLE_TEST
    assert break_it.carried_block(copy_)[0]["content"] == WEAKER_TEST
    assert [r["changedWhy"] for r in copy_[break_it.RUNS_FIELD]] == [WHY, "a second correction"]


def test_k6_a_copy_that_already_holds_the_version_keeps_it():
    copy_ = _finding(reviewer_test="the test role's original")
    RD._rewrite_break_it_copy(copy_, _block_text(FIXED_TEST), _record(), WHY)
    assert copy_[RD.REVIEWER_TEST_FIELD] == "the test role's original"


# --- K4b: formatting and relocation read as the same test (finding v0, round 8) ---------------------------------

def _repo_with_base(tmp_path, files):
    """A scratch repository with a base commit and a head commit adding `files` ({path: text}); returns (root, base, head)."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "README.md").write_text("fixture\n")
    _git(root, "add", "-A")
    _git(root, *_ID, "commit", "-q", "-m", "base")
    base = _git(root, "rev-parse", "HEAD")
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    _git(root, "add", "-A")
    _git(root, *_ID, "commit", "-q", "-m", "fix")
    return root, base, _git(root, "rev-parse", "HEAD")


def _facts_with_base(root, base, head, finding):
    return RD._break_it_target_facts({}, {"repoRoot": str(root), "baseRef": base}, finding, head)


def test_k4b_a_formatter_only_change_reads_same(tmp_path):
    # axis: a formatter-only change to the reviewer's test is the same test, never changed-unexplained
    formatted = "def test_charge():\n    assert charge( 2 )==2\n"
    root, base, head = _repo_with_base(tmp_path, {TEST_PATH: formatted})
    facts = _facts_with_base(root, base, head, _finding())
    assert facts["match"] == "same"


def test_k4b_an_unchanged_test_moved_to_another_path_reads_same(tmp_path):
    # axis: a supported relocation of the unchanged test is the same test, never missing
    root, base, head = _repo_with_base(tmp_path, {"tests/test_moved.py": ROLE_TEST})
    facts = _facts_with_base(root, base, head, _finding())
    assert facts["match"] == "same"


def test_k4b_a_weakened_test_still_reads_changed_unexplained(tmp_path):
    root, base, head = _repo_with_base(tmp_path, {TEST_PATH: WEAKER_TEST})
    facts = _facts_with_base(root, base, head, _finding())
    assert facts["match"] == "changed-unexplained"
