---
name: guardian
description: Use to run the Guardian sweep — a periodic read-only sweep of repo health (duplication, complexity, coupling, dependency and doc freshness, dead code) that surfaces maintainability drift as plain-language consequences with receipts. Deterministic tools detect; one model pass validates each candidate against the project's own conventions and drafts the consequence. Drift-over-baseline means it reports only what changed since the last sweep, never re-raising settled trades. It never edits code, never commits or pushes, and never files issues or runs enforcement — it recommends; the advisor triages and consults the owner. Not code review of a change (that is review-code).
user-invocable: true
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# Guardian

Periodic **read-only sweep of repo health**. Deterministic collectors detect candidates; one model pass validates each against the project's declared conventions and writes plain-language consequences with receipts. Reports **drift over a baseline** — only what changed since the last sweep surfaces; settled trades stay suppressed. Per LEDGERS §2, the sweep **never edits code, never commits or pushes, never files issues, and never runs or owns enforcement** — it recommends; the advisor triages and consults the owner.

This skill is **not** `/superheroes:review-code`. Review-code finds bugs in a change; Guardian surfaces maintainability drift across the whole repo on a cadence.

## Invocation

| Form | Behavior |
| --- | --- |
| `/superheroes:guardian` | Run a read-only repo-health sweep → drift report of plain-language consequences with receipts. Never edits, commits, or files. |

## What a sweep is

1. **Collect (deterministic).** Registered lenses run standard OSS collectors with thin normalization. Each lens diffs its digest against the prior snapshot and surfaces only new or worsened candidates. Red lines (absolute thresholds) bypass the baseline quiet rule.
2. **Validate (one model pass, inline).** For each surfaced candidate, the running session validates against `CLAUDE.md`, `CONVENTIONS`, the calibration profile, and any spec'd designs — killing unactionable ones (wrong context, sanctioned convention, test/generated code). Survivors get a one-sentence plain consequence, its receipt, and an effort estimate priced from measured evidence, never rule-catalog severity.
3. **Finalize (deterministic).** The sweep writes the report and compare-and-swap-replaces the drift baseline.

**Drift-over-baseline.** The first sweep records a baseline and stays quiet except absolute red lines. Later sweeps surface only what changed.

**Lens rollout.** The health lenses (duplication, complexity, coupling, dependency and doc freshness, dead code) land across the guardian arc. This shell ships the sweep machinery with the lens registry empty — a sweep today reports a clean baseline until lenses are added.

## Run it

The sweep runs in the advisor's own session, read-only. No external dispatch — the one model validation pass happens inline here.

### 1. Resolve + collect

Save the bundle JSON to a temp file. Sub-tools `guardian_store.py paths` and `guardian_sweep.py verify-config` are available when you need resolved artifact paths or fact verification.

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
BUNDLE=$(mktemp /tmp/guardian-bundle-XXXXXXXX.json)
python3 "$ROOT_DIR/lib/guardian_sweep.py" collect --cwd . > "$BUNDLE"
cat "$BUNDLE" | jq .
```

Optional — resolved storage paths (CONVENTIONS §2):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 "$ROOT_DIR/lib/guardian_store.py" paths --cwd . | jq .
```

Optional — trust-but-verify the four FACTS before validating:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 "$ROOT_DIR/lib/guardian_sweep.py" verify-config --cwd . | jq .
```

The bundle carries: `surfaced` (candidates needing validation), `funnel`, `factVerdicts`, `ledgerStatus`, `redLines`, `lensMeta` (per-lens validation guidance and consequence templates for surfaced lenses), and `nextSnapshot` (the staged baseline). Read `ledgerStatus` first — filed/tracked items are already dispositioned; do not re-litigate them.

### 2. Validate (the one model pass)

For **each** entry in the bundle's `surfaced` list, validate the candidate:

- Read `bundle.lensMeta[<lens>].validationGuidance` for the lens-specific validation rubric, then `CLAUDE.md`, `CONVENTIONS.md`, the calibration layers (`core.md`, plugin layers), and any relevant spec definition-docs.
- **Reject** if unactionable: wrong context, sanctioned project convention, test/generated/boilerplate code, or already covered by a settled ledger trade.
- **Validate** survivors: draft exactly **one plain sentence** consequence (phrase it using `bundle.lensMeta[<lens>].consequenceTemplate` as guidance), its **receipt** (the measured evidence), an **effort** estimate from that evidence (not rubric severity), and a **ledgerJoin** id (stable join key for the ledger).

Produce a **dispositions JSON** — exactly one entry per surfaced `id`:

```json
[
  {"id": "<surfaced-id>", "verdict": "validated", "consequence": "…", "receipt": "…", "effort": "…", "ledgerJoin": "…"},
  {"id": "<surfaced-id>", "verdict": "rejected", "reason": "…"},
  {"id": "<surfaced-id>", "verdict": "degraded", "reason": "…"}
]
```

Verdicts: `validated` | `rejected` | `degraded`. A `validated` entry requires non-empty `consequence`, `receipt`, `effort`, and `ledgerJoin`.

**Ledger-first rule.** The collect step already moved filed/tracked items into `ledgerStatus` and suppressed settled trades. The model never re-opens those — only the `surfaced` list gets validated.

Write dispositions to a temp file:

```bash
DISP=$(mktemp /tmp/guardian-disp-XXXXXXXX.json)
# write the JSON array to $DISP
```

### 3. Finalize

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 "$ROOT_DIR/lib/guardian_sweep.py" finalize --cwd . \
  --bundle "$BUNDLE" --dispositions "$DISP" | jq .
```

On success, finalize writes **only** `guardian/report.md`, compare-and-swap-replaces
`guardian/latest.json`, and appends one line to `guardian/vitals.jsonl` — it **does not
write `ledger.md`**. The report shows **proposed** closures (the advisor commits them in
the next step). If the ledger is unreadable, finalize marks closures **deferred** rather
than implying none; the baseline still advances.

**Refusal outcomes (surface honestly, do not retry blindly):**

- `invalid-dispositions` — a surfaced id is missing, duplicated, or a `validated` entry lacks required fields. Fix the dispositions and re-run finalize with the same bundle.
- `raced` — a concurrent sweep advanced the snapshot since collect. Re-run from step 1; the prior baseline stays intact.

### 4. Commit the ledger (advisor, at consult/triage)

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 "$ROOT_DIR/lib/guardian_sweep.py" commit-ledger --cwd . \
  --bundle "$BUNDLE" --dispositions "$DISP" | jq .
```

This is the **only** place `ledger.md` is written — filed-item closures **and** the
per-lens report card share this one write path. It is **safe to re-run** (idempotent). It
**fails closed** on an opaque/unreadable ledger and on a stale bundle (`stale-bundle` — a
newer sweep advanced the baseline since this bundle) and on a roster-read failure
(`roster-read-failed`, retryable) — in each case leaving on-disk bytes untouched. The
residual (an owner hand-editing the file in another window at the write instant — no lock
an external editor honors) is an accepted, documented residual (LEDGERS §3). The **fenced
JSON block and the report-card region are machine-owned**; owner hand-edits belong to the
surrounding prose, which the never-clobber re-splice preserves byte-for-byte.

If `commit-ledger` is skipped or fails, closures simply defer to the next consult — the
records keep their prior state and the next sweep re-proposes the same closure; nothing is
lost.

**Refusal outcomes (surface honestly, do not retry blindly):**

- `invalid-dispositions` — same shape as finalize; fix the dispositions and re-run.
- `stale-bundle` — a newer sweep advanced `latest.json` since this bundle; re-run from step 1 or use a fresh bundle from the current sweep.
- `roster-read-failed` — transient roster read error; **retryable**.
- opaque-ledger skip — ledger content is unreadable; on-disk bytes stay untouched; closures defer.
- `raced-out` — the never-clobber loop exhausted its bounded retries; on-disk bytes stay untouched; retry after the concurrent edit settles.

## The report + storage

Artifacts live beside `core.md` under the band storage mode (CONVENTIONS §2):

| Path | Role | Written by |
| --- | --- | --- |
| `guardian.md` | Calibration layer — thresholds, cadence, coverage records | configure / rarely |
| `guardian/report.md` | Latest sweep report — advisor-facing plain consequences with receipts | the sweep, each finalize |
| `guardian/latest.json` | Drift-baseline snapshot (CAS) | the sweep, each finalize |
| `guardian/ledger.md` | Dispositions ledger + per-lens report card | the advisor, at consult/triage (sole writer) |
| `guardian/vitals.jsonl` | Append-only vitals trend history (one line per sweep) | the sweep, each finalize |

In in-repo mode these commit with the repo; in global mode they live in the project store.
The sweep writes `report.md`, `latest.json`, and vitals appends; the advisor is the sole
writer of `ledger.md` (closures, the per-lens report card, and dispositions) at
consult/triage. `configure`'s one-screen view surfaces cadence,
coverage, and benched lenses (CONVENTIONS §2.1).

**Ledger outcomes (report card).** Adjudicated dispositions count toward each lens's
actionability mix: `filed`, `verified-fixed`, `accepted`, and `reopened` count for;
`triaged-out` and `declined` count against. A lens under the actionability bar — once it
has enough adjudicated findings across enough sweeps — is benched (see CONVENTIONS §2.1).

## The lens contract

Adding a health lens is a PR that meets [the lens contract](reference/lens-contract.md) with hands-on receipts from a real repo — a lens proposed from a tool's README is not a lens.

## Cost + cadence

Deterministic collectors run in seconds plus one model pass. The sweep runs on the advisor's nudge (≥10 merges or ≥14 days since the last sweep) — no superheroes-owned scheduler; the nudge/triage loop is a later arc issue.
