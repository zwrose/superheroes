# Bite-proof record — #1261 WO-D, the reconciled disposition-flow detectors

Detectors added or changed in this build, all in
`plugins/superheroes/lib/tests/test_disposition_flow.py`. Every probe below ran with the detector
**unedited**, as a targeted reversible edit applied through the host's edit action, on a committed
and otherwise clean tree at `1a4493d8`.

**Guarded-element set.** The dispatching order (1261-wo-d) named a bite-proof for the new census
but did not enumerate the set, which is an order gap the orchestrator records here. The
enumeration used is every independently neutralizable element these three detectors guard:

1. `_assert_retired_door_literals_absent` — the retired term `worth-it gate` absent from every
   shipped markdown file under `plugins/superheroes/` except the generated changelog.
2. `_assert_pinned_headings_present` — the heading `## The front door` present in
   `owner-decisions.md`.
3. `_assert_pinned_headings_present` — the heading `## The revisit-trigger registry` present in
   `owner-decisions.md`.
4. `_assert_discuss_open_holder_pins` — `discuss-open-decisions/SKILL.md` cites the canonical home
   path `skills/showrunner/reference/owner-decisions.md`.

The file's other detectors (`_assert_retired_vocabulary_absent`, `_assert_owner_rejected_terms_absent`,
`_assert_registry_marker_home`) are **unchanged** by this build and carry their existing proofs.

---

## BP-1 — the retired-term census

**Guarded element:** `_assert_retired_door_literals_absent`, `test_disposition_flow.py:134-141`.
**Axis:** presence of the retired term `worth-it gate` anywhere in shipped markdown, reached by
walking the tree rather than by a listed set of files.

**Neutralization** — one sentence appended in `owner-decisions.md` § The venue ladder:

```
-finding, a follow-up idea, or a hardening proposal.
+finding, a follow-up idea, or a hardening proposal. Each one first passes the worth-it gate.
```

**Raw red:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_disposition_flow.py::test_retired_door_literals_absent -q

E                   AssertionError: skills/showrunner/reference/owner-decisions.md: retired door literal 'worth-it gate' present

plugins/superheroes/lib/tests/test_disposition_flow.py:138: AssertionError
FAILED plugins/superheroes/lib/tests/test_disposition_flow.py::test_retired_door_literals_absent
1 failed in 0.26s
EXIT=1
```

The red names the offending file and the offending literal, which is the axis the detector claims:
the file was found by the walk, not by a list.

**Restore:** the inverse edit, removing the appended sentence.

**Restore receipt:** `git status --porcelain -- plugins/superheroes/skills/showrunner/reference/owner-decisions.md`
returned no output. No residue.

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.20s
```

---

## BP-2 — the pinned heading `## The front door`

**Guarded element:** `_assert_pinned_headings_present`, `test_disposition_flow.py:103-120`, for the
first entry of `_PINNED_OWNER_DECISIONS_HEADINGS`.
**Axis:** the exact heading line exists in `owner-decisions.md`.

**Neutralization:**

```
-## The front door
+## The front door (intake)
```

**Raw red:**

```
E               AssertionError: skills/showrunner/reference/owner-decisions.md: pinned heading missing: '## The front door'

plugins/superheroes/lib/tests/test_disposition_flow.py:113: AssertionError
FAILED plugins/superheroes/lib/tests/test_disposition_flow.py::test_new_section_headings_present
1 failed in 0.18s
```

The red names the renamed heading and not the sibling one, so the bite landed on this element.

**Restore:** the inverse edit.

**Restore receipt:** `git status --porcelain` over the file returned no output.

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.14s
```

---

## BP-3 — the pinned heading `## The revisit-trigger registry`

**Guarded element:** `_assert_pinned_headings_present`, same detector, **second** entry of
`_PINNED_OWNER_DECISIONS_HEADINGS`. Proven separately, because one entry's red says nothing about
the other.
**Axis:** the exact heading line exists in `owner-decisions.md`.

**Neutralization:**

```
-## The revisit-trigger registry
+## The revisit-trigger registry and its rows
```

**Raw red:**

```
E               AssertionError: skills/showrunner/reference/owner-decisions.md: pinned heading missing: '## The revisit-trigger registry'

plugins/superheroes/lib/tests/test_disposition_flow.py:113: AssertionError
FAILED plugins/superheroes/lib/tests/test_disposition_flow.py::test_new_section_headings_present
1 failed in 0.15s
```

**Restore:** the inverse edit.

**Restore receipt:** `git status --porcelain` over the file returned no output.

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.32s
```

---

## BP-4 — the canonical-home citation

**Guarded element:** `_assert_discuss_open_holder_pins`, `test_disposition_flow.py:143-150`.
**Axis:** `discuss-open-decisions/SKILL.md` cites the canonical home **path**, not any particular
sentence about it. The detector was narrowed in this build: its prose half retired, its path half
kept, so the proof must land on the path.

**Neutralization** — every occurrence of the path rewritten, since one surviving occurrence
satisfies the detector:

```
-skills/showrunner/reference/owner-decisions.md
+skills/showrunner/reference/decisions.md
```

applied to all three occurrences in the file.

**Raw red:**

```
E           AssertionError: skills/discuss-open-decisions/SKILL.md: canonical home 'skills/showrunner/reference/owner-decisions.md' not cited

plugins/superheroes/lib/tests/test_disposition_flow.py:148: AssertionError
FAILED plugins/superheroes/lib/tests/test_disposition_flow.py::test_discuss_open_holder_pins
1 failed in 0.21s
```

**Restore:** the inverse replacement, all three occurrences.

**Restore receipt:** `git status --porcelain` over the whole worktree returned no output.

**Raw green** — the whole file, after the last restore:

```
............                                                             [100%]
12 passed in 0.33s
```

---

## Disclosures

- **The in-file negative tests are not the proof.** `test_negative_retired_door_literal_inserted`
  and its siblings feed synthetic strings to the checkers, which proves the checkers raise but not
  that they reach the real files. The four probes above are the real-channel proofs, run against
  the repository's own surfaces.
- **No residue.** Each restore was verified with `git status --porcelain` before the next probe
  began, and the tree was clean at the start and the end of the sequence.
