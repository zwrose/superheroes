// plugins/superheroes/lib/tests/showrunner_engine_dispatch_smoke.js
// #38: engine_dispatch.js dispatchExternal spine leaf wrapper. Mirrors build_phase_setup_smoke.js's
// makeAgent(routes)/execRoute idiom (route by exact label, then prompt substring), plus an ordered
// execLog so the stdin-redirect / audit-event assertions can inspect the exact dispatch-run command.
const assert = require('assert')
const logs = []
global.log = (m) => logs.push(m)

// Route an agent() call by the first matching needle found in its prompt OR its label.
function makeAgent(routes) {
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    for (const [needle, resp] of routes) if (label === needle) return typeof resp === 'function' ? resp(prompt) : resp
    for (const [needle, resp] of routes) if (prompt.includes(needle)) return typeof resp === 'function' ? resp(prompt) : resp
    return ''
  }
}

;(async () => {
  // ---------------------------------------------------------------------
  // Review (read-only) happy path.
  // ---------------------------------------------------------------------
  const execLog = []
  global.agent = makeAgent([
    ['exec', (prompt) => {
      execLog.push(prompt)
      if (prompt.includes('engine_adapter.py build-argv')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify(['codex', 'exec', '--sandbox', 'read-only', '-']) }]
      }
      if (prompt.includes('engine_adapter.py parse-result')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, findings: [{ file: 'a.py', line: 3, title: 'x', severity: 'Minor', evidence: 'e' }] }) }]
      }
      if (prompt.includes('journal_entry.py')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      }
      if (prompt.includes('--sandbox')) {
        return [{ index: 0, ok: true, stdout: '{"raw":"external review output"}' }]
      }
      return [{ index: 0, ok: true, stdout: '{}' }]
    }],
  ])

  const d = require('../engine_dispatch.js')
  const r = await d.dispatchExternal({ engine: 'codex', roleKind: 'review', effort: 'high', prompt: 'review', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300 })

  assert.deepStrictEqual(r.findings, [{ file: 'a.py', line: 3, title: 'x', severity: 'Minor', evidence: 'e' }])
  assert.ok(!execLog.some((c) => c.includes('git') && c.includes('rev-parse')), 'no preSHA capture for a read role')
  assert.ok(!execLog.some((c) => c.includes('engine_adapter.py commit')), 'no commit for a read role')
  const runCmd = execLog.find((c) => c.includes('--sandbox') && c.includes(' < '))
  assert.ok(runCmd && /\.prompt/.test(runCmd), 'run must redirect the staged prompt file into stdin')
  // FIX 2: the CLI invocation must be wrapped in the portable perl-alarm OS-level kill guard so a
  // stall is actually killed (not just unwaited-on by the JS race).
  assert.ok(/perl -e 'alarm shift @ARGV; exec @ARGV or exit 127' \d+ 'codex' 'exec'/.test(runCmd),
    'FIX 2: run command must wrap the CLI with the perl-alarm kill guard: ' + runCmd)

  console.log('OK: engine_dispatch review-path')

  // ---------------------------------------------------------------------
  // Write (build) happy path.
  // ---------------------------------------------------------------------
  const execLog2 = []
  global.agent = makeAgent([
    ['exec', (prompt) => {
      execLog2.push(prompt)
      if (prompt.includes('git') && prompt.includes('rev-parse HEAD')) {
        return [{ index: 0, ok: true, stdout: 'preSHA-abc\n' }]
      }
      if (prompt.includes('engine_adapter.py build-argv')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify(['codex', 'exec', '--sandbox', 'workspace-write', '-C', '/tmp/wt', '-']) }]
      }
      if (prompt.includes('engine_adapter.py parse-result')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } }) }]
      }
      if (prompt.includes('engine_adapter.py commit')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, sha: 'newsha' }) }]
      }
      if (prompt.includes('journal_entry.py')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      }
      if (prompt.includes('--sandbox')) {
        return [{ index: 0, ok: true, stdout: '{"raw":"external build output"}' }]
      }
      return [{ index: 0, ok: true, stdout: '{}' }]
    }],
  ])

  const r2 = await d.dispatchExternal({ engine: 'codex', roleKind: 'build', effort: 'high', prompt: 'build', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300, taskId: 'T1', workItem: 'wi-abc' })

  assert.strictEqual(r2.ok, true)
  assert.strictEqual(r2.signal, 'ok')
  assert.strictEqual(r2.evidence.testPassed, true)
  assert.ok(execLog2.some((c) => c.includes('git') && c.includes('rev-parse HEAD')), 'preSHA must be captured for a write role')
  assert.ok(execLog2.some((c) => c.includes('engine_adapter.py commit')), 'commit must be invoked on write success')
  const runCmd2 = execLog2.find((c) => c.includes('--sandbox') && c.includes(' < '))
  assert.ok(runCmd2 && /\.prompt/.test(runCmd2), 'run must redirect the staged prompt file into stdin')
  assert.ok(execLog2.some((c) => c.includes('journal_entry.py') && c.includes('--event-type external_dispatch')),
    'FR-6: the journal call must carry the first-class external_dispatch event type')
  // FR-8: a WRITE dispatch's exec command must be confined to the target cwd via a `cd <cwd> &&`
  // prefix — cursor's argv carries no -C flag of its own, so without this the run would execute at
  // __SR_ROOT (the repo root) instead of the per-task build worktree.
  assert.ok(/(^|\n)\d+\.\s*cd '\/tmp\/wt' && /.test(runCmd2), 'write dispatch must confine the run to cwd via cd <cwd> &&: ' + runCmd2)
  // FIX 2: the perl-alarm kill guard must ALSO wrap a write-role dispatch, threaded with the same
  // timeoutSeconds (300) used to bound the JS race for this call.
  assert.ok(/perl -e 'alarm shift @ARGV; exec @ARGV or exit 127' 300 'codex' 'exec'/.test(runCmd2),
    'FIX 2: write dispatch run command must wrap the CLI with the perl-alarm kill guard using the same timeout: ' + runCmd2)

  console.log('OK: engine_dispatch write-path')

  // ---------------------------------------------------------------------
  // #308/#309: the enriched external_dispatch journal + threaded model/timeout. This exercises the
  // REAL dispatchExternal with NO monkeypatched internal seam (only the outermost exec courier is
  // stubbed, exactly as production runs it), so it pins the ACTUAL argv/journal the dispatch emits:
  //   - the resolved `model` is forwarded to build-argv (`--model 'opus'`);
  //   - the perl-alarm OS-kill guard carries the caller's effective timeout (2400s here);
  //   - the external_dispatch journal payload records model + argv + effectiveTimeout (what #299 audits).
  {
    const execLogEnrich = []
    let capturedArgv = null
    global.agent = makeAgent([
      ['exec', (prompt) => {
        execLogEnrich.push(prompt)
        if (prompt.includes('git') && prompt.includes('rev-parse HEAD')) return [{ index: 0, ok: true, stdout: 'preSHA-abc\n' }]
        if (prompt.includes('engine_adapter.py build-argv')) {
          capturedArgv = ['cursor-agent', '--model', 'claude-opus-4-8-thinking-high', '-p', '--trust', '-f', '--output-format', 'stream-json']
          return [{ index: 0, ok: true, stdout: JSON.stringify(capturedArgv) }]
        }
        if (prompt.includes('engine_adapter.py parse-result')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, signal: 'ok', evidence: {} }) }]
        if (prompt.includes('engine_adapter.py commit')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, sha: 'newsha' }) }]
        if (prompt.includes('journal_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
        if (prompt.includes('--model')) return [{ index: 0, ok: true, stdout: '{"raw":"external build output"}' }]
        return [{ index: 0, ok: true, stdout: '{}' }]
      }],
    ])
    const rEnrich = await d.dispatchExternal({ engine: 'cursor', roleKind: 'build', effort: 'composer',
      prompt: 'build', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 2400, model: 'opus', taskId: 'T1', workItem: 'wi-abc' })
    assert.strictEqual(rEnrich.ok, true, '#308/#309: the enriched write dispatch still succeeds')
    // build-argv received the resolved model (the #308 fix: dispatch forwards the tier).
    const argvCmd = execLogEnrich.find((c) => c.includes('engine_adapter.py build-argv'))
    assert.ok(argvCmd.includes("--model 'opus'"), '#308: dispatch forwards the resolved model to build-argv: ' + argvCmd)
    // the perl-alarm OS-kill guard carries the caller's effective timeout (#309), not the 300s default.
    const runCmd = execLogEnrich.find((c) => c.includes('--model') && c.includes(' < '))
    assert.ok(/perl -e 'alarm shift @ARGV; exec @ARGV or exit 127' 2400 /.test(runCmd),
      '#309: the perl-alarm guard carries the threaded timeout (2400s): ' + runCmd)
    // the external_dispatch journal payload is enriched with model + argv + effectiveTimeout (#299 audit).
    const journalCmd = execLogEnrich.find((c) => c.includes('journal_entry.py') && c.includes('external_dispatch'))
    const pm = journalCmd.match(/--payload '(.*)'$/s)
    const payload = JSON.parse(pm[1])
    assert.strictEqual(payload.model, 'opus', '#308: the journal records the resolved model')
    assert.strictEqual(payload.effectiveTimeout, 2400, '#309: the journal records the effective timeout ceiling')
    assert.deepStrictEqual(payload.argv, capturedArgv, '#308: the journal records the exact dispatched argv')
    console.log('OK: engine_dispatch enriched journal (model + argv + effectiveTimeout) + threaded timeout')
  }

  // #309: with NO timeoutSeconds supplied the dispatch keeps the legacy finite default (300s) — the
  // per-role ceilings live in the CALLERS (build_phase/showrunner), so the leaf itself stays back-compat.
  {
    const execLogDef = []
    global.agent = makeAgent([
      ['exec', (prompt) => {
        execLogDef.push(prompt)
        if (prompt.includes('engine_adapter.py build-argv')) return [{ index: 0, ok: true, stdout: JSON.stringify(['codex', 'exec', '--sandbox', 'read-only', '-']) }]
        if (prompt.includes('engine_adapter.py parse-result')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, findings: [] }) }]
        if (prompt.includes('journal_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
        if (prompt.includes('--sandbox')) return [{ index: 0, ok: true, stdout: '{}' }]
        return [{ index: 0, ok: true, stdout: '{}' }]
      }],
    ])
    await d.dispatchExternal({ engine: 'codex', roleKind: 'review', effort: 'high', prompt: 'review', cwd: '/tmp/wt', schema: {}, workItem: 'wi-abc' })
    const runCmd = execLogDef.find((c) => c.includes('--sandbox') && c.includes(' < '))
    assert.ok(/perl -e 'alarm shift @ARGV; exec @ARGV or exit 127' 300 /.test(runCmd),
      '#309: absent timeoutSeconds keeps the leaf-level 300s finite default: ' + runCmd)
    const journalCmd = execLogDef.find((c) => c.includes('journal_entry.py') && c.includes('external_dispatch'))
    assert.ok(/"effectiveTimeout":300/.test(journalCmd), '#309: the journal records the 300s default when nothing was passed')
  }

  console.log('OK: engine_dispatch leaf-default timeout back-compat')

  // ---------------------------------------------------------------------
  // #288: HONEST REFUSAL. The external build leaf refuses ({"ok":false,"signal":"plan_wrong"}) —
  // parse-result no longer launders that to ok:true, so dispatchExternal must route it to the
  // write-FAILURE path: return {ok:false, reason:'plan_wrong'} (the caller then discards uncommitted
  // edits (UFR-2) + falls open to Claude, parking (UFR-3)), leave NO commit (a refusal must never be
  // committed and recorded built:passed), and still journal exactly one external_dispatch audit line.
  const execLogRefuse = []
  global.agent = makeAgent([
    ['exec', (prompt) => {
      execLogRefuse.push(prompt)
      if (prompt.includes('git') && prompt.includes('rev-parse HEAD')) {
        return [{ index: 0, ok: true, stdout: 'preSHA-abc\n' }]
      }
      if (prompt.includes('engine_adapter.py build-argv')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify(['codex', 'exec', '--sandbox', 'workspace-write', '-C', '/tmp/wt', '-']) }]
      }
      if (prompt.includes('engine_adapter.py parse-result')) {
        // What the (fixed) parse_result returns for an honest refusal — an un-laundered ok:false.
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: false, signal: 'plan_wrong', reason: 'plan_wrong', evidence: { testFailed: true, testPassed: false } }) }]
      }
      if (prompt.includes('engine_adapter.py commit')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, sha: 'newsha' }) }]
      }
      if (prompt.includes('journal_entry.py')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      }
      if (prompt.includes('--sandbox')) {
        return [{ index: 0, ok: true, stdout: '{"ok":false,"signal":"plan_wrong"}' }]
      }
      return [{ index: 0, ok: true, stdout: '{}' }]
    }],
  ])
  const rRefuse = await d.dispatchExternal({ engine: 'codex', roleKind: 'build', effort: 'high', prompt: 'build', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300, taskId: 'T1', workItem: 'wi-abc' })
  assert.strictEqual(rRefuse.ok, false, '#288: an honest refusal must NOT dispatch as ok:true')
  assert.strictEqual(rRefuse.reason, 'plan_wrong', '#288: the leaf refusal signal must survive as the dispatch reason')
  assert.ok(!execLogRefuse.some((c) => c.includes('engine_adapter.py commit')),
    '#288: a refused build must NEVER be committed (the adapter is the sole committer; commit runs only on ok:true)')
  assert.ok(execLogRefuse.some((c) => c.includes('journal_entry.py') && c.includes('--event-type external_dispatch') && c.includes('plan_wrong')),
    '#288: a refused build must still leave exactly one external_dispatch audit line carrying the refusal reason')

  // Mutation guard: if parse-result were to launder the SAME refusal back to ok:true, dispatch would
  // commit it and report ok:true — the exact #288 defect. Assert that shape is caught (would-be false pass).
  const execLogLaunder = []
  global.agent = makeAgent([
    ['exec', (prompt) => {
      execLogLaunder.push(prompt)
      if (prompt.includes('git') && prompt.includes('rev-parse HEAD')) return [{ index: 0, ok: true, stdout: 'preSHA-abc\n' }]
      if (prompt.includes('engine_adapter.py build-argv')) return [{ index: 0, ok: true, stdout: JSON.stringify(['codex', 'exec', '--sandbox', 'workspace-write', '-C', '/tmp/wt', '-']) }]
      if (prompt.includes('engine_adapter.py parse-result')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, signal: 'ok', evidence: {} }) }]
      if (prompt.includes('engine_adapter.py commit')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, sha: 'newsha' }) }]
      if (prompt.includes('journal_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      if (prompt.includes('--sandbox')) return [{ index: 0, ok: true, stdout: '{"ok":false,"signal":"plan_wrong"}' }]
      return [{ index: 0, ok: true, stdout: '{}' }]
    }],
  ])
  const rLaunder = await d.dispatchExternal({ engine: 'codex', roleKind: 'build', effort: 'high', prompt: 'build', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300, taskId: 'T1', workItem: 'wi-abc' })
  assert.strictEqual(rLaunder.ok, true, 'control: a laundered ok:true DOES commit + pass — proving the refusal case above is load-bearing on parse_result, not on dispatch swallowing it')
  assert.ok(execLogLaunder.some((c) => c.includes('engine_adapter.py commit')), 'control: the laundered shape reaches commit — which is exactly why parse_result must not emit it (#288)')

  console.log('OK: engine_dispatch honest-refusal (#288)')

  // ---------------------------------------------------------------------
  // UFR-5 timeout / UFR-6 unauditable / sec-101 commit-failure audit.
  // ---------------------------------------------------------------------

  // (a) UFR-5: the argv-run hangs forever -> the wrapper's own timeout fires.
  global.agent = makeAgent([
    ['exec', (prompt) => {
      if (prompt.includes('git') && prompt.includes('rev-parse HEAD')) {
        return [{ index: 0, ok: true, stdout: 'preSHA-abc\n' }]
      }
      if (prompt.includes('engine_adapter.py build-argv')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify(['codex', 'exec', '--sandbox', 'workspace-write', '-C', '/tmp/wt', '-']) }]
      }
      if (prompt.includes('--sandbox')) {
        // Simulate a hang: resolve far later than the wrapper's own timeout, via an unref'd timer
        // so the never-taken branch doesn't pin the node process alive after the test moves on.
        return new Promise((resolve) => {
          const t = setTimeout(() => resolve([{ index: 0, ok: true, stdout: '{"raw":"late"}' }]), 3600000)
          if (t.unref) t.unref()
        })
      }
      return [{ index: 0, ok: true, stdout: '{}' }]
    }],
  ])
  const rTimeout = await d.dispatchExternal({ engine: 'codex', roleKind: 'build', effort: 'high', prompt: 'build', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 0.01, taskId: 'T1', workItem: 'wi-abc' })
  assert.strictEqual(rTimeout.reason, 'timeout')

  // (b) UFR-6: write happy path but the journal append fails -> unauditable (fail-closed), even
  // though the commit already landed.
  global.agent = makeAgent([
    ['exec', (prompt) => {
      if (prompt.includes('git') && prompt.includes('rev-parse HEAD')) {
        return [{ index: 0, ok: true, stdout: 'preSHA-abc\n' }]
      }
      if (prompt.includes('engine_adapter.py build-argv')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify(['codex', 'exec', '--sandbox', 'workspace-write', '-C', '/tmp/wt', '-']) }]
      }
      if (prompt.includes('engine_adapter.py parse-result')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, signal: 'ok', evidence: {} }) }]
      }
      if (prompt.includes('engine_adapter.py commit')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, sha: 'newsha' }) }]
      }
      if (prompt.includes('journal_entry.py')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: false }) }]
      }
      if (prompt.includes('--sandbox')) {
        return [{ index: 0, ok: true, stdout: '{"raw":"external build output"}' }]
      }
      return [{ index: 0, ok: true, stdout: '{}' }]
    }],
  ])
  const rUnauditable = await d.dispatchExternal({ engine: 'codex', roleKind: 'build', effort: 'high', prompt: 'build', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300, taskId: 'T1', workItem: 'wi-abc' })
  assert.strictEqual(rUnauditable.reason, 'unauditable')

  // (c) sec-101: write happy path through the argv-run + parse-result, but the adapter commit fails
  // -> the engine DID run and edit the worktree, so this outcome must ALSO leave exactly one audit
  // line (FR-6/UFR-6 symmetry) even though the overall result is a failure.
  const execLog3 = []
  global.agent = makeAgent([
    ['exec', (prompt) => {
      execLog3.push(prompt)
      if (prompt.includes('git') && prompt.includes('rev-parse HEAD')) {
        return [{ index: 0, ok: true, stdout: 'preSHA-abc\n' }]
      }
      if (prompt.includes('engine_adapter.py build-argv')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify(['codex', 'exec', '--sandbox', 'workspace-write', '-C', '/tmp/wt', '-']) }]
      }
      if (prompt.includes('engine_adapter.py parse-result')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, signal: 'ok', evidence: {} }) }]
      }
      if (prompt.includes('engine_adapter.py commit')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: false, error: 'nothing to commit' }) }]
      }
      if (prompt.includes('pr_comment.py scrub')) {
        return [{ index: 0, ok: true, stdout: 'nothing to commit' }]
      }
      if (prompt.includes('journal_entry.py')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      }
      if (prompt.includes('--sandbox')) {
        return [{ index: 0, ok: true, stdout: '{"raw":"external build output"}' }]
      }
      return [{ index: 0, ok: true, stdout: '{}' }]
    }],
  ])
  const rCommitFail = await d.dispatchExternal({ engine: 'codex', roleKind: 'build', effort: 'high', prompt: 'build', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300, taskId: 'T1', workItem: 'wi-abc' })
  assert.strictEqual(rCommitFail.ok, false)
  assert.ok(execLog3.some((c) => c.includes('journal_entry.py') && c.includes('--event-type external_dispatch') && c.includes('commit-failed')),
    'sec-101: commit-failure must still leave exactly one external_dispatch audit line')

  console.log('OK: engine_dispatch timeout + unauditable + commit-failure audit')

  // ---------------------------------------------------------------------
  // FIX 3: a synchronous throw from an internal step must fall open, never throw out of
  // dispatchExternal — callers' fall-open-to-Claude path relies on a RETURNED {ok:false}.
  // ---------------------------------------------------------------------
  global.agent = () => { throw new Error('boom: synchronous internal failure') }
  let threw = false
  let rSyncThrow
  try {
    rSyncThrow = await d.dispatchExternal({ engine: 'codex', roleKind: 'review', effort: 'high', prompt: 'review', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300 })
  } catch (_e) {
    threw = true
  }
  assert.strictEqual(threw, false, 'FIX 3: dispatchExternal must not throw when an internal step throws synchronously')
  assert.strictEqual(rSyncThrow.ok, false, 'FIX 3: a synchronous internal throw resolves to {ok:false}')
  // #277: the reason is PREFIXED dispatch-error and CARRIES the underlying error name+message (so the
  // next failure on this path is self-identifying instead of a bare, un-diagnosable 'dispatch-error').
  assert.ok(/^dispatch-error: /.test(rSyncThrow.reason),
    '#277: the fall-open reason is prefixed "dispatch-error: ": ' + rSyncThrow.reason)
  assert.ok(/boom: synchronous internal failure/.test(rSyncThrow.reason),
    '#277: the fall-open reason carries the underlying error message: ' + rSyncThrow.reason)

  console.log('OK: engine_dispatch falls open (does not throw) on a synchronous internal error, reason carries the error')

  // ---------------------------------------------------------------------
  // #277: the base64 staging encoder must NOT depend on Node's `Buffer` — the Workflow sandbox has no
  // Buffer global, and the old `Buffer.from(...)` in _stageCmd threw on its first statement, making
  // EVERY external dispatch silently fall open to Claude. With Buffer deleted from the global scope
  // (simulating the sandbox), a dispatch must still stage its inputs and reach the CLI — the exact
  // regression that was invisible to smokes running in plain node where Buffer exists.
  // ---------------------------------------------------------------------
  {
    d.__resetHarnessNotice(); logs.length = 0
    const savedBuffer = global.Buffer
    const execLogNB = []
    global.agent = makeAgent([
      ['exec', (prompt) => {
        execLogNB.push(prompt)
        if (prompt.includes('engine_adapter.py build-argv')) {
          return [{ index: 0, ok: true, stdout: JSON.stringify(['codex', 'exec', '--sandbox', 'read-only', '-']) }]
        }
        if (prompt.includes('engine_adapter.py parse-result')) {
          return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, findings: [] }) }]
        }
        if (prompt.includes('journal_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
        if (prompt.includes('--sandbox')) return [{ index: 0, ok: true, stdout: '{}' }]
        return [{ index: 0, ok: true, stdout: '{}' }]
      }],
    ])
    let rNB
    try {
      // eslint-disable-next-line no-global-assign
      delete global.Buffer
      assert.strictEqual(typeof Buffer, 'undefined', '#277 precondition: Buffer is removed from the global scope')
      rNB = await d.dispatchExternal({ engine: 'codex', roleKind: 'review', effort: 'high', prompt: 'stage me — 🎡 §', cwd: '/tmp/wt', schema: { type: 'object' }, timeoutSeconds: 300 })
    } finally {
      global.Buffer = savedBuffer
    }
    assert.ok(rNB && !rNB.reason, '#277: a dispatch must NOT fail with Buffer absent — it did: ' + (rNB && rNB.reason))
    assert.deepStrictEqual(rNB.findings, [], '#277: the Buffer-less dispatch completes normally (reaches parse-result)')
    // the prompt was staged via `printf %s '<b64>' | base64 -d > ...` — proving the encoder ran with no Buffer.
    assert.ok(execLogNB.some((c) => c.includes('base64 -d >') && c.includes('.prompt')),
      '#277: the prompt is staged via a base64-decode command even with no Buffer global')
    assert.ok(!logs.some((l) => /ENGINE-UNAVAILABLE/.test(l)),
      '#277: no harness-dead notice fires when staging succeeds Buffer-free')
  }

  console.log('OK: engine_dispatch stages inputs with NO Buffer global (Buffer-less base64 encoder)')

  // ---------------------------------------------------------------------
  // #277 tripwire: a harness-level staging/dispatch death surfaces ONCE as a distinct NAMED notice
  // (ENGINE-UNAVAILABLE), keyed on pre-CLI failure reasons only (could-not-stage-* / dispatch-error).
  // Engine-specific outcomes where the CLI actually ran (timeout/unreadable/commit-failed) must NOT.
  // ---------------------------------------------------------------------
  {
    // (A) staging fails -> could-not-stage-external-inputs -> the named notice fires, naming engine+reason.
    d.__resetHarnessNotice(); logs.length = 0
    global.agent = makeAgent([
      ['exec', (prompt) => {
        if (prompt.includes('base64 -d >')) return [{ index: 0, ok: false, stdout: '' }]
        if (prompt.includes('journal_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
        return [{ index: 0, ok: true, stdout: '{}' }]
      }],
    ])
    const rDeadA = await d.dispatchExternal({ engine: 'cursor', roleKind: 'build', effort: 'high', prompt: 'x', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300, taskId: 'T1', workItem: 'wi-1' })
    assert.strictEqual(rDeadA.reason, 'could-not-stage-external-inputs', '#277: staging failure fails closed with the staging reason')
    const notice = logs.filter((l) => /ENGINE-UNAVAILABLE/.test(l))
    assert.strictEqual(notice.length, 1, '#277: exactly one ENGINE-UNAVAILABLE notice fires on a harness-dead reason')
    assert.ok(/cursor/.test(notice[0]) && /could-not-stage-external-inputs/.test(notice[0]),
      '#277: the notice names the engine and the underlying reason: ' + notice[0])

    // (B) once-only: a SECOND harness-dead dispatch does not re-log (memoized for the run).
    const rDeadB = await d.dispatchExternal({ engine: 'cursor', roleKind: 'build', effort: 'high', prompt: 'y', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300, taskId: 'T2', workItem: 'wi-1' })
    assert.strictEqual(rDeadB.reason, 'could-not-stage-external-inputs', '#277: the second dead dispatch still fails closed')
    assert.strictEqual(logs.filter((l) => /ENGINE-UNAVAILABLE/.test(l)).length, 1,
      '#277: the named notice is emitted at most once per run (not per dispatch)')

    // (C) a NON-harness reason (timeout — the CLI genuinely ran) must NOT trip the notice.
    d.__resetHarnessNotice(); logs.length = 0
    global.agent = makeAgent([
      ['exec', (prompt) => {
        if (prompt.includes('git') && prompt.includes('rev-parse HEAD')) return [{ index: 0, ok: true, stdout: 'abc123' }]
        if (prompt.includes('engine_adapter.py build-argv')) return [{ index: 0, ok: true, stdout: JSON.stringify(['codex', 'exec', '-']) }]
        if (prompt.includes('--sandbox') || prompt.includes(' < ')) return new Promise(() => {})  // hang -> UFR-5 timeout
        if (prompt.includes('journal_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
        return [{ index: 0, ok: true, stdout: '{}' }]
      }],
    ])
    const rTimeoutN = await d.dispatchExternal({ engine: 'codex', roleKind: 'build', effort: 'high', prompt: 'z', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 0.01, taskId: 'T3', workItem: 'wi-1' })
    assert.strictEqual(rTimeoutN.reason, 'timeout', '#277 precondition: this scenario times out (CLI ran)')
    assert.ok(!logs.some((l) => /ENGINE-UNAVAILABLE/.test(l)),
      '#277: a timeout (CLI genuinely ran) must NOT trip the harness-dead notice')

    // (D) the dispatch-error disjunct — the EXACT #277 death signature (a synchronous throw before
    // the CLI ran, e.g. `dispatch-error: ReferenceError: Buffer is not defined`) — MUST fire the named
    // notice. Without this, deleting the `dispatch-error` clause from _isHarnessDeadReason would leave
    // every other assertion green while the tripwire silently stops firing on the very failure it
    // exists to make loud (mutation-survival gap, review finding test-001).
    d.__resetHarnessNotice(); logs.length = 0
    global.agent = () => { throw new Error('boom: missing sandbox global') }
    const rDeadD = await d.dispatchExternal({ engine: 'codex', roleKind: 'review', effort: 'high', prompt: 'x', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300 })
    assert.ok(/^dispatch-error: /.test(rDeadD.reason), '#277 (D): a synchronous throw yields a dispatch-error reason')
    const noticeD = logs.filter((l) => /ENGINE-UNAVAILABLE/.test(l))
    assert.strictEqual(noticeD.length, 1, '#277 (D): a dispatch-error reason trips the named notice exactly once')
    assert.ok(/dispatch-error/.test(noticeD[0]), '#277 (D): the notice carries the dispatch-error reason: ' + noticeD[0])

    // (E) the could-not-stage-external-output disjunct: prompt/schema staging + build-argv + the CLI
    // run all succeed, but staging the raw external OUTPUT (the .out file) fails -> the notice fires.
    // Closes the third keying disjunct (also un-asserted per finding test-001).
    d.__resetHarnessNotice(); logs.length = 0
    global.agent = makeAgent([
      ['exec', (prompt) => {
        if (prompt.includes('base64 -d >') && prompt.includes('.out')) return [{ index: 0, ok: false, stdout: '' }]
        if (prompt.includes('engine_adapter.py build-argv')) return [{ index: 0, ok: true, stdout: JSON.stringify(['codex', 'exec', '--sandbox', 'read-only', '-']) }]
        if (prompt.includes('--sandbox') || prompt.includes(' < ')) return [{ index: 0, ok: true, stdout: '{"ok":true}' }]
        if (prompt.includes('journal_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
        return [{ index: 0, ok: true, stdout: '{}' }]
      }],
    ])
    const rDeadE = await d.dispatchExternal({ engine: 'codex', roleKind: 'review', effort: 'high', prompt: 'x', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300, workItem: 'wi-1' })
    assert.strictEqual(rDeadE.reason, 'could-not-stage-external-output', '#277 (E): a failed external-output stage fails closed with that reason')
    const noticeE = logs.filter((l) => /ENGINE-UNAVAILABLE/.test(l))
    assert.strictEqual(noticeE.length, 1, '#277 (E): could-not-stage-external-output trips the named notice exactly once')
    d.__resetHarnessNotice()
  }

  console.log('OK: engine_dispatch #277 harness-dead tripwire (named once; all three pre-CLI keying disjuncts asserted)')

  // ---------------------------------------------------------------------
  // FIX 4a: _execJson courier-drop retry — a single empty/garbled stdout on a durable command is
  // retried ONCE (mirrors build_phase.js's canonical execJson contract); a PERSISTENT empty stdout
  // still fails closed after the retry.
  // ---------------------------------------------------------------------

  // (a1) build-argv drops its stdout ONCE (empty string, ok:true — a courier drop, not a real
  // failure) then succeeds on retry -> the dispatch completes fine (proves the retry fired).
  {
    let buildArgvCalls = 0
    global.agent = makeAgent([
      ['exec', (prompt) => {
        if (prompt.includes('engine_adapter.py build-argv')) {
          buildArgvCalls += 1
          if (buildArgvCalls === 1) return [{ index: 0, ok: true, stdout: '' }]
          return [{ index: 0, ok: true, stdout: JSON.stringify(['codex', 'exec', '--sandbox', 'read-only', '-']) }]
        }
        if (prompt.includes('engine_adapter.py parse-result')) {
          return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, findings: [] }) }]
        }
        if (prompt.includes('journal_entry.py')) {
          return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
        }
        if (prompt.includes('--sandbox')) return [{ index: 0, ok: true, stdout: '{}' }]
        return [{ index: 0, ok: true, stdout: '{}' }]
      }],
    ])
    const rRetryOk = await d.dispatchExternal({ engine: 'codex', roleKind: 'review', effort: 'high', prompt: 'review', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300 })
    assert.strictEqual(buildArgvCalls, 2, 'FIX 4a: a single empty-stdout courier drop is retried exactly once')
    assert.deepStrictEqual(rRetryOk.findings, [], 'FIX 4a: the retry succeeding lets the dispatch complete normally')
  }

  // (a2) build-argv drops its stdout on EVERY call (persistent empty) -> _execJson gives up after
  // the retry and the dispatch fails closed with build-argv-failed (never a bare throw/hang).
  {
    let buildArgvCalls2 = 0
    global.agent = makeAgent([
      ['exec', (prompt) => {
        if (prompt.includes('engine_adapter.py build-argv')) {
          buildArgvCalls2 += 1
          return [{ index: 0, ok: true, stdout: '' }]
        }
        return [{ index: 0, ok: true, stdout: '{}' }]
      }],
    ])
    const rRetryFail = await d.dispatchExternal({ engine: 'codex', roleKind: 'review', effort: 'high', prompt: 'review', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300 })
    assert.strictEqual(buildArgvCalls2, 2, 'FIX 4a: a persistent empty stdout is tried exactly twice (one retry) before giving up')
    assert.strictEqual(rRetryFail.ok, false, 'FIX 4a: a persistent courier drop fails closed')
  }

  console.log('OK: engine_dispatch _execJson courier-drop retry (transient recovers, persistent fails closed)')

  // ---------------------------------------------------------------------
  // FIX 4b: dispatchExternal early-failure branches — each must return {ok:false} and must NOT
  // commit or journal a success.
  // ---------------------------------------------------------------------

  // (b1) empty/unparseable build-argv (a REAL failure, not a courier drop — ok:false from the exec
  // itself) -> {ok:false}, and no commit/success-journal call is ever made.
  {
    const execLogB1 = []
    global.agent = makeAgent([
      ['exec', (prompt) => {
        execLogB1.push(prompt)
        if (prompt.includes('engine_adapter.py build-argv')) {
          return [{ index: 0, ok: false, stdout: '' }]
        }
        if (prompt.includes('journal_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
        return [{ index: 0, ok: true, stdout: '{}' }]
      }],
    ])
    const rBadArgv = await d.dispatchExternal({ engine: 'codex', roleKind: 'review', effort: 'high', prompt: 'review', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300 })
    assert.strictEqual(rBadArgv.ok, false, 'FIX 4b: an unparseable/failing build-argv fails closed')
    assert.ok(!execLogB1.some((c) => c.includes('engine_adapter.py commit')), 'FIX 4b: no commit is attempted when build-argv fails')
    assert.ok(!execLogB1.some((c) => c.includes('--sandbox') || c.includes(' < ')), 'FIX 4b: the CLI itself is never run when build-argv fails')
  }

  // (b2) preSHA git rev-parse fails for a WRITE role -> {ok:false} before any argv/CLI/commit work.
  {
    const execLogB2 = []
    global.agent = makeAgent([
      ['exec', (prompt) => {
        execLogB2.push(prompt)
        if (prompt.includes('git') && prompt.includes('rev-parse HEAD')) {
          return [{ index: 0, ok: false, stdout: '' }]
        }
        if (prompt.includes('journal_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
        return [{ index: 0, ok: true, stdout: '{}' }]
      }],
    ])
    const rBadPreSha = await d.dispatchExternal({ engine: 'codex', roleKind: 'build', effort: 'high', prompt: 'build', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300, taskId: 'T9', workItem: 'wi-abc' })
    assert.strictEqual(rBadPreSha.ok, false, 'FIX 4b: a failed preSHA capture fails closed')
    assert.strictEqual(rBadPreSha.reason, 'could-not-capture-preSHA', 'FIX 4b: the reason names the preSHA-capture failure')
    assert.ok(!execLogB2.some((c) => c.includes('engine_adapter.py build-argv')), 'FIX 4b: build-argv is never reached when preSHA capture fails')
    assert.ok(!execLogB2.some((c) => c.includes('engine_adapter.py commit')), 'FIX 4b: no commit is attempted when preSHA capture fails')
  }

  // (b3) staging the prompt/schema to disk fails -> {ok:false} before ANY other dispatch work
  // (preSHA/build-argv/CLI/commit never run).
  {
    const execLogB3 = []
    global.agent = makeAgent([
      ['exec', (prompt) => {
        execLogB3.push(prompt)
        if (prompt.includes('base64 -d >')) return [{ index: 0, ok: false, stdout: '' }]
        if (prompt.includes('journal_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
        return [{ index: 0, ok: true, stdout: '{}' }]
      }],
    ])
    const rBadStage = await d.dispatchExternal({ engine: 'codex', roleKind: 'build', effort: 'high', prompt: 'build', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300, taskId: 'T9', workItem: 'wi-abc' })
    assert.strictEqual(rBadStage.ok, false, 'FIX 4b: a failed input-staging write fails closed')
    assert.strictEqual(rBadStage.reason, 'could-not-stage-external-inputs', 'FIX 4b: the reason names the staging failure')
    assert.ok(!execLogB3.some((c) => c.includes('git') && c.includes('rev-parse HEAD')), 'FIX 4b: preSHA is never captured when staging fails')
    assert.ok(!execLogB3.some((c) => c.includes('engine_adapter.py commit')), 'FIX 4b: no commit is attempted when staging fails')
  }

  console.log('OK: engine_dispatch early-failure branches fail closed without committing or journaling success')

  // ---------------------------------------------------------------------
  // FIX 5: read-role UFR-6 fail-closed symmetry — the review/read role must ALSO fail closed when
  // the external_dispatch journal append fails (only the write role's UFR-6 was previously tested).
  // ---------------------------------------------------------------------
  {
    global.agent = makeAgent([
      ['exec', (prompt) => {
        if (prompt.includes('engine_adapter.py build-argv')) {
          return [{ index: 0, ok: true, stdout: JSON.stringify(['codex', 'exec', '--sandbox', 'read-only', '-']) }]
        }
        if (prompt.includes('engine_adapter.py parse-result')) {
          return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, findings: [{ file: 'a.py', line: 1, title: 'x', severity: 'Minor' }] }) }]
        }
        if (prompt.includes('journal_entry.py')) {
          return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: false }) }]
        }
        if (prompt.includes('--sandbox')) return [{ index: 0, ok: true, stdout: '{"raw":"external review output"}' }]
        return [{ index: 0, ok: true, stdout: '{}' }]
      }],
    ])
    const rReadUnauditable = await d.dispatchExternal({ engine: 'codex', roleKind: 'review', effort: 'high', prompt: 'review', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300, workItem: 'wi-abc' })
    assert.strictEqual(rReadUnauditable.ok, false, 'FIX 5: a read-role dispatch fails closed when the external_dispatch journal append fails')
    assert.strictEqual(rReadUnauditable.reason, 'unauditable', 'FIX 5: the read-role failure reason is unauditable, mirroring the write-role UFR-6 contract')
  }

  console.log('OK: engine_dispatch UFR-6 fail-closed symmetry (read role also fails closed on a failed journal append)')
})()

