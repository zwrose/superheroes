#!/usr/bin/env python3
"""Repeat marks: which new findings of a round repeat an earlier finding of the PR, and what a repeat keeps.

An earlier finding is a session ledger row decided in a round before this one, or a finding of the PR's
latest earlier review record. A repeat is a new finding the synthesis judge names (by the order's `eN` ref)
or whose identity key equals an earlier finding's; exact identity is the floor and wins over a name.
`decide` is the one home of the keep-or-new decision table; no other site decides it. A kept repeat
keeps the earlier finding's outcome; a repeat that is not kept routes as a new finding.

Pure except `code_changed` (one `git diff --quiet`) and `read_file`; stdlib plus sibling modules; never
raises on bad input.
"""
import copy
import json
import subprocess

import review_findings_schema
import session_contract
import verification

FIXED, SHOWN_WRONG = review_findings_schema.OUTCOMES[:2]
RULING = review_findings_schema.OUTCOMES[4]
_SETTLED = frozenset(review_findings_schema.OUTCOMES[2:])
_GIT_TIMEOUT_SECONDS = 30
MATCH_JUDGE = "judge"
MATCH_EXACT_ONLY = "exact-only"


def _plain_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _text(value):
    return value if isinstance(value, str) and value.strip() else None


def disposition_of(outcome):
    """The ledger disposition a kept outcome is written as, so the driver never reads it as open."""
    return "refuted" if outcome == SHOWN_WRONG else outcome


def decide(outcome, grade_verdict, changed):
    """The decision table: ``(kept, fixHolds)`` for a repeat of an earlier finding that ended ``outcome``.

    ``grade_verdict`` is the new finding's own verifier verdict this round (confirmed / plausible / wrong)
    or None; ``changed`` is whether the code changed since the earlier judgment (a bool, or a callable
    read only when the table needs it). ``fixHolds`` is only meaningful for a ``fixed`` earlier outcome."""
    if outcome == FIXED:
        # axis: a refuted repeat of a fixed finding keeps `fixed`, the fix holds — see bite-proof record c1l8a_repeat_marks_module
        if grade_verdict == "wrong":
            return True, True
        return False, False
    if outcome == SHOWN_WRONG:
        if callable(changed):
            changed = changed()
        if changed and grade_verdict != "wrong":
            return False, None
        return True, None
    if isinstance(outcome, str) and outcome in _SETTLED:
        return True, None
    return False, None


def code_changed(repo_root, earlier_head, now_head):
    """True unless git shows the same tree at both heads; an unreadable head or a failed run is a change."""
    heads = (earlier_head, now_head)
    if not _text(repo_root) or not all(_text(h) and not h.startswith("-") for h in heads):
        return True
    try:
        done = subprocess.run(["git", "-C", repo_root, "diff", "--quiet", earlier_head, now_head, "--"],
                              capture_output=True, timeout=_GIT_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.SubprocessError):
        return True
    return done.returncode != 0


def opaque_key(finding):
    """The review record's stored key for a finding (`review_record._key`)."""
    import review_record  # lazy: the closure of this module stays small
    return review_record._key(finding)


def _entry(source, key, finding, outcome, **extra):
    row = {"source": source, "key": key, "outcome": outcome,
           "id": finding.get("id") if isinstance(finding.get("id"), str) else None,
           "file": finding.get("file"), "line": finding.get("line"), "title": finding.get("title")}
    # the finding's own earlier link, so a re-match of the finding to itself can keep it
    link = finding.get("repeatOf")
    if isinstance(link, dict):
        row["repeatOf"] = copy.deepcopy(link)
    row.update(extra)
    return row


def read_inputs(state):
    """``(by_key, rulings, exempt)`` the record writer's `_decide` reads, from a driver ``state``; a ledger the
    writer could not read, or a state that is not an object, gives the empty inputs (nothing is pooled)."""
    import review_record_session  # lazy: the closure of this module stays small
    try:
        return review_record_session.decision_inputs(state if isinstance(state, dict) else {})
    except review_record_session.Refusal:
        return {}, {}, {}


def session_entry(row, round_no, inputs):
    """The pool entry for a ledger row decided before ``round_no``, else None.

    The outcome is the record writer's own (`review_record_session.row_decision` over ``inputs``, from
    `read_inputs`): a row is read through its `mergedInto` chain to the representative (an unresolvable chain
    is undecided), and the representative's `dispositionRound` is the round it was decided in. The entry
    carries the row's own identity fields."""
    if not isinstance(row, dict):
        return None
    import review_record_session  # lazy: the closure of this module stays small
    # axis: a ledger row pools with the outcome the record writer's decision gives it, never a reading of its own — see bite-proof record c1l8_wo_a_repeat_marks
    outcome, rep = review_record_session.row_decision(row, inputs)
    key = session_contract.finding_identity_key(row)
    decided = rep.get("dispositionRound") if isinstance(rep, dict) else None
    if outcome is None or not key or not _plain_int(decided) or decided >= round_no:
        return None
    grade = row.get("grade")
    return _entry("session", key, row, outcome, round=decided,
                  family=copy.deepcopy(session_contract.disposition_family_snapshot(row)),
                  grade=dict(grade) if isinstance(grade, dict) else None)


def record_entry(finding):
    """The pool entry for one finding of the earlier review record, else None (malformed); an undecided
    finding (no outcome) is pooled with outcome None, which ``decide`` reads as new.

    The entry's ``head`` (the commit the finding was judged on) is None: a record finding names no such
    commit, and the record's final commit is only where its review ended, so the judged head is unknown and
    `code_changed` reads the change as a change."""
    if not isinstance(finding, dict):
        return None
    outcome = finding.get("outcome")
    outcome = outcome if isinstance(outcome, str) and outcome in review_findings_schema.OUTCOME_SET else None
    key = finding.get(session_contract.FINDING_KEY_FIELD)
    if not _text(key):
        if not (_text(finding.get("file")) and _text(finding.get("title"))):
            return None
        key = opaque_key(finding)
    # axis: a record finding's judged head is unknown, so a repeat of one closed as wrong reads as changed code — see bite-proof record c1l8_wo_a_repeat_marks
    return _entry("record", key, finding, outcome, head=None) if _text(key) else None


def read_earlier_findings(payload):
    """``(record entries, unavailable reason)`` from the parsed `review_record.py read` output.

    Only ``review-record-missing`` is a silent "no earlier record"; any other refusal or a malformed
    object names its reason."""
    if not isinstance(payload, dict):
        return [], "malformed"
    if payload.get("ok") is False:
        reason = payload.get("reason")
        return [], (None if reason == "review-record-missing" else _text(reason) or "refused")
    findings = payload.get("findings")
    if payload.get("ok") is not True or not isinstance(findings, list):
        return [], "malformed"
    entries = [e for e in (record_entry(f) for f in findings) if e is not None]
    return entries, None


def read_file(path):
    """``(parsed object or None, record entries, unavailable reason)`` for the `--earlier-findings` file."""
    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except FileNotFoundError:
        return None, [], "file-missing"
    except OSError:
        return None, [], "unreadable"
    except ValueError:
        return None, [], "not-json"
    entries, reason = read_earlier_findings(payload)
    return (payload if isinstance(payload, dict) else None), entries, reason


def build_pool(state, round_no, record_entries):
    """The earlier-findings pool in order — session rows (ledger order), then record findings — each with
    its ``eN`` ref. A record finding the session already holds (same stored key) is not listed twice.

    The session rows are read from the driver ``state`` as the record writer reads them (`read_inputs`)."""
    inputs = read_inputs(state)
    pool = [e for e in (session_entry(row, round_no, inputs) for row in inputs[0].values()) if e is not None]
    held = {e["key"] for e in pool}
    held |= {opaque_key({session_contract.FINDING_KEY_FIELD: e["key"]}) for e in pool}
    for entry in record_entries or ():
        if isinstance(entry, dict) and entry.get("key") not in held:
            held.add(entry["key"])
            pool.append(dict(entry))
    for index, entry in enumerate(pool, 1):
        entry["ref"] = "e%d" % index
    return pool


def order_list(pool):
    """The order input's ``earlier`` list."""
    return [{k: e.get(k) for k in ("ref", "id", "file", "line", "title", "outcome")} for e in pool or ()]


def exact_match(finding, pool):
    """The pool entry whose identity key is the finding's own, else None."""
    # axis: exact identity is the floor of repeat marking, whatever the judge named — see bite-proof record c1l8a_repeat_marks_module
    raw = session_contract.finding_identity_key(finding)
    stored = None
    for entry in pool or ():
        if entry["source"] == "session":
            if raw == entry["key"]:
                return entry
            continue
        stored = stored or opaque_key(finding)
        if stored == entry["key"]:
            return entry
    return None


def judge_refs(grouping):
    """``{member id: ref}`` for the groups that name an earlier finding."""
    refs = {}
    for group in grouping if isinstance(grouping, list) else ():
        ref = group.get("repeatOf") if isinstance(group, dict) else None
        members = group.get("member_ids") if isinstance(group, dict) else None
        if isinstance(ref, str) and isinstance(members, list):
            refs.update({m: ref for m in members if isinstance(m, str)})
    return refs


def mark_repeats(staged, pool, refs):
    """``{staged id: (entry, "exact" | "judge")}``: exact identity first, then the judge's name."""
    by_ref = {e["ref"]: e for e in pool or ()}
    marks = {}
    for finding in staged:
        sid = finding.get("id") if isinstance(finding, dict) else None
        if not isinstance(sid, str):
            continue
        entry = exact_match(finding, pool)
        if entry is not None:
            marks[sid] = (entry, "exact")
        elif refs.get(sid) in by_ref:
            marks[sid] = (by_ref[refs[sid]], "judge")
    return marks


def grouping_fault(survivors, refuted, grouping, pool):
    """Structured fault (the shape of `verification.grouping_coverage_fault`) or None.

    A group's ``repeatOf`` is None or a ref in ``pool``; every member id is one of this round's staged ids;
    a refuted id sits in at most one group; survivors are covered exactly once once refuted ids are set aside."""
    if not isinstance(grouping, list):
        return None
    refs = {e["ref"] for e in pool or ()}
    # axis: refuted ids are set aside before survivor coverage is checked — see bite-proof record c1l8a_repeat_marks_module
    refuted_ids = {r["id"] for r in refuted or () if isinstance(r, dict) and isinstance(r.get("id"), str)}
    seen_refuted, stripped = set(), []
    for index, group in enumerate(grouping):
        if not isinstance(group, dict):
            continue
        ref = group.get("repeatOf")
        # axis: a repeat name that is not an earlier-finding ref of the order is refused — see bite-proof record c1l8a_repeat_marks_module
        if ref is not None and (not isinstance(ref, str) or ref not in refs):
            return {"kind": "repeat_ref", "member_id": ref, "index": index}
        members = []
        for member in group.get("member_ids") if isinstance(group.get("member_ids"), list) else ():
            if isinstance(member, str) and member in refuted_ids:
                if member in seen_refuted:
                    return {"kind": "duplicate_member", "member_id": member, "index": index}
                seen_refuted.add(member)
            else:
                members.append(member)
        if members:
            stripped.append(dict(group, member_ids=members))
    ids = sorted(s["id"] for s in survivors if isinstance(s, dict) and isinstance(s.get("id"), str))
    if grouping and not stripped and ids:
        return {"kind": "omits", "member_id": ids[0]}
    return verification.grouping_coverage_fault(survivors, stripped)


def strip_groups(grouping, removed_ids):
    """``grouping`` without ``removed_ids`` in any group; a group left empty is removed (nothing is dropped)."""
    if not isinstance(grouping, list):
        return grouping
    out = []
    for group in grouping:
        members = group.get("member_ids") if isinstance(group, dict) else None
        if not isinstance(members, list):
            out.append(group)
            continue
        left = [m for m in members if not (isinstance(m, str) and m in removed_ids)]
        if left:
            out.append(dict(group, member_ids=left))
    return out


def kept_reason(entry, fix_holds):
    """The reason a kept repeat's row carries."""
    key = str(entry.get("key"))
    named = entry.get("id") or (key if len(key) <= 40 else key[:40] + "…")
    reason = "repeat of %s; keeps its earlier outcome (%s)" % (named, entry["outcome"])
    return reason + "; the verifier found the fix still holds" if fix_holds else reason
