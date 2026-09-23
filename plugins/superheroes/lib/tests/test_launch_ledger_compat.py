import importlib.util
import os
import subprocess
import sys
import time

import pytest

import launch_ledger as ll

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
_LEDGER_PATH = "plugins/superheroes/lib/launch_ledger.py"

_BASE_SHA = "5817cc77"
_MAIN_SHA = "8e9a12a0"
_LAUNCH_ID = "bg-compat-l1"
_BACKGROUND_ID = "feac172f"
_SESSION_ID = "feac172f-474c-424d-86e7-0e50688972c9"
_STARTED_PID = 424242


class _GitShowLoader:
    def __init__(self, source):
        self._source = source

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        exec(compile(self._source, "<git-show>", "exec"), module.__dict__)


def _load_launch_ledger_at_sha(sha):
    toplevel = subprocess.run(
        ["git", "-C", _HERE, "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    try:
        proc = subprocess.run(
            ["git", "-C", toplevel, "show", f"{sha}:{_LEDGER_PATH}"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise AssertionError(
            "commit %s is not available in this checkout — "
            "fetch full history (fetch-depth: 0) to run the git-baseline test"
            % sha
        ) from exc
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    name = f"_launch_ledger_snapshot_{sha[:12]}"
    spec = importlib.util.spec_from_loader(name, _GitShowLoader(proc.stdout))
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = os.path.join(_LIB, "launch_ledger.py")
    spec.loader.exec_module(mod)
    return mod


def _new_shape_records():
    """Background-shaped record set as WO-B's launcher will write it."""
    worktree = os.path.abspath("/tmp/superheroes-bg-worktree")
    config_dir = os.path.abspath("/tmp/superheroes-bg-config")
    reserved = {
        "event": "reserved",
        "launchId": _LAUNCH_ID,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "batchId": "bg-batch",
        "repoId": "test-repo",
        "issue": 1273,
        "surfaces": ["plugins/superheroes/lib/launch_ledger.py"],
        "premise": {},
        "preflight": {},
        "argv": [],
        "doctrineDigest": "abc123",
        "model": "test-model",
        "worktree": worktree,
        "configDir": config_dir,
    }
    started = {
        "event": "started",
        "launchId": _LAUNCH_ID,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "attempt": 1,
        "pid": _STARTED_PID,
        "logPath": "/tmp/bg-log",
        "errPath": "/tmp/bg-err",
        "launchMode": ll.LAUNCH_MODE_BACKGROUND,
        "backgroundId": _BACKGROUND_ID,
        "sessionId": _SESSION_ID,
    }
    return [reserved, started]


@pytest.mark.parametrize("sha", [_BASE_SHA, _MAIN_SHA])
def test_old_reader_folds_background_lane_live(sha):
    # axis: pinned readers treat a background-shaped lane as live, not dead (c14-l4a-D5)
    snapshot = _load_launch_ledger_at_sha(sha)
    records = _new_shape_records()
    folded = snapshot.fold(records)
    assert folded["ok"] is True
    lane = folded["launches"][_LAUNCH_ID]
    assert lane["started"] is True
    assert lane["pid"] == _STARTED_PID
    assert lane["terminal"] is False
    assert lane["sessionId"] is None
    live = snapshot.live_launches(records)
    assert _LAUNCH_ID in live


@pytest.mark.parametrize("sha", [_BASE_SHA, _MAIN_SHA])
def test_old_reader_folds_background_lane_terminal_after_outcome(sha):
    snapshot = _load_launch_ledger_at_sha(sha)
    records = _new_shape_records()
    records.append({
        "event": "outcome",
        "launchId": _LAUNCH_ID,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "outcome": "handback",
        "evidence": "done",
    })
    folded = snapshot.fold(records)
    assert folded["ok"] is True
    assert folded["launches"][_LAUNCH_ID]["terminal"] is True


def test_current_reader_folds_background_session_id():
    # axis: the current reader exposes started.sessionId on the folded lane
    records = _new_shape_records()
    folded = ll.fold(records)
    assert folded["ok"] is True
    lane = folded["launches"][_LAUNCH_ID]
    assert lane["sessionId"] == _SESSION_ID
    assert lane["backgroundId"] == _BACKGROUND_ID
    assert lane["launchMode"] == ll.LAUNCH_MODE_BACKGROUND
