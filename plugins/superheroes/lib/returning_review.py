#!/usr/bin/env python3
"""The returning-review decider: what a returning pull request's new review session reads. stdlib and sibling lib modules only.

When a pull request comes back for review (after a send-back, a fix leg, a catch-up with its base or a
hand fix), the new session reads only what changed since the last reviewed commit, and runs a full panel
only when that change is over the countable-lines bar or touches a risk area the pull request had not
touched. A change whose risk is unclear counts as touching one, unless the pull request's earlier review
also treated its risk as unclear. The decision is a pure function of the pull request's earlier review
record and the repository: it starts no session, and writes nothing except the optional delta file.

The rule, in order; the first step that applies answers ``full``, otherwise the answer is ``changed``:
  1. No earlier record, or one that is not a usable ``ok`` record with a full-sha final commit: full.
  2. The final commit of the earlier review is not an ancestor of the head: full.
  3. No reviewer row of the earlier record covers that final commit: full.
  4. The earlier record's ``status`` is not ``reviewed`` or ``awaits-owner``, or it carries ``abandoned``
     (the earlier review did not finish): full. One gap is let through to step 5: a record whose only gap is
     CI pending on its final commit (it is normally written before CI finishes). It then counts as finished
     only when a CI reader (``ci_state``) says CI has since passed on that commit, or on a head with no
     changed file; otherwise full.
  5. The changed files are those whose section's own change differs between ``base...lastReviewed`` and
     ``base...head`` (proven copies left out; ``index`` lines and hunk-header line numbers are not part of a
     file's own change); a diff git cannot produce is full; no changed file is changed, with nothing read.
  6. The incremental diff is ``lastReviewed head`` (two-dot) over the changed files; the files a catch-up
     with the base also changed are named in ``overlap``, which can only raise the count.
  7. The countable lines of the incremental diff, counting every file the counter could not settle, are over
     the bar: full.
  8. The risk of the changed files against the earlier review's risk basis: an earlier basis that cannot be
     read, an area the earlier basis did not touch, or an unclear risk the earlier basis did not share: full.
  9. Otherwise changed.

CLI:
  returning_review.py decide --repo-root DIR --base SHA --earlier-record FILE [--proof FILE] [--head SHA]
                             [--delta-out FILE]
prints the result without ``deltaDiff`` as one JSON object; ``--delta-out`` writes the raw incremental diff
to FILE. Exit 0 for both answers, 2 on a usage error."""
import argparse
import json
import os
import re
import subprocess
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import countable_lines  # noqa: E402
import lane_call  # noqa: E402
import review_diff_bytes  # noqa: E402

GIT_TIMEOUT = 120

READ_FULL = "full"
READ_CHANGED = "changed"

WHY_NO_EARLIER = "no-earlier-record"
WHY_EARLIER_UNUSABLE = "earlier-record-unusable"
WHY_NOT_ANCESTOR = "last-reviewed-not-ancestor"
WHY_NOT_COVERED = "earlier-review-did-not-cover"
WHY_INCOMPLETE = "earlier-review-incomplete"
WHY_DIFF_UNREADABLE = "diff-unreadable"
WHY_OVER_BAR = "over-bar"
WHY_UNSETTLED = "unsettled-counted"
WHY_NEW_AREA = "new-risk-area"
WHY_RISK_UNCLEAR = "risk-unclear"
WHY_BASIS_UNUSABLE = "earlier-basis-unusable"
WHY_OVERLAP = "catch-up-overlap"
WHY_UNCLEAR_AS_BEFORE = "unclear-as-before"
WHY_CHANGED_ONLY = "changed-only"
WHY_CI_SETTLED = "ci-settled-since"
WHY_TOKENS = (WHY_NO_EARLIER, WHY_EARLIER_UNUSABLE, WHY_NOT_ANCESTOR, WHY_NOT_COVERED, WHY_INCOMPLETE,
              WHY_DIFF_UNREADABLE, WHY_OVER_BAR, WHY_UNSETTLED, WHY_NEW_AREA, WHY_RISK_UNCLEAR, WHY_BASIS_UNUSABLE, WHY_OVERLAP,
              WHY_UNCLEAR_AS_BEFORE, WHY_CHANGED_ONLY, WHY_CI_SETTLED)

_SHA_RE = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})")
_UNCLEAR_PREFIXES = (lane_call.WHY_NOT_SET, lane_call.WHY_UNMATCHABLE, lane_call.WHY_NO_PATHS)
_MISSING_RECORD = "review-record-missing"
_FINISHED_STATUSES = ("reviewed", "awaits-owner")
# Axis: a user's submodule settings (diff.ignoreSubmodules, diff.submodule) never hide or reshape a gitlink update.
_DIFF_ARGS = (*review_diff_bytes.REVIEW_DIFF_ARGS, "--ignore-submodules=none", "--submodule=short")


def _is_sha(value):
    return isinstance(value, str) and _SHA_RE.fullmatch(value) is not None


def _production_git(repo_root):
    """The git runner for ``repo_root``: ``run(argv) -> (returncode, stdout_text)`` over ``git -C repo_root``,
    literal pathspecs, the ambient routing variables scrubbed. A git that cannot run or times out gives
    ``(-1, "")``."""
    def run(argv):
        env = countable_lines._git_env()
        env["GIT_LITERAL_PATHSPECS"] = "1"
        try:
            proc = subprocess.run(
                ["git", "-C", os.fspath(repo_root), "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=",
                 *argv],
                capture_output=True, timeout=GIT_TIMEOUT, env=env,
            )
        except (OSError, subprocess.SubprocessError, ValueError, TypeError):
            return -1, ""
        return proc.returncode, proc.stdout.decode("utf-8", "surrogateescape")
    return run


def _result(last_reviewed=None):
    return {
        "read": READ_FULL,
        "lastReviewed": last_reviewed,
        "countable": None,
        "bar": countable_lines.COUNTABLE_LINES_BAR,
        "unsettled": [],
        "changedFiles": [],
        "newAreas": [],
        "overlap": [],
        "why": [],
        "deltaDiff": "",
    }


def _line(token, text):
    return "%s: %s" % (token, text)


def _full(result, token, text):
    result["read"] = READ_FULL
    result["why"].append(_line(token, text))
    return result


def _changed(result):
    result["read"] = READ_CHANGED
    result["why"].append(_line(WHY_CHANGED_ONLY, "nothing in the change since the last reviewed commit needs a full panel"))
    return result


def _proven_files(proven):
    files = set()
    if isinstance(proven, str):
        return {proven}
    try:
        for entry in proven:
            if isinstance(entry, str):
                files.add(entry)
            elif isinstance(entry, dict) and isinstance(entry.get("file"), str):
                files.add(entry["file"])
    except TypeError:
        return set()
    return files


def _sections_by_file(diff_text, sources=None):
    """``{file: concatenated section text}`` of ``diff_text``, or None when a section's header cannot be read.
    When ``sources`` is a dict, it gains ``{file: {old paths}}`` for every renamed or copied section."""
    out = {}
    for section in countable_lines.parse_sections(diff_text):
        if section["unreadable"]:
            return None
        out[section["file"]] = out.get(section["file"], "") + section["text"]
        old = section.get("oldFile")
        if sources is not None and old and old != section["file"]:
            sources.setdefault(section["file"], set()).add(old)
    return out


_INDEX_LINE = "index "
_BINARY_MARKERS = ("Binary files ", "GIT binary patch")
_HUNK_HEADER_RE = re.compile(r"@@ -\S+ \+\S+ @@")


def _own_change(section_text):
    """``section_text`` as the change the pull request itself made to the file: without its ``index`` lines and with
    each hunk header cut to ``@@`` and whatever follows its closing ``@@``, so the blob ids and the line numbers a
    moved base shifts are no part of it. Every other line (the ``diff --git``, mode, rename, copy, binary and
    ``---``/``+++`` lines and each hunk body line) is kept exactly."""
    lines = section_text.splitlines(keepends=True)
    # axis: a binary section has no hunk text to tell versions apart, so its index line (the blob ids) is its content identity and is kept — see bite-proof record c1l11d_wo_c_fold
    binary = any(line.startswith(_BINARY_MARKERS) for line in lines)
    out = []
    for line in lines:
        if line.startswith(_INDEX_LINE) and not binary:
            continue
        hunk = _HUNK_HEADER_RE.match(line)
        out.append("@@" + line[hunk.end():] if hunk else line)
    return "".join(out)


def _covers_final_commit(earlier):
    reviewers = earlier.get("reviewers")
    if not isinstance(reviewers, list):
        return False
    return any(isinstance(row, dict) and row.get("coversFinalCommit") is True for row in reviewers)


def _basis_areas(basis):
    """The set of area names an earlier risk basis touched, or None when the basis cannot be read."""
    if not isinstance(basis, dict) or basis.get("source") == "unavailable" or "touchedCount" in basis:
        return None
    touched = basis.get("touched")
    if not isinstance(touched, list):
        return None
    names = set()
    for hit in touched:
        if not isinstance(hit, dict) or not isinstance(hit.get("name"), str):
            return None
        names.add(hit["name"])
    return names


def _is_unclear(why_lines):
    if not isinstance(why_lines, list):
        return False
    return any(isinstance(w, str) and w.startswith(_UNCLEAR_PREFIXES) for w in why_lines)


def _catch_up_files(run, base, last_reviewed):
    """The files the base changed since it forked from the last reviewed commit, or None when git cannot say."""
    code, text = run(["merge-base", base, last_reviewed])
    fork = text.strip()
    if code != 0 or not _is_sha(fork):
        return None
    code, text = run(["diff", "--name-only", "--no-renames", "--no-ext-diff", "-z", fork, base])
    if code != 0:
        return None
    return {name for name in text.split("\0") if name}


_CI_PENDING_PREFIX = "CI is pending on "
_CI_GREEN = "green"


def _ci_pending_only(earlier, last_reviewed):
    """True when ``earlier`` did not finish for one reason only: CI was pending on its final commit when it was
    written. It is a ``not-reviewed`` record that is not abandoned, whose ``ci`` is pending on ``last_reviewed``,
    and whose ``whatIsMissing`` is the one line the record writer words for that."""
    import review_record
    # axis: only the writer's not-reviewed status, never abandoned, is let through unfinished — see bite-proof record c1l11d_wo_c_fold
    if not review_record.unfinished(earlier.get("status")) or "abandoned" in earlier:
        return False
    ci = earlier.get("ci")
    if not (isinstance(ci, dict) and ci.get("state") == "pending" and ci.get("sha") == last_reviewed):
        return False
    missing = earlier.get("whatIsMissing")
    if not (isinstance(missing, list) and len(missing) == 1 and isinstance(missing[0], str)):
        return False
    line = _CI_PENDING_PREFIX + last_reviewed[:7]
    return missing[0] == line or missing[0].startswith(line + " ")


def _ci_read(ci_state, sha):
    """What the CI reader says of ``sha``: its state, or None when there is no reader, it raises, or it answers
    anything but a string."""
    if not callable(ci_state):
        return None
    try:
        state = ci_state(sha)
    except Exception:  # noqa: BLE001 — a reader that fails is a CI nobody read
        return None
    return state if isinstance(state, str) else None


def _ci_settled(ci_state, last_reviewed, head, files):
    """``(True, why text)`` when CI has since passed on ``last_reviewed``, or on ``head`` that has no changed file
    (it was reached from ``last_reviewed`` by catch-up merges only); otherwise ``(False, text)`` naming the CI state
    read, which makes the decision full."""
    state = _ci_read(ci_state, last_reviewed)
    # Axis: only CI "green" settles an earlier record written with CI pending; red, pending, unreadable and no reader do not — see bite-proof record c1l11d_wo_c_fold
    if state == _CI_GREEN:
        return True, "CI has since passed on the last reviewed commit %s" % last_reviewed[:7]
    read = [state]
    # Axis: CI green on the head settles an earlier record only when the head has no changed file — see bite-proof record c1l11d_wo_c_fold
    if not files:
        head_state = _ci_read(ci_state, head)
        if head_state == _CI_GREEN:
            return True, "CI has since passed on the head %s, reached from the last reviewed commit by catch-up merges only" % head[:7]
        read.append(head_state)
    return False, ("the earlier review was written with CI pending on %s and CI has not since passed (CI read: %s)"
                   % (last_reviewed[:7], ", ".join(s if s is not None else "unreadable" for s in read)))


def decide(repo_root, base, head, earlier, proven=(), git=None, ci_state=None):
    """What a returning review reads: ``{"read": "full" | "changed", ...}``. Never raises: every fault reads
    ``full`` with a reason in ``why``. ``git`` is a test seam, ``git(argv) -> (returncode, stdout_text)`` with
    ``argv`` the arguments after ``git -C <repo_root>``; production leaves it None. ``ci_state(sha) -> str | None``
    reads CI's state on a commit; only ``"green"`` settles an earlier record written with CI pending (step 4), and
    no reader, a reader that raises or any other answer leaves that record unfinished."""
    result = _result()
    try:
        return _decide(result, repo_root, base, head, earlier, proven, git, ci_state=ci_state)
    except Exception as exc:  # total: a fault nobody foresaw is still a full read
        result["read"] = READ_FULL
        result["why"].append(_line(WHY_DIFF_UNREADABLE, "the decision failed on %s: %s" % (type(exc).__name__, exc)))
        return result


def _decide(result, repo_root, base, head, earlier, proven, git, ci_state=None):
    # 1. the earlier record
    if earlier is None or (isinstance(earlier, dict) and earlier.get("ok") is False
                           and earlier.get("reason") == _MISSING_RECORD):
        return _full(result, WHY_NO_EARLIER, "the pull request has no earlier review record")
    final = earlier.get("finalCommit") if isinstance(earlier, dict) else None
    last_reviewed = final.get("sha") if isinstance(final, dict) else None
    if not isinstance(earlier, dict) or earlier.get("ok") is not True or not _is_sha(last_reviewed):
        return _full(result, WHY_EARLIER_UNUSABLE, "the earlier review record is not an ok record with a final commit")
    # Axis: an abandoned session's record never counts as reviewed coverage, whatever its final commit and reviewers say.
    if earlier.get("abandoned"):
        return _full(result, WHY_EARLIER_UNUSABLE, "the earlier review session was abandoned, so its record covers nothing")
    result["lastReviewed"] = last_reviewed
    run = git if git is not None else _production_git(repo_root)

    # 2. the last reviewed commit is part of this head's history
    ancestor = False
    if _is_sha(head):
        code, _ = run(["merge-base", "--is-ancestor", last_reviewed, head])
        # Axis: a rewritten history reads full; only a last reviewed commit that git proves an ancestor is built on.
        ancestor = code == 0
    if not ancestor:
        return _full(result, WHY_NOT_ANCESTOR, "the last reviewed commit %s is not an ancestor of the head" % last_reviewed)

    # 3. the earlier session reviewed that commit
    if not _covers_final_commit(earlier):
        return _full(result, WHY_NOT_COVERED, "no reviewer of the earlier record covers its final commit")

    # 4. the earlier session finished
    # Axis: an earlier review that was abandoned or never reviewed reads full — see bite-proof record c1l11b_wo_d1_returning_session
    ci_pending = False
    if earlier.get("status") not in _FINISHED_STATUSES or "abandoned" in earlier:
        # Axis: an earlier record is let through unfinished only for CI pending on its final commit and nothing else — see bite-proof record c1l11d_wo_c_fold
        ci_pending = _ci_pending_only(earlier, last_reviewed)
        if not ci_pending:
            return _full(result, WHY_INCOMPLETE, "the earlier review did not finish (status %r%s)"
                         % (earlier.get("status"), ", abandoned" if "abandoned" in earlier else ""))

    # 5. the changed files
    if not _is_sha(base):
        return _full(result, WHY_DIFF_UNREADABLE, "the base is not a full commit sha")
    diff_args = list(_DIFF_ARGS)
    code_a, reviewed_text = run(["diff", *diff_args, "%s...%s" % (base, last_reviewed)])
    code_b, current_text = run(["diff", *diff_args, "%s...%s" % (base, head)])
    sources = {}
    reviewed = _sections_by_file(reviewed_text, sources) if code_a == 0 else None
    current = _sections_by_file(current_text, sources) if code_b == 0 else None
    if reviewed is None or current is None:
        return _full(result, WHY_DIFF_UNREADABLE, "git could not produce the diff of the earlier review or of the head against the base")
    proven_files = _proven_files(proven)
    # Axis: a file is changed when its own change differs, never for an index line or a hunk header's line numbers — see bite-proof record c1l11d_wo_c_fold
    files = sorted(f for f in set(reviewed) | set(current)
                   if _own_change(reviewed.get(f, "")) != _own_change(current.get(f, "")))
    # Axis: a proven copy is never a changed file, so it is neither read, counted nor matched against a risk area.
    files = [f for f in files if f not in proven_files]
    if ci_pending:
        settled, text = _ci_settled(ci_state, last_reviewed, head, files)
        if not settled:
            return _full(result, WHY_INCOMPLETE, text)
        result["why"].append(_line(WHY_CI_SETTLED, text))
    result["changedFiles"] = files
    if not files:
        result["countable"] = 0
        return _changed(result)

    # 5. the incremental diff, and the files a catch-up changed too
    # Axis: the incremental diff runs from the last reviewed commit to the head, never over the whole section of the change.
    # Axis: a rename's source path is part of the surface, so the diff shows the move and a risk area on the source still matches.
    # Axis: a proven copy is never passed on, whether it arrives as a changed file or as a rename's source path.
    paths = sorted(p for p in set(files).union(*(sources.get(f, set()) for f in files)) if p not in proven_files)
    code, delta = run(["diff", *diff_args, last_reviewed, head, "--", *paths])
    if code != 0:
        return _full(result, WHY_DIFF_UNREADABLE, "git could not produce the diff since the last reviewed commit")
    result["deltaDiff"] = delta
    catch_up = _catch_up_files(run, base, last_reviewed)
    if catch_up is None:
        return _full(result, WHY_DIFF_UNREADABLE, "git could not name the files the base changed since the last reviewed commit")
    result["overlap"] = [f for f in files if f in catch_up]
    if result["overlap"]:
        result["why"].append(_line(WHY_OVERLAP, "the base changed %d of these files too, so their counts may include base content: %s"
                                   % (len(result["overlap"]), ", ".join(result["overlap"][:3]))))

    # 6. the countable lines
    counted = countable_lines.count(delta, repo_root, proven, head=head)
    result["unsettled"] = list(counted["unsettled"])
    countable = counted["countable"]
    left = [row for row in counted["files"] if row["why"] == "unsettled"]
    if result["unsettled"]:
        # Axis: a binary section has no line count (git reports none), so it is never counted as zero lines.
        if any(item.get("reason") == "binary" for item in result["unsettled"]):
            return _full(result, WHY_DIFF_UNREADABLE, "a changed file is binary to git, so its lines cannot be counted")
        countable += sum(row["lines"] for row in left)
        result["why"].append(_line(WHY_UNSETTLED, "%d file(s) the counter could not settle are counted by their lines" % len(result["unsettled"])))
    result["countable"] = countable
    if countable > countable_lines.COUNTABLE_LINES_BAR:
        return _full(result, WHY_OVER_BAR, "%d countable lines since the last reviewed commit is over the bar of %d"
                     % (countable, countable_lines.COUNTABLE_LINES_BAR))

    # 7. the risk
    delta_basis = lane_call.call(repo_root, list(paths))
    earlier_areas = _basis_areas(earlier.get("laneBasis"))
    if earlier_areas is None:
        return _full(result, WHY_BASIS_UNUSABLE, "the earlier review's risk basis cannot be read")
    delta_areas = {hit["name"] for hit in delta_basis["touched"]}
    # Axis: an area the earlier review's basis did not touch reads full.
    result["newAreas"] = sorted(delta_areas - earlier_areas)
    if result["newAreas"]:
        return _full(result, WHY_NEW_AREA, "the change touches risk area(s) the earlier review did not: %s" % ", ".join(result["newAreas"]))
    if _is_unclear(delta_basis["why"]):
        # Axis: an unclear risk reads full, unless the earlier review's risk was unclear as well.
        if not _is_unclear(earlier["laneBasis"].get("why")):
            return _full(result, WHY_RISK_UNCLEAR, "the risk of the change is unclear and the earlier review's was clear")
        result["why"].append(_line(WHY_UNCLEAR_AS_BEFORE, "the risk of the change is unclear, as the earlier review's was"))

    # 8. nothing needs a full panel
    return _changed(result)


# --------------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------------

def _usage_error(message):
    sys.stderr.write("returning_review: %s\n" % message)
    return 2


def _read_earlier(path):
    """The parsed earlier record, or an ``ok: false`` object when the file is missing or not JSON."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.loads(handle.read())
    except (OSError, ValueError, UnicodeError):
        return {"ok": False, "reason": "earlier-record-unreadable"}


def production_ci_state(repo_root):
    """The CI reader for ``decide(ci_state=...)`` over ``repo_root``: ``sha -> CI's state on that commit``
    (``"green"``, ``"red"``, ``"pending"``, ``"none"``), read as the review record writer reads it. Any fault
    answers None. ``review_record`` is imported here because it imports this module."""
    def read(sha):
        try:
            import review_record
            rd = review_record._readers(None)
            return review_record._ci(rd, rd["repo_name"](repo_root), sha, repo_root)["state"]
        except Exception:  # noqa: BLE001 — a CI nobody could read is no CI answer
            return None
    return read


def _cli_proven(repo_root, base, head, proof):
    code, current = _production_git(repo_root)(
        ["diff", *_DIFF_ARGS, "%s...%s" % (base, head)])
    if code != 0:
        return []
    proven, _ = countable_lines.proven_copies(current, repo_root, proof, head=head)
    return proven


def _decide_cli(args):
    """Run ``decide`` for the CLI. It passes no CI reader, so an earlier record written with CI pending reads full."""
    repo_root = args.repo_root
    if not os.path.isdir(repo_root):
        return _usage_error("--repo-root is not a directory: %s" % repo_root)
    head = args.head
    if head is None:
        code, text = _production_git(repo_root)(["rev-parse", "HEAD"])
        head = text.strip()
        if code != 0 or not head:
            return _usage_error("cannot read HEAD of %s" % repo_root)
    proven = []
    if args.proof is not None:
        proof, fault = countable_lines.load_proof(args.proof)
        if fault is not None:
            return _usage_error("--proof is not a usable copy proof: %s" % fault)
        proven = _cli_proven(repo_root, args.base, head, proof)
    result = decide(repo_root, args.base, head, _read_earlier(args.earlier_record), proven)
    delta = result.pop("deltaDiff")
    if args.delta_out is not None:
        try:
            with open(args.delta_out, "wb") as handle:
                handle.write(delta.encode("utf-8", "surrogateescape"))
        except OSError as exc:
            return _usage_error("cannot write --delta-out: %s" % exc)
    sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(prog="returning_review")
    sub = ap.add_subparsers(dest="cmd", required=True)
    dp = sub.add_parser("decide")
    dp.add_argument("--repo-root", required=True)
    dp.add_argument("--base", required=True)
    dp.add_argument("--earlier-record", required=True)
    dp.add_argument("--proof", default=None)
    dp.add_argument("--head", default=None)
    dp.add_argument("--delta-out", default=None)
    args = ap.parse_args(argv)
    return _decide_cli(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
