#!/usr/bin/env python3
"""Harness native project-context tripwire (#629 scope item 4).

Why this exists: issue #629 slimmed SessionStart bootstrap (`lib/session_context.assemble()`)
to inject only resolved plugin roots and the covenant. Project/user CLAUDE.md, the env block,
and MEMORY.md head are now left to the harness, which loads the project-context layer natively
on all spawn paths — plain chat, headless ``-p``, and slash-command spawn (probe-verified #627
F1 on Claude Code 2.1.219). That native auto-load is load-bearing: if a future harness upgrade
stops injecting the project layer on any spawn path, the slim bootstrap would silently lose it.
This probe converts that residual dependency into a named, re-runnable, watched risk.

When to run: on every Claude Code / harness upgrade (~30 seconds), and after updating the
superheroes plugin (especially on a harness older than the validated version).

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

PreCompact top-level ``additionalContext`` tripwire (#911):

Live-session procedure: wire a throwaway PreCompact hook that emits a top-level
``additionalContext`` instructing the summarizer to begin its summary with a unique token.
Run a session with enough turns to compact, invoke ``/compact``, then capture evidence and run::

    python3 lib/harness_probe.py --check-precompact <file> --precompact-token <token>

PASS (exit 0): no ``Hook JSON output validation failed`` in the evidence and the token appears
in the generated summary.

FAIL (exit 1): validation error present or token absent — TRIPWIRE FIRED.

Fallback when this tripwire fires: the SessionStart recovery block (issue #911 part 2) is the
durable backstop and keeps working; only summary shaping is lost.

Validated against Claude Code 2.1.219 (native layer) and 2.1.222 (PreCompact top-level key).
Stdlib-only.
"""
from __future__ import annotations

import argparse
import sys

NATIVE_LAYER_MARKER = "# claudeMd"
PRECOMPACT_VALIDATION_FAILURE = "Hook JSON output validation failed"

SPAWN_PATHS = ("plain chat", "headless -p", "slash-command spawn")

_VALIDATED_VERSION = "2.1.219"
_PRECOMPACT_VALIDATED_VERSION = "2.1.222"


def native_layer_present(context_text) -> bool:
    """True iff ``context_text`` contains a standalone heading line equal to the marker."""
    if not isinstance(context_text, str):
        return False
    return any(line.strip() == NATIVE_LAYER_MARKER for line in context_text.splitlines())


def precompact_evidence_passes(context_text, token) -> tuple[bool, str]:
    """Return (ok, reason) for PreCompact top-level additionalContext evidence."""
    if not isinstance(context_text, str):
        return False, "evidence is not text"
    if PRECOMPACT_VALIDATION_FAILURE in context_text:
        return False, f"found {PRECOMPACT_VALIDATION_FAILURE!r}"
    if not token:
        return False, "no --precompact-token supplied"
    if token not in context_text:
        return False, f"token {token!r} absent from evidence"
    return True, ""


def _procedure_text() -> str:
    paths = ", ".join(SPAWN_PATHS)
    return f"""Harness native project-context tripwire (Claude Code {_VALIDATED_VERSION})

WHEN: Run on every Claude Code / harness upgrade (~30s), and after updating the superheroes plugin (especially on a harness older than the validated version).

PROCEDURE — for each spawn path ({paths}):
  1. Start that kind of session in a superheroes-calibrated project.
  2. Confirm the harness injected a native project-context block (marker: {NATIVE_LAYER_MARKER!r}).
  3. Dump the relevant session context to a file.
  4. Run: python3 lib/harness_probe.py --check <file>

PASS (exit 0): marker present — harness dependency holds.
FAIL (exit 1): marker absent — TRIPWIRE FIRED; restore the dropped records (one-commit revert of the #629 slim commit).
"""


def _precompact_procedure_text() -> str:
    return f"""Harness PreCompact top-level additionalContext tripwire (Claude Code {_PRECOMPACT_VALIDATED_VERSION})

WHEN: Run on every Claude Code / harness upgrade (~30s), especially after a harness change to hook JSON validation or compaction.

PROCEDURE:
  1. Wire a throwaway PreCompact hook emitting a top-level additionalContext that instructs
     the summarizer to begin its summary with a unique token.
  2. Run a session with enough turns to compact; invoke /compact.
  3. Capture evidence (session log or summary dump) containing the compaction output.
  4. Run: python3 lib/harness_probe.py --check-precompact <file> --precompact-token <token>

PASS (exit 0): no {PRECOMPACT_VALIDATION_FAILURE!r} and token present in summary.
FAIL (exit 1): TRIPWIRE FIRED — SessionStart recovery block remains the durable backstop;
only summary shaping is lost.
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
    parser.add_argument(
        "--check-precompact",
        metavar="PATH",
        help="PreCompact evidence file to check ('-' = stdin).",
    )
    parser.add_argument(
        "--precompact-token",
        metavar="TOKEN",
        help="Expected unique token from the throwaway PreCompact hook (required with --check-precompact).",
    )
    args = parser.parse_args(argv)

    if args.check_precompact is not None:
        if not args.precompact_token:
            print("FAIL: --check-precompact requires --precompact-token")
            return 1
        try:
            if args.check_precompact == "-":
                context_text = sys.stdin.read()
            else:
                with open(args.check_precompact, encoding="utf-8", errors="replace") as fh:
                    context_text = fh.read()
        except OSError as exc:
            print(f"FAIL: cannot read evidence file {args.check_precompact!r}: {exc}")
            return 1
        ok, reason = precompact_evidence_passes(context_text, args.precompact_token)
        if ok:
            print(
                "PASS: PreCompact top-level additionalContext accepted and token present "
                "— harness dependency holds"
            )
            return 0
        print(
            "FAIL: PreCompact tripwire FIRED (%s); SessionStart recovery block remains "
            "the durable backstop — only summary shaping is lost" % reason
        )
        return 1

    if args.check is None:
        print(_procedure_text(), end="")
        print()
        print(_precompact_procedure_text(), end="")
        return 0

    try:
        if args.check == "-":
            context_text = sys.stdin.read()
        else:
            with open(args.check, encoding="utf-8", errors="replace") as fh:
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
