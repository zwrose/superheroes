# Issue 2532 bite-proof: a scope ruling and the advisor's bound are recorded decisions

**Provenance:** claude / calibrated implementer cell (implementer), run from `/home/user/wt-2532`. Every red and green is one detector node run alone: `scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest "<node>" -q -p no:xdist --tb=short`. Each neutralization is one targeted Edit-tool edit; each restore is the inverse Edit-tool edit (the same string put back). No `git checkout`, `restore`, `stash` or `reset`. Each edit finished before its run started (sequential). Detector file `plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py` was not edited between a red and its green.

**Redaction:** captures are verbatim except that `uv`'s deprecation line (`warning: The UV_NATIVE_TLS environment variable is deprecated ...`) is dropped from each. Nothing else is changed; no secrets, tokens or private URLs appear (the URLs are test fixtures on a fictitious `o/r` repository).

**Node prefix.** `ROW2` below stands for `plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py::test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named`.

## Guarded elements (the set the order declared, with sub-legs proven separately)

The order declared nine elements: E-critical, E-link, E-chat, E-receipt-pr, E-receipt-line, E-neither, E-bound-rounds, E-fetch, E-recheck. Three of them have more than one independently neutralizable leg, so each leg got its own neutralization and its own red (thirteen neutralizations in all, no grouping, nothing unproven except as noted below).

| ID | Guarded element (file) | Axis | Detector node |
|---|---|---|---|
| E-critical | `finding_outcomes._scope_or_bound_on_record`, the severity leg | a Critical finding is never settled by a scope ruling or the advisor's bound | `ROW2[a-critical-with-a-resolving-citation]` |
| E-link | `finding_outcomes._linked_comment`, comment id must be the cited one | the comment read must be the comment the link names | `ROW2[the-comment-read-is-another-comment]` |
| E-chat | `_scope_or_bound_on_record`, words inside the chat record's quoted block | a chat record that does not quote the words is not on record | `ROW2[a-chat-record-without-the-words]` |
| E-receipt-pr | `_scope_or_bound_on_record`, receipt's issue equals `reviewPr` | a receipt on another PR is not on record | `ROW2[a-receipt-on-another-pr]` |
| E-receipt-line-key | `_receipt_decision`, scope marker's key equals the finding's key | a marker naming another finding's key is not this finding's ruling | `ROW2[a-marker-naming-another-key]` |
| E-receipt-line-above | `_receipt_decision`, words on the nearest non-blank line above the marker | text elsewhere in the receipt never counts | `ROW2[the-line-above-the-marker-lacks-the-words]` |
| E-receipt-line-min | `_receipt_decision`, words at least 12 visible characters | short boilerplate is never a decision's words | `ROW2[words-under-12-characters]` |
| E-neither | `_scope_or_bound_on_record`, a body that is no chat record and no receipt | any other comment is not on record | `ROW2[a-plain-comment]` |
| E-bound-rounds | `_scope_or_bound_on_record`, `reviewRounds >= stated` | a bound above the review's own round count is not on record | `ROW2[a-bound-above-the-reviews-rounds]` |
| E-fetch | `review_record.build_record.owner_ruling_comments`, new kinds read | the writer reads the cited comment of every linked kind | `test_fetch_reads_each_distinct_cited_link_once_for_the_new_kinds_and_none_for_a_non_permalink` |
| E-recheck | `review_record._recheck_decisions`, unmet-reason branch | a failing new-kind citation names itself in the finding's reason | `ROW2[a-chat-record-without-the-words]` |
| E-recheck-sources-both | `_recheck_decisions`, `findingKey` and `findingSeverity` handed to `on_record` | the rule sees the finding's own key | `ROW2[a-critical-with-a-resolving-citation]` |
| E-recheck-sources-severity | `_recheck_decisions`, `findingSeverity` alone | the rule sees the finding's own severity | `ROW2[a-critical-through-a-chat-ruling-record]` |
| E-recheck-refresh | `_recheck_decisions`, an already-`ruling` finding whose new-kind citation resolves | its reason leads with the citation once | `test_demotion_a_ruling_whose_scope_citation_fails_becomes_a_card` |

**Not separately neutralized (disclosed).** (1) E-link is proven on the mismatched-comment-id leg; the other legs of `_linked_comment` (reader returns nothing, issue-url mismatch, no link or words) are shared with the owner ruling and proven by `wo_a_1958_owner_ruling`, and are asserted for the new kinds by `ROW2[the-comment-cannot-be-read]`, `[not-a-comment-permalink]` and `[another-repository]` but were not neutralized here. (2) E-chat's second leg (a bound's words must state a number of rounds, `the bound's words state no number of rounds`) was not neutralized: with it removed, `stated` is `None` and the next line raises `TypeError`, so a red would show a crash, not the refusal. It is asserted by `ROW2[a-bound-whose-chat-words-state-no-number]` and `test_a_chat_bound_states_its_rounds_in_digits_or_words`. (3) The `reviewRounds` not-an-integer leg (`the review's round count is unknown`) and the `reviewPr` bool leg are asserted by unit tests (`test_the_bound_needs_a_known_round_count`, `test_a_receipt_counts_only_on_a_pull_request_given_as_an_integer`) and were not neutralized. (4) The E-recheck promotion and demotion lines themselves are kind-independent code unchanged by this order; the demotion test asserts them for the new kinds.

**Note on E-neither's red.** With the check neutralized, the plain comment (which sits on issue 7, the PR under review) falls into the receipt branch and is refused there with a different text, so the finding still stays a card; the red is on the reason text, which is the axis this element claims (the comment is named as neither a ruling record nor a receipt).

**Note on E-recheck-sources-both's red.** With both keys removed the receipt path fails on the missing key first, so that red is on the reason text, not on the Critical refusal; the severity leg is proven alone by E-recheck-sources-severity, through a chat record that needs no key.

---

## E-critical

- **file:** `plugins/superheroes/lib/finding_outcomes.py` (`_scope_or_bound_on_record`)
- **detector:** `ROW2[a-critical-with-a-resolving-citation]`
- **neutralization:**
```
-    if sources.get("findingSeverity") == "Critical":
+    if False and sources.get("findingSeverity") == "Critical":
```
**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named[a-critical-with-a-resolving-citation] _
/home/user/wt-2532/plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py:145: in test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named
    assert f["outcome"] == "left-for-owner" and rec["leftForOwner"] == ["f-1"] and rec["decisionRechecks"] == []
E   AssertionError: assert ('ruling' == 'left-for-owner'
E     
E     - left-for-owner
E     + ruling)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py::test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named[a-critical-with-a-resolving-citation]
1 failed in 0.42s
```
**restore:** the inverse edit. **restore receipt** (line quoted back): `    if sources.get("findingSeverity") == "Critical":`

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.36s
```

---

## E-link

- **file:** `plugins/superheroes/lib/finding_outcomes.py` (`_linked_comment`)
- **detector:** `ROW2[the-comment-read-is-another-comment]`
- **neutralization:**
```
- _is_int(doc.get("id")) and doc["id"] == comment_id and isinstance
+ _is_int(doc.get("id")) and True and isinstance
```
**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named[the-comment-read-is-another-comment] _
/home/user/wt-2532/plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py:145: in test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named
    assert f["outcome"] == "left-for-owner" and rec["leftForOwner"] == ["f-1"] and rec["decisionRechecks"] == []
E   AssertionError: assert ('ruling' == 'left-for-owner'
E     
E     - left-for-owner
E     + ruling)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py::test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named[the-comment-read-is-another-comment]
1 failed in 0.35s
```
**restore:** the inverse edit. **restore receipt:** `_is_int(doc.get("id")) and doc["id"] == comment_id and isinstance`

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.36s
```

---

## E-chat

- **file:** `plugins/superheroes/lib/finding_outcomes.py` (`_scope_or_bound_on_record`)
- **detector:** `ROW2[a-chat-record-without-the-words]`
- **neutralization:**
```
-        if _squash(words) not in _squash(quoted):
+        if False and _squash(words) not in _squash(quoted):
```
**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named[a-chat-record-without-the-words] _
/home/user/wt-2532/plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py:145: in test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named
    assert f["outcome"] == "left-for-owner" and rec["leftForOwner"] == ["f-1"] and rec["decisionRechecks"] == []
E   AssertionError: assert ('ruling' == 'left-for-owner'
E     
E     - left-for-owner
E     + ruling)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py::test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named[a-chat-record-without-the-words]
1 failed in 0.44s
```
**restore:** the inverse edit. **restore receipt:** `        if _squash(words) not in _squash(quoted):` (followed by `return False, "the ruling's comment does not hold the owner's words"`)

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.35s
```

---

## E-receipt-pr

- **file:** `plugins/superheroes/lib/finding_outcomes.py` (`_scope_or_bound_on_record`)
- **detector:** `ROW2[a-receipt-on-another-pr]`
- **neutralization:**
```
-        if not (_is_int(pr) and number == pr):
+        if False and not (_is_int(pr) and number == pr):
```
**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named[a-receipt-on-another-pr] _
/home/user/wt-2532/plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py:145: in test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named
    assert f["outcome"] == "left-for-owner" and rec["leftForOwner"] == ["f-1"] and rec["decisionRechecks"] == []
E   AssertionError: assert ('ruling' == 'left-for-owner'
E     
E     - left-for-owner
E     + ruling)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py::test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named[a-receipt-on-another-pr]
1 failed in 0.38s
```
**restore:** the inverse edit. **restore receipt:** `        if not (_is_int(pr) and number == pr):`

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.38s
```

---

## E-receipt-line-key

- **file:** `plugins/superheroes/lib/finding_outcomes.py` (`_receipt_decision`)
- **detector:** `ROW2[a-marker-naming-another-key]`
- **neutralization:**
```
-            if marked is None or not (isinstance(key, str) and key.strip() and marked.group(1) == key):
+            if marked is None or not (isinstance(key, str) and key.strip() and True):
```
**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named[a-marker-naming-another-key] _
/home/user/wt-2532/plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py:145: in test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named
    assert f["outcome"] == "left-for-owner" and rec["leftForOwner"] == ["f-1"] and rec["decisionRechecks"] == []
E   AssertionError: assert ('ruling' == 'left-for-owner'
E     
E     - left-for-owner
E     + ruling)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py::test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named[a-marker-naming-another-key]
1 failed in 0.39s
```
**restore:** the inverse edit. **restore receipt:** `            if marked is None or not (isinstance(key, str) and key.strip() and marked.group(1) == key):`

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.41s
```

---

## E-receipt-line-above

- **file:** `plugins/superheroes/lib/finding_outcomes.py` (`_receipt_decision`)
- **detector:** `ROW2[the-line-above-the-marker-lacks-the-words]`
- **neutralization:**
```
-        if held in _squash(above):
+        if True:
```
**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named[the-line-above-the-marker-lacks-the-words] _
/home/user/wt-2532/plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py:145: in test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named
    assert f["outcome"] == "left-for-owner" and rec["leftForOwner"] == ["f-1"] and rec["decisionRechecks"] == []
E   AssertionError: assert ('ruling' == 'left-for-owner'
E     
E     - left-for-owner
E     + ruling)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py::test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named[the-line-above-the-marker-lacks-the-words]
1 failed in 0.40s
```
**restore:** the inverse edit. **restore receipt:** `        if held in _squash(above):` (followed by `return True, rounds`)

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.38s
```

---

## E-receipt-line-min

- **file:** `plugins/superheroes/lib/finding_outcomes.py` (`_receipt_decision`)
- **detector:** `ROW2[words-under-12-characters]`
- **neutralization:**
```
-    if len(held) < _RECEIPT_WORDS_MIN:
+    if False and len(held) < _RECEIPT_WORDS_MIN:
```
**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named[words-under-12-characters] _
/home/user/wt-2532/plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py:145: in test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named
    assert f["outcome"] == "left-for-owner" and rec["leftForOwner"] == ["f-1"] and rec["decisionRechecks"] == []
E   AssertionError: assert ('ruling' == 'left-for-owner'
E     
E     - left-for-owner
E     + ruling)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py::test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named[words-under-12-characters]
1 failed in 0.36s
```
**restore:** the inverse edit. **restore receipt:** `    if len(held) < _RECEIPT_WORDS_MIN:`

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.40s
```

---

## E-neither

- **file:** `plugins/superheroes/lib/finding_outcomes.py` (`_scope_or_bound_on_record`)
- **detector:** `ROW2[a-plain-comment]`
- **neutralization:**
```
-    if quoted is None and not receipt:
+    if False and quoted is None and not receipt:
```
**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named[a-plain-comment] _
/home/user/wt-2532/plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py:146: in test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named
    assert f["reason"] == "waits for the owner" + NOT_ON_RECORD[case["kind"]] % leg
E   AssertionError: assert 'waits for th... these words)' == 'waits for th... vet receipt)'
E     
E     Skipping 59 identical leading characters in diff, use -v to show
E     - cord (the ruling's comment is neither a chat-ruling record nor a vet receipt)
E     + cord (the vet receipt records no scope ruling for this finding with these words)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py::test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named[a-plain-comment]
1 failed in 0.36s
```
**restore:** the inverse edit. **restore receipt:** `    if quoted is None and not receipt:`

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.35s
```

---

## E-bound-rounds

- **file:** `plugins/superheroes/lib/finding_outcomes.py` (`_scope_or_bound_on_record`)
- **detector:** `ROW2[a-bound-above-the-reviews-rounds]`
- **neutralization:**
```
-        if count < stated:
+        if False and count < stated:
```
**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named[a-bound-above-the-reviews-rounds] _
/home/user/wt-2532/plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py:145: in test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named
    assert f["outcome"] == "left-for-owner" and rec["leftForOwner"] == ["f-1"] and rec["decisionRechecks"] == []
E   AssertionError: assert ('ruling' == 'left-for-owner'
E     
E     - left-for-owner
E     + ruling)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py::test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named[a-bound-above-the-reviews-rounds]
1 failed in 0.36s
```
**restore:** the inverse edit. **restore receipt:** `        if count < stated:`

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.36s
```

---

## E-fetch

- **file:** `plugins/superheroes/lib/review_record.py` (`build_record.owner_ruling_comments`)
- **detector:** `plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py::test_fetch_reads_each_distinct_cited_link_once_for_the_new_kinds_and_none_for_a_non_permalink`
- **neutralization:**
```
-            if isinstance(by, dict) and by.get("kind") in finding_outcomes.LINKED_KINDS and f.get("outcome") in (_RULING, _LEFT_FOR_OWNER):
+            if isinstance(by, dict) and by.get("kind") == finding_outcomes.OWNER_RULING and f.get("outcome") in (_RULING, _LEFT_FOR_OWNER):
```
**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_fetch_reads_each_distinct_cited_link_once_for_the_new_kinds_and_none_for_a_non_permalink _
/home/user/wt-2532/plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py:199: in test_fetch_reads_each_distinct_cited_link_once_for_the_new_kinds_and_none_for_a_non_permalink
    assert calls == [("o/r", 777), ("o/r", 778), ("o/r", 779)]
E   AssertionError: assert [] == [('o/r', 777)... ('o/r', 779)]
E     
E     Right contains 3 more items, first extra item: ('o/r', 777)
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py::test_fetch_reads_each_distinct_cited_link_once_for_the_new_kinds_and_none_for_a_non_permalink
1 failed in 0.36s
```
**restore:** the inverse edit. **restore receipt:** `            if isinstance(by, dict) and by.get("kind") in finding_outcomes.LINKED_KINDS and f.get("outcome") in (_RULING, _LEFT_FOR_OWNER):`

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.35s
```

---

## E-recheck

- **file:** `plugins/superheroes/lib/review_record.py` (`_recheck_decisions`)
- **detector:** `ROW2[a-chat-record-without-the-words]`
- **neutralization:**
```
-            elif outcome == _LEFT_FOR_OWNER and by.get("kind") in finding_outcomes.LINKED_KINDS and not ok:
+            elif outcome == _LEFT_FOR_OWNER and by.get("kind") == finding_outcomes.OWNER_RULING and not ok:
```
**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named[a-chat-record-without-the-words] _
/home/user/wt-2532/plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py:146: in test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named
    assert f["reason"] == "waits for the owner" + NOT_ON_RECORD[case["kind"]] % leg
E   assert 'waits for the owner' == "waits for th...wner's words)"
E     
E     - waits for the owner; the scope ruling it cites is not on record (the ruling's comment does not hold the owner's words)
E     + waits for the owner
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py::test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named[a-chat-record-without-the-words]
1 failed in 0.38s
```
**restore:** the inverse edit. **restore receipt:** `            elif outcome == _LEFT_FOR_OWNER and by.get("kind") in finding_outcomes.LINKED_KINDS and not ok:`

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.37s
```

---

## E-recheck-sources-both

- **file:** `plugins/superheroes/lib/review_record.py` (`_recheck_decisions`)
- **detector:** `ROW2[a-critical-with-a-resolving-citation]` (its red is on the reason text; see the note above)
- **neutralization:**
```
-                by, dict(sources(), findingKey=_key(f), findingSeverity=f.get("severity")))
+                by, sources())
```
**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named[a-critical-with-a-resolving-citation] _
/home/user/wt-2532/plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py:146: in test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named
    assert f["reason"] == "waits for the owner" + NOT_ON_RECORD[case["kind"]] % leg
E   assert 'waits for th... these words)' == "waits for th...isor's bound)"
E     
E     Skipping 55 identical leading characters in diff, use -v to show
E     - n record (a Critical finding is never settled by a scope ruling or the advisor's bound)
E     + n record (the vet receipt records no scope ruling for this finding with these words)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py::test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named[a-critical-with-a-resolving-citation]
1 failed in 0.35s
```
**restore:** the inverse edit. **restore receipt:** `                by, dict(sources(), findingKey=_key(f), findingSeverity=f.get("severity")))`

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.36s
```

---

## E-recheck-sources-severity

- **file:** `plugins/superheroes/lib/review_record.py` (`_recheck_decisions`)
- **detector:** `ROW2[a-critical-through-a-chat-ruling-record]` (added after the previous entry showed its red on the key; a chat record needs no key, so only the severity leg can bite)
- **neutralization:**
```
-                by, dict(sources(), findingKey=_key(f), findingSeverity=f.get("severity")))
+                by, dict(sources(), findingKey=_key(f)))
```
**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named[a-critical-through-a-chat-ruling-record] _
/home/user/wt-2532/plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py:146: in test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named
    assert f["outcome"] == "left-for-owner" and rec["leftForOwner"] == ["f-1"] and rec["decisionRechecks"] == []
E   AssertionError: assert ('ruling' == 'left-for-owner'
E     
E     - left-for-owner
E     + ruling)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py::test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named[a-critical-through-a-chat-ruling-record]
1 failed in 0.44s
```
**restore:** the inverse edit. **restore receipt:** `                by, dict(sources(), findingKey=_key(f), findingSeverity=f.get("severity")))`

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.42s
```

---

## E-recheck-refresh

- **file:** `plugins/superheroes/lib/review_record.py` (`_recheck_decisions`)
- **detector:** `plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py::test_demotion_a_ruling_whose_scope_citation_fails_becomes_a_card`
- **neutralization:**
```
-            elif outcome == _RULING and ok and by.get("kind") in finding_outcomes.LINKED_KINDS:
+            elif outcome == _RULING and ok and by.get("kind") == finding_outcomes.OWNER_RULING:
```
**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_demotion_a_ruling_whose_scope_citation_fails_becomes_a_card _______
/home/user/wt-2532/plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py:177: in test_demotion_a_ruling_whose_scope_citation_fails_becomes_a_card
    assert the_finding(kept)["reason"].startswith('scope ruling "%s" (%s); ' % (SW, RU)) and kept["decisionRechecks"] == []
E   assert (False)
E    +  where False = <built-in method startswith of str object at 0x7faa319154f0>(('scope ruling "%s" (%s); ' % ('the page total belongs to the follow-up work', 'https://github.com/o/r/issues/7#issuecomment-777')))
E    +    where <built-in method startswith of str object at 0x7faa319154f0> = 'the owner said so'.startswith
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py::test_demotion_a_ruling_whose_scope_citation_fails_becomes_a_card
1 failed in 0.37s
```
**restore:** the inverse edit. **restore receipt:** `            elif outcome == _RULING and ok and by.get("kind") in finding_outcomes.LINKED_KINDS:`

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.35s
```

---

## Review round 1 additions (orchestrator-typed fix, commit `90801f8`)

**Provenance:** the build orchestrator (claude), at the review loop's apply-fixes step; run from a detached probe worktree at `5f283fb`, an unpushed first cut of the same fix that was remade as `90801f8` only to drop one trailing newline the break-it test file had gained in extraction (production code identical; the test file now holds the test role's bytes exactly). Same command shape as above (`pytest "<node>" -q -p no:xdist --tb=line`), one Edit-tool neutralization each, restored by the inverse Edit-tool edit, each run sequential. The two E-repeat detectors are the review's own break-it test (`test_review_scope_bound_critical_repeat_break_it.py`, written by the test role, kept byte for byte); the E-pull-link detectors are in `test_review_record_scope_bound_2532.py`. The green for all four is one run of both detector files on the restored tree: `63 passed in 0.65s`. Nothing quoted is a secret, token, private URL or personal detail; nothing is redacted.

### E-repeat

- **file:** `plugins/superheroes/lib/review_record.py` (`_follow_repeats`, the repeat's own check)
- **detector:** `test_critical_recipient_keeps_its_owner_card[repeat-advisor-bound]`
- **neutralization:** `_finding_sources(sources(), f)` → `sources()` in the repeat's `on_record` call
- **raw red** (exit 1): `E   AssertionError: assert 'ruling' == 'left-for-owner'` at `test_review_scope_bound_critical_repeat_break_it.py:41`; `1 failed in 0.50s`

### E-repeat-member

- **file:** `plugins/superheroes/lib/review_record.py` (`_follow_repeats`, each merged member's own check)
- **detector:** `test_critical_recipient_keeps_its_owner_card[member-scope-ruling]`
- **neutralization:** `if not held:` → `if False and not held:`
- **raw red** (exit 1): `E   AssertionError: assert 'ruling' == 'left-for-owner'` at `test_review_scope_bound_critical_repeat_break_it.py:41`; `1 failed in 0.50s`

### E-pull-link (accept)

- **file:** `plugins/superheroes/lib/finding_outcomes.py` (`comment_permalink`)
- **detector:** `test_a_receipt_linked_by_its_pull_request_permalink_resolves` (both kinds)
- **neutralization:** the kind-chosen form → `form = _COMMENT_PERMALINK` for every kind
- **raw red** (exit 1): `E   AssertionError: assert [] == [('o/r', 777)]` at `test_review_record_scope_bound_2532.py:198`, for both parameters; `2 failed in 3.86s`

### E-pull-link (owner refuses)

- **file:** `plugins/superheroes/lib/finding_outcomes.py` (`comment_permalink`)
- **detector:** `test_an_owner_ruling_never_takes_a_pull_request_permalink`
- **neutralization:** the kind-chosen form → `form = _PULL_COMMENT_PERMALINK` for every kind
- **raw red** (exit 1): `E   assert (True, 'owner...comment-777)') == (False, "the ...nt permalink")` at `test_review_record_scope_bound_2532.py:205`; `1 failed in 0.42s`

**restore receipts:** `ok, text = finding_outcomes.on_record(g["decidedBy"], _finding_sources(sources(), f))`; `if not held:`; `form = _PULL_COMMENT_PERMALINK if kind in (SCOPE_RULING, ADVISOR_BOUND) else _COMMENT_PERMALINK`. `git status --porcelain` on the probe worktree read empty after the last restore.
