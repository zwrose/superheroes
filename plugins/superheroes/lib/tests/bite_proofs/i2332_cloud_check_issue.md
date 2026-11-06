# I2332 cloud-check-issue bite-proof record

Invariant: `cloud_check.start` never spawns a check session whose result this seat cannot read: it
requires a positive issue number and confirms that issue resolves on GitHub before anything is
spawned.

Guarded-element set (declared by the order): A1–A3 below, all in
`plugins/superheroes/lib/cloud_check.py`, detectors in
`plugins/superheroes/lib/tests/test_cloud_check_issue_2332.py`. Each node was run alone as
`scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/pyc-2332 -m pytest "<node>" -q -p no:cacheprovider`
from the worktree root, with the detector unedited. Every capture is the full output of that
command; each begins with the same harness warning line (`UV_NATIVE_TLS`), which is not part of the
test. Nothing is redacted. Every restore was the inverse edit (no `git checkout`/`restore`/`reset`/
`stash`), and the restored line was read back from the file after the restore.

---

## A1 — no issue → check-issue-required (`start`)

**Guarded element:** `cloud_check.py:861` `if issue is None:` → `check-issue-required`.
**Axis:** no issue means no readable result path, so the check is refused before anything is spawned.

**Neutralization:** `if issue is None:` → `if False and issue is None:`.

**Red run** (`test_start_without_an_issue_is_refused_before_anything_is_read_or_spawned`):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_start_without_an_issue_is_refused_before_anything_is_read_or_spawned ___

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-0/test_start_without_an_issue_is0')

    def test_start_without_an_issue_is_refused_before_anything_is_read_or_spawned(tmp_path):
        local = _build(tmp_path)
        spawner, reader = Spawner(), Reader()
        result = _go(local, spawner, reader)
>       assert result["action"] == "refused" and result["reason"] == "check-issue-required"
E       AssertionError: assert ('refused' == 'refused'
E         
E           refused and 'check-issue-invalid' == 'check-issue-required'
E         
E         - check-issue-required
E         + check-issue-invalid)

/home/user/wt-2332/plugins/superheroes/lib/tests/test_cloud_check_issue_2332.py:41: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check_issue_2332.py::test_start_without_an_issue_is_refused_before_anything_is_read_or_spawned
1 failed in 1.23s
```
Axis check: the red is on the refusal token for the missing issue (`check-issue-required` expected;
the neutralized guard let the `None` fall to the next guard, which answered `check-issue-invalid`).

**Restore:** inverse edit, `if False and issue is None:` → `if issue is None:`.
**Restore receipt:** read back from the file (`cloud_check.py:860-862`):
```
    # axis: no issue means no readable result path, so the check is refused before anything is spawned
    if issue is None:
        return _refusal("check-issue-required", _ISSUE_REQUIRED)
```

**Green run:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.45s
```

---

## A2 — reader result not True → check-issue-unreadable (`start`)

**Guarded element:** `cloud_check.py:877` `if readable is not True:` → `check-issue-unreadable`.
**Axis:** an issue that does not resolve is no readable result path either.

**Neutralization:** `if readable is not True:` → `if False and readable is not True:`.

**Red run** (`test_an_issue_that_does_not_resolve_spawns_nothing`):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_an_issue_that_does_not_resolve_spawns_nothing ______________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-2/test_an_issue_that_does_not_re0')

    def test_an_issue_that_does_not_resolve_spawns_nothing(tmp_path):
        local = _build(tmp_path)
        spawner, reader = Spawner(), Reader(answer=False)
        result = _go(local, spawner, reader, issue=1745)
>       assert result["action"] == "refused" and result["reason"] == "check-issue-unreadable"
E       AssertionError: assert ('started' == 'refused'
E         
E         - refused
E         + started)

/home/user/wt-2332/plugins/superheroes/lib/tests/test_cloud_check_issue_2332.py:61: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check_issue_2332.py::test_an_issue_that_does_not_resolve_spawns_nothing
1 failed in 1.37s
```
Axis check: the red is the check being started (`started`) although the reader answered False.

**Restore:** inverse edit, `if False and readable is not True:` → `if readable is not True:`.
**Restore receipt:** read back from the file (`cloud_check.py:876-877`):
```
    # axis: an issue that does not resolve is no readable result path either
    if readable is not True:
```

**Green run:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.30s
```

---

## A3 — default reader's number check (`_issue_resolves`)

**Guarded element:** `cloud_check.py:848` `isinstance(body, dict) and body.get("number") == number`.
**Axis:** GitHub answering for another issue number is not this issue resolving.

**Neutralization:** `return isinstance(body, dict) and body.get("number") == number` →
`return isinstance(body, dict)` (any parsed object reads True).

**Red run** (`test_the_default_reader_is_false_for_another_issue_number`):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_the_default_reader_is_false_for_another_issue_number ___________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fa352138e30>

    def test_the_default_reader_is_false_for_another_issue_number(monkeypatch):
        _patch_gh(monkeypatch, done=_Done(0, json.dumps({"number": 7})))
>       assert CC._issue_resolves("/repo", 1745) is False
E       AssertionError: assert True is False
E        +  where True = <function _issue_resolves at 0x7fa3524140e0>('/repo', 1745)
E        +    where <function _issue_resolves at 0x7fa3524140e0> = CC._issue_resolves

/home/user/wt-2332/plugins/superheroes/lib/tests/test_cloud_check_issue_2332.py:145: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check_issue_2332.py::test_the_default_reader_is_false_for_another_issue_number
1 failed in 1.02s
```
Axis check: the red is the reader answering True for a body carrying issue 7 when 1745 was asked.

**Restore:** inverse edit, `return isinstance(body, dict)` →
`return isinstance(body, dict) and body.get("number") == number`.
**Restore receipt:** read back from the file (`cloud_check.py:848`):
```
        return isinstance(body, dict) and body.get("number") == number
```

**Green run:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.85s
```
