#!/usr/bin/env python3
"""Resolve the native review-code phase's per-project config (FR-3 / FR-7): the project verify
command and the leaf model tiers, from the resolved review-crew profile. Pure config resolution —
no loop-decision logic. Fail-open: a missing/unreadable profile yields verify 'none' and the
band-default tiers (a wrong/absent tier is a cost concern, never a safety one). stdlib only."""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model_tier            # noqa: E402
import model_tier_overrides  # noqa: E402
import core_md               # noqa: E402  (sibling)


def resolve_verify_command(profile_path):
    """The profile's `## Verify` `command:` value (first wins), or 'none' when absent/unreadable."""
    _mode, cmd = resolve_verify_from_profile(profile_path)
    return cmd


def resolve_verify_from_profile(profile_path):
    """Return (verify_mode, verify_command). verify_mode is None, 'unverified', or 'review-only'."""
    if not profile_path or not os.path.exists(profile_path):
        return None, "none"
    try:
        in_verify = False
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
                if line.startswith("mode: unverified"):
                    return "unverified", "none"
                if line.startswith("mode: review-only"):
                    return "review-only", "none"
                if line.startswith("command:"):
                    cmd = line.split(":", 1)[1].strip() or "none"
                    return None, cmd
    except OSError:
        return None, "none"
    return None, "none"


def resolve_tiers(overrides):
    """The four leaf tiers (FR-7), honoring per-role profile overrides; None => inherit session.
    The fixer is resolved in the CODE context (the mid-tier floor, sonnet) — never the doc context
    (opus); review-code only ever fixes code."""
    return {
        "reviewer": model_tier.resolve_model("reviewer", overrides),
        "reviewerDeep": model_tier.resolve_model("reviewer-deep", overrides),
        "synthesis": model_tier.resolve_model("synthesis", overrides),
        "fixer": model_tier.resolve_model("fixer", overrides, context="code"),
    }


def resolve(cwd, root=None):
    verify = None
    verify_mode = None
    profile = None
    overrides = {}
    try:
        shared = core_md.resolve_shared(cwd, root=root)
        if shared and shared.get("verifyCommand"):
            verify = shared["verifyCommand"]
    except Exception:
        verify = None
    try:
        import calibration_resolve
        cal = calibration_resolve.resolve(cwd, root=root)
        profile = cal.get("dispatch_layer") or cal.get("legacy_path")
        if profile and not os.path.isfile(profile):
            profile = None
        if verify is None:
            verify_mode, verify = resolve_verify_from_profile(profile)
    except Exception:
        profile = None
        verify_mode = None
    try:
        overrides = model_tier_overrides.load_overrides(profile)
    except Exception:
        overrides = {}
    if verify is None:
        verify = "none"
    try:
        tiers = resolve_tiers(overrides)
    except Exception:
        tiers = resolve_tiers({})
    return {"verifyCommand": verify, "verifyMode": verify_mode, "tiers": tiers}


def main(argv):
    ap = argparse.ArgumentParser(description="native review-code config resolver")
    ap.add_argument("--root", default=None, help="repo root (informational; cwd is used for resolution)")
    ap.parse_args(argv[1:])
    sys.stdout.write(json.dumps(resolve(os.getcwd())) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
