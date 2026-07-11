// plugins/superheroes/lib/tests/showrunner_engine_dispatch_smoke.js
// #38: engine_dispatch.js dispatchExternal spine leaf wrapper. Mirrors build_phase_setup_smoke.js's
// makeAgent(routes)/execRoute idiom (route by exact label, then prompt substring), plus an ordered
// execLog so the stdin-redirect / audit-event assertions can inspect the exact dispatch-run command.
const assert = require('assert')
const { markedStdout } = require('./_marked_stdout.js')
const logs = []
global.log = (m) => logs.push(m)
// #341: the CLI-run dispatch now rides the HARDENED courier (superheroes:courier + __SR_EXIT marker),
// so a stubbed run leaf must return a MARKER-carrying answer (a bare array reads as a courier decline).
// Non-run exec leaves (staging/build-argv/parse-result/commit/journal) still ride the plain exec()
// dumb-pipe and keep their bare-array shape.

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
        return markedStdout('{"raw":"external review output"}')
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
        return markedStdout('{"raw":"external build output"}')
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
  // __SR_ROOT (the repo root) instead of the per-task build worktree. #341: the run now rides the
  // hardened marker courier (markedPromptFor: "Execute this exact shell command…\n\n<cmd>"), so the
  // confinement prefix follows the blank line rather than a numbered-list marker.
  assert.ok(/\n\ncd '\/tmp\/wt' && /.test(runCmd2), 'write dispatch must confine the run to cwd via cd <cwd> &&: ' + runCmd2)
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
          // What the real adapter emits for a cursor work role under the owner policy (2026-07-09):
          // the composer default — the threaded tier informs the adapter, the policy map decides.
          capturedArgv = ['cursor-agent', '--model', 'composer-2.5-fast', '-p', '--trust', '-f', '--output-format', 'stream-json']
          return [{ index: 0, ok: true, stdout: JSON.stringify(capturedArgv) }]
        }
        if (prompt.includes('engine_adapter.py parse-result')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, signal: 'ok', evidence: {} }) }]
        if (prompt.includes('engine_adapter.py commit')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, sha: 'newsha' }) }]
        if (prompt.includes('journal_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
        if (prompt.includes('--model')) return markedStdout('{"raw":"external build output"}')
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
        if (prompt.includes('--sandbox')) return markedStdout('{}')
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
  // #309/#299: the TIMEOUT-outcome journal enrichment — the exact case resolvedArgv was hoisted for.
  // A CLI killed at the ceiling must journal outcome:'timeout' WITH the argv it was running and the
  // effective ceiling, so the audit line reads unambiguously as "killed at ceiling after Ns" (distinct
  // from a genuine CLI failure) and never records a null argv for a run that really dispatched.
  // ---------------------------------------------------------------------
  {
    const execLogTO = []
    let argvTO = null
    global.agent = makeAgent([
      ['exec', (prompt) => {
        execLogTO.push(prompt)
        if (prompt.includes('git') && prompt.includes('rev-parse HEAD')) return [{ index: 0, ok: true, stdout: 'preSHA-abc\n' }]
        if (prompt.includes('engine_adapter.py build-argv')) {
          argvTO = ['codex', 'exec', '--sandbox', 'workspace-write', '-C', '/tmp/wt', '-']
          return [{ index: 0, ok: true, stdout: JSON.stringify(argvTO) }]
        }
        if (prompt.includes('journal_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
        if (prompt.includes('--sandbox') || prompt.includes(' < ')) return new Promise(() => {})   // CLI wedges -> ceiling kill
        return [{ index: 0, ok: true, stdout: '{}' }]
      }],
    ])
    const rTO = await d.dispatchExternal({ engine: 'codex', roleKind: 'build', effort: 'high', prompt: 'build',
      cwd: '/tmp/wt', schema: {}, timeoutSeconds: 0.05, taskId: 'T1', workItem: 'wi-abc' })
    assert.strictEqual(rTO.ok, false, '#309: a ceiling kill fails the dispatch')
    assert.strictEqual(rTO.reason, 'timeout', '#309: the ceiling kill reason is timeout')
    const journalTO = execLogTO.find((c) => c.includes('journal_entry.py') && c.includes('external_dispatch'))
    assert.ok(journalTO, '#309: a ceiling-killed dispatch still journals exactly one external_dispatch line')
    const payloadTO = JSON.parse(journalTO.match(/--payload '(.*)'$/s)[1])
    assert.strictEqual(payloadTO.outcome, 'timeout', '#299: the journal outcome is timeout (killed at ceiling)')
    assert.strictEqual(payloadTO.effectiveTimeout, 0.05, '#299: the journal records the ceiling it was killed at')
    assert.deepStrictEqual(payloadTO.argv, argvTO,
      '#299: the journal records the REAL argv the CLI was killed while running (resolvedArgv hoist), never null')
  }

  console.log('OK: engine_dispatch timeout-outcome journal enrichment (killed-at-ceiling audit line)')

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
        return markedStdout('{"ok":false,"signal":"plan_wrong"}')
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
      if (prompt.includes('--sandbox')) return markedStdout('{"ok":false,"signal":"plan_wrong"}')
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
      // The timeout-path journal payload embeds the resolved argv (which contains '--sandbox'), so this
      // MUST be matched before the '--sandbox' run-hang branch below — otherwise the timeout journal
      // itself hangs and dispatchExternal never returns (a latent smoke hang that silently exited the
      // process at 6 OKs under HEAD; every block below here previously never ran).
      if (prompt.includes('journal_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      if (prompt.includes('Execute this exact shell command')) {
        // Simulate a run-hang: resolve far later than the wrapper's own timeout, via an unref'd timer
        // so the never-taken branch doesn't pin the node process alive after the test moves on.
        return new Promise((resolve) => {
          const t = setTimeout(() => resolve(markedStdout('{"raw":"late"}')), 3600000)
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
        return markedStdout('{"raw":"external build output"}')
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
        return markedStdout('{"raw":"external build output"}')
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
  // #277/#257: the staging path must NOT depend on Node's `Buffer` — the Workflow sandbox has no Buffer
  // global (the old `Buffer.from(...)` in _stageCmd threw on its first statement, making EVERY external
  // dispatch silently fall open to Claude). #257 dropped base64 for a PLAIN-readable write whose fidelity
  // rides sha256hex (bytes.js) — also Buffer-LESS (and crypto-less), so the same #277 constraint holds on
  // the hash step. With Buffer deleted from the global scope (simulating the sandbox), a dispatch must
  // still stage its inputs (compute the verify hash + emit the plain command) and reach the CLI — the
  // exact regression class that was invisible to smokes running in plain node where Buffer exists.
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
        if (prompt.includes('--sandbox')) return markedStdout('{}')
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
    // #257: the prompt is staged via the plain python write+sha256-verify command (readable payload +
    // embedded hash), proving sha256hex ran with no Buffer — and NOT via any base64-decode blob.
    const promptStageNB = execLogNB.find((c) => c.includes(d._SR_STAGE_SIG) && c.includes('.prompt'))
    assert.ok(promptStageNB,
      '#257/#277: the prompt is staged via the plain hash-verified write even with no Buffer global')
    assert.ok(/stage me — 🎡 §/.test(promptStageNB),
      '#257: the staged prompt rides the command as readable text (no opaque blob): ' + promptStageNB)
    assert.ok(!/base64 -d/.test(promptStageNB),
      '#257: the staged command carries NO base64-decode blob: ' + promptStageNB)
    assert.ok(!logs.some((l) => /ENGINE-UNAVAILABLE/.test(l)),
      '#277: no harness-dead notice fires when staging succeeds Buffer-free')
  }

  console.log('OK: engine_dispatch stages inputs plain-readable with NO Buffer global (#257/#277)')

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
        if (prompt.includes(d._SR_STAGE_SIG)) return [{ index: 0, ok: false, stdout: '' }]
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
        if (prompt.includes(d._SR_STAGE_SIG) && prompt.includes('.out')) return [{ index: 0, ok: false, stdout: '' }]
        if (prompt.includes('engine_adapter.py build-argv')) return [{ index: 0, ok: true, stdout: JSON.stringify(['codex', 'exec', '--sandbox', 'read-only', '-']) }]
        // journal BEFORE the '--sandbox' run branch: the journal payload embeds the resolved argv
        // (which contains '--sandbox'), so a run-branch checked first would mis-route the journal leaf.
        if (prompt.includes('journal_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
        if (prompt.includes('--sandbox') || prompt.includes(' < ')) return markedStdout('{"ok":true}')
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
        if (prompt.includes('--sandbox')) return markedStdout('{}')
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
        if (prompt.includes(d._SR_STAGE_SIG)) return [{ index: 0, ok: false, stdout: '' }]
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
        if (prompt.includes('--sandbox')) return markedStdout('{"raw":"external review output"}')
        return [{ index: 0, ok: true, stdout: '{}' }]
      }],
    ])
    const rReadUnauditable = await d.dispatchExternal({ engine: 'codex', roleKind: 'review', effort: 'high', prompt: 'review', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300, workItem: 'wi-abc' })
    assert.strictEqual(rReadUnauditable.ok, false, 'FIX 5: a read-role dispatch fails closed when the external_dispatch journal append fails')
    assert.strictEqual(rReadUnauditable.reason, 'unauditable', 'FIX 5: the read-role failure reason is unauditable, mirroring the write-role UFR-6 contract')
  }

  console.log('OK: engine_dispatch UFR-6 fail-closed symmetry (read role also fails closed on a failed journal append)')

  // ---------------------------------------------------------------------
  // #341 COURIER DECLINE. A safety-trained cheapest-model courier leaf REFUSES the autonomous engine
  // command and answers prose instead of running it (the a7bade9a escape: cursor 0/2 in-child). The
  // marker-less answer plus a CLEAN worktree (the #343 corroboration — nothing executed) classifies a
  // decline: the dispatch must journal the HONEST `courier-declined` outcome (NEVER external-run-failed
  // — the engine was never tried), retry ONCE through the hardened path, and journal BOTH attempts.
  // #343: a WRITE dispatch runs SINGLE (one leaf per attempt, no chain re-dispatches — every chain
  // retry would hand the command to a new leaf that RE-RUNS it, a double-execution hazard).
  // ---------------------------------------------------------------------
  {
    const REFUSAL = "I can't proceed with this request as written. This pattern — an autonomous " +
      'agent invoked with --trust -f — raises concerns, so I will not run it.'
    const journalPayloads = []
    let runLeafDispatches = 0
    let dirtyProbes = 0
    global.agent = async (prompt) => {
      // #343 corroboration: the execution-evidence probe answers the POSITIVE clean sentinel (no
      // edits, unmoved HEAD, no capture files) so the marker-less answer classifies as a genuine
      // decline (probed before EACH classification). A bare empty stdout would read as a probe DROP
      // and classify "may have executed" (fail-safe) — clean must be this explicit shape. Matched
      // BEFORE the preSHA branch: the probe command embeds 'rev-parse HEAD' inside its $().
      if (prompt.includes('__SR_PROBE__')) { dirtyProbes += 1; return [{ index: 0, ok: true, stdout: '__SR_PROBE__ 0 preSHA-abc 0' }] }
      if (prompt.includes('git') && prompt.includes('rev-parse HEAD')) return [{ index: 0, ok: true, stdout: 'preSHA-abc\n' }]
      if (prompt.includes('engine_adapter.py build-argv')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify(['cursor-agent', '--model', 'composer-2.5-fast', '-p', '--trust', '-f', '--output-format', 'stream-json']) }]
      }
      // journal BEFORE the run branch (the payload embeds the '--trust'/'-f' argv).
      if (prompt.includes('journal_entry.py')) {
        const m = prompt.match(/--payload '(.*)'$/s)
        // The refusal declinePrefix carries an apostrophe ("can't"), which shq escapes as '\'' — undo
        // that shell quoting before parsing (proves the prose survives the shq round-trip intact).
        if (m) { try { journalPayloads.push(JSON.parse(m[1].replace(/'\\''/g, "'"))) } catch (_e) { /* asserted below */ } }
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      }
      // The hardened marker-courier run dispatch (markedPromptFor). REFUSE with prose — no __SR_EXIT
      // marker — exactly the cheapest-model decline this fix exists for.
      if (prompt.includes('Execute this exact shell command')) {
        runLeafDispatches += 1
        return REFUSAL
      }
      return [{ index: 0, ok: true, stdout: '{}' }]
    }
    const rDecline = await d.dispatchExternal({ engine: 'cursor', roleKind: 'build', effort: 'composer',
      prompt: 'build', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 2400, idleSeconds: 600, taskId: 'T1', workItem: 'wi-decline' })
    // Honest distinct outcome — NEVER external-run-failed (promise 4/5: don't blame the engine).
    assert.strictEqual(rDecline.ok, false, '#341: a persistent courier decline fails the dispatch (falls open to Claude)')
    assert.strictEqual(rDecline.reason, 'courier-declined',
      '#341: a courier decline surfaces the honest courier-declined reason, not external-run-failed: ' + rDecline.reason)
    // BOTH attempts journaled as courier-declined proves the retry-once fired; NONE as
    // external-run-failed.
    const declined = journalPayloads.filter((p) => p.outcome === 'courier-declined')
    assert.strictEqual(declined.length, 2, '#341: a decline retries ONCE — BOTH attempts are journaled as courier-declined: ' + JSON.stringify(journalPayloads.map((p) => p.outcome)))
    // #343: a WRITE dispatch is SINGLE-dispatch per attempt — exactly 2 run leaves total (1 per
    // attempt), never the idempotent chain's 2×3 fan-out (each extra leaf would RE-RUN the command).
    assert.strictEqual(runLeafDispatches, 2, '#343: write decline = exactly one leaf per attempt (no chain re-execution): ' + runLeafDispatches)
    assert.strictEqual(dirtyProbes, 2, '#343: each decline classification is corroborated by a worktree dirty-probe: ' + dirtyProbes)
    assert.ok(!journalPayloads.some((p) => p.outcome === 'external-run-failed'),
      '#341: a courier decline is NEVER journaled as external-run-failed (the engine was never tried)')
    // The refusal prose is carried as clamped reason-context (audit line self-identifies the decline).
    assert.ok(declined.every((p) => typeof p.declinePrefix === 'string' && p.declinePrefix.includes("I can't proceed")),
      '#341: the courier-declined journal carries a prefix of the leaf refusal prose: ' + JSON.stringify(declined.map((p) => p.declinePrefix)))
    // The enriched engine/model/argv fields still ride the decline audit line (not a bare failure).
    assert.ok(declined.every((p) => p.engine === 'cursor' && Array.isArray(p.argv) && p.argv.includes('--trust')),
      '#341: the courier-declined audit line still carries the engine + resolved argv')
    console.log('OK: engine_dispatch #341 courier-declined (honest outcome, retry-once, both attempts journaled, never external-run-failed)')
  }

  // ---------------------------------------------------------------------
  // #341 DECLINE-THEN-RECOVER (review finding test-002). The retry-once exists because the refusal is
  // STOCHASTIC — a first-attempt decline that RECOVERS on the retry must complete the dispatch
  // normally (engine ran), journaling the engine outcome, NOT courier-declined. Guards a broken-recovery
  // mutant (a retry that silently drops the recovered result).
  // ---------------------------------------------------------------------
  {
    const REFUSAL = "I won't run this."
    const journalP = []
    let runLeaf = 0
    global.agent = async (prompt) => {
      if (prompt.includes('__SR_PROBE__')) return [{ index: 0, ok: true, stdout: '__SR_PROBE__ 0 preSHA-abc 0' }]   // clean -> genuine decline (before preSHA: probe embeds rev-parse)
      if (prompt.includes('git') && prompt.includes('rev-parse HEAD')) return [{ index: 0, ok: true, stdout: 'preSHA-abc\n' }]
      if (prompt.includes('engine_adapter.py build-argv')) return [{ index: 0, ok: true, stdout: JSON.stringify(['cursor-agent', '--trust', '-f']) }]
      if (prompt.includes('engine_adapter.py parse-result')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, signal: 'ok', evidence: {} }) }]
      if (prompt.includes('engine_adapter.py commit')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, sha: 'newsha' }) }]
      if (prompt.includes('journal_entry.py')) {
        const m = prompt.match(/--payload '(.*)'$/s)
        if (m) { try { journalP.push(JSON.parse(m[1].replace(/'\\''/g, "'"))) } catch (_e) {} }
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      }
      // #343 single-dispatch write: attempt 1's ONE leaf refuses; the retry's leaf succeeds.
      if (prompt.includes('Execute this exact shell command')) {
        runLeaf += 1
        return runLeaf === 1 ? REFUSAL : markedStdout('{"ok":true,"signal":"ok"}')
      }
      return [{ index: 0, ok: true, stdout: '{}' }]
    }
    const rRecover = await d.dispatchExternal({ engine: 'cursor', roleKind: 'build', effort: 'composer',
      prompt: 'build', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 2400, idleSeconds: 600, taskId: 'T1', workItem: 'wi-recover' })
    assert.strictEqual(rRecover.ok, true, '#341: a decline that recovers on the retry completes the dispatch normally')
    assert.strictEqual(runLeaf, 2, '#341/#343: the retry re-dispatched exactly one more leaf after the first decline: ' + runLeaf)
    const recJournals = journalP.filter((p) => p.engine === 'cursor')
    assert.strictEqual(recJournals.length, 1, '#341: a recovered dispatch journals exactly ONE external_dispatch line (the engine outcome): ' + JSON.stringify(recJournals.map((p) => p.outcome)))
    assert.strictEqual(recJournals[0].outcome, 'ok', '#341: the recovered dispatch journals the engine outcome (ok), NOT courier-declined')
    console.log('OK: engine_dispatch #341 decline-then-recover (retry recovers -> normal completion, engine outcome journaled)')
  }

  // ---------------------------------------------------------------------
  // #341 EMPTY-STDOUT IS NOT A DECLINE (review finding code-001/premortem-001). A courier answer that
  // CARRIES the __SR_EXIT marker but has empty stdout proves the shell EXECUTED (marker present) and
  // simply printed nothing — an engine outcome, NOT a courier decline. It must map to
  // external-run-failed (engine ran, no usable output), NEVER courier-declined, and must NOT retry a
  // possibly-mutating write. Guards the mislabel that would journal a dishonest "engine never tried".
  // ---------------------------------------------------------------------
  {
    const journalP = []
    let runLeaf = 0
    global.agent = async (prompt) => {
      if (prompt.includes('git') && prompt.includes('rev-parse HEAD')) return [{ index: 0, ok: true, stdout: 'preSHA-abc\n' }]
      if (prompt.includes('engine_adapter.py build-argv')) return [{ index: 0, ok: true, stdout: JSON.stringify(['cursor-agent', '--trust', '-f']) }]
      if (prompt.includes('journal_entry.py')) {
        const m = prompt.match(/--payload '(.*)'$/s)
        if (m) { try { journalP.push(JSON.parse(m[1].replace(/'\\''/g, "'"))) } catch (_e) {} }
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      }
      // Marker PRESENT (executed) but stdout empty -> runCourierMarkedText throws
      // CourierTransportError('empty stdout'), which is NOT the marker-absent decline signal.
      if (prompt.includes('Execute this exact shell command')) { runLeaf += 1; return markedStdout('') }
      return [{ index: 0, ok: true, stdout: '{}' }]
    }
    const rEmpty = await d.dispatchExternal({ engine: 'cursor', roleKind: 'build', effort: 'composer',
      prompt: 'build', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 2400, idleSeconds: 600, taskId: 'T1', workItem: 'wi-empty' })
    assert.strictEqual(rEmpty.reason, 'external-run-failed',
      '#341: a marker-present empty-stdout run is an engine failure, NOT a courier decline: ' + rEmpty.reason)
    assert.ok(!journalP.some((p) => p.outcome === 'courier-declined'),
      '#341: a run that EXECUTED (marker present) is NEVER journaled courier-declined (the engine WAS tried)')
    assert.strictEqual(runLeaf, 1, '#341/#343: an empty-stdout (executed) write is ONE leaf — no decline retry, no chain re-execution: ' + runLeaf)
    console.log('OK: engine_dispatch #341 empty-stdout is an engine failure, not a courier decline (no mislabel, no unsafe retry)')
  }

  // ---------------------------------------------------------------------
  // #343 FALSE-DECLINE-ON-EXECUTED (the PR-343 vet's live find). The leaf EXECUTES the write command
  // but its huge output is persisted by the leaf harness to a tool-results file, so the ANSWER is just
  // a file-pointer sentence — NO markers, indistinguishable from a decline by the answer alone. The
  // worktree dirty-probe corroborates: the tree is DIRTY (the engine ran and edited), so the dispatch
  // must classify external-run-failed (engine outcome; the caller falls open + UFR-2 resets edits) —
  // NEVER courier-declined, and NEVER retried (a retry would DOUBLE-EXECUTE on the edited tree).
  // ---------------------------------------------------------------------
  {
    const POINTER = 'Full stdout saved to: `/Users/x/.claude/projects/y/tool-results/abc123.txt`'
    const journalP = []
    let runLeaf = 0
    let probes = 0
    global.agent = async (prompt) => {
      // NOTE: the evidence probe's command ALSO contains 'rev-parse HEAD' (inside its $()), so the
      // probe branch must be matched FIRST — the preSHA capture is the bare rev-parse command.
      // DIRTY tree — the engine ran and left 2 uncommitted edits.
      if (prompt.includes('__SR_PROBE__')) { probes += 1; return [{ index: 0, ok: true, stdout: '__SR_PROBE__ 2 preSHA-abc 0' }] }
      if (prompt.includes('git') && prompt.includes('rev-parse HEAD')) return [{ index: 0, ok: true, stdout: 'preSHA-abc\n' }]
      if (prompt.includes('engine_adapter.py build-argv')) return [{ index: 0, ok: true, stdout: JSON.stringify(['cursor-agent', '--trust', '-f']) }]
      if (prompt.includes('journal_entry.py')) {
        const m = prompt.match(/--payload '(.*)'$/s)
        if (m) { try { journalP.push(JSON.parse(m[1].replace(/'\\''/g, "'"))) } catch (_e) {} }
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      }
      if (prompt.includes('Execute this exact shell command')) { runLeaf += 1; return POINTER }
      return [{ index: 0, ok: true, stdout: '{}' }]
    }
    const rPointer = await d.dispatchExternal({ engine: 'cursor', roleKind: 'build', effort: 'composer',
      prompt: 'build', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 2400, idleSeconds: 600, taskId: 'T1', workItem: 'wi-pointer' })
    assert.strictEqual(rPointer.ok, false, '#343: an executed-but-pointer-answer write fails the dispatch (falls open)')
    assert.strictEqual(rPointer.reason, 'external-run-failed',
      '#343: a marker-less answer over a DIRTY tree is an ENGINE failure (it ran), never courier-declined: ' + rPointer.reason)
    assert.strictEqual(runLeaf, 1, '#343: the executed write is NEVER retried (retry = double execution on the edited tree): ' + runLeaf)
    assert.strictEqual(probes, 1, '#343: exactly one dirty-probe corroborated the classification')
    assert.ok(!journalP.some((p) => p.outcome === 'courier-declined'),
      '#343: no courier-declined line for an engine that actually ran (honest audit)')
    assert.ok(journalP.some((p) => p.outcome === 'external-run-failed'),
      '#343: the failure is journaled as the engine outcome external-run-failed')
    console.log('OK: engine_dispatch #343 false-decline-on-executed (dirty-probe corroboration: engine failure, no retry, no double execution)')
  }

  // ---------------------------------------------------------------------
  // #343 EVIDENCE SIGNALS 2/3 + PROBE-DROP FAIL-SAFE (delta review premortem-001/code-001/code-002).
  // The probe must classify "may have executed" (-> external-run-failed, NO retry) on EACH of:
  //   (a) HEAD moved off preSha — an engine that SELF-COMMITTED reads porcelain-clean;
  //   (b) watchdog capture files exist — the run STARTED (failed, or an orphaned CLI is still going);
  //   (c) a DROPPED probe answer (ok:true, empty stdout — the exec courier's known drop shape) — the
  //       clean verdict must be the explicit positive sentinel, a drop can never impersonate it.
  // ---------------------------------------------------------------------
  {
    const CASES = [
      ['self-commit (HEAD moved)', '__SR_PROBE__ 0 somesha999 0'],
      ['capture files present', '__SR_PROBE__ 0 preSHA-abc 3'],
      ['probe answer dropped', ''],
    ]
    for (const [name, probeAnswer] of CASES) {
      const journalP = []
      let runLeaf = 0
      global.agent = async (prompt) => {
        if (prompt.includes('__SR_PROBE__')) return [{ index: 0, ok: true, stdout: probeAnswer }]
        if (prompt.includes('git') && prompt.includes('rev-parse HEAD')) return [{ index: 0, ok: true, stdout: 'preSHA-abc\n' }]
        if (prompt.includes('engine_adapter.py build-argv')) return [{ index: 0, ok: true, stdout: JSON.stringify(['cursor-agent', '--trust', '-f']) }]
        if (prompt.includes('journal_entry.py')) {
          const m = prompt.match(/--payload '(.*)'$/s)
          if (m) { try { journalP.push(JSON.parse(m[1].replace(/'\\''/g, "'"))) } catch (_e) {} }
          return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
        }
        if (prompt.includes('Execute this exact shell command')) { runLeaf += 1; return 'Saved output to a file.' }
        return [{ index: 0, ok: true, stdout: '{}' }]
      }
      const r = await d.dispatchExternal({ engine: 'cursor', roleKind: 'build', effort: 'composer',
        prompt: 'build', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 2400, idleSeconds: 600, taskId: 'T1', workItem: 'wi-ev' })
      assert.strictEqual(r.reason, 'external-run-failed', `#343 (${name}): evidence -> engine failure, never courier-declined: ` + r.reason)
      assert.strictEqual(runLeaf, 1, `#343 (${name}): never retried (no double execution): ` + runLeaf)
      assert.ok(!journalP.some((p) => p.outcome === 'courier-declined'), `#343 (${name}): no courier-declined audit line`)
    }
    console.log('OK: engine_dispatch #343 evidence signals (self-commit HEAD move, capture files, dropped probe) all block the retry')
  }

  // ---------------------------------------------------------------------
  // #343 ECHO+EXECUTED ACCEPTANCE. An answer that BOTH echoes the command (carrying the literal
  // unexpanded '__SR_EXIT:$?') AND carries the real runtime-expanded '__SR_EXIT:0' from actually
  // running it fails badCourierAnswer — but the digit marker (executedMarker) proves execution, so
  // the dispatch must ACCEPT the answer (markerSliceStdout takes the LAST digit marker) instead of
  // re-dispatching a leaf that would RE-RUN the write.
  // ---------------------------------------------------------------------
  {
    const journalP = []
    let runLeaf = 0
    global.agent = async (prompt) => {
      if (prompt.includes('git') && prompt.includes('rev-parse HEAD')) return [{ index: 0, ok: true, stdout: 'preSHA-abc\n' }]
      if (prompt.includes('engine_adapter.py build-argv')) return [{ index: 0, ok: true, stdout: JSON.stringify(['cursor-agent', '--trust', '-f']) }]
      if (prompt.includes('engine_adapter.py parse-result')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, signal: 'ok', evidence: {} }) }]
      if (prompt.includes('engine_adapter.py commit')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, sha: 'newsha' }) }]
      if (prompt.includes('journal_entry.py')) {
        const m = prompt.match(/--payload '(.*)'$/s)
        if (m) { try { journalP.push(JSON.parse(m[1].replace(/'\\''/g, "'"))) } catch (_e) {} }
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      }
      if (prompt.includes('Execute this exact shell command')) {
        runLeaf += 1
        // Echoed command first (unexpanded $? literal), then the real executed output + digit marker.
        return 'I ran: sh -c ... 2>&1; echo __SR_EXIT:$?\n{"raw":"external build output"}\n__SR_EXIT:0'
      }
      return [{ index: 0, ok: true, stdout: '{}' }]
    }
    const rEcho = await d.dispatchExternal({ engine: 'cursor', roleKind: 'build', effort: 'composer',
      prompt: 'build', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 2400, idleSeconds: 600, taskId: 'T1', workItem: 'wi-echo' })
    assert.strictEqual(rEcho.ok, true, '#343: an echo+digit-marker answer is ACCEPTED as executed (the dispatch completes)')
    assert.strictEqual(runLeaf, 1, '#343: the executed answer is never re-dispatched (no re-run just because the $? literal rides along): ' + runLeaf)
    assert.ok(journalP.some((p) => p.outcome === 'ok'), '#343: the accepted dispatch journals the normal ok outcome')
    console.log('OK: engine_dispatch #343 echo+executed answer accepted (executedMarker tiebreak, no re-dispatch)')
  }

  // ---------------------------------------------------------------------
  // #373 PRE-CLI EARLY EXITS ARE NOW JOURNALED. A dispatch that dies BEFORE the CLI runs — staging the
  // prompt/schema to /tmp, or (write roles) capturing preSHA — used to RETURN before the journal point,
  // leaving ZERO trace in events.jsonl (the live 2026-07-11 case: the auto-mode classifier denied
  // cursor's base64 staging courier 4/4, so the run read as "cursor never routed"). Each early exit now
  // emits exactly one external_dispatch line with a distinct outcome token; a denial rides a bounded
  // `reason`. The RETURN reasons are UNCHANGED (the #277 harness-dead tripwire still keys on them).
  // ---------------------------------------------------------------------
  {
    const DENIAL = 'Permission for this action was denied by the Claude Code auto mode classifier. ' +
      'Reason: Auto mode could not evaluate this action and is blocking it for safety.'
    // Helper: collect every external_dispatch journal payload the dispatch appends.
    function journalCollector(collector, routes, journalResult) {
      const jOut = journalResult == null ? { ok: true } : journalResult
      return async (prompt) => {
        if (prompt.includes('journal_entry.py')) {
          const m = prompt.match(/--payload '(.*)'$/s)
          if (m) { try { collector.push(JSON.parse(m[1].replace(/'\\''/g, "'"))) } catch (_e) { /* asserted below */ } }
          return [{ index: 0, ok: true, stdout: JSON.stringify(jOut) }]
        }
        for (const [needle, resp] of routes) if (prompt.includes(needle)) return typeof resp === 'function' ? resp(prompt) : resp
        return [{ index: 0, ok: true, stdout: '{}' }]
      }
    }

    // (a) STAGING DENIED: the staging courier is blocked by the classifier — the failed leaf's
    // stdout carries the denial prose. The dispatch journals outcome:'staging-denied' WITH a bounded
    // `reason` (the denial text), exactly one line, argv null (build-argv never ran), and returns the
    // unchanged could-not-stage-external-inputs reason. (#257: routes on the plain stage signature.)
    {
      d.__resetHarnessNotice()
      const jp = []
      global.agent = journalCollector(jp, [
        [d._SR_STAGE_SIG, [{ index: 0, ok: false, stdout: DENIAL }]],
      ])
      const r = await d.dispatchExternal({ engine: 'cursor', roleKind: 'build', effort: 'composer', prompt: 'secret build prompt', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 2400, idleSeconds: 600, taskId: 'T373', workItem: 'wi-373-deny' })
      assert.strictEqual(r.reason, 'could-not-stage-external-inputs', '#373: the caller-facing return reason is UNCHANGED (harness-dead tripwire keys on it)')
      const ed = jp.filter((p) => p.outcome === 'staging-denied')
      assert.strictEqual(jp.length, 1, '#373: exactly ONE external_dispatch journal line total (no stray outcome): ' + JSON.stringify(jp.map((p) => p.outcome)))
      assert.strictEqual(ed.length, 1, '#373: a denied staging journals EXACTLY ONE staging-denied line (no double-append, #350): ' + JSON.stringify(jp.map((p) => p.outcome)))
      assert.strictEqual(ed[0].engine, 'cursor', '#373: the staging-denied line names the routed engine')
      assert.strictEqual(ed[0].argv, null, '#373: argv is null (honest — build-argv never ran before the pre-CLI death)')
      assert.ok(typeof ed[0].reason === 'string' && ed[0].reason.includes('Permission for this action was denied'),
        '#373: the staging-denied line carries the bounded denial reason: ' + ed[0].reason)
      // The reason must NEVER contain the staged PROMPT content.
      assert.ok(!ed[0].reason.includes('secret build prompt'), '#373: the reason never leaks the staged prompt content')
      console.log('OK: engine_dispatch #373 staging-denied journals one line with the bounded denial reason')
    }

    // (a2) DENIAL-REASON WINDOWING: with #257's PLAIN staging the failed leaf can ECHO the staging
    // command with the READABLE prompt right there in it (`python3 -c … '<prompt>' '<hash>'`) BEFORE the
    // denial prose. The reason window STARTS at the denial phrase — so the readable payload can never
    // ride into the audit line (the windowing that guarded the base64 blob now guards the plain payload).
    {
      d.__resetHarnessNotice()
      const jp = []
      const SECRET = 'SECRETPROMPT-abc123'
      const ECHOED = "python3 -c '…hashlib.sha256…' /tmp/engine-x.prompt '" + SECRET + "' 'deadbeef'\n" + DENIAL
      global.agent = journalCollector(jp, [
        [d._SR_STAGE_SIG, [{ index: 0, ok: false, stdout: ECHOED }]],
      ])
      await d.dispatchExternal({ engine: 'cursor', roleKind: 'review', effort: 'composer', prompt: SECRET, cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300, workItem: 'wi-373-window' })
      const ed = jp.filter((p) => p.outcome === 'staging-denied')
      assert.strictEqual(jp.length, 1, '#373: exactly ONE external_dispatch journal line total (no stray outcome): ' + JSON.stringify(jp.map((p) => p.outcome)))
      assert.strictEqual(ed.length, 1, '#373: read-role staging denial also journals one staging-denied line')
      assert.ok(ed[0].reason.startsWith('Permission for this action was denied'), '#373: the reason window starts at the denial phrase: ' + ed[0].reason)
      assert.ok(!ed[0].reason.includes(SECRET), '#257/#373: the echoed readable prompt never leaks into the reason: ' + ed[0].reason)
      console.log('OK: engine_dispatch #373 denial-reason windowing (echoed plain payload excluded)')
    }

    // (a3) DENIAL-REASON CLAMP + REDACTION: denial prose exceeds 200 chars and the forward window also
    // captures an echoed base64 staging command — the reason is clamped (≤201) and long base64 runs are
    // redacted so no reversible payload fragment persists.
    {
      d.__resetHarnessNotice()
      const jp = []
      const secretPayload = 'SECRET_PROMPT_CLAMP_TEST_12'
      const blob = Buffer.from(secretPayload).toString('base64')
      const blobFrag = blob.slice(0, 24)
      const denialPrefix = 'Permission denied by auto mode classifier. '
      const echoed = ` cmd: printf '${blob}'|base64 -d>/tmp/e373-${process.pid}`
      const longTail = ' Additional denial context that extends the full stdout well past two hundred characters so the clamp is exercised on prose that would otherwise grow without bound and never fit in the audit line.'
      const ECHOED_AFTER = denialPrefix + echoed + longTail
      assert.ok(ECHOED_AFTER.length > 200, '#373: denial stdout exceeds 200 chars')
      assert.ok((denialPrefix + echoed).length <= 200, '#373: echoed staging command rides inside the forward window')
      global.agent = journalCollector(jp, [
        ['base64 -d >', [{ index: 0, ok: false, stdout: ECHOED_AFTER }]],
      ])
      await d.dispatchExternal({ engine: 'cursor', roleKind: 'review', effort: 'composer', prompt: secretPayload, cwd: '/tmp/wt', schema: {}, timeoutSeconds: 300, workItem: 'wi-373-clamp' })
      const ed = jp.filter((p) => p.outcome === 'staging-denied')
      assert.strictEqual(jp.length, 1, '#373: exactly ONE external_dispatch journal line total (no stray outcome): ' + JSON.stringify(jp.map((p) => p.outcome)))
      assert.strictEqual(ed.length, 1, '#373: clamp+redaction case journals one staging-denied line')
      assert.ok(ed[0].reason.length <= 201, '#373: the journaled reason is clamped to ≤201 chars (200 + ellipsis): len=' + ed[0].reason.length)
      assert.ok(!ed[0].reason.includes(blobFrag), '#373: no base64 fragment of the staged blob appears in the reason: ' + ed[0].reason)
      assert.ok(!ed[0].reason.includes(secretPayload), '#373: the raw prompt never leaks into the reason')
      console.log('OK: engine_dispatch #373 denial-reason clamp + base64 redaction (≤201 chars, no payload fragment)')
    }

    // (b) STAGING FAILED (no denial signature): a plain courier/exec staging error (empty stdout) →
    // outcome:'staging-failed' with NO reason field (there is no denial prose to disclose).
    {
      d.__resetHarnessNotice()
      const jp = []
      global.agent = journalCollector(jp, [
        [d._SR_STAGE_SIG, [{ index: 0, ok: false, stdout: '' }]],
      ])
      const r = await d.dispatchExternal({ engine: 'cursor', roleKind: 'build', effort: 'composer', prompt: 'p', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 2400, idleSeconds: 600, taskId: 'T373', workItem: 'wi-373-fail' })
      assert.strictEqual(r.reason, 'could-not-stage-external-inputs', '#373: return reason unchanged for a non-denial staging failure')
      const ed = jp.filter((p) => p.outcome === 'staging-failed')
      assert.strictEqual(jp.length, 1, '#373: exactly ONE external_dispatch journal line total (no stray outcome): ' + JSON.stringify(jp.map((p) => p.outcome)))
      assert.strictEqual(ed.length, 1, '#373: a plain staging failure journals EXACTLY ONE staging-failed line: ' + JSON.stringify(jp.map((p) => p.outcome)))
      assert.ok(!('reason' in ed[0]) || ed[0].reason == null, '#373: a non-denial staging failure carries NO reason field (nothing to disclose): ' + JSON.stringify(ed[0]))
      assert.ok(!jp.some((p) => p.outcome === 'staging-denied'), '#373: a no-signature failure is NOT mislabeled staging-denied')
      console.log('OK: engine_dispatch #373 staging-failed journals one line, no reason field, not mislabeled as denied')
    }

    // (c) PRESHA FAILED (write role): staging succeeds, but the write-role preSHA git capture fails →
    // outcome:'presha-failed', exactly one line, before build-argv/CLI/commit ever run.
    {
      d.__resetHarnessNotice()
      const jp = []
      const seen = []
      global.agent = async (prompt) => {
        seen.push(prompt)
        if (prompt.includes('journal_entry.py')) {
          const m = prompt.match(/--payload '(.*)'$/s)
          if (m) { try { jp.push(JSON.parse(m[1].replace(/'\\''/g, "'"))) } catch (_e) {} }
          return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
        }
        if (prompt.includes('git') && prompt.includes('rev-parse HEAD')) return [{ index: 0, ok: false, stdout: '' }]  // preSHA capture fails
        return [{ index: 0, ok: true, stdout: '{}' }]   // staging succeeds
      }
      const r = await d.dispatchExternal({ engine: 'cursor', roleKind: 'build', effort: 'composer', prompt: 'p', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 2400, idleSeconds: 600, taskId: 'T373', workItem: 'wi-373-presha' })
      assert.strictEqual(r.reason, 'could-not-capture-preSHA', '#373: return reason unchanged for a preSHA failure')
      const ed = jp.filter((p) => p.outcome === 'presha-failed')
      assert.strictEqual(jp.length, 1, '#373: exactly ONE external_dispatch journal line total (no stray outcome): ' + JSON.stringify(jp.map((p) => p.outcome)))
      assert.strictEqual(ed.length, 1, '#373: a preSHA failure journals EXACTLY ONE presha-failed line: ' + JSON.stringify(jp.map((p) => p.outcome)))
      assert.strictEqual(ed[0].engine, 'cursor', '#373: the presha-failed line names the routed engine')
      assert.ok(!seen.some((c) => c.includes('engine_adapter.py build-argv')), '#373: build-argv is never reached after a preSHA failure')
      assert.ok(!seen.some((c) => c.includes('engine_adapter.py commit')), '#373: no commit is attempted after a preSHA failure')
      console.log('OK: engine_dispatch #373 presha-failed journals one line before build-argv/CLI/commit')
    }

    // (c2) STAGING DENIED + JOURNAL APPEND FAILS: the classifier blocks staging and the audit append
    // itself fails -> fail-closed 'unauditable' (NOT could-not-stage-external-inputs).
    {
      d.__resetHarnessNotice()
      const jp = []
      global.agent = journalCollector(jp, [
        ['base64 -d >', [{ index: 0, ok: false, stdout: DENIAL }]],
      ], { ok: false })
      const r = await d.dispatchExternal({ engine: 'cursor', roleKind: 'build', effort: 'composer', prompt: 'secret build prompt', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 2400, idleSeconds: 600, taskId: 'T373', workItem: 'wi-373-unaud-staging' })
      assert.strictEqual(r.ok, false, '#373: staging denial with journal failure returns ok:false')
      assert.strictEqual(r.reason, 'unauditable', '#373: journal append failure fail-closed to unauditable (NOT could-not-stage-external-inputs): ' + r.reason)
      console.log('OK: engine_dispatch #373 staging-denied + journal failure -> unauditable fail-closed')
    }

    // (c3) PRESHA FAILED + JOURNAL APPEND FAILS: write-role staging succeeds, preSHA capture fails,
    // and the audit append itself fails -> fail-closed 'unauditable' (NOT could-not-capture-preSHA).
    {
      d.__resetHarnessNotice()
      const jp = []
      global.agent = journalCollector(jp, [
        ['git', (p) => p.includes('rev-parse HEAD') ? [{ index: 0, ok: false, stdout: '' }] : [{ index: 0, ok: true, stdout: '{}' }]],
      ], { ok: false })
      const r = await d.dispatchExternal({ engine: 'cursor', roleKind: 'build', effort: 'composer', prompt: 'p', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 2400, idleSeconds: 600, taskId: 'T373', workItem: 'wi-373-unaud-presha' })
      assert.strictEqual(r.ok, false, '#373: preSHA failure with journal failure returns ok:false')
      assert.strictEqual(r.reason, 'unauditable', '#373: journal append failure fail-closed to unauditable (NOT could-not-capture-preSHA): ' + r.reason)
      console.log('OK: engine_dispatch #373 presha-failed + journal failure -> unauditable fail-closed')
    }

    // (d) SUCCESSFUL DISPATCH UNCHANGED: a normal write build still journals EXACTLY ONE external_dispatch
    // line (outcome:'ok') — the new early-exit journaling must not add a stray line to the happy path
    // (guards against #350 double-append and against a pre-CLI journal firing when staging succeeds).
    {
      d.__resetHarnessNotice()
      const jp = []
      global.agent = journalCollector(jp, [
        ['git', (p) => p.includes('rev-parse HEAD') ? [{ index: 0, ok: true, stdout: 'preSHA-abc\n' }] : [{ index: 0, ok: true, stdout: '{}' }]],
        ['engine_adapter.py build-argv', [{ index: 0, ok: true, stdout: JSON.stringify(['cursor-agent', '--trust', '-f']) }]],
        ['engine_adapter.py parse-result', [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, signal: 'ok', evidence: {} }) }]],
        ['engine_adapter.py commit', [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, sha: 'newsha' }) }]],
        ['Execute this exact shell command', markedStdout('{"ok":true,"signal":"ok"}')],
      ])
      const r = await d.dispatchExternal({ engine: 'cursor', roleKind: 'build', effort: 'composer', prompt: 'p', cwd: '/tmp/wt', schema: {}, timeoutSeconds: 2400, idleSeconds: 600, taskId: 'T373', workItem: 'wi-373-ok' })
      assert.strictEqual(r.ok, true, '#373: the happy-path write dispatch still succeeds')
      assert.strictEqual(jp.length, 1, '#373: a successful dispatch journals EXACTLY ONE external_dispatch line (no stray pre-CLI line): ' + JSON.stringify(jp.map((p) => p.outcome)))
      assert.strictEqual(jp[0].outcome, 'ok', '#373: the single line is the ok outcome')
      assert.ok(!jp.some((p) => ['staging-denied', 'staging-failed', 'presha-failed'].includes(p.outcome)), '#373: no pre-CLI early-exit token appears on the happy path')
      console.log('OK: engine_dispatch #373 successful dispatch unchanged (exactly one ok line, no stray pre-CLI journal)')
    }
  }

  // ---------------------------------------------------------------------
  // #257 PLAIN-READABLE STAGE-WRITE + HASH-VERIFY FIDELITY. The base64 courier's opacity was the live
  // 2026-07-11 failure mode (the auto-mode classifier denied all 4 cursor stagings). _stageCmd now emits
  // a plain, readable python write + Python-side sha256 verify. These drive the REAL command through an
  // actual bash+python (not a mock) to prove: (1) an arbitrary payload — quotes, backslashes, newlines,
  // non-ASCII, shell metacharacters, even text that looks like the stage signature or a denial phrase —
  // round-trips to disk BYTE-EXACT and the embedded-hash verify EXITS 0; (2) a transit mangle of the
  // readable payload (its hash no longer matches the embedded literal) EXITS NON-ZERO (fail-closed); and
  // (3) the staged command carries NO base64 blob. Then _stageInput's retry/denial policy is pinned via
  // a mocked exec (retry once on a non-denial failure, break early on a denial).
  // ---------------------------------------------------------------------
  {
    const fs = require('fs'); const os = require('os'); const path = require('path')
    const { execFileSync } = require('child_process')
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sr-stage-257-' + process.pid + '-'))
    const runBash = (cmd) => {
      try { execFileSync('bash', ['-c', cmd], { stdio: 'pipe' }); return 0 }
      catch (e) { return (e && typeof e.status === 'number') ? e.status : 1 }
    }
    const DENIAL_PHRASE = 'Permission for this action was denied by the Claude Code auto mode classifier.'
    const payloads = [
      '',
      'plain ascii prompt',
      "it's got 'single' and \"double\" quotes",
      'back\\slashes \\ and a \\n literal and a real\ntab\there',
      'multi\nline\nprompt\nwith trailing\n',
      'café — 日本語 ✓ 🎡 astral',
      'shell metachars: $(rm -rf /) `whoami` ${HOME} | & ; > < # * ?',
      'looks like the stage sig: hashlib.sha256 and import os,sys',
      'contains a denial phrase in the BODY: ' + DENIAL_PHRASE,
      '{"type":"object","properties":{"x":{"type":"string","d":"a\\"b\\\\c"}}}',
      'x'.repeat(5000) + ' — long payload — ' + 'y'.repeat(2000),
    ]
    let n = 0
    for (const payload of payloads) {
      const p = path.join(tmpDir, 'engine-fixture-' + (n++) + '.prompt')
      const cmd = d._stageCmd(p, payload)
      // (1) no opaque blob rides the command — the payload is readable in it (non-empty case).
      assert.ok(!/base64/.test(cmd), '#257: staged command carries no base64: ' + cmd.slice(0, 120))
      if (payload) assert.ok(cmd.includes(payload) || cmd.includes(payload.replace(/'/g, "'\\''")),
        '#257: the readable payload rides in the staged command text')
      // (2) round-trip byte-exact + verify EXITS 0.
      const status = runBash(cmd)
      assert.strictEqual(status, 0, '#257: the plain write+sha256-verify exits 0 for payload #' + (n - 1))
      assert.strictEqual(fs.readFileSync(p, 'utf8'), payload,
        '#257: the staged file round-trips BYTE-EXACT for payload #' + (n - 1))
    }
    console.log('OK: engine_dispatch #257 stage-write round-trips byte-exact across quotes/backslashes/newlines/non-ASCII/metachars')

    // (3) MANGLE FAIL-CLOSED: simulate a courier that paraphrases the readable payload arg but copies the
    // embedded hash verbatim — the on-disk file no longer matches the hash, so the verify EXITS NON-ZERO.
    {
      const p = path.join(tmpDir, 'engine-mangle.prompt')
      const cmd = d._stageCmd(p, 'the original faithful prompt')
      const mangled = cmd.replace("'the original faithful prompt'", "'a MANGLED paraphrase of the prompt'")
      assert.notStrictEqual(mangled, cmd, '#257 precondition: the mangle rewrote the payload arg')
      const status = runBash(mangled)
      assert.notStrictEqual(status, 0, '#257: a payload mangle (hash no longer matches) fails closed with a non-zero verify exit')
    }
    console.log('OK: engine_dispatch #257 a transit mangle fails closed (sha256 verify catches it)')

    fs.rmSync(tmpDir, { recursive: true, force: true })
  }

  // #257: _stageInput retry + denial policy (mocked exec — no real shell). exec-level ok reflects the
  // python verify's exit status, so a non-denial failure retries ONCE (stochastic courier drop / mangle),
  // a persistent failure gives up after 2 attempts, and a DETERMINISTIC classifier denial breaks early.
  {
    const savedAgent = global.agent
    const DENIAL = 'Permission for this action was denied by the Claude Code auto mode classifier.'
    // (a) recovers on the second attempt.
    let calls = 0
    global.agent = async () => { calls += 1; return [{ index: 0, ok: calls > 1, stdout: '' }] }
    const rRecover = await d._stageInput('/tmp/sr-257-a.prompt', 'content')
    assert.strictEqual(rRecover.ok, true, '#257: _stageInput recovers when the retry succeeds')
    assert.strictEqual(calls, 2, '#257: a first-attempt non-denial failure retries exactly once')
    // (b) persistent non-denial failure gives up after two attempts.
    let calls2 = 0
    global.agent = async () => { calls2 += 1; return [{ index: 0, ok: false, stdout: '' }] }
    const rFail = await d._stageInput('/tmp/sr-257-b.prompt', 'content')
    assert.strictEqual(rFail.ok, false, '#257: a persistent staging failure returns ok:false')
    assert.strictEqual(calls2, 2, '#257: it gives up after exactly two attempts (one retry)')
    assert.ok(rFail.results && rFail.results[0] && rFail.results[0].ok === false,
      '#257: the failed leaf results ride back for denial-signature inspection')
    // (c) a deterministic classifier DENIAL breaks early — no wasted retry.
    let calls3 = 0
    global.agent = async () => { calls3 += 1; return [{ index: 0, ok: false, stdout: DENIAL }] }
    const rDenied = await d._stageInput('/tmp/sr-257-c.prompt', 'content')
    assert.strictEqual(rDenied.ok, false, '#257: a denied staging returns ok:false')
    assert.strictEqual(calls3, 1, '#257: a deterministic denial breaks early (retry would only re-deny)')
    global.agent = savedAgent
    console.log('OK: engine_dispatch #257 _stageInput retries a mangle once, gives up on persistent failure, breaks early on a denial')
  }
})()

