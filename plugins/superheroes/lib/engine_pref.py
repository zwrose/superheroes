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

# #309 role-appropriate dispatch ceilings (owner policy: HIGH ceilings + monitors, never borderline
# limits). WRITE roles (build/fix/author-plan) get a high ceiling; READ roles (review) a moderate one.
# These are CEILINGS, not expected durations, and are PAIRED with the byte-activity stall monitor
# (resolve_idle below). Twin of engine_pref.js's constants.
WRITE_TIMEOUT_SECONDS = 2400
READ_TIMEOUT_SECONDS = 900
_ROLE_TIMEOUT = {"build": WRITE_TIMEOUT_SECONDS, "fix": WRITE_TIMEOUT_SECONDS,
                 "author-plan": WRITE_TIMEOUT_SECONDS, "review": READ_TIMEOUT_SECONDS,
                 "review-deep": READ_TIMEOUT_SECONDS}

# #309 byte-activity stall thresholds — the monitor half of the ceiling+monitor pair (twin of
# engine_pref.js). A dispatch emitting NO output bytes for this many seconds is wedged and is killed
# well before the ceiling. Set far above a working engine's inter-chunk gaps (2026-07-09 receipts:
# codex ≤ ~8s, cursor ≤ ~4s), so a working CLI is never false-killed. WRITE roles get the longer idle
# window; READ roles the shorter. Both are under their role ceiling (monitor ≤ ceiling).
WRITE_IDLE_SECONDS = 600
READ_IDLE_SECONDS = 300
DEFAULT_IDLE_SECONDS = 300
_ROLE_IDLE = {"build": WRITE_IDLE_SECONDS, "fix": WRITE_IDLE_SECONDS,
              "author-plan": WRITE_IDLE_SECONDS, "review": READ_IDLE_SECONDS,
              "review-deep": READ_IDLE_SECONDS}


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


def resolve_timeout(overrides=None, role_kind=None):
    """The finite UFR-5 stall limit in seconds (#309). Resolution order: a valid positive int owner
    override (`overrides['timeout']`) wins over everything; else the role-appropriate ceiling for
    `role_kind` (WRITE_TIMEOUT_SECONDS / READ_TIMEOUT_SECONDS); else the legacy
    DEFAULT_STALL_LIMIT_SECONDS when no role is supplied (back-compat: the engine_authz probe and any
    pre-#309 caller keep 300s). Always returns a finite positive int, never raises."""
    if isinstance(overrides, dict):
        v = overrides.get("timeout", _MISSING)
        if isinstance(v, bool):
            pass  # bool is an int subclass — reject it, fall through to the role/default ceiling
        elif isinstance(v, int) and v > 0:
            return v
    if role_kind is not None and role_kind in _ROLE_TIMEOUT:
        return _ROLE_TIMEOUT[role_kind]
    return DEFAULT_STALL_LIMIT_SECONDS


def resolve_idle(overrides=None, role_kind=None):
    """The #309 byte-activity stall threshold in seconds — the monitor paired with resolve_timeout's
    ceiling. Resolution mirrors resolve_timeout: a valid positive-int owner override
    (`overrides['idleTimeout']`) wins; else the role-appropriate idle window (WRITE_IDLE / READ_IDLE);
    else DEFAULT_IDLE_SECONDS for an unknown/absent role. bool is rejected (int subclass). Always
    returns a finite positive int, never raises. The dispatch clamps to the ceiling (monitor ≤
    ceiling) and an override never disables the ceiling — both limits stay armed."""
    if isinstance(overrides, dict):
        v = overrides.get("idleTimeout", _MISSING)
        if isinstance(v, bool):
            pass  # bool is an int subclass — reject, fall through to the role/default idle
        elif isinstance(v, int) and v > 0:
            return v
    if role_kind is not None and role_kind in _ROLE_IDLE:
        return _ROLE_IDLE[role_kind]
    return DEFAULT_IDLE_SECONDS


def _normalize(engine):
    return engine if isinstance(engine, str) and engine in ENGINES else "claude"


def load_engine_prefs(cwd, root=None):
    """Read core.md's enginePreferences via core_md.read; normalize each role to a valid engine
    (else 'claude'); surface the optional FR-9 `effort` sub-map (a dict, else {}) and the optional
    #309 `timeout` owner override (a positive int, else omitted — resolve_timeout then falls to the
    role ceiling); absent block / None / any error → both 'claude' + empty effort. Never raises."""
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
    out = {"reviewer": _normalize(prefs.get("reviewer")),
           "implementation": _normalize(prefs.get("implementation")),
           "planAuthor": _normalize(prefs.get("planAuthor")),
           "effort": dict(effort) if isinstance(effort, dict) else {}}
    # #309 owner override channel: a positive-int `timeout` rides the same enginePreferences block so
    # resolve_timeout(prefs, role) can honor it at real dispatch. A bool (an int subclass) or any
    # non-positive/non-int value is dropped, leaving the role ceiling in force.
    timeout = prefs.get("timeout")
    if isinstance(timeout, int) and not isinstance(timeout, bool) and timeout > 0:
        out["timeout"] = timeout
    # #309 stall-monitor owner override: a positive-int `idleTimeout` rides the same block so
    # resolve_idle(prefs, role) can honor it at dispatch. Same guard as `timeout` (bool/non-positive
    # dropped, leaving the role idle window in force). The dispatch still clamps it to the ceiling.
    idle_timeout = prefs.get("idleTimeout")
    if isinstance(idle_timeout, int) and not isinstance(idle_timeout, bool) and idle_timeout > 0:
        out["idleTimeout"] = idle_timeout
    return out
