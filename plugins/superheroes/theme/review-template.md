# The review template

## What a sheet is

A [sheet](../rubric/glossary.md#sheet) is the review template page (`review-template.html`) published together with one data
file that holds the sheet's [cards](../rubric/glossary.md#card). The page draws the sheet's title and one card per call, in the
plugin's theme (`comic-panel.css`).

A session never edits the template's code to make a sheet. It writes a data file.

## Who uses it

Discovery's remainder sheets and its final sheet use the template. Any session may use it when it
has calls for the owner, and the owner may ask for one. No other review is required to use it.

## The data file

The data file is `sheet.json`. Its shape is defined by `sheet.schema.json`, which sits beside this
doc. There are three kinds of sheet:

- `remainder`: the calls a review left for the owner. It carries a `remainder` block, and its
  `unsettled` list names the cards that hold a finding the review didn't settle.
- `final`: the sign-off sheet. It carries a `final` block with the review's history, the findings
  that were declined and why, and the approval state.
- `plain`: any other set of calls. It carries neither block.

Each card's `id` must stay the same call across republishes, because answers are keyed by it.
Change the wording of a card freely; never reuse an id for a different call.

The data file is the sheet's saved source. Keep it with the work it belongs to. The page checks
the data file against `sheet.schema.json` when it loads, so a file the schema refuses is never drawn. The page also refuses a schema that uses a kind of rule its reader doesn't check, so a change to the sheet's shape that needs a new kind of rule must also teach the page's reader, or the page refuses every sheet.

## Publishing a sheet

On Claude Code, the Artifact tool publishes only files under the working directory or the
session's scratchpad. So:

1. Make one folder under the scratchpad.
2. Copy `review-template.html`, `comic-panel.css`, `sheet.schema.json` and `sheet-words.json` into it, unchanged.
3. Write the data file into the same folder as `sheet.json`.
4. Publish the template as the page, with the stylesheet, the schema and the data file as
   supporting files, so the published paths are `comic-panel.css`, `sheet.schema.json`,
   `sheet-words.json` and `sheet.json`.

The shape of the publish call:

```
file_path = <staged folder>/review-template.html
files     = {"comic-panel.css": "<staged comic-panel.css>",
             "sheet.schema.json": "<staged sheet.schema.json>",
             "sheet-words.json": "<staged sheet-words.json>",
             "sheet.json": "<staged sheet.json>"}
capabilities = {"db": {"rules": [{"path": "", "read": "view", "write": "owner"}]}, "user": {}}
```

The publish call also declares the sheet's store and viewer. This lets everyone who can open the
sheet read it, and only its owner answer.

`sheet-words.json` holds the owner-facing words a final sheet shares with the chat prose
(`lib/sheet_prose.py`): the page fetches it before drawing a final sheet, and the prose renderer reads
it from the same folder, so the two cannot drift apart. Change those words there and nowhere else.

A published sheet is private to the owner. The owner may share it from the page's Share menu.
Anyone it is shared with sees it but cannot answer.

Keep the returned link with the data file.

## The answers

Each card offers Aligned, Discuss and, when it has options, one button per option, labelled with
the option's own label. Aligned agrees with the card's recommendation, or with the statement when
there is no recommendation. A pick chooses that option. Discuss leaves the call open for chat. No
review adds its own answer buttons.

A card's `warning` follows the rule in `sheet.schema.json` (`$defs/card/properties/warning`). It
draws the red badge. Every other card draws a plain badge naming its kind
of call.

## How a sheet is laid out

A yellow app bar sits at the top with the review's name. Once the saved answers are read, it also
says "A of N answered", and how many of those are marked to discuss. Until they are read, it says
"N items · answers not loaded" instead, so a sheet never claims a count it hasn't checked.

One item is open at a time, with Previous and Next to move between them. Below it, the list of items
shows each one's state: Aligned, Discuss, Picked or Open. An item whose save didn't land carries a
red Not saved badge.

On a phone, a remainder sheet folds the items that are answered into one row, with their Aligned,
Discuss and Picked counts. An answer whose save failed or stalled never folds, so it stays in the list where it
can be seen and retried. On a desktop, every item is listed beside the open card.

A remainder sheet also shows a "Why only these" box. It is built only from the `remainder` block's
rounds run, fixes made and unsettled list, so it says how many items are here and why, and nothing
else.

"Done for now" saves any note that is still pausing, shows whether every answer is saved, and returns
to the same sheet. To come back to a sheet, open the same link.

## A final sheet

A final sheet (`kind` is `final`) is the owner's sign-off. Above the cards it shows how the spec got
here: the rounds the review ran, the fixes it made and the vet's one line. Below that, the findings the
review declined are folded behind a "Declined findings" button, each with the reason it was declined;
when there were none, the sheet says so. The vet's calls are the cards, listed as rows and counted
exactly as on any other sheet. After them comes a last card, "Approve the spec?", with what the spec
traces to, whether the approved board is saved with it (shown only when there is an approved board),
the Approve and Not yet buttons, a note and a Send verdict button. A box under it says what happens
next.

A tap on Approve or Not yet, and the note, save at once as a draft verdict at `draft-verdict/<digest>`,
in the shape `sheet.schema.json` defines at `$defs/draftVerdict`. A draft never counts as a verdict.
It comes back when the owner opens the link again, and it is not counted as an answer.

Every stored verdict, draft or sent, carries `sheet`: the SHA-256, in lowercase hex, of the exact
bytes of the published `sheet.json` as the page fetched them (the bytes themselves, so a file with a
byte-order mark hashes with it). That digest, written `<digest>` here, is also the document's own id:
the draft is stored at `draft-verdict/<digest>` and each sent verdict at `verdict/<digest>/sends/<sendId>`,
so each revision of the sheet has its own draft and its own sends, and `sheet` equals the `<digest>`
in the path. The page reads and writes only its own revision's documents; a delayed write from a page
showing an older revision lands among that older revision's sends and can never touch a newer revision's verdict. A republished final sheet
has a new digest, so it starts unsigned. A document whose `sheet` is not its own id is ignored: nothing
is restored and nothing locks. A browser that cannot compute the digest
(no `crypto.subtle`) leaves the last card and Send verdict off, with a plain line saying so.

Send verdict is off until a verdict is picked. Once tapped, it freezes the sheet, saves any note that
is still pausing and waits for every card's answer to be saved. If an answer didn't save, or is still
unsaved after ten seconds, it says how many and what to do, writes nothing and unfreezes the sheet.
When every answer is saved it lists `verdict/<digest>/sends` once more. If a valid send for this sheet
revision is already there (another open copy sent it), it writes nothing, shows that verdict as sent and
locks the sheet. Otherwise it creates a new document of its own at `verdict/<digest>/sends/<sendId>`, where
`<sendId>` is 32 lowercase hex characters from the browser's random source (a browser without one leaves
Send verdict off, with a plain line saying so, like a missing digest), in the shape `$defs/verdict`. Sends are
the only documents that count as the owner's verdict. That document holds the verdict, its note, the `sheet` digest and
`answers`: one entry per card in sheet order, each `{card, answer}` with the card's stored answer
document, frozen at the moment of sending. The page says "Verdict sent" only after that write has landed.
Because every send is its own document, no send can replace another.
If the write is refused, the page says the verdict didn't send and offers Try again, and the sheet
unfreezes so the owner may change things first. If the write is slow, the page asks the owner to keep
the page open and offers no Try again while the write may still land.

A sent verdict locks the sheet: it shows the verdict that was sent, and every control stays off,
including when the owner opens the link again; any valid send means sent. A document under
`verdict/<digest>/sends` that does not fit `$defs/verdict`, or whose `sheet` is not that `<digest>`, is
ignored, so it never counts as sent. If more than one valid send exists and they differ in verdict, note
or answers, the status says "More than one verdict was sent for this sheet from different windows. The
session will ask you which one counts." and the sheet stays locked.

A final sheet may have no cards, when the review left no calls. It then shows "Nothing left to
answer" in place of the count, the list and the stepper, and the history, the last card, Send verdict
and the next line work as usual.

"Done for now" on a final sheet saves any pending note, including the verdict's, and says the owner's
verdict counts only once they tap Send verdict.

## How answers come back

A tap saves at once, as a draft the owner can change, into the sheet's own store. The last tap
counts. Each card's stored document has the shape `sheet.schema.json` defines at `$defs/answer`. Anyone but the
owner who opens a shared sheet sees it with the answer controls turned off.

A save that fails says so on the card and offers Try again.

The session that sent the sheet reads every answer together once the owner says the sheet is done,
and never acts on a single tap.

On a final sheet, once the owner taps Send verdict, the session lists `verdict/<SHA-256 of the sheet.json it published>/sends` and nothing else for the verdict: exactly one send,
or several identical ones, is the verdict, and it takes the verdict, its note and the
answers from it; several that differ mean it asks the owner which one counts and treats the sheet as Discuss. It never acts on a draft and never reads `answers/` for the verdict. It uses
a send only when its `sheet` equals that same SHA-256 (for
example `shasum -a 256 sheet.json`); a republished final sheet starts unsigned because its digest is new.

A card whose note disagrees with its answer is read as Discuss: ask the owner about it.

Another session can take a sheet over by reading its data file and its store.

## Updating a sheet

Republish to the same link with the changed `sheet.json`, and with the same template and
stylesheet. Never fork a second copy of the page: the owner's link must keep pointing at the
current sheet.

## When the page shows an error

If the page can't trust the data file, it shows a box titled "This sheet can't be shown" and lists
what is wrong, one problem to a line. It draws no cards, so a broken sheet never looks like a
finished one.

The problems name the data file: it (or the schema file) could not be loaded, it isn't valid JSON, or a card is
missing something (the problem names the card's `id`). Fix the data file and republish to the
same link.

## When the host can't show a sheet

Where the host can't show a sheet, the session puts the same cards to the owner as numbered chat
prose, each with its context, options and recommendation, built from the same data file.

Render the prose with `python3 -B "${CLAUDE_PLUGIN_ROOT}/lib/sheet_prose.py" render --sheet <the data file>`
and paste its output. It runs on a plain Python, with nothing to install. It refuses a data file it
can't trust, and lists what is wrong one problem to a line.
