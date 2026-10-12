"""The advisor's recovery of a stopped cloud builder: what it pushed, whether it may be replaced,
the ask to push, the successor's premise, and the board's words.

  cloud_recover.py pushed --repo-root D --repo O/N --issue N
  cloud_recover.py assess --repo-root D --launch-id L --repo O/N --session-state S [--activity-age-seconds N]
  cloud_recover.py ask --repo-root D --launch-id L
  cloud_recover.py asked --repo-root D --launch-id L [--uncertain]
  cloud_recover.py successor --repo-root D --launch-id L --repo O/N [--branch B]
  cloud_recover.py message --issue N --place cloud|local [--stopped-at EPOCH] [--pushed-at EPOCH]
                           [--never-pushed] [--push-time-source push|commit]
  cloud_recover.py relaunch-refusal --repo-root D --launch-id L --repo O/N
  cloud_recover.py resume-row --session-state S [--activity-age-seconds N] [--handover]

A successor is composed only for a cloud lane the launch ledger already records as terminal, after
`assess` returned `stopped` on positive stop evidence or a confirmed handover, so no path through this
module helps two builders work one issue.

Stdlib plus plugin imports only. A function that runs a command or reads the environment takes
`env=None` (a mapping; default the process environment), and one that runs a command also takes
`run=None` (default `subprocess.run`). Every function returns a plain dict; an expected failure is a
result with a `reason` token, never a raise. The CLI prints one JSON object and exits 1 on a refusal.
State is `cloud-recover.json`, beside the launch ledger, written only with `store_core.atomic_write`.
"""
import argparse
import datetime
import importlib
import json
import math
import os
import re
import sys
import time
import urllib.parse

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_NAME = "cloud-recover.json"
_SECTIONS = ("asks", "assessed", "superseded")
ASK_OUTCOMES = ("delivered", "uncertain")
SESSION_STATES = ("working", "blocked", "idle", "completed", "review-ready", "failed", "archived",
                  "absent", "unread")
_STOP_STATES = ("failed", "archived", "absent")
_LIVE_STATES = ("working", "blocked")
PUSH_ASK = ("Another builder is about to take this issue over. Push every commit you have now, then post "
            "the handover comment on this issue: run python3 -B <plugin root>/lib/cloud_builder.py handover "
            "--head <your pushed head sha> and post its output as it is. Then stop working on this issue "
            "and end your turn.")
_LOCK_WAIT_SECONDS = 30
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_HANDOVER_SHA_RE = re.compile(r"My pushed head is ([0-9a-f]{40})(?![0-9a-f])")
_TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})")
_PUSH_SOURCES = ("push", "commit")
_PLACES = ("cloud", "local")
_LAUNCHER_STAMPED = ("placeCall", "standingExclusions")
_VERSION_GROUP = r"(?P<%s>\d+\.\d+\.\d+)"


def _sib(name):
    if _LIB_DIR not in sys.path:
        sys.path.insert(0, _LIB_DIR)
    return importlib.import_module(name)


def _refusal(reason):
    return {"ok": False, "reason": reason}


def _env(env):
    return os.environ if env is None else env


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _iso(epoch):
    return datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _epoch(stamp):
    """Epoch seconds of an ISO-8601 timestamp; None when it is missing or not one."""
    if not (isinstance(stamp, str) and _TIMESTAMP_RE.fullmatch(stamp)):
        return None
    try:
        return datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _check_repo(repo):
    if isinstance(repo, str) and _sib("cloud_builder")._REPO_RE.match(repo):
        return None
    return _refusal("repo-invalid")


# ---------------------------------------------------------------- the state file


def _state_path(repo_root, env):
    where = _sib("launch_ledger").ledger_path(repo_root, env)
    if not where["ok"]:
        return None
    return os.path.join(os.path.dirname(where["path"]), STATE_NAME)


def _well_formed(data):
    if not (isinstance(data, dict) and set(data) <= set(_SECTIONS)):
        return False
    if not all(isinstance(v, dict) and all(isinstance(e, dict) for e in v.values()) for v in data.values()):
        return False
    return (all(e.get("outcome") in ASK_OUTCOMES for e in data.get("asks", {}).values())
            and all(e.get("verdict") == "stopped" for e in data.get("assessed", {}).values()))


def _load(repo_root, env):
    """(state path, state dict with every section present) or (refusal, None). A missing file is no
    state; any other file that is not a well-formed state is refused and left alone."""
    path = _state_path(repo_root, env)
    if path is None:
        return _refusal("recover-state-unreadable"), None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return path, {name: {} for name in _SECTIONS}
    except (OSError, ValueError):
        return _refusal("recover-state-unreadable"), None
    if not _well_formed(data):
        return _refusal("recover-state-unreadable"), None
    return path, {name: dict(data.get(name, {})) for name in _SECTIONS}


def _save(path, data):
    try:
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        _sib("store_core").atomic_write(path, json.dumps(data, indent=1, sort_keys=True) + "\n")
    except Exception:
        return False
    return True


def _locked(fn):
    """Run a writer under one per-repository lock beside the state file, so its read-modify-write is not
    interleaved with another writer's. The state is re-read inside the lock by the writer itself."""
    def wrapper(repo_root, *args, env=None, **kwargs):
        env = _env(env)
        path = _state_path(repo_root, env)
        if path is None:
            return _refusal("recover-state-unreadable")
        lock = path + ".lock"
        fl = _sib("file_lock")
        deadline = time.monotonic() + _LOCK_WAIT_SECONDS
        while True:
            try:
                fl.acquire(lock, reclaim_dead_holder=True)
                break
            except fl.LockHeld:
                if time.monotonic() >= deadline:
                    return _refusal("recover-state-busy")
                time.sleep(0.05)
        try:
            return fn(repo_root, *args, env=env, **kwargs)
        finally:
            fl.release(lock)
    wrapper.__name__, wrapper.__doc__ = fn.__name__, fn.__doc__
    return wrapper


@_locked
def _record(repo_root, section, launch_id, entry, *, env=None, keep=None):
    """Write `entry` under `section[launch_id]`. With `keep`, called with the entry already there (or
    None): a non-None answer is returned instead of writing, and the state is left alone."""
    path, data = _load(repo_root, env)
    if data is None:
        return path
    if keep is not None:
        answer = keep(data[section].get(launch_id))
        if answer is not None:
            return answer
    data[section][launch_id] = entry
    if not _save(path, data):
        return _refusal("recover-state-unwritable")
    return {"ok": True}


def superseded_ids(repo_root, env=None):
    """(the launch ids a successor was composed for, whether the state could be read). A missing file
    is readable and empty; an unreadable one is not, and the caller treats every lane as possibly superseded."""
    path, data = _load(repo_root, _env(env))
    if data is None:
        return set(), False
    return set(data["superseded"]), True


# ---------------------------------------------------------------- the lane


def _lane(repo_root, launch_id, env):
    """(folded lane, its reserved record, refusal). Refused when the ledger cannot be read or folded, the
    launch id is not in it, or the lane is not a cloud lane."""
    ll = _sib("launch_ledger")
    got = ll.read(repo_root, env=env)
    if got["state"] not in ("ok", "missing"):
        return None, None, _refusal("launch-ledger-unreadable")
    fold = ll.fold(got["records"])
    if not fold.get("ok"):
        return None, None, _refusal("launch-ledger-unreadable")
    info = fold["launches"].get(launch_id)
    if info is None:
        return None, None, _refusal("lane-unknown")
    if info["place"] != ll.PLACE_CLOUD:
        return None, None, _refusal("lane-not-cloud")
    reserved = next((r for r in got["records"]
                     if r.get("event") == "reserved" and r.get("launchId") == launch_id), None)
    return info, reserved, None


def _lane_start(info):
    stamp = info.get("startedTs", info.get("reservedTs"))
    return stamp if _is_number(stamp) else None


def _comments_since(repo, issue, since, env, run):
    """The issue's comments created at or after `since` (epoch seconds), each with its parsed time; None
    when the read failed. A comment without a readable creation time is not kept."""
    cb = _sib("cloud_builder")
    endpoint = "repos/%s/issues/%d/comments?since=%s" % (repo, issue, _iso(since))
    code, out = cb._gh(run, ["api", "--paginate", endpoint], cb._git_env(env))
    try:
        found = _sib("pr_comment")._parse_paginated_arrays(out) if code == 0 else None
    except (ValueError, TypeError):
        return None
    if found is None or not all(isinstance(c, dict) for c in found):
        return None
    kept = []
    for comment in found:
        created = _epoch(comment.get("created_at"))
        if created is not None and created >= since and isinstance(comment.get("body"), str):
            kept.append((created, comment))
    return kept


def _handover(repo, issue, since, env, run):
    """(the newest handover comment as a dict or None, whether the comments were read)."""
    header = getattr(_sib("cloud_builder"), "HANDOVER_HEADER", None)
    comments = _comments_since(repo, issue, since, env, run) if isinstance(header, str) else None
    if comments is None:
        return None, False
    found = []
    for created, comment in comments:
        body = comment["body"].strip()
        sha = _HANDOVER_SHA_RE.search(body)
        if body.startswith(header) and sha:
            found.append((created, comment, sha.group(1)))
    if not found:
        return None, True
    created, comment, sha = max(found, key=lambda t: t[0])
    return {"commentId": comment.get("id"), "url": comment.get("html_url"), "sha": sha,
            "createdAt": comment["created_at"]}, True


# ---------------------------------------------------------------- what the lane pushed


def _push_time(repo, name, sha, env, run):
    """Epoch seconds GitHub recorded for the push that left `name` at `sha`; None when it cannot be told."""
    cb = _sib("cloud_builder")
    endpoint = "repos/%s/activity?ref=%s&activity_type=push&per_page=30" % (
        repo, urllib.parse.quote("refs/heads/" + name, safe="/"))
    code, out = cb._gh(run, ["api", endpoint], cb._git_env(env))
    try:
        events = json.loads(out) if code == 0 else None
    except ValueError:
        return None
    if not isinstance(events, list):
        return None
    for event in events:
        if not (isinstance(event, dict) and event.get("after") == sha):
            continue
        if isinstance(event.get("ref"), str) and event["ref"] != "refs/heads/" + name:
            continue
        return _epoch(event.get("timestamp"))
    return None


def _branch_entry(repo_root, repo, name, sha, env, run):
    """One kept branch: fetched, checked against the sha `ls-remote` advertised, and timed."""
    cb = _sib("cloud_builder")
    genv = cb._git_env(env)
    entry = {"branch": name, "sha": sha}
    code, _ = cb._git(run, repo_root, ["fetch", "origin", "+refs/heads/%s:refs/remotes/origin/%s" % (name, name)], genv)
    if code != 0:
        entry["reason"] = "branch-fetch-failed"
        return entry
    code, out = cb._git(run, repo_root, ["rev-parse", "refs/remotes/origin/" + name], genv)
    # axis: a branch whose fetched head is not the head the remote advertised was moving during the read — it is never named as the lane's work
    if code != 0 or out.strip() != sha:
        entry["reason"] = "branch-moved-during-read"
        return entry
    code, out = cb._git(run, repo_root, ["log", "-1", "--format=%ct", sha], genv)
    if code != 0 or not re.fullmatch(r"\d+", out.strip()):
        entry["reason"] = "commit-time-unreadable"
        return entry
    committed = int(out.strip())
    pushed = _push_time(repo, name, sha, env, run)
    entry.update({"committedAt": committed, "pushedAt": committed if pushed is None else pushed,
                  "pushTimeSource": "commit" if pushed is None else "push"})
    return entry


def pushed(repo_root, issue, *, repo, env=None, run=None):
    """The work pushed for an issue: every remote branch carrying the issue number as a whole number,
    each with its head, commit time and push time. `newest` is the one branch when there is exactly one
    and it was read cleanly; with several, `ambiguous` and the advisor names the branch."""
    env = _env(env)
    bad = _check_repo(repo)
    if bad:
        return bad
    if not (isinstance(issue, int) and not isinstance(issue, bool) and issue > 0):
        return _refusal("issue-invalid")
    cb = _sib("cloud_builder")
    code, out = cb._git(run, repo_root, ["ls-remote", "--heads", "origin"], cb._git_env(env))
    if code != 0:
        return _refusal("remote-unreadable")
    # axis: the issue number matches as a whole number, so a branch for another issue that contains its digits is not this lane's
    whole = re.compile(r"(?<!\d)%d(?!\d)" % issue)
    kept = {}
    for line in out.splitlines():
        sha, _, ref = line.partition("\t")
        if _SHA_RE.match(sha) and ref.startswith("refs/heads/") and whole.search(ref[len("refs/heads/"):]):
            kept[ref[len("refs/heads/"):]] = sha
    branches = [_branch_entry(repo_root, repo, name, kept[name], env, run) for name in sorted(kept)]
    newest = branches[0] if len(branches) == 1 and "reason" not in branches[0] else None
    return {"ok": True, "issue": issue, "branches": branches, "newest": newest, "ambiguous": len(branches) > 1}


# ---------------------------------------------------------------- may the lane be recovered now


def _check_state(session_state, activity_age_seconds):
    if session_state not in SESSION_STATES:
        return _refusal("session-state-invalid")
    if activity_age_seconds is not None and not _is_number(activity_age_seconds):
        return _refusal("activity-age-invalid")
    return None


def _fresh(session_state, age):
    """A working or blocked session with GitHub activity inside the quiet window."""
    window = _sib("heartbeat").LIVENESS_QUIET_WINDOW_SECONDS
    return session_state in _LIVE_STATES and _is_number(age) and 0 <= age <= window


def assess(repo_root, launch_id, *, session_state, activity_age_seconds=None, repo, env=None, run=None, now=None):
    """Whether the lane may be recovered now. `stopped` is returned only on positive stop evidence (the
    session failed, was archived or is gone) or a handover comment, and is recorded; every other verdict
    leaves the lane alone."""
    env = _env(env)
    bad = _check_repo(repo)
    if bad:
        return bad
    info, _, refused = _lane(repo_root, launch_id, env)
    if refused:
        return refused
    bad = _check_state(session_state, activity_age_seconds)
    if bad:
        return bad
    now = time.time() if now is None else now
    out = {"ok": True, "launchId": launch_id, "issue": info["issue"], "verdict": None, "evidence": None,
           "handover": None, "handoverRead": None, "cloudSessionName": info.get("cloudSessionName"),
           "cloudSessionId": info.get("cloudSessionId"), "configDir": info.get("configDir"),
           "stoppedAt": None}
    if info["terminal"]:
        out["verdict"] = "ended"
        return out
    start = _lane_start(info)
    handover, read = _handover(repo, info["issue"], start, env, run) if start is not None else (None, False)
    out["handover"], out["handoverRead"] = handover, "ok" if read else "failed"
    age = activity_age_seconds
    # axis: positive stop evidence recovers at once, whatever the lane's GitHub activity age says
    if session_state in _STOP_STATES:
        out["verdict"], out["evidence"] = "stopped", "session-" + session_state
    elif handover is not None:
        out["verdict"], out["evidence"] = "stopped", "handover"
    elif session_state == "unread":
        out["verdict"], out["evidence"] = "unresolved", "session-unread"
    # axis: a working or blocked session with recent activity is never recovered while it could still be working
    elif _fresh(session_state, age):
        out["verdict"] = "working"
    elif session_state in _LIVE_STATES and age is None:
        out["verdict"], out["evidence"] = "unresolved", "activity-unknown"
    else:
        path, state = _load(repo_root, env)
        if state is None:
            return path
        out["verdict"] = "awaiting-handover" if launch_id in state["asks"] else "ask-to-push"
    if out["verdict"] != "stopped":
        return out
    if out["evidence"] == "handover":
        out["stoppedAt"] = _epoch(handover["createdAt"])
    elif _is_number(age) and age >= 0:
        out["stoppedAt"] = now - age
    entry = {"verdict": "stopped", "evidence": out["evidence"], "at": _iso(now), "stoppedAt": out["stoppedAt"],
             "handoverSha": handover["sha"] if handover else None}
    wrote = _record(repo_root, "assessed", launch_id, entry, env=env)
    return out if wrote["ok"] else wrote


# ---------------------------------------------------------------- the ask to push


def ask(repo_root, launch_id, *, env=None):
    """The words that ask a stalled builder to push and hand over. Records nothing."""
    env = _env(env)
    info, _, refused = _lane(repo_root, launch_id, env)
    if refused:
        return refused
    path, state = _load(repo_root, env)
    if state is None:
        return path
    # axis: a lane already asked (delivered or unconfirmed) is never asked a second time
    if state["asks"].get(launch_id, {}).get("outcome") in ASK_OUTCOMES:
        return _refusal("already-asked")
    return {"ok": True, "launchId": launch_id, "cloudSessionName": info.get("cloudSessionName"),
            "configDir": info.get("configDir"), "text": PUSH_ASK}


def asked(repo_root, launch_id, *, uncertain=False, env=None):
    """Record that the ask was sent: plain once it was delivered, `uncertain` when delivery could not be
    confirmed. Saying it again changes nothing, and `uncertain` never downgrades a delivered ask."""
    env = _env(env)
    _, _, refused = _lane(repo_root, launch_id, env)
    if refused:
        return refused
    outcome = "uncertain" if uncertain else "delivered"

    def keep(existing):
        if existing is not None and (existing["outcome"] == outcome or existing["outcome"] == "delivered"):
            return {"ok": True, "unchanged": True}
        return None

    wrote = _record(repo_root, "asks", launch_id, {"askedAt": _iso(time.time()), "outcome": outcome},
                    env=env, keep=keep)
    if wrote.get("ok") and "unchanged" not in wrote:
        return {"ok": True, "unchanged": False, "outcome": outcome}
    return wrote


# ---------------------------------------------------------------- the successor


def _premise_of(reserved):
    premise = reserved.get("premise") if isinstance(reserved, dict) else None
    if not isinstance(premise, dict):
        return None
    return {k: v for k, v in premise.items() if k not in _LAUNCHER_STAMPED}


def _base_branch(found, handover_sha, branch):
    """(the branch entry to adopt or None for a never-pushed lane, refusal)."""
    entries = found["branches"]
    if branch is not None:
        entry = next((b for b in entries if b["branch"] == branch), None)
        if entry is None:
            return None, _refusal("branch-not-found")
        if "reason" in entry:
            return None, _refusal(entry["reason"])
        if handover_sha is not None and entry["sha"] != handover_sha:
            return None, _refusal("handover-head-not-pushed")
        return entry, None
    if handover_sha is not None:
        heads = [b for b in entries if b["sha"] == handover_sha and "reason" not in b]
        if not heads:
            return None, _refusal("handover-head-not-pushed")
        return (heads[0], None) if len(heads) == 1 else (None, _refusal("pushed-branch-ambiguous"))
    if found["ambiguous"]:
        return None, _refusal("pushed-branch-ambiguous")
    if found["newest"] is None and entries:
        return None, _refusal("pushed-branch-unreadable")
    return found["newest"], None


def successor(repo_root, launch_id, *, branch=None, repo, env=None, run=None):
    """The premise a successor launch adopts: the lane's own premise with the launcher's stamps removed,
    based on the lane's newest pushed work, or on the original base when it never pushed. Records the
    supersession so the lane is never sent anything again."""
    env = _env(env)
    bad = _check_repo(repo)
    if bad:
        return bad
    info, reserved, refused = _lane(repo_root, launch_id, env)
    if refused:
        return refused
    # axis: a live lane never gets a successor, so two builders never work one issue
    if not info["terminal"]:
        return _refusal("lane-not-ended")
    path, state = _load(repo_root, env)
    if state is None:
        return path
    assessed = state["assessed"].get(launch_id, {})
    # axis: a lane terminalized without an assess that returned stopped never gets a successor
    if assessed.get("verdict") != "stopped":
        return _refusal("lane-not-assessed-stopped")
    premise = _premise_of(reserved)
    if premise is None:
        return _refusal("lane-premise-unreadable")
    found = pushed(repo_root, info["issue"], repo=repo, env=env, run=run)
    if not found["ok"]:
        return found
    entry, refused = _base_branch(found, assessed.get("handoverSha"), branch)
    if refused:
        return refused
    if entry is None:
        premise.pop("adoptsBranch", None)
    else:
        premise["baseCommit"], premise["adoptsBranch"] = entry["sha"], entry["branch"]
    mark = {"at": _iso(time.time()), "branch": entry["branch"] if entry else None,
            "sha": entry["sha"] if entry else None}
    wrote = _record(repo_root, "superseded", launch_id, mark, env=env)
    if not wrote["ok"]:
        return wrote
    return {"ok": True, "launchId": launch_id, "issue": info["issue"], "premise": premise,
            "neverPushed": entry is None, "branch": mark["branch"], "sha": mark["sha"],
            "pushedAt": entry["pushedAt"] if entry else None,
            "pushTimeSource": entry["pushTimeSource"] if entry else None}


# ---------------------------------------------------------------- the board's words


def message(issue, *, place, stopped_at, pushed_at=None, never_pushed=False, push_time_source="push", tz=None):
    """What the board says to the owner about a recovered lane. Pure."""
    if not (isinstance(issue, int) and not isinstance(issue, bool) and issue > 0):
        return _refusal("issue-invalid")
    if place not in _PLACES:
        return _refusal("place-invalid")
    if push_time_source not in _PUSH_SOURCES:
        return _refusal("push-time-source-invalid")
    if (stopped_at is not None and not _is_number(stopped_at)) or (pushed_at is not None and not _is_number(pushed_at)):
        return _refusal("time-invalid")
    if stopped_at is None:
        first = "The cloud builder on #%d stopped." % issue
    else:
        clock = datetime.datetime.fromtimestamp(stopped_at, tz).strftime("%H:%M")
        first = "The cloud builder on #%d stopped at %s." % (issue, clock)
    where = "in a new cloud session" if place == "cloud" else "on your machine"
    if never_pushed:
        return {"ok": True, "text": "%s It never pushed, so I relaunched the build from the beginning %s." % (first, where)}
    text = "%s I recovered the lane from its pushed work %s." % (first, where)
    if stopped_at is not None and pushed_at is not None:
        minutes = max(0, round((stopped_at - pushed_at) / 60))
        since = "push" if push_time_source == "push" else "pushed commit"
        text += " About %d minute%s of work since its last %s is being redone." % (
            minutes, "" if minutes == 1 else "s", since)
    return {"ok": True, "text": text}


# ---------------------------------------------------------------- a refusal at intake


def relaunch_refusal(repo_root, launch_id, *, repo, env=None, run=None):
    """The premise that relaunches a lane the cloud refused for a plugin-version mismatch, carrying the
    version the cloud reported so the routing step sends the build to the owner's machine."""
    env = _env(env)
    bad = _check_repo(repo)
    if bad:
        return bad
    info, reserved, refused = _lane(repo_root, launch_id, env)
    if refused:
        return refused
    if not info["terminal"]:
        return _refusal("lane-not-ended")
    if not (info["terminalKind"] == "outcome" and info["outcome"] == "refusal"):
        return _refusal("lane-not-refusal")
    premise = _premise_of(reserved)
    if premise is None:
        return _refusal("lane-premise-unreadable")
    cb = _sib("cloud_builder")
    pattern = re.escape(cb.REFUSAL_TEXT["plugin-version-mismatch"])
    for slot in ("running", "launched"):
        pattern = pattern.replace(re.escape("{%s}" % slot), _VERSION_GROUP % slot)
    start = _lane_start(info)
    comments = _comments_since(repo, info["issue"], start, env, run) if start is not None else None
    if comments is None:
        return _refusal("comments-unreadable")
    found = []
    for created, comment in comments:
        match = re.search(pattern, comment["body"])
        if comment["body"].strip().startswith(cb.REFUSAL_HEADER) and match:
            found.append((created, match))
    if not found:
        return _refusal("refusal-comment-missing")
    match = max(found, key=lambda t: t[0])[1]
    premise["reportedCloud"] = {"pluginVersion": match.group("running")}
    return {"ok": True, "premise": premise, "cloudVersion": match.group("running"),
            "advisorVersion": match.group("launched")}


# ---------------------------------------------------------------- the showrunner-resume evidence


def resume_row(*, session_state, activity_age_seconds=None, handover=False):
    """The cloud-lane evidence for the showrunner-resume table. Pure."""
    bad = _check_state(session_state, activity_age_seconds)
    if bad:
        return bad
    if _fresh(session_state, activity_age_seconds):
        row = "re-arm"
    elif session_state in _STOP_STATES or handover:
        row = "adopt"
    else:
        row = "unresolved"
    return {"ok": True, "row": row}


# ---------------------------------------------------------------- the command line


def _build_parser():
    parser = argparse.ArgumentParser(prog="cloud_recover.py")
    verbs = parser.add_subparsers(dest="verb", required=True)

    def verb(name, *flags, root=True):
        sub = verbs.add_parser(name)
        if root:
            sub.add_argument("--repo-root", required=True)
        for flag, kind in flags:
            sub.add_argument(flag, required=True, **({"type": kind} if kind else {}))
        return sub

    verb("pushed", ("--repo", None), ("--issue", int))
    sub = verb("assess", ("--launch-id", None), ("--repo", None), ("--session-state", None))
    sub.add_argument("--activity-age-seconds", type=float)
    verb("ask", ("--launch-id", None))
    verb("asked", ("--launch-id", None)).add_argument("--uncertain", action="store_true")
    verb("successor", ("--launch-id", None), ("--repo", None)).add_argument("--branch")
    sub = verb("message", ("--issue", int), ("--place", None), root=False)
    sub.add_argument("--repo-root")
    sub.add_argument("--stopped-at", type=float)
    sub.add_argument("--pushed-at", type=float)
    sub.add_argument("--never-pushed", action="store_true")
    sub.add_argument("--push-time-source", default="push")
    verb("relaunch-refusal", ("--launch-id", None), ("--repo", None))
    sub = verb("resume-row", ("--session-state", None), root=False)
    sub.add_argument("--repo-root")
    sub.add_argument("--activity-age-seconds", type=float)
    sub.add_argument("--handover", action="store_true")
    return parser


def _dispatch(args):
    if args.verb == "pushed":
        return pushed(args.repo_root, args.issue, repo=args.repo)
    if args.verb == "assess":
        return assess(args.repo_root, args.launch_id, session_state=args.session_state,
                      activity_age_seconds=args.activity_age_seconds, repo=args.repo)
    if args.verb == "ask":
        return ask(args.repo_root, args.launch_id)
    if args.verb == "asked":
        return asked(args.repo_root, args.launch_id, uncertain=args.uncertain)
    if args.verb == "successor":
        return successor(args.repo_root, args.launch_id, branch=args.branch, repo=args.repo)
    if args.verb == "message":
        return message(args.issue, place=args.place, stopped_at=args.stopped_at, pushed_at=args.pushed_at,
                       never_pushed=args.never_pushed, push_time_source=args.push_time_source)
    if args.verb == "relaunch-refusal":
        return relaunch_refusal(args.repo_root, args.launch_id, repo=args.repo)
    return resume_row(session_state=args.session_state, activity_age_seconds=args.activity_age_seconds,
                      handover=args.handover)


def main(argv=None):
    try:
        args = _build_parser().parse_args(sys.argv[1:] if argv is None else list(argv))
    except SystemExit as exc:
        sys.stdout.write(json.dumps(_refusal("usage")) + "\n")
        return 0 if exc.code == 0 else 1
    try:
        result = _dispatch(args)
    except Exception:
        result = _refusal("recover-failed")
    sys.stdout.write(json.dumps(result) + "\n")
    return 1 if result.get("ok") is False else 0


if __name__ == "__main__":
    sys.exit(main())
