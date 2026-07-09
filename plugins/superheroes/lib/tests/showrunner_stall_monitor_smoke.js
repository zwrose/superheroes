// plugins/superheroes/lib/tests/showrunner_stall_monitor_smoke.js
// #309 STALL MONITOR — the byte-activity watchdog paired with the high dispatch ceiling.
//
// Two layers of coverage:
//   (1) COMMAND-SHAPE (fast, canned courier): the armed dispatch composes the setpgrp + byte-growth
//       watchdog into the run command, clamps the idle window to the ceiling (monitor ≤ ceiling), and
//       journals stallMonitor/idleSeconds; a dispatch with NO idle passed stays ceiling-only (back-compat).
//   (2) REAL SEAM (a fake engine CLI actually run through a real shell): dispatchExternal is REAL — only
//       the courier TRANSPORT is swapped for a real /bin/sh exec, exactly what the courier is in
//       production (an LLM running the one command and returning its stdout). A fake CLI that emits a
//       byte then stalls past a short test-scale idle window must journal outcome:'stalled' with the
//       payload, AND its spawned child must die with it (process-GROUP kill — no orphan). A companion
//       CLI that keeps emitting and exits under the ceiling must journal outcome:'ok'.
const assert = require('assert')
const fs = require('fs')
const os = require('os')
const path = require('path')
const { execSync } = require('child_process')

const logs = []
global.log = (m) => logs.push(m)

// pid-unique scratch dir (test isolation) — fake CLI scripts, child-pid receipts, and the (real) cwd.
const SCRATCH = fs.mkdtempSync(path.join(os.tmpdir(), `stall-smoke-${process.pid}-`))
function cleanup() { try { fs.rmSync(SCRATCH, { recursive: true, force: true }) } catch (_) {} }

// Extract the numbered command list the exec courier prompt carries (see showrunner.js exec()):
// "<preamble>\n\n1. <cmd1>\n2. <cmd2>". Commands may be MULTILINE (the watchdog script) — continuation
// lines (not starting with "N. ") belong to the current command. globalThis.__SR_ROOT is left unset in
// this smoke, so selfContained() is a no-op and each command is verbatim (runnable in a real shell).
function extractCommands(prompt) {
  const body = prompt.slice(prompt.indexOf('\n\n') + 2)
  const cmds = []
  let cur = null
  for (const ln of body.split('\n')) {
    const m = ln.match(/^(\d+)\.\s(.*)$/)
    if (m) { if (cur != null) cmds.push(cur); cur = m[2] }
    else if (cur != null) cur += '\n' + ln
  }
  if (cur != null) cmds.push(cur)
  return cmds
}
function realExec(cmd, index) {
  try {
    const stdout = execSync(cmd, { shell: '/bin/sh', encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], maxBuffer: 4 * 1024 * 1024 })
    return { index, ok: true, stdout }
  } catch (e) {
    return { index, ok: e.status === 0, stdout: e.stdout == null ? '' : String(e.stdout) }
  }
}

const d = require('../engine_dispatch.js')

;(async () => {
  // =====================================================================
  // (1) COMMAND-SHAPE — canned courier, assert the composed command + journal.
  // =====================================================================
  {
    const execLog = []
    global.agent = async (prompt) => {
      execLog.push(prompt)
      if (prompt.includes('engine_adapter.py build-argv')) return [{ index: 0, ok: true, stdout: JSON.stringify(['cursor-agent', '--model', 'x', '-p', '--trust', '--output-format', 'stream-json']) }]
      if (prompt.includes('engine_adapter.py parse-result')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, findings: [] }) }]
      if (prompt.includes('journal_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      // the run command carries the watchdog (idle armed) — return a clean canned stdout (no marker ->
      // treated as a completed run) so the dispatch reaches parse-result.
      return [{ index: 0, ok: true, stdout: '{}' }]
    }
    // Armed: cursor is a streaming engine, idleSeconds passed -> monitor armed, clamped ≤ ceiling.
    await d.dispatchExternal({ engine: 'cursor', roleKind: 'review', effort: 'composer', prompt: 'review',
      cwd: '/tmp/wt', schema: {}, timeoutSeconds: 900, idleSeconds: 300, workItem: 'wi-shape' })
    const runCmd = execLog.find((c) => c.includes('__SR_DISPATCH__') && c.includes(' < '))
    assert.ok(runCmd, 'armed dispatch composes a watchdog run command carrying the __SR_DISPATCH__ control marker')
    assert.ok(/setpgrp\(0,0\); alarm shift @ARGV; exec @ARGV or exit 127/.test(runCmd),
      'armed run wraps the CLI in a process-group-leader perl alarm (setpgrp for group-kill + ceiling): ' + runCmd)
    assert.ok(/kill -TERM -"\$p"/.test(runCmd) && /kill -KILL -"\$p"/.test(runCmd),
      'armed run TERM-then-KILLs the whole process group (negative pid) on idle expiry')
    assert.ok(/wc -c < "\$out"/.test(runCmd), 'armed run polls the captured-output file BYTE size (byte-activity monitor)')
    // ceiling (900) is the perl alarm arg; idle (300) and poll are the sh -c positional args after it.
    assert.ok(/sh -c '.*' sh 900 300 /.test(runCmd.replace(/\n/g, ' ')),
      'armed run threads ceiling=900 then idle=300 as positional args (monitor ≤ ceiling): ' + runCmd)
    const journalCmd = execLog.find((c) => c.includes('journal_entry.py') && c.includes('external_dispatch'))
    const payload = JSON.parse(journalCmd.match(/--payload '(.*)'$/s)[1])
    assert.strictEqual(payload.stallMonitor, 'armed', 'armed dispatch journals stallMonitor:armed')
    assert.strictEqual(payload.idleSeconds, 300, 'armed dispatch journals the idle threshold')
    assert.strictEqual(payload.effectiveTimeout, 900, 'the ceiling is still journalled alongside the monitor')
    console.log('OK: stall monitor armed command shape + journal (setpgrp/group-kill/byte-poll, monitor ≤ ceiling)')
  }

  // Monitor ≤ ceiling: an owner idle override ABOVE the ceiling is clamped down to the ceiling; the
  // ceiling is never disabled (the perl alarm stays inside the wrapper).
  {
    const execLog = []
    global.agent = async (prompt) => {
      execLog.push(prompt)
      if (prompt.includes('engine_adapter.py build-argv')) return [{ index: 0, ok: true, stdout: JSON.stringify(['codex', 'exec', '--sandbox', 'read-only', '-']) }]
      if (prompt.includes('engine_adapter.py parse-result')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, findings: [] }) }]
      if (prompt.includes('journal_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      return [{ index: 0, ok: true, stdout: '{}' }]
    }
    await d.dispatchExternal({ engine: 'codex', roleKind: 'review', effort: 'high', prompt: 'review',
      cwd: '/tmp/wt', schema: {}, timeoutSeconds: 120, idleSeconds: 9999, workItem: 'wi-clamp' })
    const journalCmd = execLog.find((c) => c.includes('journal_entry.py') && c.includes('external_dispatch'))
    const payload = JSON.parse(journalCmd.match(/--payload '(.*)'$/s)[1])
    assert.strictEqual(payload.idleSeconds, 120, 'an idle override above the ceiling is clamped to the ceiling (monitor ≤ ceiling)')
    const runCmd = execLog.find((c) => c.includes('__SR_DISPATCH__') && c.includes(' < '))
    assert.ok(/sh -c '.*' sh 120 120 /.test(runCmd.replace(/\n/g, ' ')), 'the clamped idle rides the run command')
    console.log('OK: stall monitor clamps idle override to the ceiling (both limits always armed)')
  }

  // Back-compat: NO idleSeconds passed -> the leaf stays ceiling-only (unarmed), byte-identical to the
  // pre-#309 perl-alarm command; the probe/legacy caller never gets a watchdog.
  {
    const execLog = []
    global.agent = async (prompt) => {
      execLog.push(prompt)
      if (prompt.includes('engine_adapter.py build-argv')) return [{ index: 0, ok: true, stdout: JSON.stringify(['codex', 'exec', '--sandbox', 'read-only', '-']) }]
      if (prompt.includes('engine_adapter.py parse-result')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, findings: [] }) }]
      if (prompt.includes('journal_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      return [{ index: 0, ok: true, stdout: '{}' }]
    }
    await d.dispatchExternal({ engine: 'codex', roleKind: 'review', effort: 'high', prompt: 'review',
      cwd: '/tmp/wt', schema: {}, timeoutSeconds: 900, workItem: 'wi-unarmed' })
    const runCmd = execLog.find((c) => c.includes('--sandbox') && c.includes(' < '))
    assert.ok(/perl -e 'alarm shift @ARGV; exec @ARGV or exit 127' 900 'codex' 'exec'/.test(runCmd),
      'no idleSeconds -> ceiling-only perl alarm (no watchdog), byte-identical to pre-#309: ' + runCmd)
    assert.ok(!runCmd.includes('__SR_DISPATCH__'), 'the unarmed run carries no watchdog marker')
    const journalCmd = execLog.find((c) => c.includes('journal_entry.py') && c.includes('external_dispatch'))
    const payload = JSON.parse(journalCmd.match(/--payload '(.*)'$/s)[1])
    assert.strictEqual(payload.stallMonitor, 'unarmed', 'an unarmed dispatch journals stallMonitor:unarmed')
    assert.strictEqual(payload.idleSeconds, null, 'an unarmed dispatch journals a null idle threshold')
    console.log('OK: stall monitor back-compat — no idle passed stays ceiling-only (unarmed)')
  }

  // Inert: an engine NOT known to stream when piped (a hypothetical fully-buffering engine) would be
  // FALSE-KILLED by a byte-growth watchdog, so the monitor is left inert (ceiling only) and journalled
  // honestly as "inert (engine buffers)". Exercised with an engine absent from the streaming map even
  // though idleSeconds was passed — the run stays ceiling-only and the journal names it inert.
  {
    const execLog = []
    global.agent = async (prompt) => {
      execLog.push(prompt)
      if (prompt.includes('engine_adapter.py build-argv')) return [{ index: 0, ok: true, stdout: JSON.stringify(['some-buffering-cli', '-']) }]
      if (prompt.includes('engine_adapter.py parse-result')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, findings: [] }) }]
      if (prompt.includes('journal_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      return [{ index: 0, ok: true, stdout: '{}' }]
    }
    await d.dispatchExternal({ engine: 'buffered-engine', roleKind: 'review', effort: 'high', prompt: 'review',
      cwd: '/tmp/wt', schema: {}, timeoutSeconds: 900, idleSeconds: 300, workItem: 'wi-inert' })
    const runCmd = execLog.find((c) => c.includes(' < ') && c.includes('some-buffering-cli'))
    assert.ok(runCmd && !runCmd.includes('__SR_DISPATCH__'),
      'a non-streaming engine gets NO byte-growth watchdog (it would false-kill a buffering CLI): ' + runCmd)
    assert.ok(/perl -e 'alarm shift @ARGV; exec @ARGV or exit 127' 900 /.test(runCmd),
      'the inert path keeps the ceiling armed (perl alarm), just not the monitor')
    const journalCmd = execLog.find((c) => c.includes('journal_entry.py') && c.includes('external_dispatch'))
    const payload = JSON.parse(journalCmd.match(/--payload '(.*)'$/s)[1])
    assert.strictEqual(payload.stallMonitor, 'inert (engine buffers)',
      'a non-streaming engine journals stall_monitor:"inert (engine buffers)" — honest about what is NOT monitored')
    assert.strictEqual(payload.idleSeconds, null, 'the inert path journals a null idle threshold (nothing armed)')
    console.log('OK: stall monitor inert path — non-streaming engine kept ceiling-only + journalled honestly')
  }

  // =====================================================================
  // (2) REAL SEAM — a fake engine CLI actually run through /bin/sh.
  // =====================================================================

  // Shared real-courier stub: journal/build-argv/parse-result are canned; staging (base64) and the run
  // command (the watchdog) are REALLY executed in a shell. Captures journal payloads for assertion.
  function realCourier(fakeArgv, journalSink) {
    return async (prompt) => {
      if (prompt.includes('journal_entry.py')) {
        const m = prompt.match(/--payload '(.*)'\s*$/s)
        if (m) { try { journalSink.push(JSON.parse(m[1])) } catch (_e) { /* ignore */ } }
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      }
      if (prompt.includes('engine_adapter.py build-argv')) return [{ index: 0, ok: true, stdout: JSON.stringify(fakeArgv) }]
      if (prompt.includes('engine_adapter.py parse-result')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, findings: [] }) }]
      // staging (base64 -d > file) and the run command (__SR_DISPATCH__): really run them in a shell.
      const cmds = extractCommands(prompt)
      return cmds.map((c, i) => realExec(c, i))
    }
  }

  // (2a) STALL + PROCESS-GROUP DEATH. The fake CLI spawns a child (sleep 300), records its pid, emits
  // ONE byte, then stalls past the idle window. The watchdog must idle-kill the whole group (child too).
  {
    const wt = fs.mkdtempSync(path.join(SCRATCH, 'cwd-stall-'))
    const childPidFile = path.join(SCRATCH, 'child.pid')
    const fakeCli = path.join(SCRATCH, 'fakecli_stall.sh')
    fs.writeFileSync(fakeCli, [
      '#!/bin/sh',
      'sleep 300 &',              // a child that outlives us UNLESS the whole process group is killed
      'echo $! > ' + JSON.stringify(childPidFile),
      'printf x',                 // one byte of output, then silence (a genuine no-output stall)
      'sleep 30',
      'printf done',
    ].join('\n'))

    const journalSink = []
    global.agent = realCourier(['/bin/sh', fakeCli], journalSink)
    const r = await d.dispatchExternal({ engine: 'codex', roleKind: 'review', effort: 'high',
      prompt: 'go', cwd: wt, schema: {}, timeoutSeconds: 60, idleSeconds: 2, workItem: 'wi-realstall-' + process.pid })

    assert.strictEqual(r.ok, false, 'a stalled dispatch fails (falls open)')
    assert.strictEqual(r.reason, 'stalled', 'the idle-kill reason is stalled (distinct from timeout/failure)')
    const stalledJournal = journalSink.find((p) => p.outcome === 'stalled')
    assert.ok(stalledJournal, 'exactly one external_dispatch line journals outcome:stalled')
    assert.strictEqual(stalledJournal.stallMonitor, 'armed', 'the stalled journal records the armed monitor')
    assert.strictEqual(stalledJournal.idleSeconds, 2, 'the stalled journal records the idle threshold it was killed at')
    assert.strictEqual(stalledJournal.effectiveTimeout, 60, 'the stalled journal still records the (un-hit) ceiling')

    // process-GROUP death: the spawned child must be dead (no orphan). Poll briefly — KILL was already
    // sent inside the watchdog, so the child (reparented to init) is reaped within moments.
    const childPid = parseInt(fs.readFileSync(childPidFile, 'utf8').trim(), 10)
    assert.ok(childPid > 0, 'the fake CLI recorded its child pid')
    let dead = false
    for (let i = 0; i < 40 && !dead; i++) {
      try { process.kill(childPid, 0) } catch (e) { if (e.code === 'ESRCH') dead = true }
      if (!dead) { execSync('sleep 0.1') }
    }
    assert.ok(dead, `the fake CLI's child (pid ${childPid}) must be killed with the group — no orphan`)
    console.log('OK: real-seam STALL — outcome:stalled journalled + process-group death (child reaped, no orphan)')
  }

  // (2b) COMPANION — the CLI keeps emitting and finishes under the ceiling -> outcome:ok (the watchdog
  // never trips because byte growth keeps resetting the idle timer).
  {
    const wt = fs.mkdtempSync(path.join(SCRATCH, 'cwd-ok-'))
    const fakeCli = path.join(SCRATCH, 'fakecli_ok.sh')
    fs.writeFileSync(fakeCli, [
      '#!/bin/sh',
      'i=0',
      'while [ $i -lt 5 ]; do printf "chunk%s" "$i"; sleep 1; i=$((i+1)); done',
      'printf DONE',
    ].join('\n'))

    const journalSink = []
    global.agent = realCourier(['/bin/sh', fakeCli], journalSink)
    // idle window (4) comfortably above the 1s emit cadence -> no false kill; ceiling 60.
    const r = await d.dispatchExternal({ engine: 'codex', roleKind: 'review', effort: 'high',
      prompt: 'go', cwd: wt, schema: {}, timeoutSeconds: 60, idleSeconds: 4, workItem: 'wi-realok-' + process.pid })

    assert.ok(r && Array.isArray(r.findings), 'a steadily-emitting CLI under the ceiling completes normally (read role -> findings)')
    const okJournal = journalSink.find((p) => p.outcome === 'ok')
    assert.ok(okJournal, 'a completed run journals outcome:ok')
    assert.strictEqual(okJournal.stallMonitor, 'armed', 'the ok run still had the monitor armed (it just never tripped)')
    assert.strictEqual(okJournal.idleSeconds, 4, 'the ok run journals its idle threshold')
    assert.ok(!journalSink.some((p) => p.outcome === 'stalled'), 'a steadily-emitting CLI is NEVER stall-killed (no false kill)')
    console.log('OK: real-seam OK — steadily-emitting CLI under the ceiling is never false-killed')
  }

  cleanup()
  console.log('OK: stall monitor smoke complete')
})().catch((e) => { cleanup(); console.error(e && e.stack || e); process.exit(1) })
