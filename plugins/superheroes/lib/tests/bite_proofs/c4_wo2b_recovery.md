# C4 WO-2B bite-proof — sweep recovery from an abandoned session, the ungraded reason, the PR-body guard

**Provenance:** claude (implementer), work order WO-2B. Detector files: `plugins/superheroes/lib/tests/test_c4_sweep_recovery.py` (and, for r4,
`plugins/superheroes/lib/tests/test_c4_sweep.py`, run and not edited). Worktree `/home/user/sh-2305`, branch
`claude/issue-2305-workhorse-rq185r`, base HEAD `b7e2f71d`.
Every run is `timeout 900 scripts/pinned-python -B -X pycache_prefix=/tmp/sh2305-pyc -m pytest "<node id>" -q -x` from the worktree, the detector
unedited, on the node named in each entry. Each neutralization is one targeted Edit of the product file, undone by the inverse Edit; the restore receipt
is the restored line quoted back by `grep -n` (or the neutralization's inverse shown in the diff) and the green run of the same node. Captures are far under
the 32 KiB / 128 KiB ceilings. Nothing was redacted (no credential-like text appears). Dropped from every capture: the `UV_NATIVE_TLS` deprecation
warning line (it is printed once per run); the temp-directory names are as the run printed them. The `====`/`!!!!` rule lines of pytest's
banners were copied by hand and their fill widths may differ by a character from the terminal's; every assertion line, node id, line number and
count is as printed.

## Guarded elements (declared in WO-2B) — one neutralization and one red each, no groups, none unproven

| ID | Guarded element (axis) | File : site | Detector node |
|---|---|---|---|
| r1 | recovery reads the stored searcher results from `_search_slots` | `review_record_session.py` `_unswept` | `test_r1_an_abandoned_session_recovers_the_outside_hit_under_its_sweep_and_the_inside_hit_as_open` |
| r2 | only a sweep still in `_sweepPending` is recovered | `review_record_session.py` `_unswept` | `test_r4_a_sweep_no_longer_pending_recovers_nothing_a_second_time` |
| r3 | a recovered outside hit goes through `add_sweep_hit`, not `add_outside_hit` | `review_record_session.py` `_with_recovered_outside` | `test_r1_an_abandoned_session_recovers_the_outside_hit_under_its_sweep_and_the_inside_hit_as_open` |
| r4 | the same place found twice is one hit | `session_contract.py` `classify_sweep_hits` | `test_r2_the_same_hit_stored_by_two_parts_is_recovered_once_and_the_first_what_wins` and `test_c4_sweep.py::test_s4_the_same_place_found_by_two_parts_is_one_hit_and_the_first_what_wins` |
| r5 | a hit at the parent's place or one of its places is covered | `session_contract.py` `classify_sweep_hits` | `test_r3_a_covered_hit_recovers_nothing` |
| r6 | a PR-body citation is dropped | `session_contract.py` `classify_sweep_hits` | `test_r3_a_pr_body_citation_hit_recovers_nothing` |
| r7 | `_slots` keeps review slots only | `review_record_session.py` `_slots` | `test_r5_no_searcher_is_a_reviewer_in_an_abandoned_session` |
| r8 | the ungraded reason is applied where `STILL_OPEN` is chosen | `review_record_session.py` `_findings_and_merges` (feeds `_decide` and the no-ledger branch) | `test_r7_an_ungraded_sweep_hit_reads_open_with_the_reason_it_was_withheld` |
| r9 | the CITATION guard of `_outside_the_round` | `review_record_session.py` `_outside_the_round` | `test_r8_the_pr_body_citation_is_never_outside_the_round` |
| r10 | no readable scope: every hit is outside, never inside | `review_record_session.py` `_unswept` | `test_r9_a_result_with_no_readable_scope_is_recovered_as_outside_only` |

Limits stated plainly. r8 neutralizes the one source of the keys (`ungraded = set()`), which silences all three `STILL_OPEN` sites at once; the detector
reaches the `_decide` site (the finding has a ledger row). The third site (a live finding with no ledger row) has no test of its own, because a hit the
driver withheld always has a ledger row; that site is therefore not separately proven. r2 neutralizes the loop's source (`for sweep in pending` becomes a loop
over the stored sweeps), and `-x` stops the node at its first parametrization, `folded-and-cleared`; the other two parametrizations (`another-sweep`,
`not-a-list`) are not shown red here.

## r1 — recovery reads `_search_slots`

**neutralization** (`review_record_session.py`, `_unswept`):
```diff
-    for key, (att, _) in _search_slots(rows).items():
+    for key, (att, _) in {}.items():
```
**raw red**:
```
F
=================================== FAILURES ===================================
_ test_r1_an_abandoned_session_recovers_the_outside_hit_under_its_sweep_and_the_inside_hit_as_open _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-64/test_r1_an_abandoned_session_r0')

    def test_r1_an_abandoned_session_recovers_the_outside_hit_under_its_sweep_and_the_inside_hit_as_open(tmp_path):
        # axis: a stored searcher result is read from the search slots, which `_slots` never holds — see bite-proof record c4_wo2b_recovery
        # axis: a recovered sweep hit lands under its sweep's own entry, never a reviewer's — see bite-proof record c4_wo2b_recovery
        session = _stored(tmp_path, {SEAT_1: _hits(INSIDE, OUTSIDE)}, outsideThisPR=[REVIEWER_ENTRY])
        account = _account(session)
        assert account["outsideThisPR"][0] == REVIEWER_ENTRY
>       assert _sweep_entries(account) == [{"source": {"kind": "sweep", "name": "searchers", "sweepId": "S-1"},
                                            "hits": [{"id": "O-2", "file": "o.py", "line": 3, "title": "outside copy"}]}]
E       AssertionError: assert [] == [{'source': {...side copy'}]}]
E         
E         Right contains one more item: {'source': {'kind': 'sweep', 'name': 'searchers', 'sweepId': 'S-1'}, 'hits': [{'id': 'O-2', 'file': 'o.py', 'line': 3, 'title': 'outside copy'}]}
E         Use -v to get more diff

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep_recovery.py:97: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep_recovery.py::test_r1_an_abandoned_session_recovers_the_outside_hit_under_its_sweep_and_the_inside_hit_as_open
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.49s
```
**restore**: the inverse Edit. **restore receipt** (`grep -n "_search_slots(rows).items()"`): `1023:    for key, (att, _) in _search_slots(rows).items():`
**raw green**: `.   [100%]` / `1 passed in 0.57s`

## r2 — the `_sweepPending` gate

**neutralization** (`review_record_session.py`, `_unswept`):
```diff
-    for sweep in pending:
+    for sweep in [{"sweepId": s} for s in stored]:
```
**raw red** (`-x` stops at the first parametrization):
```
F
=================================== FAILURES ===================================
_ test_r4_a_sweep_no_longer_pending_recovers_nothing_a_second_time[folded-and-cleared] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-66/test_r4_a_sweep_no_longer_pend0')
held = {'_sweepPending': []}

    def test_r4_a_sweep_no_longer_pending_recovers_nothing_a_second_time(tmp_path, held):
        # axis: a sweep no longer pending was folded and its hits are in the state, so it recovers nothing — see bite-proof record c4_wo2b_recovery
        state = dict(held, outsideThisPR=[REVIEWER_ENTRY])
        account = _account(_stored(tmp_path, {SEAT_1: _hits(INSIDE, OUTSIDE)}, **state))
>       assert account["findings"] == [] and _sweep_entries(account) == []
E       AssertionError: assert ([{'id': 'u.py...': None, ...}] == []
E         
E         Left contains one more item: {'id': 'u.py::inside copy@L8', 'findingKey': 'u.py::inside copy@L8', 'title': 'inside copy', 'severity': None, ...}
E         Use -v to get more diff)

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep_recovery.py:173: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep_recovery.py::test_r4_a_sweep_no_longer_pending_recovers_nothing_a_second_time[folded-and-cleared]
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.56s
```
**restore**: the inverse Edit. **restore receipt** (`grep -n "    for sweep in pending:"`): `1031:    for sweep in pending:`
**raw green**: `...   [100%]` / `3 passed in 0.40s`

## r3 — `add_sweep_hit`, not `add_outside_hit`

**neutralization** (`review_record_session.py`, `_with_recovered_outside`):
```diff
-        sc.add_sweep_hit(entries, sweep_id, sc.SWEEP_SOURCE_NAME, file, line, title)
+        sc.add_outside_hit(entries, sc.SWEEP_SOURCE_NAME, file, line, title)
```
**raw red** (the hit lands on a `kind: "reviewer"` entry named `searchers`, so the sweep-entry filter finds none):
```
F
=================================== FAILURES ===================================
_ test_r1_an_abandoned_session_recovers_the_outside_hit_under_its_sweep_and_the_inside_hit_as_open _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-68/test_r1_an_abandoned_session_r0')

    def test_r1_an_abandoned_session_recovers_the_outside_hit_under_its_sweep_and_the_inside_hit_as_open(tmp_path):
        # axis: a stored searcher result is read from the search slots, which `_slots` never holds — see bite-proof record c4_wo2b_recovery
        # axis: a recovered sweep hit lands under its sweep's own entry, never a reviewer's — see bite-proof record c4_wo2b_recovery
        session = _stored(tmp_path, {SEAT_1: _hits(INSIDE, OUTSIDE)}, outsideThisPR=[REVIEWER_ENTRY])
        account = _account(session)
        assert account["outsideThisPR"][0] == REVIEWER_ENTRY
>       assert _sweep_entries(account) == [{"source": {"kind": "sweep", "name": "searchers", "sweepId": "S-1"},
                                            "hits": [{"id": "O-2", "file": "o.py", "line": 3, "title": "outside copy"}]}]
E       AssertionError: assert [] == [{'source': {...side copy'}]}]
E         
E         Right contains one more item: {'source': {'kind': 'sweep', 'name': 'searchers', 'sweepId': 'S-1'}, 'hits': [{'id': 'O-2', 'file': 'o.py', 'line': 3, 'title': 'outside copy'}]}
E         Use -v to get more diff

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep_recovery.py:97: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep_recovery.py::test_r1_an_abandoned_session_recovers_the_outside_hit_under_its_sweep_and_the_inside_hit_as_open
!!!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.41s
```
**restore**: the inverse Edit. **restore receipt** (`grep -n "sc.add_sweep_hit(entries"`): `918:        sc.add_sweep_hit(entries, sweep_id, sc.SWEEP_SOURCE_NAME, file, line, title)`
**raw green**: `.   [100%]` / `1 passed in 0.55s`

## r4 — the de-dup in `classify_sweep_hits`

**neutralization** (`session_contract.py`, `classify_sweep_hits`):
```diff
-        if (file, line) in seen:
+        if False and (file, line) in seen:
             continue
```
**raw red** (recovery's node, `test_c4_sweep_recovery.py::test_r2_...`):
```
F
=================================== FAILURES ===================================
_ test_r2_the_same_hit_stored_by_two_parts_is_recovered_once_and_the_first_what_wins _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-70/test_r2_the_same_hit_stored_by0')

    def test_r2_the_same_hit_stored_by_two_parts_is_recovered_once_and_the_first_what_wins(tmp_path):
        # axis: the same place found twice is one hit, the first kept — see bite-proof record c4_wo2b_recovery
        session = _stored(tmp_path, {SEAT_2: _hits(dict(OUTSIDE, what="second"), dict(INSIDE, what="second")),
                                     SEAT_1: _hits(dict(OUTSIDE, what="first"), dict(INSIDE, what="first"))})
        account = _account(session)
>       assert [h["title"] for e in _sweep_entries(account) for h in e["hits"]] == ["first"]  # part order, not storage order
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AssertionError: assert ['first', 'second'] == ['first']
E         
E         Left contains one more item: 'second'
E         Use -v to get more diff

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep_recovery.py:125: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep_recovery.py::test_r2_the_same_hit_stored_by_two_parts_is_recovered_once_and_the_first_what_wins
!!!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.52s
```
**raw red** (the driver's node, `test_c4_sweep.py::test_s4_the_same_place_found_by_two_parts_is_one_hit_and_the_first_what_wins`, same neutralization still in place):
```
F
=================================== FAILURES ===================================
_ test_s4_the_same_place_found_by_two_parts_is_one_hit_and_the_first_what_wins _

world = <test_break_it_loop.World object at 0x7f40fb637fb0>

    def test_s4_the_same_place_found_by_two_parts_is_one_hit_and_the_first_what_wins(world):
        _to_sweep(world)
        state = _sweep(world, {_seat("S-1", 1): [_hit(1, "README.md", "first words")],
                               _seat("S-1", 2): [_hit(1, "README.md", "other words")]})
        (entry,) = _sweep_entries(state)
>       assert [h["title"] for h in entry["hits"]] == ["first words"] and _rows(state)[0]["outside"] == 1
E       AssertionError: assert (['first words', 'other words'] == ['first words']
E         
E         Left contains one more item: 'other words'
E         Use -v to get more diff)

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep.py:497: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep.py::test_s4_the_same_place_found_by_two_parts_is_one_hit_and_the_first_what_wins
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 2.20s
```
**restore**: the inverse Edit. **restore receipt** (`grep -n "if (file, line) in seen:"`): `593:        if (file, line) in seen:`
**raw green** (both nodes in one run): `..   [100%]` / `2 passed in 2.54s`

## r5 — the covered check

**neutralization** (`session_contract.py`, `classify_sweep_hits`):
```diff
-        if (file, line) in places:
+        if False and (file, line) in places:
             out["covered"] += 1
```
**raw red** (`-x` stops at the first parametrization, `parent-place`):
```
F
=================================== FAILURES ===================================
_____________ test_r3_a_covered_hit_recovers_nothing[parent-place] _____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-73/test_r3_a_covered_hit_recovers0')
hit = {'file': 'p.py', 'line': 5, 'what': "the parent's own place"}

    def test_r3_a_covered_hit_recovers_nothing(tmp_path, hit):
        # axis: a hit at the parent's own place or one of its places is covered, neither inside nor outside — see bite-proof record c4_wo2b_recovery
        account = _account(_stored(tmp_path, {SEAT_1: _hits(hit)}))
>       assert account["findings"] == [] and _sweep_entries(account) == []
E       assert ([] == []
E         
E         Use -v to get more diff and [{'source': {...own place"}]}] == []
E         
E         Left contains one more item: {'source': {'kind': 'sweep', 'name': 'searchers', 'sweepId': 'S-1'}, 'hits': [{'id': 'O-1', 'file': 'p.py', 'line': 5, 'title': "the parent's own place"}]}
E         Use -v to get more diff)

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep_recovery.py:139: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep_recovery.py::test_r3_a_covered_hit_recovers_nothing[parent-place]
!!!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.43s
```
**restore**: the inverse Edit. **restore receipt** (`grep -n "if (file, line) in places:"`): `597:        if (file, line) in places:`
**raw green**: `..   [100%]` / `2 passed in 0.54s`

## r6 — the PR-body-citation drop

**neutralization** (`session_contract.py`, `classify_sweep_hits`):
```diff
         if (not (isinstance(file, str) and file.strip()) or isinstance(line, bool) or not isinstance(line, int)
-                or file == pr_body_stage.CITATION):
+            ):
```
**raw red**:
```
F
=================================== FAILURES ===================================
_______________ test_r3_a_pr_body_citation_hit_recovers_nothing ________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-75/test_r3_a_pr_body_citation_hit0')

    def test_r3_a_pr_body_citation_hit_recovers_nothing(tmp_path):
        # axis: a hit citing the PR body is dropped and counted, never classified — see bite-proof record c4_wo2b_recovery
        account = _account(_stored(tmp_path, {SEAT_1: _hits({"file": pr_body_stage.CITATION, "line": 8, "what": "body"})}))
>       assert account["findings"] == [] and _sweep_entries(account) == []
E       AssertionError: assert ([{'id': 'SUPE...ortant', ...}] == []
E         
E         Left contains one more item: {'id': 'SUPERHEROES_PR_BODY.md::body@L8', 'findingKey': 'SUPERHEROES_PR_BODY.md::body@L8', 'title': 'body', 'severity': 'Important', ...}
E         Use -v to get more diff)

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep_recovery.py:158: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep_recovery.py::test_r3_a_pr_body_citation_hit_recovers_nothing
!!!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.38s
```
(The neutralized form was the two-line condition rewritten as one line ending `not isinstance(line, int)):`; the diff above shows its effect.)
**restore**: the inverse Edit. **restore receipt** (`grep -n "file == pr_body_stage.CITATION"`): `589:                or file == pr_body_stage.CITATION):`
**raw green**: `.   [100%]` / `1 passed in 0.39s`

## r7 — `_slots` admitting the search kind

**neutralization** (`review_record_session.py`, `_slots`):
```diff
-        if sc.run_kind_for_phase(phase) != sc.RUN_KIND_REVIEW or not (_int(rnd) and _int(att)):
+        if sc.run_kind_for_phase(phase) not in (sc.RUN_KIND_REVIEW, sc.RUN_KIND_SEARCH) or not (_int(rnd) and _int(att)):
```
**raw red**:
```
F
=================================== FAILURES ===================================
__________ test_r5_no_searcher_is_a_reviewer_in_an_abandoned_session ___________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-77/test_r5_no_searcher_is_a_revie0')

    def test_r5_no_searcher_is_a_reviewer_in_an_abandoned_session(tmp_path):
        # axis: `_slots` keeps review slots only, so a searcher is never a reviewer row — see bite-proof record c4_wo2b_recovery
        account = _account(_stored(tmp_path, {SEAT_1: _hits(INSIDE), SEAT_2: _hits(OUTSIDE)}))
>       assert not [n for n in _names(account["reviewers"]) if "searcher" in str(n)]
E       AssertionError: assert not ['sweep searcher:S-1:1 (round 1)', 'sweep searcher:S-1:2 (round 1)']

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep_recovery.py:212: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep_recovery.py::test_r5_no_searcher_is_a_reviewer_in_an_abandoned_session
!!!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.39s
```
**restore**: the inverse Edit. **restore receipt** (`grep -n "run_kind_for_phase(phase) !="`): `147:        if sc.run_kind_for_phase(phase) != sc.RUN_KIND_REVIEW or not (_int(rnd) and _int(att)):` and `163:        if sc.run_kind_for_phase(phase) != sc.RUN_KIND_SEARCH or not (_int(rnd) and _int(att)):` (the second is `_search_slots`)
**raw green**: `.   [100%]` / `1 passed in 0.43s`

## r8 — the ungraded reason

**neutralization** (`review_record_session.py`, `_findings_and_merges`):
```diff
-    ungraded = _ungraded_keys(state)
+    ungraded = set()
```
**raw red**:
```
F
=================================== FAILURES ===================================
___ test_r7_an_ungraded_sweep_hit_reads_open_with_the_reason_it_was_withheld ___

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-79/test_r7_an_ungraded_sweep_hit_0')

    def test_r7_an_ungraded_sweep_hit_reads_open_with_the_reason_it_was_withheld(tmp_path):
        # axis: a sweep hit the verifier did not grade reads open with that reason, not the generic one — see bite-proof record c4_wo2b_recovery
        session, key = _ungraded_session(tmp_path, keys=True)
        account = rs.account_from_session(session, extras(), Fake().readers())
        (finding,) = account["findings"]
>       assert finding["findingKey"] == key and finding["outcome"] is None and finding["reason"] == UNGRADED_REASON
E       AssertionError: assert ('u.py::ungraded site@L8' == 'u.py::ungraded site@L8'
E         
E           u.py::ungraded site@L8 and None is None and 'still open w...ew loop ended' == 'a repository...did not grade'
E         
E         - a repository-sweep hit the verifier did not grade
E         + still open when the review loop ended)

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep_recovery.py:271: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep_recovery.py::test_r7_an_ungraded_sweep_hit_reads_open_with_the_reason_it_was_withheld
!!!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.44s
```
**restore**: the inverse Edit. **restore receipt** (`grep -n "ungraded = _ungraded_keys(state)"`): `666:    ungraded = _ungraded_keys(state)`
**raw green**: `.   [100%]` / `1 passed in 0.43s`

## r9 — the `_outside_the_round` CITATION guard

**neutralization** (`review_record_session.py`, `_outside_the_round`):
```diff
-    if scope is None or not (isinstance(file, str) and file.strip()) or file == pr_body_stage.CITATION \
+    if scope is None or not (isinstance(file, str) and file.strip()) \
             or f.get("line") is None:
```
**raw red**:
```
F
=================================== FAILURES ===================================
___________ test_r8_the_pr_body_citation_is_never_outside_the_round ____________

    def test_r8_the_pr_body_citation_is_never_outside_the_round():
        # axis: the PR-body citation is in scope whatever the diff touches, so it is never recovered as outside — see bite-proof record c4_wo2b_recovery
        scope = {"u.py": {8}}
>       assert rs._outside_the_round({"file": pr_body_stage.CITATION, "line": 3}, scope) is None
E       AssertionError: assert 3 is None
E        +  where 3 = <function _outside_the_round at 0x7f51448ef240>({'file': 'SUPERHEROES_PR_BODY.md', 'line': 3}, {'u.py': {8}})
E        +    where <function _outside_the_round at 0x7f51448ef240> = rs._outside_the_round

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep_recovery.py:308: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep_recovery.py::test_r8_the_pr_body_citation_is_never_outside_the_round
!!!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.56s
```
**restore**: the inverse Edit. **restore receipt** (`grep -n "file == pr_body_stage.CITATION"`): `899:    if scope is None or not (isinstance(file, str) and file.strip()) or file == pr_body_stage.CITATION \`
**raw green**: `.   [100%]` / `1 passed in 0.39s`

## r10 — the no-scope branch

**neutralization** (`review_record_session.py`, `_unswept`):
```diff
-            hits, parent, lambda hit: scope is not None and _outside_the_round(hit, scope) is None)
+            hits, parent, lambda hit: scope is None or _outside_the_round(hit, scope) is None)
```
**raw red**:
```
F
=================================== FAILURES ===================================
_____ test_r9_a_result_with_no_readable_scope_is_recovered_as_outside_only _____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-83/test_r9_a_result_with_no_reada0')

    def test_r9_a_result_with_no_readable_scope_is_recovered_as_outside_only(tmp_path):
        # axis: with no readable scope no hit is known to be on a touched line, so every hit is recovered outside and none as open work — see bite-proof record c4_wo2b_recovery
        session = _stored(tmp_path, {SEAT_1: _hits(INSIDE, OUTSIDE)}, reviewedDiff=None)
        account = _account(session)
>       assert account["findings"] == []
E       AssertionError: assert [{'id': 'u.py...ortant', ...}] == []
E         
E         Left contains 2 more items, first extra item: {'id': 'u.py::inside copy@L8', 'findingKey': 'u.py::inside copy@L8', 'title': 'inside copy', 'severity': 'Important', ...}
E         Use -v to get more diff

/home/user/sh-2305/plugins/superheroes/lib/tests/test_c4_sweep_recovery.py:331: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c4_sweep_recovery.py::test_r9_a_result_with_no_readable_scope_is_recovered_as_outside_only
!!!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.41s
```
**restore**: the inverse Edit. **restore receipt** (`grep -n "scope is not None and _outside_the_round"`): `1047:            hits, parent, lambda hit: scope is not None and _outside_the_round(hit, scope) is None)`
**raw green**: `.   [100%]` / `1 passed in 0.51s`

## Final tree

After r10 the two test files were run together: `test_c4_sweep_recovery.py` + `test_c4_sweep.py` → `116 passed in 16.83s`. `git status --porcelain` (hidden dotfiles
of the container's home excluded) lists only the deliverables and this record; no `if False`-style residue remains in any neutralized file (each restore
receipt above is the restored line).
