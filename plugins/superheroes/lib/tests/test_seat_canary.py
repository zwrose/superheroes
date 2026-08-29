import importlib.util
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load():
    spec = importlib.util.spec_from_file_location(
        "seat_canary", os.path.join(_HERE, "..", "seat_canary.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_engine_adapter():
    spec = importlib.util.spec_from_file_location(
        "engine_adapter", os.path.join(_HERE, "..", "engine_adapter.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_canary_outcome():
    spec = importlib.util.spec_from_file_location(
        "canary_outcome", os.path.join(_HERE, "..", "canary_outcome.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SC = _load()
EA = _load_engine_adapter()
CO = _load_canary_outcome()

_PLUGIN_ROOT = os.path.join(_HERE, "..", "..")


def _count_fabricate_canary_probes_for_defs():
    count = 0
    for dirpath, _, filenames in os.walk(_PLUGIN_ROOT):
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            with open(os.path.join(dirpath, fn), encoding="utf-8") as fh:
                for line in fh:
                    if re.match(r"def fabricate_canary_probes_for\s*\(", line):
                        count += 1
    return count


def test_fabricate_canary_probes_for_single_definition():
    assert _count_fabricate_canary_probes_for_defs() == 1


def _load_fabricate_canary_probes_for():
    eval_dir = os.path.join(_PLUGIN_ROOT, "eval")
    saved = list(sys.path)
    try:
        if eval_dir not in sys.path:
            sys.path.insert(0, eval_dir)
        spec = importlib.util.spec_from_file_location(
            "review_loop_runner",
            os.path.join(eval_dir, "review_loop_runner.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.fabricate_canary_probes_for
    finally:
        sys.path[:] = saved


def test_fabricate_canary_probes_for_non_dict_map_empty():
    fabricate = _load_fabricate_canary_probes_for()
    assert fabricate(None) == []
    assert fabricate("not-a-map") == []


def test_fabricate_canary_probes_for_non_dict_seats_empty():
    fabricate = _load_fabricate_canary_probes_for()
    assert fabricate({"seats": None}) == []
    assert fabricate({"seats": "bad"}) == []


def test_fabricate_canary_probes_for_claude_and_invalid_vendors_skipped():
    fabricate = _load_fabricate_canary_probes_for()
    seat_map = {
        "seats": {
            "a": {"vendor": "claude"},
            "b": {"vendor": ""},
            "c": {"vendor": 42},
            "d": {},
            "e": {"vendor": "codex"},
        }
    }
    assert fabricate(seat_map) == [{
        "engine": "codex",
        "outcome": "ok",
        "engaged": True,
        "detectedPlant": True,
        "evidence": {},
        "detail": "",
    }]


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
            investigated=["lib/gate.py"],
            engagement={"tokens": 100, "toolCalls": None, "stdoutBytes": 50, "wallSeconds": 1.0},
        )

    out = SC.run_canary(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        repo_root="/tmp/fake", dispatch=dispatch,
    )
    assert out["engaged"] is True
    assert out["outcome"] == CO.OUTCOME_OK
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
    assert out["outcome"] == CO.OUTCOME_NOT_ENGAGED


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
    assert out["outcome"] == CO.OUTCOME_NOT_ENGAGED


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
            investigated=["a.py"],
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


def test_non_terminal_running_maps_to_non_terminal_slice():
    def dispatch(engine, **kwargs):
        return {
            "ok": False,
            "terminal": False,
            "reason": "running",
        }

    out = SC.run_canary(
        "codex", engine_model="m", effort="high", repo_root="/r", dispatch=dispatch,
    )
    assert out["outcome"] == "unrunnable"
    assert out["detail"] == "not-dispatched: non-terminal-slice"


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
        seen["kwargs"] = kwargs
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


def test_run_canary_pins_findings_expected_result_kind(tmp_path):
    """#1145 WO-B: canary production dispatch pins findings to match its fixture contract."""
    # axis: run_canary must pass expected_result_kind=findings to dispatch_review
    repo = _repo(tmp_path)
    seen = {}

    def dispatch(engine, **kwargs):
        seen.update(kwargs)
        return _base_dispatch_result()

    SC.run_canary(
        "codex", engine_model="m", effort="high", repo_root=repo, dispatch=dispatch,
    )
    assert seen.get("expected_result_kind") == "findings"


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


def test_engaged_from_dispatch_diverges_from_engagement_read():
    findings_only = {
        "findings": [{"id": "f"}],
        "investigated": [],
        "engagement": {"toolCalls": None},
    }
    assert EA.engagement_read(findings_only) == "engaged"
    assert SC._engaged_from_dispatch(findings_only) is False

    investigated_case = {
        "findings": [],
        "investigated": ["lib/a.py"],
        "engagement": {"toolCalls": None},
    }
    assert SC._engaged_from_dispatch(investigated_case) is True
    assert EA.engagement_read(investigated_case) == "engaged"

    tool_calls_case = {
        "findings": [],
        "investigated": [],
        "engagement": {"toolCalls": 2},
    }
    assert SC._engaged_from_dispatch(tool_calls_case) is True
    assert EA.engagement_read(tool_calls_case) == "engaged"

    no_evidence_case = {
        "findings": [],
        "investigated": [],
        "engagement": {"toolCalls": None},
    }
    assert SC._engaged_from_dispatch(no_evidence_case) is False
    assert EA.engagement_read(no_evidence_case) != "engaged"


def test_dod_row1_field_recurrence_specimen_not_engaged():
    def dispatch(engine, **kwargs):
        return _base_dispatch_result(
            findings=[{"id": "f", "file": "x.py", "title": "t", "body": "b"}],
            investigated=[],
            engagement={
                "tokens": None,
                "toolCalls": None,
                "stdoutBytes": 0,
                "wallSeconds": 20.0,
            },
        )

    out = SC.run_canary(
        "codex", engine_model="m", effort="high", repo_root="/r", dispatch=dispatch,
    )
    assert out["engaged"] is False
    assert out["outcome"] == CO.OUTCOME_NOT_ENGAGED
    assert out["detail"] == "no-investigation-evidence"


def test_dod_row2_engaged_dispatch_plant_undetected_when_marker_missing():
    def dispatch(engine, **kwargs):
        return _base_dispatch_result(
            findings=[{"id": "f", "file": "lib/gate.py", "title": "other", "body": "b"}],
            investigated=["lib/gate.py"],
            engagement={"tokens": 10, "toolCalls": 1, "stdoutBytes": 1, "wallSeconds": 1.0},
        )

    out = SC.run_canary(
        "codex", engine_model="m", effort="high", repo_root="/r", dispatch=dispatch,
    )
    assert out["engaged"] is True
    assert out["detectedPlant"] is False
    assert out["outcome"] == CO.OUTCOME_PLANT_UNDETECTED
    assert CO.is_pass(out["outcome"]) is False
    assert out["detail"] == "plant-undetected"


def test_classify_totality_cross_product():
    dispatch_members = [
        CO.REASON_FORFEITED,
        CO.REASON_VACUOUS,
        CO.REASON_FORFEIT_ENGAGED_ARTIFACT,
        CO.REASON_UNRUNNABLE,
        None,
    ]
    boolish = (True, False, None, "yes")
    for dispatch_member in dispatch_members:
        for engaged in boolish:
            for detected_plant in boolish:
                outcome = CO.classify(
                    dispatch_reason_outcome=dispatch_member,
                    engaged=engaged,
                    detected_plant=detected_plant,
                )
                assert outcome in CO.ALL_OUTCOMES
                assert outcome is not None


def test_normalize_probe_not_a_mapping():
    outcome, fault = CO.normalize("not-a-map")
    assert outcome == CO.OUTCOME_NOT_ENGAGED
    assert fault == "canary-probe-not-a-mapping"


def test_normalize_outcome_absent():
    outcome, fault = CO.normalize({"engaged": False, "detectedPlant": False})
    assert outcome == CO.OUTCOME_NOT_ENGAGED
    assert fault == "canary-outcome-absent"


def test_normalize_outcome_unknown():
    outcome, fault = CO.normalize({
        "outcome": "bogus",
        "engaged": True,
        "detectedPlant": True,
    })
    assert outcome == CO.OUTCOME_OK
    assert fault == "canary-outcome-unknown:'bogus'"


def test_normalize_outcome_ok_contradicts_fields():
    outcome, fault = CO.normalize({
        "outcome": CO.OUTCOME_OK,
        "engaged": True,
        "detectedPlant": False,
    })
    assert outcome == CO.OUTCOME_PLANT_UNDETECTED
    assert fault == "canary-outcome-contradicts-fields"
    assert CO.is_pass(outcome) is False


def test_normalize_valid_probe_passes_through():
    outcome, fault = CO.normalize({
        "outcome": CO.OUTCOME_NOT_ENGAGED,
        "engaged": False,
        "detectedPlant": False,
    })
    assert outcome == CO.OUTCOME_NOT_ENGAGED
    assert fault is None


def test_canary_outcome_member_literals_pinned():
    assert CO.OUTCOME_OK == "ok"
    assert CO.OUTCOME_NOT_ENGAGED == "not-engaged"
    assert CO.OUTCOME_PLANT_UNDETECTED == "plant-undetected"


def _run_main(monkeypatch, argv):
    """Drive the probe CLI with run_canary stubbed; return the kwargs it was called with."""
    seen = {}

    def fake_run_canary(engine, **kwargs):
        seen["engine"] = engine
        seen.update(kwargs)
        return {"engine": engine, "engaged": False}

    monkeypatch.setattr(SC, "run_canary", fake_run_canary)
    assert SC.main(argv) == 0
    return seen


def test_cli_effort_omitted_passes_none(monkeypatch):
    # #963: cursor's implementer/code-fixer registry config is effort-LESS — ("composer-2.5", None).
    # Omitting --effort must reach the seat path as None, not as any effort string.
    seen = _run_main(monkeypatch, [
        "probe", "--engine", "cursor", "--engine-model", "composer-2.5", "--repo-root", "/r",
    ])
    assert seen["effort"] is None
    assert seen["engine"] == "cursor"
    assert seen["engine_model"] == "composer-2.5"


def test_cli_effort_supplied_passes_through(monkeypatch):
    # The other direction: an explicit effort is still carried verbatim, unchanged by #963.
    seen = _run_main(monkeypatch, [
        "probe", "--engine", "codex", "--engine-model", "gpt-5.6-terra",
        "--effort", "high", "--repo-root", "/r",
    ])
    assert seen["effort"] == "high"
    assert seen["engine"] == "codex"
    assert seen["engine_model"] == "gpt-5.6-terra"


def test_effort_none_builds_cursor_argv_and_still_refuses_where_effort_required():
    """End of the chain the CLI feeds: effort=None is what makes cursor's effort-less seat runnable.

    Grounds the #963 DoD — the probe reaches the engine — without dispatching one, and pins that
    the relaxation is CLI-side only: a model that requires an effort still refuses without one.
    """
    runnable = EA.build_argv_result("cursor", "review", None, {"engine_model": "composer-2.5"})
    assert runnable["reason"] is None
    assert runnable["argv"]

    # Unchanged fail-closed edges: an effort string on the effort-less model, and a missing effort
    # on models that require one.
    assert EA.build_argv_result(
        "cursor", "review", "high", {"engine_model": "composer-2.5"},
    )["reason"] == "invalid-model-effort"
    assert EA.build_argv_result(
        "cursor", "review", None, {"engine_model": "cursor-grok-4.6"},
    )["reason"] == "invalid-model-effort"
    assert EA.build_argv_result(
        "codex", "review", None, {"engine_model": "gpt-5.6-terra"},
    )["reason"] == "invalid-model-effort"


def test_map_outcome_engaged_artifact_not_unrunnable():
    """axis: dispatched-and-engaged vs not-dispatched — honest member, not unrunnable fall-through."""
    res = {
        "ok": False,
        "reason": "forfeit-with-engaged-artifact",
        "forfeited": True,
        "disclosure": "transport failed",
        "salvage": {"attempt": 1},
    }
    outcome, detail = SC._map_outcome(res)
    assert outcome == "forfeit-with-engaged-artifact"
    assert detail == "transport failed"
    assert "not-dispatched" not in detail


def test_run_canary_engaged_artifact_not_engaged():
    def dispatch(engine, **kwargs):
        return {
            "ok": False,
            "reason": "forfeit-with-engaged-artifact",
            "forfeited": True,
            "disclosure": "seat produced review; not credited",
            "salvage": {"attempt": 1, "excerpt": "review prose"},
            "engagement": {"read": "engaged", "toolCalls": 5},
        }

    out = SC.run_canary(
        "codex", engine_model="m", effort="high", repo_root="/r", dispatch=dispatch,
    )
    assert out["outcome"] == "forfeit-with-engaged-artifact"
    assert out["engaged"] is False
    assert "not credited" in out["detail"]
