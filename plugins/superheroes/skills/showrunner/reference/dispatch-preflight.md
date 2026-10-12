# Dispatch preflight checks

The seven enumerated checks the advisor runs before launching a builder session. Read them at dispatch time.

<!-- launch-doctrine:preflight-charter:begin -->
   1. **Engine and CLI authentication** (`engine-auth`, always) — relaunch practice, not policy, until this makes it policy.
   2. **Base state matches the premise** (`base-state`, always) — merged, green (stale-retarget premise; stacked-base
      collapses).
   3. **Overlap with a live lane recorded, with its landing order**, if launching in parallel (`disjoint-surfaces`, conditional) — overlap no longer refuses; see below.
   4. **Workspace isolation, one per build** (`workspace-isolation`, always) — the shared-checkout collision.
   5. **Standing rulings present verbatim**, not reconstructed from memory (`standing-rulings`, conditional) — that collision's direct
      cause.
   6. **Owner-capability preconditions cleared, with a stated duration** (`owner-capability`, conditional) (see below).
   7. **Grant state** (`grant-state`, conditional) — whether one exists, its scope, and its exclusions; **failing** means no
      grant, or work outside the grant's enumerated scope.
<!-- launch-doctrine:preflight-charter:end -->

For check 1 in a wave, run `lib/conformance_probe.py` once per dispatchable engine, then compose
the walked `engine-auth` entry with `preflight-entry` and write it into the checks file the launcher
walks. A failed engine with no owner word → hold (`preflight-failed:engine-auth`, nothing launches).
With `--launch-without <engine> --owner-word "<text>"` → pass whose evidence names substitute families
from probed cells only, or **PARK** when the seat map reports `same-family` degradation.

Check 3 does **not** ask whether the surfaces are disjoint. Overlap with a live lane is a recorded,
disclosed warning: `reserve` returns `ok` with `warnings: ["surface-overlap:<launchId>", …]` and
stamps `surfaceOverlap` on the `reserved` record, `launch` stamps the disclosure on the lane's
`started` evidence and returns the same `warnings`, and `count` tallies `overlapsAccepted`. What
passing the check means is that you have **read the overlap and accepted where the cost lands** — an
overlapping pair runs in parallel, and the later lander **rebases onto the moved base** (the
`base-moved` standing ruling) and **keeps its lane branch-current**, which `merge-train.md` requires
of every remaining lane; a union fix rides the **last open PR**, disclosed, per that same file. So a
builder landing second may take a disclosed conflict round. Declare it `fail` only when you are refusing the
launch on your own judgment; declare it `na` only when nothing is live. Two refusals survive
mechanically and are not yours to waive: a second **live** launch for one issue, and an identical
worktree path (`launch-worktree-collision`).

Check 6's "(see below)" refers to the owner-involvement taxonomy in the Showrunner charter's duty
9 (dispatch and preflight), not to anything in this file.

## Where a build runs

### The place call

For every launch, the launcher decides where each build runs.

- The project's cloud builds setting sets the default.
- The owner's [launch word](../../../rubric/glossary.md#launch-word) for one build overrides that default. "This one local" keeps the build on the owner's machine, and a word naming the cloud sends it to the cloud. The word reaches the launcher as `--place local` or `--place cloud`.
- A build pointed at the cloud runs on the owner's machine when it needs something only that machine has, or when the cloud is not ready. A build is never held and never dropped.

### The needs you check for

Before a launch, judge from the build's order whether it needs anything only the owner's machine has. Write that into the premise as `needs`, a list of plain phrases. The launcher adds three needs by itself:

- **The phone simulator**, for a premise asking for the iPhone check.
- **GitHub's stack interface**, for every layer of a stack (a premise with `stack`). The cloud blocks GitHub's GraphQL interface: there, `gh pr` and `gh issue` fail while `gh api` REST calls work. Reading and linking a stack's layers uses GraphQL.
- **This project's Canon and specs**, when they are kept outside the repository.

### How each check reads for a cloud launch

- `engine-auth`: unchanged. It probes this machine's engines. Whether the cloud can run the reviewer is the launcher's readiness check, not this one.
- `base-state`: unchanged. A cloud launch also needs the premise's `baseCommit` to be available from the remote: the launcher checks that fresh against the remote itself, not against this checkout's start commit or its tracking refs. The launcher's refusals `launch-cloud-base-not-on-remote` and `launch-cloud-base-remote-unchecked` are launch refusals, a no-go you clear like any other launcher refusal. They are not a place decision, and the place call's never-held, never-dropped rule covers only where a launched build runs.
- `disjoint-surfaces`: unchanged. A cloud lane takes no slot.
- `workspace-isolation`: a cloud launch makes no worktree on this machine. The cloud session works in its own copy of the repository, so the check passes with that reason.
- `standing-rulings`: unchanged. The launcher establishes them.
- `owner-capability`: a capability only the owner's machine has is a need. Write it into `needs` so the build runs on the owner's machine. A cloud build cannot reach it.
- `grant-state`: unchanged.

### After the launch: the launch report

Once every launch in the batch has returned, run `lib/launcher.py report --repo-root <root> --batch <id>`. When the JSON field `report` is not null, show the owner that field exactly as printed. See [launch report](../../../rubric/glossary.md#launch-report).

- It lists every launched build under "In the cloud" or "On your machine".
- Each build that the setting or a launch word pointed at the cloud, but that ran on the owner's machine, carries its reason and its fix. The fix is printed once per reason.

### Until the cloud is fixed: the "Still on your machine" line

`report` remembers the reason when builds ran on the owner's machine because the cloud was not ready. Before **every** later message to the owner, run `lib/launcher.py still --repo-root <root>`. While its JSON field `line` is not null, open the message with that line. Never write the line by hand.

How it knows the reason is fixed:

- A reason that came from the cloud builds setting stops once the setting reads switched off. A reason that came from a launch word follows the rules below.
- A reason this machine can read again stops once that condition reads true again. These are no cloud setup, a lapsed reviewer pass, a calibration mismatch, and a version mismatch read from the setup record.
- Any other reason stops only once a check made on a later day has passed and the cloud reads ready. These are no reviewer pass, an unreachable cloud, and a version a builder reported.
- It also clears once any build in a later launch goes to the cloud.
