# Bite-proof record — the owner-card count and repeat suppression read the certified-review rule (#2531)

**Provenance:** light lane, orchestrator-typed (maker family claude). Detector file: `plugins/superheroes/lib/tests/test_owner_cards_read_certified_rule_2531.py`, unedited between each red and its green. Every entry is a targeted, reversible edit made and undone with the edit tool at committed head `91eabf4d (e1 to e4; e5 and e6 name their own)` (no `git checkout`, `restore`, `reset` or `stash`); after every restore, `git status --porcelain` printed nothing. Runs: `scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest plugins/superheroes/lib/tests/test_owner_cards_read_certified_rule_2531.py -q -p no:randomly -k "<expr>"`; the last line of each capture is the run's exit status. Redaction: the worktree path is shown as `<worktree>` and the `UV_NATIVE_TLS` deprecation line `uv` prints first is dropped; no secret, token, URL or personal data appears, so nothing else is redacted.

## e1. The owner-card count reads the waiting set (`review_measures._release_measures`, the `cards` predicate)

- **Axis:** a card is a finding that reaches the owner as one (`review_record.waits_for_owner`): a listed Minor is none, a no-outcome Minor card is one.
- **Detector:** `test_a_listed_minor_left_for_the_owner_is_no_owner_card`, `test_a_no_outcome_minor_card_is_an_owner_card` (both parameters).
- **Neutralization:** the predicate `review_record.waits_for_owner(f, r["findings"])` became the base's `f.get("outcome") == review_findings_schema.LEFT_FOR_OWNER and not review_record.repeat_held_elsewhere(f, r["findings"])`.
- **Selection:** `-k "listed_minor_left or no_outcome_minor_card_is_an"`.

**Raw red:**

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
___________ test_a_listed_minor_left_for_the_owner_is_no_owner_card ____________

    def test_a_listed_minor_left_for_the_owner_is_no_owner_card():
        # break-it: counting by `outcome == left-for-owner` alone counts this listed Minor, and the total reads 2
>       assert _cards([_f("k1", risk=False), _f("k2", severity="Important")]) == 1
E       AssertionError: assert 2 == 1
E        +  where 2 = _cards([{'id': 'k1', 'findingKey': 'k1', 'outcome': 'left-for-owner', 'severity': 'Minor', ...}, {'id': 'k2', 'findingKey': 'k2', 'outcome': 'left-for-owner', 'severity': 'Important', ...}])

<worktree>/plugins/superheroes/lib/tests/test_owner_cards_read_certified_rule_2531.py:54: AssertionError
________ test_a_no_outcome_minor_card_is_an_owner_card[in-a-risk-area] _________

risk = True

    @pytest.mark.parametrize("risk", [True, None], ids=["in-a-risk-area", "risk-unknown"])
    def test_a_no_outcome_minor_card_is_an_owner_card(risk):
        # break-it: counting by `outcome == left-for-owner` alone misses this no-outcome card, and the total reads 0
>       assert _cards([_f("k1", outcome=None, risk=risk)]) == 1
E       AssertionError: assert 0 == 1
E        +  where 0 = _cards([{'id': 'k1', 'findingKey': 'k1', 'outcome': None, 'severity': 'Minor', ...}])

<worktree>/plugins/superheroes/lib/tests/test_owner_cards_read_certified_rule_2531.py:64: AssertionError
_________ test_a_no_outcome_minor_card_is_an_owner_card[risk-unknown] __________

risk = None

    @pytest.mark.parametrize("risk", [True, None], ids=["in-a-risk-area", "risk-unknown"])
    def test_a_no_outcome_minor_card_is_an_owner_card(risk):
        # break-it: counting by `outcome == left-for-owner` alone misses this no-outcome card, and the total reads 0
>       assert _cards([_f("k1", outcome=None, risk=risk)]) == 1
E       AssertionError: assert 0 == 1
E        +  where 0 = _cards([{'id': 'k1', 'findingKey': 'k1', 'outcome': None, 'severity': 'Minor', ...}])

<worktree>/plugins/superheroes/lib/tests/test_owner_cards_read_certified_rule_2531.py:64: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_owner_cards_read_certified_rule_2531.py::test_a_listed_minor_left_for_the_owner_is_no_owner_card
FAILED plugins/superheroes/lib/tests/test_owner_cards_read_certified_rule_2531.py::test_a_no_outcome_minor_card_is_an_owner_card[in-a-risk-area]
FAILED plugins/superheroes/lib/tests/test_owner_cards_read_certified_rule_2531.py::test_a_no_outcome_minor_card_is_an_owner_card[risk-unknown]
3 failed, 9 deselected in 0.27s
exit=1
```

**Restore:** the inverse edit put the line back; `git status --porcelain` printed nothing.

**Raw green:**

```
...                                                                      [100%]
3 passed, 9 deselected in 0.28s
exit=0
```

## e2. The holder set of `review_record.repeat_held_elsewhere` (`left = {... if _card_shaped(g)}`)

- **Axis:** a no-outcome Minor or Nit card holds a repeat's card like a left-for-owner card.
- **Detector:** `test_a_repeat_of_a_no_outcome_minor_card_is_held_by_it`.
- **Neutralization:** `if _card_shaped(g)` became the base's `if isinstance(g, dict) and g.get("outcome") == _LEFT_FOR_OWNER and not listed_for_merge(g)`.
- **Selection:** `-k "repeat_of_a_no_outcome_minor_card_is_held_by_it"`.

**Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_a_repeat_of_a_no_outcome_minor_card_is_held_by_it ____________

    def test_a_repeat_of_a_no_outcome_minor_card_is_held_by_it():
        holder, again = _f("k1", outcome=None), _repeat(_f("k2"), "k1")
        # break-it: a holder set of left-for-owner findings only misses this no-outcome holder, so both cards wait
>       assert rr.repeat_held_elsewhere(again, [holder, again]) is True
E       AssertionError: assert False is True
E        +  where False = <function repeat_held_elsewhere at 0x7ff22acd0f40>({'id': 'k2', 'findingKey': 'k2', 'outcome': 'left-for-owner', 'severity': 'Minor', ...}, [{'id': 'k1', 'findingKey': 'k1', 'outcome': None, 'severity': 'Minor', ...}, {'id': 'k2', 'findingKey': 'k2', 'outcome': 'left-for-owner', 'severity': 'Minor', ...}])
E        +    where <function repeat_held_elsewhere at 0x7ff22acd0f40> = rr.repeat_held_elsewhere

<worktree>/plugins/superheroes/lib/tests/test_owner_cards_read_certified_rule_2531.py:88: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_owner_cards_read_certified_rule_2531.py::test_a_repeat_of_a_no_outcome_minor_card_is_held_by_it
1 failed, 11 deselected in 0.46s
exit=1
```

**Restore:** the inverse edit put the line back; `git status --porcelain` printed nothing.

**Raw green:**

```
.                                                                        [100%]
1 passed, 11 deselected in 0.26s
exit=0
```

## e3. The repeat's own guard in `review_record.repeat_held_elsewhere` (`if not _card_shaped(f) or ...`)

- **Axis:** a no-outcome Minor or Nit card that repeats another card is held like a left-for-owner repeat, so the owner does not see it twice.
- **Detector:** `test_a_no_outcome_minor_card_repeating_a_left_for_owner_card_is_held`, `test_a_no_outcome_minor_card_repeating_another_card_is_not_counted_twice`.
- **Neutralization:** `if not _card_shaped(f) or held is None` became the base's `if f.get("outcome") != _LEFT_FOR_OWNER or held is None`.
- **Selection:** `-k "repeating_a_left_for_owner_card_is_held or repeating_another_card_is_not_counted"`.

**Raw red:**

```
FF                                                                       [100%]
=================================== FAILURES ===================================
___ test_a_no_outcome_minor_card_repeating_another_card_is_not_counted_twice ___

    def test_a_no_outcome_minor_card_repeating_another_card_is_not_counted_twice():
        # break-it: a repeat rule that holds only left-for-owner repeats counts the no-outcome repeat too, and the total reads 2
>       assert _cards([_f("k1"), _repeat(_f("k2", outcome=None), "k1")]) == 1
E       AssertionError: assert 2 == 1
E        +  where 2 = _cards([{'id': 'k1', 'findingKey': 'k1', 'outcome': 'left-for-owner', 'severity': 'Minor', ...}, {'id': 'k2', 'findingKey': 'k2', 'outcome': None, 'severity': 'Minor', ...}])

<worktree>/plugins/superheroes/lib/tests/test_owner_cards_read_certified_rule_2531.py:73: AssertionError
_____ test_a_no_outcome_minor_card_repeating_a_left_for_owner_card_is_held _____

    def test_a_no_outcome_minor_card_repeating_a_left_for_owner_card_is_held():
        holder, again = _f("k1"), _repeat(_f("k2", outcome=None), "k1")
        # break-it: requiring `outcome == left-for-owner` of the repeat leaves this card waiting, so the owner sees it twice
>       assert rr.repeat_held_elsewhere(again, [holder, again]) is True
E       AssertionError: assert False is True
E        +  where False = <function repeat_held_elsewhere at 0x7f6304cc8f40>({'id': 'k2', 'findingKey': 'k2', 'outcome': None, 'severity': 'Minor', ...}, [{'id': 'k1', 'findingKey': 'k1', 'outcome': 'left-for-owner', 'severity': 'Minor', ...}, {'id': 'k2', 'findingKey': 'k2', 'outcome': None, 'severity': 'Minor', ...}])
E        +    where <function repeat_held_elsewhere at 0x7f6304cc8f40> = rr.repeat_held_elsewhere

<worktree>/plugins/superheroes/lib/tests/test_owner_cards_read_certified_rule_2531.py:81: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_owner_cards_read_certified_rule_2531.py::test_a_no_outcome_minor_card_repeating_another_card_is_not_counted_twice
FAILED plugins/superheroes/lib/tests/test_owner_cards_read_certified_rule_2531.py::test_a_no_outcome_minor_card_repeating_a_left_for_owner_card_is_held
2 failed, 10 deselected in 0.27s
exit=1
```

**Restore:** the inverse edit put the line back; `git status --porcelain` printed nothing.

**Raw green:**

```
..                                                                       [100%]
2 passed, 10 deselected in 0.26s
exit=0
```

## e4. The open test of the clean-loop and cap-choice readers (`review_measures._open`)

- **Axis:** a Minor or Nit listed for the merge verdict leaves nothing open, so a certified record with one is a clean loop.
- **Detector:** `test_a_listed_minor_leaves_a_reviewed_record_clean`.
- **Neutralization:** `and not review_record.listed_for_merge(f)` became `and True`.
- **Selection:** `-k "leaves_a_reviewed_record_clean"`.

**Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_a_listed_minor_leaves_a_reviewed_record_clean ______________

    def test_a_listed_minor_leaves_a_reviewed_record_clean():
        # break-it: reading `outcome in (None, left-for-owner)` alone calls this certified record not clean
>       assert RM._clean(_rec([_f("k1", risk=False), _f("k2", outcome=None, risk=False)], status="reviewed")) is True
E       AssertionError: assert False is True
E        +  where False = <function _clean at 0x7f8bd1005b20>({'pr': 1, 'sessionId': 's1', 'writtenAt': '2026-11-01T10:00:00Z', 'status': 'reviewed', ...})
E        +    where <function _clean at 0x7f8bd1005b20> = RM._clean
E        +    and   {'pr': 1, 'sessionId': 's1', 'writtenAt': '2026-11-01T10:00:00Z', 'status': 'reviewed', ...} = _rec([{'id': 'k1', 'findingKey': 'k1', 'outcome': 'left-for-owner', 'severity': 'Minor', ...}, {'id': 'k2', 'findingKey': 'k2', 'outcome': None, 'severity': 'Minor', ...}], status='reviewed')

<worktree>/plugins/superheroes/lib/tests/test_owner_cards_read_certified_rule_2531.py:108: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_owner_cards_read_certified_rule_2531.py::test_a_listed_minor_leaves_a_reviewed_record_clean
1 failed, 11 deselected in 0.26s
exit=1
```

**Restore:** the inverse edit put the line back; `git status --porcelain` printed nothing.

**Raw green:**

```
.                                                                        [100%]
1 passed, 11 deselected in 0.25s
exit=0
```

## e5. The carry rule admits a held no-outcome Minor card (`review_record.carry_refusal`; review round 1, finding v0)

- **Axis:** a no-outcome Minor or Nit card that another card holds is admitted like the card that holds it, so the carry is not refused as still open. Run at `70b850df`; there the predicate e2 and e3 name `_card_shaped` is public as `card_shaped`.
- **Detector:** `test_the_carry_rule_admits_a_no_outcome_minor_card_another_card_holds`.
- **Neutralization:** `or card_shaped(f))` became `or waits_for_owner(f, findings))`, the base's form.
- **Selection:** `-k "carry_rule_admits_a_no_outcome"`.

**Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_the_carry_rule_admits_a_no_outcome_minor_card_another_card_holds _____

    def test_the_carry_rule_admits_a_no_outcome_minor_card_another_card_holds():
        def decide(*args, **kwargs):
            return {"read": rr.returning_review.READ_CHANGED, "changedFiles": [], "why": []}
    
        sha = "a" * 40
        holder, again = _f("k1"), _repeat(_f("k2", outcome=None), "k1")
        prior = {"finalCommit": {"sha": sha}, "findings": [holder, again],
                 "reviewers": [{"name": "r", "ran": rr.RAN_ENGINE_RECORD, "coversFinalCommit": True}]}
        # break-it: admitting a no-outcome finding only when it waits refuses this held repeat as "still open"
>       assert rr.carry_refusal(prior, sha, "/r", "b" * 40, "c" * 40, [], decide) is None
E       AssertionError: assert 'an earlier finding is still open' is None
E        +  where 'an earlier finding is still open' = <function carry_refusal at 0x7f16c23fe7a0>({'finalCommit': {'sha': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}, 'findings': [{'id': 'k1', 'findingKey': 'k1', 'ou...me': None, 'severity': 'Minor', ...}], 'reviewers': [{'name': 'r', 'ran': 'engine-record', 'coversFinalCommit': True}]}, 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', '/r', ('b' * 40), ('c' * 40), [], <function test_the_carry_rule_admits_a_no_outcome_minor_card_another_card_holds.<locals>.decide at 0x7f16c3c50400>)
E        +    where <function carry_refusal at 0x7f16c23fe7a0> = rr.carry_refusal

<worktree>/plugins/superheroes/lib/tests/test_owner_cards_read_certified_rule_2531.py:128: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_owner_cards_read_certified_rule_2531.py::test_the_carry_rule_admits_a_no_outcome_minor_card_another_card_holds
1 failed, 13 deselected in 4.30s
exit=1
```

**Restore:** the inverse edit put the line back; `git status --porcelain` printed nothing.

**Raw green:**

```
.                                                                        [100%]
1 passed, 13 deselected in 3.51s
exit=0
```

## e6. The merge sheet admits a held no-outcome Minor card (`pr_sheet` record validation; review round 1, finding v0)

- **Axis:** a null outcome is admitted on a card-shaped finding, a held repeat included, so the sheet builds and shows the holder's one card. Run at `70b850df`.
- **Detector:** `test_the_merge_sheet_builds_with_a_no_outcome_minor_card_another_card_holds_and_shows_one_card`.
- **Neutralization:** `(review_record.listed_for_merge(f) or card)` became `(review_record.listed_for_merge(f) or waits)`, the base's form.
- **Selection:** `-k "merge_sheet_builds_with"`.

**Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_the_merge_sheet_builds_with_a_no_outcome_minor_card_another_card_holds_and_shows_one_card _

    def test_the_merge_sheet_builds_with_a_no_outcome_minor_card_another_card_holds_and_shows_one_card():
        from test_pr_sheet import WORDS, build
        from test_pr_sheet_fixed_above_2332 import pr_input, record
        from test_pr_sheet_listed_2493 import ENTRY, minor
    
        holder = minor("H1", True)
        again = {**minor("H2", True, outcome=None, reason=None), "repeatOf": {"findingKey": holder["findingKey"]}}
        # break-it: admitting a null outcome only on a waiting finding refuses this held repeat, and the sheet does not build
>       sheet = build([record(10, [holder, again])], pr_input(leftovers={holder["findingKey"]: ENTRY}))
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

<worktree>/plugins/superheroes/lib/tests/test_owner_cards_read_certified_rule_2531.py:141: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
<worktree>/plugins/superheroes/lib/tests/test_pr_sheet.py:49: in build
    return pr_sheet.build(copy.deepcopy(records), copy.deepcopy(advisor), WORDS, previous=previous)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

records = [{'schema': 'review-record/1', 'pr': 10, 'sessionId': 'session-5', 'lane': {'value': 'full', 'reason': 'A new table holds money.', 'source': 'PR lane call'}, ...}]
advisor = {'schema': 'pr-sheet-input/1', 'kind': 'pr', 'number': 10, 'title': 'Round the balance', ...}
words = {'leftoverKind': 'Leftover', 'closureKind': 'Closure receipt', 'ifLeft': 'If left', 'whyYours': "Why it's yours", ...}
place = None, previous = None, bodies = None, spec_base = None

    def build(records, advisor, words, place=None, previous=None, bodies=None, spec_base=None):
        """Returns the sheet's data file as a dict, or raises Refusal with every problem found.
    
        previous is the exact bytes of the earlier sheet the input's carriedForward.fromSheet names, None when there is no carry
        (a carry given None is refused). bodies is None (the caller reads no PR body: no accounting check is made, the input's
        accounting is accepted and ignored, and the sheet gets neither nothingListed nor canonAccounted) or a dict of each covered
        PR's number to its body text, whose keys must be exactly the covered PRs. With bodies, once they raise no problem of their
        own, the input's accounting must account for every acceptance they list, exactly once, to something on the sheet
        (_check_accounting); no listed acceptance becomes a card. The sheet then records one of three states about them: no
        acceptance is listed (nothingListed), at least one is listed and every one is accounted to a Canon ruling (canonAccounted:
        the ruling ids, sorted and distinct), or neither (some acceptance rests on an item, a fold or a leftover card).
        """
        problems = []
        if not isinstance(advisor, dict):
            raise Refusal(["the advisor's input must be an object"])
        allowed = _check_input(advisor, words, problems)
        breakdown, spec_history = None, []
        if "spec" in advisor:  # the spec-PR mode is named by the input, never inferred from a missing record
            if records:
                problems.append("a spec-PR sheet (the input names spec) takes no review record: its facts come from the spec's own artifacts")
            elif advisor.get("kind") != "pr":
                problems.append('a spec-PR sheet must be kind "pr"')
            elif _num(advisor.get("number")):
                made = _spec_record(advisor["spec"], advisor["number"], words, spec_base, problems)
                if made:
                    record, breakdown, spec_history = made
                    records = [record]
        bodies_sound = False
        if bodies is not None and allowed is not None:
            found = len(problems)
            _check_bodies(bodies, allowed, problems)
            bodies_sound = len(problems) == found
        earlier = None
        if "carriedForward" in advisor and _check_carry_input(advisor["carriedForward"], allowed, problems) and allowed is not None \
                and _num(advisor.get("number")):  # a stack without a number is refused above, and the earlier sheet cannot be compared to it
            earlier = _check_previous(advisor, previous, problems)
        recs = [r for r in (_record(raw, n, problems) for n, raw in enumerate(records, 1)) if r]
        kind, number, have = advisor.get("kind"), advisor.get("number"), [r["pr"] for r in recs]
        if allowed is not None and len(recs) == len(records):
            if kind == "pr" and len(recs) != 1:
                problems.append(f"a pr sheet takes exactly one record, got {len(recs)}")
            elif kind == "pr" and have[0] != number:
                problems.append(f"the record is for PR #{have[0]}, not PR #{number}")
            elif kind == "stack":
                problems.extend(f"PR #{n} has more than one record" for n in sorted({n for n in have if have.count(n) > 1}))
                if set(have) != set(allowed):
                    problems.append(f"the records are for PRs {sorted(set(have))}, but the stack lists PRs {sorted(allowed)}")
        leftovers, determined = advisor.get("leftovers", {}), advisor.get("craftDeterminations", {})
        leftovers, determined = (x if isinstance(x, dict) else {} for x in (leftovers, determined))
        # The earlier sheet's decided-for-you entries by finding: a carried sheet keeps them as they stand.
        before = {e["finding"]: e for e in earlier["prSheet"].get("decidedForYou", [])} if earlier is not None else {}
        named, decisions, listed_keys = {}, {}, {}  # listed_keys: each lookup key of a finding listed for the merge verdict, counted
        # Only with the bodies read: a bodies-less build makes no fixed-above reading, so its leftovers entry stays required.
        fixed, auto = _fixed_above(recs, bodies, kind, allowed, problems) if bodies_sound else ({}, set())
        for r in recs:
            for n, f in enumerate(r["findings"]):
                if review_record.listed_for_merge(f):
                    for k in _lookups(kind, r["pr"], f):
                        listed_keys[k] = listed_keys.get(k, 0) + 1
                if review_record.waits_for_owner(f, r["findings"]):
                    keys = _lookups(kind, r["pr"], f)
                    for k in keys:
                        named[k] = named.get(k, 0) + 1
                    if not keys:
                        continue
                    call_at, det_at = next((k for k in keys if k in leftovers), None), next((k for k in keys if k in determined), None)
                    prior = before.get(keys[0])
                    if (r["pr"], n) in fixed:
                        # axis: a finding fixed above needs no leftovers or craftDeterminations entry and takes none, and a carried sheet
                        # cannot move an earlier decided-for-you entry to caught
                        claim = fixed[(r["pr"], n)]
                        if call_at is not None or det_at is not None:
                            problems.append(f"left-for-owner finding {_title(f)!r} on PR #{r['pr']} is fixed above in #{claim['layer']}; "
                                            "give it no leftovers or craftDeterminations entry")
                        if prior is not None:
                            problems.append(f"left-for-owner finding {_title(f)!r} on PR #{r['pr']} was a decided-for-you entry on the earlier sheet and is "
                                            f"fixed above in #{claim['layer']}; a carried sheet cannot move a decided-for-you entry; republish unsigned")
                        continue
                    det = determined[det_at] if det_at is not None else prior if prior is not None and call_at is None else None
                    if earlier is not None and det_at is not None:
                        if prior is None:
                            problems.append(f"craftDeterminations {det_at}: a carried sheet cannot add a determination; add it on an unsigned republish")
                        elif not (isinstance(det, dict) and (det.get("ground"), det.get("reason")) == (prior["ground"], prior["reason"])):
                            problems.append(f"craftDeterminations {det_at}: a carried sheet keeps the earlier sheet's determination unchanged; change it on an unsigned republish")
                    if prior is not None and call_at is not None:
                        problems.append(f"leftovers {call_at}: a carried sheet cannot turn a decided-for-you entry back into a card; do that on an unsigned republish")
                    if det is not None:
                        decisions[(r["pr"], n)] = det
                    if det is not None and call_at is not None:
                        problems.append(f"left-for-owner finding {_title(f)!r} on PR #{r['pr']} has both a leftovers entry and a craft determination; give one")
                    elif det is None and call_at is None:
                        problems.append(f"left-for-owner finding {_title(f)!r} on PR #{r['pr']} has no leftovers entry (key {keys[0]!r}); "
                                        "give it why, context and options, or a craft determination")
        for name, given in (("leftovers", leftovers), ("craftDeterminations", determined)):
            problems.extend(f"{name} key {k!r} names no left-for-owner finding" for k in given if k not in named)
            problems.extend(f"{name} key {k!r} names {named[k]} left-for-owner findings; use a finding's findingKey"
                            for k in given if named.get(k, 0) > 1)
        listed = {pr: listed_bullets(pr, bodies[pr]) for pr in allowed} if bodies_sound else {}
        if bodies_sound:
            _check_accounting(advisor.get("accounting", {}), listed, advisor, leftovers, named, problems, auto, listed_keys)
            for pr in allowed:
                for label, text in costly_unlisted(bodies[pr]):
                    problems.append(f'PR #{pr}\'s {"costly" if label else "unlabelled (read as costly)"} deviation ("{_excerpt(text)}") has no line under '
                                    "What we're accepting: carry its text, after the label, into a line there")
        if problems:
>           raise Refusal(problems)
E           pr_sheet.Refusal: ["record for PR #10: finding 'Title of H2' has outcome None, not one of fixed, shown-wrong, craft, left-for-owner, ruling"]

<worktree>/plugins/superheroes/lib/pr_sheet.py:1345: Refusal
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_owner_cards_read_certified_rule_2531.py::test_the_merge_sheet_builds_with_a_no_outcome_minor_card_another_card_holds_and_shows_one_card
1 failed, 13 deselected in 1.13s
exit=1
```

**Restore:** the inverse edit put the line back; `git status --porcelain` printed nothing.

**Raw green:**

```
.                                                                        [100%]
1 passed, 13 deselected in 1.00s
exit=0
```
