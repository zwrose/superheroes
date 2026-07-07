// Smoke (#211 PR 3 — the JS reassembler's regression net): the receipt+chunk read path is the review
// loop's EMERGENCY FALLBACK (an entry-gather answer that unexpectedly outgrows the receipt bound —
// a large coverage-decision list). Its JS consumer `_readReceiptText` (driven via the exported
// `gatherReviewSetup`) reassembles RAW-TEXT chunks and enforces three fail-closed guards: per-chunk
// `contentHash == receipt.contentHash` (stale/wrong file), per-chunk `chunkHash == contentHash(text)`
// (retype), and the final `contentHash(reassembly) == receipt.contentHash` (partial/dropped chunk).
// The Python `read_chunk` side is unit-tested (test_review_memory.py); this pins the JS side by
// FORCING the receipt branch — the gather answer is mocked to a receipt over a real staged blob, and
// read-chunk hits the REAL `review_memory.py read-chunk` (raw-text slices) via defaultIo. Mangling a
// chunk (either guard) must reassemble to null → the loop parks, never a truncated-but-parsed setup.
'use strict'
const assert = require('assert')
const fs = require('fs'); const os = require('os'); const path = require('path')
const { reviewPanel, gatherReviewSetup } = require('../review_panel_shell.js')
const { defaultIo } = require('../io_seam.js')

globalThis.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
globalThis.log = () => {}
globalThis.synthesisLeaf = async () => ({ verdicts: [], usage: { total: 1 } })
globalThis.recordDeferred = async () => {}
globalThis.agent = async () => null

function freshDir() { return fs.mkdtempSync(path.join(os.tmpdir(), 'rl-fallback-')) }

// A valid #211 gather DECISION blob, padded past a single 300-char chunk so the receipt path
// exercises the multi-chunk reassembly loop (not a one-shot read).
function gatherBlob() {
  return {
    ok: true,
    resume: { ok: true, state: 'missing', round: 1, contentHash: defaultIo.contentHash(''),
      extras: null, confirmationPending: false, markedRound: null, roundCount: 0 },
    plan: { ok: true, round: 1, roundKind: 'baseline', enterConfirmation: false,
      escalationPolicy: 'deep-only', dimensions: { code: { action: 'run', tier: 'reviewer-deep' } },
      carried: {}, latestCoverageDecisionIds: [] },
    coverage: { ok: true, decisions: [], contentHash: defaultIo.contentHash('') },
    deferredSet: {},
    _pad: 'p'.repeat(2200),
  }
}

// io shim: emit a review-setup-gather RECEIPT over a real staged blob and, optionally, mangle every
// read-chunk answer. Everything else — the coverage-target resolve, read-chunk, persist, tally — is
// REAL python (defaultIo), so read-chunk hits the real raw-text `read_chunk` and _readReceiptText
// does the real reassembly. `mangle`: 'retype' corrupts text and leaves chunkHash stale (per-chunk
// guard); 'backstop' corrupts text AND recomputes chunkHash so per-chunk passes and only the final
// reassembly hash can catch it.
function makeIo({ mangle } = {}) {
  const chunkReads = []
  const io = Object.assign({}, defaultIo, {
    async runHelper(cmd, args, opts) {
      const line = (args || []).join(' ')
      if (line.includes('review_setup_gather.py') && line.includes('gather')) {
        const outPath = args[args.indexOf('--out-path') + 1]
        const blob = JSON.stringify(gatherBlob())
        fs.writeFileSync(outPath, blob)
        return { ok: true, stdout: JSON.stringify({ ok: true, receipt: 'review-setup-gather',
          path: outPath, contentHash: defaultIo.contentHash(blob), chunkSize: 300,
          bytes: Buffer.byteLength(blob), chars: blob.length }) }
      }
      if (line.includes('review_memory.py') && line.includes('read-chunk')) {
        chunkReads.push(line)
        const out = await defaultIo.runHelper(cmd, args, opts)
        if (mangle) {
          try {
            const c = JSON.parse(out.stdout)
            if (c && c.ok && typeof c.text === 'string' && c.text.length) {
              c.text = c.text + 'X'
              if (mangle === 'backstop') c.chunkHash = defaultIo.contentHash(c.text)
              return { ok: true, stdout: JSON.stringify(c) }
            }
          } catch (_) { /* fall through to the raw answer */ }
        }
        return out
      }
      return defaultIo.runHelper(cmd, args, opts)
    },
  })
  return { io, chunkReads }
}

async function main() {
  // (1) HAPPY: the receipt branch fires, real read-chunk ships raw-text slices, and _readReceiptText
  // reassembles the gather DECISION byte-identically over multiple chunks.
  {
    const dir = freshDir()
    const { io, chunkReads } = makeIo({})
    globalThis.io = io
    const setup = await gatherReviewSetup({ runDir: dir, reviewerSet: ['code'], context: {},
      legKind: { panel: true, code: false }, ioApi: io })
    assert.ok(setup && setup.resume && setup.resume.round === 1, 'receipt path must reassemble the gather blob')
    assert.strictEqual(setup.plan.roundKind, 'baseline', 'reassembled plan survives round-trip')
    assert.deepStrictEqual(setup.plan.dimensions, { code: { action: 'run', tier: 'reviewer-deep' } })
    assert.ok(chunkReads.length >= 2, `multi-chunk reassembly must actually run (got ${chunkReads.length} read-chunk calls)`)
  }

  // (2) FAIL-CLOSED via the per-chunk chunkHash guard: a retyped slice (stale chunkHash) never
  // reassembles — gatherReviewSetup returns null (the shell then parks round-memory-unreadable).
  {
    const dir = freshDir()
    const { io, chunkReads } = makeIo({ mangle: 'retype' })
    globalThis.io = io
    const setup = await gatherReviewSetup({ runDir: dir, reviewerSet: ['code'], context: {},
      legKind: { panel: true, code: false }, ioApi: io })
    assert.strictEqual(setup, null, 'a retyped chunk (stale chunkHash) must fail closed, never a partial setup')
    assert.ok(chunkReads.length >= 1, 'the reader must have attempted the receipt path')
  }

  // (3) FAIL-CLOSED via the final reassembly-hash backstop: a slice whose text AND chunkHash are both
  // recomputed passes every per-chunk check, so ONLY the final contentHash(reassembly) catches it.
  {
    const dir = freshDir()
    const { io } = makeIo({ mangle: 'backstop' })
    globalThis.io = io
    const setup = await gatherReviewSetup({ runDir: dir, reviewerSet: ['code'], context: {},
      legKind: { panel: true, code: false }, ioApi: io })
    assert.strictEqual(setup, null, 'a per-chunk-valid but globally-wrong reassembly must fail the final hash backstop')
  }

  // (4) END-TO-END park: a mangled receipt fallback drives reviewPanel to a cannot-certify park with
  // the stable round-memory-unreadable reason — never a fresh round on an unverifiable seed.
  {
    const dir = freshDir()
    const { io } = makeIo({ mangle: 'retype' })
    globalThis.io = io
    globalThis.reviewerAgent = async () => ({ findings: [], confidence: 'high', usage: { total: 1 } })
    const v = await reviewPanel({ reviewerSet: ['code'], context: {}, rubric: 'r', runKey: dir,
      runDir: dir, fixStep: async () => ({ fixed: [], changedSubjects: ['Code'], coverageDecisions: [] }),
      maxRounds: 7, legKind: { panel: true, code: false } })
    assert.strictEqual(v.terminal, 'cannot-certify', `mangled fallback must park (got ${v.terminal})`)
    assert.strictEqual(v.reason, 'round-memory-unreadable', `stable park reason (got ${v.reason})`)
  }

  console.log('ok: the #211 raw-text receipt fallback reassembles happy and fails closed on either guard')
}

main().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
