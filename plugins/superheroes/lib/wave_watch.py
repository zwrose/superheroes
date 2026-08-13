#!/usr/bin/env python3
"""Ledger-driven single-shot wave watcher (#982).

Watch one launch batch until the first qualifying event. stdlib only.

Contract:
- Refusals (ok=False): batch-invalid, interval-invalid, max-seconds-invalid,
  repo-root-invalid, store-unresolvable, internal-error.
- Events (ok=True): lane-terminal, lane-blocked, builder-exited, pr-set-changed,
  timer.
- Degradations (non-fatal): ledger-unreadable, heartbeat-unreadable,
  pid-probe-uncertain, pr-signal-unavailable.
- Precedence: lane-terminal (E1) > lane-blocked (E2) > builder-exited (E3) >
  pr-set-changed (E4) > timer (E5).
"""
import argparse
import json
import os
import subprocess
import sys
import time

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import launch_ledger as ll  # noqa: E402
import heartbeat as hb  # noqa: E402

_GH_PR_LIST_ARGV = [
    "gh", "pr", "list", "--state", "open", "--json", "number", "--limit", "1000",
]


def _pid_is_live(pid):
    """True live, False exited, None uncertain. Never signals, never waits."""
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return None
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None


def _refusal(reason, batch_id):
    return {"ok": False, "reason": reason, "batchId": batch_id}


def _valid_positive_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _valid_batch_id(batch_id):
    if batch_id is None or not isinstance(batch_id, str) or not batch_id.strip():
        return False
    return True


def _valid_repo_root(repo_root):
    if not isinstance(repo_root, str) or not repo_root:
        return False
    return os.path.isdir(repo_root)


def _event_result(event, batch_id, degraded, **payload):
    result = {
        "ok": True,
        "event": event,
        "batchId": batch_id,
        "degraded": sorted(degraded),
    }
    result.update(payload)
    return result


def _derive_live_lanes(repo_root, batch_id, env, degraded):
    read_result = ll.read(repo_root, env=env)
    state = read_result["state"]
    if state in ("ok", "tornTail"):
        records = read_result["records"]
    elif state == "missing":
        records = []
    elif state in ("unreadable", "interiorCorrupt"):
        degraded.add("ledger-unreadable")
        return {}
    else:
        degraded.add("ledger-unreadable")
        return {}

    folded = ll.fold(records)
    if not folded["ok"]:
        degraded.add("ledger-unreadable")
        return {}

    return {
        lid: info
        for lid, info in folded["launches"].items()
        if info.get("batchId") == batch_id and not info.get("terminal")
    }


def _evaluate_lane_heartbeats(repo_root, live_lanes, env, degraded):
    """One heartbeat read per lane; derive E1 terminal and E2 blocked lists."""
    terminal_launches = []
    blocked_launches = []
    for lid in sorted(live_lanes):
        hb_result = hb.read_heartbeat(repo_root, lid, env=env)
        hb_class = hb_result.get("class")
        hb_reason = hb_result.get("reason")
        if hb_class == "unknown" and hb_reason != "heartbeat-missing":
            degraded.add("heartbeat-unreadable")
            continue
        if hb_class == "terminal":
            terminal_launches.append({
                "launchId": lid,
                "state": hb_result.get("state"),
            })
        elif hb_result.get("state") == "blocked":
            blocked_launches.append({
                "launchId": lid,
                "state": "blocked",
            })
    return terminal_launches, blocked_launches


def _evaluate_builder_exited(live_lanes, degraded):
    exited_launches = []
    pids = []
    for lid in sorted(live_lanes):
        info = live_lanes[lid]
        if not info.get("started"):
            continue
        pid = info.get("pid")
        if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
            continue
        live = _pid_is_live(pid)
        if live is None:
            degraded.add("pid-probe-uncertain")
            continue
        if not live:
            pids.append(pid)
            exited_launches.append({"launchId": lid, "pid": pid})
    if not exited_launches:
        return None
    return pids, exited_launches


def _parse_pr_numbers(stdout):
    try:
        parsed = json.loads(stdout)
    except (ValueError, TypeError):
        return None
    if not isinstance(parsed, list):
        return None
    numbers = []
    for item in parsed:
        if not isinstance(item, dict):
            return None
        number = item.get("number")
        if not isinstance(number, int) or isinstance(number, bool):
            return None
        numbers.append(number)
    return numbers


def _evaluate_pr_set_changed(
    repo_root, deadline, monotonic, gh_run, pr_baseline, degraded,
):
    remaining = deadline - monotonic()
    timeout = max(1, min(30, int(remaining)))
    try:
        proc = gh_run(
            _GH_PR_LIST_ARGV,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=repo_root,
        )
    except Exception:
        degraded.add("pr-signal-unavailable")
        return None, pr_baseline

    if proc.returncode != 0:
        degraded.add("pr-signal-unavailable")
        return None, pr_baseline

    numbers = _parse_pr_numbers(proc.stdout)
    if numbers is None:
        degraded.add("pr-signal-unavailable")
        return None, pr_baseline

    pr_set = set(numbers)
    if pr_baseline is None:
        return None, pr_set
    if pr_set == pr_baseline:
        return None, pr_baseline
    added = sorted(pr_set - pr_baseline)
    removed = sorted(pr_baseline - pr_set)
    return {
        "prs": sorted(pr_set),
        "prsAdded": added,
        "prsRemoved": removed,
    }, pr_baseline


def run(
    repo_root,
    batch_id,
    *,
    max_seconds=2400,
    interval_seconds=60,
    env=None,
    gh_run=None,
    monotonic=None,
    sleep=None,
):
    """Watch one batch until the first event. Returns the result dict; never raises."""
    batch_for_refusal = batch_id if isinstance(batch_id, str) else None
    try:
        if env is None:
            env = os.environ
        if gh_run is None:
            gh_run = subprocess.run
        if monotonic is None:
            monotonic = time.monotonic
        if sleep is None:
            sleep = time.sleep

        if not _valid_batch_id(batch_id):
            return _refusal("batch-invalid", batch_for_refusal)
        batch_id = batch_id.strip()

        if not _valid_positive_int(interval_seconds):
            return _refusal("interval-invalid", batch_id)
        if not _valid_positive_int(max_seconds):
            return _refusal("max-seconds-invalid", batch_id)
        if not _valid_repo_root(repo_root):
            return _refusal("repo-root-invalid", batch_id)

        ledger_path_result = ll.ledger_path(repo_root, env=env)
        if not ledger_path_result["ok"]:
            return _refusal("store-unresolvable", batch_id)

        start = monotonic()
        deadline = start + max_seconds
        tick = 0
        pr_baseline = None
        degraded = set()

        while True:
            live_lanes = _derive_live_lanes(repo_root, batch_id, env, degraded)

            terminal_launches, blocked_launches = _evaluate_lane_heartbeats(
                repo_root, live_lanes, env, degraded,
            )
            if terminal_launches:
                return _event_result(
                    "lane-terminal",
                    batch_id,
                    degraded,
                    launchId=terminal_launches[0]["launchId"],
                    launches=terminal_launches,
                )

            if blocked_launches:
                return _event_result(
                    "lane-blocked",
                    batch_id,
                    degraded,
                    launchId=blocked_launches[0]["launchId"],
                    launches=blocked_launches,
                )

            exited = _evaluate_builder_exited(live_lanes, degraded)
            if exited is not None:
                pids, exited_launches = exited
                return _event_result(
                    "builder-exited",
                    batch_id,
                    degraded,
                    pids=pids,
                    launches=exited_launches,
                )

            pr_change, pr_baseline = _evaluate_pr_set_changed(
                repo_root, deadline, monotonic, gh_run, pr_baseline, degraded,
            )
            if pr_change is not None:
                return _event_result(
                    "pr-set-changed",
                    batch_id,
                    degraded,
                    **pr_change,
                )

            if monotonic() >= deadline:
                return _event_result("timer", batch_id, degraded)

            tick += 1
            target = min(start + tick * interval_seconds, deadline)
            naptime = target - monotonic()
            if naptime > 0:
                sleep(naptime)
    except Exception:
        return _refusal("internal-error", batch_for_refusal)


def _emit(result):
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")


def main(argv):
    ap = argparse.ArgumentParser(description="wave watcher")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--repo-root", required=True)
    run_parser.add_argument("--batch", required=True)
    run_parser.add_argument("--max-seconds", type=int, default=2400)
    run_parser.add_argument("--interval-seconds", type=int, default=60)
    args = ap.parse_args(argv[1:])
    if args.cmd != "run":
        return 1
    result = run(
        args.repo_root,
        args.batch,
        max_seconds=args.max_seconds,
        interval_seconds=args.interval_seconds,
    )
    _emit(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
