import os
import stat
import subprocess
import sys

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
    # Production path (no ctx["run"]) now routes through guardian_tools.invoke, so an
    # absent tool degrades with missing_tool_reason's shape. Assert the tool is named
    # and the PATH phrasing is present without pinning the whole string brittlely.
    tool = "definitely-not-a-real-binary-xyz-558"
    out = gc.run_tool([tool])
    assert out["ok"] is False
    assert tool in out["reason"]
    assert "not found on PATH" in out["reason"]


def test_run_tool_generic_exception_never_raises():
    def fake_run(argv, **kwargs):
        raise RuntimeError("boom")

    out = gc.run_tool(["tool"], ctx={"run": fake_run})
    assert out["ok"] is False
    assert out["reason"] == "tool failed: boom"


# --- production path (ctx["run"] is None) routes through guardian_tools.invoke -----
#
# These drive run_tool with NO injected run, planting REAL tiny executables the way
# test_guardian_tools.py does (never mocking invoke), to prove the hardening composes.

_MARKER = "GUARDIAN_COLLECT_RCE_MARKER"


def _make_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    (path / ".git").mkdir()
    return str(path)


def _write_executable(path, body):
    path = str(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    return path


def test_run_tool_production_rejects_repo_local_binary(tmp_path, monkeypatch):
    """A repo-local executable on PATH is REJECTED and never executed."""
    repo = _make_repo(tmp_path / "repo")
    marker = os.path.join(repo, _MARKER)
    tool = "guardian-collect-repo-local"
    binp = _write_executable(
        tmp_path / "repo" / "bin" / tool,
        "#!%s\nopen(%r, 'w').write('x')\n" % (sys.executable, marker))
    monkeypatch.setenv("PATH", os.path.dirname(binp))

    out = gc.run_tool([tool], cwd=repo)

    assert out["ok"] is False
    assert "repo-local executable ignored" in out["reason"]
    # The planted binary must NOT have run — its side-effect file must not exist.
    assert not os.path.exists(marker)
    assert os.path.isfile(binp)


def test_run_tool_production_findings_on_success_exit_three(tmp_path, monkeypatch):
    """An external tool exiting rc=3 with stdout is ok under ok_exits=(0, 3)."""
    repo = _make_repo(tmp_path / "repo")
    tool = "guardian-collect-findings-three"
    binp = _write_executable(
        tmp_path / "toolbox" / tool,
        "#!%s\nimport sys\nsys.stdout.write('findings\\n')\nsys.exit(3)\n"
        % sys.executable)
    monkeypatch.setenv("PATH", os.path.dirname(binp))

    out = gc.run_tool([tool], cwd=repo, ok_exits=(0, 3))

    assert out["ok"] is True
    assert out["exit"] == 3
    assert "findings" in out["stdout"]
    assert out["reason"] is None


def test_run_tool_production_missing_tool_never_raises(tmp_path):
    """A genuinely-absent tool degrades (never raises) on the production path."""
    repo = _make_repo(tmp_path / "repo")
    tool = "definitely-not-a-real-binary-xyz-561"
    out = gc.run_tool([tool], cwd=repo)
    assert out["ok"] is False
    assert tool in out["reason"]
    assert "not found on PATH" in out["reason"]


# --- _translate_invoke_result: the fail-closed safety branches -----------------------
#
# These map invoke's result-dict directly, exercising the branches that a planted real
# binary cannot reach (truncated-output / capture-incomplete / an unknown outcome, plus
# the ok/ok_exits gate). Direct mapper unit tests are the right seam for those.

_ARGV = ["some-tool", "--flag"]


def test_translate_truncated_output_fails_even_when_returncode_in_ok_exits():
    res = {"outcome": "truncated-output", "returncode": 3, "stdout": "x", "stderr": ""}
    out = gc._translate_invoke_result(res, _ARGV, ok_exits=(0, 3))
    assert out["ok"] is False
    assert "some-tool" in out["reason"]


def test_translate_capture_incomplete_fails_even_when_returncode_in_ok_exits():
    res = {"outcome": "capture-incomplete", "returncode": 0, "stdout": "", "stderr": ""}
    out = gc._translate_invoke_result(res, _ARGV, ok_exits=(0,))
    assert out["ok"] is False
    assert "some-tool" in out["reason"]


def test_translate_unknown_outcome_fails_closed():
    res = {"outcome": "weird-new-outcome", "returncode": 0, "stdout": "", "stderr": ""}
    out = gc._translate_invoke_result(res, _ARGV, ok_exits=(0,))
    assert out["ok"] is False
    assert "unexpected invoke outcome" in out["reason"]


def test_translate_ok_outcome_gated_on_ok_exits():
    # rc=0 but 0 is NOT in ok_exits — the "ok" outcome must still read ok=False.
    res = {"outcome": "ok", "returncode": 0, "stdout": "out", "stderr": ""}
    out = gc._translate_invoke_result(res, _ARGV, ok_exits=(3,))
    assert out["ok"] is False
    assert "exited 0" in out["reason"]
    # normal case: rc=0 with 0 in ok_exits reads ok=True.
    ok = gc._translate_invoke_result(res, _ARGV, ok_exits=(0,))
    assert ok["ok"] is True
    assert ok["reason"] is None
