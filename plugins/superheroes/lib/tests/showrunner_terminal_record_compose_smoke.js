// Smoke: the loop's terminal-record write survives a byte-dropping courier (live 2026-07-02,
// run wf_94c879e0-747: at review-loop finalize the FULL verdict (~14KB, evidence-bodied
// findings) was staged through ONE haiku courier writeFile; the courier dropped bytes, the
// Python-side --payload-hash refused the mangled stage, and the phase parked
// terminal-record.json payload-stage-failed — the durable terminal record was lost).
//
// The fix (same shape as #136 compose-persist): compose the terminal record PYTHON-SIDE from
// state already on disk (round-records.json + review-telemetry.json) with only small verdict
// scalars riding inline (self-verified), so no oversized blob ever crosses the courier.
//
// This drives a courier whose writeFile TRUNCATES any staged blob over 8KB (the observed
// byte-drop class), then contrasts:
//   (OLD) fencedJsonWrite of the full >12KB verdict — RED: the staged payload is truncated, the
//         Python hash-check refuses it, the write fails closed (the live park).
//   (NEW) writeTerminalRecord — GREEN: the big fields (evidence-bodied findings +
//         fixes/deferred/coverage) never ride writeFile at all; compose-terminal reads them from
//         disk and writes in-process, so the record lands correct and complete.
'use strict'
const assert = require('assert')
const fs = require('fs')
const os = require('os')
const path = require('path')
const { fencedJsonWrite, writeTerminalRecord } = require('../fenced_json.js')
const { defaultIo } = require('../io_seam.js')

const TRUNCATE_OVER = 8192   // the courier drops bytes past ~8KB

// A courier io: real disk for everything EXCEPT writeFile, which truncates an oversized staged
// blob exactly the way the live haiku courier did (writeFile reports no error — the corruption is
// silent, caught only by the Python-side hash check). runHelper is the REAL python3 subprocess.
// Both staging seams are wrapped: writeFile and — since #141 folded the fenced write into one leaf
// — stageAndRunHelper (the seam fencedJsonWrite stages through now). Either truncates an oversized
// staged blob exactly the way the live courier did.
const stagedCalls = []
function truncatingStage(p, text) {
  const t = typeof text === 'string' ? text : JSON.stringify(text)
  stagedCalls.push({ path: p, size: t.length, truncated: t.length > TRUNCATE_OVER })
  const dir = String(p).slice(0, String(p).lastIndexOf('/'))
  if (dir) fs.mkdirSync(dir, { recursive: true })
  fs.writeFileSync(p, t.length > TRUNCATE_OVER ? t.slice(0, TRUNCATE_OVER) : t)
}
globalThis.io = Object.assign({}, defaultIo, {
  async writeFile(p, s) { truncatingStage(p, s) },
  async stageAndRunHelper(stagedPath, text, cmd, args) {
    truncatingStage(stagedPath, text)   // the courier byte-drops the oversized staged blob...
    return defaultIo.runHelper(cmd, args)   // ...then the REAL helper's --payload-hash refuses it
  },
})

const BIG_EVIDENCE = 'E'.repeat(2048)
const BIG_FINDINGS = Array.from({ length: 60 }, (_, i) => ({
  file: 'a.py', line: i + 1, title: `finding ${i}`, severity: 'Critical', taxonomy: 'bug',
  evidence: BIG_EVIDENCE,
}))

function roundRecord(round, fixes, deferred, coverage) {
  return {
    schemaVersion: 2, round, kind: 'baseline', confirmationPending: false,
    changedSubjects: ['Code'], coverageDecisions: coverage,
    tokenUsage: { [`code:r${round}`]: { total: 3 } },
    findings: BIG_FINDINGS, carriedFindings: [],
    fix: { fixes, deferred },
    dimensions: { code: { dimension: 'code', status: 'run', round } },
  }
}

async function main() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'terminal-compose-'))
  // The durable loop state Python already wrote to disk (atomic os.replace — never the courier):
  fs.writeFileSync(path.join(dir, 'round-records.json'), JSON.stringify([
    roundRecord(1, ['a.py::finding 0'],
      [{ identity: 'a.py::finding 0', severity: 'Critical', reason: 'out of scope' }],
      [{ id: 'cd-1', classKey: 'k1' }]),
    roundRecord(2, ['b.py::finding 1'], [], [{ id: 'cd-1', classKey: 'k1' }, { id: 'cd-2', classKey: 'k2' }]),
  ]))
  fs.writeFileSync(path.join(dir, 'review-telemetry.json'), JSON.stringify({
    schemaVersion: 1, terminal: 'clean', roundCount: 2,
    tokenUsage: { complete: true, total: 42, missing: [] },
    dimensionCounts: { code: { run: 2 } }, benchmarkValid: true, runId: 'telem', lease: 'L',
  }))

  // The in-memory verdict finalize holds: evidence-bodied findings + the synthesis outputs.
  const verdict = {
    schemaVersion: 1, terminal: 'clean', reason: 'all good', round: 2, gate: 'clean',
    drops: [{ id: 'c.py::finding 9', title: 'spurious', reason: 'unsubstantiated' }],
    findings: BIG_FINDINGS,
    fixes: ['a.py::finding 0', 'b.py::finding 1'],
    deferred: [{ identity: 'a.py::finding 0', severity: 'Critical', reason: 'out of scope' }],
    coverageDecisions: [{ id: 'cd-1', classKey: 'k1' }, { id: 'cd-2', classKey: 'k2' }],
    telemetry: { benchmarkValid: true, roundCount: 2 },
  }
  const RECORD_SIZE = JSON.stringify(verdict).length
  assert.ok(RECORD_SIZE > 12 * 1024, `the verdict must be >12KB (is ${RECORD_SIZE}B) to exercise the truncation`)

  // (OLD) the pre-fix path: stage the whole verdict through the courier (fencedJsonWrite → the
  // #141 one-leaf stageAndRunHelper). The truncating courier corrupts the >12KB staged payload;
  // fenced_json.py's --payload-hash refuses it and the write fails closed — the live
  // payload-stage-failed park.
  stagedCalls.length = 0
  const oldPath = path.join(dir, 'terminal-record-old.json')
  const wOld = await fencedJsonWrite(oldPath, verdict, { overwrite: true, runId: 'run-old' })
  assert.strictEqual(wOld.ok, false,
    'OLD path must fail under a byte-dropping courier (the live payload-stage-failed park)')
  assert.ok(stagedCalls.some((c) => c.truncated),
    'OLD path staged an oversized blob that the courier truncated')
  assert.ok(!fs.existsSync(oldPath), 'OLD path leaves no terminal record on disk (the durable record is lost)')

  // (NEW) writeTerminalRecord: the big fields never touch a staged write. compose-terminal reads
  // fixes/deferred/coverage from round-records.json and telemetry from review-telemetry.json,
  // takes only the small scalars inline, and writes in-process — so it lands under the same courier.
  stagedCalls.length = 0
  const newPath = path.join(dir, 'terminal-record.json')
  const wNew = await writeTerminalRecord(newPath, verdict, { runId: 'run-new', runDir: dir, lease: 'L2' })
  assert.strictEqual(wNew.ok, true, `NEW path must survive the courier: ${JSON.stringify(wNew)}`)
  assert.ok(!stagedCalls.some((c) => c.truncated),
    'NEW path must never stage an oversized blob through the courier')

  const text = fs.readFileSync(newPath, 'utf8')
  assert.strictEqual(wNew.contentHash, defaultIo.contentHash(text), 'the answer carries the on-disk contentHash')
  const rec = JSON.parse(text)
  assert.strictEqual(rec.terminal, 'clean')
  assert.strictEqual(rec.reason, 'all good')
  assert.strictEqual(rec.round, 2)
  assert.strictEqual(rec.gate, 'clean')
  assert.strictEqual(rec.drops[0].title, 'spurious')
  // the evidence-bodied findings never enter the terminal record
  assert.ok(!('findings' in rec), 'the terminal record must not carry the evidence-bodied findings')
  assert.ok(!text.includes(BIG_EVIDENCE), 'no evidence body may ride into the terminal record')
  // the readout content is composed from disk, complete
  assert.deepStrictEqual(rec.fixes, ['a.py::finding 0', 'b.py::finding 1'], 'fixes are the union across rounds')
  assert.deepStrictEqual(rec.deferred.map((d) => d.identity), ['a.py::finding 0'])
  assert.deepStrictEqual(rec.coverageDecisions.map((c) => c.id), ['cd-1', 'cd-2'])
  assert.strictEqual(rec.telemetry.roundCount, 2, 'telemetry is the on-disk summary')
  assert.strictEqual(rec.telemetry.tokenUsage.total, 42)
  assert.strictEqual(rec.runId, 'run-new')
  assert.strictEqual(rec.lease, 'L2')

  console.log('ok: terminal-record write survives a byte-dropping courier (compose-terminal, no mega blob staged)')
}

main().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
