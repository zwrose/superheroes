#!/usr/bin/env python3
"""A review finding about the PR body is fixed in a staged copy inside the review session, audited
there, and copied onto the PR only by `publish` — the one chokepoint that writes a PR body. It
publishes only bytes an audit discharged and never overwrites a live body that moved. Fixers never
write to GitHub.

Session layout (all under ``<session>/pr-body/``):
  original.md     the body as ``<session>/pr.json`` held it; written once, never overwritten
  staged.md       the current staged copy; created from original.md once
  published.json  the publish receipt (``schema: "pr-body-publish/1"``), written for every outcome

The fixer works on a copy in its round's landing directory (``fixer_copy_path``): `dispatch-write
--landing-dir` already grants a restricted claude fixer file tools there, and ``pr-body/`` has no such
grant. The ``_`` prefix of the copy's name is ``record_paths.RESERVED_PREFIX``, which the landing sweep
skips, so the copy is never read as a stray seat file.

Stdlib plus ``record_paths``; every public function returns a value instead of raising."""
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys

import record_paths

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


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def paths(session_dir):
    """Absolute paths of the session's PR-body files."""
    root = os.path.abspath(os.path.join(session_dir, PR_BODY_DIR))
    return {"dir": root,
            "original": os.path.join(root, ORIGINAL_FILE),
            "staged": os.path.join(root, STAGED_FILE),
            "published": os.path.join(root, PUBLISHED_FILE)}


def _atomic_write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _read_bytes(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def _read_text(path):
    data = _read_bytes(path)
    if data is None:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _read_json_file(path):
    data = _read_bytes(path)
    if data is None:
        return None
    try:
        return json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None


def _same_body(a, b):
    """Body equality: exact, except one trailing newline either side is not a difference (GitHub may
    strip it from the stored body)."""
    def trim(text):
        return text[:-1] if text.endswith("\n") else text
    return trim(a) == trim(b)


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fail(reason, **fields):
    out = {"ok": False, "reason": reason}
    out.update(fields)
    return out


# ---- stage -----------------------------------------------------------------------------------

def stage(session_dir):
    """Create ``original.md`` and ``staged.md`` from ``pr.json``'s body, once. Idempotent: an existing
    file is never overwritten. ``{"ok": True, "staged": False, "reason": "no-pr"}`` in branch mode."""
    try:
        return _stage(session_dir)
    except Exception as exc:  # noqa: BLE001 — public functions never raise
        return _fail("pr-body-stage-error", staged=False, detail="%s: %s" % (type(exc).__name__, exc))


def _stage(session_dir):
    pr_path = os.path.join(session_dir, "pr.json")
    if not os.path.lexists(pr_path):
        return {"ok": True, "staged": False, "reason": REASON_NO_PR}
    raw = _read_bytes(pr_path)
    if raw is None:
        return _fail(REASON_PR_JSON_UNREADABLE, staged=False)
    try:
        pr = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return _fail(REASON_PR_JSON_UNPARSEABLE, staged=False)
    if not isinstance(pr, dict):
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
        _atomic_write(p["original"], body_bytes)
    if not os.path.lexists(p["staged"]):
        original = _read_bytes(p["original"])
        if original is None:
            return _fail(REASON_NOT_STAGED, staged=False)
        _atomic_write(p["staged"], original)
    staged = _read_bytes(p["staged"])
    original = _read_bytes(p["original"])
    if staged is None or original is None:
        return _fail(REASON_NOT_STAGED, staged=False)
    return {"ok": True, "staged": True, "reason": None,
            "originalPath": p["original"], "stagedPath": p["staged"],
            "originalSha256": _sha256_bytes(original), "stagedSha256": _sha256_bytes(staged)}


# ---- the fixer's copy ------------------------------------------------------------------------

def fixer_copy_path(session_dir, rnd):
    """The round's fixer copy, inside the landing directory a restricted claude fixer is granted."""
    return os.path.join(record_paths.landing_dir(session_dir, rnd, FIXER_PHASE), FIXER_COPY_NAME)


def seed_fixer_copy(session_dir, rnd):
    """Copy ``staged.md`` to the round's fixer copy when that copy is absent (several fix-batch
    attempts in one round share it). Returns the sha256 of ``staged.md`` — the round's "before" — or
    None when nothing is staged."""
    try:
        staged = _read_bytes(paths(session_dir)["staged"])
        if staged is None:
            return None
        copy = fixer_copy_path(session_dir, rnd)
        if not os.path.lexists(copy):
            _atomic_write(copy, staged)
        return _sha256_bytes(staged)
    except Exception:  # noqa: BLE001
        return None


def collect_fixer_copy(session_dir, rnd):
    """Atomically replace ``staged.md`` with the round's fixer copy when that copy exists. Returns the
    new sha256 — the round's "after" — or None, changing nothing, when there is no copy (or no staged
    copy to replace)."""
    try:
        p = paths(session_dir)
        if not os.path.lexists(p["staged"]):
            return None
        data = _read_bytes(fixer_copy_path(session_dir, rnd))
        if data is None:
            return None
        _atomic_write(p["staged"], data)
        return _sha256_bytes(data)
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


def _read_live(runner, pr):
    """The live PR body, or None when it cannot be read as text."""
    code, out = _run(runner, ["gh", "pr", "view", str(pr), "--json", "body"])
    if code != 0:
        return None
    try:
        parsed = json.loads(out)
    except (TypeError, ValueError):
        return None
    body = parsed.get("body") if isinstance(parsed, dict) else None
    return body if isinstance(body, str) else None


def _converged(session_dir):
    receipt = _read_json_file(os.path.join(session_dir, "round-receipt.json"))
    return isinstance(receipt, dict) and receipt.get("verdict") == "converged"


def _audited_sha(session_dir):
    """The ``prBodyAudited`` sha of the highest-numbered round that recorded one, or None."""
    state = _read_json_file(os.path.join(session_dir, "loop-state.json"))
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

    def done(outcome, reason, ok=True, **fields):
        receipt.update(fields)
        receipt.update(ok=ok, outcome=outcome, reason=reason)
        receipt.setdefault("at", _now())
        _atomic_write(p["published"],
                      (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode("utf-8"))
        return receipt

    def refuse(reason):
        return done(OUTCOME_REFUSED, reason, ok=False)

    pr_text = str(pr) if not isinstance(pr, bool) else ""
    if not pr_text.isdigit() or int(pr_text) < 1:
        return refuse(REASON_PR_INVALID)
    if not _converged(session_dir):
        return refuse(REASON_NOT_CONVERGED)
    staged = _read_text(p["staged"])
    original = _read_text(p["original"])
    if staged is None or original is None:
        return refuse(REASON_NOT_STAGED)
    staged_sha = _sha256_bytes(staged.encode("utf-8"))
    receipt["originalSha256"] = _sha256_bytes(original.encode("utf-8"))
    receipt["stagedSha256"] = staged_sha
    live = _read_live(runner, pr_text)
    if live is None:
        return refuse(REASON_LIVE_UNREADABLE)
    receipt["liveSha256"] = _sha256_bytes(live.encode("utf-8"))
    audited = staged_sha == _audited_sha(session_dir)
    if _same_body(live, staged) and not _same_body(staged, original):
        if not audited:
            return refuse(REASON_PUBLISHED_UNAUDITED)
        prior = _read_json_file(p["published"])
        if isinstance(prior, dict) and prior.get("outcome") == OUTCOME_PUBLISHED \
                and isinstance(prior.get("at"), str):
            receipt["at"] = prior["at"]
        return done(OUTCOME_PUBLISHED, REASON_ALREADY_PUBLISHED)
    if _same_body(staged, original):
        if _same_body(live, original):
            return done(OUTCOME_UNCHANGED, None)
        return done(OUTCOME_UNCHANGED, REASON_LIVE_MOVED)
    if not audited:
        return refuse(REASON_NOT_AUDITED)
    if not _same_body(live, original):
        return refuse(REASON_MOVED)
    code, _out = _run(runner, ["gh", "pr", "edit", pr_text, "--body-file", p["staged"]])
    if code != 0:
        return refuse(REASON_PUBLISH_FAILED)
    after = _read_live(runner, pr_text)
    if after is None or not _same_body(after, staged):
        return refuse(REASON_PUBLISH_UNVERIFIED)
    return done(OUTCOME_PUBLISHED, None)


# ---- the review account's line ---------------------------------------------------------------

def record_line(session_dir):
    """One plain-English sentence about the publish receipt for the review account, or None."""
    try:
        receipt = _read_json_file(paths(session_dir)["published"])
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
