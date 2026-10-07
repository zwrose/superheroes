# Contents

- [The three boards](#the-three-boards)
- [What the build board holds](#what-the-build-board-holds)
- [Never less detailed than the chat](#never-less-detailed-than-the-chat)
- [Frame and product](#frame-and-product)
- [Where the design system comes from](#where-the-design-system-comes-from)
- [Claude Design choices in Canon](#claude-design-choices-in-canon)
- [Publishing on a host that shows HTML artifacts](#publishing-on-a-host-that-shows-html-artifacts)
- [Hosts that cannot show an HTML artifact](#hosts-that-cannot-show-an-html-artifact)
- [Saving the approved build board](#saving-the-approved-build-board)
- [Syncing to Claude Design](#syncing-to-claude-design)
- [Skipping the board](#skipping-the-board)
- [The board wins](#the-board-wins)
- [Redraws after approval](#redraws-after-approval)

# Boards

A board is a drawing of the work, made before the spec is written. Discovery draws three boards
in order. The owner comments and rules on each one before the next.

## The three boards

1. The journeys or flows. This board shows how a person moves through the work.
2. The open choices, drawn side by side. Each option is drawn, so the owner compares them by
   looking.
3. The build board. It holds the settled design.

Any visual that communicates counts: screens, storyboards, flow charts, diagrams.

## What the build board holds

- It holds only the settled design. No open alternative appears on it.
- It uses the product's real wording. Placeholder copy never appears on it.
- Everything that can reasonably be drawn is drawn. Prose does not stand in for a drawing.

## Never less detailed than the chat

A board is the higher-resolution record of the work. Anything the chat settled appears on the
board.

## Frame and product

Every board is an HTML page. It has two layers.

The frame is the board's own titles, captions, notes, and marks. The frame uses the plugin's
theme, loaded from `theme/comic-panel.css`. The board loads that file and never restates a theme
colour, font, or part value.

The product is what the board draws. It uses the project's design system, wrapped in an element
with the class `sh-product`. Inside that element the theme sets nothing.

The stylesheet's own containment rules carry into every board:

- Frame text goes in its own child element. Bare text never sits beside the `sh-product`
  boundary.
- Never put `sh-product` inside a part class that sets text: button, label, tag, pill, badge,
  reviewer, step, or app bar.
- A card or a box sets no text, so it is a safe frame.
- The paper ground of the theme shows behind a transparent drawing. Give the drawing its own
  ground when it needs one.

The skeleton of a board page:

```html
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Watering reminders build board</title>
<link rel="stylesheet" href="comic-panel.css">
<link rel="stylesheet" href="design-system/tokens.css">
<link rel="stylesheet" href="design-system/components.css">
<style>
  body { background: var(--sh-paper); margin: 0; }
  .board { display: grid; gap: 20px; padding-inline: 16px; padding-block: 24px; }
</style>
<div class="sh-theme">
  <div class="board">
    <div class="sh-card">
      <h2 class="sh-heading">Screen title</h2>
      <p class="sh-label">Screen 1 of 4</p>
      <div class="sh-product">
        <!-- the product's own markup, in the project's own classes -->
      </div>
      <p class="sh-caption">What the owner sees here, and when.</p>
    </div>
  </div>
</div>
```

The two design-system links are examples. Link the files the project has. The page has no doctype and no `html`, `head` or `body` tags, like the review template, because the Artifact host wraps a published page in its own document, and the same file still opens in a browser from a folder. The page's own `style` block holds layout only, such as spacing and grid, and never a colour, font or part value. The title is a short name for the board, with no colon and no explanation after it.

## Where the design system comes from

Where the project uses Claude Design, its boards' design system comes from Claude Design, whether
or not syncing is on.

Otherwise it comes from the project's own design-system files: its tokens, stylesheets, and
components.

Where the project has neither, tell the owner so. Draw in a plain neutral style, and state on the
board that the project has no design system. The theme never stands in for one.

## Claude Design choices in Canon

Two choices belong to the owner as standing rulings. The first is whether the project uses Claude
Design. The second is whether approved boards sync to it.

Read both from Canon, as `rubric/canon-contract.md` says in its section Reading Canon. Where
Canon holds no ruling on either, ask the owner once, before the first board. Record the answer in
Canon, as that file says in its section Writing a ruling. Never assume an answer either way.

Syncing stays the project's choice.

## Publishing on a host that shows HTML artifacts

Claude Code is such a host. Its Artifact tool publishes only files under the working directory or
the session's scratchpad. This recipe mirrors the one in `theme/review-template.md`, in its
section Publishing a sheet.

1. Make one folder under the session's scratchpad for each board.
2. Copy `theme/comic-panel.css` into the folder, unchanged.
3. Copy the design-system files the board loads into the folder, at the relative paths the page
   links.
4. Write the board page into the folder.
5. Publish the page, with the stylesheet and each design-system file as supporting files. The page
   then loads them by relative path.

The shape of the publish call:

```
file_path = <staged folder>/build-board.html
files     = {"comic-panel.css": "<staged comic-panel.css>",
             "design-system/tokens.css": "<staged tokens.css>",
             "design-system/components.css": "<staged components.css>"}
```

When a board changes, republish it to the same link. Never fork a second copy. Keep each board's
link.

## Hosts that cannot show an HTML artifact

Codex is such a host. The board is the local HTML file the project keeps, in the work item's
`board/` folder. Put `comic-panel.css` and the design-system files beside it. The owner opens the
file in a browser. The rest of the flow is the same.

## Saving the approved build board

When the owner approves the build board, save it as files the project controls, kept with its
spec. They live in the work-item folder, under `board/`.

Find the work-item folder the way Exit B in the skill does. Resolve the spec path with
`definition_doc.py resolve-write --doc spec`, and take the directory of the path it reports. That
directory is correct in both storage modes. Never hardcode a repo path. Guard the call as Exit B
does. When `resolve-write` fails, stop and say so. Do not save the board anywhere else.

The saved set:

- `board/build-board.html`, the approved page.
- `board/comic-panel.css`, copied unchanged, so the file opens on its own.
- The design-system files the page loads.
- `board/README.md`, naming the board's link, the date the owner approved it, and which version
  was approved.

The saved page loads its stylesheets by relative path, so it opens in a browser from the folder.

## Syncing to Claude Design

Where the project has turned syncing on, the approved build board syncs to Claude Design once, at
approval, through the host's Claude Design path. It does not sync before approval. It does not
sync again on later edits.

Where the host has no Claude Design path, tell the owner that the sync did not happen and why.
Never claim a sync that did not run.

## Skipping the board

A piece of work may skip the board when it is small and has nothing to draw. Both conditions must
hold. A small screen or a small flow still gets a board.

Say so at the framing. The spec is then written from the framing and the rulings.

## The board wins

Where the spec and the approved board disagree, the board wins. Correct the spec in the same pass
that finds the disagreement.

The correction is a change to the spec like any other. The checks run again on the changed parts.

## Redraws after approval

A ruling can change something an approved board shows. When one does, redraw the affected part and
republish it to the same link. Save the files again, as in Saving the approved build board.

Record the redraw in `board/redraws.md`, one entry per redraw. Each entry holds:

- the date,
- the ruling, by its Canon entry,
- what changed on the board,
- the board's link,
- `sent: no`.

The owner's next sheet shows every entry still marked `sent: no`. Mark an entry `sent: yes` once a
sheet carries it.

Any later discovery session on this spec reads `redraws.md` first. The board stays the truth.
