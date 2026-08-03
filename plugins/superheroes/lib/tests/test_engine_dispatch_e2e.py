"""Real-subprocess integration battery for engine_dispatch (#702 WO-D).

Every test drives the production path: detached run-child, no injected run_engine seam.
Fake engine behavior is baked into the executable at install time — the run-child scrubs
the spawn environment, so env-var-driven fakes would never reach the engine process.
"""
import importlib.util
import json
import os
import signal
import subprocess
import sys
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load():
    path = os.environ.get("ENGINE_DISPATCH_NEUTRAL_PATH") or os.path.join(
        _HERE, "..", "engine_dispatch.py")
    spec = importlib.util.spec_from_file_location("engine_dispatch", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ED = _load()

_EA = importlib.util.spec_from_file_location(
    "engine_adapter", os.path.join(_HERE, "..", "engine_adapter.py"))
EA = importlib.util.module_from_spec(_EA)
_EA.loader.exec_module(EA)

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "dispatch-e2e",
    "GIT_AUTHOR_EMAIL": "e2e@test.local",
    "GIT_COMMITTER_NAME": "dispatch-e2e",
    "GIT_COMMITTER_EMAIL": "e2e@test.local",
}


@pytest.fixture(autouse=True)
def _pin_temp_and_journal(tmp_path, monkeypatch):
    base = str(tmp_path / "temp-base")
    os.makedirs(base, exist_ok=True)
    monkeypatch.setattr(ED.tempfile, "gettempdir", lambda: base)
    journal_root = str(tmp_path / "dispatch-journal-root")
    os.makedirs(journal_root, exist_ok=True)
    monkeypatch.setenv(ED.JOURNAL_ROOT_ENV, journal_root)
    yield


def _git(cwd, *args, check=True, env=None):
    merged = dict(os.environ)
    merged.update(_GIT_ENV)
    if env:
        merged.update(env)
    return subprocess.run(
        ["git", "-C", cwd, *args],
        capture_output=True, text=True, check=check, env=merged,
    )


def _init_repo(path):
    os.makedirs(path, exist_ok=True)
    _git(path, "init", "-q")
    readme = os.path.join(path, "README.md")
    with open(readme, "w", encoding="utf-8") as fh:
        fh.write("hello\n")
    _git(path, "add", "README.md")
    _git(path, "commit", "-qm", "init")
    return path


def _linked_worktree(tmp_path):
    main = str(tmp_path / "main")
    _init_repo(main)
    wt = str(tmp_path / "wt")
    _git(main, "worktree", "add", "-q", wt)
    return wt, main


def _prompt(tmp_path, content="Do the work.\n"):
    p = tmp_path / "prompt.txt"
    p.write_text(content, encoding="utf-8")
    return str(p)


def _run_dir(tmp_path, name):
    """Run dir under pytest tmp_path (realpath-stable on macOS)."""
    path = str(tmp_path / name)
    os.makedirs(path, exist_ok=True)
    return path


def _findings_stdout():
    return json.dumps({"findings": [{"id": "f1", "message": "issue found"}]})


def _build_ok_stdout():
    return json.dumps({
        "ok": True, "signal": "ok",
        "evidence": {"testFailed": False, "testPassed": True},
    })


def _honest_refusal_stdout():
    return json.dumps({
        "ok": False, "signal": "plan_wrong",
        "evidence": {"testFailed": True, "testPassed": False},
    })


def _install_fake_engine(tmp_path, monkeypatch, name, *, stdout="", sleep_s=0, exit_code=0,
                          argv_file=None, out_file=None, death_marker=None, stage_out_file=False):
    """Install a fake engine; behavior is literal in the script (survives env scrub)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    exe = bin_dir / name
    body = '''#!/usr/bin/env python3
import json
import subprocess
import sys
import time

_argv_file = %(argv_file)r
_out_file = %(out_file)r
_death_marker = %(death_marker)r
_stage_out_file = %(stage_out_file)s
_stdout_payload = %(stdout)r
_sleep_s = %(sleep)s
_exit_code = %(exit_code)s

if _death_marker:
    import atexit
    import signal

    def _mark_death(signum=None, frame=None):
        with open(_death_marker, "w", encoding="utf-8"):
            pass

    signal.signal(signal.SIGTERM, _mark_death)
    signal.signal(signal.SIGINT, _mark_death)
    atexit.register(_mark_death)

if _argv_file:
    with open(_argv_file, "w", encoding="utf-8") as fh:
        json.dump(sys.argv, fh)

_stdin_data = sys.stdin.read()
if _out_file:
    with open(_out_file, "w", encoding="utf-8") as fh:
        fh.write(_stdin_data)
    if _stage_out_file:
        subprocess.run(["git", "add", _out_file], check=False)

if _sleep_s:
    time.sleep(_sleep_s)

if _stdout_payload:
    sys.stdout.write(_stdout_payload)
    sys.stdout.flush()

sys.exit(_exit_code)
''' % {
        "argv_file": argv_file,
        "out_file": out_file,
        "death_marker": death_marker,
        "stage_out_file": stage_out_file,
        "stdout": stdout,
        "sleep": sleep_s,
        "exit_code": exit_code,
    }
    exe.write_text(body, encoding="utf-8")
    exe.chmod(0o755)
    path_env = str(bin_dir) + os.pathsep + "/usr/bin" + os.pathsep + "/bin"
    monkeypatch.setenv("PATH", path_env)
    return exe


def _journal_records(run_dir):
    records, _corrupt = ED._journal_read(run_dir)
    return records


def _count_attempt_started(run_dir):
    return sum(1 for r in _journal_records(run_dir) if r.get("kind") == "attempt-started")


def _wait_until(deadline, predicate, fail_msg):
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    pytest.fail(fail_msg)


def _poll_write_terminal(wt, run_dir, prompt_path, *, order_id="e2e-order", timeout=120):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = ED.dispatch_write(
            "cursor", model=None, effort="high",
            prompt_path=prompt_path, cwd=wt, run_dir=run_dir,
            order_id=order_id, timeout=60, retry_timeout=60,
        )
        if last.get("terminal"):
            return last
        if last.get("reason") != "running":
            return last
        time.sleep(0.2)
    pytest.fail(
        "timed out waiting for terminal write result; last=%s; journal=%s"
        % (last, _journal_records(run_dir))
    )


def _poll_review_terminal(repo_root, run_dir, prompt_path, *, timeout=120):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = ED.dispatch_review(
            "codex", model="sonnet", effort="high",
            prompt_path=prompt_path, repo_root=repo_root, run_dir=run_dir,
        )
        if last.get("terminal"):
            return last
        if last.get("reason") != "running":
            return last
        time.sleep(0.2)
    pytest.fail(
        "timed out waiting for terminal review result; last=%s; journal=%s"
        % (last, _journal_records(run_dir))
    )


def _engine_pgid(run_dir):
    state = ED._journal_state(_journal_records(run_dir))
    for att in sorted(state.get("attempts", {})):
        pgid = state["attempts"][att].get("enginePgid")
        if pgid is not None:
            return pgid
    return None


def _run_child_pid(run_dir):
    state = ED._journal_state(_journal_records(run_dir))
    for att in sorted(state.get("attempts", {})):
        pid = state["attempts"][att].get("childPid")
        if pid is not None:
            return pid
    return None


def _lease_path(wt):
    return ED._worktree_lease_path(os.path.realpath(wt))


def _no_mismatch_tokens(records):
    for rec in records:
        for val in rec.values():
            if isinstance(val, str) and "mismatch" in val:
                return False
    return True


def _engine_dispatch_script():
    return os.environ.get("ENGINE_DISPATCH_NEUTRAL_PATH") or os.path.join(
        _HERE, "..", "engine_dispatch.py")


def _cli_env(tmp_path):
    """Environment for subprocess CLI invocations (matches autouse fixture pins)."""
    base = str(tmp_path / "temp-base")
    os.makedirs(base, exist_ok=True)
    journal_root = os.environ.get(ED.JOURNAL_ROOT_ENV)
    if not journal_root:
        journal_root = str(tmp_path / "dispatch-journal-root")
        os.makedirs(journal_root, exist_ok=True)
    env = dict(os.environ)
    env["TMPDIR"] = base
    env[ED.JOURNAL_ROOT_ENV] = journal_root
    return env


def _parse_cli_json(stdout):
    line = stdout.strip().splitlines()[-1]
    return json.loads(line)


def _invoke_cli(env, verb, args, *, timeout=None):
    cmd = [sys.executable, "-B", _engine_dispatch_script(), verb, *args]
    return subprocess.run(
        cmd, capture_output=True, text=True, env=env, timeout=timeout,
    )


def _cli_until_terminal(env, verb, args, run_dir, *, timeout=120):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        proc = _invoke_cli(env, verb, args)
        assert proc.returncode == 0, proc.stderr
        last = _parse_cli_json(proc.stdout)
        if last.get("terminal"):
            return last
        if last.get("reason") != "running":
            return last
        time.sleep(0.2)
    pytest.fail(
        "timed out waiting for terminal CLI result; last=%s; journal=%s"
        % (last, _journal_records(run_dir))
    )


def _drop_max_wait(args):
    out = []
    skip = False
    for arg in args:
        if skip:
            skip = False
            continue
        if arg == "--max-wait":
            skip = True
            continue
        out.append(arg)
    return out


# --- 1. Review real path terminal success -------------------------------------


def test_e2e_review_real_path_terminal_success(tmp_path, monkeypatch):
    repo = str(tmp_path / "repo")
    _init_repo(repo)
    run_dir = _run_dir(tmp_path, "run-review")
    prompt_path = _prompt(tmp_path, "Review this.\n")
    argv_file = str(tmp_path / "engine-argv.json")

    _install_fake_engine(
        tmp_path, monkeypatch, "codex",
        stdout=_findings_stdout(), argv_file=argv_file,
    )

    res = _poll_review_terminal(repo, run_dir, prompt_path)

    assert res["ok"] is True
    assert res["terminal"] is True
    assert res["attempts"] == 1
    assert len(res.get("findings") or []) == 1
    assert res["findings"][0]["id"] == "f1"

    with open(argv_file, encoding="utf-8") as fh:
        spawned_argv = json.load(fh)
    # argv[0] is PATH-resolved in the child; tail must match the journaled argv exactly.
    assert os.path.basename(spawned_argv[0]) == res["argv"][0]
    assert spawned_argv[1:] == res["argv"][1:]
    records = _journal_records(run_dir)
    assert _no_mismatch_tokens(records)
    for rec in records:
        if rec.get("kind") == "attempt-ended":
            assert not rec.get("refusal")


# --- 2. Write real path terminal success --------------------------------------


def test_e2e_write_real_path_terminal_success(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)
    run_dir = _run_dir(tmp_path, "run-write")
    prompt_path = _prompt(tmp_path)
    out_marker = os.path.join(wt, "engine-wrote.txt")

    _install_fake_engine(
        tmp_path, monkeypatch, "cursor-agent",
        stdout=_build_ok_stdout(), out_file=out_marker,
    )

    head_before = _git(wt, "rev-parse", "HEAD").stdout.strip()
    porcelain_before = _git(wt, "status", "--porcelain").stdout

    res = _poll_write_terminal(wt, run_dir, prompt_path)

    assert res["ok"] is True
    assert res["terminal"] is True
    assert os.path.isfile(out_marker)
    head_after = _git(wt, "rev-parse", "HEAD").stdout.strip()
    porcelain_after = _git(wt, "status", "--porcelain").stdout
    cached = _git(wt, "diff", "--cached", "--name-only").stdout.strip()
    assert head_before == head_after
    assert "engine-wrote.txt" in porcelain_after
    assert porcelain_after.strip().startswith("??")
    assert cached == ""
    assert porcelain_before != porcelain_after


# --- 3. Survivability across supervisor rotation ------------------------------


def test_e2e_supervisor_rotation_survives(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)
    run_dir = _run_dir(tmp_path, "run-rotate")
    prompt_path = _prompt(tmp_path)

    _install_fake_engine(
        tmp_path, monkeypatch, "cursor-agent",
        stdout=_build_ok_stdout(), sleep_s=30,
    )

    first = ED.dispatch_write(
        "cursor", model=None, effort="high",
        prompt_path=prompt_path, cwd=wt, run_dir=run_dir,
        order_id="rotate-1", timeout=60, retry_timeout=60, max_wait=1,
    )
    assert first["terminal"] is False
    assert first["reason"] == "running"

    pgid = _engine_pgid(run_dir)
    assert pgid is not None
    assert ED._process_group_alive(pgid)

    second = _poll_write_terminal(wt, run_dir, prompt_path, order_id="rotate-1")
    assert second["ok"] is True
    assert second["terminal"] is True


# --- 4. Exit code survives supervisor -----------------------------------------


def test_e2e_exit_code_survives_supervisor(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)
    run_dir = _run_dir(tmp_path, "run-exit")
    prompt_path = _prompt(tmp_path)

    _install_fake_engine(
        tmp_path, monkeypatch, "cursor-agent",
        stdout="not-json", sleep_s=5, exit_code=42,
    )

    first = ED.dispatch_write(
        "cursor", model=None, effort="high",
        prompt_path=prompt_path, cwd=wt, run_dir=run_dir,
        order_id="exit-1", timeout=60, retry_timeout=60, max_wait=1,
    )
    assert first["terminal"] is False
    assert first["reason"] == "running"

    _wait_until(
        time.monotonic() + 30,
        lambda: any(
            r.get("kind") == "attempt-ended" and r.get("exit") == 42
            for r in _journal_records(run_dir)
        ),
        "engine never recorded exit 42 in journal",
    )

    second = _poll_write_terminal(wt, run_dir, prompt_path, order_id="exit-1", timeout=180)
    assert second["terminal"] is True
    assert second["ok"] is False
    assert second.get("forfeited") is True
    ended = [
        r for r in _journal_records(run_dir)
        if r.get("kind") == "attempt-ended" and r.get("attempt") == 1
    ]
    assert len(ended) == 1
    assert ended[0]["exit"] == 42


# --- 5. No second engine into one worktree (pgroup gate) -----------------------


def test_e2e_no_second_engine_pgroup_gate(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)
    run_dir = _run_dir(tmp_path, "run-pgroup")
    prompt_path = _prompt(tmp_path)

    _install_fake_engine(
        tmp_path, monkeypatch, "cursor-agent",
        stdout=_build_ok_stdout(), sleep_s=120,
    )

    first = ED.dispatch_write(
        "cursor", model=None, effort="high",
        prompt_path=prompt_path, cwd=wt, run_dir=run_dir,
        order_id="pgroup-1", timeout=180, retry_timeout=180, max_wait=1,
    )
    assert first["terminal"] is False
    assert _count_attempt_started(run_dir) == 1

    again = ED.dispatch_write(
        "cursor", model=None, effort="high",
        prompt_path=prompt_path, cwd=wt, run_dir=run_dir,
        order_id="pgroup-1", timeout=180, retry_timeout=180, max_wait=1,
    )
    assert again["terminal"] is False
    assert again["reason"] == "running"
    assert _count_attempt_started(run_dir) == 1

    child_pid = _run_child_pid(run_dir)
    assert child_pid is not None
    pgid = _engine_pgid(run_dir)
    assert pgid is not None
    assert ED._process_group_alive(pgid)

    try:
        os.kill(child_pid, signal.SIGKILL)
    except ProcessLookupError:
        pass

    _wait_until(
        time.monotonic() + 10,
        lambda: not ED._process_alive(child_pid),
        "run-child did not die after SIGKILL",
    )
    assert ED._process_group_alive(pgid), "engine pgroup must outlive run-child kill"

    again2 = ED.dispatch_write(
        "cursor", model=None, effort="high",
        prompt_path=prompt_path, cwd=wt, run_dir=run_dir,
        order_id="pgroup-1", timeout=180, retry_timeout=180, max_wait=1,
    )
    assert again2["terminal"] is False
    assert _count_attempt_started(run_dir) == 1

    ED.dispatch_abandon(run_dir)


# --- 6. Lease blocks second run dir -------------------------------------------


def test_e2e_lease_blocks_second_run_dir(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)
    run_a = _run_dir(tmp_path, "run-a")
    run_b = _run_dir(tmp_path, "run-b")
    prompt_path = _prompt(tmp_path)

    _install_fake_engine(
        tmp_path, monkeypatch, "cursor-agent",
        stdout=_build_ok_stdout(), sleep_s=120,
    )

    res_a = ED.dispatch_write(
        "cursor", model=None, effort="high",
        prompt_path=prompt_path, cwd=wt, run_dir=run_a,
        order_id="lease-a", timeout=180, retry_timeout=180, max_wait=1,
    )
    assert res_a["terminal"] is False
    assert os.path.exists(_lease_path(wt))

    res_b = ED.dispatch_write(
        "cursor", model=None, effort="high",
        prompt_path=prompt_path, cwd=wt, run_dir=run_b,
        order_id="lease-b", timeout=180, retry_timeout=180,
    )
    assert res_b["terminal"] is True
    assert res_b["detail"] == "worktree-lease-held"
    assert res_b["attempts"] == 0
    assert _count_attempt_started(run_a) == 1

    ED.dispatch_abandon(run_a)


# --- 7. Lease gone on every terminal exit -------------------------------------


@pytest.mark.parametrize("scenario", ["success", "honest_refusal", "double_forfeit", "abandon"])
def test_e2e_lease_released_on_terminal(tmp_path, monkeypatch, scenario):
    wt, _main = _linked_worktree(tmp_path)
    run_dir = _run_dir(tmp_path, "run-lease-" + scenario)
    prompt_path = _prompt(tmp_path)

    if scenario == "success":
        _install_fake_engine(tmp_path, monkeypatch, "cursor-agent", stdout=_build_ok_stdout())
        res = _poll_write_terminal(wt, run_dir, prompt_path, order_id="lease-" + scenario)
        assert res["ok"] is True
    elif scenario == "honest_refusal":
        _install_fake_engine(tmp_path, monkeypatch, "cursor-agent", stdout=_honest_refusal_stdout())
        res = _poll_write_terminal(wt, run_dir, prompt_path, order_id="lease-" + scenario)
        assert res["ok"] is False
        assert res["forfeited"] is False
        assert res["reason"] == "plan_wrong"
    elif scenario == "double_forfeit":
        _install_fake_engine(tmp_path, monkeypatch, "cursor-agent", stdout="not-valid-json")
        res = _poll_write_terminal(wt, run_dir, prompt_path, order_id="lease-" + scenario, timeout=180)
        assert res["ok"] is False
        assert res.get("forfeited") is True
    else:  # abandon
        _install_fake_engine(
            tmp_path, monkeypatch, "cursor-agent",
            stdout=_build_ok_stdout(), sleep_s=120,
        )
        ED.dispatch_write(
            "cursor", model=None, effort="high",
            prompt_path=prompt_path, cwd=wt, run_dir=run_dir,
            order_id="lease-" + scenario, timeout=180, retry_timeout=180, max_wait=2,
        )
        _wait_until(
            time.monotonic() + 15,
            lambda: _engine_pgid(run_dir) is not None and ED._process_group_alive(_engine_pgid(run_dir)),
            "engine never became alive for abandon scenario",
        )
        assert os.path.exists(_lease_path(wt))
        res = ED.dispatch_abandon(run_dir)
        assert res["detail"] == "run-abandoned"

    assert not os.path.exists(_lease_path(wt)), "lease must be gone after terminal %s" % scenario


def test_e2e_lease_retained_on_non_terminal_slice(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)
    run_dir = _run_dir(tmp_path, "run-lease-running")
    prompt_path = _prompt(tmp_path)

    _install_fake_engine(
        tmp_path, monkeypatch, "cursor-agent",
        stdout=_build_ok_stdout(), sleep_s=120,
    )

    res = ED.dispatch_write(
        "cursor", model=None, effort="high",
        prompt_path=prompt_path, cwd=wt, run_dir=run_dir,
        order_id="lease-running", timeout=180, retry_timeout=180, max_wait=1,
    )
    assert res["terminal"] is False
    assert res["reason"] == "running"
    assert os.path.exists(_lease_path(wt))

    ED.dispatch_abandon(run_dir)


# --- 8. dispatch-poll never spawns --------------------------------------------


def test_e2e_dispatch_poll_never_spawns(tmp_path, monkeypatch):
    repo = str(tmp_path / "repo-poll")
    _init_repo(repo)
    run_dir = _run_dir(tmp_path, "run-poll")
    prompt_path = _prompt(tmp_path, "Review.\n")

    _install_fake_engine(tmp_path, monkeypatch, "codex", stdout=_findings_stdout())

    opened = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=prompt_path, repo_root=repo, run_dir=run_dir, max_wait=0,
    )
    assert opened["reason"] == "running"
    before = _count_attempt_started(run_dir)
    poll1 = ED.dispatch_poll(run_dir)
    after1 = _count_attempt_started(run_dir)
    assert poll1["reason"] == "running"
    assert before == after1 == 0

    terminal = _poll_review_terminal(repo, run_dir, prompt_path)
    assert terminal["terminal"] is True

    run_dir2 = _run_dir(tmp_path, "run-poll-dead")
    wt, _main = _linked_worktree(tmp_path)
    prompt2 = _prompt(tmp_path, "Build.\n")
    _install_fake_engine(tmp_path, monkeypatch, "cursor-agent", stdout=_build_ok_stdout())
    _poll_write_terminal(wt, run_dir2, prompt2, order_id="poll-dead")

    before2 = _count_attempt_started(run_dir2)
    poll2 = ED.dispatch_poll(run_dir2)
    after2 = _count_attempt_started(run_dir2)
    assert poll2["terminal"] is True
    assert before2 == after2


# --- 9. dispatch-abandon kills engine before releasing lease ------------------


def test_e2e_dispatch_abandon_order_and_idempotent(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)
    run_dir = _run_dir(tmp_path, "run-abandon")
    prompt_path = _prompt(tmp_path)
    death_marker = str(tmp_path / "engine-death.marker")
    lease_at_abandon = []
    engine_alive_at_cleanup = []
    real_append = ED._journal_append
    real_finalize = ED._finalize_run

    def tracking_append(run_dir_real, record):
        if record.get("kind") == "run-abandoned":
            lease_at_abandon.append(os.path.exists(_lease_path(wt)))
        return real_append(run_dir_real, record)

    def tracking_finalize(state, terminal=False):
        records, _ = ED._journal_read(run_dir)
        alive, _who = ED._run_live_evidence(ED._journal_state(records))
        engine_alive_at_cleanup.append(alive)
        return real_finalize(state, terminal=terminal)

    monkeypatch.setattr(ED, "_journal_append", tracking_append)
    monkeypatch.setattr(ED, "_finalize_run", tracking_finalize)

    _install_fake_engine(
        tmp_path, monkeypatch, "cursor-agent",
        stdout=_build_ok_stdout(), sleep_s=120, death_marker=death_marker,
    )

    ED.dispatch_write(
        "cursor", model=None, effort="high",
        prompt_path=prompt_path, cwd=wt, run_dir=run_dir,
        order_id="abandon-1", timeout=180, retry_timeout=180, max_wait=2,
    )
    _wait_until(
        time.monotonic() + 15,
        lambda: _engine_pgid(run_dir) is not None and ED._process_group_alive(_engine_pgid(run_dir)),
        "engine never became alive for abandon test",
    )
    pgid = _engine_pgid(run_dir)
    assert os.path.exists(_lease_path(wt))

    first = ED.dispatch_abandon(run_dir)
    assert not ED._process_group_alive(pgid)
    assert not os.path.exists(_lease_path(wt))
    records = _journal_records(run_dir)
    abandoned = [r for r in records if r.get("kind") == "run-abandoned"]
    assert len(abandoned) == 1
    assert os.path.isfile(death_marker)
    assert os.path.getmtime(death_marker) < abandoned[0]["at"]
    assert lease_at_abandon == [True]
    assert engine_alive_at_cleanup == [False]
    assert records[-1]["kind"] == "run-abandoned"
    assert first["terminal"] is True
    assert first["detail"] == "run-abandoned"

    second = ED.dispatch_abandon(run_dir)
    assert second == first


# --- 10. Caller death: fresh process re-attaches via originating verb -------


@pytest.mark.parametrize("verb", ["dispatch-review", "dispatch-write"])
def test_e2e_caller_death_originating_verb_reattaches(tmp_path, monkeypatch, verb):
    """Prove a dead dispatch caller does not orphan the run: re-invoke the verb."""
    order_id = "death-reattach-1"
    engine_sleep_s = 30
    max_wait_s = "1"
    timeout_args = ["--timeout", "60", "--retry-timeout", "60"]

    if verb == "dispatch-review":
        repo = str(tmp_path / "repo-death")
        _init_repo(repo)
        run_dir = _run_dir(tmp_path, "run-death-review")
        prompt_path = _prompt(tmp_path, "Review this.\n")
        _install_fake_engine(
            tmp_path, monkeypatch, "codex",
            stdout=_findings_stdout(), sleep_s=engine_sleep_s,
        )
        cli_args = [
            "--engine", "codex", "--model", "sonnet", "--effort", "high",
            "--prompt-path", prompt_path, "--repo-root", repo,
            "--run-dir", run_dir, "--max-wait", max_wait_s,
            *timeout_args,
        ]
    else:
        wt, _main = _linked_worktree(tmp_path)
        run_dir = _run_dir(tmp_path, "run-death-write")
        prompt_path = _prompt(tmp_path)
        _install_fake_engine(
            tmp_path, monkeypatch, "cursor-agent",
            stdout=_build_ok_stdout(), sleep_s=engine_sleep_s,
        )
        cli_args = [
            "--engine", "cursor", "--effort", "high",
            "--prompt-path", prompt_path, "--cwd", wt,
            "--run-dir", run_dir, "--order-id", order_id,
            "--max-wait", max_wait_s,
            *timeout_args,
        ]

    env = _cli_env(tmp_path)
    reattach_args = _drop_max_wait(cli_args) + ["--max-wait", "60"]
    cmd = [sys.executable, "-B", _engine_dispatch_script(), verb, *cli_args]
    wall_start = time.monotonic()
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    )
    try:
        _wait_until(
            time.monotonic() + 15,
            lambda: (
                _count_attempt_started(run_dir) >= 1
                and _engine_pgid(run_dir) is not None
                and ED._process_group_alive(_engine_pgid(run_dir))
            ),
            "engine never became alive before caller slice expired",
        )
        pgid = _engine_pgid(run_dir)
        assert pgid is not None
        assert ED._process_group_alive(pgid), "engine must be alive before caller exits"

        stdout, _stderr = proc.communicate(timeout=15)
        assert proc.poll() is not None, "first CLI caller must have exited"
        first = _parse_cli_json(stdout)
        assert first["terminal"] is False
        assert first["reason"] == "running"

        assert proc.poll() is not None, "caller must be dead before re-attach"
        assert ED._process_group_alive(pgid), "engine must survive caller death"

        terminal = _cli_until_terminal(env, verb, reattach_args, run_dir, timeout=120)
        assert terminal["terminal"] is True
        assert terminal["ok"] is True
        assert _count_attempt_started(run_dir) == 1
    finally:
        ED.dispatch_abandon(run_dir)

    wall_elapsed = time.monotonic() - wall_start
    assert wall_elapsed < 120, "test wall time must stay modest (got %.1fs)" % wall_elapsed


# --- 11. PATH-independence proof ----------------------------------------------


def test_e2e_path_independence_terminal_refusal(tmp_path, monkeypatch):
    repo = str(tmp_path / "repo-path")
    _init_repo(repo)
    run_dir = _run_dir(tmp_path, "run-path")
    prompt_path = _prompt(tmp_path, "Review.\n")

    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    res = _poll_review_terminal(repo, run_dir, prompt_path, timeout=180)

    assert isinstance(res, dict)
    assert res.get("terminal") is True
    assert res.get("ok") is False
