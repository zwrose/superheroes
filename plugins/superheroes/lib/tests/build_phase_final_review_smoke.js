require('./_smoke_checkout_root.js')
// plugins/superheroes/lib/tests/build_phase_final_review_smoke.js
// #115: runFinalReview drives the in-memory panel (single-reviewer code leg). The reviewer RETURNS a
// findings[] array (no findings-generalist.json); merge/tally run in-process via the parity-locked
// twins; the verify gate still runs verify_gate.py via a leaf. Pins terminal 'clean' (no findings +
// verify pass) and terminal 'halted' (verify fail blocks a clean certification, FR-17/UFR-4).
// #115 increment A: verify_command_cli.py + minor_rollup_cli.py are ported to exec(raw)+parse (they
// route through the 'exec' label, stdout a JSON string). model_tier is now an in-process twin (no
// leaf) — its routes are gone (reviewerModel/fixerModel come from model_tier.js directly).
const assert = require('assert')
const fs = require('fs'); const os = require('os'); const path = require('path')
global.log = () => {}
global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))

// reviewerFindings: what the (single) reviewer leaf returns this run. verifyResult: the verify-gate
// classification ('pass'|'fail'|'timeout'|'skipped'). The config IO leaves (verify_command_cli.py,
// minor_rollup_cli.py) route through the 'exec' label and return the exec array shape. #115 Task 16:
// verifyAgent emits raw run data ({command,returncode,timedOut}) for the JS twin to classify.
function makeAgent({ reviewerFindings, verifyResult }) {
  // Map a desired classify result back to the raw run data that produces it
  function runDataFor(result) {
    if (result === 'skipped') return { command: 'none', returncode: null, timedOut: false }
    if (result === 'timeout') return { command: 'pytest -q', returncode: null, timedOut: true }
    if (result === 'pass')    return { command: 'pytest -q', returncode: 0,    timedOut: false }
    return                           { command: 'pytest -q', returncode: 1,    timedOut: false }  // fail
  }
  function writeVerifyOut(prompt, result) {
    const m = String(prompt || '').match(/--out '([^']+)'/)
    if (!m) return
    const payload = result === 'pass' ? { result: 'pass', code: 0, tail: '' }
      : result === 'skipped' ? { result: 'skipped', code: null, tail: '' }
      : result === 'timeout' ? { result: 'timeout', code: null, tail: '' }
      : { result: 'fail', code: 1, tail: '' }
    fs.writeFileSync(m[1], JSON.stringify(payload))
  }
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'resume') return '1'
    if (label.startsWith('branch-reviewer:')) return { findings: reviewerFindings }
    if (label === 'run verify') {
      if (verifyResult === 'garbled-no-command') return { returncode: 1, timedOut: false }
      writeVerifyOut(prompt, verifyResult)
      return runDataFor(verifyResult)
    }
    if (label === 'read verify + minors') {
      return [{ ok: true, stdout: JSON.stringify({ ok: true, verify_command: 'pytest -q', minors: [] }) }]
    }
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
  //    the clean-looking round CANNOT certify -> terminal 'halted'.
  global.agent = makeAgent({ reviewerFindings: [], verifyResult: 'garbled-no-command' })
  r = await bp.runFinalReview('wi', 5, 'superheroes/wi-abc',
    fs.mkdtempSync(path.join(os.tmpdir(), 'fr-')))
  assert.strictEqual(r.terminal, 'halted',
    'a verify failure with a dropped command echo must classify fail (not skipped) -> no clean certify')
  console.log('ok: build_phase final review clean + halted + garbled-verify-fail-closed (in-memory panel, FR-17/UFR-4/FIX2)')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
