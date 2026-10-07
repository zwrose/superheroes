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
4. Copy every picture a card names by a relative `src` into the staged folder at that same relative
   path, and add it to `files` under that path.
5. Publish the template as the page, with the stylesheet, the schema, the data file and every picture
   as supporting files, so the published paths are `comic-panel.css`, `sheet.schema.json`,
   `sheet-words.json`, `sheet.json` and each picture's relative path.

The shape of the publish call:

```
file_path = <staged folder>/review-template.html
files     = {"comic-panel.css": "<staged comic-panel.css>",
             "sheet.schema.json": "<staged sheet.schema.json>",
             "sheet-words.json": "<staged sheet-words.json>",
             "sheet.json": "<staged sheet.json>",
             "plan.png": "<staged plan.png>"}
capabilities = {"db": {"rules": [{"path": "", "read": "view", "write": "owner"}]}, "user": {}}
```

The publish call also declares the sheet's store and viewer. This lets everyone who can open the
sheet read it, and only its owner answer.

The example publishes one picture, `plan.png`, which a card names as `"src": "plan.png"`. A picture whose
`src` is a URL loads from that URL and is not copied. If the host can't reach it, the sheet shows it as
missing.

A changed picture is published under a new path (a new name), so changing a picture always changes
`sheet.json` and, on a final sheet, starts it unsigned. A final sheet's pictures are published with the
sheet, never by URL, because a URL picture can change without the sheet changing.

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

One item is open at a time, with Previous and Next to move between them. The same Previous and Next
also sit below the open card, so the owner doesn't have to scroll back up after reading it. Below it,
the list of items shows each one's state: Aligned, Discuss, Picked or Open. An item whose save didn't
land carries a red Not saved badge.

On a phone, a remainder sheet folds the items that are answered into one row, with their Aligned,
Discuss and Picked counts. An answer whose save failed or stalled never folds, so it stays in the list where it
can be seen and retried. On a desktop, every item is listed beside the open card. The folded
"Answered" row, and a final sheet's "Declined findings", show ▶ when closed and ▼ when open.

Tap a picture on a card to open it on its own, large. Pinch or double-tap to zoom, and drag to look
around. On a laptop, pinching the trackpad zooms the open picture about the pointer, as a phone pinch
does. The view holds that one picture and has no way to move to another. Close returns to the card.
A picture that can't load says "This picture is missing" and its description, and the rest of the card,
its answers and its note stay in place, so the card can still be answered.

A remainder sheet also shows a "Why only these" box. It is built only from the `remainder` block's
rounds run, fixes made and unsettled list, so it says how many items are here and why, and nothing
else.

Every answer saves as it is tapped and comes back when the same link is opened again, marked Saved, so
leaving needs no button. The footer says "Answers save as you tap", and on a plain or remainder sheet it also
tells the owner to go back to the chat and say they're done once every answer shows it is saved.

## A final sheet

A final sheet (`kind` is `final`) is the owner's sign-off. Above the cards it shows how the spec got
here: the rounds the review ran, the fixes it made and the vet's one line. Below that, the findings the
review declined are folded behind a "Declined findings" button, each with the reason it was declined;
when there were none, the sheet says so. The vet's calls are the cards, listed as rows and counted
exactly as on any other sheet. After them comes a last card, "Approve the spec?", with what the spec
traces to, whether the approved board is saved with it (shown only when there is an approved board),
the Approve and Not yet buttons and a note. There is no Send verdict button.

A tap on Approve or Not yet, and the note, save at once at `verdict/<digest>`, in the shape
`sheet.schema.json` defines at `$defs/verdict`, the same way an answer saves: every tap and every
pause in the note writes the whole document, the last write counts, and the last card shows the same
Saving…, Saved, Not saved and Try again as a card does. Tapping the chosen one again clears the
verdict, saved as null with the note kept. It comes back when the owner opens the link again, and it
is not counted as an answer.

`<digest>` is the SHA-256, in lowercase hex, of the exact bytes of the published `sheet.json` as the
page fetched them (the bytes themselves, so a file with a byte-order mark hashes with it), and the
document's `sheet` equals it. Each revision of the sheet has its own document, so a republished final
sheet has a new digest and starts unsigned, and a page showing an older revision never touches a newer
one. When the sheet reopens, the page reads only the document whose id is its own digest, and restores
the pick and note only when that document fits `$defs/verdict` and its `sheet` equals the digest.
Another revision's document is ignored. A verdict of null (a note saved before any pick, or a
cleared verdict) restores only the note. A browser that cannot compute the digest (no
`crypto.subtle`) leaves the last card's controls off, with a plain line on the card saying it can't
tell which version of the sheet this is, and reads and writes nothing under `verdict`.

Directly below the last card, a line tells the owner to come back to the chat once every answer shows
it is saved, and say they're done; its words are in `sheet-words.json`, the same file the chat prose
reads. Under it, a box says what happens next.

A final sheet may have no cards, when the review left no calls. It then shows "Nothing left to
answer" in place of the count, the list and the stepper, and the history, the last card, the line
below it and the next box work as usual.

## How answers come back

A tap saves at once into the sheet's own store, and the owner can change it; tapping the picked
answer again clears it, and the cleared answer (null) saves the same way, with the note kept. The
last tap counts. Each card's stored document has the shape `sheet.schema.json` defines at
`$defs/answer`. Anyone but the owner who opens a shared sheet sees it with the answer controls turned
off.

A save that fails says so on the card and offers Try again.

The session that sent the sheet reads every answer together once the owner says in the chat that the
sheet is done, and never acts on a single tap.

On a final sheet the session reads `answers` and `verdict/<digest>` together, where `<digest>` is the
SHA-256 of the `sheet.json` it published (for example `shasum -a 256 sheet.json`). It reads only that
document and uses it only when its `sheet` equals that digest, so a republished final sheet starts
unsigned because its digest is new. A card with no stored answer or a stored answer of null (a
cleared pick), a final sheet with no verdict document, or a verdict of null (a cleared verdict) is
unanswered: the session asks rather than assuming. A saved Approve never counts as approval on its
own; the owner's word in the chat does.

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
