# Bite-proof record: cloud_cleanup.py and the gardening pass's reviewer-pass line

Detectors: `plugins/superheroes/lib/tests/test_cloud_cleanup.py` (`T1`) and `plugins/superheroes/lib/tests/test_cloud_setup_gardening.py` (`T2`).
Guarded elements (declared by the order): (1) the open-PR `none` return in `plan`; (2) the `branch-moved` sha check;
(3) the final sha read right before the DELETE; (4) the `branch-in-use` base check; (5) `record`'s delivered-only `ownerMessage`;
(6) the `Renew now` threshold. Each was neutralized by a targeted edit in the production file, the detector run alone
as one `-k` selection, then restored by the inverse edit. The test files were never edited during the proofs.

Run command, each time, from `plugins/superheroes/lib`: `/root/.local/bin/pytest -p no:cacheprovider <file> -q -k <selection>`.
This is not the order's `/usr/bin/python3 -B -X pycache_prefix=/tmp/c8-pyc -m pytest ...`: that command was refused
in this session ("This command requires approval"), and `/usr/bin/python3 -m pytest` reports `No module named pytest`.
`/root/.local/bin/pytest` is the pytest installed on this machine.

Pinned condition: the fixtures set `GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CONFIG_NOSYSTEM=1` (in the `w` fixture of `T1`),
because this machine's global git config signs every commit through a signer that is not running (the ledger fixture repository still uses git). What that pin makes
unobservable: a developer's own git configuration (signing, hooks, aliases) acting on the fixture repositories.

Greens: one green run of both files after all six restores (`35 passed`), not six single-node greens; the order's
14-invocation budget cannot hold six reds, six greens, a first green and the regression run. See the order's budget note in the report.

## 1. The open-PR `none` return

Axis: an open PR gets nothing (no lane read, no receipt, no message), refusal-side.

- Neutralization (`cloud_cleanup.py`, `_plan`): `if pull["state"] == "open":` became `if False and pull["state"] == "open":`.
- Node: `T1 -k test_an_open_pr_after_a_handback_or_a_park` (two parametrized cases).
- Red (this capture was piped through `tail -25`, a filtered capture; the last lines): the plan of an open PR returned a cleanup.

```
E       AssertionError: assert {'ok': True, ...er/name', ...} == {'ok': True, ...n': 'pr-open'}
E         Differing items:
E         {'action': 'cleanup'} != {'action': 'none'}
E         Left contains 12 more items:
FAILED tests/test_cloud_cleanup.py::test_an_open_pr_after_a_handback_or_a_park_gets_no_message_no_deletion_and_no_receipt[handback]
FAILED tests/test_cloud_cleanup.py::test_an_open_pr_after_a_handback_or_a_park_gets_no_message_no_deletion_and_no_receipt[park]
2 failed, 24 deselected in 0.66s
```

- Restore: the inverse edit; `cloud_cleanup.py:181` reads `    if pull["state"] == "open":`.

## 2. The `branch-moved` sha check

Axis: a branch whose head is not the PR's recorded head is never deleted (refusal token `branch-moved`).
This is the comparison of element 3 seen from the refusal side; the delete is now a `gh api -X DELETE` call with no
expected-sha condition, so this comparison is the only guard on the branch's sha. Its proof is recorded once, under 3.

## 3. The final sha read right before the DELETE

Axis: the branch's sha is read immediately before the DELETE and compared with the PR's head; a branch that moved is
never deleted (`branch-moved`). A push that lands between that read and the DELETE is not caught: the accepted residual,
stated in the module docstring and at the call site.

- Neutralization (`branch`): `if sha != head_sha:` became `if False and sha != head_sha:`.
- Node: `T1 -k test_a_branch_that_moved_past_the_prs_head_is_never_deleted`.
- Red command (from the repository root): `scripts/pinned-python -B -m pytest plugins/superheroes/lib/tests/test_cloud_cleanup.py -q -k test_a_branch_that_moved_past_the_prs_head_is_never_deleted`.
  Last lines: `FAILED plugins/superheroes/lib/tests/test_cloud_cleanup.py::test_a_branch_that_moved_past_the_prs_head_is_never_deleted` and `1 failed, 42 deselected in 15.67s`.
  The branch was deleted where `{'ok': False, 'reason': 'branch-moved'}` was expected.
- Restore: the inverse edit; `cloud_cleanup.py:396` reads `        if sha != head_sha:`.
- Green command: the same command. Last line: `1 passed, 42 deselected in 0.72s`.
- Not separately neutralized: the adjacency of the read and the DELETE (`test_the_branch_sha_is_read_right_before_the_delete`
  pins that the call before the DELETE is the branch's ref read); that ordering is unproven by a red run.

## 4. The `branch-in-use` base check

Axis: a branch an open PR uses as its base (a stack's lower layer) is kept.

- Neutralization (`_in_use`): `if _name(other, "base", "ref") == branch:` became `if False and _name(other, "base", "ref") == branch:`.
- Node: `T1 -k test_a_branch_an_open_pr_uses_as_its_base_is_kept`.
- Red (unfiltered): `1 failed in 0.35s`; the branch was deleted (`{'ok': True, ... 'action': 'cleanup', 'already': None, 'branch': 'feature'...}` where `{'ok': False, 'reason': 'branch-in-use'}` was expected).

```
>       assert _branch(w) == {"ok": False, "reason": "branch-in-use"}
E       AssertionError: assert {'ok': True, ...d': True, ...} == {'ok': False,...ranch-in-use'}
FAILED tests/test_cloud_cleanup.py::test_a_branch_an_open_pr_uses_as_its_base_is_kept
1 failed, 25 deselected in 0.35s
```

- Restore: the inverse edit; `cloud_cleanup.py:293` reads `        if _name(other, "base", "ref") == branch:`.

## 5. `record`'s delivered-only `ownerMessage`

Axis: the owner is told the builder was asked only when the request is confirmed delivered.

- Neutralization (`record`): `... if receipt["outcome"] == "delivered" else None` became `... if True else None`.
- Node: `T1 -k "test_an_uncertain_request or test_a_failed_request"` (two tests).
- Red (unfiltered): `2 failed in 0.52s`; an `uncertain` and a `failed` receipt each carried the owner message.

```
E       assert (True and "#412 is merged. I've asked its cloud builder to archive itself. You'll get one prompt for it: tap Allow once." is None)
FAILED tests/test_cloud_cleanup.py::test_an_uncertain_request_is_never_resent_on_its_own_and_has_no_owner_message
FAILED tests/test_cloud_cleanup.py::test_a_failed_request_may_be_overwritten_by_a_delivered_one
2 failed, 24 deselected in 0.52s
```

- Restore: the inverse edit; `cloud_cleanup.py:262` reads `    owner = texts[got["outcome"]] % number if receipt["outcome"] == "delivered" else None`.

## 6. The `Renew now` threshold

Axis: a pass lapsing exactly `next_pass_days` away is marked `Renew now` (inclusive bound).

- Neutralization (`cloud_setup.py`, `_lapse_line`): `if days <= next_pass_days:` became `if days < next_pass_days:`.
- Node: `T2 -k test_the_threshold_is_the_next_pass_days_inclusive`.
- Red (unfiltered): `1 failed in 0.34s`; at exactly 7 days the mark was `None`.

```
>       assert _lines(w)[0]["mark"] == "Renew now"
E       AssertionError: assert None == 'Renew now'
FAILED tests/test_cloud_setup_gardening.py::test_the_threshold_is_the_next_pass_days_inclusive
1 failed, 8 deselected in 0.34s
```

- Restore: the inverse edit; `cloud_setup.py:335` reads `    if days <= next_pass_days:`.

## Green after all six restores

`/root/.local/bin/pytest -p no:cacheprovider tests/test_cloud_cleanup.py tests/test_cloud_setup_gardening.py -q`

```
...................................                                      [100%]
35 passed in 7.94s
```

A search of `cloud_cleanup.py` and `cloud_setup.py` for `if False`, `if True` and `days <` found none of the neutralizations present.
