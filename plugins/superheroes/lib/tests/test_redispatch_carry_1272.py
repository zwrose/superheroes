"""Re-dispatched fixer orders carry prior audit and gate rulings (#1272 WO-4)."""
import ast
import json
import os

import pytest

import audits
import round_phases as RP
import round_records as RR
import session_contract as SC

import round_driver as RD


def _minimal_paths(session_dir):
    return {
        "storage_key": "fixer.a0",
        "landing_path": os.path.join(session_dir, "landing.json"),
        "envelope_landing_path": os.path.join(session_dir, "env.json"),
        "bare_payload_path": os.path.join(session_dir, "bare.json"),
        "envelope_stub_path": os.path.join(session_dir, "stub.json"),
        "order_path": os.path.join(session_dir, "order.md"),
    }


def _guidance_disposition(fid, title, guidance, *, file="g.py", line=5):
    return {
        "id": fid,
        SC.FINDING_KEY_FIELD: fid,
        "title": title,
        "file": file,
        "line": line,
        "disposition": "fix-with-guidance",
        RD.GATE_GUIDANCE_RECORD_KEY: guidance,
    }


_K = "g.py::guard missing@L5"
_K2 = "h.py::other issue@L2"
_GUIDANCE = "add the guard on every branch before shipping"
_ROW_K = {"findingKey": _K, "title": "guard missing", "file": "g.py", "line": 5,
          "severity": "Important"}
_ROW_K2 = {"findingKey": _K2, "title": "other issue", "file": "h.py", "line": 2,
           "severity": "Minor"}
_AUDIT_REASON = "guard still missing on the else branch"


def _write_session_meta(session_dir, repo_root):
    meta_path = os.path.join(session_dir, RR.META_FILE)
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump({"repoRoot": repo_root}, fh)


def _specimen_state(tmp_path, rnd=3):
    return {
        "config": {"repoRoot": str(tmp_path), "verifyCommand": "none"},
        "reviewedDiff": "diff --git a/g b/g\n",
        "round": rnd,
        "decisions": [],
        "rounds": {
            "1": {"judgmentDispositions": [
                _guidance_disposition(_K, "guard missing", _GUIDANCE),
                {"id": _K2, SC.FINDING_KEY_FIELD: _K2, "title": "other issue", "file": "h.py",
                 "line": 2, "disposition": "fix-as-suggested"},
            ]},
            "2": {"audits": [
                {"id": _K, SC.FINDING_KEY_FIELD: _K, "ruling": "not-discharged",
                 "reason": _AUDIT_REASON},
            ]},
        },
        "_fixBatch": [_ROW_K, _ROW_K2],
    }


def _fixer_render(tmp_path, state, rnd=None):
    rnd = rnd if rnd is not None else state["round"]
    session_dir = str(tmp_path / "redispatch-session")
    os.makedirs(session_dir, exist_ok=True)
    _write_session_meta(session_dir, str(tmp_path))
    paths = _minimal_paths(session_dir)
    ph = RD._order_placeholders(
        RP.P_FIXER, "fixer", 0, state, state["config"], {},
        session_dir, rnd, paths, RD.CHANNEL_FILE,
    )
    fix_batch_path = RD._ensure_fix_batch_file(session_dir, rnd, state)
    with open(fix_batch_path, encoding="utf-8") as fh:
        fix_batch = json.loads(fh.read())
    return ph, fix_batch, session_dir


def test_redispatch_carries_prior_audit_and_gate_guidance_from_earlier_rounds(tmp_path):
    """T1: round-3 fixer carries round-1 guidance and round-2 audit on the batch row."""
    state = _specimen_state(tmp_path)
    ph, fix_batch, _session_dir = _fixer_render(tmp_path, state)
    guidance = ph["GATE_GUIDANCE"]
    assert _GUIDANCE in guidance
    assert "Ruled in round 1" in guidance
    assert guidance != RD._GATE_GUIDANCE_NO_GUIDANCE
    assert "No owner-gate guidance is attached" not in guidance
    row_k = next(r for r in fix_batch if r.get("findingKey") == _K)
    assert row_k["priorAudit"]["ruling"] == "not-discharged"
    assert row_k["priorAudit"]["round"] == 2
    assert row_k["priorAudit"]["reason"] == _AUDIT_REASON
    assert row_k["gateRuling"]["disposition"] == "fix-with-guidance"
    assert row_k["gateRuling"]["round"] == 1
    assert RD.GATE_GUIDANCE_RECORD_KEY not in row_k
    assert "guidance" not in row_k.get("gateRuling", {})


def test_one_more_round_stall_path_carries_history_at_materializer(tmp_path):
    """T2: _fold_stall one-more-round copies targets; materializer still decorates."""
    state = _specimen_state(tmp_path)
    state["_stallTargets"] = [dict(_ROW_K)]
    RD._fold_stall(state, state["config"], {"choice": RD.ONE_MORE_ROUND_CHOICE})
    assert state["step"] == RD.P_FIXER
    session_dir = str(tmp_path / "stall-session")
    os.makedirs(session_dir, exist_ok=True)
    fix_batch_path = RD._ensure_fix_batch_file(session_dir, state["round"], state)
    with open(fix_batch_path, encoding="utf-8") as fh:
        fix_batch = json.loads(fh.read())
    assert len(fix_batch) == 1
    row = fix_batch[0]
    assert row["priorAudit"]["ruling"] == "not-discharged"
    assert row["priorAudit"]["round"] == 2
    assert row["gateRuling"]["disposition"] == "fix-with-guidance"
    assert row["gateRuling"]["round"] == 1
    assert RD.GATE_GUIDANCE_RECORD_KEY not in row


def test_fix_batch_without_history_unchanged_and_no_guidance_block(tmp_path):
    """T3: no history → undecorated batch bytes and the no-guidance sentinel."""
    batch = [{"title": "plain", "file": "p.py", "line": 1, "severity": "Minor"}]
    state = {
        "config": {"repoRoot": str(tmp_path), "verifyCommand": "none"},
        "reviewedDiff": "diff --git a/p b/p\n",
        "round": 2,
        "decisions": [],
        "rounds": {},
        "_fixBatch": batch,
    }
    session_dir = str(tmp_path / "plain-session")
    os.makedirs(session_dir, exist_ok=True)
    path = RD._ensure_fix_batch_file(session_dir, 2, state)
    with open(path, encoding="utf-8") as fh:
        on_disk = fh.read()
    assert on_disk == RR.canonical(batch)
    ph, _, _ = _fixer_render(tmp_path, state, rnd=2)
    assert ph["GATE_GUIDANCE"] == RD._GATE_GUIDANCE_NO_GUIDANCE


def test_keyless_fix_batch_row_matches_content_key_guidance(tmp_path):
    """T5: title/file/line only — content key matches round-1 id → guidance renders."""
    tradeoff_id = "f.py::widen the api@L1"
    guidance = "narrow only"
    state = {
        "config": {"repoRoot": str(tmp_path), "verifyCommand": "none"},
        "reviewedDiff": "diff --git a/f b/f\n",
        "round": 2,
        "decisions": [],
        "rounds": {
            "1": {"judgmentDispositions": [
                {"id": tradeoff_id, "title": "widen the API", "file": "f.py", "line": 1,
                 "disposition": "fix-with-guidance",
                 RD.GATE_GUIDANCE_RECORD_KEY: guidance},
            ]},
        },
        "_fixBatch": [{"title": "widen the API", "file": "f.py", "line": 1}],
    }
    ph, _, _ = _fixer_render(tmp_path, state, rnd=2)
    assert guidance in ph["GATE_GUIDANCE"]
    assert ph["GATE_GUIDANCE"] != RD._GATE_GUIDANCE_NO_GUIDANCE


def test_duplicate_gate_id_in_any_round_refuses_guidance_unusable(tmp_path):
    """T4: duplicate id in an earlier round's log refuses at render."""
    state = _specimen_state(tmp_path)
    state["rounds"]["1"]["judgmentDispositions"].append(
        _guidance_disposition(_K, "duplicate", "other guidance"),
    )
    with pytest.raises(ValueError, match="order-render-refused:gate-guidance-unusable"):
        _fixer_render(tmp_path, state)


def test_row_without_key_serializes_undecorated(tmp_path):
    """E1: neither findingKey nor id → row kept, no priorAudit/gateRuling keys."""
    row = {"title": "anonymous", "file": "x.py", "line": 1}
    state = {
        "_fixBatch": [row],
        "rounds": {"1": {"judgmentDispositions": [
            _guidance_disposition(_K, "guard missing", _GUIDANCE),
        ]}},
    }
    session_dir = str(tmp_path / "keyless-session")
    os.makedirs(session_dir, exist_ok=True)
    path = RD._ensure_fix_batch_file(session_dir, 1, state)
    with open(path, encoding="utf-8") as fh:
        materialized = json.loads(fh.read())
    assert materialized == [row]
    assert "priorAudit" not in materialized[0]
    assert "gateRuling" not in materialized[0]


def test_history_row_key_follows_marker_not_row_id(tmp_path):
    """T6: audit history keys by findingKey even when id disagrees."""
    marker_other = "h.py::other issue@L2"
    state = {
        "_fixBatch": [_ROW_K, _ROW_K2],
        "rounds": {
            "2": {"audits": [
                {"id": "v0", SC.FINDING_KEY_FIELD: _K, "ruling": "not-discharged",
                 "reason": _AUDIT_REASON},
                {"id": _K, SC.FINDING_KEY_FIELD: marker_other, "ruling": "discharged",
                 "reason": "fixed"},
            ]},
        },
    }
    session_dir = str(tmp_path / "marker-session")
    os.makedirs(session_dir, exist_ok=True)
    path = RD._ensure_fix_batch_file(session_dir, 3, state)
    with open(path, encoding="utf-8") as fh:
        materialized = json.loads(fh.read())
    row_k = next(r for r in materialized if r.get("findingKey") == _K)
    row_k2 = next(r for r in materialized if r.get("findingKey") == _K2)
    assert row_k["priorAudit"]["reason"] == _AUDIT_REASON
    assert row_k2["priorAudit"]["ruling"] == "discharged"


def test_fold_judgment_stamps_finding_key_on_all_disposition_shapes():
    """T7: _fold_judgment stamps findingKey on skip, fix-with-guidance, and fail-closed logs."""
    skip_f = {"title": "defer this", "severity": "Important", "file": "s.py", "line": 1,
              "tradeoff": True}
    guidance_f = {"title": "narrow the API", "severity": "Minor", "file": "g.py", "line": 3,
                  "tradeoff": True}
    fail_closed_f = {"title": "missing disposition", "severity": "Critical", "file": "f.py",
                     "line": 5, "tradeoff": True}
    state = RD.new_state({"leg": "code", "vendors": ["claude", "codex"], "diff": "d",
                          "fixerVendor": "claude"})
    RD._route_judgment_blockers(state, [dict(skip_f), dict(guidance_f), dict(fail_closed_f)])
    ids = RD._judgment_row_ids(state["_judgmentFindings"])
    assert len(ids) == 3
    RD._fold_judgment(state, state["config"], {"dispositions": [
        {"id": ids[0], "disposition": "skip", "reason": "defer the important one"},
        {"id": ids[1], "disposition": "fix-with-guidance", "guidance": "narrow only"},
    ]})
    log = state["rounds"][str(state["round"])]["judgmentDispositions"]
    by_disp = {e["disposition"]: e for e in log}
    for entry in log:
        assert entry[SC.FINDING_KEY_FIELD] == entry["id"]
    assert by_disp["skip"][SC.FINDING_KEY_FIELD] == ids[0]
    assert by_disp["fix-with-guidance"][SC.FINDING_KEY_FIELD] == ids[1]
    fail_closed = next(e for e in log if e.get("failClosed"))
    assert fail_closed[SC.FINDING_KEY_FIELD] == ids[2]


def test_apply_audit_results_copies_target_finding_key_marker():
    """T8: apply_audit_results copies findingKey from targets; absent marker → no key on row."""
    marked = {"id": "v0", SC.FINDING_KEY_FIELD: "f.py::bug@L1", "file": "f.py", "line": 1,
              "title": "bug", "severity": "Important"}
    silent = {"id": "v1", SC.FINDING_KEY_FIELD: "g.py::gap@L2", "file": "g.py", "line": 2,
              "title": "gap", "severity": "Minor"}
    unmarked = {"id": "v2", "file": "h.py", "line": 3, "title": "plain", "severity": "Minor"}
    out = audits.apply_audit_results(
        [marked, silent, unmarked],
        [{"id": "v0", "ruling": "discharged", "reason": "verified", "auditorVendor": "codex"}],
        expected_auditors={"v0": "codex"},
        collection_manifest={"v0": "codex"},
    )
    discharged = next(a for a in out["audits"] if a["id"] == "v0")
    silent_row = next(a for a in out["audits"] if a["id"] == "v1")
    unmarked_row = next(a for a in out["audits"] if a["id"] == "v2")
    assert discharged[SC.FINDING_KEY_FIELD] == marked[SC.FINDING_KEY_FIELD]
    assert silent_row[SC.FINDING_KEY_FIELD] == silent[SC.FINDING_KEY_FIELD]
    assert SC.FINDING_KEY_FIELD not in unmarked_row


def test_history_row_key_refuses_unkeyable_guidance_and_content_keys_legacy_audit(tmp_path):
    """T9: guided row without marker/location refuses; marker-less audit keys by content."""
    state = _specimen_state(tmp_path)
    state["rounds"]["1"]["judgmentDispositions"] = [
        {"id": "x", "title": "t", "disposition": "fix-with-guidance",
         RD.GATE_GUIDANCE_RECORD_KEY: "g"},
    ]
    with pytest.raises(ValueError, match="order-render-refused:gate-guidance-unusable"):
        _fixer_render(tmp_path, state)

    legacy_audit = {"id": "v0", "ruling": "not-discharged", "reason": "legacy reason",
                    "file": "g.py", "line": 5, "title": "guard missing"}
    state2 = {
        "_fixBatch": [{"title": "guard missing", "file": "g.py", "line": 5}],
        "rounds": {"2": {"audits": [legacy_audit]}},
    }
    session_dir = str(tmp_path / "legacy-audit-session")
    os.makedirs(session_dir, exist_ok=True)
    path = RD._ensure_fix_batch_file(session_dir, 3, state2)
    with open(path, encoding="utf-8") as fh:
        materialized = json.loads(fh.read())
    assert materialized[0]["priorAudit"]["ruling"] == "not-discharged"
    assert materialized[0]["priorAudit"]["reason"] == "legacy reason"


def test_history_readers_never_key_by_row_id_census():
    """CENSUS: history readers derive keys via the leaf, never row id."""
    func_names = ("_finding_history", "_validate_gate_guidance_logs", "_gate_guidance_entries")
    lib_dir = os.path.join(os.path.dirname(__file__), "..")
    path = os.path.join(lib_dir, "round_driver.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    func_nodes = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in func_names:
            func_nodes[node.name] = node
    assert set(func_nodes) == set(func_names)
    for name, fn in func_nodes.items():
        for node in ast.walk(fn):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "get":
                    if node.args and isinstance(node.args[0], ast.Constant):
                        if node.args[0].value == "id":
                            raise AssertionError("%s uses .get('id') at line %s" % (name, node.lineno))
            if isinstance(node, ast.Subscript):
                sl = node.slice
                if isinstance(sl, ast.Constant) and sl.value == "id":
                    raise AssertionError("%s uses ['id'] at line %s" % (name, node.lineno))
