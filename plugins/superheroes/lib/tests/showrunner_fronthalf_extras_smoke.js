// Smoke: a fixStep report's extras.parentOrigin is threaded forward into the subsequent round's
// in-process tally (the D-4 transport). #115: the transport is now IN MEMORY — the round-1 fix sets
// lastExtras, which is persisted to runDir/last-extras.json (so a mid-loop resume reloads it) and
// rides into the round-2 (terminal) verdict's parentOrigin. No round-<N>/extras.json file, no
// --extras command (the tally is an in-process twin, not a panel_tally.py dispatch). Stubs the
// runtime + leaf globals.
const assert = require('assert')
const fs = require('fs')
const os = require('os')
const path = require('path')
const { reviewPanel } = require('../review_panel_shell.js')

const runDir = fs.mkdtempSync(path.join(os.tmpdir(), 'fh-extras-'))

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}
global.synthesisLeaf = async () => []          // keep all merged findings
global.recordDeferred = async () => {}
global.agent = async () => null

// Round 1 flags a blocker (continue); round 2 returns [] (clean). The reviewer RETURNS findings[].
const BLOCKER = [{ file: 'a.py', line: 1, title: 'bug', severity: 'Critical', evidence: 'e' }]
function receipt(runDir, round) {
  return { artifact: `${runDir}:round-${round}`, chain: [{ step: 'citation', evidence: 'e' }, { step: 'reachability', evidence: 'e' }, { step: 'missing-check', evidence: 'e' }, { step: 'tooling', evidence: 'e' }], coverageDecisionIds: [] }
}

async function main() {
  global.reviewerAgent = async (_r, _c, _rub, runDir, round) => {
    if (round === 1) return { findings: BLOCKER, confidence: 'high', verificationReceipt: receipt(runDir, round), usage: { total: 1 } }
    return { findings: [], confidence: 'high', verificationReceipt: receipt(runDir, round), usage: { total: 1 } }
  }
  const fixStep = async () => ({ fixes: [], deferred: [], changedSubjects: ['Code'], coverageDecisions: [], extras: { parentOrigin: 'plan' } })
  const v = await reviewPanel({ reviewerSet: ['code'], context: {}, rubric: 'r',
    runKey: runDir, runDir, fixStep, maxRounds: 7, legKind: { panel: true, code: false } })
  assert.strictEqual(v.terminal, 'clean', 'continue then clean must exit clean')
  // the round-1 fix sets lastExtras; the NEXT (round-2, terminal) verdict carries it.
  assert.strictEqual(v.parentOrigin, 'plan', 'the fix step extras.parentOrigin rides into the terminal verdict')
  // lastExtras is persisted so a mid-loop resume re-loads it (the in-memory transport's durable anchor).
  const extrasFile = path.join(runDir, 'last-extras.json')
  assert.ok(fs.existsSync(extrasFile), 'fix step extras must be persisted to last-extras.json for resume')
  assert.strictEqual(JSON.parse(fs.readFileSync(extrasFile, 'utf8')).parentOrigin, 'plan')
  // NOTE: panel_tally landing parentOrigin in the record + loop_readout rendering "Traces to an
  // upstream phase" are unit-proven by test_panel_tally.py / test_loop_readout.py; this smoke proves
  // the shell TRANSPORT (the previously-missing link), now in-memory.
  console.log('ok: fronthalf extras transport threads parentOrigin into the in-process tally')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
