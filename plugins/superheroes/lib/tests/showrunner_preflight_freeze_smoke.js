const assert = require('assert')
const modelTier = require('../model_tier.js')
const enginePref = require('../engine_pref.js')
const sr = require('../showrunner.js')

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
    phases: [
      { phase: 'plan', role: 'author', kind: 'author', model: 'sonnet', overridden: true },
      { phase: 'review-plan', role: 'reviewer', kind: 'review', engine: 'codex', effort: 'xhigh', overridden: true },
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

  // Behavior-preserving: no frozen snapshot -> the maps are returned unchanged (the rollback state).
  const passthrough = sr.mergeFrozenSnapshot(null, baseOv, baseEp)
  assert.deepStrictEqual(passthrough.overrides, baseOv, 'no snapshot -> config-derived overrides unchanged')
  assert.deepStrictEqual(passthrough.enginePrefs, baseEp, 'no snapshot -> config-derived engine prefs unchanged')

  // A role NOT named by any snapshot row keeps its config-derived value (the freeze only touches
  // roles the snapshot actually rendered a row for).
  const partial = { phases: [{ phase: 'review-plan', role: 'reviewer', kind: 'review', engine: 'codex', overridden: true }] }
  const m2 = sr.mergeFrozenSnapshot(partial, { author: 'opus' }, { reviewer: 'claude', implementation: 'claude', effort: {} })
  assert.strictEqual(m2.overrides.author, 'opus', 'a role absent from the snapshot keeps its config-derived model')
  assert.strictEqual(m2.enginePrefs.reviewer, 'codex', 'the pinned reviewer engine is applied')

  // Empty snapshot ({phases: []}) passes config through unchanged (backward-compat invariant).
  const emptySnap = sr.mergeFrozenSnapshot({ phases: [] }, baseOv, baseEp)
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
    phases: [
      // plain (non-overridden) rows — displayed A's concrete values; MUST freeze to A.
      { phase: 'workhorse', role: 'builder', kind: 'build', engine: 'codex', model: 'opus', effort: 'high' },
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
    { phases: [{ phase: 'ship', role: 'fixer', kind: 'fix', engine: 'codex', model: 'opus', effort: 'low', fallbackToClaude: true }] },
    { fixer: 'sonnet' }, { reviewer: 'claude', implementation: 'codex', effort: { fix: 'medium' } })
  assert.strictEqual(fbOnly.enginePrefs.implementation, 'claude',
    'a fallback row freezes the EFFECTIVE engine claude onto implementation, never the unauthorized target codex')
  assert.strictEqual(fbOnly.overrides.fixer, 'opus', 'fallback row still freezes A model (valid for Claude)')
  assert.strictEqual(fbOnly.enginePrefs.effort.fix, 'medium',
    'fallback row must not pin the target engine effort (Claude effort is null) — the fix effort stays live')

  console.log('showrunner_preflight_freeze_smoke ok')
}
main().catch((e) => { console.error(e); process.exit(1) })
