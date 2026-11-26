"""Tests for issue 2659: a missing evidence field or an unreadable record reads as unknown, never clean.

Four readers, each with a clean answer that needs the evidence field it rests on to be present and
readable: the cloud check's start record (`unattributed`), the loop gate's round artifacts (`findings`,
`resolutions`, each row's `action`), the panel tally's final receipt context, and the by-release
silent-reviewer measure (`silenceWatchdogEnds`). An absent or wrong-typed field routes into that
reader's existing unknown or fail-closed result. Every test deletes or breaks ONE field of a healthy
fixture, and each group pins its healthy twin so the refusals are not vacuous.
"""
import copy
import datetime
import importlib.util
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
for _path in (_HERE, _LIB):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import cloud_check as CC  # noqa: E402
import cloud_pass  # noqa: E402
import review_measures as RM  # noqa: E402
from test_cloud_check import _judge, _pair, _start_env, ENV_ID, NONCE, _confirm  # noqa: E402
from test_cloud_check_start_parts_2612 import HOOK_PART, UNREAD_SENTENCE  # noqa: E402


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LS = _load(os.path.join(_LIB, "loop_state.py"), "loop_state_2659")
PT = _load(os.path.join(_LIB, "panel_tally.py"), "panel_tally_2659")


# --- A1: the cloud check's start record ------------------------------------------------------

def _start_env_without(key):
    env = _start_env()
    record = json.loads(env[cloud_pass.START_COPY_ENV])
    del record[key]
    env[cloud_pass.START_COPY_ENV] = json.dumps(record)
    return env


def _report_under(cloud, start_env):
    env = dict({cloud_pass.ENVIRONMENT_ENV: ENV_ID}, **dict.fromkeys(CC.IDENTITY_VARIABLES, "x"), **start_env)
    return CC.report(env=env, cwd=cloud.cwd, root=cloud.root, nonce=NONCE, confirm_fn=_confirm(),
                     identity_fn=lambda cwd: {"author": True, "committer": True})


def test_a_start_record_with_no_unattributed_key_fails_the_start_part_as_unread(tmp_path):
    local, cloud = _pair(tmp_path)
    env = _start_env_without("unattributed")
    assert HOOK_PART in json.loads(env[cloud_pass.START_COPY_ENV])["parts"]
    # edge A1.a: key absent -> the record is not whole
    assert CC._start_parts(env) is None
    result = _judge(local, _report_under(cloud, env))
    assert result["failedParts"] == ["start"] and result["results"]["startPartsMatch"] is False
    assert UNREAD_SENTENCE in result["message"]


def test_the_same_start_record_with_an_empty_unattributed_list_still_reads(tmp_path):
    local, cloud = _pair(tmp_path)
    env = _start_env()
    assert json.loads(env[cloud_pass.START_COPY_ENV])["unattributed"] == []
    # edge A1.e: present and empty -> healthy
    assert CC._start_parts(env) is not None
    result = _judge(local, _report_under(cloud, env))
    assert result["action"] == "passed" and result["results"]["startPartsMatch"] is True


@pytest.mark.parametrize("value", ["x", {}, None, [5], ["a.py"]], ids=repr)
def test_a_start_record_with_a_malformed_or_non_empty_unattributed_is_still_not_read(value):
    # edges A1.b, A1.c, A1.d: unchanged
    env = _start_env()
    record = json.loads(env[cloud_pass.START_COPY_ENV])
    record["unattributed"] = value
    env[cloud_pass.START_COPY_ENV] = json.dumps(record)
    assert CC._start_parts(env) is None


# --- A2: the loop gate's round artifacts -----------------------------------------------------

def _gate(capsys, *args):
    assert LS.main(["loop_state.py", "--round", "1", *args]) == 0
    return json.loads(capsys.readouterr().out)


def _write(tmp_path, name, data):
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def _reviews_naming(out, name):
    assert out["action"] == "review" and out["mandatory"] is True, out
    assert name in out["reason"], out


@pytest.mark.parametrize("data", [{}, {"other": []}, {"findings": {}}, {"findings": None}, {"findings": "x"}, "x", 7, None],
                         ids=repr)
def test_a_fix_batch_with_no_findings_list_reviews_and_names_the_file(tmp_path, capsys, data):
    # edges A2.a, A2.b
    path = _write(tmp_path, "fix-batch.json", data)
    _reviews_naming(_gate(capsys, "--fix-batch", path), "fix-batch.json")


@pytest.mark.parametrize("data", [{}, {"other": []}, {"findings": {}}, {"findings": None}, "x"], ids=repr)
def test_a_compiled_file_with_no_findings_list_reviews_and_names_the_file(tmp_path, capsys, data):
    # edges A2.a, A2.b for the revise loops' artifact
    path = _write(tmp_path, "compiled.json", data)
    _reviews_naming(_gate(capsys, "--compiled", path), "compiled.json")


@pytest.mark.parametrize("entry", ["x", 7, None, ["Important"]], ids=repr)
def test_a_finding_that_is_not_an_object_reviews_and_names_the_file(tmp_path, capsys, entry):
    # edge A2.c, in both finding artifacts and both shapes
    _reviews_naming(_gate(capsys, "--fix-batch", _write(tmp_path, "fix-batch.json", [entry])), "fix-batch.json")
    _reviews_naming(_gate(capsys, "--fix-batch", _write(tmp_path, "fix-batch2.json", {"findings": [entry]})),
                    "fix-batch2.json")
    _reviews_naming(_gate(capsys, "--compiled", _write(tmp_path, "compiled.json", {"findings": [entry]})),
                    "compiled.json")


@pytest.mark.parametrize("data", [{}, {"other": []}, {"resolutions": {}}, {"resolutions": None}, {"resolutions": "x"}, [], "x"],
                         ids=repr)
def test_resolutions_with_no_resolutions_list_reviews_and_names_the_file(tmp_path, capsys, data):
    # edges A2.d, A2.e
    path = _write(tmp_path, "resolutions.json", data)
    _reviews_naming(_gate(capsys, "--resolutions", path), "resolutions.json")


@pytest.mark.parametrize("row", [{}, {"severity": "Critical"}, {"action": 5}, {"action": None}, "skip", None],
                         ids=repr)
def test_a_resolution_row_with_no_string_action_reviews_beside_a_clean_fix_batch(tmp_path, capsys, row):
    # edges A2.f, A2.g: the row could have been a blocking skip; with an empty fix batch it must not exit clean
    fix = _write(tmp_path, "fix-batch.json", [])
    path = _write(tmp_path, "resolutions.json", {"resolutions": [{"action": "fix", "severity": "Minor"}, row]})
    out = _gate(capsys, "--fix-batch", fix, "--resolutions", path)
    _reviews_naming(out, "resolutions.json")


def test_unreadable_artifacts_still_review(tmp_path, capsys):
    # edge A2.h: unchanged
    out = _gate(capsys, "--fix-batch", str(tmp_path / "missing-fix-batch.json"))
    _reviews_naming(out, "missing-fix-batch.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{ not json", encoding="utf-8")
    assert _gate(capsys, "--resolutions", str(bad))["action"] == "review"


def test_whole_artifacts_read_as_before(tmp_path, capsys):
    # edge A2.i: healthy
    for name, data in (("a.json", {"findings": []}), ("b.json", [])):
        assert _gate(capsys, "--fix-batch", _write(tmp_path, name, data))["action"] == "exit_clean"
    assert _gate(capsys, "--compiled", _write(tmp_path, "c.json", {"findings": []}))["action"] == "exit_clean"
    assert _gate(capsys, "--resolutions", _write(tmp_path, "r.json", {"resolutions": []}))["action"] == "exit_clean"
    row = {"resolutions": [{"action": "fix", "severity": "Important"}]}
    assert _gate(capsys, "--resolutions", _write(tmp_path, "r2.json", row))["action"] == "exit_clean"
    assert _gate(capsys, "--fix-batch", _write(tmp_path, "d.json", {"findings": [{"severity": "Important"}]}))[
        "action"] == "review"


# --- A3: the panel tally's final receipt ------------------------------------------------------

def _receipt(**over):
    receipt = {"artifact": "run-1:round-3",
               "chain": [{"step": "citation", "evidence": "reviewed source citations"},
                         {"step": "reachability", "evidence": "validated changed call path"},
                         {"step": "missing-check", "evidence": "searched for uncovered FRs"},
                         {"step": "tooling", "evidence": "pytest smoke passed"}],
               "coverageDecisionIds": ["RCD-1"]}
    receipt.update(over)
    return receipt


def _context():
    return {"artifact": "run-1:round-3", "coverageDecisionIds": ["RCD-1"]}


def _final(receipt, context, **extra):
    result = {"status": "run", "findings": [], "confidence": "high", "verificationReceipt": receipt}
    result.update(extra)
    return PT.round_gate_from_dimension_results({"code": result}, ["code"], final_confirmation=True,
                                                receipt_context=context)


def test_the_fully_valid_receipt_with_its_context_is_clean_and_high():
    # edge A3.f: healthy
    gate, conf, _missing = _final(_receipt(), _context())
    assert (gate, conf) == ("clean", "high")


def test_a_context_that_lists_no_decision_ids_requires_none():
    gate, conf, _missing = _final(_receipt(coverageDecisionIds=[]), {"artifact": "run-1:round-3", "coverageDecisionIds": []})
    assert (gate, conf) == ("clean", "high")


def test_an_external_review_seat_with_no_receipt_and_no_context_is_still_clean():
    # edge A3.g: that path never calls the receipt check
    gate, conf, _missing = _final(None, None, externalReview="codex")
    assert (gate, conf) == ("clean", "high")


def _without(key):
    context = _context()
    del context[key]
    return context


@pytest.mark.parametrize("context", [None, [], "x", {}, _without("artifact"), _without("coverageDecisionIds"),
                                     dict(_context(), artifact=""), dict(_context(), artifact=5),
                                     dict(_context(), coverageDecisionIds=None)],
                         ids=["none", "list", "str", "empty", "no-artifact", "no-ids", "blank-artifact",
                              "int-artifact", "null-ids"])
def test_a_final_confirmation_with_no_whole_receipt_context_cannot_certify(context):
    # edges A3.a, A3.b, A3.c
    assert _final(_receipt(), copy.deepcopy(context)) == ("cannot-certify", "low", [])


@pytest.mark.parametrize("ids", [[{}], [None], [5], [""], "RCD-1", {"RCD-1": 1}], ids=repr)
def test_context_decision_ids_that_are_not_non_empty_strings_cannot_certify_and_never_raise(ids):
    # edge A3.d
    assert _final(_receipt(), dict(_context(), coverageDecisionIds=ids)) == ("cannot-certify", "low", [])


@pytest.mark.parametrize("ids", [[{}], [None], [5], [""], "RCD-1", None], ids=repr)
def test_receipt_decision_ids_that_are_not_non_empty_strings_cannot_certify(ids):
    # edge A3.e
    assert _final(_receipt(coverageDecisionIds=ids), _context()) == ("cannot-certify", "low", [])


# --- A4: the by-release silent-reviewer voids -------------------------------------------------

_AT = "2026-11-06T10:00:00Z"
_SEC = "security-reviewer (round 1)"
_FROM, _UNTIL = datetime.date(2026, 10, 28), datetime.date(2026, 11, 11)
_RELEASES = [{"version": "0.49.0", "since": "2026-10-20"}, {"version": "0.50.0", "since": "2026-11-05T12:00:00Z"}]


def _record(status="not-reviewed", ran="not-run", **extra):
    rec = {"pr": 1, "sessionId": "s1", "writtenAt": _AT, "status": status, "rounds": {"count": 1},
           "reviewers": [{"name": _SEC, "ran": ran, "commit": "c1"}], "findings": []}
    rec.update(extra)
    return rec


def _voids(record):
    row = RM.compute({"records": [record], "releases": _RELEASES, "mergedPrs": [1]}, _FROM, _UNTIL)
    assert RM.problems(row) == []
    return row["measures"]["silentReviewerVoids"]["byRelease"]["0.50.0"]


def test_absent_ends_beside_a_row_that_did_not_run_in_a_session_that_did_not_clear_read_unresolved():
    # edge A4.a
    rec = _record()
    assert "silenceWatchdogEnds" not in rec
    assert _voids(rec) == {"voided": 0, "unresolved": 1, "sessions": 1}


def test_absent_ends_in_a_cleared_session_are_clear():
    # edge A4.b
    assert _voids(_record(status="reviewed")) == {"voided": 0, "unresolved": 0, "sessions": 1}


def test_absent_ends_with_no_row_that_did_not_run_are_clear():
    # edge A4.c
    assert _voids(_record(ran="engine-record")) == {"voided": 0, "unresolved": 0, "sessions": 1}


def test_present_empty_ends_keep_the_existing_logic():
    # edge A4.d: present `[]` is "none", so a row that did not run with no silent seat is clear
    assert _voids(_record(silenceWatchdogEnds=[])) == {"voided": 0, "unresolved": 0, "sessions": 1}


def test_present_malformed_ends_read_unmeasured_and_an_unrecorded_status_too():
    # edges A4.e, A4.f
    assert _voids(_record(silenceWatchdogEnds="x")) == RM.UNMEASURED
    assert _voids(_record(silenceWatchdogEnds=[{"seat": " "}])) == RM.UNMEASURED
    assert _voids(_record(status="pending")) == RM.UNMEASURED
    assert _voids(_record(status=None)) == RM.UNMEASURED
