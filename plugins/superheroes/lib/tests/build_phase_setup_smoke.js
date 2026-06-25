// plugins/superheroes/lib/tests/build_phase_setup_smoke.js
const assert = require('assert')
const logs = []
global.log = (m) => logs.push(m)
// Route an agent() call by the first matching needle found in its prompt OR its label.
function makeAgent(routes) {
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    // Exact-label first (unique labels) so a short needle never shadows a longer script name.
    for (const [needle, resp] of routes) if (label === needle) return typeof resp === 'function' ? resp(prompt) : resp
    for (const [needle, resp] of routes) if (prompt.includes(needle)) return typeof resp === 'function' ? resp(prompt) : resp
    return ''
  }
}
const bp = require('../build_phase.js')

;(async () => {
  // Zero-task: gate passed, setup returns a branch, task_list returns [] -> finish (UFR-8).
  global.agent = makeAgent([
    ['read-gate --doc tasks', 'passed'],
    ['build_entry.py', { branch: 'superheroes/wi-abc', path: '/tmp/wt' }],
    ['task_list_cli.py', { tasks: [] }],
  ])
  let r = await bp.buildPhase('wi', 5)
  assert.strictEqual(r.confidence, 'high')
  assert.ok(logs.some((m) => /no tasks to build/i.test(m)), 'UFR-8 log')

  // Un-passed tasks gate -> park (UFR-1), no branch.
  global.agent = makeAgent([['read-gate --doc tasks', 'pending']])
  r = await bp.buildPhase('wi', 5)
  assert.strictEqual(r.confidence, 'low')

  // Failed setup (no branch) -> park (UFR-2).
  global.agent = makeAgent([
    ['read-gate --doc tasks', 'passed'],
    ['build_entry.py', { error: 'buildtree preserve_notify' }],
  ])
  r = await bp.buildPhase('wi', 5)
  assert.strictEqual(r.confidence, 'low')
  console.log('ok: build_phase setup/enumerate (UFR-1/2/8)')
})()
