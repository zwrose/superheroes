#!/usr/bin/env python3
"""Shared phase-name constants for the round driver and its record/adapter layers (#723).

Single home for the `P_*` action strings so `round_driver`, `round_adapters`, and
`round_records` agree without import cycles. Stdlib-only."""
# Phases (the `action` a `next` emits; each is fulfilled by exactly one orchestrator dispatch).
P_PANEL = "dispatch-panel"
P_VERIFIERS = "dispatch-verifiers"
P_SYNTHESIS = "dispatch-synthesis"
P_AUDITS = "dispatch-audits"
P_SCOPED = "dispatch-scoped-finder"
P_GAPSWEEP = "dispatch-gap-sweep"
P_VERIFY = "run-verify"
P_FIXER = "dispatch-fixer"
P_JUDGMENT = "present-judgment"
P_STALL = "present-stall-menu"
P_TERMINAL = "terminal"

ALL_PHASES = (
    P_PANEL, P_VERIFIERS, P_SYNTHESIS, P_AUDITS, P_SCOPED, P_GAPSWEEP, P_VERIFY, P_FIXER,
    P_JUDGMENT, P_STALL, P_TERMINAL,
)
