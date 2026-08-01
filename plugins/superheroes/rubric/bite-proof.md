# Bite-proof

This file is the **one home** for the bite-proof rule. Charters and skills point here rather
than restating it. A **detector** is anything whose job is to fail when something is wrong: a
test, an assertion, a guard clause, a validator, a CI check, a lint rule, a review-rubric
question.

## The obligation

**Every new or changed detector ships with a recorded bite-proof.** Four steps, in order:

1. **Neutralize** the thing the detector guards, through the path the detector claims to cover.
2. Show the detector **red**.
3. **Restore** the neutralization.
4. Show it **green** again.

The proof runs with the **detector unedited**. A detector edited to make itself go red proves
nothing.

A green run is equally consistent with *the code is right* and *this detector cannot fail*. Only
the red run tells them apart. This is the covenant's fourth promise — **claim nothing you did not
verify** (`rubric/covenant.md`). A guard with no bite-proof is an unverified claim, however
emphatic its name.

## Four ways a bite-proof is vacuous

1. **It mutates a precondition instead of a consumer.** Breaking a helper the tests already assert
   as a precondition reddens the tests that assert the helper and says nothing about whether
   anything downstream is protected. **Mutate the production call sites that depend on the
   guarantee.**

2. **It bites on the wrong axis.** A proof can go red on something adjacent — presence where the
   guarantee is about authority, a count where it is about refusal. **Name the axis the detector
   claims, and check that the red you got is on that axis.**

3. **It proves one representative instead of every guarded element.** A detector that guards N
   things — three marker names, four fail-closed edges, two charter copies — owes **N separate
   neutralizations and N reds**. One representative is evidence about that one element only, and
   partial drift is exactly what survives it.

4. **It is delivered through a path the guarded input can never take.** If the mutation cannot
   reach the detector through the path the test uses, the red you saw came from something else —
   or never came at all. See `## When the proof cannot be produced`.

## The record

**One bite-proof entry, per guarded element, must contain:**

- **guarded element** — a `file:line` or a name — and **the axis** it claims;
- **neutralization** — the exact change applied: targeted, reversible, quoted;
- **raw red** — output with the detector unedited;
- **restore** — how the neutralization was undone;
- **raw green** — output after restore.

**Where each part lives, and why the split matters:**

- **The axis line lives in the code** — one line at the detector saying what it bites on. A review
  seat sees the diff, not the build record, so the axis line is the only part of this it can check.
- **The red and green receipts live in the durable build record** — the pull request. A bite-proof
  that happened only in a session transcript did not happen.

Naming an existing test as "the proof" satisfies none of these fields, and is exactly the vacuous
claim this file exists to refuse.

## When the proof cannot be produced

There are two such shapes. **Silence is never one of the answers.**

**Unprovable as placed.** The distinction the guard makes cannot be observed at the guard — both
operands were already normalized upstream, so the strict check and the loose one behave
identically, and no test can tell them apart. **Required disclosure:** restructure so it can bite
— move the guard to where the distinction still exists, or stop erasing the distinction upstream
— **or** ship with a recorded **construction bound** containing: what makes it unprovable; what
would make it provable; and the plain statement that its protection is unverified.

**Unreachable through this entry point.** The guarded input cannot reach the detector through the
path the test uses, because an earlier stage strips it. **Required disclosure:** the **public path
that strips the input**; and the **exact seam plus `file:line` of the proof that does bite**
(usually a unit-level test on the guard itself). A test that can never deliver the guarded input
is **inert**; shipping it as coverage is worse than shipping no test, because it reads as coverage.

## When the proof runs under a normalization

This is **not** an unprovable shape — the proof runs. It runs under a **pinned** clock, environment,
configuration, or concurrency, chosen to make the test deterministic. **Required fields:**

- **pinned condition** — what was fixed, and where;
- **production timing or environment shape the pin makes unobservable.**

Both are stated **at the pin, in the code**, and in the build record. *"Environment normalized"*
on its own is not the disclosure — the second field is the disclosure, and without it the pin
reads as rigor.

## Who owes what

- **The order's author (the build orchestrator)** — an order that adds or changes a detector
  **names the bite-proof it expects**: the guarded element, the neutralization to apply, and the
  detector expected to go red.
- **The implementer** — **produces** the proof and returns it in the record shape above, per guarded
  element; where the proof cannot be produced, returns the disclosure this file requires instead of
  silence. It never marks its own work done.
- **The orchestrator at verification** — **re-runs the proof itself** (verification never delegates)
  and carries the receipts into the build record.
- **The review seat** — flags the **absence** of an axis line, or of an owed disclosure, **in the
  diff it was given**. It never runs a proof — a review seat never changes the repository — and it
  never asserts that a receipt is missing, because the build record is not among its inputs.
