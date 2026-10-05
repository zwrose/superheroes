# C14 layer 3a — r5 bite-proof re-run by the orchestrator, at the final head

**Lane:** r5 (`launch-62ee8e9329a9b6f2`), the adoption lane that finished layer 3a.
**Run by:** the Workhorse orchestrator, not an implementer — the r4 implementers produced their own
proofs (`c14_l3a_h_payload_key_home.md`, `c14_l3a_i_run_dir_token_home.md`,
`c14_l3a_j_probe_coverage.md`); this record is the orchestrator's **independent re-run at the final
head `efe6be3e`**, per the verification duty. The r4 lane's own in-progress re-run record was left
in its dead tree unread as a receipt and **not adopted** — every red below was produced by this
session.

**Where:** a detached probe worktree at `efe6be3e` (`git worktree add --detach`), never the build
tree and never a tree a live seat was reading. Every neutralization was a **targeted, revertible
edit through the host's edit action**, reverted by its **inverse edit** before the next was planted;
the detector itself was never edited; `git status --porcelain` was **empty** before the first plant
and after the last restore.

Every command below ran as
`/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-probe -m pytest …` from the probe
worktree root.

## Elements re-proved red→green in this lane

| # | guarded element | neutralization | proving test | raw red |
|---|---|---|---|---|
| BP-I1 | a stray run-dir refusal literal outside the home fails the tree-derived census | added `_R5_BP_PLANT = "run-dir-reused"` to `engine_adapter.py` | `test_run_dir_refusal_census.py::test_run_dir_refusal_literals_only_in_home[engine_adapter.py]` | `AssertionError` at `test_run_dir_refusal_census.py:77` → `1 failed, 162 passed in 0.86s` |
| BP-I2 | the census pins the home's literal **values**, not only its symbols | `DETAIL_RUN_DIR_REUSED = "run-dir-reused"` → `"run-dir-reused-bite-proof"` | `test_run_dir_refusal_census.py::test_run_dir_refusal_home_literal_values` | `AssertionError … Extra items in the right set: 'run-dir-reused'` at `:69` → `1 failed, 162 passed in 0.78s` |
| BP-K2 | the narrowing tests the payload key's **value**, not a `carries` presence predicate | the narrowing → `if ea.review_payload_carried(branch, k)[0]` | `test_engine_result_channel.py::test_native_branch_narrowing_present_but_null_grouping_not_second_kind` | `AssertionError: assert 'object-both-payload-keys' != 'object-both-payload-keys'` at `:849` → `1 failed, 90 passed in 0.41s` |
| BP-J-a | the injected seam stamps the **delivery-kind** completion fields | the delivery-kind block → `if stdout_result is not None: ended["stdoutResult"] = stdout_result` | `test_conformance_probe.py::test_claude_probe_all_green_both_modes` (+2 siblings) | `3 failed, 77 passed in 1.13s` |
| BP-J-b | the all-mode preflight blocks dispatch before **any** mode runs | the all-mode `any_reused` branch → a per-mode reuse check | `test_conformance_probe.py::test_claude_probe_refuses_reused_background_before_any_mode_dispatches` | `AssertionError: assert 1 == 0` (one recorded `claude -p` call) at `:1225` → `1 failed in 0.27s` |
| r3 #1 | `conformance_probe`'s symlinked-parent refusal (re-proved: WO-I replaced its refusal literal with the home constant) | `if os.path.islink(stripped):` → `if False and os.path.islink(stripped):` | `test_conformance_probe.py::test_probe_refuses_symlinked_run_dir` | `AssertionError` at `:366` (`'default: auth-or-config-refusal'`) → `1 failed in 0.27s` |
| r3 #2 | the parent run-dir unrecognized-entries refusal (same reason) | `if entries - expected_names:` → `if False and (entries - expected_names):` | `test_conformance_probe.py::test_probe_refuses_parent_run_dir_with_unrecognized_entries` | `AssertionError` at `:384` (`+ auth-or-config-refusal`) → `1 failed in 0.39s` |
| r3 #10 | the in-process capture records its deadline (re-proved: WO-J edited the block immediately above it) | dropped `if timed_out: ended["timeoutAt"] = timeout_deadline_wall` | `test_engine_dispatch.py::test_injected_capture_timeout_records_timeout_at` | `KeyError: 'timeoutAt'` at `test_engine_dispatch.py:3725` → `1 failed, 779 deselected in 0.92s` |

**The BP-J-a red bites wider than the implementer's record, and it bit that way here too.** The
implementer recorded two failures under this neutralization; this lane's independent run produced
**three** — `test_claude_probe_green_as_far_as_the_injected_seam_can_reach`,
`test_claude_probe_all_green_both_modes` and
`test_claude_probe_refuses_reused_background_before_any_mode_dispatches`. Recorded as observed; a
wider bite is not a weaker proof.

**One selection-shape note, recorded rather than hidden.** The r3 #10 red was selected with `-k
<name>` rather than the exact node id. The selection resolved to exactly one test — the run reports
`1 failed, 779 deselected` and the failure is the named test — so the proof stands, but every other
red above was selected by exact node id or by file, which is the shape to prefer.

## The green half — one run, restored tree, final head

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-probe -m pytest \
  plugins/superheroes/lib/tests/test_conformance_probe.py \
  plugins/superheroes/lib/tests/test_engine_dispatch.py \
  plugins/superheroes/lib/tests/test_engine_result_channel.py \
  plugins/superheroes/lib/tests/test_run_dir_refusal_census.py \
  plugins/superheroes/lib/tests/test_engine_adapter.py -q -n auto
```
```
1700 passed in 23.39s
```
`git status --porcelain` empty before and after; `git rev-parse HEAD` = `efe6be3e`.

## The one element that could not be proved, and the check that confirms it

`c14_l3a_h_payload_key_home.md`'s **BP-K1** — *no kind is exempt by omission*, neutralized by
exempting `ruling` — is recorded there as **unprovable as placed**. This lane **accepts** that
disclosure, on a check of its own rather than on the implementer's word (read-only, at the final
head):

```
>>> ea._recognised_review_kinds({'id': 'x', 'ruling': None,        'reason': 'r'})  ->  []
>>> ea._recognised_review_kinds({'id': 'x', 'ruling': '',          'reason': 'r'})  ->  []
>>> ea._recognised_review_kinds({'id': 'x',                        'reason': 'r'})  ->  []
>>> ea._recognised_review_kinds({'id': 'x', 'ruling': 'discharged','reason': 'r'})  ->  ['ruling']
>>> ea.review_payload_key('ruling')      ->  'ruling'
>>> ea.review_payload_key('not-a-kind')  ->  None
```

A branch is recognised as `ruling` **only** when its `ruling` key already holds a valid non-empty
value, so under the final key-and-value narrowing an "exempt `ruling`" neutralization cannot change
the matched set for any branch that reaches it — the element is **behaviourally inert as placed**,
not merely unproved by one implementer. The invariant's *other* half — an **unregistered** kind is
narrowed away rather than kept — is carried by `review_payload_key` returning `None` (shown above)
and is asserted directly by the tests in `test_engine_result_channel.py`.
