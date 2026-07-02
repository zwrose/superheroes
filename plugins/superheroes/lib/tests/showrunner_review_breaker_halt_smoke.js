// Smoke (#115): the in-memory panel's INTERNAL circuit breaker halts on a recurring blocking finding.
// Drives the real reviewPanel shell + the parity-locked twins over a concrete identity sequence where
// the SAME file::normalized-title blocking finding is present in two consecutive rounds (the
// `recurring-finding` criterion — circuit_breaker.py:53-55 — NOT a max-iterations halt). Pins the
// recurrence path: verdict.terminal === 'halted' AND verdict.reason matches /recurr/i.
// Run: node plugins/superheroes/lib/tests/showrunner_review_breaker_halt_smoke.js
const assert = require('assert')
const fs = require('fs'); const os = require('os'); const path = require('path')
const { reviewPanel } = require('../review_panel_shell.js')

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}
global.synthesisLeaf = async () => []           // keep all merged findings (no drops)
global.recordDeferred = async () => {}          // the blocker is NEVER deferred -> not skip-excluded
global.agent = async () => null

// The SAME blocking finding identity (a.py::recurring bug) recurs round after round despite a
// "successful" fix each round — exactly the stuck loop the breaker exists to stop.
const RECURRING = [{ file: 'a.py', line: 7, title: 'Recurring Bug', severity: 'Critical', evidence: 'e' }]
function receipt(runDir, round) {
  return { artifact: `${runDir}:round-${round}`, chain: [{ step: 'citation', evidence: 'e' }, { step: 'reachability', evidence: 'e' }, { step: 'missing-check', evidence: 'e' }, { step: 'tooling', evidence: 'e' }], coverageDecisionIds: [] }
}

async function main() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'breaker-'))
  global.reviewerAgent = async (_r, _c, _rub, runDir, round) => ({
    findings: RECURRING, confidence: 'high', verificationReceipt: receipt(runDir, round), usage: { total: 1 },
  })
  const verdict = await reviewPanel({
    reviewerSet: ['code'], context: {}, rubric: 'r', runKey: dir, runDir: dir,
    fixStep: async () => ({ fixed: ['a.py::recurring bug'], changedSubjects: ['Code'], coverageDecisions: [] }),
    maxRounds: 7, legKind: { panel: true, code: false },
  })
  assert.strictEqual(verdict.terminal, 'halted', 'a recurring blocking finding must halt the loop')
  assert.ok(/recurr/i.test(verdict.reason || ''),
    `the halt reason must name the recurrence (got: ${verdict.reason})`)

  // It halted on RECURRENCE, not on max-iterations: it stopped at round 2 (>= 2 rounds), well under
  // maxRounds=7. The durable accumulator should therefore hold exactly two round records.
  const recs = JSON.parse(fs.readFileSync(path.join(dir, 'round-records.json'), 'utf8'))
  assert.strictEqual(recs.length, 2, 'recurrence halts at round 2, not at the max-iterations cap')

  console.log('ok: in-memory panel circuit breaker halts on a recurring finding (recurring-finding)')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
