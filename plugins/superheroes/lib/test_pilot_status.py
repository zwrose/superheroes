"""Durable test-pilot readiness status.

Schema v1 is a small JSON object persisted beside the workhorse control-plane
checkpoint. Missing, malformed, stale, or parked evidence fails closed.
"""

import json
import os

import control_plane

SCHEMA_VERSION = 1


def status_path(cwd, work_item, root=None):
    return os.path.join(control_plane.paths(cwd, work_item, root=root)["issue_dir"],
                        "test-pilot-status.json")


def _ok(reason="ready"):
    return {"ok": True, "verdict": "ready", "reason": reason}


def _park(reason):
    return {"ok": False, "verdict": "park", "reason": reason}


def _status_problem(obj, expected_verdict=None):
    if not isinstance(obj, dict):
        return "test-pilot status is not a JSON object"
    if obj.get("schemaVersion") != SCHEMA_VERSION:
        return "test-pilot status schema is missing or unsupported"
    if expected_verdict is not None and obj.get("verdict") != expected_verdict:
        return "test-pilot status verdict is not %s" % expected_verdict
    return None


def read(path):
    with open(path, encoding="utf-8") as fh:
        obj = json.load(fh)
    if not isinstance(obj, dict):
        raise ValueError("test-pilot status is not a JSON object")
    return obj


def write(path, status):
    if not isinstance(status, dict):
        raise ValueError("test-pilot status must be a JSON object")
    data = dict(status)
    data.setdefault("schemaVersion", SCHEMA_VERSION)
    control_plane.atomic_write(path, json.dumps(data, sort_keys=True))
    return data


def _head_branch_current(status, head):
    if status.get("head") != head:
        return "stale head — test-pilot status head != current head"
    if not status.get("branch"):
        return "branch missing from test-pilot status"
    return None


def _records(status):
    records = status.get("records")
    return records if isinstance(records, list) else None


def _browser_executed(record):
    return (
        isinstance(record, dict)
        and (
            record.get("browserExecuted") is True
            or record.get("browser_executed") is True
            or record.get("browser") is True
            or record.get("kind") == "browser"
            or record.get("type") == "browser"
        )
    )


def _record_passed_or_allowed(record):
    if not isinstance(record, dict):
        return False
    result = record.get("status") or record.get("result")
    if result in {"passed", "pass"}:
        return True
    return result == "skipped" and record.get("allowed") is True and record.get("preserved") is True


def _artifact_present(artifacts, key):
    return isinstance(artifacts, dict) and bool(artifacts.get(key))


def _posting_failed(status):
    posting = status.get("prPosting") or status.get("posting") or status.get("pr_posting")
    return isinstance(posting, dict) and posting.get("ok") is False


def _fallback_present(artifacts):
    if not isinstance(artifacts, dict):
        return False
    fallback = artifacts.get("fallback") or artifacts.get("fallbacks")
    if isinstance(fallback, list) and fallback:
        return True
    return bool(artifacts.get("fallbackPlan") and artifacts.get("fallbackResults"))


def _covers_head(container, key, head):
    value = container.get(key) if isinstance(container, dict) else None
    if isinstance(value, dict):
        return value.get("head") == head or value.get("covers") == head
    return value == head


def _fixes_exist(status):
    fixes = status.get("fixes")
    if isinstance(fixes, dict):
        return bool(fixes.get("count") or fixes.get("applied") or fixes.get("head"))
    if isinstance(fixes, list):
        return bool(fixes)
    return bool(fixes)


def ready_applicable(status, head):
    problem = _status_problem(status, "applicable")
    if problem:
        return _park(problem)
    problem = _head_branch_current(status, head)
    if problem:
        return _park(problem)

    records = _records(status)
    if records is None or not records:
        return _park("test-pilot records missing")
    if not any(_browser_executed(record) for record in records):
        return _park("at least one browser-executed record is required")
    if not all(_record_passed_or_allowed(record) for record in records):
        return _park("one or more test-pilot records are not passed")

    artifacts = status.get("artifacts")
    if not _artifact_present(artifacts, "plan"):
        return _park("plan artifact missing")
    if not _artifact_present(artifacts, "results"):
        return _park("results artifact missing")
    if _posting_failed(status) and not _fallback_present(artifacts):
        return _park("fallback artifacts missing after PR posting failed")

    if not _covers_head(status, "baseline", head):
        return _park("fresh baseline at head missing")
    if not _covers_head(status, "review", head):
        return _park("review coverage at head missing")
    if _fixes_exist(status):
        verify = status.get("verify")
        verify_pass = isinstance(verify, dict) and verify.get("result") == "pass"
        verify_head = isinstance(verify, dict) and verify.get("head") == head
        if not verify_pass or not verify_head:
            return _park("verify-pass at head missing after fixes")
    if not _covers_head(status, "remotePr", head):
        return _park("remote PR head does not equal current head")

    return _ok("applicable test-pilot evidence is current")


def ready_not_applicable(status, head):
    problem = _status_problem(status, "not_applicable")
    if problem:
        return _park(problem)
    if status.get("head") != head:
        return _park("stale head — test-pilot status head != current head")
    if not status.get("rationale") and not status.get("reason"):
        return _park("not-applicable rationale missing")
    return _ok("not-applicable rationale is current")


def assert_current(path, head):
    try:
        status = read(path)
    except (OSError, ValueError) as exc:
        return _park("test-pilot status missing or malformed: %s" % exc)
    problem = _status_problem(status)
    if problem:
        return _park(problem)
    verdict = status.get("verdict")
    if verdict == "applicable":
        return ready_applicable(status, head)
    if verdict == "not_applicable":
        return ready_not_applicable(status, head)
    return _park("test-pilot status verdict is park or unknown")
