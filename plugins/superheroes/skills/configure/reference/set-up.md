## Contents

- §1 — Decide the storage mode, with disclosure
- §2 — Seed the core + the light hero layers
- §3 — Verify command first
- §3.5 — Who it's for, and Risk and trust — one sitting
- §3.6 — Record that item 13 lives in Canon
- §4 — Optional heavier heroes — provisional defaults disclose
- §4.4 — Show-it surface — provisional default
- §4.5 — Engine preferences — per-role defaults
- §4.6 — Project-configuration dependencies and kind labels
- §4.7 — Review-discipline CLAUDE.md — offer recorded, not written unasked
- §4.8 — Sandbox access for the claude implementer — all off by default
- §4.9 — Size count exclusions — none by default
- §5 — Secrets stay out of shared calibration (NFR)
- §6 — Cloud builds: the setup sitting
- Recovering an interrupted set-up

# configure — set-up path

Reached from `configure` when a project has nothing configured yet. Sets the project up
end to end: storage mode, the shared core, the light hero layers, and named provisional defaults
for optional heroes. Set-up takes declared defaults and discloses them in the layer carriers — it
does not interview.

`ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"` is assigned once per bash block below.

## 1 — Decide the storage mode, with disclosure

A project keeps its calibration either **repo-shared** (committed with the repo, **visible to
collaborators**) or **out-of-repo** (kept on the local machine, the repo stays pristine). Present
both with that consequence **before** recording the mode — repo-shared publishes the calibration to
anyone with the repo. Resolve the band-wide decision (it is decided once and is sticky):

<!-- decision-point: id=configure-setup-storage-location mode=notify kind=storage-location default="recorded mode when one exists, else provisional global (out-of-repo)" carrier=review-crew-layer -->

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
DEC=$(python3 -B "$ROOT_DIR/lib/review_store.py" decide-location) || { echo "decide-location exited non-zero; halting rather than taking an undisclosed storage default" >&2; exit 1; }
LOC=$(printf '%s' "$DEC" | jq -r '.mode')
SOURCE=$(printf '%s' "$DEC" | jq -r '.source')
PROVISIONAL=$(printf '%s' "$DEC" | jq -r '.provisional')
[ -n "$LOC" ] && [ -n "$PROVISIONAL" ] && [ -n "$SOURCE" ] || { echo "decide-location returned no usable decision; halting" >&2; exit 1; }
```

**Default:** recorded mode when one exists, else provisional `global` (out-of-repo). An
already-decided mode is reported, not re-asked. **Disclosure:** when `$PROVISIONAL` is `true`, state
in the set-up output which storage mode was taken, that it is provisional, and that
`/superheroes:configure` changes it. **Follow-up:** the owner changes storage mode via
`/superheroes:configure` (view-and-tune §3 for a flip after set-up).

NOTIFY: take the returned `.mode` from `decide-location`, record mode/source/provisional status in
the set-up output and carry it into the hero's `## Setup disclosures` section per the §2 carrier
note, disclose in set-up output when provisional, and the run continues. Follow-up:
`/superheroes:configure`.

<!-- /decision-point: id=configure-setup-storage-location -->

## 2 — Seed the core + the light hero layers

Once the mode is set, seed the shared **core** (the project's stack, verify command, threat model)
and the two light layers — the-architect's doc-policy and review-crew's threat model — in the same
pass. Drive each hero's calibration logic through its now-internal `*-init` skill (reached from
here, not advertised separately). Detect facts from the repo; do not ask. Write the core
**provisional**, stating which fields were defaulted rather than answered; the owner confirms via
the owner-confirm step on the fix path.

Set-up's decisions are disclosed in the **set-up output** — this path's own report to the owner.
Each hero's `## Setup disclosures` section is **assembled and written by that hero's `*-init`
skill**, which this path drives; set-up hands its defaults to those skills, it does not write hero
layers itself. Review-crew disclosures are written in `review-init` Step 4b; test-pilot disclosures
in `test-pilot-init` Step 6.

## 3 — Verify command first

The verify command is the project's **fast iteration check**: for example lint, types, and the tests
the change touched. It is not the project's full gate. A build re-runs it after every review fix
round and on the final head, so a project whose verify command is its full gate pays that cost every
time. Workhorse §8 says when the full gate runs.

<!-- decision-point: id=configure-setup-verify-command mode=notify kind=ask-user-question default="mode: review-only when no verify command is detectable" carrier=review-crew-layer -->

When no verify command is detectable, take the provisional default **`mode: review-only`** (matching
`review-init`'s default for the same field) — **never edit the owner's build config yourself** and
never guess a command. NOTIFY: record `mode: review-only` in the core facts and disclose it in
the set-up output and carry it into the hero's `## Setup disclosures` section per the §2 carrier
note, and the run continues. The owner may set a real
verify command via `/superheroes:configure`.

<!-- /decision-point: id=configure-setup-verify-command -->

Set-up does not write `breakItInterpreter`. When the verify command names no Python launcher (for
example `pytest -q`, `make test` or `tox`), state in the set-up output that break-it Python tests
will not run until that key is set. Name `scripts/pinned-python` when that file is present. Point to
view-and-tune's "Name the Python launcher for break-it tests"
(`skills/configure/reference/view-and-tune.md` § 2). Set-up detects and discloses this only; it
never prompts for the value.

## 3.5 — Who it's for, and Risk and trust — one sitting

This step is asked, not detected. The advisor leads this sitting with the owner, in product terms:
no path patterns and no JSON in what it asks or reads back. The same sitting runs here at a new
project's set-up and, for a project that is already configured, from view-and-tune's "Set up Risk
and trust" action (`view-and-tune.md` § 2).

**First, who it's for.** Read item 14:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/project_config.py" get --item whoItsFor --cwd .
```

If it is set, do not ask it again. Offer to read it back: "Who this project is for is already
recorded. Want me to read it back before the risk questions?" Read it if the owner says yes, change
it only if the owner asks, and move on to the risk questions.

If it is not set, ask the owner, in these words: **"Who is this project for, and what is it for? A
few plain sentences: the people it serves, and what it lets them do."**

Record the answer as configuration item 14 through `project_config`:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/project_config.py" set --item whoItsFor --cwd . <<'SUPERHEROES_ANSWER'
<the answer as a one-line JSON string>
SUPERHEROES_ANSWER
```

The answer is the owner's own free text, so it goes in through a quoted here-document, never inside
shell single quotes: an apostrophe in the answer would break a single-quoted argument, and a
`$(...)` in it would run. Write it as one line of JSON, with its quotes and backslashes escaped.

Read the result as the other `set` calls are read: only `written` or `noop` means the answer was
saved. If the owner would rather not answer now, leave item 14 unset, say so in the set-up output,
and go on. The configure view shows item 14 as unset until it is set.

**Then the risk questions,** one at a time, in this order:

1. Where do money, customer data, access and irreversible actions live in the product?
2. Which outcomes are unacceptable?
3. How quickly can a bad change be undone?
4. What can be run to try the product?

**What the answers become.** The advisor turns the answers to the first three questions into
**risk areas**. For each part the owner names, the advisor finds the code that implements it and
writes the area's `covers` patterns itself (a pattern is a repo-relative path or glob; a pattern that
names a folder covers every file beneath that folder, and `*` also crosses `/`), takes `why` from the
unacceptable outcomes, and takes `undo` from the answer on undoing. A part where a mistake costs
money, customer data, safety, access, or something that cannot be undone can each be its own area. Before writing, the advisor
reads the areas back in product terms: the name, what it covers in the owner's words, why it is
risky, and how hard a mistake there is to undo. It writes them only on the owner's yes, with the
whole list in one call, through a quoted here-document as for item 14:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/project_config.py" set --item riskAndTrust --cwd . <<'SUPERHEROES_ANSWER'
{"riskAreas": [{"name": "<area name>", "covers": ["<repo-relative path pattern>"], "why": "<why a mistake costs>", "undo": "<how hard a mistake is to undo>"}]}
SUPERHEROES_ANSWER
```

An unacceptable outcome that belongs to no part of the code is offered to the owner as an addition
to the threat model (shown as "What we defend against"). The existing threat-model text is never
rewritten without the owner's yes. A change is written the same way, with the other half:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/project_config.py" set --item riskAndTrust --cwd . <<'SUPERHEROES_ANSWER'
{"threatModel": "<the threat model as prose>"}
SUPERHEROES_ANSWER
```

Each call sets one half, and setting `riskAreas` replaces the whole list. Read the result as the
other `set` calls are read: only `written` or `noop` means it was saved. Anything else is reported
to the owner with its `reason` and never worked around.

**The coverage check.** After a `written` or `noop` answer, the advisor runs the reader over the
project's tracked files:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
git -C "$(git rev-parse --show-toplevel)" ls-files -z | python3 -B "$ROOT_DIR/lib/risk_areas.py" touched --cwd . --paths-file - --nul
```

and checks that every area in `areas` appears in `touched`. An area that matched nothing is read
back to the owner in product terms ("Payments covers no file in the project today"), and the
advisor corrects its `covers` with the owner and writes the whole list again before finishing. An
area may legitimately cover files that do not exist yet; keeping it as it is, is the owner's call,
and the advisor says so in the set-up output. No write is refused for covering nothing.

The listing starts from the repository root, so a sitting opened inside a package folder still sees
every tracked file under its repository-relative path, and `-z` hands the names over unquoted, so a
file name with accented or non-English characters matches its area like any other.

The answer to the fourth question is checked against what the project's calibration already
records: the verify command, and test-pilot's profile when test-pilot is set up. A gap is offered to
the owner through that setting's own configure path. Nothing about it is stored in Risk and trust.

If the owner would rather not answer the risk questions now, leave the risk areas unset and say so in
the set-up output. Until risk areas are set, the review treats them as not set.

Keep this one sitting. Ask any other question about who the project serves or what it is for here,
together with these, and not in a later step.

## 3.6 — Record that item 13 lives in Canon

Runs at set-up only, after § 3.5. View-and-tune's "Set up Risk and trust" action runs § 3.5 and
never this step.

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/project_config.py" migrate-material-line --cwd .
```

Read the result's `action`. On a project with no item-13 value, the command moves nothing and only
marks item 13 as pointing to the project's Canon standing rulings
([Canon's contract](../../../rubric/canon-contract.md)). A project that already has a value has it
moved into Canon as standing rulings (view-and-tune § 2, "Move item 13 into Canon"). Report a
`refused` result to the owner with its `reason`, and never work around it. Only `migrated` and
`already-adopted` mean item 13 is in Canon.

## 4 — Optional heavier heroes — provisional defaults disclose

<!-- decision-point: id=configure-setup-optional-heroes mode=notify kind=ask-user-question default="do not set up optional heroes" carrier=review-crew-layer -->

Where a heavier or optional hero applies (**test-pilot**, **guardian**, or any hero needing extra
tooling such as a connected browser), the default is to **leave it un-set-up** and disclose that
optional heroes were skipped and that `/superheroes:configure` can add them. NOTIFY: record the
skipped heroes in the set-up output and carry them into the hero's `## Setup disclosures` section
per the §2 carrier note and the run continues.
Set-up still **completes** and the project is usable without them.

<!-- /decision-point: id=configure-setup-optional-heroes -->

<!-- decision-point: id=configure-setup-browser-tool-gap mode=notify kind=ask-user-question default="record the browser-tool gap; do not guide" carrier=run-output -->

When test-pilot would apply but no browser tool is connected, NOTIFY: record the browser-tool gap
in the set-up output and the run continues — do not guide the owner
to connect one and do not block set-up. Follow-up: `/superheroes:configure`.

<!-- /decision-point: id=configure-setup-browser-tool-gap -->

<!-- decision-point: id=configure-setup-guardian-tuning mode=notify kind=ask-user-question default="guardian tuning off — sweeps on plugin defaults" carrier=review-crew-layer -->

**Guardian** works with zero configuration on plugin defaults — sweeps run even when the owner
skips tuning. The default is **off**: do not offer guardian threshold/cadence tuning during
set-up; disclose that guardian runs on defaults and that `/superheroes:configure` can tune it.
`guardian.md` is a thin adder for those deviations (empty is valid). The `guardian-config` fence
shape is in `skills/guardian/reference/calibration.md`. NOTIFY: record guardian-left-on-defaults in
the set-up output and carry it into the hero's `## Setup disclosures` section per the §2 carrier
note and the run continues.

<!-- /decision-point: id=configure-setup-guardian-tuning -->

<!-- decision-point: id=configure-setup-hero-decline mode=proceed kind=owner-gate default="optional heroes not set up — not recorded as declined" carrier=review-crew-layer -->

Absent explicit decline language in the owner's **current-turn words**, the default is that optional
heroes are simply **not set up** — that is **not** the same as declined; do **not** call
`hero_setup.py decline`. PROCEED: record the not-set-up posture in `## Setup disclosures` and
continue. Only when the owner explicitly declines an optional hero in this turn, record it so the
view tune-menu does not re-offer it on every run:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/hero_setup.py" decline --cwd . --hero test-pilot
# or, for guardian:
python3 -B "$ROOT_DIR/lib/hero_setup.py" decline --cwd . --hero guardian
```

Follow-up: `/superheroes:configure` can still set up a hero later unless it was explicitly
declined.

<!-- /decision-point: id=configure-setup-hero-decline -->

When test-pilot calibration is written and the profile declares a `pilot` block,
run the headless conformance pass before set-up completes (normative CLI in
`reference/pilot-contract.md` §The conformance run):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
REPORT_JSON="$(mktemp)"
trap 'rm -f "$REPORT_JSON"' EXIT
CONFORMANCE_ARGS=(run --cwd .)
if [ -n "${PILOT_REGISTRY:-}" ]; then
  CONFORMANCE_ARGS+=(--registry-path "$PILOT_REGISTRY")
fi
python3 -B "$ROOT_DIR/lib/pilot_conformance.py" "${CONFORMANCE_ARGS[@]}" > "$REPORT_JSON"
python3 -B "$ROOT_DIR/lib/pilot_acceptance.py" matrix \
  --report-path "$REPORT_JSON" \
  --project "$(basename "$(pwd)")" \
  --commit "$(git rev-parse HEAD)" \
  --format markdown
```

When the project maintains a declare-and-exercise registry (see
`reference/pilot-contract.md` §Declare and exercise), set `PILOT_REGISTRY` to
that JSON path before running the conformance step so `--registry-path` is passed
and the report carries a `declarations` envelope. **Without a registry path** the
conformance report's `declarations` key is `null` — the matrix CLI still
renders, but declaration-backed rows read `unexercised` with a stated reason;
that is the ordinary adopter case, not a refusal.

Stdout is the report JSON from the conformance run; the matrix step prints
markdown on stdout. Stderr carries diagnostics. **Exit 1 is a real outcome to
report, not an error to swallow** — show which surfaces are `unexercised` and
why, from the report's `resolution` list. The matrix's `ok` is **false** when
any row is `unexercised`, when the reference worktree is dirty, or when the
run itself left surfaces `unexercised` — that is the honest outcome for a
project that has not exercised everything, **not a failure to work around**.
`--commit` must be a **full object id** (run `git rev-parse HEAD` in the
reference project — not a branch name). **Dirty** is derived from
`git status --porcelain` in the **CLI process's current working directory** when
neither `--dirty` nor `--clean` is passed; pass `--dirty` or `--clean` to
override. The run **never** writes into the repository when `--allow-live-effects` is not passed. The `cleanup-end-to-end`,
`mint-gate-off`, and `ownership-probe` exercises are reported as
**unexercised** unless the operator explicitly passes `--allow-live-effects`;
opting in runs the project's own destructive cleanup, gate-off, and
ownership-probe commands against live datastore and checkout resources. A
`mint-gate-off` exercise that does not produce a usable receipt is reported as
**unexercised**, never recorded as exercised — configure refuses to claim it.
The matrix is **generated, not stored** by the plugin — where a project keeps
it is the project's own decision.

## 4.4 — Show-it surface — provisional default

<!-- decision-point: id=configure-setup-show-it mode=notify kind=ask-user-question default="honest evidenced level, or none when nothing is detectable" carrier=review-crew-layer -->

Record **where the owner goes to look at a finished change** — the entry point a **show it** PR's
*How to see it* section points at. The declaration lives as prose under `## Show-it surface` in
`core.md`; it holds the **shape** (command pattern or URL form), not the per-branch instance the PR
carries. **Absent means `none`** — no level is claimed for the project. Ranked levels and the
disclosure rule (`link` > `running` > `command` > `attended` > `none`; take the highest the project
supports; disclose at `command` or below) are defined in `rubric/review-discipline.md` — cite that
doc rather than restating the table here.

The default is the honest level the repo evidences, or **`none`** when nothing is detectable —
disclose any degradation per the show-it contract. NOTIFY: record the level in the set-up output and
carry it into the hero's `## Setup disclosures` section per the §2 carrier note and the run
continues. Set-up still **completes**; the owner may change
the declaration via `/superheroes:configure`.

To persist a declaration when the owner supplies one in this turn (multi-line prose on stdin):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
printf '%s\n' '<Level/What-the-owner-does/Notes prose>' | \
  python3 -B "$ROOT_DIR/lib/core_md.py" write-show-it --cwd .
```

**Read the result, don't assume success.** `write-show-it` returns `{action, reason?}`.
Only `written` or `noop` means the Show-it declaration was saved — surface any other
`action` (`refused`, `deferred`, `behind`) to the owner with its `reason`; the command
exits 0 either way, so check `action`, not exit status.

An empty stdin body clears the section and returns the project to `none`.

<!-- /decision-point: id=configure-setup-show-it -->

## 4.5 — Engine preferences — per-role defaults

<!-- decision-point: id=configure-setup-engine-preferences mode=notify kind=interview-step default="reviewer/implementer/pilot claude; briefCheck codex" carrier=review-crew-layer -->

After the verify command (§3) is set — external implementers are verify-gated, so this must follow it —
bring **Codex** and/or **Cursor** into the loop per role on the owner's word. The **primary path**
is the named provisional defaults — **reviewer**, **implementer**, and **pilot** → `claude`;
**briefCheck** → `codex` (the cross-vendor default — a brief-check on **the host model** is a disclosed degradation).
NOTIFY:
probe availability, record the per-role defaults (or owner overrides from
this turn) into `enginePreferences` and disclose the picks in the set-up output and carry them
into the hero's `## Setup disclosures` section per the §2 carrier note, and the run continues.
Follow-up: `/superheroes:configure`.

1. **Availability.** Probe both engines and show a readiness matrix — installed + signed in, or
   what to fix:

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
   python3 -B "$ROOT_DIR/lib/engine_detect.py"   # JSON verdict per engine: installed/authed + remediation
   ```
   A not-ready engine is shown with its next-command remediation; it is never offered as ready.

2. **Per-role preference.** Record the provisional defaults (or owner picks from this turn)
   into `core.md`'s machine block
   `enginePreferences: {reviewer, implementation, briefCheck, pilot}` via `core_md` (schemaVersion 2).
   Optionally, `enginePreferences.seatPins` holds a per-review-panel-seat pin map (vendor required; model and effort optional per seat).
   An absent block reads as `claude` for every role **except `briefCheck`, which falls open to
   `codex`** (the cross-vendor default — a brief-check on the host model is a disclosed degradation).
   When Codex is selected and no concrete model pin exists, explain the effective codex defaults.
   Codex tier map: each Claude tier that has a codex peer runs the codex model that `model_registry.codex_peer_for_claude_tier` names (`lib/model_registry.py` is its one source; the configure readout shows the effective model per role), and `fable` has none.
   A Codex pin may name `gpt-6.1-sol` (the default), the pin-only `gpt-5.6-sol` or `gpt-6-sol` (any role with a codex cell, at that role's own effort), or `gpt-6-astra` on `reviewer-deep` only at effort `high`; a pin to the retired `gpt-5.6-terra` is refused (`model-retired`; `model_registry.retired_model_reason` names the text).
   `max` effort is owner opt-in only (never a default).

3. **Show the build authorization — never apply it.** If an external **implementation** engine
   is chosen, an external autonomous write needs a one-time owner grant. Show the exact snippet and where
   it goes; do **not** write it:

   ```bash
   python3 -B "$ROOT_DIR/lib/engine_authz.py" snippet --host claude --engine <codex|cursor>
   # prints the autoMode.allow block + its location (.claude/settings.local.json). SHOW it; never write it.
   ```

4. **Test dispatch, bounded by the stall limit.** Run the test dispatch **only** when
   the owner grants authorization in this turn; when no authorization is present, leave the external
   implementation engine **not-ready**, disclose that in `## Setup disclosures`, and continue — do not
   block set-up:

   ```bash
   python3 -B "$ROOT_DIR/lib/engine_authz.py" test-dispatch --engine <codex|cursor> --cwd .
   # -> {"engine":E,"ok":true}  (ready)
   # -> {"engine":E,"ok":false} (denied or no-response bounded by the stall limit -> falls open to
   #    the host model; tell the owner how to enable, leave the engine not-ready with a retry instruction)
   ```
   For Codex, this probes the codex default model (the registry's opus peer) explicitly as well as
   the host write grant, so a CLI too old for it stays not-ready; the preflight names the upgrade.
   A failed or timed-out test dispatch leaves the engine **not-ready** — builds and mechanical fixes fall
   open to the host model until it works. Never present a not-working engine as ready.

**Set-up posture.** Take the strict/provisional posture: probe and record what is detectable, but
never block and never apply the authorization — leave any external implementation engine not-ready
until the owner grants and tests it via `/superheroes:configure`.

<!-- /decision-point: id=configure-setup-engine-preferences -->

## 4.6 — Project-configuration dependencies and kind labels

At calibration, report the four declared dependencies and ensure the two kind labels exist. Neither
step blocks set-up.

1. **Declared dependencies.** Run the dependency check and write each result into the set-up output.
   Name the fallback for every dependency that is absent. A missing dependency never blocks
   calibration.

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
   python3 -B "$ROOT_DIR/lib/project_config.py" dependencies --cwd .
   ```

   When the project has a dependency to declare, persist it with JSON on stdin:

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
   printf '%s' '"standing-proposals"' | \
     python3 -B "$ROOT_DIR/lib/project_config.py" declare --dependency collector --cwd .
   ```

   An undeclared dependency is not a failure — its fallback applies.

2. **Kind labels.** When `kind:machinery` or `kind:product` is missing on the repository, create
   only the missing labels through `kind_labels`. Report what was created. A label failure
   degrades calibration with a disclosure and never refuses it.

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
   REPO=$(gh repo view --json nameWithOwner --jq .nameWithOwner)
   python3 -B "$ROOT_DIR/lib/kind_labels.py" --repo "$REPO" --apply
   ```

## 4.7 — Review-discipline CLAUDE.md — offer recorded, not written unasked

<!-- decision-point: id=configure-setup-claude-md-section mode=notify kind=ask-user-question default="never write the project CLAUDE.md unasked; record the offer as un-made" carrier=review-crew-layer -->

When the storage mode decided in §1 is **in-repo**, **never write** the project's `CLAUDE.md`
unasked — the band's review-discipline section (source of truth:
`$ROOT_DIR/rubric/review-discipline.md`) is owner-gated. NOTIFY: record the offer as **un-made** in
the set-up output and carry it into the hero's `## Setup disclosures` section per the §2 carrier
note and the run continues. The owner may append it
via `/superheroes:configure` (show the text before writing; idempotent — an existing `Review
discipline` heading means report-and-skip). **Never offer this in out-of-repo mode** — that mode
exists to keep the repo free of superheroes traces; there the SessionStart bootstrap note is the sole
carrier. A skipped offer still completes set-up; it is not persisted as a hero decline, so it
remains available on the view-and-tune menu.

<!-- /decision-point: id=configure-setup-claude-md-section -->

## 4.8 — Sandbox access for the claude implementer — all off by default

Set-up writes nothing for sandbox access. The claude implementer's sandbox is fully offline by
default: no network, no loopback, no extra sockets, and writes confined to the run's roots. When an
order's verification needs one of those, the owner opens it later through the view-and-tune path,
which holds the commands (`skills/configure/reference/view-and-tune.md` § 2).

## 4.9 — Size count exclusions — none by default

Set-up writes nothing for size count exclusions. By default every non-test path counts toward the
size count, and lockfiles are always left out. When a project has generated or vendored paths that
should not count, the owner lists them later through the view-and-tune path, which holds the
commands (`skills/configure/reference/view-and-tune.md` § 2).

## 5 — Secrets stay out of shared calibration (NFR)

Any hero credential (such as test-pilot's sign-in) records **only non-secret references — the names
of environment variables, never their values** — into committed or collaborator-visible
calibration. This is test-pilot's existing rule; preserve it.

## 6 — Cloud builds: the setup sitting

Reached when the owner asks to set up cloud builds, in any configure path. The sitting sets up one
[cloud environment](../../../rubric/glossary.md#cloud-environment) for this project on the launching
Claude account, runs one [check session](../../../rubric/glossary.md#check-session) in it, and
never switches cloud builds on. Every message the owner reads comes from
`lib/cloud_check.py` or `lib/cloud_environment.py`: run the command and say its `message` to the
owner unchanged.

The environment's id comes only from Claude Code's settings, read before and after the owner picks
the environment by name with Claude Code's `/remote-env` picker, or, after the account's first
setup, from its setup record. Never ask the owner to type, copy or paste the id, and never use an id
from anywhere but a `picked` result, a `mismatched` result's `environment`, or a ready setup
record's `environment`.

**When the pick is needed.** Only at the account's first setup, and when the owner moves the account
to another environment. Before step 1, read the account's setup record:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/cloud_setup.py" read --cwd .
```

When it returns `ready: true` and the owner has not said they are moving the account, skip steps 1
and 3 and use the record's `environment` as the id in steps 5 to 8. `compare` matches that id with
reason `recorded` without reading the picker: on a machine where several Claude accounts share one
settings file, the shared pick may name another account's environment. Any other id is refused as
`mismatched` with reason `recorded-differs`, and its `environment` is the recorded one. Otherwise
run every step. When the owner says they are moving the account to another environment, run every
step and add `--moving` to every `compare`, so the new pick decides as at a first setup; the passed
check records the new environment.

1. **Read the current pick.** Before anything else, read what the account's settings hold before
   the owner picks, and keep the result's `environment` (it may be null).

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
   python3 -B "$ROOT_DIR/lib/cloud_environment.py" snapshot --cwd .
   ```

   A refusal means the settings cannot be read: say its `message` and stop.
**The dependency hook offer.** Taken only when item 17 lists commands, and before step 2, because
the choice changes the setup text. Run `offer`, say its `message` to the owner unchanged, and record
the answer:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/cloud_dependency_hook.py" offer --cwd .
```

A refusal means there is nothing to offer: skip the offer. Whatever the owner answers, when the
offer's `inputsSource` is `detected`, first save the offer's `inputs` as item 18 (the JSON list),
and go on only when the result is `written` or `noop`. On yes, item 19 alone would leave the hook
watching nothing; on no, the files would stay out of the setup text's stamp, so a change to one
would never make the cloud check ask for new setup text, as the offer tells the owner it will.
Leave an item 18 the owner already stored as it is.

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/project_config.py" set --item cloudSetupInputs --cwd . <<'SUPERHEROES_ANSWER'
["package-lock.json"]
SUPERHEROES_ANSWER
```

Then write item 19, `true` or `false`:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/project_config.py" set --item cloudDependencyHook --cwd . <<'SUPERHEROES_ANSWER'
true
SUPERHEROES_ANSWER
```

Only `written` or `noop` means it was saved. On `true`, the result's `dependencyHook.changed` names
the two files written. Tell the owner to commit and push them, because a cloud session starts from
the pushed repository. State the cost plainly: the hook runs at every cloud session start (a few
seconds when nothing changed; when an input changed, as long as the setup commands take, up to its
600-second limit), and a failed command prints one line and never stops the session.

**The plugin pin hook.** Offered when the owner wants a plugin release to reach cloud builds without
a paste. It is a committed start-of-session script plus a committed pin file that names one plugin
commit. In a cloud session it installs that commit when the installed plugin is at another one, in
seconds when nothing changed; a failed install prints one line and keeps the installed plugin. Add
it before step 2, because it changes the setup text:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/cloud_plugin_pin.py" write --cwd .
```

Commit and push the files it names before pasting the setup text, because a cloud session starts
from the pushed repository. The setup text then stamps its own install and fetch steps and the
plugin parts a cloud session loads at its start, so write and paste it once after adding the hook.

*When a pin commit is enough, and when a paste is still needed.* After a release, run `write` again
on the owner's machine and commit the new pin; the cloud picks the release up at its next session
start. Paste new setup text only when the cloud check or readiness says the setup text is out of
date. That happens when the release changed a tool or fetch step of the setup text, or the parts of
the plugin a cloud session loads at its start (each skill's frontmatter, the agents, the plugin's
hooks file), and when an out-of-repo calibration or the setup commands changed. A project without
the hook pastes new setup text for every release.

*Several repositories.* Hooks do not run in multi-repository cloud sessions or Projects threads, so
there neither this hook nor the dependency hook runs. The session runs the plugin the setup text
installed, and a cloud builder's intake still refuses a plugin version that does not match the
launching machine's.

2. **Open the sitting.** Run `setup-message` and give the owner its `message`, then its `setupText`
   in one fenced block for them to copy.

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
   python3 -B "$ROOT_DIR/lib/cloud_check.py" setup-message
   ```

   A refusal means the [setup text](../../../rubric/glossary.md#setup-text) cannot be written: say
   the refusal's `message` and stop.
3. **Read the owner's pick.** The first hand step has the owner make the environment and pick it by
   name with `/remote-env`, in Claude Code on the account the builds run on. Ask the owner to tell
   you as soon as the pick is done, before the other steps, then read it, passing the value step 1
   kept (leave `--before` out when that value was null):

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
   python3 -B "$ROOT_DIR/lib/cloud_environment.py" pick --cwd . --before <the value step 1 kept>
   ```

   On `picked`, say its `message` and keep its `environment`: that is the id every later step names.
   On `not-picked` with reason `pick-unchanged`, say its `message`. When the owner says the
   environment shown as picked is this project's, read once more with the value step 1 kept as both
   values, and keep the `environment` it returns:

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
   python3 -B "$ROOT_DIR/lib/cloud_environment.py" pick --cwd . --before <the value step 1 kept> --confirmed <the value step 1 kept>
   ```

   On any other `not-picked`, say its `message`, wait for the owner, and run the first command again.
   On a machine where several Claude accounts share one settings file, read right after the owner says
   the pick is done: another account's pick in between would be read as this one.
4. **Walk the reviewer sign-in, and confirm it is done.** Run `sign-in`. When `signedIn` is false,
   say its `message`, wait for the owner, and run it again until `signedIn` is true; then say its
   `message`, which confirms the sign-in is in place. The sign-in is done once per machine the pass
   command runs on, and it comes before the pass command, which cannot work without it.

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
   python3 -B "$ROOT_DIR/lib/cloud_check.py" sign-in
   ```
5. **Give the pass command, naming the id.** Before giving it, check the id (steps 6 and 7 repeat
   this check). Tell the owner to run it on their own machine. It puts
   the [reviewer pass](../../../rubric/glossary.md#reviewer-pass) block on their clipboard, and they
   paste the block into the environment's variables. Never run it for them, and never ask to see
   what it copied. The owner's terminal does not hold `ROOT_DIR`, so give them the command with
   the plugin root's absolute path written out in the quoted script path.

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
   python3 -B "$ROOT_DIR/lib/cloud_environment.py" compare --environment <id>
   ```

   Go ahead only on `matched`. On `mismatched`, say its `message`, take its `environment` as the
   environment now in use for this step and every later step, and run this check again with it. On
   `unchecked`, say its `message` and stop before this step.

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
   python3 -B "$ROOT_DIR/lib/cloud_pass.py" make --environment <id>
   ```
6. **Run the check when the owner says the steps are done.** Start one check session naming the
   id. Pass `--issue` with an issue number when this seat cannot read the session's log, so the
   session also posts its one result line there as a comment; that comment is public on a public
   repository, and the line holds versions, stamps and a date, never the pass.

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
   python3 -B "$ROOT_DIR/lib/cloud_environment.py" compare --environment <id>
   ```

   Go ahead only on `matched`; `mismatched` and `unchecked` are handled as in step 5. Read the
   account this seat is signed in as, and keep the `account` it returns with the nonce; when it
   returns none, say so and stop before this step.

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
   python3 -B "$ROOT_DIR/lib/cloud_setup.py" account --cwd .
   ```

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
   python3 -B "$ROOT_DIR/lib/cloud_check.py" start --environment <id> [--issue <n>]
   ```

   Keep the `nonce` it returns. A refusal starts nothing: say its `message`.
7. **Read the result and judge it.** Read the session's final message, with the host's run-log
   reader, or the issue comment. Save its full text to a file, without picking a line out of it, and
   run:

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
   python3 -B "$ROOT_DIR/lib/cloud_environment.py" compare --environment <id>
   ```

   Go ahead only on `matched`; `mismatched` and `unchecked` are handled as in step 5. Then read the
   account again, the same way as in step 6. When it is not the account kept from step 6, the check
   ran under another account: say so, judge nothing, and repeat steps 6 and 7 with a new check.

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
   python3 -B "$ROOT_DIR/lib/cloud_setup.py" account --cwd .
   ```

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
   python3 -B "$ROOT_DIR/lib/cloud_check.py" judge --environment <id> --nonce <nonce> --account <the account kept from step 6> --line-file <file>
   ```

   Say judge's `message`. A passed check has written the setup record for this account and changed no
   setting. A failed or unread check leaves its failed-check marker, which pauses cloud launches on
   this account until a check passes; it never changes the cloud-builds setting, and the next passing
   check resumes them with no word from the owner. When `markerWritten` is false the message says the
   account is not paused; relay it as is. Never write the setup record any other way, and never tell the owner a check passed without a
   `passed` result.
8. **"Check again"** repeats steps 6 and 7 with a new check session, naming the environment now in use (the id step 3
   returned or the record's, the one the latest recovery pick returned, or the one the latest
   `mismatched` check returned, whichever came last).
   When the failed part was the environment, run `snapshot` (step 1's command) before relaying the
   failure message, so the baseline is the value as the owner leaves it. When the owner says the
   repair is done, read the pick with both the new baseline and the environment now in use, and use the
   `environment` it returns for steps 5 to 7; it becomes the environment now in use for every later
   retry. A repair that kept the same environment returns that same id.
   Leave `--before` out when the snapshot value was null.

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
   python3 -B "$ROOT_DIR/lib/cloud_environment.py" pick --cwd . --before <the snapshot value> --confirmed <the environment now in use>
   ```

   **"Setup text"** at any time writes new setup text: run
   `setup-text`, and give its `message` and its `setupText` in one fenced block.

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
   python3 -B "$ROOT_DIR/lib/cloud_check.py" setup-text
   ```

The check also asks the cloud session's git for a commit identity. It passes when git, with
guessing turned off (`user.useConfigOnly`), resolves both an author and a committer identity from
any source: the platform's own identity, the `GIT_AUTHOR_*` and `GIT_COMMITTER_*` variables, or git
config. It requires no particular name or email, and its report line says only whether each one
resolved. A cloud session starts with the platform's own identity, which signs its commits, so they
show as Verified on GitHub; that is the default and needs nothing. A project that wants a different
author or committer sets the four variables on the environment, and git reads them ahead of any
config; those commits most likely show as Unverified. A missing identity fails the check before any
build, and its fix line names the four variables with this machine's name and email filled in
("your name" and "your email" when this machine resolves none); that line appears only in the
message on this machine and is never stored. The setup text writes no identity step: `git config`
from inside a cloud session is refused as persistence, and the home folder's git config does not
carry over to later sessions.

The setup text runs the project's own setup commands (item 17) after its other steps, one at a
time, in order, in the project's clone. Each one is logged `setup command <n> ok` or
`setup command <n> FAILED`, and the first failure skips the rest. Changing the list means writing
and pasting new setup text. The stamp also covers the files the commands depend on (item 18), so
changing one, such as a lockfile, makes the check report the setup text out of date; write and paste
new setup text. With the dependency hook on (item 19), the files are not in the stamp, so changing
one needs no new setup text: the hook re-runs the commands at the next cloud session start. The
setup text then records the hook after the commands finish, logging `dependency hook recorded` or
`dependency hook record FAILED`. The hook files must be committed and pushed before the setup text
is pasted: with no script in the clone, or a failed record, the stamp is withheld and the setup
does not finish. When the project's calibration names a Python launcher (`breakItInterpreter`, or
the launcher its verify command runs) and the repository root has a lockfile or `requirements*.txt`,
the setup text then runs that launcher once in the clone, logging one line, `dependency fill ok`,
`dependency fill FAILED` with the exit code, or `dependency fill skipped` when no clone is found,
without failing the setup, so a cloud implementer's offline write sandbox (which runs uv offline
against the same cache) can run the tests on its first dispatch; a project that opens sandbox
network domains must include its package index, and a project with no Python launcher or no
dependency files gets no such step (Node dependencies come from the setup commands, such as
`npm ci`).

A launch that names an id matching no environment lands in the account's default environment
without an error. The check catches this, because the pass block names its environment and the
result line repeats that name.

## Recovering an interrupted set-up

<!-- decision-point: id=configure-setup-recovery mode=notify kind=ask-user-question default="report what is missing; do not offer to finish" carrier=review-crew-layer -->

If `route` reported "incomplete set-up" — the storage mode was recorded but not every light layer
was written (a prior run was interrupted) — do **not** present the project as healthy. NOTIFY:
report what is missing in the set-up output and carry it into the hero's `## Setup disclosures`
section per the §2 carrier note, and the run continues. The owner may finish the remaining layers
via `/superheroes:configure`.

<!-- /decision-point: id=configure-setup-recovery -->
