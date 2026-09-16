# Bite-proof record — WO-N and WO-Q, the retired-tier-vocabulary census (issue #1261)

Fifteen proofs, one per guarded element. All raw captures are unredacted because none carried a
secret, token, private URL, or PII; nothing was elided, and the record is well inside the 32 KiB
per-element and 128 KiB whole-record ceilings.

## Who produced these, and the limitation that carries

**The orchestrator planted and reverted every probe**, not the implementer. WO-N's order said so
before the work was dispatched: a probe's revert from a dispatched seat has wiped uncommitted
sibling work in this repository before, and the charter assigns the probe mechanics to the
orchestrator anyway. **The limitation is that the same session produced these proofs and re-ran
them.** Every raw capture below is reproduced verbatim rather than summarised, so the record can be
re-executed by a reader who does not trust the summary.

Every probe was applied as a **targeted, reversible edit through the host's edit action** — never a
whole-file rewrite, never an ad-hoc shell edit — in a **dedicated detached worktree**
(`/private/tmp/wh1261-bp`) that no other seat was reading. The landed work was committed before the
first probe.

## The declared guarded-element set

WO-N's order declared the set as *the four tier literals over the three enumerated files, and the
narrowed pinned heading*. This record enumerates that set at its finest reading — **twelve
(file, literal) pairs**, each independently neutralizable — plus the narrowed pinned heading, plus
the two legs whose detector this change set narrowed rather than added. Fifteen entries, no
equivalence classes, no representative standing for an unenumerated element.

**Detectors this change set added or changed, and where each is proven:**

| Detector | Status vs the base | Proofs |
|---|---|---|
| `_assert_retired_tier_literals_absent` | **new** | BP-1 … BP-12 |
| `_assert_pinned_headings_present` | **narrowed** (owner-decisions heading set shrank to one) | BP-13, BP-15 |
| `_assert_discuss_open_holder_pins` | **narrowed** (two clause legs retired; the path-citation leg survives byte-identical) | BP-14 |
| `_assert_retired_vocabulary_absent` | unchanged from the base, byte for byte | none owed |
| `_assert_owner_rejected_terms_absent` | unchanged from the base, byte for byte | none owed |
| `_assert_registry_marker_home` | unchanged from the base, byte for byte | none owed |

The three "unchanged" rows were established by extracting each function from
`origin/main:plugins/superheroes/lib/tests/test_disposition_flow.py` and from the branch head and
comparing them; the extraction and comparison are reproduced in the pull request's build record.

## The head these ran at, and why that is the final head's experiment

Probes ran in a worktree pinned at `9fe317cb`. The only later commit touching the module is
`00756556`, which inserts three **comment** lines (the axis lines WO-Q owed) and changes no
assertion, no constant, and no message — its own targeted run was `12 passed`. The final-head
equivalence check, and a final green run, are recorded in the pull request's build record: if
`git diff` over the detector module and the three censused surfaces between `9fe317cb` and the
final head shows anything beyond those comment lines, the affected proofs are re-run and this
record is updated.

## Baseline

```
$ git -C /private/tmp/wh1261-bp rev-parse --short HEAD
9fe317cb
$ git -C /private/tmp/wh1261-bp status --porcelain
[no output]
$ /usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-bp -m pytest plugins/superheroes/lib/tests/test_disposition_flow.py -q
............                                                             [100%]
12 passed in 0.30s
```

## The probe shape, applied identically for BP-1 … BP-12

For each of the three enumerated surfaces, one anchor sentence was chosen and the literal appended
to it. The anchors:

- `issue-contract.md:153` — `A routed issue that carries the four is gradable at vet without asking anyone what was decided.`
- `showrunner/SKILL.md:467` — `     collector at vet time, unconditionally, so the collector is the complete register by`
- `vet-receipt.md:129` — ``reaches the owner by the no-PR presentation rule in `skills/showrunner/reference/closure.md`.``

Restore in every case was the inverse edit through the same edit action, and the restore receipt is
`git status --porcelain` over the whole worktree coming back **empty** — a stricter receipt than the
neutralized path alone.

---

### BP-1 — `issue-contract.md` × `Tier 1`

- **Guarded element.** `test_disposition_flow.py:_assert_retired_tier_literals_absent`, the pair
  (`skills/showrunner/reference/issue-contract.md`, `"Tier 1"`).
- **Axis.** Presence of the retired literal in that enumerated surface.
- **Neutralization.** Appended ` Tier 1 applies.` to the anchor sentence at `issue-contract.md:153`.
- **Raw red.**

  ```
  E                   AssertionError: skills/showrunner/reference/issue-contract.md: retired tier literal 'Tier 1' present
  1 failed, 11 passed in 0.44s
  ```

- **Restore.** Inverse edit: the appended ` Tier 1 applies.` removed.
- **Restore receipt.** `git status --porcelain` → no output. No residue.
- **Raw green.** `12 passed in 0.41s`

### BP-2 — `issue-contract.md` × `Tier 2`

- **Guarded element.** The pair (`issue-contract.md`, `"Tier 2"`). **Axis.** As BP-1.
- **Neutralization.** Appended ` Tier 2 applies.` to the same anchor.
- **Raw red.**

  ```
  E                   AssertionError: skills/showrunner/reference/issue-contract.md: retired tier literal 'Tier 2' present
  1 failed, 11 passed in 0.67s
  ```

- **Restore.** Inverse edit. **Restore receipt.** `git status --porcelain` → no output.
- **Raw green.** `12 passed in 0.47s`

### BP-3 — `issue-contract.md` × `Tier-1`

- **Guarded element.** The pair (`issue-contract.md`, `"Tier-1"`). **Axis.** As BP-1.
- **Neutralization.** Appended ` Tier-1 applies.` to the same anchor.
- **Raw red.**

  ```
  E                   AssertionError: skills/showrunner/reference/issue-contract.md: retired tier literal 'Tier-1' present
  1 failed, 11 passed in 0.46s
  ```

- **Restore.** Inverse edit. **Restore receipt.** `git status --porcelain` → no output.
- **Raw green.** `12 passed in 0.32s`

### BP-4 — `issue-contract.md` × `Tier-2`

- **Guarded element.** The pair (`issue-contract.md`, `"Tier-2"`). **Axis.** As BP-1.
- **Neutralization.** Appended ` Tier-2 applies.` to the same anchor.
- **Raw red.**

  ```
  E                   AssertionError: skills/showrunner/reference/issue-contract.md: retired tier literal 'Tier-2' present
  1 failed, 11 passed in 0.47s
  ```

- **Restore.** Inverse edit. **Restore receipt.** `git status --porcelain` → no output.
- **Raw green.** `12 passed in 0.36s`

### BP-5 — `showrunner/SKILL.md` × `Tier 1`

- **Guarded element.** The pair (`skills/showrunner/SKILL.md`, `"Tier 1"`). **Axis.** As BP-1.
- **Neutralization.** ` (Tier 1)` inserted after `unconditionally` on the anchor line at
  `showrunner/SKILL.md:467`.
- **Raw red.**

  ```
  E                   AssertionError: skills/showrunner/SKILL.md: retired tier literal 'Tier 1' present
  1 failed, 11 passed in 0.42s
  ```

- **Restore.** Inverse edit. **Restore receipt.** `git status --porcelain` → no output.
- **Raw green.** `12 passed in 0.27s`

### BP-6 — `showrunner/SKILL.md` × `Tier 2`

- **Guarded element.** The pair (`showrunner/SKILL.md`, `"Tier 2"`). **Axis.** As BP-1.
- **Neutralization.** ` (Tier 2)` inserted at the same anchor.
- **Raw red.**

  ```
  E                   AssertionError: skills/showrunner/SKILL.md: retired tier literal 'Tier 2' present
  1 failed, 11 passed in 0.44s
  ```

- **Restore.** Inverse edit. **Restore receipt.** `git status --porcelain` → no output.
- **Raw green.** `12 passed in 0.33s`

### BP-7 — `showrunner/SKILL.md` × `Tier-1`

- **Guarded element.** The pair (`showrunner/SKILL.md`, `"Tier-1"`). **Axis.** As BP-1.
- **Neutralization.** ` (Tier-1)` inserted at the same anchor.
- **Raw red.**

  ```
  E                   AssertionError: skills/showrunner/SKILL.md: retired tier literal 'Tier-1' present
  1 failed, 11 passed in 0.25s
  ```

- **Restore.** Inverse edit. **Restore receipt.** `git status --porcelain` → no output.
- **Raw green.** `12 passed in 0.27s`

### BP-8 — `showrunner/SKILL.md` × `Tier-2`

- **Guarded element.** The pair (`showrunner/SKILL.md`, `"Tier-2"`). **Axis.** As BP-1.
- **Neutralization.** ` (Tier-2)` inserted at the same anchor.
- **Raw red.**

  ```
  E                   AssertionError: skills/showrunner/SKILL.md: retired tier literal 'Tier-2' present
  1 failed, 11 passed in 0.41s
  ```

- **Restore.** Inverse edit. **Restore receipt.** `git status --porcelain` → no output.
- **Raw green.** `12 passed in 0.21s`

### BP-9 — `vet-receipt.md` × `Tier 1`

- **Guarded element.** The pair (`skills/showrunner/reference/vet-receipt.md`, `"Tier 1"`).
  **Axis.** As BP-1.
- **Neutralization.** ` (Tier 1)` appended before the full stop on the anchor at `vet-receipt.md:129`.
- **Raw red.**

  ```
  E                   AssertionError: skills/showrunner/reference/vet-receipt.md: retired tier literal 'Tier 1' present
  1 failed, 11 passed in 0.36s
  ```

- **Restore.** Inverse edit. **Restore receipt.** `git status --porcelain` → no output.
- **Raw green.** `12 passed in 0.28s`

### BP-10 — `vet-receipt.md` × `Tier 2`

- **Guarded element.** The pair (`vet-receipt.md`, `"Tier 2"`). **Axis.** As BP-1.
- **Neutralization.** ` (Tier 2)` at the same anchor.
- **Raw red.**

  ```
  E                   AssertionError: skills/showrunner/reference/vet-receipt.md: retired tier literal 'Tier 2' present
  1 failed, 11 passed in 0.43s
  ```

- **Restore.** Inverse edit. **Restore receipt.** `git status --porcelain` → no output.
- **Raw green.** `12 passed in 0.32s`

### BP-11 — `vet-receipt.md` × `Tier-1`

- **Guarded element.** The pair (`vet-receipt.md`, `"Tier-1"`). **Axis.** As BP-1.
- **Neutralization.** ` (Tier-1)` at the same anchor.
- **Raw red.**

  ```
  E                   AssertionError: skills/showrunner/reference/vet-receipt.md: retired tier literal 'Tier-1' present
  1 failed, 11 passed in 0.26s
  ```

- **Restore.** Inverse edit. **Restore receipt.** `git status --porcelain` → no output.
- **Raw green.** `12 passed in 0.13s`

### BP-12 — `vet-receipt.md` × `Tier-2`

- **Guarded element.** The pair (`vet-receipt.md`, `"Tier-2"`). **Axis.** As BP-1.
- **Neutralization.** ` (Tier-2)` at the same anchor.
- **Raw red.**

  ```
  E                   AssertionError: skills/showrunner/reference/vet-receipt.md: retired tier literal 'Tier-2' present
  1 failed, 11 passed in 0.16s
  ```

- **Restore.** Inverse edit. **Restore receipt.** `git status --porcelain` → no output.
- **Raw green.** `12 passed in 0.14s`

---

### BP-13 — the narrowed pinned heading, owner-decisions leg

- **Guarded element.** `test_disposition_flow.py:_assert_pinned_headings_present`, the pinned
  heading `## The revisit-trigger registry` in
  `skills/showrunner/reference/owner-decisions.md` — the **one** heading the narrowed set still
  pins.
- **Axis.** Presence of that exact heading line in that file — structure, never prose.
- **Neutralization.** The heading at `owner-decisions.md:122` renamed from
  `## The revisit-trigger registry` to `## The revisit trigger registry` (one hyphen removed).
- **Raw red.**

  ```
  E               AssertionError: skills/showrunner/reference/owner-decisions.md: pinned heading missing: '## The revisit-trigger registry'
  1 failed, 11 passed in 0.15s
  ```

- **Restore.** Inverse edit: the hyphen restored.
- **Restore receipt.** `git status --porcelain` → no output.
- **Raw green.** `12 passed in 0.09s`

### BP-14 — the narrowed discuss-open holder pin, surviving leg

- **Guarded element.** `test_disposition_flow.py:_assert_discuss_open_holder_pins`, the surviving
  leg: `skills/discuss-open-decisions/SKILL.md` cites the canonical home path
  `skills/showrunner/reference/owner-decisions.md`.
- **Axis.** Presence of the home path string somewhere in the holder — a citation, not a copy.
  Because the leg is a substring check over the whole file, a partial neutralization proves nothing,
  so **every** occurrence was neutralized.
- **Neutralization.** All three occurrences of `skills/showrunner/reference/owner-decisions.md`
  (lines 23, 47, 88) replaced with `skills/showrunner/reference/owner-decisions-PROBE.md`.
- **Raw red.**

  ```
  E           AssertionError: skills/discuss-open-decisions/SKILL.md: canonical home 'skills/showrunner/reference/owner-decisions.md' not cited
  1 failed, 11 passed in 0.08s
  ```

- **Restore.** Inverse edit over all three occurrences.
- **Restore receipt.** `git status --porcelain` → no output.
- **Raw green.** `12 passed in 0.07s`

### BP-15 — the pinned-heading detector's review-discipline leg

- **Guarded element.** `test_disposition_flow.py:_assert_pinned_headings_present`, the pinned
  heading `### Continuation and the advisor-resolution valve` in `rubric/review-discipline.md`.
  Included because the detector itself was narrowed in this change set: the second leg is proven
  alongside the first rather than assumed still live.
- **Axis.** As BP-13.
- **Neutralization.** The heading at `review-discipline.md:322` renamed from
  `### Continuation and the advisor-resolution valve` to
  `### Continuation and the advisor resolution valve`.
- **Raw red.**

  ```
  E               AssertionError: rubric/review-discipline.md: pinned heading missing: '### Continuation and the advisor-resolution valve'
  1 failed, 11 passed in 0.07s
  ```

- **Restore.** Inverse edit. **Restore receipt.** `git status --porcelain` → no output; `git
  rev-parse HEAD` still `9fe317cbcf7a7b95e1e65b3efde4194d232130fa`.
- **Raw green.** `12 passed in 0.06s`

## No vacuity

- **Trap 1 — precondition instead of consumer.** Each probe mutates the **guarded surface** the
  detector reads, never a helper the tests already assert.
- **Trap 2 — wrong axis.** Every red names the detector's own axis in its own message: the file and
  the literal for BP-1 … BP-12, the file and the missing heading for BP-13 and BP-15, the file and
  the uncited home for BP-14.
- **Trap 3 — one representative.** Twelve pairs, not one literal and not one file; the two narrowed
  detectors are proven on each surviving leg separately.
- **Trap 4 — unreachable path.** Every probe went red where the reasoning said it should, through
  the same file read the detector performs in its default (`texts=None`) path — the path the suite
  actually exercises.

No normalization was applied: no clock, environment, configuration, or concurrency was pinned. No
disclosure under `## When the proof cannot be produced` is owed; every proof was produced.
