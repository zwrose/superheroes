// plugins/superheroes/lib/engine_dispatch.js
// Spine leaf wrapper (#38): the single seam every JS call site invokes instead of agent() when the
// engine is external (codex|cursor). Deterministic argv/parse/commit live in engine_adapter.py; this
// wrapper sequences them through the spine's exec dumb-pipe and returns the NATIVE result shape so
// everything downstream (loop math, verify gate, journal) is reused unchanged. Read roles are
// read-only (no preSHA/commit); write roles capture preSHA -> engine edits -> adapter commits.
const { libPath } = require('./lib_root.js')
const { b64 } = require('./bytes.js')
const DEFAULT_STALL_LIMIT_SECONDS = 300   // UFR-5 finite default; test-settable via opts.timeoutSeconds

function shq(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }

// Build a shell command that stages `content` to `path` via base64 (NOT a heredoc): external/engine
// text is untrusted and MAY contain a line identical to any fixed heredoc sentinel, which would
// terminate the heredoc early and corrupt the staged file. Base64 also makes the payload an OPAQUE
// blob as it rides the LLM `exec` courier — a courier can copy alphabet-soup verbatim or fail
// visibly, but cannot paraphrase it the way it rewrites readable text (the 2026-07-02 staged-write
// mangle class). Encoding sidesteps sentinels AND mangling; a shell `base64 -d` decodes it.
// #277: the base64 encode MUST NOT use Node's `Buffer` — the Workflow sandbox has no Buffer global
// (same class as the FR-8-banned wall-clock/PRNG globals), so `Buffer.from(...)` threw on the first
// statement here and every external dispatch silently fell open to Claude. b64() is the shared,
// Buffer-less encoder (bytes.js), byte-identical in node and the sandbox and exercised the same in
// both. base64 output is pure ASCII so shq's single-quote escaping is sufficient.
function _stageCmd(path, content) {
  const encoded = b64(content == null ? '' : String(content))
  return `printf %s ${shq(encoded)} | base64 -d > ${shq(path)}`
}

// #307: codex's `--output-schema` rides OpenAI STRICT structured outputs, whose two hard rules the
// Anthropic-authored schema literals (FINDINGS_SCHEMA / REVIEW_TASK_SCHEMA / FINAL_REVIEW_SCHEMA)
// were never written for: EVERY object must carry `additionalProperties:false` AND a `required` array
// naming EVERY property key. Sent verbatim these 400 with `invalid_json_schema` before any review
// work, so every codex review dispatch has silently fallen open to Claude since the engine onboarding
// (0 successes ever — see #307). We fix at the STAGING seam, not the literals: one transform corrects
// all three senders (and any future one), and the NATIVE Claude path keeps receiving the original
// permissive schema (Anthropic rejects some strict shapes). `strictify` deep-walks the schema and on
// every object node sets `additionalProperties:false` + `required = every property key`; a property
// that was NOT originally required is widened to a NULLABLE union (`type:["string","null"]`, or a
// `null` member added to an `enum`) so a field that used to be omittable stays semantically optional
// (the engine emits explicit `null` instead of dropping the key). PURE — never mutates its input (the
// literals are module-level constants also handed to the native agent() path). Idempotent: a second
// pass finds every key already in `required`, so nothing is re-widened.
function _typeWithNull(type) {
  if (type == null) return type
  if (Array.isArray(type)) return type.indexOf('null') >= 0 ? type : type.concat(['null'])
  return type === 'null' ? type : [type, 'null']
}

function _jsonType(v) {
  if (v === null) return 'null'
  if (typeof v === 'string') return 'string'
  if (typeof v === 'boolean') return 'boolean'
  if (typeof v === 'number') return Number.isInteger(v) ? 'integer' : 'number'
  return null
}

// Make a single property schema accept explicit null (so a previously-optional field can be present-
// but-null under strict mode). Widens a `type` to a null union; for an enum-only property, adds a
// `null` member AND an inferred nullable `type` union (the OpenAI-documented nullable-enum shape).
function _nullableProp(propSchema) {
  if (!propSchema || typeof propSchema !== 'object' || Array.isArray(propSchema)) return propSchema
  const p = Object.assign({}, propSchema)
  const hasEnum = Array.isArray(p.enum)
  if (hasEnum && p.enum.indexOf(null) < 0) p.enum = p.enum.concat([null])
  if (p.type !== undefined) {
    p.type = _typeWithNull(p.type)
  } else if (hasEnum) {
    const types = []
    for (const v of p.enum) {
      const t = _jsonType(v)
      if (t && types.indexOf(t) < 0) types.push(t)
    }
    if (types.length) p.type = types
  }
  return p
}

function _isObjectNode(node) {
  if (!node || typeof node !== 'object') return false
  if (node.type === 'object') return true
  return Array.isArray(node.type) && node.type.indexOf('object') >= 0
}

function strictify(schema) {
  if (Array.isArray(schema)) return schema.map(strictify)
  if (!schema || typeof schema !== 'object') return schema
  const out = {}
  for (const k of Object.keys(schema)) out[k] = strictify(schema[k])
  if (_isObjectNode(out)) {
    const props = (out.properties && typeof out.properties === 'object' && !Array.isArray(out.properties))
      ? out.properties : null
    const propKeys = props ? Object.keys(props) : []
    const originalRequired = Array.isArray(schema.required) ? schema.required : []
    if (props) {
      for (const key of propKeys) {
        if (originalRequired.indexOf(key) < 0) props[key] = _nullableProp(props[key])
      }
    }
    out.additionalProperties = false
    out.required = propKeys
  }
  return out
}

// Reuse the spine's exec dumb-pipe (lazy require avoids a load-time cycle: showrunner requires the
// bundle graph; deferring keeps engine_dispatch's require surface minimal for the smokes).
let _execFn = null
function _exec(commands) {
  if (!_execFn) _execFn = require('./showrunner.js').exec
  return _execFn(commands)
}

// Run ONE command through the exec dumb-pipe and parse its JSON stdout. Mirrors the canonical
// build_phase.js:43-64 `execJson` contract: the cheap haiku courier occasionally drops/garbles a
// command's stdout even though it ran (live: a journal_entry.py leaf returned stdout:"" with ok:true,
// so JSON.parse("") threw and the build fail-closed-parked); retry ONCE on an empty or unparseable
// stdout before failing closed. The dispatch-path commands here (journal append, adapter build-argv /
// parse-result / commit, preSHA) are idempotent / harmless to repeat. Returns the parsed object, or
// null after the retry (the caller fails closed on null). A clean {"ok":true} on the first call returns
// immediately (one exec, no behavior change); a parseable {"ok":false} (a REAL durable-write failure)
// is returned as-is on the first call — it is NOT a courier-drop, so it is NOT retried.
async function _execJson(cmd) {
  for (let attempt = 0; attempt < 2; attempt++) {
    const res = await _exec([cmd])
    const r0 = res && res[0]
    if (r0 && r0.ok) {
      const s = (r0.stdout == null ? '' : String(r0.stdout)).trim()
      if (s) { try { return JSON.parse(s) } catch (_e) { /* garbled -> retry */ } }
      // empty stdout -> retry (courier likely dropped it)
    }
    // exec-level failure or empty/garbled -> retry once, then give up
  }
  return null
}

// preSHA capture for write roles — the established spine pattern (showrunner.js:1226).
async function _captureHead(wt) {
  const res = await _exec([`git -C ${shq(wt)} rev-parse HEAD`])
  const r0 = res && res[0]
  if (r0 && r0.ok) { const s = (r0.stdout == null ? '' : String(r0.stdout)).trim(); if (s) return s }
  return null
}

// Run the fully-formed external argv through exec, FEEDING the staged prompt file to the process
// stdin via a shell redirect. BOTH engines take the prompt on stdin: codex's trailing `-` reads
// stdin, and cursor-agent reads stdin when given no positional prompt. The argv tokens are
// shell-quoted so paths/effort strings can't break the command; the redirect is appended last so
// the prompt is always delivered (no </dev/null guard — there is always a prompt here).
// FR-8 confinement: the command is ALWAYS prefixed with `cd <cwd> && ` (mirroring showrunner.js's
// inWorktree()) so the external process runs rooted at the per-task build worktree — never at
// __SR_ROOT (the repo root selfContained() would otherwise apply via exec's dumb-pipe). This matters
// most for cursor, whose argv (engine_adapter.py) carries NO -C/cwd flag of its own; codex is
// self-confining via -C but the cd prefix is harmless/idempotent for it too. Applied unconditionally
// whenever a cwd is supplied (read roles are already read-only-sandboxed by the engine itself).
//
// FIX 2 (premortem): the JS Promise.race in dispatchExternal only stops US from WAITING on a stalled
// CLI — the subprocess itself keeps running unkilled, orphaned, potentially still writing to the
// worktree/git index while the caller has already fallen open and is retrying with the native Claude
// worker (a write-write race on the same files). Bound the CLI at the OS level too: wrap it with a
// portable `perl -e 'alarm shift @ARGV; exec @ARGV or exit 127'` — perl's alarm() SIGALRMs the process
// after <timeoutSeconds>, and since exec() replaces the perl process image with the CLI (same PID), the
// alarm fires against the CLI itself, killing it. This is belt-and-suspenders with the JS race (which
// stays, so a slow-to-signal-death CLI still can't hang the caller past limitMs) — the perl layer's job
// is only to make sure the CLI is actually DEAD, not just unwaited-on. perl/alarm/exec are ordinary CLI
// tokens (not Node/JS globals), so they don't trip the bundle's banned-global static check.
// Returns the raw stdout string (or null on fail).
async function _runArgv(argv, promptPath, cwd, timeoutSeconds) {
  const seconds = Number(timeoutSeconds) > 0 ? Math.ceil(Number(timeoutSeconds)) : Math.ceil(DEFAULT_STALL_LIMIT_SECONDS)
  const quotedArgv = argv.map((a) => shq(a)).join(' ')
  const alarmed = `perl -e ${shq("alarm shift @ARGV; exec @ARGV or exit 127")} ${seconds} ${quotedArgv}`
  const cmd = cwd ? `cd ${shq(cwd)} && ${alarmed} < ${shq(promptPath)}` : `${alarmed} < ${shq(promptPath)}`
  const res = await _exec([cmd])
  const r0 = res && res[0]
  if (r0 && r0.ok) return (r0.stdout == null ? '' : String(r0.stdout))
  return null
}

async function _journalExternal(payload) {
  // Journal the external action as a FIRST-CLASS `external_dispatch` event (FR-6): the audit line's
  // `type` is external_dispatch (Task 4 added the type + the journal_entry.py --event-type flag), and
  // the payload is written AS-IS (non-secret {engine,effort,roleKind,verify,outcome}). A failed durable
  // append -> {ok:false} -> the caller treats it as UFR-6 (fail-closed, unauditable).
  return _execJson(
    `python3 ${libPath('journal_entry.py')} --work-item ${shq(payload.workItem || '')} ` +
    `--event-type external_dispatch --payload ` +
    shq(JSON.stringify({ engine: payload.engine, effort: payload.effort, roleKind: payload.roleKind,
      verify: payload.verify, outcome: payload.outcome })))
}

// Scrub external-derived free-text (git stderr in a commit/dispatch-failure reason) BEFORE it enters
// an owner-facing notice — the band's single scrub seam (pr_comment.py scrub reads stdin -> scrubbed
// stdout, the same scrubber readout/parse_result use). On any exec/scrub failure fall back to a
// fixed generic label (never surface the raw external text). Only used on the failure/notice path.
async function _scrubReason(reason) {
  const s = reason == null ? '' : String(reason)
  if (!s) return s
  const res = await _exec([`printf '%s' ${shq(s)} | python3 ${libPath('pr_comment.py')} scrub`])
  const r0 = res && res[0]
  if (r0 && r0.ok && r0.stdout != null) return String(r0.stdout)
  return 'external error (scrubbed)'
}

// FIX 3: the body runs inside a try/catch in the exported dispatchExternal below, so ANY thrown
// error (a synchronous throw from a step here, or an unavailable Buffer/setTimeout global) still
// returns the native {ok:false} failure shape instead of throwing — callers' fall-open-to-Claude
// path (UFR-2 discard + native worker) only fires on a returned failure, never on an exception.
async function _dispatchExternalInner(o) {
  const { engine, roleKind, effort, prompt, cwd, schema, timeoutSeconds, model } = o
  const limitSeconds = Number(timeoutSeconds) > 0 ? Number(timeoutSeconds) : DEFAULT_STALL_LIMIT_SECONDS
  const limitMs = limitSeconds * 1000
  const isWrite = (roleKind === 'build' || roleKind === 'fix')
  // author-plan (the plan-author leaf) is write-SANDBOXED (it authors the doc + stamps the marker)
  // but takes NO preSHA/commit: definition-docs are not committed by the produce phase (native
  // authors don't commit either; in-repo docs ride the ship phase, out-of-repo docs never commit).
  // Its acceptance gate is the caller's deterministic usableDraft post-check, not this dispatch.
  const isAuthor = (roleKind === 'author-plan')

  // 1. Stage prompt + schema to disk (via exec). The PROMPT file is fed to the external process
  //    stdin by _runArgv (both engines read the prompt from stdin); the SCHEMA path is passed to
  //    build-argv via --schema-path (codex --output-schema for read roles).
  // runId is built from CALLER-SUPPLIED identifiers only — no wall-clock time or PRNG calls (FR-8:
  // the Workflow sandbox has no time/random globals, and the bundle-smoke statically bans those APIs
  // because they break deterministic resume). taskId (write roles) or workItem (read roles) plus
  // engine/roleKind give a stable-enough per-dispatch key; callers that omit both share a fallback
  // key, which is safe because writeInputs/rawPath are consumed synchronously within this single
  // dispatch and never read back across calls.
  const runKey = String(o.taskId || o.workItem || 'run').replace(/[^A-Za-z0-9_.-]+/g, '-').slice(0, 80)
  const runId = `${engine}-${roleKind}-${runKey}`
  const promptPath = `/tmp/engine-${runId}.prompt`
  const schemaPath = `/tmp/engine-${runId}.schema.json`
  // #307: codex reads this file as an OpenAI-STRICT `--output-schema`; strictify it so it validates
  // (see strictify above). ONLY on the codex path — cursor ignores the schema entirely, and the
  // native Claude path never reaches this seam (it calls agent() with the original permissive schema,
  // which Anthropic's tool input_schema requires and which strict shapes would break).
  const stagedSchema = engine === 'codex' ? strictify(schema || {}) : (schema || {})
  const writeInputs = await _exec([
    _stageCmd(promptPath, prompt || ''),
    _stageCmd(schemaPath, JSON.stringify(stagedSchema)),
  ])
  if (!(writeInputs && writeInputs.every && writeInputs.every((r) => r && r.ok))) {
    return { ok: false, reason: 'could-not-stage-external-inputs' }
  }

  // 2. preSHA (write roles only — read roles never mutate the tree, FR-7).
  let preSha = null
  if (isWrite) {
    preSha = await _captureHead(cwd)
    if (!preSha) return { ok: false, reason: 'could-not-capture-preSHA' }
  }

  // 3. Wrap the whole dispatch in the UFR-5 finite timeout. A stall -> {ok:false, reason:'timeout'}.
  const run = (async () => {
    const argvObj = await _execJson(
      `python3 ${libPath('engine_adapter.py')} build-argv --engine ${shq(engine)} --role ${shq(roleKind)} ` +
      `--effort ${shq(String(effort == null ? '' : effort))} --cwd ${shq(cwd || '.')} ` +
      `--schema-path ${shq(schemaPath)}` +
      (typeof model === 'string' && model ? ` --model ${shq(model)}` : ''))
    const argv = argvObj && Array.isArray(argvObj.argv) ? argvObj.argv : (Array.isArray(argvObj) ? argvObj : null)
    if (!argv) return { ok: false, reason: 'build-argv-failed' }

    // Feed the staged prompt file to the external process stdin (the argv itself carries no prompt).
    // cwd is threaded through so _runArgv can confine the run to the worktree (FR-8; see _runArgv).
    // limitSeconds is threaded through so _runArgv can OS-level-kill a stalled CLI (FIX 2 below) —
    // the same value that bounds the JS Promise.race, so the perl alarm and the race agree.
    const rawStdout = await _runArgv(argv, promptPath, cwd, limitSeconds)
    if (rawStdout == null) return { ok: false, reason: 'external-run-failed' }

    // parse-result SCRUBS external free-text at the adapter boundary (Task 6); pass raw stdout by file.
    const rawPath = `/tmp/engine-${runId}.out`
    const wroteRaw = await _exec([_stageCmd(rawPath, rawStdout)])
    if (!(wroteRaw && wroteRaw[0] && wroteRaw[0].ok)) return { ok: false, reason: 'could-not-stage-external-output' }
    const parsed = await _execJson(
      `python3 ${libPath('engine_adapter.py')} parse-result --engine ${shq(engine)} --role ${shq(roleKind)} ` +
      `--stdout-path ${shq(rawPath)}`)
    if (!parsed || parsed.ok !== true) return { ok: false, reason: (parsed && parsed.reason) || 'unreadable' }
    return parsed
  })()

  let parsed
  // clearTimeout() the race's timeout handle once the race settles so a losing timer (the common
  // case: `run` settles first) never pins the process/test-runner event loop alive for up to
  // `limitMs` after this call already returned — pure Node hygiene, does not change the race's
  // outcome or timing. (Not unref()'d: unref would let the loop exit before EITHER branch fires
  // when the only other pending work is itself unref'd, silently abandoning the await.)
  let timeoutHandle = null
  try {
    parsed = await Promise.race([
      run,
      new Promise((resolve) => {
        timeoutHandle = setTimeout(() => resolve({ ok: false, reason: 'timeout' }), limitMs)
      }),
    ])
  } catch (_e) { parsed = { ok: false, reason: 'external-run-threw' } }
  finally { if (timeoutHandle) clearTimeout(timeoutHandle) }

  // 4a. Author role: no commit (see isAuthor above). Journal first (UFR-6 symmetry — an
  // unjournaled author dispatch is as unauditable as any other), then hand the parsed notify
  // back; the caller's usableDraft post-check decides acceptance and falls open on failure.
  if (isAuthor) {
    const jAuthor = await _journalExternal({ workItem: o.workItem, engine, effort, roleKind, verify: null,
      outcome: parsed.ok ? 'ok' : (parsed.reason || 'failed') })
    if (!(jAuthor && jAuthor.ok)) return { ok: false, reason: 'unauditable' }
    return parsed.ok ? { ok: true, notify: parsed.notify || [] } : { ok: false, reason: parsed.reason }
  }

  // 4. Read role: return findings straight through (no commit). Failure -> caller falls open to Claude.
  // FIX 5 (UFR-6 symmetry): a read role is JUST as unauditable as a write role when the journal
  // append itself fails — mirror the write-role check below (a failed journal -> {ok:false,
  // reason:'unauditable'}) instead of discarding the append's own success/failure unchecked.
  if (!isWrite) {
    const jRead = await _journalExternal({ workItem: o.workItem, engine, effort, roleKind, verify: null,
      outcome: parsed.ok ? 'ok' : (parsed.reason || 'failed') })
    if (!(jRead && jRead.ok)) return { ok: false, reason: 'unauditable' }
    return parsed.ok ? { findings: parsed.findings || [] } : { ok: false, reason: parsed.reason }
  }

  // 5. Write role failure -> only uncommitted edits exist; caller reuses resetUncommitted + falls open (UFR-2).
  if (!parsed.ok) {
    await _journalExternal({ workItem: o.workItem, engine, effort, roleKind, verify: null,
      outcome: parsed.reason || 'failed' })
    return { ok: false, reason: parsed.reason }
  }

  // 6. Write success -> the adapter is the SOLE committer (preSHA-scoped fold; single Task-Id trailer).
  const commit = await _execJson(
    `python3 ${libPath('engine_adapter.py')} commit --worktree ${shq(cwd)} --task-id ${shq(o.taskId || '')} ` +
    `--pre-sha ${shq(preSha)}`)
  if (!commit || commit.ok !== true) {
    // M1: commit.error carries raw git stderr — SCRUB it before it can reach an owner-facing notice.
    const reason = (commit && commit.error) ? await _scrubReason(commit.error) : 'commit-failed'
    // sec-101: the engine DID run and edited the worktree here, so this outcome must ALSO leave exactly
    // one audit line — otherwise commit-failure is the single external-dispatch outcome with no journal
    // entry (FR-6/UFR-6 symmetry gap). Journal BEFORE returning; the reason is already scrubbed above.
    await _journalExternal({ workItem: o.workItem, engine, effort, roleKind, verify: null,
      outcome: 'commit-failed' })
    return { ok: false, reason }
  }

  // 7. Journal BEFORE returning the native worker shape (UFR-6: unauditable -> the caller fails closed).
  const j = await _journalExternal({ workItem: o.workItem, engine, effort, roleKind,
    verify: 'pending', outcome: 'ok' })
  if (!(j && j.ok)) return { ok: false, reason: 'unauditable' }
  return { ok: true, signal: parsed.signal || 'ok', evidence: parsed.evidence || {} }
}

// #277 tripwire: the FIRST external dispatch is itself the end-to-end staging self-test — a
// harness-level staging/dispatch death (the JS path can't stage inputs, or threw before the CLI ever
// ran) means EVERY external role this run will silently fall open to Claude, violating the owner's
// enginePreferences (the named requirement #219 was held weeks for). Surface it ONCE as a distinct,
// NAMED narrator notice — run_watch shows narrator lines live, so this is the mechanical tripwire the
// named-risk convention asks for, not the routine per-dispatch "falling open" line that repeats and
// reads as normal. Keyed on PRE-CLI failure reasons only: could-not-stage-* (the staging pipe is
// dead) and dispatch-error (a synchronous throw, e.g. a missing sandbox global) — NOT engine-specific
// outcomes (timeout/unreadable/commit-failed) where the CLI genuinely ran and the harness is fine.
let _harnessDeadNoticeShown = false
function _isHarnessDeadReason(reason) {
  const r = String(reason || '')
  return r === 'could-not-stage-external-inputs' || r === 'could-not-stage-external-output' ||
    r.indexOf('dispatch-error') === 0
}
function _maybeHarnessDeadNotice(o, reason) {
  if (_harnessDeadNoticeShown || !_isHarnessDeadReason(reason)) return
  _harnessDeadNoticeShown = true
  const engine = (o && o.engine) || 'external'
  try {
    globalThis.log('ENGINE-UNAVAILABLE: engine ' + JSON.stringify(engine) + ' could not stage/dispatch in ' +
      'this harness (' + String(reason) + ') — the JS dispatch path is dead, so EVERY external role this run ' +
      'falls open to Claude, silently violating enginePreferences. Harness/staging defect (see #277), not engine auth.')
  } catch (_) {}
}

// #277: preserve the underlying error name+message (clamped) in the fall-open reason. The catch below
// is the catch-all for any synchronous throw; collapsing every throw to a bare 'dispatch-error' made
// the #277 Buffer death a transcript-archaeology session. Carrying the error text makes the next
// failure on this path self-identifying (e.g. 'dispatch-error: ReferenceError: Buffer is not defined').
// The thrown value here is an internal JS engine error (bad destructure / missing global / exec shape),
// never external free-text, so it needs no scrub — only a length clamp.
function _errText(e) {
  if (e == null) return String(e)
  const name = e.name || 'Error'
  const msg = e.message == null ? '' : String(e.message)
  return (msg ? name + ': ' + msg : name).slice(0, 160)
}

// FIX 3 (premortem): a synchronous throw ANYWHERE in the dispatch body (a bad destructure, an
// unavailable Buffer/setTimeout global, an unexpected exec-shape) must still resolve to the native
// {ok:false} failure shape — never throw out of dispatchExternal. Callers rely on a returned
// failure to trigger their fall-open-to-Claude path (UFR-2 resetUncommitted + native worker); an
// uncaught throw here would instead propagate up and abort the whole run.
async function dispatchExternal(o) {
  try {
    const res = await _dispatchExternalInner(o || {})
    _maybeHarnessDeadNotice(o, res && res.reason)
    return res
  } catch (e) {
    const reason = 'dispatch-error: ' + _errText(e)
    _maybeHarnessDeadNotice(o, reason)
    return { ok: false, reason }
  }
}

// test-only: reset the once-per-process tripwire memo so a smoke can drive the notice deterministically.
function __resetHarnessNotice() { _harnessDeadNoticeShown = false }

module.exports = { dispatchExternal, DEFAULT_STALL_LIMIT_SECONDS, __resetHarnessNotice, strictify }
