#!/usr/bin/env python3
"""The head-coverage check: whether the commit a review certified covers the pull request's current head. stdlib and
sibling lib modules only.

A review record certifies one commit, ``finalCommit.sha`` (X). This check decides whether X covers the pull request's
head, and the advisor's vet runs it for every pull request. It answers ``proven`` (git itself shows the pull
request's own change at the head equals the reviewed change at X), ``judgement`` (the vet must read the listed hunks:
every remaining difference is prose or comment and blank lines, and every new commit is the builder's) or
``needs-review`` (a returning-round review of the listed files is owed). It reads the repository and writes nothing.
A second, pure function, ``outcome``, turns that answer and CI on the head into the vet's outcome and the merge
sheet's action.

The rule, in order; the first step that applies answers:
  1. The record is not a dict, is not ``ok``, is abandoned, or has no full-sha ``finalCommit.sha``: needs-review
     (``record-unusable``).
  2. The head is X: proven (``same-commit``).
  3. The base or the head is not a full commit sha: needs-review (``input-invalid``).
  4. The changed files (``returning_review.changed_files``: the files whose own change differs between
     ``base...X`` and ``base...head``) cannot be produced by git: needs-review (``diff-unreadable``).
  5. A changed file is still proven when a clean three-way merge of X's blob, the fork blob and the base blob equals
     the head blob byte for byte (``reconstructed``). This proof is the check's own; the returning-review decider
     keeps its stricter rule.
  6. A changed file is dropped when a copy-proof entry for it is re-validated by git at the head (its file is in the
     ``base...head`` change, bound to the head blob, and the head blob's bytes hash to the entry's sha256;
     ``review_record.revalidated_copies``). An entry is never trusted for its own word; the entries relied on are
     listed in ``copies``.
  7. No changed file is left: proven (``own-change-unchanged``, or ``proven-copies`` when a copy was relied on).
  8. Otherwise the remaining files are read as ``git diff X head`` and the new commits as
     ``git rev-list head --not X base``. A file qualifies when its path ends ``.md``, ``.markdown``, ``.txt`` or
     ``.rst``, or when every added and removed body line is blank or begins (stripped) with the file's line-comment
     marker; a binary or unreadable section, a mode change, a rename or copy, a file the diff does not show and any
     other extension never qualify. A commit whose author email is not the builder's (the ``builder_author``
     given, else the author email of X), authors git cannot read, or no new commit to vouch for the difference:
     needs-review (``other-author``). All files qualify and every author is the builder: judgement
     (``prose-or-comments``), with the hunks to read. Otherwise needs-review (``behaviour-change``).
  9. Any exception: needs-review (``check-failed``).
Every failure to read anything answers needs-review. The check never raises.

``outcome(answer, ci, judged_clear, sheet, sheet_commit, head)`` is covered when the answer is proven, or judgement
with ``judged_clear``. CI red is NOT-READY (``ci-red``, no review owed: the fix arrives as a new commit); not covered
is NOT-READY (``needs-review``, or ``judged-meaningful`` for an uncleared judgement) with a returning review owed;
covered with CI pending or none is WAIT (``ci-not-green``); otherwise READY (``covered``). The sheet action is
``none`` with no sheet; a held sheet is ``republish-unsigned`` when READY, else ``keep``; a live sheet is
``take-down`` when NOT-READY, ``republish-carried`` when READY on a head other than the sheet's commit, else
``keep``.

CLI:
  head_coverage.py check --repo-root DIR --base SHA --record FILE --head SHA [--proof FILE] [--builder-author EMAIL]
  head_coverage.py outcome --answer A --ci C [--judged-clear] [--sheet none|live|held] [--sheet-commit SHA]
                           [--head SHA]
prints the result as one JSON object. Exit 0 for every answer, 2 on a usage error (an unreadable record or proof
file, a bad value)."""
import argparse
import json
import os
import re
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import countable_lines  # noqa: E402
import returning_review  # noqa: E402
import review_record  # noqa: E402

PROVEN = "proven"
JUDGEMENT = "judgement"
NEEDS_REVIEW = "needs-review"
ANSWERS = (PROVEN, JUDGEMENT, NEEDS_REVIEW)

WHY_RECORD_UNUSABLE = "record-unusable"
WHY_SAME_COMMIT = "same-commit"
WHY_INPUT_INVALID = "input-invalid"
WHY_DIFF_UNREADABLE = "diff-unreadable"
WHY_OWN_CHANGE_UNCHANGED = "own-change-unchanged"
WHY_PROVEN_COPIES = "proven-copies"
WHY_PROSE_OR_COMMENTS = "prose-or-comments"
WHY_OTHER_AUTHOR = "other-author"
WHY_BEHAVIOUR_CHANGE = "behaviour-change"
WHY_CHECK_FAILED = "check-failed"
WHY_TOKENS = (WHY_RECORD_UNUSABLE, WHY_SAME_COMMIT, WHY_INPUT_INVALID, WHY_DIFF_UNREADABLE, WHY_OWN_CHANGE_UNCHANGED,
              WHY_PROVEN_COPIES, WHY_PROSE_OR_COMMENTS, WHY_OTHER_AUTHOR, WHY_BEHAVIOUR_CHANGE, WHY_CHECK_FAILED)

CI_STATES = ("green", "pending", "red", "none")
SHEETS = ("none", "live", "held")
READY = "READY"
WAIT = "WAIT"
NOT_READY = "NOT-READY"

_PROSE_SUFFIXES = (".md", ".markdown", ".txt", ".rst")
_HASH_SUFFIXES = (".py", ".sh", ".bash", ".yml", ".yaml", ".toml", ".cfg", ".ini")
_SLASH_SUFFIXES = (".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".c", ".h", ".cc", ".cpp",
                   ".cs", ".swift", ".kt")
# A line that begins with a comment marker yet is read by a tool as an instruction is no comment.
_DIRECTIVE_PREFIXES = ("#!", "//go:", "// +build", "//+build")
_REGULAR_MODES = ("100644", "100755")
_MODE_LINES = ("old mode ", "new mode ")
_FILE_MODE_LINES = ("new file mode ", "deleted file mode ")
_HUNK_LINE_RE = re.compile(r"@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")


def _plain(value):
    return value if isinstance(value, str) else None


def _line(token, text):
    return "%s: %s" % (token, text)


def _result(base, head, certified=None):
    return {
        "answer": NEEDS_REVIEW,
        "why": [],
        "certified": certified,
        "head": _plain(head),
        "base": _plain(base),
        "files": [],
        "reconstructed": [],
        "copies": [],
        "hunks": [],
        "commits": [],
    }


def _needs_review(result, token, text):
    result["answer"] = NEEDS_REVIEW
    result["why"].append(_line(token, text))
    return result


def _certified(record):
    """X, the full sha the record certifies, or None when the record is not a usable, finished-or-not, ok record
    that is not abandoned."""
    if not isinstance(record, dict):
        return None
    # A record that is not ok, or that carries ``abandoned``, certifies nothing, whatever final commit it names.
    if "ok" in record and record["ok"] is not True:
        return None
    if "abandoned" in record:
        return None
    final = record.get("finalCommit")
    sha = final.get("sha") if isinstance(final, dict) else None
    return sha if returning_review._is_sha(sha) else None


def _copies_of(proof):
    if isinstance(proof, dict):
        proof = proof.get("copies")
    if isinstance(proof, (list, tuple)):
        return list(proof)
    return []


def _section_headers(section):
    return [line.rstrip("\r") for line in section["text"].split("\n") if _HUNK_LINE_RE.match(line)]


def _marker_of(path):
    name = path.lower()
    if name.endswith(_HASH_SUFFIXES):
        return "#"
    if name.endswith(_SLASH_SUFFIXES):
        return "//"
    return None


def _section_qualifies(section):
    """True when ``section`` (one file's diff from X to the head) is prose, or only blank and comment lines."""
    if section["unreadable"] or section["binary"]:
        return False
    # A rename or a copy moves a file; whatever it says, the path is behaviour.
    if section["copied"] or section["status"] == "renamed":
        return False
    for line in section["text"].split("\n"):
        if line.startswith(_MODE_LINES):
            return False
        if line.startswith(_FILE_MODE_LINES) and line.split()[-1] not in _REGULAR_MODES:
            return False
    path = section["file"]
    if path.lower().endswith(_PROSE_SUFFIXES):
        return True
    marker = _marker_of(path)
    if marker is None or not _section_headers(section):
        return False
    for body in section["addedLines"] + section["removedLines"]:
        text = body.strip()
        # axis: a non-prose file qualifies only when every added and removed line is blank or a comment of its own language, so a changed assertion or code line never reads judgement — see bite-proof record i2496_wo_a_head_coverage (E-judge)
        if text and not (text.startswith(marker) and not text.startswith(_DIRECTIVE_PREFIXES)):
            return False
    return True


def _qualification(run, x, head, files):
    """``(qualifies, hunks, why text)`` for ``files`` read as ``git diff X head``: every file must be shown by git and
    every section of it must qualify."""
    code, text = run(["diff", *returning_review._DIFF_ARGS, x, head, "--", *files])
    if code != 0:
        return False, [], "git could not produce the diff from the certified commit to the head"
    sections = countable_lines.parse_sections(text)
    shown = {}
    for section in sections:
        shown.setdefault(section["file"], []).append(section)
    hunks = []
    bad = []
    for path in files:
        mine = shown.get(path)
        # A changed file the diff does not show cannot be judged, so it never qualifies.
        if not mine or not all(_section_qualifies(s) for s in mine):
            bad.append(path)
            continue
        for section in mine:
            hunks.extend({"file": path, "header": header} for header in _section_headers(section))
    # a file the diff shows beyond the asked paths (a rename's other side) is read too
    for path, mine in shown.items():
        if path not in files and not all(_section_qualifies(s) for s in mine):
            bad.append(path)
    if bad:
        return False, [], "not only prose or comment lines: %s" % ", ".join(sorted(set(bad))[:5])
    return True, hunks, ""


def _author_email(run, rev):
    code, text = run(["log", "-1", "--format=%ae", rev])
    email = text.strip()
    return email if code == 0 and email else None


def _authors(run, base, x, head):
    """``[{"sha", "author"}]`` of every commit of ``git rev-list head --not X base``, or None when git cannot name them,
    names none, or cannot read an author."""
    code, text = run(["rev-list", head, "--not", x, base])
    shas = text.split()
    if code != 0 or not shas or not all(returning_review._is_sha(s) for s in shas):
        return None
    commits = []
    for sha in shas:
        email = _author_email(run, sha)
        if email is None:
            return None
        commits.append({"sha": sha, "author": email})
    return commits


def check(repo_root, base, record, head, proof=(), builder_author=None, git=None):
    """``{"answer": "proven" | "judgement" | "needs-review", ...}``: whether the commit ``record`` certifies covers
    ``head``. Never raises: every fault reads ``needs-review`` with a reason in ``why``. ``record`` is what
    ``review_record.py read --pr N`` prints, or the bare record. ``proof`` is a list of ``{file, source, sha256}``
    copy entries. ``git`` is the test seam ``returning_review.decide`` takes, ``git(argv) -> (returncode,
    stdout_text)``; production leaves it None."""
    try:
        return _check(repo_root, base, record, head, proof, builder_author, git)
    except Exception as exc:  # total: a fault nobody foresaw is still a review owed
        # axis: a fault of any kind reads needs-review, never an answer that covers the head — see bite-proof record i2496_wo_a_head_coverage (E-fail)
        result = _result(base, head)
        return _needs_review(result, WHY_CHECK_FAILED, "the check failed on %s: %s" % (type(exc).__name__, exc))


def _check(repo_root, base, record, head, proof, builder_author, git):
    x = _certified(record)
    result = _result(base, head, x)
    # 1. the record
    if x is None:
        return _needs_review(result, WHY_RECORD_UNUSABLE,
                             "the review record is not an ok, unabandoned record with a full final commit sha")
    # 2. nothing happened since the review
    if head == x:
        result["answer"] = PROVEN
        result["why"].append(_line(WHY_SAME_COMMIT, "the head is the commit the review certified"))
        return result
    # 3. the inputs
    if not (returning_review._is_sha(base) and returning_review._is_sha(head)):
        return _needs_review(result, WHY_INPUT_INVALID, "the base and the head must each be a full commit sha")
    run = git if git is not None else returning_review.production_git(repo_root)

    # 4. the changed files
    changed = returning_review.changed_files(run, base, x, head)
    if changed is None:
        return _needs_review(result, WHY_DIFF_UNREADABLE,
                             "git could not produce the diff of the certified commit or of the head against the base")
    files = changed[0]

    # 5. the reconstruction proof
    remaining = []
    for path in files:
        # axis: a file is reconstructed only when a clean three-way merge of X, the fork and the base reproduces the head blob byte for byte, so a hand-resolved file stays changed — see bite-proof record i2496_wo_a_head_coverage (E-recon)
        if returning_review.merge_reproduces_head(run, base, x, head, path):
            result["reconstructed"].append(path)
        else:
            remaining.append(path)

    # 6. the proven copies
    if remaining:
        entries = _copies_of(proof)
        # axis: a proof entry counts only when git re-validates it at the head; the entry's own word proves nothing — see bite-proof record i2496_wo_a_head_coverage (E-copy)
        valid = review_record.revalidated_copies(entries, os.fspath(repo_root), base, head) if entries else []
        wanted = set(remaining)
        for entry in valid:
            if entry["file"] in wanted and entry["file"] not in {c["file"] for c in result["copies"]}:
                result["copies"].append({"file": entry["file"], "source": entry["source"], "sha256": entry["sha256"]})
        relied = {c["file"] for c in result["copies"]}
        remaining = [path for path in remaining if path not in relied]
    result["files"] = remaining

    # 7. nothing left
    if not remaining:
        result["answer"] = PROVEN
        if result["copies"]:
            result["why"].append(_line(WHY_PROVEN_COPIES, "%d file(s) are copies git re-validated at the head, and the pull "
                                                          "request's own change is otherwise the reviewed change" % len(result["copies"])))
        else:
            result["why"].append(_line(WHY_OWN_CHANGE_UNCHANGED, "git shows the pull request's own change at the head equals "
                                                                 "the reviewed change"))
        return result

    # 8. judgement or a review owed
    qualifies, hunks, reason = _qualification(run, x, head, remaining)
    commits = _authors(run, base, x, head)
    builder = builder_author.strip().lower() if isinstance(builder_author, str) and builder_author.strip() \
        else _author_email(run, x)
    if commits is not None:
        result["commits"] = commits
    # axis: a judgement answer needs the builder to have authored every new commit; another author, an unreadable author or no commit to name reads needs-review — see bite-proof record i2496_wo_a_head_coverage (E-author)
    authors_ok = commits is not None and builder is not None and all(c["author"].lower() == builder.lower() for c in commits)
    if not authors_ok:
        if commits is None or builder is None:
            text = "git could not name the new commits and their authors"
        else:
            text = "a new commit is by someone other than the builder: %s" % ", ".join(
                sorted({c["author"] for c in commits if c["author"].lower() != builder.lower()}))
        _needs_review(result, WHY_OTHER_AUTHOR, text)
    # A judgement answer needs the content rule and the author rule both; either failing is needs-review.
    if not qualifies:
        _needs_review(result, WHY_BEHAVIOUR_CHANGE, reason)
    if authors_ok and qualifies:
        result["answer"] = JUDGEMENT
        result["hunks"] = hunks
        result["why"].append(_line(WHY_PROSE_OR_COMMENTS, "every remaining difference is prose or comment lines by the builder; "
                                                          "the vet reads the %d hunk(s)" % len(hunks)))
    return result


def outcome(answer, ci, judged_clear=False, sheet="none", sheet_commit=None, head=None):
    """``{"outcome", "why", "review", "sheet"}`` from the check's ``answer``, CI on the head, whether the vet cleared a
    judgement, and the merge sheet's state. Pure; a value outside its set raises ``ValueError``."""
    if answer not in ANSWERS:
        raise ValueError("answer must be one of %s" % ", ".join(ANSWERS))
    if ci not in CI_STATES:
        raise ValueError("ci must be one of %s" % ", ".join(CI_STATES))
    if sheet not in SHEETS:
        raise ValueError("sheet must be one of %s" % ", ".join(SHEETS))
    covered = answer == PROVEN or (answer == JUDGEMENT and judged_clear is True)
    if ci == "red":
        verdict, why, review = NOT_READY, "ci-red", "none"
    elif not covered:
        verdict, review = NOT_READY, "returning"
        why = "judged-meaningful" if answer == JUDGEMENT else "needs-review"
    elif ci in ("pending", "none"):
        verdict, why, review = WAIT, "ci-not-green", "none"
    else:
        verdict, why, review = READY, "covered", "none"
    if sheet == "none":
        action = "none"
    elif sheet == "held":
        action = "republish-unsigned" if verdict == READY else "keep"
    elif verdict == NOT_READY:
        action = "take-down"
    elif verdict == READY and sheet_commit != head:
        action = "republish-carried"
    else:
        action = "keep"
    return {"outcome": verdict, "why": why, "review": review, "sheet": action}


# --------------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------------

def _usage_error(message):
    sys.stderr.write("head_coverage: %s\n" % message)
    return 2


def _read_json(path):
    """``(object, None)`` for a JSON file, else ``(None, fault)``."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.loads(handle.read()), None
    except (OSError, ValueError, UnicodeError):
        return None, "unreadable"


def _check_cli(args):
    if not os.path.isdir(args.repo_root):
        return _usage_error("--repo-root is not a directory: %s" % args.repo_root)
    record, fault = _read_json(args.record)
    if fault is not None:
        return _usage_error("--record is not a readable JSON file: %s" % args.record)
    proof = []
    if args.proof is not None:
        loaded, fault = _read_json(args.proof)
        if fault is not None:
            return _usage_error("--proof is not a readable JSON file: %s" % args.proof)
        if isinstance(loaded, dict):
            loaded, fault = countable_lines.load_proof(args.proof)
            if fault is not None:
                return _usage_error("--proof is not a usable copy proof: %s" % fault)
            loaded = loaded["copies"]
        elif not isinstance(loaded, list) or countable_lines.copies_fault(loaded, name_extra_key=True) is not None:
            return _usage_error("--proof is not a usable list of copies")
        proof = loaded
    result = check(args.repo_root, args.base, record, args.head, proof, builder_author=args.builder_author)
    sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


def _outcome_cli(args):
    try:
        result = outcome(args.answer, args.ci, judged_clear=args.judged_clear, sheet=args.sheet,
                         sheet_commit=args.sheet_commit, head=args.head)
    except ValueError as exc:
        return _usage_error(str(exc))
    sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(prog="head_coverage")
    sub = ap.add_subparsers(dest="cmd", required=True)
    cp = sub.add_parser("check")
    cp.add_argument("--repo-root", required=True)
    cp.add_argument("--base", required=True)
    cp.add_argument("--record", required=True)
    cp.add_argument("--head", required=True)
    cp.add_argument("--proof", default=None)
    cp.add_argument("--builder-author", default=None)
    op = sub.add_parser("outcome")
    op.add_argument("--answer", required=True)
    op.add_argument("--ci", required=True)
    op.add_argument("--judged-clear", action="store_true")
    op.add_argument("--sheet", default="none")
    op.add_argument("--sheet-commit", default=None)
    op.add_argument("--head", default=None)
    args = ap.parse_args(argv)
    return _check_cli(args) if args.cmd == "check" else _outcome_cli(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
