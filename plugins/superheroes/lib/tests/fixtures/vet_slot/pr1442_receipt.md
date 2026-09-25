<!-- superheroes:vet-receipt -->
**Vet 308: READY. #1442 (closes #1435, GPT-6 Sol becomes the codex default; Terra retires; 5.6 Sol is pin-only) is a standalone PR and merges on the owner's word.**
- Commit `67dbc18f4e5ddffebbad08120ee220b0a8fec30e`.
- Diff digest `201b291fda673b37440c7b2280415e076bfdd5744f2200b2a047fa682c0b9342`: local `git diff f529c4ac..67dbc18f --patch` (the branch's latest merge base with `main`), 4,721 lines, non-empty, git exit 0.
- CI: workflow `CI` run 36176148843 **success** on `67dbc18f`.
- Remote head verified: yes. The PR is `BEHIND` `main` (#1436 landed since). A local merge with `main` at `b87ebeb1` is clean, and the four validators pass on it.

Advisor seat `~/.claude-four` (session 4189b35c). Vet tree: detached `67dbc18f`, merged locally with `main`. Lane: full.

**What I probed.**
1. **The defaults, read from the registry directly:** implementer, code-fixer, reviewer, verifier and doc-reviser resolve to `gpt-6-sol` at `high`; reviewer-deep and brief-check resolve to `gpt-6-sol` at `xhigh`. The codex ladder is `(gpt-6-sol, high), (gpt-6-sol, xhigh), (gpt-6-astra, high)`. `gpt-5.6-sol` appears only as a pin candidate, never as a default or a rung.
2. **Terra's retirement is guarded.** I emptied `_RETIRED_MODELS`. **Red**, 7 tests: `test_i1_no_default_surface_names_a_retired_or_pin_only_model`, the three `test_i2_retired_terra_*` cases (direct dispatch, `validate_config`/pin verdict, a role with no sanctioned model), `test_normalize_seat_pin_map_refuses_retired_codex_model`, and `test_load_engine_prefs_reports_invalid_seat_pins_and_codex_models_for_retired_terra`. Reverted.
3. **The Codex CLI floor is guarded.** I made the floor check pass any version. **Red**: `test_codex_cli_floor_probe_below_floor_refused`, the prerelease-at-floor case, the numeric-versus-lexical case, and `test_live_vendors_for_composition_cache_bypassed_when_codex_cli_drops_below_floor` (the brief-check fold F2). Reverted.
4. **Against the real CLI:** `codex_cli_floor_probe()` returns no refusal on this machine's `codex-cli 0.157.0`, and the registry's floor reads `('0.157.0', 'gpt-6-sol')`.
5. **Healthy case:** the preflight, engine-pref, registry, `core_md` and configure-view suites pass (642). No shipped prose names `gpt-5.6-terra` except as retired. `git status` is empty after the reverts.

**Calls accepted.**
- **The three blocking findings skipped at the judgment gates** (owner absent; recorded owner-unattributed):
  - (1) The tier map is copied into CONVENTIONS and two configure references, guarded by a drift test, as the issue asked.
  - (2) A Terra pin already in a config is reported rejected at load and in the configure view, and at dispatch the seat runs the default (GPT-6 Sol). That is the existing behavior for every invalid pin, and it moves toward the model the owner chose, not away. There is no silent downgrade.
  - (3) A registry change in the middle of a registration probe refuses loudly and counts as an attempt.

  None inverts a fail direction; each stands disclosed.
- **The two third-rework tripwires** were honoured by stopping the patching and disclosing (the CLI floor's misleading "version unknown" message for a missing binary; the mid-probe continuation). Both fail closed.
- **The Codex floor is a policy floor:** it rests on one refused version (0.153.4) and one accepted version (0.157.0). Disclosed.
- **Size: 420 non-test lines** (342 added, 78 removed from the merge base), past REPORT. Ruled continue as one PR on #1435 (the floor gate makes the switch safe to ship).

**What the owner still carries that the owner half does not say.** `None`.

**Degradations.**
- *The build's:* no certificate (`unrun-review` on the native synthesis seat; the stack-wide gap now owned by C13 4e); the Codex floor is set from a pair of versions.
- *Mine:* none. **One correction to my own earlier statement in chat:** the project store I cited as "another project pins reviewer-deep to 5.6 Sol" (`100c607f…`) is a test fixture, not a real project. No real project store pins a codex model. Keeping 5.6 Sol pin-only is harmless either way.

**Accounting.** Window: #1435, 2026-09-25 12:3xZ to 19:03Z.
- Parks: one (the Codex account refusal), ruled a by the owner, with the CLI upgraded.
- Reworks: six review rounds; two third-rework tripwires, disclosed.
- Receipt-integrity catches: 0.
- Panel confirmation rate: not derivable.

**Dispositions — completed (corrected in place after the owner's follow-up walk, 2026-09-25, items 22–29):**
- FU1: declined (registry, trigger: the first confused-user report)
- FU2: declined (trigger: a probe attempt counted against a model by a mid-run change)
- FU3: filed #1447 (one cleanup issue with FU4 and FU6)
- FU4: filed #1447 (one cleanup issue with FU3 and FU6)
- FU5: declined (trigger: the first real project with a rejected pin)
- FU6: filed #1447 (one cleanup issue with FU3 and FU4)
- FU7: folded into #1420 (C13 4e)
- FU8: declined, since C13 answers the probe's keep-or-retire question from the probe record (trigger: that read, or GPT-6 Sol missing the plant in 3 of its first 5 probes)

Registry rows are on #695.

<!-- superheroes:pending-proposals -->
**Pending.** This vet's ordinal: 308. `None`.

**Open owner calls at merge.** **Merge #1442** (squash; it closes #1435). It is the last code PR on the 0.34.0 cutline; #1441, the doc pass, follows it.

**Triggered fields.**
- **Certified-loop check:** converged (`audited-chain`, independent) over 6 rounds; certificate withheld (native synthesis seat); disclosed.
- **Size-tripwire check:** crossed at `ba687f58` (308 non-test lines against ~150). It was reported on the issue, not messaged, because the message step had not landed yet. Ruled continue (on #1435).
- **Lane-call backstop:** full was right, since every codex seat's model changes.
- **Revisit-registry scan:** no field-failure evidence in this vet beyond the Codex account refusal, which is recorded on the issue.



