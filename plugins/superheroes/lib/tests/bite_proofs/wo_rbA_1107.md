# WO-rbA (#1107) bite-proofs — one owner for review-session mode in `round_driver.py`

Both elements were neutralized together and proved in a single combined red/green
pytest invocation (two separate targeted edits, one per element; the combined diff at
capture time is quoted per element below).

## BP-rbA1 — mode-owner routing (`_resolve_prior_comments_path`)

**Guarded element:** `round_driver._resolve_prior_comments_path` (`plugins/superheroes/lib/round_driver.py`)
— axis: the function must route mode resolution through `session_mode.resolve`, the sole owner of
PR-vs-branch, not re-derive it.

**Neutralization:** replaced the routing line

```python
    mode_resolved = session_mode.resolve(meta, cfg)
```

with a hardcoded value that makes the resolved mode ignore `session_mode` entirely:

```python
    mode_resolved = {"mode": session_mode.MODE_BRANCH}  # BITE-PROOF-NEUTRALIZE-1107-rbA
```

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-rba -m pytest plugins/superheroes/lib/tests/test_prior_comments_mode.py::test_prior_comments_pr_mode_without_repo_checkout_discloses plugins/superheroes/lib/tests/test_order_input_contract.py::test_order_placeholder_registry_partition_is_complete -q
```
(run jointly with BP-rbA2's neutralization also applied — see BP-rbA2 for its own red line in
this same run)

**Red run (element 1's failure, `test_prior_comments_mode.py`; the joint run's element-2 failure
is the same run and is quoted under BP-rbA2):**
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_________ test_prior_comments_pr_mode_without_repo_checkout_discloses __________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-10570/test_prior_comments_pr_mode_wi0')

    def test_prior_comments_pr_mode_without_repo_checkout_discloses(tmp_path):
        # axis: PR mode must disclose when prior-comments.json is absent — no repo/ required
        session_dir = _session_with_mode(tmp_path, "pr")
        assert not os.path.isdir(os.path.join(session_dir, "repo"))
        state = RD.new_state(_cfg(tmp_path))
        path = RD._resolve_prior_comments_path(session_dir, state)
>       assert path.startswith("(")
E       AssertionError: assert False
E        +  where False = <built-in method startswith of str object at 0x105284670>('(')
E        +    where <built-in method startswith of str object at 0x105284670> = ''.startswith

plugins/superheroes/lib/tests/test_prior_comments_mode.py:33: AssertionError
```

**Restore:** reverted the neutralized line back to the routing call (inverse of neutralization).

**Restore receipt:** quoted restored line:
```python
    mode_resolved = session_mode.resolve(meta, cfg)
```
Post-restore `git status --porcelain` over the neutralized path showed the file with only the
order's real (non-neutralization) diff remaining — see the combined `git diff --stat` in the
implementer report.

**Green run:** see BP-rbA2's joint green run below (`2 passed in 0.74s`), which covers both
elements restored simultaneously.

---

## BP-rbA2 — `MODE_EVIDENCE` registry membership

**Guarded element:** `round_driver.ORDER_DERIVED_PLACEHOLDERS` (`plugins/superheroes/lib/round_driver.py:5339`)
— axis: every placeholder key `_order_placeholder_keys` emits for a phase must be covered by
exactly one registry set (`_placeholder_partition` completeness).

**Neutralization:** removed `"MODE_EVIDENCE"` from the `ORDER_DERIVED_PLACEHOLDERS` frozenset
literal (targeted, reversible single-line removal).

**Command:** same joint invocation as BP-rbA1 above.

**Red run:**
```
____________ test_order_placeholder_registry_partition_is_complete _____________

    def test_order_placeholder_registry_partition_is_complete():
        ...
        missing = []
        for phase in RO.ORDER_PHASES:
            names = _template_placeholders(phase) | _order_placeholder_keys(
                phase, session_dir, state, payloads[phase], seat_keys[phase])
            for name in sorted(names):
                if name not in partition:
                    missing.append("%s:%s" % (phase, name))
>       assert not missing, "placeholders outside registry partition:\n" + "\n".join(missing)
E       AssertionError: placeholders outside registry partition:
E         dispatch-panel:MODE_EVIDENCE
E       assert not ['dispatch-panel:MODE_EVIDENCE']

plugins/superheroes/lib/tests/test_order_input_contract.py:274: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_prior_comments_mode.py::test_prior_comments_pr_mode_without_repo_checkout_discloses
FAILED plugins/superheroes/lib/tests/test_order_input_contract.py::test_order_placeholder_registry_partition_is_complete
2 failed in 1.01s
```

**Restore:** re-added `"MODE_EVIDENCE"` to `ORDER_DERIVED_PLACEHOLDERS` (inverse of neutralization).

**Restore receipt:** quoted restored lines:
```python
    "FOCUS_CONTEXT_LINE",
    "MODE",
    "MODE_EVIDENCE",
    "REPO",
```
Post-restore `git status --porcelain` over `plugins/superheroes/lib/round_driver.py` showed only
the order's real (non-neutralization) diff — both bite-proof edits fully reverted, confirmed by
diffing against the pre-neutralization commit state before the neutralization/restore cycle began.

**Green run (joint, both elements restored):**
```
..                                                                       [100%]
2 passed in 0.74s
```
