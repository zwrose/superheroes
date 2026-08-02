"""Tests for forfeit_ledger — durable ledger and attribution decider (#747)."""
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import dispatch_outcome as do  # noqa: E402
import forfeit_ledger as fl  # noqa: E402
import launch_ledger as ll  # noqa: E402


def _init_repo(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    (tmp_path / "file.txt").write_text("x\n")
    subprocess.run(
        [
            "git", "-C", str(tmp_path),
            "-c", "user.email=test@test.local",
            "-c", "user.name=test",
            "add", ".",
        ],
        check=True,
    )
    subprocess.run(
        [
            "git", "-C", str(tmp_path),
            "-c", "user.email=test@test.local",
            "-c", "user.name=test",
            "commit", "-q", "-m", "init",
        ],
        check=True,
    )
    return str(tmp_path)


def _ledger_env(tmp_path, monkeypatch):
    root = str(tmp_path / "ledger-root")
    os.makedirs(root, mode=0o700, exist_ok=True)
    monkeypatch.setenv(fl.LEDGER_ROOT_ENV, root)
    return root


def _minimal_row(**kwargs):
    defaults = {
        "run_dir": "/tmp/run",
        "order_id": "wo-1",
        "engine": "cursor",
        "attempt_count": 0,
    }
    defaults.update(kwargs)
    return fl.build_row(
        run_dir=defaults.get("run_dir"),
        order_id=defaults.get("order_id"),
        engine=defaults.get("engine"),
        engine_model=defaults.get("engine_model"),
        run_kind=defaults.get("run_kind"),
        reason=defaults.get("reason"),
        detail=defaults.get("detail"),
        attempt_count=defaults.get("attempt_count"),
        attempts=defaults.get("attempts"),
        stages=defaults.get("stages"),
        engagement=defaults.get("engagement"),
        evidence=defaults.get("evidence"),
        ok=defaults.get("ok"),
        at=defaults.get("at"),
    )


# --- storage ---


def test_append_read_round_trip(tmp_path, monkeypatch):
    """axis: append/read round-trip preserves ledger rows."""
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    row = _minimal_row(reason=do.REASON_FORFEITED, attempt_count=1)
    result = fl.append(repo, row)
    assert result["written"] is True
    assert result["deduped"] is False
    rows, corrupt = fl.read(repo)
    assert corrupt is False
    assert len(rows) == 1
    assert rows[0]["runId"] == row["runId"]


def test_two_appends_preserve_order(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    row1 = _minimal_row(run_dir="/tmp/run-a", order_id="a")
    row2 = _minimal_row(run_dir="/tmp/run-b", order_id="b")
    fl.append(repo, row1)
    fl.append(repo, row2)
    rows, _ = fl.read(repo)
    assert [r["orderId"] for r in rows] == ["a", "b"]


def test_read_skips_torn_trailing_line(tmp_path, monkeypatch):
    """axis: classification of damage — torn trailing line skipped, earlier rows survive."""
    repo = _init_repo(tmp_path / "repo")
    root = _ledger_env(tmp_path, monkeypatch)
    row = _minimal_row(run_dir="/tmp/good")
    fl.append(repo, row)
    path = fl.ledger_path(repo)
    with open(path, "ab") as fh:
        fh.write(b'{"broken":')
    rows, corrupt = fl.read(repo)
    assert len(rows) == 1
    assert rows[0]["runDir"] == "/tmp/good"
    assert corrupt is False


def test_read_interior_corrupt_sets_flag(tmp_path, monkeypatch):
    """axis: classification of damage — interior corrupt line sets interior_corrupt."""
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    row = _minimal_row(run_dir="/tmp/good")
    fl.append(repo, row)
    path = fl.ledger_path(repo)
    with open(path, "ab") as fh:
        fh.write(b"not-json\n")
    fl.append(repo, _minimal_row(run_dir="/tmp/after"))
    rows, corrupt = fl.read(repo)
    assert corrupt is True
    assert len(rows) == 2


def test_append_failure_when_root_unusable(tmp_path, monkeypatch):
    """axis: failure containment — OSError on append returns written=False, never raises."""
    repo = _init_repo(tmp_path / "repo")
    ledger_root = str(tmp_path / "ledger-root")
    monkeypatch.setenv(fl.LEDGER_ROOT_ENV, ledger_root)
    os.makedirs(ledger_root, mode=0o500)
    result = fl.append(repo, _minimal_row())
    assert result["written"] is False
    assert result["why"] is not None


def test_ledger_outside_repo(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    root = _ledger_env(tmp_path, monkeypatch)
    fl.append(repo, _minimal_row())
    path = fl.ledger_path(repo)
    assert path.startswith(root)
    repo_real = os.path.realpath(repo)
    assert not path.startswith(repo_real)


# --- decider specimens ---


def test_poster_child_review_vet11_1c4dda3():
    """Specimen: poster-child review (vet11-1c4dda3)."""
    row = fl.build_row(
        run_dir="/tmp/vet11",
        reason=do.REASON_FORFEITED,
        attempt_count=2,
        attempts=[
            {"attempt": 1, "exit": 0, "timedOut": False, "stdoutBytes": 1187},
            {"attempt": 2, "exit": 0, "timedOut": False, "stdoutBytes": 681},
        ],
        stages={"engaged": True, "delivered": False},
    )
    assert row["attribution"]["class"] == do.ATTRIBUTION_TRANSPORT


def test_prose_brief_check_transport():
    """Specimen: prose brief-check."""
    row = fl.build_row(
        run_dir="/tmp/prose",
        reason=do.REASON_FORFEITED,
        attempt_count=2,
        attempts=[
            {"attempt": 1, "exit": 0, "timedOut": False, "stdoutBytes": 2109},
            {"attempt": 2, "exit": 0, "timedOut": False, "stdoutBytes": 1743},
        ],
        stages={"engaged": None, "delivered": False},
    )
    assert row["attribution"]["class"] == do.ATTRIBUTION_TRANSPORT


def test_pre_spawn_refusal_caller_error():
    """Specimen: pre-spawn refusal."""
    row = fl.build_row(
        run_dir="/tmp/refused",
        reason=do.REASON_UNRUNNABLE,
        detail="engine-config:unknown-claude-tier",
        attempt_count=0,
        attempts=[],
    )
    assert row["attribution"]["class"] == do.ATTRIBUTION_CALLER_ERROR


def test_cap_truncated_our_environment():
    """Specimen: cap-truncated."""
    row = fl.build_row(
        run_dir="/tmp/cap",
        reason=do.REASON_FORFEITED,
        attempt_count=1,
        attempts=[
            {
                "attempt": 1,
                "timedOut": True,
                "capSeconds": 900,
                "silenceSeconds": 3.0,
            },
        ],
    )
    assert row["attribution"]["class"] == do.ATTRIBUTION_ENVIRONMENT


def test_silent_stall_unknown():
    """Specimen: silent stall."""
    row = fl.build_row(
        run_dir="/tmp/stall",
        reason=do.REASON_FORFEITED,
        attempt_count=1,
        attempts=[
            {
                "attempt": 1,
                "timedOut": True,
                "capSeconds": 900,
                "silenceSeconds": 812.0,
            },
        ],
    )
    assert row["attribution"]["class"] == do.ATTRIBUTION_UNKNOWN


def test_signalled_attempt_engine_side():
    row = fl.build_row(
        run_dir="/tmp/sig",
        reason=do.REASON_FORFEITED,
        attempt_count=1,
        attempts=[
            {"attempt": 1, "signal": 9, "signalSource": "engine"},
        ],
    )
    assert row["attribution"]["class"] == do.ATTRIBUTION_ENGINE_SIDE


def test_runner_inflicted_kill_is_environment_not_engine_side():
    """axis: who inflicted the kill — runner-timeout is our-environment, never engine-side."""
    row = fl.build_row(
        run_dir="/tmp/runner-kill",
        reason=do.REASON_FORFEITED,
        attempt_count=1,
        attempts=[
            {
                "attempt": 1,
                "exit": -15,
                "signal": 15,
                "signalSource": "runner-timeout",
                "timedOut": True,
                "silenceSeconds": 2.0,
                "capSeconds": 900,
            },
        ],
    )
    assert row["attribution"]["class"] == do.ATTRIBUTION_ENVIRONMENT
    assert row["attribution"]["class"] != do.ATTRIBUTION_ENGINE_SIDE


def test_runner_timeout_without_timed_out_not_engine_side():
    """axis: runner-timeout signalSource blocks engine-side even when timedOut is false."""
    row = fl.build_row(
        run_dir="/tmp/runner-timeout-guard",
        reason=do.REASON_FORFEITED,
        attempt_count=1,
        attempts=[
            {
                "attempt": 1,
                "exit": -15,
                "signal": 15,
                "signalSource": "runner-timeout",
                "timedOut": False,
            },
        ],
    )
    assert row["attribution"]["class"] != do.ATTRIBUTION_ENGINE_SIDE


def test_spawn_failed_refusal_is_environment_not_engine_side():
    """axis: which class a runner-inflicted failure books to — spawn-failed is our-environment."""
    row = fl.build_row(
        run_dir="/tmp/spawn-fail",
        reason=do.REASON_FORFEITED,
        attempt_count=1,
        attempts=[
            {
                "attempt": 1,
                "exit": 127,
                "timedOut": False,
                "refusal": "spawn-failed: [Errno 2] No such file or directory",
            },
        ],
    )
    assert row["attempts"][0]["attribution"]["class"] == do.ATTRIBUTION_ENVIRONMENT
    assert row["attribution"]["class"] == do.ATTRIBUTION_ENVIRONMENT
    assert row["attribution"]["class"] != do.ATTRIBUTION_ENGINE_SIDE


def test_journal_append_failed_refusal_is_environment():
    row = fl.build_row(
        run_dir="/tmp/journal-fail",
        reason=do.REASON_FORFEITED,
        attempt_count=1,
        attempts=[
            {
                "attempt": 1,
                "exit": 127,
                "timedOut": False,
                "refusal": "journal-append-failed",
            },
        ],
    )
    assert row["attribution"]["class"] == do.ATTRIBUTION_ENVIRONMENT


def test_unrecognised_refusal_is_unknown_not_engine_side():
    row = fl.build_row(
        run_dir="/tmp/unknown-refusal",
        attempt_count=1,
        reason=do.REASON_FORFEITED,
        attempts=[
            {
                "attempt": 1,
                "exit": 127,
                "timedOut": False,
                "refusal": "never-seen-before",
            },
        ],
    )
    assert row["attempts"][0]["attribution"]["class"] == do.ATTRIBUTION_UNKNOWN
    assert row["attribution"]["class"] == do.ATTRIBUTION_UNKNOWN


def test_classify_attempt_engine_signal():
    """axis: engine signalSource books engine-side at attempt level."""
    att = fl.classify_attempt(
        {"attempt": 1, "signal": 9, "signalSource": "engine"},
        {},
    )
    assert att["class"] == do.ATTRIBUTION_ENGINE_SIDE


def test_classify_attempt_transport():
    """axis: exit 0 with stdout but undelivered stages books transport at attempt level."""
    att = fl.classify_attempt(
        {
            "attempt": 1,
            "exit": 0,
            "timedOut": False,
            "stdoutBytes": 1187,
        },
        {"stages": {"delivered": False}},
    )
    assert att["class"] == do.ATTRIBUTION_TRANSPORT


def test_classify_attempt_environment_timeout():
    att = fl.classify_attempt(
        {
            "attempt": 1,
            "timedOut": True,
            "silenceSeconds": 3.0,
            "capSeconds": 900,
        },
        {},
    )
    assert att["class"] == do.ATTRIBUTION_ENVIRONMENT


def test_classify_attempt_empty_dict():
    att = fl.classify_attempt({}, {})
    assert att["class"] == do.ATTRIBUTION_UNKNOWN


def test_classify_attempt_none():
    att = fl.classify_attempt(None, {})
    assert att["class"] == do.ATTRIBUTION_UNKNOWN


# --- accounting ---


def test_summarize_successes_do_not_inflate_unattributed():
    """axis: who is counted as unattributed — successes are excluded."""
    rows = [
        _minimal_row(reason=None, ok=True, at=1.0),
        _minimal_row(reason=None, ok=True, at=2.0),
        _minimal_row(reason=do.REASON_FORFEITED, at=3.0),
    ]
    summary = fl.summarize(rows, now=10.0)
    assert summary["unattributed"] == 1
    assert summary["byAttribution"][do.ATTRIBUTION_UNKNOWN] == 1


def test_summarize_unrecognised_attribution_class_counts_unknown():
    row = _minimal_row(reason=do.REASON_FORFEITED, at=1.0)
    row = dict(row)
    row["attribution"] = {"class": "future-class", "why": "hand-edited"}
    summary = fl.summarize([row], now=10.0)
    assert summary["byAttribution"][do.ATTRIBUTION_UNKNOWN] == 1
    assert summary["unattributed"] == 1


def test_summarize_all_success_rates():
    rows = [
        _minimal_row(reason=None, ok=True, at=1.0),
        _minimal_row(reason=None, ok=True, at=2.0),
    ]
    summary = fl.summarize(rows, now=10.0)
    assert summary["forfeit"]["count"] == 0
    assert summary["forfeit"]["rate"] == 0.0
    assert summary["salvage"]["rate"] == 0.0
    assert summary["unattributed"] == 0


def test_summarize_interior_corrupt_flag():
    rows = [_minimal_row(at=1.0)]
    summary = fl.summarize(rows, interior_corrupt=True, now=10.0)
    assert summary["interiorCorrupt"] is True
    assert summary["completeness"] == fl._COMPLETENESS_PARTIAL


def test_summarize_window_and_attribution_keys():
    rows = [
        _minimal_row(reason=None, ok=True, at=100.0),
        _minimal_row(reason=do.REASON_FORFEITED, at=200.0),
    ]
    summary = fl.summarize(rows, window_seconds=500, now=1000.0)
    assert summary["window"]["seconds"] == 500
    assert summary["window"]["from"] == 500.0
    assert summary["window"]["to"] == 1000.0
    for key in do.ATTRIBUTIONS:
        assert key in summary["byAttribution"]


def test_summarize_salvage_rate_empty_is_none():
    summary = fl.summarize([])
    assert summary["total"] == 0
    assert summary["salvage"]["rate"] is None


def test_summarize_salvage_rate_fraction():
    rows = [
        _minimal_row(at=1.0),
        dict(_minimal_row(at=2.0), salvage={"detected": True}),
    ]
    summary = fl.summarize(rows, now=10.0)
    assert summary["salvage"]["count"] == 1
    assert summary["salvage"]["rate"] == 0.5


def test_summarize_window_filter_excludes_old_rows():
    rows = [
        _minimal_row(at=10.0),
        _minimal_row(at=1000.0),
    ]
    summary = fl.summarize(rows, window_seconds=100, now=1000.0)
    assert summary["total"] == 1


def test_summarize_forfeit_rate_includes_successes():
    """axis: the denominator includes successes — forfeit rate uses all terminal rows."""
    rows = [
        _minimal_row(reason=None, ok=True, at=1.0),
        _minimal_row(reason=None, ok=True, at=2.0),
        _minimal_row(reason=None, ok=True, at=3.0),
        _minimal_row(reason=do.REASON_FORFEITED, at=4.0),
    ]
    summary = fl.summarize(rows, now=10.0)
    assert summary["forfeit"]["count"] == 1
    assert summary["forfeit"]["rate"] == 0.25
    assert summary["completeness"] == fl._COMPLETENESS_LEDGER_ONLY


def test_append_idempotent_same_run_id(tmp_path, monkeypatch):
    """axis: refusal to double-count a continuation — repeat append dedupes on runId."""
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    row = _minimal_row(run_dir="/tmp/same")
    first = fl.append(repo, row)
    second = fl.append(repo, row)
    assert first["deduped"] is False
    assert second["deduped"] is True
    rows, _ = fl.read(repo)
    assert len(rows) == 1


def test_append_two_run_ids_two_lines(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    fl.append(repo, _minimal_row(run_dir="/tmp/a"))
    fl.append(repo, _minimal_row(run_dir="/tmp/b"))
    rows, _ = fl.read(repo)
    assert len(rows) == 2


def test_mixed_attribution_bc8():
    """axis: which cause wins when attempts disagree — mixed sets mixed and names both causes."""
    row = fl.build_row(
        run_dir="/tmp/mixed",
        reason=do.REASON_FORFEITED,
        attempt_count=2,
        attempts=[
            {
                "attempt": 1,
                "timedOut": True,
                "capSeconds": 900,
                "silenceSeconds": 3.0,
            },
            {
                "attempt": 2,
                "exit": 1,
                "timedOut": False,
            },
        ],
    )
    assert row["attempts"][0]["attribution"]["class"] == do.ATTRIBUTION_ENVIRONMENT
    assert row["attempts"][1]["attribution"]["class"] == do.ATTRIBUTION_ENGINE_SIDE
    assert row["attribution"]["class"] == do.ATTRIBUTION_ENGINE_SIDE
    assert row["attribution"]["mixed"] is True
    assert "our-environment" in row["attribution"]["why"]
    assert "engine-side" in row["attribution"]["why"]


def test_absence_tolerance_0230_keys():
    row = fl.build_row(
        run_dir="/tmp/old",
        attempt_count=1,
        reason=do.REASON_FORFEITED,
        attempts=[
            {
                "exit": 0,
                "timedOut": False,
                "signal": None,
                "refusal": None,
                "at": 1.0,
            },
        ],
    )
    assert "attribution" in row


def test_classify_empty_attempts_forfeited_is_unknown():
    row = {
        "reason": do.REASON_FORFEITED,
        "attemptCount": 1,
        "attempts": [],
        "stages": {"engaged": None, "delivered": None},
    }
    attr = fl.classify(row)
    assert attr["class"] == do.ATTRIBUTION_UNKNOWN


def test_append_non_serializable_returns_failure(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    row = _minimal_row()
    row["bad"] = {1, 2}
    result = fl.append(repo, row)
    assert result["written"] is False


def test_cli_report_empty_ledger(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    rc = fl.main(["report", "--repo-root", repo])
    assert rc == 0


def test_cli_human_prints_window(tmp_path, monkeypatch, capsys):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    fl.main(["report", "--repo-root", repo])
    out = capsys.readouterr().out
    assert "window:" in out
    assert "salvage:" in out
    assert "unattributed:" in out


def test_cli_json_summary(tmp_path, monkeypatch, capsys):
    """axis: that a ledger holding both successes and forfeits serialises."""
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    fl.append(repo, _minimal_row(reason=None, ok=True, run_dir="/tmp/success"))
    fl.append(repo, _minimal_row(reason=do.REASON_FORFEITED, run_dir="/tmp/forfeit"))
    fl.main(["report", "--repo-root", repo, "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["total"] == 2
    assert "ok" in payload["byReason"]
    assert do.REASON_FORFEITED in payload["byReason"]


def test_cli_report_interior_corrupt(tmp_path, monkeypatch, capsys):
    """axis: that lost rows are visible in the output — not that read computed the flag."""
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    fl.append(repo, _minimal_row(run_dir="/tmp/good"))
    path = fl.ledger_path(repo)
    with open(path, "ab") as fh:
        fh.write(b"not-json\n")
    fl.append(repo, _minimal_row(run_dir="/tmp/after"))
    fl.main(["report", "--repo-root", repo, "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["interiorCorrupt"] is True
    assert payload["completeness"] == fl._COMPLETENESS_PARTIAL


def test_append_after_torn_tail_repairs_and_preserves_rows(tmp_path, monkeypatch):
    """axis: append after torn tail cannot corrupt prior or new row."""
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    row = _minimal_row(run_dir="/tmp/good", order_id="before-torn")
    fl.append(repo, row)
    path = fl.ledger_path(repo)
    with open(path, "ab") as fh:
        fh.write(b'{"broken":')
    new_row = _minimal_row(run_dir="/tmp/after-torn", order_id="after-torn")
    result = fl.append(repo, new_row)
    assert result["written"] is True
    rows, corrupt = fl.read(repo)
    assert corrupt is False
    assert len(rows) == 2
    assert rows[0]["orderId"] == "before-torn"
    assert rows[1]["orderId"] == "after-torn"


def test_ledger_repo_dir_symlink_refused(tmp_path, monkeypatch):
    """axis: where the write lands — repo-id dir symlink refused."""
    repo = _init_repo(tmp_path / "repo")
    ledger_root = _ledger_env(tmp_path, monkeypatch)
    repo_id = ll.repo_identity(repo)
    real_dir = os.path.join(ledger_root, "real-target")
    os.makedirs(real_dir, mode=0o700)
    os.symlink(real_dir, os.path.join(ledger_root, repo_id))
    result = fl.append(repo, _minimal_row())
    assert result["written"] is False
    assert result["why"] == "ledger-repo-dir-symlink"


def test_ledger_file_symlink_refused(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    ledger_root = _ledger_env(tmp_path, monkeypatch)
    repo_id = ll.repo_identity(repo)
    repo_dir = os.path.join(ledger_root, repo_id)
    os.makedirs(repo_dir, mode=0o700)
    real_file = os.path.join(tmp_path, "real-ledger.jsonl")
    with open(real_file, "w", encoding="utf-8") as fh:
        fh.write("")
    os.symlink(real_file, os.path.join(repo_dir, fl.FORFEIT_LEDGER_FILE))
    result = fl.append(repo, _minimal_row())
    assert result["written"] is False
    assert result["why"] == "ledger-file-symlink"


def test_configured_root_symlink_accepted(tmp_path, monkeypatch):
    """Default-root /tmp symlink class: configured root symlink resolves and works."""
    repo = _init_repo(tmp_path / "repo")
    real_root = tmp_path / "real-ledger"
    os.makedirs(real_root, mode=0o700)
    link = tmp_path / "link-ledger"
    link.symlink_to(real_root)
    monkeypatch.setenv(fl.LEDGER_ROOT_ENV, str(link))
    result = fl.append(repo, _minimal_row())
    assert result["written"] is True
    rows, _ = fl.read(repo)
    assert len(rows) == 1


def test_ledger_file_symlink_inside_root_allowed(tmp_path, monkeypatch):
    """Fail-closed edge: symlink ledger inside default root is refused (not followed)."""
    repo = _init_repo(tmp_path / "repo")
    ledger_root = _ledger_env(tmp_path, monkeypatch)
    repo_id = ll.repo_identity(repo)
    repo_dir = os.path.join(ledger_root, repo_id)
    os.makedirs(repo_dir, mode=0o700)
    inside = os.path.join(repo_dir, "inside.jsonl")
    with open(inside, "w", encoding="utf-8") as fh:
        fh.write("")
    os.symlink(inside, os.path.join(repo_dir, fl.FORFEIT_LEDGER_FILE))
    result = fl.append(repo, _minimal_row())
    assert result["written"] is False
    assert result["why"] == "ledger-file-symlink"
