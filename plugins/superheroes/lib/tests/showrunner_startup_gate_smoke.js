// plugins/superheroes/lib/tests/showrunner_startup_gate_smoke.js
// #115 Task 12: reconcile() uses exec; readStartupState uses the folded startup courier leaf.
// Release-on-park: a terminal park RELEASES the work-item lease (CAS on our generation) so a
// relaunch never waits out DEFAULT_TTL; a run that never acquired (generation null, e.g. a
// lease-held park) must NOT issue a release.
const assert = require('assert')

function jsonOut(obj) { return [{ ok: true, stdout: JSON.stringify(obj) }] }

const WORLD = { store_ok: true, current_content_hash: null, pr: null, seeded_empty: true }

function agentFor(generation, releaseCalls) {
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'exec') {
      if (prompt.includes('recover_entry')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ checkpoint: null, world: WORLD, generation }) }]
      }
      if (prompt.includes('fence_cli.py') && prompt.includes('--release')) {
        releaseCalls.push(prompt)
        return [{ index: 0, ok: true, stdout: '{"ok":true,"reason":"lease released"}' }]
      }
      if (prompt.includes('read-gate')) return [{ index: 0, ok: true, stdout: '{"review":"pending"}' }]
    }
    if (label === 'read startup state') {
      return jsonOut({ ok: true, spec_gate: 'pending', model_overrides: {}, doc_dir: '' })
    }
    throw new Error('unexpected agent: ' + label + ' ' + prompt.slice(0, 40))
  }
}

global.log = () => {}
const { showrunner } = require('../showrunner.js')
;(async () => {
  // (a) unapproved spec parks; no lease was acquired (generation null) -> no release attempt.
  let releaseCalls = []
  global.agent = agentFor(null, releaseCalls)
  let out = await showrunner({ workItem: 'wi' })
  assert.strictEqual(out.outcome, 'parked')
  assert.strictEqual(out.phase, 'startup')
  assert.ok(/pending/.test(out.reason))
  assert.strictEqual(releaseCalls.length, 0, 'no lease held -> no release exec')

  // (b) same park with a HELD lease (generation 3) -> exactly one CAS release at the exit.
  releaseCalls = []
  global.agent = agentFor(3, releaseCalls)
  out = await showrunner({ workItem: 'wi' })
  assert.strictEqual(out.outcome, 'parked')
  assert.strictEqual(releaseCalls.length, 1, 'a terminal park must release the held lease')
  assert.ok(releaseCalls[0].includes("--generation '3'"), 'release carries OUR generation (CAS)')
  assert.ok(releaseCalls[0].includes("--work-item 'wi'"))

  console.log('OK: UFR-1 — unapproved (pending) spec refuses to run; park releases a held lease')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
