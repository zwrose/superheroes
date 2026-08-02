"""Tests for pilot per-slot app instance control."""
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


def _now_seq():
    seq = [NOW, LATER, "2026-01-01T00:00:02Z", "2026-01-01T00:00:03Z"]

    def fn():
        if seq:
            return seq.pop(0)
        return "2026-01-01T00:00:99Z"

    return fn


@pytest.fixture(autouse=True)
def _app_lifecycle_kind(monkeypatch):
    monkeypatch.setattr(
        pc,
        "DECLARATION_KINDS",
        pc.DECLARATION_KINDS | {"app-lifecycle"},
    )


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


def test_stand_up_readiness_timeout_indeterminate():
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

        script = (
            "import sys\n"
            "sys.stderr.write('EADDRINUSE\\n')\n"
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
                [sys.executable, "-c", script],
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            ),
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
    proc = subprocess.Popen(
        ["sleep", "120"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    pgid = os.getpgid(proc.pid)
    inst = {
        "schemaVersion": 1,
        "slot": SLOT,
        "slotRef": SLOT_REF,
        "state": pa.STATE_READY,
        "pid": proc.pid,
        "pgid": pgid,
        "launchNonce": "a" * 32,
        "cwd": os.path.realpath(tempfile.gettempdir()),
        "allocation": _allocation(port),
        "command": ["sleep", "120"],
        "readinessUrl": f"http://127.0.0.1:{port}/",
        "readinessAttribution": "nonce",
        "startedAt": NOW,
        "updatedAt": NOW,
        "stopReceipt": None,
    }
    return proc, None, inst


def test_stop_uncorroborated_no_signal():
    inst = {
        "schemaVersion": 1,
        "slot": SLOT,
        "slotRef": SLOT_REF,
        "state": pa.STATE_READY,
        "pid": 999999,
        "pgid": 999999,
        "launchNonce": "b" * 32,
        "cwd": "/tmp",
        "allocation": _allocation(1),
        "command": ["/no/such/binary"],
        "readinessUrl": "http://127.0.0.1:1/",
        "readinessAttribution": "nonce",
        "startedAt": NOW,
        "updatedAt": NOW,
        "stopReceipt": None,
    }
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
    inst = {
        "schemaVersion": 1,
        "slot": SLOT,
        "slotRef": SLOT_REF,
        "state": pa.STATE_READY,
        "pid": 1,
        "pgid": 1,
        "launchNonce": "c" * 32,
        "cwd": "/tmp",
        "allocation": _allocation(port),
        "command": ["echo"],
        "readinessUrl": f"http://127.0.0.1:{port}/",
        "readinessAttribution": "nonce",
        "startedAt": NOW,
        "updatedAt": NOW,
        "stopReceipt": None,
    }
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
    inst = {
        "schemaVersion": 1,
        "slot": SLOT,
        "slotRef": SLOT_REF,
        "state": pa.STATE_STOPPED,
        "pid": 0,
        "pgid": 0,
        "launchNonce": "d" * 32,
        "cwd": "/tmp",
        "allocation": _allocation(1),
        "command": ["echo"],
        "readinessUrl": "http://127.0.0.1:1/",
        "readinessAttribution": "nonce",
        "startedAt": NOW,
        "updatedAt": NOW,
        "stopReceipt": {
            "step": "app-instance",
            "slotRef": SLOT_REF,
            "observedAt": NOW,
            "evidence": "already stopped",
        },
    }
    r = pa.stop(inst, now_fn=lambda: NOW)
    assert r["ok"] and r["observed"]


# real-default integration tests (no custom pytest mark — repo has no pytest config)
def test_real_default_spawn_process_group():
    proc = None
    inst = None
    tmp = _tmp_dir()
    try:
        proc = pa._default_spawn(["sleep", "120"], cwd=tmp, env={})
        pgid = os.getpgid(proc.pid)
        assert pgid != os.getpgid(os.getpid())
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        inst = {
            "schemaVersion": 1,
            "slot": SLOT,
            "slotRef": SLOT_REF,
            "state": pa.STATE_READY,
            "pid": proc.pid,
            "pgid": pgid,
            "launchNonce": "a" * 32,
            "cwd": tmp,
            "allocation": _allocation(port),
            "command": ["sleep", "120"],
            "readinessUrl": f"http://127.0.0.1:{port}/",
            "readinessAttribution": "nonce",
            "startedAt": NOW,
            "updatedAt": NOW,
            "stopReceipt": None,
        }
        r = pa.stop(inst, now_fn=lambda: NOW)
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
    try:
        proc, _, inst = _running_instance()
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
