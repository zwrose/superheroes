// Smoke: a fixStep report's extras.parentOrigin is written to round-<N>/extras.json and forwarded
// to the subsequent panel_tally call (the D-4 transport). Stubs the runtime + leaf globals.
const assert = require('assert')
const fs = require('fs')
const os = require('os')
const path = require('path')
const { reviewPanel } = require('../review_panel_shell.js')

const runDir = fs.mkdtempSync(path.join(os.tmpdir(), 'fh-extras-'))
fs.mkdirSync(path.join(runDir, 'round-1'), { recursive: true })

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}
global.reviewerAgent = async () => true
global.recordDeferred = async () => {}

let tallyCmds = []
let tallyQueue = [
  { schemaVersion: 1, terminal: 'continue', gate: 'blocking', findings: [] },
  { schemaVersion: 1, terminal: 'clean', gate: 'clean' },
]
global.agent = async (prompt, opts) => {
  const label = (opts && opts.label) || ''
  if (label === 'resume') return '1'
  if (label.startsWith('tally')) { tallyCmds.push(prompt); return tallyQueue.shift() }
  return null
}

async function main() {
  // fixStep returns a report carrying extras.parentOrigin (a blocker traced to a parent doc).
  const fixStep = async () => ({ fixes: [], deferred: [], extras: { parentOrigin: 'plan' } })
  const v = await reviewPanel({ reviewerSet: ['code'], context: {}, rubric: 'r',
    runKey: runDir, runDir, fixStep, maxRounds: 7, legKind: {} })
  assert.strictEqual(v.terminal, 'clean', 'continue then clean must exit clean')
  // the round-1 fix sets lastExtras; the NEXT (round-2, terminal) tally writes + forwards it.
  const extrasFile = path.join(runDir, 'round-2', 'extras.json')
  assert.ok(fs.existsSync(extrasFile), 'fix step extras must be persisted for the round-2 tally')
  assert.strictEqual(JSON.parse(fs.readFileSync(extrasFile, 'utf8')).parentOrigin, 'plan')
  // the round-2 (terminal) tally command forwarded --extras into panel_tally (-> terminal record).
  assert.ok(tallyCmds.some((c) => c.includes('--extras')), 'tally must forward --extras after a fix with extras')
  // NOTE: panel_tally landing parentOrigin in the record + loop_readout rendering "Traces to an
  // upstream phase" are unit-proven by test_panel_tally.py / test_loop_readout.py; this smoke proves
  // the shell TRANSPORT (the previously-missing link).
  console.log('ok: fronthalf extras transport forwards parentOrigin to the tally')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
