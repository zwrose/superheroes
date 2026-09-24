"""C14 layer 4a — builder lanes launch as claude background sessions through the adapter.

Guarded elements (each has a recorded red→green in bite_proofs/c14_l4a_launcher_background.md):
D1 no claude argv minted outside engine_adapter; D2 the launcher reaches the adapter's builder
argv; D3 a config root that cannot hold a lane refuses; D4 an acknowledgement alone is never a
launched lane, and a refusal is recorded only after a confirmed stop; D5 older readers see a
new lane live (the session pid, not the acknowledging process); D6 the builder role's refusals;
D7 the new `started` fields' grammar and precedence.
"""
import ast
import io
import json
import os
import signal
import subprocess
import sys
import tarfile
import time

import pytest

import background_outcome as bo
import engine_adapter as ea
import launch_ledger as ll
import heartbeat as hb
import model_registry

from test_launcher import (  # noqa: E402
    L,
    _all_checks,
    _init_repo,
    _make_spawn_fn,
    _valid_premise,
    _autouse_isolated_ledger_root,  # noqa: F401 — autouse fixture, applies here by import
    _autouse_seat_config_matches_spawn,  # noqa: F401 — autouse fixture, applies here by import
)

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
_REPO_ROOT = os.path.normpath(os.path.join(_PLUGIN_ROOT, "..", ".."))
_REAL_HANDSHAKE = L._background_handshake
_REAL_STOP = L._stop_background

BG_ID = "ab12cd34"
SESSION_ID = BG_ID + "-0000-4000-8000-000000000000"


@pytest.fixture(autouse=True)
def _config_root(tmp_path, monkeypatch):
    cfg = tmp_path / "claude-config"
    cfg.mkdir()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cfg))
    return str(cfg)


def _launch(repo, tmp_path, spawn_fn=None, **kw):
    return L.launch_build(
        repo, 656, _valid_premise(repo), _all_checks(), str(tmp_path / "logs"),
        spawn_fn=spawn_fn or _make_spawn_fn("sleep"), settle_seconds=kw.pop("settle", 0.2), **kw,
    )


def _events(repo, launch_id):
    return [r for r in ll.read(repo)["records"] if r.get("launchId") == launch_id]


def _kill(pid):
    try:
        os.killpg(pid, signal.SIGKILL)
    except OSError:
        pass


# --- D1: one home for every claude argv -----------------------------------------------------

_VENDORS = frozenset(model_registry.vendors())
_ADAPTER = os.path.join("lib", "engine_adapter.py")


def _plugin_sources():
    for root, dirs, files in os.walk(_PLUGIN_ROOT):
        dirs[:] = [d for d in dirs if d not in ("tests", "bite_proofs", "__pycache__")]
        for name in files:
            if name.endswith(".py"):
                path = os.path.join(root, name)
                yield os.path.relpath(path, _PLUGIN_ROOT), path


def _claude_headed(node):
    """A list headed by "claude", or a tuple headed by it that carries a dash flag or a starred
    tail. A bare tuple like ``return "claude", source`` is a value pair, not an argv."""
    if not (isinstance(node, (ast.List, ast.Tuple)) and node.elts
            and isinstance(node.elts[0], ast.Constant) and node.elts[0].value == "claude"):
        return False
    if isinstance(node, ast.List):
        return True
    return any(isinstance(e, ast.Starred)
               or (isinstance(e, ast.Constant) and isinstance(e.value, str)
                   and e.value.startswith("-"))
               for e in node.elts[1:])


def _pure_vendor_enumeration(node):
    return all(isinstance(e, ast.Constant) and e.value in _VENDORS for e in node.elts)


def _mutated_names(scope):
    """Names in ``scope`` that are extended, appended to, inserted into, or `+=`-ed."""
    names = set()
    for node in ast.walk(scope):
        if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
              and node.func.attr in ("extend", "append", "insert")
              and isinstance(node.func.value, ast.Name)):
            names.add(node.func.value.id)
    return names


def claude_argv_sites(source, rel):
    """Every place ``source`` mints a claude argv: a literal headed by "claude" that is not a
    pure vendor enumeration, or a pure one that is concatenated onto or grown in place."""
    tree = ast.parse(source)
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    sites = []
    for node in ast.walk(tree):
        if not _claude_headed(node):
            continue
        if not _pure_vendor_enumeration(node):
            sites.append("%s:%d" % (rel, node.lineno))
            continue
        parent = parents.get(node)
        if isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.Add) and parent.left is node:
            sites.append("%s:%d" % (rel, node.lineno))
            continue
        if isinstance(parent, ast.Assign) and all(isinstance(t, ast.Name) for t in parent.targets):
            scope = parent
            while scope in parents and not isinstance(
                    scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
                scope = parents[scope]
            if {t.id for t in parent.targets} & _mutated_names(scope):
                sites.append("%s:%d" % (rel, node.lineno))
    return sites


def test_no_claude_argv_is_minted_outside_the_adapter():
    # axis: D1 — invariant, not a site list: any module but engine_adapter that builds a claude
    # argv (by literal, by concatenation, or by growing a list in place) is named here
    offenders = []
    for rel, path in _plugin_sources():
        if rel == _ADAPTER:
            continue
        with open(path, encoding="utf-8") as fh:
            offenders += claude_argv_sites(fh.read(), rel)
    assert offenders == [], "claude-argv-outside-adapter: %s" % ", ".join(offenders)


@pytest.mark.parametrize("snippet", [
    pytest.param('argv = ["claude", "-p", prompt]\n', id="literal"),
    pytest.param('cmd = ["claude"] + list(args)\n', id="concatenation"),
    pytest.param('def f(args):\n    cmd = ["claude"]\n    cmd.extend(args)\n', id="extend"),
    pytest.param('def f(args):\n    cmd = ["claude"]\n    cmd += args\n', id="augassign"),
    pytest.param('argv = ["claude", *args]\n', id="starred"),
    pytest.param('argv = ("claude", "--bg", prompt)\n', id="tuple-with-flag"),
])
def test_the_census_names_every_construction_shape(snippet):
    # axis: D1 — the detector sees each way a claude argv can be assembled
    assert claude_argv_sites(snippet, "x.py") == ["x.py:%d" % (2 if "def f" in snippet else 1)]


@pytest.mark.parametrize("snippet", [
    'vendors = ["claude"]\n',
    'pool = ["claude", "codex"]\n',
    'def f():\n    return ["claude"]\n',
    'x = {"vendors": ["claude"]}\n',
    'def f():\n    return "claude", SOURCE\n',
])
def test_the_census_leaves_vendor_enumerations_alone(snippet):
    # axis: D1 — a list of vendor NAMES is not an argv
    assert claude_argv_sites(snippet, "x.py") == []


def test_launcher_holds_no_claude_list_at_all():
    # axis: D1 — the DoD's grep: the launcher's hand-built argv is gone, not relocated in it
    with open(os.path.join(_PLUGIN_ROOT, "lib", "launcher.py"), encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    found = [
        node.lineno for node in ast.walk(tree)
        if isinstance(node, (ast.List, ast.Tuple))
        and any(isinstance(e, ast.Constant) and e.value == "claude" for e in node.elts)
    ]
    assert found == [], "claude list literal in launcher.py at lines %r" % found


def test_claude_cli_argv_is_the_management_verb_home():
    assert ea.claude_cli_argv(["stop", BG_ID]) == ["claude", "stop", BG_ID]


# --- D2: the launcher reaches the adapter ----------------------------------------------------


def test_compose_launch_takes_its_argv_from_the_adapter(tmp_path, monkeypatch):
    # axis: D2 — chokepoint: whatever the adapter mints is what the launcher launches
    calls = []

    def fake_build(seat, role_kind, opts):
        calls.append((dict(seat), role_kind, dict(opts)))
        return {"argv": ["ADAPTER-MINTED"], "reason": None}

    monkeypatch.setattr(L.engine_adapter, "build_argv_result", fake_build)
    repo = _init_repo(tmp_path / "repo")
    result = L.compose_launch(repo, 656, _valid_premise(repo), model="sonnet")
    assert result["ok"] is True
    assert result["argv"] == ["ADAPTER-MINTED"]
    seat, role_kind, opts = calls[0]
    assert seat == {"vendor": "claude", "model": "sonnet", "effort": None}
    assert role_kind == ea.ROLE_KIND_BUILDER
    assert opts == {"claudeMode": ea.MODE_BACKGROUND, "prompt": result["prompt"]}


def test_compose_launch_surfaces_an_adapter_refusal(tmp_path, monkeypatch):
    monkeypatch.setattr(L.engine_adapter, "build_argv_result",
                        lambda *a: {"argv": [], "reason": "untokenizable", "detail": "d"})
    repo = _init_repo(tmp_path / "repo")
    result = L.compose_launch(repo, 656, _valid_premise(repo))
    assert result["ok"] is False
    assert result["reason"] == "builder-argv-refused:untokenizable"


# --- D6: the adapter's builder role ----------------------------------------------------------


def test_builder_argv_shapes():
    seat = {"vendor": "claude", "model": "opus", "effort": "medium"}
    opts = {"claudeMode": ea.MODE_BACKGROUND, "prompt": "P"}
    assert ea.build_argv_result(seat, ea.ROLE_KIND_BUILDER, opts)["argv"] == [
        "claude", "--bg", "--model", "opus", "--effort", "medium", "--", "P"]
    inherit = dict(seat, model="sonnet", effort=None)
    assert ea.build_argv_result(inherit, ea.ROLE_KIND_BUILDER, opts)["argv"] == [
        "claude", "--bg", "--model", "sonnet", "--", "P"]


@pytest.mark.parametrize("seat,opts,token", [
    pytest.param({"vendor": "claude", "model": "opus", "effort": "medium"},
                 {"prompt": "P"}, "builder-requires-background", id="no-mode"),
    pytest.param({"vendor": "claude", "model": "opus", "effort": "medium"},
                 {"claudeMode": "print", "prompt": "P"}, "builder-requires-background",
                 id="print-mode"),
    pytest.param({"vendor": "codex", "model": "gpt-5.6-sol", "effort": "xhigh"},
                 {"claudeMode": "background", "prompt": "P"}, "claude-mode-unsupported",
                 id="codex"),
    pytest.param({"vendor": "cursor", "model": "composer-2.5", "effort": None},
                 {"claudeMode": "background", "prompt": "P"}, "claude-mode-unsupported",
                 id="cursor"),
    pytest.param({"vendor": "claude", "model": "opus", "effort": "bogus"},
                 {"claudeMode": "background", "prompt": "P"}, "invalid-model-effort",
                 id="bad-effort"),
    pytest.param({"vendor": "claude", "model": "fable", "effort": None},
                 {"claudeMode": "background", "prompt": "P"}, "fable-unrunnable", id="fable"),
])
def test_builder_role_refusals(seat, opts, token):
    # axis: D6 — each refusal names its own token; a wrong token is red
    result = ea.build_argv_result(seat, ea.ROLE_KIND_BUILDER, opts)
    assert result["argv"] == []
    assert result["reason"] == token


# --- D3: the config root must be able to hold a lane -----------------------------------------


def test_missing_config_root_refuses_before_anything_runs(tmp_path, monkeypatch):
    # axis: D3 — the dispatch shell's token, before any reservation, worktree or child
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "no-such-root"))
    spawned = []
    repo = _init_repo(tmp_path / "repo")
    result = _launch(repo, tmp_path, spawn_fn=lambda *a: spawned.append(a))
    assert result["ok"] is False
    assert result["reason"] == L.CONFIG_DIR_NOT_A_DIRECTORY == "config-dir-unusable:not-a-directory"
    assert spawned == []
    assert ll.read(repo)["records"] == []


def test_unresolvable_config_root_refuses(tmp_path, monkeypatch):
    # axis: D3 — no absolute root can be derived: refused, never inherited silently
    monkeypatch.setattr(L, "spawn_config_dir", lambda env=None, cwd=None: None)
    monkeypatch.setattr(L, "_claude_seat_pin_gate_applies", lambda env=None: False)
    repo = _init_repo(tmp_path / "repo")
    result = _launch(repo, tmp_path)
    assert result["reason"] == L.CONFIG_DIR_UNRESOLVABLE == "config-dir-unusable:unresolvable"
    assert ll.read(repo)["records"] == []


def test_config_root_is_rechecked_at_the_spawn_boundary(tmp_path, monkeypatch, _config_root):
    # axis: D3 — a root that vanishes after the early gate refuses at spawn, accounted
    real_create = L.create_build_worktree

    def create_then_remove_root(*a, **k):
        result = real_create(*a, **k)
        os.rmdir(_config_root)
        return result

    monkeypatch.setattr(L, "create_build_worktree", create_then_remove_root)
    spawned = []
    repo = _init_repo(tmp_path / "repo")
    result = _launch(repo, tmp_path, spawn_fn=lambda *a: spawned.append(a))
    assert result["reason"] == "config-dir-unusable:not-a-directory"
    assert spawned == []
    events = [r["event"] for r in _events(repo, result["launchId"])]
    assert events == ["reserved", "refused"]


# --- D4: grading the background launch -------------------------------------------------------


class _Ack:
    """The acknowledging process: it has exited with ``rc`` (None = still running)."""

    def __init__(self, rc, pid=424242):
        self.rc = rc
        self.pid = pid

    def poll(self):
        return self.rc


def _row(**over):
    row = {"id": BG_ID, "kind": "background", "sessionId": SESSION_ID, "pid": 5150,
           "cwd": None, "state": "working"}
    row.update(over)
    return row


def _grade(tmp_path, monkeypatch, *, rc=0, ack="backgrounded · %s\n" % BG_ID,
           rows=None, listing_ok=True, deadline=None):
    wt = tmp_path / "wt"
    wt.mkdir(exist_ok=True)
    log = tmp_path / "ack.stdout"
    log.write_text(ack, encoding="utf-8")
    if rows is None:
        rows = [_row(cwd=str(wt))]
    monkeypatch.setattr(L.engine_dispatch, "claude_agents_rows",
                        lambda cfg, cwd: (rows if listing_ok else None, listing_ok))
    return _REAL_HANDSHAKE(_Ack(rc), str(log), str(wt), str(tmp_path / "cfg"), deadline)


def test_handshake_listed_session_is_a_launch(tmp_path, monkeypatch):
    shake = _grade(tmp_path, monkeypatch)
    assert shake == {"ok": True, "backgroundId": BG_ID, "sessionId": SESSION_ID, "pid": 5150}


@pytest.mark.parametrize("kw,token,detail", [
    pytest.param({"ack": ""}, bo.REFUSAL_LAUNCH_UNACKNOWLEDGED, None, id="no-ack"),
    pytest.param({"rc": 1}, bo.REFUSAL_LAUNCH_FAILED, "exit:1", id="nonzero"),
    pytest.param({"rc": None, "deadline": 0}, bo.REFUSAL_LAUNCH_FAILED, "ack-timeout",
                 id="ack-timeout"),
    pytest.param({"listing_ok": False}, bo.REFUSAL_AGENTS_UNREADABLE, "row-absent",
                 id="listing-unreadable"),
    pytest.param({"rows": []}, bo.REFUSAL_SESSION_UNLISTED, "row-absent", id="row-absent"),
    pytest.param({"rows": [_row(sessionId="ffffffff-0000-4000-8000-000000000000")]},
                 bo.REFUSAL_SESSION_UNLISTED, "session-id", id="session-id-not-its-own"),
    pytest.param({"rows": [_row(pid=None)]}, bo.REFUSAL_SESSION_UNLISTED, "pid", id="no-pid"),
    pytest.param({"rows": [_row(cwd="/elsewhere")]}, bo.REFUSAL_SESSION_UNLISTED, "cwd",
                 id="other-worktree"),
])
def test_an_acknowledgement_alone_is_not_a_launch(tmp_path, monkeypatch, kw, token, detail):
    # axis: D4 — every way short of a listed session in this worktree refuses with its token
    shake = _grade(tmp_path, monkeypatch, **kw)
    assert shake["ok"] is False
    assert shake["reason"] == token
    assert shake.get("detail") == detail


def _refusing_handshake(pid):
    def shake(proc, log_path, cwd, config_dir, deadline):
        return {"ok": False, "reason": bo.REFUSAL_SESSION_UNLISTED, "detail": "cwd",
                "backgroundId": BG_ID, "pid": pid}
    return shake


def test_refusal_after_ack_is_recorded_only_once_the_stop_is_confirmed(tmp_path, monkeypatch):
    # axis: D4 — confirmed stop → refused at stage spawn, no started, the stop is reported
    stops = []
    monkeypatch.setattr(L, "_background_handshake", _refusing_handshake(None))
    monkeypatch.setattr(L, "_stop_background", lambda *a, **k: stops.append(a) or "stopped")
    repo = _init_repo(tmp_path / "repo")
    result = _launch(repo, tmp_path, spawn_fn=_make_spawn_fn("exit0"))
    assert result["reason"] == bo.REFUSAL_SESSION_UNLISTED
    assert result["backgroundId"] == BG_ID and result["stop"] == "stopped"
    assert stops and stops[0][0] == BG_ID
    events = _events(repo, result["launchId"])
    assert [r["event"] for r in events] == ["reserved", "refused"]
    assert events[-1]["stage"] == "spawn"


def test_unconfirmed_stop_with_a_known_pid_leaves_a_live_started_lane(tmp_path, monkeypatch):
    # axis: D4 — a session that may still run is never recorded as refused
    session = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                               start_new_session=True)
    try:
        monkeypatch.setattr(L, "_background_handshake", _refusing_handshake(session.pid))
        monkeypatch.setattr(L, "_stop_background", lambda *a, **k: "stop-unconfirmed")
        repo = _init_repo(tmp_path / "repo")
        result = _launch(repo, tmp_path, spawn_fn=_make_spawn_fn("exit0"))
        assert result["ok"] is False and result["stop"] == "stop-unconfirmed"
        events = _events(repo, result["launchId"])
        assert [r["event"] for r in events] == ["reserved", "started"]
        assert events[-1]["pid"] == session.pid
        assert ll.fold(ll.read(repo)["records"])["launches"][result["launchId"]]["terminal"] is False
    finally:
        _kill(session.pid)
        session.wait()


def test_unconfirmed_stop_without_a_pid_leaves_the_lane_reserved(tmp_path, monkeypatch):
    # axis: D4 — no pid to record: reserved-only and nonterminal, the id named for reconciliation
    monkeypatch.setattr(L, "_background_handshake", _refusing_handshake(None))
    monkeypatch.setattr(L, "_stop_background", lambda *a, **k: "stop-unconfirmed")
    repo = _init_repo(tmp_path / "repo")
    result = _launch(repo, tmp_path, spawn_fn=_make_spawn_fn("exit0"))
    assert result["backgroundId"] == BG_ID
    assert [r["event"] for r in _events(repo, result["launchId"])] == ["reserved"]


def test_no_acknowledgement_means_nothing_to_stop(tmp_path, monkeypatch):
    stops = []
    monkeypatch.setattr(L, "_background_handshake", lambda *a: {
        "ok": False, "reason": bo.REFUSAL_LAUNCH_UNACKNOWLEDGED, "backgroundId": None})
    monkeypatch.setattr(L, "_stop_background", lambda *a, **k: stops.append(a) or "stopped")
    repo = _init_repo(tmp_path / "repo")
    result = _launch(repo, tmp_path, spawn_fn=_make_spawn_fn("exit0"))
    assert result["reason"] == bo.REFUSAL_LAUNCH_UNACKNOWLEDGED
    assert stops == []
    assert [r["event"] for r in _events(repo, result["launchId"])] == ["reserved", "refused"]


@pytest.mark.parametrize("rc,pid,alive,expected", [
    pytest.param(1, None, False, "stop-unconfirmed", id="stop-command-failed"),
    pytest.param(0, None, False, "stopped", id="no-pid-command-confirms"),
    pytest.param(0, 5150, False, "stopped", id="pid-gone"),
    pytest.param(0, 5150, True, "stop-unconfirmed", id="pid-outlives-the-wait"),
])
def test_stop_is_issued_unconditionally_and_confirmed(monkeypatch, rc, pid, alive, expected):
    # axis: D4 — the stop never trusts the listing's state; confirmation is the pid or the command
    calls = []
    monkeypatch.setattr(L.engine_dispatch, "claude_cli",
                        lambda args, cfg, cwd=None, timeout=30: calls.append(args) or (rc, "", ""))
    monkeypatch.setattr(L, "_pid_alive", lambda p, proc=None: alive)
    monkeypatch.setattr(L, "_STOP_CONFIRM_SECONDS", 0.3)
    assert _REAL_STOP(BG_ID, "/cfg", "/wt", pid) == expected
    assert calls == [["stop", BG_ID]]


# --- D5: older readers see the new lane live -------------------------------------------------

_OLD_READER_SHAS = (
    ("8e9a12a00c0f6e791bb889d85e30f9712f85b1de", True),   # origin/main at this layer's launch
    ("5817cc772a664ad0c76813eccbcbd41018ca8643", False),  # this layer's base (C14 3c)
)

_OLD_READER_SCRIPT = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
import heartbeat as hb, launch_ledger as ll, wave_watch as ww
repo, lid, phase = sys.argv[2], sys.argv[3], sys.argv[4]
folded = ll.fold(ll.read(repo)["records"])
out = {"foldOk": folded["ok"], "foldReason": folded.get("reason")}
if folded["ok"]:
    info = folded["launches"][lid]
    out["pid"] = info.get("pid")
    exited, _stale = ww._evaluate_pid_signals({lid: info}, [], set())
    out["exited"] = exited is not None
    beat = hb.read_heartbeat(repo, lid)
    out["heartbeat"] = [beat.get("class"), beat.get("state")]
    if phase in ("live", "gone"):
        out["recordOutcome"] = ll.record_outcome(repo, lid, "handback", "old-reader-compat")
print(json.dumps(out))
"""


def _old_reader(tmp_path, sha, required):
    have = subprocess.run(["git", "-C", _REPO_ROOT, "cat-file", "-e", sha + "^{commit}"],
                          capture_output=True)
    if have.returncode != 0:
        if required:
            pytest.fail("old-reader sha %s is required and absent from this checkout" % sha)
        pytest.skip("layer base %s absent (stack squash-merged); main's pin carries the proof"
                    % sha[:8])
    dest = tmp_path / ("reader-" + sha[:8])
    if not dest.exists():
        blob = subprocess.run(["git", "-C", _REPO_ROOT, "archive", sha, "plugins/superheroes/lib"],
                              capture_output=True, check=True).stdout
        with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
            tar.extractall(str(dest))
    return str(dest / "plugins" / "superheroes" / "lib")


def _run_old_reader(lib, repo, lid, phase):
    proc = subprocess.run([sys.executable, "-B", "-c", _OLD_READER_SCRIPT, lib, repo, lid, phase],
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("sha,required", _OLD_READER_SHAS, ids=["main", "layer-base"])
def test_older_readers_see_a_background_lane_live(tmp_path, monkeypatch, sha, required):
    # axis: D5 — the acknowledging process exits at once (exit0 stand-in); the session is a
    # separate live process whose pid the listing reports. The old fold reads the new record,
    # the old watch loop reads the lane live, the old heartbeat reader reads the lane's stamp,
    # and the old record-outcome refuses while the session lives and accepts once it is gone.
    lib = _old_reader(tmp_path, sha, required)
    session = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"],
                               start_new_session=True)
    try:
        monkeypatch.setattr(L, "_background_handshake", lambda proc, *a: {
            "ok": True, "backgroundId": BG_ID, "sessionId": SESSION_ID, "pid": session.pid})
        repo = _init_repo(tmp_path / "repo")
        result = _launch(repo, tmp_path, spawn_fn=_make_spawn_fn("exit0"), settle=0.3)
        assert result["ok"] is True, result
        lid = result["launchId"]
        stamped = hb.stamp(repo, state="working", phase="build", launch_id=lid)
        assert stamped["ok"] is True, stamped

        live = _run_old_reader(lib, repo, lid, "live")
        assert live["foldOk"] is True, live
        assert live["pid"] == session.pid
        assert live["exited"] is False
        assert live["heartbeat"][1] == "working"
        assert live["recordOutcome"]["ok"] is False
        assert live["recordOutcome"]["reason"].startswith("terminal-child-live")
    finally:
        _kill(session.pid)
        session.wait()
    gone = _run_old_reader(lib, repo, lid, "gone")
    assert gone["exited"] is True
    assert gone["recordOutcome"]["ok"] is True, gone


# --- D7: the new `started` fields ------------------------------------------------------------


def _launched_records(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "_background_handshake", lambda proc, *a: {
        "ok": True, "backgroundId": BG_ID, "sessionId": SESSION_ID, "pid": proc.pid})
    repo = _init_repo(tmp_path / "repo")
    result = _launch(repo, tmp_path)
    _kill(result["pid"])
    return result["launchId"], ll.read(repo)["records"]


def _with_started(records, **fields):
    out = []
    for rec in records:
        rec = dict(rec)
        if rec["event"] == "started":
            for key, value in fields.items():
                if value is _DROP:
                    rec.pop(key, None)
                else:
                    rec[key] = value
        out.append(rec)
    return out


_DROP = object()


def test_fold_carries_the_started_session_id(tmp_path, monkeypatch):
    lid, records = _launched_records(tmp_path, monkeypatch)
    info = ll.fold(records)["launches"][lid]
    assert info["sessionId"] == SESSION_ID and info["backgroundId"] == BG_ID
    legacy = ll.fold(_with_started(records, sessionId=_DROP, backgroundId=_DROP, envPins=_DROP))
    assert legacy["ok"] is True and legacy["launches"][lid]["sessionId"] is None


@pytest.mark.parametrize("fields,reason", [
    pytest.param({"backgroundId": "AB12CD34"}, "fold-bad-field:started:backgroundId", id="upper"),
    pytest.param({"backgroundId": "ab12cd3"}, "fold-bad-field:started:backgroundId", id="short"),
    pytest.param({"sessionId": "ffffffff-0000-4000-8000-000000000000"},
                 "fold-bad-field:started:sessionId", id="not-its-own"),
    pytest.param({"sessionId": BG_ID + "-not-a-uuid"}, "fold-bad-field:started:sessionId",
                 id="not-uuid"),
    pytest.param({"backgroundId": _DROP}, "fold-bad-field:started:sessionId",
                 id="session-without-background"),
    pytest.param({"envPins": {"CLAUDE_CONFIG_DIR": "relative"}},
                 "fold-bad-field:started:envPins", id="relative-root"),
    pytest.param({"envPins": {"CLAUDE_CODE_EFFORT_LEVEL": "medium"}},
                 "fold-bad-field:started:envPins", id="no-root"),
    pytest.param({"envPins": {"CLAUDE_CONFIG_DIR": "/x", "EXTRA": "1"}},
                 "fold-bad-field:started:envPins", id="extra-key"),
    pytest.param({"envPins": {"CLAUDE_CONFIG_DIR": "/somewhere/else"}},
                 "fold-bad-field:started:envPins", id="root-disagrees-with-reserved"),
])
def test_fold_refuses_each_malformed_started_field(tmp_path, monkeypatch, fields, reason):
    # axis: D7 — one rule per case; the refusal names the field
    _lid, records = _launched_records(tmp_path, monkeypatch)
    folded = ll.fold(_with_started(records, **fields))
    assert folded["ok"] is False
    assert folded["reason"] == reason


def test_fold_refuses_a_reserved_session_id_that_disagrees(tmp_path, monkeypatch):
    # axis: D7 — precedence: started wins; a disagreeing reserved id is a corrupt stream
    _lid, records = _launched_records(tmp_path, monkeypatch)
    for value, ok in (("ffffffff-0000-4000-8000-000000000000", False), (SESSION_ID, True)):
        mixed = [dict(r, sessionId=value) if r["event"] == "reserved" else r for r in records]
        folded = ll.fold(mixed)
        assert folded["ok"] is ok
        if not ok:
            assert folded["reason"] == "fold-bad-field:started:sessionId"


# --- item 3: the seat canary on a background claude seat -------------------------------------


def test_seat_canary_threads_the_claude_mode_and_the_telemetry_source():
    import seat_canary as sc
    seen = {}

    def fake_dispatch(**kw):
        seen.update(kw)
        return {"ok": True, "findings": [], "investigated": ["lib/x.py"],
                "engagement": {"read": "engaged", "toolCalls": 7, "source": "claude-transcript"}}

    res = sc.run_canary("security-reviewer",
                        {"vendor": "claude", "model": "sonnet-5", "effort": "high",
                         "tier": "reviewer"},
                        repo_root="/r", dispatch=fake_dispatch, claude_mode="background")
    assert seen["claude_mode"] == "background"
    assert res["evidence"]["toolCalls"] == 7
    assert res["evidence"]["engagementSource"] == "claude-transcript"
    codex_seen = {}
    sc.run_canary("security-reviewer",
                  {"vendor": "codex", "model": "gpt-5.6-terra", "effort": "high",
                   "tier": "reviewer"},
                  repo_root="/r", dispatch=lambda **kw: codex_seen.update(kw) or {})
    assert codex_seen and "claude_mode" not in codex_seen


def test_seat_canary_cli_accepts_a_background_claude_probe(monkeypatch):
    import seat_canary as sc
    seen = {}
    monkeypatch.setattr(sc, "run_canary", lambda *a, **k: seen.update(k) or {})
    assert sc.main(["probe", "--seat-key", "s", "--tier", "reviewer", "--engine", "claude",
                    "--engine-model", "sonnet", "--effort", "medium", "--repo-root", "/r",
                    "--claude-mode", "background"]) == 0
    assert seen["claude_mode"] == "background"
