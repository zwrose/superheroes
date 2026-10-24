# Credential-text rule bite-proof — `test_seat_rule_2071.py`

**Provenance:** run by the build orchestrator in its own shell, in a detached probe worktree at the
build head. The implementer's write sandbox could not run it: one dispatch found pytest
unresolvable offline (`No solution found when resolving`), and the next stopped on an existing
`test_engine_dispatch.py` failure that passes outside the sandbox.

Declared guarded-element set (from the order): E1 the append of `CREDENTIAL_TEXT_RULE` to
`ANTIHIJACK_PREAMBLE` in `lib/engine_dispatch.py`. Each run:
`scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest <node> -q -p no:cacheprovider`, the
detector unedited. The neutralization was one targeted edit; the restore was the inverse edit. The
`UV_NATIVE_TLS` warning line `uv` prints before each run is dropped from the captures, and the
long preamble and rule strings in the assertion message are shown as pytest abbreviated them. No
redaction was applied.

## Summary

| Element | Axis | Proving test | Verdict |
|---|---|---|---|
| E1 the rule's append to the preamble | every engine review dispatch is told credential-like text is redacted | `test_dispatch_preamble_carries_the_credential_text_rule_once` | proven |

---

## E1 — the append of `CREDENTIAL_TEXT_RULE` to `ANTIHIJACK_PREAMBLE`

**guarded element:** `lib/engine_dispatch.py`, the line `+ " " + CREDENTIAL_TEXT_RULE` inside
`ANTIHIJACK_PREAMBLE`. **axis:** the preamble every engine review dispatch is fed carries the
credential-text rule exactly once, after the review seat rule.

**neutralization:** the line `    + " " + CREDENTIAL_TEXT_RULE` was removed, so the preamble read
`+ round_orders.REVIEW_SEAT_RULE` then `+ " Respond with your review ONLY.\n\n"`.

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_dispatch_preamble_carries_the_credential_text_rule_once _________

    def test_dispatch_preamble_carries_the_credential_text_rule_once():
        import engine_dispatch as ED
>       assert ED.ANTIHIJACK_PREAMBLE.count(ED.CREDENTIAL_TEXT_RULE) == 1
E       assert 0 == 1
E        +  where 0 = <built-in method count of str object at 0x2eaa9100>('Credential-like text (API keys, tokens, private keys) can be redacted in transit: a cloud session replaces it before ...test you write, build such a value at runtime from pieces (for example "sk-" + "a" * 48) rather than writing it whole.')

/home/user/wt-2121-probe/plugins/superheroes/lib/tests/test_seat_rule_2071.py:167: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_rule_2071.py::test_dispatch_preamble_carries_the_credential_text_rule_once
1 failed in 0.47s
```
(Three further `where` lines of the assertion message, which repeat the abbreviated preamble and
rule strings, are elided.)

**restore:** the inverse edit put the line back. Restored lines:
```
    + round_orders.REVIEW_SEAT_RULE
    + " " + CREDENTIAL_TEXT_RULE
    + " Respond with your review ONLY.\n\n"
```

**restore receipt:** `git status --porcelain` in the probe worktree after the restore printed nothing.

**raw green:**
```
.                                                                        [100%]
1 passed in 0.58s
```
