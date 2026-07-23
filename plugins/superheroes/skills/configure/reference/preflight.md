# Contents

- Framing + the timing rule
- 0 — Launch match (session project root == the target repo)
- A — Interactive-approval tools (live-exercised)
- B — Engine + model availability (the dispatch-calibration readout)
- C — Test-pilot readiness
- D — Worktree hygiene
- E — Board wiring for the issue being ripped
- The gate — go/no-go

# configure — preflight (the v2 run preflight)

This is the checklist the **workhorse** charter points to for its §3
preflight step (#472). It runs once, **at session start, while the owner is still present** —
before the session goes autonomous. Follow it top to bottom; every check below ends in
**pass**, **fail**, or **N/A with the reason** — a check is never silently skipped.

`ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"` is assigned once per bash block below.

## Framing + the timing rule

The preflight exists because interactive-approval state — has the owner authorized the browser
extension, is `gh` signed in, is the cross-vendor CLI authenticated — **lives in the harness, not
in any file**. Nothing on disk can prove it; the only way to prove a tool is ready is to **use it
once**, right now, and watch what happens.

Run every applicable check **while the owner is present**. A failure here costs seconds — the
owner is right there to fix it. The same failure discovered mid-autonomy costs the night (the
0.11.0 lesson: **probe before you depend**, never assume a tool is ready because it usually is).
A session **never** enters autonomous work carrying an unproven interactive tool.

A check that plainly does not apply to this run — no test-pilot in scope, no cross-vendor engine
configured — is marked **N/A, with the reason stated**. N/A is a recorded finding, not a skip.

## 0 — Launch match (session project root == the target repo)

The **first** check, before any live-exercise probe: run `git rev-parse --show-toplevel` and confirm
it resolves to the repo the routed issue belongs to. A session launched from a *different* project
(the host mints its cwd there) while it builds the target by absolute path hits the harness's
always-ask boundary on **every** out-of-project write — regardless of allow rules — because
out-of-project writes always prompt, and the *launch* project's settings, not the target's, are the
ones that apply. On a mismatch, **bail now, while the owner is present**, with the two fixes:
relaunch with the target repo as the project, or `/add-dir <target>` if continuing here is preferred.
Same fail-loud contract as every check below — never a silent skip.

## A — Interactive-approval tools (live-exercised)

These three are never config-inspected — each is **run for real**, once, right now.

### A.1 — Browser (only when test-pilot will drive the app this run)

**Connect → navigate to the project's dev origin → snapshot.** One probe, three things proven at
once: the MCP/extension connection exists, the per-origin approval is in place, and the dev
server is actually reachable on the port this project is configured to use (the weekly-eats
run-13 port-mismatch class of failure — the spine probing one port while the dev server binds
another). This is a **host-tool action** — an MCP call the orchestrator makes directly; a Python
subprocess cannot drive a browser. Record the outcome yourself:

```python
import preflight_probe
result = preflight_probe.browser_probe_result(ok, detail)  # ok = did connect+navigate+snapshot succeed
```

If it fails, **surface it to the owner now** — do not defer, do not guess a workaround. If this
run has no test-pilot in scope, mark this check **N/A** and say why.

### A.2 — Cross-vendor CLI

One harmless authenticated no-op through **every distinct configured non-Claude engine** this run
will actually dispatch through — the brief-check reviewer, and any external-engine implementer,
reviewer, or pilot this project configures. Derive them; do not hard-code one engine:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -c "
import sys, json; sys.path.insert(0, '$ROOT_DIR/lib')
import core_md, preflight_probe
prefs = (core_md.read('.') or {}).get('enginePreferences') or {}
engines = preflight_probe.configured_cross_vendor_engines(prefs)
print(json.dumps({'engines': engines,
                  'probes': [preflight_probe.cross_vendor_cli_probe(e) for e in engines]}))
"
```

If the project is **all-Claude** (`engines` comes back empty), this check is **N/A** — say so and
move on. A non-ok result for a configured engine means the CLI is not installed, not
authenticated, or not answering — fix it with the owner before going further.

### A.3 — `gh`

Confirm sign-in:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -c "
import sys, json; sys.path.insert(0, '$ROOT_DIR/lib')
import preflight_probe
print(json.dumps(preflight_probe.gh_auth_probe()))
"
```

**And exercise one real write.** Auto-mode permission classification gates `gh` **writes** — issue/PR
comments, edits — **separately from reads**, so a passing `gh auth status` (a read) does not prove a
`gh issue comment` (a write) will clear mid-run. Post a **throwaway probe comment on the issue being
built, then delete it** — both the create and the delete are writes, so a probe that posts and
deletes cleanly proves the write class end to end. Keep the probe to a **comment** — never a label or
other board write (§E forbids the preflight touching the board). The create fires a watcher
notification before the delete lands, so the probe is not entirely invisible; that is the cheap cost
of proving the write, against a blocked write discovered headless hours later (weekly-eats
we#498/we#499 both cleared preflight, then lost their intake receipt when a `gh` write was blocked
immediately after a green preflight; #526 permission-surface evidence).

A blocked write here **fails the preflight loudly** — fold its outcome into the go/no-go aggregation
(§ "The gate — go/no-go") exactly as the browser outcome is folded in, so `go` can never stay true
after a blocked write; same fail-loud contract as every check above. If the create succeeds but the
**delete** is blocked or fails, the probe comment persists — remove it (or flag it to the owner) as
part of the fail-loud outcome, so the probe leaves nothing behind.

## B — Engine + model availability (the dispatch-calibration readout)

Separate from "is the CLI authenticated" (A.2): this check is "are the configured engines +
model tiers **readable**, and are the chosen external engines actually **ready** to dispatch." For
external engines (Codex, Cursor), run `$ROOT_DIR/lib/engine_detect.py` — it reports installed /
authenticated / ready per engine without spending a real dispatch.

The **effective engine + model for every v2 dispatch role** is the dispatch-calibration readout —
compute it once and carry it forward into two places: the build brief, and the PR's provenance
section, so anyone reading the PR later can see exactly what ran without re-deriving it:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -c "
import sys, json; sys.path.insert(0, '$ROOT_DIR/lib')
import preflight_probe
print(json.dumps(preflight_probe.dispatch_calibration(cwd='.'), indent=2))
"
```

This prints one row per role — `implementer`, `brief-check`, `review-code`, `pilot` — each with
the resolved `engine` and `model`. Fold it, verbatim or summarized, into the brief and the PR.

## C — Test-pilot readiness

Applicable only when this run will use test-pilot. Beyond the bare browser connection (A.1),
confirm the app is reachable **through whatever login or seed data it needs** — not just the
landing page. An auth wall test-pilot cannot pass mid-run is exactly the failure this preflight
exists to catch early. If this run has no test-pilot, mark **N/A** and say so.

## D — Worktree hygiene

A clean tree, checked out on the issue's base branch, with the managed worktree in good order
before any work starts. If the worktree is dirty, mid-migration, or pointed at the wrong base,
resolve it now — building on top of a bad checkout compounds every problem downstream.

## E — Board wiring for the issue being ripped

Confirm the issue being worked exists and its route is legible (build-ready / needs-discovery /
unrouted). This check is **read-only** — the preflight never writes to the board; wiring issues
into epics/projects is the advisor's job, never the builder's.

## The gate — go/no-go

Every applicable, required probe from A–E above rolls up through one FAIL-LOUD aggregator. Run
the subprocess-able probes together — **omit `--engine`** so the CLI derives and probes every
distinct configured non-Claude engine itself (the same `configured_cross_vendor_engines` logic as
§A.2; pass `--engine <name>` only to force one specific engine, e.g. for back-compat scripting):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 "$ROOT_DIR/lib/preflight_probe.py" run --cwd .
```

The JSON output's `crossVendorEngines` field records which engines it derived and probed — an
empty list means the project is all-Claude and the cross-vendor CLI check was correctly skipped
as **N/A**, not silently missed. Then fold in the browser outcome (a host action, §A.1) before
deciding:

```python
import preflight_probe
all_results = probes_from_run_json + [
    preflight_probe.browser_probe_result(browser_ok, detail),           # host action (§A.1): fold in only when the browser probe actually ran; OMIT on no-app runs (their browser N/A is recorded per §A.1, not through this helper — it can't emit N/A)
    {"tool": "gh write", "ok": gh_write_ok, "detail": gh_write_detail},  # host action (§A.3): the throwaway-comment probe (always applicable)
]
verdict = preflight_probe.aggregate(all_results)
```

`verdict["go"]` is `True` only if every applicable, required probe passed. Show the owner the
go/no-go and, if it is not a go, every tool in `verdict["blocking"]` by name — never a bare
"preflight failed." A `verdict["na"]` entry is a check this run legitimately skipped (with its
reason already stated above); it never counts against `go`. Only on a clean go does the session
move to the build brief and go autonomous.
