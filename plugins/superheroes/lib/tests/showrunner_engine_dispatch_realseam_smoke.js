// plugins/superheroes/lib/tests/showrunner_engine_dispatch_realseam_smoke.js
// #341 REAL-SEAM DETECTOR (CONVENTIONS §12.1/§12.2). The a7bade9a escape shipped because EVERY
// engine-dispatch smoke stubs the courier seam — they verify the stub, not the cheap leaf's judgment.
// This detector runs the EXACT production write-role cursor build watchdog command (the real
// _composeDispatchCommand output wrapping the real armed watchdog + real cursor-agent --trust -f argv),
// framed with the REAL production marker courier framing (wrapMarkedCommand + markedPromptFor), through
// a REAL cheapest-model `claude` agent leaf — NOT a fixture-injected courier — and asserts the leaf
// actually RAN the command (its answer carries the __SR_EXIT execution marker) rather than declining
// with prose. That single assertion is the one that would have caught the original bug: a safety-trained
// cheap leaf refusing the autonomous cursor dispatch and answering prose, which the old plain exec()
// collapsed into external-run-failed.
//
// LIVE-GATED: this dispatches a real `claude -p` subprocess (needs live credentials + the claude CLI),
// so it is a no-op SKIP unless SUPERHEROES_LIVE_COURIER=1 is set. CI leaves it unset (skips cleanly);
// the PR body carries the live round-trip receipt (CONVENTIONS §12.2's "far side unreachable in CI"
// clause). cursor-agent need NOT be installed — if it is absent the watchdog's `exec ... or exit 127`
// still runs, and the leaf's answer still carries the __SR_EXIT marker, which is all this asserts (the
// question is whether the LEAF ran the shell, not whether cursor succeeded).
'use strict'
const assert = require('assert')
const fs = require('fs')
const os = require('os')
const path = require('path')
const { spawnSync } = require('child_process')

const d = require('../engine_dispatch.js')
const courier = require('../courier_exec.js')
const { DEFAULT_TIERS } = require('../model_tier.js')

// The EXACT write-role cursor build argv the adapter emits under the owner's composer policy — the
// autonomous `--trust -f` stream-json dispatch a cheap safety-trained leaf reads as suspicious.
const CURSOR_WRITE_ARGV = ['cursor-agent', '--model', 'composer-2.5-fast', '-p', '--trust', '-f',
  '--output-format', 'stream-json']

function composeProductionLeafPrompt() {
  // pid-unique scratch (repo shared-machine-global-state convention).
  const scratch = fs.mkdtempSync(path.join(os.tmpdir(), `realseam-${process.pid}-`))
  const wt = fs.mkdtempSync(path.join(scratch, 'wt-'))
  const promptPath = path.join(scratch, 'engine-cursor-build.prompt')
  fs.writeFileSync(promptPath, 'Add a one-line comment to a file. This is a bounded acceptance probe.\n')
  // Small ceiling/idle so that IF cursor-agent happens to be installed, the watchdog bounds the real
  // run to seconds — the command SHAPE (setpgrp watchdog + cursor-agent --trust -f) is what trips the
  // refusal, not the exact seconds. armIdle=true -> the production #309 armed watchdog path.
  const cmd = d._composeDispatchCommand(CURSOR_WRITE_ARGV, promptPath, wt, 20, 6, true)
  // Frame it EXACTLY as the hardened courier does: the __SR_EXIT marker wrap + the markedPromptFor lead.
  const prompt = courier.markedPromptFor(courier.wrapMarkedCommand(cmd))
  return { prompt, scratch }
}

function cleanup(scratch) { try { fs.rmSync(scratch, { recursive: true, force: true }) } catch (_) {} }

;(async () => {
  // Compose the production command + prompt even in SKIP mode — a composition failure (e.g. a broken
  // _composeDispatchCommand export) is caught in plain CI, not only under live creds.
  const { prompt, scratch } = composeProductionLeafPrompt()
  assert.ok(/setpgrp\(0,0\); alarm shift @ARGV; exec @ARGV or exit 127/.test(prompt),
    'the composed leaf prompt carries the real production armed watchdog (setpgrp + perl alarm)')
  assert.ok(/cursor-agent.*--trust.*-f/.test(prompt.replace(/\n/g, ' ')),
    'the composed leaf prompt carries the real autonomous cursor write argv (--trust -f)')
  assert.ok(/__SR_EXIT:\$\?/.test(prompt) && /Execute this exact shell command/.test(prompt),
    'the composed leaf prompt uses the real hardened marker courier framing')

  if (process.env.SUPERHEROES_LIVE_COURIER !== '1') {
    cleanup(scratch)
    console.log('SKIP: #341 real-seam detector (set SUPERHEROES_LIVE_COURIER=1 to dispatch a real ' +
      'cheapest-model claude leaf; PR body carries the live receipt)')
    return
  }

  const model = DEFAULT_TIERS.mechanical   // the cheapest model — the tier that stochastically refuses
  const res = spawnSync('claude', ['-p', prompt, '--model', model, '--allowedTools', 'Bash',
    '--dangerously-skip-permissions'], { encoding: 'utf8', timeout: 120000, maxBuffer: 8 * 1024 * 1024 })
  cleanup(scratch)
  if (res.error) { console.error('live dispatch failed to launch claude:', res.error); process.exit(1) }
  const answer = String(res.stdout || '') + String(res.stderr || '')
  // The load-bearing assertion must be AT LEAST as strong as the PRODUCTION execution predicate — a
  // weaker `answer.includes('__SR_EXIT')` would FALSE-PASS on a decline-by-quoting, since the composed
  // prompt itself contains the literal '__SR_EXIT:$?' a leaf can echo without ever running (the
  // wf_1494a8fa-e28 shape badCourierAnswer exists to catch; review finding test-001). So:
  //   (1) reuse the PRODUCTION predicate: !badCourierAnswer rejects both a missing marker AND the
  //       unexpanded '__SR_EXIT:$?' of an echoed/quoted command; AND
  //   (2) require the watchdog's own runtime-EXPANDED control line __SR_DISPATCH__{"idleKilled":N,…},
  //       which only the actually-executed `printf` emits (the quoted command carries the %s format
  //       string, never expanded digits) — bulletproof that the shell RAN, not a quoted-command echo.
  assert.ok(!courier.badCourierAnswer(answer),
    '#341: the real cheapest-model leaf produced a marker-shape (executed) answer, not a decline — ' +
    'badCourierAnswer must be false. Answer was:\n' + answer.slice(0, 2000))
  assert.ok(/__SR_DISPATCH__\{"idleKilled":\d/.test(answer),
    '#341: the real leaf RAN the composed cursor build watchdog — its answer carries the runtime-' +
    'expanded __SR_DISPATCH__ control line (digits, not the %s format string). Answer was:\n' + answer.slice(0, 2000))
  console.log('OK: #341 real-seam — a real cheapest-model claude leaf executed the production cursor ' +
    'build watchdog command (badCourierAnswer=false + expanded __SR_DISPATCH__), not a fixture courier')
})().catch((e) => { console.error(e && e.stack || e); process.exit(1) })
