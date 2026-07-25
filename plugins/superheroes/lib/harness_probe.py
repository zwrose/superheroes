#!/usr/bin/env python3
"""Harness native project-context tripwire (#629 scope item 4).

Why this exists: issue #629 slimmed SessionStart bootstrap (`lib/session_context.assemble()`)
to inject only resolved plugin roots and the covenant. Project/user CLAUDE.md, the env block,
and MEMORY.md head are now left to the harness, which loads the project-context layer natively
on all spawn paths — plain chat, headless ``-p``, and slash-command spawn (probe-verified #627
F1 on Claude Code 2.1.219). That native auto-load is load-bearing: if a future harness upgrade
stops injecting the project layer on any spawn path, the slim bootstrap would silently lose it.
This probe converts that residual dependency into a named, re-runnable, watched risk.

When to run: on every Claude Code / harness upgrade (~30 seconds).

Live-session procedure (evidence is only observable inside a running session's context; it is
not persisted to session transcripts). For **each** of the three spawn paths — plain chat,
headless ``-p``, slash-command spawn — start that kind of session in a superheroes-calibrated
project and confirm the harness injected a native project-context block. The telltale marker is
the ``# claudeMd`` heading. The running agent dumps the relevant context to a file and runs::

    python3 lib/harness_probe.py --check <file>

PASS (exit 0): the marker is present; the harness dependency holds.

FAIL (exit 1): the marker is absent — TRIPWIRE FIRED; the harness may have stopped injecting
the native project layer on that spawn path.

Fallback when the tripwire fires: restore the dropped records via a one-commit revert of the
#629 slim commit (binding fail-direction for #629 — never silently drop context; prefer
duplication over absence).

Validated against Claude Code 2.1.219. Stdlib-only.
"""
from __future__ import annotations

import argparse
import sys

NATIVE_LAYER_MARKER = "# claudeMd"

SPAWN_PATHS = ("plain chat", "headless -p", "slash-command spawn")

_VALIDATED_VERSION = "2.1.219"


def native_layer_present(context_text) -> bool:
    """True iff the harness native project-context marker appears in ``context_text``."""
    if not isinstance(context_text, str):
        return False
    return NATIVE_LAYER_MARKER in context_text


def _procedure_text() -> str:
    paths = ", ".join(SPAWN_PATHS)
    return f"""Harness native project-context tripwire (Claude Code {_VALIDATED_VERSION})

WHEN: Run on every Claude Code / harness upgrade (~30s).

PROCEDURE — for each spawn path ({paths}):
  1. Start that kind of session in a superheroes-calibrated project.
  2. Confirm the harness injected a native project-context block (marker: {NATIVE_LAYER_MARKER!r}).
  3. Dump the relevant session context to a file.
  4. Run: python3 lib/harness_probe.py --check <file>

PASS (exit 0): marker present — harness dependency holds.
FAIL (exit 1): marker absent — TRIPWIRE FIRED; restore the dropped records (one-commit revert of the #629 slim commit).
"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Tripwire probe for harness native project-context injection (#629).",
    )
    parser.add_argument(
        "--check",
        metavar="PATH",
        help="Evidence file to check ('-' = stdin). Omit to print the live procedure.",
    )
    args = parser.parse_args(argv)

    if args.check is None:
        print(_procedure_text(), end="")
        return 0

    try:
        if args.check == "-":
            context_text = sys.stdin.read()
        else:
            with open(args.check, encoding="utf-8") as fh:
                context_text = fh.read()
    except OSError as exc:
        print(f"FAIL: cannot read evidence file {args.check!r}: {exc}")
        return 1

    if native_layer_present(context_text):
        print(
            "PASS: native project-context layer present (# claudeMd) — harness dependency holds"
        )
        return 0

    print(
        "FAIL: native project-context layer ABSENT — tripwire FIRED; "
        "restore the dropped records (one-commit revert of the #629 slim commit)"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
