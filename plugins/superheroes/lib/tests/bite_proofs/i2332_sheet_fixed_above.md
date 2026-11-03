# I2332 sheet fixed-above bite-proof record

Invariant (I-SHEET): on a `stack` sheet built with bodies, a left-for-owner finding whose PR body carries
`fixed-above #<PR> <commit>` for it, naming a PR of `prs` later in the list than the finding's PR, is shown in
`caught` as fixed above (no card, no decided-for-you entry, no accepted item); its acceptance bullet needs no
accounting and does not count toward the listed state. Every other fixed-above disposition is a refusal problem
naming the finding and the layer.

Guarded-element set (declared by the order): C1–C4 below, all in `plugins/superheroes/lib/pr_sheet.py`, all
detected by `plugins/superheroes/lib/tests/test_pr_sheet_fixed_above_2332.py`. Each node was run alone as
`scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/pyc-2332 -m pytest "<node>" -q -p no:cacheprovider`
with the detector unedited. Every capture begins with the same harness warning line (`UV_NATIVE_TLS`), which
is not part of the test. Nothing is redacted. Every restore was the inverse edit (no `git checkout`, `restore`,
`reset` or `stash`), and the restored line was read back from the file after the restore (grep, quoted below).

Where the tool that ran the command cut its own output, the capture says so and shows only what was delivered:
the cut text is not reconstructed (C2 and C3: the middle of pytest's printout of `build()`'s source).

---

## C1 — the higher-layer check (`_fixed_above`)

**Guarded element:** `pr_sheet.py:934` `higher = kind == "stack" and layer in allowed and r["pr"] in allowed and allowed.index(layer) > allowed.index(r["pr"])`.
**Axis:** a fixed-above layer must be a PR of this stack sheet above the finding's own PR; a pr sheet, a PR the stack does not cover, the finding's own PR and a lower one are all refused.

**Neutralization:** the right-hand side replaced: `higher = True`.

**Red run** (`test_s3_a_layer_that_is_not_in_the_stack_or_is_the_findings_own_pr_refuses[99]`, complete):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_s3_a_layer_that_is_not_in_the_stack_or_is_the_findings_own_pr_refuses[99] _

layer = 99

    @pytest.mark.parametrize("layer", [99, 10])
    def test_s3_a_layer_that_is_not_in_the_stack_or_is_the_findings_own_pr_refuses(layer):
        # Bites on: the higher-layer check (an unknown PR, or the finding's own PR, taken as the fixing layer).
        # Axis: E4: the layer must be a PR of this stack sheet above the finding's own.
>       problems = refused(stack_records(), stack_input(), fixed_bodies(layer))
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2332/plugins/superheroes/lib/tests/test_pr_sheet_fixed_above_2332.py:84: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

records = [{'schema': 'review-record/1', 'pr': 10, 'sessionId': 'session-5', 'lane': {'value': 'full', 'reason': 'A new table ho...ssionId': 'session-5', 'lane': {'value': 'full', 'reason': 'A new table holds money.', 'source': 'PR lane call'}, ...}]
advisor = {'schema': 'pr-sheet-input/1', 'kind': 'stack', 'number': 9, 'title': 'Balances', ...}
bodies = {10: "## What we're accepting\n\n- f-2 The old balance is rounded twice — fixed-above #99 1a2b3c4: the layer above removes it.\n", 11: "## What we're accepting\n\nNone\n"}

    def refused(records, advisor, bodies):
>       with pytest.raises(pr_sheet.Refusal) as caught:
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE Refusal

/home/user/wt-2332/plugins/superheroes/lib/tests/test_pr_sheet_fixed_above_2332.py:48: Failed
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_pr_sheet_fixed_above_2332.py::test_s3_a_layer_that_is_not_in_the_stack_or_is_the_findings_own_pr_refuses[99]
1 failed in 1.55s
```

**Restore:** `higher = True` → the original expression (inverse edit).
**Restore receipt** (`grep -n "higher = kind"` after the restore): `934:            higher = kind == "stack" and layer in allowed and r["pr"] in allowed and allowed.index(layer) > allowed.index(r["pr"])`

**Green run** (same node, after the restore, complete):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 6.08s
```

---

## C2 — the auto-accounting skip (`_check_accounting`)

**Guarded element:** `pr_sheet.py:872` `if bullet in auto:` (the fixed-above bullet takes no accounting entry and an entry for it is refused).
**Axis:** a fixed-above bullet the build shows in caught is accounted by itself.

**Neutralization:** `if bullet in auto:` → `if False and bullet in auto:` (the bullet is never skipped).

**Red run** (`test_s1_a_finding_fixed_by_the_layer_above_is_caught_as_fixed_above_and_needs_no_entry_or_accounting`). INCOMPLETE: the tool that ran the command truncated its output (1300 characters in the middle of pytest's printout of `build()`'s source, shown below as the elision); what follows is what was delivered, with the middle of that source printout elided by me and marked, nothing else changed:
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_s1_a_finding_fixed_by_the_layer_above_is_caught_as_fixed_above_and_needs_no_entry_or_accounting _

    def test_s1_a_finding_fixed_by_the_layer_above_is_caught_as_fixed_above_and_needs_no_entry_or_accounting():
        # Bites on: the stack sheet refusing a fixed-above finding for a missing leftovers entry or an unaccounted bullet, or showing it as a card.
        # Axis: I-SHEET: a valid fixed-above disposition lands in caught, takes no card, no decided-for-you entry and no accounting.
>       sheet = make(stack_records(), stack_input(), fixed_bodies())
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2332/plugins/superheroes/lib/tests/test_pr_sheet_fixed_above_2332.py:60: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt-2332/plugins/superheroes/lib/tests/test_pr_sheet_fixed_above_2332.py:44: in make
    return pr_sheet.build(copy.deepcopy(records), copy.deepcopy(advisor), WORDS, bodies=copy.deepcopy(bodies))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

records = [{'schema': 'review-record/1', 'pr': 10, ...}, ...]   (as in C1)
advisor = {'schema': 'pr-sheet-input/1', 'kind': 'stack', 'number': 9, 'title': 'Balances', ...}
bodies = {10: "## What we're accepting\n\n- f-2 The old balance is rounded twice — fixed-above #11 1a2b3c4: the layer above removes it.\n", 11: "## What we're accepting\n\nNone\n"}

    def build(records, advisor, words, place=None, previous=None, bodies=None, spec_base=None):
        [... pytest's printout of build()'s source: elided here; the tool had cut a further 1300 characters of it ...]
        if problems:
>           raise Refusal(problems)
E           pr_sheet.Refusal: ['PR #10\'s acceptance 10:31dc1e1f88 ("f-2 The old balance is rounded twice — fixed-above #11 1a2b3c4: the layer above …") is not accounted for: give accounting "10:31dc1e1f88" one of item, fold with line, leftover, or canon']

/home/user/wt-2332/plugins/superheroes/lib/pr_sheet.py:1182: Refusal
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_pr_sheet_fixed_above_2332.py::test_s1_a_finding_fixed_by_the_layer_above_is_caught_as_fixed_above_and_needs_no_entry_or_accounting
1 failed in 1.99s
```

**Restore:** `if False and bullet in auto:` → `if bullet in auto:` (inverse edit).
**Restore receipt** (`grep -n -A1 "if bullet in auto:\|if False and bullet"` after the restore):
```
872:            if bullet in auto:
873-                if bullet in accounting:
```

**Green run** (same node, after the restore, complete):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.12s
```

---

## C3 — the listed-state exclusion (`build`)

**Guarded element:** `pr_sheet.py:1307` `left = {pr: [(bullet, text) for bullet, text in bullets if bullet not in auto] for ...}` (the bullets `nothingListed` and `canonAccounted` are read from).
**Axis:** a fixed-above bullet is accounted by itself and never counts toward the listed state.

**Neutralization:** `if bullet not in auto]` → `if True]` (every bullet counts again).

**Red run** (`test_s5_when_the_only_listed_bullet_is_fixed_above_nothing_is_listed`). INCOMPLETE: the tool that ran the command truncated its output (11268 characters in the middle of pytest's printout of `build()`'s source); what follows is what was delivered, with the middle of that printout elided by me and marked. The red is an error, not an assertion: with the bullet counted, `canonAccounted` is read from an accounting entry that the bullet (accounted by itself) does not have:
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_s5_when_the_only_listed_bullet_is_fixed_above_nothing_is_listed _____

    def test_s5_when_the_only_listed_bullet_is_fixed_above_nothing_is_listed():
        # Bites on: a fixed-above bullet counted as a listed acceptance.
        # Axis: the listed state is read over the bullets the build does not account by themselves.
>       prsheet = make(stack_records(), stack_input(), fixed_bodies())["prSheet"]
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2332/plugins/superheroes/lib/tests/test_pr_sheet_fixed_above_2332.py:121: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt-2332/plugins/superheroes/lib/tests/test_pr_sheet_fixed_above_2332.py:44: in make
    return pr_sheet.build(copy.deepcopy(records), copy.deepcopy(advisor), WORDS, bodies=copy.deepcopy(bodies))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

records = [{'schema': 'review-record/1', 'pr': 10, ...}, ...]   (as in C1)
advisor = {'schema': 'pr-sheet-input/1', 'kind': 'stack', 'number': 9, 'title': 'Balances', ...}
bodies = {10: "## What we're accepting\n\n- f-2 The old balance is rounded twice — fixed-above #11 1a2b3c4: the layer above removes it.\n", 11: "## What we're accepting\n\nNone\n"}

    def build(records, advisor, words, place=None, previous=None, bodies=None, spec_base=None):
        [... pytest's printout of build()'s source: elided here; the tool had cut a further 11268 characters of it ...]
        # axis: a fixed-above bullet is accounted by itself and never counts toward the listed state
        left = {pr: [(bullet, text) for bullet, text in bullets if True] for pr, bullets in listed.items()}
        if bodies is not None and not any(left.values()):  # every covered body was read and none lists an acceptance (but a fixed-above one)
            sheet["nothingListed"] = True
        elif bodies is not None:  # at least one is listed: Canon alone covers them all when every bullet is accounted to a Canon ruling
            accounting = advisor.get("accounting", {})
>           rulings = [accounting[bullet].get("canon") for bullets in left.values() for bullet, _ in bullets]
                       ^^^^^^^^^^^^^^^^^^
E           KeyError: '10:31dc1e1f88'

/home/user/wt-2332/plugins/superheroes/lib/pr_sheet.py:1312: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_pr_sheet_fixed_above_2332.py::test_s5_when_the_only_listed_bullet_is_fixed_above_nothing_is_listed
1 failed in 1.24s
```

**Restore:** `if True]` → `if bullet not in auto]` (inverse edit).
**Restore receipt** (`grep -n "    left = {pr:"` after the restore): `1307:    left = {pr: [(bullet, text) for bullet, text in bullets if bullet not in auto] for pr, bullets in listed.items()}`

**Green run** (same node, after the restore, complete):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.98s
```

---

## C4 — the refusal of a leftovers or craftDeterminations entry on a fixed-above finding (`build`)

**Guarded element:** `pr_sheet.py:1148` `if call_at is not None or det_at is not None:` → "is fixed above in #N; give it no leftovers or craftDeterminations entry".
**Axis:** a finding fixed above takes no leftovers or craftDeterminations entry.

**Neutralization:** `if call_at is not None or det_at is not None:` → `if False and (call_at is not None or det_at is not None):`.

**Red run** (`test_s4_a_leftovers_entry_for_a_finding_fixed_above_refuses`, complete):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_s4_a_leftovers_entry_for_a_finding_fixed_above_refuses __________

    def test_s4_a_leftovers_entry_for_a_finding_fixed_above_refuses():
        # Bites on: the refusal of a leftovers entry on a finding the body marks fixed above.
        # Axis: a fixed-above finding takes no leftovers entry.
        entry = {"why": "Only you can say.", "context": "It happened.", "options": "none"}
>       problems = refused(stack_records(), stack_input(leftovers={"10:f-2": entry}), fixed_bodies())
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2332/plugins/superheroes/lib/tests/test_pr_sheet_fixed_above_2332.py:100: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

records = [{'schema': 'review-record/1', 'pr': 10, 'sessionId': 'session-5', 'lane': {'value': 'full', 'reason': 'A new table ho...ssionId': 'session-5', 'lane': {'value': 'full', 'reason': 'A new table holds money.', 'source': 'PR lane call'}, ...}]
advisor = {'schema': 'pr-sheet-input/1', 'kind': 'stack', 'number': 9, 'title': 'Balances', ...}
bodies = {10: "## What we're accepting\n\n- f-2 The old balance is rounded twice — fixed-above #11 1a2b3c4: the layer above removes it.\n", 11: "## What we're accepting\n\nNone\n"}

    def refused(records, advisor, bodies):
>       with pytest.raises(pr_sheet.Refusal) as caught:
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE Refusal

/home/user/wt-2332/plugins/superheroes/lib/tests/test_pr_sheet_fixed_above_2332.py:48: Failed
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_pr_sheet_fixed_above_2332.py::test_s4_a_leftovers_entry_for_a_finding_fixed_above_refuses
1 failed in 1.23s
```

**Restore:** `if False and (call_at is not None or det_at is not None):` → `if call_at is not None or det_at is not None:` (inverse edit).
**Restore receipt** (`grep -n "if call_at is not None or det_at is not None:\|if False and"` after the restore): `1148:                    if call_at is not None or det_at is not None:`

**Green run** (same node, after the restore, complete):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.93s
```

---

Not proven by a neutralization of its own (declared set is C1–C4): the craftDeterminations half of C4
(`test_s4_a_craft_determination_for_a_finding_fixed_above_refuses`) shares C4's guard line and was not run red alone;
the accounting-entry refusal of C2 (`test_s4_an_accounting_entry_for_the_fixed_above_bullet_refuses`) shares C2's
guard and was not run red alone; E5 (a carried sheet) and E2 (`Unreadable`) have tests only for E2
(`test_a_record_the_rule_cannot_read_is_a_problem_naming_the_pr_never_a_pass`), none for E5.
