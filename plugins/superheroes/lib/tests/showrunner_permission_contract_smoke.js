// plugins/superheroes/lib/tests/showrunner_permission_contract_smoke.js
// Task 11 (FR-1, FR-4, UFR-6): every dispatched leaf/reviewer prompt string carries BOTH
//   (a) the FR-4 probe steering — name the throwaway-test-file-in-worktree + allowed test-run family as
//       the required probe shape and explicitly discourage inline interpreter probes; and
//   (b) the 15-minute proceed contract — "if an action awaits owner permission with no response for 15
//       minutes, proceed without it and report the denied action honestly (never as done)."
// The reviewer prompt carries the steering (its probes are the throwaway-test shape) + the 15-min
// contract; the builder/leaf prompt carries the 15-min contract (its whole job is committing work).
// Run: node plugins/superheroes/lib/tests/showrunner_permission_contract_smoke.js
const assert = require('assert')
const sr = require('../showrunner.js')
const bp = require('../build_phase.js')

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}

// ---------------------------------------------------------------------------
// (1) Reviewer prompt: capture the ACTUAL dispatched string via a stubbed agent.
// ---------------------------------------------------------------------------
async function reviewerPromptEmbedsBothBlocks() {
  let reviewerPrompt = null
  global.agent = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (/-reviewer:r\d+/.test(label)) { reviewerPrompt = prompt }
    return { findings: [], confidence: 'high' }
  }
  const leaves = sr.reviewCodeLeaves({ reviewer: 'sonnet', reviewerDeep: 'opus' }, {})
  await leaves.reviewerAgent('code-reviewer', { workItem: 'wi-x' }, 'code', '/tmp/run', 1, { tier: 'reviewer' })
  assert.ok(reviewerPrompt, 'the reviewer prompt was dispatched')
  // (a) FR-4 steering.
  assert.ok(reviewerPrompt.includes('throwaway test file'),
    'reviewer prompt names the throwaway test file probe shape')
  assert.ok(reviewerPrompt.includes('do not improvise inline'),
    'reviewer prompt discourages inline interpreter probes')
  // (b) 15-minute proceed contract.
  assert.ok(reviewerPrompt.includes('15 minutes'),
    'reviewer prompt states the 15-minute bound')
  assert.ok(reviewerPrompt.includes('report the denied action'),
    'reviewer prompt requires honest reporting of the denied action')
}

// ---------------------------------------------------------------------------
// (2) Builder/leaf prompt: the exact string the build phase dispatches (single-source helper).
// ---------------------------------------------------------------------------
function leafPromptEmbedsTimeoutContract() {
  const leafPrompt = bp.buildLeafPrompt({
    wt: '/some/wt', branch: 'feat/x', task: { id: '7', title: 'Do the thing' },
  })
  assert.ok(leafPrompt.includes('Task 7'), 'leaf prompt names the task (sanity)')
  assert.ok(leafPrompt.includes('15 minutes'),
    'leaf prompt states the 15-minute bound')
  assert.ok(leafPrompt.includes('report the denied action'),
    'leaf prompt requires honest reporting of the denied action (never as done)')
}

// ---------------------------------------------------------------------------
// (3) The two contract blocks are shared constants (single source of truth), not re-typed per prompt.
// ---------------------------------------------------------------------------
function contractConstantsExported() {
  assert.strictEqual(typeof sr.PROBE_STEERING, 'string', 'PROBE_STEERING constant is exported')
  assert.strictEqual(typeof sr.TIMEOUT_PROCEED_CONTRACT, 'string', 'TIMEOUT_PROCEED_CONTRACT is exported')
  assert.ok(sr.PROBE_STEERING.includes('throwaway test file'))
  assert.ok(sr.PROBE_STEERING.includes('do not improvise inline'))
  assert.ok(sr.TIMEOUT_PROCEED_CONTRACT.includes('15 minutes'))
  assert.ok(sr.TIMEOUT_PROCEED_CONTRACT.includes('report the denied action'))
}

async function main() {
  await reviewerPromptEmbedsBothBlocks()
  leafPromptEmbedsTimeoutContract()
  contractConstantsExported()
  console.log('ok: reviewer + builder/leaf prompts embed FR-4 probe steering + 15-min proceed contract')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
