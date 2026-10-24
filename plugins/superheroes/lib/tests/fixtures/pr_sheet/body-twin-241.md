Closes #241.

## What's changing, and why

Twin A moves the shared parser into its own module so the stack's top PR can reuse it.

## What we're accepting

- **The parser keeps its old name.** Callers that import it by the old path still work, through a one-line re-export.
- **The cache is cleared on upgrade.** Cached parses from the old format are dropped, in this order:
  1. The on-disk cache is deleted at start.
  2. The first run after that is slower by about a second.
<!-- a note for the author, not an acceptance -->
- **The error text changed.** A bad file now reads as shown here, so a script that matched the old words must change:
  ```
  ## Not a heading
  ```

## How to see it

Run the parser on any file. It prints the parsed tree.

## Advisor vet
<!-- superheroes:advisor-vet -->
**Verdict: READY** · 1111111111111111111111111111111111111111

**What was checked.** The re-export and the cache clearing, by breaking each on purpose.
