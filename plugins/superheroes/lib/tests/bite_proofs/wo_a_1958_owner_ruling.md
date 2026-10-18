# WO-A (#1958) bite-proof: an owner ruling reaches the review record

**Provenance:** claude / sonnet-5.5 (implementer). Run from `/home/user/wt-1958`; every red and green is the detector node run alone (`scripts/pinned-python -B -m pytest "<node>" -q -p no:cacheprovider`). Each neutralization is one targeted edit and each restore is the inverse edit (the same string replaced back); no `git checkout`/`restore`/`stash`/`reset`. Captures are verbatim and unredacted; they carry no secrets, only repository paths and test text. Driven by a throwaway script outside the repository.

## Guarded elements (the set WO-A declared, plus V2)

| ID | Guarded element | Axis | Detector node (all in `plugins/superheroes/lib/tests/test_review_record_owner_ruling.py`) |
|---|---|---|---|
| L1 | leg L1 in `comment_permalink`: the ruling's link must fullmatch an issue-comment permalink | a link that is not `https://github.com/<owner>/<repo>/issues/<n>#issuecomment-<id>` is not on record | `test_t2_no_pointer_no_fold_and_the_finding_stays_a_card[L1-not-a-comment-permalink]` |
| L2 | leg L2 in `comment_permalink`: the link's repository must equal the PR's repository | a comment in another repository is not on record | `test_t2_no_pointer_no_fold_and_the_finding_stays_a_card[L2-another-repository]` |
| L3 | leg L3 in `_owner_ruling_on_record`: the comment read must be the comment (id) on the issue (issue_url) the link names | a missing or mismatched comment document is not on record | `test_t2_no_pointer_no_fold_and_the_finding_stays_a_card[L3-another-comment-id]` |
| L4 | leg L4 in `_owner_ruling_on_record`: author_association must be exactly OWNER | only the repository owner's own comment is a ruling | `test_t2_no_pointer_no_fold_and_the_finding_stays_a_card[L4-member]` |
| L5 | leg L5 in `_owner_ruling_on_record`: the body must hold the quoted words | a comment that does not hold the owner's words is not on record | `test_t2_no_pointer_no_fold_and_the_finding_stays_a_card[L5-words-absent]` |
| H | the hand-off `_apply_owner_rulings` in `review_record.py` that sets decidedBy from an entry | an ownerRulings entry reaches the finding it names | `test_t1_a_ruled_finding_folds_into_already_decided_and_leaves_no_card` |
| V | the names-exactly-one-finding check in `_validate` (`review_record.py`) | an entry that names no finding, or two, is refused `review-account-invalid` | `test_t5_a_malformed_entry_refuses_the_account[E9-names-no-finding]` |
| V2 | the no-two-entries-name-one-finding check in `_validate` (`review_record.py`), the second half of the one-finding rule | two entries for one finding are refused | `test_t5_a_malformed_entry_refuses_the_account[E11-two-entries-one-finding]` |
| M | the merged-member expansion `_owner_rulings` in `review_record_session.py` | a ruling on a merged group's representative covers its members | `test_t8_the_session_adapter_expands_a_ruling_on_a_merged_groups_representative_to_its_members` |
| R | the failed-citation reason in `_recheck_decisions` (`review_record.py`) | a left-for-owner finding whose owner ruling does not resolve says why in its reason | `test_t2_no_pointer_no_fold_and_the_finding_stays_a_card[L5-words-absent]` |

No grouping: ten elements (the nine declared, with V's two halves proven separately as V and V2), ten neutralizations, ten reds. No element is unproven. L3 is proven on the mismatched-comment-id case; its other branches (reader returns None or raises, issue_url mismatches) are asserted by their own T2 nodes in the same module but were not separately neutralized.

V's red is a `ValueError` out of the hand-off (`(j,) = ...` on an unvalidated entry) rather than a `Refusal`: with the check neutralized the entry reaches the hand-off, and the test's `pytest.raises(rr.Refusal)` is not satisfied. It is still the detector failing.

---

## L1: leg L1 in `comment_permalink`: the ruling's link must fullmatch an issue-comment permalink

- **axis:** a link that is not `https://github.com/<owner>/<repo>/issues/<n>#issuecomment-<id>` is not on record
- **file:** `plugins/superheroes/lib/finding_outcomes.py`
- **detector:** `plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_t2_no_pointer_no_fold_and_the_finding_stays_a_card[L1-not-a-comment-permalink]`
- **sha256 before:** `184a7e5f0a997c65ecb16dd0d1b4fea5fcecf5239ba4c5d082d1691f99df155b`
- **sha256 neutralized:** `e3c5ad9e05bd31a21fcb7b75a99c8014a0827545e26844b40fc11f1478052cf5`
- **sha256 after restore:** `184a7e5f0a997c65ecb16dd0d1b4fea5fcecf5239ba4c5d082d1691f99df155b` (equals "before")

**neutralization** (one targeted replacement; the replaced text, then its replacement):
```
- r"https://github\.com/([^/\s#?]+)/([^/\s#?]+)/issues/([0-9]+)#issuecomment-([0-9]+)")
+ r"https://github\.com/([^/\s#?]+)/([^/\s#?]+)/(?:issues|pull)/([0-9]+)#issuecomment-([0-9]+)")
```

**raw red** (exit code 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t2_no_pointer_no_fold_and_the_finding_stays_a_card[L1-not-a-comment-permalink] _

over = {'url': 'https://github.com/o/r/pull/12#issuecomment-555'}, kw = {}
why = "the ruling's link is not a comment permalink"

    @pytest.mark.parametrize("over, kw, why", FAILS)
    def test_t2_no_pointer_no_fold_and_the_finding_stays_a_card(over, kw, why):
        # Axis: fail closed, a left-for-owner finding stays one unless every leg of its pointer holds; it is never dropped.
        rec = build([entry(**over)], **kw)
        f = the_finding(rec)
>       assert f["outcome"] == "left-for-owner" and rec["leftForOwner"] == ["f-1"] and rec["decisionRechecks"] == []
E       AssertionError: assert ('ruling' == 'left-for-owner'
E         
E         - left-for-owner
E         + ruling)

/home/user/wt-1958/plugins/superheroes/lib/tests/test_review_record_owner_ruling.py:114: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_t2_no_pointer_no_fold_and_the_finding_stays_a_card[L1-not-a-comment-permalink]
1 failed in 0.37s
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

**restore** (the inverse replacement) and the restored lines quoted back:
```
r"https://github\.com/([^/\s#?]+)/([^/\s#?]+)/issues/([0-9]+)#issuecomment-([0-9]+)")
```

**raw green** (exit code 0):
```
.                                                                        [100%]
1 passed in 0.48s
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

---

## L2: leg L2 in `comment_permalink`: the link's repository must equal the PR's repository

- **axis:** a comment in another repository is not on record
- **file:** `plugins/superheroes/lib/finding_outcomes.py`
- **detector:** `plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_t2_no_pointer_no_fold_and_the_finding_stays_a_card[L2-another-repository]`
- **sha256 before:** `184a7e5f0a997c65ecb16dd0d1b4fea5fcecf5239ba4c5d082d1691f99df155b`
- **sha256 neutralized:** `8d19b1875a4068621e96bb183f6a82b8ab4755b27bfc57430d5619ee9022c592`
- **sha256 after restore:** `184a7e5f0a997c65ecb16dd0d1b4fea5fcecf5239ba4c5d082d1691f99df155b` (equals "before")

**neutralization** (one targeted replacement; the replaced text, then its replacement):
```
-     if not (isinstance(repo, str) and repo.lower()
+     if False and not (isinstance(repo, str) and repo.lower()
```

**raw red** (exit code 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t2_no_pointer_no_fold_and_the_finding_stays_a_card[L2-another-repository] _

over = {'url': 'https://github.com/x/y/issues/12#issuecomment-555'}, kw = {}
why = "the ruling's link is not in this repository"

    @pytest.mark.parametrize("over, kw, why", FAILS)
    def test_t2_no_pointer_no_fold_and_the_finding_stays_a_card(over, kw, why):
        # Axis: fail closed, a left-for-owner finding stays one unless every leg of its pointer holds; it is never dropped.
        rec = build([entry(**over)], **kw)
        f = the_finding(rec)
        assert f["outcome"] == "left-for-owner" and rec["leftForOwner"] == ["f-1"] and rec["decisionRechecks"] == []
>       assert f["reason"] == "waits for the owner" + NOT_ON_RECORD % why
E       AssertionError: assert 'waits for th... not be read)' == 'waits for th...s repository)'
E         
E         Skipping 68 identical leading characters in diff, use -v to show
E         -  ruling's link is not in this repository)
E         +  ruling's comment could not be read)

/home/user/wt-1958/plugins/superheroes/lib/tests/test_review_record_owner_ruling.py:115: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_t2_no_pointer_no_fold_and_the_finding_stays_a_card[L2-another-repository]
1 failed in 0.41s
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

**restore** (the inverse replacement) and the restored lines quoted back:
```
    if not (isinstance(repo, str) and repo.lower()
```

**raw green** (exit code 0):
```
.                                                                        [100%]
1 passed in 0.39s
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

---

## L3: leg L3 in `_owner_ruling_on_record`: the comment read must be the comment (id) on the issue (issue_url) the link names

- **axis:** a missing or mismatched comment document is not on record
- **file:** `plugins/superheroes/lib/finding_outcomes.py`
- **detector:** `plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_t2_no_pointer_no_fold_and_the_finding_stays_a_card[L3-another-comment-id]`
- **sha256 before:** `184a7e5f0a997c65ecb16dd0d1b4fea5fcecf5239ba4c5d082d1691f99df155b`
- **sha256 neutralized:** `c662bafc10c2a42ed2ae5b4752ef2f7055383432e188932def54e18a3f2d8dd5`
- **sha256 after restore:** `184a7e5f0a997c65ecb16dd0d1b4fea5fcecf5239ba4c5d082d1691f99df155b` (equals "before")

**neutralization** (one targeted replacement; the replaced text, then its replacement):
```
-     if not (isinstance(doc, dict) and _is_int
+     if False and not (isinstance(doc, dict) and _is_int
```

**raw red** (exit code 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t2_no_pointer_no_fold_and_the_finding_stays_a_card[L3-another-comment-id] _

over = {}
kw = {'doc': {'id': 556, 'issue_url': 'https://api.github.com/repos/o/r/issues/12', 'html_url': 'https://github.com/o/r/issues/12#issuecomment-555', 'author_association': 'OWNER', ...}}
why = "the ruling's comment could not be read"

    @pytest.mark.parametrize("over, kw, why", FAILS)
    def test_t2_no_pointer_no_fold_and_the_finding_stays_a_card(over, kw, why):
        # Axis: fail closed, a left-for-owner finding stays one unless every leg of its pointer holds; it is never dropped.
        rec = build([entry(**over)], **kw)
        f = the_finding(rec)
>       assert f["outcome"] == "left-for-owner" and rec["leftForOwner"] == ["f-1"] and rec["decisionRechecks"] == []
E       AssertionError: assert ('ruling' == 'left-for-owner'
E         
E         - left-for-owner
E         + ruling)

/home/user/wt-1958/plugins/superheroes/lib/tests/test_review_record_owner_ruling.py:114: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_t2_no_pointer_no_fold_and_the_finding_stays_a_card[L3-another-comment-id]
1 failed in 0.48s
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

**restore** (the inverse replacement) and the restored lines quoted back:
```
    if not (isinstance(doc, dict) and _is_int
```

**raw green** (exit code 0):
```
.                                                                        [100%]
1 passed in 0.40s
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

---

## L4: leg L4 in `_owner_ruling_on_record`: author_association must be exactly OWNER

- **axis:** only the repository owner's own comment is a ruling
- **file:** `plugins/superheroes/lib/finding_outcomes.py`
- **detector:** `plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_t2_no_pointer_no_fold_and_the_finding_stays_a_card[L4-member]`
- **sha256 before:** `184a7e5f0a997c65ecb16dd0d1b4fea5fcecf5239ba4c5d082d1691f99df155b`
- **sha256 neutralized:** `c7defc5fc7bfb797c38cd5a60b7f413c1245a42f4a05b472fef6d8616c6259c3`
- **sha256 after restore:** `184a7e5f0a997c65ecb16dd0d1b4fea5fcecf5239ba4c5d082d1691f99df155b` (equals "before")

**neutralization** (one targeted replacement; the replaced text, then its replacement):
```
-     if doc.get("author_association") != "OWNER":
+     if False and doc.get("author_association") != "OWNER":
```

**raw red** (exit code 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_t2_no_pointer_no_fold_and_the_finding_stays_a_card[L4-member] ______

over = {}
kw = {'doc': {'id': 555, 'issue_url': 'https://api.github.com/repos/o/r/issues/12', 'html_url': 'https://github.com/o/r/issues/12#issuecomment-555', 'author_association': 'MEMBER', ...}}
why = "the ruling's comment is not the owner's"

    @pytest.mark.parametrize("over, kw, why", FAILS)
    def test_t2_no_pointer_no_fold_and_the_finding_stays_a_card(over, kw, why):
        # Axis: fail closed, a left-for-owner finding stays one unless every leg of its pointer holds; it is never dropped.
        rec = build([entry(**over)], **kw)
        f = the_finding(rec)
>       assert f["outcome"] == "left-for-owner" and rec["leftForOwner"] == ["f-1"] and rec["decisionRechecks"] == []
E       AssertionError: assert ('ruling' == 'left-for-owner'
E         
E         - left-for-owner
E         + ruling)

/home/user/wt-1958/plugins/superheroes/lib/tests/test_review_record_owner_ruling.py:114: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_t2_no_pointer_no_fold_and_the_finding_stays_a_card[L4-member]
1 failed in 0.48s
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

**restore** (the inverse replacement) and the restored lines quoted back:
```
    if doc.get("author_association") != "OWNER":
```

**raw green** (exit code 0):
```
.                                                                        [100%]
1 passed in 0.36s
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

---

## L5: leg L5 in `_owner_ruling_on_record`: the body must hold the quoted words

- **axis:** a comment that does not hold the owner's words is not on record
- **file:** `plugins/superheroes/lib/finding_outcomes.py`
- **detector:** `plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_t2_no_pointer_no_fold_and_the_finding_stays_a_card[L5-words-absent]`
- **sha256 before:** `184a7e5f0a997c65ecb16dd0d1b4fea5fcecf5239ba4c5d082d1691f99df155b`
- **sha256 neutralized:** `26fe5904a01825062f6b27d7ee1c01b92e95e1a2d5bbf11c911c159e97f85a92`
- **sha256 after restore:** `184a7e5f0a997c65ecb16dd0d1b4fea5fcecf5239ba4c5d082d1691f99df155b` (equals "before")

**neutralization** (one targeted replacement; the replaced text, then its replacement):
```
-     if not (isinstance(body, str) and _squash
+     if False and not (isinstance(body, str) and _squash
```

**raw red** (exit code 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_t2_no_pointer_no_fold_and_the_finding_stays_a_card[L5-words-absent] ___

over = {}
kw = {'doc': {'id': 555, 'issue_url': 'https://api.github.com/repos/o/r/issues/12', 'html_url': 'https://github.com/o/r/issues/12#issuecomment-555', 'author_association': 'OWNER', ...}}
why = "the ruling's comment does not hold the owner's words"

    @pytest.mark.parametrize("over, kw, why", FAILS)
    def test_t2_no_pointer_no_fold_and_the_finding_stays_a_card(over, kw, why):
        # Axis: fail closed, a left-for-owner finding stays one unless every leg of its pointer holds; it is never dropped.
        rec = build([entry(**over)], **kw)
        f = the_finding(rec)
>       assert f["outcome"] == "left-for-owner" and rec["leftForOwner"] == ["f-1"] and rec["decisionRechecks"] == []
E       AssertionError: assert ('ruling' == 'left-for-owner'
E         
E         - left-for-owner
E         + ruling)

/home/user/wt-1958/plugins/superheroes/lib/tests/test_review_record_owner_ruling.py:114: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_t2_no_pointer_no_fold_and_the_finding_stays_a_card[L5-words-absent]
1 failed in 0.48s
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

**restore** (the inverse replacement) and the restored lines quoted back:
```
    if not (isinstance(body, str) and _squash
```

**raw green** (exit code 0):
```
.                                                                        [100%]
1 passed in 0.37s
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

---

## H: the hand-off `_apply_owner_rulings` in `review_record.py` that sets decidedBy from an entry

- **axis:** an ownerRulings entry reaches the finding it names
- **file:** `plugins/superheroes/lib/review_record.py`
- **detector:** `plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_t1_a_ruled_finding_folds_into_already_decided_and_leaves_no_card`
- **sha256 before:** `5dcf5f07af548459f3f0c549c7f84805a58555d61e8232849743e88e1a42054e`
- **sha256 neutralized:** `2531234a6fcd327ba805c2e58e9c22da40c4631f0274fbe5472ee6cb4ef5f453`
- **sha256 after restore:** `5dcf5f07af548459f3f0c549c7f84805a58555d61e8232849743e88e1a42054e` (equals "before")

**neutralization** (one targeted replacement; the replaced text, then its replacement):
```
-             out[j] = dict(out[j], decidedBy={"kind"
+             out[j] = dict(out[j], NEUTRALIZED_decidedBy={"kind"
```

**raw red** (exit code 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_t1_a_ruled_finding_folds_into_already_decided_and_leaves_no_card _____

    def test_t1_a_ruled_finding_folds_into_already_decided_and_leaves_no_card():
        # Axis: the whole path, a left-for-owner finding with a resolving pointer ends ruling and the sheet does not ask.
        rec = build([entry()])
        f = the_finding(rec)
>       assert f["outcome"] == "ruling" and f["sheetPart"] == rr.rfs.OUTCOME_SHEET_PART["ruling"]
E       AssertionError: assert ('left-for-owner' == 'ruling'
E         
E         - ruling
E         + left-for-owner)

/home/user/wt-1958/plugins/superheroes/lib/tests/test_review_record_owner_ruling.py:67: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_t1_a_ruled_finding_folds_into_already_decided_and_leaves_no_card
1 failed in 0.39s
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

**restore** (the inverse replacement) and the restored lines quoted back:
```
            out[j] = dict(out[j], decidedBy={"kind"
```

**raw green** (exit code 0):
```
.                                                                        [100%]
1 passed in 0.49s
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

---

## V: the names-exactly-one-finding check in `_validate` (`review_record.py`)

- **axis:** an entry that names no finding, or two, is refused `review-account-invalid`
- **file:** `plugins/superheroes/lib/review_record.py`
- **detector:** `plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_t5_a_malformed_entry_refuses_the_account[E9-names-no-finding]`
- **sha256 before:** `5dcf5f07af548459f3f0c549c7f84805a58555d61e8232849743e88e1a42054e`
- **sha256 neutralized:** `d6b9e5549d69ec78af383f841f11658b7fb0ede0562917ff7ccb8b033a32140b`
- **sha256 after restore:** `5dcf5f07af548459f3f0c549c7f84805a58555d61e8232849743e88e1a42054e` (equals "before")

**neutralization** (one targeted replacement; the replaced text, then its replacement):
```
-         chk(len(hit) == 1, f"{where}.key names {'no finding' if not hit else 'more than one finding'}")
          chk(hit.isdisjoint(ruled)
+         chk(True or len(hit) == 1, f"{where}.key names {'no finding' if not hit else 'more than one finding'}")
          chk(hit.isdisjoint(ruled)
```

**raw red** (exit code 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_t5_a_malformed_entry_refuses_the_account[E9-names-no-finding] ______

rulings = [{'key': 'nobody', 'url': 'https://github.com/o/r/issues/12#issuecomment-555', 'words': 'ship it as is'}]
detail = 'ownerRulings[0].key names no finding'

    @pytest.mark.parametrize("rulings, detail", [
        pytest.param([entry(key="nobody")], "ownerRulings[0].key names no finding", id="E9-names-no-finding"),
        pytest.param([entry(key="dup")], "ownerRulings[0].key names more than one finding", id="E10-names-two-findings"),
        pytest.param([entry(), entry(key=rr._key(X))], "ownerRulings[1].key names a finding another entry names",
                     id="E11-two-entries-one-finding"),
        pytest.param([entry(url=3)], "ownerRulings[0].url", id="url-not-a-string"),
        pytest.param([entry(url="")], "ownerRulings[0].url", id="url-empty"),
        pytest.param([entry(url="  ")], "ownerRulings[0].url", id="url-blank"),
        pytest.param([entry(words=None)], "ownerRulings[0].words", id="words-not-a-string"),
        pytest.param([entry(words=" \n")], "ownerRulings[0].words", id="words-blank"),
        pytest.param([entry(key="")], "ownerRulings[0].key", id="key-empty"),
        pytest.param([entry(key=7)], "ownerRulings[0].key", id="key-not-a-string"),
        pytest.param(["f-1"], "ownerRulings[0]", id="entry-not-an-object"),
        pytest.param("f-1", "ownerRulings", id="not-a-list"),
    ])
    def test_t5_a_malformed_entry_refuses_the_account(rulings, detail):
        # Axis: every entry names exactly one finding, once, with a link and words; anything else is refused whole.
        findings = [X, Y, dict(Y, id="dup", title="Other", line=1), dict(Y, id="dup", title="Another", line=2)]
        with pytest.raises(rr.Refusal) as refused:
>           build(rulings, findings)

/home/user/wt-1958/plugins/superheroes/lib/tests/test_review_record_owner_ruling.py:180: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt-1958/plugins/superheroes/lib/tests/test_review_record_owner_ruling.py:50: in build
    return rr.build_record(account(rulings, findings), readers(**kw))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-1958/plugins/superheroes/lib/review_record.py:906: in build_record
    findings = _apply_owner_rulings(findings, a["findings"], a["ownerRulings"])
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

findings = [{'id': 'f-1', 'title': 'Unchecked index', 'severity': 'Important', 'file': 'a.py', ...}, {'id': 'f-2', 'title': 'Unbo...y': 'Important', 'file': 'a.py', ...}, {'id': 'dup', 'title': 'Another', 'severity': 'Important', 'file': 'a.py', ...}]
raw = [{'id': 'f-1', 'title': 'Unchecked index', 'severity': 'Important', 'file': 'a.py', ...}, {'id': 'f-2', 'title': 'Unbo...y': 'Important', 'file': 'a.py', ...}, {'id': 'dup', 'title': 'Another', 'severity': 'Important', 'file': 'a.py', ...}]
entries = [{'key': 'nobody', 'url': 'https://github.com/o/r/issues/12#issuecomment-555', 'words': 'ship it as is'}]

    def _apply_owner_rulings(findings, raw, entries):
        """Set the owner-ruling citation as decidedBy on each ruling or left-for-owner finding an entry names.
        `raw` is the account's findings as given (an entry may key by the raw findingKey the stamping replaced);
        `findings` is the same list after the stamping. Every other outcome is left exactly as it is."""
        out = list(findings)
        for e in entries:
>           (j,) = _ruling_hits(raw, e["key"])
            ^^^^
E           ValueError: not enough values to unpack (expected 1, got 0)

/home/user/wt-1958/plugins/superheroes/lib/review_record.py:791: ValueError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_t5_a_malformed_entry_refuses_the_account[E9-names-no-finding]
1 failed in 0.55s
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

**restore** (the inverse replacement) and the restored lines quoted back:
```
        chk(len(hit) == 1, f"{where}.key names {'no finding' if not hit else 'more than one finding'}")
        chk(hit.isdisjoint(ruled)
```

**raw green** (exit code 0):
```
.                                                                        [100%]
1 passed in 0.44s
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

---

## V2: the no-two-entries-name-one-finding check in `_validate` (`review_record.py`), the second half of the one-finding rule

- **axis:** two entries for one finding are refused
- **file:** `plugins/superheroes/lib/review_record.py`
- **detector:** `plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_t5_a_malformed_entry_refuses_the_account[E11-two-entries-one-finding]`
- **sha256 before:** `5dcf5f07af548459f3f0c549c7f84805a58555d61e8232849743e88e1a42054e`
- **sha256 neutralized:** `2650bc9832e886c6a6444cea859dbc118e1d6fbf1865b0e9a4f5a8cc8ec14ccf`
- **sha256 after restore:** `5dcf5f07af548459f3f0c549c7f84805a58555d61e8232849743e88e1a42054e` (equals "before")

**neutralization** (one targeted replacement; the replaced text, then its replacement):
```
-         chk(hit.isdisjoint(ruled), f"{where}.key names a finding another entry names")
          ruled += hit
+         chk(True or hit.isdisjoint(ruled), f"{where}.key names a finding another entry names")
          ruled += hit
```

**raw red** (exit code 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_t5_a_malformed_entry_refuses_the_account[E11-two-entries-one-finding] __

rulings = [{'key': 'f-1', 'url': 'https://github.com/o/r/issues/12#issuecomment-555', 'words': 'ship it as is'}, {'key': 'rr1:71df46e158ff0278476bc8e3c9417b66', 'url': 'https://github.com/o/r/issues/12#issuecomment-555', 'words': 'ship it as is'}]
detail = 'ownerRulings[1].key names a finding another entry names'

    @pytest.mark.parametrize("rulings, detail", [
        pytest.param([entry(key="nobody")], "ownerRulings[0].key names no finding", id="E9-names-no-finding"),
        pytest.param([entry(key="dup")], "ownerRulings[0].key names more than one finding", id="E10-names-two-findings"),
        pytest.param([entry(), entry(key=rr._key(X))], "ownerRulings[1].key names a finding another entry names",
                     id="E11-two-entries-one-finding"),
        pytest.param([entry(url=3)], "ownerRulings[0].url", id="url-not-a-string"),
        pytest.param([entry(url="")], "ownerRulings[0].url", id="url-empty"),
        pytest.param([entry(url="  ")], "ownerRulings[0].url", id="url-blank"),
        pytest.param([entry(words=None)], "ownerRulings[0].words", id="words-not-a-string"),
        pytest.param([entry(words=" \n")], "ownerRulings[0].words", id="words-blank"),
        pytest.param([entry(key="")], "ownerRulings[0].key", id="key-empty"),
        pytest.param([entry(key=7)], "ownerRulings[0].key", id="key-not-a-string"),
        pytest.param(["f-1"], "ownerRulings[0]", id="entry-not-an-object"),
        pytest.param("f-1", "ownerRulings", id="not-a-list"),
    ])
    def test_t5_a_malformed_entry_refuses_the_account(rulings, detail):
        # Axis: every entry names exactly one finding, once, with a link and words; anything else is refused whole.
        findings = [X, Y, dict(Y, id="dup", title="Other", line=1), dict(Y, id="dup", title="Another", line=2)]
>       with pytest.raises(rr.Refusal) as refused:
             ^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE Refusal

/home/user/wt-1958/plugins/superheroes/lib/tests/test_review_record_owner_ruling.py:179: Failed
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_t5_a_malformed_entry_refuses_the_account[E11-two-entries-one-finding]
1 failed in 0.41s
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

**restore** (the inverse replacement) and the restored lines quoted back:
```
        chk(hit.isdisjoint(ruled), f"{where}.key names a finding another entry names")
        ruled += hit
```

**raw green** (exit code 0):
```
.                                                                        [100%]
1 passed in 0.48s
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

---

## M: the merged-member expansion `_owner_rulings` in `review_record_session.py`

- **axis:** a ruling on a merged group's representative covers its members
- **file:** `plugins/superheroes/lib/review_record_session.py`
- **detector:** `plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_t8_the_session_adapter_expands_a_ruling_on_a_merged_groups_representative_to_its_members`
- **sha256 before:** `a090305db4f326f5360299dd0db1947d9b47db34a484fee043a48de37ef74821`
- **sha256 neutralized:** `ba66d38e3c3c373d5ccd451ecdbf561fa7e5dfe8005ac62663ceaebf7b0836af`
- **sha256 after restore:** `a090305db4f326f5360299dd0db1947d9b47db34a484fee043a48de37ef74821` (equals "before")

**neutralization** (one targeted replacement; the replaced text, then its replacement):
```
-                 if row is rep or merged_into
+                 if True or merged_into
```

**raw red** (exit code 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t8_the_session_adapter_expands_a_ruling_on_a_merged_groups_representative_to_its_members _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-17/test_t8_the_session_adapter_ex0')

    def test_t8_the_session_adapter_expands_a_ruling_on_a_merged_groups_representative_to_its_members(tmp_path):
        # Axis: the owner rules on what the sheet showed (the representative), so its merged members fold with it.
        oos = {"disposition": "out-of-scope", "outOfScopeReason": "belongs to the follow-up"}
        ledger = _merged({}, oos) + [ledger_row("z::t@L9", id="z-1", disposition="out-of-scope", **{
            "outOfScopeReason": "unrelated"})]
        s = Session(tmp_path, dispositionLedger=ledger)
        s.seat("code-reviewer")
        session = s.save()
        given = [{"key": KEY, "url": U, "words": W}]
        account = rs.account_from_session(session, extras(repo="o/r", ownerRulings=given), Fake().readers())
>       assert account["ownerRulings"] == given + [{"key": "m::t@L1", "url": U, "words": W}]
E       AssertionError: assert [{'key': 'a.p...ip it as is'}] == [{'key': 'a.p...ip it as is'}]
E         
E         Right contains one more item: {'key': 'm::t@L1', 'url': 'https://github.com/o/r/issues/12#issuecomment-555', 'words': 'ship it as is'}
E         Use -v to get more diff

/home/user/wt-1958/plugins/superheroes/lib/tests/test_review_record_owner_ruling.py:214: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_t8_the_session_adapter_expands_a_ruling_on_a_merged_groups_representative_to_its_members
1 failed in 0.39s
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

**restore** (the inverse replacement) and the restored lines quoted back:
```
                if row is rep or merged_into
```

**raw green** (exit code 0):
```
.                                                                        [100%]
1 passed in 0.44s
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

---

## R: the failed-citation reason in `_recheck_decisions` (`review_record.py`)

- **axis:** a left-for-owner finding whose owner ruling does not resolve says why in its reason
- **file:** `plugins/superheroes/lib/review_record.py`
- **detector:** `plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_t2_no_pointer_no_fold_and_the_finding_stays_a_card[L5-words-absent]`
- **sha256 before:** `5dcf5f07af548459f3f0c549c7f84805a58555d61e8232849743e88e1a42054e`
- **sha256 neutralized:** `2c96d7627c49be1a68f23ff9dead126585bef4efa7922517a609036a847450cc`
- **sha256 after restore:** `5dcf5f07af548459f3f0c549c7f84805a58555d61e8232849743e88e1a42054e` (equals "before")

**neutralization** (one targeted replacement; the replaced text, then its replacement):
```
-                 unmet = f"the owner ruling it cites
+                 unmet = None  # NEUTRALIZED f"the owner ruling it cites
```

**raw red** (exit code 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_t2_no_pointer_no_fold_and_the_finding_stays_a_card[L5-words-absent] ___

over = {}
kw = {'doc': {'id': 555, 'issue_url': 'https://api.github.com/repos/o/r/issues/12', 'html_url': 'https://github.com/o/r/issues/12#issuecomment-555', 'author_association': 'OWNER', ...}}
why = "the ruling's comment does not hold the owner's words"

    @pytest.mark.parametrize("over, kw, why", FAILS)
    def test_t2_no_pointer_no_fold_and_the_finding_stays_a_card(over, kw, why):
        # Axis: fail closed, a left-for-owner finding stays one unless every leg of its pointer holds; it is never dropped.
        rec = build([entry(**over)], **kw)
        f = the_finding(rec)
        assert f["outcome"] == "left-for-owner" and rec["leftForOwner"] == ["f-1"] and rec["decisionRechecks"] == []
>       assert f["reason"] == "waits for the owner" + NOT_ON_RECORD % why
E       assert 'waits for the owner' == "waits for th...wner's words)"
E         
E         - waits for the owner; the owner ruling it cites is not on record (the ruling's comment does not hold the owner's words)
E         + waits for the owner

/home/user/wt-1958/plugins/superheroes/lib/tests/test_review_record_owner_ruling.py:115: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_t2_no_pointer_no_fold_and_the_finding_stays_a_card[L5-words-absent]
1 failed in 0.46s
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

**restore** (the inverse replacement) and the restored lines quoted back:
```
                unmet = f"the owner ruling it cites
```

**raw green** (exit code 0):
```
.                                                                        [100%]
1 passed in 0.45s
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

---

## Review round 1 fixes (WO-C)

**Provenance:** claude / sonnet-5.5 (implementer). Run from `/home/user/wt-1958`; each red and green is the detector node run alone (`scripts/pinned-python -B -m pytest "<node>" -q -p no:cacheprovider`). Each neutralization is one targeted edit made with the Edit tool and each restore is the inverse edit; no `git checkout`/`restore`/`stash`/`reset`. Captures are verbatim.

Three elements, three neutralizations, three reds, no grouping. The order declared no set beyond these three. V0 has two call sites (the representative lookup and the already-named check) that share one rule, `review_record._ruling_hits`; the neutralization is on the representative lookup and its node is the detector. The already-named half is guarded by `test_v0_a_member_an_entry_names_by_its_stored_key_is_not_named_twice`, which was not separately neutralized.

### WO-C-V0: the expansion matches an entry key as the writer does (raw findingKey, stored `rr1:` key or id)

- **file:** `plugins/superheroes/lib/review_record_session.py` (`_owner_rulings`)
- **detector:** `plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_v0_an_entry_keyed_by_the_representatives_stored_key_expands_to_its_member`
- **neutralization:** `for i in review_record._ruling_hits(findings, key):` replaced by `for i in [j for j, f in enumerate(findings) if key in (f.get("findingKey"), f["id"])]:` (the stored-key leg dropped)

**raw red** (exit code 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_v0_an_entry_keyed_by_the_representatives_stored_key_expands_to_its_member _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-24/test_v0_an_entry_keyed_by_the_0')

    def test_v0_an_entry_keyed_by_the_representatives_stored_key_expands_to_its_member(tmp_path):
        # Axis: the expansion finds the representative the way the writer does, by raw findingKey, stored key or id.
        session = _merged_session(tmp_path)
        base = rs.account_from_session(session, extras(repo="o/r"), Fake().readers())
        stored = rr._key(next(f for f in base["findings"] if f["id"] == "rep-1"))
        assert stored.startswith("rr1:")
        given = [{"key": stored, "url": U, "words": W}]
        account = rs.account_from_session(session, extras(repo="o/r", ownerRulings=given), Fake().readers())
>       assert account["ownerRulings"] == given + [{"key": "m::t@L1", "url": U, "words": W}]
E       AssertionError: assert [{'key': 'rr1...ip it as is'}] == [{'key': 'rr1...ip it as is'}]
E         
E         Right contains one more item: {'key': 'm::t@L1', 'url': 'https://github.com/o/r/issues/12#issuecomment-555', 'words': 'ship it as is'}
E         Use -v to get more diff

/home/user/wt-1958/plugins/superheroes/lib/tests/test_review_record_owner_ruling.py:251: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_v0_an_entry_keyed_by_the_representatives_stored_key_expands_to_its_member
1 failed in 1.90s
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

**restore** (the inverse replacement) and the restored line quoted back (`review_record_session.py:566`):
```
        for i in review_record._ruling_hits(findings, key):
```

**raw green** (exit code 0):
```
.                                                                        [100%]
1 passed in 2.03s
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

### WO-C-V1: membership is the ledger's resolved merge by identity key, never the reason text or a display id

- **file:** `plugins/superheroes/lib/review_record_session.py` (`_owner_rulings`)
- **detector:** `plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_v1_two_groups_whose_representatives_share_a_display_id_expand_separately`
- **neutralization:** `if row is rep or merged.get(row["findingKey"]) != rep["findingKey"]:` replaced by `if row is rep or merged_into(row.get("reason")) not in (rep.get("id"), rep.get("findingKey")):` (the old reason-text / id comparison)

**raw red** (exit code 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_v1_two_groups_whose_representatives_share_a_display_id_expand_separately _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-26/test_v1_two_groups_whose_repre0')

    def test_v1_two_groups_whose_representatives_share_a_display_id_expand_separately(tmp_path):
        # Axis: membership is the ledger's resolved merge by identity key, never the display id or the reason text.
        second = "r2::t@L5"
        oos = {"disposition": "out-of-scope", "outOfScopeReason": "belongs to the follow-up"}
        ledger = _merged({}, oos) + [ledger_row("m2::t@L6", id="m-2", disposition=None, mergedInto=second),
                                     ledger_row(second, id="rep-1", **oos)]
        s = Session(tmp_path, dispositionLedger=ledger)
        s.seat("code-reviewer")
        session = s.save()
        given = [{"key": KEY, "url": U, "words": W}]
        account = rs.account_from_session(session, extras(repo="o/r", ownerRulings=given), Fake().readers())
>       assert account["ownerRulings"] == given + [{"key": "m::t@L1", "url": U, "words": W}]
E       AssertionError: assert [{'key': 'a.p...ip it as is'}] == [{'key': 'a.p...ip it as is'}]
E         
E         Left contains one more item: {'key': 'm2::t@L6', 'url': 'https://github.com/o/r/issues/12#issuecomment-555', 'words': 'ship it as is'}
E         Use -v to get more diff

/home/user/wt-1958/plugins/superheroes/lib/tests/test_review_record_owner_ruling.py:289: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_v1_two_groups_whose_representatives_share_a_display_id_expand_separately
1 failed in 0.25s
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

**restore** (the inverse replacement) and the restored line quoted back (`review_record_session.py:570`):
```
                if row is rep or merged.get(row["findingKey"]) != rep["findingKey"]:
```

**raw green** (exit code 0):
```
.                                                                        [100%]
1 passed in 0.22s
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

### WO-C-V2: the words are compared against the de-quoted body as well as the raw body

- **file:** `plugins/superheroes/lib/finding_outcomes.py` (`_owner_ruling_on_record`, leg L5)
- **detector:** `plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_v2_the_standard_record_of_multiline_words_holds_the_words`
- **neutralization:** `for b in (body, re.sub(r"(?m)^[ \t]*>[ \t]?", "", body)))):` replaced by `for b in (body,))):` (raw body only)

**raw red** (exit code 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_v2_the_standard_record_of_multiline_words_holds_the_words ________

    def test_v2_the_standard_record_of_multiline_words_holds_the_words():
        # Axis: the chat-ruling record quotes each line behind a marker; the words still occur in it.
        words = "ship it\nas is"
        doc = dict(DOC, body=canon.ruling_record("2026-10-18", "12:00", words, "finding f-1"))
        rec = build([entry(words=words)], doc=doc)
>       assert the_finding(rec)["outcome"] == "ruling" and rec["leftForOwner"] == []
E       AssertionError: assert ('left-for-owner' == 'ruling'
E         
E         - ruling
E         + left-for-owner)

/home/user/wt-1958/plugins/superheroes/lib/tests/test_review_record_owner_ruling.py:313: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_v2_the_standard_record_of_multiline_words_holds_the_words
1 failed in 0.31s
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

**restore** (the inverse replacement) and the restored line quoted back (`finding_outcomes.py:196`):
```
    if not (isinstance(body, str) and any(_squash(words) in _squash(b) for b in (body, re.sub(r"(?m)^[ \t]*>[ \t]?", "", body)))):
```

**raw green** (exit code 0):
```
.                                                                        [100%]
1 passed in 0.18s
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

## Review session 2 fixes (WO-E)

### CE: the carried expansion `_carried_rulings` call in `write_from_session` (`review_record_session.py`)

- **file:** `plugins/superheroes/lib/review_record_session.py` (`write_from_session`)
- **axis:** a ruling on a representative covers the members carried from the earlier record, not only the current session's
- **detector:** `plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_wo_e_a_ruling_on_a_carried_representative_covers_its_carried_members`
- **neutralization:** `account["ownerRulings"] = _carried_rulings(account["ownerRulings"], account["findings"], carried)` replaced by `account["ownerRulings"] = account["ownerRulings"]`

**raw red** (exit code 1, the failure block as the run printed it):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_wo_e_a_ruling_on_a_carried_representative_covers_its_carried_members ___

    def test_wo_e_a_ruling_on_a_carried_representative_covers_its_carried_members(tmp_path):
        # Axis: the owner rules on the representative the sheet showed, so a member carried with it folds too.
        fake = Fake()
        before = {f["id"]: f for f in _earlier_merged_record(tmp_path, fake)}
        assert before["m-1"]["reason"].endswith(" (merged into rep-1)") and before["m-1"]["outcome"] == "left-for-owner"
        rec = _later_write(tmp_path, fake, before["rep-1"]["findingKey"])
>       assert {f["id"]: f["outcome"] for f in rec["findings"]} == {"m-1": "ruling", "rep-1": "ruling"}
E       AssertionError: assert {'m-1': 'left...-1': 'ruling'} == {'m-1': 'ruli...-1': 'ruling'}
E         
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'m-1': 'left-for-owner'} != {'m-1': 'ruling'}
E         Use -v to get more diff

=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_wo_e_a_ruling_on_a_carried_representative_covers_its_carried_members
1 failed in 0.79s
```

**restore** (the inverse replacement) and the restored line quoted back (`review_record_session.py:646`):
```
        account["ownerRulings"] = _carried_rulings(account["ownerRulings"], account["findings"], carried)
```

**raw green** (exit code 0):
```
.                                                                        [100%]
1 passed in 1.45s
```

### CU: the unique-id check in `_carried_rulings` (`review_record_session.py`)

- **file:** `plugins/superheroes/lib/review_record_session.py` (`_carried_rulings`)
- **axis:** E1, a carried member is covered only when the id its mark names is one row's, so an id two rows share expands nothing
- **detector:** `plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_wo_e_a_mark_naming_an_id_two_rows_share_adds_no_entry`
- **neutralization:** ` or mark != rep["id"] or sum(f["id"] == mark for f in findings) != 1:` replaced by ` or mark != rep["id"]:` (the uniqueness clause removed)

**raw red** (exit code 1, the failure block as the run printed it):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_wo_e_a_mark_naming_an_id_two_rows_share_adds_no_entry __________

    def test_wo_e_a_mark_naming_an_id_two_rows_share_adds_no_entry(tmp_path):
        # Axis: E1, fail closed; an id that names two rows cannot tell which representative the mark means.
        oos = {"disposition": "out-of-scope", "outOfScopeReason": "belongs to the follow-up"}
        fake = Fake()
        before = _earlier_merged_record(tmp_path, fake, [ledger_row("other::t@L5", id="rep-1", line=5, **oos)])
        assert sorted(f["line"] for f in before if f["id"] == "rep-1") == [3, 5]
        rep = next(f for f in before if f["id"] == "rep-1" and f["line"] == 3)
        rec = _later_write(tmp_path, fake, rep["findingKey"])
>       assert {f["outcome"] for f in rec["findings"] if f["id"] == "m-1"} == {"left-for-owner"}
E       AssertionError: assert {'ruling'} == {'left-for-owner'}
E         
E         Extra items in the left set:
E         'ruling'
E         Extra items in the right set:
E         'left-for-owner'
E         Use -v to get more diff

=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_wo_e_a_mark_naming_an_id_two_rows_share_adds_no_entry
1 failed in 0.31s
```

**restore** (the inverse replacement) and the restored line quoted back (`review_record_session.py:600`):
```
                if row is rep or mark is None or mark != rep["id"] or sum(f["id"] == mark for f in findings) != 1:
```

**raw green** (exit code 0):
```
.                                                                        [100%]
1 passed in 0.36s
```

## Review session 2 round 2 fix (WO-F)

### MA: the mark-anywhere test in `_carried_rulings` (`review_record_session.py`)

- **file:** `plugins/superheroes/lib/review_record_session.py` (`_carried_rulings`)
- **axis:** a carried member is found by the exact merge mark wherever it sits in its reason, so a suffix `_recheck_decisions` appended after the mark does not hide the member
- **detector:** `plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_wo_f_a_mark_followed_by_a_later_suffix_still_makes_the_carried_row_a_member`
- **neutralization:** the containment test (`reason = row.get("reason")`, its comment, and the four-line `if` that tests `MERGED_INTO_FORMAT.format(rep["id"]) not in reason`) replaced by the two earlier lines `mark = merged_into(row.get("reason"))` and `if row is rep or mark is None or mark != rep["id"] or sum(f["id"] == mark for f in findings) != 1:`

**raw red** (exit code 1, the failure block as the run printed it):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_wo_f_a_mark_followed_by_a_later_suffix_still_makes_the_carried_row_a_member _

    def test_wo_f_a_mark_followed_by_a_later_suffix_still_makes_the_carried_row_a_member():
        # Axis: the mark can sit before text `_recheck_decisions` appends, so membership is containment, not the end of the reason.
        reason = "waits for the owner (merged into rep-1); the owner ruling it cites is not on record (the link is gone)" + rs.CARRIED
>       assert _carried_out(reason) == ["k-rep", "k-m"]
E       AssertionError: assert ['k-rep'] == ['k-rep', 'k-m']
E         
E         Right contains one more item: 'k-m'
E         Use -v to get more diff

/home/user/wt-1958/plugins/superheroes/lib/tests/test_review_record_owner_ruling.py:434: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_owner_ruling.py::test_wo_f_a_mark_followed_by_a_later_suffix_still_makes_the_carried_row_a_member
1 failed in 0.45s
```

**restore** (the inverse replacement) and the restored lines quoted back (`review_record_session.py:599-604`):
```
                reason = row.get("reason")
                # the exact mark includes the closing parenthesis, so rep-1 never matches rep-10; it may sit before a later suffix
                if row is rep or not isinstance(reason, str) or not isinstance(rep["id"], str) \
                        or MERGED_INTO_FORMAT.format(rep["id"]) not in reason \
                        or sum(f["id"] == rep["id"] for f in findings) != 1:
                    continue
```

**raw green** (exit code 0):
```
.                                                                        [100%]
1 passed in 1.96s
```
