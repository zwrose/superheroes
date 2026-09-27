# Contents

- [Work orders: authoring, linting, gating, and escalation](#work-orders-authoring-linting-gating-and-escalation)
  - [Name the invariant and its census, not a list of sites](#name-the-invariant-and-its-census-not-a-list-of-sites)
  - [A removal census owes two sweeps](#a-removal-census-owes-two-sweeps)
  - [What every order carries at authoring time](#what-every-order-carries-at-authoring-time)
  - [Declared deliverables](#declared-deliverables)
  - [Linting an order](#linting-an-order)
  - [The model gate](#the-model-gate)
  - [Escalation and maker family](#escalation-and-maker-family)

# Work orders: authoring, linting, gating, and escalation

This page is reference for the orchestrator writing and dispatching work orders. The charter's §6
and §7 state the duties and point here. The six validity rules an order must satisfy live in
`agents/implementer.md`, and the implementer is the backstop that flags an order that breaks them.
Nothing on this page adds a seventh validity rule. It is how you satisfy the six, especially rule 3,
complete target enumeration.

## Name the invariant and its census, not a list of sites

An order that hands the implementer a list of sentences to apply at named sites makes correctness
depend on the author's recall. Each round fixes the sites someone thought of, the unenumerated ones
stay broken, and a fix bolted onto one site can break another.

The shape that converges has three parts:

- **The invariant.** One sentence the surface must satisfy.
- **A complete census** of the sites the invariant governs. The grep or equivalent enumeration is
  run and its output pasted into the order, not promised.
- **The single chokepoint**, where the surface has one, that every path routes through. Ask for a
  test that asserts the invariant rather than per-site end states, so a site nobody enumerated fails
  a test instead of shipping.

## A removal census owes two sweeps

A census for a removal runs two sweeps, whether you author it into an order or run it yourself in a
lane where you type the change:

1. **The identifier sweep.** A grep for the symbol being removed.
2. **The vocabulary sweep.** A grep for the values the symbol never spells: enum members, artifact
   filenames, API verbs, degradation and refusal tokens, and the prose that names them.

The identifier sweep can come back clean while the invariant still fails, because the surviving
reference is a string the symbol search never reaches. Paste both sweeps into the build record.

## What every order carries at authoring time

These obligations attach to the order on your side, when you write it.

- **A prose-contract review order carries its bounded-acceptance round count.** When an order
  dispatches a review whose contract is prose, the general re-review bar does not terminate, so the
  order states the round bound and names its source. The source is the owner, set before review
  begins, or the advisor, set at routing. The order carries the bound and never sets it. A number
  the builder chose is not an authority. Where no bound has been set, the order says so, and the
  advisor at vet remains the setter, as `rubric/review-discipline.md` § Bounded acceptance —
  prose-contract DoDs rules. An order with no bound leaves the stopping point to be improvised
  mid-review.
- **A detector-adding order names the recorded red-to-green proof it expects.** An order that adds
  or changes a detector (anything whose job is to fail when something is wrong) names the recorded
  proof. What the record must contain is whatever the bite-proof rubric the charter's §8 cites
  defines, so cite that home instead of listing its contents. A green run alone is equally
  consistent with a detector that cannot fail, which is why the proof must be recorded.
- **An implementer order names a per-order test-command budget.** The order states how many command
  invocations the implementer may spend and what they are, scoped to the order's own surface. The
  budget counts the commands the order names, run under the implementer's command-precedence
  ladder. The bite-proof red and green runs are named separately and sit inside the budget, so a
  long verification list cannot squeeze them out. The budget names a scoped command, never a
  project-wide suite. An order whose named commands cannot fit its own budget is under-specified, and
  the implementer stops and reports it under the per-order test-command budget rule in
  `agents/implementer.md`. An order that names a long suite tends to forfeit after it has already
  landed good work.

## Declared deliverables

Every implementer write dispatch declares the files the order must deliver, with `--expect-item
<path>` (repeatable) or `--expect-items-file <file>` on `dispatch-write`. At collection time the
runner compares the declared set with the run's final diff and downgrades a success to a forfeit,
reason `items-undelivered`, when a declared path was never delivered. That catches a silent partial
delivery that would otherwise read as a clean result.

The check is final-diff membership, not proof of authorship:

- It cannot tell a created file from a modified one.
- A file created and then deleted leaves no evidence and reads as missing.
- A path already dirty before the run and unchanged after it is not credited.
- It does not prove which copy of a cited file the implementer read.

## Linting an order

Lint every order before you dispatch it, with both halves. Run both before every implementer order
and every review-fix work order you author, on both channels (native subagent and `dispatch-write`).
The `review-code` in-place fixer's order is rendered by the driver and gets the deterministic half at
the driver's emission (`skills/review-code/reference/auto-fix-loop.md`).

**The deterministic half** is `lib/order_lint.py`:

`python3 -B <plugin root>/lib/order_lint.py check --order <the order file> --repo-root <the build worktree> --alt-root <the build worktree's plugin root, in this repository> --expect-item <each declared item>`

Run it over the authored order text, the same text you hand the runner or the subagent, an inlined
implementer template included. The lint recognizes a verbatim copy of the shipped
`agents/implementer.md` body and grades only the text around it, so never lint a trimmed subset. The
runner's appended write-report contract is not what is linted. Exit 1 with a named token refuses the
order.

**The semantic half** is one native subagent at the mechanical role's registry cell (Haiku tier).
Run the model gate first, with `"role": "mechanical"` in the seat. The prompt is
`rubric/orders/order-lint-semantic.md` followed by two lines naming the order's absolute path and the
repo root. It returns findings-only JSON with an investigated list.

- An **Important** finding is stop-and-fix. A **Minor** finding is your call, recorded in the
  dispatch-provenance row.
- The check did not happen when the answer is unparseable, the investigated list is empty, the list
  omits the order's absolute path, or it lists paths that do not resolve under the repository root
  or session scratch. Re-dispatch it once. If it still did not happen, the order is not dispatched:
  fix it or park. "Lint skipped" is never a state.
- Where the registry lists no model for the `mechanical` role on the host vendor, the semantic half
  is unavailable on that host. The deterministic half still runs and still binds, the order is
  dispatched, and the dispatch-provenance row records `semantic-lint-unavailable:<vendor>` as a
  disclosed degradation.

Record both halves' results in each order's dispatch-provenance row: the token list or `clean`, and
the semantic seat's finding count with its wall time. The lint exists because an orchestrator writes
orders faster than it re-reads them, and each order defect costs a full implementer dispatch plus a
rework.

## The model gate

Run the gate before each of the four dispatch kinds the charter's §7 names, on the effective seat
model you will pass (explicit in the seat JSON, or null for the seat default):

`python3 -B <plugin root>/lib/dispatch_guard.py check --seat '{"vendor":"<vendor>","model":"<id>","effort":<str-or-null>,"role":"<role>"}'`

The gate validates the model against the seat's registry allowlist in `lib/model_registry.py`, the
one model and vendor taxonomy. The full dispatch CLI surface is in
`skills/workhorse/reference/dispatch-entry.md`.

| Result | What you do |
|---|---|
| Exit 1, unlisted model | Park before any work runs. The gate prints the allowlist. A model choice inside an engine is not a preference. This governs a dispatch you are going to make. Declining to dispatch and doing the work yourself is a different act. |
| Exit 0 | Thread `model_id` into the seat's `model` key and `effort` into `effort`. Record the resolved `model_id` and `effort` in the dispatch-provenance table, never a bare composed token or a bare model string, which drop the effort. |

What the gate resolves on its own:

- A composed `dispatch_token` in `model` is accepted and resolves to the same pair.
- An `effort` that contradicts a composed token is refused.
- A null `effort` resolves when the allowlist makes the model unambiguous, and otherwise takes the
  lowest ladder rung. `effort_source` reports which.

Running the gate is your discipline, not an automatic trigger. A skipped gate leaves the
dispatch-provenance row without a validated model, which is how the advisor spots it.

**Cursor is first-party only** (CONVENTIONS `§7.5`). A work order routed to the cursor CLI runs only
cursor's registry-listed first-party models, never a Claude, GPT, or other third-party model. The
allowlist enforces it and `dispatch_guard` is where a violation surfaces, so reaching a premium model
through cursor is a park, not a pick.

**A fable tier never rides an external engine.** Configuration refuses it
(`fable-on-external-engine`). A dispatch that refuses with `fable-unrunnable` is a configuration
defect to park on, not a fall-open to route around.

## Escalation and maker family

**Escalation needs demonstrated fragility.** Implementation starts on the calibrated implementation
engine. Leaving it needs receipts from a failed round on the work at hand. A hunch, a precedent from
a previous build, or a class of work booked in advance does not count.

**Attribute the trigger before you act on it.** Ask whether a different engine, given the same work
order, would plausibly have produced the same defect.

- If yes, it is an order defect. Rewrite the order and re-dispatch at the same rung. An order that
  under-specified a fail-closed edge or left out a target file is the usual case.
- If no, it is demonstrated fragility, and one ladder step is licensed.

**The ladder comes first.** Escalate one rung up that engine's registry ladder. A jump across vendors
also needs the top rung of that ladder to have demonstrably failed on this same work. Disclose every
cross-vendor jump in the PR's dispatch-provenance record, with the trigger receipts.

An escalation is a completed result rejected on receipts and re-dispatched. It is not the fail-open
engine-selection fallback that degrades when an engine is unavailable (CONVENTIONS `§7.5`). That
section holds escalation fail-closed, and the two events are recorded differently.

**Record the maker family for every work order.** The maker family is the model family that
implemented it. Independence keys on family, not on the dispatch CLI (CONVENTIONS `§7.5`), so read
the family off the registry, never off the CLI. A rung-up inside one engine's ladder can stay in the
same family. A surface's deep and adversarial review seats exclude the maker families of the orders
that built it. Your dispatch-provenance record is that accounting.
