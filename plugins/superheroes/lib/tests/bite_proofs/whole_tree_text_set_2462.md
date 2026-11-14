# #2462 bite-proof — the whole-tree text test set and its census

**Provenance:** claude (implementer), work order WO-1. Worktree `/home/user/wt-2462`, branch `claude/issue-2462-build`, base `37965f6ccb3b7692ff4ada85af4578c5de58f410`.
The detector is `plugins/superheroes/lib/tests/test_whole_tree_text_set.py`, unedited in every run below. Every run is `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest "<node id>" -q` from the worktree root, on the single node named in each entry.
Each neutralization is one targeted Edit, undone by the inverse Edit; the restore receipt is the restored text quoted back plus the green run of the same node.
Captures are far under the 32 KiB / 128 KiB ceilings. Nothing was redacted (no credential-like text appears). Dropped from every capture: the `UV_NATIVE_TLS` deprecation warning line, shown once per run; the runs are otherwise shown whole.

## Guarded elements (declared in WO-1) and how they are covered

| ID | Guarded element (axis) | Neutralized at | Detector node |
|---|---|---|---|
| G1 | a reader missing from the set: a test file that reads plugin Markdown by pattern and is in neither the argument file nor `EXEMPT` | `plugins/superheroes/lib/tests/whole-tree-text-tests.txt`, the line for `test_invocation_hygiene.py` | `test_whole_tree_text_set.py::test_every_candidate_is_a_member_or_exempt` |
| G2 | a new enumeration in an exempt file: an exempt file's current normalised enumeration lines equal the tuple it was reviewed against | `plugins/superheroes/lib/tests/test_pilot_c10_census.py`, `_discovered_pilot_conformance_modules` | `test_whole_tree_text_set.py::test_exempt_enumeration_lines_are_pinned` |

Two elements, two neutralizations, two reds. None grouped, none unproven. The axis line for each sits in the detector's docstring.

## G1 — a reader missing from the set

**neutralization** (`whole-tree-text-tests.txt`, line 11, one Edit):
```diff
 plugins/superheroes/lib/tests/test_heartbeat_docs_drift.py
-plugins/superheroes/lib/tests/test_invocation_hygiene.py
 plugins/superheroes/lib/tests/test_model_tier_wiring.py
```
**raw red** (`::test_every_candidate_is_a_member_or_exempt`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_every_candidate_is_a_member_or_exempt __________________
plugins/superheroes/lib/tests/test_invocation_hygiene.py reads plugin Markdown by pattern (enumeration lines: ['for dirpath, _dirs, files in os.walk(base):']) and is in neither the set nor EXEMPT: add it to plugins/superheroes/lib/tests/whole-tree-text-tests.txt, or, if it does not read plugin Markdown by pattern, add it to EXEMPT with a reason and its enumeration lines.
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_whole_tree_text_set.py::test_every_candidate_is_a_member_or_exempt
1 failed in 8.33s
```
Failing line: the message names `plugins/superheroes/lib/tests/test_invocation_hygiene.py` and says to add it to the argument file or to `EXEMPT`. The red is on the claimed axis (membership), not on a parse error: the argument file stayed well formed (sorted, no duplicate, every path present), so the `arg_errors` leg did not fire.
**restore:** the inverse Edit, putting the deleted line back between its two neighbours. **restore receipt:** lines 10-12 of the argument file quoted back:
```
10:plugins/superheroes/lib/tests/test_heartbeat_docs_drift.py
11:plugins/superheroes/lib/tests/test_invocation_hygiene.py
12:plugins/superheroes/lib/tests/test_model_tier_wiring.py
```
**raw green** (same node):
```
.                                                                        [100%]
1 passed in 7.63s
```
Pass line: `1 passed in 7.63s`.

## G2 — a new enumeration in an exempt file

**neutralization** (`plugins/superheroes/lib/tests/test_pilot_c10_census.py`, `_discovered_pilot_conformance_modules`, one Edit; the file is an `EXEMPT` entry whose recorded tuple is the one `glob.glob(...)` line):
```diff
 def _discovered_pilot_conformance_modules():
     paths = sorted(glob.glob(os.path.join(_LIB, "pilot_conformance*.py")))
+    _unused = os.listdir(os.path.dirname(__file__))
     return {os.path.splitext(os.path.basename(path))[0] for path in paths}
```
**raw red** (`::test_exempt_enumeration_lines_are_pinned`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_exempt_enumeration_lines_are_pinned ___________________
plugins/superheroes/lib/tests/test_pilot_c10_census.py: the exempt file's enumeration changed; re-review whether it now reads plugin Markdown by pattern, then update its entry or move it to the set. recorded: ['paths = sorted(glob.glob(os.path.join(_LIB, "pilot_conformance*.py")))']; current: ['paths = sorted(glob.glob(os.path.join(_LIB, "pilot_conformance*.py")))', '_unused = os.listdir(os.path.dirname(__file__))']
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_whole_tree_text_set.py::test_exempt_enumeration_lines_are_pinned
1 failed in 7.48s
```
Failing line: the message names `test_pilot_c10_census.py`, quotes the recorded and the current tuple, and says to re-review. The red is on the claimed axis (the pin), not on staleness: the file is still a candidate, so the stale-entry node is unaffected.
**restore:** the inverse Edit, removing the added `_unused = ...` line. **restore receipt:** the restored lines quoted back, from `grep -n` of the function:
```
113:def _discovered_pilot_conformance_modules():
114:    paths = sorted(glob.glob(os.path.join(_LIB, "pilot_conformance*.py")))
115:    return {os.path.splitext(os.path.basename(path))[0] for path in paths}
```
`git status --porcelain -- plugins/superheroes/lib/tests/test_pilot_c10_census.py` lists nothing (the file does not differ from the committed tree).
**raw green** (same node):
```
.                                                                        [100%]
1 passed in 7.53s
```
Pass line: `1 passed in 7.53s`.
