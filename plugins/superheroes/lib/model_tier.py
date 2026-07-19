"""Band-wide model-tier policy: role -> dispatch model name (the cost/perf knob).

Pure + deterministic. review-code, review-spec, and audit-debt are the wired
consumers (guarded by test_model_tier_wiring.py).
Returns the short names the Agent/Skill dispatch layer
accepts ("sonnet"/"opus"/"haiku"), or None to inherit the session model.

Fail-OPEN to the capable default — a wrong/absent tier is a cost concern, never a
safety one (contrast escalation.py, which fails CLOSED). Defaults below apply when
the profile is silent; a caller may pass {role: model} overrides from the project
calibration profile.
"""
import json
import sys

_MISSING = object()

# orchestrator -> None means "inherit the session model" (do not pin).
DEFAULT_TIERS = {
    "orchestrator": None,
    "reviewer": "sonnet",
    "reviewer-deep": "opus",       # security / architecture review
    "mechanical": "haiku",         # well-specified implementers, fixers, triage
    "synthesis": "opus",           # panel synthesis: the strongest tier (loop-owned)
    "fixer": "sonnet",             # default context = code-fixer (the mid-tier floor)
    "author": "opus",              # produce-plan / produce-tasks (front-half authoring, #88)
    "builder": "opus",             # native build-phase implementer (a smart leaf; owner policy -> opus)
    "pr-body": "sonnet",           # #219: durable draft-PR body composer (showrunner composePrBody)
    "implementer": "sonnet",   # v2 delegated work-order implementer (owner-ratified default: sonnet)
    "pilot": "sonnet",         # v2 test-pilot executor (owner-ratified default: sonnet)
}

# Split roles: a role here has no tier of its own — absent an explicit override it resolves
# EXACTLY as its base role (including the base's override). `author-plan` exists so plan
# authoring alone can be raised (e.g. to fable) without moving tasks authoring off `author`.
_ROLE_FALLBACK = {"author-plan": "author"}

ROLES = tuple(DEFAULT_TIERS) + tuple(_ROLE_FALLBACK)

# The single `fixer` role resolves by context (spec: one role, not two): a doc-reviser is
# re-authoring design (strongest tier), a code-fixer works from a prose worklist (mid floor).
_FIXER_BY_CONTEXT = {"code": "sonnet", "doc": "opus"}


def resolve_model(role, overrides=None, context=None):
    """Return the dispatch model name for `role`, or None to inherit the session model. An
    unknown role, a non-dict `overrides`, or a malformed override value falls back to
    DEFAULT_TIERS (fail-open). `context` selects the single `fixer` role's tier (code/doc);
    a per-project override on `fixer` still wins over the context default. A split role
    (_ROLE_FALLBACK) honors its own override first, else resolves as its base role."""
    base = _ROLE_FALLBACK.get(role)
    if base is not None:
        if isinstance(overrides, dict):
            v = overrides.get(role, _MISSING)
            if v is not _MISSING:
                if v is None:
                    return None
                if isinstance(v, str) and v.strip():
                    return v.strip()
                # malformed own-override -> resolve as the base role (fail-open)
        return resolve_model(base, overrides, context)
    if role not in DEFAULT_TIERS:
        role = "reviewer"  # safe capable default for an unrecognized role
    default = DEFAULT_TIERS[role]
    if role == "fixer" and context in _FIXER_BY_CONTEXT:
        default = _FIXER_BY_CONTEXT[context]
    if not isinstance(overrides, dict):
        return default
    v = overrides.get(role, _MISSING)
    if v is _MISSING:
        return default
    if v is None:
        return None
    if isinstance(v, str) and v.strip():
        return v.strip()
    return default  # malformed (non-str / empty) -> default


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description="band model-tier resolver (core)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("resolve")
    r.add_argument("--role", required=True)
    r.add_argument("--overrides", default=None, help="optional JSON {role: model}")
    r.add_argument("--context", default=None, help="optional fixer context: code|doc")
    args = ap.parse_args(argv[1:])
    overrides = None
    if args.overrides:
        try:
            overrides = json.loads(args.overrides)
        except (ValueError, json.JSONDecodeError):
            overrides = None  # fail-open
    model = resolve_model(args.role, overrides, args.context)
    sys.stdout.write(json.dumps({"role": args.role, "model": model}) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
