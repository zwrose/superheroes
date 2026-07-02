// Smoke: the in-memory loop shell's control flow (#115) — fail-closed sentinel (UFR-9) + clean
// passthrough + continue->fix->clean loop + failed-fix->halted. Reviewer leaves RETURN findings[];
// merge/synthesis-consume/tally are in-process parity-locked twin calls (no panel_tally.py / tally
// agent). Stubs the Workflow runtime + caller-supplied leaf globals. Local gate (CI runs pytest, not
// JS). Run: node plugins/superheroes/lib/tests/showrunner_panel_shell_smoke.js
const assert = require('assert')
const fs = require('fs'); const os = require('os'); const path = require('path')
const { reviewPanel } = require('../review_panel_shell.js')
const { io } = require('../io_seam.js')
const panelTally = require('../panel_tally.js')

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}

function freshDir() { return fs.mkdtempSync(path.join(os.tmpdir(), 'panelshell-')) }

global.synthesisLeaf = async () => ({ verdicts: [], usage: { total: 1 } })
global.recordDeferred = async () => {}
global.agent = async () => null

const BLOCKER = [{ file: 'a.py', line: 1, title: 'bug', severity: 'Critical', evidence: 'x' }]
const COVERAGE_BLOCKER = [{ dimension: 'Test', taxonomy: 'coverage', title: 'Missing acceptance test', severity: 'Important', evidence: 'x' }]

function receipt(runId, round, opts = {}) {
  return { artifact: `${runId}:round-${round}`, chain: [{ step: 'citation', evidence: 'reviewed citations' }, { step: 'reachability', evidence: 'validated call path' }, { step: 'missing-check', evidence: 'checked missing FRs' }, { step: 'tooling', evidence: 'smoke passed' }], coverageDecisionIds: ((opts.coverageDecisions || []).map((d) => d.id).filter(Boolean)) }
}

function cleanResult(runDir, round, opts = {}) {
  return { findings: [], confidence: 'high', verificationReceipt: receipt(runDir, round, opts), usage: { total: 1 } }
}

function blockerResult(runDir, round, opts = {}) {
  return { findings: BLOCKER, confidence: 'high', verificationReceipt: receipt(runDir, round, opts), usage: { total: 1 } }
}

function base(dir) {
  return {
    reviewerSet: ['code'], context: {}, rubric: 'r', runKey: dir, runDir: dir,
    fixStep: async () => ({ fixed: [], changedSubjects: ['Code'], coverageDecisions: [] }), maxRounds: 7, legKind: { panel: true, code: false },
  }
}

async function main() {
  const realDecide = panelTally.decideTerminal
  panelTally.decideTerminal = () => ({})
  global.reviewerAgent = async () => cleanResult('x', 1)
  let v = await reviewPanel({ ...base(freshDir()) })
  assert.strictEqual(v.terminal, 'halted', 'unusable tally must fail closed to halted')
  assert.strictEqual(v.recordMissing, true, 'unusable tally must flag recordMissing')
  panelTally.decideTerminal = realDecide

  {
    const dir = freshDir()
    global.reviewerAgent = async (_r, _c, _rub, runDir, round, opts) => cleanResult(runDir, round, opts)
    v = await reviewPanel({ ...base(dir) })
    assert.strictEqual(v.terminal, 'clean', 'a clean round passes through to clean')
  }

  {
    const dir = freshDir()
    let round = 0
    global.reviewerAgent = async (_r, _c, _rub, runDir, r, opts) => {
      round += 1
      return round === 1 ? blockerResult(runDir, r, opts) : cleanResult(runDir, r, opts)
    }
    v = await reviewPanel({ ...base(dir), fixStep: async () => ({ fixed: ['a.py::bug'], changedSubjects: ['Code'], coverageDecisions: [] }) })
    assert.strictEqual(v.terminal, 'clean', 'continue then clean must loop once then exit clean')
  }

  {
    const dir = freshDir()
    global.reviewerAgent = async (_r, _c, _rub, runDir, round, opts) => blockerResult(runDir, round, opts)
    v = await reviewPanel({ ...base(dir), fixStep: async () => null })
    assert.strictEqual(v.terminal, 'halted', 'a failed fix step re-tallies and yields halted')
  }

  {
    const dir = freshDir()
    fs.writeFileSync(path.join(dir, 'last-extras.json'), JSON.stringify({ parentOrigin: 'plan' }))
    global.reviewerAgent = async (_r, _c, _rub, runDir, round, opts) => cleanResult(runDir, round, opts)
    v = await reviewPanel({ ...base(dir) })
    assert.strictEqual(v.parentOrigin, 'plan', 'the reloaded extras.parentOrigin rides into the verdict')
  }

  {
    const dir = freshDir()
    global.reviewerAgent = async (_r, _c, _rub, runDir, round, opts) => cleanResult(runDir, round, opts)
    await reviewPanel({ ...base(dir) })
    const recs = JSON.parse(fs.readFileSync(path.join(dir, 'round-records.json'), 'utf8'))
    assert.ok(Array.isArray(recs) && recs.length === 1 && recs[0].round === 1,
      'one durable accumulator record is written for the round')
  }

  {
    const dir = freshDir()
    global.reviewerAgent = async (_r, _c, _rub, runDir, round, opts) => cleanResult(runDir, round, opts)
    const prevAgent = global.agent
    global.agent = async (prompt, opts) => {
      if (opts && opts.label === 'run verify') {
        return { command: 'run-tests', returncode: '0', timedOut: 'false' }  // courier-stringified
      }
      return null
    }
    v = await reviewPanel({ ...base(dir), legKind: { panel: false, code: true }, verifyCommand: 'run-tests' })
    global.agent = prevAgent
    assert.strictEqual(v.terminal, 'clean',
      'verifyAgent: courier-stringified returncode:"0" timedOut:"false" must classify as pass -> clean (not timeout -> halted)')
  }

  {
    const dir = freshDir()
    const seen = []
    const fixRounds = []
    let calls = 0
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => {
      seen.push({ reviewer, round, tier: opts && opts.tier, kind: opts && opts.roundKind })
      calls += 1
      if (calls === 1) return blockerResult(runDir, round, opts)
      return cleanResult(runDir, round, opts)
    }
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer', 'security-reviewer'], fixStep: async (_ctx, verdict) => { fixRounds.push(verdict.round); return { fixed: ['bug'], changedSubjects: ['Test'], coverageDecisions: [] } } })
    assert.strictEqual(v.terminal, 'clean')
    const confirmation = seen.filter((x) => x.kind === 'confirmation')
    assert.deepStrictEqual(confirmation.map((x) => x.reviewer).sort(), ['security-reviewer', 'test-reviewer'])
    assert.ok(confirmation.every((x) => x.tier === 'reviewer-deep'))
    const finalRound = Math.max(...confirmation.map((x) => x.round))
    assert.ok(fixRounds.every((r) => r < finalRound))
  }

  {
    const dir = freshDir()
    global.reviewerAgent = async () => ({ findings: [], confidence: 'high' })
    v = await reviewPanel({ ...base(dir), reviewerSet: ['code-reviewer'], legKind: { panel: true, code: false } })
    assert.strictEqual(v.terminal, 'clean')
  }

  {
    const dir = freshDir()
    let first = true
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => {
      if (first) {
        first = false
        return blockerResult(runDir, round, opts)
      }
      return { findings: [], confidence: 'high' }
    }
    v = await reviewPanel({ ...base(dir), reviewerSet: ['code-reviewer'], legKind: { panel: true, code: false }, fixStep: async () => ({ changedSubjects: ['Code'], coverageDecisions: [] }) })
    assert.notStrictEqual(v.terminal, 'clean')
  }

  {
    const dir = freshDir()
    let first = true
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => {
      if (first) {
        first = false
        return blockerResult(runDir, round, opts)
      }
      return { findings: [], confidence: 'high', verificationReceipt: Object.assign(receipt(runDir, round, opts), { artifact: 'old-run:round-9' }) }
    }
    v = await reviewPanel({ ...base(dir), reviewerSet: ['code-reviewer'], legKind: { panel: true, code: false }, fixStep: async () => ({ changedSubjects: ['Code'], coverageDecisions: [] }) })
    assert.notStrictEqual(v.terminal, 'clean')
  }

  {
    const dir = freshDir()
    const seen = []
    let first = true
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => {
      seen.push({ reviewer, tier: opts && opts.tier, roundKind: opts && opts.roundKind })
      if (first) {
        first = false
        return { findings: BLOCKER, confidence: 'high', verificationReceipt: receipt(runDir, round, opts), usage: { total: 20 } }
      }
      if (opts && opts.tier === 'reviewer') return { findings: [], confidence: 'low', usage: { total: 1 } }
      return cleanResult(runDir, round, opts)
    }
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer'], legKind: { panel: true, code: false }, fixStep: async () => ({ changedSubjects: ['Test'], coverageDecisions: [] }) })
    assert.ok(seen.some((x) => x.tier === 'reviewer'))
    assert.ok(seen.some((x) => x.tier === 'reviewer-deep'))
    assert.strictEqual(v.terminal, 'clean')
  }

  {
    const dir = freshDir()
    const contexts = []
    const seenCoverageOptions = []
    let roundSeen = 0
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => {
      contexts.push(context)
      seenCoverageOptions.push(((opts && opts.coverageDecisions) || []).map((d) => d.id))
      roundSeen = Math.max(roundSeen, round)
      if (round === 1) return blockerResult(runDir, round, opts)
      return cleanResult(runDir, round, opts)
    }
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer'], fixStep: async () => ({ changedSubjects: ['Test'], coverageDecisions: [{ id: 'RCD-1', classKey: 'Test::coverage::missing', text: 'Covered by integration fixture' }] }) })
    assert.ok(roundSeen >= 2)
    assert.ok(contexts.some((ctx) => JSON.stringify(ctx).includes('RCD-1')))
    assert.ok(seenCoverageOptions.some((ids) => ids.includes('RCD-1')))
    assert.strictEqual(v.terminal, 'clean')
  }

  {
    const dir = freshDir()
    await io().writeFile(io().join(dir, 'round-records.json'), '{corrupt json')
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => cleanResult(runDir, round, opts)
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer'] })
    assert.notStrictEqual(v.terminal, 'clean')
    assert.match(v.reason || '', /round-memory/)
  }

  {
    const dir = freshDir()
    await io().writeFile(io().join(dir, 'round-records.json'), JSON.stringify([{
      schemaVersion: 2,
      round: 1,
      kind: 'baseline',
      dimensions: { 'test-reviewer': { status: 'run', confidence: 'high', findings: [{ dimension: 'Test', taxonomy: 'coverage', title: 'Missing acceptance test', severity: 'Critical', evidence: 'x' }], hasFindings: true, subjects: ['Test'] } },
      findings: [{ dimension: 'Test', taxonomy: 'coverage', title: 'Missing acceptance test', severity: 'Critical', evidence: 'x' }],
      changedSubjects: ['Test'],
      coverageDecisions: [{ id: 'RCD-resume', classKey: 'Test::coverage::missing' }],
    }]))
    await io().writeFile(io().join(dir, 'review-coverage-decisions.json'), JSON.stringify([{ id: 'RCD-resume', classKey: 'Test::coverage::missing' }]))
    let captured = null
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => {
      if (round === 2) {
        return { findings: [{ file: 'b.py', line: 2, title: 'resume bug', severity: 'Critical', evidence: 'x' }], confidence: 'high', verificationReceipt: receipt(runDir, round, opts), usage: { total: 1 } }
      }
      return blockerResult(runDir, round, opts)
    }
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer'], fixStep: async (ctx) => { captured = ctx; return { changedSubjects: ['Test'], coverageDecisions: [] } } })
    assert.ok(captured.priorFindings.length > 0)
    assert.ok(captured.classKeys.some((k) => k.includes('Test::coverage')))
    assert.ok(captured.changedSubjects.includes('Test'))
    assert.ok(captured.coverageDecisions.some((d) => d.id === 'RCD-resume'))
  }

  {
    const dir = freshDir()
    await io().writeFile(io().join(dir, 'round-records.json'), JSON.stringify([{
      schemaVersion: 2,
      round: 1,
      kind: 'baseline',
      dimensions: { 'test-reviewer': { status: 'run', confidence: 'high', findings: BLOCKER, hasFindings: true, subjects: ['Test'] } },
      findings: BLOCKER,
      changedSubjects: ['Test'],
      coverageDecisions: [],
      confirmationPending: true,
    }]))
    const seen = []
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => {
      seen.push({ reviewer, round, tier: opts && opts.tier, roundKind: opts && opts.roundKind })
      return cleanResult(runDir, round, opts)
    }
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer', 'security-reviewer'] })
    assert.strictEqual(v.terminal, 'clean')
    assert.deepStrictEqual(seen.map((x) => x.reviewer).sort(), ['security-reviewer', 'test-reviewer'])
    assert.ok(seen.every((x) => x.roundKind === 'confirmation' && x.tier === 'reviewer-deep'))
  }

  {
    const dir = freshDir()
    const oldIo = global.io
    const baseIo = io()
    let persists = 0
    global.io = Object.assign({}, baseIo, { runHelper: async (cmd, args) => {
      // the loop's persist surface is persist-skeleton (round record) + update-round (post-fix
      // delta) — the evidence bodies never ride round-records.json (D3).
      if (String((args || [])[0]).includes('review_memory.py') &&
          (args || []).some((a) => a === 'persist-skeleton' || a === 'update-round')) {
        persists += 1
        if (persists === 2) return { ok: false, stdout: '{"ok":false,"reason":"forced-post-fix"}' }
      }
      return baseIo.runHelper(cmd, args)
    } })
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => {
      if (round === 1) return { findings: BLOCKER, confidence: 'high', verificationReceipt: receipt(runDir, round, opts), usage: { total: 1 } }
      return cleanResult(runDir, round, opts)
    }
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer'], fixStep: async () => ({ changedSubjects: ['Test'], coverageDecisions: [] }) })
    global.io = oldIo
    assert.notStrictEqual(v.terminal, 'clean')
    assert.ok(persists >= 2)
  }

  {
    const dir = freshDir()
    await io().writeFile(io().join(dir, 'round-records.json'), JSON.stringify([{
      schemaVersion: 2,
      round: 1,
      kind: 'baseline',
      dimensions: { 'test-reviewer': { status: 'run', confidence: 'high', findings: BLOCKER, hasFindings: true, subjects: ['Test'] } },
      findings: BLOCKER,
      changedSubjects: ['Test'],
      coverageDecisions: [{ id: 'RCD-lost', classKey: 'Test::coverage::missing' }],
      confirmationPending: true,
    }]))
    await io().writeFile(io().join(dir, 'review-coverage-decisions.json'), '[]')
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => cleanResult(runDir, round, opts)
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer'] })
    assert.notStrictEqual(v.terminal, 'clean')
    assert.match(v.reason || '', /coverage-decision/)
  }

  {
    const dir = freshDir()
    await io().writeFile(io().join(dir, 'review-coverage-decisions.json'), '{bad json')
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => cleanResult(runDir, round, opts)
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer'] })
    assert.notStrictEqual(v.terminal, 'clean')
    assert.match(v.reason || '', /coverage-decisions/)
  }

  {
    const dir = freshDir()
    const fpath = io().join(dir, 'review-coverage-decisions.json')
    await io().writeFile(fpath, JSON.stringify([{ id: 'RCD-old', classKey: 'Test::old' }]))
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => {
      if (round === 1) return blockerResult(runDir, round, opts)
      return cleanResult(runDir, round, opts)
    }
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer'], forceCoverageDecisionExpectedHash: 'wrong', fixStep: async () => ({ changedSubjects: ['Test'], coverageDecisions: [{ id: 'RCD-new', classKey: 'Test::new' }] }) })
    assert.notStrictEqual(v.terminal, 'clean')
    assert.deepStrictEqual(JSON.parse(await io().readText(fpath)), [{ id: 'RCD-old', classKey: 'Test::old' }])
    const records = JSON.parse(await io().readText(io().join(dir, 'round-records.json')))
    assert.ok(!records.some((rec) => rec.confirmationPending === true), 'failed coverage-decision write must not persist a confirmation marker')
  }

  {
    const dir = freshDir()
    const oldIo = global.io
    const baseIo = io()
    global.io = Object.assign({}, baseIo, { runHelper: async (cmd, args) => String((args || [])[0]).includes('coverage_decisions.py') ? { ok: false, stdout: '{"ok":false,"reason":"forced"}' } : baseIo.runHelper(cmd, args) })
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => {
      if (round === 1) return blockerResult(runDir, round, opts)
      return cleanResult(runDir, round, opts)
    }
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer'], fixStep: async () => ({ changedSubjects: ['Test'], coverageDecisions: [{ id: 'RCD-fail', classKey: 'Test::fail' }] }) })
    global.io = oldIo
    assert.notStrictEqual(v.terminal, 'clean')
  }

  {
    const dir = freshDir()
    let challengedContextSeen = false
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => {
      if (round === 1) return { findings: BLOCKER, confidence: 'high', verificationReceipt: receipt(runDir, round, opts), usage: { total: 3 } }
      if (JSON.stringify(context || {}).includes('RCD-wrong')) challengedContextSeen = true
      return { findings: [{ dimension: 'Test', taxonomy: 'coverage', title: 'Coverage decision is false', severity: 'Important', classKey: 'Test::coverage::missing acceptance test' }], confidence: 'high', verificationReceipt: receipt(runDir, round, opts), usage: { total: 3 } }
    }
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer'], fixStep: async () => ({ changedSubjects: ['Test'], coverageDecisions: [{ id: 'RCD-wrong', classKey: 'Test::coverage::missing acceptance test', text: 'Only happy-path acceptance tests are required.' }] }) })
    assert.ok(challengedContextSeen)
    assert.notStrictEqual(v.terminal, 'clean')
  }

  {
    const dir = freshDir()
    const captured = []
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => {
      if (round <= 2) return { findings: COVERAGE_BLOCKER, confidence: 'high', verificationReceipt: receipt(runDir, round, opts), usage: { total: 3 } }
      return cleanResult(runDir, round, opts)
    }
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer'], fixStep: async (ctx, verdict) => {
      captured.push({ round: verdict.round, ctx })
      if (verdict.round === 1) return { changedSubjects: ['Test'], coverageDecisions: [] }
      return { changedSubjects: ['Test'], coverageDecisions: [{ id: 'RCD-repeat', classKey: 'Test::coverage::missing acceptance test', text: 'Repeated missing acceptance-test class is covered by the new integration fixture.' }] }
    } })
    assert.deepStrictEqual(captured[0].ctx.generalizeRequired || [], [])
    assert.ok((captured.find((x) => x.round === 2).ctx.generalizeRequired || []).some((d) => String(d.classKey).includes('Test::coverage')))
    assert.strictEqual(v.terminal, 'clean')
  }

  console.log('ok: in-memory loop shell sentinel + passthrough + continue/fix/clean + extras + accumulator + verify-coercion + policy/memory/coverage')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
