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
const { io } = require('../io_seam.js')

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}

const BLOCKER = [{ file: 'docs/superheroes/wi/plan.md', line: 1, title: 'gap', severity: 'Critical', evidence: 'e' }]

// gate: what read-gate returns. setGateFails: the set-gate step in persistPhase returns ok:false
// (exec-level failure: set-gate sys.exit(1) -> leaf ok:false). journalWriteFails: the journal command
// reports exec ok:true (bash exit 0) but its STDOUT is {"ok":false} — the durable-write fail-OPEN case
// (journal_entry.py DurableWriteError prints {"ok":false} and exits 0). persistPhase must fail-CLOSE on it.
function makeAgent({ gate, reviewerFindings = [], reviserFails = false, setGateFails, setGateStale, journalWriteFails }) {
  let panelRuns = 0
  const fn = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'resume') return '1'
    if (label === 'exec') {
      if (prompt.includes('read-gate')) return [{ index: 0, ok: true, stdout: JSON.stringify({ review: gate }) }]
      if (prompt.includes('set-gate')) {
        // persistPhase batches set-gate + journal + checkpoint into one exec call. Success stdouts are
        // production-realistic JSON (set-gate prints {"ok":true,"review":...}, journal/checkpoint {"ok":true});
        // an EMPTY stdout would now read as a courier-drop (retried), so the clean cases emit real JSON.
        // setGateFails: return ok:false for the set-gate command (exec-level fail) so persistPhase fails closed.
        const ok = !setGateFails && !setGateStale
        return [
          { index: 0, ok, stdout: setGateStale ? JSON.stringify({ ok: false, reason: 'stale' }) : JSON.stringify({ ok: true, review: 'passed', status: 'approved' }) },   // set-gate
          // journalWriteFails: bash exit 0 (exec ok:true) but stdout is {"ok":false} — the exact
          // durable-write fail-OPEN shape persistPhase must catch by parsing the stdout (NOT a drop).
          { index: 1, ok: true, stdout: journalWriteFails ? JSON.stringify({ ok: false, error: 'durable write failed' }) : JSON.stringify({ ok: true }) },  // journal_entry
          { index: 2, ok: true, stdout: JSON.stringify({ ok: true }) },  // checkpoint_entry
        ]
      }
      // gate-for-terminal must NOT be dispatched as an exec (it is the in-process JS twin).
      if (prompt.includes('gate-for-terminal')) throw new Error('gate-for-terminal dispatched as exec — must use JS twin')
      // Generic exec (recordDeferred, io writes, etc.)
      return [{ index: 0, ok: true, stdout: '' }, { index: 1, ok: true, stdout: '' }]
    }
    // gate-for-terminal must NOT be dispatched as a cmdRunner agent either.
    if (prompt.includes('gate-for-terminal')) throw new Error('gate-for-terminal dispatched as cmdRunner — must use JS twin')
    if (label.endsWith('-reviewer')) { panelRuns += 1; return { findings: reviewerFindings, confidence: 'high' } }
    if (label.startsWith('synthesis')) return { verdicts: [] }         // keep all merged findings
    if (label === 'doc-reviser') return reviserFails ? null : { fixes: [], deferred: [] }
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

  // (d) clean review but the set-gate persistPhase fails -> park low-confidence (UFR-5 guard).
  clean('wi-d')
  ag = makeAgent({ gate: 'pending', reviewerFindings: [], setGateFails: true })
  global.agent = ag
  r = await sr.reviewDocPhase('plan', 'wi-d')
  assert.strictEqual(r.gate, 'passed', 'terminal still maps to passed')
  assert.strictEqual(r.phaseResult.confidence, 'low', 'a failed gate write parks (low confidence, UFR-5)')

  // (e) DURABLE-WRITE FAIL-CLOSE (the C1 regression): the journal command's bash exits 0 (exec ok:true)
  //     but its STDOUT is {"ok":false} — journal_entry.py's DurableWriteError print-then-exit-0 shape.
  //     The pre-fix `every(r => r.ok)` ignored stdout -> persistPhase returned {ok:true} -> reviewDocPhase
  //     advanced HIGH-confidence on un-recorded state (silent UFR-5 defeat). After the fix persistPhase
  //     parses each stdout and fails-CLOSE on a script-level {"ok":false}, so we park LOW.
  clean('wi-e')
  ag = makeAgent({ gate: 'pending', reviewerFindings: [], journalWriteFails: true })
  global.agent = ag
  r = await sr.reviewDocPhase('plan', 'wi-e')
  assert.strictEqual(r.gate, 'passed', 'terminal still maps to passed')
  assert.strictEqual(r.phaseResult.confidence, 'low',
    'a journal {"ok":false} durable-write failure (bash exit 0) parks LOW — persistPhase fails-close (C1)')
  assert.deepStrictEqual(r.phaseResult.assumptions, ['gate write did not record for plan'],
    'the park reason names the un-recorded gate write (UFR-5)')

  // (e-unit) persistPhase directly: exec ok:true + stdout {"ok":false} must return {ok:false}; a
  // matching all-{"ok":true} batch must return {ok:true}. Proves the parse fold (vs the pre-fix every(r.ok)).
  global.agent = async () => [
    { index: 0, ok: true, stdout: JSON.stringify({ ok: true, review: 'passed', status: 'approved' }) },  // set-gate
    { index: 1, ok: true, stdout: JSON.stringify({ ok: false }) },       // journal durable-write failed, exit 0
    { index: 2, ok: true, stdout: JSON.stringify({ ok: true }) },        // checkpoint ok
  ]
  let pp = await sr.persistPhase('wi-e2', { sideEffectCmd: 'echo set-gate', journalPayload: {}, step: 1, phase: 'p' })
  assert.deepStrictEqual(pp, { ok: false },
    'persistPhase fails-close when a batched command stdout is {"ok":false} despite exec ok:true (C1)')
  global.agent = async () => [
    { index: 0, ok: true, stdout: JSON.stringify({ ok: true, review: 'passed', status: 'approved' }) },  // set-gate
    { index: 1, ok: true, stdout: JSON.stringify({ ok: true }) },
    { index: 2, ok: true, stdout: JSON.stringify({ ok: true }) },
  ]
  pp = await sr.persistPhase('wi-e3', { sideEffectCmd: 'echo set-gate', journalPayload: {}, step: 1, phase: 'p' })
  assert.deepStrictEqual(pp, { ok: true }, 'persistPhase happy path: all stdout {"ok":true} -> {ok:true}')

  // (f) direct reviewDocPhase gate writes include the reviewed snapshot hash, run id, and lease.
  clean('wi-f')
  const execPrompts = []
  ag = makeAgent({ gate: 'pending', reviewerFindings: [] })
  global.agent = async (prompt, opts) => {
    if ((opts && opts.label) === 'exec') execPrompts.push(prompt)
    return ag(prompt, opts)
  }
  r = await sr.reviewDocPhase('plan', 'wi-f', { runId: 'run-f', lease: 'lease-f', reviewedHash: 'hash-f' })
  const gatePrompt = execPrompts.find((p) => p.includes('set-gate') || p.includes('gate_write.py'))
  assert.ok(gatePrompt, 'reviewDocPhase emitted a gate write command')
  const postPanelHash = io().contentHash(fs.readFileSync('docs/superheroes/wi-f/plan.md', 'utf8'))
  assert.match(gatePrompt, new RegExp(`--expected-hash ['"]?${postPanelHash}['"]?`), 'gate write uses post-panel doc hash, not pre-loop snapshot')
  assert.match(gatePrompt, /--run-id ['"]?run-f['"]?/)
  assert.match(gatePrompt, /--lease ['"]?lease-f['"]?/)
  assert.strictEqual(r.phaseResult.confidence, 'high')

  // (g) stale reviewed hash parks and leaves the already-recorded gate unchanged.
  clean('wi-g')
  ag = makeAgent({ gate: 'changes-requested', reviewerFindings: [], setGateStale: true })
  global.agent = ag
  r = await sr.reviewDocPhase('plan', 'wi-g', { runId: 'run-g', lease: 'lease-g', reviewedHash: 'stale-hash' })
  assert.strictEqual(r.gate, 'passed', 'terminal still maps to passed before persistence')
  assert.strictEqual(r.phaseResult.confidence, 'low', 'stale/failed gate write parks instead of advancing')

  console.log('ok: reviewDocPhase gate mapping + idempotent skip + gate-write guard + durable-write fail-close (C1)')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
