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

  // FR-8: the spine exposes a mergeFrozenSnapshot helper that folds the frozen snapshot's pinned
  // per-role values over the config-derived maps — a pinned role wins, an unpinned role keeps the
  // config-derived (resolve-live) value.
  assert.strictEqual(typeof sr.mergeFrozenSnapshot, 'function',
    'showrunner must export mergeFrozenSnapshot (the pin-or-resolve fork)')
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

  // An unpinned role keeps its config-derived value (only-pins-win merge).
  const partial = { phases: [{ phase: 'review-plan', role: 'reviewer', kind: 'review', engine: 'codex', overridden: true }] }
  const m2 = sr.mergeFrozenSnapshot(partial, { author: 'opus' }, { reviewer: 'claude', implementation: 'claude', effort: {} })
  assert.strictEqual(m2.overrides.author, 'opus', 'an unpinned role keeps its config-derived model')
  assert.strictEqual(m2.enginePrefs.reviewer, 'codex', 'the pinned reviewer engine is applied')

  console.log('showrunner_preflight_freeze_smoke ok')
}
main().catch((e) => { console.error(e); process.exit(1) })
