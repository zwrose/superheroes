# Provisioning — slots for an authenticated wave

This page is reference for the advisor provisioning slots for a wave that needs authenticated pilot
coverage across more than one account. Duty 10 of the Showrunner charter states whose job this is;
this page holds how it runs. The contracts behind each step live in `reference/pilot-contract.md`.

## The sequence

**The sequence is load-bearing.** Backend identity is only observable on a running app, and no
credential may exist before the target is verified. So:

1. **Stand the app up unauthenticated.** Create the worktree and stand up the project, then bring
   the app up without any seeded sign-in.
2. **Verify the target boundary** against that running instance, and only then proceed.
3. **Seed with the owner present.** Per-slot sign-ins into provisioned browser contexts happen
   with the owner attending — never in the builder.
4. **Mint credentials and launch.** Mint credentials per slot and launch the headless builders.
   Each builder verifies its slot reference and generation at intake, then the pilot subagent
   drives the app.

## Wave deadline and margin are set at launch, not discovered

Every wave carries a deadline with margin. A credential whose validity horizon cannot support that
deadline plus margin does not get an unattended wave: it runs attended, or the project declares a
re-checkable server probe. The margin rule and its comparison live in `reference/pilot-contract.md`
§ Wave runtime — deadline and teardown; read it there rather than restating it.

## Wave teardown is a sequence

Teardown is two-phase, and an absent handler is a failure that must surface, not a skipped step.
The step contract lives in `reference/pilot-contract.md` § Wave runtime — deadline and teardown.

## The partial-failure report goes to the owner, not around them

A failed slot may already have started an app, created a credential, or touched shared fixtures,
so healthy slots are not safe by assumption. The report enumerates what the failed slots touched
and confirms they are fenced before recommending that the rest launch. **A report with no healthy
slots, an unfenced failed slot, or a shared effect recorded as possibly-applied is a no-go**, not a
warning. The report reads the provisioning journal. A rotated slot's history is read across its
retained segments as well as its live journal, so a long-running slot's evidence is not lost to
rotation.

## Per-account cost is displayed, and the owner decides

Under attended seeding there is no framework ceiling on accounts: each additional account costs one
owner sign-in at wave launch. Display that cost; never invent a count. The natural default is a
pair — an account that owns a resource and a second it is shared with — the minimum that makes an
interaction observable at all.

## A weaker datastore-identity guarantee is a recorded acceptance

Where the datastore is not directly reachable, the identity is app-reported and carries
`strength: "weaker"`. Provisioning **refuses `weaker` by default** and proceeds only on an explicit
acceptance record (who accepted, when, and why) supplied at the provisioning call, which runs in the
advisor and never reaches the builder. The launch ledger carries the strength and the acceptance
onto the batch report, so a weaker-guarantee slot **reads visibly weaker** in the owner-facing
count. It is a record and not a boolean so it cannot be dropped silently.

## The account-class tripwire has no acceptance record

A slot whose credential set spans more than one declared account class refuses, and so does a
credential-set account with no declared class — both are CONVENTIONS §14's accepted-limit
conditions made mechanical. Unlike the weaker-identity gate, there is **no acceptance record** for
these: §14 states the condition unconditionally, so a slot that trips it is fixed in policy, not
accepted. The refusal contract lives in `reference/pilot-contract.md` § The provisioning gate.

## Ownership-probe residue never reads as covered

Where a project declares an ownership probe, the conformance run exercises it per account, but a
passing probe is a point-in-time subclaim. An account quietly accumulating data over time is **not**
something the framework detects. That residue rides with the owner: surface it.

## Policy is enforced here and never travels

What reaches the builder is a verified **result**. The builder never holds the policy it was judged
against, so there is no file in its reach to edit, and the rules cannot change after the judging.
The ledger entry carries verification results, never policy material. A mismatch fails closed, in
the advisor. The contract lives in `reference/pilot-contract.md` § Results travel, never policy and
§ Provisioning authorization.

## The launcher carries the slot

When a launch belongs to a wave, supply the slot and generation, and the composed boundary result,
to the launcher, so the ledger records which slot a lane ran in. A wave launch recorded without its
slot is a batch report that cannot answer "which slot failed". The launcher refuses a parallel
launch on a slot-calibrated project when a lane carries no reservation. A lane already live without
a slot is driven to a terminal outcome and relaunched: slot metadata cannot be amended onto an
existing reservation. The trigger and refusal contract live in `reference/pilot-contract.md`.
