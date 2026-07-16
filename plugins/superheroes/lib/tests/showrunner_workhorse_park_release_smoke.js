// plugins/superheroes/lib/tests/showrunner_workhorse_park_release_smoke.js
// Workhorse parks (e.g. UFR-7 trailer check) must release the run lease via runPhases'
// release-on-park path — targeting the acquire-authority store via --root (and cd when set).
require('./_smoke_checkout_root.js')
const assert = require('assert')
const { markedStdout, saveProgressOk } = require('./_marked_stdout.js')
global.log = () => {}

const CHECKOUT_ROOT = globalThis.__SR_ROOT

function agentFor(generation, releaseCalls) {
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    // #434: a park now seeds a resume-continuing per-leg idem nonce before the save.
    if (label === 'phase leg seed') return markedStdout({ ok: true, max: 0 })
    if (label === 'save phase progress') {
      return saveProgressOk({ checkpoint_confirmed: false })
    }
    if (label === 'release lease') {
      assert.ok(prompt.includes('fence_cli.py') && prompt.includes('--release'))
      assert.ok(prompt.includes('--root'), 'release must carry --root for store keying')
      assert.ok(
        prompt.includes(`--root '${CHECKOUT_ROOT}'`) || prompt.startsWith("cd '"),
        'release must target the acquire-authority checkout root',
      )
      releaseCalls.push(prompt)
      return JSON.stringify({ ok: true, reason: 'lease released' })
    }
    throw new Error('unexpected agent: ' + label + ' ' + String(prompt).slice(0, 60))
  }
}

const sr = require('../showrunner.js')
;(async () => {
  const releaseCalls = []
  global.agent = agentFor(7, releaseCalls)
  const idx = sr.PHASES.indexOf('workhorse')
  const out = await sr.runPhases('wi', idx, {
    generation: 7,
    root: CHECKOUT_ROOT,
    build: async () => ({
      confidence: 'low',
      assumptions: ['a commit lacks its Task-Id trailer — park (UFR-7)'],
      parkReason: 'a commit lacks its Task-Id trailer — park (UFR-7)',
    }),
  })
  assert.strictEqual(out.outcome, 'parked')
  assert.strictEqual(out.phase, 'workhorse')
  assert.ok(/Task-Id/.test(out.reason))
  assert.strictEqual(releaseCalls.length, 1, 'workhorse park must release the held lease')
  assert.ok(releaseCalls[0].includes("--generation '7'"))
  console.log('ok: workhorse park releases the run lease')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
