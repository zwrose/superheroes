import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LS = _load(os.path.join(_HERE, "..", "loop_synthesis.py"), "loop_synthesis")
CB = _load(os.path.join(_HERE, "..", "circuit_breaker.py"), "circuit_breaker")


def _f(file, title, severity):
    return {"file": file, "line": 1, "title": title, "severity": severity}


def test_missing_verdict_keeps_finding_at_original_severity():
    merged = [_f("a.py", "bug", "Important")]
    out = LS.consume(merged, [])  # no leaf verdicts at all
    assert len(out["findings"]) == 1 and out["findings"][0]["severity"] == "Important"
    assert out["drops"] == []


def test_malformed_leaf_output_keeps_everything():
    merged = [_f("a.py", "bug", "Important")]
    out = LS.consume(merged, "not-a-list")
    assert len(out["findings"]) == 1 and out["drops"] == []


def test_clear_drop_with_reason_is_dropped():
    f = _f("a.py", "weak", "Minor")
    v = {"id": CB.finding_identity(f), "action": "drop", "reason": "does not hold against the code"}
    out = LS.consume([f], [v])
    assert out["findings"] == []
    assert out["drops"][0]["reason"] == "does not hold against the code"
    assert out["drops"][0]["was_blocking_tagged"] is False


def test_clear_drop_can_match_reviewer_short_id():
    f = {"id": "premortem-001", "file": "plugins/superheroes/lib/acceptance_deps.py",
         "line": 12, "title": "Accepts stale dependency state", "severity": "Important"}
    v = {"id": "premortem-001", "action": "drop", "reason": "does not hold in the build worktree"}
    out = LS.consume([f], [v])
    assert out["findings"] == []
    assert out["drops"][0]["id"] == CB.finding_identity(f)
    assert out["drops"][0]["was_blocking_tagged"] is True


def test_unmatched_verdict_short_id_keeps_finding_fail_closed():
    f = {"id": "premortem-001", "file": "plugins/superheroes/lib/acceptance_deps.py",
         "line": 12, "title": "Accepts stale dependency state", "severity": "Important"}
    v = {"id": "premortem-999", "action": "drop", "reason": "wrong finding"}
    out = LS.consume([f], [v])
    assert out["findings"] == [f]
    assert out["drops"] == []


def test_drop_without_reason_is_kept_uncertain():
    f = _f("a.py", "weak", "Minor")
    v = {"id": CB.finding_identity(f), "action": "drop", "reason": ""}  # no reason -> keep
    out = LS.consume([f], [v])
    assert len(out["findings"]) == 1 and out["drops"] == []


def test_dropped_blocker_is_flagged_distinctly_ufr10():
    f = _f("a.py", "real bug", "Critical")
    v = {"id": CB.finding_identity(f), "action": "drop", "reason": "stale"}
    out = LS.consume([f], [v])
    assert out["drops"][0]["was_blocking_tagged"] is True


def test_severity_normalized_up_and_down():
    f1 = _f("a.py", "overstated", "Critical")
    f2 = _f("b.py", "understated", "Minor")
    v1 = {"id": CB.finding_identity(f1), "action": "keep", "severity": "Minor"}
    v2 = {"id": CB.finding_identity(f2), "action": "keep", "severity": "Important"}
    res = LS.consume([f1, f2], [v1, v2])
    out = {x["file"]: x for x in res["findings"]}
    assert out["a.py"]["severity"] == "Minor"      # lowered
    assert out["b.py"]["severity"] == "Important"  # raised
    # #186: only the blocking→non-blocking lowering (a.py) is flagged; the Minor→Important raise
    # (b.py, an upgrade) is not — the severity outcomes above are unchanged either way.
    assert [d["id"] for d in res["downgrades"]] == [CB.finding_identity(f1)]
    assert res["downgrades"][0]["from"] == "Critical" and res["downgrades"][0]["to"] == "Minor"


# --- #186: blocking→non-blocking downgrades flagged like drops (visibility only) --------------
def test_blocking_downgrade_recorded_with_reason():
    f = _f("a.py", "overstated race", "Critical")
    v = {"id": CB.finding_identity(f), "action": "keep", "severity": "Nit",
         "reason": "single-threaded path; not actually a race"}
    out = LS.consume([f], [v])
    # severity outcome is unchanged behavior — the survivor still lands at Nit ...
    assert out["findings"][0]["severity"] == "Nit"
    # ... and the demotion is recorded for owner scrutiny, with from/to and the judge's reason.
    assert len(out["downgrades"]) == 1
    d = out["downgrades"][0]
    assert d["id"] == CB.finding_identity(f) and d["file"] == "a.py" and d["title"] == "overstated race"
    assert d["from"] == "Critical" and d["to"] == "Nit"
    assert d["reason"] == "single-threaded path; not actually a race"


def test_blocking_downgrade_without_reason_still_flagged_no_reason_key():
    f = _f("a.py", "missing guard", "Important")
    v = {"id": CB.finding_identity(f), "action": "keep", "severity": "Minor"}  # no reason
    out = LS.consume([f], [v])
    assert out["findings"][0]["severity"] == "Minor"   # the reasonless downgrade still applies
    assert len(out["downgrades"]) == 1 and "reason" not in out["downgrades"][0]
    assert out["downgrades"][0]["from"] == "Important" and out["downgrades"][0]["to"] == "Minor"


def test_blocking_to_blocking_retier_is_not_flagged():
    f = _f("a.py", "broad scope", "Critical")
    v = {"id": CB.finding_identity(f), "action": "keep", "severity": "Important"}
    out = LS.consume([f], [v])
    assert out["findings"][0]["severity"] == "Important"
    assert out["downgrades"] == []


def test_nonblocking_retier_is_not_flagged():
    f = _f("a.py", "cosmetic", "Minor")
    v = {"id": CB.finding_identity(f), "action": "keep", "severity": "Nit"}
    out = LS.consume([f], [v])
    assert out["findings"][0]["severity"] == "Nit"
    assert out["downgrades"] == []


def test_dropped_blocker_is_not_double_counted_as_a_downgrade():
    # A dropped blocker rides in `drops` (was_blocking_tagged), never in `downgrades`.
    f = _f("a.py", "real bug", "Critical")
    v = {"id": CB.finding_identity(f), "action": "drop", "reason": "stale"}
    out = LS.consume([f], [v])
    assert out["drops"][0]["was_blocking_tagged"] is True
    assert out["findings"] == [] and out["downgrades"] == []


def test_keep_on_uncertain_downgrade_is_unchanged_and_flagged():
    # A drop with no reason is kept (keep-on-uncertain). If that same verdict also carries a
    # non-blocking severity, the survivor takes it (NORMALIZE) and the demotion is flagged.
    f = _f("a.py", "weak", "Critical")
    v = {"id": CB.finding_identity(f), "action": "drop", "reason": "", "severity": "Minor"}
    out = LS.consume([f], [v])
    assert out["drops"] == [] and out["findings"][0]["severity"] == "Minor"
    assert len(out["downgrades"]) == 1 and out["downgrades"][0]["to"] == "Minor"


def test_invalid_severity_keeps_original():
    f = _f("a.py", "bug", "Important")
    v = {"id": CB.finding_identity(f), "action": "keep", "severity": "Bogus"}
    out = LS.consume([f], [v])
    assert out["findings"][0]["severity"] == "Important"


def test_missing_title_matches_summary_identity_and_grafts_severity():
    f = {"file": "a.py", "line": 1, "summary": "Nested verify result string"}
    v = {"id": "a.py::nested verify result string", "action": "keep", "severity": "Critical"}
    out = LS.consume([f], [v])
    assert out["findings"][0]["severity"] == "Critical"


def test_kept_finding_without_any_severity_defaults_to_important():
    f = {"file": "a.py", "line": 1, "summary": "Severity missing everywhere"}
    v = {"id": "a.py::severity missing everywhere", "action": "keep", "reason": "still applies"}
    out = LS.consume([f], [v])
    assert out["findings"][0]["severity"] == "Important"


# --- CLI wiring (the exact invocation standalone review-code's compile step runs) -------------
# review-code (#174 PR 3) shells out to `loop_synthesis.py --merged <file> --leaf <file>` and
# reads back `{findings, drops}`. These pin the fail-closed contract AT THE CLI SEAM the
# standalone path depends on — not just the in-process consume().
import json


def _write_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


def _run_cli(tmp_path, merged, leaf, capsys, *, leaf_exists=True):
    mpath = os.path.join(str(tmp_path), "merged.json")
    lpath = os.path.join(str(tmp_path), "synthesis-verdicts.json")
    _write_json(mpath, merged)
    if leaf_exists:
        _write_json(lpath, leaf)
    rc = LS.main(["loop_synthesis.py", "--merged", mpath, "--leaf", lpath])
    return rc, json.loads(capsys.readouterr().out)


def test_cli_missing_leaf_file_is_raw_compile_no_drops(tmp_path, capsys):
    """Synthesis failure (the judge wrote no verdict file) → raw mechanical compile, every
    finding kept, nothing dropped. This is the standalone fallback the SKILL relies on."""
    merged = [_f("a.py", "real bug", "Critical"), _f("b.py", "another", "Important")]
    rc, out = _run_cli(tmp_path, merged, None, capsys, leaf_exists=False)
    assert rc == 0
    assert len(out["findings"]) == 2
    assert out["drops"] == []


def test_cli_empty_leaf_keeps_all_no_drops(tmp_path, capsys):
    merged = [_f("a.py", "real bug", "Critical")]
    rc, out = _run_cli(tmp_path, merged, [], capsys)
    assert rc == 0
    assert len(out["findings"]) == 1 and out["drops"] == []


def test_cli_keep_on_uncertain(tmp_path, capsys):
    """A drop with no reason is ambiguous → the finding is KEPT (never dropped on a hunch)."""
    f = _f("a.py", "weak", "Important")
    v = {"id": CB.finding_identity(f), "action": "drop", "reason": ""}
    rc, out = _run_cli(tmp_path, [f], [v], capsys)
    assert len(out["findings"]) == 1 and out["drops"] == []


def test_cli_drop_with_reason_recorded(tmp_path, capsys):
    f = _f("a.py", "weak", "Minor")
    v = {"id": CB.finding_identity(f), "action": "drop", "reason": "does not hold against the code"}
    rc, out = _run_cli(tmp_path, [f], [v], capsys)
    assert out["findings"] == []
    assert out["drops"][0]["reason"] == "does not hold against the code"
    assert out["drops"][0]["was_blocking_tagged"] is False


def test_cli_dropped_blocker_is_flagged(tmp_path, capsys):
    """A dropped Critical/Important rides out flagged, so an all-drop leaf can never make a
    silent clean in the standalone readout."""
    f = _f("a.py", "real bug", "Critical")
    v = {"id": CB.finding_identity(f), "action": "drop", "reason": "stale — path removed"}
    rc, out = _run_cli(tmp_path, [f], [v], capsys)
    assert out["findings"] == []
    assert out["drops"][0]["was_blocking_tagged"] is True


def test_cli_blocking_downgrade_is_recorded(tmp_path, capsys):
    """#186: a survivor demoted from blocking to non-blocking rides out in `downgrades` at the
    CLI seam the standalone compile step reads back, so compiled.json can surface it."""
    f = _f("a.py", "overstated", "Critical")
    v = {"id": CB.finding_identity(f), "action": "keep", "severity": "Minor", "reason": "not reachable"}
    rc, out = _run_cli(tmp_path, [f], [v], capsys)
    assert out["findings"][0]["severity"] == "Minor"   # severity outcome unchanged
    assert out["drops"] == []
    assert len(out["downgrades"]) == 1
    assert out["downgrades"][0]["from"] == "Critical" and out["downgrades"][0]["to"] == "Minor"
    assert out["downgrades"][0]["reason"] == "not reachable"
