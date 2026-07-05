// Smoke (#211 Phase 4c — the ADVERSARIAL proof): the whole point of "decisions ride up, pointers
// ride down, content stays on disk" is that a courier that mangles or refuses a large answer can no
// longer break the loop, because nothing large crosses anymore — while a courier that mangles a
// SMALL decider answer must fail CLOSED (cannot-certify / halted), never silently wrong.
//
//   (A) an ioApi shim that mangles EVERY courier answer larger than 4 KB → the clean loop still
//       converges (no courier answer is that big under this architecture).
//   (B) an ioApi shim that mangles the small tally-round decider answer → the loop halts closed
//       (_failClosed: recordMissing), never certifies clean.
//   (C) an ioApi shim that mangles the small plan-round decider answer → the loop parks
//       round-plan-unreadable, never certifies clean.
'use strict'
const assert = require('assert')
const fs = require('fs'); const os = require('os'); const path = require('path')
const { reviewPanel } = require('../review_panel_shell.js')
const { defaultIo } = require('../io_seam.js')

globalThis.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
globalThis.log = () => {}
globalThis.synthesisLeaf = async () => ({ verdicts: [], usage: { total: 1 } })
globalThis.recordDeferred = async () => {}
globalThis.agent = async () => null

function receipt(runId, round) {
  return { artifact: `${runId}:round-${round}`, chain: [
    { step: 'citation', evidence: 'c' }, { step: 'reachability', evidence: 'r' },
    { step: 'missing-check', evidence: 'm' }, { step: 'tooling', evidence: 't' }],
    coverageDecisionIds: [] }
}
function freshDir() { return fs.mkdtempSync(path.join(os.tmpdir(), 'adversarial-')) }
function base(dir) {
  return {
    reviewerSet: ['code'], context: {}, rubric: 'r', runKey: dir, runDir: dir,
    fixStep: async () => ({ fixed: [], changedSubjects: ['Code'], coverageDecisions: [] }),
    maxRounds: 7, legKind: { panel: true, code: false },
  }
}

async function main() {
  globalThis.reviewerAgent = async (_r, _c, _rub, runDir, round) =>
    ({ findings: [], confidence: 'high', verificationReceipt: receipt(runDir, round), usage: { total: 1 } })

  // (A) mangle every courier answer > 4 KB — the clean loop still converges, because no courier
  // answer is that large under this architecture (findings never ride a courier answer).
  {
    const dir = freshDir()
    let mangledBig = 0
    globalThis.io = Object.assign({}, defaultIo, {
      async runHelper(cmd, args) {
        const out = await defaultIo.runHelper(cmd, args)
        if ((out.stdout || '').length > 4096) { mangledBig += 1; return { ok: true, stdout: 'X'.repeat(9000) } }
        return out
      },
    })
    const v = await reviewPanel({ ...base(dir) })
    globalThis.io = undefined
    assert.strictEqual(v.terminal, 'clean',
      `mangling only >4KB answers must not break the loop — nothing that big crosses (got ${v.terminal}/${v.reason})`)
    assert.strictEqual(mangledBig, 0, `no courier answer should have been >4KB (mangled ${mangledBig})`)
  }

  // (B) mangle the small tally-round decider answer → fail closed (halted / recordMissing), never clean.
  {
    const dir = freshDir()
    globalThis.io = Object.assign({}, defaultIo, {
      async runHelper(cmd, args) {
        if (String((args || [])[0]).includes('review_loop_plan.py') && (args || []).includes('tally-round')) {
          return { ok: true, stdout: 'courier refused: appears to violate policy' }
        }
        return defaultIo.runHelper(cmd, args)
      },
    })
    const v = await reviewPanel({ ...base(dir) })
    globalThis.io = undefined
    assert.notStrictEqual(v.terminal, 'clean', 'a mangled tally decider answer must NEVER certify clean')
    assert.strictEqual(v.terminal, 'halted', `a mangled tally answer fails closed to halted (got ${v.terminal})`)
    assert.strictEqual(v.recordMissing, true, 'the fail-closed sentinel flags recordMissing')
  }

  // (C) mangle the small plan-round decider answer → park round-plan-unreadable, never clean. Round 1
  // fixes a blocker (its plan folds into the gather, unaffected); round 2 uses the standalone
  // plan-round leaf, which the shim mangles → the shell parks fail-closed on the next round's schedule.
  {
    const dir = freshDir()
    let planCalls = 0
    globalThis.io = Object.assign({}, defaultIo, {
      async runHelper(cmd, args) {
        if (String((args || [])[0]).includes('review_loop_plan.py') && (args || []).includes('plan-round')) {
          planCalls += 1
          return { ok: true, stdout: 'mangled plan' }
        }
        return defaultIo.runHelper(cmd, args)
      },
    })
    globalThis.reviewerAgent = async (_r, _c, _rub, runDir, r) => (r === 1
      ? { findings: [{ file: 'a.py', line: 1, title: 'bug', severity: 'Critical', dimension: 'Code' }],
          confidence: 'high', verificationReceipt: receipt(runDir, r), usage: { total: 1 } }
      : { findings: [], confidence: 'high', verificationReceipt: receipt(runDir, r), usage: { total: 1 } })
    const v = await reviewPanel({ ...base(dir), fixStep: async () => ({ fixed: ['a.py::bug'], changedSubjects: ['Code'], coverageDecisions: [] }) })
    globalThis.io = undefined
    assert.notStrictEqual(v.terminal, 'clean', 'a mangled plan decider answer must NEVER certify clean')
    assert.match(v.reason || '', /round-plan-unreadable/, `a mangled plan answer parks round-plan-unreadable (got ${v.reason})`)
    assert.ok(planCalls >= 2, `the mangled plan-round leaf was retried once before parking (got ${planCalls})`)
  }

  console.log('ok: >4KB mangling never breaks the loop; mangled small decider answers fail closed (#211 Phase 4c)')
}

main().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
