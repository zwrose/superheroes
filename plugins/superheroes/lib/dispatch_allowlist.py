"""Pure allowlist validation for dispatch seats — no seat_bundle dependency (#1269 WO-8).

``dispatch_guard`` re-exports ``validate`` for back-compat; ``seat_bundle`` imports this
module directly so the CLI layer can import both at module level without a cycle.
"""
from __future__ import annotations

import model_registry

_PARK_TAIL = (
    "an unlisted model is a park, not a pick (#600). "
    "Pick a listed model or amend lib/model_registry.py."
)


def _tokens_for(role: str, vendor: str) -> list[str]:
    pairs = model_registry.allowlist(role, vendor)
    out: set[str] = set()
    for model_id, effort in pairs:
        tok = model_registry.dispatch_token(vendor, model_id, effort)
        if tok is not None:
            out.add(tok)
    return sorted(out)


def _pairs_json(candidates: list[tuple[str, str | None]]) -> list[list[str | None]]:
    return [[m, e] for m, e in candidates]


def _park(
    role: object,
    vendor: object,
    reason: str,
    *,
    allowlist: list[str] | None = None,
    allowlist_pairs: list[list[str | None]] | None = None,
) -> dict:
    return {
        "ok": False,
        "role": role,
        "vendor": vendor,
        "model_id": None,
        "effort": None,
        "dispatch_token": None,
        "effort_source": None,
        "resolved_model": None,
        "allowlist": [] if allowlist is None else allowlist,
        "allowlist_pairs": [] if allowlist_pairs is None else allowlist_pairs,
        "reason": reason,
    }


def _ok(
    role: str,
    vendor: str,
    tokens: list[str],
    resolved: dict,
) -> dict:
    dispatch_token = resolved["dispatch_token"]
    return {
        "ok": True,
        "role": role,
        "vendor": vendor,
        "model_id": resolved["model_id"],
        "effort": resolved["effort"],
        "dispatch_token": dispatch_token,
        "effort_source": resolved["effort_source"],
        "resolved_model": dispatch_token,
        "allowlist": tokens,
        "allowlist_pairs": _pairs_json(resolved["candidates"]),
        "reason": None,
    }


def validate(
    role: str,
    vendor: str,
    model: str | None = None,
    effort: str | None = None,
) -> dict:
    if not isinstance(role, str):
        return _park(role, vendor, f"role {role!r} is not a string")
    if vendor not in model_registry.vendors():
        return _park(role, vendor, f"unknown vendor {vendor!r}")
    if role not in model_registry.roles():
        return _park(
            role,
            vendor,
            f"unknown role {role!r} — not a registered dispatch role",
        )

    pairs = model_registry.allowlist(role, vendor)
    if not pairs:
        return _park(
            role,
            vendor,
            f"role {role!r} has no sanctioned model on vendor {vendor!r}",
        )

    tokens = _tokens_for(role, vendor)

    if model is not None and not isinstance(model, str):
        joined = ", ".join(tokens)
        return _park(
            role,
            vendor,
            f"model {model!r} is not on the {role}/{vendor} allowlist [{joined}] — "
            + _PARK_TAIL,
            allowlist=tokens,
            allowlist_pairs=_pairs_json(list(pairs)),
        )

    resolved = model_registry.resolve_dispatch(role, vendor, model, effort)

    if resolved["ok"]:
        return _ok(role, vendor, tokens, resolved)

    reason = resolved["reason"]
    if resolved["candidates"]:
        reason = f"{reason} — {_PARK_TAIL}"

    return _park(
        role,
        vendor,
        reason,
        allowlist=tokens,
        allowlist_pairs=_pairs_json(resolved["candidates"]),
    )
