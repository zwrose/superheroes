"""Turn recorded live-model activation observations into per-skill verdicts.

Deterministic given its inputs (the live-model non-determinism is upstream, in the
recorded observations). Scoring is PER PHRASE: a direction passes only when every
fixture phrase passes, so a single dead should_fire phrase fails the direction
(FR-1). The consensus + re-run rule applies independently per direction; a
should_not_fire over-trigger is held to the same bar as a should_fire miss, and
`fail` dominates `re-run`. Carve-outs (UFR-6) are keyed to a skill content digest
and lapse when it changes.
"""


def _phrase_result(runs, expect_activated):
    # runs: list of bools for one phrase. A phrase that was never observed is a fail
    # (you cannot claim a pass for a phrase you did not test).
    if not runs:
        return "fail"
    hits = sum(1 for activated in runs if activated == expect_activated)
    if hits == len(runs):
        return "pass"
    if hits == 0:
        return "fail"
    return "re-run"


def _direction_result(by_phrase, phrases, expect_activated):
    if not phrases:
        return "pass"  # direction with no fixture phrases is vacuously satisfied
    results = [_phrase_result(by_phrase.get(p, []), expect_activated) for p in phrases]
    if "fail" in results:
        return "fail"
    if "re-run" in results:
        return "re-run"
    return "pass"


def score(observations, fixtures, baseline, current_digests):
    by = {}
    for o in observations:
        by.setdefault((o["skill"], o["direction"], o["phrase"]), []).append(o["activated"])
    carve = (baseline or {}).get("carveOuts", {})
    result = {}
    for skill, fx in fixtures.items():
        if not fx.get("should_fire") and not fx.get("should_not_fire"):
            result[skill] = {"should_fire": "fail", "should_not_fire": "fail",
                             "verdict": "fail", "runs": 0, "notes": "no fixtures"}
            continue

        def phrases_for(direction):
            return {p: by.get((skill, direction, p), []) for p in fx.get(direction, [])}

        sf = _direction_result(phrases_for("should_fire"), fx.get("should_fire", []), True)
        snf = _direction_result(phrases_for("should_not_fire"), fx.get("should_not_fire", []), False)
        verdict = "pass"
        if "re-run" in (sf, snf):
            verdict = "re-run"
        if "fail" in (sf, snf):     # fail dominates re-run
            verdict = "fail"
        if verdict == "fail":
            c = carve.get(skill)
            if c and current_digests.get(skill) == c.get("digest"):
                verdict = "carved-out"  # pre-existing miss on an unchanged skill
        runs = max((len(v) for k, v in by.items() if k[0] == skill), default=0)
        result[skill] = {"should_fire": sf, "should_not_fire": snf,
                         "verdict": verdict, "runs": runs, "notes": ""}
    return result
