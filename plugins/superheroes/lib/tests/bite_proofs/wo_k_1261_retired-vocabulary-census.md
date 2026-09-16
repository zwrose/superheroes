# Bite-proof record — #1261 WO-K, the extended retired-vocabulary census

One detector changed in this pass:
`_assert_retired_door_literals_absent` in `plugins/superheroes/lib/tests/test_disposition_flow.py`.
Its literal set widened from one phrase to the whole retired door-and-routing vocabulary.

This record supersedes **BP-1** of `wo_d_1261_door-censuses.md` for the coverage axis. That proof
planted its literal in `owner-decisions.md`, a file the same test module already names in its
hand-maintained `_TOUCHED_FILES` tuple, so the red it produced was equally consistent with a
detector hard-coded to that one file — it did not demonstrate the tree walk it claimed. Every probe
below plants in `plugins/superheroes/rubric/prose-standard.md`, which appears in **no** hand-
maintained list in the module and is reached only by `_walk_shipped_markdown()`. The red names that
file by the relative path the walk produced, which is the axis the detector claims.

**Guarded-element set.** Each literal in `_RETIRED_DOOR_LITERALS` is an independently neutralizable
element: removing any one of them leaves the detector green on that literal's return. Six elements,
six probes:

1. `gate verdict`
2. `Tier 1`
3. `Tier 2`
4. `Tier-1`
5. `Tier-2`
6. `worth-it gate` (re-proved on the final head, at a plant site that demonstrates the walk)

**Mechanics, identical for all six.** The orchestrator applied each neutralization as a targeted,
reversible edit through the host's edit action, with the detector **unedited**, on a committed and
otherwise clean tree (`c8aaf47c`). Each probe planted one sentence immediately below the title line
of `prose-standard.md`, ran the detector, then reverted by the inverse edit. The detector was run by
exact test name, never by selector.

**Command, the same for every probe:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest \
  "plugins/superheroes/lib/tests/test_disposition_flow.py::test_retired_door_literals_absent" -q
```

---

## BP-K1 — `gate verdict`

**Neutralization** — one sentence planted in `rubric/prose-standard.md`:

```
+A disposition names its gate verdict.
```

**Raw red:**

```
                        "%s: retired door literal %r present" % (rel, literal)
                    )
E                   AssertionError: rubric/prose-standard.md: retired door literal 'gate verdict' present

plugins/superheroes/lib/tests/test_disposition_flow.py:147: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_disposition_flow.py::test_retired_door_literals_absent
1 failed in 0.86s
EXIT=1
```

## BP-K2 — `Tier 1`

**Neutralization:** `+A routing lands at Tier 1.`

**Raw red:**

```
E                   AssertionError: rubric/prose-standard.md: retired door literal 'Tier 1' present
1 failed in 0.31s
```

## BP-K3 — `Tier 2`

**Neutralization:** `+A routing lands at Tier 2.`

**Raw red:**

```
E                   AssertionError: rubric/prose-standard.md: retired door literal 'Tier 2' present
1 failed in 0.34s
```

## BP-K4 — `Tier-1`

**Neutralization:** `+A routing lands at Tier-1.`

**Raw red:**

```
E                   AssertionError: rubric/prose-standard.md: retired door literal 'Tier-1' present
1 failed in 0.27s
```

## BP-K5 — `Tier-2`

**Neutralization:** `+A routing lands at Tier-2.`

**Raw red:**

```
E                   AssertionError: rubric/prose-standard.md: retired door literal 'Tier-2' present
1 failed in 0.57s
```

## BP-K6 — `worth-it gate`, re-proved at a walk-demonstrating site

**Neutralization:** `+A residual first passes the worth-it gate.`

**Raw red:**

```
E                   AssertionError: rubric/prose-standard.md: retired door literal 'worth-it gate' present
1 failed in 0.65s
```

---

## Restore and green, once, after the last probe

**Restore:** the inverse edit, removing the planted sentence.

**Restore receipt** — `git status --porcelain` at the worktree root returned **no output**. No
residue, in the target file or anywhere else.

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.48s
```

---

## Disclosures

- **The orchestrator produced these proofs, not an implementer.** The dispatching order (1261-WO-K)
  told the implementer explicitly not to write a bite-proof record, because a neutralization probe
  reverts by an edit and a dispatched seat's revert has wiped uncommitted sibling work in this
  repository before. The mutation mechanics the builder charter assigns to the orchestrator — commit
  the landed work first, plant through the host's edit action, revert by the inverse edit — were
  followed here on a clean committed tree. The proofs were therefore both produced and re-run by the
  same session; that is the honest limitation of this record, and it is why every raw capture above
  is reproduced verbatim rather than summarised.
- **The set is hand-maintained, and the probes cannot prove otherwise.** Each probe shows that a
  literal *in* the set bites and that the file was reached by the walk. No probe can show that the
  set is complete — a retired term nobody added is invisible to it. That residual is what entry
  **S7** on the keep-or-retire list records, tagged `structural`.
