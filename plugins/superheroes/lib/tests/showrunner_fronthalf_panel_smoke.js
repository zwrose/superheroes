// Smoke: runReviewDocPanel wires the doc-leg (panel:true) — sets the three global.* wrappers and
// calls reviewPanel once with the front-half leg wiring, returning the #104 terminal. #115: reviewers
// RETURN {findings:[]} (no findings-<name>.json); the synthesis leaf RETURNS {verdicts:[]}; merge +
// tally are in-process twins (no front_half.py merge, no tally agent). Stubs the leaves + the
// cheap exec recordDeferred pipe. Uses a fresh on-disk runDir so the durable accumulator never leaks.
const assert = require('assert')
const fs = require('fs'); const os = require('os'); const path = require('path')
const sr = require('../showrunner.js')
const modelTier = require('../model_tier.js')

const BLOCKER = { file: 'docs/superheroes/wi/plan.md', line: 7, title: 'missing invariant', severity: 'Critical', evidence: 'e' }

function installAgent({ blocking = false } = {}) {
  const calls = { reviewer: [], synth: [], revise: [], defer: 0 }
  let reviewerCalls = 0
  global.agent = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'resume') return '1'
    if (label.startsWith('architecture') || label.endsWith('-reviewer')) {
      calls.reviewer.push({ label, model: opts && opts.model })
      reviewerCalls += 1
      return { findings: blocking && reviewerCalls <= sr.DOC_REVIEWERS.length ? [BLOCKER] : [], confidence: 'high' }
    }
    if (label.startsWith('synthesis')) {
      calls.synth.push({ label, model: opts && opts.model })
      return { verdicts: [] }
    }
    if (label === 'revise-doc') {
      calls.revise.push({ label, model: opts && opts.model })
      return { fixes: ['docs/superheroes/wi/plan.md::missing invariant'], deferred: [], changedSubjects: ['Plan'], coverageDecisions: [] }
    }
    if (label === 'exec') { if (prompt.includes('record-deferred')) calls.defer += 1; return [] }
    if (label === 'lib') return { ok: true }     // read-gate / set-gate cmdRunner calls
    return null
  }
  return calls
}

function assertEveryModel(items, expected, what) {
  assert.ok(items.length > 0, `${what} should have dispatched at least one leaf`)
  assert.deepStrictEqual(
    [...new Set(items.map((c) => c.model))],
    [expected],
    `${what} leaves should all dispatch on ${expected}`,
  )
}

async function runPanel({ overrides = null, blocking = false, suffix = '' } = {}) {
  const savedOverrides = globalThis.__SR_OVERRIDES
  if (overrides === null) delete globalThis.__SR_OVERRIDES
  else globalThis.__SR_OVERRIDES = overrides
  const calls = installAgent({ blocking })
  const runDir = fs.mkdtempSync(path.join(os.tmpdir(), `sr-fh-panel-${suffix || 'x'}-`))
  try {
    const v = await sr.runReviewDocPanel({ workItem: 'wi', docType: 'plan',
      docPath: 'docs/superheroes/wi/plan.md', runDir })
    return { v, calls }
  } finally {
    if (savedOverrides === undefined) delete globalThis.__SR_OVERRIDES
    else globalThis.__SR_OVERRIDES = savedOverrides
  }
}

async function main() {
  global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
  global.log = () => {}

  let { v, calls } = await runPanel({ suffix: 'default' })
  assert.strictEqual(v.terminal, 'clean', 'a clean doc-leg run returns the #104 clean terminal')
  assert.ok(calls.reviewer.length >= 5, 'the five doc reviewers were dispatched')
  assertEveryModel(calls.reviewer, modelTier.DEFAULT_TIERS.reviewer, 'default doc reviewer')
  assertEveryModel(calls.synth, modelTier.DEFAULT_TIERS.synthesis, 'default doc synthesis')
  assert.strictEqual(calls.revise.length, 0, 'clean doc-leg run does not need revise-doc')
  assert.ok(!calls.reviewer.concat(calls.synth).some((c) => c.model === 'fable'),
    'defaults stay Fable-free')
  // calls.defer is 0 here by design: a clean first round never enters the fix step (recordDeferred).

  ;({ v, calls } = await runPanel({
    suffix: 'override',
    blocking: true,
    overrides: { reviewer: 'fable', synthesis: 'fable', fixer: 'fable' },
  }))
  assert.strictEqual(v.terminal, 'clean', 'a blocking doc-leg run converges after revise-doc')
  assertEveryModel(calls.reviewer, 'fable', 'overridden doc reviewer')
  assertEveryModel(calls.synth, 'fable', 'overridden doc synthesis')
  assertEveryModel(calls.revise, 'fable', 'overridden doc reviser')
  console.log('ok: runReviewDocPanel wires the panel-doc leg (in-memory twins)')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
