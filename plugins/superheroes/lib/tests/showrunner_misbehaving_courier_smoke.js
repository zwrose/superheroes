// plugins/superheroes/lib/tests/showrunner_misbehaving_courier_smoke.js
// The regression net for the misbehaving-courier bug class (live 2026-07-02, four consecutive
// runs parked at review-plan): in the Workflow sandbox every filesystem touch is an LLM
// courier, and courier text must never enter an integrity decision. This smoke drives the
// SAME canned green full run as showrunner_stretch_budget_smoke.js through the committed
// bundle, but with a courier that misbehaves in exactly the observed ways:
//   (1) PROSE READS — a read of a missing file answers a chatty sentence instead of empty
//       output (live: "The command completed with no output, which means the file does not
//       exist at that path."). Nothing may hash or parse that prose into a fence/decision.
//   (2) CHATTY WRITE ACKS — write leaves answer conversational acknowledgements instead of
//       the command's stdout. The runtime must not read anything into a write's answer.
//   (3) CONTENT-MANGLED WRITE — one staged write leaf writes the WRONG content on its first
//       attempt (live: the second dim's write leaf re-wrote the first dim's content). The
//       Python-side hash verify must refuse it and the retry must recover.
//   (4) MANGLED HELPER ANSWER — one persist helper's stdout comes back as prose after the
//       write applied. The retry must converge (idempotent stale-probe), not park.
//   (5) FENCED runHelper ANSWER — a haiku courier STOCHASTICALLY wraps a runHelper answer in ```
//       fences (live 2026-07-02: 3 of 4 runHelper leaves fenced), pushing ``` after the exit
//       marker. The bundle's io.runHelper must find the marker anyway — else a clean exit-0
//       helper is falsely read as failed (coverage-decisions-unreadable / telemetry-write-failed
//       / memory degraded), the exact review-plan park class the live run-8 hit.
//   (6) IMPROVISING RELEASE COURIER — the park-path lease release freestyled unscripted Bash and
//       narrated instead of returning the scripted command's JSON. The hardened release leaf
//       (dedicated single-command courier + require + a prompt forbidding extra commands) must
//       reject the chatty answer and retry, converging on the scripted JSON.
// Assertions: the run still reaches 'ready', AND the review phase's terminal-record.json is
// WRITTEN with the correct verdict (the live failure mode was a phase that completed its
// panel but died in persistence, leaving no terminal record).
'use strict'
const assert = require('assert')
const crypto = require('crypto')
const fs = require('fs')
const path = require('path')
const vm = require('vm')

function sha256(text) { return crypto.createHash('sha256').update(String(text), 'utf8').digest('hex') }

const PR = { number: 7, url: 'https://github.com/o/r/pull/7', state: 'open', isDraft: false }
const PROSE = 'The command completed with no output, which means the file does not exist at that path.'
const CHATTY_ACK = 'Done! I successfully wrote the file as requested.'

const files = Object.create(null)
const usableCalls = Object.create(null)
const counters = { proseReads: 0, chattyAcks: 0, sabotagedWrites: 0, mangledAnswers: 0,
                   fencedHelpers: 0, releaseImprovised: 0, releaseCalls: 0 }

function runHelperResponse(cmdline) {
  const m = cmdline.match(/'python3' '([^']+)'((?: '[^']*')*)/)
  if (!m) return null
  const script = m[1]
  const args = (m[2].match(/'[^']*'/g) || []).map((a) => a.slice(1, -1))
  if (script.endsWith('review_memory.py')) {
    if (args[0] === 'hash') {
      const p = args[args.indexOf('--path') + 1]
      return JSON.stringify({ ok: true, contentHash: sha256(files[p] != null ? files[p] : '') })
    }
    if (args[0] === 'load-summary') return JSON.stringify({ ok: true, records: [], contentHash: sha256(''), extras: null })
    if (args[0] === 'persist-skeleton') {
      const recordJson = args[args.indexOf('--record-json') + 1]
      if (sha256(recordJson) !== args[args.indexOf('--record-hash') + 1]) {
        throw new Error('persist-skeleton --record-hash does not match --record-json')
      }
      // (4) first persist answer comes back as prose AFTER the write applied — the runtime
      // must retry and converge (the helper side answers idempotently on the real retry).
      if (counters.mangledAnswers === 0) {
        counters.mangledAnswers += 1
        return 'The round record was persisted successfully to the memory file.'
      }
      counters.mangledAnswers += 1
      return JSON.stringify({ ok: true, contentHash: 'ch-round' })
    }
    if (args[0] === 'compose-persist') throw new Error('compose-persist rode a leaf (D3 replaced it)')
    if (args[0] === 'update-round') return JSON.stringify({ ok: true, contentHash: 'ch-postfix' })
  }
  if (script.endsWith('review_setup_gather.py')) {
    // fold 2 (#141): the ONE pre-round gather leaf (mkdir + load-summary + deferred seed + coverage).
    // A misbehaving courier fences this read helper too (mode 5, below) — the bundle must still parse it.
    return JSON.stringify({
      ok: true,
      memory: { ok: true, state: 'missing', records: [], contentHash: sha256(''), extras: null },
      deferredSet: {},
      coverage: { ok: true, decisions: [], contentHash: sha256('') },
    })
  }
  if (script.endsWith('review_telemetry.py')) return JSON.stringify({ ok: true, benchmarkValid: true })
  if (script.endsWith('fenced_json.py')) {
    const p = args[args.indexOf('--path') + 1]
    const staged = args[args.indexOf('--payload-path') + 1]
    const stagedText = files[staged] != null ? files[staged] : ''
    const hashIdx = args.indexOf('--payload-hash')
    if (hashIdx >= 0) {
      const want = args[hashIdx + 1]
      const ok = sha256(stagedText) === want ||
        (stagedText.endsWith('\n') && sha256(stagedText.slice(0, -1)) === want)
      if (!ok) return JSON.stringify({ ok: false, reason: 'payload-corrupt' })
    }
    files[p] = stagedText
    return JSON.stringify({ ok: true, contentHash: sha256(files[p]) })
  }
  if (script.endsWith('coverage_decisions.py')) {
    if (args[0] === 'load') return JSON.stringify({ ok: true, decisions: [], contentHash: sha256('') })
    return JSON.stringify({ ok: true })
  }
  return '{}'
}

function shellResponse(cmd) {
  cmd = cmd.replace(/^cd '[^']*' && /, '')
  // fold 1 (#141): the CHAINED stage+verify write — [mkdir &&] opaque base64 stage-write (stdout to
  // /dev/null) && fenced_json.py, all ONE leaf. Decode the payload into the in-memory FS (applying the
  // SAME content-mangle sabotage on the review-plan terminal-record's first attempt), then answer the
  // helper — so the Python-side --payload-hash refuses the sabotaged bytes and the retry recovers.
  const cw = cmd.match(/python3 - <<'__SR_EOF__' >\/dev\/null && ([\s\S]*?) 2>&1; echo __SR_EXIT:\$\?\nimport base64\nwith open\((".*?"), 'wb'\) as fh:\n {4}fh\.write\(base64\.b64decode\('([A-Za-z0-9+/=]*)'\)\)\n__SR_EOF__$/)
  if (cw) {
    const helper = cw[1]
    const staged = JSON.parse(cw[2])
    const honest = Buffer.from(cw[3], 'base64').toString('utf8')
    if (staged.endsWith('review-plan/terminal-record.json.payload') && counters.sabotagedWrites === 0) {
      counters.sabotagedWrites += 1
      files[staged] = '{"terminal": "halted", "note": "this is the WRONG content a mangling leaf wrote"}'
    } else {
      files[staged] = honest
    }
    const out = runHelperResponse(helper)
    return (out != null ? out : '{}') + '\n__SR_EXIT:0'
  }
  // The OPAQUE write transport (base64 python heredoc) — for the remaining standalone io.writeFile
  // leaves (test-pilot artifacts, last-extras). The write's answer is a conversational ack (mode 2).
  const bw = cmd.match(/python3 - <<'__SR_EOF__'\nimport base64\nwith open\((".*?"), 'wb'\) as fh:\n    fh\.write\(base64\.b64decode\('([A-Za-z0-9+/=]*)'\)\)\nprint\('ok'\)\n__SR_EOF__$/)
  if (bw) {
    const target = JSON.parse(bw[1])
    const honest = Buffer.from(bw[2], 'base64').toString('utf8')
    if (target.endsWith('review-plan/terminal-record.json.payload') && counters.sabotagedWrites === 0) {
      counters.sabotagedWrites += 1
      files[target] = '{"terminal": "halted", "note": "this is the WRONG content a mangling leaf wrote"}'
    } else {
      files[target] = honest
    }
    counters.chattyAcks += 1
    return CHATTY_ACK   // (2) the write's answer is conversational, never the command's stdout
  }
  if (cmd.startsWith('mkdir -p')) return ''
  const r = cmd.match(/^cat '([^']+)'/)
  if (r) {
    if (files[r[1]] == null) { counters.proseReads += 1; return PROSE }   // (1)
    return files[r[1]]
  }
  if (cmd.includes("'python3'")) {
    const out = runHelperResponse(cmd)
    const body = (out != null ? out : '{}') + '\n__SR_EXIT:0'
    // (5) FENCED runHelper ANSWER — wrap the whole answer (stdout + exit marker) in one ``` fence
    // for the read/summary helpers whose failure poisoned the live loop (coverage load, telemetry
    // write, round-memory load-summary). io.runHelper must locate the marker despite the trailing
    // fence; on the pre-fix bundle the end-anchored match misses -> status 1 -> the helper reads as
    // failed -> cannot-certify at review-plan.
    if (/review_setup_gather\.py|review_memory\.py' 'load-summary'|coverage_decisions\.py|review_telemetry\.py/.test(cmd)) {
      counters.fencedHelpers += 1
      return '```\n' + body + '\n```'
    }
    return body
  }
  if (cmd.includes('recover_entry.py')) return JSON.stringify({ checkpoint: null, world: {}, generation: 5 })
  if (cmd.includes('front_half_usable.py')) {
    const doc = (cmd.match(/--doc '?(plan|tasks)/) || [])[1] || 'plan'
    usableCalls[doc] = (usableCalls[doc] || 0) + 1
    return JSON.stringify({ usable: usableCalls[doc] > 1, recorded: 'x', expected: 'x', missing_sections: [], placeholder: false })
  }
  if (cmd.includes('definition_doc.py read-gate')) {
    return cmd.includes('--json') ? JSON.stringify({ review: 'pending' }) : 'passed'
  }
  if (cmd.includes('checkpoint_entry.py')) return JSON.stringify({ pr: PR })
  if (cmd.includes('phase_progress_entry.py')) return JSON.stringify({ ok: true, journal_confirmed: true, checkpoint_confirmed: true })
  if (cmd.includes('build_entry.py')) return JSON.stringify({ branch: 'superheroes/wi-x', path: '/tmp/wt', outcome: 'reused' })
  if (cmd.includes('task_list_cli.py')) return JSON.stringify({ tasks: [{ id: '1', title: 'A' }], raw_task_heading_count: 1 })
  if (cmd.includes('fence_cli.py')) return JSON.stringify({ ok: true })
  if (cmd.includes('review_code_config.py')) return JSON.stringify({ verifyCommand: 'none', tiers: {} })
  if (cmd.includes('prov_entry.py')) return JSON.stringify({ ok: true, read_back: true })
  if (cmd.includes('test_pilot_artifacts_cli.py')) return JSON.stringify({ ok: true, artifacts: { plan: '/tmp/p.json', results: '/tmp/r.json' }, posting: { ok: true } })
  if (cmd.includes('test_pilot_seed_cli.py')) return JSON.stringify({ ok: true, status: 'ok', action: 'ready' })
  if (cmd.includes('verify_gate.py')) return JSON.stringify({ command: 'none', returncode: 0, timedOut: false })
  if (cmd.includes('git -C') && cmd.includes('rev-parse')) return 'abc123'
  if (cmd.includes('git rev-parse')) return 'cwd000'
  if (cmd.includes('loop_readout.py')) return '## readout'
  if (cmd.includes('record_deferred.py') || cmd.includes('record-deferred')) return JSON.stringify({ ok: true })
  if (cmd.includes('append-notify')) return JSON.stringify({ ok: true })
  return '{}'
}

function answerCommandPrompt(prompt) {
  const idx = prompt.indexOf('\n\n')
  const body = idx >= 0 ? prompt.slice(idx + 2) : prompt
  if (/^\d+\. /m.test(body) && prompt.startsWith('Run each')) {
    const cmds = body.split('\n').filter((l) => /^\d+\. /.test(l)).map((l) => l.replace(/^\d+\. /, ''))
    return cmds.map((c, i) => ({ index: i, ok: true, stdout: shellResponse(c) }))
  }
  if (prompt.startsWith('Use the Bash tool')) {
    try { return JSON.parse(shellResponse(body)) } catch (_) { return {} }
  }
  return shellResponse(body)
}

const COURIER_JSON = {
  'read startup state': () => JSON.stringify({ ok: true, spec_gate: 'passed', model_overrides: {}, doc_dir: '', engine_prefs: {} }),
  'save phase progress': (prompt) => {
    // With prose reads live, ANY runtime-computed doc hash on the set-gate is prose-poisoned —
    // the fence must ride the Python-side 'current' sentinel (red: the pre-hardening bundle
    // ships contentHash(PROSE) here and this throw parks the run).
    if (/set-gate/.test(prompt) && !/--expected-hash 'current'/.test(prompt)) {
      throw new Error('set-gate rode a runtime-computed hash — courier-read text entered a fence')
    }
    return JSON.stringify({ ok: true, journal_confirmed: true, checkpoint_confirmed: true })
  },
  'save round state': () => JSON.stringify({ ok: true }),
  'gather build state': () => JSON.stringify({ committed_task_ids: [], unmapped_commits: 0, review_records: {}, worktree_dirty: false, final_review: null, provenance: 'absent' }),
  'record task built': () => JSON.stringify({ ok: true, read_back: true, task: '1' }),
  'record task reviewed': () => JSON.stringify({ ok: true, read_back: true, task: '1' }),
  'read verify + minors': () => JSON.stringify({ ok: true, verify_command: 'none', minors: [] }),
  'stamp build coverage': () => JSON.stringify({ ok: true, read_back: true }),
  'stamp review coverage': () => JSON.stringify({ ok: true, read_back: true }),
  'resolve review target': () => JSON.stringify({ ok: true, worktree: '/tmp/wt', expectedHead: 'abc123', config: { verifyCommand: 'none', tiers: {} }, cwdHead: 'cwd000' }),
  'open draft PR': () => JSON.stringify({ ok: true, read_back: true, pr: PR }),
  'mark PR ready': () => JSON.stringify({ ok: true, read_back: true }),
  'read test context': () => JSON.stringify({ head: 'abc123', branch: 'superheroes/wi-x', pr: { number: 7 }, profile: { baseUrl: 'http://x' }, browserTool: { kind: 'mcp' }, allowedOrigins: ['http://x'], diff: { files: ['a'] }, detectors: { browser: true }, store: null }),
  'prepare test run': () => JSON.stringify({ ok: true, artifactResult: { ok: true, artifacts: { plan: '/tmp/p.json', results: '/tmp/r.json' }, posting: { ok: true } }, serverContext: { verdict: 'ready_external', baseUrl: 'http://x', allowedOrigins: ['http://x'] }, seedResult: { action: 'ready_for_browser' } }),
  'write test status': () => JSON.stringify({ ok: true, read_back: true }),
  'publish tested head': () => JSON.stringify({ ok: true, read_back: true }),
  'check ship-readiness': () => JSON.stringify({ ok: true, reconcile: { ok: true }, freshness: { decision: 'up_to_date' }, fence: { ok: true }, integrated: false, checks: [{ name: 'ci', bucket: 'pass', state: 'success' }] }),
  'post readout': () => JSON.stringify({ posted: true, recorded: true }),
}

// A genuinely clean/complete review needs a real verificationReceipt matching the round's
// receiptArtifact + coverageDecisionIds (else the receipt-fabrication fix downgrades it to
// confidence:low -> cannot-certify).
function receiptFor(prompt) {
  let ctx = { receiptArtifact: 'stub', receiptCoverageDecisionIds: [] }
  const m = String(prompt).match(/Prompt context: (\{.*\})$/s)
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

const GENUINE_RESPONSES = [
  [/^author-(plan|tasks)$/, () => ({ status: 'ok', notify: [] })],
  [/^(architecture|code|security|test|premortem)-reviewer(:r\d+)?$/, (p) => ({ findings: [], confidence: 'high', verificationReceipt: receiptFor(p) })],
  [/^synthesis:r\d+$/, () => ({ verdicts: [] })],
  [/^implement-task$/, () => ({ ok: true, signal: 'ok', evidence: { testPassed: true, testFailed: false } })],
  [/^task-reviewer:r\d+$/, () => ({ verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] })],
  [/^branch-reviewer:r\d+$/, () => ({ findings: [] })],
  [/^plan-tests$/, () => ({ records: [{ branch: 'superheroes/wi-x', steps: [{ id: 's1', instruction: 'i', expected: 'e', scenarioIds: [] }] }], coverageRationale: 'r' })],
  [/^browser-pass$/, () => ({ source: 'browser', baseUrl: 'http://x', steps: [{ id: 's1', status: 'passed', browserExecuted: true }] })],
  [/^revise-doc$|^fix-/, () => ({ fixes: [], deferred: [], changedSubjects: [], coverageDecisions: [] })],
]

async function cannedAgent(prompt, opts) {
  const label = (opts && opts.label) || ''
  for (const [re, fn] of GENUINE_RESPONSES) {
    if (re.test(label)) return fn(prompt)
  }
  if (label === 'run verify') return { command: 'none', returncode: 0, timedOut: false }
  if (label === 'release lease') {
    // (6) an IMPROVISING release courier: the first answer is chatty prose (as if it ran extra
    // unscripted Bash and narrated). The hardened leaf must reject it (require:['ok']) and retry,
    // converging on the scripted JSON. The prompt must forbid extra commands.
    assert.ok(/do not run any other command/i.test(String(prompt)),
      'the release prompt forbids extra commands (no improvising)')
    counters.releaseCalls += 1
    if (counters.releaseCalls === 1) {
      counters.releaseImprovised += 1
      return 'I ran a couple of checks first, then released the lease manually — all good!'
    }
    return JSON.stringify({ ok: true, reason: 'lease released' })
  }
  if (COURIER_JSON[label]) return COURIER_JSON[label](String(prompt))
  return answerCommandPrompt(String(prompt))
}

async function main() {
  const bundlePath = path.join(__dirname, '..', 'showrunner.bundle.js')
  const text = fs.readFileSync(bundlePath, 'utf8').replace(/export\s+const\s+meta/, 'const meta')
  const sandbox = { console, TextEncoder, TextDecoder }
  sandbox.globalThis = sandbox
  sandbox.global = sandbox
  sandbox.agent = cannedAgent
  sandbox.parallel = async (thunks) => { const out = []; for (const t of thunks || []) out.push(await t()); return out }
  sandbox.log = () => {}
  vm.createContext(sandbox)
  vm.runInContext('globalThis.__SR_RUN = false;\n;(async () => {\n' + text + '\n})();', sandbox, { timeout: 10000 })
  const sr = sandbox.globalThis.__sr_require('showrunner.js')

  const outcome = await sr.showrunner({ workItem: 'wi-mis' })
  assert.strictEqual(outcome.outcome, 'ready',
    `the run must survive the misbehaving courier and reach 'ready' (got ${JSON.stringify(outcome)})`)

  // every misbehavior mode actually fired
  assert.ok(counters.proseReads >= 1, 'the prose-for-missing-file read mode must be exercised')
  assert.ok(counters.chattyAcks >= 1, 'the chatty-write-ack mode must be exercised')
  assert.strictEqual(counters.sabotagedWrites, 1, 'the content-mangled write mode must fire exactly once')
  assert.ok(counters.mangledAnswers >= 2, 'the mangled persist answer must be retried (>=2 helper calls)')
  assert.ok(counters.fencedHelpers >= 1, 'the fenced-runHelper answer mode must be exercised')
  assert.ok(counters.releaseImprovised >= 1, 'the improvising release courier mode must be exercised')

  // the live failure mode: the phase completed its panel but no terminal record was written.
  // Both review phases must end with a WRITTEN terminal-record carrying the correct verdict —
  // including the one whose staged payload was sabotaged on the first attempt.
  for (const phase of ['review-plan', 'review-tasks']) {
    const rec = files[`/tmp/showrunner-wi-mis-${phase}/terminal-record.json`]
    assert.ok(rec, `${phase} terminal-record.json must be written despite the misbehaving courier`)
    const parsed = JSON.parse(rec)
    assert.strictEqual(parsed.terminal, 'clean', `${phase} terminal record carries the real verdict`)
    assert.ok(!rec.includes('WRONG content'), `${phase} terminal record must not contain the sabotaged write`)
  }

  console.log(`ok: misbehaving-courier full run reaches ready with written terminal records ` +
    `(proseReads=${counters.proseReads} chattyAcks=${counters.chattyAcks} sabotaged=${counters.sabotagedWrites} ` +
    `mangledAnswers=${counters.mangledAnswers} fencedHelpers=${counters.fencedHelpers} releaseImprovised=${counters.releaseImprovised})`)
}

main().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
