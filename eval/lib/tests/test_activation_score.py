import activation_score as a

FIX = {"s1": {"should_fire": ["p1", "p2"], "should_not_fire": ["n1"]}}

def _obs(phrase, direction, results):
    return [{"skill": "s1", "phrase": phrase, "direction": direction, "run": i, "activated": r}
            for i, r in enumerate(results)]

def _clean():
    return (_obs("p1", "should_fire", [True, True]) + _obs("p2", "should_fire", [True, True])
            + _obs("n1", "should_not_fire", [False, False]))

def test_pass_when_every_phrase_clean():
    assert a.score(_clean(), FIX, {}, {})["s1"]["verdict"] == "pass"

def test_one_dead_should_fire_phrase_fails_the_direction():
    # p2 never activates across all runs -> direction fail, even though p1 is perfect
    obs = (_obs("p1", "should_fire", [True, True]) + _obs("p2", "should_fire", [False, False])
           + _obs("n1", "should_not_fire", [False, False]))
    assert a.score(obs, FIX, {}, {})["s1"]["verdict"] == "fail"

def test_intermittent_single_phrase_is_rerun_not_fail():
    obs = (_obs("p1", "should_fire", [True, False]) + _obs("p2", "should_fire", [True, True])
           + _obs("n1", "should_not_fire", [False, False]))
    assert a.score(obs, FIX, {}, {})["s1"]["verdict"] == "re-run"

def test_unobserved_phrase_is_fail():
    # p2 has no observations at all -> cannot claim pass
    obs = _obs("p1", "should_fire", [True, True]) + _obs("n1", "should_not_fire", [False, False])
    assert a.score(obs, FIX, {}, {})["s1"]["verdict"] == "fail"

def test_should_not_fire_overtrigger_is_not_lenient():
    obs = (_obs("p1", "should_fire", [True, True]) + _obs("p2", "should_fire", [True, True])
           + _obs("n1", "should_not_fire", [True, True]))
    assert a.score(obs, FIX, {}, {})["s1"]["verdict"] == "fail"

def test_fail_dominates_rerun():
    # one direction fails, the other is re-run -> skill verdict is fail (precedence)
    obs = (_obs("p1", "should_fire", [True, False]) + _obs("p2", "should_fire", [True, True])
           + _obs("n1", "should_not_fire", [True, True]))  # n1 persistent over-trigger -> fail
    assert a.score(obs, FIX, {}, {})["s1"]["verdict"] == "fail"

def test_no_fixtures_is_fail():
    assert a.score([], {"s2": {"should_fire": [], "should_not_fire": []}}, {}, {})["s2"]["verdict"] == "fail"

def test_carveout_lapses_when_skill_changed():
    baseline = {"carveOuts": {"s1": {"digest": "OLD"}}}
    obs = (_obs("p1", "should_fire", [False, False]) + _obs("p2", "should_fire", [False, False])
           + _obs("n1", "should_not_fire", [False, False]))
    # current digest differs from the carve-out's recorded digest -> carve-out lapses -> fail
    assert a.score(obs, FIX, baseline, {"s1": "NEW"})["s1"]["verdict"] == "fail"
    # digest matches -> carve-out applies
    assert a.score(obs, FIX, baseline, {"s1": "OLD"})["s1"]["verdict"] == "carved-out"
