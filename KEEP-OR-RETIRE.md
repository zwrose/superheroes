# Keep-or-retire list and workaround-marker inventory

## Framing

You read this file at a [gardening pass](plugins/superheroes/rubric/glossary.md#gardening-pass). Nothing checks it mechanically and it gets no guard. Its vocabulary is the shipped glossary at [plugins/superheroes/rubric/glossary.md](plugins/superheroes/rubric/glossary.md); this file defines no term of its own and points there once. This file is this repository's own record, the same class of document as `LEDGERS.md`, and the rules it applies ship in the glossary and the rubric.

## How an entry is built

A [keep-or-retire entry](plugins/superheroes/rubric/glossary.md#keep-or-retire-entry) has six fields, in this fixed order:

1. **Component** — the census row, by its stable id and name, and the cost or annoyance that makes reconsidering it worthwhile.
2. **Condition** — one of the three shapes, its window in calendar days, and the one action on firing.
3. **Last demonstrated benefit** — what the component did, described, with its locator in parentheses; or `unknown`.
4. **Consumer evidence** — a consuming project's or external user's report, described, with its locator in parentheses; or `unmeasured`.
5. **Decision** — the owner's latest decision. Every non-foundational entry reads `keep-until-condition-fires`.
6. **Notes** — the tag, its one-line reason, and, where the component guards a model behaviour, the engine family the evidence was observed on.

**Condition shapes and default windows.** The three shapes are [catch-based](plugins/superheroes/rubric/glossary.md#catch-based) (45 days), [citation-based](plugins/superheroes/rubric/glossary.md#citation-based) (45 days), and [usage-based](plugins/superheroes/rubric/glossary.md#usage-based) (60 days). You choose one shape per component. When you use a window other than the default, state it with its reason.

**What a condition must name.** A well-formed condition names its signal, its window, and its action. The only valid action is a proposal to the owner at a gardening pass. The most aggressive outcome of a condition firing is a conversation.

**Deterrent and by-construction-silent components.** Deterrent and by-construction-silent components take citation-based or usage-based conditions, never catch counts. A fail-closed gate's zero catches may mean it is working. Write every entry against this rule.

**Unmeasured is not zero.** A component with no signal of any shape is [unmeasured](plugins/superheroes/rubric/glossary.md#unmeasured); a consumer that has not reported on a component is unmeasured for it. An absent, unreadable, or short-of-window record reads unmeasured. Silence never counts as a clean window.

**Tags and the decision rubric.** The tag is one of the glossary's four: [structural](plugins/superheroes/rubric/glossary.md#tag-structural), [capability-gap](plugins/superheroes/rubric/glossary.md#tag-capability-gap), [harness-limit](plugins/superheroes/rubric/glossary.md#tag-harness-limit), or [mixed](plugins/superheroes/rubric/glossary.md#tag-mixed). A zero count means keep for structural, probably outgrown for capability-gap, wait for the host to change for harness-limit, or split the line for mixed. Apply this rubric: **structural** where the component guards a property of how this system is built and no change of host or model would remove the need; **capability-gap** where it compensates for something a model cannot yet do reliably; **harness-limit** where it works around something the host does not offer; **mixed** where two of those apply to different parts of the same component, in which case the entry names which part is which.

**Landed vs plain keep.** A component whose entry has not landed is a plain keep. A landed non-foundational entry is keep-until-condition-fires from the moment it lands.

**Birth duty.** A new component ships with its entry, its condition, and its tag at birth.

## The foundational set

A [foundational component](plugins/superheroes/rubric/glossary.md#foundational-component) has no condition and is never queued. Changing one is a spec amendment. The foundational set as it stands at landing is the covenant's hard lines, read from [plugins/superheroes/rubric/covenant.md](plugins/superheroes/rubric/covenant.md), and nothing else:

- **Never merge, release, or publish on your own authority.**
- **Review before handback.**
- **Receipts before claims.**
- **Disclose degradation** where the owner reads — the PR body, not a buried log.
- **Park, don't presume.**

Every foundational component is structural, and most structural components are not foundational.

### The authority surfaces

Five [authority surfaces](plugins/superheroes/rubric/glossary.md#authority-surface) implement owner hard lines: the worktree guard, the circuit breaker and its escalation, model governance, the verify gate, and the vet-receipt spine with its owner half. The owner sets each to a condition or to foundational. A condition on a component implementing an owner hard line is never a standing licence on that surface.

**Worktree guard.** Owner's look: pending at landing.

**Circuit breaker and its escalation.** Owner's look: pending at landing.

**Model governance.** Owner's look: pending at landing.

**Verify gate.** Owner's look: pending at landing.

**Vet-receipt spine with its owner half.** Owner's look: pending at landing.

## The consumer-report lifecycle

- A consumer report is an issue on this repository carrying the `consumer-report` label and the shipped template: the project and plugin version, the component, what was expected and what happened, and a pointer to the lane, dispatch, journal, or receipt that evidences it.
- Anyone may file one. A consuming project's advisor files them as a matter of course. A report delivered by any other channel is filed as that issue on receipt, so a message queue never defers a firing past the next gardening pass after delivery.
- Each open report is linked from its component's entry as a receipt, and is closed when a gardening pass has read it or a proposal it fed has been ruled.
- A consumer with no report on a component is unmeasured for it, never a count. Every proposal names the consumers it could not measure.
- Before a retirement proposal on a component a known consumer uses, the advisor asks through an existing channel and waits at most one gardening window. No answer is recorded as unmeasured, never as consent, and the proposal proceeds saying so.
- The evidence bar is the record pointer. A report with no record behind it is a conversation, not a firing.

### A worked example

This illustration uses a fictional component named `example-guard` that appears nowhere else in this file or the repository.

1. A consumer files an open report. The entry links it as a receipt in consumer evidence.
2. A gardening pass reads the report and closes it. The entry's consumer-evidence field carries the closed report as its locator.
3. A second consumer filed nothing. The same field shows `unmeasured` for that consumer.

## The keep-or-retire list

The list's units are the census rows, and each entry is keyed to its census id.

### A. Session gates & hooks

### A6 — source_guard

- **Component.** A pytest guard that blocks writes to shipped Python source during test runs; it costs session setup and parallel-run overhead on every suite invocation.
- **Condition.** Catch-based, 45 days: real catches of shipped-source mutation under parallel test execution. On firing, a proposal to the owner at a gardening pass.
- **Last demonstrated benefit.** Caught a shipped-source mutation race under pytest-xdist parallel execution (#1153).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** structural — a zero catch count means the guard is doing its job, not that the race is gone.

### B. Launch & wave machinery

### B5 — Environment probes

- **Component.** Scaffold probes that detect harness and worktree environment faults before dispatch; the row covers `harness_probe`, `sibling_worktree_probe`, and `hostinfo`, which differ in wiring and retirement posture.
- **Condition.** Citation-based, 45 days: vet, forfeit-dispute, or incident receipts that cite the probe rule's substance for `sibling_worktree_probe`. On firing, a proposal to the owner at a gardening pass. `hostinfo` has no separate condition; `harness_probe` is retired and is not counted.
- **Last demonstrated benefit.** `sibling_worktree_probe` guards false worktree-dirtied forfeits with a wired reader on every terminal dispatch fold (wired reader, zero recorded catches).
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** harness-limit for `sibling_worktree_probe` — the host offers no native worktree-liveness signal; structural for `hostinfo` — load-bearing file-lock consumer with a real defect class behind it.

### D. Certified review loop

### D1 — Round driver core

- **Component.** The certified review loop's round driver substrate and gate; it costs ongoing contract maintenance and is the hub where certification drop-off is measured.
- **Condition.** Usage-based, first 10 post-shrink full lanes: the signal is full lanes reaching certified completion against full lanes run; on firing, a retirement-or-indictment proposal to the owner. Abandonment fires the same condition: fewer than 10 full lanes within 60 calendar days.
- **Last demonstrated benefit.** unknown.
- **Consumer evidence.** unmeasured.
- **Decision.** keep-until-condition-fires.
- **Notes.** mixed — the parse and refusal shell is structural; the exact-token certification contract is capability-gap until the re-spec lands.

<!-- remaining entries land here -->

## The workaround-marker inventory

A platform workaround in this tree carries the marker `WORKAROUND:` in a comment, immediately followed by a `delete-when:` line naming the [delete-when condition](plugins/superheroes/rubric/glossary.md#delete-when-condition) that makes it removable. When the condition comes true, the workaround is promoted into a real fix or removed, never left as unmarked ritual. A gardening pass reports the markers whose condition has come true. The inventory below lists every marked site in the tree, and a grep for the tag over the tree, excluding this file, returns exactly that set.

<!-- inventory lands here -->
