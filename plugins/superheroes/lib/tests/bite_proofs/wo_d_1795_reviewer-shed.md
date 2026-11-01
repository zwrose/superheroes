# wo_d_1795_reviewer-shed — the review record sheds reviewer detail to fit, and never sheds the decision

> Note (2026-10-31, #2296): owner-machine paths and the name of a consuming project in this record were replaced with neutral placeholders after capture; nothing else changed.

Per-element bite-proof for the reviewer shed steps in `render` (`plugins/superheroes/lib/review_record.py`). Declared
guarded-element set (from the work order): **K1** the reviewer steps run; **K2** the shed line is present; **K3** the
never-shed census; **K4** the refusal after the last step. Each element was neutralized with one targeted edit, its
single test node ran alone and went red, the edit was undone by the inverse edit, the restored line was quoted back,
and the same node ran green. No test file was edited between a red and its green.

Command for every run (never `-k`, never filtered):

```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest '<file>::<test>' -q
```

`T` = `plugins/superheroes/lib/tests/test_review_record.py`. Redaction: none needed.

| ID | Guarded element | Axis | Neutralization | Node | Red |
|---|---|---|---|---|---|
| K1 | `render`, the `for name, step in _REVIEWER_STEPS:` loop | the reviewer steps run while the body is over the cap | the iterable → `()` | `T::test_a_long_session_sheds_reviewer_detail_to_fit_and_says_so` | `review_record.Refusal: ('review-record-too-large', '73403 characters')` |
| K2 | `compose`, the shed line | the line is present whenever a reviewer step ran | `if r.get("reviewerShed") else []` → `if False else []` | same node | `assert (0 == 1)` on the shed line count |
| K3 | the never-shed census | no shed step may empty a decision field | an added first step in `_REVIEWER_STEPS` that empties `whatIsMissing` | `T::test_a_never_shed_census_of_the_decision_content_over_a_shed_record` | `assert [] == ['security-re...ling canon-7']` |
| K4 | `render`, the final `raise Refusal(...)` | a body still over the cap after every step is refused, never truncated | the `raise` line → `pass` | `T::test_a_record_that_cannot_fit_after_every_step_is_refused_not_truncated` | `Failed: DID NOT RAISE Refusal` |

K1 and K2 share one node because the one test pins both (the steps run, and the line says so); each neutralization
reddens it on its own axis (K1 on the size refusal, K2 on the missing line). K3 was picked as the added step that
empties `whatIsMissing` (the alternative, blanking a finding's `outcome`, was not run). The added step is placed
first in the ladder so it runs on the fixture (a step placed after the two real ones would never execute, because
the first real step already fits the body).

## K1 — the reviewer steps run

Neutralization: `review_record.py` line 865, `    for name, step in _REVIEWER_STEPS:` → `    for name, step in ():`.

Raw red — **incomplete**: this one run was piped through `tail -40` by mistake, so only the last 40 lines were
kept, and the head of the output (the test source and the first lines of the traceback) was not captured. The
decisive end of the traceback, as printed:

```
        # Then, still over the cap, the reviewers' evidence detail, one step at a time, each said on the record.
        # axis: the reviewer steps run while the body is over the cap — see bite-proof record wo_d_1795_reviewer-shed
        for name, step in ():
            if len(body) <= MAX_BODY_CHARS:
                break
            r = dict(step(r), reviewerShed=name)
            body = compose(r)
        # axis: a body still over the cap after every step is refused, never truncated — see bite-proof record wo_d_1795_reviewer-shed
        if len(body) > MAX_BODY_CHARS:
>           raise Refusal("review-record-too-large", f"{len(body)} characters")
E           review_record.Refusal: ('review-record-too-large', '73403 characters')

/path/to/home/.superheroes-worktrees/superheroes/issue-1713-92994e7f22aa2a28/plugins/superheroes/lib/review_record.py:872: Refusal
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_a_long_session_sheds_reviewer_detail_to_fit_and_says_so
1 failed in 0.26s
```

Restore: `    for name, step in ():` → `    for name, step in _REVIEWER_STEPS:`. Restored line quoted back (line 865):
`    for name, step in _REVIEWER_STEPS:`.

Raw green:

```
.                                                                        [100%]
1 passed in 0.33s
```

## K2 — the shed line is present

Neutralization: `review_record.py` line 846, `              if r.get("reviewerShed") else [])]` →
`              if False else [])]`.

Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_a_long_session_sheds_reviewer_detail_to_fit_and_says_so _________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x10741c9e0>

    def test_a_long_session_sheds_reviewer_detail_to_fit_and_says_so(monkeypatch):
        # axis: the reviewer shed steps and the shed line; a long session refused for size, or trimmed without saying so
        rec = _long_session()
        assert _unshed_size(rec, monkeypatch) > rr.MAX_BODY_CHARS
        body = rr.render(rec)
        assert len(body) <= rr.MAX_BODY_CHARS
        lines = body.split("\n")
        shed = SHED_LINE % "engine telemetry"
>       assert lines.count(shed) == 1 and sum(l.startswith("Reviewer detail trimmed") for l in lines) == 1
E       assert (0 == 1)
E        +  where 0 = <built-in method count of list object at 0x108b87280>("Reviewer detail trimmed to fit this comment (engine telemetry); each reviewer's full output is in its raw-output comment linked under rawOutputs.")
E        +    where <built-in method count of list object at 0x108b87280> = ['<!-- superheroes:review-record -->', '**Review record: not reviewed.** Checked: CI on bbbbbbb: green; Reviewers that... names no repository, so its risk areas were not read.', 'CI on the final commit bbbbbbb: green (GitHub checks).', ...].count

/path/to/home/.superheroes-worktrees/superheroes/issue-1713-92994e7f22aa2a28/plugins/superheroes/lib/tests/test_review_record.py:1814: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_a_long_session_sheds_reviewer_detail_to_fit_and_says_so
1 failed in 0.35s
```

Restore: `              if False else [])]` → `              if r.get("reviewerShed") else [])]`. Restored line quoted
back (line 846): `              if r.get("reviewerShed") else [])]`.

Raw green:

```
.                                                                        [100%]
1 passed in 0.25s
```

## K3 — the never-shed census

Neutralization: `review_record.py` line 805,
`_REVIEWER_STEPS = (("observation", _shed_observation), ("runDir", _shed_run_dir))` →
`_REVIEWER_STEPS = (("observation", lambda r: dict(r, whatIsMissing=[])), ("observation", _shed_observation), ("runDir", _shed_run_dir))`
(an added first step that empties `whatIsMissing`; the two real steps still run, so the body still fits and
the red is on the census, not on the size refusal).

Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_a_never_shed_census_of_the_decision_content_over_a_shed_record ______

    def test_a_never_shed_census_of_the_decision_content_over_a_shed_record():
        # axis: the never-shed set; a shed step emptying the status, a missing line, an outcome or reason, a go-ahead or a row's identity
        rec = _long_session()
        posted = rr._parse_body(rr.render(rec))
        assert "reviewerShed" in posted
        assert rec["whatIsMissing"] and rec["missingReviews"] == [{"name": "security-reviewer", "goAhead": RULING}]
        assert posted["status"] == rec["status"] == "not-reviewed"
>       assert posted["whatIsMissing"] == rec["whatIsMissing"]
E       AssertionError: assert [] == ['security-re...ling canon-7']
E         
E         Right contains one more item: 'security-reviewer did not run; go-ahead: standing ruling canon-7'
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-1713-92994e7f22aa2a28/plugins/superheroes/lib/tests/test_review_record.py:1830: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_a_never_shed_census_of_the_decision_content_over_a_shed_record
1 failed in 0.23s
```

Restore: the line → `_REVIEWER_STEPS = (("observation", _shed_observation), ("runDir", _shed_run_dir))`. Restored line quoted back
(line 805): `_REVIEWER_STEPS = (("observation", _shed_observation), ("runDir", _shed_run_dir))`.

Raw green:

```
.                                                                        [100%]
1 passed in 0.21s
```

## K4 — the refusal after the last step

Neutralization: `review_record.py` line 872,
`        raise Refusal("review-record-too-large", f"{len(body)} characters")` → `        pass` (the `render` one; the
`render_raw` raise is a different line and was not touched).

Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_a_record_that_cannot_fit_after_every_step_is_refused_not_truncated ____

    def test_a_record_that_cannot_fit_after_every_step_is_refused_not_truncated():
        # axis: the refusal after the last shed step; a body still over the cap posted, or cut to fit
        for field in ("whatIsMissing", "reason"):
            rec = _long_session()
            if field == "whatIsMissing":
                rec["whatIsMissing"] = rec["whatIsMissing"] + ["w" * rr.MAX_BODY_CHARS]
            else:
                rec["findings"][0]["reason"] = "r" * rr.MAX_BODY_CHARS
>           with pytest.raises(rr.Refusal) as e:
                 ^^^^^^^^^^^^^^^^^^^^^^^^^
E           Failed: DID NOT RAISE Refusal

/path/to/home/.superheroes-worktrees/superheroes/issue-1713-92994e7f22aa2a28/plugins/superheroes/lib/tests/test_review_record.py:1883: Failed
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_a_record_that_cannot_fit_after_every_step_is_refused_not_truncated
1 failed in 0.30s
```

Restore: `        pass` → `        raise Refusal("review-record-too-large", f"{len(body)} characters")`. Restored line quoted back (line 872):
`        raise Refusal("review-record-too-large", f"{len(body)} characters")`.

Raw green:

```
.                                                                        [100%]
1 passed in 0.25s
```

## Normalization

`test_the_shed_line_names_exactly_what_was_shed` runs with the lane-basis steps turned off (`_SHED_STEPS` set to
`()`) so its two caps are exact. Production timing the pin hides: the lane-basis steps shave a few characters first,
so the reviewer steps start a little later there. The pin is stated at the test, in the code. That test is not one of
the four declared nodes; it pins the two wordings of the shed line, and was not neutralized.
