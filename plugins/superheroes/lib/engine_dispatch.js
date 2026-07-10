// plugins/superheroes/lib/engine_dispatch.js
// Spine leaf wrapper (#38): the single seam every JS call site invokes instead of agent() when the
// engine is external (codex|cursor). Deterministic argv/parse/commit live in engine_adapter.py; this
// wrapper sequences them through the spine's exec dumb-pipe and returns the NATIVE result shape so
// everything downstream (loop math, verify gate, journal) is reused unchanged. Read roles are
// read-only (no preSHA/commit); write roles capture preSHA -> engine edits -> adapter commits.
const { libPath } = require('./lib_root.js')
const { b64 } = require('./bytes.js')
const DEFAULT_STALL_LIMIT_SECONDS = 300   // UFR-5 finite default; test-settable via opts.timeoutSeconds

// #309: engines that emit output INCREMENTALLY when piped to a file (not a TTY) — verified 2026-07-09
// by piping each CLI's stdout+stderr to a file and observing byte growth BEFORE completion (codex `exec
// --sandbox read-only -`: first bytes ~1s, chunks throughout a ~20s run, max inter-chunk gap ~8s;
// cursor-agent `-p --trust --output-format stream-json`: first bytes ~2s, a mid-run chunk, done ~6s).
// For a streaming engine the byte-activity stall monitor observes real progress and only fires on a
// genuine no-output wedge. A hypothetical engine that FULLY BUFFERS until completion would be
// false-killed by a byte-growth watchdog, so it is marked `false` here — the monitor is left INERT for
// it (ceiling only, journalled stall_monitor:"inert (engine buffers)") rather than armed-and-dangerous.
// Both current engines stream, so both arm the monitor.
const _STREAMS_WHEN_PIPED = { codex: true, cursor: true }

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

// #341: the HARDENED courier discipline (superheroes:courier agentType + __SR_EXIT marker guard +
// dispatchMarked retry/fallback chain) — reused, not reinvented, for the reliability-critical engine
// CLI dispatch. courier_exec has no cyclic dependency on showrunner (it is a standalone leaf helper),
// so a direct require is safe; kept lazy only for symmetry with _exec's minimal load surface.
let _courierMod = null
function _courier() {
  if (!_courierMod) _courierMod = require('./courier_exec.js')
  return _courierMod
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
//
// #309 STALL MONITOR (the ceiling+monitor pair): the perl alarm is a wall-clock CEILING (worst case).
// When the caller arms the byte-activity monitor (`armIdle`), the CLI is instead wrapped in a shell
// watchdog that reaps a *wedged* CLI far sooner: run the alarmed CLI in the BACKGROUND as its own
// process group (`setpgrp(0,0)` in the perl wrapper — so a group-kill reaches the CLI AND its children;
// a silently-stalled writer never gets SIGPIPE, so byte-growth is the only observable signal), poll the
// captured-output file's byte size every `poll` seconds, and if it does not grow for `idleSeconds`,
// TERM-then-KILL the whole process group. Both limits are ALWAYS armed — the perl alarm ceiling stays
// inside the wrapper, and the monitor (≤ ceiling) fires first on a true stall. The watchdog emits the
// captured CLI output followed by a trailing `__SR_DISPATCH__{...}` control line JS strips + reads for
// the idle-kill verdict. The whole watchdog is composed into ONE shell command because the spine's exec
// courier runs one command and returns its complete stdout in one shot — there is no Node child_process
// in the Workflow sandbox to attach per-chunk data listeners to (FR-8), so the progress observation has
// to live shell-side, next to the CLI. The script body carries NO single quotes so it survives shq's
// single-quote wrapping intact.
//
// Returns an object: {ok:true, stdout} on a completed run; {ok:false, stalled:true, idleSeconds} when
// the monitor idle-killed the CLI; {ok:false} on a courier-level failure.
function _pollFor(idle) {
  // Poll cadence: fine enough to honor a small (test-scale) idle window, capped at 10s so a production
  // 300–600s window costs at most ~60 cheap `wc -c` samples. Effective kill latency ≈ idle + one poll.
  return Math.max(1, Math.min(10, Math.floor(Number(idle) / 4)))
}
// The single-quote-free watchdog script (see the header note). Positional args from `sh -c <script> sh`:
// $1 ceiling, $2 idle, $3 poll, $4 capture-file BASE, $5 prompt-file, $6 perlprog; then "$@" (after
// `shift 6`) = the CLI argv. Three deliberate mechanics (each answers a review finding):
//   - The CLI's stdin is redirected from the prompt file EXPLICITLY (`< "$in"`): a POSIX-sh background
//     job's stdin is /dev/null unless explicitly redirected, so relying on an outer `< promptPath` (the
//     unarmed path's mechanism) would silently feed the engine an EMPTY prompt (live-verified
//     2026-07-09; review finding code-001 Critical).
//   - stdout and stderr are captured to SEPARATE files: the idle poll watches the SUM of both sizes
//     (activity on EITHER stream resets the timer — a test-runner spinner on stderr is progress), but
//     only stdout is emitted to parse-result, so the armed path feeds the adapter exactly what the
//     unarmed path does (stderr never pollutes parsing; review finding code-002).
//   - The capture files are suffixed with the script's OWN pid (`$$` — a shell token, not a banned
//     JS time/random global, so FR-8-clean): concurrent same-workItem dispatches (a review panel
//     fanning out reviewers that share workItem/roleKind/engine and hence a runId) each get a private
//     capture pair, so one watchdog can never poll another's file (review finding premortem-001).
const _WATCH_SCRIPT = [
  'c=$1; idle=$2; poll=$3; base=$4; in=$5; prog=$6; shift 6',
  'out="$base.$$.out"; err="$base.$$.err"',
  ': > "$out"; : > "$err"',
  'perl -e "$prog" "$c" "$@" < "$in" > "$out" 2> "$err" &',
  'p=$!',
  'last=-1; idlesec=0; killed=0',
  'while kill -0 "$p" 2>/dev/null; do',
  'sleep "$poll"',
  'szo=$(wc -c < "$out" 2>/dev/null | tr -d " "); [ -n "$szo" ] || szo=0',
  'sze=$(wc -c < "$err" 2>/dev/null | tr -d " "); [ -n "$sze" ] || sze=0',
  'sz=$((szo + sze))',
  'if [ "$sz" -gt "$last" ]; then last=$sz; idlesec=0; else idlesec=$((idlesec + poll)); fi',
  'if [ "$idle" -gt 0 ] && [ "$idlesec" -ge "$idle" ]; then killed=1; kill -TERM -"$p" 2>/dev/null; sleep 1; kill -KILL -"$p" 2>/dev/null; break; fi',
  'done',
  'wait "$p" 2>/dev/null; ec=$?',
  'cat "$out"',
  // Cleanup: the stdout capture is always consumed (cat above) so always remove it; the stderr capture
  // is KEPT on any failure (idle-kill or non-zero exit) so the engine's own diagnostic survives for
  // post-mortem on disk (never surfaced to parse-result — the journal outcome points here), and removed
  // only on success (a clean run's stderr is noise; keeping every one would accumulate per dispatch).
  'if [ "$killed" -eq 1 ] || [ "$ec" -ne 0 ]; then rm -f "$out"; else rm -f "$out" "$err"; fi',
  'printf "\\n__SR_DISPATCH__{\\"idleKilled\\":%s,\\"idleSeconds\\":%s,\\"exit\\":%s}\\n" "$killed" "$idle" "$ec"',
].join('\n')

// _composeDispatchCommand: PURE composer of the exact shell command _runArgv dispatches — the
// perl-alarm ceiling (unarmed) or the #309 background watchdog (armed), confined to cwd. Exported
// (test-only) so the #341 real-seam detector can build the byte-faithful production command and drive
// it through a REAL cheapest-model leaf without a fixture-injected courier (CONVENTIONS §12.2).
function _composeDispatchCommand(argv, promptPath, cwd, timeoutSeconds, idleSeconds, armIdle) {
  const seconds = Number(timeoutSeconds) > 0 ? Math.ceil(Number(timeoutSeconds)) : Math.ceil(DEFAULT_STALL_LIMIT_SECONDS)
  const quotedArgv = argv.map((a) => shq(a)).join(' ')
  const idleArmed = armIdle === true && Number(idleSeconds) > 0
  if (idleArmed) {
    const idle = Math.min(Math.ceil(Number(idleSeconds)), seconds)   // monitor ≤ ceiling
    const poll = _pollFor(idle)
    // Capture-file BASE: the script appends its own `.$$.out`/`.$$.err` (per-sh-process pid) so
    // concurrent same-runId dispatches never share a capture file (premortem-001).
    const captureBase = promptPath.replace(/\.prompt$/, '') + '.run'
    const perlProg = 'setpgrp(0,0); alarm shift @ARGV; exec @ARGV or exit 127'
    const inner = `sh -c ${shq(_WATCH_SCRIPT)} sh ${seconds} ${idle} ${poll} ` +
      `${shq(captureBase)} ${shq(promptPath)} ${shq(perlProg)} ${quotedArgv}`
    // No outer stdin redirect: the watchdog feeds the prompt to the (backgrounded) CLI itself via
    // `< "$in"` — a POSIX-sh async job's stdin is /dev/null unless explicitly redirected, so an outer
    // redirect would silently deliver an EMPTY prompt (code-001; live-verified 2026-07-09).
    return cwd ? `cd ${shq(cwd)} && ${inner}` : inner
  }
  const alarmed = `perl -e ${shq("alarm shift @ARGV; exec @ARGV or exit 127")} ${seconds} ${quotedArgv}`
  return cwd ? `cd ${shq(cwd)} && ${alarmed} < ${shq(promptPath)}` : `${alarmed} < ${shq(promptPath)}`
}

async function _runArgv(argv, promptPath, cwd, timeoutSeconds, idleSeconds, armIdle) {
  const idleArmed = armIdle === true && Number(idleSeconds) > 0
  const cmd = _composeDispatchCommand(argv, promptPath, cwd, timeoutSeconds, idleSeconds, armIdle)
  // #341: dispatch the reliability-critical engine CLI through the HARDENED courier discipline
  // (superheroes:courier agentType + __SR_EXIT marker guard + dispatchMarked's retry/fallback chain),
  // NOT the plain exec() dumb-pipe. A safety-trained cheapest-model leaf stochastically REFUSES an
  // autonomous `cursor-agent --trust -f` write-watchdog and answers prose; the plain exec collapsed
  // that refusal into `external-run-failed` (line 415), mis-blaming the ENGINE for a courier's
  // decline (the a7bade9a escape: cursor 0/2 in-child while codex went 8/8). The marker protocol both
  // (a) REDUCES the refusal (the lean dumb-pipe framing reads as infrastructure, not a suspicious
  // dispatch) and (b) PROVES execution — a persistent missing `__SR_EXIT` marker means the shell
  // never ran (a decline), surfaced here as {declined:true} carrying the leaf's refusal prose, which
  // the caller journals as the honest `courier-declined` outcome instead of an engine failure.
  let out
  try {
    out = await _courier().runCourierMarkedText('dispatch external CLI', cmd)
  } catch (e) {
    const c = _courier()
    if (c.CourierTransportError && e instanceof c.CourierTransportError) {
      return { ok: false, declined: true, reason: e.reason || 'courier-declined', answer: e.answer || '' }
    }
    throw e
  }
  if (idleArmed) {
    // Strip the trailing control line and read the idle-kill verdict. The marker is OUR sentinel on its
    // own final line; match the LAST occurrence so any legitimate look-alike earlier in CLI output can't
    // shadow it. A stall returns {stalled:true} so the caller journals outcome:'stalled' + falls open.
    const m = out.match(/\n?__SR_DISPATCH__(\{[^\n]*\})\s*$/)
    if (m) {
      let verdict = null
      try { verdict = JSON.parse(m[1]) } catch (_e) { verdict = null }
      out = out.slice(0, m.index)
      if (verdict && verdict.idleKilled && String(verdict.idleKilled) !== '0') {
        return { ok: false, stalled: true, idleSeconds: Number(verdict.idleSeconds) || null }
      }
    }
  }
  return { ok: true, stdout: out }
}

async function _journalExternal(payload) {
  // Journal the external action as a FIRST-CLASS `external_dispatch` event (FR-6): the audit line's
  // `type` is external_dispatch (Task 4 added the type + the journal_entry.py --event-type flag), and
  // the payload is written AS-IS. #308/#309 enrich it with the RESOLVED `model`, the final `argv`
  // (both engine-controlled config, never external free-text), and the `effectiveTimeout` in seconds,
  // so #299's expected-vs-actual audit can prove the dispatched model/timeout match the readout's
  // promise, and a `timeout` outcome + effectiveTimeout together read as "killed at ceiling after Ns"
  // — distinct from a genuine CLI failure (external-run-failed / unreadable / commit-failed). A failed
  // durable append -> {ok:false} -> the caller treats it as UFR-6 (fail-closed, unauditable).
  return _execJson(
    `python3 ${libPath('journal_entry.py')} --work-item ${shq(payload.workItem || '')} ` +
    `--event-type external_dispatch --payload ` +
    shq(JSON.stringify({ engine: payload.engine, effort: payload.effort, roleKind: payload.roleKind,
      model: payload.model == null ? null : payload.model,
      argv: Array.isArray(payload.argv) ? payload.argv : null,
      effectiveTimeout: payload.effectiveTimeout == null ? null : payload.effectiveTimeout,
      // #309 stall-monitor audit: `stallMonitor` names the monitor state (armed / inert (engine
      // buffers) / unarmed) and `idleSeconds` is the armed idle threshold (null when not armed). A
      // `stalled` outcome + idleSeconds together read as "no output for Ns -> killed" — distinct from a
      // `timeout` outcome (killed at the wall-clock ceiling) or a genuine CLI failure.
      stallMonitor: payload.stallMonitor == null ? null : payload.stallMonitor,
      idleSeconds: payload.idleSeconds == null ? null : payload.idleSeconds,
      // #341: on a `courier-declined` outcome, carry a CLAMPED prefix of the leaf's refusal prose as
      // honest reason-context (the courier hedged instead of running the CLI — the engine was never
      // tried). Present only on the decline path; absent (null) on every other outcome. It is the
      // cheap COURIER leaf's own prose (not engine stdout), clamped to a short prefix so no long or
      // secret-bearing text lands in the audit line.
      declinePrefix: payload.declinePrefix == null ? null : String(payload.declinePrefix),
      verify: payload.verify, outcome: payload.outcome })))
}

// #341: clamp the courier's refusal prose to a short single-line prefix for the courier-declined
// journal reason-context. Collapses whitespace and truncates — never surfaces a long blob.
function _declinePrefix(answer) {
  const s = String(answer == null ? '' : answer).replace(/\s+/g, ' ').trim()
  if (!s) return 'courier returned no execution marker'
  return s.length > 200 ? s.slice(0, 200) + '…' : s
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
  // #309 STALL MONITOR resolution — the monitor half of the ceiling+monitor pair. The caller resolves
  // the idle threshold (resolveIdle: role default or owner override) and passes it as o.idleSeconds; a
  // dispatch with no idle passed (the engine_authz probe / any pre-#309 caller) runs ceiling-only. The
  // monitor is armed ONLY for an engine that streams output when piped — a hypothetical fully-buffering
  // engine would be FALSE-KILLED by a byte-growth watchdog, so we leave it inert (ceiling only) and say
  // so in the journal, rather than arm a dangerous monitor. Both current engines stream (verified
  // 2026-07-09). The threshold is clamped to the ceiling in _runArgv (monitor ≤ ceiling); an override
  // never disables the ceiling — the perl alarm stays inside the wrapper regardless.
  const idleRequested = Number(o.idleSeconds) > 0 ? Math.ceil(Number(o.idleSeconds)) : null
  const engineStreams = _STREAMS_WHEN_PIPED[engine] === true
  const armIdle = engineStreams && idleRequested != null
  const idleSeconds = armIdle ? Math.min(idleRequested, Math.ceil(limitSeconds)) : null
  const stallMonitor = armIdle ? 'armed'
    : (idleRequested != null && !engineStreams ? 'inert (engine buffers)' : 'unarmed')
  // The invariant audit-line fields for THIS dispatch (#308/#309): engine/effort/roleKind + the
  // resolved model, effective timeout ceiling, (once build-argv resolves) the exact argv, and the
  // stall-monitor state + idle threshold. Read at journal time so `argv` reflects resolvedArgv whenever
  // it is available. Each outcome-specific call overlays its own {verify, outcome}. `model` is a native
  // tier short-name or null (session inherit).
  const _jbase = () => ({ workItem: o.workItem, engine, effort, roleKind,
    model: (typeof model === 'string' && model) ? model : null,
    argv: resolvedArgv, effectiveTimeout: limitSeconds,
    stallMonitor, idleSeconds })
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
  // resolvedArgv is hoisted so the journal (below, on EVERY outcome incl. a ceiling timeout) can record
  // the exact argv that was dispatched (#308). It is set synchronously inside `run` right after
  // build-argv resolves, so by the time the race's timeout branch fires (limitMs later, during the CLI
  // run) it already holds the real argv — a timeout journals the argv the CLI was killed while running.
  let resolvedArgv = null
  const run = (async () => {
    const argvObj = await _execJson(
      `python3 ${libPath('engine_adapter.py')} build-argv --engine ${shq(engine)} --role ${shq(roleKind)} ` +
      `--effort ${shq(String(effort == null ? '' : effort))} --cwd ${shq(cwd || '.')} ` +
      `--schema-path ${shq(schemaPath)}` +
      (typeof model === 'string' && model ? ` --model ${shq(model)}` : ''))
    const argv = argvObj && Array.isArray(argvObj.argv) ? argvObj.argv : (Array.isArray(argvObj) ? argvObj : null)
    if (!argv) return { ok: false, reason: 'build-argv-failed' }
    resolvedArgv = argv

    // Feed the staged prompt file to the external process stdin (the argv itself carries no prompt).
    // cwd is threaded through so _runArgv can confine the run to the worktree (FR-8; see _runArgv).
    // limitSeconds bounds the perl-alarm ceiling (belt-and-suspenders with the JS race); idleSeconds +
    // armIdle arm the #309 byte-activity stall monitor (≤ ceiling). A monitor idle-kill returns
    // {stalled:true} -> outcome:'stalled' (distinct from the ceiling 'timeout'); the caller falls open.
    let runRes = await _runArgv(argv, promptPath, cwd, limitSeconds, idleSeconds, armIdle)
    // #341 COURIER DECLINE: the hardened courier proved (via a missing __SR_EXIT marker after its own
    // retry/fallback chain) that the shell NEVER RAN — a safety-trained cheapest-model leaf refused
    // the autonomous engine command and answered prose. The engine was NEVER TRIED, so this is NOT an
    // `external-run-failed` engine failure (promise 4/5: never blame the engine for a courier's
    // refusal). Journal it as the honest `courier-declined` outcome carrying the refusal prose, then
    // retry ONCE through the hardened path (safe: the CLI never executed, so there are no partial
    // side-effects to repeat). Journal BOTH attempts so the audit trail shows the decline count. On a
    // second decline, fall open with reason `courier-declined` (the caller discards nothing new and
    // falls open to Claude, exactly as any dispatch failure).
    if (runRes && runRes.declined) {
      await _journalExternal(Object.assign(_jbase(), { verify: null,
        outcome: 'courier-declined', declinePrefix: _declinePrefix(runRes.answer) }))
      runRes = await _runArgv(argv, promptPath, cwd, limitSeconds, idleSeconds, armIdle)
      if (runRes && runRes.declined) {
        await _journalExternal(Object.assign(_jbase(), { verify: null,
          outcome: 'courier-declined', declinePrefix: _declinePrefix(runRes.answer) }))
        return { ok: false, reason: 'courier-declined', declined: true }
      }
    }
    if (runRes && runRes.stalled) return { ok: false, reason: 'stalled' }
    if (!runRes || !runRes.ok) return { ok: false, reason: 'external-run-failed' }
    const rawStdout = runRes.stdout

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

  // #341: a fully-declined dispatch already journaled BOTH courier-declined attempts inline (above,
  // in `run`) — the engine was never tried, so there is no ok/timeout/commit outcome to record here.
  // Return the fall-open reason WITHOUT re-journaling (which would add a spurious third audit line for
  // the same never-executed dispatch). The caller falls open to Claude exactly as for any failure.
  if (parsed && parsed.declined) return { ok: false, reason: 'courier-declined' }

  // 4a. Author role: no commit (see isAuthor above). Journal first (UFR-6 symmetry — an
  // unjournaled author dispatch is as unauditable as any other), then hand the parsed notify
  // back; the caller's usableDraft post-check decides acceptance and falls open on failure.
  if (isAuthor) {
    const jAuthor = await _journalExternal(Object.assign(_jbase(), { verify: null,
      outcome: parsed.ok ? 'ok' : (parsed.reason || 'failed') }))
    if (!(jAuthor && jAuthor.ok)) return { ok: false, reason: 'unauditable' }
    return parsed.ok ? { ok: true, notify: parsed.notify || [] } : { ok: false, reason: parsed.reason }
  }

  // 4. Read role: return findings straight through (no commit). Failure -> caller falls open to Claude.
  // FIX 5 (UFR-6 symmetry): a read role is JUST as unauditable as a write role when the journal
  // append itself fails — mirror the write-role check below (a failed journal -> {ok:false,
  // reason:'unauditable'}) instead of discarding the append's own success/failure unchecked.
  if (!isWrite) {
    const jRead = await _journalExternal(Object.assign(_jbase(), { verify: null,
      outcome: parsed.ok ? 'ok' : (parsed.reason || 'failed') }))
    if (!(jRead && jRead.ok)) return { ok: false, reason: 'unauditable' }
    return parsed.ok ? { findings: parsed.findings || [] } : { ok: false, reason: parsed.reason }
  }

  // 5. Write role failure -> only uncommitted edits exist; caller reuses resetUncommitted + falls open (UFR-2).
  if (!parsed.ok) {
    await _journalExternal(Object.assign(_jbase(), { verify: null,
      outcome: parsed.reason || 'failed' }))
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
    await _journalExternal(Object.assign(_jbase(), { verify: null,
      outcome: 'commit-failed' }))
    return { ok: false, reason }
  }

  // 7. Journal BEFORE returning the native worker shape (UFR-6: unauditable -> the caller fails closed).
  const j = await _journalExternal(Object.assign(_jbase(), {
    verify: 'pending', outcome: 'ok' }))
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

// _STREAMS_WHEN_PIPED is exported for the drift guard in the stall-monitor smoke (every dispatchable
// external engine must have an explicit streams-when-piped verdict) — not a public seam.
module.exports = { dispatchExternal, DEFAULT_STALL_LIMIT_SECONDS, __resetHarnessNotice,
  _STREAMS_WHEN_PIPED, strictify,
  // #341 test-only: the pure production command composer, exported so the real-seam detector
  // (CONVENTIONS §12.2) builds the byte-faithful watchdog command and drives it through a REAL leaf.
  _composeDispatchCommand }
