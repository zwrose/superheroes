// plugins/superheroes/lib/tests/showrunner_workhorse_park_release_smoke.js
// Workhorse parks (e.g. UFR-7 trailer check) must release the run lease via runPhases'
// release-on-park path — not only showrunner()'s finally — so a relaunch never waits TTL.
const assert = require('assert')
global.log = () => {}

function agentFor(generation, releaseCalls) {
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'save phase progress') {
      return JSON.stringify({ ok: true, journal_confirmed: true })
    }
    if (label === 'release lease') {
      assert.ok(prompt.includes('fence_cli.py') && prompt.includes('--release'))
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
