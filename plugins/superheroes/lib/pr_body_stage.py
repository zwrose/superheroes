#!/usr/bin/env python3
"""A review finding about the PR body is fixed in a staged copy inside the review session, audited
there, and copied onto the PR only by `publish`, the one chokepoint that writes a PR body. It
publishes only bytes an audit discharged and never overwrites a live body that moved.

Session layout (all under ``<session>/pr-body/``):
  original.md     the body as ``<session>/pr.json`` held it; written once, never overwritten
  staged.md       the current staged copy; created from original.md once
  published.json  the publish receipt (``schema: "pr-body-publish/1"``), written for every outcome

The fixer works on a copy in its round's landing directory (``fixer_copy_path``): `dispatch-write
--landing-dir` already grants a restricted claude fixer file tools there, and ``pr-body/`` has no such
grant. The ``_`` prefix of the copy's name is ``record_paths.RESERVED_PREFIX``, which the landing sweep
skips, so the copy is never read as a stray seat file.

Stdlib plus the record layer; every public function returns a value instead of raising."""
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys

import record_paths
import round_commit
import round_records

CITATION = "SUPERHEROES_PR_BODY.md"  # the file name a finding cites for the PR body
PUBLISH_SCHEMA = "pr-body-publish/1"
PR_BODY_DIR = "pr-body"
ORIGINAL_FILE = "original.md"
STAGED_FILE = "staged.md"
PUBLISHED_FILE = "published.json"
FIXER_COPY_NAME = record_paths.RESERVED_PREFIX + "pr-body.md"
FIXER_PHASE = "dispatch-fixer"
_GH_TIMEOUT_SECONDS = 60

REASON_NO_PR = "no-pr"
REASON_PR_JSON_UNREADABLE = "pr-json-unreadable"
REASON_PR_JSON_UNPARSEABLE = "pr-json-unparseable"
REASON_PR_BODY_NOT_TEXT = "pr-body-not-text"
REASON_NOT_CONVERGED = "review-not-converged"
REASON_NOT_STAGED = "pr-body-not-staged"
REASON_LIVE_UNREADABLE = "pr-body-live-unreadable"
REASON_PUBLISHED_UNAUDITED = "pr-body-published-unaudited"
REASON_NOT_AUDITED = "pr-body-not-audited"
REASON_MOVED = "pr-body-moved"
REASON_PUBLISH_FAILED = "pr-body-publish-failed"
REASON_PUBLISH_UNVERIFIED = "pr-body-publish-unverified"
REASON_PR_INVALID = "pr-number-invalid"
REASON_ALREADY_PUBLISHED = "already-published"
REASON_LIVE_MOVED = "live-moved"

OUTCOME_PUBLISHED = "published"
OUTCOME_UNCHANGED = "unchanged"
OUTCOME_REFUSED = "refused"

_REFUSAL_PHRASES = {
    REASON_NOT_CONVERGED: "the review did not end converged",
    REASON_NOT_STAGED: "no staged copy of the PR body was kept for this review",
    REASON_LIVE_UNREADABLE: "the PR body on GitHub could not be read",
    REASON_PUBLISHED_UNAUDITED: ("the PR body on GitHub already holds the staged text, but no "
                                 "audit cleared that text"),
    REASON_NOT_AUDITED: "the staged PR-body text is not the text an audit cleared",
    REASON_MOVED: ("the live body changed during the review, outside the review, so the review "
                   "would not overwrite it"),
    REASON_PUBLISH_FAILED: "GitHub did not accept the edit",
    REASON_PUBLISH_UNVERIFIED: "the body read back from GitHub after the edit did not match",
    REASON_PR_INVALID: "the PR number was not usable",
}


def _sha(data):
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()


def paths(session_dir):
    root = os.path.abspath(os.path.join(session_dir, PR_BODY_DIR))
    return {"dir": root,
            "original": os.path.join(root, ORIGINAL_FILE),
            "staged": os.path.join(root, STAGED_FILE),
            "published": os.path.join(root, PUBLISHED_FILE)}


def _read_bytes(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def _read_text(path):
    data = _read_bytes(path)
    try:
        return None if data is None else data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _json(path):
    return round_records.read_json(path)[0]


def _same_body(a, b):
    """Equal, except that one trailing newline either side is no difference (GitHub may strip it)."""
    def trim(text):
        return text[:-1] if text.endswith("\n") else text
    return trim(a) == trim(b)


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fail(reason, **fields):
    return {"ok": False, "reason": reason, **fields}


# ---- stage -----------------------------------------------------------------------------------

def stage(session_dir):
    """Create ``original.md`` and ``staged.md`` from ``pr.json``'s body, once; an existing file is
    never overwritten. ``{"ok": True, "staged": False, "reason": "no-pr"}`` in branch mode."""
    try:
        return _stage(session_dir)
    except Exception as exc:  # noqa: BLE001 — public functions never raise
        return _fail("pr-body-stage-error", staged=False, detail="%s: %s" % (type(exc).__name__, exc))


def _stage(session_dir):
    pr_path = os.path.join(session_dir, "pr.json")
    if not os.path.lexists(pr_path):
        return {"ok": True, "staged": False, "reason": REASON_NO_PR}
    pr, err = round_records.read_json(pr_path)
    if err == "missing":
        return _fail(REASON_PR_JSON_UNREADABLE, staged=False)
    if err or not isinstance(pr, dict):
        return _fail(REASON_PR_JSON_UNPARSEABLE, staged=False)
    body = pr.get("body")
    if not isinstance(body, str):
        return _fail(REASON_PR_BODY_NOT_TEXT, staged=False)
    try:
        body_bytes = body.encode("utf-8")
    except UnicodeEncodeError:
        return _fail(REASON_PR_BODY_NOT_TEXT, staged=False)
    p = paths(session_dir)
    if not os.path.lexists(p["original"]):
        round_commit.atomic_write_bytes(p["original"], body_bytes)
    original = _read_bytes(p["original"])
    if original is not None and not os.path.lexists(p["staged"]):
        round_commit.atomic_write_bytes(p["staged"], original)
    staged = _read_bytes(p["staged"])
    if staged is None or original is None:
        return _fail(REASON_NOT_STAGED, staged=False)
    return {"ok": True, "staged": True, "reason": None,
            "originalPath": p["original"], "stagedPath": p["staged"],
            "originalSha256": _sha(original), "stagedSha256": _sha(staged)}


# ---- the fixer's copy ------------------------------------------------------------------------

def fixer_copy_path(session_dir, rnd):
    return os.path.join(record_paths.landing_dir(session_dir, rnd, FIXER_PHASE), FIXER_COPY_NAME)


def seed_fixer_copy(session_dir, rnd):
    """Copy ``staged.md`` to the round's fixer copy when that copy is absent (several fix-batch
    attempts in one round share it). Returns the sha256 of ``staged.md`` (the round's "before"), or
    None when nothing is staged."""
    try:
        staged = _read_bytes(paths(session_dir)["staged"])
        if staged is None:
            return None
        copy = fixer_copy_path(session_dir, rnd)
        if not os.path.lexists(copy):
            round_commit.atomic_write_bytes(copy, staged)
        return _sha(staged)
    except Exception:  # noqa: BLE001
        return None


def collect_fixer_copy(session_dir, rnd):
    """Atomically replace ``staged.md`` with the round's fixer copy when it exists. Returns the new
    sha256 (the round's "after"), or None, changing nothing, when there is no copy or no staged one."""
    try:
        p = paths(session_dir)
        if not os.path.lexists(p["staged"]):
            return None
        data = _read_bytes(fixer_copy_path(session_dir, rnd))
        if data is None:
            return None
        round_commit.atomic_write_bytes(p["staged"], data)
        return _sha(data)
    except Exception:  # noqa: BLE001
        return None


# ---- publish ---------------------------------------------------------------------------------

def _default_runner(argv):
    return subprocess.run(argv, capture_output=True, text=True, timeout=_GH_TIMEOUT_SECONDS,
                          check=False)


def _run(runner, argv):
    """``(returncode, stdout)``; a runner that cannot run counts as a non-zero exit."""
    try:
        done = runner(argv)
        return done.returncode, done.stdout
    except Exception:  # noqa: BLE001
        return 1, ""


def _pull_endpoint(pr):
    """The REST path of a PR; ``{owner}/{repo}`` stays literal and ``gh`` fills it from the current
    repository. Every GitHub call goes through REST because GraphQL (``gh pr view``/``edit``) is
    unreachable from some sessions."""
    return "repos/{owner}/{repo}/pulls/%s" % pr


def _read_live(runner, pr):
    """The live PR body, or None when it cannot be read as text."""
    code, out = _run(runner, ["gh", "api", _pull_endpoint(pr)])
    if code != 0:
        return None
    try:
        parsed = json.loads(out)
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, dict) or "body" not in parsed:
        return None
    body = parsed["body"]
    if body is None:  # REST returns null for an empty description
        return ""
    return body if isinstance(body, str) else None


def _converged(session_dir):
    receipt = _json(os.path.join(session_dir, "round-receipt.json"))
    return isinstance(receipt, dict) and receipt.get("verdict") == "converged"


def _audited_sha(session_dir):
    """The ``prBodyAudited`` sha of the highest-numbered round that recorded one, or None."""
    state = _json(os.path.join(session_dir, "loop-state.json"))
    rounds = state.get("rounds") if isinstance(state, dict) else None
    if not isinstance(rounds, dict):
        return None
    numbered = []
    for key, rec in rounds.items():
        if isinstance(rec, dict) and isinstance(rec.get("prBodyAudited"), str) \
                and rec["prBodyAudited"] and str(key).isdigit():
            numbered.append((int(key), rec["prBodyAudited"]))
    return max(numbered)[1] if numbered else None


def publish(session_dir, pr, runner=None):
    """The one chokepoint that writes a PR body. Returns the dict it writes to ``published.json``
    (``ok``, ``reason``, ``outcome``, ``pr``, the sha256s, ``at``) for every outcome, refusals
    included. Never raises."""
    try:
        return _publish(session_dir, pr, runner or _default_runner)
    except Exception as exc:  # noqa: BLE001
        return _fail("pr-body-publish-error", outcome=OUTCOME_REFUSED, pr=pr,
                     detail="%s: %s" % (type(exc).__name__, exc))


def _publish(session_dir, pr, runner):
    if not os.path.isdir(session_dir):
        return _fail(REASON_NOT_STAGED, outcome=OUTCOME_REFUSED, pr=pr)
    p = paths(session_dir)
    receipt = {"schema": PUBLISH_SCHEMA, "pr": pr}

    def done(outcome, reason):
        receipt.update(ok=outcome != OUTCOME_REFUSED, outcome=outcome, reason=reason)
        receipt.setdefault("at", _now())
        round_records.atomic_write_json(p["published"], receipt)
        return receipt

    pr_text = str(pr) if not isinstance(pr, bool) else ""
    if not pr_text.isdigit() or int(pr_text) < 1:
        return done(OUTCOME_REFUSED, REASON_PR_INVALID)
    if not _converged(session_dir):
        return done(OUTCOME_REFUSED, REASON_NOT_CONVERGED)
    staged, original = _read_text(p["staged"]), _read_text(p["original"])
    if staged is None or original is None:
        return done(OUTCOME_REFUSED, REASON_NOT_STAGED)
    receipt.update(originalSha256=_sha(original), stagedSha256=_sha(staged))
    live = _read_live(runner, pr_text)
    if live is None:
        return done(OUTCOME_REFUSED, REASON_LIVE_UNREADABLE)
    receipt["liveSha256"] = _sha(live)
    if _same_body(staged, original):
        return done(OUTCOME_UNCHANGED, None if _same_body(live, original) else REASON_LIVE_MOVED)
    audited = receipt["stagedSha256"] == _audited_sha(session_dir)
    if _same_body(live, staged):
        if not audited:
            return done(OUTCOME_REFUSED, REASON_PUBLISHED_UNAUDITED)
        prior = _json(p["published"])
        if isinstance(prior, dict) and prior.get("outcome") == OUTCOME_PUBLISHED:
            if isinstance(prior.get("at"), str):
                receipt["at"] = prior["at"]
            return done(OUTCOME_PUBLISHED, REASON_ALREADY_PUBLISHED)
    if not audited:
        return done(OUTCOME_REFUSED, REASON_NOT_AUDITED)
    if not _same_body(live, original):
        return done(OUTCOME_REFUSED, REASON_MOVED)
    edit = ["gh", "api", "-X", "PATCH", _pull_endpoint(pr_text), "-F", "body=@%s" % p["staged"]]
    if _run(runner, edit)[0] != 0:
        return done(OUTCOME_REFUSED, REASON_PUBLISH_FAILED)
    after = _read_live(runner, pr_text)
    if after is None or not _same_body(after, staged):
        return done(OUTCOME_REFUSED, REASON_PUBLISH_UNVERIFIED)
    return done(OUTCOME_PUBLISHED, None)


# ---- the review account's line ---------------------------------------------------------------

def _has_fix_to_copy(session_dir):
    """True when a staged copy exists and differs from the original; without one there is no
    PR-body fix, whatever the receipt's refusal reason."""
    p = paths(session_dir)
    staged, original = _read_text(p["staged"]), _read_text(p["original"])
    return staged is not None and original is not None and not _same_body(staged, original)


def record_line(session_dir):
    """One plain-English sentence about the publish receipt for the review account, or None.
    A refusal is reported as a copy that was not made only when there was a fix to copy."""
    try:
        receipt = _json(paths(session_dir)["published"])
        if not isinstance(receipt, dict):
            return None
        outcome, reason = receipt.get("outcome"), receipt.get("reason")
        if outcome == OUTCOME_PUBLISHED:
            return "The review copied its audited PR-body fix onto the PR."
        if outcome == OUTCOME_UNCHANGED:
            if reason == REASON_LIVE_MOVED:
                return ("The PR body changed on GitHub during the review, outside the review; the "
                        "review had no PR-body fix to copy.")
            return None
        if outcome == OUTCOME_REFUSED and isinstance(reason, str):
            if not _has_fix_to_copy(session_dir):
                return None
            phrase = _REFUSAL_PHRASES.get(reason, "the copy was refused (%s)" % reason)
            return "The review did not copy its PR-body fix onto the PR: %s." % phrase
        return None
    except Exception:  # noqa: BLE001
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = parser.add_subparsers(dest="verb", required=True)
    p_stage = sub.add_parser("stage")
    p_stage.add_argument("--session-dir", required=True)
    p_pub = sub.add_parser("publish")
    p_pub.add_argument("--session-dir", required=True)
    p_pub.add_argument("--pr", required=True)
    args = parser.parse_args(argv)
    if args.verb == "stage":
        result = stage(args.session_dir)
    else:
        result = publish(args.session_dir, args.pr)
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
