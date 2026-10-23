"""The panel reads the host model from the session's own transcript when the start event omits it (#2110).

Every compose in this file runs on the `--live-vendors` path: no vendor CLI, no probe, no network.
Transcripts are real JSONL written in `tmp_path`, in the shape Claude Code records.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/wo_2110_host_model_transcript.md"""
import importlib.util
import io
import json
import os
import shlex
import subprocess
import sys
import time

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
_HOOK_PATH = os.path.join(os.path.dirname(_LIB), "hooks", "session_start.py")

import host_model as HM  # noqa: E402
import launch_ledger as ll  # noqa: E402
import receipt_disclosures as RDS  # noqa: E402
import seat_map as SM  # noqa: E402
import test_launcher as TL  # noqa: E402

BLOCK = 64 * 1024


def _assistant(model, sidechain=False, **extra):
    obj = {"type": "assistant", "isSidechain": sidechain, "sessionId": "s-2110",
           "timestamp": "2026-10-23T00:00:00.000Z", "message": {"model": model, "role": "assistant"}}
    obj.update(extra)
    return json.dumps(obj) + "\n"


def _write(path, *lines):
    path.write_text("".join(lines), encoding="utf-8")
    return str(path)


def _compose(capsys, host_args):
    rc = SM.main(["x", "compose", "--live-vendors", "claude,codex,cursor",
                  "--implementation-engine", "cursor", "--pr-number", "2110", *host_args])
    assert rc == 0
    return json.loads(capsys.readouterr().out)


def _unknown(receipt):
    return [d for d in receipt["degradations"] if d["constraint"] == "host-model-unknown"]


def _claude_ineligible(receipt):
    return RDS.reviewer_ineligible(host_family=RDS.host_family(receipt))("claude")


# --- compose ------------------------------------------------------------------------------------


def test_no_model_in_the_start_event_reads_the_session_transcript(capsys, tmp_path):
    # axis: the DoD's no-model test — the transcript fallback in resolve keeps the Claude seat
    # (bite-proof G1, see wo_2110_host_model_transcript)
    transcript = _write(tmp_path / "t.jsonl", _assistant("claude-opus-5-5"))
    receipt = _compose(capsys, ["--host-model", "", "--session-transcript", transcript,
                                "--session-transcript-from", "0"])
    assert not _unknown(receipt)
    assert receipt["hostFamily"] == "anthropic"
    assert _claude_ineligible(receipt) is False


def test_no_record_anywhere_still_reads_unknown(capsys, tmp_path):
    # axis: E1 — with no start-event model and no transcript the host reads unknown
    for extra in ([], ["--session-transcript", "", "--session-transcript-from", ""],
                  ["--session-transcript", str(tmp_path / "absent.jsonl"),
                   "--session-transcript-from", "0"]):
        receipt = _compose(capsys, ["--host-model", "", *extra])
        assert len(_unknown(receipt)) == 1
        assert receipt["hostFamily"] is None
        assert _claude_ineligible(receipt) is True


def test_the_start_event_model_wins_over_the_transcript(capsys, tmp_path):
    # axis: the start event's model is the first record; the transcript never overrides it
    transcript = _write(tmp_path / "t.jsonl", _assistant("claude-opus-5-5"))
    receipt = _compose(capsys, ["--host-model", "gpt-5.6-sol", "--session-transcript", transcript,
                                "--session-transcript-from", "0"])
    assert receipt["hostFamily"] == "openai"
    assert not _unknown(receipt)


def test_a_model_recorded_before_this_start_never_stands_in(capsys, tmp_path):
    # axis: B1 — history before the start offset is not the live model (bite-proof G2)
    path = tmp_path / "t.jsonl"
    transcript = _write(path, _assistant("gpt-5.6-sol"))
    start = str(os.path.getsize(transcript))
    args = ["--host-model", "", "--session-transcript", transcript, "--session-transcript-from", start]
    stale = _compose(capsys, args)
    assert len(_unknown(stale)) == 1
    assert stale["hostFamily"] is None
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(_assistant("claude-opus-5-5"))
    fresh = _compose(capsys, args)
    assert fresh["hostFamily"] == "anthropic"
    assert not _unknown(fresh)


# --- from_transcript ----------------------------------------------------------------------------


def test_from_transcript_picks_the_last_main_chain_assistant_model(tmp_path):
    # axis: sidechain, synthetic, non-assistant and malformed lines never stand in (bite-proof G3)
    path = tmp_path / "t.jsonl"
    path.write_bytes(b"".join(line.encode() for line in (
        _assistant("claude-haiku-5-5"),
        _assistant("gpt-5.6-sol", sidechain=True),
        json.dumps({"type": "user", "message": {"model": "gpt-5.6-sol"}}) + "\n",
        "{not json\n")) + b"\xff\xfe\n" + b"".join(line.encode() for line in (
        json.dumps({"type": "assistant", "message": "claude-x"}) + "\n",
        json.dumps({"type": "assistant", "isSidechain": False}) + "\n",
        _assistant("<synthetic>"),
        _assistant("claude-opus-5-5"),
        _assistant("gpt-5.6-sol", sidechain=True),
        _assistant("<synthetic>"))))
    assert HM.from_transcript(str(path), "0") == "claude-opus-5-5"


def test_from_transcript_only_sidechain_synthetic_or_foreign_lines_gives_empty(tmp_path):
    # axis: E5 — nothing qualifying means no model
    transcript = _write(
        tmp_path / "t.jsonl",
        _assistant("gpt-5.6-sol", sidechain=True),
        _assistant("<synthetic>"),
        json.dumps({"type": "user", "message": {"model": "gpt-5.6-sol"}}) + "\n",
    )
    assert HM.from_transcript(transcript, "0") == ""


def test_from_transcript_reads_a_final_line_without_a_newline(tmp_path):
    # axis: a trailing line with no newline is still considered
    transcript = _write(tmp_path / "t.jsonl", _assistant("gpt-5.6-sol"),
                        _assistant("claude-opus-5-5").rstrip("\n"))
    assert HM.from_transcript(transcript, "0") == "claude-opus-5-5"


def test_from_transcript_ignores_a_partial_line_at_the_start_boundary(tmp_path):
    # axis: a region that does not begin at a line start drops its first, partial line
    first = _assistant("claude-opus-5-5")
    transcript = _write(tmp_path / "t.jsonl", first)
    assert HM.from_transcript(transcript, "0") == "claude-opus-5-5"
    assert HM.from_transcript(transcript, "5") == ""
    assert HM.from_transcript(transcript, str(len(first.encode()))) == ""
    both = _write(tmp_path / "u.jsonl", first, _assistant("gpt-5.6-sol"))
    assert HM.from_transcript(both, "5") == "gpt-5.6-sol"
    assert HM.from_transcript(both, str(len(first.encode()))) == "gpt-5.6-sol"


@pytest.mark.parametrize("start", ["", "-1", "abc", "1.5", " 0", "0 ", "٣", "+1", None, 0])
def test_from_transcript_refuses_a_start_that_is_not_all_ascii_digits(tmp_path, monkeypatch, start):
    # axis: E3 — a malformed start means no read at all
    transcript = _write(tmp_path / "t.jsonl", _assistant("claude-opus-5-5"))
    opened = []
    real_open = open
    monkeypatch.setattr("builtins.open", lambda *a, **k: opened.append(a) or real_open(*a, **k))
    assert HM.from_transcript(transcript, start) == ""
    assert opened == []


def test_from_transcript_start_past_end_missing_file_and_directory_give_empty(tmp_path):
    # axis: E3 start past EOF; E4 missing / unreadable / directory — never raises
    transcript = _write(tmp_path / "t.jsonl", _assistant("claude-opus-5-5"))
    size = os.path.getsize(transcript)
    assert HM.from_transcript(transcript, str(size + 1)) == ""
    assert HM.from_transcript(str(tmp_path / "absent.jsonl"), "0") == ""
    assert HM.from_transcript(str(tmp_path), "0") == ""
    assert HM.from_transcript("", "0") == ""
    assert HM.from_transcript(None, "0") == ""


def test_from_transcript_reads_a_transcript_larger_than_one_block(tmp_path):
    # axis: the backward block read resolves the model past the first block
    filler = _assistant("gpt-5.6-sol", sidechain=True)
    qualifying = _assistant("claude-opus-5-5")
    body = filler * ((BLOCK * 3) // len(filler) + 1)
    far = _write(tmp_path / "far.jsonl", qualifying, body)
    assert os.path.getsize(far) > 2 * BLOCK
    assert HM.from_transcript(far, "0") == "claude-opus-5-5"
    near = _write(tmp_path / "near.jsonl", body, qualifying, filler)
    assert HM.from_transcript(near, "0") == "claude-opus-5-5"


def test_from_transcript_reads_a_line_that_straddles_a_block_boundary(tmp_path):
    # axis: a line split across two backward blocks is rejoined before it is parsed
    qualifying = _assistant("claude-opus-5-5", padding="p" * 200).encode()
    prefix = _assistant("gpt-5.6-sol", sidechain=True).encode() * 40
    tail_len = BLOCK - len(qualifying) // 2
    tail = json.dumps({"type": "assistant", "isSidechain": True, "pad": ""}).encode()
    tail = json.dumps({"type": "assistant", "isSidechain": True,
                       "pad": "x" * (tail_len - len(tail) - 1)}).encode() + b"\n"
    assert len(tail) == tail_len
    data = prefix + qualifying + tail
    boundary = len(data) - BLOCK
    assert len(prefix) < boundary < len(prefix) + len(qualifying)
    path = tmp_path / "straddle.jsonl"
    path.write_bytes(data)
    assert HM.from_transcript(str(path), "0") == "claude-opus-5-5"
    assert HM.from_transcript(str(path), str(len(prefix))) == "claude-opus-5-5"


# --- resolve / payload helpers ------------------------------------------------------------------


def test_resolve_reports_where_the_model_came_from(tmp_path):
    # axis: resolve — the start event wins, then the transcript, else none
    transcript = _write(tmp_path / "t.jsonl", _assistant("claude-opus-5-5"))
    assert HM.resolve("gpt-5.6-sol", transcript, "0") == ("gpt-5.6-sol", "start-event")
    assert HM.resolve("", transcript, "0") == ("claude-opus-5-5", "transcript")
    assert HM.resolve("bad model; rm", transcript, "0") == ("claude-opus-5-5", "transcript")
    assert HM.resolve("", "", "") == ("", "none")
    assert HM.resolve("", transcript, str(os.path.getsize(transcript))) == ("", "none")


def test_shape_ok_and_from_payload():
    # axis: the shape check moved from the hook keeps its exact behaviour
    assert HM.shape_ok("  claude-opus-5[1m] ") == "claude-opus-5[1m]"
    for bad in ("", "a b", "x;y", "a" * 129, 7, None, {"id": "x"}):
        assert HM.shape_ok(bad) == ""
    assert HM.from_payload({"model": "claude-opus-5"}) == "claude-opus-5"
    assert HM.from_payload({"model": {"id": "claude-opus-5"}}) == "claude-opus-5"
    assert HM.from_payload({"model": {"id": 1}}) == ""
    assert HM.from_payload({}) == ""
    assert HM.from_payload(None) == ""


def test_transcript_from_payload_bounds_the_path(tmp_path):
    # axis: E2 — a relative, over-long or control-character path is never exported
    existing = _write(tmp_path / "t.jsonl", _assistant("claude-opus-5-5"))
    assert HM.transcript_from_payload({"transcript_path": existing}) == (
        existing, str(os.path.getsize(existing)))
    fresh = str(tmp_path / "fresh.jsonl")
    assert HM.transcript_from_payload({"transcript_path": fresh}) == (fresh, "0")
    long_path = "/" + "a" * 4096
    for bad in ("rel/t.jsonl", long_path, "/tmp/a\nb", "/tmp/a\rb", "/tmp/a\x00b", 5, None, ""):
        assert HM.transcript_from_payload({"transcript_path": bad}) == ("", "")
    assert HM.transcript_from_payload({}) == ("", "")
    assert HM.transcript_from_payload(None) == ("", "")


# --- the hook -----------------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "isolated-config"))
    home = tmp_path / "isolated-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    for name in ("CODEX_HOME", "CLAUDE_CODE_REMOTE", "SUPERHEROES_REVIEWER_PASS"):
        monkeypatch.delenv(name, raising=False)


def _start(monkeypatch, env_file, payload):
    spec = importlib.util.spec_from_file_location("session_start_2110_%d" % id(payload), _HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setenv("CLAUDE_ENV_FILE", str(env_file))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(dict({"source": "startup", "cwd": "/tmp"},
                                                                  **payload))))
    assert mod.main() == 0


def _sourced(env_file):
    script = ". %s; printf '%%s\\n%%s\\n%%s' \"$SUPERHEROES_HOST_MODEL\" " \
             "\"$SUPERHEROES_SESSION_TRANSCRIPT\" \"$SUPERHEROES_SESSION_TRANSCRIPT_FROM\"" \
             % shlex.quote(str(env_file))
    out = subprocess.run(["/bin/sh", "-c", script], capture_output=True, text=True, check=True).stdout
    return out.split("\n")


def test_hook_exports_the_transcript_path_and_start_offset(tmp_path, monkeypatch, capsys):
    # axis: the hook exports three lines, in order, and never reads the transcript for a model
    transcript = _write(tmp_path / "t.jsonl", _assistant("gpt-5.6-sol"))
    env_file = tmp_path / "env.sh"
    env_file.write_text("", encoding="utf-8")
    _start(monkeypatch, env_file, {"transcript_path": transcript})
    assert env_file.read_text(encoding="utf-8").splitlines() == [
        "export SUPERHEROES_HOST_MODEL=''",
        "export SUPERHEROES_SESSION_TRANSCRIPT=%s" % shlex.quote(transcript),
        "export SUPERHEROES_SESSION_TRANSCRIPT_FROM=%d" % os.path.getsize(transcript),
    ]
    assert "Host model: unknown" in capsys.readouterr().out
    assert _sourced(env_file) == ["", transcript, str(os.path.getsize(transcript))]


def test_hook_exports_empty_transcript_lines_for_a_missing_or_relative_path(tmp_path, monkeypatch):
    # axis: E2 — an absent or non-absolute transcript_path is exported as ''
    for payload in ({}, {"transcript_path": "rel/t.jsonl"}, {"transcript_path": 7}):
        env_file = tmp_path / ("env-%d.sh" % id(payload))
        _start(monkeypatch, env_file, payload)
        assert env_file.read_text(encoding="utf-8").splitlines()[1:] == [
            "export SUPERHEROES_SESSION_TRANSCRIPT=''",
            "export SUPERHEROES_SESSION_TRANSCRIPT_FROM=''",
        ]


def test_hook_exports_start_zero_for_a_transcript_not_written_yet(tmp_path, monkeypatch):
    # axis: the fresh-startup case — the file does not exist yet, so the session starts at offset 0
    fresh = str(tmp_path / "fresh.jsonl")
    env_file = tmp_path / "env.sh"
    _start(monkeypatch, env_file, {"transcript_path": fresh})
    assert env_file.read_text(encoding="utf-8").splitlines()[1:] == [
        "export SUPERHEROES_SESSION_TRANSCRIPT=%s" % shlex.quote(fresh),
        "export SUPERHEROES_SESSION_TRANSCRIPT_FROM=0",
    ]


def test_a_later_start_replaces_the_earlier_starts_values_when_sourced(tmp_path, monkeypatch):
    # axis: the stale-reset intent, extended — the last start's three exports win when sourced
    first = _write(tmp_path / "first.jsonl", _assistant("gpt-5.6-sol"))
    env_file = tmp_path / "env.sh"
    _start(monkeypatch, env_file, {"model": "claude-opus-5", "transcript_path": first})
    assert _sourced(env_file) == ["claude-opus-5", first, str(os.path.getsize(first))]
    _start(monkeypatch, env_file, {})
    assert _sourced(env_file) == ["", "", ""]
    second = _write(tmp_path / "second.jsonl", _assistant("claude-opus-5-5"), _assistant("x-1"))
    _start(monkeypatch, env_file, {"transcript_path": second})
    assert _sourced(env_file) == ["", second, str(os.path.getsize(second))]


# --- the launcher -------------------------------------------------------------------------------


def test_spawn_attempt_drops_the_session_variables_from_the_child(tmp_path, monkeypatch):
    # axis: E6 — a parent's host model and transcript never reach a spawned child (bite-proof G4)
    L = TL.L
    repo = TL._init_repo(tmp_path / "repo")
    ledger_root = TL._ledger_env(tmp_path, monkeypatch)
    launch_id = "launch-2110-session-vars"
    ll.reserve(repo, {
        "event": "reserved", "launchId": launch_id, "ts": time.time(), "schema": ll.SCHEMA,
        "batchId": "batch-2110", "repoId": ll.repo_identity(repo), "issue": 2110,
        "surfaces": ["plugins/superheroes/lib"], "premise": {}, "preflight": {}, "argv": [],
        "doctrineDigest": "abc", "model": "test",
    })
    captured = {}

    def capture_spawn(argv, repo_root, out_fh, err_fh, child_env):
        captured.update(child_env)

        class _Proc:
            pid = 424248

        out_fh.close()
        err_fh.close()
        return _Proc()

    log_dir = str(tmp_path / "logs")
    os.makedirs(log_dir)
    parent_env = {ll.LEDGER_ROOT_ENV: ledger_root}
    parent_env.update({name: "parent-value" for name in HM.SESSION_ENV_VARS})
    result = L._spawn_attempt(
        repo, launch_id, 1, ["claude", "-p", "test"],
        os.path.join(log_dir, "out.log"), os.path.join(log_dir, "err.log"), 900000,
        env=parent_env, spawn_fn=capture_spawn, cwd=TL._spawn_cwd(tmp_path),
    )
    assert result["ok"] is True
    assert len(HM.SESSION_ENV_VARS) == 3
    for name in HM.SESSION_ENV_VARS:
        assert name not in captured
