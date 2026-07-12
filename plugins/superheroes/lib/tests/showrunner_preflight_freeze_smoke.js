const assert = require('assert')
const modelTier = require('../model_tier.js')
const enginePref = require('../engine_pref.js')
const sr = require('../showrunner.js')

// The current snapshot format version the consumer accepts. Every well-formed snapshot below stamps
// it; the migration-gate (B) case deliberately stamps an OLDER version to prove it is ignored.
const V = sr.READOUT_VERSION

async function main() {
  // FR-8: a pinned per-role model in __SR_OVERRIDES is what resolveModel returns (the frozen value).
  globalThis.__SR_OVERRIDES = { author: 'sonnet' }  // seeded by the startup pipe from the frozen snapshot
  assert.strictEqual(modelTier.resolveModel('author', globalThis.__SR_OVERRIDES, null), 'sonnet')

  // UFR-2: an unpinned field (absent from the frozen overrides) resolves live to the band default.
  globalThis.__SR_OVERRIDES = {}
  assert.strictEqual(modelTier.resolveModel('author', globalThis.__SR_OVERRIDES, null), 'opus')

  // FR-8/FR-12: a pinned engine pref is what resolveEngine returns.
  globalThis.__SR_ENGINE_PREFS = { reviewer: 'codex', implementation: 'claude', effort: { review: 'xhigh' } }
  assert.strictEqual(enginePref.resolveEngine('review', globalThis.__SR_ENGINE_PREFS), 'codex')
  assert.strictEqual(enginePref.resolveEffort('codex', 'review', globalThis.__SR_ENGINE_PREFS.effort), 'xhigh')

  // FR-8: the spine exposes a mergeFrozenSnapshot helper that folds the frozen snapshot's per-role
  // values over the config-derived maps — every concrete row's displayed value freezes into dispatch,
  // and a role NOT present (or excluded) in the snapshot keeps the config-derived (resolve-live) value.
  assert.strictEqual(typeof sr.mergeFrozenSnapshot, 'function',
    'showrunner must export mergeFrozenSnapshot (the freeze fork)')
  const frozen = {
    version: V,
    phases: [
      { phase: 'plan', role: 'author', kind: 'author', model: 'sonnet', overridden: true },
      { phase: 'review-plan', role: 'reviewer', kind: 'review', engine: 'codex', model: 'sonnet',
        engineModel: 'gpt-5.6-terra', effort: 'xhigh', overridden: true },
    ],
  }
  const baseOv = { author: 'opus' }        // config-derived model-tier map
  const baseEp = { reviewer: 'claude', implementation: 'claude', effort: {} }
  const merged = sr.mergeFrozenSnapshot(frozen, baseOv, baseEp)
  // pinned model wins over the config-derived value
  assert.strictEqual(merged.overrides.author, 'sonnet', 'a pinned model must win over the config-derived value')
  // pinned engine + effort seeded onto the engine-prefs map
  assert.strictEqual(merged.enginePrefs.reviewer, 'codex', 'a pinned engine must win over the config-derived value')
  assert.strictEqual(merged.enginePrefs.effort.review, 'xhigh', 'a pinned effort must seed the effort sub-map')

  // GPT-5.6: the concrete Codex model freezes into the provider-specific map, while the shared tier
  // remains in model overrides for a valid native Claude fallback.
  const codexModelSnap = {
    version: V,
    phases: [
      { phase: 'review-plan', role: 'reviewer', kind: 'review', engine: 'codex',
        model: 'sonnet', engineModel: 'gpt-5.5', effort: 'high' },
      { phase: 'plan', role: 'author-plan', kind: 'author-plan', engine: 'codex',
        model: 'opus', engineModel: 'gpt-5.6-sol', effort: 'xhigh' },
    ],
  }
  const codexMerged = sr.mergeFrozenSnapshot(codexModelSnap, {},
    { reviewer: 'claude', implementation: 'claude', planAuthor: 'claude', effort: {}, codexModels: {} })
  assert.strictEqual(codexMerged.overrides.reviewer, 'sonnet',
    'the fallback-safe shared reviewer tier freezes separately')
  assert.strictEqual(codexMerged.enginePrefs.codexModels.reviewer, 'gpt-5.5',
    'the per-run GPT-5.5 pin freezes only in the Codex model map')
  assert.strictEqual(codexMerged.enginePrefs.planAuthor, 'codex',
    'the plan-author engine freezes through its own preference key')
  assert.strictEqual(codexMerged.enginePrefs.codexModels['author-plan'], 'gpt-5.6-sol',
    'the plan-author concrete Codex model freezes by tier role')

  const invalidCodexPair = sr.mergeFrozenSnapshot({
    version: V,
    phases: [{ phase: 'review-plan', role: 'reviewer', kind: 'review', engine: 'codex',
      model: 'sonnet', engineModel: 'gpt-5.5', effort: 'max' }],
  }, {}, { reviewer: 'codex', implementation: 'claude', effort: { review: 'high' },
    codexModels: { reviewer: 'gpt-5.6-terra' } })
  assert.strictEqual(invalidCodexPair.enginePrefs.codexModels.reviewer, 'gpt-5.6-terra',
    'an invalid frozen GPT-5.5 + max pair must not replace the live Codex model')
  assert.strictEqual(invalidCodexPair.enginePrefs.effort.review, 'high',
    'an invalid frozen GPT-5.5 + max pair must not replace the live effort')
  assert.strictEqual(invalidCodexPair.pinnedCount, 0,
    'an invalid frozen Codex pair rejects the entire snapshot so startup must re-confirm')
  assert.ok(/invalid Codex model\/effort pair/.test(invalidCodexPair.reason || ''),
    'the rejected snapshot names the invalid provider pair')

  // Behavior-preserving: no frozen snapshot -> the maps are returned unchanged (the rollback state).
  const passthrough = sr.mergeFrozenSnapshot(null, baseOv, baseEp)
  assert.deepStrictEqual(passthrough.overrides, baseOv, 'no snapshot -> config-derived overrides unchanged')
  assert.deepStrictEqual(passthrough.enginePrefs, baseEp, 'no snapshot -> config-derived engine prefs unchanged')

  // A role NOT named by any snapshot row keeps its config-derived value (the freeze only touches
  // roles the snapshot actually rendered a row for).
  const partial = { version: V, phases: [{ phase: 'review-plan', role: 'reviewer', kind: 'review',
    engine: 'codex', model: 'sonnet', engineModel: 'gpt-5.6-terra', effort: 'high', overridden: true }] }
  const m2 = sr.mergeFrozenSnapshot(partial, { author: 'opus' }, { reviewer: 'claude', implementation: 'claude', effort: {} })
  assert.strictEqual(m2.overrides.author, 'opus', 'a role absent from the snapshot keeps its config-derived model')
  assert.strictEqual(m2.enginePrefs.reviewer, 'codex', 'the pinned reviewer engine is applied')

  // Empty snapshot ({phases: []}) passes config through unchanged (backward-compat invariant).
  const emptySnap = sr.mergeFrozenSnapshot({ version: V, phases: [] }, baseOv, baseEp)
  assert.deepStrictEqual(emptySnap.overrides, baseOv, 'empty snapshot -> config-derived overrides unchanged')

  // FR-8 acceptance bullet 2 (end-to-end at the merge layer): the run must dispatch with the EXACT
  // settings the confirmed readout displayed — a snapshot frozen at confirmation — REGARDLESS of a
  // config edit made in the confirm window. Build a snapshot from config A (mixed rows), then present
  // a DIFFERENT live config B to mergeFrozenSnapshot; assert the merged result carries A's values for
  // EVERY concrete row (not just the overridden one), B's values only for the excluded rows
  // (orchestration / unavailable / unrecognized), and Claude for the fallback row.
  //
  // Mutation this kills: restoring `if (!row.overridden) continue` un-freezes every non-overridden
  // concrete row (builder/reviewer-deep/plain reviewer), so they'd resolve live from config B and
  // the A-value assertions below would fail.
  // NOTE the shared `implementation` engine key: build AND fix both resolve their engine from it (the
  // engine-pref shape has no separate fix key). In a real readout both rows therefore show the SAME
  // engine, so this scenario keeps the build row as the implementation-engine witness and covers the
  // fallback (fix) row's engine separately below — mixing a codex build with a claude-fallback fix in
  // one snapshot is a shared-key collision the pref shape can't represent, not an FR-8 concern.
  const snapshotA = {
    version: V,
    phases: [
      // plain (non-overridden) rows — displayed A's concrete values; MUST freeze to A.
      { phase: 'workhorse', role: 'builder', kind: 'build', engine: 'codex', model: 'opus',
        engineModel: 'gpt-5.6-sol', effort: 'high' },
      { phase: 'review-code', role: 'reviewer-deep', kind: 'review-deep', engine: 'claude', model: 'opus', effort: null },
      // overridden row — the owner pinned it at the readout; MUST freeze to A.
      { phase: 'review-plan', role: 'reviewer', kind: 'review', engine: 'cursor', model: 'sonnet', effort: 'composer', overridden: true },
      // orchestration row (FR-3) — excluded; the run inherits live config B.
      { phase: 'test-pilot', role: 'orchestrator', kind: 'orchestration', engine: 'claude', model: null, effort: null },
      // unavailable row (UFR-2) — no snapshot value; excluded, resolves live from config B.
      { phase: 'tasks', role: 'author', kind: 'author', unavailable: true },
      // unrecognized row (UFR-5) — raw unvalidated engine; excluded, left live for config B.
      { phase: 'ship', role: 'fixer', kind: 'fix', engine: 'weirdengine', model: 'sonnet', effort: 'low', unrecognized: true, overridden: true },
    ],
  }
  // Config B — the DIFFERENT live config presented after the readout was confirmed (the edit-window leak).
  const configBOverrides = { author: 'haiku', builder: 'haiku', 'reviewer-deep': 'haiku', reviewer: 'haiku', fixer: 'haiku' }
  const configBEnginePrefs = { reviewer: 'claude', implementation: 'claude', effort: { review: 'medium', 'review-deep': 'medium', build: 'medium', fix: 'medium' } }
  const frozenMerge = sr.mergeFrozenSnapshot(snapshotA, configBOverrides, configBEnginePrefs)

  // Concrete rows freeze to A (NOT config B) — the mutation `if (!row.overridden) continue` fails here.
  assert.strictEqual(frozenMerge.overrides.builder, 'opus', 'builder (plain row) freezes A model, not B')
  assert.strictEqual(frozenMerge.overrides['reviewer-deep'], 'opus', 'reviewer-deep (plain row) freezes A model, not B')
  assert.strictEqual(frozenMerge.enginePrefs.implementation, 'codex', 'builder (plain row) freezes A engine, not B')
  assert.strictEqual(frozenMerge.enginePrefs.effort.build, 'high', 'builder (plain row) freezes A effort, not B')
  // The overridden row also freezes to A.
  assert.strictEqual(frozenMerge.overrides.reviewer, 'sonnet', 'overridden reviewer freezes A model')
  assert.strictEqual(frozenMerge.enginePrefs.reviewer, 'cursor', 'overridden reviewer freezes A engine')
  assert.strictEqual(frozenMerge.enginePrefs.effort.review, 'composer', 'overridden reviewer freezes A effort')

  // Excluded rows keep config B (live) values — never frozen from A.
  // author: only the `unavailable` row named it, so no pin -> config B's author survives.
  assert.strictEqual(frozenMerge.overrides.author, 'haiku', 'unavailable row leaves author live (config B)')
  // reviewer-deep effort came from B (the A review-deep row had null effort -> no pin).
  assert.strictEqual(frozenMerge.enginePrefs.effort['review-deep'], 'medium', 'null-effort A row leaves effort live (config B)')
  // unrecognized fixer: the raw engine is NOT frozen, so the fix engine (implementation) stays the
  // builder-frozen codex — and its model/effort are NOT pinned from the unrecognized row.
  assert.strictEqual(frozenMerge.enginePrefs.effort.fix, 'medium', 'unrecognized row leaves fix effort live (config B)')
  assert.strictEqual(frozenMerge.overrides.fixer, 'haiku', 'unrecognized row leaves fixer model live (config B)')
  // orchestration is session-inherited: no orchestrator key is ever written.
  assert.ok(!Object.prototype.hasOwnProperty.call(frozenMerge.overrides, 'orchestrator'),
    'orchestration row must never seed a model pin (session-inherited, FR-3)')

  // FR-4 fallback row (isolated, so the shared implementation key has no competing build row): the
  // EFFECTIVE engine 'claude' is frozen onto implementation, never the unauthorized target 'codex';
  // the model still freezes to A (valid for Claude dispatch); and the target-engine effort is NOT
  // pinned (Claude dispatch has null effort → the fix effort stays live from config B).
  const fbOnly = sr.mergeFrozenSnapshot(
    { version: V, phases: [{ phase: 'ship', role: 'fixer', kind: 'fix', engine: 'codex', model: 'opus', effort: 'low', fallbackToClaude: true }] },
    { fixer: 'sonnet' }, { reviewer: 'claude', implementation: 'codex', effort: { fix: 'medium' } })
  assert.strictEqual(fbOnly.enginePrefs.implementation, 'claude',
    'a fallback row freezes the EFFECTIVE engine claude onto implementation, never the unauthorized target codex')
  assert.strictEqual(fbOnly.overrides.fixer, 'opus', 'fallback row still freezes A model (valid for Claude)')
  assert.strictEqual(fbOnly.enginePrefs.effort.fix, 'medium',
    'fallback row must not pin the target engine effort (Claude effort is null) — the fix effort stays live')

  // ── B (migration gate): a snapshot whose `version` != READOUT_VERSION is IGNORED entirely; the run
  // falls through to live config (the documented rollback state) — zero pins. This is what makes a
  // pre-fix persisted snapshot (written before the widened exclusions / set validation) safe: it can
  // never be re-interpreted by the widened merge. Mutation killed: dropping the version gate lets the
  // old-version rows pin (builder would freeze to 'opus' instead of staying live 'haiku').
  const staleSnap = {
    version: V - 1,   // an EARLIER commit's format
    phases: [{ phase: 'workhorse', role: 'builder', kind: 'build', engine: 'codex', model: 'opus', effort: 'high' }],
  }
  const staleMerge = sr.mergeFrozenSnapshot(staleSnap, { builder: 'haiku' },
    { reviewer: 'claude', implementation: 'claude', effort: {} })
  assert.strictEqual(staleMerge.pinnedCount, 0, 'a stale-version snapshot pins nothing (version-gated)')
  assert.strictEqual(staleMerge.overrides.builder, 'haiku', 'a stale-version snapshot leaves the model live (config passthrough)')
  assert.strictEqual(staleMerge.enginePrefs.implementation, 'claude', 'a stale-version snapshot leaves the engine live')
  assert.ok(/version/.test(staleMerge.reason || ''), 'the version-gate reason names the version mismatch')
  // A snapshot with NO version field is treated the same (stale — ignored).
  const noVer = sr.mergeFrozenSnapshot({ phases: staleSnap.phases }, { builder: 'haiku' },
    { reviewer: 'claude', implementation: 'claude', effort: {} })
  assert.strictEqual(noVer.pinnedCount, 0, 'a version-less snapshot is ignored (treated stale)')
  assert.strictEqual(noVer.overrides.builder, 'haiku', 'a version-less snapshot leaves the model live')

  // ── C (merge set validation): a row whose model/engine is outside the producer's accepted sets is
  // NOT pinned (live fallback), while its VALID siblings in the same snapshot ARE. Mutation killed:
  // dropping the KNOWN_MODELS/ENGINES membership check lets 'gpt-9-turbo'/'grok' reach the resolvers.
  const badValues = {
    version: V,
    phases: [
      // invalid model on a valid role — model NOT pinned; but its engine (codex, valid) IS pinned.
      { phase: 'workhorse', role: 'builder', kind: 'build', engine: 'codex', model: 'gpt-9-turbo',
        engineModel: 'gpt-5.6-sol', effort: 'high' },
      // invalid engine on a review row — engine NOT pinned; its model (valid) IS pinned.
      { phase: 'review-plan', role: 'reviewer', kind: 'review', engine: 'grok', model: 'sonnet', effort: 'high' },
    ],
  }
  const bad = sr.mergeFrozenSnapshot(badValues, { builder: 'opus', reviewer: 'opus' },
    { reviewer: 'claude', implementation: 'claude', effort: {} })
  assert.strictEqual(bad.overrides.builder, 'opus', 'an out-of-set model (gpt-9-turbo) is NOT pinned — the role stays live')
  assert.strictEqual(bad.enginePrefs.implementation, 'codex', 'the valid sibling engine (codex) still pins')
  assert.strictEqual(bad.enginePrefs.reviewer, 'claude', 'an out-of-set engine (grok) is NOT pinned — the reviewer engine stays live (claude)')
  assert.strictEqual(bad.overrides.reviewer, 'sonnet', 'the valid sibling model (sonnet) on the grok row still pins')

  // ── F (synthesis pin flows end-to-end): a synthesis row (native Claude, model on the synthesis tier)
  // now pins its model into __SR_OVERRIDES['synthesis'] — making commit 025ed7f's _TIER_ROLE.synthesis
  // pin branch live. Engine is 'claude' (loop-owned), so no engine pin; the MODEL freezes.
  const synthSnap = {
    version: V,
    phases: [{ phase: 'review-code', role: 'synthesis', kind: 'synthesis', engine: 'claude', model: 'sonnet', effort: null }],
  }
  const synthMerge = sr.mergeFrozenSnapshot(synthSnap, { synthesis: 'opus' },
    { reviewer: 'claude', implementation: 'claude', effort: {} })
  assert.strictEqual(synthMerge.overrides.synthesis, 'sonnet', 'a synthesis row freezes its model onto the synthesis tier pin')
  assert.strictEqual(modelTier.resolveModel('synthesis', synthMerge.overrides, null), 'sonnet',
    'the frozen synthesis pin resolves through model_tier (the review-code synthesis dispatch reads it via _TIER_ROLE.synthesis)')

  // ── D (no-apply signal at the merge layer): a present-but-empty-pins snapshot carries a reason so
  // the caller can narrate. (The caller-side log line is covered by the run_overrides_present flag +
  // the startup smoke; here we assert the merge exposes the pinnedCount/reason the caller keys on.)
  const allExcluded = sr.mergeFrozenSnapshot(
    { version: V, phases: [{ phase: 'test-pilot', role: 'orchestrator', kind: 'orchestration', model: 'opus' }] },
    { author: 'opus' }, { reviewer: 'claude', implementation: 'claude', effort: {} })
  assert.strictEqual(allExcluded.pinnedCount, 0, 'an all-excluded snapshot pins nothing')
  assert.ok(allExcluded.reason, 'an all-excluded present snapshot records a no-pin reason for the caller log')

  console.log('showrunner_preflight_freeze_smoke ok')
}
main().catch((e) => { console.error(e); process.exit(1) })
