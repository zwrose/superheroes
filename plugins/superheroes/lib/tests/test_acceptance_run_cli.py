# plugins/superheroes/lib/tests/test_acceptance_run_cli.py
#
# Task 13 DoD guard: the live-run command the acceptance SKILL.md documents
# (`python3 "$LIB/acceptance_run.py" --fixture <fixture> --root <root>`) must be a
# REAL, honest entrypoint. Before this task it silently no-opped (no `__main__`
# block) — running the documented command exited 0 with no verdict, no record, and
# no report, so a "live acceptance run" produced nothing while appearing to succeed.
#
# These tests pin the entrypoint's contract without spawning a live showrunner:
#   - the documented command NEVER silently succeeds (no bare exit-0-with-no-output);
#   - the execution-context marker (UFR-5) makes it refuse to nest.
import os
import subprocess
import sys

HERE = os.path.dirname(__file__)
RUN_PY = os.path.normpath(os.path.join(HERE, "..", "acceptance_run.py"))
FIXTURE = os.path.normpath(
    os.path.join(HERE, "..", "..", "eval", "fixtures", "acceptance")
)
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))


def _invoke(env_extra=None):
    env = dict(os.environ)
    # Never let a surrounding acceptance/showrunner context leak into the top-level cases.
    env.pop("SUPERHEROES_ACCEPTANCE_CONTEXT", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, RUN_PY, "--fixture", FIXTURE, "--root", ROOT],
        capture_output=True,
        text=True,
        env=env,
    )


def test_documented_command_is_a_real_entrypoint_not_a_silent_noop():
    """The SKILL.md DoD command must not silently exit 0 with no output."""
    proc = _invoke()
    combined = (proc.stdout or "") + (proc.stderr or "")
    # The bug this task fixes: exit 0 AND no output == a silent no-op live run.
    silent_success = proc.returncode == 0 and combined.strip() == ""
    assert not silent_success, (
        "acceptance_run.py ran as the documented DoD command but produced a silent "
        "exit-0 no-op (no verdict / record / report); a live run must never silently "
        "succeed with no effect"
    )


def test_documented_command_refuses_to_nest(tmp_path):
    """UFR-5: with the execution-context marker set the entrypoint refuses (non-zero)."""
    proc = _invoke({"SUPERHEROES_ACCEPTANCE_CONTEXT": "1"})
    combined = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode != 0
    assert "nest" in combined.lower()
