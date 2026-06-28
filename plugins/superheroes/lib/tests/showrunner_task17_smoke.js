// plugins/superheroes/lib/tests/showrunner_task17_smoke.js
// TDD smoke for Task 17 (#115): startup overrides read + unconditional cheapest dumb-pipe pin.
//
// Assertions:
//   (a) startup: showrunner() issues an exec that calls model_tier_overrides.py, and the
//       parsed {role:model} map lands on globalThis.__SR_OVERRIDES; authorModel() resolves
//       through it (a concrete override like {author:'haiku'} must come back as 'haiku').
//   (b) bundle wrapper: a dumb-pipe leaf (label='exec' or label='io') ALWAYS receives
//       the cheapest model (DEFAULT_TIERS.mechanical = 'haiku') even when __SR_LEAF_MODEL
//       is set to something else (e.g. 'sonnet'). A non-dumb leaf ('lib', 'reviewer', etc.)
//       DOES get __SR_LEAF_MODEL when set.
//
// For (b): the wrapper lives in the bundle's PREAMBLE, not in showrunner.js. We evaluate the
// bundle in a vm sandbox (as showrunner_bundle_smoke.js does) and call globalThis.agent()
// directly to observe the model that is handed to the real underlying agent.
'use strict'
const assert = require('assert')
const fs = require('fs')
const path = require('path')
const vm = require('vm')

// ---------------------------------------------------------------------------
// PART A: showrunner() startup plants __SR_OVERRIDES via exec(model_tier_overrides.py)
// ---------------------------------------------------------------------------
const sr = require('../showrunner.js')
const modelTier = require('../model_tier.js')

async function partA() {
  // Track agent calls to find the overrides exec
  const calls = []
  const savedOverrides = globalThis.__SR_OVERRIDES
  delete globalThis.__SR_OVERRIDES

  globalThis.agent = async function(prompt, opts) {
    calls.push({ prompt, opts: opts || {}, label: (opts && opts.label) || '' })
    const label = (opts && opts.label) || ''
    if (label === 'exec') {
      if (typeof prompt === 'string' && prompt.includes('recover_entry.py')) {
        // reconcile: return empty snapshot -> world_derive -> proceed
        return [{ index: 0, ok: true, stdout: '{}' }]
      }
      if (typeof prompt === 'string' && prompt.includes('definition_doc.py read-gate')) {
        // readGate for spec: 'passed'
        return [{ index: 0, ok: true, stdout: '{"review":"passed"}' }]
      }
      if (typeof prompt === 'string' && prompt.includes('model_tier_overrides.py')) {
        // The startup overrides read — return a concrete override so we can verify authorModel.
        return [{ index: 0, ok: true, stdout: '{"author":"haiku"}' }]
      }
      // Any other exec: ok
      return [{ index: 0, ok: true, stdout: '{}' }]
    }
    // Park everything else (workhorse, etc.)
    return null
  }
  globalThis.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
  globalThis.log = () => {}

  // Run showrunner; it will reconcile -> readGate(spec) -> (startup overrides read) -> runPhases
  // runPhases will park (all phases return null from agent stub) but the overrides exec must have fired.
  try {
    await sr.showrunner({ workItem: 'wi-t17' })
  } catch (_) {
    // park or exception is fine; we just want to verify the overrides exec was issued
  }

  // (a1) There must be an exec call that contains 'model_tier_overrides.py'
  const ovCall = calls.find(
    (c) => c.label === 'exec' && c.prompt.includes('model_tier_overrides.py'),
  )
  assert.ok(ovCall, 'FAIL (a1): startup did not issue an exec containing model_tier_overrides.py')

  // (a2) globalThis.__SR_OVERRIDES must be set to the parsed {role:model} map
  assert.ok(
    globalThis.__SR_OVERRIDES && typeof globalThis.__SR_OVERRIDES === 'object',
    'FAIL (a2): globalThis.__SR_OVERRIDES was not set by the startup overrides exec',
  )
  assert.strictEqual(
    globalThis.__SR_OVERRIDES.author,
    'haiku',
    'FAIL (a2): __SR_OVERRIDES does not carry the parsed author override',
  )

  // (a3) authorModel() resolves through __SR_OVERRIDES (should return 'haiku' from the override)
  const am = sr.authorModel()
  assert.strictEqual(am, 'haiku', 'FAIL (a3): authorModel() did not resolve through __SR_OVERRIDES')

  // (a4) fail-safe: if the overrides exec returns invalid JSON, __SR_OVERRIDES must be {} (not crash)
  globalThis.__SR_OVERRIDES = undefined
  calls.length = 0
  let savedAgent = globalThis.agent
  globalThis.agent = async function(prompt, opts) {
    const label = (opts && opts.label) || ''
    if (label === 'exec') {
      if (typeof prompt === 'string' && prompt.includes('model_tier_overrides.py')) {
        return [{ index: 0, ok: false, stdout: 'not-json' }]
      }
      if (typeof prompt === 'string' && prompt.includes('recover_entry.py')) {
        return [{ index: 0, ok: true, stdout: '{}' }]
      }
      if (typeof prompt === 'string' && prompt.includes('definition_doc.py read-gate')) {
        return [{ index: 0, ok: true, stdout: '{"review":"passed"}' }]
      }
      return [{ index: 0, ok: true, stdout: '{}' }]
    }
    return null
  }
  try {
    await sr.showrunner({ workItem: 'wi-t17-fail' })
  } catch (_) {}
  assert.ok(
    globalThis.__SR_OVERRIDES !== undefined && typeof globalThis.__SR_OVERRIDES === 'object',
    'FAIL (a4): __SR_OVERRIDES was not set to {} on a failed/invalid overrides exec (should fail-safe)',
  )
  assert.strictEqual(
    Object.keys(globalThis.__SR_OVERRIDES).length,
    0,
    'FAIL (a4): __SR_OVERRIDES should be {} (empty) on invalid exec response, not crash',
  )
  globalThis.agent = savedAgent

  // Restore
  globalThis.__SR_OVERRIDES = savedOverrides
  console.log('OK (a): startup plants __SR_OVERRIDES via exec(model_tier_overrides.py); authorModel() threads it; fail-safe {} on bad parse')
}

// ---------------------------------------------------------------------------
// PART B: bundle wrapper — dumb-pipe (exec/io) always cheapest; smart gets __SR_LEAF_MODEL
// ---------------------------------------------------------------------------
async function partB() {
  const bundlePath = path.join(__dirname, '..', 'showrunner.bundle.js')
  let text = fs.readFileSync(bundlePath, 'utf8').replace(/export\s+const\s+meta/, 'const meta')

  // Track what model the real underlying agent receives for each label
  const received = []
  const sandbox = {
    console,
    args: JSON.stringify({ workItem: 'b-probe', model: 'sonnet' }),
    process: { env: {}, cwd: () => '/' },
  }
  sandbox.globalThis = sandbox
  sandbox.global = sandbox
  sandbox.agent = async function(prompt, opts) {
    received.push({ label: opts && opts.label, model: opts && opts.model })
    throw new Error('STOP')  // stop after first real agent call
  }
  sandbox.parallel = async (thunks) => Promise.all((thunks || []).map((f) => f()))
  sandbox.log = () => {}
  vm.createContext(sandbox)

  // Load the bundle with __SR_RUN=false so the ENTRY does not run the showrunner; just set up globals.
  vm.runInContext('globalThis.__SR_RUN = false;\n;(async () => {\n' + text + '\n})();', sandbox, { timeout: 5000 })

  // Now manually set __SR_LEAF_MODEL to 'sonnet' (as if args.model='sonnet' was passed)
  sandbox.globalThis.__SR_LEAF_MODEL = 'sonnet'
  const cheapest = modelTier.DEFAULT_TIERS.mechanical  // 'haiku'

  // (b1) Call globalThis.agent with label='exec' -> wrapper must pass cheapest to __realAgent
  received.length = 0
  try { await sandbox.globalThis.agent('test exec cmd', { label: 'exec', model: cheapest }) } catch (_) {}
  assert.ok(received.length > 0, 'FAIL (b1): no call to underlying agent for exec label')
  assert.strictEqual(
    received[0].model,
    cheapest,
    `FAIL (b1): exec leaf model must be cheapest ('${cheapest}'), got '${received[0].model}' — __SR_LEAF_MODEL should NOT override exec`,
  )

  // (b2) Call globalThis.agent with label='io' -> wrapper must pass cheapest to __realAgent
  received.length = 0
  try { await sandbox.globalThis.agent('test io cmd', { label: 'io', model: cheapest }) } catch (_) {}
  assert.ok(received.length > 0, 'FAIL (b2): no call to underlying agent for io label')
  assert.strictEqual(
    received[0].model,
    cheapest,
    `FAIL (b2): io leaf model must be cheapest ('${cheapest}'), got '${received[0].model}' — __SR_LEAF_MODEL should NOT override io`,
  )

  // (b3) Call globalThis.agent with label='lib' (non-dumb) -> wrapper must apply __SR_LEAF_MODEL
  received.length = 0
  try { await sandbox.globalThis.agent('test lib cmd', { label: 'lib' }) } catch (_) {}
  assert.ok(received.length > 0, 'FAIL (b3): no call to underlying agent for lib label')
  assert.strictEqual(
    received[0].model,
    'sonnet',
    `FAIL (b3): lib leaf model must be __SR_LEAF_MODEL='sonnet', got '${received[0].model}'`,
  )

  // (b4) No __SR_LEAF_MODEL set: non-dumb leaf should NOT have model forced
  sandbox.globalThis.__SR_LEAF_MODEL = null
  received.length = 0
  try { await sandbox.globalThis.agent('test lib no-override', { label: 'reviewer:r1' }) } catch (_) {}
  assert.ok(received.length > 0, 'FAIL (b4): no call to underlying agent for reviewer label')
  // Without __SR_LEAF_MODEL, the model in opts should be undefined (not set by caller, not overridden)
  assert.ok(
    received[0].model === undefined || received[0].model === null,
    `FAIL (b4): without __SR_LEAF_MODEL, non-dumb leaf should have no model override, got '${received[0].model}'`,
  )

  // (b5) Even with no opts at all, exec label should still get cheapest
  sandbox.globalThis.__SR_LEAF_MODEL = 'sonnet'
  received.length = 0
  try { await sandbox.globalThis.agent('test exec no-opts', { label: 'exec' }) } catch (_) {}
  assert.ok(received.length > 0, 'FAIL (b5): no call to underlying agent for exec with no opts')
  assert.strictEqual(
    received[0].model,
    cheapest,
    `FAIL (b5): exec with no prior model in opts must still get cheapest ('${cheapest}'), got '${received[0].model}'`,
  )

  console.log('OK (b): bundle wrapper — exec/io always cheapest regardless of __SR_LEAF_MODEL; non-dumb gets __SR_LEAF_MODEL')
}

;(async () => {
  await partA()
  await partB()
  console.log('OK: Task 17 — startup __SR_OVERRIDES + unconditional cheapest dumb-pipe (bundle wrapper)')
})().catch((e) => { console.error('FAIL:', e.message || e, e.stack); process.exit(1) })
