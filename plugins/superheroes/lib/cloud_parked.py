"""The advisor's side of a cloud build parked by a lapsed reviewer pass.

  cloud_parked.py notice --repo-root D --repo O/N --pr P [--today YYYY-MM-DD]
                          is this PR parked by the lapsed pass? If so, the words for the owner, and
                          the PR is recorded
  cloud_parked.py send-back --repo-root D [--today YYYY-MM-DD]
                          for each recorded PR whose pass is renewed: send it back for its review,
                          unless it closed or the owner already let it through

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
_ENTRY_KEYS = ("repo", "pr", "parkedCommentId", "parkedAt", "lapseSeen", "noticedAt", "outcome")
_CLOSES_RE = re.compile(r"Closes #(\d+)")


def _sib(name):
    if _LIB_DIR not in sys.path:
        sys.path.insert(0, _LIB_DIR)
    return importlib.import_module(name)


def _refusal(reason):
    return {"ok": False, "reason": reason}


def _check_args(repo, pr, today):
    """(refusal or None, pr as int, today as date). Each named argument is checked only when given."""
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
            and (e["lapseSeen"] is None or cs._date_ok(e["lapseSeen"])) for e in entries)):
        return _refusal("parked-state-unreadable"), None
    return path, entries


def _save(path, entries):
    try:
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        _sib("store_core").atomic_write(path, json.dumps(entries, indent=1) + "\n")
    except Exception:
        return False
    return True


def _lapses(repo_root, env):
    """The setup record's lapse date; None when the record is missing, unreadable or has no date."""
    cs = _sib("cloud_setup")
    account = cs.launching_account(env=env, cwd=repo_root)
    record = cs.read(repo_root, account)["record"] if account else None
    lapses = record.get("passLapses") if isinstance(record, dict) else None
    return lapses if cs._date_ok(lapses) else None


def _renewed(seen, current, today):
    """Renewed: the pass now lapses on a date that is not past, and later than the one seen."""
    return (current is not None and _sib("cloud_check")._lapses_ok(current, today)
            and (seen is None or current > seen))


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
    """The owner already let it through: its latest review record names missing reviews, all with go-aheads."""
    got = _sib("review_record").read(pr, repo=repo, readers={"list_comments": lambda p, r: _comments(r, p, env, run)})
    missing = got.get("missingReviews") if got.get("ok") else None
    return bool(missing) and isinstance(missing, list) and all(
        isinstance(m, dict) and m.get("goAhead") is not None for m in missing)


def _lane(repo_root, issue, env):
    """(launchId, folded lane) of the newest cloud lane for the issue; (None, {}) when none."""
    ll = _sib("launch_ledger")
    folded = ll.fold(ll.read(repo_root, env=env)["records"])["launches"]
    lanes = [(i["reservedIndex"], k, i) for k, i in folded.items() if i["place"] == "cloud" and i["issue"] == issue]
    return (max(lanes, key=lambda t: t[0])[1:] if lanes else (None, {}))


def notice(repo_root, repo, pr, today=None, *, env=None, run=None):
    """Is this PR parked by the lapsed pass? Records it when so; says nothing about any other PR."""
    env = os.environ if env is None else env
    bad, pr, day = _check_args(repo, pr, today)
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
        last = parks[-1]
        entries.append({"repo": repo, "pr": pr, "parkedCommentId": last.get("id"),
                        "parkedAt": last.get("created_at"), "lapseSeen": _lapses(repo_root, env),
                        "noticedAt": day.isoformat(), "outcome": None})
        if not _save(path, entries):
            return _refusal("parked-state-unwritable")
    return {"ok": True, "kind": "lapsed-pass", "pr": pr, "text": NOTICE_TEXT % pr}


def send_back(repo_root, today=None, *, env=None, run=None):
    """Decide each undecided entry whose pass is renewed: sent back, closed, or let through."""
    env = os.environ if env is None else env
    bad, _, day = _check_args(None, None, today)
    if bad:
        return bad
    path, entries = _load(repo_root, env)
    if entries is None:
        return path
    current = _lapses(repo_root, env)
    out = {"ok": True, "lapses": current, "sendBack": [], "skipped": [], "unread": [], "notRenewed": []}
    for e in (e for e in entries if e["outcome"] is None):
        if not _renewed(e["lapseSeen"], current, day):
            out["notRenewed"].append(e["pr"])
            continue
        pull = _pull(e["repo"], e["pr"], env, run)
        if pull is None:
            out["unread"].append({"pr": e["pr"], "reason": "pr-read-failed"})
        elif pull["state"] == "closed" or pull.get("merged") is True:
            e["outcome"] = "closed"
        elif _let_through(e["repo"], e["pr"], env, run):
            e["outcome"] = "owner-let-through"
        else:
            e["outcome"] = "sent-back"
            first = (pull.get("body") or "").splitlines()[:1]
            hit = _CLOSES_RE.match(first[0]) if first else None
            issue = int(hit.group(1)) if hit else None
            launch_id, lane = _lane(repo_root, issue, env) if issue else (None, {})
            out["sendBack"].append({"pr": e["pr"], "issue": issue, "launchId": launch_id,
                                    "cloudSessionName": lane.get("cloudSessionName"),
                                    "configDir": lane.get("configDir"), "message": SEND_BACK_MESSAGE})
        if e["outcome"] in ("closed", "owner-let-through"):
            out["skipped"].append({"pr": e["pr"], "outcome": e["outcome"]})
    if (out["sendBack"] or out["skipped"]) and not _save(path, entries):
        return _refusal("parked-state-unwritable")
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cloud_parked.py")
    verbs = parser.add_subparsers(dest="verb", required=True)
    for name in ("notice", "send-back"):
        sub = verbs.add_parser(name)
        sub.add_argument("--repo-root", required=True)
        sub.add_argument("--today")
        if name == "notice":
            sub.add_argument("--repo", required=True)
            sub.add_argument("--pr", required=True)
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else list(argv))
    except SystemExit as exc:
        sys.stdout.write(json.dumps(_refusal("usage")) + "\n")
        return 0 if exc.code == 0 else 1
    if args.verb == "notice":
        result = notice(args.repo_root, args.repo, args.pr, args.today)
    else:
        result = send_back(args.repo_root, args.today)
    sys.stdout.write(json.dumps(result) + "\n")
    return 1 if result.get("ok") is False else 0


if __name__ == "__main__":
    sys.exit(main())
