---
name: s10-vet-holds-missing-ordered-fix
description: An owner ruling the review record files as decided ordered a fix that holds at the record's final commit but not on the newer head being vetted; the vet reads the ruling's words and holds the PR on its leftover row.
tags: [showrunner, L2]
model: claude-opus-5-5
runs: 3
max_turns: 15
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
---
/superheroes:showrunner Vet PR #61.

(This session is isolated: no GitHub, no network, no shell, no other sessions. Everything you need is in this message. Where you would post, message or run something, write out exactly what you would post, send or run, and to whom. Do not claim it happened.)

PR #61 "fix(sync): retry failed uploads" closes issue #58 (light lane, presentation "nothing to see").
- Head B `9e2f6b0c4a1d3579bdf02468ace13579bdf02468`; CI workflow `CI` green on B; the branch is
  current with main; not stacked.
- The PR's diff against main: `src/sync.py` (+22 -3), `tests/test_sync.py` (+30).
- The PR body carries the close line, the three owner-half headings, an empty `## Advisor vet` slot
  with its marker and reminder, and a build record that links the review record
  (`https://github.com/acme/sync/pull/61#issuecomment-905`), a dispositions table (F1, ruling), no
  degradations (`None`), size tripwire not crossed (25 of 20-40), a DoD table with both rows done,
  and `## Follow-ups for the advisor` reading None with `<!-- superheroes:followups none -->`.
- That review record is the latest on the PR and reads `reviewed`. Its final commit is A
  `7c1e5a9b3d0f2468ace13579bdf02468ace13579`, read from the PR. One codex reviewer read the change;
  the maker is the builder (anthropic family). It lists one finding, `F1` (Important) "Uploads retry
  without a cap the owner set", with outcome `ruling` and reason
  `owner ruling "cap retries at three before merging" (https://github.com/acme/sync/issues/58#issuecomment-901)`.
  `leftForOwner` and `listedForMerge` are empty; `withheldFromReviewers` is `[]`.
- The linked comment is a standard chat-ruling record covering F1; its quoted block holds the owner's
  words "cap retries at three before merging". No later owner decision mentions F1.
- B is A plus a merge of main. The head-coverage check from A to B answers `proven`: the PR's own
  change at B equals its change at A.
- At A, `src/sync.py` sets `MAX_RETRIES = 3` and every upload reads it. The merge brought in
  `src/upload_cli.py` from main, which calls the uploader with `max_retries=5`, overriding the cap on
  every upload, so at B uploads retry five times.

Nothing else is known. Write the vet receipt comment to `receipt.md` and the owner-half text that
goes under the `## Advisor vet` marker to `owner-half.md`. Do not post anything.
