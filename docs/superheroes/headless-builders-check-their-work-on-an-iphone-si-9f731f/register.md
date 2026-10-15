# Contract register — headless-builders-check-their-work-on-an-iphone-si-9f731f

Cross-child technical decisions for the epic that lands the spec the owner approved on 2026-10-08,
`headless-builders-check-their-work-on-an-iphone-si-9f731f` (stored spec, beside this file). The
entries are numbered, and each is a plain binding sentence with its consuming children named. Every
entry is either decided now or names the child that decides the detail (**decide-by**). The advisor
owns edits; a builder never amends the register it is graded against. Children quote each entry's
first paragraph **verbatim**. The `*Source:*`, `*Status:*` and `*Consumers:*` lines are trailer and
are not quoted.

No entry adds product opinion. Where a decision comes from the spec, the `*Source:*` line names the
spec text. Where the spec is silent, the entry marks the gap **decide-by**, and the named child
records its choice for the owner's veto. If the choice would change what the owner sees, is asked or
keeps, the child raises it as an owner call instead.

Children: C1 the launcher's phone (the seam) · C2 the pilot's iPhone check · C3 the advisor's
launch, vet and reap · C4 the reporting-script guidance.

---

**R1 — Asking for the iPhone check.** A launch asks for the iPhone check through one optional field of the launch premise the advisor passes to the launcher; when the field is absent the check is off and the launcher creates no phone. The launcher records whether the check was asked for on that launch's ledger record. The field's name and the ledger field's name are decide-by: C1.
*Source:* FR-1 ("off for a lane unless that lane's launch asks for it"); FR-2 ("the launch record shows the iPhone check turned on").
*Status:* decided; **decide-by: C1** for the two field names.
*Consumers:* C1, C3.

**R2 — The lane's own phone, and how the builder learns about it.** When a launch asks for the iPhone check, the launcher creates one new simulated iPhone for that launch before it spawns the builder, and, through the launch it composes, hands the builder either that phone's ID or the fact that the lane holds no phone because creation failed; R4's Device Hub notice travels on the same channel. The builder treats the handed ID as its only phone and never creates, boots another or picks one by name. The facts travel in the builder's environment, the way a pilot slot reference already does (`SUPERHEROES_SLOT_REF`), because the composed launch prompt carries only the workhorse command, the issue and the standing rulings; the workhorse charter tells the builder to read them. Which device type and iOS runtime the launcher creates, and the environment variable names and values, are decide-by: C1.
*Source:* FR-3; FR-4 ("exactly one phone ID: the one FR-3 created"); UFR-8 ("the lane shall still start, without a phone"); Constraints, "Start small" (the builder is guarded only by being told its own phone's ID).
*Status:* decided; **decide-by: C1** for the device type, the runtime and the channel.
*Consumers:* C1, C2.

**R3 — Every phone is on a launch record.** The launcher creates the phone just before it reserves the launch, outside the ledger lock, and writes the phone's ID onto that launch's reservation record; when the reservation is refused before it writes anything, the launcher deletes that phone instead. So every phone that outlives its launch's reservation step is named on the launch record, including a launch that fails afterwards, and the record of the launch the builder runs under names the ID handed to the builder. A launcher that dies between creating the phone and writing the reservation leaves a phone no record names; its name carries the launch's id so a person can find it, the gap the spec's Constraints already accept. The advisor finds every recorded phone a lane's launches created by reading that lane's launch records alone, and the ledger's fold exposes the phone to its readers. The record uses an existing record kind, never a new one, because an older build's fold refuses a record kind it does not know. The ledger field's name and which existing record kind carries it are decide-by: C1.
*Source:* FR-5 and its rule; FR-18 ("every phone the lane's launch records name"); Constraints, "Phones from earlier launches wait for the reap" (a launch that dies before writing its record is an accepted gap).
*Status:* decided; **decide-by: C1** for the field and record kind. **Amended 2026-10-09 by the advisor (vet 422 on PR #1688):** creation moved to just before the reservation, outside the ledger lock, because creating it inside the lock let a stalled simulator block unrelated launches (two review sessions confirmed it). A pre-write refusal deletes the phone. The crash window is the gap the spec's Constraints accept ("a phone created by a launch that dies before writing its record"), so this needs no spec change.
*Consumers:* C1, C3.

**R4 — Device Hub stays up.** No superheroes step for an iPhone lane — launching it (a failed launch included), running its pilot, or reaping it — quits Device Hub or runs a command that shuts every phone down. When an iPhone launch starts and Device Hub is not running, the launcher opens it in the background without changing the owner's front window; when it cannot open it, the launch still starts and the launcher tells the builder that Device Hub is unavailable, on the same channel R2 uses, so the pilot opens its results with the whole-check "did not run" line naming Device Hub unavailable — unless the lane also holds no phone, in which case the results open with UFR-5's no-phone line instead and with no other "did not run" line.
*Source:* FR-19; UFR-9; UFR-10 ("A lane that also holds no phone opens with UFR-5's line instead"); UFR-5; spec Glossary, Device Hub ("closing it shuts down every phone").
*Status:* decided.
*Consumers:* C1, C2, C3.

**R5 — iPhone evidence in the pilot's results.** In the pilot's results comment, each piece of iPhone evidence (a screenshot or a page reading) carries six labelled values: `phone` (the ID the capture itself reported), `model`, `iOS`, `page` (the page address), `where` (`browser` or `installed`) and `source` (always `Simulator`). The results also carry one line stating where the check ran and whether the issue or the lane chose it, and one line stating what a simulator cannot show: a real finger's touch and real-device speed. "Did not run" lines open the results in exactly the text UFR-2 and UFR-5 give, one per part, before any evidence. The advisor's vet reads these labels by name. The exact markdown layout of a piece of evidence is decide-by: C2, keeping the six label names.
*Source:* FR-14; FR-15; FR-16; FR-17; FR-20; UFR-2; UFR-5; UFR-6.
*Status:* decided; **decide-by: C2** for the markdown layout only.
*Consumers:* C2, C3.

**R6 — The reporting script's interface.** A project's development-only reporting script is how the pilot takes a page reading on the phone. Each reading carries the four values FR-13 names: the page's visible height, its focused element, that element's value (withheld entirely for a password field), and whether the app runs in the browser or installed. The script must not need any bridge from outside the page. How the pilot asks for a reading and how the reading reaches the pilot (for example drawn on the page for a screenshot, or sent to a local address the builder listens on) is decide-by: C2, which also ships the test page the success definition uses as a test fixture; C4's guidance documents the interface C2 chose.
*Source:* FR-13 and its rule; FR-21; Out of scope ("an inspector bridge from outside the page"); Definition of done ("The build provides that page as a test fixture… not a reporting script superheroes ships to projects").
*Status:* decided; **decide-by: C2** for how a reading is asked for and delivered.
*Consumers:* C2, C4.

**R7 — Where to check is never the plugin's choice.** No plugin surface chooses whether a lane's iPhone check runs in the browser, in the installed web app, or both: an issue may state it, and when it does not, the lane chooses and its results say so. The advisor's launch doctrine and vet doctrine follow the issue's statement and never add a default of their own.
*Source:* Purpose ("whether to check in one, the other or both is the issue's or the lane's call, not the plugin's"); FR-7 and its three bullets; FR-16.
*Status:* decided.
*Consumers:* C2, C3.
