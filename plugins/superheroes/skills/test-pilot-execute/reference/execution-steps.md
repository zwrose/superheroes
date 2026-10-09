# Contents

- Framing — provisioning vs. execution
- Steps 1–4 — provision the run
- Steps 5–8 — execute, observe, report
- The iPhone check

# test-pilot-execute — the execution steps

This file is the **one home** of test-pilot's execution step-body. `SKILL.md`
points here rather than restating it, and a dispatched consumer that cannot
reach the skill (the `pilot` build subagent, which has no Skill tool) **cites
this path** instead of keeping its own copy — CONVENTIONS §11.4.

`ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"` is assigned once per bash
block below.

## Framing — provisioning vs. execution

Steps 1–4 **provision the run** (a valid plan, seeded data, the app up, a
browser tool) — this is one-time setup, done before execution begins. Steps
5–8 **execute and observe**. Once execution starts, the plan and seed are
frozen: any problem you hit is a finding, never a re-provisioning.

## Steps 1–4 — provision the run

1. **Resolve.** `store.py resolve`; read the profile and its config block.

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
   # FR-7/8: surface the single coalesced storage-mode reconcile nudge (non-blocking, ack-gated).
   NUDGE_MSG=$(python3 -B "$ROOT_DIR/lib/mode_reconcile.py" signals 2>/dev/null | jq -r 'if . == null then empty else .message end' 2>/dev/null)
   [ -n "$NUDGE_MSG" ] && echo "⚠ storage-mode: $NUDGE_MSG"
   ```
   Find plan records `<manifests_dir>/<key>.plan.json` for the current
   branch — default: every slot in sequence; an explicit slot argument
   narrows to one. None → run the test-pilot-plan skill to author one first,
   then return. The PR comment is NEVER parsed as the plan source.
   Validate each before executing:

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
   python3 -B "$ROOT_DIR/lib/engine.py" validate-plan --branch B [--slot S] --json
   ```

   A validation error means the plan is not runnable: (re)author it via test-pilot-plan here in setup, never an app bug. Getting a valid plan to run is provisioning the input before the run — not a fix; you never fix.
2. **Seed check.** `engine.py status --json`; apply the manifest if drift or
   nothing applied (`engine.py apply --branch B [--slot S] --json`). Seeding
   provisions the data the plan needs to run — it is setup, not a fix. If
   `apply` is refused (e.g. a protected-target `EngineError`) and the user
   has not authorized `--allow-protected` this session (boundary 1), the run
   cannot be provisioned — post a **partial** results comment naming it
   blocked/unprovisioned (with the scrubbed refusal), and stop. Never pass
   `--allow-protected` on your own, and never drive the plan against unseeded
   data.
3. **App up.** Per the profile: if `mayManageServer`, start `devCommand` in
   the background and poll `readinessUrl` until it answers; else verify it
   answers — when it does not, ABORT with remediation: "start the dev server
   (`devCommand` from profile) and re-run execute" (or set `mayManageServer`
   via `/superheroes:configure`). Post a **partial** results comment naming
   the blocked/unprovisioned state (same shape as step 2 seed refusal). Never
   continue without an answering app.
4. **Browser tool.** Profile `browserTools` order ∩ currently connected
   (ToolSearch). Empty intersection → ABORT with remediation: "run
   test-pilot-init to install/record a browser tool". Never continue
   without one. A missing browser tool stops only the browser-MCP plan; the
   iPhone check, when it applies, runs and posts on its own (it needs no
   browser MCP).

## Steps 5–8 — execute, observe, report

5. **Execute and observe each step** from the plan record: perform the
   interactions, verify `expected` via DOM/snapshot reads, watch
   console/network for silent errors. Record per step — what you did, what
   you observed, pass/fail, and the concrete evidence (scrubbed) — through
   the external per-slot **artifact store** (`reference/pilot-contract.md`
   §The per-slot artifact store): each step log via the `step-log` class;
   on a **failed** step, a screenshot via `failure-screenshot`. A **refused**
   retention is a reportable outcome — name the refusal token in the run
   results; never drop evidence silently. **Trace capture** is an explicit
   per-run opt-in (off by default); an opted-in `trace` is retained only
   when its redaction can be established. **Interaction calibration:**
   - Target controls by **accessible name** using the element reference the
     browser tool's accessibility snapshot returns — never by **index** or
     ordinal position, never by **screen coordinates**.
   - Drive each interaction with a **pointer** action (a real input event) —
     never an evaluated `.click()` or other **scripted event dispatch**
     through the browser tool's script-evaluation escape hatch.
   - When a step says "the first" or "the next" thing, skip targets
     reported as **`aria-disabled`**.

   Provisioning is finished: from here the plan and seed are frozen — a plan
   or seed problem you hit while executing is a finding (step 6), never a
   re-author, re-apply, or retry. **One carve-out:** if the first attempt
   produced **no observable state change**, you may vary the interaction
   mechanism once as a diagnostic observation that tests the procedure —
   record the result either way; that is not a forbidden retry toward a pass.
   If the interaction may already have taken effect, do **not** re-activate it
   — record the failure as a finding instead, noting the mechanism could not
   be **safely** varied. When a variation is performed and app state may
   nonetheless have diverged from what the plan assumes, record that on the
   step so later steps are read in that light. Re-running to obtain a pass,
   re-authoring the plan, re-applying the seed, or re-provisioning remain
   forbidden outright.
6. **On failure, record a finding — never act on it.** Note the failing step.
   Before you classify a failure as an **app bug**, if you reproduced it with
   N identical procedures and the first attempt produced no observable state
   change, vary the interaction mechanism once — N identical runs test the
   procedure N times; an A/B on the same harness cannot clear that harness.
   **Sanctioned variation axes** (index, ordinal position, screen coordinates,
   and evaluated `.click()` / scripted event dispatch are **never** admissible):
   **keyboard activation** of the element after focusing it (a real input
   event, not scripted dispatch), or re-taking the accessibility snapshot and
   re-resolving the target by **accessible name**. The pointer requirement
   above governs the **primary** interaction; a diagnostic variation may use a
   different real input event. If the interaction may already have taken
   effect, do **not** re-activate it — record the finding as **app bug
   (unconfirmed — variation unsafe)** and note the mechanism could not be
   **safely** varied. If variation is not possible, record the finding as
   **app bug (unconfirmed — evidence ceiling)**. If the variation **succeeds**,
   record the asymmetry as evidence on the step — what happened concretely
   (e.g. pointer action failed N/N; keyboard activation succeeded) — and
   record the finding as **app bug (unconfirmed — procedure not excluded)**
   with that asymmetry noted; attribute no cause. Otherwise classify it
   (plan/seed problem, or app bug) and capture a scrubbed diagnosis with its
   evidence (console, network, DOM). Then **continue the remaining steps.** You
   never fix code, never edit or re-seed-and-retry the plan, never commit — a
   failure is a finding the caller acts on.
7. **Post results.** Fill `templates/results-comment.md` (verdict: PASSED /
   FAILED / PARTIAL — the observed outcome of the run, not a certification
   that the branch is correct; per-step table; findings with evidence; run
   metadata). Post:
   `pr_comment.py upsert --pr N --family results --key K --body-file F --plans-dir <plans_dir>`.
   No PR → write to `<plans_dir>/<key>.results.md`. If the run was
   interrupted (browser died, server unreachable), post whatever completed
   marked **partial** — state stays intact for resumption.
8. **Hand off.** Report what is seeded, what passed/failed, and the findings.
   The verdict is the run's observed outcome; the human's spot-check is the
   certifier. Fixes route to the invoking session — the PR is ready for
   spot-checking.

## The iPhone check

You drive the lane's simulated iPhone through `lib/iphone_check.py`, with no
browser MCP. Every verb prints one JSON object and exits 0 when its `ok` is
true. Every verb that touches the phone takes `--timeout <seconds>`.

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/iphone_check.py" preflight [--issue-names-check]
python3 -B "$ROOT_DIR/lib/iphone_check.py" boot --phone <id>
python3 -B "$ROOT_DIR/lib/iphone_check.py" open --phone <id> --url <page-url> --run-dir <dir>
python3 -B "$ROOT_DIR/lib/iphone_check.py" drive --phone <id> -- type hello
python3 -B "$ROOT_DIR/lib/iphone_check.py" shot --phone <id> --out <png> --page <page-url> --where browser
python3 -B "$ROOT_DIR/lib/iphone_check.py" read --run-dir <dir> --token <token> --where browser
python3 -B "$ROOT_DIR/lib/iphone_check.py" judge < step.json
python3 -B "$ROOT_DIR/lib/iphone_check.py" render --in check.json
```

- **When it applies.** The check applies when `SUPERHEROES_IPHONE_ID` or
  `SUPERHEROES_DEVICE_HUB` is in your environment (the launcher sets both for
  an iPhone launch), or when the issue's done-definition names an iPhone check.
  Run `preflight` (`--issue-names-check` when the issue names one). Its `state`
  decides:
  - `off`: leave the iPhone section out of the results.
  - `did-not-run`: post its `line` as the opening of the results, and stop the
    iPhone check.
  - `ready`: go on. The handed ID is the lane's only phone. Never create or
    boot another, pick a phone by name, or use `booted` as a target.
- **Where to check.** The issue's statement governs: the browser, the installed
  web app, or both. A check limited to the browser does not meet an issue that
  asks for the installed app. When the issue says nothing, the lane chooses and
  the results say so (`chosenBy: "lane"`). The plugin makes no choice.
- **Boot and open.** Boot the phone, then open the page in Mobile Safari and
  keep the `token` it returns. Before any tap, take a first reading
  (`read --run-dir <dir> --token <token> --where browser`). It proves the
  page's reporting script. If `read` returns an `error` (a session or
  listener failure), stop the whole check with that error as the reason. If it
  never arrives, take a screenshot before calling it a miss. If Safari is not showing the page (a fresh phone's Safari
  can drop its first URL and show its Start Page), `open` once more, keep the
  new `token`, and take the first reading again. Re-opening is preparation, not
  a step of the plan. A second miss, or a page that is showing and sends no
  reading, stops the whole check. Fetch the page source served at the page URL
  once and search it for `superheroes-reading`. With no match the reason is
  `the app lacks its reporting script`; otherwise it is
  `a page reading never returned`.
  A later reading that never returns ends only its part (see Stops).
- **Driving.** Step 5's calibration (accessible names, no coordinates) is for
  browser tools; on the phone, use these rules. Send every tap and keystroke
  through `drive --phone <id> -- <axe args>` (`drive --phone <id> -- type hello`
  types). It carries the workaround for AXe dropping a tap whose process exits
  at once (`AXE_HID_STABILIZATION_MS=2000`, and `--post-delay 1` on a tap), so
  never call `axe` yourself to tap or type. Find a control with
  `axe describe-ui --udid <phone>`, then tap by `--label` or by coordinates.
  `describe-ui` can time out right after boot; retry it once. The page's own
  contents and Safari's sheets may be missing from it; then tap by coordinates
  read off a screenshot, in points (screenshot pixels divided by the phone's
  scale; 3 on current iPhones). Take a screenshot with `shot --phone <id> --out <png> --page <page-url>
  --where <part>`. Look at every screenshot yourself: you judge `keyboardSeen`
  and `expectedSeen` from the image.
- **Readings.** After each step the plan checks, take a reading with
  `read --run-dir <dir> --token <token> --where <part>`, where `<part>` is
  `browser` or `installed`. A reading gives the visible height, the focused
  element, its value (withheld for a password field), and whether the page ran
  in the browser or installed. The page's development-only reporting script
  posts each reading as JSON to the address carried in its URL's
  `superheroes-reading` query parameter (the name is `READING_PARAM` in
  `lib/iphone_check.py`). `read` listens on that loopback
  address for one call. Nothing outside the page is needed
  (`lib/tests/fixtures/iphone/reading-page.html` reports this way; its test
  harness fills the name in). An
  installed app keeps the address only when it opens the page URL it was added
  from. A project whose manifest `start_url` drops the query gets
  `no page reading from the installed app` until its development build keeps it.
- **The installed app.** When the check includes it, add the page to the Home
  Screen from Safari: Share → Add to Home Screen, keep "Open as Web App" on,
  Add. Find each control with `axe describe-ui --udid <phone>`. Dismiss a
  one-time keyboard tip if one covers the screen. After returning to the Home
  Screen, take a screenshot before tapping an icon; it may be on another Home
  Screen page (swipe to it). Open the app from its Home
  Screen icon and read with `--where installed`. Judge these preparation taps
  by whether the install succeeded; a failed install is
  `iPhone check did not run — installed-app check: the Home Screen install failed`.
  An installed part needs a reading that reports installed; `render` enforces it.
- **No response is never a pass.** Pass each plan step to `judge` with the
  before and after readings and what the screenshot showed. Its fields are
  `kind` (`tap-field`, `type` or `other`), `step`, `before`, `after`,
  `keyboardSeen`, `screenChanged`, `expected`, `expectedSeen` and `password`;
  a `tap-field` step also carries `target`, the intended field's `id` (or
  `name:<name>` for a field with no id) as a reading reports it in `focused`, and
  is completed only when the after reading's field is that `target` and a keyboard
  was seen; a typing step completes only when its before and after readings name the same field.
  A driver that reports success proves nothing; only `judge` decides. A step
  `judge` calls not completed ends that part with `no response to input (<step>)`.
- **Stops.** Every call has a time limit. A call that never returns ends its
  part: `a driver step never returned (<step>)`, `a screenshot never returned`
  or `a page reading never returned`. A boot that never returns ends the whole
  check. A cause that stops everything gets one whole-check line; each part that
  fails for its own cause gets its own; an included part never attempted gets
  `not attempted`. Evidence gathered before a stop stays in the results.
- **Labels and posting.** Every screenshot and reading carries the six labels
  that `shot` and `read` return: `phone`, `model`, `iOS`, `page`, `where`,
  `source`. Never type a label by hand, and never copy the phone ID from the
  environment. Write the check JSON (`noPhone`, `whole`, `where`, `chosenBy`,
  `parts` with `included`, `completed` and `reason` for `browser` and
  `installed`, and `evidence`), then run `render --in <file>`; it refuses
  unlabelled evidence. A PR comment shows a screenshot only by a URL its
  readers can open: publish each screenshot where the PR readers can reach it
  and pass its `url` in the evidence; else the results name the local file and
  its `sha256` (pass `path` and `sha256` from `shot`). The plugin makes no
  hosting choice. Put its `opening` first in the results, before any
  evidence, and its `section` after the steps table (the iPhone slots in
  `templates/results-comment.md`).
- **Hard lines.** Never quit Device Hub. Never shut down, erase or delete any
  phone; the advisor deletes the lane's phone when it reaps the lane. Never
  drive a phone other than the handed one. The check needs no owner approval
  and no sandbox change. An iPhone check that did not complete never holds the
  PR: the results say so, and the build hands back.
