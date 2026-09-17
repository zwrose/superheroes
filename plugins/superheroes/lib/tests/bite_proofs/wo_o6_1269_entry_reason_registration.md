# WO-O6 bite-proof — closed 2026-09-16 (WO-R7A)

The guarded element in this record — registering `entry-reason-undeclared` as a member of `dispatch_outcome.ALL_REASONS` / `NOT_RUN_REASONS` — was removed by WO-R7A. Entry vocabulary now lives solely on the additive `entryReason` key (`seat_bundle.ENTRY_REASON_UNDECLARED`); the outcome channel stays `reason: unrunnable` unconditionally via `engine_dispatch._entry_refusal_terminal`.

Replacement proofs: `plugins/superheroes/lib/tests/bite_proofs/wo_o7_1269_entry_channel.md`.
