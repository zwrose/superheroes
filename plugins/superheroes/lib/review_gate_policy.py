#!/usr/bin/env python3
"""Gate-policy/1 library for owner-judgment and stall-menu pre-authorization.

Resolves narrow calibration-time rules for ``present-judgment`` and ``present-stall-menu``
without letting a builder authorize anything. Two layers: optional caller-supplied calibration
overlay (evaluated first) and the shipped rubric default (empty rules → park). Fail-closed
throughout; never raises."""
from __future__ import annotations

import hashlib
import json
import os

import panel_tally
import round_phases

GATE_POLICY_SCHEMA = "gate-policy/1"
GATE_PRESENT_JUDGMENT = "present-judgment"
GATE_PRESENT_STALL_MENU = "present-stall-menu"
PARK = "park"

GATES = (GATE_PRESENT_JUDGMENT, GATE_PRESENT_STALL_MENU)
JUDGMENT_DISPOSITIONS = round_phases.JUDGMENT_DISPOSITIONS
# Policy rules may authorize only dispositions the resolver can fulfil without owner input.
POLICY_JUDGMENT_DISPOSITIONS = ("fix-as-suggested", "skip")
STALL_CHOICES = round_phases.STALL_CHOICES

# Exact ``_park`` reason tokens (non-parameterized) — authoritative vocabulary for drift guards.
RESOLVER_PARK_CAUSES = frozenset({
    "gate-policy-judgment-input-not-list",
    "gate-policy-no-valid-layer",
    "gate-policy-judgment-row-not-object",
    "gate-policy-judgment-row-missing-class",
    "gate-policy-unknown-stall-class",
})

STALL_CLASS_ELIGIBLE = "stall:accept-risk-eligible"
STALL_CLASS_INELIGIBLE = "stall:accept-risk-ineligible"
STALL_FINDING_CLASSES = frozenset((STALL_CLASS_ELIGIBLE, STALL_CLASS_INELIGIBLE))

ACCEPT_RISK_CHOICE = round_phases.ACCEPT_RISK_CHOICE


def gate_policy_path(root: str | None = None) -> str:
    """Absolute path to the shipped gate-policy artifact."""
    if root is None:
        base = os.path.dirname(os.path.abspath(__file__))
        return os.path.normpath(os.path.join(base, "..", "rubric", "review-gate-policy.json"))
    return os.path.normpath(os.path.join(root, "rubric", "review-gate-policy.json"))


def judgment_severities() -> tuple[str, ...]:
    """Lower-cased severity vocabulary from ``panel_tally.SEV_RANK``."""
    return tuple(sev.lower() for sev in panel_tally.SEV_RANK)


def judgment_finding_classes() -> frozenset[str]:
    """Closed enum: ``judgment:<severity>`` over the severity vocabulary."""
    return frozenset("judgment:%s" % sev for sev in judgment_severities())


def stall_finding_classes() -> frozenset[str]:
    return STALL_FINDING_CLASSES


def _stall_allowed_dispositions(finding_class: str) -> tuple[str, ...]:
    if finding_class == STALL_CLASS_ELIGIBLE:
        return STALL_CHOICES
    if finding_class == STALL_CLASS_INELIGIBLE:
        return tuple(c for c in STALL_CHOICES if c != ACCEPT_RISK_CHOICE)
    return ()


def _judgment_allowed_dispositions(_finding_class: str) -> tuple[str, ...]:
    return POLICY_JUDGMENT_DISPOSITIONS


def _allowed_dispositions(gate: str, finding_class: str) -> tuple[str, ...]:
    if gate == GATE_PRESENT_JUDGMENT:
        return _judgment_allowed_dispositions(finding_class)
    if gate == GATE_PRESENT_STALL_MENU:
        return _stall_allowed_dispositions(finding_class)
    return ()


def _known_finding_classes(gate: str) -> frozenset[str]:
    if gate == GATE_PRESENT_JUDGMENT:
        return judgment_finding_classes()
    if gate == GATE_PRESENT_STALL_MENU:
        return stall_finding_classes()
    return frozenset()


def _park(reason: str, layers: list[dict] | None = None) -> dict:
    return {"action": PARK, "reason": reason, "layers": layers or [], "matches": []}


def _read_shipped_bytes(path: str) -> tuple[bytes | None, str | None]:
    try:
        with open(path, "rb") as fh:
            return fh.read(), None
    except FileNotFoundError:
        return None, "gate-policy-shipped-missing"
    except OSError:
        return None, "gate-policy-shipped-unreadable"


def _parse_json_bytes(raw: bytes) -> tuple[dict | None, str | None]:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, "gate-policy-shipped-unparseable"
    if not isinstance(data, dict):
        return None, "gate-policy-shipped-unparseable"
    return data, None


def _validate_layer(
    data: dict,
    *,
    source: str,
    sha256: str,
) -> tuple[dict | None, str | None]:
    schema = data.get("schema")
    if schema != GATE_POLICY_SCHEMA:
        return None, "layer-invalid-schema"

    if data.get("default") != PARK:
        return None, "layer-invalid-default"

    rules_raw = data.get("rules")
    if not isinstance(rules_raw, list):
        return None, "layer-rules-not-list"

    normalized_rules: list[dict] = []
    for rule in rules_raw:
        if not isinstance(rule, dict):
            return None, "layer-rule-not-object"

        gate = rule.get("gate")
        if gate not in GATES:
            return None, "layer-unknown-gate"

        finding_class = rule.get("findingClass")
        if not isinstance(finding_class, str) or finding_class not in _known_finding_classes(gate):
            return None, "layer-unknown-finding-class"

        disposition = rule.get("disposition")
        if not isinstance(disposition, str):
            return None, "layer-unknown-disposition"
        allowed = _allowed_dispositions(gate, finding_class)
        if disposition not in allowed:
            return None, "layer-disposition-not-allowed"
        if (
            gate == GATE_PRESENT_STALL_MENU
            and finding_class == STALL_CLASS_INELIGIBLE
            and disposition == ACCEPT_RISK_CHOICE
        ):
            return None, "layer-disposition-not-allowed"

        normalized_rules.append(
            {
                "gate": gate,
                "findingClass": finding_class,
                "disposition": disposition,
            }
        )

    identity = {"source": source, "schema": GATE_POLICY_SCHEMA, "sha256": sha256}
    return {
        "identity": identity,
        "rules": normalized_rules,
        "default": PARK,
    }, None


def validate_policy_for_write(policy: object) -> str | None:
    """Validate a gate-policy/1 document for calibration write.

    Returns a human-readable refusal string, or ``None`` when valid. Never raises."""
    if not isinstance(policy, dict):
        return "policy must be a JSON object"
    schema = policy.get("schema")
    if schema != GATE_POLICY_SCHEMA:
        return "schema must be %s (got %r)" % (GATE_POLICY_SCHEMA, schema)
    default = policy.get("default")
    if default != PARK:
        return "default must be %r (got %r)" % (PARK, default)
    rules_raw = policy.get("rules")
    if not isinstance(rules_raw, list):
        return "rules must be a list"
    for index, rule in enumerate(rules_raw):
        if not isinstance(rule, dict):
            return "rules[%d] must be an object" % index
        gate = rule.get("gate")
        if gate not in GATES:
            return "rules[%d].gate must be one of %s (got %r)" % (
                index, ", ".join(GATES), gate)
        finding_class = rule.get("findingClass")
        known = _known_finding_classes(gate)
        if not isinstance(finding_class, str) or finding_class not in known:
            return "rules[%d].findingClass must be one of %s (got %r)" % (
                index, ", ".join(sorted(known)), finding_class)
        disposition = rule.get("disposition")
        allowed = _allowed_dispositions(gate, finding_class)
        if not isinstance(disposition, str) or disposition not in allowed:
            return "rules[%d].disposition for gate %s class %s must be one of %s (got %r)" % (
                index, gate, finding_class, ", ".join(allowed), disposition)
    source = "calibration/write-check"
    raw = json.dumps(policy, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    _, reason = _validate_layer(policy, source=source, sha256=digest)
    return reason


def calibration_layer_resolution(overlay_raw: dict | None) -> dict:
    """Shipped + overlay parse results for calibration consumers. Never raises."""
    overlay_parse = None
    if overlay_raw is not None:
        overlay_parse = parse_overlay(overlay_raw)
    return {
        "shipped": load_shipped_layer(),
        "overlayParse": overlay_parse,
    }


def load_shipped_layer(path: str | None = None) -> dict:
    """Load and validate the shipped gate-policy layer. Never raises."""
    target = gate_policy_path() if path is None else path
    raw, read_reason = _read_shipped_bytes(target)
    if raw is None:
        return {"ok": False, "reason": read_reason, "layer": None}

    data, parse_reason = _parse_json_bytes(raw)
    if data is None:
        return {"ok": False, "reason": parse_reason, "layer": None}

    digest = hashlib.sha256(raw).hexdigest()
    layer, reason = _validate_layer(data, source=target, sha256=digest)
    if layer is None:
        return {"ok": False, "reason": reason, "layer": None}
    return {"ok": True, "reason": None, "layer": layer}


def parse_overlay(overlay: dict | None) -> dict:
    if not overlay:
        return {"ok": False, "reason": "overlay-absent", "layer": None}
    if not isinstance(overlay, dict):
        return {"ok": False, "reason": "overlay-not-object", "layer": None}

    identity = overlay.get("identity")
    policy = overlay.get("policy")
    if not isinstance(identity, dict) or not isinstance(policy, dict):
        return {"ok": False, "reason": "overlay-malformed", "layer": None}

    source = identity.get("source")
    schema = identity.get("schema")
    sha256 = identity.get("sha256")
    if not isinstance(source, str) or not isinstance(schema, str) or not isinstance(sha256, str):
        return {"ok": False, "reason": "overlay-malformed", "layer": None}

    if schema != GATE_POLICY_SCHEMA:
        return {"ok": False, "reason": "layer-invalid-schema", "layer": None}

    try:
        policy_bytes = json.dumps(
            policy, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError):
        return {"ok": False, "reason": "overlay-malformed", "layer": None}
    computed = hashlib.sha256(policy_bytes).hexdigest()
    if computed != sha256:
        return {"ok": False, "reason": "overlay-digest-mismatch", "layer": None}

    layer, reason = _validate_layer(policy, source=source, sha256=sha256)
    if layer is None:
        return {"ok": False, "reason": reason, "layer": None}
    return {"ok": True, "reason": None, "layer": layer}


def _layer_record(
    layer: dict | None,
    *,
    ok: bool,
    reason: str | None,
    used: bool,
    identity: dict | None = None,
) -> dict:
    ident = identity if identity is not None else (layer["identity"] if layer else None)
    if ident is None:
        return {"identity": None, "ok": ok, "reason": reason, "used": used, "normalizedRules": []}
    return {
        "identity": dict(ident),
        "ok": ok,
        "reason": reason,
        "used": used,
        "normalizedRules": [dict(r) for r in (layer or {}).get("rules", [])],
    }


def _active_layers(overlay: dict | None) -> tuple[list[dict], list[dict]]:
    """Return (stack for matching, layer audit records). Overlay precedes shipped."""
    records: list[dict] = []
    stack: list[dict] = []

    overlay_result = parse_overlay(overlay)
    overlay_identity = None
    if isinstance(overlay, dict) and isinstance(overlay.get("identity"), dict):
        overlay_identity = overlay["identity"]
    if overlay_result["ok"]:
        stack.append(overlay_result["layer"])
        records.append(_layer_record(overlay_result["layer"], ok=True, reason=None, used=False))
    elif overlay is not None:
        records.append(
            _layer_record(
                None,
                ok=False,
                reason=overlay_result["reason"],
                used=False,
                identity=overlay_identity,
            )
        )

    shipped = load_shipped_layer()
    if shipped["ok"]:
        stack.append(shipped["layer"])
        records.append(_layer_record(shipped["layer"], ok=True, reason=None, used=False))
    else:
        records.append(_layer_record(None, ok=False, reason=shipped["reason"], used=False))

    return stack, records


def _first_match(stack: list[dict], gate: str, finding_class: str) -> tuple[dict | None, dict | None]:
    for layer in stack:
        for rule in layer["rules"]:
            if rule["gate"] == gate and rule["findingClass"] == finding_class:
                return rule, layer
    return None, None


def resolve_judgment(rows: list, overlay: dict | None = None) -> dict:
    """Resolve per-row judgment dispositions or park. Never raises."""
    if not isinstance(rows, list):
        return _park("gate-policy-judgment-input-not-list")

    stack, records = _active_layers(overlay)
    if not stack:
        return _park("gate-policy-no-valid-layer", records)

    matches: list[dict] = []
    dispositions: list[dict] = []

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            return _park("gate-policy-judgment-row-not-object", records)
        finding_class = row.get("findingClass")
        if not isinstance(finding_class, str):
            return _park("gate-policy-judgment-row-missing-class", records)

        rule, layer = _first_match(stack, GATE_PRESENT_JUDGMENT, finding_class)
        if rule is None:
            return _park("gate-policy-unmatched-class:%s" % finding_class, records)

        for rec in records:
            if rec.get("identity") == layer["identity"]:
                rec["used"] = True
        matches.append(
            {
                "rowIndex": index,
                "matchInput": dict(row),
                "findingClass": finding_class,
                "rule": dict(rule),
                "layer": dict(layer["identity"]),
            }
        )
        dispositions.append(
            {
                "findingClass": finding_class,
                "disposition": rule["disposition"],
            }
        )

    return {
        "action": {"dispositions": dispositions},
        "reason": None,
        "layers": records,
        "matches": matches,
    }


def resolve_stall(stall_class: str, overlay: dict | None = None) -> dict:
    """Resolve one stall-menu choice or park. Never raises."""
    if not isinstance(stall_class, str) or stall_class not in stall_finding_classes():
        return _park("gate-policy-unknown-stall-class")

    stack, records = _active_layers(overlay)
    if not stack:
        return _park("gate-policy-no-valid-layer", records)

    rule, layer = _first_match(stack, GATE_PRESENT_STALL_MENU, stall_class)
    if rule is None:
        return _park("gate-policy-unmatched-class:%s" % stall_class, records)

    for rec in records:
        if rec.get("identity") == layer["identity"]:
            rec["used"] = True

    return {
        "action": {"choice": rule["disposition"]},
        "reason": None,
        "layers": records,
        "matches": [
            {
                "matchInput": {"findingClass": stall_class},
                "findingClass": stall_class,
                "rule": dict(rule),
                "layer": dict(layer["identity"]),
            }
        ],
    }
