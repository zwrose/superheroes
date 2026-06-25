// Smoke: the loop shell's control flow — fail-closed sentinel (UFR-9) + clean passthrough +
// continue->fix->clean loop. Stubs the Workflow runtime + caller-supplied leaf globals. Local
// gate (CI runs pytest, not JS). Run: node plugins/superheroes/lib/tests/showrunner_panel_shell_smoke.js
const assert = require('assert')
const { reviewPanel } = require('../review_panel_shell.js')

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}
global.reviewerAgent = async () => true   // reviewer "completed"
global.recordDeferred = async () => {}    // deferral writer no-op

let tallyQueue = []
global.agent = async (prompt, opts) => {
  const label = (opts && opts.label) || ''
  if (label === 'resume') return '1'
  if (label.startsWith('tally')) return tallyQueue.shift()
  return null
}

const base = { reviewerSet: ['code'], context: {}, rubric: 'r', runKey: '/tmp/x', runDir: '/tmp/x',
               fixStep: async () => ({ fixed: [] }), maxRounds: 7, legKind: {} }

async function main() {
  // 1. Sentinel: the tally process returns nothing -> fail closed, never clean (UFR-9).
  tallyQueue = [null]
  let v = await reviewPanel({ ...base })
  assert.strictEqual(v.terminal, 'halted', 'null tally must fail closed to halted')
  assert.strictEqual(v.recordMissing, true, 'null tally must flag recordMissing')

  // 2. Clean passthrough: a clean verdict is returned as-is.
  tallyQueue = [{ schemaVersion: 1, terminal: 'clean', gate: 'clean' }]
  v = await reviewPanel({ ...base })
  assert.strictEqual(v.terminal, 'clean', 'clean verdict must pass through')

  // 3. continue -> fix -> re-tally -> clean (the loop's one branch).
  tallyQueue = [{ schemaVersion: 1, terminal: 'continue', gate: 'blocking', findings: [] },
                { schemaVersion: 1, terminal: 'clean', gate: 'clean' }]
  v = await reviewPanel({ ...base })
  assert.strictEqual(v.terminal, 'clean', 'continue then clean must loop once then exit clean')

  // 4. fix step fails -> the shell re-tallies with fixStatus 'failed' (the core decides halted).
  tallyQueue = [{ schemaVersion: 1, terminal: 'continue', gate: 'blocking', findings: [] },
                { schemaVersion: 1, terminal: 'halted', gate: 'blocking', reason: 'fix failed' }]
  v = await reviewPanel({ ...base, fixStep: async () => null })  // null report => fix failure
  assert.strictEqual(v.terminal, 'halted', 'a failed fix step re-tallies and yields halted')

  // 5. extras seam: when runDir/extras.json exists, the tally command forwards --extras <path>.
  const fs = require('fs'); const os = require('os'); const path = require('path')
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'panelshell-'))
  fs.writeFileSync(path.join(dir, 'extras.json'), JSON.stringify({ parentOrigin: 'plan' }))
  let seenCmd = ''
  global.agent = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label.startsWith('tally')) { seenCmd = prompt; return { schemaVersion: 1, terminal: 'clean', gate: 'clean' } }
    if (label === 'resume') return '1'
    return null
  }
  await reviewPanel({ ...base, runKey: dir, runDir: dir })
  assert.ok(seenCmd.includes('--extras') && seenCmd.includes(path.join(dir, 'extras.json')),
    'tally must forward --extras <runDir>/extras.json when it exists')

  console.log('ok: loop shell sentinel + passthrough + continue/fix/clean + extras seam')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
