# Contents

- [The vet receipt — shape](#the-vet-receipt--shape)
- [The spine — always present, filled or `None`](#the-spine--always-present-filled-or-none)
- [Triggered fields — the artifacts raise them, not your memory](#triggered-fields--the-artifacts-raise-them-not-your-memory)
- [The review record checks](#the-review-record-checks)
- [A handback with open findings](#a-handback-with-open-findings)
- [Recording an owner acceptance — the advisor writes it](#recording-an-owner-acceptance--the-advisor-writes-it)
- [The outside list](#the-outside-list)
- [The claims check](#the-claims-check)
- [Project vet checks](#project-vet-checks)
- [The `None` convention](#the-none-convention)
- [The owner-half write — register](#the-owner-half-write--register)
- [Markers](#markers)
- [Skeleton](#skeleton)

# The vet receipt — shape

The vet is the **last independent read before the owner's one irreversible act**. This file is the
shape of the receipt that read leaves behind — and, below, the register of the owner-half write it
points at. **When** it is written and what else the vet does are the **showrunner** charter's duty 4
— read this one at vet time, and do not reconstruct it from memory.

**Why a shape at all.** The spine below was not designed; it is what independent receipts had
**already converged on**, ratified rather than invented. What had *not* travelled were the loads a
charter added later — and the reason nobody could measure that is the reason this file exists: **presence-by-grep cannot tell "not applicable" from "forgotten."** An explicit `None` is
what makes an absence readable.

**The template is a floor, never a ceiling — most of all for field 2.** The probes are where a vet's
value actually lives. A uniform receipt whose probes field reads like a form has hollowed out the one
field that cannot be. If the shape ever makes a receipt shorter than the vet's actual thinking, the
shape is wrong and the thinking wins.

## The spine — always present, filled or `None`

1. **Verdict, and what it is pinned to.** The verdict, plus the **commit sha** you vetted, the **CI
   state** on that sha, and confirmation that the **remote head** contains it. A verdict pinned to
   nothing is a mood; a verdict pinned to a local-only commit is a claim about work the owner cannot
   see.
   **Select that CI run by workflow name *and* head sha — never `gh run list --limit 1`.** The latest
   run on a branch is whatever workflow happened to fire last, which is not necessarily the one whose
   green you are claiming, so `--limit 1` can report another workflow's green as this one's. Name
   the workflow and pin the sha; a run that does not match both is not evidence about this head. When the same check ran more than once on that sha, its newest run is the reading: an older cancelled run that a newer run of the same check replaced is superseded, and a check whose newest run is cancelled is red — the review record reads CI the same way. The same selection binds
   **any** CI watch on a head you are about to act on — a vet, a wave watch, a merge train — not only
   the one this receipt records.

   **The content pin.** The receipt records the head sha **and the digest of the pull request's
   diff**. Take the digest from a materialized artifact between the **pinned base commit** and the
   current head — prefer a **locally generated patch** (`git diff <base>..<head> --patch` or
   equivalent over the two git objects), which cannot be truncated by a server-side display limit and
   includes merge-commit resolutions in the final tree. Where `gh pr diff <n> --patch` is used instead,
   materialize it to a file, check `gh`'s exit status, assert the file is non-empty, and **establish
   completeness**: the response must not be at or over GitHub's stated diff limits (20,000 lines, 1 MB,
   300 files) and must carry no truncation marker. Then run `shasum -a 256` over that file. It is not
   a pipeline, for a reason a careful reader would not guess: a shell pipeline discards `gh`'s exit
   status, so an auth, network or limit failure hashes **empty input** and two failed reads compare
   **equal**. That is the fail-open this recipe closes. When completeness **cannot** be established —
   a read that fails, comes back empty, or is truncated — the result is **`digest-unavailable`**, and
   `digest-unavailable` is treated **exactly as unequal**, never as equal.

   **The re-pin form.** After a bring-current the lane recomputes the digest, re-pins the sha in
   place with a dated line, and runs CI on the new head. Coverage after any move is the check's
   answer, as the final-commit row of [the review record checks](#the-review-record-checks) says.
   **A layer is not rebased while its review loop is open.** A moved base still takes CI on the new
   head, which this field already requires.

   **A straightening for a merge queue.** When `lib/stack_linear.py prove` shows a layer's new head has
   the same git tree as its vetted head, the receipt is re-pinned with the dated `repin` line `prove`
   printed, and CI runs on the new head. A `tree-changed` refusal prints no `repin` line. The recipe is
   `skills/showrunner/reference/merge-train.md` § Merging a stack, item 4.

   **The verdict form — how the slot is read.** The `## Advisor vet` owner-half slot's verdict is
   read from **one line**: the **first non-empty line after `<!-- superheroes:advisor-vet -->`**.
   That line **begins, at its start**, with exactly one of `**Verdict: READY**`,
   `**Verdict: NOT-READY**`, `**Verdict: PARKED**`, followed by ` · ` and the **full 40-character
   head sha** the verdict is pinned to. Qualifiers ("as a layer", "held with the stack") follow on
   that same line and **never replace the token**. **For the purpose of extracting a verdict, every
   other slot content is non-authoritative** — dispositions, probes, prose, fenced blocks and
   `<details>` regions are not read for a verdict. That scoping is about **verdict extraction only**.
   It does not make the owner half's *what accepting it means* or *what is theirs to decide* any less
   authoritative as **owner** information.

   **Each of these reads NOT-READY by construction:** no marker; no non-empty line after the marker;
   a first line that does not begin with one of the three tokens; an unknown or negated verdict word;
   more than one token on the line; a missing head sha, a sha that is not 40 hex characters, or a sha
   that is not the pull request's current head; more than one advisor-vet marker in the body. **A
   slot not in this form reads NOT-READY.**

   **Retrofit — a listed edit, not a judgment per pull request.** Every **open** pull request whose
   body carries the advisor-vet marker is brought to this form by **the advisor**, editing the slot's
   first line **in place**, before the reader that consumes the form is live. Identify the population
   **mechanically**: `gh pr list --state open` ∩ advisor-vet marker present. A pull request opened
   after the reader goes live is in the population **by the rule**. A slot whose currency **cannot be
   proved** — no verdict line, a dropped write, a sha that is not the current head — **reads
   NOT-READY**.
2. **What I probed.** **Distinct from the builder's own receipts** — re-running a green suite the
   builder already ran is not a probe. Say **what bit**: the mutation that made a named test fail, the
   guard you live-fired, the refusal you provoked. Confirm every **probe residue was reverted**. A
   probe that found nothing is still a probe — record it, including the ones whose premise turned out
   to be yours rather than the code's.
   **The PR's self-claims are checked against the diff, unconditionally.** On every full or light
   vet, read the PR body's claims against the diff and the artifacts by hand — the DoD table's `done`
   rows, the degradations it states, and every receipt or test run it claims — whether or not a
   review seat ran. The auto-fix loop does not run review-code's step 7 honesty check, so this read
   is the only one. The receipt says what was read and names any claim the artifacts do not support.
3. **Calls accepted, with reasons.** Every builder judgment call you are letting stand, each with
   why. Silence here reads as *not noticed*, not as *endorsed*.
4. **What the owner still carries that the owner half does not say.** The **principle check**, asked
   **unconditionally**: is there a consequence of merging that this PR's owner half never states? It
   is scoped to the **principle only** — the review seat owns the omission floor's presence match, and
   you do not re-run it. When the answer is not `None`, that consequence goes into the **owner half**
   too, not only here. There is **no floor-green precondition**.
5. **Degradations.** Everything that cost something promised — in the build, and in **your own vet**
   (a probe you could not run, a surface you could not reach, a window that closes with your session).
6. **Accounting, with attribution.** Orders dispatched and reworks, each blocking finding attributed
   to **order quality**, **implementer execution**, or **the orchestrator's own integration/assembly**
   (external or unknown where none fits); the **park/refusal** rate with whether each was correct; and
   your own **receipt-integrity catches** — claims that did not reproduce when re-run against the
   world. Each record **names its window**. **Zero of either guard is a signal to inspect, never a
   clean sheet:** both are prose, so an agreeable model drives either rate to zero and it reads as a
   clean batch. Inspecting means re-reading a sample of that batch's park and vet receipts, not
   noticing the zero.

   This inspects the **verifier's** agreeableness — a different axis from the charter's park-rate
   and receipt-integrity guards. **A panel's confirmation rate is inspected the same way.** The
   round receipt does not today carry per-pass verdict totals, so where the rate is not derivable
   from the durable artifacts record that plainly — **`not derivable from the receipt`** — rather
   than guessing: the receipt carries neither the per-pass verdict totals nor, on a converged
   delta path, any surviving findings at all. Where a rate **is** visible — because the build
   recorded one in its own build record —
   a verification pass whose verdicts come back **uniformly confirming** — every finding
   CONFIRMED, over a large surface — is still a **signal to inspect**, not a clean panel: an
   agreeable verifier and a genuinely sound batch produce the same number, and only reading a
   sample tells them apart. Record what the rate was and what you did about it.
7. **Dispositions — completed, and pending.** **Completed first**, because that is the primary path:
   this PR's follow-ups are dispositioned at *this* vet, before this receipt posts. Under
   `**Dispositions — completed.**`, write one bullet per build-record id, `- FU<n>: <disposition>`.
   The disposition begins with one of `fixed` (in this PR), `filed #<n>`, `folded into #<n>`,
   `collector <pointer>`, `declined` with its revisit trigger, or `info` — e.g. `filed #12` or `collector 574`.
   `filed #<n>` stands only when the owner's word for that filing exists, and the bullet names where
   it was given (e.g. `filed #12 (owner's word: <link>)`), or when a canonical exception in
   `skills/showrunner/reference/owner-decisions.md` § The tiers and the filing rule already covers
   the filing — name which exception applies and where the word was given. Anything else stays
   `collector <pointer>` until the word lands. Then
   write one marker line with the same ids, `<!-- superheroes:dispositions FU1 FU2 -->`, or
   `<!-- superheroes:dispositions none -->` only over a `none` build record. Other completed items
   may follow as prose. The slot writer compares the two markers and refuses the owner-half write
   when an id has no disposition, when the receipt lists an id the build record lacks, or when
   `none` sits over a list. Then the
   **pending** set under `<!-- superheroes:pending-proposals -->` — only what genuinely could not
   close in this session. Every owner call is appended to the collector at vet time,
   unconditionally, so the collector is the complete register by construction; owner attendance
   governs only when discussion happens — attended, the item is proposed in the vet-delivery message
   and may be struck minutes after it was appended; absent, it awaits the batch. The receipt
   therefore records an **append that already happened**, never a promise to append — **except where
   the collector pointer could not be resolved**: then the receipt carries the item **and** the
   disclosed degradation, and the item keeps **this vet's ordinal as its proposing ordinal** for the
   later deferred append. Every append carries the door grading and venue recommendation that
   `skills/showrunner/reference/owner-decisions.md` § Craft calls and owner calls defines.
   **Known limit, carried knowingly:** the slot writer checks that the two marker lists agree; it
   trusts each marker as its author's declaration and reads no prose, so the vet reads the prose
   against the marker. Nothing mechanical checks that an append names a door grading and a venue. A
   reader who wants to know that can only read the receipt. Each pending item carries
   **what it is**, **your recommendation** (so the owner's batch pass is one word rather than a
   re-derivation), and **the vet ordinal it was proposed at** — a monotonic integer, one per vet,
   assigned at the vet that proposed the item (the same vet when proposed and appended together; the
   earlier proposing vet when an append was deferred). **State this vet's own ordinal alongside the
   pending set**, so
   the sequence is readable from the receipt itself. **An item's ordinal is never re-stamped** when it
   is carried forward: age is `this vet's ordinal − the item's ordinal`, a subtraction over written
   numbers rather than a count of artifacts, which is what makes it immune to receipts being edited in
   place. **Never the future tense** — "I'll file X" is not a disposition.
8. **Open owner calls at merge.** What the owner must decide before or at the click, each stated as a
   consequence rather than a craft question.
9. **Lane.** The lane the PR ran — `full`, `light`, or `micro` — read from the issue's recorded lane
   call (from the PR itself for micro), with a one-line note when the build escalated, naming the
   lane it moved from and the lane it moved to. It exists so the gardening pass can read misses by
   lane.
10. **Misses-log appends.** Each misses-log append this vet made — what it was, and its class:
    declined-then-escaped, launched-then-regretted, mis-tiered, review escape, or [false PR claim](../../../rubric/glossary.md#false-pr-claim) — or `None`. The misses log's home and classes are
    `skills/showrunner/reference/owner-decisions.md` § Every grading keeps its scoring, and the
    misses log.

## Triggered fields — the artifacts raise them, not your memory

Above the spine sit fields that **the PR's own artifacts** raise. The full inventory of loads runs to
about nineteen items: nineteen always-on fields become a form and get hollowed out, while plain
conditional fields reintroduce the silent omission this shape exists to kill. The way out is that
**every trigger below is a fact greppable in the artifacts**, so the artifact raises the field and you
are never holding the inventory in working memory.

| When the artifacts show… | the receipt owes |
|---|---|
| the diff adds a **gate, hook, or enforcement mechanism** | the ratified-precondition citation, and the evidence it is met |
| dispatch provenance shows **sequential orders against one worktree** | the commit-between-orders check |
| provenance names a **seat under a standing counter** this project keeps | that counter's line |
| the body carries **headline before/after numbers** | reproduction, by you, not a restatement |
| the issue carries a **show it** call | the show-it check (and the timing consequence duty 4 sets out) |
| the issue carries a **lane call** | the lane-call backstop, **both directions** |
| the PR carries a **build record** (a full or light build) | the **size-tripwire check** — the build record's size tripwire row against the non-test count at each commit in the PR's history and the build's starting estimate, both as `rubric/review-discipline.md` § Size defines them; a crossed row cites the issue record its form names; a missing row is a finding. The row's forms live in `skills/workhorse/reference/handback.md` § The size tripwire row |
| a **prior receipt on this PR is being corrected** | a dated correction, **edited in place** — never a superseding comment |
| the collector holds an item whose **proposing ordinal is two or more below this vet's ordinal** | an **escalation line** naming that item and stating plainly that **the owner batch is not happening** |
| the vet's evidence includes an **observed-in-the-field failure** — a real incident, a field report, or a reproduction — rather than a hypothetical. | the **revisit-registry scan** — read the project's revisit-trigger registry (the pinned comment on the collector issue) and state whether this vet's evidence fires any recorded revisit trigger, naming the row if it does. Cite the registry's canonical home, `skills/showrunner/reference/owner-decisions.md`. |
| the PR carries a **decomposition package** (a package-read audit trail in its diff) | the **filing dry-run citation** — the audit trail's `Filing dry-run` section, cited before the merge word is asked for. The rule's one home is `skills/showrunner/reference/decomposition.md` § The verification pass |
| the PR is a **child of a spec package that has a contract register** | the **register-conformance row** — the change conforms to the register, or the drift is disclosed; undisclosed drift is a blocker |
| the PR carries **iPhone evidence**, or the issue's done-definition names an **iPhone check** | the **iPhone-evidence row** — each piece valid or invalid with its reason. When the issue names the check, add whether the check is complete by the conditions in `skills/showrunner/reference/vetting.md` § iPhone evidence, and if not, the advisor's own iPhone check, recorded before the ruling |
| this vet is the one whose merge closes the spec's last open child (or whose close, where the last open child closes without a PR), or for a stacked feature the vet `skills/showrunner/reference/closure.md#when-closure-fires` § When closure fires names | the **closure receipt** — on the merge path it rides this same receipt in the same sitting; its elements live at `skills/showrunner/reference/closure.md` |
| the PR carries a **build record** (a full or light build) | the **review record checks** — one line per check, saying what was read from the record and whether it held the PR; the six checks are the rows of [The review record checks](#the-review-record-checks) |
| the review record carries `commandRefusals`, or the build record's dispatch provenance lists a refusal | a **refusals line**: each refusal was read, and any refusal followed by the same act in another form, by any seat, as the stop rule and the session rule define that, is named as a **finding**, without listing the forms, unless a sanctioned retry covers it (`SANCTIONED_RETRIES`): a covered re-take is named as a sanctioned re-run and graded on that entry's seats, conditions and disclosure, and one that misses any of them is a finding. The rule's one home is `lib/command_refusals.py` |
| the `vet-checks` verb reports `declared: true`, or any non-null `reason` | one receipt line per declared check, and a finding per malformed entry or unreadable calibration — see [Project vet checks](#project-vet-checks) |
| the review record shows a finding still **open at handback** (the review stopped at its round cap, or handed back as it does at the cap) | the **handback with open findings** — the craft list and the cap choices, as [A handback with open findings](#a-handback-with-open-findings) says |
| you wrote PR-body lines recording an owner acceptance, or applied a builder's posted body correction | the **advisor-applied body lines** field, as [Recording an owner acceptance — the advisor writes it](#recording-an-owner-acceptance--the-advisor-writes-it) says |
| the review record carries `outsideThisPR` | the **outside-list row** — every hit sorted into a proposed follow-up filing or a dismissal with its reason, as [The outside list](#the-outside-list) says |
| the PR body claims tests ran or passed, carries a definition-of-done table, or claims the verify command passed | the **claims check** — each such claim listed with holds or does not hold and its evidence, as [The claims check](#the-claims-check) says |

Where the last open child closes without a PR there is no vet receipt to ride; the receipt
reaches the owner by the no-PR presentation rule in `skills/showrunner/reference/closure.md`.

Every owner call is appended before this receipt posts; the collector-escalation row is the tripwire
when items still live only in receipts or age without owner batch — **not** a substitute for the
append-always rule at attended vets. Each pending item's **proposing ordinal** is what makes its age
inspectable — a subtraction against this vet's ordinal, not a count of anything — so the escalation
is raised by a number the artifacts carry rather than by your memory of having carried the item.

**Known limit, carried knowingly:** a trigger is weaker than a check. A build record that omits a
sequential-order run raises no field. You read the diff too, so the trigger is a second chance rather
than the only one — but it is not a guarantee.

## The review record checks

Every review ends by writing a review record on the PR. The record's home, its fields and the
`read` verb are `skills/review-code/reference/review-record.md`; this section says only what the vet
reads from it. At a full or light vet, read the latest record with
`python3 -B "$ROOT_DIR/lib/review_record.py" read --pr <n>` (`$ROOT_DIR` is `${CLAUDE_PLUGIN_ROOT}`)
and grade the six checks below. **A PR that any row holds is not returned as ready**, and the
receipt names the row that held it.

| Check | What it reads from the record | The PR is held when |
|---|---|---|
| **The record exists** | the result of the `read` verb, and the record link in the PR's build record | `read` refuses, with `review-record-missing`, `review-record-unreadable` or any other reason; or the PR's build record names no record; or the record carries `transitDamage` or a non-empty `earlierRecordsNotChecked` and the vet has not read each named record's comments directly and confirmed that no finding went missing or changed its meaning (the receipt says what was read) |
| **The checks ran on the final commit** | `finalCommit.sha` and `finalCommit.source`; `missingReviews` and `parked`; and, from the PR itself, its head now and CI on that head (spine field 1). The record's stored `ci` (`ci.state`, `ci.sha` and `ci.source`) is history shown on the sheet and never holds the PR by itself | the head-coverage outcome (the paragraph under this table) is not `READY`; `finalCommit.source` is neither `GitHub PR` nor `reported by the session; the PR head had moved past it`; or an entry of `missingReviews` has a null `goAhead` (`parked` is true), so a planned review did not run and the owner gave no go-ahead; or its go-ahead cannot be followed to an owner-attributed record (a standing ruling's canon entry, or the place the owner's words were said) that authorizes skipping that review |
| **No leftover skipped the owner's review** | every entry of `findings` (its `title`, `body`, `consequence`, `outcome` and `reason`), `leftForOwner`, `listedForMerge`, and the PR's owner half | a finding with a real consequence has outcome `craft`, or has no outcome and is neither listed nor a Minor or Nit that waits (both are read below); or has outcome `ruling` and its `reason` names no ruling the vet can follow to a record (where the decision it cites is an owner-ruling, a scope-ruling or an advisor-bound, the vet reads the link the citation holds; for an advisor-bound the vet also confirms the contract under review was prose and the final round raised no new Critical or Important finding); or has outcome `left-for-owner` and the record does not list it, or is a Minor or Nit with no outcome that waits (`leftForOwner` names it), and is shown to the owner neither as a card on the PR's sheet, nor as a line under the card on the sheet that carries it (a leftover, item or list-item card; the sheet input's leftovers entry for it names that card by its carriedBy reference, and the card shows it in its carried section), where that card asks exactly the decision the finding asks: the vet reads the finding's consequence against what the card asks the owner, for a choice card its question and options and for an Accept card (one with no options) its question and its If left, which is what the owner accepts, and a card whose answer does not settle that consequence does not carry it (only then do the card's answer and the merge verdict cover it), nor as an entry of the sheet's decided-for-you list, nor, on a stack sheet, in its caught list as fixed above in a higher layer of that stack, nor, where no sheet is built, under the owner half's `## What we're accepting`; or is a finding the record lists (`listedForMerge`; which findings it lists is [the review record's rule](../../review-code/reference/review-record.md#what-reviewed-means)), which needs no card, and is shown neither in the sheet's listed part nor, where no sheet is built, in the record's summary; or is a listed finding the vet judges misgraded (its severity understated, or its file in a declared risk area the stamp missed) and has not been raised to the owner as a card, because the vet raises any listed finding it judges misgraded; or is shown as fixed above and the vet cannot follow the named layer and commit to a higher PR of the same stack whose history holds that commit; or is an entry of the sheet's decided-for-you list and has a real consequence that none of [the template's grounds](../../../theme/review-template.md#decided-for-you) covers, names no ground, or re-grades a finding the owner already answered or took back on this PR |
| **The proven copies match their source** | the record's `provenCopies` and every copy the head-coverage check relied on (each `{file, source, sha256}`); a regenerated file counts only on the vet's own re-run whose output is the head blob | the record carries `provenCopies`, or the check relied on a copy, and the vet has not read each named `source` where the proof names it and compared its sha256 with the entry's `sha256`, or a source cannot be read, or its sha256 does not match (the receipt says, per copy, what was found) |
| **A merged finding's fix is its own** | every entry of `findings` whose `outcome` is fixed and whose `reason` holds ` (merged into …)`, with its `title`, `consequence` and `body`, and the fix at the record's `finalCommit.sha` | the vet has not read each such finding's own title and consequence against the fix and found its own part fixed at that commit (the receipt names each one read and what in the fix covers it) |
| **A fix's scope note has a call** | every entry of `findings` whose `outcome` is fixed and whose `reason` holds "listed for the vet", with its `title`, the note after those words, and the fix at the record's `finalCommit.sha` | the vet has not read each such note's extra change at that commit and recorded one call for it in the receipt's scope-notes field; or a call is held; or a call put to the owner is not shown in the owner half's *what is theirs to decide* |

**The head-coverage outcome.** The vet writes what `review_record.py read --pr <n>` prints to a file and runs `lib/head_coverage.py check` with `--base` (the PR's base tip, or the head of the layer below for a stack layer), `--record` (that file), `--head` (the PR's head now), `--repo-root`, `--proof` for every copy or regenerated file it relies on, and `--union-proof` for a tested-union proof the vet recorded (the next paragraph). For a stack layer whose layer below was rewritten after the review, the vet adds `--base-at-review` as `skills/showrunner/reference/merge-train.md` § Merging a stack item 4(g) says; a head that no longer fits is ignored, so adding it never costs anything. It then runs `lib/head_coverage.py outcome` with the check's answer and CI on the head now, and the row holds unless the outcome is `READY`. On `judgement` the vet reads every hunk the check lists and passes `--judged-clear` only when none changes meaning; a `judgement` with why token `conflict-fix` is read by the test of the paragraph **A builder's code-conflict fix.** below, not by the meaning test that follows. A hunk changes meaning when it touches product code, a test's assertions or fixtures' expected values, prose that states a rule a session or a gate follows, or a claim the PR makes, or changes behaviour in any other way (configuration, CI, a hook, or test code beyond its assertions, such as a skip mark, a removed test or a changed input). A hunk the vet cannot call non-semantic counts as changing meaning. On `needs-review` the PR goes back for a returning-round review of the listed files, and a stack layer is judged on its own diff and never waits on the layer below. The receipt names the answer, the files and every hunk read.

**A tested-union proof.** When the vet merged the PR (the commit the record certifies, or the published sheet's commit) with its base, or with a PR about to land in it, to test the union, and ran the tests on that merge, it records the run so a later bring-current identical to that merge keeps the owner's word. To record it, commit the merge as the probe; keep a ref to it so git can still read it at the check (for example `refs/superheroes/union-probe/<pr>`, never pushed); run the test command in a clean detached worktree of the probe, with `git status --porcelain` empty before and after; read the tree there with `git rev-parse HEAD^{tree}`; and write the proof file beside the record file with that command, its real exit status and that tree, as `{"schema": "union-probe/1", "probe": <the probe's full sha>, "tree": <that tree>, "base": <the full sha of the commit the probe merged the PR with>, "receipt": {"command": <the test command>, "exitCode": 0, "tree": <that tree>}}`. Quote the proof file in the receipt. A run that was not clean, did not exit 0, or ran on another tree records no proof. The check never takes the proof's word for the run: it asks git. The proof is consulted only when the check without it does not answer `proven`, the record is an ok, unabandoned record with a full final commit sha, the inputs are valid and the diff is readable; otherwise it is not consulted. Git then checks, in order: the proof has the shape above; the receipt has exactly the keys `command`, `exitCode` and `tree`, a non-blank command, exit code 0, and the same tree as the proof; the check's `--base` is exactly the proof's `base` commit (a base with an equal tree does not count, so a probe against a PR about to land carries only when the head's base is that same commit, and when landing made a new commit the vet probes again on the new base); git reads the probe as a commit; git's tree of the probe is the proof's `tree`; the probe has exactly two parents, the base and one other commit P, and P is the commit the record certifies or a commit the check itself, run from the certified commit to P with no union proof, answers `proven`; the base is an ancestor of the head; and the head's tree is git's tree of the probe, which is identity of every file byte for byte and mode for mode. Only when all of these pass is the answer `proven`, with why token `proven-union`, and the result's `unionProbe` lists `covers`, the files the check had left. Otherwise the answer is exactly what it was without the proof, with a why line `union-probe-ignored: <probe> <reason>`, so a proof never makes an answer worse. The reasons are `malformed`, `no-receipt`, `other-base`, `probe-unreadable`, `tree-unconfirmed`, `other-commit`, `head-not-current` and `other-tree`, and `not-consulted` when the proof was not consulted; the result carries `unionProbe` only when a proof was given. An unreadable proof file is a usage error. Pass the same `--union-proof` on the coverage check and on the carry check (the second `check`, from the sheet's commit, as `skills/showrunner/reference/merge-train.md` § Merging a stack item 6 says), so one probe of the sheet's commit serves both. When the carry answer is `proven` through the proof (`proven-union`), the republished sheet's `carriedForward.whyNotMaterial` names it: the head's tree is the vet's tested union probe, with the probe's and the base's short shas and the receipt's command. The receipt names the proof file, the probe, its tree, its base, the receipt's command and exit status, and the check's `unionProbe.covers`.

**A builder's code-conflict fix.** When every new commit is the builder's merge of the base into the PR and the only thing that kept the answer from `proven` is a code conflict the builder fixed by hand, the check answers `judgement` with why token `conflict-fix`. Each listed hunk is git's own automatic merge of the file, conflict blocks and both sides included, shown as `-` lines against the builder's merge as `+` lines, with `merge`, `parents`, `mergeBase` and `kind` naming the merge it was read at. The vet reads each hunk against both sides and passes `--judged-clear` only when the resolution combines the two approved changes (the PR's reviewed change and the base's change) and adds no behaviour of its own. A resolution line need not appear on either side: a line written fresh to hold both changes (the PR's edit and the base's edit to one expression, written as one expression) combines them. For example, when the PR changed `subtotal += item.price` to `subtotal += item.price + item.tax` and the base changed it to `subtotal += item.price - item.discount`, the resolution `subtotal += item.price - item.discount + item.tax` is on neither side and is not material. A hunk is material when it drops either side's change, adds behaviour that neither approved change brought (a new branch, call, value or condition), or is one the vet is unsure about; unsure is material. A material call takes the existing path: the PR goes back to its builder for a scoped returning review of the merge, and the sheet is republished unsigned. The vet passes the same `--builder-author` (the builder's own commit email, read from the build's commits) on the coverage check and on the carry check, since the carry check's fallback is the author of the sheet commit. When the carry is a cleared `conflict-fix` judgement, the republished sheet's `carriedForward` carries `conflictFix`, the vet's one-line reason (what the resolution combined), and `whyNotMaterial` says the same. The check rebuilds git's merge with `git merge-file`, so it may list a line git's real merge made, never fewer lines than the builder typed; the vet reads such a line like any other. The receipt names the answer, every hunk read (file, header and merge sha), the call on each, and the one-line reason.

**A text flagged as changed in transit is graded from its source, never from the GitHub copy.**
A flag is a record's `transitDamage` (`sentHashMatches: false`, the parts' `hashMatches: false`, or
`redactedFields`), or a `Transit damage:` or `Transit check: not checked` line in the build record
or the handback. Grade that text from the committed file, the engine artifact or the run directory
it was made from, and say in the receipt which source you read. A flagged text you cannot reach
holds the PR as the row it belongs to says.

**A fix's scope note gets one call.** A fixed finding whose `reason` holds "listed for the vet" is a
fix the audit ruled right that also changed something its finding does not name, and the review did
not review that change. Read the note, then read the change itself at the record's
`finalCommit.sha`, and make exactly one of three calls, graded against the
[owner-vs-craft line](../../../rubric/owner-vs-craft-line.md) with doubt resolving upward:

1. **Accepted as craft.** The change is right and carries no
   [material consequence](../../../rubric/glossary.md#material-consequence). Its line in the field
   below is the whole record.
2. **Held.** The change is wrong, or you cannot tell what it does. The row holds the PR, so it goes
   back to the builder, and the receipt names the row and the finding.
3. **Put to the owner.** The change is right but has a material consequence that is the owner's.
   Record it under `**Open owner calls at merge.**` too, framed as
   `skills/showrunner/reference/owner-decisions.md` § The per-item spine says, and write it into the
   owner-half slot's *what is theirs to decide*.

The receipt records every call in one fixed field, `**Scope notes.**`, one bullet per such finding:

```markdown
**Scope notes.**
- <finding id> · <title> — craft | held | owner — <what the extra change does, and why this call>
```

A record with no "listed for the vet" reason needs no line for it: the vet writes no field.

**Whether a seat read its calibration is read from the record's own fields.** Read it from that reviewer row's `calibrationRead`, and, for the test lens, from the record's `testLens`. Never read it from the seat's `investigated` array: the sanitized view tells every seat never to list those absolute paths there, so "no calibration file in `investigated`" holds of every seat, calibrated or not, and is not evidence of anything. A `calibrationRead` entry of `unknown`, and a row or record that reads unmeasured, are not "did not read". The review record checks have no row for the calibration read, and this paragraph holds no PR on its own.

**A `judgement` answer, worked.** The record certifies commit A, and the builder then pushes commit B. **Cleared:** the check answers `judgement` and lists one hunk, which rewords a code comment and changes no claim. The vet reads it, passes `--judged-clear`, and with CI green on B the outcome is `READY`. **Holding:** B instead changes the expected value in one of a test's assertions. The vet cannot call that hunk non-semantic, so it does not pass `--judged-clear`, the outcome is `NOT-READY`, and the PR waits for a returning-round review (workhorse §12's second row).

A `ruling` whose reason starts `owner ruling "<words>" (<url>)` is followable. The vet opens the link and checks that the comment is the owner's ruling covering that finding and that no later owner decision overturned it. For every `ruling` outcome, whatever decision it cites (an owner ruling, a scope ruling, the advisor's bound, or a ruling named only in its reason's prose), the vet also reads that decision's words, because the record settles the finding without reading them: where the words order a fix in this PR, the vet confirms that fix holds at the record's final commit and, when the PR head differs from it, on the head being vetted too. Words that send the fix to a follow-up or another PR order nothing here, and the row reads that decision as written. If any of these fails, the row holds the PR.

**Withheld paths are checked by hand.** The vet reads the record's `withheldFromReviewers`. No external
reviewer read a listed path in full, so the vet reads each listed file itself and the receipt says what it
found. `[]` needs nothing. `null` means the changed files were not read, and the vet checks every changed
agent or IDE configuration path by hand.

**A real consequence is graded, never read off one field.** A real consequence is a
[material consequence](../../../rubric/glossary.md#material-consequence). Grade each finding from
its `consequence` and, where that is null, from its `title` and `body`, against the
[owner-vs-craft line](../../../rubric/owner-vs-craft-line.md). A null `consequence` never makes a
finding craft. When you cannot tell, the row holds the PR: doubt resolves upward. A finding with
outcome `fixed` or `shown-wrong` needs no owner, and the row does not hold on it.

**A left-for-owner finding is shown** under `## What we're accepting` only when a line there carries
the finding's id and its title. On a PR sheet it is also shown as an entry of the sheet's decided-for-you
list, which [the review template](../../../theme/review-template.md#decided-for-you) describes, or as a line
under the card on the sheet that carries it (named by the finding's `leftovers` entry; which cards can
carry, and the forms that name them, are in the docstring of `lib/pr_sheet.py`) when that card asks exactly the decision the finding asks (the row above says how the vet reads it); the card's answer and the
merge verdict then cover it. The advisor
never re-grades a finding the owner already answered as a card on this PR, or took back with "Make this
mine" on this PR, so an entry for either holds the PR.

A line that carries `fixed-above #<PR> <commit>` with the finding's id and title shows it as fixed above
(on a stack sheet it lands in the caught list). The id and the title are matched under the rule's
normalisation (`lib/leftover_accepting.py`). The vet opens the named layer's PR and confirms the commit is in
its history; the command checks only that the layer is a higher member of the stack, so the commit is the
vet's to follow.

**`status` is not the test.** A record whose only open lines are leftovers shown to the owner reads `awaits-owner`, and one with a go-ahead for a review that did not run reads `not-reviewed`; either can still be returned as ready. A record that reads `awaits-owner` is read exactly as `not-reviewed`: it says only that every open line is a finding left for the owner, and it clears nothing. A `reviewed` record may carry listed findings (`listedForMerge`), and the leftover row still reads them. A
record whose finding with a real consequence was decided as craft reads `reviewed` and is held. Read
the fields the rows name. Any line of `whatIsMissing` that the six rows do not account for is a vet
finding. The line saying no planned reviewer ran is never accounted for: at least one reviewer runs on
every PR, and a go-ahead covers a planned reviewer that did not run, never the last one
(`skills/showrunner/SKILL.md` duty 6). A record written before CI left the certificate may hold a line saying CI was pending or none on the final commit; it is accounted
for once the head-coverage check covers the PR's head now and CI is green there. The line saying a finding waits for the owner's decision is
accounted for when the third row finds that finding shown to the owner, or shown as fixed above. Any other line of
`whatIsMissing` holds the PR, and the receipt names the line. The line naming a withheld certificate ("the review session ended <terminal>, not converged, so its certificate was withheld: <cause>") is accounted for only by the owner's go-ahead over it, which the vet follows as it follows any go-ahead, and the receipt names it. A record whose owner-choice hand-back qualifies carries no such line and needs no go-ahead over it, as [the review record](../../review-code/reference/review-record.md#what-reviewed-means) says.

**A go-ahead is followed, not trusted.** The record proves only that the go-ahead's citation is a
non-blank string. Resolve it yourself: open the standing ruling's canon entry, or the place the owner's
words were said, and confirm it is the owner's and covers the skipped review. When it is missing,
unreadable or about something else, the row holds the PR.

**When a go-ahead lets the PR through**, the receipt names the review that did not run, the
go-ahead that covered it, and the record you verified it against.

The vet carries these checks. Nothing automated runs them at handback.

## A handback with open findings

A review stops at its round cap and hands the PR back with every finding still open, Important and
Critical alike; a fix that keeps failing its audit hands back the same way. Three rounds run past the
cap, and no others: [the bounded pass](../../review-code/reference/round-driver.md#the-bounded-pass)'s
audit of the cap round's fixes (round `cap + 1`), its audit of its one fix (round `cap + 2`), and an
ordered extra audit round a saved state holds (round `cap + 1`). A session stops at the cap in four
ways: `round-cap`, `extra-audit-open`, a `bounded-pass-open` of a pass whose trigger is `round-cap`,
and a converged `round-cap` bounded pass. A pass begun by a fix that kept failing below the cap is
not a stop at the cap. Nothing from the review
reached the owner while it ran, so this vet is where each open finding is settled. Read the open
findings from the latest review record and grade each one's consequence as
[The review record checks](#the-review-record-checks) grade a real consequence: against the
owner-vs-craft line, with doubt resolving upward.

**A finding whose only consequence is code quality is yours to decide.** Decide it, and list it in
the receipt under `**Decided for the owner's veto.**`, one line each: the finding, what you decided,
and why. A finding the review record already settles as craft is listed for the owner's veto on the
PR's sheet by its folded part of craft decisions put to the owner's veto. A left-for-owner
finding you grade as code quality only is an entry of the sheet's decided-for-you list
([the review template](../../../theme/review-template.md#decided-for-you)), written in the sheet
input's craftDeterminations. A finding the record shows with no outcome cannot be put on a sheet; it
holds the PR until the record settles it. Where no sheet is built it is a line under the owner half's
*what accepting it means*, saying what you decided and that the owner can take it back. It never
reaches the owner as a question.

**A finding with a real owner consequence takes one of two next steps, and you choose which.** The two
apply to a session handed back with last decision `round-cap` or `fix-keeps-failing`. A session handed
back `bounded-pass-open` takes the same two next steps. A cap round with unaudited fixes is handled by
[the bounded pass](../../review-code/reference/round-driver.md#the-bounded-pass), so no extra audit
round is ordered. A session that ended `converged` as a bounded pass has no handback, and the
`left-for-owner` cards the pass settled are settled at the vet like any leftover: grade each one,
decide a code-quality finding for the owner's veto, and take one of the two next steps for the rest.

1. **A leftover for the owner.** The finding goes to the owner, framed in owner terms as
   `skills/showrunner/reference/owner-decisions.md` § The per-item spine says for a leftover. Its
   outcome in the record is `left-for-owner`, and the third row of the review record checks holds
   the PR until the owner is shown it.
2. **A rethink.** The PR goes back to the builder to rethink the approach, not to patch the finding.
   The record of the PR's next review session shows whether the rethink converged.

**An open Critical is never a leftover.** It goes to a rethink.

**The cap-choice field.** The receipt records each choice in one fixed field, `**Cap choices.**`,
which the gardening pass counts. Under it, each choice is a bullet followed by its own marker line:

```markdown
**Cap choices.**
- <finding title> — <choice> — <why>
<!-- superheroes:cap-choice choice=<choice> vet=<this vet's ordinal> record=<link to the review record> key=<findingKey> -->
```

`choice` is `leftover` or `rethink`. A receipt may carry a third spelling, `extra-audit-round`, which
no new choice writes and which the gardening pass reads. `key` is
the finding's stored `findingKey`, copied exactly from the review record, and runs to the end of the
marker line; never the finding's `id`, which is the reviewer's own and can repeat. `record` is the
review record the choice was made against. A posted line is never removed or rewritten, even when
the receipt is edited in place: a later vet's choice for the same finding, such as a rethink for a
finding first left for the owner, is a new line in that vet's receipt, carrying that
vet's ordinal. A receipt that records `leftover` for a Critical is a defect in the receipt. A vet
with no open finding that has a real owner consequence writes no field.

**Recording a scope ruling or the advisor's bound.** When a finding was settled by an out-of-scope
ruling or by the advisor's bound, the vet may record it in the receipt so a review record can cite it.
Each is a bullet with the words, then its marker line on the very next line:

```markdown
- <the words of the ruling>
<!-- superheroes:scope-ruling key=<findingKey> -->
- <the words of the bound>
<!-- superheroes:advisor-bound rounds=<n> -->
```

`key` is the finding's stored `findingKey`, copied exactly from the review record, and runs to the end
of the marker line. `rounds` is the bound's number of rounds, a whole number from 1. A review record's
`decidedBy` of kind `scope-ruling` or `advisor-bound` cites them by the receipt comment's permalink and the
bullet's words; the record writer reads that comment, and the words must be at least 12 visible
characters and sit on the nearest non-blank line above the marker line. Text elsewhere in the receipt
never counts as a ruling or a bound.

## Recording an owner acceptance — the advisor writes it

When a handback rests on the owner's acceptance of something the builder could not finish (an
uncertified review, a waived check, a park the owner lifted by their word), **you write the PR-body
lines that record that acceptance, and you mark the PR ready for review (out of draft).** Never order
the builder to write them or to mark it ready for review: a builder's permission check judges the edit from its text alone and refuses it
as merging without review, so the order parks. Each line names the owner's words and links the
record of the ruling. Any other body correction the builder owes, it posts as text on the issue, and
you apply it word for word, changing nothing. These are builder-body edits you make outside the
slot, alongside the others this file names.

**The receipt names it.** Under one field, `**Advisor-applied body lines.**`, list each line you
wrote with the ruling it records, and each builder correction you applied with a link to the
comment that carried it. A vet with no such line writes no field.

## The outside list

A reviewer that noticed a real defect on lines the change did not touch raised it as an
[outside finding](../../../rubric/glossary.md#outside-finding). The review record lists them under
`outsideThisPR`, and the review never fixed them. Read the list from the latest review record and
sort **every** hit, reviewer entries and sweep entries alike, into one of two choices:

1. **A proposed follow-up filing.** A proposal only. Append it to the owner's pending calls as
   `skills/showrunner/reference/owner-decisions.md` says for an owner call: an entry in the owner's
   pending calls, not a card on the PR's review sheet. Nothing is filed until the owner's word; this
   vet files nothing.
2. **A dismissal with its reason.** The hit is not worth an issue, and the receipt says why.

An outside finding never holds the PR, never becomes a cap choice, and never reaches the owner as a
card on the PR's sheet.

**The outside field.** The receipt records the sort in one fixed field, `**Outside this PR.**`, one
bullet per hit:

```markdown
**Outside this PR.**
- <hit id> <file>:<line> · <title> — follow-up | dismissed — <the proposed issue's one-line scope, or the reason>
```

A list not sorted in full, meaning a hit of the record that the field does not carry, is a vet
finding. A vet whose record carries no `outsideThisPR` writes no field.

A sample for a fixture PR with two hits:

```markdown
**Outside this PR.**
- O-1 lib/cloud_check.py:212 · The retry loop never stops on a permanent error — follow-up — Stop retrying on a permanent error and report it, in `lib/cloud_check.py`
- O-2 lib/cloud_check.py:340 · A helper's name no longer matches what it returns — dismissed — Nothing calls the helper any more, so no one is misled by its name
```

## The claims check

The vet checks what the PR description claims against the change and its runs. Read the PR body for
three kinds of claim: each claim that tests ran or passed, each row of its definition-of-done table,
and each claim that the verify command passed. List every one in the receipt under
`**Claims checked.**`, one line each:

```markdown
**Claims checked.**
- <the claim, quoted or named> — holds | does not hold — <the evidence>
```

The evidence is what you read or ran: the CI run on the vetted head, selected as spine field 1 says;
the test or file in the diff; a run you made yourself; or output the build record quotes, checked
against the run it names. A row of the definition-of-done table holds only when the evidence it
points at shows the outcome the row claims. **One line saying the claims were checked does not meet
this**, and neither does a list that leaves a claim out. A claim you cannot check either way is
listed as does not hold, with what was missing. A claim that does not hold is a finding, and it
holds the PR.

## Project vet checks

The `` ```json superheroes-core `` `` block in `core.md` may carry an optional `vetChecks` key: a
JSON list of objects, each with exactly `name`, `evidence`, and `records` (non-empty strings);
check names must be unique; `[]` means zero checks. It is the enforcement home for rules whose
evidence lives in the PR body or a ledger — surfaces review seats cannot read. **This section
defines the shape only.** Encoding checks is the project's work, done through `configure`.

Example (inside the fence):

```json
"vetChecks": [
  {
    "name": "Example check",
    "evidence": "PR body · Build record",
    "records": "what was read from the evidence and what the vet recorded"
  }
]
```

**Malformed reasons** — the authoritative closed set is the module constant
`VET_CHECKS_MALFORMED_REASONS` in `lib/core_md.py`; each token names which rule of the shape above
was broken. Malformed entries report as `{"index", "field", "reason"}`; when any entry is malformed,
`checks` is empty — never a partial list.

**Read verb.** From the project cwd:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/core_md.py" vet-checks --cwd .
```

It prints one JSON object and exits 0:

`{"declared": bool, "checks": [{"name", "evidence", "records"}, ...], "malformed": [...],
"reason": null | <token>, "detail": null | str, "behind": bool}`.

The key absent → `declared: false`, `reason: null` (no vet-check lines owed). When `reason` is a
calibration-read failure token (`core-md-absent`, `repo-root-unavailable`, `core-md-unreadable`,
`core-md-unparseable`, `multiple-core-blocks`, `duplicate-core-key:<key>`), `declared` is false and
both lists are empty. `vet-checks-malformed` comes with `declared: true`, the items in `malformed`,
and `checks` empty.

**How the vet acts on the read.**

- Each well-formed declared check → **one receipt line**: the check's name, what you read from its
  `evidence`, and what you record per its `records` field.
- `reason: core-md-absent` → no calibration file, so no vet checks are declared: **one plain
  receipt line** — **not a finding**.
- Any other non-null `reason`, or a non-empty `malformed` list → **findings** naming the token or
  each malformed index — never a silent skip.
- `declared: false` with `reason: null` → the key is absent; no vet-check lines are owed.

## The `None` convention

**Every spine field is filled or written `None`** — the literal word, the same convention *Follow-ups
for the advisor* already uses. Not blank, not omitted, not a dash. A **spine** field that is absent is
a defect in the receipt, because absence is exactly what a reader cannot interpret.

A **triggered** field that did not trigger is simply **absent** — and that is safe only because its
trigger is greppable in the artifacts, so any reader can re-derive whether it should have fired
without trusting the receipt's author.

The receipt stands without your context.

## The owner-half write — register

The receipt above is written for **you and the next advisor**. The `## Advisor vet` slot in the PR
body is written for **the owner**, and they are not the same document. Reproducing the full vet in
the slot is the failure this section names: the owner half is not the full vet, and a slot that
reproduces the vet buries what the owner is being asked to accept.

Four elements, in this order:

1. **The verdict.** Written in the verdict form of spine field 1, which is where that
   grammar lives: the slot's first line carries the token and the head sha.
2. **What was checked, in owner terms** — what an independent reader went and looked at, said as
   consequences rather than as mechanism. Not the probe list.
3. **What accepting it means** — what the owner still carries after merging.
4. **What is theirs to decide** — the open calls at the click, or `None`.

**One standing row writes into this half by name.** When the **standing anchor-coverage row**
fires — the diff introduces owner-perceivable new behavior that no approved decision covers — its
flag belongs **here, in plain language**: what the new behavior is, and that no approved decision
covers it. It is exactly what the owner is being asked to accept, so it is stated in the owner half
and not left in the receipt alone.

**Write the slot through the command, never by hand.** Put the slot text in a file and run:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/vet_slot.py" write --pr <n> --repo <owner/name> --slot-file <path>
```

The command reads the body and the latest vet receipt and checks the read, a non-empty body that
still holds the builder's owner half (a live `What's changing, and why` heading above the
`advisor-vet` marker: live means GitHub renders it, decided by a CommonMark parse of the body in
`lib/md_hidden.py`, and where the parse cannot be sure the write refuses `body-emptied`), both the
`advisor-vet` and `build-record` markers, the build record's
followups marker, and the receipt's dispositions marker. It re-reads the body before the push,
writes only between the two slot markers, and reads the result back. A refusal names its reason
(for example `body-emptied` (the body is empty or lost the builder's owner half: restore it from
the PR's edit history, never re-stamp into it; the one exception is a detail saying the parse could
not decide the render, where you move the text by hand instead of restoring),
`followup-undispositioned`, `disposition-unknown`, `none-over-list`, `markers-invalid`,
`slot-span-foreign-content` (another `superheroes:` marker, such as the DoD table, sits in the slot
span and the write would delete it), `slot-span-builder-text` (builder text sits in the slot span:
move it out or ask the builder to; nothing was written), or `read-failed`) with a detail
that says what was wrong, and writes nothing, except `write-unconfirmed`: the edit call was made (even
one that failed or timed out) but the readback failed or differed from the pushed body. `check --pr <n> --repo <owner/name>` runs the same
comparison with no write. The command exists because a hand-rolled write fails silently: a shell
redirect truncates the target file *before* `gh` runs, so a `gh` read that fails leaves an empty
file that the next `--body-file` pushes as the body. There is one write path, the command. Re-stamping a dropped
`advisor-vet` marker, or creating the slot on a pre-contract PR, is the advisor's own hand edit to its
own slot, made before the command runs. A build record that predates keyed follow-ups is keyed in
place first: the advisor numbers its existing items FU1.. in order with a class each, adds the
followups marker line, changes nothing else in the build record, and records that keying edit in
the receipt; the receipt carries the dispositions marker before the command runs, so the repair can
reach a successful write.

**Probes, accounting and dispositions are mechanism.** Where they belong in the slot at all they go
**collapsed inside `<details>`**, below the four elements, never above them; the pointer to the
receipt comment carries the rest. Consequence up, mechanism down — the same rule the PR body's own
two halves run on.

This register is the standing rule. Write to it, rather than to whatever the receipt happens to look
like.

## Markers

Three markers. Two are **written by the advisor at vet time**, after handback; the third —
`advisor-vet` — is **stamped by the builder** into the empty slot at handback, and you write beneath
it:

- `<!-- superheroes:vet-receipt -->` — the **first line** of the receipt.
- `<!-- superheroes:pending-proposals -->` — immediately above spine field 7's **pending** set (its
  body is the items, or the literal `None`).
- `<!-- superheroes:advisor-vet -->` — the boundary of your write inside the PR's `## Advisor vet`
  owner-half slot. The slot's **first line** is the verdict line, in spine field 1's form. **The builder stamps the marker for you** (workhorse charter §11), together with a
  reminder comment beneath it; you write **beneath the marker**, and your write **replaces the
  reminder**. The slot is **append-only and yours**: you edit your own prior text in place, never the
  builder's prose — with exactly one exception, **the reminder**, which is the sole piece of
  builder-emitted text you are expected to remove inside the slot (outside it, see [Recording an owner acceptance — the advisor writes it](#recording-an-owner-acceptance--the-advisor-writes-it)), and which you **must** delete once your verdict is
  there (a verdict sitting beside a standing reminder makes the signal read "owner-half write still
  owed" when it is not). **What the reminder detects is the hidden case:** a body rewrite that
  **re-creates the heading but drops your text** leaves the slot looking present and saying nothing
  — a slot carrying **neither** reminder nor verdict is a write that was dropped, distinct from one
  still carrying the reminder, which is a vet not yet written.
  A reminder still standing means the **owner-half write** is owed, not necessarily the receipt: you
  post the receipt first, so a failure between the two leaves the receipt posted and the reminder
  intact. Check for your own existing receipt comment before posting a second one. Before posting, run `python3 -B <plugin root>/lib/mention_guard.py check --file <receipt file>`; a `bare-mention` refusal names each token to drop the at-sign from. (A rewrite that drops the heading
  entirely is visible without either.) Marker-presence alone is **not sufficient** and no longer
  separates those two states: re-stamp the marker when a rewrite dropped it, and remember a slot can
  be marker-present and text-stale. The showrunner charter's **duty 4** backstop is where the check
  and remedy live — follow that, not a marker-keyed rule here.
  **A slot with no marker at all** is read against your own receipt, the same canonical copy duty 4's
  backstop uses: with **no receipt comment** on the PR it is a body written before the builder stamped
  it — read it as *not yet vetted*, and stamp the marker yourself when you write; with **a
  receipt already posted** it is a rewrite that dropped your verdict and the marker together —
  restore the verdict and re-stamp. The other dropped-write state is **marker present, reminder and
  verdict both gone**.

**No review seat checks these at review time.** A build's pre-handback review runs in branch mode,
before a PR body or a vet exists, so their absence during a review is the normal state and is never a
finding. (A CI drift test *does* read these literals — it pins them to the marker inventory in
`CONVENTIONS.md` §10.7 so the bytes cannot drift between copies — but that is a docs-consistency check,
not a consumer of the markers in a PR.) They exist so *your own* backstops have a grep anchor — above
all the age of a carried item, and the loss of an advisor write.

## Skeleton

Two artifacts, two skeletons. **The receipt comment:**

```markdown
<!-- superheroes:vet-receipt -->
**Vet — <verdict>** · commit `<sha>` · diff digest `<sha256 | digest-unavailable>` · CI <state>
· remote head verified <yes/no>

**What I probed.** <what bit; residue reverted> | `None`
**Calls accepted.** <call — why> | `None`
**What the owner still carries that the owner half does not say.** <consequence> | `None`
**Degradations.** <build's, and my own> | `None`
**Accounting.** orders <n>, reworks <n>, attribution <…>; parks/refusals <…, each correct?>;
receipt-integrity catches <…>; panel confirmation rate <rate or `not derivable from the receipt`>,
inspection <what you did>; window: <…>
**Dispositions — completed.**
- FU<n>: <disposition: fixed | filed #… | folded into #… | collector … | declined (trigger) | info> <…>
<!-- superheroes:dispositions FU<n> … --> | <!-- superheroes:dispositions none -->
<other completed items, as prose> | `None` (only over a `none` build record)
<!-- superheroes:pending-proposals -->
**Pending.** this vet's ordinal: <n> · <item — recommendation — proposed at ordinal <n>> | `None`
**Open owner calls at merge.** <…> | `None`
**Lane.** <full | light | micro> <escalated: from → to, if it did>
**Misses-log appends.** <each append this vet made — what it was, and its class: declined-then-escaped, launched-then-regretted, mis-tiered, review escape, or [false PR claim](../../../rubric/glossary.md#false-pr-claim)> | `None`

<triggered fields, each only when its trigger is present in the artifacts>
```

**The owner-half slot's first line** — the `## Advisor vet` slot in the PR body, a different
artifact from the receipt comment above:

```markdown
<!-- superheroes:advisor-vet -->
**Verdict: READY** · <40-character head sha> <qualifier, if any>
```
