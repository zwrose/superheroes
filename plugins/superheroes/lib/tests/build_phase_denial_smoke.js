require('./_smoke_checkout_root.js')
// plugins/superheroes/lib/tests/build_phase_denial_smoke.js
// UFR-6/UFR-8: a build leaf whose 15-min timeout denied a SUBSTANTIVE step (not a verification
// probe) reports it honestly via `deniedAction` in its JSON. buildOneTask must record that denial
// via prov_entry's `--step build-denial` leaf (ship_gate.record_build_denial) so the provenance is
// tainted and the ship gate (ship_gate.decide) later GATEs — REGARDLESS of whether the leaf still
// finished the rest of the task with ok:true. Also pins the leaf prompt actually asks for the field
// (the review-side finding: a flag nobody is instructed to emit is unreachable).
const assert = require('assert')
const { routeMatches } = require('./_task_leaf_route.js')
global.log = () => {}
function makeAgent(routes) {
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    for (const [needle, resp] of routes) {
      if (routeMatches(label, needle)) return typeof resp === 'function' ? resp(prompt) : resp
    }
    for (const [needle, resp] of routes) if (prompt.includes(needle)) return typeof resp === 'function' ? resp(prompt) : resp
    if (opts && opts.courier) { for (const [needle, resp] of routes) if (needle === 'exec') return typeof resp === 'function' ? resp(prompt) : resp }
    return ''
  }
}
const bp = require('../build_phase.js')
const TASK = { id: '9', title: 'Denied step' }

function execRoute(captures, order) {
  return ['exec', (prompt) => {
    if (prompt.includes('prov_entry.py --step build-denial')) {
      if (captures) captures.push(prompt)
      if (order) order.push('prov')
      return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
    }
    let stdout = '{}'
    if (prompt.includes('build_state_cli.py gather')) stdout = JSON.stringify({ unmapped_commits: 0 })
    else if (prompt.includes('fence_cli.py')) stdout = JSON.stringify({ ok: true })
    else if (prompt.includes('journal_entry.py')) {
      if (order && prompt.includes('permission_denied')) order.push('journal')
      stdout = JSON.stringify({ ok: true })
    }
    return [{ index: 0, ok: true, stdout }]
  }]
}

;(async () => {
  // (1) buildLeafPrompt itself asks for deniedAction (the missing-instruction finding).
  const leafPrompt = bp.buildLeafPrompt({ wt: '/tmp/wt', branch: 'feat/x', task: { id: '9', title: 'Denied step' } })
  assert.ok(/deniedAction/.test(leafPrompt), 'the leaf prompt names the deniedAction field')
  assert.ok(/never fabricate a completed step/i.test(leafPrompt), 'the leaf prompt forbids fabricating a denied step as done')

  // (2) A leaf reporting deniedAction (even with ok:true) must record the denial via prov_entry.
  //     DUAL-CARRIER ordering (premortem-001): the best-effort journal `permission_denied` event
  //     must be written BEFORE the fail-closed provenance write, so the denial survives even if the
  //     provenance write later fails and the task parks (a resume skips the already-committed leaf).
  const calls = []
  const order = []
  global.agent = makeAgent([
    execRoute(calls, order),
    ['implement-task', { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true }, deniedAction: 'could not run the migration script' }],
    ['task-reviewer:r', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }],
    ['record task built', [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true, task: '9' }) }]],
    ['record task reviewed', [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true, task: '9' }) }]],
  ])
  const r = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '9', '/tmp/wt', 1)
  assert.strictEqual(r.parked, false, 'a denied-but-otherwise-ok task still completes the build step (the gate, not the build loop, holds it back)')
  assert.strictEqual(calls.length, 1, 'exactly one build-denial provenance write fires')
  assert.ok(calls[0].includes("--denied-step 'build:9'"), 'the denial is tagged with the task id')
  assert.ok(calls[0].includes('could not run the migration script'), 'the denied action text is recorded')
  assert.deepStrictEqual(order, ['journal', 'prov'],
    'the best-effort journal carrier is written BEFORE the fail-closed provenance write (dual-carrier ordering)')

  // (3) A clean task (no deniedAction) never calls build-denial.
  const cleanCalls = []
  global.agent = makeAgent([
    execRoute(cleanCalls),
    ['implement-task', { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } }],
    ['task-reviewer:r', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }],
    ['record task built', [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true, task: '9' }) }]],
    ['record task reviewed', [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true, task: '9' }) }]],
  ])
  const r2 = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '9', '/tmp/wt', 1)
  assert.strictEqual(r2.parked, false, 'a clean task completes')
  assert.strictEqual(cleanCalls.length, 0, 'no denial recorded for a clean task')

  // (4) FR-1 finality: a denial reported on a FAILING attempt (ok:false, needs_context) is remembered and
  //     threaded into the RE-DISPATCH's prompt so the fresh leaf never re-attempts the denied action; the
  //     reported denial is recorded once and never lost.
  const finalityCalls = []
  const implPrompts = []
  let implCall = 0
  global.agent = makeAgent([
    execRoute(finalityCalls),
    ['implement-task', (prompt) => {
      implPrompts.push(prompt)
      implCall += 1
      // Attempt 1: the timeout denied a substantive step AND the leaf needs context (a re-dispatch).
      if (implCall === 1) return { ok: false, signal: 'needs_context', evidence: { testFailed: false, testPassed: false }, deniedAction: 'run the DB migration' }
      // Attempt 2 (the re-dispatch): completes, no new denial.
      return { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } }
    }],
    ['task-reviewer:r', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }],
    ['record task built', [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true, task: '9' }) }]],
    ['record task reviewed', [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true, task: '9' }) }]],
  ])
  const r3 = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '9', '/tmp/wt', 1)
  assert.strictEqual(r3.parked, false, 'the task completes on the retry after the first attempt was denied+needs_context')
  assert.strictEqual(implPrompts.length, 2, 'two build dispatches: the denied first attempt, then the re-dispatch')
  assert.ok(!implPrompts[0].includes('already denied by the permission timeout'),
    'the FIRST dispatch carries NO denial memory (nothing denied yet)')
  assert.ok(implPrompts[1].includes('already denied by the permission timeout'),
    'the RE-DISPATCH carries the FR-1 denial memory (denied action is FINAL)')
  assert.ok(implPrompts[1].includes('run the DB migration'),
    'the denial memory names the specific denied action X, so the fresh leaf works around it')
  assert.strictEqual(finalityCalls.length, 1,
    'the reported denial is recorded EXACTLY once (per attempt that reported it) — never lost, never doubled')
  assert.ok(finalityCalls[0].includes('run the DB migration'), 'the recorded build-denial names the denied action')

  // (5) premortem-001: the build-denial provenance write is fail-CLOSED. A durable-write failure
  //     (stdout {ok:false}) — or a dropped courier — must PARK the task (record-before-advance), never
  //     silently promote a tainted build to a ready PR (the ship gate reads ONLY provenance.buildDenials).
  const failRoute = ['exec', (prompt) => {
    if (prompt.includes('prov_entry.py --step build-denial')) {
      return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: false, error: 'garbled provenance.json' }) }]
    }
    let stdout = '{}'
    if (prompt.includes('build_state_cli.py gather')) stdout = JSON.stringify({ unmapped_commits: 0 })
    else if (prompt.includes('fence_cli.py')) stdout = JSON.stringify({ ok: true })
    else if (prompt.includes('journal_entry.py')) stdout = JSON.stringify({ ok: true })
    return [{ index: 0, ok: true, stdout }]
  }]
  global.agent = makeAgent([
    failRoute,
    ['implement-task', { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true }, deniedAction: 'could not run the migration script' }],
    ['task-reviewer:r', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }],
    ['record task built', [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true, task: '9' }) }]],
    ['record task reviewed', [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true, task: '9' }) }]],
  ])
  const r4 = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '9', '/tmp/wt', 1)
  assert.strictEqual(r4.parked, true, 'a failed build-denial provenance write PARKS the task (fail-closed, record-before-advance)')
  assert.ok(/build-denial record write failed/.test(r4.reason), 'the park reason names the failed build-denial record write')
  // premortem-001: on a correlated double-drop the park reason is the only surviving disclosure, so it
  // must name the specific denied action (reaching the resuming owner through the park channel).
  assert.ok(/could not run the migration script/.test(r4.reason),
    'the park reason names the denied action so a double-carrier-drop denial still discloses through the park channel')

  console.log('ok: build leaf deniedAction is instructed + recorded via prov_entry build-denial (fail-CLOSED on a failed write) + journaled for the readout + FR-1 finality memory threads a denied action into the re-dispatch (UFR-6/UFR-8, UFR-3, FR-1)')
})()
