#!/usr/bin/env python3
# plugins/superheroes/lib/guardian_lens.py
"""The Guardian lens contract — protocol enforcement + production lens registry.

Stdlib-only. A lens is any object providing the five contract parts. Production lenses
are named in PRODUCTION_LENS_MODULES and loaded (fail-closed) by load_production_lenses().

Optional conformance hook (production lenses MUST implement; not checked by validate_lens):

  conformance_cases() -> {"reported-nonzero-parsed-zero": {
      "stdout": <raw tool output that reports findings but parses to zero>,
      "clean_stdout": <raw tool output with genuinely zero findings>,
      "exit": <exit code on a findings run (may be non-zero)>,
      "clean_exit": <optional exit code on a genuinely-clean run; defaults to "exit">,
      "config": <dict | None>,
      "prev_digest": <json | None>,
  }}

The harness owns the five tool-agnostic scenarios (``missing-tool``, ``timeout``,
``nonzero-exit``, ``findings-empty-output``, ``unparseable``) and injects its own
``ctx["run"]`` stubs. For ``reported-nonzero-parsed-zero`` the lens supplies stdout,
clean_stdout, and exit; the harness runs a clean probe (at ``clean_exit`` when the case
declares one, else ``exit``) and a findings probe (at ``exit``). The optional
``clean_exit`` models dual-success-exit tools such as ``npm audit`` (0 = clean, 1 =
findings): declare ``exit=1, clean_exit=0``. Omitting ``clean_exit`` is byte-for-byte the
prior single-exit behavior.

Tool-free lenses (stdlib-only collectors — no external tool, no indirect spawn) opt in by
setting the class attribute ``uses_external_tools = False``. Such a lens supplies
TOOL_FREE_CONFORMANCE_SCENARIOS via conformance_cases() instead of the tool-injection
scenarios (see the tool-free case shape below); the harness skips the five tool-injection
scenarios and the ``reported-nonzero-parsed-zero`` two-probe (all assume a ``ctx["run"]``
call) and instead drives the tool-free honesty invariants AND proves — at runtime, not by
trust — that collect() spawns nothing.

The per-lens conformance harness (test_guardian_conformance) drives every scenario,
classifies each collect() outcome, and fails registration when coverage or an honesty
invariant is missing.
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
PERMANENT_BOUNDARY_KEY = "permanentBoundary"

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

LENS_SUPPLIED_CONFORMANCE_SCENARIOS = (
    "reported-nonzero-parsed-zero",
)
"""Lens-supplied conformance scenarios; the harness owns every other member of
REQUIRED_CONFORMANCE_SCENARIOS.
"""

CONFORMANCE_CASE_FIELDS = ("stdout", "clean_stdout", "exit")
"""Authoritative REQUIRED field schema for a lens-supplied ``conformance_cases()`` entry.

Every ``reported-nonzero-parsed-zero`` case MUST carry all three. Optional keys live in
CONFORMANCE_CASE_OPTIONAL_FIELDS below.
"""

CONFORMANCE_CASE_OPTIONAL_FIELDS = (
    "clean_exit", "config", "prev_digest", "stdout_by_tool", "clean_stdout_by_tool")
"""Optional keys a ``reported-nonzero-parsed-zero`` case MAY carry.

- ``clean_exit`` — the exit code the tool returns on a genuinely-clean run when it differs
  from the findings exit (dual-success-exit tools like ``npm audit``: ``exit=1,
  clean_exit=0``). Defaults to ``exit`` when absent.
- ``config`` / ``prev_digest`` — forwarded to ``collect()`` (as ``ctx["config"]`` and
  ``ctx["prevDigest"]``).
- ``stdout_by_tool`` / ``clean_stdout_by_tool`` — per-``argv[0]`` stdout maps for a
  MULTI-COLLECTOR lens. The harness dispatches the findings payload to ONLY the targeted
  collector (``stdout_by_tool``) and hands every co-firing collector a clean payload
  (``clean_stdout_by_tool``, else ``clean_stdout``), so the targeted honesty gate is the
  only thing that can degrade the findings probe — a single shared stdout would degrade the
  whole lens through a co-firing tool regardless of the gate, letting a deleted gate still
  pass. Additive: a case with no ``stdout_by_tool`` keeps the single-stdout behavior.

None of these is required; the required set stays CONFORMANCE_CASE_FIELDS.
"""

TOOL_FREE_CONFORMANCE_SCENARIOS = (
    "unreadable-input",
    "all-inputs-unavailable",
    "partial-carry-forward",
)
"""Honesty scenarios a tool-free lens (``uses_external_tools = False``) supplies via
conformance_cases() in place of the tool-injection scenarios.

Each maps to a tool-free case: ``{"fixture": {relpath: content}, "unreadable": [relpath,
...], "prev_digest": <json>, "config": <dict | None>}``. The harness builds a fresh temp
workspace per scenario, writes ``fixture``, makes any ``unreadable`` paths unreadable, runs
collect() with cwd == root == that workspace and NO injected ``ctx["run"]``, and asserts:

- ``unreadable-input`` — an unreadable input must degrade (``partial`` / ``not-collected``
  with a reason) OR carry the prior digest forward; it must NEVER read as a false clean
  (i.e. never resolve prior findings it did not re-measure).
- ``all-inputs-unavailable`` — nothing to measure must degrade with a non-empty reason.
- ``partial-carry-forward`` — a ``partial`` result must preserve the prior digest
  (``diff()`` must not spuriously resolve prior ids).

Across every tool-free scenario, when measurement stopped ``diff()`` must emit no
``resolved`` ids. The harness additionally proves — by monkeypatching the spawn primitives
to raise and running collect() — that a tool-free lens invokes neither
``guardian_collect.run_tool`` nor any indirect spawn helper.
"""

"""A lens is any object providing:
  - name: str, collector_version: str
  - cost: dict — declared collection cost, e.g. {"collectorSeconds": float, "note": str}
  - required_facts: tuple — subset of FACTS this lens depends on
  - validation_guidance: str — non-empty text for model validation
  - consequence_template: str — non-empty text guiding plain-sentence consequences
  - collect(ctx) -> {"candidates": [{"id": str, ...}], "digest": <json>,
                     "status": <COLLECT_STATUSES member, default "collected">,
                     "reason": str | None,
                     "permanentBoundary": bool | omitted}
      When status is "partial", permanentBoundary may be set to True to declare that
      the un-measured remainder is a structural capability limit (see permanent_boundary()).
  - permanent_boundary(out) -> bool — fail-closed: True only when out is a dict with
      status "partial", permanentBoundary is exactly the boolean True, and reason is a
      non-empty string (a contract-valid partial).
      ctx carries {"cwd", "root", "config", "run", "prevDigest", "verifyCommand"}. A lens
      that could not collect returns status "not-collected" (never an empty candidate
      list). ``verifyCommand`` is the calibrated core.md verify command already resolved by
      the sweep (``guardian_sweep.collect`` reads it once alongside the verify-command
      FACT) so a tool-free lens can resolve the paths it names without a second core.md read
      or a git spawn; it is None when no calibration was resolved, and lenses that do not
      need it ignore it.
  - diff(prev_digest, cur_digest) -> {"new": [ids], "worsened": [ids], "resolved": [ids]}
  - red_lines(candidates) -> [{"kind": <RED_LINE_KINDS>, "id": str, "detail": str}]
  - degrade(reason) -> {"lens": name, "degraded": True, "reason": reason}
  - conformance_cases() -> dict (optional on the protocol; REQUIRED for production lenses)
      Maps each REQUIRED_CONFORMANCE_SCENARIOS name to a harness case (see module docstring).
  - uses_external_tools: bool (optional class attribute, defaults True) — set False for a
      stdlib-only lens that spawns nothing; the harness then drives the tool-free scenarios
      (TOOL_FREE_CONFORMANCE_SCENARIOS) and proves no spawn happens (see module docstring).
"""

REGISTRY = []

PRODUCTION_LENS_MODULES = (
    "guardian_lens_duplication", "guardian_lens_hotspots", "guardian_lens_deps",
    "guardian_lens_deadcode", "guardian_lens_docs", "guardian_lens_coupling")
"""Authoritative runtime roster of production lens module names (under lib/).

Rebasing lens PRs populate this tuple; each module MUST expose a module-level LENSES
tuple of ready-to-register lens objects.
"""

PRODUCTION_LENS_NAMES = {
    "guardian_lens_duplication": ("duplication",),
    "guardian_lens_hotspots": ("hotspots",),
    "guardian_lens_deps": ("deps",),
    "guardian_lens_deadcode": ("deadcode",),
    "guardian_lens_docs": ("docs",),
    "guardian_lens_coupling": ("coupling",),
}
"""Map module-name → tuple of lens names the module is expected to export.

Used to synthesize correctly-named stand-ins when a module fails to load and to
fail-closed when an imported module's LENSES omits an expected name.
"""

_PRODUCTION_LOADED = False
_PRODUCTION_LOAD_ERRORS = []
_PRODUCTION_COLLIDED_NAMES = set()
_PRODUCTION_REGISTERED = []
_PRODUCTION_MODULE_LENSES = {}


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


def permanent_boundary(out):
    """True only for a contract-valid partial that declares a permanent capability boundary.

    Requires status exactly ``partial``, ``permanentBoundary`` exactly the boolean ``True``,
    and a non-empty string ``reason`` on the raw collect() object — a partial with no
    reason is synthesized as a contract violation by ``classify_collect`` and must not seed
    a baseline.
    """
    if not isinstance(out, dict):
        return False
    if out.get("status") != "partial":
        return False
    if out.get(PERMANENT_BOUNDARY_KEY) is not True:
        return False
    reason = out.get("reason")
    return isinstance(reason, str) and bool(reason)


def validate_lens(lens):
    """Fail-closed check that lens implements LENS_CONTRACT_PARTS. Returns (ok, reasons)."""
    reasons = []
    if not isinstance(getattr(lens, "name", None), str) or not lens.name:
        reasons.append("name must be a non-empty str")
    elif lens.name.startswith("module:"):
        reasons.append(
            "name must not use the reserved 'module:' prefix "
            "(reserved for load-failure stand-ins)")
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
    _PRODUCTION_COLLIDED_NAMES.clear()
    _PRODUCTION_MODULE_LENSES.clear()
    if force:
        loader_ids = {id(lens) for lens in _PRODUCTION_REGISTERED}
        REGISTRY[:] = [lens for lens in REGISTRY if id(lens) not in loader_ids]
        _PRODUCTION_REGISTERED.clear()
    known = {getattr(lens, "name", None) for lens in REGISTRY}
    for module_name in PRODUCTION_LENS_MODULES:
        expected = PRODUCTION_LENS_NAMES.get(module_name, ())
        if not expected:
            _record_production_error({
                "module": module_name,
                "error": (
                    "module has no PRODUCTION_LENS_NAMES mapping — roster misconfiguration"),
            })
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
                _PRODUCTION_COLLIDED_NAMES.add(name)
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
                if name and "duplicate lens name" in str(exc):
                    _PRODUCTION_COLLIDED_NAMES.add(name)
                _record_production_error({
                    "module": module_name,
                    "lens": name,
                    "error": str(exc),
                })
                continue
            known.add(name)
            _PRODUCTION_REGISTERED.append(lens)
            _PRODUCTION_MODULE_LENSES.setdefault(module_name, set()).add(name)
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
    if "lens" in entry:
        named = entry.get("lens")
        if isinstance(named, str) and named:
            return (named,)
        return ()
    return PRODUCTION_LENS_NAMES.get(entry.get("module"), ())


def registered_lenses():
    load_production_lenses()
    lenses = list(REGISTRY)
    present = {getattr(lens, "name", None) for lens in lenses}

    if _PRODUCTION_COLLIDED_NAMES:
        lenses = [l for l in lenses if l.name not in _PRODUCTION_COLLIDED_NAMES]
        present = {getattr(lens, "name", None) for lens in lenses}
        for name in sorted(_PRODUCTION_COLLIDED_NAMES):
            dup_error = "duplicate lens name"
            for err in _PRODUCTION_LOAD_ERRORS:
                if err.get("lens") == name and "duplicate lens name" in err.get("error", ""):
                    dup_error = err.get("error") or dup_error
                    break
            lenses.append(_UnavailableLens(name, dup_error))
            present.add(name)

    module_fallback = {}
    for err in _PRODUCTION_LOAD_ERRORS:
        if err.get("lens") in _PRODUCTION_COLLIDED_NAMES:
            continue
        names = _stub_names_for_error(err)
        added_any = False
        for name in names:
            if name in present:
                continue
            lenses.append(_UnavailableLens(name, err.get("error") or "unknown"))
            present.add(name)
            added_any = True
        if not added_any:
            module = err.get("module")
            key = module if module else "<unknown>"
            module_fallback.setdefault(key, []).append(err.get("error") or "unknown")
    for module, reasons in module_fallback.items():
        standin_name = "module:%s" % module
        if standin_name not in present:
            lenses.append(_UnavailableLens(standin_name, "; ".join(reasons)))
            present.add(standin_name)
    return lenses
