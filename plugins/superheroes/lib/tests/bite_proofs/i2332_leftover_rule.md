# I2332 leftover-rule bite-proof record

Invariant (#2332, gaps 2 and 3): a leftover is named by an acceptance that carries its record id as a whole
token (case, Unicode form and dash aside) and its title by words (case, quotes, apostrophes and punctuation
aside); two ids sharing a normal form are matched byte for byte; and a `fixed-above #<PR> <commit>`
acceptance passes only when that PR is a higher member of this PR's own stack, refusing
`fixed-above-not-in-stack` or `fixed-above-unverified` otherwise.

Guarded-element set (declared by order B): B1–B5 below, in `plugins/superheroes/lib/leftover_accepting.py`
and `plugins/superheroes/lib/vet_slot.py`. Each node was run alone as
`scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/pyc-2332B -m pytest "<node>" -q -p no:cacheprovider`
with the detector unedited, after the changes of order B2 (the `SIXTEEN_TOKENS` pin, the non-dict read
folding to `fixed-above-unverified`, the apostrophe drop) were in place. Every capture is the full output of
that command; each begins with the harness warning line (`UV_NATIVE_TLS`), which is not part of the test.
Nothing is redacted (no secrets, tokens or private URLs appear). Every restore was the inverse edit (no
`git checkout`/`restore`/`reset`/`stash`), and the restored lines were read back from the file.

---

## B1 — whole-token id equality (`_id_named`)

**Guarded element:** `leftover_accepting.py:153` `return any(have[i:i + n] == want for i in range(len(have) - n + 1))`.
**Axis:** an id is named only as a consecutive run of whole tokens, so `f-1` is never inside `f-1-b`.

**Neutralization:** the line became `return " ".join(want) in " ".join(have)` (a substring check on the joined
normalised token strings).

**Red run** (`test_g2b_distinct_ids_with_one_title_are_not_satisfied_by_one_acceptance[ids1]`):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_g2b_distinct_ids_with_one_title_are_not_satisfied_by_one_acceptance[ids1] _

ids = ('f-1', 'f-1-b')

    @pytest.mark.parametrize("ids", [("F/1", "F.1.2"), ("f-1", "f-1-b")])
    def test_g2b_distinct_ids_with_one_title_are_not_satisfied_by_one_acceptance(ids):
        first, second = ids
        record = rec((first, "same title here"), (second, "same title here"))
>       assert gaps(record, "- %s same title here: accepted.\n" % second) == [first]
E       AssertionError: assert [] == ['f-1']
E         
E         Right contains one more item: 'f-1'
E         Use -v to get more diff

/home/user/wt-2332-B/plugins/superheroes/lib/tests/test_leftover_rule_2332.py:59: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_leftover_rule_2332.py::test_g2b_distinct_ids_with_one_title_are_not_satisfied_by_one_acceptance[ids1]
1 failed in 0.61s
```
Axis check: the red is `f-1` reported as named (gaps `[]`) by an acceptance that writes only `f-1-b`.

**Restore:** inverse edit, the substring line → the `any(have[i:i + n] == want ...)` line.
**Restore receipt:** read back from the file (`leftover_accepting.py:153`):
```
    return any(have[i:i + n] == want for i in range(len(have) - n + 1))
```

**Green run:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.45s
```

---

## B2 — the collision fallback (`missing`)

**Guarded element:** `leftover_accepting.py:192` `_names(item, ident, title, exact=ident in colliding)` in `missing`.
**Axis:** two ids of one record that share a normal form are each matched byte for byte, so neither satisfies the other.

**Neutralization:** `exact=ident in colliding` → `exact=False` in `missing` (so `missing` never passes
`exact=True`). The twin call in `fixed_above` (line 213) was left as it was.

**Red run** (`test_g2c_ids_sharing_a_normal_form_are_matched_byte_for_byte`):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_g2c_ids_sharing_a_normal_form_are_matched_byte_for_byte __________

    def test_g2c_ids_sharing_a_normal_form_are_matched_byte_for_byte():
        record = rec(("F-1", "same title here"), ("f-1", "same title here"))
>       assert gaps(record, "- F-1 same title here: accepted.\n") == ["f-1"]
E       AssertionError: assert [] == ['f-1']
E         
E         Right contains one more item: 'f-1'
E         Use -v to get more diff

/home/user/wt-2332-B/plugins/superheroes/lib/tests/test_leftover_rule_2332.py:64: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_leftover_rule_2332.py::test_g2c_ids_sharing_a_normal_form_are_matched_byte_for_byte
1 failed in 0.50s
```
Axis check: the red is `f-1` reported as named by an acceptance that writes only `F-1`.

**Restore:** inverse edit, `exact=False` → `exact=ident in colliding`.
**Restore receipt:** read back from the file (`leftover_accepting.py:192` and `:213`, the two `exact=` uses):
```
            if not any(_names(item, ident, title, exact=ident in colliding) for item in items)]
            if found and _names(item, ident, title, exact=ident in colliding):
```

**Green run:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.42s
```

---

## B3 — the title normalisation (`_title_key`)

**Guarded element:** `leftover_accepting.py:134` `_title_key` (NFKC, case-fold, dashes, quotes and apostrophes dropped,
non-word runs to one space).
**Axis:** a title is compared by its words, so a quoted title and a cased id are named by an acceptance that writes them plainly.

**Neutralization:** `return text` inserted as the first line of the function body (the input returned unchanged).

**Red run** (`test_g2a_the_field_case_a_quoted_title_and_a_cased_id_are_named`):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_g2a_the_field_case_a_quoted_title_and_a_cased_id_are_named ________

    def test_g2a_the_field_case_a_quoted_title_and_a_cased_id_are_named():
        record = rec(("f-1", 'the "retry" loop never backs off.'))
        accepting = "- F-1 — the retry loop never backs off: merging accepts slower recovery.\n"
>       assert gaps(record, accepting) == []
E       AssertionError: assert ['f-1'] == []
E         
E         Left contains one more item: 'f-1'
E         Use -v to get more diff

/home/user/wt-2332-B/plugins/superheroes/lib/tests/test_leftover_rule_2332.py:28: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_leftover_rule_2332.py::test_g2a_the_field_case_a_quoted_title_and_a_cased_id_are_named
1 failed in 0.34s
```
Axis check: the red is `f-1` reported missing for the field case (a quoted title, written plainly in the acceptance).

**Restore:** inverse edit, the inserted `return text` line removed.
**Restore receipt:** read back from the file (`leftover_accepting.py:138-139`):
```
    folded = _DASHES.sub("-", unicodedata.normalize("NFKC", text).casefold())
    return re.sub(r"[^\w]+", " ", folded.translate(_QUOTES)).strip()
```

**Green run:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.33s
```
Disclosure about this green: the restore edit first left line 138 as `folded =_DASHES.sub(...)` (one space
missing, same meaning), and a first green run (also `1 passed in 0.33s`) was taken with that. The space was
put back, the lines read back as quoted above, and the green shown is the second run, taken on the
corrected file.

---

## B4 — the combined failing-claim condition (`_check_fixed_above`)

**Guarded element:** `vet_slot.py:471` `if not (isinstance(layer, int) and not isinstance(layer, bool) and layer > mine):`.
**Axis:** a named layer that is not a member of this PR's stack, or sits at or below it, fails the claim. Membership
and position are tested in this one combined condition (one statement), so one neutralization covers both.

**Neutralization:** `if not (...)` → `if False and not (...)` (no claim ever fails).

**Red run** (`test_g3b_a_named_pr_that_is_not_in_the_stack_is_refused_by_both_callers`):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_g3b_a_named_pr_that_is_not_in_the_stack_is_refused_by_both_callers ____

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fa49dadcf80>
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-16/test_g3b_a_named_pr_that_is_no0')

    def test_g3b_a_named_pr_that_is_not_in_the_stack_is_refused_by_both_callers(monkeypatch, tmp_path):
        use(monkeypatch, Membership(stack(PR, 43)))
        result = handback(body(named(99)), COMMENTS)
>       assert result["ok"] is False and result["reason"] == "fixed-above-not-in-stack"
E       assert (True is False)

/home/user/wt-2332-B/plugins/superheroes/lib/tests/test_leftover_rule_2332.py:203: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_leftover_rule_2332.py::test_g3b_a_named_pr_that_is_not_in_the_stack_is_refused_by_both_callers
1 failed in 0.33s
```
Axis check: the red is the handback passing (`ok` True) for a layer (#99) that is in no member list of the stack.

**Restore:** inverse edit, `if False and not (...)` → `if not (...)`.
**Restore receipt:** read back from the file (`vet_slot.py:471`):
```
        if not (isinstance(layer, int) and not isinstance(layer, bool) and layer > mine):
```

**Green run:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 4.87s
```

---

## B5 — the unreadable-membership refusal (`_check_fixed_above`)

**Guarded element:** `vet_slot.py:455-458` the `raise _Refusal("fixed-above-unverified", ...)` under
`if not isinstance(read, dict) or read.get("ok") is not True:`.
**Axis:** a membership read that is not an object or did not succeed (and is not `not-linked`) refuses
`fixed-above-unverified`, never passes. (Order B's planning note: disabling only the `if` would fall through to the
later position guard and stay green, so the `raise` itself is replaced.)

**Neutralization:** the two-line `raise _Refusal("fixed-above-unverified", "%s: the stack membership of PR %d could not be read (%s); the" " disposition is not accepted" % (...))` was replaced with `return`.

**Red run** (`test_g3d_a_membership_read_that_does_not_place_this_pr_is_refused[read2-fixed-above-unverified]`, the `stack-unreadable` parameter):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_g3d_a_membership_read_that_does_not_place_this_pr_is_refused[read2-fixed-above-unverified] _

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f35560dce90>
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-18/test_g3d_a_membership_read_tha0')
read = {'ok': False, 'reason': 'stack-unreadable', 'detail': 'gh failed'}
reason = 'fixed-above-unverified'

    @pytest.mark.parametrize("read, reason", [
        ({"ok": False, "reason": "not-linked", "detail": "PR is in no stack"}, "fixed-above-not-in-stack"),
        ("not a dict", "fixed-above-unverified"),  # membership is unknown, not "in no stack"
        ({"ok": False, "reason": "stack-unreadable", "detail": "gh failed"}, "fixed-above-unverified"),
        (stack(41, 43), "fixed-above-unverified"),  # this PR is absent from the members
        ({"ok": True, "members": "x"}, "fixed-above-unverified"),
        ({"ok": True}, "fixed-above-unverified"),
    ])
    def test_g3d_a_membership_read_that_does_not_place_this_pr_is_refused(monkeypatch, tmp_path, read, reason):
        use(monkeypatch, Membership(read))
        result = handback(body(named(43)), COMMENTS)
>       assert result["ok"] is False and result["reason"] == reason and "f-2" in result["detail"]
E       assert (True is False)

/home/user/wt-2332-B/plugins/superheroes/lib/tests/test_leftover_rule_2332.py:242: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_leftover_rule_2332.py::test_g3d_a_membership_read_that_does_not_place_this_pr_is_refused[read2-fixed-above-unverified]
1 failed in 0.35s
```
Axis check: the red is the handback passing (`ok` True) over a membership read that failed (`stack-unreadable`).

**Restore:** inverse edit, `return` → the two-line `raise _Refusal("fixed-above-unverified", ...)`.
**Restore receipt:** read back from the file (`vet_slot.py:454-458`):
```
    # axis: a read that is not an object (membership unknown) or did not succeed refuses fixed-above-unverified, never passes
    if not isinstance(read, dict) or read.get("ok") is not True:
        cause = ("%s: %s" % (reason, read.get("detail"))) if isinstance(read, dict) else "the read was not an object"
        raise _Refusal("fixed-above-unverified", "%s: the stack membership of PR %d could not be read (%s); the"
                       " disposition is not accepted" % ("; ".join(_claim_name(c) for c in claims), pr, cause))
```

**Green run:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.33s
```
