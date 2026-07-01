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


def _default_local_head():
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _default_push(branch, force=False, head=None):
    if force:
        return False
    src = head or "HEAD"
    result = subprocess.run(
        ["git", "push", "origin", "%s:refs/heads/%s" % (src, branch)],
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
            read_pr_head=None, write_status=None, local_head=None,
            expected_branch=None, store=None, generation=None,
            protected_branches=None):
    """Publish the tested head to the existing PR branch and mark status ready last."""
    try:
        status = _read_status(status_json)
    except (OSError, ValueError) as exc:
        return _park("malformed status JSON: %s" % exc)

    branch = expected_branch or status.get("branch")
    if expected_branch and status.get("branch") != expected_branch:
        return _park("status branch does not match trusted PR branch")
    status_store = status.get("store")
    if store and status_store and os.path.realpath(str(status_store)) != os.path.realpath(str(store)):
        return _park("status store does not match trusted control-plane store")
    if not store:
        store = control_plane.ensure_store(os.getcwd())
    status_generation = _generation(status)
    if generation is None:
        generation = status_generation
    elif not isinstance(generation, int) or generation <= 0:
        return _park("trusted lock generation is missing or invalid")
    elif status_generation is not None and generation != status_generation:
        return _park("status lock generation does not match trusted generation")
    if not isinstance(branch, str) or not branch.strip():
        return _park("branch missing from status JSON")
    protected = set(protected_branches or ["main", "master"])
    if branch in protected:
        return _park("refusing to publish test-pilot head to protected/default branch")
    if not store:
        return _park("control-plane store unavailable")
    if generation is None:
        return _park("lock generation missing from status JSON")

    renew = renew or ref_lock.renew
    fence_ok = fence_ok or ref_lock.fence_ok
    push = push or _default_push
    read_pr_head = read_pr_head or _default_read_pr_head
    write_status = write_status or _default_write_status
    local_head = local_head or _default_local_head

    current = local_head() if callable(local_head) else local_head
    if current != head:
        return _park("local HEAD does not equal final tested head")

    if not renew(store, work_item, generation):
        return _park("lease renewal failed before publish")
    if not fence_ok(store, work_item, generation):
        return _park("fence check failed before publish")

    before = read_pr_head(branch)
    if not before:
        return _park("existing PR branch is required before publish")

    if not push(branch, force=False, head=head):
        return _park("non-force push to PR branch failed")

    remote_head = read_pr_head(branch)
    if remote_head != head:
        return _park("remote PR head does not equal final tested head")

    ready_status = dict(status)
    ready_status["ready"] = True
    ready_status["remotePr"] = {"branch": branch, "head": head}
    write_status(status_json, ready_status)
    try:
        reread = _read_status(status_json)
    except (OSError, ValueError):
        return _park("published head but status read-back failed")
    read_back = (
        reread.get("ready") is True
        and isinstance(reread.get("remotePr"), dict)
        and reread["remotePr"].get("head") == head
        and reread["remotePr"].get("branch") == branch
        and read_pr_head(branch) == head
    )
    return {"ok": True, "verdict": "published", "branch": branch, "head": head, "read_back": bool(read_back)}
