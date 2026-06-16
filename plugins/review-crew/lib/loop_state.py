#!/usr/bin/env python3
"""The deterministic loop-continuation gate — decides the ONE mandatory next action.

review-crew's loops (review-code's auto-fix loop; the review-plan/spec/tasks revise loops)
re-review until no blocking findings remain. That continuation decision used to be prose the
orchestrator executed — and a model rationalizes past prose ("this fix is trivial", "the
next round will be clean", "I'll offer it as optional", "save the tokens"), exiting early
and shipping unverified fixes. `circuit_breaker.py` already takes the *halt* decision out of
the model's hands; this takes the symmetric *continue* decision out too.

The invariant: **if a fix was applied to a blocking (Critical/Important) finding this round,
another review round is MANDATORY — to verify the fix actually resolved it and introduced
nothing new.** There is deliberately NO "exit because I believe it's clean" branch in the
output: the model OBEYS the action, it does not decide it.

Actions (stdout JSON `{action, mandatory, reason}`):
  - `review`        — a blocking fix landed; re-review from scratch. MANDATORY.
  - `exit_clean`    — no blocking fix applied and none skipped; the loop is done.
  - `exit_skipped`  — no blocking finding addressed, but blocking finding(s) were deliberately
                      skipped; exit CLEAN-EXCEPT-FOR-SKIPPED (report them, not plain success).
  - `halt`          — the circuit breaker halted, or the round cap was hit with blocking
                      findings still being addressed.

The blocking counts can be passed explicitly OR derived from the round artifacts so the
model can't self-report them: review-code passes `--fix-batch` (+ `--resolutions`); the
revise loops pass `--compiled` (+ `--skipped-blocking`). stdlib only.
"""
import argparse
import json
import sys

_BLOCKING = ("Critical", "Important")


def _count_blocking(findings):
    return sum(1 for f in findings if f.get("severity") in _BLOCKING)


def _blocking_fixed_from_fix_batch(path):
    """fix-batch.json is the array of findings handed to the fixer this round."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    findings = data if isinstance(data, list) else data.get("findings", [])
    return _count_blocking(findings)


def _skipped_blocking_from_resolutions(path):
    """resolutions.json: { resolutions: [{action, severity}] }; count skipped blockers."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return sum(1 for r in data.get("resolutions", [])
               if r.get("action") == "skip" and r.get("severity") in _BLOCKING)


def _blocking_present_from_compiled(path):
    """compiled.json: { findings: [{severity}] }; count blocking findings present this round.
    Used by the revise loops (which have no fix-batch) so their continue count is derived
    from the agents' findings, not self-reported by the orchestrator."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    findings = data if isinstance(data, list) else data.get("findings", [])
    return _count_blocking(findings)


def decide(blocking_fixed, skipped_blocking, rnd, max_rounds, breaker_halt):
    """Pure decision. Returns (action, mandatory, reason)."""
    if breaker_halt:
        return ("halt", True,
                "circuit breaker halted (stuck / recurrence) — stop and report the still-open "
                "findings and the commit range; do not loop further.")
    if blocking_fixed > 0:
        if rnd >= max_rounds:
            return ("halt", True,
                    "round cap (%d) reached with blocking fixes still landing — REPORT the open "
                    "findings; do NOT declare success." % max_rounds)
        return ("review", True,
                "MANDATORY: %d blocking (Critical/Important) finding(s) were addressed this "
                "round — re-review from scratch to verify they resolved and introduced nothing "
                "new. You may NOT exit, declare success, or offer the next round as 'optional'. "
                "The loop exists to verify fixes; your confidence that 'it is clean' is exactly "
                "what this gate overrides." % blocking_fixed)
    # No blocking finding was addressed this round (none present, or all skipped).
    if skipped_blocking > 0:
        return ("exit_skipped", False,
                "no blocking finding addressed; %d blocking finding(s) were deliberately "
                "skipped — exit CLEAN-EXCEPT-FOR-SKIPPED: list the skipped blocker(s); do not "
                "report a plain success." % skipped_blocking)
    return ("exit_clean", False,
            "no blocking findings to address and none skipped — the loop is genuinely done; "
            "exit SUCCESS.")


def main(argv):
    ap = argparse.ArgumentParser(description="deterministic loop-continuation gate (review-crew)")
    ap.add_argument("--round", type=int, required=True, dest="rnd")
    ap.add_argument("--max-rounds", type=int, default=7)
    ap.add_argument("--breaker-halt", choices=["yes", "no"], default="no")
    # blocking-fixed: explicit, or derived from an artifact — review-code from its fix-batch
    # (already excludes skipped); the revise loops from compiled.json (blocking present minus
    # the blockers they skipped). Deriving it means the count is NOT self-reported.
    ap.add_argument("--blocking-fixed", type=int, default=None)
    ap.add_argument("--fix-batch", default=None, help="round-<N>/fix-batch.json (review-code: derives blocking-fixed)")
    ap.add_argument("--compiled", default=None, help="compiled.json (revise loops: derives blocking present this round)")
    # skipped-blocking: explicit, or derived from the resolutions artifact.
    ap.add_argument("--skipped-blocking", type=int, default=None)
    ap.add_argument("--resolutions", default=None, help="round-<N>/resolutions.json (derives skipped-blocking)")
    args = ap.parse_args(argv[1:])

    try:
        # Skipped count first — the --compiled derivation of blocking-fixed depends on it.
        if args.skipped_blocking is not None:
            skipped_blocking = args.skipped_blocking
        elif args.resolutions is not None:
            skipped_blocking = _skipped_blocking_from_resolutions(args.resolutions)
        else:
            skipped_blocking = 0

        if args.blocking_fixed is not None:
            blocking_fixed = args.blocking_fixed
        elif args.fix_batch is not None:
            blocking_fixed = _blocking_fixed_from_fix_batch(args.fix_batch)
        elif args.compiled is not None:
            # revise loops: every effective blocker present this round was revised, so the
            # count addressed = blockers present minus the ones skipped.
            blocking_fixed = max(0, _blocking_present_from_compiled(args.compiled) - skipped_blocking)
        else:
            blocking_fixed = 0  # nothing addressed this round (e.g. everything skipped)
    except (OSError, ValueError, TypeError, AttributeError, KeyError, json.JSONDecodeError) as exc:
        # Fail SAFE toward more review, never toward a silent exit — a malformed or wrong-shape
        # artifact must not let the loop slip out early.
        sys.stdout.write(json.dumps({
            "action": "review", "mandatory": True,
            "reason": "could not read the round artifacts (%s) — defaulting to another review "
                      "round rather than risk a premature exit." % exc}) + "\n")
        return 0

    action, mandatory, reason = decide(blocking_fixed, skipped_blocking,
                                       args.rnd, args.max_rounds, args.breaker_halt == "yes")
    sys.stdout.write(json.dumps({"action": action, "mandatory": mandatory, "reason": reason}) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
