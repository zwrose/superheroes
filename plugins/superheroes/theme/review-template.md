# The review template

## What a sheet is

A [sheet](../rubric/glossary.md#sheet) is the review template page (`review-template.html`) published together with one data
file that holds the sheet's [cards](../rubric/glossary.md#card). The page draws the sheet's title and one card per call, in the
plugin's theme (`comic-panel.css`).

A session never edits the template's code to make a sheet. It writes a data file, and
`lib/sheet_title.py` sets the staged page's title (§ Publishing a sheet).

## Who uses it

Discovery's remainder sheets and its final sheet use the template, and so do PR sheets and stack
sheets, which put a PR's review to the owner before it merges. Any session may use it when it has
calls for the owner, and the owner may ask for one. No other review is required to use it.

## The data file

The data file is `sheet.json`. Its shape is defined by `sheet.schema.json`, which sits beside this
doc. There are six kinds of sheet:

- `remainder`: the calls a review left for the owner. It carries a `remainder` block, and its
  `unsettled` list names the cards that hold a finding the review didn't settle.
- `final`: the sign-off sheet. It carries a `final` block with the review's history, the findings
  that were declined and why, and the approval state.
- `plain`: any other set of calls. It carries neither block.
- `pr`: one PR's review put to the owner before merge. It carries a `prSheet` block. See § A PR sheet and a stack sheet.
- `stack`: the same for a stack of PRs that merges whole, as one sheet. Its `prSheet` block also lists the stack's PRs.
- `index`: the list of PRs waiting on the owner, with the questions that block work above it. It carries an `index` block, and its cards may be none. See § The index.

Each card's `id` must stay the same call across republishes, because answers are keyed by it.
Change the wording of a card freely; never reuse an id for a different call.

The sending session owns the shape of a card's context. It writes sections, titles each in its own
words, and fills them with paragraphs and bulleted lists, the way it would explain a call in chat:
"what you're accepting", what is true now, why it needs the owner, whatever the call needs. Where the
call is about exact text, it quotes it as a `quote` block. The template fixes no heading and requires
no section, so a card never shows an empty heading or an empty quote.

The data file is the sheet's saved source. Keep it with the work it belongs to. The page checks
the data file against `sheet.schema.json` when it loads, so a file the schema refuses is never drawn. The page also refuses a schema that uses a kind of rule its reader doesn't check, so a change to the sheet's shape that needs a new kind of rule must also teach the page's reader, or the page refuses every sheet.

## Publishing a sheet

On Claude Code, the Artifact tool publishes only files under the working directory or the
session's scratchpad. So:

1. Make one folder under the scratchpad.
2. Copy `comic-panel.css`, `sheet.schema.json` and `sheet-words.json` into it, unchanged.
3. Write the data file into the same folder as `sheet.json`.
4. Stage the page with its title:

   ```
   python3 -B "${CLAUDE_PLUGIN_ROOT}/lib/sheet_title.py" stage --sheet <staged sheet.json> --project <project> [--slug <work-item slug>] --out <staged folder>/review-template.html
   ```

   It writes `review-template.html` with its `<title>` set to the sheet's title and changes nothing
   else. The page's `<title>` is the artifact's title in the sidebar and the gallery, so the publish
   call passes no `title`. `<project>` is the project's name as its repository names it, without the
   owner. A plain, remainder or final sheet passes `--slug` with its work item's slug; no other kind
   does. The titles:

   - a PR sheet: `<project> PR #<number> review sheet`, for example `superheroes PR #7 review sheet`;
   - a stack sheet: `<project> stack PR #<bottom>–#<top> review sheet`;
   - the index: `<project> open decisions review sheet`;
   - a plain, remainder or final sheet: `<project> <work-item slug> review sheet`.

   The app bar still shows the data file's own `title`, and the data file is never touched, so its
   digest, answers and verdict are the same as before. A sheet published before titles were set keeps
   "Review sheet" until it is next republished.
5. Copy every picture a card names by a relative `src` into the staged folder at that same relative
   path, and add it to `files` under that path.
6. Publish the staged page, with the stylesheet, the schema, the data file and every picture
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

A PR sheet's call adds `"assets": {}` to `capabilities`: Add a screenshot uploads through it, and it makes
the sheet organization-internal.

The publish call also declares the sheet's store and viewer. This lets everyone who can open the
sheet read it, and only its owner answer.

The example publishes one picture, `plan.png`, which a card names as `"src": "plan.png"`. A picture whose
`src` is a URL loads from that URL and is not copied. If the host can't reach it, the sheet shows it as
missing.

A changed picture is published under a new path (a new name), so changing a picture always changes
`sheet.json` and, on a final sheet, starts it unsigned. A final sheet's pictures are published with the
sheet, never by URL, because a URL picture can change without the sheet changing.

`sheet-words.json` holds the owner-facing words a final sheet shares with the chat prose
(`lib/sheet_prose.py`), and the answers each card offers (their words, and which a card with options and
which a card without options gets): the page fetches it before drawing a sheet, and the prose renderer reads
it from the same folder, so the two cannot drift apart. Change those words there and nowhere else.

A published sheet is private to the owner. The owner may share it from the page's Share menu.
Anyone it is shared with sees it but cannot answer.

Keep the returned link with the data file.

## The answers

On a plain, remainder or final sheet, a card with options offers one button per option, labelled with the option's own label, and
**Something else**, and nothing more. A card without options offers **Aligned** and **Discuss**. A
pick chooses that option. Something else leaves the call open for chat, and the note is the place to
say what instead. Aligned agrees with the card's recommendation, or with the statement when there is
no recommendation. Discuss leaves the call open for chat. No review adds its own answer buttons. A PR
sheet's buttons are set out in § A PR sheet and a stack sheet.

A card's `warning` follows the rule in `sheet.schema.json` (`$defs/card/properties/warning`). It
draws the red badge. Every other card draws a plain badge naming its kind
of call.

## How a sheet is laid out

A yellow app bar sits at the top with the review's name, and scrolls away with the page. Once the
saved answers are read, it also says "A of N answered", and how many of those are open for chat
(Discuss or Something else). Until they are read, it says
"N items · answers not loaded" instead, so a sheet never claims a count it hasn't checked.

One item is open at a time, with Previous and Next to move between them. The same Previous and Next
also sit below the open card, so the owner doesn't have to scroll back up after reading it. Below it,
the list of items shows each one's state: Aligned, Discuss, Picked, Something else or Open. An item whose save didn't
land carries a red Not saved badge. Moving to another item, from Previous, Next or the list, scrolls
the page back to its top.

A note box scrolls into view when it is opened, and again if the on-screen keyboard comes up and
covers it. A box that is already in view stays where it is. Web addresses (`http://` or `https://`)
in a card's text, and in a final sheet's declined findings and history, are links that open in a new
tab. The answer buttons stay plain text, even when an option's label holds an address.

On a phone, a remainder sheet folds the items that are answered into one row, with how many of them
are settled (Aligned, or an option picked) and how many are open for chat (Discuss or Something
else). An answer whose save failed or stalled never folds, so it stays in the list where it
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
sheet has a new digest and starts unsigned, and so does a PR or stack sheet republished with a material
move (`previousCommit` alone); a page showing an older revision never touches a newer one. When the
sheet reopens, the page reads only the document whose id is its own digest, and restores the pick and
note only when that document fits `$defs/verdict` and its `sheet` equals the digest. Another revision's
document is ignored. That holds for a final sheet, and for a PR or stack sheet with no carry; the one
exception is a PR or stack sheet republished with `carriedForward`, which reads through its chain
(§ A carried PR). A verdict of null (a note saved before any pick, or a
cleared verdict) restores only the note. A browser that cannot compute the digest (no
`crypto.subtle`) leaves the last card's controls off, with a plain line on the card saying it can't
tell which version of the sheet this is, and reads and writes nothing under `verdict`.

Directly below the last card, a line tells the owner to come back to the chat once every answer shows
it is saved, and say they're done; its words are in `sheet-words.json`, the same file the chat prose
reads. Under it, a box says what happens next.

A final sheet may have no cards, when the review left no calls. It then shows "Nothing left to
answer" in place of the count, the list and the stepper, and the history, the last card, the line
below it and the next box work as usual.

## A PR sheet and a stack sheet

A PR sheet (`kind` is `pr`) puts one PR's review to the owner before the merge. A stack sheet (`kind` is
`stack`) does the same for a stack that merges whole, as one sheet. Both carry the `prSheet` block
(`$defs/prSheet` in `sheet.schema.json`). Every word the page shows on one is in the `pr` and
`prAnswers` blocks of `sheet-words.json`.

The advisor never writes the data file by hand. It builds it from the PR's review record, one
`--record` for each PR of a stack, one `--pr-body` for each PR it covers, and its own input:

```
python3 -B "${CLAUDE_PLUGIN_ROOT}/lib/pr_sheet.py" build --record <file> [--record <file> ...] --pr-body <number>=<file> [--pr-body ...] --input <file> --out sheet.json
```

Each `--pr-body` file holds one covered PR's body, read with `gh api repos/<o>/<r>/pulls/<n> --jq .body`.

A PR that had no review run gets no sheet; never hand-build a review record to make one. The owner merges it with their own click, as the showrunner charter's duty 6 says
([`skills/showrunner/SKILL.md`](../skills/showrunner/SKILL.md)).

**A spec PR's sheet.** A spec PR has no review record, and it still gets a sheet, so that one Merge verdict
plus "done" covers the spec and its breakdown, as duty 6 says. The input names `spec` (the work-item
folder, every spec-vet record posted on the PR, and the PR's CI) and the build takes no `--record`:

```
python3 -B "${CLAUDE_PLUGIN_ROOT}/lib/pr_sheet.py" build --pr-body <number>=<file> --input <file> --out sheet.json
```

Its facts come from the spec's own artifacts. The reviewer and the round count come from the spec checks
record, `checks-record.md`. The commit and one history line per round come from the advisor's vet
records, and the newest one must be a clean breakdown vet. The breakdown comes from that record's
`Breakdown pins:`. The pins become one Accept card, **The breakdown**, under What you're accepting. It
lists every body the filing writes (a new issue, an issue rewritten in place, or a seam quoted onto one) and the coverage map, register and package-read audit trail, each
with its path and hash, and its title counts the bodies. A pin that no longer hashes to its pinned value
refuses the build, and so does a spec that no longer hashes to the newest record's `Vet done:` hash: a
stale breakdown is never shown as accepted. A `.md` file beside a pinned file in its subfolder that
the vet does not pin also refuses. The vet's pins are the inventory: a body left out of every pin in
its subfolder, or at the folder's root, is not caught, because no folder convention lists the bodies. The mode is chosen only by the input's `spec`, so a code PR
missing its record still refuses. The merge verdict and "done" read exactly as on a code PR's sheet.

The shape of the advisor's input is defined in the docstring of `lib/pr_sheet.py`, and nowhere else.
Publishing is as § Publishing a sheet says.

A published PR sheet is private to the owner until shared, and only the owner's answers count, as
§ Publishing a sheet and § How answers come back say.

### Layout

A PR sheet is one scrolling page with every item shown at once, and has no Previous or Next and no item
list. Its parts come in this order:

1. What changed: what changed, who reviewed it, what the review caught, the rounds, CI and the commit it
   ran on, the lane and why, and the commit the sheet describes.
2. The walk, when the PR has something to try: a box to open the product, the count walked, a line saying
   the advisor walked it first and where the pictures come from, then the stops in the order the data file
   declares them, with a group label wherever the group changes, so a group listed apart is labelled again
   where it reappears. A try
   stop shows its numbered steps, an Expect line, its pictures, **Works**, **Problem** and **Skip**, and a
   note. A look stop shows a Look for line and **Looks right**. A Problem asks **Fix before merge** or
   **Fix in a follow-up**, offers **Add a screenshot**, and labels the note "What did you see?". When the
   picture store does not answer in time, the next tap asks again; when this view cannot store pictures at
   all, the button stays off. On a stack each stop names its PR.
3. The items, under the accepting heading.
4. The Decided for you list, when the sheet has one, unfolded: each entry's title, ground, reason and
   **Make this mine**. See `### Decided for you` for the rest.
5. The folded parts: the craft decisions put to the owner's veto, the decisions already made, how the
   review went, and on a stack the stack's PRs. Each shows its count and opens on a tap.
6. The merge verdict.

How the review went carries, per review, the rounds. When some reviewers read an earlier commit it adds
one line: plain when a later round or an audit covered the final commit, a warning when no planned
reviewer's run covers it. It adds one line counting the findings left for the owner below, in place of
one line each. It says "the review record is incomplete" only for the record's other gaps. On a stack,
each line names its PR.

A part with nothing in it is left out, except the items. With no card, the items say one of three things,
read from what the build recorded about the covered PR bodies. They say that the review left nothing
for the owner only when the build recorded that every covered PR body lists no acceptance
(`prSheet.nothingListed`). They say the sheet was checked and every acceptance is covered by a Canon
ruling, naming the entry ids, only when the build recorded that the bodies list at least one acceptance
and each one is accounted to a Canon ruling (`prSheet.canonAccounted`, the ids sorted and distinct, each
appearing in the summary). With neither record they say the sheet was not checked against the PR body. The
app bar follows the same rule for its count. With cards the app bar says "<k> of <n> accepted". The headings and these lines are in the `pr`
block of `sheet-words.json`, the home of the words.

### The items

**Judge before you build.** The sheet carries the owner's real calls; everything else is one tap or
none. Before building a PR or stack sheet, the advisor reads the project's Canon
(`rubric/canon-contract.md`): a standing ruling that already answers a call makes it craft. Then:

- A leftover goes to `craftDeterminations`, not to a card, only on one of the three grounds in
  § Decided for you, each of which means its real consequence needs no card of its own: another
  card on the same sheet carries it; a fix in another layer of the same stack, named in the ground,
  removed it; or a Canon entry, cited by id, answers it. Doubt keeps it a card.
- An acceptance a Canon ruling already covers is never an item. The sheet's `summary` cites it once,
  with the entry id.
- A sheet with no card whose every acceptance is accounted to a Canon ruling reads the Canon line:
  "Checked against the PR body's What we're accepting: every acceptance it lists is covered by a Canon
  ruling", with the ids. It is not the nothing-to-accept line, which is for a body that lists none.
- An item is only for a call that passes Test 2 (showrunner duty 5 in `skills/showrunner/SKILL.md`),
  and it names its ground as `skills/showrunner/reference/owner-decisions.md` § The filter says.
- An acceptance no Canon ruling covers that carries its own consequence for the owner to weigh is
  its own Accept item, with a short title and a short `ifLeft`: for example a change near access or
  identity, a cost or CI-time trade, a shift in what gets tested where, or an advisor craft call the
  owner can veto.
- Only routine notes with nothing to weigh fold into one "What you're accepting" item with a single
  Accept: size against the estimate, "tests only, no app change", a heads-up about something the
  owner already ruled. Doubt keeps a disclosure its own item. The fold gives its `ifLeft` as a list,
  one short line per note, and the page shows it as a bulleted list, never one paragraph (the list
  shape is in `lib/pr_sheet.py`'s docstring). Neither the fold nor these Accept items are calls, so
  the item bar above does not apply to them.
- Every acceptance a covered PR body lists is accounted for exactly once in the input's `accounting`,
  keyed by the bullet id the build names. An acceptance is accounted for as its own Accept item
  (`item`), as one line of the fold (`fold` with `line`), as the leftover card it restates
  (`leftover`), or as the Canon entry the summary cites (`canon`). No body bullet becomes a card on
  its own. The build refuses a sheet that leaves one out, counts one twice, or points at an item,
  fold line, leftover or Canon id that is not there, and each refusal names the bullet. A first build
  with no `accounting` lists every bullet's id. The accounting covers only what the body lists
  under What we're accepting, above the build record; a harmless deviation listed only in the build
  record's degradations needs no card, and a costly one, listed there and under What we're
  accepting, cannot be left off. The build also refuses a body whose `[costly]` or unlabelled
  degradation bullet has no line under What we're accepting, naming the bullet; a `[harmless]` one
  never needs one.
- A collector item that concerns this PR is its own card, from the input's `collectorItems`. It is never
  folded into the "What you're accepting" item and never only mentioned there by number. The builder
  refuses an option-less card whose text sends the owner to a list item ("decision item 1435", "item 1435
  on your list", a collector number) instead of carrying that decision's options. It is a best-effort
  pattern scan, so the rule binds the advisor whether or not the scan catches a wording.

Each item shows, in this order, its kind, its title, what happens if it is left, its options with what
each means, the recommendation, the answer buttons and a note box. Every item can be answered with its
note left empty.

- An item with a real choice offers its options and **Something else**.
- A leftover shows, in order, its kind, its title, **Why it's yours**, **What happened**, **If left**,
  its options each with this leftover's consequence, the recommendation, the answer buttons and the note
  box. The advisor writes the spine in its `leftovers` input (`skills/showrunner/reference/owner-decisions.md`
  § The per-item spine): `why`, `context`, an optional `ifLeft` when the reviewer's text is no longer
  true, `options` as the three leftover options (Keep it, Fix in a follow-up, Fix before merge) with
  their consequences for this finding, or `"none"` when nothing is left to decide, and a recommendation
  whose reason names the why and the cost. The input's exact shape is in `lib/pr_sheet.py`'s docstring.
- A collector card shows, in order, its kind (naming the collector number), its title, **Why it's yours**,
  **What happened**, **If left**, its lettered options (each label shown as `a. …`), the recommendation
  naming its letter, the answer buttons and the note box. The input's exact shape is in `lib/pr_sheet.py`'s
  docstring.
- An item with no real choice offers **Accept** and **Discuss** and shows no options list.
- When the merge closes a spec's last open piece, the spec's closure receipt is one of the items.

### The four answer patterns

No PR sheet offers an answer button outside these four:

- Pick: an item with a real choice. One of its options, or Something else.
- Agree: an item with no real choice. Accept is the yes-word.
- Check: a walk stop, answered Works (Looks right on a look stop), Problem or Skip. A Problem then asks
  for a fix choice. The answers each kind of stop offers, and their order, come from
  `$defs/walkAnswersByKind` in `sheet.schema.json`, their one home; their labels come from `sheet-words.json`.
- Sign-off: the merge verdict, Merge or Not yet.

Discovery's sheets use agree (Aligned), pick and sign-off (Approve), unchanged. The sheets for a PR, a
stack and the index differ from them in four things: the answer buttons, the merge verdict, the zoom
buttons (−, +, Fit) on an opened picture, and a question that blocks work on the index, whose first answer
counts at once. Everything else is as the rest of this doc says: taps save as drafts, the last tap is the
answer, and a failed save, a picture that cannot load and a shared sheet behave as described there.

### The merge verdict

The verdict is "Merge #<number>" ("Merge stack #<number>" on a stack) and Not yet, with a note. It saves
at `verdict/<digest>` exactly as a final sheet's verdict does. Every answer save on a PR sheet or a stack
sheet carries a fresh `revision` (`$defs/answer`), and a Merge records `covers` (`$defs/verdict`), one
`answers/<card id>@<revision>` for each card: the answers it was given for. A Merge whose covered answers
have since changed, from any page, is not a Merge, and the verdict reopens cleared.

It is locked until every item above it is accepted. The Merge button then says it is locked, it cannot
be tapped, and a line says when it unlocks and how many items are accepted so far. When an accepted answer
was saved without a revision, a line says so and names those cards by their questions.

An item counts as accepted only when its saved answer is Accept, or an option that does not send the PR
back, and that answer shows Saved. A save in flight, failed or stalled keeps the verdict locked. An
answer that sends the PR back never counts.

- Choosing Fix before merge, or any option that sends the PR back, replaces the verdict with a message
  that the PR goes back for that fix and returns with a new sheet, with nothing to answer here.
- A walk stop answered Problem with no saved fix choice keeps the verdict locked. Fix before merge on a stop
  replaces the verdict with the same send-back message. Stops not walked never lock the verdict, which says
  how many are not walked, optional stops not counted.
- Un-accepting an item after a Merge clears the Merge, saved as null with the note kept. A Merge
  restored onto a sheet that is locked is cleared the same way.

### Decided for you

A left-for-owner finding the advisor re-graded as craft at vet is no card, and neither is one whose real
consequence needs no card of its own on one of three grounds: another card on the same sheet
carries it; a fix in another layer of the same stack, named in the ground, removed it; or a Canon
entry, cited by id, answers it. Each is an entry of the sheet's
**Decided for you** list (`prSheet.decidedForYou`, `$defs/decided` in `sheet.schema.json`). The list sits
below the cards, unfolded, and is left out when it is empty. Each entry shows its title, its ground, its
reason and one control, **Make this mine**. An entry never counts toward the accepted items. The advisor
writes each one in the `craftDeterminations` key of its input, whose shape is in the docstring of
`lib/pr_sheet.py`. The list's words are in the `pr` block of `sheet-words.json`.

A carried sheet keeps the earlier sheet's entries. The builder refuses a carry that adds a determination,
changes one, or turns one back into a card, because each of those changes what the owner decides.

**Make this mine** saves an ordinary answer at `answers/<entry id>`, with `optionId` `make-this-mine` and
the note, and clearing it saves a null answer. Any other document stored there counts as taken back, so a
malformed one never hides a take-back. While any entry is taken back, or may still be stored as taken back,
Merge is locked and a held Merge is cleared. `pr_state` reads that PR as Needs you.

After "done", a saved take-back sends the finding back to the owner as a card on a new, unsigned sheet, as
`skills/showrunner/reference/owner-decisions.md` § Reading a PR sheet says.

### Pictures on the walk

The builder copies each walk picture into `pictures/` beside `sheet.json` and lists the paths in its
result; publish each listed path in `files`. A picture it could not copy shows as missing and links nowhere.

### A changed PR

A sheet republished for a new commit carries `previousCommit` and shows a heading and note saying the PR changed. An item's id
stays the same while its finding and its shown content do, so answers to unchanged items are kept. The
verdict starts over, because its digest is new. That is a material republish.

### A carried PR

When the PR moved but the move is not material (a bring-current from the base branch with no conflict,
say), the advisor gives the builder `carriedForward` in its input: the earlier sheet's path (`fromSheet`),
each covered PR's new head (`heads`), the `date`, what `moved`, and `whyNotMaterial`. The built sheet then
carries `previousCommit` (the earlier sheet's commit) and `prSheet.carriedForward`, whose `sheets` lists
the digest of the earlier sheet and then the digests that one carried, newest first. The sheet shows a
dated Carried forward box in place of the changed box, and the answers to unchanged items are kept as for
any republish.

Its verdict is read through that chain, by one rule that the page and the index's row both follow: take the
first digest, from the sheet's own and then `sheets` in order, under which the store holds any verdict
document. That document is the verdict only if it fits `$defs/verdict` and its `sheet` equals the digest it
was found under; if not there is no verdict, and the older digests are not tried. A Merge found that way
stands as it would on its own sheet: every item accepted, no walk Problem left, and `covers` equal to the
answers now. So a Merge saved on an earlier revision keeps standing on the carried sheet until the owner
changes an answer, and a Not yet or a cleared verdict saved on any revision in the chain ends it. Every
write goes to the sheet's own digest: tapping Merge again, or changing an answer under a carried Merge,
saves a null there first. A sheet with `previousCommit` alone has no chain and reads only its own digest.

### How a PR sheet's answers come back

The session reads a PR sheet's answers and its verdict together only after the owner says "done" in the
chat. Nothing is merged, sent back, filed or recorded from a sheet before then.

A saved Merge together with "done" is the owner's word to merge that PR. Neither alone is, and a saved
Not yet, or no verdict, with "done" is not. A Merge counts only when its `covers` names exactly the
`answers/<card id>@<revision>` of every card as the store holds them now; an answer saved again from any
page has a new `revision`, so the Merge no longer covers it and is not a Merge.

The walk's results are stored at `walk/<stop key>` (`$defs/walkAnswer`), the key being the stop's `key` in `sheet.json`, and read with the answers and
verdict after "done". A stop's `shots` are asset ids shown at `/_blob/<id>`. A Fix in a follow-up on a
stop is the owner's word to file that follow-up.

A note that disagrees with its answer (Keep it with a note that says to fix it first) leaves the item
open, and the session asks which one stands.

A saved take-back on a Decided for you entry is read with the answers after "done", and it keeps the PR
from merging on that sheet.

## The index

The index (`kind` is `index`) lists every PR that waits on the owner, so the owner has one place to see what
needs them. It carries the `index` block (`$defs/index` in `sheet.schema.json`); every word the page shows
on it is in the `index` block of `sheet-words.json`.

### What it shows

- On top, the questions that block work. They are the advisor's first batch of questions, the ones that
  block its next step, and each is a card with its context, any pictures, its options, the recommendation
  and a note box, answered with the pick pattern. When none is left the index says "Nothing is blocking
  work right now."
- Below, every PR with a sheet, under **Needs you**, **Being fixed** or **Ready**; a group with no PR is
  left out. A row names the PR (or the stack), then its counts: how many items are accepted, how many walk
  stops are walked, and on Needs you where the PR comes in the merge order. The builder composes that line once
  into the row's `caption`, and the page and the chat prose show it as it is. A row opens the PR's sheet.
- A line at the end tells the owner to say "done" in the chat once every sheet they meant to answer is
  saved.

### How it is built

The advisor builds the data file from its own input and each PR's published sheet and store:

```
python3 -B "${CLAUDE_PLUGIN_ROOT}/lib/pr_sheet.py" index --input <file> [--answers <file>] --out sheet.json
```

The shape of the input and of a store dump is defined in the docstring of `lib/pr_sheet.py`, and nowhere
else. `--answers` holds the answers to the index's own questions; a question it answers is left out, so an
answered question leaves the index when the advisor rebuilds it.

### When a PR is Being fixed or Ready

A PR is **Being fixed** when a saved answer sends it back for a fix: an option that sends the PR back, or
a walk Problem whose fix is before merge. Otherwise it is **Ready** when its Merge verdict stands: saved on
the sheet's current revision, with every item accepted, no walk Problem left without a follow-up fix, and
`covers` naming exactly the answers the store holds now. Every other PR is under **Needs you**, and a taken-back Decided for you entry keeps a PR there. One rule,
`pr_state` in `lib/pr_sheet.py`, decides this.

A sheet republished for a fixed PR keeps its link, so the PR's row keeps opening the current sheet.

### Publishing the index

As § Publishing a sheet says, with no `assets`: the index has no screenshots to add.

## How answers come back

A tap saves at once into the sheet's own store, and the owner can change it; tapping the picked
answer again clears it, and the cleared answer (null) saves the same way, with the note kept. The
last tap counts. Each card's stored document has the shape
`sheet.schema.json` defines at `$defs/answer`. Anyone but the owner who opens a shared sheet sees it
with the answer controls turned off.

A save that fails says so on the card and offers Try again.

The session that sent the sheet reads every answer together once the owner says in the chat that the
sheet is done, and never acts on a single tap. One exemption: a question that blocks work on the index
(§ The index) counts as soon as the advisor reads its first answer, wherever it came from, without waiting
for "done". When the chat and the index disagree, the advisor asks.

On a final sheet the session reads `answers` and `verdict/<digest>` together, where `<digest>` is the
SHA-256 of the `sheet.json` it published (for example `shasum -a 256 sheet.json`). It reads only that
document and uses it only when its `sheet` equals that digest, so a republished final sheet starts
unsigned because its digest is new. A PR or stack sheet does the same, except that one republished with
`carriedForward` reads the first revision in its chain that has a document (§ A carried PR); a material
republish starts unsigned. A card with no stored answer or a stored answer of null (a
cleared pick), a final sheet with no verdict document, or a verdict of null (a cleared verdict) is
unanswered: the session asks rather than assuming. A saved Approve never counts as approval on its
own; the owner's word in the chat does.

The stored `answer` is `option` or `something-else` on a card with options, and `aligned` or
`discuss` on a card without. On a PR sheet a card without options stores `accept` or `discuss`.

The session reads each stored answer against the card as it is published now:

- An answer the card does not offer now (an Aligned or Discuss saved before the card gained options,
  or an option the card no longer has) is unanswered, and the session asks.
- Discuss and Something else leave the call open for chat, and the session asks.
- The page shows a no-longer-offered answer as unanswered and keeps its note.

A note that disagrees with its answer leaves the call open, and the session asks the owner about it.

Another session can take a sheet over by reading its data file and its store.

## Updating a sheet

Republish to the same link with the changed `sheet.json`, and with the same template and
stylesheet, the page staged again with its title as § Publishing a sheet says. Never fork a second copy of the page: the owner's link must keep pointing at the
current sheet. Answers are keyed by card id, so a republished sheet keeps the answers to its
unchanged cards.

## When the page shows an error

If the page can't trust the data file, it shows a box titled "This sheet can't be shown" and lists
what is wrong, one problem to a line. It draws no cards, so a broken sheet never looks like a
finished one.

The problems name the data file: it (or the schema file) could not be loaded, it isn't valid JSON, or a card is
missing something (the problem names the card's `id`). Fix the data file and republish to the
same link.

## When the host can't show a sheet

Where the host can't show a sheet, the session puts the same cards to the owner as numbered chat
prose, each with its context, options and recommendation, built from the same data file. A PR sheet
and a stack sheet go to the owner as numbered prose the same way. In that prose each walk stop shows its id,
and its answers are written with that id (for example `p1 Works`), so a short chat answer names the stop it answers.

Render the prose with `python3 -B "${CLAUDE_PLUGIN_ROOT}/lib/sheet_prose.py" render --sheet <the data file>`
and paste its output. It runs on a plain Python, with nothing to install. It refuses a data file it
can't trust, and lists what is wrong one problem to a line.
