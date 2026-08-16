# Rehearsal 1 — demonstrated cause: shell redirect empties body before `gh` runs

## What a rehearsal record is

A rehearsal record is a Definition-of-Done artifact: it shows, from documents alone, that the detective → advisor pipeline produces honest artifacts. **Every claim in this record is either a command that was actually run with its real output pasted below, or is explicitly labelled `DRAFTED — NOT POSTED` / `DRAFTED — NOT FILED`.** A reader can tell, for every artifact, whether it happened or was written for someone else to perform.

**DoD row status (partial).** This record satisfies the detective DoD row **in part**: the **diagnosis receipt** and **five-check vet verdict** are produced here; the **incident-body update** and **fix issue** are drafted for the advisor, because a builder never wires the board. The row is therefore **carried as partially satisfied and disclosed in the PR** — not claimed closed by this document alone.

**Board-wiring boundary.** A builder never wires the board — it does not file issues and does not edit issue bodies. In this record:

- the **diagnosis receipt** and **five-check vet verdict** are **produced for real** (`PRODUCED`);
- the **incident-body update** and **fix issue** are **drafted, ready to paste**, and marked **`DRAFTED — NOT POSTED (advisor action)`** / **`DRAFTED — NOT FILED (advisor action)`**.

Diagnostic output in this record was **scrubbed** for secrets, tokens, credentials, authorization headers, private URLs, and PII before pasting. Absolute local paths under `/Users/` and temp dirs are retained.

---

## Incident

On 2026-08-16 an advisor session pushed an **empty PR body** to PR #1041 while correcting one line of its vet slot. The recorded note in that PR's body says: *"a shell redirect truncated my working copy before `gh pr edit`"*. The symptom "the body went blank" names no failing component; the same read-modify-write shape threatens every issue or PR body edit.

**Examined surface:** PR #1041 body (read-only `gh` calls only; no body edits in this rehearsal).

---

## Diagnosis receipt — `PRODUCED`

*(Shape per detective charter — four elements; this is the comment the detective would post on the incident issue.)*

### 1. What happened, with receipts

**Symptom.** PR #1041's body was replaced with a zero-byte body during an advisor vet-slot correction on 2026-08-16. The advisor's own note attributes it to a shell redirect truncating the working copy before `gh pr edit`.

**Hypothesis.** When `gh <read> > body.md` runs in a working directory where `gh` cannot resolve the repository (outside any git tree), the shell's `>` truncates `body.md` **before** `gh` runs; `gh` then fails, writes nothing, and a following `gh pr edit --body-file body.md` can push an empty body. Exit statuses are easy to miss if not checked.

**A/B — suspected factor: working directory.** All probes ran in a disposable temp directory (`mktemp -d`), never in the repository. Read-only `gh issue view` against issue #931 (this repo's detective work-item issue).

**Arm A (factor present — outside git repo):**

```text
PWD: /var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/tmp.ZoAcoORYJG
$ gh issue view 931 --json body -q .body > out-a.md 2>gh-a.stderr
gh exit status: 1
stderr:
failed to run git: fatal: not a git repository (or any of the parent directories): .git

$ wc -c out-a.md
       0 out-a.md
```

**Arm B (factor absent — inside this repository):**

```text
PWD: /private/tmp/sh931-woF
$ gh issue view 931 --json body -q .body > out-b.md 2>gh-b.stderr
gh exit status: 0
stderr: (empty)

$ wc -c out-b.md
    3563 out-b.md
```

First 200 characters of `out-b.md` (excerpt):

```text
**Anchor (spec-section):** spec `the-detective-16c561` (whole spec) — owner-approved 2026-08-07, as-of amendment #1. [Spec](../blob/main/docs/superheroes/the-detective-16c561/spec.md) · FR-36 fast 
```

**Redirect truncates first (second half of mechanism).** Pre-filled file in Arm A context:

```text
$ echo "KNOWN_CONTENT_BEFORE_REDIRECT" > prefill.md
$ wc -c prefill.md
      30 prefill.md

$ gh issue view 931 --json body -q .body > prefill.md 2>gh-prefill.stderr
gh exit status: 1
stderr:
failed to run git: fatal: not a git repository (or any of the parent directories): .git

$ wc -c prefill.md
       0 prefill.md
```

The known content is gone even though `gh` failed — the truncate happened at redirect open, not from `gh` writing an empty JSON field.

**Disposable copy discarded** *(reconstruction — variable name corrected from the original capture; commands and output are consistent with the path used in the A/B probes above)*:

```text
DISPOSABLE_PATH=/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/tmp.ZoAcoORYJG
$ rm -rf "$DISPOSABLE_PATH"
$ ls "$DISPOSABLE_PATH"
ls: /var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/tmp.ZoAcoORYJG: No such file or directory
```

### 2. Demonstrated root cause

**What the A/B demonstrates (sufficient mechanism).** Running `gh issue view … > file` **outside** a git repository yields a **zero-byte file** and `gh` exit **1** (`failed to run git: not a git repository`). The **identical command inside** the repository yields a **populated file** (3563 bytes) and exit **0**. Pre-filling the target file shows the redirect empties the file **before** `gh` executes — so the failure mode is the shell redirect truncating first plus an unchecked `gh` failure, not `gh` returning an empty body string. This is a **demonstrated sufficient mechanism** for producing a zero-byte body file that could feed a later `gh pr edit --body-file`.

**What the A/B does not establish about PR #1041.** No receipt from the incident session establishes that the advisor's read ran outside a git repository, that `gh` exited non-zero, that exit status was ignored, or that this zero-byte file was what `gh pr edit --body-file` consumed. The only incident evidence is the advisor's one-line note in the PR body. The mechanism is demonstrated; its application to PR #1041 remains a **plausible, unconfirmed** match until session records close the gap.

### 3. Blast radius

**Exposure the demonstrated mechanism creates.** Any workflow that **reads an issue/PR body to a file with `>`** and later **writes that file back** with `gh issue edit` / `gh pr edit --body-file` is exposed when the read happens outside a resolvable git context (wrong cwd, detached temp dir, stale worktree path). That exposure pattern matches advisor vet-slot corrections, incident-body drafts, and any agent script using the same read-modify-write shape. Failure is silent when shell exit codes are not checked — regardless of whether PR #1041's session actually hit this path.

### 4. Recommended follow-ups

1. **Advisor / showrunner charter** — document the safe pattern: read body to a variable or use a cwd inside the repo (or explicit `--repo`); never `gh … > file` from an unanchored directory; check `gh` exit status before any edit.
2. **Close the PR #1041 gap** — recover the failing invocation, its cwd, and `gh` exit status from the advisor session record (or equivalent logs) to confirm or rule out this mechanism on the actual incident.
3. **Restore PR #1041 body** — build-ready fix from the last good body (git history or issue cross-links), routed only after this vet passes.
4. **Optional guard** — shell wrapper or preflight that refuses `gh pr edit --body-file` when the file is empty or below a minimum size.

---

## Five-check vet verdict — `PRODUCED`

| Check | Grade | Notes |
| --- | --- | --- |
| 1. Cause demonstrated (repro or A/B, not inference) | **Pass** | A/B demonstrates a **sufficient mechanism** (0 vs 3563 bytes, exit 1 vs 0; redirect-first proof on pre-filled file). Does not by itself prove that mechanism ran on PR #1041 — only that it can produce the observed symptom. |
| 2. Recommended fix targets cause, not symptom | **Pass** | Follow-ups address read-modify-write cwd and exit checking; body restore is separate build work. |
| 3. Blast radius stated | **Pass** | All `gh` body read-modify-write paths named. |
| 4. Each follow-up carries the right anchor | **Pass** | Charter doc, PR #1041 restore, optional guard — each tied to this diagnosis. |
| 5. No smuggled product opinion | **Pass** | No new product requirements; operational guard only. |

**Verdict (plain language).** The diagnosis is vetted for what was measured: a **sufficient mechanism** — shell redirect truncation combined with `gh` failing outside a git repository — was demonstrated on a disposable copy with read-only `gh` calls. That demonstration does not confirm this mechanism on PR #1041 without session evidence (cwd, exit status, file path). Route charter documentation, session-record follow-up to close the incident gap, and a build to restore PR #1041's body; do not treat "blank body" as an `gh` API bug without this cwd check.

**Terminal branch:** vet passes → advisor may update the incident body and file anchored fix issues (drafts below; not posted by this builder).

---

## Incident-body update — `DRAFTED — NOT POSTED (advisor action)`

```markdown
## Demonstrated mechanism (sufficient; incident match unconfirmed)

A/B on issue #931 shows a **sufficient mechanism** for a zero-byte PR body: a shell redirect (`>`) truncates the target file **before** `gh issue view` / `gh pr view` runs; when cwd is **outside** a git repository, `gh` fails (`not a git repository`), writes nothing, and a subsequent `gh pr edit --body-file` can push the empty file. Measured: 0 vs 3563 bytes in vs out of repo; redirect-first proof on a pre-filled file.

**PR #1041 gap.** The advisor's note attributes the empty body to redirect truncation, but no session receipt yet confirms cwd, `gh` exit status, or that this file fed the edit. Treat the mechanism as demonstrated; treat the PR #1041 application as plausible until session records close the gap.

## Routing

- **Vet:** passed for demonstrated mechanism (see diagnosis comment).
- **Follow-up:** recover failing invocation, cwd, and exit status from the advisor session record.
- **Fix:** restore PR #1041 body from last good revision; add showrunner guidance on safe body read-modify-write (cwd + exit checks).

## Log

Diagnosis receipt and vet verdict live in comments. This body is the advisor post-vet summary.
```

---

## Fix issue — `DRAFTED — NOT FILED (advisor action)`

**Title:** `fix(superheroes): document safe gh body read-modify-write; restore PR #1041 body`

**Anchor:** Diagnosis on PR #1041 empty-body incident (rehearsal record `rehearsal-1-gh-empty-body.md`; detective receipt above).

**What:** (1) Restore PR #1041's body from the last good content. (2) Add showrunner/advisor guidance: never `gh … > file` from a cwd outside the repo; check `gh` exit status before `gh pr edit --body-file`; prefer in-repo cwd or explicit `--repo`.

**Definition of done:**

- PR #1041 body restored and readable without the comment thread.
- Charter or reference doc states the safe pattern with a one-line failure mode ("redirect truncates before gh runs").
- No regression to PR body editing workflows in CI.

---

## Untouched-surface evidence

**Before rehearsal:**

```text
$ git rev-parse HEAD
9013a46e42a60c7cca058633dedd69a51f045b98
$ git status --porcelain | shasum -a 256
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  -
```

**After rehearsal** (before committing these record files):

```text
$ git rev-parse HEAD
9013a46e42a60c7cca058633dedd69a51f045b98
$ git status --porcelain | shasum -a 256
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  -
```

HEAD and porcelain hash **match** — examined surface (PR #1041 body) was not edited; only read-only `gh` and disposable temp probes.

**Disposable copy:** `/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/tmp.ZoAcoORYJG` — removed (`rm -rf`); `ls` confirms path absent.
