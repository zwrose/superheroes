// plugins/superheroes/lib/tests/showrunner_reviewcode_smoke.js
// Dev-time only (node, not CI): proves the #86 panel verdict -> gate vocabulary mapping.
// verdictToGate is a pure synchronous map, so this smoke needs no agent()/parallel() stubs.
const assert = require('assert')
const sr = require('../showrunner.js')

;(async () => {
  assert.strictEqual(sr.verdictToGate({ gate: 'clean', terminal: 'clean' }), 'passed',
    'a clean verdict -> passed')
  assert.strictEqual(sr.verdictToGate({ gate: 'blocking', terminal: 'halted' }), 'changes-requested',
    'a blocking verdict -> changes-requested')
  assert.strictEqual(sr.verdictToGate({ gate: 'cannot-certify', terminal: 'cannot-certify' }), 'changes-requested',
    'a cannot-certify verdict -> changes-requested (fail closed, never passed)')

  let promptLog = []
  global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
  global.log = () => {}
  global.agent = async (prompt, opts) => {
    promptLog.push(prompt)
    const label = opts && opts.label
    if (label === 'lib' && prompt.includes('git -C')) return 'head-1\n'
    if (label === 'resume') return '1'
    if (label === 'lib' && prompt.includes('review_code_config.py')) return { verifyCommand: 'none', tiers: {} }
    if (label && label.startsWith('tally')) return { terminal: 'clean', gate: 'clean', findings: [] }
    if (label && label.startsWith('verify')) return { result: 'pass' }
    if (label && label.startsWith('synthesis')) return { findings: [], drops: [] }
    if (label === 'lib' && prompt.includes('prov_entry.py')) return { ok: true }
    return true
  }
  const r = await sr.reviewCodePhase('wi-targeted', {
    worktree: '/tmp/build-worktree',
    expectedHead: 'head-1',
    runDir: '/tmp/showrunner-wi-targeted-review-code-test-pilot-1-head-1',
  })
  assert.strictEqual(r.gate, 'passed')
  assert.ok(promptLog.some((p) => p.includes('/tmp/showrunner-wi-targeted-review-code-test-pilot-1-head-1')),
    'targeted stabilization uses the caller-provided fresh runDir')
  assert.ok(promptLog.some((p) => p.includes('Target worktree: /tmp/build-worktree') && p.includes('Expected head: head-1')),
    'review leaves receive explicit worktree/head context')
  assert.ok(promptLog.some((p) => p.includes('prov_entry.py') && p.includes('--worktree') && p.includes('--head')),
    'provenance restamp is bound to explicit worktree/head')

  console.log('OK: panel verdict maps to gate (clean->passed, else->changes-requested)')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
