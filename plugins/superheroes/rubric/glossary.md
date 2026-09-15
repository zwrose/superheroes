# Glossary

The one home for the plugin's ruled vocabulary. Every other surface cites a term by its heading
anchor and states no definition of its own. When prose elsewhere needs one of these words, link
the heading rather than paraphrasing it.

## Owner decisions and walks

### Ruling

Any decision the owner gives, in any session.

### Decision walk

A sitting in which the owner takes batched decisions, from the command or from a conversation.
"Walk" alone means this.

### Craft call

A decision the advisor decides, executes, and records for the owner's veto.

### Owner call

A decision that waits for the owner's word. Doubt resolves to an [owner call](#owner-call).

### Material consequence

The line between a [craft call](#craft-call) and an [owner call](#owner-call): a change with a
material consequence is the owner's to accept. Each project configures the line as a plugin default
illustrated by the project's own examples, evolves it by the owner's [rulings](#ruling) at walks,
and never checks it by tool.

### Priority tiers

The four tiers an item can hold at the front door: P0, P1, P2, and declined. P0 is the next wave,
rare by construction, and every P0 names what it displaces. P1 enters the standing budget on the
owner's batched word at a walk, and ages: at each [gardening pass](#gardening-pass) an old P1 is
proposed for promotion, demotion, or decline. P2 should eventually happen, files without an owner
word, and drains mostly by being folded in. Declined is below the bar: a [declined
registry](#declined-registry) line with a [trigger](#trigger), and nothing on the board.

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
cost or annoyance that makes reconsidering it worthwhile; its condition and window; its last
demonstrated benefit with its receipt; its [consumer evidence](#consumer-evidence); the owner's
last decision; and notes.

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

A receipt relying on a rule's substance, whether or not it names the rule; the signal a
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

A component with no condition, never queued; changing it is a spec amendment. Every foundational
component is structural; most structural components are not foundational.

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

The section of the pinned registry comment where the advisor records three kinds of miss:
declined-then-escaped, launched-then-regretted, and mis-tiered.

### Collector

The one open issue per project that holds proposals awaiting the owner's word. Its issue number is
project configuration.

### Pending-words line

The line in a [gardening record](#gardening-record) that lists the items still waiting on the
owner's word.

## The forward-share dial

### Dial

A project's ceiling on the share of launched lanes that carry machinery work over a [gardening
window](#gardening-window). The plugin default is 20 to 30 percent; each project configures its own
number.

### Machinery lane

A launched lane whose issue carries the machinery [kind label](#kind-label): work on the plugin's
own mechanisms.

### Product-forward lane

A launched lane whose issue carries the product [kind label](#kind-label): work that moves the
product toward its users. Test-pilot work is product.

### N

The [dial](#dial) expressed for one wave: the dial times the wave's lane count, rounded down, with
a floor of one when a non-zero dial would round to zero. A project may pin N directly.

### Kind label

`kind:machinery` or `kind:product` on an issue: the advisor's judgment at routing, the owner's at
an epic's ratification, and never set or checked by a tool.

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

## Threat and component tags

### Threat tags

What a component on the machinery map assumes: A, an untrusted repository; B, agent mistakes; C,
a sincere but wrong self-report; or none.

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
[proposal](#proposal) can split it. Example: the seat canary, whose engagement axis is structural
(a silent transport, read from telemetry) and whose plant-detection axis is a competence test,
now a sampled probe.
