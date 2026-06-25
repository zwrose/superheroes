# plugins/superheroes/lib/tests/test_worker_recovery_cli.py
import json, os, subprocess, sys
CLI = os.path.join(os.path.dirname(__file__), "..", "worker_recovery_cli.py")


def test_cli_retry():
    out = subprocess.run([sys.executable, CLI, "--attempt", "1", "--signal", "needs_context"],
                         capture_output=True, text=True)
    assert json.loads(out.stdout)["action"] == "retry_with_context"


def test_cli_bad_attempt_parks():
    out = subprocess.run([sys.executable, CLI, "--attempt", "x", "--signal", "needs_context"],
                         capture_output=True, text=True)
    assert json.loads(out.stdout)["action"] == "park"
