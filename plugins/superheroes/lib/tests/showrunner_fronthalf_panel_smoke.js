// Smoke: runReviewDocPanel wires the doc-leg (panel:true) — sets the three global.* wrappers and
// calls reviewPanel once with the front-half leg wiring, returning the #104 terminal. #115: reviewers
// RETURN {findings:[]} (no findings-<name>.json); the synthesis leaf RETURNS {verdicts:[]}; merge +
// tally are in-process twins (no front_half.py merge, no tally agent). Stubs the leaves + the
// cheap exec recordDeferred pipe. Uses a fresh on-disk runDir so the durable accumulator never leaks.
const assert = require('assert')
const fs = require('fs'); const os = require('os'); const path = require('path')
const sr = require('../showrunner.js')

let calls = { reviewer: 0, synth: 0, defer: 0 }
global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}
global.agent = async (prompt, opts) => {
  const label = (opts && opts.label) || ''
  if (label === 'resume') return '1'
  // a genuinely clean review needs a real verificationReceipt (else the receipt-fabrication fix
  // downgrades it to confidence:low -> cannot-certify).
  if (label.startsWith('architecture') || label.endsWith('-reviewer')) {
    calls.reviewer += 1
    return { findings: [], confidence: 'high', verificationReceipt: { artifact: 'stub', chain: [], coverageDecisionIds: [] } }
  }
  if (label.startsWith('synthesis')) { calls.synth += 1; return { verdicts: [] } }
  if (label === 'exec') { if (prompt.includes('record-deferred')) calls.defer += 1; return [] }
  if (label === 'lib') return { ok: true }     // read-gate / set-gate cmdRunner calls
  return null
}

async function main() {
  const runDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sr-fh-panel-'))
  const v = await sr.runReviewDocPanel({ workItem: 'wi', docType: 'plan',
    docPath: 'docs/superheroes/wi/plan.md', runDir })
  assert.strictEqual(v.terminal, 'clean', 'a clean doc-leg run returns the #104 clean terminal')
  assert.ok(calls.reviewer >= 5, 'the five doc reviewers were dispatched')
  assert.ok(calls.synth >= 1, 'the synthesis leaf wrapper ran (panel leg synthesis)')
  // calls.defer is 0 here by design: a clean first round never enters the fix step (recordDeferred).
  console.log('ok: runReviewDocPanel wires the panel-doc leg (in-memory twins)')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
