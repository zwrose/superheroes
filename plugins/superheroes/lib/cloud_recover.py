"""The advisor's recovery of a stopped cloud builder: what it pushed, whether it may be replaced, the ask
to push, the successor's premise, and the board's words.

  cloud_recover.py pushed --repo-root D --repo O/N --issue N
  cloud_recover.py assess --repo-root D --launch-id L --repo O/N --session-state S [--activity-age-seconds N]
  cloud_recover.py ask --repo-root D --launch-id L
  cloud_recover.py asked --repo-root D --launch-id L [--uncertain]
  cloud_recover.py successor --repo-root D --launch-id L --repo O/N [--never-pushed 'what was checked']
  cloud_recover.py message --issue N --place cloud|local [--stopped-at EPOCH] [--pushed-at EPOCH]
                           [--never-pushed] [--push-time-source push|commit]

A successor is composed only for a cloud lane the launch ledger records as ended and `assess` recorded as
`stopped` (positive stop evidence or a confirmed handover), so no path through this module helps two
builders work one issue. Every verb checks its inputs through the one `_inputs`.

Stdlib plus plugin imports only. A function that reads the environment takes `env=None` (a mapping; default
the process environment), and one that runs a command also takes `run=None` (default `subprocess.run`).
Every function returns a plain dict; an expected failure is a result with a `reason` token, never a raise.
The CLI prints one JSON object and exits 1 on a refusal. State is `cloud-recover.json`, beside the launch
ledger, written only with `store_core.atomic_write`.
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
            "--head <your pushed head sha> and post the comment field of its output, as it is. Then stop working on this issue "
            "and end your turn.")
_LOCK_WAIT_SECONDS = 30
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})")
_PUSH_SOURCES = ("push", "commit")
_PLACES = ("cloud", "local")
_LAUNCHER_STAMPED = ("placeCall", "standingExclusions")


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


_INPUT_CHECKS = (  # the order in which the first refusal is chosen
    ("repo", "repo-invalid", lambda v: isinstance(v, str) and _sib("cloud_builder")._REPO_RE.match(v)),
    ("issue", "issue-invalid", lambda v: isinstance(v, int) and not isinstance(v, bool) and v > 0),
    ("launch_id", "launch-id-invalid", lambda v: isinstance(v, str) and v != ""),
    ("session_state", "session-state-invalid", lambda v: v in SESSION_STATES),
    ("activity_age_seconds", "activity-age-invalid", lambda v: v is None or _is_number(v)),
    ("place", "place-invalid", lambda v: v in _PLACES),
    ("stopped_at", "time-invalid", lambda v: v is None or _is_number(v)),
    ("pushed_at", "time-invalid", lambda v: v is None or _is_number(v)),
    ("push_time_source", "push-time-source-invalid", lambda v: v in _PUSH_SOURCES),
    ("never_pushed_evidence", "never-pushed-evidence-invalid", lambda v: v is None or (isinstance(v, str) and v.strip() != "")),
)


def _inputs(**given):
    """The first refusal token for the arguments handed in (only those), or None when all are sound."""
    # axis: every verb's inputs are judged here, and only the arguments it hands over, so no verb acts on one it never checked
    for name, token, sound in _INPUT_CHECKS:
        if name in given and not sound(given[name]):
            return token
    return None


def _state_path(repo_root, env):
    where = _sib("launch_ledger").ledger_path(repo_root, env)
    return os.path.join(os.path.dirname(where["path"]), STATE_NAME) if where["ok"] else None


def _well_formed(data):
    if not (isinstance(data, dict) and set(data) <= set(_SECTIONS)):
        return False
    if not all(isinstance(v, dict) and all(isinstance(e, dict) for e in v.values()) for v in data.values()):
        return False
    return (all(e.get("outcome") in ASK_OUTCOMES for e in data.get("asks", {}).values())
            and all(e.get("verdict") == "stopped" for e in data.get("assessed", {}).values()))


def _load(repo_root, env):
    """(state path, state with every section present) or (refusal, None). A missing file is no state; any
    other file that is not well formed is refused and left alone."""
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


def _record(repo_root, section, launch_id, entry, *, env=None, keep=None):
    """Write `entry` under `section[launch_id]`, under one per-repository lock beside the state file so the
    read-modify-write is not interleaved with another writer's. With `keep`, called with the entry already
    there (or None): a non-None answer is returned instead of writing, and the state is left alone."""
    env = _env(env)
    path = _state_path(repo_root, env)
    if path is None:
        return _refusal("recover-state-unreadable")
    lock, fl = path + ".lock", _sib("file_lock")
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
        path, data = _load(repo_root, env)
        if data is None:
            return path
        answer = keep(data[section].get(launch_id)) if keep is not None else None
        if answer is not None:
            return answer
        if entry is None:
            if launch_id not in data[section]:
                return {"ok": True}
            del data[section][launch_id]
        else:
            data[section][launch_id] = entry
        return {"ok": True} if _save(path, data) else _refusal("recover-state-unwritable")
    finally:
        fl.release(lock)


def superseded_ids(repo_root, env=None):
    """(the launch ids a successor was composed for, whether the state could be read). A missing file
    is readable and empty; an unreadable one is not, and the caller treats every lane as possibly superseded."""
    path, data = _load(repo_root, _env(env))
    return (set(), False) if data is None else (set(data["superseded"]), True)


def _lane(repo_root, launch_id, env):
    """(folded lane, its reserved record, refusal). Refused when the ledger cannot be read or folded, the
    launch id is not in it, or the lane is not a cloud lane."""
    ll = _sib("launch_ledger")
    got = ll.read(repo_root, env=env)
    fold = ll.fold(got["records"]) if got["state"] in ("ok", "missing") else {}
    if not fold.get("ok"):
        return None, None, _refusal("launch-ledger-unreadable")
    info = fold["launches"].get(launch_id)
    if info is None:
        return None, None, _refusal("lane-unknown")
    if info["place"] != ll.PLACE_CLOUD:
        return None, None, _refusal("lane-not-cloud")
    reserved = next((r for r in got["records"] if r.get("event") == "reserved" and r.get("launchId") == launch_id), None)
    return info, reserved, None


def _handover(repo, issue, since, env, run):
    """(the newest handover comment created at or after `since` as a dict or None, whether the comments
    were read). A comment without a readable creation time or a whole handover body is not kept."""
    cb = _sib("cloud_builder")
    endpoint = "repos/%s/issues/%d/comments?since=%s" % (repo, issue, _iso(since))
    code, out = cb._gh(run, ["api", "--paginate", endpoint], cb._git_env(env))
    try:
        comments = _sib("pr_comment")._parse_paginated_arrays(out) if code == 0 else None
    except (ValueError, TypeError):
        comments = None
    if comments is None or not all(isinstance(c, dict) for c in comments):
        return None, False
    found = []
    for comment in comments:
        created, body = _epoch(comment.get("created_at")), comment.get("body")
        sha = cb.handover_sha(body)
        if created is not None and created >= since and sha:
            found.append((created, comment, sha))
    if not found:
        return None, True
    _, comment, sha = max(found, key=lambda t: t[0])
    return {"commentId": comment.get("id"), "url": comment.get("html_url"), "sha": sha,
            "createdAt": comment["created_at"]}, True


def _push_time(repo, name, sha, env, run):
    """Epoch seconds GitHub recorded for the push that left `name` at `sha`; None when it cannot be told."""
    cb = _sib("cloud_builder")
    ref = "refs/heads/" + name
    endpoint = "repos/%s/activity?ref=%s&activity_type=push&per_page=30" % (repo, urllib.parse.quote(ref, safe="/"))
    code, out = cb._gh(run, ["api", endpoint], cb._git_env(env))
    try:
        events = json.loads(out) if code == 0 else None
    except ValueError:
        return None
    if not isinstance(events, list):
        return None
    return next((_epoch(e.get("timestamp")) for e in events if isinstance(e, dict) and e.get("after") == sha
                 and (not isinstance(e.get("ref"), str) or e["ref"] == ref)), None)


def _branch_entry(repo_root, repo, name, sha, env, run):
    """One kept branch: fetched, checked against the sha `ls-remote` advertised, and timed."""
    cb = _sib("cloud_builder")
    genv = cb._git_env(env)
    entry = {"branch": name, "sha": sha}
    code, _ = cb._git(run, repo_root, ["fetch", "origin", "+refs/heads/%s:refs/remotes/origin/%s" % (name, name)], genv)
    if code != 0:
        return dict(entry, reason="branch-fetch-failed")
    code, out = cb._git(run, repo_root, ["rev-parse", "refs/remotes/origin/" + name], genv)
    # axis: a branch whose fetched head is not the head the remote advertised was moving during the read — it is never named as the lane's work
    if code != 0 or out.strip() != sha:
        return dict(entry, reason="branch-moved-during-read")
    code, out = cb._git(run, repo_root, ["log", "-1", "--format=%ct", sha], genv)
    if code != 0 or not re.fullmatch(r"\d+", out.strip()):
        return dict(entry, reason="commit-time-unreadable")
    committed, pushed_at = int(out.strip()), _push_time(repo, name, sha, env, run)
    return dict(entry, committedAt=committed, pushedAt=committed if pushed_at is None else pushed_at,
                pushTimeSource="commit" if pushed_at is None else "push")


def pushed(repo_root, issue, *, repo, adopted=None, env=None, run=None):
    """The work pushed for an issue: every remote branch carrying the issue number as a whole number,
    each with its head, commit time and push time. `newest` is the one branch when there is exactly one
    and it was read cleanly; with several, `ambiguous`. The lane's `adopted` branch is kept whatever its name."""
    env = _env(env)
    bad = _inputs(repo=repo, issue=issue)
    if bad:
        return _refusal(bad)
    cb = _sib("cloud_builder")
    code, out = cb._git(run, repo_root, ["ls-remote", "--heads", "origin"], cb._git_env(env))
    if code != 0:
        return _refusal("remote-unreadable")
    # axis: the issue number matches as a whole number, so a branch for another issue that contains its digits is not this lane's
    whole = re.compile(r"(?<!\d)%d(?!\d)" % issue)
    kept = {}
    for line in out.splitlines():
        sha, _, ref = line.partition("\t")
        if _SHA_RE.match(sha) and ref.startswith("refs/heads/") and (whole.search(ref[len("refs/heads/"):]) or ref == "refs/heads/%s" % adopted):
            kept[ref[len("refs/heads/"):]] = sha
    branches = [_branch_entry(repo_root, repo, name, kept[name], env, run) for name in sorted(kept)]
    newest = branches[0] if len(branches) == 1 and "reason" not in branches[0] else None
    return {"ok": True, "issue": issue, "branches": branches, "newest": newest, "ambiguous": len(branches) > 1}


def assess(repo_root, launch_id, *, session_state, activity_age_seconds=None, repo, env=None, run=None, now=None):
    """Whether the lane may be recovered now. `stopped` is returned only on positive stop evidence (the
    session failed, was archived or is gone) or a handover comment, and is recorded; every other verdict
    leaves the lane alone."""
    env = _env(env)
    bad = _inputs(repo=repo, launch_id=launch_id, session_state=session_state,
                  activity_age_seconds=activity_age_seconds)
    if bad:
        return _refusal(bad)
    info, _, refused = _lane(repo_root, launch_id, env)
    if refused:
        return refused
    now = time.time() if now is None else now
    out = {"ok": True, "launchId": launch_id, "issue": info["issue"], "verdict": None, "evidence": None,
           "handover": None, "handoverRead": None, "cloudSessionName": info.get("cloudSessionName"),
           "cloudSessionId": info.get("cloudSessionId"), "configDir": info.get("configDir"), "stoppedAt": None}
    # axis: a parked or died lane is still recoverable from current stop evidence until a successor is composed for it
    if info["terminal"] and (info.get("outcome") not in ("park", "died") or launch_id in superseded_ids(repo_root, env)[0]):
        out["verdict"] = "ended"
        return out
    start, age = info.get("startedTs", info.get("reservedTs")), activity_age_seconds
    handover, read = _handover(repo, info["issue"], start, env, run) if _is_number(start) else (None, False)
    out["handover"], out["handoverRead"] = handover, "ok" if read else "failed"
    fresh = (session_state in _LIVE_STATES and _is_number(age)
             and 0 <= age <= _sib("heartbeat").LIVENESS_QUIET_WINDOW_SECONDS)
    # axis: positive stop evidence recovers at once, whatever the lane's GitHub activity age says
    if session_state in _STOP_STATES:
        out["verdict"], out["evidence"] = "stopped", "session-" + session_state
    # axis: a working or blocked session with recent activity is never recovered while it could still be working, whatever an earlier handover says
    elif fresh:
        out["verdict"] = "working"
    elif handover is not None:
        out["verdict"], out["evidence"] = "stopped", "handover"
    elif session_state == "unread":
        out["verdict"], out["evidence"] = "unresolved", "session-unread"
    elif session_state in _LIVE_STATES and age is None:
        out["verdict"], out["evidence"] = "unresolved", "activity-unknown"
    else:
        path, state = _load(repo_root, env)
        if state is None:
            return path
        out["verdict"] = "awaiting-handover" if launch_id in state["asks"] else "ask-to-push"
    if out["verdict"] != "stopped":
        # axis: a newer non-stopped reading withdraws an earlier stop authorization
        wrote = _record(repo_root, "assessed", launch_id, None, env=env)
        # an unreadable state also refuses every successor, so only another failure to withdraw it is surfaced
        return out if wrote["ok"] or wrote["reason"] == "recover-state-unreadable" else wrote
    if out["evidence"] == "handover":
        out["stoppedAt"] = _epoch(handover["createdAt"])
    entry = {"verdict": "stopped", "evidence": out["evidence"], "at": _iso(now), "stoppedAt": out["stoppedAt"],
             "handoverSha": handover["sha"] if handover else None}
    wrote = _record(repo_root, "assessed", launch_id, entry, env=env)
    return out if wrote["ok"] else wrote


def ask(repo_root, launch_id, *, env=None):
    """The words that ask a stalled builder to push and hand over. Records nothing."""
    env = _env(env)
    bad = _inputs(launch_id=launch_id)
    if bad:
        return _refusal(bad)
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
    bad = _inputs(launch_id=launch_id)
    if bad:
        return _refusal(bad)
    _, _, refused = _lane(repo_root, launch_id, env)
    if refused:
        return refused
    outcome = "uncertain" if uncertain else "delivered"

    def keep(existing):
        same = existing is not None and (existing["outcome"] == outcome or existing["outcome"] == "delivered")
        return {"ok": True, "unchanged": True} if same else None

    wrote = _record(repo_root, "asks", launch_id, {"askedAt": _iso(time.time()), "outcome": outcome},
                    env=env, keep=keep)
    if wrote.get("ok") and "unchanged" not in wrote:
        return {"ok": True, "unchanged": False, "outcome": outcome}
    return wrote


def _adopted(found, handover_sha):
    """(the pushed branch entry to adopt, or None for a never-pushed lane; refusal). A recorded handover
    head names the entry; without one, only a single cleanly read branch is taken."""
    entries = found["branches"]
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


def successor(repo_root, launch_id, *, repo, never_pushed_evidence=None, env=None, run=None):
    """The premise a successor launch adopts: the lane's own premise with the launcher's stamps removed and
    its `baseCommit` kept, carrying the lane's pushed work as `adoptsBranch` and `adoptsHead` (neither, when
    it never pushed, which needs `never_pushed_evidence`, a line naming what was checked). Records the
    supersession so the lane is never sent anything again."""
    env = _env(env)
    bad = _inputs(repo=repo, launch_id=launch_id, never_pushed_evidence=never_pushed_evidence)
    if bad:
        return _refusal(bad)
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
    premise = reserved.get("premise") if isinstance(reserved, dict) else None
    if not isinstance(premise, dict):
        return _refusal("lane-premise-unreadable")
    premise = {k: v for k, v in premise.items() if k not in _LAUNCHER_STAMPED}
    found = pushed(repo_root, info["issue"], repo=repo, adopted=premise.get("adoptsBranch"), env=env, run=run)
    if not found["ok"]:
        return found
    entry, refused = _adopted(found, assessed.get("handoverSha"))
    if refused:
        return refused
    if entry is None:
        if never_pushed_evidence is None:
            # axis: absence of a matching branch is not proof of no pushed work, as a branch whose name lacks the issue number is not seen
            return dict(_refusal("pushed-work-unknown"), note="a branch whose name does not carry the issue number is not seen; check the remote's branches and the issue's pull requests, then pass --never-pushed <what was checked>")
        premise.pop("adoptsBranch", None)
        premise.pop("adoptsHead", None)
    else:
        premise["adoptsBranch"], premise["adoptsHead"] = entry["branch"], entry["sha"]
        if premise.get("layerPosition") not in (None, 1) and "adopts" not in premise:
            # axis: a stack layer whose pull request now holds its position adopts that pull request, else the stack gate refuses the occupied position
            cb = _sib("cloud_builder")
            head = urllib.parse.quote("%s:%s" % (repo.split("/")[0], entry["branch"]), safe="")
            code, out = cb._gh(run, ["api", "repos/%s/pulls?head=%s&state=open" % (repo, head)], cb._git_env(env))
            try:
                prs = json.loads(out) if code == 0 else None
            except ValueError:
                prs = None
            if not isinstance(prs, list):
                return _refusal("open-pr-unreadable")
            if len(prs) == 1 and isinstance(prs[0], dict) and isinstance(prs[0].get("number"), int):
                premise["adopts"] = prs[0]["number"]
    mark = {"at": _iso(time.time()), "branch": entry and entry["branch"], "sha": entry and entry["sha"]}
    if entry is None:
        mark["neverPushedEvidence"] = never_pushed_evidence
    wrote = _record(repo_root, "superseded", launch_id, mark, env=env)
    if not wrote["ok"]:
        return wrote
    return {"ok": True, "launchId": launch_id, "issue": info["issue"], "premise": premise,
            "neverPushed": entry is None, "branch": mark["branch"], "sha": mark["sha"],
            "pushedAt": entry and entry["pushedAt"], "pushTimeSource": entry and entry["pushTimeSource"]}


def message(issue, *, place, stopped_at, pushed_at=None, never_pushed=False, push_time_source="push", tz=None):
    """What the board says to the owner about a recovered lane. Pure."""
    bad = _inputs(issue=issue, place=place, stopped_at=stopped_at, pushed_at=pushed_at,
                  push_time_source=push_time_source)
    if bad:
        return _refusal(bad)
    first = "The cloud builder on #%d stopped" % issue
    if stopped_at is not None:
        first += " at " + datetime.datetime.fromtimestamp(stopped_at, tz).strftime("%H:%M")
    first += "."
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


_ROOT, _LAUNCH, _REPO = ("--repo-root", {}), ("--launch-id", {}), ("--repo", {})
_VERBS = {  # verb: (function, required flags, optional flags); each flag is (name, add_argument options)
    "pushed": (pushed, [_ROOT, _REPO, ("--issue", {"type": int})], []),
    "assess": (assess, [_ROOT, _LAUNCH, _REPO, ("--session-state", {})],
               [("--activity-age-seconds", {"type": float})]),
    "ask": (ask, [_ROOT, _LAUNCH], []),
    "asked": (asked, [_ROOT, _LAUNCH], [("--uncertain", {"action": "store_true"})]),
    "successor": (successor, [_ROOT, _LAUNCH, _REPO], [("--never-pushed", {"dest": "never_pushed_evidence"})]),
    "message": (message, [("--issue", {"type": int}), ("--place", {})],
                [("--repo-root", {}), ("--stopped-at", {"type": float}), ("--pushed-at", {"type": float}),
                 ("--never-pushed", {"action": "store_true"}), ("--push-time-source", {"default": "push"})]),
}


def _build_parser():
    parser = argparse.ArgumentParser(prog="cloud_recover.py")
    verbs = parser.add_subparsers(dest="verb", required=True)
    for name, (_, required, optional) in _VERBS.items():
        sub = verbs.add_parser(name)
        for flag, options in required:
            sub.add_argument(flag, required=True, **options)
        for flag, options in optional:
            sub.add_argument(flag, **options)
    return parser


def main(argv=None):
    try:
        args = _build_parser().parse_args(sys.argv[1:] if argv is None else list(argv))
    except SystemExit as exc:
        sys.stdout.write(json.dumps(_refusal("usage")) + "\n")
        return 0 if exc.code == 0 else 1
    try:
        given = {k: v for k, v in vars(args).items() if k != "verb"}
        if args.verb == "message":
            given.pop("repo_root")  # accepted and ignored: the board's words read no repository
        result = _VERBS[args.verb][0](**given)
    except Exception:
        result = _refusal("recover-failed")
    sys.stdout.write(json.dumps(result) + "\n")
    return 1 if result.get("ok") is False else 0


if __name__ == "__main__":
    sys.exit(main())
