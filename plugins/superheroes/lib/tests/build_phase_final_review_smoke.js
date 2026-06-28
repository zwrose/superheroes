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
    // The verify GATE leaf carries label 'verify:r<round>'. Match it precisely — NOT the config read
    // 'verify_command_cli.py' (which only happens to start with 'verify') — so the spine threads the
    // REAL verifyCommand ('pytest -q' from the config route below) into verifyAgent.
    if (label.startsWith('verify:r')) {
      // 'garbled-no-command': a leaf that DROPS its echoed `command` but reports a real failure
      // (returncode 1). The spine must classify with the command IT knows (the real verifyCommand),
      // not the leaf's missing echo — otherwise the twin sees !cmd -> 'skipped' (a pass-equivalent).
      if (verifyResult === 'garbled-no-command') return { returncode: 1, timedOut: false }
      return runDataFor(verifyResult)  // raw run data; JS twin classifies
    }
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

  // 3. FIX 2 (#115 final review): a GARBLED verify leaf that DROPS its `command` echo but reports a
  //    real failure (returncode 1) under a REAL verifyCommand must NOT be misclassified 'skipped'
  //    (which would certify clean). The spine classifies with the command it knows -> 'fail' ->
  //    the clean-looking round CANNOT certify -> terminal 'halted'. A mutant that classifies on the
  //    leaf's missing echo (out.command) would see !cmd -> 'skipped' -> clean and FAIL here.
  global.agent = makeAgent({ reviewerFindings: [], verifyResult: 'garbled-no-command' })
  r = await bp.runFinalReview('wi', 5, 'superheroes/wi-abc',
    fs.mkdtempSync(path.join(os.tmpdir(), 'fr-')))
  assert.strictEqual(r.terminal, 'halted',
    'a verify failure with a dropped command echo must classify fail (not skipped) -> no clean certify')
  console.log('ok: build_phase final review clean + halted + garbled-verify-fail-closed (in-memory panel, FR-17/UFR-4/FIX2)')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
