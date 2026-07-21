import subprocess

import guardian_collect as gc
import pytest


def test_tool_available_false_for_missing():
    assert gc.tool_available("definitely-not-a-real-binary-xyz-558") is False


def test_status_builders():
    assert gc.collected() == {"status": "collected"}
    assert gc.partial("half") == {"status": "partial", "reason": "half"}
    assert gc.not_collected("nope") == {"status": "not-collected", "reason": "nope"}


def test_run_tool_success():
    def fake_run(argv, **kwargs):
        class R:
            returncode = 0
            stdout = "ok"
            stderr = ""
        return R()

    out = gc.run_tool(["tool"], ctx={"run": fake_run})
    assert out["ok"] is True
    assert out["exit"] == 0
    assert out["stdout"] == "ok"
    assert out["reason"] is None


def test_run_tool_nonzero_exit():
    def fake_run(argv, **kwargs):
        class R:
            returncode = 1
            stdout = ""
            stderr = "err"
        return R()

    out = gc.run_tool(["tool"], ctx={"run": fake_run})
    assert out["ok"] is False
    assert out["exit"] == 1
    assert "exited 1" in out["reason"]


def test_run_tool_ok_exits():
    def fake_run(argv, **kwargs):
        class R:
            returncode = 3
            stdout = "findings"
            stderr = ""
        return R()

    out = gc.run_tool(["vulture"], ctx={"run": fake_run}, ok_exits=(0, 3))
    assert out["ok"] is True
    assert out["exit"] == 3


def test_run_tool_timeout_never_raises():
    def fake_run(argv, **kwargs):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=5)

    out = gc.run_tool(["slow"], ctx={"run": fake_run}, timeout=5)
    assert out["ok"] is False
    assert out["reason"] == "slow timed out after 5s"


def test_run_tool_missing_never_raises():
    out = gc.run_tool(["definitely-not-a-real-binary-xyz-558"])
    assert out["ok"] is False
    assert out["reason"] == "definitely-not-a-real-binary-xyz-558 not available"


def test_run_tool_generic_exception_never_raises():
    def fake_run(argv, **kwargs):
        raise RuntimeError("boom")

    out = gc.run_tool(["tool"], ctx={"run": fake_run})
    assert out["ok"] is False
    assert out["reason"] == "tool failed: boom"
