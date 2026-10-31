<!-- auto-fix-loop-version: 1 -->
## Contents

1. [Specialist Dispatch Prompt Template](#specialist-dispatch-prompt-template)
2. [Triage Subagent Prompt](#triage-subagent-prompt)
3. [Applying the fixes](#applying-the-fixes)
4. [Verification Rules (for subagents)](#verification-rules-for-subagents)
5. [Common Mistakes](#common-mistakes)
6. [Break-it tests](#break-it-tests)

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
mechanical-focus-flag detector over the round diff (grep-detected **additive** brief flags;
**additions only, never classifier-driven lens removal**):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/focus_flags.py" "$SESSION_DIR/round-<round>/diff.txt"
```

It prints zero or more flag lines (a changed migration file → rollback/data-safety
emphasis; a changed dependency lockfile → supply-chain check). **Append** each emitted
line into every specialist's `Focus:` context block, alongside any `--focus` notes — an
addition that never replaces the `--focus` notes and never removes or down-scopes a lens
(classifier-driven lens removal is banned). If nothing is emitted, append
nothing. The detector is grep-grounded and has no authority to drop a finding or a lens.

> **External-engine reviewers — stdout channel grading mechanics.** When `$REVIEWER_ENGINE` is
> `codex` or `cursor`, a specialist is dispatched through `engine_adapter.py` (read-only sandbox)
> instead of a named subagent, and it returns its payload on **stdout** rather than writing a
> findings file. Panel seats emit `{"findings": [...], "investigated": [...]}`; verifier seats emit
> `{"verdicts": [...], "investigated": [...]}`; synthesis judges emit `{"grouping": [...]}`; fix
> auditors emit `{id, ruling, reason}`. The graded result carries **`resultKind`** (one of
> `REVIEW_RESULT_KINDS` in `lib/engine_adapter.py`) naming which payload key survived. A non-empty
> payload succeeds without `investigated`; only an **empty** payload needs a surviving
> `investigated` path (see below). **Findings-only prompt authoring** (caller side): cite
> `skills/workhorse/reference/dispatch-mechanics.md` § *Findings-only review prompts* — a prompt
> that demands a single JSON object without requiring `investigated` guarantees a vacuous forfeit
> when the honest answer is no findings. The contract shape also lives in the base rubric's
> "Findings output format" section; the
> dispatch prompt's `## Output` block names the seat's channel — this block is how the runner grades
> what the rubric already specified. `engine_adapter.parse_result` scans stdout for the **last
> top-level JSON value**, so incidental trailing prose after a valid object is tolerated. An **empty**
> `findings` array is accepted as *clean* **only** when its `investigated` list survives the
> runner's investigation floor (`engine_adapter.spot_check_investigated` in `lib/engine_adapter.py`).
> A seat that returns empty findings with no verifiable `investigated` record is a
> **vacuous forfeit** — a named cause (`reason: "vacuous"` from `dispatch-review`): treated as a seat
> that **never ran**, not as a clean review; the orchestrator submits the folded seat with
> `vacuous: true` (or `reason: "vacuous"`). Engine telemetry (token spend, tool calls, wall time) is
> **corroborating evidence only** and can never satisfy that investigation floor. The parser also
> **tolerates a bare top-level array** `[...]` of finding objects, but anything else
> (prose with no parseable JSON object/array, an empty stream, an array of non-objects) parses as
> `unreadable`, which forfeits the slot to a re-run on a vendor outside every maker family (the
> driver's choice; with none, the seat is recorded missing and counts as not run) and silently doubles the
> round's cost.

> **Reviewer-seat dispatch runs through the dispatch RUNNER — reviewer role ONLY.**
> When `$REVIEWER_ENGINE` is `codex` or `cursor`, dispatch each read-only reviewer seat through
> `lib/engine_dispatch.py dispatch-review` (not a hand-rolled `codex exec` / `cursor-agent` shell
> line). The runner owns the previously per-session dispatch mechanics as **machinery**: it prepends
> the anti-hijack preamble (the hardening that stops the codex SessionStart/skill-selection
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
> toward the panel, and the loop's behaviour is unchanged). A forfeit → the orchestrator re-runs the seat on another live vendor from the seat map's `liveVendors` whose family is outside every maker family, only when that vendor takes the same delivery channel as the emitted order (never hand-compose a replacement order), recording which vendor ran it in its dispatch record (the driver does not reseat a panel seat; for the non-panel phases the driver re-emits the order to the same selected vendor, with no switch to another vendor in this layer, and a non-panel result whose recorded vendor is not the one its order named is ignored and disclosed); with no such vendor live on that channel, the seat is recorded missing (`record-missing`) and counts as not run, and it is never re-run on the host model when the host's family is a maker and the
> orchestrator **discloses** the degraded vendor mix (the `disclosure` string); the driver also records
> the fall-open on the receipt from the orchestrator's `ranManifest` (`round-driver.md`,
> `dispatch-panel`).
>
> **Sanitized review view.** The seat does not run inside the owner's checkout. The runner
> materializes a fresh single-commit git repo at `headSha` holding the reviewed tree, with the named
> repo-local agent-config surface removed (`AGENTS.md`, `.cursor/`, `CLAUDE.md`, and the other basenames
> the runner strips at every directory level). That config is **not discoverable** from the seat's cwd —
> which is the point of the view. The project's own conventions still reach the seat by path: every
> reviewer order the driver renders (panel, verifiers, synthesis, seams-check, audits, scoped finder)
> names the core calibration, the review-crew layer and the project's `CLAUDE.md` by absolute paths
> into the live checkout, resolved once when the order renders, and the view's notice tells the seat
> that a file its order names by an absolute path is readable there. A project with no `CLAUDE.md`
> gets the sentence `(this project has no CLAUDE.md at <repo root>)` in its place. Never paste a
> calibration file or `CLAUDE.md` into a seat prompt by hand.
> Reading ordinary source files and `git grep` work; **`git log`,
> `git blame`, `git diff <ref>`, and `git show <ref>` do not** — the view has no `origin/main`, no
> remote, and no parent commit (one synthetic commit, no history). The dispatch prompt's auto-prepended
> notice states this prohibition to the seat explicitly. Paths the runner stripped are **unreadable**
> even when the diff under review touches them — the dispatch prompt should name stripped paths so the
> seat knows why a read failed. The one exception: with `--diff-base`, a changed regular file under
> exactly `.claude/superheroes/` whose remainder matches no other stripped name is shown in full and kept
> in the review patch; symlinks, gitlinks, deleted or renamed-away files, case or alias variants and every
> other `.claude/` path stay withheld.
>
> **`--mode {review,brief-check}` (optional, default `review`).** `--mode review` or omitted →
> behaviour identical to today, including `--diff-base` resolving to an empty patch →
> `sanitized-view-diff-empty`, `attempts: 0`. `--mode brief-check` → the sanitized view is built
> **diff-less**; all six `sanitizedView` diff keys below are `null`. Supplying **both**
> `--mode brief-check` and `--diff-base` is a terminal refusal `mode-brief-check-with-diff-base`,
> `attempts: 0`, no spawn — **including on continuation**, because the check runs before the journal
> read. On continuation, an explicitly disagreeing `--mode` is
> `run-dir-mode-mismatch`, `attempts: 0`; omitted `--mode` inherits the mode the run was opened with
> (a journal written before this change, with no `mode` key, normalizes to `review`); when inherited
> mode is `brief-check` and `--mode` is omitted, `--diff-base` stays accepted-and-ignored. Every
> `dispatch-review` result carries a top-level **`mode`** string — success, forfeit, and every
> pre-spawn refusal alike. Registry/model gate, sanitized-view export and config strip, the
> investigation floor, engagement read, and vacuous-forfeit accounting are unchanged in both modes.
>
> **`--diff-base <commit-oid>` (optional).** Omitted → nothing is staged and the six receipt keys
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
> **`--leave-out-file <path>` (optional).** The review loop's driver writes
> `<session dir>/reviewer-leave-out.json`, `{"schema": "leave-out/1", "files": [<repo-relative path>, ...]}`,
> naming the changed files the change proves byte-for-byte copies of a named source. With `--diff-base`,
> the patch staged in the view leaves out every listed path that is in the change (matched on its head-side
> path); the seat's notice says how many changed files were left out and that they are not part of what it
> reviews. A listed path that is not in the change is ignored. A file that is missing, unreadable, not
> JSON, or of the wrong shape (extra or missing key, a non-list `files`, a duplicate, blank, absolute,
> `..`-segment or backslash entry) refuses `sanitized-view-leave-out-invalid` on a launch, with or without
> `--diff-base`, before anything is spawned. A change whose every file is left out refuses `sanitized-view-diff-empty`; a
> change whose only non-config file is left out beside a withheld config file is reviewed as config only, with
> the left-out file in neither the patch nor the configuration-changes file. On a
> continuation it is accepted and ignored, as `--diff-base` is. It adds no `sanitizedView` receipt key.
>
> The staged review patch, the review-only configuration-changes file, and the staged PR body are
> **rejected from the investigation floor**: a seat whose `investigated` array cites only these
> artifacts fails the floor and forfeits vacuously, exactly as if it had cited nothing.
> Rejection is by resolved file identity, so `./NAME`, `a/../NAME` and a symlink to it are all
> rejected. The rejection reason string is `generated-artifact`.
>
> **Six `sanitizedView` receipt keys** (always present, `null` when `--diff-base` was not used):
>
> | key | meaning |
> |---|---|
> | `diffBase` | the resolved **merge-base** sha the patch is against (40 hex chars, or 64 in a SHA-256 repository) |
> | `diffPath` | `SUPERHEROES_REVIEW_DIFF.patch`, relative to the view root; `null` when every changed path was withheld, in which case the whole change is in `configDiffPath` |
> | `diffBytes` | patch size in bytes; `null` when every changed path was withheld, in which case the whole change is in `configDiffPath` |
> | `diffWithheldCount` | **only** the changed non-tree entries the stripped-config policy withheld (it excludes the changed calibration files shown in full, and a view built without `--diff-base`, brief-check included, shows none); undecodable paths, unrecognized spans, and unaccounted census entries **refuse the dispatch** rather than being counted here — opaque review-patch content refuses unless it is a genuine binary blob (placeholder line); opaque content in the configuration-changes file still refuses — this is what keeps the reviewer-facing "the absence is not a finding" statement true |
> | `configDiffPath` | `SUPERHEROES_CONFIG_CHANGES_UNDER_REVIEW.txt`, relative to the view root, when withheld configuration hunks were staged; `null` when nothing was withheld |
> | `configDiffBytes` | size in bytes of that configuration-changes file; `null` when `configDiffPath` is `null` |
>
> A change whose every path is withheld is reviewed from the configuration-changes file alone, and a
> leaf named like a config directory (such as a `.claude` symlink) is withheld too.
>
> The census of changed paths comes from direct two-tree enumeration (`git ls-tree` on the
> merge-base and head), not from patch presentation — `git diff`, rendered patch text, or a list of
> presently-known dangerous configuration keys. Sections on stripped paths are filtered out of the
> review patch; a section whose path cannot be decoded refuses; an unrecognized span refuses. The
> merge-base is resolved directly in the reviewed repository under an environment built by dropping
> every inherited `GIT_*` variable, with replace-refs and the commit-graph pinned off — and
> repository-local ancestry overlays such as `.git/info/grafts` are honoured. An empty directory
> added or removed in a commit is a tree-only change carrying no file, symlink or gitlink content,
> `git diff` renders nothing for it either, and it is therefore outside this contract. Opaque or
> unaccounted content returns a named terminal refusal (`attempts: 0`) that is never interpreted as
> zero findings or a clean review; genuine binary blobs in the review patch appear as placeholder
> lines instead. There is no automatic fallback.
>
> **Diff refusals** (all `attempts: 0`, no token spend), joining the existing `sanitized-view-*`
> family:
>
> | token | when |
> |---|---|
> | `sanitized-view-diff-base-abbreviated` | the base is an abbreviated hex commit id; pass the full 40- or 64-character id |
> | `sanitized-view-diff-base-unresolved` | the base is empty, begins with `-`, is not a full 40-/64-hex commit object id (non-hex, fewer than four hex digits, or hex lengths of 41–63 or 65 or more), does not resolve to a commit, shares no merge base with head, the repository's shallow state cannot be determined from its git, or the merge-base cannot be established |
> | `sanitized-view-diff-base-shallow` | the reviewed repository is a shallow clone, so the genuine merge-base cannot be established from its object store; fetch full history (for example `fetch-depth: 0` or `git fetch --unshallow`) and dispatch again |
> | `sanitized-view-diff-empty` | a base was requested and the change has no paths, or the resulting patch is empty with nothing withheld, or every changed path was withheld and their hunks render nothing, or every file in the change is left out by `--leave-out-file` |
> | `sanitized-view-diff-too-large` | the patch exceeds the 8 MiB ceiling, or census `ls-tree` stdout exceeds the export byte ceiling |
> | `sanitized-view-diff-path-collision` | the repository already tracks a file named `SUPERHEROES_REVIEW_DIFF.patch` |
> | `sanitized-view-diff-config-path-collision` | the review-only configuration-changes file could not be created at its name in the view, or did not read back as written |
> | `sanitized-view-diff-config-too-large` | the assembled review-only configuration-changes file exceeds its size cap, or patch streaming hits its byte ceiling while those hunks are being generated |
> | `sanitized-view-diff-failed` | a git subprocess failed while resolving ancestry or generating the patch (spawn error, non-zero exit, timeout) — command failure only |
> | `sanitized-view-diff-opaque` | a rendered section whose content is opaque — `Binary files … differ` (or `GIT binary patch`) instead of hunks — when it is not a genuine binary blob placeholder, or in the configuration-changes file |
> | `sanitized-view-diff-unaccounted` | a census tree containing the same path more than once, a patch section whose path cannot be decoded, or an unrecognized span in the patch text |
>
> **Mode refusals** (all `attempts: 0`, no spawn — not members of the `sanitized-view-*`
> diff-refusal family above):
>
> | token | when |
> |---|---|
> | `mode-invalid` | `--mode` is not a string in `{review,brief-check}` — top-level `mode` stays canonical (`review`); the rejected value is in `rejectedMode` |
> | `mode-brief-check-with-diff-base` | `--mode brief-check` and `--diff-base` were both explicitly supplied |
> | `run-dir-mode-mismatch` | continuation with an explicitly disagreeing `--mode` |
> | `run-dir-claude-mode-mismatch` | a continuation supplies a `--claude-mode` that disagrees with the one the run was opened with; refused with `attempts: 0`, nothing spawned |
> | `claude-mode-retired` | `--claude-mode background` on either `dispatch-review` or `dispatch-write` — background mode is retired; refused with `attempts: 0`, nothing spawned, never falls back to print |
> | `run-dir-claude-mode-retired` | a continuation of a run opened in background mode; refused with `attempts: 0`, nothing re-opened or spawned |
> | `run-dir-claude-mode-unknown` | a continuation of a run whose journal records a claude mode that is neither declared nor retired; refused with `attempts: 0`, nothing re-opened or spawned |
>
> **Investigation floor.** A seat that cites a **stripped** path in its `investigated` array fails
> the investigation floor and forfeits vacuously — fail-safe (the seat is re-run on a vendor outside every maker family, or recorded missing and counted as not run when there is none; never on the host model when the host's family is a maker), never a
> false clean.
>
> **CLI `parse-result` echo gap.** The CLI `parse-result --role review` path does not receive the
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
> `sanitized-view-export-failed`, `sanitized-view-export-timeout`,
> and `sanitized-view-init-failed`
> (also `attempts: 0`). There is
> **no fallback to the raw repo and no opt-out**.
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
> `diffPath`, `diffBytes`, `diffWithheldCount`, `configDiffPath`, and `configDiffBytes` — the last
> six always present, `null` when `--diff-base` was not used). The `bytes` and `fileCount` figures
> **include** the staged patch when
> one was written. The view is the **committed** tree at `headSha`; `sourceDirty: true` flags modified
> tracked files in the source repo
> so a caller reviewing uncommitted work is disclosed rather than silently given the pre-change tree.
> Every result also carries **`terminal`**, **`argv`** (the exact spawned command), **`runDir`**, and
> top-level **`mode`** (`review` or `brief-check`).
>
> **Result shape — top-level, no wrapper.** Every `dispatch-review` result object carries
> **`ok`**, **`terminal`**, **`runDir`**, **`argv`**, and **`mode`** at the top level. On a failure it also
> carries **`reason`** (and usually **`detail`**). On success it also carries **`resultKind`**
> (one of `REVIEW_RESULT_KINDS` in `lib/engine_adapter.py`) naming the payload, plus **exactly one**
> payload key of that name.
> **`investigated`** is present only when a claimed path survives the runner's investigation floor (`engine_adapter.spot_check_investigated`); a normal non-empty payload reply omits it. Outcome-dependent keys also include **`engagement`** and
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
> **Review payload transport.** The runner accepts result kinds on stdout
> (`REVIEW_RESULT_KINDS` in `lib/engine_adapter.py`). Every
> `ok: true` review result carries **`resultKind`** naming exactly one payload key of that name;
> **`investigated`** is attached only when a claimed path survives the investigation floor.
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
> its own engagement floor; the findings-only posture for panel seats is carried by the pin those
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
> **`engagement.read`.** When the result carries an **`engagement`** block with a non-`null`
> value (present only when the attempt produced stdout that was graded), `engagement.read` is
> `"engaged"` when the seat demonstrably acted: at least
> one finding returned, or `engagement.toolCalls` is not
> `None` and `>= 1`. Otherwise it is `"unknown"`. A seat's `investigated` list is **disclosure**,
> not engagement evidence; the runner still spot-checks it. On a timeout, refusal, nonzero-exit, or
> missing-stdout forfeit the `engagement` key is **present with the value `null`** (there was no graded
> stdout to measure), so `engagement.read` is unavailable — `result.get("engagement", {})` is
> **unsafe** because the key may carry `null`, not merely be missing; consumers must handle a `null`
> value. The runner **never** reports `"inert"` — absence of positive evidence is not proof of
> inaction, because a correct payload the transport could not read looks identical to a seat that never
> ran. Whether a seat actually looked is proven only by that seat's runner telemetry (recorded tool
> calls and reads).
>
> **Tokens are corroborating evidence only — measured.** Engine telemetry (token spend, tool
> calls, wall time) remains **corroborating evidence only** and can never satisfy the investigation
> floor — the field heuristic that "~23K tokens means vacuous, ~83–175K means real work" is refuted.
> Through the identical `dispatch-review` path with the calibrated codex reviewer seat
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
> `CLAUDE.md` stripped.
>
> **`payloadShape` on shape-unreadable forfeit.** When the **last** attempt forfeits because
> stdout was shape-unreadable, the result may carry `payloadShape`: a mapping with `parsed` (one of
> the tokens in `engine_adapter.REVIEW_PAYLOAD_SHAPES` — the one home for this enumeration;
> read it there rather than a restated list here), `topLevelKeys` (a list of strings,
> populated only when
> `parsed` is `object-without-findings` or `object-both-payload-keys`), `keysTruncated` (bool; signals the key list was
> capped), and on hollow-family diagnostics only (the `*-hollow-member` / `*-partial-hollow-member` shapes — read the token enumeration in `engine_adapter.REVIEW_PAYLOAD_SHAPES` rather than a restated list here) `memberShapeWanted` and `memberShapeGot` (each a short bounded token naming the member shape the grader **wanted** and **got**, respectively). Diagnosis only — it never changes the fail direction. `payloadShape` is **absent** on a
> vacuous forfeit and on success.
>
> **Originating-verb continuation loop.** Open with `--run-dir` (or omit it for a private temp run dir
> that loops to terminal). **Launch** each `--run-dir` with a **short positive slice** (12–45 s is the
> measured range in `skills/workhorse/reference/dispatch-mechanics.md` § Launch slice vs continuation slice);
> then re-invoke **`dispatch-review`** (never `dispatch-poll`) on the same `--run-dir` with
> `--max-wait 540` while `.terminal` is false. A non-terminal
> `{"reason": "running", "terminal": false}` is **not** a forfeit. `dispatch-poll` is observational
> and never spawns; `dispatch-abandon` is how a run directory is abandoned. Omitting `--max-wait`
> loops until terminal in 540 s slices — below the **600 s foreground-conversion boundary**.
>
> ```bash
> ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
> # Per external seat — the orchestrator sets these before this recipe runs:
> #   $SEAT_KEY       roster seat key (e.g. code-reviewer) — indexes $SEAT_MAP.seats
> #   $SEAT_PROMPT    emitted order path for this seat
> #   $RUN_DIR        fresh run directory (created by first dispatch-review)
> #   $SEAT_PROGRESS  progress file outside $RUN_DIR
> case "$SEAT_KEY" in ""|null)
>   echo "dispatch-review: SEAT_KEY unset — cannot resolve seat map entry (fail closed)." >&2; exit 1;; esac
> SEAT_CELL=$(printf '%s' "$SEAT_MAP" | jq -c ".seats[\"$SEAT_KEY\"] // empty")
> case "$SEAT_CELL" in ""|null)
>   echo "dispatch-review: seat map has no entry for SEAT_KEY=$SEAT_KEY (fail closed)." >&2; exit 1;; esac
> SEAT_VENDOR=$(printf '%s' "$SEAT_CELL" | jq -r '.vendor // empty')
> SEAT_ENGINE_MODEL=$(printf '%s' "$SEAT_CELL" | jq -r '.model // empty')
> SEAT_TIER=$(printf '%s' "$SEAT_CELL" | jq -r '.tier // empty')
> SEAT_EFFORT=$(printf '%s' "$SEAT_CELL" | jq -r '.effort // empty')
> if [ -z "$SEAT_VENDOR" ] || [ "$SEAT_VENDOR" = "null" ] || \
>    [ -z "$SEAT_ENGINE_MODEL" ] || [ "$SEAT_ENGINE_MODEL" = "null" ] || \
>    [ -z "$SEAT_TIER" ] || [ "$SEAT_TIER" = "null" ]; then
>   echo "dispatch-review: seat map entry for SEAT_KEY=$SEAT_KEY is malformed (fail closed)." >&2; exit 1
> fi
> if [ "$SEAT_EFFORT" = "null" ]; then SEAT_EFFORT_JSON=null; else SEAT_EFFORT_JSON="\"$SEAT_EFFORT\""; fi
> SEAT_JSON='{"vendor":"'"$SEAT_VENDOR"'","model":"'"$SEAT_ENGINE_MODEL"'","effort":'"$SEAT_EFFORT_JSON"',"role":"'"$SEAT_TIER"'"}'
> # Keep $SEAT_PROGRESS outside $RUN_DIR — non-empty run-dir → run-dir-not-empty-unopened
> # A session begun before the leave-out sidecar existed (a pending panel resumed after an upgrade) has no
> # reviewer-leave-out.json; pass the flag only when the file is there, since a missing file refuses the launch.
> LEAVE_OUT_ARGS=(); [ -f "$SESSION_DIR/reviewer-leave-out.json" ] && LEAVE_OUT_ARGS=(--leave-out-file "$SESSION_DIR/reviewer-leave-out.json")
> # The scoped finder reviews only the fix delta its order names (FIX_DIFF_PATH). `--diff-base "$BASE_REF"`
> # would stage the full PR patch and tell the seat to read it first, contradicting that scope — so that
> # seat launches without `--diff-base` (nothing staged); every other seat keeps the full-PR patch.
> DIFF_BASE_ARGS=(--diff-base "$BASE_REF"); [ "$SEAT_KEY" = "scoped-finder" ] && DIFF_BASE_ARGS=()
> # LAUNCH — first call on each --run-dir: short positive slice (see dispatch-mechanics.md)
> python3 -B "$ROOT_DIR/lib/engine_dispatch.py" dispatch-review \
>   --seat "$SEAT_JSON" \
>   --prompt-path "$SEAT_PROMPT" --repo-root "$REPO_ROOT" \
>   ${DIFF_BASE_ARGS[@]+"${DIFF_BASE_ARGS[@]}"} \
>   ${LEAVE_OUT_ARGS[@]+"${LEAVE_OUT_ARGS[@]}"} \
>   --expected-result-kind findings \
>   --run-dir "$RUN_DIR" --max-wait 12 \
>   --progress-file "$SEAT_PROGRESS" --timeout 900 --retry-timeout 900
> # CONTINUATION — re-invoke while .terminal is false: full slice up to 540 s
> python3 -B "$ROOT_DIR/lib/engine_dispatch.py" dispatch-review \
>   --seat "$SEAT_JSON" \
>   --prompt-path "$SEAT_PROMPT" --repo-root "$REPO_ROOT" \
>   ${DIFF_BASE_ARGS[@]+"${DIFF_BASE_ARGS[@]}"} \
>   --expected-result-kind findings \
>   --run-dir "$RUN_DIR" --max-wait 540 \
>   --progress-file "$SEAT_PROGRESS" --timeout 900 --retry-timeout 900
> ```
>
> For the full `dispatch-review` argument surface, read
> `skills/workhorse/reference/dispatch-entry.md`.
>
> Read-only sandbox is **hard-coded inside the runner API** — it cannot emit a write dispatch. The
> seat reviews by reading inside the sanitized view and never runs the project's own files, scripts
> or tests; every seat order carries that rule from the renderer (`round_orders.py`). Inlining the diff in the seat prompt remains available and is still reasonable for a
> small diff, but it is no longer the only way a seat gets the change.
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
> — never a soft failure, never a silent fall-open. `configure` does not offer the rule; the owner
> pastes it by hand.

> **External-engine dispatches — timeout is structural, an expired slot is `unreadable`.**
> Every engine dispatch (the reviewer, read-only, above)
> runs as a Bash tool call, so its timeout is already **structural, not prompted**: the plugin's
> `PreToolUse(Bash)` floor (`hooks/bash_timeout.py`) injects a 600s `timeout` on any dispatch
> that carries none, so a wedged engine CLI is bounded and killed instead of blocking the panel's
> `wait` forever (a hang is **not** fail-open — CONVENTIONS `§7.5`). You do **not** compose a
> per-dispatch watchdog. What this file owns is the **expiry contract**: treat a killed/timed-out
> dispatch as an **expired slot** — its stdout is absent or partial, so `engine_adapter.parse_result`
> returns `unreadable`. A timed-out **reviewer** then takes the existing re-run-on-the-host-model path.
> A hang becomes a bounded cost, never a stuck loop.
>
> **Settled dispatch contract.** The reconciliation between this skill's dispatch
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
> 2. **The fix step is not a dispatch.** The build session applies review fixes itself, in the
>    checked-out branch of the current checkout, at the loop's `apply-fixes` step; no fixer is
>    dispatched and no write verb takes part.
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
> **Hand-rolled engine dispatch — stdin form, empty-prompt guard, portable timeout.** Prefer the
> supervised runner above: the sanctioned call is `engine_dispatch.py dispatch-review`, and a
> hand-rolled engine call must redirect stdin from a file or `/dev/null`. When a builder hand-rolls an
> engine CLI dispatch (exactly when the adapter path fails), three verified rules keep it from wedging:
> 1. **Always feed the prompt from a real file over redirected stdin — `codex exec … - < promptfile`
>    — never an inherited/open stdin.** codex `exec` reads its prompt from stdin when given `-`, no
>    positional prompt, or even an empty-string positional; if that stdin is an open source that
>    never delivers data or EOF (the inherited stdin of a headless dispatch with no `< file`
>    redirect), codex **hangs forever**. An EOF-closed empty stdin (`< /dev/null`) does not hang — it
>    errors fast.
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
> **A hand-rolled review dispatch feeds the runner's preamble first.** The runner puts
> `engine_dispatch.ANTIHIJACK_PREAMBLE`, which carries the review seat rule (#2071), ahead of every
> engine review prompt. A hand-rolled review or brief-check call writes it to the top of its prompt
> file from that one home, then appends the order:
> `python3 -B -c "import sys; sys.path.insert(0, sys.argv[1] + '/lib'); import engine_dispatch; sys.stdout.write(engine_dispatch.ANTIHIJACK_PREAMBLE)" "$ROOT_DIR"`.
>
> **Dispatch-runner scope boundary.** The supervised runner supervises **both**
> `dispatch-review` and `dispatch-write`; each is a **distinct subcommand** with its **own** host
> grant string, so write autonomy is revocable on its own. The host
> permission classifier still gates the dispatch **at the Bash call** — absent a matching grant
> nothing spawns and the caller parks loudly. CONVENTIONS `§7.5` holds: engine **selection** fails
> open when a seat is unavailable, a completed external **result** fails closed. It does not forbid
> supervising the write path.

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

## Applying the fixes

When `next` returns `apply-fixes`, the build session fixes the batch itself, in its own working tree, as it fulfils `run-verify`. No fixer agent, fix order, order file, envelope stub, orders manifest, order lint or locked-down sandbox takes part. The payload's keys and the driver's checks are in `round-driver.md` § The `apply-fixes` step.

**What the session does.**

1. Read the batch at `fixBatchPath` and, when `guidancePath` is not `null`, the guidance at `guidancePath`. For each finding, apply a fix in the working tree. The fix follows `CLAUDE.md` and the project profile; guidance for a finding wins over its suggestion.
2. A finding whose `suggestion` is a `break-it-test v1` block carries a test. Write that file at the block's `path`, byte for byte, keep it, and commit it **in the same commit as the fix**. Never edit or weaken the test to make it pass, and never run a formatter or autofix over it. Findings that share a fix group (the batch's `fixGroup` stamps list the members) get one fix: make one commit that holds every test-carrying member's test, each at its own path, and a change beside all of those tests, and bind each member that you fixed to it.
3. Run the scoped checks for what you changed: the tests that reference the changed files plus the project's static validators, at most once each. Never run the project's full verify command; the driver's `run-verify` gate runs it once after the fixes. Never commit code that fails them: fix the failure, or list the finding `unfixed` with the failing output as `why`.
4. A finding that needs a judgment call you cannot make (several valid approaches, unclear intent) is not guessed at: list it `unfixed` with `why`.
5. A finding about the PR body is fixed by editing the staged PR body at `prBodyPath`; that file is never committed. With no `prBodyPath`, list such a finding `unfixed`.
6. Never push, merge or write to GitHub.
7. When a run needs a throwaway test file, choose a path inside the working tree named with the prefix `autofix-probe-`, check on the filesystem (not with git) that the path does not exist, and delete only that file before you commit. If you cannot show the path is new, do not write there; report it instead. A probe file must never land in a fix commit.

**A restore-only step.** When the payload carries `restoreOnly: true`, the fix auditor found a break-it test missing, changed without a reason or weakened, and the step puts the test role's version back. It carries `restores` and no batch. Write each `restores` entry's `content` at its `path`, byte for byte, and commit; a commit that carries only those files is right here. Make no other change, fix nothing, edit nothing to make a test pass, and run no formatter or autofix over the files. Submit `{"fixes": []}`; the report takes no `unfixed` entry and no `{finding, commit}` binding, and the driver reads the commit from git. A second restore-only step may follow when the test role corrects its test: it is the same step, with the corrected `content`.

**The report** is a JSON object. `fixes` is required and is a list; `unfixed` and `coverageDecisions` are optional lists:

```json
{
  "fixes": [{"finding": "<the finding's key or staged id>", "commit": "<full sha>"}],
  "unfixed": [{"finding": "<key or staged id>", "why": "<why it was not fixed>"}],
  "coverageDecisions": []
}
```

- `fixes` — an entry binds a finding to the commit that fixed it. The binding is **required** for every finding that carries a break-it test; other entries may be plain notes. A commit may fix several findings, and the fixed members of one fix group are bound to the same commit. An object entry with a `finding` key or a `commit` key must give both as non-empty strings.
- `unfixed` — `{finding, why}`, both non-empty strings, for a finding you could not fix. It is not credited as fixed, and the next audit judges it.
- `headDiff` / `headDiffPath` are optional cross-checks, as in `round-driver.md`.

Fold it on the path the session already uses, as for every other phase: a hand `submit` on a hand-path session, or writing it to the payload's `landingPath` and calling `advance` on a durable-record session. A session that has used one path refuses the other (`advance-submit-interleaved`).

**Refusals.** The driver derives what was committed from git, never from the report. A refusal leaves the step pending, with the same phase and attempt: fix what it names, then fold again.

| Refusal | What to do |
| --- | --- |
| a reason that names a field, for example `` `fixes` is missing `` (a hand `submit` only; the driver journals `apply-fixes-shape`) | The report's shape is wrong. Correct the field it names and submit again. |
| `fold-refused`, detail `fix-without-break-it-test:<finding key>:no-binding` | Add a `fixes` entry binding that finding to its commit, or list it `unfixed`. |
| `…:commit-unknown` or `…:commit-not-in-step` | Bind the full sha of a commit made at this step: known to git and reachable from HEAD, not reachable from `startHead`. |
| `…:test-missing` or `…:test-bytes-differ` | Write the test at the block's `path` with the block's bytes, and commit it with the fix. Do not edit the test to match the code. |
| `…:no-fix-change` | The commit changed only the test. Commit the fix itself with it. |
| `…:unverifiable` | The driver could not read git: the session has no repository root, base reference or step start head. Fold from a session that runs in the repository. |
| `fix-group-split:<group id>` | Some members of the fix group are listed `unfixed` and others are not. Fix all of them in one commit, or list all of them `unfixed`. |
| `fix-group-no-shared-commit:<group id>` | No single bound commit passes every member's test check, or the commit changes only the members' tests. Bind every fixed member to one commit that holds all their tests and a change beside them. |
| `fix-binding-malformed:<index>` | The `fixes` entry at that position (from 0) has a `finding` or a `commit` key without both being non-empty strings. Give both as non-empty strings, or drop the key to make it a note. |
| `fix-finding-unknown:<value>` | A `fixes` binding names a finding outside the batch. Remove or correct it. |
| `unfixed-finding-unknown:<value>` | An `unfixed` entry names a finding outside the batch. Remove or correct it. |
| `finding-id-ambiguous:<value>` | A `fixes` or `unfixed` entry names a staged id that two findings of the batch share (staged ids restart in each verifier wave). Give the full finding key instead. |

A step with no commit at all is not a refusal, and a PR-body-only fix makes none.

**Size.** The session's own fix commits are counted like any commit it makes: the builder recounts the non-test lines after each fix round (the size rule's count, `python3 -B <plugin root>/lib/size_count.py count --base <build base>`) and reports a crossing of the size rule's lines. The rule is in [review-discipline § Size](../../../rubric/review-discipline.md#size).

### A ruling that arrives during a fix

A ruling (`rule`, see `round-driver.md` § Owner and advisor rulings) is accepted whenever it arrives.
One accepted while `apply-fixes` is pending rewrites that step's batch and guidance files, and the
next `next` returns the current direction. One recorded after the session folded the step reaches the
next round: it binds the next fix of its finding, and when that fix went against it the next round
sends the finding back. No finding below blocking joins a fix batch unless a ruling names it; those
settle when the loop converges.

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
| Tiering or skipping specialists based on "what changed" | Round 1 is the full panel, except a returning PR's round 1, which `round_driver.py` `next` runs as a returning round when the returning-review decider answers `changed`; later rounds follow `round_driver.py` `next` (delta audits + scoped finder only; an unknown fix surface hands the PR back). Never skip by eye. |
| **Continuing when `$BASE_REF` is not a commit**         | An empty `$BASE_REF` makes `git diff "$BASE_REF"...HEAD` argv `...HEAD` — git reads it as `HEAD...HEAD` and emits a **zero-line diff at exit 0**, so the panel reviews nothing and the loop certifies clean. The literal string `null` (what `jq -r` prints for an absent key) is non-empty, so a `[ -n … ]` test passes it while `git diff null...HEAD` exits 128 and still leaves an empty artifact. Setup validates with `git rev-parse --verify --quiet "$BASE_REF^{commit}"` — which rejects empty, `null`, a deleted branch, and a non-commit tag — and every consumer uses the guarded diff command that halts on a failed OR empty diff. Never substitute a branch name to "recover". |
| **Diffing against the worktree's local base branch**    | A long-lived worktree's local `main` goes stale as a matter of course; three-dot diff then walks back to a stale merge-base and drags already-merged work into the review, burying the real change. The bootstrap fetches the base and pins it to a commit; never re-resolve the base from a branch name mid-run. |
| Using `gh pr diff` inside the loop                      | Rounds 2+ have local fix commits not on the remote. Always recompute the diff locally each round **with the guarded per-round command from the SKILL's Setup** — `git diff "$BASE_REF"...HEAD` against the **pinned remote base commit**, including its failed-diff and empty-diff halts — never a branch name and never a bare copy.                                               |
| Auto-fixing a PR you don't have checked out             | Auto-fix needs the PR's branch as the current branch **or** an adopted build (tracks remote `origin` with merge ref `refs/heads/<PR branch>` **and** `HEAD` == the PR's `headRefOid`); anything else — detached HEAD, an unrelated branch, a stale adopted branch — stops: reviewing a PR that was not built in this project is not supported.                                        |
| Re-reviewing on a broken tree                           | If `VERIFY_CMD` fails after a fix, HALT. Never run the next review round on code that doesn't pass verification. |
| Re-raising a finding the user skipped                   | Skipped identities go in the skip-set and are excluded from every later round's effective findings AND the circuit breaker.                                        |
| Eyeballing "are we stuck?" by hand                      | The audit-keyed stall breaker lives in `round_driver.py` — never call `circuit_breaker.py` inside the auto-fix loop.                                                 |
| Exiting the loop early because a fix "looks done"       | Obey `round_driver.py` `next`/`submit` — never `code_loop_plan` or manual continuation. "Trivial fix / save tokens / offer optional round" are the rationalizations it overrides. |
| Pushing automatically at loop end                       | The loop commits locally only. Pushing is always a separate, user-confirmed step.                                                                                 |
| Dispatching reviewers by reading an agent file          | The five reviewers are bundled plugin agents — dispatch the `<name>` reviewer with its methodology (resolve dispatch via the host tool map (`hosts/<host>-tools.md` at the plugin root)).                  |
| Skipping the profile bootstrap                           | If `.claude/review-profile.md` is absent, run review-init's create procedure inline first. When no profile resolves, every run gets a provisional strict profile. |

---

## Break-it tests

On a full panel, the build session runs each break-it test the test role wrote once, exactly as written, on the unfixed code, before the verifiers grade (`lib/break_it.py`). The run is in the session's own working copy, the repository root the review runs in, and its temporary files go to the session folder. There is no copy and no linked dependency folder: an `npm test` or `npx` break-it test resolves the project's dependencies from the working copy's own installed `node_modules`, used as it is. The command and output are recorded under the test role's name in the round record's `breakItRuns`, on the finding as its `breakItRun` stamp, and in the review record's `breakItRuns` part. The working copy is left as it was: the written test file is removed; HEAD and the branch it points at, the index, the local config, tracked files and new untracked files are restored; any other ref the run's time window saw change is left as it is, because another worktree of the same repository may have changed it, and the run record names each one in `refsLeft`. A run on a working copy that is not at the reviewed head, or has a modified tracked file, is recorded not-run (`working-copy-not-at-head`, `working-copy-dirty`). A restore that fails is recorded not-run (`working-copy-restore-failed`), and the review cannot certify over it. A run with dependencies declared but none installed is recorded not-run (`module-not-found`). A test whose text carries a transit redaction placeholder (a bracketed `[REDACTED…]`) is recorded not-run (`transit-redacted`) and never executed; the review record shows it as `not run: transit-redacted`.

The run judges nothing. Its output is saved with the finding and handed to the verifier, and a passing run does not drop the finding. A test that passes, fails or could not run stays a finding.

Break-it tests are of two kinds, and only the test role writes either. An attached test rides on a finding of any taxonomy that the test role can prove that way: the finding keeps its own taxonomy, `file:line` and scope, and its `suggestion` is a `break-it-test v1` block. An attached test is run, recorded, kept and checked like any other, and has no cap. A per-area test is its own finding (`taxonomy: break-it-test`); the cap of three per review counts only these. The build session never writes a break-it test. Its one edit to a reviewer's test is the small change: after the panel folds and before it dispatches the verifiers, for a run whose output shows the test itself failed to compile, parse or type-check, the session changes the test through `break-it-change` ([round-driver.md](round-driver.md#break-it-change)) and says why. The verb rewrites the finding's `suggestion` block with the changed content, so the changed test is the one the build session writes and commits at `apply-fixes` and the kept check reads. The changed test runs again in the working copy, both runs are recorded with the finding (the second carries the reason in `changedWhy`), and the review goes on to the verifier. A run that fails for any other reason is not changed.

A run whose command exits 127 or whose output reports a missing command or module is recorded not-run (`command-not-found` / `module-not-found`), never failed or passed, even when the signature was printed early in a long output. The build session keeps the test in the change, in the same commit as the fix (for a fix group, the group's one shared commit), and the driver checks that at the `apply-fixes` fold (§ Applying the fixes). Before the loop certifies `converged`, it checks that each fixed break-it finding's test counts as kept and that it passes there (`breakItKept`); otherwise it parks with certification withheld. A break-it finding that the owner or advisor ruled out of scope through the `rule` verb, with who ruled and when, and that a round's audit then cleared (`discharged` or `discharged-but-new-issue`) is not required to be kept: its `breakItKept` row reads `ruled-out-of-scope` and the review record lists it as "ruled out of scope", while a ruling alone, a clearing audit alone, or an unattributed ruling still requires the test kept. The body match applies to break-it tests in these languages: Python, JavaScript and TypeScript. Such a test counts as kept when its fixture and assertions appear unchanged in a file the final diff carries, at its own path or any other, with formatting and the test's title free to differ and anything the check cannot compare read as not kept. A test in any other language must still be byte-identical at its own path. The test role never writes its test into the repository; it delivers each one in a finding. Which Python a break-it test runs under depends on one optional core.md calibration key, `breakItInterpreter`, a launcher command such as `scripts/pinned-python` or `uv run python`. When the key is set, a test whose program is `python` or `python3` runs as `<launcher> <args>`, and one whose program is `pytest` or `py.test` runs as `<launcher> -m pytest <args>`; any other program runs as written, and the verify command is not consulted. The launcher must pass a readiness probe, a one-line Python program, or the test is recorded not-run (`interpreter-unavailable`), never a failed test. A set value that is not a usable launcher records Python and pytest tests not-run (`interpreter-key-invalid`); it never falls back to the verify command. When the key is not set, the launcher is read from the verify command's text, and Python tests are recorded not-run (`interpreter-unresolved`) when none is found. A project whose verify command is `pytest -q`, `uv run pytest`, `make test`, `tox` or `poetry run pytest` names no launcher the driver can read, so it should set the key; otherwise its Python break-it tests do not run, and a review that fixes a break-it finding parks with certification withheld. `/superheroes:configure` sets it (view-and-tune's "Name the Python launcher for break-it tests").

---

## Per-seat dispatch + the seat map

The round-1 panel composes over live vendors via a per-seat **seat map** (`lib/seat_map.py`,
computed once in the SKILL as `$SEAT_MAP`). Each of the five lens seats carries `{vendor, model, effort, tier, family, source}`:

- **Read the seat's assignment** from `$SEAT_MAP.seats[<reviewer-name>]`. Dispatch a `claude`
  seat as the named subagent with `model: <seat>.model`; dispatch a `codex`/`cursor` seat through
  `engine_adapter.py` (read-only sandbox), building a four-key `--seat` JSON from the entry —
  `vendor`, `model`, and `effort` carry over, and `role` is the entry's `tier` — leaving `family`
  and `source` as the driver bookkeeping that never travels in the seat — never
  the hard-coded composer default. The seat's **registry id** rides in `model`; its **effort** in
  `effort`. `build-argv` also accepts the **composed dispatch token** in `model`, and resolves it
  identically, but an `effort` that **contradicts** a composed token is refused rather than
  silently resolved either way. A refused dispatch surfaces
  `detail: "engine-config:<reason>"` (see the engine-config refusal tokens section of
  `skills/workhorse/reference/dispatch-entry.md`) — so the panel's
  degradation disclosure names **what** died. The persona and `$RUBRIC` are identical across engines; the only per-seat difference is
  the dispatch target.
- **Independence keys on model family, not the dispatch CLI** (CONVENTIONS §7.5), and **cursor's
  first-party models are ONE family**: the token-efficient implementer and grok judge models both
  carry the `xai` independence-accounting key. A `cursor` review seat is therefore NOT independent of a
  cursor/composer implementer — a composer-made diff stamps `authorFamily = xai`, so the seat map
  excludes the maker family from **rotation** onto every panel seat — all five lens seats
  (`architecture-reviewer`, `code-reviewer`, `security-reviewer`, `test-role`,
  `premortem-reviewer`), not
  merely from strong-tier and critical. The makers are the author family plus every
  extra maker family passed to compose with `--maker-family`. A seat with no live candidate outside
  the makers' families is recorded **`unfilled`** (`vendor`, `model`, `effort` and `family` all null,
  `source: "unfilled"`) with a `seat-unfilled` degradation naming the seat: it is never filled with a
  maker family and never backfilled, so no panel is ever composed from the maker's own family. An
  owner pin to a maker's family does not seat it either; that seat is left `unfilled` and recorded
  as `pin-breaks-constraint`. An `unfilled` seat is a planned reviewer that did not run: it is
  never dispatched and stays in the record. `verify()` treats it as a known not-run seat, not as a
  missing, malformed or maker-family seat, and unusable liveness evidence still fails closed to a
  violation for any seat that does name a maker family. Every degradation / unhonorable-pin fallback is recorded in the
  seat-map receipt, so a downgraded composition is visible at vet time, never silent.
