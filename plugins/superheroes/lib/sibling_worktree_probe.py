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
MIN_DEADLINE_SECONDS = 10.0

_SIGNALS = ("headSha", "porcelainSha256", "reflogCount")


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
    if proc is None:
        return None, err or "reflog-unmeasured"
    if proc.returncode != 0:
        detail = ((proc.stdout or "") + (proc.stderr or "")).strip()
        return None, detail or "reflog-failed"
    text = (proc.stdout or "").strip()
    if not text:
        return None, "reflog-empty"
    try:
        return int(text), None
    except ValueError:
        return None, "reflog-unparseable"


def _porcelain_sha256(cwd, *, run, deadline_end, env):
    proc, err = _run_git(
        cwd, ("status", "--porcelain=v1"),
        run=run, deadline_end=deadline_end, env=env,
    )
    if proc is None:
        return None, err or "status-unmeasured"
    if proc.returncode != 0:
        detail = ((proc.stdout or "") + (proc.stderr or "")).strip()
        return None, detail or "status-failed"
    porcelain = proc.stdout or ""
    return hashlib.sha256(porcelain.encode("utf-8")).hexdigest(), None


def _head_sha(cwd, *, run, deadline_end, env):
    proc, err = _run_git(
        cwd, ("rev-parse", "HEAD"),
        run=run, deadline_end=deadline_end, env=env,
    )
    if proc is None:
        return None, err or "head-unmeasured"
    if proc.returncode != 0:
        detail = ((proc.stdout or "") + (proc.stderr or "")).strip()
        return None, detail or "head-failed"
    return (proc.stdout or "").strip(), None


def _unreadable_entry(real_path, reason):
    return {
        "path": real_path,
        "readable": False,
        "reason": reason,
        "locked": False,
        "prunable": False,
        "disappeared": False,
        "headSha": None,
        "headMeasured": False,
        "porcelainSha256": None,
        "porcelainMeasured": False,
        "reflogCount": None,
        "reflogMeasured": False,
    }


def _probe_worktree(path, *, run, deadline_end, env):
    real_path = os.path.realpath(path)
    if not os.path.exists(path):
        entry = _unreadable_entry(real_path, "path-missing")
        entry["disappeared"] = True
        return entry, None
    head, head_err = _head_sha(real_path, run=run, deadline_end=deadline_end, env=env)
    if head_err:
        return _unreadable_entry(real_path, head_err), None
    porcelain, porcelain_err = _porcelain_sha256(
        real_path, run=run, deadline_end=deadline_end, env=env,
    )
    if porcelain_err:
        return _unreadable_entry(real_path, porcelain_err), None
    reflog_count, reflog_err = _reflog_count(
        real_path, run=run, deadline_end=deadline_end, env=env,
    )
    return {
        "path": real_path,
        "readable": True,
        "locked": False,
        "prunable": False,
        "disappeared": False,
        "headSha": head,
        "headMeasured": True,
        "porcelainSha256": porcelain,
        "porcelainMeasured": True,
        "reflogCount": reflog_count,
        "reflogMeasured": reflog_err is None,
        **({"reflogUnmeasuredReason": reflog_err} if reflog_err else {}),
    }, None


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
            entry, _probe_err = _probe_worktree(
                wt_path, run=run, deadline_end=deadline_end, env=env,
            )
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


def _signal_measured(entry, signal):
    if not isinstance(entry, dict):
        return False
    if not entry.get("readable", True):
        return False
    key = signal + "Measured"
    if key in entry:
        return bool(entry[key])
    if signal == "reflogCount":
        return entry.get("reflogCount") is not None
    return entry.get(signal) is not None


def _reflog_delta(before_entry, after_entry):
    if not _signal_measured(before_entry, "reflogCount"):
        return None
    if not _signal_measured(after_entry, "reflogCount"):
        return None
    before_val = before_entry.get("reflogCount")
    after_val = after_entry.get("reflogCount")
    if before_val != after_val:
        return {"before": before_val, "after": after_val}
    return None


def _coverage_tally(before_wt, after_wt, all_paths):
    coverage = {
        "worktreesCompared": len(all_paths),
        "signals": {},
    }
    for signal in _SIGNALS:
        measured_before = 0
        measured_after = 0
        compared = 0
        for path in all_paths:
            b = before_wt.get(path) or {}
            a = after_wt.get(path) or {}
            b_ok = _signal_measured(b, signal)
            a_ok = _signal_measured(a, signal)
            if b_ok:
                measured_before += 1
            if a_ok:
                measured_after += 1
            if b_ok and a_ok:
                compared += 1
        coverage["signals"][signal] = {
            "measuredBefore": measured_before,
            "measuredAfter": measured_after,
            "compared": compared,
        }
    return coverage


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
            b = b or {}
            a = a or {}
            if not b.get("readable", True) or not a.get("readable", True):
                reason = a.get("reason") or b.get("reason") or "unreadable"
                deltas.append({"path": path, "kind": "unreadable", "reason": reason})
                continue
            if b.get("disappeared") and not a.get("disappeared"):
                deltas.append({"path": path, "kind": "appeared"})
                continue
            if not b.get("disappeared") and a.get("disappeared"):
                deltas.append({"path": path, "kind": "disappeared"})
                continue
            if (
                _signal_measured(b, "headSha")
                and _signal_measured(a, "headSha")
                and b.get("headSha") != a.get("headSha")
            ):
                deltas.append({
                    "path": path,
                    "kind": "head-changed",
                    "before": b.get("headSha"),
                    "after": a.get("headSha"),
                })
            if (
                _signal_measured(b, "porcelainSha256")
                and _signal_measured(a, "porcelainSha256")
                and b.get("porcelainSha256") != a.get("porcelainSha256")
            ):
                deltas.append({
                    "path": path,
                    "kind": "porcelain-changed",
                    "before": b.get("porcelainSha256"),
                    "after": a.get("porcelainSha256"),
                })
            reflog = _reflog_delta(b, a)
            if reflog is not None:
                deltas.append({
                    "path": path,
                    "kind": "reflog-changed",
                    **reflog,
                })
        truncated = bool(before.get("truncated") or after.get("truncated"))
        coverage = _coverage_tally(before_wt, after_wt, all_paths)
        return {
            "status": "observed",
            "deltas": deltas,
            "truncated": truncated,
            "coverage": coverage,
        }
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
