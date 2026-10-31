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

---

# Appended by C1-L11f (WO-A, build #2279, vet 737 item 1): entries for the guards whose axis comments cite this record and held none

These are proofs of existing guards: no lasting source change. Each element was neutralized with one targeted Edit and restored with the inverse Edit (no `git checkout`, `restore`, `reset` or `stash`). Run from the worktree root under `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-a -m pytest "<node id>" -q -p no:cacheprovider --tb=short`, on the tree at build base `4f350065` plus WO-A's `_ci_pending_only` change (E8 alone ran with `--tb=line`). `--tb=short` and `--tb=line` are the runner's own options; the `UV_NATIVE_TLS` deprecation warning line is dropped from each capture; nothing else is filtered and nothing is redacted (no secret appears). Line numbers are those of that tree. Elements: E3 (two pieces, E3a the function `revalidated_copies` and E3b its `carryBase` argument), E5 (two pieces, E5a never demote and E5b always demote), E6, E7 (the ledger operand's rows half), E8 (its fault half). The E4 pair (`carryBase` validation and the session writer's pinned base) cites `c1l11d_wo_c_fold` and is recorded there.

## E3a — `review_record.revalidated_copies`

**axis:** the carry check hears only the copies git still proves at the final commit; the account's word is never taken (`review_record.py:1527` axis comment, call at `:1528`).

**neutralization** (`review_record.py:1528`, one Edit: the account's copies are passed on as given, no recheck):
```python
-                           revalidated_copies(a.get("provenCopies") or [], a.get("repoRoot"), a.get("carryBase"), fc["sha"]),
+                           list(a.get("provenCopies") or []),
```

**raw red:** `... -m pytest "plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_e6_a_stale_copy_proof_over_a_real_source_change_does_not_widen_the_empty_round" "plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_a_proven_copy_only_returning_round_with_a_symbolic_base_ref_writes_a_carried_record_that_reads_reviewed" -q -p no:cacheprovider --tb=short`
```
F.                                                                       [100%]
=================================== FAILURES ===================================
_ test_e6_a_stale_copy_proof_over_a_real_source_change_does_not_widen_the_empty_round _
/home/user/wt-2279-a/plugins/superheroes/lib/tests/test_c1l11d_carried_review.py:269: in test_e6_a_stale_copy_proof_over_a_real_source_change_does_not_widen_the_empty_round
    assert out["ok"] is True and out["status"] == "not-reviewed", out
E   AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/2', 'parts': 0, ...}
E   assert (True is True and 'reviewed' == 'not-reviewed'
E     
E     - not-reviewed
E     ? ----
E     + reviewed)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_e6_a_stale_copy_proof_over_a_real_source_change_does_not_widen_the_empty_round
1 failed, 1 passed in 2.34s
```
The red is on the axis: with the account's copies taken unchecked, a stale proof over a real source change widens the empty round and the record reads `reviewed` where the test requires `not-reviewed`. The second test stayed green: its copy proof is genuine.

**restore:** the inverse Edit.

**restore receipt** (the restored line, quoted from `review_record.py:1528` by Grep):
```
1528:                           revalidated_copies(a.get("provenCopies") or [], a.get("repoRoot"), a.get("carryBase"), fc["sha"]),
```

**raw green:** same command.
```
..                                                                       [100%]
2 passed in 1.88s
```

## E3b — `review_record.revalidated_copies`, its `carryBase` argument

**axis:** the copies are rechecked against the session's pinned full-sha review base (`carryBase`), never the symbolic `baseRef`.

**neutralization** (`review_record.py:1528`, one Edit: the recheck is given `baseRef`):
```python
-                           revalidated_copies(a.get("provenCopies") or [], a.get("repoRoot"), a.get("carryBase"), fc["sha"]),
+                           revalidated_copies(a.get("provenCopies") or [], a.get("repoRoot"), a.get("baseRef"), fc["sha"]),
```

**raw red:** same command (both node ids).
```
.F                                                                       [100%]
=================================== FAILURES ===================================
_ test_a_proven_copy_only_returning_round_with_a_symbolic_base_ref_writes_a_carried_record_that_reads_reviewed _
/home/user/wt-2279-a/plugins/superheroes/lib/tests/test_c1l11d_carried_review.py:563: in test_a_proven_copy_only_returning_round_with_a_symbolic_base_ref_writes_a_carried_record_that_reads_reviewed
    assert out["ok"] is True and out["status"] == "reviewed", out
E   AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/2', 'parts': 0, ...}
E   assert (True is True and 'not-reviewed' == 'reviewed'
E     
E     - reviewed
E     ? ++++)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_a_proven_copy_only_returning_round_with_a_symbolic_base_ref_writes_a_carried_record_that_reads_reviewed
1 failed, 1 passed in 2.00s
```
The red is on the axis: with the symbolic `baseRef` given to the recheck, a genuine copy proof cannot be rechecked (the recheck needs a full sha), is dropped, and the proven-copy-only round reads `not-reviewed` where the test requires `reviewed`. The stale-proof test stayed green: dropping every copy is the safe direction.

**restore:** the inverse Edit.

**restore receipt** (the restored line, quoted from `review_record.py:1528` by Grep):
```
1528:                           revalidated_copies(a.get("provenCopies") or [], a.get("repoRoot"), a.get("carryBase"), fc["sha"]),
```

**raw green:** same command.
```
..                                                                       [100%]
2 passed in 2.08s
```

## E5a — the light-lane `reading` check, never demote

**axis:** a carried row has no observation of its own; it counts outside the full lane exactly when the earlier record's matching row itself read engaged, else it stays demoted (`review_record.py:1201` axis comment, check at `:1202`).

**neutralization** (`review_record.py:1202`, one Edit: the demotion never fires):
```python
-            if carried_reading != "engaged":
+            if False:
```

**raw red:** `... -m pytest "plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_a_light_lane_carry_over_an_earlier_engaged_row_is_carried_and_counts" "plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_a_light_lane_carry_over_an_earlier_row_not_engaged_is_demoted" -q -p no:cacheprovider --tb=short`
```
.FF                                                                      [100%]
=================================== FAILURES ===================================
_ test_a_light_lane_carry_over_an_earlier_row_not_engaged_is_demoted[not-shown] _
/home/user/wt-2279-a/plugins/superheroes/lib/tests/test_c1l11d_carried_review.py:608: in test_a_light_lane_carry_over_an_earlier_row_not_engaged_is_demoted
    assert out["ok"] is True and out["status"] == "not-reviewed", out
E   AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/2', 'parts': 0, ...}
E   assert (True is True and 'reviewed' == 'not-reviewed'
E     
E     - not-reviewed
E     ? ----
E     + reviewed)
__ test_a_light_lane_carry_over_an_earlier_row_not_engaged_is_demoted[absent] __
/home/user/wt-2279-a/plugins/superheroes/lib/tests/test_c1l11d_carried_review.py:608: in test_a_light_lane_carry_over_an_earlier_row_not_engaged_is_demoted
    assert out["ok"] is True and out["status"] == "not-reviewed", out
E   AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/2', 'parts': 0, ...}
E   assert (True is True and 'reviewed' == 'not-reviewed'
E     
E     - not-reviewed
E     ? ----
E     + reviewed)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_a_light_lane_carry_over_an_earlier_row_not_engaged_is_demoted[not-shown]
FAILED plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_a_light_lane_carry_over_an_earlier_row_not_engaged_is_demoted[absent]
2 failed, 1 passed in 2.28s
```
The red is on the axis: with the demotion gone, a carried row over an earlier row that did not read engaged (`not-shown` or absent) counts and the record reads `reviewed` where the test requires `not-reviewed`. The engaged-row test stayed green.

**restore:** the inverse Edit.

**restore receipt** (the restored line, quoted from `review_record.py:1202` by Grep):
```
1202:            if carried_reading != "engaged":
```

**raw green:** same command.
```
...                                                                      [100%]
3 passed in 2.42s
```

## E5b — the light-lane `reading` check, always demote

**axis:** the same: an earlier row that did read engaged still counts.

**neutralization** (`review_record.py:1202`, one Edit: the demotion always fires):
```python
-            if carried_reading != "engaged":
+            if True:
```

**raw red:** same command (both node ids).
```
F..                                                                      [100%]
=================================== FAILURES ===================================
__ test_a_light_lane_carry_over_an_earlier_engaged_row_is_carried_and_counts ___
/home/user/wt-2279-a/plugins/superheroes/lib/tests/test_c1l11d_carried_review.py:595: in test_a_light_lane_carry_over_an_earlier_engaged_row_is_carried_and_counts
    assert out["ok"] is True and out["status"] == "reviewed", out
E   AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/2', 'parts': 0, ...}
E   assert (True is True and 'not-reviewed' == 'reviewed'
E     
E     - reviewed
E     ? ++++)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_a_light_lane_carry_over_an_earlier_engaged_row_is_carried_and_counts
1 failed, 2 passed in 2.34s
```
The red is on the axis: with every carried row demoted outside the full lane, the engaged carried row no longer counts and the record reads `not-reviewed` where the test requires `reviewed`. The two not-engaged cases stayed green.

**restore:** the inverse Edit.

**restore receipt** (the restored line, quoted from `review_record.py:1202` by Grep):
```
1202:            if carried_reading != "engaged":
```

**raw green:** same command.
```
...                                                                      [100%]
3 passed in 2.33s
```

## E6 — `review_record._seat_bullet`, the carried branch

**axis:** a carried row says it was carried and from which commit, never that it ran, whether or not its name carries a round suffix (`review_record.py:1915` axis comment, branch at `:1914`).

**neutralization** (`review_record.py:1914`, one Edit: the branch never fires):
```python
-        if state != "not-run" and isinstance(v.get("carried"), dict):
+        if False and state != "not-run" and isinstance(v.get("carried"), dict):
```

**raw red:** `... -m pytest "plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_a_carried_round_suffixed_reviewer_renders_carried_and_never_ran" -q -p no:cacheprovider --tb=short`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_a_carried_round_suffixed_reviewer_renders_carried_and_never_ran _____
/home/user/wt-2279-a/plugins/superheroes/lib/tests/test_c1l11d_carried_review.py:345: in test_a_carried_round_suffixed_reviewer_renders_carried_and_never_ran
    assert bullets and all("carried from %s" % s.reviewed[:7] in b and "ran" not in b.split("findings:")[0] for b in bullets), bullets
E   AssertionError: ['- code-reviewer: ran in round 1 (reported by the session) on ccc8865; findings: reported by the session']
E   assert (['- code-reviewer: ran in round 1 (reported by the session) on ccc8865; findings: reported by the session'] and False)
E    +  where False = all(<generator object test_a_carried_round_suffixed_reviewer_renders_carried_and_never_ran.<locals>.<genexpr> at 0x7f6d665f7e60>)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_a_carried_round_suffixed_reviewer_renders_carried_and_never_ran
1 failed in 1.91s
```
The red is on the axis: with the branch gone, the carried row's bullet says it ran in round 1 (reported by the session) where the test requires `carried from <commit>` and no "ran".

**restore:** the inverse Edit.

**restore receipt** (the restored line, quoted from `review_record.py:1914` by Grep):
```
1914:        if state != "not-run" and isinstance(v.get("carried"), dict):
```

**raw green:** same command.
```
.                                                                        [100%]
1 passed in 2.07s
```

## E7 — `review_record_session._empty_returning_round`, the ledger operand's rows half

**axis:** a session holding a carried finding, a finding or a ledger row ran something, so it is not the empty round (`review_record_session.py:348` axis comment, operand at `:350`). The operand is `any(sc.read_disposition_ledger(state, required=False))`: that function answers `(rows, fault)`, so the operand is true for rows (this entry) or for a fault (E8).

**neutralization** (`review_record_session.py:350`, one Edit: only the fault slot is read):
```python
-            or any(sc.read_disposition_ledger(state, required=False)):  # rows or a fault: either way not the empty round
+            or any(sc.read_disposition_ledger(state, required=False)[1:]):  # rows or a fault: either way not the empty round
```

**raw red:** `... -m pytest "plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_e5_a_session_that_ran_anything_still_refuses_as_it_did[a-ledger-row]" -q -p no:cacheprovider --tb=short`
```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_e5_a_session_that_ran_anything_still_refuses_as_it_did[a-ledger-row] ___
/home/user/wt-2279-a/plugins/superheroes/lib/tests/test_c1l11d_carried_review.py:226: in test_e5_a_session_that_ran_anything_still_refuses_as_it_did
    assert out == {"ok": False, "reason": RS.UNSUPPORTED, "detail": RS.NO_SEAT_RESULT}, out
E   AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/2', 'parts': 0, ...}
E   assert {'ok': True, ...arts': 0, ...} == {'ok': False,... seat status'}
E     
E     Differing items:
E     {'ok': True} != {'ok': False}
E     Left contains 6 more items:
E     {'action': 'created',
E      'parked': False,
E      'parts': 0,...
E     
E     ...Full output truncated, use '-vv' to show
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_e5_a_session_that_ran_anything_still_refuses_as_it_did[a-ledger-row]
1 failed in 1.64s
```
The red is on the axis: with the ledger rows unread, a session holding one ledger row is taken for the empty round and a record is written (`'ok': True, 'action': 'created'`) where the unedited test requires the refusal `review-session-unsupported`.

**restore:** the inverse Edit.

**restore receipt** (the restored line, quoted from `review_record_session.py:350` by Grep):
```
350:            or any(sc.read_disposition_ledger(state, required=False)):  # rows or a fault: either way not the empty round
```

**raw green:** same command.
```
.                                                                        [100%]
1 passed in 1.61s
```

## E8 — `review_record_session._empty_returning_round`, the ledger operand's fault half

**axis:** a ledger that cannot be read is not "no rows", so the round it belongs to is never the empty round (`review_record_session.py:348` axis comment, operand at `:350`).

**Unreachable through this entry point** (the disclosure shape): `write_from_session` cannot deliver a malformed ledger to this operand, because the session reader refuses it first with `review-session-unreadable` / `disposition-ledger-malformed` (shown by `test_e5_an_otherwise_empty_session_whose_ledger_is_malformed_is_not_the_empty_round`, `test_c1l11d_carried_review.py:230`, whose own axis comment says it is not a bite for this operand). The proof that does bite is the direct unit test `test_e8_a_malformed_disposition_ledger_is_never_the_empty_round` (`plugins/superheroes/lib/tests/test_c1l11f_wo_a_returning.py`, WO-A of build #2279), which calls `_empty_returning_round(state)` on a real empty-round session state with five malformed ledgers (a string, a dict, a list holding `None`, a list holding a string, an int) and requires `None`; it first asserts that the unedited state is the empty round (`== s.reviewed`). The operand is therefore reachable by a direct call, and it was not removed.

**neutralization** (`review_record_session.py:350`, one Edit: only the rows slot is read, so a fault reads as "no rows"):
```python
-            or any(sc.read_disposition_ledger(state, required=False)):  # rows or a fault: either way not the empty round
+            or any(sc.read_disposition_ledger(state, required=False)[:1]):  # rows or a fault: either way not the empty round
```

**raw red:** `... -m pytest "plugins/superheroes/lib/tests/test_c1l11f_wo_a_returning.py::test_e8_a_malformed_disposition_ledger_is_never_the_empty_round" -q -p no:cacheprovider --tb=line` (this one with `--tb=line`; the same run with `--tb=short` was made first with a sixth case, `[{}]`, which stayed green because an empty-dict row is not a fault: `finding_identity_key({})` is truthy; that case was removed from the test as mislabelled and the red below is the run of the final test)
```
FFFFF                                                                    [100%]
=================================== FAILURES ===================================
E   AssertionError: assert 'cb4e3507c2e8e9196386f2d384209a39a14a2cc0' is None
     +  where 'cb4e3507c2e8e9196386f2d384209a39a14a2cc0' = <function _empty_returning_round at 0x7f9a88c3b560>({'_auditTargets': [], '_coverage': [], '_fixDeltaDiff': '', '_incompletePanel': False, ...})
     +    where <function _empty_returning_round at 0x7f9a88c3b560> = RS._empty_returning_round
     +    and   {'_auditTargets': [], '_coverage': [], '_fixDeltaDiff': '', '_incompletePanel': False, ...} = dict({'_auditTargets': [], '_coverage': [], '_fixDeltaDiff': '', '_incompletePanel': False, ...}, dispositionLedger='not-a-ledger')
/home/user/wt-2279-a/plugins/superheroes/lib/tests/test_c1l11f_wo_a_returning.py:159: AssertionError: assert 'cb4e3507c2e8e9196386f2d384209a39a14a2cc0' is None
E   AssertionError: assert '05a3937c0f9c08bfe80e012f362f0ebf38102b27' is None
     +  where '05a3937c0f9c08bfe80e012f362f0ebf38102b27' = <function _empty_returning_round at 0x7f9a88c3b560>({'_auditTargets': [], '_coverage': [], '_fixDeltaDiff': '', '_incompletePanel': False, ...})
     +    where <function _empty_returning_round at 0x7f9a88c3b560> = RS._empty_returning_round
     +    and   {'_auditTargets': [], '_coverage': [], '_fixDeltaDiff': '', '_incompletePanel': False, ...} = dict({'_auditTargets': [], '_coverage': [], '_fixDeltaDiff': '', '_incompletePanel': False, ...}, dispositionLedger={'rows': []})
/home/user/wt-2279-a/plugins/superheroes/lib/tests/test_c1l11f_wo_a_returning.py:159: AssertionError: assert '05a3937c0f9c08bfe80e012f362f0ebf38102b27' is None
E   AssertionError: assert '05a3937c0f9c08bfe80e012f362f0ebf38102b27' is None
     +  where '05a3937c0f9c08bfe80e012f362f0ebf38102b27' = <function _empty_returning_round at 0x7f9a88c3b560>({'_auditTargets': [], '_coverage': [], '_fixDeltaDiff': '', '_incompletePanel': False, ...})
     +    where <function _empty_returning_round at 0x7f9a88c3b560> = RS._empty_returning_round
     +    and   {'_auditTargets': [], '_coverage': [], '_fixDeltaDiff': '', '_incompletePanel': False, ...} = dict({'_auditTargets': [], '_coverage': [], '_fixDeltaDiff': '', '_incompletePanel': False, ...}, dispositionLedger=[None])
/home/user/wt-2279-a/plugins/superheroes/lib/tests/test_c1l11f_wo_a_returning.py:159: AssertionError: assert '05a3937c0f9c08bfe80e012f362f0ebf38102b27' is None
E   AssertionError: assert '05a3937c0f9c08bfe80e012f362f0ebf38102b27' is None
     +  where '05a3937c0f9c08bfe80e012f362f0ebf38102b27' = <function _empty_returning_round at 0x7f9a88c3b560>({'_auditTargets': [], '_coverage': [], '_fixDeltaDiff': '', '_incompletePanel': False, ...})
     +    where <function _empty_returning_round at 0x7f9a88c3b560> = RS._empty_returning_round
     +    and   {'_auditTargets': [], '_coverage': [], '_fixDeltaDiff': '', '_incompletePanel': False, ...} = dict({'_auditTargets': [], '_coverage': [], '_fixDeltaDiff': '', '_incompletePanel': False, ...}, dispositionLedger=['row'])
/home/user/wt-2279-a/plugins/superheroes/lib/tests/test_c1l11f_wo_a_returning.py:159: AssertionError: assert '05a3937c0f9c08bfe80e012f362f0ebf38102b27' is None
E   AssertionError: assert '05a3937c0f9c08bfe80e012f362f0ebf38102b27' is None
     +  where '05a3937c0f9c08bfe80e012f362f0ebf38102b27' = <function _empty_returning_round at 0x7f9a88c3b560>({'_auditTargets': [], '_coverage': [], '_fixDeltaDiff': '', '_incompletePanel': False, ...})
     +    where <function _empty_returning_round at 0x7f9a88c3b560> = RS._empty_returning_round
     +    and   {'_auditTargets': [], '_coverage': [], '_fixDeltaDiff': '', '_incompletePanel': False, ...} = dict({'_auditTargets': [], '_coverage': [], '_fixDeltaDiff': '', '_incompletePanel': False, ...}, dispositionLedger=3)
/home/user/wt-2279-a/plugins/superheroes/lib/tests/test_c1l11f_wo_a_returning.py:159: AssertionError: assert '05a3937c0f9c08bfe80e012f362f0ebf38102b27' is None
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_a_returning.py::test_e8_a_malformed_disposition_ledger_is_never_the_empty_round[string]
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_a_returning.py::test_e8_a_malformed_disposition_ledger_is_never_the_empty_round[dict]
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_a_returning.py::test_e8_a_malformed_disposition_ledger_is_never_the_empty_round[none-row]
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_a_returning.py::test_e8_a_malformed_disposition_ledger_is_never_the_empty_round[string-row]
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_a_returning.py::test_e8_a_malformed_disposition_ledger_is_never_the_empty_round[int]
5 failed in 2.29s
```
The red is on the axis: with a fault read as "no rows", `_empty_returning_round` answers the last reviewed commit sha (the empty round) for every malformed ledger, where the test requires `None`.

**restore:** the inverse Edit.

**restore receipt** (the restored line, quoted from `review_record_session.py:350` by Grep):
```
350:            or any(sc.read_disposition_ledger(state, required=False)):  # rows or a fault: either way not the empty round
```

**raw green:** same command.
```
.....                                                                    [100%]
5 passed in 2.55s
```
