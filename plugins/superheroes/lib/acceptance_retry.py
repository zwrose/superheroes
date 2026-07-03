"""Retry classifier for the acceptance harness (FR-9 / UFR-9).

Pure `classify(failure_facts)` over a plain dict: judges whether a failed live run may be
retried once. A retry is offered ONLY for a confidently-environmental failure on the first
attempt — infrastructure noise the run under test did not cause (the check-runner erroring
before it ran, the host being unreachable). Behavioral failures (the showrunner parked on a
blocking review, or a red check on its own change) are the run's own verdict and NEVER
retry. Anything unclassifiable is treated as behavioral (fail-closed: never an unwarranted
retry).

Fail-CLOSED on unreadability (UFR-9): if the failure facts could not be read, the failure is
`unconfirmable` and never justifies a retry — an unreadable fact can never contribute to a
retry decision. A second attempt (`attempt >= 2`) never retries again, capping the harness at
one retry.

Mirrors `preflight.decide` / `acceptance_ceiling.decide` (pure, no I/O; every fact is
injected as `failure_facts`). Never raises.
"""

# Failure kinds that are confidently INFRASTRUCTURE, not the run's own behavior. A first
# attempt that failed this way is safe to retry once. Everything not in this set is
# behavioral (the run's own verdict) or unclassifiable — neither retries.
_ENVIRONMENTAL = frozenset({
    "check-runner-errored-before-running",
    "host-unreachable",
})


def classify(failure_facts):
    """Pure retry judgment over the injected `failure_facts` dict.

    Returns `{"retry": bool, "class": "environmental"|"behavioral"|"unconfirmable",
    "reason": str}`.

    `retry: True` only for a confidently-environmental first-attempt failure. Unreadable
    facts (fail-closed) and second attempts never retry; every other failure is behavioral.
    """
    if not isinstance(failure_facts, dict):
        failure_facts = {}

    # UFR-9: an unreadable fact can never justify a retry (fail-closed).
    if failure_facts.get("unreadable"):
        return {
            "retry": False,
            "class": "unconfirmable",
            "reason": "failure facts were unreadable; fail-closed, no retry",
        }

    # One retry cap: a second attempt never retries again.
    attempt = failure_facts.get("attempt", 1)
    if attempt >= 2:
        return {
            "retry": False,
            "class": "behavioral",
            "reason": "already on attempt %s; the one retry is spent" % attempt,
        }

    kind = failure_facts.get("kind")
    if kind in _ENVIRONMENTAL:
        return {
            "retry": True,
            "class": "environmental",
            "reason": "confidently-environmental first-attempt failure (%s); retry once" % kind,
        }

    # Behavioral (parked / red check) or unclassifiable — the run's own verdict, no retry.
    return {
        "retry": False,
        "class": "behavioral",
        "reason": "failure kind %r is behavioral or unclassifiable; no retry" % (kind,),
    }
