# Dispatch preflight checks

The eight enumerated checks the advisor runs before launching a builder session. Read them at dispatch time.

<!-- launch-doctrine:preflight-charter:begin -->
   1. **Account and quota headroom** (`quota`, always) — a mid-batch weekly-limit death killed a launch outright.
   2. **Engine and CLI authentication** (`engine-auth`, always) — relaunch practice, not policy, until this makes it policy.
   3. **Base state matches the premise** (`base-state`, always) — merged, green (stale-retarget premise; stacked-base
      collapses).
   4. **Overlap with a live lane recorded, with its landing order**, if launching in parallel (`disjoint-surfaces`, conditional) — overlap no longer refuses; see below.
   5. **Workspace isolation, one per build** (`workspace-isolation`, always) — the shared-checkout collision.
   6. **Standing rulings present verbatim**, not reconstructed from memory (`standing-rulings`, conditional) — that collision's direct
      cause.
   7. **Owner-capability preconditions cleared, with a stated duration** (`owner-capability`, conditional) (see below).
   8. **Grant state** (`grant-state`, conditional) — whether one exists, its scope, and its exclusions; **failing** means no
      grant, or work outside the grant's enumerated scope.
<!-- launch-doctrine:preflight-charter:end -->

Check 4 does **not** ask whether the surfaces are disjoint. Overlap with a live lane is a recorded,
disclosed warning: `reserve` returns `ok` with `warnings: ["surface-overlap:<launchId>", …]` and
stamps `surfaceOverlap` on the `reserved` record, `launch` stamps the disclosure on the lane's
`started` evidence and returns the same `warnings`, and `count` tallies `overlapsAccepted`. What
passing the check means is that you have **read the overlap and accepted its landing order** — an
overlapping pair runs in parallel and **the later lander rebases** (`merge-train.md`), so a builder
landing second may take a disclosed conflict round. Declare it `fail` only when you are refusing the
launch on your own judgment; declare it `na` only when nothing is live. Two refusals survive
mechanically and are not yours to waive: a second **live** launch for one issue, and an identical
worktree path (`launch-worktree-collision`).

Check 7's "(see below)" refers to the owner-involvement taxonomy in the Showrunner charter's duty
9 (dispatch and preflight), not to anything in this file.
