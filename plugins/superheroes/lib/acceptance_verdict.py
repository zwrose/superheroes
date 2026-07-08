"""Verdict decider for the acceptance harness (FR-3 / FR-4 / UFR-9).

Pure `decide(facts)` over a plain dict assembled by the orchestrator from the run-outcome
plus live `gh` reads. Fail-CLOSED: a `pass` is emitted ONLY when every required fact is
present, true, and readable AND the readout-vs-reality consistency holds; any missing,
false, unreadable, or inconsistent fact yields a `fail` naming the first offending fact —
never a false pass. Never raises: a missing key is treated as its false/unreadable form.

Mirrors `preflight.decide` (pure, no I/O; all clock/gh/process reads live in the mechanical
layer and are injected as `facts`).
"""


def _pass():
    return {"verdict": "pass", "reason": "all required facts present, true, and consistent with reality"}


def _fail(reason):
    return {"verdict": "fail", "reason": reason}


def decide(facts):
    """Pure verdict over the assembled facts dict.

    Order of judgment:
      1. UFR-9 — any unreadable required fact fails, naming those facts (never a pass).
      2. FR-3 — each required fact must be present and true (terminal ready, PR exists +
         ready-for-review, checks green, every expected phase traversed, readout exists
         with a PR link).
      3. FR-4 — readout-vs-reality consistency: the readout's claimed checks-green and PR
         must match the live values.
    Otherwise: pass.
    """
    if not isinstance(facts, dict):
        facts = {}

    # 1. UFR-9: an unreadable required fact never contributes to a pass.
    unreadable = facts.get("unreadable") or []
    if unreadable:
        return _fail("unreadable required fact(s), cannot pass: %s" % ", ".join(unreadable))

    # 2. FR-3: required facts, in order — fail naming the first false/missing one.
    if facts.get("terminal") != "ready":
        return _fail("terminal outcome was %r, expected \"ready\"" % facts.get("terminal"))
    if not facts.get("pr_exists"):
        return _fail("no PR was created")
    if not facts.get("pr_ready_for_review"):
        return _fail("PR is not ready-for-review")
    if not facts.get("checks_green"):
        if facts.get("checks_pending"):
            # honest-reason (#212/#11 class): a settle wait that ran out is NOT a red —
            # never report a timed-out wait identically to a genuine CI failure.
            return _fail("checks still pending after the settle wait — never confirmed green")
        return _fail("checks are not green")

    expected = set(facts.get("expected_phases") or [])
    traversed = set(facts.get("phases_traversed") or [])
    if not expected <= traversed:
        missing = sorted(expected - traversed)
        return _fail("expected phase(s) not traversed: %s" % ", ".join(missing))

    if not facts.get("readout_exists"):
        return _fail("readout does not exist")
    if not facts.get("readout_pr_link"):
        return _fail("readout has no PR link")

    # 3. FR-4: readout-vs-reality consistency.
    if facts.get("readout_claimed_checks_green") != facts.get("live_checks_green"):
        return _fail(
            "readout's claimed checks-green (%r) is inconsistent with reality (%r)"
            % (facts.get("readout_claimed_checks_green"), facts.get("live_checks_green"))
        )
    if facts.get("readout_claimed_pr") != facts.get("live_pr"):
        return _fail(
            "readout's claimed PR (%r) is inconsistent with reality (%r)"
            % (facts.get("readout_claimed_pr"), facts.get("live_pr"))
        )

    # 4. #299 dispatch census: the run's ACTUAL engine/model dispatch must match the readout's
    # EXPECTED rows. A silent fall-open to Claude under an external calibration, or an off-policy /
    # Fable model, fails here (never a false pass). Absent / all-Claude -> {ok:True} -> no-op.
    census = facts.get("dispatch_census")
    if isinstance(census, dict) and census.get("ok") is False:
        return _fail("dispatch census diverged from the readout: %s"
                     % "; ".join(census.get("failures") or ["unspecified divergence"]))

    return _pass()
