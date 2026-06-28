// plugins/superheroes/lib/tests/build_phase_tasklist_shape_smoke.js
// Guards for BUG-2 (schema lets tasks be a string) and BUG-3 (string "[]" passes .length===0 but
// crashes .map), plus the silent-zero park guard (raw_task_heading_count > 0 but tasks:[]).
const assert = require('assert')
const logs = []
global.log = (m) => logs.push(m)
function makeAgent(routes) {
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    for (const [needle, resp] of routes) if (label === needle) return typeof resp === 'function' ? resp(prompt) : resp
    for (const [needle, resp] of routes) if (prompt.includes(needle)) return typeof resp === 'function' ? resp(prompt) : resp
    return ''
  }
}
const bp = require('../build_phase.js')

;(async () => {
  // ===========================================================================
  // (1) BUG-3: task-list leaf returns {tasks: "[]"} (string, not array).
  //     build_phase must NOT crash on .map over the string. It must fail closed
  //     (park) — a non-array tasks value is unrecoverable at this point.
  // ===========================================================================
  logs.length = 0
  global.agent = makeAgent([
    ['read-gate --doc tasks', 'passed'],
    ['build_entry.py', { branch: 'superheroes/wi-abc', path: '/tmp/wt' }],
    ['task_list_cli.py', { tasks: '[]', raw_task_heading_count: 0 }],
  ])
  let r = await bp.buildPhase('wi', 5)
  // With tasks as a string '[]': length===2 so tasks.length===0 is FALSE — without the fix
  // it crashes .map. After the fix it must park (or treat as zero tasks if string parses to []).
  // Either outcome is acceptable; the key property is NO CRASH (no unhandled rejection).
  assert.ok(
    r && (r.confidence === 'low' || r.confidence === 'high'),
    'BUG-3: tasks:"[]" (string) must not crash — got: ' + JSON.stringify(r)
  )
  console.log('ok: BUG-3 tasks:"[]" string does not crash (result confidence=' + r.confidence + ')')

  // ===========================================================================
  // (2) BUG-3 variant: task-list returns {tasks: "[{\"id\":\"1\",\"title\":\"A\"}]"} (non-empty string).
  //     Without fix, .map crashes. After fix: recovered or parked, never throws.
  // ===========================================================================
  logs.length = 0
  global.agent = makeAgent([
    ['read-gate --doc tasks', 'passed'],
    ['build_entry.py', { branch: 'superheroes/wi-abc', path: '/tmp/wt' }],
    // tasks is a JSON string of a one-item array — a real derailment scenario
    ['task_list_cli.py', { tasks: '[{"id":"1","title":"A"}]', raw_task_heading_count: 1 }],
  ])
  let threw = false
  try {
    r = await bp.buildPhase('wi', 5)
  } catch (e) {
    threw = true
  }
  assert.ok(!threw, 'BUG-3 non-empty string: must not throw unhandled exception')
  console.log('ok: BUG-3 non-empty string tasks does not throw')

  // ===========================================================================
  // (3) Silent-zero park guard: tasks:[] but raw_task_heading_count > 0.
  //     This means the doc has task headings but the parser returned nothing — format mismatch.
  //     build_phase must PARK with a descriptive reason rather than silently finish (UFR-8 bypass).
  // ===========================================================================
  logs.length = 0
  global.agent = makeAgent([
    ['read-gate --doc tasks', 'passed'],
    ['build_entry.py', { branch: 'superheroes/wi-abc', path: '/tmp/wt' }],
    ['task_list_cli.py', { tasks: [], raw_task_heading_count: 3 }],
  ])
  r = await bp.buildPhase('wi', 5)
  assert.strictEqual(r.confidence, 'low',
    'silent-zero guard: tasks:[] + raw_task_heading_count:3 must park, not finish silently')
  const reason = (r.assumptions || [])[0] || ''
  assert.ok(
    /format mismatch|parseable|heading/i.test(reason),
    'silent-zero park reason must mention format mismatch; got: ' + reason
  )
  console.log('ok: silent-zero park guard (tasks:[] + raw_task_heading_count:3 -> low, reason: "' + reason + '")')

  // ===========================================================================
  // (4) Genuine empty task list (tasks:[] + raw_task_heading_count:0) -> finish ok (UFR-8 intact).
  //     This is the real "nothing to build" case; the guard must NOT incorrectly park it.
  // ===========================================================================
  logs.length = 0
  global.agent = makeAgent([
    ['read-gate --doc tasks', 'passed'],
    ['build_entry.py', { branch: 'superheroes/wi-abc', path: '/tmp/wt' }],
    ['task_list_cli.py', { tasks: [], raw_task_heading_count: 0 }],
  ])
  r = await bp.buildPhase('wi', 5)
  assert.strictEqual(r.confidence, 'high',
    'genuine empty task list must still finish ok (UFR-8)')
  console.log('ok: genuine empty task list (UFR-8) still finishes ok after guard')

  // ===========================================================================
  // (5) Normal array tasks -> proceeds normally (regression / sanity check).
  //     Just the enumerate path — does NOT go all the way through the task loop.
  //     Stubs only through gather-entry so it parks at "park: build_progress parked"
  //     (unmapped commit); the point is tasks.map does NOT crash.
  // ===========================================================================
  logs.length = 0
  global.agent = makeAgent([
    ['read-gate --doc tasks', 'passed'],
    ['build_entry.py', { branch: 'superheroes/wi-abc', path: '/tmp/wt' }],
    ['task_list_cli.py', { tasks: [{ id: '1', title: 'A' }], raw_task_heading_count: 1 }],
    // unmapped_commits > 0 -> reconcile (twin) returns park immediately after entry gather
    ['gather-entry', { committed_task_ids: [], unmapped_commits: 1, worktree_dirty: false }],
  ])
  threw = false
  try {
    r = await bp.buildPhase('wi', 5)
  } catch (e) {
    threw = true
  }
  assert.ok(!threw, 'normal array tasks: must not throw')
  assert.strictEqual(r.confidence, 'low')    // parked at reconcile (expected)
  console.log('ok: normal array tasks shape does not crash build_phase')

  console.log('ALL build_phase_tasklist_shape smoke tests passed')
})()
