"""The advisor's cleanup after a cloud lane ends: the archive request to its builder and the PR's branch.

  cloud_cleanup.py plan   --repo-root D --repo O/N --pr P [--launch-id ID]
  cloud_cleanup.py record --repo-root D --repo O/N --pr P --msg-id ID --outcome pending|delivered|uncertain|failed [--launch-id ID]
  cloud_cleanup.py branch --repo-root D --repo O/N --pr P [--launch-id ID]

A plan whose request is already `delivered` carries `archiveText: null` and `alreadyDelivered: true`: the
caller sends nothing, and goes on to `branch`. The plan's launch id is given as `--launch-id` to `record`
and `branch`, so all three act on the one lane. The caller records `pending` before it sends; a later
`delivered`, `uncertain` or `failed` for the same msg id replaces it. A `pending` or `uncertain` request
found on resume is never sent a second time on its own.

Stdlib plus plugin imports only. A function that runs a command or reads the environment takes
`env=None` (a mapping; default the process environment), and one that runs a command also takes
`run=None` (default `subprocess.run`). Every function returns a plain dict; an expected failure is a
result with a `reason` token, never a raise. The CLI prints one JSON object and exits 1 on a refusal.
State is `cloud-cleanup.json`, beside the launch ledger, written only with `store_core.atomic_write`.

The cleanup acts only on a cloud lane whose PR is merged or closed, bound unambiguously to that PR,
and never deletes a ref that is not exactly the PR's recorded head, that another open PR uses as head
or base, or that is the default branch. An open PR gets nothing: no message, no deletion, no receipt.
The branch is deleted through the same `gh api` channel every check used
(`DELETE repos/<owner>/<name>/git/refs/heads/<branch>`), so the delete reaches exactly the repository the
checks read, with the credential the reads already proved; no git command runs. The branch's sha is read
again right before the delete and the delete is skipped if it moved. The REST delete has no expected-sha
condition, so a push that lands between that last read and the delete is not caught; that window is accepted,
because the pull request is already merged or closed and its builder is finished.
The delete's own result is never trusted: the branch step reports what a re-read of the branch shows. After
the delete the branch is read again; absent is deleted, still at the PR's head is deleted once more (one retry,
never more) and then refused as `delete-unconfirmed`, any other sha is `branch-moved`, and a branch that cannot
be read is `delete-outcome-unknown`.
"""
import argparse
import datetime
import importlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_NAME = "cloud-cleanup.json"
OUTCOMES = ("pending", "delivered", "uncertain", "failed")
ARCHIVE_TEXT_MERGED = (
    "Pull request #%d is merged, so this build is finished. Archive your own session now with your "
    "session tool. If you have no tool that archives a session, post one line on your issue naming "
    "the session tools you do have.")
ARCHIVE_TEXT_CLOSED = ARCHIVE_TEXT_MERGED.replace("is merged", "is closed without merging")
OWNER_MESSAGE_MERGED = ("#%d is merged. I've asked its cloud builder to archive itself. "
                        "You'll get one prompt for it: tap Allow once.")
OWNER_MESSAGE_CLOSED = ("#%d is closed. I've asked its cloud builder to archive itself. "
                        "You'll get one prompt for it: tap Allow once.")
_RECEIPT_KEYS = ("repo", "pr", "session", "msgId", "outcome", "at")
_LOCK_WAIT_SECONDS = 30
_GH_TIMEOUT = 60
_SHA_RE = re.compile(r"[0-9a-f]{40}([0-9a-f]{24})?")
_NOT_FOUND_RE = re.compile(r"HTTP 404|Not Found")


def _sib(name):
    if _LIB_DIR not in sys.path:
        sys.path.insert(0, _LIB_DIR)
    return importlib.import_module(name)


def _refusal(reason, **more):
    return dict({"ok": False, "reason": reason}, **more)


def _check_args(repo, pr):
    """(refusal or None, pr as int)."""
    if not (isinstance(repo, str) and _sib("cloud_builder")._REPO_RE.match(repo)):
        return _refusal("repo-invalid"), None
    number = int(pr) if isinstance(pr, str) and re.fullmatch(r"[1-9]\d*", pr) else pr
    if not (isinstance(number, int) and not isinstance(number, bool) and number > 0):
        return _refusal("pr-invalid"), None
    return None, number


def _state_path(repo_root, env):
    where = _sib("launch_ledger").ledger_path(repo_root, env)
    if not where["ok"]:
        return _refusal(where["reason"]), None
    return None, os.path.join(os.path.dirname(where["path"]), STATE_NAME)


def _load(repo_root, env):
    """(state path, receipts) or a refusal dict. A missing file is no receipts; any other file that is
    not a list of well-formed receipts is refused and left alone."""
    bad, path = _state_path(repo_root, env)
    if bad:
        return bad, None
    try:
        with open(path, encoding="utf-8") as fh:
            receipts = json.load(fh)
    except FileNotFoundError:
        return path, []
    except (OSError, ValueError):
        return _refusal("cleanup-state-unreadable"), None
    if not (isinstance(receipts, list) and all(
            isinstance(r, dict) and set(r) == set(_RECEIPT_KEYS)
            and isinstance(r["repo"], str) and isinstance(r["pr"], int) and isinstance(r["session"], str)
            and isinstance(r["msgId"], str) and r["outcome"] in OUTCOMES and isinstance(r["at"], str)
            for r in receipts)):
        return _refusal("cleanup-state-unreadable"), None
    return path, receipts


def _same_receipt(receipt, repo, pr, session):
    """Repository names compare without case (GitHub spells a repository as it likes); the receipt keeps
    the spelling it was saved with."""
    return (receipt["repo"].lower(), receipt["pr"], receipt["session"]) == (repo.lower(), pr, session)


def _save(path, receipts):
    try:
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        _sib("store_core").atomic_write(path, json.dumps(receipts, indent=1) + "\n")
    except Exception:
        return False
    return True


def _locked(fn):
    """Run a verb under one per-repository lock beside the state file, so its read-modify-write is not
    interleaved with another verb's. The state is re-read inside the lock by the verb itself."""
    def wrapper(repo_root, *args, env=None, **kwargs):
        env = os.environ if env is None else env
        bad, path = _state_path(repo_root, env)
        if bad:
            return bad
        lock = path + ".lock"
        fl = _sib("file_lock")
        deadline = time.monotonic() + _LOCK_WAIT_SECONDS
        while True:
            try:
                fl.acquire(lock, reclaim_dead_holder=True)
                break
            except fl.LockHeld:
                if time.monotonic() >= deadline:
                    return _refusal("cleanup-state-busy")
                time.sleep(0.05)
        try:
            return fn(repo_root, *args, env=env, **kwargs)
        finally:
            fl.release(lock)
    wrapper.__name__, wrapper.__doc__ = fn.__name__, fn.__doc__
    return wrapper


def _gh(run, args, env):
    """(exit code, stdout, stderr) of one `gh` call; (None, "", "") when it could not run at all."""
    runner = subprocess.run if run is None else run
    try:
        proc = runner(["gh"] + list(args), capture_output=True, text=True, timeout=_GH_TIMEOUT, env=dict(env))
    except Exception:
        return None, "", ""
    code, out, err = (getattr(proc, name, None) for name in ("returncode", "stdout", "stderr"))
    return (code if isinstance(code, int) else None), (out if isinstance(out, str) else ""), \
        (err if isinstance(err, str) else "")


def _object(run, path, env):
    """The JSON object at a REST path, or None when it could not be read."""
    code, out, _ = _gh(run, ["api", path], env)
    try:
        got = json.loads(out) if code == 0 else None
    except ValueError:
        return None
    return got if isinstance(got, dict) else None


def _pages(run, path, env):
    """Every item of a paginated REST list, or None when any page failed or was not a list of objects."""
    code, out, _ = _gh(run, ["api", "--paginate", path], env)
    try:
        found = _sib("pr_comment")._parse_paginated_arrays(out) if code == 0 else None
    except ValueError:
        return None
    return found if found is not None and all(isinstance(i, dict) for i in found) else None


def _name(node, *keys):
    for key in keys:
        node = node.get(key) if isinstance(node, dict) else None
    return node if isinstance(node, str) and node else None


def _epoch(stamp):
    """Epoch seconds of an ISO-8601 `created_at`; None when it is missing or not a timestamp."""
    if not isinstance(stamp, str):
        return None
    try:
        return datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _adopting_successor(repo_root, lid, lane, issues, pr, branch, env):
    """(launchId, lane, refusal): the latest later cloud lane of the given issues whose premise adopts this PR
    or its branch and whose fold shows a started cloud session; the given lane when there is none (an empty
    lane when the PR had no older cloud lane, so any such adopter is found). Read from the reserved records,
    which carry the premise `cloud_recover.successor` wrote."""
    ll = _sib("launch_ledger")
    got = ll.read(repo_root, env=env)
    if got["state"] not in ("ok", "missing", "tornTail"):
        return None, {}, "launch-ledger-unreadable"
    fold = ll.fold(got["records"])
    if not fold.get("ok", True):
        return None, {}, "launch-ledger-fold-failed"
    premises = {r.get("launchId"): r.get("premise") for r in got["records"] if r.get("event") == "reserved"}

    def adopts(premise):
        return isinstance(premise, dict) and (
            (premise.get("adopts") == pr and not isinstance(premise.get("adopts"), bool))
            or (bool(branch) and premise.get("adoptsBranch") == branch))

    later = [(i["reservedIndex"], k, i) for k, i in fold["launches"].items()
             if i["place"] == ll.PLACE_CLOUD and i["issue"] in issues
             and isinstance(i.get("cloudSessionName"), str) and i["cloudSessionName"]
             and i["reservedIndex"] > lane.get("reservedIndex", -1) and adopts(premises.get(k))]
    if not later:
        return lid, lane, None
    best = max(later, key=lambda t: t[0])
    return best[1], best[2], None


def _plan(repo_root, repo, pr, launch_id, env, run):
    """(result, facts): the plan, and the PR facts the branch step reads. `facts` is None unless the
    plan is a cleanup."""
    bad, pr = _check_args(repo, pr)
    if bad:
        return bad, None
    pull = _object(run, "repos/%s/pulls/%d" % (repo, pr), env)
    if pull is None or not isinstance(pull.get("state"), str):
        return _refusal("pr-unreadable"), None
    # axis: an open PR gets nothing, no lane read, no receipt, no message — see bite-proof record c8_cloud_cleanup
    if pull["state"] == "open":
        return {"ok": True, "action": "none", "reason": "pr-open"}, None
    outcome = "merged" if pull.get("merged") is True else "closed"
    opened = _epoch(pull.get("created_at"))
    if opened is None:
        return _refusal("pr-unreadable"), None
    cp = _sib("cloud_parked")
    issues = cp._linked_issues(pull.get("body"), repo)
    if not issues:
        return _refusal("pr-unlinked"), None
    if launch_id:
        found = [cp._lane(repo_root, issues, env, launch_id=launch_id)]
        if found[0][2] is None and found[0][1] and found[0][1].get("issue") not in issues:
            return _refusal("lane-mismatch"), None
    else:
        # axis: a lane reserved after the PR was opened cannot have built it, so the newest lane at or before the open — see bite-proof record c8_cloud_cleanup
        found = [cp._lane(repo_root, [issue], env, reserved_by=opened) for issue in issues]
    for _, _, reason in found:
        if reason:
            return _refusal(reason), None
    lanes = [(lid, lane) for lid, lane, _ in found if lane]
    if not lanes and not launch_id:
        # axis: a cloud builder that adopted a PR built elsewhere postdates it, so adopters are searched before refusing — see bite-proof record c8_cloud_cleanup
        lid, lane, reason = _adopting_successor(repo_root, None, {}, issues, pr, _name(pull.get("head"), "ref"), env)
        if reason:
            return _refusal(reason), None
        lanes = [(lid, lane)] if lane else []
    if not lanes:
        return _refusal("no-cloud-lane"), None
    if len(lanes) > 1:
        return _refusal("lane-ambiguous"), None
    lid, lane = lanes[0]
    if not launch_id:
        # axis: a later lane that adopted this PR (or its branch) is the one that finished it, so cleanup follows it — see bite-proof record c8_cloud_cleanup
        lid, lane, reason = _adopting_successor(repo_root, lid, lane, [lane.get("issue")], pr, _name(pull.get("head"), "ref"), env)
        if reason:
            return _refusal(reason), None
    session = lane.get("cloudSessionName")
    if not (isinstance(session, str) and session):
        return _refusal("lane-session-unknown"), None
    path, receipts = _load(repo_root, env)
    if receipts is None:
        return path, None
    request = next((r for r in receipts if _same_receipt(r, repo, pr, session)), {"state": "none"})
    head = pull.get("head")
    facts = {"branch": _name(head, "ref"), "headSha": _name(head, "sha"), "headRepo": _name(head, "repo", "full_name"),
             "baseRepo": _name(pull.get("base"), "repo", "full_name")}
    text = ARCHIVE_TEXT_MERGED if outcome == "merged" else ARCHIVE_TEXT_CLOSED
    delivered = request.get("outcome") == "delivered"
    result = {"ok": True, "action": "cleanup", "outcome": outcome, "repo": repo, "pr": pr, "issue": lane.get("issue"),
              "launchId": lid, "session": session, "sessionId": lane.get("cloudSessionId"),
              "configDir": lane.get("configDir"), "archiveText": None if delivered else text % pr,
              "request": request, "branch": facts["branch"], "headSha": facts["headSha"]}
    # axis: a confirmed delivery needs no further send, so a retried cleanup carries no archive text
    if delivered:
        result["alreadyDelivered"] = True
    return result, facts


def plan(repo_root, repo, pr, *, launch_id=None, env=None, run=None):
    """What to do for this PR: nothing while it is open; else the archive text for its lane's builder.
    Sends nothing and writes nothing."""
    env = os.environ if env is None else env
    return _plan(repo_root, repo, pr, launch_id, env, run)[0]


@_locked
def record(repo_root, repo, pr, msg_id, outcome, *, launch_id=None, env=None, run=None):
    """Record the archive request the advisor sent for this PR's lane. The receipt records the request,
    never the owner's prompt for it."""
    env = os.environ if env is None else env
    bad, number = _check_args(repo, pr)
    if bad:
        return bad
    if not (isinstance(msg_id, str) and msg_id.strip()):
        return _refusal("msg-id-invalid")
    if outcome not in OUTCOMES:
        return _refusal("outcome-invalid")
    got = plan(repo_root, repo, number, launch_id=launch_id, env=env, run=run)
    if not got["ok"]:
        return got
    if got["action"] == "none":
        return _refusal("pr-open")
    path, receipts = _load(repo_root, env)
    if receipts is None:
        return path
    texts = {"merged": OWNER_MESSAGE_MERGED, "closed": OWNER_MESSAGE_CLOSED}
    old = next((r for r in receipts if _same_receipt(r, repo, number, got["session"])), None)
    # axis: a pending write over a delivered receipt grants no reservation, so a caller holding a stale plan sends nothing
    if old is not None and old["outcome"] == "delivered" and outcome == "pending":
        return _refusal("request-delivered")
    if old is not None and old["outcome"] == "delivered":
        return {"ok": True, "already": True, "request": old, "ownerMessage": texts[got["outcome"]] % number}
    # axis: a pending write is an exclusive send reservation, refused whatever its message id when a request is already pending or uncertain
    if old is not None and outcome == "pending" and old["outcome"] in ("pending", "uncertain"):
        return _refusal("request-in-progress" if old["outcome"] == "pending" else "request-uncertain")
    if old is not None and old["outcome"] in ("pending", "uncertain") and old["msgId"] != msg_id:
        return _refusal("request-uncertain")
    receipt = {"repo": repo, "pr": number, "session": got["session"], "msgId": msg_id, "outcome": outcome,
               "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    receipts[:] = [r for r in receipts if r is not old] + [receipt]
    if not _save(path, receipts):
        return _refusal("cleanup-state-unwritable")
    # axis: the owner is told the builder was asked only once the request is confirmed delivered — see bite-proof record c8_cloud_cleanup
    owner = texts[got["outcome"]] % number if receipt["outcome"] == "delivered" else None
    return {"ok": True, "request": receipt, "ownerMessage": owner}


def _ref_sha(repo, branch, env, run):
    """(sha or None, refusal or None, absent): the branch's head sha; a 404 alone is absent."""
    code, out, err = _gh(run, ["api", "repos/%s/git/ref/heads/%s" % (repo, urllib.parse.quote(branch, safe="/"))], env)
    if code is None:
        return None, "branch-unreadable", False
    if code != 0:
        return (None, None, True) if _NOT_FOUND_RE.search(out + "\n" + err) else (None, "branch-unreadable", False)
    try:
        sha = (json.loads(out).get("object") or {}).get("sha")
    except (ValueError, AttributeError):
        return None, "branch-unreadable", False
    return (sha, None, False) if isinstance(sha, str) and _SHA_RE.fullmatch(sha) else (None, "branch-unreadable", False)


def _listing(repo, env, run):
    found = _pages(run, "repos/%s/branches?per_page=100" % repo, env)
    names = [b.get("name") for b in found] if found is not None else None
    return names if names is not None and all(isinstance(n, str) for n in names) else None


def _in_use(repo, branch, env, run):
    """True/False: an open PR uses the branch as head (in this repository) or as base; None unreadable."""
    found = _pages(run, "repos/%s/pulls?state=open&per_page=100" % repo, env)
    if found is None:
        return None
    for other in found:
        # axis: an open PR's base is as much a use of the branch as its head, so a stack's lower layer is kept — see bite-proof record c8_cloud_cleanup
        if _name(other, "base", "ref") == branch:
            return True
        # repository names compare without case (GitHub reports its own spelling); branch names stay exact
        head_repo = _name(other, "head", "repo", "full_name")
        if _name(other, "head", "ref") == branch and head_repo and head_repo.lower() == repo.lower():
            return True
    return False


def branch(repo_root, repo, pr, *, launch_id=None, env=None, run=None):
    """Delete the merged or closed PR's head branch, only while it is exactly the PR's recorded head."""
    env = os.environ if env is None else env
    got, facts = _plan(repo_root, repo, pr, launch_id, env, run)
    if not got["ok"] or got["action"] == "none":
        return got
    name, head_sha = facts["branch"], facts["headSha"]
    if not (name and not name.startswith("-") and not re.search(r"[\s\x00-\x1f\x7f]", name)
            and head_sha and _SHA_RE.fullmatch(head_sha)):
        return _refusal("pr-unreadable")
    if not facts["headRepo"] or facts["headRepo"] != facts["baseRepo"]:
        return _refusal("head-repo-foreign")
    repo_info = _object(run, "repos/%s" % repo, env)
    default = repo_info.get("default_branch") if repo_info else None
    if not (isinstance(default, str) and default):
        return _refusal("default-branch-unreadable")
    if name == default:
        return _refusal("default-branch")
    used = _in_use(repo, name, env, run)
    if used is None:
        return _refusal("open-prs-unreadable")
    if used:
        return _refusal("branch-in-use")
    sha, why, absent = _ref_sha(repo, name, env, run)
    if why:
        return _refusal(why)
    deleted, already = False, "absent"
    if not absent:
        # axis: work pushed after the PR's head is never deleted — see bite-proof record c8_cloud_cleanup
        if sha != head_sha:
            return _refusal("branch-moved")
        # axis: the delete goes through the gh channel the checks read, so it targets exactly the checked repository
        # The sha was read just above and is compared with the PR's head; the REST delete has no expected-sha
        # condition, so a push landing between that read and the delete is not caught (accepted: the PR is
        # already merged or closed and its builder is finished).
        # The delete's own result is never trusted: its exit code, output and errors decide nothing. The branch
        # step reports what a re-read of the branch shows. A ref still at the PR's head is deleted once more
        # (one retry, never more); any other sha is a moved branch; an unreadable ref is an unknown outcome.
        target = "repos/%s/git/refs/heads/%s" % (repo, urllib.parse.quote(name, safe="/"))
        detail = ""
        for _try in (1, 2):
            _, out, err = _gh(run, ["api", "-X", "DELETE", target], env)
            detail = next((ln for ln in (err or out).splitlines() if ln.strip()), "")
            # axis: only a 404 read-back after the delete is absent; the delete's own result says nothing — see bite-proof record c8_cloud_cleanup
            after, why, absent = _ref_sha(repo, name, env, run)
            if absent:
                deleted, already = True, None
                break
            # axis: a branch that is unreadable after the delete is an unknown outcome, never a success — see bite-proof record c8_cloud_cleanup
            if why:
                return _refusal("delete-outcome-unknown",
                                detail="the branch could not be read after the delete, so whether it was deleted is unknown")
            # axis: a branch that moved during the delete is never reported deleted — see bite-proof record c8_cloud_cleanup
            if after != head_sha:
                return _refusal("branch-moved")
        else:
            return _refusal("delete-unconfirmed", detail=detail)
    names = _listing(repo, env, run)
    if names is None:
        return _refusal("branches-unreadable")
    return {"ok": True, "action": "cleanup", "branch": name, "deleted": deleted, "already": already,
            "listing": names}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cloud_cleanup.py")
    verbs = parser.add_subparsers(dest="verb", required=True)
    for name in ("plan", "record", "branch"):
        sub = verbs.add_parser(name)
        sub.add_argument("--repo-root", required=True)
        sub.add_argument("--repo", required=True)
        sub.add_argument("--pr", required=True)
        sub.add_argument("--launch-id")
        if name == "record":
            sub.add_argument("--msg-id", required=True)
            sub.add_argument("--outcome", required=True)
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else list(argv))
    except SystemExit as exc:
        sys.stdout.write(json.dumps(_refusal("usage")) + "\n")
        return 0 if exc.code == 0 else 1
    if args.verb == "plan":
        result = plan(args.repo_root, args.repo, args.pr, launch_id=args.launch_id)
    elif args.verb == "record":
        result = record(args.repo_root, args.repo, args.pr, args.msg_id, args.outcome,
                        launch_id=args.launch_id)
    else:
        result = branch(args.repo_root, args.repo, args.pr, launch_id=args.launch_id)
    sys.stdout.write(json.dumps(result) + "\n")
    return 1 if result.get("ok") is False else 0


if __name__ == "__main__":
    sys.exit(main())
