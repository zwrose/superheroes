"""Band-wide engine-preference policy: which ENGINE runs a role (claude|codex|cursor)
and at what effort — the axis ORTHOGONAL to model_tier's model choice. Pure +
deterministic. Fail-OPEN to claude — a wrong/absent/unavailable engine is a cost concern,
never a safety one (exactly model_tier.py's posture). load_engine_prefs (Task 3) reads
core.md's enginePreferences; these resolvers never touch disk."""
import json
import sys

import os

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

_MISSING = object()

ENGINES = ("claude", "codex", "cursor")

# role_kind -> the enginePreferences key it reads. `author-plan` (the front-half plan-author
# leaf) reads its OWN key — plan authoring routes independently of review/build; tasks
# authoring has no key on purpose and always runs native.
_ROLE_KEY = {"review": "reviewer", "build": "implementation", "fix": "implementation",
             "author-plan": "planAuthor"}

# effort defaults per engine. codex is effort-tiered; cursor is one composer model
# (FR-10, exempt); claude defers to model_tier (None). Depth-aware review: the deep reviewers
# (security/architecture — the reviewer-deep model tier) dispatch at 'review-deep' -> xhigh;
# regular review -> high. gpt-5.5 efforts: none/low/medium/high/xhigh.
_CODEX_EFFORT = {"review": "high", "review-deep": "xhigh", "build": "high", "fix": "low",
                 "author-plan": "xhigh"}
_CURSOR_EFFORT = "composer"

DEFAULT_STALL_LIMIT_SECONDS = 300


def resolve_engine(role_kind, prefs):
    """Return the engine for `role_kind`, fail-open to 'claude'. A missing/unknown role,
    a non-dict `prefs`, an absent key, or a value outside ENGINES all fall open."""
    key = _ROLE_KEY.get(role_kind)
    if key is None:
        return "claude"
    if not isinstance(prefs, dict):
        return "claude"
    v = prefs.get(key)
    if isinstance(v, str) and v in ENGINES:
        return v
    return "claude"


def resolve_effort(engine, role_kind, overrides=None):
    """Return the effort token for (engine, role_kind), or None (claude/unknown engine).
    A valid non-empty str override for role_kind wins; anything malformed falls to default."""
    if engine == "codex":
        default = _CODEX_EFFORT.get(role_kind, "high")
    elif engine == "cursor":
        default = _CURSOR_EFFORT
    else:
        return None  # claude (model_tier governs) or an unknown engine
    if isinstance(overrides, dict):
        v = overrides.get(role_kind, _MISSING)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return default


def resolve_timeout(overrides=None):
    """The finite UFR-5 stall limit in seconds. A valid positive int override wins; else the
    finite default. Always returns a finite positive int, never raises."""
    if isinstance(overrides, dict):
        v = overrides.get("timeout", _MISSING)
        if isinstance(v, bool):
            return DEFAULT_STALL_LIMIT_SECONDS  # bool is an int subclass — reject it
        if isinstance(v, int) and v > 0:
            return v
    return DEFAULT_STALL_LIMIT_SECONDS


def _normalize(engine):
    return engine if isinstance(engine, str) and engine in ENGINES else "claude"


def load_engine_prefs(cwd, root=None):
    """Read core.md's enginePreferences via core_md.read; normalize each role to a valid engine
    (else 'claude'); surface the optional FR-9 `effort` sub-map (a dict, else {}); absent block /
    None / any error → both 'claude' + empty effort. Never raises."""
    degenerate = {"reviewer": "claude", "implementation": "claude", "planAuthor": "claude",
                  "effort": {}}
    try:
        import core_md
        rec = core_md.read(cwd, root)
    except Exception:
        return degenerate
    if not isinstance(rec, dict):
        return degenerate
    prefs = rec.get("enginePreferences")
    if not isinstance(prefs, dict):
        return degenerate
    effort = prefs.get("effort")
    return {"reviewer": _normalize(prefs.get("reviewer")),
            "implementation": _normalize(prefs.get("implementation")),
            "planAuthor": _normalize(prefs.get("planAuthor")),
            "effort": dict(effort) if isinstance(effort, dict) else {}}
