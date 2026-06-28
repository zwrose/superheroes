// plugins/superheroes/lib/tests/build_phase_final_review_smoke.js
// #115: runFinalReview drives the in-memory panel (single-reviewer code leg). The reviewer RETURNS a
// findings[] array (no findings-generalist.json); merge/tally run in-process via the parity-locked
// twins; the verify gate still runs verify_gate.py via a leaf. Pins terminal 'clean' (no findings +
// verify pass) and terminal 'halted' (verify fail blocks a clean certification, FR-17/UFR-4).
const assert = require('assert')
const fs = require('fs'); const os = require('os'); const path = require('path')
global.log = () => {}
global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))

// reviewerFindings: what the (single) reviewer leaf returns this run. verifyResult: the verify-gate
// classification ('pass'|'fail'|'timeout'|'skipped'). Routes the cmdRunner config leaves by prompt
// substring. #115 Task 16: verifyAgent now emits raw run data ({command,returncode,timedOut}) for the
// JS twin to classify — stubs return the raw-run form that produces the target verifyResult.
function makeAgent({ reviewerFindings, verifyResult }) {
  const routes = [
    ['verify_command_cli.py', { command: 'pytest -q' }],
    ['model_tier_resolve.py --role reviewer-deep', { model: 'opus' }],
    ['model_tier_resolve.py --role fixer', { model: 'sonnet' }],
    ['minor_rollup_cli.py', { minors: [] }],
  ]
  // Map a desired classify result back to the raw run data that produces it
  function runDataFor(result) {
    if (result === 'skipped') return { command: 'none', returncode: null, timedOut: false }
    if (result === 'timeout') return { command: 'pytest -q', returncode: null, timedOut: true }
    if (result === 'pass')    return { command: 'pytest -q', returncode: 0,    timedOut: false }
    return                           { command: 'pytest -q', returncode: 1,    timedOut: false }  // fail
  }
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'resume') return '1'
    if (label.startsWith('reviewer:')) return { findings: reviewerFindings }   // RETURNS findings (no file)
    if (label.startsWith('verify')) return runDataFor(verifyResult)  // raw run data; JS twin classifies
    if (label === 'exec') return []           // recordDeferred's cheap pipe (unused on the clean path)
    for (const [needle, resp] of routes) if (prompt.includes(needle)) return resp
    return ''
  }
}

global.recordDeferred = async () => {}
const bp = require('../build_phase.js')

;(async () => {
  // 1. Clean single-round final review: no findings + verify pass -> terminal 'clean'.
  global.agent = makeAgent({ reviewerFindings: [], verifyResult: 'pass' })
  let r = await bp.runFinalReview('wi', 5, 'superheroes/wi-abc',
    fs.mkdtempSync(path.join(os.tmpdir(), 'fr-')))
  assert.strictEqual(r.terminal, 'clean')

  // 2. Verify fails -> a clean-looking round cannot certify clean -> terminal 'halted'
  //    (the caller parks, UFR-4). No findings, so the only thing blocking clean is the verify gate.
  global.agent = makeAgent({ reviewerFindings: [], verifyResult: 'fail' })
  r = await bp.runFinalReview('wi', 5, 'superheroes/wi-abc',
    fs.mkdtempSync(path.join(os.tmpdir(), 'fr-')))
  assert.strictEqual(r.terminal, 'halted')
  console.log('ok: build_phase final review clean + halted (in-memory panel, FR-17/UFR-4)')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
