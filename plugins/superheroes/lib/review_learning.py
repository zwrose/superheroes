#!/usr/bin/env python3
"""The review learning loop's code: the adoption day, the owner-approved
calibration change (a Risk and trust half, a standing ruling, a project focus hint or a CLAUDE.md rule),
and the seat and escape-kind tally that starts counting at the adoption day.

CLI (`python3 -B lib/review_learning.py <verb>`; one JSON object on stdout; exit 0 on ok, 1 on a refusal):
  adopt --cwd D [--root R] --date YYYY-MM-DD      # record the adoption day once
  since --cwd D [--root R]                        # read it back
  apply --cwd D [--root R] --canon-root R --session-id S --proposal F --approval F
  tally --records F --escapes F (--since YYYY-MM-DD | --cwd D [--root R]) [--until D] [--window-days N]
  seating --row F                                 # the security and premortem seats' numbers; a number not given reads "unmeasured"
"""
import argparse
import collections
import contextlib
import datetime
import json
import math
import os
import re
import subprocess
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import canon  # noqa: E402
import control_plane  # noqa: E402
import core_md  # noqa: E402
import definition_doc  # noqa: E402
import mode_registry  # noqa: E402
import project_config  # noqa: E402
import review_findings_schema  # noqa: E402
import review_record  # noqa: E402
import review_record_session  # noqa: E402
import review_seats  # noqa: E402
import session_contract  # noqa: E402
import store_core  # noqa: E402

SINCE_KEY = "reviewLearningSince"
PROPOSAL_SCHEMA = "calibration-proposal/1"
COMMIT_MESSAGE = "docs: record an approved calibration change in Canon"
GIT_TIMEOUT_SECONDS = 60  # a stalled signer or commit hook must not hang apply after Canon is appended
_FIXED = review_findings_schema.OUTCOMES[0]
_KEYS = {"risk-and-trust": {"schema", "kind", "half", "value", "ruling"},
         "standing-ruling": {"schema", "kind", "ruling"},
         "focus-hint": {"schema", "kind", "hint", "ruling"},
         "claude-md-rule": {"schema", "kind", "rule", "ruling"}}
_LINE_FIELD = {"focus-hint": "hint", "claude-md-rule": "rule"}  # the one line each text kind adds
REVIEW_LAYER_HERO = "review-crew"  # the review settings' layer, whose Focus hints section a focus hint joins
FOCUS_HEADING = "## Focus hints"
CLAUDE_MD = "CLAUDE.md"
SUPERSEDES_KEY = "supersedes"  # optional on either kind: the Canon entry id a replacement retires
DIMENSION_SEAT = review_seats.DIMENSION_SEAT
_SEATS = set(DIMENSION_SEAT.values())
_KNOWN = set(DIMENSION_SEAT) | _SEATS
FALSE_CLAIM_MARKER = "false-pr-claim"  # an escape input item carrying this "marker" is a false PR claim, counted apart from escapes
SEATING_SEATS = ("security", "premortem")
UNMEASURED = "unmeasured"
# what would have caught an escape: the eight kinds, in the order owner-decisions.md lists them
ESCAPE_KINDS = ("claude-md-rule", "focus-hint", "plugin-reviewer-instruction", "one-time-sweep",
                "permanent-check", "environment-test", "risk-setting-or-leftover-rule", "nothing-reachable")


def _canon_id(value):
    """Whether the whole string is one Canon entry id, by Canon's own grammar (canon.ids_in)."""
    return isinstance(value, str) and canon.ids_in("- **%s**" % value) == {value}


def _result(ok, outcome, reason=None, detail=None, **extra):
    return {"ok": ok, "outcome": outcome, "reason": reason, "detail": detail, **extra}


def _day(value, whole=True):
    """The date a string is (or, when not `whole`, starts with), or None."""
    match = re.fullmatch if whole else re.match
    if not isinstance(value, str) or not match(r"\d{4}-\d{2}-\d{2}" + ("" if whole else r"(?=$|[T ])"), value):
        return None
    try:
        return datetime.date.fromisoformat(value[:10])
    except ValueError:
        return None


# --- the adoption day (I3) ---

def adoption_day(cwd, root=None):
    # scrubbed: core_md resolves the project through git, which must act on `cwd`, not an inherited GIT_DIR / GIT_WORK_TREE
    with _scrubbed_environ():
        return _adoption_day(cwd, root)


def _adoption_day(cwd, root):
    facts = core_md.read(cwd, root)
    mapping = facts.get("projectConfiguration") if facts else None
    if not isinstance(mapping, dict) or SINCE_KEY not in mapping:
        return {"since": None, "reason": "not-recorded"}
    stored = mapping[SINCE_KEY]
    return {"since": stored, "reason": None} if _day(stored) else {"since": None, "reason": "malformed"}


def record_adoption_day(cwd, day, root=None):
    # one scrubbed span over the read and the compare-and-set write, so both act on the requested project
    with _scrubbed_environ():
        return _record_adoption_day(cwd, day, root)


def _record_adoption_day(cwd, day, root):
    if _day(day) is None:
        return _result(False, "refused", "bad-date", "%r is not an ISO date (YYYY-MM-DD)" % (day,))
    cur = adoption_day(cwd, root)
    if cur["since"] == day:
        return _result(True, "unchanged", since=day)
    # axis: the adoption day is set once; a different day never overwrites the stored one — see bite-proof record wo_a_1718_adopt-set-once
    wrote = core_md.write_project_config_item_if(cwd, SINCE_KEY, day, expected=None, root=root)
    if wrote.get("reason") == "item-changed":
        return _result(False, "refused", "adoption-day-already-recorded", wrote.get("observed"),
                       since=wrote.get("observed"))
    if wrote.get("action") not in ("written", "noop"):
        return _result(False, "refused", wrote.get("reason") or wrote.get("action"), wrote)
    return _result(True, "recorded", since=day)


# --- the owner-approved calibration change (I1, I2) ---

def _owner_yes(approval):
    return (isinstance(approval, dict) and approval.get("answer") == "yes"
            and all(isinstance(approval.get(k), str) and approval[k].strip() for k in ("words", "where"))
            and _day(approval.get("date")) is not None)


def _proposal_problem(p):
    """What is wrong with the whole proposal, or None. Nothing is written before this is None."""
    kind = p.get("kind") if isinstance(p, dict) else None
    keys = _KEYS.get(kind) if isinstance(kind, str) else None
    if keys is None:
        return "kind must be one of %s" % ", ".join(repr(k) for k in _KEYS)
    if set(p) - {SUPERSEDES_KEY} != keys or p.get("schema") != PROPOSAL_SCHEMA:
        return "a %s proposal is exactly %s (plus an optional %s) with schema %s" % (
            p["kind"], sorted(keys), SUPERSEDES_KEY, PROPOSAL_SCHEMA)
    if SUPERSEDES_KEY in p and not (_canon_id(p[SUPERSEDES_KEY])):
        return "supersedes must be the id of the Canon entry being replaced (YYYY-MM-DD-xxxxxxxx-N)"
    try:
        canon._field("ruling", p["ruling"] if isinstance(p["ruling"], str) else "")
    except canon.Refusal as exc:
        return exc.payload["detail"]
    if p["kind"] == "risk-and-trust":
        item = project_config._item_by_slug("riskAndTrust")
        if not isinstance(p["half"], str) or project_config.validate_item_value(item, {p["half"]: p["value"]}):
            return "half must name one riskAndTrust half, and value must be that half's valid value"
    field = _LINE_FIELD.get(p["kind"])
    if field:
        text = p[field]
        # axis: a hint or rule is one plain line, so it can never add a heading or a second line — see bite-proof record wo_2190_one-line
        # one line by splitlines(), the same split the writer's read-back uses, so a Unicode line separator is refused too
        if (not isinstance(text, str) or not text.strip() or text != text.strip()
                or len(text.splitlines()) != 1 or text.startswith("#")):
            return "%s must be one non-empty line with no surrounding space, not a heading" % field
    return None


def _append_args(canon_root, session_id, proposal, approval):
    argv = ["append", "--root=" + canon_root, "--session-id=" + str(session_id), "--ground=owner-call",
            "--scope=standing", "--ruling=" + proposal["ruling"], "--owners-words=" + approval["words"],
            "--where=" + approval["where"], "--date=" + approval["date"]]
    if proposal.get(SUPERSEDES_KEY):
        argv.append("--supersedes=" + proposal[SUPERSEDES_KEY])
    return canon._parser().parse_args(argv)


def _append_canon(canon_root, session_id, proposal, approval):
    return canon.cmd_append(_append_args(canon_root, session_id, proposal, approval))


def _run_git(cwd, *args):
    """Canon's git, bounded: the same invocation as canon._git plus a timeout (canon.py stays untouched)."""
    return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True,
                          timeout=GIT_TIMEOUT_SECONDS, env=definition_doc._scrubbed_git_env())


@contextlib.contextmanager
def _scrubbed_environ():
    """The ambient environment minus the git routing variables `_run_git` removes, for the span of the
    block, so a shared probe that cannot take an env acts on the repository it was given."""
    scrubbed = definition_doc._scrubbed_git_env()
    gone = {k: v for k, v in os.environ.items() if k not in scrubbed}
    for k in gone:
        del os.environ[k]
    try:
        yield
    finally:
        os.environ.update(gone)


def _refresh_default_branch(canon_root):
    """Canon's write procedure step 1: when an origin remote exists, `git fetch origin` before the lookup,
    so a stale origin/HEAD does not hide a Canon the default branch already has. Returns a note saying the
    refresh could not run or failed, or None when it ran or there is no origin to refresh from."""
    try:
        if _run_git(canon_root, "remote", "get-url", "origin").returncode != 0:
            return None  # no origin remote: nothing to refresh
        got = _run_git(canon_root, "fetch", "origin")
    except subprocess.TimeoutExpired:
        return "the default branch was not refreshed: git fetch origin timed out after %ss" % GIT_TIMEOUT_SECONDS
    except OSError as exc:
        return "the default branch was not refreshed: git could not be run (%s: %s)" % (type(exc).__name__, exc)
    if got.returncode != 0:
        return "the default branch was not refreshed: git fetch origin failed: %s" % (got.stderr or got.stdout).strip()
    return None


def _noted(out, note):
    if note:
        out["detail"] = "%s; %s" % (out["detail"], note) if out.get("detail") else note
    return out


def _commit_canon(res, line):
    """Canon's write procedure steps 7-8: commit only Canon's paths, then see the line in HEAD."""
    git_root = res["gitRoot"]
    rel = os.path.relpath(res["path"], git_root).replace(os.sep, "/")
    try:
        before = _run_git(git_root, "rev-parse", "HEAD")
        before_head = before.stdout.strip() if before.returncode == 0 else None
    except (subprocess.TimeoutExpired, OSError):
        before_head = None
    failure = None
    try:
        for args in (("add", "--", *res["commitPaths"]), ("commit", "-m", COMMIT_MESSAGE, "--", *res["commitPaths"])):
            got = _run_git(git_root, *args)
            if got.returncode != 0:
                failure = "git %s failed: %s" % (args[0], (got.stderr or got.stdout).strip())
                break
    except subprocess.TimeoutExpired as exc:
        failure = "git %s timed out after %ss" % (exc.cmd[3] if len(exc.cmd) > 3 else "command", GIT_TIMEOUT_SECONDS)
    except OSError as exc:
        failure = "git could not be run (%s: %s)" % (type(exc).__name__, exc)
    if failure:
        # a commit that errored or timed out continues only when HEAD shows it landed (the one shared proof)
        landed = project_config._commit_landed(git_root, rel, before_head, [line])
        if landed is not True:
            return None, failure + ("; git could not say whether the commit landed" if landed is None else "")
    try:
        shown = _run_git(git_root, "show", "HEAD:" + rel)
        if shown.returncode != 0 or line not in shown.stdout.splitlines():
            return None, "HEAD:%s does not hold the appended line" % rel
        return _run_git(git_root, "rev-parse", "HEAD").stdout.strip(), None
    except subprocess.TimeoutExpired as exc:
        return None, "git %s timed out after %ss" % (exc.cmd[3] if len(exc.cmd) > 3 else "command", GIT_TIMEOUT_SECONDS)
    except OSError as exc:
        return None, "git could not be run (%s: %s)" % (type(exc).__name__, exc)


# --- the two text kinds: a project focus hint and a CLAUDE.md rule ---

class TargetUnreadable(OSError):
    """A text kind's home file exists but cannot be read as UTF-8 text."""


def _text_target(cwd, kind, root):
    """The file a text kind writes, or raises OSError naming why there is none. A focus hint joins the
    review settings' layer; a CLAUDE.md rule joins the CLAUDE.md at the project's git root. Neither file
    is created: a project with none has not set that home up, and the owner's yes does not set it up."""
    if kind == "focus-hint":
        try:
            path = core_md.layer_path(cwd, REVIEW_LAYER_HERO, root)
        except store_core.RepoRootUnavailable as exc:
            raise OSError("the review settings' layer could not be located: %s" % exc) from exc
    else:
        top = _run_git(cwd, "rev-parse", "--show-toplevel")
        if top.returncode != 0:
            raise OSError("the project's git root could not be read: %s" % (top.stderr or top.stdout).strip())
        path = os.path.join(top.stdout.strip(), CLAUDE_MD)
    if not os.path.isfile(path):
        raise OSError("%s does not exist" % path)
    try:
        with open(path, encoding="utf-8") as fh:
            fh.read()
    except UnicodeError as exc:
        # axis: a home file that is not UTF-8 text is refused before Canon is written — see bite-proof record wo_2190_target-unreadable
        raise TargetUnreadable("%s is not UTF-8 text: %s" % (path, exc)) from exc
    # the cloud calibration guard reads the path as given (a link standing where a calibration file belongs),
    # so it runs here, before the writer resolves the link to its target
    # axis: a cloud session never writes a calibration file through a symlinked layer — see bite-proof record wo_2190_cloud-guard
    if store_core.in_cloud_session() and store_core.is_calibration_path(path):
        raise store_core.CalibrationWriteRefused("%s: %s" % (store_core.CLOUD_REFUSAL_REASON, path))
    return path


def _with_focus_hint(text, line):
    """The layer text with `line` as the last bullet of its Focus hints section (a new section at the end
    when there is none), or None when the section already holds that bullet."""
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if l.strip() == FOCUS_HEADING), None)
    if start is None:
        return text.rstrip("\n") + "\n\n%s\n\n%s\n" % (FOCUS_HEADING, line)
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    if line in (l.rstrip() for l in lines[start + 1:end]):
        return None
    at = end
    while at > start + 1 and not lines[at - 1].strip():
        at -= 1
    added = [line] if at > start + 1 else ["", line]
    lines[at:at] = added + ([""] if at < len(lines) and lines[at].strip() else [])
    return "\n".join(lines) + "\n"


def _with_claude_md_rule(text, line):
    """CLAUDE.md with `line` appended as its own paragraph, or None when a line already reads exactly that."""
    if line in (l.rstrip() for l in text.splitlines()):
        return None
    return text.rstrip("\n") + "\n\n" + line + "\n"


def _write_text_kind(cwd, proposal, root):
    """Write the one line a text kind adds, under the project's config lock, and read it back. Returns
    (action, path) with action "written" or "noop", or raises OSError / RuntimeError naming the failure."""
    kind = proposal["kind"]
    line = ("- " if kind == "focus-hint" else "") + proposal[_LINE_FIELD[kind]]
    with mode_registry.config_lock(cwd, root) as got:
        if not got:
            raise RuntimeError("the project's config lock is held by another writer")
        given = _text_target(cwd, kind, root)
        # a symlinked CLAUDE.md (a supported layout) is written through to its target, so the link survives;
        # the layer is written where it stands, as every other layer write does
        path = os.path.realpath(given) if kind == "claude-md-rule" else given
        with open(path, encoding="utf-8") as fh:
            before = fh.read()
        after = (_with_focus_hint if kind == "focus-hint" else _with_claude_md_rule)(before, line)
        if after is None:
            return "noop", given
        store_core.atomic_write(path, after)
        with open(path, encoding="utf-8") as fh:
            if line not in (l.rstrip() for l in fh.read().splitlines()):
                raise RuntimeError("%s does not hold the added line after the write" % path)
    return "written", given


def apply(cwd, proposal, approval, *, canon_root, session_id, root=None):
    """Record an owner-approved calibration change. The caller applies between reviews: the command
    does not check for a running review, so the advisor runs it only when no review loop is in flight.

    Canon's append path cannot carry a store root (`canon._locate` resolves the ambient store), so a
    `root` naming any other store is refused (`store-override-unsupported`) before anything is written,
    rather than recording the approval in one store and the calibration in another.

    A focus hint joins the Focus hints section of the review settings' layer; a CLAUDE.md rule joins the
    project's CLAUDE.md, left uncommitted for the advisor to land with the Canon entry. Neither file is
    created: with no such file the proposal is refused (`target-missing`), a file that is not UTF-8 text is refused
    (`target-unreadable`), and a cloud session's calibration write is refused (`calibration-write-in-cloud-session`), each
    before anything is written.

    Every apply appends a fresh Canon entry; a failed apply (canon-not-committed or partial) is retried by hand after reading Canon."""
    # axis: a calibration change is written only on the owner's exact yes, with their words, place and date — see bite-proof record wo_a_1718_no-owner-yes
    if not _owner_yes(approval):
        return _result(False, "refused", "no-owner-yes", "no approval with answer 'yes', words, where and an ISO date")
    problem = _proposal_problem(proposal)
    if problem:
        return _result(False, "refused", "proposal-invalid", problem)
    if root is not None and os.path.realpath(os.path.expanduser(root)) != control_plane.store_root():
        return _result(False, "refused", "store-override-unsupported",
                       "Canon's append cannot take a store root; --root %s is not the ambient store" % root)
    # one scrubbed span from the fetch through the calibration write: every git probe below (the lookups, canon._locate,
    # project_config's core.md and project-store resolution) acts on the repository it was given, not GIT_DIR / GIT_WORK_TREE
    with _scrubbed_environ():
        return _apply_bound(cwd, proposal, approval, canon_root, session_id, root)


def _apply_bound(cwd, proposal, approval, canon_root, session_id, root):
    note = _refresh_default_branch(canon_root)  # Canon's write procedure step 1: fetch before every Canon lookup, the binding check included
    # both writes bind to one project: Canon's lookup for canon_root must land where it lands for cwd
    try:
        canon_home = os.path.realpath(definition_doc.resolve_canon(root=canon_root)["path"])
        project_home = os.path.realpath(definition_doc.resolve_canon(root=cwd)["path"])
    except Exception as exc:  # CanonLookupError, UnknownSchemaVersion: both fail closed, as canon._locate does
        return _result(False, "refused", "canon-refused", "canon-lookup-failed: %s" % exc)
    if canon_home != project_home:
        return _result(False, "refused", "canon-root-mismatch",
                       "--canon-root resolves Canon to %s but --cwd resolves it to %s; nothing was written" % (canon_home, project_home))
    if proposal["kind"] in _LINE_FIELD:
        try:
            _text_target(cwd, proposal["kind"], root)
        except store_core.CalibrationWriteRefused as exc:
            return _noted(_result(False, "refused", store_core.CLOUD_REFUSAL_REASON, "%s; nothing was written" % exc), note)
        except TargetUnreadable as exc:
            return _noted(_result(False, "refused", "target-unreadable", "%s; nothing was written" % exc), note)
        except (OSError, subprocess.TimeoutExpired) as exc:
            # axis: a text kind whose home file is missing writes nothing, Canon included — see bite-proof record wo_2190_target-missing
            return _noted(_result(False, "refused", "target-missing", "%s; nothing was written" % exc), note)
    try:
        res = _append_canon(canon_root, session_id, proposal, approval)
        line = res["appended"][0]
    except canon.Refusal as exc:
        reason = "proposal-invalid" if exc.payload["reason"] == "canon-stays-out" else "canon-refused"
        return _noted(_result(False, "refused", reason, "%s: %s" % (exc.payload["reason"], exc.payload["detail"])), note)
    except OSError as exc:
        return _noted(_result(False, "canon-not-committed", "canon-write-failed", "%s: %s" % (type(exc).__name__, exc)), note)
    commit, failure = _commit_canon(res, line)
    if failure:
        return _noted(_result(False, "canon-not-committed", "canon-commit-failed", failure, canonEntry=line), note)
    if proposal["kind"] == "standing-ruling":
        return _noted(_result(True, "applied", canonEntry=line, canonCommit=commit, calibration="canon-only"), note)
    if proposal["kind"] in _LINE_FIELD:
        try:
            action, path = _write_text_kind(cwd, proposal, root)
        except (OSError, RuntimeError, UnicodeError, subprocess.TimeoutExpired) as exc:
            return _noted(_result(False, "partial", "calibration-not-written",
                                  "Canon holds %s (commit %s); the %s write failed: %s" % (line, commit, proposal["kind"], exc),
                                  canonEntry=line, canonCommit=commit), note)
        return _noted(_result(True, "applied", canonEntry=line, canonCommit=commit, calibration=proposal["kind"],
                              set={"action": action, "path": path}), note)
    half = proposal["half"]
    try:
        wrote = project_config.set_item(cwd, "riskAndTrust", {half: proposal["value"]}, root=root)
    except Exception as exc:  # e.g. core_md.VerifyCommandMalformed: Canon is already committed, so name it rather than trace
        return _noted(_result(False, "partial", "calibration-not-written",
                              "Canon holds %s (commit %s); the calibration write raised %s: %s"
                              % (line, commit, type(exc).__name__, exc),
                              canonEntry=line, canonCommit=commit), note)
    # axis: a failed calibration read-back reads partial and unconfirmed, never applied — see bite-proof record wo_a_1718_failed-read-back
    if wrote.get("reason") == project_config.REASON_SET_MISMATCH:  # the write precedes its read-back: the setting may have landed
        return _noted(_result(False, "partial", "calibration-unconfirmed",
                              "Canon holds %s (commit %s); the calibration write may have landed but its read-back failed, "
                              "so the setting must be read back before anyone relies on it" % (line, commit),
                              canonEntry=line, canonCommit=commit, set=wrote), note)
    if wrote.get("action") not in ("written", "noop"):
        return _noted(_result(False, "partial", "calibration-not-written",
                              "Canon holds %s (commit %s); the calibration write returned %s"
                              % (line, commit, wrote.get("reason") or wrote.get("action")),
                              canonEntry=line, canonCommit=commit, set=wrote), note)
    return _noted(_result(True, "applied", canonEntry=line, canonCommit=commit, calibration="risk-and-trust", set=wrote), note)


# --- the tally (I4) ---

def _seats(name):
    """The seats a reviewer row name or finding `reviewer` string names (rule 3)."""
    out = []
    # a merged finding label joins its dimensions with " + " (panel_tally._merge_dims, verification._union_dimensions)
    for part in re.split(r"[,+]", name) if isinstance(name, str) else []:
        part = review_record_session.REVIEWER_ROUND_SUFFIX.sub("", part.strip()).strip().lower()
        tokens = part.split()
        if len(tokens) > 1 and tokens[-1] in _KNOWN:
            part = tokens[-1]
        seat = DIMENSION_SEAT.get(part, part)
        # only the known lens seats are seats: an audit, verifier, or phase label is not one and is not counted
        if seat in _SEATS and seat not in out:
            out.append(seat)
    return out


def _id_ok(value):
    """An identity field that is absent or hashable (a string or int)."""
    return value is None or isinstance(value, (str, int))


def _finding_ok(f):
    """A finding row with a hashable identity and an outcome that is null (undecided) or a known one."""
    if not isinstance(f, dict):
        return False
    key = f.get(session_contract.FINDING_KEY_FIELD) or f.get("id")
    return isinstance(key, (str, int)) and _id_ok(f.get("id")) and _id_ok(f.get(session_contract.FINDING_KEY_FIELD)) and (f.get("outcome") is None or (
        isinstance(f["outcome"], str) and f["outcome"] in review_findings_schema.OUTCOME_SET))


def _merged_member(f):
    """True for a member row folded into a representative; the representative carries the catch."""
    return review_record_session.merged_into(f.get("reason")) is not None


def tally(records, escapes, since, *, until=None, window_days=None):
    """The input is one review record per PR, the latest, as the record writer reads it (`review_record.py read --pr <n>`);
    a PR is dated by that record's `writtenAt`, and counts when that day is on or after the adoption day and inside the window.
    Its reviews are its seat rows that ran; its catches are its fixed findings, one per finding key, credited to every seat the
    finding's rows name, leaving out merged members (the representative carries the catch). A PR supplied more than once reads `incomplete-evidence`.
    An escape item marked `"marker": "false-pr-claim"` is counted in `falsePrClaims`, never in `escapes`; `falsePrClaims` is None wherever `escapes` reads None.
    An escape's optional `kind` (one of ESCAPE_KINDS, what would have caught it) is counted in `escapesByKind`; an escape with no
    kind counts there as `unmeasured`, never as `nothing-reachable`, and a kind outside the list reads malformed."""
    end = _day(until) if until is not None else datetime.datetime.now(datetime.timezone.utc).date()
    left = {"beforeWindow": 0, "afterWindow": 0, "undated": 0, "malformed": 0}
    out = {"since": since, "window": {"from": None, "until": end.isoformat() if end else until},
           "measured": False, "reason": None, "seats": {}, "unattributedCatches": None,
           "escapes": {"missed": None, "seenAndLeft": None}, "escapesByKind": None, "falsePrClaims": None,
           "leftOut": dict.fromkeys(left)}
    if since is None:
        return dict(out, reason="no-adoption-day")
    start = _day(since)
    bad_window = window_days is not None and not (isinstance(window_days, int) and window_days > 0)
    if start is None or end is None or bad_window or end < start:  # an `until` before the adoption day measures nothing
        return dict(out, ok=False, reason="bad-input")
    first = end - datetime.timedelta(days=window_days - 1) if window_days else start
    low = max(first, start)  # nothing dated before the adoption day ever counts (rule 1, 7)
    out.update(measured=first >= start, reason=None if first >= start else "short-of-window")
    out["window"]["from"] = first.isoformat()

    def outside(d):
        # axis: a review event dated before the adoption day never counts — see bite-proof record wo_a_1718_tally-before-adoption
        return "beforeWindow" if d < low else "afterWindow" if d > end else None

    reviews, caught = collections.defaultdict(set), collections.Counter()
    seen_prs = set()
    unattributed, incomplete = 0, False  # incomplete: evidence went missing, so no count is a zero
    for rec in records if isinstance(records, list) else []:
        day = _day(rec.get("writtenAt"), whole=False) if isinstance(rec, dict) else None
        if not isinstance(rec, dict):
            left["malformed"] += 1
            incomplete = True
            continue
        if day is None:
            left["undated"] += 1
            incomplete = True
            continue
        if outside(day):  # a record outside the counting range is left out before its evidence is checked, so it never turns the tally incomplete
            left[outside(day)] += 1
            continue
        # a record that lost its reviewers or findings (a refusal body, a partial read) is unknown coverage, not an empty review;
        # one whose raw reviewer output could not be read (`unreadFiles`) is likewise missing evidence, not a measured zero
        if (rec.get("ok") is False or rec.get("unreadFiles") not in (None, [])
                or not isinstance(rec.get("reviewers"), list) or not rec["reviewers"]
                or not isinstance(rec.get("findings"), list)):
            left["malformed"] += 1
            incomplete = True
            continue
        pr, session = rec.get("pr"), rec.get("sessionId")  # the review's identity: without both, reviews and catches collapse together
        if not (isinstance(pr, (str, int)) and not isinstance(pr, bool) and pr != ""
                and isinstance(session, str) and session.strip()):
            left["malformed"] += 1
            incomplete = True
            continue
        if str(pr) in seen_prs:  # the caller did not reduce to one record per PR: a retried or duplicated record is never a second catch
            left["malformed"] += 1
            incomplete = True
            continue
        seen_prs.add(str(pr))
        if any(not (isinstance(r, dict) and r.get("ran") in review_record.RAN_STATES
                    and isinstance(r.get("name"), str) and r["name"].strip())
               for r in rec["reviewers"]) or any(not _finding_ok(f) for f in rec["findings"]):
            left["malformed"] += 1  # a damaged row is missing evidence, not a review that caught nothing
            incomplete = True
            continue
        for row in rec["reviewers"]:
            if row["ran"] != review_record.RAN_NOT_RUN:
                for seat in _seats(row.get("name")):
                    reviews[seat].add(str(pr))
        fixed = {}  # the PR's catches, one per findingKey
        for f in rec["findings"]:
            if f.get("outcome") == _FIXED and not _merged_member(f):
                # axis: a finding with no findingKey is keyed by its id, so distinct keyless findings stay distinct — see bite-proof record wo_a_1718_keyless-id
                # axis: rows sharing a findingKey are one catch crediting the union of their seats, so row order never changes the tally
                fixed.setdefault(f.get(session_contract.FINDING_KEY_FIELD) or f.get("id"), set()).update(_seats(f.get("reviewer")))
        for seats in fixed.values():
            unattributed += not seats
            caught.update(seats)
    counts, claims = {"missed": 0, "seenAndLeft": 0}, 0
    by_kind = dict.fromkeys(ESCAPE_KINDS + (UNMEASURED,), 0)
    for esc in escapes if isinstance(escapes, list) else []:
        day = _day(esc.get("reviewedAt")) if isinstance(esc, dict) else None
        call = esc.get("call") if isinstance(esc, dict) else None
        label = {"missed": "missed", "seen-and-left": "seenAndLeft"}.get(call) if isinstance(call, str) else None
        marked = isinstance(esc, dict) and esc.get("marker") == FALSE_CLAIM_MARKER
        if isinstance(esc, dict) and "marker" in esc and not marked:
            # axis: a marker other than the false-claim marker reads malformed, never counted — see bite-proof record wo_revisit_unknown-marker
            left["malformed"] += 1
            incomplete = True
        elif day is None and isinstance(esc, dict):
            left["undated"] += 1
            incomplete = True
        elif label is None or esc.get("kind") not in ESCAPE_KINDS + (None,):
            # axis: a kind outside the eight reads malformed, never counted — see bite-proof record wo_2190_unknown-kind
            left["malformed"] += 1
            incomplete = True
        elif outside(day):
            left[outside(day)] += 1
        elif marked:
            # axis: a false PR claim never adds to the missed or seen-and-left counts — see bite-proof record wo_revisit_claim-apart
            claims += 1
        else:
            counts[label] += 1
            # axis: an escape logged with no kind counts as unmeasured, never as nothing reachable — see bite-proof record wo_2190_kind-missing
            by_kind[esc.get("kind") or UNMEASURED] += 1
    if incomplete:  # missing evidence reads unmeasured, never zero (owner-decisions.md, the gardening pass)
        # axis: an unmeasured tally leaves the false-claim count None, never zero — see bite-proof record wo_revisit_claims-unmeasured
        return dict(out, measured=False, reason=out["reason"] or "incomplete-evidence", leftOut=left)
    out.update(seats={s: {"reviews": len(reviews[s]), "caught": caught[s]} for s in sorted(set(reviews) | set(caught))},
               unattributedCatches=unattributed, escapes=counts, escapesByKind=by_kind, falsePrClaims=claims, leftOut=left)
    return out


# --- the seating numbers ---

def _measured(value):
    """The one chokepoint for every number the seating record shows: the number itself when it is a finite
    int or float of zero or more, else "unmeasured". Anything not given is never shown as 0."""
    # axis: a bool is not a number — see bite-proof record wo_revisit_measured-bool
    if isinstance(value, bool):
        return UNMEASURED
    # axis: a huge integer is compared as an integer, never converted to a float — see bite-proof record wo_revisit_measured-huge-int
    if isinstance(value, int):
        return value if value >= 0 else UNMEASURED
    # axis: a missing or null number reads unmeasured, never zero — see bite-proof record wo_revisit_measured-none
    # axis: a negative or non-numeric value reads unmeasured — see bite-proof record wo_revisit_measured-range
    if not isinstance(value, float) or not math.isfinite(value) or value < 0:
        return UNMEASURED
    return value


def seating(row):
    """The numbers the seating check reads, for the security and premortem seats: each seat's finding outcomes by
    outcome, its tokens and its minutes. `row` is a dict keyed by seat name; every number passes through `_measured`,
    so a number the row does not give reads "unmeasured" and is listed in `unmeasured`, never shown as 0."""
    if not isinstance(row, dict):
        return _result(False, "refused", "bad-input", "the seating row is a JSON object keyed by seat name",
                       seats=None, unmeasured=None)
    seats, unmeasured = {}, []
    for seat in SEATING_SEATS:
        given = row.get(seat) if isinstance(row.get(seat), dict) else {}
        outcomes = given.get("outcomes") if isinstance(given.get("outcomes"), dict) else {}
        shown = {"outcomes": {o: _measured(outcomes.get(o)) for o in review_findings_schema.OUTCOMES},
                 "tokens": _measured(given.get("tokens")), "minutes": _measured(given.get("minutes"))}
        seats[seat] = shown
        unmeasured += ["%s.outcomes.%s" % (seat, o) for o, n in shown["outcomes"].items() if n == UNMEASURED]
        unmeasured += ["%s.%s" % (seat, k) for k in ("tokens", "minutes") if shown[k] == UNMEASURED]
    return {"ok": True, "seats": seats, "unmeasured": sorted(unmeasured)}


# --- the CLI ---

def _load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _parser():
    p = argparse.ArgumentParser(prog="review_learning.py")
    sub = p.add_subparsers(dest="verb", required=True)
    for name in ("adopt", "since", "apply", "tally"):
        s = sub.add_parser(name)
        s.add_argument("--root")
        if name != "tally":
            s.add_argument("--cwd", required=True)
    sub.add_parser("seating").add_argument("--row", required=True)
    sub.choices["adopt"].add_argument("--date", required=True)
    for f in ("canon-root", "session-id", "proposal", "approval"):
        sub.choices["apply"].add_argument("--" + f, required=True)
    t = sub.choices["tally"]
    t.add_argument("--records", required=True)
    t.add_argument("--escapes", required=True)
    t.add_argument("--cwd")
    t.add_argument("--since")
    t.add_argument("--until")
    t.add_argument("--window-days", type=int)
    return p


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] not in ("adopt", "since", "apply", "tally", "seating"):
        argv = argv[1:]  # a full sys.argv, program name first
    a = _parser().parse_args(argv)
    if a.verb == "adopt":
        out = record_adoption_day(a.cwd, a.date, a.root)
    elif a.verb == "since":
        got = adoption_day(a.cwd, a.root)
        out = _result(got["reason"] != "malformed", None, got["reason"], None, since=got["since"])
    elif a.verb == "apply":
        out = apply(a.cwd, _load(a.proposal), _load(a.approval), canon_root=a.canon_root,
                    session_id=a.session_id, root=a.root)
    elif a.verb == "seating":
        out = seating(_load(a.row))
    else:
        records, escapes = _load(a.records), _load(a.escapes)
        if not isinstance(records, list) or not isinstance(escapes, list) or bool(a.since) == bool(a.cwd):
            out = _result(False, "refused", "bad-input", "--records and --escapes are JSON lists; give --since or --cwd")
        else:
            out = tally(records, escapes, a.since or adoption_day(a.cwd, a.root)["since"],
                        until=a.until, window_days=a.window_days)
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    return 0 if out.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(main())
