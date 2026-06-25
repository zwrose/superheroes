# plugins/superheroes/lib/tests/test_minor_rollup_cli.py
import json, os, subprocess, sys
CLI = os.path.join(os.path.dirname(__file__), "..", "minor_rollup_cli.py")


def test_cli_append_then_read(tmp_path, monkeypatch):
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    out = subprocess.run([sys.executable, CLI, "--work-item", "wi",
                          "--append", '[{"file":"a.py","title":"n","severity":"Minor"}]'],
                         cwd=str(tmp_path), env=env, capture_output=True, text=True)
    assert len(json.loads(out.stdout)["minors"]) == 1
