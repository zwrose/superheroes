#!/usr/bin/env python3
"""Deterministic consumer of a delta round's fix-audit stage (#507).

Sibling of verification.apply_verdicts: a delta round re-audits each fixed finding and rules it
`discharged` (the fix resolved it), `not-discharged` (it did not), or `discharged-but-new-issue`
(the fix resolved the original finding but introduced a fresh problem). A model makes the
judgments; this fold consumes them DETERMINISTICALLY so accounting stays reproducible.

stdlib only; never raises on bad input; fail-closed — a wrong `discharged` certifies an
unaudited fix (the expensive failure direction: a real defect ships believed fixed), so every
uncertain / malformed / missing ruling collapses to `not-discharged` and is disclosed.
"""

import os
import re

from finding_identity import finding_identity, place_pair as _place_key

AUDIT_RULINGS = ("discharged", "not-discharged", "discharged-but-new-issue")

UNAUTHENTICATED_NO_AUDITOR_RECORDED = "no-auditor-recorded"
UNAUTHENTICATED_MANIFEST_ENTRY_MISSING = "manifest-entry-missing"
UNAUTHENTICATED_MANIFEST_VENDOR_MISMATCH = "manifest-vendor-mismatch"

# The rulings whose fix counts as discharged for stall/continuation accounting. A
# `discharged-but-new-issue` clears the ORIGINAL finding (a new candidate is emitted separately),
# so it is not a stall on that finding; only `not-discharged` is.
_CLEARS = ("discharged", "discharged-but-new-issue")


def _valid_new_issues(candidates, origin_id):
    """The dict-shaped new-issue candidates from a discharged-but-new-issue claim, each tagged
    with its originating audit id. Non-dict entries are dropped (fail-closed); an empty result
    means the claim carried no usable candidate."""
    out = []
    if not isinstance(candidates, list):
        return out
    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        tagged = dict(cand)
        tagged["originAuditId"] = origin_id
        out.append(tagged)
    return out


def has_usable_new_issues(candidates):
    """True when `candidates` carries at least one dict-shaped new-issue candidate — EXACTLY the
    usability test `apply_audit_results` applies to a `discharged-but-new-issue` claim, exposed so
    the submit-shape guard (#885) and the fold can never read the field differently. The guard's
    whole value is that what it accepts is what the fold can use."""
    return bool(_valid_new_issues(candidates, None))


def has_usable_reason(reason):
    """True when `reason` is a non-blank string — EXACTLY the grounds test `apply_audit_results`
    applies before it honors a `discharged` ruling, exposed so the submit-shape guard (#885) and the
    fold can never read the field differently. Sibling of `has_usable_new_issues`: the guard's whole
    value is that what it accepts is what the fold can use, so a later loosening or tightening of the
    rule moves BOTH sides at once — a guard reading it one way and the fold the other either
    false-refuses a legitimate submit or re-admits the #885 terminal-loss class."""
    return isinstance(reason, str) and bool(reason.strip())


CHECK_NAMES = ("right", "brokeNothing", "testWouldFail")
CHECK_ANSWERS = ("yes", "no")
TEST_MATCH_ANSWERS = ("matches", "weakened")

# The third answer `testWouldFail` may take (#2341): the fix's whole delta is doctrine prose, which
# the pin rule (rubric/review-discipline.md) forbids pinning with a test, so no test can be asked for.
REVIEW_GUARDED = "review-guarded"

# The fourth answer `testWouldFail` may take (#2434): the fix only removes test lines that a worthless-test
# finding cites, so no test can be asked for. The fold clears it only through `test_removal_clearance`.
WORTHLESS_TEST_REMOVED = "worthless-test-removed"

# The test smells (as `normalize_smell` reads a finding's `taxonomy`) whose finding asks for a test to be removed.
WORTHLESS_TEST_SMELLS = frozenset({"wording-pin", "duplicate-test", "mock-echo", "cannot-fail"})


def check_answers(name):
    """The answers check `name` accepts. The one home of the per-check answer set: the shape judge
    (`audit_checks_fault`) and the strict-mode schema (`engine_result_channel`) both read it. Only
    `testWouldFail` may answer `review-guarded` or `worthless-test-removed`."""
    if name == "testWouldFail":
        return CHECK_ANSWERS + (REVIEW_GUARDED, WORTHLESS_TEST_REMOVED)
    return CHECK_ANSWERS


def normalize_smell(text):
    """A taxonomy label read as a test-smell name: lower-cased, every run of non-alphanumeric characters one
    `-`, leading and trailing `-` stripped (`"Wording pin"` reads `wording-pin`). None when `text` is no string."""
    if not isinstance(text, str):
        return None
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


# Path components that are never doctrine prose, even for a Markdown file: eval graders are scored
# checks, and fixture or golden files pin rendered text. Compared case-insensitively.
NON_PROSE_DIR_NAMES = frozenset({
    "eval", "evals", "graders", "fixtures", "fixture", "golden", "goldens", "snapshots",
    "__snapshots__", "testdata",
})

_DIFF_HEADER = "diff --git "


def _delta_files(target):
    """The files the target's driver-built `fixerDelta` names, in order, or None when the delta is
    absent, not a list, or carries a header that does not read `diff --git a/<f> b/<f>` with the same
    `<f>` on both sides (fail closed: an unreadable delta is never prose-only)."""
    delta = target.get("fixerDelta") if isinstance(target, dict) else None
    if not isinstance(delta, list):
        return None
    files = []
    for line in delta:
        if not isinstance(line, str) or not line.startswith(_DIFF_HEADER):
            continue
        rest = line[len(_DIFF_HEADER):]
        # The form is `a/<f> b/<f>`: five fixed characters plus `<f>` twice, so `<f>` (which may hold
        # spaces) is read off by length and the whole header compared; never split on spaces.
        span = len(rest) - 5
        if span <= 0 or span % 2:
            return None
        path = rest[2:2 + span // 2]
        if rest != "a/" + path + " b/" + path:
            return None
        if path not in files:
            files.append(path)
    return files


def _is_prose_path(path):
    from size_count import is_test_path as _is_test_path  # noqa: E402 — lazy: the closure of this module stays unchanged
    normalized = path.replace("\\", "/")
    # axis: only a Markdown file is prose — see bite-proof record audit_review_guarded_2341
    if not normalized.lower().endswith(".md"):
        return False
    # axis: a Markdown file under a test tree is test material, not doctrine — see bite-proof record audit_review_guarded_2341
    if _is_test_path(normalized):
        return False
    # axis: a Markdown file under an eval, fixture or golden tree is a scored or pinned artifact, not doctrine — see bite-proof record audit_review_guarded_2341
    return not any(c.lower() in NON_PROSE_DIR_NAMES for c in normalized.split("/")[:-1])


def prose_only_delta(target):
    """`(ok, files)`: `ok` is True only when the target's driver-built `fixerDelta` names at least one
    file and every file it names is doctrine prose (a Markdown file outside the test trees and the
    `NON_PROSE_DIR_NAMES` trees); `files` lists the files that are not prose, empty when `ok` and
    also empty when the delta is absent, unreadable or names no file. The judgment reads the target the
    driver built, never anything the auditor wrote."""
    files = _delta_files(target)
    # axis: an absent, unreadable or empty delta is never prose-only — see bite-proof record audit_review_guarded_2341
    if not files:
        return False, []
    other = [f for f in files if not _is_prose_path(f)]
    return not other, other


def _plain_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


_ABSENT = object()


# The languages whose test files the removal clearance can read (#2434): the extensions of each and the line
# pattern that opens a test in it. A file in any other language has no reader, so it clears nothing.
PYTHON_TEST_EXTENSIONS = frozenset({".py"})
JS_TEST_EXTENSIONS = frozenset({".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"})
PYTHON_TEST_OPENING = re.compile(r"^\s*(async\s+)?def\s+test\w*\s*\(|^\s*class\s+Test\w*\b")
JS_TEST_OPENING = re.compile(r"^\s*(it|test|describe)(\.\w+)*\s*\(")


def test_openings(path, text):
    """The sorted 1-based line numbers at which the file `path` with content `text` opens a test, or None
    when the language of `path` has no reader (an extension outside `PYTHON_TEST_EXTENSIONS` and
    `JS_TEST_EXTENSIONS`). A reader matches a line, not a parse: a line inside a string or comment that looks like
    an opening counts as one, which only makes the clearance refuse more. Lines are cut at `\\n`, as git counts
    them."""
    extension = os.path.splitext(path)[1].lower() if isinstance(path, str) else ""
    if extension in PYTHON_TEST_EXTENSIONS:
        pattern = PYTHON_TEST_OPENING
    elif extension in JS_TEST_EXTENSIONS:
        pattern = JS_TEST_OPENING
    else:
        return None
    return [number for number, line in enumerate(text.split("\n"), 1) if pattern.match(line)]


def _removal_files(target):
    """The files of the target's driver-built `fixerRemoval` as `[(path, ranges, added, openings)]`, or None when
    the record is absent, `unreadable`, or not exactly `{"files": [{"path": <non-empty str>, "removed": [[start,
    end], ...], "added": <bool>, "testOpenings": <None or [<int >= 1>, ...]>}, ...]}` with at least one file, one
    record per path, and every range two plain integers with `1 <= start <= end` (fail closed: an unreadable
    record clears nothing). `testOpenings` is the base file's test-opening lines (`test_openings`); None means
    its language has no reader."""
    record = target.get("fixerRemoval") if isinstance(target, dict) else None
    # axis: an absent, unreadable or malformed removal record is never readable — see bite-proof record audit_test_removal_2434
    if not isinstance(record, dict) or "unreadable" in record:
        return None
    files = record.get("files")
    if not isinstance(files, list) or not files:
        return None
    out, seen = [], set()
    for entry in files:
        if not isinstance(entry, dict):
            return None
        path, removed, added = entry.get("path"), entry.get("removed"), entry.get("added")
        if not isinstance(path, str) or not path or path in seen:
            return None
        if not isinstance(added, bool) or not isinstance(removed, list):
            return None
        openings = entry.get("testOpenings", _ABSENT)
        # axis: a row whose `testOpenings` is absent or not None-or-a-list-of-lines-from-1 makes the record unreadable — see bite-proof record audit_test_removal_2434
        if openings is _ABSENT or not (openings is None or (
                isinstance(openings, list) and all(_plain_int(n) and n >= 1 for n in openings))):
            return None
        ranges = []
        for pair in removed:
            if not (isinstance(pair, list) and len(pair) == 2 and all(_plain_int(n) for n in pair)):
                return None
            if not 1 <= pair[0] <= pair[1]:
                return None
            ranges.append((pair[0], pair[1]))
        seen.add(path)
        out.append((path, ranges, added, None if openings is None else list(openings)))
    return out


def _worthless_test_smell(finding):
    """`(smell, detail)`: the normalized `taxonomy` of a finding that is a Test finding labelled with one of the
    `WORTHLESS_TEST_SMELLS` and carries a usable body, else `(None, <what is missing>)`."""
    if not isinstance(finding, dict):
        return None, "is not a finding"
    # axis: only a Test finding is a worthless-test finding — see bite-proof record audit_test_removal_2434
    if finding.get("dimension") != "Test":
        return None, "dimension is %r, not 'Test'" % (finding.get("dimension"),)
    smell = normalize_smell(finding.get("taxonomy"))
    # axis: only a finding labelled with one of the worthless-test smells is one — see bite-proof record audit_test_removal_2434
    if smell not in WORTHLESS_TEST_SMELLS:
        return None, "taxonomy %r is not one of: %s" % (finding.get("taxonomy"), ", ".join(sorted(WORTHLESS_TEST_SMELLS)))
    # axis: a worthless-test finding must give its reason in a body — see bite-proof record audit_test_removal_2434
    if not has_usable_reason(finding.get("body")):
        return None, "has no usable body giving its reason"
    return smell, None


def cited_lines(finding):
    """The `(file, line)` places a finding cites at a plain integer line, in order, none twice: its own
    `file`/`line` and the places of its kind of mistake. The one reading of what a finding cites: the clearance
    conditions and the driver's citation-freshness check both use it."""
    out = []
    if isinstance(finding, dict) and isinstance(finding.get("file"), str) and _plain_int(finding.get("line")):
        out.append((finding["file"], finding["line"]))
    for file, line in target_places(finding):
        if isinstance(file, str) and _plain_int(line) and (file, line) not in out:
            out.append((file, line))
    return out


def test_removal_clearance(target):
    """`(evidence, failing, detail)`: whether the target's fix is the removal of test lines a worthless-test
    finding cites, judged only from driver-built data (the target's `fixerDelta`, `fixerRemoval`, its own
    finding fields and its `batchFindings`), never from anything the auditor wrote. All of C1-C10 must hold:

    C1  `fixerDelta` is readable, names at least one file, and every file is a test path;
    C2  `fixerRemoval` is readable and well formed (see `_removal_files`);
    C3  the removal record names exactly the delta's files;
    C4  every file of the record added nothing and removed at least one range;
    C5  the target is a Test finding labelled with a worthless-test smell, with a usable body;
    C6  one of the target's own cited lines (its `file:line` or a kind-of-mistake place) lies in a removed range;
    C7  every removed range holds a line cited by the target or by a fresh qualifying sibling (a batch sibling
        that itself passes C5 and whose driver-built `citationFresh` is True);
    C8  every changed file is in a language the test-opening reader supports (`testOpenings` is not None);
    C9  every test the base file opens inside a removed range opens on a cited line (the target's, or a
        fresh qualifying sibling's), so the fix cannot also delete an unflagged test beside the flagged one;
    C10 the target's `citationFresh` is True: the files its cited lines sit in did not change between the head
        the finding was raised on and the fix's start head, so a cited line still points at what it cited.

    On success `(evidence, None, None)` with `evidence` the dict the audit entry records
    (`{"source": "finding", "finding", "taxonomy", "reason", "removed", "cited", "openings"}`; `cited` lists the
    target's cited lines, then each fresh qualifying sibling's; `openings` lists, per file, the base file's test openings
    inside its removed ranges); otherwise `(None, <first failing condition>, <short detail>)`."""
    from size_count import is_test_path as _is_test_path  # noqa: E402 — lazy: the closure of this module stays unchanged
    files = _delta_files(target)
    # axis: an absent, unreadable or empty delta clears nothing on the removal answer — see bite-proof record audit_test_removal_2434
    if not files:
        return None, "C1", "no recorded delta"
    # axis: a non-test file in the delta clears nothing on the removal answer — see bite-proof record audit_test_removal_2434
    other = [f for f in files if not _is_test_path(f)]
    if other:
        return None, "C1", "the delta touches non-test %s" % ", ".join(other)
    rows = _removal_files(target)
    # axis: a removal record that is absent, unreadable or malformed clears nothing — see bite-proof record audit_test_removal_2434
    if rows is None:
        return None, "C2", "no readable removal record"
    # axis: the removal record and the delta must name the same files — see bite-proof record audit_test_removal_2434
    if {path for path, _r, _a, _o in rows} != set(files):
        return None, "C3", "the removal record and the delta name different files"
    for path, ranges, added, _o in rows:
        # axis: a fix that adds a line to a file clears nothing on the removal answer — see bite-proof record audit_test_removal_2434
        if added is not False:
            return None, "C4", "%s has added lines" % path
        # axis: a file with no removed range clears nothing on the removal answer — see bite-proof record audit_test_removal_2434
        if not ranges:
            return None, "C4", "%s has no removed lines" % path
    smell, detail = _worthless_test_smell(target)
    if smell is None:
        return None, "C5", detail
    own = cited_lines(target)
    cited = list(own)
    batch = target.get("batchFindings")
    for sibling in batch if isinstance(batch, list) else ():
        # axis: only a sibling that is itself a worthless-test finding, with a citation the driver found fresh, lends its cited lines — see bite-proof record audit_test_removal_2434
        if _worthless_test_smell(sibling)[0] is not None and sibling.get("citationFresh") is True:
            cited.extend(c for c in cited_lines(sibling) if c not in cited)

    def _inside(places, path, rng):
        return any(file == path and rng[0] <= line <= rng[1] for file, line in places)

    # axis: one of the target's own cited lines must lie in a removed range — see bite-proof record audit_test_removal_2434
    if not any(_inside(own, path, rng) for path, ranges, _a, _o in rows for rng in ranges):
        return None, "C6", "no removed range holds a line the finding cites"
    for path, ranges, _a, _o in rows:
        for rng in ranges:
            # axis: every removed range must hold a cited line, so the fix cannot also delete an uncited test — see bite-proof record audit_test_removal_2434
            if not _inside(cited, path, rng):
                return None, "C7", "%s lines %d-%d hold no cited line" % (path, rng[0], rng[1])
    for path, _r, _a, openings in rows:
        # axis: a file in a language the test-opening reader does not support clears nothing on the removal answer — see bite-proof record audit_test_removal_2434
        if openings is None:
            return None, "C8", "%s is in a language whose tests cannot be read" % path
    inside_openings = []
    for path, ranges, _a, openings in rows:
        within = sorted({n for n in openings if any(rng[0] <= n <= rng[1] for rng in ranges)})
        for line in within:
            # axis: every test the base file opens inside a removed range must open on a cited line, so the fix cannot also delete an unflagged test beside the flagged one — see bite-proof record audit_test_removal_2434
            if (path, line) not in cited:
                return None, "C9", "%s opens a test at line %d that no finding cites" % (path, line)
        inside_openings.append({"file": path, "lines": within})
    # axis: a cited line that may have moved since the finding was raised ties nothing — see bite-proof record audit_test_removal_2434
    if target.get("citationFresh") is not True:
        return None, "C10", "the cited lines may have moved since the finding was raised"
    reason = target["body"].strip()[:500]
    return {"source": "finding", "finding": target.get("id"), "taxonomy": smell, "reason": reason,
            "removed": [{"file": path, "ranges": [list(r) for r in ranges]} for path, ranges, _a, _o in rows],
            "cited": [{"file": file, "line": line} for file, line in cited],
            "openings": inside_openings}, None, None


MATCH_SAME = "same"
MATCH_CHANGED_EXPLAINED = "changed-explained"
MATCH_CHANGED_UNEXPLAINED = "changed-unexplained"
MATCH_MISSING = "missing"
BREAK_IT_MATCHES = (MATCH_SAME, MATCH_CHANGED_EXPLAINED, MATCH_CHANGED_UNEXPLAINED, MATCH_MISSING)
# The matches that block the fix whatever the result says: the committed test is not the test role's
# version, nor a change of it the build session explained.
_BLOCKING_MATCHES = (MATCH_CHANGED_UNEXPLAINED, MATCH_MISSING)


def break_it_match(target):
    """The `breakIt.match` the driver recorded on an audit target: None when the target carries no
    `breakIt`; a value outside `BREAK_IT_MATCHES` reads as `missing` (fail closed)."""
    if not isinstance(target, dict) or "breakIt" not in target:
        return None
    block = target.get("breakIt")
    match = block.get("match") if isinstance(block, dict) else None
    return match if match in BREAK_IT_MATCHES else MATCH_MISSING


def _answered(entry, allowed):
    """None when `entry` is `{"answer": <one of allowed>, "why": <usable reason>}`, else what is wrong."""
    if not isinstance(entry, dict):
        return "is not an object"
    if not isinstance(entry.get("answer"), str) or entry["answer"] not in allowed:
        return "has an `answer` of %r, not one of: %s" % (entry.get("answer"), ", ".join(allowed))
    if not has_usable_reason(entry.get("why")):
        return "has no usable `why`"
    return None


def audit_checks_fault(result, target=None):
    """None when an audit result answers the fix auditor's three checks (`checks.right`,
    `checks.brokeNothing`, `checks.testWouldFail`, each `{"answer": "yes"|"no", "why": <reason>}`; only
    `testWouldFail` may also answer `review-guarded` or `worthless-test-removed`, per `check_answers`) and,
    where `target` carries a `breakIt` whose match is `changed-explained`, the test comparison
    (`testMatch`: `{"answer": "matches"|"weakened", "why": <reason>}`); otherwise a short reason. With
    no target in hand only the `checks` shape is judged. The ONE judge of this shape: the payload
    contract's `audit-checks` predicate, the submit-shape guard and the fold all call this function."""
    checks = result.get("checks") if isinstance(result, dict) else None
    if not isinstance(checks, dict):
        return "`checks` is %s, not an object with `right`, `brokeNothing` and `testWouldFail`" % (
            "missing" if checks is None else type(checks).__name__)
    for name in CHECK_NAMES:
        if name not in checks:
            return "`checks.%s` is missing" % name
        # axis: only `testWouldFail` accepts `review-guarded`; `right` and `brokeNothing` answer yes or no — see bite-proof record audit_review_guarded_2341
        why = _answered(checks[name], check_answers(name))
        if why is not None:
            return "`checks.%s` %s" % (name, why)
    if break_it_match(target) == MATCH_CHANGED_EXPLAINED:
        why = _answered(result.get("testMatch"), TEST_MATCH_ANSWERS)
        if why is not None:
            return ("`testMatch` %s — the committed break-it test was changed, so the audit owes "
                    "whether it still matches the test role's" % why)
    return None


def target_places(target):
    """The `(file, line)` of each place the target finding's kind of mistake names, in order, none twice;
    empty when it names none."""
    kind = target.get("kindOfMistake") if isinstance(target, dict) else None
    places = kind.get("places") if isinstance(kind, dict) else None
    out = []
    for place in places if isinstance(places, list) else ():
        key = _place_key(place)
        if key is not None and key not in out:
            out.append(key)
    return out


def place_answers_fault(result):
    """None when the result's optional `places` is absent, null, or a list of `{file, line, fixed}` rows
    (`fixed` a boolean); otherwise a short reason. The submit-shape guard and the fold both read this."""
    places = result.get("places") if isinstance(result, dict) else None
    if places is None:
        return None
    if not isinstance(places, list):
        return "`places` is %s, not a list of {file, line, fixed}" % type(places).__name__
    for i, row in enumerate(places):
        if _place_key(row) is None:
            return "`places[%d]` has no usable file and line" % i
        if not isinstance(row.get("fixed"), bool):
            return "`places[%d].fixed` is not true or false" % i
    return None


def judge_places(target, result):
    """How the result answers the places the target names: `None` when the target names none, else
    `{"rows": [{file, line, fixed}], "unfixed": [(file, line)], "unanswered": [(file, line)], "ignored": [(file, line)]}`.
    A place counts fixed only when a result row with the same `(file, line)` says `fixed: true`; an unanswered
    place reads `fixed: false`. A result row for a place the target does not list is ignored."""
    named = target_places(target)
    if not named:
        return None
    answers = {}
    ignored = []
    rows_in = result.get("places") if isinstance(result, dict) and isinstance(result.get("places"), list) else []
    for row in rows_in:
        key = _place_key(row)
        if key is None or not isinstance(row.get("fixed"), bool):
            continue
        if key not in named:
            if key not in ignored:
                ignored.append(key)
            continue
        # a place answered twice is fixed only when every answer says so
        answers[key] = answers.get(key, True) and row["fixed"]
    rows, unfixed, unanswered = [], [], []
    for key in named:
        fixed = answers.get(key) is True
        rows.append({"file": key[0], "line": key[1], "fixed": fixed})
        if key not in answers:
            unanswered.append(key)
        elif not fixed:
            unfixed.append(key)
    return {"rows": rows, "unfixed": unfixed, "unanswered": unanswered, "ignored": ignored}


def _places_text(keys):
    return ", ".join(file if line is None else "%s:%s" % (file, line) for file, line in keys)


def failed_check(result):
    """`(name, why)` of the first of the three checks answered `no` in a result that passes
    `audit_checks_fault`, else None."""
    checks = result.get("checks") if isinstance(result, dict) else None
    for name in CHECK_NAMES:
        entry = checks.get(name) if isinstance(checks, dict) else None
        if isinstance(entry, dict) and entry.get("answer") == "no":
            return name, str(entry.get("why")).strip()
    return None


def _resolve_expected_auditor(fid, finding, expected_auditors):
    """The TRUSTED independent-auditor selection for a target — the DRIVER's record, never the
    result's own echo (#507 R2). Prefer the explicit `expected_auditors` map the driver passes
    (round_driver._audit_targets); fall back to the target's driver-stamped `auditorVendor`. Returns
    (expected_vendor_or_None, enforced): `enforced` is True whenever the driver supplied a provenance
    signal (a map, or an auditorVendor on the target). When enforced but the expected vendor is falsy
    (a target with NO recorded selection), a clearing ruling cannot prove independence → fail closed."""
    if isinstance(expected_auditors, dict):
        v = expected_auditors.get(fid)
        return (v if isinstance(v, str) and v else None), True
    v = finding.get("auditorVendor") if isinstance(finding, dict) else None
    if isinstance(v, str) and v:
        return v, True
    return None, False


UNNAMED_CHANGE_REASON_PREFIX = "the fix changes behaviour its finding does not name: "


def has_usable_unnamed_change(value):
    """True when `value` is a non-blank string — the auditor's plain-words statement of behaviour the
    fix changes that its finding does not name. Absent, null or blank means none."""
    return isinstance(value, str) and bool(value.strip())


def _claim_members(value):
    """The stripped members of an `unnamedChangeFixes` / `unnamedChangeReverts` claim, or None when
    the value is not a usable claim list (non-list, or a member that is not a non-blank string)."""
    if value is None:
        return []
    if not isinstance(value, list):
        return None
    members = []
    for m in value:
        if not (isinstance(m, str) and m.strip()):
            return None
        if m.strip() not in members:
            members.append(m.strip())
    return members


def unnamed_change_claims_fault(fixes, reverts):
    """The name of the first malformed claim field among `unnamedChangeFixes` / `unnamedChangeReverts`,
    or None. A claim is None or a list of non-blank strings (an empty list is no claim). Sibling of
    `has_usable_reason`: the submit guard and the fold read the field through this one predicate."""
    if _claim_members(fixes) is None:
        return "unnamedChangeFixes"
    if _claim_members(reverts) is None:
        return "unnamedChangeReverts"
    return None


def _target_names(target, field, key):
    """The usable names a driver-built list on a target carries: the non-blank string `key` of each
    dict entry of `target[field]`. A missing or non-list field has none."""
    rows = target.get(field) if isinstance(target, dict) else None
    if not isinstance(rows, list):
        return set()
    return {row[key] for row in rows
            if isinstance(row, dict) and isinstance(row.get(key), str) and row[key].strip()}


def _claims_verify(target, fixes, reverts):
    """True when at least one claim is given and every named id is a round finding of the target's
    driver-built `roundFindings` and every named ref is one of its `reportedUnnamedChanges`."""
    if not (fixes or reverts):
        return False
    round_ids = _target_names(target, "roundFindings", "id")
    refs = _target_names(target, "reportedUnnamedChanges", "ref")
    return all(i in round_ids for i in fixes) and all(x in refs for x in reverts)


# The reason an audit entry carries when no result came back for its target (silence, not a ruling).
NO_AUDIT_RESULT_REASON = "no audit result for this finding — cannot certify the fix discharged"


def is_decision_seq(value):
    """True when `value` is an integer (never a bool) — the sequence of a carried owner decision."""
    return isinstance(value, int) and not isinstance(value, bool)


def _index_results(results):
    """Index the audit results by id: `(by_id, seen_ids, ambiguous_ids)`."""
    # Build the id→result map, detecting duplicate ids. A finding id carried by MORE THAN ONE
    # result is ambiguous — honor none of them so a wrong `discharged` cannot silently win and
    # certify an unaudited fix. `seen_ids` is every id any result carried (used to tell silence
    # from a matched-but-unhonored result).
    by_id = {}
    seen_ids = set()
    ambiguous_ids = set()
    if isinstance(results, list):
        for r in results:
            if isinstance(r, dict) and isinstance(r.get("id"), str):
                rid = r["id"]
                if rid in seen_ids:
                    ambiguous_ids.add(rid)
                    by_id.pop(rid, None)
                    continue
                seen_ids.add(rid)
                by_id[rid] = r
    return by_id, seen_ids, ambiguous_ids


def _duplicate_target_ids(audited):
    """The set of target ids carried by more than one audit target."""
    # Duplicate TARGET ids (e.g. a session persisted before per-location ids) — honor none of the
    # group so one ruling cannot discharge an unaudited sibling.
    duplicate_target_ids = set()
    target_id_counts = {}
    for f in audited:
        if not isinstance(f, dict):
            continue
        fid = f.get("id")
        if isinstance(fid, str):
            target_id_counts[fid] = target_id_counts.get(fid, 0) + 1
    for fid, count in target_id_counts.items():
        if count > 1:
            duplicate_target_ids.add(fid)
    return duplicate_target_ids


class _AuditFold:
    """One `apply_audit_results` call's inputs and its accumulating outcome lists. It is created per
    call and never shared; the per-target values (`fid`, `r`, `base`, the ruling and the rest) are
    locals of `fold_target`, passed to each stage, and never stored here."""

    def __init__(self, by_id, ambiguous_ids, duplicate_target_ids, expected_auditors,
                 collection_manifest, carry_fields, change_allowed_ids):
        self.by_id = by_id
        self.ambiguous_ids = ambiguous_ids
        self.duplicate_target_ids = duplicate_target_ids
        self.expected_auditors = expected_auditors
        self.collection_manifest = collection_manifest
        self.carry_fields = carry_fields
        self.change_allowed_ids = change_allowed_ids
        self.audits = []
        self.discharged, self.not_discharged = [], []
        self.new_issues = []
        self.unaudited, self.malformed = [], []
        self.unauthenticated = []
        self.echo_mismatch = []
        self.unnamed_change = []
        self.attributed_change = []
        self.test_mismatch = []
        self.places_unfixed = []
        self.places_ignored = []
        self.review_guarded = []
        self.review_guard_refused = []
        self.test_removal_cleared = []
        self.test_removal_refused = []
        self.allowed_ids = set(i for i in (change_allowed_ids or ()) if isinstance(i, str))
        self.matched_ids = set()

    def _reject_unauthenticated(self, base, fid, reason, cause):
        """Fail-closed a clearing ruling the orchestrator's manifest could not authenticate:
        not-discharged, disclosed as `unauthenticated`."""
        self.unauthenticated.append(fid)
        self.not_discharged.append(fid)
        base.update(ruling="not-discharged", reason=reason, unauthenticatedCause=cause)
        self.audits.append(base)

    def refuse_unnamed_change(self, base, fid, text, candidates):
        """A clearing result that states behaviour its finding does not name, with no ruling that
        allows it: not-discharged, disclosed as `unnamedChange`; any new issues it carried stay."""
        self.unnamed_change.append(fid)
        self.not_discharged.append(fid)
        self.new_issues.extend(candidates)
        base.update(ruling="not-discharged",
                    reason=UNNAMED_CHANGE_REASON_PREFIX + text)
        self.audits.append(base)

    def credit_attribution(self, base, fid, text, fixes, reverts):
        """A clearing result whose unnamed change is attributed, by claims the driver's record
        verifies, to a same-round fix and/or a revert: stays discharged, never `allowedChange`."""
        base["attributedChange"] = text
        if fixes:
            base["sameRoundFixes"] = fixes
        if reverts:
            base["revertedChanges"] = reverts
        self.attributed_change.append(fid)

    def fold_target(self, f):
        """Fold one audit target (a dict) into the outcome lists."""
        fid = f.get("id")
        if not isinstance(fid, str):
            fid = None
        r = self.by_id.get(fid) if fid is not None else None
        if r is not None and fid is not None:
            self.matched_ids.add(fid)

        # The DRIVER records the SELECTED independent auditor vendor per target (round_driver.
        # _audit_targets) and passes it here as trusted provenance. A clearing ruling is authenticated
        # against THAT record — never the result's own claimant-controlled echo. `base` also carries
        # the recurrence class keys so the audit-stall breaker's alias-tolerant match sees a
        # retitled-but-same-class stall (#507 v0).
        expected_auditor, provenance_enforced = _resolve_expected_auditor(fid, f, self.expected_auditors)
        ident = f.get("identity")
        if not isinstance(ident, str) or not ident:
            ident = finding_identity(f) if isinstance(f, dict) else None
        base = {"id": fid, "identity": ident, "file": f.get("file"), "line": f.get("line"),
                "title": f.get("title"), "classKey": f.get("classKey"),
                "dimension": f.get("dimension"), "taxonomy": f.get("taxonomy")}
        for name in self.carry_fields:
            marker = f.get(name)
            if isinstance(marker, str) and marker:
                base[name] = marker
        match = break_it_match(f)
        if match is not None:
            base["testMatch"] = {"match": match, "answer": None, "blocking": False}

        # No matching result (silence) → fail-closed not-discharged, disclosed as unaudited.
        # An ambiguous id is IN seen_ids OR is a duplicate target id — disclosed via `ambiguous`.
        if r is None:
            self._fold_silence(base, fid)
            return

        if self._fold_duplicate_target(base, fid):
            return

        ruling = r.get("ruling")
        reason = r.get("reason")
        # The SHARED grounds predicate — the same function the submit-shape guard calls, never a
        # second copy of the rule (#885 review: cross-module connascence of algorithm).
        has_reason = has_usable_reason(reason)
        evidence = r.get("evidence")

        if self._reject_unproven_provenance(base, fid, r, ruling, expected_auditor, provenance_enforced):
            return

        keeps_new_issues = self._keeps_new_issues(fid, ruling, expected_auditor, provenance_enforced)

        # The committed break-it test is judged after provenance and before any ruling arm. A test that
        # is missing, or changed with no explanation, is not the test role's version: the fix is
        # blocked whatever the result says.
        test_match = r.get("testMatch")
        reported = test_match.get("answer") if isinstance(test_match, dict) else None
        if self._fold_blocking_test(base, fid, f, r, match, reported, keeps_new_issues):
            return
        if self._fold_checks_fault(base, fid, f, r):
            return
        placed, incomplete = self._collect_places(base, fid, f, r)
        if self._fold_weakened_test(base, fid, r, match, test_match, reported, keeps_new_issues):
            return
        if self._fold_incomplete_places(base, fid, r, ruling, placed, incomplete):
            return
        if self._fold_failed_check(base, fid, r, ruling):
            return
        finished, guarded = self._review_guard(base, fid, f, r, ruling)
        if finished:
            return
        finished, removal = self._test_removal_guard(base, fid, f, r, ruling)
        if finished:
            return

        # A clearing result that names behaviour its finding does not name is accepted only when the
        # finding's ruling allows the change. Provenance (above) keeps its precedence.
        unnamed = r.get("unnamedChange")
        if self._fold_malformed_unnamed(base, fid, r, ruling, unnamed):
            return
        unnamed_text = unnamed.strip() if has_usable_unnamed_change(unnamed) else None
        # The change is attributed (rather than refused) only when every claim the auditor gives
        # verifies against the driver's own record on the target; claims without a change do nothing.
        fixes = _claim_members(r.get("unnamedChangeFixes")) if ruling in _CLEARS else []
        reverts = _claim_members(r.get("unnamedChangeReverts")) if ruling in _CLEARS else []
        attributed = bool(unnamed_text and fid not in self.allowed_ids
                          and _claims_verify(f, fixes, reverts))
        if unnamed_text:
            base["reportedUnnamedChange"] = unnamed_text

        if ruling == "discharged":
            self._fold_discharged(base, fid, reason, has_reason, evidence, unnamed_text, attributed,
                                  fixes, reverts, guarded, removal)
        elif ruling == "discharged-but-new-issue":
            self._fold_discharged_new_issue(base, fid, r, reason, has_reason, evidence, unnamed_text,
                                            attributed, fixes, reverts, guarded, removal)
        elif ruling == "not-discharged":
            self._fold_not_discharged(base, fid, r, reason, has_reason, unnamed_text, expected_auditor,
                                      keeps_new_issues)
        else:
            self._fold_unrecognized(base, fid, ruling)

    def _fold_silence(self, base, fid):
        if fid is not None and fid in self.duplicate_target_ids:
            base.update(ruling="not-discharged",
                        reason="duplicate audit target id — honoring none")
        elif fid is not None and fid in self.ambiguous_ids:
            base.update(ruling="not-discharged",
                        reason="more than one audit result claimed this finding — honoring none")
        else:
            if fid is not None:
                self.unaudited.append(fid)
            base.update(ruling="not-discharged",
                        reason=NO_AUDIT_RESULT_REASON)
        self.audits.append(base)
        if fid is not None:
            self.not_discharged.append(fid)

    def _fold_duplicate_target(self, base, fid):
        if fid in self.duplicate_target_ids:
            base.update(ruling="not-discharged",
                        reason="duplicate audit target id — honoring none")
            self.audits.append(base)
            self.not_discharged.append(fid)
            return True
        return False

    def _reject_unproven_provenance(self, base, fid, r, ruling, expected_auditor, provenance_enforced):
        # Provenance (trust-boundary): a ruling that CLEARS the finding is authenticated against the
        # dispatching ORCHESTRATOR's out-of-band COLLECTION MANIFEST — {result-id: vendor} recorded
        # from the orchestrator's OWN dispatch records, NEVER derived from the result's contents. The
        # in-result `auditorVendor` echo is ADVISORY only: a forged/mistaken result simply echoes the
        # expected value, so the echo authenticates nothing (the R2 defect: the auditor's own words
        # used as their credential). Fail-closed rejections (each → not-discharged + disclosed as
        # `unauthenticated`): a target with NO recorded auditor selection cannot prove independence at
        # all; NO manifest entry means the orchestrator never recorded who executed this audit; a
        # manifest vendor that disagrees with the recorded selection is a misroute. When authenticated
        # by the manifest, an echo that disagrees with it is disclosed via `echoMismatch` but the
        # manifest governs — the discharge stands.
        if provenance_enforced and ruling in ("discharged", "discharged-but-new-issue"):
            if not expected_auditor:
                self._reject_unauthenticated(
                    base, fid,
                    "no independent auditor was recorded for this target — cannot prove the audit "
                    "came from an independent auditor; treated as not-discharged",
                    UNAUTHENTICATED_NO_AUDITOR_RECORDED)
                return True
            manifest_vendor = None
            if isinstance(self.collection_manifest, dict):
                mv = self.collection_manifest.get(fid)
                if isinstance(mv, str) and mv:
                    manifest_vendor = mv
            if manifest_vendor is None:
                self._reject_unauthenticated(
                    base, fid,
                    "no dispatch-manifest entry for this target — the orchestrator did not record "
                    "which engine executed the audit; cannot authenticate; treated as not-discharged",
                    UNAUTHENTICATED_MANIFEST_ENTRY_MISSING)
                return True
            if manifest_vendor != expected_auditor:
                self._reject_unauthenticated(
                    base, fid,
                    "the dispatch manifest names %r but the selected independent auditor is %r — "
                    "treated as not-discharged" % (manifest_vendor, expected_auditor),
                    UNAUTHENTICATED_MANIFEST_VENDOR_MISMATCH)
                return True
            # Authenticated by the orchestrator's manifest. The recorded auditor is the TRUSTED value
            # (the manifest, not the claimant echo). An echo that disagrees is advisory noise —
            # disclosed via `echoMismatch`, but the manifest governs and the discharge stands.
            base["auditor"] = manifest_vendor
            echo = r.get("auditorVendor")
            if isinstance(echo, str) and echo and echo != manifest_vendor:
                self.echo_mismatch.append(fid)
                base["echoMismatch"] = {"echo": echo, "manifest": manifest_vendor}
        return False

    def _keeps_new_issues(self, fid, ruling, expected_auditor, provenance_enforced):
        # The new issues a result that got this far raised stay whatever its verdict: a `not-discharged`
        # result keeps them as a `discharged-but-new-issue` one does, once the manifest authenticates it
        # (or the target is not provenance-enforced). Results refused before here (unauthenticated,
        # ambiguous, unmatched, unknown ruling) and those `audit_checks_fault` refuses drop them.
        return ruling == "discharged-but-new-issue" or (
            ruling == "not-discharged"
            and (not provenance_enforced
                 or (bool(expected_auditor) and isinstance(self.collection_manifest, dict)
                     and self.collection_manifest.get(fid) == expected_auditor)))

    def _fold_blocking_test(self, base, fid, f, r, match, reported, keeps_new_issues):
        if match in _BLOCKING_MATCHES:
            self.test_mismatch.append(fid)
            self.not_discharged.append(fid)
            base["testMatch"].update(answer=reported if reported in TEST_MATCH_ANSWERS else None,
                                     blocking=True)
            base.update(ruling="not-discharged",
                        reason=("break-it test %s: the committed test at %s is not the test role's "
                                "version (or the build session's explained change of it)"
                                % (match, (f.get("breakIt") or {}).get("path"))))
            # axis: a blocking test mismatch keeps the new issues a not-discharged result raised — see bite-proof record c1l11f_wo_d_exempt_and_new_issues
            if keeps_new_issues:
                self.new_issues.extend(_valid_new_issues(r.get("newIssues"), fid))
            self.audits.append(base)
            return True
        return False

    def _fold_checks_fault(self, base, fid, f, r):
        # Every result answers the three checks, whatever its ruling; a result that does not is
        # refused here exactly as the submit guard refuses it.
        checks_fault = audit_checks_fault(r, f)
        if checks_fault is not None:
            self.malformed.append(fid)
            self.not_discharged.append(fid)
            base.update(ruling="not-discharged", reason="audit refused: %s" % checks_fault)
            self.audits.append(base)
            return True
        return False

    def _collect_places(self, base, fid, f, r):
        # A target whose kind of mistake names other places owes an answer for every one of them. A place
        # answered `fixed: false`, or not answered, leaves the fix incomplete: the ruling is not discharged. The
        # per-place results ride the audit entry (`places`) whatever the ruling, for the driver to write onto
        # the finding. A target naming no place is judged exactly as before.
        # axis: every place the kind of mistake names must be answered fixed or the clearing ruling is refused — see bite-proof record c4_wo1_kind
        placed = judge_places(f, r)
        if placed is not None:
            base["places"] = placed["rows"]
            if placed["ignored"]:
                self.places_ignored.append(fid)
                base["placesIgnored"] = [{"file": k[0], "line": k[1]} for k in placed["ignored"]]
            incomplete = placed["unfixed"] + placed["unanswered"]
        else:
            incomplete = []
        return placed, incomplete

    def _fold_weakened_test(self, base, fid, r, match, test_match, reported, keeps_new_issues):
        # axis: a weakened committed test is blocked before an incomplete-place return, so the mandatory restore is scheduled — see bite-proof record c4_wo1_kind
        if match == MATCH_CHANGED_EXPLAINED:
            base["testMatch"]["answer"] = reported
            if reported == "weakened":
                base["testMatch"]["blocking"] = True
                self.test_mismatch.append(fid)
                self.not_discharged.append(fid)
                base.update(ruling="not-discharged",
                            reason="break-it test weakened: %s" % test_match["why"].strip())
                # axis: a weakened-test return keeps the new issues a not-discharged result raised — see bite-proof record c1l11f_wo_d_exempt_and_new_issues
                if keeps_new_issues:
                    self.new_issues.extend(_valid_new_issues(r.get("newIssues"), fid))
                self.audits.append(base)
                return True
        return False

    def _fold_incomplete_places(self, base, fid, r, ruling, placed, incomplete):
        if placed is not None:
            if incomplete and ruling in _CLEARS:
                self.places_unfixed.append(fid)
                self.not_discharged.append(fid)
                parts = []
                if placed["unfixed"]:
                    parts.append("left unfixed: %s" % _places_text(placed["unfixed"]))
                if placed["unanswered"]:
                    parts.append("not answered: %s" % _places_text(placed["unanswered"]))
                candidates = (_valid_new_issues(r.get("newIssues"), fid)
                              if ruling == "discharged-but-new-issue" else [])
                self.new_issues.extend(candidates)
                reason_text = ("the fix leaves a place of the same kind of mistake open (%s)"
                               % "; ".join(parts))
                # An unnamed change reported with an incomplete-place return is kept on the entry and in
                # its reason, so the driver's record of reported changes and the next fixer still carry it.
                reported_unnamed = r.get("unnamedChange")
                if has_usable_unnamed_change(reported_unnamed):
                    base["reportedUnnamedChange"] = reported_unnamed.strip()
                    reason_text += ". Unnamed change: %s" % reported_unnamed.strip()
                base.update(ruling="not-discharged", reason=reason_text)
                self.audits.append(base)
                return True
        return False

    def _fold_failed_check(self, base, fid, r, ruling):
        # A clearing ruling stands only when all three checks are answered `yes`.
        failed = failed_check(r) if ruling in _CLEARS else None
        if failed is not None:
            self.not_discharged.append(fid)
            candidates = (_valid_new_issues(r.get("newIssues"), fid)
                          if ruling == "discharged-but-new-issue" else [])
            self.new_issues.extend(candidates)
            base.update(ruling="not-discharged",
                        reason="audit check failed: %s: %s" % failed)
            self.audits.append(base)
            return True
        return False

    def _review_guard(self, base, fid, f, r, ruling):
        # A clearing ruling whose `testWouldFail` answers `review-guarded` stands only when the fix attempt's
        # whole delta is doctrine prose, judged from the driver-built `fixerDelta` on the target — never from
        # anything the auditor wrote. The answer is recorded only once the entry ends cleared.
        guarded = None
        if ruling in _CLEARS and r["checks"]["testWouldFail"]["answer"] == REVIEW_GUARDED:
            prose, others = prose_only_delta(f)
            # axis: review-guarded clears only a prose-only delta; any other delta folds not-discharged — see bite-proof record audit_review_guarded_2341
            if not prose:
                self.not_discharged.append(fid)
                self.review_guard_refused.append(fid)
                candidates = (_valid_new_issues(r.get("newIssues"), fid)
                              if ruling == "discharged-but-new-issue" else [])
                self.new_issues.extend(candidates)
                base.update(ruling="not-discharged",
                            reason=("audit check failed: testWouldFail: review-guarded clears only a fix "
                                    "whose whole delta is prose; this fix's delta touches %s"
                                    % (", ".join(others) if others else "no recorded delta")))
                self.audits.append(base)
                return True, guarded
            guarded = {"answer": REVIEW_GUARDED, "why": r["checks"]["testWouldFail"]["why"].strip()}
        return False, guarded

    def _test_removal_guard(self, base, fid, f, r, ruling):
        # A clearing ruling whose `testWouldFail` answers `worthless-test-removed` stands only when the fix
        # attempt only removed test lines a worthless-test finding cites (`test_removal_clearance`, C1-C10),
        # judged from the driver-built `fixerDelta`, `fixerRemoval` and the target's own finding fields — never
        # from anything the auditor wrote. The answer is recorded only once the entry ends cleared.
        removal = None
        if ruling in _CLEARS and r["checks"]["testWouldFail"]["answer"] == WORTHLESS_TEST_REMOVED:
            evidence, failing, detail = test_removal_clearance(f)
            # axis: worthless-test-removed clears only when every condition C1-C10 holds; any other fix folds not-discharged — see bite-proof record audit_test_removal_2434
            if evidence is None:
                self.not_discharged.append(fid)
                self.test_removal_refused.append(fid)
                candidates = (_valid_new_issues(r.get("newIssues"), fid)
                              if ruling == "discharged-but-new-issue" else [])
                self.new_issues.extend(candidates)
                base.update(ruling="not-discharged",
                            reason=("audit check failed: testWouldFail: worthless-test-removed clears only a "
                                    "fix that removes test lines a worthless-test finding cites; %s: %s"
                                    % (failing, detail)))
                self.audits.append(base)
                return True, removal
            evidence["finding"] = fid
            removal = {"answer": WORTHLESS_TEST_REMOVED, "why": r["checks"]["testWouldFail"]["why"].strip(),
                       "evidence": evidence}
        return False, removal

    def _fold_malformed_unnamed(self, base, fid, r, ruling, unnamed):
        if ruling in _CLEARS and unnamed is not None and not isinstance(unnamed, str):
            self.malformed.append(fid)
            base.update(ruling="not-discharged",
                        reason="`unnamedChange` is not a string — treated as not-discharged")
            self.audits.append(base)
            self.not_discharged.append(fid)
            return True
        named_seq = r.get("unnamedChangeAllowedBySeq")
        if ruling in _CLEARS and named_seq is not None and not is_decision_seq(named_seq):
            self.malformed.append(fid)
            base.update(ruling="not-discharged",
                        reason="`unnamedChangeAllowedBySeq` is not an integer — treated as not-discharged")
            self.audits.append(base)
            self.not_discharged.append(fid)
            return True

        claim_fault = (unnamed_change_claims_fault(r.get("unnamedChangeFixes"),
                                                   r.get("unnamedChangeReverts"))
                       if ruling in _CLEARS else None)
        if claim_fault is not None:
            self.malformed.append(fid)
            base.update(ruling="not-discharged",
                        reason="`%s` is not a list of non-blank strings — treated as not-discharged"
                        % claim_fault)
            self.audits.append(base)
            self.not_discharged.append(fid)
            return True
        return False

    def _fold_discharged(self, base, fid, reason, has_reason, evidence, unnamed_text, attributed,
                         fixes, reverts, guarded, removal=None):
        if has_reason and unnamed_text and fid not in self.allowed_ids and not attributed:
            self.refuse_unnamed_change(base, fid, unnamed_text, [])
            return
        if has_reason:
            if attributed:
                self.credit_attribution(base, fid, unnamed_text, fixes, reverts)
            elif unnamed_text:
                base["allowedChange"] = unnamed_text
            base.update(ruling="discharged", reason=reason.strip())
            if isinstance(evidence, str) and evidence.strip():
                base["evidence"] = evidence
            self.audits.append(base)
            self.discharged.append(fid)
            # axis: a review-guarded id is listed only once its entry ends cleared — see bite-proof record audit_review_guarded_2341
            if guarded is not None:
                self.review_guarded.append(fid)
                base["reviewGuarded"] = guarded
            # a worthless-test-removed id is listed only once its entry ends cleared, as a review-guarded one is
            if removal is not None:
                self.test_removal_cleared.append(fid)
                base["testRemoval"] = removal
            return
        # reasonless `discharged` is unusable — a bare "fixed" is exactly the unproven claim
        # this fold exists to reject.
        self.malformed.append(fid)
        base.update(ruling="not-discharged",
                    reason="`discharged` with no reason — treated as not-discharged")
        self.audits.append(base)
        self.not_discharged.append(fid)
        return

    def _fold_discharged_new_issue(self, base, fid, r, reason, has_reason, evidence, unnamed_text,
                                   attributed, fixes, reverts, guarded, removal=None):
        candidates = _valid_new_issues(r.get("newIssues"), fid)
        if candidates and unnamed_text and fid not in self.allowed_ids and not attributed:
            self.refuse_unnamed_change(base, fid, unnamed_text, candidates)
            return
        if candidates:
            if attributed:
                self.credit_attribution(base, fid, unnamed_text, fixes, reverts)
            elif unnamed_text:
                base["allowedChange"] = unnamed_text
            base.update(ruling="discharged-but-new-issue",
                        reason=reason.strip() if has_reason else "fix discharged; new issue emitted")
            if isinstance(evidence, str) and evidence.strip():
                base["evidence"] = evidence
            self.audits.append(base)
            self.new_issues.extend(candidates)
            self.discharged.append(fid)
            if guarded is not None:
                self.review_guarded.append(fid)
                base["reviewGuarded"] = guarded
            if removal is not None:
                self.test_removal_cleared.append(fid)
                base["testRemoval"] = removal
            return
        # a discharged-but-new-issue with no usable candidate is an unusable claim.
        self.malformed.append(fid)
        base.update(ruling="not-discharged",
                    reason="`discharged-but-new-issue` with no usable newIssues — treated as not-discharged")
        self.audits.append(base)
        self.not_discharged.append(fid)
        return

    def _fold_not_discharged(self, base, fid, r, reason, has_reason, unnamed_text, expected_auditor,
                             keeps_new_issues):
        mv = self.collection_manifest.get(fid) if isinstance(self.collection_manifest, dict) else None
        if isinstance(mv, str) and mv and mv == expected_auditor:
            base["auditor"] = mv  # a completed rejection by the selected auditor is a reviewer that ran
        kept_reason = reason.strip() if has_reason else "not discharged"
        if unnamed_text:
            # keep the auditor's account of the unnamed change: the next fixer reads it from
            # the recorded reason (priorAudit.reason), so it knows what to undo.
            kept_reason += " Unnamed change: " + unnamed_text
        base.update(ruling="not-discharged", reason=kept_reason)
        # axis: a not-discharged arm keeps the new issues its result raised, as a cleared audit's are kept — see bite-proof record c1l11f_wo_d_exempt_and_new_issues
        if keeps_new_issues:
            self.new_issues.extend(_valid_new_issues(r.get("newIssues"), fid))
        self.audits.append(base)
        self.not_discharged.append(fid)
        return

    def _fold_unrecognized(self, base, fid, ruling):
        # Unknown ruling string (or a non-str) → fail-closed not-discharged + malformed.
        self.malformed.append(fid)
        base.update(ruling="not-discharged",
                    reason="unrecognized ruling %r — treated as not-discharged" % (ruling,))
        self.audits.append(base)
        self.not_discharged.append(fid)

    def outcome(self):
        unmatched = [rid for rid in self.by_id if rid not in self.matched_ids]
        return {
            "audits": self.audits,
            "discharged": self.discharged,
            "notDischarged": self.not_discharged,
            "newIssues": self.new_issues,
            "unaudited": self.unaudited,
            "ambiguous": sorted(self.ambiguous_ids),
            "malformed": self.malformed,
            "unmatched": unmatched,
            "unauthenticated": self.unauthenticated,
            "echoMismatch": self.echo_mismatch,
            "unnamedChange": self.unnamed_change,
            "attributedChange": self.attributed_change,
            "testMismatch": self.test_mismatch,
            "placesUnfixed": self.places_unfixed,
            "placesIgnored": self.places_ignored,
            "reviewGuarded": self.review_guarded,
            "reviewGuardRefused": self.review_guard_refused,
            "testRemovalCleared": self.test_removal_cleared,
            "testRemovalRefused": self.test_removal_refused,
        }


def apply_audit_results(audited, results, expected_auditors=None, collection_manifest=None,
                        carry_fields=(), change_allowed_ids=()):
    """Consume per-finding fix-audit rulings; fail-closed on ambiguity, silence, and malformation.

    `audited`  — findings already carrying a unique staged `id` (via verification.stage_ids)
                 plus file/line/title/severity.
    `results`  — audit-result dicts {id, ruling, reason, evidence?, newIssues?, auditorVendor?}.
                 The in-result `auditorVendor` is ADVISORY only — a claimant-controlled echo that
                 authenticates NOTHING (a fixer or misrouted worker can echo the expected vendor).
    `expected_auditors` — {finding_id: auditor_vendor} recorded by the DRIVER
                 (round_driver._audit_targets) naming the SELECTED independent auditor per target.
                 When None, the target's driver-stamped `auditorVendor` is the fallback selection; a
                 target with neither is not provenance-enforced.
    `collection_manifest` — {result_id: vendor} the DISPATCHING ORCHESTRATOR recorded from its OWN
                 dispatch records, out-of-band from the results (round_driver threads the submit
                 artifact's `collectionManifest`; the library run_loop synthesizes it from the
                 dispatch payload). This — NOT the result's echo — is the trusted provenance: a
                 clearing ruling is authenticated iff `manifest[id]` EXISTS and EQUALS the recorded
                 selected auditor. Provenance rests on the orchestrator's dispatch manifest; the fold
                 cannot cryptographically verify engine identity and does not pretend to.

    `change_allowed_ids` — target ids whose finding carries a ruling that allows the fix to change
                 behaviour the finding does not name. A clearing result that states such a change
                 (`unnamedChange`) stays discharged only for these ids (its audit entry records
                 `allowedChange`); for any other id it is `not-discharged` and listed in
                 `unnamedChange`. A non-string, non-null `unnamedChange` is malformed, and so is a
                 non-integer, non-null `unnamedChangeAllowedBySeq` (the fold, not this function,
                 verifies the named decision before an id is listed here).
                 A clearing result with an `unnamedChange` is also discharged, for an id not in
                 `change_allowed_ids`, when it attributes the change to the DRIVER's own record, read off
                 the target: `unnamedChangeFixes` (ids, each in the target's `roundFindings`) and/or
                 `unnamedChangeReverts` (refs, each in the target's `reportedUnnamedChanges`). Each
                 given claim must verify, and at least one must be given. The entry then records
                 `attributedChange` (the change), `sameRoundFixes` and `revertedChanges` (the claims
                 given), never `allowedChange`; the id is listed in `attributedChange`. A claim that
                 is not None or a list of non-blank strings is malformed. Every result that states
                 an `unnamedChange` records it on its entry as `reportedUnnamedChange`.

    Every result answers the three checks (`audit_checks_fault`); one that does not is malformed and
    not-discharged. A clearing ruling stands only on three `yes` answers, or on `yes` for `right` and
    `brokeNothing` with `review-guarded` for `testWouldFail` when the target's driver-built `fixerDelta`
    shows the fix attempt's whole delta is prose (`prose_only_delta`); with any other delta it is
    not-discharged and listed in `reviewGuardRefused`, and a cleared one is listed in `reviewGuarded`
    and its entry records `reviewGuarded: {answer, why}`. A clearing ruling may instead answer `worthless-test-removed`
    for `testWouldFail` (`right` and `brokeNothing` still `yes`); it stands only when `test_removal_clearance`
    finds every condition C1-C10 true of the target's driver-built `fixerDelta`, `fixerRemoval`, own finding
    fields and `batchFindings` (the fix only removes test lines a worthless-test finding cites); otherwise it is
    not-discharged and listed in `testRemovalRefused`, its reason naming the first failing condition, and a
    cleared one is listed in `testRemovalCleared` and its entry records `testRemoval: {answer, why, evidence}`.
    A target carrying `breakIt`
    is blocked (not-discharged, listed in `testMismatch`) when its `match` is `missing` or
    `changed-unexplained`, or is `changed-explained` and the result's `testMatch` says `weakened`; each
    of its `audits` entries records `testMatch: {match, answer, blocking}`. Only a target that has a
    result is listed in `testMismatch`.

    Returns {audits, discharged, notDischarged, newIssues, unaudited, ambiguous, malformed,
    unmatched, unauthenticated, echoMismatch, unnamedChange, attributedChange, testMismatch,
    placesUnfixed, placesIgnored, reviewGuarded, reviewGuardRefused, testRemovalCleared, testRemovalRefused}. Each `audits` entry
    carries the EFFECTIVE (post-fail-closed) ruling. The disclosure lists (unaudited/ambiguous/malformed/unauthenticated)
    are subsets of notDischarged that name WHY the finding could not be certified discharged;
    `unmatched` names results that hit no finding. `unauthenticated` names clearing rulings the
    orchestrator's manifest could not authenticate (missing entry, or manifest ≠ the selected
    independent auditor). `echoMismatch` names discharged findings whose advisory in-result echo
    disagreed with the governing manifest (disclosed, but the manifest governed → still discharged).
    """
    by_id, seen_ids, ambiguous_ids = _index_results(results)

    if not isinstance(audited, list):
        audited = []

    duplicate_target_ids = _duplicate_target_ids(audited)
    ambiguous_ids |= duplicate_target_ids

    fold = _AuditFold(by_id, ambiguous_ids, duplicate_target_ids, expected_auditors,
                      collection_manifest, carry_fields, change_allowed_ids)
    for f in audited:
        if not isinstance(f, dict):
            continue
        fold.fold_target(f)
    return fold.outcome()
