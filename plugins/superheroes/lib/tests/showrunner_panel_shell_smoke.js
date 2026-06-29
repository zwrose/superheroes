// Smoke: the in-memory loop shell's control flow (#115) — fail-closed sentinel (UFR-9) + clean
// passthrough + continue->fix->clean loop + failed-fix->halted. Reviewer leaves RETURN findings[];
// merge/synthesis-consume/tally are in-process parity-locked twin calls (no panel_tally.py / tally
// agent). Stubs the Workflow runtime + caller-supplied leaf globals. Local gate (CI runs pytest, not
// JS). Run: node plugins/superheroes/lib/tests/showrunner_panel_shell_smoke.js
const assert = require('assert')
const fs = require('fs'); const os = require('os'); const path = require('path')
const { reviewPanel } = require('../review_panel_shell.js')
const panelTally = require('../panel_tally.js')

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}

// A fresh on-disk runDir per scenario so the durable accumulator + deferred-set never leak across cases.
function freshDir() { return fs.mkdtempSync(path.join(os.tmpdir(), 'panelshell-')) }

// The synthesis leaf (panel leg) RETURNS keep/drop verdicts; here it keeps everything (empty verdicts
// -> loop_synthesis.consume keeps all at their pre-synthesis severity).
global.synthesisLeaf = async () => []
global.recordDeferred = async () => {}    // deferral writer no-op (fixStep success path)
// No tally agent any more; only the doc/verify-less panel leg here, so agent() is rarely hit.
global.agent = async () => null

const BLOCKER = [{ file: 'a.py', line: 1, title: 'bug', severity: 'Critical', evidence: 'x' }]

function base(dir) {
  return {
    reviewerSet: ['code'], context: {}, rubric: 'r', runKey: dir, runDir: dir,
    fixStep: async () => ({ fixed: [] }), maxRounds: 7, legKind: { panel: true, code: false },
  }
}

async function main() {
  // 1. Sentinel (UFR-9): the in-process tally yields no usable verdict -> fail closed, never clean.
  //    Force decideTerminal to return a terminal-less object so the shell's _usable() guard fires.
  const realDecide = panelTally.decideTerminal
  panelTally.decideTerminal = () => ({})        // no `terminal` -> verdict unusable
  global.reviewerAgent = async () => []
  let v = await reviewPanel({ ...base(freshDir()) })
  assert.strictEqual(v.terminal, 'halted', 'unusable tally must fail closed to halted')
  assert.strictEqual(v.recordMissing, true, 'unusable tally must flag recordMissing')
  panelTally.decideTerminal = realDecide        // restore the real twin

  // 2. Clean passthrough: a clean round (no findings) -> clean.
  global.reviewerAgent = async () => []
  v = await reviewPanel({ ...base(freshDir()) })
  assert.strictEqual(v.terminal, 'clean', 'a clean round passes through to clean')

  // 3. continue -> fix -> re-review -> clean (the loop's one branch). Round 1 reviewer flags a
  //    blocker (continue); the fix resolves it; round 2 reviewer returns [] -> clean.
  {
    let round = 0
    global.reviewerAgent = async () => { round += 1; return round === 1 ? BLOCKER : [] }
    v = await reviewPanel({ ...base(freshDir()), fixStep: async () => ({ fixed: ['a.py::bug'] }) })
    assert.strictEqual(v.terminal, 'clean', 'continue then clean must loop once then exit clean')
  }

  // 4. fix step fails -> the shell re-tallies with fixStatus 'failed' (the core decides halted).
  global.reviewerAgent = async () => BLOCKER
  v = await reviewPanel({ ...base(freshDir()), fixStep: async () => null })  // null report => fix failure
  assert.strictEqual(v.terminal, 'halted', 'a failed fix step re-tallies and yields halted')

  // 5. extras seam (#104 threaded design): a prior fix's extras, persisted to runDir/last-extras.json,
  //    is reloaded on entry and threaded into the round's verdict (parentOrigin rides to the readout).
  {
    const dir = freshDir()
    fs.writeFileSync(path.join(dir, 'last-extras.json'), JSON.stringify({ parentOrigin: 'plan' }))
    global.reviewerAgent = async () => []
    v = await reviewPanel({ ...base(dir) })
    assert.strictEqual(v.parentOrigin, 'plan', 'the reloaded extras.parentOrigin rides into the verdict')
  }

  // 6. durable accumulator: one cheap write per round records the round's compiled findings (carrying
  //    the blocking identities) so a crash-resume can rebuild the breaker history.
  {
    const dir = freshDir()
    global.reviewerAgent = async () => []
    await reviewPanel({ ...base(dir) })
    const recs = JSON.parse(fs.readFileSync(path.join(dir, 'round-records.json'), 'utf8'))
    assert.ok(Array.isArray(recs) && recs.length === 1 && recs[0].round === 1,
      'one durable accumulator record is written for the round')
  }

  // 7. verifyAgent boundary coercion: a courier leaf returning stringified returncode/timedOut fields
  //    (returncode:'0', timedOut:'false') must be classified as 'pass', not 'timeout'.
  //    Before fix: timedOut='false' was truthy -> 'timeout' -> halted (even though verify passed).
  //    After fix: boundary coercion normalises to boolean false + number 0 -> 'pass' -> clean.
  {
    const dir = freshDir()
    global.reviewerAgent = async () => []
    // The code leg's verifyAgent dispatches an `agent()` call with label starting 'verify:'.
    // Override agent to return stringified fields as the courier would.
    const prevAgent = global.agent
    global.agent = async (prompt, opts) => {
      if (opts && opts.label && opts.label.startsWith('verify:')) {
        return { command: 'run-tests', returncode: '0', timedOut: 'false' }  // courier-stringified
      }
      return null
    }
    v = await reviewPanel({ ...base(dir), legKind: { panel: false, code: true }, verifyCommand: 'run-tests' })
    global.agent = prevAgent
    assert.strictEqual(v.terminal, 'clean',
      'verifyAgent: courier-stringified returncode:"0" timedOut:"false" must classify as pass -> clean (not timeout -> halted)')
  }

  console.log('ok: in-memory loop shell sentinel + passthrough + continue/fix/clean + extras + accumulator + verify-coercion')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
