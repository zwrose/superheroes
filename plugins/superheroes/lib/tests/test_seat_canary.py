import importlib.util
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load():
    spec = importlib.util.spec_from_file_location(
        "seat_canary", os.path.join(_HERE, "..", "seat_canary.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SC = _load()


def _repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "marker.txt").write_text("keep-me", encoding="utf-8")
    (root / ".git").write_text("gitdir: /fake/worktree\n", encoding="utf-8")
    return str(root)


def _base_dispatch_result(**overrides):
    base = {
        "ok": True,
        "findings": [],
        "attempts": 1,
        "engagement": {
            "tokens": None,
            "toolCalls": None,
            "stdoutBytes": 0,
            "wallSeconds": 0.0,
        },
    }
    base.update(overrides)
    return base


def test_findings_with_plant_engaged_and_detected():
    captured = {}

    def dispatch(engine, **kwargs):
        captured.update(kwargs)
        return _base_dispatch_result(
            findings=[{
                "id": "p1",
                "severity": "Critical",
                "file": "lib/gate.py",
                "title": SC.PLANT_MARKER,
                "body": "fails open",
            }],
            engagement={"tokens": 100, "toolCalls": None, "stdoutBytes": 50, "wallSeconds": 1.0},
        )

    out = SC.run_canary(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        repo_root="/tmp/fake", dispatch=dispatch,
    )
    assert out["engaged"] is True
    assert out["outcome"] == "ok"
    assert out["detectedPlant"] is True
    assert out["evidence"]["findings"] == 1


def test_vacuous_no_telemetry_not_engaged():
    def dispatch(engine, **kwargs):
        return {
            "ok": False,
            "reason": "vacuous",
            "attempts": 2,
            "forfeited": True,
            "engagement": {
                "tokens": None,
                "toolCalls": None,
                "stdoutBytes": 0,
                "wallSeconds": 0.0,
            },
            "disclosure": "vacuous seat",
        }

    out = SC.run_canary(
        "codex", engine_model="m", effort="high", repo_root="/r", dispatch=dispatch,
    )
    assert out["engaged"] is False
    assert out["outcome"] == "vacuous"
    assert out["detail"]


def test_high_token_spend_alone_not_engaged():
    def dispatch(engine, **kwargs):
        return {
            "ok": False,
            "reason": "vacuous",
            "attempts": 2,
            "forfeited": True,
            "engagement": {
                "tokens": 50000,
                "toolCalls": None,
                "stdoutBytes": 999,
                "wallSeconds": 120.0,
            },
        }

    out = SC.run_canary(
        "codex", engine_model="m", effort="high", repo_root="/r", dispatch=dispatch,
    )
    assert out["engaged"] is False


def test_wall_time_alone_not_engaged_but_finding_with_fast_wall_engaged():
    def dispatch_vacuous(engine, **kwargs):
        return {
            "ok": False,
            "reason": "vacuous",
            "attempts": 2,
            "forfeited": True,
            "engagement": {
                "tokens": None,
                "toolCalls": None,
                "stdoutBytes": 0,
                "wallSeconds": 600.0,
            },
        }

    out_slow = SC.run_canary(
        "codex", engine_model="m", effort="high", repo_root="/r", dispatch=dispatch_vacuous,
    )
    assert out_slow["engaged"] is False

    def dispatch_finding(engine, **kwargs):
        return _base_dispatch_result(
            findings=[{"id": "f", "file": "a.py", "title": "t", "body": "b"}],
            engagement={
                "tokens": 10,
                "toolCalls": None,
                "stdoutBytes": 1,
                "wallSeconds": 8.0,
            },
        )

    out_fast = SC.run_canary(
        "codex", engine_model="m", effort="high", repo_root="/r", dispatch=dispatch_finding,
    )
    assert out_fast["engaged"] is True


def test_tool_calls_engagement_ladder():
    def dispatch_one(engine, **kwargs):
        return _base_dispatch_result(
            engagement={"tokens": None, "toolCalls": 1, "stdoutBytes": 0, "wallSeconds": 0.0},
        )

    assert SC.run_canary(
        "cursor", engine_model="c", effort="high", repo_root="/r", dispatch=dispatch_one,
    )["engaged"] is True

    def dispatch_zero(engine, **kwargs):
        return _base_dispatch_result(
            engagement={"tokens": None, "toolCalls": 0, "stdoutBytes": 0, "wallSeconds": 0.0},
        )

    assert SC.run_canary(
        "cursor", engine_model="c", effort="high", repo_root="/r", dispatch=dispatch_zero,
    )["engaged"] is False


def test_investigated_without_findings_engaged():
    def dispatch(engine, **kwargs):
        return _base_dispatch_result(
            investigated=["lib/a.py"],
            engagement={"tokens": None, "toolCalls": None, "stdoutBytes": 0, "wallSeconds": 0.0},
        )

    out = SC.run_canary(
        "codex", engine_model="m", effort="high", repo_root="/r", dispatch=dispatch,
    )
    assert out["engaged"] is True
    assert out["evidence"]["investigated"] == 1


def test_unrunnable_attempts_zero_not_engaged_despite_telemetry():
    def dispatch(engine, **kwargs):
        return {
            "ok": False,
            "reason": "unrunnable",
            "detail": "repo-root-missing",
            "attempts": 0,
            "forfeited": False,
            "engagement": {"tokens": 99999, "toolCalls": 5, "stdoutBytes": 1, "wallSeconds": 1.0},
        }

    out = SC.run_canary(
        "codex", engine_model="m", effort="high", repo_root="/r", dispatch=dispatch,
    )
    assert out["engaged"] is False
    assert out["outcome"] == "unrunnable"
    assert out["detail"].startswith("not-dispatched:")


def test_dispatch_raises_becomes_unrunnable_no_escape():
    def dispatch(engine, **kwargs):
        raise RuntimeError("boom")

    out = SC.run_canary(
        "codex", engine_model="m", effort="high", repo_root="/r", dispatch=dispatch,
    )
    assert out["outcome"] == "unrunnable"
    assert out["engaged"] is False
    assert "RuntimeError" in out["detail"]


def test_no_residue_and_repo_untouched(tmp_path):
    repo = _repo(tmp_path)
    marker = tmp_path / "repo" / "marker.txt"
    paths_seen = []

    def dispatch(engine, *, prompt_path, repo_root, **kwargs):
        paths_seen.append(prompt_path)
        assert os.path.isfile(prompt_path)
        return _base_dispatch_result()

    SC.run_canary(
        "codex", engine_model="m", effort="high", repo_root=repo, dispatch=dispatch,
    )
    assert marker.read_text(encoding="utf-8") == "keep-me"
    for p in paths_seen:
        assert not os.path.exists(p)


def test_dispatch_receives_fixture_prompt_and_repo_root(tmp_path):
    repo = _repo(tmp_path)
    seen = {}

    def dispatch(engine, *, prompt_path, repo_root, **kwargs):
        seen["prompt_path"] = prompt_path
        seen["repo_root"] = repo_root
        assert os.path.isfile(prompt_path)
        with open(prompt_path, encoding="utf-8") as fh:
            seen["contents"] = fh.read()
        return _base_dispatch_result()

    SC.run_canary(
        "codex", engine_model="m", effort="high", repo_root=repo, dispatch=dispatch,
    )
    assert seen["repo_root"] == repo
    assert SC.PLANT_MARKER in seen["contents"]
    assert "investigated" in seen["contents"]


def test_detected_plant_does_not_drive_engaged():
    # detectedPlant True requires a finding carrying PLANT_MARKER, which also satisfies the
    # engagement OR-ladder — combination unconstructible. Pin: engaged logic never reads detectedPlant.
    src_path = os.path.join(_HERE, "..", "seat_canary.py")
    with open(src_path, encoding="utf-8") as fh:
        src = fh.read()
    engaged_block = re.search(
        r"def _engaged_from_dispatch\(.*?(?=\ndef |\Z)", src, re.DOTALL)
    assert engaged_block is not None
    assert "detectedPlant" not in engaged_block.group(0)
    assert "detected_plant" not in engaged_block.group(0)


def test_dispatch_exception_still_cleans_temp_file(tmp_path):
    repo = _repo(tmp_path)
    created = []

    def dispatch(engine, *, prompt_path, **kwargs):
        created.append(prompt_path)
        raise ValueError("nope")

    SC.run_canary(
        "codex", engine_model="m", effort="high", repo_root=repo, dispatch=dispatch,
    )
    assert created
    assert not os.path.exists(created[0])
