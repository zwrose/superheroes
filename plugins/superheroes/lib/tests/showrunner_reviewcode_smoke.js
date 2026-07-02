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
  // #115: reviewers RETURN {findings:[...]} (no findings-<name>.json); the synthesis leaf RETURNS
  // {verdicts:[...]}; merge/tally are in-process twins (no panel_tally.py / tally agent).
  global.agent = async (prompt, opts) => {
    promptLog.push(prompt)
    const label = opts && opts.label
    if (label === 'lib' && prompt.includes('git -C')) return 'head-1\n'
    if (label === 'resume') return '1'
    if (label === 'lib' && prompt.includes('review_code_config.py')) {
      assert.ok(prompt.includes("cd '/tmp/build-worktree' &&"), 'config resolves in the explicit target worktree')
      return { verifyCommand: 'python3 -m pytest targeted-tests -q', tiers: {} }
    }
    if (label && label.startsWith('verify')) {
      assert.ok(prompt.includes("cd '/tmp/build-worktree' &&"), 'verify gate runs from the explicit target worktree')
      // #115 Task 16: verifyAgent now emits raw run data; JS twin classifies in-process
      return { command: 'python3 -m pytest targeted-tests -q', returncode: 0, timedOut: false }
    }
    if (label && label.startsWith('synthesis')) return { verdicts: [] }
    if (label === 'lib' && prompt.includes('prov_entry.py')) return { ok: true }
    if (label && /^(architecture|code|security|test|premortem)-reviewer/.test(label)) return { findings: [] }
    return { findings: [] }
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
  assert.ok(promptLog.some((p) => p.includes('prov_entry.py') && p.includes('--worktree') && p.includes('--head')),
    'provenance restamp is bound to explicit worktree/head')

  promptLog = []
  let gitHeads = ['head-1\n', 'head-2\n']
  global.agent = async (prompt, opts) => {
    promptLog.push(prompt)
    const label = opts && opts.label
    if (label === 'lib' && prompt.includes('git -C')) return gitHeads.shift() || 'head-2\n'
    if (label === 'resume') return '1'
    if (label === 'lib' && prompt.includes('review_code_config.py')) return { verifyCommand: 'none', tiers: {} }
    if (label && label.startsWith('verify')) return { command: 'none', returncode: null, timedOut: false }
    if (label && label.startsWith('synthesis')) return { verdicts: [] }
    if (label === 'lib' && prompt.includes('prov_entry.py')) return { ok: true }
    return { findings: [] }   // every reviewer leg returns an empty findings array (clean round)
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
