// Smoke: reviewDocPhase maps a #104 terminal -> gate, short-circuits when the gate is already
// passed (idempotent passed-gate skip), and parks on a failed gate write (UFR-5). Stubs the leaves.
const assert = require('assert')
const sr = require('../showrunner.js')

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}

function makeAgent({ gate, terminal, setGateFails }) {
  let panelRuns = 0
  const fn = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'resume') return '1'
    if (label === 'lib') {
      if (prompt.includes('read-gate')) return { review: gate }
      if (prompt.includes('gate-for-terminal')) return { gate: terminal === 'clean' ? 'passed' : 'changes-requested' }
      if (prompt.includes('set-gate')) {
        if (setGateFails) return { review: 'pending', status: 'in-review' }   // write did not record the gate
        const m = prompt.match(/--review '([^']+)'/); return { review: m ? m[1] : 'passed', status: 'approved' }
      }
      return { ok: true }
    }
    if (label.endsWith('-reviewer')) { panelRuns += 1; return null }
    if (label.startsWith('synthesis')) return { findings: [], drops: [] }
    if (label.startsWith('tally')) return { schemaVersion: 1, terminal, gate: 'clean' }
    return null
  }
  fn.panelRuns = () => panelRuns
  return fn
}

async function main() {
  // (a) gate already passed -> skip the panel entirely, return passed.
  let ag = makeAgent({ gate: 'passed', terminal: 'clean' })
  global.agent = ag
  let r = await sr.reviewDocPhase('plan', 'wi')
  assert.strictEqual(r.gate, 'passed', 'already-passed gate -> passed')
  assert.strictEqual(ag.panelRuns(), 0, 'idempotent skip: the panel must NOT run when gate already passed')

  // (b) gate pending + clean terminal -> run the panel, map to passed.
  ag = makeAgent({ gate: 'pending', terminal: 'clean' })
  global.agent = ag
  r = await sr.reviewDocPhase('plan', 'wi')
  assert.strictEqual(r.gate, 'passed', 'clean terminal maps to passed')
  assert.ok(ag.panelRuns() >= 5, 'the panel ran when the gate was not yet passed')

  // (c) pending + halted terminal -> changes-requested (parks downstream).
  ag = makeAgent({ gate: 'pending', terminal: 'halted' })
  global.agent = ag
  r = await sr.reviewDocPhase('plan', 'wi')
  assert.strictEqual(r.gate, 'changes-requested', 'halted terminal maps to changes-requested')

  // (d) clean terminal but the set-gate write does not record -> park low-confidence (UFR-5 guard).
  ag = makeAgent({ gate: 'pending', terminal: 'clean', setGateFails: true })
  global.agent = ag
  r = await sr.reviewDocPhase('plan', 'wi')
  assert.strictEqual(r.gate, 'passed', 'terminal still maps to passed')
  assert.strictEqual(r.phaseResult.confidence, 'low', 'a failed gate write parks (low confidence, UFR-5)')
  console.log('ok: reviewDocPhase gate mapping + idempotent skip + gate-write guard')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
