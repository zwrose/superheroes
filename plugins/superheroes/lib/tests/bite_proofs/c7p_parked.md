# Bite-proof record: cloud_parked.py

Detector: `plugins/superheroes/lib/tests/test_cloud_parked.py`. Guarded elements (declared by the
order): the lapsed-text match, the renewal test, the per-account read, the closed filter, the
let-through filter, `send_back` never marking sent, the no-lane branch. Each was neutralized by a
targeted edit in `plugins/superheroes/lib/cloud_parked.py`, the detector run alone as one test node,
then restored by the inverse edit and run green. The test file was never edited during the proofs.
Command, each time, from the worktree root:
`scripts/pinned-python -B -m pytest "<node>" -q -p no:cacheprovider`.

## 1. The lapsed-text match

Axis: a comment is the lapsed park only when its text starts with `REVIEW_LAPSED_TEXT`.

- Neutralization (in `notice`): `... c["body"].strip().startswith(lapsed)]` became
  `... c["body"].strip() is not None]` (any comment with a body counts).
- Node: `test_cloud_parked.py::test_a_pr_whose_review_did_not_run_for_another_reason_gets_no_renewal_words`
- Red: `1 failed in 1.01s`; the notice for a review-record comment was no longer `not-lapsed-pass`
  (`{'ok': False, ... 'reason': 'park-date-unreadable'} != {'ok': True, 'kind': 'not-lapsed-pass', ...}`).
- Restore: the inverse edit; line 182 reads again
  `parks = [c for c in comments if isinstance(c.get("body"), str) and c["body"].strip().startswith(lapsed)]`.
- Green: `1 passed in 1.64s`.

## 2. The renewal test

Axis: a PR is renewed only when the setup record's lapse date is later than the day it was parked.

- Neutralization (in `_renewed`): `and current > parked_on)` became `and True)`.
- Node: `test_cloud_parked.py::test_a_pass_lapsing_no_later_than_the_park_day_is_not_a_renewal`
- Red: `1 failed in 1.66s`; `assert [] == [10]` on `notRenewed` (a pass lapsing on the park day counted as renewed).
- Restore: the inverse edit; line 114 reads again `and current > parked_on)`.
- Green: `1 passed in 1.07s`.

## 3. The per-account read

Axis: the lapse date is read from the setup record of the account the lane ran on, not the advisor's.

- Neutralization (in `_lapses`): `if isinstance(config_dir, str) and config_dir:` became
  `if False and isinstance(config_dir, str) and config_dir:` (the caller's env is always used).
- Node: `test_cloud_parked.py::test_only_a_renewal_of_the_lanes_own_account_releases_the_pr`
- Red: `1 failed in 0.94s`; `assert ([{'pr': 10, '...second', ...}] == []` (a renewal on the advisor's
  account alone released the second account's PR).
- Restore: the inverse edit; line 103 reads again `if isinstance(config_dir, str) and config_dir:`.
- Green: `1 passed in 1.00s`.

## 4. The closed filter

Axis: a parked PR that closed or merged before the renewal is marked `closed` and not sent.

- Neutralization (in `send_back`): `if pull["state"] == "closed" or pull.get("merged") is True:`
  became `if False and (pull["state"] == "closed" or pull.get("merged") is True):`.
- Node: `test_cloud_parked.py::test_a_parked_pr_closed_or_merged_before_the_renewal_is_not_sent_back`
- Red: `1 failed in 1.21s`; `assert [{'pr': 10, '...: 'l-b', ...}] == []`, "Left contains 2 more
  items" (both the closed and the merged PR were listed to send back).
- Restore: the inverse edit; line 212 reads again `if pull["state"] == "closed" or pull.get("merged") is True:`.
- Green: `1 passed in 0.91s`.

## 5. The let-through filter

Axis: a PR whose review record names missing reviews that all carry an owner go-ahead is marked
`owner-let-through` and not sent.

- Neutralization (in `send_back`): `if through:` became `if False and through:`.
- Node: `test_cloud_parked.py::test_a_parked_pr_the_owner_let_through_is_not_sent_back`
- Red: `1 failed in 1.09s`; `assert [] == [{'pr': 10, 'outcome': 'owner-let-through'}]`.
- Restore: the inverse edit; line 227 reads again `if through:`.
- Green: `1 passed in 1.20s`.

## 6. `send_back` never marks sent

Axis: only the `sent` verb records a delivery; listing a PR leaves its outcome null.

- Neutralization (in `send_back`, step g): a line `e["outcome"], changed = "sent-back", True` added
  before `out["sendBack"].append(...)`.
- Node: `test_cloud_parked.py::test_a_pr_stays_listed_until_it_is_recorded_as_sent_and_never_after`
- Red: `1 failed in 1.15s`; `assert [] == [10]` on the second `send_back` (the first call had marked it sent).
- Restore: the inverse edit; the line is gone and `out["sendBack"].append({"pr": e["pr"], ...` follows
  `continue` again (line 234).
- Green: `1 passed in 1.21s`.

## 7. The no-lane branch

Axis: a due PR with no lane session is reported in `noLane` and left undecided, never listed to send.

- Neutralization (in `send_back`): `if not lane.get("cloudSessionName"):` became
  `if False and not lane.get("cloudSessionName"):`.
- Node: `test_cloud_parked.py::test_a_due_pr_with_no_cloud_lane_is_reported_and_stays_undecided`
- Red: `1 failed in 1.09s`; `KeyError: 'cloudSessionName'` at `"cloudSessionName": lane["cloudSessionName"]`
  (the no-lane PR reached the send list; it fails by error rather than by assertion).
- Restore: the inverse edit; line 231 reads again `if not lane.get("cloudSessionName"):`.
- Green: `1 passed in 1.07s`.
