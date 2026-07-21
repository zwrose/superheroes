#!/usr/bin/env python3
# plugins/superheroes/lib/guardian_lens.py
"""The Guardian lens contract — protocol enforcement + production lens registry.

Stdlib-only. A lens is any object providing the five contract parts. Production lenses
are named in PRODUCTION_LENS_MODULES and loaded (fail-closed) by load_production_lenses().

Optional conformance hook (production lenses MUST implement; not checked by validate_lens):

  conformance_cases() -> {scenario_name: {
      "run": <callable — ctx["run"] stand-in>,
      "config": <dict | None>,
      "prev_digest": <json | None>,
  }}

For each name in REQUIRED_CONFORMANCE_SCENARIOS, the lens supplies a case whose ``run``
stub simulates that tool outcome. The per-lens conformance harness (test_guardian_conformance)
drives each case, classifies the collect() outcome, and fails registration when coverage or
an honesty invariant is missing.
"""
import importlib
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
COLLECT_STATUSES = ("collected", "partial", "not-collected")

REQUIRED_CONFORMANCE_SCENARIOS = (
    "missing-tool",
    "timeout",
    "nonzero-exit",
    "findings-empty-output",
    "unparseable",
    "reported-nonzero-parsed-zero",
)
"""Tool-honesty scenarios every production lens must cover via conformance_cases().

The conformance harness fails registration for any registered lens that omits one.
"""

"""A lens is any object providing:
  - name: str, collector_version: str
  - cost: dict — declared collection cost, e.g. {"collectorSeconds": float, "note": str}
  - required_facts: tuple — subset of FACTS this lens depends on
  - validation_guidance: str — non-empty text for model validation
  - consequence_template: str — non-empty text guiding plain-sentence consequences
  - collect(ctx) -> {"candidates": [{"id": str, ...}], "digest": <json>,
                     "status": <COLLECT_STATUSES member, default "collected">,
                     "reason": str | None}
      ctx carries {"cwd", "root", "config", "run", "prevDigest"}. A lens that could not
      collect returns status "not-collected" (never an empty candidate list).
  - diff(prev_digest, cur_digest) -> {"new": [ids], "worsened": [ids], "resolved": [ids]}
  - red_lines(candidates) -> [{"kind": <RED_LINE_KINDS>, "id": str, "detail": str}]
  - degrade(reason) -> {"lens": name, "degraded": True, "reason": reason}
  - conformance_cases() -> dict (optional on the protocol; REQUIRED for production lenses)
      Maps each REQUIRED_CONFORMANCE_SCENARIOS name to a harness case (see module docstring).
"""

REGISTRY = []

PRODUCTION_LENS_MODULES = ()
"""Authoritative runtime roster of production lens module names (under lib/).

Rebasing lens PRs populate this tuple; each module MUST expose a module-level LENSES
tuple of ready-to-register lens objects.
"""

PRODUCTION_LENS_NAMES = {}
"""Map module-name → tuple of lens names the module is expected to export (empty on main).

Used to synthesize correctly-named stand-ins when a module fails to load and to
fail-closed when an imported module's LENSES omits an expected name.
"""

_PRODUCTION_LOADED = False
_PRODUCTION_LOAD_ERRORS = []


class MalformedCollect(ValueError):
    """A collect() outcome that is structurally unusable."""


def classify_collect(out):
    """Return (status, reason) for a collect() outcome. Fail-closed."""
    if not isinstance(out, dict):
        raise MalformedCollect(
            "collect() must return a dict, got %s" % type(out).__name__)
    status = out.get("status", "collected")
    reason = out.get("reason")
    if status not in COLLECT_STATUSES:
        return ("not-collected", "invalid collect status: %r" % (status,))
    if status in ("partial", "not-collected"):
        if not isinstance(reason, str) or not reason:
            return (status, "%s reported without a reason (contract violation)" % status)
        return (status, reason)
    if status == "collected":
        if "candidates" not in out or not isinstance(out.get("candidates"), list):
            raise MalformedCollect(
                "collected outcome requires a list 'candidates', got %r"
                % (out.get("candidates"),))
        if "digest" not in out:
            raise MalformedCollect("collected outcome requires a 'digest' key")
    return ("collected", None)


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
    """Validate and append to REGISTRY. Raises ValueError on invalid or duplicate lens."""
    ok, reasons = validate_lens(lens)
    if not ok:
        raise ValueError("; ".join(reasons))
    if any(existing.name == lens.name for existing in REGISTRY):
        raise ValueError(
            "duplicate lens name %r already registered — lens names are the sweep's "
            "per-lens baseline key and must be unique" % lens.name)
    REGISTRY.append(lens)


def _record_production_error(entry):
    _PRODUCTION_LOAD_ERRORS.append(entry)
    sys.stderr.write("guardian_lens: production lens load failed: %r\n" % (entry,))


def load_production_lenses(force=False):
    """Import + register every PRODUCTION_LENS_MODULES entry. Idempotent.

    A broken lens degrades visibly by name — never silently omitted, never fatal to the
    sweep. Returns list(REGISTRY).
    """
    global _PRODUCTION_LOADED
    if _PRODUCTION_LOADED and not force:
        return list(REGISTRY)
    del _PRODUCTION_LOAD_ERRORS[:]
    known = {getattr(lens, "name", None) for lens in REGISTRY}
    for module_name in PRODUCTION_LENS_MODULES:
        try:
            module = importlib.import_module(module_name)
            lenses = tuple(getattr(module, "LENSES", ()) or ())
        except Exception as exc:  # noqa: BLE001 — a broken module must not kill the sweep
            _record_production_error({
                "module": module_name,
                "error": "%s: %s" % (type(exc).__name__, exc),
            })
            continue
        if not lenses:
            _record_production_error({
                "module": module_name,
                "error": "exposes no module-level LENSES",
            })
            continue
        exported_names = tuple(
            getattr(lens, "name", None) for lens in lenses
            if isinstance(getattr(lens, "name", None), str) and lens.name)
        expected = PRODUCTION_LENS_NAMES.get(module_name, ())
        for want in expected:
            if want not in exported_names:
                _record_production_error({
                    "module": module_name,
                    "lens": want,
                    "error": "expected lens %r missing from LENSES export" % want,
                })
        for lens in lenses:
            name = getattr(lens, "name", None)
            if name in known:
                _record_production_error({
                    "module": module_name,
                    "lens": name,
                    "error": (
                        "duplicate lens name %r already registered — lens names are the "
                        "sweep's per-lens baseline key and must be unique" % name),
                })
                continue
            try:
                register(lens)
            except ValueError as exc:
                _record_production_error({
                    "module": module_name,
                    "lens": name,
                    "error": str(exc),
                })
                continue
            known.add(name)
    _PRODUCTION_LOADED = True
    return list(REGISTRY)


def production_lens_load_errors():
    """Visible record of production-lens load/registration failures from the last load."""
    return list(_PRODUCTION_LOAD_ERRORS)


class _UnavailableLens(object):
    """Stand-in for a production lens that failed to load/register."""

    def __init__(self, name, error):
        self.name = name
        self.collector_version = "0"
        self.cost = {
            "collectorSeconds": 0.0,
            "note": "production lens unavailable — load/registration failed",
        }
        self.required_facts = ()
        self.validation_guidance = (
            "This production lens failed to load; there is nothing to validate.")
        self.consequence_template = (
            "Production lens %s is unavailable." % name)
        self._error = error

    def collect(self, ctx):
        return {
            "candidates": [],
            "digest": None,
            "status": "not-collected",
            "reason": "%s: production lens unavailable — %s" % (self.name, self._error),
        }

    def diff(self, prev_digest, cur_digest):
        return {"new": [], "worsened": [], "resolved": []}

    def red_lines(self, candidates):
        return []

    def degrade(self, reason):
        return {"lens": self.name, "degraded": True, "reason": reason}


def _stub_names_for_error(entry):
    """Lens names that must appear as degraded stand-ins for a load error."""
    named = entry.get("lens")
    if isinstance(named, str) and named:
        return (named,)
    return PRODUCTION_LENS_NAMES.get(entry.get("module"), ())


def registered_lenses():
    load_production_lenses()
    lenses = list(REGISTRY)
    present = {getattr(lens, "name", None) for lens in lenses}
    for err in _PRODUCTION_LOAD_ERRORS:
        for name in _stub_names_for_error(err):
            if name in present:
                continue
            lenses.append(_UnavailableLens(name, err.get("error") or "unknown"))
            present.add(name)
    return lenses
