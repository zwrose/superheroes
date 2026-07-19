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

# Canonical v2 engine-preference role keys (the single home the §11 drift guard reads). Each is a
# key under core.md's enginePreferences. `orchestrator` is intentionally absent — the session model
# is not owner-configurable. `planAuthor` is retired (plan authoring was retired in #479) — it is
# not a v2 schema key and survives only as a tombstone in RETIRED_ENGINE_KEYS below.
ENGINE_ROLE_KEYS = ("reviewer", "implementation", "briefCheck", "pilot")

# The FULL valid enginePreferences key set (role keys + the non-role tuning keys) — the schema home
# the §11 drift guard reads so no test re-types the list. `codexModels`/`effort`/`timeout`/
# `idleTimeout` are the non-role keys load_engine_prefs already honors.
ENGINE_PREF_KEYS = ENGINE_ROLE_KEYS + ("codexModels", "effort", "timeout", "idleTimeout")

# Retired enginePreferences keys that must never be cited as a live config knob again (plan authoring
# was retired in #479). The §11 drift guard asserts these never re-appear in the calibration prose.
RETIRED_ENGINE_KEYS = ("planAuthor",)

# Codex model policy is provider-specific and deliberately separate from model_tier's
# Claude-family capability names. Shared tiers express role strength; this map translates those
# strengths at the external boundary. Explicit pins live under enginePreferences.codexModels so a
# GPT id can never leak into a native Claude fallback or Cursor dispatch.
CODEX_MODELS = ("gpt-5.5", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna")
CODEX_MODEL_BY_TIER = {
    "haiku": "gpt-5.6-luna",
    "sonnet": "gpt-5.6-terra",
    "opus": "gpt-5.6-sol",
    "fable": "gpt-5.6-sol",
}
CODEX_PIN_ROLES = ("reviewer", "reviewer-deep", "fixer", "implementer", "pilot")
CODEX_ROLE_KIND = {"reviewer": "review", "reviewer-deep": "review-deep",
                   "fixer": "fix", "implementer": "build", "pilot": "pilot"}
CODEX_EFFORTS = ("none", "low", "medium", "high", "xhigh", "max")
CODEX_MAX_UNSUPPORTED_MODELS = ("gpt-5.5",)

# #409 write-auth probe strength order (weakest → strongest). The build-authz probe (engine_authz)
# dispatches the strongest model the codex implementation role will actually run, so a passing probe
# covers every weaker dispatch. Kept a superset of CODEX_MODELS (guarded by a unit test) so no valid
# pin is ever unrankable and silently dropped.
CODEX_MODEL_STRENGTH = ("gpt-5.5", "gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol")

# The pin roles the codex IMPLEMENTATION role dispatches as workspace writes (build + fix). The
# write-auth probe (engine_authz) must cover exactly these — reviewer roles run on separate
# (read / non-write-gated) paths, so their pins are irrelevant to whether a build write is authorized.
CODEX_WRITE_PIN_ROLES = ("implementer", "fixer")

# role_kind -> the enginePreferences key it reads. `brief-check` (the v2 cross-vendor pre-code
# reviewer) and `pilot` (the v2 test-pilot executor) each read their own key.
_ROLE_KEY = {"review": "reviewer", "build": "implementation", "fix": "implementation",
             "brief-check": "briefCheck", "pilot": "pilot"}

# Most roles fail open to claude; the brief-check reviewer defaults to codex (the ratified
# cross-vendor pre-code check). An unavailable codex is handled at dispatch time (disclosed
# claude+opus fallback), never here — this resolver is pure and never probes.
_ROLE_DEFAULT_ENGINE = {"brief-check": "codex"}

# When the brief-check reviewer must fall back to a Claude reviewer (codex unavailable), it runs at
# this tier — a tier UP from the sonnet implementer, never session-inherited. Disclosed at dispatch.
BRIEF_CHECK_CLAUDE_FALLBACK_TIER = "opus"


def _effective_model(engine, pin_role, tier, prefs):
    """The model to REPORT for a dispatch role given its resolved engine — honest provenance.
    claude → the Claude tier; codex → the concrete Codex model (pin or tier→GPT map); cursor → the
    single composer model. `pin_role` is the CODEX_PIN_ROLES key for this role (or None)."""
    if engine == "codex":
        return resolve_engine_model("codex", pin_role, tier, prefs) or tier
    if engine == "cursor":
        return "(cursor composer)"
    return tier  # claude (or unknown) → the Claude-family tier


def dispatch_calibration_rows(prefs, tiers):
    """The effective (engine, model) per v2 dispatch role — the ONE source both the configure view
    and the preflight readout format. `prefs` MUST be the RAW enginePreferences dict (NOT
    load_engine_prefs output: an absent `briefCheck` must stay ABSENT so resolve_engine applies the
    codex default; a normalized 'claude' would suppress it). `tiers` is the effective model-tier map.
    Honest per-engine provenance: `model` is meaningful only when engine==claude (the Claude tier);
    an external engine carries its OWN model (the resolved Codex model, or cursor's single composer
    model) via `_effective_model` — never the Claude tier misreported as what actually ran.
    Returns a list of {role, engine, model}. Pure; tolerant of non-dict inputs."""
    prefs = prefs if isinstance(prefs, dict) else {}
    tiers = tiers if isinstance(tiers, dict) else {}
    brief_engine = resolve_engine("brief-check", prefs)
    brief_model = _effective_model(brief_engine, None, BRIEF_CHECK_CLAUDE_FALLBACK_TIER, prefs)
    impl_engine = resolve_engine("build", prefs)
    rev_engine = resolve_engine("review", prefs)
    pilot_engine = resolve_engine("pilot", prefs)
    return [
        {"role": "implementer", "engine": impl_engine,
         "model": _effective_model(impl_engine, "implementer", tiers.get("implementer"), prefs)},
        {"role": "brief-check", "engine": brief_engine, "model": brief_model},
        {"role": "review-code", "engine": rev_engine,
         "model": "reviewer=%s reviewer-deep=%s" % (
             _effective_model(rev_engine, "reviewer", tiers.get("reviewer"), prefs),
             _effective_model(rev_engine, "reviewer-deep", tiers.get("reviewer-deep"), prefs))},
        {"role": "pilot", "engine": pilot_engine,
         "model": _effective_model(pilot_engine, "pilot", tiers.get("pilot"), prefs)},
    ]


# effort defaults per engine. codex is effort-tiered; cursor is one composer model
# (FR-10, exempt); claude defers to model_tier (None). Depth-aware review: the deep reviewers
# (security/architecture — the reviewer-deep model tier) dispatch at 'review-deep' -> xhigh;
# regular review -> high. GPT-5.6 additionally accepts max, but max is owner opt-in only;
# GPT-5.5 remains limited to none/low/medium/high/xhigh.
_CODEX_EFFORT = {"review": "high", "review-deep": "xhigh", "build": "high", "fix": "low",
                 "brief-check": "high", "pilot": "medium"}
_CURSOR_EFFORT = "composer"

DEFAULT_STALL_LIMIT_SECONDS = 300

# #309 role-appropriate dispatch ceilings (owner policy: HIGH ceilings + monitors, never borderline
# limits). WRITE roles (build/fix) get a high ceiling; READ roles (review) a moderate one.
# These are CEILINGS, not expected durations, and are PAIRED with the byte-activity stall monitor
# (resolve_idle below). Twin of engine_pref.js's constants.
WRITE_TIMEOUT_SECONDS = 2400
READ_TIMEOUT_SECONDS = 900
_ROLE_TIMEOUT = {"build": WRITE_TIMEOUT_SECONDS, "fix": WRITE_TIMEOUT_SECONDS,
                 "review": READ_TIMEOUT_SECONDS, "review-deep": READ_TIMEOUT_SECONDS}

# #309 byte-activity stall thresholds — the monitor half of the ceiling+monitor pair (twin of
# engine_pref.js). A dispatch emitting NO output bytes for this many seconds is wedged and is killed
# well before the ceiling. Set far above a working engine's inter-chunk gaps (2026-07-09 receipts:
# codex ≤ ~8s, cursor ≤ ~4s), so a working CLI is never false-killed. WRITE roles get the longer idle
# window; READ roles the shorter. Both are under their role ceiling (monitor ≤ ceiling).
WRITE_IDLE_SECONDS = 600
READ_IDLE_SECONDS = 300
DEFAULT_IDLE_SECONDS = 300
_ROLE_IDLE = {"build": WRITE_IDLE_SECONDS, "fix": WRITE_IDLE_SECONDS,
              "review": READ_IDLE_SECONDS, "review-deep": READ_IDLE_SECONDS}


def resolve_engine(role_kind, prefs):
    """Return the engine for `role_kind`, fail-open to its role default (claude for most roles;
    codex for the cross-vendor brief-check reviewer — see _ROLE_DEFAULT_ENGINE). A missing/unknown
    role, a non-dict `prefs`, an absent key, or a value outside ENGINES all fall open to that
    default. A VALID configured engine in ENGINES always wins."""
    key = _ROLE_KEY.get(role_kind)
    if key is None:
        return _ROLE_DEFAULT_ENGINE.get(role_kind, "claude")
    if not isinstance(prefs, dict):
        return _ROLE_DEFAULT_ENGINE.get(role_kind, "claude")
    v = prefs.get(key)
    if isinstance(v, str) and v in ENGINES:
        return v
    return _ROLE_DEFAULT_ENGINE.get(role_kind, "claude")


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


def resolve_engine_model(engine, tier_role, tier_model, prefs=None):
    """Return the concrete Codex model for a role, or None for another engine.

    A valid per-role persistent pin wins. Otherwise a known shared tier maps to its GPT-5.6
    capability peer. An unknown tier fails open to Sol, the capable default; it never reuses an
    invalid owner pin and never changes another provider's model selection.
    """
    if engine != "codex":
        return None
    pins = prefs.get("codexModels") if isinstance(prefs, dict) else None
    if isinstance(pins, dict):
        pinned = pins.get(tier_role)
        if isinstance(pinned, str) and pinned in CODEX_MODELS:
            return pinned
    return CODEX_MODEL_BY_TIER.get(tier_model, "gpt-5.6-sol")


def codex_write_probe_model(prefs):
    """The Codex model the build/fix write-auth probe should dispatch (#409): the strongest model the
    implementation role will actually RUN. Each write role (build, fix) contributes its explicit pin
    when set, else the sol capability floor — an UNPINNED codex write role derives a GPT-5.6 tier model
    (up to sol), so it must keep the floor in the max, never under-testing the real dispatch. A project
    whose write roles are pinned ENTIRELY to an older family (e.g. gpt-5.5) therefore probes that
    family (not falsely failed by a hard sol probe), while any unpinned write role clamps the probe up
    to sol — preserving the original rationale (an old CLI must not falsely pass). Takes a
    load_engine_prefs() result (so pins are already validity-filtered). Pure; never raises; always
    returns a valid model in CODEX_MODEL_STRENGTH."""
    pins = prefs.get("codexModels") if isinstance(prefs, dict) else None
    pins = pins if isinstance(pins, dict) else {}
    floor = CODEX_MODEL_BY_TIER["opus"]  # sol — the strongest a tier fallback can derive
    candidates = []
    for role in CODEX_WRITE_PIN_ROLES:
        model = pins.get(role)
        candidates.append(model if model in CODEX_MODEL_STRENGTH else floor)
    return max(candidates, key=CODEX_MODEL_STRENGTH.index)


def valid_codex_model_effort(model, effort):
    """Whether an explicit Codex model/effort pair is dispatchable by owner policy."""
    if model not in CODEX_MODELS or effort not in CODEX_EFFORTS:
        return False
    return not (model in CODEX_MAX_UNSUPPORTED_MODELS and effort == "max")


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
    degenerate = {"reviewer": "claude", "implementation": "claude",
                  "briefCheck": "claude", "pilot": "claude", "effort": {}}
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
           "briefCheck": _normalize(prefs.get("briefCheck")),
           "pilot": _normalize(prefs.get("pilot")),
           "effort": dict(effort) if isinstance(effort, dict) else {}}
    codex_models = prefs.get("codexModels")
    if isinstance(codex_models, dict):
        pins = {}
        invalid = {}
        for role, model in codex_models.items():
            if role not in CODEX_PIN_ROLES:
                invalid[role] = "unknown role %r rejected" % role
                continue
            if not isinstance(model, str) or model not in CODEX_MODELS:
                invalid[role] = "unknown model %r rejected" % model
                continue
            role_effort = resolve_effort("codex", CODEX_ROLE_KIND[role], out["effort"])
            if valid_codex_model_effort(model, role_effort):
                pins[role] = model
            else:
                invalid[role] = "%s + %s is invalid" % (model, role_effort)
        if pins:
            out["codexModels"] = pins
        if invalid:
            out["invalidCodexModels"] = invalid
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
