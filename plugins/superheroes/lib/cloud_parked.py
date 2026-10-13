"""The advisor's side of a cloud build parked by a lapsed reviewer pass.

  cloud_parked.py notice --repo-root D --repo O/N --pr P
  cloud_parked.py send-back --repo-root D
  cloud_parked.py sent --repo-root D --repo O/N --pr P [--uncertain]

Stdlib plus plugin imports only. A function that runs a command or reads the environment takes
`env=None` (a mapping; default the process environment), and one that runs a command also takes
`run=None` (default `subprocess.run`). Every function returns a plain dict; an expected failure is a
result with a `reason` token, never a raise. The CLI prints one JSON object and exits 1 on a refusal.
State is `cloud-parked.json`, beside the launch ledger, written only with `store_core.atomic_write`.
"""
import argparse
import datetime
import importlib
import json
import os
import re
import sys
import time

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_NAME = "cloud-parked.json"
UNCERTAIN = "send-uncertain"  # a send-back whose delivery could not be confirmed; never resent on its own
OUTCOMES = ("sent-back", UNCERTAIN, "closed", "owner-let-through")
NOTICE_TEXT = ("#%d is parked. The reviewer pass lapsed mid-build, so its review didn't run. "
               "Renew the pass and I'll send it back for review.")
SEND_BACK_MESSAGE = ("The reviewer pass is renewed. Run this pull request's review now, as your "
                     "review step says, then hand back as usual.")
_ENTRY_KEYS = ("repo", "pr", "parkedOn", "outcome")
_LAUNCH_KEY = "launchId"  # the lane the park came from; absent on an entry written before it was kept
_PARK_KEY = "parkId"  # id of the latest park comment seen; absent on an entry written before it was kept
_OPTIONAL_KEYS = (_LAUNCH_KEY, _PARK_KEY)
_LOCK_WAIT_SECONDS = 30
_NO_RECORD = ("review-record-missing", "review-record-unreadable")
_TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})")


def _sib(name):
    if _LIB_DIR not in sys.path:
        sys.path.insert(0, _LIB_DIR)
    return importlib.import_module(name)


def _refusal(reason):
    return {"ok": False, "reason": reason}


def _check_args(repo, pr, today, *, need=False):
    """(refusal or None, pr as int, today as date). Each named argument is checked only when given;
    with `need`, a missing repo or pr is refused after the rest."""
    try:
        if today is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", today):
            raise ValueError
        day = datetime.date.today() if today is None else datetime.date.fromisoformat(today)
    except (ValueError, TypeError):
        return _refusal("today-invalid"), None, None
    number = int(pr) if isinstance(pr, str) and re.fullmatch(r"[1-9]\d*", pr) else pr
    if pr is not None and not (isinstance(number, int) and not isinstance(number, bool) and number > 0):
        return _refusal("pr-invalid"), None, None
    if repo is not None and not (isinstance(repo, str) and _sib("cloud_builder")._REPO_RE.match(repo)):
        return _refusal("repo-invalid"), None, None
    if need and (repo is None or pr is None):
        return _refusal("repo-invalid" if repo is None else "pr-invalid"), None, None
    return None, number, day


def _load(repo_root, env):
    """(state path, entries) or a refusal dict. A missing file is no entries; any other file that is
    not a list of well-formed entries is refused and left alone."""
    where = _sib("launch_ledger").ledger_path(repo_root, env)
    if not where["ok"]:
        return _refusal(where["reason"]), None
    path = os.path.join(os.path.dirname(where["path"]), STATE_NAME)
    try:
        with open(path, encoding="utf-8") as fh:
            entries = json.load(fh)
    except FileNotFoundError:
        return path, []
    except (OSError, ValueError):
        return _refusal("parked-state-unreadable"), None
    cs = _sib("cloud_setup")
    if not (isinstance(entries, list) and all(
            isinstance(e, dict) and set(_ENTRY_KEYS) <= set(e) <= set(_ENTRY_KEYS) | set(_OPTIONAL_KEYS)
            and isinstance(e["repo"], str) and isinstance(e["pr"], int) and e["outcome"] in (None,) + OUTCOMES
            and isinstance(e.get(_LAUNCH_KEY), (str, type(None)))
            and isinstance(e.get(_PARK_KEY), (str, int, type(None))) and cs._date_ok(e["parkedOn"])
            for e in entries)):
        return _refusal("parked-state-unreadable"), None
    return path, entries


def _save(path, entries):
    try:
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        _sib("store_core").atomic_write(path, json.dumps(entries, indent=1) + "\n")
    except Exception:
        return False
    return True


def _locked(fn):
    """Run a verb under one per-repository lock beside the state file, so its read-modify-write is not
    interleaved with another verb's. The state is re-read inside the lock by the verb itself."""
    def wrapper(repo_root, *args, env=None, **kwargs):
        env = os.environ if env is None else env
        where = _sib("launch_ledger").ledger_path(repo_root, env)
        if not where["ok"]:
            return _refusal(where["reason"])
        lock = os.path.join(os.path.dirname(where["path"]), STATE_NAME + ".lock")
        fl = _sib("file_lock")
        deadline = time.monotonic() + _LOCK_WAIT_SECONDS
        while True:
            try:
                fl.acquire(lock, reclaim_dead_holder=True)
                break
            except fl.LockHeld:
                if time.monotonic() >= deadline:
                    return _refusal("parked-state-busy")
                time.sleep(0.05)
        try:
            return fn(repo_root, *args, env=env, **kwargs)
        finally:
            fl.release(lock)
    wrapper.__name__, wrapper.__doc__ = fn.__name__, fn.__doc__
    return wrapper


def _lapses(repo_root, env, config_dir=None, environment=None):
    """The lapse date in the setup record of the account the lane ran on: the account its `config_dir`
    names when that is a non-empty string, else the caller's own. A `config_dir` that is the default
    root is the default account (no override), as the launcher records it. When `environment` is a
    non-empty string the record must name that environment. None when the account cannot be resolved
    or the record is missing, unreadable, for another environment or has no date."""
    cs = _sib("cloud_setup")
    cd = _sib("config_dir")
    if isinstance(config_dir, str) and config_dir:
        bare = {k: v for k, v in env.items() if k != cd.CONFIG_DIR_ENV}
        default = cd.resolve(bare, repo_root)
        if default is not None and os.path.normpath(config_dir) == os.path.normpath(default):
            env = bare
        else:
            env = dict(env, **{cd.CONFIG_DIR_ENV: config_dir})
    account = cs.launching_account(env=env, cwd=repo_root)
    if account and _sib("cloud_check").read_failed_check(repo_root, account) is not None:
        return None  # the latest check failed (or its marker is unreadable): the saved date is stale
    record = cs.read(repo_root, account)["record"] if account else None
    if isinstance(record, dict) and isinstance(environment, str) and environment \
            and record.get("environment") != environment:
        return None
    lapses = record.get("passLapses") if isinstance(record, dict) else None
    return lapses if cs._date_ok(lapses) else None


def _renewed(parked_on, current, today):
    """Renewed: the pass now lapses on a date that is not past, and later than the day it was parked."""
    return (_sib("cloud_setup")._date_ok(current) and _sib("cloud_check")._lapses_ok(current, today)
            and current > parked_on)


def _park_day(created_at):
    """The UTC `YYYY-MM-DD` of a comment's `created_at`; None when it is missing or not an ISO timestamp."""
    if not (isinstance(created_at, str) and _TIMESTAMP_RE.fullmatch(created_at)):
        return None
    try:
        stamp = datetime.datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp.astimezone(datetime.timezone.utc).date().isoformat()


def _park_time(comment):
    """Epoch seconds of a park comment already known to carry a readable `created_at`."""
    return datetime.datetime.fromisoformat(comment["created_at"].replace("Z", "+00:00")).timestamp()


def _comments(repo, pr, env, run):
    code, out = _sib("cloud_builder")._gh(run, ["api", "--paginate", "repos/%s/issues/%d/comments" % (repo, pr)], env)
    try:
        found = _sib("pr_comment")._parse_paginated_arrays(out) if code == 0 else None
    except ValueError:
        return None
    return found if found is not None and all(isinstance(c, dict) for c in found) else None


def _pull(repo, pr, env, run):
    code, out = _sib("cloud_builder")._gh(run, ["api", "repos/%s/pulls/%d" % (repo, pr)], env)
    try:
        pull = json.loads(out) if code == 0 else None
    except ValueError:
        return None
    return pull if isinstance(pull, dict) and isinstance(pull.get("state"), str) else None


def _let_through(repo, pr, env, run, head):
    """True when the owner already let it through: its latest review record covers the PR's current `head`,
    covers no missing review or names them, and itself says it is no longer parked (its writer owns that decision). A record
    for an earlier head is no go-ahead. None when the record could not be read for a reason other than there being none."""
    got = _sib("review_record").read(pr, repo=repo, readers={"list_comments": lambda p, r: _comments(r, p, env, run)})
    if not got.get("ok"):
        return False if got.get("reason") in _NO_RECORD else None
    missing, parked = got.get("missingReviews"), got.get("parked")
    if not (isinstance(missing, list) and isinstance(parked, bool)):
        return None
    commit = got.get("finalCommit")
    covers = isinstance(head, str) and isinstance(commit, dict) and commit.get("sha") == head
    return not parked and covers


def _linked_issues(body, repo):
    """The issues the PR body's first line links: those it closes, else any `#N` it names (a non-closing link)."""
    found = _sib("review_record").closing_issues(body, repo)
    if found or not isinstance(body, str):
        return found
    first = body.split("\n", 1)[0]
    return [int(n) for n in dict.fromkeys(re.findall(r"(?<![\w/])#([1-9]\d*)", first))]


def _lane(repo_root, issues, env, launch_id=None, reserved_by=None):
    """(launchId, folded lane, reason) of the cloud lane: the one named by `launch_id` when given (never
    another), else the newest for the issues; (None, {}, None) when a readable ledger has none. `reason`
    names a ledger that could not be read or folded. With `reserved_by` (epoch seconds), a launch
    reserved after it is not the lane."""
    ll = _sib("launch_ledger")
    got = ll.read(repo_root, env=env)
    if got["state"] not in ("ok", "missing", "tornTail"):
        return None, {}, "launch-ledger-unreadable"
    fold = ll.fold(got["records"])
    if not fold.get("ok", True):
        return None, {}, "launch-ledger-fold-failed"
    lanes = [(i["reservedIndex"], k, i) for k, i in fold["launches"].items()
             if i["place"] == ll.PLACE_CLOUD and (k == launch_id if launch_id else i["issue"] in issues)
             and (reserved_by is None or i["reservedTs"] <= reserved_by)]
    if not lanes:
        return None, {}, None
    best = max(lanes, key=lambda t: t[0])
    return best[1], best[2], None


@_locked
def notice(repo_root, repo, pr, today=None, *, env=None, run=None):
    """Is this PR parked by the lapsed pass? Records it when so; says nothing about any other PR."""
    env = os.environ if env is None else env
    bad, pr, _ = _check_args(repo, pr, today, need=True)
    if bad:
        return bad
    path, entries = _load(repo_root, env)
    if entries is None:
        return path
    comments = _comments(repo, pr, env, run)
    if comments is None:
        return _refusal("pr-read-failed")
    lapsed = _sib("cloud_builder").REVIEW_LAPSED_TEXT.strip()
    parks = [c for c in comments if isinstance(c.get("body"), str) and c["body"].strip().startswith(lapsed)]
    if not parks:
        return {"ok": True, "kind": "not-lapsed-pass", "pr": pr, "text": None}
    known = [e for e in entries if e["repo"] == repo and e["pr"] == pr]
    parked_on = _park_day(parks[-1].get("created_at"))
    park_id = parks[-1].get("id")
    park_id = park_id if isinstance(park_id, (str, int)) and not isinstance(park_id, bool) else None
    if known and known[0]["outcome"] in (None, "sent-back", UNCERTAIN, "owner-let-through"):
        seen = known[0].get(_PARK_KEY)
        newer = park_id != seen if (park_id is not None and seen is not None) else (
            bool(parked_on) and parked_on > known[0]["parkedOn"])
    else:
        newer = False
    if not known or newer:
        if parked_on is None:
            return _refusal("park-date-unreadable")
        pull = _pull(repo, pr, env, run)
        if pull is None:
            return _refusal("pr-read-failed")
        issues = _linked_issues(pull.get("body"), repo)
        old = known[0].get(_LAUNCH_KEY) if known else None
        superseded, recover_readable = _sib("cloud_recover").superseded_ids(repo_root, env)
        # axis: an unreadable recovery record refuses before the park id is saved, so a retry can still rebind to the replacement
        if old and not recover_readable:
            return _refusal("recover-state-unreadable")
        launch_id, _, ledger_reason = (
            _lane(repo_root, issues, env,
                  # axis: a park after the original lane was superseded binds to the replacement, not the superseded launch
                  old if old not in superseded else None,
                  reserved_by=_park_time(parks[-1])) if issues else (None, {}, None))
        if ledger_reason:
            return _refusal(ledger_reason)
        entries[:] = [e for e in entries if e not in known]
        entries.append({"repo": repo, "pr": pr, "parkedOn": parked_on, "outcome": None, _LAUNCH_KEY: launch_id,
                        _PARK_KEY: park_id})
        if not _save(path, entries):
            return _refusal("parked-state-unwritable")
    return {"ok": True, "kind": "lapsed-pass", "pr": pr, "text": NOTICE_TEXT % pr}


@_locked
def send_back(repo_root, today=None, *, env=None, run=None):
    """The undecided entries due for their review. A closed or let-through entry is decided here; a due
    one is listed and stays undecided until `sent` records it. An entry whose send could not be confirmed
    is never listed for sending again, but is listed under `uncertain` every time."""
    env = os.environ if env is None else env
    bad, _, day = _check_args(None, None, today)
    if bad:
        return bad
    path, entries = _load(repo_root, env)
    if entries is None:
        return path
    out = {"ok": True, "sendBack": [], "skipped": [], "unread": [], "notRenewed": [], "noLane": [],
           "superseded": [],
           "uncertain": [{"pr": e["pr"], "repo": e["repo"], _LAUNCH_KEY: e.get(_LAUNCH_KEY)}
                         for e in entries if e["outcome"] == UNCERTAIN]}
    changed = False
    for e in (e for e in entries if e["outcome"] is None):
        pull = _pull(e["repo"], e["pr"], env, run)
        if pull is None:
            out["unread"].append({"pr": e["pr"], "reason": "pr-read-failed"})
            continue
        if pull["state"] == "closed" or pull.get("merged") is True:
            e["outcome"], changed = "closed", True
            out["skipped"].append({"pr": e["pr"], "outcome": e["outcome"]})
            continue
        issues = _linked_issues(pull.get("body"), e["repo"])
        launch_id, lane, ledger_reason = (
            _lane(repo_root, issues, env, e[_LAUNCH_KEY]) if e.get(_LAUNCH_KEY) else (None, {}, None))
        if ledger_reason:
            out["unread"].append({"pr": e["pr"], "reason": ledger_reason})
            continue
        issue = lane.get("issue") if lane else (issues[0] if issues else None)
        lapses = _lapses(repo_root, env, lane.get("configDir"), lane.get("cloudEnvironment"))
        if not _renewed(e["parkedOn"], lapses, day):
            out["notRenewed"].append(e["pr"])
            continue
        through = _let_through(e["repo"], e["pr"], env, run, (pull.get("head") or {}).get("sha"))
        if through is None:
            out["unread"].append({"pr": e["pr"], "reason": "review-record-read-failed"})
            continue
        if through:
            e["outcome"], changed = "owner-let-through", True
            out["skipped"].append({"pr": e["pr"], "outcome": e["outcome"]})
            continue
        if not lane.get("cloudSessionName"):
            out["noLane"].append({"pr": e["pr"], "issue": issue})
            continue
        # axis: a lane a successor was composed for is never sent to, and an unreadable record of that is read as "may be superseded"; read last, after this entry's GitHub reads
        superseded, recover_readable = _sib("cloud_recover").superseded_ids(repo_root, env)
        if not recover_readable:
            out["unread"].append({"pr": e["pr"], "reason": "recover-state-unreadable"})
            continue
        if launch_id in superseded:
            out["superseded"].append({"pr": e["pr"], "launchId": launch_id})
            continue
        out["sendBack"].append({"pr": e["pr"], "repo": e["repo"], "issue": issue, "launchId": launch_id,
                                "cloudSessionName": lane["cloudSessionName"],
                                "configDir": lane.get("configDir"), "message": SEND_BACK_MESSAGE})
    # axis: a lane superseded while a later entry's GitHub reads ran is not sent to; the last read decides
    late, late_readable = _sib("cloud_recover").superseded_ids(repo_root, env) if out["sendBack"] else (set(), True)
    if not late_readable:
        out["unread"] += [{"pr": c["pr"], "reason": "recover-state-unreadable"} for c in out["sendBack"]]
        out["sendBack"] = []
    out["superseded"] += [{"pr": c["pr"], "launchId": c["launchId"]} for c in out["sendBack"] if c["launchId"] in late]
    out["sendBack"] = [c for c in out["sendBack"] if c["launchId"] not in late]
    if changed and not _save(path, entries):
        return _refusal("parked-state-unwritable")
    return out


@_locked
def sent(repo_root, repo, pr, *, uncertain=False, env=None):
    """Record one parked PR as sent back, once its message was delivered; with `uncertain`, as sent with
    delivery unconfirmed. Saying it twice changes nothing, and `uncertain` never downgrades a confirmed send."""
    env = os.environ if env is None else env
    bad, pr, _ = _check_args(repo, pr, None, need=True)
    if bad:
        return bad
    path, entries = _load(repo_root, env)
    if entries is None:
        return path
    found = [e for e in entries if e["repo"] == repo and e["pr"] == pr]
    if not found:
        return _refusal("not-parked")
    entry = found[0]
    if entry["outcome"] in ("closed", "owner-let-through"):
        return _refusal("already-decided")
    outcome = UNCERTAIN if uncertain else "sent-back"
    if entry["outcome"] == outcome or (uncertain and entry["outcome"] == "sent-back"):
        return {"ok": True, "action": "unchanged"}
    entry["outcome"] = outcome
    if not _save(path, entries):
        return _refusal("parked-state-unwritable")
    return {"ok": True, "action": "written"}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cloud_parked.py")
    verbs = parser.add_subparsers(dest="verb", required=True)
    for name in ("notice", "send-back", "sent"):
        sub = verbs.add_parser(name)
        sub.add_argument("--repo-root", required=True)
        if name != "send-back":
            sub.add_argument("--repo", required=True)
            sub.add_argument("--pr", required=True)
        if name == "sent":
            sub.add_argument("--uncertain", action="store_true")
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else list(argv))
    except SystemExit as exc:
        sys.stdout.write(json.dumps(_refusal("usage")) + "\n")
        return 0 if exc.code == 0 else 1
    if args.verb == "notice":
        result = notice(args.repo_root, args.repo, args.pr)
    elif args.verb == "sent":
        result = sent(args.repo_root, args.repo, args.pr, uncertain=args.uncertain)
    else:
        result = send_back(args.repo_root)
    sys.stdout.write(json.dumps(result) + "\n")
    return 1 if result.get("ok") is False else 0


if __name__ == "__main__":
    sys.exit(main())
