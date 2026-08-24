#!/usr/bin/env python3
"""Single home for declared per-seat payload contracts.

Sits below both the round-phase orchestration layer and the engine transport core so
both may depend on it without either reaching upward. Imports are stdlib plus
`round_phases`, `audits`, and `dispatch_outcome` only — that constraint is pinned by
the layering test in test_payload_contracts_layering.py.
"""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audits  # noqa: E402
import dispatch_outcome  # noqa: E402
import round_phases  # noqa: E402

P_PANEL = round_phases.P_PANEL
P_VERIFIERS = round_phases.P_VERIFIERS
P_SYNTHESIS = round_phases.P_SYNTHESIS
P_GAPSWEEP = round_phases.P_GAPSWEEP
P_AUDITS = round_phases.P_AUDITS
P_SCOPED = round_phases.P_SCOPED
P_VERIFY = round_phases.P_VERIFY
P_FIXER = round_phases.P_FIXER

ADAPTER_PHASES = (P_PANEL, P_VERIFIERS, P_SYNTHESIS, P_GAPSWEEP, P_AUDITS, P_SCOPED, P_VERIFY,
                  P_FIXER)

SEAT_SYNTHESIS = "synthesis"
SEAT_GAPSWEEP = "gap-sweep"
SEAT_SCOPED = "scoped-finder"
SEAT_VERIFY = "verify"
SEAT_FIXER = "fixer"

# The one ruling whose claim is unusable without a new-issue payload. `audits` exposes the ENUM
# (`AUDIT_RULINGS`, which this module validates against and never hand-copies) but no per-member
# constant, so the member is named here once and `test_new_issue_ruling_is_a_real_member` holds it
# equal to a real member of that enum.
RULING_NEW_ISSUE = "discharged-but-new-issue"

# The panel payload's never-ran FLAG (`_fold_panel` reads `seat.get(...) is True`). Bound from
# `dispatch_outcome` rather than spelled as a literal: the flag IS the boolean form of that outcome
# token, and #747's census keeps every outcome token in that one home.
# `test_panel_vacuous_flag_marks_a_seat_never_ran` drives the real fold through this exact key, so
# the binding is pinned by behaviour rather than by a string comparison.
VACUOUS_FIELD = dispatch_outcome.REASON_VACUOUS

def _label(value):
    """A message-safe rendering of an arbitrary value."""
    return value if isinstance(value, str) else repr(value)


def _type_name(value):
    return type(value).__name__


# =============================================================================================
# payload_fault — record-time per-field validation
# =============================================================================================

def _field_missing(field):
    return "`%s` is missing" % field


def _field_type(field, value, expected):
    return "`%s` is %s, not %s" % (field, _type_name(value), expected)


def _optional_str(payload, field):
    if field not in payload:
        return None
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        return _field_type(field, value, "a non-empty string")
    return None


def _optional_bool(payload, field):
    if field not in payload:
        return None
    value = payload.get(field)
    if not isinstance(value, bool):
        return _field_type(field, value, "a boolean")
    return None


def _list_of_objects(value, field):
    if not isinstance(value, list):
        return _field_type(field, value, "a list")
    for index, member in enumerate(value):
        if not isinstance(member, dict):
            return "`%s`[%d] is %s, not an object" % (field, index, _type_name(member))
    return None


def _abs_path(payload, field):
    if field not in payload:
        return None
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        return _field_type(field, value, "a non-empty string")
    if not os.path.isabs(value):
        return ("`%s` is not an absolute path (%r) — the driver reads it at FOLD time and treats a "
                "non-absolute path as an unknown surface" % (field, value))
    return None


# Closed vocabulary for `types` entries in `_PAYLOAD_CONTRACTS`. An unknown token is a declaration
# defect and must fail loudly — never silently pass.
TYPE_TOKENS = frozenset((
    "string",
    "non-empty-string",
    "boolean",
    "integer",
    "list",
    "list-of-objects",
    "nullable-list-of-objects",
    "absolute-path",
    "object",
    "any",
))


def _assert_type_token(token, where):
    if token not in TYPE_TOKENS:
        raise ValueError("unknown type token %r in %s" % (token, where))


def _check_scalar_type(field, value, type_token, expected_phrase):
    """Return a fault string or None. `expected_phrase` is the suffix after 'not '."""
    if type_token == "any":
        return None
    _assert_type_token(type_token, "declaration")
    if type_token == "string":
        if not isinstance(value, str):
            return _field_type(field, value, "a string")
    elif type_token == "non-empty-string":
        if not isinstance(value, str) or not value:
            return _field_type(field, value, "a non-empty string")
    elif type_token == "boolean":
        if not isinstance(value, bool):
            return _field_type(field, value, "a boolean")
    elif type_token == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            return _field_type(field, value, "an integer")
    elif type_token == "list":
        if not isinstance(value, list):
            return _field_type(field, value, "a list")
    elif type_token == "object":
        if not isinstance(value, dict):
            return _field_type(field, value, "an object")
    elif type_token == "absolute-path":
        if not isinstance(value, str) or not value:
            return _field_type(field, value, "a non-empty string")
        if not os.path.isabs(value):
            return ("`%s` is not an absolute path (%r) — the driver reads it at FOLD time and treats a "
                    "non-absolute path as an unknown surface" % (field, value))
    else:
        raise ValueError("scalar check called for non-scalar type token %r on %s" % (type_token, field))
    return None


def _check_list_of_objects(value, field):
    return _list_of_objects(value, field)


def _check_top_level_type(payload, field, type_token):
    if field not in payload:
        return None
    value = payload.get(field)
    if type_token == "list-of-objects":
        return _check_list_of_objects(value, field)
    if type_token == "nullable-list-of-objects":
        if value is None:
            return None
        return _check_list_of_objects(value, field)
    return _check_scalar_type(field, value, type_token,
                              None)  # expected_phrase unused — _check_scalar_type uses token


def _element_where(list_field, index):
    return "%s[%d]" % (list_field, index)


def _element_field_label(list_field, index, elem_field):
    return "`%s.%s`" % (_element_where(list_field, index), elem_field)


def _check_element_fields(list_field, index, element, elem_contract, extra_context=None):
    """Mechanical element validation. `extra_context` is an optional dict passed to special cases."""
    _ = extra_context
    where = _element_where(list_field, index)
    for req in elem_contract.get("required") or []:
        if req not in element:
            value = element.get(req)
            label = _element_field_label(list_field, index, req)
            types = elem_contract.get("types") or {}
            tok = types.get(req, "any")
            if tok == "non-empty-string":
                detail = "%s is %s, not a non-empty string" % (label, _type_name(value))
                if list_field == "verdicts" and req == "id" and "findingId" in element:
                    detail += ("; the payload carries `findingId` — apply_verdicts keys on `id`, and a "
                               "verdict it cannot key reaches no finding at all")
                return detail
            if tok == "list":
                return "`%s`[%d].%s is %s, not a non-empty list" % (
                    list_field, index, req, _type_name(value))
            return "%s is missing" % label
    field_order = list(elem_contract.get("required") or []) + list(elem_contract.get("optional") or [])
    seen = set()
    types = elem_contract.get("types") or {}
    enums = elem_contract.get("enums") or {}
    for elem_field in field_order:
        if elem_field in seen:
            continue
        seen.add(elem_field)
        if elem_field not in element:
            continue
        value = element.get(elem_field)
        tok = types.get(elem_field, "any")
        _assert_type_token(tok, "elements.%s.types" % list_field)
        label = _element_field_label(list_field, index, elem_field)
        if tok == "non-empty-string":
            if not isinstance(value, str) or not value:
                detail = "%s is %s, not a non-empty string" % (label, _type_name(value))
                if (list_field == "verdicts" and elem_field == "id"
                        and "findingId" in element):
                    detail += ("; the payload carries `findingId` — apply_verdicts keys on `id`, and a "
                               "verdict it cannot key reaches no finding at all")
                return detail
        elif tok == "string":
            if not isinstance(value, str):
                return "%s is %s, not a string" % (label, _type_name(value))
        elif tok == "list":
            pass
        elif tok != "any":
            fault = _check_scalar_type(label, value, tok, None)
            if fault:
                return fault
        if elem_field in enums:
            allowed = enums[elem_field]
            if not isinstance(value, str) or value not in allowed:
                return ("`%s.%s` is %r — expected one of: %s"
                        % (where, elem_field, value, ", ".join(allowed)))
    return None


def _check_declared(payload, contract, *, record_boundary=False):
    """Enforce the mechanical half of a declared contract. Predicates run separately."""
    _ = record_boundary
    types = contract.get("types") or {}
    enums = contract.get("enums") or {}
    elements = contract.get("elements") or {}
    for field in contract.get("required") or []:
        if field in ("reason", "result") and field not in payload:
            continue
        tok = types.get(field)
        if tok == "non-empty-string" and field not in payload:
            value = payload.get(field)
            fault = _check_scalar_type(field, value, tok, None)
            if fault:
                if field == "id" and "ruling" in (contract.get("required") or []):
                    return ("`id` is %s, not a non-empty string — a ruling with no finding id can never reach "
                            "its target" % _type_name(value))
                return fault
            continue
        if field not in payload:
            return _field_missing(field)
    ordered = list(contract.get("required") or []) + list(contract.get("optional") or [])
    seen = set()
    for field in ordered:
        if field in seen:
            continue
        seen.add(field)
        if field not in payload:
            continue
        tok = types.get(field)
        if tok is not None:
            _assert_type_token(tok, "types")
            if tok in ("list-of-objects", "nullable-list-of-objects"):
                fault = _check_top_level_type(payload, field, tok)
                if fault:
                    return fault
                value = payload.get(field)
                if value is None:
                    continue
                elem_contract = elements.get(field)
                if elem_contract:
                    for index, element in enumerate(value):
                        if not isinstance(element, dict):
                            return "`%s`[%d] is %s, not an object" % (
                                field, index, _type_name(element))
                        fault = _check_element_fields(field, index, element, elem_contract)
                        if fault:
                            return fault
            elif tok != "any":
                fault = _check_top_level_type(payload, field, tok)
                if fault:
                    return fault
        if field in enums:
            value = payload.get(field)
            allowed = enums[field]
            if not isinstance(value, str) or value not in allowed:
                return ("`%s` is %r — expected one of: %s"
                        % (field, value, ", ".join(allowed)))
    return None


def _apply_predicate(pred, payload, seat_key, *, record_boundary=False):
    name = pred.get("name")
    if name == "findings-unless-not-run":
        declared_not_run = payload.get(VACUOUS_FIELD) is True or (
            isinstance(payload.get("reason"), str)
            and payload.get("reason") in dispatch_outcome.NOT_RUN_REASONS)
        if "findings" not in payload and not declared_not_run:
            return ("%s — a seat that ran owes its findings list (a seat that did NOT run says so "
                    "with `reason` / the never-ran flag)" % _field_missing("findings"))
    elif name == "member_ids-non-empty-strings":
        grouping = payload.get("grouping")
        if grouping is None:
            return None
        for index, group in enumerate(grouping):
            member_ids = group.get("member_ids")
            if not isinstance(member_ids, list) or not member_ids:
                return ("`%s`[%d].member_ids is %s, not a non-empty list"
                        % ("grouping", index, _type_name(member_ids)))
            for member_index, member in enumerate(member_ids):
                if not isinstance(member, str) or not member:
                    return ("`%s`[%d].member_ids[%d] is %s, not a non-empty string"
                            % ("grouping", index, member_index, _type_name(member)))
    elif name == "head-diff-store-path-driver-owned":
        if record_boundary and "headDiffStorePath" in payload:
            return ("`headDiffStorePath` is driver-owned — callers must supply `headDiffPath` only; "
                    "the driver copies the diff into the store at record time")
    elif name == "verify-result":
        return round_phases.verify_result_fault(payload)
    elif name == "audit-id-matches-seat":
        rid = payload.get("id")
        if isinstance(seat_key, str) and seat_key and rid != seat_key:
            return ("`id` is %r but this seat is %r — a ruling keyed to another target reaches no "
                    "finding" % (rid, seat_key))
    elif name == "usable-reason":
        if not audits.has_usable_reason(payload.get("reason")):
            return ("`reason` is missing or blank (got %r) — a ruling with no grounds is the unproven "
                    "claim the audit fold exists to reject" % (payload.get("reason"),))
    elif name == "usable-newIssues":
        ruling = payload.get("ruling")
        if ruling == RULING_NEW_ISSUE and not audits.has_usable_new_issues(payload.get("newIssues")):
            detail = ("`newIssues` carries no usable issue object (got %r) — a %s ruling owes the new "
                      "issue it claims" % (payload.get("newIssues"), RULING_NEW_ISSUE))
            if "newIssue" in payload:
                detail += "; the payload carries `newIssue` (singular) — the driver consumes a LIST"
            return detail
    else:
        raise ValueError("unknown predicate %r" % name)
    return None


def _apply_predicates(payload, contract, seat_key, *, record_boundary=False):
    for pred in contract.get("predicates") or []:
        fault = _apply_predicate(pred, payload, seat_key, record_boundary=record_boundary)
        if fault:
            return fault
    return None


def _payload_fault_from_contract(payload, phase, seat_key, *, record_boundary=False):
    contract = _PAYLOAD_CONTRACTS[phase]
    for pred in contract.get("predicates") or []:
        if pred.get("name") == "verify-result":
            fault = _apply_predicate(pred, payload, seat_key, record_boundary=record_boundary)
            if fault:
                return fault
            break
    fault = _check_declared(payload, contract, record_boundary=record_boundary)
    if fault:
        return fault
    for pred in contract.get("predicates") or []:
        if pred.get("name") == "verify-result":
            continue
        fault = _apply_predicate(pred, payload, seat_key, record_boundary=record_boundary)
        if fault:
            return fault
    return None


def _panel_payload_fault(payload, seat_key):
    """A reviewer seat. `confidence` and `tier` are LOAD-BEARING — `_fold_panel` reads both into the
    per-dimension review record `_confirmation_qualifies` judges — so a mis-shaped one is named.

    The `vacuous` FLAG matters more than it looks: `_fold_panel` tests it with `is True`, so a
    non-boolean truthy value ("yes", 1) does NOT mark the seat never-ran and the seat counts toward
    certification. Naming it at record time is what keeps a mis-typed flag from certifying.
    """
    return _payload_fault_from_contract(payload, P_PANEL, seat_key)


def _verifiers_payload_fault(payload, seat_key):
    """A verifier cluster. `verification.apply_verdicts` keys on `id` (NOT `findingId`) and consumes
    `reason` and `severity`, so those are exactly the fields named here."""
    return _payload_fault_from_contract(payload, P_VERIFIERS, seat_key)


def _synthesis_payload_fault(payload, seat_key):
    """The merge grouping `verification.merge_and_rank` consumes. `None` (no merging proposed) is a
    real answer; a mis-shaped grouping is not — `_valid_grouping` would silently discard it, losing
    the merge with no disclosure."""
    return _payload_fault_from_contract(payload, P_SYNTHESIS, seat_key)


def _gap_sweep_payload_fault(payload, seat_key):
    """The gap-sweep candidate list."""
    return _payload_fault_from_contract(payload, P_GAPSWEEP, seat_key)


def _scoped_payload_fault(payload, seat_key):
    """The scoped-finder candidate list."""
    return _payload_fault_from_contract(payload, P_SCOPED, seat_key)


def _fixer_payload_fault(payload, seat_key, record_boundary=False):
    return _payload_fault_from_contract(payload, P_FIXER, seat_key,
                                        record_boundary=record_boundary)


def _verify_payload_fault(payload, seat_key):
    """Delegates the `result` vocabulary to `round_phases.verify_result_fault`."""
    fault = _payload_fault_from_contract(payload, P_VERIFY, seat_key)
    if fault:
        return fault
    return None


def _audits_payload_fault(payload, seat_key):
    """One auditor's ruling. `ruling` is validated against `audits.AUDIT_RULINGS` — the enum
    imported from its own home, never a hand-copy — and the grounds/new-issue predicates are
    `audits`' OWN (`has_usable_reason` / `has_usable_new_issues`), so what this accepts is exactly
    what the fold can use.

    `reason` is required on EVERY ruling here (the driver's submit-shape guard requires it only on
    `discharged`): at RECORD time a reasonless ruling is a re-dispatch away from being right, and a
    ruling with no grounds is the unproven claim the audit fold exists to reject.
    """
    return _payload_fault_from_contract(payload, P_AUDITS, seat_key)


_PAYLOAD_CHECKERS = {
    P_PANEL: _panel_payload_fault,
    P_VERIFIERS: _verifiers_payload_fault,
    P_SYNTHESIS: _synthesis_payload_fault,
    P_GAPSWEEP: _gap_sweep_payload_fault,
    P_SCOPED: _scoped_payload_fault,
    P_FIXER: lambda payload, seat_key: _fixer_payload_fault(payload, seat_key),
    P_VERIFY: _verify_payload_fault,
    P_AUDITS: _audits_payload_fault,
}

# Declared payload field bindings — one home for required/optional/conditional/enums; drift-tested
# against the payload_fault checkers in test_round_adapters.py.
_PAYLOAD_FIELD_BINDINGS = {
    P_PANEL: {
        "required": [],
        "optional": ["findings", "confidence", "tier", "receiptMissing", "receiptStale",
                     VACUOUS_FIELD, "reason"],
        "conditional": {
            "findings": ("required unless the seat declared it did not run "
                         "(vacuous is True or reason is a not-run outcome token)"),
        },
        "enums": {},
        "types": {
            "findings": "list-of-objects",
            "confidence": "non-empty-string",
            "tier": "non-empty-string",
            "receiptMissing": "boolean",
            "receiptStale": "boolean",
            VACUOUS_FIELD: "boolean",
            "reason": "string",
        },
        "elements": {
            "findings": {"required": [], "optional": [], "types": {}, "enums": {}},
        },
        "predicates": [{
            "name": "findings-unless-not-run",
            "fields": ["findings", VACUOUS_FIELD, "reason"],
            "rule": ("findings is required unless vacuous is True or reason is a not-run outcome "
                     "token"),
        }],
    },
    P_VERIFIERS: {
        "required": ["verdicts"],
        "optional": [],
        "conditional": {},
        "enums": {},
        "types": {"verdicts": "list-of-objects"},
        "elements": {
            "verdicts": {
                "required": ["id", "verdict"],
                "optional": ["reason", "severity", "evidence"],
                "types": {
                    "id": "non-empty-string",
                    "verdict": "non-empty-string",
                    "reason": "string",
                    "severity": "string",
                    "evidence": "string",
                },
                "enums": {"verdict": list(round_phases.VERDICTS)},
            },
        },
        "predicates": [],
    },
    P_SYNTHESIS: {
        "required": ["grouping"],
        "optional": [],
        "conditional": {},
        "enums": {},
        "types": {"grouping": "nullable-list-of-objects"},
        "elements": {
            "grouping": {
                "required": ["member_ids"],
                "optional": [],
                "types": {"member_ids": "list"},
                "enums": {},
            },
        },
        "predicates": [{
            "name": "member_ids-non-empty-strings",
            "fields": ["grouping"],
            "rule": "each group member_ids must be a non-empty list of non-empty strings",
        }],
    },
    P_GAPSWEEP: {
        "required": ["findings"],
        "optional": [],
        "conditional": {},
        "enums": {},
        "types": {"findings": "list-of-objects"},
        "elements": {
            "findings": {"required": [], "optional": [], "types": {}, "enums": {}},
        },
        "predicates": [],
    },
    P_SCOPED: {
        "required": ["findings"],
        "optional": [],
        "conditional": {},
        "enums": {},
        "types": {"findings": "list-of-objects"},
        "elements": {
            "findings": {"required": [], "optional": [], "types": {}, "enums": {}},
        },
        "predicates": [],
    },
    P_FIXER: {
        "required": ["fixes"],
        "optional": ["escalated", "headDiff", "headDiffPath", "coverageDecisions"],
        "conditional": {},
        "enums": {},
        "types": {
            "fixes": "list",
            "escalated": "boolean",
            "headDiff": "string",
            "headDiffPath": "absolute-path",
            "coverageDecisions": "list-of-objects",
        },
        "elements": {
            "coverageDecisions": {"required": [], "optional": [], "types": {}, "enums": {}},
        },
        "predicates": [{
            "name": "head-diff-store-path-driver-owned",
            "fields": ["headDiffStorePath"],
            "rule": "headDiffStorePath is driver-owned at record boundary",
        }],
    },
    P_VERIFY: {
        "required": ["result"],
        "optional": ["command", "exit", "outputSha256"],
        "conditional": {},
        "enums": {"result": list(round_phases._VERIFY_RESULTS)},
        "types": {
            "result": "any",
            "command": "string",
            "exit": "integer",
            "outputSha256": "string",
        },
        "elements": {},
        "predicates": [{
            "name": "verify-result",
            "fields": ["result"],
            "rule": "result must be a recognized verify token per round_phases.verify_result_fault",
        }],
    },
    P_AUDITS: {
        "required": ["id", "ruling", "reason"],
        "optional": ["newIssues", "evidence", "auditorVendor"],
        "conditional": {
            "newIssues": "required when ruling is %s" % RULING_NEW_ISSUE,
        },
        "enums": {"ruling": list(audits.AUDIT_RULINGS)},
        "types": {
            "id": "non-empty-string",
            "ruling": "non-empty-string",
            "reason": "any",
            "newIssues": "list-of-objects",
            "evidence": "string",
            "auditorVendor": "string",
        },
        "elements": {
            "newIssues": {"required": [], "optional": [], "types": {}, "enums": {}},
        },
        "predicates": [
            {
                "name": "audit-id-matches-seat",
                "fields": ["id"],
                "rule": "id must equal the roster seat key",
            },
            {
                "name": "usable-reason",
                "fields": ["reason"],
                "rule": "reason must pass audits.has_usable_reason",
            },
            {
                "name": "usable-newIssues",
                "fields": ["newIssues", "ruling"],
                "rule": ("newIssues must pass audits.has_usable_new_issues when ruling is "
                         "discharged-but-new-issue"),
            },
        ],
    },
}

_PAYLOAD_CONTRACTS = {
    phase: copy.deepcopy(spec) for phase, spec in _PAYLOAD_FIELD_BINDINGS.items()
}


def payload_contract(phase):
    """({required, optional, enums, conditional?, types, elements, predicates}, reason_or_None).

    The declared per-seat payload shape for `phase`, as data. An unknown phase or a phase with no
    checker returns an empty contract plus a distinct reason — never a silent empty contract.
    """
    if phase not in ADAPTER_PHASES:
        return {}, "unknown-phase:%s" % _label(phase)
    if phase not in _PAYLOAD_CHECKERS:
        return {}, "no-payload-checker:%s" % _label(phase)
    return copy.deepcopy(_PAYLOAD_CONTRACTS[phase]), None


def payload_fault(phase, payload, seat_key, record_boundary=False):
    """A reason string naming the offending field, or None. Never raises."""
    if phase not in ADAPTER_PHASES:
        return "unknown-phase:%s" % _label(phase)
    if not isinstance(payload, dict):
        return "payload is %s, not an object" % _type_name(payload)
    try:
        if phase == P_FIXER:
            return _fixer_payload_fault(payload, seat_key, record_boundary=record_boundary)
        return _PAYLOAD_CHECKERS[phase](payload, seat_key)
    except Exception as exc:  # noqa: BLE001 — a validator that raises must not crash the adapter
        return "payload-validator-error:%s:%s" % (_type_name(exc), exc)

