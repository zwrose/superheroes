# Work order A (#2072, layer 3 of #2053) bite-proof: a break-it test ruled out of scope and discharged by the audit is not required to be kept

> Note (2026-10-31, #2296): owner-machine paths and the name of a consuming project in this record were replaced with neutral placeholders after capture; nothing else changed.

**Provenance:** claude / sonnet-5.5 (implementer, work order A), maker family anthropic. Production under proof: `plugins/superheroes/lib/round_driver.py` (`_break_it_ruled_exempt`, `_break_it_kept_step`), `plugins/superheroes/lib/review_record_session.py` (`_decide`), `plugins/superheroes/lib/receipt_disclosures.py` (`build_degraded_prose`, the `breakItKept` not-kept filter). Tests: `plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py`.

Declared guarded-element set (from the order): **E1**, **E2**, **E3**, **E4**, **E5**, **E6**, **E7**. Each was neutralized by one targeted edit (the Edit tool, exact-text match), only its proving nodes run by exact node id (never `-k`; a bare function id selects every parametrization of that function), the inverse edit applied, `git diff --stat` taken over the file (empty: the file equals the implementation commit `cd750964a`), and the same ids run again. The probes ran on the committed implementation. No `git checkout`, `git restore`, `git reset` or `git stash` was used.

## Guarded elements

| ID | Guarded element | Axis | Proving nodes (all in `test_break_it_ruled_exempt_2072.py`) |
|---|---|---|---|
| E1 | the rule leg, `_break_it_ruled_exempt` (`live.get("ruling") == "out-of-scope" and live.get("source") == "rule"`) | only an out-of-scope ruling from the `rule` verb exempts; a later guidance/fix ruling, or no ruling, leaves the check owed | `::test_edge2_a_cleared_finding_with_no_rule_still_owes_the_check`, `::test_edge4_a_later_ruling_that_superseded_the_skip_owes_the_check` |
| E2 | the provenance leg, `_break_it_ruled_exempt` (`isinstance(prov, dict) and all(... ruledBy, ruledAt ...)`) | an unattributed ruling exempts nothing | `::test_edge3_an_unattributed_rule_owes_the_check` |
| E3 | the discharge leg, `_break_it_ruled_exempt` (the scan of `rounds[*]["audits"]` for a clearing entry whose `id` is the key) | a ruling with no clearing audit exempts nothing | `::test_edge1_a_rule_with_no_clearing_audit_still_owes_the_check` |
| E4 | the out-of-scope routing in `_break_it_kept_step` (`disposition not in ("fixed", "out-of-scope")`) | an out-of-scope disposition owes the kept check unless the exemption holds, never a bare `not-required` | `::test_edge1_a_rule_with_no_clearing_audit_still_owes_the_check[out-of-scope]` |
| E5 | the exemption wiring in `_break_it_kept_step` (`ruled = _break_it_ruled_exempt(state, key)`) | the exemption is consulted before `check_kept`; without it an exempt test parks | `::test_a_ruled_out_of_scope_and_discharged_test_is_exempt_from_the_kept_check`, `::test_the_exempt_finding_lets_the_terminal_converge` |
| E6 | the record label in `review_record_session._decide` (`if disp == "fixed" and isinstance(held, dict):`) | a fixed finding the driver ruled out of scope reads `ruling`, never "fixed and audited" | `::test_the_review_record_labels_the_exempt_finding_ruling_never_fixed` |
| E7 | the accepted tuple in `receipt_disclosures.build_degraded_prose` (`("kept", "not-required", "ruled-out-of-scope")`) | a `ruled-out-of-scope` row is not listed as a test the final change failed to hold | `::test_the_receipt_disclosure_does_not_list_a_ruled_out_of_scope_row_as_not_kept` |

## Disclosures

- Every element went red under its neutralization (pytest exit 1) and green after the restore (exit 0).
- **E1's red is partly a crash.** The order's neutralization (`if False and not (...)`) lets a missing ruling fall through to `live.get("provenance")`, so the edge-2 test errors with `AttributeError: 'NoneType' object has no attribute 'get'` rather than failing an assertion. The two edge-4 rows (a guidance/fix ruling with attributed provenance and a clearing audit) fail on the axis: `assert False is True` (the finding was wrongly exempt, `check_kept` never ran). A gate-source skip carries no provenance, so the `source == "rule"` sub-leg is not separately reachable through a `rulingsLog` row (the log writer stamps `source: "rule"` on every row it reads) and is covered by the provenance leg and `::test_edge4b_a_gate_skip_is_not_a_rule_verb_ruling`; it was not neutralized on its own because it is not an independently declared element.
- **E2's red is partly a crash.** Under the neutralization the exempt row builder reads `ruled["provenance"]["ruledBy"]`: five of the ten rows fail with `KeyError`/`TypeError` building the row, the other five fail on the axis with `assert False is True`.
- E3 is neutralized by returning the ruling row (`return live`) where the scan finds no clearing audit, because the edge-1 fixtures record no audit at all, so a neutralized per-entry test would never run. The sub-conditions of the per-entry test (`id == key`, `ruling in audits._CLEARS`) are not declared elements; they are exercised by `::test_edge5_a_not_discharged_audit_owes_the_check`, `::test_edge8_a_round_without_a_usable_audit_list_contributes_no_discharge[other-key]` and `::test_a_ruled_out_of_scope_and_discharged_test_is_exempt_from_the_kept_check`, but were not neutralized.
- The restore receipt is `git diff --stat -- <file>` taken after the inverse edit, printed between `--- git diff --stat` and `--- end diff` markers: in every element it printed nothing. The restored line is also quoted from `grep -n` (or the Read tool for E3).
- The command shape is `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest <exact node ids> -q`, followed by `echo "pytest exit: $?"`. Everything else is verbatim (default `--tb`, no filter).
- Redaction: none needed; local `/path/to/home/...` and `/private/tmp/...` paths are kept as printed, no secret, token or private URL appears.
- **E2's red capture is 40480 bytes, over the 32 KiB ceiling**, so it is stored off-repo at `/private/tmp/claude-501/-Users-zwrose--superheroes-worktrees-superheroes-issue-2072-wo-a/f9907c28-e51a-4615-ac4e-768bdc84522a/scratchpad/e2_red.txt` and its first and last lines are quoted below. All other captures are under 32 KiB, and the record is under 128 KiB together.

---

## E1: the rule leg

- **axis:** only an out-of-scope ruling from the `rule` verb exempts; a later guidance/fix ruling, or no ruling, leaves the check owed

**neutralization** (`plugins/superheroes/lib/round_driver.py`, `_break_it_ruled_exempt`):
```diff
-    if not (isinstance(live, dict) and live.get("ruling") == "out-of-scope"
+    if False and not (isinstance(live, dict) and live.get("ruling") == "out-of-scope"
             and live.get("source") == "rule"):
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_edge2_a_cleared_finding_with_no_rule_still_owes_the_check plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_edge4_a_later_ruling_that_superseded_the_skip_owes_the_check -q
```

**raw red** (exit 1):
```
FFF                                                                      [100%]
=================================== FAILURES ===================================
________ test_edge2_a_cleared_finding_with_no_rule_still_owes_the_check ________

world = <test_break_it_loop.World object at 0x1077a68a0>, spy = []

    def test_edge2_a_cleared_finding_with_no_rule_still_owes_the_check(world, spy):
        key = _shape(world)
        _audit(world, key)
>       _owes_the_check(world, spy)

/path/to/home/.superheroes-worktrees/superheroes/issue-2072-wo-a/plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py:140: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/path/to/home/.superheroes-worktrees/superheroes/issue-2072-wo-a/plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py:64: in _owes_the_check
    assert RD._break_it_kept_step(world.state, world.state["config"]) is True
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/path/to/home/.superheroes-worktrees/superheroes/issue-2072-wo-a/plugins/superheroes/lib/round_driver.py:6958: in _break_it_kept_step
    ruled = _break_it_ruled_exempt(state, key)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

state = {'schemaVersion': 5, 'sessionGeneration': 6, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...}
key = 'tests/test_charge_once.py::breakit a retried charge runs twice@L1'

    def _break_it_ruled_exempt(state, key):
        """The ``rule``-verb out-of-scope ruling row that exempts a break-it finding's test from the kept
        check, or None. Exempt only when the finding's effective decision is that attributed ruling AND
        some round's recorded audit cleared the finding; either leg alone leaves the check owed."""
        live = _live_ruling_by_key(state).get(key)
        # axis: only an out-of-scope ruling from the rule verb exempts — a fixed finding with no ruling still owes the kept check — see bite-proof record wo_a_2072_ruled_exempt
        if False and not (isinstance(live, dict) and live.get("ruling") == "out-of-scope"
                and live.get("source") == "rule"):
            return None
>       prov = live.get("provenance")
               ^^^^^^^^
E       AttributeError: 'NoneType' object has no attribute 'get'

/path/to/home/.superheroes-worktrees/superheroes/issue-2072-wo-a/plugins/superheroes/lib/round_driver.py:6899: AttributeError
_ test_edge4_a_later_ruling_that_superseded_the_skip_owes_the_check[guidance] __

world = <test_break_it_loop.World object at 0x1077bffb0>, spy = []
later = 'guidance'

    @pytest.mark.parametrize("later", ["guidance", "fix"])
    def test_edge4_a_later_ruling_that_superseded_the_skip_owes_the_check(world, spy, later):
        key = _shape(world)
        _rule(world, key)
        _rule(world, key, ruling=later)
        _audit(world, key)
>       _owes_the_check(world, spy)

/path/to/home/.superheroes-worktrees/superheroes/issue-2072-wo-a/plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py:162: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

world = <test_break_it_loop.World object at 0x1077bffb0>, spy = []

    def _owes_the_check(world, spy):
        """The kept step ran `check_kept`, found the test absent from head, and parked."""
>       assert RD._break_it_kept_step(world.state, world.state["config"]) is True
E       AssertionError: assert False is True
E        +  where False = <function _break_it_kept_step at 0x10782dee0>({'schemaVersion': 5, 'sessionGeneration': 6, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...}, {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...})
E        +    where <function _break_it_kept_step at 0x10782dee0> = RD._break_it_kept_step
E        +    and   {'schemaVersion': 5, 'sessionGeneration': 6, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...} = <test_break_it_loop.World object at 0x1077bffb0>.state

/path/to/home/.superheroes-worktrees/superheroes/issue-2072-wo-a/plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py:64: AssertionError
____ test_edge4_a_later_ruling_that_superseded_the_skip_owes_the_check[fix] ____

world = <test_break_it_loop.World object at 0x106a71a00>, spy = []
later = 'fix'

    @pytest.mark.parametrize("later", ["guidance", "fix"])
    def test_edge4_a_later_ruling_that_superseded_the_skip_owes_the_check(world, spy, later):
        key = _shape(world)
        _rule(world, key)
        _rule(world, key, ruling=later)
        _audit(world, key)
>       _owes_the_check(world, spy)

/path/to/home/.superheroes-worktrees/superheroes/issue-2072-wo-a/plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py:162: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

world = <test_break_it_loop.World object at 0x106a71a00>, spy = []

    def _owes_the_check(world, spy):
        """The kept step ran `check_kept`, found the test absent from head, and parked."""
>       assert RD._break_it_kept_step(world.state, world.state["config"]) is True
E       AssertionError: assert False is True
E        +  where False = <function _break_it_kept_step at 0x10782dee0>({'schemaVersion': 5, 'sessionGeneration': 6, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...}, {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...})
E        +    where <function _break_it_kept_step at 0x10782dee0> = RD._break_it_kept_step
E        +    and   {'schemaVersion': 5, 'sessionGeneration': 6, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...} = <test_break_it_loop.World object at 0x106a71a00>.state

/path/to/home/.superheroes-worktrees/superheroes/issue-2072-wo-a/plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py:64: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_edge2_a_cleared_finding_with_no_rule_still_owes_the_check
FAILED plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_edge4_a_later_ruling_that_superseded_the_skip_owes_the_check[guidance]
FAILED plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_edge4_a_later_ruling_that_superseded_the_skip_owes_the_check[fix]
3 failed in 48.53s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_driver.py` (`if False and not (isinstance(live, dict)` back to `if not (isinstance(live, dict)`).

**restore receipt** (`git diff --stat` over the file printed nothing; the restored lines quoted from `grep -n -A1`):
```
--- git diff --stat (round_driver.py):
--- end diff
6896:    if not (isinstance(live, dict) and live.get("ruling") == "out-of-scope"
6897-            and live.get("source") == "rule"):
```

**raw green** (exit 0), same command:
```
...                                                                      [100%]
3 passed in 33.18s
pytest exit: 0
```

---

## E2: the provenance leg

- **axis:** an unattributed ruling (provenance missing, not a dict, or `ruledBy`/`ruledAt` empty or not a string) exempts nothing

**neutralization** (`plugins/superheroes/lib/round_driver.py`, `_break_it_ruled_exempt`):
```diff
-    if not (isinstance(prov, dict)
+    if False and not (isinstance(prov, dict)
             and all(isinstance(prov.get(f), str) and prov[f].strip() for f in ("ruledBy", "ruledAt"))):
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_edge3_an_unattributed_rule_owes_the_check -q
```

**raw red** (exit 1; all ten rows fail; 40480 bytes, written off-repo to `/private/tmp/claude-501/-Users-zwrose--superheroes-worktrees-superheroes-issue-2072-wo-a/f9907c28-e51a-4615-ac4e-768bdc84522a/scratchpad/e2_red.txt`; the first 40 lines are the header and the `[missing]` failure, the last 16 lines are quoted here):

First lines of the capture:
```
FFFFFFFFFF                                                               [100%]
=================================== FAILURES ===================================
___________ test_edge3_an_unattributed_rule_owes_the_check[missing] ____________

world = <test_break_it_loop.World object at 0x103cdd8e0>, spy = []
provenance = None
```

Decisive error lines, by row (lines 80, 160, 240, 320, 400 of the capture, then the on-axis assertions from line 428):
```
E               KeyError: 'provenance'
E               TypeError: string indices must be integers, not 'str'
E               KeyError: 'ruledBy'
E               KeyError: 'ruledAt'
E               KeyError: 'ruledBy'
E       AssertionError: assert False is True
```
(`[missing]`, `[not-a-dict]`, `[empty]`, `[no-ruledAt]`, `[no-ruledBy]` die building the exempt row from the malformed provenance; `[empty-ruledBy]`, `[empty-ruledAt]`, `[blank-ruledAt]`, `[non-string-ruledBy]`, `[non-string-ruledAt]` fail the assertion, five `AssertionError: assert False is True`.)

Last lines of the capture:
```
E        +    where <function _break_it_kept_step at 0x10555e020> = RD._break_it_kept_step
E        +    and   {'schemaVersion': 5, 'sessionGeneration': 6, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...} = <test_break_it_loop.World object at 0x1054d0350>.state

/path/to/home/.superheroes-worktrees/superheroes/issue-2072-wo-a/plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py:64: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_edge3_an_unattributed_rule_owes_the_check[missing]
FAILED plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_edge3_an_unattributed_rule_owes_the_check[not-a-dict]
FAILED plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_edge3_an_unattributed_rule_owes_the_check[empty]
FAILED plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_edge3_an_unattributed_rule_owes_the_check[no-ruledAt]
FAILED plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_edge3_an_unattributed_rule_owes_the_check[no-ruledBy]
FAILED plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_edge3_an_unattributed_rule_owes_the_check[empty-ruledBy]
FAILED plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_edge3_an_unattributed_rule_owes_the_check[empty-ruledAt]
FAILED plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_edge3_an_unattributed_rule_owes_the_check[blank-ruledAt]
FAILED plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_edge3_an_unattributed_rule_owes_the_check[non-string-ruledBy]
FAILED plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_edge3_an_unattributed_rule_owes_the_check[non-string-ruledAt]
10 failed in 75.68s (0:01:15)
```
(The tail above is the capture's last 16 lines. The command redirected pytest's output to the file and printed `pytest exit: 1` on the terminal, so the exit code is not in the file. The per-row error kinds were read off the saved file with `grep -n`, which shows `KeyError`/`TypeError` at lines 80, 160, 240, 320 and 400, inside the first five rows' sections, and five `AssertionError: assert False is True` lines in the last five.)

**restore:** the inverse edit on `plugins/superheroes/lib/round_driver.py` (`if False and not (isinstance(prov, dict)` back to `if not (isinstance(prov, dict)`).

**restore receipt:**
```
--- git diff --stat (round_driver.py):
--- end diff
6901:    if not (isinstance(prov, dict)
6902-            and all(isinstance(prov.get(f), str) and prov[f].strip() for f in ("ruledBy", "ruledAt"))):
```

**raw green** (exit 0), same command:
```
..........                                                               [100%]
10 passed in 106.81s (0:01:46)
pytest exit: 0
```

---

## E3: the discharge leg

- **axis:** a ruling with no clearing audit exempts nothing; the test must still be kept

**neutralization** (`plugins/superheroes/lib/round_driver.py`, the last statement of `_break_it_ruled_exempt`, so a finding with no clearing audit reads exempt):
```diff
                 return live
-    return None
+    return live
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_edge1_a_rule_with_no_clearing_audit_still_owes_the_check" -q
```

**raw red** (exit 1):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_____ test_edge1_a_rule_with_no_clearing_audit_still_owes_the_check[fixed] _____

world = <test_break_it_loop.World object at 0x102ce1010>, spy = []
disposition = 'fixed'

    @pytest.mark.parametrize("disposition", ["fixed", "out-of-scope"])
    def test_edge1_a_rule_with_no_clearing_audit_still_owes_the_check(world, spy, disposition):
        key = _shape(world, disposition)
        _rule(world, key)
>       _owes_the_check(world, spy)

/path/to/home/.superheroes-worktrees/superheroes/issue-2072-wo-a/plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py:134: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

world = <test_break_it_loop.World object at 0x102ce1010>, spy = []

    def _owes_the_check(world, spy):
        """The kept step ran `check_kept`, found the test absent from head, and parked."""
>       assert RD._break_it_kept_step(world.state, world.state["config"]) is True
E       AssertionError: assert False is True
E        +  where False = <function _break_it_kept_step at 0x102d69ee0>({'schemaVersion': 5, 'sessionGeneration': 6, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...}, {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...})
E        +    where <function _break_it_kept_step at 0x102d69ee0> = RD._break_it_kept_step
E        +    and   {'schemaVersion': 5, 'sessionGeneration': 6, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...} = <test_break_it_loop.World object at 0x102ce1010>.state

/path/to/home/.superheroes-worktrees/superheroes/issue-2072-wo-a/plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py:64: AssertionError
_ test_edge1_a_rule_with_no_clearing_audit_still_owes_the_check[out-of-scope] __

world = <test_break_it_loop.World object at 0x102cf1250>, spy = []
disposition = 'out-of-scope'

    @pytest.mark.parametrize("disposition", ["fixed", "out-of-scope"])
    def test_edge1_a_rule_with_no_clearing_audit_still_owes_the_check(world, spy, disposition):
        key = _shape(world, disposition)
        _rule(world, key)
>       _owes_the_check(world, spy)

/path/to/home/.superheroes-worktrees/superheroes/issue-2072-wo-a/plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py:134: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

world = <test_break_it_loop.World object at 0x102cf1250>, spy = []

    def _owes_the_check(world, spy):
        """The kept step ran `check_kept`, found the test absent from head, and parked."""
>       assert RD._break_it_kept_step(world.state, world.state["config"]) is True
E       AssertionError: assert False is True
E        +  where False = <function _break_it_kept_step at 0x102d69ee0>({'schemaVersion': 5, 'sessionGeneration': 6, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...}, {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...})
E        +    where <function _break_it_kept_step at 0x102d69ee0> = RD._break_it_kept_step
E        +    and   {'schemaVersion': 5, 'sessionGeneration': 6, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...} = <test_break_it_loop.World object at 0x102cf1250>.state

/path/to/home/.superheroes-worktrees/superheroes/issue-2072-wo-a/plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py:64: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_edge1_a_rule_with_no_clearing_audit_still_owes_the_check[fixed]
FAILED plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_edge1_a_rule_with_no_clearing_audit_still_owes_the_check[out-of-scope]
2 failed in 24.19s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_driver.py` (the final `return live` back to `return None`).

**restore receipt** (`git diff --stat` printed nothing; the restored lines quoted from the Read tool, lines 6903-6911):
```
--- git diff --stat (round_driver.py):
--- end diff
        return None
    rounds = state.get("rounds")
    for rec in (rounds.values() if isinstance(rounds, dict) else ()):
        entries = rec.get("audits") if isinstance(rec, dict) else None
        for audit in (entries if isinstance(entries, list) else ()):
            # axis: a ruling with no clearing audit exempts nothing — the test must still be kept — see bite-proof record wo_a_2072_ruled_exempt
            if isinstance(audit, dict) and audit.get("id") == key and audit.get("ruling") in audits._CLEARS:
                return live
    return None
```

**raw green** (exit 0), same command:
```
..                                                                       [100%]
2 passed in 20.26s
pytest exit: 0
```

---

## E4: the out-of-scope routing to the kept check

- **axis:** an out-of-scope disposition owes the kept check like a fixed one unless the exemption holds, never a bare `not-required`

**neutralization** (`plugins/superheroes/lib/round_driver.py`, `_break_it_kept_step`):
```diff
-        if disposition not in ("fixed", "out-of-scope"):
+        if disposition != "fixed":
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_edge1_a_rule_with_no_clearing_audit_still_owes_the_check[out-of-scope]" -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_edge1_a_rule_with_no_clearing_audit_still_owes_the_check[out-of-scope] __

world = <test_break_it_loop.World object at 0x1056ee450>, spy = []
disposition = 'out-of-scope'

    @pytest.mark.parametrize("disposition", ["fixed", "out-of-scope"])
    def test_edge1_a_rule_with_no_clearing_audit_still_owes_the_check(world, spy, disposition):
        key = _shape(world, disposition)
        _rule(world, key)
>       _owes_the_check(world, spy)

/path/to/home/.superheroes-worktrees/superheroes/issue-2072-wo-a/plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py:134: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

world = <test_break_it_loop.World object at 0x1056ee450>, spy = []

    def _owes_the_check(world, spy):
        """The kept step ran `check_kept`, found the test absent from head, and parked."""
>       assert RD._break_it_kept_step(world.state, world.state["config"]) is True
E       AssertionError: assert False is True
E        +  where False = <function _break_it_kept_step at 0x105775ee0>({'schemaVersion': 5, 'sessionGeneration': 6, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...}, {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...})
E        +    where <function _break_it_kept_step at 0x105775ee0> = RD._break_it_kept_step
E        +    and   {'schemaVersion': 5, 'sessionGeneration': 6, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...} = <test_break_it_loop.World object at 0x1056ee450>.state

/path/to/home/.superheroes-worktrees/superheroes/issue-2072-wo-a/plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py:64: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_edge1_a_rule_with_no_clearing_audit_still_owes_the_check[out-of-scope]
1 failed in 10.80s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_driver.py` (`if disposition != "fixed":` back to `if disposition not in ("fixed", "out-of-scope"):`).

**restore receipt:**
```
--- git diff --stat (round_driver.py):
--- end diff
6953:        if disposition not in ("fixed", "out-of-scope"):
```

**raw green** (exit 0), same command:
```
.                                                                        [100%]
1 passed in 12.57s
pytest exit: 0
```

---

## E5: the exemption wiring in `_break_it_kept_step`

- **axis:** the exemption is consulted before `check_kept`; without it a ruled-out-of-scope, discharged test parks

**neutralization** (`plugins/superheroes/lib/round_driver.py`, `_break_it_kept_step`):
```diff
-        ruled = _break_it_ruled_exempt(state, key)
+        ruled = None
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_a_ruled_out_of_scope_and_discharged_test_is_exempt_from_the_kept_check plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_the_exempt_finding_lets_the_terminal_converge -q
```

**raw red** (exit 1):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_a_ruled_out_of_scope_and_discharged_test_is_exempt_from_the_kept_check __

world = <test_break_it_loop.World object at 0x106a9bc20>
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x106a9b9b0>

    def test_a_ruled_out_of_scope_and_discharged_test_is_exempt_from_the_kept_check(world, monkeypatch):
        key = _shape(world)
        _rule(world, key)
        _audit(world, key)
    
        def never(*args, **kwargs):
            raise AssertionError("check_kept ran for an exempt finding")
    
        monkeypatch.setattr(break_it, "check_kept", never)
>       assert RD._break_it_kept_step(world.state, world.state["config"]) is False
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/path/to/home/.superheroes-worktrees/superheroes/issue-2072-wo-a/plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py:81: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/path/to/home/.superheroes-worktrees/superheroes/issue-2072-wo-a/plugins/superheroes/lib/round_driver.py:6964: in _break_it_kept_step
    got = break_it.check_kept(config.get("repoRoot"), config.get("baseRef"), head, run,
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

args = ('/private/tmp/claude-501/pytest-of-zwrose/pytest-294/test_a_ruled_out_of_scope_and_0/repo', 'c873de8e426030e45baba9cc..._charge_once.py', 'command': '/path/to/home/.cache/uv/builds-v0/.tmpePJJ4g/bin/python tests/test_charge_once.py', ...})
kwargs = {'interpreter': '/path/to/home/.cache/uv/builds-v0/.tmpePJJ4g/bin/python'}

    def never(*args, **kwargs):
>       raise AssertionError("check_kept ran for an exempt finding")
E       AssertionError: check_kept ran for an exempt finding

/path/to/home/.superheroes-worktrees/superheroes/issue-2072-wo-a/plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py:78: AssertionError
______________ test_the_exempt_finding_lets_the_terminal_converge ______________

world = <test_break_it_loop.World object at 0x106ba97f0>
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x106aa6300>

    def test_the_exempt_finding_lets_the_terminal_converge(world, monkeypatch):
        key = _shape(world)
        _rule(world, key)
        _audit(world, key, "discharged-but-new-issue")
        monkeypatch.setattr(break_it, "check_kept", lambda *a, **k: pytest.fail("check_kept ran"))
>       RD._terminal_converged(world.state, world.state["config"], full_panel=True)

/path/to/home/.superheroes-worktrees/superheroes/issue-2072-wo-a/plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py:94: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/path/to/home/.superheroes-worktrees/superheroes/issue-2072-wo-a/plugins/superheroes/lib/round_driver.py:7007: in _terminal_converged
    if _break_it_kept_step(state, config):
       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/path/to/home/.superheroes-worktrees/superheroes/issue-2072-wo-a/plugins/superheroes/lib/round_driver.py:6964: in _break_it_kept_step
    got = break_it.check_kept(config.get("repoRoot"), config.get("baseRef"), head, run,
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

a = ('/private/tmp/claude-501/pytest-of-zwrose/pytest-294/test_the_exempt_finding_lets_t0/repo', 'ad5fc089eb291d1576e7b40d..._charge_once.py', 'command': '/path/to/home/.cache/uv/builds-v0/.tmpePJJ4g/bin/python tests/test_charge_once.py', ...})
k = {'interpreter': '/path/to/home/.cache/uv/builds-v0/.tmpePJJ4g/bin/python'}

>   monkeypatch.setattr(break_it, "check_kept", lambda *a, **k: pytest.fail("check_kept ran"))
                                                                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   Failed: check_kept ran

/path/to/home/.superheroes-worktrees/superheroes/issue-2072-wo-a/plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py:93: Failed
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_a_ruled_out_of_scope_and_discharged_test_is_exempt_from_the_kept_check
FAILED plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_the_exempt_finding_lets_the_terminal_converge
2 failed in 28.39s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_driver.py` (`ruled = None` back to `ruled = _break_it_ruled_exempt(state, key)`).

**restore receipt:**
```
--- git diff --stat (round_driver.py):
--- end diff
6958:        ruled = _break_it_ruled_exempt(state, key)
```

**raw green** (exit 0), same command:
```
..                                                                       [100%]
2 passed in 22.14s
pytest exit: 0
```

---

## E6: the record label in `review_record_session._decide`

- **axis:** a fixed finding the driver ruled out of scope reads `ruling` in the review record, never "fixed and audited"

**neutralization** (`plugins/superheroes/lib/review_record_session.py`, `_decide`):
```diff
-    if disp == "fixed" and isinstance(held, dict):
+    if False and disp == "fixed" and isinstance(held, dict):
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_the_review_record_labels_the_exempt_finding_ruling_never_fixed -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_the_review_record_labels_the_exempt_finding_ruling_never_fixed ______

world = <test_break_it_loop.World object at 0x104abe900>
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x104abe4b0>

    def test_the_review_record_labels_the_exempt_finding_ruling_never_fixed(world, monkeypatch):
        key = _shape(world)
        _rule(world, key)
        _audit(world, key)
        monkeypatch.setattr(break_it, "check_kept", lambda *a, **k: pytest.fail("check_kept ran"))
        assert RD._break_it_kept_step(world.state, world.state["config"]) is False
        findings, _merged = RRS._findings_and_merges(world.state)
        (got,) = [f for f in findings if f["findingKey"] == key]
>       assert got["outcome"] == "ruling"
E       AssertionError: assert 'fixed' == 'ruling'
E         
E         - ruling
E         + fixed

/path/to/home/.superheroes-worktrees/superheroes/issue-2072-wo-a/plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py:107: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_the_review_record_labels_the_exempt_finding_ruling_never_fixed
1 failed in 12.56s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/review_record_session.py` (`if False and disp == "fixed" and isinstance(held, dict):` back to `if disp == "fixed" and isinstance(held, dict):`).

**restore receipt:**
```
--- git diff --stat (review_record_session.py):
--- end diff
422:    if disp == "fixed" and isinstance(held, dict):
```

**raw green** (exit 0), same command:
```
.                                                                        [100%]
1 passed in 13.51s
pytest exit: 0
```

---

## E7: the receipt disclosure filter

- **axis:** a `ruled-out-of-scope` row is not listed as a fixed break-it test the final change failed to hold

**neutralization** (`plugins/superheroes/lib/receipt_disclosures.py`, `build_degraded_prose`):
```diff
-            not_kept = [r for r in bik if r.get("outcome") not in ("kept", "not-required", "ruled-out-of-scope")]
+            not_kept = [r for r in bik if r.get("outcome") not in ("kept", "not-required")]
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_the_receipt_disclosure_does_not_list_a_ruled_out_of_scope_row_as_not_kept -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_the_receipt_disclosure_does_not_list_a_ruled_out_of_scope_row_as_not_kept _

    def test_the_receipt_disclosure_does_not_list_a_ruled_out_of_scope_row_as_not_kept():
        exempt = {"findingKey": "k", "path": "tests/t.py", "outcome": "ruled-out-of-scope"}
>       assert not [line for line in _degraded_for([exempt]) if "break-it-test-not-kept" in line]
E       AssertionError: assert not ['break-it-test-not-kept (round 1): 1 fixed break-it test(s) not held in the final change (tests/t.py: ruled-out-of-scope) — certification withheld']

/path/to/home/.superheroes-worktrees/superheroes/issue-2072-wo-a/plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py:122: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_ruled_exempt_2072.py::test_the_receipt_disclosure_does_not_list_a_ruled_out_of_scope_row_as_not_kept
1 failed in 2.04s
pytest exit: 1
```

**restore:** the inverse edit on `plugins/superheroes/lib/receipt_disclosures.py` (the tuple back to `("kept", "not-required", "ruled-out-of-scope")`).

**restore receipt:**
```
--- git diff --stat (receipt_disclosures.py):
--- end diff
695:            not_kept = [r for r in bik if r.get("outcome") not in ("kept", "not-required", "ruled-out-of-scope")]
```
After E7 a `git status --porcelain` over the worktree printed nothing.

**raw green** (exit 0), same command:
```
.                                                                        [100%]
1 passed in 2.09s
pytest exit: 0
```
