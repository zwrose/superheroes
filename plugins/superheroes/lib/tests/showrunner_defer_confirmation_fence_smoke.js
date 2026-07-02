// Probe: defer-then-exit bypass — a fix round that defers blockers and sets confirmationPending
// must not exit clean-with-skips on the next intermediate round; it must enter confirmation.
// Run: node plugins/superheroes/lib/tests/showrunner_defer_confirmation_fence_smoke.js
const assert = require('assert')
const fs = require('fs')
const os = require('os')
const path = require('path')
const { reviewPanel } = require('../review_panel_shell.js')
const { findingIdentity } = require('../circuit_breaker.js')

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}
global.synthesisLeaf = async () => ({ verdicts: [], usage: { total: 1 } })
global.recordDeferred = async (report, _verdict, runDir) => {
  const p = path.join(runDir, 'deferred-set.json')
  let set = {}
  try { set = JSON.parse(fs.readFileSync(p, 'utf8')) } catch (_) {}
  for (const d of (report && report.deferred) || []) set[d.id] = d.severity
  fs.writeFileSync(p, JSON.stringify(set))
}

const BLOCKER = [{ file: 'a.py', line: 1, title: 'bug', severity: 'Critical', evidence: 'x' }]
const IDENT = findingIdentity(BLOCKER[0])

function receipt(runDir, round, opts = {}) {
  return {
    artifact: `${runDir}:round-${round}`,
    chain: [
      { step: 'citation', evidence: 'x' },
      { step: 'reachability', evidence: 'x' },
      { step: 'missing-check', evidence: 'x' },
      { step: 'tooling', evidence: 'x' },
    ],
    coverageDecisionIds: [],
  }
}
function blockerResult(runDir, round, opts = {}) {
  return { findings: BLOCKER, confidence: 'high', verificationReceipt: receipt(runDir, round, opts), usage: { total: 1 } }
}
function cleanResult(runDir, round, opts = {}) {
  return { findings: [], confidence: 'high', verificationReceipt: receipt(runDir, round, opts), usage: { total: 1 } }
}

async function main() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'defer-confirm-'))
  const seen = []
  global.reviewerAgent = async (_r, _c, _rub, runDir, round, opts) => {
    seen.push({ round, tier: opts && opts.tier, roundKind: opts && opts.roundKind })
    if (round === 1) return blockerResult(runDir, round, opts)
    if (opts && opts.roundKind === 'confirmation') return cleanResult(runDir, round, opts)
    return blockerResult(runDir, round, opts)
  }
  const v = await reviewPanel({
    reviewerSet: ['code'],
    context: {},
    rubric: 'r',
    runKey: dir,
    runDir: dir,
    maxRounds: 7,
    legKind: { panel: true, code: false },
    fixStep: async () => ({
      fixed: [IDENT],
      deferred: [{ id: IDENT, severity: 'Critical' }],
      changedSubjects: ['Code'],
      coverageDecisions: [],
    }),
  })
  const confirmation = seen.filter((x) => x.roundKind === 'confirmation')
  assert.ok(confirmation.length > 0,
    `expected confirmation round after defer-then-intermediate (terminal=${v.terminal} reason=${v.reason})`)
  assert.ok(confirmation.every((x) => x.tier === 'reviewer-deep'))
  assert.strictEqual(v.terminal, 'clean')
  console.log('ok: defer-then-intermediate enters confirmation instead of exiting clean-with-skips')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
