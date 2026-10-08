---
superheroes: doc
schemaVersion: 1
docType: spec
workItem: the-review-surface-d59417
issue: null
size: medium
status: approved
approved: "2026-10-04"
gates: {review: passed}
producedBy: "the-architect@0.33.0"
created: "2026-10-03"
updated: "2026-10-07"
---
# The review surface

## How to read this spec

Every statement ends with its source in plain text, using the same sources as its sibling spec,
`aligning-on-what-to-build-6da1ee`: **ruling N** (the discovery handoff,
`docs/superheroes/discovery-notes/spec-alignment/HANDOFF.md`), **board · <artboard>** (the approved
board, https://claude.ai/artifact/FDiMfa95mWjEPCaT64d5pf, round 3 plus ruling 38), **framing**, and
**craft** (the author's choice, recorded for the owner's veto). (source: rulings 39, 41)

## Purpose

When superheroes needs the owner's calls, the owner should be able to answer them quickly, on a
phone or a desktop, from one familiar card that shows everything a call needs, including its
pictures. This spec gives the plugin one review template, a light web app rather than a document,
and one visual theme it ships for every board, sheet and review page. (source: rulings 20, 31;
board round 1 comments)

## Who it's for

- As a project owner, I want every review to use the same card, so I can answer calls quickly
  without learning a new screen each time. (source: ruling 34)
- As that owner, I want to see the picture behind a call and zoom into it on my phone, so I can
  decide without opening anything else. (source: ruling 31)
- As a superheroes session with calls for the owner, I want a ready template, so the owner gets a
  familiar sheet instead of a wall of chat. (source: ruling 31)

## Functional requirements

### The template and who uses it

**FR-1.** The plugin shall ship one review template, a light web app that works on a phone first
and on a desktop too. (source: ruling 31; board round 1 comments; board · One review template)

**FR-2.** Discovery's remainder sheets and its final sheet shall use the template, built in.
(source: ruling 31)

**FR-3.** Any session may use the template when it has calls for the owner, and the owner may ask
for it; no other review shall be required to use it. (source: ruling 31, amended)
  - *Acceptance (rule):* the plugin names no expected use beyond discovery's sheets. (source: as its requirement)

**FR-4.** When the owner answers a card, the sheet shall save the answer at once as a draft the
owner can change, and the last tap counts. (source: board · Spec review · phone; ruling 49)
  - *Acceptance (Given-When-Then):* Given an owner who answers two cards and closes the sheet,
    when they reopen it, then both answers are still there. (source: board · Spec review · phone)

**FR-4a.** The session that sent a sheet shall read its answers together, once the owner tells it
the sheet is done, and shall never act on a single tap. (source: ruling 49; board · One review
template)
  - *Acceptance (rule):* no extra submission machinery is built for this; a saved draft plus the
    owner's word is enough. (source: ruling 49)
  - *Acceptance (rule):* on a final sheet too, the owner's word in the chat is that word; no
    button on the sheet stands in for it (FR-18). (source: ruling 49; owner's comment on the
    final-sheet sample, 2026-10-07)

### The card

**FR-5.** Every card except a final sheet's last card (FR-17) shall have the same parts, in this order: the kind of call; the question in
one line, in the owner's words where possible; the context, in sections the sending session titles
and writes in its own words, as paragraphs and bulleted lists (what is true now, what accepting
it means, why it needs the owner: whatever this call needs), quoting the exact text the call is
about where there is one; images, when the call has
relevant ones; options, when there are real ones, each with its plain consequence; a one-line
recommendation with its reason; the owner's answer; a note. (source: ruling 34; board · One
review template; the owner's comment on the merge review sheet, 2026-10-07, Amendment 3)
  - *Acceptance (rule):* the template fixes no context headings and requires no section; a card
    whose call has no exact text shows no empty quote. (source: as its requirement)

**FR-6.** Every card except a final sheet's last card (FR-17) shall offer answers that match the
call: a card with options offers one button per option and Something else, and nothing more; a card
with no options offers Aligned and Discuss. (source: ruling 34; the owner's comment on the merge
review sheet, 2026-10-07, Amendment 3)
  - *Acceptance (rule):* a pick chooses that option; Something else leaves the call open for chat,
    with the note as the place to say what instead; Aligned agrees with the card's recommendation,
    or with the statement when there is no recommendation; Discuss leaves the call open for chat.
    (source: ruling 48; Amendment 3)
  - *Acceptance (rule):* when the owner's note disagrees with their answer, the session treats the
    card as open for chat and asks. (source: ruling 48)
  - *Acceptance (rule):* no review adds its own answer buttons. (source: ruling 34)
  - *Acceptance (rule):* a final sheet's last card offers Approve and Not yet instead. (source:
    board · One review template)

**FR-7.** A card for a gap the reviewer found, a statement with no source, or a finding the review
didn't settle shall carry a red warning badge; other cards, except a final sheet's last card (FR-17), shall carry a plain badge naming the kind of
call. (source: board · One
review template; board · The superheroes theme)

**FR-8.** When a call has images that bear on it (a board frame, a screenshot, a diagram), its card
shall show them, in every review. (source: ruling 31)

### Images

**FR-9.** When the owner taps an image on a card, the sheet shall open it on its own, large, with a
Close control that returns to the card. (source: ruling 31; board · Image zoom · phone)

**FR-10.** While an image is open, the owner shall be able to pinch or double-tap to zoom and drag
to look around. (source: ruling 31; board · Image zoom · phone)

**FR-11.** The image view shall not move between images by swiping sideways; each image opens on
its own. (source: ruling 38)

### Sheets

**FR-12.** A sheet shall show the review's name in a yellow app bar, and how many items are
answered out of the total; the bar scrolls away with the page rather than staying pinned in view.
(source: board · Spec review · phone; board · Final sheet · phone; board · The superheroes theme;
the owner's comment on the merge review sheet, 2026-10-07, Amendment 3)

**FR-13.** On a phone, a remainder sheet shall fold answered items into one row showing how many
are settled (Aligned or an option picked) and how many are left open for chat (Discuss or Something
else), show the open item in full, and list each other open item
as a short row with its state. (source: board · Spec review · phone)

**FR-14.** On a desktop, a sheet shall list every item with its state beside the open card, with
Previous and Next controls. (source: board · Spec review · desktop)

**FR-15.** A remainder sheet shall say why it holds only these items: how many rounds the review
ran, how many things it fixed itself, and that everything else traces to the owner's board or
rulings, apart from any finding marked as not settled by the review. (source: board · Spec review ·
desktop; ruling 16)

**FR-16.** The owner shall be able to leave a sheet unfinished and come back to it; every answer
is already saved, so leaving needs no button. (source: board · Spec review · phone; owner's
comment on the review-sheet sample, 2026-10-07)

**FR-17.** A final sheet shall open with how the spec got there (the review rounds, the fixes, the
vet), list the declined findings folded away, show the vet's calls as rows with their answers,
and end with a last card asking "Approve the spec?" that says every statement traces to the
owner's board (where there is one), framing, rulings, answers or craft recorded for veto, and,
where there is an approved board, that it is saved with it, and offers Approve and Not yet, and a note. (source: board · Final sheet · phone; ruling 16; framing)
  - *Acceptance (rule):* below the last card, the sheet says what happens next: the advisor adds
    the breakdown to the same PR (or, where the project keeps specs outside the repo or gitignored,
    to the spec where it's kept) and vets it, then one merge word covers both. (source: board ·
    Final sheet · phone; ruling 47; craft, for your veto: gitignored specs treated the same way)

**FR-18.** A final sheet's verdict (Approve or Not yet) and its note shall save as the owner taps
and types, like any answer, and shall not count as approval on their own. Below the last card,
the sheet shall say plainly what to do next: once every answer shows it is saved, go back to the
chat and say you're done, and the session then reads the answers and the verdict together. The sheet has no "Send verdict" button.
(source: board · Final sheet · phone; owner's note on the final sheet, 2026-10-05; owner's
comment on the final-sheet sample, 2026-10-07)

### The theme

**FR-19.** The plugin shall ship one visual theme, Comic panel, for its own pages: every sheet, every
review page, and the frame and labels of every board; a board draws the product itself in the
project's design system. (source: rulings 2, 20, 28; advisor vet round 1, F10)

**FR-20.** Each theme colour shall have one job: paper (#FFF8E7) for the ground; ink (#111111) for
text, outlines, shadows and arrows; hero blue (#1B4FD8) for the owner's moments and the main
action; alarm red (#D7263D) for warnings; highlight yellow (#FFC93C) for app bars, what's new and
standing rulings; reviewer green (#0F7A4F on #E3F4EA) for independent reviewers only. (source:
board · The superheroes theme)

**FR-21.** The theme shall set headings in Bricolage Grotesque 800, body text in Atkinson
Hyperlegible 400 and 700, labels in the body font in tracked capitals, and tags and Canon entries
in IBM Plex Mono. (source: board · The superheroes theme)

**FR-22.** The theme's parts shall follow its drawn rules: 3px ink outlines (2px on small parts);
offset shadows, never blurred (6px on cards, 4px on small boxes, 3px on buttons); corners of 6 to
14px; no gradients and no emoji. (source: board · The superheroes theme)

## When things go wrong (significant unhappy paths)

**UFR-1.** If a sheet can't be shown on the owner's host, then the session shall put the same
items to the owner as numbered chat prose, each with its context, options and recommendation.
(source: framing)

**UFR-2.** If the owner's connection drops after they tap an answer, then the sheet shall make
clear which answers were saved. (source: ruling 51)
  - *Acceptance:* Given a failed save, when the owner looks at the card, then it shows that the
    answer wasn't saved and lets them try again. (source: as its requirement)

**UFR-3.** If an image can't load, then the card shall still show its question, context and
answers, and say the image is missing. (source: ruling 52)

**UFR-4.** If someone other than the owner opens a sheet the owner shared, then they shall see it
but shall not be able to answer. (source: ruling 50)

## Non-functional requirements

- **Readability:** all text meets a 4.5 to 1 contrast ratio; white text sits only on blue, red or
  ink. (source: board · The superheroes theme)
- **Privacy:** a sheet is private to the owner by default; the owner may share it to show
  someone. (source: ruling 50)
- **Touch:** every control is at least 44px tall. (source: board · The superheroes theme)
- **Telling things apart:** colours that must be told apart also differ in lightness. (source:
  board · The superheroes theme)

## UI / UX

The approved board is the design: https://claude.ai/artifact/FDiMfa95mWjEPCaT64d5pf, artboards
"The superheroes theme · Comic panel", "One review template", "Spec review · phone", "Final
sheet · phone", "Spec review · desktop" and "Image zoom · phone". (source: ruling 39)

## Definition of done / success

The owner answers a discovery's remainder sheet and final sheet on a phone, sees and zooms the
images behind each call, and the answers reach the session; any other session that asks for the
template produces a sheet with the same card and theme. (source: rulings 31, 34)

## Assumptions & dependencies

- Discovery's flow (`aligning-on-what-to-build-6da1ee`) decides what goes on each sheet; this
  spec decides how a sheet looks and behaves. (source: ruling 40)

## Out of scope

- What goes on a sheet and when it is sent: the sibling spec. (source: ruling 40)
- A dark variant or other themes: later, if wanted. (source: ruling 28; board · The superheroes
  theme)
- Requiring PR walks, merge reviews or other reviews to use the template. (source: ruling 31)

## Glossary

- **Card:** one call for the owner on a sheet, with the parts in FR-5. (source: ruling 34)
- **Sheet:** a set of cards sent to the owner at one time. (source: ruling 8)

## Delivery

**Delivered, accepted in full by the owner on 2026-10-07** (collector #695 item 46 = a, in chat: "46 a, you can merge the stack"; option a read "keep everything and accept Spec B as delivered"). The acceptance rests on the closure receipt carried at PR #1659's vet 404 and amended at vets 409 and 410. C7 shipped as stack #1642, and C8 as stack #1650, with this spec's Amendments 1 and 2 below. Every one of the spec's criteria as it stood after Amendments 1 and 2 is delivered; none is deferred or declined. Amendment 3 (2026-10-07) changes FR-5, FR-6, FR-12 and FR-13 after that acceptance; those changes are delivered by C10 (issue #1673, PR #1676, merged 2026-10-08 as the top layer of stack #1670). **Amendment 3 was accepted in full by the owner on 2026-10-08** (collector #695 item 56 = a), on the closure receipt at PR #1676's vet 418, re-pinned at vet 419. Before the merge, the owner's spot-check added three small sheet fixes inside C10's surface (scroll to top on a card change, the note box kept above the keyboard, clickable links); they change no criterion.

## Amendments

- **2026-10-07 (owner-stamped, substantive):** retired the "Done for now" button. Every answer
  already saves as it is tapped and comes back when the sheet reopens, so leaving a sheet needs no
  button; the owner, live-checking the sample sheet, found the button and its status page
  unnecessary (collector #695 item 47, ruled "a" in chat). Sections touched: FR-16.
- **2026-10-07 (owner-stamped, substantive):** retired the "Send verdict" button. A sheet cannot
  reach the chat session that sent it, so the button looked like it set Claude working when it did
  not. A final sheet's verdict and note now save like any answer, the sheet says plainly to go back
  to the chat and say you're done, and the owner's word in the chat is what the session reads
  (collector #695 item 48, ruled "a" in chat). Sections touched: FR-4a, FR-18.
- **2026-10-07 (owner-stamped, substantive):** the cards fit how the owner reads them. A card with
  options offers one button per option and Something else, and Aligned and Discuss only appear on
  cards with no options; the app bar scrolls away instead of staying pinned; and a card's context
  is written by the sending session in its own sections rather than forced into fixed ones. The
  owner, after completing the merge review sheet, found the extra buttons confusing, the pinned
  bar in the way, and the context "forced into the template" when the owner wanted the "what you're
  accepting" explanations he gets in chat (collector #695 item 54, ruled "a" in chat; built by
  issue #1673). Sections touched: FR-5, FR-6, FR-12, FR-13, Coverage (Wording & tone).

## Coverage

The author's audit record. Where a row names a requirement, that requirement carries the source;
where it gives a reason instead, the reason is the author's, recorded for the owner's veto.
(source: craft)

| Area | Disposition | Show-it? | Where / why |
| --- | --- | --- | --- |
| Empty & first-run | Defer-to-build | No | A sheet is only sent with items on it (source: craft) |
| Invalid & malformed input | N-A | — | The only typed input is an optional note (source: craft) |
| Boundaries & limits | Defer-to-build | No | Long notes and many images: the build's call (source: craft) |
| Errors & failures | Specify | Yes | UFR-1, UFR-2, UFR-3 (source: as the requirement named) |
| Access & permissions | Specify | No | NFR privacy; UFR-4 shared sheets are view-only (source: as the requirement named) |
| Duplicates & double-actions | Specify | No | FR-4 last tap counts; FR-4a the session reads answers once, together (source: as the requirement named) |
| Conflicting / simultaneous use | N-A | — | One owner answers each sheet (source: craft) |
| Misuse & abuse | N-A | — | Malicious input is outside the plugin's threat model (source: craft) |
| Reach (i18n / a11y) | Specify | Yes | Readability, touch and colour requirements above (source: craft) |
| Wording & tone | Specify | Yes | Button words Aligned, Discuss, Something else, Approve, Not yet (source: craft; Done for now and Send verdict retired, Amendments 1 and 2; Something else added, Amendment 3) |
| Workflow shape | Specify | Yes | FR-12 to FR-18 (source: as the requirement named) |
| Placement & prominence | Specify | Yes | FR-5 card order; FR-12 app bar (source: as the requirement named) |
| Limits & defaults | N-A | — | No limits the owner sets (source: craft) |
| Tier & access boundaries | N-A | — | No tiers (source: craft) |
| Visibility & disclosure | Specify | Yes | FR-15 why only these; FR-17 declines folded (source: as the requirement named) |
