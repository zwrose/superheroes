#!/usr/bin/env python3
"""Advisory sibling-worktree delta observation for supervised write dispatches (#754).

Snapshots every *other* registered worktree at write-run open and again at fold time,
then compares head sha, porcelain sha256, and HEAD reflog entry count. Emits an
unattributed observed delta only — it cannot say who changed a sibling worktree.

stdlib only. Injectable command runner for unit tests. Public functions never raise."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

MAX_SIBLING_WORKTREES = 16
DEFAULT_DEADLINE_SECONDS = 30.0


def _git_env(base=None):
    env = dict(base if base is not None else os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return env


def _deadline_exhausted(deadline_end):
    return deadline_end is not None and time.monotonic() >= deadline_end


def _remaining_timeout(deadline_end):
    if deadline_end is None:
        return None
    return max(0.0, deadline_end - time.monotonic())


def _run_git(cwd, args, *, run, deadline_end, env):
    if _deadline_exhausted(deadline_end):
        return None, "deadline-exhausted"
    timeout = _remaining_timeout(deadline_end)
    if timeout is not None and timeout <= 0:
        return None, "deadline-exhausted"
    try:
        proc = run(
            ["git", "-C", cwd, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        return proc, None
    except subprocess.TimeoutExpired:
        return None, "deadline-exhausted"
    except Exception as exc:
        return None, str(exc)


def _parse_worktree_list(text):
    blocks = []
    current = {}
    for line in (text or "").splitlines():
        if not line.strip():
            if current:
                blocks.append(current)
                current = {}
            continue
        if line.startswith("worktree "):
            if current:
                blocks.append(current)
            current = {"path": line[len("worktree "):].strip()}
        elif line.startswith("HEAD "):
            current["head"] = line[len("HEAD "):].strip()
        elif line.startswith("branch "):
            current["branch"] = line[len("branch "):].strip()
        elif line == "bare":
            current["bare"] = True
        elif line == "detached":
            current["detached"] = True
        elif line == "locked":
            current["locked"] = True
        elif line.startswith("prunable "):
            current["prunable"] = True
    if current:
        blocks.append(current)
    return blocks


def _reflog_count(cwd, *, run, deadline_end, env):
    proc, err = _run_git(
        cwd, ("rev-list", "--walk-reflogs", "HEAD", "--count"),
        run=run, deadline_end=deadline_end, env=env,
    )
    if proc is None or proc.returncode != 0:
        return None
    text = (proc.stdout or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _porcelain_sha256(cwd, *, run, deadline_end, env):
    proc, err = _run_git(
        cwd, ("status", "--porcelain=v1"),
        run=run, deadline_end=deadline_end, env=env,
    )
    if proc is None or proc.returncode != 0:
        return None, err or "status-failed"
    porcelain = proc.stdout or ""
    return hashlib.sha256(porcelain.encode("utf-8")).hexdigest(), None


def _head_sha(cwd, *, run, deadline_end, env):
    proc, err = _run_git(
        cwd, ("rev-parse", "HEAD"),
        run=run, deadline_end=deadline_end, env=env,
    )
    if proc is None or proc.returncode != 0:
        return None, err or "head-failed"
    return (proc.stdout or "").strip(), None


def _probe_worktree(path, *, run, deadline_end, env):
    real_path = os.path.realpath(path)
    entry = {
        "path": real_path,
        "locked": False,
        "prunable": False,
        "disappeared": False,
    }
    if not os.path.exists(path):
        entry["disappeared"] = True
        entry["headSha"] = None
        entry["porcelainSha256"] = None
        entry["reflogCount"] = None
        return entry, None
    head, head_err = _head_sha(real_path, run=run, deadline_end=deadline_end, env=env)
    if head_err:
        return None, head_err
    porcelain, porcelain_err = _porcelain_sha256(
        real_path, run=run, deadline_end=deadline_end, env=env,
    )
    if porcelain_err:
        return None, porcelain_err
    entry["headSha"] = head
    entry["porcelainSha256"] = porcelain
    entry["reflogCount"] = _reflog_count(
        real_path, run=run, deadline_end=deadline_end, env=env,
    )
    return entry, None


def snapshot(repo_root, assigned_cwd, *, deadline=None, run=None, max_worktrees=None):
    """Snapshot every other registered worktree. Never raises."""
    if run is None:
        run = subprocess.run
    if max_worktrees is None:
        max_worktrees = MAX_SIBLING_WORKTREES
    deadline_end = None
    if deadline is not None:
        deadline_end = time.monotonic() + float(deadline)
    env = _git_env()
    try:
        assigned_real = os.path.realpath(assigned_cwd)
        repo_real = os.path.realpath(repo_root)
        proc, err = _run_git(
            repo_real, ("worktree", "list", "--porcelain"),
            run=run, deadline_end=deadline_end, env=env,
        )
        if proc is None or proc.returncode != 0:
            reason = err or "worktree-list-failed"
            if proc is not None and proc.returncode != 0:
                reason = "worktree-list-failed"
            return {"status": "indeterminate", "reason": reason}
        blocks = _parse_worktree_list(proc.stdout or "")
        siblings = []
        for block in blocks:
            wt_path = block.get("path")
            if not wt_path:
                continue
            if os.path.realpath(wt_path) == assigned_real:
                continue
            siblings.append(block)
        truncated = len(siblings) > max_worktrees
        if truncated:
            siblings = siblings[:max_worktrees]
        worktrees = {}
        for block in siblings:
            if _deadline_exhausted(deadline_end):
                return {
                    "status": "indeterminate",
                    "reason": "deadline-exhausted",
                    "partial": True,
                    "truncated": truncated,
                    "worktrees": worktrees,
                }
            wt_path = block["path"]
            entry, probe_err = _probe_worktree(
                wt_path, run=run, deadline_end=deadline_end, env=env,
            )
            if probe_err:
                return {
                    "status": "indeterminate",
                    "reason": probe_err,
                    "partial": bool(worktrees),
                    "truncated": truncated,
                    "worktrees": worktrees,
                }
            entry["locked"] = bool(block.get("locked"))
            entry["prunable"] = bool(block.get("prunable"))
            worktrees[entry["path"]] = entry
        return {
            "status": "ok",
            "truncated": truncated,
            "worktrees": worktrees,
        }
    except Exception as exc:
        return {"status": "indeterminate", "reason": str(exc)}


def _reflog_delta(before_val, after_val):
    if before_val is None or after_val is None:
        return None
    if before_val != after_val:
        return {"before": before_val, "after": after_val}
    return None


def compare(before, after):
    """Pure delta comparison between two snapshot dicts. Never raises."""
    try:
        if not isinstance(before, dict) or not isinstance(after, dict):
            return {"status": "indeterminate", "reason": "invalid-snapshot"}
        if before.get("status") != "ok" or after.get("status") != "ok":
            reason = after.get("reason") or before.get("reason") or "snapshot-indeterminate"
            return {"status": "indeterminate", "reason": reason}
        before_wt = before.get("worktrees") or {}
        after_wt = after.get("worktrees") or {}
        deltas = []
        all_paths = sorted(set(before_wt) | set(after_wt))
        for path in all_paths:
            b = before_wt.get(path)
            a = after_wt.get(path)
            if b is None and a is not None:
                deltas.append({"path": path, "kind": "appeared"})
                continue
            if a is None and b is not None:
                deltas.append({"path": path, "kind": "disappeared"})
                continue
            if b.get("disappeared") and not a.get("disappeared"):
                deltas.append({"path": path, "kind": "appeared"})
                continue
            if not b.get("disappeared") and a.get("disappeared"):
                deltas.append({"path": path, "kind": "disappeared"})
                continue
            if b.get("headSha") != a.get("headSha"):
                deltas.append({
                    "path": path,
                    "kind": "head-changed",
                    "before": b.get("headSha"),
                    "after": a.get("headSha"),
                })
            if b.get("porcelainSha256") != a.get("porcelainSha256"):
                deltas.append({
                    "path": path,
                    "kind": "porcelain-changed",
                    "before": b.get("porcelainSha256"),
                    "after": a.get("porcelainSha256"),
                })
            reflog = _reflog_delta(b.get("reflogCount"), a.get("reflogCount"))
            if reflog is not None:
                deltas.append({
                    "path": path,
                    "kind": "reflog-changed",
                    **reflog,
                })
        truncated = bool(before.get("truncated") or after.get("truncated"))
        return {"status": "observed", "deltas": deltas, "truncated": truncated}
    except Exception as exc:
        return {"status": "indeterminate", "reason": str(exc)}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Sibling worktree probe CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    snap = sub.add_parser("snapshot", help="Snapshot sibling worktrees")
    snap.add_argument("repo_root")
    snap.add_argument("assigned_cwd")
    snap.add_argument("--deadline", type=float, default=DEFAULT_DEADLINE_SECONDS)
    snap.add_argument("--max-worktrees", type=int, default=MAX_SIBLING_WORKTREES)

    cmp = sub.add_parser("compare", help="Compare two snapshot JSON files")
    cmp.add_argument("before_path")
    cmp.add_argument("after_path")

    args = parser.parse_args(argv)
    if args.command == "snapshot":
        result = snapshot(
            args.repo_root, args.assigned_cwd,
            deadline=args.deadline, max_worktrees=args.max_worktrees,
        )
    else:
        with open(args.before_path, encoding="utf-8") as fh:
            before = json.load(fh)
        with open(args.after_path, encoding="utf-8") as fh:
            after = json.load(fh)
        result = compare(before, after)
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
