"""#1947: the native implementer fence — native_fence.fence_decision and the implementer_fence.py shim.

Invariant: the hook acts only when the payload's agent_type is exactly "superheroes:implementer" AND
either the call is a native run's enroll command or its agent_id is enrolled in a native run (open
or closed). It then denies per the contract, and is silent for every other payload. A deny is one
atomic JSON write with permissionDecision "deny"; it never prompts and never hangs.

Token, reason and record-kind literals are spelled out as strings on purpose: a test that reaches
them through the module's constants stays green under any value (rubric/bite-proof.md).

Detector axes (bite-proof):
- F1 — scope: the builder and every other agent are untouched, enrolled index entry or not
- F2 — scope: an un-enrolled implementer is untouched
- F3 — binding: the enroll command journals one native-enrolled record and writes the index, once
- F4 — deadline: an enrolled implementer past deadlineAt is denied on Bash, Edit and Write
- F5 — closed run: an enrolled implementer of a closed run is denied
- F6 — installers: every installer form is denied, the nearby safe forms are not
- F7 — network: every network form is denied, the nearby safe git forms are not
- F8 — parsing: wrappers, assignments, chaining and path-qualified words are seen through
- F9 — parsing: an unparseable segment is denied
- F10 — process contract: one atomic deny, silent for others, fail-closed on a raise
- F11 — wiring: see test_hook_wiring.py
"""
import importlib.util
import io
import json
import os
import subprocess
import sys

import pytest

import engine_dispatch as ED
import native_fence

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_HOOK = os.path.join(_PLUGIN, "hooks", "implementer_fence.py")
_LIB = os.path.join(_PLUGIN, "lib")

_IMPLEMENTER = "superheroes:implementer"
_NOW = "2026-01-01T12:00:00Z"
_FUTURE = "2026-01-01T13:00:00Z"
_PAST = "2026-01-01T11:00:00Z"
_FAR_FUTURE = "2099-01-01T00:00:00Z"
_AGENT = "agent-1"


@pytest.fixture(autouse=True)
def _pin_roots(tmp_path, monkeypatch):
    store = str(tmp_path / "store-root")
    os.makedirs(store, exist_ok=True)
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", store)
    monkeypatch.delenv("WORKHORSE_STORE_ROOT", raising=False)
    monkeypatch.setenv("SUPERHEROES_DISPATCH_JOURNAL_ROOT", str(tmp_path / "journal-root"))
    monkeypatch.setenv("SUPERHEROES_NATIVE_INDEX_ROOT", str(tmp_path / "index-root"))


def _index_file(tmp_path, agent_id=_AGENT):
    return tmp_path / "index-root" / ("%s.json" % agent_id)


def _run_dir(tmp_path, name="run"):
    d = tmp_path / name
    d.mkdir()
    return os.path.realpath(str(d))


def _open_run(run_dir, deadline_at=_FUTURE, engine="native"):
    assert ED._journal_append(run_dir, {
        "kind": "run-opened", "engine": engine, "runKind": "write", "cwd": "/builder/worktree",
        "deadlineAt": deadline_at})


def _close_run(run_dir):
    assert ED._journal_append(run_dir, {"kind": "run-closed", "ok": True})


def _enroll_directly(tmp_path, run_dir, agent_id=_AGENT):
    """Journal the binding and write the index the way the hook's enroll step does, without it."""
    assert ED._journal_append(run_dir, {
        "kind": "native-enrolled", "agentId": agent_id, "worktree": "/agent/worktree", "at": _NOW})
    os.makedirs(tmp_path / "index-root", exist_ok=True)
    _index_file(tmp_path, agent_id).write_text(json.dumps({"runDir": run_dir}))


def _enrolled_run(tmp_path, deadline_at=_FUTURE):
    run_dir = _run_dir(tmp_path)
    _open_run(run_dir, deadline_at)
    _enroll_directly(tmp_path, run_dir)
    return run_dir


def _payload(tool="Bash", command=None, agent_type=_IMPLEMENTER, agent_id=_AGENT, cwd="/agent/worktree"):
    p = {"tool_name": tool, "tool_input": {}, "agent_id": agent_id, "cwd": cwd}
    if command is not None:
        p["tool_input"] = {"command": command}
    if agent_type is not None:
        p["agent_type"] = agent_type
    return p


def _enroll_command(run_dir):
    return "python3 -B %s/native_engine.py enroll --run-dir %s" % (_LIB, run_dir)


def _decide(payload, now=_NOW):
    return native_fence.fence_decision(payload, now)


def _records(run_dir, kind):
    return [r for r in ED._journal_read_raw(run_dir)[0] if r.get("kind") == kind]


# --- F1 / F2: scope ----------------------------------------------------------------------------

@pytest.mark.parametrize("agent_type", [None, "absent", "Explore", "superheroes:pilot"])
def test_builder_and_other_agents_are_silent_even_with_an_enrolled_index_entry(tmp_path, agent_type):
    # axis: scope — only the exact implementer agent_type is fenced
    _enrolled_run(tmp_path)
    payload = _payload(command="pip install x", agent_type=agent_type)
    if agent_type == "absent":
        del payload["agent_type"]
    assert _decide(payload) is None


def test_builder_enroll_command_is_silent_and_records_nothing(tmp_path):
    # axis: scope — the enroll step belongs to the implementer alone
    run_dir = _run_dir(tmp_path)
    _open_run(run_dir)
    assert _decide(_payload(command=_enroll_command(run_dir), agent_type=None)) is None
    assert _records(run_dir, "native-enrolled") == []
    assert not _index_file(tmp_path).exists()


def test_unenrolled_implementer_is_silent(tmp_path):
    # axis: scope — an implementer with no index entry is outside any native run
    assert _decide(_payload(command="curl x")) is None
    _enrolled_run(tmp_path)
    assert _decide(_payload(command="curl x", agent_id="agent-2")) is None


# --- F3: the enroll binding --------------------------------------------------------------------

def test_enroll_binds_the_agent_once(tmp_path):
    # axis: binding — one native-enrolled record and one index entry per run, written by the hook
    run_dir = _run_dir(tmp_path)
    _open_run(run_dir)
    real_wt = tmp_path / "wt"
    real_wt.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real_wt)

    assert _decide(_payload(command=_enroll_command(run_dir), cwd=str(link))) is None

    recs = _records(run_dir, "native-enrolled")
    assert len(recs) == 1
    assert recs[0]["agentId"] == "agent-1"
    assert recs[0]["worktree"] == os.path.realpath(str(real_wt))
    assert recs[0]["at"] == _NOW
    assert json.loads(_index_file(tmp_path).read_text()) == {"runDir": run_dir}

    again = _decide(_payload(command=_enroll_command(run_dir), cwd=str(link)))
    assert again is not None and "already" in again
    other = _decide(_payload(command=_enroll_command(run_dir), agent_id="agent-2"))
    assert other is not None and "already" in other
    assert len(_records(run_dir, "native-enrolled")) == 1
    assert not _index_file(tmp_path, "agent-2").exists()


def test_enroll_is_denied_for_a_closed_run(tmp_path):
    # axis: binding — a closed run cannot be enrolled into
    run_dir = _run_dir(tmp_path)
    _open_run(run_dir)
    _close_run(run_dir)
    reason = _decide(_payload(command=_enroll_command(run_dir)))
    assert reason is not None and "closed" in reason
    assert _records(run_dir, "native-enrolled") == []


def test_enroll_is_denied_past_the_deadline(tmp_path):
    # axis: binding — a run past its deadline cannot be enrolled into
    run_dir = _run_dir(tmp_path)
    _open_run(run_dir, deadline_at=_PAST)
    reason = _decide(_payload(command=_enroll_command(run_dir)))
    assert reason is not None and _PAST in reason
    assert _records(run_dir, "native-enrolled") == []


def test_enroll_is_denied_without_a_native_run(tmp_path):
    # axis: binding — a run dir with no native run-opened record has nothing to enroll into
    empty = _run_dir(tmp_path, "empty")
    reason = _decide(_payload(command=_enroll_command(empty)))
    assert reason is not None and "no open native run" in reason
    assert _records(empty, "native-enrolled") == []

    other_engine = _run_dir(tmp_path, "other")
    _open_run(other_engine, engine="codex")
    assert _decide(_payload(command=_enroll_command(other_engine))) is not None
    assert _records(other_engine, "native-enrolled") == []
    assert not _index_file(tmp_path).exists()


def test_a_chained_enroll_command_is_not_an_enroll(tmp_path):
    # axis: binding — the enroll recognizer takes the whole command, so a chain cannot smuggle a fenced word
    run_dir = _run_dir(tmp_path)
    _open_run(run_dir)
    chained = "curl x; " + _enroll_command(run_dir)
    _decide(_payload(command=chained))
    assert _records(run_dir, "native-enrolled") == []
    assert native_fence.enroll_run_dir(chained) is None
    assert native_fence.enroll_run_dir(_enroll_command(run_dir)) == run_dir
    assert native_fence.enroll_run_dir(_enroll_command("relative/dir")) is None


# --- F4 / F5: deadline and closed run ----------------------------------------------------------

@pytest.mark.parametrize("tool,command", [("Bash", "ls"), ("Edit", None), ("Write", None)])
def test_enrolled_implementer_past_the_deadline_is_denied(tmp_path, tool, command):
    # axis: deadline — Bash, Edit and Write all stop at deadlineAt, and the reason names it
    _enrolled_run(tmp_path, deadline_at=_PAST)
    reason = _decide(_payload(tool=tool, command=command))
    assert reason is not None
    assert "2026-01-01T11:00:00Z" in reason and "deadline" in reason


@pytest.mark.parametrize("tool,command", [("Bash", "ls"), ("Edit", None), ("Write", None)])
def test_enrolled_implementer_before_the_deadline_is_silent_on_plain_calls(tmp_path, tool, command):
    # axis: deadline — the deadline gate does not fire early
    _enrolled_run(tmp_path, deadline_at=_FUTURE)
    assert _decide(_payload(tool=tool, command=command)) is None


@pytest.mark.parametrize("tool,command", [("Bash", "ls"), ("Edit", None), ("Write", None)])
def test_enrolled_implementer_of_a_closed_run_is_denied(tmp_path, tool, command):
    # axis: closed run — the enrolled agent is denied after run-closed, open deadline or not
    run_dir = _enrolled_run(tmp_path, deadline_at=_FUTURE)
    _close_run(run_dir)
    reason = _decide(_payload(tool=tool, command=command))
    assert reason is not None and "closed" in reason


# --- F6: installers ----------------------------------------------------------------------------

_INSTALLERS = [
    "pip install x", "pip3 install x", "pip download x", "python -m pip install x",
    "python3 -m pip install x", "uv pip install x", "uv add x", "uv tool install x", "uvx ruff",
    "pipx install x", "npm install", "npm i x", "npm ci", "npm add x", "npm update",
    "pnpm add x", "pnpm install", "pnpm i", "pnpm update", "yarn add x", "yarn install", "yarn",
    "brew install x", "apt install x", "apt-get install x", "dnf install x", "yum install x",
    "apk add x", "gem install x", "cargo install x", "go install x", "go get x",
    "conda install x", "poetry add x", "poetry install",
]


@pytest.mark.parametrize("command", _INSTALLERS)
def test_installers_are_denied(tmp_path, command):
    # axis: installers — each form in the contract's list is refused for an enrolled implementer
    _enrolled_run(tmp_path)
    reason = _decide(_payload(command=command))
    assert reason is not None
    assert reason.startswith("installs and network commands are refused for a native implementer: ")


@pytest.mark.parametrize("command", [
    "pip list", "npm test", "npm run build", "uv run pytest", "scripts/pinned-python -m pytest",
    "python3 -B -m unittest", "yarn test", "python3 -B -m pytest -q", "go test ./...",
    "cargo test", "poetry run pytest",
])
def test_nearby_safe_forms_are_silent(tmp_path, command):
    # axis: installers — the fence does not over-match the build and test commands
    _enrolled_run(tmp_path)
    assert _decide(_payload(command=command)) is None


# --- F7: network -------------------------------------------------------------------------------

@pytest.mark.parametrize("command", [
    "curl x", "wget x", "ssh host", "scp a b", "sftp host", "nc host 1", "ncat host 1",
    "netcat host 1", "telnet host", "ftp host", "git push", "git fetch", "git pull",
    "git clone x", "git ls-remote x", "git -C /tmp/x push", "gh pr list", "gh",
])
def test_network_commands_are_denied(tmp_path, command):
    # axis: network — each network word and each networked git subcommand is refused
    _enrolled_run(tmp_path)
    reason = _decide(_payload(command=command))
    assert reason is not None
    assert reason.startswith("installs and network commands are refused for a native implementer: ")


@pytest.mark.parametrize("command", [
    "git status", "git diff", "git commit -m x", "git log --oneline", "git add -A",
    'git commit -m "fix a; curl b"', "git -C /tmp/x diff",
])
def test_local_git_is_silent(tmp_path, command):
    # axis: network — local git work is not fenced
    _enrolled_run(tmp_path)
    assert _decide(_payload(command=command)) is None


def test_the_reason_names_the_matched_word(tmp_path):
    # axis: network — the deny reason carries the matched fence word
    _enrolled_run(tmp_path)
    assert _decide(_payload(command="git push origin x")).endswith(": git push")
    assert _decide(_payload(command="curl x")).endswith(": curl")
    assert native_fence.fence_word("pip install x") == "pip install"
    assert native_fence.fence_word("ls") is None


# --- F8 / F9: wrappers, chaining, unparseable --------------------------------------------------

@pytest.mark.parametrize("command", [
    "sudo pip install x", "env A=1 curl x", "FOO=1 npm install", "echo ok && curl x",
    "true; wget x", "ls | nc host 1", "/usr/bin/curl x", "echo a || pip install x",
    "ls\ncurl x", "sleep 1 & curl x", "nohup curl x", "time npm ci", "exec ssh host",
    "command curl x", "sudo -n pip install x",
])
def test_wrappers_chaining_and_paths_are_seen_through(tmp_path, command):
    # axis: parsing — the leading word is found past assignments, wrappers, separators and a path
    _enrolled_run(tmp_path)
    reason = _decide(_payload(command=command))
    assert reason is not None
    assert reason.startswith("installs and network commands are refused for a native implementer: ")


def test_shell_comments_are_ignored_outside_quotes():
    assert native_fence.fence_word("git status # don't fetch") is None
    assert native_fence.fence_word("ls\n# pip install x\ngit status") is None
    assert native_fence.fence_word("ls # note\npip install x") == "pip install"
    assert native_fence.fence_word("echo 'a # b' && pip install x") == "pip install"
    assert native_fence.fence_word("echo a#b; git fetch") == "git fetch"
    assert native_fence.fence_word('echo "unterminated') == "unparseable"


def test_unparseable_command_is_denied(tmp_path):
    # axis: parsing — a segment shlex cannot parse is refused, not waved through
    _enrolled_run(tmp_path)
    reason = _decide(_payload(command='echo "unterminated'))
    assert reason is not None and "unparseable command" in reason
    assert native_fence.fence_word('echo "unterminated') == "unparseable"
    no_command = _decide(_payload(command=None))
    assert no_command is not None and "unparseable command" in no_command


# --- F10: the shim end to end ------------------------------------------------------------------

def _run_hook(payload_text, extra_env=None):
    return subprocess.run([sys.executable, "-B", _HOOK], input=payload_text, capture_output=True,
                          text=True, timeout=30, env=dict(os.environ, **(extra_env or {})))


def test_shim_denies_an_enrolled_implementer_in_one_json_write(tmp_path):
    # axis: process contract — a single JSON document with permissionDecision deny, exit 0
    _enrolled_run(tmp_path, deadline_at=_FAR_FUTURE)  # the subprocess reads the real clock
    r = _run_hook(json.dumps(_payload(command="pip install x")))
    assert r.returncode == 0
    assert r.stdout.count("\n") == 1
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "pip install" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_shim_is_silent_for_the_builder_and_for_malformed_stdin(tmp_path):
    # axis: process contract — every other payload prints nothing and exits 0
    _enrolled_run(tmp_path, deadline_at=_FAR_FUTURE)
    builder = _run_hook(json.dumps(_payload(command="pip install x", agent_type=None)))
    assert builder.returncode == 0 and builder.stdout == ""
    for text in ("", "not json", "[1, 2]", "null"):
        r = _run_hook(text)
        assert r.returncode == 0 and r.stdout == ""


def _shim_module():
    spec = importlib.util.spec_from_file_location("implementer_fence_under_test", _HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_shim_main(monkeypatch, payload, raiser):
    monkeypatch.setattr(native_fence, "fence_decision", raiser)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    rc = _shim_module().main()
    return rc, buf.getvalue()


def _boom(payload, now=None):
    raise RuntimeError("boom")


def test_shim_fails_closed_for_an_implementer_when_the_decision_raises(monkeypatch):
    # axis: process contract — a raise denies the implementer with the fail-closed reason
    rc, out = _run_shim_main(monkeypatch, _payload(command="ls"), _boom)
    assert rc == 0
    parsed = json.loads(out)
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert parsed["hookSpecificOutput"]["permissionDecisionReason"] == \
        "superheroes native fence error (fail-closed)"


def test_shim_stays_silent_for_another_agent_when_the_decision_raises(monkeypatch):
    # axis: process contract — a raise never denies the builder or another agent
    for agent_type in (None, "Explore"):
        rc, out = _run_shim_main(monkeypatch, _payload(command="ls", agent_type=agent_type), _boom)
        assert rc == 0 and out == ""


def test_shim_fails_closed_on_a_corrupt_index_entry(tmp_path):
    # axis: process contract — a real internal failure (unreadable index) denies the implementer
    os.makedirs(tmp_path / "index-root")
    _index_file(tmp_path).write_text("{not json")
    r = _run_hook(json.dumps(_payload(command="ls")))
    assert r.returncode == 0
    assert json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"] == \
        "superheroes native fence error (fail-closed)"
