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
import json
import re
import sys

# Mirrors the core's DEFAULT_TIERS keys (the-architect/lib/model_tier.py); a role not in
# this set is an owner typo and is dropped (fail-open to the default).
KNOWN_ROLES = ("orchestrator", "reviewer", "reviewer-deep", "mechanical")

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
            if m and m.group(1) in KNOWN_ROLES:
                out[m.group(1)] = m.group(2)
    return out


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description="review-crew model-tier override loader")
    ap.add_argument("--profile", default=None)
    args = ap.parse_args(argv[1:])
    try:
        ov = load_overrides(args.profile)
    except Exception:
        ov = {}  # belt-and-suspenders fail-open
    sys.stdout.write(json.dumps(ov) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
