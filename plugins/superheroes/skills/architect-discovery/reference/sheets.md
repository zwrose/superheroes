# Contents

- [Sheets](#sheets)
- [Where a sheet lives](#where-a-sheet-lives)
- [Building a remainder sheet](#building-a-remainder-sheet)
- [Sending a sheet](#sending-a-sheet)
- [Reading the answers](#reading-the-answers)
- [Handing over for the vet](#handing-over-for-the-vet)
- [Building the final sheet](#building-the-final-sheet)
- [What the final sheet's answers mean](#what-the-final-sheets-answers-mean)
- [When the host can't show a sheet](#when-the-host-cant-show-a-sheet)
- [Taking a sheet over](#taking-a-sheet-over)
- [The owner never reads the spec end to end](#the-owner-never-reads-the-spec-end-to-end)

# Sheets

Step 8 of the skill owns when each sheet is sent. This reference holds how a sheet is built, sent,
read and taken over. The sheet template's own rules are in `theme/review-template.md`, and this
doc points at them and restates none of them.

## Where a sheet lives

A sheet lives in the spec's work-item folder, which `definition_doc.py dir --work-item <slug>`
prints. Under it, a `sheets/` folder holds:

- One folder per sheet, named `<n>-<kind>` in send order, such as `1-remainder` or `3-final`. It
  holds the sheet's data file, which is the sheet's saved source.
- The `sheets.md` log, one line per sheet: its folder, kind, link, date sent, and `open` or `done`.

Keep the link the publish returns, in the log line and beside the data file. A republish keeps the
folder and the link and updates the data file. Record a republish of a final sheet as a new line
with the same link, so each revision is listed.

## Building a remainder sheet

A remainder sheet's cards come only from `checks-record.md`.

1. Take the owner's queue: the owner's-pile items, the declines marked contested with both sides,
   and the items marked "the review didn't settle this".
2. Drop every item an earlier sheet's answer already settled.
3. Add one card per entry in `redraws.md` (in the work item's `board` folder) that is still
   `sent: no`, showing the redrawn board. Mark each of those entries `sent: yes` once the sheet is
   sent.

Nothing else goes on the sheet. A craft fix stays off it, and so does any item a board, a ruling or
an earlier answer covers. An unsourced statement that decides product behaviour is a card with a
recommendation and the warning badge.

The "why only these" facts come from the record too: the rounds run, the fixes made, and the cards
that hold a finding the review didn't settle.

Every field name, kind value and answer value comes from `theme/review-template.md` and
`theme/sheet.schema.json`. This doc names none of them, so it needs no rewrite when they change. A
card's id stays the same call across republishes. A later sheet reuses an id only for the same call.

## Sending a sheet

Publish the sheet exactly as `theme/review-template.md` says in its section Publishing a sheet. Then
tell the owner in one or two chat lines what the sheet holds, and that they say they're done in the
chat once every answer shows it is saved.

To change a sheet, republish to the same link, as that doc says in its section Updating a sheet.

## Reading the answers

Follow `theme/review-template.md` in its section How answers come back: when to read, how, and
what to ask about. This doc names no stored value. One discovery-specific point: a card answered
Discuss or Something else is open for chat and is asked about, the two treated alike.

Then record each ruling in Canon as `rubric/canon-contract.md` says in its section Writing a ruling.
Apply the answers to the spec first. Keep the sheet `open` in the `sheets.md` log until they are
applied and the checks on the changed parts have run. Then mark it `done` and continue step 8.

## Handing over for the vet

Tell the advisor the spec's path and the path of `checks-record.md`, in either mode.

- **A spec committed in the repo.** Commit the spec, `checks-record.md`, the `board/` folder and
  the `sheets/` folder on a branch, and open the spec PR. The advisor's vet records land on the PR.
- **A spec kept out of the repo, or in the repo but gitignored.** Tell the advisor the stored
  spec's path. The vet records land beside it, as `skills/showrunner/reference/spec-vet.md` says in
  its section The vet record.

## Building the final sheet

Send the final sheet only after a current clean vet record (step 8). Its cards are:

- Every owner call the vet records raised.
- Every `redraws.md` entry still `sent: no`.
- When the header of `checks-record.md` says the reviewer was from the author's own family, one
  card carrying the sentence that header gives, word for word. The record's header holds that
  sentence. Do not copy it here or paraphrase it.

The rest of the sheet comes from the record and the vet records:

- Its history is the rounds run, the fixes made and the vet's one line.
- Its declined findings are every decline on the record, folded away, each with its reason.
- Its approval facts say whether there is an approved board and whether it is saved with the spec.

Say the writing pass on the sheet in plain words. Take it from the "Writing pass" section of the
record, and restate none of that section's rules. It reads one of three ways: the wording was tidied
after the checks and an independent reviewer confirmed no meaning moved, the tidy-up was thrown
away, or the pass changed nothing.

When a check did not run in the last round, the sheet says so and names the check, in plain words.

## What the final sheet's answers mean

Step 8 of the charter holds the approval conditions and the changes-requested path; this section
adds only what is specific to sheets.

When the re-run checks put anything new in the owner's queue, settle it on a remainder sheet, as in
Building a remainder sheet, before the spec goes back to the vet. Repeat until the queue holds
nothing unsettled. Items settled that way do not go on the republished final sheet.

The republished final sheet starts unsigned, because its data file changed. When a changed answer
redraws the board, put the redraw on that republished sheet.

## When the host can't show a sheet

`theme/review-template.md` says in its section When the host can't show a sheet how the prose is
rendered, from the same data file.

In that mode the sheet has no store. So write each answer into an `answers.md` file in that sheet's
folder, as the owner gives it: the card id, the answer in the owner's words, the note and the date.
Write a final sheet's verdict there the same way. Put the data file's digest on the verdict line
only, as `theme/review-template.md` names the digest for the saved verdict; an answer line is keyed
by its card id alone, as in the template. A republish changes the digest, so an earlier verdict, an
old Approve included, no longer matches and counts as unanswered, while an answer to a card whose
call is unchanged still stands. A session that takes the sheet over reads `answers.md` with the data
file, keeps the answers to unchanged cards, and accepts only a verdict line carrying the current
digest.

The same three conditions for approval hold. The owner's chat words stand in for the saved verdict.

## Taking a sheet over

Another session given only the work item does this:

1. Read the `sheets.md` log, in the work item's `sheets` folder.
2. Open the data file of the newest `open` sheet. First check the newest `done` sheet: when its
   rulings are in Canon but not yet in the spec, apply them, run the checks on the changed parts,
   and only then carry on.
3. Read its store through the kept link, as `theme/review-template.md` says in its section How
   answers come back. On a final sheet, read the verdict for the published revision too. In the
   prose mode, read the sheet's `answers.md` instead.
4. Carry on from the answers already given. Never ask again for an answered card. Treat an
   unanswered card, or a missing verdict, as unanswered.

Nothing in this assumes the owner has a second account.

## The owner never reads the spec end to end

Everything that needs the owner arrives as a card on a remainder sheet or the final sheet. The spec
itself is for the build and the advisor. The owner may still open it.
