# Glossary

This file is the one home for the project's ruled vocabulary. Every other surface
cites a slug from here, and no surface restates a definition. When prose elsewhere
needs a ruled term, link to its heading rather than paraphrasing it.

## Owner decisions and walks

### Ruling

Any decision the owner gives, in any session.

### Decision walk

Any sitting in which the owner takes batched decisions, from the command or from a
conversation. "Walk" alone means this.

### Craft call

A decision the advisor decides, executes, and records for veto.

### Owner call

The owner's word; doubt resolves to an [owner call](#owner-call).

### Material consequence

The line between a [craft call](#craft-call) and an [owner call](#owner-call), defined
by [configuration item](#configuration-item) 13: a plugin default illustrated by each
project's own examples, evolved by the owner's [rulings](#ruling) at walks, never
checked by a tool.

### Priority tiers

The four tiers are **P0**, **P1**, **P2**, and **declined**. *P0* is the next wave —
rare by construction, and every P0 names what it displaces. *P1* enters the standing
budget soon on the owner's word, batched at a walk, and ages — at each [gardening
pass](#gardening-pass) an old P1 is proposed for promotion, demotion, or decline.
*P2* should eventually happen, files without an owner word, lives in the backlog and
drains mostly by being folded in. *Declined* is below the bar — a [declined
registry](#declined-registry) line and a [trigger](#trigger), nothing on the board.

## Gardening and condition windows

### Gardening pass

The periodic sweep.

### Gardening record

The comment a [gardening pass](#gardening-pass) leaves.

### Gardening window

The calendar span between two [gardening records](#gardening-record).

### Condition window

The calendar span one [retirement condition](#retirement-condition) counts over.

## The keep-or-retire list and its entries

### Keep-or-retire list

The hand-kept list of every [plugin component](#plugin-component), one line each, that
makes retirement the default.

### Keep-or-retire entry

One component's entry on the [keep-or-retire list](#keep-or-retire-list): the
component and the cost or annoyance that makes reconsidering it worthwhile; its
condition and window; its last demonstrated benefit with its receipt; [consumer
evidence](#consumer-evidence); the owner's last decision; notes.

### Plugin component

One census mechanism. The [keep-or-retire list](#keep-or-retire-list)'s unit; doctrine
sections are not components; they are cut where they are restructured, never measured.

### Retirement condition

A shape, a window, and one action: propose to the owner.

### Catch-based

One of the three [retirement condition](#retirement-condition) shapes.

### Citation-based

One of the three [retirement condition](#retirement-condition) shapes.

### Usage-based

One of the three [retirement condition](#retirement-condition) shapes.

### Real catch

A firing on a genuine defect that was acted on and named in a receipt.

### Noise

A firing that led to no accepted finding.

### Citation

A receipt relying on a rule's substance, whether or not it names it; the signal a
[citation-based](#citation-based) [retirement condition](#retirement-condition) counts,
for mechanisms only.

### Consumer evidence

The [keep-or-retire entry](#keep-or-retire-entry)'s field holding any consuming
project's or external user's report about a component, as a receipt; silence is never
a count.

### Unmeasured

A consumer that has not reported on a component, or a component with no signal of any
shape; never zero.

### Fired

A [retirement condition](#retirement-condition) whose window elapsed with its signal met.

### Proposal

The full-spine item the advisor brings at a pass for a [fired](#fired) component.

### Retirement ruling

The owner's word on a [proposal](#proposal): retire, keep, or recalibrate. "Kill" names
only the CP2 list K1 to K6.

### Foundational component

No condition, never queued; change is a spec amendment. Every foundational component
is structural; most structural components are not foundational.

### Authority surface

A component implementing an owner hard line: the worktree guard, the circuit breaker and
escalation, model governance, the verify gate.

## Priority-tier instruments

### Declined registry

One of the priority-tier instruments.

### Trigger

One of the priority-tier instruments.

### Misses log

One of the priority-tier instruments.

### Collector

One of the priority-tier instruments; issue #695.

### Pending-words line

One of the priority-tier instruments.

## Forward-share dial

### Dial

One of the forward-share dial controls.

### Machinery lane

One of the forward-share dial lanes.

### Product-forward lane

One of the forward-share dial lanes.

### N

One of the forward-share dial parameters.

### Kind label

`kind:machinery` or `kind:product` on an issue: the advisor's judgment at routing, the
owner's at an epic's ratification; never set or checked by a tool.

## Backlog fold-in

### Fold-in rules

The rules for draining the backlog without launch slots.

### Folded-in items

Backlog items absorbed into an epic or a routed issue under them.

## Reset vocabulary

### Background-session trial

One hand-run wave on the host's background-session primitive across all three accounts,
early in the reset, whose receipt decides whether the six orchestration workarounds
retire. Not test-pilot.

### Child names

The landing epic's work items carry descriptive names: founding-documents;
committed-docs correction (docs-truth); merge-gate retirement (owner-authority);
[keep-or-retire list](#keep-or-retire-list) rollout; charter-restructure (E10 diet);
calmer-reviews (Change-4); eval-cadence (H4, removed 2026-09-13); dispatch-shell (C1);
certification (D1); CLI-Claude engine (R5); orchestration-decommission (R3);
sanitized-view shrink; Astra registration. Names are reference vocabulary; the epic's
shape is decided at the package breakdown.

### Workaround marker

A marker on temporary scaffolding, paired with a [delete-when condition](#delete-when-condition).

### Delete-when condition

The condition paired with a [workaround marker](#workaround-marker); when it comes true,
the marker and what it guards are candidates for removal.

## What a project configures

### Project configuration

The values a project supplies through `configure` that the plugin's rules read.

### Configuration item

One value within [project configuration](#project-configuration); a project supplies
thirteen of them through configure.

### Ground-truth sources

The sources whose word is taken as true without further checking, such as CI's exit
code or git's history; every claim must point at one of them in a single step. It is an
enumeration, not a scoring instrument, and it is configured per project.

## Process prose and tests

### Always-loaded set

The seven files of loaded process prose across the three roles (each charter, the
covenant, the launch, dispatch, and review-discipline doctrine); a given session carries
its own role's share, which is what the charter-restructure child measures.

### Keep list

The stamped file listing the test files delete-on-contact never deletes; the only record
that rule reads (no catch ledger, no per-file credits).

### Rail

A small standing check that guards a process rule mechanically (a CI check or a pinned
test), listed by id in the rail inventory.

### Doctrine surface

A file of the [always-loaded set](#always-loaded-set) or a reference doc a charter
points to; process prose, as opposed to code and its tests. The pin rule applies to
tests on these.

### Foreign catch

A pre-existing test going red on a later change that did not touch the test (the
verification investigation's regression-catch class); a regression in the test's own
module counts. Its one consequence is a line on the [keep list](#keep-list).

## Threat and component tags

### Threat tags on the machinery map

**A**, an untrusted repo; **B**, agent mistakes; **C**, a sincere but wrong
self-report; or none.

### Tag: structural

Guards a property no model strength removes: independence of maker and checker,
approval as an authority fact, hard context boundaries, the difference between a green
run and a detector that cannot fail. Examples: the worktree guard, the bite-proof rule,
the base pin on residual counts. A zero count means the guard is doing its job.

### Tag: capability-gap

Guards a behavior a strong, honest model would not show: fabricating after an exhausted
search, omitting a required line, restating a rule already loaded. Examples: the excuse
tables, chain-of-verification as a five-step procedure, the `Closes #` template line,
the severity closed-enum prose. A zero count means the component is probably outgrown,
and the [proposal](#proposal) says so.

### Tag: harness-limit

Exists because of a property of the host, not of the model or the problem: turn-end
death, transcript-file liveness, the bash-timeout hook. Retires when the host property
changes; the [workaround marker](#workaround-marker)'s [delete-when
condition](#delete-when-condition) wearing a tag.

### Tag: mixed

Part structural, part capability-gap; the line names which part is which so a
[proposal](#proposal) can split it. Example: the seat canary, whose engagement axis is
structural (a silent transport; read from telemetry) and whose plant-detection axis is
a competence test, now a sampled probe.
