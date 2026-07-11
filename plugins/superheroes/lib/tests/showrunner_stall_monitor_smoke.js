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
const { markedStdout } = require('./_marked_stdout.js')

const logs = []
global.log = (m) => logs.push(m)
// #341: the CLI run rides the hardened marker courier (markedPromptFor + __SR_EXIT). A stubbed run
// leaf returns a MARKER-carrying answer; the real-seam courier really runs the marked command (whose
// wrapMarkedCommand tail emits __SR_EXIT naturally). Non-run exec leaves keep their bare-array shape.

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
      // the run command rides the hardened marker courier — return a MARKER-carrying canned stdout so
      // the dispatch reads it as a completed run (no __SR_DISPATCH__ -> no idle-kill) and reaches parse-result.
      if (prompt.includes('Execute this exact shell command')) return markedStdout('{}')
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
      if (prompt.includes('Execute this exact shell command')) return markedStdout('{}')
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
      if (prompt.includes('Execute this exact shell command')) return markedStdout('{}')
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
      if (prompt.includes('Execute this exact shell command')) return markedStdout('{}')
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
      // #341: the run command now rides the hardened marker courier (markedPromptFor: "Execute this
      // exact shell command…\n\n<cmd>"). The command follows the blank line; wrapMarkedCommand already
      // appended `2>&1; echo __SR_EXIT:$?`, so REALLY running it in a shell yields the __SR_EXIT marker
      // (proving execution) alongside the watchdog's __SR_DISPATCH__ line — exactly the production seam.
      if (prompt.includes('Execute this exact shell command')) {
        const runCmd = prompt.slice(prompt.indexOf('\n\n') + 2)
        return realExec(runCmd, 0).stdout
      }
      // staging (base64 -d > file): the plain exec() dumb-pipe (numbered list) — really run it in a shell.
      const cmds = extractCommands(prompt)
      return cmds.map((c, i) => realExec(c, i))
    }
  }

  // (2a) STALL + PROCESS-GROUP DEATH. The fake CLI spawns a child (sleep 60), records its pid, emits
  // ONE byte, then stalls past the idle window. The watchdog must idle-kill the whole group (child too).
  // (The child sleeps 60, not longer: if group-kill ever regresses, the orphan assert below still fails
  // fast and the leaked child self-reaps in a minute instead of squatting for five.)
  {
    const wt = fs.mkdtempSync(path.join(SCRATCH, 'cwd-stall-'))
    const childPidFile = path.join(SCRATCH, 'child.pid')
    const fakeCli = path.join(SCRATCH, 'fakecli_stall.sh')
    fs.writeFileSync(fakeCli, [
      '#!/bin/sh',
      'sleep 60 &',               // a child that outlives us UNLESS the whole process group is killed
      'echo $! > ' + JSON.stringify(childPidFile),
      'echo DIAG-ON-STDERR >&2',  // the diagnostic a real wedged CLI leaves — must survive the kill
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

    // Post-mortem detectability (round-2 premortem finding): the engine's stderr diagnostic survives a
    // stall-kill on disk (the $$-suffixed .err capture is kept on failure, removed only on success).
    const errFiles = fs.readdirSync('/tmp').filter((n) =>
      n.startsWith(`engine-codex-review-wi-realstall-${process.pid}.run.`) && n.endsWith('.err'))
    assert.ok(errFiles.length >= 1, 'a stall-killed dispatch keeps its stderr capture on disk for post-mortem')
    const errContent = fs.readFileSync(path.join('/tmp', errFiles[0]), 'utf8')
    assert.ok(errContent.includes('DIAG-ON-STDERR'),
      'the surviving stderr capture carries the engine diagnostic: ' + JSON.stringify(errContent))
    for (const n of errFiles) { try { fs.unlinkSync(path.join('/tmp', n)) } catch (_) {} }
    // #349 retention keeps the stdout capture too — clean this test's own /tmp files
    for (const n of fs.readdirSync('/tmp').filter((x) =>
      x.startsWith(`engine-codex-review-wi-realstall-${process.pid}.run.`))) {
      try { fs.unlinkSync(path.join('/tmp', n)) } catch (_) {}
    }
    console.log('OK: real-seam STALL — outcome:stalled journalled, group death (no orphan), stderr kept for post-mortem')
  }

  // (2b) COMPANION — the CLI keeps emitting and finishes under the ceiling -> outcome:ok (the watchdog
  // never trips because byte growth keeps resetting the idle timer). The CLI also ECHOES ITS STDIN
  // first: a POSIX-sh background job's stdin is /dev/null unless explicitly redirected, so this proves
  // the armed path really delivers the staged prompt to the engine (review finding code-001 — the
  // exact silent-empty-prompt regression this smoke previously could not see).
  {
    const wt = fs.mkdtempSync(path.join(SCRATCH, 'cwd-ok-'))
    const fakeCli = path.join(SCRATCH, 'fakecli_ok.sh')
    fs.writeFileSync(fakeCli, [
      '#!/bin/sh',
      'printf "PROMPT[%s]" "$(cat)"',   // echo stdin back — proves prompt delivery through the armed path
      'echo SPINNER >&2',               // stderr noise — must NEVER reach parse-result (code-002 mutation kill)
      'i=0',
      'while [ $i -lt 5 ]; do printf "chunk%s" "$i"; sleep 1; i=$((i+1)); done',
      'printf DONE',
    ].join('\n'))

    const journalSink = []
    let stagedParseInput = null   // the rawStdout dispatch staged for parse-result (base64 decoded here)
    const courier = realCourier(['/bin/sh', fakeCli], journalSink)
    global.agent = async (prompt) => {
      if (prompt.includes('engine_adapter.py parse-result')) {
        const m = prompt.match(/--stdout-path '([^']+)'/)
        if (m) { try { stagedParseInput = fs.readFileSync(m[1], 'utf8') } catch (_e) { /* asserted below */ } }
      }
      return courier(prompt)
    }
    // idle window (8) is 8x the 1s emit cadence -> no false kill even under heavy CI load; ceiling 60.
    const r = await d.dispatchExternal({ engine: 'codex', roleKind: 'review', effort: 'high',
      prompt: 'the-staged-prompt', cwd: wt, schema: {}, timeoutSeconds: 60, idleSeconds: 8, workItem: 'wi-realok-' + process.pid })

    assert.ok(r && Array.isArray(r.findings), 'a steadily-emitting CLI under the ceiling completes normally (read role -> findings)')
    const okJournal = journalSink.find((p) => p.outcome === 'ok')
    assert.ok(okJournal, 'a completed run journals outcome:ok')
    assert.strictEqual(okJournal.stallMonitor, 'armed', 'the ok run still had the monitor armed (it just never tripped)')
    assert.strictEqual(okJournal.idleSeconds, 8, 'the ok run journals its idle threshold')
    // #347: a small (fully-relayed) dispatch journals NO relay keys — pre-#347 payloads byte-identical
    assert.ok(!('outputTruncated' in okJournal) && !('outPath' in okJournal),
      'an untruncated dispatch journals no #347 relay keys: ' + JSON.stringify(okJournal))
    // #349 retention keeps this test's stdout capture too — clean it up
    for (const n of fs.readdirSync('/tmp').filter((x) =>
      x.startsWith(`engine-codex-review-wi-realok-${process.pid}.run.`))) {
      try { fs.unlinkSync(path.join('/tmp', n)) } catch (_) {}
    }
    assert.ok(!journalSink.some((p) => p.outcome === 'stalled'), 'a steadily-emitting CLI is NEVER stall-killed (no false kill)')
    // code-001: the engine really received the staged prompt on stdin (the armed background job would
    // otherwise read /dev/null and this capture would be PROMPT[]).
    assert.ok(stagedParseInput != null, 'parse-result received a staged stdout file')
    assert.ok(stagedParseInput.includes('PROMPT[the-staged-prompt]'),
      'code-001: the armed CLI received the staged prompt on stdin (not an empty /dev/null): ' + JSON.stringify(stagedParseInput))
    // marker-strip: what reaches parse-result is the CLI output ONLY — the __SR_DISPATCH__ control line
    // was stripped in JS, and stderr was captured separately (never fed to the parser).
    assert.ok(stagedParseInput.includes('chunk4') && stagedParseInput.includes('DONE'),
      'the full CLI stdout reaches parse-result')
    assert.ok(!stagedParseInput.includes('__SR_DISPATCH__'),
      'the watchdog control marker is stripped before parse-result ever sees the output')
    // code-002 mutation kill: the fake CLI wrote SPINNER to stderr — a 2>&1 revert (merging stderr back
    // into the parse input) fails HERE, not silently.
    assert.ok(!stagedParseInput.includes('SPINNER'),
      'code-002: engine stderr is captured separately and never reaches parse-result')
    console.log('OK: real-seam OK — prompt delivered on stdin, no false kill, marker stripped, stderr never parsed')
  }

  // (2c) #347/#349 FLOOD — a fake CLI floods well past EMIT_TAIL_BYTES of stream-json noise and
  // ends with the REAL cursor result envelope (findings JSON escaped INSIDE the envelope's `result`
  // string). The watchdog must relay only the stdout TAIL to the leaf (the persist-wall bound,
  // #347), but the REAL parser (engine_adapter.py, actually executed) must read the on-disk capture
  // DIRECTLY — the COMPLETE stream, never a courier-retyped copy (#349: a leaf re-typing the ~31KB
  // base64 re-stage live-corrupted every large payload) — unwrap the envelope, and the journal must
  // disclose the truncated relay.
  {
    const wt = fs.mkdtempSync(path.join(SCRATCH, 'cwd-flood-'))
    const payloadFile = path.join(SCRATCH, 'flood_payload.jsonl')
    const findings = [{ severity: 'Important', title: 'envelope-finding', file: 'a.py', line: 3,
      body: 'b', suggestion: 's' }]
    const innerText = 'Reviewed.\n```json\n' + JSON.stringify({ findings }) + '\n```\nDone.'
    const envelope = JSON.stringify({ type: 'result', subtype: 'success', is_error: false,
      duration_ms: 1, session_id: 'smoke', result: innerText })
    const noise = []
    for (let i = 0; i < 700; i++) noise.push(JSON.stringify({ type: 'thinking', text: 'noise-' + i + '-' + 'x'.repeat(40) }))
    fs.writeFileSync(payloadFile, noise.join('\n') + '\n' + envelope + '\n')   // ~45KB >> the cap
    assert.ok(fs.statSync(payloadFile).size > 2 * d.EMIT_TAIL_BYTES, 'the flood really exceeds the cap')
    const fakeCli = path.join(SCRATCH, 'fakecli_flood.sh')
    fs.writeFileSync(fakeCli, '#!/bin/sh\ncat ' + JSON.stringify(payloadFile) + '\n')

    const journalSink = []
    let parsePath = null, parseInput = null, courierAnswerBytes = null
    const restageCmds = []   // any courier command that re-stages engine stdout (must stay empty, #349)
    const courier = realCourier(['/bin/sh', fakeCli], journalSink)
    global.agent = async (prompt) => {
      // parse-result runs FOR REAL here — the envelope unwrap under test is the actual python parser.
      if (prompt.includes('engine_adapter.py parse-result')) {
        const m = prompt.match(/--stdout-path '([^']+)'/)
        if (m) { parsePath = m[1]; try { parseInput = fs.readFileSync(m[1], 'utf8') } catch (_e) { /* asserted below */ } }
        return extractCommands(prompt).map((c, i) => realExec(c, i))
      }
      // #349 corruption-vector guard: engine STDOUT must never be re-staged through a courier
      // (prompt/schema INPUT staging is ours and small — only the rawPath re-stage is the hazard).
      if (/base64 -d > '\/tmp\/engine-[^']*\.out'/.test(prompt)) restageCmds.push(prompt.slice(0, 120))
      if (prompt.includes('Execute this exact shell command')) {
        const answer = await courier(prompt)
        courierAnswerBytes = String(answer).length
        return answer
      }
      return courier(prompt)
    }
    const r = await d.dispatchExternal({ engine: 'cursor', roleKind: 'review', effort: 'composer',
      prompt: 'go', cwd: wt, schema: {}, timeoutSeconds: 60, idleSeconds: 8, workItem: 'wi-flood-' + process.pid })

    assert.ok(r && Array.isArray(r.findings),
      'a flooding CLI still completes: bounded relay + direct capture parse: ' + JSON.stringify(r))
    assert.strictEqual(r.findings[0].title, 'envelope-finding',
      'the findings were recovered from INSIDE the stream envelope by the real parser')
    // #347: what the LEAF relayed stays bounded (the persist-wall bound)…
    assert.ok(courierAnswerBytes != null && courierAnswerBytes <= d.EMIT_TAIL_BYTES + 400,
      'the courier ANSWER is bounded (never the full stream): ' + courierAnswerBytes)
    // …but #349: what the PARSER read is the on-disk capture — COMPLETE (head AND tail), unretyped.
    assert.ok(parsePath && parsePath.includes('.run.'),
      'parse-result reads the shell-written capture directly: ' + parsePath)
    assert.ok(parseInput != null && parseInput.includes('noise-0-') && parseInput.includes('envelope-finding'),
      'the parser saw the COMPLETE stream from disk (head and tail)')
    assert.strictEqual(restageCmds.length, 0,
      'engine stdout is NEVER re-staged through a courier (the #349 corruption vector): ' + restageCmds[0])
    // disclosure: the ok journal line names the truncated RELAY + the capture receipt
    const okJournal = journalSink.find((p) => p.outcome === 'ok')
    assert.ok(okJournal && okJournal.outputTruncated === true,
      'the ok journal discloses the bounded relay: ' + JSON.stringify(okJournal))
    assert.ok(Number(okJournal.outBytes) > d.EMIT_TAIL_BYTES, 'outBytes names the true capture size')
    assert.ok(fs.existsSync(okJournal.outPath), 'the capture file is kept on disk')
    try { fs.unlinkSync(okJournal.outPath) } catch (_) {}
    console.log('OK: real-seam FLOOD — bounded leaf relay, parser read the COMPLETE capture from disk (no courier re-stage), truncation disclosed')
  }

  // Drift guard (architecture-001): every dispatchable external engine must carry an explicit
  // streams-when-piped verdict — adding an engine to engine_pref.ENGINES without deciding its
  // buffering behavior would silently run it monitor-inert. 'claude' never dispatches externally.
  {
    const EP = require('../engine_pref.js')
    for (const eng of EP.ENGINES) {
      if (eng === 'claude') continue
      assert.ok(Object.prototype.hasOwnProperty.call(d._STREAMS_WHEN_PIPED, eng) &&
        typeof d._STREAMS_WHEN_PIPED[eng] === 'boolean',
        `drift guard: engine '${eng}' needs an explicit _STREAMS_WHEN_PIPED verdict (verify its piped-output behavior, see the receipts note)`)
    }
    console.log('OK: every external engine carries an explicit streams-when-piped verdict (no silent inert drift)')
  }

  cleanup()
  console.log('OK: stall monitor smoke complete')
})().catch((e) => { cleanup(); console.error(e && e.stack || e); process.exit(1) })
