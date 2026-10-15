---
superheroes: doc
schemaVersion: 1
docType: spec
workItem: sever-the-superpowers-dependency-and-retire-the-ma-2f84ef
issue: 111
size: large
status: draft
gates: {review: pending}
producedBy: "the-architect@0.3.0"
created: "2026-07-01"
updated: "2026-07-02"
---
# Sever the superpowers dependency and retire the manual path

## Purpose

The superheroes plugin grew up inside the superpowers plugin's scaffolding: the manual
pipeline invokes two superpowers skills to do its work (tasks decomposition and the
build loop), the native pipeline still borrows its tasks-authoring method from
superpowers by reference, and the public story says "powered by superpowers." The
showrunner now carries the whole post-approval pipeline natively, so the borrowed
scaffolding is duplication and drift risk, and the dependency makes the plugin
incomplete on any machine that doesn't also have superpowers. This work removes the
dependency entirely: one post-approval path (the showrunner), one host (Claude Code),
authoring methods the plugin owns outright, and an honest "inspired by" credit.
(GitHub issue #111.)

## Who it's for

- **The owner** — runs work-items from idea to a ready-for-review PR and wants exactly
  one dependable path to maintain, with no parallel manual pipeline drifting out of sync.
- **A new installer** — installs superheroes on a machine that has never seen
  superpowers and gets a fully working plugin, with every advertised capability usable.

## Functional requirements

**FR-1.** When a spec receives the owner's final approval, the plugin shall offer
exactly one way to run the work-item: launching the showrunner.
  - *Acceptance (Given-When-Then):* Given a spec whose review gate has just been
    recorded as passed, when discovery hands off, then the owner is offered the
    showrunner launch and no manual-path alternative, and no path-choice record is
    written (the path-choice machinery is gone).

**FR-2.** The plugin shall not offer the manual pipeline commands — `workhorse`,
`architect-plan`, `architect-tasks`, `review-plan`, `review-tasks` — as invocable
skills.
  - *Acceptance (rule):* The installed plugin's skill catalog contains none of the
    five retired commands; the surviving cast (discovery, spec authoring,
    review-spec, review-code, showrunner, configure, the test-pilot commands,
    audit-debt, and the init helpers) is unchanged.

**FR-3.** The plugin shall own the tasks-authoring method — the decomposition rules a
tasks doc is written by (bite-sized test-first steps, exact file paths, shared
global constraints, per-task interfaces, the no-placeholders bar) — in reference
material that lives inside the plugin.
  - *Acceptance (Given-When-Then):* Given the showrunner authors a tasks doc, when
    the authoring step resolves its method references, then every referenced
    document lives in the superheroes plugin and none of them names or routes to a
    superpowers skill.
  - *Acceptance (rule):* The native method is at parity with the superpowers
    `writing-plans` method it replaces (despite its name, `writing-plans` is
    superpowers' tasks-decomposition engine — the step-by-step tasks doc is its
    output): authored from it side by side, copying or adapting its text where that
    is the best result, with a parity record delivered with the work — one entry
    per section of the original (split into one entry per rule where a section
    carries more than one distinct rule), each marked carried, adapted, or dropped
    with a reason — and the derived doc carrying the license-attribution notice.
    No silent capability loss.

**FR-4.** The plugin shall keep the plan-authoring method available to the showrunner
after the manual planning command retires.
  - *Acceptance (rule):* The plan-authoring method reference the showrunner's
    authoring step reads survives the retirement in a plugin-owned location, and the
    authoring step's pointer to it resolves.

**FR-5.** The plugin shall define its tasks-document format in its own conventions
and template, with no reference to a superpowers skill or superpowers version.
  - *Acceptance (rule):* The conventions' tasks-doc section and the tasks template
    name every required section natively; the "we target superpowers ≥ 6.0" style
    of format-by-external-reference is gone.

**FR-6.** The plugin shall invoke no superpowers skill on any path.
  - *Acceptance (rule):* A search of every shipped skill, library file, template,
    hook, agent definition, and dispatched prompt finds no superpowers skill
    invocation or route-through.

**FR-7.** If a functional reference to superpowers is reintroduced anywhere in the
plugin, then the repository's continuous-integration checks shall fail.
  - *Acceptance (Given-When-Then):* Given the guard is in place, when any shipped
    plugin file gains a functional superpowers reference (an invocation, a
    read-at-runtime method pointer, or a format defined by superpowers reference),
    then CI fails with a message naming the offending file.
  - *Acceptance (rule):* The guard has a small explicit allowlist for narrative
    mentions — the "inspired by superpowers" credit, the license-attribution notices
    on material derived from superpowers, and historical design-doc path comments —
    and those do not trip it.

**FR-8.** When a build records its provenance, the record shall carry a
superheroes-native engine label.
  - *Acceptance (Given-When-Then):* Given a build completes on the showrunner, when
    its provenance is written, then the engine label is a superheroes-native name —
    not "subagent-driven-development" — and the ship gate's messages name the native
    label.
  - *Acceptance (rule):* Provenance records written before this change remain
    accepted by the ship gate (the gate's decision does not depend on the old label).

**FR-9.** The plugin shall target Claude Code as its only host.
  - *Acceptance (rule):* No Codex plugin manifest, host tool maps, Codex hook
    config, or host-consistency CI step remains; the per-skill host-pointer preamble
    is gone from every skill.
  - *Acceptance (rule):* Engine dispatch — Codex and Cursor as per-role engines — is
    untouched and its existing tests still pass.

**FR-10.** While the pipeline acts on the owner's behalf, the plugin shall keep the
owner-authority guard in force — the pipeline cannot merge, force-push, or push to
the default branch.
  - *Acceptance (rule):* After the dual-host layer is removed, the guard blocks
    those owner-only actions on Claude Code exactly as it does today, and the
    existing safety checks that prove it continue to pass.

**FR-11.** The plugin shall provide a superheroes-native systematic-debugging skill
that the owner can invoke on its own, outside any work-item.
  - *Acceptance (Given-When-Then):* Given a machine with only superheroes installed,
    when the owner asks to debug a failure (no work-item in flight), then the native
    systematic-debugging skill is available and loads with its method
    (understand the failure before changing code; one hypothesis at a time;
    reproduce, isolate, verify).
  - *Acceptance (rule):* The native skill is at parity with the superpowers
    `systematic-debugging` skill it replaces: authored from it side by side,
    copying or adapting its text where that is the best result, with a parity
    record delivered with the work — one entry per section or rule of the original,
    each marked carried, adapted, or dropped with a reason — and the derived skill
    carrying the license-attribution notice. No silent capability loss.
  - *Acceptance (rule):* As a new skill it ships with the repo's required
    skill-eval artifacts, and the skill-shape validation passes.

**FR-12.** While fixing a failing build or a failing CI run, the pipeline shall
follow the native systematic-debugging method.
  - *Acceptance (rule):* The build-fix and CI-fix steps cite the native
    systematic-debugging method as the discipline for diagnosing failures, and cite
    no superpowers equivalent.

**FR-13.** The plugin's public description shall credit superpowers as inspiration,
not as a dependency.
  - *Acceptance (rule):* The README tagline and the marketplace catalog description
    read "inspired by superpowers" (or equivalent credit); no shipped surface says
    "powered by superpowers."

**FR-14.** The repository's surviving documentation and manifests shall contain no
reference to a retired command, the manual bridged path, or the dual-host layer.
  - *Acceptance (rule):* The README hero sections and command tables, the
    conventions document, the repo instructions' CI section, the plugin manifest
    description (which today names the workhorse in its cast), the skill-eval
    registry and its fixtures, and the ignore-file's manual-build scratch entry all
    reflect the post-retirement cast — nothing steers a reader to a retired command.

**FR-15.** When this work completes, a follow-up issue for a superheroes-native
writing-skills equivalent shall exist.
  - *Acceptance (rule):* The issue is filed, references issue #111, and records that
    it waits on a named consumer before being built.

**FR-16.** When the retirement lands, the plugin shall retain no library module,
command-line wrapper, hook code path, or test suite whose only consumers were
retired surfaces.
  - *Acceptance (rule):* The audit behind this covers, at minimum: the allowance
    store (`lib/allowance.py`) and its tests, which exist solely to bridge live
    owner approval across the deny-only Codex host gate and lose their last consumer
    when the Codex host retires (FR-9) — deleted, together with the enforcer's
    deny-only / host-aware branches that issue and consume allowances, its
    apply_patch classification surface (a Codex-host-only tool shape — on Claude
    Code, edits arrive as Edit/Write tool calls, never apply_patch), and the
    precompact hook's allowance-wipe step; and every library module or
    command-line wrapper whose only callers were the five retired commands —
    candidates include the gate-writing helper's certify mode (the showrunner
    records gates through its own doc library, and the surviving review-spec uses
    only the reset mode) and any front-half entry points only the retired
    plan/tasks skills invoked. Anything with a named surviving consumer
    (review-code, review-spec, audit-debt, configure, the test-pilot commands, or
    the showrunner spine) is kept.
  - *Acceptance (rule):* A disposition record ships with the work — one row per
    audited module or hook branch, marked **kept** (naming its surviving consumer)
    or **deleted**. Nothing ships that no surviving surface can reach.
  - *Acceptance (rule):* FR-10's acceptance passes **after** these deletions — the
    owner-authority guard's survival is demonstrated with the allowance branches
    gone, not by leaving them in place.

**FR-17.** When this work completes, a follow-up issue proposing the JS-canonical
decider collapse shall exist.
  - *Acceptance (rule):* The issue is filed; references issue #111 and the planned
    native-skills sunset; proposes making the showrunner's bundled JS decision
    twins canonical for pure decision logic — deleting the then-orphaned Python
    decider twins and the parity suite that today holds the two sides equivalent,
    keeping Python only at the input/output boundaries — and records that it waits
    on the sunset of the remaining Python-loop consumers (review-code, review-spec,
    audit-debt) before being built: the named-consumer rule, in reverse. This
    work-item does not orphan those deciders (the surviving review commands still
    drive the Python side), so the issue is the deliverable — building the collapse
    is out of this work-item's scope.

## When things go wrong (significant unhappy paths)

**UFR-1.** If a work-item carries a recorded "manual" path choice from before this
change, then the showrunner shall run that work-item from its approved spec as if no
record existed.
  - *Acceptance:* Given a work-item with an approved spec and a stale advisory
    "manual" path-choice record, when the owner launches the showrunner on it, then
    the run proceeds normally and the stale record changes nothing.

**UFR-2.** If the showrunner encounters a tasks draft in the retired old format
(bold-label headings instead of the native section headings), then the system shall
keep that draft from advancing to the build — a parked run the
owner fixes manually is an acceptable outcome, and the plugin gains no handling
dedicated to old-format drafts.
  - *Acceptance:* Given a pre-change tasks draft in the old format, when the
    showrunner's authoring step evaluates it, then the old-format draft itself never
    reaches the build: the run either parks for the owner to fix, or the draft is
    replaced through the authoring step's existing generic behavior.
  - *Acceptance (rule):* No code or requirement specific to detecting or migrating
    old-format drafts is added — this case is rare enough that manual fix-up on a
    parked run is the accepted answer.

**UFR-3.** If the plugin is installed on a machine where superpowers was never
installed, then every shipped command shall work without any error about a missing
skill.
  - *Acceptance:* Given a fresh machine with only superheroes installed, when the
    owner exercises each surviving command's entry path, then no step attempts to
    load a superpowers skill and no command degrades or fails for its absence.

**UFR-4.** If a work-item has an unfinished manual-path run (an open build branch or
worktree) when the retirement lands, then the plugin shall leave that run untouched
for the owner to finish manually — it neither migrates nor resumes it.
  - *Acceptance:* Given a work-item with an in-progress manual build at upgrade
    time, when the retirement lands, then the branch and worktree remain as ordinary
    version-control artifacts the owner completes by hand; no migration or resume
    machinery exists for it.

## Non-functional requirements

- **Standalone completeness:** a machine with only this plugin installed can run
  every capability the README advertises. *Fit:* the UFR-3 acceptance passes.
- **Regression loudness:** an accidental reintroduction of the dependency is caught
  by machine checks, not by a human noticing. *Fit:* the FR-7 guard runs in CI on
  every PR and push to main.

## Definition of done / success

- On a machine without superpowers, an owner can take a work-item from idea →
  approved spec → showrunner run → ready-for-review PR, with no superpowers skill
  involved at any step and no reference to one surfacing in the run.
- The repository's full validation (the remaining validators and the whole test
  suite) is green with the host-consistency CI step removed.
- The whole-plugin superpowers-free guard (FR-7) is in CI and passing.
- The native tasks-authoring method and systematic-debugging skill each ship with
  their parity record against the superpowers version they replace (FR-3/FR-11) —
  nothing the originals taught is silently lost.
- The README, conventions, and repo-instruction docs read correctly for the
  post-retirement cast in the same change that retires it (FR-13/FR-14).
- The writing-skills follow-up issue exists (FR-15), and the JS-canonical
  decider-collapse follow-up issue exists (FR-17).
- The retired-machinery disposition record ships with the work (FR-16) — every
  audited module or hook branch marked kept-with-consumer or deleted, and nothing
  remains that only a retired surface could reach.

## Assumptions & dependencies

- **Showrunner confidence:** by the time this work merges, the owner considers the
  showrunner path proven for carrying real work-items (owner decision, 2026-07-01).
  Until merge, the manual path remains available on the main branch as the fallback.
- **Engine layer present:** Codex/Cursor per-role engine dispatch (issue #38) is
  merged and stays; retiring Codex as a *host* does not touch Codex as an *engine*.
- **Owner's machine:** the superpowers plugin may remain installed on the owner's
  machine for personal use; this work changes only what superheroes itself requires
  and invokes.
- **License:** superpowers is MIT-licensed (verified 2026-07-01, © 2025 Jesse
  Vincent), so copying or adapting its method text into superheroes-native docs is
  permitted; derived material carries the attribution notice the license requires.
- **Tracking:** GitHub issue #111 is the work's home; #115 landed the format-only
  half of the tasks-authoring severance that FR-3 completes.
- **Showrunner review is self-contained:** the showrunner reviews the documents it
  authors with its own built-in review step, which does not depend on the retiring
  review-plan / review-tasks commands — so retiring them removes no review coverage
  from the showrunner path.

## Constraints

- **Recoverability:** retirement happens through normal version-controlled changes —
  everything retired stays recoverable from history; no history rewriting.
- **Scope discipline:** the showrunner's behavior contract is not redesigned here —
  changes are limited to severing references, relabeling provenance, owning the
  authoring methods, and removing the retired surfaces along with the machinery
  beneath them that only those surfaces reached (FR-16).
- **Breaking-change honesty:** retiring invocable commands and a host is a breaking
  change for anyone using them; the release that ships this work presents it as such.

## Out of scope

- A superheroes-native writing-skills equivalent (deferred to the FR-15 follow-up
  issue, per the named-consumer rule).
- Building the JS-canonical decider collapse — deleting the Python decider twins
  and the parity suite (FR-17 files the issue; the build waits on the sunset of the
  remaining Python-loop consumers).
- Any new showrunner capability or redesign of its phases.
- Automating the Discovery front-half (it stays an owner dialogue).
- Removing or altering the superpowers plugin on the owner's machine.
- Renaming the historical local design-doc directories whose paths appear in code
  comments (allowlisted as narrative).
- Any change to the Codex/Cursor engine-dispatch layer.

## Open questions

*(none — all resolved with the owner during discovery)*

## Glossary

- **superpowers** — the third-party plugin superheroes historically wrapped for
  tasks decomposition and the build loop.
- **Manual bridged path** — the owner-invoked plan → tasks → build command sequence
  being retired; the showrunner replaces it.
- **Showrunner** — the pipeline that takes an approved spec to a ready-for-review PR.
- **Host vs. engine** — the *host* is the harness the plugin runs on (Claude Code
  after this work); an *engine* is a coding CLI a build or review step dispatches
  work to (Codex, Cursor) — engines are unaffected.
- **Functional vs. narrative reference** — *functional*: invoked at runtime, read at
  runtime as method, or defining a format by reference; *narrative*: a credit line
  or historical comment. The FR-7 guard blocks the former and allowlists the latter.

## Coverage

| Area | Disposition | Where / why |
| --- | --- | --- |
| Empty & first-run | Specify | UFR-3 — a fresh machine without superpowers is this work's first-run state. |
| Invalid & malformed input | Specify | UFR-2 — a pre-change bold-label tasks draft is the malformed input that matters. |
| Boundaries & limits | N-A | No new limits introduced; the authoring step's bounded retry behavior is existing, unchanged. |
| Errors & failures | Specify | UFR-1 (stale path record), UFR-3 (missing dependency), UFR-4 (mid-flight manual run) — the failures this change can cause. |
| Access & permissions | Specify | FR-10 — the owner-authority guard rides the host layer being removed and must survive it unchanged. |
| Duplicates & double-actions | N-A | No new owner actions; showrunner re-entry idempotence is existing behavior, unchanged. |
| Conflicting / simultaneous use | N-A | Single owner, single run per work-item (existing lease behavior, unchanged). |
| Misuse & abuse | N-A | No money or private data; accidental-reintroduction risk is covered by FR-7's guard. |
| Reach (i18n / a11y) | N-A | Developer tool with English docs and no UI surface. |
