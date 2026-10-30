# Glossary

The one home for the plugin's ruled vocabulary. Every other surface cites a term by its heading
anchor and states no definition of its own. When prose elsewhere needs one of these words, link
the heading rather than paraphrasing it.

## Owner decisions and walks

### Ruling

Any decision the owner gives, in any session.

### Canon

The project's record of the owner's decisions: answers to owner calls, principles, and ceded calls,
each standing or for one piece. The contract holds what goes in, what stays out and where it goes
instead. See [Canon's contract](canon-contract.md).

### Ceded call

A kind of call the owner has told agents to decide from now on. It is kept in [Canon](#canon) as a
[standing ruling](#standing-ruling), and it is not a builder's handback.
See [Canon's contract](canon-contract.md).

### Standing ruling

A [ruling](#ruling) that applies to all later work. The project's principles are its standing
rulings. See [Canon's contract](canon-contract.md).

### Decision walk

A sitting in which the owner takes batched decisions, from the command or from a conversation.
"Walk" alone, outside a PR sheet, means this.

### Walk

The part of a PR sheet where the owner tries the change, stop by stop, answering each stop with the
[check pattern](#answer-pattern). A look-only stop is one the owner only looks at.

### Answer pattern

One of the four shapes a question on a sheet is answered in, as
[the four answer patterns](../theme/review-template.md#the-four-answer-patterns) states: agree
(accept or discuss), pick (one of the options), check (works, a problem or skip) and sign-off (the
merge verdict). Adding a pattern takes the owner's ruling.

### Owner-vs-craft line

The one line that sorts every call a session meets into a [craft call](#craft-call) or an
[owner call](#owner-call): ten owner categories, a sorting rule, an always-craft list, the
consequence rule, and errors that are not decisions. It is the same in every project.
See [the owner-vs-craft line](owner-vs-craft-line.md).

### Craft call

A call the [owner-vs-craft line](#owner-vs-craft-line) sorts as craft. An agent decides it, executes
it, and records it for the owner's veto.

### Owner call

A call the [owner-vs-craft line](#owner-vs-craft-line) sorts as the owner's. It waits for the owner's
word. Doubt resolves to an [owner call](#owner-call).

### Material consequence

An owner consequence that a change or a craft choice carries: one that touches a category of the
[owner-vs-craft line](#owner-vs-craft-line). It goes to the owner as its own decision under the
line's [consequence rule](owner-vs-craft-line.md#a-craft-choice-that-carries-an-owner-consequence).
Nothing checks it by tool.

### Priority tiers

The four tiers an item can hold at the front door. P0 is the next wave. P1 is the standing
budget, entered on the owner's batched word. P2 should eventually happen; like every
tier, it files only on the owner's word. Declined is a [declined registry](#declined-registry) line with a
[trigger](#trigger). The front door's rules for each tier live in the issue contract.

## Gardening and condition windows

### Gardening pass

The periodic sweep in which the advisor reads the keep-or-retire list, the registry's triggers, and
the misses log, and brings [proposals](#proposal) to the owner.

### Gardening record

The comment a [gardening pass](#gardening-pass) leaves.

### Gardening window

The calendar span between two [gardening records](#gardening-record).

### Condition window

The calendar span one [retirement condition](#retirement-condition) counts over.

## The keep-or-retire list and its entries

### Keep-or-retire list

The hand-kept list of every [plugin component](#plugin-component), one entry each, that makes
retirement the default.

### Keep-or-retire entry

One component's entry on the [keep-or-retire list](#keep-or-retire-list): the component and the
cost or annoyance that makes reconsidering it worthwhile, its condition and window, its last
demonstrated benefit with its receipt, its [consumer evidence](#consumer-evidence), the owner's
last decision, and notes.

### Plugin component

One census mechanism, the [keep-or-retire list](#keep-or-retire-list)'s unit. Doctrine sections are
not components: they are cut where they are restructured, never measured.

### Retirement condition

A shape, a window, and one action on firing: propose to the owner.

### Catch-based

The [retirement condition](#retirement-condition) shape that counts the component's real catches
over its window, and fires when the window elapses with none.

### Citation-based

The [retirement condition](#retirement-condition) shape that counts receipts relying on the
component's rule over its window, and fires when the window elapses with none.

### Usage-based

The [retirement condition](#retirement-condition) shape that counts invocations of the component
over its window, and fires when the window elapses with none.

### Real catch

A firing on a genuine defect that was acted on and named in a receipt.

### Noise

A firing that led to no accepted finding.

### Citation

A receipt relying on a rule's substance, whether or not it names the rule. It is the signal a
[citation-based](#citation-based) condition counts, for mechanisms only.

### Consumer evidence

The [keep-or-retire entry](#keep-or-retire-entry)'s field holding any consuming project's or
external user's report about a component, as a receipt. Silence is never a count.

### Unmeasured

A consumer that has not reported on a component, or a component with no signal of any shape.
Never zero.

### Fired

A [retirement condition](#retirement-condition) whose window elapsed with its signal met.

### Proposal

The full-spine item the advisor brings at a [gardening pass](#gardening-pass) for a
[fired](#fired) component.

### Retirement ruling

The owner's word on a [proposal](#proposal): retire, keep, or recalibrate.

### Foundational component

A component with no condition and never queued. Changing it is a spec amendment. Every
foundational component is structural, and most structural components are not foundational.

### Authority surface

A component that implements an owner hard line: the worktree guard, the circuit breaker and its
escalation, model governance, the verify gate, and the vet-receipt spine with its owner half.

## The front door's instruments

### Declined registry

The pinned comment on the [collector](#collector) that archives declined items, one line each,
with the [trigger](#trigger) that reopens it.

### Trigger

The concrete condition on a [declined registry](#declined-registry) line whose firing re-scores the
item at the front door.

### Misses log

The section of the pinned registry comment where the advisor records four kinds of miss:
declined-then-escaped, launched-then-regretted, mis-tiered, and [review escapes](#review-escape).

### Review escape

A bug traced after merge to a PR that had a review. The act that traces it logs it in the [misses log](#misses-log): a vet of a fix, a detective diagnosis, a field report, or the owner's own report. The entry links that PR's [review record](#review-record) and makes one call, missed or seen and left. It counts only from the project's adoption day. The rule for logging it is in [the owner-decisions reference](../skills/showrunner/reference/owner-decisions.md#every-grading-keeps-its-scoring-and-the-misses-log).

### Collector

The one open issue per project that holds proposals awaiting the owner's word. Its issue number is
project configuration.

### Pending-words line

The line in a [gardening record](#gardening-record) that lists the items still waiting on the
owner's word.

## The forward-share dial

### Dial

A project's ceiling on the share of launched lanes that carry machinery work over a [gardening
window](#gardening-window). Each project configures its number, and the plugin ships a default.

### Machinery lane

A launched lane whose issue carries the machinery [kind label](#kind-label): work on the plugin's
own mechanisms.

### Product-forward lane

A launched lane whose issue carries the product [kind label](#kind-label): work that moves the
product toward its users, under the classification convention PHILOSOPHY's forward-share bet
states.

### N

The [dial](#dial) expressed for one wave: the dial times the wave's lane count, rounded down, with
a floor of one when a non-zero dial would round to zero. A project may pin N directly.

### Kind label

`kind:machinery` or `kind:product` on an issue: the advisor's judgment at routing, the owner's at
an epic's ratification, and never set or checked by a tool.

## Cloud builds

### Cloud build

A build that runs in a cloud session of the host platform instead of on the owner's machine. It
follows the same order, review rules, advisor's vet, and merge rules as any build.

### Cloud builder

The builder session of a [cloud build](#cloud-build).

### Cloud lane

A lane of the launch ledger whose builder is a [cloud builder](#cloud-builder). The ledger records
and counts it and gives it the same terminal outcomes as any lane, and every listing of lanes marks
it with the word "cloud".

### Launch report

The advisor's message after a launch that says which build went where: each build "In the cloud" or
"On your machine", with the reason and its fix for any build pointed at the cloud that ran on the
owner's machine.

### Launch word

What the owner says at a launch to name where one build runs, "this one local" or the cloud. It
overrides the project's cloud builds setting for that build.

## Backlog fold-in

### Fold-in rules

The rules for draining the backlog without launch slots: a backlog item rides an epic or a routed
issue as ratified scope instead of taking a lane of its own.

### Folded-in items

Backlog items absorbed into an epic or a routed issue under the [fold-in rules](#fold-in-rules).

## Workaround markers

### Workaround marker

A marker on temporary scaffolding, paired with a [delete-when condition](#delete-when-condition).

### Delete-when condition

The condition paired with a [workaround marker](#workaround-marker). When it comes true, the marker
and what it guards are candidates for removal.

## What a project configures

### Project configuration

The values a project supplies through `configure` that the plugin's rules read.

### Configuration item

One value within [project configuration](#project-configuration).

### Risk and trust

The [configuration item](#configuration-item) that holds the project's threat model ("what we
defend against") and its [risk areas](#risk-area). It is set up with the owner in one sitting with
the advisor.

### Risk area

A named part of the project where a mistake costs money, customer data, safety, access, or something
that cannot be undone. It names the parts it covers, why it is risky, and how hard a mistake there is
to undo. A folder it names covers every file beneath that folder. A change that touches one is matched
from the area itself, without model judgment.

### Calibration

The settings a review runs on: the project's [Risk and trust](#risk-and-trust) item and its [standing rulings](#standing-ruling) about leftovers. It changes only on the owner's yes, whether the change tightens or loosens it.

### Ground-truth sources

The sources whose word is taken as true without further checking, such as CI's exit code or git's
history. Every claim points at one of them in a single step. The set is an enumeration, not a
scoring instrument, and each project configures it.

## Process prose and its tests

### Always-loaded set

The process prose a session carries from its start: its charter, the covenant, and the doctrine
its charter loads. Each role carries its own share.

### Keep list

The stamped file listing the test files that delete-on-contact never deletes. It is the only
record that rule reads.

### Rail

A small standing check that guards a process rule mechanically, such as a CI check or a pinned
test, listed by id in the rail inventory.

### Doctrine surface

A file of the [always-loaded set](#always-loaded-set) or a reference doc a charter points to:
process prose, as opposed to code and its tests. The pin rule applies to tests on these.

### Foreign catch

A pre-existing test going red on a later change that did not touch the test. A regression in the
test's own module counts. Its one consequence is a line on the [keep list](#keep-list).

## Native stacks

### Stack

A GitHub-side object numbering an ordered set of pull requests over one base branch. Every multi-PR
child of this project is a native stack; an exception is owner-ruled and recorded. See
[native-stacks.md](native-stacks.md) for the object model and tooling.

### Layer

One pull request in a stack, at one position, based on the branch of the layer below, with its own
sub-issue of the feature issue it breaks down. See [Each layer is a
sub-issue](native-stacks.md#each-layer-is-a-sub-issue), [native-stacks.md](native-stacks.md) § What a
layer is, and the workhorse charter §2 for the lane lifecycle.

## Threat and component tags

### Threat tags

What a component on the machinery map assumes. A means an untrusted repository, B means agent
mistakes, C means a sincere but wrong self-report, and none means no assumption.

### Tag: structural

The component guards a property no model strength removes: independence of maker and checker,
approval as an authority fact, hard context boundaries, the difference between a green run and a
detector that cannot fail. Examples: the worktree guard, the bite-proof rule, the base pin on
residual counts. A zero count means the guard is doing its job.

### Tag: capability-gap

The component guards a behavior a strong, honest model would not show: fabricating after an
exhausted search, omitting a required line, restating a rule already loaded. Examples: the excuse
tables, chain-of-verification as a five-step procedure, the `Closes #` template line, the severity
closed-enum prose. A zero count means the component is probably outgrown, and the
[proposal](#proposal) says so.

### Tag: harness-limit

The component exists because of a property of the host, not of the model or the problem: turn-end
death, transcript-file liveness, the bash-timeout hook. It retires when the host property changes.
It is a [workaround marker](#workaround-marker)'s [delete-when
condition](#delete-when-condition) wearing a tag.

### Tag: mixed

Part structural, part capability-gap. The entry names which part is which so a
[proposal](#proposal) can split it. Example: the gate-write helper, whose `reset` mode and decisions
plumbing are structural (how an approval is revoked and recorded is a property of how the gate is
built) and whose legacy `certify` mode is capability-gap baggage left from the retired plan and
tasks legs.

## Review sheets

### Card

One call for the owner on a [sheet](#sheet): the kind of call, the question, its context, any
images and options, a recommendation, and the owner's answer and note.

### Sheet

A set of [cards](#card) sent to the owner at one time, drawn by the plugin's review template.

### Remainder sheet

A [sheet](#sheet) that holds only what nothing already rules on: no board, ruling or earlier answer
covers it. It also holds the findings the review didn't settle and the declines the reviewer still
contests.

### Ready for vet

The owner's word that the spec may go to the advisor's vet. It is not approval, and a
[sheet](#sheet)'s answers or silence never stand in for it.

### Review record

The plain account of one PR's review, written when the review ends on any lane. It holds what was checked, which reviewers ran, every finding and what happened to it, CI on the final commit, and what is left. Each review session adds its own record comment to the PR and never edits an earlier one; each reviewer's raw output is kept in its own comment that the record links. The rule for writing it is in [the review record reference](../skills/review-code/reference/review-record.md).

### Maker

Any model that built or fixed the product's code under review. The build session is a maker of every fix it applies. A reviewer that only writes break-it tests for a change is not a maker of it.

### Leftover

A finding with a real consequence that the review left unfixed, and that no on-record decision settles. It comes to the owner under "What you're accepting" on the PR's [sheet](#sheet), whatever its severity. Its outcome in the [review record](#review-record) is `left-for-owner`.

### Test role

The review panel's test seat. For each changed test it asks whether the test would fail if the code were wrong, and it reports tests that check nothing, pass by chance, or bloat the change. It asks for no coverage outside the project's risk areas and raises no test-style findings. Its method is in [the test role's agent file](../agents/test-role.md).

### Break-it test

A test written only by the [test role](#test-role), to try to break a change on a named risky scenario: either attached to one of its findings or as a finding of its own for a risk area. The build session runs it once, in its own working copy, on the unfixed code. The run judges nothing: its result is saved with the finding and handed to the [verifier](#verifier), and a passing run does not drop the finding. The test stays with the change once its finding is fixed. The shape is in [the test role's agent file](../agents/test-role.md).

### Verifier

The independent reviewer that grades each finding on its own as confirmed, plausible or wrong,
with its reason, using the output of the finding's [break-it tests](#break-it-test) where there
are any. It is the only one that closes a finding as wrong (`shown-wrong` in the
[review record](#review-record)); the build session, the other reviewers and every filter may
keep, merge or carry a finding, but never close it as wrong. When a passing break-it test never
reached the path its finding describes, a fresh run of the [test role](#test-role) writes one
more test, and then the verifier decides; no third test is written. The pass is in
[the verification pass reference](../skills/review-code/reference/verification-pass.md).

### Extra audit round

The one extra round the advisor may order at the vet for a PR a session handed back at the 4-round cap. It audits only the fixes the cap round applied, runs no panel and no new search, and is allowed once per PR. The [review record](#review-record) labels it and does not count it in its rounds. The rules are in [the round driver reference](../skills/review-code/reference/round-driver.md#the-extra-audit-round).

## Cloud builds

### Cloud environment

The place on the cloud platform where the owner pastes the [setup text](#setup-text) and the
[reviewer pass](#reviewer-pass).

### Cloud setup

A project's [cloud environment](#cloud-environment) after a [check session](#check-session) has
passed. It belongs to the Claude account it was made on.

### Setup text

The block the plugin writes for the owner to paste into the [cloud environment](#cloud-environment).
It holds no secret. A project that commits the plugin pin hook gets a plugin release in its cloud
builds by a new pin commit, without a paste.

### Reviewer pass

The sign-in the owner places in the [cloud environment](#cloud-environment) so the independent
reviewer can run there.

### Check session

The one short cloud session that proves a [cloud setup](#cloud-setup).
