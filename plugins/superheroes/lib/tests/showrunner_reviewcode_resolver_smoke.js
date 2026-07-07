// plugins/superheroes/lib/tests/showrunner_reviewcode_resolver_smoke.js
// FIX A coverage (required): proves reviewCodePhase resolves the build worktree via the
// opts.resolveTarget seam and targets it — and fails CLOSED (park, not root-review) when the
// resolver returns null.
// Run: node plugins/superheroes/lib/tests/showrunner_reviewcode_resolver_smoke.js
const assert = require('assert')
const fs = require('fs'); const os = require('os'); const path = require('path')
const sr = require('../showrunner.js')

function jsonOut(obj) { return [{ ok: true, stdout: JSON.stringify(obj) }] }

function receiptFromPrompt(prompt) {
  let ctx = { receiptArtifact: 'stub', receiptCoverageDecisionIds: [] }
  const m = String(prompt || '').match(/Prompt context: (\{.*\})/s)
  if (m) { try { ctx = JSON.parse(m[1]) } catch (_) {} }
  return { artifact: ctx.receiptArtifact || 'stub', chain: [{ step: 'citation', evidence: 'reviewed citations' }, { step: 'reachability', evidence: 'validated call path' }, { step: 'missing-check', evidence: 'checked missing FRs' }, { step: 'tooling', evidence: 'smoke passed' }], coverageDecisionIds: ctx.receiptCoverageDecisionIds || [] }
}

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}

function fresh() { return fs.mkdtempSync(path.join(os.tmpdir(), 'rcresolver-')) }

async function main() {
  // ─────────────────────────────────────────────────────────────────────────
  // (a) With NO opts.worktree, reviewCodePhase resolves via opts.resolveTarget and TARGETS the
  //     resolved worktree: reviewCode config, verify gate, and reviewer prompts all target $wt.
  // ─────────────────────────────────────────────────────────────────────────
  const RESOLVED_WT = '/tmp/resolved-build-wt'
  const RESOLVED_HEAD = 'resolved-head-abc123'
  const RESOLVED_EVENTS_PATH = '/tmp/resolved-store/events.jsonl'
  let resolverCalled = false
  const resolveTarget = async (wi) => {
    resolverCalled = true
    assert.strictEqual(wi, 'wi-resolver-a', 'resolver receives the work-item')
    return { worktree: RESOLVED_WT, expectedHead: RESOLVED_HEAD, eventsPath: RESOLVED_EVENTS_PATH }
  }

  // Collect prompts to verify the resolved worktree is targeted.
  const seenPrompts = []
  global.agent = async (prompt, opts) => {
    seenPrompts.push({ prompt, label: (opts && opts.label) || '' })
    const label = (opts && opts.label) || ''
    // resolveHead + config now ride the exec courier (#118); return the expected head so it matches.
    if (label === 'resolve head' && prompt.includes('git -C') && prompt.includes(RESOLVED_WT)) return RESOLVED_HEAD + '\n'
    if (label === 'resolve head' && prompt.includes('git rev-parse')) return 'cwd-head-000\n'
    if (label === 'resume') return '1'
    if (label === 'read review config') return JSON.stringify({ verifyCommand: 'none', tiers: {} })
    if (label === 'run verify') return { command: 'none', returncode: 0, timedOut: false }
    if (label.startsWith('synthesis:')) return { verdicts: [] }
    if (label === 'stamp review coverage') return jsonOut({ ok: true })
    // a genuinely clean review needs a real verificationReceipt (else the receipt-fabrication fix
    // downgrades it to confidence:low -> cannot-certify).
    if (/^(architecture|code|security|test|premortem)-reviewer:/.test(label)) {
      return { findings: [], confidence: 'high', verificationReceipt: receiptFromPrompt(prompt) }
    }
    return { findings: [] }
  }
  // exec is used by the exec-based dumb-pipe (recordDeferred). Wire a no-op.
  global.agent.__execStub = true

  const r = await sr.reviewCodePhase('wi-resolver-a', {
    runDir: fresh(),
    resolveTarget,
  })

  assert.ok(resolverCalled, 'resolveTarget is called when opts.worktree is absent')
  assert.strictEqual(r.gate, 'passed', 'resolved-worktree path reaches clean -> passed')

  // The config command must have run in the resolved worktree (cd '/tmp/resolved-build-wt' &&).
  // (The resolver SEAM here returns no folded config, so the phase falls back to its own exec leaf;
  // the real resolveBuildTarget carries config inside the one 'resolve review target' gather.)
  const configPrompt = seenPrompts.find((p) => p.label === 'read review config' && p.prompt.includes('review_code_config.py'))
  assert.ok(configPrompt, 'config command was dispatched')
  assert.ok(
    configPrompt.prompt.includes(`cd '${RESOLVED_WT}'`) ||
    configPrompt.prompt.includes(`cd "${RESOLVED_WT}"`),
    `config resolves in the build worktree (got: ${configPrompt && configPrompt.prompt.slice(0, 200)})`
  )

  // The reviewers' targetSuffix must name the resolved worktree + head.
  const reviewerPrompt = seenPrompts.find((p) => /^(architecture|code|security|test|premortem)-reviewer:/.test(p.label))
  assert.ok(reviewerPrompt, 'a reviewer was dispatched')
  assert.ok(
    reviewerPrompt.prompt.includes(RESOLVED_WT),
    `reviewer prompt names the resolved worktree (got: ${reviewerPrompt && reviewerPrompt.prompt.slice(0, 300)})`
  )
  assert.ok(
    reviewerPrompt.prompt.includes(RESOLVED_HEAD),
    `reviewer prompt names the resolved head (got: ${reviewerPrompt && reviewerPrompt.prompt.slice(0, 300)})`
  )
  // Task 10 (FR-2/UFR-3): the resolver's eventsPath must ride the reviewer's prompt context so a
  // denied probe's permission_denied event lands in the run's OWN journal (not silently dropped).
  assert.ok(
    reviewerPrompt.prompt.includes(RESOLVED_EVENTS_PATH),
    `reviewer prompt context carries the resolved eventsPath (got: ${reviewerPrompt && reviewerPrompt.prompt.slice(0, 400)})`
  )

  const synthesisPrompt = seenPrompts.find((p) => p.label === 'synthesis:r1')
  assert.ok(synthesisPrompt, 'synthesis leaf was dispatched')
  assert.ok(
    synthesisPrompt.prompt.includes(`Absolute verification worktree: ${RESOLVED_WT}`),
    `synthesis prompt names the absolute worktree to verify files in (got: ${synthesisPrompt && synthesisPrompt.prompt.slice(0, 500)})`
  )

  // ─────────────────────────────────────────────────────────────────────────
  // (b) When resolveTarget returns null -> PARKS (changes-requested), names "could not resolve",
  //     and does NOT attempt to review root (no reviewer/config prompts dispatched).
  // ─────────────────────────────────────────────────────────────────────────
  const nullResolvePrompts = []
  global.agent = async (prompt, opts) => {
    nullResolvePrompts.push({ prompt, label: (opts && opts.label) || '' })
    return { findings: [] }  // should not reach reviewers
  }

  const parked = await sr.reviewCodePhase('wi-resolver-b', {
    runDir: fresh(),
    resolveTarget: async () => null,   // resolver fails -> must park
  })

  assert.strictEqual(parked.gate, 'changes-requested', 'null resolver -> park (changes-requested)')
  assert.ok(
    parked.phaseResult && parked.phaseResult.assumptions &&
    parked.phaseResult.assumptions.some((a) => a.includes('could not resolve the build worktree')),
    `park assumption names the resolution failure (got: ${JSON.stringify(parked.phaseResult && parked.phaseResult.assumptions)})`
  )
  // No reviewer, config, or verify prompts dispatched — the phase parks immediately, never reviews root.
  const reviewerDispatched = nullResolvePrompts.some((p) =>
    p.label.startsWith('branch-reviewer:') ||
    p.prompt.includes('review_code_config.py')
  )
  assert.ok(!reviewerDispatched, 'null resolver: no reviewer or config dispatched — root is NOT reviewed')

  // ─────────────────────────────────────────────────────────────────────────
  // (c) The REAL resolveBuildTarget (not the seam): it execs build_entry.py then `git rev-parse
  //     HEAD`, and fail-CLOSES on a 'created' outcome (a fresh empty build worktree is never
  //     certified). A 'reused' outcome resolves {worktree, expectedHead}; a missing outcome stays
  //     permissive (older build_entry.py). exec() dispatches via agent({label:'exec'}) and expects an
  //     array of {index, ok, stdout}; build_entry.py's stdout is a JSON object string.
  // ─────────────────────────────────────────────────────────────────────────
  function execStubForOutcome(outcome) {
    return async (prompt, opts) => {
      const label = (opts && opts.label) || ''
      if (label === 'resolve review target') {
        if (outcome === 'created') return jsonOut({ ok: false, error: 'fresh worktree created' })
        return jsonOut({ ok: true, worktree: '/tmp/real-build-wt', expectedHead: 'real-head-deadbeef' })
      }
      return { findings: [] }
    }
  }

  // 'reused' -> resolves the worktree + head
  global.agent = execStubForOutcome('reused')
  const reused = await sr.resolveBuildTarget('wi-real-reused')
  assert.deepStrictEqual(reused, { worktree: '/tmp/real-build-wt', expectedHead: 'real-head-deadbeef', config: null, cwdHead: null, eventsPath: null },
    `'reused' outcome resolves {worktree, expectedHead} (+ folded config/cwdHead/eventsPath, null when absent) (got: ${JSON.stringify(reused)})`)

  // 'created' -> fail-closed: returns null (never certifies a fresh empty build worktree)
  global.agent = execStubForOutcome('created')
  const created = await sr.resolveBuildTarget('wi-real-created')
  assert.strictEqual(created, null, "'created' outcome must fail-closed to null (empty worktree never certified)")

  // missing outcome (older build_entry.py) -> permissive, resolves normally
  global.agent = execStubForOutcome(undefined)
  const legacy = await sr.resolveBuildTarget('wi-real-legacy')
  assert.deepStrictEqual(legacy, { worktree: '/tmp/real-build-wt', expectedHead: 'real-head-deadbeef', config: null, cwdHead: null, eventsPath: null },
    `missing outcome stays permissive (got: ${JSON.stringify(legacy)})`)

  console.log('ok: FIX A — resolveTarget seam targets build worktree + null-resolver parks; resolveBuildTarget fail-closes on a created worktree')
}

main().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
