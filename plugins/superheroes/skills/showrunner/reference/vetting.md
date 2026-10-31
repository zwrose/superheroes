# Contents

- [Vetting — the mechanism behind duty 4](#vetting--the-mechanism-behind-duty-4)
- [Order-quality accounting](#order-quality-accounting)
- [Dispatch provenance against engine doctrine](#dispatch-provenance-against-engine-doctrine)
- [Parallel vets — the vet-drafter](#parallel-vets--the-vet-drafter)
- [Adversarial probes at vet](#adversarial-probes-at-vet)
- [Grading the third-rework tripwire](#grading-the-third-rework-tripwire)
- [The collector — pointer, ordinals, and age](#the-collector--pointer-ordinals-and-age)
- [The merged-PR backstop](#the-merged-pr-backstop)
- [The collector preamble](#the-collector-preamble)
- [The owner-half slot — states you will meet](#the-owner-half-slot--states-you-will-meet)
- [A gate needs its unlock citation](#a-gate-needs-its-unlock-citation)
- [Sequential orders need a commit between them](#sequential-orders-need-a-commit-between-them)
- [iPhone evidence](#iphone-evidence)
- [A new refusal needs a healthy-case check](#a-new-refusal-needs-a-healthy-case-check)
- [A pending spec gate is not an unreviewed spec](#a-pending-spec-gate-is-not-an-unreviewed-spec)
- [Vet-time escalation](#vet-time-escalation)
- [Timing follows the show-it level](#timing-follows-the-show-it-level)

# Vetting — the mechanism behind duty 4

This page is reference for the advisor at vet time. Duty 4 of the Showrunner charter states the
rules; this page holds the mechanism that fires only while you vet. The receipt's shape lives in
`skills/showrunner/reference/vet-receipt.md`, and the owner-call contract lives in
`skills/showrunner/reference/owner-decisions.md`.
The checks the vet reads from the PR's review record are the rows of § The review record checks in `skills/showrunner/reference/vet-receipt.md`.

## Order-quality accounting

**Record it from the PR's dispatch-provenance at every vet.** Record **orders dispatched, rework
orders, and each blocking review finding's attribution** — order quality, implementer execution, or
the orchestrator's own integration or assembly (external or unknown where none fits). Track the
**order-vs-implementer subset** against a baseline of about 5:1.

Also record:

- **Park/refusal rate** — how often builders parked or refused, and whether each was correct.
- **Vet receipt-integrity catches** — how often the vet caught a claim that did not reproduce when
  re-run against the world.

Each accounting record **names its window**. **Zero of either is a signal to inspect, never a clean
sheet.** Both guards are prose: if a future model is more agreeable, either rate can fall to zero
and read as a clean batch. The accounting lives in the **durable batch record**, not session memory.
**Inspect** means re-reading a sample of that batch's park and vet receipts, not merely noticing the
zero. It is standing accounting you keep, not a machine count.

Why these two and not the panel: **review panels check the diff against the brief, never the brief
against the world**, so a bad advisor premise is invisible to them. A third guard, the **panel
confirmation-rate line**, inspects the verifiers' agreeableness the same way and lives in
`skills/showrunner/reference/vet-receipt.md`.

Standing accounting makes the work-order authoring rules' effect measurable over time, and tells
you when a build's defects point at order quality rather than the engine. An **owner-half omission
caught at vet** attributes to the **orchestrator's own integration/assembly**, so systematic
under-statement surfaces as a rate rather than an anecdote.

## Dispatch provenance against engine doctrine

Vet dispatch provenance against engine doctrine (CONVENTIONS §7.5). A provenance row showing a
non-first-party model dispatched through the cursor CLI, or a fable tier on an external engine, is
a **defect to catch at vet** — not a builder judgment call to accept.

## Parallel vets — the vet-drafter

**When.** With **two or more** handed-back PRs or stacks waiting for a vet, dispatch one
`vet-drafter` (`agents/vet-drafter.md`) per PR or per stack, in parallel; with one waiting, drafting
it is your choice. A stack goes to one drafter, which drafts every layer's vet.

**Ordinals.** Before dispatch, assign each vet its ordinal from § The collector — consecutive, one
per PR, and one per layer bottom-up for a stack — and write the highest assigned ordinal to durable
memory beside the collector pointer, so a lost draft never lets a later vet reuse its number. Post
in ordinal order. A draft you discard keeps its ordinal: vet that PR yourself under the same number.

**Dispatch inputs.** Give the drafter the repository, the PR number (a stack's, bottom layer first),
each vet's ordinal, the draft directory (absolute, outside the repository) and the installed plugin
root (`${CLAUDE_PLUGIN_ROOT}` resolved to an absolute path), so it never reads the PR branch's copy.

**No model override.** Dispatch the drafter with no model parameter. Its definition says
`model: inherit`, so it runs on your own model, and the draft carries the judgment you will sign.
Vet serially on a host that cannot honour that: one forcing a single model on every subagent
(`CLAUDE_CODE_SUBAGENT_MODEL_FORCE` on Claude Code), or one whose host tool map says the drafter is
not dispatched there (Codex).

**The verdict stays yours.** Check each draft against the PR before you post it, as your own vet:
re-read the diff and the decisive artifacts, re-run any probe the verdict turns on, and make each
act the drafter wrote as proposed (a collector append, a misses-log append, a follow-up filed), then
correct that line of the receipt to record the act as made, before you post. Then post the receipt
and write the slot through `vet_slot.py write`, as duty 4 says.

**Check what the drafter left.** After each drafter returns, read the PR's comments and body for
anything new since dispatch and run `git worktree list` and `git status` in your checkout. Its grant
carries a shell, so the no-post rule is its obligation and this read is the detector; anything it
posted or left behind is a finding you clear before you vet.

## Adversarial probes at vet

Spend vet time on the adversarial probes the suite does not contain: does the guard actually fire when its target breaks? does the test assert what its name claims? does the behavior actually behave?

## Grading the third-rework tripwire

This is the vet-time grading of the third-rework tripwire; the ruling is [review-discipline.md § The third-rework tripwire](../../../rubric/review-discipline.md#the-third-rework-tripwire).

When a builder parks here, the tripwire is firing as designed — **welcome it and go looking for the design problem**, rather than ordering another rework.

## The collector — pointer, ordinals, and age

Reading it is a vet-time step: the one moment you are already in disposition mode, and the one moment guaranteed to recur whatever the project's release model.

**Locating the collector is part of the duty.** Record its issue pointer in durable memory the first
time you open or find it. If you cannot resolve it, the pending field says so as a **disclosed
degradation**, never a bare `None`, which is indistinguishable from an empty collector. Ask the
owner for the number rather than opening a second collector: a duplicate orphans everything the
first one holds.

**An unresolved pointer loses nothing.** When the owner cannot supply the pointer, record the item
and the disclosed degradation in the vet receipt; **no duplicate collector is opened**. Every
pending item also lives in the receipt of the vet that proposed it. An item recorded in a receipt
this way **carries the ordinal of the vet that proposed it**. When the pointer is later resolved,
the deferred append **preserves that original proposing ordinal** and never re-stamps it with the
later vet's ordinal, so the item's age keeps counting from when it was proposed and the age-2
escalation still fires on time.

**Each entry carries three things:** **what it is**, **your recommendation**, and **the proposing
vet's ordinal, stamped on it immutably**. It is **struck when the owner rules** — closing or
declining an item removes it from the collector — and nothing re-numbers what remains.

**Age is a subtraction over ordinals, never a count of artifacts.** Receipts are edited in place,
so they are neither a monotonic register nor one-per-vet, and every counting rule fails on that.
Every vet has a **monotonic ordinal** — one integer per vet, per project — kept in durable memory
beside the collector pointer and **also written into each receipt**, so the sequence survives a
lost memory. The next ordinal is **one more than the highest appearing in the collector or the
receipts**. Carrying an item forward never re-stamps it. Age is `this vet's ordinal − the item's
ordinal`. **The escalation is owed at 2 or more:** an item that old is evidence the owner batch is
not happening, and the receipt says so plainly rather than re-listing as though carrying were
normal. **An item the reconciliation surfaces means the primary path failed for that item** — not
routine throughput.

The merged-PR backstop and the collector's preamble are yours at the same moment.

## The merged-PR backstop

**At vet, grep merged-PR bodies for the Follow-ups for the advisor heading** and reconcile against
the board. The workhorse charter standardizes the heading; `<!-- superheroes:build-record -->` is
its grep anchor. You may run `vet_slot.py check --pr <n> --repo <owner/name>` per PR. It compares
the build record's followups marker with the receipt's dispositions marker, and it flags a PR
**closed** unmerged whose followups marker is not `none` and that has no vet receipt. Those
follow-ups carry into the superseding PR's build record in the carry format the workhorse charter's
§11 defines; that section is the one home for the bullet shape.

## The collector preamble

**Install the contract's distilled preamble at the top of the collector issue body, above the
items, and refresh it when it has drifted or is missing.** The canonical snippet, its markers, why
placement matters, and the replace-region and malformed-marker rules live in
`skills/showrunner/reference/owner-decisions.md` § The collector preamble — canonical snippet. When
the collector pointer cannot be resolved, record the preamble duty as a **disclosed degradation** in
the vet receipt — never a silent skip, and never a second collector.

## The owner-half slot — states you will meet

The slot is the builder's to create (the **workhorse** charter's §11 has the builder create it and governs what it must preserve on a body rewrite; that guarantee is prose with no mechanical check, so the backstop below is still yours).

Consequence up, mechanism down — *an independent reader checked this, and this is what they concluded* is the most merge-relevant single fact on the page.

**Post the receipt first, then write the owner half that points at it** — a failure between the two leaves a receipt with no pointer (visible, recoverable), never a verdict pointing at a receipt that does not exist.

**A heading without its marker is a failed stamp.** A body that carries the `## Advisor vet`
heading without the advisor-vet marker is a current-contract builder that failed to stamp. Re-stamp
the marker and write into the existing slot; that is **not** retroactive creation.

**A missing heading is ambiguous — resolve it against your own receipt comment.** A missing heading
may be a genuine pre-contract PR or a current-contract body rewrite that dropped the whole slot.

- **A receipt exists** → the slot was dropped. Restore it as a dropped write, per the check below.
- **No receipt comment** → a genuine pre-contract PR. **Create the slot at vet**: the
  `## Advisor vet` heading plus the advisor-vet marker, then write into it.

Retroactive creation applies **only** to pre-contract PRs, never as a way to re-seed a slot whose
advisor write was dropped.

**The reminder is the one builder text you remove.** It is not an exception to "never the
builder's prose". If you find your verdict and the reminder both present, the verdict wins: delete
the reminder on that read.

**Check the slot whenever you next read the PR's body** — a re-vet, a re-review, or the read before
handing it back, not only a formal re-vet. Compare its text against your **most recent** vet receipt
comment, your canonical copy, not merely whether the marker is there. A rewrite can:

- drop your text and re-seed the builder's reminder (marker present, reminder back — which reads
  exactly like a vet that has not happened yet);
- drop the marker with your text (marker gone);
- carry an older copy forward over a newer one (marker present, text stale — invisible to a marker
  check);
- drop your text and the marker together (no marker at all — which a pre-contract body also looks
  like; a receipt already posted means this is a dropped write).

Re-write your text when any of those holds, and **re-stamp the marker only when it is actually
gone**. Hand edits before `vet_slot.py write` — re-stamping, pre-contract slot creation, legacy
follow-up keying — are ruled in the register in `skills/showrunner/reference/vet-receipt.md`.

## A gate needs its unlock citation

A PR that adds a **gate, hook, or enforcement mechanism** must name, in its brief, the ratified
precondition that unlocks it and the evidence it is met. **A missing citation is a finding in its
own right**, in any project. When the project being vetted is the superheroes source repository
itself, cite the unlock condition in the anti-opportunities ledger (`LEDGERS.md` §2).

## Sequential orders need a commit between them

A build that ran sequential orders against one worktree should show a commit between them in its
artifacts. Uncommitted work a later order could have wiped is a finding.

## iPhone evidence

**It applies** when the PR carries iPhone evidence (a screenshot or page reading from a simulated
iPhone, a phone the Mac imitates in software), or the issue's done-definition names an iPhone check.

**Read each piece's labels by name:** `phone`, `model`, `iOS`, `page`, `where` (`browser` or
`installed`), and `source` (always `Simulator`). The layout belongs to the pilot
(`test-pilot-execute`), not to this page. Never grade a piece on its layout.

**Rule a piece invalid, with its reason, when:**

- (a) it has no `phone` value;
- (b) its `phone` is not among the phones on the record of the launch the builder runs under
  (`iphoneIds`, or `iphoneId` on a record without it). That is the launch that delivered the PR,
  normally the lane's latest started launch; the builder's heartbeat is filed under that launch id.
  `python3 -B <plugin root>/lib/iphone_reap.py phones --repo-root <repo> --issue <n>` lists one
  `phones[]` entry per phone (`launchId`, `iphoneId`). The delivering launch's phones are the
  `iphoneId` values of the entries whose `launchId` is that launch's.
  A phone from an earlier launch of the same lane is still not on the record;
- (c) it has no `where` label;
- (d) its `where` disagrees with its reading (for example `installed` on a piece whose reading says
  the page runs in the browser);
- (e) its `page` or `where` reads the not-established value — `NOT_ESTABLISHED` in the plugin's
  `lib/iphone_check.py`, the one home of that text (the pilot's tool could not tell what the phone
  showed);
- (f) it was taken after a change to a served file but before the page was reloaded or reinstalled.

The ruling lists every invalid piece and its reason.

**A complete check** matters only when the issue names an iPhone check. The results show one unless
**any** of these holds:

1. a "did not run" line in the results' opening;
2. no pilot's results;
3. no iPhone evidence in the results;
4. no evidence for a part the lane's check includes;
5. any piece ruled invalid;
6. any piece missing its `model`, `iOS`, or `page`;
7. any piece missing its `where` label;
8. any piece missing its `source: Simulator` label;
9. results missing the statement of what a simulator cannot show (a real finger's touch and
   real-device speed);
10. results missing the statement of where the check ran and who chose it;
11. an installed-app part with no reading that reports the app installed;
12. the results name no `commit`, or the `commit` does not resolve
    (`git rev-parse --verify <commit>^{commit}` fails), or
    `git diff --name-only <commit> <head>` fails, or it lists any file that can reach the checked
    page (anything the app serves, a fixture page the check served included). Only later changes
    that cannot reach the checked page (tests that are not served, docs) leave the check standing
    for the head. The receipt quotes the command and its output;
13. the results do not state that the served checkout was clean (`git status --porcelain` empty)
    at that `commit` when the check ran. A commit alone does not show the page served matched it.

**When the launch named sizes.** When the delivering launch's premise names `iphoneModels`, the
check is complete only when **every named size has its own complete check**: one rendered check
object per phone, whose evidence is all from that one phone (its `model` label names the size), with
every part the issue asks for (browser, installed) completed on that phone. A size with no phone,
no evidence, or only part of its check makes the whole check not complete. Evidence split across
phones (browser on one size, installed on the other) completes neither. Without `iphoneModels`, the
conditions above stand as written.

**Superseded attempts.** Pieces under *Superseded attempts* are read and listed but count toward
nothing: conditions 3–8 and 11 and the invalid-piece rules apply to the final attempt's pieces only.
A superseded attempt never excuses a part whose final attempt did not complete. A retry the results
do not show as such (no superseded entry) is graded as written.

**Your own check.** When the issue names an iPhone check and the check is not complete, check the
change on a simulated iPhone by hand **before** you rule. The vet receipt records what you checked,
on which phone (its ID, model and iOS version), where (browser or installed), and what you saw. Check
where the issue says. When the issue says nothing, check where the lane's results say the lane
checked. When neither names a place, the receipt records the place as undetermined and you check in
the browser and in the installed web app alike, so that no place is preferred; never pick one of
them. Use a phone of your own, never a lane's phone that is waiting to be reaped.

When the delivering launch named sizes, check **each size the builder's evidence does not cover**,
one advisor phone per size, running the steps below for each in turn.

1. Make a phone: `xcrun simctl create superheroes-advisor-<vet> <type>`. With named sizes, `<type>`
   is the identifier of the entry in `xcrun simctl list devicetypes -j` whose `name` matches the
   size. With none, it is the value of `IPHONE_DEVICE_TYPE` in `lib/launcher.py` (read it from
   there; never type it here). Keep the ID it prints.
2. An advisor seat has no launch values, so set them for the check's commands:
   `SUPERHEROES_IPHONE_ID=<your id> SUPERHEROES_DEVICE_HUB=available` before
   `iphone_check.py preflight`. Preflight still proves Device Hub is running.
3. `boot`, then drive the check as `test-pilot-execute`'s § The iPhone check says.
4. To check against the plugin's reading page, fill its placeholder from `READING_PARAM` and serve
   it (below). Served as-is, the page posts nothing and every `shot` reads not established.
5. When done, delete only that phone: `xcrun simctl delete <your id>`. Never delete, shut down or
   erase a lane's phone; the reap does that.

```
python3 -B -c "import sys; sys.path.insert(0, '<plugin root>/lib'); import iphone_check as c; print(open('<plugin root>/lib/tests/fixtures/iphone/reading-page.html').read().replace('__READING_PARAM__', c.READING_PARAM))" > <dir>/index.html
python3 -B -m http.server <port> --bind 127.0.0.1 --directory <dir>
```

```
piece 1: no phone ID                        → invalid: no `phone` value (a)
piece 2: phone from an earlier launch       → invalid: not on the record (b)
piece 3: where installed, reading: browser  → invalid: `where` disagrees with reading (d)
piece 4: no `where` label                   → invalid: no `where` label (c)
piece 5: page reads NOT_ESTABLISHED         → invalid: page not established (e)
piece 6: under Superseded attempts          → read and listed; counts toward nothing
check not complete (condition 5) → advisor's own iPhone check recorded
check not complete (condition 12: git diff --name-only abc1234 <head> lists app/page.html) → recorded
ruling: pieces 1–5 invalid, with the reasons above
```

```
sizes iPhone 17, iPhone 17e; a complete check object from each phone on the record
  → complete
sizes iPhone 17, iPhone 17e; a complete check from the iPhone 17 phone only
  → not complete: the iPhone 17e size is missing; the advisor's own check covers it
sizes iPhone 17, iPhone 17e; browser evidence from the iPhone 17 phone, installed evidence from
the iPhone 17e phone
  → not complete for either size
```

## A new refusal needs a healthy-case check

At a vet where a sibling build covers the same scope, run the sibling's healthy-case tests against
this tree. For a lone build, write one healthy-case probe per new refusal and run it. A
refusal-leg bite-proof shows the refusal fires on bad input; it cannot see the same refusal firing
on good input, so over-refusal ships unseen.

Before you order a test that guards a prose line, check it against the pin rule and
Named-failure-first (`rubric/review-discipline.md`). A line that fails either bar gets no test;
record it as review-guarded instead.

## A pending spec gate is not an unreviewed spec

Before dispatching any review gate on a spec, read the linked issue's review receipts. A spec's
`gates.review: pending` is its normal state until the owner approves, so it does not mean the spec
checks never ran. `skills/architect-discovery/reference/spec-checks.md` § The review gate says what
each gate state means. A review dispatched on `pending` alone re-runs checks that already ran, at
the cost of a full multi-round review.

## Vet-time escalation

**You may escalate a full or light PR to a full panel before merge.** This turns a wrong lane call
from a shipped defect into a late review, and it covers a known blind spot: thin tests on large,
visibly-working code are invisible at routing and obvious at vet.

**Triggers:**

- the diff touches quiet-failure surfaces the issue did not reveal;
- it came in much larger than assumed;
- the stated reasoning does not hold against the diff;
- the tests look thin for the size;
- it moved a line the issue implied it would sit inside.

**Proportionality:** where the doubt is narrow, dispatch **one independent reviewer given the
doubt** rather than a full panel: a reviewer from outside every maker's family, with the doubt stated
in its dispatch, whose reading the review record shows. **The vet is the backstop for lane calls in
both directions.**

## Timing follows the show-it level

**The vet is async by default; what binds you is the show-it level, not attendance.** The
presentation call (duty 5) already says when the owner must *see* something, so the vet's timing
follows from it.

- **say it** and **nothing to see** are fully async.
- **show it @ `link`** is fully async — the environment outlives the session.
- **show it @ `running`** means your window is this session's. Say so in the receipt **and** in the
  owner half: a spot-check surface that dies at session end is a disclosed **degradation**.
- **show it @ `command`** is async, but **you must have run the command yourself** and written the
  exact drive-to-state path. Instructions nobody executed are reconstruction with extra steps.
- **attended** and **none** remain the honest floor.
