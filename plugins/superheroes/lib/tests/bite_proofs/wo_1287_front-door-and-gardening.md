# Bite-proof record — the detectors this change set adds or changes (issue #1287)

**Twenty-four proofs, one per guarded element, every one run on the final head `8ba125e8`.** An
earlier full pass ran at `851a72ff` and was superseded when WO-F added the contract-literal pin; only
the final-head experiment stands and is quoted here.

All raw captures are unredacted because none carried a secret, token, private URL, or PII. Nothing
was elided; the record is well inside the 32 KiB per-element and 128 KiB whole-record ceilings.

## Who produced these, and the limitation that carries

**The orchestrator planted and reverted every probe**, not a dispatched implementer, and each work
order said so before it was dispatched ("Mutation probes are not yours"). Two reasons: a probe's
revert from a dispatched seat has wiped uncommitted sibling work in this repository before, and the
builder charter assigns the probe mechanics to the orchestrator. **The limitation is that the same
session produced these proofs and re-ran them.** Every raw capture below is reproduced verbatim
rather than summarised, so a reader who does not trust the summary can re-execute the record.

Every probe was applied as a **targeted, reversible edit through the host's edit action** — never a
whole-file rewrite, never an ad-hoc shell edit — in a **dedicated detached worktree**
(`/private/tmp/wh1287-bp`) that no other seat was reading. All landed work was committed before the
first probe. `git rev-parse HEAD` read `8ba125e84cd1b62b4556e5691d001f4d7963a944` before and after
the whole pass, and `git status --porcelain` was **empty** at the end.

## The order gap, declared

**None of this build's work orders declared a guarded-element set.** The orders asked each
implementer for "one line naming the guarded element" per new or changed leg, which is a report
field, not the up-front declaration `rubric/bite-proof.md` requires. The gap is the orchestrator's
(the author of every order in this build), and it is flagged here rather than papered over. The
enumeration below is therefore the rubric's fallback: **every independently neutralizable element
each changed detector guards**, at its finest reading, with no equivalence classes and no
representative standing for anything unenumerated.

## The guarded-element set

| Detector | Status vs the base | Guarded elements | Proofs |
|---|---|---|---|
| `_assert_retired_gate_literals_absent` | **new** | **2** retired gate literals over the shipped-markdown walk | FP-1, FP-2 |
| `_assert_pinned_headings_present` | **changed** (owner-decisions heading set replaced) | **10** pinned `owner-decisions.md` headings | FP-3 … FP-12 |
| `_assert_retired_tier_literals_absent` | **changed** (waiver emptied) | **8** newly censused pairs: 2 surfaces × 4 retired literals | FP-13 … FP-20 |
| `_assert_discuss_open_holder_pins`, ordering leg | **changed** (raw substring → normalized ordering) | **1** ordering leg, plus its formatting-tolerance behaviour | FP-21, FP-22 |
| `front_door.grade`, unstamped-`p0Definition` branch | **changed** (fall-open → fail-closed) | **1** refusal branch | FP-23 |
| `test_p0_definition_unstamped_pins_contract_literal` | **new** | **1** token spelling | FP-24 |

The module's two `review-discipline.md` pinned headings, `_assert_retired_vocabulary_absent`,
`_assert_owner_rejected_terms_absent`, and `_assert_registry_marker_home` are **unchanged from the
base byte for byte** and owe no proof.

**The walk's completeness is what FP-1 and FP-2 prove.** Both plant in
`plugins/superheroes/rubric/covenant.md` — a file **outside** the module's `_TOUCHED_FILES` tuple and
outside every other enumeration in the module. A tuple-scoped census would have stayed green on
either plant; the walk goes red and names the file. **The exclusion pair's own behaviour** — that
`lib/tests/` and `CHANGELOG.md` do not trip the walk — is proven by the green baseline, which is
green while `CHANGELOG.md` carries the retired gate heading in its release history and this module
carries both literals in order to census them.

## Baseline

```
$ git -C /private/tmp/wh1287-bp rev-parse HEAD
8ba125e84cd1b62b4556e5691d001f4d7963a944
$ git -C /private/tmp/wh1287-bp status --porcelain
(empty)
$ pytest plugins/superheroes/lib/tests/test_disposition_flow.py -q
................                                                         [100%]
16 passed in 0.06s
```

Every run below used
`/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-bp -m pytest …` from
`/private/tmp/wh1287-bp`. The `pycache_prefix` is the **pinned condition**: Apple's Python caches
bytecode outside the tree, and a same-size, same-second edit — the shape of every probe here — then
runs stale bytecode. It pins nothing about production behaviour; it makes the probe observe the file
it just edited.

---

## FP-1 — the retired gate heading, over the shipped-markdown walk

- **Guarded element:** `_RETIRED_GATE_HEADING` (`## The worth-it gate and the venue ladder`) in
  `test_disposition_flow.py`. **Axis:** presence of the retired heading in a shipped markdown surface.
- **Neutralization:** inserted the heading into `plugins/superheroes/rubric/covenant.md`, a file no
  tuple in the module enumerates:

  ```
   # The superheroes covenant
  +
  +## The worth-it gate and the venue ladder
  ```

- **Raw red:**

  ```
  E   AssertionError: rubric/covenant.md: retired gate literal '## The worth-it gate and the venue ladder' present
  1 failed in 0.12s
  ```

- **Restore:** inverse edit, removing the two inserted lines.
- **Restore receipt / raw green:** see the end-of-class receipt under FP-2.

## FP-2 — the bare retired gate phrase

- **Guarded element:** `_RETIRED_GATE_PHRASE` (`worth-it gate`). **Axis:** presence of the retired
  phrase in a shipped markdown surface, independent of the heading form.
- **Neutralization:** `# The superheroes covenant` → `# The superheroes covenant (a worth-it gate note)`
  in `plugins/superheroes/rubric/covenant.md`.
- **Raw red:**

  ```
  E   AssertionError: rubric/covenant.md: retired gate literal 'worth-it gate' present
  1 failed in 0.11s
  ```

- **Restore:** inverse edit back to `# The superheroes covenant`.
- **Restore receipt:** `git status --porcelain` → empty.
- **Raw green:**

  ```
  .                                                                        [100%]
  1 passed in 0.05s
  ```

---

## FP-3 … FP-12 — the ten pinned `owner-decisions.md` headings

Each proof renamed **one** heading line in
`plugins/superheroes/skills/showrunner/reference/owner-decisions.md` through a targeted edit, ran
`test_disposition_flow.py::test_new_section_headings_present` with the detector unedited, then
reverted with the inverse edit before the next. **Axis for all ten:** presence of that exact heading
line in that file — structure, never prose.

| # | Guarded element (heading) | Neutralization | Raw red |
|---|---|---|---|
| FP-3 | `## The filter — what is the owner's, and on what grounds` | apostrophe dropped: `owners` | ``AssertionError: skills/showrunner/reference/owner-decisions.md: pinned heading missing: "## The filter — what is the owner's, and on what grounds"`` |
| FP-4 | `## The per-item spine` | hyphen dropped: `per item` | `AssertionError: …: pinned heading missing: '## The per-item spine'` |
| FP-5 | `## The front door` | `door` → `doorway` | `AssertionError: …: pinned heading missing: '## The front door'` |
| FP-6 | `## The venue ladder` | pluralised: `ladders` | `AssertionError: …: pinned heading missing: '## The venue ladder'` |
| FP-7 | `## The revisit-trigger registry` | hyphen dropped: `revisit trigger` | `AssertionError: …: pinned heading missing: '## The revisit-trigger registry'` |
| FP-8 | `## Delivery mechanics` | singularised: `mechanic` | `AssertionError: …: pinned heading missing: '## Delivery mechanics'` |
| FP-9 | `## Formatting — one block per spine section` | em dash → hyphen | `AssertionError: …: pinned heading missing: '## Formatting — one block per spine section'` |
| FP-10 | `## Where the items come from, and the bound on that sweep` | comma dropped | `AssertionError: …: pinned heading missing: '## Where the items come from, and the bound on that sweep'` |
| FP-11 | `## What batch-1 execution may and may not do` | hyphen dropped: `batch 1` | `AssertionError: …: pinned heading missing: '## What batch-1 execution may and may not do'` |
| FP-12 | `## The collector preamble — canonical snippet` | `the` inserted before `canonical` | `AssertionError: …: pinned heading missing: '## The collector preamble — canonical snippet'` |

Each red names **exactly the one heading neutralized** and no other — which is the evidence that the
ten are independently guarded rather than one representative standing for ten. Every `…` above elides
only the repeated file path `skills/showrunner/reference/owner-decisions.md`, shown in full on FP-3.

- **Restore:** ten inverse edits, one per proof, applied immediately after each red.
- **Restore receipt:** `git status --porcelain` → empty after the class.
- **Raw green:**

  ```
  .                                                                        [100%]
  1 passed in 0.09s
  ```

---

## FP-13 … FP-20 — the eight newly censused tier-literal pairs

Emptying `_TIER_VOCAB_NOT_YET_MIGRATED` brings two surfaces into the tier census for the first time.
Each of the eight (surface, literal) pairs is independently neutralizable, so each gets its own
plant, red, and revert, running
`test_disposition_flow.py::test_retired_tier_literals_absent` with the detector unedited. **Axis for
all eight:** presence of that retired literal in that censused surface.

Plant site in `owner-decisions.md`: `…on every item that passes the filter:` →
`…on every item that passes the filter (<literal>):`.
Plant site in `discuss-open-decisions/SKILL.md`: `## Step 4 — Deliver batch 1` →
`## Step 4 — Deliver batch 1 (<literal>)`.

| # | Surface | Literal | Raw red |
|---|---|---|---|
| FP-13 | `owner-decisions.md` | `Tier 1` | `AssertionError: skills/showrunner/reference/owner-decisions.md: retired tier literal 'Tier 1' present` |
| FP-14 | `owner-decisions.md` | `Tier 2` | `AssertionError: skills/showrunner/reference/owner-decisions.md: retired tier literal 'Tier 2' present` |
| FP-15 | `owner-decisions.md` | `Tier-1` | `AssertionError: skills/showrunner/reference/owner-decisions.md: retired tier literal 'Tier-1' present` |
| FP-16 | `owner-decisions.md` | `Tier-2` | `AssertionError: skills/showrunner/reference/owner-decisions.md: retired tier literal 'Tier-2' present` |
| FP-17 | `discuss-open-decisions/SKILL.md` | `Tier 1` | `AssertionError: skills/discuss-open-decisions/SKILL.md: retired tier literal 'Tier 1' present` |
| FP-18 | `discuss-open-decisions/SKILL.md` | `Tier 2` | `AssertionError: skills/discuss-open-decisions/SKILL.md: retired tier literal 'Tier 2' present` |
| FP-19 | `discuss-open-decisions/SKILL.md` | `Tier-1` | `AssertionError: skills/discuss-open-decisions/SKILL.md: retired tier literal 'Tier-1' present` |
| FP-20 | `discuss-open-decisions/SKILL.md` | `Tier-2` | `AssertionError: skills/discuss-open-decisions/SKILL.md: retired tier literal 'Tier-2' present` |

Between FP-16 and FP-17 the `owner-decisions.md` plant was reverted first; `git status --porcelain`
at FP-17 read exactly `M plugins/superheroes/skills/discuss-open-decisions/SKILL.md`, which is the
evidence that FP-17's red came from the walk-skill plant and not from residue of the previous class.

- **Restore:** eight inverse edits, one per proof.
- **Restore receipt and raw green:** carried by the end-of-pass receipt below.

---

## FP-21 — the append-before-propose ordering leg

- **Guarded element:** `_assert_append_before_propose_ordering` against
  `skills/discuss-open-decisions/SKILL.md`. **Axis:** the **ordering** — appended *before* proposed —
  not the sentence's characters.
- **Neutralization:** both occurrences of
  `**before** it is proposed in this session's delivery message` replaced with
  `right after it is put to the owner in this session's delivery message`, which **inverts the
  ordering while leaving the sentence well-formed English**.
- **Raw red:**

  ```
  E   AssertionError: skills/discuss-open-decisions/SKILL.md: append-before-propose ordering missing
  ```

- **Restore:** inverse edit restoring both occurrences.

## FP-22 — the same leg's formatting tolerance, with an A/B against the pin it replaces

This is the **changed** half of the leg: the retired guard was a raw substring, so a formatting-only
edit failed CI while the guarded ordering was untouched. The proof is the discrimination.

- **Neutralization:** a **formatting-only** edit — emphasis markers removed and the sentence reflowed
  across a line break — leaving the ordering intact.
- **New detector, raw result:**

  ```
  .                                                                        [100%]
  1 passed in 0.13s
  ```

- **A/B against the retired pin, same text:**

  ```
  retired raw-substring pin would be: RED
  ```

  Read together with FP-21: the new leg goes **red** when the ordering is inverted and stays
  **green** under formatting-only change, while the pin it replaces would have gone red on the
  formatting change alone. That is the axis moving from characters to ordering.

- **Restore:** inverse edit restoring the emphasised single-line sentence.

---

## FP-23 — the front door's unstamped-`p0Definition` refusal

- **Guarded element:** `front_door.py`'s `_p0_policy` branch
  `if p0_entry.get("source") != "stamped":`. **Axis:** **refusal** — that an ungoverned P0 claim is
  refused rather than graded. Not presence, not a count.
- **Neutralization:** the fall-open this change removed, restored verbatim in behaviour:

  ```
   if p0_entry.get("source") != "stamped":
  -    return None, None, REASON_P0_DEFINITION_UNSTAMPED
  +    return {_ladder_band_names(ladder_entry.get("effective"))[0]}, None, None
  ```

- **Raw red** (detectors unedited):

  ```
  FAILED plugins/superheroes/lib/tests/test_front_door.py::test_p0_unstamped_definition_refuses_top_band_field
  FAILED plugins/superheroes/lib/tests/test_front_door.py::test_p0_unstamped_definition_refuses_top_band_lab
  FAILED plugins/superheroes/lib/tests/test_front_door.py::test_p0_unstamped_definition_refuses_non_top_band
  FAILED plugins/superheroes/lib/tests/test_front_door.py::test_p0_definition_unstamped_pins_contract_literal
  4 failed, 30 deselected in 7.38s
  ```

  with the discriminating assertion reading `assert 'graded' == 'refused'` — the refusal axis, not an
  adjacent one.
- **Restore:** inverse edit restoring the refusal return.

## FP-24 — the refusal token's spelling

The three FP-23 tests assert `FD.REASON_P0_DEFINITION_UNSTAMPED`, the **symbol**, so they stay green
under any value the constant holds. The project's keep-or-retire record and the shipped door doctrine
both match this token by its characters, which makes it an external-contract constant.

- **Guarded element:** the literal `"p0-definition-unstamped"`. **Axis:** the token's **spelling**.
- **Neutralization:** the constant renamed at its definition, leaving every call site untouched:

  ```
  -REASON_P0_DEFINITION_UNSTAMPED = "p0-definition-unstamped"
  +REASON_P0_DEFINITION_UNSTAMPED = "p0-definition-not-stamped"
  ```

- **Raw red:**

  ```
  E   AssertionError: assert 'p0-definition-not-stamped' == 'p0-definition-unstamped'
  E     - p0-definition-unstamped
  E     ?               -
  E     + p0-definition-not-stamped
  E     ?                +++
  FAILED plugins/superheroes/lib/tests/test_front_door.py::test_p0_definition_unstamped_pins_contract_literal
  1 failed, 3 passed, 30 deselected in 4.74s
  ```

  **`1 failed, 3 passed` is the whole point of this proof.** The three symbol-spelled tests stayed
  green through a rename that would have left the keep-or-retire condition and the door's prose
  pointing at a token no longer emitted; only the literal pin caught it.

- **Restore:** inverse edit restoring the original spelling.

---

## End-of-pass receipt

```
$ git -C /private/tmp/wh1287-bp rev-parse HEAD
8ba125e84cd1b62b4556e5691d001f4d7963a944
$ git -C /private/tmp/wh1287-bp status --porcelain
(empty)
$ pytest plugins/superheroes/lib/tests/test_disposition_flow.py plugins/superheroes/lib/tests/test_front_door.py -q
..................................................                       [100%]
50 passed in 76.75s (0:01:16)
```

No probe residue. Nothing was edited on the build branch by this pass; the probe worktree is detached
and was left at the final head with an empty porcelain.
