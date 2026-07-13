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
//   (3) CONTENT-MANGLED SELF-VERIFIED LEAF — the review-plan terminal-record write's compose-terminal
//       leaf receives a MANGLED inline verdict on its first attempt (the courier content-mangle
//       class). The Python-side --verdict-hash self-check must refuse it (verdict-corrupt) and
//       writeTerminalRecord must retry and converge — the terminal record is composed Python-side
//       from on-disk state now (no oversized blob staged through the courier), so the record's only
//       courier exposure is this small, self-verifying scalar arg.
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
require('./_smoke_checkout_root.js')
const assert = require('assert')
const crypto = require('crypto')
const fs = require('fs')
const path = require('path')
const vm = require('vm')
const { markedStdout } = require('./_marked_stdout.js')

function sha256(text) { return crypto.createHash('sha256').update(String(text), 'utf8').digest('hex') }

const PR = { number: 7, url: 'https://github.com/o/r/pull/7', state: 'open', isDraft: false }
const PROSE = 'The command completed with no output, which means the file does not exist at that path.'
const CHATTY_ACK = 'Done! I successfully wrote the file as requested.'

const files = Object.create(null)
const usableCalls = Object.create(null)
// Stateful mini gate store (see stretch_budget smoke): pending until the chained set-gate flips
// it — read-gate rides --json on BOTH the front-half and build_phase reads post run-9 fix.
const gateStore = { plan: 'pending', tasks: 'pending' }
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
      const path = args[args.indexOf('--path') + 1]
      const record = JSON.parse(recordJson)
      let records = []
      try { records = JSON.parse(files[path] || '[]') } catch (_) { records = [] }
      records = records.filter((r) => r.round !== record.round)
      records.push(record)
      files[path] = JSON.stringify(records)
      // (4) first persist answer comes back as prose AFTER the write applied — the runtime
      // must retry and converge (the helper side answers idempotently on the real retry).
      if (counters.mangledAnswers === 0) {
        counters.mangledAnswers += 1
        return 'The round record was persisted successfully to the memory file.'
      }
      counters.mangledAnswers += 1
      return JSON.stringify({ ok: true, contentHash: sha256(files[path]) })
    }
    if (args[0] === 'compose-persist') throw new Error('compose-persist rode a leaf (D3 replaced it)')
    if (args[0] === 'update-round') return JSON.stringify({ ok: true, contentHash: 'ch-postfix' })
    if (args[0] === 'compose-terminal') {
      // The terminal record is composed Python-side from on-disk state; only the small verdict
      // scalars ride inline, self-verified by --verdict-hash. (3) CONTENT-MANGLE: mangle the
      // review-plan verdict on its FIRST compose attempt — the self-check must refuse it and the
      // caller must retry and converge (the write is never staged as an oversized courier blob).
      const target = args[args.indexOf('--path') + 1]
      let verdictJson = args[args.indexOf('--verdict-json') + 1]
      const wantHash = args[args.indexOf('--verdict-hash') + 1]
      if (target.endsWith('review-plan/terminal-record.json') && counters.sabotagedWrites === 0) {
        counters.sabotagedWrites += 1
        verdictJson = verdictJson + ' /*MANGLED*/'   // corrupt the inline arg -> hash mismatch
      }
      if (sha256(verdictJson) !== wantHash &&
          !(verdictJson.endsWith('\n') && sha256(verdictJson.slice(0, -1)) === wantHash)) {
        return JSON.stringify({ ok: false, reason: 'verdict-corrupt' })
      }
      const verdict = JSON.parse(verdictJson)
      files[target] = JSON.stringify(Object.assign({}, verdict, { runId: 'run-x' }))
      return JSON.stringify({ ok: true, contentHash: sha256(files[target]) })
    }
  }
  if (script.endsWith('review_setup_gather.py')) {
    // #211: the ONE pre-round gather leaf rides DECISIONS (resume + round-1 plan + coverage + deferred).
    // A misbehaving courier fences this read helper too (mode 5, below) — the bundle must still parse it.
    const dims = JSON.parse(args[args.indexOf('--dimensions') + 1] || '[]')
    const schedule = {}
    for (const d of dims) schedule[d] = { action: 'run', tier: 'reviewer-deep' }
    return JSON.stringify({
      ok: true,
      resume: { ok: true, state: 'missing', round: 1, contentHash: sha256(''), extras: null,
        confirmationPending: false, markedRound: null, roundCount: 0 },
      plan: { ok: true, round: 1, roundKind: 'baseline', enterConfirmation: false,
        escalationPolicy: 'deep-only', dimensions: schedule, carried: {}, latestCoverageDecisionIds: [] },
      deferredSet: {},
      coverage: { ok: true, decisions: [], contentHash: sha256('') },
    })
  }
  if (script.endsWith('review_loop_plan.py')) {
    // #211 deciders — small meaningful JSON. The canned run is one clean round per phase.
    const dims = JSON.parse((args.indexOf('--dimensions') >= 0 && args[args.indexOf('--dimensions') + 1]) ||
      (args.indexOf('--roster') >= 0 && args[args.indexOf('--roster') + 1]) || '[]')
    const round = Number(args[args.indexOf('--round') + 1]) || 1
    if (args[0] === 'plan-round') {
      const schedule = {}
      for (const d of dims) schedule[d] = { action: 'run', tier: 'reviewer-deep' }
      return JSON.stringify({ ok: true, round, roundKind: 'intermediate', enterConfirmation: false,
        escalationPolicy: 'deep-only', dimensions: schedule, carried: {}, latestCoverageDecisionIds: [],
        coverage: { ok: true, decisions: [], contentHash: sha256('') } })
    }
    if (args[0] === 'tally-round') {
      const gate = args[args.indexOf('--gate') + 1] || 'clean'
      const terminal = gate === 'clean' ? 'clean' : (gate === 'blocking' ? 'continue' : 'cannot-certify')
      const out = { ok: true, schemaVersion: 1, terminal, reason: 'clean', gate, confidence: 'high',
        round, missing: [], presentBlocking: 0, presentDeferred: 0, breaker: { halt: false } }
      if (terminal === 'clean') out.certification = { fullPanels: 0, lastPanelSurfacedResolved: false }
      return JSON.stringify(out)
    }
  }
  if (script.endsWith('review_telemetry.py')) return JSON.stringify({ ok: true, benchmarkValid: true })
  if (script.endsWith('review_handoff.py') && args[0] === 'collect') {
    const path = args[args.indexOf('--records-path') + 1]
    const text = path && files[path] != null ? files[path] : '[]'
    try {
      const records = JSON.parse(text)
      const findings = []
      if (Array.isArray(records)) {
        for (const rec of records) {
          if (!rec || !Array.isArray(rec.findings)) continue
          for (const f of rec.findings) {
            if (!f || !f.severity) continue
            const sev = String(f.severity).toLowerCase()
            if (sev !== 'minor' && sev !== 'nit') continue
            const e = Object.assign({}, f)
            e.planSection = f.planSection || f.docSection || f.section || f.dimension || ''
            findings.push(e)
          }
        }
      }
      return JSON.stringify({ ok: true, findings })
    } catch (_) {
      return JSON.stringify({ ok: false, reason: 'unreadable' })
    }
  }
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
  // /dev/null) && fenced_json.py, all ONE leaf. The terminal-record write no longer stages here — it
  // is composed Python-side via compose-terminal, and the content-mangle regression moved to that
  // self-verified inline path (see the compose-terminal handler in runHelperResponse). Any remaining
  // fenced write decodes honestly, then answers the helper.
  // argv shape (finding #13): python3 -c '<writer>' '<path>' '<b64>' >/dev/null && helper
  const cw = cmd.match(/^python3 -c '[\s\S]*?' '([^']*)' '([A-Za-z0-9+/=]*)' >\/dev\/null && ([\s\S]*?) 2>&1; echo __SR_EXIT:\$\?$/)
  if (cw) {
    const helper = cw[3]
    const staged = cw[1]
    files[staged] = Buffer.from(cw[2], 'base64').toString('utf8')
    const out = runHelperResponse(helper)
    return (out != null ? out : '{}') + '\n__SR_EXIT:0'
  }
  // The OPAQUE write transport (base64 python heredoc) — for the remaining standalone io.writeFile
  // leaves (test-pilot artifacts, last-extras). The write's answer is a conversational ack (mode 2).
  const bw = cmd.match(/^python3 -c '[\s\S]*?' '([^']*)' '([A-Za-z0-9+/=]*)'$/)
  if (bw) {
    const target = bw[1]
    files[target] = Buffer.from(bw[2], 'base64').toString('utf8')
    counters.chattyAcks += 1
    return CHATTY_ACK   // (2) the write's answer is conversational, never the command's stdout
  }
  if (cmd.startsWith('mkdir -p')) return ''
  if (/^python3 -c '[^']*os\.makedirs[^']*' '[^']*'$/.test(cmd)) return ''   // argv-shape mkdirp
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
    if (/review_setup_gather\.py|review_loop_plan\.py|review_memory\.py' 'load-summary'|coverage_decisions\.py|review_telemetry\.py/.test(cmd)) {
      counters.fencedHelpers += 1
      return '```\n' + body + '\n```'
    }
    return body
  }
  if (cmd.includes('recover_entry.py')) {
    return markedStdout({ checkpoint: null, world: {}, generation: 5, root: process.cwd() })
  }
  if (cmd.includes('front_half_usable.py')) {
    const doc = (cmd.match(/--doc '?(plan|tasks)/) || [])[1] || 'plan'
    usableCalls[doc] = (usableCalls[doc] || 0) + 1
    return JSON.stringify({ usable: usableCalls[doc] > 1, recorded: 'x', expected: 'x', missing_sections: [], placeholder: false })
  }
  if (cmd.includes('definition_doc.py read-gate')) {
    const doc = (cmd.match(/--doc '?(plan|tasks)/) || [])[1] || 'plan'
    const body = JSON.stringify({ review: gateStore[doc] || 'pending' })
    // FENCE the build-phase read's answer (bare `--doc tasks` — the run-9 wf_b69571d9
    // misbehavior): the whole-answer single fence must still parse under the gate read's strict
    // extraction and the run must still reach ready. The front-half readGate (shq-quoted --doc)
    // stays bare — its exec leg does a bare JSON.parse and fencing it is not this PR's scope.
    return /--doc tasks /.test(cmd) ? '```json\n' + body + '\n```' : body
  }
  if (cmd.includes('checkpoint_entry.py')) return JSON.stringify({ pr: PR })
  if (cmd.includes('phase_progress_entry.py')) {
    return markedStdout({ ok: true, journal_confirmed: true, checkpoint_confirmed: true })
  }
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
  if (cmd.includes('review_handoff.py') && cmd.includes(' collect ')) {
    const path = (cmd.match(/--records-path '([^']+)'/) || [])[1]
    const text = path && files[path] != null ? files[path] : '[]'
    try {
      const records = JSON.parse(text)
      const findings = []
      if (Array.isArray(records)) {
        for (const rec of records) {
          if (!rec || !Array.isArray(rec.findings)) continue
          for (const f of rec.findings) {
            if (!f || !f.severity) continue
            const sev = String(f.severity).toLowerCase()
            if (sev !== 'minor' && sev !== 'nit') continue
            const e = Object.assign({}, f)
            e.planSection = f.planSection || f.docSection || f.section || f.dimension || ''
            findings.push(e)
          }
        }
      }
      return JSON.stringify({ ok: true, findings })
    } catch (_) {
      return JSON.stringify({ ok: false, reason: 'unreadable' })
    }
  }
  if (cmd.includes('review_handoff.py') && cmd.includes(' write ')) {
    return JSON.stringify({ ok: true, counts: { distinct: 0 } })
  }
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
  'read startup state': () => markedStdout({ ok: true, spec_gate: 'passed', model_overrides: {}, doc_dir: '', engine_prefs: {}, run_overrides_present: false }),
  'save phase progress': (prompt) => {
    // With prose reads live, ANY runtime-computed doc hash on the set-gate is prose-poisoned —
    // the fence must ride the Python-side 'current' sentinel (red: the pre-hardening bundle
    // ships contentHash(PROSE) here and this throw parks the run).
    if (/set-gate/.test(prompt) && !/--expected-hash 'current'/.test(prompt)) {
      throw new Error('set-gate rode a runtime-computed hash — courier-read text entered a fence')
    }
    // Chained set-gate flips the mini gate store (see gateStore comment above).
    const sg = String(prompt).match(/set-gate --doc '?(plan|tasks)'?[\s\S]*?--review '?([a-z-]+)'?/)
    if (sg) gateStore[sg[1]] = sg[2]
    return markedStdout({ ok: true, journal_confirmed: true, checkpoint_confirmed: true })
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
  [/^implement task .+ of \d+$/, () => ({ ok: true, signal: 'ok', evidence: { testPassed: true, testFailed: false } })],
  [/^review task .+:r\d+$/, () => ({ verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] })],
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

  // every misbehavior mode actually fired. NOTE (#211): the review loop's last prose-vulnerable JS
  // read — the deferred-set cat — moved Python-side (the tally decider reads it via --deferred-path,
  // fail-soft to {} on a missing/odd file), so the whole pipeline no longer does a missing-file JS
  // cat and proseReads is 0. The prose shim stays as a defensive net (a future JS read that cats a
  // missing file would return prose and the "reaches ready" + terminal-record checks would catch any
  // poisoning). The decider answers are instead stress-tested by the FENCED-answer mode below (now
  // covering review_loop_plan.py) and by showrunner_reviewloop_adversarial_smoke.js (fail-closed).
  assert.strictEqual(counters.proseReads, 0,
    '#211: the review loop no longer does a prose-vulnerable JS missing-file read (deferred read is Python-side)')
  assert.ok(counters.chattyAcks >= 1, 'the chatty-write-ack mode must be exercised')
  assert.strictEqual(counters.sabotagedWrites, 1, 'the content-mangled compose-terminal verdict must fire exactly once')
  assert.ok(counters.mangledAnswers >= 2, 'the mangled persist answer must be retried (>=2 helper calls)')
  assert.ok(counters.fencedHelpers >= 1, 'the fenced-runHelper answer mode must be exercised')
  assert.ok(counters.releaseImprovised >= 1, 'the improvising release courier mode must be exercised')

  // the live failure mode: the phase completed its panel but no terminal record was written.
  // Both review phases must end with a WRITTEN terminal-record carrying the correct verdict —
  // including review-plan, whose compose-terminal verdict was mangled on its first attempt (the
  // --verdict-hash self-check refused it and writeTerminalRecord retried to the honest verdict).
  for (const phase of ['review-plan', 'review-tasks']) {
    const rec = files[`/tmp/showrunner-wi-mis-${phase}/terminal-record.json`]
    assert.ok(rec, `${phase} terminal-record.json must be written despite the misbehaving courier`)
    const parsed = JSON.parse(rec)
    assert.strictEqual(parsed.terminal, 'clean', `${phase} terminal record carries the real verdict`)
    assert.ok(!rec.includes('MANGLED'), `${phase} terminal record must not persist the mangled verdict`)
  }

  console.log(`ok: misbehaving-courier full run reaches ready with written terminal records ` +
    `(proseReads=${counters.proseReads} chattyAcks=${counters.chattyAcks} sabotaged=${counters.sabotagedWrites} ` +
    `mangledAnswers=${counters.mangledAnswers} fencedHelpers=${counters.fencedHelpers} releaseImprovised=${counters.releaseImprovised})`)
}

main().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
