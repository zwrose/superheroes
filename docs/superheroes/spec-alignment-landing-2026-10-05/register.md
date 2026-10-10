# Contract register — spec-alignment-landing-2026-10-05

Cross-child technical decisions for the landing epic of the two specs the owner approved on
2026-10-04: `aligning-on-what-to-build-6da1ee` (Spec A, the alignment flow) and
`the-review-surface-d59417` (Spec B, the review surface). Numbered entries; each is a plain
binding sentence with its consuming children named. Every entry is either decided now or marks
the detail a named child decides (**decide-by**). The advisor owns edits; a builder never amends
the register it is graded against. Children quote each entry's first paragraph **verbatim**; the
`*Source:*`, `*Status:*` and `*Consumers:*` lines are trailer and are not quoted. A stacked
child's layer tokens (for example `C4-L1`) appear in parentheses after the child's token on a
`*Consumers:*` line: the feature issue quotes every entry its token is named on, and the binding
register check for a layer runs on the feature issue's body with the feature's token
(`skills/showrunner/reference/register-check.md` § Stack layer inputs); each layer body also quotes
the entries its layer token is named on, so the same check can prove those quotes too.

No entry adds product opinion: where a decision comes from a spec, the `*Source:*` line quotes or
names the spec text; where a spec is silent, the entry marks the gap **decide-by** and the named
child records its choice for the owner's veto, raising it as an owner call instead when the choice
would change what the owner sees, is asked, or keeps.

Children: C1 Canon (the seam) · C2 the owner-vs-craft line · C3 configuration items · C4 the
discovery flow · C5 the three checks and the review-spec retirement · C6 the advisor's vet and the
approval handoff · C7 the theme and the template shell · C8 cards, sheets, images and answers.

---

**R1 — Canon's home.** Each project's Canon is one plain file named `canon.md`, kept in the folder that holds the project's definition-doc work-item folders: the doc-policy location for a project that keeps definition-docs in its repo (`docs/superheroes/canon.md` in this repository), and `docs/canon.md` in the project store for a project that keeps them out of the repo. A session finds the file through the existing definition-doc resolver, `plugins/superheroes/lib/definition_doc.py`, extended with a Canon lookup rather than joined by a new script. The lookup's verb name, and where Canon lives for a project whose in-repo definition-docs are gitignored (the specs are silent on that case), are decide-by: C1.
*Source:* Spec A FR-14 ("one plain file, `canon.md`, where the project keeps its definition-docs"); FR-15, fourth bullet ("where a project keeps them out of the repo, Canon lives in its project store"); HANDOFF ruling 35 ("`canon.md` at the project's superheroes root").
*Status:* decided; **decide-by: C1** for the lookup's verb name and the gitignored case.
*Consumers:* C1, C3, C4 (C4-L1), C5 (C5-L1), C6.

**R2 — Canon's contract doc.** Canon's rules have one home, a new reference doc `plugins/superheroes/rubric/canon-contract.md`, which states what Canon holds and what stays out of it (go-words, walk records, the declined registry, the threat model), the entry fields, the write procedure and the read rule; every other surface that needs Canon points at that doc and restates none of it.
*Source:* Spec A FR-14 and its bullet ("go-words (merge, launch, release, tier) stay where the owner gives them, and walk records and the declined-items registry carry on as they are"); FR-19 ("Canon shall not absorb it"); CONVENTIONS §11 (one home per cross-boundary fact).
*Status:* decided.
*Consumers:* C1, C2, C3, C4 (C4-L1), C5 (C5-L1), C6.

**R3 — A Canon entry.** Every entry carries an id, the date, the ruling in plain words, whether it is standing (it applies to all later work) or for one piece (naming that piece's work item), the owner's exact words where there are any, and a pointer to where it was said (the session and the time), never transcript line numbers. The id is the date, the writing session's short id and a sequence number, so two branches cannot mint the same id. A ceded call is a standing entry that also names the kind of call ceded and gives one example. The entry's exact markdown shape and the short id's form are decide-by: C1.
*Source:* Spec A FR-16 and its two bullets ("no entry cites transcript line numbers"; "for example the date, the session's short id and a sequence number"); FR-9 ("a standing ruling with an example, called a ceded call"); FR-17.
*Status:* decided; **decide-by: C1** for the markdown shape and the short id's form.
*Consumers:* C1, C3, C4 (C4-L1), C5 (C5-L1), C6.

**R4 — Append only, and how a ruling is replaced.** No session edits or deletes a Canon entry. A take-back of a ceded call, or any later ruling that replaces an earlier one, is a new entry that names the earlier entry's id, and from then the earlier entry counts as superseded for every reader, including the issue contract's supersession check on a ruling anchor that cites it. When two branches both add entries, the merge keeps both; whether that is done with a union-merge attribute or a stated resolution rule is decide-by: C1.
*Source:* Spec A FR-10; FR-16, second bullet ("when two branches both add to Canon, the merge keeps both entries"); What this spec amends, the anchor-resolution item ("the contract's attribution, date and supersession checks still apply").
*Status:* decided; **decide-by: C1** for the merge mechanism.
*Consumers:* C1, C3, C4 (C4-L1), C6.

**R5 — Writing a ruling.** A session that receives a ruling that decides something (an answer to an owner call, a principle, a ceded call or its take-back) appends it to Canon by the procedure in Canon's contract doc and commits that change at once to the branch it is working on, before its next step; go-words (merge, launch, release, tier) are never written to Canon. Canon never gets a PR of its own: a spec's rulings ride the spec PR, and the advisor's ride the PRs it already opens, a ruling it receives outside any open PR being committed to the branch of the next PR it opens. Where definition-docs live out of the repo, the commit goes at once to the project store's own git repository. How the advisor holds a ruling until that next PR's branch exists is decide-by: C6.
*Source:* Spec A FR-15 and its four bullets ("Canon never gets a PR of its own; a spec's rulings ride the spec PR and the advisor's ride the PRs it already opens"); FR-14's bullet on go-words.
*Status:* decided; **decide-by: C6** for the advisor's holding step.
*Consumers:* C1, C3, C4 (C4-L1), C6.

**R6 — Reading Canon.** Discovery (before its first question), the source check (to trace tags) and the advisor's vet (to check a spec across every piece) each read Canon from the project's default branch plus their own branch, and a session sorting a call reads it the same way; a ruling not yet on the default branch binds only sessions on the branch that holds it. Where Canon lives in the project store, every session sharing that store on the machine reads the one copy.
*Source:* Spec A FR-20; FR-15, third and fourth bullets; FR-4.
*Status:* decided.
*Consumers:* C1, C2, C4 (C4-L1), C5 (C5-L1), C6.

**R7 — How every session learns the two homes.** The covenant, `plugins/superheroes/rubric/covenant.md`, which every superheroes session carries, gains two pointer lines and no restatement: one to Canon's contract doc (C1 lands it) and one to the owner-vs-craft line's home (C2 lands it); the three charters and the discovery skill point at the same two homes.
*Source:* Spec A FR-1 ("everywhere it makes or routes a decision"); FR-4 ("When any session meets a call"); FR-15 ("in any session").
*Status:* decided.
*Consumers:* C1, C2, C4 (C4-L1), C6.

**R8 — The line's one home.** The owner-vs-craft line (the ten owner categories, each with its description, a real example and a "not yours when" note; the sorting rule; the always-craft list; the rule for a craft choice that carries an owner consequence; and the rule that errors are not decisions) lives in one new rubric file, `plugins/superheroes/rubric/owner-vs-craft-line.md`. Every place that states a version of it today is rewritten to point there: showrunner duty 5's two tests and `skills/showrunner/reference/perceivability.md`; `skills/showrunner/reference/owner-decisions.md` § "Craft calls and owner calls"; the glossary's craft-call, owner-call and material-consequence entries; and the issue contract's craft-call section with its material-consequence default. No later child restates any part of the line.
*Source:* Spec A FR-1, second bullet (the list of current homes); FR-2; FR-3 to FR-7.
*Status:* decided.
*Consumers:* C2, C3, C4 (C4-L1), C5 (C5-L1), C6, C9.

**R9 — Pointing at the line and at a project's answers.** A surface that needs the line names it "the owner-vs-craft line" and links its home (with the section anchor when it cites one part); a surface that needs a project's own answers points at the project's Canon (its standing rulings and ceded calls), never at a configuration value, so no per-project setting moves the line.
*Source:* Spec A FR-8 and its bullet ("the plugin has no per-project setting that moves the line"); FR-2's bullet.
*Status:* decided.
*Consumers:* C2, C3, C4 (C4-L1), C6.

**R10 — Configuration items 14 and 13.** "Who it's for and what it's for" is a new configuration item, number 14, with no plugin default, listed in configure's view beside item 10 (threat model); every existing item keeps its number. Item 13 (material consequence line) keeps its number and slug; once a project adopts the release, it holds no value of its own and shows a pointer to the project's Canon standing rulings, and a project that has not adopted keeps today's behaviour. Item 14's slug and home section, and what configure does when someone sets item 13 after adoption, are decide-by: C3.
*Source:* Spec A FR-11 ("beside the threat model item"); FR-18 and its bullet ("until it adopts, the project keeps today's behaviour").
*Status:* decided; **decide-by: C3** for item 14's slug and home section and for the item-13 set behaviour.
*Consumers:* C2, C3, C4 (C4-L1).

**R11 — The spec-reviewer seat.** The spec-reviewer seat is its own role in configure's engine preferences (`enginePreferences.specReviewer` in the project's `core.md`), separate from the code-review roles and seat pins, with no plugin default and no model named by the plugin. When it is unset, or names an engine of the spec author's own model family, the checks use a reviewer from an installed engine of a different model family, chosen the way review panels already choose cross-vendor seats; only when no different-family engine is installed do the checks take the same-family path: a fresh reviewer from the author's family, said plainly on the owner's final sheet.
*Source:* Spec A FR-43 ("separate from the code-review seats; the plugin shall name no model for it"); FR-42; UFR-7.
*Status:* decided.
*Consumers:* C3, C4 (C4-L4), C5 (C5-L1).

**R12 — One setup sitting, shared with the review-overhaul discovery.** C3 adds the "who it's for and what it's for" question to configure's set-up as its own step, placed so the review-overhaul discovery's (#1472) risk-profile questions can join it in one sitting. Where risk-tolerance records live is not decided in this package: it is decided once, together with that discovery. This seam is owed reciprocally: when #1472's spec is approved, its register (or its single child's issue body) quotes this entry.
*Source:* Spec A, Assumptions & dependencies ("Setup asks 'who it's for and what it's for' and the review-overhaul discovery's risk profile in one sitting; where risk-tolerance records live is decided once, together with that discovery"); HANDOFF ruling 57.
*Status:* **decide-by: C3** for the step's placement; the risk-tolerance home is owed to the #1472 package and is not this epic's to decide. **Risk-tolerance home answered, recorded by the advisor 2026-10-10:** the review package's register entry R9 (`docs/superheroes/risk-calibrated-review-that-learns-dec0af/register.md`) answers it: risk-tolerance records live in the one "Risk and trust" configure item, and the risk questions join the who-it's-for sitting.
*Consumers:* C3.

**R13 — The three checks' home and seats.** The three checks (gap review; the source check, both directions; grounding), the three finding piles and five decline reasons, the round rules and the re-run after a set of owner rulings live in one new reference doc, `plugins/superheroes/skills/architect-discovery/reference/spec-checks.md`, which discovery follows and no other surface restates. Discovery dispatches the three in parallel, each to the spec-reviewer seat, and each check keeps the same reviewer across rounds, confirming the last round's fixes before looking for new problems. How the same reviewer is kept across rounds is decide-by: C5.
*Source:* Spec A FR-41, FR-42 ("the same reviewer shall continue across rounds, confirming the last round's fixes before looking for new problems"), FR-45 to FR-48.
*Status:* decided; **decide-by: C5** for the same-reviewer mechanism.
*Consumers:* C4 (C4-L3), C5 (C5-L1, C5-L2), C6.

**R14 — What the checks hand discovery.** The checks keep one running record per spec: the rounds run; each finding with its pile (fixed as craft, queued for the owner with a recommendation, or declined with its reason and proof); declines the reviewer still contests; findings marked "the review didn't settle this"; and whether the reviewers were of the author's model family. Discovery builds every remainder sheet's items and its "why only these" facts, and the final sheet's history and folded declines, from that record. Where the record lives and its exact shape are decide-by: C5.
*Source:* Spec A FR-35, FR-38, FR-45, FR-46, UFR-3, UFR-7; Spec B FR-15, FR-17.
*Status:* **decide-by: C5** for the record's place and shape.
*Consumers:* C4 (C4-L4), C5 (C5-L1).

**R15 — The spec review weight call retires.** Every spec gets the three checks, and no surface lets a light-or-full weight call decide how a spec is reviewed; code review's light, full and micro lanes are untouched, and the advisor may still size its own vet.
*Source:* Spec A FR-49a; What this spec amends (front-half-sdlc-core FR-16 and FR-17).
*Status:* decided.
*Consumers:* C4 (C4-L3), C5 (C5-L2), C6.

**R16 — Retiring review-spec: the consumer list.** The callable review-spec skill retires, and C5 repoints every live mention of it to the three checks' home. The live sites, as of the approved specs, are: in the plugin, `skills/architect-discovery/SKILL.md`, `skills/architect-spec/SKILL.md` and `skills/architect-spec/reference/spec-content.md`, `skills/showrunner/SKILL.md` duty 1, `rubric/review-base.md`, `reference/review-loop.md`, `reference/decision-points.md`, `agents/grounding-reviewer.md`, `skills/audit-debt/SKILL.md`, `skills/review-code/reference/synthesis-pass.md`, `lib/citation_validator.py`, `lib/doc_focus_flags.py`, `lib/gate_write.py`, `lib/loop_state.py`, `lib/loop_synthesis.py`, `lib/model_tier.py`, `lib/spec_loop_plan.py` and `.codex-plugin/plugin.json`; at the repo root, `README.md`, `CONVENTIONS.md`, `RELEASING.md`, `docs/superheroes/KEEP-OR-RETIRE.md`, `eval/gate.md` and `eval/skills/` (its README, registry, activation result and mappings). Dated history (the CHANGELOG, ROADMAP's cut rows, specs' Amendments logs) stays as written. A spec's review gate keeps its states (pending, changes-requested, passed) and its stale-approval guard. Which lib modules retire with the skill and which stay because another surface uses them is decide-by: C5, listed in its PR body. No later child reintroduces a pointer to review-spec.
*Source:* Spec A FR-49; FR-49b ("the spec-writing and discovery skills, showrunner duty 1, CONVENTIONS and the keep-or-retire list"; "A spec's review gate keeps its states (pending, changes-requested, passed)"); a repository search for `review-spec` at this package's base commit.
*Status:* decided; **decide-by: C5** for which lib modules retire.
*Consumers:* C4 (C4-L3), C5 (C5-L2), C6.

**R17 — The sheet data file.** A sheet is the plugin's review template published together with one data file that holds the sheet's cards; no session edits the template's code to make a sheet, and the data file is also the sheet's saved source. The data file names the sheet's kind (a remainder sheet, a final sheet, or a plain sheet for any other review) and its title; for a remainder sheet, the facts behind "why only these" (rounds run, fixes made, any finding the review didn't settle); for a final sheet, how the spec got there (review rounds, fixes, the vet), the folded declined findings, and the approval card's facts (whether there is an approved board and whether it is saved with the spec). Each card carries a stable id, the kind of call, whether it carries the warning badge, the question, its context (sections the sending session titles and writes as paragraphs and bulleted lists, quoting the exact text the call is about where there is one; no fixed headings, Spec B amendment 3, 2026-10-07), its images, its options each with a plain consequence, and a one-line recommendation with its reason. The data file's field names are decide-by: C7, which lands the schema with the template; the amended context's shape and field names are decide-by: C10, which changes the schema, and C4 (C4-L4) builds its data files to the schema C10 lands.
*Source:* Spec B FR-5, FR-7, FR-15, FR-17; Spec A FR-35, FR-38; Spec A UFR-5 ("the sheet's source and its answers are saved where a later session can read them").
*Status:* decided. **Decide-by outcomes, recorded by the advisor 2026-10-08:** C7 named the field names in `plugins/superheroes/theme/sheet.schema.json` (stack #1642), the one home for them; C10 (PR #1676) set the amended context's shape there: a card's `context` is a list of sections `{"title", "blocks"}`, each block exactly one of `{"paragraph"}`, `{"bullets"}` or `{"quote"}`; the schema id stays `superheroes-sheet/1`.
*Consumers:* C4 (C4-L4), C7 (C7-L2), C8 (C8-L1, C8-L2, C8-L3, C8-L4), C10.

**R18 — How answers come back.** A sheet is published private to the owner, and its own store holds the answers: each tap writes or replaces one document per card, keyed by the card's id, in an `answers` collection (the answer, and the note; the answer is an option or Something else on a card with options, and Aligned or Discuss on a card without, Spec B amendment 3, 2026-10-07), so the last tap counts; the stored value for Something else is decide-by: C10; an answer stored under a control the card no longer offers (an Aligned or Discuss saved before a card gained options, under amendment 3) counts as unanswered: the sheet shows the card with no answer chosen and keeps the note, and the session asks; answers are keyed by card id across a sheet's revisions by design, so a republished sheet keeps the answers to its unchanged cards; a final sheet's verdict (Approve or Not yet, with its note) saves the same way, the moment it is tapped, as one document per sheet revision at `verdict/<digest>` (`<digest>` is the SHA-256, in lowercase hex, of the exact published `sheet.json` bytes, so a republished sheet starts unsigned and a page showing an older revision never touches a newer one), holding the verdict, the note and the digest; it never counts as approval on its own, reopening the sheet restores it, and the sheet has no "Send verdict" button (Spec B amendment 2, 2026-10-07). The sheet shows each answer's save state, and its next-step line tells the owner to come back to the chat once every answer shows it is saved. The session that sent the sheet reads every answer, and on a final sheet the verdict document for the published revision, together once the owner says in the chat that the sheet is done; a card with no stored answer, or a final sheet with no verdict document, is unanswered, and the session asks rather than assuming; it never acts on a single tap, treats a card answered Discuss or Something else as open for chat, and treats a card whose note disagrees with its answer as open for chat and asks. Another session can take a sheet over by reading its data file and its store; nothing assumes the owner has a second account.
*Source:* Spec B FR-4, FR-4a and its bullets ("no extra submission machinery is built for this"), FR-6's bullets, FR-18; Spec A UFR-5 ("The plugin assumes nothing about an owner having more than one Claude account").
*Status:* decided. **Decide-by outcome, recorded by the advisor 2026-10-08:** C10 (PR #1676) stores Something else as `"answer": "something-else"` with `optionId` null (`plugins/superheroes/theme/sheet.schema.json`, the one home).
*Consumers:* C4 (C4-L4), C6, C8 (C8-L1, C8-L3, C8-L5), C10.

**R19 — The theme ships once.** The Comic panel theme ships as one stylesheet, with its fonts declared, at a path C7 names; the review template and every board's frame and labels load it, nothing else restates a theme colour, font or part rule, and a board draws the product itself in the project's design system, never in the theme. The path is decide-by: C7.
*Source:* Spec B FR-19 to FR-22 ("a board draws the product itself in the project's design system"); Spec A FR-28 ("the plugin's own frame, labels and sheets use the Comic panel theme").
*Status:* decided; **decide-by: C7** for the path.
*Consumers:* C4 (C4-L2), C7 (C7-L1, C7-L2), C8 (C8-L1, C8-L2, C8-L3, C8-L4).

**R20 — When a sheet can't be shown.** Where the host can't show a sheet, the session puts the same cards to the owner as numbered chat prose, each with its context, options and recommendation, built from the same data file; the template's usage doc states this once and discovery points at it.
*Source:* Spec B UFR-1; Spec A UFR-4 (the same rule, from discovery's side).
*Status:* decided.
*Consumers:* C4 (C4-L4), C8 (C8-L1), C10.

**R21 — The vet handoff between discovery and the advisor.** Discovery hands a spec to the advisor's vet by opening the spec PR once the owner says "ready for vet" (where the project keeps specs out of the repo or gitignored, the stored spec stands in for the PR). The advisor never edits the spec; it returns every finding to discovery in one durable vet record on the PR (or beside the stored spec), each finding marked craft or owner call, and vets again after discovery's fixes. Discovery fixes the craft findings and carries the owner calls to the final sheet. The vet record's exact shape, and how discovery learns a vet is done, are decide-by: C6.
*Source:* Spec A FR-36, FR-36a, FR-37 ("shall never fix the spec itself, and shall send every finding back to discovery, which fixes it"), FR-38 ("a final sheet holding the vet's owner calls"), UFR-6.
*Status:* decided; **decide-by: C6** for the record's shape and the done notice.
*Consumers:* C4 (C4-L4), C6.

**R22 — After approval.** When the owner, having chosen Approve on the final sheet, says in the chat that the sheet is done (a saved Approve alone starts nothing; R18), and no other answer on the final sheet changes the spec (Spec A FR-38a's hold comes first: such an answer sends the spec back through its checks, a new vet and a new approval card), the advisor adds the breakdown to the same spec PR (or beside the stored spec) and vets it; the existing independent package read still runs where it applies; one merge word covers both, and issues file with the owner's word as it merges. The final sheet's "what happens next" line says exactly this.
*Source:* Spec A FR-39 and its two bullets; Spec B FR-17's bullet.
*Status:* decided.
*Consumers:* C6, C8 (C8-L3).

**R23 — No new machinery for tags, Canon or the source check.** Source tags are plain text at the end of a statement, Canon is one plain file, and the source check is an agent reading plain files; none of the three adds a new script, validator or database, and no script reads a tag.
*Source:* Spec A, Non-functional requirements, Simplicity ("source tags, Canon and the source check add no new scripts, validators or databases"); FR-31's first bullet ("no new script or validator reads tags"); Constraints.
*Status:* decided.
*Consumers:* C1, C4 (C4-L3), C5 (C5-L1).

**R24 — Glossary terms.** The glossary, `plugins/superheroes/rubric/glossary.md`, gains one entry each, under a stable heading, for Canon, ceded call and standing ruling (C1); the owner-vs-craft line (C2); remainder sheet and ready for vet (C4); and card and sheet (C8). Every other surface links the heading and states no definition of its own.
*Source:* Spec A, Glossary; Spec B, Glossary; the glossary's own rule ("The one home for the plugin's ruled vocabulary").
*Status:* decided.
*Consumers:* C1, C2, C4 (C4-L4), C8 (C8-L1).

**R25 — Shipped text carries no spec provenance.** Plugin text this epic ships states its rules without the specs' source tags, ruling numbers, requirement numbers or discovery-note references, per `plugins/superheroes/rubric/prose-standard.md` § "Shipped surfaces carry no project provenance"; source tags belong in specs, never in shipped doctrine.
*Source:* `rubric/prose-standard.md` § Shipped surfaces carry no project provenance (shipped doctrine; this entry applies it, it adds nothing).
*Status:* decided.
*Consumers:* C1, C2, C3, C4 (C4-L1, C4-L2, C4-L3, C4-L4), C5 (C5-L1, C5-L2), C6, C7 (C7-L1, C7-L2), C8 (C8-L1, C8-L2, C8-L3, C8-L4), C10.
