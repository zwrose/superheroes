// Smoke: reviewDocPhase maps a #104 terminal -> gate, short-circuits when the gate is already
// passed (idempotent passed-gate skip), and parks on a failed gate write (UFR-5). #115: the doc panel
// runs in-memory — reviewers RETURN {findings:[]}, the synthesis leaf RETURNS {verdicts:[]}, merge +
// tally are in-process twins (no front_half.py merge / tally agent). Terminals are driven by the
// reviewer findings + the doc-reviser fixStep, not by a canned tally verdict. Stubs the leaves.
// #115 Task 12: gateForTerminal is the in-process JS twin (no gate-for-terminal cmdRunner agent).
//   readGate uses exec (not cmdRunner label='lib').
//   reviewDocPhase records the gate via persistPhase (exec with set-gate + journal + checkpoint).
const assert = require('assert')
const fs = require('fs')
const sr = require('../showrunner.js')

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}

const BLOCKER = [{ file: 'docs/superheroes/wi/plan.md', line: 1, title: 'gap', severity: 'Critical', evidence: 'e' }]

// gate: what read-gate returns. setGateFails: the set-gate step in persistPhase returns ok:false.
function makeAgent({ gate, reviewerFindings = [], reviserFails = false, setGateFails }) {
  let panelRuns = 0
  const fn = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'resume') return '1'
    if (label === 'exec') {
      if (prompt.includes('read-gate')) return [{ index: 0, ok: true, stdout: JSON.stringify({ review: gate }) }]
      if (prompt.includes('set-gate')) {
        // persistPhase batches set-gate + journal + checkpoint into one exec call.
        // setGateFails: return ok:false for the set-gate command so persistPhase returns {ok:false}.
        const ok = !setGateFails
        return [
          { index: 0, ok, stdout: '' },   // set-gate
          { index: 1, ok: true, stdout: '' },  // journal_entry
          { index: 2, ok: true, stdout: '' },  // checkpoint_entry
        ]
      }
      // gate-for-terminal must NOT be dispatched as an exec (it is the in-process JS twin).
      if (prompt.includes('gate-for-terminal')) throw new Error('gate-for-terminal dispatched as exec — must use JS twin')
      // Generic exec (recordDeferred, io writes, etc.)
      return [{ index: 0, ok: true, stdout: '' }, { index: 1, ok: true, stdout: '' }]
    }
    // gate-for-terminal must NOT be dispatched as a cmdRunner agent either.
    if (prompt.includes('gate-for-terminal')) throw new Error('gate-for-terminal dispatched as cmdRunner — must use JS twin')
    if (label.endsWith('-reviewer')) { panelRuns += 1; return { findings: reviewerFindings } }
    if (label.startsWith('synthesis')) return { verdicts: [] }         // keep all merged findings
    if (label === 'doc-reviser') return reviserFails ? null : { fixes: [], deferred: [] }
    return null
  }
  fn.panelRuns = () => panelRuns
  return fn
}

// reviewDocPhase reuses /tmp/showrunner-<wi>-review-<doc>; clear it so the durable accumulator from a
// prior scenario/run never leaks into this one.
function clean(wi) { try { fs.rmSync(`/tmp/showrunner-${wi}-review-plan`, { recursive: true, force: true }) } catch (_) {} }

async function main() {
  // (a) gate already passed -> skip the panel entirely, return passed.
  clean('wi-a')
  let ag = makeAgent({ gate: 'passed' })
  global.agent = ag
  let r = await sr.reviewDocPhase('plan', 'wi-a')
  assert.strictEqual(r.gate, 'passed', 'already-passed gate -> passed')
  assert.strictEqual(ag.panelRuns(), 0, 'idempotent skip: the panel must NOT run when gate already passed')

  // (b) gate pending + a clean review (no findings) -> run the panel, map to passed.
  clean('wi-b')
  ag = makeAgent({ gate: 'pending', reviewerFindings: [] })
  global.agent = ag
  r = await sr.reviewDocPhase('plan', 'wi-b')
  assert.strictEqual(r.gate, 'passed', 'clean terminal maps to passed (JS twin gateForTerminal)')
  assert.ok(ag.panelRuns() >= 5, 'the panel ran when the gate was not yet passed')

  // (c) pending + a blocker whose doc-reviser fix fails -> halted -> changes-requested (parks).
  clean('wi-c')
  ag = makeAgent({ gate: 'pending', reviewerFindings: BLOCKER, reviserFails: true })
  global.agent = ag
  r = await sr.reviewDocPhase('plan', 'wi-c')
  assert.strictEqual(r.gate, 'changes-requested', 'halted terminal maps to changes-requested (JS twin)')

  // (d) clean review but the set-gate persistPhase fails -> park low-confidence (UFR-5 guard).
  clean('wi-d')
  ag = makeAgent({ gate: 'pending', reviewerFindings: [], setGateFails: true })
  global.agent = ag
  r = await sr.reviewDocPhase('plan', 'wi-d')
  assert.strictEqual(r.gate, 'passed', 'terminal still maps to passed')
  assert.strictEqual(r.phaseResult.confidence, 'low', 'a failed gate write parks (low confidence, UFR-5)')
  console.log('ok: reviewDocPhase gate mapping + idempotent skip + gate-write guard (exec+twin, no cmdRunner)')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
