# Contents

- [The spec vet](#the-spec-vet)
- [When a vet runs](#when-a-vet-runs)
- [What you check](#what-you-check)
- [Sorting a finding](#sorting-a-finding)
- [The vet record](#the-vet-record)
- [How discovery learns the vet is done](#how-discovery-learns-the-vet-is-done)
- [Vetting the breakdown](#vetting-the-breakdown)

# The spec vet

This file holds the mechanism of the advisor's spec vet. The rules — what the vet checks against,
that it never edits the spec, the sequence, and the after-approval path — are duty 1 of
`skills/showrunner/SKILL.md`, stated there once.

## When a vet runs

- On the spec PR discovery opens after the owner's "ready for vet".
- On the stored spec, where the project keeps specs out of the repo or gitignored. Its home is the
  spec's work-item folder.
- Again after each round of discovery's fixes.
- Again when a final-sheet answer changes the spec.

Rounds are numbered from 1 per spec and keep counting across all of these.

## What you check

Five checks. Each is a source of findings.

1. **The three spec checks ran.** Every finding they raised has its pile in the checks record. Read
   the record; the checks themselves are in
   [spec-checks.md](../../architect-discovery/reference/spec-checks.md).
2. **The repo.** Every claim the spec makes about the product or the repo holds on the project's
   default branch.
3. **The other approved specs.** No contradiction, and nothing in this spec belongs to another
   piece.
4. **Canon across every piece.** No conflict with a standing ruling or with another piece's ruling,
   read as [Canon's contract](../../../rubric/canon-contract.md#reading-canon) says.
5. **Decomposable, in owner terms.** The spec can be broken into issues, and its consequences are
   stated in owner terms.

You may size your own vet. Say in the record the size you chose and why.

## Sorting a finding

Each finding is craft or owner call, sorted by the
[owner-vs-craft line](../../../rubric/owner-vs-craft-line.md).

- **An owner call** carries the question the final sheet will ask and your recommendation with its
  reason.
- **A craft finding** says what is wrong and which source it fails. You fix nothing; discovery fixes
  it.

## The vet record

One durable record per round. A record is never edited after it is posted; a correction is the next
round's record.

Where it lives:

- A comment on the spec PR.
- For a stored spec, appended to `vet-record.md` in the spec's work-item folder, newest last, records
  separated by a blank line.

The template:

```
<!-- superheroes:spec-vet -->
**Spec vet, round <n>** · spec `<work item>` · head `<sha or "stored">` · spec hash `<content hash>` · size `<the size you chose and why>`
**Verdict:** `clean` | `findings`

| Id | Kind | Where | What is wrong | Source it fails |
|---|---|---|---|---|
| V<n>.<k> | craft or owner call | § <spec section> | <one or two sentences> | <repo path, approved spec and section, or Canon entry id> |

**Owner calls for the final sheet:**
- V<r>.<k> — <the question>. Recommendation: <option>, because <reason>.

Vet done: round <n> · <clean|findings> · <content hash>
```

The fields:

- **Spec hash.** Run `python3 -B <plugin root>/lib/definition_doc.py content-hash --path <spec.md>`
  on the spec as vetted. It prints one lowercase SHA-256 line. Use the same command in both storage
  modes.
- **Verdict.** `findings` when any craft finding is open, `clean` when none is. Owner calls do not
  stop a clean verdict.
- **The table.** It lists this round's findings, or the single word `None`.
- **Owner calls.** Every owner call not yet put on a final sheet is carried forward into each later
  record's list, with its original id. A clean record then lists every owner call the final sheet
  must hold. The list reads `None` when there are none.
- **The last line.** The `Vet done:` line is always the record's last line.

## How discovery learns the vet is done

The record is the notice. Discovery reads the newest record by round number and acts on it only when
the hash on its `Vet done:` line equals the spec's content hash now. A record whose hash does not
match is stale, and the spec needs a new vet.

When the discovery session is reachable, also send it a one-line pointer to the record. The pointer
is a courtesy and never the notice, because a session that has ended cannot receive it.

## Vetting the breakdown

After approval (duty 1), the breakdown you add to the same PR, or beside the stored spec, is yours.
You fix its findings yourself.

Record that vet in a vet record of the same shape, on the same PR or in the same file. Its rounds
count on from the spec's. Its spec hash is unchanged, because the breakdown never edits the spec.
The record's header line reads `**Breakdown vet, round <n>**` in place of `**Spec vet, round <n>**`,
and its owner-call list reads `None`. The breakdown carries no owner calls; a breakdown finding that
needs the owner goes to the owner through the merge-word conversation, not the final sheet.

**The breakdown pin.** The spec hash does not cover the breakdown, so the record also pins what you
vetted. Just above the `Vet done:` line, add a line `Breakdown pins:` followed by one
`<path> <content hash>` pair for each breakdown artifact, each hash from the same `content-hash`
command run on that file as vetted. The artifacts are the coverage map, the contract register, the
package-read audit trail and every body the filing creates, which is the inventory of
[the filing dry-run](decomposition.md#the-verification-pass): each child body, the epic body and
every planned layer body, each as a file. A single-issue spec has no
register and no package read, so its pins are the bodies its filing creates: the child's proposed
body and, when the child plans a stack, every planned layer body, each saved beside the spec as a
file before you vet it. A record is clean for filing only when every pinned file's hash
equals its content now. A file that changed, or one the record does not pin, means the record is
stale and the breakdown needs a new vet. This holds in the stored-spec mode too.

Where the package read applies, it runs as
[decomposition.md](decomposition.md#the-adversarial-package-read) says. This vet does not replace
it.
