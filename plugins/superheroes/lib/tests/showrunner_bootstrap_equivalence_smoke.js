// Smoke (#193): resume-equivalence. Seeding the review loop from the entry-bootstrap STUB (blocking
// skeletons + decision scalars) must produce EXACTLY the same behavior as seeding from the full
// load-summary skeleton (every finding, blocking and non-blocking). We prove it two ways over the
// same on-disk history:
//   (A) drive the whole loop once seeded from the full skeleton and once from the stub, and assert
//       identical round scheduling, fix-context generalizeRequired, and terminal/reason;
//   (B) directly compare the pure consumers the seed feeds — the circuit-breaker verdict and the
//       recurrence keys — on the two record forms.
// The two seed forms are produced by the REAL Python verbs (review_memory.py load-summary vs
// entry-bootstrap), so this also guards the stub against the durable skeleton it is derived from.
'use strict'
const assert = require('assert')
const fs = require('fs'); const os = require('os'); const path = require('path')
const { reviewPanel } = require('../review_panel_shell.js')
const { defaultIo } = require('../io_seam.js')
const circuitBreaker = require('../circuit_breaker.js')
const reviewMemory = require('../review_memory.js')

globalThis.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
globalThis.log = () => {}
globalThis.synthesisLeaf = async () => ({ verdicts: [], usage: { total: 1 } })
globalThis.recordDeferred = async () => {}
globalThis.agent = async () => null
globalThis.io = defaultIo

const PY = path.join(__dirname, '..', 'review_memory.py')
const REVIEWERS = ['code', 'security']
const RESUME_ROUND = 3

function receipt(runId, round) {
  return { artifact: `${runId}:round-${round}`, chain: [
    { step: 'citation', evidence: 'c' }, { step: 'reachability', evidence: 'r' },
    { step: 'missing-check', evidence: 'm' }, { step: 'tooling', evidence: 't' }],
    coverageDecisionIds: [] }
}

// A recurring blocking Code finding (same classKey across the two prior rounds) + a chatty pile of
// non-blocking findings the stub drops. security is high-confidence clean and untouched (skip-eligible).
const RECUR = { file: 'a.py', line: 1, title: 'Unbounded loop', severity: 'Critical',
  taxonomy: 'bug', dimension: 'Code', classKey: 'Code::bug::unbounded loop' }
const NOISE = Array.from({ length: 30 }, (_, i) => ({ file: 'n.py', line: i + 1,
  title: `nit ${i} with a verbose chatty body`, severity: 'Minor', taxonomy: 'style', dimension: 'Code',
  evidence: 'z'.repeat(400) }))

function priorRecords() {
  return [1, 2].map((rnd) => ({
    schemaVersion: 2, round: rnd, kind: 'baseline', confirmationPending: false,
    changedSubjects: ['Code'], coverageDecisions: [], tokenUsage: { available: true },
    findings: [Object.assign({}, RECUR)].concat(NOISE), carriedFindings: [],
    dimensions: {
      code: { dimension: 'code', status: 'run', confidence: 'high', round: rnd, tier: 'reviewer-deep',
        subjects: ['Code'], hasFindings: true, findings: [Object.assign({}, RECUR)].concat(NOISE) },
      security: { dimension: 'security', status: 'run', confidence: 'high', round: rnd,
        tier: 'reviewer-deep', subjects: ['Security'], hasFindings: false, findings: [] },
    },
  }))
}

function seedDir() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'boot-equiv-'))
  fs.writeFileSync(path.join(dir, 'round-records.json'), JSON.stringify(priorRecords()))
  fs.writeFileSync(path.join(dir, 'last-extras.json'), JSON.stringify({ changedSubjects: ['Code'] }))
  return dir
}

async function seedMemory(verb, dir) {
  const out = await defaultIo.runHelper('python3', [PY, verb, '--path', path.join(dir, 'round-records.json'),
    '--dimensions', JSON.stringify(REVIEWERS), '--extras-path', path.join(dir, 'last-extras.json')])
  const parsed = JSON.parse(out.stdout)
  assert.ok(parsed.ok && Array.isArray(parsed.records), `${verb} seed failed: ${out.stdout}`)
  return parsed
}

// Run the loop once, seeded from `memory` (a preloaded gather), capturing the observable decisions.
async function runOnce(dir, memory) {
  const schedule = []
  const generalize = []
  globalThis.reviewerAgent = async (reviewer, _c, _rub, runDir, round, opts) => {
    schedule.push(`r${round}:${reviewer}:${opts.tier}`)
    if (reviewer === 'code' && round === RESUME_ROUND) {
      return { findings: [Object.assign({}, RECUR)], confidence: 'high',
        verificationReceipt: receipt(runDir, round), usage: { total: 1 } }
    }
    return { findings: [], confidence: 'high', verificationReceipt: receipt(runDir, round), usage: { total: 1 } }
  }
  const preloaded = {
    ok: true, memory,
    deferredSet: {},
    coverage: { ok: true, decisions: [], contentHash: defaultIo.contentHash('') },
  }
  const v = await reviewPanel({
    reviewerSet: REVIEWERS, context: {}, rubric: 'r', runKey: dir, runDir: dir,
    fixStep: async (fixContext) => {
      generalize.push(JSON.stringify(fixContext.generalizeRequired || []))
      return { fixed: [`${RECUR.file}::${RECUR.title}`], changedSubjects: ['Code'], coverageDecisions: [] }
    },
    maxRounds: 7, legKind: { panel: true, code: false }, preloaded,
  })
  return { schedule, generalize, terminal: v.terminal, reason: v.reason }
}

// The breaker input the shell assembles from the seed's prior rounds (assembleRounds, minus the
// deferred-skip which is empty here).
function breakerInput(records) {
  return (records || []).map((r) => ({
    round: Number(r.round), findings: r.findings || [],
    dimensions: r.dimensions, coverageDecisions: r.coverageDecisions,
  })).sort((a, b) => a.round - b.round)
}

async function main() {
  // (A) full-loop equivalence
  const fullDir = seedDir()
  const stubDir = seedDir()
  const fullMem = await seedMemory('load-summary', fullDir)
  const stubMem = await seedMemory('entry-bootstrap', stubDir)
  // sanity: the two seed forms genuinely differ (stub is smaller, blocking-only)
  assert.ok(JSON.stringify(stubMem.records).length < JSON.stringify(fullMem.records).length,
    'the stub seed must be strictly smaller than the full skeleton seed')
  assert.ok(!JSON.stringify(stubMem.records).includes('nit 0'), 'the stub drops non-blocking prior findings')
  assert.ok(JSON.stringify(fullMem.records).includes('nit 0'), 'the full skeleton keeps non-blocking findings')

  const full = await runOnce(fullDir, fullMem)
  const stub = await runOnce(stubDir, stubMem)
  assert.deepStrictEqual(stub.schedule, full.schedule,
    `round scheduling must match\n full=${JSON.stringify(full.schedule)}\n stub=${JSON.stringify(stub.schedule)}`)
  assert.deepStrictEqual(stub.generalize, full.generalize,
    `fix-context generalizeRequired must match\n full=${JSON.stringify(full.generalize)}\n stub=${JSON.stringify(stub.generalize)}`)
  assert.strictEqual(stub.terminal, full.terminal, `terminal must match (full=${full.terminal}, stub=${stub.terminal})`)
  assert.strictEqual(stub.reason, full.reason, `reason must match (full=${full.reason}, stub=${stub.reason})`)
  // the fix actually ran, so generalizeRequired was genuinely exercised (not a vacuous [] == [])
  assert.ok(full.generalize.length >= 1 && full.generalize[0] !== '[]',
    `generalizeRequired must be non-trivially exercised, got ${JSON.stringify(full.generalize)}`)

  // (B) direct consumer equivalence over the two seed forms
  const fullBrk = circuitBreaker.checkCircuitBreaker(breakerInput(fullMem.records), 7)
  const stubBrk = circuitBreaker.checkCircuitBreaker(breakerInput(stubMem.records), 7)
  assert.deepStrictEqual(stubBrk, fullBrk, 'circuit-breaker verdict must match on the two seed forms')
  const fullRec = reviewMemory.recurrentClasses(fullMem.records, [])
  const stubRec = reviewMemory.recurrentClasses(stubMem.records, [])
  assert.deepStrictEqual(stubRec, fullRec, 'recurrence keys must match on the two seed forms')
  assert.ok(fullRec.length >= 1, 'the fixture must genuinely produce a recurrence key')

  console.log('ok: bootstrap-seeded resume is behavior-equivalent to full-skeleton seeding (#193)')
}

main().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
