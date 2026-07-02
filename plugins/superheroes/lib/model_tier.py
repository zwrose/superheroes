"""Band-wide model-tier policy: role -> dispatch model name (the cost/perf knob).

Pure + deterministic. review-code is the first consumer; the review trio
(review-spec/review-plan/review-tasks) and audit-debt wire it next. Workhorse's
Build leg defers to SDD's own model heuristic and is NOT a model_tier consumer;
note that the native build leg (build_phase.js) IS now an *engine* consumer (#38) —
the engine axis (claude|codex|cursor via engine_pref) is orthogonal to this model
tier and governs which agent family runs a role, not which Claude model.
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
}

ROLES = tuple(DEFAULT_TIERS)

# The single `fixer` role resolves by context (spec: one role, not two): a doc-reviser is
# re-authoring design (strongest tier), a code-fixer works from a prose worklist (mid floor).
_FIXER_BY_CONTEXT = {"code": "sonnet", "doc": "opus"}


def resolve_model(role, overrides=None, context=None):
    """Return the dispatch model name for `role`, or None to inherit the session model. An
    unknown role, a non-dict `overrides`, or a malformed override value falls back to
    DEFAULT_TIERS (fail-open). `context` selects the single `fixer` role's tier (code/doc);
    a per-project override on `fixer` still wins over the context default."""
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
