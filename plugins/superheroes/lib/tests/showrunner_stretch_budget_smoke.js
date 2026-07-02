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
const assert = require('assert')
const crypto = require('crypto')
const fs = require('fs')
const path = require('path')
const vm = require('vm')

const CHEAPEST = require('../model_tier.js').DEFAULT_TIERS.mechanical

// ── The #118 Labels matrix, as the fixture ─────────────────────────────────────────────────────
// Genuine-model agents (spec "Genuine-model agents (judgment)") — never pinned to the cheapest tier.
const GENUINE = [
  /^author-(plan|tasks)$/,
  /^(architecture|code|security|test|premortem)-reviewer(:r\d+)?$/,
  /^synthesis:r\d+$/,
  /^revise-doc$/,
  /^implement-task$/,
  /^task-reviewer:r\d+$/,
  /^fix-(task|branch|code|ci|app-bug)$/,
  /^branch-reviewer:r\d+$/,
  /^plan-tests$/,
  /^browser-pass$/,
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
]
function isAllowedCourier(label) { return COURIER_ALLOW.some((re) => re.test(label)) }

// Per-phase courier-leaf budgets for THIS canned green run (1 doc-review round, 1 build task,
// clean review-code round, passing test-pilot, green ship). Each budget is a CEILING pinned at
// the observed as-built count; the breakdown comments map every leaf to its matrix row so a
// future courier added to a phase fails here and has to justify itself against the matrix.
const PHASE_BUDGETS = {
  // read world-snapshot (exec) + read startup state — the FR-1 two-leaf exception. Was 3 before
  // #118 conformance (engine_pref_load.py rode its own exec leaf).
  startup: 2,
  // read draft signals (pre-author) + post-author marker verify + save phase progress
  plan: 3,
  tasks: 3,
  // read-gate exec (1) + one panel round: load-summary (1), last-extras read (1), coverage read
  // (1), 5 staged dim writes + 5 mkdirs + 5 hash verifies (the #136 hash-verified staging),
  // compose-persist (1), deferred-set read (1), telemetry read+write (2) + save round state (1)
  // + reviewed-doc reads + terminal-record fence (read, mkdir, stage-write, hash, fenced write)
  // + save phase progress (1). This count is DOMINATED by the #129/#136 per-op io surface —
  // the defect-4 batching proposal in PR #118-conformance targets exactly these leaves.
  'review-plan': 35,
  'review-tasks': 35,
  // entry gathers (read-gate, build_entry, task list, fence — 6 exec) + gather build state +
  // per-task record-built/record-reviewed + verify+minors + final-review round (run verify +
  // round-record io + review_memory/telemetry helpers) + stamp build coverage + prov exec
  // + save phase progress
  workhorse: 24,
  // resolve review target (the ONE entry gather: worktree + head + config + cwd-head) + one panel
  // round (as review-plan, incl. run verify) + final/cwd head reads (2 exec) + terminal-record
  // fence + stamp review coverage + save phase progress
  'review-code': 29,
  // open draft PR + save phase progress
  'draft-PR': 2,
  // resolve review target (build-worktree pin) + read test context + plan/results/server/seed
  // artifact staging (writeJson = mkdir+write pairs) + prepare test run + milestone status writes
  // + final artifacts + restore-baseline + write test status + publish tested head + save phase
  // progress; the four deciders (applicability/budget/aggregate/retry) are twins — 0 leaves
  'test-pilot': 36,
  // mark PR ready + save phase progress
  'mark-ready': 2,
  // read PR (checkpoint_entry --read-pr) + resolve review target + renew fence + check
  // ship-readiness (the folded green path) + post readout (hand-back) + lease release
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
    if (args[0] === 'load-summary') return JSON.stringify({ ok: true, records: [], contentHash: sha256('') })
    if (args[0] === 'compose-persist') return JSON.stringify({ ok: true, contentHash: 'ch-round' })
    if (args[0] === 'update-round') return JSON.stringify({ ok: true, contentHash: 'ch-postfix' })
  }
  if (script.endsWith('review_telemetry.py')) return JSON.stringify({ ok: true, benchmarkValid: true })
  if (script.endsWith('fenced_json.py')) {
    const p = args[args.indexOf('--path') + 1]
    const staged = args[args.indexOf('--payload-path') + 1]
    files[p] = files[staged] != null ? files[staged] : '{}'
    return JSON.stringify({ ok: true, contentHash: sha256(files[p]) })
  }
  if (script.endsWith('coverage_decisions.py')) return JSON.stringify({ ok: true })
  return '{}'
}

// Answer one shell command the leaf-bash io (or an exec/courier pipe) would run.
function shellResponse(cmd) {
  // withTargetCommandPrompts prefixes review-code commands with `cd '<worktree>' && ` — strip it
  // so the path/command routing below still matches.
  cmd = cmd.replace(/^cd '[^']*' && /, '')
  const w = cmd.match(/cat > '([^']+)' <<'__SR_EOF__'\n([\s\S]*)\n__SR_EOF__$/)
  if (w) { files[w[1]] = w[2]; return '' }
  if (cmd.startsWith('mkdir -p')) return ''
  const r = cmd.match(/^cat '([^']+)'/)
  if (r) return files[r[1]] != null ? files[r[1]] : ''
  if (cmd.includes("'python3'")) {
    const out = runHelperResponse(cmd)
    if (out != null) return out + '\n__SR_EXIT:0'
    return '{}\n__SR_EXIT:0'
  }
  // single-command exec/courier pipes, routed by content:
  if (cmd.includes('recover_entry.py')) {
    // world_derive from step 0, carrying the acquired lease generation (the ship fences renew it)
    return JSON.stringify({ checkpoint: null, world: {}, generation: 5 })
  }
  if (cmd.includes('front_half_usable.py')) {
    const doc = (cmd.match(/--doc '?(plan|tasks)/) || [])[1] || 'plan'
    usableCalls[doc] = (usableCalls[doc] || 0) + 1
    return JSON.stringify({ usable: usableCalls[doc] > 1, recorded: 'x', expected: 'x', missing_sections: [], placeholder: false })
  }
  if (cmd.includes('definition_doc.py read-gate')) {
    // showrunner.readGate passes --json (front-half skip check: pending -> run the panel);
    // build_phase's entry gate check reads the PLAIN gate word and needs 'passed' to build.
    return cmd.includes('--json') ? JSON.stringify({ review: 'pending' }) : 'passed'
  }
  if (cmd.includes('engine_pref_load.py')) throw new Error('engine_pref_load.py dispatched as its own leaf (#118 startup fold)')
  if (cmd.includes('journal_entry.py')) throw new Error('journal_entry.py rode its own leaf (#118 every-phase tail)')
  if (cmd.includes('checkpoint_entry.py') && !cmd.includes('--read-pr')) {
    throw new Error('checkpoint_entry.py write rode its own leaf (#118 every-phase tail)')
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
  'read startup state': () => JSON.stringify({ ok: true, spec_gate: 'passed', model_overrides: {}, doc_dir: '', engine_prefs: {} }),
  'save phase progress': () => JSON.stringify({ ok: true, journal_confirmed: true, checkpoint_confirmed: true }),
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

const GENUINE_RESPONSES = [
  [/^author-(plan|tasks)$/, () => ({ status: 'ok', notify: [] })],
  [/^(architecture|code|security|test|premortem)-reviewer(:r\d+)?$/, () => ({ findings: [], confidence: 'high' })],
  [/^synthesis:r\d+$/, () => ({ verdicts: [] })],
  [/^implement-task$/, () => ({ ok: true, signal: 'ok', evidence: { testPassed: true, testFailed: false } })],
  [/^task-reviewer:r\d+$/, () => ({ verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] })],
  [/^branch-reviewer:r\d+$/, () => ({ findings: [] })],
  [/^plan-tests$/, () => ({ records: [{ branch: 'superheroes/wi-x', steps: [{ id: 's1', instruction: 'i', expected: 'e', scenarioIds: [] }] }], coverageRationale: 'r' })],
  [/^browser-pass$/, () => ({ source: 'browser', baseUrl: 'http://x', steps: [{ id: 's1', status: 'passed', browserExecuted: true }] })],
  [/^revise-doc$|^fix-/, () => ({ fixes: [], deferred: [], changedSubjects: [], coverageDecisions: [] })],
]

const calls = []
async function cannedAgent(prompt, opts) {
  const label = (opts && opts.label) || ''
  calls.push({ label, model: opts && opts.model, phase: (opts && opts.phase) || '(none)', prompt: String(prompt) })
  for (const [re, fn] of GENUINE_RESPONSES) {
    if (re.test(label)) return fn()
  }
  if (label === 'run verify') return { command: 'none', returncode: 0, timedOut: false }
  if (COURIER_JSON[label]) return COURIER_JSON[label]()
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

  // (1) MODEL PIN: every non-genuine leaf resolves to the cheapest (mechanical) tier; no genuine
  // agent is ever pinned there.
  const unpinned = calls.filter((c) => !isGenuine(c.label) && c.model !== CHEAPEST)
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
