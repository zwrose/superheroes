import json
import subprocess
import sys

import test_pilot_publish as publish


def _status(tmp_path, **overrides):
    data = {
        "branch": "codex/issue-90",
        "generation": 4,
        "store": str(tmp_path / "store"),
    }
    data.update(overrides)
    path = tmp_path / "status.json"
    path.write_text(json.dumps(data))
    return path, data


def test_publish_renews_fences_pushes_non_force_and_writes_ready_status(tmp_path):
    status_path, data = _status(tmp_path)
    calls = []
    written = []

    result = publish.publish(
        "issue-90",
        "abc123",
        str(status_path),
        renew=lambda store, work_item, generation: calls.append(("renew", store, work_item, generation)) or True,
        fence_ok=lambda store, work_item, generation: calls.append(("fence", store, work_item, generation)) or True,
        local_head=lambda: "abc123",
        expected_branch="codex/issue-90",
        store=data["store"],
        generation=4,
        push=lambda branch, force=False, head=None: calls.append(("push", branch, force, head)) or True,
        read_pr_head=lambda branch: calls.append(("read_pr_head", branch)) or "abc123",
        write_status=lambda path, status: written.append((path, status)) or status,
    )

    assert result == {"ok": True, "verdict": "published", "branch": "codex/issue-90", "head": "abc123"}
    assert calls == [
        ("renew", data["store"], "issue-90", 4),
        ("fence", data["store"], "issue-90", 4),
        ("read_pr_head", "codex/issue-90"),
        ("push", "codex/issue-90", False, "abc123"),
        ("read_pr_head", "codex/issue-90"),
    ]
    assert written == [
        (
            str(status_path),
            {
                "branch": "codex/issue-90",
                "generation": 4,
                "store": data["store"],
                "ready": True,
                "remotePr": {"branch": "codex/issue-90", "head": "abc123"},
            },
        )
    ]


def test_publish_parks_when_lease_cannot_renew_and_does_not_push_or_write(tmp_path):
    status_path, data = _status(tmp_path)
    calls = []

    result = publish.publish(
        "issue-90",
        "abc123",
        str(status_path),
        renew=lambda *args: False,
        fence_ok=lambda *args: calls.append("fence") or True,
        local_head=lambda: "abc123",
        store=data["store"],
        push=lambda *args, **kwargs: calls.append("push") or True,
        read_pr_head=lambda *args: calls.append("read") or "abc123",
        write_status=lambda *args: calls.append("write"),
    )

    assert result["verdict"] == "park"
    assert "lease" in result["reason"]
    assert calls == []


def test_publish_parks_when_fence_fails_before_push(tmp_path):
    status_path, data = _status(tmp_path)
    calls = []

    result = publish.publish(
        "issue-90",
        "abc123",
        str(status_path),
        renew=lambda *args: True,
        fence_ok=lambda *args: False,
        local_head=lambda: "abc123",
        store=data["store"],
        push=lambda *args, **kwargs: calls.append("push") or True,
        read_pr_head=lambda *args: calls.append("read") or "abc123",
        write_status=lambda *args: calls.append("write"),
    )

    assert result["verdict"] == "park"
    assert "fence" in result["reason"]
    assert calls == []


def test_publish_requires_existing_remote_pr_branch(tmp_path):
    status_path, data = _status(tmp_path)
    calls = []

    result = publish.publish(
        "issue-90",
        "abc123",
        str(status_path),
        renew=lambda *args: True,
        fence_ok=lambda *args: True,
        local_head=lambda: "abc123",
        store=data["store"],
        push=lambda *args, **kwargs: calls.append("push") or True,
        read_pr_head=lambda branch: None,
        write_status=lambda *args: calls.append("write"),
    )

    assert result["verdict"] == "park"
    assert "existing PR branch" in result["reason"]
    assert calls == []


def test_publish_parks_when_remote_pr_head_does_not_equal_tested_head(tmp_path):
    status_path, data = _status(tmp_path)
    calls = []

    result = publish.publish(
        "issue-90",
        "abc123",
        str(status_path),
        renew=lambda *args: True,
        fence_ok=lambda *args: True,
        local_head=lambda: "abc123",
        store=data["store"],
        push=lambda branch, force=False, head=None: calls.append(("push", force, head)) or True,
        read_pr_head=lambda branch: "def456",
        write_status=lambda *args: calls.append("write"),
    )

    assert result["verdict"] == "park"
    assert "remote PR head" in result["reason"]
    assert calls == [("push", False, "abc123")]


def test_publish_parks_before_push_when_local_head_is_not_tested_head(tmp_path):
    status_path, data = _status(tmp_path)
    calls = []

    result = publish.publish(
        "issue-90",
        "abc123",
        str(status_path),
        renew=lambda *args: True,
        fence_ok=lambda *args: True,
        local_head=lambda: "def456",
        store=data["store"],
        push=lambda *args, **kwargs: calls.append("push") or True,
        read_pr_head=lambda branch: calls.append("read") or "abc123",
        write_status=lambda *args: calls.append("write"),
    )

    assert result["verdict"] == "park"
    assert "local HEAD" in result["reason"]
    assert calls == []


def test_publish_rejects_status_branch_mismatch_against_trusted_branch(tmp_path):
    status_path, _ = _status(tmp_path, branch="main")
    calls = []

    result = publish.publish(
        "issue-90",
        "abc123",
        str(status_path),
        expected_branch="codex/issue-90",
        local_head=lambda: "abc123",
        renew=lambda *args: calls.append("renew") or True,
        fence_ok=lambda *args: calls.append("fence") or True,
        push=lambda *args, **kwargs: calls.append("push") or True,
        read_pr_head=lambda branch: calls.append("read") or "abc123",
        write_status=lambda *args: calls.append("write"),
    )

    assert result["verdict"] == "park"
    assert "trusted PR branch" in result["reason"]
    assert calls == []


def test_publish_rejects_status_store_mismatch_against_trusted_store(tmp_path):
    status_path, _ = _status(tmp_path, store=str(tmp_path / "untrusted-store"))
    calls = []

    result = publish.publish(
        "issue-90",
        "abc123",
        str(status_path),
        store=str(tmp_path / "trusted-store"),
        local_head=lambda: calls.append("local_head") or "abc123",
        renew=lambda *args: calls.append("renew") or True,
        fence_ok=lambda *args: calls.append("fence") or True,
        push=lambda *args, **kwargs: calls.append("push") or True,
        read_pr_head=lambda branch: calls.append("read") or "abc123",
        write_status=lambda *args: calls.append("write"),
    )

    assert result["verdict"] == "park"
    assert "trusted control-plane store" in result["reason"]
    assert calls == []


def test_publish_rejects_invalid_trusted_generation_before_remote_action(tmp_path):
    status_path, data = _status(tmp_path, generation=0)
    calls = []

    result = publish.publish(
        "issue-90",
        "abc123",
        str(status_path),
        store=data["store"],
        generation=0,
        local_head=lambda: calls.append("local_head") or "abc123",
        renew=lambda *args: calls.append("renew") or True,
        fence_ok=lambda *args: calls.append("fence") or True,
        push=lambda *args, **kwargs: calls.append("push") or True,
        read_pr_head=lambda branch: calls.append("read") or "abc123",
        write_status=lambda *args: calls.append("write"),
    )

    assert result["verdict"] == "park"
    assert "generation" in result["reason"]
    assert calls == []


def test_publish_rejects_status_generation_mismatch_before_remote_action(tmp_path):
    status_path, data = _status(tmp_path, generation=3)
    calls = []

    result = publish.publish(
        "issue-90",
        "abc123",
        str(status_path),
        store=data["store"],
        generation=4,
        local_head=lambda: calls.append("local_head") or "abc123",
        renew=lambda *args: calls.append("renew") or True,
        fence_ok=lambda *args: calls.append("fence") or True,
        push=lambda *args, **kwargs: calls.append("push") or True,
        read_pr_head=lambda branch: calls.append("read") or "abc123",
        write_status=lambda *args: calls.append("write"),
    )

    assert result["verdict"] == "park"
    assert "status lock generation" in result["reason"]
    assert calls == []


def test_publish_parks_when_non_force_push_fails(tmp_path):
    status_path, data = _status(tmp_path)
    calls = []
    written = []

    result = publish.publish(
        "issue-90",
        "abc123",
        str(status_path),
        renew=lambda store, work_item, generation: calls.append(("renew", store, work_item, generation)) or True,
        fence_ok=lambda store, work_item, generation: calls.append(("fence", store, work_item, generation)) or True,
        local_head=lambda: "abc123",
        store=data["store"],
        generation=4,
        push=lambda branch, force=False, head=None: calls.append(("push", branch, force, head)) or False,
        read_pr_head=lambda branch: calls.append(("read_pr_head", branch)) or "abc123",
        write_status=lambda path, status: written.append((path, status)) or status,
    )

    assert result["verdict"] == "park"
    assert "non-force push" in result["reason"]
    assert calls == [
        ("renew", data["store"], "issue-90", 4),
        ("fence", data["store"], "issue-90", 4),
        ("read_pr_head", "codex/issue-90"),
        ("push", "codex/issue-90", False, "abc123"),
    ]
    assert written == []


def test_publish_refuses_protected_branch_before_any_remote_action(tmp_path):
    status_path, _ = _status(tmp_path, branch="main")
    calls = []

    result = publish.publish(
        "issue-90",
        "abc123",
        str(status_path),
        local_head=lambda: calls.append("local_head") or "abc123",
        renew=lambda *args: calls.append("renew") or True,
        fence_ok=lambda *args: calls.append("fence") or True,
        push=lambda *args, **kwargs: calls.append("push") or True,
        read_pr_head=lambda branch: calls.append("read") or "abc123",
        write_status=lambda *args: calls.append("write"),
    )

    assert result["verdict"] == "park"
    assert "protected/default branch" in result["reason"]
    assert calls == []


def test_cli_publish_prints_result_json(tmp_path):
    status_path, _ = _status(tmp_path, remotePr={"head": "abc123"})

    proc = subprocess.run(
        [
            sys.executable,
            "plugins/superheroes/lib/test_pilot_publish_cli.py",
            "publish",
            "--work-item",
            "issue-90",
            "--head",
            "abc123",
            "--status-json",
            str(status_path),
            "--expected-branch",
            "codex/issue-90",
            "--store",
            str(tmp_path / "store"),
            "--generation",
            "4",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    result = json.loads(proc.stdout)
    assert result["verdict"] in {"published", "park"}
