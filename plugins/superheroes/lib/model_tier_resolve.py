"""Skill-facing wrapper over the model_tier.py core.

Resolves role -> dispatch model name by calling the shared core directly (so
review-code and the trio get the band-wide knob without re-implementing the
table). In the consolidated one-plugin tree the core is a same-tree sibling, so
this wrapper imports it directly (no cross-plugin resolution, no subprocess).
Fail-OPEN: if the core errors, return the embedded default for the role (a
wrong/absent tier is a cost concern, never a safety one).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model_tier  # noqa: E402  (same-tree sibling core)

# Embedded fallback mirrors the core's DEFAULT_TIERS (used only when the core
# errors). The core is the source of truth; this is the degrade path.
_FALLBACK = {
    "orchestrator": None,
    "reviewer": "sonnet",
    "reviewer-deep": "opus",
    "mechanical": "haiku",
    "synthesis": "opus",
    "fixer": "sonnet",
    "author": "opus",
}


def _fallback(role):
    return _FALLBACK.get(role, _FALLBACK["reviewer"])


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description="model-tier resolver (superheroes)")
    ap.add_argument("--role", required=True)
    ap.add_argument("--overrides", default=None)
    ap.add_argument("--context", default=None, help="optional fixer context: code|doc")
    args = ap.parse_args(argv[1:])

    overrides = None
    if args.overrides:
        try:
            overrides = json.loads(args.overrides)
        except (ValueError, json.JSONDecodeError):
            overrides = None  # fail-open
    try:
        model = model_tier.resolve_model(args.role, overrides, args.context)
        sys.stdout.write(json.dumps({"role": args.role, "model": model,
                                     "degraded": False}) + "\n")
        return 0
    except Exception:
        sys.stdout.write(json.dumps({"role": args.role, "model": _fallback(args.role),
                                     "degraded": True}) + "\n")
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
