// plugins/superheroes/lib/tests/showrunner_test_pilot_phase_smoke.js
require('./_smoke_checkout_root.js')
const assert = require('assert')

global.agent = async (prompt) => {
  if (prompt.includes('phase_step_cli.py')) {
    return { action: 'park_unexpected_gate', reason: 'browser verification failed' }
  }
  if (prompt.includes('journal_entry.py')) return { ok: true }
  return { ok: true }
}
global.log = () => {}

const sr = require('../showrunner.js')
const {
  testPilotPhase,
  collectAppBugFailures,
  reconcileCommittedMutations,
} = require('../test_pilot_phase.js')

function baseContext(extra) {
  return Object.assign({
    branch: 'codex/example',
    head: 'abc123',
    profile: { baseUrl: 'http://localhost:3000' },
    browserTool: { kind: 'mcp' },
    allowedOrigins: ['http://localhost:3000'],
  }, extra || {})
}

function applicableContext(extra) {
  return baseContext(Object.assign({
    diff: { files: ['src/app.tsx'] },
    detectors: { browser: true },
  }, extra || {}))
}

function courierStdout(value) {
  return { ok: true, stdout: JSON.stringify(value) }
}

function applicableDeps(extra) {
  return Object.assign({
    resolveContext: async () => applicableContext(),
    derivePlan: async () => ({
      records: [{
        branch: 'codex/example',
        steps: [{ id: 's1', instruction: 'open page', expected: 'page loads', scenarioIds: ['scenario-a'] }],
      }],
    }),
    preparePlanRecords: async (_plan, context) => ({
      action: 'ready',
      records: [{
        branch: context.branch,
        steps: [{ id: 's1', instruction: 'open page', expected: 'page loads', scenarioIds: ['scenario-a'] }],
      }],
    }),
    prepareArtifacts: async () => ({ ok: true, artifacts: { plan: 'plan.md', results: 'results.md' }, posting: { ok: true } }),
    resolveServer: async (_context) => ({ verdict: 'ready_external', baseUrl: 'http://localhost:3000', allowedOrigins: ['http://localhost:3000'], teardownRequired: false }),
    withManagedServer: async (serverContext, run) => run(serverContext),
    seedRecords: async (_records) => ({ action: 'ready_for_browser', status: { seeded: true } }),
    runBrowserPass: async () => ({
      source: 'browser',
      baseUrl: 'http://localhost:3000',
      steps: [{ id: 's1', status: 'passed', notes: 'observed page load' }],
    }),
    reviewCode: async (_workItem, opts) => ({
      gate: 'passed',
      head: opts.expectedHead,
      changed: false,
      reviewCoverageHead: opts.expectedHead,
      verifyPassedHead: opts.expectedHead,
    }),
    restoreBaseline: async (_records, details) => ({ ok: true, baseline: { head: details.head, restored: true } }),
    ensureFinalArtifacts: async (payload) => ({ ok: true, artifacts: Object.assign({}, payload.artifacts, { results: 'final-results.md' }), posting: { ok: true } }),
    publishReady: async (_workItem, head) => ({ ok: true, read_back: true, remotePr: { branch: 'codex/example', head } }),
    writeStatus: async () => ({ ok: true, read_back: true }),
  }, extra || {})
}

// #411: the folded prepare path (deps.prepareTestRun present) collapses artifacts+server+seed into a
// single leaf. On success it returns { ok:true, artifactResult, serverContext, seedResult }; on failure
// the showrunner folds it to { action:'park', reason:<the leaf's real diagnosis> } (or a raw
// { ok:false, reason }). These deps drive that folded path.
function foldedDeps(extra) {
  return applicableDeps(Object.assign({
    prepareTestRun: async () => ({
      ok: true,
      artifactResult: { ok: true, artifacts: { plan: 'plan.md', results: 'results.md' }, posting: { ok: true } },
      serverContext: { verdict: 'ready_external', baseUrl: 'http://localhost:3000', allowedOrigins: ['http://localhost:3000'], teardownRequired: false },
      seedResult: { action: 'ready_for_browser', status: { seeded: true } },
    }),
  }, extra || {}))
}

// #411 (a): a folded { action:'park', reason } must surface the leaf's own honest reason VERBATIM in
// the low-confidence terminal — not the generic "artifact preparation returned no result" that masked
// the live specimen's argparse usage error (weekly-eats error-tracking run, 2026-07-13, spine 0.12.0).
async function foldedParkReasonSurfacesVerbatimInLowTerminal() {
  const realReason = 'usage: test_pilot_server_config_cli.py resolve [-h] --profile-json PROFILE_JSON …'
  let browserRan = false
  const out = await testPilotPhase('wi', 3, foldedDeps({
    prepareTestRun: async () => ({ action: 'park', reason: realReason }),
    runBrowserPass: async () => { browserRan = true },
  }))
  assert.strictEqual(out.confidence, 'low')
  assert.strictEqual(out.assumptions[0], realReason, 'the folded park reason must surface verbatim, not be masked')
  assert.strictEqual(browserRan, false)
}

// #411 (b): a raw folded { ok:false, reason } (the inner subprocess exception shape) must surface its
// reason the same way.
async function foldedOkFalseReasonSurfacesInLowTerminal() {
  const realReason = 'command failed: transport corruption in prepare exec courier'
  let browserRan = false
  const out = await testPilotPhase('wi', 3, foldedDeps({
    prepareTestRun: async () => ({ ok: false, reason: realReason }),
    runBrowserPass: async () => { browserRan = true },
  }))
  assert.strictEqual(out.confidence, 'low')
  assert.strictEqual(out.assumptions[0], realReason)
  assert.strictEqual(browserRan, false)
}

// #411: a folded top-level { confidence:'low', reason } (the module's own low() shape) is the third
// "not ready" signal the sibling readiness predicates honor. The guard catches it too, so its reason is
// surfaced rather than masked by the null-arm "returned no result".
async function foldedConfidenceLowReasonSurfacesInLowTerminal() {
  const realReason = 'prepare leaf is low-confidence: could not resolve managed server command argv'
  let browserRan = false
  const out = await testPilotPhase('wi', 3, foldedDeps({
    prepareTestRun: async () => ({ confidence: 'low', reason: realReason }),
    runBrowserPass: async () => { browserRan = true },
  }))
  assert.strictEqual(out.confidence, 'low')
  assert.strictEqual(out.assumptions[0], realReason)
  assert.strictEqual(browserRan, false)
}

// #411: a folded park with NO reason falls back to the dedicated default, not the misleading
// "returned no result".
async function foldedParkWithoutReasonUsesPreparationDefault() {
  const out = await testPilotPhase('wi', 3, foldedDeps({
    prepareTestRun: async () => ({ action: 'park' }),
  }))
  assert.strictEqual(out.confidence, 'low')
  assert.strictEqual(out.assumptions[0], 'test-pilot preparation parked')
}

// #411 (c): the existing null / missing-field readiness messages are UNCHANGED — a folded value that is
// genuinely absent (or missing its result fields) still reports "returned no result". This is not a park
// signal (no action:'park' / ok:false), so the new guard must not swallow it.
async function foldedNullKeepsReturnedNoResultMessage() {
  const out = await testPilotPhase('wi', 3, foldedDeps({
    prepareTestRun: async () => null,
  }))
  assert.strictEqual(out.confidence, 'low')
  assert.match(out.assumptions[0], /artifact preparation returned no result/)
}

// #411: the happy folded path is untouched — a full { ok:true, artifactResult, serverContext, seedResult }
// still proceeds to a high-confidence terminal (the guard's ok:true is not a park).
async function foldedHappyPathStillProceedsToHigh() {
  const out = await testPilotPhase('wi', 3, foldedDeps())
  assert.strictEqual(out.confidence, 'high')
}

async function notApplicableProceeds() {
  const statuses = []
  const out = await testPilotPhase('wi', 3, {
    resolveContext: async () => baseContext({ diff: { files: ['docs/readme.md'] }, detectors: {} }),
    writeStatus: async (status) => { statuses.push(status); return { ok: true, read_back: true } },
  })
  assert.strictEqual(out.confidence, 'high')
  assert.strictEqual(statuses.length, 1)
  assert.strictEqual(statuses[0].verdict, 'not_applicable')
  assert.strictEqual(statuses[0].head, 'abc123')
}

async function productionWrapperHandlesNotApplicableWithoutMissingLeaf() {
  const previousAgent = global.agent
  global.agent = async (prompt, opts) => {
    if (opts && opts.label === 'resolve review target') {
      return [{ ok: true, stdout: JSON.stringify({ ok: true, worktree: '/build/wt-pw', expectedHead: 'pw-head' }) }]
    }
    if (prompt.includes('test_pilot_context_cli.py resolve')) {
      return courierStdout(baseContext({
        workItem: 'wi',
        generation: 3,
        pr: { number: 7 },
        diff: { files: ['docs/readme.md'] },
        detectors: {},
      }))
    }
    if (prompt.includes('test_pilot_status_cli.py write')) {
      return courierStdout({ ok: true, read_back: true })
    }
    return previousAgent(prompt, opts)
  }
  try {
    const out = await sr.defaultTestPilotPhase('wi', 3)
    assert.strictEqual(out.confidence, 'high')
  } finally {
    global.agent = previousAgent
  }
}

async function productionManagedServerUsesLifecycleHelperAroundBrowserRun() {
  const previousAgent = global.agent
  const commands = []
  let browserRan = false
  global.agent = async (prompt) => {
    if (prompt.includes('test_pilot_server_config_cli.py launch')) {
      commands.push('launch')
      return {
        verdict: 'managed',
        shell: false,
        baseUrl: 'http://localhost:3000',
        allowedOrigins: ['http://localhost:3000'],
        handle: { pid: 123, port: 3000 },
      }
    }
    if (prompt.includes('test_pilot_server_config_cli.py finish')) {
      commands.push('finish')
      return { source: 'browser', steps: [{ id: 's1', status: 'passed' }] }
    }
    return previousAgent(prompt)
  }
  try {
    const deps = sr.testPilotDeps('wi', 3)
    const out = await deps.withManagedServer(
      { verdict: 'managed', shell: false, baseUrl: 'http://localhost:3000', allowedOrigins: ['http://localhost:3000'] },
      async (activeServer) => {
        browserRan = true
        assert.strictEqual(activeServer.handle.pid, 123)
        return { source: 'browser', steps: [{ id: 's1', status: 'passed' }] }
      },
    )
    assert.deepStrictEqual(commands, ['launch', 'finish'])
    assert.strictEqual(browserRan, true)
    assert.strictEqual(out.source, 'browser')
  } finally {
    global.agent = previousAgent
  }
}

// #410: io.writeFile now THROWS on a persistently-unverified courier write. withManagedServer's finish
// artifacts (server-finish-context / server-finish-outcome) are ADVISORY teardown bookkeeping — a
// transport throw on them must NOT (a) discard a successful run outcome, nor (b) mask the ORIGINAL run
// error on the exception path. Injecting a global.io whose writeFile throws for the finish artifacts (but
// not the launch context) exercises exactly that.
async function managedServerFinishWriteThrowPreservesOutcomeAndError() {
  const prevIo = global.io
  const prevAgent = global.agent
  const commands = []
  global.io = {
    join: (...a) => a.join('/'),
    tmpdir: () => '/tmp',
    async mkdirp() {},
    async readText() { return '' },
    async readJson(_p, d) { return d },
    async writeFile(p) { if (String(p).includes('server-finish')) throw new Error('io:write to ' + p + ' unverified after retry (no __SR_WROTE marker)') },
  }
  global.agent = async (prompt) => {
    if (prompt.includes('test_pilot_server_config_cli.py launch')) {
      commands.push('launch')
      return { verdict: 'managed', shell: false, baseUrl: 'http://localhost:3000', allowedOrigins: ['http://localhost:3000'], handle: { pid: 7, port: 3000 } }
    }
    if (prompt.includes('test_pilot_server_config_cli.py finish')) { commands.push('finish'); return { source: 'browser', echoed: true } }
    return { ok: true }
  }
  try {
    const deps = sr.testPilotDeps('wi', 3)
    const serverCtx = { verdict: 'managed', shell: false, baseUrl: 'http://localhost:3000', allowedOrigins: ['http://localhost:3000'] }
    // (1) run() SUCCEEDS but the finish-context write throws — the successful outcome is NOT discarded.
    const out = await deps.withManagedServer(serverCtx, async () => ({ source: 'browser', steps: [{ id: 's1', status: 'passed' }] }))
    assert.strictEqual(out && out.source, 'browser', '#410: a finish-artifact write throw must not discard the successful run outcome')
    // (2) run() THROWS — the ORIGINAL run error propagates, never masked by the finish-write transport throw.
    let threw = null
    try { await deps.withManagedServer(serverCtx, async () => { throw new Error('browser boom') }) } catch (e) { threw = e }
    assert.ok(threw && /browser boom/.test(String(threw.message)),
      '#410: a run() failure propagates the ORIGINAL error, not the finish-write transport error')
  } finally {
    if (prevIo === undefined) delete global.io; else global.io = prevIo
    global.agent = prevAgent
  }
}

async function uncertainApplicabilityParks() {
  const out = await testPilotPhase('wi', 3, {
    resolveContext: async () => baseContext({ diff: { files: ['Makefile'] }, detectors: {} }),
    writeStatus: async () => { throw new Error('status should not be written') },
  })
  assert.strictEqual(out.confidence, 'low')
  assert.match(out.assumptions[0], /uncertain applicability/)
}

async function emptyApplicablePlanParks() {
  let browserRan = false
  const out = await testPilotPhase('wi', 3, {
    resolveContext: async () => applicableContext(),
    derivePlan: async () => ({ records: [] }),
    runBrowserPass: async () => { browserRan = true },
  })
  assert.strictEqual(out.confidence, 'low')
  assert.match(out.assumptions[0], /plan is empty/)
  assert.strictEqual(browserRan, false)
}

async function missingSetupParksBeforeBrowser() {
  let browserRan = false
  const out = await testPilotPhase('wi', 3, {
    resolveContext: async () => applicableContext({ profile: null }),
    runBrowserPass: async () => { browserRan = true },
  })
  assert.strictEqual(out.confidence, 'low')
  assert.match(out.assumptions[0], /calibration\/profile/)
  assert.strictEqual(browserRan, false)
}

async function missingBrowserToolParksBeforeBrowser() {
  let browserRan = false
  const out = await testPilotPhase('wi', 3, {
    resolveContext: async () => applicableContext({ browserTool: null }),
    runBrowserPass: async () => { browserRan = true },
  })
  assert.strictEqual(out.confidence, 'low')
  assert.match(out.assumptions[0], /browser tool/)
  assert.strictEqual(browserRan, false)
}

async function applicableFlowOrdersDurableMilestones() {
  const calls = []
  const statuses = []
  const out = await testPilotPhase('wi', 3, applicableDeps({
    derivePlan: async () => { calls.push('derivePlan'); return { records: [{
      branch: 'codex/example',
      steps: [{ id: 's1', instruction: 'open page', expected: 'page loads', scenarioIds: ['scenario-a'] }],
    }] } },
    preparePlanRecords: async (plan) => { calls.push('preparePlanRecords'); return { action: 'ready', records: plan.records } },
    prepareArtifacts: async () => { calls.push('prepareArtifacts'); return { ok: true, artifacts: { plan: 'plan.md', results: 'results.md' }, posting: { ok: true } } },
    resolveServer: async () => { calls.push('resolveServer'); return { verdict: 'ready_external', baseUrl: 'http://localhost:3000', allowedOrigins: ['http://localhost:3000'], teardownRequired: false } },
    seedRecords: async () => { calls.push('seedRecords'); return { action: 'ready_for_browser', status: { seeded: true } } },
    runBrowserPass: async (browserContext) => {
      calls.push('runBrowserPass')
      assert.strictEqual(browserContext.baseUrl, 'http://localhost:3000')
      assert.deepStrictEqual(browserContext.allowedOrigins, ['http://localhost:3000'])
      return { source: 'browser', baseUrl: 'http://localhost:3000', steps: [{ id: 's1', status: 'passed', notes: 'observed page load' }] }
    },
    writeStatus: async (status) => { calls.push(`writeStatus:${status.milestone || status.verdict}`); statuses.push(status); return { ok: true, read_back: true } },
  }))
  assert.strictEqual(out.confidence, 'high')
  assert.deepStrictEqual(calls, [
    'derivePlan',
    'writeStatus:plan-derived',
    'preparePlanRecords',
    'writeStatus:plan-records-ready',
    'prepareArtifacts',
    'writeStatus:artifacts-ready',
    'resolveServer',
    'writeStatus:server-ready',
    'seedRecords',
    'writeStatus:seed-ready',
    'runBrowserPass',
    'writeStatus:applicable',
  ])
  assert.strictEqual(statuses[statuses.length - 1].verdict, 'applicable')
  assert.strictEqual(statuses[statuses.length - 1].records[0].stepId, 's1')
}

async function invalidPreparedRecordsParkBeforeArtifactsSeedAndBrowser() {
  const calls = []
  const out = await testPilotPhase('wi', 3, applicableDeps({
    preparePlanRecords: async () => ({ action: 'park', reason: 'plan validation failed: bad record' }),
    prepareArtifacts: async () => { calls.push('artifacts') },
    seedRecords: async () => { calls.push('seed') },
    runBrowserPass: async () => { calls.push('browser') },
  }))
  assert.strictEqual(out.confidence, 'low')
  assert.match(out.assumptions[0], /plan validation failed/)
  assert.deepStrictEqual(calls, [])
}

async function generatedInRepoPlanStoreParksBeforeWorktreeMutation() {
  const calls = []
  const out = await testPilotPhase('wi', 3, applicableDeps({
    derivePlan: async () => ({ records: [{
      branch: 'codex/example',
      store: { location: 'in_repo', generated: true },
      steps: [{ id: 's1', instruction: 'open page', expected: 'page loads' }],
    }] }),
    preparePlanRecords: async () => { calls.push('preparePlanRecords') },
    seedRecords: async () => { calls.push('seed') },
  }))
  assert.strictEqual(out.confidence, 'low')
  assert.match(out.assumptions[0], /generated in-repo plan store/)
  assert.deepStrictEqual(calls, [])
}

async function resumePreservesHumanStateAndAvoidsDuplicateIds() {
  let preparedRecords
  const previous = [{
    stepId: 's1',
    checkboxState: 'checked',
    humanChecked: true,
    status: 'passed',
    browserExecuted: true,
  }]
  const out = await testPilotPhase('wi', 3, applicableDeps({
    readStatus: async () => ({ verdict: 'applicable', records: previous }),
    derivePlan: async () => ({ records: [{
      branch: 'codex/example',
      steps: [
        { id: 's1', instruction: 'open page again', expected: 'page loads', scenarioIds: ['scenario-a'] },
        { id: 's2', instruction: 'click action', expected: 'action completes', scenarioIds: ['scenario-b'] },
      ],
    }] }),
    preparePlanRecords: async (plan) => { preparedRecords = plan.records; return { action: 'ready', records: plan.records } },
    runBrowserPass: async () => ({
      source: 'browser',
      baseUrl: 'http://localhost:3000',
      steps: [
        { id: 's1', status: 'passed', notes: 'observed page load' },
        { id: 's2', status: 'passed', notes: 'observed action' },
      ],
    }),
  }))
  assert.strictEqual(out.confidence, 'high')
  assert.strictEqual(preparedRecords[0].steps[0].checkboxState, 'checked')
  const ids = preparedRecords.flatMap((record) => record.steps.map((step) => step.id))
  assert.deepStrictEqual(ids, ['s1', 's2'])
}

async function skippedStepRequiresPreservationFields() {
  const out = await testPilotPhase('wi', 3, applicableDeps({
    derivePlan: async () => ({ records: [{
      branch: 'codex/example',
      steps: [{ id: 's1', instruction: 'open page', expected: 'page loads', status: 'skipped', removalReason: 'no longer reachable' }],
    }] }),
  }))
  assert.strictEqual(out.confidence, 'low')
  assert.match(out.assumptions[0], /skipped step preservation/)
}

async function managedServerTearsDownOnBrowserFailure() {
  const calls = []
  const out = await testPilotPhase('wi', 3, applicableDeps({
    resolveServer: async () => ({
      verdict: 'managed',
      command: ['npm', 'run', 'dev'],
      shell: false,
      baseUrl: 'http://localhost:3000',
      allowedOrigins: ['http://localhost:3000'],
      teardownRequired: true,
    }),
    withManagedServer: async (serverContext, run) => {
      assert.strictEqual(serverContext.shell, false)
      calls.push('start')
      try {
        return await run(serverContext)
      } finally {
        calls.push('teardown')
      }
    },
    runBrowserPass: async () => { throw new Error('browser crashed') },
  }))
  assert.strictEqual(out.confidence, 'low')
  assert.match(out.assumptions[0], /browser execution failed/)
  assert.deepStrictEqual(calls, ['start', 'teardown'])
}

async function offOriginBrowserResultsPark() {
  const out = await testPilotPhase('wi', 3, applicableDeps({
    runBrowserPass: async () => ({
      source: 'browser',
      baseUrl: 'http://evil.example',
      steps: [{ id: 's1', status: 'passed', notes: 'off origin' }],
    }),
  }))
  assert.strictEqual(out.confidence, 'low')
  assert.match(out.assumptions[0], /off-origin/)
}

async function nonBrowserEvidenceParksBeforeReadiness() {
  const out = await testPilotPhase('wi', 3, applicableDeps({
    runBrowserPass: async () => ({ source: 'api', steps: [{ id: 's1', status: 'passed' }] }),
  }))
  assert.strictEqual(out.confidence, 'low')
  assert.match(out.assumptions[0], /browser-derived evidence/)
}

async function budgetExhaustedParksBeforeBrowser() {
  let browserRan = false
  const out = await testPilotPhase('wi', 3, applicableDeps({
    budgetCheck: async () => ({ ok: false, reason: 'test-pilot budget exhausted before browser-pass' }),
    runBrowserPass: async () => { browserRan = true; return { source: 'browser', baseUrl: 'http://localhost:3000', steps: [] } },
  }))
  assert.strictEqual(out.confidence, 'low')
  assert.match(out.assumptions[0], /budget exhausted/)
  assert.strictEqual(browserRan, false)
}

async function appBugFailuresDispatchOneFixBatchAndRerunWholePlan() {
  const budgetChecks = []
  const browserScopes = []
  const statuses = []
  let dispatchFailures
  let pass = 0
  const out = await testPilotPhase('wi', 3, applicableDeps({
    derivePlan: async () => ({
      records: [{
        branch: 'codex/example',
        steps: [
          { id: 's1', instruction: 'save settings', expected: 'settings save', scenarioIds: ['scenario-a'] },
          { id: 's2', instruction: 'open profile', expected: 'profile opens', scenarioIds: ['scenario-b'] },
        ],
      }],
    }),
    preparePlanRecords: async (plan) => ({ action: 'ready', records: plan.records }),
    budgetCheck: async (phase, payload) => {
      budgetChecks.push({ phase, counts: payload.counts })
      return { ok: true }
    },
    runBrowserPass: async (browserContext) => {
      browserScopes.push(browserContext.rerunScope || { action: 'initial' })
      pass += 1
      if (pass === 1) {
        return {
          source: 'browser',
          baseUrl: 'http://localhost:3000',
          steps: [
            { id: 's1', status: 'failed', failureType: 'app_bug', summary: 'save crashed' },
            { id: 's2', status: 'failed', failureType: 'app_bug', summary: 'profile crashed' },
          ],
        }
      }
      return {
        source: 'browser',
        baseUrl: 'http://localhost:3000',
        steps: [
          { id: 's1', status: 'passed' },
          { id: 's2', status: 'passed' },
        ],
      }
    },
    retryDecide: async (_passResult, _history, changedFiles) => {
      if (changedFiles) return { action: 'rerun_all', failedStepIds: ['s1', 's2'] }
      return { action: 'fix_batch', failedStepIds: ['s1', 's2'], summary: 'Fix browser app failures' }
    },
    dispatchFixBatch: async (failures) => {
      dispatchFailures = failures
      return { ok: true, commitShas: ['fix111'], changedFiles: ['web/settings.js'], head: 'fix111' }
    },
    ensureCleanWorktreeAfterFix: async () => ({ ok: true }),
    reconcileCommittedMutations: async () => ({ ok: true, commitShas: ['fix111'], head: 'fix111' }),
    writeStatus: async (status) => { statuses.push(status); return { ok: true, read_back: true } },
  }))

  assert.strictEqual(out.confidence, 'high')
  assert.deepStrictEqual(dispatchFailures.map((failure) => failure.stepId), ['s1', 's2'])
  assert.deepStrictEqual(budgetChecks.map((entry) => entry.phase), ['browser-pass', 'fix-batch', 'browser-pass'])
  assert.deepStrictEqual(
    budgetChecks.filter((entry) => entry.phase === 'browser-pass').map((entry) => entry.counts.browserPasses),
    [1, 2],
  )
  assert.deepStrictEqual(browserScopes.map((scope) => scope.action), ['initial', 'rerun_all'])
  const finalStatus = statuses[statuses.length - 1]
  assert.strictEqual(finalStatus.browserEvidenceHead, 'fix111')
  assert.deepStrictEqual(finalStatus.fixBatchHistory[0].commitShas, ['fix111'])
  assert.strictEqual(finalStatus.fixBatchHistory[0].rerunScope.action, 'rerun_all')
  assert.ok(finalStatus.fixBatchHistory[0].scrubbedSummary)
}

async function stringyOkFixBatchParksNotFalseProgress() {
  // #275-class: the fix-batch leaf returns a STRINGY ok:'false' (a refusal — truthy in JS). The old
  // gate `fixResult.ok === false` let it pass as success -> false progress recorded (empty shas,
  // unchanged head), browser re-run against the unfixed app. The hardened gate `fixResult.ok !== true`
  // parks BEFORE the post-fix clean/reconcile steps. `cleaned` staying false is the mutation-kill:
  // under the old gate the flow reaches ensureCleanWorktreeAfterFix and flips it true.
  let cleaned = false
  const out = await testPilotPhase('wi', 3, applicableDeps({
    budgetCheck: async () => ({ ok: true }),
    runBrowserPass: async () => ({
      source: 'browser',
      baseUrl: 'http://localhost:3000',
      steps: [{ id: 's1', status: 'failed', failureType: 'app_bug' }],
    }),
    // Capped so a REGRESSED gate (which would let the stringy result proceed) still terminates and
    // returns — the `cleaned` assertion then fires as a clean kill instead of an infinite re-fix loop.
    retryDecide: async (_passResult, history) => (history.length >= 3
      ? { action: 'park_cap_reached', reason: 'reached 3 browser fix batches with failed browser steps remaining' }
      : { action: 'fix_batch', failedStepIds: ['s1'], summary: 'Fix browser app failures' }),
    dispatchFixBatch: async () => ({ ok: 'false', commitShas: [] }),  // stringy refusal
    ensureCleanWorktreeAfterFix: async () => { cleaned = true; return { ok: true } },
    reconcileCommittedMutations: async () => ({ ok: true, commitShas: [], head: 'x' }),
  }))
  assert.strictEqual(out.confidence, 'low', 'a stringy ok:"false" fix batch must park, not record false progress (#275)')
  assert.strictEqual(cleaned, false, 'the stringy refusal must short-circuit at the gate, BEFORE the post-fix clean step (#275)')
  assert.match(out.assumptions[0], /fix batch parked/)

  // Symmetric to the build-gate coverage: a stringy ok:'true' is ALSO not a genuine boolean, so the
  // `ok !== true` gate fails it closed too — a stringy success must not record false progress either.
  let cleaned2 = false
  const out2 = await testPilotPhase('wi', 3, applicableDeps({
    budgetCheck: async () => ({ ok: true }),
    runBrowserPass: async () => ({
      source: 'browser',
      baseUrl: 'http://localhost:3000',
      steps: [{ id: 's1', status: 'failed', failureType: 'app_bug' }],
    }),
    retryDecide: async (_passResult, history) => (history.length >= 3
      ? { action: 'park_cap_reached', reason: 'reached 3 browser fix batches with failed browser steps remaining' }
      : { action: 'fix_batch', failedStepIds: ['s1'], summary: 'Fix browser app failures' }),
    dispatchFixBatch: async () => ({ ok: 'true', commitShas: ['deadbeef'] }),  // stringy (non-boolean) success
    ensureCleanWorktreeAfterFix: async () => { cleaned2 = true; return { ok: true } },
    reconcileCommittedMutations: async () => ({ ok: true, commitShas: ['deadbeef'], head: 'x' }),
  }))
  assert.strictEqual(out2.confidence, 'low', 'a stringy ok:"true" fix batch must also fail closed, not record progress (#275)')
  assert.strictEqual(cleaned2, false, 'a stringy ok:"true" must short-circuit at the gate too (#275)')
}

async function knownDependencyRerunsFailedAndAffectedSubset() {
  const browserStepSets = []
  let pass = 0
  const out = await testPilotPhase('wi', 3, applicableDeps({
    derivePlan: async () => ({
      dependencyMap: { 'web/settings.js': ['s3'] },
      records: [{
        branch: 'codex/example',
        steps: [
          { id: 's1', instruction: 'save settings', expected: 'settings save' },
          { id: 's2', instruction: 'open profile', expected: 'profile opens' },
          { id: 's3', instruction: 'reload settings', expected: 'settings persist' },
        ],
      }],
    }),
    preparePlanRecords: async (plan) => ({ action: 'ready', records: plan.records }),
    budgetCheck: async () => ({ ok: true }),
    runBrowserPass: async (browserContext) => {
      browserStepSets.push(browserContext.records.flatMap((record) => record.steps.map((step) => step.id)))
      pass += 1
      if (pass === 1) {
        return {
          source: 'browser',
          baseUrl: 'http://localhost:3000',
          steps: [
            { id: 's1', status: 'failed', failureType: 'app_bug' },
            { id: 's2', status: 'passed' },
            { id: 's3', status: 'passed' },
          ],
        }
      }
      return {
        source: 'browser',
        baseUrl: 'http://localhost:3000',
        steps: [
          { id: 's1', status: 'passed' },
          { id: 's3', status: 'passed' },
        ],
      }
    },
    retryDecide: async (_passResult, _history, changedFiles, dependencyMap) => {
      if (changedFiles) {
        const affected = dependencyMap && Array.isArray(dependencyMap['web/settings.js'])
          ? dependencyMap['web/settings.js']
          : []
        return { action: 'rerun_subset', failedStepIds: ['s1'], stepIds: ['s1', ...affected].sort() }
      }
      return { action: 'fix_batch', failedStepIds: ['s1'], summary: 'Fix browser app failures' }
    },
    dispatchFixBatch: async () => ({ ok: true, commitShas: ['fix222'], changedFiles: ['web/settings.js'], head: 'fix222' }),
    ensureCleanWorktreeAfterFix: async () => ({ ok: true }),
    reconcileCommittedMutations: async () => ({ ok: true, commitShas: ['fix222'], head: 'fix222' }),
  }))

  assert.strictEqual(out.confidence, 'high')
  assert.deepStrictEqual(browserStepSets, [['s1', 's2', 's3'], ['s1', 's3']])
}

async function dirtyFixLeftoversParkBehindInjectedWorktreeGuard() {
  let dispatches = 0
  const out = await testPilotPhase('wi', 3, applicableDeps({
    budgetCheck: async () => ({ ok: true }),
    runBrowserPass: async () => ({
      source: 'browser',
      baseUrl: 'http://localhost:3000',
      steps: [{ id: 's1', status: 'failed', failureType: 'app_bug' }],
    }),
    retryDecide: async () => ({ action: 'fix_batch', failedStepIds: ['s1'], summary: 'Fix browser app failures' }),
    dispatchFixBatch: async () => { dispatches += 1; return { ok: true, dirty: true } },
    ensureCleanWorktreeAfterFix: async () => ({ ok: false, reason: 'dirty fix leftovers after lease reset failed' }),
  }))

  assert.strictEqual(out.confidence, 'low')
  assert.strictEqual(dispatches, 1)
  assert.match(out.assumptions[0], /dirty fix leftovers/)
}

async function threeFixBatchesParkIfFailuresRemain() {
  let dispatches = 0
  const out = await testPilotPhase('wi', 3, applicableDeps({
    budgetCheck: async () => ({ ok: true }),
    retryDecide: async (_passResult, history, changedFiles) => {
      if (changedFiles) return { action: 'rerun_all', failedStepIds: ['s1'] }
      if (history.length >= 3) {
        return { action: 'park_cap_reached', reason: 'reached 3 browser fix batches with failed browser steps remaining' }
      }
      return { action: 'fix_batch', failedStepIds: ['s1'], summary: `Fix browser app failures batch ${history.length + 1}` }
    },
    runBrowserPass: async () => ({
      source: 'browser',
      baseUrl: 'http://localhost:3000',
      steps: [{ id: 's1', status: 'failed', failureType: 'app_bug' }],
    }),
    dispatchFixBatch: async () => {
      dispatches += 1
      return { ok: true, commitShas: [`fix${dispatches}`], changedFiles: [`web/app${dispatches}.js`], head: `fix${dispatches}` }
    },
    ensureCleanWorktreeAfterFix: async () => ({ ok: true }),
    reconcileCommittedMutations: async (_result) => ({ ok: true, commitShas: [`fix${dispatches}`], head: `fix${dispatches}` }),
  }))

  assert.strictEqual(out.confidence, 'low')
  assert.strictEqual(dispatches, 3)
  assert.match(out.assumptions[0], /3 browser fix batches/)
}

async function reviewCodeMutationForcesBrowserRevalidationWithoutConsumingBrowserFixBudget() {
  let browserPasses = 0
  let reviewCalls = 0
  let dispatches = 0
  const out = await testPilotPhase('wi', 3, applicableDeps({
    requireReviewCode: true,
    budgetCheck: async () => ({ ok: true }),
    runBrowserPass: async () => {
      browserPasses += 1
      return { source: 'browser', baseUrl: 'http://localhost:3000', steps: [{ id: 's1', status: 'passed' }] }
    },
    reviewCode: async (_workItem, opts) => {
      reviewCalls += 1
      assert.strictEqual(opts.browserFixBatchCount, 0)
      if (reviewCalls === 1) return { gate: 'passed', head: 'review-fix-1', changed: true, reviewCoverageHead: 'review-fix-1', verifyPassedHead: 'review-fix-1' }
      return { gate: 'passed', head: 'review-fix-1', changed: false, reviewCoverageHead: 'review-fix-1', verifyPassedHead: 'review-fix-1' }
    },
    dispatchFixBatch: async () => { dispatches += 1; return { ok: true } },
  }))

  assert.strictEqual(out.confidence, 'high')
  assert.strictEqual(browserPasses, 2)
  assert.strictEqual(reviewCalls, 2)
  assert.strictEqual(dispatches, 0)
}

async function reviewCodeCleanWithSkipsParksBecauseNoCoversStamp() {
  const out = await testPilotPhase('wi', 3, applicableDeps({
    requireReviewCode: true,
    budgetCheck: async () => ({ ok: true }),
    reviewCode: async () => ({ gate: 'passed', terminal: 'clean-with-skips', head: 'abc123' }),
  }))

  assert.strictEqual(out.confidence, 'low')
  assert.match(out.assumptions[0], /clean-with-skips/)
}

function helperContractsCoverFailureCollectionAndMutationReconciliation() {
  const failures = collectAppBugFailures({
    records: [
      { stepId: 's1', status: 'failed', failureType: 'app_bug', browserExecuted: true },
      { stepId: 's2', status: 'failed', failureType: 'test_bug', browserExecuted: true },
      { stepId: 's3', status: 'passed', browserExecuted: true },
    ],
  })
  assert.deepStrictEqual(failures.map((failure) => failure.stepId), ['s1'])

  const unreconciled = reconcileCommittedMutations({ cleanCommittedMutations: true }, [], null, {})
  assert.strictEqual(unreconciled.ok, false)
  assert.match(unreconciled.reason, /committed mutations/)
}

async function finalReadinessRestoresBaselinePublishesArtifactsAndRemoteHeadBeforeReadyStatus() {
  const calls = []
  const statuses = []
  const out = await testPilotPhase('wi', 3, applicableDeps({
    budgetCheck: async () => ({ ok: true }),
    runBrowserPass: async () => { calls.push('browser'); return { source: 'browser', baseUrl: 'http://localhost:3000', steps: [{ id: 's1', status: 'passed' }] } },
    reviewCode: async (_workItem, opts) => { calls.push('reviewCode'); return { gate: 'passed', head: opts.expectedHead, changed: false, reviewCoverageHead: opts.expectedHead, verifyPassedHead: opts.expectedHead } },
    restoreBaseline: async (_records, details) => { calls.push('restoreBaseline'); return { ok: true, baseline: { head: details.head, restored: true } } },
    ensureFinalArtifacts: async (payload) => {
      calls.push('ensureFinalArtifacts')
      assert.strictEqual(payload.baseline.head, 'abc123')
      return { ok: true, artifacts: { plan: 'plan.md', results: 'final-results.md' }, posting: { ok: true } }
    },
    publishReady: async (_workItem, head, payload) => {
      calls.push('publishReady')
      assert.strictEqual(payload.baseline.head, head)
      assert.strictEqual(payload.artifacts.results, 'final-results.md')
      return { ok: true, read_back: true, remotePr: { branch: 'codex/example', head } }
    },
    writeStatus: async (status) => { calls.push(`writeStatus:${status.milestone || status.verdict}`); statuses.push(status); return { ok: true, read_back: true } },
  }))

  assert.strictEqual(out.confidence, 'high')
  assert.ok(calls.indexOf('restoreBaseline') > calls.indexOf('reviewCode'))
  assert.ok(calls.indexOf('ensureFinalArtifacts') > calls.indexOf('restoreBaseline'))
  assert.ok(calls.indexOf('publishReady') > calls.indexOf('ensureFinalArtifacts'))
  const final = statuses[statuses.length - 1]
  assert.strictEqual(final.verdict, 'applicable')
  assert.strictEqual(final.baseline.head, 'abc123')
  assert.strictEqual(final.artifacts.results, 'final-results.md')
  assert.strictEqual(final.remotePr.head, 'abc123')
}

async function finalPublishFailureParksBeforeApplicableReadyStatus() {
  const statuses = []
  const out = await testPilotPhase('wi', 3, applicableDeps({
    budgetCheck: async () => ({ ok: true }),
    publishReady: async () => ({ ok: false, reason: 'remote PR head does not equal final tested head' }),
    writeStatus: async (status) => { statuses.push(status); return { ok: true, read_back: true } },
  }))

  assert.strictEqual(out.confidence, 'low')
  assert.match(out.assumptions[0], /remote PR head/)
  assert.strictEqual(statuses.some((status) => status.verdict === 'applicable'), false)
}

async function phaseOrderAndGate() {
  const idx = sr.PHASES.indexOf('test-pilot')
  assert.ok(idx > sr.PHASES.indexOf('draft-PR'), 'test-pilot follows draft-PR')
  assert.ok(idx < sr.PHASES.indexOf('mark-ready'), 'test-pilot precedes mark-ready')

  let markReadyReached = false
  const out = await sr.runPhases('wi', sr.PHASES.indexOf('test-pilot'), {
    testPilot: async () => ({ confidence: 'low', assumptions: ['browser verification failed'] }),
    markReady: async () => { markReadyReached = true; return { phaseResult: { confidence: 'high', assumptions: [] }, sideEffect: { ready: true } } },
  })
  assert.strictEqual(out.outcome, 'parked')
  assert.strictEqual(out.phase, 'test-pilot')
  assert.strictEqual(markReadyReached, false)
}

// I-1 / I-2 regression test: resolveContext coerces courier-stringified fields including allowedOrigins
// (an array). Patch global.agent to return all nested fields as JSON strings (simulating the cheap
// courier's field-extract path), then assert:
//   (a) resolveContext returns real objects/arrays, not strings
//   (b) in-process applicability consumes coerced objects without a courier leaf
// This test would FAIL against the pre-I-1 code for allowedOrigins (stays string → Array.isArray false).
async function resolveContextCoercesStringifiedFieldsIncludingAllowedOriginsArray() {
  const deciders = require('../test_pilot_deciders.js')
  const previousAgent = global.agent
  const previousIo = global.io

  // The stringified context the cheap courier would deliver (every nested field is a JSON string).
  const rawDiff = { files: ['src/app.jsx'], additions: 5, deletions: 2 }
  const rawDetectors = { frontend: true, hasTests: true }
  const rawProfile = { baseUrl: 'http://localhost:3000', scenarios: ['login'] }
  const rawAllowedOrigins = ['http://localhost:3000', 'http://localhost:8080']
  const rawPr = { number: 42, title: 'fix: test coercion' }

  // Written files captured by the io seam intercept (unused after in-process applicability).
  const writtenFiles = {}

  global.io = Object.assign({}, require('../io_seam.js').defaultIo, {
    async mkdirp() { /* no-op in test */ },
    async writeFile(p, content) {
      writtenFiles[require('path').basename(p)] = content
    },
  })

  const RESOLVED_WT = '/build/wt-coerce'
  let contextResolvePrompt = null
  global.agent = async (prompt, opts) => {
    if (opts && opts.label === 'resolve review target') {
      return [{ ok: true, stdout: JSON.stringify({ ok: true, worktree: RESOLVED_WT, expectedHead: 'wt-head-abc' }) }]
    }
    if (prompt.includes('test_pilot_context_cli.py resolve')) {
      contextResolvePrompt = prompt
      // Simulate courier stringification: every nested object/array field arrives as a string.
      return courierStdout({
        workItem: 'wi',
        generation: 3,
        branch: 'codex/example',
        head: 'abc123',
        diff: JSON.stringify(rawDiff),
        detectors: JSON.stringify(rawDetectors),
        profile: JSON.stringify(rawProfile),
        allowedOrigins: JSON.stringify(rawAllowedOrigins),
        pr: JSON.stringify(rawPr),
      })
    }
    if (prompt.includes('test_pilot_status_cli.py write')) {
      return courierStdout({ ok: true, read_back: true })
    }
    return previousAgent(prompt, opts)
  }

  try {
    const deps = sr.testPilotDeps('wi', 3)

    // (a) resolveContext must coerce all stringified fields back to their real types.
    const context = await deps.resolveContext()
    assert.deepStrictEqual(context.diff, rawDiff, 'diff must be coerced to object')
    assert.deepStrictEqual(context.detectors, rawDetectors, 'detectors must be coerced to object')
    assert.deepStrictEqual(context.profile, rawProfile, 'profile must be coerced to object')
    assert.deepStrictEqual(context.pr, rawPr, 'pr must be coerced to object')
    // I-1 regression: allowedOrigins is an ARRAY — must coerce even though Array.isArray(p) is true.
    assert.ok(Array.isArray(context.allowedOrigins), 'allowedOrigins must be coerced to an array (I-1 regression)')
    assert.deepStrictEqual(context.allowedOrigins, rawAllowedOrigins, 'allowedOrigins array values must match')
    // Scalar strings (head, branch) must pass through unchanged.
    assert.strictEqual(context.branch, 'codex/example', 'branch string must not be coerced')
    assert.strictEqual(context.head, 'abc123', 'head string must not be coerced')

    // (a2) FIX B / test-002: resolveBuildTarget resolved a worktree, so resolveContext threads
    // --worktree into the context CLI (and would fail-closed/throw if the worktree were unresolvable).
    assert.ok(contextResolvePrompt && contextResolvePrompt.includes(`--worktree '${RESOLVED_WT}'`),
      `resolveContext threads --worktree from resolveBuildTarget (got: ${contextResolvePrompt && contextResolvePrompt.slice(0, 220)})`)

    // (b) in-process applicability must consume coerced objects, not stringified JSON blobs.
    const verdict = deciders.applicabilityDecision(context.diff, context.detectors, context.profile)
    assert.strictEqual(verdict.verdict, 'applicable')
  } finally {
    global.agent = previousAgent
    global.io = previousIo
  }
}

async function unresolvableWorktreeParksNotSkips() {
  // premortem-001 (round-3 finding): when resolveBuildTarget cannot resolve the build worktree, the
  // real resolveContext must FAIL-CLOSED (throw -> low park), NOT silently run the context CLI against
  // the showrunner's own tree and skip test-pilot via a bogus not_applicable. Drives the real
  // resolveContext (via testPilotDeps) with a failing build_entry.py exec.
  const previousAgent = global.agent
  global.agent = async (prompt, opts) => {
    if (opts && opts.label === 'resolve review target') {
      return [{ ok: true, stdout: JSON.stringify({ ok: false, error: 'missing build worktree' }) }]
    }
    if (prompt.includes('test_pilot_context_cli.py resolve')) throw new Error('context CLI must not run against the showrunner tree')
    return previousAgent(prompt, opts)
  }
  try {
    const deps = sr.testPilotDeps('wi', 3)
    const out = await testPilotPhase('wi', 3, deps)
    assert.strictEqual(out.confidence, 'low', 'unresolvable build worktree -> low-confidence park (not a skip)')
    assert.match(out.assumptions[0], /could not resolve the build worktree/,
      `park names the worktree resolution failure (got: ${JSON.stringify(out.assumptions)})`)
  } finally {
    global.agent = previousAgent
  }
}


// #451 Half A: the managed dev-server launch MUST be rooted at the BUILD worktree so browser
// evidence is gathered against the tree under test — never the session root (which sits behind the
// PR branch HEAD and would produce FALSE evidence toward flipping the PR ready). Fails if the launch
// command is not cd'd into the build worktree and does not thread --worktree through the launch CLI.
async function managedServerLaunchIsRootedAtBuildWorktree() {
  const previousAgent = global.agent
  const buildWorktree = '/tmp/build-worktree-451'
  const sessionRoot = require('path').resolve(__dirname, '../../../..')
  let launchPrompt = null
  global.agent = async (prompt) => {
    if (prompt.includes('test_pilot_server_config_cli.py launch')) {
      launchPrompt = prompt
      return { verdict: 'managed', shell: false, cwd: buildWorktree, baseUrl: 'http://localhost:3003', allowedOrigins: ['http://localhost:3003'], handle: { pid: 99, port: 3003 } }
    }
    if (prompt.includes('test_pilot_server_config_cli.py finish')) {
      return { source: 'browser', steps: [{ id: 's1', status: 'passed' }] }
    }
    return previousAgent(prompt)
  }
  try {
    const deps = sr.testPilotDeps('wi', 3)
    await deps.withManagedServer(
      { verdict: 'managed', shell: false, cwd: buildWorktree, baseUrl: 'http://localhost:3003', allowedOrigins: ['http://localhost:3003'] },
      async () => ({ source: 'browser', steps: [{ id: 's1', status: 'passed' }] }),
    )
    assert.ok(launchPrompt, 'launch command must have been composed')
    assert.ok(launchPrompt.includes(`cd '${buildWorktree}' &&`),
      `#451 Half A: launch must be rooted (cd) at the build worktree (got: ${launchPrompt})`)
    assert.ok(launchPrompt.includes(`--worktree '${buildWorktree}'`),
      `#451 Half A: launch must thread --worktree into the launch CLI (got: ${launchPrompt})`)
    // The command (after the courier preamble) must START by cd-ing into the build worktree — proves
    // it is rooted at the tree under test, not merely un-prefixed / left at the session root.
    const launchCmd = launchPrompt.slice(launchPrompt.lastIndexOf('\n\n') + 2)
    assert.ok(launchCmd.startsWith(`cd '${buildWorktree}' && python3 `),
      `#451 Half A: launch command must be rooted at the build worktree (got: ${launchCmd})`)
    assert.ok(!launchCmd.includes(`cd '${sessionRoot}'`),
      '#451 Half A: launch must NOT be rooted at the session root when a build worktree is known')
  } finally {
    global.agent = previousAgent
  }
}

// #451 Half A: with NO build worktree on the server context, the launch stays session-rooted and adds
// no --worktree (backward-compatible with the pre-#451 ready_external / cwd-less managed path).
async function managedServerLaunchWithoutWorktreeStaysBackwardCompatible() {
  const previousAgent = global.agent
  let launchPrompt = null
  global.agent = async (prompt) => {
    if (prompt.includes('test_pilot_server_config_cli.py launch')) {
      launchPrompt = prompt
      return { verdict: 'managed', shell: false, baseUrl: 'http://localhost:3000', allowedOrigins: ['http://localhost:3000'], handle: { pid: 7, port: 3000 } }
    }
    if (prompt.includes('test_pilot_server_config_cli.py finish')) {
      return { source: 'browser', steps: [{ id: 's1', status: 'passed' }] }
    }
    return previousAgent(prompt)
  }
  try {
    const deps = sr.testPilotDeps('wi', 3)
    await deps.withManagedServer(
      { verdict: 'managed', shell: false, baseUrl: 'http://localhost:3000', allowedOrigins: ['http://localhost:3000'] },
      async () => ({ source: 'browser', steps: [{ id: 's1', status: 'passed' }] }),
    )
    assert.ok(launchPrompt, 'launch command must have been composed')
    const sessionRoot = require('path').resolve(__dirname, '../../../..')
    const launchCmd = launchPrompt.slice(launchPrompt.lastIndexOf('\n\n') + 2)
    // No build worktree known -> the launch stays session-rooted (selfContained cd to __SR_ROOT),
    // carries no --worktree flag, and still invokes the launch CLI. This is the pre-#451 shape.
    assert.ok(launchCmd.startsWith(`cd '${sessionRoot}' && python3 `),
      `#451: no build worktree -> launch stays session-rooted (got: ${launchCmd})`)
    assert.ok(launchCmd.includes('test_pilot_server_config_cli.py launch --context-json'),
      `#451: launch CLI must still be invoked (got: ${launchCmd})`)
    assert.ok(!launchCmd.includes('--worktree'),
      `#451: no build worktree -> no --worktree flag (got: ${launchCmd})`)
  } finally {
    global.agent = previousAgent
  }
}

// #451: resolveServer must thread the build worktree into the resolver CLI (--worktree) — this is the
// connective tissue that populates serverContext.cwd, which in turn (a) sources the .env.local port
// override and (b) roots the managed launch. A regression dropping it reintroduces the :3000 mismatch.
async function resolveServerThreadsWorktreeIntoCli() {
  const previousAgent = global.agent
  const buildWorktree = '/tmp/build-worktree-451'
  let resolvePrompt = null
  global.agent = async (prompt) => {
    if (prompt.includes('test_pilot_server_config_cli.py resolve')) {
      resolvePrompt = prompt
      return { verdict: 'managed', baseUrl: 'http://localhost:3003', allowedOrigins: ['http://localhost:3003'], cwd: buildWorktree, command: ['npm', 'run', 'dev'], shell: false }
    }
    return previousAgent(prompt)
  }
  try {
    const deps = sr.testPilotDeps('wi', 3)
    await deps.resolveServer({ worktree: buildWorktree, profile: { baseUrl: 'http://localhost:3003' }, detectors: {} })
    assert.ok(resolvePrompt, 'resolve command must have been composed')
    assert.ok(resolvePrompt.includes(`--worktree '${buildWorktree}'`),
      `#451: resolveServer must thread the build worktree into the resolver CLI (got: ${resolvePrompt})`)
  } finally {
    global.agent = previousAgent
  }
}

;(async () => {
  await notApplicableProceeds()
  await productionWrapperHandlesNotApplicableWithoutMissingLeaf()
  await productionManagedServerUsesLifecycleHelperAroundBrowserRun()
  await managedServerLaunchIsRootedAtBuildWorktree()
  await managedServerLaunchWithoutWorktreeStaysBackwardCompatible()
  await resolveServerThreadsWorktreeIntoCli()
  await managedServerFinishWriteThrowPreservesOutcomeAndError()
  await uncertainApplicabilityParks()
  await emptyApplicablePlanParks()
  await missingSetupParksBeforeBrowser()
  await missingBrowserToolParksBeforeBrowser()
  await applicableFlowOrdersDurableMilestones()
  await foldedParkReasonSurfacesVerbatimInLowTerminal()
  await foldedOkFalseReasonSurfacesInLowTerminal()
  await foldedConfidenceLowReasonSurfacesInLowTerminal()
  await foldedParkWithoutReasonUsesPreparationDefault()
  await foldedNullKeepsReturnedNoResultMessage()
  await foldedHappyPathStillProceedsToHigh()
  await invalidPreparedRecordsParkBeforeArtifactsSeedAndBrowser()
  await generatedInRepoPlanStoreParksBeforeWorktreeMutation()
  await resumePreservesHumanStateAndAvoidsDuplicateIds()
  await skippedStepRequiresPreservationFields()
  await managedServerTearsDownOnBrowserFailure()
  await offOriginBrowserResultsPark()
  await nonBrowserEvidenceParksBeforeReadiness()
  await budgetExhaustedParksBeforeBrowser()
  await appBugFailuresDispatchOneFixBatchAndRerunWholePlan()
  await stringyOkFixBatchParksNotFalseProgress()
  await knownDependencyRerunsFailedAndAffectedSubset()
  await dirtyFixLeftoversParkBehindInjectedWorktreeGuard()
  await threeFixBatchesParkIfFailuresRemain()
  await reviewCodeMutationForcesBrowserRevalidationWithoutConsumingBrowserFixBudget()
  await reviewCodeCleanWithSkipsParksBecauseNoCoversStamp()
  await finalReadinessRestoresBaselinePublishesArtifactsAndRemoteHeadBeforeReadyStatus()
  await finalPublishFailureParksBeforeApplicableReadyStatus()
  helperContractsCoverFailureCollectionAndMutationReconciliation()
  await phaseOrderAndGate()
  await resolveContextCoercesStringifiedFieldsIncludingAllowedOriginsArray()
  await unresolvableWorktreeParksNotSkips()
  console.log('OK: test-pilot phase skeleton smokes passed')
})().catch((e) => { console.error('FAIL:', e.stack || e.message); process.exit(1) })
