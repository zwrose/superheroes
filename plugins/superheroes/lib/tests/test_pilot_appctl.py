"""Tests for pilot per-slot app instance control."""
import contextlib
import http.server
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_appctl as pa  # noqa: E402
import pilot_contract as pc  # noqa: E402
import pilot_journal as pj  # noqa: E402
import pilot_lifecycle as pl  # noqa: E402

NOW = "2026-01-01T00:00:00Z"
LATER = "2026-01-01T00:00:01Z"
SLOT = "slot1"
SLOT_REF = "slot1@1"
ACCOUNTS = [{"account": "owner", "role": "resource-owner"}]
_DECLARATION = {"evidence": "app-lifecycle exercised"}
_JOIN_TIMEOUT = 30.0


def _tmp_dir():
    return tempfile.mkdtemp()


def _registry():
    digest = pc.declaration_digest(_DECLARATION)
    return {
        "schemaVersion": pc.REGISTRY_SCHEMA_VERSION,
        "records": [{
            "kind": "app-lifecycle",
            "declarationDigest": digest,
            "exercisedAt": NOW,
            "receipt": {"result": "pass", "evidence": "ok"},
        }],
    }


def _allocation(port):
    return {
        "host": "127.0.0.1",
        "port": port,
        "hostnames": [],
        "containers": [],
        "envMetadata": {},
    }


def _authorized(readiness_url):
    return {
        "schemaVersion": 1,
        "slotRef": SLOT_REF,
        "baseUrl": "http://127.0.0.1/",
        "readinessUrl": readiness_url,
        "policyDigest": "abc123",
    }


def _launch_base(cwd, port, readiness_url, **overrides):
    base = {
        "authorized": _authorized(readiness_url),
        "slot": SLOT,
        "slotRef": SLOT_REF,
        "cwd": cwd,
        "argv": [sys.executable, "-c", "import time; time.sleep(60)"],
        "env": {},
        "allocation": _allocation(port),
        "readinessUrl": readiness_url,
        "readinessAttribution": "nonce",
        "readinessTimeoutSeconds": 2.0,
        "pollSeconds": 0.05,
    }
    base.update(overrides)
    return base


def _setup_slot(slots_dir, state=pl.STATE_PROVISIONED):
    os.makedirs(slots_dir, exist_ok=True)
    created = pl.create_slot(slots_dir, SLOT, ACCOUNTS, now=NOW)
    assert created["ok"]
    rec = created["record"]
    if state == pl.STATE_PROVISIONING:
        return rec
    rec = pl.transition(rec, pl.STATE_PROVISIONED, now=NOW)
    pl.write_record(pl.record_path(slots_dir, SLOT), rec)
    return rec


def _journal_lines(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _instance_log_paths(slot_dir=None):
    base = slot_dir or os.path.join(tempfile.gettempdir(), SLOT)
    return (
        os.path.join(base, "app.stdout.log"),
        os.path.join(base, "app.stderr.log"),
    )


def _instance_record(**overrides):
    stdout_path, stderr_path = _instance_log_paths()
    base = {
        "schemaVersion": 1,
        "slot": SLOT,
        "slotRef": SLOT_REF,
        "state": pa.STATE_READY,
        "pid": 1,
        "pgid": 1,
        "launchNonce": "a" * 32,
        "cwd": os.path.realpath(tempfile.gettempdir()),
        "allocation": _allocation(9),
        "command": ["echo"],
        "readinessUrl": "http://127.0.0.1:9/",
        "readinessAttribution": "nonce",
        "stdoutPath": stdout_path,
        "stderrPath": stderr_path,
        "startedAt": NOW,
        "updatedAt": NOW,
        "stopReceipt": None,
    }
    base.update(overrides)
    return base


def _now_seq():
    seq = [NOW, LATER, "2026-01-01T00:00:02Z", "2026-01-01T00:00:03Z"]

    def fn():
        if seq:
            return seq.pop(0)
        return "2026-01-01T00:00:99Z"

    return fn


# --- resolve_invocation edges ---


@pytest.mark.parametrize("dev_command", [[], None, [""], ["x", 1], "x"])
def test_resolve_command_invalid(dev_command):
    r = pa.resolve_invocation(dev_command, params={}, readiness_url="http://x/")
    assert r == {"ok": False, "reason": pa.REASON_COMMAND_INVALID}


def test_resolve_params_not_mapping():
    r = pa.resolve_invocation(["echo"], params=[], readiness_url="http://x/")
    assert r["reason"] == pa.REASON_PARAMS_INVALID


@pytest.mark.parametrize("key", ["", "{bad}", "a{b}"])
def test_resolve_params_key_invalid(key):
    r = pa.resolve_invocation(["echo"], params={key: "v"}, readiness_url="http://x/")
    assert r["reason"] == pa.REASON_PARAMS_INVALID


def test_resolve_params_value_not_str():
    r = pa.resolve_invocation(["echo"], params={"p": 1}, readiness_url="http://x/")
    assert r["reason"] == pa.REASON_PARAMS_INVALID


def test_resolve_single_pass_literal_braces_in_value():
    r = pa.resolve_invocation(
        ["echo", "{port}"],
        params={"port": "{port}"},
        readiness_url="http://127.0.0.1:{port}/",
    )
    assert r["ok"]
    assert r["argv"] == ["echo", "{port}"]
    assert r["readinessUrl"] == "http://127.0.0.1:{port}/"


def test_resolve_unresolved_placeholder():
    r = pa.resolve_invocation(["echo", "{missing}"], params={}, readiness_url="http://x/")
    assert r["reason"] == pa.REASON_PLACEHOLDER_UNRESOLVED


def test_resolve_unresolved_in_readiness_url():
    r = pa.resolve_invocation(["echo"], params={}, readiness_url="http://{missing}/")
    assert r["reason"] == pa.REASON_PLACEHOLDER_UNRESOLVED


def test_resolve_placeholder_in_argv0():
    r = pa.resolve_invocation(["{bin}"], params={"bin": "echo"}, readiness_url="http://x/")
    assert r["reason"] == pa.REASON_PLACEHOLDER_IN_ARGV0


def test_resolve_unbalanced_brace():
    r = pa.resolve_invocation(["{bad"], params={}, readiness_url="http://x/")
    assert r["reason"] == pa.REASON_PARAMS_INVALID


def test_resolve_env_not_mapping():
    r = pa.resolve_invocation(["echo"], params={}, readiness_url="http://x/", env=[])
    assert r["reason"] == pa.REASON_ENV_INVALID


@pytest.mark.parametrize("key", ["", "a=b", "a\x00b"])
def test_resolve_env_key_invalid(key):
    r = pa.resolve_invocation(["echo"], params={}, readiness_url="http://x/", env={key: "v"})
    assert r["reason"] == pa.REASON_ENV_INVALID


def test_resolve_readiness_url_absent():
    r = pa.resolve_invocation(["echo"], params={}, readiness_url="")
    assert r["reason"] == pa.REASON_READINESS_URL_INVALID


def test_resolve_readiness_url_bad_scheme():
    r = pa.resolve_invocation(["echo"], params={}, readiness_url="ftp://x/")
    assert r["reason"] == pa.REASON_READINESS_URL_INVALID


def test_resolve_success():
    r = pa.resolve_invocation(
        ["run", "{port}"],
        params={"port": "3000"},
        readiness_url="http://127.0.0.1:{port}/ready",
        env={"K": "V"},
    )
    assert r["ok"]
    assert r["argv"] == ["run", "3000"]
    assert r["readinessUrl"] == "http://127.0.0.1:3000/ready"
    assert r["env"] == {"K": "V"}


# --- assert_unique_endpoints ---


def test_assert_unique_endpoints_empty_ok():
    assert pa.assert_unique_endpoints([])["ok"]


def test_assert_unique_endpoints_not_list():
    assert pa.assert_unique_endpoints({})["reason"] == pa.REASON_ALLOCATION_INVALID


def test_assert_unique_endpoints_duplicate_port():
    allocs = [
        {"slotRef": "slot1@1", "host": "localhost", "port": 3000},
        {"slotRef": "slot2@1", "host": "LOCALHOST.", "port": 3000},
    ]
    r = pa.assert_unique_endpoints(allocs)
    assert r["reason"] == pa.REASON_ENDPOINT_DUPLICATE
    assert r["duplicates"]


def test_assert_unique_endpoints_duplicate_slot_ref():
    allocs = [
        {"slotRef": "slot1@1", "host": "127.0.0.1", "port": 3000},
        {"slotRef": "slot1@1", "host": "127.0.0.1", "port": 3001},
    ]
    assert pa.assert_unique_endpoints(allocs)["reason"] == pa.REASON_ALLOCATION_INVALID


def test_assert_unique_endpoints_bad_port():
    allocs = [{"slotRef": "slot1@1", "host": "127.0.0.1", "port": 0}]
    assert pa.assert_unique_endpoints(allocs)["reason"] == pa.REASON_ALLOCATION_INVALID


# --- retry_gate ---


def test_retry_gate_bind_conflict_not_retryable():
    r = pa.retry_gate(pa.REASON_BIND_CONFLICT)
    assert r["retryable"] is False
    assert r["reason"] == pa.REASON_BIND_CONFLICT


def test_retry_gate_census():
    retryable = frozenset({
        pa.REASON_READINESS_TIMEOUT,
        pa.REASON_READINESS_TRANSPORT_ERROR,
    })
    assert retryable == pa.RETRYABLE_REASONS
    for name in dir(pa):
        if not name.startswith("REASON_"):
            continue
        token = getattr(pa, name)
        if not isinstance(token, str):
            continue
        gated = pa.retry_gate(token)
        if token in retryable:
            assert gated["retryable"] is True, token
        else:
            assert gated["retryable"] is False, token


# --- check_endpoint_free ---


@pytest.mark.parametrize(
    "host,port,timeout,connect",
    [
        (None, 9, 0.25, None),
        (123, 9, 0.25, None),
        ("", 9, 0.25, None),
        ("host\x00name", 9, 0.25, None),
        ("x" * 254, 9, 0.25, None),
        ("127.0.0.1", "9", 0.25, None),
        ("127.0.0.1", True, 0.25, None),
        ("127.0.0.1", 0, 0.25, None),
        ("127.0.0.1", 65536, 0.25, None),
        ("127.0.0.1", 9, float("nan"), None),
        ("127.0.0.1", 9, float("inf"), None),
        ("127.0.0.1", 9, "bad", None),
        ("127.0.0.1", 9, 0.25, "not-callable"),
    ],
    ids=[
        "host-none", "host-not-str", "host-empty", "host-nul", "host-too-long",
        "port-not-int", "port-bool", "port-zero", "port-out-of-range",
        "timeout-nan", "timeout-inf", "timeout-non-numeric", "connect-not-callable",
    ],
)
def test_check_endpoint_free_malformed_allocation(host, port, timeout, connect):
    r = pa.check_endpoint_free(host, port, timeout=timeout, connect=connect)
    assert r["ok"] is False
    assert r["reason"] == pa.REASON_ALLOCATION_INVALID


def test_check_endpoint_free_refused_ok():
    def connect_refused(addr, t):
        raise ConnectionRefusedError()

    assert pa.check_endpoint_free("127.0.0.1", 9, connect=connect_refused)["ok"]


def test_check_endpoint_free_timeout_ok():
    def connect_timeout(addr, t):
        raise socket.timeout()

    assert pa.check_endpoint_free("127.0.0.1", 9, connect=connect_timeout)["ok"]


def test_check_endpoint_free_other_oserror_bind_conflict():
    def connect_error(addr, t):
        raise OSError("probe failed")

    r = pa.check_endpoint_free("127.0.0.1", 9, connect=connect_error)
    assert r["ok"] is False
    assert r["reason"] == pa.REASON_BIND_CONFLICT


def test_check_endpoint_free_connect_raises_no_leak():
    def connect_boom(addr, t):
        raise ValueError("injected")

    r = pa.check_endpoint_free("127.0.0.1", 9, connect=connect_boom)
    assert r["ok"] is False
    assert r["reason"] == pa.REASON_BIND_CONFLICT


def test_check_endpoint_free_real_socket():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    try:
        occupied = pa.check_endpoint_free("127.0.0.1", port)
        assert occupied["ok"] is False
        assert occupied["reason"] == pa.REASON_BIND_CONFLICT
    finally:
        sock.close()
    assert pa.check_endpoint_free("127.0.0.1", port)["ok"]


# --- stand_up ---


def test_stand_up_record_before_spawn():
    tmp = _tmp_dir()
    try:
        cwd = os.path.join(tmp, "wt")
        os.makedirs(cwd)
        slots_dir = os.path.join(tmp, "slots")
        _setup_slot(slots_dir)
        journal = os.path.join(tmp, "journal.jsonl")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        launch = _launch_base(cwd, port, f"http://127.0.0.1:{port}/ready")
        nonce_holder = {}

        def spawn_stub(argv, *, cwd, env):
            loaded = pa.read_instance(slots_dir, SLOT)
            assert loaded["ok"]
            assert loaded["instance"]["state"] == pa.STATE_STARTING
            nonce_holder["nonce"] = env["SUPERHEROES_PILOT_LAUNCH_NONCE"]
            proc = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            return proc

        def probe(url, *, timeout):
            return {"status": 200, "body": nonce_holder.get("nonce", ""), "error": None}

        mono = iter([0.0, 0.0, 0.0, 0.0, 10.0])

        def monotonic():
            return next(mono, 10.0)

        result = pa.stand_up(
            launch,
            journal_path=journal,
            slots_dir_path=slots_dir,
            now=NOW,
            now_fn=_now_seq(),
            registry=_registry(),
            declaration=_DECLARATION,
            spawn=spawn_stub,
            readiness_probe=probe,
            monotonic=monotonic,
            sleep=lambda _t: None,
        )
        assert result["ok"]
        lines = _journal_lines(journal)
        assert lines[-1]["outcome"] == pj.OUTCOME_APPLIED
    finally:
        shutil.rmtree(tmp)


def test_stand_up_spawn_oserror_not_applied():
    tmp = _tmp_dir()
    try:
        cwd = os.path.join(tmp, "wt")
        os.makedirs(cwd)
        slots_dir = os.path.join(tmp, "slots")
        _setup_slot(slots_dir)
        journal = os.path.join(tmp, "journal.jsonl")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        launch = _launch_base(cwd, port, f"http://127.0.0.1:{port}/ready")

        def spawn_fail(argv, *, cwd, env):
            raise OSError("nope")

        result = pa.stand_up(
            launch,
            journal_path=journal,
            slots_dir_path=slots_dir,
            now=NOW,
            now_fn=_now_seq(),
            registry=_registry(),
            declaration=_DECLARATION,
            spawn=spawn_fail,
            readiness_probe=lambda *_a, **_k: {"status": 200, "body": "x", "error": None},
            monotonic=lambda: 0.0,
            sleep=lambda _t: None,
        )
        assert result["reason"] == pa.REASON_SPAWN_FAILED
        lines = _journal_lines(journal)
        assert lines[-1]["outcome"] == pj.OUTCOME_NOT_APPLIED
    finally:
        shutil.rmtree(tmp)


def test_stand_up_readiness_transport_error_at_deadline():
    tmp = _tmp_dir()
    try:
        cwd = os.path.join(tmp, "wt")
        os.makedirs(cwd)
        slots_dir = os.path.join(tmp, "slots")
        _setup_slot(slots_dir)
        journal = os.path.join(tmp, "journal.jsonl")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        launch = _launch_base(cwd, port, f"http://127.0.0.1:{port}/ready")
        times = iter([0.0, 5.0])

        result = pa.stand_up(
            launch,
            journal_path=journal,
            slots_dir_path=slots_dir,
            now=NOW,
            now_fn=_now_seq(),
            registry=_registry(),
            declaration=_DECLARATION,
            spawn=lambda argv, *, cwd, env: subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            ),
            readiness_probe=lambda *_a, **_k: {"status": None, "body": "", "error": "down"},
            monotonic=lambda: next(times, 99.0),
            sleep=lambda _t: None,
        )
        assert result["reason"] == pa.REASON_READINESS_TRANSPORT_ERROR
        assert _journal_lines(journal)[-1]["outcome"] == pj.OUTCOME_INDETERMINATE
    finally:
        shutil.rmtree(tmp)


def test_stand_up_readiness_timeout_no_status():
    tmp = _tmp_dir()
    try:
        cwd = os.path.join(tmp, "wt")
        os.makedirs(cwd)
        slots_dir = os.path.join(tmp, "slots")
        _setup_slot(slots_dir)
        journal = os.path.join(tmp, "journal.jsonl")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        launch = _launch_base(cwd, port, f"http://127.0.0.1:{port}/ready")
        times = iter([0.0, 5.0])

        result = pa.stand_up(
            launch,
            journal_path=journal,
            slots_dir_path=slots_dir,
            now=NOW,
            now_fn=_now_seq(),
            registry=_registry(),
            declaration=_DECLARATION,
            spawn=lambda argv, *, cwd, env: subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            ),
            readiness_probe=lambda *_a, **_k: {"status": None, "body": "", "error": None},
            monotonic=lambda: next(times, 99.0),
            sleep=lambda _t: None,
        )
        assert result["reason"] == pa.REASON_READINESS_TIMEOUT
    finally:
        shutil.rmtree(tmp)


def test_stand_up_nonce_unattributed():
    tmp = _tmp_dir()
    try:
        cwd = os.path.join(tmp, "wt")
        os.makedirs(cwd)
        slots_dir = os.path.join(tmp, "slots")
        _setup_slot(slots_dir)
        journal = os.path.join(tmp, "journal.jsonl")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        launch = _launch_base(cwd, port, f"http://127.0.0.1:{port}/ready")
        times = iter([0.0, 0.0, 5.0])

        result = pa.stand_up(
            launch,
            journal_path=journal,
            slots_dir_path=slots_dir,
            now=NOW,
            now_fn=_now_seq(),
            registry=_registry(),
            declaration=_DECLARATION,
            spawn=lambda argv, *, cwd, env: subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            ),
            readiness_probe=lambda *_a, **_k: {"status": 200, "body": "no-nonce", "error": None},
            monotonic=lambda: next(times, 99.0),
            sleep=lambda _t: None,
        )
        assert result["reason"] == pa.REASON_READINESS_UNATTRIBUTED
    finally:
        shutil.rmtree(tmp)


def test_stand_up_unattributed_degradation():
    tmp = _tmp_dir()
    try:
        cwd = os.path.join(tmp, "wt")
        os.makedirs(cwd)
        slots_dir = os.path.join(tmp, "slots")
        _setup_slot(slots_dir)
        journal = os.path.join(tmp, "journal.jsonl")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        launch = _launch_base(
            cwd, port, f"http://127.0.0.1:{port}/ready",
            readinessAttribution="unattributed",
        )

        result = pa.stand_up(
            launch,
            journal_path=journal,
            slots_dir_path=slots_dir,
            now=NOW,
            now_fn=_now_seq(),
            registry=_registry(),
            declaration=_DECLARATION,
            spawn=lambda argv, *, cwd, env: subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            ),
            readiness_probe=lambda *_a, **_k: {"status": 200, "body": "x", "error": None},
            monotonic=lambda: 0.0,
            sleep=lambda _t: None,
        )
        assert result["ok"]
        assert result["degradations"]
    finally:
        shutil.rmtree(tmp)


def test_stand_up_redirect_refused_immediately():
    tmp = _tmp_dir()
    try:
        cwd = os.path.join(tmp, "wt")
        os.makedirs(cwd)
        slots_dir = os.path.join(tmp, "slots")
        _setup_slot(slots_dir)
        journal = os.path.join(tmp, "journal.jsonl")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        launch = _launch_base(cwd, port, f"http://127.0.0.1:{port}/ready")
        times = iter([0.0])

        result = pa.stand_up(
            launch,
            journal_path=journal,
            slots_dir_path=slots_dir,
            now=NOW,
            now_fn=_now_seq(),
            registry=_registry(),
            declaration=_DECLARATION,
            spawn=lambda argv, *, cwd, env: subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            ),
            readiness_probe=lambda *_a, **_k: {"status": 302, "body": "", "error": None},
            monotonic=lambda: next(times, 99.0),
            sleep=lambda _t: None,
        )
        assert result["reason"] == pa.REASON_READINESS_REDIRECT_REFUSED
    finally:
        shutil.rmtree(tmp)


def test_stand_up_bind_conflict_stderr():
    tmp = _tmp_dir()
    try:
        cwd = os.path.join(tmp, "wt")
        os.makedirs(cwd)
        slots_dir = os.path.join(tmp, "slots")
        _setup_slot(slots_dir)
        journal = os.path.join(tmp, "journal.jsonl")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        launch = _launch_base(cwd, port, f"http://127.0.0.1:{port}/ready")

        stderr_path = os.path.join(slots_dir, SLOT, "app.stderr.log")

        def spawn_bind_fail(argv, *, cwd, env):
            with open(stderr_path, "wb") as fh:
                fh.write(b"EADDRINUSE\n")
            return subprocess.Popen(
                [sys.executable, "-c", "import sys; sys.exit(1)"],
                cwd=cwd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

        result = pa.stand_up(
            launch,
            journal_path=journal,
            slots_dir_path=slots_dir,
            now=NOW,
            now_fn=_now_seq(),
            registry=_registry(),
            declaration=_DECLARATION,
            spawn=spawn_bind_fail,
            readiness_probe=lambda *_a, **_k: {"status": None, "body": "", "error": "wait"},
            monotonic=lambda: 0.0,
            sleep=lambda _t: None,
        )
        assert result["reason"] == pa.REASON_BIND_CONFLICT
    finally:
        shutil.rmtree(tmp)


def test_stand_up_generation_moved_stops_child():
    tmp = _tmp_dir()
    try:
        cwd = os.path.join(tmp, "wt")
        os.makedirs(cwd)
        slots_dir = os.path.join(tmp, "slots")
        rec = _setup_slot(slots_dir)
        journal = os.path.join(tmp, "journal.jsonl")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        launch = _launch_base(cwd, port, f"http://127.0.0.1:{port}/ready")
        child_holder = {}
        phase = {"count": 0}

        def probe(url, *, timeout):
            if phase["count"] == 0:
                phase["count"] = 1
                rec2 = pl.transition(rec, pl.STATE_OCCUPIED, now=LATER)
                rec2 = pl.transition(rec2, pl.STATE_RELEASED, now=LATER)
                rec2 = pl.begin_generation(rec2, now=LATER)
                pl.write_record(pl.record_path(slots_dir, SLOT), rec2)
            return {"status": 200, "body": child_holder.get("nonce", ""), "error": None}

        def spawn_stub(argv, *, cwd, env):
            child_holder["nonce"] = env["SUPERHEROES_PILOT_LAUNCH_NONCE"]
            proc = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            child_holder["proc"] = proc
            return proc

        result = pa.stand_up(
            launch,
            journal_path=journal,
            slots_dir_path=slots_dir,
            now=NOW,
            now_fn=_now_seq(),
            registry=_registry(),
            declaration=_DECLARATION,
            spawn=spawn_stub,
            readiness_probe=probe,
            monotonic=lambda: 0.0,
            sleep=lambda _t: None,
        )
        assert result["reason"] == pa.REASON_GENERATION_MOVED
        proc = child_holder.get("proc")
        if proc is not None:
            proc.wait(timeout=_JOIN_TIMEOUT)
    finally:
        shutil.rmtree(tmp)


def _pin_poll_alive_to_child(monkeypatch, child_holder):
    """Pin stop()'s liveness view to the test's own child handle.

    PINNED CONDITION: `pilot_appctl._default_poll_alive`, for the duration of one test.
    The real one asks `killpg(pgid, 0)`, which keeps answering "alive" for a child that
    has exited but not yet been reaped — and stand_up's in-lock stop() reaps only after
    its kill loops, so it burns the full SIGTERM + SIGKILL budget (20s) on a zombie.

    MADE UNOBSERVABLE BY THIS PIN: that production timing. These tests will not notice
    if stop() gets slower, or faster, against an unreaped child. They pin liveness, not
    the stop sequence: the real SIGTERM, the real stop(), and the real persistence call
    all still run.
    """
    monkeypatch.setattr(
        pa,
        "_default_poll_alive",
        lambda _pgid: child_holder["proc"].poll() is None,
    )


def _reap_child(child_holder):
    """Failure-safe child cleanup, matching this file's real-process convention."""
    proc = child_holder.get("proc")
    if proc is None:
        return
    if proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except OSError:
            pass
    proc.wait(timeout=_JOIN_TIMEOUT)


def test_stand_up_generation_moved_persists_stop_to_disk(monkeypatch):
    """The in-lock generation-moved site writes the stopped instance record to disk.

    Bite axis: DURABILITY of the stop at pilot_appctl.py's generation-moved
    `_write_instance_locked` call — that the stop reached the file, not merely that
    stand_up returned a stopped record in memory.
    """
    tmp = _tmp_dir()
    child_holder = {}
    try:
        cwd = os.path.join(tmp, "wt")
        os.makedirs(cwd)
        slots_dir = os.path.join(tmp, "slots")
        rec = _setup_slot(slots_dir)
        journal = os.path.join(tmp, "journal.jsonl")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        launch = _launch_base(cwd, port, f"http://127.0.0.1:{port}/ready")
        phase = {"count": 0}
        _pin_poll_alive_to_child(monkeypatch, child_holder)

        def probe(url, *, timeout):
            if phase["count"] == 0:
                phase["count"] = 1
                rec2 = pl.transition(rec, pl.STATE_OCCUPIED, now=LATER)
                rec2 = pl.transition(rec2, pl.STATE_RELEASED, now=LATER)
                rec2 = pl.begin_generation(rec2, now=LATER)
                pl.write_record(pl.record_path(slots_dir, SLOT), rec2)
            return {"status": 200, "body": child_holder.get("nonce", ""), "error": None}

        def spawn_stub(argv, *, cwd, env):
            child_holder["nonce"] = env["SUPERHEROES_PILOT_LAUNCH_NONCE"]
            proc = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            child_holder["proc"] = proc
            return proc

        result = pa.stand_up(
            launch,
            journal_path=journal,
            slots_dir_path=slots_dir,
            now=NOW,
            now_fn=_now_seq(),
            registry=_registry(),
            declaration=_DECLARATION,
            spawn=spawn_stub,
            readiness_probe=probe,
            monotonic=lambda: 0.0,
            sleep=lambda _t: None,
        )
        assert result["reason"] == pa.REASON_GENERATION_MOVED
        assert result["instance"]["state"] == pa.STATE_STOPPED

        on_disk = pa.read_instance(slots_dir, SLOT)
        assert on_disk["ok"], on_disk
        assert on_disk["instance"]["state"] == pa.STATE_STOPPED
        assert on_disk["instance"]["stopReceipt"] == result["instance"]["stopReceipt"]
        assert on_disk["instance"]["updatedAt"] == result["instance"]["updatedAt"]
    finally:
        _reap_child(child_holder)
        shutil.rmtree(tmp)


def test_stand_up_unreadable_slot_record_persists_stop_to_disk(monkeypatch):
    """The in-lock unreadable-slot-record site writes the stopped instance record to disk.

    Bite axis: DURABILITY of the stop at pilot_appctl.py's unreadable-record
    `_write_instance_locked` call — that the stop reached the file, not merely that
    stand_up returned a stopped record in memory.
    """
    tmp = _tmp_dir()
    child_holder = {}
    try:
        cwd = os.path.join(tmp, "wt")
        os.makedirs(cwd)
        slots_dir = os.path.join(tmp, "slots")
        _setup_slot(slots_dir)
        journal = os.path.join(tmp, "journal.jsonl")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        # This path stops the child under the DEFAULT corroborator, which compares
        # `ps -o command=` against argv[0]. A framework-wrapped interpreter reports a
        # different basename than sys.executable, so drive a plain `sleep` child whose
        # reported command matches the launch argv on both macOS and Linux.
        sleep_bin = shutil.which("sleep")
        assert sleep_bin, "no sleep(1) on PATH"
        launch = _launch_base(
            cwd,
            port,
            f"http://127.0.0.1:{port}/ready",
            argv=[sleep_bin, "60"],
        )
        phase = {"count": 0}
        _pin_poll_alive_to_child(monkeypatch, child_holder)

        def probe(url, *, timeout):
            if phase["count"] == 0:
                phase["count"] = 1
                # Corrupt the slot record so the post-readiness re-read inside the
                # lock fails, driving the unreadable-record branch.
                with open(pl.record_path(slots_dir, SLOT), "w", encoding="utf-8") as fh:
                    fh.write("{ not json")
            return {"status": 200, "body": child_holder.get("nonce", ""), "error": None}

        def spawn_stub(argv, *, cwd, env):
            child_holder["nonce"] = env["SUPERHEROES_PILOT_LAUNCH_NONCE"]
            proc = subprocess.Popen(
                argv,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            child_holder["proc"] = proc
            return proc

        result = pa.stand_up(
            launch,
            journal_path=journal,
            slots_dir_path=slots_dir,
            now=NOW,
            now_fn=_now_seq(),
            registry=_registry(),
            declaration=_DECLARATION,
            spawn=spawn_stub,
            readiness_probe=probe,
            monotonic=lambda: 0.0,
            sleep=lambda _t: None,
        )
        assert result["reason"] == pa.REASON_SLOT_STATE_NOT_LAUNCHABLE
        assert result["instance"]["state"] == pa.STATE_STOPPED

        on_disk = pa.read_instance(slots_dir, SLOT)
        assert on_disk["ok"], on_disk
        assert on_disk["instance"]["state"] == pa.STATE_STOPPED
        assert on_disk["instance"]["stopReceipt"] == result["instance"]["stopReceipt"]
        assert on_disk["instance"]["updatedAt"] == result["instance"]["updatedAt"]
    finally:
        _reap_child(child_holder)
        shutil.rmtree(tmp)


def test_stand_up_record_write_failed_keeps_pid(monkeypatch):
    tmp = _tmp_dir()
    try:
        cwd = os.path.join(tmp, "wt")
        os.makedirs(cwd)
        slots_dir = os.path.join(tmp, "slots")
        _setup_slot(slots_dir)
        journal = os.path.join(tmp, "journal.jsonl")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        launch = _launch_base(cwd, port, f"http://127.0.0.1:{port}/ready")
        real_write = pa.write_instance
        calls = {"n": 0}

        def flaky_write(slots_dir_path, slot, instance, *, timeout=30.0):
            calls["n"] += 1
            if calls["n"] >= 2 and instance.get("state") == pa.STATE_READY:
                return {"ok": False, "reason": pa.REASON_INSTANCE_RECORD_WRITE_FAILED}
            return real_write(slots_dir_path, slot, instance, timeout=timeout)

        monkeypatch.setattr(pa, "write_instance", flaky_write)
        nonce_holder = {}

        result = pa.stand_up(
            launch,
            journal_path=journal,
            slots_dir_path=slots_dir,
            now=NOW,
            now_fn=_now_seq(),
            registry=_registry(),
            declaration=_DECLARATION,
            spawn=lambda argv, *, cwd, env: (
                nonce_holder.update({"nonce": env["SUPERHEROES_PILOT_LAUNCH_NONCE"]}) or
                subprocess.Popen(
                    [sys.executable, "-c", "import time; time.sleep(30)"],
                    cwd=cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True,
                )
            ),
            readiness_probe=lambda *_a, **_k: {
                "status": 200,
                "body": nonce_holder.get("nonce", ""),
                "error": None,
            },
            monotonic=lambda: 0.0,
            sleep=lambda _t: None,
        )
        assert result["ok"] is False
        assert result["reason"] == pa.REASON_INSTANCE_RECORD_WRITE_FAILED
        assert "pid" in result
        assert result["pid"] > 0
        proc = result.get("instance")
        if proc is not None:
            pid = result["pid"]
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass
    finally:
        shutil.rmtree(tmp)


def test_stand_up_declaration_unexercised():
    tmp = _tmp_dir()
    try:
        cwd = os.path.join(tmp, "wt")
        os.makedirs(cwd)
        slots_dir = os.path.join(tmp, "slots")
        _setup_slot(slots_dir)
        journal = os.path.join(tmp, "journal.jsonl")
        launch = _launch_base(cwd, 9, "http://127.0.0.1:9/ready")
        result = pa.stand_up(
            launch,
            journal_path=journal,
            slots_dir_path=slots_dir,
            now=NOW,
            now_fn=lambda: NOW,
            registry={},
            declaration=_DECLARATION,
            monotonic=lambda: 0.0,
            sleep=lambda _t: None,
        )
        assert result["reason"] == pa.REASON_DECLARATION_UNEXERCISED
        # kind-unknown and unexercised both map to REASON_DECLARATION_UNEXERCISED today —
        # no separate appctl token exists for kind-unknown.
    finally:
        shutil.rmtree(tmp)


def test_stand_up_bind_conflict_no_journal():
    tmp = _tmp_dir()
    try:
        cwd = os.path.join(tmp, "wt")
        os.makedirs(cwd)
        slots_dir = os.path.join(tmp, "slots")
        _setup_slot(slots_dir)
        journal = os.path.join(tmp, "journal.jsonl")
        occupier = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        occupier.bind(("127.0.0.1", 0))
        occupier.listen(1)
        port = occupier.getsockname()[1]
        launch = _launch_base(cwd, port, f"http://127.0.0.1:{port}/ready")
        result = pa.stand_up(
            launch,
            journal_path=journal,
            slots_dir_path=slots_dir,
            now=NOW,
            now_fn=lambda: NOW,
            registry=_registry(),
            declaration=_DECLARATION,
            monotonic=lambda: 0.0,
            sleep=lambda _t: None,
        )
        assert result["reason"] == pa.REASON_BIND_CONFLICT
        assert not os.path.exists(journal)
        occupier.close()
    finally:
        shutil.rmtree(tmp)


# --- read_instance ---


def test_read_instance_absent():
    tmp = _tmp_dir()
    try:
        slots_dir = os.path.join(tmp, "slots")
        os.makedirs(os.path.join(slots_dir, SLOT), exist_ok=True)
        r = pa.read_instance(slots_dir, SLOT)
        assert r["reason"] == pa.REASON_INSTANCE_RECORD_ABSENT
    finally:
        shutil.rmtree(tmp)


def test_read_instance_symlink_refused():
    tmp = _tmp_dir()
    try:
        slots_dir = os.path.join(tmp, "slots")
        slot_dir = os.path.join(slots_dir, SLOT)
        os.makedirs(slot_dir)
        target = os.path.join(tmp, "target.json")
        with open(target, "w", encoding="utf-8") as fh:
            fh.write("{}")
        link = os.path.join(slot_dir, "app.json")
        os.symlink(target, link)
        r = pa.read_instance(slots_dir, SLOT)
        assert r["reason"] == pa.REASON_INSTANCE_RECORD_UNREADABLE
    finally:
        shutil.rmtree(tmp)


# --- stop ---


def _running_instance():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    tmp = _tmp_dir()
    stdout_path, stderr_path = _instance_log_paths(tmp)
    proc = subprocess.Popen(
        ["sleep", "120"],
        cwd=tmp,
        stdout=open(stdout_path, "wb"),
        stderr=open(stderr_path, "wb"),
        start_new_session=True,
    )
    pgid = os.getpgid(proc.pid)
    inst = _instance_record(
        state=pa.STATE_READY,
        pid=proc.pid,
        pgid=pgid,
        cwd=tmp,
        allocation=_allocation(port),
        command=["sleep", "120"],
        readinessUrl=f"http://127.0.0.1:{port}/",
        stdoutPath=stdout_path,
        stderrPath=stderr_path,
    )
    return proc, tmp, inst


def test_stop_uncorroborated_no_signal():
    inst = _instance_record(
        state=pa.STATE_READY,
        pid=999999,
        pgid=999999,
        command=["/no/such/binary"],
    )
    calls = []

    def spy_terminate(pgid, sig):
        calls.append((pgid, sig))

    r = pa.stop(
        inst,
        now_fn=lambda: NOW,
        corroborate=lambda _i: False,
        terminate=spy_terminate,
    )
    assert r["reason"] == pa.REASON_INSTANCE_PID_MISMATCH
    assert calls == []


def test_stop_group_gone_port_occupied():
    occupier = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupier.bind(("127.0.0.1", 0))
    occupier.listen(1)
    port = occupier.getsockname()[1]
    inst = _instance_record(
        state=pa.STATE_READY,
        pid=1,
        pgid=1,
        allocation=_allocation(port),
        readinessUrl=f"http://127.0.0.1:{port}/",
    )
    try:
        r = pa.stop(
            inst,
            now_fn=lambda: NOW,
            corroborate=lambda _i: True,
            poll_alive=lambda _pgid: False,
            check_free=lambda h, p: {"ok": False, "reason": pa.REASON_BIND_CONFLICT},
        )
        assert r["reason"] == pa.REASON_STOP_INDETERMINATE
        assert r["observed"] is False
    finally:
        occupier.close()


def test_stop_double_idempotent():
    inst = _instance_record(
        state=pa.STATE_STOPPED,
        pid=0,
        pgid=0,
        stopReceipt={
            "step": "app-instance",
            "slotRef": SLOT_REF,
            "observedAt": NOW,
            "evidence": "already stopped",
        },
    )
    r = pa.stop(inst, now_fn=lambda: NOW)
    assert r["ok"] and r["observed"]


# real-default integration tests (no custom pytest mark — repo has no pytest config)
def test_real_default_spawn_process_group():
    proc = None
    inst = None
    tmp = _tmp_dir()
    try:
        stdout_path, stderr_path = _instance_log_paths(tmp)
        nonce = "a" * 32
        cmd = [
            sys.executable, "-c",
            "import os, sys, time; sys.stdout.write(os.environ['SUPERHEROES_PILOT_LAUNCH_NONCE']); "
            "sys.stdout.flush(); time.sleep(120)",
        ]
        proc = pa._default_spawn(
            cmd,
            cwd=tmp,
            env={"SUPERHEROES_PILOT_LAUNCH_NONCE": nonce},
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
        pgid = os.getpgid(proc.pid)
        assert pgid != os.getpgid(os.getpid())
        time.sleep(0.2)
        with open(stdout_path, encoding="utf-8") as fh:
            assert fh.read() == nonce
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        inst = _instance_record(
            state=pa.STATE_READY,
            pid=proc.pid,
            pgid=pgid,
            cwd=tmp,
            allocation=_allocation(port),
            command=cmd,
            readinessUrl=f"http://127.0.0.1:{port}/",
            stdoutPath=stdout_path,
            stderrPath=stderr_path,
        )
        r = pa.stop(inst, now_fn=lambda: NOW, corroborate=lambda _i: True)
        assert r["ok"] and r["observed"]
        proc.wait(timeout=_JOIN_TIMEOUT)
    finally:
        if proc is not None and proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except OSError:
                pass
            proc.wait(timeout=_JOIN_TIMEOUT)
        shutil.rmtree(tmp)


def test_real_spawn_process_group_and_stop():
    proc = None
    inst = None
    tmp = None
    try:
        proc, tmp, inst = _running_instance()
        pgid = inst["pgid"]
        assert os.getpgid(proc.pid) == pgid
        assert pgid != os.getpgid(os.getpid())
        r = pa.stop(inst, now_fn=lambda: NOW)
        assert r["ok"] and r["observed"] and r["receipt"]
        proc.wait(timeout=_JOIN_TIMEOUT)
    finally:
        if proc is not None and proc.poll() is None:
            try:
                os.killpg(inst["pgid"], signal.SIGKILL)
            except OSError:
                pass
            proc.wait(timeout=_JOIN_TIMEOUT)
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)


def test_real_readiness_probe_2xx():
    holder = {"port": None, "server": None, "thread": None}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok-body")

        def log_message(self, *_args):
            return

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        r = pa._default_readiness_probe(f"http://127.0.0.1:{port}/", timeout=2.0)
        assert r["status"] == 200
        assert r["body"] == "ok-body"
    finally:
        server.shutdown()


def test_real_readiness_probe_302_not_followed():
    class RedirectHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", "/ready"):
                self.send_response(302)
                self.send_header("Location", "/ok")
                self.end_headers()
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *_args):
            return

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = http.server.HTTPServer(("127.0.0.1", port), RedirectHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        r = pa._default_readiness_probe(f"http://127.0.0.1:{port}/", timeout=2.0)
        assert r["status"] == 302
    finally:
        server.shutdown()


def test_validate_launch_slot_slotref_mismatch():
    launch = _launch_base(os.path.realpath(tempfile.gettempdir()), 9, "http://127.0.0.1:9/")
    launch["slot"] = "slot-a"
    launch["slotRef"] = "slot-b@1"
    launch["authorized"]["slotRef"] = "slot-b@1"
    r = pa._validate_launch(launch)
    assert r["reason"] == pa.REASON_LAUNCH_INVALID


def test_validate_launch_env_key_equals():
    tmp = _tmp_dir()
    try:
        launch = _launch_base(tmp, 9, "http://127.0.0.1:9/")
        launch["env"] = {"PATH=/tmp/evil": "x"}
        r = pa._validate_launch(launch)
        assert r["reason"] == pa.REASON_ENV_INVALID
    finally:
        shutil.rmtree(tmp)


def test_stand_up_instance_record_exists():
    tmp = _tmp_dir()
    try:
        cwd = os.path.join(tmp, "wt")
        os.makedirs(cwd)
        slots_dir = os.path.join(tmp, "slots")
        _setup_slot(slots_dir)
        journal = os.path.join(tmp, "journal.jsonl")
        stdout_path, stderr_path = pa._instance_log_paths(slots_dir, SLOT)
        existing = _instance_record(
            state=pa.STATE_READY,
            cwd=cwd,
            stdoutPath=stdout_path,
            stderrPath=stderr_path,
        )
        pa.write_instance(slots_dir, SLOT, existing)
        launch = _launch_base(cwd, 9, "http://127.0.0.1:9/")
        result = pa.stand_up(
            launch,
            journal_path=journal,
            slots_dir_path=slots_dir,
            now=NOW,
            now_fn=lambda: NOW,
            registry=_registry(),
            declaration=_DECLARATION,
            monotonic=lambda: 0.0,
            sleep=lambda _t: None,
        )
        assert result["reason"] == pa.REASON_INSTANCE_RECORD_EXISTS
    finally:
        shutil.rmtree(tmp)


def test_stand_up_slot_state_not_launchable():
    tmp = _tmp_dir()
    try:
        cwd = os.path.join(tmp, "wt")
        os.makedirs(cwd)
        slots_dir = os.path.join(tmp, "slots")
        rec = _setup_slot(slots_dir)
        rec = pl.transition(rec, pl.STATE_OCCUPIED, now=NOW)
        pl.write_record(pl.record_path(slots_dir, SLOT), rec)
        journal = os.path.join(tmp, "journal.jsonl")
        launch = _launch_base(cwd, 9, "http://127.0.0.1:9/")
        result = pa.stand_up(
            launch,
            journal_path=journal,
            slots_dir_path=slots_dir,
            now=NOW,
            now_fn=lambda: NOW,
            registry=_registry(),
            declaration=_DECLARATION,
            monotonic=lambda: 0.0,
            sleep=lambda _t: None,
        )
        assert result["reason"] == pa.REASON_SLOT_STATE_NOT_LAUNCHABLE
    finally:
        shutil.rmtree(tmp)


def test_stand_up_process_exited():
    tmp = _tmp_dir()
    try:
        cwd = os.path.join(tmp, "wt")
        os.makedirs(cwd)
        slots_dir = os.path.join(tmp, "slots")
        _setup_slot(slots_dir)
        journal = os.path.join(tmp, "journal.jsonl")
        launch = _launch_base(cwd, 9, "http://127.0.0.1:9/")
        result = pa.stand_up(
            launch,
            journal_path=journal,
            slots_dir_path=slots_dir,
            now=NOW,
            now_fn=_now_seq(),
            registry=_registry(),
            declaration=_DECLARATION,
            spawn=lambda argv, *, cwd, env: subprocess.Popen(
                [sys.executable, "-c", "import sys; sys.exit(0)"],
                cwd=cwd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            ),
            readiness_probe=lambda *_a, **_k: {"status": None, "body": "", "error": "wait"},
            monotonic=lambda: 0.0,
            sleep=lambda _t: None,
        )
        assert result["reason"] == pa.REASON_PROCESS_EXITED
    finally:
        shutil.rmtree(tmp)


def test_stand_up_readiness_unexpected_status():
    tmp = _tmp_dir()
    try:
        cwd = os.path.join(tmp, "wt")
        os.makedirs(cwd)
        slots_dir = os.path.join(tmp, "slots")
        _setup_slot(slots_dir)
        journal = os.path.join(tmp, "journal.jsonl")
        launch = _launch_base(cwd, 9, "http://127.0.0.1:9/")
        times = iter([0.0, 5.0])
        result = pa.stand_up(
            launch,
            journal_path=journal,
            slots_dir_path=slots_dir,
            now=NOW,
            now_fn=_now_seq(),
            registry=_registry(),
            declaration=_DECLARATION,
            spawn=lambda argv, *, cwd, env: subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                cwd=cwd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            ),
            readiness_probe=lambda *_a, **_k: {"status": 404, "body": "", "error": None},
            monotonic=lambda: next(times, 99.0),
            sleep=lambda _t: None,
        )
        assert result["reason"] == pa.REASON_READINESS_UNEXPECTED_STATUS
    finally:
        shutil.rmtree(tmp)


def test_write_and_clear_instance():
    tmp = _tmp_dir()
    try:
        slots_dir = os.path.join(tmp, "slots")
        _setup_slot(slots_dir)
        stdout_path, stderr_path = pa._instance_log_paths(slots_dir, SLOT)
        inst = _instance_record(
            state=pa.STATE_STOPPED,
            pid=0,
            pgid=0,
            cwd=tmp,
            stdoutPath=stdout_path,
            stderrPath=stderr_path,
        )
        written = pa.write_instance(slots_dir, SLOT, inst)
        assert written["ok"]
        loaded = pa.read_instance(slots_dir, SLOT)
        assert loaded["ok"]
        cleared = pa.clear_instance(slots_dir, SLOT)
        assert cleared["ok"]
        absent = pa.read_instance(slots_dir, SLOT)
        assert absent["reason"] == pa.REASON_INSTANCE_RECORD_ABSENT
    finally:
        shutil.rmtree(tmp)


def test_default_spawn_chatty_child_survives_large_output():
    tmp = _tmp_dir()
    try:
        stdout_path, stderr_path = pa._instance_log_paths(tmp, SLOT)
        os.makedirs(os.path.dirname(stdout_path), exist_ok=True)
        script = (
            "import sys, time\n"
            "sys.stdout.write('x' * 70000)\n"
            "sys.stderr.write('y' * 70000)\n"
            "sys.stdout.flush(); sys.stderr.flush()\n"
            "time.sleep(5)\n"
        )
        proc = pa._default_spawn(
            [sys.executable, "-c", script],
            cwd=tmp,
            env={},
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
        time.sleep(0.5)
        assert proc.poll() is None
        os.kill(proc.pid, signal.SIGKILL)
        proc.wait(timeout=_JOIN_TIMEOUT)
    finally:
        shutil.rmtree(tmp)


def test_stop_stopped_without_receipt_is_indeterminate():
    inst = _instance_record(
        state=pa.STATE_STOPPED,
        pid=0,
        pgid=0,
        stopReceipt=None,
    )
    r = pa.stop(inst, now_fn=lambda: NOW, corroborate=lambda _i: True)
    assert r["reason"] == pa.REASON_STOP_INDETERMINATE


def test_stop_non_positive_pgid_refused():
    inst = _instance_record(state=pa.STATE_READY, pid=1, pgid=0)
    calls = []

    def spy_terminate(pgid, sig):
        calls.append((pgid, sig))

    r = pa.stop(
        inst,
        now_fn=lambda: NOW,
        corroborate=lambda _i: True,
        terminate=spy_terminate,
    )
    assert r["reason"] == pa.REASON_STOP_INDETERMINATE
    assert calls == []


def test_stop_endpoint_timeout_not_observed():
    inst = _instance_record(state=pa.STATE_READY, pid=2, pgid=2)

    def check_timeout(host, port):
        return {"ok": True, "reason": None, "observable": False}

    r = pa.stop(
        inst,
        now_fn=lambda: NOW,
        corroborate=lambda _i: True,
        poll_alive=lambda _pgid: False,
        check_free=check_timeout,
    )
    assert r["reason"] == pa.REASON_STOP_INDETERMINATE


def test_stand_up_journal_end_write_failure(monkeypatch):
    tmp = _tmp_dir()
    try:
        cwd = os.path.join(tmp, "wt")
        os.makedirs(cwd)
        slots_dir = os.path.join(tmp, "slots")
        _setup_slot(slots_dir)
        journal = os.path.join(tmp, "journal.jsonl")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        launch = _launch_base(cwd, port, f"http://127.0.0.1:{port}/ready")
        nonce_holder = {}
        real_end = pj.end_effect

        def fail_end(*args, **kwargs):
            if kwargs.get("outcome") == pj.OUTCOME_APPLIED:
                return {"ok": False, "reason": pj.REASON_JOURNAL_WRITE_FAILED}
            return real_end(*args, **kwargs)

        monkeypatch.setattr(pj, "end_effect", fail_end)
        result = pa.stand_up(
            launch,
            journal_path=journal,
            slots_dir_path=slots_dir,
            now=NOW,
            now_fn=_now_seq(),
            registry=_registry(),
            declaration=_DECLARATION,
            spawn=lambda argv, *, cwd, env: (
                nonce_holder.update({"nonce": env["SUPERHEROES_PILOT_LAUNCH_NONCE"]}) or
                subprocess.Popen(
                    [sys.executable, "-c", "import time; time.sleep(30)"],
                    cwd=cwd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            ),
            readiness_probe=lambda *_a, **_k: {
                "status": 200,
                "body": nonce_holder.get("nonce", ""),
                "error": None,
            },
            monotonic=lambda: 0.0,
            sleep=lambda _t: None,
        )
        assert result["ok"] is False
        assert result["reason"] == pa.REASON_JOURNAL_WRITE_FAILED
        if result.get("pid"):
            try:
                os.kill(result["pid"], signal.SIGKILL)
            except OSError:
                pass
    finally:
        shutil.rmtree(tmp)


def test_write_instance_locked_inside_slot_lock_succeeds_quickly():
    tmp = _tmp_dir()
    try:
        slots_dir = os.path.join(tmp, "slots")
        _setup_slot(slots_dir)
        stdout_path, stderr_path = pa._instance_log_paths(slots_dir, SLOT)
        inst = _instance_record(
            state=pa.STATE_STARTING,
            pid=0,
            pgid=0,
            stdoutPath=stdout_path,
            stderrPath=stderr_path,
        )
        t0 = time.monotonic()
        with pl.slot_lock(slots_dir, SLOT, timeout=0.5):
            result = pa._write_instance_locked(slots_dir, SLOT, inst)
        elapsed = time.monotonic() - t0
        assert result["ok"] is True, result
        assert elapsed < 0.25, elapsed
    finally:
        shutil.rmtree(tmp)


def test_write_instance_refuses_when_lock_held_externally():
    tmp = _tmp_dir()
    try:
        slots_dir = os.path.join(tmp, "slots")
        _setup_slot(slots_dir)
        stdout_path, stderr_path = pa._instance_log_paths(slots_dir, SLOT)
        inst = _instance_record(
            state=pa.STATE_STARTING,
            pid=0,
            pgid=0,
            stdoutPath=stdout_path,
            stderrPath=stderr_path,
        )
        held = threading.Event()
        release = threading.Event()

        def holder():
            with pl.slot_lock(slots_dir, SLOT):
                held.set()
                release.wait(timeout=5.0)

        thread = threading.Thread(target=holder)
        thread.start()
        held.wait(timeout=5.0)
        t0 = time.monotonic()
        result = pa.write_instance(slots_dir, SLOT, inst, timeout=0.2)
        elapsed = time.monotonic() - t0
        release.set()
        thread.join(timeout=5.0)
        assert result["ok"] is False
        assert result["reason"] == pa.REASON_INSTANCE_RECORD_WRITE_FAILED
        assert elapsed >= 0.15
    finally:
        shutil.rmtree(tmp)


def test_stand_up_post_spawn_lock_failure_compensates_child(monkeypatch):
    tmp = _tmp_dir()
    try:
        cwd = os.path.join(tmp, "wt")
        os.makedirs(cwd)
        slots_dir = os.path.join(tmp, "slots")
        _setup_slot(slots_dir)
        journal = os.path.join(tmp, "journal.jsonl")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        launch = _launch_base(cwd, port, f"http://127.0.0.1:{port}/ready")
        child_holder = {}
        real_slot_lock = pl.slot_lock
        calls = {"n": 0}

        @contextlib.contextmanager
        def flaky_slot_lock(slots_dir_path, slot, *, timeout=30.0):
            calls["n"] += 1
            if calls["n"] >= 3:
                raise pl.PilotLifecycleError(pl.REASON_LOCK_UNAVAILABLE)
            with real_slot_lock(slots_dir_path, slot, timeout=timeout):
                yield

        monkeypatch.setattr(pl, "slot_lock", flaky_slot_lock)
        result = pa.stand_up(
            launch,
            journal_path=journal,
            slots_dir_path=slots_dir,
            now=NOW,
            now_fn=_now_seq(),
            registry=_registry(),
            declaration=_DECLARATION,
            spawn=lambda argv, *, cwd, env: (
                child_holder.update({
                    "nonce": env["SUPERHEROES_PILOT_LAUNCH_NONCE"],
                    "proc": subprocess.Popen(
                        [sys.executable, "-c", "import time; time.sleep(60)"],
                        cwd=cwd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    ),
                }) or child_holder["proc"]
            ),
            readiness_probe=lambda *_a, **_k: {
                "status": 200,
                "body": child_holder.get("nonce", ""),
                "error": None,
            },
            monotonic=lambda: 0.0,
            sleep=lambda _t: None,
        )
        assert result["ok"] is False
        assert result["reason"] == pa.REASON_SLOT_STATE_NOT_LAUNCHABLE
        proc = child_holder.get("proc")
        assert proc is not None
        proc.wait(timeout=_JOIN_TIMEOUT)
        assert _journal_lines(journal)[-1]["outcome"] == pj.OUTCOME_INDETERMINATE
    finally:
        shutil.rmtree(tmp)


def test_stand_up_readiness_failure_journal_end_fails_compensates_child(monkeypatch):
    tmp = _tmp_dir()
    child_holder = {}
    try:
        cwd = os.path.join(tmp, "wt")
        os.makedirs(cwd)
        slots_dir = os.path.join(tmp, "slots")
        _setup_slot(slots_dir)
        journal = os.path.join(tmp, "journal.jsonl")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        launch = _launch_base(cwd, port, f"http://127.0.0.1:{port}/ready")
        real_end = pj.end_effect

        def fail_indeterminate_end(*args, **kwargs):
            if kwargs.get("outcome") == pj.OUTCOME_INDETERMINATE:
                return {"ok": False, "reason": pj.REASON_JOURNAL_WRITE_FAILED}
            return real_end(*args, **kwargs)

        monkeypatch.setattr(pj, "end_effect", fail_indeterminate_end)
        compensate_calls = {"n": 0}
        real_compensate = pa._compensate_running_child

        def track_compensate(*args, **kwargs):
            compensate_calls["n"] += 1
            return real_compensate(*args, **kwargs)

        monkeypatch.setattr(pa, "_compensate_running_child", track_compensate)
        times = iter([0.0, 5.0])
        result = pa.stand_up(
            launch,
            journal_path=journal,
            slots_dir_path=slots_dir,
            now=NOW,
            now_fn=_now_seq(),
            registry=_registry(),
            declaration=_DECLARATION,
            spawn=lambda argv, *, cwd, env: (
                child_holder.update({"proc": subprocess.Popen(
                    [sys.executable, "-c", "import time; time.sleep(60)"],
                    cwd=cwd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )}) or child_holder["proc"]
            ),
            readiness_probe=lambda *_a, **_k: {"status": None, "body": "", "error": "down"},
            monotonic=lambda: next(times, 99.0),
            sleep=lambda _t: None,
        )
        assert result["ok"] is False
        assert result["reason"] == pa.REASON_JOURNAL_WRITE_FAILED
        assert compensate_calls["n"] >= 1
    finally:
        proc = child_holder.get("proc")
        if proc is not None and proc.poll() is None:
            try:
                os.kill(proc.pid, signal.SIGKILL)
            except OSError:
                pass
        shutil.rmtree(tmp)


def test_stand_up_log_symlink_refuses_spawn():
    tmp = _tmp_dir()
    try:
        cwd = os.path.join(tmp, "wt")
        os.makedirs(cwd)
        slots_dir = os.path.join(tmp, "slots")
        _setup_slot(slots_dir)
        journal = os.path.join(tmp, "journal.jsonl")
        victim = os.path.join(tmp, "victim.log")
        with open(victim, "w", encoding="utf-8") as fh:
            fh.write("precious\n")
        slot_dir = os.path.join(slots_dir, SLOT)
        os.symlink(victim, os.path.join(slot_dir, "app.stdout.log"))
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        launch = _launch_base(cwd, port, f"http://127.0.0.1:{port}/ready")
        result = pa.stand_up(
            launch,
            journal_path=journal,
            slots_dir_path=slots_dir,
            now=NOW,
            now_fn=_now_seq(),
            registry=_registry(),
            declaration=_DECLARATION,
            monotonic=lambda: 0.0,
            sleep=lambda _t: None,
        )
        assert result["ok"] is False
        assert result["reason"] == pa.REASON_SPAWN_FAILED
        with open(victim, encoding="utf-8") as fh:
            assert fh.read() == "precious\n"
    finally:
        shutil.rmtree(tmp)


def test_validate_instance_rejects_foreign_stop_receipt():
    inst = _instance_record(
        state=pa.STATE_STOPPED,
        stopReceipt={
            "step": "app-instance",
            "slotRef": "slotb@1",
            "observedAt": NOW,
            "evidence": "evidence about a DIFFERENT slot",
        },
    )
    with pytest.raises(pa.PilotAppctlError) as exc:
        pa._validate_instance_record(inst)
    assert exc.value.reason == pa.REASON_INSTANCE_RECORD_INVALID


def test_stop_rejects_foreign_stop_receipt_on_stopped_record():
    inst = _instance_record(
        state=pa.STATE_STOPPED,
        stopReceipt={
            "step": "app-instance",
            "slotRef": "slotb@1",
            "observedAt": NOW,
            "evidence": "evidence about a DIFFERENT slot",
        },
    )
    result = pa.stop(inst, now_fn=lambda: NOW)
    assert result["ok"] is False
    assert result["reason"] == pa.REASON_INSTANCE_RECORD_INVALID
    assert result["observed"] is False
