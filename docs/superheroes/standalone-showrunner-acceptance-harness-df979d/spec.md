---
superheroes: doc
schemaVersion: 1
docType: spec
workItem: standalone-showrunner-acceptance-harness-df979d
issue: null
size: medium
status: approved
gates: {review: passed}
producedBy: "the-architect@0.3.0"
created: "2026-07-01"
updated: "2026-07-02"
---
# Standalone showrunner acceptance harness

## Purpose

The showrunner is the band's autonomous pipeline — and every deep bug it has ever had was found by a live end-to-end run, not by unit tests or reviews. Today those live runs are hand-rolled, one-shot eval sessions with manual cleanup, and cleanup mistakes have left stray PRs and stores behind. This work gives the owner a durable, repeatable, on-demand acceptance run: launch the showrunner on a small throwaway work-item in the real repo, let it run its whole pipeline to a ready-for-review PR, judge the result against hard facts, clean up everything it created, and report pass or fail. It exists so that before and after changes to the pipeline itself, "does the showrunner still reach a green ship?" is one command, not an afternoon.

## Who it's for

The **repo owner** — the one person who runs this project. They want a trustworthy yes/no on the showrunner's health, on demand, without babysitting the run and without cleanup homework afterward.

## Functional requirements

**FR-1.** When the owner invokes the acceptance harness, the harness shall start one full showrunner run on the canned fixture work-item, stamped with a run identifier unique to that launch.
  - *Acceptance (Given-When-Then):* Given no acceptance run is in flight, when the owner invokes the harness, then a showrunner run starts on a fixture work-item carrying a fresh run identifier and the owner is told the run has started.
  - *Acceptance (rule):* Two consecutive launches produce work-item names, branches, and pull requests that never collide with each other.
  - *Acceptance (rule):* Every artifact a run creates carries its run identifier in a form recognizable as the acceptance harness's, so recovery (UFR-8) can tell it apart from the owner's real work by inspection alone.

**FR-2.** The canned fixture work-item shall define exactly one small, unambiguous task — a change to a single file with no decision left to judgment — that still traverses every pipeline phase from planning through ship.
  - *Acceptance (rule):* The fixture contains exactly one task touching exactly one file, and its wording leaves no open choice for the run to research or decide.
  - *Acceptance (Given-When-Then):* Given the fixture work-item, when a passing acceptance run completes, then the run's recorded list of traversed phases equals the full pipeline phase list.

**FR-3.** When the launched run terminates, the harness shall compute the verdict solely from machine-checkable facts, and shall report **pass** only when all of the following are true: the run's terminal outcome is "ready"; a pull request for the run exists and is in ready-for-review state; that pull request's checks are green; every expected phase was traversed; and the run readout exists and contains the pull request link.
  - *Acceptance (Given-When-Then):* Given a terminated run meeting every listed fact, when the harness computes the verdict, then the verdict is pass.
  - *Acceptance (Given-When-Then):* Given a terminated run missing any one listed fact, when the harness computes the verdict, then the verdict is fail and the verdict report names which fact was false.
  - *Acceptance (rule):* For a retried invocation, the verdict is computed from the final attempt's terminated run.

**FR-4.** When computing the verdict, the harness shall compare the run readout's claimed facts against reality, and shall report fail if any claim differs — including the claimed check status versus the pull request's actual check status, and the claimed pull request versus the pull request that actually exists.
  - *Acceptance (Given-When-Then):* Given a terminated run whose run readout claims green checks, when the pull request's actual checks are not green, then the verdict is fail with a reason stating the run readout was inconsistent with reality.
  - *Acceptance (Given-When-Then):* Given a terminated run whose run readout names a pull request, when that pull request does not match the pull request the run actually created, then the verdict is fail with a reason stating the run readout was inconsistent with reality.

**FR-5.** When an invocation ends with any verdict, the harness shall write exactly one durable machine-readable result record — covering every attempt within that invocation — containing at least: the verdict, the reason, the pull request link (if one was created), the phases traversed, the spend and elapsed time, and the launch and termination timestamps.
  - *Acceptance (rule):* The result record exists and is readable after every invocation the harness survives to complete — including invocations where cleanup failed.
  - *Acceptance (rule):* A result record missing any of the listed elements fails acceptance.
  - *Acceptance (rule):* For an invocation ended by the harness dying outright (so no record could be written), the next invocation's recovery (UFR-8) writes a result record for the orphaned invocation, marking it failed, when it reclaims the leftovers — no invocation is ever left without a record, and never given a second one: a reclaim writes a record only when the orphaned invocation has none.

**FR-6.** When an invocation ends, the harness shall present the owner exactly one plain-language verdict report stating the verdict, the reason, where the result record lives, and what was cleaned up or left behind.
  - *Acceptance (Given-When-Then):* Given a completed acceptance invocation, when the owner reads the verdict report, then they can state the verdict and the reason without opening any other file.
  - *Acceptance (rule):* A retried invocation produces one verdict report — never one per attempt.
  - *Acceptance (rule):* Every verdict report contains all four elements — the verdict, the reason, where the result record lives, and what was cleaned up or left behind; a report missing any of them fails acceptance.

**FR-7.** When a run reaches any exit — pass, fail, killed, or harness error — the harness shall remove every artifact the run created: the pull request is closed, the branch is deleted, and the run's working copy and run-state records are removed. The result record (FR-5) and the verdict report are the only things an invocation leaves behind. Cleanup — including UFR-8's recovery — removes only artifacts the harness itself created for an acceptance run; it never closes a pull request, deletes a branch, or removes a record it did not create.
  - *Acceptance (Given-When-Then):* Given a run that terminated (any verdict), when cleanup completes, then the repo has no open fixture pull request, no fixture branch, and no leftover working copy or run-state records from that run.
  - *Acceptance (rule):* Running the cleanup a second time on an already-clean state changes nothing and reports success.
  - *Acceptance (Given-When-Then):* Given the harness hits an internal error of its own mid-invocation, when the invocation ends, then cleanup still runs, exactly one result record exists with a fail verdict naming the harness error, and the verdict report presents it — a harness error never produces a pass.
  - *Acceptance (rule):* Given fixture leftovers alongside the owner's real branches and pull requests, when cleanup or recovery runs, then only the fixture artifacts are removed — every branch, pull request, and record the harness did not create is untouched.

**FR-8.** While a run is in flight, the harness shall track the invocation's cumulative elapsed time and spend against ceilings the owner can configure, enforced from outside the run itself; when the owner has configured nothing, built-in default ceilings apply.
  - *Acceptance (rule):* The ceilings are in force on every run without the owner setting anything; when the owner does set them, the configured values are the ones enforced.
  - *Acceptance (rule):* The ceilings bound the whole invocation: a retry (FR-9) spends the invocation's remaining budget — it never resets the ceilings or receives a fresh budget.

**FR-9.** If a run fails for a classifiably environmental reason — a failure of the surrounding infrastructure, not of the pipeline's own behavior — then the harness shall perform at most one automatic retry and shall record in the result that a retry happened; failures of the pipeline's own behavior shall never be retried automatically. A retry cleans up the failed attempt's artifacts first, launches with a fresh run identifier, and the invocation still produces exactly one result record, covering both attempts. If that pre-retry cleanup itself fails, then no retry launches — the invocation ends as a cleanup failure (UFR-3), with the original failure and the abandoned retry noted in the result record.
  - *Acceptance (Given-When-Then):* Given a run that failed because a hosted check runner errored before running, when the harness classifies the failure as environmental, then exactly one retry launches and the final result record notes it.
  - *Acceptance (Given-When-Then):* Given a run that parked because a review found blocking findings, when the harness classifies the failure, then no retry launches.
  - *Acceptance (rule):* After a retried invocation, exactly one result record exists, it names both attempts, and no artifacts from the first attempt remain.
  - *Acceptance (rule):* A failure that cannot be confidently classified is treated as a failure of the pipeline's own behavior — no retry launches.
  - *Acceptance (Given-When-Then):* Given an environmental failure eligible for retry, when the cleanup of the failed attempt's artifacts fails, then no retry launches and the invocation ends on the cleanup-failure path (UFR-3).
  - *Acceptance (rule):* If the retried attempt itself fails — for any reason, environmental or not — no further retry launches.

## When things go wrong (significant unhappy paths)

**UFR-1.** If the launched run terminates parked at any phase, then the harness shall report a fail verdict carrying the park reason, and cleanup shall still run.
  - *Acceptance:* Given a run that parked during its build phase, when the harness reports, then the verdict is fail, the verdict report carries the park reason, and no fixture artifacts remain.

**UFR-2.** If a run exceeds its elapsed-time or spend ceiling, then the harness shall stop the run, report a fail verdict stating which ceiling tripped, and cleanup shall still run — beginning only once the run is confirmed stopped and can no longer act.
  - *Acceptance:* Given an in-flight run that crosses its elapsed-time ceiling, when the harness acts, then the run is stopped without waiting for it to finish, the verdict is fail with "time ceiling exceeded", and no fixture artifacts remain.
  - *Acceptance:* Given an in-flight run that crosses its spend ceiling, when the harness acts, then the run is stopped without waiting for it to finish, the verdict is fail with "spend ceiling exceeded", and no fixture artifacts remain.
  - *Acceptance (rule):* Cleanup of a ceiling-tripped run begins only after the run is confirmed stopped; anything the run managed to write before stopping is swept by that same cleanup.

**UFR-3.** If cleanup itself fails, then the harness shall list exactly which artifacts were left behind and give the owner one re-runnable cleanup action that finishes the job.
  - *Acceptance:* Given a cleanup that could not delete the branch, when the harness reports, then the verdict report names the surviving branch, the result record is still written, and the owner can run the offered cleanup once to remove it.

**UFR-4.** If the owner invokes the harness while an acceptance run is already in flight, then the harness shall refuse, naming the in-flight run, and shall not start a second run.
  - *Acceptance:* Given an acceptance run in flight, when the owner invokes the harness again, then they see a refusal naming the running acceptance run and no new run, branch, or pull request appears.

**UFR-5.** If the harness is invoked from inside a showrunner run, then it shall refuse and state that acceptance runs cannot nest inside the pipeline they test.
  - *Acceptance:* Given execution inside a showrunner run, when the harness is invoked, then it refuses before launching anything.

**UFR-6.** If anything in an acceptance run would change the project's real state — merging the fixture pull request, cutting a release, or touching a real work-item's records — then that action shall be blocked by structure rather than by instruction, and the project's real state shall be unchanged after every run.
  - *Acceptance:* Given any completed acceptance run (any verdict), when the owner inspects the project, then the default branch contains no commit from the run and no real work-item's records changed.

**UFR-7.** If a prerequisite for launching is missing or out of step with the pipeline — the project's calibration, the fixture definition (absent, or no longer consistent with the pipeline's current phases or its single target file), or the ability to reach the code host — then the harness shall refuse before launching anything and name what is missing or drifted.
  - *Acceptance:* Given a missing fixture definition, when the owner invokes the harness, then they see a refusal naming the fixture as the missing piece and nothing was launched or created.
  - *Acceptance:* Given a fixture whose expected phase list no longer matches the pipeline's, when the owner invokes the harness, then they see a refusal naming the drift and no run launches — the drift is never reported as a pipeline failure.
  - *Acceptance:* Given a fixture whose single target file no longer exists in the project, when the owner invokes the harness, then they see a refusal naming the drift and no run launches.
  - *Acceptance:* Given a project whose calibration is missing, when the owner invokes the harness, then they see a refusal naming the calibration as the missing piece and nothing was launched or created.
  - *Acceptance:* Given a code host that cannot be reached before launch, when the owner invokes the harness, then they see a refusal naming the code host as unreachable and nothing was launched or created.

**UFR-8.** If the harness is invoked while recorded run state says an acceptance run is in flight but that run is verifiably no longer alive, then the harness shall report the dead run, clean up its leftovers, and proceed with the fresh launch. The same recovery applies when a dead attempt left artifacts behind without any recorded run state — every artifact an acceptance run creates shall be discoverable and removable by a later invocation. Reclaim happens only on confirmed death: if the prior run's liveness cannot be confirmed either way, the harness shall refuse the new launch (as in UFR-4), saying why, rather than reclaim.
  - *Acceptance:* Given a prior acceptance run that was killed mid-run leaving in-flight state behind, when the owner invokes the harness, then the verdict report of the new invocation names the dead run, the dead run's artifacts are cleaned up, and the new run launches — the owner is never permanently locked out by a crashed run.
  - *Acceptance:* Given a prior attempt that died after creating artifacts but before recording any run state, when the owner next invokes the harness, then those leftover artifacts are detected, reported, and cleaned up before the new run launches.
  - *Acceptance:* Given recorded in-flight state whose run's liveness cannot be confirmed either way, when the owner invokes the harness, then the invocation is refused naming the unconfirmable run — nothing is reclaimed and no new run launches.

**UFR-9.** If any fact the verdict depends on cannot be read once the run has terminated, then the harness shall report a fail verdict naming the unreadable fact; an unreadable fact shall never contribute to a pass.
  - *Acceptance:* Given a terminated run, when the code host cannot be reached to read the pull request's check status, then the verdict is fail with a reason naming the check status as unreadable — not pass, and not a silent retry.
  - *Acceptance (rule):* The same fail-closed rule governs retry classification (FR-9): a fact that cannot be read never justifies a retry.

## Non-functional requirements

- **Cost (harness overhead):** the harness's own work — launching, fact-checking, cleanup, reporting — adds no model-driven spend beyond the pipeline run under test; every assertion is a plain lookup. *Fit criterion:* the harness itself performs no model-driven work; an acceptance run's total spend is the showrunner run's spend.
- **Cost (fixture):** the fixture is the cheapest work-item that still exercises the whole pipeline. *Fit criterion:* the fixture never causes the run to research, iterate on ambiguity, or produce more than one task's worth of change.
- **Verdict determinism:** the same terminated run always yields the same verdict. *Fit criterion:* re-computing the verdict on an unchanged terminal state produces an identical verdict and reason, every time.
- **Unattended operation:** the owner can invoke the harness and walk away. *Fit criterion:* from launch to verdict report, the harness never waits on owner input.
- **Privacy:** the result record and verdict report stay on the owner's machine; the harness never publishes captured failure text to the code host or anywhere else. *Fit criterion:* after any run, no harness-written text appears outside the owner's local records.

## Definition of done / success

- The owner can invoke the harness on demand and receive a verdict report with no further input.
- One live acceptance run has been performed end-to-end and demonstrated: a computed verdict, a written result record, and a cleanup that left no fixture pull request, branch, working copy, or run-state records behind.
- Every deterministic behavior — verdict facts, consistency checks, cleanup, refusals, ceilings, retry classification — is proven by tests that do not require a live run.
- The GitHub issue tracking this capability (#112) reflects the standalone shape.

## Assumptions & dependencies

- The showrunner's machine-readable run-outcome record (already shipped) remains the authoritative terminal summary of a run: status, pull request link, check status, phases traversed, and readout location.
- The showrunner itself is operational; this harness detects its regressions but does not repair them.
- The project's superheroes calibration exists in the repo where the harness runs.
- The code host is reachable for pull-request and check facts, and for cleanup.

## Constraints

- Acceptance runs happen in the real repo — no sandbox repo is created or maintained.
- An acceptance run never merges anything, and the harness is never part of any merge gate.
- The harness is invoked on demand by the owner only; no scheduled cadence in this work.

## Out of scope

- A modality seam through test-pilot (reconsidered only if a second agentic-workflow consumer appears).
- Scheduled or per-change automatic acceptance runs.
- Best-of-N / repeated-run confidence modes.
- A dedicated sandbox repo.
- Any LLM-judge scoring of readout prose.
- Validating agentic workflows other than the showrunner.

## Open questions

_None._

## Glossary

- **Acceptance run** — one harness-launched showrunner run on the fixture work-item, ending in a verdict and cleanup.
- **Fixture work-item** — the canned throwaway work-item the run builds; small, single-task, discarded after every run.
- **Verdict** — the harness's pass/fail judgment, computed only from machine-checkable facts.
- **Run readout** — the summary the showrunner run itself produces about its own outcome; the harness fact-checks it (FR-4) but does not write it.
- **Verdict report** — the plain-language report the harness presents to the owner (FR-6); distinct from the run readout.
- **Environmental failure** — a failure of the surrounding infrastructure rather than of the pipeline's own behavior. A failure is environmental only when it arose outside anything the pipeline produced and the same step could be re-attempted unchanged — e.g. a hosted check runner erroring before running, or the code host being briefly unreachable. A failure arising from the pipeline's own output — a parked run, a red check on its change, a blocking review finding — is behavioral and is never retried automatically.

## Coverage

| Area | Disposition | Where / why |
| --- | --- | --- |
| Empty & first-run | Specify | UFR-7 — missing calibration/fixture/host access refused before launch |
| Invalid & malformed input | Specify | UFR-7 — invocation takes no free-form input; bad, missing, or drifted prerequisites are refused pre-launch |
| Boundaries & limits | Specify | FR-8, UFR-2 — time/spend ceilings and behavior when tripped |
| Errors & failures | Specify | UFR-1 (parked run), UFR-3 (cleanup failure), UFR-9 (unreadable verdict fact), FR-9 (environmental retry) |
| Access & permissions | Specify | UFR-6 — real project state protected by structure; owner-only tool |
| Duplicates & double-actions | Specify | UFR-4 (concurrent second run refused), UFR-8 (dead run's stale in-flight state reclaimed) |
| Conflicting / simultaneous use | N-A | Single-owner project; the concurrency case is UFR-4 |
| Misuse & abuse | Specify | UFR-5 (no nesting), UFR-6 (no real-state mutation) |
| Reach (i18n / a11y) | N-A | Internal single-owner tool; plain-text readouts only |
