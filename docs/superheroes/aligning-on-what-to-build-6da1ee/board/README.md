# The approved board for the spec-alignment specs

Source: https://claude.ai/artifact/FDiMfa95mWjEPCaT64d5pf (Design canvas, owned by the -three account),
exported 2026-10-05 from its live version 1791170301-8b22 (version 12).

- **Entry:** `project/canvas.json` is the index (artboard titles, layout, order).
  `project/Main.dc.html` ("Start here") is the first artboard. Each `.dc.html` is one artboard's whole
  source and opens in a browser on its own. The canvas runtime (`support.js`) isn't included and isn't
  needed to read them. Fonts load from Google Fonts.
- **Which spec uses which artboards:**
  - aligning-on-what-to-build: Main, Flow, ReviewCycle, SourceTags, Line.
  - the-review-surface: Theme, ReviewTemplate, TapSheetItem, TapSheetFinal, TapSheetDesktop, TapSheetZoom.

## Approved version versus this export

The owner approved round 3 plus ruling 38 (version 11, 2026-10-03; ruling 39). Ruling 38 removed the
image carousel on TapSheetZoom. After approval, ruling 45 required redraws when later rulings changed
the board. One redraw happened (version 12, 2026-10-04), wording only, for rulings 60 and 61:
- **Line:** "hand back" became "cede": the sorting diagram's "Did you cede it?", the worked example,
  "How a project adjusts the line", and the SVG aria-label.
- **SourceTags:** Canon is `canon.md` "where the project keeps its specs, and every ruling is committed at
  once to the session's branch". "Hand-backs" became "Ceded calls". "Rulings" became "Decisions … go-words stay where you
  give them".
- **Main:** "your hand-backs" became "your ceded calls".

Nothing else changed. Main's status text ("Nothing here is approved yet", "Still open for you") is the
round-3 snapshot as the owner approved it, not the current state.
