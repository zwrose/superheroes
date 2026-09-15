#!/usr/bin/env python3
"""Validate a workhorse engine dispatch's effective model against the registry allowlist.

This module is the MODEL-authority gate: it checks whether the effective ``--model`` is on the
seat's registry allowlist. For codex, model reasoning effort is validated separately and
fail-loud at the real dispatch boundary (``engine_adapter.build_argv`` →
``model_registry.validate_config``) before dispatch; ``--effort`` here is used to resolve
effort-qualified dispatch tokens and the registry-model-id ``is_allowed`` path, and this gate does not
re-police codex effort.

On success the JSON payload exposes the structured triple (``model_id``, ``effort``,
``dispatch_token``) plus ``effort_source``; ``resolved_model`` remains the composed dispatch
token for back-compat.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import cli_contract as cc  # noqa: E402
import model_registry  # noqa: E402
import seat_bundle  # noqa: E402

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


def _cli_check(args: argparse.Namespace) -> int:
    parsed = seat_bundle.parse(args.seat)
    if not parsed.get("ok"):
        payload = {
            "ok": False,
            "role": args.role,
            "vendor": None,
            "model_id": None,
            "effort": None,
            "dispatch_token": None,
            "effort_source": None,
            "resolved_model": None,
            "allowlist": [],
            "allowlist_pairs": [],
            "reason": parsed.get("reason"),
            "seat_detail": parsed.get("detail"),
        }
        print(json.dumps(payload))
        print(parsed.get("detail") or parsed.get("reason"), file=sys.stderr)
        return 1
    validated = seat_bundle.validate(parsed, args.role)
    if not validated.get("ok"):
        payload = {
            "ok": False,
            "role": args.role,
            "vendor": validated.get("vendor"),
            "model_id": None,
            "effort": None,
            "dispatch_token": None,
            "effort_source": None,
            "resolved_model": None,
            "allowlist": [],
            "allowlist_pairs": [],
            "reason": validated.get("reason"),
            "seat_detail": validated.get("detail"),
        }
        print(json.dumps(payload))
        print(validated.get("detail") or validated.get("reason"), file=sys.stderr)
        return 1
    result = validate(
        args.role,
        validated["vendor"],
        validated["model"],
        validated["effort"],
    )
    print(json.dumps(result))
    if not result["ok"]:
        print(result["reason"], file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dispatch model allowlist guard")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="Validate a dispatch against the allowlist")
    cc.add_argument(check, "--seat", contract="free-text", required=True,
                    help="JSON seat bundle or vendor:token composed dispatch token")
    cc.add_argument(check, "--role", contract="role", required=True, type=cc.role)
    check.set_defaults(func=_cli_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    dropped = seat_bundle.scan_dropped_flags(argv)
    if dropped:
        refusal = seat_bundle.legacy_refusal(dropped_flags=tuple(dropped))
        print(json.dumps(refusal))
        print(refusal["detail"], file=sys.stderr)
        return 1
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
