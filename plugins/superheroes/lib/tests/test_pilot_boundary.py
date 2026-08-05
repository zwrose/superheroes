"""Tests for pilot_boundary.py — target boundary bindings and verdicts."""
import json
import os
import signal
import stat
import sys
import threading
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_boundary as pb  # noqa: E402
import pilot_slot  # noqa: E402


def _binding(**kwargs):
    defaults = {
        "slot_ref": "slot@1",
        "origin": "http://127.0.0.1:5173",
        "permitted_redirects": [],
        "protected_targets": ["example_prod"],
    }
    defaults.update(kwargs)
    return pb.target_binding(**defaults)


def _write_executable(path, content):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    os.chmod(path, stat.S_IMODE(os.stat(path).st_mode) | stat.S_IXUSR)


# --- store.SLOT_RE trailing newline (test_store.py absent) --------------------

def test_slot_re_refuses_trailing_newline():
    with pytest.raises(pilot_slot.PilotSlotError) as exc:
        pilot_slot.validate_slot_id("slot\n")
    assert exc.value.reason == pilot_slot.REFUSAL_SLOT_ID_INVALID


# --- parse_origin -------------------------------------------------------------

def test_parse_origin_idempotent():
    origin = "HTTP://HOST.EXAMPLE.COM:8080"
    once = pb.parse_origin(origin)
    twice = pb.parse_origin(once)
    assert once == "http://host.example.com:8080"
    assert twice == once


def test_parse_origin_ipv6_brackets():
    assert pb.parse_origin("http://[::1]:443") == "http://[::1]:443"


def test_parse_origin_refuses_port_zero():
    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.parse_origin("http://host.example.com:0")
    assert exc.value.reason == pb.REFUSAL_ORIGIN_INVALID


def test_parse_origin_refuses_port_65536():
    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.parse_origin("http://host.example.com:65536")
    assert exc.value.reason == pb.REFUSAL_ORIGIN_INVALID


def test_parse_origin_refuses_leading_zero_port():
    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.parse_origin("http://host.example.com:080")
    assert exc.value.reason == pb.REFUSAL_ORIGIN_INVALID


def test_parse_origin_refuses_no_port():
    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.parse_origin("http://localhost")
    assert exc.value.reason == pb.REFUSAL_ORIGIN_INVALID


def test_parse_origin_refuses_wildcard_host():
    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.parse_origin("http://*.example.com:443")
    assert exc.value.reason == pb.REFUSAL_ORIGIN_INVALID


def test_parse_origin_refuses_userinfo():
    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.parse_origin("http://user@host:443")
    assert exc.value.reason == pb.REFUSAL_ORIGIN_INVALID


def test_parse_origin_refuses_non_bracketed_host_with_colon():
    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.parse_origin("http://host:8080:9090")
    assert exc.value.reason == pb.REFUSAL_ORIGIN_INVALID


@pytest.mark.parametrize(
    "url",
    [
        "http://h:1/",
        "http://h:1?a",
        "http://h:1#f",
    ],
)
def test_parse_origin_refuses_path_query_fragment(url):
    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.parse_origin(url)
    assert exc.value.reason == pb.REFUSAL_ORIGIN_INVALID


# --- target_binding -----------------------------------------------------------

def test_target_binding_canonicalizes_slot_ref_and_redirects():
    binding = pb.target_binding(
        "slot-a@1",
        origin="http://127.0.0.1:5173",
        permitted_redirects=[
            "http://127.0.0.1:9000",
            "http://127.0.0.1:8080",
            "http://127.0.0.1:9000",
        ],
        protected_targets=["example_prod"],
    )
    assert binding["slotRef"] == "slot-a@1"
    assert binding["permittedRedirects"] == [
        "http://127.0.0.1:9000",
        "http://127.0.0.1:8080",
    ]


def test_target_binding_refuses_empty_protected_targets():
    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.target_binding(
            "slot@1",
            origin="http://127.0.0.1:5173",
            permitted_redirects=[],
            protected_targets=[],
        )
    assert exc.value.reason == pb.REFUSAL_PROTECTED_TARGETS_INVALID


def test_target_binding_refuses_portless_url_protected_target():
    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.target_binding(
            "slot@1",
            origin="http://127.0.0.1:5173",
            permitted_redirects=["https://login.example.com:443"],
            protected_targets=["https://login.example.com"],
        )
    assert exc.value.reason == pb.REFUSAL_PROTECTED_TARGETS_INVALID


def test_target_binding_opaque_protected_target_still_works():
    binding = pb.target_binding(
        "slot@1",
        origin="http://127.0.0.1:5173",
        permitted_redirects=[],
        protected_targets=["example_prod"],
    )
    assert binding["protectedTargets"] == ["example_prod"]


def test_check_redirect_refuses_protected_target_with_explicit_port():
    binding = pb.target_binding(
        "slot@1",
        origin="http://127.0.0.1:5173",
        permitted_redirects=["https://login.example.com:443"],
        protected_targets=["https://login.example.com:443"],
    )
    result = pb.check_redirect(binding, "https://login.example.com:443")
    assert result == {"ok": False, "reason": pb.REFUSAL_PROTECTED_TARGET}


def test_parse_origin_lowercases_ipv6_host():
    lower = pb.parse_origin("https://[::ffff:1]:443")
    upper = pb.parse_origin("https://[::FFFF:1]:443")
    assert lower == upper == "https://[::ffff:1]:443"


def test_check_redirect_refuses_protected_ipv6_case_variant():
    binding = pb.target_binding(
        "slot@1",
        origin="http://127.0.0.1:5173",
        permitted_redirects=["https://[::FFFF:1]:443"],
        protected_targets=["https://[::ffff:1]:443"],
    )
    result = pb.check_redirect(binding, "https://[::FFFF:1]:443")
    assert result == {"ok": False, "reason": pb.REFUSAL_PROTECTED_TARGET}


# --- check_target allowlist (T2) ----------------------------------------------

def test_check_target_accepts_bound_origin():
    origin = "http://127.0.0.1:5173"
    binding = _binding(origin=origin)
    result = pb.check_target(binding, origin)
    assert result == {"ok": True, "reason": None}


@pytest.mark.parametrize(
    "url",
    [
        "http://other.example.com:80",
        "http://127.0.0.1:8080",
        "https://127.0.0.1:5173",
    ],
)
def test_check_target_refuses_off_allowlist_origin(url):
    binding = _binding(origin="http://127.0.0.1:5173")
    result = pb.check_target(binding, url)
    assert result == {"ok": False, "reason": pb.REFUSAL_TARGET_OFF_ALLOWLIST}


def test_check_target_refuses_protected_bound_origin_first():
    origin = "http://127.0.0.1:5173"
    binding = _binding(origin=origin, protected_targets=[origin, "example_prod"])
    result = pb.check_target(binding, origin)
    assert result == {"ok": False, "reason": pb.REFUSAL_PROTECTED_TARGET}


def test_check_redirect_refuses_protected_permitted_redirect_first():
    redirect = "http://app.example.com:443"
    binding = _binding(
        origin="http://127.0.0.1:5173",
        permitted_redirects=[redirect],
        protected_targets=[redirect],
    )
    result = pb.check_redirect(binding, redirect)
    assert result == {"ok": False, "reason": pb.REFUSAL_PROTECTED_TARGET}


@pytest.mark.parametrize(
    "url",
    [None, 42, "not-an-origin", "http://missing-port"],
)
def test_check_target_never_raises_on_malformed_url(url):
    binding = _binding()
    result = pb.check_target(binding, url)
    assert result["ok"] is False
    assert result["reason"] == pb.REFUSAL_ORIGIN_INVALID


@pytest.mark.parametrize(
    "url",
    [None, 42, "not-an-origin", "http://missing-port"],
)
def test_check_redirect_never_raises_on_malformed_url(url):
    binding = _binding()
    result = pb.check_redirect(binding, url)
    assert result["ok"] is False
    assert result["reason"] == pb.REFUSAL_ORIGIN_INVALID


# --- check_protected_identity -------------------------------------------------

def test_check_protected_identity_refuses_protected_target():
    binding = _binding(protected_targets=["example_prod"])
    result = pb.check_protected_identity(binding, "example_prod")
    assert result == {"ok": False, "reason": pb.REFUSAL_PROTECTED_TARGET}


def test_check_protected_identity_passes_non_protected():
    binding = _binding(protected_targets=["example_prod"])
    result = pb.check_protected_identity(binding, "example_dev")
    assert result == {"ok": True, "reason": None}


# --- check_datastore_identity -------------------------------------------------

def _observation(identity, *, provenance="observed", strength="strong"):
    return {
        "identity": identity,
        "provenance": provenance,
        "strength": strength,
    }


@pytest.mark.parametrize("expected_identity", [None, "", 123])
def test_check_datastore_identity_refuses_unavailable_expected_identity(expected_identity):
    binding = _binding(protected_targets=["example_prod"])
    observation = _observation("example_dev")
    result = pb.check_datastore_identity(binding, observation, expected_identity)
    assert result == {
        "ok": False,
        "reason": pb.REFUSAL_DATASTORE_IDENTITY_UNAVAILABLE,
        "provenance": "observed",
        "strength": "strong",
        "match": False,
    }


def test_check_datastore_identity_protected_identity_precedes_unavailable_expected():
    binding = _binding(protected_targets=["example_prod"])
    observation = _observation(
        "example_prod",
        provenance="app-reported",
        strength="weaker",
    )
    result = pb.check_datastore_identity(binding, observation, None)
    assert result == {
        "ok": False,
        "reason": pb.REFUSAL_PROTECTED_TARGET,
        "provenance": "app-reported",
        "strength": "weaker",
        "match": False,
    }


# --- app_reported_identity ----------------------------------------------------

@pytest.mark.parametrize("value", [None, "", 123])
def test_app_reported_identity_refuses_unavailable(value):
    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.app_reported_identity(value)
    assert exc.value.reason == pb.REFUSAL_DATASTORE_IDENTITY_UNAVAILABLE


def test_app_reported_identity_records_weaker_provenance():
    result = pb.app_reported_identity("example_dev")
    assert result == {
        "identity": "example_dev",
        "provenance": "app-reported",
        "strength": "weaker",
        "weaker": True,
    }


# --- observe_datastore_identity ------------------------------------------------

def _observer_layout(private_tmp):
    reach_root = os.path.join(private_tmp, "reach")
    run_cwd = os.path.join(private_tmp, "cwd")
    bin_dir = os.path.join(private_tmp, "bin")
    os.makedirs(reach_root)
    os.makedirs(run_cwd)
    os.makedirs(bin_dir)
    return reach_root, run_cwd, bin_dir


def test_observe_datastore_identity_runs_observer_stdout(private_tmp):
    reach_root, run_cwd, bin_dir = _observer_layout(private_tmp)
    script = os.path.join(bin_dir, "observer.sh")
    _write_executable(
        script,
        "#!/bin/sh\n"
        "echo \"observed:${PILOT_DB_URL}\"\n",
    )
    connection = "postgres://localhost:5432/example_dev"
    observer = {
        "command": [script],
        "connectionEnvVar": "PILOT_DB_URL",
    }
    result = pb.observe_datastore_identity(
        observer,
        connection_detail=connection,
        reach_roots=[reach_root],
        run_cwd=run_cwd,
    )
    assert result == {
        "identity": "observed:" + connection,
        "provenance": "observed",
        "strength": "strong",
        "weaker": False,
    }


def test_observe_datastore_identity_child_env_has_only_connection_var(private_tmp):
    reach_root, run_cwd, bin_dir = _observer_layout(private_tmp)
    script = os.path.join(bin_dir, "path_check.sh")
    _write_executable(
        script,
        "#!/bin/sh\n"
        '/usr/bin/python3 -c "import os; print(\'PATH_SET\' if \'PATH\' in os.environ else \'PATH_UNSET\')"\n',
    )
    observer = {
        "command": [script],
        "connectionEnvVar": "PILOT_DB_URL",
    }
    result = pb.observe_datastore_identity(
        observer,
        connection_detail="postgres://localhost:5432/example_dev",
        reach_roots=[reach_root],
        run_cwd=run_cwd,
    )
    assert result["identity"] == "PATH_UNSET"


def test_observe_datastore_identity_refuses_nonzero_exit(private_tmp):
    # axis: the EXIT CODE is what refuses. The observer prints a perfectly good one-line identity
    # and then exits 1 — so with the exit-code check removed this call would succeed. It used to
    # print nothing, which meant the empty-stdout check refused first and the exit-code check was
    # never the discriminating one (#866, found by A/B probe during the bounded-runner extraction).
    reach_root, run_cwd, bin_dir = _observer_layout(private_tmp)
    script = os.path.join(bin_dir, "fail.sh")
    _write_executable(script, "#!/bin/sh\necho example_dev\nexit 1\n")
    observer = {"command": [script], "connectionEnvVar": "PILOT_DB_URL"}
    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.observe_datastore_identity(
            observer,
            connection_detail="postgres://localhost:5432/example_dev",
            reach_roots=[reach_root],
            run_cwd=run_cwd,
        )
    assert exc.value.reason == pb.REFUSAL_DATASTORE_OBSERVER_FAILED


_GRANDCHILD_OBSERVER_SCRIPT = """#!/usr/bin/env python3
import os
import subprocess
import sys
import time

pid_path = os.environ["PILOT_DB_URL"]
grandchild_code = (
    "import os, signal, sys, time\\n"
    "signal.signal(signal.SIGTERM, signal.SIG_IGN)\\n"
    "open(sys.argv[1], 'w').write(str(os.getpid()))\\n"
    "sys.stdout.flush()\\n"
    "time.sleep(120)\\n"
)
subprocess.Popen([sys.executable, "-c", grandchild_code, pid_path], stdout=sys.stdout)

# Wait for the grandchild to actually be observable before this parent exits, instead of exiting
# immediately and leaving the test to assume it started. Bounded so a stuck grandchild cannot hang
# the runner: if the deadline passes, exit anyway and let the test's own poll fail with its
# existing "grandchild never started" message, which is the correct signal in that case.
deadline = time.monotonic() + 20
while time.monotonic() < deadline:
    if os.path.isfile(pid_path):
        try:
            with open(pid_path) as f:
                if f.read().strip():
                    break
        except OSError:
            pass
    time.sleep(0.05)

os._exit(0)
"""


def test_observe_datastore_identity_timeout_reaps_process_group(private_tmp):
    # axis: process-group containment for the BOUNDARY caller specifically. The observer script
    # exits after forking a grandchild that inherits its stdout, ignores SIGTERM, and sleeps.
    # pilot_mint's own grandchild-timeout test cannot prove this for pilot_boundary — a review seat
    # showed that hardcoding `start_new_session=True` inside the shared runner (rather than
    # deriving it from a per-caller flag) left every existing boundary test green while the
    # observer path had no equivalent proof (#866). This test is that proof: only signalling the
    # observer's whole process group (not just the direct child) reaps the grandchild.
    #
    # Timing: `timeout_seconds=15` here is what the runner is bounded by, not what the test's
    # setup should be tuned to the edge of — setup (interpreter spawn twice + a file write) must
    # complete inside that timeout or the group gets killed before the grandchild ever proves it
    # started, failing the test at setup rather than at the containment assertion. Measured cold
    # start (5 trials, otherwise-idle machine) was `['1.895', '0.056', '0.046', '0.048', '0.051']`
    # seconds — the first, cold trial at ~1.9s, everything after warm. 15s is roughly 8x that
    # worst measured cold start. This test failed in CI once for exactly this reason at
    # `timeout_seconds=2` (#866, CI run 31002921349): "grandchild never started: pid file never
    # appeared" — a race against its own timeout, not a containment defect. The pid-file poll
    # deadline (20s) and `runner.join` timeout (40s) below are widened to match; the post-timeout
    # grandchild-death poll (3s) is untouched because the group is SIGKILLed before `run_bounded`
    # returns, so that poll never races the timeout the way setup did.
    reach_root, run_cwd, bin_dir = _observer_layout(private_tmp)
    pid_file = os.path.join(private_tmp, "grandchild.pid")
    script = os.path.join(bin_dir, "observer.py")
    _write_executable(script, _GRANDCHILD_OBSERVER_SCRIPT)
    observer = {"command": [script], "connectionEnvVar": "PILOT_DB_URL"}

    gpid = None
    outcome = {}

    def _run_observe():
        try:
            outcome["result"] = pb.observe_datastore_identity(
                observer,
                connection_detail=pid_file,
                reach_roots=[reach_root],
                run_cwd=run_cwd,
                timeout_seconds=15,
            )
        except pb.PilotBoundaryError as exc:
            outcome["error"] = exc

    try:
        runner = threading.Thread(target=_run_observe)
        runner.start()

        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            if os.path.isfile(pid_file):
                with open(pid_file) as f:
                    content = f.read().strip()
                if content:
                    gpid = int(content)
                    break
            time.sleep(0.02)
        else:
            pytest.fail("grandchild never started: pid file never appeared")

        runner.join(timeout=40)
        assert runner.is_alive() is False, "observe_datastore_identity did not finish"
        assert "error" in outcome, "observe_datastore_identity did not raise"
        assert outcome["error"].reason == pb.REFUSAL_DATASTORE_OBSERVER_FAILED

        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            try:
                os.kill(gpid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
        else:
            pytest.fail(
                "grandchild pid %d still alive after observer timeout reap" % gpid
            )
    finally:
        if gpid is not None:
            try:
                os.kill(gpid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if os.path.isfile(pid_file):
            os.remove(pid_file)


def test_path_containment_filesystem_root():
    assert pb._is_inside("/private/tmp/example", "/") is True


def test_is_outside_all_reach_roots_matches_private_helper(private_tmp):
    reach_root = os.path.join(private_tmp, "reach")
    inside = os.path.join(reach_root, "inside")
    outside = os.path.join(private_tmp, "outside")
    os.makedirs(inside)
    os.makedirs(outside)
    reach_roots = [reach_root]
    assert pb.is_outside_all_reach_roots(inside, reach_roots) is False
    assert pb._is_outside_all_reach_roots(inside, reach_roots) is False
    assert pb.is_outside_all_reach_roots(outside, reach_roots) is True
    assert pb._is_outside_all_reach_roots(outside, reach_roots) is True


# --- G1 empty reach_roots -----------------------------------------------------

def test_observe_datastore_identity_refuses_empty_reach_roots(private_tmp):
    reach_root, run_cwd, bin_dir = _observer_layout(private_tmp)
    script = os.path.join(bin_dir, "observer.sh")
    _write_executable(script, "#!/bin/sh\necho observed\n")
    observer = {"command": [script], "connectionEnvVar": "PILOT_DB_URL"}
    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.observe_datastore_identity(
            observer,
            connection_detail="postgres://localhost:5432/example_dev",
            reach_roots=[],
            run_cwd=run_cwd,
        )
    assert exc.value.reason == pb.REFUSAL_DATASTORE_OBSERVER_INVALID


def test_observe_datastore_identity_succeeds_with_nonempty_reach_roots(private_tmp):
    reach_root, run_cwd, bin_dir = _observer_layout(private_tmp)
    script = os.path.join(bin_dir, "observer.sh")
    _write_executable(script, "#!/bin/sh\necho observed\n")
    observer = {"command": [script], "connectionEnvVar": "PILOT_DB_URL"}
    result = pb.observe_datastore_identity(
        observer,
        connection_detail="postgres://localhost:5432/example_dev",
        reach_roots=[reach_root],
        run_cwd=run_cwd,
    )
    assert result["provenance"] == "observed"


# --- G3 argv confinement for non-existent paths ---------------------------------

def test_observe_datastore_identity_refuses_nonexistent_argv_inside_reach(private_tmp):
    reach_root, run_cwd, bin_dir = _observer_layout(private_tmp)
    script = os.path.join(bin_dir, "observer.sh")
    _write_executable(script, "#!/bin/sh\necho ok\n")
    missing_inside = os.path.join(reach_root, "not-created-yet.sql")
    observer = {"command": [script, missing_inside], "connectionEnvVar": "PILOT_DB_URL"}
    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.observe_datastore_identity(
            observer,
            connection_detail="postgres://localhost:5432/example_dev",
            reach_roots=[reach_root],
            run_cwd=run_cwd,
        )
    assert exc.value.reason == pb.REFUSAL_DATASTORE_OBSERVER_INVALID


def test_observe_datastore_identity_accepts_nonexistent_argv_outside_reach(private_tmp):
    reach_root, run_cwd, bin_dir = _observer_layout(private_tmp)
    script = os.path.join(bin_dir, "observer.sh")
    _write_executable(script, "#!/bin/sh\necho ok\n")
    missing_outside = os.path.join(private_tmp, "outside", "not-created-yet.sql")
    observer = {"command": [script, missing_outside], "connectionEnvVar": "PILOT_DB_URL"}
    result = pb.observe_datastore_identity(
        observer,
        connection_detail="postgres://localhost:5432/example_dev",
        reach_roots=[reach_root],
        run_cwd=run_cwd,
    )
    assert result["identity"] == "ok"


# --- G5 observer executable owner/mode ----------------------------------------

@pytest.mark.skipif(os.getuid() == 0, reason="mode/owner checks do not bite as root")
def test_observe_datastore_identity_refuses_group_writable_observer(private_tmp):
    reach_root, run_cwd, bin_dir = _observer_layout(private_tmp)
    script = os.path.join(bin_dir, "writable.sh")
    _write_executable(script, "#!/bin/sh\necho ok\n")
    os.chmod(script, 0o775)
    observer = {"command": [script], "connectionEnvVar": "PILOT_DB_URL"}
    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.observe_datastore_identity(
            observer,
            connection_detail="postgres://localhost:5432/example_dev",
            reach_roots=[reach_root],
            run_cwd=run_cwd,
        )
    assert exc.value.reason == pb.REFUSAL_DATASTORE_OBSERVER_INVALID


@pytest.mark.skipif(os.getuid() == 0, reason="mode/owner checks do not bite as root")
def test_observe_datastore_identity_accepts_secure_observer(private_tmp):
    reach_root, run_cwd, bin_dir = _observer_layout(private_tmp)
    script = os.path.join(bin_dir, "secure.sh")
    _write_executable(script, "#!/bin/sh\necho ok\n")
    os.chmod(script, 0o755)
    observer = {"command": [script], "connectionEnvVar": "PILOT_DB_URL"}
    result = pb.observe_datastore_identity(
        observer,
        connection_detail="postgres://localhost:5432/example_dev",
        reach_roots=[reach_root],
        run_cwd=run_cwd,
    )
    assert result["identity"] == "ok"


# --- T1 symlink-free temp base ------------------------------------------------

def test_tmp_base_has_no_symlinked_ancestor(tmp_base, path_has_symlinked_ancestor):
    assert not path_has_symlinked_ancestor(tmp_base)


# --- T5 observer failure discrimination ---------------------------------------

def test_observe_datastore_identity_refuses_oversized_output(private_tmp):
    reach_root, run_cwd, bin_dir = _observer_layout(private_tmp)
    script = os.path.join(bin_dir, "huge.sh")
    _write_executable(
        script,
        "#!/bin/sh\n"
        "/usr/bin/python3 -c \"import sys; sys.stdout.write('x' * 20000)\"\n",
    )
    observer = {"command": [script], "connectionEnvVar": "PILOT_DB_URL"}
    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.observe_datastore_identity(
            observer,
            connection_detail="postgres://localhost:5432/example_dev",
            reach_roots=[reach_root],
            run_cwd=run_cwd,
            max_output_bytes=1024,
        )
    assert exc.value.reason == pb.REFUSAL_DATASTORE_OBSERVER_FAILED


def test_observe_datastore_identity_oversized_output_bites_on_byte_cap(private_tmp):
    reach_root, run_cwd, bin_dir = _observer_layout(private_tmp)
    script = os.path.join(bin_dir, "huge.sh")
    _write_executable(
        script,
        "#!/bin/sh\n"
        "/usr/bin/python3 -c \"import sys; sys.stdout.write('x' * 20000)\"\n",
    )
    observer = {"command": [script], "connectionEnvVar": "PILOT_DB_URL"}
    with pytest.raises(pb.PilotBoundaryError):
        pb.observe_datastore_identity(
            observer,
            connection_detail="postgres://localhost:5432/example_dev",
            reach_roots=[reach_root],
            run_cwd=run_cwd,
            max_output_bytes=1024,
        )
    result = pb.observe_datastore_identity(
        observer,
        connection_detail="postgres://localhost:5432/example_dev",
        reach_roots=[reach_root],
        run_cwd=run_cwd,
        max_output_bytes=100000,
    )
    assert result["identity"].startswith("x")


def test_observe_datastore_identity_timeout_bites_on_timeout_seconds(private_tmp):
    reach_root, run_cwd, bin_dir = _observer_layout(private_tmp)
    script = os.path.join(bin_dir, "sleep.sh")
    _write_executable(script, "#!/bin/sh\n/bin/sleep 3\necho slept\n")
    observer = {"command": [script], "connectionEnvVar": "PILOT_DB_URL"}
    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.observe_datastore_identity(
            observer,
            connection_detail="postgres://localhost:5432/example_dev",
            reach_roots=[reach_root],
            run_cwd=run_cwd,
            timeout_seconds=1,
        )
    assert exc.value.reason == pb.REFUSAL_DATASTORE_OBSERVER_FAILED
    result = pb.observe_datastore_identity(
        observer,
        connection_detail="postgres://localhost:5432/example_dev",
        reach_roots=[reach_root],
        run_cwd=run_cwd,
        timeout_seconds=10,
    )
    assert result["identity"] == "slept"


def test_observe_datastore_identity_refuses_empty_stdout(private_tmp):
    reach_root, run_cwd, bin_dir = _observer_layout(private_tmp)
    script = os.path.join(bin_dir, "empty.sh")
    _write_executable(script, "#!/bin/sh\n")
    observer = {"command": [script], "connectionEnvVar": "PILOT_DB_URL"}
    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.observe_datastore_identity(
            observer,
            connection_detail="postgres://localhost:5432/example_dev",
            reach_roots=[reach_root],
            run_cwd=run_cwd,
        )
    assert exc.value.reason == pb.REFUSAL_DATASTORE_OBSERVER_FAILED


def test_observe_datastore_identity_refuses_command_inside_reach_root(private_tmp):
    reach_root, run_cwd, _ = _observer_layout(private_tmp)
    script = os.path.join(reach_root, "inside.sh")
    _write_executable(script, "#!/bin/sh\necho inside\n")
    observer = {"command": [script], "connectionEnvVar": "PILOT_DB_URL"}
    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.observe_datastore_identity(
            observer,
            connection_detail="postgres://localhost:5432/example_dev",
            reach_roots=[reach_root],
            run_cwd=run_cwd,
        )
    assert exc.value.reason == pb.REFUSAL_DATASTORE_OBSERVER_INVALID


def test_path_containment_not_string_prefix(private_tmp):
    reach_a_b = os.path.join(private_tmp, "a", "b")
    reach_a_bc = os.path.join(private_tmp, "a", "bc")
    os.makedirs(reach_a_b)
    os.makedirs(reach_a_bc)
    script = os.path.join(reach_a_bc, "observer.sh")
    _write_executable(script, "#!/bin/sh\necho ok\n")
    run_cwd = os.path.join(private_tmp, "outside-cwd")
    os.makedirs(run_cwd)
    observer = {"command": [script], "connectionEnvVar": "PILOT_DB_URL"}
    result = pb.observe_datastore_identity(
        observer,
        connection_detail="postgres://localhost:5432/example_dev",
        reach_roots=[reach_a_b],
        run_cwd=run_cwd,
    )
    assert result["identity"] == "ok"


# --- boundary_verdict ---------------------------------------------------------

def test_boundary_verdict_carries_no_policy_values():
    distinctive_origin = "http://distinctive-host.example:5999"
    distinctive_identity = "distinctive_datastore_identity_token"
    binding = pb.target_binding(
        "slot@1",
        origin=distinctive_origin,
        permitted_redirects=[],
        protected_targets=[distinctive_identity],
    )
    checks = [
        ("target-binding", {"ok": True, "reason": None}),
        (
            "datastore-identity",
            {
                "ok": True,
                "reason": None,
                "provenance": "observed",
                "strength": "strong",
                "match": True,
            },
        ),
    ]
    identity_check = {
        "ok": True,
        "reason": None,
        "provenance": "observed",
        "strength": "strong",
        "match": True,
    }
    verdict = pb.boundary_verdict(
        binding,
        checks=checks,
        policy_digest="distinctive-policy-digest-value",
        datastore_identity=identity_check,
        verified_at="2026-01-01T00:00:00Z",
    )
    serialized = json.dumps(verdict)
    for leaked in (
        distinctive_origin,
        "distinctive-host.example",
        distinctive_identity,
    ):
        assert leaked not in serialized


# --- authorize_credentials ----------------------------------------------------

def _passing_verdict_dict(slot_ref="slot@1", policy_digest="digest-abc"):
    return {
        "schemaVersion": pb.BOUNDARY_SCHEMA_VERSION,
        "slotRef": slot_ref,
        "result": "pass",
        "reason": None,
        "checks": [
            {"check": "target-binding", "result": "pass", "reason": None},
            {"check": "datastore-identity", "result": "pass", "reason": None},
        ],
        "datastoreIdentity": None,
        "policyDigest": policy_digest,
        "verifiedAt": "2026-01-01T00:00:00Z",
    }


def _passing_verdict(slot_ref="slot@1", policy_digest="digest-abc"):
    binding = _binding(slot_ref=slot_ref)
    checks = [
        ("target-binding", {"ok": True, "reason": None}),
        (
            "datastore-identity",
            {
                "ok": True,
                "reason": None,
                "provenance": "observed",
                "strength": "strong",
                "match": True,
            },
        ),
    ]
    return pb.boundary_verdict(binding, checks=checks, policy_digest=policy_digest)


def test_authorize_credentials_refuses_refuse_verdict():
    verdict = _passing_verdict()
    verdict["result"] = "refuse"
    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.authorize_credentials(verdict, "slot@1", "digest-abc")
    assert exc.value.reason == pb.REFUSAL_UNVERIFIED


def test_authorize_credentials_refuses_wrong_slot_ref():
    verdict = _passing_verdict(slot_ref="slot@1")
    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.authorize_credentials(verdict, "slot@2", "digest-abc")
    assert exc.value.reason == pb.REFUSAL_UNVERIFIED


def test_authorize_credentials_refuses_policy_digest_mismatch():
    verdict = _passing_verdict(policy_digest="digest-abc")
    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.authorize_credentials(verdict, "slot@1", "other-digest")
    assert exc.value.reason == pb.REFUSAL_UNVERIFIED


def test_authorize_credentials_refuses_schema_version_true():
    verdict = _passing_verdict()
    verdict["schemaVersion"] = True
    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.authorize_credentials(verdict, "slot@1", "digest-abc")
    assert exc.value.reason == pb.REFUSAL_UNVERIFIED


def test_authorize_credentials_success():
    verdict = _passing_verdict()
    result = pb.authorize_credentials(verdict, "slot@1", "digest-abc")
    assert result == {
        "slotRef": "slot@1",
        "policyDigest": "digest-abc",
        "authorized": True,
    }


@pytest.mark.parametrize(
    "checks",
    [
        [],
        [{"check": "datastore-identity", "result": "pass", "reason": None}],
        [{"check": "target-binding", "result": "pass", "reason": None}],
        [
            {"check": "target-binding", "result": "pass", "reason": None},
            {"check": "datastore-identity", "result": "refuse", "reason": "x"},
        ],
    ],
)
def test_authorize_credentials_refuses_vacuous_or_forged_checks(checks):
    verdict = _passing_verdict_dict()
    verdict["checks"] = checks
    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.authorize_credentials(verdict, "slot@1", "digest-abc")
    assert exc.value.reason == pb.REFUSAL_UNVERIFIED


def test_boundary_verdict_refuses_empty_checks():
    binding = _binding()
    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.boundary_verdict(binding, checks=[], policy_digest="digest")
    assert exc.value.reason == pb.REFUSAL_VERDICT_VACUOUS


def test_boundary_verdict_refuses_missing_mandatory_check():
    binding = _binding()
    checks = [("target-binding", {"ok": True, "reason": None})]
    with pytest.raises(pb.PilotBoundaryError) as exc:
        pb.boundary_verdict(binding, checks=checks, policy_digest="digest")
    assert exc.value.reason == pb.REFUSAL_VERDICT_VACUOUS
