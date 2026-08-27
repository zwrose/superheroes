<!-- auto-fix-loop-version: 1 -->
## Contents

1. [Specialist Dispatch Prompt Template](#specialist-dispatch-prompt-template)
2. [Triage Subagent Prompt](#triage-subagent-prompt)
3. [Fixer Subagent Prompt](#fixer-subagent-prompt)
4. [Verification Rules (for subagents)](#verification-rules-for-subagents)
5. [Common Mistakes](#common-mistakes)

---

## Specialist Dispatch Prompt Template

**Moved.** The panel specialist prompt template now ships as data and is rendered per seat by
`round_orders.render_order` on each `next` for `dispatch-panel`. The orchestrator **dispatches the
emitted order file** at `$SESSION_DIR/round-<N>/orders/dispatch-panel/<skey>.a<K>.md` (paths and
landing shapes: `SKILL.md` §3; emission contract: `skills/review-code/reference/round-driver.md` § Emitted orders) —
do not hand-compose from a fenced template.

The authoritative template body lives at `rubric/orders/dispatch-panel.md` under the plugin
root. The driver fills placeholders (`{{DIFF_PATH}}`, `{{RUBRIC_PATH}}`, channel blocks,
ratified residuals, payload contract, landing instructions) before you dispatch.

Before dispatching a `codex`/`cursor` seat, confirm the rendered order's delivery channel matches
the seat's vendor (stdout vs file) — the driver derives the channel block from the seat map; you
still choose the dispatch mechanism (`dispatch-review` vs native subagent) per the blocks below.

## Mechanical focus flags

Before dispatching the round's specialists, the orchestrator runs the deterministic
mechanical-focus-flag detector over the round diff (design authority: ratified #474,
position 15 — grep-detected **additive** brief flags; **additions only, never
classifier-driven lens removal**):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -B "$ROOT_DIR/lib/focus_flags.py" "$SESSION_DIR/round-<round>/diff.txt"
```

It prints zero or more flag lines (a changed migration file → rollback/data-safety
emphasis; a changed dependency lockfile → supply-chain check). **Append** each emitted
line into every specialist's `Focus:` context block, alongside any `--focus` notes — an
addition that never replaces the `--focus` notes and never removes or down-scopes a lens
(that classifier-driven lens-removal is banned by #474). If nothing is emitted, append
nothing. The detector is grep-grounded and has no authority to drop a finding or a lens.

> **External-engine reviewers — stdout channel grading mechanics (#38, #196, #666).** When `$REVIEWER_ENGINE` is
> `codex` or `cursor`, a specialist is dispatched through `engine_adapter.py` (read-only sandbox)
> instead of a named subagent, and it returns its payload on **stdout** rather than writing a
> findings file. Panel seats emit `{"findings": [...], "investigated": [...]}`; verifier seats emit
> `{"verdicts": [...], "investigated": [...]}`; synthesis judges emit `{"grouping": [...]}`; fix
> auditors emit `{id, ruling, reason}`. The graded result carries **`resultKind`** (one of
> `findings`, `verdicts`, `grouping`, `ruling`) naming which payload key survived. A non-empty
> payload succeeds without `investigated`; only an **empty** payload needs a surviving
> `investigated` path (see below). **Findings-only prompt authoring** (caller side): cite
> `skills/workhorse/reference/dispatch-mechanics.md` § *Findings-only review prompts* — a prompt
> that demands a single JSON object without requiring `investigated` guarantees a vacuous forfeit
> when the honest answer is no findings. The contract shape also lives in the base rubric's
> "Findings output format" section; the
> dispatch prompt's `## Output` block names the seat's channel — this block is how the runner grades
> what the rubric already specified. `engine_adapter.parse_result` scans stdout for the **last
> top-level JSON value**, so incidental trailing prose after a valid object is tolerated. An **empty**
> `findings` array is accepted as *clean* **only** when `investigated` lists at least one path that
> survives the runner's spot-check (the path must resolve inside the sanitized review view root and
> exist on disk). A seat that returns empty findings with no verifiable `investigated` record is a
> **vacuous forfeit** — a named cause (`reason: "vacuous"` from `dispatch-review`): treated as a seat
> that **never ran**, not as a clean review; the orchestrator submits the folded seat with
> `vacuous: true` (or `reason: "vacuous"`). Engine telemetry (token spend, tool calls, wall time) is
> **corroborating evidence only** and can never satisfy that investigation floor. The parser also
> **tolerates a bare top-level array** `[...]` of finding objects as of #196, but anything else
> (prose with no parseable JSON object/array, an empty stream, an array of non-objects) parses as
> `unreadable`, which forfeits the slot to a Claude re-run (UFR-7) and silently doubles the round's
> cost.

> **Reviewer-seat dispatch runs through the dispatch RUNNER (#563 DoD 2/4) — reviewer role ONLY.**
> When `$REVIEWER_ENGINE` is `codex` or `cursor`, dispatch each read-only reviewer seat through
> `lib/engine_dispatch.py dispatch-review` (not a hand-rolled `codex exec` / `cursor-agent` shell
> line). The runner owns the previously per-session dispatch mechanics as **machinery**: it prepends
> the anti-hijack preamble (the mode-7 hardening that stops the codex SessionStart/skill-selection
> derail), feeds the prompt via the `- < realfile` stdin form behind the `_prompt_path_ok`
> empty-prompt guard, builds a **disposable sanitized export** of the repository named by
> `--repo-root` and pins the dispatch to that view (codex `-C`, cursor's subprocess cwd — not the
> caller's live checkout), bounds the attempt and streams liveness heartbeats to `--progress-file`,
> and on a **terminal forfeit** (timeout OR nonzero engine exit OR `unreadable` OR **vacuous** OR
> **`forfeit-with-engaged-artifact`** — never intermediate bootstrap noise that still yields a final
> answer) auto-retries ONCE tight-inline with a ≥900 s ceiling before returning
> `{"ok": false, "forfeited": true, "disclosure": …}` (or `reason: "vacuous"` when the **last**
> attempt ended vacuous — e.g. attempt 1 timing out and attempt 2 coming back vacuous still yields
> `vacuous`, not only a double vacuous forfeit; or `reason: "forfeit-with-engaged-artifact"` when
> stdout was engaged but our transport could not grade it — still a forfeit, the seat does not count
> toward the panel, and the loop's behaviour is unchanged). A forfeit → the seat falls open to a Claude re-run (UFR-7) and the
> orchestrator **discloses** the degraded vendor mix (the `disclosure` string); making that fall-open
> loud by machinery in the receipt is #563 PR C.
>
> **Sanitized review view (#684).** The seat does not run inside the owner's checkout. The runner
> materializes a fresh single-commit git repo at `headSha` holding the reviewed tree, with the named
> repo-local agent-config surface removed (`AGENTS.md`, `.cursor/`, `CLAUDE.md`, and the other basenames
> the runner strips at every directory level). That config is **not discoverable** from the seat's cwd —
> which is the point of #684. Reading ordinary source files and `git grep` work; **`git log`,
> `git blame`, `git diff <ref>`, and `git show <ref>` do not** — the view has no `origin/main`, no
> remote, and no parent commit (one synthetic commit, no history). The dispatch prompt's auto-prepended
> notice states this prohibition to the seat explicitly. Paths the runner stripped are **unreadable**
> even when the diff under review touches them — the dispatch prompt should name stripped paths so the
> seat knows why a read failed.
>
> **`--mode {review,brief-check}` (optional, default `review`).** `--mode review` or omitted →
> behaviour identical to today, including `--diff-base` resolving to an empty patch →
> `sanitized-view-diff-empty`, `attempts: 0`. `--mode brief-check` → the sanitized view is built
> **diff-less**; all four `sanitizedView` diff keys below are `null`. Supplying **both**
> `--mode brief-check` and `--diff-base` is a terminal refusal `mode-brief-check-with-diff-base`,
> `attempts: 0`, no spawn — **including on continuation**, because the check runs before the journal
> read. On continuation, an explicitly disagreeing `--mode` is
> `run-dir-mode-mismatch`, `attempts: 0`; omitted `--mode` inherits the mode the run was opened with
> (a journal written before this change, with no `mode` key, normalizes to `review`); when inherited
> mode is `brief-check` and `--mode` is omitted, `--diff-base` stays accepted-and-ignored. Every
> `dispatch-review` result carries a top-level **`mode`** string — success, forfeit, and every
> pre-spawn refusal alike. Registry/model gate, sanitized-view export and config strip, the #666
> investigation floor, engagement read, and vacuous-forfeit accounting are unchanged in both modes.
>
> **`--diff-base <commit-oid>` (optional).** Omitted → nothing is staged and the four receipt keys
> below are `null` (this has always been true — `--diff-base` was never required). Supplied → the value must be a **pinned commit object id**
> (40 hex characters, or 64 in a SHA-256 repository); a revision expression, branch name or tag is
> refused as `sanitized-view-diff-base-unresolved` **before any repository-local git command runs**.
> The runner verifies that commit **in the source repository** (which has git), resolves the **merge
> base** of that commit and the view's `headSha`,
> generates the merge-base→head patch, and stages it inside the view at the view-root-relative path
> `SUPERHEROES_REVIEW_DIFF.patch`. The patch is written **after** export verification and **before**
> the view's synthetic commit, so the view is committed clean rather than dirty. Changed paths that
> match the runner's stripped-config predicate are **withheld from the patch and counted** — the patch
> can never reintroduce the agent/IDE config the export just removed. The dispatch prompt's
> auto-prepended notice states explicitly that when a patch was staged, the change under review **is**
> that patch, that it is a **generated artifact rather than repository source**, and that the seat
> must not review it, must not list it in `investigated`, and should exclude it from repo-wide
> searches. On a **continuation** (`--run-dir` naming an existing run), `--diff-base` is accepted but
> ignored — the live run's view is not rebuilt — except when this invocation also asserts
> `--mode brief-check` explicitly, which refuses `mode-brief-check-with-diff-base` before the
> journal is read.
>
> The staged patch is **rejected from the #666 investigation floor**: a seat whose `investigated` array
> cites only the patch fails the floor and forfeits vacuously, exactly as if it had cited nothing.
> Rejection is by resolved file identity, so `./NAME`, `a/../NAME` and a symlink to it are all
> rejected. The rejection reason string is `generated-artifact`.
>
> **Four `sanitizedView` receipt keys** (always present, `null` when `--diff-base` was not used):
>
> | key | meaning |
> |---|---|
> | `diffBase` | the resolved **merge-base** sha the patch is against (40 hex chars, or 64 in a SHA-256 repository) |
> | `diffPath` | `SUPERHEROES_REVIEW_DIFF.patch`, relative to the view root |
> | `diffBytes` | patch size in bytes |
> | `diffWithheldCount` | **only** the changed non-tree entries the stripped-config policy withheld; underivable, unrecognized, unaccounted, and opaque content **refuse the dispatch** rather than being counted here — this is what keeps the reviewer-facing "the absence is not a finding" statement true |
>
> The census of changed paths comes from direct two-tree enumeration (`git ls-tree` on the
> merge-base and head), not from patch presentation — `git diff`, rendered patch text, or a list of
> presently-known dangerous configuration keys. Every changed recursively enumerated **non-tree**
> entry — blob/file, symlink or gitlink — must be **rendered**, **policy-withheld**, or **refused**
> before any external engine spawns. The merge-base the census is taken against is resolved outside
> the reviewed repository's git directory — in a scratch repository linked only by its object store,
> under an environment with every inherited `GIT_*` variable dropped — so repository-controlled
> ancestry overlays cannot select a base that omits a genuine change, and dispatch **refuses** when
> authoritative ancestry cannot be established. An empty directory added or removed in a commit is a
> tree-only change carrying no file, symlink or gitlink content, `git diff` renders nothing for it
> either, and it is therefore outside this contract. Until a follow-up issue
> lands, opaque or unaccounted content returns a named terminal refusal (`attempts: 0`) that is
> never interpreted as zero findings or a clean review; there is no automatic fallback, and that
> absence is an explicitly accepted availability limitation.
>
> **Diff refusals** (all `attempts: 0`, no token spend), joining the existing `sanitized-view-*`
> family:
>
> | token | when |
> |---|---|
> | `sanitized-view-diff-base-unresolved` | the base is empty, begins with `-`, is not a pinned 40-/64-hex commit object id, does not resolve to a commit, shares no merge base with head, the repository's shallow state cannot be determined from its git, the repository's object store cannot be located, the scratch ancestry repository cannot be created, or the merge-base cannot be established from it |
> | `sanitized-view-diff-base-shallow` | the reviewed repository is a shallow clone, so the genuine merge-base cannot be established from its object store; fetch full history (for example `fetch-depth: 0` or `git fetch --unshallow`) and dispatch again |
> | `sanitized-view-diff-empty` | a base was requested and the resulting patch is empty with nothing withheld |
> | `sanitized-view-diff-fully-withheld` | every changed path was withheld as stripped config — an external seat could not review this change at all |
> | `sanitized-view-diff-too-large` | the patch exceeds the 8 MiB ceiling, or census `ls-tree` stdout exceeds the export byte ceiling |
> | `sanitized-view-diff-path-collision` | the repository already tracks a file named `SUPERHEROES_REVIEW_DIFF.patch` |
> | `sanitized-view-diff-failed` | a git subprocess failed while resolving ancestry or generating the patch (spawn error, non-zero exit, timeout) — command failure only |
> | `sanitized-view-diff-unaccounted` | an unrecognized non-`diff --git` span, a duplicate path within one census tree, a changed census entry that survived the stripped policy but has no rendered section, a rendered section for a path the census does not contain, or a duplicate rendered section for the same path |
> | `sanitized-view-diff-opaque` | a rendered section whose content is opaque — `Binary files … differ` (or `GIT binary patch`) instead of hunks |
>
> **Mode refusals** (all `attempts: 0`, no spawn — not members of the `sanitized-view-*`
> diff-refusal family above):
>
> | token | when |
> |---|---|
> | `mode-invalid` | `--mode` is not a string in `{review,brief-check}` — top-level `mode` stays canonical (`review`); the rejected value is in `rejectedMode` |
> | `mode-brief-check-with-diff-base` | `--mode brief-check` and `--diff-base` were both explicitly supplied |
> | `run-dir-mode-mismatch` | continuation with an explicitly disagreeing `--mode` |
>
> **#666 investigation floor.** A seat that cites a **stripped** path in its `investigated` array fails
> the investigation floor and forfeits vacuously — fail-safe (the seat falls open to Claude), never a
> false clean.
>
> **#685 CLI `parse-result` echo gap.** The CLI `parse-result --role review` path does not receive the
> dispatched prompt, so it performs **no echo strip**. An **empty-findings result from that path is
> unverified** — apply the investigation floor **manually**. The runner path (`engine_dispatch.py
> dispatch-review`) parses raw stdout first; only when that parse yields no findings does it strip
> the echoed prompt and re-parse (so an empty-findings result from the runner path has been through
> the strip). A `--prompt-path` flag for `parse-result`
> is **deliberately not built** pending a named consumer.
>
> **View build refusal (no fallback).** If the sanitized view cannot be built, `dispatch-review`
> returns a named `unrunnable` refusal with `attempts: 0` and **no spawn** — alongside post-argparse
> refusals such as `sanitized-view-tempbase-inside-repo`, `sanitized-view-head-unresolved`,
> `sanitized-view-export-failed`, `sanitized-view-export-timeout`, `sanitized-view-partial-clone`,
> and `sanitized-view-init-failed`
> (also `attempts: 0`). There is
> **no fallback to the raw repo and no opt-out**.
>
> **Partial clones are an unsupported checkout shape** (owner-ruled 2026-08-09, #797). View
> construction **refuses the shape up front**, before it reads a single object:
> **`sanitized-view-partial-clone` — partial or unhydrated clone detected; sanitized-view
> construction refused. Hydrate the checkout and dispatch again.** Nothing is materialized, so
> there is no partial view to clean up. As defence in depth, every git subprocess construction
> spawns also runs under `GIT_NO_LAZY_FETCH=1`, so no path can wait on git's on-demand fetching of
> an object the checkout does not hold — the quiet-hang class PR #761 recorded.
>
> **Hydrating.** Re-cloning without `--filter` is the reliable remedy. To fix a checkout in place,
> every marker the detector reads has to go — not just `origin`'s two keys — because any one of
> them on its own re-triggers the refusal:
>
> ```bash
> # 1. list what is actually there (any of these three shapes counts, on ANY remote name)
> git config --local --get-regexp '^remote\..*\.(promisor|partialclonefilter)$'
> git config --local --get extensions.partialclone
>
> # 2. clear every line the first step printed, substituting the real remote name
> git config --local --unset-all remote.<name>.partialclonefilter
> git config --local --unset-all remote.<name>.promisor
> git config --local --unset-all extensions.partialclone
>
> # 3. fetch the objects the filter had been skipping
> git fetch --refetch <name>
> ```
>
> A checkout whose only marker is `extensions.partialclone`, or whose promisor remote is not named
> `origin`, is still refused after unsetting `origin`'s keys alone.
>
> **`git fetch --refetch` on its own is not a remedy** — it deliberately reapplies the filter
> recorded in `remote.<name>.partialCloneFilter`, so it downloads another filtered pack and leaves
> the required objects absent, returning the operator to the identical refusal. (Measured on git
> 2.50.1 against a `--filter=blob:none` clone: the blob was still reported `missing` after a bare
> `--refetch`, and present after the unset-then-refetch above.)
>
> **The refusal is wider than "this clone is missing something we need", deliberately.** A filtered
> clone that happens to hold every object it needs still refuses. Three measured facts make the
> narrower reading untenable. A blob-filtered clone **with a checkout** — the shape real users have
> — has its HEAD blobs already hydrated, so materialization succeeds and only the review diff trips
> over an absent base-side blob, arriving as an ordinary "git diff failed" that is
> indistinguishable at that call site from a dozen unrelated faults. The outward refusal tokens are
> umbrellas (`sanitized-view-export-failed` also covers a census type mismatch and a
> destination-filesystem error), so renaming one would tell an operator to hydrate their checkout
> when their disk was full. And `GIT_NO_LAZY_FETCH` is honoured only by newer git, so a mechanism
> resting on it alone is silently inert on an older client. Refusing the shape, from config, is the
> one answer that holds on every git version and every filter.
>
> **What counts as the shape.** The repository's **own** config (`--local`, so a marker in a user's
> global config cannot condemn every repository on the machine) carrying any of
> `extensions.partialclone`, `remote.<name>.partialCloneFilter`, or a git-true
> `remote.<name>.promisor`. Boolean values are evaluated by `git config --type=bool` itself rather
> than by a hand-rolled parser — git reads `yes`/`on`/`1` as true and also `0x10`, `010` and `1k`.
> A config probe that cannot run answers "not partial" and lets the build proceed under the
> `GIT_NO_LAZY_FETCH` backstop, so a config hiccup on an ordinary repository never becomes a hard
> refusal. No timeout machinery is involved — the ruling replaced the earlier bounded-deadline
> design.
>
> **Argparse vs JSON refusals.** `--repo-root` is **required** and validated by argparse before
> `dispatch-review` runs: a missing flag, an empty expansion from an unset shell variable
> (`--repo-root ""`), a path that is not an existing directory, or a directory without `.git` exits
> **2** with argparse's usage error — it never reaches the JSON envelope. `--run-dir` is optional;
> when omitted the runner allocates a private temp directory. When supplied, a path that **exists but
> is not a directory** is refused at argparse (exit 2); a missing path is accepted (the nearest
> existing ancestor must be a directory). **JSON refusals** (exit 0,
> top-level `ok: false`) still apply for run-directory problems argparse cannot see: `run-dir-is-symlink`,
> `run-dir-not-writable`, `run-dir-setup-failed:<Type>`, and the post-spawn `run-dir-*` family documented below.
>
> **Receipt.** Every dispatch result carries a `sanitizedView` block (`strategy`, `stripped`,
> `strippedCount`, `headSha`, `sourceDirty`, `buildSeconds`, `bytes`, `fileCount`, plus `diffBase`,
> `diffPath`, `diffBytes`, `diffWithheldCount` — the last four always present, `null` when
> `--diff-base` was not used). The `bytes` and `fileCount` figures **include** the staged patch when
> one was written. The view is the **committed** tree at `headSha`; `sourceDirty: true` flags modified
> tracked files in the source repo
> so a caller reviewing uncommitted work is disclosed rather than silently given the pre-change tree.
> Every result also carries **`terminal`**, **`argv`** (the exact spawned command), **`runDir`**, and
> top-level **`mode`** (`review` or `brief-check`).
>
> **Result shape — top-level, no wrapper (#687).** Every `dispatch-review` result object carries
> **`ok`**, **`terminal`**, **`runDir`**, **`argv`**, and **`mode`** at the top level. On a failure it also
> carries **`reason`** (and usually **`detail`**). On success it also carries **`resultKind`**
> (one of `findings`, `verdicts`, `grouping`, `ruling`) naming the payload, plus **exactly one**
> payload key of that name.
> **`investigated`** is present only when at least one claimed path survives the runner's spot-check
> (resolves inside the sanitized review view and exists on disk); a normal non-empty payload reply
> omits it. Outcome-dependent keys also include **`engagement`** and
> **`sanitizedView`**. A consumer must **not** read an absent `findings` as "zero findings" — an
> absent `findings` may mean a different `resultKind` instead; that is the fail-open reading this
> subsystem exists to prevent. An object carrying **more than one** payload key from
> `REVIEW_RESULT_KINDS` is refused as
> `unreadable`. An item whose `id` is exactly `<agent-name>-001` or whose `severity` is exactly
> `Critical | Important | Minor | Nit` — the `review-base.md` template literals — is refused as
> `unreadable` (field-exact; an honest finding that *quotes* those literals in its prose survives).
> An `unrunnable` refusal carries no `findings` / `investigated` / `engagement`; it carries
> `sanitizedView` **only when raised after the sanitized view was built** — early refusals
> (`prompt-*`, `run-dir-is-symlink`, `run-dir-not-writable`, `schema-*`, and argparse failures for
> `--repo-root` / `--run-dir`) precede the view and carry none. A terminal
> forfeit carries no `findings`/`investigated`. There is no `result` wrapper; parsing
> `result.findings` reads nothing.
>
> **Review payload transport (#687).** The runner accepts **four** result kinds on stdout
> (`REVIEW_RESULT_KINDS`: `findings`, `verdicts`, `grouping`, `ruling`). Every
> `ok: true` review result carries **`resultKind`** naming exactly one payload key of that name;
> **`investigated`** is attached only when at least one claimed path survives spot-checking.
> **Recognition is not gradeability** — widening what the transport can read changes nothing about
> what it will certify: the investigation floor still forfeits an empty payload with no surviving
> `investigated` path for **every** kind including `grouping`, and an `--expected-result-kind`
> mismatch still forfeits. Every other top-level key the
> seat emits is dropped. Callers may pin the expected kind mechanically via
> `dispatch-review --expected-result-kind {findings,verdicts,grouping,ruling}` (library:
> `expected_result_kind=`); a mismatched kind is refused with `detail: result-kind-mismatch`, not
> `unreadable`. The pin is journaled when the run is **opened**; on a continuation an **omitted** pin
> inherits the journaled value, while a **supplied** pin that disagrees with the journaled one —
> including supplying a pin on a run opened without one — refuses `run-dir-result-kind-mismatch`,
> `attempts: 0`, no spawn — a run's identity is fixed at open. **Review panel** seats pass the
> **`findings`** pin; the **verify phase** passes the
> **`verdicts`** pin. When no pin is set the transport accepts any of the four kinds, each graded by
> its own engagement floor; #687's findings-only posture for panel seats is carried by the pin those
> seats pass, not by a transport default. Any other `expected_result_kind` value is refused before
> dispatch on either route — neither silently ignores it. The **library** API (`expected_result_kind=`)
> returns a structured refusal with `attempts: 0`, `detail: "expected-result-kind-invalid"`, and the
> rejected value under `rejectedResultKind`; the **CLI** (`--expected-result-kind`) is rejected by
> argparse before dispatch with a usage error, a non-zero exit, and no result object. A **`verdicts`**
> payload now travels through `dispatch-review` for verifier seats — a correct `{"verdicts": [...]}`
> stdout no longer parses `unreadable` by construction; **`grouping`** and **`ruling`** payloads are
> likewise recognised for synthesis judges and fix auditors. A **`ruling`** payload is recognised only
> when the object carries `id`, `reason`, and a `ruling` drawn from `audits.AUDIT_RULINGS`, and
> validates against the `P_AUDITS` contract; the terminal result then carries the scrubbed ruling
> record under **`ruling`**, with `id` and `reason` **nested inside that record and not mirrored at
> top level** — **one per-id ruling per dispatch**. What does not
> travel through this verb is the round-driver's `dispatch-audits` **phase submission**: its seat
> payloads land on the per-target artifact path the order names, and the `collectionManifest`
> provenance is built out-of-band from the orchestrator's own dispatch records, so the batch submit
> stays the driver's channel (`round-driver.md`). For verifier delivery channels, see
> `verification-pass.md`.
>
> **`engagement.read` (#687).** When the result carries an **`engagement`** block with a non-`null`
> value (present only when the attempt produced stdout that was graded), `engagement.read` is
> `"engaged"` when the seat demonstrably acted: at least
> one finding returned, at least one accepted `investigated` path, or `engagement.toolCalls` is not
> `None` and `>= 1`. Otherwise it is `"unknown"`. On a timeout, refusal, nonzero-exit, or
> missing-stdout forfeit the `engagement` key is **present with the value `null`** (there was no graded
> stdout to measure), so `engagement.read` is unavailable — `result.get("engagement", {})` is
> **unsafe** because the key may carry `null`, not merely be missing; consumers must handle a `null`
> value. The runner **never** reports `"inert"` — absence of positive evidence is not proof of
> inaction, because a correct payload the transport could not read looks identical to a seat that never
> ran. Only `seat_canary probe` can justify calling a seat inert.
>
> **Tokens are corroborating evidence only — measured (#687).** Engine telemetry (token spend, tool
> calls, wall time) remains **corroborating evidence only** and can never satisfy the investigation
> floor — the field heuristic that "~23K tokens means vacuous, ~83–175K means real work" is refuted.
> Through the identical `dispatch-review` path on 2026-07-31 with the calibrated codex reviewer seat
> at maximal effort:
>
> | Dispatch | Outcome | Tokens |
> |---|---|---|
> | 15-line docs diff, empty answer invited | clean — `{"findings":[],"investigated":["README.md"]}` | 2,449 |
> | 20-line fail-open diff | produced a Critical finding | 10,415 |
> | verdict-shaped contract | forfeited (transport), work was correct | 20,753 |
> | 1,871-line real diff | 3 findings, ~430 s | 173,229 |
>
> A 23K token floor would have discarded the Critical. Cross-path comparison is worse: the
> preflight's "reply with the single word READY" cost 20,388 tokens because it runs in the real repo
> cwd where SessionStart hooks load, while `dispatch-review` runs in the sanitized view with
> `CLAUDE.md` stripped (#684).
>
> **`payloadShape` on shape-unreadable forfeit (#687).** When the **last** attempt forfeits because
> stdout was shape-unreadable, the result may carry `payloadShape`: a mapping with `parsed` (one of
> `object-without-findings`, `object-both-payload-keys`, `object-findings-not-a-list`,
> `object-verdicts-not-a-list`, `array-not-all-objects`, `findings-hollow-member`,
> `verdicts-hollow-member`, `placeholder-literal-refusal`, `no-parseable-json`, `empty-stdout`, or
> `prompt-echo-only`), `topLevelKeys` (a list of strings,
> populated only when
> `parsed` is `object-without-findings` or `object-both-payload-keys`), and `keysTruncated` (bool; signals the key list was
> capped). Diagnosis only — it never changes the fail direction. `payloadShape` is **absent** on a
> vacuous forfeit and on success.
>
> **Originating-verb continuation loop.** Open with `--run-dir` (or omit it for a private temp run dir
> that loops to terminal). **Launch** each `--run-dir` with a **short positive slice** (12–45 s is the
> measured range in `skills/workhorse/reference/dispatch-mechanics.md` § Launch slice vs continuation slice);
> then re-invoke **`dispatch-review`** (never `dispatch-poll`) on the same `--run-dir` with
> `--max-wait 540` while `.terminal` is false. A non-terminal
> `{"reason": "running", "terminal": false}` is **not** a forfeit. `dispatch-poll` is observational
> and never spawns; `dispatch-abandon` is how a run directory is abandoned. Omitting `--max-wait`
> loops until terminal in 540 s slices — below the **600 s foreground-conversion boundary on harness
> 2.1.219**.
>
> ```bash
> ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
> # Keep $SEAT_PROGRESS outside $RUN_DIR — non-empty run-dir → run-dir-not-empty-unopened
> # LAUNCH — first call on each --run-dir: short positive slice (see dispatch-mechanics.md)
> python3 -B "$ROOT_DIR/lib/engine_dispatch.py" dispatch-review \
>   --engine "$REVIEWER_ENGINE" --engine-model "$SEAT_ENGINE_MODEL" --effort "$SEAT_EFFORT" \
>   --prompt-path "$SEAT_PROMPT" --repo-root "$REPO_ROOT" \
>   --diff-base "$BASE_REF" \
>   --expected-result-kind findings \
>   --run-dir "$RUN_DIR" --max-wait 12 \
>   --progress-file "$SEAT_PROGRESS" --timeout 900 --retry-timeout 900
> # CONTINUATION — re-invoke while .terminal is false: full slice up to 540 s
> python3 -B "$ROOT_DIR/lib/engine_dispatch.py" dispatch-review \
>   --engine "$REVIEWER_ENGINE" --engine-model "$SEAT_ENGINE_MODEL" --effort "$SEAT_EFFORT" \
>   --prompt-path "$SEAT_PROMPT" --repo-root "$REPO_ROOT" \
>   --diff-base "$BASE_REF" \
>   --expected-result-kind findings \
>   --run-dir "$RUN_DIR" --max-wait 540 \
>   --progress-file "$SEAT_PROGRESS" --timeout 900 --retry-timeout 900
> ```
>
> `$SEAT_ENGINE_MODEL` is the seat's **registry id** and `$SEAT_EFFORT` its effort — **both are
> required by this runner**; `engine_dispatch` takes `--effort` as a required flag on
> `dispatch-review`. Every review seat the seat map assigns on cursor carries a real effort, so this
> is not a limitation in practice.
>
> Read-only sandbox is **hard-coded inside the runner API** — it cannot emit a write dispatch. The
> seat **may and should** read files and run read-only commands inside the sanitized view to ground
> its findings (`--repo-root` on the CLI still names the **source** repository; the runner builds the
> view itself). An unresolvable `--repo-root` is refused by **argparse before any JSON is emitted**
> (exit 2) — missing, empty, not a directory, or not a git repository. `--diff-base` makes staging the diff **machinery** — the runner stages the change as
> `SUPERHEROES_REVIEW_DIFF.patch` inside the view so the seat can read it without git history.
> The value must be the **pinned base commit object id** the round diff was computed against — not a
> symbolic ref like `origin/main`, which can drift mid-loop and stage a patch that disagrees with the
> round diff. This is now **mechanized**: anything that is not a 40-/64-hex commit object id is refused
> before any repository-local git command runs. An unset shell variable expands to `--diff-base ""`,
> which the runner refuses as
> `sanitized-view-diff-base-unresolved` with `attempts: 0` — empty is not the same as omitted.
> Inlining the diff in the seat prompt remains available and is still reasonable for a small diff,
> but it is no longer the only way a seat gets the change. Repo access is no longer forbidden.
>
> **Host grants (subcommand granularity).** The owner may adopt these grant strings at subcommand
> granularity (the band states them; it never writes the owner's settings):
> - `Bash(python3 -B */lib/engine_dispatch.py dispatch-review:*)`
> - `Bash(python3 -B */lib/engine_dispatch.py dispatch-write:*)`
> - `Bash(python3 -B */lib/engine_dispatch.py dispatch-poll:*)`
> `dispatch-poll` is **observational — it never spawns an engine, never advances a run, and never
> writes to the repository**, so the **subcommand** adds no write capability of its own; like the
> two grants above, this grant is a **prefix** rule over a **wildcard path**, so it discriminates
> the subcommand rather than the script's identity. The write grant is deliberately narrower so **write autonomy is revocable on its own**. Host rules
> match a **prefix**, so that revocability holds only at subcommand granularity — a file-level or
> bare-`python3` rule would cover both verbs. The path wildcard (`*/lib/engine_dispatch.py`) matches
> any install location, so the grant discriminates the **subcommand**, not the script's identity —
> an executable at any matching path would be covered by the same rule; owners who want script
> identity should pin the absolute installed plugin path in their own rule. **Absent grant → fail closed:** with no matching grant
> the dispatch does not run, no engine is spawned, nothing is written, and the caller **parks loudly**
> — never a soft failure, never a silent fall-open. A `configure` onboarding offer for the rule is
> deferred to [#549](https://github.com/zwrose/superheroes/issues/549); the owner pastes the rule by
> hand.
>
> **Why the in-place fixer is not a `dispatch-write` consumer.** review-code's auto-fix path
> deliberately runs in the checked-out branch of the **current checkout** (see
> `skills/review-code/SKILL.md`'s auto-fix branch guard, which refuses to create a worktree for that
> path). `dispatch-write` refuses a primary checkout (`cwd-primary-checkout`), so the in-place fixer
> path is **unchanged** and is **not** a consumer of the write verb. Do not imply otherwise.
>
> **Cross-vendor control probe (#668).** For each **distinct cross-vendor vendor** among the
> panel's seats that ran with zero findings on that vendor's seat(s), run the planted-defect control
> probe **once per such vendor** before treating those seats as clean. Use that vendor's own seat
> model and effort from the seat map. A seat whose registry config is **effort-less** — one the model
> registry records with no effort at all — is expressed by **omitting `--effort`** (#963), never by an
> effort string: `probe`'s `--effort` is optional and defaults to `None`, the registry's own value.
> Passing an empty `--effort ""` is not the same thing and still refuses at
> `engine-config:invalid-model-effort`, so the loop omits the flag rather than passing an empty one.
>
> ```bash
> ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
> CANARY_RESULTS=()
> for VENDOR in "${CROSS_VENDOR_VENDORS[@]}"; do
>   SEAT_ENGINE_MODEL="${SEAT_MODEL_BY_VENDOR[${VENDOR}]}"
>   SEAT_EFFORT="${SEAT_EFFORT_BY_VENDOR[${VENDOR}]}"
>   EFFORT_ARGS=()
>   if [ -n "${SEAT_EFFORT}" ]; then EFFORT_ARGS=(--effort "${SEAT_EFFORT}"); fi
>   CANARY_RESULTS+=("$(
>     python3 -B "${ROOT_DIR}/lib/seat_canary.py" probe \
>       --engine "${VENDOR}" --engine-model "${SEAT_ENGINE_MODEL}" "${EFFORT_ARGS[@]}" \
>       --repo-root "${REPO_ROOT}"
>   )")
> done
> ```
>
> Submit the probe JSON objects as a **list** on the panel artifact as `canaryResult` (a single
> dict is still accepted when only one cross-vendor vendor needs a probe). Each result must carry
> its `engine` field matching the vendor you probed. The probe is scored on **engagement
> evidence** — findings produced, a verifiable investigation record, or tool calls actually invoked
> — and **never** on magnitudes: token spend and wall time are recorded but are deliberately not a
> pass branch, because they classify backwards (a genuinely engaged clean review here spent 2,460
> tokens while the field's vacuous seat spent about ten times that, and an 8-second dispatch returned
> a Critical). It is also **never** scored on whether it detected the planted defect; a demonstrably
> live seat can miss the plant (measured twice: PR #667's round-1 control, and this build's own live
> probe, which spent 14,980 tokens and ran three repo commands while missing it). Without a probe,
> the round records `canaryUnverified` and the receipt carries a degraded disclosure; a probe that
> shows no engagement downgrades those seats to never-ran.

> **External-engine dispatches — timeout is structural, an expired slot is `unreadable` (#202, #204).**
> Every engine dispatch — the reviewer (read-only, above) AND the **fixer** (cursor, workspace-write) —
> runs as a Bash tool call, so its timeout is already **structural, not prompted**: the plugin's
> `PreToolUse(Bash)` floor (`hooks/bash_timeout.py`, #204) injects a 600s `timeout` on any dispatch
> that carries none, so a wedged engine CLI is bounded and killed instead of blocking the panel's
> `wait` forever (a hang is **not** fail-open — CONVENTIONS `§7.5`). You do **not** compose a
> per-dispatch watchdog. What this file owns is the **expiry contract**: treat a killed/timed-out
> dispatch as an **expired slot** — its stdout is absent or partial, so `engine_adapter.parse_result`
> returns `unreadable`. A timed-out **reviewer** then takes the existing UFR-7 re-run-on-Claude path;
> a timed-out **fixer** commits no external write and the fix falls open to Claude. A hang becomes a
> bounded cost, never a stuck loop.
>
> **Settled dispatch contract (issue #865).** The reconciliation between this skill's dispatch
> behaviour and the builder's native-shape rule is **closed** — not an open migration:
>
> 1. **External-engine seats (`codex`/`cursor`) satisfy the native-shape rule.** Each **launches**
>    through `dispatch-review` on a fresh `--run-dir` with a **short positive launch slice**, then
>    re-invokes the same `dispatch-review` on that `--run-dir` with `--max-wait 540` until the
>    structured result is terminal — the originating-verb continuation loop above.
>    **Claude seats** are native subagents (the `await-dispatches` ruling's native-subagent lifecycle
>    exemption); the runner cannot dispatch them. A build whose review seats ran through the runner
>    or as claude native subagents under this skill **owes no native-shape limitation disclosure**
>    for those seats.
> 2. **The in-place fixer is a reasoned, permanent exemption — not unfinished work.** It deliberately
>    stays a foreground Bash dispatch bounded by the `PreToolUse(Bash)` structural floor; see **Why the
>    in-place fixer is not a `dispatch-write` consumer** above. Adopting the write verb there would
>    require changing the auto-fix path's checkout model, which is not on the table.
> 3. **Two owners, one boundary — bounds vs channel.** This skill owns the **bounds** of the
>    dispatches it launches — slice sizes (a short launch slice and continuations up to `--max-wait
>    540`, never zero), structural timeout, retry ladder, and the standing rule that the caller
>    composes **no** per-dispatch watchdog. The builder's
>    `await-dispatches` ruling governs the **channel** for dispatches **the builder itself launches**.
>    Timeout contract stays the skill's; channel duty attaches to what the builder launches.
> 4. **The native-shape limitation disclosure is retired for runner-dispatched and claude-native
>    seats**, not blanket. The **hand-rolled engine fallback** below does not follow the native shape
>    (`--run-dir`, `--max-wait`, originating-verb continuation) — a round that used it **still owes
>    that disclosure**.
>
> **Hand-rolled engine dispatch — stdin form, empty-prompt guard, portable timeout (#563).** Prefer the
> supervised runner above; when a builder hand-rolls an engine CLI dispatch (exactly when the adapter
> path fails), three verified rules keep it from wedging:
> 1. **Always feed the prompt from a real file over redirected stdin — `codex exec … - < promptfile`
>    — never an inherited/open stdin.** codex `exec` reads its prompt from stdin when given `-`, no
>    positional prompt, or even an empty-string positional; if that stdin is an open source that
>    never delivers data or EOF (the inherited stdin of a headless dispatch with no `< file`
>    redirect), codex **hangs forever**. An EOF-closed empty stdin (`< /dev/null`) does not hang — it
>    errors fast. Repro'd 2026-07-23 against codex 0.144.1.
> 2. **Reject an empty/missing prompt before dispatch.** `engine_adapter.py build-argv --prompt-path
>    PATH` fails closed (emitting `{"ok":false,"reason":"empty-prompt",…}` instead of argv) unless
>    PATH is a readable regular file with non-whitespace content. The caller MUST redirect **that same
>    validated file** into the engine's stdin — validating one file and redirecting another (or none)
>    reopens the hang. (The supervised runner couples validate + redirect in one step, closing the
>    check/use window; a hand-rolled dispatch must couple them by hand.)
> 3. **Bound the run with a portable timeout — macOS has no `timeout(1)`.** Use a perl fork+kill
>    wrapper and a HIGH ceiling (≥900 s for a real engine run; never a borderline limit), redirecting
>    engine output to a **file** (never `| tail`, which buffers a stall to look identical to progress):
>    ```bash
>    perl -e 'my $t=shift; my $to=0; my $p=fork; die unless defined $p; if(!$p){exec @ARGV or die $!}
>      local $SIG{ALRM}=sub{$to=1; kill "KILL",$p}; alarm $t; waitpid $p,0; my $s=$?; alarm 0;
>      exit 124 if $to; exit($s>>8) if ($s&127)==0; exit(128+($s&127))' \
>      900 codex exec … - < promptfile > out.json 2> err.log
>    ```
>    (exit 124 = timed out.) Watch the process's **CPU-time column, not elapsed** — an engine CLI can
>    sit at ~0% CPU for minutes and still be live.
>
> **Dispatch-runner scope boundary (#563).** The supervised runner now supervises **both**
> `dispatch-review` and `dispatch-write`; each is a **distinct subcommand** with its **own** host
> grant string, so write autonomy is revocable on its own — that **is** the fresh authz design the
> earlier text here asked for, ratified in [#623](https://github.com/zwrose/superheroes/issues/623)
> and re-based by [#702](https://github.com/zwrose/superheroes/issues/702). (The paragraph's earlier
> prohibition against folding the write path into a Python runner is **superseded**.) The host
> permission classifier still gates the dispatch **at the Bash call** — absent a matching grant
> nothing spawns and the caller parks loudly. CONVENTIONS `§7.5` still holds and still means what it
> always meant: engine **selection** fails open when a seat is unavailable, a completed external
> **result** fails closed. It never said the write path may not be supervised.

After dispatch, wait for all five agents to return. A file-channel seat's findings are read from
`$SESSION_DIR/round-<round>/findings-<agent>.json`; a stdout-channel seat's findings come from the
terminal `dispatch-review` result, which the orchestrator folds. The orchestrator does not read agent
transcripts — only those structured outputs.

---

## Triage Subagent Prompt

```
You are triaging code-review findings for one round of an auto-fix loop.

## Input
- Findings to classify: $SESSION_DIR/round-<N>/compiled.json (use only the
  findings whose ids are in this list: <ids of effective findings>)
- Triage rubric: the base rubric's "Triage rubric (mechanical vs judgment)"
  section (absolute path: <absolute RUBRIC path>)
- Project profile: <PROFILE_PATH> (threat model, scope, focus hints)
- Project conventions: CLAUDE.md
- Code to inspect: the current working tree (read the cited files to judge
  whether a fix is mechanical or a judgment call)

## Your job
For EACH listed finding, emit TWO things — a fix-complexity classification AND an
orchestrator POV. Read the cited file before deciding; use what you read for both.

### 1. classification: "mechanical" or "judgment"
Apply the base rubric's "Triage rubric" — this is about the FIX, not whether to
fix. Mark "judgment" ONLY when applying the fix involves a real choice
(`finding.tradeoff === true`; a UX/design call with more than one reasonable
option; or a change to established product behavior the user may have an opinion
on). Everything else (one determinate, obviously-correct fix) → mechanical. Bias
hard toward mechanical.

### 2. recommendation (orchestrator POV) — EVERY finding
Per the base rubric's "Orchestrator POV", emit for every finding (this drives
whether the loop fixes it silently or stops to ask the user):
- recommendation: "Fix" | "Skip" | "Defer"
  - Fix = correct and worth the change here.
  - Skip = good reason not to (correct-but-not-worth-it for this project per the
    profile's threat model/scope, cost > benefit, or borderline/likely-false-
    positive on a closer read).
  - Defer = real but not now/not here (big-job, out of scope for this change).
- rationale: one sentence saying why.
- confidence: "High" | "Low" (Low = genuinely unsure; flags it for scrutiny).

## Output
Write $SESSION_DIR/round-<N>/triage.json — every listed finding id exactly once:
[ { "id": "<id>", "classification": "mechanical" | "judgment", "reason": "<one sentence>",
    "recommendation": "Fix" | "Skip" | "Defer", "rationale": "<one sentence>", "confidence": "High" | "Low" } ]
(All four POV-related fields are present on EVERY entry.)
```

---

## Fixer Subagent Prompt

**Fixer file-scope guard (`escalation-base.md` hard floor — runtime self-modification).** The guard runs
in the **fixer subagent** context, which does NOT inherit `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}` or `$REPO_ROOT`. So the
orchestrator embeds both absolute values into the fixer prompt's `## Input` block (the expanded `ESC_WRAPPER`
and `REPO_ROOT` resolved in setup), exactly as it embeds the absolute `RUBRIC`/`PROFILE` paths. Before the
fixer edits any file, it gates it with those embedded absolute values:
`python3 -B "<absolute ESC_WRAPPER path>" guard --root "<absolute REPO_ROOT>" --path "<file>"`.
If `allow` is false, the fixer MUST NOT edit that file (it is safety machinery — the authoritative
membership is the `SAFETY_MACHINERY` tuple in `escalation.py`); report the refusal and let the
orchestrator route it per `rubric/review-discipline.md` § *The safety-machinery route — the guard
refuses the fixer*. A `degraded:true`
result also refuses (fail-closed). The fixer never pushes/merges/deploys (those stay user-gated).

**Where those findings go next.** A refusal here means this loop **cannot converge on that surface** —
that is the guard's designed bound, not a defect, an engine failure, or an escalation trigger. The
route from the refusal to a fix — ordered implementer work orders on advisor or builder authority
with loud disclosure, the owner's word required only for the owner-authority-gate family, and the
park branch scoped to that family — is
`rubric/review-discipline.md` § *The safety-machinery route — the guard refuses the fixer*. Follow it
rather than re-deriving it; do not retry the fixer, and never narrow the guard to converge a round.

```
You are the fixer for one round of an auto-fix code-review loop.

## Input
- Findings to fix: $SESSION_DIR/round-<N>/fix-batch.json (array; each has
  id, severity, dimension, file, line, body, suggestion, and optional
  userGuidance)
- Conventions: CLAUDE.md and the project profile (<PROFILE_PATH>);
  severity/format from the base rubric (<absolute RUBRIC path>)
- Work in the current branch's working tree at <cwd>
- Repo root: <absolute REPO_ROOT>
- Escalation guard: <absolute ESC_WRAPPER path>
- Verify command: <VERIFY_CMD, or the literal "none" when the profile is mode: unverified>

## Your job
1. Apply a fix for EACH finding. Follow CLAUDE.md conventions and the profile's
   canonical patterns. When a finding has userGuidance, follow it over the
   original suggestion. BEFORE editing any file, gate it with the fixer
   file-scope guard, using the absolute "Escalation guard" and "Repo root"
   values from ## Input:
   `python3 -B "<absolute ESC_WRAPPER path>" guard --root "<absolute REPO_ROOT>" --path "<file>"`
   — if `allow` is false (or `degraded` is true), DO NOT edit that file (it is
   safety machinery); report it under "escalated" for the orchestrator to route instead. Never
   push/merge/deploy (those stay user-gated).
2. Fix ONLY what the findings call for. No unrelated refactors (YAGNI).
3. If a verify command was provided, run it. If it fails, fix the failure and
   retry ONCE. If it still fails, STOP and report CHECK_FAILED with the failing
   output — never commit broken code. If the verify command is "none"
   (unverified profile), skip this check entirely.
   When you need to verify something by *running* it, choose a throwaway test file path inside
   the build worktree, named with the fixed prefix `autofix-probe-` so a leftover one is
   identifiable. **Before writing it, check that the chosen path does not already exist** — a
   **filesystem** existence check on the path (does a file exist there), not a git query: git
   does not know about ignored or untracked-but-present files for this purpose, and this repo's
   gitignored `docs/` holds real owner content a git-flavoured check would miss. A
   crashed prior round can leave its own probe behind under a predictable name, and an
   unrelated tracked file could occupy it too. If the name is already taken, pick a different
   one (e.g. add a unique suffix, still carrying the `autofix-probe-` prefix) rather than
   overwriting whatever is there. If you cannot
   establish that your chosen path is new, do not write a probe there and do not delete
   anything — report it instead. Once the path is confirmed new, write the file and run it
   with the project's test-run family (e.g. `pytest` or the repo's test command); do not
   improvise inline interpreter one-liners (the `-c` / `-e` flag forms). Before you commit,
   delete **only the probe file you just wrote this round** — you know its name, because you
   just named it and confirmed it was new. Do not sweep for other files matching the prefix,
   and do not decide what to delete by reasoning from tracked or untracked status. A crashed
   round may leave its own probe behind, and nothing sweeps it up: a stray `autofix-probe-*`
   file can still be present in the working tree the orchestrator inspects when it verifies.
   Delete the throwaway before step 4's commit — it must never land in the fix commit.
4. Commit ALL changes in ONE commit (after the check passes, or immediately when
   unverified): `git commit -m "Auto-fix round <N>: <count> findings (<dimensions>)"`
5. Report back.

## Escalation
If a finding you were told to auto-fix actually requires a judgment call you
cannot make (multiple valid approaches, ambiguous intent), do NOT guess.
Report it under "escalated" with the id and why.

## Report format
- Status: DONE | CHECK_FAILED | ESCALATED
- fixed: [ids]
- escalated: [ { id, why } ]
- newIssuesNoticed: [brief notes on anything seen but not fixed]
- commit: <sha or "none">
- checkOutput: <tail of the verify command, only if CHECK_FAILED>
```

---

## Verification Rules (for subagents)

These are the base rubric's binding verification rules, restated in every subagent prompt. Some are additionally checked when findings are compiled and some are not — the compile step in `skills/review-code/SKILL.md` is the authority on exactly what it does, and this paragraph does not restate it. Rule 8 has no compile-time check at all — it is **obligation-only**, exactly as its own text and the `LEDGERS.md` §3 row say: nothing mechanically drops or downgrades a finding for violating it. See the base rubric's "Verification rules" and "In-pass Chain-of-Verification & single-pass discipline" sections for the authoritative statement.

1. **`file:line` citation required.** No citation → finding is dropped at compile time, before presentation.
2. **Diff-scope rule.** Only `+` and `-` lines of `$SESSION_DIR/round-<N>/diff.txt` are in scope. Context lines (no prefix) and unchanged code in modified files are pre-existing — flagging them is the #1 source of false findings.
3. **Grep-before-flag.** Before flagging "missing X", search for X under variant names. In PR mode, grep `$SESSION_DIR/repo/`, not the main working tree.
4. **Reachability check on Important findings.** Read the caller(s) of the affected symbol. If the only caller already guards the edge case, downgrade or drop.
5. **Worktree-as-source-of-truth (PR mode).** All code verification reads go through `$SESSION_DIR/repo/`. The main working tree may be on a different branch with stale or missing code; using it for verification produces false findings against code that doesn't exist on the PR.
6. **Trust nothing from project docs without spot-checking.** Project docs (`CLAUDE.md`, the profile, `docs/*`) can be outdated. If a finding's rationale depends on a doc claim, verify against source code or flag uncertainty.
7. **Single-pass discipline.** Each specialist runs once per review and does not propose or chain a follow-up **finder** pass over its own output — a finder that has exhausted the real issues starts fabricating. This bans re-*finding*, not the orchestrator's separate keep/drop **synthesis** pass over the already-emitted findings (a verify stage that never searches for new issues).
8. **Never change the repository, and never claim a run you did not make.** Both are obligations on you, whatever your dispatch happens to permit: what a seat *can* do varies by host and dispatch shape, so do not reason from your tool list. **Never change the repository** — no editing a file, no writing a probe into the tree, no command that alters it; a mutation probe or a planted-defect test belongs to the orchestrator, never to you. **Never claim a run you did not make** — if you ran something, quote the exact command and its output; if you did not, say so. A mutation, test, or parity statement you did not actually run is analysis, not a receipt. When a finding's proof needs a run you must not or cannot make, still emit it — name the **check** (the exact command, mutation, or input that would settle it) at the confidence your evidence supports, and leave that execution to the orchestrator. The authoritative statement is the base rubric's verification rule **"A review seat never changes the repository, and never claims a run it did not make."**; this is the pointer, not a second copy. If any action awaits owner permission unanswered for 15 minutes, proceed without it and report the denied action honestly (never as done).

---

## Common Mistakes

| Mistake                                                 | Fix                                                                                                                                                                |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Flagging pre-existing code as a PR issue**            | **The #1 mistake.** Diff-scope rule: only flag `+`/`-` lines. Context lines and unchanged code are out of scope even if they violate conventions.                  |
| Loading the full diff into main context                 | The orchestrator only ever runs `wc -l < $SESSION_DIR/round-<N>/diff.txt`. Subagents read the diff from disk; the orchestrator reads JSON findings.                |
| Finding based on assumed code state                     | Subagents must verify against `$SESSION_DIR/repo/` (PR mode) or the working tree (branch mode). No "I think this calls X" — open the file and confirm.             |
| Marking test issues as Critical                         | Critical is reserved for production bugs, data loss, security vulns. Test anti-patterns are Important at most — see the base rubric's "Severity tiers".            |
| Severity miscalibrated to deployment context            | Calibrate to the profile's threat model (strict / multi-user when the profile is absent). Don't raise threats the profile declares out of scope.                  |
| Using diff.txt line numbers as file line numbers        | Diff line numbers and file line numbers are different. A finding must cite the FILE line; `lib/diff_scope.py` parses `@@` hunk headers to derive which file lines the round diff makes anchorable, and the compile step drops a finding that misses them. |
| Re-flagging issues the author already justified         | PR mode: raise the finding and note the prior justification; the post-verification filter drops only non-CONFIRMED findings (see `round-driver.md`). |
| Dropping resolved Important findings silently           | If reachability or the post-verification author-justification filter drops an Important, mention it — the justification is quoted in the record.                      |
| Tiering or skipping specialists based on "what changed" | Round 1 is always the full panel; later rounds follow `round_driver.py` `next` (delta audits + scoped finder, or a full panel on #174/unknown). Never skip by eye. |
| **Continuing when `$BASE_REF` is not a commit**         | An empty `$BASE_REF` makes `git diff "$BASE_REF"...HEAD` argv `...HEAD` — git reads it as `HEAD...HEAD` and emits a **zero-line diff at exit 0**, so the panel reviews nothing and the loop certifies clean. The literal string `null` (what `jq -r` prints for an absent key) is non-empty, so a `[ -n … ]` test passes it while `git diff null...HEAD` exits 128 and still leaves an empty artifact. Setup validates with `git rev-parse --verify --quiet "$BASE_REF^{commit}"` — which rejects empty, `null`, a deleted branch, and a non-commit tag — and every consumer uses the guarded diff command that halts on a failed OR empty diff. Never substitute a branch name to "recover" (#637). |
| **Diffing against the worktree's local base branch**    | A long-lived worktree's local `main` goes stale as a matter of course; three-dot diff then walks back to a stale merge-base and drags already-merged work into the review (#637 — ~6,600 contaminated lines against 2,931 real). The bootstrap fetches the base and pins it to a commit; never re-resolve the base from a branch name mid-run. |
| Using `gh pr diff` inside the loop                      | Rounds 2+ have local fix commits not on the remote. Always recompute the diff locally each round **with the guarded per-round command from the SKILL's Setup** — `git diff "$BASE_REF"...HEAD` against the **pinned remote base commit**, including its failed-diff and empty-diff halts — never a branch name and never a bare copy.                                               |
| Auto-fixing a PR you don't have checked out             | Auto-fix needs the PR's branch as the current branch **or** an adopted build (tracks remote `origin` with merge ref `refs/heads/<PR branch>` **and** `HEAD` == the PR's `headRefOid`); anything else — detached HEAD, an unrelated branch, a stale adopted branch — stops and goes to `--review-only`.                                        |
| Re-reviewing on a broken tree                           | If `VERIFY_CMD` fails after a fix, HALT. Never run the next review round on code that doesn't pass verification. (No gate when the profile is `mode: unverified`.) |
| Re-raising a finding the user skipped                   | Skipped identities go in the skip-set and are excluded from every later round's effective findings AND the circuit breaker.                                        |
| Eyeballing "are we stuck?" by hand                      | The audit-keyed stall breaker lives in `round_driver.py` — never call `circuit_breaker.py` inside the auto-fix loop.                                                 |
| Exiting the loop early because a fix "looks done"       | Obey `round_driver.py` `next`/`submit` — never `code_loop_plan` or manual continuation. "Trivial fix / save tokens / offer optional round" are the rationalizations it overrides. |
| Pushing automatically at loop end                       | The loop commits locally only. Pushing is always a separate, user-confirmed step.                                                                                 |
| Dispatching reviewers by reading an agent file          | The five reviewers are bundled plugin agents — dispatch the `<name>` reviewer with its methodology (resolve dispatch via the host tool map (`hosts/<host>-tools.md` at the plugin root)).                  |
| Skipping the profile bootstrap                           | If `.claude/review-profile.md` is absent, run review-init's create procedure inline first. When no profile resolves, every run gets a provisional strict profile. |

---

## Per-seat dispatch + the seat map (#510)

The round-1 panel composes over live vendors via a per-seat **seat map** (`lib/seat_map.py`,
computed once in the SKILL as `$SEAT_MAP`). Each of the five lens seats plus the grounding seat
carries `{vendor, model, effort, tier, family, source}`:

- **Read the seat's assignment** from `$SEAT_MAP.seats[<reviewer-name>]`. Dispatch a `claude`
  seat as the named subagent with `model: <seat>.model`; dispatch a `codex`/`cursor` seat through
  `engine_adapter.py` (read-only sandbox), threading the seat's **registry id** as `engine_model`
  and its **effort** as `--effort` — never the hard-coded composer default. `build-argv` also
  accepts the **composed dispatch token** that joins registry id and effort, and resolves it
  identically, but an effort that **contradicts** a composed token is refused rather than
  silently resolved either way. A `--model` value that is not a native Claude tier short name
  (`haiku`/`sonnet`/`opus`/`fable`) is **refused by name** (`unknown-claude-tier`) instead of
  silently falling back to composer. A refused dispatch surfaces
  `detail: "engine-config:<reason>"` with one of `unknown-engine`, `unknown-claude-tier`,
  `fable-unrunnable`, `unregistered-engine-model`, `engine-model-effort-conflict`,
  `invalid-model-effort`, `untokenizable` — so the panel's degradation disclosure names **what**
  died. The persona and `$RUBRIC` are identical across engines; the only per-seat difference is
  the dispatch target.
- **The grounding seat** (`$SEAT_MAP.seats["grounding-seat"]`) is *assigned* a vendor by the seat map
  — chosen to be independent of both the author (code) and narrative (PR text) families — and that
  assignment is recorded in the receipt. On the **read-only path** (`--review-only`) it
  is **live-dispatched under #609** with the PR body staged as seat-readable input — full contract:
  `grounding-seat.md`. The driver-owned auto-fix loop does **not** run SKILL step 8 today,
  so on that path the seat does not influence certification.
- **Independence keys on model family, not the dispatch CLI** (CONVENTIONS §7.5), and **cursor's
  first-party models are ONE family**: the token-efficient implementer and grok judge models both
  carry the `xai` independence-accounting key (#651, owner-ratified 2026-07-26; post-acquisition
  affiliation as of 2026-08-14 — **behaviour unchanged**). A `cursor` review seat is therefore NOT independent of a
  cursor/composer implementer — a composer-made diff stamps `authorFamily = xai`, so the seat map
  excludes the maker family from **rotation** onto every panel seat — all five lens seats
  (`architecture-reviewer`, `code-reviewer`, `security-reviewer`, `test-reviewer`,
  `premortem-reviewer`) **and** the `grounding-seat` (#670, owner-ratified 2026-07-26), not
  merely from strong-tier, critical, and grounding. An owner pin can still seat the maker family;
  `verify()` flags a `maker-family` violation and records `pin-breaks-constraint` for that seat.
  Where an alternative family is live, the maker family never seats through rotation and such a
  panel buys its independence from anthropic/openai instead; where
  none is live, the seat still fills with the maker family and the map records a disclosed
  `same-family` degradation, which rides the certification shape (`-degraded`) alongside
  `independenceDegraded`, `baseDegraded`, and disclosed `plugin-version-skew` (semantics-divergent
  or evidence-unreadable across `lib/model_registry.py`, `lib/seat_map.py`, and `lib/version_skew.py`
  against the superheroes source repo — detection only, not a version-string compare). The `verify()` result (the #547c
  maker-family-vs-seat check) now separates a **violation** (maker family seated when an
  alternative was reachable) from that unavoidable **degradation**; unusable liveness evidence
  fails closed to violation. Every degradation / unhonorable-pin fallback is recorded in the
  seat-map receipt, so a downgraded composition is visible at vet time, never silent.
