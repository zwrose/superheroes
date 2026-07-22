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


# --- targets= (repo-file operands) ---------------------------------------------------
#
# run_tool grew an optional `targets=()` that threads repo-file operands to the tool
# behind a `--` separator. Production hands them to invoke (which absolutizes + validates
# under-repo + inserts `--`); the injected seam reproduces exactly the argv invoke would
# build so a test observes the real operands.


def test_run_tool_production_threads_targets_into_invoke(monkeypatch, tmp_path):
    """Production path (no ctx['run']) passes `targets` straight through to invoke —
    it does NOT append operands itself (invoke owns the `--` + absolutization)."""
    repo = _make_repo(tmp_path / "repo")
    captured = {}

    def fake_invoke(tool, fixed_args, repo_arg, targets, *, run=None, timeout=None,
                    **kwargs):
        captured["tool"] = tool
        captured["fixed_args"] = list(fixed_args)
        captured["repo"] = repo_arg
        captured["targets"] = list(targets)
        return {"outcome": "ok", "returncode": 0, "stdout": "out", "stderr": ""}

    monkeypatch.setattr(gc.gt, "invoke", fake_invoke)
    out = gc.run_tool(["jscpd", "-o", "x"], cwd=repo, targets=["a.py", "b.py"])
    assert out["ok"] is True
    assert captured["tool"] == "jscpd"
    assert captured["fixed_args"] == ["-o", "x"]
    assert captured["targets"] == ["a.py", "b.py"]
    assert os.path.realpath(captured["repo"]) == os.path.realpath(repo)


def test_run_tool_injected_seam_appends_separator_and_absolutized_operands(tmp_path):
    """Injected seam builds full_argv exactly as invoke would: argv + ['--'] + abs paths
    (absolutized under the repo)."""
    repo = _make_repo(tmp_path / "repo")
    (tmp_path / "repo" / "a.py").write_text("x\n", encoding="utf-8")
    (tmp_path / "repo" / "b.py").write_text("y\n", encoding="utf-8")
    seen = {}

    def run(argv, **kwargs):
        seen["argv"] = list(argv)

        class R:
            returncode = 0
            stdout = "ok"
            stderr = ""
        return R()

    out = gc.run_tool(["jscpd", "-o", "x"], ctx={"run": run}, cwd=repo,
                      targets=["a.py", "b.py"])
    assert out["ok"] is True
    repo_real = os.path.realpath(repo)
    assert seen["argv"] == [
        "jscpd", "-o", "x", "--",
        os.path.join(repo_real, "a.py"),
        os.path.join(repo_real, "b.py"),
    ]


def test_run_tool_injected_seam_empty_targets_argv_unchanged(tmp_path):
    """Empty targets ⇒ the argv the run stub sees is byte-for-byte the input argv."""
    repo = _make_repo(tmp_path / "repo")
    seen = {}

    def run(argv, **kwargs):
        seen["argv"] = list(argv)

        class R:
            returncode = 0
            stdout = "ok"
            stderr = ""
        return R()

    gc.run_tool(["jscpd", "-o", "x"], ctx={"run": run}, cwd=repo)
    assert seen["argv"] == ["jscpd", "-o", "x"]
    assert "--" not in seen["argv"]


def test_run_tool_injected_seam_escaping_symlink_target_degrades_never_raises(tmp_path):
    """A tracked symlink whose realpath escapes the repo makes absolute_repo_operands raise
    ValueError. run_tool must DEGRADE (not raise) on the injected seam, and must not call
    the run stub with an unsafe operand."""
    repo = _make_repo(tmp_path / "repo")
    outside = tmp_path / "outside.py"
    outside.write_text("secret\n", encoding="utf-8")
    link = tmp_path / "repo" / "escape.py"
    os.symlink(str(outside), str(link))
    # os.path.isfile follows the symlink → True, so such a path can survive a census filter.
    assert os.path.isfile(str(link))
    called = {"n": 0}

    def run(argv, **kwargs):
        called["n"] += 1

        class R:
            returncode = 0
            stdout = "ok"
            stderr = ""
        return R()

    out = gc.run_tool(["jscpd"], ctx={"run": run}, cwd=repo, targets=["escape.py"])
    assert out["ok"] is False
    assert "unsafe target operand" in out["reason"]
    assert called["n"] == 0, "the run stub must not be called with an unsafe operand"


def test_run_tool_empty_targets_matches_no_targets_arg(tmp_path):
    """Regression-safety: passing targets=() is byte-for-byte identical to omitting it."""
    def run(argv, **kwargs):
        class R:
            returncode = 0
            stdout = "ok"
            stderr = ""
        return R()

    a = gc.run_tool(["tool", "-x"], ctx={"run": run})
    b = gc.run_tool(["tool", "-x"], ctx={"run": run}, targets=())
    assert a == b
