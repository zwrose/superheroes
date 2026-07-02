// Smoke: reviewDocPhase maps a #104 terminal -> gate, short-circuits when the gate is already
// passed (idempotent passed-gate skip), and parks on a failed gate write (UFR-5). #115: the doc panel
// runs in-memory — reviewers RETURN {findings:[]}, the synthesis leaf RETURNS {verdicts:[]}, merge +
// tally are in-process twins (no front_half.py merge / tally agent). Terminals are driven by the
// reviewer findings + the doc-reviser fixStep, not by a canned tally verdict. Stubs the leaves.
// #115 Task 12: gateForTerminal is the in-process JS twin (no gate-for-terminal cmdRunner agent).
//   readGate uses exec (not cmdRunner label='lib').
// #118: reviewDocPhase RETURNS its persist spec (set-gate side-effect + journal payload); the ONE
//   'save phase progress' write happens in runPhases' per-phase tail — the failure scenarios drive
//   runPhases and assert the park there (UFR-5: never advance on an un-recorded gate).
const assert = require('assert')
const fs = require('fs')
const sr = require('../showrunner.js')
const { io } = require('../io_seam.js')

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}

const BLOCKER = [{ file: 'docs/superheroes/wi/plan.md', line: 1, title: 'gap', severity: 'Critical', evidence: 'e' }]
const BIG_MINOR_FINDINGS = Array.from({ length: 24 }, (_, i) => ({
  file: 'docs/superheroes/wi/plan.md',
  line: i + 2,
  title: `large nonblocking note ${i}`,
  severity: 'Minor',
  evidence: 'e'.repeat(700),
}))

// gate: what read-gate returns. setGateFails: the set-gate step in persistPhase returns ok:false
// (exec-level failure: set-gate sys.exit(1) -> leaf ok:false). journalWriteFails: the journal command
// reports exec ok:true (bash exit 0) but its STDOUT is {"ok":false} — the durable-write fail-OPEN case
// (journal_entry.py DurableWriteError prints {"ok":false} and exits 0). persistPhase must fail-CLOSE on it.
function jsonOut(obj) { return [{ ok: true, stdout: JSON.stringify(obj) }] }

// setGateFails / journalWriteFails: shape the save phase progress courier response.
function makeAgent({ gate, reviewerFindings = [], reviserFails = false, setGateFails, setGateStale, journalWriteFails }) {
  let panelRuns = 0
  const fn = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'resume') return '1'
    if (label === 'save phase progress') {
      if (setGateFails || setGateStale || journalWriteFails) {
        // setGateStale: the fenced set-gate refuses a stale snapshot (exits non-zero inside the
        // batched sideEffectCmd) — the courier reports ok:false and persistPhase fails closed.
        return jsonOut({ ok: false, reason: setGateFails ? 'set-gate failed' : (setGateStale ? 'stale' : 'durable write failed') })
      }
      return jsonOut({ ok: true, journal_confirmed: true, checkpoint_confirmed: true })
    }
    if (label === 'save round state') return jsonOut({ ok: true })
    if (label === 'exec') {
      if (prompt.includes('read-gate')) return [{ index: 0, ok: true, stdout: JSON.stringify({ review: gate }) }]
      // gate-for-terminal must NOT be dispatched as an exec (it is the in-process JS twin).
      if (prompt.includes('gate-for-terminal')) throw new Error('gate-for-terminal dispatched as exec — must use JS twin')
      return [{ index: 0, ok: true, stdout: '' }, { index: 1, ok: true, stdout: '' }]
    }
    // gate-for-terminal must NOT be dispatched as a cmdRunner agent either.
    if (prompt.includes('gate-for-terminal')) throw new Error('gate-for-terminal dispatched as cmdRunner — must use JS twin')
    // a genuinely clean/complete review needs a real verificationReceipt (else the receipt-fabrication
    // fix downgrades it to confidence:low -> cannot-certify).
    if (label.endsWith('-reviewer')) {
      panelRuns += 1
      return { findings: reviewerFindings, confidence: 'high', verificationReceipt: { artifact: 'stub', chain: [], coverageDecisionIds: [] } }
    }
    if (label.startsWith('synthesis')) return { verdicts: [] }         // keep all merged findings
    if (label === 'revise-doc') return reviserFails ? null : { fixes: [], deferred: [] }
    return null
  }
  fn.panelRuns = () => panelRuns
  return fn
}

// reviewDocPhase reuses /tmp/showrunner-<wi>-review-<doc>; clear it so the durable accumulator from a
// prior scenario/run never leaks into this one. Also seed a minimal plan doc so the panel's doc-mode
// coverage-decision reader (review_panel_shell) can load an empty decision set instead of cannot-certify.
function clean(wi) {
  try { fs.rmSync(`/tmp/showrunner-${wi}-review-plan`, { recursive: true, force: true }) } catch (_) {}
  const dir = `docs/superheroes/${wi}`
  try {
    fs.mkdirSync(dir, { recursive: true })
    fs.writeFileSync(`${dir}/plan.md`, '# Plan\n## Review coverage decisions\n')
  } catch (_) {}
}

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

  // (d) clean review but the set-gate write fails at the per-phase tail -> runPhases parks (UFR-5).
  // The persist now lives in runPhases' tail (ONE 'save phase progress' leaf), so the failure is
  // asserted on the loop outcome — the run must never advance past an un-recorded gate.
  clean('wi-d')
  ag = makeAgent({ gate: 'pending', reviewerFindings: [], setGateFails: true })
  global.agent = ag
  let loopOut = await sr.runPhases('wi-d', 1, { reviewDoc: (doc, wi) => sr.reviewDocPhase(doc, wi) })
  assert.strictEqual(loopOut.outcome, 'parked', 'a failed gate write parks the run (UFR-5)')
  assert.strictEqual(loopOut.phase, 'review-plan')
  assert.match(loopOut.reason, /phase progress not recorded/, 'the park names the durable-write failure')

  // (e) DURABLE-WRITE FAIL-CLOSE (the C1 regression): the save command's bash exits 0 (exec ok:true)
  //     but its STDOUT is {"ok":false} — the DurableWriteError print-then-exit-0 shape. persistPhase
  //     parses the stdout and fails-CLOSE, so runPhases parks instead of advancing.
  clean('wi-e')
  ag = makeAgent({ gate: 'pending', reviewerFindings: [], journalWriteFails: true })
  global.agent = ag
  loopOut = await sr.runPhases('wi-e', 1, { reviewDoc: (doc, wi) => sr.reviewDocPhase(doc, wi) })
  assert.strictEqual(loopOut.outcome, 'parked',
    'a journal {"ok":false} durable-write failure (bash exit 0) parks — persistPhase fails-close (C1)')
  assert.strictEqual(loopOut.phase, 'review-plan')
  assert.match(loopOut.reason, /phase progress not recorded/, 'the park names the un-recorded write (UFR-5)')

  // (e-unit) persistPhase directly: exec ok:true + stdout {"ok":false} must return {ok:false}; a
  // matching all-{"ok":true} batch must return {ok:true}. Proves the parse fold (vs the pre-fix every(r.ok)).
  global.agent = async (_p, opts) => {
    if (opts && opts.label === 'save phase progress') {
      return jsonOut({ ok: false, reason: 'durable write failed' })
    }
    return jsonOut({ ok: true, journal_confirmed: true, checkpoint_confirmed: true })
  }
  let pp = await sr.persistPhase('wi-e2', { sideEffectCmd: 'echo set-gate', journalPayload: {}, step: 1, phase: 'p' })
  assert.deepStrictEqual(pp, { ok: false, error: 'durable write failed' },
    'persistPhase fails-close when save phase progress returns ok:false (C1)')
  global.agent = async (_p, opts) => {
    if (opts && opts.label === 'save phase progress') {
      return jsonOut({ ok: true, journal_confirmed: true, checkpoint_confirmed: true })
    }
    return jsonOut({ ok: true })
  }
  pp = await sr.persistPhase('wi-e3', { sideEffectCmd: 'echo set-gate', journalPayload: {}, step: 1, phase: 'p' })
  assert.deepStrictEqual(pp, { ok: true, recovered: false }, 'persistPhase happy path read-back confirmed')

  // (f) reviewDocPhase returns the set-gate persist spec (side-effect command + journal payload)
  // carrying the 'current' fence sentinel, run id, and lease — the runPhases tail chains it ahead
  // of the phase_progress_entry save inside the ONE 'save phase progress' leaf (#118 fold). The
  // doc hash is computed PYTHON-SIDE at write time: a runtime contentHash(readText(doc)) fed the
  // fence courier prose live (2026-07-02) and parked every gate write as 'stale'.
  clean('wi-f')
  ag = makeAgent({ gate: 'pending', reviewerFindings: [] })
  global.agent = ag
  r = await sr.reviewDocPhase('plan', 'wi-f', { runId: 'run-f', lease: 'lease-f' })
  assert.ok(r.persist && r.persist.sideEffectCmd, 'reviewDocPhase returned the set-gate persist spec')
  const gatePrompt = r.persist.sideEffectCmd
  assert.ok(gatePrompt.includes('set-gate'), 'the persist side effect is the fenced set-gate')
  assert.match(gatePrompt, /--expected-hash ['"]?current['"]?/, 'gate write fences via the Python-side current-hash sentinel (no courier-read hash)')
  assert.match(gatePrompt, /--run-id ['"]?run-f['"]?/)
  assert.match(gatePrompt, /--lease ['"]?lease-f['"]?/)
  assert.deepStrictEqual(r.persist.journalPayload.phase, 'review-plan', 'the journal payload names the review phase')
  assert.strictEqual(r.phaseResult.confidence, 'high')

  // (g) stale gate write parks at the tail (fail-closed at the courier boundary); the
  // unchanged-gate half of the stale contract is proven python-side in test_gate_write.py.
  clean('wi-g')
  ag = makeAgent({ gate: 'changes-requested', reviewerFindings: [], setGateStale: true })
  global.agent = ag
  loopOut = await sr.runPhases('wi-g', 1, { reviewDoc: (doc, wi) => sr.reviewDocPhase(doc, wi, { runId: 'run-g', lease: 'lease-g', reviewedHash: 'stale-hash' }) })
  assert.strictEqual(loopOut.outcome, 'parked', 'stale/failed gate write parks instead of advancing')
  assert.match(loopOut.reason, /phase progress not recorded/, 'the park names the durable-write failure')

  // (h) terminal-record persistence must not stage a large verdict blob through the courier. A
  // truncating write leaf leaves an old terminal-record.json behind in the live failure class; the
  // phase must compose and overwrite the record in-process from small scalars + on-disk records.
  clean('wi-h')
  const hDir = '/tmp/showrunner-wi-h-review-plan'
  fs.mkdirSync(hDir, { recursive: true })
  fs.writeFileSync(`${hDir}/terminal-record.json`, JSON.stringify({ terminal: 'stale-prior-run' }))
  const oldIo = global.io
  const baseIo = io()
  global.io = Object.assign({}, baseIo, {
    async writeFile(p, s) {
      const text = typeof s === 'string' ? s : JSON.stringify(s)
      if (String(p).endsWith('terminal-record.json.payload') && text.length > 8192) {
        fs.writeFileSync(p, text.slice(0, 8192))
        return
      }
      return baseIo.writeFile(p, s)
    },
  })
  ag = makeAgent({ gate: 'pending', reviewerFindings: BIG_MINOR_FINDINGS })
  global.agent = ag
  r = await sr.reviewDocPhase('plan', 'wi-h', { runId: 'run-h' })
  global.io = oldIo
  assert.strictEqual(r.phaseResult.confidence, 'high', 'large terminal-record compose should not park at payload stage')
  const terminal = JSON.parse(fs.readFileSync(`${hDir}/terminal-record.json`, 'utf8'))
  assert.strictEqual(terminal.terminal, 'clean', 'stale prior terminal record must be overwritten')
  assert.ok(!('findings' in terminal), 'terminal record must not carry evidence-bodied findings')
  assert.ok(!fs.readFileSync(`${hDir}/terminal-record.json`, 'utf8').includes('stale-prior-run'),
    'stale prior terminal record content must be gone')

  console.log('ok: reviewDocPhase gate mapping + idempotent skip + gate-write guard + durable-write fail-close (C1)')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
