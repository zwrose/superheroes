// Smoke: frontHalfBoundary composes the run-outcome envelope — it calls front_half render-outcome and
// returns a parked result naming the front-half boundary. Stubs the render leaf.
const assert = require('assert')
const sr = require('../showrunner.js')
global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}

let calledRender = false
global.agent = async (prompt, opts) => {
  if (prompt.includes('render-outcome')) { calledRender = true; return '# Front-half run outcome\n\n**Completed phases:** plan, review-plan, tasks, review-tasks\n' }
  return null
}

async function main() {
  const r = await sr.frontHalfBoundary('wi')
  assert.strictEqual(r.outcome, 'parked', 'the boundary parks')
  assert.strictEqual(r.phase, 'front-half-boundary', 'names the front-half boundary')
  assert.ok(calledRender, 'render_run_outcome was invoked (envelope composed, not dead code)')
  assert.ok(/Completed phases/.test(r.reason), 'the rendered envelope is the park reason')
  console.log('ok: frontHalfBoundary composes the run-outcome envelope')
}
main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
