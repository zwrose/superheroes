#!/usr/bin/env python3
"""Render per-seat dispatch orders from shipped templates (#723).

Two public entry points, both returning ``(value, reason_or_None)`` and **never raising**:

  * ``render_order(phase, seat_key, context)`` — pure over its inputs; returns the complete order
    text for one seat.
  * ``resolve_order_residuals(repo_root, base_oid)`` — reads ratified residuals from the
    pinned base commit when in-repo, else from the calibration store; never reads the worktree
    under review. ``resolve_base_residuals`` is the base-pinned git cat-file arm only.

Placeholder syntax (documented): ``{{NAME}}`` where ``NAME`` is ``[A-Z][A-Z0-9_]*``. An unfilled
placeholder is a refusal; an unknown placeholder left in a template after substitution is a
refusal. A successful render contains no literal ``{{...}}`` anywhere.

``context`` required keys (all phases):

  * ``session_dir`` — absolute session working directory
  * ``round`` — int, current round number
  * ``attempt`` — int, dispatch attempt within the phase
  * ``diff_path`` — absolute path to the round diff artifact
  * ``rubric_path`` — absolute path to the base rubric
  * ``core_path`` — absolute path to core calibration
  * ``layer_path`` — absolute path to the review-crew layer
  * ``repo_root`` — absolute repository root
  * ``landing_path`` — absolute path this seat must write its result to
  * ``envelope_stub_path`` — absolute path to the envelope stub to copy header fields from
  * ``ratified_residuals`` — resolved residual prose (may be empty string)
  * ``residuals_provenance`` — one line stating which calibration mode produced the list
  * ``residuals_read_failure`` — unreadable/absent reason, or None when the read succeeded
  * ``threat_model`` / ``threat_model_read_failure`` — the project's threat model prose and its
    failure reason (optional keys: absent renders an explicit "could not be read" line, never no block)
  * ``standing_rulings`` / ``standing_rulings_read_failure`` — the live out-of-scope rulings
    (``[{"findingKey", "reason"}]``) and the rulings-log fault (same optional-key rule)
  * ``payload`` — the phase payload dict from the driver
  * ``host_seat`` — bool; host seats write payload-only, engine seats write the full envelope

Phase-specific keys are supplied via ``context["placeholders"]`` — a dict mapping placeholder
names (without braces) to string values the template references. The renderer also injects
derived placeholders (panel channel block, optional context lines) before substitution.

``seat_key`` is passed separately; templates do not substitute it unless the driver places it in
``context["placeholders"]``."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import core_md  # noqa: E402
import mode_registry  # noqa: E402
import order_contract  # noqa: E402
import round_adapters  # noqa: E402
import review_findings_schema  # noqa: E402
import round_phases  # noqa: E402

_PLACEHOLDER_RE = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")

ORDER_PHASES = (
    round_phases.P_PANEL,
    round_phases.P_VERIFIERS,
    round_phases.P_SYNTHESIS,
    round_phases.P_GAPSWEEP,
    round_phases.P_SECOND_TEST,
    round_phases.P_AUDITS,
    round_phases.P_SCOPED,
)

# Placeholder inputs consumed by derivation but not substituted into the template body.
_AUX_PLACEHOLDER_INPUTS = frozenset({
    "CHANNEL",
    "FOCUS_NOTES",
    "FINDINGS_OUTPUT_PATH",
    "GROUPING_OUTPUT_PATH",
    "PRIOR_COMMENTS_PATH",
    "ROLE_BRIEF_PATH",
    "RISK_AREAS_TEXT",
    "BREAK_IT_GRAMMAR_TEXT",
})

_COMMON_CONTEXT_KEYS = (
    "session_dir",
    "round",
    "attempt",
    "diff_path",
    "rubric_path",
    "core_path",
    "layer_path",
    "repo_root",
    "landing_path",
    "envelope_stub_path",
    "ratified_residuals",
    "residuals_provenance",
    "residuals_read_failure",
    "payload",
    "host_seat",
    "placeholders",
)


# The standing rule every seat order carries (#2071), one home for the sentences. It is stated
# positively — what a seat may do — and names no program or command: a forbidden-name list is
# exactly the whack-a-mole the owner ruled out.
SEAT_RULE_HEADING = "## What you may run"

REVIEW_SEAT_RULE = (
    "You review by reading. You may read, list and search files, including with read-only "
    "inspection commands. You never run the project's own files, scripts or tests. A run you "
    "need is the driver's: name it in your result, and the driver runs the project's declared "
    "verify command."
)

def seat_rule_block(phase: str) -> str:
    """The standing-rule block for ``phase``'s order: the review seats' rule."""
    return SEAT_RULE_HEADING + "\n\n" + REVIEW_SEAT_RULE


def order_template_path(phase: str, root: str | None = None) -> str:
    """Absolute path to ``rubric/orders/<phase>.md`` (``phase`` is a template name: see ``_template_name``)."""
    if root is None:
        base = os.path.dirname(os.path.abspath(__file__))
        return os.path.normpath(os.path.join(base, "..", "rubric", "orders", phase + ".md"))
    return os.path.normpath(os.path.join(root, "rubric", "orders", phase + ".md"))


SECOND_TEST_CORRECTION_TEMPLATE = "dispatch-second-test-correction"


def _template_name(phase: str, context: dict) -> str:
    """The template a phase's order is read from: the phase's own, except the second-test phase's
    correction form (payload ``correction`` exactly ``true``), which has a template of its own."""
    payload = context.get("payload")
    if (phase == round_phases.P_SECOND_TEST and isinstance(payload, dict)
            and payload.get("correction") is True):
        return SECOND_TEST_CORRECTION_TEMPLATE
    return phase


def _refuse(reason: str) -> tuple[None, str]:
    return None, reason


def _ok(value: str) -> tuple[str, None]:
    return value, None


def _read_template(phase: str) -> tuple[str | None, str | None]:
    path = order_template_path(phase)
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read(), None
    except FileNotFoundError:
        return None, "template-missing:%s" % phase
    except OSError as exc:
        return None, "template-unreadable:%s:%s" % (phase, exc)


def _element_has_shape(element: dict) -> bool:
    return any(element.get(key) for key in ("required", "optional", "types", "enums"))


def _format_payload_contract(phase: str) -> tuple[str | None, str | None]:
    contract, reason = round_adapters.payload_contract(phase)
    if reason:
        return None, "payload-contract:%s" % reason
    lines = [
        order_contract.PAYLOAD_CONTRACT_HEADING,
        "",
        "Your result must carry a payload matching this shape:",
        "",
    ]
    required = contract.get("required") or []
    lines.append("Required keys: %s" % (", ".join(required) if required else "(none)"))
    optional = contract.get("optional") or []
    if optional:
        lines.append("Optional keys: %s" % ", ".join(optional))
    types = contract.get("types") or {}
    for field in sorted(types):
        lines.append("%s type: %s" % (field, types[field]))
    enums = contract.get("enums") or {}
    for field in sorted(enums):
        values = enums[field]
        lines.append("%s enum: %s" % (field, " | ".join(values)))
    elements = contract.get("elements") or {}
    for field in sorted(elements):
        element = elements[field]
        if not _element_has_shape(element):
            continue
        elem_required = element.get("required") or []
        if elem_required:
            lines.append("%s[] required keys: %s" % (field, ", ".join(elem_required)))
        elem_optional = element.get("optional") or []
        if elem_optional:
            lines.append("%s[] optional keys: %s" % (field, ", ".join(elem_optional)))
        elem_types = element.get("types") or {}
        for key in sorted(elem_types):
            lines.append("%s[].%s type: %s" % (field, key, elem_types[key]))
        elem_enums = element.get("enums") or {}
        for key in sorted(elem_enums):
            values = elem_enums[key]
            lines.append("%s[].%s enum: %s" % (field, key, " | ".join(values)))
    conditional = contract.get("conditional") or {}
    for field in sorted(conditional):
        lines.append("Conditional — %s: %s" % (field, conditional[field]))
    predicates = contract.get("predicates") or []
    for predicate in predicates:
        lines.append("Also enforced — %s: %s" % (predicate["name"], predicate["rule"]))
    return "\n".join(lines), None


def _format_residual_block(context: dict) -> str:
    failure = context.get("residuals_read_failure")
    provenance = context.get("residuals_provenance")
    text = context.get("ratified_residuals")
    text = text if isinstance(text, str) else ""
    prov_line = provenance if isinstance(provenance, str) and provenance.strip() else ""
    if isinstance(failure, str) and failure:
        lines = ["## Ratified residuals", ""]
        if prov_line:
            lines.append(prov_line)
            lines.append("")
        lines.append("Residuals could not be read: %s." % failure)
        return "\n".join(lines) + "\n"
    if text.strip():
        lines = [
            "## Ratified residuals (owner-ratified, quoted data)",
            "",
        ]
        if prov_line:
            lines.append(prov_line)
            lines.append("")
        lines.extend([
            "A finding that reduces wholly to a recorded residual below is a non-blocking "
            "restatement, not a blocker.",
            "",
            "-----",
            text.rstrip(),
            "-----",
        ])
        return "\n".join(lines) + "\n"
    lines = ["## Ratified residuals", ""]
    if prov_line:
        lines.append(prov_line)
        lines.append("")
    lines.append("No ratified residuals are recorded for this project at the review base.")
    return "\n".join(lines) + "\n"


def escape_placeholder_syntax(text):
    """Escape ``{{`` so quoted owner data cannot inject order placeholders during render.

    Fixed-point: each pass strictly increases length and strictly decreases ``{{`` count, so the
    loop terminates on any finite input. The one home — the driver's guidance path imports it."""
    while "{{" in text:
        text = text.replace("{{", "{ {")
    return text


THREAT_MODEL_HEADING = "## Project threat model (project calibration, quoted data)"
STANDING_RULINGS_HEADING = "## Standing rulings (recorded this session, quoted data)"
THREAT_MODEL_CORE_UNRESOLVED = "core calibration not resolved"


def format_threat_model_block(context: dict) -> str:
    """The project's threat model as quoted data — appended to every order, never absent: an
    unread, unresolved, or empty threat model renders an explicit line in place of the text."""
    lines = [THREAT_MODEL_HEADING, ""]
    failure = context.get("threat_model_read_failure")
    text = context.get("threat_model")
    if isinstance(failure, str) and failure:
        lines.append("The project's threat model could not be read: %s." % failure)
    elif not isinstance(text, str):
        lines.append("The project's threat model could not be read: not supplied to the renderer.")
    elif not text.strip():
        lines.append("No threat model is recorded for this project.")
    else:
        lines.extend(["-----", escape_placeholder_syntax(text.strip()), "-----"])
    return "\n".join(lines) + "\n"


def format_rulings_block(context: dict) -> str:
    """The session's live out-of-scope rulings as quoted data — appended to every order, never
    absent. Each row is ``{"findingKey", "reason"}``; keys and reasons are owner prose."""
    lines = [STANDING_RULINGS_HEADING, ""]
    failure = context.get("standing_rulings_read_failure")
    rows = context.get("standing_rulings")
    if isinstance(failure, str) and failure:
        lines.append("Standing rulings could not be read: %s." % failure)
    elif not isinstance(rows, list):
        lines.append("Standing rulings could not be read: not supplied to the renderer.")
    elif not rows:
        lines.append("No standing rulings are recorded for this session.")
    else:
        lines.extend([
            "Each finding below was ruled out of scope by the session's owner or advisor, with "
            "the reason given. Do not raise it again, under its own title or any other, unless it "
            "is now Critical: a finding that is now Critical is always reported.",
            "",
        ])
        for row in rows:
            key = row.get("findingKey") if isinstance(row, dict) else None
            reason = row.get("reason") if isinstance(row, dict) else None
            key = " ".join(key.split()) if isinstance(key, str) else ""
            reason = " ".join(reason.split()) if isinstance(reason, str) else ""
            lines.append(escape_placeholder_syntax(
                "- %s: out of scope — %s" % (key, reason or "(no reason recorded)")))
    return "\n".join(lines) + "\n"


def resolve_order_threat_model(core_path) -> tuple[str, str | None]:
    """``(threat_model_text, failure_reason)`` read from the resolved core.md path. Never raises.

    Reuses ``core_md.parse_core`` (no second parser). A failure reason is never an empty-text
    success: an unresolved, unreadable, or refused core.md reads as a failure, not as 'none'."""
    try:
        if not isinstance(core_path, str) or not core_path:
            return "", THREAT_MODEL_CORE_UNRESOLVED
        try:
            with open(core_path, encoding="utf-8") as fh:
                raw = fh.read()
        except (OSError, UnicodeDecodeError) as exc:
            return "", "core calibration unreadable (%s)" % type(exc).__name__
        try:
            facts = core_md.parse_core(raw)
        except Exception as exc:  # noqa: BLE001 — a refused parse is a failure line, not a crash
            return "", "core calibration refused (%s)" % type(exc).__name__
        if facts is None:
            return "", "core calibration refused (json block missing or corrupt)"
        text = facts.get("threatModel")
        return (text.strip() if isinstance(text, str) else ""), None
    except Exception as exc:  # noqa: BLE001
        return "", "threat-model-read-failed:%s" % exc


_RESULT_CHANNEL_NEUTRAL_DELIVERY = (
    "Deliver the object on the runner's declared result channel: the runner appends "
    "the authoritative result contract at the end of this prompt — when it names a "
    "result file, write exactly that file and reply DONE; otherwise emit the object "
    "as your final response with nothing after it. Never write a landing file "
    "(read-only sandbox)."
)


def _result_channel_neutral_delivery(stdout_example=None):
    """Channel-neutral delivery prose for engine seats (stdout or typed-file)."""
    if stdout_example is None:
        return _RESULT_CHANNEL_NEUTRAL_DELIVERY
    return (
        "Deliver the object on the runner's declared result channel: the runner appends "
        "the authoritative result contract at the end of this prompt — when it names a "
        "result file, write exactly that file and reply DONE; otherwise emit `%s` as your "
        "final response with nothing after it. Never write a landing file "
        "(read-only sandbox)." % stdout_example
    )


_READ_PARTS_REMINDER = (
    "Return `readParts` — one entry per file you actually read, with the line ranges of it you "
    "read (the file's lines at the reviewed head), as the base rubric defines it; `[]` when you "
    "read nothing."
)


def _panel_stdout_delivery_text(include_investigated_reminder: bool = False) -> str:
    """Format-only panel stdout delivery — shape illustration, not a literal emit target."""
    lines = [
        review_findings_schema.example_prompt_block(),
        "",
        "Deliver a single JSON object of this shape on the runner's declared result channel: "
        "the runner appends the authoritative result contract at the end of this prompt — "
        "when it names a result file, write exactly that file and reply DONE; otherwise emit "
        "the object as your final response with nothing after it. Never write a landing file "
        "(read-only sandbox). Replace every value in the example above with your own review "
        "content — do not echo the example. A review with nothing to flag emits "
        "`\"findings\": []` (an empty list).",
    ]
    if include_investigated_reminder:
        lines.append(
            "List in `investigated` every repo-relative path you actually read to ground "
            "this review — always, whether or not you found anything. " + _READ_PARTS_REMINDER
        )
    return "\n".join(lines)


def _stdout_payload_example(phase: str) -> tuple[str | None, str | None]:
    """Minimal stdout JSON example derived from the phase payload contract — one home with the block above."""
    contract, reason = round_adapters.payload_contract(phase)
    if reason:
        return None, "payload-contract:%s" % reason
    required = contract.get("required") or []
    if phase == round_phases.P_PANEL:
        return json.dumps(
            review_findings_schema.example_findings_object(), sort_keys=True,
        ), None
    if phase == round_phases.P_AUDITS:
        # Audits stdout contract (id/ruling/reason) — not the findings-member schema; do not
        # route through review_findings_schema.example_findings_object().
        return '{"id": "...", "ruling": "...", "reason": "..."}', None
    if not required:
        return '{...}', None
    inner = ", ".join('"%s": [...]' % key for key in required)
    return '{%s}' % inner, None


def _format_landing_block(context: dict, phase: str) -> tuple[str | None, str | None]:
    landing = context.get("landing_path")
    stub = context.get("envelope_stub_path")
    if not isinstance(landing, str) or not landing:
        return None, "context-missing:landing_path"
    if not isinstance(stub, str) or not stub:
        return None, "context-missing:envelope_stub_path"
    host_seat = context.get("host_seat") is True
    lines = ["## Return your result", ""]
    if host_seat:
        lines.extend([
            "Write **only** your payload artifact to the landing path below — no envelope header, "
            "no stub copy.",
            "",
            "- Payload landing path: %s" % landing,
        ])
    else:
        if phase == round_phases.P_PANEL:
            lines.extend([_RESULT_CHANNEL_NEUTRAL_DELIVERY])
        else:
            stdout_example, reason = _stdout_payload_example(phase)
            if reason:
                return None, reason
            lines.extend([_result_channel_neutral_delivery(stdout_example)])
    return "\n".join(lines), None


def _validate_common_context(context: object) -> str | None:
    if not isinstance(context, dict):
        return "context-not-a-dict:%s" % type(context).__name__
    for key in _COMMON_CONTEXT_KEYS:
        if key not in context:
            return "context-missing:%s" % key
    if not isinstance(context.get("placeholders"), dict):
        return "context-placeholders-not-a-dict"
    if not isinstance(context.get("payload"), dict):
        return "context-payload-not-a-dict"
    return None


def _test_role_derived_placeholders(ph: dict) -> dict[str, str]:
    """``ph`` with the test role's brief line and break-it grammar block derived from the order inputs
    ``ROLE_BRIEF_PATH`` and ``BREAK_IT_GRAMMAR_TEXT`` — one home for the panel's test-role order and the
    second-test order."""
    ph = dict(ph)
    role_brief = ph.get("ROLE_BRIEF_PATH", "").strip()
    ph["ROLE_BRIEF_LINE"] = (
        "- Your role brief (read it first; it binds over the generic assignment above): %s"
        % role_brief if role_brief else ""
    )
    grammar_text = ph.get("BREAK_IT_GRAMMAR_TEXT", "").strip()
    ph["BREAK_IT_GRAMMAR_BLOCK"] = (
        "- The break-it block (a break-it finding's suggestion is exactly this; the loop parses it):\n\n"
        + grammar_text if grammar_text else ""
    )
    return ph


def _panel_derived_placeholders(context: dict) -> dict[str, str]:
    ph = dict(context.get("placeholders") or {})
    channel = ph.get("CHANNEL", "file")
    landing = context.get("landing_path", "")
    if channel == "stdout":
        # Delivery block is format-only (wraps review_findings_schema.example_findings_object).
        ph["OUTPUT_CHANNEL_BLOCK"] = (
            _panel_stdout_delivery_text(include_investigated_reminder=True)
            + " do not write a findings file (read-only sandbox — nothing reads one)."
        )
    else:
        ph["OUTPUT_CHANNEL_BLOCK"] = (
            "Deliver per the base rubric's panel output-format section. Write your payload "
            "artifact to %s — write an empty findings list rather than skipping the file when "
            "you have nothing to flag. " % landing + _READ_PARTS_REMINDER
        )
    prior = ph.get("PRIOR_COMMENTS_PATH", "").strip()
    ph["PRIOR_COMMENTS_CONTEXT_LINE"] = (
        "- Prior comments + author justifications: %s" % prior if prior else ""
    )
    prior_instr = ph.get("PRIOR_COMMENTS_PATH", "")
    if not isinstance(prior_instr, str):
        prior_instr = ""
    if prior_instr and not prior_instr.startswith("("):
        ph["PRIOR_COMMENTS_INSTRUCTION_BLOCK"] = (
            "%s contains prior review comments and their\nthreads." % prior_instr
        )
    elif prior_instr.startswith("("):
        ph["PRIOR_COMMENTS_INSTRUCTION_BLOCK"] = (
            "No prior-comments.json was supplied for this PR — there are no prior review "
            "comments or author justifications to consult."
        )
    else:
        ph["PRIOR_COMMENTS_INSTRUCTION_BLOCK"] = ""
    focus = ph.get("FOCUS_NOTES", "").strip()
    ph["FOCUS_CONTEXT_LINE"] = (
        "- Focus: %s" % focus if focus else ""
    )
    risk_text = ph.get("RISK_AREAS_TEXT", "").strip()
    ph["RISK_AREAS_LINE"] = (
        "- Risk areas this change touches: %s" % risk_text if risk_text else ""
    )
    return _test_role_derived_placeholders(ph)


def _channel_derived_placeholders(phase: str, context: dict) -> dict[str, str]:
    ph = dict(context.get("placeholders") or {})
    channel = ph.get("CHANNEL", "file")
    landing = context.get("landing_path", "")
    stdout_example, reason = _stdout_payload_example(phase)
    if channel == "stdout":
        if reason:
            ph["OUTPUT_CHANNEL_BLOCK"] = ""
            return ph
        if phase == round_phases.P_SYNTHESIS:
            ph["OUTPUT_CHANNEL_BLOCK"] = (
                _result_channel_neutral_delivery(stdout_example)
                + " Every survivor id appears exactly once across all groups."
            )
        else:
            ph["OUTPUT_CHANNEL_BLOCK"] = _result_channel_neutral_delivery(stdout_example)
    elif phase == round_phases.P_VERIFIERS:
        ph["OUTPUT_CHANNEL_BLOCK"] = (
            "Write your verdict payload to %s — the `verdicts` array carries exactly one entry "
            "per cluster issue." % landing
        )
    elif phase == round_phases.P_SYNTHESIS:
        ph["OUTPUT_CHANNEL_BLOCK"] = (
            "Write your grouping payload to %s.\n"
            "every survivor id appears exactly once across all groups." % landing
        )
    elif phase in (round_phases.P_GAPSWEEP, round_phases.P_SECOND_TEST, round_phases.P_SCOPED):
        ph["OUTPUT_CHANNEL_BLOCK"] = (
            "Deliver per the base rubric's panel output-format section. Write your findings "
            "payload to %s — write an empty findings list rather than skipping the file when "
            "you have nothing to flag." % landing
        )
    else:
        ph["OUTPUT_CHANNEL_BLOCK"] = ""
    return ph


def _derived_placeholders(phase: str, context: dict) -> dict[str, str]:
    ph = dict(context.get("placeholders") or {})
    if phase == round_phases.P_PANEL:
        ph = _panel_derived_placeholders(context)
    elif phase in (round_phases.P_VERIFIERS, round_phases.P_SYNTHESIS,
                   round_phases.P_GAPSWEEP, round_phases.P_SECOND_TEST, round_phases.P_SCOPED):
        ph = _channel_derived_placeholders(phase, context)
        if phase == round_phases.P_SECOND_TEST:
            ph = _test_role_derived_placeholders(ph)
    return ph


def render_order(phase: str, seat_key: str, context: dict) -> tuple[str | None, str | None]:
    """Return ``(order_text, None)`` or ``(None, reason)``. Never raises."""
    try:
        fault = _validate_common_context(context)
        if fault:
            return _refuse(fault)
        if phase not in ORDER_PHASES:
            return _refuse("no-template:%s" % phase)

        template, reason = _read_template(_template_name(phase, context))
        if reason:
            return _refuse(reason)

        template_placeholders = set(_PLACEHOLDER_RE.findall(template or ""))
        values = _derived_placeholders(phase, context)
        for name in template_placeholders:
            if name not in values:
                return _refuse("unfilled-placeholder:%s" % name)

        for name in sorted(context.get("placeholders") or {}):
            if name not in template_placeholders and name not in _AUX_PLACEHOLDER_INPUTS:
                return _refuse("unused-context-key:%s" % name)

        body = template
        for name in template_placeholders:
            body = body.replace("{{" + name + "}}", values[name])

        if _PLACEHOLDER_RE.search(body):
            return _refuse("unknown-placeholder-remaining")

        blocks = [body.rstrip(), seat_rule_block(phase),
                  _format_residual_block(context).rstrip(),
                  format_threat_model_block(context).rstrip(),
                  format_rulings_block(context).rstrip()]
        contract_block, creason = _format_payload_contract(phase)
        if creason:
            return _refuse(creason)
        blocks.append(contract_block.rstrip())
        landing_block, lreason = _format_landing_block(context, phase)
        if lreason:
            return _refuse(lreason)
        blocks.append(landing_block.rstrip())

        order = "\n\n".join(blocks) + "\n"

        if _PLACEHOLDER_RE.search(order):
            return _refuse("post-condition-placeholder-leak")

        return _ok(order)
    except Exception as exc:  # noqa: BLE001 — renderer must never raise
        return _refuse("render-error:%s:%s" % (type(exc).__name__, exc))


def resolve_base_residuals(
    repo_root: str,
    base_oid: str | None,
    core_rel_path: str,
) -> tuple[str, str | None]:
    """Read ratified residuals from ``core.md`` at the pinned base commit. Never raises."""
    try:
        if not base_oid or not isinstance(base_oid, str):
            return "", "no-base-oid"
        if not isinstance(repo_root, str) or not repo_root:
            return "", "git-cat-file-failed:no-repo-root"
        if not isinstance(core_rel_path, str) or not core_rel_path:
            return "", "git-cat-file-failed:no-core-path"

        spec = "%s:%s" % (base_oid, core_rel_path)
        try:
            proc = subprocess.run(
                ["git", "-C", repo_root, "cat-file", "blob", spec],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
            return "", "git-cat-file-failed:%s" % exc

        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            if "Not a valid object" in err or "does not exist" in err:
                return "", "no-core-at-base"
            return "", "git-cat-file-failed:%s" % (err or proc.returncode)

        parsed = core_md.parse_core(proc.stdout)
        if parsed is None:
            return "", "no-core-at-base"
        residuals = parsed.get("ratifiedResiduals") or ""
        if not isinstance(residuals, str):
            return "", "no-residual-section"
        return residuals.strip(), None
    except Exception as exc:  # noqa: BLE001
        return "", "git-cat-file-failed:%s" % exc


def resolve_order_residuals(repo_root: str, base_oid: str | None) -> tuple[str, str | None, str | None]:
    """Read ratified residuals for order rendering — base-pinned in-repo, store-direct out-of-repo.

    Returns ``(residual_text, provenance_line, failure_reason)``. ``failure_reason`` is set when the
    calibration read failed or is unreadable; never claim 'none recorded' on a failure."""
    try:
        if not isinstance(repo_root, str) or not repo_root.strip():
            return "", None, "no-repo-root"
        mode = mode_registry.resolve(repo_root).get("mode")
        if mode == mode_registry.IN_REPO:
            provenance = (
                "Residuals below are read from the review base commit (base-pinned)."
            )
            core_rel = core_md.in_repo_core_rel_path()
            text, reason = resolve_base_residuals(repo_root, base_oid, core_rel)
            if reason:
                return "", provenance, reason
            return text, provenance, None
        provenance = (
            "Residuals below are read from the calibration store file (not base-pinned)."
        )
        facts = core_md.read(repo_root)
        if facts is None:
            return "", provenance, "core-unreadable-or-absent"
        text = (facts.get("ratifiedResiduals") or "").strip()
        return text, provenance, None
    except Exception as exc:  # noqa: BLE001
        return "", None, "residual-read-failed:%s" % exc


# --- shell-interpreted template census (FX-4A) ---------------------------------

_ANY_FENCE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
_INLINE_TICK_RE = re.compile(r"`([^`\n]+)`")
_ANGLE_SUB_RE = re.compile(r"<([a-zA-Z][a-zA-Z0-9_]*)>")

# Driver-rendered placeholders — not branch-controlled (quoted or numeric at render time).
_SHELL_SAFE_PLACEHOLDERS = frozenset({"REPO_ROOT", "ROUND"})

# Model-authored commit-message slots — not branch-controlled diff paths.
_SAFE_ANGLE_SUBSTITUTIONS = frozenset({"count", "dimensions"})


def iter_shell_interpreted_regions(body: str):
    """Yield every fenced block and inline backtick span — fail-closed on placeholders inside."""
    for match in _ANY_FENCE_RE.finditer(body):
        yield match.group(1)
    for match in _INLINE_TICK_RE.finditer(body):
        yield match.group(1)


def scan_template_shell_violations(template_body: str, template_id: str) -> list[str]:
    """Flag placeholders or substitution markers inside shell-interpreted template regions."""
    violations = []
    for region in iter_shell_interpreted_regions(template_body):
        for match in _PLACEHOLDER_RE.finditer(region):
            name = match.group(1)
            if name not in _SHELL_SAFE_PLACEHOLDERS:
                violations.append(
                    "%s: shell region contains unfenced placeholder {{%s}}" % (template_id, name))
        for match in _ANGLE_SUB_RE.finditer(region):
            name = match.group(1)
            if name not in _SAFE_ANGLE_SUBSTITUTIONS:
                violations.append(
                    "%s: shell region contains substitution marker <%s>" % (template_id, name))
    return violations


def scan_all_order_templates_shell_violations(root: str | None = None) -> list[str]:
    """Census over every shipped order template."""
    violations = []
    orders_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "rubric", "orders")
    if root is not None:
        orders_dir = os.path.join(root, "rubric", "orders")
    orders_dir = os.path.normpath(orders_dir)
    for name in sorted(os.listdir(orders_dir)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(orders_dir, name)
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        template_id = name[:-3]
        violations.extend(scan_template_shell_violations(body, template_id))
    return violations
