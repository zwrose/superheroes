# plugins/superheroes/lib/tests/test_task_list_cli.py
import json, os, subprocess, sys
HERE = os.path.dirname(__file__)
CLI = os.path.join(HERE, "..", "task_list_cli.py")


def test_cli_emits_tasks_json_for_missing_doc(tmp_path):
    # No tasks doc under tmp_path -> fail-closed empty list, exit 0.
    out = subprocess.run([sys.executable, CLI, "--work-item", "does-not-exist"],
                         cwd=str(tmp_path), capture_output=True, text=True)
    assert out.returncode == 0
    assert json.loads(out.stdout) == {"tasks": []}
