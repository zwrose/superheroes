# Contents

- [Frame and product](#frame-and-product)
- [Where the design system comes from](#where-the-design-system-comes-from)
- [Publishing on a host that shows HTML artifacts](#publishing-on-a-host-that-shows-html-artifacts)
- [Hosts that cannot show an HTML artifact](#hosts-that-cannot-show-an-html-artifact)
- [Saving the approved build board](#saving-the-approved-build-board)
- [Skipping the board, the board winning, and redraws](#skipping-the-board-the-board-winning-and-redraws)

# Boards

A board is a drawing of the work, made before the spec is written. Step 5 of the skill owns which
boards discovery draws and what they hold. This reference holds how a board is made.

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

A board's design system comes from the project's own design-system files: its tokens,
stylesheets, and components.

Where the project has no design-system files, tell the owner so. Draw in a plain neutral style, and state on the
board that the project has no design system. The theme never stands in for one.

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

## Skipping the board, the board winning, and redraws

Step 5 of the skill owns when a board may be skipped, which wins when the spec and the approved
board disagree, and when a redraw is needed. This reference holds only the file format of a redraw.

Save the files again after a redraw, as in Saving the approved build board.

`board/redraws.md` holds one entry per redraw. Each entry holds:

- the date,
- the ruling, by its Canon entry,
- what changed on the board,
- the board's link,
- `sent: no`.

Mark an entry `sent: yes` once a sheet carries it. Any later discovery session on this spec reads
`redraws.md` first. The board stays the truth.
