# Coverage map — headless-builders-check-their-work-on-an-iphone-si-9f731f

Acceptance-level allocation of every criterion of the spec the owner approved on 2026-10-08,
`headless-builders-check-their-work-on-an-iphone-si-9f731f` (stored spec, beside this file), each
owned by exactly one child.

**What counts as one criterion.** Each acceptance bullet of an FR or UFR is one criterion, at the
spec's own bullet granularity. Where an FR or UFR carries acceptance bullets, its statement is owned
by the child that owns its bullets. UFR-2's "The reasons this covers include" bullet is a list inside
the requirement, graded by UFR-2's own acceptance bullets; it is not counted on its own.

**Declared splits.** Two criteria span the launcher and the pilot. Each is split at its conjunction,
the way the decomposition doctrine's worked example splits one:
- **UFR-8**, its one Given-When-Then: "then the builder starts" is **C1**'s, because the launcher
  must start the lane without a phone. "and its results later open with UFR-5's line" is **C2**'s,
  and it is the same outcome as UFR-5's second Given-When-Then, which C2 owns. Register entries R2
  and R4 bind both.
- **UFR-10**, its one Given-When-Then: "then the builder starts", with the launcher telling the
  builder that Device Hub is unavailable, is **C1**'s. "and its results open with 'iPhone check did
  not run — whole check: Device Hub unavailable'" is **C2**'s. Register entry R4 binds both.

No other criterion is split.

**FR-19 spans steps, not children.** Its one rule covers every superheroes step for an iPhone lane:
launching it, running its pilot and reaping it. **C1** owns the criterion, because the launcher is
where Device Hub is opened and where the rule first applies. Register entry R4 binds C2 and C3 to the
same rule for the pilot and the reap, and each of their DoDs carries it.

**The spec's "Definition of done / success".** This is the success definition: an acceptance test
in a real launched lane, then a reap. No child can run it, because only the advisor launches lanes
and reaps them. It is the epic's **closure validation run**, recorded as a rehearsal under
`skills/showrunner/reference/closure.md` § The validation run (a plugin surface, so one recorded live
run supplements the automated checks). It is listed in the last row and owned by the epic's closure,
not by a child.

Children: C1 the launcher's phone (the seam) · C2 the pilot's iPhone check · C3 the advisor's
launch, vet and reap · C4 the reporting-script guidance.

**Sequencing.** Wave 0: C1, the seam C2 and C3 build on. Wave 1: C2 and C3 in parallel, after C1. Both
read the evidence fields R5 fixes, so neither waits on the other. Wave 2: C4, after C2, because C2
decides the reporting script's interface (R6) and C4's guidance documents it.

| Ref | Item | Criterion (opening words) | Owner |
| --- | --- | --- | --- |
| FR-1 | rule | a lane launched without asking for an iPhone check gets no phone. | **C1** |
| FR-2 | GWT | Given an issue whose done-definition names an iPhone check, when the advisor launches its lane, then the launch record shows the iPhone check turned on. | **C3** |
| FR-3 | GWT | Given a launch with the iPhone check, when the builder starts, then a simulated iPhone exists that did not exist before the launch, and no other lane was given it. | **C1** |
| FR-4 | rule | the builder's launch hands it exactly one phone ID: the one FR-3 created. | **C1** |
| FR-5 | rule | the advisor can read each phone a lane's launches created from its launch records without asking the builder… | **C1** |
| FR-6 | rule | a lane with the iPhone check runs its whole iPhone check with no permission prompt reaching the owner, and no lane's sandbox is widened for it. | **C2** |
| FR-7 | GWT 1 | Given an issue that says to check in the installed web app… a check run only in the browser does not meet the issue. | **C2** |
| FR-7 | GWT 2 | Given an issue that says nothing about where to check… the lane has made the choice and the results state it (FR-16). | **C2** |
| FR-7 | rule | the plugin makes no choice of where to check for any lane. | **C2** |
| FR-8 | GWT | Given a lane whose iPhone check includes the installed web app… the project's app appears on the phone's Home Screen. | **C2** |
| FR-9 | rule | an installed-app part with no reading, or with a reading that reports the browser, does not count as an installed-app check. | **C2** |
| FR-10 | GWT | Given a page on the lane's phone… with a text field set in 14 px type, when the builder taps that field, then a screenshot shows the on-screen keyboard raised. | **C2** |
| FR-11 | GWT | Given a focused text field on the lane's phone, when the builder types "hello", then a page reading (FR-13) returns "hello"… | **C2** |
| FR-12 | rule | a screenshot request from the lane's pilot yields an image of the phone's current screen. | **C2** |
| FR-13 | GWT | Given the reporting script in a page on the lane's phone and a reading taken before any tap… a new reading returns all four… | **C2** |
| FR-13 | rule | a reading taken while a password field is focused carries no part of that field's value. | **C2** |
| FR-14 | rule | each piece of iPhone evidence in the pilot's results carries the phone ID its capture reported; at vet, FR-20 applies. | **C2** |
| FR-14 | GWT | Given a screenshot captured from a phone other than the lane's own… the evidence names that other phone's ID… | **C2** |
| FR-15 | rule | no piece of iPhone evidence in the results lacks any of the three. | **C2** |
| FR-16 | rule | the results state where the check ran and who chose it; no piece of iPhone evidence… lacks the browser-or-installed label… | **C2** |
| FR-17 | rule | every piece of iPhone evidence carries the Simulator label, and every set of pilot's results… carries a statement of gaps… | **C2** |
| FR-18 | GWT | Given a finished lane, including one that was relaunched or whose launch failed after its phone was created, when the advisor reaps it… | **C3** |
| FR-19 | rule | if Device Hub was running before such a step, it is running after it. | **C1** (R4 binds C2 and C3; see above) |
| FR-20 | GWT | Given a PR whose results carry one piece with no phone ID, one piece naming another phone… then the vet ruling lists all four as invalid… | **C3** |
| FR-21 | rule | the guidance projects read when adding the reporting script contains both rules. | **C4** |
| UFR-1 | GWT | Given a lane whose iPhone check cannot complete, when the lane finishes, then its PR is handed back rather than held. | **C2** |
| UFR-2 | rule | for each listed reason, the results open with that line naming the part and the reason… | **C2** |
| UFR-2 | GWT 1 | Given a lane whose iPhone check includes both the browser and the installed web app, when the pilot posts browser evidence only… | **C2** |
| UFR-2 | GWT 2 | Given a screenshot step that never returns, when the lane finishes, then its PR is handed back and the results open with a "did not run" line… | **C2** |
| UFR-3 | GWT | Given an installed-app check that took two screenshots and then got no response to typing… those two screenshots are in them… | **C2** |
| UFR-4 | GWT 1 | Given a tap on a text field that the driver tool reports as done while a reading shows no field focused… | **C2** |
| UFR-4 | GWT 2 | Given a tap on a text field after which the next screenshot shows no on-screen keyboard… | **C2** |
| UFR-4 | GWT 3 | Given typing the driver tool reports as done while a reading shows the focused field's value unchanged… | **C2** |
| UFR-4 | GWT 4 | Given typing into a password field after which the next screenshot shows no change in the field… | **C2** |
| UFR-4 | GWT 5 | Given a tap on a button whose test-plan step expects a new screen, after which the next screenshot shows the same screen… | **C2** |
| UFR-4 | GWT 6 | Given a test-plan step that names no expected change… | **C2** |
| UFR-5 | GWT 1 | Given an issue naming an iPhone check launched without one, when the lane finishes, then its results open with that line. | **C2** |
| UFR-5 | GWT 2 | Given a lane launched with the iPhone check whose phone was never created… results open with that line and with no UFR-2 line. | **C2** |
| UFR-6 | rule | for each listed condition, a vet ruling on such a PR records the advisor's own iPhone check. | **C3** |
| UFR-6 | GWT | Given a PR whose iPhone evidence is otherwise complete but one piece lacks the Simulator label… | **C3** |
| UFR-7 | rule | every phone a reaped lane's launch records name is either gone or listed in the reap as left running. | **C3** |
| UFR-8 | GWT, first clause | …when the launch runs, then the builder starts… | **C1** (declared split) |
| UFR-8 | GWT, second clause | …and its results later open with UFR-5's line. | **C2** (declared split) |
| UFR-9 | GWT | Given Device Hub not running, when a lane with the iPhone check starts, then Device Hub is running and the owner's front window has not changed. | **C1** |
| UFR-10 | GWT, first clause | …when a lane with the iPhone check starts, then the builder starts… | **C1** (declared split) |
| UFR-10 | GWT, second clause | …and its results open with "iPhone check did not run — whole check: Device Hub unavailable". | **C2** (declared split) |
| DoD | success definition | The acceptance test passes in a real launched lane… When the advisor reaps that lane, its phone is gone and any other running phone is untouched. | **Epic closure** (validation run; see above) |

Counts: 47 rows. C1 owns 8, C2 owns 31, C3 owns 6, C4 owns 1, and the epic's closure owns the
success definition. Each criterion is owned once.
