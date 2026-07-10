// plugins/superheroes/lib/tests/showrunner_engine_dispatch_realseam_smoke.js
// #341 REAL-SEAM DETECTOR (CONVENTIONS §12.1/§12.2). The a7bade9a escape shipped because EVERY
// engine-dispatch smoke stubs the courier seam — they verify the stub, not the cheap leaf's judgment.
// This detector runs the EXACT production write-role cursor build watchdog command (the real
// _composeDispatchCommand output wrapping the real armed watchdog + real cursor-agent --trust -f argv),
// framed with the REAL production marker courier framing (wrapMarkedCommand + markedPromptFor), through
// a REAL cheapest-model `claude` agent leaf — NOT a fixture-injected courier — and asserts the leaf
// actually RAN the command rather than declining with prose. That is the assertion that would have
// caught the original bug: a safety-trained cheap leaf refusing the autonomous cursor dispatch and
// answering prose, which the old plain exec() collapsed into external-run-failed.
//
// EXECUTION CLASSIFICATION MIRRORS PRODUCTION (#343 — the PR-343 vet's live find). A real leaf's
// answer is STOCHASTIC across runs; three executed shapes and one decline shape were live-observed:
//   (a) marker-carrying verbatim stdout (the common case) — executedMarker (a runtime-expanded
//       __SR_EXIT:<digit>) proves execution; a quoted command can only carry the '$?' literal.
//   (b) executed, but the leaf's harness PERSISTED the huge (30KB+) stream-json output to a
//       tool-results file and the answer was only a file-pointer sentence — NO markers (live-observed
//       2026-07-10 vetting PR #343). Marker absence is NOT proof of non-execution, so — exactly like
//       production's worktree dirty-probe — this detector corroborates with on-disk evidence: the
//       write-role cursor probe leaves files in the scratch worktree that a declined (never-run)
//       command cannot have created.
//   (c) echo of the command text (the '$?' literal) ALONGSIDE real executed output — accepted via the
//       executedMarker tiebreak, exactly as production does (courier_exec.js).
//   (d) a genuine prose DECLINE (no markers, no on-disk evidence) — the #341 bug class. Production
//       retries such a dispatch ONCE; this detector mirrors that (up to 2 attempts) so a single
//       stochastic refusal can't flake the detector while a PERSISTENT decline still fails it.
//
// LIVE-GATED: this dispatches a real `claude -p` subprocess (needs live credentials + the claude CLI),
// so it is a no-op SKIP unless SUPERHEROES_LIVE_COURIER=1 is set. CI leaves it unset (skips cleanly);
// the PR body carries the live round-trip receipt (CONVENTIONS §12.2's "far side unreachable in CI"
// clause). cursor-agent need NOT be installed — if it is absent the watchdog's `exec ... or exit 127`
// still runs and the answer still carries the __SR_EXIT digit marker (path (a)); the question is
// whether the LEAF ran the shell, not whether cursor succeeded.
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
  return { prompt, scratch, wt }
}

function cleanup(scratch) { try { fs.rmSync(scratch, { recursive: true, force: true }) } catch (_) {} }

// On-disk execution corroborator — the detector's twin of production's worktree dirty-probe: the
// cursor write probe creates file(s) in the (initially empty) scratch worktree; a declined (never-run)
// command cannot have. Checked only when the answer carries no marker (shape (b) above).
function worktreeTouched(wt) {
  try { return fs.readdirSync(wt).length > 0 } catch (_) { return false }
}

;(async () => {
  // Compose the production command + prompt even in SKIP mode — a composition failure (e.g. a broken
  // _composeDispatchCommand export) is caught in plain CI, not only under live creds.
  const { prompt, scratch, wt } = composeProductionLeafPrompt()
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
  let verdict = null   // {kind: 'marker'|'on-disk', attempt}
  const answers = []
  // Up to 2 attempts — mirroring production's decline retry-once, so ONE stochastic refusal cannot
  // flake the detector while a PERSISTENT decline (the #341 bug class) still fails it.
  for (let attempt = 1; attempt <= 2 && !verdict; attempt += 1) {
    const res = spawnSync('claude', ['-p', prompt, '--model', model, '--allowedTools', 'Bash',
      '--dangerously-skip-permissions'], { encoding: 'utf8', timeout: 180000, maxBuffer: 8 * 1024 * 1024 })
    if (res.error) {
      // A leaf that TIMED OUT is a transport-level inconclusive attempt (a slow leaf, not a decline) —
      // check the on-disk evidence, then let the loop retry. Only a genuine launch failure (no CLI,
      // no credentials) hard-fails: the detector cannot certify anything without a real leaf.
      if (res.error.code === 'ETIMEDOUT') {
        if (worktreeTouched(wt)) { verdict = { kind: 'on-disk', attempt }; break }
        continue
      }
      cleanup(scratch); console.error('live dispatch failed to launch claude:', res.error); process.exit(1)
    }
    const answer = String(res.stdout || '') + String(res.stderr || '')
    answers.push(answer)
    // (a)/(c): the runtime-expanded digit marker — the PRODUCTION execution predicate (executedMarker;
    // an echoed command can only carry the '$?' literal, never digits).
    if (courier.executedMarker(answer)) { verdict = { kind: 'marker', attempt }; break }
    // (b): no marker, but the write probe touched the worktree — executed, answer dropped the markers
    // (e.g. large-output persistence). Production maps this to external-run-failed WITHOUT retry —
    // never courier-declined — so the leaf-executed-the-command claim this detector certifies holds.
    if (worktreeTouched(wt)) { verdict = { kind: 'on-disk', attempt }; break }
    // (d): genuine decline — retry once, as production does.
  }
  cleanup(scratch)
  assert.ok(verdict,
    '#341: the real cheapest-model leaf PERSISTENTLY DECLINED the production cursor build watchdog ' +
    '(no execution marker, no on-disk evidence, across 2 attempts — the a7bade9a bug class). ' +
    'Last answer was:\n' + String(answers[answers.length - 1] || '').slice(0, 2000))
  console.log('OK: #341 real-seam — a real cheapest-model claude leaf executed the production cursor ' +
    'build watchdog command (proof: ' + verdict.kind + ', attempt ' + verdict.attempt + ' of 2), ' +
    'not a fixture courier')
})().catch((e) => { console.error(e && e.stack || e); process.exit(1) })
