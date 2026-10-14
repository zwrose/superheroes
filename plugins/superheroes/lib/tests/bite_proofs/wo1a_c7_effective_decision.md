# Bite-proof record — one effective decision per finding (test_effective_decision_c7.py)

Status of every entry below: **Unrunnable here.** No neutralization was applied and no red or green
run was made in this dispatch. Nothing in this record is a receipt of a run.

## What blocked the run

Every `pytest` invocation the order names was refused by the shell permission layer before it
started. Quoted, in the order they were attempted:

- `cd /home/user/wt-1868 && /usr/bin/python3 -B -X pycache_prefix=/tmp/claude-0/pyc -m pytest plugins/superheroes/lib/tests/test_effective_decision_c7.py -q -n 4`
  -> `This Bash command contains multiple operations. The following part requires approval: /usr/bin/python3 -B -X pycache_prefix=/tmp/claude-0/pyc -m pytest plugins/superheroes/lib/tests/test_effective_decision_c7.py -q -n 4`
- the same command, alone, from `/home/user/wt-1868` -> `This command requires approval`

The only interpreter calls that ran were inline file-edit scripts (they wrote `decision_kinds.py` and
`round_driver.py`); no test of any kind ran. A scratch exploration script was also refused. The
order mandates this interpreter and these flags, so no other invocation form was substituted.

## Command that can run it, and who owes the receipts

Environment: the worktree `/home/user/wt-1868` with a shell that permits the order's pytest form.
Each proof names one exact node id (never `-k`):

`/usr/bin/python3 -B -X pycache_prefix=/tmp/claude-0/pyc -m pytest plugins/superheroes/lib/tests/test_effective_decision_c7.py::<node> -q -n 0`

The orchestrator owns the outstanding receipts (the order says it re-runs and verifies itself).
Substitute evidence produced: none. No A/B against the base revision was run either.

## Declared guarded elements, with the neutralization to apply for each

Each is a targeted edit in `plugins/superheroes/lib/round_driver.py`, restored by the inverse edit
(never `git checkout`/`restore`/`stash`). The detector stays unedited.

### BP-1 — the lineage write in `_stage_findings` (`_LineageCarry.apply`)

- axis: a reworded finding at the decided file and line takes the decision (lineage is written)
- detector: `test_effective_decision_c7.py::test_t1_reword_carries_guidance_to_next_fix`
- neutralization: in `_LineageCarry.apply`, replace
  `        state.setdefault("findingLineage", {})[key] = root`
  with
  `        return  # neutralized: carry never happens` placed before that line (the two lines after
  it, the lineage write and the `ruling-carried` decision, become unreachable).
- expected red: `assert state["findingLineage"] == {key_new: key_a}` fails (KeyError on
  `findingLineage`).
- restore: delete the inserted `return` line.

### BP-2 — lineage resolution in the reader (latest across the group)

- axis: the original wording reads the newest decision given on any member of its group
- detector: `test_effective_decision_c7.py::test_t2_replaced_guidance_never_returns`
- neutralization: in `_effective_decisions`, replace
  `        root = _lineage_root(lineage, key)\n        held = best.get(root)` (first loop) and
  `by_key[key] = best[_lineage_root(lineage, key)][1]` (second loop) so the root is the key itself:
  add `lineage = {}` directly after `lineage = _lineage_map(state)`.
- expected red: `RD._live_ruling_by_key(state)[key_f]["guidance"] == "G2"` fails (it reads "G1").
- restore: delete the inserted `lineage = {}` line.

### BP-3 — the single-entry rendering in `_gate_guidance_entries`

- axis: only the effective decision renders; a replaced one never does
- detector: `test_effective_decision_c7.py::test_t3_precedence_latest_decision_renders_alone`
- neutralization: make `guided(key)` ignore which decision is effective and the current-round
  gate loop render without the effectiveness test: replace
  `                if (live is None or live.get("source") != "gate" or live.get("findingKey") != key`
  `                        or str(live.get("round")) != str(rnd)`
  `                        or live.get("guidance") != guidance.strip()):`
  `                    continue`
  with `                if False:` + `                    continue`, and add a second rendering of
  the rule row for the key by changing `guided` to read the latest `rulingsLog` row directly. (The
  first half alone — gate "A" then rule "B" — already renders both once the gate loop stops
  testing effectiveness.)
- expected red: the `[(key, "B", True)]` equality in the gate-then-rule half fails (two entries).
- restore: the inverse edit of each replacement.

### BP-4 — the gate-skip candidate in the reader

- axis: an owner-gate `skip` is a decision and keeps binding the finding after a reword
- detector: `test_effective_decision_c7.py::test_t4_gate_skip_binds_a_reword`
- neutralization: in `_gate_decision_candidates`, replace
  `            if disposition == "skip":\n                ruling = "out-of-scope"`
  with
  `            if disposition == "skip":\n                continue`
- expected red: `state["findingLineage"] == {key_new: L2E._TRADEOFF_ID}` fails (no decision to
  carry, so no lineage entry).
- restore: change `continue` back to `ruling = "out-of-scope"`.

## What is NOT proven by this record

The fail-closed edge tests (`test_t5` .. `test_t11`) and the extra tests have no recorded
neutralization; the order's declared set is exactly the four elements above.
