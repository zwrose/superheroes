// plugins/superheroes/lib/tests/showrunner_stretch_budget_smoke.js
// #118 acceptance harness for the RUNTIME leaf shape — the gap the 2026-07-02 live run exposed:
// nothing asserted (a) how many courier leaves each stretch fires or (b) which MODEL a dumb-pipe
// leaf resolves to, so cmdRunner leaves silently ran at the session model (~41k tokens per
// command echo) and startup grew a third leaf, invisible to every existing smoke.
//
// This smoke drives a CANNED FULL RUN (green path to 'ready') through the COMMITTED BUNDLE —
// showrunner.bundle.js evaluated in a vm sandbox — so every leaf passes through the preamble's
// agent wrapper exactly as in production: the model pin resolves, __SR_PHASE threads onto
// opts.phase, and the 'lib'/'io' relabel applies. The canned shim underneath records
// {label, model, phase} per dispatch and emulates the leaf-bash io with an in-memory FS.
//
// Assertions (the #118 spec's Labels matrix, encoded as the fixture below):
//   (1) MODEL PIN (FR — dumb pipes ride the cheapest tier): every leaf whose label is not a
//       genuine-model agent resolves to DEFAULT_TIERS.mechanical; genuine agents never do.
//   (2) PER-PHASE LEAF BUDGET (FR-1): the courier-leaf count per phase (the __SR_PHASE progress
//       group) stays within PHASE_BUDGETS — pinned from the matrix + the sanctioned as-built
//       leaves, so ANY future courier growth in a phase fails CI here.
//   (3) EVERY-PHASE TAIL (FR-6): each non-terminal phase persists via exactly ONE
//       'save phase progress' leaf; journal_entry.py / checkpoint_entry.py never ride their own
//       leaves (checkpoint_entry --read-pr, the ship-entry READ, is the one allowed appearance).
//   (4) STARTUP = the deliberately-two-leaf stretch (FR-1 logged exception): the world-snapshot
//       gate + ONE folded gather; engine_pref_load.py must not appear as its own leaf.
//   (5) LABEL SET (FR-10): every observed label is in the matrix-derived allowlist.
'use strict'
require('./_smoke_checkout_root.js')
const assert = require('assert')
const crypto = require('crypto')
const fs = require('fs')
const path = require('path')
const vm = require('vm')
const { markedStdout } = require('./_marked_stdout.js')

const CHEAPEST = require('../model_tier.js').DEFAULT_TIERS.mechanical
const PAYLOAD_TIER = require('../model_tier.js').DEFAULT_TIERS.fixer

// #191: payload-carrying couriers (receipt-emitting entry loads + chunk relays) ride the
// copy-faithful fixer tier — plain-cheapest couriers regenerate/transform large relay answers.
// The payload marker is preamble-only (stripped before the runtime call), so the smoke
// recognizes the sanctioned exception by label + tier.
const PAYLOAD_COURIERS = [/^review_setup_gather\.py$/, /^review_memory\.py$/]
function isPayloadCourier(label, model) {
  return model === PAYLOAD_TIER && PAYLOAD_COURIERS.some((re) => re.test(label))
}

// ── The #118 Labels matrix, as the fixture ─────────────────────────────────────────────────────
// Genuine-model agents (spec "Genuine-model agents (judgment)") — never pinned to the cheapest tier.
const GENUINE = [
  /^author-(plan|tasks)$/,
  /^(architecture|code|security|test|premortem)-reviewer(:r\d+)?$/,
  /^synthesis:r\d+$/,
  /^revise-doc$/,
  /^implement task .+ of \d+$/,
  /^review task .+:r\d+$/,
  /^fix task /,
  /^fix-(branch|code|ci|app-bug)$/,
  /^branch-reviewer:r\d+$/,
  /^plan-tests$/,
  /^browser-pass$/,
  /^compose PR body$/,             // #219: the Sonnet draft-PR body composer (a genuine judgment leaf)
]
function isGenuine(label) { return GENUINE.some((re) => re.test(label)) }

// Courier / dumb-pipe labels the matrix sanctions (surviving-leaf names + the io/exec transports
// + the *.py relabel the bundle preamble applies to 'lib'/'io' leaves).
const COURIER_ALLOW = [
  /^exec$/,                        // the exec dumb-pipe (incl. world-snapshot, fences, head reads)
  /^io(:(read|write|mkdir))?$/,    // leaf-bash io ops that carry no .py to relabel from
  /^[\w-]+\.py( [\w-]+)?$/,        // preamble __leafLabel relabel of 'lib'/'io' (script + subcommand)
  /^read startup state$/,
  /^read (plan|tasks) draft$/,
  /^read gate$/,
  /^save phase progress$/,
  /^save round state$/,
  /^run verify$/,
  /^readout$/,
  /^gather build state$/,
  /^record task (built|reviewed)$/,
  /^read verify \+ minors$/,
  /^stamp (build|review) coverage$/,
  /^reset-uncommitted$/,
  /^resolve review target$/,
  /^open draft PR$/,
  /^mark PR ready$/,
  /^read test context$/,
  /^prepare test run$/,
  /^write test status$/,
  /^publish tested head$/,
  /^check ship-readiness$/,
  /^prepare CI fix$/,
  /^push CI fix \+ recheck$/,
  /^post readout$/,
  /^release lease$/,               // the dedicated hardened lease-release courier (BUG C — was 'exec')
  // #151: the descriptive exec-courier labels that replaced the bare 'exec' dumb pipe. Same leaves,
  // same per-phase counts — only the display purpose changed (routing still rides courier:true).
  /^gather snapshot$/,             // reconcile: recover_entry.py --snapshot
  /^check draft$/,                 // producePhase: front_half_usable.py --emit-signals
  /^prepare build$/,               // buildPhase: build_entry.py
  /^read tasks$/,                  // buildPhase: task_list_cli.py
  /^fence lease$/,                 // build/ship fence: fence_cli.py
  /^check trailers$/,              // buildPhase per-task: build_state_cli.py gather (trailer check)
  /^write provenance$/,            // buildPhase: prov_entry.py
  /^resolve head$/,                // resolveHead: git rev-parse
  /^read pr$/,                     // loadPr: checkpoint_entry.py --read-pr
  /^pr-body context$/,             // #219: composePrBody's context courier (pr_body.py context)
  /^write plan hand-off$/,         // #397: review_handoff.py write at plan-review terminal
  /^read nonblocking findings$/,   // #397: review_handoff.py collect at plan-review terminal
]
function isAllowedCourier(label) { return COURIER_ALLOW.some((re) => re.test(label)) }

// Per-phase courier-leaf budgets for THIS canned green run (1 doc-review round, 1 build task,
// clean review-code round, passing test-pilot, green ship). Each budget is a CEILING pinned at
// the observed as-built count; the breakdown comments map every leaf to its matrix row so a
// future courier added to a phase fails here and has to justify itself against the matrix.
const PHASE_BUDGETS = {
  // Task 12 (FR-8/UFR-9): the run-start rules freeze — ONE 'io' bookkeeping leaf that snapshots the
  // provenance-valid rules for this run (permission_rules.freeze_run_rules via the io() runHelper
  // shim). Grouped under its own phase so it never inflates the sanctioned two-leaf startup stretch.
  'permission-freeze': 1,
  // read world-snapshot (exec) + read startup state — the FR-1 two-leaf exception. Was 3 before
  // #118 conformance (engine_pref_load.py rode its own exec leaf).
  startup: 2,
  // read draft signals (pre-author) + post-author marker verify + save phase progress
  plan: 3,
  tasks: 3,
  // read-gate exec (1) + #211 pre-round SETUP GATHER (1 — run-dir mkdir + resume DECISION + round-1
  // plan + deferred seed + coverage, folded Python-side by review_setup_gather.py) + persist-skeleton
  // (1) + #211 tally-round DECIDER (1 — breaker + terminal + certification from disk; the ONE new
  // decider leaf per round, plan folds into the gather, compose-fix-context folds into tally) +
  // telemetry write (1) + save round state (1) + terminal-record compose-terminal write as ONE leaf
  // (1) + io:read nonblocking findings (1) + io:write nonblocking.json staging (1) + save phase progress
  // (1) + #397 plan-handoff.json write (1). Was 7 pre-#211 (in-memory tally), 12 post-D3, 35 pre-D3,
  // 8 pre-#397, 9 pre-Task-15 (handoff skipped when zero findings).
  'review-plan': 11,
  'review-tasks': 8,
  // entry gathers (read-gate, build_entry, task list, fence — exec) + gather build state ×2 +
  // per-task record-built/record-reviewed + verify+minors + final-review round: #211 setup gather
  // (1 — folds resume + plan + coverage + deferred) + run verify + persist-skeleton + tally-round
  // decider + telemetry write + stamp build coverage + prov exec + save phase progress. Was 19
  // pre-#211 (separate load-summary + coverage + deferred reads, in-memory tally), 24 pre-D3.
  // Task 12 (FR-8, #149): +1 per built task — the record_composed 'io' leaf that freezes the
  // spine-composed leaf command into this run's composed-exact allow set (1 task in this canned run).
  workhorse: 19,
  // resolve review target (the ONE entry gather: worktree + head + config + cwd-head) + #211 pre-round
  // SETUP GATHER (1 — run-dir mkdir + resume DECISION + round-1 plan + coverage, folded Python-side) +
  // one panel round (run verify, persist-skeleton, #211 tally-round decider, telemetry write = 4) +
  // final/cwd head reads (2 exec) + stamp review coverage + save phase progress. Was 9 pre-#211
  // (in-memory tally), 12 post-D3, 29 pre-D3. (The clean green path parks nothing, so
  // renderAndPostReadout's terminal-record compose-terminal write does not fire here.)
  'review-code': 10,
  // #219: resolve review target (the SAME build-worktree entry gather review-code/test-pilot/ship
  // use — review finding: composePrBody and pr_entry's --worktree must describe the build branch,
  // not the launch checkout, so draft-PR resolves it too) + pr-body context (composePrBody's Python
  // gather courier, now rooted at the resolved worktree) + io:write (the composed body's durable
  // file) + open draft PR + save phase progress. The Sonnet 'compose PR body' leaf itself is a
  // genuine judgment agent (not a courier), so it does not count here. Was 2 pre-#219, 4 pre-worktree-fix.
  'draft-PR': 5,
  // resolve review target (build-worktree pin) + read test context + plan/results/server/seed
  // artifact staging (writeJson = mkdir+write pairs) + prepare test run + milestone status writes
  // + final artifacts + restore-baseline + write test status + publish tested head + save phase
  // progress; the four deciders (applicability/budget/aggregate/retry) are twins — 0 leaves
  'test-pilot': 36,
  // mark PR ready + save phase progress
  'mark-ready': 2,
  // read PR (checkpoint_entry --read-pr) + resolve review target + renew fence + check
  // ship-readiness (the folded green path) + post readout (hand-back) + lease release (the
  // dedicated hardened 'release lease' courier, BUG C — still ONE leaf, was label 'exec')
  ship: 6,
}

// Phases whose tail must persist via exactly ONE 'save phase progress' leaf (FR-6). 'ship' is
// terminal (hand-back/park precedes any further cursor write).
const TAIL_PHASES = ['plan', 'review-plan', 'tasks', 'review-tasks', 'workhorse',
                     'review-code', 'draft-PR', 'test-pilot', 'mark-ready']

// ── canned leaf responses ──────────────────────────────────────────────────────────────────────
function sha256(text) { return crypto.createHash('sha256').update(String(text), 'utf8').digest('hex') }

const PR = { number: 7, url: 'https://github.com/o/r/pull/7', state: 'open', isDraft: false }

// In-memory FS backing the leaf-bash io emulation (writes then read-backs must round-trip so the
// fenced writes' hash verification passes with REAL hashes).
const files = Object.create(null)
const usableCalls = Object.create(null)   // per-doc draft-signal call count (1st: not usable)
// Stateful mini gate store: pending until the phase tail's chained set-gate flips it. Both the
// front-half readGate AND build_phase's UFR-1 entry read now ride --json (the run-9 fenced-answer
// fix), so the old plain-vs-json discriminator can't tell them apart — the gate LIFECYCLE can.
const gateStore = { plan: 'pending', tasks: 'pending' }

function runHelperResponse(cmdline) {
  // runHelper prompts quote each argv element: 'python3' 'plugins/...X.py' 'sub' '--flag' 'v' ...
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
      // D3: the ONE verified round-record leaf — the inline skeleton must self-verify
      // (record-hash == sha256 of record-json) and must never carry evidence bodies.
      const recordJson = args[args.indexOf('--record-json') + 1]
      if (sha256(recordJson) !== args[args.indexOf('--record-hash') + 1]) {
        throw new Error('persist-skeleton --record-hash does not match --record-json')
      }
      if (recordJson.includes('"evidence"')) throw new Error('persist-skeleton shipped finding bodies (D3 skeleton contract)')
      const path = args[args.indexOf('--path') + 1]
      const record = JSON.parse(recordJson)
      let records = []
      try { records = JSON.parse(files[path] || '[]') } catch (_) { records = [] }
      records = records.filter((r) => r.round !== record.round)
      records.push(record)
      files[path] = JSON.stringify(records)
      return JSON.stringify({ ok: true, contentHash: sha256(files[path]) })
    }
    if (args[0] === 'compose-terminal') {
      const p = args[args.indexOf('--path') + 1]
      const verdictJson = args[args.indexOf('--verdict-json') + 1]
      if (sha256(verdictJson) !== args[args.indexOf('--verdict-hash') + 1]) {
        throw new Error('compose-terminal --verdict-hash does not match --verdict-json')
      }
      const record = JSON.parse(verdictJson)
      record.fixes = []
      record.deferred = []
      record.coverageDecisions = []
      record.runId = args[args.indexOf('--run-id') + 1]
      if (args.includes('--lease')) record.lease = args[args.indexOf('--lease') + 1]
      files[p] = JSON.stringify(record)
      return JSON.stringify({ ok: true, contentHash: sha256(files[p]) })
    }
    if (args[0] === 'compose-persist') {
      throw new Error('compose-persist rode a leaf — the D3 skeleton persist replaced the staging ceremony')
    }
    if (args[0] === 'update-round') {
      const updatesJson = args[args.indexOf('--updates-json') + 1]
      if (sha256(updatesJson) !== args[args.indexOf('--updates-hash') + 1]) {
        throw new Error('update-round --updates-hash does not match --updates-json')
      }
      return JSON.stringify({ ok: true, contentHash: 'ch-postfix' })
    }
    if (args[0] === 'compose-terminal') {
      // the terminal record is composed Python-side from on-disk state in ONE leaf — the inline
      // verdict must self-verify (verdict-hash == sha256 of verdict-json) and must never carry
      // evidence bodies (findings ride round-records.json / round-bodies, never the courier).
      const verdictJson = args[args.indexOf('--verdict-json') + 1]
      if (sha256(verdictJson) !== args[args.indexOf('--verdict-hash') + 1]) {
        throw new Error('compose-terminal --verdict-hash does not match --verdict-json')
      }
      if (verdictJson.includes('"evidence"') || verdictJson.includes('"findings"')) {
        throw new Error('compose-terminal shipped an evidence-bodied verdict through the courier')
      }
      const p = args[args.indexOf('--path') + 1]
      files[p] = verdictJson
      return JSON.stringify({ ok: true, contentHash: sha256(files[p]) })
    }
  }
  if (script.endsWith('review_setup_gather.py')) {
    // #211: the ONE pre-round gather leaf rides DECISIONS — resume + round-1 plan + coverage +
    // deferred, folded Python-side. A fresh canned run has no prior records/coverage/deferrals.
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
    // #211 deciders — small meaningful JSON, never findings. The canned green run is one clean round
    // per phase, so tally answers `clean` (the gate the shell computed from clean reviewers rides down).
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
    const stagedText = files[staged] != null ? files[staged] : '{}'
    // D3: the 2-leaf fenced write — the helper verifies the staged text's hash itself,
    // tolerating exactly the ONE trailing newline the heredoc write appends (mirrors
    // fenced_json.py staged_hash_ok; the shim's heredoc emulation appends it faithfully).
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
    // the loop's coverage read is a Python-side helper (courier prose never enters the fence)
    if (args[0] === 'load') return JSON.stringify({ ok: true, decisions: [], contentHash: sha256('') })
    return JSON.stringify({ ok: true })
  }
  return '{}'
}

// Answer one shell command the leaf-bash io (or an exec/courier pipe) would run.
function shellResponse(cmd) {
  // withTargetCommandPrompts prefixes review-code commands with `cd '<worktree>' && ` — strip it
  // so the path/command routing below still matches.
  cmd = cmd.replace(/^cd '[^']*' && /, '')
  // fold 1 (#141): the CHAINED stage+verify write — [mkdir &&] opaque base64 stage-write (stdout to
  // /dev/null) && the fenced_json.py helper, all one leaf. Decode the payload into the in-memory FS
  // FIRST so the helper's --payload-hash check sees the real staged bytes, then answer the helper.
  const cw = cmd.match(/^python3 -c '[\s\S]*?' '([^']*)' '([A-Za-z0-9+/=]*)' >\/dev\/null && ([\s\S]*?) 2>&1; echo __SR_EXIT:\$\?$/)
  if (cw) {
    files[cw[1]] = Buffer.from(cw[2], 'base64').toString('utf8')
    const out = runHelperResponse(cw[3])
    return (out != null ? out : '{}') + '\n__SR_EXIT:0'
  }
  // The OPAQUE write transport: base64 payload in a python heredoc, decoded byte-exact.
  const bw = cmd.match(/^python3 -c '[\s\S]*?' '([^']*)' '([A-Za-z0-9+/=]*)'$/)
  if (bw) { files[bw[1]] = Buffer.from(bw[2], 'base64').toString('utf8'); return 'ok' }
  // Legacy cat-heredoc write (pre-opaque bundles): body+'\n' lands on disk — model that
  // faithfully; the staged-hash checks tolerate exactly the one transport-appended newline.
  const w = cmd.match(/cat > '([^']+)' <<'__SR_EOF__'\n([\s\S]*)\n__SR_EOF__$/)
  if (w) { files[w[1]] = w[2] + '\n'; return '' }
  if (cmd.startsWith('mkdir -p')) return ''
  if (/^python3 -c '[^']*os\.makedirs[^']*' '[^']*'$/.test(cmd)) return ''   // argv-shape mkdirp
  const r = cmd.match(/^cat '([^']+)'/)
  if (r) return files[r[1]] != null ? files[r[1]] : ''
  if (cmd.includes("'python3'")) {
    const out = runHelperResponse(cmd)
    if (out != null) return out + '\n__SR_EXIT:0'
    return '{}\n__SR_EXIT:0'
  }
  // single-command exec/courier pipes, routed by content:
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
    return JSON.stringify({ review: gateStore[doc] || 'pending' })
  }
  if (cmd.includes('engine_pref_load.py')) throw new Error('engine_pref_load.py dispatched as its own leaf (#118 startup fold)')
  if (cmd.includes('journal_entry.py')) throw new Error('journal_entry.py rode its own leaf (#118 every-phase tail)')
  if (cmd.includes('checkpoint_entry.py') && !cmd.includes('--read-pr')) {
    throw new Error('checkpoint_entry.py write rode its own leaf (#118 every-phase tail)')
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

// Courier prompts wrap ONE command; exec() prompts wrap a numbered list; cmdRunner prompts
// ("Use the Bash tool …") return a StructuredOutput OBJECT. Extract + answer accordingly.
function answerCommandPrompt(prompt) {
  const idx = prompt.indexOf('\n\n')
  const body = idx >= 0 ? prompt.slice(idx + 2) : prompt
  if (/^\d+\. /m.test(body) && prompt.startsWith('Run each')) {
    // exec batch: answer each numbered command as a row
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
    // The review-phase tail chains set-gate ahead of the save — flip the mini gate store so the
    // NEXT read-gate (workhorse's UFR-1 entry read of the tasks doc) sees the passed gate.
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
  // #219: the composePrBody context gather (no usable prior body -> the fresh compose path runs).
  'pr-body context': () => JSON.stringify({ work_item: 'wi', commits: [], prior_body_usable: false }),
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
  [/^compose PR body$/, () => ({ body: 'A composed body.\n\nCloses #219' })],   // #219 Sonnet draft-PR body
]

const calls = []
async function cannedAgent(prompt, opts) {
  const label = (opts && opts.label) || ''
  calls.push({ label, model: opts && opts.model, phase: (opts && opts.phase) || '(none)', prompt: String(prompt) })
  for (const [re, fn] of GENUINE_RESPONSES) {
    if (re.test(label)) return fn(prompt)
  }
  if (label === 'run verify') return { command: 'none', returncode: 0, timedOut: false }
  if (COURIER_JSON[label]) return COURIER_JSON[label](String(prompt))
  return answerCommandPrompt(String(prompt))
}

// ── drive the bundle ───────────────────────────────────────────────────────────────────────────
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
  // __SR_RUN=false: evaluate the preamble + module registry without the ENTRY's args plumbing.
  vm.runInContext('globalThis.__SR_RUN = false;\n;(async () => {\n' + text + '\n})();', sandbox, { timeout: 10000 })
  const sr = sandbox.globalThis.__sr_require('showrunner.js')

  const outcome = await sr.showrunner({ workItem: 'wi-conf' })
  // SR_STRETCH_DEBUG=1 dumps every recorded leaf — use it when pinning a new budget.
  if (process.env.SR_STRETCH_DEBUG) {
    const n = Number(process.env.SR_STRETCH_DEBUG) > 1 ? Number(process.env.SR_STRETCH_DEBUG) : 120
    for (const c of calls) console.error(`${c.phase} | ${c.label} | model=${c.model} | ${c.prompt.slice(0, n).replace(/\n/g, ' ')}`)
  }
  assert.strictEqual(outcome.outcome, 'ready',
    `the canned green run must reach 'ready' (got ${JSON.stringify(outcome)})`)

  // CLASS GUARD: no leaf may ever inherit the Workflow session model. The bundle wrapper is the
  // choke point, so every fake-runtime agent invocation must arrive with an explicit opts.model.
  const modelLess = calls.filter((c) => c.model === undefined || c.model === null)
  assert.deepStrictEqual(
    modelLess.map((c) => `${c.phase}/${c.label}`),
    [],
    'no agent invocation may reach the runtime without opts.model')

  // (1) MODEL PIN: every non-genuine leaf resolves to the cheapest (mechanical) tier; no genuine
  // agent is ever pinned there.
  const unpinned = calls.filter((c) => !isGenuine(c.label) && c.model !== CHEAPEST && !isPayloadCourier(c.label, c.model))
  assert.deepStrictEqual(
    unpinned.map((c) => `${c.phase}/${c.label}=${c.model}`), [],
    'every dumb-pipe leaf must resolve to the mechanical (cheapest) model tier')
  const pinnedGenuine = calls.filter((c) => isGenuine(c.label) && c.model === CHEAPEST)
  assert.deepStrictEqual(
    pinnedGenuine.map((c) => `${c.phase}/${c.label}`), [],
    'no genuine-model agent may be pinned to the mechanical tier')

  // (5) LABEL SET: every non-genuine label is a matrix-sanctioned courier label.
  const strayLabels = [...new Set(calls.filter((c) => !isGenuine(c.label) && !isAllowedCourier(c.label)).map((c) => c.label))]
  assert.deepStrictEqual(strayLabels, [], 'every courier label must be in the #118 matrix allowlist')

  // (2) PER-PHASE LEAF BUDGET: courier leaves per __SR_PHASE progress group stay within budget.
  const perPhase = {}
  for (const c of calls) {
    if (isGenuine(c.label)) continue
    perPhase[c.phase] = (perPhase[c.phase] || 0) + 1
  }
  for (const [phase, count] of Object.entries(perPhase)) {
    const budget = PHASE_BUDGETS[phase]
    assert.ok(budget != null, `phase '${phase}' fired courier leaves but has no budget in the fixture`)
    assert.ok(count <= budget,
      `phase '${phase}' fired ${count} courier leaves (budget ${budget}) — a stretch grew; ` +
      `justify against the #118 matrix or fold the new leaf`)
  }

  // (4) STARTUP is the deliberately-two-leaf stretch; assert EXACTLY the matrix shape.
  const startup = calls.filter((c) => c.phase === 'startup' && !isGenuine(c.label))
  assert.strictEqual(startup.length, 2,
    `startup must be the two-leaf stretch (world-snapshot + folded gather); got ` +
    startup.map((c) => c.label).join(', '))
  assert.ok(startup.some((c) => c.prompt.includes('recover_entry.py')), 'startup leaf 1 is the world-snapshot gate')
  assert.ok(startup.some((c) => c.label === 'read startup state' && c.prompt.includes('engine_pref')),
    'startup leaf 2 is the folded gather (spec-gate + overrides + doc dir + engine prefs)')

  // (3) EVERY-PHASE TAIL: exactly one 'save phase progress' per non-terminal phase; review phases
  // chain their set-gate INSIDE it (FR-4 persist order).
  for (const phase of TAIL_PHASES) {
    const tails = calls.filter((c) => c.phase === phase && c.label === 'save phase progress')
    assert.strictEqual(tails.length, 1, `phase '${phase}' must persist via exactly ONE save phase progress leaf (got ${tails.length})`)
    assert.ok(tails[0].prompt.includes('phase_progress_entry.py save'), `phase '${phase}' tail rides phase_progress_entry.py save`)
    if (phase === 'review-plan' || phase === 'review-tasks') {
      assert.ok(tails[0].prompt.includes('set-gate') && tails[0].prompt.indexOf('set-gate') < tails[0].prompt.indexOf('phase_progress_entry.py'),
        `phase '${phase}' tail chains the set-gate side effect ahead of the save (FR-4)`)
    }
  }

  // Emit the observed per-phase counts so a budget bump is a conscious, reviewable edit.
  const summary = Object.entries(perPhase).map(([p, n]) => `${p}=${n}`).join(' ')
  console.log(`ok: #118 stretch/model conformance over the bundle (courier leaves: ${summary})`)
}

main().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
