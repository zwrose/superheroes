# Bite-proof record — the owner-card count and repeat suppression read the certified-review rule (#2531)

**Provenance:** light lane, orchestrator-typed (maker family claude). Detector file: `plugins/superheroes/lib/tests/test_owner_cards_read_certified_rule_2531.py`, unedited between each red and its green. Every entry is a targeted, reversible edit made and undone with the edit tool at committed head `91eabf4d` (no `git checkout`, `restore`, `reset` or `stash`); after every restore, `git status --porcelain` printed nothing. Runs: `scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest plugins/superheroes/lib/tests/test_owner_cards_read_certified_rule_2531.py -q -p no:randomly -k "<expr>"`; the last line of each capture is the run's exit status. Redaction: the worktree path is shown as `<worktree>` and the `UV_NATIVE_TLS` deprecation line `uv` prints first is dropped; no secret, token, URL or personal data appears, so nothing else is redacted.

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
