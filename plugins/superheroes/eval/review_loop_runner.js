#!/usr/bin/env node
const fs = require('fs')
const os = require('os')
const path = require('path')
const { reviewPanel } = require('../lib/review_panel_shell.js')
const { defaultIo } = require('../lib/io_seam.js')

const fixture = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const failTelemetry = process.argv.includes('--fail-telemetry')
function receipt(runId, round, opts = {}) {
  return { artifact: `${runId}:round-${round}`, chain: [
    { step: 'citation', evidence: 'fixture cited changed artifact' },
    { step: 'reachability', evidence: 'fixture reached changed path' },
    { step: 'missing-check', evidence: 'fixture checked missing requirements' },
    { step: 'tooling', evidence: 'fixture harness completed' },
  ], coverageDecisionIds: ((opts.coverageDecisions || []).map((d) => d.id).filter(Boolean)) }
}

const events = (fixture.reviewerEvents || []).slice()
const seen = []
const usage = {}
const coverageDecisionIds = []
const fixContexts = []
const fixResults = []

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}
global.io = Object.assign({}, defaultIo, {
  async runHelper(cmd, args) {
    if (failTelemetry && String((args || [])[0]).endsWith('review_telemetry.py')) {
      return { ok: false, status: 1, stdout: '{"ok":false,"reason":"forced-telemetry-failure"}\n', stderr: 'forced telemetry failure' }
    }
    const argv = args || []
    // The telemetry rounds now come from round-records.json on disk (write-from-records); only
    // the small usage map rides the invocation. Simulate the fix leaf's usage (the live fix
    // leaf does not report usage) by injecting the expected fix:rN leaves into --usage-json.
    if (String(argv[0]).endsWith('review_telemetry.py') && argv.includes('write-from-records')) {
      const uIdx = argv.indexOf('--usage-json')
      const eIdx = argv.indexOf('--expected-leaves-json')
      if (uIdx >= 0 && eIdx >= 0) {
        const usageArg = JSON.parse(argv[uIdx + 1])
        for (const leaf of JSON.parse(argv[eIdx + 1])) {
          if (leaf.startsWith('fix:r') && !usageArg[leaf]) {
            usageArg[leaf] = { total: Number((usage[leaf] && usage[leaf].total) || 1) }
          }
        }
        argv[uIdx + 1] = JSON.stringify(usageArg)
      }
    }
    return defaultIo.runHelper(cmd, args)
  },
})

global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts = {}) => {
  const idx = events.findIndex((e) => e.round === round && e.reviewer === reviewer && (!e.tier || e.tier === opts.tier))
  const event = idx >= 0 ? events.splice(idx, 1)[0] : { findings: [], usageTotal: 1 }
  seen.push({ reviewer, round, tier: opts.tier, roundKind: opts.roundKind })
  usage[`${reviewer}:r${round}`] = { total: event.usageTotal || 1 }
  return { findings: event.findings || [], confidence: event.confidence || 'high', verificationReceipt: receipt(fixture.name, round, opts), usage: { total: event.usageTotal || 1 } }
}
global.synthesisLeaf = async (_merged, _context, _rubric, _runDir, round) => {
  usage[`synthesis:r${round}`] = { total: 1 }
  return { verdicts: [], usage: { total: 1 } }
}
global.recordDeferred = async () => {}
global.fixStep = async (fixContext, verdict) => {
  // #211: the fixer receives the worklist PATH; read it so the eval can assert on its content
  // (findings / classKeys / generalizeRequired / changedSubjects / coverageDecisions on disk).
  let context = fixContext
  if (fixContext && fixContext.worklistPath) {
    try { context = JSON.parse(fs.readFileSync(fixContext.worklistPath, 'utf8')) } catch (_) { context = fixContext }
  }
  fixContexts.push({ round: verdict.round, context })
  usage[`fix:r${verdict.round}`] = { total: 1 }
  const fix = (fixture.fixEvents || []).find((f) => f.afterRound === verdict.round) || { changedSubjects: [], coverageDecisions: [] }
  fixResults.push({ round: verdict.round, coverageDecisionIds: (fix.coverageDecisions || []).map((d) => d.id).filter(Boolean) })
  for (const d of fix.coverageDecisions || []) coverageDecisionIds.push(d.id)
  return { fixed: ['fixture'], changedSubjects: fix.changedSubjects || [], coverageDecisions: fix.coverageDecisions || [], extras: { changedSubjects: fix.changedSubjects || [], needsConfirmation: true } }
}

async function main() {
  const runDir = fs.mkdtempSync(path.join(os.tmpdir(), `${fixture.name}-`))
  if (fixture.seedRoundRecords) fs.writeFileSync(path.join(runDir, 'round-records.json'), JSON.stringify(fixture.seedRoundRecords))
  if (fixture.seedCoverageDecisions) fs.writeFileSync(path.join(runDir, 'review-coverage-decisions.json'), JSON.stringify(fixture.seedCoverageDecisions))
  const verdict = await reviewPanel({
    reviewerSet: fixture.reviewerSet,
    context: { fixture: fixture.name },
    rubric: 'review-loop convergence eval',
    runKey: fixture.name,
    runDir,
    fixStep: global.fixStep,
    legKind: { panel: true, code: false },
    maxRounds: fixture.maxRounds || 7,
  })
  let telemetry = verdict.telemetry || null
  try { telemetry = JSON.parse(fs.readFileSync(path.join(runDir, 'review-telemetry.json'), 'utf8')) } catch (_) {}
  const fallbackTotal = Object.values(usage).reduce((sum, u) => sum + Number(u.total || 0), 0)
  const tokenTotal = telemetry && telemetry.tokenUsage ? telemetry.tokenUsage.total : fallbackTotal
  console.log(JSON.stringify({ terminal: verdict.terminal, roundCount: Math.max(...seen.map((x) => x.round)), tokenTotal, benchmarkValid: !!(telemetry && telemetry.benchmarkValid), telemetry, coverageDecisionIds, seen, fixContexts, fixResults }))
}

main().catch((err) => {
  console.error(err && err.stack ? err.stack : String(err))
  process.exit(1)
})
