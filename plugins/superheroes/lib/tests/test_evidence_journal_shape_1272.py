"""#1272 WO-4: runner journal shape guards for evidence binding."""
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import engine_adapter  # noqa: E402
import engine_dispatch  # noqa: E402
import review_findings_schema  # noqa: E402
import round_driver  # noqa: E402
import round_records  # noqa: E402
import sanitized_view  # noqa: E402
import test_round_driver_integration as TRI  # noqa: E402


def _run_dir_with_non_object_journal_line(tmp_path, order_path, monkeypatch):
    """Build a dispatch run dir, then corrupt the journal with a non-object JSON line."""
    run_dir = str(tmp_path / "journal-shape-run")
    journal_root = str(tmp_path / "dispatch-journal-root")
    os.makedirs(journal_root, exist_ok=True)
    monkeypatch.setenv(engine_dispatch.JOURNAL_ROOT_ENV, journal_root)
    repo_root = str(tmp_path / "journal-shape-repo")
    os.makedirs(repo_root, exist_ok=True)
    with open(os.path.join(repo_root, ".git"), "w", encoding="utf-8") as fh:
        fh.write("gitdir: /fake/worktree\n")
    view_path = str(tmp_path / "journal-shape-view")
    os.makedirs(view_path, exist_ok=True)
    view_meta = {"headSha": "abc123fake", "stripped": [], "path": view_path}
    with open(order_path, encoding="utf-8") as fh:
        base_prompt = fh.read()
    notice = sanitized_view.sanitized_view_notice(view_meta, mode="review")
    fed_prompt = (
        engine_dispatch.ANTIHIJACK_PREAMBLE + notice + base_prompt + "\n\n"
        + review_findings_schema.example_prompt_block("nonce-journal-shape") + "\n\n"
        + engine_adapter.REVIEW_RESULT_CONTRACT("findings")
    )
    findings_text = json.dumps({"findings": []})
    stdout = TRI._codex_event_stream(findings_text, action_items=1)
    ok, detail = engine_dispatch._open_review_run(
        run_dir, engine="codex", argv=[sys.executable, "-c", "pass"], cwd=repo_root,
        timeout=30, retry_timeout=30, prompt_path=order_path, view_path=view_path,
        view_meta=view_meta, fed_prompt=fed_prompt, order_id="journal-shape-order",
        progress_path=os.path.join(run_dir, "progress.jsonl"), repo_root=repo_root,
        echo_nonce="nonce-journal-shape", base_prompt=base_prompt,
    )
    assert ok, detail
    engine_dispatch._journal_append(run_dir, {
        "kind": "attempt-ended", "attempt": 1,
        "exit": 0, "timedOut": False, "refusal": None,
        "wallSeconds": 0.1, "stdoutBytes": len(stdout),
        "at": time.time(),
    })
    with open(os.path.join(run_dir, "attempt-1.stdout"), "wb") as fh:
        fh.write(stdout.encode("utf-8"))
    with open(os.path.join(run_dir, "attempt-1.stderr"), "wb") as fh:
        fh.write(b"")
    journal_path = engine_dispatch._journal_path(os.path.realpath(run_dir))
    with open(journal_path, "a", encoding="utf-8") as fh:
        fh.write("[]\n")
    return run_dir


def test_journal_line_not_an_object_refuses_evidence_binding(tmp_path, monkeypatch):
    """A journal line that is valid JSON but not an object is refused at both seams."""
    order_path = str(tmp_path / "journal-shape-order.txt")
    with open(order_path, "w", encoding="utf-8") as fh:
        fh.write("Review the change.\n")
    run_dir = _run_dir_with_non_object_journal_line(tmp_path, order_path, monkeypatch)
    record, err = engine_dispatch.run_execution_record(run_dir)
    assert record is None
    assert err == "internal-error"  # runner-side class; dispatch shell not narrowed here

    envelope = {"orderSha256": "0" * 64, "payload": {"findings": []}}
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir, exist_ok=True)
    assembled, refusal, extra = round_driver._assemble_dispatch_evidence(
        session_dir, envelope, run_dir)
    assert assembled is None
    assert refusal == "evidence-run-dir-unreadable"
    assert extra == {"detail": "internal-error"}


def _panel_cross_kind_fixture():
    finding = {
        "dimension": "d",
        "taxonomy": "t",
        "title": "x",
        "file": "f.py",
        "line": 1,
        "severity": "Important",
    }
    grouping = [{"group_id": "g", "member_ids": ["x"]}]
    payload = {"findings": [finding], "grouping": grouping}
    order_sha = "a" * 64
    envelope = {
        "phase": round_driver.P_PANEL,
        "orderSha256": order_sha,
        "payload": payload,
    }
    base_record = {
        "orderPromptSha256": order_sha,
        "source": "runner",
        "runnerNonce": "nonce-cross-kind",
        "recordDigest": "digest-cross-kind",
        "observation": TRI._execution_evidence()["observation"],
    }
    return envelope, payload, grouping, base_record


def test_assemble_dispatch_evidence_refuses_cross_kind_subject_disagreement(tmp_path):
    """T9: grouping digest on a panel envelope with findings refuses subject disagreement."""
    envelope, payload, grouping, base_record = _panel_cross_kind_fixture()
    record = dict(
        base_record,
        resultKind="grouping",
        resultDigest=round_records.payload_sha256(grouping),
    )
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir, exist_ok=True)
    real_record = engine_dispatch.run_execution_record

    def _patched(_run_dir):
        return record, None

    engine_dispatch.run_execution_record = _patched
    try:
        assembled, refusal, extra = round_driver._assemble_dispatch_evidence(
            session_dir, envelope, "fake-run-dir")
    finally:
        engine_dispatch.run_execution_record = real_record
    assert assembled is None
    assert refusal == "evidence-result-mismatch"
    assert extra.get("subjectDisagreement") is True

    findings_record = dict(
        base_record,
        resultKind="findings",
        resultDigest=round_records.payload_sha256(payload["findings"]),
    )

    def _findings_patched(_run_dir):
        return findings_record, None

    engine_dispatch.run_execution_record = _findings_patched
    try:
        assembled, refusal, extra = round_driver._assemble_dispatch_evidence(
            session_dir, envelope, "fake-run-dir")
    finally:
        engine_dispatch.run_execution_record = real_record
    assert assembled is not None
    assert refusal is None
    assert extra == {}
