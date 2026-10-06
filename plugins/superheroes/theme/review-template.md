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
2. Copy `review-template.html`, `comic-panel.css` and `sheet.schema.json` into it, unchanged.
3. Write the data file into the same folder as `sheet.json`.
4. Publish the template as the page, with the stylesheet, the schema and the data file as
   supporting files, so the published paths are `comic-panel.css`, `sheet.schema.json` and
   `sheet.json`.

The shape of the publish call:

```
file_path = <staged folder>/review-template.html
files     = {"comic-panel.css": "<staged comic-panel.css>",
             "sheet.schema.json": "<staged sheet.schema.json>",
             "sheet.json": "<staged sheet.json>"}
capabilities = {"db": {"rules": [{"path": "", "read": "view", "write": "owner"}]}, "user": {}}
```

The publish call also declares the sheet's store and viewer. This lets everyone who can open the
sheet read it, and only its owner answer.

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

## How answers come back

A tap saves at once, as a draft the owner can change, into the sheet's own store. The last tap
counts. Each card's stored document has the shape `answer.schema.json` defines. Anyone but the
owner who opens a shared sheet sees it with the answer controls turned off.

A save that fails says so on the card and offers Try again.

The session that sent the sheet reads every answer together once the owner says the sheet is done,
and never acts on a single tap.

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
