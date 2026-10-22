#!/usr/bin/env python3
"""#2046 — the driver names a committed-but-unlanded fix, cross-checks a fixer's refusals against its
transcript, and offers one sanctioned correction for a wrong landed `refusals` list.

The durable-record path runs the REAL driver over the REAL adapters (the harness of
`test_round_driver_integration.py`); the hand-submit path runs the `_Cli` of
`test_head_diff_from_git_1966.py`. Transcripts are synthetic JSONL in the real shape: an assistant
`tool_use` row, then a user `tool_result` row with `is_error` true and the hook's refusal text.
"""
import json
import os
import shlex
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _path in (_HERE, _LIB):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import round_driver as RD  # noqa: E402
import round_records as RR  # noqa: E402
from session_checkout import make_checkout, seed_session_meta  # noqa: E402

import test_head_diff_from_git_1966 as hand  # noqa: E402
from test_round_driver_integration import (  # noqa: E402
    _blocking_finding, _bootstrap, _drive_to_phase, _fake_git, _fixture_repo, _land, _payload_for,
    _state,
)

SEAT = "fixer"
HEREDOC = "python3 - <<'EOF'\nprint(1)\nEOF"
ENTRY = {"command": HEREDOC, "refusedBy": "hook", "next": "wrote the file with the Write tool"}


def _git(repo, *args):
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", repo, *args],
        check=True, capture_output=True, text=True).stdout.strip()


def _commit(repo, name):
    with open(os.path.join(repo, name), "w", encoding="utf-8") as fh:
        fh.write("fix\n")
    _git(repo, "add", name)
    _git(repo, "commit", "-qm", name)
    return _git(repo, "rev-parse", "HEAD")


def _fixer_session(tmp_path, name="s"):
    """A durable-record session parked at dispatch-fixer, whose order was emitted at the repo's
    real HEAD. Returns (session_dir, gitdir, head_diff_path, repo, emission_head)."""
    repo = _fixture_repo(tmp_path, name)
    head = make_checkout(repo)
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name=name, head_sha=head, repoRoot=repo)
    seed_session_meta(session_dir, repo)
    _drive_to_phase(session_dir, gitdir, [_blocking_finding("unchecked index", 2)], head_path,
                    RD.P_FIXER)
    return session_dir, gitdir, head_path, repo, head


def _land_fixer(session_dir, head_path, refusals=None):
    state = _state(session_dir)
    pend = state["pending"]
    payload = _payload_for(session_dir, state, pend, SEAT, [], head_path)
    if refusals is not None:
        payload["refusals"] = refusals
    _land(session_dir, state, pend, SEAT, payload)
    return pend, payload


def _transcript(tmp_path, commands, name="fixer.jsonl"):
    rows = []
    for i, command in enumerate(commands):
        tid = "toolu_%d" % i
        rows.append({"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": tid, "name": "Bash", "input": {"command": command}}]}})
        rows.append({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": tid, "is_error": True,
             "content": "PreToolUse:Bash hook error: [guard]: heredocs are not allowed"}]}})
    path = tmp_path / name
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return str(path)


def _refusals_file(tmp_path, refusals):
    path = tmp_path / "refusals.json"
    path.write_text(json.dumps(refusals), encoding="utf-8")
    return str(path)


def _store_path(session_dir, pend):
    return RR.store_path(session_dir, pend["round"], pend["phase"], RR.storage_key(SEAT),
                         pend["attempt"])


def _landing_path(session_dir, pend):
    return RR.landing_path(session_dir, pend["round"], pend["phase"], RR.storage_key(SEAT),
                           pend["attempt"])


def _rows(session_dir, outcome, rd=RD):
    return [row for row in rd.read_journal(session_dir) if row.get("outcome") == outcome]


def _read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


# ---- A: a committed fix with no landing is never read as "nothing landed" ----------------------

def test_a1_record_result_names_the_commit_of_a_fixer_that_never_landed(tmp_path):
    session_dir, _gitdir, _head_path, repo, _head = _fixer_session(tmp_path)
    pend = _state(session_dir)["pending"]
    first = _commit(repo, "one.txt")
    second = _commit(repo, "two.txt")
    out = RD.cmd_record_result(session_dir, SEAT)
    assert out["ok"] is False and out["reason"] == "fixer-committed-unlanded"
    assert out["commits"] == [first, second]
    assert "re-dispatch the same fixer order" in out["detail"]
    assert not os.path.exists(_store_path(session_dir, pend))


def test_a2_sweep_and_advance_refuse_a_committed_unlanded_fixer(tmp_path):
    session_dir, gitdir, _head_path, repo, _head = _fixer_session(tmp_path)
    pend = _state(session_dir)["pending"]
    sha = _commit(repo, "one.txt")
    swept = RD.cmd_record_result(session_dir, sweep=True)
    assert swept["ok"] is False and swept["reason"] == "fixer-committed-unlanded"
    assert swept["commits"] == [sha]
    out = RD.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is False and out["reason"] == "fixer-committed-unlanded"
    assert out["commits"] == [sha]
    assert not os.path.exists(_store_path(session_dir, pend))


def test_a3_record_missing_refuses_a_fixer_that_committed(tmp_path):
    session_dir, _gitdir, _head_path, repo, _head = _fixer_session(tmp_path)
    pend = _state(session_dir)["pending"]
    sha = _commit(repo, "one.txt")
    out = RD.cmd_record_missing(session_dir, SEAT, pend["attempt"], "forfeit")
    assert out["ok"] is False and out["reason"] == "fixer-committed-unlanded"
    assert out["commits"] == [sha]
    assert not os.path.exists(_store_path(session_dir, pend))


def test_a_no_new_commits_keeps_todays_refusals_and_record_missing_succeeds(tmp_path):
    session_dir, gitdir, _head_path, _repo, _head = _fixer_session(tmp_path)
    pend = _state(session_dir)["pending"]
    out = RD.cmd_record_result(session_dir, SEAT)
    assert out["ok"] is False and out["reason"] == "landing-missing"
    out = RD.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is False and out["reason"] == "incomplete-roster"
    out = RD.cmd_record_missing(session_dir, SEAT, pend["attempt"], "forfeit")
    assert out["ok"] is True, out


def test_a_unknown_emission_head_keeps_the_old_refusal_never_a_pass(tmp_path, monkeypatch):
    session_dir, _gitdir, _head_path, repo, _head = _fixer_session(tmp_path)
    _commit(repo, "one.txt")
    monkeypatch.setattr(RD, "_anchor_cited_head", lambda *args: None)
    out = RD.cmd_record_result(session_dir, SEAT)
    assert out["ok"] is False and out["reason"] == "landing-missing"


# ---- B: a fixer result that leaves out a refusal the driver can see is never a clean record ----

def test_b1_record_result_refuses_an_unreported_refusal_then_records_when_listed(tmp_path):
    session_dir, _gitdir, head_path, _repo, _head = _fixer_session(tmp_path)
    transcript = _transcript(tmp_path, [HEREDOC])
    pend, _payload = _land_fixer(session_dir, head_path, refusals=[])
    out = RD.cmd_record_result(session_dir, SEAT, fixer_transcript=transcript)
    assert out["ok"] is False and out["reason"] == "fixer-refusals-unreported"
    assert [entry["command"] for entry in out["unreported"]] == [HEREDOC]
    assert "correct-fixer-refusals --session-dir" in out["correction"]
    assert RD.FIXER_REFUSALS_FILE_PLACEHOLDER in out["correction"]
    assert not os.path.exists(_store_path(session_dir, pend))
    _land_fixer(session_dir, head_path, refusals=[ENTRY])
    out = RD.cmd_record_result(session_dir, SEAT, fixer_transcript=transcript)
    assert out["ok"] is True, out
    assert [row["refusalCheck"] for row in _rows(session_dir, "recorded")
            if row.get("seat") == SEAT] == ["checked"]


def test_b_unreadable_transcript_refuses_and_never_degrades_to_unobserved(tmp_path):
    session_dir, _gitdir, head_path, _repo, _head = _fixer_session(tmp_path)
    pend, _payload = _land_fixer(session_dir, head_path, refusals=[])
    out = RD.cmd_record_result(session_dir, SEAT,
                               fixer_transcript=str(tmp_path / "missing.jsonl"))
    assert out["ok"] is False and out["reason"] == "fixer-transcript-unreadable"
    assert out["detail"] == "transcript-missing"
    assert not os.path.exists(_store_path(session_dir, pend))


@pytest.mark.parametrize("via", ["record-result", "sweep", "advance"])
def test_b_no_transcript_journals_unobserved(tmp_path, via):
    session_dir, gitdir, head_path, _repo, _head = _fixer_session(tmp_path)
    _land_fixer(session_dir, head_path, refusals=[])
    if via == "record-result":
        out = RD.cmd_record_result(session_dir, SEAT)
    elif via == "sweep":
        out = RD.cmd_record_result(session_dir, sweep=True)
    else:
        out = RD.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is True, out
    assert [row["refusalCheck"] for row in _rows(session_dir, "recorded")
            if row.get("seat") == SEAT] == ["unobserved"]


def test_b2_sweep_refuses_an_unreported_refusal_then_records_when_listed(tmp_path):
    session_dir, _gitdir, head_path, _repo, _head = _fixer_session(tmp_path)
    transcript = _transcript(tmp_path, [HEREDOC])
    pend, _payload = _land_fixer(session_dir, head_path, refusals=[])
    out = RD.cmd_record_result(session_dir, sweep=True, fixer_transcript=transcript)
    assert out["ok"] is False and out["reason"] == "fixer-refusals-unreported"
    assert not os.path.exists(_store_path(session_dir, pend))
    _land_fixer(session_dir, head_path, refusals=[ENTRY])
    out = RD.cmd_record_result(session_dir, sweep=True, fixer_transcript=transcript)
    assert out["ok"] is True, out
    assert [row["refusalCheck"] for row in _rows(session_dir, "recorded")
            if row.get("seat") == SEAT] == ["checked"]


def test_b3_advance_refuses_an_unreported_refusal_then_folds_when_listed(tmp_path):
    session_dir, gitdir, head_path, _repo, _head = _fixer_session(tmp_path)
    transcript = _transcript(tmp_path, [HEREDOC])
    pend, _payload = _land_fixer(session_dir, head_path, refusals=[])
    out = RD.cmd_advance(session_dir, git=_fake_git(gitdir), fixer_transcript=transcript)
    assert out["ok"] is False and out["reason"] == "fixer-refusals-unreported"
    assert not os.path.exists(_store_path(session_dir, pend))
    _land_fixer(session_dir, head_path, refusals=[ENTRY])
    out = RD.cmd_advance(session_dir, git=_fake_git(gitdir), fixer_transcript=transcript)
    assert out["ok"] is True and out["folded"]["phase"] == RD.P_FIXER, out
    assert [row["refusalCheck"] for row in _rows(session_dir, "recorded")
            if row.get("seat") == SEAT] == ["checked"]


def test_b4_hand_submit_refuses_an_unreported_refusal_then_accepts_when_listed(tmp_path, monkeypatch):
    cli = hand._Cli(tmp_path, monkeypatch)
    transcript = _transcript(tmp_path, [HEREDOC])
    cli.supply = lambda c: {"refusals": []}
    n = cli.to_fixer()
    artifact = cli.respond(n["phase"], n["payload"], n["round"])

    def submit(art, path):
        return hand.RD.cmd_submit(cli.d, n["phase"], n["attempt"], n["expectedStateHash"], art,
                                  fixer_transcript=path)

    out = submit(artifact, str(tmp_path / "missing.jsonl"))
    assert out["ok"] is False and out["reason"] == "fixer-transcript-unreadable"
    out = submit(artifact, transcript)
    assert out["ok"] is False and out["reason"] == "fixer-refusals-unreported"
    assert [entry["command"] for entry in out["unreported"]] == [HEREDOC]
    assert "correction" not in out and "resubmit" in out["detail"]
    ok, state = hand.RD.load_state(cli.d)
    assert ok and state["pending"]["phase"] == RD.P_FIXER
    out = submit(dict(artifact, refusals=[ENTRY]), transcript)
    assert out["ok"] is True, out
    assert [row["refusalCheck"] for row in _rows(cli.d, "accepted", hand.RD)
            if row.get("phase") == RD.P_FIXER] == ["checked"]


def test_b4_hand_submit_without_a_transcript_journals_unobserved(tmp_path, monkeypatch):
    cli = hand._Cli(tmp_path, monkeypatch)
    cli.supply = lambda c: {"refusals": []}
    out = cli.submit(cli.to_fixer())
    assert out["ok"] is True, out
    assert [row["refusalCheck"] for row in _rows(cli.d, "accepted", hand.RD)
            if row.get("phase") == RD.P_FIXER] == ["unobserved"]


# ---- C: a sanctioned correction for a wrong landed fixer payload -------------------------------

def test_c_correction_from_the_session_repo_fixes_the_landing_and_the_session_resumes(tmp_path):
    session_dir, gitdir, head_path, _repo, _head = _fixer_session(tmp_path)
    transcript = _transcript(tmp_path, [HEREDOC])
    pend, payload = _land_fixer(session_dir, head_path, refusals=[])
    out = RD.cmd_record_result(session_dir, SEAT, fixer_transcript=transcript)
    assert out["reason"] == "fixer-refusals-unreported"
    before = RR.read_json(_landing_path(session_dir, pend))[0]

    out = RD.cmd_correct_fixer_refusals(session_dir, _refusals_file(tmp_path, [ENTRY]),
                                        fixer_transcript=transcript)
    assert out["ok"] is True, out
    assert out["landingPath"] == _landing_path(session_dir, pend)
    assert "record-result" in out["next"] and "--supersede" not in out["next"]
    assert "--fixer-transcript" in out["next"]

    after = RR.read_json(out["landingPath"])[0]
    assert after["payload"]["refusals"] == [ENTRY]
    assert {k: v for k, v in after["payload"].items() if k != "refusals"} == {
        k: v for k, v in payload.items() if k != "refusals"}
    assert {k: v for k, v in after.items() if k not in ("payload", "payloadSha256", "envelopeSha256")} == {
        k: v for k, v in before.items() if k not in ("payload", "payloadSha256", "envelopeSha256")}
    assert after["payloadSha256"] == RR.payload_sha256(after["payload"])
    if after["schema"] == RR.SEAT_RESULT_SCHEMA_V2:
        assert after["envelopeSha256"] == RR.envelope_sha256(after["payload"],
                                                             after["executionEvidence"])
    (row,) = _rows(session_dir, "fixer-refusals-corrected")
    assert row["beforeSha256"] == RR.payload_sha256(before["payload"])
    assert row["afterSha256"] == RR.payload_sha256(after["payload"])

    out = RD.cmd_record_result(session_dir, SEAT, fixer_transcript=transcript)
    assert out["ok"] is True, out
    out = RD.cmd_advance(session_dir, git=_fake_git(gitdir), fixer_transcript=transcript)
    assert out["ok"] is True and out["folded"]["phase"] == RD.P_FIXER, out


def test_c_correction_names_the_supersede_form_when_a_record_is_already_stored(tmp_path):
    session_dir, _gitdir, head_path, _repo, _head = _fixer_session(tmp_path)
    pend, _payload = _land_fixer(session_dir, head_path, refusals=[])
    assert RD.cmd_record_result(session_dir, SEAT)["ok"] is True
    token = RR.envelope_cas_token(RR.read_json(_store_path(session_dir, pend))[0])
    out = RD.cmd_correct_fixer_refusals(session_dir, _refusals_file(tmp_path, [ENTRY]))
    assert out["ok"] is True, out
    words = shlex.split(out["next"])
    assert "--supersede" in words
    assert words[words.index("--expect-sha256") + 1] == token
    out = RD.cmd_record_result(session_dir, SEAT, supersede=True, expect_sha256=token)
    assert out["ok"] is True, out
    stored = RR.read_json(_store_path(session_dir, pend))[0]
    assert stored["payload"]["refusals"] == [ENTRY]


def test_c_correction_from_another_repo_refuses_and_writes_nothing(tmp_path, monkeypatch):
    session_dir, _gitdir, head_path, _repo, _head = _fixer_session(tmp_path)
    pend, _payload = _land_fixer(session_dir, head_path, refusals=[])
    landing = _landing_path(session_dir, pend)
    before = _read_bytes(landing)
    other = str(tmp_path / "other-repo")
    make_checkout(other)
    monkeypatch.chdir(other)
    out = RD.cmd_correct_fixer_refusals(session_dir, _refusals_file(tmp_path, [ENTRY]))
    assert out["ok"] is False and out["reason"] == "correction-outside-session-repo"
    assert os.path.realpath(other) in out["detail"]
    assert _read_bytes(landing) == before
    assert _rows(session_dir, "fixer-refusals-corrected") == []


def test_c_correction_refuses_when_the_session_records_no_repo(tmp_path):
    session_dir, _gitdir, head_path, _repo, _head = _fixer_session(tmp_path)
    _land_fixer(session_dir, head_path, refusals=[])
    meta_path = os.path.join(session_dir, RR.META_FILE)
    meta = RR.read_json(meta_path)[0]
    del meta["repoRoot"]
    RR.atomic_write_json(meta_path, meta)
    out = RD.cmd_correct_fixer_refusals(session_dir, _refusals_file(tmp_path, [ENTRY]))
    assert out["ok"] is False and out["reason"] == "correction-session-repo-unknown"


@pytest.mark.parametrize("content", [[{"command": "c", "refusedBy": "denied", "next": "n"}],
                                     "not a list", "not json at all"])
def test_c_invalid_refusals_file_refuses_and_writes_nothing(tmp_path, content):
    session_dir, _gitdir, head_path, _repo, _head = _fixer_session(tmp_path)
    pend, _payload = _land_fixer(session_dir, head_path, refusals=[])
    landing = _landing_path(session_dir, pend)
    before = _read_bytes(landing)
    path = tmp_path / "bad.json"
    path.write_text(content if content == "not json at all" else json.dumps(content),
                    encoding="utf-8")
    out = RD.cmd_correct_fixer_refusals(session_dir, str(path))
    assert out["ok"] is False and out["reason"] == "correction-refusals-invalid"
    assert _read_bytes(landing) == before


def test_c_correction_that_still_leaves_out_an_observed_refusal_refuses(tmp_path):
    session_dir, _gitdir, head_path, _repo, _head = _fixer_session(tmp_path)
    pend, _payload = _land_fixer(session_dir, head_path, refusals=[])
    landing = _landing_path(session_dir, pend)
    before = _read_bytes(landing)
    transcript = _transcript(tmp_path, [HEREDOC])
    out = RD.cmd_correct_fixer_refusals(session_dir, _refusals_file(tmp_path, []),
                                        fixer_transcript=transcript)
    assert out["ok"] is False and out["reason"] == "fixer-refusals-unreported"
    assert _read_bytes(landing) == before


def test_c_correction_without_a_landing_refuses_landing_missing(tmp_path):
    session_dir, _gitdir, _head_path, _repo, _head = _fixer_session(tmp_path)
    out = RD.cmd_correct_fixer_refusals(session_dir, _refusals_file(tmp_path, [ENTRY]))
    assert out["ok"] is False and out["reason"] == "landing-missing"


def test_c_correction_outside_the_fixer_phase_refuses(tmp_path):
    repo = _fixture_repo(tmp_path, "p")
    session_dir, _gitdir, _head_path = _bootstrap(tmp_path, name="p", repoRoot=repo)
    seed_session_meta(session_dir, repo)
    out = RD.cmd_correct_fixer_refusals(session_dir, _refusals_file(tmp_path, [ENTRY]))
    assert out["ok"] is False and out["reason"] == "correction-not-fixer-phase"


def test_c_correction_rewrites_a_bare_payload_landing_as_json(tmp_path):
    session_dir, _gitdir, head_path, _repo, _head = _fixer_session(tmp_path)
    state = _state(session_dir)
    pend = state["pending"]
    payload = _payload_for(session_dir, state, pend, SEAT, [], head_path)
    payload["refusals"] = []
    bare = RR.bare_payload_path(session_dir, pend["round"], pend["phase"], RR.storage_key(SEAT),
                                pend["attempt"])
    RR.atomic_write_json(bare, payload)
    out = RD.cmd_correct_fixer_refusals(session_dir, _refusals_file(tmp_path, [ENTRY]))
    assert out["ok"] is True, out
    assert out["landingPath"] == bare
    assert RR.read_json(bare)[0] == dict(payload, refusals=[ENTRY])
