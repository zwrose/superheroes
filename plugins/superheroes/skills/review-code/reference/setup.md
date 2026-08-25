<!-- setup — review-code -->
## Contents

- Session artifacts
- Setup resolution — run these in order

---

# Setup — review-code

## Session artifacts

| Path                                                | Written by     | Purpose                                                                                     |
| --------------------------------------------------- | -------------- | ------------------------------------------------------------------------------------------- |
| `$SESSION_DIR/meta.json`                            | orchestrator   | Mode, PR number (if any), repo, branch, head SHA, pinned base commit + base branch + fetch state, `repoRoot` (checkout path), verify story, focus notes, `interactive` (this run's resolved `$INTERACTIVE`, boolean)       |
| `$SESSION_DIR/repo/`                                | orchestrator   | `--review-only` PR path only: detached `git worktree` at the PR head SHA                    |
| `$SESSION_DIR/prior-comments.json`                  | orchestrator   | PR-mode only: prior review comments + threads (for author justifications)                   |
| `$SESSION_DIR/round-<N>/diff.txt`                   | orchestrator   | Round `<N>` unified diff (`git diff <pinned baseRef>...HEAD`). **Never read by the main context.** |
| `$SESSION_DIR/round-<N>/findings-architecture.json` | arch agent     | Architecture-reviewer findings array                                                        |
| `$SESSION_DIR/round-<N>/findings-code.json`         | code agent     | Code-reviewer findings array                                                                |
| `$SESSION_DIR/round-<N>/findings-security.json`     | sec agent      | Security-reviewer findings array                                                            |
| `$SESSION_DIR/round-<N>/findings-test.json`         | test agent     | Test-reviewer findings array                                                                |
| `$SESSION_DIR/round-<N>/findings-premortem.json`    | premortem agent | Premortem-reviewer (Failure-Mode) findings array                                            |
| `$SESSION_DIR/round-<N>/compiled.json`              | orchestrator   | Deduplicated, verified findings + summary + verdict (read by `circuit_breaker.py`)          |
| `$SESSION_DIR/round-<N>/triage.json`                | triage agent   | Per-finding `mechanical`/`judgment` classification + POV for every finding (loop only)      |
| `$SESSION_DIR/round-<N>/resolutions.json`           | orchestrator   | User decisions on `present-set` findings (loop only; read by `circuit_breaker.py`)          |
| `$SESSION_DIR/round-<N>/fix-batch.json`             | round driver   | Findings handed to the fixer this round — materialized from loop state before fixer emit (loop only) |
| `$SESSION_DIR/round-1/presentation.md`              | orchestrator   | `--review-only` headless only: the tiered presentation as prose — approved set + undecided `ask-set` |
| `$SESSION_DIR/loop-state.json`                      | round driver   | Auto-fix loop only: driver state (`next`/`submit` protocol)                                 |
| `$SESSION_DIR/driver-journal.jsonl`                 | round driver   | Auto-fix loop only: `scriptRan` journal (one line per `next`/`submit`)                      |
| `$SESSION_DIR/round-receipt.json`                   | round driver   | Auto-fix loop only: terminal receipt (`validate_receipt` shape)                             |

## Setup resolution — run these in order

**Resolve `$INTERACTIVE` first, for the whole run.** Two later steps consume it — `decide-location` (below) and the `--review-only` presentation channel (`SKILL.md` § Read-Only Path) — so it is decided once, here, before anything is dispatched, not re-derived per consumer. Set `INTERACTIVE=true` only when a human is present to answer a question this run; set it to `false` on a headless/non-interactive run (`claude -p`, a spawned subagent, any caller with no one at the other end). **When you cannot tell, set it to `false`** — the consumers fail open in that direction on purpose (a headless-by-mistake run still completes; an interactive-by-mistake headless run stalls on a question nobody sees). It is orchestrator-resolved, not sniffed from a tty: the orchestrator's own calls are never on one.

```bash
INTERACTIVE=false   # ← promote to `true` ONLY on positive evidence that a human is present to answer this run
```

**The literal above is `false` on purpose — it is the fail-closed rung, not a placeholder to copy past.** A block copied verbatim into a headless run then behaves correctly; the same block copied verbatim into an interactive run costs that run its questions (`decide-location` takes the provisional, re-askable `global` instead of asking, and `--review-only` writes prose instead of presenting) and nothing more. The reverse default trades a recoverable annoyance for an unrecoverable stall, which is why it is not the one shipped here.

**Resolve the base rubric path once.** The base rubric is bundled at `$ROOT_DIR/rubric/review-base.md`. Capture the rubric path so it can be embedded — **expanded to an absolute path** — into subagent prompts (subagents may not inherit `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}`):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
RUBRIC="$ROOT_DIR/rubric/review-base.md"   # absolute; embed the expanded value in subagent prompts
```

**Resolve the escalation guard wrapper and repo root once.** Subagents do not inherit `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}` or `$REPO_ROOT`, so compute both absolute values here (in the orchestrator's context, where they expand) for embedding into the fixer prompt's `## Input` block — the same way `RUBRIC`/`PROFILE` are embedded as expanded absolute paths:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
ESC_WRAPPER="$ROOT_DIR/lib/escalation_resolve.py"   # absolute; embed the expanded value in the fixer prompt
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)  # absolute; the canonical safe-capture pattern, anchors the in-repo (dogfood) safety files
```

**Resolve calibration paths.** `calibration_resolve.py` returns `$CORE`, `$LAYER`, `$PROFILE`, `$LOCATION`, `$EXISTS`, `$DECISIONS`. If resolve exits non-zero, halt rather than assuming uncalibrated.

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
CAL=$(python3 -B "$ROOT_DIR/lib/calibration_resolve.py" resolve) || { echo "calibration_resolve resolve exited non-zero (exit $?); halting rather than assuming uncalibrated" >&2; exit 1; }
CORE=$(printf '%s' "$CAL" | jq -r '.dispatch_core // empty')
LAYER=$(printf '%s' "$CAL" | jq -r '.dispatch_layer // empty')
PROFILE="${LAYER:-$(printf '%s' "$CAL" | jq -r '.legacy_path // empty')}"
LOCATION=$(printf '%s' "$CAL" | jq -r .location)
EXISTS=$(printf '%s' "$CAL" | jq -r .exists)
DRES=$(python3 -B "$ROOT_DIR/lib/review_store.py" resolve --kind decisions) \
  || DRES='{"path":null}'
DECISIONS=$(printf '%s' "$DRES" | jq -r '.path // empty')
# FR-7/8: surface the single coalesced storage-mode reconcile nudge (non-blocking, ack-gated).
NUDGE_MSG=$(python3 -B "$ROOT_DIR/lib/mode_reconcile.py" signals 2>/dev/null | jq -r 'if . == null then empty else .message end' 2>/dev/null)
[ -n "$NUDGE_MSG" ] && echo "⚠ storage-mode: $NUDGE_MSG"
```

Also resolve the engine versions the staleness self-check (next) needs — the **plugin version** from `$ROOT_DIR/.claude-plugin/plugin.json` (`version`) and the **rubric-version** from the first line of `$RUBRIC` (`<!-- rubric-version: N -->`):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
PLUGIN_VERSION=$(python3 -B -c "import json,sys;print(json.load(open(sys.argv[1]))['version'])" "$ROOT_DIR/.claude-plugin/plugin.json")
RUBRIC_VERSION=$(sed -n 's/.*rubric-version: *\([0-9][0-9]*\).*/\1/p' "$RUBRIC" | head -1)
```

**Resolve model tiers.** Specialists at `reviewer` (`reviewer-deep` for security/architecture); triage + fixer at `mechanical`:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
MT="$ROOT_DIR/lib/model_tier_resolve.py"   # resolved like $RUBRIC
OV=$(python3 -B "$ROOT_DIR/lib/model_tier_overrides.py" --profile "$PROFILE")  # {role:model} or {}
REVIEWER_MODEL=$(python3 -B "$MT" --role reviewer --overrides "$OV" | jq -r '.model // empty')
DEEP_MODEL=$(python3 -B "$MT" --role reviewer-deep --overrides "$OV" | jq -r '.model // empty')
MECH_MODEL=$(python3 -B "$MT" --role mechanical --overrides "$OV" | jq -r '.model // empty')
SYNTH_MODEL=$(python3 -B "$MT" --role synthesis --overrides "$OV" | jq -r '.model // empty')  # fail-closed synthesis judge
VERIFIER_MODEL=$(python3 -B "$MT" --role verifier --overrides "$OV" | jq -r '.model // empty')  # per-finding verification tier
FIXER_MODEL=$(python3 -B "$MT" --role code-fixer --overrides "$OV" | jq -r '.model // empty')  # auto-fix loop fixer tier (#510)
```

**Resolve per-role engine (FR-15).** Default `claude` when unset.

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
EP=$(python3 -B "$ROOT_DIR/lib/engine_pref_load.py")            # {"reviewer","implementation"} (both "claude" if unset)
REVIEWER_ENGINE=$(echo "$EP" | jq -r '.reviewer // "claude"')
IMPL_ENGINE=$(echo "$EP" | jq -r '.implementation // "claude"')
```

**Compose the panel seat map (#510).** Per-seat engine+model over the live vendors — this replaces the single `$REVIEWER_ENGINE`-for-all-seats knob. Optional per-seat pins come from `enginePreferences.seatPins` in `$EP`; pins the account cannot honor stay loud via the shipped seat-map machinery (degradations in the receipt, seat falls back to rotation). `$AUTHOR_FAMILY` is the implementation engine's maker family; the narrative family is this orchestrator (`anthropic`). The map (per-seat tiers + resolved models, any pin/degradation disclosures) rides into the receipt; per-seat consumption is in `skills/review-code/reference/auto-fix-loop.md`.

**What `--pins` does and does not do (#1039).** A pin value is `{vendor, model?, effort?}`; a **bare
string is the documented shorthand** for `{"vendor": "<string>"}` and resolves down the identical
honorability path. Any other **pin value shape** — null, number, bool, list — and a **non-null** pin
map that is not itself an object are **refused by name**: compose exits non-zero printing
`pins-invalid:<seat>` (or `pins-invalid` for the map), never a traceback and never a silently dropped
pin. Two boundaries the refusal does **not** cover: `--pins null` is an **absent** pin map, not a
refusal (it composes normally, unpinned); and the refusal grades the **value shape** only, so a
malformed field *inside* an object pin — a `vendor` that is not a string, say — is still the
pre-#1039 behaviour, not a named refusal. **Pinning one seat
does not hold the others** — every unpinned seat stays in the normal seeded assignment over whatever
vendors are eligible for it, so an operator excluding a second maker family must pin **every** seat
they need held; there is no hold-the-rest knob.

```bash
CONFIGURED=$(python3 -B -c "import sys;sys.path.insert(0,sys.argv[1]+'/lib');import preflight_probe,core_md;p=(core_md.read('.') or {}).get('enginePreferences') or {};print(','.join(preflight_probe.configured_cross_vendor_engines(p)))" "$ROOT_DIR")
AUTHOR_FAMILY=$(python3 -B -c "import sys;sys.path.insert(0,sys.argv[1]+'/lib');import model_registry as m;print(m.family_for('code-fixer',sys.argv[2]) or '')" "$ROOT_DIR" "$IMPL_ENGINE")
SEAT_PINS=$(echo "$EP" | jq -c 'if (.seatPins // {}) == {} then empty else .seatPins end')  # owner per-seat pins (#607); empty/absent → omit --pins
PINS_ARGS=()
[ -n "$SEAT_PINS" ] && PINS_ARGS=(--pins "$SEAT_PINS")
# Leg 1 (#610): compose probes live vendors on a cache miss and rides a within-TTL receipt
# otherwise. Every review-code path dispatches a panel, so there is no receipt-only mode to
# select: seat_map's `cache-only` probe mode lost its last caller when --post was removed
# (#1121) and was reaped in #1138.
SEAT_MAP=$(python3 -B "$ROOT_DIR/lib/seat_map.py" compose --configured-engines "$CONFIGURED" --author-family "$AUTHOR_FAMILY" --narrative-family anthropic --pr-number "${PR_NUMBER:-}" --head-sha "$(git rev-parse HEAD 2>/dev/null)" "${PINS_ARGS[@]}" --repo-root "$REPO_ROOT" || echo '{"seats":{},"degradations":[{"constraint":"compose-failed","reason":"seat_map compose failed — every seat falls open to Claude"}]}')
```

The compose receipt always carries `pluginVersionSkew` — `{"status", "detail", "inspectedRoot"}`
with `status` one of `checked-clean`, `checked-degraded`, or `not-checked` — so a receipt
distinguishes "checked, clean" from "never checked"; only `checked-degraded` appends a disclosed
`plugin-version-skew` record to `degradations` (detection only, never blocks). The skew
comparison reads the repository root resolved at Setup (`$REPO_ROOT`), not ambient cwd, and
`pluginVersionSkew.inspectedRoot` names which tree was actually compared.

When dispatching specialists, map each panel seat's **tier** to a model — `reviewer-deep` → `model: $DEEP_MODEL`, `reviewer` → `model: $REVIEWER_MODEL` (the auto-fix loop's per-round schedule is driver-owned; see `round-driver.md`). Triage subagents use `model: $MECH_MODEL`; the fixer uses `model: $FIXER_MODEL` (the `code-fixer` tier, #510). An empty value means "inherit the session model" — omit the `model` arg in that case.

**Staleness self-check (first action).** Before the profile bootstrap and before dispatching anything, run the deterministic staleness/degraded self-check. It soft-fails (always exit 0) and **must never block the review** on drift — it only produces a non-blocking nudge surfaced at end of run. Read the working tree (default root, `.`). Run it only when a profile already resolved (`$EXISTS` is `true`) — a MISSING profile (`$LOCATION` is `none`) routes to the profile bootstrap below (which runs review-init/bootstrap), not to staleness:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
if [ "$EXISTS" = "true" ]; then
  DOCTOR_JSON=$(python3 -B "$ROOT_DIR/lib/repo_doctor.py" \
    "$PROFILE" "$PLUGIN_VERSION" "$RUBRIC_VERSION")
fi
```

Capture `DOCTOR_JSON`; on `readable: false`, tell the user to re-run `/superheroes:configure` and continue. Retain `message`, `signal_hash`, `nudge_acked` for the end-of-run staleness nudge. Do NOT act on `drift` here.

**Profile bootstrap (run before dispatching anything).** The review engine reads its per-project calibration (threat model, verify command, scope, focus hints, canonical patterns) from the resolved profile. If nothing resolved (`$LOCATION` is `none`), decide where to store it, create it, then write it:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
if [ "$LOCATION" = "none" ]; then
  # Decide location: env override > ask (interactive) > global (headless).
  # $INTERACTIVE was resolved above, for the whole run — do not re-decide it here.
  LOC=$(python3 -B "$ROOT_DIR/lib/review_store.py" decide-location --interactive "$INTERACTIVE")
  # If LOC is "ask" → AskUserQuestion, set LOC to owner's pick, then record band-wide (FR-3).
  # If LOC is already in-repo/global → skip record, go straight to create.
  REC=$(python3 -B "$ROOT_DIR/lib/mode_reconcile.py" reconcile --mode "$LOC" 2>/dev/null) || REC=""
  if [ -z "$REC" ] || printf '%s' "$REC" | jq -e '.written == false' >/dev/null 2>&1; then
    echo "note: couldn't record the band storage mode this run — you'll be asked again next time."
  fi
  PROFILE=$(python3 -B "$ROOT_DIR/lib/review_store.py" create --kind profile --location "$LOC")
  DECISIONS=$(python3 -B "$ROOT_DIR/lib/review_store.py" create --kind decisions --location "$LOC")
fi
```

When `decide-location` returns `ask`, present the in-repo-vs-global `AskUserQuestion` and use the answer as `$LOC`. When `$LOCATION` was `none`, run review-init inline (`skills/review-init/SKILL.md`, Steps 1–4) before the re-resolve above — **inheriting this run's already-resolved `$INTERACTIVE`, never reassigning it.** That skill's own bootstrap block opens with `INTERACTIVE=true` for the case where it is the entry point; run inline it is not, and re-running that line would raise the flag a headless run just lowered and hand review-init's interview questions to nobody — the stall this file's resolve-once rule exists to prevent. Its own headless branch (skip the interview, provisional profile from detected defaults) is the one that applies.

**Its interview is not the only question in there.** When the created layer lands **in-repo**, review-init's write step asks whether to commit the new files — and `$LOC` can be `in-repo` on a headless run regardless of the flag, because `decide_mode` honours an env override or a recorded band mode ahead of the interactive/headless split. So `$INTERACTIVE=false` plus a recorded in-repo band mode reaches a commit question with nobody to answer it. **On a headless inline bootstrap that question is skipped too:** write the core + layer, leave them **uncommitted and untracked**, say so in the dispatch summary, and continue. Committing them unasked would be the other failure — a headless review writing to the user's index — so the honest headless answer is to leave the files for a human to stage.

**Read the verify story from core calibration** via `review_code_config.py` — `$CORE`'s `verifyCommand`, else legacy `$PROFILE`'s `## Verify`. Sets `VERIFY_CMD` for the verify gate and fixer:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
VERIFY_JSON=$(python3 -B "$ROOT_DIR/lib/review_code_config.py" 2>/dev/null) || VERIFY_JSON='{}'
VERIFY_CMD=$(printf '%s' "$VERIFY_JSON" | jq -r '.verifyCommand // empty')
VERIFY_MODE=$(printf '%s' "$VERIFY_JSON" | jq -r '.verifyMode // empty')
REFUSAL=$(printf '%s' "$VERIFY_JSON" | jq -r '.calibrationRefusal.remedy // empty')
[ "$VERIFY_CMD" = "none" ] && VERIFY_CMD=""
```

When `REFUSAL` is non-empty, `core.md` calibration was not read and the legacy profile is unsupported — state that, quote the remedy, and note the legacy profile may still have supplied `VERIFY_CMD` and per-role tier overrides; say which values differ from band defaults rather than asserting they all came from the legacy file. When `VERIFY_MODE` is `unverified`, skip the verify gate. When `VERIFY_MODE` is `review-only`, degrade to one pass + presentation.

**Refresh dispatch paths before specialists.** Re-run the `calibration_resolve.py` jq block above once after bootstrap.
