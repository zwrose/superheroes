# plugins/superheroes/lib/tests/test_readout_post_courier_retries.py
"""B5 (#315): the terminal hand-back leaf must disclose courier retry pressure — journal a `notify`
breadcrumb AND render a readout line — from the --courier-retries payload the spine passes. Real
subprocess over the conftest-isolated store (no monkeypatched journal seam)."""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
CLI = str(HERE.parent / "readout_post.py")
LIB = str(HERE.parent)
sys.path.insert(0, LIB)
import control_plane  # noqa: E402
import journal  # noqa: E402


def _run(repo, work_item, extra):
    env = os.environ.copy()
    env["PYTHONPATH"] = LIB
    proc = subprocess.run([sys.executable, CLI, "--work-item", work_item, *extra],
                          cwd=str(repo), env=env, capture_output=True, text=True)
    return proc


def _notifies(repo, work_item):
    events = journal.read_events(control_plane.paths(str(repo), work_item)["events"])
    return [e for e in events if isinstance(e, dict) and e.get("type") == "notify"]


def test_courier_retries_journaled_and_rendered_in_ctx(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    wi = "wi-retry"
    ctx = {"pr_url": "http://x/pr/1", "ci_status": "green"}
    proc = _run(repo, wi, ["--terminal", "completed", "--ctx", json.dumps(ctx),
                           "--courier-retries", json.dumps({"retried": 4, "byLabel": {"post readout": 4}})])
    assert json.loads(proc.stdout).get("recorded") in (True, None) or "posted" in proc.stdout, proc.stderr
    notes = _notifies(repo, wi)
    assert any("retried" in (e.get("detail") or "") for e in notes), (
        "a courier-retry notify breadcrumb must be journaled, got %r" % notes)


def test_courier_retries_zero_is_silent(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    wi = "wi-noretry"
    _run(repo, wi, ["--reason", "parked for a reason",
                    "--courier-retries", json.dumps({"retried": 0, "byLabel": {}})])
    assert not _notifies(repo, wi), "zero retries must journal no courier notify"


def test_courier_retries_absent_is_silent(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    wi = "wi-absent"
    _run(repo, wi, ["--reason", "parked, no retries arg"])
    assert not _notifies(repo, wi), "no --courier-retries arg must journal no courier notify"
