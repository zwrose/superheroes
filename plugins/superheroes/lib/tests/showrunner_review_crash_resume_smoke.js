// Smoke (#115): the in-memory panel's DURABLE accumulator survives a crash. The only state the panel
// keeps on disk is (a) the per-round accumulator [{round, findings:[{file,title,severity}]}] carrying
// the blocking identities, and (b) the deferred-set. A crash-resume rebuilds the circuit-breaker
// history + the deferred accounting from those two files (fresh in-memory state, SAME runDir) and
// reaches the SAME terminal an uninterrupted run would.
// Run: node plugins/superheroes/lib/tests/showrunner_review_crash_resume_smoke.js
const assert = require('assert')
const fs = require('fs'); const os = require('os'); const path = require('path')
const { reviewPanel } = require('../review_panel_shell.js')
const { findingIdentity } = require('../circuit_breaker.js')

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}
global.synthesisLeaf = async () => []           // keep all merged findings (no drops)
global.agent = async () => null

// One deliberately-skipped (deferred) blocker; once deferred it counts as a present-∩-deferred skip,
// so a round that re-flags only it exits clean-with-skips.
const BLOCKER = { file: 'a.py', line: 3, title: 'bug', severity: 'Critical', evidence: 'e' }
const IDENT = findingIdentity(BLOCKER)          // 'a.py::bug'
function receipt(runDir, round) {
  return { artifact: `${runDir}:round-${round}`, chain: [{ step: 'citation', evidence: 'e' }, { step: 'reachability', evidence: 'e' }, { step: 'missing-check', evidence: 'e' }, { step: 'tooling', evidence: 'e' }], coverageDecisionIds: [] }
}
function blockerResult(runDir, round) {
  return { findings: [{ ...BLOCKER }], confidence: 'high', verificationReceipt: receipt(runDir, round), usage: { total: 1 } }
}

// A recordDeferred that writes the deferred-set to disk exactly as the real consumer leg does (the
// channel the in-process tally reads). Defers every fixed identity at its severity.
function realRecordDeferred() {
  global.recordDeferred = async (report, _verdict, runDir) => {
    const p = `${runDir}/deferred-set.json`
    let set = {}
    try { set = JSON.parse(fs.readFileSync(p, 'utf8')) } catch (_) {}
    for (const d of (report && report.deferred) || []) set[d.id] = d.severity
    fs.writeFileSync(p, JSON.stringify(set))
  }
}

async function main() {
  // --- Reference run (uninterrupted): the deferred blocker -> clean-with-skips at round 2. ---
  realRecordDeferred()
  const refDir = fs.mkdtempSync(path.join(os.tmpdir(), 'resume-ref-'))
  global.reviewerAgent = async (_r, _c, _rub, runDir, round) => blockerResult(runDir, round)
  const ref = await reviewPanel({
    reviewerSet: ['code'], context: {}, rubric: 'r', runKey: refDir, runDir: refDir,
    fixStep: async () => ({ fixed: [IDENT], deferred: [{ id: IDENT, severity: 'Critical' }], changedSubjects: ['Code'], coverageDecisions: [] }),
    maxRounds: 7, legKind: { panel: true, code: false },
  })
  assert.strictEqual(ref.terminal, 'clean-with-skips',
    'reference: a deferred blocker exits clean-with-skips')

  // --- Crash-resume run: seed the disk state a round-1 crash would leave (the accumulator record in
  //     its pinned SHAPE + the recorded deferral), then re-invoke reviewPanel with FRESH in-memory
  //     state but the SAME runDir. It must resume at round 2 and reach the same terminal. ---
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'resume-'))
  // (a) the durable accumulator — pinned SHAPE: a list of {round, findings:[{file,title,severity}]}
  //     carrying round 1's blocking identity.
  fs.writeFileSync(path.join(dir, 'round-records.json'),
    JSON.stringify([{ round: 1, findings: [{ file: 'a.py', title: 'bug', severity: 'Critical' }] }]))
  // (b) the deferred-set: round 1's recorded deferral (the deferred accounting restored from disk).
  fs.writeFileSync(path.join(dir, 'deferred-set.json'), JSON.stringify({ [IDENT]: 'Critical' }))

  realRecordDeferred()
  global.reviewerAgent = async (_r, _c, _rub, runDir, round) => blockerResult(runDir, round)
  const resumed = await reviewPanel({
    reviewerSet: ['code'], context: {}, rubric: 'r', runKey: dir, runDir: dir,
    fixStep: async () => ({ fixed: [IDENT], deferred: [{ id: IDENT, severity: 'Critical' }], changedSubjects: ['Code'], coverageDecisions: [] }),
    maxRounds: 7, legKind: { panel: true, code: false },
  })
  assert.strictEqual(resumed.terminal, ref.terminal,
    'a crash-resume (deferred-set + breaker history restored from disk) reaches the SAME terminal')
  assert.strictEqual(resumed.round, 2, 'the resumed run picks up at round 2 (round 1 restored from disk)')

  // The accumulator now carries both rounds; round 1 is read back in its pinned shape.
  const recs = JSON.parse(fs.readFileSync(path.join(dir, 'round-records.json'), 'utf8'))
  const r1 = recs.find((r) => r.round === 1)
  assert.ok(r1 && Array.isArray(r1.findings) && r1.findings[0].file === 'a.py' &&
    r1.findings[0].severity === 'Critical', 'round-1 accumulator record keeps its {file,title,severity} shape')

  console.log('ok: in-memory panel crash-resume rebuilds deferred-set + breaker history from disk')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
