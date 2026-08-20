#!/usr/bin/env python3
"""Load model-tier overrides from the review-crew profile.

Reads the optional `## Model tiers` block out of the resolved review-crew profile and
emits a {role: model} JSON map for `model_tier_resolve.py`'s --overrides seam. The block
is plain `role: model` lines under a `## Model tiers` heading, e.g.:

    ## Model tiers
    reviewer-deep: opus
    mechanical: sonnet

Fail-OPEN: a missing profile, missing block, malformed line, or unknown role yields {}
(or drops the bad key) — the knob then uses its band defaults. A wrong/absent override is
a cost concern, never a safety one. stdlib only.
"""
import collections
import json
import os
import re
import stat
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import model_registry  # noqa: E402

# The OWNER-CONFIGURABLE model-tier role set — re-derived from the registry minus
# `orchestrator`. `orchestrator` is deliberately excluded: it has no config key (the
# session model is not owner-configurable, so it must never be silently overridable via
# this block). A role not in this set is an owner typo and is dropped (fail-open to the
# default).
KNOWN_ROLES = model_registry.known_roles()
KNOWN_MODELS = model_registry.known_claude_models()

_LEGACY_ROLE_ALIAS = {"fixer": "code-fixer"}

TIERS_OK = "ok"
TIERS_ABSENT = "absent"
TIERS_UNREADABLE = "unreadable"
TIERS_ROOT_UNAVAILABLE = "root-unavailable"
TIER_REASON_UNREADABLE = "model-tiers-unreadable"
TIER_REASON_ROOT_UNAVAILABLE = "calibration-root-unavailable"
TIER_REASON_EVALUATION_FAILED = "model-tiers-evaluation-failed"

TierGate = collections.namedtuple("TierGate", "tiers overrides status detail path")

_TIER_GATE_USABLE_STATUSES = frozenset({TIERS_OK, TIERS_ABSENT})
_TIER_GATE_REFUSAL_REASONS = {
    TIERS_UNREADABLE: TIER_REASON_UNREADABLE,
    TIERS_ROOT_UNAVAILABLE: TIER_REASON_ROOT_UNAVAILABLE,
}

_GATE_REASON_EVALUATION_FAILED_FALLBACK = "dispatch-gate-evaluation-failed"


def _gate_refusal_fallback(reason, detail):
    """The {"reason", "detail"} gate-refusal payload, built WITHOUT importing ``core_md``.

    ``core_md.gate_refusal`` is the single home for this shape (rider 9 of #699) and every path that
    can rely on ``core_md`` being importable uses it. These paths cannot: they are the handlers that
    exist to report that ``core_md`` itself could not be imported or evaluated, so reaching for
    ``core_md.gate_refusal`` here would raise the very failure they are reporting (it did — see
    test_gate_refusal_fallback_matches_core_md_shape; if you change one, that test fails."""
    return {"reason": reason, "detail": detail}


def _gate_refusal_detail_fallback(exc):
    """Exception detail string for import-hostile gate paths — mirrors ``core_md.gate_refusal_detail``.

    The runtime path cannot import ``core_md``; test_gate_refusal_fallback_matches_core_md_shape
    guards drift against ``core_md.gate_refusal_detail``."""
    return "%s: %s" % (type(exc).__name__, exc)


_HEADING = re.compile(r"^\s*##\s+[Mm]odel tiers\s*$")
_NEXT_HEADING = re.compile(r"^\s*##\s+")
_ENTRY = re.compile(r"^\s*([A-Za-z][A-Za-z-]*)\s*:\s*(\S+)\s*$")


def load_overrides(profile_path):
    """Return {role: model} from the profile's `## Model tiers` block, or {}. Never raises."""
    if not profile_path:
        return {}
    try:
        with open(profile_path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return {}
    out = {}
    in_block = False
    for line in text.splitlines():
        if _HEADING.match(line):
            in_block = True
            continue
        if in_block and _NEXT_HEADING.match(line):
            break
        if in_block:
            m = _ENTRY.match(line)
            if m:
                role = _LEGACY_ROLE_ALIAS.get(m.group(1), m.group(1))
                if role in KNOWN_ROLES:
                    out[role] = m.group(2)
    return out


def _read_text(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def _write_text(path, text):
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, f".{os.path.basename(path)}.tmp.{os.getpid()}")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def effective_tiers(profile_path):
    """Return DEFAULT_TIERS merged with the profile override block, keyed by public role name."""
    import model_tier
    overrides = load_overrides(profile_path)
    return {role: model_tier.resolve_model(role, overrides) for role in KNOWN_ROLES}


def _normalize_updates(updates):
    out = {}
    warnings = []
    for role, model in (updates or {}).items():
        if role in _LEGACY_ROLE_ALIAS:
            warnings.append(
                f"'{role}' is a legacy alias for '{_LEGACY_ROLE_ALIAS[role]}' (remapped)"
            )
            role = _LEGACY_ROLE_ALIAS[role]
        if role not in KNOWN_ROLES:
            warnings.append(f"unknown role: {role} (dropped)")
            continue
        if model is None:
            continue
        if not isinstance(model, str) or not model.strip():
            warnings.append(f"empty model for {role} (cleared)")
            continue
        model = model.strip()
        if model not in KNOWN_MODELS:
            warnings.append(f"unknown model for {role}: {model} (kept)")
        out[role] = model
    return out, warnings


def _render_block(overrides):
    lines = ["## Model tiers"]
    for role in KNOWN_ROLES:
        if role in overrides:
            lines.append(f"{role}: {overrides[role]}")
    return "\n".join(lines) + "\n"


def replace_model_tiers_block(text, overrides):
    """Create or replace only the `## Model tiers` block, preserving all other sections."""
    block = _render_block(overrides)
    lines = text.splitlines(keepends=True)
    start = None
    for i, line in enumerate(lines):
        if _HEADING.match(line):
            start = i
            break
    if start is None:
        if not text:
            return block
        sep = "" if text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
        return text + sep + block
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if _NEXT_HEADING.match(lines[j]):
            end = j
            break
    return "".join(lines[:start]) + block + "".join(lines[end:])


class _TierGateRefusal(Exception):
    def __init__(self, gate):
        self.gate = gate


def _candidate_effective_tiers(profile_path, set_overrides=None, clear_roles=None):
    import model_tier

    gate = overrides_for_gate(profile_path)
    if tier_gate_is_refusal(gate):
        raise _TierGateRefusal(gate)
    current = dict(gate.overrides)
    for role in clear_roles or []:
        role = _LEGACY_ROLE_ALIAS.get(role, role)
        if role in KNOWN_ROLES:
            current.pop(role, None)
    normalized, _warnings = _normalize_updates(set_overrides or {})
    current.update(normalized)
    return {role: model_tier.resolve_model(role, current) for role in KNOWN_ROLES}


def _read_engine_preferences_for_gate(profile_path=None, cwd=None, root=None):
    """Engine preferences for the gate. Returns ``(prefs, evaluation_error)``.

    ``prefs`` is ``{}`` on confirmed absence (no core.md). ``evaluation_error`` is a
    ``{"reason", "detail"}`` dict when configuration exists but cannot be evaluated."""
    try:
        import core_md

        cfg = core_md.engine_preferences_for_gate(
            profile_path=profile_path, cwd=cwd, root=root)
        refusal = core_md.gate_config_refusal(cfg)
        if refusal is not None:
            return {}, refusal
        return cfg.prefs, None
    except Exception as exc:
        return {}, _gate_refusal_fallback(
            _GATE_REASON_EVALUATION_FAILED_FALLBACK, _gate_refusal_detail_fallback(exc))


def _evaluate_tier_writer_dispatch_gate(profile_path, set_overrides=None, clear_roles=None):
    """Returns ``(violations, evaluation_error)`` — same posture as ``core_md``'s configured gate."""
    import engine_pref

    prefs, gate_err = _read_engine_preferences_for_gate(profile_path=profile_path)
    if gate_err is not None:
        return None, gate_err
    try:
        candidate_tiers = _candidate_effective_tiers(profile_path, set_overrides, clear_roles)
    except _TierGateRefusal as exc:
        return None, tier_gate_refusal(exc.gate)
    except Exception as exc:
        import core_md

        return None, _gate_refusal_fallback(
            _GATE_REASON_EVALUATION_FAILED_FALLBACK, core_md.gate_refusal_detail(exc))
    return engine_pref.configured_dispatch_violations(prefs, candidate_tiers), None


def update_overrides(profile_path, set_overrides=None, clear_roles=None):
    """Mutate the resolved profile's model-tier block and return the new effective state.

    Unknown roles are dropped. Unknown model strings are kept with a warning so newly available
    models, including owner-approved experiments, do not require a plugin release before use.
    """
    if not profile_path:
        raise ValueError("profile_path is required")
    current = load_overrides(profile_path)
    warnings = []
    for role in clear_roles or []:
        role = _LEGACY_ROLE_ALIAS.get(role, role)
        if role not in KNOWN_ROLES:
            warnings.append(f"unknown role: {role} (dropped)")
            continue
        current.pop(role, None)
    normalized, update_warnings = _normalize_updates(set_overrides)
    warnings.extend(update_warnings)
    current.update(normalized)
    text = _read_text(profile_path)
    _write_text(profile_path, replace_model_tiers_block(text, current))
    return {
        "ok": True,
        "path": profile_path,
        "overrides": load_overrides(profile_path),
        "effective": effective_tiers(profile_path),
        "warnings": warnings,
        "knownRoles": list(KNOWN_ROLES),
        "knownModels": list(KNOWN_MODELS),
    }


def _parse_overrides_from_text(text):
    out = {}
    in_block = False
    for line in text.splitlines():
        if _HEADING.match(line):
            in_block = True
            continue
        if in_block and _NEXT_HEADING.match(line):
            break
        if in_block:
            m = _ENTRY.match(line)
            if m:
                role = _LEGACY_ROLE_ALIAS.get(m.group(1), m.group(1))
                if role in KNOWN_ROLES:
                    out[role] = m.group(2)
    return out


def _classify_profile_path(path):
    """Classify a single profile path for gate purposes. Never raises."""
    import core_md

    try:
        st = os.stat(path)
    except FileNotFoundError:
        try:
            os.lstat(path)
        except FileNotFoundError:
            return TIERS_ABSENT, None
        except OSError as exc:
            return TIERS_UNREADABLE, "lstat failed at %s: %s" % (path, exc)
        return TIERS_UNREADABLE, "dangling symlink at %s" % path
    except OSError as exc:
        return TIERS_UNREADABLE, core_md.gate_refusal_detail(exc, at=path)

    if not stat.S_ISREG(st.st_mode):
        return TIERS_UNREADABLE, "not a regular file at %s" % path

    return TIERS_OK, None


def resolve_profile_path_for_gate(cwd=None, root=None):
    """Resolve the review-crew profile path for gate purposes. Never raises."""
    import calibration_resolve
    import core_md
    import store_core

    try:
        cwd = cwd or os.getcwd()
        # Side effect only: raises UnresolvableRootError when root is supplied but wrong.
        calibration_resolve.resolve(cwd, root=root)
        for path in calibration_resolve.candidate_profile_paths(cwd, root=root):
            status, detail = _classify_profile_path(path)
            if status == TIERS_ABSENT:
                continue
            if status == TIERS_UNREADABLE:
                return path, TIERS_UNREADABLE, detail
            return path, TIERS_OK, None
        return None, TIERS_ABSENT, None
    except calibration_resolve.UnresolvableRootError as exc:
        return None, TIERS_ROOT_UNAVAILABLE, core_md.gate_refusal_detail(exc)
    except store_core.RepoRootUnavailable as exc:
        return None, TIERS_ROOT_UNAVAILABLE, core_md.gate_refusal_detail(exc)
    except Exception as exc:
        return None, TIERS_UNREADABLE, core_md.gate_refusal_detail(exc)


def overrides_for_gate(profile_path):
    """Classify and parse overrides at ``profile_path``. Never raises."""
    import core_md

    if not profile_path:
        return TierGate(None, {}, TIERS_ABSENT, None, None)

    status, detail = _classify_profile_path(profile_path)
    if status != TIERS_OK:
        return TierGate(None, {}, status, detail, profile_path)

    try:
        with open(profile_path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        return TierGate(
            None,
            {},
            TIERS_UNREADABLE,
            core_md.gate_refusal_detail(exc, at=profile_path, verb="opening"),
            profile_path,
        )
    except UnicodeDecodeError as exc:
        return TierGate(
            None,
            {},
            TIERS_UNREADABLE,
            "UTF-8 decode failed at %s: %s" % (profile_path, exc),
            profile_path,
        )

    overrides = _parse_overrides_from_text(text)
    return TierGate(None, overrides, TIERS_OK, None, profile_path)


def effective_tiers_for_gate(cwd=None, root=None, profile_path=None):
    """Merged effective tiers with fail-closed refusal semantics. Never raises."""
    import model_tier

    if profile_path:
        gate = overrides_for_gate(profile_path)
        if tier_gate_is_refusal(gate):
            return TierGate(None, gate.overrides, gate.status, gate.detail, gate.path)
        tiers = {role: model_tier.resolve_model(role, gate.overrides) for role in KNOWN_ROLES}
        return TierGate(tiers, gate.overrides, gate.status, gate.detail, profile_path)

    path, status, detail = resolve_profile_path_for_gate(cwd=cwd, root=root)
    if status == TIERS_ABSENT:
        tiers = {role: model_tier.resolve_model(role, {}) for role in KNOWN_ROLES}
        return TierGate(tiers, {}, status, detail, None)
    if status != TIERS_OK:
        return TierGate(None, {}, status, detail, path)

    gate = overrides_for_gate(path)
    if tier_gate_is_refusal(gate):
        return TierGate(None, gate.overrides, gate.status, gate.detail, gate.path)
    tiers = {role: model_tier.resolve_model(role, gate.overrides) for role in KNOWN_ROLES}
    return TierGate(tiers, gate.overrides, TIERS_OK, None, path)


def tier_gate_is_refusal(gate):
    """True when ``effective_tiers_for_gate`` status refuses usable tiers."""
    return gate.status not in _TIER_GATE_USABLE_STATUSES


def tier_gate_is_absent(gate):
    """True when no profile is present at the resolved gate path."""
    return gate.status == TIERS_ABSENT


def tier_gate_is_ok(gate):
    """True when a readable profile was classified successfully."""
    return gate.status == TIERS_OK


def tier_gate_reason_for_status(status):
    """Return the canonical refusal reason string for a registered tier-gate status."""
    return _TIER_GATE_REFUSAL_REASONS[status]


def tier_gate_refusal(gate):
    """Return the ``core_md.gate_refusal`` payload for a refusal status, or ``None``."""
    import core_md

    if not tier_gate_is_refusal(gate):
        return None
    try:
        reason = tier_gate_reason_for_status(gate.status)
    except KeyError:
        return core_md.gate_refusal(
            TIER_REASON_EVALUATION_FAILED,
            "unregistered tier gate status: %s" % gate.status,
        )
    return core_md.gate_refusal(reason, gate.detail)


def resolve_profile_path(cwd=None, root=None):
    return _resolve_profile_path(cwd, root)


def _resolve_profile_path(cwd=None, root=None):
    """Auto-resolve the review-crew layer (unified) or legacy profile path. `root` threads the
    control-plane store root through so a global-store / custom-root setup reads its model tiers
    from the SAME store as the core prefs (else a dropped root silently resolves against the
    default store)."""
    try:
        import calibration_resolve
        return calibration_resolve.resolve_profile_path(cwd or os.getcwd(), root=root)
    except Exception as exc:
        _cr = sys.modules.get("calibration_resolve")
        if _cr is None:
            try:
                import calibration_resolve as _cr
            except Exception:
                _cr = None
        if _cr is not None and isinstance(exc, getattr(_cr, "UnresolvableRootError", ())):
            raise
        return None


def main(argv):
    import argparse
    raw = argv[1:]
    if raw and raw[0] in ("show", "write"):
        cmd = raw[0]
        ap = argparse.ArgumentParser(description="review-crew model-tier override configurator")
        ap.add_argument("--profile", default=None)
        if cmd == "write":
            ap.add_argument("--set", action="append", default=[], metavar="ROLE=MODEL")
            ap.add_argument("--clear", action="append", default=[], metavar="ROLE")
        args = ap.parse_args(raw[1:])
        if cmd == "show":
            if args.profile is not None:
                gate = effective_tiers_for_gate(profile_path=args.profile)
            else:
                gate = effective_tiers_for_gate(cwd=os.getcwd())
            refusal = tier_gate_refusal(gate)
            if refusal is not None:
                sys.stdout.write(json.dumps({
                    "ok": False,
                    "reason": refusal["reason"],
                    "detail": refusal["detail"],
                    "path": gate.path,
                }) + "\n")
                return 1
            sys.stdout.write(json.dumps({
                "ok": True,
                "path": gate.path,
                "overrides": gate.overrides,
                "effective": gate.tiers,
                "knownRoles": list(KNOWN_ROLES),
                "knownModels": list(KNOWN_MODELS),
            }) + "\n")
            return 0
        profile = args.profile if args.profile is not None else _resolve_profile_path()
        if not profile:
            sys.stdout.write(json.dumps({"ok": False, "reason": "profile-not-resolved"}) + "\n")
            return 1
        updates = {}
        warnings = []
        for item in args.set:
            if "=" not in item:
                warnings.append(f"malformed set item: {item} (expected role=model)")
                continue
            role, model = item.split("=", 1)
            updates[role.strip()] = model.strip()
        clear_roles = [r.strip() for r in args.clear]

        violations, gate_err = _evaluate_tier_writer_dispatch_gate(profile, updates, clear_roles)
        if gate_err is not None:
            sys.stdout.write(json.dumps({
                "ok": False,
                "reason": gate_err["reason"],
                "violations": [gate_err],
            }) + "\n")
            return 1
        if violations:
            sys.stdout.write(json.dumps({
                "ok": False,
                "reason": "fable-on-external-engine",
                "violations": violations,
            }) + "\n")
            return 1
        result = update_overrides(profile, updates, clear_roles)
        result["warnings"] = warnings + result["warnings"]
        sys.stdout.write(json.dumps(result) + "\n")
        return 0

    ap = argparse.ArgumentParser(description="review-crew model-tier override loader")
    ap.add_argument("--profile", default=None)
    args = ap.parse_args(raw)
    try:
        # An explicit --profile always wins; otherwise self-resolve the session's
        # review-crew profile (so the override feature actually LOADS in production
        # without the startup site having to add a second exec to find the path).
        profile = args.profile if args.profile is not None else _resolve_profile_path()
        ov = load_overrides(profile)
    except Exception:
        ov = {}  # belt-and-suspenders fail-open
    sys.stdout.write(json.dumps(ov) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
