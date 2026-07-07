// plugins/superheroes/lib/tests/showrunner_startup_gate_smoke.js
// #115 Task 12: reconcile() uses exec; readStartupState uses the folded startup courier leaf.
// Release-on-park: a terminal park RELEASES the work-item lease (CAS on our generation) so a
// relaunch never waits out DEFAULT_TTL; a run that never acquired (generation null, e.g. a
// lease-held park) must NOT issue a release.
require('./_smoke_checkout_root.js')
const assert = require('assert')
const { markedStdout } = require('./_marked_stdout.js')

const CHECKOUT_ROOT = globalThis.__SR_ROOT

function jsonOut(obj) { return [{ ok: true, stdout: JSON.stringify(obj) }] }

const WORLD = { store_ok: true, current_content_hash: null, pr: null, seeded_empty: true }

function agentFor(generation, releaseCalls) {
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (opts && opts.courier) {
      if (prompt.includes('recover_entry')) {
        return markedStdout({
          checkpoint: null, world: WORLD, generation, root: CHECKOUT_ROOT,
        })
      }
      if (prompt.includes('read-gate')) return [{ index: 0, ok: true, stdout: '{"review":"pending"}' }]
    }
    // BUG C: the lease release rides a DEDICATED single-command hardened courier (label
    // 'release lease'), NOT the permissive batch exec that let a haiku improvise unscripted Bash
    // and manually release the lease live (2026-07-02). Its prompt must forbid extra commands and
    // it returns a require()-validated JSON object.
    if (label === 'release lease') {
      assert.ok(prompt.includes('fence_cli.py') && prompt.includes('--release'),
        'the release runs the scripted release command')
      assert.ok(prompt.includes('--root'), 'release must carry --root for store keying')
      assert.ok(/do not run any other command/i.test(prompt),
        'the release prompt forbids extra commands (no improvising)')
      releaseCalls.push(prompt)
      return [{ ok: true, stdout: '{"ok":true,"reason":"lease released"}' }]
    }
    if (label === 'read startup state') {
      return [{ ok: true, stdout: markedStdout({ ok: true, spec_gate: 'pending', model_overrides: {}, doc_dir: '' }) }]
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
  assert.strictEqual(releaseCalls.length, 0, 'no lease held -> no release courier')

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
