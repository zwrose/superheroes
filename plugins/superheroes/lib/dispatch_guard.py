#!/usr/bin/env python3
"""Validate a workhorse engine dispatch's effective model against the registry allowlist.

This module is the MODEL-authority gate: it checks whether the effective ``--model`` is on the
seat's registry allowlist. For codex, model reasoning effort is validated separately and
fail-loud at the real dispatch boundary (``engine_adapter.build_argv`` →
``model_registry.validate_config``) before dispatch; ``--effort`` here is used to resolve
effort-qualified dispatch tokens and the registry-model-id ``is_allowed`` path, and this gate does not
re-police codex effort.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import model_registry  # noqa: E402

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


def _park(
    role: object,
    vendor: object,
    reason: str,
    *,
    allowlist: list[str] | None = None,
) -> dict:
    return {
        "ok": False,
        "role": role,
        "vendor": vendor,
        "resolved_model": None,
        "allowlist": [] if allowlist is None else allowlist,
        "reason": reason,
    }


def _ok(role: str, vendor: str, resolved_model: str, allowlist: list[str]) -> dict:
    return {
        "ok": True,
        "role": role,
        "vendor": vendor,
        "resolved_model": resolved_model,
        "allowlist": allowlist,
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

    if model is None:
        cell = model_registry.matrix_config(role, vendor)
        # defensive: unreachable while matrix_config(role,vendor) is None <=> allowlist()==() (registry invariant); kept as belt-and-suspenders against future divergence.
        if cell is None:
            return _park(
                role,
                vendor,
                f"no seat default for role {role!r} on vendor {vendor!r}",
                allowlist=tokens,
            )
        resolved = model_registry.dispatch_token(vendor, *cell)
        if resolved is None or resolved not in tokens:
            joined = ", ".join(tokens)
            return _park(
                role,
                vendor,
                (
                    f"default for role {role!r} on vendor {vendor!r} is not on the "
                    f"{role}/{vendor} allowlist [{joined}]"
                ),
                allowlist=tokens,
            )
        return _ok(role, vendor, resolved, tokens)

    if not isinstance(model, str):
        joined = ", ".join(tokens)
        return _park(
            role,
            vendor,
            f"model {model!r} is not on the {role}/{vendor} allowlist [{joined}] — "
            + _PARK_TAIL,
            allowlist=tokens,
        )

    if model in tokens:
        return _ok(role, vendor, model, tokens)

    if model_registry.is_allowed(role, vendor, model, effort):
        resolved = model_registry.dispatch_token(vendor, model, effort) or model
        return _ok(role, vendor, resolved, tokens)

    joined = ", ".join(tokens)
    return _park(
        role,
        vendor,
        f"model {model!r} is not on the {role}/{vendor} allowlist [{joined}] — " + _PARK_TAIL,
        allowlist=tokens,
    )


def _cli_check(args: argparse.Namespace) -> int:
    result = validate(args.role, args.vendor, args.model, args.effort)
    print(json.dumps(result))
    if not result["ok"]:
        print(result["reason"], file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dispatch model allowlist guard")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="Validate a dispatch against the allowlist")
    check.add_argument("--role", required=True)
    check.add_argument("--vendor", required=True)
    check.add_argument("--model", default=None)
    check.add_argument("--effort", default=None)
    check.set_defaults(func=_cli_check)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
