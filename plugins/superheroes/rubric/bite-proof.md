# Bite-proof

This file is the **one home** for the bite-proof rule. Charters and skills point here rather
than restating it. A **detector** is anything whose job is to fail when something is wrong: a
test, an assertion, a guard clause, a validator, a CI check, a lint rule, a review-rubric question.

## The obligation

**Every new or changed detector ships with a recorded bite-proof.** Four steps, in order:

1. **Neutralize** the thing the detector guards, through the path the detector claims to cover.
2. Show the detector **red**.
3. **Restore** the neutralization.
4. Show it **green** again.

The proof runs with the **detector unedited**. A detector edited to make itself go red proves nothing.

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
   partial drift is exactly what survives it (a doc guard whose legs matched a substring anywhere
   in a section still passed when any one of three occurrences of the same marker was renamed, and
   failed only when all three were — partial drift was invisible).

4. **It is delivered through a path the guarded input can never take.** If the mutation cannot
   reach the detector through the path the test uses, the red you saw came from something else —
   or never came at all. **The same failure wears a second face:** the mutation *does* reach the
   mutated branch, but the **fixture never creates the condition the assertion discriminates on** —
   so the probe stays green for every implementation, and the assertion is measuring nothing. The
   tell is **a probe green where your own reasoning says it should be red**; when you see it, the
   defect is in the fixture and **the cure is fixing the fixture, never relaxing the assertion**
   (observed twice in one build — PR #1134's freshness leg). See
   `## When the proof cannot be produced`.

## The record

**One bite-proof entry, per guarded element, must contain:**

- **guarded element** — a `file:line` or a name — and **the axis** it claims;
- **neutralization** — the exact change applied: targeted, reversible, quoted;
- **raw red** — output with the detector unedited;
- **restore** — how the neutralization was undone;
- **restore receipt** — mechanical evidence the neutralized surface is back to its
  pre-neutralization state: a post-restore `git status --porcelain` over the neutralized path, or
  the restored content quoted; **any residue that could not be reverted must be reported
  explicitly**;
- **raw green** — output after restore.

**Raw captures are bounded:** at most **32 KiB per element** and **128 KiB across the whole
record**. Overflow goes to session-scoped scratch **outside the repository**; quote decisive
lines (redacted) into the durable record — with what was elided and how much — before removal
once verification closes (an interrupted run leaves it as an accepted residual). **A path that
no longer resolves is not a receipt** — quote before removal; scratch is a working artifact, not
the receipt. Receipts in the durable record are **redacted** — secrets, tokens, private URLs,
PII — and the redaction is said out loud.

**Bounded volume shape:** when a detector guards many elements, the record may group them into
**failure-mode equivalence classes** — each class named by **the distinct failure mode it
produces**, each class's **representative element named**, and the classes must **cover every
guarded element**, with any element in no class **listed as unproven**. A class is a **failure
mode**, never a convenience bucket; **"there were a lot of them" is not a class**. This does not
weaken trap 3 — trap 3 forbids an *unnamed* representative standing for elements nobody enumerated.

**Where each part lives, and why the split matters:**

- **The axis line lives in the code** — one line at the detector saying what it bites on. A review
  seat sees the diff, not the build record, so the axis line is the only part of this it can check.
- **Every disclosure this file requires lives at the detector, in the code** — one line at the
  detector, same form as the axis line, with the full record in the durable record. That is what
  makes it checkable by someone reading only the change.
- **The red and green receipts live in the durable build record** — the pull request. A bite-proof
  that happened only in a session transcript did not happen.

**Records are receipts, not consumed surfaces: they are categorically outside every content
census, exactly as detector self-paths are.** A proof must be free to quote the literal it proves —
the retired flag name, the forbidden string, the doctrine path a pointer census polices — so a
census that reads its own evidence re-fires on every new proof. Close the class at the **category**:
exclude the record directory at the census's walk, the way detector self-paths are already
excluded, rather than rewording each record that trips it. (Standing advisor ruling, 2026-08-25.)

Naming an existing test as "the proof" satisfies none of these fields, and is exactly the vacuous
claim this file exists to refuse.

## When the proof cannot be produced

There are three such shapes. **Silence is never one of the answers.**

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
A fix batch commissioned specifically to replace inert end-to-end tests shipped three more inert
end-to-end tests — the guarded input could not reach the guard through the public entry point,
because an earlier stage stripped it.

**Unrunnable here.** The detector is expected to bite, but the run cannot be executed in this
environment — the shell was rejected or sandboxed; a safety mechanism refuses to run a suite with
a deliberately weakened check in the tree; the check needs secrets, services, privileges, or runner
hardware this environment lacks. This shape is about the **run**, not the code: the disclosure is an
honest handoff, not an excuse. **Required disclosure:** **what refused or blocked the run**, quoted;
**the exact command and the environment that could run it**; **the substitute evidence actually
produced** — for example an A/B of the new detector against the base revision of the guarded file —
**with the cases it does not discriminate named explicitly**; and **who owns the outstanding receipt**.

## When the proof runs under a normalization

This is **not** an unprovable shape — the proof runs. It runs under a **pinned** clock, environment,
configuration, or concurrency, chosen to make the test deterministic. **Required fields:**

- **pinned condition** — what was fixed, and where;
- **production timing or environment shape the pin makes unobservable.**

Both are stated **at the pin, in the code**, and in the build record. *"Environment normalized"*
on its own is not the disclosure — the second field is the disclosure, and without it the pin
reads as rigor. A wall-clock-tight interleaving suite passed on an idle machine and failed under
load, and two earlier rounds had environment-normalizing tests hide blockers that were inert in
production.

## Who owes what

- **The order's author (the build orchestrator)** — an order that adds or changes a detector
  **names the bite-proof it expects**: the guarded element, the neutralization to apply, and the
  detector expected to go red.
- **Whoever types the change** — **produces** the proof and returns it in the record shape above,
  per guarded element; where the proof cannot be produced, returns the disclosure this file requires
  instead of silence; a **dispatched implementer** never marks its own work done.
- **The orchestrator at verification** — **re-runs the proof itself** (verification never delegates),
  carries the receipts into the build record, and **accepts or rejects each disclosure and records
  which** — **no party accepts its own disclosure**; where the same actor typed the change and
  verifies, the disclosure travels to the **next independent reader of the record** — the advisor's
  vet where a project has one, otherwise the owner before the merge decision — and until then the
  record **states plainly that the disclosure is unadjudicated**, which is a permitted terminal state for
  the build, not a blocker: what is forbidden is recording it as *accepted* by the party that
  wrote it; an accepted disclosure names the check that confirmed the proof is genuinely unavailable (for
  instance: it attempted the neutralization and observed no red). **The four vacuity traps are
  not disclosable** — a one-representative or whole-document check is a defect to fix, not a caveat
  to write.
- **The review seat** — flags the **absence** of an axis line, or of an owed disclosure, **in the
  diff it was given**. It never runs a proof — a review seat never changes the repository — and it
  never asserts that a receipt is missing, because the build record is not among its inputs.
