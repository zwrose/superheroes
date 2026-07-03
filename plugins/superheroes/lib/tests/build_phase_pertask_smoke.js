require('./_smoke_checkout_root.js')
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
    if (label === 'gather build state') {
      for (const [needle, resp] of routes) {
        if (needle === 'exec' && typeof resp === 'function') {
          const raw = resp('build_state_cli.py gather')
          const row = Array.isArray(raw) ? raw[0] : raw
          const stdout = (row && row.stdout != null) ? row.stdout : '{}'
          return [{ ok: true, stdout }]
        }
      }
    }
    // Exact-label first (labels are unique), so a short needle never shadows a longer script name
    // via substring; then a prompt-substring fallback. A function resp receives the prompt (capture).
    for (const [needle, resp] of routes) {
      if (label === needle || (needle.endsWith(':r') && label.startsWith(needle))) {
        return typeof resp === 'function' ? resp(prompt) : resp
      }
    }
    for (const [needle, resp] of routes) if (prompt.includes(needle)) return typeof resp === 'function' ? resp(prompt) : resp
    if (opts && opts.courier) { for (const [needle, resp] of routes) if (needle === 'exec') return typeof resp === 'function' ? resp(prompt) : resp }
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
    ['implement-task', { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } }],
    ['task-reviewer:r', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }],
    ['record task built', [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true, task: '1' }) }]],
    ['record task reviewed', [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true, task: '1' }) }]],
  ])
  let r = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '1,2', '/tmp/wt')
  assert.strictEqual(r.parked, false, 'a clean task should not park')
  assert.ok(gatherPrompt.includes("--valid-ids '1,2'"),
    'the write-time trailer check must score against the FULL valid-id set, not just this task')
  assert.ok(gatherPrompt.includes("--worktree '/tmp/wt'"),
    'the write-time gather must read git from the build worktree, not the ambient cwd')
  // BUG-1 guard (byte-identical-to-today): with __SR_BASE UNSET the per-task gather carries NO --base.
  assert.ok(!gatherPrompt.includes('--base'),
    'with __SR_BASE unset the per-task trailer gather must NOT append --base (byte-identical to today)')

  // (1a) Configurable base (FR-8): with __SR_BASE set, the PER-TASK UFR-7 gather must thread --base so
  //      a build off a non-main base measures against that base (the live bug: the per-task check
  //      omitted --base and parked off origin/main). Pins baseArg() threading on the per-task site.
  let basePrompt = ''
  globalThis.__SR_BASE = 'live-showrunner-102'
  try {
    global.agent = makeAgent([
      execRoute({ unmapped: 0, capture: (p) => { if (p.includes('build_state_cli.py gather')) basePrompt = p } }),
      ['implement-task', { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } }],
      ['task-reviewer:r', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }],
      ['record task built', [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true, task: '1' }) }]],
      ['record task reviewed', [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true, task: '1' }) }]],
    ])
    r = await bp.buildOneTask('wi', 5, TASK, 'live-showrunner-102', '1,2', '/tmp/wt')
    assert.strictEqual(r.parked, false, 'a clean task on a configured base should not park')
    assert.ok(basePrompt.includes("--base 'live-showrunner-102'"),
      'the per-task UFR-7 gather must thread the configured base (FR-8) so it does not park off origin/main')
  } finally {
    delete globalThis.__SR_BASE  // don't leak the global into later cases / other smokes
  }

  // (1b) Fail-closed: the trailer-check leaf fails to run (ok:false) -> park (UFR-7), NOT advance.
  global.agent = makeAgent([
    ['exec', (prompt) => {
      if (prompt.includes('build_state_cli.py gather')) return [{ index: 0, ok: false, stdout: 'boom' }]
      if (prompt.includes('fence_cli.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      return [{ index: 0, ok: true, stdout: '{}' }]
    }],
    ['implement-task', { ok: true, signal: 'ok', evidence: {} }],
  ])
  r = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '1', '/tmp/wt')
  assert.strictEqual(r.parked, true, 'a failed trailer-check leaf must park (fail closed, UFR-7)')
  assert.ok(/boom/i.test(r.reason || ''), 'honest UFR-7 fail-closed reason')

  // (2) Worker stuck (plan_wrong) -> the worker_recovery TWIN parks for real (UFR-3). No leaf: the
  //     worker returns {ok:false, signal:'plan_wrong'} and workerRecoveryTwin.decide parks in-process.
  global.agent = makeAgent([
    execRoute(),
    ['implement-task', { ok: false, signal: 'plan_wrong' }],
  ])
  r = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '1', '/tmp/wt')
  assert.strictEqual(r.parked, true, 'worker plan_wrong should park (UFR-3)')
  assert.ok(/plan\/task is wrong/i.test(r.reason || ''), 'park reason is the twin\'s real plan_wrong reason')

  // (3) Review never converges -> the task_review TWIN parks (UFR-4). No leaf: a persistent identical
  //     Important finding makes the real twin return 'review' (fix) on round 1, then 'park' on round 2
  //     when the circuit breaker sees the SAME blocking finding recur after a fix was committed. The
  //     park is genuine (the twin halts a non-progressing loop), not a stubbed action.
  global.agent = makeAgent([
    execRoute(),
    ['task-reviewer:r', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' },
                 findings: [{ severity: 'Important', file: 'a', title: 'bug' }] }],
    ['fix-task', ''],
  ])
  r = await bp.reviewOneTask('wi', 5, TASK, 'superheroes/wi-abc', '/tmp/wt')
  assert.strictEqual(r.parked, true, 'unconverged review should park (UFR-4)')
  assert.ok(/recurred/i.test(r.reason || ''), 'park reason is the twin\'s real recurring-finding breaker reason')

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

  // (5) Converging fix loop: round 1 returns a blocking finding -> the real task_review TWIN says
  //     'review' -> fix; the FIXER then resolves it, so round 2's review is clean -> twin says
  //     'complete'. The reviewer mock is STATEFUL (blocking on call 1, clean afterward), so a mutant
  //     that dropped `round += 1` / `history.push` (a frozen loop) would re-fix the same finding
  //     forever and never reach the clean second review -> genuinely pins the loop advance.
  let reviewCalls = 0
  global.agent = makeAgent([
    execRoute(),
    ['task-reviewer:r', () => {
      reviewCalls += 1
      return reviewCalls >= 2
        ? { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }
        : { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [{ severity: 'Important', file: 'a', title: 'bug' }] }
    }],
    ['fix-task', ''],
    ['record task reviewed', [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true, task: '1' }) }]],
  ])
  r = await bp.reviewOneTask('wi', 5, TASK, 'superheroes/wi-abc', '/tmp/wt')
  assert.strictEqual(r.parked, false, 'a converging fix loop should complete, not park')
  assert.ok(reviewCalls >= 2, 'the loop advances to a second (clean) review round before completing')

  // (6) Runaway regression (#115): the reviewer's StructuredOutput returns `verdicts` as a STRINGIFIED
  //     JSON (the proven live derailment). With the defensive parse the string is recovered to an
  //     object -> the twin sees both verdicts -> the task COMPLETES; it does NOT loop. Capture the
  //     dispatch count to prove the reviewer is called a BOUNDED number of times (not 10+).
  let recoverCalls = 0
  global.agent = makeAgent([
    execRoute(),
    ['task-reviewer:r', () => { recoverCalls += 1; return { verdicts: '{"spec_compliance":"pass","code_quality":"pass"}', findings: [] } }],
    ['fix-task', ''],
    ['record task reviewed', [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true, task: '1' }) }]],
  ])
  r = await bp.reviewOneTask('wi', 5, TASK, 'superheroes/wi-abc', '/tmp/wt')
  assert.strictEqual(r.parked, false, 'a stringified-verdicts review must be recovered (defensive parse) and complete, not loop')
  assert.strictEqual(recoverCalls, 1, 'a recoverable stringified verdicts completes on the first review (no re-request)')

  // (7) Bound regression (#115): the reviewer ALWAYS returns a verdicts shape that CANNOT be recovered
  //     ('not json' -> parse fails -> {} -> twin re_requests forever on the pre-fix code). The bounded
  //     loop must PARK after MAX_ROUNDS attempts with the re_request reason — and the reviewer must be
  //     dispatched a BOUNDED number of times (<= MAX_ROUNDS), NOT the 10+ of the live runaway. The stub
  //     also caps itself so a regressed (unbounded) loop fails loudly instead of hanging the suite.
  let boundCalls = 0
  const HARD_CAP = bp.MAX_ROUNDS * 5   // a runaway would blow past this; the bound keeps us <= MAX_ROUNDS
  global.agent = makeAgent([
    execRoute(),
    ['task-reviewer:r', () => {
      boundCalls += 1
      assert.ok(boundCalls <= HARD_CAP, `RUNAWAY: reviewer dispatched ${boundCalls} times (>${HARD_CAP}) — the loop is unbounded`)
      return { verdicts: 'not json', findings: [] }
    }],
    ['fix-task', ''],
  ])
  r = await bp.reviewOneTask('wi', 5, TASK, 'superheroes/wi-abc', '/tmp/wt')
  assert.strictEqual(r.parked, true, 'an unrecoverable verdicts shape must PARK the loop (bounded), not run away')
  assert.ok(/both verdicts after \d+ attempts/i.test(r.reason || ''), 'park reason names the bounded re-request attempts')
  assert.ok(boundCalls <= bp.MAX_ROUNDS, `the reviewer must be dispatched <= MAX_ROUNDS (${bp.MAX_ROUNDS}) times, not the 10+ of the runaway (was ${boundCalls})`)

  console.log('ok: build_phase per-task (FR-6/UFR-3/4/5/7/10, exec fail-closed; #115 bounded review loop)')
})()
