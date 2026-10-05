# Contents

- [Canon's contract](#canons-contract)
  - [What Canon is and where it lives](#what-canon-is-and-where-it-lives)
  - [What Canon holds](#what-canon-holds)
  - [An entry](#an-entry)
  - [Standing rulings and principles](#standing-rulings-and-principles)
  - [Ceded calls](#ceded-calls)
  - [Append only, and supersession](#append-only-and-supersession)
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
  default ref as `origin/HEAD`, else `origin/main`, else `origin/master`, returns `null` only when
  the repository has no `origin` remote, and otherwise refuses (exit 1, nothing on stdout, the
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

Three things stay out:

- Go-words (merge, launch, release, tier) stay where the owner gives them.
- Walk records and the declined registry carry on as they are.
- The threat model stays in configure's threat model item.

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

- `<date>` is the ISO date (`YYYY-MM-DD`) the ruling was given.
- `<scope>` is `standing` or `piece <work-item slug>`.
- `<ruling>` may be several sentences. It never contains a line break and never contains ` · `.
- `cedes:` appears only on a ceded call. `supersedes:` appears only on an entry that replaces an
  earlier one.
- Where no owner's words were recorded, the field reads `owner's words: none recorded`, with no
  quotes.
- `<time>` may read `time not recorded` when the time is unknown.

An entry is one line because a union merge keeps whole lines. Two branches' entries can never
interleave.

**The id rule.** An id is `<YYYY-MM-DD the entry was written>-<first 8 characters of the writing
session's id, lowercase>-<n>`. `<n>` is a positive integer with no leading zeros. The sequence
continues from the highest number that session prefix already used on that date in any copy the
writer can read, meaning its working copy and the default-branch copy. A resumed session keeps
counting. **A writer never mints an id already present.** Where a host exposes no session id, the
session mints 8 random lowercase hex characters once and reuses them.

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

## Writing a ruling

A session that receives a ruling that decides something writes it. That means an answer to an owner
call, a principle, or a ceded call or its take-back. Go-words are never written.

1. Run the lookup.
2. If `gitRoot` is not a git repository, stop and report. Never initialize one. Configure sets the
   project store up.
3. If the file does not exist, create it with the shape below. In the repository home, also create
   the `.gitattributes` beside it.
4. Read the ids already present in the working copy and, when `defaultRef` is set, in
   `git show <defaultRef>:<repo-relative path>`.
5. Append the entry as one new last line. Never rewrite the file.
6. Commit only Canon's paths at once, before the session's next step. Commit to the branch the
   session is working on in the repository home, and to the store's own repository in the store
   home.
7. Confirm that `git show HEAD:<path relative to gitRoot>` holds the new line. If the commit was
   refused or the line is missing, append again where needed and commit again. A session never moves
   on with an uncommitted ruling.

**The file shape.** Line 1 is `# Canon`, then a blank line. Next is one short paragraph of at most
four lines. It says the file is the project's Canon, the record of the owner's decisions, that its
rules live in the superheroes plugin's `rubric/canon-contract.md`, and that entries are appended
one per line at the end and never edited or deleted. Then a blank line, `## Entries`, and a blank
line. The entries follow, one per line, with nothing after them.

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
carries no meaning.

## Reading Canon

A reader reads the default-branch copy (`git show <defaultRef>:<path>`) plus its own working copy,
joined by id. A ruling not yet on the default branch binds only the sessions on the branch that
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
