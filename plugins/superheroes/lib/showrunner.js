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
