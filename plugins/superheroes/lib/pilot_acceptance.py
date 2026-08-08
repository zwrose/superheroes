"""Acceptance matrix contract — capability evidence vs declared limits (C10).

Owns the pinned-reference record, row vocabulary, resolution against conformance
report and declaration receipts, framework-authored rows, matrix aggregation, and CLI.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone

SCHEMA = 1

STATUS_EXERCISED = "exercised"
STATUS_ATTESTED = "attested"
STATUS_UNEXERCISED = "unexercised"
STATUS_DECLARED_LIMIT = "declared-limit"
STATUS_PROSE_RESIDUE = "prose-residue"
STATUS_NOT_APPLICABLE = "not-applicable"
ACCEPTANCE_STATUSES = frozenset({
    STATUS_EXERCISED,
    STATUS_ATTESTED,
    STATUS_UNEXERCISED,
    STATUS_DECLARED_LIMIT,
    STATUS_PROSE_RESIDUE,
    STATUS_NOT_APPLICABLE,
})

RULING_OWNER_RULED = "owner-ruled"
RULING_PENDING_OWNER_RULING = "pending-owner-ruling"
RULINGS = frozenset({RULING_OWNER_RULED, RULING_PENDING_OWNER_RULING})

REASON_REFERENCE_PROJECT_INVALID = "acceptance-reference-project-invalid"
REASON_REFERENCE_COMMIT_INVALID = "acceptance-reference-commit-invalid"
REASON_REFERENCE_DIRTY_INVALID = "acceptance-reference-dirty-invalid"
REASON_ROW_AREA_INVALID = "acceptance-row-area-invalid"
REASON_ROW_CLAIM_INVALID = "acceptance-row-claim-invalid"
REASON_ROW_STATUS_INVALID = "acceptance-row-status-invalid"
REASON_ROW_EVIDENCE_REQUIRED = "acceptance-row-evidence-required"
REASON_ROW_EVIDENCE_FORBIDDEN = "acceptance-row-evidence-forbidden"
REASON_ROW_EVIDENCE_SHAPE_INVALID = "acceptance-row-evidence-shape-invalid"
REASON_ROW_LIMIT_ID_REQUIRED = "acceptance-row-limit-id-required"
REASON_ROW_LIMIT_ID_FORBIDDEN = "acceptance-row-limit-id-forbidden"
REASON_ROW_CLOSURE_PATH_REQUIRED = "acceptance-row-closure-path-required"
REASON_ROW_CLOSURE_PATH_FORBIDDEN = "acceptance-row-closure-path-forbidden"
REASON_ROW_RULING_REQUIRED = "acceptance-row-ruling-required"
REASON_ROW_RULING_INVALID = "acceptance-row-ruling-invalid"
REASON_ROW_RULING_FORBIDDEN = "acceptance-row-ruling-forbidden"

REASON_RESOLUTION_EXERCISE_MISSING = "acceptance-resolution-exercise-missing"
REASON_RESOLUTION_EXERCISE_FAILED = "acceptance-resolution-exercise-failed"
REASON_RESOLUTION_SURFACE_MISSING = "acceptance-resolution-surface-missing"
REASON_RESOLUTION_DECLARATION_MISSING = "acceptance-resolution-declaration-missing"
REASON_RESOLUTION_DECLARATION_NOT_ATTESTED = "acceptance-resolution-declaration-not-attested"

REASON_EVIDENCE_EXERCISE_ABSENT = "acceptance-evidence-exercise-absent"
REASON_EVIDENCE_EXERCISE_FAILED = "acceptance-evidence-exercise-failed"
REASON_EVIDENCE_SURFACE_UNBOUND = "acceptance-evidence-surface-unbound"
REASON_EVIDENCE_DECLARATION_ABSENT = "acceptance-evidence-declaration-absent"
REASON_EVIDENCE_DECLARATION_NOT_ATTESTED = "acceptance-evidence-declaration-not-attested"

REASON_CLI_REPORT_PATH_INVALID = "acceptance-cli-report-path-invalid"
REASON_CLI_REPORT_INVALID = "acceptance-cli-report-invalid"
REASON_CLI_DECLARATIONS_MISSING = "acceptance-cli-declarations-missing"
REASON_CLI_GENERATED_AT_INVALID = "acceptance-cli-generated-at-invalid"
REASON_CLI_FORMAT_INVALID = "acceptance-cli-format-invalid"

_COMMIT_OID_RE = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")
_EXERCISE_EVIDENCE_KEYS = frozenset({"exercise", "surface"})
_DECLARATION_EVIDENCE_KEYS = frozenset({"kind", "slotRef", "digest"})
_UNEXERCISED_EVIDENCE_KEYS = frozenset({"reason"})
_ROW_KEYS = frozenset({
    "area",
    "claim",
    "status",
    "evidence",
    "limit_id",
    "closure_path",
    "ruling",
})


class PilotAcceptanceError(Exception):
    """Acceptance-matrix contract refusal."""

    def __init__(self, reason, detail=None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _has_control_char(value):
    return any(ord(ch) < 32 for ch in value)


def _validate_label(value, reason):
    if not isinstance(value, str) or not value or _has_control_char(value):
        raise PilotAcceptanceError(reason)


def _is_exercise_evidence(evidence):
    return (
        isinstance(evidence, dict)
        and set(evidence.keys()) == _EXERCISE_EVIDENCE_KEYS
        and isinstance(evidence["exercise"], str)
        and evidence["exercise"]
        and not _has_control_char(evidence["exercise"])
        and isinstance(evidence["surface"], str)
        and evidence["surface"]
        and not _has_control_char(evidence["surface"])
    )


def _is_declaration_evidence(evidence):
    return (
        isinstance(evidence, dict)
        and set(evidence.keys()) == _DECLARATION_EVIDENCE_KEYS
        and isinstance(evidence["kind"], str)
        and evidence["kind"]
        and not _has_control_char(evidence["kind"])
        and isinstance(evidence["slotRef"], str)
        and evidence["slotRef"]
        and not _has_control_char(evidence["slotRef"])
        and isinstance(evidence["digest"], str)
        and evidence["digest"]
        and not _has_control_char(evidence["digest"])
    )


def _is_unexercised_evidence(evidence):
    return (
        isinstance(evidence, dict)
        and set(evidence.keys()) == _UNEXERCISED_EVIDENCE_KEYS
        and isinstance(evidence["reason"], str)
        and evidence["reason"]
        and not _has_control_char(evidence["reason"])
        and not any(ch.isspace() for ch in evidence["reason"])
    )


def reference(project, commit, *, dirty):
    """Return a pinned reference record for the acceptance matrix."""
    _validate_label(project, REASON_REFERENCE_PROJECT_INVALID)
    if not isinstance(commit, str) or not _COMMIT_OID_RE.match(commit):
        # bite-axis: commit oid — only full lowercase hex object ids; short shas and refs refuse.
        raise PilotAcceptanceError(REASON_REFERENCE_COMMIT_INVALID)
    if dirty is not True and dirty is not False:
        raise PilotAcceptanceError(REASON_REFERENCE_DIRTY_INVALID)
    return {
        "project": project,
        "commit": commit,
        "dirty": dirty,
    }


def row(*, area, claim, status, evidence=None, limit_id=None, closure_path=None, ruling=None):
    """Validate and return one acceptance-matrix row dict."""
    _validate_label(area, REASON_ROW_AREA_INVALID)
    _validate_label(claim, REASON_ROW_CLAIM_INVALID)
    if status not in ACCEPTANCE_STATUSES:
        raise PilotAcceptanceError(REASON_ROW_STATUS_INVALID)

    if status in (STATUS_EXERCISED, STATUS_ATTESTED):
        if evidence is None:
            raise PilotAcceptanceError(REASON_ROW_EVIDENCE_REQUIRED)
        if status == STATUS_EXERCISED and not _is_exercise_evidence(evidence):
            raise PilotAcceptanceError(REASON_ROW_EVIDENCE_SHAPE_INVALID)
        if status == STATUS_ATTESTED and not _is_declaration_evidence(evidence):
            raise PilotAcceptanceError(REASON_ROW_EVIDENCE_SHAPE_INVALID)
        if limit_id is not None:
            raise PilotAcceptanceError(REASON_ROW_LIMIT_ID_FORBIDDEN)
        if closure_path is not None:
            raise PilotAcceptanceError(REASON_ROW_CLOSURE_PATH_FORBIDDEN)
        if ruling is not None:
            raise PilotAcceptanceError(REASON_ROW_RULING_FORBIDDEN)
    elif status == STATUS_DECLARED_LIMIT:
        if evidence is not None:
            raise PilotAcceptanceError(REASON_ROW_EVIDENCE_FORBIDDEN)
        if not isinstance(limit_id, str) or not limit_id or _has_control_char(limit_id):
            raise PilotAcceptanceError(REASON_ROW_LIMIT_ID_REQUIRED)
        if not isinstance(closure_path, str) or not closure_path or _has_control_char(closure_path):
            raise PilotAcceptanceError(REASON_ROW_CLOSURE_PATH_REQUIRED)
        if ruling is None:
            raise PilotAcceptanceError(REASON_ROW_RULING_REQUIRED)
        if ruling not in RULINGS:
            raise PilotAcceptanceError(REASON_ROW_RULING_INVALID)
    elif status == STATUS_UNEXERCISED:
        if evidence is None or not _is_unexercised_evidence(evidence):
            raise PilotAcceptanceError(REASON_ROW_EVIDENCE_REQUIRED)
        if limit_id is not None:
            raise PilotAcceptanceError(REASON_ROW_LIMIT_ID_FORBIDDEN)
        if closure_path is not None:
            raise PilotAcceptanceError(REASON_ROW_CLOSURE_PATH_FORBIDDEN)
        if ruling is not None:
            raise PilotAcceptanceError(REASON_ROW_RULING_FORBIDDEN)
    elif status in (STATUS_PROSE_RESIDUE, STATUS_NOT_APPLICABLE):
        if evidence is not None:
            raise PilotAcceptanceError(REASON_ROW_EVIDENCE_FORBIDDEN)
        if limit_id is not None:
            raise PilotAcceptanceError(REASON_ROW_LIMIT_ID_FORBIDDEN)
        if closure_path is not None:
            raise PilotAcceptanceError(REASON_ROW_CLOSURE_PATH_FORBIDDEN)
        if ruling is not None:
            raise PilotAcceptanceError(REASON_ROW_RULING_FORBIDDEN)

    return {
        "area": area,
        "claim": claim,
        "status": status,
        "evidence": evidence,
        "limit_id": limit_id,
        "closure_path": closure_path,
        "ruling": ruling,
    }


def _rewrite_unexercised(row_data, reason):
    return {
        "area": row_data["area"],
        "claim": row_data["claim"],
        "status": STATUS_UNEXERCISED,
        "evidence": {"reason": reason},
        "limit_id": None,
        "closure_path": None,
        "ruling": None,
    }


def _framework_unexercised_row(*, area, claim, reason):
    return _rewrite_unexercised(
        {"area": area, "claim": claim},
        reason,
    )


def _find_exercise_record(report_data, exercise_name):
    exercises = report_data.get("exercises")
    if not isinstance(exercises, list):
        return None
    for record in exercises:
        if isinstance(record, dict) and record.get("exercise") == exercise_name:
            return record
    return None


def _find_declaration_row(declarations_block, kind, slot_ref, digest):
    rows = declarations_block.get("rows")
    if not isinstance(rows, list):
        return None
    for decl_row in rows:
        if not isinstance(decl_row, dict):
            continue
        if (
            decl_row.get("kind") == kind
            and decl_row.get("slotRef") == slot_ref
            and decl_row.get("declarationDigest") == digest
        ):
            return decl_row
    return None


def _resolve_exercised(row_data, report_data):
    evidence = row_data["evidence"]
    record = _find_exercise_record(report_data, evidence["exercise"])
    if record is None:
        return _rewrite_unexercised(row_data, REASON_EVIDENCE_EXERCISE_ABSENT)
    if record.get("result") != "pass":
        return _rewrite_unexercised(row_data, REASON_EVIDENCE_EXERCISE_FAILED)
    surfaces = record.get("surfaces")
    if not isinstance(surfaces, list):
        return _rewrite_unexercised(row_data, REASON_EVIDENCE_SURFACE_UNBOUND)
    # bite-axis: surface binding — cited surface must appear on the passing exercise record.
    if evidence["surface"] not in surfaces:
        return _rewrite_unexercised(row_data, REASON_EVIDENCE_SURFACE_UNBOUND)
    return dict(row_data)


def _resolve_attested(row_data, declarations_block):
    evidence = row_data["evidence"]
    decl_row = _find_declaration_row(
        declarations_block,
        evidence["kind"],
        evidence["slotRef"],
        evidence["digest"],
    )
    if decl_row is None:
        return _rewrite_unexercised(row_data, REASON_EVIDENCE_DECLARATION_ABSENT)
    if decl_row.get("status") != "attested":
        return _rewrite_unexercised(row_data, REASON_EVIDENCE_DECLARATION_NOT_ATTESTED)
    return dict(row_data)


def resolve(rows, report_data, declarations_block):
    """Resolve exercised and attested rows against run evidence; downgrade failures."""
    if not isinstance(rows, list):
        raise PilotAcceptanceError(REASON_ROW_STATUS_INVALID)
    if not isinstance(report_data, dict):
        raise PilotAcceptanceError(REASON_CLI_REPORT_INVALID)
    if not isinstance(declarations_block, dict):
        raise PilotAcceptanceError(REASON_CLI_DECLARATIONS_MISSING)

    resolved = []
    for row_data in rows:
        if not isinstance(row_data, dict) or set(row_data.keys()) != _ROW_KEYS:
            raise PilotAcceptanceError(REASON_ROW_STATUS_INVALID)
        status = row_data.get("status")
        if status == STATUS_EXERCISED:
            resolved.append(_resolve_exercised(row_data, report_data))
        elif status == STATUS_ATTESTED:
            resolved.append(_resolve_attested(row_data, declarations_block))
        else:
            # bite-axis: not-applicable never produced — resolution never rewrites to it.
            resolved.append(dict(row_data))
    return resolved


def matrix(reference_record, rows, report_data, declarations_block, *, generated_at):
    """Aggregate resolved rows into a matrix dict with an ok verdict."""
    resolved_rows = resolve(rows, report_data, declarations_block)
    # bite-axis: non-empty rows — vacuous matrix is never ok.
    rows_ok = bool(resolved_rows)
    # bite-axis: no unexercised rows — every applicable claim must resolve or be declared.
    no_unexercised = all(
        row_data["status"] != STATUS_UNEXERCISED for row_data in resolved_rows
    )
    # bite-axis: dirty reference — pin mismatch forces ok false even when rows resolve.
    reference_clean = not reference_record.get("dirty")
    report_unexercised_empty = (
        isinstance(report_data.get("unexercised"), list)
        and not report_data["unexercised"]
    )
    report_ok = report_data.get("ok") is True
    declarations_ok = declarations_block.get("ok") is True
    ok = (
        rows_ok
        and no_unexercised
        and reference_clean
        and report_unexercised_empty
        and report_ok
        and declarations_ok
    )
    return {
        "schemaVersion": SCHEMA,
        "reference": dict(reference_record),
        "generatedAt": generated_at,
        "rows": resolved_rows,
        "ok": ok,
    }


FRAMEWORK_DECLARED_LIMITS = (
    {
        "limit_id": "results-only-key-position",
        "ruling": RULING_OWNER_RULED,
        "claim": (
            "An account name shaped like a field name is not matched in dict-key position, "
            "so a producer keying a result dict by account name leaks that name past the guard. "
            "Value-position detection and all non-account material are unchanged."
        ),
        "closure_path": (
            "The schema-key-position exemption design (fourteen call sites), funded only if a "
            "project's threat model names key-position account-name leakage."
        ),
    },
    {
        "limit_id": "sentinel-account-attestation",
        "ruling": RULING_OWNER_RULED,
        "claim": (
            "The framework verifies the sentinel account is absent from the mint allowlist but not "
            "that it names no real account; a real-but-not-mintable account satisfies every "
            "framework-side check."
        ),
        "closure_path": (
            "Project attestation; promote to an A1 schema field only if a project's threat model "
            "demands it."
        ),
    },
    {
        "limit_id": "appctl-stop-pgid-reuse",
        "ruling": RULING_OWNER_RULED,
        "claim": (
            "Reaping releases the child pid, so signals sent after a successful reap address the "
            "process group by number rather than pinned identity; a pid recycled into a group leader "
            "between two adjacent syscalls would be mis-signalled."
        ),
        "closure_path": (
            "Platform-specific group-membership enumeration, funded only if a project's threat model "
            "names pid-wraparound races."
        ),
    },
    {
        "limit_id": "bounded-run-clean-exit-containment",
        "ruling": RULING_OWNER_RULED,
        "claim": (
            "The shared runner signals the whole process group on every termination path, but a "
            "command that exits cleanly after detaching a helper never has its group signalled, so "
            "the helper survives."
        ),
        "closure_path": (
            "A containment-on-success semantics decision, funded only on field evidence: a real "
            "leaked helper observed reopens it."
        ),
    },
    {
        "limit_id": "residue-scan-encoded-material",
        "ruling": RULING_PENDING_OWNER_RULING,
        "claim": (
            "A substring scan cannot catch base64, UTF-16, or percent-encoded material, so "
            "redaction is established only against plain-text residue of declared material."
        ),
        "closure_path": "Awaiting owner ruling.",
    },
    {
        "limit_id": "screenshot-pixels-uninspectable",
        "ruling": RULING_PENDING_OWNER_RULING,
        "claim": (
            "The capture receipt binds bytes to a digest and checks format; nothing establishes "
            "that what was rendered carries no secret."
        ),
        "closure_path": "Awaiting owner ruling.",
    },
    {
        "limit_id": "trace-retention-usually-refuses",
        "ruling": RULING_PENDING_OWNER_RULING,
        "claim": (
            "Any binary archive member refuses retention fail-closed, and real browser traces carry "
            "binary screencast frames, so the opt-in trace path exists and is exercised but rarely "
            "retains."
        ),
        "closure_path": "Awaiting owner ruling.",
    },
)

EXTRAPOLATION_POINTS = (
    {
        "id": "sign-in-cardinality",
        "claim": (
            "Sign-in cardinality is derived from cookies being host-scoped and port-blind; a project "
            "holding its session in origin-scoped storage counts sign-ins per slot instead of per "
            "account."
        ),
        "status": STATUS_PROSE_RESIDUE,
        "evidence": None,
    },
    {
        "id": "declared-session-surface",
        "claim": (
            "Which browser surface holds the session, and the context options it requires, are "
            "generalized from one project's shape."
        ),
        "status": STATUS_ATTESTED,
        "declaration_kind": "session-surface",
    },
    {
        "id": "validity-provenance",
        "claim": "The default intuition for validity provenance comes from cookie expiry.",
        "status": STATUS_EXERCISED,
        "evidence": {
            "exercise": "horizon-validity",
            "surface": "pilot_horizon.account_margin",
        },
    },
    {
        "id": "one-app-instance-per-slot",
        "claim": (
            "One app instance per slot assumes a project can afford N instances, which is untrue for "
            "a heavy application or one backed by a shared remote service."
        ),
        "status": STATUS_EXERCISED,
        "evidence": {
            "exercise": "wave-headless",
            "surface": "pilot_appctl.assert_unique_endpoints",
        },
    },
    {
        "id": "filesystem-reclaim",
        "claim": "Filesystem reclaim assumes the slot is a renameable directory.",
        "status": STATUS_EXERCISED,
        "evidence": {
            "exercise": "reclaim-sweep",
            "surface": "pilot_reclaim.sweep",
        },
    },
)

TRIPWIRE_ROWS = (
    {
        "id": "multi-account-class",
        "claim": (
            "Credentials spanning more than one account class refuse at provisioning; enforcement is "
            "mechanical at the provisioning gate and is not exercised by this conformance run."
        ),
        "status": STATUS_PROSE_RESIDUE,
        "evidence": None,
    },
    {
        "id": "local-development-only",
        "claim": (
            "Any target that is not local development refuses before a credential exists."
        ),
        "status": STATUS_EXERCISED,
        "evidence": {
            "exercise": "boundary-refusals",
            "surface": "pilot_boundary.is_local_development_origin",
        },
    },
    {
        "id": "account-owns-nothing",
        "claim": (
            "The pilot account gaining real data, rights, or billing is not something the framework "
            "detects; an account quietly accumulating data over time relies on the owner noticing."
        ),
        "status": STATUS_PROSE_RESIDUE,
        "evidence": None,
    },
    {
        "id": "account-owns-nothing-probe",
        "claim": (
            "Where the project declares an ownership probe, each credential-set account answered "
            "that it owns nothing at the moment the probe ran."
        ),
        "status": STATUS_EXERCISED,
        "evidence": {
            "exercise": "ownership-probe",
            "surface": "pilot_policy.ownership_probe_request",
        },
    },
)


def _declaration_evidence_for_kind(declarations_block, kind):
    rows = declarations_block.get("rows")
    if not isinstance(rows, list):
        return None
    for decl_row in rows:
        if not isinstance(decl_row, dict):
            continue
        if decl_row.get("kind") != kind:
            continue
        digest = decl_row.get("declarationDigest")
        slot_ref = decl_row.get("slotRef")
        if not isinstance(digest, str) or not digest:
            continue
        if not isinstance(slot_ref, str) or not slot_ref:
            continue
        return {
            "kind": kind,
            "slotRef": slot_ref,
            "digest": digest,
        }
    return None


def _build_framework_row(spec, *, area, declarations_block):
    status = spec["status"]
    claim = spec["claim"]
    evidence = spec.get("evidence")
    if status in (STATUS_EXERCISED, STATUS_ATTESTED):
        if status == STATUS_ATTESTED and evidence is None:
            declaration_kind = spec.get("declaration_kind")
            if declaration_kind:
                evidence = _declaration_evidence_for_kind(declarations_block, declaration_kind)
            if evidence is None:
                return _framework_unexercised_row(
                    area=area,
                    claim=claim,
                    reason=REASON_EVIDENCE_DECLARATION_ABSENT,
                )
        if evidence is None:
            return _framework_unexercised_row(
                area=area,
                claim=claim,
                reason=REASON_EVIDENCE_EXERCISE_ABSENT,
            )
    kwargs = {
        "area": area,
        "claim": claim,
        "status": status,
        "evidence": evidence,
    }
    if status == STATUS_DECLARED_LIMIT:
        kwargs["limit_id"] = spec["limit_id"]
        kwargs["closure_path"] = spec["closure_path"]
        kwargs["ruling"] = spec["ruling"]
    return row(**kwargs)


def framework_rows(report_data, declarations_block):
    """Return the framework's own rows, resolved against this run's evidence."""
    candidates = []
    for spec in FRAMEWORK_DECLARED_LIMITS:
        candidates.append(
            row(
                area="declared-limit",
                claim=spec["claim"],
                status=STATUS_DECLARED_LIMIT,
                limit_id=spec["limit_id"],
                closure_path=spec["closure_path"],
                ruling=spec["ruling"],
            )
        )
    for spec in EXTRAPOLATION_POINTS:
        candidates.append(
            _build_framework_row(spec, area="generality", declarations_block=declarations_block)
        )
    for spec in TRIPWIRE_ROWS:
        candidates.append(
            _build_framework_row(
                spec,
                area="accepted-limit-tripwire",
                declarations_block=declarations_block,
            )
        )
    return resolve(candidates, report_data, declarations_block)


def _escape_markdown_cell(value):
    if value is None:
        return ""
    return str(value).replace("|", "\\|")


def render_markdown(matrix_data):
    """Render a matrix dict as an owner-readable markdown table."""
    lines = []
    ok = matrix_data.get("ok")
    lines.append("## Acceptance matrix")
    lines.append("")
    lines.append("**ok:** %s" % ok)
    reference = matrix_data.get("reference") or {}
    project = reference.get("project", "")
    commit = reference.get("commit", "")
    dirty = reference.get("dirty")
    lines.append("**reference:** %s @ %s" % (project, commit))
    if dirty:
        lines.append("")
        lines.append("> **Warning:** reference worktree was dirty at generation time.")
    lines.append("")
    generated_at = matrix_data.get("generatedAt")
    if generated_at:
        lines.append("**generatedAt:** %s" % generated_at)
        lines.append("")

    rows = matrix_data.get("rows") or []
    by_area = {}
    for row_data in rows:
        area = row_data.get("area", "")
        by_area.setdefault(area, []).append(row_data)

    for area in sorted(by_area):
        lines.append("### %s" % area)
        lines.append("")
        lines.append("| Status | Claim | Evidence / closure |")
        lines.append("| --- | --- | --- |")
        for row_data in by_area[area]:
            status = row_data.get("status", "")
            claim = _escape_markdown_cell(row_data.get("claim", ""))
            detail = ""
            if row_data.get("status") == STATUS_DECLARED_LIMIT:
                detail = _escape_markdown_cell(row_data.get("closure_path"))
            elif row_data.get("status") == STATUS_UNEXERCISED:
                reason = (row_data.get("evidence") or {}).get("reason")
                if reason:
                    detail = _escape_markdown_cell("reason: %s" % reason)
                else:
                    detail = _escape_markdown_cell(
                        json.dumps(row_data["evidence"], sort_keys=True)
                    )
            elif row_data.get("evidence") is not None:
                detail = _escape_markdown_cell(json.dumps(row_data["evidence"], sort_keys=True))
            lines.append("| %s | %s | %s |" % (status, claim, detail))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _validate_generated_at(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise PilotAcceptanceError(REASON_CLI_GENERATED_AT_INVALID)
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise PilotAcceptanceError(REASON_CLI_GENERATED_AT_INVALID)
    return value


def _load_report(path):
    if not isinstance(path, str) or not path:
        raise PilotAcceptanceError(REASON_CLI_REPORT_PATH_INVALID)
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        raise PilotAcceptanceError(REASON_CLI_REPORT_INVALID)
    if not isinstance(data, dict):
        raise PilotAcceptanceError(REASON_CLI_REPORT_INVALID)
    return data


def _matrix_from_report(report_data, *, project, commit, dirty, generated_at):
    declarations = report_data.get("declarations")
    if not isinstance(declarations, dict):
        raise PilotAcceptanceError(REASON_CLI_DECLARATIONS_MISSING)
    ref = reference(project, commit, dirty=dirty)
    rows = framework_rows(report_data, declarations)
    return matrix(ref, rows, report_data, declarations, generated_at=generated_at)


def main(argv):
    """CLI entry point for acceptance-matrix generation."""
    parser = argparse.ArgumentParser(prog="pilot_acceptance.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    matrix_parser = subparsers.add_parser("matrix")
    matrix_parser.add_argument("--report-path", required=True)
    matrix_parser.add_argument("--project", required=True)
    matrix_parser.add_argument("--commit", required=True)
    matrix_parser.add_argument("--dirty", action="store_true", default=False)
    matrix_parser.add_argument("--generated-at", default=None)
    matrix_parser.add_argument("--format", choices=("json", "markdown"), default="json")

    parsed = parser.parse_args(argv[1:])
    if parsed.command != "matrix":
        sys.stderr.write("%s\n" % REASON_CLI_FORMAT_INVALID)
        return 2

    try:
        if parsed.generated_at is None:
            generated_at_value = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            generated_at_value = _validate_generated_at(parsed.generated_at)
        ref = reference(parsed.project, parsed.commit, dirty=parsed.dirty)
        report_data = _load_report(parsed.report_path)
        declarations = report_data.get("declarations")
        if not isinstance(declarations, dict):
            raise PilotAcceptanceError(REASON_CLI_DECLARATIONS_MISSING)
        rows = framework_rows(report_data, declarations)
        matrix_data = matrix(
            ref,
            rows,
            report_data,
            declarations,
            generated_at=generated_at_value,
        )
    except PilotAcceptanceError as exc:
        sys.stderr.write("%s\n" % exc.reason)
        return 2

    if parsed.format == "markdown":
        output = render_markdown(matrix_data)
    else:
        output = json.dumps(matrix_data, indent=2) + "\n"
    # bite-axis: stdout/stderr split — matrix payload on stdout; diagnostics on stderr.
    sys.stdout.write(output)
    return 0 if matrix_data["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
