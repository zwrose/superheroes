// Smoke: #397 FR-15 — doc-review convergence record is journaled at every terminal (pass, park,
// accepted) with rounds used, per-round blocking vs routed-forward counts, and the outcome.
'use strict'
require('./_smoke_checkout_root.js')
if (globalThis.__SR_ROOT) process.chdir(globalThis.__SR_ROOT)
const assert = require('assert')
const fs = require('fs')
const path = require('path')
const { execSync, execFileSync } = require('child_process')
const test = require('node:test')
const sr = require('../showrunner.js')
const { saveProgressOk } = require('./_marked_stdout.js')

globalThis.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
globalThis.log = () => {}

const SFX = `-pid${process.pid}`
const WI = `wi-conv${SFX}`

const BLOCKER = [{
  file: 'plan.md', line: 1, title: 'blocker', severity: 'Critical',
  evidence: 'e',
}]

function receiptFromPrompt(prompt) {
  let ctx = { receiptArtifact: 'stub', receiptCoverageDecisionIds: [] }
  const m = String(prompt || '').match(/Prompt context: (\{.*\})/s)
  if (m) { try { ctx = JSON.parse(m[1]) } catch (_) {} }
  return {
    artifact: ctx.receiptArtifact || 'stub',
    chain: [
      { step: 'citation', evidence: 'reviewed citations' },
      { step: 'reachability', evidence: 'validated call path' },
      { step: 'missing-check', evidence: 'checked missing FRs' },
      { step: 'tooling', evidence: 'smoke passed' },
    ],
    coverageDecisionIds: ctx.receiptCoverageDecisionIds || [],
  }
}

function extractExecCommand(prompt) {
  const m = String(prompt).match(/^\d+\.\s(.*)$/m)
  return m ? m[1] : null
}

function makeAgent({ convergenceMode = 'real', gate = 'pending' } = {}) {
  const fn = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'resume') return '1'
    if (label === 'save phase progress') {
      return saveProgressOk({ checkpoint_confirmed: false })
    }
    if (label === 'save round state') {
      return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
    }
    if (opts && opts.courier) {
      if (prompt.includes('read-gate')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ review: gate }) }]
      }
      if (prompt.includes('review_convergence.py')) {
        if (convergenceMode === 'reject') throw new Error('courier transport rejected')
        if (convergenceMode === 'non-json') {
          return [{ index: 0, ok: true, stdout: 'not json' }]
        }
        const cmd = extractExecCommand(prompt)
        assert.ok(cmd, 'review_convergence dispatch must be a numbered exec command')
        const stdout = execSync(cmd, { encoding: 'utf8', shell: '/bin/bash' }).trim()
        return [{ index: 0, ok: true, stdout }]
      }
      if (prompt.includes('review_handoff.py') && prompt.includes(' write ')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true, counts: { distinct: 0 } }) }]
      }
      if (prompt.includes('review_park.py')) {
        const cmd = extractExecCommand(prompt)
        assert.ok(cmd)
        const stdout = execSync(cmd, { encoding: 'utf8', shell: '/bin/bash' }).trim()
        return [{ index: 0, ok: true, stdout }]
      }
      if (prompt.includes('gate-for-terminal')) {
        throw new Error('gate-for-terminal dispatched as exec — must use JS twin')
      }
      return [{ index: 0, ok: true, stdout: '' }, { index: 1, ok: true, stdout: '' }]
    }
    if (prompt.includes('gate-for-terminal')) {
      throw new Error('gate-for-terminal dispatched as cmdRunner — must use JS twin')
    }
    if (label.endsWith('-reviewer')) {
      return { findings: BLOCKER, confidence: 'high', verificationReceipt: receiptFromPrompt(prompt) }
    }
    if (label.startsWith('synthesis')) return { verdicts: [] }
    if (label === 'revise-doc') return null
    return null
  }
  return fn
}

function seedPlanDoc(docsDir) {
  fs.mkdirSync(docsDir, { recursive: true })
  fs.writeFileSync(path.join(docsDir, 'plan.md'), '# Plan\n## Review coverage decisions\n')
}

function cleanRunDir(workItem = WI) {
  try { fs.rmSync(`/tmp/showrunner-${workItem}-review-plan`, { recursive: true, force: true }) } catch (_) {}
}

function cleanLegacyFixture(workItem = WI) {
  try { fs.rmSync(`docs/superheroes/${workItem}`, { recursive: true, force: true }) } catch (_) {}
}

function getJournalEvents(workItem) {
  const libDir = path.join(__dirname, '..')
  const script = [
    'import sys, os, json',
    `sys.path.insert(0, ${JSON.stringify(libDir)})`,
    'import control_plane',
    `wi = ${JSON.stringify(workItem)}`,
    'p = control_plane.paths(os.getcwd(), wi)',
    'events = p["events"]',
    'out = []',
    'if os.path.isfile(events):',
    '    with open(events, encoding="utf-8") as fh:',
    '        for line in fh:',
    '            line = line.strip()',
    '            if line:',
    '                out.append(json.loads(line))',
    'print(json.dumps(out))',
  ].join('\n')
  const stdout = execFileSync('python3', ['-c', script], {
    encoding: 'utf8',
    cwd: globalThis.__SR_ROOT || process.cwd(),
  }).trim()
  return JSON.parse(stdout)
}

function convergenceEvents(workItem, sinceSeq = 0) {
  return getJournalEvents(workItem).filter((e) => e.type === 'review_convergence' && (e.seq || 0) > sinceSeq)
}

function maxEventSeq(workItem) {
  return getJournalEvents(workItem).reduce((m, e) => Math.max(m, e.seq || 0), 0)
}

async function drivePlanReview(convergenceMode, { blockerFindings = BLOCKER, gate = 'pending', workItem = WI } = {}) {
  cleanRunDir(workItem)
  cleanLegacyFixture(workItem)
  const docsDir = fs.mkdtempSync(path.join(require('os').tmpdir(), 'sr-conv-'))
  seedPlanDoc(docsDir)
  globalThis.__SR_DOC_DIRS = { [workItem]: docsDir }
  const agent = makeAgent({ convergenceMode, gate })
  const origAgent = agent
  globalThis.agent = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label.endsWith('-reviewer')) {
      return { findings: blockerFindings, confidence: 'high', verificationReceipt: receiptFromPrompt(prompt) }
    }
    return origAgent(prompt, opts)
  }
  globalThis.agent.savePrompts = origAgent.savePrompts ? () => origAgent.savePrompts() : () => []
  const idx = sr.PHASES.indexOf('review-plan')
  const loopOut = await sr.runPhases(workItem, idx, {
    reviewDoc: (doc, wi) => sr.reviewDocPhase(doc, wi, { runId: 'run-conv' }),
  })
  return { loopOut, docsDir, workItem }
}

test('convergence record function is called on a parked doc terminal (no exceptions)', async () => {
  const since = maxEventSeq(WI)
  try {
    const { loopOut } = await drivePlanReview('real')
    assert.strictEqual(loopOut.outcome, 'parked', 'review with blocker should park')
    assert.strictEqual(loopOut.phase, 'review-plan')
    const events = convergenceEvents(WI, since)
    assert.strictEqual(events.length, 1, 'park terminal must journal exactly one review_convergence event')
    assert.strictEqual(events[0].payload.doc, 'plan')
    assert.ok(events[0].payload.outcome, 'convergence payload must name the terminal outcome')
  } finally {
    delete globalThis.__SR_DOC_DIRS
    delete globalThis.agent
    cleanRunDir()
    cleanLegacyFixture()
  }
})

test('convergence record is journaled on both passed and parked terminals', async () => {
  try {
    let since = maxEventSeq(WI)
    const { loopOut: parked } = await drivePlanReview('real')
    assert.strictEqual(parked.outcome, 'parked')
    assert.strictEqual(convergenceEvents(WI, since).length, 1, 'parked terminal journals review_convergence')

    delete globalThis.__SR_DOC_DIRS
    delete globalThis.agent
    cleanRunDir()
    cleanLegacyFixture()

    const passWi = `${WI}-pass`
    since = maxEventSeq(passWi)
    cleanRunDir(passWi)
    cleanLegacyFixture(passWi)
    const docsDir = fs.mkdtempSync(path.join(require('os').tmpdir(), 'sr-conv-'))
    seedPlanDoc(docsDir)
    globalThis.__SR_DOC_DIRS = { [passWi]: docsDir }
    const orig = makeAgent({ gate: 'pending' })
    globalThis.agent = async (prompt, opts) => {
      const label = (opts && opts.label) || ''
      if (label.endsWith('-reviewer')) {
        return { findings: [], confidence: 'high', verificationReceipt: receiptFromPrompt(prompt) }
      }
      if (label === 'revise-doc') return { fixes: [], deferred: [] }
      return orig(prompt, opts)
    }
    const r = await sr.reviewDocPhase('plan', passWi, { runId: 'run-conv' })
    assert.strictEqual(r.gate, 'passed', 'clean review should pass')
    const passEvents = convergenceEvents(passWi, since)
    assert.strictEqual(passEvents.length, 1, 'passed terminal must journal review_convergence')
    assert.strictEqual(passEvents[0].payload.doc, 'plan')
    assert.strictEqual(passEvents[0].payload.outcome, 'clean')
  } finally {
    delete globalThis.__SR_DOC_DIRS
    delete globalThis.agent
    cleanRunDir()
    cleanLegacyFixture()
  }
})

test('accepted-pass gate skip journals review_convergence without re-running the panel', async () => {
  const since = maxEventSeq(WI)
  try {
    cleanRunDir()
    cleanLegacyFixture()
    const docsDir = fs.mkdtempSync(path.join(require('os').tmpdir(), 'sr-conv-'))
    seedPlanDoc(docsDir)
    globalThis.__SR_DOC_DIRS = { [WI]: docsDir }
    let panelRuns = 0
    const orig = makeAgent({ gate: 'passed' })
    globalThis.agent = async (prompt, opts) => {
      const label = (opts && opts.label) || ''
      if (label.endsWith('-reviewer')) panelRuns += 1
      return orig(prompt, opts)
    }
    const r = await sr.reviewDocPhase('plan', WI, { runId: 'run-conv' })
    assert.strictEqual(r.gate, 'passed')
    assert.strictEqual(panelRuns, 0, 'passed-gate skip must not re-run the panel')
    const events = convergenceEvents(WI, since)
    assert.strictEqual(events.length, 1, 'accepted-pass must journal review_convergence')
    assert.strictEqual(events[0].payload.outcome, 'accepted-pass')
  } finally {
    delete globalThis.__SR_DOC_DIRS
    delete globalThis.agent
    cleanRunDir()
    cleanLegacyFixture()
  }
})

test('UFR-1: convergence dispatch failure discloses on phaseResult.assumptions', async () => {
  const since = maxEventSeq(WI)
  try {
    cleanRunDir()
    cleanLegacyFixture()
    const docsDir = fs.mkdtempSync(path.join(require('os').tmpdir(), 'sr-conv-'))
    seedPlanDoc(docsDir)
    globalThis.__SR_DOC_DIRS = { [WI]: docsDir }
    globalThis.agent = makeAgent({ convergenceMode: 'reject' })
    const r = await sr.reviewDocPhase('plan', WI, { runId: 'run-conv' })
    assert.ok(r.phaseResult, 'phase should return phaseResult even on convergence dispatch failure')
    const assumptions = (r.phaseResult && r.phaseResult.assumptions) || []
    assert.ok(
      assumptions.some((a) => /review_convergence record may have failed/.test(a)),
      'courier rejection must disclose on phaseResult.assumptions',
    )
    assert.strictEqual(convergenceEvents(WI, since).length, 0,
      'UFR-1: no review_convergence event when compose dispatch fails')
  } finally {
    delete globalThis.__SR_DOC_DIRS
    delete globalThis.agent
    cleanRunDir()
    cleanLegacyFixture()
  }
})

test('UFR-1: non-JSON convergence compose discloses and does not journal', async () => {
  const since = maxEventSeq(WI)
  try {
    cleanRunDir()
    cleanLegacyFixture()
    const docsDir = fs.mkdtempSync(path.join(require('os').tmpdir(), 'sr-conv-'))
    seedPlanDoc(docsDir)
    globalThis.__SR_DOC_DIRS = { [WI]: docsDir }
    globalThis.agent = makeAgent({ convergenceMode: 'non-json' })
    const r = await sr.reviewDocPhase('plan', WI, { runId: 'run-conv' })
    const assumptions = (r.phaseResult && r.phaseResult.assumptions) || []
    assert.ok(
      assumptions.some((a) => /review_convergence record may have failed/.test(a)),
      'non-JSON compose stdout must disclose on phaseResult.assumptions',
    )
    assert.strictEqual(convergenceEvents(WI, since).length, 0,
      'UFR-1: no review_convergence event when compose stdout is not JSON')
  } finally {
    delete globalThis.__SR_DOC_DIRS
    delete globalThis.agent
    cleanRunDir()
    cleanLegacyFixture()
  }
})
