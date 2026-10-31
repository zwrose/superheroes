# C2 WO-3 bite-proof — the seams check replaces the gap sweep; the folder split goes

**Provenance:** claude / sonnet-5.5 (implementer). Detector file: `plugins/superheroes/lib/tests/test_seams_check_c2.py`. Neutralized files: `plugins/superheroes/lib/round_driver.py` (E1–E4) and `plugins/superheroes/skills/review-code/reference/round-driver.md` (E5).

Declared guarded-element set (from the order): E1–E5. Each was neutralized by one targeted `Edit` (never a whole-file rewrite, never `git checkout`/`restore`/`stash`), the proving node was run alone with `-k` and `-v` (unfiltered), and the neutralization was undone by the inverse `Edit`. To stay inside the order's command budget the runs are chained: each run after the first selects the element's own node plus the previous element's node, so the previous element's green half (post-restore) is the `PASSED` line in the next element's run, and a last full-file run closes the chain. That is six runs where the order sketched ten. Redaction: none needed (no secrets, tokens or URLs in any output); the pytest temp path is left as printed.

## Disclosure that applies to E5's green half

The order's rule that the old `rubric/orders/dispatch-gap-sweep.md` and its golden are deleted could not be carried out: the `git rm` command naming them was held for approval and never answered (a refusal, recorded in the return; not retried in another form). So the old template is still on disk, and the census test (E5) is red on that file alone in every run, before and after the neutralization. E5's red therefore shows **two** hits (the stale template and the injected doc sentence) and its green half is **not green**: it fails on the stale template only. That is a failing green half, reported word for word below, and it clears when the orchestrator runs the deletion. E1–E4 are unaffected.

## E1 — `_after_panel_findings`' round-1 test

- **axis:** a later round of a sliced change never enters the seams check (the `state["round"] == 1` clause).
- **neutralization** (`plugins/superheroes/lib/round_driver.py`), dropping the clause:
```diff
-    if _round_is_sliced(state) and state["round"] == 1 and not state.get("_seamsChecked"):
+    if _round_is_sliced(state) and not state.get("_seamsChecked"):
```
- **raw red** (`pytest ... -k test_a_later_round_of_a_sliced_change_never_enters_the_seams_check -v`, exit 1):
```
collecting ... collected 19 items / 18 deselected / 1 selected

plugins/superheroes/lib/tests/test_seams_check_c2.py::test_a_later_round_of_a_sliced_change_never_enters_the_seams_check FAILED [100%]

=================================== FAILURES ===================================
______ test_a_later_round_of_a_sliced_change_never_enters_the_seams_check ______

    def test_a_later_round_of_a_sliced_change_never_enters_the_seams_check():
        state = _round_one_state(SLICE_PLAN)
        state["round"] = 2
        staged, _drops = RD.mechanical_compile([_finding("later", "a.py")], DIFF)
        RD._after_panel_findings(state, state["config"], staged)
>       assert state["step"] == RD.P_VERIFIERS
E       AssertionError: assert 'dispatch-seams-check' == 'dispatch-verifiers'
E         
E         - dispatch-verifiers
E         + dispatch-seams-check

/home/user/wt-2218-wo3/plugins/superheroes/lib/tests/test_seams_check_c2.py:125: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seams_check_c2.py::test_a_later_round_of_a_sliced_change_never_enters_the_seams_check
======================= 1 failed, 18 deselected in 2.02s =======================
```
- **restore:** inverse `Edit` (the `state["round"] == 1 and` clause put back).
- **restore receipt** (restored line quoted back, as it stands in `round_driver.py`):
```
    if _round_is_sliced(state) and state["round"] == 1 and not state.get("_seamsChecked"):
```
  `git diff --stat` of `round_driver.py` cannot isolate the restore, since the file also carries the intended whole change of this order (227 lines in the run after the restore); the quoted line is the receipt.
- **raw green** (the `PASSED` line of the next run, E2's run):
```
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_a_later_round_of_a_sliced_change_never_enters_the_seams_check PASSED [100%]
```

## E2 — the `_seamsChecked` once-flag

- **axis:** the seams check runs once; re-entering round 1 after it goes to the verifiers.
- **neutralization** (`plugins/superheroes/lib/round_driver.py`), not setting the flag:
```diff
     if _round_is_sliced(state) and state["round"] == 1 and not state.get("_seamsChecked"):
-        state["_seamsChecked"] = True
+        pass
         state["_panelStaged"] = staged
```
- **raw red** (`-k "test_after_the_seams_check_re_entering_round_one_goes_straight_to_the_verifiers or test_a_later_round_of_a_sliced_change_never_enters_the_seams_check" -v`, exit 1; preceded by `git diff --stat -- plugins/superheroes/lib/round_driver.py` printing `1 file changed, 143 insertions(+), 84 deletions(-)` for the whole intended change plus this neutralization):
```
collecting ... collected 19 items / 17 deselected / 2 selected

plugins/superheroes/lib/tests/test_seams_check_c2.py::test_after_the_seams_check_re_entering_round_one_goes_straight_to_the_verifiers FAILED [ 50%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_a_later_round_of_a_sliced_change_never_enters_the_seams_check PASSED [100%]

=================================== FAILURES ===================================
_ test_after_the_seams_check_re_entering_round_one_goes_straight_to_the_verifiers _

    def test_after_the_seams_check_re_entering_round_one_goes_straight_to_the_verifiers():
        state = _round_one_state(SLICE_PLAN)
        _fold_panel_with(state, _finding("panel bug", "a.py"))
        RD._fold(state, state["config"], RD.P_SEAMS, {"findings": []})
        staged, _drops = RD.mechanical_compile([_finding("another", "b.py")], DIFF)
        state["step"] = RD.P_PANEL
        RD._after_panel_findings(state, state["config"], staged)
>       assert state["step"] == RD.P_VERIFIERS
E       AssertionError: assert 'dispatch-seams-check' == 'dispatch-verifiers'
E         
E         - dispatch-verifiers
E         + dispatch-seams-check

/home/user/wt-2218-wo3/plugins/superheroes/lib/tests/test_seams_check_c2.py:116: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seams_check_c2.py::test_after_the_seams_check_re_entering_round_one_goes_straight_to_the_verifiers
================== 1 failed, 1 passed, 17 deselected in 1.91s ==================
```
  (The `PASSED` line is E1's green half.)
- **restore:** inverse `Edit` (`pass` replaced by the assignment).
- **restore receipt** (restored lines quoted back):
```
    if _round_is_sliced(state) and state["round"] == 1 and not state.get("_seamsChecked"):
        state["_seamsChecked"] = True
        state["_panelStaged"] = staged
```
- **raw green** (the `PASSED` line of the next run, E3's run):
```
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_after_the_seams_check_re_entering_round_one_goes_straight_to_the_verifiers PASSED [ 20%]
```

## E3 — `_round_is_sliced`

- **axis:** an unsliced change (no plan, `sliced` not `True`, a plan that is not a dict) never enters the seams check.
- **neutralization** (`plugins/superheroes/lib/round_driver.py`), returning `True` always:
```diff
     plan = state.get("slicePlan")
-    return isinstance(plan, dict) and plan.get("sliced") is True
+    return True
```
- **raw red** (`-k "test_an_unsliced_round_one_never_enters_the_seams_check or test_after_the_seams_check_re_entering_round_one_goes_straight_to_the_verifiers" -v`, exit 1; the four failure bodies are identical but for the parameter, one is quoted and the other three listed):
```
collecting ... collected 19 items / 14 deselected / 5 selected

plugins/superheroes/lib/tests/test_seams_check_c2.py::test_after_the_seams_check_re_entering_round_one_goes_straight_to_the_verifiers PASSED [ 20%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_an_unsliced_round_one_never_enters_the_seams_check[no-plan] FAILED [ 40%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_an_unsliced_round_one_never_enters_the_seams_check[not-sliced] FAILED [ 60%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_an_unsliced_round_one_never_enters_the_seams_check[sliced-not-true] FAILED [ 80%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_an_unsliced_round_one_never_enters_the_seams_check[not-a-dict] FAILED [100%]

=================================== FAILURES ===================================
_______ test_an_unsliced_round_one_never_enters_the_seams_check[no-plan] _______

plan = None

    @pytest.mark.parametrize("plan", [None, {"sliced": False, "slices": []}, {"sliced": "yes", "slices": []}, "junk"],
                             ids=["no-plan", "not-sliced", "sliced-not-true", "not-a-dict"])
    def test_an_unsliced_round_one_never_enters_the_seams_check(plan):
        state = _round_one_state()
        if plan is not None:
            state["slicePlan"] = plan
>       assert RD._round_is_sliced(state) is False
E       AssertionError: assert True is False
E        +  where True = <function _round_is_sliced at 0x7f868e29aac0>({'schemaVersion': 5, 'sessionGeneration': 7, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...})
E        +    where <function _round_is_sliced at 0x7f868e29aac0> = RD._round_is_sliced

/home/user/wt-2218-wo3/plugins/superheroes/lib/tests/test_seams_check_c2.py:155: AssertionError
[... the [not-sliced], [sliced-not-true] and [not-a-dict] bodies repeat this one with plan = {'sliced': False, 'slices': []}, {'sliced': 'yes', 'slices': []} and 'junk'; elided here: three near-identical blocks ...]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seams_check_c2.py::test_an_unsliced_round_one_never_enters_the_seams_check[no-plan]
FAILED plugins/superheroes/lib/tests/test_seams_check_c2.py::test_an_unsliced_round_one_never_enters_the_seams_check[not-sliced]
FAILED plugins/superheroes/lib/tests/test_seams_check_c2.py::test_an_unsliced_round_one_never_enters_the_seams_check[sliced-not-true]
FAILED plugins/superheroes/lib/tests/test_seams_check_c2.py::test_an_unsliced_round_one_never_enters_the_seams_check[not-a-dict]
================== 4 failed, 1 passed, 14 deselected in 1.74s ==================
```
  (The first `PASSED` line is E2's green half.)
- **restore:** inverse `Edit`.
- **restore receipt** (restored lines quoted back):
```
    plan = state.get("slicePlan")
    return isinstance(plan, dict) and plan.get("sliced") is True
```
- **raw green** (the four `PASSED` lines of the next run, E4's run):
```
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_an_unsliced_round_one_never_enters_the_seams_check[no-plan] PASSED [ 16%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_an_unsliced_round_one_never_enters_the_seams_check[not-sliced] PASSED [ 33%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_an_unsliced_round_one_never_enters_the_seams_check[sliced-not-true] PASSED [ 50%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_an_unsliced_round_one_never_enters_the_seams_check[not-a-dict] PASSED [ 66%]
```

## E4 — the saved-state handler for the removed step

- **axis:** a current-generation session saved at the removed step (as its step, or only as its pending action and phase) continues past it, with the decision recorded.
- **neutralization** (`plugins/superheroes/lib/round_driver.py`, in `_commit_recover_or_refuse`), skipping the handler's call:
```diff
-    _drop_saved_extra_pass(session_dir, cmd)
+    # _drop_saved_extra_pass(session_dir, cmd)
     _hand_back_retired_gate(session_dir, cmd)
```
- **raw red** (`-k "test_a_current_generation_session_saved_at_the_retired_step_continues_past_it or test_an_unsliced_round_one_never_enters_the_seams_check" -v`, exit 1):
```
collecting ... collected 19 items / 13 deselected / 6 selected

plugins/superheroes/lib/tests/test_seams_check_c2.py::test_an_unsliced_round_one_never_enters_the_seams_check[no-plan] PASSED [ 16%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_an_unsliced_round_one_never_enters_the_seams_check[not-sliced] PASSED [ 33%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_an_unsliced_round_one_never_enters_the_seams_check[sliced-not-true] PASSED [ 50%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_an_unsliced_round_one_never_enters_the_seams_check[not-a-dict] PASSED [ 66%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_a_current_generation_session_saved_at_the_retired_step_continues_past_it[step] FAILED [ 83%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_a_current_generation_session_saved_at_the_retired_step_continues_past_it[pending] FAILED [100%]

=================================== FAILURES ===================================
_ test_a_current_generation_session_saved_at_the_retired_step_continues_past_it[step] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-20/test_a_current_generation_sess0')
where = 'step'

    @pytest.mark.parametrize("where", ["step", "pending"])
    def test_a_current_generation_session_saved_at_the_retired_step_continues_past_it(tmp_path, where):
        session_dir = _saved_at_retired_step(tmp_path, where)
        assert RD._commit_recover_or_refuse(session_dir, "next") is None
        ok, state = RD.load_state(session_dir)
        assert ok, state
        pending = state.get("pending") if isinstance(state.get("pending"), dict) else {}
>       assert RETIRED_STEP not in (state.get("step"), pending.get("action"), pending.get("phase"))
E       AssertionError: assert 'dispatch-gap-sweep' not in ('dispatch-gap-sweep', None, None)

/home/user/wt-2218-wo3/plugins/superheroes/lib/tests/test_seams_check_c2.py:243: AssertionError
_ test_a_current_generation_session_saved_at_the_retired_step_continues_past_it[pending] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-20/test_a_current_generation_sess1')
where = 'pending'

    @pytest.mark.parametrize("where", ["step", "pending"])
    def test_a_current_generation_session_saved_at_the_retired_step_continues_past_it(tmp_path, where):
        session_dir = _saved_at_retired_step(tmp_path, where)
        assert RD._commit_recover_or_refuse(session_dir, "next") is None
        ok, state = RD.load_state(session_dir)
        assert ok, state
        pending = state.get("pending") if isinstance(state.get("pending"), dict) else {}
>       assert RETIRED_STEP not in (state.get("step"), pending.get("action"), pending.get("phase"))
E       AssertionError: assert 'dispatch-gap-sweep' not in ('dispatch-verifiers', 'dispatch-gap-sweep', 'dispatch-gap-sweep')

/home/user/wt-2218-wo3/plugins/superheroes/lib/tests/test_seams_check_c2.py:243: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seams_check_c2.py::test_a_current_generation_session_saved_at_the_retired_step_continues_past_it[step]
FAILED plugins/superheroes/lib/tests/test_seams_check_c2.py::test_a_current_generation_session_saved_at_the_retired_step_continues_past_it[pending]
================== 2 failed, 4 passed, 13 deselected in 1.60s ==================
```
  (The four `PASSED` lines are E3's green half.)
- **restore:** inverse `Edit` (the leading `# ` removed).
- **restore receipt** (restored lines quoted back):
```
    _drop_saved_extra_pass(session_dir, cmd)
    _hand_back_retired_gate(session_dir, cmd)
```
- **raw green** (the two `PASSED` lines of the next run, E5's run):
```
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_a_current_generation_session_saved_at_the_retired_step_continues_past_it[step] PASSED [ 33%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_a_current_generation_session_saved_at_the_retired_step_continues_past_it[pending] PASSED [ 66%]
```

## E5 — the census test

- **axis:** no shipped library module, order template or review-code doc names the retired pass or the folder split.
- **neutralization** (`plugins/superheroes/skills/review-code/reference/round-driver.md`), putting the retired name back into one sentence:
```diff
-folds synthesis, the seams check, or the scoped finder
+folds synthesis, the gap sweep, or the scoped finder
```
- **raw red** (`-k "test_no_shipped_library or test_a_current_generation_session_saved_at_the_retired_step_continues_past_it" -v`, exit 1). Two hits: the second is the injected sentence, the first is the stale template described in the disclosure at the top:
```
collecting ... collected 19 items / 16 deselected / 3 selected

plugins/superheroes/lib/tests/test_seams_check_c2.py::test_a_current_generation_session_saved_at_the_retired_step_continues_past_it[step] PASSED [ 33%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_a_current_generation_session_saved_at_the_retired_step_continues_past_it[pending] PASSED [ 66%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_no_shipped_library_module_order_template_or_review_code_doc_names_the_retired_pass_or_the_folder_split FAILED [100%]

=================================== FAILURES ===================================
_ test_no_shipped_library_module_order_template_or_review_code_doc_names_the_retired_pass_or_the_folder_split _

    def test_no_shipped_library_module_order_template_or_review_code_doc_names_the_retired_pass_or_the_folder_split():
        found = []
        for rel in _shipped_files():
            with open(os.path.join(_PLUGIN_ROOT, rel), encoding="utf-8") as fh:
                text = fh.read()
            if rel in _NAMES_RETIRED_PASS:
                for token in _RETIRED_TOKENS:
                    text = text.replace(token, "")
            found.extend("%s: %s" % (rel, m.group(0)) for m in _CENSUS.finditer(text))
>       assert not found, "the retired names are still in shipped text:\n" + "\n".join(found)
E       AssertionError: the retired names are still in shipped text:
E         rubric/orders/dispatch-gap-sweep.md: gap-sweep
E         skills/review-code/reference/round-driver.md: gap sweep
E       assert not ['rubric/orders/dispatch-gap-sweep.md: gap-sweep', 'skills/review-code/reference/round-driver.md: gap sweep']

/home/user/wt-2218-wo3/plugins/superheroes/lib/tests/test_seams_check_c2.py:290: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seams_check_c2.py::test_no_shipped_library_module_order_template_or_review_code_doc_names_the_retired_pass_or_the_folder_split
================== 1 failed, 2 passed, 16 deselected in 2.26s ==================
```
  (The two `PASSED` lines are E4's green half.) The same node, before the neutralization, printed one hit (the stale template only): `1 failed, 43 passed` for `test_seams_check_c2.py` plus `test_delta_surface.py`.
- **restore:** inverse `Edit`.
- **restore receipt** (restored text quoted back, and `git diff --stat` printed in the final run's command):
```
folds synthesis, the seams check, or the scoped finder
```
```
 plugins/superheroes/lib/round_driver.py            | 227 +++++++++++++--------
 .../skills/review-code/reference/round-driver.md   |  28 +--
 2 files changed, 157 insertions(+), 98 deletions(-)
```
  (Both files carry the order's whole intended change; the quoted sentence is the restore receipt.)
- **raw green** — the full-file run after all restores (`pytest plugins/superheroes/lib/tests/test_seams_check_c2.py -v`, exit 1). Eighteen nodes pass; the census node still fails, for the stale template alone. This is a failing green half, reported as it printed:
```
collecting ... collected 19 items

plugins/superheroes/lib/tests/test_seams_check_c2.py::test_a_sliced_round_one_goes_panel_then_seams_check_then_verifiers_with_both_findings_staged_once PASSED [  5%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_a_seams_check_with_no_findings_stages_the_panels_alone PASSED [ 10%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_a_seams_check_finding_outside_the_diff_is_dropped_at_compile_like_any_other PASSED [ 15%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_after_the_seams_check_re_entering_round_one_goes_straight_to_the_verifiers PASSED [ 21%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_a_later_round_of_a_sliced_change_never_enters_the_seams_check PASSED [ 26%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_a_sliced_run_through_its_fix_rounds_runs_the_seams_check_once PASSED [ 31%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_an_unsliced_round_one_never_enters_the_seams_check[no-plan] PASSED [ 36%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_an_unsliced_round_one_never_enters_the_seams_check[not-sliced] PASSED [ 42%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_an_unsliced_round_one_never_enters_the_seams_check[sliced-not-true] PASSED [ 47%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_an_unsliced_round_one_never_enters_the_seams_check[not-a-dict] PASSED [ 52%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_an_unsliced_big_run_never_dispatches_the_seams_check PASSED [ 57%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_a_three_thousand_line_diff_has_no_shards_in_the_panel_payload PASSED [ 63%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_the_seams_payload_lists_each_slice_by_id_with_its_sorted_files PASSED [ 68%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_the_seams_payload_with_no_plan_lists_no_slices PASSED [ 73%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_the_seams_order_sidecar_carries_the_slice_list PASSED [ 78%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_a_current_generation_session_saved_at_the_retired_step_continues_past_it[step] PASSED [ 84%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_a_current_generation_session_saved_at_the_retired_step_continues_past_it[pending] PASSED [ 89%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_the_retired_step_handler_leaves_other_states_as_they_are PASSED [ 94%]
plugins/superheroes/lib/tests/test_seams_check_c2.py::test_no_shipped_library_module_order_template_or_review_code_doc_names_the_retired_pass_or_the_folder_split FAILED [100%]

E       AssertionError: the retired names are still in shipped text:
E         rubric/orders/dispatch-gap-sweep.md: gap-sweep
E       assert not ['rubric/orders/dispatch-gap-sweep.md: gap-sweep']
========================= 1 failed, 18 passed in 2.31s =========================
```
  (The traceback body between the node list and the `E` lines is the same as in the red above and is elided here; the node list and the `E` lines are verbatim.)

## Disclosures

- Not neutralized, so listed as unproven: the seams-slices sidecar's write (`_order_sidecar_writes`) has a green test (`test_the_seams_order_sidecar_carries_the_slice_list`) with no red shown here; the compile-and-drop step of `_fold_seams`; the `_seams_slices` helper's skipping of malformed slice rows; and the per-slice file sort.
- The chained run shape (six runs for ten) is a deviation from the order's sketch, made to stay inside the 24-command budget.
