"""The advisor's recovery of a stopped cloud builder: what it pushed, whether it may be replaced, the ask
to push, the successor's premise, and the board's words.

  cloud_recover.py pushed --repo-root D --repo O/N --issue N
  cloud_recover.py assess --repo-root D --launch-id L --repo O/N --session-state S [--activity-age-seconds N]
  cloud_recover.py ask --repo-root D --launch-id L
  cloud_recover.py asked --repo-root D --launch-id L [--uncertain]
  cloud_recover.py successor --repo-root D --launch-id L --repo O/N [--never-pushed 'what was checked']
  cloud_recover.py relaunch-refusal --repo-root D --launch-id L --repo O/N
  cloud_recover.py message --issue N --place cloud|local [--stopped-at EPOCH] [--pushed-at EPOCH]
                           [--never-pushed] [--push-time-source push|commit]
  cloud_recover.py helper-read --repo O/N --issue N --session-id S [--session-id S ...]

A successor is composed only for a cloud lane the launch ledger records as ended and `assess` recorded as
`stopped` (positive stop evidence: the session failed, was archived or is gone, or the lane's own account
is limited and the lane started before the limit was recorded; or a confirmed handover), so no path through
this module helps two builders work one issue. Every verb checks its inputs through the one `_inputs`.
`assess` also answers `parked` (the issue holds a builder stop or park newer than the lane's last pushed
work; never a recovery step).

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
_PARK_KINDS = ("stop", "park")
_PLACES = ("cloud", "local")
_LAUNCHER_STAMPED = ("placeCall", "standingExclusions", "standDown")
HELPER_READ_FIELDS = ("id", "title", "session_status", "status_bucket", "archived")
_SESSION_ID_RE = re.compile(r"session_[A-Za-z0-9_-]+")


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
    ("session_ids", "session-ids-invalid", lambda v: isinstance(v, (list, tuple)) and len(v) > 0
     and all(isinstance(s, str) and _SESSION_ID_RE.fullmatch(s) for s in v)),
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


def _record(repo_root, section, launch_id, entry, *, env=None, keep=None, assessed=None):
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
        if assessed is not None and data["assessed"].get(launch_id) != assessed:
            return _refusal("lane-not-assessed-stopped")
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


def handover_stopped_ids(repo_root, env=None):
    """(the launch ids `assess` recorded as stopped on a confirmed handover, whether the state could be
    read). A missing file is readable and empty; an unreadable one is not, and the caller treats no lane as
    stopped."""
    path, data = _load(repo_root, _env(env))
    if data is None:
        return set(), False
    return {lid for lid, entry in data["assessed"].items()
            if entry.get("verdict") == "stopped" and entry.get("evidence") == "handover"}, True


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


def _started_later(repo_root, info, env):
    """Whether a later launch for the lane's issue has started."""
    ll = _sib("launch_ledger")
    launches = ll.fold(ll.read(repo_root, env=env)["records"])["launches"].values()
    return any(i["issue"] == info["issue"] and i["reservedIndex"] > info["reservedIndex"] and "startedTs" in i for i in launches)


def _replaced(repo_root, launch_id, info, env):
    """Whether a successor was composed for the lane and a replacement has since started. A mark with no
    started launch behind it is a recovery interrupted before its launch, so the lane stays recoverable."""
    if launch_id not in superseded_ids(repo_root, env)[0]:
        return False
    return _started_later(repo_root, info, env)


def _issue_comments(repo, issue, since, env, run):
    """The issue's comments updated since `since - 1` (every page); None when they could not be read whole."""
    cb = _sib("cloud_builder")
    endpoint = "repos/%s/issues/%d/comments?since=%s" % (repo, issue, _iso(since - 1))
    git_env = cb._git_env(env)

    def fetch(page_endpoint):
        code, out = cb._gh(run, ["api", page_endpoint], git_env)
        return out if code == 0 else None
    comments = _sib("gh_pages").read(fetch, endpoint)
    if comments is None or not all(isinstance(c, dict) for c in comments):
        return None
    return comments


def _newest(comments, since, parse):
    """The newest of `comments` created at or after `since` whose `parse(body)` is truthy, as {"commentId", "url",
    "parsed", "createdAt"}; None when there is none. A comment without a readable creation time or a body
    `parse` accepts is not kept."""
    found = []
    for comment in comments:
        created, parsed = _epoch(comment.get("created_at")), parse(comment.get("body"))
        if created is not None and created >= since and parsed:
            found.append((created, comment, parsed))
    if not found:
        return None
    # same-second ties go to the larger comment id, as the wave watch's lane-terminal reader does
    _, comment, parsed = max(found, key=lambda t: (t[0], t[1].get("id") if type(t[1].get("id")) is int else -1))
    return {"commentId": comment.get("id"), "url": comment.get("html_url"), "parsed": parsed,
            "createdAt": comment["created_at"]}


def _newest_comment(repo, issue, since, env, run, parse):
    """(the newest comment created at or after `since` whose `parse(body)` is truthy, whether the comments were read)."""
    comments = _issue_comments(repo, issue, since, env, run)
    return (None, False) if comments is None else (_newest(comments, since, parse), True)


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
    carries = _sib("wave_watch").carries_issue
    kept = {}
    for line in out.splitlines():
        sha, _, ref = line.partition("\t")
        if _SHA_RE.match(sha) and ref.startswith("refs/heads/") and (carries(ref[len("refs/heads/"):], issue) or ref == "refs/heads/%s" % adopted):
            kept[ref[len("refs/heads/"):]] = sha
    branches = [_branch_entry(repo_root, repo, name, kept[name], env, run) for name in sorted(kept)]
    newest = branches[0] if len(branches) == 1 and "reason" not in branches[0] else None
    return {"ok": True, "issue": issue, "branches": branches, "newest": newest, "ambiguous": len(branches) > 1}


def _latest_outcome(info):
    """The lane's current outcome: the latest reoutcome amendment, else the recorded one."""
    return next((a["value"] for a in reversed(info.get("amendments") or []) if a["kind"] == _sib("launch_ledger").AMENDMENT_REOUTCOME), info.get("outcome"))


def _withdrawn(repo_root, launch_id, out, env):
    """`out`, once any stop authorization for the lane is withdrawn (an unreadable state is not surfaced, as it refuses every successor)."""
    wrote = _record(repo_root, "assessed", launch_id, None, env=env)
    return out if wrote["ok"] or wrote["reason"] == "recover-state-unreadable" else wrote


def _park_reading(repo_root, repo, info, reserved, comments, cutoff, env, run):
    """(the builder stop or park that is the lane's last word, as {"commentId", "url", "kind", "createdAt"} or None;
    "ok" when nothing it needed was left unread, else "failed"). Any doubt reads as None, which leaves today's answers."""
    cb = _sib("cloud_builder")
    # axis: the comments are read whole and from the attempt's own start, or no stop or park is believed
    if comments is None or not _is_number(cutoff):
        return None, "failed"
    # axis: only the newest terminal-family comment of this attempt counts, so a later handover, handback or ask ends a park
    found = _newest(comments, cutoff, cb.terminal_kind)
    if found is None or found["parsed"] not in _PARK_KINDS:
        return None, "ok"
    commented, comment_id = _epoch(found["createdAt"]), found["commentId"]
    tied = any(c.get("created_at") == found["createdAt"] and cb.terminal_kind(c.get("body")) not in _PARK_KINDS + (None,)
               for c in comments)
    if tied or commented is None or not isinstance(comment_id, int) or isinstance(comment_id, bool):
        return None, "failed"
    ww = _sib("wave_watch")
    path = ww._answered_notes_path(repo_root, env, create=False)
    answered, readable = ww._load_answered_notes(path) if path is not None else (set(), False)
    # axis: an answered record that cannot be read answers nothing, and a stop or park already answered is no longer current
    if not readable:
        return None, "failed"
    if comment_id in answered:
        return None, "ok"
    premise = (reserved or {}).get("premise")
    work = pushed(repo_root, info["issue"], repo=repo, adopted=premise.get("adoptsBranch") if isinstance(premise, dict) else None,
                  env=env, run=run)
    # axis: the pushed work is read whole and each branch timed from GitHub's push record, never from a commit time that may predate the push
    if not work["ok"] or any("reason" in b or b.get("pushTimeSource") != "push" or not _is_number(b.get("pushedAt"))
                             for b in work["branches"]):
        return None, "failed"
    # axis: work pushed after the stop or park means the builder went on, so the comment is no longer its last word
    if any(b["pushedAt"] > commented for b in work["branches"]):
        return None, "ok"
    return {"commentId": comment_id, "url": found["url"], "kind": found["parsed"], "createdAt": found["createdAt"]}, "ok"


def _limit_reading(repo_root, info, reserved, start, env, now):
    """The account-limit reading for the lane's own account when it counts as stop evidence, else None: the
    reading is ok and limited, the lane started before the limit was recorded, and the lane's reserved premise
    carries the launcher's `standDown` stamp (an int 1, the rule the launcher's original-session check uses).
    Any doubt is no reading."""
    cfg = info.get("configDir")
    if not (isinstance(cfg, str) and cfg):
        return None
    premise = reserved.get("premise") if isinstance(reserved, dict) else None
    stand_down = premise.get("standDown") if isinstance(premise, dict) else None
    # axis: a lane launched before the stand-down check existed cannot stand down on waking, so the limit is no stop evidence for it and it needs a session read — see bite-proof record i2272_recover
    if not (isinstance(stand_down, int) and not isinstance(stand_down, bool) and stand_down == 1):
        return None
    reading = _sib("cloud_relay").account_limit(repo_root, cfg, env=env, now=now)
    recorded = reading.get("recordedAt") if isinstance(reading, dict) else None
    # axis: a limit counts only while it holds and only for a lane that started before it was recorded, so a lane launched after the limit lifted is never taken for stopped by it — see bite-proof record i2272_recover
    if (isinstance(reading, dict) and reading.get("ok") is True and reading.get("limited") is True
            and _is_number(start) and _is_number(recorded) and start < recorded):
        return reading
    return None


def _reopened_handback(repo_root, info, env):
    """Whether a handed-back lane was sent a fix order after its handback, so the wave watch watches it again."""
    ww = _sib("wave_watch")
    relay_times = ww._fix_order_times(repo_root, env, set())  # an unreadable relay yields {}: only the ledger's openers count
    name = info.get("cloudSessionName")
    return ww._reopen_candidate(info, relay_times.get(name, ()) if isinstance(name, str) and name else ()) is not None


def assess(repo_root, launch_id, *, session_state, activity_age_seconds=None, repo, env=None, run=None, now=None):
    """Whether the lane may be recovered now. `stopped` is returned only on positive stop evidence (the
    session failed, was archived or is gone; or the lane's own account reads limited and the lane started
    before the limit was recorded, evidence `account-limited`, the limit in `limitType`/`limitResetsAt`) or a
    handover comment, and is recorded; every other verdict leaves the lane alone. `parked` (evidence
    `builder-stop` or `builder-park`, the comment in `parkComment`) means the issue holds a builder stop or park
    newer than the lane's last pushed work; it is never a recovery step. `parkRead` is `failed` when a read the
    park needed failed, so a park was not believed for want of it. A handed-back lane a fix order reopened is
    assessed like a live lane."""
    env = _env(env)
    bad = _inputs(repo=repo, launch_id=launch_id, session_state=session_state,
                  activity_age_seconds=activity_age_seconds)
    if bad:
        return _refusal(bad)
    info, reserved, refused = _lane(repo_root, launch_id, env)
    if refused:
        return refused
    now = time.time() if now is None else now
    out = {"ok": True, "launchId": launch_id, "issue": info["issue"], "verdict": None, "evidence": None,
           "handover": None, "handoverRead": None, "cloudSessionName": info.get("cloudSessionName"),
           "cloudSessionId": info.get("cloudSessionId"), "configDir": info.get("configDir"), "stoppedAt": None,
           "parkComment": None, "parkRead": None, "limitType": None, "limitResetsAt": None}
    # axis: a parked or died lane is still recoverable from current stop evidence until a successor is composed for it
    latest = _latest_outcome(info)
    # axis: a handed-back lane stays ended unless a fix order reopened it, and a replaced lane is ended whatever reopened it — see bite-proof record i2272_recover
    open_again = latest in ("park", "died") or (latest == "handback" and _reopened_handback(repo_root, info, env))
    if info["terminal"] and (not open_again or _replaced(repo_root, launch_id, info, env)):
        out["verdict"] = "ended"
        return _withdrawn(repo_root, launch_id, out, env)
    start, age = info.get("startedTs", info.get("reservedTs")), activity_age_seconds
    cutoff = _sib("wave_watch")._note_cutoff(info)  # the watch's attempt start, so both agree on which comments belong to it
    # one request, from the earlier of the handover's start and the attempt's cutoff, serves both reads below
    begins = [t for t in (start, cutoff) if _is_number(t)]
    comments = _issue_comments(repo, info["issue"], min(begins), env, run) if begins else None
    read = _is_number(start) and comments is not None
    found = _newest(comments, start, _sib("cloud_builder").handover_sha) if read else None
    handover = found and {"commentId": found["commentId"], "url": found["url"], "sha": found["parsed"],
                          "createdAt": found["createdAt"]}
    out["handover"], out["handoverRead"] = handover, "ok" if read else "failed"
    fresh = (session_state in _LIVE_STATES and _is_number(age)
             and 0 <= age <= _sib("heartbeat").LIVENESS_QUIET_WINDOW_SECONDS)
    if not fresh:
        out["parkComment"], out["parkRead"] = _park_reading(repo_root, repo, info, reserved, comments, cutoff, env, run)
    # axis: a working or blocked session with recent activity is never recovered while it could still be working, whatever the comments say
    if fresh:
        out["verdict"] = "working"
    # axis: a builder that stopped or parked on a question is not recovered, even when its session is gone
    elif out["parkComment"] is not None:
        out["verdict"], out["evidence"] = "parked", "builder-" + out["parkComment"]["kind"]
    # axis: positive stop evidence recovers at once, whatever the lane's GitHub activity age says
    elif session_state in _STOP_STATES:
        out["verdict"], out["evidence"] = "stopped", "session-" + session_state
    elif handover is not None:
        out["verdict"], out["evidence"] = "stopped", "handover"
    # axis: the account's limit holding is stop evidence for a lane that started before it, but never over a fresh, parked, stopped or handed-over lane — see bite-proof record i2272_recover
    elif (limit := _limit_reading(repo_root, info, reserved, start, env, now)) is not None:
        out["verdict"], out["evidence"] = "stopped", "account-limited"
        out["limitType"], out["limitResetsAt"], out["stoppedAt"] = limit.get("limitType"), limit.get("resetsAt"), limit["recordedAt"]
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
        return _withdrawn(repo_root, launch_id, out, env)
    if out["evidence"] == "handover":
        out["stoppedAt"] = _epoch(handover["createdAt"])
    entry = {"verdict": "stopped", "evidence": out["evidence"], "at": _iso(now), "stoppedAt": out["stoppedAt"],
             "handoverSha": handover["sha"] if handover else None}
    if out["evidence"] == "account-limited":
        entry["limitResetsAt"] = out["limitResetsAt"]
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


def _has_pull_request(repo, name, env, run):
    """Whether a pull request (any state) has the branch as its head on this repository; None when the read
    failed or did not parse as a list."""
    cb = _sib("cloud_builder")
    head = urllib.parse.quote("%s:%s" % (repo.split("/")[0], name), safe=":/")
    code, out = cb._gh(run, ["api", "repos/%s/pulls?state=all&head=%s&per_page=100" % (repo, head)], cb._git_env(env))
    try:
        prs = json.loads(out) if code == 0 else None
    except ValueError:
        return None
    if not isinstance(prs, list) or not all(isinstance(p, dict) for p in prs):
        return None
    return any(not _from_elsewhere(p, repo) for p in prs)


def _from_elsewhere(pull, repo):
    """Whether the pull request's head lives in a repository other than `repo` (a fork)."""
    head = pull.get("head")
    source = head.get("repo") if isinstance(head, dict) else None
    return isinstance(source, dict) and isinstance(source.get("full_name"), str) and source["full_name"] != repo


def _primary(entries, repo, premise, env, run):
    """The lane's own branch among the cleanly read `entries`: the premise's `adoptsBranch` when it is one of
    them, else the one entry that has a pull request on this repository; None when no single entry is."""
    named = [b for b in entries if b["branch"] == premise.get("adoptsBranch")]
    if named:
        return named[0]
    found = [_has_pull_request(repo, b["branch"], env, run) for b in entries]
    # axis: a pull request read that failed or did not parse names no lane branch, and zero or several pull requests name none either — see bite-proof record i2272_recover
    if any(f is None for f in found) or found.count(True) != 1:
        return None
    return entries[found.index(True)]


def _contained(repo_root, entry, primary, env, run):
    """Whether the primary's head contains the entry's head; anything but git's clean yes is no."""
    cb = _sib("cloud_builder")
    code, _ = cb._git(run, repo_root, ["merge-base", "--is-ancestor", entry["sha"], primary["sha"]], cb._git_env(env))
    return code == 0


def _adopted(repo_root, repo, premise, found, handover_sha, env, run):
    """(the pushed branch entry to adopt, or None for a never-pushed lane; the branches passed over; refusal).
    A recorded handover head names the entry; without one, a single cleanly read branch is taken, or the lane's
    own branch when every other branch is already contained in it."""
    entries = found["branches"]
    if handover_sha is not None:
        heads = [b for b in entries if b["sha"] == handover_sha and "reason" not in b]
        if not heads:
            return None, [], _refusal("handover-head-not-pushed")
        return (heads[0], [], None) if len(heads) == 1 else (None, [], _refusal("pushed-branch-ambiguous"))
    if found["ambiguous"]:
        primary = None if any("reason" in b for b in entries) else _primary(entries, repo, premise, env, run)
        if primary is None:
            return None, [], _refusal("pushed-branch-ambiguous")
        others = [b for b in entries if b is not primary]
        # axis: a branch is passed over only when the lane's own branch contains it, so a stray branch with work found nowhere else, or one ahead of the lane's branch, still refuses — see bite-proof record i2272_recover
        if not all(_contained(repo_root, b, primary, env, run) for b in others):
            return None, [], _refusal("pushed-branch-ambiguous")
        return primary, [{"branch": b["branch"], "sha": b["sha"]} for b in others], None
    if found["newest"] is None and entries:
        return None, [], _refusal("pushed-branch-unreadable")
    return found["newest"], [], None


def _own_premise(reserved):
    """(the lane's own premise with the launcher's stamps removed, refusal) from its reserved record."""
    premise = reserved.get("premise") if isinstance(reserved, dict) else None
    if not isinstance(premise, dict):
        return None, _refusal("lane-premise-unreadable")
    return {k: v for k, v in premise.items() if k not in _LAUNCHER_STAMPED}, None


def relaunch_refusal(repo_root, launch_id, *, repo, env=None, run=None):
    """The premise that relaunches a lane that ended as a version-mismatch refusal: its own premise, stamps removed,
    reporting the cloud's version (from the lane's whole refusal comment, posted since it was reserved). Records nothing."""
    env = _env(env)
    bad = _inputs(repo=repo, launch_id=launch_id)
    if bad:
        return _refusal(bad)
    info, reserved, refused = _lane(repo_root, launch_id, env)
    if refused:
        return refused
    if not info["terminal"]:
        return _refusal("lane-not-ended")
    if _latest_outcome(info) != "refusal":
        return _refusal("lane-not-refusal")
    if _started_later(repo_root, info, env):
        return _refusal("lane-replaced")
    premise, refused = _own_premise(reserved)
    if refused:
        return refused
    # The reservation precedes the spawn, so an intake refusal posted before the start receipt still counts;
    # whole seconds, since GitHub stamps comments to the second.
    start = info.get("reservedTs")
    found, read = (_newest_comment(repo, info["issue"], int(start), env, run, _sib("cloud_builder").refusal_versions)
                   if _is_number(start) else (None, False))
    if not read:
        return _refusal("comments-unreadable")
    if found is None:
        return _refusal("refusal-comment-missing")
    running, launched = found["parsed"]
    premise["reportedCloud"] = {"pluginVersion": running}
    return {"ok": True, "launchId": launch_id, "issue": info["issue"], "premise": premise,
            "cloudVersion": running, "advisorVersion": launched}


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
    # axis: an account-limit stop authorization expires when the limit stops holding, so a reset after the assess never relaunches beside a builder that may push again — read before any pushed work is read
    limited_stop = assessed.get("evidence") == "account-limited"
    if limited_stop and _limit_reading(repo_root, info, reserved, info.get("startedTs", info.get("reservedTs")), env, None) is None:
        return _refusal("stop-evidence-expired")
    premise, refused = _own_premise(reserved)
    if refused:
        return refused
    found = pushed(repo_root, info["issue"], repo=repo, adopted=premise.get("adoptsBranch"), env=env, run=run)
    if not found["ok"]:
        return found
    entry, passed_over, refused = _adopted(repo_root, repo, premise, found, assessed.get("handoverSha"), env, run)
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
                # axis: an open pull request is adopted only when linked into the stack at this position, as a cloud builder does not link its own
                sc = _sib("stack_check")
                got = sc.read_membership(pr=prs[0]["number"], repo=repo, expect_stack=premise.get("stack"), run=run)
                if not got["ok"] and got["reason"] != sc.REASON_NOT_LINKED:
                    return _refusal("stack-membership-unreadable")
                if got["ok"] and any(m["number"] == prs[0]["number"] and m["position"] == premise["layerPosition"] for m in got["members"]):
                    premise["adopts"] = prs[0]["number"]
    mark = {"at": _iso(time.time()), "branch": entry and entry["branch"], "sha": entry and entry["sha"]}
    if entry is None:
        mark["neverPushedEvidence"] = never_pushed_evidence
    if passed_over:
        mark["passedOver"] = passed_over
    # axis: a handback recorded during the remote reads above ends the lane's recovery, so the ledger is re-read just before the supersession is written
    again, _, refused = _lane(repo_root, launch_id, env)
    if refused or _latest_outcome(again) not in ("park", "died"):
        return refused or _refusal("lane-not-assessed-stopped")
    # axis: the limit is read a second time after the pushed-work and pull-request reads, so a reset during them never relaunches beside a builder that may push again — see bite-proof record i2272_recover
    if limited_stop and _limit_reading(repo_root, info, reserved, info.get("startedTs", info.get("reservedTs")), env, None) is None:
        return _refusal("stop-evidence-expired")
    wrote = _record(repo_root, "superseded", launch_id, mark, env=env, assessed=assessed)
    if not wrote["ok"]:
        return wrote
    result = {"ok": True, "launchId": launch_id, "issue": info["issue"], "premise": premise,
              "neverPushed": entry is None, "branch": mark["branch"], "sha": mark["sha"],
              "pushedAt": entry and entry["pushedAt"], "pushTimeSource": entry and entry["pushTimeSource"]}
    if passed_over:
        result["passedOver"] = passed_over
    return result


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
        gap = stopped_at - pushed_at
        minutes = round(gap / 60)
        since = "push" if push_time_source == "push" else "pushed commit"
        if gap <= 0:
            text += " No work since its last %s is lost." % since
        elif gap < 60:
            text += " Less than a minute of work since its last %s is being redone." % since
        elif minutes >= 120:
            text += " About %d hours of work since its last %s is being redone." % (round(minutes / 60), since)
        else:
            text += " About %d minute%s of work since its last %s is being redone." % (
                minutes, "" if minutes == 1 else "s", since)
    return {"ok": True, "text": text}


def helper_read(repo, issue, session_ids):
    """The ask for a cloud helper session on the builders' account: read each session and post, on the issue, only
    the fields the takeover check reads. The comment is public, so the prompt names those fields and no others."""
    bad = _inputs(repo=repo, issue=issue, session_ids=session_ids)
    if bad:
        return _refusal(bad)
    # axis: the prompt asks for exactly HELPER_READ_FIELDS and nothing else, as the helper posts on a public issue and must never carry usage or cost data — see bite-proof record i2272_recover
    fields = ", ".join(HELPER_READ_FIELDS[:-1]) + " and " + HELPER_READ_FIELDS[-1]
    prompt = ("Run get_session for each of these session ids: %s. For each one, keep only the fields %s, and "
              "nothing else. Post them as one JSON array in a fenced json block, as one comment on issue #%d of %s. "
              "Change, archive or message no session. Then end your turn."
              % (", ".join(session_ids), fields, issue, repo))
    return {"ok": True, "fields": list(HELPER_READ_FIELDS), "prompt": prompt}


_ROOT, _LAUNCH, _REPO = ("--repo-root", {}), ("--launch-id", {}), ("--repo", {})
_VERBS = {  # verb: (function, required flags, optional flags); each flag is (name, add_argument options)
    "pushed": (pushed, [_ROOT, _REPO, ("--issue", {"type": int})], []),
    "assess": (assess, [_ROOT, _LAUNCH, _REPO, ("--session-state", {})],
               [("--activity-age-seconds", {"type": float})]),
    "ask": (ask, [_ROOT, _LAUNCH], []),
    "asked": (asked, [_ROOT, _LAUNCH], [("--uncertain", {"action": "store_true"})]),
    "successor": (successor, [_ROOT, _LAUNCH, _REPO], [("--never-pushed", {"dest": "never_pushed_evidence"})]),
    "relaunch-refusal": (relaunch_refusal, [_ROOT, _LAUNCH, _REPO], []),
    "helper-read": (helper_read, [_REPO, ("--issue", {"type": int}), ("--session-id", {"action": "append", "dest": "session_ids"})], []),
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
