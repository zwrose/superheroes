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


# #310: external_dispatch outcomes that are a LEGITIMATE, VISIBLE fall-open reason — the
# owner's environment cannot run the engine (its CLI is absent, or the owner's settings deny
# the engine's Bash verb). A run that journals one of these has HONESTLY disclosed why it fell
# open to Claude (the "fall-open must be visible" principle, #288/#292/#299), so it does not
# fail the authenticity gate. EVERY other non-"ok" outcome (timeout, unreadable, commit-failed,
# could-not-stage-*, dispatch-error, an engine parse reason, a bare "failed") is a genuine
# dispatch FAILURE and counts against the tally. These clean markers are emitted by the spine's
# dispatch path (the #299 fall-open-visibility work); until then the only authentic path is an
# outcome of "ok". #308 adds a resolved `model` field to these payloads — this reader ignores
# unknown payload keys, so it extends without change.
ACCEPTABLE_FALLOPEN_OUTCOMES = frozenset({"authz-denied", "engine-unavailable"})


def tally_external_dispatches(events):
    """Pure tally of a run's `external_dispatch` journal events (#310).

    Returns `{"ok": int, "failed": int, "by_engine": {engine: {"ok": n, "total": m}},
    "acceptable_reasons": [outcome, ...]}` where `total` counts genuine dispatch ATTEMPTS
    (ok + failed) per engine, EXCLUDING the acceptable fall-open outcomes (authz-denied /
    engine-unavailable), which are recorded separately as visible, legitimate reasons — never
    as failures. Never raises: a non-dict event or payload contributes nothing.
    """
    ok = 0
    failed = 0
    by_engine = {}
    reasons = []
    for ev in events or []:
        if not isinstance(ev, dict) or ev.get("type") != "external_dispatch":
            continue
        payload = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
        outcome = payload.get("outcome")
        engine = payload.get("engine") or "external"
        if outcome in ACCEPTABLE_FALLOPEN_OUTCOMES:
            reasons.append(outcome)
            continue
        slot = by_engine.setdefault(engine, {"ok": 0, "total": 0})
        slot["total"] += 1
        if outcome == "ok":
            ok += 1
            slot["ok"] += 1
        else:
            failed += 1
    return {"ok": ok, "failed": failed, "by_engine": by_engine, "acceptable_reasons": reasons}


def _dispatch_tally_phrase(tally):
    """Human phrase naming the per-engine ok/total tallies for a FAIL reason, e.g.
    `external engines failed every dispatch: codex 0/8, cursor 0/2`. Zero attempts is the
    silent-fall-open shape."""
    by_engine = (tally or {}).get("by_engine") or {}
    if not by_engine:
        return "zero external_dispatch events were journaled (a silent fall-open to Claude)"
    parts = ", ".join("%s %d/%d" % (eng, d.get("ok", 0), d.get("total", 0))
                      for eng, d in sorted(by_engine.items()))
    return "external engines failed every dispatch: " + parts


def decide(facts):
    """Pure verdict over the assembled facts dict.

    Order of judgment:
      1. UFR-9 — any unreadable required fact fails, naming those facts (never a pass).
      2. FR-3 — each required fact must be present and true (terminal ready, PR exists +
         ready-for-review, checks green, every expected phase traversed, readout exists
         with a PR link).
      3. FR-4 — readout-vs-reality consistency: the readout's claimed checks-green and PR
         must match the live values.
      4. #310 engine authenticity — when the resolved calibration routed any role to an
         external engine (`external_calibration`), the run must show the external dispatch
         chain actually worked at least once: ≥1 `external_dispatch` with outcome "ok", OR an
         explicitly journaled fall-open reason (authz-denied / engine-unavailable). A run whose
         external engines failed every dispatch — or that journaled zero events under external
         calibration — is byte-identical to a healthy all-Claude run in every terminal fact
         above, so without this gate a silent/total fall-open certifies as a passing
         "external-engine" run (the 0.11.0 escape: 9 dispatches, all failed, passed). An
         unreadable dispatch journal (`external_dispatch_unreadable`) cannot certify authentic
         dispatch and fails here (UFR-9). Judged LAST so a run that already fails a terminal
         fact keeps that headline reason rather than being masked by the engine reason.
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

    # 4. #310 engine authenticity — only gates a run whose calibration routed a role
    # externally; an all-Claude run has no external chain to prove.
    if facts.get("external_calibration"):
        if facts.get("external_dispatch_unreadable"):
            return _fail(
                "external-engine calibration, but the run's external-dispatch journal was "
                "unreadable — an unreadable journal cannot certify an authentic external "
                "dispatch (UFR-9)")
        tally = facts.get("external_dispatch_tally") or {}
        if not (tally.get("ok") or tally.get("acceptable_reasons")):
            return _fail(
                "external-engine calibration, but no authentic external dispatch — "
                + _dispatch_tally_phrase(tally))

    return _pass()
