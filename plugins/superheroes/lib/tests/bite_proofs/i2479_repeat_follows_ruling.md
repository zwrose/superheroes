# Bite-proof record — a kept repeat follows its earlier finding's cited ruling (#2479)

Detector file: `plugins/superheroes/lib/tests/test_review_record_repeat_follows_ruling_2479.py`, unedited between each red and its green (one exception, named in entry 0 and entry 2). Every entry is a targeted, reversible edit to one production file (`plugins/superheroes/lib/review_record.py`, function `_follow_repeats`), made and undone with the edit tool (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2479 -m pytest '<exact node id>' -q`, one test node each; output captured whole; the `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out of each capture. No secret, token, URL beyond the test fixture's placeholder comment link, or personal data appears in any capture, so nothing is redacted. The restore receipt of each entry is the restored line, quoted from a content search run on its own after the inverse edit; the green run follows it.

Guarded elements, one entry each, none grouped: 1 the ruling branch's gate, 2 the `on_record` check, 3 the repeat's left-for-owner condition, 4 the `decidedBy` copy on the repeat, 5 the reason leading with the citation text, 6 the `decidedBy` copy on each merged member. Entry 0 is the field case run before `review_record.py` was edited at all.

## 0. Fails before — R1 on the unmodified base behaviour

- **Axis:** the field case. The owner ruled on the earlier finding's card; its kept left-for-owner repeat must read `ruling`.
- **Detector:** `test_review_record_repeat_follows_ruling_2479.py::test_r1_a_kept_repeat_of_a_finding_the_owner_ruled_on_reads_that_ruling_and_adds_no_card`.
- **Neutralization:** none; `review_record.py` was untouched when this ran. (The test's last line, the sheet-card assertion, was changed afterwards from a call with a leftovers entry for `f-2` to a call with none, because the sheet refuses a leftovers entry that names no left-for-owner finding; the failing assertion below comes before that line and is unaffected.)

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_r1_a_kept_repeat_of_a_finding_the_owner_ruled_on_reads_that_ruling_and_adds_no_card _

    def test_r1_a_kept_repeat_of_a_finding_the_owner_ruled_on_reads_that_ruling_and_adds_no_card():
        # axis: the field case, the owner ruled on the earlier finding's card, so its kept repeat reads the same ruling
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2479_repeat_follows_ruling.md
        rec = build([X, repeat()])
        rows = by_id(rec)
        assert rows["f-1"]["outcome"] == "ruling"
        r = rows["f-2"]
>       assert r["outcome"] == "ruling"
E       AssertionError: assert 'left-for-owner' == 'ruling'
E         
E         - ruling
E         + left-for-owner

/home/user/wt-2479/plugins/superheroes/lib/tests/test_review_record_repeat_follows_ruling_2479.py:76: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_ruling_2479.py::test_r1_a_kept_repeat_of_a_finding_the_owner_ruled_on_reads_that_ruling_and_adds_no_card
1 failed in 0.32s
```

## 1. The ruling branch's gate (`review_record.py:1928-1929`, `ruled = (...)`)

- **Axis:** the branch runs only when the earlier finding reads `ruling` with a cited decision (a dict) and the repeat is kept at left-for-owner.
- **Detector:** `test_review_record_repeat_follows_ruling_2479.py::test_r1_a_kept_repeat_of_a_finding_the_owner_ruled_on_reads_that_ruling_and_adds_no_card`.
- **Neutralization:** `            ruled = (sources is not None and g.get("outcome") == _RULING` became `            ruled = (False and sources is not None and g.get("outcome") == _RULING` (the branch never runs).

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_r1_a_kept_repeat_of_a_finding_the_owner_ruled_on_reads_that_ruling_and_adds_no_card _

    def test_r1_a_kept_repeat_of_a_finding_the_owner_ruled_on_reads_that_ruling_and_adds_no_card():
        # axis: the field case, the owner ruled on the earlier finding's card, so its kept repeat reads the same ruling
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2479_repeat_follows_ruling.md
        rec = build([X, repeat()])
        rows = by_id(rec)
        assert rows["f-1"]["outcome"] == "ruling"
        r = rows["f-2"]
>       assert r["outcome"] == "ruling"
E       AssertionError: assert 'left-for-owner' == 'ruling'
E         
E         - ruling
E         + left-for-owner

/home/user/wt-2479/plugins/superheroes/lib/tests/test_review_record_repeat_follows_ruling_2479.py:76: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_ruling_2479.py::test_r1_a_kept_repeat_of_a_finding_the_owner_ruled_on_reads_that_ruling_and_adds_no_card
1 failed in 0.34s
```

**Restore:** the inverse edit (`ruled = (False and sources is not None ...` back to `ruled = (sources is not None ...`). **Restore receipt** (restored lines, quoted from a content search run on its own):

```
1928:            ruled = (sources is not None and g.get("outcome") == _RULING
1929-                     and isinstance(session_contract.decided_by_of(g), dict) and f.get("outcome") == _LEFT_FOR_OWNER)
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.34s
```

## 2. The `on_record` check (`review_record.py:1936-1938`, `if not ok: continue`)

- **Axis:** the repeat reads a ruling only while the earlier finding's citation is on record now; otherwise nothing moves and the repeat is not marked handled.
- **Detector:** `test_review_record_repeat_follows_ruling_2479.py::test_r3_e1_the_follow_itself_leaves_the_repeat_alone_when_the_citation_is_not_on_record`.
- **Neutralization:** `                if not ok:` (inside the ruling branch, under `ok, text = finding_outcomes.on_record(...)`) became `                if False and not ok:` (the check always passes).

**Disclosure — unreachable through this entry point.** The build-level row R3 (`test_r3_e1_an_owner_ruling_that_does_not_resolve_leaves_the_repeat_held_behind_the_earlier_finding`, owner comment unreadable) does **not** go red under this neutralization. Run with the neutralization in place it printed (exit 0):

```
.                                                                        [100%]
1 passed in 0.34s
```

The public path that strips the input: `build_record` calls `_recheck_decisions` before `_follow_repeats`, and that function moves any `ruling` whose cited decision is not on record back to `left-for-owner` using the same cached `sources()` read, so the earlier finding is never a `ruling` with an unresolved citation when the follow runs. The proof that does bite is the unit-level seam: `_follow_repeats` called directly (`review_record.py:1883` onward) with a `ruling` earlier finding and a `sources` callable that does not resolve it, in the new test `test_r3_e1_the_follow_itself_leaves_the_repeat_alone_when_the_citation_is_not_on_record` (written after the build-level row showed it could not bite, and run for the red below with the neutralization still in place).

**Raw red** (exit 1; the closing "Full output truncated" line is pytest's own text, quoted as received):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_r3_e1_the_follow_itself_leaves_the_repeat_alone_when_the_citation_is_not_on_record _

    def test_r3_e1_the_follow_itself_leaves_the_repeat_alone_when_the_citation_is_not_on_record():
        # axis: the follow checks the citation on its own, so a ruling the record writer did not re-check never moves a repeat
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2479_repeat_follows_ruling.md
        # (build_record demotes an unresolved ruling before the follow, so only a direct call delivers this input to the check)
        by = {"kind": "owner-ruling", "ref": {"url": U, "words": W}}
        ruled = dict(X, outcome="ruling", reason="the owner ruled", decidedBy=by)
        findings = [ruled, repeat()]
        before = copy.deepcopy(findings)
>       assert rr._follow_repeats(findings, [], lambda: {}) == before
E       assert [{'id': 'f-1'... 'a.py', ...}] == [{'id': 'f-1'... 'a.py', ...}]
E         
E         At index 1 diff: {'id': 'f-2', 'title': 'Same mistake again', 'severity': 'Important', 'file': 'a.py', 'line': 12, 'body': 'b', 'consequence': 'the total on the page is wrong', 'outcome': 'ruling', 'reason': "the ruling's link is not in this repository; repeat of f-1, which that ruling settled, so it reads the ruling; earlier: repeat of f-1; keeps its earlier outcome (left-for-owner)", 'reviewer': 'r1', 'repeatOf': {'findingKey': 'rr1:71df46e158ff0278476bc8e3c9417b66', 'id': 'f-1', 'fixHolds': None, 'kept': {'outcome': 'ruling', 'verdict': 'wrong'}}, 'decidedBy': {'kind...
E         
E         ...Full output truncated, use '-vv' to show

/home/user/wt-2479/plugins/superheroes/lib/tests/test_review_record_repeat_follows_ruling_2479.py:125: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_ruling_2479.py::test_r3_e1_the_follow_itself_leaves_the_repeat_alone_when_the_citation_is_not_on_record
1 failed in 0.34s
```

**Restore:** the inverse edit (`if False and not ok:` back to `if not ok:`). **Restore receipt** (restored lines, quoted from a content search run on its own; line 845 is an unrelated `chk` helper):

```
844-    def chk(ok, key):
845:        if not ok:
846-            raise Refusal("review-account-invalid", key)
--
1936-                ok, text = finding_outcomes.on_record(g["decidedBy"], sources())
1937:                if not ok:
1938-                    continue
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.33s
```

## 3. The repeat's left-for-owner condition (`review_record.py:1929`, `and f.get("outcome") == _LEFT_FOR_OWNER`)

- **Axis:** only a repeat kept at left-for-owner follows a ruling; one kept at another outcome (here `craft`) stays as it is.
- **Detector:** `test_review_record_repeat_follows_ruling_2479.py::test_r5_e3_a_repeat_kept_at_another_outcome_is_unchanged_whatever_its_earlier_finding_reads`.
- **Neutralization:** `and isinstance(session_contract.decided_by_of(g), dict) and f.get("outcome") == _LEFT_FOR_OWNER)` became `and isinstance(session_contract.decided_by_of(g), dict))` (the condition dropped).

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_r5_e3_a_repeat_kept_at_another_outcome_is_unchanged_whatever_its_earlier_finding_reads _

    def test_r5_e3_a_repeat_kept_at_another_outcome_is_unchanged_whatever_its_earlier_finding_reads():
        # axis: only a repeat kept at left-for-owner follows a ruling; one kept at craft stays craft
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2479_repeat_follows_ruling.md
        given = repeat("craft")
        rec = build([X, given])
        rows = by_id(rec)
        assert rows["f-1"]["outcome"] == "ruling"
        r = rows["f-2"]
>       assert (r["outcome"], r["reason"], r["repeatOf"]) == ("craft", OLD, given["repeatOf"])
E       AssertionError: assert ('ruling', 'o...t': 'wrong'}}) == ('craft', 're...t': 'wrong'}})
E         
E         At index 0 diff: 'ruling' != 'craft'
E         Use -v to get more diff

/home/user/wt-2479/plugins/superheroes/lib/tests/test_review_record_repeat_follows_ruling_2479.py:162: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_ruling_2479.py::test_r5_e3_a_repeat_kept_at_another_outcome_is_unchanged_whatever_its_earlier_finding_reads
1 failed in 0.35s
```

**Restore:** the inverse edit. **Restore receipt** (restored lines):

```
1928:            ruled = (sources is not None and g.get("outcome") == _RULING
1929-                     and isinstance(session_contract.decided_by_of(g), dict) and f.get("outcome") == _LEFT_FOR_OWNER)
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.33s
```

## 4. The `decidedBy` copy on the repeat (`review_record.py:1941`, `by = copy.deepcopy(g["decidedBy"])`)

- **Axis:** the repeat carries its own copy of the earlier finding's cited decision, so a later write re-checks it and demotes it when the citation stops resolving.
- **Detector:** `test_review_record_repeat_follows_ruling_2479.py::test_r8_b1_a_merged_member_follows_with_its_own_copy_and_all_demote_when_the_citation_stops_resolving` (R1 also goes red on this element through its `decidedBy` assertion, not run separately).
- **Neutralization:** `                by = copy.deepcopy(g["decidedBy"])` became `                by = None` (the repeat reads `ruling` with no citation).

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_r8_b1_a_merged_member_follows_with_its_own_copy_and_all_demote_when_the_citation_stops_resolving _

    def test_r8_b1_a_merged_member_follows_with_its_own_copy_and_all_demote_when_the_citation_stops_resolving():
        # axis: each member moved to ruling carries its own decidedBy, so a later write that cannot resolve it demotes it
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2479_repeat_follows_ruling.md
        rec = build([X, member_repeat(), member()])
        rows = by_id(rec)
        m = rows["f-3"]
        assert (rows["f-2"]["outcome"], m["outcome"]) == ("ruling", "ruling")
        assert m["decidedBy"] == rows["f-1"]["decidedBy"] and m["decidedBy"] is not rows["f-1"]["decidedBy"]
        assert m["reason"] == (f'{CITATION}; ' + rr.REPEAT_MEMBER_FOLLOWS_RULING.format(name="f-2") + "; earlier: " + WAS)
        assert rec["leftForOwner"] == []
        later = rebuild(rec, doc=None)
>       assert {i: row["outcome"] for i, row in by_id(later).items()} == {"f-1": LFO, "f-2": LFO, "f-3": LFO}
E       AssertionError: assert {'f-1': 'left...ft-for-owner'} == {'f-1': 'left...ft-for-owner'}
E         
E         Omitting 2 identical items, use -vv to show
E         Differing items:
E         {'f-2': 'ruling'} != {'f-2': 'left-for-owner'}
E         Use -v to get more diff

/home/user/wt-2479/plugins/superheroes/lib/tests/test_review_record_repeat_follows_ruling_2479.py:208: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_ruling_2479.py::test_r8_b1_a_merged_member_follows_with_its_own_copy_and_all_demote_when_the_citation_stops_resolving
1 failed in 0.35s
```

**Restore:** the inverse edit. **Restore receipt** (restored line):

```
1941:                by = copy.deepcopy(g["decidedBy"])
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.32s
```

## 5. The reason leading with the citation text (`review_record.py:1943`, `reason = f"{text}; ..."`)

- **Axis:** the inherited reason starts with the citation text exactly, so the refresh in `_recheck_decisions` on a later write (`reason.startswith(refreshed)`) never prepends it a second time.
- **Detector:** `test_review_record_repeat_follows_ruling_2479.py::test_r7_b3_a_later_write_of_the_same_findings_shows_the_citation_once`.
- **Neutralization:** `                reason = f"{text}; {REPEAT_FOLLOWS_RULING.format(name=_name(g))}"` became `                reason = f"{REPEAT_FOLLOWS_RULING.format(name=_name(g))}; {text}"` (the citation moves to the end).

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_r7_b3_a_later_write_of_the_same_findings_shows_the_citation_once _____

    def test_r7_b3_a_later_write_of_the_same_findings_shows_the_citation_once():
        # axis: the inherited reason leads with the citation text, so the refresh on a later write never prepends it again
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2479_repeat_follows_ruling.md
        rec = build([X, repeat()])
        again = rebuild(rec)
        r = by_id(again)["f-2"]
        assert r["outcome"] == "ruling" and r["decidedBy"] == by_id(rec)["f-2"]["decidedBy"]
>       assert r["reason"].count(CITATION) == 1
E       assert 2 == 1
E        +  where 2 = <built-in method count of str object at 0x7fa62e024450>('owner ruling "ship it as is" (https://github.com/o/r/issues/12#issuecomment-555)')
E        +    where <built-in method count of str object at 0x7fa62e024450> = 'owner ruling "ship it as is" (https://github.com/o/r/issues/12#issuecomment-555); repeat of f-1, which that ruling se...https://github.com/o/r/issues/12#issuecomment-555); earlier: repeat of f-1; keeps its earlier outcome (left-for-owner)'.count

/home/user/wt-2479/plugins/superheroes/lib/tests/test_review_record_repeat_follows_ruling_2479.py:191: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_ruling_2479.py::test_r7_b3_a_later_write_of_the_same_findings_shows_the_citation_once
1 failed in 0.34s
```

**Restore:** the inverse edit. **Restore receipt** (restored line):

```
1943:                reason = f"{text}; {REPEAT_FOLLOWS_RULING.format(name=_name(g))}"
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.31s
```

## 6. The `decidedBy` copy on each merged member (`review_record.py:1953`, `decidedBy=copy.deepcopy(g["decidedBy"])`)

- **Axis:** every member moved to `ruling` carries its own copy of the cited decision; an uncited ruling would never be re-checked on a later write.
- **Detector:** `test_review_record_repeat_follows_ruling_2479.py::test_r8_b1_a_merged_member_follows_with_its_own_copy_and_all_demote_when_the_citation_stops_resolving`.
- **Neutralization:** `                        h, outcome=_RULING, decidedBy=copy.deepcopy(g["decidedBy"]),` became `                        h, outcome=_RULING,` (the member reads `ruling` with no citation).

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_r8_b1_a_merged_member_follows_with_its_own_copy_and_all_demote_when_the_citation_stops_resolving _

    def test_r8_b1_a_merged_member_follows_with_its_own_copy_and_all_demote_when_the_citation_stops_resolving():
        # axis: each member moved to ruling carries its own decidedBy, so a later write that cannot resolve it demotes it
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2479_repeat_follows_ruling.md
        rec = build([X, member_repeat(), member()])
        rows = by_id(rec)
        m = rows["f-3"]
        assert (rows["f-2"]["outcome"], m["outcome"]) == ("ruling", "ruling")
>       assert m["decidedBy"] == rows["f-1"]["decidedBy"] and m["decidedBy"] is not rows["f-1"]["decidedBy"]
               ^^^^^^^^^^^^^^
E       KeyError: 'decidedBy'

/home/user/wt-2479/plugins/superheroes/lib/tests/test_review_record_repeat_follows_ruling_2479.py:204: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_repeat_follows_ruling_2479.py::test_r8_b1_a_merged_member_follows_with_its_own_copy_and_all_demote_when_the_citation_stops_resolving
1 failed in 0.37s
```

**Restore:** the inverse edit. **Restore receipt** (restored lines):

```
1953:                        h, outcome=_RULING, decidedBy=copy.deepcopy(g["decidedBy"]),
1954-                        reason=f"{note}; earlier: {was}" if isinstance(was, str) and was else note)
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.35s
```
