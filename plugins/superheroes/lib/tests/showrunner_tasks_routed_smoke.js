// Smoke: #397 FR-4/FR-5 / UFR-1 — tasks-review terminal journals routed_forward events for
// non-blocking findings and discloses a journal dispatch failure on phaseResult.assumptions.
'use strict'
require('./_smoke_checkout_root.js')
if (globalThis.__SR_ROOT) process.chdir(globalThis.__SR_ROOT)
const assert = require('assert')
const fs = require('fs')
const path = require('path')
const test = require('node:test')
const sr = require('../showrunner.js')
const { defaultIo } = require('../io_seam.js')
const { saveProgressOk } = require('./_marked_stdout.js')

globalThis.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
globalThis.log = () => {}

const SFX = `-pid${process.pid}`
const WI = `wi-routed${SFX}`

const NONBLOCKING = [
  { file: 'tasks.md', line: 1, title: 'nit: variable naming', severity: 'Minor',
    docSection: 'Intro', summary: 'rename the loop counter' },
  { file: 'tasks.md', line: 2, title: 'clarify step order', severity: 'Minor',
    docSection: 'Flow', summary: 'step 2 should precede step 3' },
]

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

function makeAgent() {
  const fn = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'resume') return '1'
    if (label === 'save phase progress') return saveProgressOk()
    if (label === 'save round state') return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
    if (opts && opts.courier) {
      if (prompt.includes('read-gate')) {
        return [{ index: 0, ok: true, stdout: JSON.stringify({ review: 'pending' }) }]
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
      return { findings: NONBLOCKING, confidence: 'high', verificationReceipt: receiptFromPrompt(prompt) }
    }
    if (label.startsWith('synthesis')) return { verdicts: [] }
    if (label === 'revise-doc') return { fixes: [], deferred: [] }
    return null
  }
  return fn
}

function seedTasksDoc(docsDir) {
  fs.mkdirSync(docsDir, { recursive: true })
  fs.writeFileSync(path.join(docsDir, 'tasks.md'), '# Tasks\n## Review coverage decisions\n')
}

function cleanRunDir() {
  try { fs.rmSync(`/tmp/showrunner-${WI}-review-tasks`, { recursive: true, force: true }) } catch (_) {}
}

function cleanLegacyFixture() {
  try { fs.rmSync(`docs/superheroes/${WI}`, { recursive: true, force: true }) } catch (_) {}
}

function installIo({ routedMode = 'real' } = {}) {
  const routedCalls = []
  const orig = global.io
  global.io = {
    ...defaultIo,
    async runHelper(cmd, args, opts) {
      if (opts && opts.label === 'route tasks findings') {
        routedCalls.push({
          workItem: args[2],
          findings: JSON.parse(args[3]),
        })
        if (routedMode === 'reject') throw new Error('courier transport rejected')
        if (routedMode === 'non-ok') {
          return { ok: false, status: 1, stdout: '', stderr: 'stub journal failure' }
        }
        return { ok: true, status: 0, stdout: '', stderr: '' }
      }
      return defaultIo.runHelper(cmd, args, opts)
    },
  }
  return {
    routedCalls: () => routedCalls,
    restore() {
      if (orig === undefined) delete global.io
      else global.io = orig
    },
  }
}

async function driveTasksReview(docsDir, routedMode) {
  cleanRunDir()
  cleanLegacyFixture()
  seedTasksDoc(docsDir)
  globalThis.__SR_DOC_DIRS = { [WI]: docsDir }
  globalThis.agent = makeAgent()
  const ioStub = installIo({ routedMode })
  try {
    const r = await sr.reviewDocPhase('tasks', WI, { runId: 'run-routed' })
    return { result: r, ioStub, docsDir }
  } finally {
    ioStub.restore()
  }
}

test('tasks-review terminal dispatches routed_forward journal for non-blocking findings', async () => {
  const docsDir = fs.mkdtempSync(path.join(require('os').tmpdir(), 'sr-tasks-routed-'))
  try {
    const { result, ioStub } = await driveTasksReview(docsDir, 'real')
    assert.strictEqual(result.gate, 'passed', 'non-blocking-only panel must pass')
    const calls = ioStub.routedCalls()
    assert.ok(calls.length >= 1, 'must dispatch route tasks findings journal write')
    assert.strictEqual(calls[0].workItem, WI)
    assert.ok(calls[0].findings.length >= 2, 'non-blocking findings must reach the journal dispatch')
  } finally {
    delete globalThis.__SR_DOC_DIRS
    delete globalThis.agent
    try { fs.rmSync(docsDir, { recursive: true, force: true }) } catch (_) {}
    cleanRunDir()
    cleanLegacyFixture()
  }
})

test('routed_forward payload scrubs secrets from BOTH text and identity (real production path)', async () => {
  // No interception: sr.journalTasksRoutedFindings runs its REAL embedded python3 -c courier
  // script against a temp store root, and we read back the events.jsonl it wrote. This is the
  // production composition path — a secret in a finding title must not survive into either
  // payload.text or payload.identity (journal.append writes payload as-is).
  const store = fs.mkdtempSync(path.join(require('os').tmpdir(), `sr-routed-store${SFX}-`))
  const prevStore = process.env.SUPERHEROES_STORE_ROOT
  process.env.SUPERHEROES_STORE_ROOT = store
  const prevIo = global.io
  delete global.io   // fall back to defaultIo — the real runHelper
  try {
    await sr.journalTasksRoutedFindings(WI, [
      { file: 'tasks.md', title: 'rotate the leaked token: Bearer abcdef0123456789',
        severity: 'Minor', docSection: 'Security' },
    ])
    // find the events.jsonl the real courier wrote under the pinned store root
    const found = []
    ;(function walk(d) {
      for (const e of fs.readdirSync(d, { withFileTypes: true })) {
        const p = path.join(d, e.name)
        if (e.isDirectory()) walk(p)
        else if (e.name === 'events.jsonl') found.push(p)
      }
    })(store)
    assert.strictEqual(found.length, 1, 'exactly one events.jsonl written under the pinned store root')
    const events = fs.readFileSync(found[0], 'utf8').trim().split('\n').map((l) => JSON.parse(l))
    const routed = events.filter((e) => e.type === 'routed_forward')
    assert.strictEqual(routed.length, 1, 'exactly one routed_forward event')
    const payload = routed[0].payload
    assert.ok(!payload.text.includes('abcdef0123456789'), 'secret absent from payload.text')
    assert.ok(!payload.identity.includes('abcdef0123456789'), 'secret absent from payload.identity')
    assert.ok(payload.text.includes('[REDACTED]'), 'text carries the redaction marker')
    assert.ok(payload.identity.startsWith('tasks.md::'), 'identity keeps its file::title shape')
  } finally {
    if (prevStore === undefined) delete process.env.SUPERHEROES_STORE_ROOT
    else process.env.SUPERHEROES_STORE_ROOT = prevStore
    if (prevIo !== undefined) global.io = prevIo
    try { fs.rmSync(store, { recursive: true, force: true }) } catch (_) {}
  }
})

test('UFR-1: routed_forward journal dispatch failure discloses on phaseResult.assumptions', async () => {
  const docsDir = fs.mkdtempSync(path.join(require('os').tmpdir(), 'sr-tasks-routed-'))
  try {
    const { result } = await driveTasksReview(docsDir, 'non-ok')
    const assumptions = (result.phaseResult && result.phaseResult.assumptions) || []
    assert.ok(
      assumptions.some((a) => /routed_forward events may have failed/.test(a)),
      'journal dispatch failure must surface on phaseResult.assumptions',
    )
  } finally {
    delete globalThis.__SR_DOC_DIRS
    delete globalThis.agent
    try { fs.rmSync(docsDir, { recursive: true, force: true }) } catch (_) {}
    cleanRunDir()
    cleanLegacyFixture()
  }
})

test('UFR-1 guard: rejected routed_forward dispatch still returns terminal result with disclosure', async () => {
  const docsDir = fs.mkdtempSync(path.join(require('os').tmpdir(), 'sr-tasks-routed-'))
  try {
    const { result } = await driveTasksReview(docsDir, 'reject')
    assert.ok(result && result.gate, 'phase must still return its terminal gate (not abort)')
    const assumptions = (result.phaseResult && result.phaseResult.assumptions) || []
    assert.ok(
      assumptions.some((a) => /routed_forward events may have failed/.test(a)),
      'reject path must disclose on phaseResult.assumptions',
    )
  } finally {
    delete globalThis.__SR_DOC_DIRS
    delete globalThis.agent
    try { fs.rmSync(docsDir, { recursive: true, force: true }) } catch (_) {}
    cleanRunDir()
    cleanLegacyFixture()
  }
})
