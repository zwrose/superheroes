#!/usr/bin/env python3
"""Package-read audit trail writer and conformance reader (#937).

Deterministic, stdlib-only machine module that appends structured records to a
markdown audit trail and checks that every FR-32 audit element was recorded and
every finding reached disposition and verification.
"""
import argparse
import json
import sys

import md_fence

# --- vocabulary: ONE authoritative home (CONVENTIONS §11) --------------------

SCHEMA = "package-read-audit/1"
RECORD_MARKER = "<!-- package-read-audit:record -->"
TRAIL_HEADING = "# Package-read audit trail"

RECORD_KIND_INVOCATION = "invocation"
RECORD_KIND_ROUND = "round"
RECORD_KIND_VERIFICATION = "verification"
RECORD_KINDS = frozenset({
    RECORD_KIND_INVOCATION,
    RECORD_KIND_ROUND,
    RECORD_KIND_VERIFICATION,
})

LENS_SPEC_CONTRADICTION = "spec-contradiction"
LENS_REGISTER_DRIFT = "register-drift"
LENS_COVERAGE_EXACTLY_ONCE = "coverage-exactly-once"
LENS_COLLISIONS = "collisions"
LENS_DOD_ADEQUACY = "dod-adequacy"
LENSES = frozenset({
    LENS_SPEC_CONTRADICTION,
    LENS_REGISTER_DRIFT,
    LENS_COVERAGE_EXACTLY_ONCE,
    LENS_COLLISIONS,
    LENS_DOD_ADEQUACY,
})

PART_STATUS_UNREVIEWED = "unreviewed"
PART_STATUS_REVIEWED = "reviewed"
PART_STATUSES = frozenset({PART_STATUS_UNREVIEWED, PART_STATUS_REVIEWED})

CONTROL_PROBE_ENGAGED = "engaged"
CONTROL_PROBE_NOT_ENGAGED = "not-engaged"
CONTROL_PROBE_NOT_APPLICABLE = "not-applicable"
CONTROL_PROBE_READS = frozenset({
    CONTROL_PROBE_ENGAGED,
    CONTROL_PROBE_NOT_ENGAGED,
    CONTROL_PROBE_NOT_APPLICABLE,
})

WEIGHT_LIGHT = "light"
WEIGHT_FULL = "full"
WEIGHTS = frozenset({WEIGHT_LIGHT, WEIGHT_FULL})

DISPOSITION_PACKAGE_FIX = "package-fix"
DISPOSITION_SPEC_AMENDMENT = "spec-amendment"
DISPOSITION_REFUTATION = "refutation"
DISPOSITION_DECLINED_EXTENSION = "declined-extension"
DISPOSITIONS = frozenset({
    DISPOSITION_PACKAGE_FIX,
    DISPOSITION_SPEC_AMENDMENT,
    DISPOSITION_REFUTATION,
    DISPOSITION_DECLINED_EXTENSION,
})

OUTCOME_VERIFIED = "verified"
OUTCOME_FAILED = "failed"
OUTCOMES = frozenset({OUTCOME_VERIFIED, OUTCOME_FAILED})

SYNC_RESULT_PASS = "pass"
SYNC_RESULT_FAIL = "fail"
SYNC_RESULT_UNDECIDED = "undecided"
SYNC_RESULTS = frozenset({SYNC_RESULT_PASS, SYNC_RESULT_FAIL, SYNC_RESULT_UNDECIDED})

RESULT_RECORDED = "recorded"
RESULT_REFUSED = "refused"
WRITE_RESULTS = frozenset({RESULT_RECORDED, RESULT_REFUSED})

RESULT_CONFORMING = "conforming"
RESULT_NONCONFORMING = "nonconforming"
RESULT_UNDECIDED = "undecided"
CHECK_RESULTS = frozenset({RESULT_CONFORMING, RESULT_NONCONFORMING, RESULT_UNDECIDED})

REFUSAL_TRAIL_UNREADABLE = "trail-unreadable"
REFUSAL_TRAIL_MISSING = "trail-missing"
REFUSAL_TRAIL_MALFORMED = "trail-malformed"
REFUSAL_INVOCATION_DUPLICATE = "invocation-duplicate"
REFUSAL_INVOCATION_UNKNOWN = "invocation-unknown"
REFUSAL_ROUND_DUPLICATE = "round-duplicate"
REFUSAL_ROUND_EXCEEDS_CEILING = "round-exceeds-ceiling"
REFUSAL_ROUND_INVALID = "round-invalid"
REFUSAL_LENS_UNRECOGNIZED = "lens-unrecognized"
REFUSAL_PART_MALFORMED = "part-malformed"
REFUSAL_PART_STATUS_UNRECOGNIZED = "part-status-unrecognized"
REFUSAL_CONTROL_PROBE_UNRECOGNIZED = "control-probe-unrecognized"
REFUSAL_FINDING_MALFORMED = "finding-malformed"
REFUSAL_FINDING_DUPLICATE = "finding-duplicate"
REFUSAL_FINDING_UNKNOWN = "finding-unknown"
REFUSAL_VERIFICATION_DUPLICATE = "verification-duplicate"
REFUSAL_DISPOSITION_NOT_ALLOWED_FOR_LENS = "disposition-not-allowed-for-lens"
REFUSAL_EVIDENCE_EMPTY = "evidence-empty"
REFUSAL_DISPOSITION_UNRECOGNIZED = "disposition-unrecognized"
REFUSAL_OUTCOME_UNRECOGNIZED = "outcome-unrecognized"
REFUSAL_SYNC_CHECK_MALFORMED = "sync-check-malformed"
REFUSAL_SYNC_CHECK_DUPLICATE = "sync-check-duplicate"
REFUSAL_SYNC_RESULT_UNRECOGNIZED = "sync-result-unrecognized"
REFUSAL_WEIGHT_UNRECOGNIZED = "weight-unrecognized"
REFUSAL_CEILING_INVALID = "ceiling-invalid"
REFUSAL_MEASURABLE_INVALID = "measurable-invalid"
REFUSAL_SEATS_MISSING = "seats-missing"
REFUSAL_USAGE = "usage"
REFUSAL_INTERNAL_ERROR = "internal-error"
REFUSAL_REASONS = frozenset({
    REFUSAL_TRAIL_UNREADABLE,
    REFUSAL_TRAIL_MISSING,
    REFUSAL_TRAIL_MALFORMED,
    REFUSAL_INVOCATION_DUPLICATE,
    REFUSAL_INVOCATION_UNKNOWN,
    REFUSAL_ROUND_DUPLICATE,
    REFUSAL_ROUND_EXCEEDS_CEILING,
    REFUSAL_ROUND_INVALID,
    REFUSAL_LENS_UNRECOGNIZED,
    REFUSAL_PART_MALFORMED,
    REFUSAL_PART_STATUS_UNRECOGNIZED,
    REFUSAL_CONTROL_PROBE_UNRECOGNIZED,
    REFUSAL_FINDING_MALFORMED,
    REFUSAL_FINDING_DUPLICATE,
    REFUSAL_FINDING_UNKNOWN,
    REFUSAL_VERIFICATION_DUPLICATE,
    REFUSAL_DISPOSITION_NOT_ALLOWED_FOR_LENS,
    REFUSAL_EVIDENCE_EMPTY,
    REFUSAL_DISPOSITION_UNRECOGNIZED,
    REFUSAL_OUTCOME_UNRECOGNIZED,
    REFUSAL_SYNC_CHECK_MALFORMED,
    REFUSAL_SYNC_CHECK_DUPLICATE,
    REFUSAL_SYNC_RESULT_UNRECOGNIZED,
    REFUSAL_WEIGHT_UNRECOGNIZED,
    REFUSAL_CEILING_INVALID,
    REFUSAL_MEASURABLE_INVALID,
    REFUSAL_SEATS_MISSING,
    REFUSAL_USAGE,
    REFUSAL_INTERNAL_ERROR,
})

UNDECIDED_TRAIL_UNREADABLE = "trail-unreadable"
UNDECIDED_TRAIL_MISSING = "trail-missing"
UNDECIDED_TRAIL_EMPTY = "trail-empty"
UNDECIDED_TRAIL_MALFORMED = "trail-malformed"
UNDECIDED_INVOCATION_UNKNOWN = "invocation-unknown"
UNDECIDED_USAGE = "usage"
UNDECIDED_INTERNAL_ERROR = "internal-error"
UNDECIDED_REASONS = frozenset({
    UNDECIDED_TRAIL_UNREADABLE,
    UNDECIDED_TRAIL_MISSING,
    UNDECIDED_TRAIL_EMPTY,
    UNDECIDED_TRAIL_MALFORMED,
    UNDECIDED_INVOCATION_UNKNOWN,
    UNDECIDED_USAGE,
    UNDECIDED_INTERNAL_ERROR,
})

NONCONFORMITY_ROUND_MISSING = "round-missing"
NONCONFORMITY_ELEMENT_MISSING = "element-missing"
NONCONFORMITY_FINDING_UNVERIFIED = "finding-unverified"
NONCONFORMITY_DISPOSITION_MISMATCH = "disposition-mismatch"
NONCONFORMITY_DISPOSITION_NOT_ALLOWED_FOR_LENS = "disposition-not-allowed-for-lens"
NONCONFORMITY_REFUTATION_EVIDENCE_MISSING = "refutation-evidence-missing"
NONCONFORMITY_SYNC_CHECK_MISSING = "sync-check-missing"
NONCONFORMITY_SYNC_CHECK_INCOMPLETE = "sync-check-incomplete"
NONCONFORMITY_SYNC_CHECK_FAILED = "sync-check-failed"
NONCONFORMITY_KINDS = frozenset({
    NONCONFORMITY_ROUND_MISSING,
    NONCONFORMITY_ELEMENT_MISSING,
    NONCONFORMITY_FINDING_UNVERIFIED,
    NONCONFORMITY_DISPOSITION_MISMATCH,
    NONCONFORMITY_DISPOSITION_NOT_ALLOWED_FOR_LENS,
    NONCONFORMITY_REFUTATION_EVIDENCE_MISSING,
    NONCONFORMITY_SYNC_CHECK_MISSING,
    NONCONFORMITY_SYNC_CHECK_INCOMPLETE,
    NONCONFORMITY_SYNC_CHECK_FAILED,
})

SPEC_CONTRADICTION_DISPOSITIONS = frozenset({
    DISPOSITION_PACKAGE_FIX,
    DISPOSITION_SPEC_AMENDMENT,
    DISPOSITION_REFUTATION,
})

EXIT_RECORDED = 0
EXIT_REFUSED = 1
EXIT_CONFORMING = 0
EXIT_NONCONFORMING = 1
EXIT_UNDECIDED = 2

WRITE_RESULT_FIELDS = (
    "schema", "result", "ok", "reason", "detail", "trail", "invocation", "record",
)
CHECK_RESULT_FIELDS = (
    "schema", "result", "ok", "reason", "detail", "trail", "invocations", "findings",
)
NONCONFORMITY_FIELDS = ("kind", "invocation", "detail")
INVOCATION_SUMMARY_FIELDS = (
    "invocation", "weight", "ceiling", "seats", "roundsRecorded",
    "findingsRecorded", "syncChecks", "converged", "ceilingReached", "parkOwed",
)

# Projection readings for trail-ordered invocation records (#937).
READING_LATEST_WINS = "latest-wins"
READING_EVERY_RECORD = "every-record"
READING_POSITION = "position"


def _read_lines(path):
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError):
        return None
    lines = text.split("\n")
    if text.endswith("\n"):
        lines = lines[:-1]
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def _trail_exists(path):
    try:
        with open(path, encoding="utf-8"):
            return True
    except OSError:
        return False


def _format_record(obj):
    payload = json.dumps(obj, sort_keys=True, indent=1)
    return (
        "\n"
        + RECORD_MARKER
        + "\n"
        + "```json\n"
        + payload
        + "\n"
        + "```\n"
    )


def _append_record(path, obj, create=False):
    block = _format_record(obj)
    if create:
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(TRAIL_HEADING + "\n")
            fh.write(block)
        return
    with open(path, "a", encoding="utf-8", newline="") as fh:
        if fh.tell() > 0:
            fh.write("\n")
        fh.write(block.lstrip("\n"))


def _parse_records(lines):
    """Parse marked audit records from trail lines.

    Returns (records, error_reason, error_detail) where error_reason is a
    REFUSAL_TRAIL_MALFORMED / UNDECIDED_TRAIL_MALFORMED token on failure.
    """
    fence_scan = md_fence.scan(lines)
    if fence_scan.unterminated_opener_line is not None:
        return None, REFUSAL_TRAIL_MALFORMED, (
            "unterminated code fence at line %d" % fence_scan.unterminated_opener_line
        )

    inert = fence_scan.inert
    kinds = fence_scan.kinds
    records = []
    i = 0
    n = len(lines)

    while i < n:
        if inert[i]:
            i += 1
            continue
        if lines[i] != RECORD_MARKER:
            i += 1
            continue

        marker_line = i + 1
        if i + 1 >= n or kinds[i + 1] != md_fence.KIND_OPENER:
            return None, REFUSAL_TRAIL_MALFORMED, (
                "record marker at line %d is not followed by a fenced JSON block"
                % marker_line
            )

        opener_idx = i + 1
        j = opener_idx + 1
        json_lines = []
        while j < n:
            if kinds[j] == md_fence.KIND_CLOSER:
                break
            if kinds[j] == md_fence.KIND_CONTENT:
                json_lines.append(lines[j])
            j += 1
        if j >= n or kinds[j] != md_fence.KIND_CLOSER:
            return None, REFUSAL_TRAIL_MALFORMED, (
                "unterminated fenced JSON block opened at line %d" % (opener_idx + 1)
            )

        raw = "\n".join(json_lines).strip()
        if not raw:
            return None, REFUSAL_TRAIL_MALFORMED, (
                "empty fenced JSON block at line %d" % (opener_idx + 1)
            )
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            return None, REFUSAL_TRAIL_MALFORMED, (
                "invalid JSON at line %d: %s" % (opener_idx + 1, exc)
            )
        if not isinstance(payload, dict):
            return None, REFUSAL_TRAIL_MALFORMED, (
                "fenced JSON at line %d is not a JSON object" % (opener_idx + 1)
            )
        kind = payload.get("kind")
        if kind not in RECORD_KINDS:
            return None, REFUSAL_TRAIL_MALFORMED, (
                "record at line %d has unrecognized kind %r" % (marker_line, kind)
            )
        records.append(payload)
        i = j + 1

    return records, None, None


def _load_trail(path):
    if not _trail_exists(path):
        return None, REFUSAL_TRAIL_MISSING, "trail file does not exist"
    lines = _read_lines(path)
    if lines is None:
        return None, REFUSAL_TRAIL_UNREADABLE, "trail file is missing or not valid UTF-8"
    records, reason, detail = _parse_records(lines)
    if records is None:
        return None, reason, detail
    return records, None, None


def _group_records(records):
    invocations = {}
    rounds_by_inv = {}
    verifications_by_inv = {}

    for record in records:
        kind = record["kind"]
        inv_id = record.get("invocation")
        if kind == RECORD_KIND_INVOCATION:
            invocations[inv_id] = record
        elif kind == RECORD_KIND_ROUND:
            rounds_by_inv.setdefault(inv_id, []).append(record)
        elif kind == RECORD_KIND_VERIFICATION:
            verifications_by_inv.setdefault(inv_id, []).append(record)

    return invocations, rounds_by_inv, verifications_by_inv


def _disposition_allowed_for_lens(lens, disposition):
    if disposition == DISPOSITION_DECLINED_EXTENSION:
        return lens != LENS_SPEC_CONTRADICTION
    if lens == LENS_SPEC_CONTRADICTION:
        return disposition in SPEC_CONTRADICTION_DISPOSITIONS
    return disposition in DISPOSITIONS


def _invocation_trail_records(records, inv_id):
    """Return round and verification records for one invocation in trail order."""
    trail_records = []
    for record in records:
        if record.get("invocation") != inv_id:
            continue
        if record.get("kind") in (RECORD_KIND_ROUND, RECORD_KIND_VERIFICATION):
            trail_records.append(record)
    return trail_records


def _project_invocation(records):
    """Project trail-ordered invocation records into a single read model.

    Three readings apply to different questions (see module vocabulary):
    - READING_LATEST_WINS: finding outcome/disposition and per-child sync-check
      result — the last record in trail order wins.
    - READING_EVERY_RECORD: legality of each verification item as written.
    - READING_POSITION: whether verification covers the current round state
      (latest verification record appears after the highest-numbered round).
    """
    rounds = []
    verifications = []
    finding_ids = []
    finding_ids_seen = set()
    finding_lenses = {}
    declined_extension = set()
    latest_outcomes = {}
    latest_sync_by_child = {}
    highest_round = 0
    highest_mechanical_only = False
    highest_round_trail_index = -1
    latest_verification_trail_index = -1

    for trail_index, record in enumerate(records):
        kind = record.get("kind")
        if kind == RECORD_KIND_ROUND:
            rounds.append(record)
            round_no = record.get("round", 0)
            if round_no >= highest_round:
                highest_round = round_no
                highest_mechanical_only = bool(record.get("mechanicalOnly"))
                highest_round_trail_index = trail_index
            for item in record.get("findings", []):
                fid = item.get("finding")
                if fid not in finding_ids_seen:
                    finding_ids.append(fid)
                    finding_ids_seen.add(fid)
                finding_lenses[fid] = item.get("lens")
            for fid in record.get("declinedExtension", []):
                declined_extension.add(fid)
        elif kind == RECORD_KIND_VERIFICATION:
            verifications.append(record)
            latest_verification_trail_index = trail_index
            for item in record.get("findings", []):
                latest_outcomes[item["finding"]] = item
            for check in record.get("syncChecks", []):
                child = check.get("child")
                if child:
                    latest_sync_by_child[child] = check

    rounds_sorted = sorted(rounds, key=lambda r: r.get("round", 0))
    verification_covers_current_state = (
        latest_verification_trail_index > highest_round_trail_index
    )

    return {
        "reading_latest_wins": READING_LATEST_WINS,
        "reading_every_record": READING_EVERY_RECORD,
        "reading_position": READING_POSITION,
        "rounds": rounds_sorted,
        "verifications": verifications,
        "finding_ids": finding_ids,
        "finding_lenses": finding_lenses,
        "declined_extension": declined_extension,
        "latest_outcomes": latest_outcomes,
        "latest_sync_by_child": latest_sync_by_child,
        "highest_round": highest_round,
        "highest_mechanical_only": highest_mechanical_only,
        "has_verification": bool(verifications),
        "verification_covers_current_state": verification_covers_current_state,
    }


def _measurables_children(invocation):
    measurables = invocation.get("measurables")
    if not isinstance(measurables, dict):
        return None
    return measurables.get("children")


def _sync_checks_complete(invocation, latest_sync_by_child):
    expected = _measurables_children(invocation)
    if expected is None:
        return False
    if len(latest_sync_by_child) != expected:
        return False
    return all(
        check.get("result") == SYNC_RESULT_PASS
        for check in latest_sync_by_child.values()
    )


def _summarize_invocation(inv_id, invocation, projection):
    rounds_sorted = projection["rounds"]
    finding_ids = projection["finding_ids"]
    latest_outcomes = projection["latest_outcomes"]
    latest_sync_by_child = projection["latest_sync_by_child"]

    converged = (
        bool(rounds_sorted)
        and projection["has_verification"]
        and projection["verification_covers_current_state"]
        and projection["highest_mechanical_only"]
        and all(
            latest_outcomes.get(fid, {}).get("outcome") == OUTCOME_VERIFIED
            for fid in finding_ids
        )
        and _sync_checks_complete(invocation, latest_sync_by_child)
    )
    ceiling = invocation.get("ceiling", 0)
    highest_round = projection["highest_round"]
    ceiling_reached = bool(rounds_sorted) and highest_round == ceiling
    park_owed = ceiling_reached and not converged

    seats_val = invocation.get("seats")
    if isinstance(seats_val, list):
        seats = list(seats_val)
    else:
        seats = []

    return {
        "invocation": inv_id,
        "weight": invocation.get("weight"),
        "ceiling": ceiling,
        "seats": seats,
        "roundsRecorded": len(rounds_sorted),
        "findingsRecorded": len(finding_ids),
        "syncChecks": list(latest_sync_by_child.values()),
        "converged": converged,
        "ceilingReached": ceiling_reached,
        "parkOwed": park_owed,
    }


def _nonconformities_for_invocation(inv_id, invocation, projection):
    findings = []

    if invocation.get("cause") is None:
        findings.append({
            "kind": NONCONFORMITY_ELEMENT_MISSING,
            "invocation": inv_id,
            "detail": "invocation is missing cause",
        })
    if invocation.get("weight") is None:
        findings.append({
            "kind": NONCONFORMITY_ELEMENT_MISSING,
            "invocation": inv_id,
            "detail": "invocation is missing weight",
        })
    measurables = invocation.get("measurables")
    if not isinstance(measurables, dict) or measurables.get("children") is None:
        findings.append({
            "kind": NONCONFORMITY_ELEMENT_MISSING,
            "invocation": inv_id,
            "detail": "invocation is missing measurables.children",
        })
    if not isinstance(measurables, dict) or measurables.get("registerEntries") is None:
        findings.append({
            "kind": NONCONFORMITY_ELEMENT_MISSING,
            "invocation": inv_id,
            "detail": "invocation is missing measurables.registerEntries",
        })
    if invocation.get("ceiling") is None:
        findings.append({
            "kind": NONCONFORMITY_ELEMENT_MISSING,
            "invocation": inv_id,
            "detail": "invocation is missing ceiling",
        })
    seats = invocation.get("seats")
    if not isinstance(seats, list) or not seats:
        findings.append({
            "kind": NONCONFORMITY_ELEMENT_MISSING,
            "invocation": inv_id,
            "detail": "invocation is missing seats",
        })

    rounds = projection["rounds"]
    if not rounds:
        findings.append({
            "kind": NONCONFORMITY_ROUND_MISSING,
            "invocation": inv_id,
            "detail": "invocation has no round records",
        })
        return findings

    latest_outcomes = projection["latest_outcomes"]
    declined_named = projection["declined_extension"]
    latest_sync_by_child = projection["latest_sync_by_child"]
    has_verification = projection["has_verification"]
    finding_lenses = projection["finding_lenses"]

    for rnd in rounds:
        round_no = rnd.get("round")
        if not rnd.get("lenses"):
            findings.append({
                "kind": NONCONFORMITY_ELEMENT_MISSING,
                "invocation": inv_id,
                "detail": "round %s is missing lenses" % round_no,
            })
        if not rnd.get("parts"):
            findings.append({
                "kind": NONCONFORMITY_ELEMENT_MISSING,
                "invocation": inv_id,
                "detail": "round %s is missing parts" % round_no,
            })
        if rnd.get("controlProbe") is None:
            findings.append({
                "kind": NONCONFORMITY_ELEMENT_MISSING,
                "invocation": inv_id,
                "detail": "round %s is missing controlProbe" % round_no,
            })

    if has_verification:
        for fid in projection["finding_ids"]:
            if fid not in latest_outcomes:
                findings.append({
                    "kind": NONCONFORMITY_FINDING_UNVERIFIED,
                    "invocation": inv_id,
                    "detail": "finding %s has no verification record" % fid,
                })

    for fid in declined_named:
        item = latest_outcomes.get(fid)
        if item is None:
            continue
        if item.get("disposition") != DISPOSITION_DECLINED_EXTENSION:
            findings.append({
                "kind": NONCONFORMITY_DISPOSITION_MISMATCH,
                "invocation": inv_id,
                "detail": (
                    "finding %s is named in declinedExtension but verification "
                    "disposition is %r" % (fid, item.get("disposition"))
                ),
            })

    for fid, item in latest_outcomes.items():
        if item.get("disposition") == DISPOSITION_DECLINED_EXTENSION and fid not in declined_named:
            findings.append({
                "kind": NONCONFORMITY_DISPOSITION_MISMATCH,
                "invocation": inv_id,
                "detail": (
                    "finding %s has disposition declined-extension but no round "
                    "named it in declinedExtension" % fid
                ),
            })

    for ver in projection["verifications"]:
        for item in ver.get("findings", []):
            fid = item.get("finding")
            lens = finding_lenses.get(fid)
            disposition = item.get("disposition")
            if lens is not None and disposition is not None:
                if not _disposition_allowed_for_lens(lens, disposition):
                    findings.append({
                        "kind": NONCONFORMITY_DISPOSITION_NOT_ALLOWED_FOR_LENS,
                        "invocation": inv_id,
                        "detail": (
                            "finding %s with lens %r has disposition %r"
                            % (fid, lens, disposition)
                        ),
                    })

    for ver in projection["verifications"]:
        for item in ver.get("findings", []):
            if item.get("disposition") == DISPOSITION_REFUTATION:
                evidence = item.get("evidence")
                if not evidence or not str(evidence).strip():
                    findings.append({
                        "kind": NONCONFORMITY_REFUTATION_EVIDENCE_MISSING,
                        "invocation": inv_id,
                        "detail": (
                            "finding %s has disposition refutation but no evidence"
                            % item.get("finding")
                        ),
                    })

    if has_verification and not latest_sync_by_child:
        findings.append({
            "kind": NONCONFORMITY_SYNC_CHECK_MISSING,
            "invocation": inv_id,
            "detail": "invocation has verification records but no sync-check entries",
        })
    elif has_verification:
        expected_children = _measurables_children(invocation)
        distinct_count = len(latest_sync_by_child)
        if expected_children is not None and distinct_count != expected_children:
            findings.append({
                "kind": NONCONFORMITY_SYNC_CHECK_INCOMPLETE,
                "invocation": inv_id,
                "detail": (
                    "sync-check covers %d distinct children but measurables.children "
                    "is %d"
                    % (distinct_count, expected_children)
                ),
            })

    for child, check in latest_sync_by_child.items():
        if check.get("result") != SYNC_RESULT_PASS:
            findings.append({
                "kind": NONCONFORMITY_SYNC_CHECK_FAILED,
                "invocation": inv_id,
                "detail": (
                    "sync-check for child %s has result %r"
                    % (child, check.get("result"))
                ),
            })

    return findings


def _make_write_result(
    result,
    ok,
    reason,
    detail,
    trail,
    invocation,
    record,
):
    values = (SCHEMA, result, ok, reason, detail, trail, invocation, record)
    payload = dict(zip(WRITE_RESULT_FIELDS, values))
    assert set(payload) == set(WRITE_RESULT_FIELDS)
    return payload


def _make_check_result(result, ok, reason, detail, trail, invocations, findings):
    values = (SCHEMA, result, ok, reason, detail, trail, invocations, findings)
    payload = dict(zip(CHECK_RESULT_FIELDS, values))
    assert set(payload) == set(CHECK_RESULT_FIELDS)
    return payload


def _refuse(reason, detail, trail=None, invocation=None):
    return _make_write_result(
        RESULT_REFUSED,
        False,
        reason,
        detail,
        trail,
        invocation,
        None,
    )


def _parse_int_nonneg(value, name):
    try:
        num = int(value)
    except (TypeError, ValueError):
        return None, "invalid integer for %s: %r" % (name, value)
    if num < 0:
        return None, "%s must be a non-negative integer" % name
    return num, None


def _parse_colon_pair(value, name):
    if ":" not in value:
        return None, None, "%s must be NAME:VALUE" % name
    left, right = value.split(":", 1)
    if not left or not right:
        return None, None, "%s must be NAME:VALUE" % name
    return left, right, None


def _parse_colon_triple(value, name):
    parts = value.split(":")
    if len(parts) != 3 or not all(parts):
        return None, None, None, "%s must be ID:DISPOSITION:OUTCOME" % name
    return parts[0], parts[1], parts[2], None


def _known_findings_for_invocation(records, inv_id):
    known = {}
    for record in records:
        if record.get("kind") != RECORD_KIND_ROUND:
            continue
        if record.get("invocation") != inv_id:
            continue
        for item in record.get("findings", []):
            known[item["finding"]] = item["lens"]
    return known


def _recorded_finding_ids(records, inv_id):
    ids = set()
    for record in records:
        if record.get("kind") != RECORD_KIND_ROUND:
            continue
        if record.get("invocation") != inv_id:
            continue
        for item in record.get("findings", []):
            ids.add(item["finding"])
    return ids


def _latest_verified_finding_ids(records, inv_id):
    latest = {}
    for record in records:
        if record.get("kind") != RECORD_KIND_VERIFICATION:
            continue
        if record.get("invocation") != inv_id:
            continue
        for item in record.get("findings", []):
            latest[item["finding"]] = item
    return {
        fid
        for fid, item in latest.items()
        if item.get("outcome") == OUTCOME_VERIFIED
    }


def _invocation_ids(records):
    return {
        record["invocation"]
        for record in records
        if record.get("kind") == RECORD_KIND_INVOCATION
    }


def _round_numbers(records, inv_id):
    nums = set()
    for record in records:
        if record.get("kind") != RECORD_KIND_ROUND:
            continue
        if record.get("invocation") != inv_id:
            continue
        nums.add(record.get("round"))
    return nums


def _invocation_ceiling(records, inv_id):
    for record in records:
        if record.get("kind") == RECORD_KIND_INVOCATION and record.get("invocation") == inv_id:
            return record.get("ceiling")
    return None


def verb_open(trail, invocation, cause, weight, children, register_entries, ceiling,
              override, seats):
    if not seats:
        return _refuse(
            REFUSAL_SEATS_MISSING,
            "at least one --seat is required",
            trail=trail,
            invocation=invocation,
        )
    if weight not in WEIGHTS:
        return _refuse(
            REFUSAL_WEIGHT_UNRECOGNIZED,
            "unrecognized weight %r" % weight,
            trail=trail,
            invocation=invocation,
        )
    try:
        ceiling_int = int(ceiling)
    except (TypeError, ValueError):
        return _refuse(
            REFUSAL_CEILING_INVALID,
            "ceiling must be an integer >= 1",
            trail=trail,
            invocation=invocation,
        )
    if ceiling_int < 1:
        return _refuse(
            REFUSAL_CEILING_INVALID,
            "ceiling must be an integer >= 1",
            trail=trail,
            invocation=invocation,
        )

    children_int, err = _parse_int_nonneg(children, "children")
    if children_int is None:
        return _refuse(
            REFUSAL_MEASURABLE_INVALID,
            err,
            trail=trail,
            invocation=invocation,
        )
    register_int, err = _parse_int_nonneg(register_entries, "register-entries")
    if register_int is None:
        return _refuse(
            REFUSAL_MEASURABLE_INVALID,
            err,
            trail=trail,
            invocation=invocation,
        )

    create = not _trail_exists(trail)
    if not create:
        records, reason, detail = _load_trail(trail)
        if records is None:
            return _refuse(reason, detail, trail=trail, invocation=invocation)
        if invocation in _invocation_ids(records):
            return _refuse(
                REFUSAL_INVOCATION_DUPLICATE,
                "invocation %r already exists in the trail" % invocation,
                trail=trail,
                invocation=invocation,
            )
    else:
        records = []

    record = {
        "kind": RECORD_KIND_INVOCATION,
        "invocation": invocation,
        "cause": cause,
        "weight": weight,
        "measurables": {
            "children": children_int,
            "registerEntries": register_int,
        },
        "ceiling": ceiling_int,
        "override": override,
        "seats": list(seats),
    }
    _append_record(trail, record, create=create)
    return _make_write_result(
        RESULT_RECORDED,
        True,
        None,
        None,
        trail,
        invocation,
        record,
    )


def verb_record_round(
    trail,
    invocation,
    round_no,
    lenses,
    parts,
    control_probe,
    findings,
    declined_extension,
    mechanical_only,
):
    records, reason, detail = _load_trail(trail)
    if records is None:
        if reason == REFUSAL_TRAIL_MISSING:
            return _refuse(reason, detail, trail=trail, invocation=invocation)
        return _refuse(reason, detail, trail=trail, invocation=invocation)

    if invocation not in _invocation_ids(records):
        return _refuse(
            REFUSAL_INVOCATION_UNKNOWN,
            "invocation %r is not recorded in the trail" % invocation,
            trail=trail,
            invocation=invocation,
        )

    try:
        round_int = int(round_no)
    except (TypeError, ValueError):
        return _refuse(
            REFUSAL_ROUND_INVALID,
            "round must be a positive integer",
            trail=trail,
            invocation=invocation,
        )
    if round_int < 1:
        return _refuse(
            REFUSAL_ROUND_INVALID,
            "round must be a positive integer",
            trail=trail,
            invocation=invocation,
        )

    ceiling = _invocation_ceiling(records, invocation)
    if round_int > ceiling:
        return _refuse(
            REFUSAL_ROUND_EXCEEDS_CEILING,
            "round %d exceeds invocation ceiling %d" % (round_int, ceiling),
            trail=trail,
            invocation=invocation,
        )

    if round_int in _round_numbers(records, invocation):
        return _refuse(
            REFUSAL_ROUND_DUPLICATE,
            "round %d is already recorded for invocation %r" % (round_int, invocation),
            trail=trail,
            invocation=invocation,
        )

    for lens in lenses:
        if lens not in LENSES:
            return _refuse(
                REFUSAL_LENS_UNRECOGNIZED,
                "unrecognized lens %r" % lens,
                trail=trail,
                invocation=invocation,
            )

    part_objs = []
    for part in parts:
        name, status, err = _parse_colon_pair(part, "part")
        if err is not None:
            return _refuse(
                REFUSAL_PART_MALFORMED,
                err,
                trail=trail,
                invocation=invocation,
            )
        if status not in PART_STATUSES:
            return _refuse(
                REFUSAL_PART_STATUS_UNRECOGNIZED,
                "unrecognized part status %r" % status,
                trail=trail,
                invocation=invocation,
            )
        part_objs.append({"part": name, "status": status})

    if control_probe not in CONTROL_PROBE_READS:
        return _refuse(
            REFUSAL_CONTROL_PROBE_UNRECOGNIZED,
            "unrecognized control-probe read %r" % control_probe,
            trail=trail,
            invocation=invocation,
        )

    finding_objs = []
    known = _recorded_finding_ids(records, invocation)
    for finding in findings:
        fid, lens, err = _parse_colon_pair(finding, "finding")
        if err is not None:
            return _refuse(
                REFUSAL_FINDING_MALFORMED,
                err,
                trail=trail,
                invocation=invocation,
            )
        if lens not in LENSES:
            return _refuse(
                REFUSAL_LENS_UNRECOGNIZED,
                "unrecognized lens %r" % lens,
                trail=trail,
                invocation=invocation,
            )
        if fid in known:
            return _refuse(
                REFUSAL_FINDING_DUPLICATE,
                "finding %r is already recorded for invocation %r" % (fid, invocation),
                trail=trail,
                invocation=invocation,
            )
        known.add(fid)
        finding_objs.append({"finding": fid, "lens": lens})

    for fid in declined_extension:
        if fid not in known:
            return _refuse(
                REFUSAL_FINDING_UNKNOWN,
                "declined-extension finding %r was not recorded in a round" % fid,
                trail=trail,
                invocation=invocation,
            )

    record = {
        "kind": RECORD_KIND_ROUND,
        "invocation": invocation,
        "round": round_int,
        "lenses": list(lenses),
        "parts": part_objs,
        "controlProbe": control_probe,
        "findings": finding_objs,
        "declinedExtension": list(declined_extension),
        "mechanicalOnly": bool(mechanical_only),
    }
    _append_record(trail, record)
    return _make_write_result(
        RESULT_RECORDED,
        True,
        None,
        None,
        trail,
        invocation,
        record,
    )


def verb_record_verification(trail, invocation, findings, sync_checks, evidence_items):
    records, reason, detail = _load_trail(trail)
    if records is None:
        return _refuse(reason, detail, trail=trail, invocation=invocation)

    if not findings and not sync_checks:
        return _refuse(
            REFUSAL_USAGE,
            "at least one --finding or --sync-check is required",
            trail=trail,
            invocation=invocation,
        )

    if invocation not in _invocation_ids(records):
        return _refuse(
            REFUSAL_INVOCATION_UNKNOWN,
            "invocation %r is not recorded in the trail" % invocation,
            trail=trail,
            invocation=invocation,
        )

    known_round = _known_findings_for_invocation(records, invocation)
    already_verified = _latest_verified_finding_ids(records, invocation)
    evidence_by_finding = {}
    for evidence in evidence_items:
        fid, text, err = _parse_colon_pair(evidence, "evidence")
        if err is not None:
            return _refuse(
                REFUSAL_FINDING_MALFORMED,
                err,
                trail=trail,
                invocation=invocation,
            )
        if fid not in known_round:
            return _refuse(
                REFUSAL_FINDING_UNKNOWN,
                "evidence finding %r was not recorded in a round" % fid,
                trail=trail,
                invocation=invocation,
            )
        if not text.strip():
            return _refuse(
                REFUSAL_EVIDENCE_EMPTY,
                "evidence for finding %r is empty" % fid,
                trail=trail,
                invocation=invocation,
            )
        evidence_by_finding[fid] = text

    finding_objs = []
    for finding in findings:
        fid, disposition, outcome, err = _parse_colon_triple(finding, "finding")
        if err is not None:
            return _refuse(
                REFUSAL_FINDING_MALFORMED,
                err,
                trail=trail,
                invocation=invocation,
            )
        if disposition not in DISPOSITIONS:
            return _refuse(
                REFUSAL_DISPOSITION_UNRECOGNIZED,
                "unrecognized disposition %r" % disposition,
                trail=trail,
                invocation=invocation,
            )
        if outcome not in OUTCOMES:
            return _refuse(
                REFUSAL_OUTCOME_UNRECOGNIZED,
                "unrecognized outcome %r" % outcome,
                trail=trail,
                invocation=invocation,
            )
        if fid not in known_round:
            return _refuse(
                REFUSAL_FINDING_UNKNOWN,
                "finding %r was not recorded in a round" % fid,
                trail=trail,
                invocation=invocation,
            )
        lens = known_round[fid]
        if not _disposition_allowed_for_lens(lens, disposition):
            return _refuse(
                REFUSAL_DISPOSITION_NOT_ALLOWED_FOR_LENS,
                (
                    "disposition %r is not allowed for finding %r with lens %r"
                    % (disposition, fid, lens)
                ),
                trail=trail,
                invocation=invocation,
            )
        if disposition == DISPOSITION_REFUTATION and fid not in evidence_by_finding:
            return _refuse(
                REFUSAL_EVIDENCE_EMPTY,
                "refutation for finding %r requires --evidence" % fid,
                trail=trail,
                invocation=invocation,
            )
        if fid in already_verified:
            return _refuse(
                REFUSAL_VERIFICATION_DUPLICATE,
                "finding %r already has a verification record" % fid,
                trail=trail,
                invocation=invocation,
            )
        already_verified.add(fid)
        item = {
            "finding": fid,
            "disposition": disposition,
            "outcome": outcome,
        }
        if fid in evidence_by_finding:
            item["evidence"] = evidence_by_finding[fid]
        finding_objs.append(item)

    sync_objs = []
    seen_children = set()
    for sync_check in sync_checks:
        child, result, err = _parse_colon_pair(sync_check, "sync-check")
        if err is not None:
            return _refuse(
                REFUSAL_SYNC_CHECK_MALFORMED,
                err,
                trail=trail,
                invocation=invocation,
            )
        if result not in SYNC_RESULTS:
            return _refuse(
                REFUSAL_SYNC_RESULT_UNRECOGNIZED,
                "unrecognized sync-check result %r" % result,
                trail=trail,
                invocation=invocation,
            )
        if child in seen_children:
            return _refuse(
                REFUSAL_SYNC_CHECK_DUPLICATE,
                "sync-check child %r is named more than once" % child,
                trail=trail,
                invocation=invocation,
            )
        seen_children.add(child)
        sync_objs.append({"child": child, "result": result})

    record = {
        "kind": RECORD_KIND_VERIFICATION,
        "invocation": invocation,
        "findings": finding_objs,
        "syncChecks": sync_objs,
    }
    _append_record(trail, record)
    return _make_write_result(
        RESULT_RECORDED,
        True,
        None,
        None,
        trail,
        invocation,
        record,
    )


def verb_check(trail, invocation_filter=None):
    if not _trail_exists(trail):
        return _make_check_result(
            RESULT_UNDECIDED,
            False,
            UNDECIDED_TRAIL_MISSING,
            "trail file does not exist",
            trail,
            [],
            [],
        )

    lines = _read_lines(trail)
    if lines is None:
        return _make_check_result(
            RESULT_UNDECIDED,
            False,
            UNDECIDED_TRAIL_UNREADABLE,
            "trail file is missing or not valid UTF-8",
            trail,
            [],
            [],
        )

    records, reason, detail = _parse_records(lines)
    if records is None:
        return _make_check_result(
            RESULT_UNDECIDED,
            False,
            UNDECIDED_TRAIL_MALFORMED,
            detail,
            trail,
            [],
            [],
        )

    if not records:
        return _make_check_result(
            RESULT_UNDECIDED,
            False,
            UNDECIDED_TRAIL_EMPTY,
            "trail contains no audit records",
            trail,
            [],
            [],
        )

    invocations, rounds_by_inv, verifications_by_inv = _group_records(records)

    if invocation_filter is not None:
        if invocation_filter not in invocations:
            return _make_check_result(
                RESULT_UNDECIDED,
                False,
                UNDECIDED_INVOCATION_UNKNOWN,
                "invocation %r is not recorded in the trail" % invocation_filter,
                trail,
                [],
                [],
            )
        inv_ids = [invocation_filter]
    else:
        inv_ids = sorted(invocations.keys())

    summaries = []
    findings = []
    for inv_id in inv_ids:
        invocation = invocations[inv_id]
        trail_records = _invocation_trail_records(records, inv_id)
        projection = _project_invocation(trail_records)
        summaries.append(_summarize_invocation(inv_id, invocation, projection))
        findings.extend(_nonconformities_for_invocation(
            inv_id, invocation, projection,
        ))

    if invocation_filter is None and records and not invocations:
        pass

    if findings:
        return _make_check_result(
            RESULT_NONCONFORMING,
            False,
            None,
            None,
            trail,
            summaries,
            findings,
        )

    if not summaries:
        return _make_check_result(
            RESULT_NONCONFORMING,
            False,
            None,
            "trail has records but no invocation records",
            trail,
            [],
            [],
        )

    return _make_check_result(
        RESULT_CONFORMING,
        True,
        None,
        None,
        trail,
        summaries,
        [],
    )


def _emit(obj):
    sys.stdout.write(json.dumps(obj, separators=(",", ": ")) + "\n")


class _WriteArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._usage_paths = {"trail": None, "invocation": None}

    def error(self, message):
        result = _refuse(
            REFUSAL_USAGE,
            message,
            trail=self._usage_paths["trail"],
            invocation=self._usage_paths["invocation"],
        )
        _emit(result)
        raise SystemExit(EXIT_REFUSED)

    def exit(self, status=0, message=None):
        if status != 0:
            detail = message or "invalid command-line arguments"
            result = _refuse(
                REFUSAL_USAGE,
                detail,
                trail=self._usage_paths["trail"],
                invocation=self._usage_paths["invocation"],
            )
            _emit(result)
            raise SystemExit(EXIT_REFUSED)
        raise SystemExit(status)


class _CheckArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._usage_paths = {"trail": None}

    def error(self, message):
        result = _make_check_result(
            RESULT_UNDECIDED,
            False,
            UNDECIDED_USAGE,
            message,
            self._usage_paths["trail"],
            [],
            [],
        )
        _emit(result)
        raise SystemExit(EXIT_UNDECIDED)

    def exit(self, status=0, message=None):
        if status != 0:
            detail = message or "invalid command-line arguments"
            result = _make_check_result(
                RESULT_UNDECIDED,
                False,
                UNDECIDED_USAGE,
                detail,
                self._usage_paths["trail"],
                [],
                [],
            )
            _emit(result)
            raise SystemExit(EXIT_UNDECIDED)
        raise SystemExit(status)


def _peek_argv_value(argv, flag):
    if argv is None:
        return None
    for i, arg in enumerate(argv):
        if arg == flag and i + 1 < len(argv):
            return argv[i + 1]
        prefix = flag + "="
        if arg.startswith(prefix):
            return arg[len(prefix):]
    return None


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    if not argv or argv[0] in ("-h", "--help"):
        parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
        sub = parser.add_subparsers(dest="cmd")
        sub.add_parser("open", help="open a new invocation in the audit trail")
        sub.add_parser("record-round", help="record a review round")
        sub.add_parser("record-verification", help="record verification outcomes")
        sub.add_parser("check", help="check trail conformance")
        parser.print_help()
        return EXIT_RECORDED

    cmd = argv[0]
    rest = argv[1:]

    if cmd == "open":
        return _main_open(rest)
    if cmd == "record-round":
        return _main_record_round(rest)
    if cmd == "record-verification":
        return _main_record_verification(rest)
    if cmd == "check":
        return _main_check(rest)

    if cmd in ("-h", "--help"):
        return EXIT_RECORDED

    parser = _WriteArgumentParser(description=__doc__.splitlines()[0])
    parser._usage_paths["trail"] = _peek_argv_value(argv, "--trail")
    parser._usage_paths["invocation"] = _peek_argv_value(argv, "--invocation")
    parser.error("unknown subcommand %r" % cmd)


def _main_open(argv):
    parser = _WriteArgumentParser(description="open a package-read invocation")
    parser._usage_paths["trail"] = _peek_argv_value(argv, "--trail")
    parser._usage_paths["invocation"] = _peek_argv_value(argv, "--invocation")
    parser.add_argument("--trail", required=True)
    parser.add_argument("--invocation", required=True)
    parser.add_argument("--cause", required=True)
    parser.add_argument("--weight", required=True)
    parser.add_argument("--children", required=True)
    parser.add_argument("--register-entries", required=True)
    parser.add_argument("--ceiling", required=True)
    parser.add_argument("--override", default=None)
    parser.add_argument("--seat", action="append", default=[])
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        if exc.code in (0, None):
            return EXIT_RECORDED
        return EXIT_REFUSED

    if argv and argv[0] in ("-h", "--help"):
        return EXIT_RECORDED

    parser._usage_paths["trail"] = args.trail
    parser._usage_paths["invocation"] = args.invocation

    try:
        result = verb_open(
            args.trail,
            args.invocation,
            args.cause,
            args.weight,
            args.children,
            args.register_entries,
            args.ceiling,
            args.override,
            args.seat,
        )
    except Exception as exc:
        result = _refuse(
            REFUSAL_INTERNAL_ERROR,
            "%s: %s" % (type(exc).__name__, exc),
            trail=args.trail,
            invocation=args.invocation,
        )
        _emit(result)
        return EXIT_REFUSED

    _emit(result)
    return EXIT_RECORDED if result["ok"] else EXIT_REFUSED


def _main_record_round(argv):
    parser = _WriteArgumentParser(description="record a package-read round")
    parser._usage_paths["trail"] = _peek_argv_value(argv, "--trail")
    parser._usage_paths["invocation"] = _peek_argv_value(argv, "--invocation")
    parser.add_argument("--trail", required=True)
    parser.add_argument("--invocation", required=True)
    parser.add_argument("--round", required=True)
    parser.add_argument("--lens", action="append", default=[])
    parser.add_argument("--part", action="append", default=[])
    parser.add_argument("--control-probe", required=True)
    parser.add_argument("--finding", action="append", default=[])
    parser.add_argument("--declined-extension", action="append", default=[])
    parser.add_argument("--mechanical-only", action="store_true")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        if exc.code in (0, None):
            return EXIT_RECORDED
        return EXIT_REFUSED

    parser._usage_paths["trail"] = args.trail
    parser._usage_paths["invocation"] = args.invocation

    try:
        result = verb_record_round(
            args.trail,
            args.invocation,
            args.round,
            args.lens,
            args.part,
            args.control_probe,
            args.finding,
            args.declined_extension,
            args.mechanical_only,
        )
    except Exception as exc:
        result = _refuse(
            REFUSAL_INTERNAL_ERROR,
            "%s: %s" % (type(exc).__name__, exc),
            trail=args.trail,
            invocation=args.invocation,
        )
        _emit(result)
        return EXIT_REFUSED

    _emit(result)
    return EXIT_RECORDED if result["ok"] else EXIT_REFUSED


def _main_record_verification(argv):
    parser = _WriteArgumentParser(description="record package-read verification")
    parser._usage_paths["trail"] = _peek_argv_value(argv, "--trail")
    parser._usage_paths["invocation"] = _peek_argv_value(argv, "--invocation")
    parser.add_argument("--trail", required=True)
    parser.add_argument("--invocation", required=True)
    parser.add_argument("--finding", action="append", default=[])
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--sync-check", action="append", default=[])
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        if exc.code in (0, None):
            return EXIT_RECORDED
        return EXIT_REFUSED

    parser._usage_paths["trail"] = args.trail
    parser._usage_paths["invocation"] = args.invocation

    try:
        result = verb_record_verification(
            args.trail,
            args.invocation,
            args.finding,
            args.sync_check,
            args.evidence,
        )
    except Exception as exc:
        result = _refuse(
            REFUSAL_INTERNAL_ERROR,
            "%s: %s" % (type(exc).__name__, exc),
            trail=args.trail,
            invocation=args.invocation,
        )
        _emit(result)
        return EXIT_REFUSED

    _emit(result)
    return EXIT_RECORDED if result["ok"] else EXIT_REFUSED


def _main_check(argv):
    parser = _CheckArgumentParser(description="check package-read audit trail conformance")
    parser._usage_paths["trail"] = _peek_argv_value(argv, "--trail")
    parser.add_argument("--trail", required=True)
    parser.add_argument("--invocation", default=None)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        if exc.code in (0, None):
            return EXIT_CONFORMING
        return EXIT_UNDECIDED

    parser._usage_paths["trail"] = args.trail

    try:
        result = verb_check(args.trail, args.invocation)
    except Exception as exc:
        result = _make_check_result(
            RESULT_UNDECIDED,
            False,
            UNDECIDED_INTERNAL_ERROR,
            "%s: %s" % (type(exc).__name__, exc),
            args.trail,
            [],
            [],
        )
        _emit(result)
        return EXIT_UNDECIDED

    _emit(result)
    if result["result"] == RESULT_CONFORMING:
        return EXIT_CONFORMING
    if result["result"] == RESULT_NONCONFORMING:
        return EXIT_NONCONFORMING
    return EXIT_UNDECIDED


if __name__ == "__main__":
    sys.exit(main())
