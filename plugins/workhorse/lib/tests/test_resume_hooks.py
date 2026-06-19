# plugins/workhorse/lib/tests/test_resume_hooks.py
import json
import os
import subprocess
import sys

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "hooks")


def _run(script, payload, env):
    return subprocess.run([sys.executable, os.path.join(HOOKS, script)],
                          input=json.dumps(payload), capture_output=True, text=True, env=env)


def test_session_start_compact_emits_resume_context(tmp_path):
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    import control_plane as cp
    cp.set_current(str(tmp_path), "wi", root=str(tmp_path / "store"))
    r = _run("session_start.py", {"source": "compact", "cwd": str(tmp_path)}, env)
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert "re-arm" in json.dumps(out).lower() or "reconcile" in json.dumps(out).lower()


def test_session_start_noncompact_is_noop(tmp_path):
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    r = _run("session_start.py", {"source": "startup", "cwd": str(tmp_path)}, env)
    assert r.returncode == 0 and r.stdout.strip() == ""   # non-compact emits NOTHING


def test_precompact_is_nonfatal_without_state(tmp_path):
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    r = _run("precompact.py", {"cwd": str(tmp_path)}, env)
    assert r.returncode == 0          # never fails the session


def test_precompact_refreshes_brief_with_state(tmp_path):
    # The load-bearing success path: with a current work-item + checkpoint + events,
    # the hook actually writes resume-brief.md.
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    root = str(tmp_path / "store")
    env = dict(os.environ, WORKHORSE_STORE_ROOT=root)
    import control_plane as cp
    import checkpoint as ck
    import journal
    cp.set_current(str(tmp_path), "wi", root=root)
    p = cp.paths(str(tmp_path), "wi", root=root)
    ck.write(p["checkpoint"], ck.new("wi", "superheroes/wi-abc"))
    journal.append(p["events"], "run_started", root=str(tmp_path))
    r = _run("precompact.py", {"cwd": str(tmp_path)}, env)
    assert r.returncode == 0
    assert os.path.exists(p["resume_brief"])          # success path wrote the brief
    assert "# Workhorse resume brief" in open(p["resume_brief"]).read()
