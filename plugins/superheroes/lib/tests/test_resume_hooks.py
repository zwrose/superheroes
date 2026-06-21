# plugins/superheroes/lib/tests/test_resume_hooks.py
import json
import os
import subprocess
import sys

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "hooks")


def _run(script, payload, env):
    return subprocess.run([sys.executable, os.path.join(HOOKS, script)],
                          input=json.dumps(payload), capture_output=True, text=True, env=env)


def _ctx(r):
    """The emitted additionalContext string (empty when nothing was emitted)."""
    if not r.stdout.strip():
        return ""
    return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]


def _git_repo_with_claude(tmp_path, sentinel):
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    (tmp_path / "CLAUDE.md").write_text("# Project rules\n%s\n" % sentinel)


def test_session_start_startup_emits_bootstrap(tmp_path):
    # The contract this change introduces: a slash-command spawn (source=startup)
    # now gets the project-context bootstrap, NOT nothing. (Replaces the old
    # noncompact-is-noop contract.)
    _git_repo_with_claude(tmp_path, "STARTUP_SENTINEL")
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    r = _run("session_start.py", {"source": "startup", "cwd": str(tmp_path)}, env)
    assert r.returncode == 0
    ctx = _ctx(r)
    assert "Superheroes session bootstrap" in ctx        # the bootstrap block
    assert "Resolved plugin roots" in ctx                # host-map fix is injected
    assert "STARTUP_SENTINEL" in ctx                     # project CLAUDE.md parity
    assert "reconcile" not in ctx.lower()                # no resume-brief on startup
    assert len(ctx) < 10000                              # conservative size margin


def test_session_start_resume_and_clear_emit_bootstrap(tmp_path):
    _git_repo_with_claude(tmp_path, "RC_SENTINEL")
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    for source in ("resume", "clear"):
        r = _run("session_start.py", {"source": source, "cwd": str(tmp_path)}, env)
        assert r.returncode == 0
        assert "Superheroes session bootstrap" in _ctx(r), source


def test_session_start_compact_with_workitem_emits_both(tmp_path):
    # compact WITH a work-item: bootstrap (always-on) AND the resume-brief (additive)
    # arrive in one additionalContext — the brief layers in, it is not dropped.
    _git_repo_with_claude(tmp_path, "COMPACT_SENTINEL")
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    import control_plane as cp
    cp.set_current(str(tmp_path), "wi", root=str(tmp_path / "store"))
    r = _run("session_start.py", {"source": "compact", "cwd": str(tmp_path)}, env)
    assert r.returncode == 0
    ctx = _ctx(r).lower()
    assert "superheroes session bootstrap" in ctx        # bootstrap present
    assert "compact_sentinel".lower() in ctx             # project CLAUDE.md parity
    assert "re-arm" in ctx and "reconcile" in ctx        # resume-brief names BOTH actions


def test_session_start_compact_without_workitem_emits_bootstrap_only(tmp_path):
    # The compacted-discovery path (no work-item): the work-item early-return must
    # NOT suppress the bootstrap, and the resume-brief must be ABSENT.
    _git_repo_with_claude(tmp_path, "NO_WI_SENTINEL")
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    r = _run("session_start.py", {"source": "compact", "cwd": str(tmp_path)}, env)
    assert r.returncode == 0
    ctx = _ctx(r)
    assert "Superheroes session bootstrap" in ctx        # bootstrap still emitted
    assert "NO_WI_SENTINEL" in ctx
    assert "reconcile" not in ctx.lower()                # resume-brief gated out


def test_session_start_unknown_source_is_noop(tmp_path):
    # Only an out-of-enum source is a no-op now (the four real sources all inject).
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    r = _run("session_start.py", {"source": "bogus", "cwd": str(tmp_path)}, env)
    assert r.returncode == 0 and r.stdout.strip() == ""


def test_session_start_malformed_stdin_is_noop(tmp_path):
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    for stdin in ("not json", "", "[]", "\"a string\""):   # invalid + valid-but-non-dict JSON
        r = subprocess.run([sys.executable, os.path.join(HOOKS, "session_start.py")],
                           input=stdin, capture_output=True, text=True, env=env)
        assert r.returncode == 0 and r.stdout.strip() == "", repr(stdin)


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
