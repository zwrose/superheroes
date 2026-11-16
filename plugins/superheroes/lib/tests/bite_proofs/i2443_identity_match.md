# Bite-proof record: the review loop matches a superseded slot and a stalled finding by their full identity (#2443)

Detector: `plugins/superheroes/lib/tests/test_identity_match_2443.py` (36 tests). Declared guarded-element set: G1 to G7
(one neutralization and one red per element, the detector unedited). Every neutralization was one targeted `Edit` on the
build tree and was undone by the inverse `Edit`; no `git checkout`, `restore`, `reset` or `stash` was used. Each red and
each green is a single test node id (never `-k`), run as
`scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/pyc-2443 -m pytest <node id> -q -p no:cacheprovider`.
The `warning: The UV_NATIVE_TLS ...` line the launcher prints before every run is left out of the captures below. Each red
is quoted from its failure body: the test's `def` and decorator lines, the `tmp_path` and `adapters` fixture lines, the
`-vv` hint lines and blank lines are elided, and the assertion lines are quoted as printed. Nothing below is redacted: the
captures hold no secret, token or private URL.

Baseline before any neutralization: `36 passed in 15.45s` (the whole file). Part 1 has no base-code run of its own; each
red below is the proof that the test fails when the guarded clause is absent, which is the base behaviour for that
field (the base matched on `seat` alone).

Restore receipt for every element: the restored lines quoted below, and one `git diff --stat` taken after the last restore
(G7), showing the source diff holds only the intended change:

```
 plugins/superheroes/TRANSITION.md                  |  7 +++
 plugins/superheroes/lib/circuit_breaker.py         | 56 ++++++++++++++++------
 plugins/superheroes/lib/round_driver.py            | 23 +++++++--
 .../skills/review-code/reference/review-record.md  |  2 +-
 4 files changed, 69 insertions(+), 19 deletions(-)
```

The restored lines, quoted from the files after the last restore (`grep` of the lines, with their line numbers):

```
plugins/superheroes/lib/round_driver.py:9823:        {"identity": a.get("identity"), "ruling": a.get("ruling"), "id": a.get("id"),
plugins/superheroes/lib/round_driver.py:18364:                 and row["phase"] == phase
plugins/superheroes/lib/round_driver.py:18365:                 and row["round"] == rnd
plugins/superheroes/lib/round_driver.py:18366:                 and row["attempt"] == attempt
plugins/superheroes/lib/round_driver.py:18367:                 and row["seat"] == seat
plugins/superheroes/lib/round_driver.py:18368:                 and row["occurrence"] == occurrence
plugins/superheroes/lib/circuit_breaker.py:314:            out.append((("id", target_id), target_id, aliases))
plugins/superheroes/lib/circuit_breaker.py:358:                       % (len(counted), "; ".join(names))),
```

The seven single-node greens below are the post-restore runs. After the last restore the whole new file ran green
(`36 passed in 15.08s`, after a comment-spacing edit on `circuit_breaker.py` line 340, `counted = {}  # ...`, which
changes no code), and `test_round_driver_advance.py` ran `145 passed in 39.03s`.

## G1. `_attest_roster` matches on `round`

- Axis: a superseded row labels only a slot of its own round; the row of another round never labels it, so a missing seat is not hidden.
- Neutralization (`round_driver.py`, `_attest_roster`): the line `                 and row["round"] == rnd` was removed.
- Red (node `test_edge1_a_superseded_row_of_another_round_does_not_label_the_slot`, 1 failed):
  ```
  >       assert _roster(d)[SEAT] == "recorded"
  E       AssertionError: assert 'superseded' == 'recorded'
  E
  E         - recorded
  E         + superseded
  test_identity_match_2443.py:203: AssertionError
  FAILED ...::test_edge1_a_superseded_row_of_another_round_does_not_label_the_slot
  1 failed in 1.47s
  ```
- Restore: the inverse `Edit` put `and row["round"] == rnd` back between the `phase` and `attempt` lines. Receipt: line 18365 quoted above.
- Green: `1 passed in 1.19s`.

## G2. `_attest_roster` matches on `phase`

- Axis: a superseded row of another phase never labels the slot.
- Neutralization: the line `                 and row["phase"] == phase` was removed.
- Red (node `test_edge2_a_superseded_row_of_another_phase_does_not_label_the_slot`, 1 failed):
  ```
  >       assert _roster(d)[SEAT] == "recorded"
  E       AssertionError: assert 'superseded' == 'recorded'
  E         - recorded
  E         + superseded
  test_identity_match_2443.py:210: AssertionError
  1 failed in 1.25s
  ```
- Restore: the inverse `Edit` put the `phase` line back before the `round` line. Receipt: line 18364 quoted above.
- Green: `1 passed in 1.21s`.

## G3. `_attest_roster` matches on `attempt`

- Axis: a superseded row of another attempt never labels the slot.
- Neutralization: the line `                 and row["attempt"] == attempt` was removed.
- Red (node `test_edge3_a_superseded_row_of_another_attempt_does_not_label_the_slot`, 1 failed):
  ```
  >       assert _roster(d)[SEAT] == "recorded"
  E       AssertionError: assert 'superseded' == 'recorded'
  E         - recorded
  E         + superseded
  test_identity_match_2443.py:216: AssertionError
  1 failed in 1.41s
  ```
- Restore: the inverse `Edit` put the `attempt` line back between the `round` and `seat` lines. Receipt: line 18366 quoted above.
- Green: `1 passed in 1.28s`.

## G4. `_attest_roster` matches on `occurrence`

- Axis: of a twin slot (`seat` and `seat#1`), only the occurrence the row names reads superseded.
- Neutralization: the line `                 and row["occurrence"] == occurrence` was removed.
- Red (node `test_edge4_only_the_named_occurrence_of_a_twin_slot_reads_superseded[1-expected0]`, 1 failed): the row names
  occurrence 1, and the slot `code-reviewer` (occurrence 0) read superseded too:
  ```
  >       assert _roster(d) == expected
  E       AssertionError: assert {'code-review... 'superseded'} == {'code-review... 'superseded'}
  E         Omitting 1 identical items, use -vv to show
  E         Differing items:
  E         {'code-reviewer': 'superseded'} != {'code-reviewer': 'recorded'}
  test_identity_match_2443.py:227: AssertionError
  1 failed in 0.75s
  ```
- Restore: the inverse `Edit` put the `occurrence` line back before `for row in superseded):`. Receipt: line 18368 quoted above.
- Green: `1 passed in 0.80s`.

## G5. `check_audit_breaker` counts by distinct finding key

- Axis: the stall line counts distinct findings, never the aliases a finding carries.
- Neutralization (`circuit_breaker.py`, the detail's format arguments): `% (len(counted), "; ".join(names))),`
  became `% (len(ids), "; ".join(ids))),` (the alias-union count over `stalled`).
- Red (node `test_p3_edge1_one_finding_with_class_key_aliases_counts_once`, 1 failed):
  ```
  >       assert res["detail"] == STALL_PREFIX % (1, "f.py@L1")
  E       AssertionError: assert '2 finding(s)...; f.py::leaks' == '1 finding(s)...unds: f.py@L1'
  E         - 1 finding(s) failed audit in two consecutive rounds: f.py@L1
  E         + 2 finding(s) failed audit in two consecutive rounds: Security::CWE-401::leaks; f.py::leaks
  test_identity_match_2443.py:343: AssertionError
  1 failed in 0.48s
  ```
- Restore: the inverse `Edit`. Receipt: line 358 quoted above.
- Green: `1 passed in 0.34s`.

## G6. the id dedup in `_round_not_discharged_findings`

- Axis: outcomes sharing one target `id` in the latest round are one finding.
- Neutralization: `out.append((("id", target_id), target_id, aliases))` became `out.append((entry_key, target_id, aliases))`
  (every entry keyed by its index).
- Red (node `test_p3_edge4_one_id_recorded_twice_in_the_latest_round_counts_once`, 1 failed):
  ```
  >       assert res["detail"] == STALL_PREFIX % (1, "T1")
  E       AssertionError: assert '2 finding(s)...ounds: T1; T1' == '1 finding(s)...ve rounds: T1'
  E         - 1 finding(s) failed audit in two consecutive rounds: T1
  E         + 2 finding(s) failed audit in two consecutive rounds: T1; T1
  test_identity_match_2443.py:367: AssertionError
  1 failed in 0.47s
  ```
- Restore: the inverse `Edit`. Receipt: line 314 quoted above.
- Green: `1 passed in 0.34s`.

## G7. `_fold_audits` writes `id` on each audit-round outcome

- Axis: an outcome row carries its target's `id`, which is what the breaker keys a finding on.
- Neutralization (`round_driver.py`): the entry ` "id": a.get("id"),` was removed from the outcome dict.
- Red (node `test_p3_edge8_a_folded_audit_outcome_carries_its_targets_id`, 1 failed):
  ```
  >       assert round1["outcomes"][0]["id"] == tgt["id"]
  E       KeyError: 'id'
  test_identity_match_2443.py:457: AssertionError
  1 failed in 0.42s
  ```
  The through-the-fold naming test (`test_p3_edge8_a_stall_through_the_fold_names_the_finding_by_its_target_id`) was not run
  under this neutralization, and no edge-3 test through the fold was built; the one red above is the element's.
- Restore: the inverse `Edit`. Receipt: line 9823 quoted above.
- Green: `1 passed in 0.35s`.

## Disclosures

- The Part 1 reds drop one clause of the match at a time; the type check on `round`/`attempt` (a bool is not an int)
  and the occurrence coercion are not in the declared set and have no neutralization here (their tests,
  `test_edge9_*` and `test_edge5_*`, pass on the final code).
- Nothing in this record is redacted.
