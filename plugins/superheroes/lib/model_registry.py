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
        "opus-5": {"family": "anthropic", "dispatch": "opus", "override_only": False},
        "fable-5": {"family": "anthropic", "dispatch": "fable", "override_only": True},
    },
    "codex": {
        "gpt-5.6-terra": {"family": "openai", "dispatch": "gpt-5.6-terra", "override_only": False},
        "gpt-5.6-sol": {"family": "openai", "dispatch": "gpt-5.6-sol", "override_only": False},
    },
    # family is an independence-accounting key (panel maker exclusion), not vendor attribution.
    # Both cursor first-party models share ONE family so a ladder rung-up does not change the
    # maker family (#651, owner-ratified 2026-07-26; CONVENTIONS §7.5). Post-acquisition (2026-08-14)
    # cursor and xAI sit under one corporate roof, so the `xai` key reflects that affiliation while
    # remaining an accounting label, not a dispatch input. A new cursor first-party model added here
    # inherits this family by design; one that should be independent of composer needs an owner
    # ruling — splitting the family changes panel-exclusion behaviour.
    "cursor": {
        "composer-2.5": {
            "family": "xai",
            "dispatch": "composer-2.5",
            "override_only": False,
            "efforts": (),
        },
        "cursor-grok-4.6": {
            "family": "xai",
            "dispatch": "cursor-grok-4.6",
            "override_only": False,
            "efforts": ("xhigh",),
        },
    },
}

_EFFORT_ENUM: dict[str, tuple[str, ...]] = {
    "claude": ("low", "medium", "high", "xhigh"),
    "codex": ("none", "low", "medium", "high", "xhigh", "max"),
    "cursor": ("low", "medium", "high", "xhigh"),
}
OVERRIDE_ONLY_EFFORTS: dict[str, tuple[str, ...]] = {"codex": ("max",)}

_LADDERS: dict[str, tuple[tuple[str, str | None], ...]] = {
    "claude": (
        ("haiku-4.5", "medium"),
        ("sonnet-5", "high"),
        ("opus-5", "high"),
        ("opus-5", "xhigh"),
    ),
    "codex": (
        ("gpt-5.6-terra", "high"),
        ("gpt-5.6-sol", "high"),
        ("gpt-5.6-sol", "xhigh"),
    ),
    "cursor": (
        ("composer-2.5", None),
        ("cursor-grok-4.6", "xhigh"),
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
        "claude": ("opus-5", "high"),
        "codex": ("gpt-5.6-sol", "high"),
        "cursor": ("cursor-grok-4.6", "xhigh"),
    },
    "reviewer": {
        "claude": ("sonnet-5", "high"),
        "codex": ("gpt-5.6-terra", "high"),
        "cursor": ("cursor-grok-4.6", "xhigh"),
    },
    "reviewer-deep": {
        "claude": ("opus-5", "xhigh"),
        "codex": ("gpt-5.6-sol", "xhigh"),
        "cursor": ("cursor-grok-4.6", "xhigh"),
    },
    "verifier": {
        "claude": ("opus-5", "high"),
        "codex": ("gpt-5.6-sol", "high"),
        "cursor": ("cursor-grok-4.6", "xhigh"),
    },
    "brief-check": {
        "claude": ("opus-5", "xhigh"),
        "codex": ("gpt-5.6-sol", "xhigh"),
        "cursor": ("cursor-grok-4.6", "xhigh"),
    },
    "synthesis": {
        "claude": ("opus-5", "high"),
        "codex": None,
        "cursor": None,
    },
    "mechanical": {
        "claude": ("haiku-4.5", "medium"),
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

# --- Claude tier-alias resolution (verified, not assumed; issue #639) ---------------------------
# Claude dispatch tokens are tier ALIASES (`opus`, `sonnet`, `haiku`, `fable`): the harness resolves
# each to the LATEST model in that tier, so a claude `model_id` above is a LABEL for what its alias
# currently serves — never the string that dispatches. Decision (2026-07-26): keep the alias. An
# alias tracks harness upgrades silently, which is exactly how the `opus-4.8` label went
# stale-but-green; an explicit pin (`claude-opus-5`) would make the registry literal but would
# replace the owner-facing tier vocabulary the whole config surface keys on, and would turn a missed
# refresh into a dispatch of an OLDER model rather than a stale label. The alias's one weakness —
# a silently stale label — is bounded by the record below and its drift guard in
# tests/test_model_registry.py, which fails if a model id is bumped without re-probing.
#
# Probed live with `claude -p --model <alias>`; re-run and re-stamp on a harness upgrade.
CLAUDE_ALIAS_RESOLUTION = {
    "harness": "claude-code/2.1.219",
    "verified": "2026-07-26",
    "resolved": {
        "haiku": "claude-haiku-4-5-20251001",
        "sonnet": "claude-sonnet-5",
        "opus": "claude-opus-5",
        "fable": "claude-fable-5",
    },
}

FABLE_NEVER_DEFAULT = True

_MODEL_TIER_ROLES = (
    "orchestrator",
    "reviewer",
    "reviewer-deep",
    "verifier",
    "mechanical",
    "synthesis",
    "code-fixer",
    "doc-reviser",
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
_GROK_MODEL = "cursor-grok-4.6"


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


def _allowed_efforts(vendor: str, model_id: str) -> tuple[str, ...] | None:
    """Per-model effort constraint when the row declares `efforts`; else vendor enum."""
    rec = _MODELS.get(vendor, {}).get(model_id)
    if rec is None:
        return None
    if "efforts" in rec:
        return tuple(rec["efforts"])
    return _EFFORT_ENUM.get(vendor, ())


def dispatch_token(vendor: str, model_id: str, effort: str | None = None) -> str | None:
    if not is_registered(vendor, model_id):
        return None
    if vendor == "claude":
        return _MODELS[vendor][model_id]["dispatch"]
    if vendor == "codex":
        return model_id
    if vendor == "cursor":
        rec = _MODELS[vendor][model_id]
        allowed = _allowed_efforts(vendor, model_id)
        if allowed is None:
            return None
        if not allowed:
            if effort is not None:
                return None
            return rec["dispatch"]
        if effort is None or effort not in allowed:
            return None
        return f"{rec['dispatch']}-{effort}"
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
    allowed = _allowed_efforts(vendor, model_id)
    if allowed is None:
        return False, f"model {model_id!r} is not registered for vendor {vendor!r}"
    if "efforts" in rec:
        if not allowed:
            if effort is not None:
                return False, f"model {model_id!r} does not take an effort level"
        elif effort is None:
            return False, f"effort is required for model {model_id!r}"
        elif effort not in allowed:
            return False, f"effort {effort!r} is not valid for model {model_id!r}"
    elif effort not in allowed:
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


def claude_dispatch_tokens() -> tuple[str, ...]:
    """Every claude dispatch token sanctioned for at least one role, in ladder order.

    The ONE home for "what a claude dispatch may run": `launcher.py`'s launch-model validation
    and `engine_pref`'s builder-dispatch-tier classifier both read it, so a tier no role
    sanctions can never become a launch default. `fable` is override-only and absent from the
    claude ladder, so it is absent here by construction — see FABLE_NEVER_DEFAULT."""
    sanctioned: set[str] = set()
    for role in roles():
        for model_id, effort in allowlist(role, "claude"):
            tok = dispatch_token("claude", model_id, effort)
            if tok is not None:
                sanctioned.add(tok)
    out: list[str] = []
    seen: set[str] = set()
    for model_id, effort in ladder("claude"):
        tok = dispatch_token("claude", model_id, effort)
        if tok is not None and tok in sanctioned and tok not in seen:
            seen.add(tok)
            out.append(tok)
    return tuple(out)


def codex_models() -> tuple[str, ...]:
    return tuple(_MODELS["codex"])


def cursor_models() -> tuple[str, ...]:
    return tuple(_MODELS["cursor"])


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


def engine_pref_role_kind(role: str) -> str | None:
    """Codex effort / argv role_kind for a model-tier dispatch role.

    Not every returned value is a ``resolve_engine`` role_kind (e.g. ``review-deep``); prefer
    ``engine_pref_key`` + ``engine_pref.resolve_engine_pref_key`` for engine selection."""
    meta = _ROLE_META.get(role)
    if not meta:
        return None
    codex_kind = meta.get("codex_kind")
    if isinstance(codex_kind, str) and codex_kind:
        return codex_kind
    if meta.get("engine_pref_key") == "reviewer":
        return "review"
    return None


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


def parse_dispatch_token(vendor: str, token: str) -> tuple[str, str | None] | None:
    """Inverse of ``dispatch_token``: composed argv token → (model_id, effort)."""
    if not _is_str(vendor) or not _is_str(token) or vendor not in VENDORS:
        return None
    if vendor == "claude":
        for model_id, rec in _MODELS["claude"].items():
            if rec["dispatch"] == token:
                return (model_id, None)
        return None
    if vendor == "codex":
        if is_registered("codex", token):
            return (token, None)
        return None
    if vendor == "cursor":
        for model_id, rec in _MODELS["cursor"].items():
            dispatch = rec["dispatch"]
            if token == dispatch:
                allowed = _allowed_efforts(vendor, model_id)
                if allowed is None:
                    return None
                if not allowed:
                    return (model_id, None)
                return None
            allowed = _allowed_efforts(vendor, model_id)
            if not allowed:
                continue
            prefix = f"{dispatch}-"
            if token.startswith(prefix):
                effort = token[len(prefix) :]
                if effort in allowed:
                    return (model_id, effort)
        return None
    return None


def _allowlist_park_text(pairs: tuple[tuple[str, str | None], ...] | list) -> str:
    return ", ".join("(%s, %s)" % (m, e) for m, e in pairs)


def _resolve_dispatch_fail(
    reason: str,
    candidates: list[tuple[str, str | None]] | None = None,
) -> dict:
    return {
        "ok": False,
        "model_id": None,
        "effort": None,
        "dispatch_token": None,
        "effort_source": None,
        "candidates": [] if candidates is None else list(candidates),
        "reason": reason,
    }


def _resolve_dispatch_success(
    vendor: str,
    model_id: str,
    eff: str,
    effort_source: str,
    pairs: list[tuple[str, str | None]],
) -> dict:
    tok = dispatch_token(vendor, model_id, eff)
    if tok is None:
        return _resolve_dispatch_fail(
            f"({model_id!r}, {eff!r}) has no dispatch token for vendor {vendor!r}",
            pairs,
        )
    ok_cfg, why = validate_config(
        vendor, model_id, eff, allow_override_only=True
    )
    if not ok_cfg:
        return _resolve_dispatch_fail(why or "invalid config", pairs)
    return {
        "ok": True,
        "model_id": model_id,
        "effort": eff,
        "dispatch_token": tok,
        "effort_source": effort_source,
        "candidates": pairs,
        "reason": None,
    }


def resolve_dispatch(
    role: str,
    vendor: str,
    model: str | None = None,
    effort: str | None = None,
) -> dict:
    """Resolve registry id, dispatch token, or seat default to a dispatch triple."""
    if not _is_str(role):
        return _resolve_dispatch_fail(f"role must be a str, got {type(role).__name__}")
    if not _is_str(vendor):
        return _resolve_dispatch_fail(f"vendor must be a str, got {type(vendor).__name__}")
    if vendor not in VENDORS:
        return _resolve_dispatch_fail(f"unknown vendor {vendor!r}")
    if role not in roles():
        return _resolve_dispatch_fail(
            f"unknown role {role!r} — not a registered dispatch role"
        )

    pairs = list(allowlist(role, vendor))
    pairs_t = tuple(pairs)

    if model is not None and not _is_str(model):
        return _resolve_dispatch_fail(
            f"model must be a str or None, got {type(model).__name__}",
            pairs,
        )
    if effort is not None and not _is_str(effort):
        return _resolve_dispatch_fail(
            f"effort must be a str or None, got {type(effort).__name__}",
            pairs,
        )

    if not pairs:
        return _resolve_dispatch_fail(
            f"role {role!r} has no sanctioned model on vendor {vendor!r}"
        )

    token_effort: str | None = None

    if model is None:
        cell = matrix_config(role, vendor)
        if cell is None:
            return _resolve_dispatch_fail(
                f"no seat default for role {role!r} on vendor {vendor!r}"
            )
        if effort is None:
            if cell not in pairs_t:
                return _resolve_dispatch_fail(
                    f"seat default {cell!r} for role {role!r} on vendor {vendor!r} "
                    f"is not on its own allowlist",
                    pairs,
                )
            model_id, eff = cell
            effort_source = "seat-default"
            return _resolve_dispatch_success(
                vendor, model_id, eff, effort_source, pairs
            )
        model = cell[0]

    by_id = [p for p in pairs if p[0] == model]
    if not by_id:
        parsed = parse_dispatch_token(vendor, model)
        if parsed is None:
            pairs_text = _allowlist_park_text(pairs_t)
            return _resolve_dispatch_fail(
                f"model {model!r} is not on the {role}/{vendor} allowlist [{pairs_text}]",
                pairs,
            )
        p_model, p_effort = parsed
        if p_effort is not None and effort is not None and p_effort != effort:
            return _resolve_dispatch_fail(
                f"effort {effort!r} conflicts with the effort {p_effort!r} "
                f"encoded in dispatch token {model!r}",
                pairs,
            )
        token_effort = p_effort
        by_id = [
            p
            for p in pairs
            if p[0] == p_model and (p_effort is None or p[1] == p_effort)
        ]
        if not by_id:
            pairs_text = _allowlist_park_text(pairs_t)
            return _resolve_dispatch_fail(
                f"model {model!r} is not on the {role}/{vendor} allowlist [{pairs_text}]",
                pairs,
            )

    if effort is not None:
        cands = [p for p in by_id if p[1] == effort]
        if not cands:
            pairs_text = _allowlist_park_text(pairs_t)
            return _resolve_dispatch_fail(
                f"model {model!r} at effort {effort!r} is not on the "
                f"{role}/{vendor} allowlist [{pairs_text}]",
                pairs,
            )
    else:
        cands = by_id

    model_id, eff = cands[0]
    if effort is not None:
        effort_source = "given"
    elif token_effort is not None:
        effort_source = "token-encoded"
    elif len(cands) == 1:
        effort_source = "resolved-unique"
    else:
        effort_source = "resolved-lowest-rung"

    return _resolve_dispatch_success(
        vendor, model_id, eff, effort_source, pairs
    )
