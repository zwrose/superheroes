"""The advisor's side of a cloud build parked by a lapsed reviewer pass.

  cloud_parked.py notice --repo-root D --repo O/N --pr P
  cloud_parked.py send-back --repo-root D
  cloud_parked.py sent --repo-root D --repo O/N --pr P

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

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_NAME = "cloud-parked.json"
OUTCOMES = ("sent-back", "closed", "owner-let-through")
NOTICE_TEXT = ("#%d is parked. The reviewer pass lapsed mid-build, so its review didn't run. "
               "Renew the pass and I'll send it back for review.")
SEND_BACK_MESSAGE = ("The reviewer pass is renewed. Run this pull request's review now, as your "
                     "review step says, then hand back as usual.")
_ENTRY_KEYS = ("repo", "pr", "parkedOn", "outcome")
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
            isinstance(e, dict) and set(e) == set(_ENTRY_KEYS) and isinstance(e["repo"], str)
            and isinstance(e["pr"], int) and e["outcome"] in (None,) + OUTCOMES
            and cs._date_ok(e["parkedOn"]) for e in entries)):
        return _refusal("parked-state-unreadable"), None
    return path, entries


def _save(path, entries):
    try:
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        _sib("store_core").atomic_write(path, json.dumps(entries, indent=1) + "\n")
    except Exception:
        return False
    return True


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


def _let_through(repo, pr, env, run):
    """True when the owner already let it through: its latest review record names missing reviews, all
    with go-aheads. None when the record could not be read for a reason other than there being none."""
    got = _sib("review_record").read(pr, repo=repo, readers={"list_comments": lambda p, r: _comments(r, p, env, run)})
    if not got.get("ok"):
        return False if got.get("reason") in _NO_RECORD else None
    missing = got.get("missingReviews")
    return bool(missing) and isinstance(missing, list) and all(
        isinstance(m, dict) and m.get("goAhead") is not None for m in missing)


def _lane(repo_root, issues, env):
    """(launchId, folded lane, reason) of the newest cloud lane for the issues; (None, {}, None) when a
    readable ledger has none. `reason` names a ledger that could not be read or folded."""
    ll = _sib("launch_ledger")
    got = ll.read(repo_root, env=env)
    if got["state"] not in ("ok", "missing", "tornTail"):
        return None, {}, "launch-ledger-unreadable"
    fold = ll.fold(got["records"])
    if not fold.get("ok", True):
        return None, {}, "launch-ledger-fold-failed"
    lanes = [(i["reservedIndex"], k, i) for k, i in fold["launches"].items()
             if i["place"] == "cloud" and i["issue"] in issues]
    if not lanes:
        return None, {}, None
    best = max(lanes, key=lambda t: t[0])
    return best[1], best[2], None


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
    if not any(e["repo"] == repo and e["pr"] == pr for e in entries):
        parked_on = _park_day(parks[-1].get("created_at"))
        if parked_on is None:
            return _refusal("park-date-unreadable")
        entries.append({"repo": repo, "pr": pr, "parkedOn": parked_on, "outcome": None})
        if not _save(path, entries):
            return _refusal("parked-state-unwritable")
    return {"ok": True, "kind": "lapsed-pass", "pr": pr, "text": NOTICE_TEXT % pr}


def send_back(repo_root, today=None, *, env=None, run=None):
    """The undecided entries due for their review. A closed or let-through entry is decided here; a due
    one is listed and stays undecided until `sent` records it."""
    env = os.environ if env is None else env
    bad, _, day = _check_args(None, None, today)
    if bad:
        return bad
    path, entries = _load(repo_root, env)
    if entries is None:
        return path
    out = {"ok": True, "sendBack": [], "skipped": [], "unread": [], "notRenewed": [], "noLane": []}
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
        issues = _sib("review_record").closing_issues(pull.get("body"), e["repo"])
        launch_id, lane, ledger_reason = _lane(repo_root, issues, env) if issues else (None, {}, None)
        issue = lane.get("issue") if lane else (issues[0] if issues else None)
        lapses = _lapses(repo_root, env, lane.get("configDir"), lane.get("cloudEnvironment"))
        if not _renewed(e["parkedOn"], lapses, day):
            out["notRenewed"].append(e["pr"])
            continue
        through = _let_through(e["repo"], e["pr"], env, run)
        if through is None:
            out["unread"].append({"pr": e["pr"], "reason": "review-record-read-failed"})
            continue
        if through:
            e["outcome"], changed = "owner-let-through", True
            out["skipped"].append({"pr": e["pr"], "outcome": e["outcome"]})
            continue
        if ledger_reason:
            out["unread"].append({"pr": e["pr"], "reason": ledger_reason})
            continue
        if not lane.get("cloudSessionName"):
            out["noLane"].append({"pr": e["pr"], "issue": issue})
            continue
        out["sendBack"].append({"pr": e["pr"], "repo": e["repo"], "issue": issue, "launchId": launch_id,
                                "cloudSessionName": lane["cloudSessionName"],
                                "configDir": lane.get("configDir"), "message": SEND_BACK_MESSAGE})
    if changed and not _save(path, entries):
        return _refusal("parked-state-unwritable")
    return out


def sent(repo_root, repo, pr, *, env=None):
    """Record one parked PR as sent back, once its message was delivered. Saying it twice changes nothing."""
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
    if entry["outcome"] == "sent-back":
        return {"ok": True, "action": "unchanged"}
    entry["outcome"] = "sent-back"
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
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else list(argv))
    except SystemExit as exc:
        sys.stdout.write(json.dumps(_refusal("usage")) + "\n")
        return 0 if exc.code == 0 else 1
    if args.verb == "notice":
        result = notice(args.repo_root, args.repo, args.pr)
    elif args.verb == "sent":
        result = sent(args.repo_root, args.repo, args.pr)
    else:
        result = send_back(args.repo_root)
    sys.stdout.write(json.dumps(result) + "\n")
    return 1 if result.get("ok") is False else 0


if __name__ == "__main__":
    sys.exit(main())
