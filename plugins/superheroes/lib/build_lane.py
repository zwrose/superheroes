#!/usr/bin/env python3
"""Build-lane scope marker writer (#624 §4.2).

Workhorse full-lane intake declares ``build-lane.json`` beside the handback sidecar so the
receipt gate can arm before review starts. stdlib only."""
import argparse
import json
import os
import sys
import tempfile
import time

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import store_core  # noqa: E402

BUILD_LANE_FILE = "build-lane.json"
BUILD_LANE_SCHEMA = "build-lane/1"
SIDECAR_DIRNAME = "superheroes"


def _iso8601_utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _atomic_write_json(path, payload):
    text = json.dumps(payload, sort_keys=True) + "\n"
    directory = os.path.dirname(os.path.abspath(path)) or "."
    tmp = None
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".build-lane-", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


def _resolve_branch(repo_root):
    branch = store_core.run_git(repo_root, "rev-parse", "--abbrev-ref", "HEAD")
    if not branch or branch == "HEAD":
        raise ValueError("detached HEAD — no branch name")
    return branch


def _marker_path(repo_root):
    gitdir = store_core.get_worktree_gitdir(repo_root)
    return os.path.join(gitdir, SIDECAR_DIRNAME, BUILD_LANE_FILE)


def _validate_issue(issue):
    if issue is None or (isinstance(issue, str) and not issue.strip()):
        return False, "missing issue"
    text = str(issue).strip()
    if not text.isdigit():
        return False, "issue must be numeric"
    return True, text


def _ensure_git_repository(repo_root):
    res = store_core.run_git_result(repo_root, "rev-parse", "--is-inside-work-tree")
    return res.status == store_core.GIT_OK and res.out == "true"


def declare(repo_root, lane, issue):
    """Declare a full-lane build scope marker. Returns ``{ok: True, path, marker}`` or
    ``{ok: False, reason}``."""
    if lane != "full":
        return {"ok": False, "reason": "lane must be full"}
    ok, issue_or_reason = _validate_issue(issue)
    if not ok:
        return {"ok": False, "reason": issue_or_reason}
    issue = issue_or_reason
    try:
        resolved_root = store_core.repo_root(repo_root)
    except store_core.RepoRootUnavailable as exc:
        return {"ok": False, "reason": "repo root unresolvable: %s" % exc}
    resolved_root = os.path.realpath(resolved_root)
    if not _ensure_git_repository(resolved_root):
        return {"ok": False, "reason": "not a repository"}
    try:
        branch = _resolve_branch(resolved_root)
        path = _marker_path(resolved_root)
    except Exception as exc:
        return {"ok": False, "reason": str(exc)}
    marker = {
        "schema": BUILD_LANE_SCHEMA,
        "lane": "full",
        "issue": issue,
        "declaredAt": _iso8601_utc(),
        "repoRoot": resolved_root,
        "branch": branch,
    }
    try:
        _atomic_write_json(path, marker)
    except OSError as exc:
        return {"ok": False, "reason": "marker unwritable: %s" % exc}
    return {"ok": True, "path": path, "marker": marker}


def clear(repo_root):
    """Remove the build-lane marker when present. Idempotent when absent."""
    try:
        resolved_root = store_core.repo_root(repo_root)
        path = _marker_path(resolved_root)
    except Exception:
        return {"ok": True, "removed": False}
    if os.path.isfile(path):
        try:
            os.unlink(path)
        except OSError as exc:
            return {"ok": False, "reason": "marker not removable: %s" % exc}
        return {"ok": True, "removed": True}
    return {"ok": True, "removed": False}


def _emit(result):
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")


def main(argv):
    ap = argparse.ArgumentParser(description="build-lane scope marker")
    sub = ap.add_subparsers(dest="cmd", required=True)
    decl = sub.add_parser("declare")
    decl.add_argument("--repo-root", required=True)
    decl.add_argument("--lane", required=True)
    decl.add_argument("--issue", required=True)
    clr = sub.add_parser("clear")
    clr.add_argument("--repo-root", required=True)
    args = ap.parse_args(argv[1:])
    if args.cmd == "declare":
        result = declare(args.repo_root, args.lane, args.issue)
        _emit(result)
        return 0 if result.get("ok") else 1
    result = clear(args.repo_root)
    _emit(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
