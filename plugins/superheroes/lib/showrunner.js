// plugins/superheroes/lib/showrunner.js
// Control-flow-only native Workflow (the #86 review_panel_shell.js posture): the script
// forwards decisions; every judgement is a pure Python decider or a #86 shell.
const { reviewPanel } = require('./review_panel_shell.js')

const REVIEW_CODE_REVIEWERS = [
  'architecture-reviewer', 'code-reviewer', 'security-reviewer',
  'test-reviewer', 'premortem-reviewer',
]

// The slice's derisk: review-code's 5-reviewer panel, single-pass (maxRounds:1, no auto-fix).
// reviewerAgent / recordDeferred are the #86 caller-supplied leaf wrappers.
async function runReviewCodePanel({ runDir, context, rubric, reviewerAgent, recordDeferred }) {
  global.reviewerAgent = reviewerAgent
  global.recordDeferred = recordDeferred
  return reviewPanel({
    reviewerSet: REVIEW_CODE_REVIEWERS,
    context, rubric, runKey: runDir, runDir,
    fixStep: async () => ({}),   // defer-only stub; never reached at maxRounds:1
    maxRounds: 1,
  })
}

module.exports = { runReviewCodePanel, REVIEW_CODE_REVIEWERS }

function shq(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }

// JS<->Python bridge: run a lib command in a leaf, return its stdout JSON (schema-validated).
async function cmdRunner(cmd, { schema }) {
  return agent(
    `Run exactly this command and return ONLY its stdout JSON, unchanged:\n\n${cmd}`,
    { label: 'lib', schema },
  )
}

const RECONCILE_SCHEMA = {
  type: 'object', required: ['action'],
  properties: { action: { type: 'string' }, from_step: {}, reason: { type: 'string' } },
}

// Reconcile-from-store: the leaf runs a small python that ensures the store, reads the
// checkpoint + a world snapshot, and returns recover.reconcile(...)'s action.
async function reconcile(workItem) {
  return cmdRunner(
    `python3 plugins/superheroes/lib/recover_entry.py --work-item ${shq(workItem)}`,
    { schema: RECONCILE_SCHEMA },
  )
}

async function showrunner({ workItem }) {
  const r = await reconcile(workItem)
  if (r.action === 'park_gate' || r.action === 'gate') {
    return { outcome: 'parked', phase: 'reconcile', reason: r.reason || r.action }
  }
  // 'continue' (from_step) or 'world_derive' (from_step 0) -> run the phase loop (Task 8).
  // lastGoodStep = the last *completed* phase index; resume at the next one (no re-run, FR-3).
  return runPhases(workItem, r.action === 'continue' && r.from_step != null ? Number(r.from_step) + 1 : 0)
}

// placeholder forward-declared; Task 8 implements runPhases.
async function runPhases(_workItem, _fromStep) {
  return { outcome: 'parked', phase: 'reconcile', reason: 'phase loop not yet wired' }
}

module.exports.showrunner = showrunner
module.exports.cmdRunner = cmdRunner
module.exports.reconcile = reconcile
