"""The advisor's side of a cloud build parked by a lapsed or rejected reviewer pass.

  cloud_parked.py notice --repo-root D --repo O/N --pr P (a park is `lapsed`, or `rejected` when a 401 stopped the review)
  cloud_parked.py send-back --repo-root D [--confirmed] (lists sendBack, adopt and adopting; --confirmed records a renewal)
  cloud_parked.py sent --repo-root D --repo O/N --pr P [--uncertain]

A renewed reviewer pass never reaches a cloud session that is already running, so a renewed park whose
lane started before the renewal is listed under `adopt` (a fresh session takes the pull request over) and
is never messaged; only a lane that started after the renewal gets the send-back message.

Stdlib plus plugin imports only. A function that runs a command or reads the environment takes
`env=None` (a mapping; default the process environment), and one that runs a command also takes
`run=None` (default `subprocess.run`). Every function returns a plain dict; an expected failure is a
result with a `reason` token, never a raise. The CLI prints one JSON object and exits 1 on a refusal.
State is `cloud-parked.json`, beside the launch ledger, written only with `store_core.atomic_write`; so is
`cloud-pass-confirmed.json` beside it, the time `send-back --confirmed` recorded for each account.
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

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_NAME = "cloud-parked.json"
CONFIRMED_NAME = "cloud-pass-confirmed.json"  # {account id: epoch seconds} of the last `send-back --confirmed`
UNCERTAIN = "send-uncertain"  # a send-back whose delivery could not be confirmed; never resent on its own
OUTCOMES = ("sent-back", UNCERTAIN, "closed", "owner-let-through", "adopting", "adopted")
_RESOLVED = ("closed", "owner-let-through", "adopting", "adopted")  # outcomes after which the park needs no renewal advice
NOTICE_TEXT = ("#%d is parked. The reviewer pass lapsed mid-build, so its review didn't run. "
               "Renew the pass and I'll send it back for review.")
REJECTED_NOTICE_TEXT = ("#%d is parked. The reviewer's sign-in was rejected mid-build (a 401), so its review "
                        "didn't run. Renew the sign-in and the pass, and a fresh session will run its review.")
SEND_BACK_MESSAGE = ("The reviewer pass is renewed. Run this pull request's review now, as your "
                     "review step says, then hand back as usual.")
ADOPT_MESSAGE = ("A newer launch takes over this pull request's review: a renewed reviewer pass never reaches "
                 "a running session, so a fresh session adopts your pushed branch. Do not run the review. "
                 "Run your wake check for a newer launch now, with --launch-id %s, and follow your cloud "
                 "reference's steps for superseded: true.")
_ENTRY_KEYS = ("repo", "pr", "parkedOn", "outcome")
_LAUNCH_KEY = "launchId"  # the lane the park came from; absent on an entry written before it was kept
_PARK_KEY = "parkId"  # id of the latest park comment seen; absent on an entry written before it was kept
_CAUSE_KEY = "cause"  # "rejected" when a 401 stopped the review; absent (a lapsed pass) on every other entry
_OPTIONAL_KEYS = (_LAUNCH_KEY, _PARK_KEY, _CAUSE_KEY)
_LOCK_WAIT_SECONDS = 30
_NO_RECORD = ("review-record-missing", "review-record-unreadable")
_TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})")
_401_RE = re.compile(r"(?<!\d)401(?!\d)")


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
            and (_CAUSE_KEY not in e or e[_CAUSE_KEY] == "rejected")
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


def _is_time(value):
    """A finite epoch-seconds number (a bool is not one)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _load_confirmed(repo_root, env):
    """(path of the confirmation file, {account id: epoch seconds}) or a refusal dict. A missing file is
    `{}`; one that is not a JSON object of account ids to finite times is refused and left alone."""
    where = _sib("launch_ledger").ledger_path(repo_root, env)
    if not where["ok"]:
        return _refusal(where["reason"]), None
    path = os.path.join(os.path.dirname(where["path"]), CONFIRMED_NAME)
    try:
        with open(path, encoding="utf-8") as fh:
            known = json.load(fh)
    except FileNotFoundError:
        return path, {}
    except (OSError, ValueError):
        return _refusal("pass-confirmed-unreadable"), None
    if not (isinstance(known, dict) and all(isinstance(k, str) and _is_time(v) for k, v in known.items())):
        return _refusal("pass-confirmed-unreadable"), None
    return path, known


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


def _lane_account(repo_root, env, config_dir=None, account_id=None):
    """The account the lane ran on: the lane's own `account_id` when it carries one, else the account its
    `config_dir` names when that is a non-empty string, else the caller's own. A `config_dir` that is the
    default root is the default account (no override), as the launcher records it. None when it cannot
    be resolved."""
    cs = _sib("cloud_setup")
    cd = _sib("config_dir")
    if isinstance(config_dir, str) and config_dir:
        bare = {k: v for k, v in env.items() if k != cd.CONFIG_DIR_ENV}
        default = cd.resolve(bare, repo_root)
        if default is not None and os.path.normpath(config_dir) == os.path.normpath(default):
            env = bare
        else:
            env = dict(env, **{cd.CONFIG_DIR_ENV: config_dir})
    # axis: the lane's recorded account id decides, whatever config path the advisor runs under — see bite-proof record c8a_wo4.md
    if isinstance(account_id, str) and account_id:
        return account_id
    return cs.launching_account(env=env, cwd=repo_root)


def _lapses(repo_root, env, config_dir=None, environment=None, account_id=None):
    """The lapse date in the setup record of the account the lane ran on (`_lane_account` names it). When
    `environment` is a non-empty string the record must name that environment. None when the account
    cannot be resolved, the latest check failed, or the record is missing, unreadable, for another
    environment or has no date."""
    cs = _sib("cloud_setup")
    account = _lane_account(repo_root, env, config_dir, account_id)
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


def _renewal_time(repo_root, account, confirmed):
    """Epoch seconds of the account's latest renewal: the larger of the modification time of its setup
    record (when the record reads ready) and the time `send-back --confirmed` recorded for it. None when
    neither exists or the account is unresolved."""
    if not account:
        return None
    times = []
    if _sib("cloud_setup").read(repo_root, account, persist_backfill=False)["ready"]:
        try:
            times.append(os.path.getmtime(_sib("cloud_setup").record_path(repo_root, account)))
        except OSError:
            pass
    if _is_time(confirmed.get(account)):
        times.append(confirmed[account])
    return max(times) if times else None


def _rejected_renewed(started, current, renewal, today):
    """A rejected sign-in is renewed when the account's lapse date is valid and not past (it may be the
    same date as before) and its renewal time is later than the lane's start. An unreadable start or no
    renewal time is not a renewal."""
    return (_sib("cloud_setup")._date_ok(current) and _sib("cloud_check")._lapses_ok(current, today)
            and renewal is not None and _is_time(started) and started < renewal)


def _park_cause(body):
    """`lapsed` for a body opening with the lapsed-pass park text, `rejected` for one whose first line is that
    text's first line and which names a 401 as a whole number; None for any other comment."""
    cb = _sib("cloud_builder")
    text = body.strip()
    if text.startswith(cb.REVIEW_LAPSED_TEXT.strip()):
        return "lapsed"
    first = cb.REVIEW_LAPSED_TEXT.splitlines()[0]
    # axis: a rejected sign-in is a park only when it opens the park line and names a whole-number 401
    if text.splitlines()[:1] == [first] and _401_RE.search(text):
        return "rejected"
    return None


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
    def fetch(endpoint):
        code, out = _sib("cloud_builder")._gh(run, ["api", endpoint], env)
        return out if code == 0 else None
    found = _sib("gh_pages").read(fetch, "repos/%s/issues/%d/comments" % (repo, pr))
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
    """Is this PR parked by the lapsed pass or a rejected sign-in? Records it when so (a rejected one with
    `cause: "rejected"`, the newest park deciding the cause); says nothing about any other PR."""
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
    found = [(c, _park_cause(c["body"])) for c in comments if isinstance(c.get("body"), str)]
    found = [(c, cause) for c, cause in found if cause]
    parks = [c for c, _ in found]
    if not parks:
        return {"ok": True, "kind": "not-lapsed-pass", "pr": pr, "text": None}
    rejected = found[-1][1] == "rejected"
    known = [e for e in entries if e["repo"] == repo and e["pr"] == pr]
    parked_on = _park_day(parks[-1].get("created_at"))
    park_id = parks[-1].get("id")
    park_id = park_id if isinstance(park_id, (str, int)) and not isinstance(park_id, bool) else None
    if known:
        seen = known[0].get(_PARK_KEY)
        newer = park_id != seen if (park_id is not None and seen is not None) else (
            bool(parked_on) and parked_on > known[0]["parkedOn"])
    else:
        newer = False
    # axis: a resolved park that is not newer gets no renewal advice — see bite-proof record c8a_wo4.md
    if known and not newer and known[0]["outcome"] in _RESOLVED:
        return {"ok": True, "kind": "park-resolved", "pr": pr, "text": None}
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
        rebind = bool(old) and old in superseded
        if rebind:
            _, was, why = _lane(repo_root, issues, env, old)
            issues = [was["issue"]] if was else issues
        launch_id, _, ledger_reason = (
            _lane(repo_root, issues, env, None if rebind else old,
                  reserved_by=_park_time(parks[-1])) if issues else (None, {}, None))
        if ledger_reason:
            return _refusal(ledger_reason)
        entries[:] = [e for e in entries if e not in known]
        entry = {"repo": repo, "pr": pr, "parkedOn": parked_on, "outcome": None, _LAUNCH_KEY: launch_id,
                 _PARK_KEY: park_id}
        # axis: the cause is stored only for a rejected sign-in, so every lapsed-pass entry keeps its shape
        if rejected:
            entry[_CAUSE_KEY] = "rejected"
        entries.append(entry)
        if not _save(path, entries):
            return _refusal("parked-state-unwritable")
    # axis: a rejected sign-in is told apart from a lapsed pass in the result, with its own renewal words
    if rejected:
        return {"ok": True, "kind": "lapsed-pass", "pr": pr, "cause": "rejected", "text": REJECTED_NOTICE_TEXT % pr}
    return {"ok": True, "kind": "lapsed-pass", "pr": pr, "text": NOTICE_TEXT % pr}


def _adopt_item(e, issue, launch_id, lane, rejected):
    """One entry of the `adopt` or `adopting` list: the lane to supersede, with the notice to post and the
    message to give the old session."""
    return {"pr": e["pr"], "repo": e["repo"], "issue": issue, "launchId": launch_id, _PARK_KEY: e.get(_PARK_KEY),
            "cloudSessionName": lane.get("cloudSessionName"), "configDir": lane.get("configDir"),
            _CAUSE_KEY: "rejected" if rejected else "lapsed",
            "notice": _sib("cloud_builder").superseded_notice_text(launch_id), "message": ADOPT_MESSAGE % launch_id}


@_locked
def send_back(repo_root, today=None, *, confirmed=False, env=None, run=None, now=None):
    """The undecided entries due for their review. A closed or let-through entry is decided here. A due
    entry whose lane started after the account's renewal is listed under `sendBack` and stays undecided
    until `sent` records it. One whose lane started before the renewal (or has no readable start) is listed
    under `adopt` once and becomes `adopting`: a renewed pass never reaches a running session, so a fresh
    session takes it over; later runs list it under `adopting` until a replacement launch has started
    (`adopted`) or the PR closes. An entry whose send could not be confirmed is never listed for sending
    again, but is listed under `uncertain` every time. With `confirmed`, the time `now` (default the
    clock) is first recorded in `cloud-pass-confirmed.json` for the caller's own account: it is the
    renewal time of a renewal that left the lapse date unchanged. A confirmation file that cannot be
    read refuses the whole run, and no confirmation is recorded for an account that cannot be resolved."""
    env = os.environ if env is None else env
    now = time.time() if now is None else now
    bad, _, day = _check_args(None, None, today)
    if bad:
        return bad
    path, entries = _load(repo_root, env)
    if entries is None:
        return path
    confirmed_path, confirmed_at = _load_confirmed(repo_root, env)
    if confirmed_at is None:
        return confirmed_path
    if confirmed:
        account = _sib("cloud_setup").launching_account(env=env, cwd=repo_root)
        if account is None:
            return _refusal("account-unknown")
        confirmed_at[account] = now
        if not _save(confirmed_path, confirmed_at):
            return _refusal("pass-confirmed-unwritable")
    out = {"ok": True, "sendBack": [], "adopt": [], "adopting": [], "skipped": [], "unread": [],
           "notRenewed": [], "noLane": [], "superseded": [],
           "uncertain": [{"pr": e["pr"], "repo": e["repo"], _LAUNCH_KEY: e.get(_LAUNCH_KEY), _PARK_KEY: e.get(_PARK_KEY)}
                         for e in entries if e["outcome"] == UNCERTAIN]}
    changed = False
    for e in (e for e in entries if e["outcome"] in (None, "adopting")):
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
        rejected = e.get(_CAUSE_KEY) == "rejected"
        # axis: an adopting entry is listed once as adopt, then only as adopting until a replacement started or the PR closed
        if e["outcome"] == "adopting":
            if not lane:
                out["unread"].append({"pr": e["pr"], "reason": "lane-unknown"})
            elif _sib("cloud_recover")._replaced(repo_root, launch_id, lane, env):
                e["outcome"], changed = "adopted", True
                out["skipped"].append({"pr": e["pr"], "outcome": e["outcome"]})
            else:
                out["adopting"].append(_adopt_item(e, issue, launch_id, lane, rejected))
            continue
        # axis: a rejected park with no lane to relaunch from is a no-lane PR before any renewal is judged
        if rejected and not lane.get("cloudSessionName"):
            out["noLane"].append({"pr": e["pr"], "issue": issue})
            continue
        lapses = _lapses(repo_root, env, lane.get("configDir"), lane.get("cloudEnvironment"),
                         lane.get("accountId"))
        account = _lane_account(repo_root, env, lane.get("configDir"), lane.get("accountId"))
        renewal = _renewal_time(repo_root, account, confirmed_at)
        started = lane.get("startedTs")
        # axis: a rejected sign-in is renewed only by a renewal after the lane started; a lapsed pass keeps the lapse-date test
        renewed = (_rejected_renewed(started, lapses, renewal, day) if rejected
                   else _renewed(e["parkedOn"], lapses, day))
        if not renewed:
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
        # axis: a lane that started before the renewal (or has no readable start) never gets the message; a fresh session adopts it
        if not _is_time(started) or (renewal is not None and started < renewal):
            out["adopt"].append(_adopt_item(e, issue, launch_id, lane, rejected))
            e["outcome"], changed = "adopting", True
            continue
        out["sendBack"].append({"pr": e["pr"], "repo": e["repo"], "issue": issue, "launchId": launch_id,
                                _PARK_KEY: e.get(_PARK_KEY),
                                "cloudSessionName": lane["cloudSessionName"],
                                "configDir": lane.get("configDir"), "message": SEND_BACK_MESSAGE})
    if changed and not _save(path, entries):
        return _refusal("parked-state-unwritable")
    # axis: a lane superseded while a later entry's GitHub reads ran is not sent to; the last read decides
    late, late_readable = _sib("cloud_recover").superseded_ids(repo_root, env) if out["sendBack"] else (set(), True)
    if not late_readable:
        out["unread"] += [{"pr": c["pr"], "reason": "recover-state-unreadable"} for c in out["sendBack"]]
        out["sendBack"] = []
    out["superseded"] += [{"pr": c["pr"], "launchId": c["launchId"]} for c in out["sendBack"] if c["launchId"] in late]
    out["sendBack"] = [c for c in out["sendBack"] if c["launchId"] not in late]
    return out


@_locked
def sent(repo_root, repo, pr, *, uncertain=False, park_id=None, env=None):
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
    if str(entry.get(_PARK_KEY)) != str(park_id):
        return _refusal("park-changed")
    if entry["outcome"] in ("closed", "owner-let-through", "adopting", "adopted"):
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
            sub.add_argument("--park-id")
        if name == "send-back":
            sub.add_argument("--confirmed", action="store_true")
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else list(argv))
    except SystemExit as exc:
        sys.stdout.write(json.dumps(_refusal("usage")) + "\n")
        return 0 if exc.code == 0 else 1
    if args.verb == "notice":
        result = notice(args.repo_root, args.repo, args.pr)
    elif args.verb == "sent":
        result = sent(args.repo_root, args.repo, args.pr, uncertain=args.uncertain, park_id=args.park_id)
    else:
        result = send_back(args.repo_root, confirmed=args.confirmed)
    sys.stdout.write(json.dumps(result) + "\n")
    return 1 if result.get("ok") is False else 0


if __name__ == "__main__":
    sys.exit(main())
