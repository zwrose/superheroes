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

function execRoute(captures) {
  return ['exec', (prompt) => {
    if (prompt.includes('prov_entry.py --step build-denial')) {
      if (captures) captures.push(prompt)
      return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
    }
    let stdout = '{}'
    if (prompt.includes('build_state_cli.py gather')) stdout = JSON.stringify({ unmapped_commits: 0 })
    else if (prompt.includes('fence_cli.py')) stdout = JSON.stringify({ ok: true })
    else if (prompt.includes('journal_entry.py')) stdout = JSON.stringify({ ok: true })
    return [{ index: 0, ok: true, stdout }]
  }]
}

;(async () => {
  // (1) buildLeafPrompt itself asks for deniedAction (the missing-instruction finding).
  const leafPrompt = bp.buildLeafPrompt({ wt: '/tmp/wt', branch: 'feat/x', task: { id: '9', title: 'Denied step' } })
  assert.ok(/deniedAction/.test(leafPrompt), 'the leaf prompt names the deniedAction field')
  assert.ok(/never fabricate a completed step/i.test(leafPrompt), 'the leaf prompt forbids fabricating a denied step as done')

  // (2) A leaf reporting deniedAction (even with ok:true) must record the denial via prov_entry.
  const calls = []
  global.agent = makeAgent([
    execRoute(calls),
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

  console.log('ok: build leaf deniedAction is instructed + recorded via prov_entry build-denial (UFR-6/UFR-8)')
})()
