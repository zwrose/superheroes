#!/usr/bin/env python3
"""Render per-seat dispatch orders from shipped templates (#723).

Two public entry points, both returning ``(value, reason_or_None)`` and **never raising**:

  * ``render_order(phase, seat_key, context)`` — pure over its inputs; returns the complete order
    text for one seat.
  * ``resolve_base_residuals(repo_root, base_oid, core_rel_path)`` — reads ratified residuals from
    the pinned base commit via ``git cat-file``; never reads the worktree.

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
  * ``payload`` — the phase payload dict from the driver
  * ``host_seat`` — bool; host seats write payload-only, engine seats write the full envelope

Phase-specific keys are supplied via ``context["placeholders"]`` — a dict mapping placeholder
names (without braces) to string values the template references. The renderer also injects
derived placeholders (panel channel block, optional context lines) before substitution.

``seat_key`` is passed separately; templates do not substitute it unless the driver places it in
``context["placeholders"]``."""
from __future__ import annotations

import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import core_md  # noqa: E402
import mode_registry  # noqa: E402
import round_adapters  # noqa: E402
import round_phases  # noqa: E402

_PLACEHOLDER_RE = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")

ORDER_PHASES = (
    round_phases.P_PANEL,
    round_phases.P_VERIFIERS,
    round_phases.P_SYNTHESIS,
    round_phases.P_GAPSWEEP,
    round_phases.P_AUDITS,
    round_phases.P_FIXER,
    round_phases.P_SCOPED,
)

# Placeholder inputs consumed by derivation but not substituted into the template body.
_AUX_PLACEHOLDER_INPUTS = frozenset({"CHANNEL", "FOCUS_NOTES", "FINDINGS_OUTPUT_PATH"})

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


def order_template_path(phase: str, root: str | None = None) -> str:
    """Absolute path to ``rubric/orders/<phase>.md``."""
    if root is None:
        base = os.path.dirname(os.path.abspath(__file__))
        return os.path.normpath(os.path.join(base, "..", "rubric", "orders", phase + ".md"))
    return os.path.normpath(os.path.join(root, "rubric", "orders", phase + ".md"))


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


def _format_payload_contract(phase: str) -> tuple[str | None, str | None]:
    contract, reason = round_adapters.payload_contract(phase)
    if reason:
        return None, "payload-contract:%s" % reason
    lines = [
        "## Payload contract",
        "",
        "Your result must carry a payload matching this shape:",
        "",
    ]
    required = contract.get("required") or []
    lines.append("Required keys: %s" % (", ".join(required) if required else "(none)"))
    optional = contract.get("optional") or []
    if optional:
        lines.append("Optional keys: %s" % ", ".join(optional))
    enums = contract.get("enums") or {}
    for field in sorted(enums):
        values = enums[field]
        lines.append("%s enum: %s" % (field, " | ".join(values)))
    conditional = contract.get("conditional") or {}
    for field in sorted(conditional):
        lines.append("Conditional — %s: %s" % (field, conditional[field]))
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


def _format_landing_block(context: dict) -> tuple[str | None, str | None]:
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
        lines.extend([
            "Copy the envelope stub below verbatim, add the payload described in the Payload "
            "contract section above, and write the complete envelope to the landing path.",
            "",
            "- Envelope stub: %s" % stub,
            "- Landing path: %s" % landing,
        ])
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


def _panel_derived_placeholders(context: dict) -> dict[str, str]:
    ph = dict(context.get("placeholders") or {})
    channel = ph.get("CHANNEL", "file")
    if channel == "stdout":
        ph["OUTPUT_CHANNEL_BLOCK"] = (
            'Emit `{"findings": [...], "investigated": [...]}` as your final stdout with nothing '
            "after it; do not write a findings file (read-only sandbox — nothing reads one)."
        )
    else:
        ph["OUTPUT_CHANNEL_BLOCK"] = (
            "Write the JSON array to %s — write `[]` rather than skipping the file when you have "
            "nothing to flag." % ph.get("FINDINGS_OUTPUT_PATH", "{{FINDINGS_OUTPUT_PATH}}")
        )
    pr_checkout = ph.get("PR_CHECKOUT_PATH", "").strip()
    ph["PR_CHECKOUT_CONTEXT_LINE"] = (
        "- PR branch checkout: %s" % pr_checkout if pr_checkout else ""
    )
    prior = ph.get("PRIOR_COMMENTS_PATH", "").strip()
    ph["PRIOR_COMMENTS_CONTEXT_LINE"] = (
        "- Prior comments + author justifications: %s" % prior if prior else ""
    )
    focus = ph.get("FOCUS_NOTES", "").strip()
    ph["FOCUS_CONTEXT_LINE"] = (
        "- Focus: %s" % focus if focus else ""
    )
    return ph


def _derived_placeholders(phase: str, context: dict) -> dict[str, str]:
    ph = dict(context.get("placeholders") or {})
    if phase == round_phases.P_PANEL:
        ph = _panel_derived_placeholders(context)
    return ph


def render_order(phase: str, seat_key: str, context: dict) -> tuple[str | None, str | None]:
    """Return ``(order_text, None)`` or ``(None, reason)``. Never raises."""
    try:
        fault = _validate_common_context(context)
        if fault:
            return _refuse(fault)
        if phase not in ORDER_PHASES:
            return _refuse("no-template:%s" % phase)

        template, reason = _read_template(phase)
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

        contract_block, creason = _format_payload_contract(phase)
        if creason:
            return _refuse(creason)
        landing_block, lreason = _format_landing_block(context)
        if lreason:
            return _refuse(lreason)
        residual_block = _format_residual_block(context)

        order = "\n\n".join([body.rstrip(), residual_block.rstrip(),
                             contract_block.rstrip(), landing_block.rstrip()]) + "\n"

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
            core_rel = ".claude/superheroes/core.md"
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
