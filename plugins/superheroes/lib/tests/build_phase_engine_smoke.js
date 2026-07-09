require('./_smoke_checkout_root.js')
// plugins/superheroes/lib/tests/build_phase_engine_smoke.js
// #38 Task 11: build_phase.js's worker (buildOneTask), fixer (reviewLoop), and final-review
// reviewer/final-fixer route to engine_dispatch.dispatchExternal when the implementation/reviewer
// engine is external (globalThis.__SR_ENGINE_PREFS). The Claude path (prefs absent) is byte-unchanged
// (build_phase_loop_smoke.js / build_phase_final_review_smoke.js already pin that). This smoke pins:
//   - build-then-verify on an external implementation engine (worker routes to dispatchExternal, the
//     native 'worker' agent() never fires, and the verify-gate + trailer-gather run unchanged).
//   - the UFR-4 write preflight (engine_authz.py test-dispatch) runs exactly once per run (cached).
//   - the fail-closed trio: a failed external dispatch -> resetUncommitted fired -> native worker falls
//     open; the verify-gate/reviewPanel path is untouched; mixed reviewer!=impl engines split correctly
//     (FR-15).
//   - UFR-4 preflight DENIED -> the impl role falls fully open to Claude for the whole run (never
//     dispatches externally for a write role), using the require.cache-reset idiom (mirrors
//     showrunner_cmdrunner_cwd_smoke.js) so the module-level _writeAuthOk cache does not leak across
//     scenarios in this single process.
//   - FIX I5: the final-fixer's fixStep closure ALWAYS returns the {fixed,deferred} report shape (never
//     _implDispatch's raw {ok,...} result / undefined), so review_panel_shell.runFixStep does not treat
//     a successful external fix as a fix-failure.
//   - the commit-discipline multi-round fold invariant: two external fix rounds dispatch TWICE with the
//     SAME taskId.
'use strict'
const assert = require('assert')
const fs = require('fs'); const os = require('os'); const path = require('path')
const { routeMatches } = require('./_task_leaf_route.js')
// pid-unique final-review runDir + reason-bearing terminal assertions (see
// _final_review_probe.js; must load before build_phase.js binds reviewPanel).
const { uniqueWorkItem, resetRunDir, assertTerminal } = require('./_final_review_probe.js')

global.log = () => {}
global.parallel = async (thunks) => Promise.all((thunks || []).map((t) => t()))

// Route an agent() call by exact label first (labels are unique), then a prompt-substring fallback.
function makeAgent(routes) {
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    for (const [needle, resp] of routes) if (routeMatches(label, needle)) return typeof resp === 'function' ? resp(prompt, opts) : resp
    // #150: per-task reviewer labels are "review task <id>:rN" — scenarios route it as 'review'.
    if (/^review task .+:r\d+$/.test(label)) {
      for (const [needle, resp] of routes) if (needle === 'review') return typeof resp === 'function' ? resp(prompt, opts) : resp
    }
    if (label === 'read verify + minors') return JSON.stringify({ ok: true, verify_command: 'pytest -q', minors: [] })
    // #118 fold: a dumb-pipe leaf (record/gather/stamp + the descriptively-labelled exec helpers like
    // 'read gate'/'fence lease') carries opts.courier and one command — route it by that command. A
    // dedicated script route (needle containing '.py', e.g. 'verify_gate.py' for the 'run verify' leaf)
    // wins; otherwise it feeds the scenario's generic exec map. Handled BEFORE the substring loop so a
    // generic English needle ('review') never mis-grabs a courier command ('record-reviewed').
    if (opts && opts.courier) {
      const cmd = prompt.split('\n\n').slice(1).join('\n\n')
      for (const [needle, resp] of routes) if (needle !== 'exec' && needle.includes('.py') && cmd.includes(needle)) return typeof resp === 'function' ? resp(cmd, opts) : resp
      for (const [needle, resp] of routes) if (needle === 'exec' && typeof resp === 'function') return resp(cmd, opts)
    }
    for (const [needle, resp] of routes) if (prompt.includes(needle)) return typeof resp === 'function' ? resp(prompt, opts) : resp
    return ''
  }
}

// execRoute(map): a single 'exec' route. `map(prompt)` -> raw stdout STRING for the listed command.
function execRoute(map) {
  return ['exec', (prompt) => [{ index: 0, ok: true, stdout: map(prompt) }]]
}

// runFinalReview derives its runDir INTERNALLY from workItem (a fixed `/tmp/workhorse-<wi>-final-
// review` path, not the caller-supplied wt) — every scenario below that calls runFinalReview(WI, ...)
// shares that SAME on-disk directory. reviewPanel persists a durable round-records.json accumulator
// there (+ recordDeferred writes deferred-set.json), so a stale accumulator from an EARLIER scenario
// would corrupt a later scenario's round-1 state. Reset it (resetRunDir) before every
// runFinalReview(WI, ...) call for hermetic, run-order-independent scenarios; WI is pid-unique so a
// concurrently running second suite on the same machine can never clobber this process's runDir
// mid-panel (_final_review_probe.js has the 2026-07-06 flake story).
const WI = uniqueWorkItem()

function verifyGateStub(cmd, result = 'pass') {
  const m = String(cmd || '').match(/--out '([^']+)'/)
  const payload = result === 'pass' ? { result: 'pass', code: 0, tail: '' }
    : result === 'timeout' ? { result: 'timeout', code: null, tail: '' }
    : { result: 'fail', code: 1, tail: '' }
  if (m) fs.writeFileSync(m[1], JSON.stringify(payload))
  return { command: 'pytest -q', returncode: result === 'pass' ? 0 : 1, timedOut: result === 'timeout' }
}

// standardLeaf: the stdout for the common IO leaves on a clean build-then-verify run. `authzOk`
// controls the UFR-4 engine_authz.py test-dispatch preflight verdict; `authzCalls` counts it (cached
// per run -> must fire exactly once even across multiple dispatches in the same process instance).
function standardLeaf(p, { authzOk = true, authzCalls = null, provOk = true } = {}) {
  if (p.includes('read-gate')) return '{"review": "passed"}'
  if (p.includes('build_entry.py')) return JSON.stringify({ branch: 'superheroes/wi-abc', path: '/tmp/wt' })
  if (p.includes('engine_authz.py test-dispatch')) {
    if (authzCalls) authzCalls.n += 1
    const m = p.match(/--engine (\S+)/)
    return JSON.stringify({ engine: m ? m[1].replace(/^'|'$/g, '') : 'codex', ok: authzOk })
  }
  if (p.includes('build_state_cli.py gather')) return JSON.stringify({ unmapped_commits: 0 })
  if (p.includes('fence_cli.py')) return JSON.stringify({ ok: true })
  if (p.includes('journal_entry.py')) return JSON.stringify({ ok: true })
  if (p.includes('record-built')) return JSON.stringify({ ok: true, read_back: true, task: '1' })
  if (p.includes('record-reviewed')) return JSON.stringify({ ok: true, read_back: true, task: '1' })
  if (p.includes('record-final-review')) return JSON.stringify({ ok: true, read_back: true })
  if (p.includes('minor_rollup_cli.py')) return JSON.stringify({ minors: [] })
  if (p.includes('verify_command_cli.py')) return JSON.stringify({ command: 'pytest -q' })
  if (p.includes('prov_entry.py')) return provOk ? JSON.stringify({ ok: true }) : JSON.stringify({ ok: false, error: 'disk' })
  return '{}'
}

;(async () => {
  // ===========================================================================
  // Scenario 1: build-then-verify on an external implementation engine (Codex).
  // ===========================================================================
  {
    globalThis.__SR_ENGINE_PREFS = { reviewer: 'claude', implementation: 'codex', effort: {} }
    const dispatchCalls = []
    const authzCalls = { n: 0 }
    const engineDispatch = require('../engine_dispatch.js')
    engineDispatch.dispatchExternal = async (o) => {
      dispatchCalls.push(o)
      return { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } }
    }
    let workerFired = 0
    global.agent = makeAgent([
      execRoute((p) => standardLeaf(p, { authzCalls })),
      ['implement-task', () => { workerFired += 1; return { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } } }],
      ['review', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }],
    ])
    const bp = require('../build_phase.js')
    const r = await bp.buildOneTask('wi', 5, { id: '1', title: 'One' }, 'br', '1', '/tmp/wt', 1)
    assert.strictEqual(r.parked, false, 'a clean external build+review completes (not parked)')
    assert.strictEqual(workerFired, 0, 'the native worker agent() must NOT fire when the impl engine is external')
    const buildCall = dispatchCalls.find((o) => o.roleKind === 'build')
    assert.ok(buildCall, 'dispatchExternal was called for the build role')
    assert.strictEqual(buildCall.engine, 'codex', 'build dispatch uses the configured implementation engine')
    assert.strictEqual(buildCall.cwd, '/tmp/wt', 'build dispatch cwd is the build worktree')
    assert.strictEqual(buildCall.taskId, '1', 'build dispatch carries the task id')
    // #308: the build dispatch threads the SAME builder tier the native path + readout resolve (opus),
    // never the composer default the cursor build silently ran before. #309: the build role carries the
    // HIGH write ceiling (resolveTimeout(prefs,'build')=2400), never the 300s wall-clock kill. Both
    // computed via the REAL twins (no monkeypatched resolveModel/resolveTimeout).
    const modelTierS1 = require('../model_tier.js')
    const enginePrefS1 = require('../engine_pref.js')
    assert.strictEqual(buildCall.model, modelTierS1.resolveModel('builder', null, null),
      '#308: the build dispatch carries the resolved builder tier (opus)')
    assert.strictEqual(buildCall.timeoutSeconds, enginePrefS1.resolveTimeout(globalThis.__SR_ENGINE_PREFS, 'build'),
      '#309: the build dispatch carries the high write ceiling from the REAL resolveTimeout')
    assert.strictEqual(buildCall.timeoutSeconds, 2400, '#309: the write ceiling is 2400s (owner HIGH-ceiling policy)')
    // the verify-gate + trailer-gather ran unchanged: build_state_cli.py gather fired.
    let gatherFired = false
    global.agent = makeAgent([
      execRoute((p) => { if (p.includes('build_state_cli.py gather')) gatherFired = true; return standardLeaf(p, { authzCalls }) }),
      ['implement-task', () => { workerFired += 1; return { ok: true, signal: 'ok', evidence: {} } }],
      ['review', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }],
    ])
    await bp.buildOneTask('wi', 5, { id: '2', title: 'Two' }, 'br', '1,2', '/tmp/wt', 2)
    assert.ok(gatherFired, 'the write-time trailer gather (build_state_cli.py gather) ran unchanged')
    // UFR-4 preflight is cached for the run — exactly ONE test-dispatch call across BOTH buildOneTask
    // invocations above (same process-level bp module instance, no require.cache reset yet).
    assert.strictEqual(authzCalls.n, 1, 'engine_authz.py test-dispatch preflight fires exactly ONCE per run (cached)')
    console.log('OK: build routes to the external implementation engine + verify/audit unchanged')
  }

  // ===========================================================================
  // Scenario 2: fail-closed trio + UFR-2 discard + mixed reviewer!=impl (FR-15).
  // Fresh module instance so the UFR-4 cache from scenario 1 does not leak in.
  // ===========================================================================
  {
    delete require.cache[require.resolve('../build_phase.js')]
    delete require.cache[require.resolve('../engine_dispatch.js')]
    const engineDispatch = require('../engine_dispatch.js')
    const dispatchCalls = []
    let dispatchShouldFail = true
    // #160: the per-task review is now engine-routed too, so the review branch fires for BOTH the
    // per-task loop and the whole-branch final review (reviewer:codex in part (c) below). Round 1
    // returns a blocker so the mixed reviewer=codex/impl=cursor case still drives a fix dispatch to
    // cursor through the per-task loop; every later review (round 2 + the whole-branch review) is clean.
    let reviewDispatchN = 0
    engineDispatch.dispatchExternal = async (o) => {
      dispatchCalls.push(o)
      if (dispatchShouldFail && (o.roleKind === 'build' || o.roleKind === 'fix')) {
        return { ok: false, reason: 'external-run-failed' }
      }
      if (o.roleKind === 'review') {
        reviewDispatchN += 1
        return reviewDispatchN === 1
          ? { findings: [{ severity: 'Critical', file: 'x.js', title: 'bug', cannot_verify_from_diff: false }] }
          : { findings: [] }
      }
      return { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } }
    }
    const bp = require('../build_phase.js')

    // (a) dispatchExternal fails -> resetUncommitted fires -> native worker THEN runs (fall open).
    globalThis.__SR_ENGINE_PREFS = { reviewer: 'claude', implementation: 'codex', effort: {} }
    let resetFired = 0
    let workerFired2 = 0
    global.agent = makeAgent([
      execRoute((p) => standardLeaf(p)),
      ['reset-uncommitted', () => { resetFired += 1; return { ok: true } }],
      ['implement-task', () => { workerFired2 += 1; return { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } } }],
      ['review', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }],
    ])
    const r2 = await bp.buildOneTask('wi', 5, { id: '3', title: 'Three' }, 'br', '3', '/tmp/wt', 1)
    assert.strictEqual(r2.parked, false, 'a failed external dispatch falls open to Claude and still completes')
    assert.strictEqual(resetFired, 1, 'UFR-2: a failed external write discards uncommitted edits (resetUncommitted)')
    assert.strictEqual(workerFired2, 1, 'the native worker agent() runs after the external dispatch fails (fall open, loop not blocked)')

    // (b) verify-SUCCESS path unchanged: the whole-branch final review's verify gate still runs on
    // an external build result (dispatchShouldFail toggled off so the final review dispatches
    // cleanly) and a passing verify (returncode:0) certifies clean.
    dispatchShouldFail = false
    let verifyGateFired = 0
    global.agent = makeAgent([
      execRoute((p) => standardLeaf(p)),
      ['implement-task', () => ({ ok: true, signal: 'ok', evidence: {} })],
      ['review', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }],
      ['verify_gate.py', (cmd) => { verifyGateFired += 1; return verifyGateStub(cmd, 'pass') }],
    ])
    resetRunDir(WI)
    const fr = await bp.runFinalReview(WI, 5, 'br', fs.mkdtempSync(path.join(os.tmpdir(), 'bpe-')))
    assertTerminal(fr, 'clean', 'the native verify-gate/reviewPanel path is untouched by the engine branch')
    assert.ok(verifyGateFired >= 1, 'the legKind.code verify path ran (verify_gate.py fired)')

    // (b2) FIX 6: the genuine verify-FAIL path — a failing verify command (returncode != 0) on an
    // otherwise-clean external-engine review must NOT certify clean; it halts (FR-17/UFR-4: a code
    // leg's clean terminal requires verify to have passed), unchanged by the engine branch.
    let verifyGateFiredFail = 0
    global.agent = makeAgent([
      execRoute((p) => standardLeaf(p)),
      ['implement-task', () => ({ ok: true, signal: 'ok', evidence: {} })],
      ['review', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }],
      ['verify_gate.py', (cmd) => { verifyGateFiredFail += 1; return verifyGateStub(cmd, 'fail') }],
    ])
    resetRunDir(WI)
    const frFail = await bp.runFinalReview(WI, 5, 'br', fs.mkdtempSync(path.join(os.tmpdir(), 'bpe-')))
    assertTerminal(frFail, 'halted', 'FIX 6: a failing verify command halts even on an otherwise-clean external-engine review')
    assert.ok(verifyGateFiredFail >= 1, 'the legKind.code verify path ran on the fail case too (verify_gate.py fired)')

    // (c) mixed reviewer=codex / impl=cursor: the per-task reviewer dispatches roleKind:'review',engine:
    // 'codex' (#160) while the fixer dispatches roleKind:'fix',engine:'cursor' (FR-15 split). The
    // per-task review is engine-routed now, so its blocker comes from the dispatchExternal review mock
    // above (round 1) — the native 'review' agent route is no longer exercised for reviewer:codex.
    globalThis.__SR_ENGINE_PREFS = { reviewer: 'codex', implementation: 'cursor', effort: {} }
    dispatchCalls.length = 0
    global.agent = makeAgent([
      execRoute((p) => standardLeaf(p)),
    ])
    const r3 = await bp.reviewLoop('wi', 5, { id: '4', title: 'Four' }, 'br', '/tmp/wt')
    assert.strictEqual(r3.parked, false, 'mixed reviewer!=impl fix loop completes clean')
    const perTaskReviewCall = dispatchCalls.find((o) => o.roleKind === 'review')
    assert.ok(perTaskReviewCall, '#160: the per-task reviewer dispatched externally')
    assert.strictEqual(perTaskReviewCall.engine, 'codex', '#160: the per-task reviewer routes to the reviewer engine (codex)')
    const fixCall = dispatchCalls.find((o) => o.roleKind === 'fix')
    assert.ok(fixCall, 'the fixer dispatched externally')
    assert.strictEqual(fixCall.engine, 'cursor', 'FR-15: the fixer routes to the implementation engine (cursor)')
    // #308/#309: the fix dispatch threads the resolved fixer tier (sonnet, code context) + the HIGH
    // write ceiling (2400s) — a fix is a write role, so it needs the same generous budget as a build.
    const modelTierS2 = require('../model_tier.js')
    assert.strictEqual(fixCall.model, modelTierS2.resolveModel('fixer', null, 'code'),
      '#308: the fix dispatch carries the resolved fixer tier (sonnet)')
    assert.strictEqual(fixCall.timeoutSeconds, 2400, '#309: the fix dispatch carries the high write ceiling (2400s)')
    dispatchCalls.length = 0
    global.agent = makeAgent([
      execRoute((p) => standardLeaf(p)),
      ['implement-task', () => ({ ok: true, signal: 'ok', evidence: {} })],
      ['verify_gate.py', (cmd) => verifyGateStub(cmd, 'pass')],
    ])
    resetRunDir(WI)
    const fr2 = await bp.runFinalReview(WI, 5, 'br', fs.mkdtempSync(path.join(os.tmpdir(), 'bpe-')))
    assertTerminal(fr2, 'clean', 'mixed-engine final review reaches clean')
    const reviewCall = dispatchCalls.find((o) => o.roleKind === 'review')
    assert.ok(reviewCall, 'the reviewer leaf dispatched externally')
    assert.strictEqual(reviewCall.engine, 'codex', 'FR-15: the reviewer leaf routes to the reviewer engine (codex)')
    // #308/#309: the whole-branch (deep) reviewer threads the reviewer-deep tier (opus) + the moderate
    // read ceiling (900s). reviewer-deep is a read role — it shares the read ceiling with review.
    assert.strictEqual(reviewCall.model, modelTierS2.resolveModel('reviewer-deep', null, null),
      '#308: the whole-branch reviewer dispatch carries the resolved reviewer-deep tier (opus)')
    assert.strictEqual(reviewCall.timeoutSeconds, 900, '#309: the whole-branch reviewer carries the moderate read ceiling (900s)')
    console.log('OK: fail-closed trio + UFR-2 discard + UFR-4 write-preflight-denied fall-open + final-fixer {fixed,deferred} contract + mixed reviewer!=impl')
  }

  // ===========================================================================
  // Scenario 3: UFR-4 preflight DENIED -> the impl role falls open to Claude for the WHOLE run.
  // Reset the module cache so this scenario re-probes from a clean _writeAuthOk = null (the module-
  // level cache from scenario 1/2 would otherwise leak a stale `true` verdict into this scenario).
  // ===========================================================================
  {
    delete require.cache[require.resolve('../build_phase.js')]
    delete require.cache[require.resolve('../engine_dispatch.js')]
    const engineDispatch = require('../engine_dispatch.js')
    const dispatchCalls = []
    engineDispatch.dispatchExternal = async (o) => {
      dispatchCalls.push(o)
      return { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } }
    }
    const bp = require('../build_phase.js')

    globalThis.__SR_ENGINE_PREFS = { reviewer: 'claude', implementation: 'codex', effort: {} }
    const authzCalls = { n: 0 }
    let workerFired3 = 0
    let fixerFired3 = 0
    global.agent = makeAgent([
      execRoute((p) => standardLeaf(p, { authzOk: false, authzCalls })),
      ['implement-task', () => { workerFired3 += 1; return { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } } }],
      ['fix-task', () => { fixerFired3 += 1; return { ok: true } }],
      ['review', (() => {
        let n = 0
        return () => {
          n += 1
          if (n === 1) {
            return { verdicts: { spec_compliance: 'fail', code_quality: 'pass' },
              findings: [{ severity: 'Critical', file: 'x.js', title: 'bug', cannot_verify_from_diff: false }] }
          }
          return { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }
        }
      })()],
    ])
    const r = await bp.buildOneTask('wi', 5, { id: '5', title: 'Five' }, 'br', '5', '/tmp/wt', 1)
    assert.strictEqual(r.parked, false, 'a denied preflight still completes the run (fall open, not parked)')
    assert.ok(dispatchCalls.every((o) => o.roleKind !== 'build' && o.roleKind !== 'fix'),
      'dispatchExternal is NEVER called for a write role once the preflight is denied')
    assert.strictEqual(workerFired3, 1, 'the native worker agent() ran (fall open)')
    assert.strictEqual(fixerFired3, 1, 'the native fixer agent() ran (fall open) for the fix round')
    assert.strictEqual(authzCalls.n, 1, 'the preflight itself is still probed exactly once (cached denial)')
    console.log('OK: per-round external fix dispatch (fold invariant boundary) + preflight-denied fall-open')
  }

  // ===========================================================================
  // Scenario 4: FIX I5 — the final-fixer's fixStep closure returns {fixed,deferred}, never the raw
  // _implDispatch result / undefined, so runFixStep does not treat a successful external fix as a
  // failure (which would halt the panel instead of continuing to re-review).
  // ===========================================================================
  {
    delete require.cache[require.resolve('../build_phase.js')]
    delete require.cache[require.resolve('../engine_dispatch.js')]
    const engineDispatch = require('../engine_dispatch.js')
    engineDispatch.dispatchExternal = async (o) => {
      if (o.roleKind === 'review') {
        return { findings: [] } // second round is clean
      }
      // the fix dispatch itself succeeds, returning the raw {ok,signal,evidence} dispatch shape —
      // NOT a {fixed,deferred} report. The fixStep closure must translate this into a report.
      return { ok: true, signal: 'ok', evidence: {} }
    }
    const bp = require('../build_phase.js')
    globalThis.__SR_ENGINE_PREFS = { reviewer: 'claude', implementation: 'codex', effort: {} }
    // runFinalReview's runDir is derived internally from workItem (not the caller-supplied wt), and
    // build_phase.js installs its OWN globalThis.recordDeferred (writing via io() to <runDir>/deferred-
    // set.json) — a test-local override set before the call would just be clobbered. Reset + recreate
    // the fixed runDir (mirrors production: showrunner.js mkdirp's the runDir before invoking the
    // phase) so the io()-backed write succeeds AND no earlier scenario's accumulator/deferred-set leaks in.
    const deferredSetPath = `${resetRunDir(WI)}/deferred-set.json`
    global.agent = makeAgent([
      execRoute((p) => standardLeaf(p)),
      ['review', (() => {
        let n = 0
        return () => {
          n += 1
          if (n === 1) return { findings: [{ severity: 'Critical', file: 'y.js', title: 'blocker', line: 1, evidence: 'x' }] }
          return { findings: [] }
        }
      })()],
      ['verify_gate.py', (cmd) => verifyGateStub(cmd, 'pass')],
    ])
    const fr = await bp.runFinalReview(WI, 5, 'br', fs.mkdtempSync(path.join(os.tmpdir(), 'bpe-')))
    assertTerminal(fr, 'clean',
      'FIX I5: a successful external final-fix is NOT treated as a fix-failure (would halt otherwise)')
    // recordDeferred (installed by build_phase.js itself) only reaches its io().writeFile call if
    // runFixStep received a TRUTHY {fixed,deferred} report from the fixStep closure — a raw
    // _implDispatch result ({ok,signal,evidence}) or undefined would have made runFixStep return
    // {ok:false} instead, short-circuiting to 'halted' before recordDeferred ever ran. So the mere
    // presence of the written deferred-set.json + the blocker's id inside it IS the FIX I5 contract
    // assertion (the terminal:'clean' assertion above already proves runFixStep did not fail-halt).
    const written = JSON.parse(fs.readFileSync(deferredSetPath, 'utf8'))
    assert.ok(Object.prototype.hasOwnProperty.call(written, 'blocker'),
      'the fixStep report\'s {fixed:[...]} ids (from blockers.map) reached recordDeferred/deferred-set.json')
    console.log('OK: final-fixer {fixed,deferred} report contract preserved with an external implementation engine')
  }

  // ===========================================================================
  // Scenario 5: commit-discipline multi-round fold invariant — two external fix rounds dispatch
  // TWICE with roleKind:'fix' and the SAME taskId (a fresh dispatch per round; fold correctness
  // inside dispatchExternal is unit-tested elsewhere).
  // ===========================================================================
  {
    delete require.cache[require.resolve('../build_phase.js')]
    delete require.cache[require.resolve('../engine_dispatch.js')]
    const engineDispatch = require('../engine_dispatch.js')
    const fixDispatches = []
    engineDispatch.dispatchExternal = async (o) => {
      if (o.roleKind === 'fix') fixDispatches.push(o)
      return { ok: true, signal: 'ok', evidence: {} }
    }
    const bp = require('../build_phase.js')
    globalThis.__SR_ENGINE_PREFS = { reviewer: 'claude', implementation: 'codex', effort: {} }
    global.agent = makeAgent([
      execRoute((p) => standardLeaf(p)),
      ['review', (() => {
        let n = 0
        return () => {
          n += 1
          if (n <= 2) {
            return { verdicts: { spec_compliance: 'fail', code_quality: 'pass' },
              findings: [{ severity: 'Critical', file: 'z.js', title: `round-${n}-bug`, cannot_verify_from_diff: false }] }
          }
          return { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }
        }
      })()],
    ])
    const r = await bp.reviewLoop('wi', 5, { id: '6', title: 'Six' }, 'br', '/tmp/wt')
    assert.strictEqual(r.parked, false, 'a two-round external fix loop completes clean')
    assert.strictEqual(fixDispatches.length, 2, 'exactly two external fix dispatches (one per round)')
    assert.strictEqual(fixDispatches[0].taskId, '6', 'round 1 fix dispatch carries the task id')
    assert.strictEqual(fixDispatches[1].taskId, '6', 'round 2 fix dispatch carries the SAME task id')
    console.log('OK: per-round external fix dispatch (fold invariant boundary)')
  }

  // ===========================================================================
  // Scenario 6 (#160): the PER-TASK reviewer honors enginePreferences.reviewer + the model tier.
  // Before #160, reviewLoop's per-task review called agent() with NO model and NO engine resolution,
  // so a project configured `reviewer: codex` never routed the per-task review to codex (it silently
  // rode the bundle's Opus safety floor). It must now mirror the whole-branch final review beside it:
  // dispatch to the reviewer engine at the LIGHTER `reviewer` tier / regular `review` effort (NOT the
  // deep review-deep the whole-branch review uses), and on the native (claude) path pass an EXPLICIT
  // reviewer model. The engine adapter's review parse yields {findings} only, so the two required
  // verdicts are synthesized from the findings (the task_review twin uses them only as a completeness
  // guard — the real decision rides the findings' blocking severities).
  // ===========================================================================
  {
    delete require.cache[require.resolve('../build_phase.js')]
    delete require.cache[require.resolve('../engine_dispatch.js')]
    const engineDispatch = require('../engine_dispatch.js')
    const modelTier = require('../model_tier.js')
    const bp = require('../build_phase.js')

    // (a) reviewer:codex -> the per-task review dispatches roleKind:'review',engine:'codex' at effort
    //     'review' (regular/high, NOT 'review-deep'/xhigh); the native per-task reviewer agent() NEVER
    //     fires; a clean external review (findings []) -> synthesized verdicts -> complete.
    globalThis.__SR_ENGINE_PREFS = { reviewer: 'codex', implementation: 'claude', effort: {} }
    const reviewDispatches = []
    engineDispatch.dispatchExternal = async (o) => {
      if (o.roleKind === 'review') { reviewDispatches.push(o); return { findings: [] } }
      return { ok: true, signal: 'ok', evidence: {} }
    }
    let nativeReviewFired = 0
    global.agent = makeAgent([
      execRoute((p) => standardLeaf(p)),
      ['review', () => { nativeReviewFired += 1; return { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] } }],
    ])
    let r = await bp.reviewLoop('wi', 5, { id: '7', title: 'Seven' }, 'br', '/tmp/wt')
    assert.strictEqual(r.parked, false, '#160: a clean external per-task review completes')
    assert.strictEqual(reviewDispatches.length, 1, '#160: the per-task review dispatched exactly once to the external engine')
    assert.strictEqual(reviewDispatches[0].engine, 'codex', '#160: the per-task review routes to the configured reviewer engine')
    assert.strictEqual(reviewDispatches[0].roleKind, 'review', '#160: the per-task review dispatches the review role')
    assert.strictEqual(reviewDispatches[0].effort, 'high', '#160: the per-task review runs at REGULAR review effort (high), not review-deep (xhigh)')
    assert.strictEqual(reviewDispatches[0].cwd, '/tmp/wt', '#160: the per-task review reads git from the build worktree')
    assert.strictEqual(reviewDispatches[0].taskId, '7', '#160: the per-task review carries the task id')
    assert.strictEqual(nativeReviewFired, 0, '#160: the native per-task reviewer agent() does NOT fire when the reviewer engine is external')
    // #308: the per-task review dispatch threads the resolved reviewer tier (sonnet) — cursor otherwise
    // ran composer. #309: the read role carries the moderate ceiling (900s), not the 300s default.
    const enginePrefS6 = require('../engine_pref.js')
    assert.strictEqual(reviewDispatches[0].model, modelTier.resolveModel('reviewer', null, null),
      '#308: the per-task review dispatch carries the resolved reviewer tier (sonnet)')
    assert.strictEqual(reviewDispatches[0].timeoutSeconds, enginePrefS6.resolveTimeout(globalThis.__SR_ENGINE_PREFS, 'review'),
      '#309: the per-task review dispatch carries the moderate read ceiling from the REAL resolveTimeout')
    assert.strictEqual(reviewDispatches[0].timeoutSeconds, 900, '#309: the read ceiling is 900s')

    // (b) an external review that returns a BLOCKING finding -> synthesized verdict drives a fix round,
    //     then a clean round-2 external review -> complete. Proves the decision rides the FINDINGS.
    let n = 0
    engineDispatch.dispatchExternal = async (o) => {
      if (o.roleKind === 'review') {
        n += 1
        return n === 1
          ? { findings: [{ severity: 'Critical', file: 'x.js', title: 'bug', cannot_verify_from_diff: false }] }
          : { findings: [] }
      }
      return { ok: true, signal: 'ok', evidence: {} }
    }
    global.agent = makeAgent([execRoute((p) => standardLeaf(p))])
    r = await bp.reviewLoop('wi', 5, { id: '8', title: 'Eight' }, 'br', '/tmp/wt')
    assert.strictEqual(r.parked, false, '#160: an external per-task review that finds then clears a blocker completes')
    assert.strictEqual(n, 2, '#160: the synthesized-fail verdict drove a fix round then a clean re-review (findings decide, not verdict text)')

    // (c) an UNREADABLE external review ({ok:false}, no findings array) falls OPEN to the native Claude
    //     reviewer (UFR-7 parity) — which itself passes an EXPLICIT reviewer model on opts.
    let capturedModel = 'UNSET'
    engineDispatch.dispatchExternal = async (o) => (o.roleKind === 'review')
      ? { ok: false, reason: 'unreadable' }
      : { ok: true, signal: 'ok', evidence: {} }
    global.agent = makeAgent([
      execRoute((p) => standardLeaf(p)),
      ['review', (_p, opts) => { capturedModel = opts && opts.model; return { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] } }],
    ])
    r = await bp.reviewLoop('wi', 5, { id: '9', title: 'Nine' }, 'br', '/tmp/wt')
    assert.strictEqual(r.parked, false, '#160: an unreadable external review falls open to Claude and completes')
    assert.strictEqual(capturedModel, modelTier.resolveModel('reviewer', null, null),
      '#160: the fall-open native per-task reviewer passes the EXPLICIT reviewer model tier (never session-inherited)')

    // (d) reviewer:claude (default) -> the per-task review does NOT dispatch externally; the native
    //     reviewer fires WITH an explicit reviewer model (the model-resolution half of #160).
    globalThis.__SR_ENGINE_PREFS = { reviewer: 'claude', implementation: 'claude', effort: {} }
    let dispatchedForReview = 0
    let capturedModelD = 'UNSET'
    engineDispatch.dispatchExternal = async (o) => { if (o.roleKind === 'review') dispatchedForReview += 1; return { ok: true, signal: 'ok', evidence: {} } }
    global.agent = makeAgent([
      execRoute((p) => standardLeaf(p)),
      ['review', (_p, opts) => { capturedModelD = opts && opts.model; return { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] } }],
    ])
    r = await bp.reviewLoop('wi', 5, { id: '10', title: 'Ten' }, 'br', '/tmp/wt')
    assert.strictEqual(r.parked, false, '#160: the default (claude) per-task review completes')
    assert.strictEqual(dispatchedForReview, 0, '#160: the default per-task review does NOT dispatch externally')
    assert.strictEqual(capturedModelD, modelTier.resolveModel('reviewer', null, null),
      '#160: the default native per-task reviewer resolves an EXPLICIT reviewer model tier (no silent session inheritance)')
    console.log('OK: #160 per-task reviewer honors the reviewer engine + explicit model tier')
  }

  // ===========================================================================
  // Scenario 7: the native BUILDER dispatch carries an EXPLICIT model equal to the readout's
  // builder-row model. Before this fix, buildOneTask called agent() with NO `model` option, so the
  // dispatch silently rode the bundle preamble's __safeSmartDefault() Opus floor while the preflight
  // readout's builder row (model_tier role 'builder') claimed the tier's model — an NFR-Accuracy break
  // (readout vs dispatch disagree). The mutation this pins: someone removes the `model` option and the
  // dispatch falls back to __safeSmartDefault() while the readout still shows the tier model. Both the
  // dispatch and the readout row resolve through model_tier.resolveModel('builder', ...), so this
  // asserts they share ONE source (the same guarantee the readout's builder row makes in Python).
  {
    delete require.cache[require.resolve('../build_phase.js')]
    delete require.cache[require.resolve('../engine_dispatch.js')]
    const modelTier = require('../model_tier.js')
    const bp = require('../build_phase.js')

    // (a) default config (impl:claude) -> the native builder fires WITH an explicit model equal to the
    //     readout's builder-row model (resolveModel('builder')), never a silent safeSmartDefault fall.
    globalThis.__SR_ENGINE_PREFS = { reviewer: 'claude', implementation: 'claude', effort: {} }
    delete globalThis.__SR_OVERRIDES
    let capturedBuilderModel = 'UNSET'
    global.agent = makeAgent([
      execRoute((p) => standardLeaf(p)),
      ['implement-task', (_p, opts) => { capturedBuilderModel = opts && opts.model; return { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } } }],
      ['review', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }],
    ])
    let r = await bp.buildOneTask('wi', 5, { id: '11', title: 'Eleven' }, 'br', '11', '/tmp/wt', 1)
    assert.strictEqual(r.parked, false, 'the native builder path completes')
    const readoutBuilderModel = modelTier.resolveModel('builder', null, null)
    assert.strictEqual(readoutBuilderModel, 'opus', 'the builder tier defaults to opus (owner smart-leaf policy)')
    assert.strictEqual(capturedBuilderModel, readoutBuilderModel,
      'the native builder dispatch carries an EXPLICIT model equal to the readout builder-row model (no safeSmartDefault fall)')

    // (b) a per-run builder override REACHES the dispatch — impossible before this fix (no `model`
    //     option existed to carry it). __SR_OVERRIDES.builder wins over the tier default.
    globalThis.__SR_OVERRIDES = { builder: 'sonnet' }
    let capturedBuilderModelOv = 'UNSET'
    global.agent = makeAgent([
      execRoute((p) => standardLeaf(p)),
      ['implement-task', (_p, opts) => { capturedBuilderModelOv = opts && opts.model; return { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } } }],
      ['review', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }],
    ])
    r = await bp.buildOneTask('wi', 5, { id: '12', title: 'Twelve' }, 'br', '12', '/tmp/wt', 1)
    assert.strictEqual(r.parked, false, 'the native builder path completes under an override')
    assert.strictEqual(capturedBuilderModelOv, modelTier.resolveModel('builder', globalThis.__SR_OVERRIDES, null),
      'a per-run builder-model override reaches the native builder dispatch (opts.model)')
    assert.strictEqual(capturedBuilderModelOv, 'sonnet', 'the builder override value (sonnet) is what the dispatch carries')
    delete globalThis.__SR_OVERRIDES
    console.log('OK: native builder dispatch carries an explicit model equal to the readout builder-row model')
  }

  // ===========================================================================
  // Scenario 8 (#309): the owner `timeout` override on __SR_ENGINE_PREFS REACHES the real build
  // dispatch — the UFR-5 override channel that was production-dead code. resolveTimeout is NOT
  // monkeypatched here (the production _implDispatch calls the REAL twin); only the dispatch is
  // captured. Without the override the build gets the 2400s ceiling; WITH it, the owner value wins.
  // ===========================================================================
  {
    delete require.cache[require.resolve('../build_phase.js')]
    delete require.cache[require.resolve('../engine_dispatch.js')]
    const engineDispatch = require('../engine_dispatch.js')
    const dispatchCalls = []
    engineDispatch.dispatchExternal = async (o) => {
      dispatchCalls.push(o)
      return { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } }
    }
    const bp = require('../build_phase.js')
    // owner override: a tighter-than-ceiling budget the owner deliberately set — it must beat 2400.
    globalThis.__SR_ENGINE_PREFS = { reviewer: 'claude', implementation: 'codex', effort: {}, timeout: 1800 }
    global.agent = makeAgent([
      execRoute((p) => standardLeaf(p)),
      ['implement-task', () => ({ ok: true, signal: 'ok', evidence: {} })],
      ['review', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }],
    ])
    const r = await bp.buildOneTask('wi', 5, { id: '13', title: 'Thirteen' }, 'br', '13', '/tmp/wt', 1)
    assert.strictEqual(r.parked, false, 'the build completes under an owner timeout override')
    const buildCall = dispatchCalls.find((o) => o.roleKind === 'build')
    assert.ok(buildCall, 'the build dispatched externally')
    assert.strictEqual(buildCall.timeoutSeconds, 1800,
      '#309: the owner enginePreferences.timeout override reaches the real build dispatch (not the 2400 ceiling)')
    delete globalThis.__SR_ENGINE_PREFS
    console.log('OK: #309 owner timeout override reaches the real production build dispatch')
  }

  delete globalThis.__SR_ENGINE_PREFS
  console.log('OK: build_phase engine branch (worker/fixer/final-review routing, UFR-2/4, FR-15, FIX I5)')
})().catch((e) => { console.error('FAIL:', e.message || e, e.stack || ''); process.exit(1) })
