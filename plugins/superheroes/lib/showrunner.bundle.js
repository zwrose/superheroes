export const meta = {
  name: 'superheroes-showrunner',
  description: 'Run the superheroes showrunner end-to-end for one approved work-item (full-run, native front-half).',
}
// The Workflow runtime provides agent()/parallel()/log() in scope; bind them onto globalThis so the
// inlined spine (which reads globals) sees them. agent is WRAPPED so EVERY leaf gets, centrally:
//  (1) model pinning — dumb pipes (exec/io) are UNCONDITIONALLY pinned to the cheapest model
//      (DEFAULT_TIERS.mechanical) regardless of __SR_LEAF_MODEL or any session default; genuine-LLM
//      (smart) leaves get __SR_LEAF_MODEL when set (throwaway/test runs) or the session default.
//  (2) the current phase as its progress group — globalThis.__SR_PHASE, set by runPhases — so the
//      Workflow UI shows named phases instead of a flat undifferentiated list.
// Display label: turn a generic 'lib'/'io' leaf into the lib script (+ subcommand) or io op it runs,
// derived from the prompt (which carries the command). Done HERE (bundle-only) — not in the spine's
// cmdRunner — so the node smokes, which route canned responses by the logical 'lib' label, are unaffected.
function __leafLabel(p, fallback) {
  var m = p.match(/([\w-]+\.py)(?:\s+([a-z][\w-]*))?/)
  if (m) return m[2] ? m[1] + ' ' + m[2] : m[1]
  if (p.indexOf('cat > ') >= 0) return 'io:write'
  if (p.indexOf('mkdir -p') >= 0) return 'io:mkdir'
  if (p.indexOf('cat ') >= 0) return 'io:read'
  return fallback || 'lib'
}
// __cheapest: resolves the mechanical (cheapest) model tier once via the bundled model_tier module and
// caches it. Called lazily inside the wrapper (at agent-call time, after the module registry is set up).
var __cheapestCache = null
function __cheapest() {
  if (__cheapestCache === null) __cheapestCache = __require('model_tier').DEFAULT_TIERS.mechanical
  return __cheapestCache
}
const __realAgent = agent
globalThis.agent = function (prompt, opts) {
  var o = Object.assign({}, opts || {})
  // Dumb-pipe detection: check the INCOMING label (before __leafLabel may relabel it) to identify
  // the mechanical tier. exec and io leaves are pure side-effect executors — they ALWAYS run at the
  // cheapest model unconditionally, independent of __SR_LEAF_MODEL or any session default.
  // Genuine-LLM (smart) leaves get __SR_LEAF_MODEL when set (throwaway/test run override).
  var __isDumb = (o.label === 'exec' || o.label === 'io')
  if (__isDumb) {
    o.model = __cheapest()
  } else if (globalThis.__SR_LEAF_MODEL) {
    o.model = globalThis.__SR_LEAF_MODEL
  }
  if (!o.phase && globalThis.__SR_PHASE) o.phase = globalThis.__SR_PHASE
  if (!o.label || o.label === 'lib' || o.label === 'io') o.label = __leafLabel(String(prompt), o.label)
  return __realAgent(prompt, o)
}
globalThis.parallel = parallel
globalThis.log = (typeof log === 'function') ? log : (() => {})
// Leaf-bash io: every filesystem touch runs in a command-runner leaf, so the script body needs no fs.
// __sh dispatches through globalThis.agent (the wrapper) so io leaves also get the model/phase enrichment.
function __q(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }
function __sc(cmd) {
  var root = (typeof globalThis !== 'undefined' && globalThis.__SR_ROOT) ? String(globalThis.__SR_ROOT) : null
  if (!root) return cmd
  var t = String(cmd).replace(/^\s+/, '')
  if (t.startsWith('cd ')) return cmd
  return 'cd ' + __q(root) + ' && ' + cmd
}
async function __sh(cmd) { return globalThis.agent('Run exactly this command and return ONLY its stdout, unchanged:\n\n' + __sc(cmd), { label: 'io' }) }
function __join() { return Array.prototype.slice.call(arguments).join('/').replace(/\/+/g, '/') }
globalThis.io = {
  join: __join, tmpdir() { return '/tmp' },
  async mkdirp(d) { await __sh('mkdir -p ' + __q(d)) },
  async writeFile(p, s) { const b = (typeof s === 'string') ? s : JSON.stringify(s); await __sh('cat > ' + __q(p) + " <<'__SR_EOF__'\n" + b + '\n__SR_EOF__') },
  async readText(p) { return __sh('cat ' + __q(p) + ' 2>/dev/null || true') },
  async readJson(p, dflt) { const t = await __sh('cat ' + __q(p) + ' 2>/dev/null || true'); try { return JSON.parse(t) } catch (_) { return dflt } },
}
// Full-run mode (read by showrunner() in Task 8): inject native authoring WITHOUT frontHalfBoundary.
globalThis.SUPERHEROES_BUNDLE_FULL_RUN = true

const __modules = {}
const __cache = {}
function __require(id) {
  const key = String(id).replace('./', '').replace(/\.js$/, '')   // MUST match the bundler's norm()
  // io_seam is supplied by the preamble (leaf-bash) — never the fs-backed disk module.
  if (key === 'io_seam') return { io: function () { return globalThis.io }, joinPath: __join }
  if (__cache[key]) return __cache[key].exports
  if (!__modules[key]) throw new Error('bundle: unknown module ' + id)
  const m = { exports: {} }
  __cache[key] = m
  __modules[key](m, m.exports, __require)
  return m.exports
}
globalThis.__sr_require = __require   // exposed so the compose smoke can resolve the registry

// ===== circuit_breaker.js =====
__modules["circuit_breaker"] = function (module, exports, require) {
// plugins/superheroes/lib/circuit_breaker.js
const BLOCKING = new Set(['Critical', 'Important'])
// Python re.ASCII: \w == [A-Za-z0-9_], \s == [ \t\n\r\f\v]. Match those explicitly so JS \w/\s
// (which differ on unicode) cannot drift.
const _NON_WORD = /[^A-Za-z0-9_ \t\n\r\f\v]/g
const _WS = /[ \t\n\r\f\v]+/g
function normalizeTitle(title) {
  let t = String(title).toLowerCase()
  t = t.replace(_NON_WORD, '')
  t = t.replace(_WS, ' ')
  return t.trim()
}
function findingIdentity(finding) {
  return `${(finding && finding.file) || ''}::${normalizeTitle((finding && finding.title) || '')}`
}
function _blocking(round) { return round.findings.filter((f) => BLOCKING.has(f.severity)) }
function checkCircuitBreaker(rounds, maxRounds) {
  const n = rounds.length
  if (n === 0) return { halt: false, reason: null, detail: 'no rounds yet' }
  const latest = _blocking(rounds[n - 1])
  if (n >= maxRounds && latest.length > 0) {
    return { halt: true, reason: 'max-iterations',
      detail: `Reached ${maxRounds} rounds; the latest review still showed ${latest.length} blocking finding(s) (the final round's fixes are committed but not yet re-reviewed).` }
  }
  if (n >= 2) {
    const prevIds = new Set(_blocking(rounds[n - 2]).map(findingIdentity))
    const recurring = latest.filter((f) => prevIds.has(findingIdentity(f)))
    if (recurring.length) {
      const ids = recurring.map(findingIdentity).join('; ')
      return { halt: true, reason: 'recurring-finding',
        detail: `${recurring.length} blocking finding(s) recurred after a fix was committed: ${ids}` }
    }
  }
  if (n >= 3) {
    const cN = _blocking(rounds[n - 1]).length
    const cN1 = _blocking(rounds[n - 2]).length
    const cN2 = _blocking(rounds[n - 3]).length
    if (cN > 0 && cN >= cN1 && cN1 >= cN2) {
      return { halt: true, reason: 'no-net-progress',
        detail: `Blocking-finding count did not decrease over two rounds (${cN2} → ${cN1} → ${cN}).` }
    }
  }
  return { halt: false, reason: null, detail: 'progressing' }
}
module.exports = { normalizeTitle, findingIdentity, checkCircuitBreaker, BLOCKING }

};

// ===== loop_state.js =====
__modules["loop_state"] = function (module, exports, require) {
// plugins/superheroes/lib/loop_state.js
function decide(blockingFixed, skippedBlocking, rnd, maxRounds, breakerHalt) {
  if (breakerHalt) {
    return ['halt', true, 'circuit breaker halted (stuck / recurrence) — stop and report the still-open findings and the commit range; do not loop further.']
  }
  if (blockingFixed > 0) {
    if (rnd >= maxRounds) {
      return ['halt', true, `round cap (${maxRounds}) reached with blocking fixes still landing — REPORT the open findings; do NOT declare success.`]
    }
    return ['review', true, `MANDATORY: ${blockingFixed} blocking (Critical/Important) finding(s) were addressed this round — re-review from scratch to verify they resolved and introduced nothing new. You may NOT exit, declare success, or offer the next round as 'optional'. The loop exists to verify fixes; your confidence that 'it is clean' is exactly what this gate overrides.`]
  }
  if (skippedBlocking > 0) {
    return ['exit_skipped', false, `no blocking finding addressed; ${skippedBlocking} blocking finding(s) were deliberately skipped — exit CLEAN-EXCEPT-FOR-SKIPPED: list the skipped blocker(s); do not report a plain success.`]
  }
  return ['exit_clean', false, 'no blocking findings to address and none skipped — the loop is genuinely done; exit SUCCESS.']
}
module.exports = { decide }

};

// ===== loop_synthesis.js =====
__modules["loop_synthesis"] = function (module, exports, require) {
// plugins/superheroes/lib/loop_synthesis.js
const { findingIdentity } = require('./circuit_breaker.js')
const _TIERS = new Set(['Critical', 'Important', 'Minor', 'Nit'])
const _BLOCKING = new Set(['Critical', 'Important'])
function consume(merged, leafVerdicts) {
  const byId = Object.create(null)   // null-proto: byId[identity] tests own keys only (Python dict parity)
  if (Array.isArray(leafVerdicts)) {
    for (const v of leafVerdicts) {
      if (v && typeof v === 'object' && typeof v.id === 'string') byId[v.id] = v
    }
  }
  const survivors = []; const drops = []
  for (const f of merged) {
    const id = findingIdentity(f)
    const v = byId[id]
    const action = (v && typeof v === 'object') ? v.action : null
    const reason = (v && typeof v === 'object') ? v.reason : null
    if (action === 'drop' && typeof reason === 'string' && reason.trim()) {
      drops.push({ id, file: f.file === undefined ? null : f.file, title: f.title === undefined ? null : f.title,
        reason: reason.trim(), was_blocking_tagged: _BLOCKING.has(f.severity) })
      continue
    }
    const kept = Object.assign({}, f)
    const sev = (v && typeof v === 'object') ? v.severity : null
    if (_TIERS.has(sev)) kept.severity = sev
    survivors.push(kept)
  }
  return { findings: survivors, drops }
}
module.exports = { consume }

};

// ===== panel_tally.js =====
__modules["panel_tally"] = function (module, exports, require) {
// plugins/superheroes/lib/panel_tally.js
const { findingIdentity } = require('./circuit_breaker.js')
const loopState = require('./loop_state.js')
const BLOCKING = new Set(['Critical', 'Important'])
const SEV_RANK = { Critical: 0, Important: 1, Minor: 2, Nit: 3 }
const _ACTION_TO_TERMINAL = { review: 'continue', exit_clean: 'clean', exit_skipped: 'clean-with-skips', halt: 'halted' }

function _mergeDims(a, b) {
  const parts = []
  for (const src of [a.dimension, b.dimension]) {
    if (!src) continue
    for (let p of String(src).split('+')) { p = p.trim(); if (p && !parts.includes(p)) parts.push(p) }
  }
  return parts.join(' + ')
}
function compileFindings(findings, contextFiles) {
  const byId = Object.create(null)   // null-proto: `fid in byId` tests own keys only (Python dict parity)
  for (const f of findings) {
    if (f.file === null || f.file === undefined || f.line === null || f.line === undefined) continue
    if (contextFiles != null && !contextFiles.includes(f.file)) continue
    const fid = findingIdentity(f)
    if (fid in byId) {
      const ex = byId[fid]
      const dims = _mergeDims(ex, f)
      const merged = ((SEV_RANK[f.severity] != null ? SEV_RANK[f.severity] : 99) <
                      (SEV_RANK[ex.severity] != null ? SEV_RANK[ex.severity] : 99)) ? Object.assign({}, f) : Object.assign({}, ex)
      merged.dimension = dims
      byId[fid] = merged
    } else byId[fid] = Object.assign({}, f)
  }
  const out = Object.values(byId)
  for (const f of out) f.classification = f.tradeoff ? 'judgment' : 'mechanical'
  return out
}
function roundGate(compiled, expectedRoster, completedRoster) {
  const incomplete = expectedRoster.filter((r) => !completedRoster.includes(r))
  const hasBlocker = compiled.some((f) => BLOCKING.has(f.severity))
  let gate
  if (incomplete.length) gate = 'cannot-certify'
  else if (hasBlocker) gate = 'blocking'
  else gate = 'clean'
  const allVerifiable = compiled.every((f) => !!f.evidence)
  const confidence = (!incomplete.length && allVerifiable) ? 'high' : 'low'
  return { gate, confidence, incomplete }
}
function presentDeferred(compiled, deferredSet) {
  let n = 0
  for (const f of compiled) {
    if (!BLOCKING.has(f.severity)) continue
    const deferredSev = deferredSet[findingIdentity(f)]
    if (deferredSev === undefined || deferredSev === null) continue
    if ((SEV_RANK[f.severity] != null ? SEV_RANK[f.severity] : 99) >= (SEV_RANK[deferredSev] != null ? SEV_RANK[deferredSev] : 99)) n += 1
  }
  return n
}
function decideTerminal(gate, presentBlocking, presentDeferredCount, fixStatus, rnd, maxRounds, breakerHalt) {
  if (gate === 'cannot-certify') return { terminal: 'cannot-certify', reason: 'a reviewer did not complete after its retry — coverage not certified' }
  if (fixStatus === 'failed') return { terminal: 'halted', reason: 'the fix step did not complete (failed or timed out)' }
  const blockingFixed = Math.max(0, presentBlocking - presentDeferredCount)
  const [action, , reason] = loopState.decide(blockingFixed, presentDeferredCount, rnd, maxRounds, !!breakerHalt)
  return { terminal: _ACTION_TO_TERMINAL[action], reason }
}
module.exports = { compileFindings, roundGate, presentDeferred, decideTerminal, BLOCKING, SEV_RANK, _ACTION_TO_TERMINAL }

};

// ===== ci_status.js =====
__modules["ci_status"] = function (module, exports, require) {
// plugins/superheroes/lib/ci_status.js
const _PASS = new Set(['pass', 'success', 'skipping', 'skipped', 'neutral'])
function _bucket(item) {
  if (!item || typeof item !== 'object') return 'unknown'
  return String(item.bucket || item.state || item.conclusion || 'unknown').toLowerCase()
}
function classify(checks) {
  if (!Array.isArray(checks) || checks.length === 0) return { status: 'none', failing: [] }
  const failing = []
  let sawGating = false
  for (const item of checks) {
    const b = _bucket(item)
    const name = (item && typeof item === 'object') ? item.name : null
    if (b === 'skipping' || b === 'skipped' || b === 'neutral') continue
    sawGating = true
    if (!_PASS.has(b)) failing.push(name || 'unknown')
  }
  if (failing.length) return { status: 'red', failing }
  if (!sawGating) return { status: 'none', failing: [] }
  return { status: 'green', failing: [] }
}
module.exports = { classify }

};

// ===== verify_gate.js =====
__modules["verify_gate"] = function (module, exports, require) {
// plugins/superheroes/lib/verify_gate.js
// JS twin of verify_gate.py's returncode->result classification (the subprocess RUN stays an
// executor; this is the pure mapping it feeds). 'none'/'' command -> skipped; timeout -> timeout;
// returncode 0 -> pass; else fail. Fail-closed: anything not unambiguously a pass is fail.
function classify(runResult) {
  const r = runResult || {}
  const cmd = r.command
  if (!cmd || String(cmd).trim().toLowerCase() === 'none') return 'skipped'
  if (r.timedOut) return 'timeout'
  return r.returncode === 0 ? 'pass' : 'fail'
}
module.exports = { classify }

};

// ===== review_panel_shell.js =====
__modules["review_panel_shell"] = function (module, exports, require) {
// review_panel_shell.js — the reusable review-panel + loop-to-clean orchestration shell (#86, #115).
//
// CONTROL FLOW ONLY. Every judgement (compile, gate, confidence, the four loop terminals, the
// fix-failure -> halted decision, the circuit breaker) lives in the parity-locked pure-decider
// twins (panel_tally / loop_synthesis / circuit_breaker / loop_state); this shell detects events and
// forwards them IN MEMORY. The shell makes exactly one branch: `if (terminal !== 'continue')`.
//
// #115 re-architecture: reviewer leaves now RETURN a `findings[]` array (the panel holds them in
// memory) instead of writing findings-<name>.json. merge/synthesis-consume/tally are in-process twin
// calls over those in-memory arrays — no panel_tally.py / merge_findings.py / loop_synthesis.py
// dispatch and no per-finding disk file. The ONLY durable state is the per-round accumulator (the
// per-round verdict carrying the skip-excluded blocking finding IDENTITIES) + the deferred-set, each
// kept on disk via one cheap write so a crash-resume rebuilds the breaker history + deferred
// accounting. The synthesis leaf stays a genuine LLM agent (it returns verdicts).
//
// Runtime contract (native Workflow): `agent()` runs a leaf worker (no Agent tool, §10.1);
// `parallel()` fans out. The reviewers + synthesis leaf + fixStep are caller-supplied leaf agents.
// `runDir` names the on-disk scratch dir the accumulator + deferred-set live under.
//
// reviewPanel({ reviewerSet, context, rubric, runKey, runDir, fixStep, maxRounds, legKind, verifyCommand })
// legKind = { panel: bool, code: bool }. The shell is itself in SAFETY_MACHINERY (FR-24).
const { io } = require('./io_seam.js')
const panelTally = require('./panel_tally.js')
const loopSynthesis = require('./loop_synthesis.js')
const circuitBreaker = require('./circuit_breaker.js')
const loopState = require('./loop_state.js')
// #115 Task 16: verify gate split — subprocess run stays a cheap pipe, classification is in-process
const verifyGateTwin = require('./verify_gate.js')

const SCHEMA_VERSION = 1
const BLOCKING = new Set(['Critical', 'Important'])
const _VERIFY_OK = new Set(['pass', 'skipped'])   // none/doc-leg signalled by a null verifyResult

function _usable(v) { return v && typeof v.terminal === 'string' }
function _failClosed() {
  // UFR-9 last-resort: no usable verdict from the tally -> fail closed, never a clean advance.
  return { schemaVersion: SCHEMA_VERSION, terminal: 'halted', recordMissing: true,
           reason: 'tally produced no usable verdict — failing closed' }
}

// ── durable per-round accumulator (one cheap write per round; rebuilt on resume) ──
// Each record: { round, findings:[{file,title,severity,...}] } where findings are the round's
// compiled findings with deferred (skipped) identities removed — so a crash-resume rebuilds the
// circuit-breaker history + deferred accounting from disk. Stored as a single JSON array.
function accumulatorPath(runDir) { return `${runDir}/round-records.json` }
function deferredSetPath(runDir) { return `${runDir}/deferred-set.json` }

async function loadAccumulator(runDir) {
  const recs = await io().readJson(accumulatorPath(runDir), [])
  return Array.isArray(recs) ? recs : []
}
async function loadDeferredSet(runDir) {
  const set = await io().readJson(deferredSetPath(runDir), {})
  return (set && typeof set === 'object' && !Array.isArray(set)) ? set : {}
}

// resumeRound: the round to (re)start at = max recorded round + 1, or 1 (panel_tally.resume_round
// parity — a round is fully saved iff its accumulator record exists).
function resumeRound(records) {
  let best = 0
  for (const r of records) {
    const n = r && Number(r.round)
    if (Number.isFinite(n) && n > best) best = n
  }
  return best + 1
}

// assembleRounds: circuit_breaker's [{round, findings}] from the durable accumulator, skip-excluded
// (panel_tally.assemble_rounds parity — but reads the in-memory accumulator, not per-round files).
function assembleRounds(records, deferredSet) {
  const skip = new Set(Object.keys(deferredSet || {}))
  const out = []
  for (const rec of records) {
    if (!rec || typeof rec !== 'object') continue
    const findings = (rec.findings || []).filter((f) => !skip.has(circuitBreaker.findingIdentity(f)))
    out.push({ round: Number(rec.round), findings })
  }
  out.sort((a, b) => a.round - b.round)
  return out
}

async function reviewPanel({ reviewerSet, context, rubric, runKey, runDir, fixStep,
                            maxRounds = 7, legKind = {}, verifyCommand = 'none' }) {
  runDir = runDir || runKey
  let records = await loadAccumulator(runDir)        // durable accumulator (breaker history + deferral)
  let round = resumeRound(records)                   // UFR-7: resume at the round boundary from disk
  let lastExtras = await io().readJson(`${runDir}/last-extras.json`, null)
  // UFR-7: a mid-loop resume must re-load the latest fix extras (in-memory only otherwise), else the
  // resumed round's tally drops parentOrigin from the terminal record/readout.
  if (!reviewerSet || reviewerSet.length === 0) {
    const v = await tallyRound({ runDir, round, roster: reviewerSet || [], maxRounds,
                                 roundFindings: {}, records, legKind, verifyResult: null, extras: lastExtras })
    await persistRound(runDir, records, v)
    return _usable(v) ? v : _failClosed()
  }
  while (true) {
    // 1. Fan out the panel — each reviewer RETURNS its findings[] (held in memory, no disk file).
    const roundFindings = {}
    await parallel(reviewerSet.map((r) => () => dispatchReviewer(r, context, rubric, runDir, round, roundFindings)))
    // 2. Panel-only synthesis (FR-11): mechanical merge (compileFindings twin) -> Opus leaf -> the
    // deterministic loop_synthesis.consume twin. A throw / null synthesis degrades to the raw compile
    // (keep-on-uncertain — no finding dropped), logged for detectability.
    let synthesized = null
    if (legKind.panel) {
      try {
        synthesized = await synthesizeRound(roundFindings, context, rubric, runDir, round)
      } catch (e) {
        try { log(`review-panel r${round}: synthesis threw (${e && e.message ? e.message : e}) — falling back to raw compile`) } catch (_) {}
        synthesized = null
      }
      if (!synthesized) {
        try { log(`review-panel r${round}: synthesis produced no result — falling back to raw compile (no findings dropped)`) } catch (_) {}
      }
    }
    // 3. Code-leg verify gate (FR-17): run the project verify command, classify pass/fail/timeout.
    let verifyResult = null
    if (legKind.code) {
      try { verifyResult = await verifyAgent(verifyCommand, runDir, round) }
      catch (e) { verifyResult = 'fail' }  // fail-closed: a verify that can't run blocks clean
    }
    // 4. In-process tally — the twins decide gate/terminal (+ internal circuit breaker). A prior
    // round's fix extras (parentOrigin/escalation) ride forward into the record/readout.
    const verdict = await tallyRound({ runDir, round, roster: reviewerSet, maxRounds,
                                       roundFindings, records, legKind, synthesized, verifyResult, extras: lastExtras })
    if (!_usable(verdict)) return _failClosed()
    await persistRound(runDir, records, verdict)     // one cheap write: append this round's record
    // 5. The shell's only branch: stop unless the core says continue.
    if (verdict.terminal !== 'continue') return verdict
    // 6. Fix step (caller's). Detect failure/timeout; the CORE decides halted next round.
    const fix = await runFixStep(fixStep, verdict, runDir)
    if (!fix.ok) {
      const failVerdict = await tallyRound({ runDir, round, roster: reviewerSet, maxRounds,
                                            roundFindings, records, legKind, synthesized, verifyResult,
                                            fixStatus: 'failed', extras: fix.extras || lastExtras })
      await persistRound(runDir, records, failVerdict)
      return _usable(failVerdict) ? failVerdict : _failClosed()
    }
    lastExtras = fix.extras || lastExtras   // latest fix's extras win; persisted once a blocker is parent-traced
    // persist to a stable per-run path so a mid-loop resume can re-load it (the reload above).
    if (lastExtras) { try { await io().writeFile(`${runDir}/last-extras.json`, JSON.stringify(lastExtras)) } catch (_) {} }
    round += 1
  }
}

// One cheap durable write per round: append/replace this round's accumulator record (carrying the
// compiled findings with their blocking identities) so a crash-resume rebuilds the breaker history.
// Mutates `records` in place so the live loop's breaker history stays current without a re-read.
async function persistRound(runDir, records, verdict) {
  const rnd = Number(verdict && verdict.round)
  if (!Number.isFinite(rnd)) return
  const rec = { round: rnd, findings: (verdict.findings || []).map(
    (f) => ({ file: f.file, title: f.title, severity: f.severity })) }
  const idx = records.findIndex((r) => Number(r.round) === rnd)
  if (idx >= 0) records[idx] = rec; else records.push(rec)
  try { await io().writeFile(accumulatorPath(runDir), JSON.stringify(records)) } catch (_) {}
}

// Dispatch one reviewer leaf agent; UFR-1: one re-dispatch if it does not finish (a non-array return
// is what the tally reads as "did not complete"). On completion the RETURNED findings[] is held in
// roundFindings[reviewer]; absence of the key means the reviewer did not complete (coverage gap).
async function dispatchReviewer(reviewer, context, rubric, runDir, round, roundFindings) {
  let out = await reviewerAgent(reviewer, context, rubric, runDir, round)
  if (!Array.isArray(out)) out = await reviewerAgent(reviewer, context, rubric, runDir, round) // single re-dispatch
  if (Array.isArray(out)) roundFindings[reviewer] = out
}

// Panel synthesis: mechanical merge (panel_tally.compileFindings twin), then the genuine Opus leaf
// (returns per-finding keep/drop verdicts), then the deterministic loop_synthesis.consume twin.
async function synthesizeRound(roundFindings, context, rubric, runDir, round) {
  const all = []
  for (const arr of Object.values(roundFindings)) if (Array.isArray(arr)) all.push(...arr)
  const merged = panelTally.compileFindings(all, null)            // in-memory mechanical merge
  const leafVerdicts = await synthesisLeaf(merged, context, rubric, runDir, round) // genuine agent
  return loopSynthesis.consume(merged, Array.isArray(leafVerdicts) ? leafVerdicts : []) // {findings, drops}
}

// Code-leg verify gate split (#115 Task 16): agent runs the subprocess (--emit-run, IO-only);
// verifyGateTwin.classify maps the raw run data to pass/fail/timeout/skipped in-process.
// Fail-closed: if the agent gives nothing or the result is unparseable -> 'fail'.
async function verifyAgent(verifyCommand, runDir, round) {
  const out = await agent(
    `Run exactly this and return ONLY its stdout JSON, unchanged:\n\n` +
    `python3 plugins/superheroes/lib/verify_gate.py --command ${shq(verifyCommand || 'none')} --emit-run`,
    { label: `verify:r${round}`, schema: VERIFY_SCHEMA })
  if (!out) return 'fail'  // fail-closed if the runner gave nothing
  // Classify with the command the SPINE knows (verifyCommand), NOT the leaf's echoed out.command.
  // A garbled leaf that drops `command` would make the twin see !cmd -> 'skipped' (a pass-equivalent
  // in _VERIFY_OK) — certifying clean without verify passing. Using verifyCommand here means a real
  // verifyCommand can never be misclassified 'skipped' by a missing echo; a garbled returncode still
  // falls to 'fail' (fail-closed). (#115 final review FIX 2.)
  return verifyGateTwin.classify({ command: verifyCommand || 'none', returncode: out.returncode, timedOut: out.timedOut })
}

// In-process tally — the parity-locked twins decide gate/confidence/terminal + the circuit breaker,
// over the in-memory roundFindings + the durable accumulator. NO panel_tally.py dispatch. Mirrors
// panel_tally.tally's precedence exactly; fails closed to `halted` on any unforeseen error (UFR-9).
async function tallyRound({ runDir, round, roster, maxRounds, roundFindings = {}, records = [],
                           legKind = {}, synthesized = null, verifyResult = null,
                           fixStatus = 'completed', extras = null }) {
  // Only readout-enrichment keys ride in from the caller — never decision/terminal fields, so a
  // caller's extras can't overwrite a fail-closed `halted` or any gate field (panel_tally parity).
  const safeExtras = {}
  if (extras && typeof extras === 'object') {
    for (const k of ['fixes', 'deferred', 'parentOrigin']) if (k in extras) safeExtras[k] = extras[k]
  }
  try {
    if (!roster || roster.length === 0) {
      return Object.assign({ schemaVersion: SCHEMA_VERSION, gate: 'cannot-certify', confidence: 'low',
        findings: [], missing: [], drops: [], terminal: 'cannot-certify', round,
        reason: 'empty reviewer set — nothing to certify' }, safeExtras)
    }
    const completed = roster.filter((r) => Array.isArray(roundFindings[r]))
    let compiled, drops
    if (synthesized && typeof synthesized === 'object') {       // panel leg: judgment already done
      compiled = synthesized.findings || []
      drops = synthesized.drops || []
    } else {                                                    // single-reviewer leg: compile raw
      const all = []
      for (const r of completed) all.push(...roundFindings[r])
      compiled = panelTally.compileFindings(all, null)
      drops = []
    }
    const gateOut = panelTally.roundGate(compiled, roster, completed)
    const gate = gateOut.gate, confidence = gateOut.confidence, missing = gateOut.incomplete
    const deferredSet = await loadDeferredSet(runDir)
    const presentBlocking = compiled.filter((f) => BLOCKING.has(f.severity)).length
    const pdef = panelTally.presentDeferred(compiled, deferredSet)
    // Internal circuit breaker (UFR-2): prior rounds from the durable accumulator + this round's
    // findings, skip-set excluded. Exclude THIS round from the disk-read history (it may already be
    // recorded from a prior idempotent call) and append the current findings exactly once.
    const skip = new Set(Object.keys(deferredSet))
    const prior = assembleRounds(records, deferredSet).filter((r) => r.round !== round)
    const thisRound = { round, findings: compiled.filter((f) => !skip.has(circuitBreaker.findingIdentity(f))) }
    const brk = circuitBreaker.checkCircuitBreaker(prior.concat([thisRound]), maxRounds)
    const breakerHalt = !!brk.halt
    let { terminal, reason } = panelTally.decideTerminal(
      gate, presentBlocking, pdef, fixStatus, round, maxRounds, breakerHalt)
    // The breaker's own reason (recurring-finding / no-net-progress / max-iterations) is the precise
    // recurrence detail the readout needs — surface it when the breaker is what forced the halt.
    if (terminal === 'halted' && breakerHalt && brk.detail) reason = brk.detail
    // Verify gate (FR-17/UFR-4): a code leg's clean terminal requires verify to have passed.
    if ((terminal === 'clean' || terminal === 'clean-with-skips') &&
        verifyResult !== null && !_VERIFY_OK.has(verifyResult)) {
      terminal = 'halted'
      reason = verifyResult === 'timeout'
        ? 'verify command timed out — cannot certify clean'
        : 'verify command failed — cannot certify clean'
    }
    if (terminal === 'cannot-certify' && missing.length) {
      reason = 'coverage incomplete — missing review angle(s): ' + missing.join(', ')
    }
    return Object.assign({ schemaVersion: SCHEMA_VERSION, gate, confidence, findings: compiled,
      missing, drops, terminal, reason, round }, safeExtras)
  } catch (exc) {   // absolute fail-safe — any unforeseen error halts, never clean (UFR-9)
    return Object.assign({ schemaVersion: SCHEMA_VERSION, gate: 'cannot-certify', confidence: 'low',
      findings: [], missing: [], drops: [], terminal: 'halted', round,
      reason: 'tally failed: ' + (exc && exc.message ? exc.message : exc) }, safeExtras)
  }
}

// Invoke the caller-supplied fix step on the round's blocking findings; record its per-finding
// resolved/deferred report into the deferred-set (the tally reads it next round). Returns false on
// fix-step failure/timeout (UFR-3) — the shell does NOT decide the outcome, the core does.
async function runFixStep(fixStep, verdict, runDir) {
  try {
    const blockers = (verdict.findings || []).filter((f) => f.severity === 'Critical' || f.severity === 'Important')
    const report = await fixStep(blockers, runDir) // caller's leaf agent; may return null on failure
    if (!report) return { ok: false, extras: null }
    await recordDeferred(report, verdict, runDir) // append deferred identities (+severity) to deferred-set
    return { ok: true, extras: (report && report.extras) || null }
  } catch (e) {
    try { log(`review-panel: fix step failed, treating as fix failure -> halted: ${e && e.message ? e.message : e}`) } catch (_) {}
    return { ok: false, extras: null }
  }
}

const VERDICT_SCHEMA = {
  type: 'object',
  required: ['terminal'],
  properties: {
    schemaVersion: { type: 'number' },
    gate: { enum: ['clean', 'blocking', 'cannot-certify'] },
    confidence: { enum: ['high', 'low'] },
    findings: { type: 'array' },
    drops: { type: 'array' },
    terminal: { enum: ['continue', 'clean', 'clean-with-skips', 'cannot-certify', 'halted'] },
    reason: { type: 'string' },
    recordMissing: { type: 'boolean' },
  },
}
const SYNTH_SCHEMA = { type: 'object', required: ['findings', 'drops'],
  properties: { findings: { type: 'array' }, drops: { type: 'array' } } }
// #115 Task 16: VERIFY_SCHEMA now matches the --emit-run output (raw run data, not classified result)
const VERIFY_SCHEMA = { type: 'object', required: ['command'],
  properties: { command: {}, returncode: {}, timedOut: {} } }

function shq(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }

// reviewerAgent / synthesisLeaf / recordDeferred are caller/runtime-provided leaf wrappers: a
// consumer (#88/#89/#87) supplies its real reviewer dispatch (which RETURNS a findings[] array), its
// genuine Opus synthesis leaf (RETURNS per-finding keep/drop verdicts), and its deferred-set writer
// (writes the deferred identities via its own cheap executor). The harness (Task 8) supplies stubs.
module.exports = { reviewPanel, VERDICT_SCHEMA, SYNTH_SCHEMA, VERIFY_SCHEMA }

};

// ===== test_pilot_phase.js =====
__modules["test_pilot_phase"] = function (module, exports, require) {
// plugins/superheroes/lib/test_pilot_phase.js
// Native showrunner test-pilot phase. This module stays dependency-injected so the
// showrunner spine can be smoke-tested without launching browsers or mutating refs.

// Native showrunner test-pilot phase. The orchestrator threads state through five sequential
// helpers, each of which returns `{ done: <terminalResult> }` to short-circuit (park or proceed) or
// the state it produced. Judgment stays in the injected leaves + pure helpers (§10.1); these helpers
// are control flow only.
async function testPilotPhase(workItem, generation, deps) {
  deps = deps || {}

  const setup = await resolveApplicabilityAndSetup(deps, workItem, generation)
  if (setup.done) return setup.done
  const { context } = setup

  const planned = await preparePlanAndRecords(deps, workItem, context)
  if (planned.done) return planned.done
  const { plan, records, previousStatus } = planned

  const execCtx = await prepareExecutionContext(deps, workItem, context, plan, records, previousStatus)
  if (execCtx.done) return execCtx.done
  const { artifactResult, serverContext, seedResult } = execCtx

  const browser = await runBrowserPasses(deps, workItem, context, plan, records, artifactResult, serverContext, seedResult)
  if (browser.done) return browser.done
  const { combinedAggregated, retryState } = browser

  return finalizeReadiness(deps, workItem, context, plan, records, retryState, combinedAggregated, artifactResult)
}

// Phase 1: resolve context, decide applicability (short-circuit not_applicable / park uncertain),
// validate setup. Returns `{ context }` to proceed or `{ done }` for a terminal.
async function resolveApplicabilityAndSetup(deps, workItem, generation) {
  let context
  try {
    context = await callLeaf(deps.resolveContext, workItem, generation)
  } catch (err) {
    return { done: low(`test-pilot setup failed: ${message(err)}`) }
  }
  if (!context || !context.head) {
    return { done: low('test-pilot setup failed: missing current head') }
  }

  let applicability
  try {
    applicability = await callLeaf(deps.decideApplicability, context)
  } catch (err) {
    return { done: low(`test-pilot applicability failed: ${message(err)}`) }
  }
  if (!applicability || typeof applicability !== 'object') {
    return { done: low('test-pilot applicability failed: no verdict') }
  }

  if (applicability.verdict === 'not_applicable') {
    const status = {
      schemaVersion: 1,
      verdict: 'not_applicable',
      workItem,
      branch: context.branch,
      head: context.head,
      rationale: applicability.rationale || applicability.reason || 'no browser-verifiable workflow changed',
    }
    const wrote = await writeStatus(deps, workItem, status)
    if (!wrote.ok) return { done: low(wrote.reason) }
    return { done: { confidence: 'high', assumptions: [] } }
  }

  if (applicability.verdict !== 'applicable') {
    return { done: low(applicability.reason || 'test-pilot applicability is uncertain') }
  }

  const setupProblem = validateSetup(context)
  if (setupProblem) {
    return { done: await parkLow(deps, workItem, context, setupProblem) }
  }

  return { context }
}

// Phase 2: derive the plan, prepare + validate plan records, write the plan milestones. Returns
// `{ plan, records, previousStatus }` to proceed or `{ done }` for a terminal.
async function preparePlanAndRecords(deps, workItem, context) {
  const previousStatus = await readPreviousStatus(deps, workItem)

  let plan
  try {
    plan = await callLeaf(deps.derivePlan, context)
  } catch (err) {
    return { done: low(`test-pilot plan derivation failed: ${message(err)}`) }
  }
  if (plan && plan.confidence === 'low') {
    return { done: low(plan.reason || 'test-pilot plan derivation is low-confidence') }
  }
  plan = normalizePlan(plan)
  if (!plan.records.length) {
    return { done: await parkLow(deps, workItem, context, 'applicable test-pilot plan is empty') }
  }
  const generatedStoreProblem = generatedInRepoStoreProblem(plan.records)
  if (generatedStoreProblem) {
    return { done: await parkLow(deps, workItem, context, generatedStoreProblem) }
  }
  const mergedRecords = mergePriorStepState(plan.records, previousStatus)
  const skippedProblem = validateSkippedPreservation(mergedRecords)
  if (skippedProblem) {
    return { done: low(skippedProblem) }
  }
  const dedupeProblem = validateUniqueIds(mergedRecords)
  if (dedupeProblem) {
    return { done: low(dedupeProblem) }
  }
  plan.records = mergedRecords
  let wrote = await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'plan-derived', {
    planRecords: plan.records,
  }))
  if (!wrote.ok) return { done: low(wrote.reason) }

  let prepared
  try {
    prepared = await callLeaf(deps.preparePlanRecords, plan, context, previousStatus)
  } catch (err) {
    return { done: low(`test-pilot plan record preparation failed: ${message(err)}`) }
  }
  const recordProblem = planRecordProblem(prepared)
  if (recordProblem) {
    return { done: await parkLow(deps, workItem, context, recordProblem) }
  }
  const records = mergePriorStepState(prepared.records, previousStatus)
  const preparedSkippedProblem = validateSkippedPreservation(records)
  if (preparedSkippedProblem) {
    return { done: low(preparedSkippedProblem) }
  }
  const preparedDedupeProblem = validateUniqueIds(records)
  if (preparedDedupeProblem) {
    return { done: low(preparedDedupeProblem) }
  }
  wrote = await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'plan-records-ready', {
    planRecords: records,
  }))
  if (!wrote.ok) return { done: low(wrote.reason) }

  return { plan, records, previousStatus }
}

// Phase 3: prepare artifacts, resolve the server, seed records — each with its readiness milestone.
// Returns `{ artifactResult, serverContext, seedResult }` to proceed or `{ done }` for a terminal.
async function prepareExecutionContext(deps, workItem, context, plan, records, previousStatus) {
  let artifactResult
  try {
    artifactResult = await callLeaf(deps.prepareArtifacts, {
      plan: Object.assign({}, plan, { records }),
      records,
      context,
      previousStatus,
    })
  } catch (err) {
    return { done: low(`test-pilot artifact preparation failed: ${message(err)}`) }
  }
  const artifactProblem = artifactReadinessProblem(artifactResult)
  if (artifactProblem) {
    return { done: low(artifactProblem) }
  }
  let wrote = await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'artifacts-ready', {
    planRecords: records,
    artifacts: artifactResult.artifacts,
    prPosting: artifactResult.posting || artifactResult.prPosting,
    fallback: artifactResult.fallback,
  }))
  if (!wrote.ok) return { done: low(wrote.reason) }

  let serverContext
  try {
    serverContext = await callLeaf(deps.resolveServer, context, records)
  } catch (err) {
    return { done: low(`test-pilot server resolution failed: ${message(err)}`) }
  }
  const serverProblem = serverContextProblem(serverContext, context)
  if (serverProblem) {
    return { done: low(serverProblem) }
  }
  wrote = await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'server-ready', {
    planRecords: records,
    artifacts: artifactResult.artifacts,
    server: publicServerContext(serverContext),
  }))
  if (!wrote.ok) return { done: low(wrote.reason) }

  let seedResult
  try {
    seedResult = await callLeaf(deps.seedRecords, records, context)
  } catch (err) {
    return { done: low(`test-pilot seed preparation failed: ${message(err)}`) }
  }
  const seedProblem = seedReadinessProblem(seedResult)
  if (seedProblem) {
    return { done: low(seedProblem) }
  }
  wrote = await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'seed-ready', {
    planRecords: records,
    artifacts: artifactResult.artifacts,
    server: publicServerContext(serverContext),
    seed: seedResult.status || seedResult,
  }))
  if (!wrote.ok) return { done: low(wrote.reason) }

  return { artifactResult, serverContext, seedResult }
}

// Phase 4: run browser passes, dispatch app-bug fix batches + review-code stabilization, until the
// evidence is clean (returns { combinedAggregated, retryState }) or a park condition returns { done }.
async function runBrowserPasses(deps, workItem, context, plan, records, artifactResult, serverContext, seedResult) {
  const retryState = {
    fixBatchHistory: [],
    currentHead: context.head,
    browserEvidenceHead: context.head,
    browserPasses: [],
    allRecords: records,
  }
  let aggregated
  let combinedAggregated = null
  let rerunScope = null
  let browserRecords = records
  let stabilizationCycle = 0
  while (true) {
    const budget = await budgetCheck(deps, 'browser-pass', {
      workItem,
      head: retryState.currentHead,
      rerunScope,
      fixBatchHistory: retryState.fixBatchHistory,
      counts: {
        browserPasses: retryState.browserPasses.length + 1,
        browserFixBatches: retryState.fixBatchHistory.length,
      },
    })
    if (!budget.ok) return { done: low(budget.reason) }

    let rawResults
    try {
      rawResults = await runWithServer(deps, serverContext, async (activeServer) => {
        const browserContext = browserLeafContext(
          context,
          activeServer,
          browserRecords,
          artifactResult,
          seedResult,
          rerunScope,
          retryState,
        )
        return callLeaf(deps.runBrowserPass, browserContext)
      })
    } catch (err) {
      return { done: low(`test-pilot browser execution failed: ${message(err)}`) }
    }
    const originProblem = browserOriginProblem(rawResults, serverContext)
    if (originProblem) {
      return { done: low(originProblem) }
    }

    try {
      aggregated = await callLeaf(deps.aggregateResults, rawResults, {
        context,
        records: browserRecords,
        allRecords: records,
        server: serverContext,
        rerunScope,
        fixBatchHistory: retryState.fixBatchHistory,
      })
    } catch (err) {
      return { done: low(`test-pilot result aggregation failed: ${message(err)}`) }
    }
    const aggregationProblem = resultAggregationProblem(aggregated)
    if (aggregationProblem) {
      return { done: low(aggregationProblem) }
    }

    retryState.browserEvidenceHead = retryState.currentHead
    retryState.browserPasses.push({
      head: retryState.browserEvidenceHead,
      rerunScope: rerunScope || { action: 'initial' },
      records: statusMap(aggregated),
    })
    completeLatestBatchAfter(retryState.fixBatchHistory, aggregated)
    combinedAggregated = mergeAggregatedEvidence(combinedAggregated, aggregated)

    const evidenceProblem = resultEvidenceProblem(combinedAggregated, records)
    if (!evidenceProblem) {
      const stabilization = await stabilizeReviewCode(deps, workItem, context, retryState, combinedAggregated, records)
      if (!stabilization.ok) {
        const wrote = await writeRetryStatus(deps, workItem, context, retryState, combinedAggregated, records, stabilization.reason)
        if (!wrote.ok) return { done: low(wrote.reason) }
        return { done: low(stabilization.reason) }
      }
      if (stabilization.changed) {
        stabilizationCycle += 1
        if (stabilizationCycle > 2) {
          const reason = 'review-code stabilization cycle cap reached'
          const wrote = await writeRetryStatus(deps, workItem, context, retryState, combinedAggregated, records, reason)
          if (!wrote.ok) return { done: low(wrote.reason) }
          return { done: low(reason) }
        }
        retryState.currentHead = stabilization.head || retryState.currentHead
        retryState.reviewStabilizationCycle = stabilizationCycle
        retryState.reviewCoverageHead = stabilization.reviewCoverageHead || stabilization.head
        rerunScope = { action: 'rerun_all', reason: 'review-code changed branch' }
        browserRecords = records
        combinedAggregated = null
        continue
      }
      retryState.reviewStabilizationCycle = stabilizationCycle
      retryState.reviewCoverageHead = stabilization.reviewCoverageHead || retryState.currentHead
      retryState.verifyPassedHead = stabilization.verifyPassedHead || retryState.currentHead
      return { combinedAggregated, retryState }
    }

    const failed = failedBrowserRecords(aggregated)
    if (!failed.length) {
      const retryWrite = await writeRetryStatus(deps, workItem, context, retryState, aggregated, records, evidenceProblem)
      if (!retryWrite.ok) return { done: low(retryWrite.reason) }
      return { done: low(evidenceProblem) }
    }

    const decision = await retryDecision(deps, aggregated, retryState.fixBatchHistory)
    if (decision.action !== 'fix_batch') {
      const reason = decision.reason || evidenceProblem
      const retryWrite = await writeRetryStatus(deps, workItem, context, retryState, aggregated, records, reason)
      if (!retryWrite.ok) return { done: low(retryWrite.reason) }
      return { done: low(reason) }
    }

    const failures = collectAppBugFailures(aggregated)
    if (!failures.length || failures.length !== failed.length) {
      const reason = 'one or more browser failures are not app-bug failures'
      const retryWrite = await writeRetryStatus(deps, workItem, context, retryState, aggregated, records, reason)
      if (!retryWrite.ok) return { done: low(retryWrite.reason) }
      return { done: low(reason) }
    }

    const fixBudget = await budgetCheck(deps, 'fix-batch', {
      workItem,
      failures,
      head: retryState.currentHead,
      fixBatchHistory: retryState.fixBatchHistory,
    })
    if (!fixBudget.ok) return { done: low(fixBudget.reason) }

    const summary = decision.summary || failureSummary(failures)
    const batch = {
      type: 'browser_fix_batch',
      batchNumber: retryState.fixBatchHistory.length + 1,
      intent: true,
      headBefore: retryState.browserEvidenceHead,
      failedStepIds: failures.map((failure) => failure.stepId),
      summary,
      scrubbedSummary: scrubFailureSummary(summary),
      before: statusMap(aggregated),
    }
    retryState.fixBatchHistory.push(batch)

    let fixResult
    try {
      fixResult = await dispatchFixBatch(failures, deps, {
        workItem,
        context,
        records,
        passResult: aggregated,
        fixBatchHistory: retryState.fixBatchHistory,
        batch,
      })
    } catch (err) {
      return { done: low(`test-pilot browser fix batch failed: ${message(err)}`) }
    }
    if (!fixResult || fixResult.ok === false || fixResult.action === 'park' || fixResult.confidence === 'low') {
      return { done: low((fixResult && (fixResult.reason || fixResult.message)) || 'test-pilot browser fix batch parked') }
    }

    const clean = await ensureCleanWorktreeAfterFix(fixResult, deps, { workItem, context, batch })
    if (!clean.ok) return { done: low(clean.reason) }

    const reconciled = await reconcileCommittedMutations(fixResult, retryState.fixBatchHistory, batch, deps, {
      workItem,
      context,
    })
    if (!reconciled.ok) return { done: low(reconciled.reason) }

    batch.intent = false
    batch.commitShas = normalizeShas(reconciled.commitShas || fixResult.commitShas || fixResult.commits || fixResult.shas)
    batch.changedFiles = normalizeStrings(reconciled.changedFiles || fixResult.changedFiles || fixResult.files)
    batch.headAfter = reconciled.head || fixResult.head || batch.commitShas[batch.commitShas.length - 1] || retryState.currentHead
    retryState.currentHead = batch.headAfter

    const dependencyMap = deps.dependencyMap || aggregated.dependencyMap || plan.dependencyMap || context.dependencyMap
    const rerunDecision = await retryDecision(
      deps,
      aggregated,
      retryState.fixBatchHistory,
      batch.changedFiles,
      dependencyMap,
    )
    rerunScope = normalizeRerunScope(rerunDecision)
    batch.rerunScope = rerunScope
    browserRecords = recordsForRerun(records, rerunScope)

    const wrote = await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'fix-batch-ready', {
      planRecords: records,
      artifacts: artifactResult.artifacts,
      server: publicServerContext(serverContext),
      seed: seedResult.status || seedResult,
      fixBatchHistory: retryState.fixBatchHistory,
      browserEvidenceHead: retryState.browserEvidenceHead,
      currentHead: retryState.currentHead,
      lastBrowserResult: aggregated,
    }))
    if (!wrote.ok) return { done: low(wrote.reason) }
  }
}

// Phase 5: restore the seed baseline, publish the final artifacts + tested head, write the applicable
// status. Returns the high-confidence terminal, or low() on any park.
async function finalizeReadiness(deps, workItem, context, plan, records, retryState, combinedAggregated, artifactResult) {
  const baselineResult = await restoreFinalBaseline(deps, records, context, retryState)
  if (!baselineResult.ok) return low(baselineResult.reason)

  const finalArtifacts = await ensureFinalArtifacts(deps, {
    workItem,
    context,
    records,
    aggregated: combinedAggregated,
    artifacts: artifactResult.artifacts,
    baseline: baselineResult.baseline,
    retryState,
  })
  if (!finalArtifacts.ok) return low(finalArtifacts.reason)

  const publishResult = await publishFinalHead(deps, workItem, context, retryState, {
    records,
    artifacts: finalArtifacts.artifacts,
    baseline: baselineResult.baseline,
    aggregated: combinedAggregated,
  })
  if (!publishResult.ok) return low(publishResult.reason)

  const finalStatus = {
    schemaVersion: 1,
    verdict: 'applicable',
    workItem,
    branch: context.branch,
    head: retryState.currentHead,
    browserEvidenceHead: retryState.browserEvidenceHead,
    records: mergeAllowedSkippedResults(combinedAggregated.records, records),
    fixBatchHistory: retryState.fixBatchHistory,
    browserPasses: retryState.browserPasses,
    artifacts: finalArtifacts.artifacts,
    prPosting: finalArtifacts.posting || finalArtifacts.prPosting || artifactResult.posting || artifactResult.prPosting,
    baseline: baselineResult.baseline,
    review: context.review || { head: retryState.reviewCoverageHead || retryState.currentHead },
    verify: context.verify || { result: 'pass', head: retryState.verifyPassedHead || retryState.currentHead },
    remotePr: publishResult.remotePr || publishResult.remotePR || { head: retryState.currentHead },
  }
  if (combinedAggregated.coverageRationale || plan.coverageRationale) {
    finalStatus.coverageRationale = combinedAggregated.coverageRationale || plan.coverageRationale
  }
  if (combinedAggregated.fixes) finalStatus.fixes = combinedAggregated.fixes
  if (combinedAggregated.verify) finalStatus.verify = combinedAggregated.verify
  const wrote = await writeStatus(deps, workItem, finalStatus)
  if (!wrote.ok) return low(wrote.reason)

  return { confidence: 'high', assumptions: [] }
}

function validateSetup(context) {
  if (!context.profile) {
    return 'test-pilot setup missing calibration/profile'
  }
  if (!context.browserTool) {
    return 'test-pilot setup missing browser tool'
  }
  const baseUrl = context.baseUrl || (context.profile && (context.profile.baseUrl || context.profile.base_url))
  if (!baseUrl) {
    return 'test-pilot setup missing baseUrl'
  }
  const allowed = context.allowedOrigins || context.allowed_origins || (context.profile && (context.profile.allowedOrigins || context.profile.allowed_origins))
  if (!Array.isArray(allowed) || allowed.length === 0) {
    return 'test-pilot setup missing allowedOrigins'
  }
  return null
}

async function writeStatus(deps, workItem, status) {
  try {
    if (deps.writeStatus) {
      // status already carries workItem (milestoneStatus / terminal statuses set it); the writer
      // contract is writeStatus(status) — don't pass a 2nd arg no implementation reads.
      const out = await deps.writeStatus(status)
      if (out && out.ok === false) return { ok: false, reason: out.reason || 'test-pilot status write failed' }
      return { ok: true }
    }
  } catch (err) {
    return { ok: false, reason: `test-pilot status write failed: ${message(err)}` }
  }
  return { ok: false, reason: 'test-pilot status writer unavailable' }
}

async function readPreviousStatus(deps, workItem) {
  if (typeof deps.readStatus !== 'function') return null
  try {
    const out = await deps.readStatus(workItem)
    return out && typeof out === 'object' ? out : null
  } catch (_) {
    return null
  }
}

function normalizePlan(plan) {
  const source = plan && typeof plan === 'object' ? plan : {}
  const records = source.records || source.planRecords
  return Object.assign({}, source, { records: Array.isArray(records) ? records : [] })
}

function generatedInRepoStoreProblem(records) {
  for (const record of records) {
    const store = record && (record.store || record.planStore || record.generatedStore)
    const location = store && (store.location || store.mode)
    const generated = (store && store.generated === true) || record.generated === true || record.generatedManifest === true
    if (generated && (location === 'in_repo' || location === 'in-repo')) {
      return 'generated in-repo plan store writes must park before touching worktree'
    }
  }
  return null
}

function previousRecords(status) {
  return status && Array.isArray(status.records) ? status.records : []
}

function stepKey(value) {
  if (!value || typeof value !== 'object') return null
  const raw = value.id || value.stepId || value.step_id
  return raw == null || raw === '' ? null : String(raw)
}

function mergePriorStepState(records, previousStatus) {
  const prior = new Map()
  for (const record of previousRecords(previousStatus)) {
    const key = stepKey(record)
    if (key) prior.set(key, record)
  }
  return records.map((record) => {
    if (!record || typeof record !== 'object') return record
    const seen = new Set()
    const steps = []
    for (const step of Array.isArray(record.steps) ? record.steps : []) {
      if (!step || typeof step !== 'object') continue
      const key = stepKey(step)
      if (key && seen.has(key)) continue
      if (key) seen.add(key)
      const merged = Object.assign({}, step)
      const old = key ? prior.get(key) : null
      if (old) {
        for (const field of ['checked', 'checkboxState', 'humanChecked', 'humanCheckboxState']) {
          if (old[field] !== undefined && merged[field] === undefined) merged[field] = old[field]
        }
        if (merged.priorResult === undefined) merged.priorResult = old.result || old.status
      }
      if (Array.isArray(merged.scenarioIds)) {
        merged.scenarioIds = [...new Set(merged.scenarioIds.map(String).filter(Boolean))]
      }
      steps.push(merged)
    }
    return Object.assign({}, record, { steps })
  })
}

function validateSkippedPreservation(records) {
  for (const record of records) {
    for (const step of (record && Array.isArray(record.steps) ? record.steps : [])) {
      const skipped = step.status === 'skipped' || step.result === 'skipped' || step.skipped === true
      if (!skipped) continue
      if (!stepKey(step) || !step.removalReason || !step.priorResult || !step.planContext) {
        return 'skipped step preservation missing step id, removal reason, prior result, or updated plan context'
      }
    }
  }
  return null
}

function validateUniqueIds(records) {
  const stepIds = new Set()
  const scenarioIds = new Set()
  for (const record of records) {
    if (!record || typeof record !== 'object') return 'malformed plan records'
    const steps = record.steps
    if (!Array.isArray(steps) || steps.length === 0) return 'malformed plan records: steps missing'
    for (const step of steps) {
      const key = stepKey(step)
      if (!key) return 'malformed plan records: step id missing'
      if (stepIds.has(key)) return `duplicate browser step id: ${key}`
      stepIds.add(key)
      for (const sid of Array.isArray(step.scenarioIds) ? step.scenarioIds : []) {
        const value = String(sid)
        if (scenarioIds.has(value)) continue
        scenarioIds.add(value)
      }
    }
  }
  return null
}

function planRecordProblem(prepared) {
  if (!prepared || typeof prepared !== 'object') return 'test-pilot plan record preparation returned no result'
  if (prepared.confidence === 'low') return prepared.reason || 'test-pilot plan record preparation is low-confidence'
  if (prepared.action === 'park' || prepared.ok === false) return prepared.reason || 'test-pilot plan records are invalid'
  if (!Array.isArray(prepared.records) || prepared.records.length === 0) return 'test-pilot plan records missing after preparation'
  return null
}

function artifactReadinessProblem(result) {
  if (!result || typeof result !== 'object') return 'test-pilot artifact preparation returned no result'
  if (result.confidence === 'low') return result.reason || 'test-pilot artifact preparation is low-confidence'
  if (result.action === 'park' || result.ok === false) return result.reason || 'test-pilot artifact preparation parked'
  if (!result.artifacts || !result.artifacts.plan) return 'plan artifact missing before seed/browser execution'
  return null
}

function seedReadinessProblem(result) {
  if (!result || typeof result !== 'object') return 'test-pilot seed preparation returned no result'
  if (result.confidence === 'low') return result.reason || 'test-pilot seed preparation is low-confidence'
  if (result.action === 'park' || result.ok === false) return result.reason || 'test-pilot seed preparation parked'
  if (!['ready_for_browser', 'verified', 'ready'].includes(result.action) && result.ready !== true) {
    return 'test-pilot seed state was not verified before browser execution'
  }
  return null
}

function serverContextProblem(server, context) {
  if (!server || typeof server !== 'object') return 'test-pilot server resolution returned no context'
  if (server.verdict === 'park' || server.action === 'park' || server.ok === false) return server.reason || 'test-pilot server resolution parked'
  if (!['ready_external', 'managed'].includes(server.verdict)) return 'test-pilot server resolution did not confirm external or managed server'
  if (!server.baseUrl) return 'test-pilot server resolution missing baseUrl'
  const allowed = server.allowedOrigins || server.allowed_origins || context.allowedOrigins || context.allowed_origins || (context.profile && context.profile.allowedOrigins)
  if (!Array.isArray(allowed) || !allowed.length) return 'test-pilot server resolution missing allowedOrigins'
  server.allowedOrigins = allowed
  if (server.verdict === 'managed') {
    if (!Array.isArray(server.command) || !server.command.length) return 'managed server command argv missing'
    if (server.shell !== false) return 'managed server must launch with shell=false'
  }
  return null
}

function publicServerContext(server) {
  const out = Object.assign({}, server)
  if (out.handle) out.handle = '[managed]'
  return out
}

async function runWithServer(deps, serverContext, run) {
  if (serverContext.verdict === 'managed') {
    return callLeaf(deps.withManagedServer, serverContext, run)
  }
  return run(serverContext)
}

function browserLeafContext(context, server, records, artifacts, seed, rerunScope, retryState) {
  return {
    workItem: context.workItem,
    branch: context.branch,
    head: retryState && retryState.currentHead ? retryState.currentHead : context.head,
    profile: context.profile,
    browserTool: context.browserTool,
    baseUrl: server.baseUrl,
    allowedOrigins: server.allowedOrigins,
    server,
    records,
    allRecords: retryState ? retryState.allRecords : undefined,
    artifacts,
    seed,
    rerunScope,
    fixBatchHistory: retryState ? retryState.fixBatchHistory : undefined,
  }
}

function browserOriginProblem(rawResults, server) {
  const allowed = new Set((server.allowedOrigins || []).map(originOf).filter(Boolean))
  allowed.add(originOf(server.baseUrl))
  const urls = []
  collectUrls(rawResults, urls)
  for (const url of urls) {
    const origin = originOf(url)
    if (origin && !allowed.has(origin)) {
      return `off-origin browser navigation/result cannot count: ${bounded(url)}`
    }
  }
  const resultOrigin = originOf(rawResults && rawResults.baseUrl)
  if (resultOrigin && !allowed.has(resultOrigin)) {
    return `off-origin browser navigation/result cannot count: ${bounded(rawResults.baseUrl)}`
  }
  return null
}

function collectUrls(value, urls) {
  if (!value || typeof value !== 'object') return
  if (Array.isArray(value)) {
    value.forEach((entry) => collectUrls(entry, urls))
    return
  }
  for (const key of ['url', 'currentUrl', 'current_url', 'navigationUrl', 'navigation_url', 'baseUrl']) {
    if (typeof value[key] === 'string') urls.push(value[key])
  }
  for (const key of ['steps', 'records', 'navigations']) {
    collectUrls(value[key], urls)
  }
}

function originOf(url) {
  if (typeof url !== 'string' || !url) return null
  try {
    return new URL(url).origin
  } catch (_) {
    return null
  }
}

function bounded(value) {
  const text = String(value || '')
  return text.length > 200 ? `${text.slice(0, 197)}...` : text
}

function resultAggregationProblem(aggregated) {
  if (!aggregated || typeof aggregated !== 'object') return 'test-pilot result aggregation returned no result'
  if (aggregated.confidence === 'low') return aggregated.reason || 'test-pilot result aggregation is low-confidence'
  if (aggregated.action === 'park' || aggregated.ok === false) return aggregated.reason || 'test-pilot result aggregation parked'
  if (!Array.isArray(aggregated.records) || aggregated.records.length === 0) return 'no browser-executed records were produced'
  return null
}

// Single source of truth for "this record is browser-derived evidence". MUST stay byte-for-byte
// equivalent to test_pilot_status.py `_browser_executed` (the mark-ready gate's check) — if the two
// drift, the in-phase readiness check and the mark-ready gate can disagree on the same status.
// The `browser === true` alias is the one the Python accepts that the JS previously omitted.
function browserExecutedRecord(record) {
  return !!record && typeof record === 'object' && (
    record.browserExecuted === true ||
    record.browser_executed === true ||
    record.browser === true ||
    record.kind === 'browser' ||
    record.type === 'browser'
  )
}

function resultEvidenceProblem(aggregated, records) {
  const aggregationProblem = resultAggregationProblem(aggregated)
  if (aggregationProblem) return aggregationProblem
  const expected = new Set()
  for (const record of records) {
    for (const step of record.steps || []) {
      const key = stepKey(step)
      if (key && !(step.status === 'skipped' || step.result === 'skipped')) expected.add(key)
    }
  }
  const seen = new Set()
  for (const record of aggregated.records) {
    const key = stepKey(record)
    if (!key) return 'browser-derived pass/fail evidence missing step id'
    const status = record.status || record.result
    if (status !== 'passed' && status !== 'pass') return 'skipped, incomplete, or failing browser records park before readiness'
    if (!browserExecutedRecord(record)) {
      return 'every browser step must have browser-derived pass/fail evidence'
    }
    seen.add(key)
  }
  for (const key of expected) {
    if (!seen.has(key)) return `browser-derived pass/fail evidence missing for step ${key}`
  }
  return null
}

function failedBrowserRecords(passResult) {
  const out = []
  for (const record of passRecords(passResult)) {
    const status = resultStatus(record)
    const key = stepKey(record)
    if ((status === 'failed' || status === 'fail') && key) out.push(record)
  }
  return out
}

function collectAppBugFailures(passResult) {
  return failedBrowserRecords(passResult)
    .filter(isAppBugFailure)
    .map((record) => {
      const key = stepKey(record)
      return Object.assign({}, record, {
        stepId: key,
        failureType: record.failureType || record.failure_type || record.kind || 'app_bug',
        summary: record.summary || record.notes || record.message || `browser step failed: ${key}`,
      })
    })
}

function passRecords(passResult) {
  if (!passResult || typeof passResult !== 'object') return []
  if (Array.isArray(passResult.records)) return passResult.records
  if (Array.isArray(passResult.steps)) return passResult.steps
  return []
}

function resultStatus(record) {
  return record && (record.status || record.result)
}

function isAppBugFailure(record) {
  const kind = record && (record.failureType || record.failure_type || record.kind)
  return kind === undefined || kind === null || ['app_bug', 'app-bug', 'application'].includes(kind)
}

function statusMap(passResult) {
  const out = {}
  for (const record of passRecords(passResult)) {
    const key = stepKey(record)
    if (key) out[key] = resultStatus(record)
  }
  return out
}

function mergeAggregatedEvidence(previous, current) {
  if (!previous) return Object.assign({}, current, { records: passRecords(current).map((record) => Object.assign({}, record)) })
  const byId = new Map()
  const order = []
  for (const record of passRecords(previous)) {
    const key = stepKey(record)
    if (!key) continue
    byId.set(key, Object.assign({}, record))
    order.push(key)
  }
  for (const record of passRecords(current)) {
    const key = stepKey(record)
    if (!key) continue
    if (!byId.has(key)) order.push(key)
    byId.set(key, Object.assign({}, record))
  }
  const merged = Object.assign({}, previous, current)
  merged.records = order.map((key) => byId.get(key)).filter(Boolean)
  return merged
}

function completeLatestBatchAfter(history, passResult) {
  const latest = latestFixBatch(history)
  if (latest && latest.after === undefined) latest.after = statusMap(passResult)
}

function latestFixBatch(history) {
  if (!Array.isArray(history)) return null
  for (let i = history.length - 1; i >= 0; i -= 1) {
    const entry = history[i]
    if (entry && (entry.type === 'browser_fix_batch' || entry.type === 'fix_batch')) return entry
  }
  return null
}

async function budgetCheck(deps, phase, payload) {
  if (typeof deps.budgetCheck !== 'function') return { ok: true }
  try {
    const out = await deps.budgetCheck(phase, payload)
    if (out === false) return { ok: false, reason: `test-pilot budget exhausted before ${phase}` }
    if (out && out.ok === false) return { ok: false, reason: out.reason || `test-pilot budget exhausted before ${phase}` }
    if (out && out.action === 'park') return { ok: false, reason: out.reason || `test-pilot budget exhausted before ${phase}` }
    return { ok: true }
  } catch (err) {
    return { ok: false, reason: `test-pilot budget check failed before ${phase}: ${message(err)}` }
  }
}

async function retryDecision(deps, passResult, history, changedFiles, dependencyMap) {
  try {
    if (typeof deps.retryDecide === 'function') {
      return await deps.retryDecide(passResult, history, changedFiles, dependencyMap)
    }
    return { action: 'park_retry_decision_failed', reason: 'test-pilot retry decision unavailable' }
  } catch (err) {
    return { action: 'park_retry_decision_failed', reason: `test-pilot retry decision failed: ${message(err)}` }
  }
}

function fixBatches(history) {
  return Array.isArray(history)
    ? history.filter((entry) => entry && (entry.type === 'browser_fix_batch' || entry.type === 'fix_batch'))
    : []
}

function failureSummary(failures) {
  return `Fix browser app failures: ${failures.map((failure) => failure.stepId).join(', ')}`
}

function scrubFailureSummary(summary) {
  return bounded(String(summary || '')
    .replace(/(?:\/private)?\/tmp\/\S+|\/[\w./-]+(?::\d+)?/g, ' ')
    .replace(/:\d+\b/g, ' ')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
    .replace(/\s+/g, ' '))
}

async function dispatchFixBatch(failures, deps, details) {
  if (typeof deps.dispatchFixBatch !== 'function') throw new Error('required leaf is unavailable')
  return deps.dispatchFixBatch(failures, details)
}

async function ensureCleanWorktreeAfterFix(fixResult, deps, details) {
  if (typeof deps.ensureCleanWorktreeAfterFix === 'function') {
    try {
      const out = await deps.ensureCleanWorktreeAfterFix(fixResult, details)
      if (out && out.ok === false) return { ok: false, reason: out.reason || 'dirty fix leftovers after lease reset failed' }
      if (out && out.action === 'park') return { ok: false, reason: out.reason || 'dirty fix leftovers after lease reset failed' }
      return { ok: true }
    } catch (err) {
      return { ok: false, reason: `test-pilot clean worktree guard failed: ${message(err)}` }
    }
  }
  if (fixResult && (fixResult.dirty || fixResult.uncommitted || fixResult.untracked)) {
    return { ok: false, reason: 'dirty fix leftovers require an injected lease-fenced reset before retry' }
  }
  return { ok: true }
}

function reconcileCommittedMutations(fixResult, history, intent, deps, details) {
  if (deps && typeof deps.reconcileCommittedMutations === 'function') {
    return deps.reconcileCommittedMutations(fixResult, history, intent, details)
  }
  const commitShas = normalizeShas(fixResult && (fixResult.commitShas || fixResult.commits || fixResult.shas))
  const changedFiles = normalizeStrings(fixResult && (fixResult.changedFiles || fixResult.files))
  const head = fixResult && (fixResult.head || fixResult.headAfter)
  const committed = fixResult && (
    fixResult.cleanCommittedMutations ||
    fixResult.committedMutations ||
    fixResult.committed === true ||
    head ||
    commitShas.length
  )
  const hasHistory = Array.isArray(history) && history.includes(intent)
  if (committed && !commitShas.length && !hasHistory) {
    return {
      ok: false,
      reason: 'clean committed mutations without matching browser fix-batch history cannot be reconciled deterministically',
    }
  }
  return { ok: true, commitShas, changedFiles, head }
}

function normalizeRerunScope(decision) {
  if (!decision || typeof decision !== 'object') return { action: 'rerun_all' }
  if (decision.action === 'rerun_subset') {
    return {
      action: 'rerun_subset',
      stepIds: normalizeStrings(decision.stepIds),
      failedStepIds: normalizeStrings(decision.failedStepIds),
      affectedStepIds: normalizeStrings(decision.affectedStepIds),
    }
  }
  return {
    action: 'rerun_all',
    failedStepIds: normalizeStrings(decision.failedStepIds),
  }
}

function recordsForRerun(records, rerunScope) {
  if (!rerunScope || rerunScope.action !== 'rerun_subset') return records
  const allowed = new Set(normalizeStrings(rerunScope.stepIds))
  if (!allowed.size) return records
  return records
    .map((record) => {
      const steps = (record.steps || []).filter((step) => allowed.has(stepKey(step)))
      return Object.assign({}, record, { steps })
    })
    .filter((record) => record.steps.length)
}

async function stabilizeReviewCode(deps, workItem, context, retryState, aggregated, records) {
  const needsReview = fixBatches(retryState.fixBatchHistory).length > 0 ||
    (typeof deps.alwaysStabilizeReviewCode === 'function' && deps.alwaysStabilizeReviewCode())
  if (!needsReview && typeof deps.reviewCode !== 'function') {
    return { ok: true, changed: false, reviewCoverageHead: retryState.currentHead, verifyPassedHead: retryState.currentHead }
  }
  if (!needsReview && deps.requireReviewCode !== true) {
    return { ok: true, changed: false, reviewCoverageHead: retryState.currentHead, verifyPassedHead: retryState.currentHead }
  }
  if (retryState.reviewStabilizationCycle >= 2) {
    return { ok: false, reason: 'review-code stabilization cycle cap reached' }
  }
  if (typeof deps.reviewCode !== 'function') {
    return { ok: false, reason: 'review-code stabilization leaf unavailable' }
  }
  const cycle = (retryState.reviewStabilizationCycle || 0) + 1
  const before = retryState.currentHead
  let result
  try {
    result = await deps.reviewCode(workItem, {
      purpose: 'test-pilot-stabilization',
      worktree: context.worktree,
      expectedHead: before,
      runDirSuffix: `test-pilot-${cycle}-${before}`,
      cycle,
      browserFixBatchCount: fixBatches(retryState.fixBatchHistory).length,
      records,
      aggregated,
    })
  } catch (err) {
    return { ok: false, reason: `review-code stabilization failed: ${message(err)}` }
  }
  if (!result || result.ok === false || result.gate === 'changes-requested' ||
      (result.phaseResult && result.phaseResult.confidence === 'low')) {
    return { ok: false, reason: (result && (result.reason || (result.phaseResult && result.phaseResult.assumptions && result.phaseResult.assumptions[0]))) || 'review-code stabilization parked' }
  }
  if (result.terminal === 'clean-with-skips') {
    return { ok: false, reason: 'review-code stabilization clean-with-skips produced no covers stamp' }
  }
  const after = result.head || result.headAfter || result.currentHead || before
  const changed = after !== before || result.changed === true || result.mutated === true
  return {
    ok: true,
    changed,
    head: after,
    reviewCoverageHead: result.reviewCoverageHead || result.covers || after,
    verifyPassedHead: result.verifyPassedHead || result.verifyHead || after,
  }
}

async function restoreFinalBaseline(deps, records, context, retryState) {
  if (typeof deps.restoreBaseline !== 'function') {
    return { ok: true, baseline: context.baseline || { head: retryState.currentHead, restored: true } }
  }
  try {
    const out = await deps.restoreBaseline(records, {
      context,
      head: retryState.currentHead,
      fixBatchHistory: retryState.fixBatchHistory,
      reviewStabilizationCycle: retryState.reviewStabilizationCycle || 0,
    })
    if (!out || out.ok === false || out.action === 'park' || out.confidence === 'low') {
      return { ok: false, reason: (out && out.reason) || 'final seed baseline restore parked' }
    }
    const baseline = out.baseline || out.status || out
    if (!coversHead(baseline, retryState.currentHead)) {
      return { ok: false, reason: 'final seed baseline restore did not verify the final head' }
    }
    return { ok: true, baseline }
  } catch (err) {
    return { ok: false, reason: `final seed baseline restore failed: ${message(err)}` }
  }
}

async function ensureFinalArtifacts(deps, payload) {
  if (typeof deps.ensureFinalArtifacts !== 'function') {
    return { ok: true, artifacts: payload.artifacts }
  }
  try {
    const out = await deps.ensureFinalArtifacts(payload)
    if (!out || out.ok === false || out.action === 'park' || out.confidence === 'low') {
      return { ok: false, reason: (out && out.reason) || 'final test-pilot results artifact parked' }
    }
    const artifacts = out.artifacts || out
    if (!artifacts.plan || !artifacts.results) {
      return { ok: false, reason: 'final test-pilot plan/results artifacts missing' }
    }
    return Object.assign({ ok: true, artifacts }, out)
  } catch (err) {
    return { ok: false, reason: `final test-pilot artifact publish failed: ${message(err)}` }
  }
}

async function publishFinalHead(deps, workItem, context, retryState, payload) {
  if (typeof deps.publishReady !== 'function') {
    return { ok: true, remotePr: context.remotePr || context.remotePR || { head: retryState.currentHead } }
  }
  try {
    const out = await deps.publishReady(workItem, retryState.currentHead, Object.assign({
      context,
      branch: context.branch,
      head: retryState.currentHead,
    }, payload))
    if (!out || out.ok === false || out.action === 'park' || out.confidence === 'low') {
      return { ok: false, reason: (out && out.reason) || 'final tested head publish parked' }
    }
    const remotePr = out.remotePr || out.remotePR || { branch: context.branch, head: out.head || retryState.currentHead }
    if (!coversHead(remotePr, retryState.currentHead)) {
      return { ok: false, reason: 'remote PR head does not equal final tested head' }
    }
    return { ok: true, remotePr }
  } catch (err) {
    return { ok: false, reason: `final tested head publish failed: ${message(err)}` }
  }
}

function coversHead(value, head) {
  if (!value || typeof value !== 'object') return false
  return value.head === head || value.covers === head || value.browserEvidenceHead === head
}

async function writeRetryStatus(deps, workItem, context, retryState, aggregated, records, reason) {
  return writeStatus(deps, workItem, milestoneStatus(context, workItem, 'browser-retry-parked', {
    planRecords: records,
    fixBatchHistory: retryState.fixBatchHistory,
    reviewStabilizationCycle: retryState.reviewStabilizationCycle || 0,
    browserEvidenceHead: retryState.browserEvidenceHead,
    lastBrowserResult: aggregated,
    reason,
  }))
}

function normalizeStrings(values) {
  if (!Array.isArray(values)) return []
  return values.map((value) => value == null ? '' : String(value)).filter(Boolean)
}

function normalizeShas(values) {
  return normalizeStrings(values)
}

function mergeAllowedSkippedResults(resultRecords, planRecords) {
  const records = resultRecords.map((record) => Object.assign({}, record))
  for (const planRecord of planRecords) {
    for (const step of planRecord.steps || []) {
      const skipped = step.status === 'skipped' || step.result === 'skipped'
      if (!skipped) continue
      records.push({
        stepId: stepKey(step),
        status: 'skipped',
        allowed: true,
        preserved: true,
        removalReason: step.removalReason,
        priorResult: step.priorResult,
        planContext: step.planContext,
        browserExecuted: true,
      })
    }
  }
  return records
}

function milestoneStatus(context, workItem, milestone, extra) {
  return Object.assign({
    schemaVersion: 1,
    verdict: 'park',
    milestone,
    workItem,
    branch: context.branch,
    head: context.head,
  }, extra || {})
}

async function callLeaf(fn, ...args) {
  if (typeof fn !== 'function') throw new Error('required leaf is unavailable')
  return fn(...args)
}

// Best-effort: stamp a parked status carrying WHY before an early low() return, so the mark-ready
// gate (and a human reading the sidecar) see the real cause instead of an opaque "status missing".
// Never changes the returned reason and never fails the phase if the write is unavailable/fails —
// the not_applicable path writes a status the same way; these early parks were the gap.
async function recordParkStatus(deps, workItem, context, reason) {
  if (!context) return
  try {
    await writeStatus(deps, workItem, milestoneStatus(context, workItem, 'parked', { reason }))
  } catch (_) { /* best-effort: low(reason) below still carries the real cause */ }
}

async function parkLow(deps, workItem, context, reason) {
  await recordParkStatus(deps, workItem, context, reason)
  return low(reason)
}

function low(reason) {
  return { confidence: 'low', assumptions: [reason] }
}

function message(err) {
  return err && err.message ? err.message : String(err || 'unknown')
}

module.exports = {
  testPilotPhase,
  collectAppBugFailures,
  dispatchFixBatch,
  ensureCleanWorktreeAfterFix,
  reconcileCommittedMutations,
  stabilizeReviewCode,
}

};

// ===== build_progress.js =====
__modules["build_progress"] = function (module, exports, require) {
// plugins/superheroes/lib/build_progress.js
function reconcile(taskList, committedTaskIds, unmappedCommits, reviewRecords, worktreeDirty, finalReview, provenance) {
  const committed = new Set(committedTaskIds || [])
  const reviews = reviewRecords || {}
  if (unmappedCommits && unmappedCommits > 0) {
    return { action: 'park', reason: `${unmappedCommits} commit(s) above the branch base carry no/unknown Task-Id — fail closed (UFR-7)` }
  }
  if (provenance === 'garbled') {
    return { action: 'park', reason: 'build provenance is unreadable (garbled) — fail closed (UFR-6)' }
  }
  let resume = null
  for (const t of taskList || []) {
    if (!(committed.has(t.id) && reviews[t.id] === 'passed')) { resume = t; break }
  }
  if (worktreeDirty) {
    return { action: 'reset_uncommitted', resume_at: resume, reason: 'uncommitted leftover changes — reset only those, then re-dispatch (UFR-12)' }
  }
  if (resume !== null) {
    if (committed.has(resume.id)) {
      return { action: 'review_task', resume_at: resume, reason: 'task implemented but not reviewed — keep the commit, take it up at review (UFR-7)' }
    }
    return { action: 'build_task', resume_at: resume, reason: 'first task not yet implemented — build it' }
  }
  if (finalReview === null || finalReview === undefined || !finalReview.clean) {
    return { action: 'final_review', reason: 'all tasks complete — run/resume the whole-branch final review to a clean result (FR-8/UFR-7)' }
  }
  if (provenance === 'absent') {
    return { action: 'write_provenance', reason: 'final review clean, provenance absent — (re)write provenance idempotently, do not re-review (FR-9)' }
  }
  return { action: 'complete', reason: 'build complete — provenance present over the handed-off commit' }
}
module.exports = { reconcile }

};

// ===== worker_recovery.js =====
__modules["worker_recovery"] = function (module, exports, require) {
// plugins/superheroes/lib/worker_recovery.js
// In-process twin of worker_recovery.py (#115 increment B) — byte-for-byte parity is CI-enforced
// (test_parity.py). Bounded build-worker recovery (UFR-3): (attempt, signal, maxAttempts) ->
// {action, reason} where action ∈ retry_with_context | escalate | park. A "plan is wrong" signal
// parks immediately; otherwise retry (early attempts), escalate on the attempt before the cap, then
// park at the cap.
const PLAN_WRONG = 'plan_wrong'
const DEFAULT_MAX_ATTEMPTS = 3

function decide(attempt, signal, maxAttempts = DEFAULT_MAX_ATTEMPTS) {
  if (signal === PLAN_WRONG) {
    return { action: 'park',
      reason: 'worker signalled the plan/task is wrong or too large — park (UFR-3)' }
  }
  if (attempt >= maxAttempts) {
    return { action: 'park',
      reason: `worker still blocked at the fixed maximum (${maxAttempts}) — park (UFR-3)` }
  }
  if (attempt === maxAttempts - 1) {
    return { action: 'escalate',
      reason: 'retry budget nearly spent — escalate to a more capable worker (UFR-3)' }
  }
  return { action: 'retry_with_context',
    reason: `worker needs more context — retry (attempt ${attempt} of ${maxAttempts})` }
}

module.exports = { decide, DEFAULT_MAX_ATTEMPTS, PLAN_WRONG }

};

// ===== task_review.js =====
__modules["task_review"] = function (module, exports, require) {
// plugins/superheroes/lib/task_review.js
// In-process twin of task_review.py (#115 increment B) — byte-for-byte parity is CI-enforced
// (test_parity.py). The BESPOKE two-verdict per-task review decision (FR-5/FR-6/FR-7, UFR-5), NOT
// routed through reviewPanel. Reuses only the loop primitives: circuit_breaker.BLOCKING (the
// Critical/Important set), circuit_breaker.checkCircuitBreaker, and loop_state.decide.
const circuitBreaker = require('./circuit_breaker.js')
const loopState = require('./loop_state.js')

const REQUIRED_VERDICTS = ['spec_compliance', 'code_quality']
// exit_skipped maps to PARK, never complete: a deliberately-left-unresolved blocker must park (UFR-4).
// (The bespoke loop passes skippedBlocking=0 so loop_state never returns exit_skipped today; the
// fail-closed mapping guards against a future contract change rather than fail open.)
const _MAP = { review: 'review', exit_clean: 'complete', exit_skipped: 'park', halt: 'park' }

function _partition(findings) {
  const blocking = []; const minors = []; const cannotVerify = []
  for (const f of findings || []) {
    if (f && f.cannot_verify_from_diff) cannotVerify.push(f)
    if (f && circuitBreaker.BLOCKING.has(f.severity)) blocking.push(f)
    else minors.push(f)
  }
  return { blocking, minors, cannotVerify }
}

function decide(verdicts, findings, rnd, maxRounds, history) {
  verdicts = verdicts || {}
  if (!REQUIRED_VERDICTS.every((k) => verdicts[k])) {
    return { action: 're_request', blocking: [], minors: [], cannot_verify: [],
      reason: 'both verdicts (spec-compliance + code-quality) are required (FR-5)' }
  }
  const { blocking, minors, cannotVerify } = _partition(findings)
  const rounds = (history || []).concat([{ round: rnd, findings: findings || [] }])
  const brk = circuitBreaker.checkCircuitBreaker(rounds, maxRounds)
  const [action, , loopReason] = loopState.decide(blocking.length, 0, rnd, maxRounds, !!brk.halt)
  let mapped = _MAP[action]
  let reason = loopReason
  if (brk.halt) {
    reason = brk.detail !== undefined ? brk.detail : reason
  }
  // UFR-5: never complete while a cannot-verify item is unresolved — force a resolution round.
  if (mapped === 'complete' && cannotVerify.length) {
    mapped = 'review'
    reason = "unresolved 'cannot verify from diff' item(s) must be confirmed, sent back, or parked (UFR-5)"
  }
  return { action: mapped, blocking, minors, cannot_verify: cannotVerify, reason }
}

module.exports = { decide }

};

// ===== build_phase.js =====
__modules["build_phase"] = function (module, exports, require) {
// plugins/superheroes/lib/build_phase.js
// The native "workhorse" build phase (#87). CONTROL FLOW ONLY (CONVENTIONS §10.1): every judgement
// is a pure Python decider behind a *_cli.py bridge; this module detects events and sequences them.
// It makes NO PR/merge/force-push (FR-10).
// FR-4a (#115): build state lives in memory during a continuous run. build_state gather /
// build_progress.reconcile are called ONLY on entry/resume (not per loop iteration).
const { reviewPanel } = require('./review_panel_shell.js')
const { io } = require('./io_seam.js')
const modelTierTwin = require('./model_tier.js')
// #115 increment B: the two SMART judgement leaves (worker_recovery, task_review) are now
// parity-locked in-process twins (no leaf — judgments live in twins, called in-process). Pure
// deciders with no IO, so a top-level require is safe (no load-time cycle).
const workerRecoveryTwin = require('./worker_recovery.js')
const taskReviewTwin = require('./task_review.js')

const LIB = 'plugins/superheroes/lib'
const MAX_ROUNDS = 3                 // per-task + final-review fix bound (plan: same bound as a task)

function shq(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }
function park(reason) { return { confidence: 'low', assumptions: [reason] } }
function ok() { return { confidence: 'high', assumptions: [] } }

// Reuse the spine's proven exec primitive (lazy require avoids a load-time cycle: showrunner's
// build_phase reference is itself lazy, and deferring keeps build_phase's require surface unchanged
// for the smokes). One exec, no duplication, no front-half change.
let _execFn = null
function exec(commands) {
  if (!_execFn) _execFn = require('./showrunner.js').exec
  return _execFn(commands)
}

// build_progress.reconcile via the module (NOT a destructured load-time binding) so reconcileState
// calls THROUGH the module export — keeps the twin the single source AND makes it spy-able in smokes
// (a testability improvement; the FR-4a entry-once property is re-asserted by spying reconcile).
function _reconcile(...a) { return require('./build_progress.js').reconcile(...a) }

// model_tier overrides: mirror showrunner.js's authorModel — read from globalThis.__SR_OVERRIDES
// (set by the Task 17 startup pipe; absent in test/throwaway runs -> null -> DEFAULT_TIERS).
function _overrides() { return (typeof globalThis !== 'undefined' && globalThis.__SR_OVERRIDES) || null }

// #115 increment B: cmdRunner is gone. The IO/side-effect leaves are ported to exec(raw)+in-process
// -parse (increment A); the two SMART judgement leaves (worker_recovery, task_review) are now
// parity-locked in-process twins (above) — no JS<->Python bridge remains in this module.

// FR-4a: gather authoritative git state (entry/resume only, NOT per loop iteration).
// Ported to exec(raw)+in-process-parse: the leaf runs the command and returns its raw stdout; the
// spine JSON.parses it here (the leaf can no longer derail by mis-copying fields — the live bug).
// Returns the parsed state object, or NULL on exec-fail / parse-fail (the caller parks honestly).
// FR-8: thread configurable base (--base) when globalThis.__SR_BASE is set; absent -> _base() detection.
async function gatherState(workItem, branch, validIds, wt) {
  const _srBase = (typeof globalThis !== 'undefined' && globalThis.__SR_BASE) ? String(globalThis.__SR_BASE) : null
  const _baseArg = _srBase ? ` --base ${shq(_srBase)}` : ''
  const _res = await exec([
    `python3 ${LIB}/build_state_cli.py gather --work-item ${shq(workItem)} --branch ${shq(branch)} --valid-ids ${shq(validIds)} --worktree ${shq(wt)}${_baseArg}`,
  ])
  const _r0 = _res && _res[0]
  if (!_r0 || !_r0.ok) return null
  try { return JSON.parse(_r0.stdout) } catch (_e) { return null }
}

// FR-4a: derive the starting action + resume_at from authoritative state using the in-process twin.
// Returns the reconcile decision object ({action, resume_at?, reason?}). Calls THROUGH the module
// export (_reconcile) so the twin stays the single source and is spy-able in smokes.
function reconcileState(taskList, state) {
  return _reconcile(
    taskList,
    state.committed_task_ids || [],
    state.unmapped_commits || 0,
    state.review_records || {},
    !!(state.worktree_dirty),
    state.final_review || null,
    state.provenance || null)
}

async function buildPhase(workItem, generation) {
  const root = '$(git rev-parse --show-toplevel)'
  // UFR-1: refuse unless the tasks gate is passed. read-gate prints a PLAIN STRING (e.g. 'passed'),
  // NOT JSON — exec returns the raw stdout; trim it directly (no JSON.parse). Fail closed on exec-fail.
  const _gateRes = await exec([
    `python3 ${LIB}/definition_doc.py read-gate --doc tasks --work-item ${shq(workItem)} --root "${root}"`,
  ])
  const _gate0 = _gateRes && _gateRes[0]
  if (!_gate0 || !_gate0.ok) return park('could not read the tasks gate — failing closed')
  const gate = String(_gate0.stdout || '').trim()
  if (gate !== 'passed') return park(`tasks gate not passed (${gate}) — refusing to build (UFR-1)`)
  // UFR-2: setup the content-addressed worktree/branch + persist this run's generation.
  const _setupRes = await exec([
    `python3 ${LIB}/build_entry.py --work-item ${shq(workItem)} --generation ${shq(String(generation))}`,
  ])
  const _setup0 = _setupRes && _setupRes[0]
  if (!_setup0 || !_setup0.ok) return park('build setup failed: no branch')
  let setup
  try { setup = JSON.parse(_setup0.stdout) } catch (_e) { return park('build setup failed: no branch') }
  if (!setup.branch) return park('build setup failed: ' + (setup.error || 'no branch'))
  const branch = setup.branch
  // The build branch is checked out in a SEPARATE managed build worktree (build_entry -> buildtree);
  // every git read/write below must operate there, not in the showrunner's main checkout.
  const wt = setup.path
  // UFR-8: zero executable tasks -> finish without building.
  // With exec+JSON.parse the BUG-2 string-recovery is structurally moot, but KEEP the
  // typeof===string JSON.parse recovery + Array.isArray guard as defense-in-depth (BUG-3).
  const _taskRes = await exec([`python3 ${LIB}/task_list_cli.py --work-item ${shq(workItem)}`])
  const _task0 = _taskRes && _taskRes[0]
  if (!_task0 || !_task0.ok) return park('task-list command did not run — failing closed')
  let _taskResult
  try { _taskResult = JSON.parse(_task0.stdout) } catch (_e) { return park('task-list returned unparseable output — failing closed') }
  let tasks = _taskResult.tasks
  if (typeof tasks === 'string') {
    try { tasks = JSON.parse(tasks) } catch (_) { tasks = null }
  }
  if (!Array.isArray(tasks)) return park('task-list returned non-array tasks — schema mismatch, failing closed')
  // Silent-zero guard: if the doc has raw task headings but the parser returned nothing,
  // the format is wrong (e.g. em-dash in an old doc not yet re-authored). Park explicitly
  // instead of silently finishing (which would be a UFR-8 bypass — building nothing when
  // there are tasks to build). raw_task_heading_count===0 is the genuine empty case.
  const rawHeadingCount = typeof _taskResult.raw_task_heading_count === 'number' ? _taskResult.raw_task_heading_count : 0
  if (tasks.length === 0 && rawHeadingCount > 0) {
    return park('tasks doc present but no parseable ### Task N: headings — format mismatch, refusing to build nothing')
  }
  if (tasks.length === 0) { log('no tasks to build'); return ok() }

  const validIds = tasks.map((t) => t.id).join(',')

  // FR-4a: gather authoritative git state ONCE at entry (not per iteration).
  // A fresh invocation (after park/crash) re-gathers here — resume correctness preserved.
  // gatherState returns null on exec/parse failure — park honestly (fail closed; never walk on a
  // mis-read or absent git state — the live bug that mis-reported a clean tree as dirty).
  let state = await gatherState(workItem, branch, validIds, wt)
  if (!state) return park('could not gather authoritative git state — failing closed')

  // Handle entry-level non-forward reconcile actions before entering the forward-walk.
  // reset_uncommitted: fence, reset, then re-gather + re-reconcile ONCE (a reset is resume-like).
  let d = reconcileState(tasks, state)
  if (d.action === 'park') return park(d.reason || 'build_progress parked at entry')
  if (d.action === 'reset_uncommitted') {
    if (!(await fenceOrPark(workItem, generation))) return park('lease lost before reset — park (UFR-10)')
    const rr = await resetUncommitted(wt, branch)
    if (!rr.ok) return park('could not reset uncommitted changes: ' + (rr.error || 'unknown'))
    // Re-gather + re-reconcile after reset (ground truth mutated).
    state = await gatherState(workItem, branch, validIds, wt)
    if (!state) return park('could not gather authoritative git state — failing closed')
    d = reconcileState(tasks, state)
    if (d.action === 'park') return park(d.reason || 'build_progress parked after reset')
    // If the SECOND reconcile is STILL reset_uncommitted, the reset did not fully clean the worktree.
    // Park honestly — bounded, fail-closed — rather than fall through into a dirty forward-walk
    // (#115 final review FIX 4 / UFR-12). One reset attempt only; a still-dirty tree is the owner's.
    if (d.action === 'reset_uncommitted') return park('worktree still dirty after reset — park (UFR-12)')
  }

  // FR-4a forward-walk: in-memory state for the continuous run.
  // Seed from the entry gather; advance only on confirmed durable success.
  const builtTaskIds = new Set(state.committed_task_ids || [])
  const reviewRecords = Object.assign({}, state.review_records || {})
  // Track whether THIS walk built or reviewed any task. If it did, the branch HEAD changed, so the
  // ENTRY gather's final_review.clean / provenance are STALE — the whole-branch final review must
  // RE-RUN over the new HEAD and provenance must be RE-WRITTEN. A pure resume (nothing built this
  // walk) keeps the skip optimization (the entry state is fresh). (#115 final review FIX 3 / FR-4a.)
  let didWork = false
  // Determine the starting index from the entry reconcile's resume_at.
  const resumeTaskId = d.resume_at ? d.resume_at.id : null

  // Forward-walk states that are already-past (handled after all-tasks-built+reviewed):
  // final_review, write_provenance, complete are processed after the task loop.
  // If the entry action indicates we're already past the task loop, skip it.
  const pastTaskLoop = (d.action === 'final_review' || d.action === 'write_provenance' || d.action === 'complete')

  if (!pastTaskLoop) {
    // Guard: bound so a non-progressing forward-walk can't spin forever.
    const MAX_GUARD = tasks.length * 4 + 8
    let guard = 0
    // Find the start index (resume from the first un-built or un-reviewed task).
    let startIdx = 0
    if (resumeTaskId !== null) {
      const idx = tasks.findIndex((t) => t.id === resumeTaskId)
      if (idx >= 0) startIdx = idx
    }

    for (let i = startIdx; i < tasks.length; i += 0) {
      guard += 1
      if (guard > MAX_GUARD) {
        return park('build loop exceeded its guard bound without completing (last task: '
          + (tasks[i] ? tasks[i].id : '?') + ')')
      }
      const task = tasks[i]
      const isBuilt = builtTaskIds.has(task.id)
      const isReviewed = reviewRecords[task.id] === 'passed'

      if (isBuilt && isReviewed) {
        // Already done in memory; advance.
        i += 1; continue
      }
      if (!isBuilt) {
        // Build the task (fence, dispatch worker, commit, journal, then review).
        const r = await buildOneTask(workItem, generation, task, branch, validIds, wt)
        if (r.parked) return park(r.reason)
        // On confirmed success (buildOneTask only returns !parked when journal+review both passed):
        builtTaskIds.add(task.id)
        reviewRecords[task.id] = 'passed'
        didWork = true                 // HEAD moved this walk -> entry final_review/provenance stale
        i += 1; continue
      }
      if (isBuilt && !isReviewed) {
        // Task implemented but not reviewed (e.g. after a crash mid-review): review it.
        const r = await reviewOneTask(workItem, generation, task, branch, wt)
        if (r.parked) return park(r.reason)
        reviewRecords[task.id] = 'passed'
        didWork = true                 // a review (with its possible fix commits) also moves HEAD
        i += 1; continue
      }
    }
  }

  // All tasks built+reviewed. Run the whole-branch final review.
  // Skip ONLY on a pure resume (didWork === false): the entry final_review.clean then covers the
  // current HEAD. If this walk built/reviewed anything, HEAD moved — the entry's final_review.clean
  // is STALE, so RE-RUN the whole-branch final review over the new HEAD (#115 final review FIX 3).
  const alreadyFinalClean = !didWork && state.final_review && state.final_review.clean
  if (!alreadyFinalClean) {
    const fr = await runFinalReview(workItem, generation, branch, wt)
    // UFR-4 fail-closed intent: only a 'clean' terminal advances. Parking on
    // 'clean-with-skips'/'halted'/'cannot-certify' is deliberate — a skipped blocker must park.
    if (fr.terminal !== 'clean') return park('whole-branch final review did not reach clean: ' + fr.terminal)
    await recordFinalReviewClean(workItem)
  }

  // Write provenance if absent (FR-9): idempotent, only after final review clean. Same staleness
  // guard: a walk that did work must RE-WRITE provenance over the new HEAD (don't trust the entry's).
  const alreadyProv = !didWork && state.provenance && state.provenance !== 'absent'
  if (!alreadyProv) {
    const p = await writeProvenance(workItem)
    if (!p.ok) return park('provenance not recorded: ' + (p.error || 'unknown'))
  }

  return ok()
}

// Reset ONLY uncommitted/untracked changes; never discard a commit (UFR-12). Returns {ok,error?}
// so a failed reset parks honestly (UFR-6) rather than spinning to the guard bound.
async function resetUncommitted(wt, branch) {
  return agent(
    `In the build worktree at ${wt} (branch ${branch}), reset only uncommitted state: `
    + `git checkout -- . && git clean -fd . — do NOT touch any commit. `
    + `Return JSON {"ok":true} on success or {"ok":false,"error":"<reason>"}.`,
    { label: 'reset-uncommitted', schema: { type: 'object', required: ['ok'], properties: { ok: {}, error: { type: 'string' } } } })
}

// Record build provenance once over HEAD = X (FR-9), via the existing prov_entry leaf.
// exec/parse fail -> {ok:false, error:'provenance leaf did not run'} so the caller's !p.ok parks.
async function writeProvenance(workItem) {
  const _res = await exec([`python3 ${LIB}/prov_entry.py --step build --work-item ${shq(workItem)}`])
  const _r0 = _res && _res[0]
  if (!_r0 || !_r0.ok) return { ok: false, error: 'provenance leaf did not run' }
  try { return JSON.parse(_r0.stdout) } catch (_e) { return { ok: false, error: 'provenance leaf did not run' } }
}

// Record final-review-clean. Caller does not check .ok today (preserve that), but stay fail-closed-safe.
async function recordFinalReviewClean(workItem) {
  const _res = await exec([
    `python3 ${LIB}/build_state_cli.py record-final-review --work-item ${shq(workItem)} --clean true`,
  ])
  const _r0 = _res && _res[0]
  if (!_r0 || !_r0.ok) return { ok: false }
  try { return JSON.parse(_r0.stdout) } catch (_e) { return { ok: false } }
}

// fenceOrPark: lease-fence acquire. CRITICAL fail-closed: an exec/parse failure must read as a LOST
// fence (false), NEVER as ok — a fence failure read as ok would let an unfenced write through (UFR-10).
async function fenceOrPark(workItem, generation) {
  const _res = await exec([
    `python3 ${LIB}/fence_cli.py --work-item ${shq(workItem)} --generation ${shq(String(generation))}`,
  ])
  const _r0 = _res && _res[0]
  if (!_r0 || !_r0.ok) return false
  let f
  try { f = JSON.parse(_r0.stdout) } catch (_e) { return false }
  return !!(f && f.ok)
}

// Build one task test-first (FR-3) with bounded recovery (UFR-3), then review it. `validIds` is the
// FULL enumeration's task ids (comma-joined) so the write-time trailer check scores every above-base
// commit against the whole task set — not just this task (an earlier task's commit is not "unmapped").
async function buildOneTask(workItem, generation, task, branch, validIds, wt) {
  let attempt = 1
  for (;;) {
    if (!(await fenceOrPark(workItem, generation))) {
      return { parked: true, reason: 'lease lost before build — park (UFR-10)' }
    }
    const worker = await agent(
      `In the build worktree at ${wt} (branch ${branch}), implement Task ${task.id} (${task.title}) TEST-FIRST: write the test(s), `
      + `run to observe FAIL, implement, run to observe PASS. Commit with a trailer line `
      + `"Task-Id: ${task.id}" on EVERY commit you make for this task. Return JSON `
      + `{"ok":bool,"signal":"ok|needs_context|plan_wrong","evidence":{"testFailed":bool,"testPassed":bool}}.`,
      { label: 'worker', schema: { type: 'object', required: ['ok'] } })
    if (worker.ok) {
      // write-time trailer enforcement (UFR-7): every above-base commit must carry its Task-Id.
      // This is a per-built-task CORRECTNESS read (NOT the FR-4a per-iteration resume gather).
      // exec+parse, fail closed: a leaf that can't run / returns unparseable output must NOT read
      // as a clean trailer state — park honestly (UFR-7).
      const _chkRes = await exec([
        `python3 ${LIB}/build_state_cli.py gather --work-item ${shq(workItem)} --branch ${shq(branch)} --valid-ids ${shq(validIds)} --worktree ${shq(wt)}`,
      ])
      const _chk0 = _chkRes && _chkRes[0]
      let chk
      if (!_chk0 || !_chk0.ok) return { parked: true, reason: 'could not verify commit trailers — failing closed (UFR-7)' }
      try { chk = JSON.parse(_chk0.stdout) } catch (_e) { return { parked: true, reason: 'could not verify commit trailers — failing closed (UFR-7)' } }
      if ((chk.unmapped_commits || 0) > 0) {
        return { parked: true, reason: 'a commit lacks its Task-Id trailer — park (UFR-7)' }
      }
      // record-before-advance: journal must succeed before the task counts as built. Guard the .ok
      // explicitly (defense-in-depth for invariant #4): a failed journal must NOT advance into the
      // review loop — park honestly (#115 final review FIX 8). The FR-4a forward-walk no longer
      // self-heals a missed journal per-iteration, so this guard is the advance fence.
      // exec/parse fail -> jrnl = {ok:false} so the guard parks (a missed journal must NOT advance).
      const _jrnlRes = await exec([
        `python3 ${LIB}/journal_entry.py --work-item ${shq(workItem)} --payload `
        + `${shq(JSON.stringify({ phase: 'workhorse', event: 'task_built', task: task.id, evidence: worker.evidence }))}`,
      ])
      const _jrnl0 = _jrnlRes && _jrnlRes[0]
      let jrnl
      if (!_jrnl0 || !_jrnl0.ok) jrnl = { ok: false }
      else { try { jrnl = JSON.parse(_jrnl0.stdout) } catch (_e) { jrnl = { ok: false } } }
      if (!(jrnl && jrnl.ok)) {
        return { parked: true, reason: 'task journal write failed (record-before-advance) — park' }
      }
      return reviewLoop(workItem, generation, task, branch, wt)
    }
    // #115 increment B: bounded recovery decided in-process via the worker_recovery twin (no leaf).
    const rec = workerRecoveryTwin.decide(attempt, worker.signal || 'needs_context')
    if (rec.action === 'park') return { parked: true, reason: rec.reason }
    attempt += 1                                   // retry_with_context / escalate -> re-dispatch
  }
}

// A committed-but-unreviewed task (UFR-7) is taken up at review without rebuilding.
async function reviewOneTask(workItem, generation, task, branch, wt) {
  return reviewLoop(workItem, generation, task, branch, wt)
}

// The bespoke two-verdict review + bounded fix loop (FR-4..7, UFR-4/5). Never uses reviewPanel.
async function reviewLoop(workItem, generation, task, branch, wt) {
  // model_tier resolved in-process via the existing twin (no leaf): mirror showrunner's authorModel.
  const fixerModel = modelTierTwin.resolveModel('fixer', _overrides(), 'code')
  const history = []
  let round = 1
  for (;;) {
    const review = await agent(
      `Review Task ${task.id} (${task.title}) on branch ${branch}. Return JSON `
      + `{"verdicts":{"spec_compliance":"pass|fail","code_quality":"pass|fail"},`
      + `"findings":[{"severity","file","title","cannot_verify_from_diff"}]}.`,
      { label: 'review', schema: { type: 'object', required: ['verdicts'] } })
    // #115 increment B: the bespoke two-verdict decision is decided in-process via the task_review
    // twin (no leaf). Same shape: {action, blocking, minors, cannot_verify, reason}.
    const d = taskReviewTwin.decide(review.verdicts || {}, review.findings || [], round, MAX_ROUNDS, history)
    if (d.action === 'park') return { parked: true, reason: d.reason }
    if (d.action === 're_request') continue        // both verdicts required (FR-5) -> re-review
    if (d.action === 'complete') {
      if (Array.isArray(d.minors) && d.minors.length) {
        // append the carried-forward Minors (result unused — best-effort accumulator write).
        await exec([
          `python3 ${LIB}/minor_rollup_cli.py --work-item ${shq(workItem)} --append ${shq(JSON.stringify(d.minors))}`,
        ])
      }
      // record-before-advance: record-reviewed must succeed before the task counts reviewed.
      // (Caller does not branch on .ok today; keep behavior — the exec call still records it.)
      await exec([
        `python3 ${LIB}/build_state_cli.py record-reviewed --work-item ${shq(workItem)} --task ${shq(task.id)}`,
      ])
      return { parked: false }
    }
    // d.action === 'review': fence, fix the blockers + cannot-verify items, then re-review (FR-6/UFR-5).
    if (!(await fenceOrPark(workItem, generation))) {
      return { parked: true, reason: 'lease lost before fix — park (UFR-10)' }
    }
    await agent(
      `In the build worktree at ${wt} (branch ${branch}), fix these Task ${task.id} findings and commit with trailer `
      + `"Task-Id: ${task.id}": ${JSON.stringify((d.blocking || []).concat(d.cannot_verify || []))}`,
      { label: 'fixer', model: fixerModel })
    history.push({ round, findings: review.findings || [] })
    round += 1
  }
}

async function runFinalReview(workItem, generation, branch, wt) {
  // verify command via exec+parse; on exec/parse fail -> 'none' (verify command unknown -> the
  // verify_gate twin fails closed downstream; a missing verify command already maps to a safe path).
  const _verifyRes = await exec([`python3 ${LIB}/verify_command_cli.py`])
  const _verify0 = _verifyRes && _verifyRes[0]
  let verify = 'none'
  if (_verify0 && _verify0.ok) { try { verify = JSON.parse(_verify0.stdout).command || 'none' } catch (_e) { verify = 'none' } }
  // model_tier resolved in-process via the existing twin (no leaf): mirror showrunner's authorModel.
  const reviewerModel = modelTierTwin.resolveModel('reviewer-deep', _overrides(), null)
  const fixerModel = modelTierTwin.resolveModel('fixer', _overrides(), 'code')
  // carried-forward Minors via exec+parse; on exec/parse fail -> [].
  const _minorsRes = await exec([`python3 ${LIB}/minor_rollup_cli.py --work-item ${shq(workItem)}`])
  const _minors0 = _minorsRes && _minorsRes[0]
  let _minorsResult = null
  if (_minors0 && _minors0.ok) { try { _minorsResult = JSON.parse(_minors0.stdout) } catch (_e) { _minorsResult = null } }
  const minors = Array.isArray(_minorsResult && _minorsResult.minors) ? _minorsResult.minors : []
  const runDir = `/tmp/workhorse-${workItem}-final-review`
  // The #104 shell resolves these caller leaves from global scope. #115: the reviewer RETURNS its
  // findings[] array (the panel holds it in memory + runs the merge/tally twins in-process) — no
  // findings-generalist.json. This is the single-reviewer code leg (legKind.panel:false), so the
  // shell compiles the raw returned findings; there is no synthesis leaf.
  globalThis.reviewerAgent = async (_r, _ctx, _rub, _rdir, round) => {
    const out = await agent(
      `In the build worktree at ${wt}, review the whole branch ${branch}; carried-forward Minor findings: ${JSON.stringify(minors)}. `
      + `Return ONLY a JSON object {"findings":[{"file","line","title","severity","evidence"}]} ({"findings":[]} if nothing to flag).`,
      { label: `reviewer:${round}`, model: reviewerModel,
        schema: { type: 'object', required: ['findings'], properties: { findings: { type: 'array' } } } })
    return (out && Array.isArray(out.findings)) ? out.findings : null
  }
  // recordDeferred writes the deferred-set (the channel the in-process tally reads) with one cheap
  // direct io-seam write — no genuine agent. (build_phase has no exec seam; the awaited io write below
  // is the bundle's cheap leaf-bash pipe, the equivalent of showrunner's exec for this leg.)
  globalThis.recordDeferred = async (report, verdict, rdir) => {
    const p = `${rdir}/deferred-set.json`
    let set = await io().readJson(p, {})
    for (const id of (report && report.fixed) || []) set[String(id)] = (verdict && verdict.gate) || 'resolved'
    await io().writeFile(p, JSON.stringify(set))
  }
  const fixStep = async (blockers) => {
    // Fence before the only branch-mutating final-review path (UFR-10: the module's fence-before-write
    // invariant). A lost lease -> null -> reviewPanel treats it as a fix failure -> halted -> phase parks.
    if (!(await fenceOrPark(workItem, generation))) return null
    await agent(`In the build worktree at ${wt} (branch ${branch}), fix these whole-branch blocking findings: ${JSON.stringify(blockers)}`,
      { label: 'final-fixer', model: fixerModel })
    return { fixed: blockers.map((b) => b.id || b.title) }
  }
  const verdict = await reviewPanel({
    reviewerSet: ['generalist'], context: { workItem, branch }, rubric: 'review-base',
    runKey: runDir, runDir, fixStep, maxRounds: MAX_ROUNDS,
    legKind: { panel: false, code: true }, verifyCommand: verify,
  })
  return { terminal: verdict && verdict.terminal }
}

module.exports = { buildPhase, shq, LIB, MAX_ROUNDS, park, ok }
module.exports.buildOneTask = buildOneTask
module.exports.reviewOneTask = reviewOneTask
module.exports.reviewLoop = reviewLoop
module.exports.fenceOrPark = fenceOrPark
module.exports.runFinalReview = runFinalReview
module.exports.resetUncommitted = resetUncommitted
module.exports.writeProvenance = writeProvenance
module.exports.recordFinalReviewClean = recordFinalReviewClean
module.exports.gatherState = gatherState

};

// ===== model_tier.js =====
__modules["model_tier"] = function (module, exports, require) {
// model_tier.js — twin of model_tier.resolve_model
// Pure + deterministic model-tier resolver: role -> model name or null.

const DEFAULT_TIERS = {
  orchestrator: null,
  reviewer: 'sonnet',
  'reviewer-deep': 'opus',
  mechanical: 'haiku',
  synthesis: 'opus',
  fixer: 'sonnet',
  author: 'opus',
}

const _FIXER_BY_CONTEXT = { code: 'sonnet', doc: 'opus' }

// Python `k in dict` / `dict.get(k, default)` test OWN keys only; JS `in`/bracket walk the prototype
// chain (so `'constructor' in {}` is true). Use own-key membership everywhere a twin mirrors Python
// dict membership, so a prototype-named role/identity ('constructor', 'toString', '…::hasOwnProperty')
// cannot drift the result.
function hasOwn(o, k) {
  return Object.prototype.hasOwnProperty.call(o, k)
}

function resolveModel(role, overrides, context) {
  if (!hasOwn(DEFAULT_TIERS, role)) role = 'reviewer'   // safe capable default for an unknown role
  let def = DEFAULT_TIERS[role]
  if (role === 'fixer' && hasOwn(_FIXER_BY_CONTEXT, context)) def = _FIXER_BY_CONTEXT[context]
  if (!overrides || typeof overrides !== 'object' || Array.isArray(overrides)) return def
  if (!hasOwn(overrides, role)) return def
  const v = overrides[role]
  if (v === null) return null
  if (typeof v === 'string' && v.trim()) return v.trim()
  return def   // malformed (non-str / empty) -> default
}

module.exports = { resolveModel, DEFAULT_TIERS }

};

// ===== phase_step.js =====
__modules["phase_step"] = function (module, exports, require) {
// plugins/superheroes/lib/phase_step.js
// Faithful JS twin of phase_step.py:decide — parity-locked. Safety ordering: assumption /
// low-confidence parks are evaluated BEFORE the gate (a recorded assumption parks even on a
// passed gate). Pure + fail-closed.
function pyReprStr(v) {
  // Python %r for a simple str: single-quoted, backslash- and quote-escaped.
  if (typeof v === 'string') return "'" + v.replace(/\\/g, '\\\\').replace(/'/g, "\\'") + "'"
  if (v === null || v === undefined) return 'None'
  return String(v)
}
function decide(phaseResult, gate) {
  const pr = phaseResult || {}
  if (pr.assumptions && pr.assumptions.length) {
    return { action: 'park_assumption', reason: 'phase recorded a material assumption' }
  }
  if (pr.confidence === 'low') {
    return { action: 'park_low_confidence', reason: 'phase recorded confidence below the parking threshold' }
  }
  if (gate === null || gate === undefined || gate === 'passed') {
    return { action: 'proceed', reason: (gate === null || gate === undefined) ? 'no review gate' : 'gate passed' }
  }
  if (gate === 'changes-requested') return { action: 'park_changes_requested', reason: 'review requested changes' }
  if (gate === 'pending') return { action: 'park_pending', reason: 'gate not passed (pending / not yet approved)' }
  return { action: 'park_unexpected_gate', reason: 'unexpected or unreadable gate value: ' + pyReprStr(gate) }
}
module.exports = { decide }

};

// ===== recover.js =====
__modules["recover"] = function (module, exports, require) {
// plugins/superheroes/lib/recover.js
const _UNKNOWN = 'unknown'
function _branchHash(branch) {
  if (typeof branch !== 'string' || !branch.includes('-')) return null
  return branch.slice(branch.lastIndexOf('-') + 1)
}
function reconcile(checkpoint, world) {
  world = world || {}
  if (world.store_ok === false) {
    return { action: 'park_gate', reason: 'control-plane store unusable — fail closed (no lockless run)' }
  }
  if (!checkpoint) return { action: 'world_derive', reason: 'no checkpoint — re-derive from reality' }
  if (checkpoint._incompatible) {
    // Match Python checkpoint.get("reason", "unknown reason"): default ONLY when the key is absent;
    // a present-but-falsy reason ("") is emitted as-is. (`|| 'unknown reason'` would wrongly substitute.)
    return { action: 'park_gate', reason: 'checkpoint incompatible — ' + (checkpoint.reason === undefined ? 'unknown reason' : checkpoint.reason) }
  }
  if (checkpoint.branch) {
    const cur = world.current_content_hash
    if (cur === null || cur === undefined) {
      return { action: 'gate', reason: 'could not recompute the tasks content-hash (transient) — not resuming blind' }
    }
    const bh = _branchHash(checkpoint.branch)
    if (bh !== null && bh !== cur) {
      return { action: 'gate', reason: 'approved tasks changed since this run started (stale spec)' }
    }
  }
  const pr = world.pr
  if (pr && typeof pr === 'object' && pr.state === 'merged') {
    return { action: 'gate', reason: "PR already merged — the work is done (merge is the owner's)" }
  }
  if (pr === _UNKNOWN) {
    return { action: 'gate', reason: 'could not read PR state (transient) — not creating a second PR' }
  }
  if (world.seeded_empty === _UNKNOWN) {
    return { action: 'gate', reason: 'could not read seeded state (transient) — cannot confirm a clean baseline' }
  }
  return { action: 'continue', from_step: checkpoint.lastGoodStep === undefined ? null : checkpoint.lastGoodStep, reason: 'reconciled — resume' }
}
function prAction(world) {
  const pr = (world || {}).pr
  if (pr === _UNKNOWN) return 'gate'
  if (pr && typeof pr === 'object' && !Array.isArray(pr)) {
    if (!pr.number) return 'gate'
    return pr.state === 'merged' ? 'gate' : 'adopt'
  }
  if (pr !== null && pr !== undefined) return 'gate'
  return 'create'
}
const FLOOR_RETRY_MAX = 3
function rearmAction(attempt, armed, maxRetry = FLOOR_RETRY_MAX) {
  if (armed) return 'proceed'
  if (attempt < maxRetry) return 'retry'
  return 'park_gate'
}
module.exports = { reconcile, prAction, rearmAction, FLOOR_RETRY_MAX }

};

// ===== front_half.js =====
__modules["front_half"] = function (module, exports, require) {
// plugins/superheroes/lib/front_half.js
// Pure-decider JS twin of front_half.py: gate_for_terminal + is_usable_draft.
// render_run_outcome is deferred to Task 18. IO helpers (merge_findings /
// record_deferred / append_notify) stay Python executors (Task 11).

function gateForTerminal(terminal) {
  return (terminal === 'clean' || terminal === 'clean-with-skips') ? 'passed' : 'changes-requested'
}

// Faithful port of front_half.py _PLACEHOLDER (same four alternatives, same IGNORECASE flag).
// NOTE: Python _PLACEHOLDER is compiled with re.IGNORECASE only (NOT re.ASCII), so Python's
// \w/\s/\b are UNICODE-aware there. JS \w/\s/\b (no `u` flag) are ASCII-aware. The twin
// intentionally uses JS-default classes — NOT explicit ASCII classes as in circuit_breaker.js.
// This is an accepted ASCII-in-practice approximation: the divergence only bites on a unicode
// word/space char immediately adjacent to a placeholder token or heading, which never occurs in
// ASCII definition-docs. Do NOT "fix" this to explicit ASCII classes; the asymmetry is deliberate.
const _PLACEHOLDER = /\{\{|<!--\s*AUTHOR GUIDANCE|\bTBD\b|similar to Task\s+\w/i

function _escapeRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') }

function isUsableDraft(docText, completionSignal, expectedSignal, requiredSections = []) {
  if (!completionSignal || !expectedSignal || completionSignal !== expectedSignal) return false
  if (!docText || !docText.trim() || !docText.startsWith('---\n')) return false
  const end = docText.indexOf('\n---', 4)
  if (end === -1) return false
  const body = docText.slice(end + 4)
  if (!body.trim()) return false
  if (_PLACEHOLDER.test(docText)) return false
  for (const sec of requiredSections) {
    const m = new RegExp('^#{1,6}\\s+' + _escapeRe(sec) + '\\s*$', 'm').exec(body)
    if (!m) return false
    const rest = body.slice(m.index + m[0].length)
    const nxt = /^#{1,6}\s+/m.exec(rest)
    const segment = nxt ? rest.slice(0, nxt.index) : rest
    if (!segment.trim()) return false
  }
  return true
}

// ---------------------------------------------------------------------------
// renderRunOutcome — faithful JS twin of front_half.py:render_run_outcome (FR-7).
// Composes the front-half run-outcome envelope in-process (pure; never throws).
// For phase_records, calls the optional renderReadout(record) injected by the spine
// (exec-backed in the real run; a stub in unit tests).  Parity fixtures NEVER have
// phase_records, so renderReadout is undefined for all parity cases — the loop body
// is simply never reached.
//
// Return value: when all renderReadout calls return plain strings (or renderReadout is
// absent), the function returns a string synchronously.  When renderReadout is async
// (exec-backed in the spine), it returns a Promise<string>.  The spine always awaits it.
// FR-8 sandbox: no fs/child_process/time-funcs/rand-funcs/process/bare-global (use globalThis).
// ---------------------------------------------------------------------------

function renderRunOutcome(outcome, renderReadout) {
  const o = (outcome !== null && typeof outcome === 'object' && !Array.isArray(outcome)) ? outcome : {}
  const lines = ['# Front-half run outcome', '']
  const completed = (o.completed_phases && Array.isArray(o.completed_phases)) ? o.completed_phases : []
  lines.push('**Completed phases:** ' + (completed.length ? completed.join(', ') : '(none)'))
  lines.push('')

  const docs = (o.docs && typeof o.docs === 'object' && !Array.isArray(o.docs)) ? o.docs : {}
  if (Object.keys(docs).length > 0) {
    lines.push('**Docs:**')
    for (const k of Object.keys(docs)) {
      lines.push('- ' + k + ' → ' + docs[k])
    }
    lines.push('')
  }

  if (o.parked_phase) {
    lines.push('**Parked at:** ' + o.parked_phase + ' — ' + (o.park_reason || ''))
    lines.push('')
  }

  // Deduplicated NOTIFY defaults: key is (phase, identity || message) — distinct un-identified
  // NOTIFYs (no identity) fall back to message so they don't collapse on (phase, undefined).
  const notify = Array.isArray(o.notify) ? o.notify : []
  const deduped = []
  const seen = new Set()
  for (const n of notify) {
    if (!n || typeof n !== 'object') continue
    const key = JSON.stringify([n.phase, n.identity || n.message])
    if (seen.has(key)) continue
    seen.add(key)
    deduped.push(n)
  }
  lines.push('**NOTIFY defaults (named — owner may veto):**')
  if (deduped.length) {
    for (const n of deduped) {
      lines.push('- [' + (n.phase !== undefined ? n.phase : '?') + '] ' + (n.message !== undefined ? n.message : ''))
    }
  } else {
    lines.push('- (none)')
  }
  lines.push('')

  // Collect phase_records to embed (skip non-dict entries per oracle parity).
  const phaseRecords = Array.isArray(o.phase_records) ? o.phase_records : []
  const validRecords = phaseRecords.filter(function(pr) {
    return pr && typeof pr === 'object' && !Array.isArray(pr)
  })

  const ufr6 = o.readout_record_ok === false

  // Internal finalizer: receives per-record rendered texts (string[]) and assembles the full output.
  function _finish(renderedTexts) {
    const out = lines.slice()
    for (let i = 0; i < validRecords.length; i++) {
      const pr = validRecords[i]
      const phase = pr.phase !== undefined ? pr.phase : '?'
      out.push('## ' + phase + ' — review loop readout')
      out.push('')
      out.push(renderedTexts[i])
      out.push('')
    }
    if (ufr6) {
      out.push('> ⚠️ The durable readout record could not be written — this outcome is ' +
        'reported to the invoking session only; treat the durable copy as missing (UFR-6).')
      out.push('')
    }
    return out.join('\n').replace(/\s+$/, '') + '\n'
  }

  // If there are no phase_records or no renderReadout, compose synchronously.
  if (validRecords.length === 0 || typeof renderReadout !== 'function') {
    return _finish([])
  }

  // Call renderReadout for each valid record. If any call returns a Promise, collect all as promises.
  const results = validRecords.map(function(pr) {
    try {
      return renderReadout(pr.record !== undefined ? pr.record : null)
    } catch (_) {
      return ''
    }
  })

  // Check if any result is a thenable (async renderReadout).
  const hasPromise = results.some(function(r) {
    return r && typeof r === 'object' && typeof r.then === 'function'
  })
  if (!hasPromise) {
    // All synchronous — return string directly (parity path + sync stub tests).
    return _finish(results.map(function(r) { return typeof r === 'string' ? r : '' }))
  }

  // At least one async — return a Promise that resolves to the assembled string.
  return Promise.all(results.map(function(r) {
    if (r && typeof r === 'object' && typeof r.then === 'function') return r
    return Promise.resolve(typeof r === 'string' ? r : '')
  })).then(_finish, function() { return _finish(results.map(function() { return '' })) })
}

module.exports = { gateForTerminal, isUsableDraft, renderRunOutcome }

};

// ===== showrunner.js =====
__modules["showrunner"] = function (module, exports, require) {
// plugins/superheroes/lib/showrunner.js
// Control-flow-only native Workflow (#86 review_panel_shell.js posture): the script
// forwards decisions; every judgment is a pure JS twin (in-process) or a #86 shell.
// #115 Task 12: front-half spine rewired — reconcile/phaseStep/gateForTerminal/usableDraft/
// authorModel are now in-process JS twin calls; zero decider agents on the front-half.
const { reviewPanel } = require('./review_panel_shell.js')
const { testPilotPhase } = require('./test_pilot_phase.js')
const { io, joinPath } = require('./io_seam.js')
const phaseStepTwin = require('./phase_step.js')
const recoverTwin = require('./recover.js')
const frontHalfTwin = require('./front_half.js')
const modelTierTwin = require('./model_tier.js')
// #115 Task 16: back-half twins — CI status + PR recover (prAction already via recoverTwin above)
const ciStatusTwin = require('./ci_status.js')

// `process` is absent in the Workflow runtime sandbox (only the io seam is injected). Guard the two
// node-only globals the spine touches so a bare `process.*` reference can't crash the live run: under
// node (smokes) these forward to the real process; under the bundle they degrade safely ('.' / undefined,
// so the bundle's globalThis.SUPERHEROES_BUNDLE_FULL_RUN drives full-run, not the env selector).
function procCwd() { return (typeof process !== 'undefined' && process.cwd) ? process.cwd() : '.' }
function procEnv(name) { return (typeof process !== 'undefined' && process.env) ? process.env[name] : undefined }

const REVIEW_CODE_REVIEWERS = [
  'architecture-reviewer', 'code-reviewer', 'security-reviewer',
  'test-reviewer', 'premortem-reviewer',
]

const REVIEW_DEEP = new Set(['security-reviewer', 'architecture-reviewer'])
const ADVANCE_TERMINALS = new Set(['clean', 'clean-with-skips'])

const FIX_REPORT_SCHEMA = {
  type: 'object',
  properties: { fixed: { type: 'array' }, deferred: { type: 'array' } },
}
const CONFIG_SCHEMA = {
  type: 'object', required: ['verifyCommand'],
  properties: { verifyCommand: { type: 'string' }, tiers: { type: 'object' } },
}
const PROV_SCHEMA = { type: 'object', required: ['ok'], properties: { ok: {}, error: { type: 'string' } } }
const OK_SCHEMA = { type: 'object', required: ['ok'], properties: { ok: {} } }
// #115: the reviewer leaf RETURNS a findings[] array (no findings-<name>.json write); the panel holds
// it in memory and runs the merge/synthesis-consume/tally twins in-process.
const FINDINGS_SCHEMA = { type: 'object', required: ['findings'], properties: { findings: { type: 'array' } } }
// the genuine synthesis leaf RETURNS per-finding keep/drop verdicts (loop_synthesis.consume reads them).
const SYNTH_VERDICTS_SCHEMA = { type: 'object', required: ['verdicts'], properties: { verdicts: { type: 'array' } } }

// Build the four caller-supplied leaf wrappers, closed over the resolved model tiers (FR-7/FR-8).
// (#115: mergeAgent is gone — the merge is the in-process panel_tally.compileFindings twin.)
function reviewCodeLeaves(tiers, opts) {
  opts = opts || {}
  const withModel = (model, opts) => (model ? Object.assign({ model }, opts) : opts)
  const target = opts.target || {}
  const targetSuffix = target.worktree || target.head
    ? `\n\nTarget worktree: ${target.worktree || procCwd()}\nExpected head: ${target.head || 'current HEAD'}`
    : ''

  const reviewerAgent = async (reviewer, context, rubric, runDir, round) => {
    const model = REVIEW_DEEP.has(reviewer) ? tiers.reviewerDeep : tiers.reviewer
    const out = await agent(
      `You are the ${reviewer}. Review the built change for work-item ${context} against the ` +
      `${rubric} rubric. Return ONLY a JSON object {"findings":[...]} whose findings array lists each ` +
      `finding ({file, line, title, severity, evidence}); return {"findings":[]} if nothing to flag.${targetSuffix}`,
      withModel(model, { label: `${reviewer}:r${round}`, schema: FINDINGS_SCHEMA }))
    return (out && Array.isArray(out.findings)) ? out.findings : null   // non-array => "did not complete"
  }

  const synthesisLeaf = async (merged, context, rubric, runDir, round) => {
    const out = await agent(
      `You are the panel synthesis judge (eval/synthesis-leaf.md). For EACH merged finding below decide ` +
      `keep/drop + the rubric-justified severity (keep-on-uncertain; never decide the loop terminal). ` +
      `Return ONLY a JSON object {"verdicts":[{"id","action":"keep|drop","reason","severity"}]} — one ` +
      `verdict per merged finding, keyed by its file::normalized-title identity.\n\n` +
      `Merged findings:\n${JSON.stringify(merged)}`,
      withModel(tiers.synthesis, { label: `synthesis:r${round}`, schema: SYNTH_VERDICTS_SCHEMA }))
    return (out && Array.isArray(out.verdicts)) ? out.verdicts : []
  }

  // the code-fixer (fixStep): attempt every blocking finding, commit fixes, tag upstream-traced blockers.
  const fixStep = async (blockers, runDir) => {
    const out = await agent(
      `You are the code-fixer. For each blocking finding below, attempt a real fix and COMMIT it to ` +
      `the change under review. If a finding traces to an upstream phase (plan, tasks, or build) rather ` +
      `than the code under review, leave it unresolved and tag its originating phase. Never edit the ` +
      `review-loop machinery (refused edits surface as findings, not applied). Return ONLY a JSON object ` +
      `{"fixed": [<titles>], "deferred": [{"id", "severity", "parentOrigin"?}]}.\n\n` +
      `Blocking findings:\n${JSON.stringify(blockers)}${targetSuffix}`,
      withModel(tiers.fixer, { label: 'code-fixer', schema: FIX_REPORT_SCHEMA }))
    return out || null   // null report => the shell treats it as a fix failure -> the core decides halted
  }

  const recordDeferred = async (report, _verdict, runDir) => {
    // #115: write the deferred-set via the cheap exec dumb-pipe (not a genuine agent). record_deferred.py
    // (frozen) appends the deferred identities to deferred-set.json — the channel the in-process tally
    // reads — and prints the readout-enrichment extras (fixes + accumulated parentOrigin) to stdout.
    const out = await exec([
      `python3 plugins/superheroes/lib/record_deferred.py --run-dir ${shq(runDir)} ` +
      `--report ${shq(JSON.stringify(report || {}))}`,
    ])
    // Attach the computed extras to the fix report so #104's shared shell threads it
    // (report.extras -> tally -> readout). FR-6. Parse the cheap pipe's stdout (best-effort).
    let parsed = null
    try { parsed = JSON.parse((out && out[0] && out[0].stdout) || '') } catch (_) {}
    if (parsed && parsed.extras && report && typeof report === 'object') report.extras = parsed.extras
  }

  return { reviewerAgent, synthesisLeaf, fixStep, recordDeferred }
}

// Drive the shared loop with the code-review configuration + leaves (FR-1..FR-5, FR-7, FR-8).
async function runReviewCodePanel({ runDir, context, rubric, verifyCommand, leaves, worktree }) {
  globalThis.reviewerAgent = leaves.reviewerAgent
  globalThis.synthesisLeaf = leaves.synthesisLeaf
  globalThis.recordDeferred = leaves.recordDeferred
  return withTargetCommandPrompts(worktree, () => reviewPanel({
    reviewerSet: REVIEW_CODE_REVIEWERS,
    context, rubric, runKey: runDir, runDir,
    fixStep: leaves.fixStep,
    maxRounds: 7,
    legKind: { panel: true, code: true },
    verifyCommand,
  }))
}

module.exports = { REVIEW_CODE_REVIEWERS }

// The plan/tasks doc-review panel (the five reviewers, unchanged by #34 — spec Assumptions).
const DOC_REVIEWERS = ['architecture-reviewer', 'code-reviewer', 'security-reviewer',
                       'test-reviewer', 'premortem-reviewer']

// the three caller-supplied doc-leg leaf wrappers the #104 shell expects (panel:true). Each is a
// single leaf (no fan-out). Set as globalThis.* before reviewPanel, exactly as runReviewCodePanel does.
// #115: the reviewer RETURNS a findings[] array (the panel holds it in memory); the merge is the
// in-process panel_tally.compileFindings twin (no docMergeAgent / front_half.py merge), and the
// synthesis leaf RETURNS its keep/drop verdicts (loop_synthesis.consume reads them).
async function docReviewerAgent(reviewer, context, rubric, runDir, round) {
  const out = await agent(
    `Run the ${reviewer} review of the ${context.docType} definition-doc at ${context.docPath} ` +
    `against the ${rubric} rubric (reframed to a ${context.docType} doc). Return ONLY a JSON object ` +
    `{"findings":[{"file","line","title","severity","evidence"}]} ({"findings":[]} if none).`,
    { label: reviewer, schema: FINDINGS_SCHEMA })
  return (out && Array.isArray(out.findings)) ? out.findings : null
}
async function docSynthesisLeaf(merged, context, rubric, runDir, round) {
  const out = await agent(
    `You are the panel synthesis judge for round ${round} of the ${context.docType} doc review. ` +
    `For each merged finding below and the doc at ${context.docPath}, per the synthesis-leaf prompt ` +
    `(plugins/superheroes/eval/synthesis-leaf.md) emit one keep/drop/severity verdict (keep-on-uncertain). ` +
    `Return ONLY a JSON object {"verdicts":[{"id","action":"keep|drop","reason","severity"}]} keyed by ` +
    `each finding's file::normalized-title identity.\n\nMerged findings:\n${JSON.stringify(merged)}`,
    { label: `synthesis:r${round}`, schema: SYNTH_VERDICTS_SCHEMA })
  return (out && Array.isArray(out.verdicts)) ? out.verdicts : []
}
async function docRecordDeferred(report, _verdict, runDir) {
  // #115: write the deferred-set via the cheap exec dumb-pipe. fix-report.json is a transient hand-off
  // written first, then front_half.py record-deferred (frozen) appends the deferred identities to
  // deferred-set.json — the channel the in-process tally reads. Both run as cheap pipes.
  await io().writeFile(`${runDir}/fix-report.json`, JSON.stringify(report || {}))
  await exec([
    `python3 plugins/superheroes/lib/front_half.py record-deferred --run-dir ${shq(runDir)} ` +
    `--report ${shq(runDir + '/fix-report.json')}`,
  ])
}

// the doc-reviser fixStep: dispatch the doc-reviser leaf; return the resolved/deferred report
// (with extras.parentOrigin for a parent-traced / GATE finding), or null on failure (#104 -> halted).
async function docReviser(blockers, runDir, context) {
  const out = await agent(
    `You are the doc-reviser (fixStep) for the ${context.docType} doc at ${context.docPath}. ` +
    `Per plugins/superheroes/eval/doc-reviser-leaf.md, resolve these blocking findings with targeted ` +
    `revisions: ${JSON.stringify(blockers)}. Leave a parent-traced or GATE finding unresolved and ` +
    `name it in extras.parentOrigin. Return ONLY the report JSON ` +
    `{fixes, deferred:[{identity,severity}], extras:{parentOrigin?}}.`,
    { label: 'doc-reviser',
      schema: { type: 'object', properties: { fixes: { type: 'array' }, deferred: { type: 'array' },
                extras: { type: 'object' } } } })
  return out || null
}

// run the panel-doc leg: set the four global wrappers, then reviewPanel with the front-half wiring.
async function runReviewDocPanel({ workItem, docType, docPath, runDir }) {
  const context = { workItem, docType, docPath }
  globalThis.reviewerAgent = docReviewerAgent
  globalThis.synthesisLeaf = docSynthesisLeaf
  globalThis.recordDeferred = docRecordDeferred
  return reviewPanel({
    reviewerSet: DOC_REVIEWERS, context, rubric: 'review-base', runKey: runDir, runDir,
    fixStep: (blockers, rd) => docReviser(blockers, rd, context),
    maxRounds: 7, legKind: { panel: true, code: false }, verifyCommand: 'none' })
}

module.exports.DOC_REVIEWERS = DOC_REVIEWERS
module.exports.runReviewDocPanel = runReviewDocPanel

function docPathFor(workItem, doc) { return `docs/superheroes/${workItem}/${doc}.md` }
function runDirFor(workItem, phase) { return `/tmp/showrunner-${workItem}-${phase}` }

// the produce phase: author the doc author-only (resume a usable draft; re-produce otherwise).
// #115 Task 12: usableDraft uses exec+JS twin (front_half.isUsableDraft, no LLM agent).
// authorModel is the in-process JS twin (model_tier.resolveModel, no agent dispatch).
// The --write-marker stamp is FOLDED into the author agent (FR-4 fold): the author's prompt
// instructs it to run front_half_usable.py --write-marker after authoring the doc, so there is
// no separate cmdRunner call — the author leaf handles its own completion stamp.
// Layer 2b: bounded repair loop (N=2 retries, 3 total attempts). On a failed post-check the
// author is re-dispatched with a TARGETED gap hint derived from the --emit-signals why-signal
// (missing_sections + placeholder). Only parks (confidence:'low') after all attempts exhausted.
// NOTIFY defaults are accumulated across all attempts (not dropped on a failed attempt).
const _PRODUCE_MAX_RETRIES = 2   // N=2 retries -> 3 total author attempts
async function producePhase(phase, workItem) {
  const doc = phase                                    // 'plan' | 'tasks'
  // resume vs re-produce: a usable draft (content-bound completion signal + complete content) is kept.
  const draft = await usableDraft(workItem, doc)
  if (draft.usable) return { confidence: 'high', assumptions: [] } // FR-8 resume — do not re-author
  const model = authorModel()
  // _authorPrompt: builds the author dispatch prompt. On a retry, appends a targeted gap hint so
  // the author knows precisely what to fix (Layer 2b). The hint is derived from the why-signal
  // (missing_sections + placeholder) returned by usableDraft on the previous failed check.
  // FR-8 sandbox: no banned tokens in this function body.
  function _authorPrompt(gapSignal) {
    const base =
      `You are the author-only produce leaf (plugins/superheroes/eval/produce-leaf.md). Author the ` +
      `${doc} definition-doc for work-item ${workItem} from its approved parent, every section ` +
      `non-empty, no placeholder. After writing the doc, run the following command to stamp the ` +
      `content-bound completion marker (deterministic — do NOT skip it):\n\n` +
      selfContained(`python3 plugins/superheroes/lib/front_half_usable.py --work-item ${shq(workItem)} ` +
      `--doc ${shq(doc)} --write-marker --root "$(git rev-parse --show-toplevel)"`) + `\n\n` +
      `Do NOT run review or record the review gate. Return ` +
      `{ status, notify } where notify is an array of any NOTIFY-class defaults you took, each ` +
      `{ identity, message }.`
    if (!gapSignal) return base
    const hints = []
    const missing = (gapSignal.missing_sections && Array.isArray(gapSignal.missing_sections))
      ? gapSignal.missing_sections : []
    if (missing.length > 0) {
      hints.push(
        `Your previous draft was rejected: the following required sections must be ## markdown headings ` +
        `with non-empty content: ${missing.join(', ')}. ` +
        `Use "## ${missing[0]}" (a heading), NOT "**${missing[0]}:**" (bold inline label).`)
    }
    if (gapSignal.placeholder) {
      hints.push(`A placeholder token was found (e.g. TBD, {{…}}, or "similar to Task N") — remove it.`)
    }
    if (hints.length === 0) return base
    return base + `\n\nIMPORTANT (retry): ` + hints.join(' ')
  }
  // Bounded author+repair loop: up to _PRODUCE_MAX_RETRIES retries (3 total attempts).
  // lastSignal carries the why-signal from the previous failed check for the gap hint.
  let lastSignal = null
  for (let attempt = 0; attempt <= _PRODUCE_MAX_RETRIES; attempt++) {
    // FR-4 fold: the author leaf writes its own doc + stamps the completion marker (--write-marker) +
    // returns notify. Single-author docs are NOT return-don't-write (the author IS the side effect's input).
    const authored = await agent(
      _authorPrompt(attempt > 0 ? lastSignal : null),
      { label: `produce-${doc}`, model,
        schema: { type: 'object', properties: { status: {}, notify: { type: 'array' } } } })
    if (authored == null) {
      return { confidence: 'low', assumptions: [`produce step failed for ${doc}`] } // UFR-4
    }
    // surface any produce-phase NOTIFY default in the durable ledger the boundary reads (UFR-2): a
    // produce phase has no #104 loop record to ride, so it is named via the ledger, not the extras seam.
    // NOTIFY defaults are recorded on EVERY attempt (not dropped on a failed check — UFR-2).
    if (authored.notify && authored.notify.length) {
      const ok = await appendNotify(workItem, authored.notify.map(
        (n) => ({ phase: doc, identity: n && n.identity, message: n && n.message })))
      if (!ok) {
        // a NOTIFY default that can't be durably recorded must NOT be silently lost (UFR-2): park and
        // name it. No marker is stamped yet, so a resume re-produces and retries the NOTIFY.
        return { confidence: 'low', assumptions: ['produce NOTIFY default not durably recorded: ' +
                 authored.notify.map((n) => (n && n.message) || '').join('; ')] }
      }
    }
    // Verify the author actually stamped the marker (UFR-4 guard). usableDraft re-reads via exec+twin.
    // The why-signal (missing_sections, placeholder) is preserved for the next retry's gap hint.
    const after = await usableDraft(workItem, doc)
    if (after.usable) return { confidence: 'high', assumptions: [] }
    // Store the gap signal for the next attempt's targeted hint.
    lastSignal = after
    // If more retries remain, loop back and re-dispatch the author with the gap hint.
    // On the last attempt, fall through to park.
  }
  // All attempts exhausted — park low-confidence, naming the persistent gap.
  const gapDesc = (lastSignal && lastSignal.missing_sections && lastSignal.missing_sections.length)
    ? `missing ## headings: ${lastSignal.missing_sections.join(', ')}`
    : (lastSignal && lastSignal.placeholder ? 'placeholder token present' : 'content check failed')
  return { confidence: 'low',
    assumptions: [`produce step yielded no usable ${doc} draft after ${_PRODUCE_MAX_RETRIES + 1} attempts: ${gapDesc}`] }
}

// the review phase: idempotent passed-gate skip, else run the panel-doc leg and map terminal->gate.
// #115 Task 12: gateForTerminal is now the in-process JS twin; the gate write goes through
// persistPhase (one exec: set-gate + journal + checkpoint) — not a cmdRunner agent dispatch.
async function reviewDocPhase(doc, workItem) {
  const existing = await readGate(workItem, doc)
  if (existing === 'passed') {
    // cursor-lost re-entry guard (gate written, recordCursor failed): never re-run the panel and
    // risk overwriting a correct passed (FR-8 passed-gate skip).
    return { phaseResult: { confidence: 'high', assumptions: [] }, gate: 'passed' }
  }
  const runDir = runDirFor(workItem, `review-${doc}`)
  const verdict = await runReviewDocPanel({ workItem, docType: doc, docPath: docPathFor(workItem, doc), runDir })
  // persist the #104 terminal record so the front-half boundary can embed its readout (FR-7).
  try { await io().writeFile(`${runDir}/terminal-record.json`, JSON.stringify(verdict || {})) } catch (_) {}
  // gateForTerminal is the in-process JS twin (no agent dispatch).
  const gate = gateForTerminal(verdict && verdict.terminal)
  // Record gate + journal + checkpoint in one exec call (persistPhase, FR-4 persist order).
  const sideEffectCmd =
    `python3 plugins/superheroes/lib/definition_doc.py set-gate --doc ${shq(doc)} ` +
    `--work-item ${shq(workItem)} --review ${shq(gate)} --root "$(git rev-parse --show-toplevel)"`
  const pr = await persistPhase(workItem, {
    sideEffectCmd,
    journalPayload: { phase: `review-${doc}`, gate, confidence: 'high', assumptions: [] },
    step: -1,   // placeholder: the real step is written by recordCursor in runPhases; -1 signals review-doc context
    phase: `review-${doc}`,
  })
  if (!pr.ok) {
    // a failed durable gate write must NOT advance on un-recorded state (UFR-5) — park low-confidence,
    // mirroring reviewCodePhase's provenance-write guard.
    return { phaseResult: { confidence: 'low', assumptions: [`gate write did not record for ${doc}`] }, gate }
  }
  return { phaseResult: { confidence: 'high', assumptions: [] }, gate }
}

// gateForTerminal: pure in-process JS twin. No agent dispatch.
function gateForTerminal(terminal) {
  return frontHalfTwin.gateForTerminal(terminal || 'unknown')
}

// usableDraft: exec runs front_half_usable.py --emit-signals, which computes the verdict
// Python-side at the IO boundary (calls front_half.is_usable_draft) and returns a small
// {usable, recorded, expected, missing_sections, placeholder} signal — the large doc text
// never crosses the cheapest-model pipe (live-surfaced large-payload-transport limit).
// The frontHalfTwin.isUsableDraft JS twin stays for parity testing only; it is no longer
// called here on the live doc text.
// Layer 2a: the why-signal fields (missing_sections, placeholder) are forwarded so the
// produce repair loop (producePhase) can craft a targeted gap hint for re-prompting.
async function usableDraft(workItem, doc) {
  const results = await exec([
    `python3 plugins/superheroes/lib/front_half_usable.py --work-item ${shq(workItem)} ` +
    `--doc ${shq(doc)} --root "$(git rev-parse --show-toplevel)" --emit-signals`,
  ])
  let signals = null
  try { signals = JSON.parse((results[0] && results[0].stdout) || '') } catch (_) {}
  if (!signals) return { usable: false }   // IO failure -> fail closed (re-produce)
  return {
    usable: !!signals.usable,
    missing_sections: Array.isArray(signals.missing_sections) ? signals.missing_sections : [],
    placeholder: !!signals.placeholder,
  }
}

// authorModel: pure in-process JS twin. Reads overrides from globalThis.__SR_OVERRIDES (set by
// Task 17 startup pipe; absent in test/throwaway runs -> null -> DEFAULT_TIERS.author = 'opus').
function authorModel() {
  const overrides = (typeof globalThis !== 'undefined' && globalThis.__SR_OVERRIDES) || null
  return modelTierTwin.resolveModel('author', overrides, null)
}
// the durable per-work-item NOTIFY ledger (under the gitignored docs dir — run-local state).
function notifyLedgerFor(workItem) { return `docs/superheroes/${workItem}/.notify.json` }
// appendNotify: IO accumulator write via exec (not cmdRunner). Returns false on failed durable write.
async function appendNotify(workItem, entries) {
  const results = await exec([
    `python3 plugins/superheroes/lib/front_half.py append-notify ` +
    `--ledger ${shq(notifyLedgerFor(workItem))} --entries ${shq(JSON.stringify(entries || []))}`,
  ])
  let out = null
  try { out = JSON.parse((results[0] && results[0].stdout) || '') } catch (_) {}
  return !!(out && out.ok)   // false on a failed durable write — the caller must not silently lose it
}

module.exports.producePhase = producePhase
module.exports.reviewDocPhase = reviewDocPhase
module.exports.notifyLedgerFor = notifyLedgerFor

// FR-7: compose the front-half run-outcome envelope (in-process via frontHalfTwin.renderRunOutcome)
// and return a parked result. Reads best-effort per-phase terminal records + the durable NOTIFY ledger.
// The ENVELOPE judgment is in-process (no front_half.py render-outcome agent); only the per-phase
// loop_readout RENDER stays an exec leaf (loop_readout.py --record <path>).
// #115 Task 18: rewired from 1 decider agent to 0 — envelope is the twin, readout stays exec.
async function frontHalfBoundary(workItem) {
  // The io() seam is async (it shares one contract with the bundle's Promise-returning leaf-bash io),
  // so await every read BEFORE building the outcome literal — embedding an un-awaited Promise would
  // serialize as "{}" and silently drop the durable readout records (the bug this fix class closes).
  const notify = await io().readJson(notifyLedgerFor(workItem), [])
  const planRec = await io().readJson(`${runDirFor(workItem, 'review-plan')}/terminal-record.json`, null)
  const tasksRec = await io().readJson(`${runDirFor(workItem, 'review-tasks')}/terminal-record.json`, null)
  const outcome = {
    completed_phases: ['plan', 'review-plan', 'tasks', 'review-tasks'],
    docs: { plan: docPathFor(workItem, 'plan'), tasks: docPathFor(workItem, 'tasks') },
    notify,
    phase_records: [
      { phase: 'review-plan', record: planRec },
      { phase: 'review-tasks', record: tasksRec },
    ],
    readout_record_ok: true,
  }
  // recordOk guards UFR-6: if we cannot write the durable readout records, flag it in the reason.
  // (The readout records live in the per-phase run dirs and are written by renderAndPostReadout earlier;
  // the outcome JSON written here is the durable ENVELOPE artifact — a missing write flags UFR-6.)
  const outPath = `/tmp/showrunner-${workItem}-fronthalf-outcome.json`
  let recordOk = true
  try { await io().writeFile(outPath, JSON.stringify(outcome)) } catch (_) { recordOk = false }

  // exec-backed renderReadout: writes the record to a temp file and execs loop_readout.py --record.
  // Mirrors how renderAndPostReadout runs loop_readout.py (line ~896). Returns the stdout text.
  // Used only when recordOk (the write seam is available); if recordOk is false the loop body is
  // skipped (phase_records still embeds headers with no readout text — tolerable since UFR-6 fires).
  async function renderReadout(record) {
    const recPath = `/tmp/showrunner-${workItem}-fronthalf-readout-tmp.json`
    try { await io().writeFile(recPath, JSON.stringify(record || {})) } catch (_) { return '' }
    const text = await agent(
      `Run exactly this and return ONLY its stdout, unchanged:\n\n` +
      selfContained(`python3 plugins/superheroes/lib/loop_readout.py --record ${shq(recPath)}`),
      { label: 'readout' })
    return typeof text === 'string' ? text : ''
  }

  // In-process envelope composition (no agent for the judgment — only the per-phase readout is exec).
  // If the durable outcome JSON could not be written, skip phase_records embed (no readout seam) and
  // surface UFR-6 in the fallback reason instead; the twin still composes the envelope shell.
  const rendered = recordOk
    ? frontHalfTwin.renderRunOutcome(outcome, renderReadout)
    : frontHalfTwin.renderRunOutcome({ ...outcome, phase_records: [], readout_record_ok: false })

  // rendered is a Promise when renderReadout is async (it is, above) — await it.
  const text = await rendered

  const reason = (typeof text === 'string' && text.trim())
    ? text
    : recordOk
      ? 'front-half complete: plan and tasks gated — parked at the front-half boundary, awaiting owner'
      : '⚠️ front-half complete (plan and tasks gated) but the run-outcome record could not be written ' +
        '— treat the durable readout as missing (UFR-6); awaiting owner'
  return { outcome: 'parked', phase: 'front-half-boundary', reason }
}

module.exports.frontHalfBoundary = frontHalfBoundary

function shq(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }
function safeRunKey(s) { return String(s).replace(/[^A-Za-z0-9_.-]+/g, '-').slice(0, 120) || 'target' }

// selfContained: FR-5 — prefix a command with `cd <root> && ` so the leaf always runs from the
// correct repo root, regardless of the haiku leaf's cwd. Opt-in: only applies when globalThis.__SR_ROOT
// is set (threaded from args.root in the ENTRY). Commands already starting with `cd ` (e.g. the
// build-worktree inWorktree commands) are left untouched — the startsWith guard prevents double-cd.
// When __SR_ROOT is unset (most smokes, back-half runs not yet opted in) behavior is unchanged.
function selfContained(cmd) {
  var root = (typeof globalThis !== 'undefined' && globalThis.__SR_ROOT) ? String(globalThis.__SR_ROOT) : null
  if (!root) return cmd
  var trimmed = String(cmd).trimLeft ? String(cmd).trimLeft() : String(cmd).replace(/^\s+/, '')
  if (trimmed.startsWith('cd ')) return cmd   // already rooted (inWorktree or similar) — leave alone
  return 'cd ' + shq(root) + ' && ' + cmd
}

// cheapestModel: resolves the mechanical (cheapest) tier once and caches it. The `mechanical` tier
// is unconditionally `'haiku'` per DEFAULT_TIERS; resolving through model_tier.js keeps the twin
// parity contract intact and allows future overrides without changing the spine.
let _cheapestModelCache = null
function cheapestModel() {
  if (_cheapestModelCache === null) {
    _cheapestModelCache = require('./model_tier.js').DEFAULT_TIERS.mechanical
  }
  return _cheapestModelCache
}

// _parseExecResult: parse the leaf agent's response into a [{index,ok,stdout}] array.
// Handles all response shapes the leaf may produce:
//   1. Array (stub/pass-through) — returned as-is.
//   2. String — robust extraction tried in order:
//      (a) First fenced block ANYWHERE in the string (non-anchored match for prose-prefixed output).
//      (b) Whole trimmed string as-is (covers clean bare JSON array).
//      For each candidate, try JSON.parse directly; if that fails, slice from first '[' to last ']'
//      and JSON.parse that slice (handles prose before/after a bare JSON array).
//      The first candidate that yields an Array is returned.
//   3. Anything else / all candidates fail — synthetic per-command failure array (fail-closed).
// n = commands.length; used only for synthetic failure array sizing (must be >= 1).
function _parseExecResult(out, n) {
  var count = (n && n > 0) ? n : 1
  if (Array.isArray(out)) return out
  if (typeof out === 'string') {
    var trimmed = out.trim()
    // Build candidates to try, in priority order:
    // (a) content of the FIRST fenced block found anywhere (handles prose-prefixed fences).
    var candidates = []
    var fenceMatch = trimmed.match(/```(?:[a-zA-Z0-9]+)?\s*([\s\S]*?)```/)
    if (fenceMatch) candidates.push(fenceMatch[1].trim())
    // (b) whole trimmed string (handles clean bare JSON or prose-around-JSON via bracket slice).
    candidates.push(trimmed)
    for (var ci = 0; ci < candidates.length; ci++) {
      var candidate = candidates[ci]
      // Try direct parse first.
      try {
        var parsed = JSON.parse(candidate)
        if (Array.isArray(parsed)) return parsed
      } catch (_e1) { /* try bracket-slice fallback */ }
      // Slice from first '[' to last ']' to handle prose around a bare JSON array.
      var firstBracket = candidate.indexOf('[')
      var lastBracket = candidate.lastIndexOf(']')
      if (firstBracket >= 0 && lastBracket > firstBracket) {
        var slice = candidate.slice(firstBracket, lastBracket + 1)
        try {
          var sliced = JSON.parse(slice)
          if (Array.isArray(sliced)) return sliced
        } catch (_e2) { /* try next candidate */ }
      }
    }
  }
  // Synthetic per-command failure: callers can detect the failure and surface it clearly.
  var failures = []
  for (var i = 0; i < count; i++) {
    failures.push({ index: i, ok: false, stdout: 'exec: could not parse leaf result' })
  }
  return failures
}

// exec: the dumb-pipe executor. Dispatches ONE globalThis.agent whose prompt lists all fully-formed
// commands and asks the leaf to run each and return a JSON array of {index, ok, stdout}.
// The model is UNCONDITIONALLY forced to cheapestModel() — overriding __SR_LEAF_MODEL or any
// caller-supplied opts.model. This is a side-effect executor, not a genuine-LLM agent.
// FR-8 sandbox-safe: no fs, no child_process, no time/random globals, no process/bare-global refs.
async function exec(commands, opts) {
  var cmds = commands || []
  const cmdList = cmds.map(function(c, i) { return (i + 1) + '. ' + selfContained(c) }).join('\n')
  const prompt =
    'Run each of the following commands in order using the Bash tool. ' +
    'Return ONLY a raw JSON array and NOTHING else — no prose, no explanation, no markdown fences; ' +
    'your entire response must be valid for JSON.parse. ' +
    'Each element: {"index":<0-based>,"ok":<true|false>,"stdout":<string>}.\n\n' +
    cmdList
  const o = Object.assign({}, opts || {}, { model: cheapestModel(), label: 'exec' })
  const out = await globalThis.agent(prompt, o)
  return _parseExecResult(out, cmds.length)
}

// persistPhase: batches side-effect -> journal_entry -> checkpoint_entry into one exec call.
// Persist order (FR-4): side-effect first (when present), then journal, then checkpoint (cursor last).
// Every interpolated non-constant arg is shq()-quoted.
// Returns {ok: boolean} — ok is false if any command in the batch reported failure.
async function persistPhase(workItem, opts) {
  opts = opts || {}
  const sideEffectCmd = opts.sideEffectCmd || null
  const journalPayload = opts.journalPayload || {}
  const step = opts.step
  const phase = opts.phase

  const journalCmd =
    'python3 plugins/superheroes/lib/journal_entry.py ' +
    '--work-item ' + shq(workItem) + ' ' +
    '--payload ' + shq(JSON.stringify(journalPayload))

  const checkpointCmd =
    'python3 plugins/superheroes/lib/checkpoint_entry.py ' +
    '--work-item ' + shq(workItem) + ' ' +
    '--step ' + shq(String(step)) + ' ' +
    '--phase ' + shq(phase)

  const commands = sideEffectCmd
    ? [sideEffectCmd, journalCmd, checkpointCmd]
    : [journalCmd, checkpointCmd]

  const results = await exec(commands)
  return { ok: results.every(function(r) { return r && r.ok }) }
}

function inWorktree(cmd, worktree) {
  return worktree ? `cd ${shq(worktree)} && ${cmd}` : cmd
}
function targetCommandPrompt(prompt, worktree) {
  if (!worktree || typeof prompt !== 'string') return prompt
  if (!prompt.startsWith('Run exactly this')) return prompt
  // The cmdRunner shape is "Run exactly this …:\n\n<cmd>"; split on the FIRST blank-line boundary
  // so a multi-line command (which may itself contain a blank line) is wrapped whole, not just its tail.
  const idx = prompt.indexOf('\n\n')
  if (idx < 0) return prompt
  const prefix = prompt.slice(0, idx + 2)
  const cmd = prompt.slice(idx + 2)
  if (!cmd.trim() || cmd.trim().startsWith('cd ')) return prompt
  return `${prefix}${inWorktree(cmd, worktree)}`
}
async function withTargetCommandPrompts(worktree, fn) {
  if (!worktree) return fn()
  const originalAgent = globalThis.agent
  globalThis.agent = async (prompt, opts) => originalAgent(targetCommandPrompt(prompt, worktree), opts)
  try {
    return await fn()
  } finally {
    globalThis.agent = originalAgent
  }
}

// JS<->Python bridge: run a lib command in a leaf, return its stdout JSON (schema-validated).
async function cmdRunner(cmd, { schema }) {
  // The command prints ONE JSON object to stdout. The leaf must map each top-level key of that
  // object to the SAME-named StructuredOutput field — NOT stuff the whole JSON text into one field
  // (a live-only derailment: that is schema-valid-but-wrong, e.g. action="{...the whole blob...}",
  // which then mis-routes the deciders). Spell the mapping out so the leaf can't collapse it.
  return agent(
    `Use the Bash tool to run exactly this command. It prints ONE JSON object to stdout. Return that ` +
    `object via StructuredOutput by copying each of its top-level keys to the same-named output field, ` +
    `values exactly as printed. Do NOT put the whole JSON into a single field, do NOT stringify or nest ` +
    `it, and do NOT add commentary or extra fields:\n\n${cmd}`,
    { label: 'lib', schema },
  )
}

// Reconcile-from-store: exec gathers the world snapshot via recover_entry.py --snapshot
// (IO: store, enforcer, lease, checkpoint, world read), then the JS twin decides (pure, in-process).
// generation is threaded from the Python snapshot (UFR-10).
async function reconcile(workItem) {
  const results = await exec([
    `python3 plugins/superheroes/lib/recover_entry.py --work-item ${shq(workItem)} --snapshot`,
  ])
  let snap = null
  try { snap = JSON.parse((results[0] && results[0].stdout) || '') } catch (_) {}
  if (!snap) {
    // A failed/empty snapshot (IO error, store unusable before lease) -> fail closed.
    return { action: 'park_gate', reason: 'recover_entry snapshot failed (IO error)', generation: null }
  }
  // recover_entry emits an early_park when the cursor guard triggers (before snapshot).
  // In that case the snapshot fields are absent and {action, reason, generation} come directly.
  if (snap.action) return snap   // early park (cursor_gate or store/enforcer/lease failure)
  const decision = recoverTwin.reconcile(snap.checkpoint, snap.world)
  return Object.assign({}, decision, { generation: snap.generation })
}

async function showrunner({ workItem }) {
  // Progress-group the pre-loop leaves (reconcile / spec-gate / startup) under 'startup'; runPhases
  // re-stamps this per phase. Read by the bundle's agent wrapper (globalThis.__SR_PHASE).
  if (typeof globalThis !== 'undefined') globalThis.__SR_PHASE = 'startup'
  const r = await reconcile(workItem)
  if (r.action === 'park_gate' || r.action === 'gate') {
    return { outcome: 'parked', phase: 'reconcile', reason: r.reason || r.action }
  }
  // UFR-1: refuse to run if the spec hasn't been approved.
  const specGate = await readGate(workItem, 'spec')
  const startup = await phaseStep({ confidence: 'high', assumptions: [] }, specGate)
  if (startup.action !== 'proceed') {
    return { outcome: 'parked', phase: 'startup', reason: startup.reason }
  }
  // Task 17: load model-tier overrides once at startup from the review-crew profile. The Python script
  // returns a {role:model} JSON map (or {} when the profile is absent/unreadable — the safe degenerate
  // path). We pass no --profile here (→ load_overrides(None) → {}); a throwaway run has no profile, so
  // {} is correct there; production uses the session-wide profile read elsewhere. Fail-safe: any exec
  // error or bad JSON yields {} so resolveModel falls back to DEFAULT_TIERS — startup never crashes.
  const _ovRes = await exec(['python3 plugins/superheroes/lib/model_tier_overrides.py'])
  let _ovMap = {}
  try { const _p = (_ovRes[0] && _ovRes[0].stdout) || ''; _ovMap = JSON.parse(_p) } catch (_) {}
  if (typeof globalThis !== 'undefined') {
    globalThis.__SR_OVERRIDES = (_ovMap && typeof _ovMap === 'object' && !Array.isArray(_ovMap)) ? _ovMap : {}
  }
  // 'continue' (from_step) or 'world_derive' (from_step 0) -> run the phase loop (Task 8).
  // lastGoodStep = the last *completed* phase index; resume at the next one (no re-run, FR-3).
  const fromStep = r.action === 'continue' && r.from_step != null ? Number(r.from_step) + 1 : 0
  // UFR-10 (#107): thread the lease generation recover_entry acquired into the workhorse build phase,
  // so the build can fence (renew-then-fence) at every branch-mutating boundary.
  const deps = { gateRead: gateReadFor(workItem), generation: r.generation }
  // FR-7 (#108)/FR-4 (#102)/Task-13a (#115): native front-half wiring. Three opt-in selectors
  // share the native authoring deps but differ on the boundary park:
  //   - env SUPERHEROES_FRONT_HALF=native: direct-node/smoke path (procEnv); keeps boundary park.
  //   - globalThis.SUPERHEROES_FRONT_HALF_NATIVE: Workflow-sandbox path (set by the ENTRY from
  //     args.frontHalf==='native'); procEnv is unavailable in the sandbox (FR-8), so the ENTRY
  //     injects this globalThis flag instead.
  //   - SUPERHEROES_BUNDLE_FULL_RUN true (preamble default + full-run ENTRY): no boundary park,
  //     proceeds into the back-half.
  const fullRun = !!globalThis.SUPERHEROES_BUNDLE_FULL_RUN
  const frontHalfNative = procEnv('SUPERHEROES_FRONT_HALF') === 'native' || !!globalThis.SUPERHEROES_FRONT_HALF_NATIVE
  if (frontHalfNative || fullRun) {
    deps.produce = producePhase                  // plan / tasks authoring (author-only)
    deps.reviewDoc = reviewDocPhase              // review-plan / review-tasks -> panel-doc leg
    if (!fullRun) deps.frontHalfBoundary = frontHalfBoundary   // front-half-only keeps the boundary park
  }
  return runPhases(workItem, fromStep, deps)
}

// readGate: IO read via exec (definition-doc on disk). A missing/malformed doc returns the
// 'unreadable' sentinel that phaseStep twin maps to park_unexpected_gate.
async function readGate(workItem, doc) {
  try {
    const results = await exec([
      `python3 plugins/superheroes/lib/definition_doc.py read-gate --doc ${shq(doc)} ` +
      `--work-item ${shq(workItem)} --root "$(git rev-parse --show-toplevel)" --json`,
    ])
    let out = null
    try { out = JSON.parse((results[0] && results[0].stdout) || '') } catch (_) {}
    return (out && out.review) || 'unreadable'
  } catch (_) {
    return 'unreadable'
  }
}

const REVIEWED = new Set(['review-plan', 'review-tasks', 'review-code'])
function gateReadFor(workItem) {
  return async (phase) => {
    if (!REVIEWED.has(phase)) return null            // authoring phase: no review gate
    if (phase === 'review-code') return null          // review-code's gate = the reviewPanel verdict (Task 10)
    const doc = phase === 'review-plan' ? 'plan' : 'tasks'
    return readGate(workItem, doc)
  }
}

const PHASES = ['plan', 'review-plan', 'tasks', 'review-tasks', 'workhorse',
                'review-code', 'draft-PR', 'test-pilot', 'mark-ready', 'ship']

// phaseStep: pure in-process JS twin (phase_step.decide). No agent dispatch.
function phaseStep(phaseResult, gate) {
  return phaseStepTwin.decide(phaseResult, gate)
}

async function defaultTestPilotPhase(workItem, generation) {
  return testPilotPhase(workItem, generation, testPilotDeps(workItem, generation))
}

function testPilotDeps(workItem, generation) {
  const runDir = joinPath(io().tmpdir(), `showrunner-${workItem}-test-pilot`)
  // writeJson is async (the io() seam is async — see io_seam.js) and lazily ensures runDir, so every
  // call site must await it. Lazy mkdirp keeps the dir-create on the same awaited path as the write.
  const writeJson = async (name, value) => {
    const p = joinPath(runDir, `${name}.json`)
    await io().mkdirp(runDir)
    await io().writeFile(p, JSON.stringify(value || {}))
    return p
  }
  const jsonCommand = (cmd, schema) => cmdRunner(cmd, { schema: schema || { type: 'object' } })
  const cli = (cmd, schema) => jsonCommand(cmd, schema || { type: 'object' })
  const keyFor = (branch) => encodeURIComponent(branch || workItem).replace(/~/g, '%7E')

  return {
    resolveContext: async () => cli(
      `python3 plugins/superheroes/lib/test_pilot_context_cli.py resolve ` +
      `--work-item ${shq(workItem)}${generation != null ? ` --generation ${shq(String(generation))}` : ''}`,
      { type: 'object' }),

    decideApplicability: async (context) => {
      const diff = await writeJson('applicability-diff', context.diff || {})
      const detectors = await writeJson('applicability-detectors', context.detectors || {})
      const profile = await writeJson('applicability-profile', context.profile || {})
      return cli(
        `python3 plugins/superheroes/lib/test_pilot_applicability_cli.py decide ` +
        `--diff-json ${shq(diff)} --detectors-json ${shq(detectors)} --profile-json ${shq(profile)}`,
        { type: 'object', required: ['verdict'] })
    },

    derivePlan: async (context) => agent(
      `You are the test-pilot plan leaf for work-item ${workItem}. Derive a browser test plan for ` +
      `the current branch head ${context.head}. Return ONLY JSON ` +
      `{"records":[{"branch":${JSON.stringify(context.branch)},"steps":[{"id","instruction","expected","scenarioIds":[]}]}],` +
      `"coverageRationale":"..."}. Use concise stable step ids; include scenarioIds when seed scenarios are needed.`,
      { label: 'test-pilot-plan', schema: { type: 'object', required: ['records'], properties: { records: { type: 'array' } } } }),

    preparePlanRecords: async (plan) => ({ action: 'ready', records: plan.records || [] }),

    prepareArtifacts: async ({ plan, records, context }) => {
      const pr = context.pr && context.pr.number
      if (!pr) return { action: 'park', reason: 'test-pilot artifacts require a draft PR number' }
      const planPath = await writeJson('plan-artifact', { key: keyFor(context.branch), records })
      const resultsPath = await writeJson('results-artifact-initial', { key: keyFor(context.branch), records: [], coverageRationale: plan.coverageRationale })
      return cli(
        `python3 plugins/superheroes/lib/test_pilot_artifacts_cli.py ensure ` +
        `--plan-json ${shq(planPath)} --results-json ${shq(resultsPath)} --pr ${shq(String(pr))} --key ${shq(keyFor(context.branch))}`,
        { type: 'object' })
    },

    resolveServer: async (context) => {
      const profile = await writeJson('server-profile', context.profile || {})
      const detection = await writeJson('server-detection', context.detectors || {})
      return cli(
        `python3 plugins/superheroes/lib/test_pilot_server_config_cli.py resolve ` +
        `--profile-json ${shq(profile)} --detection-json ${shq(detection)} --work-item ${shq(workItem)}`,
        { type: 'object' })
    },

    withManagedServer: async (serverContext, run) => {
      const launchPath = await writeJson('server-launch-context', serverContext)
      const launched = await cli(
        `python3 plugins/superheroes/lib/test_pilot_server_config_cli.py launch ` +
        `--context-json ${shq(launchPath)}`,
        { type: 'object' })
      if (!launched || launched.verdict === 'park' || launched.action === 'park' || launched.ok === false) {
        return launched
      }
      try {
        const outcome = await run(launched)
        const contextPath = await writeJson('server-finish-context', launched)
        const outcomePath = await writeJson('server-finish-outcome', outcome || {})
        return cli(
          `python3 plugins/superheroes/lib/test_pilot_server_config_cli.py finish ` +
          `--context-json ${shq(contextPath)} --outcome-json ${shq(outcomePath)}`,
          { type: 'object' })
      } catch (err) {
        const contextPath = await writeJson('server-finish-context', launched)
        const outcomePath = await writeJson('server-finish-outcome', { action: 'exception', reason: err && err.message ? err.message : String(err) })
        await cli(
          `python3 plugins/superheroes/lib/test_pilot_server_config_cli.py finish ` +
          `--context-json ${shq(contextPath)} --outcome-json ${shq(outcomePath)}`,
          { type: 'object' })
        throw err
      }
    },

    seedRecords: async (records) => {
      const recordsPath = await writeJson('seed-records', records)
      return cli(
        `python3 plugins/superheroes/lib/test_pilot_seed_cli.py prepare --records-json ${shq(recordsPath)}`,
        { type: 'object' })
    },

    runBrowserPass: async (browserContext) => agent(
      `Run the test-pilot browser pass for work-item ${workItem}. Stay within baseUrl/allowedOrigins and return ONLY JSON ` +
      `{"source":"browser","baseUrl":${JSON.stringify(browserContext.baseUrl)},"steps":[{"id","status","notes","browserExecuted":true,"failureType"?,"summary"?}]}. ` +
      `Browser context: ${JSON.stringify(browserContext)}`,
      { label: 'test-pilot-browser', schema: { type: 'object' } }),

    aggregateResults: async (rawResults) => {
      const raw = await writeJson('browser-raw', rawResults)
      return cli(
        `python3 plugins/superheroes/lib/test_pilot_results_cli.py aggregate --raw-json ${shq(raw)}`,
        { type: 'object' })
    },

    budgetCheck: async (_phase, payload) => {
      const counts = await writeJson('budget-counts', payload && payload.counts ? payload.counts : {
        browserPasses: payload && typeof payload.browserPasses === 'number'
          ? payload.browserPasses
          : (payload && payload.rerunScope ? 1 : 0),
        browserFixBatches: payload && payload.fixBatchHistory ? payload.fixBatchHistory.length : 0,
      })
      const out = await cli(
        `python3 plugins/superheroes/lib/test_pilot_budget_cli.py decide --counts-json ${shq(counts)}`,
        { type: 'object' })
      return out.action === 'within_budget' ? { ok: true } : { ok: false, reason: out.reason || 'test-pilot budget exceeded' }
    },

    retryDecide: async (passResult, history, changedFiles, dependencyMap) => {
      const passPath = await writeJson('retry-pass', passResult)
      const histPath = await writeJson('retry-history', history || [])
      const depPath = dependencyMap ? await writeJson('retry-deps', dependencyMap) : null
      const changed = (changedFiles || []).map((f) => ` --changed-file ${shq(f)}`).join('')
      return cli(
        `python3 plugins/superheroes/lib/test_pilot_retry_cli.py decide --pass-json ${shq(passPath)} ` +
        `--history-json ${shq(histPath)}${changed}${depPath ? ` --dependency-json ${shq(depPath)}` : ''}`,
        { type: 'object' })
    },

    dispatchFixBatch: async (failures, details) => agent(
      `Fix the app bugs found by native test-pilot for work-item ${workItem}. Commit fixes locally. ` +
      `Return ONLY JSON {"ok":true,"commitShas":["..."],"changedFiles":["..."],"head":"..."}. ` +
      `Failures: ${JSON.stringify(failures)} Details: ${JSON.stringify(details)}`,
      { label: 'test-pilot-fixer', schema: { type: 'object' } }),

    reviewCode: (wi, opts) => reviewCodePhase(wi, Object.assign({}, opts, {
      runDir: opts.runDir || `/tmp/showrunner-${wi}-review-code-${safeRunKey(opts.runDirSuffix || `${opts.cycle || 1}-${opts.expectedHead || 'head'}`)}`,
    })),

    restoreBaseline: async (records, details) => {
      const recordsPath = await writeJson('restore-records', records)
      const out = await cli(
        `python3 plugins/superheroes/lib/test_pilot_seed_cli.py restore-baseline --records-json ${shq(recordsPath)}`,
        { type: 'object' })
      if (out.action === 'park' || out.ok === false) return out
      return Object.assign({}, out, { baseline: { head: details.head, restored: true, status: out.status } })
    },

    ensureFinalArtifacts: async (payload) => {
      const pr = payload.context.pr && payload.context.pr.number
      if (!pr) return { action: 'park', reason: 'final results artifact requires a PR number' }
      const planPath = await writeJson('final-plan-artifact', { key: keyFor(payload.context.branch), records: payload.records })
      const resultsPath = await writeJson('final-results-artifact', Object.assign({ key: keyFor(payload.context.branch) }, payload.aggregated || {}))
      return cli(
        `python3 plugins/superheroes/lib/test_pilot_artifacts_cli.py ensure ` +
        `--plan-json ${shq(planPath)} --results-json ${shq(resultsPath)} --pr ${shq(String(pr))} --key ${shq(keyFor(payload.context.branch))}`,
        { type: 'object' })
    },

    publishReady: async (_wi, head, payload) => {
      const statusPath = await writeJson('publish-status', {
        branch: payload.context.branch,
        store: payload.context.store,
        generation,
      })
      const storeArg = payload.context.store ? ` --store ${shq(payload.context.store)}` : ''
      const generationArg = generation ? ` --generation ${shq(String(generation))}` : ''
      return cli(
        `python3 plugins/superheroes/lib/test_pilot_publish_cli.py publish --work-item ${shq(workItem)} ` +
        `--head ${shq(head)} --status-json ${shq(statusPath)} --expected-branch ${shq(payload.context.branch)} ` +
        `${storeArg}${generationArg}`,
        { type: 'object' })
    },

    writeStatus: async (status) => {
      const statusPath = await writeJson('status-write', status)
      return cli(
        `python3 plugins/superheroes/lib/test_pilot_status_cli.py write --work-item ${shq(workItem)} --status-json ${shq(statusPath)}`,
        { type: 'object', required: ['ok'] })
    },
  }
}

// returns { ok } — a false ok means journal_entry caught a DurableWriteError (UFR-2).
async function appendPhaseRecord(workItem, phase, gate, phaseResult) {
  const payload = shq(JSON.stringify({ phase, gate,
    confidence: phaseResult.confidence, assumptions: phaseResult.assumptions || [] }))
  return cmdRunner(
    `python3 plugins/superheroes/lib/journal_entry.py --work-item ${shq(workItem)} --payload ${payload}`,
    { schema: { type: 'object', required: ['ok'], properties: { ok: {}, error: { type: 'string' } } } },
  )
}

async function runPhases(workItem, fromStep, deps) {
  deps = deps || {}
  for (let i = fromStep; i < PHASES.length; i += 1) {
    const phase = PHASES[i]
    // Progress-group every leaf dispatched during this phase under the phase name (read by the
    // bundle's agent wrapper). Purely cosmetic — no control-flow effect.
    if (typeof globalThis !== 'undefined') globalThis.__SR_PHASE = phase
    // FR-7: the native front-half ends at its boundary — park before entering the back-half
    // (the 'workhorse' build phase, renamed from 'build' in #107), on a FRESH run AND on a RESUME
    // (a resume re-enters at the build cursor, so the boundary must be checked at that phase, not
    // merely after review-tasks).
    if (deps.frontHalfBoundary && phase === 'workhorse') {
      return deps.frontHalfBoundary(workItem)
    }
    if (phase === 'ship') {                              // terminal: returns {outcome,phase,reason}
      return (deps.ship || shipPhase)(workItem, await loadPr(workItem))
    }
    let phaseResult, gate, sideEffect = null
    if (phase === 'review-code') {
      const r = await (deps.reviewCode || reviewCodePhase)(workItem); phaseResult = r.phaseResult; gate = r.gate
    } else if (phase === 'workhorse') {
      phaseResult = await (deps.build || buildPhase)(workItem, deps.generation); gate = null
    } else if (phase === 'draft-PR') {
      const r = await (deps.draftPR || draftPRPhase)(workItem); phaseResult = r.phaseResult; gate = null; sideEffect = r.sideEffect
    } else if (phase === 'test-pilot') {
      phaseResult = await (deps.testPilot || defaultTestPilotPhase)(workItem, deps.generation); gate = null
    } else if (phase === 'mark-ready') {
      const r = await (deps.markReady || markReadyPhase)(workItem); phaseResult = r.phaseResult; gate = null; sideEffect = r.sideEffect
    } else if ((phase === 'review-plan' || phase === 'review-tasks') && deps.reviewDoc) {
      const doc = phase === 'review-plan' ? 'plan' : 'tasks'
      const r = await deps.reviewDoc(doc, workItem); phaseResult = r.phaseResult; gate = r.gate
    } else if ((phase === 'plan' || phase === 'tasks') && deps.produce) {
      phaseResult = await deps.produce(phase, workItem); gate = null
    } else {
      phaseResult = await (deps.phaseLeaf || defaultPhaseLeaf)(phase, workItem)
      gate = await (deps.gateRead || (async () => null))(phase, workItem)
    }
    const rec = await appendPhaseRecord(workItem, phase, gate, phaseResult)
    if (!rec.ok) return { outcome: 'parked', phase, reason: 'durable write failed (DurableWriteError) — UFR-2' }
    const decision = await phaseStep(phaseResult, gate)
    if (decision.action !== 'proceed') return { outcome: 'parked', phase, reason: decision.reason }
    // FR-4/FR-3: persist the side effect + cursor BEFORE advancing. If that durable write fails, park
    // rather than advance — advancing on an unrecorded cursor would lose record-before-advance.
    const cur = await recordCursor(workItem, i, phase, sideEffect)
    if (!cur.ok) return { outcome: 'parked', phase, reason: 'cursor not recorded (durable write failed) — FR-4' }
  }
  // Unreachable in normal operation — the 'ship' phase always returns first. Reaching here means
  // PHASES lacks 'ship' (an invariant violation), so park defensively rather than claim ready.
  return { outcome: 'parked', phase: 'ship', reason: 'phase loop ended without reaching ship (no ship phase?)' }
}

// #86 verdict -> the gate phase_step.decide consumes.
function verdictToGate(verdict) {
  return verdict && verdict.gate === 'clean' ? 'passed' : 'changes-requested'
}

// Render the loop's uniform readout (from its own verdict record, which carries parentOrigin via the
// extras channel) and post it at the park (no PR yet -> readout_post records to the store). FR-6/UFR-1.
async function renderAndPostReadout(workItem, runDir, verdict) {
  const recPath = `${runDir}/terminal-record.json`
  try { await io().writeFile(recPath, JSON.stringify(verdict || {})) } catch (_) {}
  const text = await agent(
    `Run exactly this and return ONLY its stdout, unchanged:\n\n` +
    `python3 plugins/superheroes/lib/loop_readout.py --record ${shq(recPath)}`,
    { label: 'readout' })
  await cmdRunner(
    `python3 plugins/superheroes/lib/readout_post.py --work-item ${shq(workItem)} --reason ${shq(String(text))}`,
    { schema: { type: 'object', required: ['posted'], properties: { posted: {}, recorded: {}, error: { type: 'string' } } } })
}

// the review-code phase: drive the shared loop, map its terminal to advance/park, stamp covers on a
// pure `clean` (X'), and surface the readout at a park. Returns { phaseResult, gate } for runPhases.
async function reviewCodePhase(workItem, opts) {
  opts = opts || {}
  const runDir = opts.runDir || (opts.runDirSuffix
    ? `/tmp/showrunner-${workItem}-review-code-${safeRunKey(opts.runDirSuffix)}`
    : `/tmp/showrunner-${workItem}-review-code`)
  const initialHead = opts.expectedHead || null
  if (opts.expectedHead) {
    const actual = await resolveHead(opts.worktree || null, opts.ref || 'HEAD')
    if (!actual || actual !== opts.expectedHead) {
      return { phaseResult: { confidence: 'low', assumptions: [`review-code target head mismatch: expected ${opts.expectedHead}, got ${actual || 'unknown'}`] }, gate: 'changes-requested' }
    }
  }
  const targetWorktree = opts.worktree || null
  // premortem-002: the fixer is a freeform subagent that receives the target worktree only as a TEXT
  // hint (withTargetCommandPrompts retargets just the "Run exactly this" cmdRunner prompts). If it
  // commits to the showrunner CWD instead of the target tree, the target HEAD never advances, the
  // expectedHead checks still pass (both = pre-fix HEAD), and a stale `clean` covers-stamp would
  // publish unmodified code. Snapshot CWD HEAD so we can detect that divergence after the loop.
  const cwdHeadBefore = (targetWorktree && opts.expectedHead) ? await resolveHead(null, opts.ref || 'HEAD') : null
  const cfg = await cmdRunner(
    inWorktree(`python3 plugins/superheroes/lib/review_code_config.py --root "$(git rev-parse --show-toplevel)"`, targetWorktree),
    { schema: CONFIG_SCHEMA })
  const leaves = reviewCodeLeaves((cfg && cfg.tiers) || {}, {
    target: { worktree: opts.worktree, head: opts.expectedHead },
  })
  const verdict = await runReviewCodePanel({
    runDir, context: workItem, rubric: 'review-base',
    verifyCommand: (cfg && cfg.verifyCommand) || 'none', leaves, worktree: targetWorktree,
  })
  const terminal = (verdict && verdict.terminal) || 'halted'
  const finalHead = opts.expectedHead
    ? await resolveHead(opts.worktree || null, opts.ref || 'HEAD')
    : null
  if (opts.expectedHead && !finalHead) {
    return { phaseResult: { confidence: 'low', assumptions: ['review-code final target head could not be resolved'] }, gate: 'changes-requested', terminal, head: null, changed: false }
  }
  // #104's advance/park mapping, read off the terminal (plan Key decision 2).
  if (!ADVANCE_TERMINALS.has(terminal)) {
    await renderAndPostReadout(workItem, runDir, verdict)   // names parentOrigin at the review-phase park
    return { phaseResult: { confidence: 'high', assumptions: [`review-code ${terminal}`] }, gate: 'changes-requested', terminal, head: finalHead, changed: !!(initialHead && finalHead && initialHead !== finalHead) }
  }
  // premortem-002 fail-closed: an advancing terminal means we're about to certify the target HEAD. If
  // the CWD advanced while the target HEAD did not, the fixer's commits landed outside the shipped tree
  // — refuse to advance/stamp rather than certify (and ship) code the fixes never touched.
  if (targetWorktree && opts.expectedHead) {
    const cwdHeadAfter = await resolveHead(null, opts.ref || 'HEAD')
    const cwdMoved = cwdHeadBefore && cwdHeadAfter && cwdHeadBefore !== cwdHeadAfter
    const targetMoved = initialHead && finalHead && initialHead !== finalHead
    if (cwdMoved && !targetMoved) {
      return { phaseResult: { confidence: 'low', assumptions: ['review-code fixes landed outside the target worktree (cwd HEAD advanced, target HEAD did not) — refusing to stamp coverage'] }, gate: 'changes-requested', terminal, head: finalHead, changed: false }
    }
  }
  // FR-9: stamp covers = X' ONLY on a pure `clean`; `clean-with-skips` advances with NO stamp and so
  // later parks at the ship gate. prov_entry resolves the build-branch tip (= X' after the fixer's commits).
  if (terminal === 'clean') {
    const targetArgs = opts.worktree || opts.expectedHead
      ? ` --worktree ${shq(opts.worktree || procCwd())}${finalHead ? ` --head ${shq(finalHead)}` : ''}`
      : ''
    const prov = await cmdRunner(
      `python3 plugins/superheroes/lib/prov_entry.py --step review --work-item ${shq(workItem)}${targetArgs}`,
      { schema: PROV_SCHEMA })
    if (!prov.ok) {
      // UFR-2: the covers-stamp write failed -> park (low confidence), do NOT assert ship-ready.
      return { phaseResult: { confidence: 'low', assumptions: ['review covers stamp not recorded: ' + (prov.error || 'unknown')] }, gate: 'changes-requested' }
    }
  }
  return {
    phaseResult: { confidence: 'high', assumptions: [] },
    gate: 'passed',
    terminal,
    head: finalHead,
    changed: !!(initialHead && finalHead && initialHead !== finalHead),
    reviewCoverageHead: terminal === 'clean' ? (finalHead || undefined) : undefined,
    verifyPassedHead: finalHead || undefined,
  }
}

async function resolveHead(worktree, ref) {
  const cmd = worktree
    ? `git -C ${shq(worktree)} rev-parse ${shq(ref || 'HEAD')}`
    : `git rev-parse ${shq(ref || 'HEAD')}`
  try {
    const out = await agent(
      `Run exactly this command and return ONLY its stdout, unchanged:\n\n${cmd}`,
      { label: 'lib' })
    const text = String(out || '').trim()
    return text || null
  } catch (_) {
    return null
  }
}

// the native "workhorse" build phase (#87) — implement the approved tasks doc task-by-task with a
// per-task review + bounded fix loop, one whole-branch final review, and provenance written once.
// All of that orchestration lives in build_phase.js; the spine just delegates, threading the lease
// generation reconcile() acquired so the build can fence every branch-mutating boundary (UFR-10).
const buildPhase = (workItem, generation) => require('./build_phase.js').buildPhase(workItem, generation)

module.exports.verdictToGate = verdictToGate
module.exports.reviewCodePhase = reviewCodePhase
module.exports.runReviewCodePanel = runReviewCodePanel
module.exports.buildPhase = buildPhase

const CKPT_SCHEMA = { type: 'object', required: ['ok'], properties: { ok: {}, pr: {} } }

// recordCursor writes lastGoodStep + lastGoodPhase (+ any side effect: { pr } or { ready }) BEFORE the loop
// advances — so a crash resumes after this phase and never repeats an irreversible action (FR-4).
async function recordCursor(workItem, step, phase, sideEffect) {
  const extra = sideEffect ? ` --json ${shq(JSON.stringify(sideEffect))}` : ''
  return cmdRunner(
    `python3 plugins/superheroes/lib/checkpoint_entry.py --work-item ${shq(workItem)} ` +
    `--step ${shq(String(step))} --phase ${shq(phase)}${extra}`,
    { schema: CKPT_SCHEMA })
}

async function loadPr(workItem) {
  const out = await cmdRunner(
    `python3 plugins/superheroes/lib/checkpoint_entry.py --work-item ${shq(workItem)} --read-pr`,
    { schema: { type: 'object', required: ['pr'], properties: { pr: {} } } })
  return out.pr
}

// draft-PR: split IO from judgment (#115 Task 16).
// --emit-world reads the PR world (IO-only); recoverTwin.prAction decides adopt/create/gate in-process.
// On 'create': the full pr_entry.py path (ship_gate.decide + gh pr create + read-back) stays in Python.
// The {pr} capture happens before recordCursor persists it (FR-4 exactly-once preserved).
async function draftPRPhase(workItem) {
  const worldResults = await exec([
    `python3 plugins/superheroes/lib/pr_entry.py --step draft --work-item ${shq(workItem)} --emit-world`,
  ])
  let world = { pr: 'unknown' }  // fail-closed default
  if (worldResults[0] && worldResults[0].ok) {
    try { world = JSON.parse(worldResults[0].stdout) } catch (_) {}
  }
  const act = recoverTwin.prAction(world)
  if (act === 'gate') {
    return { phaseResult: { confidence: 'low', assumptions: ['PR read transient/merged — not creating a 2nd PR'] }, sideEffect: null }
  }
  if (act === 'adopt') {
    return { phaseResult: { confidence: 'high', assumptions: [] }, sideEffect: { pr: world.pr } }
  }
  // 'create': ship_gate.decide + gh pr create + read-back stay in Python (irreducible IO + git/gh).
  // FR-8: thread configurable base (--base) when __SR_BASE is set; absent -> gh uses remote default.
  const _srBaseForPR = (typeof globalThis !== 'undefined' && globalThis.__SR_BASE) ? String(globalThis.__SR_BASE) : null
  const _prBaseArg = _srBaseForPR ? ` --base ${shq(_srBaseForPR)}` : ''
  const createResults = await exec([
    `python3 plugins/superheroes/lib/pr_entry.py --step draft --work-item ${shq(workItem)}${_prBaseArg}`,
  ])
  let createOut = null
  if (createResults[0] && createResults[0].ok) {
    try { createOut = JSON.parse(createResults[0].stdout) } catch (_) {}
  }
  if (!createOut || !createOut.ok) {
    return { phaseResult: { confidence: 'low', assumptions: [createOut && createOut.reason || 'draft-PR gated'] }, sideEffect: null }
  }
  return { phaseResult: { confidence: 'high', assumptions: [] }, sideEffect: { pr: createOut.pr } }
}

// mark-ready: pr_entry.py world-reads isDraft (pr_phase.mark_ready_action), flips if needed,
// returns { ready: true }. Idempotent on resume (an already-ready PR -> skip).
async function markReadyPhase(workItem) {
  const out = await cmdRunner(
    `python3 plugins/superheroes/lib/pr_entry.py --step mark-ready --work-item ${shq(workItem)}`,
    { schema: { type: 'object', required: ['ok'], properties: { ok: {}, reason: { type: 'string' } } } })
  if (!out.ok) return { phaseResult: { confidence: 'low', assumptions: [out.reason || 'mark-ready gated'] }, sideEffect: null }
  return { phaseResult: { confidence: 'high', assumptions: [] }, sideEffect: { ready: true } }
}

module.exports.recordCursor = recordCursor
module.exports.draftPRPhase = draftPRPhase
module.exports.markReadyPhase = markReadyPhase
module.exports.testPilotPhase = testPilotPhase
module.exports.defaultTestPilotPhase = defaultTestPilotPhase
module.exports.testPilotDeps = testPilotDeps

async function shipPhase(workItem, pr) {
  // freshness.decide -> up_to_date | sync | give_up_notify | gate. For this slice only up_to_date
  // proceeds; the auto-sync of a behind branch is back-half deepening, so sync/give_up_notify/gate
  // all park (FR-11: not merge-ready unless up to date).
  // FR-8: thread configurable base (--base) when __SR_BASE is set; absent -> default 'main' behavior.
  const _srBase = (typeof globalThis !== 'undefined' && globalThis.__SR_BASE) ? String(globalThis.__SR_BASE) : null
  const _baseArg = _srBase ? ` --base ${shq(_srBase)}` : ''
  const fresh = await cmdRunner(
    `python3 plugins/superheroes/lib/ship_phase.py --step freshness --work-item ${shq(workItem)}${_baseArg}`,
    { schema: { type: 'object', required: ['decision'], properties: { decision: { type: 'string' } } } })
  if (fresh.decision !== 'up_to_date') {
    return park(workItem, pr, `branch not up to date with base (${fresh.decision})`)
  }
  // CI split (#115 Task 16): exec reads raw checks array (IO-only); ciStatusTwin classifies in-process.
  // green -> merge-ready; none -> merge-ready with carve-out; red -> park.
  // Fail-closed: exec error or {error} response -> park (never a false green).
  const ciResults = await exec([
    `python3 plugins/superheroes/lib/ship_phase.py --step ci --work-item ${shq(workItem)} --emit-checks`,
  ])
  if (!ciResults[0] || !ciResults[0].ok) {
    return park(workItem, pr, 'CI status could not be read')
  }
  let ciChecks = null
  try { ciChecks = JSON.parse(ciResults[0].stdout) } catch (_) {}
  // Fail-closed (Critical, #115 final review): a JSON.parse failure (ciChecks === null) means the
  // leaf returned garbled / non-JSON / truncated stdout — the read genuinely FAILED. Park; do NOT
  // coerce a parse-failure to [] (which would classify 'none' -> a false "merge-ready: no required
  // checks"). A genuinely-empty array [] still classifies to 'none' below (correct: no checks gate).
  if (ciChecks === null) {
    return park(workItem, pr, 'CI status could not be read')
  }
  if (!Array.isArray(ciChecks) && ciChecks.error) {
    return park(workItem, pr, ciChecks.error || 'CI status could not be read')
  }
  const checksArr = Array.isArray(ciChecks) ? ciChecks : []
  const ciRes = ciStatusTwin.classify(checksArr)
  if (ciRes.status === 'green') {
    return park(workItem, pr, 'merge-ready: CI green and branch up to date — awaiting owner merge', true)
  }
  if (ciRes.status === 'none') {
    return park(workItem, pr, 'merge-ready: no required checks gate this PR — confirm checks before merging', true)
  }
  const ciReason = ciRes.failing && ciRes.failing.length
    ? 'checks not green: ' + ciRes.failing.join(', ')
    : 'CI could not be made green'
  return park(workItem, pr, ciReason)
}

// park posts the readout (scrubbed) to the PR; on a failed post it records to the store (UFR-4).
async function park(workItem, pr, reason, mergeReady) {
  const prNum = pr && pr.number ? ` --pr ${shq(String(pr.number))}` : ''
  const rPost = await cmdRunner(
    `python3 plugins/superheroes/lib/readout_post.py --work-item ${shq(workItem)} --reason ${shq(reason)}${prNum}`,
    { schema: { type: 'object', required: ['posted'], properties: { posted: {}, recorded: {}, error: { type: 'string' } } } })
  // UFR-4 detectability: if the readout reached neither the PR nor the store (e.g. a full disk failed
  // both the journal and the store fallback), the owner gets no 'your turn' signal — surface that in
  // the returned reason rather than reporting a clean park.
  const delivered = rPost && (rPost.posted || rPost.recorded)
  const reasonOut = delivered
    ? reason
    : `${reason} [warning: readout could not be delivered (${(rPost && rPost.error) || 'unknown'})]`
  return { outcome: mergeReady ? 'ready' : 'parked', phase: 'ship', reason: reasonOut }
}

module.exports.shipPhase = shipPhase
module.exports.park = park

async function defaultPhaseLeaf(_phase, _workItem) {
  return { confidence: 'high', assumptions: [] }
}

module.exports.showrunner = showrunner
module.exports.cmdRunner = cmdRunner
module.exports.reconcile = reconcile
module.exports.runPhases = runPhases
module.exports.PHASES = PHASES
module.exports.exec = exec
module.exports.persistPhase = persistPhase
module.exports.cheapestModel = cheapestModel
module.exports.selfContained = selfContained
module.exports.authorModel = authorModel

};


if (globalThis.__SR_RUN !== false) {
  // The Workflow runtime delivers the tool's args input as a JSON STRING (not a parsed object), so
  // accept either: parse a string, pass an object through. A non-JSON / missing value -> clear throw.
  let __a = args
  if (typeof __a === 'string') { try { __a = JSON.parse(__a) } catch (_) { __a = null } }
  const wi = (__a && typeof __a === 'object') ? __a.workItem : null
  if (!wi) throw new Error('showrunner bundle requires args.workItem')
  // Optional cheap-leaf override for throwaway/test runs (args.model, e.g. 'haiku'); absent in
  // production so the per-role model tiers govern. The preamble's agent wrapper applies it.
  if (__a && __a.model) globalThis.__SR_LEAF_MODEL = __a.model
  // FR-5: thread the explicit repo root so leaf commands cd to the correct checkout regardless of
  // the haiku leaf's cwd. Callers pass args.root = <abs repo root> to opt in; absent in production
  // (where the leaf cwd is the correct repo) the guard is unset and selfContained() is a no-op.
  if (__a && __a.root) globalThis.__SR_ROOT = __a.root
  // args-based front-half selector (Task 13a, #115): args.frontHalf==='native' opts into a
  // front-half-only run (parks at the workhorse boundary). This drives the sandbox selector
  // because the env path (SUPERHEROES_FRONT_HALF) is unavailable in the Workflow sandbox (FR-8).
  // The preamble sets SUPERHEROES_BUNDLE_FULL_RUN=true as the safe default; the ENTRY's
  // assignment here runs AFTER the preamble so it correctly overrides that default.
  const frontHalfNative = !!(__a && __a.frontHalf === 'native')
  globalThis.SUPERHEROES_FRONT_HALF_NATIVE = frontHalfNative
  globalThis.SUPERHEROES_BUNDLE_FULL_RUN = !frontHalfNative
  // Configurable base branch (#115): args.base is the branch name to build off of and PR into.
  // Absent -> unset (each site falls back to its default: _base() / 'main' / gh default).
  if (__a && __a.base) globalThis.__SR_BASE = __a.base
  return __require('showrunner.js').showrunner({ workItem: wi })
}
