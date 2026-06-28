// plugins/superheroes/lib/tests/showrunner_reviewcode_resolver_smoke.js
// FIX A coverage (required): proves reviewCodePhase resolves the build worktree via the
// opts.resolveTarget seam and targets it — and fails CLOSED (park, not root-review) when the
// resolver returns null.
// Run: node plugins/superheroes/lib/tests/showrunner_reviewcode_resolver_smoke.js
const assert = require('assert')
const fs = require('fs'); const os = require('os'); const path = require('path')
const sr = require('../showrunner.js')

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
  let resolverCalled = false
  const resolveTarget = async (wi) => {
    resolverCalled = true
    assert.strictEqual(wi, 'wi-resolver-a', 'resolver receives the work-item')
    return { worktree: RESOLVED_WT, expectedHead: RESOLVED_HEAD }
  }

  // Collect prompts to verify the resolved worktree is targeted.
  const seenPrompts = []
  global.agent = async (prompt, opts) => {
    seenPrompts.push({ prompt, label: (opts && opts.label) || '' })
    const label = (opts && opts.label) || ''
    // resolveHead for head-mismatch check: return the expected head so it matches.
    if (label === 'lib' && prompt.includes('git -C') && prompt.includes(RESOLVED_WT)) return RESOLVED_HEAD + '\n'
    if (label === 'resume') return '1'
    if (label === 'lib' && prompt.includes('review_code_config.py')) return { verifyCommand: 'none', tiers: {} }
    if (label && label.startsWith('verify')) return { command: 'none', returncode: null, timedOut: false }
    if (label && label.startsWith('synthesis')) return { verdicts: [] }
    if (label === 'lib' && prompt.includes('prov_entry.py')) return { ok: true }
    if (label === 'lib' && prompt.includes('readout_post.py')) return { posted: true, recorded: true }
    if (label === 'readout') return '## Review loop — done'
    if (/^(architecture|code|security|test|premortem)-reviewer/.test(label)) return { findings: [] }
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
  const configPrompt = seenPrompts.find((p) => p.label === 'lib' && p.prompt.includes('review_code_config.py'))
  assert.ok(configPrompt, 'config command was dispatched')
  assert.ok(
    configPrompt.prompt.includes(`cd '${RESOLVED_WT}'`) ||
    configPrompt.prompt.includes(`cd "${RESOLVED_WT}"`),
    `config resolves in the build worktree (got: ${configPrompt && configPrompt.prompt.slice(0, 200)})`
  )

  // The reviewers' targetSuffix must name the resolved worktree + head.
  const reviewerPrompt = seenPrompts.find((p) => /^(architecture|code|security|test|premortem)-reviewer/.test(p.label))
  assert.ok(reviewerPrompt, 'a reviewer was dispatched')
  assert.ok(
    reviewerPrompt.prompt.includes(RESOLVED_WT),
    `reviewer prompt names the resolved worktree (got: ${reviewerPrompt && reviewerPrompt.prompt.slice(0, 300)})`
  )
  assert.ok(
    reviewerPrompt.prompt.includes(RESOLVED_HEAD),
    `reviewer prompt names the resolved head (got: ${reviewerPrompt && reviewerPrompt.prompt.slice(0, 300)})`
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
    /^(architecture|code|security|test|premortem)-reviewer/.test(p.label) ||
    (p.label === 'lib' && p.prompt.includes('review_code_config.py'))
  )
  assert.ok(!reviewerDispatched, 'null resolver: no reviewer or config dispatched — root is NOT reviewed')

  console.log('ok: FIX A — resolveTarget seam targets build worktree + null-resolver parks (never reviews root)')
}

main().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
