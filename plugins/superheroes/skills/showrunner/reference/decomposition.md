# Contents

- [When epic machinery fires](#when-epic-machinery-fires)
- [The coverage map](#the-coverage-map)
- [The contract register](#the-contract-register)
- [Seam-first sequencing](#seam-first-sequencing)
- [Verbatim injection into child bodies](#verbatim-injection-into-child-bodies)
- [The adversarial package read](#the-adversarial-package-read)
- [Re-entry after a substantive amendment](#re-entry-after-a-substantive-amendment)
- [Reciprocal cross-epic seams](#reciprocal-cross-epic-seams)
- [The child-PR register vet row](#the-child-pr-register-vet-row)
- [The single-issue fast path](#the-single-issue-fast-path)
- [Vocabulary (drift-tested)](#vocabulary-drift-tested)

# Epic decomposition

## When epic machinery fires

Epic machinery activates at **two or more children, never below**; one child takes the fast path in
[The single-issue fast path](#the-single-issue-fast-path). Everything below assumes that threshold
is met.

The precondition that governs everything below is pinned verbatim:

> Decomposition begins only after the spec is owner-approved: no coverage map, no register, and no child body is drafted against an unapproved spec, and a decomposition artifact dated before its spec's approval is a routing defect.

The machinery produces three artifacts:

1. **Coverage map** — acceptance-level allocation of every spec acceptance criterion to exactly one
   named child.
2. **Contract register** — numbered cross-child technical decisions, each with its consuming children
   named.
3. **Package-read audit trail** — the round-by-round record of the adversarial read before children
   file.

All three live **beside the spec in the work item's own folder** — one canonical file home each, no
size ceiling, no edit races. The epic body links to each; it does not duplicate them.

## The coverage map

When the advisor decomposes an owner-approved spec, the coverage map allocates at **acceptance
level**: every acceptance criterion is owned by **exactly one named child issue** — none unowned,
none owned twice.

- Each FR/UFR group marked as **faces of one behavior** allocates as one.
- Where a criterion genuinely spans children, it is **split at the spec's own acceptance-bullet
  granularity** and the split is **declared in the map** so each bullet is still owned exactly once.
- The map's home is the work-item folder; the epic body links to it.

An unallocated acceptance criterion, or an epic-scoped decision that is neither decided nor owned,
is a **routing defect** the advisor repairs **before any child build starts** — the package read
holds filing until it is repaired.

### Worked example — splitting a criterion that spans two children

**Spanning acceptance criterion** (as it would read in a spec):

> *Acceptance:* Given a user who has enabled push notifications, when a matching alert fires, then
> the device receives the push within thirty seconds **and** the in-app notification center shows the
> same alert with a deep link to the source item.

This criterion has two testable clauses — delivery latency and in-app display — that belong to
different implementation surfaces.

**Map rows** (declared split in the map's own prose):

| Child | Owned clause |
| --- | --- |
| C1 — push delivery | *…then the device receives the push within thirty seconds* |
| C2 — notification center | *…and the in-app notification center shows the same alert with a deep link to the source item* |

The map declares: *"The push-notifications acceptance criterion is split at the conjunction; C1
owns delivery latency, C2 owns in-app display and deep linking."*

**Verbatim register text each child gets:**

Child C1's body quotes:

> **R4 — Push payload contract.** The push channel carries `alert_id`, `title`, `body`, and
> `deep_link` fields; delivery is measured from server emit to device receipt.
> *Consumers:* C1, C2.

Child C2's body quotes:

> **R4 — Push payload contract.** The push channel carries `alert_id`, `title`, `body`, and
> `deep_link` fields; delivery is measured from server emit to device receipt.
> *Consumers:* C1, C2.

The shared payload shape is the register entry both children consume; each child's slice binds only
the clause the map assigns it.

**The test a reader applies:** read the original criterion, read the two map rows, and confirm every
clause of the original is owned once and only once. The failure this example prevents is a clause
that falls between the two children and is built by neither — the push arrives but the in-app
center never shows it, or the center renders alerts the push layer never defined a payload for.

## The contract register

When a decomposition yields **two or more children**, the advisor records every cross-child technical
decision in a **contract register** stored beside the spec in the work-item folder.

- **Numbered entries**, each a **plain binding sentence**, with its **consuming children named** on a
  `*Consumers:*` line, owner rulings embedded, amendments dated.
- An **embedded ruling is a dated copy pointing at where the ruling was made** — the register
  **quotes** rulings, it never becomes their ledger.
- **The advisor owns register edits; a builder never amends the register it is graded against.**

Two **blocking package-read findings:**

- An entry with **no named consumer**.
- An entry that introduces **new product opinion** — that is the spec's job, not the register's.

Every entry is either **decided at decomposition** or explicitly marked **decide-by**, naming the
child that owns the decision. An epic-scoped decision that is neither is a routing defect.

## Seam-first sequencing

Where one child creates a **seam** other children build on, that child is **sequenced first**, so the
register's contracts get their real review **as working code rather than as a document**.

What goes wrong otherwise: a contract that reads fine on paper and does not survive contact with its
first implementation — discovered by every consumer at once when their builds start in parallel
against an untested seam.

## Verbatim injection into child bodies

Child issues quote the register text they consume **verbatim, injected mechanically from the
register**; a paraphrased restatement is a defect. The machine check that proves it, its result
contract, and its three invocation points live in `skills/showrunner/reference/register-check.md` —
read that file; this section adds nothing further.

## The adversarial package read

Before an epic's children file, the package — register, slice boundaries, and child bodies — passes
an adversarial read performed by seats independent of the package's author.

### When it runs, and what it covers

The read runs **before an epic's children file**. The package under read is the **register, the slice
boundaries, and the child bodies** — not the spec itself (the spec is the authority the lenses grade
against).

### The weight call

The advisor calls the read's weight — `light` or `full` — using the vocabulary whose home is the
showrunner charter's duty 1. This section adds only the package-read specifics: the **measurables are the child count and the
register-entry count**, the call **names a round ceiling**, and the advisor **may override in either
direction with one stated sentence**. The numbers are guidelines; nothing here is a gate.

### Seats and independence

The read is performed by **seats independent of the package's author**. Seat composition follows
the **same independence rules as the plugin's code review** — see `rubric/review-discipline.md` and
defer to it; **this file adds no separate seat doctrine.**

Two things this file does state:

- **The package's author is the maker**, including the advisor when the advisor authored the
  package — so the author's model family is excluded from every seat.
- Reviewer unavailability or mid-run loss follows that same rubric's rules.

Every external seat carries the **planted-defect control probe** that rubric already mandates, and
the round's audit record carries the probe's engagement read.

### The five lenses

Each lens is one plain sentence; the audit tool records the token alongside the name:

- **Contradiction with the spec** (`spec-contradiction`) — a child body, register entry, or slice
  boundary contradicts the owner-approved spec.
- **Register-to-child drift** (`register-drift`) — quoted register text in a child body does not
  match the register on disk.
- **Exactly-once acceptance coverage** (`coverage-exactly-once`) — the coverage map leaves a
  criterion unowned, double-owned, or mis-split.
- **Child-against-child and cross-epic collisions** (`collisions`) — two children disagree, or a
  cross-epic seam is recorded on one side only.
- **DoD adequacy** (`dod-adequacy`) — a child's DoD bullets are not gradable from handback
  artifacts alone.

### Scoped rounds

A round reads the **currently-unreviewed parts**, plus, for the three **relational** lenses (spec
contradiction, collisions, coverage), **each reviewed part those unreviewed parts directly touch**.
Never a fresh pass over the whole package.

A code review cannot scope this tightly because diffs are contiguous hunks, not named verbatim
units. The package admits exact scoping because its register entries, child bodies, and map rows are
discrete, addressable text.

### The convergence rule

The read repeats until a round returns **only mechanical items** — fixes that change wording or
synchronization and decide nothing.

**Authorship extends the loop; re-flagging does not**: a fix that adds a contract or redraws a slice
boundary makes those parts unreviewed and they are re-read before filing, while a blocking finding
raised against text **unchanged since its last review** is logged and fixed **without** further
extension — unless its fix creates such new authorship.

### The verification pass

The read ends with a **recorded verification pass**: each fix checked against its finding, **plus
the mechanical sync check** (the register-quote check of
[Verbatim injection into child bodies](#verbatim-injection-into-child-bodies), run per
register-consuming child), with **no new hunting**.

A fix that **fails** verification returns its parts to unreviewed and they are re-read before
filing. **The ceiling is the backstop, not the exit mechanism** — exhausting it parks.

### The audit trail

The trail is preserved with the epic, in the work-item folder. A trail missing any of these elements
is nonconforming:

- The weight call (its measurables and ceiling)
- Each re-read invocation's cause and ceiling
- Any override sentence
- The seats
- The lenses run per round
- The parts each round read with their unreviewed-at-entry status
- The findings declined further extension under the unchanged-text rule
- Each fix's verification outcome

The per-round receipt is **machine-written, not reconstructed from a session log**:
`lib/package_read_audit.py` appends the invocation record, each round's record (lenses run, the
parts read with their unreviewed-at-entry status, the control probe's engagement read, the findings
raised, the findings declined further extension, and whether the round was mechanical-only), and the
verification record (each finding's disposition and outcome, and the sync-check result per child);
its `check` verb reads the trail back and reports `conforming`, `nonconforming`, or `undecided`.

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -B "$ROOT_DIR/lib/package_read_audit.py" check \
  --trail docs/superheroes/<work-item>/package-read-audit.md
```

### The ceiling park

A read invocation that fails to converge within the ceiling named at its invocation **parks to the
owner with the children unfiled and the open findings named**. The park's surface — where the note
lands, and the durable copy — is defined in the showrunner charter's duty 1.

`check`'s `parkOwed` is the mechanical face of this rule. A trail honestly recording an
unconverged read at its ceiling is a **conforming** trail reporting a park.

## Re-entry after a substantive amendment

The classification itself (`wording` vs `substantive`) and the propagation duty live in
`skills/showrunner/reference/amendments.md` — cite that file; this section does not restate the
classes.

A **substantive** amendment landing while a decomposition or its children are in flight sends the
**touched parts of the package back into the read loop**.

- **Each re-read draws a fresh ceiling named at its invocation and requires a new cause** — an owner
  decision or a recorded amendment. Because amendments are owner-stamped, **every cause passes
  through the owner: the loop cannot cycle without an owner decision.**
- **Re-read invocations never self-trigger** — a failed verification re-reads **within its own
  invocation's ceiling**.
- A re-read that exhausts its ceiling **parks** ([The ceiling park](#the-ceiling-park)).
- The **coverage map is re-checked before affected children file.**

### Contradiction dispositions

A package-read finding of **contradiction with the spec** resolves in exactly one of three ways:

1. A **package fix** — the child body, register entry, or slice boundary is corrected to match the
   spec.
2. An **owner-stamped spec amendment** — the spec body is edited with a dated, owner-stamped
   Amendments-log entry per the amendment machinery.
3. A **recorded refutation in the audit trail** — the finding is answered with evidence readable in
   the trail.

**Never a silent spec edit.** A spec body changed during a package read with no owner-stamped
amendment entry is a blocking finding. The audit trail is where a refutation has to be readable.

## Reciprocal cross-epic seams

Where an epic shares a seam with another epic, the seam is recorded **reciprocally — in both
registers and in both affected child bodies**.

A seam recorded on **one side only** is a **blocking package-read finding** under the collisions
lens.

Where the other side is a **single-issue** spec, that side's register home is **the child's issue
body**, which quotes the entry verbatim ([The single-issue fast path](#the-single-issue-fast-path)).

## The child-PR register vet row

This section is the **canonical home** of the row; the charter's vet duty carries a copy. The row
is pinned verbatim:

> A child PR in a package that has a contract register is vetted against one added row: the change conforms to the epic's register, or the drift is disclosed — and undisclosed drift is a blocker, held until it is disclosed or repaired.

**What "conforms" means in practice:** the diff does what the entries this child consumes bind it
to. A deliberate departure from a register entry is **disclosure**, not silence — the vet row grades
whether the handback names the drift or the implementation matches.

**Undisclosed drift found at vet** holds the handback until the drift is disclosed or repaired.

## The single-issue fast path

**Epic machinery activates at two or more children, never below.** One child means **no register**
and no separate decomposition sitting.

The **in-channel fast continuation**: the advisor proposes the single child issue **in the same
conversation**, and the owner approves it **there**.

**Closure folds into that PR's vet** — the applicable closure elements are graded there. The closure
receipt's element list belongs to the closure contract and is not enumerated here.

**The owner's merge decision doubles as delivery acceptance only when the handback names it as such
in so many words — an explicit line, never an inference.** A single-issue spec still ends with an
**explicit owner delivery decision**.

**Shared seams:** where a single-issue spec shares a seam with an epic, the seam is recorded in the
**epic's register** and **quoted verbatim in the single child's issue body**, which **stands in for
the missing register on the single-issue side** — reciprocity
([Reciprocal cross-epic seams](#reciprocal-cross-epic-seams)) and amendment propagation both read
that issue body as that side's register home.

## Vocabulary (drift-tested)

The Python module `package_read_audit.py` is the authoritative home for these tokens; this list is
checked against it.

**Schema:**

- `package-read-audit/1`

**Results:**

- `recorded` — write verbs
- `refused` — write verbs
- `conforming` — the check verb
- `nonconforming` — the check verb
- `undecided` — the check verb

**Lenses:**

- `spec-contradiction`
- `register-drift`
- `coverage-exactly-once`
- `collisions`
- `dod-adequacy`

**Part statuses:**

- `unreviewed`
- `reviewed`

**Control-probe reads:**

- `engaged`
- `not-engaged`
- `not-applicable`

**Weights:**

- `light`
- `full`

**Dispositions:**

- `package-fix`
- `spec-amendment`
- `refutation`
- `declined-extension`

**Verification outcomes:**

- `verified`
- `failed`

**Sync-check results:**

- `pass`
- `fail`
- `undecided`

**Record kinds:**

- `invocation`
- `round`
- `verification`

**Refusal reasons:**

- `trail-unreadable`
- `trail-missing`
- `trail-malformed`
- `invocation-duplicate`
- `invocation-unknown`
- `round-duplicate`
- `round-exceeds-ceiling`
- `round-invalid`
- `lens-unrecognized`
- `part-malformed`
- `part-status-unrecognized`
- `control-probe-unrecognized`
- `finding-malformed`
- `finding-duplicate`
- `finding-unknown`
- `verification-duplicate`
- `disposition-unrecognized`
- `outcome-unrecognized`
- `sync-check-malformed`
- `sync-result-unrecognized`
- `weight-unrecognized`
- `ceiling-invalid`
- `measurable-invalid`
- `seats-missing`
- `usage`
- `internal-error`

**Nonconformity kinds:**

- `round-missing`
- `element-missing`
- `finding-unverified`
- `disposition-mismatch`
- `sync-check-missing`
- `sync-check-failed`

**Undecided reasons:**

- `trail-unreadable`
- `trail-missing`
- `trail-empty`
- `trail-malformed`
- `invocation-unknown`
- `usage`
- `internal-error`

**Exit codes:**

- `0` — conforming
- `1` — nonconforming
- `2` — undecided
