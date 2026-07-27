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
        return _base_dispatch_result(
            investigated=[],
            engagement={
                "tokens": 50000,
                "toolCalls": None,
                "stdoutBytes": 999,
                "wallSeconds": 120.0,
            },
        )

    out = SC.run_canary(
        "codex", engine_model="m", effort="high", repo_root="/r", dispatch=dispatch,
    )
    assert out["engaged"] is False
    assert out["outcome"] == "ok"


def test_wall_time_alone_not_engaged():
    def dispatch(engine, **kwargs):
        return _base_dispatch_result(
            engagement={
                "tokens": None,
                "toolCalls": None,
                "stdoutBytes": 0,
                "wallSeconds": 600.0,
            },
        )

    out = SC.run_canary(
        "codex", engine_model="m", effort="high", repo_root="/r", dispatch=dispatch,
    )
    assert out["engaged"] is False
    assert out["outcome"] == "ok"


def test_vacuous_with_tool_calls_still_engaged_path_alive():
    def dispatch(engine, **kwargs):
        return {
            "ok": False,
            "reason": "vacuous",
            "attempts": 2,
            "forfeited": True,
            "findings": [],
            "engagement": {
                "tokens": 50000,
                "toolCalls": 30,
                "stdoutBytes": 999,
                "wallSeconds": 600.0,
            },
            "disclosure": "vacuous seat",
        }

    out = SC.run_canary(
        "codex", engine_model="m", effort="high", repo_root="/r", dispatch=dispatch,
    )
    assert out["engaged"] is True
    assert out["outcome"] == "vacuous"
    assert out["detail"] == ""


def test_finding_with_fast_wall_engaged():
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

    out = SC.run_canary(
        "codex", engine_model="m", effort="high", repo_root="/r", dispatch=dispatch_finding,
    )
    assert out["engaged"] is True


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


def _engagement_decision_source(src):
    parts = []
    for name in ("_engaged_from_dispatch", "run_canary"):
        m = re.search(rf"def {name}\(.*?(?=\ndef |\Z)", src, re.DOTALL)
        assert m is not None, "missing function %s" % name
        parts.append(m.group(0))
    return "\n".join(parts)


def _assert_engaged_not_branched_on_plant_detection(engagement_src, full_src):
    # Pin: engagement never consults plant detection. Cannot prove absence of all indirect
    # coupling — only that no `engaged` assignment names detected_plant and detected_plant is
    # not referenced outside its compute line and the returned dict entry.
    assert not re.search(r"if\s+detected_plant\b", engagement_src)
    assert not re.search(r"if\s+detectedPlant\b", engagement_src)
    for line in engagement_src.splitlines():
        stripped = line.strip()
        if re.search(r"\bengaged\b", line) and "=" in line and not stripped.startswith("#"):
            assert "detected_plant" not in line
            assert "detectedPlant" not in line
    for line in full_src.splitlines():
        if not re.search(r"\bdetected_plant\b", line) and "detectedPlant" not in line:
            continue
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if re.match(r"\s*detected_plant\s*=", line):
            continue
        if re.search(r'["\']detectedPlant["\']\s*:', line):
            continue
        raise AssertionError(
            "detected_plant/detectedPlant referenced outside assignment and return: %r"
            % stripped
        )


def test_detected_plant_does_not_drive_engaged():
    # detectedPlant True requires a finding carrying PLANT_MARKER, which also satisfies the
    # engagement OR-ladder — combination unconstructible at the behavioural layer.
    def dispatch(engine, **kwargs):
        return _base_dispatch_result(
            findings=[],
            engagement={"tokens": None, "toolCalls": None, "stdoutBytes": 0, "wallSeconds": 0.0},
        )

    out = SC.run_canary(
        "codex", engine_model="m", effort="high", repo_root="/r", dispatch=dispatch,
    )
    assert out["engaged"] is False
    assert out["detectedPlant"] is False

    src_path = os.path.join(_HERE, "..", "seat_canary.py")
    with open(src_path, encoding="utf-8") as fh:
        src = fh.read()
    engagement_src = _engagement_decision_source(src)
    _assert_engaged_not_branched_on_plant_detection(engagement_src, src)


def test_probe_passes_sanitized_view_from_dispatch(tmp_path):
    repo = _repo(tmp_path)
    block = {
        "strategy": "git-archive-export",
        "stripped": [".cursor"],
        "strippedCount": 1,
        "headSha": "deadbeef",
        "sourceDirty": False,
        "buildSeconds": 0.1,
        "bytes": 100,
        "fileCount": 5,
    }

    def dispatch(engine, **kwargs):
        return _base_dispatch_result(sanitizedView=block)

    out = SC.run_canary(
        "codex", engine_model="m", effort="high", repo_root=repo, dispatch=dispatch,
    )
    assert out["sanitizedView"] == block


def test_probe_passes_sanitized_view_on_vacuous_dispatch(tmp_path):
    repo = _repo(tmp_path)
    block = {
        "strategy": "git-archive-export",
        "stripped": [".cursor"],
        "strippedCount": 1,
        "headSha": "deadbeef",
        "sourceDirty": False,
        "buildSeconds": 0.1,
        "bytes": 100,
        "fileCount": 5,
    }

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
            "sanitizedView": block,
        }

    out = SC.run_canary(
        "codex", engine_model="m", effort="high", repo_root=repo, dispatch=dispatch,
    )
    assert out["sanitizedView"] == block


def test_probe_sanitized_view_absent_when_dispatch_unrunnable(tmp_path):
    def dispatch(engine, **kwargs):
        return {
            "ok": False,
            "reason": "unrunnable",
            "detail": "repo-root-missing",
            "attempts": 0,
            "forfeited": False,
        }

    out = SC.run_canary(
        "codex", engine_model="m", effort="high", repo_root="/r", dispatch=dispatch,
    )
    assert out.get("sanitizedView") is None


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
