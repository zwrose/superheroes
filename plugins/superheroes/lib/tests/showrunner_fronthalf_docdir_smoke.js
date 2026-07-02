// Smoke: the front-half completion-signal paths are storage-mode-aware. docPathFor /
// notifyLedgerFor resolve through the work-item docs dir planted at startup
// (readStartupState computes it via definition_doc.resolve_work_item_dir and showrunner()
// plants it on globalThis.__SR_DOC_DIRS); un-planted (direct smoke/unit drives, or a failed
// resolution) they fall back to the legacy in-repo default docs/superheroes/<wi>.
// Regression for the 2026-07-02 live run on an out-of-repo-calibrated project: the resolver
// wrote plan.md into the project store while the spine read (and hashed, and appended the
// NOTIFY ledger under) the hard-wired in-repo path.
'use strict'
const assert = require('assert')
const fs = require('fs')
const sr = require('../showrunner.js')
const { io } = require('../io_seam.js')

globalThis.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
globalThis.log = () => {}

// (a) fallback: nothing planted -> legacy in-repo relative paths (unchanged behavior).
function partFallback() {
  delete globalThis.__SR_DOC_DIRS
  assert.strictEqual(sr.docPathFor('wi-x', 'plan'), 'docs/superheroes/wi-x/plan.md')
  assert.strictEqual(sr.notifyLedgerFor('wi-x'), 'docs/superheroes/wi-x/.notify.json')
}

// (b) planted: the startup-resolved (absolute, mode-aware) dir wins — per work-item.
function partPlanted() {
  globalThis.__SR_DOC_DIRS = { 'wi-x': '/abs/proj-store/docs/wi-x' }
  assert.strictEqual(sr.docPathFor('wi-x', 'plan'), '/abs/proj-store/docs/wi-x/plan.md')
  assert.strictEqual(sr.notifyLedgerFor('wi-x'), '/abs/proj-store/docs/wi-x/.notify.json')
  // a different work-item is untouched (the map is per-work-item, not a blanket override)
  assert.strictEqual(sr.docPathFor('wi-y', 'plan'), 'docs/superheroes/wi-y/plan.md')
  delete globalThis.__SR_DOC_DIRS
}

// (c) producePhase's NOTIFY append targets the resolved ledger path (not the legacy one).
async function partAppendNotify() {
  globalThis.__SR_DOC_DIRS = { 'wi-n': '/abs/proj-store/docs/wi-n' }
  const NOT_USABLE = JSON.stringify({ usable: false, recorded: '', expected: '' })
  const USABLE = JSON.stringify({ usable: true, recorded: 'h', expected: 'h' })
  const notifyPrompts = []
  let emitCalls = 0
  globalThis.agent = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'exec') {
      if (prompt.includes('emit-signals')) {
        emitCalls += 1
        return [{ index: 0, ok: true, stdout: emitCalls === 1 ? NOT_USABLE : USABLE }]
      }
      if (prompt.includes('append-notify')) {
        notifyPrompts.push(prompt)
        return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      }
      return [{ index: 0, ok: true, stdout: '' }]
    }
    if (label.startsWith('author-')) return { status: 'ok', notify: [{ identity: 'i', message: 'm' }] }
    return null
  }
  const r = await sr.producePhase('plan', 'wi-n')
  assert.strictEqual(r.confidence, 'high', 'produce must succeed in this scenario')
  assert.strictEqual(notifyPrompts.length, 1, 'exactly one append-notify exec expected')
  assert.ok(notifyPrompts[0].includes('/abs/proj-store/docs/wi-n/.notify.json'),
    'append-notify must target the resolved ledger path, got: ' + notifyPrompts[0])
  delete globalThis.__SR_DOC_DIRS
}

// (d) reviewDocPhase reads + hashes the doc at the RESOLVED dir. A decoy doc with different
// content sits at the legacy path — a regression to the hard-wired path yields its hash instead.
async function partReviewRead() {
  const resolved = fs.mkdtempSync('/tmp/sr-docdir-')
  fs.writeFileSync(`${resolved}/plan.md`, '# Resolved plan\n## Review coverage decisions\n')
  const legacy = 'docs/superheroes/wi-d'
  fs.mkdirSync(legacy, { recursive: true })
  fs.writeFileSync(`${legacy}/plan.md`, '# DECOY (legacy path) plan\n## Review coverage decisions\n')
  try { fs.rmSync('/tmp/showrunner-wi-d-review-plan', { recursive: true, force: true }) } catch (_) {}
  try {
    await partReviewReadInner(resolved, legacy)
  } finally {
    try { fs.rmSync(resolved, { recursive: true, force: true }) } catch (_) {}
    try { fs.rmSync(legacy, { recursive: true, force: true }) } catch (_) {}
  }
}

async function partReviewReadInner(resolved, legacy) {
  globalThis.__SR_DOC_DIRS = { 'wi-d': resolved }
  const persistPrompts = []
  globalThis.agent = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'resume') return '1'
    if (label === 'save phase progress') {
      persistPrompts.push(prompt)
      return [{ ok: true, stdout: JSON.stringify({ ok: true, journal_confirmed: true, checkpoint_confirmed: true }) }]
    }
    if (label === 'save round state') return [{ ok: true, stdout: JSON.stringify({ ok: true }) }]
    if (label === 'exec') {
      if (prompt.includes('read-gate')) return [{ index: 0, ok: true, stdout: JSON.stringify({ review: 'pending' }) }]
      return [{ index: 0, ok: true, stdout: '' }, { index: 1, ok: true, stdout: '' }]
    }
    if (label.endsWith('-reviewer')) return { findings: [], confidence: 'high' }
    if (label.startsWith('synthesis')) return { verdicts: [] }
    if (label === 'revise-doc') return { fixes: [], deferred: [] }
    return null
  }
  const r = await sr.reviewDocPhase('plan', 'wi-d', { runId: 'run-d' })
  assert.strictEqual(r.gate, 'passed', 'clean panel maps to passed')
  // #118: reviewDocPhase RETURNS the set-gate persist spec; runPhases' tail chains it into the ONE
  // 'save phase progress' leaf. The fence hash is the Python-side 'current' sentinel:
  // definition_doc.py resolves (doc-dir aware) + hashes the SAME file it edits at write time, so
  // no runtime-computed hash — which a prose-answering courier read can poison, and which could
  // disagree with the resolved write target (the old decoy-path hazard) — rides the command.
  const gatePrompt = r.persist && r.persist.sideEffectCmd
  assert.ok(gatePrompt && gatePrompt.includes('set-gate'), 'reviewDocPhase returned the gate write spec')
  const resolvedHash = io().contentHash(fs.readFileSync(`${resolved}/plan.md`, 'utf8'))
  const decoyHash = io().contentHash(fs.readFileSync(`${legacy}/plan.md`, 'utf8'))
  assert.notStrictEqual(resolvedHash, decoyHash, 'fixture sanity: decoy must differ')
  assert.ok(gatePrompt.includes(`--expected-hash 'current'`),
    'gate write fences via the Python-side current-hash sentinel; got: ' + gatePrompt)
  assert.ok(!gatePrompt.includes(resolvedHash) && !gatePrompt.includes(decoyHash),
    'no runtime-computed doc hash may ride the gate write (courier-read hashes are banned)')
  delete globalThis.__SR_DOC_DIRS
}

// (e) startup: readStartupState computes doc_dir and showrunner() plants __SR_DOC_DIRS.
async function partStartupPlants() {
  delete globalThis.__SR_DOC_DIRS
  const calls = []
  globalThis.agent = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    calls.push({ prompt: String(prompt), label })
    if (label === 'read startup state') {
      return [{ ok: true, stdout: JSON.stringify({
        ok: true, spec_gate: 'passed', model_overrides: {},
        doc_dir: '/abs/proj-store/docs/wi-s' }) }]
    }
    if (label === 'exec') {
      if (prompt.includes('recover_entry.py')) return [{ index: 0, ok: true, stdout: '{}' }]
      if (prompt.includes('definition_doc.py read-gate')) return [{ index: 0, ok: true, stdout: '{"review":"passed"}' }]
      return [{ index: 0, ok: true, stdout: '{}' }]
    }
    return null   // park the phase loop — startup already ran by then
  }
  try { await sr.showrunner({ workItem: 'wi-s' }) } catch (_) {}
  const sCall = calls.find((c) => c.label === 'read startup state')
  assert.ok(sCall, 'startup issued the read startup state courier')
  assert.ok(sCall.prompt.includes('doc_dir'), 'the startup state script must compute doc_dir')
  assert.ok(globalThis.__SR_DOC_DIRS && globalThis.__SR_DOC_DIRS['wi-s'] === '/abs/proj-store/docs/wi-s',
    'showrunner() must plant the resolved docs dir on __SR_DOC_DIRS')
  assert.strictEqual(sr.docPathFor('wi-s', 'plan'), '/abs/proj-store/docs/wi-s/plan.md')

  // fail-safe: an absent/empty doc_dir must NOT plant a bogus entry (fallback stays legacy).
  delete globalThis.__SR_DOC_DIRS
  globalThis.agent = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'read startup state') {
      return [{ ok: true, stdout: JSON.stringify({ ok: true, spec_gate: 'passed', model_overrides: {}, doc_dir: '' }) }]
    }
    if (label === 'exec') {
      if (String(prompt).includes('recover_entry.py')) return [{ index: 0, ok: true, stdout: '{}' }]
      return [{ index: 0, ok: true, stdout: '{}' }]
    }
    return null
  }
  try { await sr.showrunner({ workItem: 'wi-s2' }) } catch (_) {}
  assert.strictEqual(sr.docPathFor('wi-s2', 'plan'), 'docs/superheroes/wi-s2/plan.md',
    'an empty doc_dir must leave the legacy fallback in place')
  delete globalThis.__SR_DOC_DIRS
}

// (f) contract: a startup response MISSING doc_dir is a mangled courier response — the Python
// side ALWAYS emits it ('' on failed resolution) — so the courier must retry, then fall back
// fail-safe, never silently plant nothing while the spec gate read "passes".
async function partMissingDocDirRetries() {
  let calls = 0
  globalThis.agent = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'read startup state') {
      calls += 1
      return [{ ok: true, stdout: JSON.stringify({ ok: true, spec_gate: 'passed', model_overrides: {} }) }]
    }
    if (label === 'exec') return [{ index: 0, ok: true, stdout: '{}' }]
    return null
  }
  const facts = await sr.readStartupState('wi-m')
  assert.strictEqual(calls, 2, 'a doc_dir-less startup response must be retried (mangled courier output)')
  assert.strictEqual(facts.spec_gate, 'unreadable', 'both attempts missing doc_dir -> the fail-safe fallback')
  assert.strictEqual(facts.doc_dir, '', 'the fallback carries the empty doc_dir shape')
}

async function main() {
  partFallback()
  partPlanted()
  await partAppendNotify()
  await partReviewRead()
  await partStartupPlants()
  await partMissingDocDirRetries()
  console.log('ok: front-half doc/marker/ledger paths are storage-mode-aware (planted dir + legacy fallback)')
}

main().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
