# Bite-proof record — the disposition-flow detectors this change set adds or changes (issue #1261)

**Twenty-two proofs, one per guarded element, all run on the final head `b1cbaf1b`** — the head that
carries the review's auto-fix round, which reshaped two of these detectors after an earlier proof
pass. The earlier pass is superseded and is not quoted here; only the final-head experiment stands.

All raw captures are unredacted because none carried a secret, token, private URL, or PII; nothing
was elided, and the record is well inside the 32 KiB per-element and 128 KiB whole-record ceilings.

## Who produced these, and the limitation that carries

**The orchestrator planted and reverted every probe**, not a dispatched implementer. The WO-N order
said so before the work was dispatched: a probe's revert from a dispatched seat has wiped
uncommitted sibling work in this repository before, and the charter assigns the probe mechanics to
the orchestrator anyway. **The limitation is that the same session produced these proofs and re-ran
them.** Every raw capture below is reproduced verbatim rather than summarised, so a reader who does
not trust the summary can re-execute the record.

Every probe was applied as a **targeted, reversible edit through the host's edit action** — never a
whole-file rewrite, never an ad-hoc shell edit — in a **dedicated detached worktree**
(`/private/tmp/wh1261-bp2`) that no other seat was reading. The landed work was committed before the
first probe; `git rev-parse HEAD` read `b1cbaf1b8dd607651700f1cf96a2fd8c324dce24` before and after
the whole pass.

## The guarded-element set

WO-N's order declared the set as *the four tier literals over the enumerated files, and the narrowed
pinned heading*. The review's auto-fix round widened the census and restored two detector legs, so
the set below enumerates the shipped shape at its finest reading — **every independently
neutralizable element**, no equivalence classes, no representative standing for anything
unenumerated.

| Detector | Status vs the base | Guarded elements | Proofs |
|---|---|---|---|
| `_assert_retired_tier_literals_absent` | **new** | 4 censused files × 4 retired literals = **16** | FP-1 … FP-16 |
| `_assert_pinned_headings_present` | **changed** (heading set narrowed, then one member restored) | **4** pinned headings across 2 files | FP-17 … FP-20 |
| `_assert_discuss_open_holder_pins` | **changed** (two legs retired, then restored in a structural form) | **3** legs: home-headings, home-path citation, append-before-propose | FP-17, FP-18 (home-headings leg), FP-21, FP-22 |
| `_assert_retired_vocabulary_absent` | unchanged from the base, byte for byte | — | none owed |
| `_assert_owner_rejected_terms_absent` | unchanged from the base, byte for byte | — | none owed |
| `_assert_registry_marker_home` | unchanged from the base, byte for byte | — | none owed |

The three "unchanged" rows were established by extracting each function from
`origin/main:plugins/superheroes/lib/tests/test_disposition_flow.py` and from the branch head and
comparing them line for line; the comparison is reproduced in the pull request's build record.

**The census's effective surface set.** `_TIER_VOCAB_CENSUS_SURFACES` is `_TOUCHED_FILES +
(_ISSUE_CONTRACT,)` — six files — minus `_TIER_VOCAB_NOT_YET_MIGRATED`
(`owner-decisions.md`, `discuss-open-decisions/SKILL.md`), leaving **four** censused surfaces:
`skills/showrunner/SKILL.md`, `skills/showrunner/reference/vet-receipt.md`,
`skills/showrunner/reference/issue-contract.md`, and `rubric/review-discipline.md`. The two waived
surfaces are the ones that still carry the retired names; they leave the waiver with the change that
renames their text. **The waiver's own behaviour — that a waived surface does not trip the census
while it still carries all four literals — is proven by the green baseline**, which is green with
eleven `Tier[ -][12]` occurrences live in `owner-decisions.md` and two in
`discuss-open-decisions/SKILL.md`.

## Baseline

```
$ git -C /private/tmp/wh1261-bp2 rev-parse --short HEAD
b1cbaf1b
$ git -C /private/tmp/wh1261-bp2 status --porcelain
[no output]
$ /usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-bp2 -m pytest plugins/superheroes/lib/tests/test_disposition_flow.py -q
.............                                                            [100%]
13 passed in 0.11s
```

## FP-1 … FP-16 — the retired-tier-vocabulary census

Axis for every one: **presence of a retired tier literal in a censused shipped surface** — never
absence elsewhere. Failure mode: `AssertionError: <file>: retired tier literal <literal> present`.

One anchor sentence per file; the literal is inserted into it and removed again by the inverse edit.
Restore receipt in every case is `git status --porcelain` over the **whole worktree** coming back
empty — stricter than the neutralized path alone. Raw green after each file's four probes is quoted
at the end of that file's block.

**Anchors.**

- `skills/showrunner/reference/issue-contract.md:153` — `A routed issue that carries the four is gradable at vet without asking anyone what was decided.`
- `skills/showrunner/SKILL.md:467` — `     collector at vet time, unconditionally, so the collector is the complete register by`
- `skills/showrunner/reference/vet-receipt.md:129` — ``reaches the owner by the no-PR presentation rule in `skills/showrunner/reference/closure.md`.``
- `rubric/review-discipline.md:325` — `This is **venue 1** of the residual venue ladder; the ladder's canonical home is`

### `issue-contract.md`

| Proof | Neutralization | Raw red |
|---|---|---|
| **FP-1** | appended ` Tier 1 applies.` | `E  AssertionError: skills/showrunner/reference/issue-contract.md: retired tier literal 'Tier 1' present` / `1 failed, 12 passed in 0.17s` |
| **FP-2** | ` Tier 2 applies.` | `E  AssertionError: skills/showrunner/reference/issue-contract.md: retired tier literal 'Tier 2' present` / `1 failed, 12 passed in 0.12s` |
| **FP-3** | ` Tier-1 applies.` | `E  AssertionError: skills/showrunner/reference/issue-contract.md: retired tier literal 'Tier-1' present` / `1 failed, 12 passed in 0.12s` |
| **FP-4** | ` Tier-2 applies.` | `E  AssertionError: skills/showrunner/reference/issue-contract.md: retired tier literal 'Tier-2' present` / `1 failed, 12 passed in 0.06s` |

**Restore.** Inverse edit removing the appended clause. **Restore receipt.** `git status --porcelain`
→ no output. **Raw green.** `13 passed in 0.36s`

### `showrunner/SKILL.md`

| Proof | Neutralization | Raw red |
|---|---|---|
| **FP-5** | ` (Tier 1)` after `unconditionally` | `E  AssertionError: skills/showrunner/SKILL.md: retired tier literal 'Tier 1' present` / `1 failed, 12 passed in 0.64s` |
| **FP-6** | ` (Tier 2)` | `E  AssertionError: skills/showrunner/SKILL.md: retired tier literal 'Tier 2' present` / `1 failed, 12 passed in 0.65s` |
| **FP-7** | ` (Tier-1)` | `E  AssertionError: skills/showrunner/SKILL.md: retired tier literal 'Tier-1' present` / `1 failed, 12 passed in 0.49s` |
| **FP-8** | ` (Tier-2)` | `E  AssertionError: skills/showrunner/SKILL.md: retired tier literal 'Tier-2' present` / `1 failed, 12 passed in 0.57s` |

**Restore.** Inverse edit. **Restore receipt.** `git status --porcelain` → no output.
**Raw green.** `13 passed in 0.61s`

### `vet-receipt.md`

| Proof | Neutralization | Raw red |
|---|---|---|
| **FP-9** | ` (Tier 1)` before the full stop | `E  AssertionError: skills/showrunner/reference/vet-receipt.md: retired tier literal 'Tier 1' present` / `1 failed, 12 passed in 0.54s` |
| **FP-10** | ` (Tier 2)` | `E  AssertionError: skills/showrunner/reference/vet-receipt.md: retired tier literal 'Tier 2' present` / `1 failed, 12 passed in 0.46s` |
| **FP-11** | ` (Tier-1)` | `E  AssertionError: skills/showrunner/reference/vet-receipt.md: retired tier literal 'Tier-1' present` / `1 failed, 12 passed in 0.36s` |
| **FP-12** | ` (Tier-2)` | `E  AssertionError: skills/showrunner/reference/vet-receipt.md: retired tier literal 'Tier-2' present` / `1 failed, 12 passed in 0.44s` |

**Restore.** Inverse edit. **Restore receipt.** `git status --porcelain` → no output.
**Raw green.** `13 passed in 0.77s`

### `rubric/review-discipline.md` — the surface the widened census newly covers

These four matter most: `review-discipline.md` was **outside** the census before the review's
auto-fix round widened it, so without them the widening would be a claim rather than a receipt.

| Proof | Neutralization | Raw red |
|---|---|---|
| **FP-13** | ` (Tier 1)` after `**venue 1**` | `E  AssertionError: rubric/review-discipline.md: retired tier literal 'Tier 1' present` / `1 failed, 12 passed in 0.80s` |
| **FP-14** | ` (Tier 2)` | `E  AssertionError: rubric/review-discipline.md: retired tier literal 'Tier 2' present` / `1 failed, 12 passed in 0.72s` |
| **FP-15** | ` (Tier-1)` | `E  AssertionError: rubric/review-discipline.md: retired tier literal 'Tier-1' present` / `1 failed, 12 passed in 0.84s` |
| **FP-16** | ` (Tier-2)` | `E  AssertionError: rubric/review-discipline.md: retired tier literal 'Tier-2' present` / `1 failed, 12 passed in 0.45s` |

**Restore.** Inverse edit. **Restore receipt.** `git status --porcelain` → no output.
**Raw green.** `13 passed in 0.82s`

## FP-17 … FP-20 — the pinned headings

Axis: **presence of each pinned heading line in its own file** — structure, never prose.

### FP-17 — `owner-decisions.md` × `## The worth-it gate and the venue ladder`

- **Neutralization.** The heading at `owner-decisions.md:76` renamed to
  `## The worth-it gate and the venue-ladder` (one space became a hyphen).
- **Raw red** — note **two** detectors bit, which is the point: `_assert_pinned_headings_present`
  and the restored home-first leg of `_assert_discuss_open_holder_pins` both read this heading, so
  this proof covers the home-headings leg of the second detector as well.

  ```
  E               AssertionError: skills/showrunner/reference/owner-decisions.md: pinned heading missing: '## The worth-it gate and the venue ladder'
  E               AssertionError: skills/showrunner/reference/owner-decisions.md: pinned heading missing: '## The worth-it gate and the venue ladder'
  2 failed, 11 passed in 0.92s
  ```

- **Restore.** Inverse edit. **Restore receipt.** `git status --porcelain` → no output.
  **Raw green.** `13 passed in 0.65s`

### FP-18 — `owner-decisions.md` × `## The revisit-trigger registry`

- **Neutralization.** The heading at `owner-decisions.md:122` renamed to
  `## The revisit trigger registry` (one hyphen removed).
- **Raw red** — again two detectors, for the same reason:

  ```
  E               AssertionError: skills/showrunner/reference/owner-decisions.md: pinned heading missing: '## The revisit-trigger registry'
  E               AssertionError: skills/showrunner/reference/owner-decisions.md: pinned heading missing: '## The revisit-trigger registry'
  2 failed, 11 passed in 0.62s
  ```

- **Restore.** Inverse edit. **Restore receipt.** `git status --porcelain` → no output.
  **Raw green.** `13 passed in 0.72s`

### FP-19 — `review-discipline.md` × `### Continuation and the advisor-resolution valve`

- **Neutralization.** The heading at `review-discipline.md:323` renamed to
  `### Continuation and the advisor resolution valve`.
- **Raw red.**

  ```
  E               AssertionError: rubric/review-discipline.md: pinned heading missing: '### Continuation and the advisor-resolution valve'
  1 failed, 12 passed in 0.72s
  ```

- **Restore.** Inverse edit.

### FP-20 — `review-discipline.md` × `### Standing authorization — venue-1 folds`

- **Neutralization.** The heading at `review-discipline.md:338` renamed to
  `### Standing authorization — venue 1 folds`.
- **Raw red.**

  ```
  E               AssertionError: rubric/review-discipline.md: pinned heading missing: '### Standing authorization — venue-1 folds'
  1 failed, 12 passed in 0.61s
  ```

- **Restore.** Inverse edit. **Restore receipt** (covering FP-19 and FP-20): `git status
  --porcelain` → no output. **Raw green.** `13 passed in 0.63s`

## FP-21, FP-22 — the discuss-open holder pins

The third leg of this detector, the home-headings assertion, is proven by FP-17 and FP-18 above.

### FP-21 — the home-path citation leg

- **Axis.** Presence of the home's path string somewhere in the holder — a citation, not a copy.
  Because the leg is a substring check over the whole file, a partial neutralization would prove
  nothing, so **every** occurrence was neutralized.
- **Neutralization.** All three occurrences of `skills/showrunner/reference/owner-decisions.md` in
  `skills/discuss-open-decisions/SKILL.md` (lines 23, 47, 88) replaced with
  `skills/showrunner/reference/owner-decisions-PROBE.md`.
- **Raw red.**

  ```
  E           AssertionError: skills/discuss-open-decisions/SKILL.md: canonical home 'skills/showrunner/reference/owner-decisions.md' not cited
  1 failed, 12 passed in 0.63s
  ```

- **Restore.** Inverse edit over all three occurrences.

### FP-22 — the append-before-propose content leg

- **Axis.** Presence of the append-before-propose clause in the holder — the owner-ruled ordering
  that the appending happens *before* the item is proposed.
- **Neutralization.** Both occurrences of `**before** it is proposed in this session's delivery
  message` changed to `*before* it is proposed in this session's delivery message` — a
  **formatting-only** mutation, deliberately chosen because it is the weakest change that still
  breaks the pin, and because it demonstrates the brittleness this leg carries (recorded as a
  disclosed follow-up in the pull request body).
- **Raw red.**

  ```
  E           AssertionError: skills/discuss-open-decisions/SKILL.md: append-before-propose pin "**before** it is proposed in this session's delivery message" missing
  1 failed, 12 passed in 0.66s
  ```

- **Restore.** Inverse edit. **Restore receipt** (covering FP-21 and FP-22):
  `git status --porcelain` → no output; `git rev-parse HEAD` still
  `b1cbaf1b8dd607651700f1cf96a2fd8c324dce24`. **Raw green.** `13 passed in 0.34s`

## No vacuity

- **Trap 1 — precondition instead of consumer.** Every probe mutates the **guarded documentation
  surface** the detector reads, never a helper the tests already assert.
- **Trap 2 — wrong axis.** Every red names the detector's own axis in its own message: the file and
  the literal for FP-1 … FP-16, the file and the missing heading for FP-17 … FP-20, the uncited home
  for FP-21, the missing clause for FP-22.
- **Trap 3 — one representative.** Sixteen (file, literal) pairs, not one literal and not one file;
  four pinned headings, not one; each surviving leg of the two changed detectors proven separately.
  The census's newly-covered surface (`review-discipline.md`) is proven on all four literals rather
  than assumed to inherit the others' coverage.
- **Trap 4 — unreachable path.** Every probe went red where the reasoning said it should, through
  the same file read the detector performs in its default (`texts=None`) path — the path the suite
  actually exercises.

No normalization was applied: no clock, environment, configuration, or concurrency was pinned. No
disclosure under *When the proof cannot be produced* is owed; every proof was produced.

## Why this head is the final head's experiment

The only commit after `b1cbaf1b` on this branch is the one that adds this record file. The detector
reads six named documentation surfaces and never the test tree, and bite-proof records are
categorically outside every content census, so adding this file cannot change any of the twenty-two
experiments above. The pull request's build record carries the mechanical check: `git diff
b1cbaf1b..HEAD` over the detector module and the six census surfaces is empty, plus a full green run
on the true final head.
