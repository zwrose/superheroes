// plugins/superheroes/lib/tests/build_phase_pertask_smoke.js
// #115 increment A: the IO leaves (gather/fence/journal/record-reviewed/minor-rollup) are ported to
// exec(raw)+in-process-parse — they all route through the single 'exec' label now, returning the
// exec array shape [{index,ok,stdout}] with stdout a JSON STRING. The stub inspects the exec PROMPT
// (which lists "N. <command>") to choose the stdout. model_tier is now an in-process twin (no leaf).
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

// execRoute: a single 'exec' route whose stdout is a function of the listed command. unmapped lets a
// test choose the trailer-check result; capture lets a test inspect the exec prompt (PIN threading).
function execRoute({ unmapped = 0, capture = null } = {}) {
  return ['exec', (prompt) => {
    if (capture) capture(prompt)
    let stdout = '{}'
    if (prompt.includes('build_state_cli.py gather')) stdout = JSON.stringify({ unmapped_commits: unmapped })
    else if (prompt.includes('fence_cli.py')) stdout = JSON.stringify({ ok: true })
    else if (prompt.includes('journal_entry.py')) stdout = JSON.stringify({ ok: true })
    else if (prompt.includes('record-reviewed')) stdout = JSON.stringify({ ok: true })
    else if (prompt.includes('minor_rollup_cli.py')) stdout = JSON.stringify({ ok: true })
    return [{ index: 0, ok: true, stdout }]
  }]
}

;(async () => {
  // (1) Clean: fence ok, worker ok, trailer-check clean (scored against the FULL valid-id set '1,2'),
  //     reviewer two verdicts clean -> complete. Capture the exec prompt to PIN the valid-ids threading.
  let gatherPrompt = ''
  global.agent = makeAgent([
    execRoute({ unmapped: 0, capture: (p) => { if (p.includes('build_state_cli.py gather')) gatherPrompt = p } }),
    ['worker', { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } }],
    ['review', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }],
    ['task_review_cli.py', { action: 'complete', blocking: [], minors: [], cannot_verify: [] }],
  ])
  let r = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '1,2', '/tmp/wt')
  assert.strictEqual(r.parked, false, 'a clean task should not park')
  assert.ok(gatherPrompt.includes("--valid-ids '1,2'"),
    'the write-time trailer check must score against the FULL valid-id set, not just this task')
  assert.ok(gatherPrompt.includes("--worktree '/tmp/wt'"),
    'the write-time gather must read git from the build worktree, not the ambient cwd')

  // (1b) Fail-closed: the trailer-check leaf fails to run (ok:false) -> park (UFR-7), NOT advance.
  global.agent = makeAgent([
    ['exec', (prompt) => {
      if (prompt.includes('build_state_cli.py gather')) return [{ index: 0, ok: false, stdout: 'boom' }]
      if (prompt.includes('fence_cli.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      return [{ index: 0, ok: true, stdout: '{}' }]
    }],
    ['worker', { ok: true, signal: 'ok', evidence: {} }],
  ])
  r = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '1', '/tmp/wt')
  assert.strictEqual(r.parked, true, 'a failed trailer-check leaf must park (fail closed, UFR-7)')
  assert.ok(/verify commit trailers/i.test(r.reason || ''), 'honest UFR-7 fail-closed reason')

  // (2) Worker stuck (plan_wrong) -> recovery says park (UFR-3).
  global.agent = makeAgent([
    execRoute(),
    ['worker_recovery_cli.py', { action: 'park', reason: 'plan wrong' }],
    ['worker', { ok: false, signal: 'plan_wrong' }],
  ])
  r = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '1', '/tmp/wt')
  assert.strictEqual(r.parked, true, 'worker plan_wrong should park (UFR-3)')

  // (3) Review parks (cap reached) -> park (UFR-4).
  global.agent = makeAgent([
    execRoute(),
    ['task_review_cli.py', { action: 'park', reason: 'cap reached' }],
    ['review', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' },
                 findings: [{ severity: 'Important', file: 'a', title: 'bug' }] }],
  ])
  r = await bp.reviewOneTask('wi', 5, TASK, 'superheroes/wi-abc', '/tmp/wt')
  assert.strictEqual(r.parked, true, 'unconverged review should park (UFR-4)')

  // (4) Fence lost before a build write -> park (UFR-10). The fence leaf returns {ok:false}.
  global.agent = makeAgent([
    ['exec', () => [{ index: 0, ok: true, stdout: JSON.stringify({ ok: false, reason: 'lease lost' }) }]],
  ])
  r = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '1', '/tmp/wt')
  assert.strictEqual(r.parked, true, 'fence-lost should park before any write (UFR-10)')

  // (4b) Fence leaf FAILS to run (ok:false at the exec layer) -> fence reads LOST -> park (UFR-10).
  //      A fence exec failure must NEVER read as ok.
  global.agent = makeAgent([
    ['exec', () => [{ index: 0, ok: false, stdout: 'leaf crashed' }]],
  ])
  r = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '1', '/tmp/wt')
  assert.strictEqual(r.parked, true, 'a failed fence leaf must read as lost (fail closed, UFR-10)')

  // (5) Converging fix loop: round 1 blocking -> review -> fix; round 2 clean -> complete.
  //     The task_review mock is ROUND-DRIVEN (it reads --round from the command), not call-count:
  //     a mutant that dropped `round += 1` would never reach round 2, so the loop would never
  //     converge — genuinely pinning round++/history.push (a frozen counter fails to complete).
  global.agent = makeAgent([
    execRoute(),
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
  r = await bp.reviewOneTask('wi', 5, TASK, 'superheroes/wi-abc', '/tmp/wt')
  assert.strictEqual(r.parked, false, 'a converging fix loop should complete, not park')

  console.log('ok: build_phase per-task (FR-6/UFR-3/4/5/7/10, exec fail-closed)')
})()
