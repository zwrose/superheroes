#!/usr/bin/env python3
# plugins/superheroes/lib/guardian_lens.py
"""The Guardian lens contract — protocol enforcement + production registry (empty here).

Stdlib-only. A lens is any object providing the five contract parts; real lenses register
in future issues. This order ships validate_lens + an empty REGISTRY.
"""
import os
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

LENS_CONTRACT_PARTS = (
    "collector", "baseline-diff", "validation", "consequence", "cost",
)
FINDING_STATES = (
    "candidate", "surfaced", "triaged-out", "filed", "accepted", "declined",
    "verified-fixed", "reopened",
)
RED_LINE_THRESHOLDS = {"complexity": 100, "cloneLines": 100}
RED_LINE_KINDS = ("critical-vuln", "new-high-complexity", "large-fresh-clone")
FACTS = ("verify-command", "recorded-coverage", "stack-tags", "paths")

"""A lens is any object providing:
  - name: str, collector_version: str
  - cost: dict — declared collection cost, e.g. {"collectorSeconds": float, "note": str}
  - required_facts: tuple — subset of FACTS this lens depends on
  - validation_guidance: str — non-empty text for model validation
  - consequence_template: str — non-empty text guiding plain-sentence consequences
  - collect(ctx) -> {"candidates": [{"id": str, ...}], "digest": <json>}
  - diff(prev_digest, cur_digest) -> {"new": [ids], "worsened": [ids], "resolved": [ids]}
  - red_lines(candidates) -> [{"kind": <RED_LINE_KINDS>, "id": str, "detail": str}]
  - degrade(reason) -> {"lens": name, "degraded": True, "reason": reason}
"""

REGISTRY = []


def validate_lens(lens):
    """Fail-closed check that lens implements LENS_CONTRACT_PARTS. Returns (ok, reasons)."""
    reasons = []
    if not isinstance(getattr(lens, "name", None), str) or not lens.name:
        reasons.append("name must be a non-empty str")
    if not isinstance(getattr(lens, "collector_version", None), str) or not lens.collector_version:
        reasons.append("collector_version must be a non-empty str")
    cost = getattr(lens, "cost", None)
    if not isinstance(cost, dict):
        reasons.append("cost must be a dict")
    rf = getattr(lens, "required_facts", None)
    if not isinstance(rf, tuple):
        reasons.append("required_facts must be a tuple")
    elif any(f not in FACTS for f in rf):
        reasons.append("required_facts must be a tuple of FACTS members")
    for attr in ("validation_guidance", "consequence_template"):
        val = getattr(lens, attr, None)
        if not isinstance(val, str) or not val:
            reasons.append("%s must be a non-empty str" % attr)
    for meth in ("collect", "diff", "red_lines", "degrade"):
        if not callable(getattr(lens, meth, None)):
            reasons.append("%s must be callable" % meth)
    return (len(reasons) == 0, reasons)


def register(lens):
    """Validate and append to REGISTRY. Raises ValueError on invalid lens."""
    ok, reasons = validate_lens(lens)
    if not ok:
        raise ValueError("; ".join(reasons))
    REGISTRY.append(lens)


def registered_lenses():
    return list(REGISTRY)
