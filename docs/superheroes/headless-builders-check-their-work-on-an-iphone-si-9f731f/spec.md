---
superheroes: doc
schemaVersion: 1
docType: spec
workItem: headless-builders-check-their-work-on-an-iphone-si-9f731f
issue: null
size: medium
status: approved
approved: "2026-10-08"
gates: {review: passed}
producedBy: "the-architect@0.40.0"
created: "2026-10-07"
updated: "2026-10-08"
---
# Headless builders check their work on an iPhone Simulator

## Purpose

Today only the advisor can look at a project on an iPhone. It does so by hand through the desktop
app's simulator tool, which headless builders cannot reach. So iPhone-only defects slip through
every build and are caught, if at all, at the advisor's vet. Examples: Safari zooming the page on a
text field under 16 px, and keyboard placement written for Chrome hiding the focused field. This
work lets a headless builder check its own work on a simulated iPhone, in Mobile Safari or in the
same web app installed to the Home Screen; whether to check in one, the other or both is the issue's
or the lane's call, not the plugin's.
The builder taps and types with the real keyboard rising, takes screenshots, and reads page
measurements. It starts with the smallest machinery that does this, and adds more only when real
use proves it is needed (owner ruling, 2026-10-07).

## Who it's for

- **A builder lane doing iPhone-sensitive UI work.** It needs to see its change behave on an
  iPhone before handing the PR back, instead of leaving the iPhone check to the advisor.
- **The advisor.** It vets that lane's PR from the pilot's iPhone evidence rather than repeating
  the check by hand. Today it is the bottleneck on any project's iPhone work.
- **The owner.** They install one tool once, and read a PR that says plainly whether the iPhone
  check ran.

## Functional requirements

**FR-1.** The iPhone check shall be off for a lane unless that lane's launch asks for it.
  - *Acceptance (rule):* a lane launched without asking for an iPhone check gets no phone.

**FR-2.** Where an issue's done-definition names an iPhone check, the advisor shall launch that
issue's lane with the iPhone check turned on.
  - *Acceptance (Given-When-Then):* Given an issue whose done-definition names an iPhone check, when
    the advisor launches its lane, then the launch record shows the iPhone check turned on.

**FR-3.** When a launch with the iPhone check starts, the launcher shall create a new simulated
iPhone for that lane alone.
  - *Acceptance (Given-When-Then):* Given a launch with the iPhone check, when the builder starts,
    then a simulated iPhone exists that did not exist before the launch, and no other lane was
    given it.

**FR-4.** When a launch with the iPhone check starts, the launcher shall give the builder the ID of
that lane's own phone.
  - *Acceptance (rule):* the builder's launch hands it exactly one phone ID: the one FR-3 created.

**FR-5.** When a launch with the iPhone check creates a phone, that launch's record shall name the
phone's ID.
  - *Acceptance (rule):* the advisor can read each phone a lane's launches created from its launch
    records without asking the builder, including a launch that failed after creating its phone, and
    the record of the launch the builder actually runs under names the ID FR-4 handed it.

**FR-6.** While a lane holds a phone, its pilot shall be able to drive that phone without any
approval from the owner during the run.
  - *Acceptance (rule):* a lane with the iPhone check runs its whole iPhone check with no permission
    prompt reaching the owner, and no lane's sandbox is widened for it.

**FR-7.** The choice of where a lane's iPhone check runs (in the browser, in the installed web app,
or both) shall rest with the lane's issue when the issue states one, and with the lane when it does
not.
  - *Acceptance (Given-When-Then):* Given an issue that says to check in the installed web app, when
    the lane runs its iPhone check, then the check includes the installed web app; a check run only in
    the browser does not meet the issue.
  - *Acceptance (Given-When-Then):* Given an issue that says nothing about where to check, when the
    lane runs its iPhone check, then the lane has made the choice and the results state it (FR-16).
  - *Acceptance (rule):* the plugin makes no choice of where to check for any lane.

**FR-8.** Where a lane's iPhone check includes the installed web app, the builder shall add the
project's app to its phone's Home Screen.
  - *Acceptance (Given-When-Then):* Given a lane whose iPhone check includes the installed web app,
    when the builder prepares its iPhone check, then the project's app appears on the phone's Home
    Screen.

**FR-9.** Where a lane's iPhone check includes the installed web app, every page reading from that
part shall report the app running as an installed web app, and that part shall carry at least one
reading.
  - *Acceptance (rule):* an installed-app part with no reading, or with a reading that reports the
    browser, does not count as an installed-app check.

**FR-10.** When the builder taps a text field on its phone, the phone shall raise its real on-screen
keyboard.
  - *Acceptance (Given-When-Then):* Given a page on the lane's phone, in Mobile Safari or in the
    installed web app, with a text field set in 14 px type, when the builder taps that field, then
    a screenshot shows the on-screen keyboard raised.

**FR-11.** When the builder types on its phone, the phone shall enter the typed text into the
focused field.
  - *Acceptance (Given-When-Then):* Given a focused text field on the lane's phone, when the
    builder types "hello", then a page reading (FR-13) returns "hello" as that field's value.

**FR-12.** While a lane holds a phone, its pilot shall be able to take a screenshot of that phone.
  - *Acceptance (rule):* a screenshot request from the lane's pilot yields an image of the phone's
    current screen.

**FR-13.** While a lane holds a phone, its builder shall be able to take a page reading through the
project's reporting script, and a reading shall give four things: the page's visible height, its
focused element, that element's value (withheld for a password field), and whether the app is
running in the browser or installed.
  - *Acceptance (Given-When-Then):* Given the reporting script in a page on the lane's phone and a
    reading taken before any tap, when the builder taps a 14 px field, then a new reading returns all
    four, with a visible height smaller than the earlier reading's and the tapped field named as
    focused.
  - *Acceptance (rule):* a reading taken while a password field is focused carries no part of that
    field's value.

**FR-14.** Every iPhone screenshot and reading in the pilot's results shall name the ID of the phone
it was actually captured from, as reported at the moment of capture, never copied from the ID the
builder was handed.
  - *Acceptance (rule):* each piece of iPhone evidence in the pilot's results carries the phone ID its
    capture reported; at vet, FR-20 applies.
  - *Acceptance (Given-When-Then):* Given a screenshot captured from a phone other than the lane's
    own, when the pilot records it, then the evidence names that other phone's ID, not the ID the
    builder was handed.

**FR-15.** Every iPhone screenshot and reading in the pilot's results shall name the iPhone model,
iOS version and page address it came from.
  - *Acceptance (rule):* no piece of iPhone evidence in the results lacks any of the three.

**FR-16.** The pilot's results shall label each piece of iPhone evidence as coming from the browser
or from the installed web app, and state where the check ran and whether the issue or the lane chose
it.
  - *Acceptance (rule):* the results state where the check ran and who chose it; no piece of iPhone
    evidence in the results lacks the browser-or-installed label, and where a
    reading accompanies the evidence, the label agrees with the reading's browser-or-installed value;
    at vet, FR-20 applies to a piece whose label and reading disagree.

**FR-17.** The pilot's results shall label each piece of iPhone evidence as Simulator evidence, and
state what a simulator cannot show: a real finger's touch (the timing and imprecision of a human
tap, and multi-finger gestures) and real-device speed.
  - *Acceptance (rule):* every piece of iPhone evidence carries the Simulator label, and every set of
    pilot's results that carries iPhone evidence carries a statement of gaps naming both a real
    finger's touch and real-device speed.

**FR-18.** When the advisor reaps a finished lane, the advisor shall delete every phone the lane's
launch records name.
  - *Acceptance (Given-When-Then):* Given a finished lane, including one that was relaunched or
    whose launch failed after its phone was created, when the advisor reaps it, then none of the
    phones its launch records name exists, other than any UFR-7 lists as left running (a phone already
    gone counts as deleted), and every other phone that was running before the reap is still running.

**FR-19.** When a superheroes step for an iPhone lane runs (launching it, including a launch that
fails; running its pilot; reaping it), the step shall leave Xcode's Device Hub running.
  - *Acceptance (rule):* if Device Hub was running before such a step, it is running after it.

**FR-20.** When the advisor vets a PR carrying iPhone evidence, the advisor shall rule invalid each
piece whose phone ID is missing or differs from the record of the launch the builder runs under
(FR-5), or whose
browser-or-installed label is missing or disagrees with its reading (FR-16).
  - *Acceptance (Given-When-Then):* Given a PR whose results carry one piece with no phone ID, one
    piece naming another phone, one piece labelled "installed" whose reading says browser, and one
    piece with no browser-or-installed label, when the advisor vets it, then the vet ruling lists all
    four as invalid, each with its reason.

**FR-21.** The superheroes plugin shall give projects guidance for the reporting script stating that
it must be absent from, or do nothing in, the app the project's real users get, and that its
readings withhold a password field's value.
  - *Acceptance (rule):* the guidance projects read when adding the reporting script contains both
    rules.

## When things go wrong (significant unhappy paths)

**UFR-1.** If any part of a lane's iPhone check does not complete, then the lane shall still finish
its PR.
  - *Acceptance (Given-When-Then):* Given a lane whose iPhone check cannot complete, when the lane
    finishes, then its PR is handed back rather than held.

**UFR-2.** If any part of a lane's iPhone check does not complete, including a part the lane's
check includes that was never attempted, then the pilot's results shall open with one line "iPhone check did not
run — <part>: <reason>" for each part that did not complete, where <part> is exactly one of "browser check", "installed-app check" or "whole check". A cause that
stops everything (the driver tool, Device Hub, the phone not booting, the missing reporting script)
names the whole check, in a single line, and so does a boot or driver-tool start that never returns;
a cause inside one part, including a step there that never returns, names that part, and each part
that fails for its own cause gets its own line.
  - The reasons this covers include: the driver tool missing or failing to start; Device Hub
    unavailable; the phone not booting; the app lacking its reporting script; the phone showing no
    response to input (UFR-4); a driver, boot or screenshot step that never returns (how long to wait
    is the build's choice); the Home Screen install failing; and an included part never attempted. A
    lane with no phone at all opens with UFR-5's line instead.
  - *Acceptance (rule):* for each listed reason, the results open with that line naming the part and
    the reason; when the browser check and the installed-app check each fail for their own cause, the
    results open with two lines, one per part; a cause that stops everything gives one whole-check
    line.
  - *Acceptance (Given-When-Then):* Given a lane whose iPhone check includes both the browser and the
    installed web app, when the pilot posts browser evidence only, then the results open with "iPhone check did not
    run — installed-app check: " followed by its reason.
  - *Acceptance (Given-When-Then):* Given a screenshot step that never returns, when the lane
    finishes, then its PR is handed back and the results open with a "did not run" line for that
    step's part.

**UFR-3.** If any part of a lane's iPhone check stops partway, then the pilot's results shall keep
the evidence that part gathered before it stopped.
  - *Acceptance (Given-When-Then):* Given an installed-app check that took two screenshots and then
    got no response to typing, when the results are posted, then those two screenshots are in them
    beside the "did not run" line for the installed-app check.

**UFR-4.** If the phone shows no response to an input the builder sent, then the builder shall count
that step as not completed, never as passed. No response means: for a tap on a text field, that a
reading shows no field focused, or that the next screenshot shows no on-screen keyboard; for typing,
that the focused field's value is unchanged (for a password field, whose value readings withhold,
that the next screenshot shows no change in the field); for any other input, that the next screenshot or
reading shows none of the change the pilot's test plan says that step should make (a step whose plan
names no expected change counts as not completed). This rule covers the steps of the test plan; the
builder's preparation taps (installing the app, dismissing a one-time tip) are judged by whether the
preparation succeeded (FR-8, UFR-2).
  - *Acceptance (Given-When-Then):* Given a tap on a text field that the driver tool reports as
    done while a reading shows no field focused, when the builder records the step, then the step is
    reported through a UFR-2 line for its part, not as a pass.
  - *Acceptance (Given-When-Then):* Given a tap on a text field after which the next screenshot shows
    no on-screen keyboard, when the builder records the step, then the step is reported through a
    UFR-2 line for its part, not as a pass.
  - *Acceptance (Given-When-Then):* Given typing the driver tool reports as done while a reading
    shows the focused field's value unchanged, when the builder records the step, then the step is
    reported through a UFR-2 line for its part, not as a pass.
  - *Acceptance (Given-When-Then):* Given typing into a password field after which the next
    screenshot shows no change in the field, when the builder records the step, then the step is
    reported through a UFR-2 line for its part, not as a pass.
  - *Acceptance (Given-When-Then):* Given a tap on a button whose test-plan step expects a new screen,
    after which the next screenshot shows the same screen, when the builder records the step, then the
    step is reported through a UFR-2 line for its part, not as a pass.
  - *Acceptance (Given-When-Then):* Given a test-plan step that names no expected change, when the
    builder records it, then the step is reported through a UFR-2 line for its part, not as a pass.

**UFR-5.** If a lane's issue names an iPhone check, or its launch asked for one, and the lane holds no
phone (whether it was launched without the check or its phone was never created), then the pilot's
results shall open with "iPhone check did not run — whole check: no phone for this lane".
  - *Acceptance (Given-When-Then):* Given an issue naming an iPhone check launched without one, when
    the lane finishes, then its results open with that line.
  - *Acceptance (Given-When-Then):* Given a lane launched with the iPhone check whose phone was never
    created, when the lane finishes, then its results open with that line and with no UFR-2 line.

**UFR-6.** If the advisor vets a PR whose issue names an iPhone check and whose results do not show
a complete iPhone check, then the advisor shall check the change on a simulated iPhone by hand
before ruling on it. Not complete means any of: a "did not run" line, no pilot's results, no iPhone
evidence in the results, no evidence for a part the lane's check includes, any piece of iPhone evidence ruled
invalid (FR-20), any piece of iPhone evidence missing its model, its iOS version or its page
address (FR-15), its browser-or-installed label (FR-16), or its Simulator label (FR-17), results
missing the statement of gaps (FR-17), results missing the statement of where the check ran and who
chose it (FR-16), or an installed-app part with no reading that reports the app
installed (FR-9).
  - *Acceptance (rule):* for each listed condition, a vet ruling on such a PR records the advisor's
    own iPhone check.
  - *Acceptance (Given-When-Then):* Given a PR whose iPhone evidence is otherwise complete but one
    piece lacks the Simulator label, when the advisor vets it, then the vet records the advisor's
    own iPhone check before its ruling.

**UFR-7.** If the advisor cannot delete a phone while reaping a lane, then the advisor shall record
that phone's ID as left running in the reap record.
  - *Acceptance (rule):* every phone a reaped lane's launch records name is either gone or listed in
    the reap as left running.

**UFR-8.** If the launcher cannot create a phone for a lane with the iPhone check, then the lane
shall still start, without a phone.
  - *Acceptance (Given-When-Then):* Given a launch with the iPhone check whose phone creation fails,
    when the launch runs, then the builder starts and its results later open with UFR-5's line.

**UFR-9.** If Device Hub is not running when a lane with the iPhone check starts, then the launcher
shall open Device Hub without taking focus from what the owner is doing.
  - *Acceptance (Given-When-Then):* Given Device Hub not running, when a lane with the iPhone check
    starts, then Device Hub is running and the owner's front window has not changed.

**UFR-10.** If the launcher cannot open Device Hub for a lane with the iPhone check that holds a phone,
then the lane shall still start, and its results shall open with the whole-check "did not run" line
naming Device Hub unavailable (UFR-2). A lane that also holds no phone opens with UFR-5's line
instead.
  - *Acceptance (Given-When-Then):* Given Device Hub not running and unable to open, when a lane with
    the iPhone check starts, then the builder starts and its results open with "iPhone check did not
    run — whole check: Device Hub unavailable".

## Definition of done / success

The acceptance test passes in a real launched lane, not a hand-run probe, on a test page
that carries a reporting script. The build provides that page as a test fixture for this check; it is
not a reporting script superheroes ships to projects. A headless builder,
launched with the iPhone check, taps a 14 px field on its own phone in Mobile Safari, and the real
keyboard rises. A screenshot naming the phone shows the raised keyboard, and a reading returns the page's visible
height and the focused field. The same test then passes in the app installed to that phone's Home
Screen, with the lane choosing to check both. When the advisor reaps that lane, its phone is gone and any other running phone is
untouched.

## Assumptions & dependencies

- **Measured feasibility, 2026-10-07** (US Eastern; Xcode 27.0, iOS 27.0, macOS 26.6.2, Claude Code
  2.1.292, AXe 1.8.0). A headless builder, run inside the stricter implementer sandbox, ran the
  acceptance test above by hand on a
  temporary phone, and it passed. Each phone costs about 4.3 GB of memory and 0.5 GB of disk, and
  boots in about 20 seconds. With the Mac's normal load, about 3–4 phones fit at once.
- **Installed web apps, measured the same evening.** The same kind of builder ran the same test in a web
  app installed from a local development address. Safari's "Add to Home Screen" offered "Open as
  Web App", on by default. The installed app reported itself as installed, ran without Safari's
  toolbar (full height 812 rather than 714), zoomed on the 14 px field, and raised the real
  keyboard. Installing took five taps through Safari's menus. A fresh phone also showed a one-time
  keyboard tip ("slide to type") that covered part of the screen until dismissed.
- **The owner installs the driver tool, AXe, once** (MIT-licensed, from its author's GitHub
  release). On this Xcode it has a known bug: taps report success but do nothing unless the tool
  stays alive briefly (cameroncooke/AXe#71; a fix is open as #73). A documented workaround made it
  work; UFR-4 keeps a silent miss from reading as a pass.
- **Device Hub must be running** while any phone is driven. It ships with Xcode 27, which replaced
  the old Simulator app with it.
- **Builder sessions and their pilots run without a sandbox today**
  [cite: plugins/superheroes/lib/engine_adapter.py § def claude_builder_argv], and the pilot runs inside
  the builder session [cite: plugins/superheroes/skills/workhorse/SKILL.md § A pilot subagent executes].
  Among Claude sessions, only the nested implementer write channel is sandboxed (external review and
  build engines run under their own sandboxes)
  [cite: plugins/superheroes/lib/engine_adapter.py § def claude_write_sandbox_settings]. The feasibility
  run above used that stricter sandbox and needed two isolation-weakening exceptions to reach the
  Simulator; the pilot needs none, so this work widens no sandbox (FR-6). The same lack of a sandbox
  means a builder can already reach any phone on the Mac (Constraints).
- **Each project adds its own development-only reporting script** to its app; superheroes does
  not. Until a project adds it, its lanes' iPhone checks report "did not run" (UFR-2).
- **The launcher already provisions each lane's worktree, and reaping a finished lane's worktree
  is the advisor's manual duty**
  [cite: plugins/superheroes/skills/showrunner/SKILL.md § Reaping a finished lane's worktree is yours]
  — FR-18 rides on that existing step.
- **The pilot already posts a results comment**, where FR-14 to FR-17, UFR-2 and UFR-5 land
  [cite: plugins/superheroes/skills/test-pilot-execute/SKILL.md § posts a results comment].

## Constraints

- **Simulator only.** The owner has no physical iPhone, so the gaps FR-17 states are never covered
  by anything else.
- **Start small** (owner ruling, 2026-10-07). The builder is guarded against using the wrong phone
  only by being told its own phone's ID (FR-4) and by every piece of evidence naming the phone it
  was captured from (FR-14). Further guard machinery waits for evidence that it is needed.
- **Accepted exposure.** Because builder sessions run without a sandbox, a builder's own commands can
  shut down, wipe or drive any phone on the Mac (another lane's, the advisor's, the owner's own, or
  one used for another project), and can close Device Hub, which shuts down every phone (FR-19 binds
  only superheroes' own steps). FR-14 catches evidence whose
  capture reports a different phone, but nothing detects a neighbour's phone being disturbed. The
  owner accepted this with the start-small ruling.
- **Phones from earlier launches wait for the reap.** When a lane is relaunched, the earlier
  launch's phone keeps running, and holding memory, until the advisor reaps the lane (FR-18). This
  is part of the forgotten-phone risk the owner accepted with the manual reap. So is a phone created
  by a launch that dies before writing its record: no record names it, so the reap cannot find it and
  only a person spotting it removes it.
- **The reporting script does nothing outside development.** Each project owns keeping its script
  out of, or inert in, the app its real users get; superheroes' part is the guidance FR-21 asks for.

## Out of scope

- Native iPhone apps; web apps only (in Mobile Safari, or installed to the Home Screen) until a
  project needs native.
- Reading pages a project does not control (an inspector bridge from outside the page).
- Guard machinery against a builder touching another lane's phone: refusing shortcut commands, or
  a helper outside the sandbox that drives only the lane's own phone.
- Automatic phone deletion when a lane ends (FR-18 is the advisor's manual step).
- A hard limit on how many phones run at once; the advisor judges it per launch.
- Pausing a lane when its iPhone check cannot complete (UFR-1 finishes the PR instead).
- iPhone access for the advisor or detective seats through this machinery; the advisor keeps the
  desktop app's simulator tool.

## Glossary

- **Phone:** a simulated iPhone running on the owner's Mac.
- **Builder:** the lane's builder session, including the pilot it runs; requirements naming the
  builder or the pilot mean that same session.
- **Issue names an iPhone check:** the issue's done-definition names one.
- **Driver tool:** the tool a builder uses to tap, type and press buttons on its phone (AXe today).
- **Lane:** one issue's build. A lane may be launched more than once (a relaunch), and each launch
  starts a builder session.
- **Pilot:** the builder's step that exercises the change in a running app and posts the pilot's
  results on the PR.
- **iPhone check:** the pilot driving the lane's own phone to verify the change in the browser
  (Mobile Safari) or in the project's web app installed to the phone's Home Screen.
- **Installed web app:** a project's web app added to the phone's Home Screen through Safari,
  opening on its own without Safari's toolbar.
- **Device Hub:** Xcode 27's app that hosts the simulated phones; closing it shuts down every phone.
- **Reporting script:** a small development-only script a project adds to its app so a builder can
  take page readings on the phone.
- **Launch record:** the launcher's record of a lane's launch, which the advisor reads.
- **iPhone lane:** a lane launched with the iPhone check.
- **Page reading:** one set of the four values FR-13 lists, taken through the reporting script.
- **Done-definition:** the "done" section of an issue, which says what the lane must deliver.
- **Vet:** the advisor's review of a lane's PR before it goes to the owner.
- **Part:** the browser check or the installed-app check within a lane's iPhone check; "whole check"
  means both, or the check as a whole.
- **Test plan:** the pilot's list of steps for a lane's check (from test-pilot planning), each naming
  the change it expects.
- **Reap:** the advisor's cleanup of a finished lane.
- **Reap record:** the advisor's written entry for a reaped lane, kept where the advisor records each
  lane's outcome.

## Amendments

_No amendments since the last full approval._

## Coverage

| Area | Disposition | Show-it? | Where / why |
| --- | --- | --- | --- |
| Empty & first-run | Specify | Yes | UFR-2: a project without its reporting script, or an owner without the driver tool, gets "did not run" with that reason |
| Invalid & malformed input | N-A | — | No user input; the builder's commands are its own work |
| Boundaries & limits | Specify | No | No hard phone limit (Out of scope; the advisor judges count per launch); UFR-8 and UFR-5 cover a phone that cannot be created; how long to wait on a stuck step is the build's choice (UFR-2) |
| Errors & failures | Specify | Yes | UFR-1 to UFR-10 |
| Access & permissions | Specify | No | FR-1, FR-4 (own ID only), FR-6 (no sandbox widened, no mid-run approvals); no enforcement, per the start-small ruling; exposure stated under Constraints |
| Duplicates & double-actions | Specify | No | FR-18: reaping deletes every phone the lane's launch records name, including relaunched and failed launches |
| Conflicting / simultaneous use | Specify | No | FR-14 names the phone each piece came from and FR-20 rules a different phone invalid at vet; FR-19 keeps superheroes' own steps from shutting down others' phones; a builder disturbing a neighbour's phone is accepted and undetected (Constraints) |
| Misuse & abuse | N-A | — | Hostile code is outside the threat model (PHILOSOPHY) |
| Reach (i18n / a11y) | N-A | — | Machinery for builders; no owner-facing interface |
| Wording & tone | Specify | Yes | UFR-2 and UFR-5's opening lines; FR-17's Simulator label and gap statement |
| Workflow shape | Specify | No | FR-2 → FR-3/FR-4/FR-5 → FR-7 (where to check) → (FR-8 install, when included) → builder checks → vet (FR-20, UFR-6) → FR-18 at reap |
| Placement & prominence | Specify | Yes | UFR-2, UFR-5: "did not run" opens the pilot's results |
| Limits & defaults | Specify | No | FR-1: off unless the launch asks |
| Tier & access boundaries | N-A | — | No tiers |
| Visibility & disclosure | Specify | Yes | FR-14 to FR-17 and FR-20: every iPhone result names its phone, model, iOS version, page address, browser-or-installed, and its Simulator gaps; the advisor rules mismatches invalid |
