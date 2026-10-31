"""An engine panel seat keeps the read list the runner graded, not the copy the build session landed.

`record-result --evidence-run-dir` on a round-1 panel seat binds the landed `readParts` to the list in the runner's own
graded result for that run: a different landed list is refused `evidence-read-parts-mismatch`, a landing with no list
takes the runner's, and a runner result with no list counts as `[]`. A native seat (no run dir) and every other phase are
left alone. The record's reviewer row then shows the runner's list.
"""
import json
import os

import pytest

import review_record_session as rs

import test_round_commit_seams as seams
from test_round_commit_seams import adapters  # noqa: F401  fixture: stands in for the round adapters
from test_review_record_session import CODEX, Fake, Session, extras, put_envelope

RD, RR, ED = seams.RD, seams.RR, seams.ED

RUNNER = [{"file": "src/a.py", "lines": [[3, 9], [20, 24]]}]
OTHER = [{"file": "src/other.py", "lines": [[1, 2]]}]
SEAT = "code-reviewer"


def _runner_writes(monkeypatch, parts):
    """Make the shared run-dir builder write a native review result whose findings branch carries `parts`."""

    def write(run_dir, repo_root, *, findings=None):
        td = seams._dispatch_test_helpers()
        rel = seams._ensure_investigated_repo_path(repo_root)
        branch = td._native_review_branch("findings", findings=[] if findings is None else findings,
                                          investigated=[rel], readParts=parts)
        with open(ED._native_result_path(run_dir, 1), "w", encoding="utf-8") as fh:
            json.dump({"result": branch}, fh, separators=(",", ":"))
            fh.write("\n")

    monkeypatch.setattr(seams, "_write_native_review_result", write)


def _landed(tmp_path, monkeypatch, runner_parts, payload, name):
    """A round-1 panel seat landed with `payload`, and a run dir whose graded result carries `runner_parts`."""
    _runner_writes(monkeypatch, runner_parts)
    d = seams._session_with_anchor_head(tmp_path, name=name)
    pend = seams._pending(d)
    assert pend["phase"] == RD.P_PANEL
    path, env, before = seams._dispatch_observed_land(d, SEAT, payload=payload)
    order_path = RR.order_prompt_path(d, pend["round"], pend["phase"], RR.storage_key(SEAT),
                                      pend["attempt"])
    run_dir = seams._execution_run_dir(tmp_path, order_path, name=name + "-run")
    return d, run_dir, path, env, before


def _stored(out):
    stored, err = RR.read_json(out["storePath"])
    assert err is None
    return stored


def _row_from_store(tmp_path, stored):
    """The reviewer row `review_record_session` builds for the seat from its stored payload."""
    session = Session(tmp_path).seat(SEAT).save()
    put_envelope(session, SEAT, {"vendor": "codex", "model": CODEX, "payload": stored["payload"]})
    rows = {v["name"]: v for v in rs.account_from_session(session, extras(), Fake().readers())["reviewers"]}
    return rows[SEAT + " (round 1)"]


def test_a_landed_list_that_differs_from_the_runners_is_refused(tmp_path, adapters, monkeypatch):
    # axis: the panel seat's read list must equal the list in the runner's graded result; a different landed list refuses
    d, run_dir, path, _env, before = _landed(
        tmp_path, monkeypatch, RUNNER, {"findings": [], "readParts": OTHER}, "c2-differs")
    out = RD.cmd_record_result(d, SEAT, evidence_run_dir=run_dir)
    assert out["ok"] is False
    assert out["reason"] == RD.EVIDENCE_READ_PARTS_MISMATCH_REFUSAL == "evidence-read-parts-mismatch"
    assert out["landedReadPartsSha256"] == RR.payload_sha256(OTHER)
    assert out["runnerReadPartsSha256"] == RR.payload_sha256(RUNNER)
    assert seams._read_bytes(path) == before


def test_a_landing_with_no_list_takes_the_runners_and_the_row_shows_it(tmp_path, adapters, monkeypatch):
    # axis: a landing that names no list is recorded with the runner's list, and the record's reviewer row shows it
    d, run_dir, path, _env, _before = _landed(
        tmp_path, monkeypatch, RUNNER, {"findings": []}, "c2-adopt")
    out = RD.cmd_record_result(d, SEAT, evidence_run_dir=run_dir)
    assert out["ok"], out
    stored = _stored(out)
    assert stored["payload"]["readParts"] == RUNNER
    assert stored["payloadSha256"] == RR.payload_sha256(stored["payload"])
    assert stored["envelopeSha256"] == RR.envelope_sha256(stored["payload"], stored["executionEvidence"])
    assert _row_from_store(tmp_path, stored)["readParts"] == RUNNER
    landing, err = RR.read_json(path)
    assert err is None and landing["payload"]["readParts"] == RUNNER  # the stamped landing agrees with the store


def test_equal_lists_are_accepted_unchanged(tmp_path, adapters, monkeypatch):
    # axis: a landed list equal to the runner's is accepted and kept as it landed
    payload = {"findings": [], "readParts": RUNNER}
    d, run_dir, _path, _env, _before = _landed(tmp_path, monkeypatch, RUNNER, payload, "c2-equal")
    out = RD.cmd_record_result(d, SEAT, evidence_run_dir=run_dir)
    assert out["ok"], out
    stored = _stored(out)
    assert stored["payload"] == payload
    assert stored["payloadSha256"] == RR.payload_sha256(payload)
    assert _row_from_store(tmp_path, stored)["readParts"] == RUNNER


def test_a_runner_with_no_list_accepts_a_landed_empty_list(tmp_path, adapters, monkeypatch):
    # axis: a runner result carrying no list counts as [], so a landed [] equals it
    d, run_dir, _path, _env, _before = _landed(
        tmp_path, monkeypatch, None, {"findings": [], "readParts": []}, "c2-none-empty")
    out = RD.cmd_record_result(d, SEAT, evidence_run_dir=run_dir)
    assert out["ok"], out
    assert _stored(out)["payload"]["readParts"] == []


def test_a_runner_with_no_list_refuses_a_landed_non_empty_list(tmp_path, adapters, monkeypatch):
    # axis: a runner result carrying no list counts as [], so a landed non-empty list differs from it
    d, run_dir, path, _env, before = _landed(
        tmp_path, monkeypatch, None, {"findings": [], "readParts": OTHER}, "c2-none-nonempty")
    out = RD.cmd_record_result(d, SEAT, evidence_run_dir=run_dir)
    assert out["ok"] is False
    assert out["reason"] == "evidence-read-parts-mismatch"
    assert out["runnerReadPartsSha256"] == RR.payload_sha256([])
    assert seams._read_bytes(path) == before


def test_a_runner_with_no_list_and_a_landing_with_none_records_an_empty_list(tmp_path, adapters, monkeypatch):
    # axis: no list on either side records [] — the reviewer returned no list, so it read nothing
    d, run_dir, _path, _env, _before = _landed(
        tmp_path, monkeypatch, None, {"findings": []}, "c2-none-none")
    out = RD.cmd_record_result(d, SEAT, evidence_run_dir=run_dir)
    assert out["ok"], out
    stored = _stored(out)
    assert stored["payload"]["readParts"] == []
    assert _row_from_store(tmp_path, stored)["readParts"] == []


def test_run_execution_record_carries_the_runners_list_on_a_review_run(tmp_path, adapters, monkeypatch):
    # axis: the runner's record of a review run holds the readParts of its admitted result, and no key when it had none
    _d, run_dir, _path, _env, _before = _landed(
        tmp_path, monkeypatch, RUNNER, {"findings": []}, "c2-carry")
    record, err = ED.run_execution_record(run_dir)
    assert err is None
    assert record["readParts"] == RUNNER
    _d2, run_dir2, _p2, _e2, _b2 = _landed(
        tmp_path, monkeypatch, None, {"findings": []}, "c2-carry-none")
    record2, err2 = ED.run_execution_record(run_dir2)
    assert err2 is None
    assert "readParts" not in record2


def test_a_native_seat_with_no_run_dir_keeps_its_landed_list(tmp_path, adapters):
    # axis: a seat recorded without --evidence-run-dir is not bound to a runner list
    d = seams._session(tmp_path, name="c2-native")
    payload = {"findings": [], "confidence": "high", "seat": SEAT,
               "verificationReceipt": {"ran": True}, "readParts": OTHER}
    out = seams._land_and_record(d, SEAT, payload=payload)
    assert _stored(out)["payload"]["readParts"] == OTHER


def test_another_phase_is_not_bound_to_the_runners_list(tmp_path, adapters, monkeypatch):
    # axis: only the panel phase binds the list; the same landing and run under another phase assemble untouched
    _runner_writes(monkeypatch, RUNNER)
    d = seams._session_with_anchor_head(tmp_path, name="c2-phase")
    pend = seams._pending(d)
    _path, env, _before = seams._dispatch_observed_land(
        d, SEAT, payload={"findings": [], "readParts": OTHER})
    order_path = RR.order_prompt_path(d, pend["round"], pend["phase"], RR.storage_key(SEAT),
                                      pend["attempt"])
    run_dir = seams._execution_run_dir(tmp_path, order_path, name="c2-phase-run")
    assembled, reason, _extra, _src = RD._assemble_dispatch_evidence(
        d, env, run_dir, "abc123fake", RD.P_VERIFIERS)
    assert reason is None
    assert assembled["payload"]["readParts"] == OTHER
