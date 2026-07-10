# plugins/superheroes/lib/tests/test_minor_rollup_corruption.py
"""B4 (#315): a corrupt Minor-findings roll-up must not be handled silently.

Detector this fix ships: a REAL roll-up file that exists but is unparseable (no monkeypatched
reader) must make `minor_rollup.read_status` report corrupt=True and make `minor_rollup_cli.py`
both (a) flag `corrupt: true` in its output and (b) journal a `notify` breadcrumb the owner reads
back — rather than an indistinguishable empty roll-up.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
CLI = str(HERE.parent / "minor_rollup_cli.py")
LIB = str(HERE.parent)
sys.path.insert(0, LIB)
import control_plane  # noqa: E402
import journal  # noqa: E402
import minor_rollup  # noqa: E402


def test_read_status_distinguishes_missing_corrupt_valid(tmp_path):
    missing = str(tmp_path / "nope.json")
    assert minor_rollup.read_status(missing) == ([], False)

    corrupt = tmp_path / "bad.json"
    corrupt.write_text("{ this is not json", encoding="utf-8")
    assert minor_rollup.read_status(str(corrupt)) == ([], True)

    not_a_list = tmp_path / "obj.json"
    not_a_list.write_text('{"a": 1}', encoding="utf-8")
    assert minor_rollup.read_status(str(not_a_list)) == ([], True)

    valid = tmp_path / "ok.json"
    valid.write_text('[{"file": "a.py", "title": "nit", "severity": "Minor"}]', encoding="utf-8")
    findings, corrupt_flag = minor_rollup.read_status(str(valid))
    assert corrupt_flag is False and len(findings) == 1


def _run_cli(repo, work_item):
    env = os.environ.copy()
    env["PYTHONPATH"] = LIB
    proc = subprocess.run([sys.executable, CLI, "--work-item", work_item],
                          cwd=str(repo), env=env, capture_output=True, text=True)
    return json.loads(proc.stdout)


def test_cli_flags_corruption_and_journals_a_breadcrumb(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    wi = "wi-corrupt"
    rollup = os.path.join(control_plane.paths(str(repo), wi)["issue_dir"], "minor-findings.json")
    os.makedirs(os.path.dirname(rollup), exist_ok=True)
    with open(rollup, "w", encoding="utf-8") as fh:
        fh.write("]]not json at all[[")

    out = _run_cli(repo, wi)
    assert out.get("corrupt") is True, "a corrupt roll-up must be flagged, got %r" % out
    assert out.get("minors") == [], "fail-closed read still returns [] on corruption, got %r" % out

    events = journal.read_events(control_plane.paths(str(repo), wi)["events"])
    notes = [e for e in events if isinstance(e, dict) and e.get("type") == "notify"]
    assert any("corrupt" in (e.get("detail") or "").lower() for e in notes), (
        "a notify breadcrumb disclosing the corruption must be journaled, got %r" % events)


def test_cli_clean_rollup_is_not_flagged_corrupt(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    wi = "wi-clean"
    out = _run_cli(repo, wi)   # no roll-up file at all -> legitimately empty, not corrupt
    assert out.get("corrupt") is False
    assert out.get("minors") == []
    events = journal.read_events(control_plane.paths(str(repo), wi)["events"])
    assert not [e for e in events if isinstance(e, dict) and e.get("type") == "notify"], (
        "an absent roll-up is not corruption — no breadcrumb should be journaled")
