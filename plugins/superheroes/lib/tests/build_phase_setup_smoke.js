require('./_smoke_checkout_root.js')
// plugins/superheroes/lib/tests/build_phase_setup_smoke.js
// #115 increment A: read-gate / build_entry.py / task_list_cli.py are ported to exec(raw)+parse.
// They route through the single 'exec' label; the stub inspects the exec PROMPT (which lists the
// command) to choose the stdout. read-gate rides `--json` ({"review": "..."}) so the answer takes
// the fence-tolerant JSON leg — the plain-string mode parked live run 9 (wf_b69571d9) when the
// courier fenced its verbatim answer.
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
    if (opts && opts.courier) { for (const [needle, resp] of routes) if (needle === 'exec') return typeof resp === 'function' ? resp(prompt) : resp }
    return ''
  }
}
const bp = require('../build_phase.js')

// execRoute(map): a single 'exec' route. `map` is a function(prompt) -> raw stdout string.
function execRoute(map) {
  return ['exec', (prompt) => [{ ok: true, stdout: map(prompt) }]]
}
function gatherRoute(map) {
  return ['gather build state', (prompt) => [{ ok: true, stdout: map(prompt) }]]
}

;(async () => {
  // Zero-task: gate passed, setup returns a branch, task_list returns [] -> finish (UFR-8).
  global.agent = makeAgent([
    execRoute((p) => {
      // Run-9 adversarial shape: the courier FENCES its verbatim JSON answer. extractJson must
      // still accept it (the old plain-string leg compared the fenced text and false-parked).
      if (p.includes('read-gate')) return '```json\n{"review": "passed"}\n```'
      if (p.includes('build_entry.py')) return JSON.stringify({ branch: 'superheroes/wi-abc', path: '/tmp/wt' })
      if (p.includes('task_list_cli.py')) return JSON.stringify({ tasks: [] })
      return '{}'
    }),
  ])
  let r = await bp.buildPhase('wi', 5)
  assert.strictEqual(r.confidence, 'high')
  assert.ok(logs.some((m) => /no tasks to build/i.test(m)), 'UFR-8 log')

  // Un-passed tasks gate -> park (UFR-1), no branch — the reason names the actual gate value.
  global.agent = makeAgent([execRoute((p) => (p.includes('read-gate') ? '{"review": "pending"}' : '{}'))])
  r = await bp.buildPhase('wi', 5)
  assert.strictEqual(r.confidence, 'low')
  assert.ok(/tasks gate not passed \(pending\)/.test((r.assumptions || [])[0] || ''), 'UFR-1 park names the gate value')

  // Gate leaf FAILS to run (ok:false) -> park (fail closed), not a silent build.
  global.agent = makeAgent([['exec', () => [{ index: 0, ok: false, stdout: 'leaf crashed' }]]])
  r = await bp.buildPhase('wi', 5)
  assert.strictEqual(r.confidence, 'low')
  assert.ok(/could not read the tasks gate/i.test((r.assumptions || [])[0] || ''), 'honest gate fail-closed reason')

  // Failed setup (no branch) -> park (UFR-2).
  global.agent = makeAgent([
    execRoute((p) => {
      if (p.includes('read-gate')) return '{"review": "passed"}'
      if (p.includes('build_entry.py')) return JSON.stringify({ error: 'buildtree preserve_notify' })
      return '{}'
    }),
  ])
  r = await bp.buildPhase('wi', 5)
  assert.strictEqual(r.confidence, 'low')

  // C-I3: an unresolvable --base makes the gather leaf emit a STRUCTURED {error:...} on stdout.
  // gatherState surfaces it as {__error}; buildPhase parks with THAT specific reason — not the
  // generic 'could not gather authoritative git state' (which would misdirect the owner).
  const baseErr = "--base 'no-such-base' could not be resolved in /tmp/wt (tried local and origin/<branch>) — failing closed"
  global.agent = makeAgent([
    execRoute((p) => {
      if (p.includes('read-gate')) return '{"review": "passed"}'
      if (p.includes('build_entry.py')) return JSON.stringify({ branch: 'superheroes/wi-abc', path: '/tmp/wt' })
      if (p.includes('task_list_cli.py')) return JSON.stringify({ tasks: [{ id: '1', title: 'One' }], raw_task_heading_count: 1 })
      return '{}'
    }),
    gatherRoute(() => JSON.stringify({ error: baseErr })),
  ])
  r = await bp.buildPhase('wi', 5)
  assert.strictEqual(r.confidence, 'low')
  assert.strictEqual((r.assumptions || [])[0], baseErr,
    'buildPhase must park with the SPECIFIC base-resolution reason, not the generic gather park')

  // gatherState() surfaces the structured error directly as {__error}.
  global.agent = makeAgent([gatherRoute(() => JSON.stringify({ error: baseErr }))])
  const gs = await bp.gatherState('wi', 'superheroes/wi-abc', '1', '/tmp/wt')
  assert.deepStrictEqual(gs, { __error: baseErr }, 'gatherState surfaces {__error} from a structured leaf error')

  // A normal successful gather (no error key) still returns the full state object unchanged.
  global.agent = makeAgent([
    gatherRoute(() => JSON.stringify({ committed_task_ids: ['1'], unmapped_commits: 0, review_records: {}, worktree_dirty: false, final_review: null, provenance: 'absent' })),
  ])
  const gs2 = await bp.gatherState('wi', 'superheroes/wi-abc', '1', '/tmp/wt')
  assert.strictEqual(gs2.__error, undefined, 'normal gather has no __error')
  assert.deepStrictEqual(gs2.committed_task_ids, ['1'], 'normal gather returns the state object')

  console.log('ok: build_phase setup/enumerate (UFR-1/2/8, exec fail-closed, C-I3 base error surfaced)')
})()
