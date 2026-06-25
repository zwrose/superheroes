# plugins/superheroes/lib/tests/test_task_review_cli.py
import json, os, subprocess, sys
CLI = os.path.join(os.path.dirname(__file__), "..", "task_review_cli.py")


def _run(args):
    return subprocess.run([sys.executable, CLI, *args], capture_output=True, text=True)


def test_cli_clean_completes():
    out = _run(["--verdicts", '{"spec_compliance":"pass","code_quality":"pass"}',
                "--findings", "[]", "--round", "1", "--max-rounds", "3", "--history", "[]"])
    assert json.loads(out.stdout)["action"] == "complete"


def test_cli_bad_json_parks():
    out = _run(["--verdicts", "{bad", "--findings", "[]", "--round", "1",
                "--max-rounds", "3", "--history", "[]"])
    assert json.loads(out.stdout)["action"] == "park"
