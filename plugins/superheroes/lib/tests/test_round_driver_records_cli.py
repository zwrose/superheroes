"""#1196 WO-B: CLI-path round-records producer, submit-accept atomicity, corrupt-resume park."""
import ast
import importlib.util
import json
import os

import pytest

from test_round_driver import _guard_argv

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")
RM = _load("review_memory")
RR = _load("round_records")
RC = RD.round_commit

DIFF = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
        "@@ -1 +1,2 @@\n-old\n+new\n+more\n")
HEAD = "abc123def4567890abcdef1234567890abcdef12"
_A_FINDING = {"title": "bug", "severity": "Important", "file": "f.py", "line": 1}


def _cfg(**over):
    base = {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF, "fixerVendor": "claude"}
    base.update(over)
    return base


def _responder(round1_findings=None):
    def respond(phase, payload, rnd):
        if phase == RD.P_PANEL:
            dims = payload.get("dimensions") or list(RD.DIMENSIONS)
            seats = {d: {"findings": []} for d in dims}
            if rnd == 1 and round1_findings:
                seats[dims[0]] = {"findings": list(round1_findings)}
            return {"seats": seats}
        if phase == RD.P_VERIFIERS:
            return {"verdicts": [
                {"id": i, "verdict": "CONFIRMED", "evidence": "ran"}
                for c in payload.get("clusters", []) for i in c.get("ids", [])]}
        if phase == RD.P_SYNTHESIS:
            return {"grouping": None}
        if phase == RD.P_GAPSWEEP:
            return {"findings": []}
        if phase == RD.P_AUDITS:
            return {"results": [
                {"id": t["id"], "ruling": "discharged", "reason": "r", "evidence": "e",
                 "auditorVendor": t.get("auditorVendor")} for t in payload.get("targets", [])],
                    "collectionManifest": {t["id"]: t.get("auditorVendor")
                                           for t in payload.get("targets", [])}}
        if phase == RD.P_SCOPED:
            return {"findings": []}
        if phase == RD.P_FIXER:
            return {"fixes": [], "headDiff": HEAD, "changedSubjects": ["Code"]}
        if phase == RD.P_VERIFY:
            return {"result": "pass"}
        return {}

    return respond


def _expected_panel_records_bytes(session_dir, respond, n):
    art = respond(n["phase"], n["payload"], n["round"])
    ok, state = RD.load_state(session_dir)
    assert ok and state is not None
    RD._fold(state, state["config"], n["phase"], art)
    payload = RD._round_records_payload(state, state["config"])
    assert payload["outcome"] == "ready", payload
    return RM.records_bytes(payload["records"])


def test_commit_recover_call_sites_always_use_kind_dispatch(capsys):
    """F1 census: every ``_commit_recover_or_refuse`` call recovers with kind dispatch in force."""
    driver_path = os.path.join(_LIB, "round_driver.py")
    source = open(driver_path, encoding="utf-8").read()
    tree = ast.parse(source, filename=driver_path)
    recover_fn = None
    calls = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_commit_recover_or_refuse":
            recover_fn = node
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "_commit_recover_or_refuse":
            calls.append(node)
        elif (isinstance(func, ast.Attribute)
              and func.attr == "_commit_recover_or_refuse"):
            calls.append(node)
    assert recover_fn is not None, "_commit_recover_or_refuse must exist"
    fn_source = ast.get_source_segment(source, recover_fn)
    assert fn_source is not None
    assert "_sidecar_resolver_for_recover_dispatch" in fn_source, (
        "chokepoint must default sidecar_resolver_for to kind dispatch")
    assert calls, "expected at least one _commit_recover_or_refuse call site"
    census_lines = []
    for call in calls:
        resolver_kw = None
        for kw in call.keywords:
            if kw.arg == "sidecar_resolver_for":
                resolver_kw = kw
                break
        if resolver_kw is None:
            census_lines.append("ok: default kind dispatch via chokepoint")
            continue
        if (isinstance(resolver_kw.value, ast.Call)
                and isinstance(resolver_kw.value.func, ast.Name)
                and resolver_kw.value.func.id == "_sidecar_resolver_for_recover_dispatch"):
            census_lines.append("ok: explicit kind dispatch resolver")
            continue
        pytest.fail("call site passes a non-dispatch sidecar_resolver_for: %s"
                    % ast.get_source_segment(source, call))
    print("commit_recover_or_refuse census (%d call sites):" % len(calls))
    for line in census_lines:
        print("  %s" % line)
    captured = capsys.readouterr()
    assert "chokepoint must default" not in captured.out


def _stop_at_kind(monkeypatch, kind, stop_at, n=0):
    real = RC.begin
    counts = {}

    def wrapper(session_dir, commit_kind, **kw):
        idx = counts.get(commit_kind, 0)
        if commit_kind == kind and idx == n:
            kw["stop_at"] = stop_at
        counts[commit_kind] = idx + 1
        return real(session_dir, commit_kind, **kw)

    monkeypatch.setattr(RD.round_commit, "begin", wrapper)


def _records_panel_submit_setup(tmp_path):
    records = tmp_path / "round-records.json"
    before_bytes = RM.records_bytes([])
    records.write_bytes(before_bytes)
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir, exist_ok=True)
    cfg = _cfg(dimensions=["test-reviewer"], recordsPath=str(records))
    respond = _responder(round1_findings=[_A_FINDING])
    n = RD.cmd_next(session_dir, cfg)
    assert n["ok"], n
    assert n["phase"] == RD.P_PANEL, n
    return session_dir, records, before_bytes, cfg, respond, n


def test_cmd_next_corrupt_non_mapping_member_parks_cannot_certify(tmp_path):
  records = tmp_path / "records.json"
  records.write_text("[null]")
  session_dir = str(tmp_path)
  cfg = _cfg(dimensions=["test-reviewer"], recordsPath=str(records))
  out = RD.cmd_next(session_dir, cfg)
  assert out["ok"], out
  assert out["phase"] == RD.P_TERMINAL
  assert out["payload"]["verdict"] == "cannot-certify"
  assert out["payload"]["certification"]["shape"] is None
  journal = RD.read_journal(session_dir)
  assert any(e.get("outcome") == "resume-corrupt-park" for e in journal)


def test_cmd_next_corrupt_malformed_json_parks_cannot_certify(tmp_path):
  records = tmp_path / "records.json"
  records.write_text("{not valid json")
  session_dir = str(tmp_path)
  cfg = _cfg(dimensions=["test-reviewer"], recordsPath=str(records))
  out = RD.cmd_next(session_dir, cfg)
  assert out["ok"], out
  assert out["phase"] == RD.P_TERMINAL
  assert out["payload"]["verdict"] == "cannot-certify"
  journal = RD.read_journal(session_dir)
  assert any(e.get("outcome") == "resume-corrupt-park" for e in journal)


def test_submit_records_staged_crash_leaves_file_byte_identical(tmp_path, monkeypatch):
  session_dir, records, before_bytes, cfg, respond, n = _records_panel_submit_setup(tmp_path)
  _stop_at_kind(monkeypatch, "submit-accept", "staged")
  with pytest.raises(RC.StopPoint):
    RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"],
                  respond(n["phase"], n["payload"], n["round"]))
  assert records.read_bytes() == before_bytes


def test_submit_records_sealed_crash_recovers_exact_bytes(tmp_path, monkeypatch):
  session_dir, records, before_bytes, cfg, respond, n = _records_panel_submit_setup(tmp_path)
  art = respond(n["phase"], n["payload"], n["round"])
  expected_bytes = _expected_panel_records_bytes(session_dir, respond, n)
  before_state = open(os.path.join(session_dir, RD.STATE_FILE), "rb").read()
  _stop_at_kind(monkeypatch, "submit-accept", "sealed")
  with pytest.raises(RC.StopPoint):
    RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"], art)
  assert records.read_bytes() == before_bytes
  assert open(os.path.join(session_dir, RD.STATE_FILE), "rb").read() == before_state
  out = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"], art)
  assert out["ok"], out
  assert records.read_bytes() == expected_bytes
  assert open(os.path.join(session_dir, RD.STATE_FILE), "rb").read() != before_state


def test_submit_records_part0_crash_recovers_exact_bytes(tmp_path, monkeypatch):
  session_dir, records, before_bytes, cfg, respond, n = _records_panel_submit_setup(tmp_path)
  art = respond(n["phase"], n["payload"], n["round"])
  expected_bytes = _expected_panel_records_bytes(session_dir, respond, n)
  before_state = open(os.path.join(session_dir, RD.STATE_FILE), "rb").read()
  _stop_at_kind(monkeypatch, "submit-accept", "part:0")
  with pytest.raises(RC.StopPoint):
    RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"], art)
  assert records.read_bytes() == before_bytes
  assert open(os.path.join(session_dir, RD.STATE_FILE), "rb").read() != before_state
  out = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"], art)
  assert out["ok"], out
  assert records.read_bytes() == expected_bytes


def test_next_records_sealed_crash_recovers_exact_bytes(tmp_path, monkeypatch):
  session_dir, records, before_bytes, cfg, respond, n = _records_panel_submit_setup(tmp_path)
  art = respond(n["phase"], n["payload"], n["round"])
  expected_bytes = _expected_panel_records_bytes(session_dir, respond, n)
  before_state = open(os.path.join(session_dir, RD.STATE_FILE), "rb").read()
  _stop_at_kind(monkeypatch, "submit-accept", "sealed")
  with pytest.raises(RC.StopPoint):
    RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"], art)
  assert records.read_bytes() == before_bytes
  assert open(os.path.join(session_dir, RD.STATE_FILE), "rb").read() == before_state
  out = RD.cmd_next(session_dir)
  assert out["ok"], out
  assert records.read_bytes() == expected_bytes
  assert open(os.path.join(session_dir, RD.STATE_FILE), "rb").read() != before_state


def test_submit_hash_mismatch_leaves_records_file_byte_identical(tmp_path):
  session_dir, records, before_bytes, cfg, respond, n = _records_panel_submit_setup(tmp_path)
  out = RD.cmd_submit(session_dir, n["phase"], n["attempt"], "deadbeef", respond(n["phase"],
                                                                                  n["payload"],
                                                                                  n["round"]))
  assert out["ok"] is False
  assert "hash" in out["reason"]
  assert records.read_bytes() == before_bytes


def test_cli_and_run_loop_records_files_are_byte_identical(tmp_path):
  """DoD row 4 (narrowed): the CLI sidecar and library ``_persist_round_records`` land the same
  bytes when the post-fold state feeding ``_round_records_payload`` is equivalent."""
  finding = dict(_A_FINDING)
  records_cli = tmp_path / "cli-records.json"
  records_loop = tmp_path / "loop-records.json"
  empty_bytes = RM.records_bytes([])
  records_cli.write_bytes(empty_bytes)
  records_loop.write_bytes(empty_bytes)
  cfg_cli = _cfg(dimensions=["test-reviewer"], recordsPath=str(records_cli))
  cfg_loop = _cfg(dimensions=["test-reviewer"], recordsPath=str(records_loop))
  respond = _responder(round1_findings=[finding])
  session_dir = str(tmp_path / "cli-session")
  os.makedirs(session_dir, exist_ok=True)
  n = RD.cmd_next(session_dir, cfg_cli)
  assert n["ok"], n
  RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"],
                respond(n["phase"], n["payload"], n["round"]))
  ok, state_cli = RD.load_state(session_dir)
  assert ok and state_cli is not None
  state_loop = RD.new_state(dict(cfg_loop))
  state_loop["_records"] = json.loads(json.dumps(state_cli["_records"]))
  state_loop["rounds"] = json.loads(json.dumps(state_cli["rounds"]))
  RD._persist_round_records(state_loop, state_loop["config"])
  assert records_cli.read_bytes() == records_loop.read_bytes()


def _run_next_records_cli(capsys, session_dir, records_path, *, fresh=True):
    argv = ["next", "--session-dir", session_dir, "--records-path", records_path]
    argv += _guard_argv(session_dir, fresh=fresh)
    rc = RD.main(argv)
    out = capsys.readouterr().out.strip()
    parsed = json.loads(out.splitlines()[-1]) if out else None
    return rc, parsed


def test_records_path_on_non_fresh_state_refuses(tmp_path, capsys):
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir)
    records = str(tmp_path / "records.json")
    open(records, "wb").write(RM.records_bytes([]))
    rc0, out0 = _run_next_records_cli(capsys, session_dir, records, fresh=True)
    assert rc0 == 0 and out0["ok"]
    rc, out = _run_next_records_cli(capsys, session_dir, records, fresh=False)
    assert rc == 1
    assert out == {"ok": False, "reason": "records-path-not-fresh-state", "value": records}


def test_records_path_on_fresh_state_lands_in_config(tmp_path, capsys):
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir)
    records = str(tmp_path / "records.json")
    open(records, "wb").write(RM.records_bytes([]))
    rc, out = _run_next_records_cli(capsys, session_dir, records, fresh=True)
    assert rc == 0 and out["ok"]
    ok, state = RD.load_state(session_dir)
    assert ok and state["config"]["recordsPath"] == os.path.abspath(records)


@pytest.mark.parametrize("rel_path", [
    RD.STATE_FILE,
    RD.JOURNAL_FILE,
    RD.JOURNAL_FAULT_FILE,
    RD.RECEIPT_FILE,
    RD.RECEIPT_INTERIM_FILE,
    RR.META_FILE,
    RR.LOCK_FILE,
    "prior-comments.json",
])
def test_records_path_reserved_session_files_refuse(tmp_path, capsys, rel_path):
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir)
    target = os.path.join(session_dir, rel_path)
    rc, out = _run_next_records_cli(capsys, session_dir, target, fresh=True)
    assert rc == 1
    assert out == {"ok": False, "reason": "records-path-reserved", "value": target}


def test_records_path_reserved_loop_state_refuses(tmp_path, capsys):
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir)
    target = os.path.join(session_dir, RD.STATE_FILE)
    rc, out = _run_next_records_cli(capsys, session_dir, target, fresh=True)
    assert rc == 1
    assert out == {"ok": False, "reason": "records-path-reserved", "value": target}


def test_records_path_reserved_via_traversal_refuses(tmp_path, capsys):
    session_dir = str(tmp_path / "session")
    inner = os.path.join(session_dir, "inner")
    os.makedirs(inner)
    traversal = os.path.join(inner, "..", RD.STATE_FILE)
    rc, out = _run_next_records_cli(capsys, session_dir, traversal, fresh=True)
    assert rc == 1
    assert out == {"ok": False, "reason": "records-path-reserved", "value": traversal}


def test_records_path_reserved_at_commits_root_refuses(tmp_path, capsys):
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir)
    commits = RC.commits_root(session_dir)
    os.makedirs(commits)
    rc, out = _run_next_records_cli(capsys, session_dir, commits, fresh=True)
    assert rc == 1
    assert out == {"ok": False, "reason": "records-path-reserved", "value": commits}


def test_records_path_reserved_under_commits_refuses(tmp_path, capsys):
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir)
    under = os.path.join(RC.commits_root(session_dir), "abc", "intent.json")
    os.makedirs(os.path.dirname(under))
    rc, out = _run_next_records_cli(capsys, session_dir, under, fresh=True)
    assert rc == 1
    assert out == {"ok": False, "reason": "records-path-reserved", "value": under}


def test_records_path_inside_session_refuses(tmp_path, capsys):
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir)
    target = os.path.join(session_dir, "commits-backup", "x.json")
    os.makedirs(os.path.dirname(target))
    rc, out = _run_next_records_cli(capsys, session_dir, target, fresh=True)
    assert rc == 1
    assert out == {"ok": False, "reason": "records-path-reserved", "value": target}


def test_records_path_outside_session_accepted(tmp_path, capsys):
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir)
    records = str(tmp_path / "outside-records.json")
    open(records, "wb").write(RM.records_bytes([]))
    rc, out = _run_next_records_cli(capsys, session_dir, records, fresh=True)
    assert rc == 0 and out["ok"]
    ok, state = RD.load_state(session_dir)
    assert ok and state["config"]["recordsPath"] == os.path.abspath(records)


def test_records_path_relative_persisted_absolute_and_submit_from_other_cwd(tmp_path, capsys):
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir)
    records_rel = "outside-records.json"
    records_abs = os.path.abspath(os.path.join(tmp_path, records_rel))
    open(records_abs, "wb").write(RM.records_bytes([]))
    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        argv = ["next", "--session-dir", session_dir, "--records-path", records_rel]
        argv += _guard_argv(session_dir, fresh=True)
        rc = RD.main(argv)
        assert rc == 0
        ok, state = RD.load_state(session_dir)
        assert ok and state["config"]["recordsPath"] == records_abs
        n = state.get("pending") or {}
        assert n.get("phase") == RD.P_PANEL
        respond = _responder(round1_findings=[_A_FINDING])
        art = respond(n["phase"], n.get("payload"), n.get("round"))
        os.chdir(session_dir)
        out = RD.cmd_submit(session_dir, n["phase"], n["attempt"],
                            RD.state_hash(state), art)
        assert out["ok"], out
        expected = _expected_panel_records_bytes(session_dir, respond, {
            "phase": n["phase"], "payload": n.get("payload"), "round": n.get("round")})
        assert open(records_abs, "rb").read() == expected
    finally:
        os.chdir(cwd)
