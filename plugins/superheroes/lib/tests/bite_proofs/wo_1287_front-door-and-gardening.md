# Bite-proof record — the detectors this change set adds or changes (issue #1287)

**Thirty-two proofs over twelve guarded elements' worth of detector surface.** Twelve of them were
re-earned on the final head `62cc568e` after the review's two auto-fix rounds reshaped three
detectors; the other twenty were earned at `099a4b00` on detector code that is **byte-identical** at
the final head, with the equivalence receipt printed below. Both facts are stated rather than
implied — see **Which proofs ran on which head, and why**.

All raw captures are unredacted because none carried a secret, token, private URL, or PII. Nothing
was elided; the record is well inside the 32 KiB per-element and 128 KiB whole-record ceilings.

## Who produced these, and the limitation that carries

**The orchestrator planted and reverted every probe**, not a dispatched implementer, and every work
order said so before it was dispatched ("Mutation probes are not yours"). Two reasons: a probe's
revert from a dispatched seat has wiped uncommitted sibling work in this repository before, and the
builder charter assigns the probe mechanics to the orchestrator. **The limitation is that the same
session produced these proofs and re-ran them.** Every raw capture below is reproduced verbatim
rather than summarised, so a reader who does not trust the summary can re-execute the record.

Every probe was applied as a **targeted, reversible edit through the host's edit action** — never a
whole-file rewrite, never an ad-hoc shell edit — in a **dedicated detached worktree**
(`/private/tmp/wh1287-bp`) that no other seat was reading. All landed work was committed before each
pass, and `git status --porcelain` was **empty** at the end of each.

## The order gap, declared

**None of this build's work orders declared a guarded-element set.** The orders asked each
implementer for "one line naming the guarded element" per new or changed leg, which is a report
field, not the up-front declaration `rubric/bite-proof.md` requires. The gap is the orchestrator's —
the author of every order in this build — and it is flagged here rather than papered over. The
enumeration below is the rubric's fallback: **every independently neutralizable element each changed
detector guards**, at its finest reading, with no equivalence classes and no representative standing
for anything unenumerated.

Two of the detectors were reshaped **by the review's own auto-fix rounds**, not by a work order, so
for those the declaration could not have preceded the change at all; the enumeration below is the
first one that exists for them.

## Which proofs ran on which head, and why

`rubric/bite-proof.md`'s rule is that a proof is earned on the head that ships. An earlier full pass
ran at `099a4b00`. The review loop then landed two auto-fix commits and one scope repair, so the
final head is `62cc568e`.

- **FP-21 … FP-32 (twelve proofs) were re-earned on `62cc568e` itself.** They cover every detector
  the auto-fix rounds touched: the reshaped append-before-propose ordering leg, the brand-new
  retired-door-grading census, the front door's refusal branch, and the reshaped refusal-token
  guard. Their earlier recorded forms are **superseded and are not quoted here**; one of them
  (the old FP-24, which asserted a hand-typed literal the auto-fix deleted) was caught as stale by an
  independent fix auditor, which is why this record was rewritten rather than amended.
- **FP-1 … FP-20 (twenty proofs) ran at `099a4b00`.** Their detectors and element tuples are
  byte-identical at the final head. The receipt:

  ```
  comparing detector bodies and element tuples, 099a4b00 vs 62cc568e (final head)

  _assert_pinned_headings_present               identical=True  sha=8b73c1642ba9
  _assert_retired_tier_literals_absent          identical=True  sha=2a9f2c0f4882
  _assert_retired_gate_literals_absent          identical=True  sha=46a8a15b0a91
  _PINNED_OWNER_DECISIONS_HEADINGS              identical=True
  _RETIRED_TIER_LITERALS                        identical=True
  _TIER_VOCAB_NOT_YET_MIGRATED                  identical=True
  _RETIRED_GATE_LITERALS                        identical=True
  _RETIRED_GATE_WALK_EXCLUSIONS                 identical=True
  _TOUCHED_FILES                                identical=True
  ```

  **The honest limit of that receipt**, stated rather than left for a reader to notice: it proves the
  detector code and its element sets did not move, not that re-running each plant on the final head
  would necessarily reproduce. The guarded *surfaces* did move (the auto-fix rounds edited
  `owner-decisions.md`), and a plant's red depends on the surface as well as the detector. That is
  the residual, and it is the advisor's to weigh; the twelve proofs that did run on the final head
  are the ones whose detectors changed, which is where staleness actually bites.

## The guarded-element set

| Detector | Status vs the base | Guarded elements | Proofs | Head |
|---|---|---|---|---|
| `_assert_retired_gate_literals_absent` | **new** (WO-C) | **2** retired gate literals over the shipped-markdown walk | FP-1, FP-2 | `099a4b00` |
| `_assert_pinned_headings_present` | **changed** (WO-C; owner-decisions heading set replaced) | **10** pinned `owner-decisions.md` headings | FP-3 … FP-12 | `099a4b00` |
| `_assert_retired_tier_literals_absent` | **changed** (WO-C; waiver emptied) | **8** newly censused pairs: 2 surfaces × 4 retired literals | FP-13 … FP-20 | `099a4b00` |
| `_assert_append_before_propose_ordering` | **changed twice** (WO-C, then reshaped by both auto-fix rounds) | **4**: 2 pinned clauses × {inversion, absence} | FP-21 … FP-24 | **`62cc568e`** |
| `_assert_retired_door_grading_literals_absent` | **new** (auto-fix round 2) | **5**: the `gate verdict` literal over 5 censused surfaces | FP-25 … FP-29 | **`62cc568e`** |
| `front_door.grade`, unstamped-`p0Definition` branch | **changed** (WO-D) | **1** refusal branch | FP-30 | **`62cc568e`** |
| `test_p0_definition_unstamped_token_docs_follow_home` | **new** (auto-fix round 1, replacing WO-F's literal pin) | **3**: the token's spelling at its home, plus its presence in each of 2 doc copies | FP-31, FP-32 (+ the home half, proven by FP-31) | **`62cc568e`** |

`_assert_retired_vocabulary_absent`, `_assert_owner_rejected_terms_absent`,
`_assert_registry_marker_home`, and the two `review-discipline.md` pinned headings are **unchanged
from the base byte for byte** and owe no proof.

**The walk's completeness is what FP-1 and FP-2 prove.** Both plant in
`plugins/superheroes/rubric/covenant.md` — a file **outside** the module's `_TOUCHED_FILES` tuple and
outside every other enumeration in the module. A tuple-scoped census would have stayed green on
either plant; the walk goes red and names the file. **The exclusion pair's own behaviour** — that
`lib/tests/` and `CHANGELOG.md` do not trip the walk — is proven by the green baseline, which is
green while `CHANGELOG.md` carries the retired gate heading in its release history and this module
and this record carry the literals in order to census and to prove them.

## Baseline (final-head pass)

```
$ git -C /private/tmp/wh1287-bp rev-parse HEAD
62cc568e8f2c85b6dc3bb43dec4f49e1839e18e7
$ git -C /private/tmp/wh1287-bp status --porcelain
(empty)
$ pytest plugins/superheroes/lib/tests/test_disposition_flow.py -q
....................                                                     [100%]
20 passed in 0.09s
```

Every run used `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-bp -m pytest …`
from `/private/tmp/wh1287-bp`. The `pycache_prefix` is the **pinned condition**: Apple's Python
caches bytecode outside the tree, and a same-size, same-second edit — the shape of every probe here —
then runs stale bytecode. It pins nothing about production behaviour; it makes the probe observe the
file it just edited.

---

## FP-1 — the retired gate heading, over the shipped-markdown walk

- **Guarded element:** `_RETIRED_GATE_HEADING` (`## The worth-it gate and the venue ladder`).
  **Axis:** presence of the retired heading in a shipped markdown surface.
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

- **Restore:** inverse edit removing the two inserted lines. **Restore receipt / raw green:** under FP-2.

## FP-2 — the bare retired gate phrase

- **Guarded element:** `_RETIRED_GATE_PHRASE` (`worth-it gate`). **Axis:** presence of the retired
  phrase, independent of the heading form.
- **Neutralization:** `# The superheroes covenant` → `# The superheroes covenant (a worth-it gate note)`.
- **Raw red:**

  ```
  E   AssertionError: rubric/covenant.md: retired gate literal 'worth-it gate' present
  1 failed in 0.11s
  ```

- **Restore:** inverse edit. **Restore receipt:** `git status --porcelain` → empty. **Raw green:**

  ```
  .                                                                        [100%]
  1 passed in 0.05s
  ```

---

## FP-3 … FP-12 — the ten pinned `owner-decisions.md` headings

Each proof renamed **one** heading line through a targeted edit, ran
`test_disposition_flow.py::test_new_section_headings_present` with the detector unedited, then
reverted before the next. **Axis for all ten:** presence of that exact heading line in that file —
structure, never prose.

| # | Guarded element (heading) | Neutralization | Raw red |
|---|---|---|---|
| FP-3 | `## The filter — what is the owner's, and on what grounds` | apostrophe dropped | ``AssertionError: skills/showrunner/reference/owner-decisions.md: pinned heading missing: "## The filter — what is the owner's, and on what grounds"`` |
| FP-4 | `## The per-item spine` | hyphen dropped | `AssertionError: …: pinned heading missing: '## The per-item spine'` |
| FP-5 | `## The front door` | `door` → `doorway` | `AssertionError: …: pinned heading missing: '## The front door'` |
| FP-6 | `## The venue ladder` | pluralised | `AssertionError: …: pinned heading missing: '## The venue ladder'` |
| FP-7 | `## The revisit-trigger registry` | hyphen dropped | `AssertionError: …: pinned heading missing: '## The revisit-trigger registry'` |
| FP-8 | `## Delivery mechanics` | singularised | `AssertionError: …: pinned heading missing: '## Delivery mechanics'` |
| FP-9 | `## Formatting — one block per spine section` | em dash → hyphen | `AssertionError: …: pinned heading missing: '## Formatting — one block per spine section'` |
| FP-10 | `## Where the items come from, and the bound on that sweep` | comma dropped | `AssertionError: …: pinned heading missing: '## Where the items come from, and the bound on that sweep'` |
| FP-11 | `## What batch-1 execution may and may not do` | hyphen dropped | `AssertionError: …: pinned heading missing: '## What batch-1 execution may and may not do'` |
| FP-12 | `## The collector preamble — canonical snippet` | `the` inserted | `AssertionError: …: pinned heading missing: '## The collector preamble — canonical snippet'` |

Each red names **exactly the one heading neutralized** and no other — the evidence that the ten are
independently guarded rather than one representative standing for ten. Every `…` elides only the
repeated file path, shown in full on FP-3.

- **Restore:** ten inverse edits, one per proof. **Restore receipt:** `git status --porcelain` →
  empty. **Raw green:** `1 passed in 0.09s`.

---

## FP-13 … FP-20 — the eight newly censused tier-literal pairs

Emptying `_TIER_VOCAB_NOT_YET_MIGRATED` brings two surfaces into the tier census for the first time.
Each (surface, literal) pair is independently neutralizable, so each got its own plant, red, and
revert, running `test_retired_tier_literals_absent` with the detector unedited. **Axis for all
eight:** presence of that retired literal in that censused surface.

Plant site in `owner-decisions.md`: `…passes the filter:` → `…passes the filter (<literal>):`.
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
at FP-17 read exactly `M plugins/superheroes/skills/discuss-open-decisions/SKILL.md`, the evidence
that FP-17's red came from the walk-skill plant and not from residue of the previous class.

- **Restore:** eight inverse edits, one per proof, each applied immediately after its red.

---

## FP-21 … FP-24 — the reshaped append-before-propose ordering leg *(final head)*

The leg was rebuilt twice during review. It now finds each of **two pinned clauses** in
`skills/discuss-open-decisions/SKILL.md`, bounds a window from the clause marker to the phrase
`proposed in this session's delivery message`, and inside that window refuses an
`append…after…proposed` ordering, requires an `append…before…proposed` ordering, and finally requires
that **both** clauses were found. That is four independently neutralizable elements: each clause can
be **inverted** or **removed**.

| # | Guarded element | Axis | Neutralization | Raw red |
|---|---|---|---|---|
| FP-21 | clause 1, `append it to the collector immediately` | ordering | `**before**` → `**after**` in that clause only | `AssertionError: skills/discuss-open-decisions/SKILL.md: append-after-propose in pinned ordering clause` |
| FP-22 | clause 2, `every owner call is appended` | ordering | `**before**` → `**after**` in that clause only | `AssertionError: skills/discuss-open-decisions/SKILL.md: append-after-propose in pinned ordering clause` |
| FP-23 | clause 2, presence | clause-count floor | `every owner call` → `every owner claim`, so the marker no longer matches | `AssertionError: skills/discuss-open-decisions/SKILL.md: expected 2 pinned append-before-propose clauses, found 1` |
| FP-24 | clause 1, presence | clause-count floor | `append it to the collector` → `add it to the collector` | `AssertionError: skills/discuss-open-decisions/SKILL.md: expected 2 pinned append-before-propose clauses, found 1` |

**Why FP-21 and FP-22 matter more than they look.** The leg this replaced normalized the whole
document and searched it with an unbounded `.*?` under `re.DOTALL`; five independent review seats
demonstrated that inverting **both** clauses left it green, because the three tokens could be
supplied by three unrelated sentences. FP-21 and FP-22 each invert **one** clause and each goes red —
which is strictly stronger than what the superseded detector could do with both inverted.

- **Restore:** four inverse edits. **Restore receipt:** `git status --porcelain` → empty.
  **Raw green:** `1 passed in 0.08s`.

---

## FP-25 … FP-29 — the new retired-door-grading census *(final head)*

Added by the review's second auto-fix round when the home's `gate verdict` wording was replaced by
`door grading`. It censuses the literal `gate verdict` across the module's five `_TOUCHED_FILES`.
Each (surface, literal) pair is independently neutralizable. **Axis for all five:** presence of the
retired contract literal in that censused surface.

| # | Surface | Neutralization | Raw red |
|---|---|---|---|
| FP-25 | `owner-decisions.md` | heading suffixed `(gate verdict)` | `AssertionError: skills/showrunner/reference/owner-decisions.md: retired door-grading literal 'gate verdict' present` |
| FP-26 | `discuss-open-decisions/SKILL.md` | heading suffixed `(gate verdict)` | `AssertionError: skills/discuss-open-decisions/SKILL.md: retired door-grading literal 'gate verdict' present` |
| FP-27 | `rubric/review-discipline.md` | heading suffixed `(gate verdict)` | `AssertionError: rubric/review-discipline.md: retired door-grading literal 'gate verdict' present` |
| FP-28 | `vet-receipt.md` | heading suffixed `(gate verdict)` | `AssertionError: skills/showrunner/reference/vet-receipt.md: retired door-grading literal 'gate verdict' present` |
| FP-29 | `showrunner/SKILL.md` | sentence suffixed `(gate verdict)` | `AssertionError: skills/showrunner/SKILL.md: retired door-grading literal 'gate verdict' present` |

Each red names exactly the one surface planted. **Restore:** five inverse edits.

**Disclosed coverage limit of this detector, not of its proof:** it reads `_TOUCHED_FILES` — five
files — not a tree walk, so a `gate verdict` reintroduced in a shipped surface outside that tuple is
uncensused. The proofs establish that all five enumerated members bite; they cannot establish reach
the detector does not have.

---

## FP-30 — the front door's unstamped-`p0Definition` refusal *(final head)*

- **Guarded element:** `front_door.py`'s `_p0_policy` branch `if p0_entry.get("source") != "stamped":`.
  **Axis:** **refusal** — that an ungoverned P0 claim is refused rather than graded.
- **Neutralization:** the fall-open this change removed, restored in behaviour:

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
  4 failed, 1 passed, 30 deselected in 12.04s
  ```

  The discriminating assertion reads `assert 'graded' == 'refused'` — the refusal axis, not an
  adjacent one. The one test that stayed **passed** is the doc-copies guard, which is about the
  token's spelling and is correctly indifferent to this mutation.

- **Restore:** inverse edit restoring the refusal return.

## FP-31 — the refusal token's spelling at its home *(final head)*

WO-F landed a hand-typed literal pin; the review's first auto-fix round replaced it with a guard that
reads the constant and asserts the two shipped doc copies carry it. That is a stronger tie, and it is
what this proof exercises.

- **Guarded element:** the spelling of `front_door.REASON_P0_DEFINITION_UNSTAMPED`. **Axis:** the
  token's **spelling**, not its plumbing.
- **Neutralization:** the constant renamed at its definition, every call site untouched:

  ```
  -REASON_P0_DEFINITION_UNSTAMPED = "p0-definition-unstamped"
  +REASON_P0_DEFINITION_UNSTAMPED = "p0-definition-not-stamped"
  ```

- **Raw red:**

  ```
  E   AssertionError: plugins/superheroes/skills/showrunner/reference/owner-decisions.md: refusal token 'p0-definition-not-stamped' missing — drift from front_door.REASON_P0_DEFINITION_UNSTAMPED
  FAILED plugins/superheroes/lib/tests/test_front_door.py::test_p0_definition_unstamped_token_docs_follow_home
  1 failed, 4 passed, 30 deselected in 6.66s
  ```

  **`1 failed, 4 passed` is the whole point.** The four behaviour tests assert the *symbol* and stayed
  green through a rename that would have left the shipped door doctrine and the keep-or-retire
  condition pointing at a token no longer emitted; only the doc-copies guard caught it.

- **Restore:** inverse edit restoring the spelling.

## FP-32 — the second doc copy is independently guarded *(final head)*

FP-31 goes red naming the *first* doc copy, which alone would not prove the second is covered.

- **Guarded element:** the token's presence in `docs/superheroes/KEEP-OR-RETIRE.md`. **Axis:**
  per-copy coverage.
- **Neutralization:** the token deleted from S5's condition enumeration, the constant untouched:

  ```
  -  `p0-definition-unstamped`) that stopped a filing from expanding its own authority. On firing, a
  +  ) that stopped a filing from expanding its own authority. On firing, a
  ```

- **Raw red:**

  ```
  E   AssertionError: docs/superheroes/KEEP-OR-RETIRE.md: refusal token 'p0-definition-unstamped' missing — drift from front_door.REASON_P0_DEFINITION_UNSTAMPED
  ```

- **Restore:** inverse edit restoring the token.

---

## End-of-pass receipt (final head)

```
$ git -C /private/tmp/wh1287-bp rev-parse HEAD
62cc568e8f2c85b6dc3bb43dec4f49e1839e18e7
$ git -C /private/tmp/wh1287-bp status --porcelain
(empty)
$ pytest plugins/superheroes/lib/tests/test_disposition_flow.py plugins/superheroes/lib/tests/test_front_door.py -q
.......................................................                  [100%]
55 passed in 50.94s
```

No probe residue. Nothing was edited on the build branch by either pass; the probe worktree is
detached and was left at the final head with an empty porcelain.
