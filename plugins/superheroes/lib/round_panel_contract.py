#!/usr/bin/env python3
"""Scoped-finder phase token and default panel roster — driverless contract leaf (#1272).

Imported by ``round_phases`` (driver) and ``round_certification`` (writer) so neither
crosses the register R5 import fence. Stdlib-only."""
from __future__ import annotations

P_SCOPED_FINDER_PHASE = "dispatch-scoped-finder"

# The code leg is the FIVE shared reviewers. `grounding-reviewer` is spec-leg-only — absent here.
DEFAULT_PANEL_DIMENSIONS = (
    "architecture-reviewer",
    "code-reviewer",
    "security-reviewer",
    "test-reviewer",
    "premortem-reviewer",
)


def panel_dimensions_from_config(config):
    """Configured panel dimensions, or the default roster."""
    dims = config.get("dimensions") if isinstance(config, dict) else None
    if isinstance(dims, (list, tuple)):
        strings = [d for d in dims if isinstance(d, str)]
        return strings if strings else list(DEFAULT_PANEL_DIMENSIONS)
    return list(DEFAULT_PANEL_DIMENSIONS)
