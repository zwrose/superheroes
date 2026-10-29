# Contents

- [Diagnosing in a cloud session](#diagnosing-in-a-cloud-session)
  - [When this file applies](#when-this-file-applies)
  - [Intake](#intake)
  - [The GitHub channel](#the-github-channel)
  - [Where disposable copies live](#where-disposable-copies-live)
  - [The progress comment](#the-progress-comment)
  - [Terminal notes](#terminal-notes)
  - [Asking the advisor](#asking-the-advisor)
  - [What stays the same](#what-stays-the-same)

# Diagnosing in a cloud session

This page is reference for the detective running in a cloud session. The charter's *In a cloud
session* section points here. Every step below names a `cloud_builder.py` verb the CLI accepts, or a
plain `git` or `gh api` command. In a cloud session, `<plugin root>` is the plugin directory the
session loaded.

## When this file applies

The launch prompt carries `Place: cloud session`, then `Advisor plugin version: <version>`,
`Cloud environment: <id>` and `Base commit: <sha>`. Its cloud rule for the detective is the
`cloud-detective` block of `rubric/launch-doctrine.md`; follow the sentence in your launch prompt and
read the limits from that block. Everything else in the charter still holds; this page says only what
differs.

## Intake

1. Write the launch prompt text to a file.
2. Run `python3 -B <plugin root>/lib/cloud_builder.py intake --repo-root <root> --launch-file <file>`.
3. On `ok: false` (exit 1) post the result's `comment` on the incident issue as it is and end the
   lane. Diagnose nothing.
4. On `ok: true` post the result's `comment` as the first comment on the incident issue. Never
   re-word it.

The checks are the builder's: the plugin version against the advisor's, the environment, the base
commit (`skills/workhorse/reference/cloud.md` § Intake). The clone is left at the launch's base
commit, or on the adopted branch at its pushed head: that checkout is what you read.

## The GitHub channel

Run the preflight channel steps of `skills/workhorse/reference/cloud.md` § Preflight, and read the
tracker as its § GitHub reads, without GraphQL says. You need a write channel only for comments.

## Where disposable copies live

Only inside this cloud session: a detached worktree, or a copy under the session's scratch
directory, made from the checkout above. A copy is never committed to a pushed branch, never pushed,
never a pull request, and is discarded before the terminal note. The surface under diagnosis, the
clone's own checkout, is never edited.

## The progress comment

Keep **one** progress comment on the incident issue and edit it in place. Compose it with
`python3 -B <plugin root>/lib/cloud_builder.py progress --phase <text> --running <text> --started <UTC time, …Z> --expected-minutes <N> [--lost <text>]`;
the fields, the update rule and the edit channel are those of `skills/workhorse/reference/cloud.md`
§ The progress comment.

Its header is the cloud lanes' shared progress header, which the advisor's wave watch reads for
every cloud lane; it is not a claim of being a builder. Update it at each phase: intake, registry
scan, each reproduction or A/B, receipt.

## Terminal notes

Post each on the incident issue after the receipt comment, composed with
`python3 -B <plugin root>/lib/cloud_builder.py terminal --kind <kind> --text-file <file>`, and link
the receipt comment in the text.

- `handback`: the receipt with a demonstrated root cause is posted.
- `park`: an honest not-demonstrated receipt is posted (the named budget was reached, or hypotheses
  ran out). The text names what was ruled out.
- `stop`: you declined before any diagnosis spend because the work meets none of the three fire
  conditions (charter § When this role fires).

This mirrors the charter's stamp duty: `handback` after a receipt, `parked` after an honest exit.

## Asking the advisor

Ask by builder note, exactly as `skills/workhorse/reference/cloud.md` § Asking the advisor says,
including the park when no answer comes.

## What stays the same

Everything in the charter: observe-only, the receipt's four elements, redaction (and the cloud's own
credential redaction, `skills/workhorse/reference/cloud.md` § The cloud container), and the
advisor's vet.
