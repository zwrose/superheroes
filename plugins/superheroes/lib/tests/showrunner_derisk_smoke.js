// plugins/superheroes/lib/tests/showrunner_derisk_smoke.js
// Dev-time only (node, not CI): proves reviewPanel composes single-pass inside showrunner.
const assert = require('assert')
const path = require('path')

// Inject the #86 globals the shell expects, then require the modules.
const calls = { reviewers: [], tally: 0 }
global.parallel = (thunks) => Promise.all(thunks.map((t) => t()))
global.agent = async (_prompt, _opts) =>
  // the tally leaf: panel_tally with a single clean round -> terminal 'clean'
  ({ gate: 'clean', confidence: 'high', findings: [], terminal: 'clean' })
global.log = () => {}

const shell = require('../review_panel_shell.js')
// caller-supplied leaf wrappers (the #86 consumer contract)
global.reviewerAgent = async (r) => { calls.reviewers.push(r); return true }
global.recordDeferred = async () => {}

const { runReviewCodePanel } = require('../showrunner.js')

;(async () => {
  const verdict = await runReviewCodePanel({
    runDir: '/tmp/derisk-smoke', context: 'ctx', rubric: 'rub',
    reviewerAgent: global.reviewerAgent, recordDeferred: global.recordDeferred,
  })
  assert.strictEqual(verdict.terminal, 'clean', 'single-pass clean verdict expected')
  assert.deepStrictEqual(
    calls.reviewers.sort(),
    ['architecture-reviewer', 'code-reviewer', 'premortem-reviewer',
     'security-reviewer', 'test-reviewer'].sort(),
    'all 5 review-code reviewers fanned out',
  )
  console.log('OK: reviewPanel composed single-pass with the 5 reviewers')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
