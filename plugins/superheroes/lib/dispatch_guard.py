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

``validate`` lives in ``dispatch_allowlist``; this module re-exports it and hosts the CLI.
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
import dispatch_allowlist  # noqa: E402
import seat_bundle  # noqa: E402

validate = dispatch_allowlist.validate


def _cli_check(args: argparse.Namespace) -> int:
    resolved = seat_bundle.resolve_entry(args.seat, verb="guard-check")
    if not resolved.get("ok"):
        allowlist_verdict = resolved.get("allowlistVerdict")
        if isinstance(allowlist_verdict, dict):
            print(json.dumps(allowlist_verdict))
            print(allowlist_verdict.get("reason") or resolved.get("detail"), file=sys.stderr)
            return 1
        payload = {
            "ok": False,
            "role": None,
            "vendor": None,
            "model_id": None,
            "effort": None,
            "dispatch_token": None,
            "effort_source": None,
            "resolved_model": None,
            "allowlist": [],
            "allowlist_pairs": [],
            "reason": resolved.get("entryReason"),
            "seat_detail": resolved.get("detail"),
        }
        print(json.dumps(payload))
        print(resolved.get("detail") or resolved.get("entryReason"), file=sys.stderr)
        return 1
    result = dict(resolved["allowlistVerdict"])
    result["effort_source"] = resolved["effortSource"]
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
                    help="JSON seat bundle with vendor, model, effort, and role")
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
