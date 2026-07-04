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
        fs.writeFileSync(path.join(dir, 'verify-result-r1.json'),
          JSON.stringify({ command: 'run-tests', returncode: '0', timedOut: 'false' }))
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
    assert.strictEqual(v.terminal, 'cannot-certify', 'a high-confidence reviewer result without a receipt must fail closed')
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
    global.reviewerAgent = async () => ({ findings: [], confidence: 'low', receiptMissing: true })
    v = await reviewPanel({ ...base(dir), reviewerSet: ['code-reviewer'], legKind: { panel: true, code: false } })
    assert.notStrictEqual(v.terminal, 'clean')
    const recs = JSON.parse(fs.readFileSync(path.join(dir, 'round-records.json'), 'utf8'))
    assert.strictEqual(recs[0].dimensions['code-reviewer'].status, 'run',
      'a shaped low-confidence reviewer result ran; only null/malformed results are missing')
    assert.strictEqual(recs[0].dimensions['code-reviewer'].confidence, 'low')
  }

  {
    const dir = freshDir()
    let calls = 0
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => {
      calls += 1
      if (calls === 1) return { findings: [], confidence: 'low', receiptMissing: true }
      return cleanResult(runDir, round, opts)
    }
    v = await reviewPanel({ ...base(dir), reviewerSet: ['code-reviewer'], legKind: { panel: true, code: false } })
    assert.strictEqual(v.terminal, 'clean')
    assert.strictEqual(calls, 2, 'a deep-tier receipt miss gets one deep retry before recording')
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
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) =>
      ({ findings: [], confidence: 'high', verificationReceipt: receipt(runDir, round, opts), usage: { input: 0, output: 0, total: 0 } })
    v = await reviewPanel({ ...base(dir), reviewerSet: ['code-reviewer'], legKind: { panel: true, code: false } })
    assert.strictEqual(v.terminal, 'clean')
    assert.ok(v.telemetry.tokenUsage.missing.includes('code-reviewer:r1'),
      'zero usage stubs are omitted instead of counted as real telemetry')
    assert.ok(!v.telemetry.tokenUsage.present.includes('code-reviewer:r1'))
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
      round: 5,
      kind: 'confirmation',
      dimensions: { 'test-reviewer': { status: 'run', confidence: 'high', findings: [], hasFindings: false, subjects: ['Test'] } },
      findings: [],
      changedSubjects: ['Test'],
      coverageDecisions: [],
    }]))
    const oldIo = global.io
    const baseIo = io()
    let loadCalls = 0
    let reviewerCalls = 0
    global.io = Object.assign({}, baseIo, { runHelper: async (cmd, args) => {
      if (String((args || [])[0]).includes('review_memory.py') && (args || []).includes('entry-bootstrap')) {
        loadCalls += 1
        return { ok: true, stdout: 'courier wrapped a non-json answer' }
      }
      return baseIo.runHelper(cmd, args)
    } })
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => {
      reviewerCalls += 1
      return cleanResult(runDir, round, opts)
    }
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer'] })
    global.io = oldIo
    assert.strictEqual(v.reason, 'round-memory-unreadable',
      'unreadable existing round memory parks by name instead of starting a fresh round')
    assert.strictEqual(loadCalls, 2, 'round-memory load gets one retry before parking')
    assert.strictEqual(reviewerCalls, 0, 'unreadable existing memory must not burn a redundant panel')
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
    const oldIo = global.io
    const baseIo = io()
    global.io = Object.assign({}, baseIo, { runHelper: async (cmd, args) => {
      if (String((args || [])[0]).includes('coverage_decisions.py') && (args || []).includes('load')) {
        return { ok: true, status: 0, stdout: '`{"ok":true,"decisions":[],"contentHash":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}`' }
      }
      return baseIo.runHelper(cmd, args)
    } })
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => cleanResult(runDir, round, opts)
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer'] })
    global.io = oldIo
    assert.strictEqual(v.terminal, 'clean',
      'single-backtick-wrapped coverage-load JSON should parse via brace-slice fallback, not park')
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

  {
    const dir = freshDir()
    const modernFinding = {
      file: 'plugins/superheroes/lib/showrunner.js',
      line: 1493,
      summary: 'verify courier result is nested as a JSON string',
      failure_scenario: 'The verify courier wraps verify_gate stdout under result, making the pass unreadable.',
    }
    const expectedId = 'plugins/superheroes/lib/showrunner.js::verify courier result is nested as a json string'
    let fixCalls = 0
    global.reviewerAgent = async (_reviewer, _context, _rubric, runDir, round, opts) => {
      if (round === 1) return { findings: [modernFinding], confidence: 'high', verificationReceipt: receipt(runDir, round, opts), usage: { total: 3 } }
      return cleanResult(runDir, round, opts)
    }
    global.synthesisLeaf = async (merged) => ({
      verdicts: merged.map((f) => ({
        id: expectedId,
        action: 'keep',
        severity: 'Critical',
        reason: `kept ${f.file}`,
      })),
      usage: { total: 1 },
    })
    v = await reviewPanel({ ...base(dir), reviewerSet: ['code-reviewer'], fixStep: async () => {
      fixCalls += 1
      return { fixed: [expectedId], changedSubjects: ['Code'], coverageDecisions: [] }
    } })
    assert.strictEqual(fixCalls, 1,
      'modern reviewer finding + Critical synthesis verdict must trigger the fix leg')
    assert.strictEqual(v.terminal, 'clean')
    const recs = JSON.parse(fs.readFileSync(path.join(dir, 'round-records.json'), 'utf8'))
    const first = recs.find((r) => r.round === 1).findings[0]
    assert.strictEqual(first.title, modernFinding.summary,
      'round-record finding title must be normalized from summary')
    assert.strictEqual(first.severity, 'Critical',
      'round-record finding severity must include the synthesis verdict severity')
    assert.strictEqual(first.summary, undefined,
      'round-record skeleton remains bounded and does not persist full modern-shape bodies')
  }

  {
    const dir = freshDir()
    const modernFinding = {
      file: 'plugins/superheroes/lib/review_panel_shell.js',
      line: 671,
      summary: 'kept synthesis finding has no severity',
      failure_scenario: 'A synthesis keep with no severity must not become certification-neutral.',
    }
    const expectedId = 'plugins/superheroes/lib/review_panel_shell.js::kept synthesis finding has no severity'
    let fixCalls = 0
    global.reviewerAgent = async (_reviewer, _context, _rubric, runDir, round, opts) => {
      if (round === 1) return { findings: [modernFinding], confidence: 'high', verificationReceipt: receipt(runDir, round, opts), usage: { total: 3 } }
      return cleanResult(runDir, round, opts)
    }
    global.synthesisLeaf = async () => ({
      verdicts: [{ id: expectedId, action: 'keep', reason: 'still applies' }],
      usage: { total: 1 },
    })
    v = await reviewPanel({ ...base(dir), reviewerSet: ['code-reviewer'], fixStep: async () => {
      fixCalls += 1
      return { fixed: [expectedId], changedSubjects: ['Code'], coverageDecisions: [] }
    } })
    assert.strictEqual(fixCalls, 1,
      'a kept finding with no severity anywhere must still block and run the fix leg')
    assert.strictEqual(v.terminal, 'clean')
    const recs = JSON.parse(fs.readFileSync(path.join(dir, 'round-records.json'), 'utf8'))
    const first = recs.find((r) => r.round === 1).findings[0]
    assert.strictEqual(first.title, modernFinding.summary)
    assert.strictEqual(first.severity, 'Important',
      'severity-less kept findings default to Important before persistence')
  }

  // #212 fix-before-park (receipt-missing replay of run 6): a reviewer that answers high WITHOUT a
  // receipt is downgraded to low+receiptMissing (findings KEPT). A round-1 answer that STILL holds a
  // blocker must NOT park-without-fix — it routes to the fix leg. When the seat still can't produce a
  // receipt but the blocker is gone next round, THEN it parks, naming the seat + defect class honestly.
  {
    const dir = freshDir()
    const fixRounds = []
    global.reviewerAgent = async (_r, _c, _rub, _rd, round, _opts) => (
      // r1 (+ its retries): blocker, no receipt -> low+receiptMissing, blocker kept.
      // r2 (+ retries):     no blocker, no receipt -> low+receiptMissing, only the coverage gap remains.
      round === 1 ? { findings: BLOCKER, confidence: 'high' } : { findings: [], confidence: 'high' })
    v = await reviewPanel({ ...base(dir), reviewerSet: ['code'], legKind: { panel: true, code: false },
      fixStep: async (_ctx, verdict) => { fixRounds.push(verdict && verdict.round); return { fixed: ['a.py::bug'], changedSubjects: ['Code'], coverageDecisions: [] } } })
    assert.strictEqual(v.terminal, 'cannot-certify',
      '#212: an uncertified round holding a blocker fixes first, then parks cannot-certify once only the coverage gap remains')
    // Pin the ORDERING directly (not just "a fix happened"): the fix leg ran on the uncertified
    // round-1 that held the blocker, and the park returns on a LATER round — fix strictly BEFORE park.
    assert.ok(fixRounds.includes(1), '#212: the fix leg ran on the uncertified round-1 that held the blocker')
    assert.ok((v.round || 0) > Math.max(...fixRounds), '#212: the park returns AFTER the fix round (fix-before-park)')
    assert.strictEqual(v.uncertified, true, '#212: the verdict carries the uncertified flag')
    assert.match(v.reason || '', /receipt-missing — uncertifiable/, '#212: the park reason names the receipt-missing defect class')
    assert.match(v.reason || '', /^code /, '#212: the park reason names the uncertifiable seat')
  }

  // #212 composite (addendum item 4): seat X answers MALFORMED twice (the corrective retry fires,
  // carrying retryReason 'malformed') and ends status:'missing', while another seat holds a blocker.
  // The round FIXES the blocker first (fix-before-park), then parks cannot-certify naming BOTH the
  // malformed seat and its cause — exercising all four changes plus the addendum in one fixture.
  {
    const dir = freshDir()
    const retryReasons = []
    let fixCalls = 0
    global.reviewerAgent = async (reviewer, _c, _rub, runDir, round, opts) => {
      if (opts && opts.retryReason) retryReasons.push({ reviewer, retryReason: opts.retryReason })
      if (reviewer === 'code-reviewer') return { notFindings: true }   // malformed every attempt -> status:missing
      return round === 1 ? blockerResult(runDir, round, opts) : cleanResult(runDir, round, opts)
    }
    v = await reviewPanel({ ...base(dir), reviewerSet: ['code-reviewer', 'security-reviewer'], legKind: { panel: true, code: false },
      fixStep: async () => { fixCalls += 1; return { fixed: ['a.py::bug'], changedSubjects: ['Code'], coverageDecisions: [] } } })
    assert.ok(retryReasons.some((x) => x.reviewer === 'code-reviewer' && x.retryReason === 'malformed'),
      '#212: a malformed answer gets a CORRECTIVE retry (retryReason=malformed), not a blind one')
    assert.ok(fixCalls >= 1, '#212: the healthy seat\'s blocker is fixed before the park')
    assert.strictEqual(v.terminal, 'cannot-certify', '#212: the round stays uncertifiable (gate changes-requested)')
    assert.strictEqual(v.uncertified, true)
    assert.match(v.reason || '', /code-reviewer did not return a usable result after retry \(malformed — uncertifiable\)/,
      '#212: the park reason names the malformed seat AND its cause')
  }

  global.synthesisLeaf = async () => ({ verdicts: [], usage: { total: 1 } })

  console.log('ok: in-memory loop shell sentinel + passthrough + continue/fix/clean + extras + accumulator + verify-coercion + policy/memory/coverage + #212 fix-before-park/corrective-retry/honest-reason')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
