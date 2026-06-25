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
import review_store          # noqa: E402


def resolve_verify_command(profile_path):
    """The profile's `## Verify` `command:` value (first wins), or 'none' when absent/unreadable."""
    if not profile_path or not os.path.exists(profile_path):
        return "none"
    try:
        with open(profile_path, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if line.startswith("command:"):
                    return line.split(":", 1)[1].strip() or "none"
    except OSError:
        return "none"
    return "none"


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


def resolve(cwd):
    res = review_store.resolve(cwd, "profile", review_store.store_root())
    profile = res.get("path") if res.get("exists") else None
    overrides = model_tier_overrides.load_overrides(profile)
    return {"verifyCommand": resolve_verify_command(profile), "tiers": resolve_tiers(overrides)}


def main(argv):
    ap = argparse.ArgumentParser(description="native review-code config resolver")
    ap.add_argument("--root", default=None, help="repo root (informational; cwd is used for resolution)")
    ap.parse_args(argv[1:])
    sys.stdout.write(json.dumps(resolve(os.getcwd())) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
