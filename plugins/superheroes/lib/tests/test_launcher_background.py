"""C14 layer 4a — builder lanes launch as claude background sessions through the adapter.

Guarded elements (each has a recorded red→green in bite_proofs/c14_l4a_launcher_background.md):
D1 no claude argv minted outside engine_adapter; D2 the launcher reaches the adapter's builder
argv; D3 a config root that cannot hold a lane refuses; D4 an acknowledgement alone is never a
launched lane, and a refusal is recorded only after a confirmed stop; D5 older readers see a
new lane live (the session pid, not the acknowledging process); D6 the builder role's refusals;
D7 the new `started` fields' grammar and precedence; D9 one background-session handle, built
only from a listing row in the lane's own worktree, and one `_retire` that alone stops a builder
session and confirms the stop by the pid exiting or the id leaving a clean listing — on every
failure branch and on the finished lane's `record-outcome --retire`; D10 one home each for the
config-root refusal tokens and the transcript engagement source; item 3 the launcher's lane
canary reads the lane's transcript through the identity the launcher recorded.
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
import config_dir as cd
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
_REAL_RETIRE = L._retire

BG_ID = "ab12cd34"
SESSION_ID = BG_ID + "-0000-4000-8000-000000000000"


@pytest.fixture(autouse=True)
def _config_root(tmp_path, monkeypatch):
    cfg = tmp_path / "claude-config"
    cfg.mkdir()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cfg))
    return str(cfg)


def _handle(pid, cwd="/wt", cfg="/cfg", bid=BG_ID):
    return L._handle_from_row({"id": bid, "pid": pid, "cwd": cwd}, cfg, cwd)


def _ok_shake(pid_of):
    """A passing handshake whose session pid is ``pid_of(proc)``; the handle is built the one way
    the launcher builds one."""
    def shake(proc, log_path, cwd, config_dir, deadline):
        pid = pid_of(proc)
        return {"ok": True, "backgroundId": BG_ID, "sessionId": SESSION_ID, "pid": pid,
                "handle": _handle(pid, cwd, config_dir)}
    return shake


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
    pure vendor enumeration, or a pure one that is concatenated onto or grown in place.

    Declared boundary: this is a tripwire over the LITERAL shapes an argv is written in (list,
    flag-bearing or starred tuple, concatenation, in-place growth), not a proof over every way
    Python can compute a list — a head spelled through a variable or a join is out of its reach.
    The invariant itself holds by construction: the launcher and the dispatch shell call the
    adapter, and the launcher holds no "claude" list at all."""
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


def test_the_preflight_claude_probe_argv_comes_from_the_adapter():
    # axis: D1 — the preflight's claude no-op is minted by the adapter, not by the probe
    import preflight_probe as pp
    assert list(pp.cross_vendor_no_op_argv("claude")) == ea.claude_cli_argv(["--version"])


def test_claude_cli_argv_is_the_management_verb_home():
    # axis: D1 — the agents/stop argv is minted by the adapter, head and args in order
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
    # axis: D2 — an adapter refusal stops the launch with its token, never a fallback argv
    monkeypatch.setattr(L.engine_adapter, "build_argv_result",
                        lambda *a: {"argv": [], "reason": "untokenizable", "detail": "d"})
    repo = _init_repo(tmp_path / "repo")
    result = L.compose_launch(repo, 656, _valid_premise(repo))
    assert result["ok"] is False
    assert result["reason"] == "builder-argv-refused:untokenizable"


# --- D6: the adapter's builder role ----------------------------------------------------------


def test_builder_argv_shapes():
    # axis: D6 — the builder argv: --bg, the token, --effort only when pinned, prompt after --,
    # and never --restricted or --permission-mode
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
    assert result["reason"] == cd.NOT_A_DIRECTORY == "config-dir-unusable:not-a-directory"
    assert spawned == []
    assert ll.read(repo)["records"] == []


def test_unresolvable_config_root_refuses(tmp_path, monkeypatch):
    # axis: D3 — no absolute root can be derived: refused, never inherited silently
    monkeypatch.setattr(L, "spawn_config_dir", lambda env=None, cwd=None: None)
    monkeypatch.setattr(L, "_claude_seat_pin_gate_applies", lambda env=None: False)
    repo = _init_repo(tmp_path / "repo")
    result = _launch(repo, tmp_path)
    assert result["reason"] == cd.UNRESOLVABLE == "config-dir-unusable:unresolvable"
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
    monkeypatch.setattr(L, "_LISTING_WAIT_SECONDS", 0.3)
    monkeypatch.setattr(L, "_LISTING_POLL_SECONDS", 0.05)
    listings = rows if callable(rows) else (lambda: rows)
    monkeypatch.setattr(L.engine_dispatch, "claude_agents_rows",
                        lambda cfg, cwd: (listings() if listing_ok else None, listing_ok))
    return _REAL_HANDSHAKE(_Ack(rc), str(log), str(wt), str(tmp_path / "cfg"), deadline)


def test_handshake_listed_session_is_a_launch(tmp_path, monkeypatch):
    # axis: D4 — the one passing grade: a listed session in this worktree with its own ids
    shake = _grade(tmp_path, monkeypatch)
    wt = str(tmp_path / "wt")
    assert shake == {"ok": True, "backgroundId": BG_ID, "sessionId": SESSION_ID, "pid": 5150,
                     "handle": L._Handle(BG_ID, 5150, wt, str(tmp_path / "cfg"))}


def test_handshake_waits_for_the_row_to_carry_its_pid(tmp_path, monkeypatch):
    # axis: D4 — a fresh session is listed before its process (live on 2.1.281: no pid for ~1 s);
    # the handshake polls, bounded, and grades the row once the pid is there
    wt = str(tmp_path / "wt")
    calls = []

    def listing():
        calls.append(1)
        return [_row(cwd=wt, pid=None)] if len(calls) < 3 else [_row(cwd=wt)]

    shake = _grade(tmp_path, monkeypatch, rows=listing)
    assert shake["ok"] is True and shake["pid"] == 5150
    assert len(calls) == 3


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
        return {"ok": False, "reason": bo.REFUSAL_SESSION_UNLISTED, "detail": "session-id",
                "backgroundId": BG_ID, "pid": pid}
    return shake


def _listing(monkeypatch, rows_for, listing_ok=True):
    """Stub the per-account listing: ``rows_for(cwd)`` builds the rows for the lane's worktree."""
    monkeypatch.setattr(L, "_LISTING_WAIT_SECONDS", 0.3)
    monkeypatch.setattr(L, "_LISTING_POLL_SECONDS", 0.05)
    monkeypatch.setattr(L.engine_dispatch, "claude_agents_rows", lambda cfg, cwd: (
        rows_for(cwd) if listing_ok else None, listing_ok))


def _retires(monkeypatch, outcome):
    """Stub `_retire`, recording each handle; ``outcome`` is a token or a function of the handle."""
    handles = []
    monkeypatch.setattr(L, "_retire", lambda handle, proc=None: handles.append(handle) or (
        outcome(handle) if callable(outcome) else outcome))
    return handles


def test_refusal_after_ack_is_recorded_only_once_the_stop_is_confirmed(tmp_path, monkeypatch):
    # axis: D4/D9 — the acknowledged session, listed in the worktree, is retired and confirmed →
    # refused at stage spawn, no started, the stop is reported
    monkeypatch.setattr(L, "_background_handshake", _refusing_handshake(None))
    _listing(monkeypatch, lambda cwd: [_row(cwd=cwd)])
    retired = _retires(monkeypatch, "stopped")
    repo = _init_repo(tmp_path / "repo")
    result = _launch(repo, tmp_path, spawn_fn=_make_spawn_fn("exit0"))
    assert result["reason"] == bo.REFUSAL_SESSION_UNLISTED
    assert result["backgroundId"] == BG_ID and result["stop"] == "stopped"
    assert [h.backgroundId for h in retired] == [BG_ID]
    events = _events(repo, result["launchId"])
    assert [r["event"] for r in events] == ["reserved", "refused"]
    assert events[-1]["stage"] == "spawn"


def test_unconfirmed_stop_with_a_known_pid_leaves_a_live_started_lane(tmp_path, monkeypatch):
    # axis: D4/D9 — a session that may still run is never recorded as refused
    session = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                               start_new_session=True)
    try:
        monkeypatch.setattr(L, "_background_handshake", _refusing_handshake(session.pid))
        _listing(monkeypatch, lambda cwd: [_row(cwd=cwd, pid=session.pid)])
        _retires(monkeypatch, "stop-unconfirmed")
        repo = _init_repo(tmp_path / "repo")
        result = _launch(repo, tmp_path, spawn_fn=_make_spawn_fn("exit0"))
        assert result["ok"] is False and result["stop"] == "stop-unconfirmed"
        assert result["unconfirmedSessions"] == [BG_ID]
        events = _events(repo, result["launchId"])
        assert [r["event"] for r in events] == ["reserved", "started"]
        assert events[-1]["pid"] == session.pid
        assert ll.fold(ll.read(repo)["records"])["launches"][result["launchId"]]["terminal"] is False
    finally:
        _kill(session.pid)
        session.wait()


def test_unconfirmed_stop_without_a_pid_leaves_the_lane_reserved(tmp_path, monkeypatch):
    # axis: D4/D9 — no pid to record: reserved-only and nonterminal, the id named for reconciliation
    monkeypatch.setattr(L, "_background_handshake", _refusing_handshake(None))
    _listing(monkeypatch, lambda cwd: [_row(cwd=cwd, pid=None)])
    _retires(monkeypatch, "stop-unconfirmed")
    repo = _init_repo(tmp_path / "repo")
    result = _launch(repo, tmp_path, spawn_fn=_make_spawn_fn("exit0"))
    assert result["backgroundId"] == BG_ID and result["unconfirmedSessions"] == [BG_ID]
    assert [r["event"] for r in _events(repo, result["launchId"])] == ["reserved"]


def test_an_acknowledged_session_listed_elsewhere_is_never_stopped_nor_forgotten(
        tmp_path, monkeypatch):
    # axis: D9 — the ack names this launch's id but its row is outside the worktree: no handle,
    # so nothing is stopped, and the lane is not recorded refused (the session may run)
    monkeypatch.setattr(L, "_background_handshake", _refusing_handshake(5150))
    _listing(monkeypatch, lambda cwd: [_row(cwd=str(tmp_path / "elsewhere"))])
    retired = _retires(monkeypatch, "stopped")
    repo = _init_repo(tmp_path / "repo")
    result = _launch(repo, tmp_path, spawn_fn=_make_spawn_fn("exit0"))
    assert retired == []
    assert result["stop"] == "stop-unconfirmed" and result["unconfirmedSessions"] == [BG_ID]
    assert [r["event"] for r in _events(repo, result["launchId"])] == ["reserved"]


def _unacknowledged(*a):
    return {"ok": False, "reason": bo.REFUSAL_LAUNCH_UNACKNOWLEDGED, "backgroundId": None}


@pytest.mark.parametrize("rows,listing_ok,stop,events,retired_ids", [
    pytest.param([], True, "stopped", ["reserved", "refused"], [], id="no-rows"),
    pytest.param([{}], True, "stopped", ["reserved", "refused"], [BG_ID], id="one-row-stopped"),
    pytest.param([{}], True, "stop-unconfirmed", ["reserved"], [BG_ID], id="one-row-unconfirmed"),
    pytest.param(None, False, "stopped", ["reserved"], [], id="listing-unreadable"),
])
def test_no_acknowledgement_reconciles_the_worktree_before_refusing(
        tmp_path, monkeypatch, rows, listing_ok, stop, events, retired_ids):
    # axis: D4/D9 — with no acknowledged id, every live session listed in the launch's own
    # worktree is retired first; `refused` is recorded only when the listing was readable and
    # every retire confirmed — an unreadable inventory or an unconfirmed stop leaves the lane open
    monkeypatch.setattr(L, "_background_handshake", _unacknowledged)
    _listing(monkeypatch, lambda cwd: [_row(cwd=cwd, pid=None, **r) for r in rows], listing_ok)
    retired = _retires(monkeypatch, stop)
    repo = _init_repo(tmp_path / "repo")
    result = _launch(repo, tmp_path, spawn_fn=_make_spawn_fn("exit0"))
    assert result["reason"] == bo.REFUSAL_LAUNCH_UNACKNOWLEDGED
    assert [h.backgroundId for h in retired] == retired_ids
    assert [r["event"] for r in _events(repo, result["launchId"])] == events
    if events == ["reserved"]:
        assert result["stop"] == "stop-unconfirmed"


def test_no_acknowledgement_never_touches_a_session_outside_the_worktree(tmp_path, monkeypatch):
    # axis: D9 — round-4 finding 1: the per-account listing also holds sibling lanes, review
    # seats and the owner's own agents; with no ack only rows in the lane's worktree yield a
    # handle, so none of those is stopped and the lane is refused (nothing of its own ran)
    monkeypatch.setattr(L, "_background_handshake", _unacknowledged)
    _listing(monkeypatch, lambda cwd: [
        _row(id="11111111", cwd=str(tmp_path / "sibling-lane"), pid=4001),
        _row(id="22222222", cwd=cwd + "/sub", pid=4002),  # --cwd is a PREFIX scope
        _row(id="33333333", cwd=None, pid=4003)])
    retired = _retires(monkeypatch, "stopped")
    repo = _init_repo(tmp_path / "repo")
    result = _launch(repo, tmp_path, spawn_fn=_make_spawn_fn("exit0"))
    assert retired == []
    assert [r["event"] for r in _events(repo, result["launchId"])] == ["reserved", "refused"]


def test_no_acknowledgement_rereads_an_empty_inventory(tmp_path, monkeypatch):
    # axis: D4 — a session listed a moment after the first read is still found and retired
    reads = []
    monkeypatch.setattr(L, "_background_handshake", _unacknowledged)
    _listing(monkeypatch, lambda cwd: reads.append(1) or (
        [] if len(reads) < 3 else [_row(cwd=cwd, pid=None)]))
    retired = _retires(monkeypatch, "stopped")
    repo = _init_repo(tmp_path / "repo")
    result = _launch(repo, tmp_path, spawn_fn=_make_spawn_fn("exit0"))
    assert [h.backgroundId for h in retired] == [BG_ID] and len(reads) == 3
    assert [r["event"] for r in _events(repo, result["launchId"])] == ["reserved", "refused"]


def test_a_live_acknowledger_is_reaped_before_the_inventory(tmp_path, monkeypatch):
    # axis: D4 — a timed-out acknowledger still running could open a session after the
    # inventory; it is reaped before the worktree is listed
    alive_at_listing = []
    monkeypatch.setattr(L, "_LISTING_WAIT_SECONDS", 0.2)
    monkeypatch.setattr(L, "_LISTING_POLL_SECONDS", 0.05)
    monkeypatch.setattr(L, "_background_handshake", lambda proc, *a: (
        _SPAWNED.append(proc) or {"ok": False, "reason": bo.REFUSAL_LAUNCH_FAILED,
                                  "detail": "ack-timeout", "backgroundId": None}))
    monkeypatch.setattr(L.engine_dispatch, "claude_agents_rows", lambda cfg, cwd: (
        alive_at_listing.append(_SPAWNED[-1].poll() is None) or [], True))
    repo = _init_repo(tmp_path / "repo")
    _launch(repo, tmp_path, spawn_fn=_make_spawn_fn("sleep"))
    assert alive_at_listing and not any(alive_at_listing)


_SPAWNED = []


def _live_session():
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"],
                            start_new_session=True)


def _retire_session(session):
    def retire(handle, proc=None):
        assert handle.pid == session.pid
        _kill(session.pid)
        session.wait()
        return "stopped"
    return retire


def test_deadline_in_settle_stops_the_session_before_terminalizing(tmp_path, monkeypatch):
    # axis: D4/D9 — the acknowledging process has exited and the session is a separate process;
    # at the deadline the session is retired and confirmed, then the lane is terminalized
    session = _live_session()
    try:
        monkeypatch.setattr(L, "_background_handshake", _ok_shake(lambda proc: session.pid))
        monkeypatch.setattr(L, "_retire", _retire_session(session))
        repo = _init_repo(tmp_path / "repo")
        monkeypatch.setattr(L, "_observe_session_settle", lambda *a, **k: "deadline")
        result = _launch(repo, tmp_path, spawn_fn=_make_spawn_fn("exit0"))
        assert result["reason"] == "retry-deadline-exceeded", result
        assert result["stop"] == "stopped" and result["backgroundId"] == BG_ID
        info = ll.fold(ll.read(repo)["records"])["launches"][result["launchId"]]
        assert info["terminal"] is True
    finally:
        _kill(session.pid)
        session.wait()


def test_deadline_with_an_unconfirmed_stop_keeps_the_lane_live(tmp_path, monkeypatch):
    # axis: D4/D9 — a session that may still run is never terminalized: the started lane stays
    # open on the ledger and the result hands back its id
    session = _live_session()
    try:
        monkeypatch.setattr(L, "_background_handshake", _ok_shake(lambda proc: session.pid))
        _retires(monkeypatch, "stop-unconfirmed")
        repo = _init_repo(tmp_path / "repo")
        monkeypatch.setattr(L, "_observe_session_settle", lambda *a, **k: "deadline")
        result = _launch(repo, tmp_path, spawn_fn=_make_spawn_fn("exit0"))
        assert result["reason"] == "retry-deadline-exceeded"
        assert result["stop"] == "stop-unconfirmed" and result["backgroundId"] == BG_ID
        info = ll.fold(ll.read(repo)["records"])["launches"][result["launchId"]]
        assert info["terminal"] is False and info["pid"] == session.pid
    finally:
        _kill(session.pid)
        session.wait()


def _reject_first_started(monkeypatch):
    """The ledger refuses the launcher's own `started` append; the repair's append goes through."""
    real_append = ll.append
    monkeypatch.setattr(ll, "append", lambda root, rec, env=None: False
                        if rec.get("event") == "started" and not rec.get("repaired")
                        else real_append(root, rec, env=env))


def test_failed_started_append_with_a_confirmed_stop_terminalizes_through_repair(
        tmp_path, monkeypatch):
    # axis: D4/D9 — round-4 finding 5: the repair itself appends `started`, so only the
    # launcher's own append is refused here; the repaired record carries the SESSION pid (never
    # the acknowledging process's) and the lane reaches a terminal outcome
    session = _live_session()
    acks = []
    try:
        _reject_first_started(monkeypatch)
        monkeypatch.setattr(L, "_background_handshake",
                            _ok_shake(lambda proc: acks.append(proc.pid) or session.pid))
        monkeypatch.setattr(L, "_retire", _retire_session(session))
        repo = _init_repo(tmp_path / "repo")
        result = _launch(repo, tmp_path, spawn_fn=_make_spawn_fn("exit0"))
        assert result["ok"] is False and result["stop"] == "stopped"
        assert result["backgroundId"] == BG_ID and result["sessionId"] == SESSION_ID
        events = _events(repo, result["launchId"])
        assert [r["event"] for r in events] == ["reserved", "started", "outcome"]
        assert events[1]["repaired"] is True
        assert events[1]["pid"] == session.pid and acks and acks[0] != session.pid
        assert ll.fold(ll.read(repo)["records"])["launches"][result["launchId"]]["terminal"]
    finally:
        _kill(session.pid)
        session.wait()


def test_failed_started_append_with_an_unconfirmed_stop_hands_back_the_handle(
        tmp_path, monkeypatch):
    # axis: D4/D9 — the session may still run: nothing is terminalized, the result names it
    session = _live_session()
    try:
        _reject_first_started(monkeypatch)
        monkeypatch.setattr(L, "_background_handshake", _ok_shake(lambda proc: session.pid))
        _retires(monkeypatch, "stop-unconfirmed")
        repo = _init_repo(tmp_path / "repo")
        result = _launch(repo, tmp_path, spawn_fn=_make_spawn_fn("exit0"))
        assert result["ok"] is False and result["stop"] == "stop-unconfirmed"
        assert result["backgroundId"] == BG_ID and result["sessionId"] == SESSION_ID
        assert [r["event"] for r in _events(repo, result["launchId"])] == ["reserved"]
        os.kill(session.pid, 0)  # still running, and the result named it
    finally:
        _kill(session.pid)
        session.wait()


@pytest.mark.parametrize("pid,alive,listed,expected", [
    pytest.param(5150, False, [_row()], "stopped", id="pid-gone"),
    pytest.param(5150, True, [_row()], "stop-unconfirmed", id="pid-outlives-the-wait"),
    pytest.param(None, False, [], "stopped", id="no-pid-id-left-a-clean-listing"),
    pytest.param(None, False, [_row(state="stopped", pid=None)], "stop-unconfirmed",
                 id="no-pid-sticky-stopped-row"),
    pytest.param(None, False, None, "stop-unconfirmed", id="no-pid-listing-unreadable"),
])
def test_retire_confirms_only_by_pid_exit_or_absence_from_a_clean_listing(
        monkeypatch, pid, alive, listed, expected):
    # axis: D9 — round-4 finding 2: the stop command's own exit is never a confirmation; a
    # PID-less session is confirmed stopped only when a cleanly read listing no longer holds it
    calls = []
    monkeypatch.setattr(L.engine_dispatch, "claude_cli",
                        lambda args, cfg, cwd=None, timeout=30: calls.append(args) or (0, "", ""))
    monkeypatch.setattr(L.engine_dispatch, "claude_agents_rows",
                        lambda cfg, cwd: (listed, listed is not None))
    monkeypatch.setattr(L, "_pid_alive", lambda p, proc=None: alive)
    monkeypatch.setattr(L, "_STOP_CONFIRM_SECONDS", 0.3)
    assert _REAL_RETIRE(_handle(pid)) == expected
    assert calls == [["stop", BG_ID]]


def _functions_in(tree):
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    def enclosing(node):
        while node in parents and not isinstance(node, ast.FunctionDef):
            node = parents[node]
        return node.name if isinstance(node, ast.FunctionDef) else None
    return enclosing


def lifecycle_sites(source):
    """(stop sites, handle sites): every function that spells a `stop` command literal, and
    every function that constructs a `_Handle`. By construction each is exactly one function."""
    tree = ast.parse(source)
    enclosing = _functions_in(tree)
    stops, handles = [], []
    for node in ast.walk(tree):
        if (isinstance(node, (ast.List, ast.Tuple)) and node.elts
                and isinstance(node.elts[0], ast.Constant) and node.elts[0].value == "stop"):
            stops.append(enclosing(node))
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "_Handle"):
            handles.append(enclosing(node))
    return stops, handles


def test_one_retire_and_one_handle_constructor_in_the_launcher():
    # axis: D9 — the lifecycle invariant: `_retire` is the only place a builder stop is spelled,
    # `_handle_from_row` the only place a handle is built
    with open(os.path.join(_PLUGIN_ROOT, "lib", "launcher.py"), encoding="utf-8") as fh:
        stops, handles = lifecycle_sites(fh.read())
    assert stops == ["_retire"], "builder-stop-outside-retire: %r" % stops
    assert handles == ["_handle_from_row"], "handle-built-outside-constructor: %r" % handles


@pytest.mark.parametrize("snippet,expected", [
    pytest.param('def f(h):\n    claude_cli(["stop", h.backgroundId], c)\n',
                 (["f"], []), id="stray-stop"),
    pytest.param('def g(row):\n    return _Handle(row["id"], 1, "/wt", "/c")\n',
                 ([], ["g"]), id="stray-handle"),
])
def test_the_lifecycle_census_names_a_stray_site(snippet, expected):
    # axis: D9 — the detector sees a stop or a handle minted outside its one home
    assert lifecycle_sites(snippet) == expected


def _retire_lane_fixture(tmp_path, monkeypatch, *, stops_session):
    """A started lane whose live session the listing reports in the lane's worktree, beside a
    sibling session on the same config root; `claude stop` ends ours when ``stops_session``."""
    session, sibling = _live_session(), _live_session()
    monkeypatch.setattr(L, "_background_handshake", _ok_shake(lambda proc: session.pid))
    repo = _init_repo(tmp_path / "repo")
    result = _launch(repo, tmp_path, spawn_fn=_make_spawn_fn("exit0"), settle=0.2)
    assert result["ok"] is True, result
    stopped = []

    def cli(args, cfg, cwd=None, timeout=30):
        stopped.append(args[1])
        if stops_session and args[1] == BG_ID:
            _kill(session.pid)
            session.wait()
        return 0, "", ""

    monkeypatch.setattr(L.engine_dispatch, "claude_cli", cli)
    _listing(monkeypatch, lambda cwd: [
        _row(cwd=result["worktree"], pid=session.pid),
        _row(id="99999999", cwd=str(tmp_path / "sibling"), pid=sibling.pid)])
    monkeypatch.setattr(L, "_STOP_CONFIRM_SECONDS", 0.5)
    return repo, result["launchId"], session, sibling, stopped


@pytest.mark.parametrize("stops_session", [True, False], ids=["confirmed", "unconfirmed"])
def test_record_outcome_retire_is_the_finished_lanes_path_to_terminal(
        tmp_path, monkeypatch, stops_session):
    # axis: D9 — round-4 finding 3: a finished lane's session is retired (confirmed) through
    # `_retire` and only then is the outcome recorded; an unconfirmed stop records nothing, and
    # the sibling session on the same config root is never touched
    repo, lid, session, sibling, stopped = _retire_lane_fixture(
        tmp_path, monkeypatch, stops_session=stops_session)
    try:
        res = L.record_outcome(repo, lid, "handback", "pr-1", retire=True)
        assert stopped == [BG_ID]
        outcomes = [r for r in _events(repo, lid) if r["event"] == "outcome"]
        if stops_session:
            assert res["ok"] is True, res
            assert [r["outcome"] for r in outcomes] == ["handback"]
        else:
            assert res["ok"] is False and res["reason"] == "stop-unconfirmed"
            assert outcomes == []
        os.kill(sibling.pid, 0)
    finally:
        for proc in (session, sibling):
            _kill(proc.pid)
            proc.wait()


def test_record_outcome_cli_retire_flag(tmp_path, monkeypatch):
    # axis: D9 — the CLI verb reaches the retire path
    repo, lid, session, sibling, stopped = _retire_lane_fixture(
        tmp_path, monkeypatch, stops_session=True)
    try:
        rc = L.main(["record-outcome", "--repo-root", repo, "--launch-id", lid,
                     "--outcome", "handback", "--evidence", "pr-1", "--retire"])
        assert rc == 0 and stopped == [BG_ID]
    finally:
        for proc in (session, sibling):
            _kill(proc.pid)
            proc.wait()


# --- D10: one home for each shared token -----------------------------------------------------


def _string_constants(rel):
    with open(os.path.join(_PLUGIN_ROOT, rel), encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
            and isinstance(n.value, str)]


@pytest.mark.parametrize("token,home", [
    pytest.param("config-dir-unusable:", "lib/config_dir.py", id="config-root-refusals"),
    pytest.param("claude-transcript", "lib/engine_adapter.py", id="engagement-source"),
])
def test_each_shared_token_is_spelled_in_one_home(token, home):
    # axis: D10 — round-4 findings 4 and gap-sweep 2: no producer restates the literal
    spelled = sorted(rel for rel, _path in _plugin_sources()
                     if any(token in c for c in _string_constants(rel)))
    assert spelled == [home], "token-restated-outside-home: %s in %r" % (token, spelled)


def test_config_dir_unusable_classifies_each_root(tmp_path):
    # axis: D10 — the one classifier the launcher and the dispatch shell read
    assert cd.unusable(None) == cd.UNRESOLVABLE
    assert cd.unusable(str(tmp_path / "absent")) == cd.NOT_A_DIRECTORY
    assert cd.unusable(str(tmp_path)) is None


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
        monkeypatch.setattr(L, "_background_handshake", _ok_shake(lambda proc: session.pid))
        repo = _init_repo(tmp_path / "repo")
        result = _launch(repo, tmp_path, spawn_fn=_make_spawn_fn("exit0"), settle=0.3)
        assert result["ok"] is True, result
        lid = result["launchId"]
        stamped = hb.stamp(repo, state="working", phase="build", launch_id=lid)
        assert stamped["ok"] is True, stamped

        live = _run_old_reader(lib, repo, lid, "live")
        assert live["foldOk"] is True, live
        assert live["exited"] is False, "old watch loop reads the new lane as builder-exited"
        assert live["pid"] == session.pid
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
    monkeypatch.setattr(L, "_background_handshake", _ok_shake(lambda proc: proc.pid))
    repo = _init_repo(tmp_path / "repo")
    result = _launch(repo, tmp_path)
    _kill(result["pid"])
    return result["launchId"], ll.read(repo)["records"]


def _with_started(records, **fields):
    out = []
    for rec in records:
        rec = dict(rec)
        if rec["event"] == "started":
            if isinstance(fields.get("envPins"), str):
                # "<KEY>:<value>" edits the REAL pins in one place; EFFORT names the effort pin
                pins = dict(rec["envPins"])
                key, value = fields["envPins"].split(":", 1)
                key = "CLAUDE_CODE_EFFORT_LEVEL" if key == "EFFORT" else key
                if value == "drop":
                    pins.pop(key)
                else:
                    pins[key] = value
                fields = dict(fields, envPins=pins)
            for key, value in fields.items():
                if value is _DROP:
                    rec.pop(key, None)
                else:
                    rec[key] = value
        out.append(rec)
    return out


_DROP = object()


def test_fold_carries_the_started_session_id(tmp_path, monkeypatch):
    # axis: D7 — started.sessionId becomes the lane's session id; a legacy record folds unchanged
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
    pytest.param({"envPins": "EXTRA:1"}, "fold-bad-field:started:envPins", id="extra-key"),
    pytest.param({"envPins": {"CLAUDE_CONFIG_DIR": "/somewhere/else"}},
                 "fold-bad-field:started:envPins", id="root-disagrees-with-reserved"),
    pytest.param({"envPins": "EFFORT:high"}, "fold-bad-field:started:envPins",
                 id="effort-disagrees-with-reserved"),
    pytest.param({"envPins": "EFFORT:drop"}, "fold-bad-field:started:envPins",
                 id="pinned-reservation-without-effort-pin"),
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


# --- item 3: the launcher's seat canary reads the lane's transcript ---------------------------


def _write_transcript(cfg, session_id, tool_ids, folder="-some-worktree", filler=0):
    folder = os.path.join(cfg, "projects", folder)
    os.makedirs(folder, exist_ok=True)
    rows = [{"type": "user", "message": {"role": "user", "content": "go"}}]
    for tool_id in tool_ids:
        rows.append({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": tool_id, "name": "Read", "input": {}}]}})
    rows += [{"type": "assistant", "message": {"content": [{"type": "text", "text": "x" * 64}]}}
             for _ in range(filler)]
    with open(os.path.join(folder, session_id + ".jsonl"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(json.dumps(r) for r in rows) + "\n")


def _canary_lane(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "_background_handshake", _ok_shake(lambda proc: proc.pid))
    repo = _init_repo(tmp_path / "repo")
    result = _launch(repo, tmp_path)
    _kill(result["pid"])
    return repo, result["launchId"]


def test_lane_canary_reads_tool_calls_from_the_recorded_transcript(tmp_path, monkeypatch,
                                                                   _config_root):
    # axis: item 3 (R7) — the launcher's canary counts the lane's transcript tool calls, found
    # through the session id and config root the LAUNCHER recorded
    import seat_canary as sc
    repo, lid = _canary_lane(tmp_path, monkeypatch)
    _write_transcript(_config_root, SESSION_ID, ["t1", "t2", "t2"])
    res = sc.lane_canary(repo, lid)
    assert res == {"ok": True, "reason": None, "launchId": lid, "sessionId": SESSION_ID,
                   "toolCalls": 2, "engaged": True, "engagementSource": "claude-transcript"}


def test_lane_canary_zero_tool_calls_is_not_engaged(tmp_path, monkeypatch, _config_root):
    # axis: item 3 — empty telemetry is not engagement
    import seat_canary as sc
    repo, lid = _canary_lane(tmp_path, monkeypatch)
    _write_transcript(_config_root, SESSION_ID, [])
    res = sc.lane_canary(repo, lid)
    assert res["ok"] is True and res["toolCalls"] == 0 and res["engaged"] is False


@pytest.mark.parametrize("case,reason", [
    pytest.param("no-transcript", "lane-transcript-unresolved", id="no-transcript"),
    pytest.param("unknown-lane", "lane-unknown", id="unknown-lane"),
    pytest.param("no-session", "lane-session-unrecorded", id="legacy-record"),
])
def test_lane_canary_refuses_rather_than_guessing(tmp_path, monkeypatch, _config_root, case,
                                                  reason):
    # axis: item 3 — no recorded identity, no transcript, no lane: a named refusal, never a
    # transcript found some other way
    import seat_canary as sc
    repo, lid = _canary_lane(tmp_path, monkeypatch)
    if case == "unknown-lane":
        lid = "launch-0000000000000000"
    if case == "no-session":
        _write_transcript(_config_root, SESSION_ID, ["t1"])
        records = _with_started(ll.read(repo)["records"], sessionId=_DROP, backgroundId=_DROP)
        monkeypatch.setattr(sc.launch_ledger, "read",
                            lambda repo_root, env=None: {"state": "ok", "records": records})
    res = sc.lane_canary(repo, lid)
    assert res["ok"] is False and res["reason"] == reason and res["engaged"] is False


def test_lane_canary_refuses_two_transcripts_for_one_session(tmp_path, monkeypatch, _config_root):
    # axis: item 3 — the recorded session id resolving to two transcripts is ambiguous, never a
    # pick of one
    import seat_canary as sc
    repo, lid = _canary_lane(tmp_path, monkeypatch)
    _write_transcript(_config_root, SESSION_ID, ["t1"])
    _write_transcript(_config_root, SESSION_ID, ["t1"], folder="-another-worktree")
    res = sc.lane_canary(repo, lid)
    assert res["ok"] is False and res["reason"] == "lane-transcript-ambiguous"


def test_lane_canary_refuses_a_transcript_it_could_only_read_the_tail_of(
        tmp_path, monkeypatch, _config_root):
    # axis: item 3 — gap-sweep 3: past the read cap only the tail is read; the lane's only tool
    # call sits before it, so grading the tail would report an engaged lane as not engaged
    import seat_canary as sc
    repo, lid = _canary_lane(tmp_path, monkeypatch)
    _write_transcript(_config_root, SESSION_ID, ["t1"], filler=64)
    monkeypatch.setattr(sc.engine_dispatch, "MAX_STDOUT_CAPTURE", 2048)
    res = sc.lane_canary(repo, lid)
    assert res["ok"] is False and res["reason"] == "lane-transcript-truncated"
    assert res["engaged"] is False


def test_lane_canary_cli_exit_follows_the_result(tmp_path, monkeypatch, _config_root):
    # axis: item 3 — the CLI exits 1 on a refusal, so a caller cannot read one as engaged
    import seat_canary as sc
    repo, lid = _canary_lane(tmp_path, monkeypatch)
    assert sc.main(["lane", "--repo-root", repo, "--launch-id", lid]) == 1
    _write_transcript(_config_root, SESSION_ID, ["t1"])
    assert sc.main(["lane", "--repo-root", repo, "--launch-id", lid]) == 0
