# C1-L11 (WO-C) bite-proof — a stacked layer is reviewed on its lower layer's current head

**Provenance:** implementer WO-C / `lib/review_base_guard.py` (`check_stack_lower`), `lib/round_driver.py` (`_dispatch`, `_refuse_stack_lower`), `lib/tests/test_stack_lower_c1l11.py`

Declared guarded elements (from the order): E1 the remote-head-equals-pin check; E2 the pin-is-an-ancestor-of-HEAD check; E3 the unreadable refusal; E4 the `_dispatch` call for `next`; E5 the `_dispatch` call for `submit`; E6 the `_dispatch` call for `advance`. Each was neutralized with one targeted edit and restored with the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2215-c` under `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider`. The captures are the runner's whole output for each run apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out; nothing is redacted (no secrets, tokens or URLs appear; temp paths are pytest's).

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| E1 | `review_base_guard.py` `check_stack_lower`, the `remote_head != pin` test | a lower branch whose remote head is not the pin refuses `stack-lower-moved` | `test_moved_lower_before_the_session_refuses_moved` |
| E2 | `review_base_guard.py` `check_stack_lower`, the `merge-base --is-ancestor` test | a pin that is not in HEAD's history refuses `stack-lower-ahead` | `test_pin_the_layer_does_not_contain_refuses_ahead_until_merged` |
| E3 | `review_base_guard.py` `check_stack_lower`, the `ls_remote(...)` read feeding the unreadable refusal | an unreadable remote head refuses `stack-lower-unreadable`, even when a cached pin is an ancestor of HEAD | `test_unreadable_remote_refuses_even_with_a_stale_pin_that_is_an_ancestor` |
| E4 | `round_driver.py` `_dispatch`, `next` branch: the `check_stack_lower` call | `next` on a started session refuses when the lower layer moved | `test_cli_next_refuses_when_lower_moves_during_the_session` |
| E5 | `round_driver.py` `_dispatch`, `submit` branch: the `_refuse_stack_lower` call | `submit` refuses when the lower layer moved | `test_cli_submit_refuses_when_lower_moves_during_the_session` |
| E6 | `round_driver.py` `_dispatch`, `advance` branch: the `_refuse_stack_lower` call | `advance` refuses when the lower layer moved | `test_cli_advance_refuses_when_lower_moves_during_the_session` |

Unproven parts of the file (no separate neutralization): the `stackLower`-absent/false no-check path, the invalid-branch-name and non-boolean-flag refusals, the unreadable-meta refusal, the missing-`origin` leg of E3 (the E3 neutralization is red on the first loop value, `None`, so the `""`, short and non-hex answers and the real unreachable-origin case are not separately shown red), the `ls-remote` parsing in `_ls_remote_head`, the Setup-shell and prose tests.

---

## E1 — remote head equals the pin

**axis:** the lower branch's remote head must equal the session's pin.

**neutralization** (`review_base_guard.py`, `check_stack_lower`):
```python
-    if remote_head != pin:
+    if remote_head != remote_head:  # BITE-PROOF NEUTRALIZATION (E1)
```

**raw red:** `... pytest ... "plugins/superheroes/lib/tests/test_stack_lower_c1l11.py::test_moved_lower_before_the_session_refuses_moved"`
```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_moved_lower_before_the_session_refuses_moved _______________

stack = <test_stack_lower_c1l11.Stack object at 0x7f4a93d25430>

    def test_moved_lower_before_the_session_refuses_moved(stack):
        # axis: remote head != pin refuses stack-lower-moved and names both shas
        new_head = stack.push_lower()
        res = G.check_stack_lower(stack.session(), stack.repo)
>       assert res["ok"] is False and res["reason"] == "stack-lower-moved" == G.REASON_STACK_LOWER_MOVED
E       assert (True is False)

/home/user/wt-2215-c/plugins/superheroes/lib/tests/test_stack_lower_c1l11.py:142: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_lower_c1l11.py::test_moved_lower_before_the_session_refuses_moved
1 failed in 2.37s
```

**restore:** the inverse edit (`remote_head != remote_head:  # BITE-PROOF NEUTRALIZATION (E1)` back to `remote_head != pin:`).

**restore receipt:** a search of `review_base_guard.py` and `round_driver.py` for `BITE-PROOF` finds nothing, and the line reads `review_base_guard.py:444:    if remote_head != pin:`.

**raw green:** same command
```
.                                                                        [100%]
1 passed in 0.49s
```

---

## E2 — the pin is in HEAD's history

**axis:** a pin that is not an ancestor of HEAD refuses `stack-lower-ahead`.

**neutralization** (`review_base_guard.py`, `check_stack_lower`):
```python
-    if _run_git_bytes(repo_root, "merge-base", "--is-ancestor", pin, "HEAD") is None:
+    if _run_git_bytes(repo_root, "merge-base", "--is-ancestor", pin, "HEAD") is Ellipsis:  # BITE-PROOF NEUTRALIZATION (E2)
```

**raw red:** `... pytest ... "plugins/superheroes/lib/tests/test_stack_lower_c1l11.py::test_pin_the_layer_does_not_contain_refuses_ahead_until_merged"`
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_pin_the_layer_does_not_contain_refuses_ahead_until_merged ________

stack = <test_stack_lower_c1l11.Stack object at 0x7f7e5bbca090>

    def test_pin_the_layer_does_not_contain_refuses_ahead_until_merged(stack):
        # axis: pin == remote head but not in HEAD's history refuses stack-lower-ahead; a --no-ff merge clears it
        new_head = stack.push_lower()
        _git(stack.repo, "fetch", "-q", "origin", "lower")
        sd = stack.session(pin=new_head)
        res = G.check_stack_lower(sd, stack.repo)
>       assert res["ok"] is False and res["reason"] == "stack-lower-ahead" == G.REASON_STACK_LOWER_AHEAD
E       assert (True is False)

/home/user/wt-2215-c/plugins/superheroes/lib/tests/test_stack_lower_c1l11.py:153: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_lower_c1l11.py::test_pin_the_layer_does_not_contain_refuses_ahead_until_merged
1 failed in 0.33s
```

**restore:** the inverse edit (`is Ellipsis:  # BITE-PROOF NEUTRALIZATION (E2)` back to `is None:`).

**restore receipt:** no `BITE-PROOF` text remains in either file, and the line reads `review_base_guard.py:454:    if _run_git_bytes(repo_root, "merge-base", "--is-ancestor", pin, "HEAD") is None:`.

**raw green:** same command
```
.                                                                        [100%]
1 passed in 0.33s
```

---

## E3 — an unreadable remote head refuses

**axis:** when the remote head cannot be read the call refuses `stack-lower-unreadable`; the cached pin is never a substitute.

**neutralization** (`review_base_guard.py`, `check_stack_lower`: an unreadable head falls back to the cached pin):
```python
-    remote_head = ls_remote(repo_root, branch)
+    remote_head = ls_remote(repo_root, branch) or pin  # BITE-PROOF NEUTRALIZATION (E3)
```

**raw red:** `... pytest ... "plugins/superheroes/lib/tests/test_stack_lower_c1l11.py::test_unreadable_remote_refuses_even_with_a_stale_pin_that_is_an_ancestor"`
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_unreadable_remote_refuses_even_with_a_stale_pin_that_is_an_ancestor ___

stack = <test_stack_lower_c1l11.Stack object at 0x7f8f8532a270>

    def test_unreadable_remote_refuses_even_with_a_stale_pin_that_is_an_ancestor(stack):
        # axis: an unreadable remote head refuses; a cached pin in HEAD's history is not a substitute
        sd = stack.session()
        assert _git(stack.repo, "merge-base", "--is-ancestor", stack.pin, "HEAD") == ""
        for answer in (None, "", "abc123", "z" * 40):
            res = G.check_stack_lower(sd, stack.repo, ls_remote=lambda _r, _b, a=answer: a)
>           assert res["ok"] is False and res["reason"] == "stack-lower-unreadable" == G.REASON_STACK_LOWER_UNREADABLE
E           assert (True is False)

/home/user/wt-2215-c/plugins/superheroes/lib/tests/test_stack_lower_c1l11.py:168: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_lower_c1l11.py::test_unreadable_remote_refuses_even_with_a_stale_pin_that_is_an_ancestor
1 failed in 0.31s
```

**restore:** the inverse edit (the ` or pin  # BITE-PROOF NEUTRALIZATION (E3)` suffix removed).

**restore receipt:** no `BITE-PROOF` text remains, and the line reads `review_base_guard.py:434:    remote_head = ls_remote(repo_root, branch)`.

**raw green:** same command
```
.                                                                        [100%]
1 passed in 0.32s
```

---

## E4 — `_dispatch` checks the stacked layer on `next`

**axis:** `next` on a started session refuses `stack-lower-moved` when the lower layer moved, leaving the state file byte for byte unchanged.

**neutralization** (`round_driver.py`, `_dispatch`, `next` branch):
```python
-            stack = review_base_guard.check_stack_lower(args.session_dir, repo_root)
+            stack = {"ok": True, "stacked": False}  # BITE-PROOF NEUTRALIZATION (E4)
```

**raw red:** `... pytest ... "plugins/superheroes/lib/tests/test_stack_lower_c1l11.py::test_cli_next_refuses_when_lower_moves_during_the_session"`
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_cli_next_refuses_when_lower_moves_during_the_session ___________

stack = <test_stack_lower_c1l11.Stack object at 0x7f40db5a9d90>
capsys = <_pytest.capture.CaptureFixture object at 0x7f40db5a9fd0>

    def test_cli_next_refuses_when_lower_moves_during_the_session(stack, capsys):
        # axis: next on a started session refuses stack-lower-moved and changes nothing but the journal
        sd = _started(stack, capsys)
        state_path = os.path.join(sd, RD.STATE_FILE)
        before = _read(state_path)
        stack.push_lower()
        rc, out = _run(["next", "--session-dir", sd, "--repo-root", stack.repo], capsys)
>       assert rc == 1 and out["ok"] is False and out["reason"] == "stack-lower-moved"
E       assert (0 == 1)

/home/user/wt-2215-c/plugins/superheroes/lib/tests/test_stack_lower_c1l11.py:257: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_lower_c1l11.py::test_cli_next_refuses_when_lower_moves_during_the_session
1 failed in 0.81s
```

**restore:** the inverse edit.

**restore receipt:** no `BITE-PROOF` text remains, and the line reads `round_driver.py:14832:            stack = review_base_guard.check_stack_lower(args.session_dir, repo_root)`.

**raw green:** same command
```
.                                                                        [100%]
1 passed in 0.26s
```

---

## E5 — `_dispatch` checks the stacked layer on `submit`

**axis:** `submit` on a started session refuses `stack-lower-moved` before it reads the artifact, leaving the state file unchanged.

**neutralization** (`round_driver.py`, `_dispatch`, final `else` branch, before the artifact is read):
```python
-        refused = _refuse_stack_lower(args.session_dir)
+        refused = None  # BITE-PROOF NEUTRALIZATION (E5)
```

**raw red:** `... pytest ... "plugins/superheroes/lib/tests/test_stack_lower_c1l11.py::test_cli_submit_refuses_when_lower_moves_during_the_session"`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_cli_submit_refuses_when_lower_moves_during_the_session __________

stack = <test_stack_lower_c1l11.Stack object at 0x7f22c17aa0c0>
capsys = <_pytest.capture.CaptureFixture object at 0x7f22c17aa180>
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-26/test_cli_submit_refuses_when_l0')

    def test_cli_submit_refuses_when_lower_moves_during_the_session(stack, capsys, tmp_path):
        # axis: submit on a started session refuses stack-lower-moved before it reads the artifact or folds
        sd = _started(stack, capsys)
        state_path = os.path.join(sd, RD.STATE_FILE)
        before = _read(state_path)
        stack.push_lower()
        artifact = str(tmp_path / "artifact.json")
        with open(artifact, "w", encoding="utf-8") as fh:
            json.dump({"findings": []}, fh)
        rc, out = _run(["submit", "--session-dir", sd, "--phase", "dispatch-panel", "--attempt", "1",
                        "--artifact", artifact], capsys)
>       assert rc == 1 and out["ok"] is False and out["reason"] == "stack-lower-moved"
E       assert (0 == 1)

/home/user/wt-2215-c/plugins/superheroes/lib/tests/test_stack_lower_c1l11.py:273: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_lower_c1l11.py::test_cli_submit_refuses_when_lower_moves_during_the_session
1 failed in 0.85s
```

**restore:** the inverse edit.

**restore receipt:** no `BITE-PROOF` text remains, and the line reads `round_driver.py:14937:        refused = _refuse_stack_lower(args.session_dir)`.

**raw green:** same command
```
.                                                                        [100%]
1 passed in 0.76s
```

---

## E6 — `_dispatch` checks the stacked layer on `advance`

**axis:** `advance` on a started session refuses `stack-lower-moved` before it folds, leaving the state file unchanged.

**neutralization** (`round_driver.py`, `_dispatch`, `advance` branch):
```python
-        refused = _refuse_stack_lower(args.session_dir)
+        refused = None  # BITE-PROOF NEUTRALIZATION (E6)
```

**raw red:** `... pytest ... "plugins/superheroes/lib/tests/test_stack_lower_c1l11.py::test_cli_advance_refuses_when_lower_moves_during_the_session"`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_cli_advance_refuses_when_lower_moves_during_the_session _________

stack = <test_stack_lower_c1l11.Stack object at 0x7f7232556750>
capsys = <_pytest.capture.CaptureFixture object at 0x7f7232556a80>

    def test_cli_advance_refuses_when_lower_moves_during_the_session(stack, capsys):
        # axis: advance on a started session refuses stack-lower-moved and folds nothing
        sd = _started(stack, capsys)
        state_path = os.path.join(sd, RD.STATE_FILE)
        before = _read(state_path)
        stack.push_lower()
        rc, out = _run(["advance", "--session-dir", sd], capsys)
>       assert rc == 1 and out["ok"] is False and out["reason"] == "stack-lower-moved"
E       assert (0 == 1)

/home/user/wt-2215-c/plugins/superheroes/lib/tests/test_stack_lower_c1l11.py:285: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_lower_c1l11.py::test_cli_advance_refuses_when_lower_moves_during_the_session
1 failed in 0.75s
```

**restore:** the inverse edit.

**restore receipt:** no `BITE-PROOF` text remains, and the line reads `round_driver.py:14914:        refused = _refuse_stack_lower(args.session_dir)`.

**raw green:** same command
```
.                                                                        [100%]
1 passed in 0.76s
```
