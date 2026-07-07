// plugins/superheroes/lib/tests/showrunner_reconcile_smoke.js
// #115 Task 12: reconcile() gathers the world snapshot via runCourierMarkedText (label='gather
// snapshot', #218 __SR_EXIT marker protocol), parses stdout JSON, then calls the JS twin in-process.
// The LLM-dispatched cmdRunner (label='lib') for recover_entry is GONE.
require('./_smoke_checkout_root.js')
const assert = require('assert')
global.log = () => {}

const CHECKOUT_ROOT = globalThis.__SR_ROOT

// Stub exec: when reconcile runs, it calls exec(['python3 .../recover_entry.py --work-item wi --snapshot']).
// exec returns [{ok: true, stdout: <JSON>}]. The snapshot JSON drives the JS twin.
const snapshots = {
  // Scenario: store unusable — the Python entry park_gate is returned directly (early_park or a
  // store_ok=false world); simulated as a snapshot with world.store_ok=false.
  park_gate: JSON.stringify({ checkpoint: null, world: { store_ok: false }, generation: 'g1' }),
  // Scenario: no checkpoint -> world_derive
  world_derive: JSON.stringify({
    checkpoint: null,
    world: { store_ok: true, current_content_hash: null, pr: null, seeded_empty: true },
    generation: 'g2', root: CHECKOUT_ROOT,
  }),
  // Scenario: valid checkpoint -> continue
  continue: JSON.stringify({
    checkpoint: { lastGoodStep: 2, lastGoodPhase: 'tasks' },
    world: { store_ok: true, current_content_hash: null, pr: null, seeded_empty: true },
    generation: 'g3', root: CHECKOUT_ROOT,
  }),
  missing_root: JSON.stringify({
    checkpoint: null,
    world: { store_ok: true, current_content_hash: null, pr: null, seeded_empty: true },
    generation: 'g4',
  }),
}

function marked(stdout) {
  return String(stdout) + (String(stdout).includes('__SR_EXIT') ? '' : '\n__SR_EXIT:0')
}

global.agent = async (prompt, opts) => {
  throw new Error('unexpected agent call (reconcile must use marked courier, not cmdRunner): ' + prompt.slice(0, 60))
}
global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))

const { reconcile } = require('../showrunner.js')

;(async () => {
  // (a) store unusable -> park_gate via twin (world.store_ok === false)
  global.agent = async (prompt, opts) => {
    return marked(snapshots.park_gate)
  }
  const r1 = await reconcile('wi')
  assert.strictEqual(r1.action, 'park_gate', 'store unusable -> park_gate (twin decided)')
  assert.strictEqual(r1.generation, 'g1', 'generation threaded from snapshot')

  // (b) no checkpoint -> world_derive (twin decides)
  global.agent = async (prompt, opts) => {
    return marked(snapshots.world_derive)
  }
  const r2 = await reconcile('wi')
  assert.strictEqual(r2.action, 'world_derive', 'no checkpoint -> world_derive (twin decided)')
  assert.strictEqual(r2.generation, 'g2', 'generation threaded from snapshot')
  assert.strictEqual(r2.root, CHECKOUT_ROOT, 'checkout root threaded from snapshot')

  // (c) valid checkpoint -> continue (twin decides)
  global.agent = async (prompt, opts) => {
    return marked(snapshots.continue)
  }
  const r3 = await reconcile('wi')
  assert.strictEqual(r3.action, 'continue', 'valid checkpoint -> continue (twin decided)')
  assert.strictEqual(r3.from_step, 2, 'from_step threaded from checkpoint.lastGoodStep')
  assert.strictEqual(r3.generation, 'g3', 'generation threaded from snapshot')
  assert.strictEqual(r3.root, CHECKOUT_ROOT, 'checkout root threaded from snapshot')

  // (d) missing checkout root in snapshot -> park_gate (fail closed)
  global.agent = async () => marked(snapshots.missing_root)
  const rMissing = await reconcile('wi')
  assert.strictEqual(rMissing.action, 'park_gate')
  assert.ok(/missing checkout root/.test(rMissing.reason))

  // (e) reconcile must ride the dumb-pipe marked courier (descriptive label 'gather snapshot' +
  // courier:true + agentType superheroes:courier), NOT a cmdRunner 'lib' leaf.
  let agentLabel = null
  let agentCourier = null
  let agentType = null
  global.agent = async (prompt, opts) => {
    agentLabel = (opts && opts.label) || ''
    agentCourier = !!(opts && opts.courier)
    agentType = (opts && opts.agentType) || null
    return marked(snapshots.world_derive)
  }
  await reconcile('wi')
  assert.strictEqual(agentLabel, 'gather snapshot', "reconcile's gather leaf carries the descriptive 'gather snapshot' label, NOT 'lib'")
  assert.strictEqual(agentCourier, true, 'reconcile rides the dumb-pipe courier (courier:true -> cheapest model)')
  assert.strictEqual(agentType, 'superheroes:courier', 'reconcile gather snapshot rides the lean courier agent (#218)')

  // (f) marker-less courier transport exhaustion -> generic IO park (not libRoot-named).
  let transportCalls = 0
  global.agent = async () => {
    transportCalls += 1
    return snapshots.world_derive
  }
  const rTransport = await reconcile('wi')
  assert.strictEqual(rTransport.action, 'park_gate', 'missing marker fails closed to park_gate')
  assert.strictEqual(rTransport.reason, 'recover_entry snapshot failed (IO error)',
    'marker-less transport exhaustion maps to generic IO error, not libRoot park')
  assert.strictEqual(transportCalls, 6, 'reconcile exhausts 2 attempts × 3 dispatchMarked tries')

  console.log('OK: reconcile uses marked courier+JS twin, not cmdRunner; generation threaded correctly')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
