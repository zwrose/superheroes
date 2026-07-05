require('./_smoke_checkout_root.js')
// plugins/superheroes/lib/tests/build_phase_docpointer_smoke.js
// #222: the workhorse build + per-task reviewer prompts must carry the mode-aware ABSOLUTE tasks-doc
// pointer (docDirFor / __SR_DOC_DIRS, resolved storage-mode-aware at startup). Before this, the worker
// got only worktree/branch/task.id/task.title, so in OUT-OF-REPO storage (a bare-main build worktree)
// it had nothing to anchor to — it swept the owner's filesystem for the doc (tripping macOS TCC
// dialogs) or built from the one-line title, and the per-task reviewer's spec_compliance was equally
// blind. The #79 storage-mode seam covered review-crew/test-pilot prompts but never these. This smoke
// pins: (1) the resolved doc path + Read instruction + no-sweep guardrail ride BOTH the build prompt and
// the per-task reviewer prompt in out-of-repo mode; (2) a needs_context retry genuinely ADDS context
// (not the byte-identical prompt the recovery twin used to re-dispatch); (3) an unplanted doc dir falls
// back to the in-repo default (byte-identical to pre-#222).
'use strict'
const assert = require('assert')
global.log = () => {}

// A build worktree checked out from bare main — the out-of-repo-storage case where the tasks doc lives
// OUTSIDE the worktree, at an absolute path the worker cannot discover on its own.
const OUT = '/Users/owner/.superheroes-store/projects/deadbeef/docs/superheroes/wi'
const DOC = `${OUT}/tasks.md`
const GUARD = 'Never search the filesystem outside the build worktree'
const TASK = { id: '1', title: 'enumerate_dispatch' }

// Route agent() calls: the build worker + per-task reviewer by their unique labels (capturing the
// prompt); every dumb-pipe courier leaf (fence/gather/record) by the command embedded in its prompt.
function agentWith({ onBuild, onReview, buildResponder } = {}) {
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    if (/^implement task /.test(label)) {
      if (onBuild) onBuild(prompt)
      return buildResponder ? buildResponder() : { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } }
    }
    if (/^review task .+:r\d+$/.test(label)) {
      if (onReview) onReview(prompt)
      return { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }
    }
    if (prompt.includes('fence_cli.py')) return [{ ok: true, stdout: JSON.stringify({ ok: true }) }]
    if (prompt.includes('build_state_cli.py gather')) return [{ ok: true, stdout: JSON.stringify({ unmapped_commits: 0 }) }]
    if (prompt.includes('record-built')) return [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true, task: '1' }) }]
    if (prompt.includes('record-reviewed')) return [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true, task: '1' }) }]
    return [{ ok: true, stdout: '{}' }]
  }
}

const bp = require('../build_phase.js')

;(async () => {
  // (1) Out-of-repo storage: the resolved absolute doc path + Read instruction + guardrail ride BOTH
  //     the build prompt and the per-task reviewer prompt.
  globalThis.__SR_DOC_DIRS = { wi: OUT }
  let buildPrompt = null
  let reviewPrompt = null
  global.agent = agentWith({ onBuild: (p) => { buildPrompt = p }, onReview: (p) => { reviewPrompt = p } })
  let r = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '1', '/tmp/wt', 1)
  assert.strictEqual(r.parked, false, 'a clean task completes')
  assert.ok(buildPrompt.includes(DOC), `#222: the build prompt must carry the resolved tasks-doc path (${DOC})`)
  assert.ok(/Read it before writing code/.test(buildPrompt), '#222: the build prompt tells the worker to Read the real definition, not build from the title')
  assert.ok(buildPrompt.includes(GUARD), '#222: the build prompt carries the no-filesystem-sweep guardrail (the TCC-dialog class)')
  assert.ok(reviewPrompt.includes(DOC), '#222: the per-task reviewer prompt must carry the doc path (spec_compliance was unfalsifiable without it)')
  assert.ok(reviewPrompt.includes(GUARD), '#222: the reviewer prompt carries the no-filesystem-sweep guardrail')

  // (2) needs_context retry genuinely adds context. Worker fails needs_context on attempt 1, succeeds on
  //     attempt 2 (worker_recovery twin -> retry_with_context). The two build prompts must DIFFER (the
  //     defect: workerRecoveryTwin.decide re-dispatched the byte-identical prompt), and the retry must
  //     re-anchor to the doc path.
  const prompts = []
  let n = 0
  global.agent = agentWith({
    onBuild: (p) => prompts.push(p),
    buildResponder: () => { n += 1; return n === 1 ? { ok: false, signal: 'needs_context' } : { ok: true, signal: 'ok', evidence: {} } },
  })
  r = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '1', '/tmp/wt', 1)
  assert.strictEqual(r.parked, false, 'a needs_context task recovers and completes')
  assert.strictEqual(prompts.length, 2, 'the worker was re-dispatched exactly once after needs_context')
  assert.notStrictEqual(prompts[1], prompts[0], '#222: the retry prompt must NOT be byte-identical to the first (it must genuinely add context)')
  assert.ok(!/RETRY/.test(prompts[0]), 'the first attempt carries no retry note')
  assert.ok(/RETRY/.test(prompts[1]), '#222: the retry adds an explicit re-anchoring RETRY note')
  assert.ok(prompts[1].includes(DOC), 'the retry re-states the absolute doc path')

  // (3) Fallback: an unplanted __SR_DOC_DIRS resolves to the in-repo default (a direct smoke / a failed
  //     startup resolution) — byte-identical to the pre-#222 in-repo behavior.
  delete globalThis.__SR_DOC_DIRS
  let fallbackPrompt = null
  global.agent = agentWith({ onBuild: (p) => { fallbackPrompt = p } })
  r = await bp.buildOneTask('wi', 5, TASK, 'superheroes/wi-abc', '1', '/tmp/wt', 1)
  assert.strictEqual(r.parked, false, 'the fallback path still completes')
  assert.ok(fallbackPrompt.includes('docs/superheroes/wi/tasks.md'), '#222: an unplanted doc dir falls back to the in-repo default tasks.md path')

  console.log('ok: #222 workhorse build + per-task reviewer prompts carry the mode-aware tasks-doc pointer + guardrail; needs_context retry adds context')
})().catch((e) => { console.error('FAIL:', e.message || e, e.stack || ''); process.exit(1) })
