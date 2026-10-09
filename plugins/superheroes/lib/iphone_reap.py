#!/usr/bin/env python3
"""Reap a finished iPhone lane's simulated phones (FR-18/UFR-7).

The advisor runs this once a lane is terminal: it deletes the phones that lane's launch records
name, records one result per phone-carrying launch on the ledger, and reports what it could not
delete. It only ever deletes the phones the lane's records name, and it never runs a command that
could stop Device Hub or any other phone. Never raises to callers."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import launch_ledger as ll  # noqa: E402

DELETE_TIMEOUT = 60
CENSUS_TIMEOUT = 30
_DETAIL_LIMIT = 200

RESULT_DELETED = "deleted"
RESULT_ALREADY_GONE = "already-gone"
RESULT_LEFT_RUNNING = "left-running"
_CENSUS_UNREADABLE = "census-unreadable"


def _default_run(argv, timeout):
    """The one runner every simulator command goes through."""
    return subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _delete_argv(udid):
    """The one argv the helper may send to remove a phone; no other verb exists here."""
    # axis: the only delete command is `simctl delete <udid>` for a single named device.
    return ["xcrun", "simctl", "delete", udid]


def _census_argv():
    """The one other argv: list every device so a failed delete can be told from a gone phone."""
    return ["xcrun", "simctl", "list", "devices", "-j"]


def _is_issue(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _failure(issue, reason, **extra):
    result = {"ok": False, "reason": reason, "issue": issue}
    result.update(extra)
    return result


def lane_phones(repo_root, issue, env=None):
    """List the phones a lane's launch records name, and the launches still live.

    ``phones`` covers every launch for the issue that carries a phone, in reserved-record order,
    including relaunches and launches that were refused or failed after reserving.
    ``liveLaunches`` covers every launch for the issue, phone or not, that is not terminal.
    """
    if not _is_issue(issue):
        return _failure(issue, "reap-issue-invalid", phones=[], liveLaunches=[])

    read_result = ll.read(repo_root, env=env)
    if read_result["state"] != "ok":
        return _failure(issue, "reap-ledger-unreadable:%s" % read_result["state"],
                        phones=[], liveLaunches=[])

    folded = ll.fold(read_result["records"])
    if not folded["ok"]:
        return _failure(issue, "reap-ledger-fold-refused:%s" % folded["reason"],
                        phones=[], liveLaunches=[])

    phones = []
    live = []
    for launch_id, info in folded["launches"].items():
        # axis: lane scoping -- only launches whose issue is this lane's issue are in the lane.
        if info.get("issue") != issue:
            continue
        if info.get("iphoneId") is not None:
            phones.append({
                "launchId": launch_id,
                "iphoneId": info["iphoneId"],
                "terminal": bool(info.get("terminal")),
            })
        if not info.get("terminal"):
            live.append(launch_id)
    return {"ok": True, "reason": None, "issue": issue, "phones": phones, "liveLaunches": live}


def _first_line(text):
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line[:_DETAIL_LIMIT]
    return ""


def _census(run):
    """The set of device ids simctl lists, or None when the census cannot be read.

    Never raises. Any unexpected shape is unreadable, and unreadable is never absence.
    """
    try:
        proc = run(_census_argv(), CENSUS_TIMEOUT)
        if proc.returncode != 0:
            return None
        data = json.loads(proc.stdout)
    except Exception:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("devices"), dict):
        return None
    udids = set()
    for devices in data["devices"].values():
        if not isinstance(devices, list):
            return None
        for device in devices:
            if not isinstance(device, dict) or not isinstance(device.get("udid"), str):
                return None
            udids.add(device["udid"].upper())
    return udids


def _reap_phone(udid, run):
    """Delete one phone; return (result, detail). Never raises."""
    try:
        proc = run(_delete_argv(udid), DELETE_TIMEOUT)
        returncode = proc.returncode
        output = "%s\n%s" % (
            proc.stderr if isinstance(proc.stderr, str) else "",
            proc.stdout if isinstance(proc.stdout, str) else "",
        )
        detail = _first_line(output) or "exit %s" % returncode
    except Exception as exc:
        returncode = None
        detail = _first_line("%s: %s" % (type(exc).__name__, exc)) or type(exc).__name__
    if returncode == 0:
        return RESULT_DELETED, None

    census = _census(run)
    # axis: an unreadable census is never absence; only a valid census lacking the id is gone.
    if census is None:
        return RESULT_LEFT_RUNNING, _CENSUS_UNREADABLE
    if udid.upper() not in census:
        return RESULT_ALREADY_GONE, None
    return RESULT_LEFT_RUNNING, detail


def _note(udid, result, detail):
    if result == RESULT_DELETED:
        return "reap: phone %s deleted" % udid
    if result == RESULT_ALREADY_GONE:
        return "reap: phone %s already gone" % udid
    return "reap: phone %s left running: %s" % (udid, detail)


def reap_lane(repo_root, issue, run=None, env=None):
    """Delete the phones a finished lane's records name; record one result per launch.

    Refuses, running nothing, while any launch for the issue is live. A phone that could not be
    deleted or a result that could not be recorded makes the reap not ok.
    """
    run = _default_run if run is None else run
    lane = lane_phones(repo_root, issue, env=env)
    if not lane["ok"]:
        return _failure(issue, lane["reason"], phones=[], leftRunning=[], recordFailures=[])
    # axis: a lane with any live launch is refused before any runner call is made.
    if lane["liveLaunches"]:
        return _failure(issue, "reap-lane-not-terminal:%s" % lane["liveLaunches"][0],
                        phones=[], leftRunning=[], recordFailures=[])

    phones = []
    left_running = []
    record_failures = []
    outcomes = {}
    for entry in lane["phones"]:
        udid = entry["iphoneId"]
        if udid not in outcomes:
            outcomes[udid] = _reap_phone(udid, run)
            if outcomes[udid][0] == RESULT_LEFT_RUNNING:
                left_running.append(udid)
        result, detail = outcomes[udid]
        phones.append({
            "launchId": entry["launchId"],
            "iphoneId": udid,
            "result": result,
            "detail": detail,
        })
        amended = ll.amend(repo_root, entry["launchId"], "evidence", "reap",
                           _note(udid, result, detail), env=env)
        if not amended["ok"]:
            record_failures.append({
                "launchId": entry["launchId"],
                "iphoneId": udid,
                "result": result,
                "reason": amended["reason"],
            })

    ok = not left_running and not record_failures
    return {
        "ok": ok,
        "reason": None if ok else "reap-incomplete",
        "issue": issue,
        "phones": phones,
        "leftRunning": left_running,
        "recordFailures": record_failures,
    }


def _parse_issue(text):
    # A non-numeric issue is passed through as text so the verb answers with reap-issue-invalid.
    return int(text) if text.isascii() and text.isdigit() else text


def main(argv=None):
    parser = argparse.ArgumentParser(prog="iphone_reap")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("phones", "reap"):
        verb = sub.add_parser(name)
        verb.add_argument("--repo-root", required=True)
        verb.add_argument("--issue", required=True)
    args = parser.parse_args(argv)

    issue = _parse_issue(args.issue)
    if args.command == "phones":
        result = lane_phones(args.repo_root, issue)
    else:
        result = reap_lane(args.repo_root, issue)
    print(json.dumps(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
