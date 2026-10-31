Closes #100.

## What's changing, and why

The export page now lists the newest files first, so the file people want is at the top.

## What we're accepting

- The verify gate did not run on the final head, so the last commit's tests are unverified until CI runs.

<!-- superheroes:build-record -->
<details><summary>Build record</summary>

<!-- superheroes:degradations -->
### Disclosed degradations

- [harmless] The order rode a prompt file, not inline: the builder was pointed at the file and read it there.
- [costly] The verify gate did not run on the final head, so the last commit's tests are unverified until CI runs.

</details>
