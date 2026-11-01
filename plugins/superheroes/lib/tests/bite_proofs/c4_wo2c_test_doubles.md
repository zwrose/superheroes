# C4 WO-2C bite-proof — the sweep-template test in `test_claude_md_path_1965.py`

**Provenance:** claude (implementer), work order WO-2C. Detector: `plugins/superheroes/lib/tests/test_claude_md_path_1965.py::test_sweep_is_an_order_phase_whose_template_has_no_bare_claude_md_slot`.
Worktree `/home/user/sh-2305`, branch `claude/issue-2305-workhorse-rq185r`, base commit `955d962b`.
Every run is `timeout 900 scripts/pinned-python -B -X pycache_prefix=/tmp/sh2305-pyc -m pytest "<node id>" -q` from the worktree, the detector
unedited, on the single node above. Each neutralization is one targeted Edit, undone by the inverse Edit; the restore receipt is the restored
lines quoted back plus `git status --porcelain` over the neutralized paths (empty). Captures are far under the 32 KiB / 128 KiB ceilings.
Nothing was redacted (no credential-like text appears). The `UV_NATIVE_TLS` deprecation warning line, shown once per run, is omitted below.

## Guarded elements (declared in WO-2C)

| ID | Guarded element (axis) | File : site | Detector node |
|---|---|---|---|
| t1 | the sweep stays an order phase (`RP.P_SWEEP in RO.ORDER_PHASES`) | `round_orders.py` `ORDER_PHASES` | the node above, first assertion |
| t2 | the sweep template carries no bare `CLAUDE.md` slot (`_BARE_SLOT`) | `rubric/orders/dispatch-sweep.md` | the node above, second assertion |

## t1 — the sweep stays an order phase

**neutralization** (`round_orders.py`, `ORDER_PHASES`):
```diff
     round_phases.P_SCOPED,
-    round_phases.P_SWEEP,
 )
```
**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_sweep_is_an_order_phase_whose_template_has_no_bare_claude_md_slot ____

    def test_sweep_is_an_order_phase_whose_template_has_no_bare_claude_md_slot():
        # axis: the sweep stays a real order phase (t1) and its searcher template names no bare CLAUDE.md (t2)
        # — see bite-proof record c4_wo2c_test_doubles
>       assert RP.P_SWEEP in RO.ORDER_PHASES
E       AssertionError: assert 'dispatch-sweep' in ('dispatch-panel', 'dispatch-verifiers', 'dispatch-synthesis', 'dispatch-seams-check', 'dispatch-second-test', 'dispatch-audits', ...)
E        +  where 'dispatch-sweep' = RP.P_SWEEP
E        +  and   ('dispatch-panel', 'dispatch-verifiers', 'dispatch-synthesis', 'dispatch-seams-check', 'dispatch-second-test', 'dispatch-audits', ...) = RO.ORDER_PHASES

/home/user/sh-2305/plugins/superheroes/lib/tests/test_claude_md_path_1965.py:59: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_claude_md_path_1965.py::test_sweep_is_an_order_phase_whose_template_has_no_bare_claude_md_slot
1 failed in 5.12s
```
**restore:** the inverse Edit re-added `    round_phases.P_SWEEP,` after `    round_phases.P_SCOPED,`.
**restore receipt:** `plugins/superheroes/lib/round_orders.py` lines 69–72 read back as `round_phases.P_AUDITS,` / `round_phases.P_SCOPED,` / `round_phases.P_SWEEP,` / `)`;
`git status --porcelain` over the file is empty.
**raw green:** no separate t1-only green run was spent (the order's 4-run bite-proof was spent as t1 red, t2 red, t2 green, and the t2 red
run is the t1-restored evidence). With t1 restored and t2 neutralized, the t2 red run below passed the first assertion
(`assert RP.P_SWEEP in RO.ORDER_PHASES`) and failed only at the second; the t2 green run below is the full node green with both restored.

## t2 — no bare CLAUDE.md slot

**neutralization** (`rubric/orders/dispatch-sweep.md`, after the `Verification root` line):
```diff
 - Verification root (read the listed files here ONLY): {{VERIFICATION_ROOT}}
+- Project conventions: CLAUDE.md
```
**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_sweep_is_an_order_phase_whose_template_has_no_bare_claude_md_slot ____

    def test_sweep_is_an_order_phase_whose_template_has_no_bare_claude_md_slot():
        # axis: the sweep stays a real order phase (t1) and its searcher template names no bare CLAUDE.md (t2)
        # — see bite-proof record c4_wo2c_test_doubles
        assert RP.P_SWEEP in RO.ORDER_PHASES
        bare = [line for line in _template(RP.P_SWEEP).splitlines() if _BARE_SLOT.search(line)]
>       assert bare == [], "%s names CLAUDE.md as a bare relative path: %r" % (RP.P_SWEEP, bare)
E       AssertionError: dispatch-sweep names CLAUDE.md as a bare relative path: ['- Project conventions: CLAUDE.md']
E       assert ['- Project c...s: CLAUDE.md'] == []
E         
E         Left contains one more item: '- Project conventions: CLAUDE.md'
E         Use -v to get more diff

/home/user/sh-2305/plugins/superheroes/lib/tests/test_claude_md_path_1965.py:61: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_claude_md_path_1965.py::test_sweep_is_an_order_phase_whose_template_has_no_bare_claude_md_slot
1 failed in 0.38s
```
**restore:** the inverse Edit removed the added `- Project conventions: CLAUDE.md` line.
**restore receipt:** `rubric/orders/dispatch-sweep.md` lines 4–7 read back as `## Input` / `- Your search (...` / `  of files you search): {{SEARCH_INPUT_PATH}}` /
`- Verification root (read the listed files here ONLY): {{VERIFICATION_ROOT}}`; `git status --porcelain -- plugins/` lists only the four test files, neither shipped file.
**raw green:**
```
.                                                                        [100%]
1 passed in 0.28s
```
