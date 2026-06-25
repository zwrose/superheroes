import importlib.util
import os
import subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load():
    path = os.path.join(_HERE, "..", "verify_gate.py")
    spec = importlib.util.spec_from_file_location("verify_gate", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


VG = _load()


class _Proc:
    def __init__(self, rc, out="", err=""):
        self.returncode, self.stdout, self.stderr = rc, out, err


def test_pass_when_command_exits_zero():
    res = VG.run_verify("pytest", runner=lambda *a, **k: _Proc(0, "ok"))
    assert res["result"] == "pass" and res["code"] == 0


def test_fail_when_command_exits_nonzero():
    res = VG.run_verify("pytest", runner=lambda *a, **k: _Proc(1, "boom"))
    assert res["result"] == "fail" and res["code"] == 1 and "boom" in res["tail"]


def test_timeout_is_distinct_from_fail():
    def _raise(*a, **k):
        raise subprocess.TimeoutExpired(cmd="pytest", timeout=1, output="partial")
    res = VG.run_verify("pytest", timeout=1, runner=_raise)
    assert res["result"] == "timeout" and res["code"] is None and "partial" in res["tail"]


def test_none_command_is_skipped():
    assert VG.run_verify("none")["result"] == "skipped"
    assert VG.run_verify("")["result"] == "skipped"


def test_execution_error_fails_closed():
    def _raise(*a, **k):
        raise OSError("no such command")
    res = VG.run_verify("pytest", runner=_raise)
    assert res["result"] == "fail"  # never silently passes
