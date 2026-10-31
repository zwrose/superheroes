# WO-1 (#1097) bite-proof — the launcher's detective charter

Per-guard bite proof for `charter_premise_reason` (`launcher.py`), the command choice in `compose_launch`,
and the ledger's `reserved` `charter` fold guard (`launch_ledger.py`). Every red and green below is the
raw output of a run made in this dispatch; the neutralization of each was a targeted Edit and was undone
by the inverse Edit. Nothing in the captures is redacted (no secrets, tokens or private URLs appear in
them). The warning line `UV_NATIVE_TLS ...` that the pinned interpreter prints on every run is kept.

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-1 | `charter_premise_reason` charter-name guard (`premise-charter-invalid`) | `charter` is a string naming a launchable charter | `test_compose_refuses_a_bad_charter_budget_pair_and_composes_nothing` |
| BP-2 | `charter_premise_reason` missing-budget guard (`premise-detective-budget-missing`), compose door | a detective prompt is never composed without a budget | `test_a_detective_premise_without_a_budget_is_never_composed_with_a_workhorse_command` |
| BP-3 | `charter_premise_reason` budget-without-detective guard (`premise-budget-without-detective`) | a budget on a workhorse lane is refused, not dropped | `test_compose_refuses_a_bad_charter_budget_pair_and_composes_nothing` |
| BP-4 | `charter_premise_reason` budget-shape guard (`premise-budget-invalid`) | a budget is one unpadded non-blank line | `test_compose_refuses_a_bad_charter_budget_pair_and_composes_nothing` |
| BP-5 | `compose_launch` command choice `cmd = _CHARTER_COMMANDS[charter]` | the prompt starts with the premise's charter command | `test_local_detective_prompt_starts_with_the_command_and_names_the_budget` |
| BP-6 | `_validate_reserved_optional_fields` `charter` guard (`fold-bad-field:reserved:charter`) | the record's charter is a launchable name and agrees with the premise's | `test_fold_refuses_a_bad_or_disagreeing_charter` |

Notes on reach, stated plainly:

- `validate_premise` and `compose_launch` both call `charter_premise_reason`, so BP-1 to BP-4 neutralize the
  one function body and both doors go red together. The proof runs name the compose-door test node; the
  `validate_premise` door has its own parametrized test (`test_validate_premise_refuses_a_bad_charter_budget_pair`)
  over the same cases, which was not run against a neutralized tree (the order's budget fits one node per element).
- A parametrized node stops at its first failing case under `-x`. Each red shows that first case only; the green
  runs every case.
- BP-6 neutralizes the whole guard. Its three disjuncts (not a string, not in `LAUNCH_CHARTERS`, disagrees with the
  premise) are not neutralized one at a time; the parametrized test has a case for each, but only the whole guard
  was proven to bite.
- BP-2's red fails by `KeyError: 'budget'` inside `compose_launch`, because with the guard off the composer reaches
  `premise["budget"]` on a premise without one. That is a failure of the test's call, not of its `ok is False`
  assertion; either way the detector goes red.
- Row D.2 on the base commit is recorded at the end (red today).
- The decorative `!!!!` banner lines of the `-x` runs were retyped into this file and may differ from the terminal
  in the count of `!` characters; no other line was edited.

---

## BP-1 — premise-charter-invalid

- **axis:** `charter` is a string naming a launchable charter

**neutralization** (`plugins/superheroes/lib/launcher.py`):
```python
    if False and "charter" in premise and (
```
(replaces `if "charter" in premise and (`)

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/sh-pyc-1097 -m pytest plugins/superheroes/lib/tests/test_launcher_detective_1097.py::test_compose_refuses_a_bad_charter_budget_pair_and_composes_nothing -q -x
```

**raw red** (exit 1):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F
=================================== FAILURES ===================================
_ test_compose_refuses_a_bad_charter_budget_pair_and_composes_nothing[extra0-premise-charter-invalid] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-3/test_compose_refuses_a_bad_cha0')
extra = {'charter': None}, reason = 'premise-charter-invalid'

    @pytest.mark.parametrize("extra,reason", _refusal_cases())
    def test_compose_refuses_a_bad_charter_budget_pair_and_composes_nothing(tmp_path, extra, reason):
        # axis: charter_premise_reason at the compose_launch door — each refusal token, no prompt
        repo = _init_repo(tmp_path / "repo")
>       result = _local(repo, _valid_premise(repo, **extra))
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-1097/plugins/superheroes/lib/tests/test_launcher_detective_1097.py:94: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt-1097/plugins/superheroes/lib/tests/test_launcher_detective_1097.py:42: in _local
    return L.compose_launch(repo, issue, premise)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo_root = '/tmp/claude-0/pytest-of-root/pytest-3/test_compose_refuses_a_bad_cha0/repo'
issue = 656
premise = {'baseCommit': '92c0cc7a8d1a9dd6af3521c876cdbee1e221a8a6', 'surfaces': ['plugins/superheroes/lib'], 'batchId': 'wave-test', 'issue': 656, ...}
model = None, doctrine_loader = None, effort = None, place = None
cloud_environment = None, session_name = None

    def compose_launch(
        repo_root, issue, premise, model=None, doctrine_loader=None, effort=None,
        place=None, cloud_environment=None, session_name=None,
    ):
        """Compose prompt and argv. Never raises."""
        import launch_lines  # the one home of the launch line labels (cloud_builder parses them back)
        if place not in (None, PLACE_LOCAL, PLACE_CLOUD):
            return _fail("launch-place-invalid")
        cloud = place == PLACE_CLOUD
        loader = doctrine_loader or launch_doctrine.load
        doctrine = loader()
        if not doctrine.get("ok"):
            return _fail(doctrine.get("reason") or "doctrine-unreadable")
    
        rulings_block = doctrine.get("rulingsBlock") or ""
        own_line = launch_doctrine.ruling_line(doctrine, "own-worktree")
        if not own_line:
            return _fail("compose-ruling-zero-absent")
    
        adopts = None
        adopts_reason = adopts_premise_reason(premise)
        if adopts_reason is not None:
            return _fail(adopts_reason)
        charter_reason = charter_premise_reason(premise)
        if charter_reason is not None:
            return _fail(charter_reason)
        charter = premise.get("charter", "workhorse") if isinstance(premise, dict) else "workhorse"
>       cmd = _CHARTER_COMMANDS[charter]
              ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: None

/home/user/wt-1097/plugins/superheroes/lib/launcher.py:1399: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_detective_1097.py::test_compose_refuses_a_bad_charter_budget_pair_and_composes_nothing[extra0-premise-charter-invalid]
!!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.72s
```

**restore:** the inverse Edit — `if False and "charter" in premise and (` back to `if "charter" in premise and (`.

**restore receipt** (a `grep -n` over `launcher.py`, run in the green command below): `1168:    if "charter" in premise and (`.

**raw green** (exit 0):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
...................................                                      [100%]
35 passed in 3.07s
1168:    if "charter" in premise and (
```
(the last line is the restore-receipt grep, which also matched no `if False`.)

---

## BP-2 — premise-detective-budget-missing (compose door; the DoD fixture)

- **axis:** a detective prompt is never composed without a budget

**neutralization** (`plugins/superheroes/lib/launcher.py`):
```python
    if False and charter == "detective" and not has_budget:
```
(replaces `if charter == "detective" and not has_budget:`)

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/sh-pyc-1097 -m pytest plugins/superheroes/lib/tests/test_launcher_detective_1097.py::test_a_detective_premise_without_a_budget_is_never_composed_with_a_workhorse_command -q
```

**raw red** (exit 1):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_detective_premise_without_a_budget_is_never_composed_with_a_workhorse_command _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-5/test_a_detective_premise_witho0')

    def test_a_detective_premise_without_a_budget_is_never_composed_with_a_workhorse_command(tmp_path):
        # axis: the DoD fixture — a detective premise with no budget composes nothing at all
        repo = _init_repo(tmp_path / "repo")
>       result = _local(repo, _valid_premise(repo, charter="detective"))
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-1097/plugins/superheroes/lib/tests/test_launcher_detective_1097.py:111: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt-1097/plugins/superheroes/lib/tests/test_launcher_detective_1097.py:42: in _local
    return L.compose_launch(repo, issue, premise)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo_root = '/tmp/claude-0/pytest-of-root/pytest-5/test_a_detective_premise_witho0/repo'
issue = 656
premise = {'baseCommit': '25d62b7078ea845935239369951a88db5b762642', 'surfaces': ['plugins/superheroes/lib'], 'batchId': 'wave-test', 'issue': 656, ...}
model = None, doctrine_loader = None, effort = None, place = None
cloud_environment = None, session_name = None

    def compose_launch(
        repo_root, issue, premise, model=None, doctrine_loader=None, effort=None,
        place=None, cloud_environment=None, session_name=None,
    ):
        """Compose prompt and argv. Never raises."""
        import launch_lines  # the one home of the launch line labels (cloud_builder parses them back)
        if place not in (None, PLACE_LOCAL, PLACE_CLOUD):
            return _fail("launch-place-invalid")
        cloud = place == PLACE_CLOUD
        loader = doctrine_loader or launch_doctrine.load
        doctrine = loader()
        if not doctrine.get("ok"):
            return _fail(doctrine.get("reason") or "doctrine-unreadable")
    
        rulings_block = doctrine.get("rulingsBlock") or ""
        own_line = launch_doctrine.ruling_line(doctrine, "own-worktree")
        if not own_line:
            return _fail("compose-ruling-zero-absent")
    
        adopts = None
        adopts_reason = adopts_premise_reason(premise)
        if adopts_reason is not None:
            return _fail(adopts_reason)
        charter_reason = charter_premise_reason(premise)
        if charter_reason is not None:
            return _fail(charter_reason)
        charter = premise.get("charter", "workhorse") if isinstance(premise, dict) else "workhorse"
        cmd = _CHARTER_COMMANDS[charter]
        issue_line = "Issue: #%s" % issue
        if charter == "detective":
>           issue_line += "\n%s %s" % (_BUDGET_LABEL, premise["budget"])
                                                      ^^^^^^^^^^^^^^^^^
E           KeyError: 'budget'

/home/user/wt-1097/plugins/superheroes/lib/launcher.py:1402: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_detective_1097.py::test_a_detective_premise_without_a_budget_is_never_composed_with_a_workhorse_command
1 failed in 2.20s
```

**restore:** the inverse Edit — `if False and charter == "detective" and not has_budget:` back to `if charter == "detective" and not has_budget:`.

**restore receipt** (Grep over `launcher.py` for `charter == "detective" and not has_budget|if False`): `1175:    if charter == "detective" and not has_budget:` — one match, no `if False`.

**raw green** (exit 0):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.45s
```

---

## BP-3 — premise-budget-without-detective

- **axis:** a budget on a workhorse lane is refused, not dropped

**neutralization** (`plugins/superheroes/lib/launcher.py`):
```python
    if False and has_budget and charter == "workhorse":
```
(replaces `if has_budget and charter == "workhorse":`)

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/sh-pyc-1097 -m pytest plugins/superheroes/lib/tests/test_launcher_detective_1097.py::test_compose_refuses_a_bad_charter_budget_pair_and_composes_nothing -q -x
```

**raw red** (exit 1):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
...................F
=================================== FAILURES ===================================
_ test_compose_refuses_a_bad_charter_budget_pair_and_composes_nothing[extra19-premise-budget-without-detective] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-7/test_compose_refuses_a_bad_cha19')
extra = {'budget': 'until 18:00 local, no more than 3 hours of builder time'}
reason = 'premise-budget-without-detective'

    @pytest.mark.parametrize("extra,reason", _refusal_cases())
    def test_compose_refuses_a_bad_charter_budget_pair_and_composes_nothing(tmp_path, extra, reason):
        # axis: charter_premise_reason at the compose_launch door — each refusal token, no prompt
        repo = _init_repo(tmp_path / "repo")
        result = _local(repo, _valid_premise(repo, **extra))
>       assert result["ok"] is False
E       assert True is False

/home/user/wt-1097/plugins/superheroes/lib/tests/test_launcher_detective_1097.py:95: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_detective_1097.py::test_compose_refuses_a_bad_charter_budget_pair_and_composes_nothing[extra19-premise-budget-without-detective]
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed, 19 passed in 2.23s
```

**restore:** the inverse Edit — `if False and has_budget and charter == "workhorse":` back to `if has_budget and charter == "workhorse":`.

**restore receipt:** the green run below passes every case, including the BP-3 and BP-4 cases; the final `if False` Grep over `launch*.py` (after BP-6) found no matches.

**raw green** (exit 0):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
...................................                                      [100%]
35 passed in 2.00s
```
(This run was issued in the same step as the BP-4 neutralizing Edit; its 35 passes include the BP-4 cases, which would fail with that guard off, so the BP-4 Edit had not landed when it ran.)

---

## BP-4 — premise-budget-invalid

- **axis:** a budget is one unpadded non-blank line

**neutralization** (`plugins/superheroes/lib/launcher.py`):
```python
    if False and has_budget and (
        not isinstance(budget, str)
```
(replaces `if has_budget and (` followed by `not isinstance(budget, str)`)

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/sh-pyc-1097 -m pytest plugins/superheroes/lib/tests/test_launcher_detective_1097.py::test_compose_refuses_a_bad_charter_budget_pair_and_composes_nothing -q -x
```

**raw red** (exit 1):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.....................F
=================================== FAILURES ===================================
_ test_compose_refuses_a_bad_charter_budget_pair_and_composes_nothing[extra21-premise-budget-invalid] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-9/test_compose_refuses_a_bad_cha21')
extra = {'charter': 'detective', 'budget': None}
reason = 'premise-budget-invalid'

    @pytest.mark.parametrize("extra,reason", _refusal_cases())
    def test_compose_refuses_a_bad_charter_budget_pair_and_composes_nothing(tmp_path, extra, reason):
        # axis: charter_premise_reason at the compose_launch door — each refusal token, no prompt
        repo = _init_repo(tmp_path / "repo")
        result = _local(repo, _valid_premise(repo, **extra))
>       assert result["ok"] is False
E       assert True is False

/home/user/wt-1097/plugins/superheroes/lib/tests/test_launcher_detective_1097.py:95: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_detective_1097.py::test_compose_refuses_a_bad_charter_budget_pair_and_composes_nothing[extra21-premise-budget-invalid]
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!! 
1 failed, 21 passed in 2.25s
```

**restore:** the inverse Edit — `if False and has_budget and (` back to `if has_budget and (`.

**restore receipt:** the green run below passes all 35 cases; the final `if False` Grep over `launch*.py` found no matches.

**raw green** (exit 0):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
...................................                                      [100%]
35 passed in 2.49s
```

---

## BP-5 — the command choice

- **axis:** the prompt starts with the command of the charter the premise names

**neutralization** (`plugins/superheroes/lib/launcher.py`):
```python
    cmd = _WORKHORSE_CMD
```
(replaces `cmd = _CHARTER_COMMANDS[charter]`)

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/sh-pyc-1097 -m pytest plugins/superheroes/lib/tests/test_launcher_detective_1097.py::test_local_detective_prompt_starts_with_the_command_and_names_the_budget -q
```

**raw red** (exit 1; the prompt body in the assertion message is elided by pytest itself with `...`):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_local_detective_prompt_starts_with_the_command_and_names_the_budget ___

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-11/test_local_detective_prompt_st0')

    def test_local_detective_prompt_starts_with_the_command_and_names_the_budget(tmp_path):
        # axis: the command choice and the budget line on the local prompt
        repo = _init_repo(tmp_path / "repo")
        detective = _local(repo, _valid_premise(repo, charter="detective", budget=BUDGET))
        workhorse = _local(repo, _valid_premise(repo))
        assert detective["ok"] is True, detective
>       assert detective["prompt"].startswith(DETECTIVE_HEAD % (656, BUDGET))
E       AssertionError: assert False
E        +  where False = <built-in method startswith of str object at 0x2aba5420>(('/superheroes:detective\n\nIssue: #%s\nBudget: %s\n\n' % (656, 'until 18:00 local, no more than 3 hours of builder time')))
E        +    where <built-in method startswith of str object at 0x2aba5420> = '/superheroes:workhorse\n\nIssue: #656\nBudget: until 18:00 local, no more than 3 hours of builder time\n\n- `own-work...ermission classifier sees it; staging a gated command in a file and executing the file to dodge the gate is forbidden.'.startswith

/home/user/wt-1097/plugins/superheroes/lib/tests/test_launcher_detective_1097.py:143: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_detective_1097.py::test_local_detective_prompt_starts_with_the_command_and_names_the_budget
1 failed in 1.77s
```

**restore:** the inverse Edit — `cmd = _WORKHORSE_CMD` back to `cmd = _CHARTER_COMMANDS[charter]`.

**restore receipt:** the restored line is `    cmd = _CHARTER_COMMANDS[charter]` (the Edit matched `cmd = _WORKHORSE_CMD` followed by `issue_line` and replaced it with that line); the final `if False` Grep found no matches.

**raw green** (exit 0):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.74s
```

---

## BP-6 — the ledger `charter` fold guard

- **axis:** the record's charter is a launchable name and agrees with the premise's

**neutralization** (`plugins/superheroes/lib/launch_ledger.py`):
```python
    if False and "charter" in rec:
        charter = rec["charter"]
```
(replaces `if "charter" in rec:` followed by `charter = rec["charter"]`)

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/sh-pyc-1097 -m pytest plugins/superheroes/lib/tests/test_launcher_detective_1097.py::test_fold_refuses_a_bad_or_disagreeing_charter -q -x
```

**raw red** (exit 1):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F
=================================== FAILURES ===================================
____________ test_fold_refuses_a_bad_or_disagreeing_charter[extra0] ____________

extra = {'charter': 'bogus'}

    @pytest.mark.parametrize("extra", [
        {"charter": "bogus"},
        {"charter": ""},
        {"charter": None},
        {"charter": "Detective"},
        {"charter": ["detective"]},
        {"charter": "detective", "premise": {"charter": "workhorse"}},
        {"charter": "workhorse", "premise": {"charter": "detective", "budget": "1h"}},
    ])
    def test_fold_refuses_a_bad_or_disagreeing_charter(extra):
        # axis: the reserved charter guard — a string in LAUNCH_CHARTERS that agrees with the premise's
        folded = ll.fold([_fold_rec(**extra)])
>       assert folded["ok"] is False
E       assert True is False

/home/user/wt-1097/plugins/superheroes/lib/tests/test_launcher_detective_1097.py:253: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_detective_1097.py::test_fold_refuses_a_bad_or_disagreeing_charter[extra0]
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.66s
```

**restore:** the inverse Edit — `if False and "charter" in rec:` back to `if "charter" in rec:`.

**restore receipt:** Grep for `if False` over `plugins/superheroes/lib/launch*.py` after the restore: `No matches found`.

**raw green** (exit 0):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.......                                                                  [100%]
7 passed in 1.40s
```

---

## Row D.2 on the base commit — red today

The test file was written first, before any edit to `launcher.py` or `launch_ledger.py`. Its first run,
with the parametrize list for the command-table test still reading `ll.LAUNCH_CHARTERS` at import time, did
not collect (a collection error, not a red for D.2):

```
ERROR plugins/superheroes/lib/tests/test_launcher_detective_1097.py - Attribu...
AttributeError: module 'launch_ledger' has no attribute 'LAUNCH_CHARTERS'
```

That parametrize list was changed to the literal names `["workhorse", "detective"]` (the test body still reads
`ll.LAUNCH_CHARTERS`-keyed `L._CHARTER_COMMANDS` at run time), and D.2 was run alone with both source files
still at base:

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/sh-pyc-1097 -m pytest 'plugins/superheroes/lib/tests/test_launcher_detective_1097.py::test_a_detective_premise_without_a_budget_is_never_composed_with_a_workhorse_command' -q
```

**raw red** (exit 1):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_detective_premise_without_a_budget_is_never_composed_with_a_workhorse_command _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-0/test_a_detective_premise_witho0')

    def test_a_detective_premise_without_a_budget_is_never_composed_with_a_workhorse_command(tmp_path):
        # axis: the DoD fixture — a detective premise with no budget composes nothing at all
        repo = _init_repo(tmp_path / "repo")
        result = _local(repo, _valid_premise(repo, charter="detective"))
>       assert result["ok"] is False
E       assert True is False

/home/user/wt-1097/plugins/superheroes/lib/tests/test_launcher_detective_1097.py:112: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_detective_1097.py::test_a_detective_premise_without_a_budget_is_never_composed_with_a_workhorse_command
1 failed in 1.63s
```

The green half of D.2 is BP-2's green run above (restored code, same node, `1 passed`).
