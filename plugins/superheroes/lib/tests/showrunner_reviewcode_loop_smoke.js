// plugins/superheroes/lib/tests/showrunner_reviewcode_loop_smoke.js
// Dev-time (node, not CI): drives the REAL reviewPanel shell with reviewCodePhase's real wrappers
// across every terminal + the UFR-2 covers-stamp-failure park. #115: reviewers RETURN findings[];
// merge/synthesis-consume/tally are in-process twins; recordDeferred writes the deferred-set via the
// cheap exec pipe (record_deferred.py — here emulated in the exec stub so the on-disk deferred-set
// drives the next round's tally). Stubs the Workflow runtime + the lib command-runner.
// Run: node plugins/superheroes/lib/tests/showrunner_reviewcode_loop_smoke.js
const assert = require('assert')
const fs = require('fs'); const os = require('os'); const path = require('path')
const sr = require('../showrunner.js')
const { findingIdentity } = require('../circuit_breaker.js')

function jsonOut(obj) { return [{ ok: true, stdout: JSON.stringify(obj) }] }

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}

// A fresh on-disk runDir per scenario so the durable accumulator + deferred-set never leak across
// scenarios OR across `node` runs (reviewCodePhase otherwise reuses /tmp/showrunner-<wi>-review-code).
function fresh() { return fs.mkdtempSync(path.join(os.tmpdir(), 'rcloop-')) }

// A scenario supplies, per round, the findings every reviewer returns (the same array drives all five
// reviewers — a cited blocker compiles to one blocking finding by identity), the fixer behaviour, and
// whether the covers-stamp write succeeds. `roundFindings` is a queue (last value repeats).
function install({ roundFindings, fix = 'resolve', provOk = true }) {
  const queue = roundFindings.slice()
  const nextFindings = () => (queue.length > 1 ? queue.shift() : queue[0])
  const calls = { prov: 0, readout: 0, readoutPost: 0, fix: 0, recordDeferred: 0 }
  // Emulate record_deferred.py inside the exec dumb-pipe: write deferred-set.json so the next round's
  // in-process tally reads the deferral (present-∩-deferred -> clean-with-skips).
  function runRecordDeferred(cmd) {
    calls.recordDeferred += 1
    const rd = cmd.match(/--run-dir '([^']+)'/)
    const rep = cmd.match(/--report '(.*)'\s*$/s)
    let runDir = rd && rd[1]; let report = {}
    try { report = JSON.parse((rep && rep[1] || '{}').replace(/'\\''/g, "'")) } catch (_) {}
    const p = `${runDir}/deferred-set.json`
    let set = {}
    try { set = JSON.parse(fs.readFileSync(p, 'utf8')) } catch (_) {}
    for (const d of report.deferred || []) if (d && d.id) set[d.id] = d.severity
    try { fs.writeFileSync(p, JSON.stringify(set)) } catch (_) {}
    return JSON.stringify({ ok: true, extras: { fixes: report.fixed || [] } })
  }
  global.agent = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'resume') return '1'
    // #115 Task 16: verifyAgent emits raw run data; JS twin classifies in-process
    if (label === 'run verify') return { command: 'run-tests', returncode: 0, timedOut: false }
    if (label.startsWith('synthesis')) return { verdicts: [] }   // keep all merged findings
    if (label === 'exec') {                                       // the cheap recordDeferred pipe
      if (prompt.includes('record_deferred.py')) return [{ index: 0, ok: true, stdout: runRecordDeferred(prompt) }]
      return []
    }
    if (label === 'fix-code') {
      calls.fix += 1
      const f = nextFindings() || []
      const ids = f.filter((x) => x.severity === 'Critical' || x.severity === 'Important').map(findingIdentity)
      if (fix === 'fail') return null                            // fix failure -> halted
      if (fix === 'defer') return { fixed: [], deferred: ids.map((id) => ({ id, severity: 'Important', parentOrigin: 'plan' })) }
      return { fixed: ids, deferred: [] }                        // resolve
    }
    if (label === 'readout') { calls.readout += 1; return '## Review loop — done' }
    if (label === 'post readout') { calls.readoutPost += 1; return jsonOut({ posted: true, recorded: true }) }
    if (label === 'stamp review coverage') {
      calls.prov += 1
      return jsonOut({ ok: provOk, error: provOk ? undefined : 'disk full' })
    }
    if (label === 'lib') {
      if (prompt.includes('review_code_config.py')) return { verifyCommand: 'none', tiers: { reviewer: 'sonnet', reviewerDeep: 'opus', synthesis: 'opus', fixer: 'sonnet' } }
      return { ok: true }
    }
    // every reviewer leg RETURNS {findings:[...]} (the panel holds them in memory).
    if (label.startsWith('branch-reviewer:')) return { findings: nextFindings() || [] }
    return { findings: [] }
  }
  return calls
}

const BLOCKER = [{ file: 'a.py', line: 1, title: 'bug', severity: 'Important', evidence: 'e' }]

// Stub resolveTarget: returns a synthetic build worktree so loop-terminal scenarios can exercise the
// full reviewCodePhase path without a real build worktree on disk. The seam is on opts.resolveTarget.
// expectedHead is null here so the head-mismatch check (which needs a real git HEAD) is not armed;
// the loop-terminal scenarios focus on clean/halt/fix/skips/cc/ufr2, not head-verification coverage
// (that is covered by the targeted smoke + the new resolver-seam smoke below).
const STUB_WT = '/tmp/review-loop-stub-wt'
const stubResolveTarget = async () => ({ worktree: STUB_WT, expectedHead: null })

async function main() {
  // 1. clean -> advance + covers stamped (FR-9), gate passed.
  let calls = install({ roundFindings: [[]] })
  let r = await sr.reviewCodePhase('wi-clean', { runDir: fresh(), resolveTarget: stubResolveTarget })
  assert.strictEqual(r.gate, 'passed', 'clean -> passed')
  assert.strictEqual(calls.prov, 1, 'clean stamps covers exactly once')

  // 2. clean-with-skips -> advance, gate passed, NO covers stamp (parks later at the ship gate). The
  //    blocker is flagged every round but the fixer DEFERS it -> round 2 is present-∩-deferred.
  calls = install({ roundFindings: [BLOCKER], fix: 'defer' })
  r = await sr.reviewCodePhase('wi-skips', { runDir: fresh(), resolveTarget: stubResolveTarget })
  assert.strictEqual(r.gate, 'passed', 'clean-with-skips advances like clean')
  assert.strictEqual(calls.prov, 0, 'clean-with-skips must not stamp covers (FR-9)')

  // 3. halted -> park (changes-requested) + readout posted (UFR-1). A blocker whose fix step fails.
  calls = install({ roundFindings: [BLOCKER], fix: 'fail' })
  r = await sr.reviewCodePhase('wi-halt', { runDir: fresh(), resolveTarget: stubResolveTarget })
  assert.strictEqual(r.gate, 'changes-requested', 'halted -> park')
  assert.ok(calls.readout === 1 && calls.readoutPost === 1, 'halted posts the uniform readout')
  assert.strictEqual(calls.prov, 0, 'a park never stamps covers')

  // 4. cannot-certify -> park (changes-requested). A reviewer that does NOT complete (non-array).
  install({ roundFindings: [[]] })
  let incomplete = 0
  const realAgent = global.agent
  global.agent = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    // the first reviewer never returns a findings array (and its retry also fails) -> coverage gap.
    if (label.startsWith('branch-reviewer:')) { incomplete += 1; return { notFindings: true } }
    return realAgent(prompt, opts)
  }
  r = await sr.reviewCodePhase('wi-cc', { runDir: fresh(), resolveTarget: stubResolveTarget })
  assert.strictEqual(r.gate, 'changes-requested', 'cannot-certify -> park')
  assert.ok(incomplete >= 1, 'an incomplete reviewer drives cannot-certify')

  // 5. UFR-2: clean but the covers-stamp write fails -> low-confidence park, NOT ship-ready.
  calls = install({ roundFindings: [[]], provOk: false })
  r = await sr.reviewCodePhase('wi-ufr2', { runDir: fresh(), resolveTarget: stubResolveTarget })
  assert.strictEqual(r.gate, 'changes-requested', 'failed covers stamp -> park, never ship-ready (UFR-2)')
  assert.strictEqual(r.phaseResult.confidence, 'low', 'UFR-2 park is low-confidence (resumable)')

  // 6. continue -> fix step + recordDeferred -> re-review clean (the fix path is wired, loop converges).
  //    Round 1 flags the blocker (continue); the fixer RESOLVES it; round 2 returns [] -> clean.
  calls = install({ roundFindings: [BLOCKER, []], fix: 'resolve' })
  r = await sr.reviewCodePhase('wi-fix', { runDir: fresh(), resolveTarget: stubResolveTarget })
  assert.strictEqual(r.gate, 'passed', 'continue then clean converges to passed')
  assert.ok(calls.fix === 1 && calls.recordDeferred === 1, 'the fix step + recordDeferred leaves are invoked')
  assert.strictEqual(calls.prov, 1, 'a fix-applied clean still stamps covers (X′)')

  console.log('ok: reviewCodePhase clean/skips/halted/cannot-certify + UFR-2 + continue/fix/clean')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
