# Bite-proof record — each review record carries its session's own reviewer cost, `sessionCost` (#2307)

Detector file: `plugins/superheroes/lib/tests/test_review_record_session_cost_2307.py`, unedited between each red and its green. Every entry is a targeted, reversible edit to one production file (`plugins/superheroes/lib/review_record_session.py` or `plugins/superheroes/lib/review_record.py`), made and undone with the edit tool (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2307 -m pytest '<exact node id>' -q`, one test node each, output captured whole; the `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out of each capture, and the `tmp_path` directory names are as the runner printed them (no secret, token, URL or personal data appears in any capture, so nothing else is redacted). The seven guarded elements are the seven the order declared; none is grouped. Each target occurred exactly once in the edit's `old_string` (the edit tool refuses a non-unique match).

The detectors the entries name are the tests that carry a `# bite-proof:` line. The other tests in the file carry an `# axis:` line or a `bites on:` comment only; their elements are outside the declared set and are listed under *Not proven* below.

## 1. Nonce identity (`lib/review_record_session.py`, `_session_cost`)

- **Axis:** a run is counted once under its runner nonce, however many slots journal it and however many times its dir is listed.
- **Detector:** `test_review_record_session_cost_2307.py::test_t3_a_run_listed_twice_counts_once_with_its_figures`.
- **Neutralization:** `key = ("nonce", nonce) if nonce else ("slot", phase, r["round"], seat, r.get("occurrence", 0), r["attempt"])` became `key = ("slot", phase, r["round"], seat, r.get("occurrence", 0), r["attempt"])`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_t3_a_run_listed_twice_counts_once_with_its_figures ____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-3/test_t3_a_run_listed_twice_cou0')

    def test_t3_a_run_listed_twice_counts_once_with_its_figures(tmp_path):
        # axis: a run is one nonce, however many slots journal it and however many times its dir is listed
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2307_session_cost.md
        s = Session(tmp_path).seat("code-reviewer", nonce="n1").seat("security-reviewer", nonce="n1")
        rec = written(tmp_path, s.save(), {"n1": run("n1", 100, 120)}, dirs=["/run/n1", "/run/n1"])
>       assert rec["sessionCost"] == {"tokens": 100, "minutes": 2.0, "runs": 1, "runsWithoutFigure": 0, "complete": True,
                                      "bySeat": {"code-reviewer": {"tokens": 100, "minutes": 2.0, "runs": 1}}}
E       AssertionError: assert {'bySeat': {'...runs': 2, ...} == {'tokens': 10...gure': 0, ...}
E         
E         Omitting 2 identical items, use -vv to show
E         Differing items:
E         {'minutes': 4.0} != {'minutes': 2.0}
E         {'runs': 2} != {'runs': 1}
E         {'bySeat': {'code-reviewer': {'minutes': 2.0, 'runs': 1, 'tokens': 100}, 'security-reviewer': {'minutes': 2.0, 'runs': 1, 'tokens': 100}}} != {'bySeat': {'code-reviewer': {'tokens': 100, 'minutes': 2.0, 'runs': 1}}}
E         {'tokens': 200} != {'tokens': 100}
E         Use -v to get more diff

/home/user/wt-2307/plugins/superheroes/lib/tests/test_review_record_session_cost_2307.py:76: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_session_cost_2307.py::test_t3_a_run_listed_twice_counts_once_with_its_figures
1 failed in 3.70s
```

**Restore:** the inverse edit put the original `key = ("nonce", nonce) if nonce else ("slot", ...)` line back.
**Restore receipt** (the restored line, quoted from `review_record_session.py:222`): `        key = ("nonce", nonce) if nonce else ("slot", phase, r["round"], seat, r.get("occurrence", 0), r["attempt"])`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 3.46s
```

## 2. No-figure handling (`lib/review_record_session.py`, `_figure`)

- **Axis:** a run whose observation lacks tokens or wall time is a run, adds no figure, and counts in `runsWithoutFigure` (it is never a zero figure).
- **Detector:** `test_review_record_session_cost_2307.py::test_t4_a_run_without_a_figure_is_counted_and_adds_nothing[no-tokens]`.
- **Neutralization:** in `_figure`, `obs.get("tokens")` became `obs.get("tokens", 0)`, so a missing `tokens` counts as 0 with a figure.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_t4_a_run_without_a_figure_is_counted_and_adds_nothing[no-tokens] _____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-5/test_t4_a_run_without_a_figure0')
obs = {'wallSeconds': 60}

    @pytest.mark.parametrize("obs", [
        {"wallSeconds": 60},                       # no tokens
        {"tokens": 5},                             # no wall time
        {"tokens": True, "wallSeconds": 60},       # a bool is no count
        {"tokens": 5, "wallSeconds": True},
        {"tokens": -1, "wallSeconds": 60},         # negative
        {"tokens": 5, "wallSeconds": -1},
        "not-a-dict",
    ], ids=["no-tokens", "no-wall", "bool-tokens", "bool-wall", "neg-tokens", "neg-wall", "no-observation"])
    def test_t4_a_run_without_a_figure_is_counted_and_adds_nothing(tmp_path, obs):
        # axis: a run lacking tokens or wall time counts as a run, adds no figure, and makes the cost incomplete
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2307_session_cost.md
        s = Session(tmp_path).seat("code-reviewer", nonce="n1").seat("security-reviewer", nonce="n2")
        rec = written(tmp_path, s.save(), {"n1": run("n1", 100, 120), "n2": run("n2", obs=obs)})
>       assert rec["sessionCost"] == {
            "tokens": 100, "minutes": 2.0, "runs": 2, "runsWithoutFigure": 1, "complete": False,
            "bySeat": {"code-reviewer": {"tokens": 100, "minutes": 2.0, "runs": 1},
                       "security-reviewer": {"tokens": 0, "minutes": 0.0, "runs": 1}}}
E       AssertionError: assert {'bySeat': {'...runs': 2, ...} == {'tokens': 10...gure': 1, ...}
E         
E         Omitting 2 identical items, use -vv to show
E         Differing items:
E         {'complete': True} != {'complete': False}
E         {'bySeat': {'code-reviewer': {'minutes': 2.0, 'runs': 1, 'tokens': 100}, 'security-reviewer': {'minutes': 1.0, 'runs': 1, 'tokens': 0}}} != {'bySeat': {'code-reviewer': {'tokens': 100, 'minutes': 2.0, 'runs': 1}, 'security-reviewer': {'tokens': 0, 'minutes': 0.0, 'runs': 1}}}
E         {'minutes': 3.0} != {'minutes': 2.0}
E         {'runsWithoutFigure': 0} != {'runsWithoutFigure': 1}
E         Use -v to get more diff

/home/user/wt-2307/plugins/superheroes/lib/tests/test_review_record_session_cost_2307.py:94: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_session_cost_2307.py::test_t4_a_run_without_a_figure_is_counted_and_adds_nothing[no-tokens]
1 failed in 3.39s
```

**Restore:** the inverse edit put `obs.get("tokens")` back.
**Restore receipt** (the restored line, quoted from `review_record_session.py:198`): `    t, w = (obs.get("tokens"), obs.get("wallSeconds")) if isinstance(obs, dict) else (None, None)`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 3.38s
```

## 3. All-attempts population (`lib/review_record_session.py`, `_session_cost`)

- **Axis:** every attempt of a slot is a run the session dispatched; a superseded attempt still cost.
- **Detector:** `test_review_record_session_cost_2307.py::test_t9_a_superseded_attempt_still_counts`.
- **Neutralization:** the loop `for r in rows:` in `_session_cost` became `for r in [v[1] for v in _slots(rows).values()]:`, so only the highest attempt of each slot is read.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_t9_a_superseded_attempt_still_counts ___________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-7/test_t9_a_superseded_attempt_s0')

    def test_t9_a_superseded_attempt_still_counts(tmp_path):
        # axis: every attempt of a slot is a run the session dispatched
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2307_session_cost.md
        s = Session(tmp_path).seat("code-reviewer", attempt=0, nonce="n1").seat("code-reviewer", attempt=1, nonce="n2")
        rec = written(tmp_path, s.save(), {"n1": run("n1", 100, 60), "n2": run("n2", 200, 120)})
>       assert rec["sessionCost"] == {"tokens": 300, "minutes": 3.0, "runs": 2, "runsWithoutFigure": 0, "complete": True,
                                      "bySeat": {"code-reviewer": {"tokens": 300, "minutes": 3.0, "runs": 2}}}
E       AssertionError: assert {'bySeat': {'...runs': 1, ...} == {'tokens': 30...gure': 0, ...}
E         
E         Omitting 2 identical items, use -vv to show
E         Differing items:
E         {'bySeat': {'code-reviewer': {'minutes': 2.0, 'runs': 1, 'tokens': 200}}} != {'bySeat': {'code-reviewer': {'tokens': 300, 'minutes': 3.0, 'runs': 2}}}
E         {'runs': 1} != {'runs': 2}
E         {'tokens': 200} != {'tokens': 300}
E         {'minutes': 2.0} != {'minutes': 3.0}
E         Use -v to get more diff

/home/user/wt-2307/plugins/superheroes/lib/tests/test_review_record_session_cost_2307.py:192: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_session_cost_2307.py::test_t9_a_superseded_attempt_still_counts
1 failed in 3.65s
```

**Restore:** the inverse edit put `for r in rows:` back.
**Restore receipt** (the restored lines, quoted from `review_record_session.py:209-210`): `    runs, seats = {}, {}` / `    for r in rows:`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 3.89s
```

## 4. Synthesis included (`lib/review_record_session.py`, `_session_cost`)

- **Axis:** a `dispatch-synthesis` row is a review-kind run and counts, under `synthesis <seat>`.
- **Detector:** `test_review_record_session_cost_2307.py::test_t10_a_synthesis_run_counts_under_its_own_name`.
- **Neutralization:** the population condition `or r.get("cmd") not in _INGEST_CMDS:` became `or r.get("cmd") not in _INGEST_CMDS or phase == "dispatch-synthesis":`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_t10_a_synthesis_run_counts_under_its_own_name ______________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-9/test_t10_a_synthesis_run_count0')

    def test_t10_a_synthesis_run_counts_under_its_own_name(tmp_path):
        # axis: the synthesis seat is a reviewer run and costs like one
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2307_session_cost.md
        s = Session(tmp_path).seat("code-reviewer", nonce="n1").seat("grouper", phase="dispatch-synthesis", nonce="n2")
        rec = written(tmp_path, s.save(), {"n1": run("n1", 100, 60), "n2": run("n2", 40, 30)})
>       assert rec["sessionCost"]["bySeat"] == {"code-reviewer": {"tokens": 100, "minutes": 1.0, "runs": 1},
                                                "synthesis grouper": {"tokens": 40, "minutes": 0.5, "runs": 1}}
E       AssertionError: assert {'code-review...tokens': 100}} == {'code-review...5, 'runs': 1}}
E         
E         Omitting 1 identical items, use -vv to show
E         Right contains 1 more item:
E         {'synthesis grouper': {'minutes': 0.5, 'runs': 1, 'tokens': 40}}
E         Use -v to get more diff

/home/user/wt-2307/plugins/superheroes/lib/tests/test_review_record_session_cost_2307.py:201: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_session_cost_2307.py::test_t10_a_synthesis_run_counts_under_its_own_name
1 failed in 3.24s
```

**Restore:** the inverse edit removed the added `or phase == "dispatch-synthesis"`.
**Restore receipt** (the restored line, quoted from `review_record_session.py:215`): `                or r.get("cmd") not in _INGEST_CMDS:`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 3.32s
```

## 5. Seat-key showing (`lib/review_record.py`, `_shown_session_cost`)

- **Axis:** a `bySeat` key the record's own detector would hide is shown as `[REDACTED SEAT]` with its figures kept; without it the scrubber replaces the key and its whole value.
- **Detector:** `test_review_record_session_cost_2307.py::test_t12_a_secret_shaped_seat_key_is_shown_redacted_with_its_figures`.
- **Neutralization:** the last line of `_shown_session_cost`, `return dict(cost, bySeat=out)`, became `return cost`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_t12_a_secret_shaped_seat_key_is_shown_redacted_with_its_figures _____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-11/test_t12_a_secret_shaped_seat_0')

    def test_t12_a_secret_shaped_seat_key_is_shown_redacted_with_its_figures(tmp_path):
        # axis: a seat key the scrubber would hide is shown neutrally and keeps its figures
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2307_session_cost.md
        secret_seat = "to" + "ken.py::t@L3"
        s = Session(tmp_path, rounds={"1": {}, "2": {}})
        s.seat("code-reviewer", nonce="n1").seat(secret_seat, phase="dispatch-audits", rnd=2, head=HEAD, nonce="n2")
        rec = written(tmp_path, s.save(), {"n1": run("n1", 100, 60), "n2": run("n2", 300, 30)})
>       assert rec["sessionCost"]["bySeat"] == {"code-reviewer": {"tokens": 100, "minutes": 1.0, "runs": 1},
                                                "[REDACTED SEAT]": {"tokens": 300, "minutes": 0.5, "runs": 1}}
E       AssertionError: assert {'[REDACTED K...tokens': 100}} == {'code-review...5, 'runs': 1}}
E         
E         Omitting 1 identical items, use -vv to show
E         Left contains 1 more item:
E         {'[REDACTED KEY]': '[REDACTED]'}
E         Right contains 1 more item:
E         {'[REDACTED SEAT]': {'minutes': 0.5, 'runs': 1, 'tokens': 300}}
E         Use -v to get more diff

/home/user/wt-2307/plugins/superheroes/lib/tests/test_review_record_session_cost_2307.py:228: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_session_cost_2307.py::test_t12_a_secret_shaped_seat_key_is_shown_redacted_with_its_figures
1 failed in 3.59s
```

**Restore:** the inverse edit put `return dict(cost, bySeat=out)` back.
**Restore receipt** (the restored line, quoted from `review_record.py:1808`): `    return dict(cost, bySeat=out)`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 3.44s
```

## 6. Validator `complete` check (`lib/review_record.py`, `_validate`)

- **Axis:** `sessionCost.complete` is true exactly when `runsWithoutFigure == 0`; an account that says otherwise is `review-account-invalid` naming `sessionCost.complete`.
- **Detector:** `test_review_record_session_cost_2307.py::test_t13_the_validator_refuses_a_malformed_session_cost_and_posts_nothing[complete-disagrees]`.
- **Neutralization:** `chk(c["complete"] is (c["runsWithoutFigure"] == 0), "sessionCost.complete")` became `chk(True, "sessionCost.complete")`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t13_the_validator_refuses_a_malformed_session_cost_and_posts_nothing[complete-disagrees] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-13/test_t13_the_validator_refuses0')
cost = {'tokens': 10, 'minutes': 1.0, 'runs': 1, 'runsWithoutFigure': 0, ...}
detail = 'sessionCost.complete'

    @pytest.mark.parametrize("cost,detail", [(c, d) for _, c, d in BAD], ids=[i for i, _, _ in BAD])
    def test_t13_the_validator_refuses_a_malformed_session_cost_and_posts_nothing(tmp_path, cost, detail):
        # axis: a malformed sessionCost is review-account-invalid, naming the path, and nothing is posted
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2307_session_cost.md
        fake = trr.Fake()
        out = rr.write(trr.put(tmp_path, trr.account(sessionCost=cost)), str(tmp_path), fake.readers())
>       assert out["ok"] is False and out["reason"] == "review-account-invalid" and out["detail"] == detail, out
E       AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/1', 'parts': 0, ...}
E       assert (True is False)

/home/user/wt-2307/plugins/superheroes/lib/tests/test_review_record_session_cost_2307.py:267: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_session_cost_2307.py::test_t13_the_validator_refuses_a_malformed_session_cost_and_posts_nothing[complete-disagrees]
1 failed in 3.62s
```

**Restore:** the inverse edit put the original `chk(...)` back.
**Restore receipt** (the restored line, quoted from `review_record.py:836`): `        chk(c["complete"] is (c["runsWithoutFigure"] == 0), "sessionCost.complete")`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 3.29s
```

## 7. Record carry (`lib/review_record.py`, `build_record`'s `rec = {...}`)

- **Axis:** the record carries `sessionCost` exactly when the account has it.
- **Detector:** `test_review_record_session_cost_2307.py::test_t1_a_two_round_session_sums_exactly_its_three_runs`.
- **Neutralization:** `**({"sessionCost": _shown_session_cost(a["sessionCost"])} if "sessionCost" in a else {}),` became `**{},`, so the account's cost never reaches the record.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_t1_a_two_round_session_sums_exactly_its_three_runs ____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-15/test_t1_a_two_round_session_su0')

    def test_t1_a_two_round_session_sums_exactly_its_three_runs(tmp_path):
        # axis: the record carries the session's whole reviewer cost
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2307_session_cost.md
        session, _, _ = fix_session(tmp_path)  # two panel seats in round 1 at EARLIER, an audit in round 2 at HEAD
        rec = written(tmp_path, session, {"n1": run("n1", 100, 60), "n2": run("n2", 200, 120), "n3": run("n3", 300, 30)})
>       assert rec["sessionCost"] == {
               ^^^^^^^^^^^^^^^^^^
            "tokens": 600, "minutes": 3.5, "runs": 3, "runsWithoutFigure": 0, "complete": True,
            "bySeat": {"code-reviewer": {"tokens": 100, "minutes": 1.0, "runs": 1},
                       "security-reviewer": {"tokens": 200, "minutes": 2.0, "runs": 1},
                       f"audits {KEY}": {"tokens": 300, "minutes": 0.5, "runs": 1}}}
E       KeyError: 'sessionCost'

/home/user/wt-2307/plugins/superheroes/lib/tests/test_review_record_session_cost_2307.py:46: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_session_cost_2307.py::test_t1_a_two_round_session_sums_exactly_its_three_runs
1 failed in 3.22s
```

**Restore:** the inverse edit put the original `**({"sessionCost": ...} if "sessionCost" in a else {}),` line back.
**Restore receipt** (the restored line, quoted from `review_record.py:1630`): `        **({"sessionCost": _shown_session_cost(a["sessionCost"])} if "sessionCost" in a else {}),`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 3.48s
```

## Not proven (outside the declared set)

These tests carry no neutralization of their own; they are listed so nobody reads them as covered by this record: T2 (a carried row never counts), T4's other six parametrized cases (bool, negative and non-dict observations), T4b (a raising engine record, a non-dict one, a nonce claimed by two dirs), T5 (per-seat sums), T6 and T6b (no reviewer; the hand-submit rule), T7 (the size trim leaves `sessionCost` alone), T8 (a rewrite keeps earlier heads' runs), T11 (a nonce-less missing or advanced slot is not a run), T12b (distinct redacted keys) and the other twelve T13 cases.
