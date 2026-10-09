# Contents

- [Canon's contract](#canons-contract)
  - [What Canon is and where it lives](#what-canon-is-and-where-it-lives)
  - [What Canon holds](#what-canon-holds)
  - [What stays out, and where it goes](#what-stays-out-and-where-it-goes)
  - [An entry](#an-entry)
    - [Rulings that approve wording kept elsewhere](#rulings-that-approve-wording-kept-elsewhere)
  - [Standing rulings and principles](#standing-rulings-and-principles)
  - [Ceded calls](#ceded-calls)
  - [Append only, and supersession](#append-only-and-supersession)
    - [Retiring a misfiled entry](#retiring-a-misfiled-entry)
  - [Writing a ruling](#writing-a-ruling)
  - [Merging](#merging)
  - [Reading Canon](#reading-canon)
  - [Choices recorded for the owner's veto](#choices-recorded-for-the-owners-veto)

# Canon's contract

This page is the one home for Canon's rules. Every other surface points here and states none of
them. Read it before you write or read a Canon entry.

## What Canon is and where it lives

**Canon is one plain file, `canon.md`, per project.** It is the record of the owner's decisions.

A project that keeps its definition-docs committed in the repository keeps Canon in that folder.
A project that keeps them out of the repository keeps Canon at `docs/canon.md` in its project store.
**A project whose in-repository definition-docs are gitignored keeps Canon in its project store.** A
gitignored file never reaches the default branch, lives in one worktree only, and is lost when that
worktree is removed. This is a choice recorded for the owner's veto.

A storage-mode switch made through configure does not move Canon. It stays where it is, and the
lookup below finds an existing Canon there in either mode.

Every session finds the file with:

```
python3 -B <plugin root>/lib/definition_doc.py canon --root <repo root>
```

The command prints one JSON object on one line with five keys:

- `path`: the absolute path of `canon.md`.
- `home`: `"repo"` or `"project-store"`.
- `gitRoot`: the absolute path of the git repository a write is committed to. It is the repo root
  when `home` is `"repo"` and the project store directory when `home` is `"project-store"`.
- `exists`: `true` when a file exists on disk at `path`, else `false`.
- `defaultRef`: the default-branch ref name, for example `origin/main`, when `home` is `"repo"` and
  `git rev-parse --abbrev-ref origin/HEAD` resolves. Otherwise `null`. The lookup resolves the
  default ref from `origin/HEAD` only (never a guessed `origin/main` or `origin/master`), returns
  `null` only when the repository has no `origin` remote, and otherwise refuses (exit 1, nothing on stdout, the
  cause and the remedy `git remote set-head origin --auto` on stderr) rather than reading an
  unprobed default branch as one with no Canon.

The in-repository candidate is `<repo root>/<doc-policy location>/canon.md`. It is a candidate only
when the doc-policy visibility is `committed`. The store candidate is `<project store>/docs/canon.md`.
**An existing file wins.** The in-repository candidate wins when it exists on disk or at the
default-branch ref. Otherwise the store candidate wins when it exists on disk. With neither file
present, in-repository storage mode with a committed policy gives the in-repository candidate.
Anything else, meaning global mode or a gitignored policy, gives the store candidate. The lookup
reads only. It creates and writes nothing.

## What Canon holds

Canon holds three kinds of record:

- Answers to owner calls.
- Principles, recorded as standing rulings.
- Ceded calls, and their take-backs.

Everything else the owner says stays out, even when it sounds like a decision. [What stays out, and
where it goes](#what-stays-out-and-where-it-goes) says what that is and where each kind belongs.

**The test.** Would a session sorting a future call, after the work this is about is done, need
this to answer it? If not, it is not Canon.

**An instruction that does two things.** When an owner instruction both directs one act and states
a rule for later work, it holds a ruling. Record the rule only, and leave the act where it was
given.

## What stays out, and where it goes

**Instructions for one act.** An owner instruction that directs one specific act, and is spent once
the act happens, stays where it was given: the issue's STATE block or order, the pull request's
owner half, or the thread. The class includes:

- Go-words: launch, merge, release, tier, force-push and filing words.
- Which instance or account a session runs on.
- Who brings a branch up to date, and when.
- Whether to wait for CI or another check before a step.
- A waiver or authorization for one change, such as the micro lane's quiet-failure waiver or a lane
  downgrade.

**Records that already have a home.** Canon never duplicates them.

| Record | Its home |
|---|---|
| Spec approval | The spec's review gate and its dated approval |
| Delivery acceptance | The closure receipt |
| [Decision-walk](glossary.md#decision-walk) dispositions, and proposals awaiting the owner's word | The [collector](glossary.md#collector) |
| Declined items and their reopening [triggers](glossary.md#trigger) | The [declined registry](glossary.md#declined-registry) |
| Lane and presentation calls | The issue |
| Merge and release words | The thread and the pull request's owner half |
| The threat model | Configure's threat model item |

**Bookkeeping that rides on a ruling.** When a real ruling arrives with bookkeeping attached (where
it was filed, which phase or milestone it is scheduled for, which issue tracks it), only the ruling
goes in. The bookkeeping stays on the board.

## An entry

An entry records one ruling and carries these fields:

- The id.
- The date the ruling was given.
- The ruling, in plain words.
- The scope: standing, or for one piece, naming that piece's work item.
- The owner's exact words, where there are any.
- Where it was said: the session and the time. Never transcript line numbers.

An entry is exactly one line. Fields are separated by the three characters space, middle dot, space
(` · `), in this order:

```
- **<id>** · <date> · <scope> · <ruling>[ · cedes: <kind of call>; example: <example>][ · supersedes: <id>] · owner's words: "<exact words>" · where: <session>, <time>
```

- `<date>` is the ISO date (`YYYY-MM-DD`) the ruling was given, in UTC.
- `<scope>` is `standing` or `piece <work-item slug>`. See **scope honesty** below.
- `<ruling>` may be several sentences. It never contains a line break and never contains ` · `.
- `cedes:` appears only on a ceded call. `supersedes:` appears only on an entry that replaces an
  earlier one.
- Where no owner's words were recorded, the field reads `owner's words: none recorded`, with no
  quotes.
- `<time>` is written in UTC and marked `UTC` (for example `14:05 UTC`), or reads
  `time not recorded` when the time is unknown.

An entry is one line because a union merge keeps whole lines. Two branches' entries can never
interleave.

**One ruling per entry.** An entry records exactly one ruling. Two rulings are two entries. A ruling
mixed with an act or with bookkeeping is trimmed to the ruling.

**Scope honesty.** The scope says how far the ruling reaches, and no further.

- `standing` only when the ruling applies to all later work. A step that is spent within the pull
  request it was given on is not standing: it is an instruction for one act and stays out.
- `piece <work-item slug>` names a work item's minted slug. An issue, a pull request, a stack layer
  or a phase is not a piece.
- A ruling that concerns only an issue or pull request with no work-item slug stays on that issue
  or pull request, where a ruling anchor can cite it, unless it holds for later work too. Then it
  passes the test, gets an entry, and its scope is `standing`. One that does not hold for later
  work gets no entry.

**Dates and times are UTC.** The `<date>` is the UTC date the ruling was given. The id's date is the
UTC date the entry was written. Take both from a UTC clock (`date -u`). When the source shows a
time in another zone (a sheet, a chat stamp), convert it, so an entry's date never disagrees with
the `where:` time it cites.

**Narrowing or replacing an earlier decision.** When a ruling narrows or replaces an earlier owner
decision, the entry says so. It carries `supersedes: <id>` when the earlier decision is a Canon
entry. Otherwise the ruling text names where the earlier decision lives (a spec section, a
configure item, an issue). Because a superseded entry no longer binds, the new entry restates
whatever part of the earlier ruling still stands.

**The id rule.** An id is `<YYYY-MM-DD the entry was written, in UTC>-<first 8 characters of the
writing session's id, lowercase>-<n>`. `<n>` is a positive integer with no leading zeros. The
sequence continues from the highest number that session prefix already used on that date in any
copy the writer can read, meaning its working copy and the default-branch copy. A resumed session
keeps counting. **A writer never mints an id already present.** Where a host exposes no session id,
the session mints 8 random lowercase hex characters once and reuses them.

### Rulings that approve wording kept elsewhere

When a ruling approves wording whose home is another artifact (a product doc, a configure item, a
spec), the entry records the decision and names the artifact. It never copies the wording. The
artifact is authoritative for the wording. A later change to that wording, made through the
artifact's own path (a spec amendment, a configure change), needs no new entry unless it changes
what the ruling decided. That is a new ruling, recorded with `supersedes:`.

Where Canon is itself the wording's home (configure item 13's examples once item 13 points to
Canon, a ceded call's example), Canon is authoritative, and a change is a new entry that
supersedes.

Canon is append-only and cannot follow an edit, so a copy goes stale silently. The same wording in
two homes can disagree, with no rule for which wins. The owner's-words field still quotes what the
owner said.

## Standing rulings and principles

A standing ruling applies to all later work. A piece ruling applies to the named work item only.
The project's principles are its standing rulings. An answer to a case that tests or creates a
principle is recorded as a standing ruling.

## Ceded calls

When the owner hands a kind of call to the agents ("you decide these from now on"), the session
records a standing entry with the `cedes:` field naming the kind of call and one example. From then,
calls of that kind are craft.

When the owner takes the call back, the session records a new entry that supersedes the ceded one.
Calls of that kind return to the owner.

## Append only, and supersession

**No session edits or deletes an entry.** A later ruling that replaces an earlier one, a take-back
included, is a new entry with `supersedes: <earlier id>`. From then the earlier entry is superseded
for every reader. That includes the supersession check in the issue contract's
[Anchor resolution](../skills/showrunner/reference/issue-contract.md#anchor-resolution) on a ruling
anchor that cites the earlier entry.

**Two entries sharing one id resolve for no reader.** A ruling anchor citing that id does not
resolve, and the duplicate goes to the owner.

### Retiring a misfiled entry

An entry that should never have been in Canon is retired, never edited or deleted. The retirement is
a new entry with `supersedes: <id>` whose ruling says the earlier entry is not a ruling and names
where it belongs.

- **A mixed entry** (a real ruling plus an act or bookkeeping): the new entry restates the ruling
  alone, with that ruling's own honest scope, and says what it trimmed. Supersession retires the
  earlier entry for every reader, whatever the new entry's scope.
- **An entry with nothing left to rule:** the new entry's scope is `standing`, because the
  retirement holds for every reader and every later piece of work. Its owner's-words field reads
  `owner's words: none recorded` unless the owner said something.
- **Only a plain misfile.** A session retires only an entry the contract's tests plainly put outside
  Canon. Whether a disputed entry is a ruling is the owner's call.
- **Anchors.** A retirement is a supersession, so a ruling anchor citing the retired id stops
  resolving. The session that writes a retirement tells the advisor. The advisor's supersession
  notice ([the advisor charter's](../skills/showrunner/SKILL.md) duty 2) re-points affected
  Anchors at the replacement entry where one carries the ruling.
- **No sweep is owed.** No project owes a sweep of its Canon for misfiled entries. A session that
  meets one may retire it.

## Writing a ruling

A session writes a ruling that passes the test in [What Canon holds](#what-canon-holds): an answer
to an owner call, a principle, or a ceded call or its take-back. It writes one ruling per entry.
What stays out is never written.

1. Refresh the default branch, then run the lookup. Before the lookup, when an origin remote exists and
   the network is available, run `git fetch origin`, so a stale `origin/HEAD` does not hide a Canon
   the default branch already has. If the fetch could not run or failed, say so in the report. The
   lookup itself never fetches.
2. If `gitRoot` is not a git repository, stop and report. Never initialize one. Configure sets the
   project store up.
3. Probe the default-branch copy before writing anything. In the repository home, when `defaultRef`
   is set, run `git ls-tree <defaultRef> -- <repo-relative path>`. Exit 0 with output means the
   default branch has a Canon. Exit 0 with empty output means it has none yet. Any non-zero exit
   means stop and report, and write nothing. In the store home, or when `defaultRef` is null because
   the repository has no origin remote, there is no default-branch copy: skip the probe.
4. If the file does not exist on disk, create it with the shape below: on the branch the session is
   working on in the repository home, and in the store's own repository in the store home (step 2
   confirmed it is one). Create it even when step 3 found a Canon on the default branch. **Writing a
   ruling never merges anything into the working branch.** A branch takes in only its own base, and
   only when its lane already would. The two files join when the branch lands, by the union merge
   in [Merging](#merging), and the repeated header that leaves is valid. In the repository home, on
   every write, make sure the `.gitattributes` beside `canon.md` holds the line
   `canon.md merge=union`, creating the file or adding the line when it is missing.
5. Read the ids already present in the working copy and, when step 3 found a default-branch Canon,
   in that copy, with `git show <defaultRef>:<repo-relative path>`.
6. Append the entry as one new last line. Never rewrite the file.
7. Make the Canon commit: commit only Canon's paths (`canon.md`, and in the repository home the
   `.gitattributes` beside it) at once, before the session's next step. Commit to the branch the
   session is working on in the repository home, and to the store's own repository in the store
   home.
8. Confirm that `git show HEAD:<path relative to gitRoot>` holds the new line. If the commit was
   refused or the line is missing, append again where needed and commit again. A session never moves
   on with an uncommitted ruling.

**The file shape.** Line 1 is `# Canon`, then a blank line. Next is one short paragraph of at most
four lines. It says the file is the project's Canon, the record of the owner's decisions, that its
rules live in the superheroes plugin's `rubric/canon-contract.md`, and that entries are appended
one per line at the end and never edited or deleted. Then a blank line, `## Entries`, and a blank
line. The entries follow, one per line, with nothing after them.

The entries are exactly the lines that begin with the entry marker (`- **<id>**`). Every other line is
header text and carries no meaning to a reader. If two branches each created the file and a union
merge kept both headers, the file is still valid: readers ignore the repeated header, and no session
edits it away.

**Canon never gets a pull request of its own.** A ruling rides the pull request of the branch it was
committed on, so a spec's rulings ride the spec's pull request. A ruling the advisor receives
outside any open pull request is committed to the branch of the next pull request it opens. How the
advisor holds it until then is the [advisor charter's](../skills/showrunner/SKILL.md) to say.

In the store home, each commit binds at once every session that shares that store on the machine.

## Merging

In the repository home, the `.gitattributes` beside `canon.md` holds one line:
`canon.md merge=union`. It makes git keep both branches' new lines when two branches both append.

A tool that ignores the attribute, a web conflict editor for example, is resolved by the same rule
by hand. Keep every line from both sides whole and change no entry's text. The order of entries
carries no meaning. A repeated header kept by a union merge of two created files is header text and
is left as it is.

## Reading Canon

Before the lookup, a reader runs `git fetch origin` when an origin remote exists and the network is
available, so a stale tracking ref does not hide a Canon the default branch already has (the same
step writing step 1 has); when the fetch could not run or failed, it says so and names the copy it
read as possibly stale. The lookup itself never fetches.

A reader reads the default-branch copy plus its own working copy, joined by id. When `defaultRef`
is null (the repository has no origin remote, even after the fetch) there is no default-branch copy: it
reads its own working copy only, says so, and skips the tree probe. Otherwise it first runs
`git ls-tree <defaultRef> -- <repo-relative path>` (the absence test write step 3 uses): exit 0 with empty
output means the default branch has no Canon yet, so the reader reads its own working copy only and says
so; exit 0 with output means it reads the copy with `git show <defaultRef>:<path>`; any non-zero exit means
it stops and reports. A ruling not yet on the default branch binds only the sessions on the branch that
holds it. In the store home there is one copy, and every session sharing the store reads it.

These sessions read Canon:

- Discovery, before its first question.
- The source check, to trace a statement to its source.
- The advisor's vet, to check a spec across every piece.
- Any session sorting a call. A standing ruling or a ceded call that already answers the call makes
  it craft.

## Choices recorded for the owner's veto

- Canon lives in the project store when a project's definition-docs are gitignored.
- An in-repository project gains the one-line `.gitattributes` with its first entry.
- Entries are one line each.
- An entry that approves wording kept in another artifact points to it rather than copying it.
- Canon's dates and times are UTC.
- A misfiled entry is retired by a superseding entry, scoped `standing` when nothing in it is a
  ruling.
