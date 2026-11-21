# Upgrade notes waiting for a release

Each file here is one change's upgrade note, named for its issue number (`<issue>.md`, or
`<issue>-<slug>.md`). `TRANSITION.md`'s header says when a change owes one and the shape it takes.
The release doc pass assembles every file here into `TRANSITION.md` and removes it (`RELEASING.md`
§ Release day). This README is never a note.

A note file looks like this:

````
### Before you upgrade

- **After switching.** **What a consumer sees, in one sentence.** See [The note's heading](#the-notes-heading).

### The note's heading

- **The change.** …
- Replacement. …
````
