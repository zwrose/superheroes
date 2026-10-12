# Bite-proof record: cloud C7 WO-C (#1748), `cloud_parked.py`

Detector: `plugins/superheroes/lib/tests/test_cloud_parked.py`. Guarded elements (declared by the
order): the lapsed-text match, the renewal test, the closed filter, the let-through filter,
decided-once. Each was neutralized by a targeted edit in `plugins/superheroes/lib/cloud_parked.py`,
the detector run alone as one test node, then restored by the inverse edit and run green. The test
file was never edited during the proofs. Command, each time, from the worktree root:
`scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "<node>" -q`.

## 1. The lapsed-text match

Axis: a comment is the lapsed park only when its text starts with `REVIEW_LAPSED_TEXT`.

- Neutralization (in `notice`): `... c["body"].strip().startswith(lapsed)]` became
  `... c["body"].strip() is not None]` (any comment with a body counts).
- Node: `test_cloud_parked.py::test_a_pr_whose_review_did_not_run_for_another_reason_gets_no_renewal_words`
- Red: `1 failed in 1.31s`; `{'kind': 'lapsed-pass'} != {'kind': 'not-lapsed-pass'}` and the text
  `#43 is parked. The reviewer pass lapsed mid-build, ... Renew the pass and I'll send it back for review.`
  `!= None`.
- Restore: the inverse edit; line 155 reads again
  `parks = [c for c in comments if isinstance(c.get("body"), str) and c["body"].strip().startswith(lapsed)]`.
- Green: `1 passed in 0.89s`.

## 2. The renewal test

Axis: a PR is renewed only when the setup record's lapse date moved later than the one seen and is not past.

- Neutralization (in `_renewed`): `return (current is not None and ...)` became
  `return True or (current is not None and ...)`.
- Node: `test_cloud_parked.py::test_a_pass_made_but_not_confirmed_by_a_cloud_session_sends_nothing_back`
- Red: `1 failed in 2.72s`; `AssertionError: assert ([{'pr': 10, '...': None, ...}] == []` (the
  unconfirmed pass sent PR 10 back).
- Restore: the inverse edit; `_renewed` returns
  `(current is not None and _sib("cloud_check")._lapses_ok(current, today)` /
  `and (seen is None or current > seen))` again.
- Green: `1 passed in 1.85s`.

## 3. The closed filter

Axis: a parked PR that closed or merged before the renewal is marked `closed` and not sent.

- Neutralization (in `send_back`): `elif pull["state"] == "closed" or pull.get("merged") is True:`
  became `elif False and (pull["state"] == "closed" or pull.get("merged") is True):`.
- Node: `test_cloud_parked.py::test_a_parked_pr_closed_before_the_renewal_is_not_sent_back`
- Red: `1 failed in 2.62s`; `assert [{'pr': 10, '...': None, ...}] == []`, "Left contains 2 more
  items" (both the closed and the merged PR were sent back).
- Restore: the inverse edit; the line reads `elif pull["state"] == "closed" or pull.get("merged") is True:` again.
- Green: `1 passed in 2.56s`.

## 4. The let-through filter

Axis: a PR whose review record names missing reviews that all carry an owner go-ahead is marked
`owner-let-through` and not sent.

- Neutralization (in `send_back`): `elif _let_through(e["repo"], e["pr"], env, run):` became
  `elif False and _let_through(e["repo"], e["pr"], env, run):`.
- Node: `test_cloud_parked.py::test_a_parked_pr_the_owner_let_through_is_not_sent_back`
- Red: `1 failed in 2.65s`; `assert [] == [{'pr': 10, 'outcome': 'owner-let-through'}]`.
- Restore: the inverse edit; the line reads `elif _let_through(e["repo"], e["pr"], env, run):` again.
- Green: `1 passed in 8.92s`.

## 5. Decided-once

Axis: an entry whose `outcome` is set is never decided or sent again.

- Neutralization (in `send_back`): `for e in (e for e in entries if e["outcome"] is None):` became
  `for e in entries:`.
- Node: `test_cloud_parked.py::test_a_decided_entry_is_not_sent_back_twice`
- Red: `1 failed in 5.00s`; `assert ([{'pr': 10, '...': None, ...}] == []` on the second call
  (PR 10 was sent back again).
- Restore: the inverse edit; the line reads `for e in (e for e in entries if e["outcome"] is None):` again.
- Green: `1 passed in 3.20s`.
