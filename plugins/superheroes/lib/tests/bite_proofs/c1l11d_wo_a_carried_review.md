# C1-L11d (WO-A) bite-proof — an empty returning round's record carries the earlier review's reviewers only when every guard holds

**Provenance:** implementer WO-A2, recording the guards of WO-A on `lib/review_record.py` and `lib/review_record_session.py`, proved by `lib/tests/test_c1l11d_carried_review.py`

Declared guarded elements (from the order): G1 to G7 below. The census `grep -n "c1l11d_wo_a_carried_review" plugins/superheroes/lib/review_record.py plugins/superheroes/lib/review_record_session.py` printed eight lines, which are the seven declared elements (G7 carries two axis lines, one for each of its two conditions); no guarded line outside the declared set, and every declared element has an axis comment:

```
plugins/superheroes/lib/review_record.py:390:    # axis: the earlier record's final commit must be the commit the session says it last reviewed — see bite-proof record c1l11d_wo_a_carried_review
plugins/superheroes/lib/review_record.py:394:    # axis: an earlier finding with no outcome stops the carry, so an unsettled finding never reads reviewed — see bite-proof record c1l11d_wo_a_carried_review
plugins/superheroes/lib/review_record.py:403:    # axis: the writer re-derives from git that the change since the last reviewed commit is empty; the account's word is never taken — see bite-proof record c1l11d_wo_a_carried_review
plugins/superheroes/lib/review_record.py:673:    # axis: a carried row and the account's carriedReview name each other and the same commit, never one without the other — see bite-proof record c1l11d_wo_a_carried_review
plugins/superheroes/lib/review_record.py:1071:        # axis: a carried row takes a row of the earlier record with its name, vendor and model that ran and covers its final commit — see bite-proof record c1l11d_wo_a_carried_review
plugins/superheroes/lib/review_record.py:1813:        # axis: a carried row says it was carried and from which commit, never that it ran — see bite-proof record c1l11d_wo_a_carried_review
plugins/superheroes/lib/review_record_session.py:345:    # axis: a round that carried a finding, audited, or ran a verifier is not the empty round — see bite-proof record c1l11d_wo_a_carried_review
plugins/superheroes/lib/review_record_session.py:348:    # axis: a session holding a carried finding, a finding or a ledger row ran something, so it is not the empty round — see bite-proof record c1l11d_wo_a_carried_review
```

Each element was neutralized with one targeted edit and restored with the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2273` (head `ac36dba8`) under `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2273 -m pytest "<node id>" -q -p no:cacheprovider`. The captures are the runner's whole output for each run apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out of every capture (it is the first line of each real output); nothing else is trimmed, and a few lines inside a capture end in `...` because pytest itself truncated them. Nothing is redacted: no secrets, tokens or URLs appear (the `/tmp/claude-0/...` paths are pytest temp directories, and `http://c/2` is the test fake's comment URL). Every neutralization below was made on the line quoted, and every restore put back the quoted original; the lines were checked back at the same line numbers after the last restore (the restore receipt of each element is the quoted line).

Every red is the runner's own failure of the unedited test, caused by the neutralization alone; a red here is the expected half of a bite-proof, not a defect. The final run of the whole test file on the restored tree and the final `git status --porcelain` are in the dispatch return, not in this record.

| ID | Guarded element | Axis | Proving test (node id, in `plugins/superheroes/lib/tests/test_c1l11d_carried_review.py`) |
|---|---|---|---|
| G1 | `review_record.carry_refusal`, the final-commit-match leg (`review_record.py:391`) | the earlier record's final commit must be the commit the session says it last reviewed | `test_e3_an_earlier_record_on_another_final_commit_refuses` |
| G2 | `review_record.carry_refusal`, the settled-findings leg (`review_record.py:395`) | an earlier finding with no outcome stops the carry, so an unsettled finding never reads reviewed | `test_e2_an_unsettled_earlier_finding_refuses_review_session_unsupported` |
| G3 | `review_record.carry_refusal`, the decider leg (`review_record.py:404`) | the writer re-derives from git that the change since the last reviewed commit is empty | `test_e6_a_carried_account_over_a_real_source_change_demotes_every_row` |
| G4 | `review_record._validate`, the `carriedFrom` / `carriedReview` consistency check (`review_record.py:674`) | a carried row and the account's `carriedReview` name each other and the same commit | `test_e8_carriedfrom_and_carriedreview_that_do_not_name_each_other_are_invalid` |
| G5 | `review_record._carried_row`, the name/vendor/model covering-row match (`review_record.py:1072`) | a carried row takes only a row of the earlier record with its name, vendor and model | `test_e7_a_carried_row_the_earlier_record_has_no_covering_row_for_is_not_run` |
| G6 | `review_record._row_bullet`, a carried row's label (`review_record.py:1812`) | a carried row says it was carried and from which commit, never that it ran | `test_a_catch_up_merge_only_writes_a_record_marked_carried_that_reads_reviewed_with_no_reviewer_run` |
| G7a | `review_record_session._empty_returning_round`, the round-1 `carried` / `audits` / `verifyPasses` condition (`review_record_session.py:346`) | a round that carried a finding, audited, or ran a verifier is not the empty round | `test_e5_a_session_that_ran_anything_still_refuses_as_it_did` |
| G7b | `review_record_session._empty_returning_round`, the `returningCarried` / findings / ledger condition (`review_record_session.py:349`) | a session holding a carried finding, a finding or a ledger row ran something | `test_e5_a_session_that_ran_anything_still_refuses_as_it_did` |

G7 is one declared element with two conditions; it is recorded as two entries, G7a and G7b, each with its own neutralization, red and green, so that neither condition stands as the representative of the other.

Not separately neutralized (the unproven part of this record):

- G1, G2, G3: each leg was made unreachable whole (`if False:`). The operands inside a leg (G1 `_full_sha(last_reviewed)` and `isinstance(final, dict)`; G2 `isinstance(findings, list)`; G3 the `read != READ_CHANGED` and `changedFiles != []` operands) were not neutralized one by one, so a test that discriminates between the operands of one leg is not shown here. E3's two cases both use a full-length sha, so a non-sha `last_reviewed` is not driven by E3.
- G2: the capture shows the record was written (`'ok': True, 'action': 'created'`) where the test expects a refusal; the capture is cut by pytest before the written record's status, so this record does not itself show the status the written record carried.
- G4: with the consistency check made `chk(True, ...)`, 3 of the 8 E8 cases went red (`no-carriedReview`, `mismatched-sha`, `no-row-carries-it`) and 5 stayed green (`short-carriedFrom`, `short-lastReviewed`, `blank-why`, `no-why`, `not-a-dict`): those five are caught by the earlier `carriedFrom` and `carriedReview` shape checks in `_validate`, not by G4, and are not evidence for G4. The three red cases are the G4 cases.
- G5: the `all(v.get(k) == r.get(k) for k in ("name", "vendor", "model"))` test was removed whole. The E7 test varies only the row's `name`, so the `vendor` and `model` keys of the match are not separately proven by any test run here.
- G6: the whole carried branch of the label was made unreachable; the proving test asserts the full `- code-reviewer: carried from <sha7>` bullet, so the label's text and its sha are both under that one assertion.
- G7a: `audits` has no E5 case. The `any(rec.get(k) for k in ("carried", "audits", "verifyPasses"))` condition went red on `a-carried-finding` and `a-verifier-pass` only; the `audits` key is **unproven** — dropping it from the tuple would not turn any E5 case red.
- G7: the E5 case `a-second-round` stayed green under both G7 neutralizations; it is refused by the `list(rounds) != ["1"]` check earlier in `_empty_returning_round`, which is no part of G7.
- Nothing here neutralizes the raise or the refusal text of any guard, only its condition; the E4, E9 and `carry_refusal`-order tests of the same file are not re-proved here.

---

## G1 — the final-commit-match leg of `carry_refusal`

**axis:** the earlier record's final commit must be the commit the session says it last reviewed.

**neutralization** (`review_record.py:391`, `carry_refusal`: the leg made unreachable, so an earlier record on another final commit is carried):
```python
-    if not (_full_sha(last_reviewed) and isinstance(final, dict) and final.get("sha") == last_reviewed):
+    if False:
```

**raw red:** `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2273 -m pytest "plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_e3_an_earlier_record_on_another_final_commit_refuses" -q -p no:cacheprovider`
```
FF                                                                       [100%]
=================================== FAILURES ===================================
__ test_e3_an_earlier_record_on_another_final_commit_refuses[the-head-itself] __

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-16/test_e3_an_earlier_record_on_a0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f178c873b00>
at = 'head'

    @pytest.mark.parametrize("at", ["head", "c" * 40], ids=["the-head-itself", "an-unknown-commit"])
    def test_e3_an_earlier_record_on_another_final_commit_refuses(tmp_path, monkeypatch, at):
        # the head itself is the case only this leg refuses: the decider reads an empty surface from it, and says `changed`
        s = _empty_session(tmp_path, monkeypatch)
        fake = TRRS.Fake(head=s.head)
        _post_earlier(fake, s, at=s.head if at == "head" else None,
                      edit=None if at == "head" else lambda rec: rec.update(finalCommit={"sha": at, "source": "GitHub PR"}))
        out = _send(tmp_path, s, fake)
>       assert out["ok"] is False and out["reason"] == RS.UNSUPPORTED, out
E       AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/2', 'parts': 0, ...}
E       assert (True is False)

/home/user/wt-2273/plugins/superheroes/lib/tests/test_c1l11d_carried_review.py:181: AssertionError
_ test_e3_an_earlier_record_on_another_final_commit_refuses[an-unknown-commit] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-16/test_e3_an_earlier_record_on_a1')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f178c873e30>
at = 'cccccccccccccccccccccccccccccccccccccccc'

    @pytest.mark.parametrize("at", ["head", "c" * 40], ids=["the-head-itself", "an-unknown-commit"])
    def test_e3_an_earlier_record_on_another_final_commit_refuses(tmp_path, monkeypatch, at):
        # the head itself is the case only this leg refuses: the decider reads an empty surface from it, and says `changed`
        s = _empty_session(tmp_path, monkeypatch)
        fake = TRRS.Fake(head=s.head)
        _post_earlier(fake, s, at=s.head if at == "head" else None,
                      edit=None if at == "head" else lambda rec: rec.update(finalCommit={"sha": at, "source": "GitHub PR"}))
        out = _send(tmp_path, s, fake)
        assert out["ok"] is False and out["reason"] == RS.UNSUPPORTED, out
>       assert out["detail"] == "the earlier record's final commit is not the last reviewed commit", out
E       AssertionError: {'ok': False, 'reason': 'review-session-unsupported', 'detail': 'the earlier review does not stand for this head (last...iewed-not-ancestor: the last reviewed commit cccccccccccccccccccccccccccccccccccccccc is not an ancestor of the head)'}
E       assert 'the earlier ... of the head)' == 'the earlier ...viewed commit'
E         
E         - the earlier record's final commit is not the last reviewed commit
E         + the earlier review does not stand for this head (last-reviewed-not-ancestor: the last reviewed commit cccccccccccccccccccccccccccccccccccccccc is not an ancestor of the head)

/home/user/wt-2273/plugins/superheroes/lib/tests/test_c1l11d_carried_review.py:182: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_e3_an_earlier_record_on_another_final_commit_refuses[the-head-itself]
FAILED plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_e3_an_earlier_record_on_another_final_commit_refuses[an-unknown-commit]
2 failed in 2.58s
```
The red is on the axis: with the leg gone, `the-head-itself` writes a record (`'ok': True, 'action': 'created'`) where the unedited test expects the refusal, and `an-unknown-commit` is refused by the decider's ancestry check with a different detail than this leg's own.

**restore:** the inverse edit — the `if False:` put back to the original condition.

**restore receipt** (the restored line, quoted from `review_record.py:391`):
```
    if not (_full_sha(last_reviewed) and isinstance(final, dict) and final.get("sha") == last_reviewed):
```

**raw green:** the same command.
```
..                                                                       [100%]
2 passed in 2.69s
```

---

## G2 — the settled-findings leg of `carry_refusal` (the DoD break-it)

**axis:** an earlier finding with no outcome stops the carry, so an unsettled finding never reads reviewed.

**neutralization** (`review_record.py:395`, `carry_refusal`: the leg made unreachable, so an earlier record with an open finding is carried):
```python
-    if not (isinstance(findings, list) and all(isinstance(f, dict) and f.get("outcome") is not None for f in findings)):
+    if False:
```

**raw red:** `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2273 -m pytest "plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_e2_an_unsettled_earlier_finding_refuses_review_session_unsupported" -q -p no:cacheprovider`
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_e2_an_unsettled_earlier_finding_refuses_review_session_unsupported ____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-18/test_e2_an_unsettled_earlier_f0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f4a91637cb0>

    def test_e2_an_unsettled_earlier_finding_refuses_review_session_unsupported(tmp_path, monkeypatch):
        s = _empty_session(tmp_path, monkeypatch)
        fake = TRRS.Fake(head=s.head)
        _post_earlier(fake, s, edit=_open_finding, findings=[OPEN])
        before = list(fake.comments)
        out = _send(tmp_path, s, fake)
>       assert out["ok"] is False and out["reason"] == RS.UNSUPPORTED and out["detail"] == "an earlier finding is still open", out
E       AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/2', 'parts': 0, ...}
E       assert (True is False)

/home/user/wt-2273/plugins/superheroes/lib/tests/test_c1l11d_carried_review.py:167: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_e2_an_unsettled_earlier_finding_refuses_review_session_unsupported
1 failed in 2.56s
```
The red is on the axis: with the leg gone the record is written (`'ok': True, 'action': 'created'`) over an earlier record holding an open finding, where the unedited test expects the refusal `an earlier finding is still open`. The capture is cut before the written record's status (see the unproven list).

**restore:** the inverse edit — the `if False:` put back to the original condition.

**restore receipt** (the restored line, quoted from `review_record.py:395`):
```
    if not (isinstance(findings, list) and all(isinstance(f, dict) and f.get("outcome") is not None for f in findings)):
```

**raw green:** the same command.
```
.                                                                        [100%]
1 passed in 2.44s
```

---

## G3 — the decider leg of `carry_refusal`

**axis:** the writer re-derives from git that the change since the last reviewed commit is empty; the account's word is never taken.

**neutralization** (`review_record.py:404`, `carry_refusal`: the leg made unreachable, so the decider's answer is never held to `read == changed` and `changedFiles == []`):
```python
-    if answer.get("read") != returning_review.READ_CHANGED or answer.get("changedFiles") != []:
+    if False:
```

**raw red:** `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2273 -m pytest "plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_e6_a_carried_account_over_a_real_source_change_demotes_every_row" -q -p no:cacheprovider`
```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_e6_a_carried_account_over_a_real_source_change_demotes_every_row _____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-20/test_e6_a_carried_account_over0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7ff4dd7afa70>

    def test_e6_a_carried_account_over_a_real_source_change_demotes_every_row(tmp_path, monkeypatch):
        s = _changed_session(tmp_path, monkeypatch)
        fake = TRRS.Fake(head=s.head)
        _post_earlier(fake, s)
        out = _write(tmp_path, s, fake, _carried_account(s))
>       assert out["ok"] is True and out["status"] == "not-reviewed", out
E       AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/2', 'parts': 0, ...}
E       assert (True is True and 'reviewed' == 'not-reviewed'
E         
E         - not-reviewed
E         ? ----
E         + reviewed)

/home/user/wt-2273/plugins/superheroes/lib/tests/test_c1l11d_carried_review.py:234: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_e6_a_carried_account_over_a_real_source_change_demotes_every_row
1 failed in 2.47s
```
The red is on the axis: over a real source change the writer, with the leg gone, takes the account's word and writes the record as `reviewed` where the unedited test expects `not-reviewed`.

**restore:** the inverse edit — the `if False:` put back to the original condition.

**restore receipt** (the restored line, quoted from `review_record.py:404`):
```
    if answer.get("read") != returning_review.READ_CHANGED or answer.get("changedFiles") != []:
```

**raw green:** the same command.
```
.                                                                        [100%]
1 passed in 2.26s
```

---

## G4 — the `carriedFrom` / `carriedReview` consistency check in `_validate`

**axis:** a carried row and the account's `carriedReview` name each other and the same commit, never one without the other.

**neutralization** (`review_record.py:674-675`, `_validate`: the check made always true):
```python
-    chk(bool(from_shas) == ("carriedReview" in a)
-        and (not from_shas or from_shas == {carried_review["lastReviewed"]}), "carriedReview (and reviewers[].carriedFrom)")
+    chk(True, "carriedReview (and reviewers[].carriedFrom)")
```

**raw red:** `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2273 -m pytest "plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_e8_carriedfrom_and_carriedreview_that_do_not_name_each_other_are_invalid" -q -p no:cacheprovider`
```
FFF.....                                                                 [100%]
=================================== FAILURES ===================================
_ test_e8_carriedfrom_and_carriedreview_that_do_not_name_each_other_are_invalid[no-carriedReview] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-22/test_e8_carriedfrom_and_carrie0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fe5f832fe90>
edit = <function _without.<locals>.<lambda> at 0x7fe5f8220f40>

    @pytest.mark.parametrize("edit", [
        _without("carriedReview"),
        lambda a: dict(a, carriedReview=dict(a["carriedReview"], lastReviewed="d" * 40)),
        lambda a: dict(a, reviewers=[{k: v for k, v in a["reviewers"][0].items() if k != "carriedFrom"}]),
        lambda a: dict(a, reviewers=[dict(a["reviewers"][0], carriedFrom="abc123")]),
        lambda a: dict(a, carriedReview=dict(a["carriedReview"], lastReviewed="abc123")),
        lambda a: dict(a, carriedReview=dict(a["carriedReview"], why="  ")),
        lambda a: dict(a, carriedReview={"lastReviewed": a["carriedReview"]["lastReviewed"]}),
        lambda a: dict(a, carriedReview="carried"),
    ], ids=["no-carriedReview", "mismatched-sha", "no-row-carries-it", "short-carriedFrom", "short-lastReviewed", "blank-why",
            "no-why", "not-a-dict"])
    def test_e8_carriedfrom_and_carriedreview_that_do_not_name_each_other_are_invalid(tmp_path, monkeypatch, edit):
        s = _empty_session(tmp_path, monkeypatch)
        fake = TRRS.Fake(head=s.head)
        _post_earlier(fake, s)
        before = list(fake.comments)
        out = _write(tmp_path, s, fake, edit(_carried_account(s)))
>       assert out["ok"] is False and out["reason"] == "review-account-invalid", out
E       AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/2', 'parts': 0, ...}
E       assert (True is False)

/home/user/wt-2273/plugins/superheroes/lib/tests/test_c1l11d_carried_review.py:313: AssertionError
_ test_e8_carriedfrom_and_carriedreview_that_do_not_name_each_other_are_invalid[mismatched-sha] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-22/test_e8_carriedfrom_and_carrie1')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fe5f832f770>
edit = <function <lambda> at 0x7fe5f8220fe0>

    @pytest.mark.parametrize("edit", [
        _without("carriedReview"),
        lambda a: dict(a, carriedReview=dict(a["carriedReview"], lastReviewed="d" * 40)),
        lambda a: dict(a, reviewers=[{k: v for k, v in a["reviewers"][0].items() if k != "carriedFrom"}]),
        lambda a: dict(a, reviewers=[dict(a["reviewers"][0], carriedFrom="abc123")]),
        lambda a: dict(a, carriedReview=dict(a["carriedReview"], lastReviewed="abc123")),
        lambda a: dict(a, carriedReview=dict(a["carriedReview"], why="  ")),
        lambda a: dict(a, carriedReview={"lastReviewed": a["carriedReview"]["lastReviewed"]}),
        lambda a: dict(a, carriedReview="carried"),
    ], ids=["no-carriedReview", "mismatched-sha", "no-row-carries-it", "short-carriedFrom", "short-lastReviewed", "blank-why",
            "no-why", "not-a-dict"])
    def test_e8_carriedfrom_and_carriedreview_that_do_not_name_each_other_are_invalid(tmp_path, monkeypatch, edit):
        s = _empty_session(tmp_path, monkeypatch)
        fake = TRRS.Fake(head=s.head)
        _post_earlier(fake, s)
        before = list(fake.comments)
        out = _write(tmp_path, s, fake, edit(_carried_account(s)))
>       assert out["ok"] is False and out["reason"] == "review-account-invalid", out
E       AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/2', 'parts': 0, ...}
E       assert (True is False)

/home/user/wt-2273/plugins/superheroes/lib/tests/test_c1l11d_carried_review.py:313: AssertionError
_ test_e8_carriedfrom_and_carriedreview_that_do_not_name_each_other_are_invalid[no-row-carries-it] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-22/test_e8_carriedfrom_and_carrie2')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fe5f832f6e0>
edit = <function <lambda> at 0x7fe5f8221080>

    @pytest.mark.parametrize("edit", [
        _without("carriedReview"),
        lambda a: dict(a, carriedReview=dict(a["carriedReview"], lastReviewed="d" * 40)),
        lambda a: dict(a, reviewers=[{k: v for k, v in a["reviewers"][0].items() if k != "carriedFrom"}]),
        lambda a: dict(a, reviewers=[dict(a["reviewers"][0], carriedFrom="abc123")]),
        lambda a: dict(a, carriedReview=dict(a["carriedReview"], lastReviewed="abc123")),
        lambda a: dict(a, carriedReview=dict(a["carriedReview"], why="  ")),
        lambda a: dict(a, carriedReview={"lastReviewed": a["carriedReview"]["lastReviewed"]}),
        lambda a: dict(a, carriedReview="carried"),
    ], ids=["no-carriedReview", "mismatched-sha", "no-row-carries-it", "short-carriedFrom", "short-lastReviewed", "blank-why",
            "no-why", "not-a-dict"])
    def test_e8_carriedfrom_and_carriedreview_that_do_not_name_each_other_are_invalid(tmp_path, monkeypatch, edit):
        s = _empty_session(tmp_path, monkeypatch)
        fake = TRRS.Fake(head=s.head)
        _post_earlier(fake, s)
        before = list(fake.comments)
        out = _write(tmp_path, s, fake, edit(_carried_account(s)))
>       assert out["ok"] is False and out["reason"] == "review-account-invalid", out
E       AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/2', 'parts': 0, ...}
E       assert (True is False)

/home/user/wt-2273/plugins/superheroes/lib/tests/test_c1l11d_carried_review.py:313: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_e8_carriedfrom_and_carriedreview_that_do_not_name_each_other_are_invalid[no-carriedReview]
FAILED plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_e8_carriedfrom_and_carriedreview_that_do_not_name_each_other_are_invalid[mismatched-sha]
FAILED plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_e8_carriedfrom_and_carriedreview_that_do_not_name_each_other_are_invalid[no-row-carries-it]
3 failed, 5 passed in 3.66s
```
The red is on the axis: the three cases that break only the mutual naming (a carried row with no `carriedReview`, a `carriedReview` naming another commit, a `carriedReview` no row carries) are written where the unedited test expects `review-account-invalid`. The five cases that stayed green are listed in the unproven part above.

**restore:** the inverse edit — the `chk(True, ...)` put back to the original two-line check.

**restore receipt** (the restored lines, quoted from `review_record.py:674-675`):
```
    chk(bool(from_shas) == ("carriedReview" in a)
        and (not from_shas or from_shas == {carried_review["lastReviewed"]}), "carriedReview (and reviewers[].carriedFrom)")
```

**raw green:** the same command.
```
........                                                                 [100%]
8 passed in 4.16s
```

---

## G5 — the name/vendor/model covering-row match in `_carried_row`

**axis:** a carried row takes only a row of the earlier record with its name, vendor and model that ran and covers its final commit.

**neutralization** (`review_record.py:1072`, `_carried_row`: the name/vendor/model comparison replaced by `True`, so a row of the earlier record that ran and covers the final commit is taken whatever its name):
```python
-        if isinstance(v, dict) and all(v.get(k) == r.get(k) for k in ("name", "vendor", "model")) \
+        if isinstance(v, dict) and True \
```

**raw red:** `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2273 -m pytest "plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_e7_a_carried_row_the_earlier_record_has_no_covering_row_for_is_not_run" -q -p no:cacheprovider`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_e7_a_carried_row_the_earlier_record_has_no_covering_row_for_is_not_run __

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-24/test_e7_a_carried_row_the_earl0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fd5977f7fe0>

    def test_e7_a_carried_row_the_earlier_record_has_no_covering_row_for_is_not_run(tmp_path, monkeypatch):
        s = _empty_session(tmp_path, monkeypatch)
        fake = TRRS.Fake(head=s.head)
        _post_earlier(fake, s)
        stranger = dict(_carried_account(s)["reviewers"][0], name="test-role")
        out = _write(tmp_path, s, fake, _carried_account(s, reviewers=[stranger, _carried_account(s)["reviewers"][0]]))
        rows = {v["name"]: v for v in _latest(fake)["reviewers"]}
        assert out["ok"] is True, out
>       assert rows["test-role"]["ran"] == "not-run" and "carried" not in rows["test-role"]
E       AssertionError: assert ('reported-by-session' == 'not-run'
E         
E         - not-run
E         + reported-by-session)

/home/user/wt-2273/plugins/superheroes/lib/tests/test_c1l11d_carried_review.py:277: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_e7_a_carried_row_the_earlier_record_has_no_covering_row_for_is_not_run
1 failed in 2.31s
```
The red is on the axis: the carried row named `test-role`, which the earlier record has no row for, is credited `reported-by-session` where the unedited test expects `not-run`.

**restore:** the inverse edit — the `True` put back to the `all(...)` comparison.

**restore receipt** (the restored line, quoted from `review_record.py:1072`):
```
        if isinstance(v, dict) and all(v.get(k) == r.get(k) for k in ("name", "vendor", "model")) \
```

**raw green:** the same command.
```
.                                                                        [100%]
1 passed in 2.72s
```

---

## G6 — a carried row's label in `_row_bullet`

**axis:** a carried row says it was carried and from which commit, never that it ran.

**proving test:** the test that asserts the `carried from` label is `test_a_catch_up_merge_only_writes_a_record_marked_carried_that_reads_reviewed_with_no_reviewer_run`, at the line `assert "- code-reviewer: carried from %s" % s.reviewed[:7] in body and "ran (reported by the session)" not in body` (test file line 151).

**neutralization** (`review_record.py:1812`, `_row_bullet`: the carried branch made unreachable, so a carried row is labelled by the ordinary `ran (...)` label):
```python
-    if v["ran"] != "not-run" and isinstance(v.get("carried"), dict):
+    if False:
```

**raw red:** `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2273 -m pytest "plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_a_catch_up_merge_only_writes_a_record_marked_carried_that_reads_reviewed_with_no_reviewer_run" -q -p no:cacheprovider`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_catch_up_merge_only_writes_a_record_marked_carried_that_reads_reviewed_with_no_reviewer_run _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-26/test_a_catch_up_merge_only_wri0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f35bc083980>

    def test_a_catch_up_merge_only_writes_a_record_marked_carried_that_reads_reviewed_with_no_reviewer_run(tmp_path, monkeypatch):
        s = _empty_session(tmp_path, monkeypatch)
        fake = TRRS.Fake(head=s.head)
        _post_earlier(fake, s)
        out = _send(tmp_path, s, fake)
        assert out["ok"] is True and out["status"] == "reviewed", out
        rec = _latest(fake)
        assert rec["status"] == "reviewed" and rec["finalCommit"]["sha"] == s.head
        assert rec["reviewers"] and all(v["carried"] == {"commit": s.reviewed} and v["commit"] == s.reviewed
                                        and v["ran"] == "reported-by-session" and v["coversFinalCommit"] is True
                                        and v["cost"] == {"tokens": None, "minutes": None} and "observation" not in v
                                        for v in rec["reviewers"]), rec["reviewers"]
        # the record says plainly that no reviewer ran in this round, and why
        assert rec["checked"][1] == ("Reviewers that ran: none in this round — carried from the earlier review of %s: code-reviewer"
                                     % s.reviewed[:7]), rec["checked"]
        assert RS.CARRIED_WHY % s.reviewed[:7] in rec["checked"], rec["checked"]
        body = fake.marked()[-1]["body"]
>       assert "- code-reviewer: carried from %s" % s.reviewed[:7] in body and "ran (reported by the session)" not in body
E       assert (('- code-reviewer: carried from %s' % '0d1d02a') in '<!-- superheroes:review-record -->\n**Review record: reviewed.** Checked: CI on 3933580: green; Reviewers that ran: n...d","unreadFiles":[],"whatIsMissing":[],"withheldFromReviewers":[],"writtenAt":"2026-10-30T11:48:19Z"}\n```\n</details>')

/home/user/wt-2273/plugins/superheroes/lib/tests/test_c1l11d_carried_review.py:151: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_a_catch_up_merge_only_writes_a_record_marked_carried_that_reads_reviewed_with_no_reviewer_run
1 failed in 2.23s
```
The red is on the axis: every assertion before the label (the record reads `reviewed`, the row carries `carried == {"commit": <last reviewed>}`, the `checked` line says none ran) passed, and the failure is the label assertion at test line 151: the posted body does not hold `- code-reviewer: carried from 0d1d02a`.

**restore:** the inverse edit — the `if False:` put back to the original condition.

**restore receipt** (the restored line, quoted from `review_record.py:1812`):
```
    if v["ran"] != "not-run" and isinstance(v.get("carried"), dict):
```

**raw green:** the same command.
```
.                                                                        [100%]
1 passed in 2.23s
```

---

## G7a — the round-1 `carried` / `audits` / `verifyPasses` condition in `_empty_returning_round`

**axis:** a round that carried a finding, audited, or ran a verifier is not the empty round.

**neutralization** (`review_record_session.py:346`, `_empty_returning_round`: the condition made unreachable, so a round that carried a finding or ran a verifier is still the empty round):
```python
-    if any(rec.get(k) for k in ("carried", "audits", "verifyPasses")):
+    if False:
```

**raw red:** `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2273 -m pytest "plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_e5_a_session_that_ran_anything_still_refuses_as_it_did" -q -p no:cacheprovider`
```
.FF...                                                                   [100%]
=================================== FAILURES ===================================
_ test_e5_a_session_that_ran_anything_still_refuses_as_it_did[a-carried-finding] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-28/test_e5_a_session_that_ran_any1')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f97913d3680>
edit = <function <lambda> at 0x7f9791334720>

    @pytest.mark.parametrize("edit", [
        lambda st: st["rounds"].update({"2": {}}),
        lambda st: st["rounds"]["1"].update(carried=[{"findingKey": "rr1:x"}]),
        lambda st: st["rounds"]["1"].update(verifyPasses=[{"held": 0}]),
        lambda st: st["config"].update(returningCarried=[{"findingKey": "rr1:x"}]),
        lambda st: st.update(findings=[{"id": "F-1", "title": "t", "severity": "Important", "file": "a.py", "line": 1}]),
        lambda st: st.update(dispositionLedger=[TRRS.ledger_row()]),
    ], ids=["a-second-round", "a-carried-finding", "a-verifier-pass", "carried-in-config", "a-finding", "a-ledger-row"])
    def test_e5_a_session_that_ran_anything_still_refuses_as_it_did(tmp_path, monkeypatch, edit):
        s = _empty_session(tmp_path, monkeypatch)
        path = os.path.join(s.dir, SC.STATE_FILE)
        with open(path, encoding="utf-8") as fh:
            state = json.load(fh)
        edit(state)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
        fake = TRRS.Fake(head=s.head)
        _post_earlier(fake, s)
        before = list(fake.comments)
        out = _send(tmp_path, s, fake)
>       assert out == {"ok": False, "reason": RS.UNSUPPORTED, "detail": RS.NO_SEAT_RESULT}, out
E       AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/2', 'parts': 0, ...}
E       assert {'ok': True, ...arts': 0, ...} == {'ok': False,... seat status'}
E         
E         Differing items:
E         {'ok': True} != {'ok': False}
E         Left contains 6 more items:
E         {'action': 'created',
E          'parked': False,
E          'parts': 0,...
E         
E         ...Full output truncated, use '-vv' to show

/home/user/wt-2273/plugins/superheroes/lib/tests/test_c1l11d_carried_review.py:223: AssertionError
_ test_e5_a_session_that_ran_anything_still_refuses_as_it_did[a-verifier-pass] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-28/test_e5_a_session_that_ran_any2')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f9791237bc0>
edit = <function <lambda> at 0x7f97913347c0>

    @pytest.mark.parametrize("edit", [
        lambda st: st["rounds"].update({"2": {}}),
        lambda st: st["rounds"]["1"].update(carried=[{"findingKey": "rr1:x"}]),
        lambda st: st["rounds"]["1"].update(verifyPasses=[{"held": 0}]),
        lambda st: st["config"].update(returningCarried=[{"findingKey": "rr1:x"}]),
        lambda st: st.update(findings=[{"id": "F-1", "title": "t", "severity": "Important", "file": "a.py", "line": 1}]),
        lambda st: st.update(dispositionLedger=[TRRS.ledger_row()]),
    ], ids=["a-second-round", "a-carried-finding", "a-verifier-pass", "carried-in-config", "a-finding", "a-ledger-row"])
    def test_e5_a_session_that_ran_anything_still_refuses_as_it_did(tmp_path, monkeypatch, edit):
        s = _empty_session(tmp_path, monkeypatch)
        path = os.path.join(s.dir, SC.STATE_FILE)
        with open(path, encoding="utf-8") as fh:
            state = json.load(fh)
        edit(state)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
        fake = TRRS.Fake(head=s.head)
        _post_earlier(fake, s)
        before = list(fake.comments)
        out = _send(tmp_path, s, fake)
>       assert out == {"ok": False, "reason": RS.UNSUPPORTED, "detail": RS.NO_SEAT_RESULT}, out
E       AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/2', 'parts': 0, ...}
E       assert {'ok': True, ...arts': 0, ...} == {'ok': False,... seat status'}
E         
E         Differing items:
E         {'ok': True} != {'ok': False}
E         Left contains 6 more items:
E         {'action': 'created',
E          'parked': False,
E          'parts': 0,...
E         
E         ...Full output truncated, use '-vv' to show

/home/user/wt-2273/plugins/superheroes/lib/tests/test_c1l11d_carried_review.py:223: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_e5_a_session_that_ran_anything_still_refuses_as_it_did[a-carried-finding]
FAILED plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_e5_a_session_that_ran_anything_still_refuses_as_it_did[a-verifier-pass]
2 failed, 4 passed in 3.54s
```
The red is on the axis: the two cases that put a carried finding or a verifier pass in round 1 write a record (`'ok': True, 'action': 'created'`) where the unedited test expects the refusal `review-session-unsupported` with `NO_SEAT_RESULT`. The four other cases stayed green (`a-second-round`, `carried-in-config`, `a-finding`, `a-ledger-row`): they are not this condition's cases. No case puts an audit in round 1, so the `audits` key is unproven (see above).

**restore:** the inverse edit — the `if False:` put back to the original condition.

**restore receipt** (the restored line, quoted from `review_record_session.py:346`):
```
    if any(rec.get(k) for k in ("carried", "audits", "verifyPasses")):
```

**raw green:** the same command.
```
......                                                                   [100%]
6 passed in 4.17s
```

---

## G7b — the `returningCarried` / findings / ledger condition in `_empty_returning_round`

**axis:** a session holding a carried finding, a finding or a ledger row ran something, so it is not the empty round.

**neutralization** (`review_record_session.py:349`, `_empty_returning_round`: the condition made unreachable, so a session holding a carried finding in its config, a finding or a ledger row is still the empty round):
```python
-    if cfg.get("returningCarried") or state.get("findings") or state.get(sc.DISPOSITION_LEDGER_KEY):
+    if False:
```

**raw red:** the same node id and command as G7a.
```
...FFF                                                                   [100%]
=================================== FAILURES ===================================
_ test_e5_a_session_that_ran_anything_still_refuses_as_it_did[carried-in-config] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-30/test_e5_a_session_that_ran_any3')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f234ccd9c70>
edit = <function <lambda> at 0x7f234cc78860>

    @pytest.mark.parametrize("edit", [
        lambda st: st["rounds"].update({"2": {}}),
        lambda st: st["rounds"]["1"].update(carried=[{"findingKey": "rr1:x"}]),
        lambda st: st["rounds"]["1"].update(verifyPasses=[{"held": 0}]),
        lambda st: st["config"].update(returningCarried=[{"findingKey": "rr1:x"}]),
        lambda st: st.update(findings=[{"id": "F-1", "title": "t", "severity": "Important", "file": "a.py", "line": 1}]),
        lambda st: st.update(dispositionLedger=[TRRS.ledger_row()]),
    ], ids=["a-second-round", "a-carried-finding", "a-verifier-pass", "carried-in-config", "a-finding", "a-ledger-row"])
    def test_e5_a_session_that_ran_anything_still_refuses_as_it_did(tmp_path, monkeypatch, edit):
        s = _empty_session(tmp_path, monkeypatch)
        path = os.path.join(s.dir, SC.STATE_FILE)
        with open(path, encoding="utf-8") as fh:
            state = json.load(fh)
        edit(state)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
        fake = TRRS.Fake(head=s.head)
        _post_earlier(fake, s)
        before = list(fake.comments)
        out = _send(tmp_path, s, fake)
>       assert out == {"ok": False, "reason": RS.UNSUPPORTED, "detail": RS.NO_SEAT_RESULT}, out
E       AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/2', 'parts': 0, ...}
E       assert {'ok': True, ...arts': 0, ...} == {'ok': False,... seat status'}
E         
E         Differing items:
E         {'ok': True} != {'ok': False}
E         Left contains 6 more items:
E         {'action': 'created',
E          'parked': False,
E          'parts': 0,...
E         
E         ...Full output truncated, use '-vv' to show

/home/user/wt-2273/plugins/superheroes/lib/tests/test_c1l11d_carried_review.py:223: AssertionError
____ test_e5_a_session_that_ran_anything_still_refuses_as_it_did[a-finding] ____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-30/test_e5_a_session_that_ran_any4')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f234cb45940>
edit = <function <lambda> at 0x7f234cc78900>

    @pytest.mark.parametrize("edit", [
        lambda st: st["rounds"].update({"2": {}}),
        lambda st: st["rounds"]["1"].update(carried=[{"findingKey": "rr1:x"}]),
        lambda st: st["rounds"]["1"].update(verifyPasses=[{"held": 0}]),
        lambda st: st["config"].update(returningCarried=[{"findingKey": "rr1:x"}]),
        lambda st: st.update(findings=[{"id": "F-1", "title": "t", "severity": "Important", "file": "a.py", "line": 1}]),
        lambda st: st.update(dispositionLedger=[TRRS.ledger_row()]),
    ], ids=["a-second-round", "a-carried-finding", "a-verifier-pass", "carried-in-config", "a-finding", "a-ledger-row"])
    def test_e5_a_session_that_ran_anything_still_refuses_as_it_did(tmp_path, monkeypatch, edit):
        s = _empty_session(tmp_path, monkeypatch)
        path = os.path.join(s.dir, SC.STATE_FILE)
        with open(path, encoding="utf-8") as fh:
            state = json.load(fh)
        edit(state)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
        fake = TRRS.Fake(head=s.head)
        _post_earlier(fake, s)
        before = list(fake.comments)
        out = _send(tmp_path, s, fake)
>       assert out == {"ok": False, "reason": RS.UNSUPPORTED, "detail": RS.NO_SEAT_RESULT}, out
E       AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/2', 'parts': 0, ...}
E       assert {'ok': True, ...arts': 0, ...} == {'ok': False,... seat status'}
E         
E         Differing items:
E         {'ok': True} != {'ok': False}
E         Left contains 6 more items:
E         {'action': 'created',
E          'parked': False,
E          'parts': 0,...
E         
E         ...Full output truncated, use '-vv' to show

/home/user/wt-2273/plugins/superheroes/lib/tests/test_c1l11d_carried_review.py:223: AssertionError
__ test_e5_a_session_that_ran_anything_still_refuses_as_it_did[a-ledger-row] ___

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-30/test_e5_a_session_that_ran_any5')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f234cb474a0>
edit = <function <lambda> at 0x7f234cc789a0>

    @pytest.mark.parametrize("edit", [
        lambda st: st["rounds"].update({"2": {}}),
        lambda st: st["rounds"]["1"].update(carried=[{"findingKey": "rr1:x"}]),
        lambda st: st["rounds"]["1"].update(verifyPasses=[{"held": 0}]),
        lambda st: st["config"].update(returningCarried=[{"findingKey": "rr1:x"}]),
        lambda st: st.update(findings=[{"id": "F-1", "title": "t", "severity": "Important", "file": "a.py", "line": 1}]),
        lambda st: st.update(dispositionLedger=[TRRS.ledger_row()]),
    ], ids=["a-second-round", "a-carried-finding", "a-verifier-pass", "carried-in-config", "a-finding", "a-ledger-row"])
    def test_e5_a_session_that_ran_anything_still_refuses_as_it_did(tmp_path, monkeypatch, edit):
        s = _empty_session(tmp_path, monkeypatch)
        path = os.path.join(s.dir, SC.STATE_FILE)
        with open(path, encoding="utf-8") as fh:
            state = json.load(fh)
        edit(state)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
        fake = TRRS.Fake(head=s.head)
        _post_earlier(fake, s)
        before = list(fake.comments)
        out = _send(tmp_path, s, fake)
>       assert out == {"ok": False, "reason": RS.UNSUPPORTED, "detail": RS.NO_SEAT_RESULT}, out
E       AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/2', 'parts': 0, ...}
E       assert {'ok': True, ...arts': 0, ...} == {'ok': False,... seat status'}
E         
E         Differing items:
E         {'ok': True} != {'ok': False}
E         Left contains 6 more items:
E         {'action': 'created',
E          'parked': False,
E          'parts': 0,...
E         
E         ...Full output truncated, use '-vv' to show

/home/user/wt-2273/plugins/superheroes/lib/tests/test_c1l11d_carried_review.py:223: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_e5_a_session_that_ran_anything_still_refuses_as_it_did[carried-in-config]
FAILED plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_e5_a_session_that_ran_anything_still_refuses_as_it_did[a-finding]
FAILED plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_e5_a_session_that_ran_anything_still_refuses_as_it_did[a-ledger-row]
3 failed, 3 passed in 3.53s
```
The red is on the axis: the three cases that put a carried finding in the config, a finding, or a ledger row in the session write a record (`'ok': True, 'action': 'created'`) where the unedited test expects the refusal `review-session-unsupported` with `NO_SEAT_RESULT`. The three other cases stayed green (`a-second-round`, `a-carried-finding`, `a-verifier-pass`): they are G7a's cases, or the earlier round check's. Each red case sets one field only, so each of the three operands has its own red case; the operands were not neutralized one by one.

**restore:** the inverse edit — the `if False:` put back to the original condition.

**restore receipt** (the restored line, quoted from `review_record_session.py:349`):
```
    if cfg.get("returningCarried") or state.get("findings") or state.get(sc.DISPOSITION_LEDGER_KEY):
```

**raw green:** the same command.
```
......                                                                   [100%]
6 passed in 3.61s
```
