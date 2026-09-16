# Reset C3 (#1262) bite-proof — the bite-proof pointer census

This change set adds one row to the hand-maintained `_CONSUMER_ROSTER` in
`plugins/superheroes/lib/tests/test_bite_proof_doctrine.py`, and it also lands the rule
(`rubric/review-discipline.md`, `### Prefer shapes that cannot fail`) saying that an existing
detector-shaped test owes the three birth duties the next time a change edits the detector itself or
the enumeration it maintains. Editing the roster is exactly such an edit, so the pointer census owes
a proof. This record is that proof.

Two elements are proved: the **roster row's own pointer-count assertion**, and the **completeness
walker** that the docstring's by-construction-coverage claim rests on. Nothing else on this branch is
a new or changed detector; the rest of the diff is doctrine prose and one project-record entry.

Both proofs were **produced and re-run by the orchestrator**, not inherited from an implementer
report. Each mutation was applied as a targeted revertible edit through the host's edit action —
never a whole-file rewrite, never an ad-hoc shell edit, never a git discard — and each was reverted
by its **inverse edit**.

**Where the probes ran.** In a **detached worktree of its own** (`/private/tmp/c3-probe`) pinned to
commit `b71b8714`, never in the build worktree, so no concurrent read-only seat could grade a tree
mid-probe.

**Normalization, stated because it changes what the runs mean.** Every command ran under
`-B -X pycache_prefix=/private/tmp/superheroes-pyc-c3probe`, so Apple Python's out-of-tree bytecode
cache could not serve stale objects across same-second edits — the exact shape of both mutations
here. Each red and green run selected its test by **exact node id**, never by `-k`, and ran under
`-p no:randomly` so ordering could not enter the result.

**Tree state after the probe sequence:** `git status --porcelain` empty and `git diff HEAD --stat`
empty, both measured in the probe worktree and quoted below.

---

## BP-C3-1 — the roster row's pointer-count assertion

**Guarded element:** the roster row
`("rubric/review-discipline.md", "## Machinery, homes, and what a review may ask for", 1)`. It is
what makes the `rubric/bite-proof.md` pointer inside that section a **deliberate, counted** pointer
rather than one that can be added or lost silently.

**Neutralization:** the pointer literal inside that section was misspelled, from
`` `rubric/bite-proof.md` `` to `` `rubric/biteproof.md` ``. The pointer sentence and the section
were both left in place, so the probe measures the **count assertion**, not the presence of a
paragraph. Misspelling rather than deleting is the point: a proof that deletes the whole sentence
also removes the prose a reader would notice, and would not distinguish a census that counts from
one that merely checks the section exists.

**Red run** — node id
`test_consumer_section_points_at_bite_proof_home[rubric/review-discipline.md::## Machinery, homes, and what a review may ask for]`:

```
E           AssertionError: rubric/review-discipline.md (section ## Machinery, homes, and what a
            review may ask for): expected 'rubric/bite-proof.md' count 1, found 0 — re-add
            pointer(s) or update test_bite_proof_doctrine.py roster

plugins/superheroes/lib/tests/test_bite_proof_doctrine.py:234: AssertionError
FAILED plugins/superheroes/lib/tests/test_bite_proof_doctrine.py::test_consumer_section_points_at_bite_proof_home[rubric/review-discipline.md::## Machinery, homes, and what a review may ask for]
1 failed in 0.07s
```

**Green run** after the inverse edit, same node id:

```
.                                                                        [100%]
1 passed in 0.06s
```

## BP-C3-2 — the completeness walker

**Guarded element:** `_walk_plugin_pointer_sections` together with `_check_pointer_roster_complete`.
This pair is what the module docstring's **by-construction coverage** claim rests on: the roster
cannot silently miss a consumer, because the walk enumerates every markdown file under the plugin
root and the check refuses any pointer-carrying section the roster does not name. A claim of
by-construction coverage that is never driven red is exactly the vacuity this proof exists to rule
out.

**Neutralization:** a `rubric/bite-proof.md` pointer was planted inside a level-2 section the roster
does not name (`## Prose-driven review (--review-only)`), by adding one sentence. No roster row, no
assertion, and no walk code was touched — so the probe measures the **walker's reach**, not an
edited expectation.

**Red run** — node id `test_pointer_roster_is_complete`:

```
E           AssertionError: pointer roster drift: missing=[], unrostered=[('rubric/review-discipline.md',
            '## Prose-driven review (`--review-only`)')] — extend roster

plugins/superheroes/lib/tests/test_bite_proof_doctrine.py:370: AssertionError
FAILED plugins/superheroes/lib/tests/test_bite_proof_doctrine.py::test_pointer_roster_is_complete
1 failed in 0.09s
```

The red output names the defect exactly: a pointer carried by a section nobody rostered, found by
the walk rather than by anyone remembering to look.

**Green run** after the inverse edit, same node id:

```
.                                                                        [100%]
1 passed in 0.07s
```

**Tree state, measured after the inverse edit and before leaving the probe worktree:**

```
porcelain: []
diff stat: []
```

---

## What this proof does not cover, stated rather than implied

The **heading and clause rosters** in the same module have no completeness walker. They are
hand-maintained, and a new heading or a newly restated clause is unguarded until someone adds it.
That residual is recorded in the module's own docstring and is **not** covered by BP-C3-2; the
by-construction-coverage duty is discharged for the **pointer half only**, and the docstring says so
in those words rather than claiming the detector is covered as a whole.

Neither proof says anything about whether the doctrine the census points at is correct or obeyed.
A census proves that a pointer is where the roster says it is, and nothing more.
