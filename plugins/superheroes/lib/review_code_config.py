#!/usr/bin/env python3
"""Resolve the native review-code phase's per-project config (FR-3 / FR-7): the project verify
command and the leaf model tiers, from the resolved review-crew profile. Pure config resolution —
no loop-decision logic. Fail-open: a missing/unreadable profile yields verify 'none' and the
band-default tiers (a wrong/absent tier is a cost concern, never a safety one); a refused
calibration is surfaced via calibrationRefusal rather than silently ignored. stdlib only."""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model_tier            # noqa: E402
import model_tier_overrides  # noqa: E402
import core_md               # noqa: E402  (sibling)


VERIFY_REFUSAL_REASON = "verify-command-required"
VERIFY_REFUSAL_MESSAGE = (
    "Code review is not available until a verify command is set. Code review needs a command "
    "that verifies this project's code; set one with /superheroes:configure."
)


verify_command_configured = core_md.verify_command_configured  # the one shared no-command test


_RETIRED_VERIFY_MODES = ("review-only", "unverified")


def _is_retired_mode(value):
    """True when a legacy `mode:` value names a retired verify mode. Backticks and case are
    tolerated, and any inline annotation after the mode token (`review-only # disabled`) is
    ignored, so an annotated opt-out still refuses."""
    tokens = value.split("#", 1)[0].replace("`", " ").split()
    return bool(tokens) and tokens[0].lower() in _RETIRED_VERIFY_MODES


def resolve_verify_command(profile_path):
    """The profile's `## Verify` `command:` value (first wins), or 'none' when absent/unreadable."""
    return resolve_verify_from_profile(profile_path)


def resolve_verify_from_profile(profile_path):
    """Return the profile's `## Verify` `command:` value (first wins), or 'none' when the profile
    is absent, unreadable, or sets no command."""
    if not profile_path or not os.path.exists(profile_path):
        return "none"
    try:
        in_verify = False
        command = None
        with open(profile_path, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if line.startswith("## Verify"):
                    in_verify = True
                    continue
                if in_verify and line.startswith("## "):
                    break
                if not in_verify:
                    continue
                if line.startswith("mode:") and _is_retired_mode(line.split(":", 1)[1]):
                    # A retired opt-out mode wins over a retained command, in either order.
                    return "none"
                if command is None and line.startswith("command:"):
                    command = line.split(":", 1)[1].strip() or "none"
        return command or "none"
    except OSError:
        return "none"


# The cfg.tiers key -> model_tier role map. The single home for the review-code tier vocabulary
# on the Python side. The review-code fixer resolves the `code-fixer` role (review-code only
# fixes code).
_TIER_ROLE = {
    "reviewer": "reviewer",
    "reviewerDeep": "reviewer-deep",
    "synthesis": "synthesis",
    "fixer": "code-fixer",
}


def resolve_tiers(overrides):
    """The four leaf tiers (FR-7), honoring per-role profile overrides; None => inherit session.
    Resolved through the _TIER_ROLE vocabulary map (the SSOT for the cfg-key -> model_tier-role
    mapping)."""
    return {key: model_tier.resolve_model(role, overrides)
            for key, role in _TIER_ROLE.items()}


def _break_it_interpreter_value(record):
    """The ``breakItInterpreter`` calibration key as the core record carries it: the stored string
    verbatim (valid or not), None when absent or null, and "" for any other type so the driver
    reads a malformed value as set-but-invalid and fails closed, never as unset."""
    value = record.get(core_md.BREAK_IT_INTERPRETER_KEY)
    if value is None or isinstance(value, str):
        return value
    return ""


def resolve(cwd, root=None):
    verify = None
    profile = None
    overrides = {}
    refusal = None
    break_it_interpreter = None
    try:
        shared = core_md.resolve_shared(cwd, root=root)
        if isinstance(shared, dict) and shared.get("action") != "refused":
            break_it_interpreter = _break_it_interpreter_value(shared)
        if isinstance(shared, dict) and shared.get("action") == "refused":
            refusal = {
                "reason": shared.get("reason"),
                "paths": shared.get("paths") or [],
                "remedy": shared.get("remedy"),
            }
        elif shared and shared.get("verifyCommand"):
            verify = shared["verifyCommand"]
    except core_md.VerifyCommandMalformed as exc:
        # #1331: surfaced, never swallowed into the profile fallback — setup halts on this reason.
        refusal = {"reason": exc.reason, "paths": [], "remedy": str(exc)}
        verify = "none"
    except Exception:
        verify = None
    try:
        import calibration_resolve
        cal = calibration_resolve.resolve(cwd, root=root)
        profile = cal.get("dispatch_layer") or cal.get("legacy_path")
        if profile and not os.path.isfile(profile):
            profile = None
        if verify is None:
            verify = resolve_verify_from_profile(profile)
    except Exception as exc:
        _cr = sys.modules.get("calibration_resolve")
        if _cr is None:
            try:
                import calibration_resolve as _cr
            except Exception:
                _cr = None
        if _cr is not None and isinstance(exc, getattr(_cr, "UnresolvableRootError", ())):
            raise
        profile = None
    try:
        # Deliberate fail-open: model tiers here are a cost knob for review-code rounds,
        # not a governance gate — an unreadable profile yields band defaults (cost concern,
        # not a safety one). Governance/readout consumers use effective_tiers_for_gate.
        overrides = model_tier_overrides.load_overrides(profile)
    except Exception:
        overrides = {}
    configured = verify_command_configured(verify)
    if not configured:
        verify = "none"
    try:
        tiers = resolve_tiers(overrides)
    except Exception:
        tiers = resolve_tiers({})
    return {
        "verifyCommand": verify,
        "verifyRefusal": None if configured else {
            "reason": VERIFY_REFUSAL_REASON,
            "message": VERIFY_REFUSAL_MESSAGE,
        },
        "tiers": tiers,
        "calibrationRefusal": refusal,
        "breakItInterpreter": break_it_interpreter,
    }


def main(argv):
    ap = argparse.ArgumentParser(description="native review-code config resolver")
    ap.add_argument("--root", default=None, help="repo root (informational; cwd is used for resolution)")
    ap.parse_args(argv[1:])
    sys.stdout.write(json.dumps(resolve(os.getcwd())) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
