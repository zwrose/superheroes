"""#1467 item 1: a native result file rewritten before the deadline is admitted.

Invariant under test: the completion stamp is the digest of the latest result-file content
observed stable at or before the attempt's monotonic deadline (stamped after the read);
content first observed after the deadline never replaces an existing stamp.
"""
import importlib.util
import json
import os
import subprocess
import time
import types

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load():
    path = os.environ.get("ENGINE_DISPATCH_NEUTRAL_PATH") or os.path.join(
        _HERE, "..", "engine_dispatch.py")
    spec = importlib.util.spec_from_file_location("engine_dispatch", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ED = _load()

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "dispatch-e2e",
    "GIT_AUTHOR_EMAIL": "e2e@test.local",
    "GIT_COMMITTER_NAME": "dispatch-e2e",
    "GIT_COMMITTER_EMAIL": "e2e@test.local",
}


@pytest.fixture(autouse=True)
def _pin_temp_and_journal(tmp_path, monkeypatch):
    base = str(tmp_path / "temp-base")
    os.makedirs(base, exist_ok=True)
    monkeypatch.setattr(ED.tempfile, "gettempdir", lambda: base)
    journal_root = str(tmp_path / "dispatch-journal-root")
    os.makedirs(journal_root, exist_ok=True)
    monkeypatch.setenv(ED.JOURNAL_ROOT_ENV, journal_root)
    yield


def _git(cwd, *args):
    merged = dict(os.environ)
    merged.update(_GIT_ENV)
    return subprocess.run(
        ["git", "-C", cwd, *args], capture_output=True, text=True, check=True, env=merged,
    )


def _linked_worktree(tmp_path):
    main = str(tmp_path / "main")
    os.makedirs(main, exist_ok=True)
    _git(main, "init", "-q")
    with open(os.path.join(main, "README.md"), "w", encoding="utf-8") as fh:
        fh.write("hello\n")
    _git(main, "add", "README.md")
    _git(main, "commit", "-qm", "init")
    wt = str(tmp_path / "wt")
    _git(main, "worktree", "add", "-q", wt)
    return wt


def _payload(report):
    return json.dumps({
        "ok": True, "signal": "ok", "report": report,
        "evidence": {"testFailed": False, "testPassed": True},
    }, separators=(",", ":"))


def _seat():
    return {"vendor": "cursor", "model": "composer-2.5", "effort": None, "role": "implementer"}


def _install_rewriting_engine(tmp_path, monkeypatch, steps, *, on_term=None):
    """Fake cursor-agent: run steps [("write", text) | ("sleep", secs)] in order.

    on_term, when given, is a payload written on SIGTERM before exiting.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    exe = bin_dir / "cursor-agent"
    body = '''#!/usr/bin/env python3
import signal
import sys
import time

_STEPS = %(steps)r
_ON_TERM = %(on_term)r
_PREFIX = %(prefix)r

_data = sys.stdin.read()
_path = None
for _line in _data.split("\\n"):
    if _line.startswith(_PREFIX):
        _rest = _line[len(_PREFIX):].strip()
        _path = _rest if _rest else None

def _term(signum, frame):
    if _ON_TERM is not None and _path:
        with open(_path, "w", encoding="utf-8") as fh:
            fh.write(_ON_TERM)
    sys.exit(0)

signal.signal(signal.SIGTERM, _term)

with open("work-product.txt", "w", encoding="utf-8") as fh:
    fh.write("dirty the tree\\n")

for _kind, _arg in _STEPS:
    if _kind == "write":
        with open(_path, "w", encoding="utf-8") as fh:
            fh.write(_arg)
    else:
        time.sleep(_arg)
sys.exit(0)
''' % {
        "steps": steps,
        "on_term": on_term,
        "prefix": ED.engine_result_channel.RESULT_FILE_LINE_PREFIX,
    }
    exe.write_text(body, encoding="utf-8")
    exe.chmod(0o755)
    monkeypatch.setenv(
        "PATH", str(bin_dir) + os.pathsep + "/usr/bin" + os.pathsep + "/bin")


def _run(tmp_path, monkeypatch, steps, *, cap, on_term=None, wait=120):
    wt = _linked_worktree(tmp_path)
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Do the work.\n", encoding="utf-8")
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    _install_rewriting_engine(tmp_path, monkeypatch, steps, on_term=on_term)
    deadline = time.monotonic() + wait
    last = None
    while time.monotonic() < deadline:
        last = ED.dispatch_write(
            seat=_seat(), prompt_path=str(prompt), cwd=wt, run_dir=run_dir,
            order_id="rewrite-order", timeout=cap, retry_timeout=cap,
        )
        if last.get("terminal") or last.get("reason") != "running":
            return last, run_dir
        time.sleep(0.2)
    pytest.fail("no terminal result; last=%s" % (last,))


def _admission_detail(run_dir):
    records, _ = ED._journal_read(run_dir)
    grade = ED._grade_write_attempt(run_dir, ED._journal_state(records), 1)
    return {k: grade.get(k) for k in ("detail", "admissionDetail", "reason")}


def test_t1_rewrite_before_deadline_is_admitted(tmp_path, monkeypatch):
    res, run_dir = _run(tmp_path, monkeypatch, [
        ("write", _payload("first")), ("sleep", 1.5),
        ("write", _payload("second")), ("sleep", 1),
    ], cap=60)
    assert res.get("ok") is True, (res, _admission_detail(run_dir))
    assert res["report"] == "second"


def test_t2_rewrite_after_deadline_still_forfeits(tmp_path, monkeypatch):
    res, run_dir = _run(tmp_path, monkeypatch, [
        ("write", _payload("first")), ("sleep", 60),
    ], cap=4, on_term=_payload("second"))
    assert not res.get("ok"), res
    assert res.get("detail") == "worktree-dirtied-by-attempt", res
    assert res.get("attemptDetail") == "timeout-native-result-unadmitted", res
    records, _ = ED._journal_read(run_dir)
    state = ED._journal_state(records)
    grade = ED._grade_write_attempt(run_dir, state, 1)
    assert grade["admissionDetail"] == "result-completion-payload-mismatch", grade


def test_t3_identical_rewrite_and_single_write_admitted(tmp_path, monkeypatch):
    same = _payload("same")
    res, _ = _run(tmp_path, monkeypatch, [
        ("write", same), ("sleep", 1.5), ("write", same), ("sleep", 1),
    ], cap=60)
    assert res.get("ok") is True, res
    assert res["report"] == "same"


def test_t3_single_write_admitted(tmp_path, monkeypatch):
    res, _ = _run(tmp_path, monkeypatch, [("write", _payload("only"))], cap=60)
    assert res.get("ok") is True, res
    assert res["report"] == "only"


def test_t4_same_length_rewrite_seen_through_signature(tmp_path, monkeypatch):
    a, b = _payload("aaaaaa"), _payload("bbbbbb")
    assert len(a) == len(b) and a != b
    res, _ = _run(tmp_path, monkeypatch, [
        ("write", a), ("sleep", 1.5), ("write", b), ("sleep", 60),
    ], cap=5)
    assert res.get("ok") is True, res
    assert res.get("admittedAfterTimeout") is True, res
    assert res["report"] == "bbbbbb"


# ---- unit tests against the observer -------------------------------------------------

def _digest(report):
    return ED.engine_result_channel.canonical_payload_digest(
        ED._scrub_native_payload(json.loads(_payload(report))))


def _put(run_dir, text):
    with open(ED._native_result_path(run_dir, 1), "w", encoding="utf-8") as fh:
        fh.write(text)


def _held(run_dir, monkeypatch, report="A", at=10.0):
    _put(run_dir, _payload(report))
    obs = {"stamp": None, "prev_sig": None}
    monkeypatch.setattr(ED, "time", types.SimpleNamespace(monotonic=lambda: at))
    ED._observe_native_file_completion(
        obs, run_dir, 1, terminal=True, deadline_mono=100.0)
    assert obs["stamp"] is not None
    key = ED.engine_result_channel.FIELD_RESULT_COMPLETE_SHA256
    assert obs["stamp"][key] == _digest(report)
    return obs, key


def _observe_b(run_dir, monkeypatch, obs, *, after_read, deadline=100.0, report="B"):
    clock = [50.0]
    real_read = ED._read_native_result_file

    def _read(path):
        out = real_read(path)
        clock[0] = after_read
        return out

    monkeypatch.setattr(ED, "_read_native_result_file", _read)
    monkeypatch.setattr(ED, "time", types.SimpleNamespace(monotonic=lambda: clock[0]))
    _put(run_dir, _payload(report))
    ED._observe_native_file_completion(
        obs, run_dir, 1, terminal=True, deadline_mono=deadline)


def test_t5_post_read_instant_after_deadline_keeps_stamp(tmp_path, monkeypatch):
    run_dir = str(tmp_path)
    obs, key = _held(run_dir, monkeypatch)
    _observe_b(run_dir, monkeypatch, obs, after_read=150.0)
    assert obs["stamp"][key] == _digest("A")


def test_t5_post_read_instant_before_deadline_restamps(tmp_path, monkeypatch):
    run_dir = str(tmp_path)
    obs, key = _held(run_dir, monkeypatch)
    _observe_b(run_dir, monkeypatch, obs, after_read=60.0)
    assert obs["stamp"][key] == _digest("B")


def test_t6_unparseable_rewrite_keeps_stamp(tmp_path, monkeypatch):
    run_dir = str(tmp_path)
    obs, key = _held(run_dir, monkeypatch)
    _put(run_dir, "not json {")
    monkeypatch.setattr(ED, "time", types.SimpleNamespace(monotonic=lambda: 50.0))
    ED._observe_native_file_completion(
        obs, run_dir, 1, terminal=True, deadline_mono=100.0)
    assert obs["stamp"][key] == _digest("A")
    _put(run_dir, "[1,2,3]")
    ED._observe_native_file_completion(
        obs, run_dir, 1, terminal=True, deadline_mono=100.0)
    assert obs["stamp"][key] == _digest("A")


def test_t6_deleted_file_keeps_stamp(tmp_path, monkeypatch):
    run_dir = str(tmp_path)
    obs, key = _held(run_dir, monkeypatch)
    os.unlink(ED._native_result_path(run_dir, 1))
    ED._observe_native_file_completion(
        obs, run_dir, 1, terminal=True, deadline_mono=100.0)
    assert obs["stamp"][key] == _digest("A")


@pytest.mark.parametrize("deadline", [None, "soon", True])
def test_t6_no_real_deadline_never_restamps(tmp_path, monkeypatch, deadline):
    run_dir = str(tmp_path)
    obs, key = _held(run_dir, monkeypatch)
    _put(run_dir, _payload("B"))
    monkeypatch.setattr(ED, "time", types.SimpleNamespace(monotonic=lambda: 50.0))
    ED._observe_native_file_completion(
        obs, run_dir, 1, terminal=True, deadline_mono=deadline)
    assert obs["stamp"][key] == _digest("A")
