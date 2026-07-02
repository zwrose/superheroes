// plugins/superheroes/lib/tests/showrunner_reviewcode_smoke.js
// Dev-time only (node, not CI): proves the #86 panel verdict -> gate vocabulary mapping.
// verdictToGate is a pure synchronous map, so this smoke needs no agent()/parallel() stubs.
const assert = require('assert')
const sr = require('../showrunner.js')

function jsonOut(obj) { return [{ ok: true, stdout: JSON.stringify(obj) }] }

function reviewAgentStub({ verifyCommand = 'python3 -m pytest targeted-tests -q' } = {}) {
  let wtHeadCalls = 0
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    // #118: resolveHead + the config read ride the exec courier (raw stdout), not cmdRunner 'lib'
    if (label === 'exec' && prompt.includes('git -C')) {
      wtHeadCalls += 1
      return wtHeadCalls <= 1 ? 'head-1\n' : 'head-2\n'
    }
    if (label === 'exec' && prompt.includes('git rev-parse')) return 'head-1\n'
    if (label === 'resume') return '1'
    if (label === 'exec' && prompt.includes('review_code_config.py')) {
      assert.ok(prompt.includes("cd '/tmp/build-worktree' &&"), 'config resolves in the explicit target worktree')
      return JSON.stringify({ verifyCommand, tiers: {} })
    }
    if (label === 'run verify') {
      assert.ok(prompt.includes("cd '/tmp/build-worktree' &&"), 'verify gate runs from the explicit target worktree')
      return { command: verifyCommand, returncode: 0, timedOut: false }
    }
    if (label.startsWith('synthesis:')) return { verdicts: [] }
    if (label === 'stamp review coverage') {
      assert.ok(prompt.includes('prov_entry.py') && prompt.includes('--worktree') && prompt.includes('--head'),
        'provenance restamp is bound to explicit worktree/head')
      return jsonOut({ ok: true })
    }
    if (label.startsWith('branch-reviewer:')) return { findings: [] }
    if (label === 'readout') return '## Review loop — done'
    if (label === 'post readout') return jsonOut({ posted: true, recorded: true })
    // reviewer-panel dimensions (architecture-reviewer:r1, code-reviewer:r1, ...): a genuinely clean
    // review needs a real verificationReceipt to avoid the receipt-fabrication fix's downgrade to low.
    return { findings: [], confidence: 'high', verificationReceipt: { artifact: 'stub', chain: [], coverageDecisionIds: [] } }
  }
}

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
  const firstStub = reviewAgentStub()
  global.agent = async (prompt, opts) => {
    promptLog.push(prompt)
    return firstStub(prompt, opts)
  }
  const runDir1 = require('fs').mkdtempSync(require('path').join(require('os').tmpdir(), 'rc-smoke-1-'))
  const r = await sr.reviewCodePhase('wi-targeted', {
    worktree: '/tmp/build-worktree',
    expectedHead: 'head-1',
    runDir: runDir1,
  })
  assert.strictEqual(r.gate, 'passed')
  assert.ok(promptLog.some((p) => p.includes('Target worktree: /tmp/build-worktree') && p.includes('Expected head: head-1')),
    'review leaves receive explicit worktree/head context')
  assert.ok(promptLog.some((p) => p.includes("cd '/tmp/build-worktree' &&") && p.includes('verify_gate.py')),
    'targeted stabilization runs the verify gate from the explicit worktree')

  promptLog = []
  const changedStub = reviewAgentStub({ verifyCommand: 'none' })
  global.agent = async (prompt, opts) => {
    promptLog.push(prompt)
    return changedStub(prompt, opts)
  }
  const runDir2 = require('fs').mkdtempSync(require('path').join(require('os').tmpdir(), 'rc-smoke-2-'))
  const changed = await sr.reviewCodePhase('wi-targeted', {
    worktree: '/tmp/build-worktree',
    expectedHead: 'head-1',
    runDir: runDir2,
  })
  assert.strictEqual(changed.gate, 'passed')
  assert.strictEqual(changed.head, 'head-2')
  assert.strictEqual(changed.changed, true)
  assert.strictEqual(changed.reviewCoverageHead, 'head-2')
  assert.ok(promptLog.some((p) => p.includes('prov_entry.py') && p.includes('--head') && p.includes('head-2')),
    'review-code restamps the post-fix final head')

  console.log('OK: panel verdict maps to gate (clean->passed, else->changes-requested)')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
