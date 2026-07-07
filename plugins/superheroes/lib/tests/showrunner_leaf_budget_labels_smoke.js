require('./_smoke_checkout_root.js')
// Pin cwd to the checkout root: buildPhase's final review runs REAL root-pinned helpers
// (review_setup_gather.py), so repo-relative state only lines up when the smoke itself runs
// from the root (pre-existing; see showrunner_fronthalf_phase_smoke.js for the story).
if (globalThis.__SR_ROOT) process.chdir(globalThis.__SR_ROOT)
const assert = require('assert')
const bp = require('../build_phase.js')
const { testPilotPhase } = require('../test_pilot_phase.js')
const { saveProgressOk } = require('./_marked_stdout.js')

// pid-unique work item: buildPhase's final review derives a machine-global
// /tmp/workhorse-<wi>-final-review dir from the work-item name, so a fixed name shares (and
// reads) state with a concurrent pytest suite on this machine (see _final_review_probe.js for
// the flake story). The dir is reaped on a passing exit; a failing run keeps it as evidence.
const WI = `wi-pid${process.pid}`
process.on('exit', (code) => {
  if (code !== 0) return
  try { require('fs').rmSync(`/tmp/workhorse-${WI}-final-review`, { recursive: true, force: true }) } catch (_) {}
  try { require('fs').rmSync(`/tmp/showrunner-${WI}-review-plan`, { recursive: true, force: true }) } catch (_) {}
  // test-pilot's deps create /tmp/showrunner-<wi>-test-pilot lazily on their first writeJson;
  // today this smoke's stubs park before that fires, but reap it anyway so a stub change can't
  // start accumulating pid dirs silently.
  try { require('fs').rmSync(`/tmp/showrunner-${WI}-test-pilot`, { recursive: true, force: true }) } catch (_) {}
})


const exercised = [
  'read startup state', 'read plan draft', 'read tasks draft',
  'author-plan', 'author-tasks',
  'architecture-reviewer', 'code-reviewer', 'security-reviewer', 'test-reviewer', 'premortem-reviewer',
  'save round state', 'save phase progress',
  'gather build state', 'implement task 1 of 1', 'record task built', 'review task 1:r1', 'record task reviewed',
  'read verify + minors', 'stamp build coverage', 'run verify',
  'open draft PR', 'mark PR ready',
  'read test context', 'plan-tests', 'prepare test run',
  'resolve review target', 'check ship-readiness', 'post readout',
  // #151 descriptive exec-courier labels (replace the bare 'exec') — pinned so a regression to
  // 'exec' (or a dropped purpose) fails CI. These are the dumb-pipe leaves the build/front-half drive.
  'check draft', 'read gate', 'prepare build', 'read tasks', 'fence lease', 'write provenance', 'check trailers',
]
const forbidden = ['worker', 'review', 'fixer', 'final-fixer', 'code-fixer', 'fix']

function jsonOut(obj) { return [{ ok: true, stdout: JSON.stringify(obj) }] }

;(async () => {
  const seen = new Set()
  global.log = () => {}
  global.parallel = (fns) => Promise.all(fns.map((fn) => fn()))
  global.agent = async (p, opts) => {
    const label = (opts && opts.label) || ''
    seen.add(label)
    if (forbidden.includes(label)) throw new Error('forbidden label exercised: ' + label)
    if (label === 'read startup state') {
      return jsonOut({ ok: true, spec_gate: 'passed', model_overrides: {}, doc_dir: '', world: {} })
    }
    if (label === 'read world-snapshot') {
      return jsonOut({ ok: true, gate: 'passed' })
    }
    if (label === 'read plan draft' || label === 'read tasks draft') {
      return jsonOut({ ok: true, path: '/tmp/doc.md', docType: 'plan', gate: 'pending', exists: true })
    }
    if (label.startsWith('author-')) return { status: 'ok', notify: [] }
    if (label === 'revise-doc' || label === 'fix-branch' || label === 'fix-code' || label === 'fix-ci' || label === 'fix-app-bug') return { ok: true, fixes: [], deferred: [] }
    if (/^fix task /.test(label)) return { ok: true, fixes: [], deferred: [] }
    if (/^implement task .+ of \d+$/.test(label)) return { ok: true, signal: 'ok', evidence: { testPassed: true, testFailed: false } }
    if (/^review task .+:r\d+$/.test(label)) return { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }
    if (label.startsWith('branch-reviewer:')) return { findings: [] }
    if (label === 'architecture-reviewer') {
      return { findings: [{ file: 'docs/x.md', line: 1, title: 'gap', severity: 'Critical', evidence: 'e' }] }
    }
    if (label === 'code-reviewer' || label === 'security-reviewer' || label === 'test-reviewer' || label === 'premortem-reviewer') {
      return { findings: [] }
    }
    if (label.startsWith('synthesis:')) {
      return { verdicts: [{ id: 'docs/x.md::gap', action: 'keep', reason: 'r', severity: 'Critical' }] }
    }
    // Build-phase dumb-pipe leaves now carry UNIQUE descriptive labels — match by LABEL, not a prompt
    // substring. The 'resolve review target' gather embeds build_entry.py + review_code_config.py in
    // its python -c script, so a p.includes('build_entry.py') check would mis-handle it (returning the
    // build-setup shape and failing its require:['ok']); label matching avoids that class of collision.
    // buildPhase's 'read gate' leaf (execText) wants plain 'passed'; the front-half readGate (execJson,
    // --json) parses 'passed' as non-JSON and falls back to 'unreadable', as it did under bare 'exec'.
    if (label === 'read gate') return [{ index: 0, ok: true, stdout: 'passed' }]
    if (label === 'prepare build') return [{ index: 0, ok: true, stdout: JSON.stringify({ branch: 'superheroes/wi-abc', path: '/tmp/wt' }) }]
    if (label === 'read tasks') return [{ index: 0, ok: true, stdout: JSON.stringify({ tasks: [{ id: '1', title: 'A' }], raw_task_heading_count: 1 }) }]
    if (label === 'fence lease') return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
    if (label === 'write provenance') return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
    if (label === 'append minors') return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
    if (label === 'lib') return { ok: true }
    if (label === 'gather build state') {
      return jsonOut({ committed_task_ids: [], unmapped_commits: 0, review_records: {}, worktree_dirty: false, final_review: null, provenance: 'absent' })
    }
    if (label === 'record task built' || label === 'record task reviewed') return jsonOut({ ok: true, read_back: true, task: '1' })
    if (label === 'read verify + minors') return jsonOut({ ok: true, verify_command: 'none', minors: [] })
    if (label === 'stamp build coverage' || label === 'stamp review coverage') return jsonOut({ ok: true, read_back: true })
    if (label === 'resolve review target') return jsonOut({ ok: true, worktree: '/wt', expectedHead: 'abc' })
    if (label === 'run verify') return { command: 'none', returncode: 0, timedOut: false }
    if (label === 'open draft PR') return jsonOut({ ok: true, read_back: true, pr: { number: 1, url: 'u', state: 'open' } })
    if (label === 'mark PR ready') return jsonOut({ ok: true, read_back: true })
    if (label === 'plan-tests') return { records: [{ branch: 'b', steps: [{ id: 's1', instruction: 'i', expected: 'e', scenarioIds: ['a'] }] }] }
    if (label === 'browser-pass') return { source: 'browser', steps: [{ id: 's1', status: 'passed' }] }
    if (label === 'read test context') {
      return jsonOut({ head: 'abc', branch: 'b', pr: { number: 1 }, profile: { baseUrl: 'http://x' }, browserTool: { kind: 'mcp' }, allowedOrigins: ['http://x'], diff: { files: ['a'] }, detectors: { browser: true } })
    }
    if (label === 'prepare test run') {
      return jsonOut({ artifactResult: { ok: true, artifacts: {}, posting: { ok: true } }, serverContext: { verdict: 'ready_external', baseUrl: 'http://x', allowedOrigins: ['http://x'] }, seedResult: { action: 'ready_for_browser' } })
    }
    if (label === 'write test status' || label === 'publish tested head') return jsonOut({ ok: true, read_back: true })
    if (label === 'check ship-readiness') {
      return jsonOut({ ok: true, reconcile: { ok: true }, freshness: { decision: 'up_to_date' }, integrated: false, checks: [{ name: 'ci', bucket: 'pass', state: 'success' }] })
    }
    if (label === 'prepare CI fix') return jsonOut({ action: 'revert_and_gate', ok: true, read_back: true })
    if (label === 'push CI fix + recheck') return jsonOut({ ok: true, pushed: true, read_back: true, checks: [] })
    if (label === 'post readout') return jsonOut({ posted: true, recorded: true })
    if (label === 'save phase progress') return saveProgressOk()
    if (label === 'save round state') return jsonOut({ ok: true })
    // generic dumb-pipe catch-all — AFTER all named courier branches (e.g. the per-task 'check
    // trailers' gather + any provenance/minor-rollup leaf that reaches here).
    if (opts && opts.courier) return [{ index: 0, ok: true, stdout: '{}' }]
    return {}
  }

  delete require.cache[require.resolve('../showrunner.js')]
  const sr = require('../showrunner.js')
  globalThis.reviewerAgent = async () => []
  globalThis.recordDeferred = async () => {}

  await sr.readStartupState(WI)
  await sr.readDefinitionDraft(WI, 'plan')
  await sr.readDefinitionDraft(WI, 'tasks')
  await sr.producePhase('plan', WI)
  await sr.producePhase('tasks', WI)
  await sr.reviewDocPhase('plan', WI)
  await sr.persistPhase(WI, { step: 1, phase: 'build', record: { phase: 'build' } })
  await bp.buildPhase(WI, 5)
  await sr.draftPRPhase(WI)
  await sr.markReadyPhase(WI)
  await testPilotPhase(WI, 1, sr.testPilotDeps(WI, 1))
  await sr.shipPhase(WI, { number: 1 }, 1)

  for (const label of exercised) {
    assert.ok(seen.has(label), 'missing exercised label: ' + label)
  }
  for (const label of forbidden) {
    assert.ok(!seen.has(label), 'forbidden label present: ' + label)
  }
  console.log('ok: leaf budget label matrix')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
