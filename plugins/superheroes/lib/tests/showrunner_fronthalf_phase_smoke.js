// Smoke: reviewDocPhase maps a #104 terminal -> gate, short-circuits when the gate is already
// passed (idempotent passed-gate skip), and parks on a failed gate write (UFR-5). #115: the doc panel
// runs in-memory — reviewers RETURN {findings:[]}, the synthesis leaf RETURNS {verdicts:[]}, merge +
// tally are in-process twins (no front_half.py merge / tally agent). Terminals are driven by the
// reviewer findings + the doc-reviser fixStep, not by a canned tally verdict. Stubs the leaves.
const assert = require('assert')
const fs = require('fs')
const sr = require('../showrunner.js')

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}

const BLOCKER = [{ file: 'docs/superheroes/wi/plan.md', line: 1, title: 'gap', severity: 'Critical', evidence: 'e' }]

// reviewerFindings: what each doc reviewer returns. reviserFails: the doc-reviser fixStep returns null
// (a fix failure -> halted). gate: the read-gate value. setGateFails: the set-gate write does not record.
function makeAgent({ gate, reviewerFindings = [], reviserFails = false, setGateFails }) {
  let panelRuns = 0
  const fn = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'resume') return '1'
    if (label === 'lib') {
      if (prompt.includes('read-gate')) return { review: gate }
      if (prompt.includes('gate-for-terminal')) {
        // map the terminal in the command to a gate exactly as front_half.py would.
        const m = prompt.match(/--terminal '([^']+)'/)
        return { gate: m && m[1] === 'clean' ? 'passed' : 'changes-requested' }
      }
      if (prompt.includes('set-gate')) {
        if (setGateFails) return { review: 'pending', status: 'in-review' }   // write did not record the gate
        const m = prompt.match(/--review '([^']+)'/); return { review: m ? m[1] : 'passed', status: 'approved' }
      }
      return { ok: true }
    }
    if (label === 'exec') return []                                    // the cheap recordDeferred pipe
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
  assert.strictEqual(r.gate, 'passed', 'clean terminal maps to passed')
  assert.ok(ag.panelRuns() >= 5, 'the panel ran when the gate was not yet passed')

  // (c) pending + a blocker whose doc-reviser fix fails -> halted -> changes-requested (parks).
  clean('wi-c')
  ag = makeAgent({ gate: 'pending', reviewerFindings: BLOCKER, reviserFails: true })
  global.agent = ag
  r = await sr.reviewDocPhase('plan', 'wi-c')
  assert.strictEqual(r.gate, 'changes-requested', 'halted terminal maps to changes-requested')

  // (d) clean review but the set-gate write does not record -> park low-confidence (UFR-5 guard).
  clean('wi-d')
  ag = makeAgent({ gate: 'pending', reviewerFindings: [], setGateFails: true })
  global.agent = ag
  r = await sr.reviewDocPhase('plan', 'wi-d')
  assert.strictEqual(r.gate, 'passed', 'terminal still maps to passed')
  assert.strictEqual(r.phaseResult.confidence, 'low', 'a failed gate write parks (low confidence, UFR-5)')
  console.log('ok: reviewDocPhase gate mapping + idempotent skip + gate-write guard')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
