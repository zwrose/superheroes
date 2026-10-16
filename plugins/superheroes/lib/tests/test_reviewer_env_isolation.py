import os
import subprocess
import sys

from test_session_start_hook import _pass_fixture

_HERE = os.path.dirname(os.path.abspath(__file__))


def test_ambient_cloud_pass_never_reaches_the_real_home_through_the_hook(tmp_path):
    # Axis: a hook test outside test_session_start_hook.py, run with a cloud session and a valid
    # pass ambient in the process environment, must write nothing under HOME (the shared conftest
    # fixture removes the variables). Fails without that fixture: the hook places the sign-in.
    home = tmp_path / "ambient-home"
    home.mkdir()
    pass_value, _, _ = _pass_fixture()
    env = dict(os.environ, HOME=str(home), CLAUDE_CODE_REMOTE="true",
               SUPERHEROES_REVIEWER_PASS=pass_value)
    env.pop("CODEX_HOME", None)
    proc = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "-q", "-n", "0", "-p", "no:cacheprovider",
         os.path.join(_HERE, "test_cache_markers.py")
         + "::test_session_start_hook_invokes_sweep_stale"],
        env=env, capture_output=True, text=True, check=False, cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert list(home.rglob("*")) == []
