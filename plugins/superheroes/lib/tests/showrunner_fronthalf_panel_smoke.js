// Smoke: runReviewDocPanel wires the doc-leg (panel:true) — sets the four global.* wrappers and
// calls reviewPanel once with the front-half leg wiring, returning the #104 terminal. Stubs leaves.
const assert = require('assert')
const sr = require('../showrunner.js')

let calls = { reviewer: 0, merge: 0, synth: 0, defer: 0, tally: 0 }
global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}
global.agent = async (prompt, opts) => {
  const label = (opts && opts.label) || ''
  if (label === 'resume') return '1'
  if (label.startsWith('architecture') || label.endsWith('-reviewer')) { calls.reviewer += 1; return null }
  if (label === 'lib') {                       // cmdRunner: merge / record-deferred / read-gate
    if (prompt.includes('front_half.py merge')) { calls.merge += 1; return { ok: true, merged: 0 } }
    if (prompt.includes('record-deferred')) { calls.defer += 1; return { ok: true, deferred: 0 } }
    return { ok: true }
  }
  if (label.startsWith('synthesis')) { calls.synth += 1; return { findings: [], drops: [] } }
  if (label.startsWith('tally')) { calls.tally += 1; return { schemaVersion: 1, terminal: 'clean', gate: 'clean' } }
  return null
}

async function main() {
  const v = await sr.runReviewDocPanel({ workItem: 'wi', docType: 'plan',
    docPath: 'docs/superheroes/wi/plan.md', runDir: '/tmp/sr-fh-panel-smoke' })
  assert.strictEqual(v.terminal, 'clean', 'a clean doc-leg run returns the #104 clean terminal')
  assert.ok(calls.reviewer >= 5, 'the five doc reviewers were dispatched')
  assert.ok(calls.merge >= 1, 'the mechanical merge wrapper ran (panel leg synthesis)')
  assert.ok(calls.synth >= 1, 'the synthesis leaf wrapper ran (panel leg synthesis)')
  assert.ok(calls.tally >= 1, 'the tally ran')
  // calls.defer is 0 here by design: a clean first round never enters the fix step (recordDeferred).
  console.log('ok: runReviewDocPanel wires the panel-doc leg')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
