# Dispatch preflight checks

The eight enumerated checks the advisor runs before launching a builder session. Read them at dispatch time.

<!-- launch-doctrine:preflight-charter:begin -->
   1. **Account and quota headroom** (`quota`, always) — a mid-batch weekly-limit death killed a launch outright.
   2. **Engine and CLI authentication** (`engine-auth`, always) — relaunch practice, not policy, until this makes it policy.
   3. **Base state matches the premise** (`base-state`, always) — merged, green (stale-retarget premise; stacked-base
      collapses).
   4. **Surfaces genuinely disjoint**, if launching in parallel (`disjoint-surfaces`, conditional) — claimed disjointness was wrong once.
   5. **Workspace isolation, one per build** (`workspace-isolation`, always) — the shared-checkout collision.
   6. **Standing rulings present verbatim**, not reconstructed from memory (`standing-rulings`, conditional) — that collision's direct
      cause.
   7. **Owner-capability preconditions cleared, with a stated duration** (`owner-capability`, conditional) (see below).
   8. **Grant state** (`grant-state`, conditional) — whether one exists, its scope, and its exclusions; **failing** means no
      grant, or work outside the grant's enumerated scope.
<!-- launch-doctrine:preflight-charter:end -->
