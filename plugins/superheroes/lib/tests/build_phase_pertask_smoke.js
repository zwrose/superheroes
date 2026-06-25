// plugins/superheroes/lib/tests/build_phase_pertask_smoke.js
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
const TASK = { id: '1', title: 'A' }

;(async () => {
  // (1) Clean: fence ok, worker ok, trailer-check clean (scored against the FULL valid-id set '1,2'),
  //     reviewer two verdicts clean -> complete. Capture the gather call to PIN the valid-ids threading.
  let gatherPrompt = ''
  global.agent = makeAgent([
    ['build_state_cli.py gather', (p) => { gatherPrompt = p; return { unmapped_commits: 0 } }],
    ['fence_cli.py', { ok: true }],
    ['journal_entry.py', { ok: true }],
    ['model_tier_resolve.py', { model: 'sonnet' }],
    ['record-reviewed', { ok: true }],
    ['worker', { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } }],
    ['review', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }],
    ['task_review_cli.py', { action: 'complete', blocking: [], minors: [], cannot_verify: [] }],
  ])
  let r = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '1,2')
  assert.strictEqual(r.parked, false, 'a clean task should not park')
  assert.ok(gatherPrompt.includes("--valid-ids '1,2'"),
    'the write-time trailer check must score against the FULL valid-id set, not just this task')

  // (2) Worker stuck (plan_wrong) -> recovery says park (UFR-3).
  global.agent = makeAgent([
    ['fence_cli.py', { ok: true }],
    ['worker_recovery_cli.py', { action: 'park', reason: 'plan wrong' }],
    ['worker', { ok: false, signal: 'plan_wrong' }],
  ])
  r = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '1')
  assert.strictEqual(r.parked, true, 'worker plan_wrong should park (UFR-3)')

  // (3) Review parks (cap reached) -> park (UFR-4).
  global.agent = makeAgent([
    ['fence_cli.py', { ok: true }],
    ['model_tier_resolve.py', { model: 'sonnet' }],
    ['task_review_cli.py', { action: 'park', reason: 'cap reached' }],
    ['review', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' },
                 findings: [{ severity: 'Important', file: 'a', title: 'bug' }] }],
  ])
  r = await bp.reviewOneTask('wi', 5, TASK, 'superheroes/wi-abc')
  assert.strictEqual(r.parked, true, 'unconverged review should park (UFR-4)')

  // (4) Fence lost before a build write -> park (UFR-10).
  global.agent = makeAgent([['fence_cli.py', { ok: false, reason: 'lease lost' }]])
  r = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '1')
  assert.strictEqual(r.parked, true, 'fence-lost should park before any write (UFR-10)')

  // (5) Converging fix loop: round 1 blocking -> review -> fix; round 2 clean -> complete.
  //     The task_review mock is ROUND-DRIVEN (it reads --round from the command), not call-count:
  //     a mutant that dropped `round += 1` would never reach round 2, so the loop would never
  //     converge — genuinely pinning round++/history.push (a frozen counter fails to complete).
  global.agent = makeAgent([
    ['fence_cli.py', { ok: true }],
    ['model_tier_resolve.py', { model: 'sonnet' }],
    ['record-reviewed', { ok: true }],
    ['task_review_cli.py', (p) => {
      const round = parseInt((p.match(/--round (\d+)/) || [])[1] || '0', 10)
      return round >= 2
        ? { action: 'complete', blocking: [], minors: [], cannot_verify: [] }
        : { action: 'review', blocking: [{ severity: 'Important', file: 'a', title: 'bug' }], minors: [], cannot_verify: [] }
    }],
    ['review', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' },
                 findings: [{ severity: 'Important', file: 'a', title: 'bug' }] }],
    ['fixer', ''],
  ])
  r = await bp.reviewOneTask('wi', 5, TASK, 'superheroes/wi-abc')
  assert.strictEqual(r.parked, false, 'a converging fix loop should complete, not park')

  console.log('ok: build_phase per-task (FR-6/UFR-3/4/5/10)')
})()
