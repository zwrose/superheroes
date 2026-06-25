// plugins/superheroes/lib/tests/build_phase_loop_smoke.js
const assert = require('assert')
global.log = () => {}
function makeAgent(routes) {
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    // Exact-label first (labels are unique), so a short needle never shadows a longer script name
    // via substring; then a prompt-substring fallback. A function resp receives the prompt (capture).
    for (const [needle, resp] of routes) if (label === needle) return typeof resp === 'function' ? resp(prompt) : resp
    for (const [needle, resp] of routes) if (prompt.includes(needle)) return typeof resp === 'function' ? resp(prompt) : resp
    return ''
  }
}
const bp = require('../build_phase.js')
const BASE = [
  ['read-gate --doc tasks', 'passed'],
  ['build_entry.py', { branch: 'superheroes/wi-abc', path: '/tmp/wt' }],
  ['task_list_cli.py', { tasks: [{ id: '1', title: 'A' }] }],
  ['build_state_cli.py gather', { committed_task_ids: ['1'], unmapped_commits: 0 }],
]

;(async () => {
  // (1) reconcile says write_provenance then complete -> provenance written exactly once (FR-9).
  let provWrites = 0
  let progress = [{ action: 'write_provenance' }, { action: 'complete' }]
  global.agent = makeAgent([...BASE,
    ['build_progress_cli.py', () => progress.shift()],
    ['prov_entry.py', () => { provWrites += 1; return { ok: true } }],
  ])
  let r = await bp.buildPhase('wi', 5)
  assert.strictEqual(r.confidence, 'high')
  assert.strictEqual(provWrites, 1, 'provenance written exactly once (FR-9)')

  // (2) provenance write fails -> park (UFR-6).
  progress = [{ action: 'write_provenance' }]
  global.agent = makeAgent([...BASE,
    ['build_progress_cli.py', () => progress.shift()],
    ['prov_entry.py', { ok: false, error: 'disk' }],
  ])
  r = await bp.buildPhase('wi', 5)
  assert.strictEqual(r.confidence, 'low', 'provenance write failure parks (UFR-6)')

  // (3) reconcile says park -> park (e.g. unmapped commit / garbled provenance).
  progress = [{ action: 'park', reason: 'unmapped commit' }]
  global.agent = makeAgent([...BASE, ['build_progress_cli.py', () => progress.shift()]])
  r = await bp.buildPhase('wi', 5)
  assert.strictEqual(r.confidence, 'low')

  // (4) reset_uncommitted: fence ok + reset ok -> loop continues to complete (UFR-12).
  let resets = 0
  progress = [{ action: 'reset_uncommitted' }, { action: 'complete' }]
  global.agent = makeAgent([...BASE,
    ['build_progress_cli.py', () => progress.shift()],
    ['fence_cli.py', { ok: true }],
    ['reset-uncommitted', () => { resets += 1; return { ok: true } }],
  ])
  r = await bp.buildPhase('wi', 5)
  assert.strictEqual(r.confidence, 'high')
  assert.strictEqual(resets, 1, 'reset ran once before completing (UFR-12)')

  // (5) reset fails -> park honestly (UFR-6), not a generic guard-bound park.
  progress = [{ action: 'reset_uncommitted' }]
  global.agent = makeAgent([...BASE,
    ['build_progress_cli.py', () => progress.shift()],
    ['fence_cli.py', { ok: true }],
    ['reset-uncommitted', { ok: false, error: 'dirty submodule' }],
  ])
  r = await bp.buildPhase('wi', 5)
  assert.strictEqual(r.confidence, 'low', 'a failed reset parks (UFR-6)')
  assert.ok(/could not reset/i.test((r.assumptions || [])[0] || ''), 'honest reset-failure reason')

  console.log('ok: build_phase reconcile loop (FR-9/UFR-6/UFR-12)')
})()
