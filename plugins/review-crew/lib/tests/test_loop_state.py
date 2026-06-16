"""Tests for the deterministic loop-continuation gate (`loop_state`).

The whole point is that the *continue* decision is no longer prose the model can rationalize
past: a blocking fix this round → `review` is mandatory; the only exits are when no blocking
fix was applied. These tests pin that matrix, the artifact derivation (so the counts aren't
self-reported), and the fail-safe (a bad artifact defaults to *more* review, never a silent
exit).
"""
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LS = _load(os.path.join(_HERE, "..", "loop_state.py"), "loop_state")


def _run(capsys, *args):
    rc = LS.main(["loop_state.py", *args])
    return rc, json.loads(capsys.readouterr().out)


# --- the pure decision matrix --------------------------------------------

def test_breaker_halt_wins():
    assert LS.decide(2, 0, 1, 7, breaker_halt=True)[0] == "halt"


def test_blocking_fix_mandates_review():
    action, mandatory, reason = LS.decide(2, 0, 1, 7, breaker_halt=False)
    assert action == "review" and mandatory is True
    assert "MANDATORY" in reason  # the anti-rationalization message travels with the directive


def test_blocking_fix_at_cap_halts_not_review():
    assert LS.decide(1, 0, 7, 7, breaker_halt=False)[0] == "halt"


def test_no_fix_no_skip_exits_clean():
    assert LS.decide(0, 0, 3, 7, breaker_halt=False)[0] == "exit_clean"


def test_no_fix_with_skipped_blocker_exits_skipped():
    assert LS.decide(0, 2, 3, 7, breaker_halt=False)[0] == "exit_skipped"


def test_there_is_no_clean_exit_when_a_blocking_fix_landed():
    # The crux: no combination of round/cap lets a just-addressed blocker exit without re-review.
    for rnd in range(1, 7):
        assert LS.decide(1, 0, rnd, 7, breaker_halt=False)[0] == "review"


# --- CLI + artifact derivation -------------------------------------------

def test_cli_review_derived_from_fix_batch(tmp_path, capsys):
    fb = tmp_path / "fix-batch.json"
    fb.write_text(json.dumps([{"severity": "Important"}, {"severity": "Minor"}]), encoding="utf-8")
    rc, out = _run(capsys, "--round", "1", "--fix-batch", str(fb))
    assert rc == 0 and out["action"] == "review" and out["mandatory"] is True


def test_cli_fix_batch_with_only_minors_does_not_mandate_review(tmp_path, capsys):
    fb = tmp_path / "fix-batch.json"
    fb.write_text(json.dumps([{"severity": "Minor"}, {"severity": "Nit"}]), encoding="utf-8")
    rc, out = _run(capsys, "--round", "1", "--fix-batch", str(fb))
    assert out["action"] == "exit_clean"  # no blocking fix → done


def test_cli_skipped_derived_from_resolutions(tmp_path, capsys):
    res = tmp_path / "res.json"
    res.write_text(json.dumps({"resolutions": [
        {"action": "skip", "severity": "Critical"},
        {"action": "fix", "severity": "Important"},
        {"action": "skip", "severity": "Minor"},  # not blocking — not counted
    ]}), encoding="utf-8")
    rc, out = _run(capsys, "--round", "2", "--resolutions", str(res))
    assert out["action"] == "exit_skipped"  # 1 skipped blocker, no fix applied


def test_cli_breaker_halt(capsys):
    rc, out = _run(capsys, "--round", "3", "--blocking-fixed", "1", "--breaker-halt", "yes")
    assert out["action"] == "halt"


def test_cli_bad_artifact_fails_safe_to_review(tmp_path, capsys):
    rc, out = _run(capsys, "--round", "1", "--fix-batch", str(tmp_path / "does-not-exist.json"))
    assert rc == 0 and out["action"] == "review"  # fail SAFE toward review, never a silent exit


# --- the revise-loop wiring: derive the count from compiled.json, not self-report ---------

def test_cli_review_derived_from_compiled_minus_skipped(tmp_path, capsys):
    # revise-loop wiring: blockers present (from compiled) minus skipped → addressed > 0 → review.
    comp = tmp_path / "compiled.json"
    comp.write_text(json.dumps({"findings": [
        {"severity": "Important"}, {"severity": "Critical"}, {"severity": "Minor"}]}), encoding="utf-8")
    rc, out = _run(capsys, "--round", "1", "--compiled", str(comp), "--skipped-blocking", "1")
    assert out["action"] == "review"  # 2 blockers present, 1 skipped → 1 addressed → re-review


def test_cli_compiled_all_blockers_skipped_exits_skipped(tmp_path, capsys):
    comp = tmp_path / "compiled.json"
    comp.write_text(json.dumps({"findings": [{"severity": "Important"}]}), encoding="utf-8")
    rc, out = _run(capsys, "--round", "2", "--compiled", str(comp), "--skipped-blocking", "1")
    assert out["action"] == "exit_skipped"  # the only blocker was skipped → nothing addressed


def test_cli_compiled_skip_count_must_be_cumulative_present(tmp_path, capsys):
    # arch-r2-001 regression: a blocker skipped in an earlier round is RE-FLAGGED in compiled.json
    # every subsequent round (the specialists don't know it was skipped). The revise loops must
    # pass SKIPPED_BLOCKING as the CUMULATIVE count of present-and-skipped blockers, not just those
    # newly skipped this round. With the cumulative count, the lone re-flagged skipped blocker
    # yields exit_skipped...
    comp = tmp_path / "compiled.json"
    comp.write_text(json.dumps({"findings": [{"severity": "Critical"}]}), encoding="utf-8")
    rc, out = _run(capsys, "--round", "4", "--compiled", str(comp), "--skipped-blocking", "1")
    assert out["action"] == "exit_skipped"  # cumulative skip count → loop converges
    # ...whereas a delta count of 0 (the old bug: "nothing NEW was skipped this round") would have
    # mis-read the same re-flagged blocker as addressed, forcing review to the round cap forever.
    rc, out = _run(capsys, "--round", "4", "--compiled", str(comp), "--skipped-blocking", "0")
    assert out["action"] == "review"  # demonstrates why the count must be cumulative, not a delta


def test_cli_compiled_no_blockers_exits_clean(tmp_path, capsys):
    comp = tmp_path / "compiled.json"
    comp.write_text(json.dumps({"findings": [{"severity": "Minor"}, {"severity": "Nit"}]}), encoding="utf-8")
    rc, out = _run(capsys, "--round", "1", "--compiled", str(comp))
    assert out["action"] == "exit_clean"


def test_cli_wrong_shape_artifact_fails_safe_to_review(tmp_path, capsys):
    # A valid-JSON-but-wrong-shape resolutions (a bare list, not {resolutions:[...]}) makes
    # data.get(...) raise AttributeError — the broadened except must fail SAFE to review (code-001),
    # not crash with empty stdout.
    res = tmp_path / "res.json"
    res.write_text(json.dumps([{"action": "skip", "severity": "Critical"}]), encoding="utf-8")
    rc, out = _run(capsys, "--round", "1", "--resolutions", str(res), "--blocking-fixed", "0")
    assert rc == 0 and out["action"] == "review"
