# plugins/superheroes/lib/tests/test_fence_cli.py
import json, os, subprocess, sys
CLI = os.path.join(os.path.dirname(__file__), "..", "fence_cli.py")


def test_cli_bad_generation_fails_closed(tmp_path):
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    out = subprocess.run([sys.executable, CLI, "--work-item", "wi", "--generation", "x"],
                         cwd=str(tmp_path), env=env, capture_output=True, text=True)
    assert json.loads(out.stdout)["ok"] is False
