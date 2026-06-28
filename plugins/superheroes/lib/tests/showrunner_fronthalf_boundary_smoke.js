// Smoke: frontHalfBoundary composes the run-outcome envelope — in-process via
// frontHalfTwin.renderRunOutcome (Task 18 rewire). Stubs io() + the loop_readout exec leaves.
// Assertions:
//   (a) returns { outcome:'parked', phase:'front-half-boundary' }
//   (b) the envelope header appears in the reason (in-process twin was called)
//   (c) NO agent call for 'render-outcome' (that agent is eliminated by Task 18)
//   (d) loop_readout.py exec is issued per phase_record (the exec leaf is preserved)
const assert = require('assert')
const sr = require('../showrunner.js')
global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}

const agentCalls = []
global.agent = async (prompt, opts) => {
  agentCalls.push({ prompt: String(prompt), label: (opts && opts.label) || '' })
  // Stub loop_readout exec leaves — return a known sentinel
  if (typeof prompt === 'string' && prompt.includes('loop_readout.py')) {
    return '## stub readout\n\n- terminal: clean\n'
  }
  return null
}

async function main() {
  agentCalls.length = 0
  const r = await sr.frontHalfBoundary('wi')
  assert.strictEqual(r.outcome, 'parked', 'the boundary parks')
  assert.strictEqual(r.phase, 'front-half-boundary', 'names the front-half boundary')
  // (b) envelope header is in the reason — produced in-process by the twin
  assert.ok(/Front-half run outcome/.test(r.reason), 'envelope header in reason (in-process twin ran)')
  // (c) NO agent call for render-outcome (that agent is eliminated in Task 18)
  const renderOutcomeCall = agentCalls.find((c) => c.prompt.includes('render-outcome'))
  assert.ok(!renderOutcomeCall, 'render-outcome agent must NOT be called after Task 18 rewire')
  // (d) loop_readout.py exec is issued (per-phase readout exec leaf is preserved)
  const readoutCall = agentCalls.find((c) => c.prompt.includes('loop_readout.py'))
  assert.ok(readoutCall, 'loop_readout.py exec must still be called (render executor preserved)')
  console.log('ok: frontHalfBoundary — in-process twin (no render-outcome agent) + loop_readout exec leaf preserved')
}
main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
