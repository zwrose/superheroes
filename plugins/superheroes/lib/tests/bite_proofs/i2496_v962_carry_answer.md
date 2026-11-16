# Issue 2496 (vet 962) bite-proof: a verdict carries onto a moved head only on the check from the sheet's commit

**Provenance:** typed and run by the build session on 2026-11-16, for the advisor's vet 962 fix order on layer 2
(PR 2547). The guards are in `lib/head_coverage.py` `outcome`, proved by
`lib/tests/test_head_coverage_carry_answer_v962.py`. Every red below ran in a detached probe worktree at commit
7711669b, by one exact text swap and its inverse. After each restore, `git status --porcelain` printed nothing. Each
command was
`scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest plugins/superheroes/lib/tests/test_head_coverage_carry_answer_v962.py -q -p no:cacheprovider -k <selection>`.

## E-carry: the action on a ready head past a live sheet

**guarded element:** `action = "republish-carried" if carried else "republish-unsigned"`, where `carried` is the carry
answer `proven`, or `judgement` with `carry_judged_clear`. **Axis:** the head's own record proving it never carries the
verdict by itself. The check from the published sheet's commit must cover the head, and code that changed since the
sheet reads needs-review, so the sheet is republished unsigned (vet 962's case: a sheet at A, a code fix B, and a
review of B).

**neutralization:** `action = "republish-carried"` (the earlier rule: any READY head past a live sheet carries).

**raw red** (`-k "republishes_unsigned or carries_only_on"`):
```
F..FFF                                                                   [100%]
E   AssertionError: assert {'outcome': '...lish-carried'} == {'outcome': '...ish-unsigned'}
      {'sheet': 'republish-carried'} != {'sheet': 'republish-unsigned'}
FAILED ...::test_a_sheet_at_a_whose_code_fix_b_was_reviewed_republishes_unsigned
FAILED ...::test_a_ready_head_past_a_live_sheet_carries_only_on_a_covering_carry_answer[judgement-uncleared]
FAILED ...::test_a_ready_head_past_a_live_sheet_carries_only_on_a_covering_carry_answer[needs-review]
FAILED ...::test_a_ready_head_past_a_live_sheet_carries_only_on_a_covering_carry_answer[needs-review-cleared-flag]
4 failed, 2 passed, 25 deselected in 0.56s
```
The two that stay green are the covering carry answers (`proven`, and a cleared `judgement`), which carry under both
rules.

## E-carry-required: a live sheet whose head moved needs the carry answer

**guarded element:** `if moved and carry_answer is None: raise ValueError(...)`. **Axis:** a live sheet past which
the head moved never gets an action without the second check's answer, whatever the verdict.

**neutralization:** `if False and moved and carry_answer is None:`.

**raw red** (`-k no_carry_answer_is_a_usage_error`):
```
FFF                                                                      [100%]
E   Failed: DID NOT RAISE ValueError
3 failed, 28 deselected in 0.32s
```

## E-sha: with a sheet, both commits are full 40-hex shas

**guarded element:** `if not (isinstance(value, str) and _FULL_SHA_40.fullmatch(value)): raise ValueError(...)`, for
the sheet's commit and the head whenever a sheet is given. **Axis:** "the head moved past the sheet" compares two full
commits. An abbreviation, a ref, another case or nothing is refused.

**neutralization:** `if False:`.

**raw red** (`-k "full_40_hex or short_sheet_commit"`, `--tb=no`):
```
FFFFFFFFFFFFFFFFFFF                                                      [100%]
FAILED ...::test_a_sheet_needs_full_40_hex_shas_for_its_commit_and_the_head[<all 18 cases, live and held>]
FAILED ...::test_the_cli_refuses_a_short_sheet_commit_or_head_and_accepts_full_ones
19 failed, 12 deselected in 1.28s
```

## Green

After the three restores, the whole file passed: `31 passed in 1.62s`. Nothing is redacted.
