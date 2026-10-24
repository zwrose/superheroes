Closes #242.

## What's changing, and why

Twin B uses the parser from Twin A in the report step.

## What we're accepting

- **The report step reads files twice.** Once to count lines and once to parse them; a large file takes about twice as long.
- A plain bullet with no bold lead: the report's title line now names the file.

## How to see it

Run the report on any file.

## Advisor vet
<!-- superheroes:advisor-vet -->
**Verdict: READY** · 2222222222222222222222222222222222222222
