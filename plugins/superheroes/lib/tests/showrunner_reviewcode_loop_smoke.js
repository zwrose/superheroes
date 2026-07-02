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

function fresh() { return fs.mkdtempSync(path.join(os.tmpdir(), 'rcloop-')) }

function reviewerPayload(findings, runDir, round) {
  return {
    findings: findings || [],
    confidence: 'high',
    verificationReceipt: {
      artifact: `${runDir}:round-${round}`,
      chain: [
        { step: 'citation', evidence: 'reviewed citations' },
        { step: 'reachability', evidence: 'validated call path' },
        { step: 'missing-check', evidence: 'checked missing FRs' },
        { step: 'tooling', evidence: 'smoke passed' },
      ],
      coverageDecisionIds: [],
    },
    usage: { input: 0, output: 0, total: 1 },
  }
}

function install({ roundFindings, fix = 'resolve', provOk = true }) {
  const queue = roundFindings.slice()
  const nextFindings = () => (queue.length > 1 ? queue.shift() : queue[0])
  const calls = { prov: 0, readout: 0, readoutPost: 0, fix: 0, recordDeferred: 0 }
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
    return JSON.stringify({ ok: true, extras: { fixes: report.fixed || report.fixes || [] } })
  }
  global.agent = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'resume') return '1'
    // #115 Task 16: verifyAgent emits raw run data; JS twin classifies in-process
    if (label === 'run verify') return { command: 'run-tests', returncode: 0, timedOut: false }
    if (label.startsWith('synthesis')) return { verdicts: [], usage: { total: 1 } }
    if (label === 'exec') {                                       // the cheap recordDeferred pipe
      if (prompt.includes('record_deferred.py')) return [{ index: 0, ok: true, stdout: runRecordDeferred(prompt) }]
      return []
    }
    if (label.startsWith('fix-code')) {
      calls.fix += 1
      const f = nextFindings() || []
      const ids = f.filter((x) => x.severity === 'Critical' || x.severity === 'Important').map(findingIdentity)
      if (fix === 'fail') return null
      if (fix === 'defer') {
        return {
          fixes: [],
          deferred: ids.map((id) => ({ id, severity: 'Important', parentOrigin: 'plan' })),
          changedSubjects: ['Code'],
          coverageDecisions: [],
          extras: { parentOrigin: 'plan' },
        }
      }
      return { fixes: ids, fixed: ids, deferred: [], changedSubjects: ['Code'], coverageDecisions: [] }
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
    const m = label.match(/^(architecture|code|security|test|premortem)-reviewer:r(\d+)/)
    if (m) {
      const round = Number(m[2]) || 1
      const runDir = (prompt.match(/Prompt context: (\{.*\})/) || [])[1]
      let ctx = {}
      try { ctx = JSON.parse(runDir || '{}') } catch (_) {}
      const rd = ctx.receiptArtifact ? ctx.receiptArtifact.replace(/:round-\d+$/, '') : 'run'
      return reviewerPayload(nextFindings() || [], rd, round)
    }
    return reviewerPayload([], 'run', 1)
  }
  return calls
}

const BLOCKER = [{ file: 'a.py', line: 1, title: 'bug', severity: 'Important', evidence: 'e' }]

const STUB_WT = '/tmp/review-loop-stub-wt'
const stubResolveTarget = async () => ({ worktree: STUB_WT, expectedHead: null })

async function main() {
  let calls = install({ roundFindings: [[]] })
  let r = await sr.reviewCodePhase('wi-clean', { runDir: fresh(), resolveTarget: stubResolveTarget })
  assert.strictEqual(r.gate, 'passed', 'clean -> passed')
  assert.strictEqual(calls.prov, 1, 'clean stamps covers exactly once')

  calls = install({ roundFindings: [BLOCKER], fix: 'defer' })
  r = await sr.reviewCodePhase('wi-skips', { runDir: fresh(), resolveTarget: stubResolveTarget })
  assert.strictEqual(r.gate, 'changes-requested', 'clean-with-skips parks while a blocking tail exists')
  assert.strictEqual(calls.prov, 0, 'clean-with-skips records NO covers stamp')

  calls = install({ roundFindings: [BLOCKER], fix: 'fail' })
  r = await sr.reviewCodePhase('wi-halt', { runDir: fresh(), resolveTarget: stubResolveTarget })
  assert.strictEqual(r.gate, 'changes-requested', 'halted -> park')
  assert.ok(calls.readout === 1 && calls.readoutPost === 1, 'halted posts the uniform readout')
  assert.strictEqual(calls.prov, 0, 'a park never stamps covers')

  install({ roundFindings: [[]] })
  let incomplete = 0
  const realAgent = global.agent
  global.agent = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    // this reviewer never returns a findings array (and its retry also fails) -> coverage gap.
    if (label.startsWith('architecture-reviewer')) { incomplete += 1; return { notFindings: true } }
    return realAgent(prompt, opts)
  }
  r = await sr.reviewCodePhase('wi-cc', { runDir: fresh(), resolveTarget: stubResolveTarget })
  assert.strictEqual(r.gate, 'changes-requested', 'cannot-certify -> park')
  assert.ok(incomplete >= 1, 'an incomplete reviewer drives cannot-certify')

  calls = install({ roundFindings: [[]], provOk: false })
  r = await sr.reviewCodePhase('wi-ufr2', { runDir: fresh(), resolveTarget: stubResolveTarget })
  assert.strictEqual(r.gate, 'changes-requested', 'failed covers stamp -> park, never ship-ready (UFR-2)')
  assert.strictEqual(r.phaseResult.confidence, 'low', 'UFR-2 park is low-confidence (resumable)')

  calls = install({ roundFindings: [BLOCKER, [], []], fix: 'resolve' })
  r = await sr.reviewCodePhase('wi-fix', { runDir: fresh(), resolveTarget: stubResolveTarget })
  assert.strictEqual(r.gate, 'passed', 'continue then clean converges to passed')
  assert.ok(calls.fix === 1 && calls.recordDeferred === 1, 'the fix step + recordDeferred leaves are invoked')
  assert.strictEqual(calls.prov, 1, 'a fix-applied clean still stamps covers (X′)')

  console.log('ok: reviewCodePhase clean/skips/halted/cannot-certify + UFR-2 + continue/fix/clean')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
