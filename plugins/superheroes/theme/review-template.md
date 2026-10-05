# The review template

## What a sheet is

A sheet is the review template page (`review-template.html`) published together with one data
file that holds the sheet's cards. The page draws the sheet's title and one card per call, in the
plugin's theme (`comic-panel.css`).

A session never edits the template's code to make a sheet. It writes a data file.

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
the data file against `sheet.schema.json` when it loads, so a file the schema refuses is never drawn.

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
```

A published sheet is private to the owner. The owner may share it from the page's Share menu.

Keep the returned link with the data file.

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
