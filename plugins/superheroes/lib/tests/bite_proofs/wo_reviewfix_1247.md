# Bite-proof record — review-fix rounds (#1247 continuation)

**Provenance: orchestrator-authored and orchestrator-run.** The detectors below were added by the
`review-code` auto-fix loop's fix rounds (commits `2d888b7f` and `1fd7f8fc`, fixer = cursor
`composer-2.5`), which produces no bite-proof record of its own. The orchestrator produced and ran
every proof here on the **final head**, with the detectors unedited. Every neutralization was applied
as a targeted, revertible edit through the host's edit action and reverted by inverse edit; no
`git checkout`/discard was used. Raw captures are quoted verbatim and carry no secrets, tokens,
private URLs, or PII — nothing was redacted because there was nothing to redact.

Command shape for every run below:

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest <exact node id> -q
```

Tests are selected by **exact node id**, never `-k`.

## Guarded elements

| id | guarded element | axis | representative |
|---|---|---|---|
| BP-RF1 | `test_outcome_members_from_ast_includes_annotated_constant` | an `OUTCOME_*` member declared as an **annotated** assignment is still derived by the member census | itself |
| BP-RF2 | `test_normalize_declared_non_pass_never_upgrades_to_pass` | a **declared non-pass** member is never normalized **up** to a pass member by its own fields | itself |
| BP-RF3 | *class:* **declared outcome returned unchanged despite contradicting fields** — `test_normalize_declared_ok_with_refusing_fields_reredives_downward` and `test_contradictory_plant_undetected_probe_folds_dead` | a declared outcome whose fields refuse it is **re-derived downward**, and the re-derivation reaches the driver's fold | `test_normalize_declared_ok_with_refusing_fields_reredives_downward` |

BP-RF3 is a **failure-mode equivalence class**, not a convenience bucket: both members go red on
exactly one neutralization because both assert the same downward re-derivation — one at the
`normalize` boundary, one through `round_driver.canary_liveness`'s fold. Both members are named
above, so no element stands unenumerated. BP-RF2 is deliberately **not** in that class: it has its
own neutralization and its own red, because the upward-clamp is a separate branch.

---

## BP-RF1 — annotated member declarations

**guarded element:** `plugins/superheroes/lib/tests/test_canary_outcome_census.py::test_outcome_members_from_ast_includes_annotated_constant`
**axis:** an `OUTCOME_*` member declared as `ast.AnnAssign` is derived by the census, not silently dropped.

**neutralization** (production path — `_outcome_member_from_assign`, the extractor the detector
exercises; the detector itself untouched): the `ast.AnnAssign` arm removed, restoring the
`ast.Assign`-only shape.

```python
    if isinstance(node, ast.Assign):
        targets = node.targets
        value = node.value
    else:
        return
```

**raw red:**

```
plugins/superheroes/lib/tests/test_canary_outcome_census.py:222: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_canary_outcome_census.py::test_outcome_members_from_ast_includes_annotated_constant
1 failed in 0.14s
```

The red is on the declared axis: the annotated member is absent from the derived set.

**restore:** inverse edit reinstating the `ast.AnnAssign` arm (including its non-`Name`-target
early return).
**restore receipt:** `git status --porcelain` over the whole worktree → **empty**.
**raw green:** see the consolidated green run at the end of this record.

---

## BP-RF2 — a declared non-pass member never upgrades to pass

**guarded element:** `plugins/superheroes/lib/tests/test_canary_outcome_census.py::test_normalize_declared_non_pass_never_upgrades_to_pass`
**axis:** no member of `NON_PASS_OUTCOMES`, declared with `engaged=True, detectedPlant=True`,
normalizes to a pass member.

This is the detector for the **fail-direction inversion the round-1 fix itself introduced** — two
independent round-2 auditors found it, and the round-2 fix added the clamp.

**neutralization** (production path — `canary_outcome.normalize`; the detector untouched): the
upward clamp deleted, leaving the derived value to win unconditionally.

```python
    if outcome != derived:
        # axis: a caller cannot assert an outcome its fields refuse
        return derived, "canary-outcome-contradicts-fields"
```

**raw red:**

```
E            +    where <function is_pass at 0x1082de550> = canary_outcome.is_pass

plugins/superheroes/lib/tests/test_canary_outcome_census.py:235: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_canary_outcome_census.py::test_normalize_declared_non_pass_never_upgrades_to_pass
1 failed, 2 passed in 0.14s
```

The red is on the declared axis — a declared non-pass member reached `is_pass` true — and the two
BP-RF3 members stayed **green** under this neutralization, which is the evidence that BP-RF2 and
BP-RF3 are independently guarded rather than one assertion standing for both.

**restore:** inverse edit reinstating the clamp branch and its `# axis:` line.
**restore receipt:** `git status --porcelain` over the whole worktree → **empty**.

---

## BP-RF3 — a declared outcome its fields refuse is re-derived downward

**guarded elements (class members, both named):**

- `plugins/superheroes/lib/tests/test_canary_outcome_census.py::test_normalize_declared_ok_with_refusing_fields_reredives_downward` — the boundary assertion (representative);
- `plugins/superheroes/lib/tests/test_canary_outcome_census.py::test_contradictory_plant_undetected_probe_folds_dead` — the same guarantee observed through `round_driver.canary_liveness`'s fold.

**axis:** a declared outcome contradicted by its own `engaged` / `detectedPlant` fields is replaced
by the derived (stricter) member, and that replacement is what the driver folds on.

**neutralization** (production path — `canary_outcome.normalize`; both detectors untouched): the
contradiction branch returns the **declared** outcome instead of the derived one.

```python
        # axis: a caller cannot assert an outcome its fields refuse
        return outcome, "canary-outcome-contradicts-fields"
```

**raw red (both members, one neutralization):**

```
plugins/superheroes/lib/tests/test_canary_outcome_census.py:260: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_canary_outcome_census.py::test_normalize_declared_ok_with_refusing_fields_reredives_downward
FAILED plugins/superheroes/lib/tests/test_canary_outcome_census.py::test_contradictory_plant_undetected_probe_folds_dead
2 failed in 0.13s
```

**restore:** inverse edit reinstating `return derived, …` (with the clamp branch above it).
**restore receipt:** `git status --porcelain` over the whole worktree → **empty**.

---

## Consolidated restore receipt and green

After every neutralization above was reverted:

```
RESTORE RECEIPT: []
............................................................             [100%]
60 passed in 1.33s
```

(`pytest plugins/superheroes/lib/tests/test_canary_outcome_census.py plugins/superheroes/lib/tests/test_seat_canary.py -q`.)

No residue: the `git status --porcelain` above covers the whole worktree, not just the neutralized
paths, and came back empty.
