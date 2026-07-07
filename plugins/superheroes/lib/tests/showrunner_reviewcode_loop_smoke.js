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
  const calls = { prov: 0, readout: 0, readoutPost: 0, fix: 0, recordDeferred: 0, reviewerModels: [], fixerModels: [] }
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
    // mirror the frozen record_deferred.py exactly: it reads ONLY `fixed` (normalizeFixResult
    // guarantees the key on every report) — a `fixes`-only report must surface as empty enrichment.
    return JSON.stringify({ ok: true, extras: { fixes: Array.isArray(report.fixed) ? report.fixed : [] } })
  }
  global.agent = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'resume') return '1'
    // #115 Task 16: verifyAgent emits raw run data; JS twin classifies in-process
    if (label === 'run verify') return { command: 'run-tests', returncode: 0, timedOut: false }
    if (label.startsWith('synthesis')) return { verdicts: [], usage: { total: 1 } }
    // the cheap recordDeferred pipe (a dumb courier leaf; routed by its command, not its label)
    if (opts && opts.courier && prompt.includes('record_deferred.py')) return [{ index: 0, ok: true, stdout: runRecordDeferred(prompt) }]
    if (label.startsWith('fix-code')) {
      calls.fix += 1
      calls.fixerModels.push({ label, model: opts && opts.model })
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
      return { fixes: ids, deferred: [], changedSubjects: ['Code'], coverageDecisions: [] }
    }
    if (label === 'readout') { calls.readout += 1; return '## Review loop — done' }
    if (label === 'post readout') { calls.readoutPost += 1; return jsonOut({ posted: true, recorded: true }) }
    if (label === 'stamp review coverage') {
      calls.prov += 1
      return jsonOut({ ok: provOk, error: provOk ? undefined : 'disk full' })
    }
    // #118: the config fallback rides the exec courier (raw stdout), not cmdRunner 'lib'
    if (opts && opts.courier && prompt.includes('review_code_config.py')) {
      return JSON.stringify({ verifyCommand: 'none', tiers: { reviewer: 'sonnet', reviewerDeep: 'opus', synthesis: 'opus', fixer: 'sonnet' } })
    }
    if (opts && opts.courier && prompt.includes('git rev-parse')) return 'stub-head\n'
    if (label === 'lib') {
      return { ok: true }
    }
    // any other cheap dumb-pipe leaf — routed AFTER the named courier branches AND the 'lib' cmdRunner
    // branch (cmdRunner 'lib' leaves also carry courier:true), so it never swallows 'post readout'/
    // 'stamp review coverage' or a courier-marked 'lib' StructuredOutput leaf.
    if (opts && opts.courier) return []
    const m = label.match(/^(architecture|code|security|test|premortem)-reviewer:r(\d+)/)
    if (m) {
      const round = Number(m[2]) || 1
      calls.reviewerModels.push({ label, round, model: opts && opts.model })
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
  // #212 addendum3: the terminal + honest reason survives the phase layer on parkDetail (phase_step
  // threads it into the workflow park reason), naming the seat + defect class — not a bare flatten.
  assert.match(r.phaseResult.parkDetail || '',
    /^cannot-certify: architecture-reviewer did not return a usable result after retry \(malformed — uncertifiable\)/,
    '#212: reviewCodePhase names the terminal + honest reason on parkDetail')

  calls = install({ roundFindings: [[]], provOk: false })
  r = await sr.reviewCodePhase('wi-ufr2', { runDir: fresh(), resolveTarget: stubResolveTarget })
  assert.strictEqual(r.gate, 'changes-requested', 'failed covers stamp -> park, never ship-ready (UFR-2)')
  assert.strictEqual(r.phaseResult.confidence, 'low', 'UFR-2 park is low-confidence (resumable)')

  const fixRunDir = fresh()
  calls = install({ roundFindings: [BLOCKER, [], []], fix: 'resolve' })
  r = await sr.reviewCodePhase('wi-fix', { runDir: fixRunDir, resolveTarget: stubResolveTarget })
  assert.strictEqual(r.gate, 'passed', 'continue then clean converges to passed')
  assert.ok(calls.fix === 1 && calls.recordDeferred === 1, 'the fix step + recordDeferred leaves are invoked')
  assert.strictEqual(calls.prov, 1, 'a fix-applied clean still stamps covers (X′)')
  const lastExtras = JSON.parse(fs.readFileSync(path.join(fixRunDir, 'last-extras.json'), 'utf8'))
  assert.deepStrictEqual(lastExtras.changedSubjects, ['Code'],
    'real fix executor path must persist normalized changedSubjects beside fix-detail extras')
  const records = JSON.parse(fs.readFileSync(path.join(fixRunDir, 'round-records.json'), 'utf8'))
  const roundTwoDims = records.find((rec) => rec.round === 2).dimensions
  assert.ok(Object.values(roundTwoDims).some((dim) => dim.status === 'skipped' || dim.tier === 'reviewer'),
    'round 2 must consume persisted changedSubjects and schedule skips or cheap reviewer runs')
  assert.ok(calls.reviewerModels.some((call) => call.round === 2 && call.model === 'sonnet'),
    'a cheap-scheduled round-2 reviewer must dispatch with an explicit Sonnet-tier model')

  // ── FR-8 / NFR-Accuracy: frozen per-run model pins reach the review-code dispatch ──────────────
  // With NO pins (__SR_OVERRIDES absent), the dispatch carries the cfg.tiers values EXACTLY — the
  // deep reviewer at the reviewerDeep tier ('opus') and the fixer at the fixer tier ('sonnet').
  // (This is the byte-identical no-op control; the mutation to kill is removing the pinnedTier overlay.)
  assert.ok(!globalThis.__SR_OVERRIDES, 'precondition: no frozen pins for the no-op control')
  assert.ok(calls.fixerModels.length >= 1 && calls.fixerModels.every((c) => c.model === 'sonnet'),
    'no pins: the fixer dispatch carries the cfg.tiers fixer model (sonnet), unchanged')
  assert.ok(calls.reviewerModels.some((c) => c.round === 1 && c.model === 'opus'),
    'no pins: the round-1 deep reviewer dispatch carries the cfg.tiers reviewerDeep model (opus), unchanged')

  // With a FROZEN pin for the deep reviewer AND the fixer (as mergeFrozenSnapshot lands them into
  // __SR_OVERRIDES, keyed by the model_tier role — 'reviewer-deep' / 'fixer'), the dispatch carries
  // the PINNED model, NOT cfg.tiers'. cfg.tiers is still {reviewerDeep:'opus', fixer:'sonnet'}; the
  // pins ('haiku' / 'opus') are distinct from those so a miss is visible.
  const pinRunDir = fresh()
  const pinCalls = install({ roundFindings: [BLOCKER, [], []], fix: 'resolve' })
  globalThis.__SR_OVERRIDES = { 'reviewer-deep': 'haiku', fixer: 'opus' }
  try {
    r = await sr.reviewCodePhase('wi-pinned', { runDir: pinRunDir, resolveTarget: stubResolveTarget })
  } finally {
    delete globalThis.__SR_OVERRIDES
  }
  assert.strictEqual(r.gate, 'passed', 'pinned run still converges to passed')
  assert.ok(pinCalls.reviewerModels.some((c) => c.round === 1 && c.model === 'haiku'),
    'frozen reviewer-deep pin reaches the deep-reviewer dispatch (haiku), overriding cfg.tiers opus')
  assert.ok(pinCalls.reviewerModels.every((c) => c.model !== 'opus'),
    'the disk-resolved reviewerDeep model (opus) never reaches dispatch once a per-run pin exists')
  assert.ok(pinCalls.fixerModels.length >= 1 && pinCalls.fixerModels.every((c) => c.model === 'opus'),
    'frozen fixer pin reaches the fixer dispatch (opus), overriding cfg.tiers sonnet')

  const rawRunDir = fresh()
  const rawCalls = []
  const rawLeaves = {
    reviewerAgent: async (reviewer, context, rubric, runDir, round, opts) => {
      rawCalls.push({ reviewer, round, tier: opts && opts.tier })
      if (round === 1 && reviewer === 'code-reviewer') return reviewerPayload(BLOCKER, runDir, round)
      return reviewerPayload([], runDir, round)
    },
    synthesisLeaf: async () => ({ verdicts: [], usage: { total: 1 } }),
    fixStep: async () => ({ fixed: [], changedSubjects: ['src/raw-path.js'], coverageDecisions: [] }),
    recordDeferred: async () => {},
  }
  r = await sr.runReviewCodePanel({
    runDir: rawRunDir,
    context: { workItem: 'wi-raw-paths' },
    rubric: 'review-base',
    verifyCommand: 'none',
    leaves: rawLeaves,
  })
  assert.strictEqual(r.terminal, 'clean', 'raw-path defensive scheduling still converges')
  const rawExtras = JSON.parse(fs.readFileSync(path.join(rawRunDir, 'last-extras.json'), 'utf8'))
  assert.deepStrictEqual(rawExtras.changedSubjects, [],
    'unnormalized top-level changedSubjects must not be trusted as policy subjects')
  assert.deepStrictEqual(rawExtras.changedSubjectDetails, ['src/raw-path.js'],
    'raw top-level changedSubjects remain available only as details')
  const rawRecords = JSON.parse(fs.readFileSync(path.join(rawRunDir, 'round-records.json'), 'utf8'))
  const rawRoundTwoCode = rawRecords.find((rec) => rec.round === 2).dimensions['code-reviewer']
  assert.notStrictEqual(rawRoundTwoCode.status, 'skipped',
    'a dimension with prior findings must not be skipped when raw paths normalize to no policy subjects')
  assert.ok(rawCalls.some((call) => call.round === 2 && call.reviewer === 'code-reviewer'),
    'the prior-finding dimension actually ran on the intermediate round')

  console.log('ok: reviewCodePhase clean/skips/halted/cannot-certify + UFR-2 + continue/fix/clean + frozen model pins reach dispatch')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
