# #2349 bite-proof — a delta round cuts unchanged diff sections before it parses

**Provenance:** implementer WO-1 / `lib/round_driver.py` (`_enter_delta_round`), `lib/tests/test_delta_round_unchanged_sections_2349.py`.

Declared guarded elements (from the order): E1 and E2. Each was neutralized with one targeted edit through the edit tool and restored with the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2349` under `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider "<node id>"` (one test node per run, no `-n`), each wrapped in `timeout 300`. The captures are the runner's output with the `UV_NATIVE_TLS` deprecation warning line left out (it is printed first on every run); nothing else is trimmed and nothing is redacted (no secrets, tokens or URLs appear). Each red run exited 1 and each green run exited 0.

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| E1 | `_enter_delta_round`: the cut pair into `delta_surface.split_fix_surface(cut_reviewed, cut_head, ...)` | an unchanged rename or binary section never reaches the hunk parser inside the split, so it cannot hand the PR back | `test_delta_round_unchanged_sections_2349.py::test_t1_an_unchanged_rename_beside_a_fixed_file_gets_the_scoped_delta_round` |
| E2 | `_enter_delta_round`: the cut pair into `_fix_delta_surface(state, cut_reviewed, cut_head)` | the fix delta (surface and diff text) is worked out from the cut pair, so an unchanged rename or binary section cannot make it `None` | the same T1 node |

T1 was the proving node for both runs (the order's choice). T2 has the same failure mode (an unchanged binary instead of an unchanged rename) and was not run for the proof.

E1 and E2 are independent: each neutralization alone turns T1 red, because each call parses the uncut pair on its own and answers unknown. The red text is the same for both (the hand-back decision `fix-surface-unknown`); which call refused is told by the `grep` receipts and the edit, not by the assertion message (`_hand_back_unknown_fix_surface` is reached from the `split.get("unknown")` branch for E1 and from the `fix_delta is None` branch for E2).

Not neutralized by this record: T3 (a fix that renames a file), T4 (a fix that changes a binary) and T5 (plain modified files, the equivalence of the cut on a parseable pair). T3 and T4 are the fail-closed contrasts and T5 the equivalence control; no neutralization of E1 or E2 turns any of them red (with the cut removed they still pass), so they stand as unproven by neutralization.

---

## E1 — the cut pair into `split_fix_surface`

**axis:** an unchanged rename or binary section never reaches the hunk parser inside `split_fix_surface`.

**neutralization** (`round_driver.py`, `_enter_delta_round`; that call only):
```python
-        cut_reviewed, cut_head, state.get("fixBatch") or [])
+        reviewed, state.get("headDiff"), state.get("fixBatch") or [])
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t1_an_unchanged_rename_beside_a_fixed_file_gets_the_scoped_delta_round __

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-1/test_t1_an_unchanged_rename_be0')

    def test_t1_an_unchanged_rename_beside_a_fixed_file_gets_the_scoped_delta_round(tmp_path):
        # axis: an unchanged rename section never reaches the hunk parser, so it cannot hand the PR back
        def pr(repo):
            repo.git("mv", "src/shared.py", "src/moved.py")
            _set_line_10(repo, "keep.py", "reviewed = 1")
    
        reviewed, head = _diffs(tmp_path, pr, lambda repo: _set_line_10(repo, "keep.py", "fixed = 1"))
        assert "rename from src/shared.py\nrename to src/moved.py\n" in reviewed
        _premise_unchanged_unparseable(reviewed, head, "src/moved.py")
>       _assert_scoped_without(_round_two(reviewed, head), "shared.py", "moved.py")

/home/user/wt-2349/plugins/superheroes/lib/tests/test_delta_round_unchanged_sections_2349.py:110: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

state = {'schemaVersion': 5, 'sessionGeneration': 7, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 2, ...}
files = ('shared.py', 'moved.py')

    def _assert_scoped_without(state, *files):
>       assert state["step"] == RD.P_AUDITS and not state.get("terminal"), state.get("decisions")
E       AssertionError: [{'round': 2, 'kind': 'fix-surface-unknown', 'detail': "The driver could not work out what this round's fixes changed ...code they touched cannot be searched. The PR is handed back with its findings still open; certification is withheld."}]
E       assert ('terminal' == 'dispatch-audits'
E         
E         - dispatch-audits
E         + terminal)

/home/user/wt-2349/plugins/superheroes/lib/tests/test_delta_round_unchanged_sections_2349.py:87: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_delta_round_unchanged_sections_2349.py::test_t1_an_unchanged_rename_beside_a_fixed_file_gets_the_scoped_delta_round
1 failed in 1.50s
```

**restore:** the inverse edit, `cut_reviewed, cut_head` put back.

**restore receipt:** `grep -n -B2 -A1 "cut_reviewed, cut_head, state.get" plugins/superheroes/lib/round_driver.py` printed
```
8306-    cut_reviewed, cut_head = _changed_sections_only(reviewed, state.get("headDiff"))
8307-    split = delta_surface.split_fix_surface(
8308:        cut_reviewed, cut_head, state.get("fixBatch") or [])
8309-    if split.get("unknown"):
```

**raw green:**
```
.                                                                        [100%]
1 passed in 1.44s
```

---

## E2 — the cut pair into `_fix_delta_surface`

**axis:** the fix delta is worked out from the cut pair, so an unchanged rename or binary section cannot make it `None`.

**neutralization** (`round_driver.py`, `_enter_delta_round`; that call only):
```python
-    fix_delta = _fix_delta_surface(state, cut_reviewed, cut_head)
+    fix_delta = _fix_delta_surface(state, reviewed, state.get("headDiff"))
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t1_an_unchanged_rename_beside_a_fixed_file_gets_the_scoped_delta_round __

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-3/test_t1_an_unchanged_rename_be0')

    def test_t1_an_unchanged_rename_beside_a_fixed_file_gets_the_scoped_delta_round(tmp_path):
        # axis: an unchanged rename section never reaches the hunk parser, so it cannot hand the PR back
        def pr(repo):
            repo.git("mv", "src/shared.py", "src/moved.py")
            _set_line_10(repo, "keep.py", "reviewed = 1")
    
        reviewed, head = _diffs(tmp_path, pr, lambda repo: _set_line_10(repo, "keep.py", "fixed = 1"))
        assert "rename from src/shared.py\nrename to src/moved.py\n" in reviewed
        _premise_unchanged_unparseable(reviewed, head, "src/moved.py")
>       _assert_scoped_without(_round_two(reviewed, head), "shared.py", "moved.py")

/home/user/wt-2349/plugins/superheroes/lib/tests/test_delta_round_unchanged_sections_2349.py:110: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

state = {'schemaVersion': 5, 'sessionGeneration': 7, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 2, ...}
files = ('shared.py', 'moved.py')

    def _assert_scoped_without(state, *files):
>       assert state["step"] == RD.P_AUDITS and not state.get("terminal"), state.get("decisions")
E       AssertionError: [{'round': 2, 'kind': 'fix-surface-unknown', 'detail': "The driver could not work out what this round's fixes changed ...code they touched cannot be searched. The PR is handed back with its findings still open; certification is withheld."}]
E       assert ('terminal' == 'dispatch-audits'
E         
E         - dispatch-audits
E         + terminal)

/home/user/wt-2349/plugins/superheroes/lib/tests/test_delta_round_unchanged_sections_2349.py:87: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_delta_round_unchanged_sections_2349.py::test_t1_an_unchanged_rename_beside_a_fixed_file_gets_the_scoped_delta_round
1 failed in 1.75s
```

**restore:** the inverse edit, `cut_reviewed, cut_head` put back.

**restore receipt:** `grep -n "_fix_delta_surface(state, cut_reviewed, cut_head)" plugins/superheroes/lib/round_driver.py` printed
```
8314:    fix_delta = _fix_delta_surface(state, cut_reviewed, cut_head)
```

**raw green:**
```
.                                                                        [100%]
1 passed in 1.71s
```
