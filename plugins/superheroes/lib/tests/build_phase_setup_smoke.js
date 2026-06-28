// plugins/superheroes/lib/tests/build_phase_setup_smoke.js
// #115 increment A: read-gate / build_entry.py / task_list_cli.py are ported to exec(raw)+parse.
// They route through the single 'exec' label; the stub inspects the exec PROMPT (which lists the
// command) to choose the stdout. read-gate returns a PLAIN STRING (not JSON).
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

// execRoute(map): a single 'exec' route. `map` is a function(prompt) -> raw stdout string.
function execRoute(map) {
  return ['exec', (prompt) => [{ index: 0, ok: true, stdout: map(prompt) }]]
}

;(async () => {
  // Zero-task: gate passed, setup returns a branch, task_list returns [] -> finish (UFR-8).
  global.agent = makeAgent([
    execRoute((p) => {
      if (p.includes('read-gate')) return 'passed'               // PLAIN STRING leaf
      if (p.includes('build_entry.py')) return JSON.stringify({ branch: 'superheroes/wi-abc', path: '/tmp/wt' })
      if (p.includes('task_list_cli.py')) return JSON.stringify({ tasks: [] })
      return '{}'
    }),
  ])
  let r = await bp.buildPhase('wi', 5)
  assert.strictEqual(r.confidence, 'high')
  assert.ok(logs.some((m) => /no tasks to build/i.test(m)), 'UFR-8 log')

  // Un-passed tasks gate -> park (UFR-1), no branch.
  global.agent = makeAgent([execRoute((p) => (p.includes('read-gate') ? 'pending' : '{}'))])
  r = await bp.buildPhase('wi', 5)
  assert.strictEqual(r.confidence, 'low')

  // Gate leaf FAILS to run (ok:false) -> park (fail closed), not a silent build.
  global.agent = makeAgent([['exec', () => [{ index: 0, ok: false, stdout: 'leaf crashed' }]]])
  r = await bp.buildPhase('wi', 5)
  assert.strictEqual(r.confidence, 'low')
  assert.ok(/read the tasks gate/i.test((r.assumptions || [])[0] || ''), 'honest gate fail-closed reason')

  // Failed setup (no branch) -> park (UFR-2).
  global.agent = makeAgent([
    execRoute((p) => {
      if (p.includes('read-gate')) return 'passed'
      if (p.includes('build_entry.py')) return JSON.stringify({ error: 'buildtree preserve_notify' })
      return '{}'
    }),
  ])
  r = await bp.buildPhase('wi', 5)
  assert.strictEqual(r.confidence, 'low')
  console.log('ok: build_phase setup/enumerate (UFR-1/2/8, exec fail-closed)')
})()
