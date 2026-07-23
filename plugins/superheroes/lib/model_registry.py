"""Band-wide model/vendor registry: the single taxonomy data home (issue #509).

Pure + deterministic. Stdlib-only; never touches disk. Every model role/vendor map
elsewhere re-derives from THIS module — no parallel literals survive.

Fail-OPEN for selection resolvers (wrong/absent config is a cost concern, never safety).
`validate_config` is the explicit fail-loud surface — it returns (False, reason), never raises.
"""
from __future__ import annotations

VENDORS = ("claude", "codex", "cursor")

_MODELS: dict[str, dict[str, dict]] = {
    "claude": {
        "haiku-4.5": {"family": "anthropic", "dispatch": "haiku", "override_only": False},
        "sonnet-5": {"family": "anthropic", "dispatch": "sonnet", "override_only": False},
        "opus-4.8": {"family": "anthropic", "dispatch": "opus", "override_only": False},
        "fable-5": {"family": "anthropic", "dispatch": "fable", "override_only": True},
    },
    "codex": {
        "gpt-5.6-terra": {"family": "openai", "dispatch": "gpt-5.6-terra", "override_only": False},
        "gpt-5.6-sol": {"family": "openai", "dispatch": "gpt-5.6-sol", "override_only": False},
    },
    "cursor": {
        "composer-2.5": {"family": "cursor", "dispatch": "composer-2.5", "override_only": False},
        "cursor-grok-4.5": {"family": "xai", "dispatch": "cursor-grok-4.5", "override_only": False},
    },
}

_EFFORT_ENUM: dict[str, tuple[str, ...]] = {
    "claude": ("low", "medium", "high", "xhigh"),
    "codex": ("none", "low", "medium", "high", "xhigh", "max"),
    "cursor": ("low", "medium", "high"),
}
OVERRIDE_ONLY_EFFORTS: dict[str, tuple[str, ...]] = {"codex": ("max",)}

_LADDERS: dict[str, tuple[tuple[str, str | None], ...]] = {
    "claude": (
        ("haiku-4.5", "medium"),
        ("sonnet-5", "high"),
        ("opus-4.8", "high"),
        ("opus-4.8", "xhigh"),
    ),
    "codex": (
        ("gpt-5.6-terra", "high"),
        ("gpt-5.6-sol", "high"),
        ("gpt-5.6-sol", "xhigh"),
    ),
    "cursor": (
        ("composer-2.5", None),
        ("cursor-grok-4.5", "high"),
    ),
}

_MATRIX: dict[str, dict[str, tuple[str, str | None] | None]] = {
    "implementer": {
        "claude": ("sonnet-5", "high"),
        "codex": ("gpt-5.6-terra", "high"),
        "cursor": ("composer-2.5", None),
    },
    "code-fixer": {
        "claude": ("sonnet-5", "high"),
        "codex": ("gpt-5.6-terra", "high"),
        "cursor": ("composer-2.5", None),
    },
    "doc-reviser": {
        "claude": ("opus-4.8", "high"),
        "codex": ("gpt-5.6-sol", "high"),
        "cursor": ("cursor-grok-4.5", "high"),
    },
    "reviewer": {
        "claude": ("sonnet-5", "high"),
        "codex": ("gpt-5.6-terra", "high"),
        "cursor": ("cursor-grok-4.5", "high"),
    },
    "reviewer-deep": {
        "claude": ("opus-4.8", "xhigh"),
        "codex": ("gpt-5.6-sol", "xhigh"),
        "cursor": ("cursor-grok-4.5", "high"),
    },
    "verifier": {
        "claude": ("opus-4.8", "high"),
        "codex": ("gpt-5.6-sol", "high"),
        "cursor": ("cursor-grok-4.5", "high"),
    },
    "brief-check": {
        "claude": ("opus-4.8", "xhigh"),
        "codex": ("gpt-5.6-sol", "xhigh"),
        "cursor": ("cursor-grok-4.5", "high"),
    },
    "synthesis": {
        "claude": ("opus-4.8", "high"),
        "codex": None,
        "cursor": None,
    },
    "mechanical": {
        "claude": ("haiku-4.5", "medium"),
        "codex": None,
        "cursor": None,
    },
    "pr-body": {
        "claude": ("sonnet-5", "medium"),
        "codex": None,
        "cursor": None,
    },
    "pilot": {
        "claude": ("sonnet-5", "high"),
        "codex": None,
        "cursor": None,
    },
}

_ROLE_META: dict[str, dict] = {
    "orchestrator": {
        "model_tier_role": True,
        "engine_pref_key": None,
        "codex_kind": None,
        "read_write": None,
        "pin_eligible": False,
        "owner_tunable": False,
    },
    "reviewer": {
        "model_tier_role": True,
        "engine_pref_key": "reviewer",
        "codex_kind": "review",
        "read_write": "read",
        "pin_eligible": True,
        "owner_tunable": True,
    },
    "reviewer-deep": {
        "model_tier_role": True,
        "engine_pref_key": "reviewer",
        "codex_kind": "review-deep",
        "read_write": "read",
        "pin_eligible": True,
        "owner_tunable": True,
    },
    "verifier": {
        "model_tier_role": True,
        "engine_pref_key": "reviewer",
        "codex_kind": None,
        "read_write": "read",
        "pin_eligible": False,
        "owner_tunable": True,
    },
    "mechanical": {
        "model_tier_role": True,
        "engine_pref_key": None,
        "codex_kind": None,
        "read_write": None,
        "pin_eligible": False,
        "owner_tunable": True,
    },
    "synthesis": {
        "model_tier_role": True,
        "engine_pref_key": None,
        "codex_kind": None,
        "read_write": None,
        "pin_eligible": False,
        "owner_tunable": True,
    },
    "code-fixer": {
        "model_tier_role": True,
        "engine_pref_key": "implementation",
        "codex_kind": "fix",
        "read_write": "write",
        "pin_eligible": True,
        "owner_tunable": True,
    },
    "doc-reviser": {
        "model_tier_role": True,
        "engine_pref_key": "implementation",
        "codex_kind": "fix",
        "read_write": "write",
        "pin_eligible": False,
        "owner_tunable": True,
    },
    "pr-body": {
        "model_tier_role": True,
        "engine_pref_key": None,
        "codex_kind": None,
        "read_write": None,
        "pin_eligible": False,
        "owner_tunable": True,
    },
    "implementer": {
        "model_tier_role": True,
        "engine_pref_key": "implementation",
        "codex_kind": "build",
        "read_write": "write",
        "pin_eligible": True,
        "owner_tunable": True,
    },
    "pilot": {
        "model_tier_role": True,
        "engine_pref_key": "pilot",
        "codex_kind": "pilot",
        "read_write": None,
        "pin_eligible": True,
        "owner_tunable": True,
    },
    "brief-check": {
        "model_tier_role": False,
        "engine_pref_key": "briefCheck",
        "codex_kind": "brief-check",
        "read_write": "read",
        "pin_eligible": False,
        "owner_tunable": False,
    },
}

FABLE_NEVER_DEFAULT = True
SMART_CLAUDE_FALLBACK = ("opus-4.8", None)

_MODEL_TIER_ROLES = (
    "orchestrator",
    "reviewer",
    "reviewer-deep",
    "verifier",
    "mechanical",
    "synthesis",
    "code-fixer",
    "doc-reviser",
    "pr-body",
    "implementer",
    "pilot",
)

_CODEX_PIN_ROLES = ("reviewer", "reviewer-deep", "code-fixer", "implementer", "pilot")

_CODEX_PEER_BY_CLAUDE = {
    "sonnet": "gpt-5.6-terra",
    "opus": "gpt-5.6-sol",
    "haiku": "gpt-5.6-terra",
}

_COMPOSER_MODEL = "composer-2.5"
_GROK_MODEL = "cursor-grok-4.5"


def vendors() -> tuple[str, ...]:
    return VENDORS


def roles() -> tuple[str, ...]:
    return tuple(_MATRIX)


def model_tier_roles() -> tuple[str, ...]:
    return _MODEL_TIER_ROLES


def is_registered(vendor: str, model_id: str) -> bool:
    return vendor in _MODELS and model_id in _MODELS[vendor]


def model_family(vendor: str, model_id: str) -> str | None:
    rec = _MODELS.get(vendor, {}).get(model_id)
    return rec["family"] if rec else None


def matrix_config(role: str, vendor: str) -> tuple[str, str | None] | None:
    row = _MATRIX.get(role)
    if row is None:
        return None
    return row.get(vendor)


def ladder(vendor: str) -> tuple[tuple[str, str | None], ...]:
    return _LADDERS.get(vendor, ())


def effort_enum(vendor: str) -> tuple[str, ...]:
    return _EFFORT_ENUM.get(vendor, ())


def dispatch_token(vendor: str, model_id: str, effort: str | None = None) -> str | None:
    if not is_registered(vendor, model_id):
        return None
    if vendor == "claude":
        return _MODELS[vendor][model_id]["dispatch"]
    if vendor == "codex":
        return model_id
    if vendor == "cursor":
        if model_id == _COMPOSER_MODEL:
            return _COMPOSER_MODEL
        if model_id == _GROK_MODEL:
            if effort is None:
                return None
            return f"{_GROK_MODEL}-{effort}"
    return None


def validate_config(
    vendor: str,
    model_id: str,
    effort: str | None,
    allow_override_only: bool = False,
) -> tuple[bool, str | None]:
    if vendor not in VENDORS:
        return False, f"unknown vendor {vendor!r}"
    vendor_models = _MODELS.get(vendor, {})
    if model_id not in vendor_models:
        return False, f"model {model_id!r} is not registered for vendor {vendor!r}"
    rec = vendor_models[model_id]
    if rec.get("override_only") and not allow_override_only:
        return False, f"model {model_id!r} is override-only"
    if vendor == "cursor" and model_id == _COMPOSER_MODEL:
        if effort is not None:
            return False, f"model {model_id!r} does not take an effort level"
        return True, None
    enum = _EFFORT_ENUM.get(vendor, ())
    if effort not in enum:
        return False, f"effort {effort!r} is not valid for vendor {vendor!r}"
    override_efforts = OVERRIDE_ONLY_EFFORTS.get(vendor, ())
    if effort in override_efforts and not allow_override_only:
        return False, f"effort {effort!r} is override-only for vendor {vendor!r}"
    return True, None


def escalate(
    vendor: str, model_id: str, effort: str | None
) -> tuple[str, str, str | None] | None:
    rungs = _LADDERS.get(vendor)
    if not rungs:
        return None
    pos = None
    for i, (m, e) in enumerate(rungs):
        if m == model_id and e == effort:
            pos = i
            break
    if pos is None:
        return None
    if pos + 1 < len(rungs):
        nxt_m, nxt_e = rungs[pos + 1]
        return (vendor, nxt_m, nxt_e)
    vi = VENDORS.index(vendor)
    next_vendor = VENDORS[(vi + 1) % len(VENDORS)]
    first_m, first_e = _LADDERS[next_vendor][0]
    return (next_vendor, first_m, first_e)


def default_claude_tiers() -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for role in _MODEL_TIER_ROLES:
        if role == "orchestrator":
            out[role] = None
            continue
        cell = matrix_config(role, "claude")
        if cell is None:
            out[role] = None
            continue
        model_id, effort = cell
        out[role] = dispatch_token("claude", model_id, effort)
    return out


def known_roles() -> tuple[str, ...]:
    return tuple(r for r in _MODEL_TIER_ROLES if r != "orchestrator")


def known_claude_models() -> tuple[str, ...]:
    return ("haiku", "sonnet", "opus", "fable")


def codex_models() -> tuple[str, ...]:
    return tuple(_MODELS["codex"])


def codex_efforts() -> tuple[str, ...]:
    return _EFFORT_ENUM["codex"]


def codex_model_strength() -> tuple[str, ...]:
    seen: list[str] = []
    for model_id, _ in _LADDERS["codex"]:
        if model_id not in seen:
            seen.append(model_id)
    return tuple(seen)


def codex_effort_for_kind(codex_kind: str) -> str:
    for role, meta in _ROLE_META.items():
        if meta.get("codex_kind") == codex_kind:
            cell = matrix_config(role, "codex")
            if cell is not None:
                return cell[1] or "high"
    return "medium" if codex_kind == "pilot" else "high"


def codex_peer_for_claude_tier(claude_short: str) -> str:
    if claude_short == "fable":
        raise ValueError(
            "no codex peer for claude tier 'fable' — fable is anthropic-only; "
            "a cross-family substitution is forbidden"
        )
    if claude_short in _CODEX_PEER_BY_CLAUDE:
        return _CODEX_PEER_BY_CLAUDE[claude_short]
    return "gpt-5.6-sol"


def codex_pin_roles() -> tuple[str, ...]:
    return _CODEX_PIN_ROLES


def codex_role_kind() -> dict[str, str]:
    return {role: _ROLE_META[role]["codex_kind"] for role in _CODEX_PIN_ROLES}


def codex_write_pin_roles() -> tuple[str, ...]:
    """Pin-eligible roles whose read_write is 'write', in stable registry order."""
    return ("code-fixer", "implementer")


def engine_pref_key(role: str) -> str | None:
    meta = _ROLE_META.get(role)
    return meta["engine_pref_key"] if meta else None


def cursor_dispatch_id(role: str) -> str | None:
    cell = matrix_config(role, "cursor")
    if cell is None:
        return None
    model_id, effort = cell
    return dispatch_token("cursor", model_id, effort)


def _is_str(value: object) -> bool:
    return isinstance(value, str)


def family_for(role: str, vendor: str) -> str | None:
    if not _is_str(role) or not _is_str(vendor):
        return None
    cell = matrix_config(role, vendor)
    if cell is None:
        return None
    model_id, _effort = cell
    return model_family(vendor, model_id)


def allowlist(role: str, vendor: str) -> tuple[tuple[str, str | None], ...]:
    if not _is_str(role) or not _is_str(vendor):
        return ()
    cell = matrix_config(role, vendor)
    if cell is None:
        return ()
    rungs = ladder(vendor)
    index = None
    for i, rung in enumerate(rungs):
        if rung == cell:
            index = i
            break
    if index is None:
        model_id, effort = cell
        if not is_registered(vendor, model_id):
            return ()
        ok, _ = validate_config(vendor, model_id, effort, allow_override_only=True)
        return (cell,) if ok else ()
    out: list[tuple[str, str | None]] = []
    for model_id, effort in rungs[index:]:
        if not is_registered(vendor, model_id):
            continue
        ok, _ = validate_config(vendor, model_id, effort, allow_override_only=True)
        if ok:
            out.append((model_id, effort))
    return tuple(out)


def is_allowed(
    role: str, vendor: str, model: str, effort: str | None
) -> bool:
    if not _is_str(role) or not _is_str(vendor) or not _is_str(model):
        return False
    if effort is not None and not _is_str(effort):
        return False
    return (model, effort) in allowlist(role, vendor)
