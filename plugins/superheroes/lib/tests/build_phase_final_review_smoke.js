// plugins/superheroes/lib/tests/build_phase_final_review_smoke.js
const assert = require('assert')
global.log = () => {}
global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
let tally = []
function makeAgent(routes) {
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'resume') return '1'
    if (label.startsWith('tally')) return tally.shift()
    // Exact-label first (unique labels) so a short needle never shadows a longer script name.
    for (const [needle, resp] of routes) if (label === needle) return typeof resp === 'function' ? resp(prompt) : resp
    for (const [needle, resp] of routes) if (prompt.includes(needle)) return typeof resp === 'function' ? resp(prompt) : resp
    return ''
  }
}
global.reviewerAgent = async () => true
global.recordDeferred = async () => {}
const bp = require('../build_phase.js')

;(async () => {
  const routes = [
    ['verify_command_cli.py', { command: 'none' }],
    ['model_tier_resolve.py --role reviewer-deep', { model: 'opus' }],
    ['model_tier_resolve.py --role fixer', { model: 'sonnet' }],
    ['minor_rollup_cli.py', { minors: [] }],
  ]
  // Clean single-round final review -> terminal 'clean'.
  global.agent = makeAgent(routes)
  tally = [{ schemaVersion: 1, gate: 'clean', terminal: 'clean', findings: [] }]
  let r = await bp.runFinalReview('wi', 'superheroes/wi-abc')
  assert.strictEqual(r.terminal, 'clean')

  // A halted final review -> terminal 'halted' (the caller will park, UFR-4).
  global.agent = makeAgent(routes)
  tally = [{ schemaVersion: 1, gate: 'cannot-certify', terminal: 'halted', findings: [] }]
  r = await bp.runFinalReview('wi', 'superheroes/wi-abc')
  assert.strictEqual(r.terminal, 'halted')
  console.log('ok: build_phase final review clean + halted (FR-8/UFR-4)')
})()
