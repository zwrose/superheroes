# Contents

- [Dispatch preflight checks](#dispatch-preflight-checks)
- [Proving engines live before a wave](#proving-engines-live-before-a-wave)
- [Where a build runs](#where-a-build-runs)
- [The owner-involvement taxonomy](#the-owner-involvement-taxonomy)

# Dispatch preflight checks

The seven enumerated checks the advisor runs before launching a builder session. Read them at dispatch time. At dispatch time you stand where the builder stands at its own preflight — about to go autonomous on assumptions nobody has exercised — with no equivalent check unless you run it.

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
Run the claude probe with the same `CLAUDE_CONFIG_DIR` the launch will spawn builders with:
`preflight-entry` refuses a claude record taken under another dir (`probe-config-dir-mismatch:claude`)
or one that recorded none (`probe-config-dir-unrecorded:claude`), and `--config-dir` names the
launch's dir when it is not this seat's own.

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

Check 6's "(see below)" refers to § The owner-involvement taxonomy, at the end of this file.

Checks marked always run every time; conditional checks run when the work needs them.
An N/A carries a **one-line reason**; "marked N/A" without a reason is a silent skip.

Keep the preflight proportionate: a twenty-minute preflight before every dispatch
repeats, one layer up, the cost mistake the product already watches for.

Supply the checks as data; the launcher records
each and the go/no-go, and it establishes `standing-rulings` itself.

## Proving engines live before a wave

At each wave preflight, one conformance probe per
dispatchable engine runs on its channel and must return a typed result that validates; the
result is recorded in the walked `engine-auth` check
(`dispatch-preflight.md`). A configuration
selftest proves configuration, never that the engine answers. The probe strengthens what
`engine-auth` must mean in a wave; it does not add a check to the list.

The failure is loud: it names the engine, what failed,
and the lanes that depend on it. The
owner either holds the wave to troubleshoot, or launches without that engine — and when that
engine supplied a lane's second family, the preflight names the substitute family, or those full
lanes park.

## Where a build runs

### The place call

For every launch, the launcher decides where each build runs.

- The project's cloud builds setting sets the default.
- The owner's [launch word](../../../rubric/glossary.md#launch-word) for one build overrides that default. "This one local" keeps the build on the owner's machine, and a word naming the cloud sends it to the cloud. The word reaches the launcher as `--place local` or `--place cloud`.
- A failed setup check pauses cloud launches for that Claude account only: its failed-check marker is the paused state. The cloud builds setting stays on, other accounts are unaffected, and launches go back to the cloud by themselves once a check passes.
- A build pointed at the cloud runs on the owner's machine when it needs something only that machine has, or when the cloud is not ready. A build is never held and never dropped. The one exception is a cloud launch whose checkout is off its base: it stops with a `launch-cloud-checkout-*` refusal for the owner rather than moving to the owner's machine (see `orchestration.md`).

### The needs you check for

Before a launch, judge from the build's order whether it needs anything only the owner's machine has. Write that into the premise as `needs`, a list of plain phrases. The launcher adds two needs by itself:

- **The phone simulator**, for a premise asking for the iPhone check.
- **This project's Canon and specs**, when they are kept outside the repository.

### How each check reads for a cloud launch

- `engine-auth`: unchanged. It probes this machine's engines. Whether the cloud can run the reviewer is the launcher's readiness check, not this one.
- `base-state`: unchanged. A cloud launch also needs the premise's `baseCommit` to be available from the remote: the launcher checks that fresh against the remote itself, not against this checkout's start commit or its tracking refs. When the launcher's own cloud base check refuses with `launch-cloud-base-not-on-remote` or `launch-cloud-base-remote-unchecked`, the build is not a no-go: it falls back to the owner's machine (`fellBack: true`), and the place call records why. `launch-cloud-base-remote-unchecked` reads as an unreachable cloud, and `launch-cloud-base-not-on-remote` as a build that needs its base commit, which only this machine has. The launcher also checks that this checkout is on a branch whose local head and whose tip on the remote are both the `baseCommit`; when it is not, the launch refuses with a `launch-cloud-checkout-*` reason and does not fall back.
- `disjoint-surfaces`: unchanged. A cloud lane takes no slot.
- `workspace-isolation`: a cloud launch makes no worktree on this machine. The cloud session works in its own copy of the repository, so the check passes with that reason.
- `standing-rulings`: unchanged. The launcher establishes them.
- `owner-capability`: a capability only the owner's machine has is a need. Write it into `needs` so the build runs on the owner's machine. A cloud build cannot reach it.
- `grant-state`: unchanged.

### After the launch: the launch report

Once every launch in the batch has returned, run `lib/launcher.py report --repo-root <root> --batch <id>`. When the JSON field `report` is not null, show the owner that field exactly as printed. See [launch report](../../../rubric/glossary.md#launch-report).

- It lists every launched build under "In the cloud" or "On your machine".
- Each build that the setting or a launch word pointed at the cloud, but that ran on the owner's machine, carries its reason and its fix. The fix is printed once per reason.
- A build the cloud was meant for that fell back because of a failed check carries the paused line: cloud builds are paused for this account until its setup check passes, and resume by themselves once it does.

### Until the cloud is fixed: the "Still on your machine" line

`still` works the reason out each time it runs, from the launch ledger and the cloud's readiness at that moment; nothing is saved. Before **every** later message to the owner, run `lib/launcher.py still --repo-root <root>`. While its JSON field `line` is not null, open the message with that line. Never write the line by hand.

How it knows the reason is fixed:

- A reason that came from the cloud builds setting stops once the setting reads switched off. A reason that came from a launch word follows the rules below.
- A reason this machine can read again stops once that condition reads true again. These are no cloud setup, a lapsed reviewer pass, a calibration mismatch, and a version mismatch read from the setup record.
- Any other reason stops only once a check made on a later day has passed and the cloud reads ready. These are no reviewer pass, an unreachable cloud, and a version a builder reported.
- A reason that came from a failed check stops once a passing check clears the marker.
- It also clears once any build in a later launch goes to the cloud.

## The owner-involvement taxonomy

**Owner involvement sorts three distinct ways:** **Owner capability** — what an
agent structurally cannot do regardless of authority (sign-in so a browser pilot is not blocked,
account actions, anything needing credentials the product forbids an agent from handling). **No
substitute exists.** **Owner authority** — a commitment or trade that binds the owner; you can hold
work and park, so latency is affordable. **A live human to unblock** — premise corrections, forks
inside ratified scope; **this resolves to the advisor**, and it is almost all of what actually
happens. **Who launched and whether the owner is available are independent
axes** — attended, reachable-with-latency, and asleep all appear under advisor launch; do not use
advisor-launch as a proxy for owner-absence. A running headless session is deaf — a need
raised after launch reaches nobody.

State a **duration** — a session that expires two hours into a four-hour build is the same
failure, later.
