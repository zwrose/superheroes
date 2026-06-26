"""Publication gate for test-pilot readiness status."""

import json
import os
import subprocess

import control_plane
import ref_lock


def _park(reason):
    return {"ok": False, "verdict": "park", "reason": reason}


def _read_status(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("status JSON must be an object")
    return data


def _default_push(branch, force=False):
    if force:
        return False
    result = subprocess.run(
        ["git", "push", "origin", "HEAD:%s" % branch],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.returncode == 0


def _default_read_pr_head(branch):
    result = subprocess.run(
        ["git", "ls-remote", "origin", "refs/heads/%s" % branch],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout.split()[0]


def _default_write_status(path, status):
    control_plane.atomic_write(path, json.dumps(status, sort_keys=True))
    return status


def _generation(status):
    value = status.get("generation", status.get("lockGeneration"))
    return value if isinstance(value, int) and value > 0 else None


def publish(work_item, head, status_json, *, renew=None, fence_ok=None, push=None,
            read_pr_head=None, write_status=None):
    """Publish the tested head to the existing PR branch and mark status ready last."""
    try:
        status = _read_status(status_json)
    except (OSError, ValueError) as exc:
        return _park("malformed status JSON: %s" % exc)

    branch = status.get("branch")
    store = status.get("store") or control_plane.ensure_store(os.getcwd())
    generation = _generation(status)
    if not isinstance(branch, str) or not branch.strip():
        return _park("branch missing from status JSON")
    if not store:
        return _park("control-plane store unavailable")
    if generation is None:
        return _park("lock generation missing from status JSON")

    renew = renew or ref_lock.renew
    fence_ok = fence_ok or ref_lock.fence_ok
    push = push or _default_push
    read_pr_head = read_pr_head or _default_read_pr_head
    write_status = write_status or _default_write_status

    if not renew(store, work_item, generation):
        return _park("lease renewal failed before publish")
    if not fence_ok(store, work_item, generation):
        return _park("fence check failed before publish")

    before = read_pr_head(branch)
    if not before:
        return _park("existing PR branch is required before publish")

    if not push(branch, force=False):
        return _park("non-force push to PR branch failed")

    remote_head = read_pr_head(branch)
    if remote_head != head:
        return _park("remote PR head does not equal final tested head")

    ready_status = dict(status)
    ready_status["ready"] = True
    ready_status["remotePr"] = {"branch": branch, "head": head}
    write_status(status_json, ready_status)
    return {"ok": True, "verdict": "published", "branch": branch, "head": head}
